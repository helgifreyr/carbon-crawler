import math

WALL_T, WALL_H, WALL_BASE_Y = 1.0, 3.0, -1.0
PLAYER_RADIUS, ENEMY_RADIUS, PROJECTILE_RADIUS = 0.5, 0.5, 0.25
FLOOR_Y = -PLAYER_RADIUS
# Rooms are joined by corridors along z = 0, DOOR_HALF either side; each room's west doorway holds an iron gate.
DOOR_HALF = 2.0


def _pillars(points, half=1.0):
    return [(x - half, z - half, x + half, z + half) for x, z in points]


# The dungeon, west to east: each room's floor rect (x0, z0, x1, z1), its free-standing walls and pillars, and the wave
# fought in it. The hall is where a run starts; the last room is the Warlord's.
ROOMS = [
    {"name": "The Hall", "rect": (-30.0, -20.0, 30.0, 20.0), "wave": 1,
     "blocks": _pillars([(px, pz) for px in (-18.0, 0.0, 18.0) for pz in (-9.0, 9.0)]) + [(-6.0, -2.0, 6.0, -1.0)]},
    {"name": "The Crypt", "rect": (40.0, -18.0, 76.0, 18.0), "wave": 2,
     "blocks": _pillars([(50.0, -8.0), (50.0, 8.0), (66.0, -8.0), (66.0, 8.0)], 1.2) + [(56.0, -1.0, 60.0, 1.0)]},
    {"name": "The Gallery", "rect": (86.0, -9.0, 146.0, 9.0), "wave": 3,
     "blocks": _pillars([(96.0, -3.5), (106.0, 3.5), (116.0, -3.5), (126.0, 3.5), (136.0, -3.5)], 0.8)},
    {"name": "The Ring", "rect": (156.0, -22.0, 200.0, 22.0), "wave": 4,
     "blocks": [(171.0, -7.0, 185.0, 7.0)] + _pillars([(163.0, -15.0), (163.0, 15.0), (193.0, -15.0), (193.0, 15.0)])},
    {"name": "The Throne Room", "rect": (210.0, -20.0, 260.0, 20.0), "wave": 5,
     "blocks": _pillars([(224.0, -10.0), (224.0, 10.0), (246.0, -10.0), (246.0, 10.0)], 1.2)},
]


def room_at(x, z, margin=0.0):
    """The index of the room whose floor contains (x, z), at least margin in from its walls, or None."""
    for i, room in enumerate(ROOMS):
        x0, z0, x1, z1 = room["rect"]
        if x0 + margin <= x <= x1 - margin and z0 + margin <= z <= z1 - margin:
            return i
    return None


def _walls():
    """Outer walls with doorways, and corridor walls, as (box, outward normal)."""
    t, gap = WALL_T, DOOR_HALF
    walls = []
    for i, room in enumerate(ROOMS):
        x0, z0, x1, z1 = room["rect"]
        walls += [((x0 - t, z0 - t, x1 + t, z0), (0.0, -1.0)), ((x0 - t, z1, x1 + t, z1 + t), (0.0, 1.0))]
        for x, side, door in ((x0 - t, -1.0, i > 0), (x1, 1.0, i < len(ROOMS) - 1)):
            if door:
                walls += [((x, z0, x + t, -gap), (side, 0.0)), ((x, gap, x + t, z1), (side, 0.0))]
            else:
                walls.append(((x, z0, x + t, z1), (side, 0.0)))
        if i < len(ROOMS) - 1:
            nx = ROOMS[i + 1]["rect"][0] - t
            walls += [((x1 + t, -gap - t, nx, -gap), (0.0, -1.0)), ((x1 + t, gap, nx, gap + t), (0.0, 1.0))]
    return walls


_OUTER = _walls()
# Axis-aligned footprints (x0, z0, x1, z1) of every wall; WALL_OUTSIDE[i] is the outward normal of an outer wall, or
# None for the free-standing ones inside a room.
WALL_BOXES = [box for box, _ in _OUTER] + [b for room in ROOMS for b in room["blocks"]]
WALL_OUTSIDE = [normal for _, normal in _OUTER] + [None] * (len(WALL_BOXES) - len(_OUTER))

# Gate i stands in room i + 1's west doorway; it shuts that room off until room i is cleared.
GATES = [(room["rect"][0] - WALL_T, -DOOR_HALF, room["rect"][0], DOOR_HALF) for room in ROOMS[1:]]

# Corridor floors between consecutive rooms, as rects.
CORRIDORS = [(a["rect"][2], -DOOR_HALF, b["rect"][0], DOOR_HALF) for a, b in zip(ROOMS, ROOMS[1:])]


def _props():
    props = []
    for i, room in enumerate(ROOMS):
        x0, z0, x1, z1 = room["rect"]
        for sx, cx in ((-1.0, x0 + 0.5), (1.0, x1 - 0.5)):
            for sz, cz in ((-1.0, z0 + 0.5), (1.0, z1 - 0.5)):
                props += [("crate", cx, cz, 0.3 * sx * sz), ("barrel", cx - sx * 1.35, cz, 0.0),
                          ("barrel", cx, cz - sz * 1.3, 0.0)]
        if i == 0:
            hx, hz = x1, z1
            props += [("barrel", -6.0, -hz + 0.45, 0.0), ("barrel", 6.4, -hz + 0.45, 0.0), ("crate", -18.0, hz - 0.5, 0.15),
                      ("crate", 18.0, hz - 0.5, -0.2), ("barrel", -hx + 0.45, -5.0, 0.0), ("barrel", hx - 0.45, 5.0, 0.0)]
    # The crypt's coffins, end to end along its side walls.
    for x in (46.0, 58.0, 70.0):
        props += [("crate", x - 0.45, -17.4, 0.0), ("crate", x + 0.45, -17.4, 0.0),
                  ("crate", x - 0.45, 17.4, 0.0), ("crate", x + 0.45, 17.4, 0.0)]
    return props


# Props as (kind, x, z, yaw); each blocks a PROP_SIZE square like a short wall.
PROPS = _props()
PROP_SIZE = {"crate": 0.9, "barrel": 0.8}
PROP_BOXES = [(x - PROP_SIZE[k] / 2, z - PROP_SIZE[k] / 2, x + PROP_SIZE[k] / 2, z + PROP_SIZE[k] / 2) for k, x, z, _ in PROPS]


def _torches():
    inset = 0.22
    torches = []
    for room in ROOMS:
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
            if bz1 - bz0 >= 1.6 and bx1 - bx0 <= 2.6:
                torches.append((cx, bz1 + inset, 0.0) if bz0 + bz1 < z0 + z1 else (cx, bz0 - inset, math.pi))
    for cx0, _, cx1, _ in CORRIDORS:
        x = (cx0 + cx1) / 2
        torches += [(x, -DOOR_HALF + inset, 0.0), (x, DOOR_HALF - inset, math.pi)]
    return torches


# Wall torches as (x, z, yaw): yaw turns the torch's front (+Z) away from the wall it hangs on.
TORCHES = _torches()
TORCH_Y = 1.25

# Everything the dungeon covers, rooms and walls included.
BOUNDS = (min(r["rect"][0] for r in ROOMS) - 2.0, min(r["rect"][1] for r in ROOMS) - 2.0,
          max(r["rect"][2] for r in ROOMS) + 2.0, max(r["rect"][3] for r in ROOMS) + 2.0)
# The baked torch light covers this floor rectangle (x0, z0, x1, z1) at LIGHTMAP_PX_PER_M.
LIGHTMAP_RECT = BOUNDS
LIGHTMAP_PX_PER_M = 4

# The shrine players visit before the first fight to spend upgrades and ready up; it stands clear of the centre wall.
SHRINE = (0.0, 5.0)
SHRINE_RANGE = 3.0
SHRINE_HALF = 0.55
# Everything that collides, apart from the gates; collision boxes stand WALL_H tall from WALL_BASE_Y.
BOXES = WALL_BOXES + PROP_BOXES + [(SHRINE[0] - SHRINE_HALF, SHRINE[1] - SHRINE_HALF,
                                   SHRINE[0] + SHRINE_HALF, SHRINE[1] + SHRINE_HALF)]
