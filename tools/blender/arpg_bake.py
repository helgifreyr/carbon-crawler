"""Texture bakes for the animated characters: procedural materials per palette slot, baked in Cycles onto a UV unwrap.

Writes <prefix>_<variant>.png (colour with ambient occlusion) per colour variant and <prefix>_n.png (tangent-space
normal in rgb, specular mask in alpha)."""
import math
import os

import bpy
import numpy as np

SIZE = 1024
MARGIN = 6


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _node(tree, kind, **inputs):
    node = tree.nodes.new(kind)
    for name, value in inputs.items():
        if name in node.inputs:
            node.inputs[name].default_value = value
        else:
            setattr(node, name, value)
    return node


def _material(slot, look):
    """A Principled material whose colour comes from an RGB node (swapped per variant) and whose surface detail is
    procedural: look is (roughness, metallic, bump kind, bump scale)."""
    roughness, metallic, kind, scale = look
    mat = bpy.data.materials.new("slot%d" % slot)
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    links = tree.links
    rgb = _node(tree, "ShaderNodeRGB")
    rgb.name = "slot_color"
    coord = _node(tree, "ShaderNodeTexCoord")
    if kind == "scales":
        tex = _node(tree, "ShaderNodeTexVoronoi", Scale=scale)
        out = tex.outputs["Distance"]
    elif kind == "weave":
        tex = _node(tree, "ShaderNodeTexWave", Scale=scale, Distortion=1.5, Detail=3.0)
        out = tex.outputs["Fac"]
    elif kind == "grain":
        tex = _node(tree, "ShaderNodeTexWave", Scale=scale, Distortion=6.0, Detail=4.0, wave_type="BANDS")
        out = tex.outputs["Fac"]
    elif kind == "ridges":
        tex = _node(tree, "ShaderNodeTexWave", Scale=scale, Distortion=0.8, wave_type="RINGS")
        out = tex.outputs["Fac"]
    else:
        tex = _node(tree, "ShaderNodeTexNoise", Scale=scale, Detail=6.0)
        out = tex.outputs["Fac"]
    links.new(coord.outputs["Object"], tex.inputs["Vector"])
    # Colour varies a little with the same pattern, so the bake isn't one flat tone per part.
    mix = _node(tree, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    mix.inputs["Factor"].default_value = 0.35
    color_in = [sock for sock in mix.inputs if sock.type == "RGBA"]
    color_out = next(sock for sock in mix.outputs if sock.type == "RGBA")
    links.new(rgb.outputs["Color"], color_in[0])
    ramp = _node(tree, "ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.72
    ramp.inputs["To Max"].default_value = 1.15
    links.new(out, ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], color_in[1])
    # Painted-look shading baked into the colour: convex edges catch light, crevices darken, and the figure darkens
    # toward the floor.
    geometry = _node(tree, "ShaderNodeNewGeometry")
    edges = _node(tree, "ShaderNodeMapRange")
    edges.inputs["From Min"].default_value, edges.inputs["From Max"].default_value = 0.42, 0.58
    edges.inputs["To Min"].default_value, edges.inputs["To Max"].default_value = 0.7, 1.3
    links.new(geometry.outputs["Pointiness"], edges.inputs["Value"])
    xyz = _node(tree, "ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Object"], xyz.inputs["Vector"])
    height = _node(tree, "ShaderNodeMapRange")
    height.inputs["From Min"].default_value, height.inputs["From Max"].default_value = -0.5, 0.6
    height.inputs["To Min"].default_value, height.inputs["To Max"].default_value = 0.72, 1.05
    links.new(xyz.outputs["Z"], height.inputs["Value"])
    shade = _node(tree, "ShaderNodeMath", operation="MULTIPLY")
    links.new(edges.outputs["Result"], shade.inputs[0])
    links.new(height.outputs["Result"], shade.inputs[1])
    painted = _node(tree, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    painted.inputs["Factor"].default_value = 1.0
    paint_in = [sock for sock in painted.inputs if sock.type == "RGBA"]
    links.new(color_out, paint_in[0])
    links.new(shade.outputs["Value"], paint_in[1])
    links.new(next(sock for sock in painted.outputs if sock.type == "RGBA"), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if kind != "none":
        bump = _node(tree, "ShaderNodeBump", Strength={"noise": 0.35, "scales": 0.45}.get(kind, 0.6), Distance=0.03)
        links.new(out, bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    image_node = _node(tree, "ShaderNodeTexImage")
    image_node.name = "bake_target"
    tree.nodes.active = image_node
    return mat


def _image(name, non_color=False):
    img = bpy.data.images.new(name, SIZE, SIZE, alpha=True, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def _target(obj, img):
    for mat in obj.data.materials:
        node = mat.node_tree.nodes["bake_target"]
        node.image = img
        mat.node_tree.nodes.active = node


def _pixels(img):
    px = np.empty(SIZE * SIZE * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(SIZE, SIZE, 4)


def _save(name, pixels, out_dir, non_color=False):
    img = _image(name, non_color)
    img.pixels.foreach_set(pixels.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(out_dir, name + ".png")
    img.file_format = "PNG"
    img.save()


def unwrap(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_textures(obj, prefix, looks, variants, out_dir):
    """looks: palette slot -> (roughness, metallic, bump kind, bump scale); variants: name -> {slot: (r, g, b)}."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    # Fill the existing slots in place: clearing them would reset every face to slot 0.
    slots = max(p.material_index for p in obj.data.polygons) + 1
    while len(obj.data.materials) < slots:
        obj.data.materials.append(None)
    for slot in range(slots):
        obj.data.materials[slot] = _material(slot, looks.get(slot, (0.6, 0.0, "noise", 30.0)))
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bake = scene.render.bake
    bake.margin, bake.use_clear = MARGIN, True

    scene.cycles.samples = 64
    ao_img = _image(prefix + "_ao", non_color=True)
    _target(obj, ao_img)
    bpy.ops.object.bake(type="AO")
    ao = _pixels(ao_img)[..., 0]
    scene.cycles.samples = 1
    normal_img = _image(prefix + "_nrm", non_color=True)
    _target(obj, normal_img)
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
    normal = _pixels(normal_img)
    rough_img = _image(prefix + "_rough", non_color=True)
    _target(obj, rough_img)
    bpy.ops.object.bake(type="ROUGHNESS")
    rough = _pixels(rough_img)[..., 0]
    normal[..., 3] = np.clip((1.0 - rough) ** 1.5 * 1.1, 0.04, 1.0)
    _save(prefix + "_n", normal, out_dir, non_color=True)

    occlusion = 0.35 + 0.65 * ao
    for variant, colors in variants.items():
        for slot, mat in enumerate(obj.data.materials):
            rgb = colors.get(slot, (128, 128, 128))
            mat.node_tree.nodes["slot_color"].outputs[0].default_value = tuple(srgb_to_linear(c) for c in rgb) + (1.0,)
        color_img = _image(prefix + "_" + variant)
        _target(obj, color_img)
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
        px = _pixels(color_img)
        # Pixels read back already in sRGB; darken creases by the baked occlusion in roughly linear light.
        px[..., :3] = np.clip(((px[..., :3] ** 2.2) * occlusion[..., None]) ** (1 / 2.2), 0, 1)
        px[..., 3] = 1.0
        _save(prefix + "_" + variant, px, out_dir)
