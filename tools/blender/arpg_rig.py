import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import cmf
import dds


def mirror_name(name):
    if name.endswith(".p"):
        return name[:-2] + ".n"
    if name.endswith(".n"):
        return name[:-2] + ".p"
    return name


def rigid(name):
    return lambda co: {name: 1.0}


def chain(*segments, sharpness=4):
    """Weights a vertex to the nearest bone segments, blending smoothly across the joints between them."""
    segs = [(name, Vector(a), Vector(b)) for name, a, b in segments]

    def weights(co):
        scored = []
        for name, a, b in segs:
            ab = b - a
            t = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
            scored.append((1.0 / ((co - (a + ab * t)).length ** sharpness + 1e-7), name))
        scored.sort(reverse=True)
        top = scored[:2]
        total = sum(w for w, _ in top)
        out = {}
        for w, name in top:
            out[name] = out.get(name, 0.0) + w / total
        return out
    return weights


def curve(t, keys):
    """Piecewise smoothstep between (time, value) keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return v0 + (v1 - v0) * u
    return keys[-1][1]


X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


class Clip:
    def __init__(self, name, frames, fps, loop, pose, stride=None, events=None):
        self.name, self.frames, self.fps, self.loop, self.pose, self.stride = name, frames, fps, loop, pose, stride
        self.events = events or {}

    def times(self):
        n = self.frames
        return [i / n for i in range(n)] if self.loop else [i / (n - 1) for i in range(n)]


def _merge(model, scale_matrix, triangulate=True):
    bm = bmesh.new()
    layer_ids = []
    for index, layer in enumerate(("base", "glow")):
        tmp = bpy.data.meshes.new("tmp")
        model.layers[layer].to_mesh(tmp)
        before = len(bm.faces)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        layer_ids += [index] * (len(bm.faces) - before)
    face_layer = bm.faces.layers.int.new("layer")
    bm.faces.ensure_lookup_table()
    for face, index in zip(bm.faces, layer_ids):
        face[face_layer] = index
    deform = bm.verts.layers.deform.verify()
    halo_verts = []
    for co, _, bone, _ in model.halos:
        v = bm.verts.new(co)
        v[deform][model.bone_index(bone)] = 1.0
        halo_verts.append(v)
    bm.transform(scale_matrix)
    if triangulate:
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.index_update()
    return bm, [v.index for v in halo_verts]


def _apply(obj, kind, **settings):
    mod = obj.modifiers.new(kind.lower(), kind)
    for key, value in settings.items():
        setattr(mod, key, value)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _build_objects(name, model, scale_matrix, smooth_angle, subdivide=False):
    bm, halo_indices = _merge(model, scale_matrix, triangulate=not subdivide)
    bm.verts.ensure_lookup_table()
    halo_points = [bm.verts[i].co.copy() for i in halo_indices] if subdivide else None
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.set_sharp_from_angle(angle=smooth_angle)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for bone_name, _, _, _ in model.bones:
        obj.vertex_groups.new(name=bone_name)
    if subdivide:
        # Modifiers clamp material indices to the slots a mesh has, so give it one per palette index first.
        for _ in range(max(p.material_index for p in mesh.polygons) + 1):
            mesh.materials.append(None)
        # One Catmull-Clark level rounds the primitives off; weights, materials and the layer attribute follow.
        _apply(obj, "SUBSURF", levels=1, render_levels=1)
        _apply(obj, "TRIANGULATE")
        mesh = obj.data
        mesh.set_sharp_from_angle(angle=smooth_angle)
        loose = {v.index for v in mesh.vertices} - {i for e in mesh.edges for i in e.vertices}
        halo_indices = [min(loose, key=lambda i: (mesh.vertices[i].co - p).length) for p in halo_points]

    arm_data = bpy.data.armatures.new(name + "_rig")
    arm = bpy.data.objects.new(name + "_rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    edit = {}
    for bone_name, head, tail, parent in model.bones:
        eb = arm_data.edit_bones.new(bone_name)
        eb.head, eb.tail = scale_matrix @ Vector(head), scale_matrix @ Vector(tail)
        if parent:
            eb.parent = edit[parent]
        edit[bone_name] = eb
    bpy.ops.object.mode_set(mode="OBJECT")
    modifier = obj.modifiers.new("rig", "ARMATURE")
    modifier.object = arm
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj, arm, halo_indices


def _apply_pose(arm, pose):
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    for bone_name, spec in pose.items():
        if bone_name == "root_loc":
            continue
        pb = arm.pose.bones[bone_name]
        to_local = pb.bone.matrix_local.to_3x3().inverted()
        q = Quaternion()
        for axis, angle in spec:
            q = q @ Quaternion((to_local @ axis).normalized(), angle)
        pb.rotation_quaternion = q
    if "root_loc" in pose:
        root = arm.pose.bones[0]
        root.location = root.bone.matrix_local.to_3x3().inverted() @ Vector(pose["root_loc"])


def _evaluate(obj):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    me = evaluated.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    normals = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", normals)
    evaluated.to_mesh_clear()
    return co.reshape(-1, 3), normals.reshape(-1, 3)


def engine(a):
    # Blender is Z-up with the front at -Y; the engine is Y-up with the front at +Z.
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], axis=1)


def bake(name, model, clips, meshes_dir, anims_dir, scale_matrix, smooth_angle, palette_uv, textures=None):
    """Rigs the model in Blender, bakes every clip frame into vertex animation textures, writes the meshes.

    With textures (a function of the Blender object), the model is subdivided, unwrapped and texture-baked first."""
    obj, arm, halo_indices = _build_objects(name, model, scale_matrix, smooth_angle, subdivide=textures is not None)
    me = obj.data
    uv_data = None
    if textures is not None:
        from arpg_bake import unwrap
        unwrap(obj)
        textures(obj)
        uv_data = me.uv_layers.active.data
    layer_attr = me.attributes["layer"].data
    loop_vert = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", loop_vert)
    rest_co, rest_nrm = _evaluate(obj)

    columns, layers = [], {0: {"keys": {}, "verts": [], "indices": []}, 1: {"keys": {}, "verts": [], "indices": []}}
    for poly in me.polygons:
        layer = layers[layer_attr[poly.index].value]
        for li in poly.loop_indices:
            vi = int(loop_vert[li])
            uv = tuple(np.round(uv_data[li].uv, 5)) if uv_data is not None else None
            key = (vi, tuple(np.round(rest_nrm[li], 3)), poly.material_index, uv)
            index = layer["keys"].get(key)
            if index is None:
                index = layer["keys"][key] = len(layer["verts"])
                layer["verts"].append((len(columns), vi, poly.material_index, uv))
                columns.append((vi, li))
            layer["indices"].append(index)
    halo_columns = []
    for vi in halo_indices:
        halo_columns.append(len(columns))
        columns.append((vi, None))

    col_vert = np.array([c[0] for c in columns])
    col_loop = np.array([c[1] if c[1] is not None else 0 for c in columns])
    width = len(columns)
    height = sum(c.frames for c in clips)
    pos = np.zeros((height, width, 4), dtype=np.float32)
    nrm = np.zeros((height, width, 4), dtype=np.float32)
    table, row = {}, 0
    for clip in clips:
        table[clip.name] = {"row": row, "frames": clip.frames, "fps": clip.fps, "loop": clip.loop,
                            "stride": clip.stride, "events": clip.events}
        for t in clip.times():
            _apply_pose(arm, clip.pose(t))
            co, normals = _evaluate(obj)
            pos[row, :, :3] = engine(co[col_vert])
            pos[row, :, 3] = 1.0
            nrm[row, :, :3] = engine(normals[col_loop])
            row += 1
    _apply_pose(arm, {})

    os.makedirs(anims_dir, exist_ok=True)
    dds.write_rgba_float(os.path.join(anims_dir, name + "_pos.dds"), pos)
    dds.write_rgba_float(os.path.join(anims_dir, name + "_nrm.dds"), nrm)
    # Named halo points double as sockets: where e.g. the staff orb is on every baked frame, in model space.
    sockets = {h[3]: np.round(pos[:, column, :3], 4).tolist() for h, column in zip(model.halos, halo_columns) if h[3]}
    with open(os.path.join(anims_dir, name + ".json"), "w", newline="\n") as f:
        json.dump({"width": width, "height": height, "clips": table, "sockets": sockets}, f)

    # Bounds cover every baked pose, so a character lying down after a death isn't culled.
    lo, hi = pos[..., :3].reshape(-1, 3).min(axis=0), pos[..., :3].reshape(-1, 3).max(axis=0)
    extent = [tuple(lo), tuple(hi)]
    rest_engine_co, rest_engine_nrm = engine(rest_co), engine(rest_nrm)
    counts = {}
    for layer_id, suffix in ((0, ""), (1, "_glow")):
        layer = layers[layer_id]
        if not layer["indices"]:
            continue
        positions, normals, uvs, uv1 = [], [], [], []
        for column, vi, material, uv in layer["verts"]:
            li = columns[column][1]
            positions.append(tuple(rest_engine_co[vi]))
            normals.append(tuple(rest_engine_nrm[li]))
            u, v = uv if uv is not None else palette_uv(material)
            uvs.append((u, 1.0 - v))
            uv1.append(((column + 0.5) / width, 0.0))
        cmf.write_mesh(os.path.join(meshes_dir, name + suffix + ".cmf"), positions, normals, uvs, layer["indices"],
                       name=name + suffix, uv1=uv1, extra_bounds=extent)
        counts[suffix or "base"] = (len(layer["verts"]), len(layer["indices"]) // 3)

    positions, normals, uvs, uv1, indices = [], [], [], [], []
    for (co, size, _, _), column in zip(model.halos, halo_columns):
        base = len(positions)
        center = tuple(rest_engine_co[columns[column][0]])
        scaled = size * scale_matrix.to_scale().x
        for corner in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
            positions.append(center)
            normals.append((scaled, 0.0, 0.0))
            uvs.append(corner)
            uv1.append(((column + 0.5) / width, 0.0))
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    if indices:
        cmf.write_mesh(os.path.join(meshes_dir, name + "_halo.cmf"), positions, normals, uvs, indices,
                       name=name + "_halo", uv1=uv1, extra_bounds=extent)
    bpy.data.objects.remove(obj)
    bpy.data.objects.remove(arm)
    counts["vat"] = (width, height)
    return counts
