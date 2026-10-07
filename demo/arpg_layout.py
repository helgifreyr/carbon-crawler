import math

ROOM_W, ROOM_D = 60.0, 40.0
WALL_T, WALL_H, WALL_BASE_Y = 1.0, 3.0, -1.0
PLAYER_RADIUS, ENEMY_RADIUS, PROJECTILE_RADIUS = 0.5, 0.5, 0.25
FLOOR_Y = -PLAYER_RADIUS


def _walls():
    hx, hz, t = ROOM_W / 2, ROOM_D / 2, WALL_T
    boxes = [
        (-hx - t, -hz - t, hx + t, -hz),
        (-hx - t, hz, hx + t, hz + t),
        (-hx - t, -hz, -hx, hz),
        (hx, -hz, hx + t, hz),
    ]
    for px in (-18.0, 0.0, 18.0):
        for pz in (-9.0, 9.0):
            boxes.append((px - 1.0, pz - 1.0, px + 1.0, pz + 1.0))
    boxes.append((-6.0, -2.0, 6.0, -1.0))
    return boxes


# Axis-aligned footprints (x0, z0, x1, z1); the first four are the outer walls.
WALL_BOXES = _walls()


def _props():
    hx, hz = ROOM_W / 2, ROOM_D / 2
    props = []
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            cx, cz = sx * (hx - 0.5), sz * (hz - 0.5)
            props += [("crate", cx, cz, 0.3 * sx * sz), ("barrel", cx - sx * 1.35, cz, 0.0),
                      ("barrel", cx, cz - sz * 1.3, 0.0)]
    props += [("barrel", -6.0, -hz + 0.45, 0.0), ("barrel", 6.4, -hz + 0.45, 0.0), ("crate", -18.0, hz - 0.5, 0.15),
              ("crate", 18.0, hz - 0.5, -0.2), ("barrel", -hx + 0.45, -5.0, 0.0), ("barrel", hx - 0.45, 5.0, 0.0)]
    return props


# Props as (kind, x, z, yaw); each blocks a PROP_SIZE square like a short wall.
PROPS = _props()
PROP_SIZE = {"crate": 0.9, "barrel": 0.8}
PROP_BOXES = [(x - PROP_SIZE[k] / 2, z - PROP_SIZE[k] / 2, x + PROP_SIZE[k] / 2, z + PROP_SIZE[k] / 2) for k, x, z, _ in PROPS]


def _torches():
    hx, hz, inset = ROOM_W / 2, ROOM_D / 2, 0.22
    torches = []
    for x in (-24.0, -12.0, 0.0, 12.0, 24.0):
        torches += [(x, -hz + inset, 0.0), (x, hz - inset, math.pi)]
    for z in (-10.0, 0.0, 10.0):
        torches += [(-hx + inset, z, math.pi / 2), (hx - inset, z, -math.pi / 2)]
    for px in (-18.0, 0.0, 18.0):
        torches += [(px, -8.0 + inset, 0.0), (px, 8.0 - inset, math.pi)]
    return torches


# Wall torches as (x, z, yaw): yaw turns the torch's front (+Z) away from the wall it hangs on.
TORCHES = _torches()
TORCH_Y = 1.25
# The baked torch light covers this floor rectangle (x0, z0, x1, z1) at LIGHTMAP_PX_PER_M.
LIGHTMAP_RECT = (-32.0, -22.0, 32.0, 22.0)
LIGHTMAP_PX_PER_M = 4

# The shrine players visit between waves to spend upgrades and ready up; it stands clear of the centre wall.
SHRINE = (0.0, 5.0)
SHRINE_RANGE = 3.0
SHRINE_HALF = 0.55
# Everything that collides; collision boxes stand WALL_H tall from WALL_BASE_Y.
BOXES = WALL_BOXES + PROP_BOXES + [(SHRINE[0] - SHRINE_HALF, SHRINE[1] - SHRINE_HALF,
                                   SHRINE[0] + SHRINE_HALF, SHRINE[1] + SHRINE_HALF)]
