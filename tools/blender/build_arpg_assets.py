import hashlib
import json
import math
import os
import random
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "demo"))
sys.path.insert(0, HERE)

import cmf
from arpg_anims import HOUND_CLIPS, IMP_CLIPS, MAGE_CLIPS
from arpg_bake import bake_textures
from arpg_rig import bake, chain, mirror_name, rigid
from arpg_world import KINDS, SPELLS

FROST_RANGE, METEOR_RADIUS = SPELLS["frost"]["range"], SPELLS["meteor"]["radius"]
NOVA_RADIUS, SLAM_RADIUS = SPELLS["nova"]["radius"], KINDS["brute"]["slam"]["radius"]
from arpg_layout import DOOR_HALF, FLOOR_Y, LIGHTMAP_PX_PER_M, WALL_BASE_Y, WALL_H, test_level
from arpg_map import CELL

# The fixed test level: its torch light is baked here, and every placeable's LightMapRect defaults to its extent.
TEST_LEVEL = test_level()
LIGHTMAP_RECT = TEST_LEVEL.cells.extent

OUT = os.path.join(ROOT, "res", "arpg")
PREVIEW = os.path.join(ROOT, "demo", "out", "arpg_assets_preview.png")
EFFECT = "res:/graphics/effect/game/texmesh.fx"
BLOB_EFFECT = "res:/graphics/effect/game/blob.fx"
HALO_EFFECT = "res:/graphics/effect/game/halo.fx"
VAT_EFFECT = "res:/graphics/effect/game/vat.fx"
VAT_HALO_EFFECT = "res:/graphics/effect/game/halo_vat.fx"
WALL_EFFECT = "res:/graphics/effect/game/wall.fx"
FX_BURST_EFFECT = "res:/graphics/effect/game/fx_burst.fx"
FX_FLAME_EFFECT = "res:/graphics/effect/game/fx_flame.fx"
TORCH_REACH_M, TORCH_STRENGTH, TORCH_COLOR = 9.0, 1.5, (1.0, 0.6, 0.28)
FX_TRAIL_EFFECT = "res:/graphics/effect/game/fx_trail.fx"
# Procedural particle effects: FxTime is (age, duration); the rest is baked per effect.
def area_motion(radius, drag, seconds, gravity=0.0, up=0.0):
    """FxMotion for a burst whose particles coast out to exactly `radius` over its `seconds` of life."""
    return (radius * drag / (1.0 - math.exp(-drag * seconds)), drag, gravity, up)


FX_BURSTS = {
    "fx_impact": (24, {"FxTime": (0, 0.42, 0, 0), "FxColor": (1.0, 0.72, 0.32, 2.2), "FxColorEnd": (1.0, 0.22, 0.04, 1),
                       "FxSize": (0.09, 0.02, 0, 0), "FxMotion": (6.5, 4.0, -9.0, 0.45)}),
    "fx_death": (40, {"FxTime": (0, 0.95, 0, 0), "FxColor": (1.0, 0.36, 0.14, 1.7), "FxColorEnd": (0.4, 0.05, 0.02, 1),
                      "FxSize": (0.17, 0.04, 0, 0), "FxMotion": (3.6, 2.5, -3.0, 0.9)}),
    "fx_levelup": (64, {"FxTime": (0, 0.9, 0, 0), "FxColor": (1.0, 0.85, 0.35, 2.4), "FxColorEnd": (1.0, 0.5, 0.1, 1),
                        "FxSize": (0.26, 0.05, 0, 0), "FxMotion": (4.5, 2.0, 1.5, 1.4), "FxShape": (1.0, 0.3, 1.0, 0)}),
    "fx_pickup_health": (22, {"FxTime": (0, 0.5, 0, 0), "FxColor": (1.0, 0.3, 0.25, 2.2), "FxColorEnd": (0.6, 0.05, 0.05, 1),
                              "FxSize": (0.18, 0.03, 0, 0), "FxMotion": (2.2, 3.0, 3.0, 1.6)}),
    "fx_pickup_mana": (22, {"FxTime": (0, 0.5, 0, 0), "FxColor": (0.35, 0.6, 1.0, 2.2), "FxColorEnd": (0.05, 0.15, 0.6, 1),
                            "FxSize": (0.18, 0.03, 0, 0), "FxMotion": (2.2, 3.0, 3.0, 1.6)}),
    "fx_goo": (64, {"FxTime": (0, 0.8, 0, 0), "FxColor": (0.7, 1.0, 0.25, 1.8), "FxColorEnd": (0.2, 0.4, 0.05, 1),
                    "FxSize": (0.24, 0.08, 0, 0), "FxMotion": (6.5, 4.5, -8.0, 0.7), "FxShape": (1.0, 0.25, 1.0, 0)}),
    "fx_mend": (20, {"FxTime": (0, 0.6, 0, 0), "FxColor": (0.4, 1.0, 0.8, 2.2), "FxColorEnd": (0.05, 0.5, 0.4, 1),
                     "FxSize": (0.16, 0.03, 0, 0), "FxMotion": (1.6, 3.2, 2.5, 1.4)}),
    "fx_zap": (20, {"FxTime": (0, 0.3, 0, 0), "FxColor": (0.6, 0.8, 1.0, 2.6), "FxColorEnd": (0.2, 0.3, 1.0, 1),
                    "FxSize": (0.2, 0.03, 0, 0), "FxMotion": (6.0, 5.0, 0.0, 0.3)}),
    "fx_frost": (96, {"FxTime": (0, 0.5, 0, 0), "FxColor": (0.55, 0.8, 1.0, 1.1), "FxColorEnd": (0.2, 0.45, 1.0, 1),
                      "FxSize": (0.24, 0.12, 0, 0), "FxMotion": area_motion(FROST_RANGE + 0.4, 2.0, 0.5),
                      "FxShape": (0.75, 0.12, 0.25, 0), "FxBias": (0.0, 0.0, 1.35, 0), "FxVary": (0.9, 0.55, 0, 0)}),
    "fx_meteor": (80, {"FxTime": (0, 0.8, 0, 0), "FxColor": (1.0, 0.55, 0.15, 2.6), "FxColorEnd": (0.6, 0.08, 0.02, 1),
                       "FxSize": (0.5, 0.14, 0, 0), "FxMotion": area_motion(METEOR_RADIUS, 2.6, 0.8, gravity=-4.0, up=0.5),
                       "FxShape": (1.0, 0.4, 1.0, 0), "FxVary": (0.8, 0.6, 0, 0)}),
    "fx_embers": (20, {"FxTime": (0, 0.7, 0, 0), "FxColor": (1.0, 0.5, 0.12, 2.0), "FxColorEnd": (0.5, 0.05, 0.02, 1),
                       "FxSize": (0.32, 0.05, 0, 0), "FxMotion": (1.4, 2.0, 2.5, 1.5)}),
    "fx_slam": (48, {"FxTime": (0, 0.6, 0, 0), "FxColor": (0.75, 0.6, 0.45, 1.2), "FxColorEnd": (0.35, 0.28, 0.22, 1),
                     "FxSize": (0.5, 0.22, 0, 0), "FxMotion": area_motion(SLAM_RADIUS, 3.3, 0.6, gravity=1.0, up=0.1),
                     "FxShape": (1.0, 0.1, 1.0, 0), "FxVary": (0.9, 0.8, 0, 0)}),
    "fx_nova": (72, {"FxTime": (0, 0.45, 0, 0), "FxColor": (1.0, 0.5, 0.16, 2.3), "FxColorEnd": (0.8, 0.1, 0.02, 1),
                     "FxSize": (0.38, 0.18, 0, 0), "FxMotion": area_motion(NOVA_RADIUS + 0.5, 4.0, 0.45),
                     "FxShape": (1.0, 0.05, 1.0, 0), "FxVary": (0.92, 0.85, 0, 0)}),
    "fx_blink": (28, {"FxTime": (0, 0.42, 0, 0), "FxColor": (0.62, 0.5, 1.0, 2.2), "FxColorEnd": (0.2, 0.1, 0.6, 1),
                      "FxSize": (0.26, 0.04, 0, 0), "FxMotion": (3.0, 4.0, 2.0, 0.6)}),
    "fx_cast_self": (24, {"FxTime": (0, 0.36, 0, 0), "FxColor": (0.4, 1.0, 0.55, 2.2), "FxColorEnd": (0.1, 0.5, 0.2, 1),
                          "FxSize": (0.22, 0.03, 0, 0), "FxMotion": (3.4, 5.0, 1.5, 0.2)}),
    "fx_cast_purple": (24, {"FxTime": (0, 0.36, 0, 0), "FxColor": (0.8, 0.5, 1.0, 2.2), "FxColorEnd": (0.35, 0.1, 0.6, 1),
                            "FxSize": (0.22, 0.03, 0, 0), "FxMotion": (3.4, 5.0, 1.5, 0.2)}),
    "fx_cast_amber": (24, {"FxTime": (0, 0.36, 0, 0), "FxColor": (1.0, 0.75, 0.3, 2.2), "FxColorEnd": (0.6, 0.3, 0.05, 1),
                           "FxSize": (0.22, 0.03, 0, 0), "FxMotion": (3.4, 5.0, 1.5, 0.2)}),
    "fx_cast_other": (24, {"FxTime": (0, 0.36, 0, 0), "FxColor": (0.45, 0.7, 1.0, 2.2), "FxColorEnd": (0.1, 0.25, 0.6, 1),
                           "FxSize": (0.22, 0.03, 0, 0), "FxMotion": (3.4, 5.0, 1.5, 0.2)}),
}
BOLT_TRAIL = {"mesh": "fx_trail28", "texture": "halo", "effect": FX_TRAIL_EFFECT, "transparent": True,
              "params": {"FxTime": (0, 1, 0, 0), "FxColor": (1.0, 0.55, 0.15, 2.4), "FxColorEnd": (0.6, 0.12, 0.02, 1),
                         "FxSize": (0.32, 0.08, 0, 0), "FxTrail": (2.0, 0.2, 4.0, 30.0)}}

SMOOTH_ANGLE = math.radians(55)
CHARACTER_AO = (0.55, -0.5, 0.75, 0.0)
GLOW = (1.0, 0.3, 0.0, 0.0)
BOLT_GLOW = (0.8, 0.45, 0.0, 0.0)
ENEMY_SCALE = 1.15
PROJECTILE_HALOS = [((0.0, 0.0, 0.0), 0.6)]
HALO_COLORS = {
    "self": (0.25, 1.0, 0.45, 0.8), "other": (0.3, 0.6, 1.0, 0.8), "purple": (0.75, 0.4, 1.0, 0.8),
    "amber": (1.0, 0.7, 0.25, 0.8), "enemy": (1.0, 0.7, 0.2, 0.8),
    "projectile": (1.0, 0.45, 0.12, 0.9), "spitter": (0.6, 1.0, 0.2, 0.8), "brute": (1.0, 0.3, 0.1, 0.9),
    "spit": (0.55, 1.0, 0.15, 0.9), "warlord": (1.0, 0.3, 0.08, 1.0), "bossshot": (0.65, 0.2, 1.0, 0.95),
    "shaman": (0.35, 1.0, 0.8, 0.9), "hound": (1.0, 0.55, 0.15, 0.9), "bloater": (0.6, 1.0, 0.25, 0.8),
    "shieldbearer": (1.0, 0.8, 0.3, 0.9),
}

PALETTE_CELLS = 8
PALETTE_PX = 8
(SKIN, CLOTH, CLOTH_DARK, TRIM, WOOD, ORB, BODY, BODY_DARK, HORN, EYE, BOLT, BOLT_CORE,
 HAIR, EYE_DARK, BELLY, METAL, BODY_BACK, IRON, EMBER, PLANK, PLANK_DARK, STONE) = range(22)
# The spitter and the brute reuse the imp's mesh and baked clips with their own colours.
ENEMY_PALETTES = {
    "spitter": {BODY: (132, 158, 54), BODY_BACK: (86, 108, 34), BODY_DARK: (58, 74, 26), BELLY: (206, 196, 110),
                HORN: (220, 226, 170), EYE: (190, 255, 70), BOLT: (120, 230, 40), BOLT_CORE: (225, 255, 170)},
    "brute": {BODY: (86, 70, 92), BODY_BACK: (56, 44, 62), BODY_DARK: (40, 32, 46), BELLY: (132, 108, 116),
              HORN: (214, 200, 176), EYE: (255, 110, 40)},
    "warlord": {BODY: (58, 40, 42), BODY_BACK: (34, 22, 24), BODY_DARK: (22, 14, 16), BELLY: (120, 42, 30),
                HORN: (236, 192, 78), EYE: (255, 70, 30), BOLT: (170, 50, 255), BOLT_CORE: (240, 190, 255)},
}
# The shaman has its own mesh: ashen skin, a rust shawl, and the teal glow of its mending.
SHAMAN_PALETTE = {BODY: (112, 120, 128), BODY_BACK: (74, 80, 90), BODY_DARK: (46, 50, 58), BELLY: (150, 150, 140),
                  HORN: (226, 218, 196), EYE: (90, 255, 210), BOLT: (80, 240, 200), CLOTH: (150, 62, 38),
                  CLOTH_DARK: (90, 40, 30), WOOD: (96, 70, 48), HAIR: (222, 212, 188)}
# The bloater: sickly olive skin over glowing green pustules.
BLOATER_PALETTE = {BODY: (150, 160, 80), BODY_BACK: (110, 118, 58), BODY_DARK: (70, 74, 40), BELLY: (196, 186, 120),
                   EYE: (220, 255, 90), BOLT: (150, 255, 60), HORN: (200, 196, 160)}
# The shieldbearer: tan hide under dark iron and brass.
SHIELD_PALETTE = {BODY: (128, 90, 62), BODY_BACK: (88, 60, 42), BODY_DARK: (58, 40, 30), BELLY: (166, 124, 92),
                  METAL: (120, 122, 132), TRIM: (186, 146, 72), EYE: (255, 200, 60), HORN: (220, 210, 186)}
# The hound: charcoal hide, bone ridge, ember eyes.
HOUND_PALETTE = {BODY: (78, 62, 56), BODY_BACK: (50, 40, 38), BODY_DARK: (32, 27, 27), BELLY: (104, 76, 64),
                 HORN: (214, 200, 172), EYE: (255, 150, 40), EMBER: (255, 120, 30)}
PALETTES = {
    "self": {CLOTH: (46, 160, 87), CLOTH_DARK: (24, 92, 52), ORB: (60, 240, 110)},
    "other": {CLOTH: (52, 110, 205), CLOTH_DARK: (28, 60, 130), ORB: (70, 150, 255)},
    "purple": {CLOTH: (122, 64, 178), CLOTH_DARK: (70, 34, 108), ORB: (190, 120, 255)},
    "amber": {CLOTH: (190, 120, 40), CLOTH_DARK: (110, 64, 22), ORB: (255, 190, 80)},
    "dead": {CLOTH: (90, 90, 96), CLOTH_DARK: (60, 60, 66), ORB: (120, 120, 126), SKIN: (130, 126, 122),
             TRIM: (110, 104, 92), HAIR: (150, 150, 150)},
}
BASE_COLORS = {
    SKIN: (228, 184, 146), CLOTH: (46, 160, 87), CLOTH_DARK: (24, 92, 52), TRIM: (222, 184, 76),
    WOOD: (116, 76, 42), ORB: (140, 255, 170), BODY: (176, 48, 42), BODY_DARK: (104, 26, 28),
    HORN: (232, 218, 186), EYE: (255, 220, 70), BOLT: (255, 110, 24), BOLT_CORE: (255, 232, 170),
    HAIR: (232, 232, 238), EYE_DARK: (34, 26, 22), BELLY: (222, 128, 88), METAL: (186, 186, 196),
    BODY_BACK: (128, 30, 32), IRON: (70, 66, 64), EMBER: (255, 150, 50), PLANK: (150, 104, 60),
    PLANK_DARK: (92, 60, 34), STONE: (96, 92, 88),
}

# How each palette slot looks when the characters are texture-baked: (roughness, metallic, surface detail, detail scale).
# Metals bake as non-metallic: the diffuse bake keeps no colour for metal, and the gloss mask carries their shine.
LOOKS = {
    SKIN: (0.55, 0.0, "noise", 18.0), CLOTH: (0.85, 0.0, "noise", 7.0), CLOTH_DARK: (0.85, 0.0, "noise", 7.0),
    TRIM: (0.3, 0.0, "noise", 14.0), WOOD: (0.6, 0.0, "grain", 4.0), ORB: (0.1, 0.0, "none", 1.0),
    BODY: (0.5, 0.0, "scales", 16.0), BODY_DARK: (0.55, 0.0, "scales", 16.0), BODY_BACK: (0.5, 0.0, "scales", 14.0),
    HORN: (0.35, 0.0, "ridges", 8.0), EYE: (0.1, 0.0, "none", 1.0), BOLT: (0.2, 0.0, "none", 1.0),
    BOLT_CORE: (0.2, 0.0, "none", 1.0), HAIR: (0.7, 0.0, "noise", 12.0), EYE_DARK: (0.15, 0.0, "none", 1.0),
    BELLY: (0.6, 0.0, "noise", 14.0), METAL: (0.35, 0.0, "noise", 14.0),
}
CHARACTER_SURFACE = (0.5, 0.55, 24.0, 0.6)


def variant_colors(overrides):
    colors = dict(BASE_COLORS)
    colors.update(overrides)
    return colors


def to_engine(v):
    # Blender is Z-up; the engine is Y-up with the model's front (Blender -Y) facing +Z.
    return (v.x, v.z, -v.y)


def palette_uv(index):
    cx, cy = index % PALETTE_CELLS, index // PALETTE_CELLS
    return ((cx + 0.5) / PALETTE_CELLS, (cy + 0.5) / PALETTE_CELLS)


class Model:
    def __init__(self, scale=1.0):
        self.layers = {"base": bmesh.new(), "glow": bmesh.new()}
        self.scale = scale
        self.bones, self.halos = [], []

    def bone(self, name, head, tail, parent=None):
        self.bones.append((name, head, tail, parent))

    def bone_index(self, name):
        return [b[0] for b in self.bones].index(name)

    def halo(self, center, size, bone, name=None):
        self.halos.append((Vector(center), size, bone, name))

    def scale_matrix(self):
        # Grow about the feet so the model still stands on the floor.
        return at(0, 0, -0.5) @ Matrix.Scale(self.scale, 4) @ at(0, 0, 0.5)

    def add(self, geom_fn, color, matrix=Matrix(), smooth=True, glow=False, bone=None):
        part = bmesh.new()
        geom_fn(part)
        part.transform(matrix)
        part.normal_update()
        for face in part.faces:
            face.material_index = color(face) if callable(color) else color
            face.smooth = smooth
        if bone is not None:
            weigh = rigid(bone) if isinstance(bone, str) else bone
            deform = part.verts.layers.deform.verify()
            for v in part.verts:
                for name, w in weigh(v.co).items():
                    v[deform][self.bone_index(name)] = w
        mesh = bpy.data.meshes.new("part")
        part.to_mesh(mesh)
        part.free()
        self.layers["glow" if glow else "base"].from_mesh(mesh)
        bpy.data.meshes.remove(mesh)

    def mirrored(self, geom_fn, color, matrix=Matrix(), bone=None, **kw):
        self.add(geom_fn, color, matrix, bone=bone, **kw)
        if isinstance(bone, str):
            bone = mirror_name(bone)
        elif bone is not None:
            weigh = bone
            bone = lambda co: {mirror_name(n): w for n, w in weigh(Vector((-co.x, co.y, co.z))).items()}
        self.add(lambda bm: (geom_fn(bm), bmesh.ops.reverse_faces(bm, faces=bm.faces[:])), color,
                 Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)) @ matrix, bone=bone, **kw)

    def export(self, path, name, uv_fn=None, layer="base"):
        positions, normals, uvs, indices = self.mesh_data(uv_fn, layer)
        cmf.write_mesh(path, positions, normals, uvs, indices, name=name)
        return len(indices) // 3

    def mesh_data(self, uv_fn=None, layer="base"):
        """Triangle-list positions, normals, uvs and indices in engine coordinates."""
        bm = self.layers[layer].copy()
        if self.scale != 1.0:
            bm.transform(self.scale_matrix())
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.normal_update()
        limit = math.cos(SMOOTH_ANGLE)
        positions, normals, uvs, indices = [], [], [], []
        for face in bm.faces:
            fn = face.normal
            for loop in face.loops:
                n = fn
                if face.smooth:
                    acc = Vector()
                    for other in loop.vert.link_faces:
                        if other.smooth and other.normal.dot(fn) > limit:
                            acc += other.normal * other.calc_area()
                    if acc.length > 0:
                        n = acc.normalized()
                indices.append(len(positions))
                positions.append(to_engine(loop.vert.co))
                normals.append(to_engine(n))
                u, v = uv_fn(loop.vert.co, fn) if uv_fn else palette_uv(face.material_index)
                # Blender images are stored bottom-up; Direct3D's v=0 is the top row.
                uvs.append((u, 1.0 - v))
        bm.free()
        return positions, normals, uvs, indices


def cone(r1, r2, depth, segments=16):
    return lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r1, radius2=r2, depth=depth)


def ico(radius, subdivisions=2):
    return lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius)


def sphere(radius, u=16, v=10):
    return lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)


def box(sx, sy, sz, bevel=0.0, segments=2):
    def build(bm):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts[:])
        if bevel:
            bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=segments, affect="EDGES", profile=0.5)
    return build


def tube(points, radii, segments=12):
    """Swept circle through points; a zero radius closes that end to a point."""
    def build(bm):
        pts = [Vector(p) for p in points]
        rings, normal = [], None
        for i, p in enumerate(pts):
            t = Vector()
            for span in range(1, len(pts)):
                t = pts[min(i + span, len(pts) - 1)] - pts[max(i - span, 0)]
                if t.length > 1e-6:
                    break
            t.normalize()
            if normal is None:
                ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                normal = t.cross(ref).normalized()
            else:
                normal = (normal - t * normal.dot(t)).normalized()
            binormal = t.cross(normal)
            if radii[i] <= 1e-6:
                rings.append([bm.verts.new(p)])
                continue
            rings.append([bm.verts.new(p + (normal * math.cos(a) + binormal * math.sin(a)) * radii[i])
                          for a in (2 * math.pi * k / segments for k in range(segments))])
        for a, b in zip(rings, rings[1:]):
            for k in range(segments):
                k2 = (k + 1) % segments
                quad = [a[k % len(a)], a[k2 % len(a)], b[k2 % len(b)], b[k % len(b)]]
                unique = list(dict.fromkeys(quad))
                if len(unique) >= 3:
                    bm.faces.new(unique)
        for ring in (rings[0], rings[-1]):
            if len(ring) > 1:
                bm.faces.new(ring)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return build


def lathe(profile, segments=20):
    return tube([(0, 0, z) for _, z in profile], [r for r, _ in profile], segments)


def folded(geom_fn, folds, depth, z_hem, z_top, phase=0.0):
    """Cloth folds: pushes a lathed part in and out around its axis, fully at z_hem and fading out by z_top."""
    def build(bm):
        geom_fn(bm)
        for v in bm.verts:
            w = max(0.0, min(1.0, (z_top - v.co.z) / (z_top - z_hem)))
            r = math.hypot(v.co.x, v.co.y)
            if r > 1e-4 and w > 0.0:
                a = math.atan2(v.co.y, v.co.x)
                k = 1.0 + depth * w * w * math.sin(folds * a + phase + 1.7 * math.sin(3 * a)) / max(r, 0.15)
                v.co.x, v.co.y = v.co.x * k, v.co.y * k
    return build


def skin_mesh(joints, bones, levels=1):
    """An organic part from a skeleton: joints are name -> (position, radius), bones join them, and Blender's skin
    modifier wraps them in one seamless surface (smoothed by `levels` of subdivision)."""
    def build(bm):
        names = list(joints)
        me = bpy.data.meshes.new("skin")
        me.from_pydata([joints[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in bones], [])
        ob = bpy.data.objects.new("skin", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.modifiers.new("skin", "SKIN")
        for i, n in enumerate(names):
            me.skin_vertices[0].data[i].radius = (joints[n][1], joints[n][1])
        me.skin_vertices[0].data[0].use_root = True
        if levels:
            ob.modifiers.new("smooth", "SUBSURF").levels = levels
        evaluated = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        bm.from_mesh(evaluated.to_mesh())
        evaluated.to_mesh_clear()
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    return build


def at(x, y, z, sx=1.0, sy=1.0, sz=1.0, rx=0.0, ry=0.0, rz=0.0):
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y")
            @ Matrix.Rotation(rx, 4, "X") @ Matrix.Diagonal((sx, sy, sz, 1.0)))


def vertical(low, high, z0, z1):
    def weights(co):
        u = max(0.0, min(1.0, (co.z - z0) / (z1 - z0)))
        u = u * u * (3 - 2 * u)
        return {low: 1.0 - u, high: u} if 0.0 < u < 1.0 else {high if u >= 1.0 else low: 1.0}
    return weights


def build_player():
    m = Model()
    f = -0.5
    shoulder_s, elbow_s, wrist_s = (0.2, 0.0, f + 0.94), (0.31, -0.04, f + 0.76), (0.37, -0.18, f + 0.64)
    shoulder_f, elbow_f, wrist_f = (-0.2, 0.0, f + 0.94), (-0.33, -0.1, f + 0.8), (-0.36, -0.27, f + 0.78)
    m.bone("root", (0, 0, f), (0, 0, f + 0.25))
    m.bone("hem", (0, 0, f + 0.55), (0, 0, f + 0.1), "root")
    m.bone("spine", (0, 0, f + 0.5), (0, 0, f + 0.95), "root")
    m.bone("head", (0, 0, f + 1.0), (0, 0, f + 1.3), "spine")
    m.bone("arm_s", shoulder_s, elbow_s, "spine")
    m.bone("forearm_s", elbow_s, wrist_s, "arm_s")
    m.bone("arm_f", shoulder_f, elbow_f, "spine")
    m.bone("forearm_f", elbow_f, wrist_f, "arm_f")
    body = vertical("hem", "spine", f + 0.3, f + 0.62)
    arm_s = chain(("arm_s", shoulder_s, elbow_s), ("forearm_s", elbow_s, wrist_s))
    arm_f = chain(("arm_f", shoulder_f, elbow_f), ("forearm_f", elbow_f, wrist_f))

    robe = lathe([(0.0, f), (0.44, f), (0.46, f + 0.05), (0.41, f + 0.3), (0.32, f + 0.56), (0.27, f + 0.76),
                  (0.28, f + 0.88), (0.18, f + 0.98), (0.08, f + 1.02), (0.0, f + 1.03)], 40)
    m.add(folded(robe, 9, 0.035, f, f + 0.62),
          lambda face: CLOTH_DARK if face.normal.y < -0.6 and abs(face.calc_center_median().x) < 0.04 else CLOTH,
          bone=body)
    m.add(folded(lathe([(0.0, f + 0.005), (0.465, f + 0.005), (0.47, f + 0.075), (0.0, f + 0.075)], 40), 9, 0.035,
                 f - 0.1, f + 0.62), TRIM, bone="hem")
    m.add(lathe([(0.0, f + 0.6), (0.315, f + 0.6), (0.32, f + 0.68), (0.0, f + 0.68)], 32), CLOTH_DARK, bone=body)
    m.add(box(0.11, 0.035, 0.11, 0.014), TRIM, at(0, -0.315, f + 0.64), smooth=False, bone=body)
    m.add(box(0.06, 0.06, 0.12, 0.012), WOOD, at(0.22, -0.2, f + 0.56, rz=0.6), bone=body)
    # A shoulder mantle with a few soft folds, over the robe.
    m.add(folded(lathe([(0.0, f + 1.0), (0.17, f + 1.0), (0.33, f + 0.9), (0.37, f + 0.79), (0.34, f + 0.75),
                        (0.0, f + 0.75)], 32), 7, 0.025, f + 0.74, f + 0.95, 0.5), CLOTH_DARK,
          at(0, 0.035, 0, 1.0, 0.86, 1.0), bone="spine")
    m.add(sphere(0.19, 20, 14), SKIN, at(0, -0.02, f + 1.14), bone="head")
    m.add(tube([(0, -0.15, f + 1.12), (0, -0.27, f + 1.03), (0, -0.33, f + 0.9), (0, -0.33, f + 0.76), (0, -0.29, f + 0.64)],
               [0.12, 0.15, 0.13, 0.08, 0.0], 14), HAIR, at(0, 0, 0, 1.2, 0.62, 1.0), bone="head")
    m.add(sphere(0.07, 12, 8), HAIR, at(0, -0.2, f + 1.12, 1.9, 0.6, 0.45), bone="head")
    m.mirrored(sphere(0.045, 10, 6), HAIR, at(0.08, -0.17, f + 1.235, 1.6, 0.8, 0.55, ry=0.25), bone="head")
    m.mirrored(sphere(0.026, 8, 6), EYE_DARK, at(0.075, -0.19, f + 1.19), bone="head")
    m.add(sphere(0.04, 10, 6), SKIN, at(0, -0.225, f + 1.15, 1.0, 1.2, 1.0), bone="head")
    # The hat: a wide, slightly drooping brim and a tall crooked crown with a band and buckle.
    m.add(lathe([(0.0, f + 1.215), (0.3, f + 1.215), (0.45, f + 1.185), (0.46, f + 1.2), (0.32, f + 1.25),
                 (0.0, f + 1.26)], 36), CLOTH_DARK, bone="head")
    m.add(tube([(0, 0, f + 1.24), (0, 0.01, f + 1.44), (0, 0.07, f + 1.62), (0, 0.19, f + 1.76), (0, 0.34, f + 1.78)],
               [0.25, 0.185, 0.115, 0.05, 0.0], 24), CLOTH_DARK, bone="head")
    m.add(lathe([(0.0, f + 1.255), (0.253, f + 1.255), (0.24, f + 1.33), (0.0, f + 1.33)], 32), TRIM, bone="head")
    m.add(box(0.09, 0.03, 0.08, 0.01), METAL, at(0, -0.245, f + 1.29), smooth=False, bone="head")
    # Sleeves that flare at the cuff, and hands, as skinned arms.
    for shoulder, elbow, wrist, side, weigh in ((shoulder_s, elbow_s, wrist_s, "s", arm_s),
                                                (shoulder_f, elbow_f, wrist_f, "f", arm_f)):
        sh, el, wr = Vector(shoulder), Vector(elbow), Vector(wrist)
        cuff = wr + (wr - el).normalized() * 0.03
        m.add(skin_mesh({"shoulder": (sh, 0.1), "upper": (sh.lerp(el, 0.5), 0.098), "elbow": (el, 0.1),
                         "fore": (el.lerp(wr, 0.6), 0.115), "cuff": (cuff, 0.15)},
                        [("shoulder", "upper"), ("upper", "elbow"), ("elbow", "fore"), ("fore", "cuff")]), CLOTH, bone=weigh)
        hand = cuff + (wr - el).normalized() * 0.06
        m.add(skin_mesh({"palm": (cuff, 0.05), "hand": (hand, 0.058), "tip": (hand + Vector((0, -0.03, -0.035)), 0.04),
                         "thumb": (hand + Vector((0.035 if side == "s" else -0.035, -0.04, 0.02)), 0.025)},
                        [("palm", "hand"), ("hand", "tip"), ("hand", "thumb")]), SKIN, bone="forearm_" + side)
    m.add(tube([(0.345, -0.13, f + 0.66), (0.37, -0.19, f + 0.63)], [0.15, 0.15], 20), TRIM, bone="forearm_s")
    m.add(tube([(-0.357, -0.23, f + 0.785), (-0.365, -0.29, f + 0.78)], [0.15, 0.15], 20), TRIM, bone="forearm_f")
    # A gnarled staff, its head a wooden claw around the orb.
    staff = [(0.39, -0.2, f + 0.02), (0.405, -0.19, f + 0.35), (0.392, -0.21, f + 0.7), (0.408, -0.2, f + 1.05),
             (0.395, -0.205, f + 1.35), (0.4, -0.2, f + 1.5)]
    m.add(tube(staff, [0.026, 0.032, 0.03, 0.033, 0.035, 0.042], 10), WOOD, bone="forearm_s")
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        dx, dy = math.cos(a), math.sin(a)
        m.add(tube([(0.4, -0.2, f + 1.48), (0.4 + dx * 0.1, -0.2 + dy * 0.1, f + 1.58),
                    (0.4 + dx * 0.075, -0.2 + dy * 0.075, f + 1.7), (0.4 + dx * 0.03, -0.2 + dy * 0.03, f + 1.76)],
                   [0.024, 0.02, 0.014, 0.0], 8), WOOD, bone="forearm_s")
    m.add(ico(0.085), ORB, at(0.4, -0.2, f + 1.62), glow=True, bone="forearm_s")
    m.halo((0.4, -0.2, f + 1.62), 0.34, "forearm_s", "orb")
    return m


def imp_bones(m, f, spine, arm, leg, tail_pts, head):
    """The imp skeleton's bones (the names its clips drive), placed for one body; returns the torso's weighting."""
    hip, waist, neck = spine
    shoulder, elbow, wrist = arm
    hip_j, knee, ankle, toe = leg
    m.bone("root", (0, 0, f), (0, 0, f + 0.2))
    m.bone("pelvis", hip, waist, "root")
    m.bone("chest", waist, neck, "pelvis")
    m.bone("head", head[0], head[1], "chest")
    for side, sx in ((".p", 1.0), (".n", -1.0)):
        mirror = lambda p, sx=sx: (p[0] * sx, p[1], p[2])
        m.bone("arm" + side, mirror(shoulder), mirror(elbow), "chest")
        m.bone("forearm" + side, mirror(elbow), mirror(wrist), "arm" + side)
        m.bone("thigh" + side, mirror(hip_j), mirror(knee), "pelvis")
        m.bone("shin" + side, mirror(knee), mirror(ankle), "thigh" + side)
        m.bone("foot" + side, mirror(ankle), mirror(toe), "shin" + side)
    m.bone("tail1", tail_pts[0], tail_pts[1], "pelvis")
    m.bone("tail2", tail_pts[1], tail_pts[2], "tail1")
    m.bone("tail3", tail_pts[2], tail_pts[3], "tail2")
    return chain(("pelvis", hip, waist), ("chest", waist, neck))


def imp_limbs(joints, links, f, shoulder, elbow, wrist, hand, hip_j, knee, ankle, toe, sizes):
    """Adds both arms and legs to a skin skeleton; sizes are the shoulder, elbow, wrist, hand, hip, knee, ankle and toe radii."""
    for side, sx in ((".p", 1.0), (".n", -1.0)):
        mx = lambda p, sx=sx: (p[0] * sx, p[1], p[2])
        points = (shoulder, elbow, wrist, hand, hip_j, knee, ankle, toe)
        names = ("shoulder", "elbow", "wrist", "hand", "hip", "knee", "ankle", "toe")
        joints.update({n + side: (mx(p), r) for n, p, r in zip(names, points, sizes)})
        links += [("chest", "shoulder" + side), ("shoulder" + side, "elbow" + side), ("elbow" + side, "wrist" + side),
                  ("wrist" + side, "hand" + side), ("pelvis", "hip" + side), ("hip" + side, "knee" + side),
                  ("knee" + side, "ankle" + side), ("ankle" + side, "toe" + side)]


def build_enemy():
    m = Model(ENEMY_SCALE)
    f = -0.5
    hip, waist, neck = (0, 0.1, f + 0.36), (0, 0.02, f + 0.56), (0, -0.1, f + 0.86)
    shoulder, elbow, wrist = (0.3, -0.08, f + 0.76), (0.42, -0.04, f + 0.54), (0.41, -0.26, f + 0.42)
    hip_j, knee, ankle, toe = (0.17, 0.08, f + 0.36), (0.24, -0.08, f + 0.22), (0.24, 0.08, f + 0.08), (0.24, -0.1, f + 0.02)
    tail_pts = [(0, 0.14, f + 0.34), (0, 0.4, f + 0.26), (0.02, 0.62, f + 0.28), (0.12, 0.9, f + 0.44)]
    torso = imp_bones(m, f, (hip, waist, neck), (shoulder, elbow, wrist), (hip_j, knee, ankle, toe), tail_pts,
                      ((0, -0.12, f + 0.88), (0, -0.4, f + 0.95)))
    # The body is one skinned skeleton (torso, head, limbs, tail), weighted to the nearest bones.
    joints = {"pelvis": ((0, 0.08, f + 0.37), 0.17), "belly": ((0, 0.02, f + 0.52), 0.235),
              "chest": ((0, -0.05, f + 0.69), 0.25), "neck": ((0, -0.13, f + 0.84), 0.13),
              "head": ((0, -0.25, f + 0.94), 0.19), "brow": ((0, -0.36, f + 0.96), 0.13), "snout": ((0, -0.46, f + 0.89), 0.09),
              "nose": ((0, -0.55, f + 0.88), 0.065), "jaw": ((0, -0.36, f + 0.84), 0.1),
              "chin": ((0, -0.46, f + 0.81), 0.065),
              "tail1": ((0, 0.3, f + 0.3), 0.075), "tail2": ((0.02, 0.56, f + 0.3), 0.052), "tail3": ((0.08, 0.8, f + 0.4), 0.032),
              "tail4": ((0.12, 0.9, f + 0.45), 0.014)}
    links = [("pelvis", "belly"), ("belly", "chest"), ("chest", "neck"), ("neck", "head"), ("head", "brow"),
             ("brow", "snout"), ("snout", "nose"), ("head", "jaw"), ("jaw", "chin"), ("pelvis", "tail1"), ("tail1", "tail2"), ("tail2", "tail3"), ("tail3", "tail4")]
    for side, sx in ((".p", 1.0), (".n", -1.0)):
        mx = lambda p, sx=sx: (p[0] * sx, p[1], p[2])
        joints.update({"shoulder" + side: (mx((0.24, -0.06, f + 0.76)), 0.105), "elbow" + side: (mx(elbow), 0.075),
                       "wrist" + side: (mx(wrist), 0.06), "hand" + side: (mx((0.41, -0.31, f + 0.4)), 0.07),
                       "hip" + side: (mx(hip_j), 0.125), "knee" + side: (mx(knee), 0.09), "ankle" + side: (mx(ankle), 0.06),
                       "toe" + side: (mx((0.24, -0.12, f + 0.035)), 0.06)})
        links += [("chest", "shoulder" + side), ("shoulder" + side, "elbow" + side), ("elbow" + side, "wrist" + side),
                  ("wrist" + side, "hand" + side), ("pelvis", "hip" + side), ("hip" + side, "knee" + side),
                  ("knee" + side, "ankle" + side), ("ankle" + side, "toe" + side)]
    everything = chain(*[(n, h, t) for n, h, t, _ in m.bones if n != "root"])

    def hide(face):
        c, n = face.calc_center_median(), face.normal
        if c.z < f + 0.3 or (c.y < -0.55 and c.z > f + 0.84):
            return BODY_DARK
        if n.y < -0.45 and abs(c.x) < 0.17 and f + 0.4 < c.z < f + 0.78:
            return BELLY
        return BODY_BACK if n.z > 0.35 or n.y > 0.5 else BODY

    m.add(skin_mesh(joints, links), hide, bone=everything)
    m.mirrored(tube([(0.045, -0.46, f + 0.84), (0.055, -0.51, f + 0.79), (0.06, -0.53, f + 0.75)], [0.022, 0.016, 0.0], 6),
               HORN, bone="head")
    m.mirrored(sphere(0.042, 10, 6), EYE, at(0.085, -0.42, f + 1.0, 1.0, 0.7, 0.8), glow=True, bone="head")
    # Horns, brows and ear spikes start inside the head: the smoothed skin sits inside the joint radii.
    m.mirrored(tube([(0.03, -0.4, f + 1.0), (0.05, -0.43, f + 1.04), (0.12, -0.4, f + 1.07)], [0.024, 0.02, 0.012], 6),
               BODY_DARK, bone="head")
    m.mirrored(tube([(0.05, -0.27, f + 0.97), (0.12, -0.3, f + 1.04), (0.2, -0.28, f + 1.14), (0.27, -0.2, f + 1.21),
                     (0.29, -0.08, f + 1.2)], [0.075, 0.065, 0.045, 0.025, 0.0], 10), HORN, bone="head")
    m.mirrored(tube([(0.08, -0.24, f + 0.95), (0.17, -0.23, f + 0.96), (0.28, -0.2, f + 1.0), (0.37, -0.14, f + 1.02)],
                    [0.06, 0.05, 0.035, 0.0], 8), BODY_DARK, bone="head")
    for claw in (-1, 0, 1):
        m.mirrored(tube([(0.41 + claw * 0.035, -0.34, f + 0.4), (0.41 + claw * 0.04, -0.41, f + 0.36),
                         (0.41 + claw * 0.045, -0.43, f + 0.3)], [0.018, 0.012, 0.0], 5), HORN, bone="forearm.p")
    tip, prev = Vector(tail_pts[3]), Vector((0.07, 0.8, f + 0.36))
    heading = (tip - prev).normalized()
    m.add(tube([tip - heading * 0.02, tip + heading * 0.06, tip + heading * 0.16], [0.02, 0.075, 0.0], 4), HORN,
          smooth=False, bone="tail3")
    for i in range(4):
        t = i / 3.0
        m.add(tube([(0, 0.2 - t * 0.2, f + 0.62 + t * 0.2), (0, 0.3 - t * 0.2, f + 0.72 + t * 0.2)],
                   [0.045 - 0.01 * t, 0.0], 6), HORN, bone=torso)
    for sx in (1.0, -1.0):
        m.halo((0.085 * sx, -0.45, f + 1.0), 0.11, "head")
    return m


def build_shaman():
    """The imp's skeleton grown thin and hunched, behind a bone mask, with a bone crest, a shawl and a charmed staff."""
    m = Model(ENEMY_SCALE)
    f = -0.5
    hip, waist, neck = (0, 0.1, f + 0.36), (0, 0.04, f + 0.55), (0, -0.14, f + 0.8)
    shoulder, elbow, wrist = (0.26, -0.1, f + 0.72), (0.36, -0.08, f + 0.5), (0.37, -0.28, f + 0.4)
    hip_j, knee, ankle, toe = (0.14, 0.08, f + 0.36), (0.2, -0.08, f + 0.22), (0.2, 0.08, f + 0.08), (0.2, -0.1, f + 0.02)
    tail_pts = [(0, 0.14, f + 0.34), (0, 0.34, f + 0.24), (0.02, 0.5, f + 0.22), (0.08, 0.64, f + 0.28)]
    imp_bones(m, f, (hip, waist, neck), (shoulder, elbow, wrist), (hip_j, knee, ankle, toe), tail_pts,
              ((0, -0.16, f + 0.82), (0, -0.44, f + 0.86)))
    # Thinner than the imp everywhere, with a hump between the shoulders that pushes the head forward and down.
    joints = {"pelvis": ((0, 0.08, f + 0.37), 0.14), "belly": ((0, 0.04, f + 0.52), 0.17),
              "chest": ((0, -0.03, f + 0.66), 0.19), "hump": ((0, 0.07, f + 0.75), 0.15),
              "neck": ((0, -0.17, f + 0.79), 0.1), "head": ((0, -0.29, f + 0.86), 0.15),
              "brow": ((0, -0.38, f + 0.88), 0.11), "jaw": ((0, -0.38, f + 0.78), 0.08),
              "tail1": ((0, 0.28, f + 0.28), 0.06), "tail2": ((0.02, 0.46, f + 0.23), 0.04),
              "tail3": ((0.08, 0.64, f + 0.28), 0.012)}
    links = [("pelvis", "belly"), ("belly", "chest"), ("chest", "hump"), ("chest", "neck"), ("neck", "head"),
             ("head", "brow"), ("head", "jaw"), ("pelvis", "tail1"), ("tail1", "tail2"), ("tail2", "tail3")]
    imp_limbs(joints, links, f, (0.21, -0.07, f + 0.73), elbow, wrist, (0.37, -0.32, f + 0.38), hip_j, knee, ankle,
              (0.2, -0.12, f + 0.035), (0.08, 0.055, 0.045, 0.055, 0.1, 0.07, 0.05, 0.05))
    everything = chain(*[(n, h, t) for n, h, t, _ in m.bones if n != "root"])

    def hide(face):
        c, n = face.calc_center_median(), face.normal
        if c.z < f + 0.3:
            return BODY_DARK
        if n.y < -0.45 and abs(c.x) < 0.14 and f + 0.4 < c.z < f + 0.7:
            return BELLY
        return BODY_BACK if n.z > 0.35 or n.y > 0.5 else BODY

    m.add(skin_mesh(joints, links), hide, bone=everything)
    # A bone mask over the face, its eye holes lit from behind.
    m.add(sphere(0.15, 18, 12), HAIR, at(0, -0.46, f + 0.86, 1.0, 0.42, 1.3), bone="head")
    m.add(tube([(0, -0.52, f + 0.99), (0, -0.53, f + 0.8)], [0.012, 0.012], 6), BODY_DARK, bone="head")
    m.mirrored(sphere(0.034, 10, 6), EYE_DARK, at(0.055, -0.5, f + 0.9, 1.0, 0.7, 1.2), bone="head")
    m.mirrored(sphere(0.022, 8, 6), EYE, at(0.055, -0.52, f + 0.9), glow=True, bone="head")
    # A crest of bone spikes fanned over the skull, alternately tipped with the shawl's colour.
    for k in range(-2, 3):
        a = k * 0.38
        base = (math.sin(a) * 0.05, -0.33, f + 0.95)
        tip = (math.sin(a) * 0.26, -0.2 - 0.04 * abs(k), f + 1.0 + math.cos(a) * 0.3)
        mid = tuple((b + t) / 2 + d for b, t, d in zip(base, tip, (0.0, 0.05, 0.02)))
        m.add(tube([base, mid, tip], [0.026, 0.018, 0.0], 6), HORN if k % 2 == 0 else CLOTH, bone="head")
    # A ragged shawl over the hump and a loincloth.
    m.add(folded(cone(0.27, 0.12, 0.22, 20), 7, 0.03, -0.11, 0.11), CLOTH, at(0, 0.0, f + 0.66, rx=0.3), bone="chest")
    m.add(folded(cone(0.17, 0.15, 0.16, 16), 6, 0.025, -0.08, 0.08), CLOTH_DARK, at(0, 0.06, f + 0.3), bone="pelvis")
    # A staff in the right hand with a skull charm and a glowing stone on top; claws on the left.
    staff = [(0.37, -0.33, f + 0.02), (0.38, -0.32, f + 0.4), (0.365, -0.33, f + 0.8), (0.375, -0.32, f + 1.12)]
    m.add(tube(staff, [0.022, 0.026, 0.024, 0.03], 8), WOOD, bone="forearm.p")
    m.add(sphere(0.06, 12, 8), HAIR, at(0.375, -0.33, f + 1.17, 1.0, 1.1, 0.9), bone="forearm.p")
    m.add(ico(0.045), BOLT, at(0.375, -0.33, f + 1.235), glow=True, bone="forearm.p")
    for claw in (-1, 0, 1):
        m.add(tube([(-0.37 - claw * 0.03, -0.35, f + 0.38), (-0.37 - claw * 0.035, -0.41, f + 0.34),
                    (-0.37 - claw * 0.04, -0.43, f + 0.29)], [0.015, 0.01, 0.0], 5), HORN, bone="forearm.n")
    for sx in (1.0, -1.0):
        m.halo((0.055 * sx, -0.53, f + 0.9), 0.08, "head")
    m.halo((0.375, -0.33, f + 1.235), 0.3, "forearm.p")
    return m


def build_bloater():
    """The imp's skeleton round a swollen gut: stubby limbs, a small head on top, pustules glowing through the skin."""
    m = Model(ENEMY_SCALE)
    f = -0.5
    hip, waist, neck = (0, 0.1, f + 0.36), (0, 0.0, f + 0.6), (0, -0.12, f + 0.88)
    shoulder, elbow, wrist = (0.3, -0.1, f + 0.75), (0.4, -0.12, f + 0.6), (0.38, -0.25, f + 0.52)
    hip_j, knee, ankle, toe = (0.18, 0.06, f + 0.3), (0.22, -0.06, f + 0.18), (0.22, 0.06, f + 0.07), (0.22, -0.1, f + 0.02)
    tail_pts = [(0, 0.3, f + 0.36), (0, 0.42, f + 0.3), (0.02, 0.5, f + 0.3), (0.05, 0.56, f + 0.34)]
    imp_bones(m, f, (hip, waist, neck), (shoulder, elbow, wrist), (hip_j, knee, ankle, toe), tail_pts,
              ((0, -0.14, f + 0.9), (0, -0.36, f + 0.95)))
    joints = {"pelvis": ((0, 0.06, f + 0.38), 0.2), "belly": ((0, -0.06, f + 0.56), 0.36),
              "chest": ((0, -0.02, f + 0.74), 0.28), "neck": ((0, -0.12, f + 0.88), 0.14),
              "head": ((0, -0.2, f + 0.95), 0.14), "brow": ((0, -0.3, f + 0.97), 0.09), "jaw": ((0, -0.3, f + 0.88), 0.08),
              "tail1": ((0, 0.3, f + 0.36), 0.05), "tail2": ((0, 0.46, f + 0.32), 0.02)}
    links = [("pelvis", "belly"), ("belly", "chest"), ("chest", "neck"), ("neck", "head"), ("head", "brow"),
             ("head", "jaw"), ("pelvis", "tail1"), ("tail1", "tail2")]
    imp_limbs(joints, links, f, (0.28, -0.08, f + 0.76), elbow, wrist, (0.38, -0.29, f + 0.49), hip_j, knee, ankle,
              (0.22, -0.12, f + 0.035), (0.07, 0.045, 0.04, 0.05, 0.11, 0.07, 0.05, 0.055))
    everything = chain(*[(n, h, t) for n, h, t, _ in m.bones if n != "root"])

    def hide(face):
        c, n = face.calc_center_median(), face.normal
        if c.z < f + 0.24:
            return BODY_DARK
        if n.y < -0.3 and abs(c.x) < 0.26 and f + 0.32 < c.z < f + 0.82:
            return BELLY
        return BODY_BACK if n.z > 0.4 or n.y > 0.5 else BODY

    m.add(skin_mesh(joints, links), hide, bone=everything)
    m.mirrored(sphere(0.03, 10, 6), EYE, at(0.06, -0.33, f + 1.0, 1.0, 0.7, 0.8), glow=True, bone="head")
    m.add(tube([(-0.06, -0.37, f + 0.9), (0.0, -0.385, f + 0.885), (0.06, -0.37, f + 0.9)], [0.012, 0.014, 0.012], 6),
          EYE_DARK, bone="head")
    rng = random.Random(4)
    belly = chain(("pelvis", hip, waist), ("chest", waist, neck))
    for _ in range(16):
        a, z = rng.uniform(-2.2, 2.2), rng.uniform(f + 0.38, f + 0.8)
        r = 0.36 * math.sqrt(max(0.0, 1.0 - ((z - (f + 0.56)) / 0.4) ** 2)) + 0.005
        x, y = r * math.sin(a), -0.06 - r * math.cos(a)
        m.add(sphere(rng.uniform(0.025, 0.05), 8, 6), BOLT, at(x, y, z), glow=True, bone=belly)
    for sx in (1.0, -1.0):
        m.halo((0.06 * sx, -0.35, f + 1.0), 0.06, "head")
    m.halo((0.0, -0.4, f + 0.56), 0.5, "pelvis")
    return m


def build_shieldbearer():
    """The imp's skeleton built heavy, helmeted, with a slab shield on its left arm and a mace in its right."""
    m = Model(ENEMY_SCALE)
    f = -0.5
    hip, waist, neck = (0, 0.1, f + 0.38), (0, 0.02, f + 0.6), (0, -0.08, f + 0.92)
    shoulder, elbow, wrist = (0.34, -0.08, f + 0.8), (0.45, -0.06, f + 0.56), (0.42, -0.28, f + 0.44)
    hip_j, knee, ankle, toe = (0.19, 0.08, f + 0.38), (0.26, -0.08, f + 0.22), (0.26, 0.08, f + 0.08), (0.26, -0.12, f + 0.02)
    tail_pts = [(0, 0.14, f + 0.36), (0, 0.38, f + 0.26), (0.02, 0.56, f + 0.26), (0.08, 0.7, f + 0.32)]
    imp_bones(m, f, (hip, waist, neck), (shoulder, elbow, wrist), (hip_j, knee, ankle, toe), tail_pts,
              ((0, -0.1, f + 0.94), (0, -0.36, f + 1.0)))
    joints = {"pelvis": ((0, 0.08, f + 0.4), 0.2), "belly": ((0, 0.02, f + 0.56), 0.26),
              "chest": ((0, -0.04, f + 0.74), 0.3), "neck": ((0, -0.1, f + 0.9), 0.16),
              "head": ((0, -0.2, f + 0.99), 0.17), "brow": ((0, -0.3, f + 1.0), 0.12), "jaw": ((0, -0.3, f + 0.9), 0.11),
              "tail1": ((0, 0.3, f + 0.3), 0.07), "tail2": ((0.02, 0.5, f + 0.26), 0.045), "tail3": ((0.08, 0.7, f + 0.32), 0.012)}
    links = [("pelvis", "belly"), ("belly", "chest"), ("chest", "neck"), ("neck", "head"), ("head", "brow"),
             ("head", "jaw"), ("pelvis", "tail1"), ("tail1", "tail2"), ("tail2", "tail3")]
    imp_limbs(joints, links, f, (0.28, -0.06, f + 0.8), elbow, wrist, (0.42, -0.32, f + 0.42), hip_j, knee, ankle,
              (0.26, -0.14, f + 0.035), (0.13, 0.095, 0.075, 0.08, 0.14, 0.1, 0.07, 0.07))
    everything = chain(*[(n, h, t) for n, h, t, _ in m.bones if n != "root"])

    def hide(face):
        c, n = face.calc_center_median(), face.normal
        if c.z < f + 0.3:
            return BODY_DARK
        if n.y < -0.45 and abs(c.x) < 0.2 and f + 0.42 < c.z < f + 0.82:
            return BELLY
        return BODY_BACK if n.z > 0.35 or n.y > 0.5 else BODY

    m.add(skin_mesh(joints, links), hide, bone=everything)
    # A domed iron helmet with a lit visor slit and two horns through it; pauldrons over the shoulders.
    m.add(sphere(0.2, 18, 12), METAL, at(0, -0.22, f + 1.02, 1.0, 1.1, 0.9), bone="head")
    m.add(box(0.2, 0.05, 0.03, 0.01), EYE, at(0, -0.43, f + 1.0), glow=True, bone="head")
    m.mirrored(tube([(0.12, -0.24, f + 1.1), (0.22, -0.26, f + 1.2), (0.26, -0.18, f + 1.3)], [0.045, 0.03, 0.0], 8),
               HORN, bone="head")
    m.mirrored(sphere(0.15, 14, 10), METAL, at(0.32, -0.06, f + 0.84, 1.0, 1.0, 0.65), bone="arm.p")
    # The shield: an iron slab with a brass rim and boss, held across the body on the left forearm.
    shield = at(-0.3, -0.5, f + 0.55, rz=0.25)
    m.add(box(0.62, 0.06, 0.8, 0.02), METAL, shield, smooth=False, bone="forearm.n")
    m.add(box(0.68, 0.04, 0.86, 0.02), TRIM, shield @ at(0, 0.03, 0), smooth=False, bone="forearm.n")
    m.add(sphere(0.08, 12, 8), TRIM, shield @ at(0, -0.04, 0.05, 1.0, 0.5, 1.0), bone="forearm.n")
    # A mace in the right hand: haft and a flanged iron head.
    m.add(tube([(0.42, -0.36, f + 0.3), (0.42, -0.36, f + 0.86)], [0.025, 0.028], 8), WOOD, bone="forearm.p")
    m.add(ico(0.08, 1), METAL, at(0.42, -0.36, f + 0.9, 1.0, 1.0, 1.2), smooth=False, bone="forearm.p")
    for sx in (1.0, -1.0):
        m.halo((0.05 * sx, -0.45, f + 1.0), 0.07, "head")
    return m


def build_hound():
    """A four-legged skeleton: a lean, deep-chested hound with a ridge of bone down its back and embers in its hide."""
    m = Model(ENEMY_SCALE)
    f = -0.5
    m.bone("root", (0, 0, f), (0, 0, f + 0.2))
    m.bone("pelvis", (0, 0.3, f + 0.52), (0, 0.0, f + 0.55), "root")
    m.bone("chest", (0, 0.0, f + 0.55), (0, -0.32, f + 0.6), "pelvis")
    m.bone("neck", (0, -0.32, f + 0.62), (0, -0.48, f + 0.75), "chest")
    m.bone("head", (0, -0.48, f + 0.75), (0, -0.74, f + 0.71), "neck")
    m.bone("jaw", (0, -0.52, f + 0.68), (0, -0.74, f + 0.63), "head")
    for side, sx in ((".p", 1.0), (".n", -1.0)):
        mx = lambda p, sx=sx: (p[0] * sx, p[1], p[2])
        m.bone("upper" + side, mx((0.13, -0.26, f + 0.5)), mx((0.15, -0.3, f + 0.27)), "chest")
        m.bone("lower" + side, mx((0.15, -0.3, f + 0.27)), mx((0.15, -0.28, f + 0.07)), "upper" + side)
        m.bone("paw" + side, mx((0.15, -0.28, f + 0.07)), mx((0.15, -0.37, f + 0.03)), "lower" + side)
        m.bone("thigh" + side, mx((0.13, 0.28, f + 0.48)), mx((0.16, 0.2, f + 0.28)), "pelvis")
        m.bone("shin" + side, mx((0.16, 0.2, f + 0.28)), mx((0.15, 0.34, f + 0.13)), "thigh" + side)
        m.bone("foot" + side, mx((0.15, 0.34, f + 0.13)), mx((0.15, 0.27, f + 0.03)), "shin" + side)
    m.bone("tail1", (0, 0.36, f + 0.56), (0, 0.58, f + 0.57), "pelvis")
    m.bone("tail2", (0, 0.58, f + 0.57), (0, 0.78, f + 0.48), "tail1")
    joints = {"rump": ((0, 0.28, f + 0.52), 0.14), "belly": ((0, 0.06, f + 0.5), 0.13),
              "chest": ((0, -0.2, f + 0.52), 0.18), "withers": ((0, -0.26, f + 0.64), 0.12),
              "neck": ((0, -0.42, f + 0.7), 0.1), "head": ((0, -0.55, f + 0.76), 0.115),
              "snout": ((0, -0.7, f + 0.72), 0.065), "nose": ((0, -0.79, f + 0.7), 0.045),
              "jaw": ((0, -0.6, f + 0.67), 0.07), "chin": ((0, -0.73, f + 0.65), 0.04),
              "t1": ((0, 0.42, f + 0.56), 0.045), "t2": ((0, 0.6, f + 0.56), 0.03), "t3": ((0, 0.8, f + 0.47), 0.008)}
    links = [("rump", "belly"), ("belly", "chest"), ("chest", "withers"), ("withers", "neck"), ("chest", "neck"),
             ("neck", "head"), ("head", "snout"), ("snout", "nose"), ("head", "jaw"), ("jaw", "chin"),
             ("rump", "t1"), ("t1", "t2"), ("t2", "t3")]
    for side, sx in ((".p", 1.0), (".n", -1.0)):
        mx = lambda p, sx=sx: (p[0] * sx, p[1], p[2])
        joints.update({"shoulder" + side: (mx((0.12, -0.25, f + 0.48)), 0.085),
                       "elbow" + side: (mx((0.15, -0.3, f + 0.27)), 0.05), "wrist" + side: (mx((0.15, -0.28, f + 0.07)), 0.038),
                       "fpaw" + side: (mx((0.15, -0.35, f + 0.035)), 0.042),
                       "hip" + side: (mx((0.12, 0.27, f + 0.46)), 0.1), "stifle" + side: (mx((0.16, 0.2, f + 0.28)), 0.065),
                       "hock" + side: (mx((0.15, 0.34, f + 0.13)), 0.04), "hpaw" + side: (mx((0.15, 0.27, f + 0.035)), 0.042)})
        links += [("chest", "shoulder" + side), ("shoulder" + side, "elbow" + side), ("elbow" + side, "wrist" + side),
                  ("wrist" + side, "fpaw" + side), ("rump", "hip" + side), ("hip" + side, "stifle" + side),
                  ("stifle" + side, "hock" + side), ("hock" + side, "hpaw" + side)]
    everything = chain(*[(n, h, t) for n, h, t, _ in m.bones if n != "root"])

    def hide(face):
        c, n = face.calc_center_median(), face.normal
        if c.z < f + 0.22:
            return BODY_DARK
        if n.z < -0.5 and c.z < f + 0.5:
            return BELLY
        return BODY_BACK if n.z > 0.45 else BODY

    m.add(skin_mesh(joints, links), hide, bone=everything)
    m.mirrored(sphere(0.03, 10, 6), EYE, at(0.06, -0.63, f + 0.8, 1.0, 0.8, 0.7), glow=True, bone="head")
    m.mirrored(tube([(0.05, -0.53, f + 0.79), (0.08, -0.48, f + 0.87), (0.095, -0.41, f + 0.9)], [0.035, 0.022, 0.0], 6),
               HORN, bone="head")
    # Bone spikes down the spine, tallest at the withers.
    for k in range(7):
        u = k / 6.0
        y, z = -0.3 + 0.62 * u, f + 0.72 - 0.12 * u + 0.04 * math.sin(math.pi * u)
        h = 0.16 - 0.1 * u
        bone_name = "chest" if y < 0.0 else "pelvis"
        m.add(tube([(0, y, z - 0.06), (0, y + 0.04, z + h * 0.6), (0, y + 0.1, z + h)], [0.03 - 0.012 * u, 0.018, 0.0], 6),
              HORN, bone=bone_name)
    # Fangs under the snout, and embers smouldering in the hide.
    m.mirrored(tube([(0.035, -0.74, f + 0.68), (0.038, -0.75, f + 0.62)], [0.012, 0.0], 5), HORN, bone="head")
    rng = random.Random(9)
    for _ in range(9):
        y = rng.uniform(-0.25, 0.3)
        a = rng.uniform(0.5, 1.3)
        x, z = 0.14 * math.cos(a), f + 0.52 + 0.13 * math.sin(a)
        m.mirrored(sphere(0.018, 6, 4), EMBER, at(x, y, z), glow=True, bone="chest" if y < 0.0 else "pelvis")
    for sx in (1.0, -1.0):
        m.halo((0.06 * sx, -0.65, f + 0.8), 0.07, "head")
    return m


def build_loot():
    m = Model()
    f = -0.5
    m.add(ico(0.15), ORB, at(0, 0, f + 0.55), glow=True)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        dx, dy = math.cos(a), math.sin(a)
        m.add(tube([(0, 0, f + 0.3), (dx * 0.19, dy * 0.19, f + 0.45), (dx * 0.19, dy * 0.19, f + 0.65), (0, 0, f + 0.8)],
                   [0.018, 0.016, 0.016, 0.018], 6), IRON)
    m.add(lathe([(0.0, f + 0.27), (0.07, f + 0.27), (0.07, f + 0.31), (0.0, f + 0.31)], 12), TRIM)
    m.add(lathe([(0.0, f + 0.78), (0.06, f + 0.78), (0.03, f + 0.84), (0.0, f + 0.84)], 12), TRIM)
    return m


def build_shrine():
    m = Model()
    f = FLOOR_Y
    m.add(box(1.5, 1.5, 0.18, 0.04), STONE, at(0, 0, f + 0.09), smooth=False)
    m.add(box(1.15, 1.15, 0.16, 0.03), STONE, at(0, 0, f + 0.26), smooth=False)
    m.add(lathe([(0.0, f + 0.34), (0.32, f + 0.34), (0.24, f + 0.5), (0.2, f + 0.95), (0.3, f + 1.05), (0.0, f + 1.1)], 8),
          STONE, smooth=False)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        m.add(tube([(0.28 * math.cos(a), 0.28 * math.sin(a), f + 1.05), (0.4 * math.cos(a), 0.4 * math.sin(a), f + 1.35),
                    (0.22 * math.cos(a), 0.22 * math.sin(a), f + 1.7)], [0.04, 0.03, 0.0], 6), METAL)
    m.add(ico(0.2, 0), ORB, at(0, 0, f + 1.55, 0.8, 0.8, 1.7), glow=True, smooth=False)
    return m


def build_torch():
    """A wall sconce: the placeable's origin is the flame, the wall is behind it (Blender +Y)."""
    m = Model()
    m.add(box(0.14, 0.03, 0.26, 0.01), IRON, at(0, 0.21, -0.28), smooth=False)
    m.add(tube([(0, 0.2, -0.34), (0, 0.1, -0.3), (0, 0.02, -0.2)], [0.022, 0.02, 0.02], 8), IRON)
    m.add(lathe([(0.0, -0.22), (0.035, -0.21), (0.08, -0.1), (0.1, -0.03), (0.0, -0.02)], 14), IRON)
    m.add(ico(0.07, 1), EMBER, at(0, 0, -0.04, 1.0, 1.0, 0.5), glow=True)
    return m


def torch_lightmap(level):
    """Top-down torch light over a level's extent, with hard 2D shadows from every wall box, softened by a blur."""
    x0, z0, x1, z1 = level.cells.extent
    walls = level.cells.wall_boxes()
    w, h = int((x1 - x0) * LIGHTMAP_PX_PER_M), int((z1 - z0) * LIGHTMAP_PX_PER_M)
    xs = x0 + (np.arange(w) + 0.5) / LIGHTMAP_PX_PER_M
    zs = z0 + (np.arange(h) + 0.5) / LIGHTMAP_PX_PER_M
    light = np.zeros((h, w))
    with np.errstate(divide="ignore", invalid="ignore"):
        for tx, tz, _ in level.torches:
            # Only the pixels and walls within the torch's reach matter.
            i0, i1 = np.searchsorted(xs, tx - TORCH_REACH_M), np.searchsorted(xs, tx + TORCH_REACH_M)
            j0, j1 = np.searchsorted(zs, tz - TORCH_REACH_M), np.searchsorted(zs, tz + TORCH_REACH_M)
            gx, gz = np.meshgrid(xs[i0:i1], zs[j0:j1])
            dx, dz = tx - gx, tz - gz
            falloff = np.clip(1.0 - np.hypot(dx, dz) / TORCH_REACH_M, 0.0, 1.0) ** 1.8
            lit = np.ones_like(falloff, dtype=bool)
            for bx0, bz0, bx1, bz1 in walls:
                if bx1 < tx - TORCH_REACH_M or bx0 > tx + TORCH_REACH_M or bz1 < tz - TORCH_REACH_M or bz0 > tz + TORCH_REACH_M:
                    continue
                ax, bx = (bx0 - gx) / dx, (bx1 - gx) / dx
                az, bz = (bz0 - gz) / dz, (bz1 - gz) / dz
                tmin = np.maximum(np.minimum(ax, bx), np.minimum(az, bz))
                tmax = np.minimum(np.maximum(ax, bx), np.maximum(az, bz))
                lit &= ~((tmax >= tmin) & (tmax > 0.0) & (tmin < 1.0))
            light[j0:j1, i0:i1] += falloff * lit
    for _ in range(3):
        padded = np.pad(light, 1, mode="edge")
        light = sum(padded[1 + a:h + 1 + a, 1 + b:w + 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1)) / 9.0
    light = np.clip(light, 0.0, 1.0)
    return light[..., None] * np.array(TORCH_COLOR)[None, None, :]


def build_projectile():
    m = Model()
    m.add(ico(0.1), BOLT_CORE, glow=True)
    m.add(ico(0.17), BOLT, at(0, 0.03, 0, 1.0, 1.35, 1.0), glow=True)
    m.add(tube([(0, 0.08, 0), (0, 0.3, 0), (0, 0.6, 0)], [0.15, 0.09, 0.0], 12), BOLT, glow=True)
    return m


def kit_wall():
    """One wall cell, centred on the origin: a bevelled block whose seams read as courses of big stones."""
    m = Model()
    m.add(box(CELL, CELL, WALL_H, 0.05), 0, at(0, 0, WALL_BASE_Y + WALL_H / 2), smooth=False)
    return m


def kit_floor():
    m = Model()
    m.add(box(CELL, CELL, 0.1), 0, at(0, 0, FLOOR_Y - 0.05), smooth=False)
    return m


def kit_crate():
    m = Model()
    f = FLOOR_Y
    m.add(box(0.86, 0.86, 0.86, 0.02), PLANK, at(0, 0, f + 0.43), smooth=False)
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.add(box(0.1, 0.1, 0.9, 0.01), PLANK_DARK, at(sx * 0.4, sy * 0.4, f + 0.45), smooth=False)
    m.add(box(0.9, 0.9, 0.1, 0.01), PLANK_DARK, at(0, 0, f + 0.45), smooth=False)
    return m


def kit_barrel():
    m = Model()
    place = at(0, 0, FLOOR_Y)
    m.add(lathe([(0.0, 0.0), (0.3, 0.0), (0.36, 0.25), (0.38, 0.5), (0.36, 0.75), (0.3, 1.0), (0.0, 1.0)], 20), PLANK, place)
    for h, r in ((0.16, 0.345), (0.84, 0.345)):
        m.add(lathe([(0.0, h - 0.035), (r, h - 0.035), (r, h + 0.035), (0.0, h + 0.035)], 20), IRON, place)
    return m


def kit_rubble():
    """A loose scatter of small stones about a metre across."""
    m = Model()
    rng = np.random.default_rng(11)
    for _ in range(7):
        size = rng.uniform(0.06, 0.16)
        m.add(ico(size, 1), STONE, at(rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), FLOOR_Y + size * 0.4, 1.0,
                                      rng.uniform(0.7, 1.3), 0.6, rz=rng.uniform(0, 3)), smooth=False)
    return m


# The dungeon kit: pieces the client places per cell or per prop and merges into meshes. Pieces with a scale take
# world-space UVs at that scale (so neighbours' textures line up); the rest keep their palette UVs.
KIT = {"wall": (kit_wall, 1.5), "floor": (kit_floor, 4.0), "crate": (kit_crate, None), "barrel": (kit_barrel, None),
       "rubble": (kit_rubble, None)}


def write_kit(path):
    pieces = {}
    for name, (build, scale) in KIT.items():
        positions, normals, uvs, indices = build().mesh_data()
        pieces[name] = {"world_uv": scale, "positions": [round(c, 5) for p in positions for c in p],
                        "normals": [round(c, 5) for n in normals for c in n],
                        "uvs": [round(c, 5) for t in uvs for c in t], "indices": indices}
    with open(path, "w") as f:
        json.dump(pieces, f, separators=(",", ":"))
    return {name: len(p["indices"]) // 3 for name, p in pieces.items()}


def build_gate():
    """A portcullis filling a doorway: the origin is the doorway's centre on the floor, its bars run along engine Z."""
    m = Model()
    f, top, half = FLOOR_Y, FLOOR_Y + WALL_H + 0.1, DOOR_HALF
    bars = 11
    for k in range(bars):
        y = -half + 0.12 + k * (2 * half - 0.24) / (bars - 1)
        m.add(tube([(0, y, f - 0.12), (0, y, (f + top) / 2), (0, y, top)], [0.045, 0.045, 0.045], 8), IRON)
        m.add(lathe([(0.0, f - 0.3), (0.05, f - 0.12), (0.0, f - 0.12)], 8), IRON, at(0, y, 0))
    for z in (f + 0.35, f + 1.4, f + 2.45):
        m.add(box(0.07, 2 * half, 0.1, 0.01), IRON, at(0, 0, z), smooth=False)
    m.add(box(0.12, 2 * half + 0.1, 0.16, 0.02), IRON, at(0, 0, top), smooth=False)
    return m


def world_uv(scale):
    def uv(co, normal):
        n = Vector((abs(normal.x), abs(normal.y), abs(normal.z)))
        if n.z >= n.x and n.z >= n.y:
            return (co.x / scale, co.y / scale)
        if n.x >= n.y:
            return (co.y / scale, co.z / scale)
        return (co.x / scale, co.z / scale)
    return uv


def save_image(name, pixels):
    h, w, channels = pixels.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    rgba = pixels if channels == 4 else np.concatenate([pixels, np.ones((h, w, 1))], axis=2)
    rgba = rgba[::-1].astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    path = os.path.join(OUT, "textures", name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def palette_pixels(overrides):
    size = PALETTE_CELLS * PALETTE_PX
    px = np.zeros((size, size, 3))
    colors = dict(BASE_COLORS)
    colors.update(overrides)
    for index, rgb in colors.items():
        cx, cy = index % PALETTE_CELLS, index // PALETTE_CELLS
        px[cy * PALETTE_PX:(cy + 1) * PALETTE_PX, cx * PALETTE_PX:(cx + 1) * PALETTE_PX] = np.array(rgb) / 255.0
    return px[::-1]


def noise(size, rng, octaves=4):
    out = np.zeros((size, size))
    for o in range(octaves):
        cells = 4 * 2 ** o
        grid = rng.random((cells + 1, cells + 1))
        grid[-1, :], grid[:, -1] = grid[0, :], grid[:, 0]
        xs = np.linspace(0, cells, size, endpoint=False)
        i, f = xs.astype(int), xs - xs.astype(int)
        f = f * f * (3 - 2 * f)
        row = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
        row2 = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
        out += (row * (1 - f)[:, None] + row2 * f[:, None]) / 2 ** o
    return out / out.max()


def stones(size, rows, per_row, jitter, base, grout, rng, offset_rows=False, bevel=5, gap=2):
    """Tileable rows of stones with per-stone tint, a one-sided bevel and grout lines."""
    n, fine = noise(size, rng), noise(size, rng, 6)
    px = np.zeros((size, size, 3))
    height = np.zeros((size, size))
    h = size // rows
    xs = np.arange(size)
    for r in range(rows):
        k = per_row
        splits = (np.arange(k) + 0.5 * (r % 2 if offset_rows else rng.random())) * size / k
        splits = np.sort((splits + rng.uniform(-jitter, jitter, k) * size / k) % size)
        idx = (np.searchsorted(splits, xs, side="right") - 1) % k
        dl = (xs - splits[idx]) % size
        dr = (splits[(idx + 1) % k] - xs) % size
        tint = (0.86 + 0.2 * rng.random(k))[:, None] * (1.0 + rng.normal(0, 0.012, (k, 3)))
        ys = np.arange(h)[:, None]
        dt, db = np.broadcast_to(ys, (h, size)), np.broadcast_to(h - 1 - ys, (h, size))
        band = slice(r * h, (r + 1) * h)
        color = np.array(base) / 255.0 * tint[idx][None, :, :] * (0.72 + 0.42 * n[band])[..., None]
        color *= (0.92 + 0.16 * fine[band])[..., None]
        lit = np.clip(1.0 - np.minimum(dt, dl[None, :]) / bevel, 0, 1)
        shade = np.clip(1.0 - np.minimum(db, dr[None, :]) / bevel, 0, 1)
        color *= (1.0 + 0.28 * lit - 0.38 * shade)[..., None]
        edge = np.minimum(np.minimum(dt, db), np.minimum(dl, dr)[None, :])
        mortar = np.array(grout) / 255.0 * (0.8 + 0.4 * fine[band])[..., None]
        px[band] = np.where((edge < gap)[..., None], mortar, color)
        ramp = np.clip((edge - gap) / (bevel * 1.6), 0, 1)
        height[band] = np.where(edge < gap, 0.0, ramp ** 0.6 * (0.85 + 0.15 * tint[idx][None, :, 0])) + 0.12 * fine[band]
    return np.clip(px, 0, 1), height


SHADOW = {"mesh": "shadow", "texture": "blob", "effect": BLOB_EFFECT, "transparent": True}


def normal_pixels(height, strength, gloss):
    """A tileable tangent-space normal map from a height field, with a specular mask in alpha (higher stone, shinier)."""
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    n = np.dstack([-dx * strength, dy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    spec = np.clip(gloss * (0.4 + 0.6 * height / max(height.max(), 1e-6)), 0, 1)
    return np.dstack([n * 0.5 + 0.5, spec])


def mesh_yaml(mesh, texture, effect=EFFECT, transparent=False, params=None, textures=None):
    if effect in (EFFECT, VAT_EFFECT, WALL_EFFECT):
        x0, z0, x1, z1 = LIGHTMAP_RECT
        params = dict(params or {}, LightMapRect=(x0, z0, 1.0 / (x1 - x0), 1.0 / (z1 - z0)),
                      LightScale=(TORCH_STRENGTH, 0, 0, 0))
        textures = dict({"NormalMap": "res:/arpg/textures/flat_n.png"}, **dict(textures or {}),
                        LightMap="res:/arpg/textures/torchlight.png")
    lines = [
        "    -   type: Tr2Mesh",
        "        geometryResPath: \"res:/arpg/meshes/%s.cmf\"" % mesh,
        "        %s:" % ("transparentAreas" if transparent else "opaqueAreas"),
        "        -   type: Tr2MeshArea",
        "            effect:",
        "                type: Tr2Effect",
        "                effectFilePath: \"%s\"" % effect,
    ]
    if params:
        lines.append("                parameters:")
        for pname, value in params.items():
            lines += ["                -   type: Tr2Vector4Parameter",
                      "                    name: \"%s\"" % pname,
                      "                    value: [%s]" % ", ".join("%.3f" % v for v in value)]
    lines.append("                resources:")
    for tname, path in [("DiffuseMap", "res:/arpg/textures/%s.png" % texture)] + sorted((textures or {}).items()):
        lines += ["                -   type: TriTextureParameter",
                  "                    name: \"%s\"" % tname,
                  "                    resourcePath: \"%s\"" % path]
    return lines


def write_red(name, *meshes):
    lines = ["type: WodPlaceableRes", "visualModel:", "    type: Tr2Model", "    meshes:"]
    for mesh in meshes:
        lines += mesh_yaml(**mesh)
    with open(os.path.join(OUT, "placeables", name + ".red"), "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def blob_pixels(size=64):
    ys, xs = np.mgrid[0:size, 0:size]
    r = np.hypot(xs - (size - 1) / 2, ys - (size - 1) / 2) / (size / 2)
    alpha = np.clip(1.0 - r, 0, 1) ** 1.1 * 0.7
    rgba = np.zeros((size, size, 4))
    rgba[..., 3] = alpha
    return rgba


def write_halos(path, name, halos, scale):
    positions, normals, uvs, indices = [], [], [], []
    for center, size in halos:
        c = Vector(center)
        c.z = (c.z + 0.5) * scale - 0.5
        c.x, c.y = c.x * scale, c.y * scale
        base = len(positions)
        for corner in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
            positions.append(to_engine(c))
            normals.append((size * scale, 0.0, 0.0))
            uvs.append(corner)
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    cmf.write_mesh(path, positions, normals, uvs, indices, name=name)


def write_particles(path, name, count, rng, extent):
    positions, normals, uvs, uv1, indices = [], [], [], [], []
    for _ in range(count):
        seed, seed2 = tuple(rng.random(3)), tuple(rng.random(2))
        base = len(positions)
        for corner in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
            positions.append((0.0, 0.0, 0.0))
            normals.append(seed)
            uvs.append(corner)
            uv1.append(seed2)
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    cmf.write_mesh(path, positions, normals, uvs, indices, name=name, uv1=uv1,
                   extra_bounds=[(-extent[0], -extent[1], -extent[2]), extent])


def halo_pixels(size=64):
    ys, xs = np.mgrid[0:size, 0:size]
    r = np.hypot(xs - (size - 1) / 2, ys - (size - 1) / 2) / (size / 2)
    rgba = np.ones((size, size, 4))
    rgba[..., 3] = np.clip(1.0 - r, 0, 1) ** 2.2
    return rgba


def build_shadow(radius=0.8, segments=32):
    m = Model()
    m.add(lambda bm: bmesh.ops.create_circle(bm, cap_ends=True, segments=segments, radius=radius), 0,
          at(0, 0, -0.5 + 0.02))
    return m, lambda co, normal: (0.5 + co.x / (2 * radius), 0.5 + co.y / (2 * radius))


def preview_object(name, model, image, location):
    bm = bmesh.new()
    for layer in model.layers.values():
        tmp = bpy.data.meshes.new("tmp")
        layer.to_mesh(tmp)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            loop[uv_layer].uv = palette_uv(face.material_index)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.set_sharp_from_angle(angle=SMOOTH_ANGLE)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image)
    tex.interpolation = "Closest"
    mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    obj.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(obj)


def preview(models):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    for i, (name, model, image) in enumerate(models):
        preview_object(name, model, image, (i * 1.5 - 2.25, 0, 0.3 if name == "bolt" else 0.0))
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 560
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    # Front three-quarter view, then the game's camera pitch (0.95 rad above the horizon).
    for suffix, pitch, ortho, z in (("", math.radians(78), 6.6, 0.4), ("_game", math.pi / 2 - 0.95, 6.6, 0.2)):
        cam_data.ortho_scale = ortho
        direction = Vector((0.0, -math.sin(pitch), math.cos(pitch)))
        cam.location = Vector((0.0, 0.0, z)) + direction * 12.0
        cam.rotation_euler = (pitch, 0, 0)
        scene.render.filepath = PREVIEW.replace(".png", suffix + ".png")
        bpy.ops.render.render(write_still=True)


def red_meshes(mesh, texture, glow_params=GLOW, ao=True, shadow=True, halo=None):
    base = {"mesh": mesh, "texture": texture}
    if ao:
        base["params"] = {"Occlusion": CHARACTER_AO}
    meshes = [base, {"mesh": mesh + "_glow", "texture": texture, "params": {"Emissive": glow_params}}]
    if halo:
        meshes.append({"mesh": mesh + "_halo", "texture": "halo", "effect": HALO_EFFECT, "transparent": True,
                       "params": {"HaloColor": halo}})
    return meshes + ([SHADOW] if shadow else [])


# Code a character bake runs, besides the model and clips themselves.
BAKE_CODE = [os.path.join(HERE, f) for f in ("arpg_rig.py", "arpg_bake.py")] + \
            [os.path.join(ROOT, "demo", "cmf.py"), os.path.join(ROOT, "tools", "dds.py")]


def character_inputs(model, clips, colors):
    """A fingerprint of everything a character bake reads. Blender's UV packing differs from run to run, so a character
    is only rebaked when this changes; otherwise every rebuild would rewrite all its files."""
    h = hashlib.sha256()
    for layer in ("base", "glow"):
        bm = model.layers[layer]
        bm.verts.index_update()
        deform = bm.verts.layers.deform.active
        for v in bm.verts:
            weights = sorted((k, round(w, 6)) for k, w in v[deform].items()) if deform else ()
            h.update(repr((tuple(round(c, 6) for c in v.co), weights)).encode())
        # Faces by their corners' positions: parts with coincident vertices can come out indexed differently per run.
        faces = sorted((face.material_index, face.smooth, tuple(sorted(tuple(round(c, 5) for c in v.co) for v in face.verts)))
                       for face in bm.faces)
        h.update(repr(faces).encode())
    h.update(repr((model.bones, [(tuple(c), s, b, n) for c, s, b, n in model.halos], model.scale)).encode())
    for clip in clips:
        h.update(repr((clip.name, clip.frames, clip.fps, clip.loop, clip.stride, clip.events)).encode())
        for t in clip.times():
            h.update(repr(clip.pose(t)).encode())
    h.update(repr((sorted((k, sorted(v.items())) for k, v in colors.items()), LOOKS, SMOOTH_ANGLE)).encode())
    for path in BAKE_CODE:
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def vat_meshes(mesh, texture, height, glow_params=GLOW, halo=None):
    rest = 0.5 / height
    state = {"VatState": (rest, rest, 0.0, 0.0), "VatFade": (rest, rest, 0.0, 0.0), "Flash": (0.0, 0.0, 0.0, 0.0),
             "Tint": (0.0, 0.0, 0.0, 0.0)}
    vat = {"VatPos": "res:/arpg/anims/%s_pos.dds" % mesh, "VatNrm": "res:/arpg/anims/%s_nrm.dds" % mesh,
           "NormalMap": "res:/arpg/textures/char_%s_n.png" % mesh}
    meshes = [{"mesh": mesh, "texture": texture, "effect": VAT_EFFECT, "textures": vat,
               "params": dict(state, Occlusion=CHARACTER_AO, Surface=CHARACTER_SURFACE)},
              {"mesh": mesh + "_glow", "texture": texture, "effect": VAT_EFFECT, "textures": vat,
               "params": dict(state, Emissive=glow_params)}]
    if halo:
        meshes.append({"mesh": mesh + "_halo", "texture": "halo", "effect": VAT_HALO_EFFECT, "transparent": True,
                       "textures": {"VatPos": vat["VatPos"]},
                       "params": {"VatState": state["VatState"], "VatFade": state["VatFade"], "HaloColor": halo}})
    return meshes + [SHADOW]


def main():
    for sub in ("meshes", "textures", "placeables"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    rng = np.random.default_rng(3)
    for variant, overrides in PALETTES.items():
        save_image("palette_" + variant, palette_pixels(overrides))
    save_image("palette_enemy", palette_pixels({}))
    for kind, overrides in ENEMY_PALETTES.items():
        save_image("palette_" + kind, palette_pixels(overrides))
    for name, args in (("floor", (512, 4, 3, 0.3, (112, 106, 98), (44, 40, 38), rng)),
                       ("wall", (256, 8, 4, 0.0, (128, 100, 84), (56, 48, 44), rng)),
                       ("ground", (512, 6, 5, 0.45, (60, 56, 52), (26, 24, 22), rng))):
        kw = {"floor": dict(bevel=8, gap=3), "wall": dict(offset_rows=True, bevel=4), "ground": dict(bevel=10, gap=5)}[name]
        color, height = stones(*args, **kw)
        save_image(name, color)
        save_image(name + "_n", normal_pixels(height, {"floor": 5.0, "wall": 3.5, "ground": 5.0}[name], 0.35))
    save_image("flat_n", np.concatenate([np.full((4, 4, 2), 0.5), np.ones((4, 4, 1)), np.full((4, 4, 1), 0.25)], axis=2))
    save_image("blob", blob_pixels())
    save_image("halo", halo_pixels())
    save_image("torchlight", torch_lightmap(TEST_LEVEL))

    meshes = os.path.join(OUT, "meshes")
    player, enemy, shaman, bolt = build_player(), build_enemy(), build_shaman(), build_projectile()
    hound, bloater, shieldbearer = build_hound(), build_bloater(), build_shieldbearer()
    shadow, shadow_uv = build_shadow()
    shadow.export(os.path.join(meshes, "shadow.cmf"), "shadow", shadow_uv)
    anims = os.path.join(OUT, "anims")
    counts = {"projectile": bolt.export(os.path.join(meshes, "projectile_glow.cmf"), "projectile_glow", layer="glow")}
    write_halos(os.path.join(meshes, "projectile_halo.cmf"), "projectile_halo", PROJECTILE_HALOS, 1.0)
    heights = {}
    textures = os.path.join(OUT, "textures")
    variants = {"player": {v: variant_colors(o) for v, o in PALETTES.items()},
                "enemy": dict({"enemy": variant_colors({})}, **{k: variant_colors(o) for k, o in ENEMY_PALETTES.items()}),
                "shaman": {"shaman": variant_colors(SHAMAN_PALETTE)}, "hound": {"hound": variant_colors(HOUND_PALETTE)},
                "bloater": {"bloater": variant_colors(BLOATER_PALETTE)},
                "shieldbearer": {"shieldbearer": variant_colors(SHIELD_PALETTE)}}
    for name, model, clips in (("player", player, MAGE_CLIPS), ("enemy", enemy, IMP_CLIPS), ("shaman", shaman, IMP_CLIPS),
                               ("hound", hound, HOUND_CLIPS), ("bloater", bloater, IMP_CLIPS),
                               ("shieldbearer", shieldbearer, IMP_CLIPS)):
        fingerprint = character_inputs(model, clips, variants[name])
        stamp, table_path = os.path.join(anims, name + ".inputs"), os.path.join(anims, name + ".json")
        if os.path.exists(stamp) and os.path.exists(table_path) and open(stamp).read().strip() == fingerprint:
            with open(table_path) as f:
                heights[name] = json.load(f)["height"]
            counts[name] = "unchanged"
            continue
        baker = lambda obj, name=name: bake_textures(obj, "char_" + name, LOOKS, variants[name], textures)
        counts[name] = bake(name, model, clips, meshes, anims, model.scale_matrix(), SMOOTH_ANGLE, palette_uv, baker)
        heights[name] = counts[name]["vat"][1]
        with open(stamp, "w", newline="\n") as f:
            f.write(fingerprint + "\n")
    os.makedirs(os.path.join(OUT, "kits"), exist_ok=True)
    # A plain floor slab for the model, animation and effect sheets; the game builds its floors from the kit.
    sheet_floor = Model()
    sheet_floor.add(box(40.0, 40.0, 0.1), 0, at(0, 0, FLOOR_Y - 0.05), smooth=False)
    sheet_floor.export(os.path.join(meshes, "floor.cmf"), "floor", world_uv(4.0))
    counts["kit"] = write_kit(os.path.join(OUT, "kits", "dungeon.json"))
    counts["gate"] = build_gate().export(os.path.join(meshes, "gate.cmf"), "gate")

    for variant in PALETTES:
        glow = (0.6, 0.0, 0.0, 0.0) if variant == "dead" else GLOW
        write_red("player_" + variant, *vat_meshes("player", "char_player_" + variant, heights["player"], glow,
                                                   halo=HALO_COLORS.get(variant)))
    write_red("enemy", *vat_meshes("enemy", "char_enemy_enemy", heights["enemy"], halo=HALO_COLORS["enemy"]))
    for kind in ENEMY_PALETTES:
        write_red(kind, *vat_meshes("enemy", "char_enemy_" + kind, heights["enemy"], halo=HALO_COLORS[kind]))
    write_red("shaman", *vat_meshes("shaman", "char_shaman_shaman", heights["shaman"], halo=HALO_COLORS["shaman"]))
    for kind in ("hound", "bloater", "shieldbearer"):
        write_red(kind, *vat_meshes(kind, "char_%s_%s" % (kind, kind), heights[kind], halo=HALO_COLORS[kind]))
    spit_trail = dict(BOLT_TRAIL, params=dict(BOLT_TRAIL["params"], FxColor=(0.5, 1.0, 0.2, 2.0),
                                              FxColorEnd=(0.15, 0.4, 0.05, 1), FxSize=(0.26, 0.06, 0, 0)))
    write_red("spit", *red_meshes("projectile", "palette_spitter", BOLT_GLOW, ao=False, shadow=False,
                                  halo=HALO_COLORS["spit"])[1:], spit_trail)
    boss_trail = dict(BOLT_TRAIL, params=dict(BOLT_TRAIL["params"], FxColor=(0.65, 0.25, 1.0, 2.2),
                                              FxColorEnd=(0.3, 0.05, 0.5, 1), FxSize=(0.3, 0.07, 0, 0)))
    write_red("bossshot", *red_meshes("projectile", "palette_warlord", BOLT_GLOW, ao=False, shadow=False,
                                      halo=HALO_COLORS["bossshot"])[1:], boss_trail)
    write_red("projectile", *red_meshes("projectile", "palette_enemy", BOLT_GLOW, ao=False, shadow=False,
                                        halo=HALO_COLORS["projectile"])[1:], BOLT_TRAIL)
    for count in sorted({n for n, _ in FX_BURSTS.values()}):
        write_particles(os.path.join(meshes, "fx_burst%d.cmf" % count), "fx_burst%d" % count, count, rng, (4.0, 4.0, 4.0))
    write_particles(os.path.join(meshes, "fx_trail28.cmf"), "fx_trail28", 28, rng, (1.0, 1.0, 3.0))
    loot = build_loot()
    loot.export(os.path.join(meshes, "loot.cmf"), "loot")
    loot.export(os.path.join(meshes, "loot_glow.cmf"), "loot_glow", layer="glow")
    write_halos(os.path.join(meshes, "loot_halo.cmf"), "loot_halo", [((0.0, 0.0, 0.05), 0.75)], 1.0)
    for kind, orb, halo in (("health", (255, 60, 50), (1.0, 0.25, 0.2, 0.8)), ("mana", (60, 120, 255), (0.3, 0.5, 1.0, 0.8))):
        save_image("palette_loot_" + kind, palette_pixels({ORB: orb}))
        write_red("loot_" + kind, {"mesh": "loot", "texture": "palette_loot_" + kind},
                  {"mesh": "loot_glow", "texture": "palette_loot_" + kind, "params": {"Emissive": (1.0, 0.4, 0, 0)}},
                  {"mesh": "loot_halo", "texture": "halo", "effect": HALO_EFFECT, "transparent": True,
                   "params": {"HaloColor": halo}}, SHADOW)
    shrine = build_shrine()
    shrine.export(os.path.join(meshes, "shrine.cmf"), "shrine")
    shrine.export(os.path.join(meshes, "shrine_glow.cmf"), "shrine_glow", layer="glow")
    write_halos(os.path.join(meshes, "shrine_halo.cmf"), "shrine_halo", [((0.0, 0.0, 1.55), 1.6)], 1.0)
    save_image("palette_shrine", palette_pixels({ORB: (255, 200, 90), STONE: (110, 104, 118)}))
    write_red("shrine", {"mesh": "shrine", "texture": "palette_shrine", "params": {"Occlusion": (0.35, -0.5, 1.0, 0)}},
              {"mesh": "shrine_glow", "texture": "palette_shrine", "params": {"Emissive": (1.0, 0.8, 0, 0)}},
              {"mesh": "shrine_halo", "texture": "halo", "effect": HALO_EFFECT, "transparent": True,
               "params": {"HaloColor": (1.0, 0.75, 0.3, 0.75)}}, SHADOW)
    torch = build_torch()
    counts["torch"] = torch.export(os.path.join(meshes, "torch.cmf"), "torch")
    torch.export(os.path.join(meshes, "torch_glow.cmf"), "torch_glow", layer="glow")
    write_particles(os.path.join(meshes, "fx_flame24.cmf"), "fx_flame24", 24, rng, (0.5, 1.0, 0.5))
    write_halos(os.path.join(meshes, "torch_halo.cmf"), "torch_halo", [((0.0, 0.0, 0.15), 1.3)], 1.0)
    write_red("torch", {"mesh": "torch", "texture": "palette_enemy"},
              {"mesh": "torch_glow", "texture": "palette_enemy", "params": {"Emissive": (1.0, 0.6, 0, 0)}},
              {"mesh": "fx_flame24", "texture": "halo", "effect": FX_FLAME_EFFECT, "transparent": True,
               "params": {"FxTime": (0, 1, 0, 0), "FxColor": (1.0, 0.62, 0.22, 1.6), "FxColorEnd": (0.9, 0.18, 0.03, 1),
                          "FxSize": (0.26, 0.07, 0, 0), "FxFlame": (0.55, 0.08, 2.2, 0)}},
              {"mesh": "torch_halo", "texture": "halo", "effect": HALO_EFFECT, "transparent": True,
               "params": {"HaloColor": (1.0, 0.55, 0.2, 0.7), "HaloFacing": (1.0, 0, 0, 0)}})
    for name, (count, params) in FX_BURSTS.items():
        write_red(name, {"mesh": "fx_burst%d" % count, "texture": "halo", "effect": FX_BURST_EFFECT,
                         "transparent": True, "params": params})
    write_red("gate", {"mesh": "gate", "texture": "palette_enemy"})
    write_red("floor", {"mesh": "floor", "texture": "floor", "textures": {"NormalMap": "res:/arpg/textures/floor_n.png"},
                        "params": {"Surface": (1.0, 0.55, 18.0, 0.0)}})
    print("[assets] triangles: %s" % counts)

    preview([("player", player, os.path.join(textures, "palette_self.png")),
             ("other", player, os.path.join(textures, "palette_other.png")),
             ("enemy", enemy, os.path.join(textures, "palette_enemy.png")),
             ("bolt", bolt, os.path.join(textures, "palette_enemy.png"))])
    print("[assets] preview: %s" % PREVIEW)


main()
