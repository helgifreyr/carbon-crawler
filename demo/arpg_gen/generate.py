"""One act from a template and a seed: graph, layout, simulation, cells, then what stands on them."""
import math
import random

import numpy as np

from arpg_gen import interpret, karst, layout, light, template
from arpg_map import CELL, FLOOR, CellMap, Level

TORCH_SPACING_M = 9.0
# Floor cells per pack in ordinary regions, the most packs a region gets, and the room kept around each pack.
CELLS_PER_PACK, MAX_PACKS, PACK_GAP_CELLS = 220, 4, 9
PROCESSES = {"karst": karst.simulate}


class GenerationFailed(Exception):
    pass


def plain(value):
    """numpy scalars and arrays inside nested lists, tuples and dicts as plain Python, so the engine can send them."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(plain(v) for v in value)
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def wall_distance(floor):
    """Each floor cell's distance in cells to the nearest rock (a two-pass chamfer transform)."""
    nz, nx = floor.shape
    d = np.where(floor, 1e6, 0.0)
    for z in range(nz):
        for x in range(nx):
            if d[z, x]:
                d[z, x] = min(d[z, x], (d[z - 1, x] + 1) if z else 1, (d[z, x - 1] + 1) if x else 1)
    for z in range(nz - 1, -1, -1):
        for x in range(nx - 1, -1, -1):
            if d[z, x]:
                d[z, x] = min(d[z, x], (d[z + 1, x] + 1) if z < nz - 1 else 1, (d[z, x + 1] + 1) if x < nx - 1 else 1)
    return d


def torches(cells, rng):
    """Torches on wall faces next to floor, roughly TORCH_SPACING_M apart, each facing out of its wall."""
    sides = [((0, -1), 0.0), ((0, 1), math.pi), ((-1, 0), math.pi / 2), ((1, 0), -math.pi / 2)]
    spots = []
    for j in range(cells.nz):
        for i in range(cells.nx):
            if cells.get(i, j) != FLOOR:
                continue
            for (di, dj), yaw in sides:
                if cells.is_wall(i + di, j + dj):
                    x0, z0, x1, z1 = cells.cell_rect(i, j)
                    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
                    spots.append((cx + di * (CELL / 2 - 0.22), cz + dj * (CELL / 2 - 0.22), yaw))
    rng.shuffle(spots)
    placed = []
    for x, z, yaw in spots:
        if all((x - px) ** 2 + (z - pz) ** 2 >= TORCH_SPACING_M ** 2 for px, pz, _ in placed):
            placed.append((x, z, yaw))
    return placed


def pack_kinds(depth, rng):
    """A pack's enemy kinds: bigger and stranger the deeper it sits."""
    size = rng.randint(3, 4) + round(depth * 3)
    pool = ["imp"] * 6 + ["spitter"] * (2 if depth > 0.1 else 0) + ["hound"] * (2 if depth > 0.25 else 0) \
        + ["brute"] * (1 if depth > 0.35 else 0) + ["shaman"] * (1 if depth > 0.45 else 0) \
        + ["bloater"] * (1 if depth > 0.55 else 0) + ["shieldbearer"] * (1 if depth > 0.65 else 0)
    return [rng.choice(pool) for _ in range(size)]


def arena(floor, owner, k, depth, rng):
    """A sealed arena in region k: its floor cells, a gate on every floor cell just outside it, and its waves."""
    # Only the region's largest connected stretch of floor: pockets joined to it only from outside stay outside.
    label = interpret.components(floor & (owner == k))
    sizes = np.bincount(label.ravel())
    sizes[0] = 0
    inside = label == sizes.argmax()
    gates, yaws = [], []
    nz, nx = floor.shape
    for z, x in np.argwhere(floor & (owner != k)):
        for dz, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            a, b = z + dz, x + dx
            if 0 <= a < nz and 0 <= b < nx and inside[a, b]:
                gates.append((x * CELL, z * CELL, (x + 1) * CELL, (z + 1) * CELL))
                # A portcullis spans the doorway: across z when the arena lies east or west of it.
                yaws.append(0.0 if dx else math.pi / 2)
                break
    waves = [pack_kinds(min(1.0, depth + 0.1 * w), rng) + pack_kinds(depth, rng) for w in range(3)]
    return {"cells": [(int(x), int(z)) for z, x in np.argwhere(inside)], "waves": waves}, gates, yaws, inside


def generate(template_name, seed, attempts=4, debug=False):
    """A Level for the template (a name, or a .json path); tries further seeds if a result fails validation."""
    tmpl = template.load(template_name)
    for attempt in range(attempts):
        try:
            return build(tmpl, seed + 1000 * attempt, debug)
        except GenerationFailed as failure:
            print("[gen] %s seed %d rejected: %s" % (template_name, seed + 1000 * attempt, failure))
    raise GenerationFailed("no valid act for %s from seed %d" % (template_name, seed))


def build(tmpl, seed, debug=False):
    rng, nrng = random.Random(seed), np.random.default_rng(seed)
    graph = template.instantiate(tmpl, rng)
    pos, r = layout.place_anchors(graph, rng, tmpl.get("shape", {}).get("aspect", 1.5))
    owner = layout.grow_regions(pos, r, nrng)
    fields = {}
    for name in tmpl.get("processes", ["karst"]):
        fields.update(PROCESSES[name](graph, pos, r, owner, nrng))
    floor, score = interpret.carve_cells(graph, pos, r, owner, fields)
    interpret.repair(graph, pos, floor, score)
    target = sum(n["area"] for n in graph.nodes)
    if floor.sum() < 0.8 * target:
        raise GenerationFailed("only %d floor cells of %d wanted" % (floor.sum(), target))
    nz, nx = floor.shape
    cells = CellMap((0.0, 0.0), nx, nz, interpret.to_cells(floor))

    def world(k):
        z, x = interpret.anchor_cell(floor, pos, k)
        return (x + 0.5) * CELL, (z + 0.5) * CELL

    clearance = wall_distance(floor)
    route = graph.route()
    start, boss = route[0], route[-1]
    regions, packs, checkpoints, taken = [], [], [world(start)], [world(start)]
    arenas, gates, gate_yaws, arena_points = [], [], [], {}
    for k, node in enumerate(graph.nodes):
        regions.append({"id": node["id"], "type": node["type"], "depth": node["depth"], "at": world(k)})
        if node["type"] == "checkpoint":
            checkpoints.append(world(k))
    for k, node in enumerate(graph.nodes):
        if node["type"] == "arena":
            spec, boxes, yaws, inside = arena(floor, owner, k, node["depth"], rng)
            # The route goes through the arena proper, so walking it seals the gates behind you.
            zs, xs = np.nonzero(inside)
            near = np.argmin((xs - pos[k, 0]) ** 2 + (zs - pos[k, 1]) ** 2)
            arena_points[k] = ((xs[near] + 0.5) * CELL, (zs[near] + 0.5) * CELL)
            spec["gates"] = list(range(len(gates), len(gates) + len(boxes)))
            arenas.append(spec)
            gates += boxes
            gate_yaws += yaws
            continue
        if node["type"] in ("start", "checkpoint", "boss"):
            continue
        mine = [tuple(c) for c in np.argwhere(floor & (owner == k) & (clearance >= 2))]
        count = 1 if node["type"] == "vault" else min(MAX_PACKS, max(1, int((floor & (owner == k)).sum() / CELLS_PER_PACK)))
        rng.shuffle(mine)
        for z, x in mine:
            if count == 0:
                break
            at = ((x + 0.5) * CELL, (z + 0.5) * CELL)
            if all(math.hypot(at[0] - tx, at[1] - tz) >= PACK_GAP_CELLS * CELL for tx, tz in taken):
                depth = min(1.0, node["depth"] + (0.3 if node["type"] == "vault" else 0.0))
                packs.append({"at": at, "kinds": pack_kinds(depth, rng), "depth": depth, "region": k,
                              "reward": node["type"] == "vault"})
                taken.append(at)
                count -= 1
    if not packs:
        raise GenerationFailed("no room for packs")
    # The exit opens on the far side of the boss's chamber from where the route comes in.
    bx, bz = world(boss)
    px, pz = world(route[-2])
    away = [(math.hypot(x * CELL - px, z * CELL - pz), (x + 0.5) * CELL, (z + 0.5) * CELL)
            for z, x in np.argwhere(floor & (owner == boss) & (clearance >= 2))]
    exit_at = max(away)[1:] if away else (bx, bz)
    level = Level(tmpl["name"], cells, gates=plain(gates), torches=plain(torches(cells, rng)), shrine=plain(world(start)))
    level.features = plain({"seed": seed, "tileset": tmpl.get("tileset", "dungeon"), "start": world(start), "checkpoints": checkpoints, "packs": packs,
                      "boss": (bx, bz), "exit": exit_at, "regions": regions,
                      "route": [arena_points.get(k) or world(k) for k in route], "arenas": arenas, "gate_yaws": gate_yaws})
    level.lightmap = light.bake(level)
    if debug:
        # What the editor draws: the simulation's fields and the layout behind the cells.
        level.debug = {"fields": {k: v.astype(np.float32) for k, v in fields.items()}, "owner": owner,
                       "floor": floor, "pos": pos, "r": r, "nodes": graph.nodes, "edges": graph.edges}
    return level
