import arpg_world as world
from arpg_game.components import Enemy

CELL = 2.0


class EnemyGrid:
    """Enemy positions bucketed into CELL-sized squares, rebuilt each tick for contact and projectile tests."""

    def __init__(self, g):
        self.cells, balls = {}, g.park.balls
        for eid in g.ents.of(Enemy):
            e = balls.get(eid)
            if e is not None:
                self.cells.setdefault((int(e.x // CELL), int(e.z // CELL)), []).append((eid, e.x, e.z, e.radius))

    def around(self, x, z):
        gx, gz = int(x // CELL), int(z // CELL)
        for cx in (gx - 1, gx, gx + 1):
            for cz in (gz - 1, gz, gz + 1):
                yield from self.cells.get((cx, cz), ())

    def first_hit(self, ax, az, bx, bz, radius, skip=()):
        """The enemy a circle of radius sweeping from a to b touches first, or None."""
        seg_x, seg_z = bx - ax, bz - az
        seg_len2 = seg_x * seg_x + seg_z * seg_z or 1e-9
        best, best_t = None, 2.0
        for gx in range(int(min(ax, bx) // CELL) - 1, int(max(ax, bx) // CELL) + 2):
            for gz in range(int(min(az, bz) // CELL) - 1, int(max(az, bz) // CELL) + 2):
                for eid, ex, ez, er in self.cells.get((gx, gz), ()):
                    if eid in skip:
                        continue
                    t = max(0.0, min(1.0, ((ex - ax) * seg_x + (ez - az) * seg_z) / seg_len2))
                    cx, cz = ax + seg_x * t - ex, az + seg_z * t - ez
                    reach = radius + er
                    if cx * cx + cz * cz <= reach * reach and t < best_t:
                        best, best_t = eid, t
        return best


def room_area(g, inset=2.0):
    """The current room's floor (or an act's whole extent), inset from its walls, as (x0, z0, x1, z1)."""
    x0, z0, x1, z1 = world.BOUNDS if getattr(g, "act", None) is not None else world.room_rect(g.room)
    return x0 + inset, z0 + inset, x1 - inset, z1 - inset


def entry_area(g):
    """Where players arrive: around the last checkpoint in an act, else just inside the current room's west wall."""
    if getattr(g, "act", None) is not None:
        x, z = g.act.arrival()
        return x - 3.0, z - 3.0, x + 3.0, z + 3.0
    x0, z0, _, z1 = world.room_rect(g.room)
    return x0 + 2.0, max(z0 + 2.0, -6.0), x0 + 8.0, min(z1 - 2.0, 6.0)


def clamp_to_room(g, x, z, inset=1.0):
    x0, z0, x1, z1 = room_area(g, inset)
    return max(x0, min(x1, x)), max(z0, min(z1, z))


def free_spot(g, area, min_player_distance=0.0, min_gap=1.5, attempts=300):
    """A random floor point in area (x0, z0, x1, z1) clear of walls, other massive balls and (optionally) players."""
    balls = g.park.balls
    players = g.player_balls()
    for _ in range(attempts):
        x = g.rng.uniform(area[0], area[2])
        z = g.rng.uniform(area[1], area[3])
        if world.inside_box(x, z, pad=1.0):
            continue
        if any((b.x - x) ** 2 + (b.z - z) ** 2 < min_gap ** 2 for b in balls.values() if b.isMassive):
            continue
        if any((balls[b].x - x) ** 2 + (balls[b].z - z) ** 2 < min_player_distance ** 2 for _, b in players):
            continue
        return x, z
    return None
