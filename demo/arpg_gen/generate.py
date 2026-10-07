"""One act from a template and a seed: graph, layout, simulation, cells, then what stands on them."""
import math
import random

import numpy as np

from arpg_gen import interpret, karst, layout, light, template
from arpg_map import CELL, FLOOR, CellMap, Level

TORCH_SPACING_M = 9.0
GATE_THICKNESS_M = 0.6
# How far out from an arena's way in its gate may stand, in cells.
CUT_SEARCH = 7
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


STEPS4 = ((0, 1), (0, -1), (1, 0), (-1, 0))
STEPS8 = STEPS4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _groups(cells):
    """cells (a set of (z, x)) split into 8-connected groups."""
    groups, left = [], set(cells)
    while left:
        stack = [left.pop()]
        group = set(stack)
        while stack:
            z, x = stack.pop()
            for dz, dx in STEPS8:
                n = (z + dz, x + dx)
                if n in left:
                    left.discard(n)
                    group.add(n)
                    stack.append(n)
        groups.append(group)
    return groups


def arena(floor, owner, k, depth, rng):
    """A sealed arena in region k: a straight gate across each way in, at its narrowest within reach, and waves.

    Returns the arena spec, the gate boxes and yaws, and the arena's cells (which take in the pockets up to its gates)."""
    label = interpret.components(floor & (owner == k))
    sizes = np.bincount(label.ravel())
    sizes[0] = 0
    nz, nx = floor.shape
    inside = {(int(z), int(x)) for z, x in np.argwhere(label == sizes.argmax())}

    def open_(c):
        return 0 <= c[0] < nz and 0 <= c[1] < nx and floor[c]

    border = {(z + dz, x + dx) for z, x in inside for dz, dx in STEPS4
              if open_((z + dz, x + dx)) and (z + dz, x + dx) not in inside}
    entrances = _groups(border)
    cuts, gates, yaws = [], [], []

    def flood(blocked, stop=()):
        """Floor reachable from the arena around blocked cells; None as soon as it touches a stop cell."""
        seen, stack = set(inside), list(inside)
        while stack:
            z, x = stack.pop()
            for dz, dx in STEPS4:
                n = (z + dz, x + dx)
                if n in seen or n in blocked or not open_(n):
                    continue
                if n in stop:
                    return None
                seen.add(n)
                stack.append(n)
        return seen

    for entrance in entrances:
        others = border - entrance
        # Floor outward from this way in, not through the arena: the cut is looked for within CUT_SEARCH cells of it.
        dist, frontier = {c: 0 for c in entrance}, list(entrance)
        while frontier:
            nxt = []
            for z, x in frontier:
                for dz, dx in STEPS4:
                    n = (z + dz, x + dx)
                    if open_(n) and n not in inside and n not in dist and n not in others:
                        dist[n] = dist[(z, x)] + 1
                        if dist[n] <= CUT_SEARCH:
                            nxt.append(n)
            frontier = nxt
        far = {c for c, d in dist.items() if d > CUT_SEARCH}
        if not far:
            continue
        candidates = []
        for c in dist:
            if dist[c] > CUT_SEARCH:
                continue
            for axis in (0, 1):
                run, touches = [c], False
                for sign in (-1, 1):
                    n = c
                    while True:
                        n = (n[0] + sign, n[1]) if axis == 0 else (n[0], n[1] + sign)
                        if not open_(n):
                            break
                        if n in inside:
                            touches = True
                            break
                        run.append(n)
                if not touches:
                    candidates.append((len(run), dist[c], axis, frozenset(run)))
        for length, _, axis, run in sorted(candidates, key=lambda t: t[:2]):
            if flood(set(run) | others | {cell for cut, _ in cuts for cell in cut}, far) is not None:
                cuts.append((run, axis))
                break
    blocked = {cell for cut, _ in cuts for cell in cut}
    cells = flood(blocked)
    half = GATE_THICKNESS_M / 2
    for run, axis in cuts:
        for z, x in run:
            cx, cz = (x + 0.5) * CELL, (z + 0.5) * CELL
            if axis == 0:
                # A run down z: the gate spans z.
                gates.append((cx - half, z * CELL, cx + half, (z + 1) * CELL))
                yaws.append(0.0)
            else:
                gates.append((x * CELL, cz - half, (x + 1) * CELL, cz + half))
                yaws.append(math.pi / 2)
    # Players count as in the arena a cell clear of every gate and of the floor outside, so no gate closes on anyone.
    deep = {c for c in cells if all((c[0] + dz, c[1] + dx) in cells or not open_((c[0] + dz, c[1] + dx))
                                    for dz, dx in STEPS8)}
    waves = [pack_kinds(min(1.0, depth + 0.1 * w), rng) + pack_kinds(depth, rng) for w in range(3)]
    mask = np.zeros_like(floor)
    for c in cells:
        mask[c] = True
    return ({"cells": [(x, z) for z, x in sorted(cells)], "deep": [(x, z) for z, x in sorted(deep)], "waves": waves},
            gates, yaws, mask)


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
