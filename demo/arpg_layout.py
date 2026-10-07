"""Sizes every level shares, and the hand-built five-room dungeon kept as a fixed test level."""
import math

from arpg_map import CELL, FLOOR, ROCK, CellMap, Level

WALL_H, WALL_BASE_Y = 3.0, -1.0
PLAYER_RADIUS, ENEMY_RADIUS, PROJECTILE_RADIUS = 0.5, 0.5, 0.25
FLOOR_Y = -PLAYER_RADIUS
TORCH_Y = 1.25
LIGHTMAP_PX_PER_M = 4
# The props that collide, as the side of the square each blocks; others (rubble) are only decoration.
PROP_SIZE = {"crate": 0.9, "barrel": 0.8}
SHRINE_RANGE = 3.0
SHRINE_HALF = 0.55
# Rooms of the test level are joined by corridors along z = 0, DOOR_HALF either side.
DOOR_HALF = 2.0


def _blocks(rects):
    return [tuple(float(v) for v in r) for r in rects]


# The test dungeon, west to east: each room's floor rect (x0, z0, x1, z1), its pillars and free-standing walls (all on
# the CELL grid), and the wave fought in it. The hall is where a run starts; the last room is the Warlord's.
TEST_ROOMS = [
    {"name": "The Hall", "rect": (-30.0, -20.0, 30.0, 20.0), "wave": 1,
     "blocks": _blocks([(x, z, x + 2, z + 2) for x in (-20, -2, 16) for z in (-10, 8)] + [(-6, -2, 6, 0)])},
    {"name": "The Crypt", "rect": (40.0, -18.0, 76.0, 18.0), "wave": 2,
     "blocks": _blocks([(x, z, x + 4, z + 4) for x in (48, 64) for z in (-10, 6)] + [(56, -2, 60, 2)])},
    {"name": "The Gallery", "rect": (86.0, -10.0, 146.0, 10.0), "wave": 3,
     "blocks": _blocks([(x, -4 if k % 2 == 0 else 2, x + 2, -2 if k % 2 == 0 else 4) for k, x in enumerate(range(96, 140, 10))])},
    {"name": "The Ring", "rect": (156.0, -22.0, 200.0, 22.0), "wave": 4,
     "blocks": _blocks([(170, -8, 186, 8)] + [(x, z, x + 2, z + 2) for x in (162, 192) for z in (-16, 14)])},
    {"name": "The Throne Room", "rect": (210.0, -20.0, 260.0, 20.0), "wave": 5,
     "blocks": _blocks([(x, z, x + 4, z + 4) for x in (222, 244) for z in (-12, 8)])},
]
TEST_CORRIDORS = [(a["rect"][2], -DOOR_HALF, b["rect"][0], DOOR_HALF) for a, b in zip(TEST_ROOMS, TEST_ROOMS[1:])]
TEST_SHRINE = (0.0, 5.0)


def _props(rooms):
    props = []
    for i, room in enumerate(rooms):
        x0, z0, x1, z1 = room["rect"]
        for sx, cx in ((-1.0, x0 + 0.5), (1.0, x1 - 0.5)):
            for sz, cz in ((-1.0, z0 + 0.5), (1.0, z1 - 0.5)):
                props += [("crate", cx, cz, 0.3 * sx * sz), ("barrel", cx - sx * 1.35, cz, 0.0),
                          ("barrel", cx, cz - sz * 1.3, 0.0)]
        # Rubble in each corner, kicked a little way out from it; it doesn't collide.
        for k, (sx, sz) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1))):
            props.append(("rubble", (x0 + x1) / 2 + sx * ((x1 - x0) / 2 - 2.4), (z0 + z1) / 2 + sz * ((z1 - z0) / 2 - 1.3),
                          1.3 * (i * 4 + k)))
        if i == 0:
            props += [("barrel", -6.0, z0 + 0.45, 0.0), ("barrel", 6.4, z0 + 0.45, 0.0), ("crate", -18.0, z1 - 0.5, 0.15),
                      ("crate", 18.0, z1 - 0.5, -0.2), ("barrel", x0 + 0.45, -5.0, 0.0), ("barrel", x1 - 0.45, 5.0, 0.0)]
    # The crypt's coffins, end to end along its side walls.
    for x in (46.0, 58.0, 70.0):
        props += [("crate", x - 0.45, -17.4, 0.0), ("crate", x + 0.45, -17.4, 0.0),
                  ("crate", x - 0.45, 17.4, 0.0), ("crate", x + 0.45, 17.4, 0.0)]
    return props


def _torches(rooms, corridors):
    """Wall torches as (x, z, yaw): yaw turns the torch's front (+Z) away from the wall it hangs on."""
    inset = 0.22
    torches = []
    for room in rooms:
        x0, z0, x1, z1 = room["rect"]
        w, d = x1 - x0, z1 - z0
        n = max(2, round(w / 12.0))
        for k in range(n):
            x = x0 + w * (k + 0.5) / n
            torches += [(x, z0 + inset, 0.0), (x, z1 - inset, math.pi)]
        m = max(1, round(d / 10.0))
        for k in range(m):
            z = z0 + d * (k + 0.5) / m
            if abs(z) < DOOR_HALF + 0.6:
                z += (DOOR_HALF + 1.5) * (1.0 if k >= m / 2 else -1.0)
            torches += [(x0 + inset, z, math.pi / 2), (x1 - inset, z, -math.pi / 2)]
        # A torch on each pillar, on the face toward the room's middle.
        for bx0, bz0, bx1, bz1 in room["blocks"]:
            cx = (bx0 + bx1) / 2
            if bz1 - bz0 >= 1.6 and bx1 - bx0 <= 4.0:
                torches.append((cx, bz1 + inset, 0.0) if bz0 + bz1 < z0 + z1 else (cx, bz0 - inset, math.pi))
    for cx0, _, cx1, _ in corridors:
        x = (cx0 + cx1) / 2
        torches += [(x, -DOOR_HALF + inset, 0.0), (x, DOOR_HALF - inset, math.pi)]
    return torches


def test_level():
    rooms, corridors = TEST_ROOMS, TEST_CORRIDORS
    cells = CellMap.covering(min(r["rect"][0] for r in rooms) - 2 * CELL, min(r["rect"][1] for r in rooms) - 2 * CELL,
                             max(r["rect"][2] for r in rooms) + 2 * CELL, max(r["rect"][3] for r in rooms) + 2 * CELL)
    for rect in [r["rect"] for r in rooms] + corridors:
        cells.fill(rect, FLOOR)
    for room in rooms:
        for block in room["blocks"]:
            cells.fill(block, ROCK)
    # Gate i fills the last cell of the corridor into room i + 1, shutting that room off until room i is cleared.
    gates = [(r["rect"][0] - CELL, -DOOR_HALF, r["rect"][0], DOOR_HALF) for r in rooms[1:]]
    return Level("test dungeon", cells, [{"name": r["name"], "rect": r["rect"], "wave": r["wave"]} for r in rooms],
                 gates, _props(rooms), _torches(rooms, corridors), TEST_SHRINE)
