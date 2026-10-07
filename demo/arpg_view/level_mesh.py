"""Builds a level's meshes at load time: kit pieces merged per chunk of cells, written as CMF and placeable files."""
import json
import math
import os

import cmf
from arpg_view.cave_mesh import CaveBuilder
from arpg_map import CELL, FLOOR

RES_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "res")
KIT_PATH = os.path.join(RES_ROOT, "arpg", "kits", "dungeon.json")
CHUNK = 16
EFFECT = "res:/graphics/effect/game/texmesh.fx"
WALL_EFFECT = "res:/graphics/effect/game/wall.fx"
TORCH_STRENGTH = 1.5
# Sides of a wall cell, by the direction a face points: a face toward another wall cell is never seen.
SIDES = {(1, 0): "+x", (-1, 0): "-x", (0, 1): "+z", (0, -1): "-z"}


class Piece:
    """A kit piece's triangles, grouped by the way each faces: up, down, one of the four sides, or slanted ("edge":
    bevels, never culled, so neighbouring pieces meet without gaps)."""

    def __init__(self, data, top_only=False):
        p, n, t = data["positions"], data["normals"], data["uvs"]
        self.world_uv = data["world_uv"]
        self.groups = {}
        idx = data["indices"]
        for k in range(0, len(idx), 3):
            corners = [(tuple(p[3 * v:3 * v + 3]), tuple(n[3 * v:3 * v + 3]), tuple(t[2 * v:2 * v + 2])) for v in idx[k:k + 3]]
            nx, ny, nz = (sum(c[1][a] for c in corners) for a in range(3))
            length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            if max(abs(nx), abs(ny), abs(nz)) < 0.9 * length:
                group = "edge"
            elif abs(ny) >= abs(nx) and abs(ny) >= abs(nz):
                group = "up" if ny > 0 else "down"
            elif abs(nx) >= abs(nz):
                group = "+x" if nx > 0 else "-x"
            else:
                group = "+z" if nz > 0 else "-z"
            if not top_only or group == "up":
                self.groups.setdefault(group, []).extend(corners)


def load_kit(path=KIT_PATH):
    with open(path) as f:
        data = json.load(f)
    kit = {name: Piece(d, top_only=name == "floor") for name, d in data.items()}
    # The ground is the floor tile sunk a little lower, with a coarser texture scale.
    ground = Piece(data["floor"], top_only=True)
    ground.world_uv = 6.0
    ground.groups = {g: [((px, py - 0.07, pz), n, t) for (px, py, pz), n, t in corners] for g, corners in ground.groups.items()}
    kit["ground"] = ground
    return kit


def front_face(piece):
    """+1 if a triangle's (b - a) x (c - a) points the way its normal does in the kit, -1 if the other way."""
    (a, n, _), (b, _, _), (c, _, _) = piece.groups["up"][:3]
    cross_y = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2])
    return 1 if cross_y * n[1] > 0 else -1


def world_uv(position, normal, scale):
    # The same projection the Blender build used for the old whole-dungeon meshes (Blender's y is the engine's -z).
    x, y, z = position
    nx, ny, nz = (abs(c) for c in normal)
    if ny >= nx and ny >= nz:
        u, v = x / scale, -z / scale
    elif nx >= nz:
        u, v = -z / scale, y / scale
    else:
        u, v = x / scale, y / scale
    return u, 1.0 - v


class MeshBuilder:
    def __init__(self):
        self.positions, self.normals, self.uvs = [], [], []

    def add(self, piece, x, z, yaw=0.0, skip=(), stretch=(1.0, 1.0)):
        c, s = math.cos(yaw), math.sin(yaw)
        for group, corners in piece.groups.items():
            if group in skip:
                continue
            for (px, py, pz), (nx, ny, nz), uv in corners:
                px, pz = px * stretch[0], pz * stretch[1]
                position = (x + px * c + pz * s, py, z - px * s + pz * c)
                normal = (nx * c + nz * s, ny, -nx * s + nz * c)
                self.positions.append(position)
                self.normals.append(normal)
                self.uvs.append(world_uv(position, normal, piece.world_uv) if piece.world_uv else uv)

    def write(self, path, name):
        if not self.positions:
            return False
        cmf.write_mesh(path, self.positions, self.normals, self.uvs, list(range(len(self.positions))), name=name)
        return True


def red_text(meshes, looks):
    """A placeable file holding several (mesh path, kind, light) meshes; light is (rect, lightmap texture path)."""
    lines = ["type: WodPlaceableRes", "visualModel:", "    type: Tr2Model", "    meshes:"]
    for mesh_path, kind, light in meshes:
        lines += mesh_lines(mesh_path, *looks[kind], light=light)
    return "\n".join(lines) + "\n"


def mesh_lines(mesh_path, texture, normal_map, effect=EFFECT, params=None, light=None):
    params = dict(params or {})
    textures = [("DiffuseMap", "res:/arpg/textures/%s.png" % texture), ("NormalMap", normal_map)]
    if light is not None:
        (x0, z0, x1, z1), light_path = light
        params.update(LightMapRect=(x0, z0, 1.0 / (x1 - x0), 1.0 / (z1 - z0)), LightScale=(TORCH_STRENGTH, 0, 0, 0))
        textures.append(("LightMap", light_path))
    lines = ["    -   type: Tr2Mesh", "        geometryResPath: \"%s\"" % mesh_path, "        opaqueAreas:",
             "        -   type: Tr2MeshArea", "            effect:", "                type: Tr2Effect",
             "                effectFilePath: \"%s\"" % effect, "                parameters:"]
    for name, value in params.items():
        lines += ["                -   type: Tr2Vector4Parameter", "                    name: \"%s\"" % name,
                  "                    value: [%s]" % ", ".join("%.6f" % v for v in value)]
    lines.append("                resources:")
    for name, path in textures:
        lines += ["                -   type: TriTextureParameter", "                    name: \"%s\"" % name,
                  "                    resourcePath: \"%s\"" % path]
    return lines


# What each kind of level mesh looks like: (texture, normal map, effect, parameters).
CAVE_LOOKS = {
    "walls": ("cave_rock", "res:/arpg/textures/cave_rock_n.png", WALL_EFFECT,
              {"SeeThrough": (0, -1000, 0, 0), "EyePos": (0, 0, 0, 1), "Surface": (1.0, 0.35, 12.0, 0.2)}),
    "tops": ("cave_top", "res:/arpg/textures/cave_rock_n.png", WALL_EFFECT,
             {"SeeThrough": (0, -1000, 0, 0), "EyePos": (0, 0, 0, 1), "Surface": (1.0, 0.2, 12.0, 0.2)}),
    "floor": ("cave_floor", "res:/arpg/textures/cave_floor_n.png", EFFECT, {"Surface": (1.0, 0.45, 14.0, 0.0)}),
    "ground": ("cave_top", "res:/arpg/textures/cave_rock_n.png", EFFECT, {"Surface": (1.0, 0.2, 12.0, 0.0)}),
}
LOOKS = {
    "walls": ("wall", "res:/arpg/textures/wall_n.png", WALL_EFFECT,
              {"SeeThrough": (0, -1000, 0, 0), "EyePos": (0, 0, 0, 1), "Surface": (1.0, 0.4, 16.0, 0.25)}),
    "floor": ("floor", "res:/arpg/textures/floor_n.png", EFFECT, {"Surface": (1.0, 0.55, 18.0, 0.0)}),
    "ground": ("ground", "res:/arpg/textures/ground_n.png", EFFECT, {"Surface": (1.0, 0.3, 14.0, 0.0)}),
    "props": ("palette_enemy", "res:/arpg/textures/flat_n.png", EFFECT, {"Occlusion": (0.35, -0.5, 1.0, 0)}),
}


def build(level, out_dir, prefix, light, kit=None):
    """Writes the level's meshes into out_dir, one placeable per chunk; returns [(has walls, placeable file name)]."""
    kit = kit or load_kit()
    cells = level.cells
    builders = {}

    def builder(kind, ci, cj):
        return builders.setdefault((kind, ci, cj), MeshBuilder())

    caves = level.features.get("tileset") == "caves"
    looks = dict(LOOKS, **CAVE_LOOKS) if caves else LOOKS
    if caves:
        rock = CaveBuilder(cells, front_face(kit["floor"]), lambda p, n: world_uv(p, n, 2.5))
        for j in range(cells.nz + 1):
            for i in range(cells.nx + 1):
                chunk = (min(i, cells.nx - 1) // CHUNK, min(j, cells.nz - 1) // CHUNK)
                rock.corner(builder("walls", *chunk), builder("tops", *chunk), i, j)
    for j in range(cells.nz):
        for i in range(cells.nx):
            x0, z0, x1, z1 = cells.cell_rect(i, j)
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            chunk = (i // CHUNK, j // CHUNK)
            if cells.get(i, j) == FLOOR or (caves and cells.is_wall(i, j)):
                # Under cave rock too: the rough walls leave slivers of a wall cell's floor in view.
                builder("floor", *chunk).add(kit["floor"], cx, cz)
            elif cells.is_wall(i, j):
                hidden = ["down"] + [side for (di, dj), side in SIDES.items() if cells.is_wall(i + di, j + dj)]
                builder("walls", *chunk).add(kit["wall"], cx, cz, skip=hidden)
    for kind, x, z, yaw in level.props:
        if kind in kit:
            i, j = cells.cell_of(x, z)
            builder("props", i // CHUNK, j // CHUNK).add(kit[kind], x, z, yaw)
    # The ground under everything is one floor tile stretched well past the level, just below the floor.
    gx0, gz0, gx1, gz1 = cells.extent
    margin = 80.0
    ground = MeshBuilder()
    ground.add(kit["ground"], (gx0 + gx1) / 2, (gz0 + gz1) / 2,
               stretch=((gx1 - gx0 + 2 * margin) / CELL, (gz1 - gz0 + 2 * margin) / CELL))
    builders[("ground", 0, 0)] = ground
    chunks = {}
    for (kind, ci, cj), b in sorted(builders.items()):
        name = "%s_%s_%d_%d" % (prefix, kind, ci, cj)
        if b.write(os.path.join(out_dir, name + ".cmf"), name):
            chunks.setdefault((ci, cj), []).append(("gen:/%s.cmf" % name, kind, light))
    placed = []
    for (ci, cj), meshes in sorted(chunks.items()):
        name = "%s_chunk_%d_%d.red" % (prefix, ci, cj)
        with open(os.path.join(out_dir, name), "w", newline="\n") as f:
            f.write(red_text(meshes, looks))
        placed.append((any(kind in ("walls", "tops") for _, kind, _ in meshes), name))
    return placed
