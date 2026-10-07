"""Renders the mouse cursor: a mage's gauntlet pointing up-left, to res/arpg/ui/cursor_render.png plus its hotspot.

blender -b --factory-startup -P tools/blender/render_cursor.py   (then py -3.12 tools/make_arpg_ui.py builds the cursor)"""
import json
import math
import os

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "res", "arpg", "ui", "cursor_render.png")
SIZE = 512


def material(name, color, metallic=0.0, roughness=0.5, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color + (1.0,)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = emission + (1.0,)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def blob(name, location, scale, rotation=(0, 0, 0), mat=None, parent=None, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = Euler([math.radians(a) for a in rotation])
    bpy.ops.object.shade_smooth()
    if mat:
        obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    return obj


def capsule(meta, a, b, radius):
    a, b = Vector(a), Vector(b)
    el = meta.elements.new(type="CAPSULE")
    el.co, el.radius = (a + b) / 2, radius
    el.size_x = (b - a).length / 2
    el.rotation = Vector((1, 0, 0)).rotation_difference(b - a)
    return el


def surface_z(obj, x, y):
    hit, location, *_ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(), Vector((x, y, 5)),
                                                   Vector((0, 0, -1)))
    return location.z if hit else 0.2


def build():
    leather = material("leather", (0.035, 0.016, 0.075), roughness=0.4)
    cloth = material("cuff", (0.05, 0.02, 0.11), roughness=0.65)
    gold = material("gold", (1.0, 0.68, 0.28), metallic=1.0, roughness=0.25)
    gem = material("gem", (0.02, 0.12, 0.6), roughness=0.05, emission=(0.15, 0.4, 1.0), strength=0.9)
    # The glove is a skin-modifier skeleton (joints with radii), subdivided into one smooth surface. The hand lies in
    # the XY plane pointing along +Y with its back toward +Z (the camera).
    joints = {"wrist": ((0.0, -0.36, 0.0), 0.3), "palm": ((0.0, -0.02, 0.0), 0.33), "palm2": ((-0.02, 0.2, 0.0), 0.31),
              "thumb0": ((0.3, 0.02, -0.02), 0.15), "thumb1": ((0.47, 0.24, -0.06), 0.125), "thumb2": ((0.41, 0.45, -0.15), 0.105)}
    bones = [("wrist", "palm"), ("palm", "palm2"), ("palm", "thumb0"), ("thumb0", "thumb1"), ("thumb1", "thumb2")]
    knuckles = [("index", 0.24, 0.42, 0.15), ("middle", 0.02, 0.46, 0.145), ("ring", -0.19, 0.43, 0.135),
                ("pinky", -0.37, 0.36, 0.12)]
    for k, (name, x, y, r) in enumerate(knuckles):
        joints[name] = ((x, y, 0.0), r)
        bones.append(("palm2", name))
        if name == "index":
            for j, (yy, rr) in enumerate(((0.72, 0.125), (0.97, 0.112), (1.17, 0.1))):
                joints["index%d" % j] = ((x + 0.012 * (j + 1), yy, 0.0), rr)
                bones.append(("index%d" % (j - 1) if j else "index", "index%d" % j))
        else:
            joints[name + "1"] = ((x, y + 0.16, -0.13), r * 0.85)
            joints[name + "2"] = ((x * 0.97, y + 0.02, -0.25), r * 0.75)
            bones += [(name, name + "1"), (name + "1", name + "2")]
    names = list(joints)
    mesh = bpy.data.meshes.new("glove")
    mesh.from_pydata([joints[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in bones], [])
    glove = bpy.data.objects.new("glove", mesh)
    bpy.context.scene.collection.objects.link(glove)
    skin = glove.modifiers.new("skin", "SKIN")
    skin.use_smooth_shade = True
    for i, n in enumerate(names):
        r = joints[n][1]
        glove.data.skin_vertices[0].data[i].radius = (r, r)
    glove.data.skin_vertices[0].data[names.index("wrist")].use_root = True
    glove.modifiers.new("smooth", "SUBSURF").levels = 2
    glove.scale = (1.0, 1.0, 0.72)
    glove.data.materials.append(leather)
    hand = bpy.data.objects.new("hand", None)
    bpy.context.scene.collection.objects.link(hand)
    glove.parent = hand
    bpy.context.view_layer.update()
    tip = Vector((0.276, 1.27, 0.0))
    for x in (0.26, 0.02, -0.2, -0.39):
        z = surface_z(glove, x, 0.42)
        blob("stud", (x, 0.42, z + 0.005), (0.045, 0.045, 0.03), mat=gold, parent=hand, segments=16)
    z = surface_z(glove, -0.02, 0.02)
    blob("setting", (-0.02, 0.02, z - 0.01), (0.15, 0.18, 0.03), mat=gold, parent=hand)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.12, location=(-0.02, 0.02, z + 0.03))
    stone = bpy.context.object
    stone.scale = (1.0, 1.2, 0.55)
    stone.data.materials.append(gem)
    stone.parent = hand
    # The cuff: a flared cone with gold bands at both ends, built along its own Z and laid along -Y, flattened.
    cuff = bpy.data.objects.new("cuff", None)
    bpy.context.scene.collection.objects.link(cuff)
    cuff.location, cuff.rotation_euler, cuff.scale = (0, -0.62, 0), (math.radians(90), 0, 0), (1.0, 0.62, 1.0)
    cuff.parent = hand
    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0.33, radius2=0.47, depth=0.46, location=(0, 0, 0))
    cone = bpy.context.object
    bpy.ops.object.shade_smooth()
    cone.data.materials.append(cloth)
    cone.parent = cuff
    for zz, r in ((0.23, 0.48), (-0.23, 0.34)):
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.05, location=(0, 0, zz), major_segments=64,
                                         minor_segments=16)
        ring = bpy.context.object
        bpy.ops.object.shade_smooth()
        ring.data.materials.append(gold)
        ring.parent = cuff
    # Point up-left on screen and roll a little so the side of the hand catches the light.
    hand.rotation_euler = Euler((math.radians(18), math.radians(-24), math.radians(32)))
    bpy.context.view_layer.update()
    return hand.matrix_world @ tip


def stage():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.9
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = (0.05, 0.15, 6.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for name, location, energy, color, size in (("key", (-2.5, 2.5, 4.0), 700.0, (1.0, 0.88, 0.74), 2.0),
                                                ("rim", (3.0, -2.0, 1.5), 900.0, (0.6, 0.7, 1.0), 1.0),
                                                ("fill", (0.0, 0.0, 5.0), 60.0, (1.0, 1.0, 1.0), 4.0)):
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.color, light.size = energy, color, size
        obj = bpy.data.objects.new(name, light)
        obj.location = location
        obj.rotation_euler = (Vector((0, 0, 0)) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(obj)
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.07, 1.0)
    scene.world = world
    return scene, cam


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tip = build()
    scene, cam = stage()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    u, v, _ = world_to_camera_view(scene, cam, tip)
    hotspot = (u, 1.0 - v)
    with open(OUT.replace(".png", ".json"), "w") as f:
        json.dump({"hotspot": hotspot, "size": SIZE}, f)
    print("cursor rendered, fingertip at %.3f, %.3f of the image" % hotspot)


main()
