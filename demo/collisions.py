import math
from collections import defaultdict

NEIGHBOURS = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]


class ContactCorrections:
    """Server side: replicate the authoritative state of balls that touched another ball this tick.

    Collision outcomes depend on park-local history, so clients can't be trusted to reproduce them.
    Destiny only raises DoCollision for missiles, so contacts are found here with a spatial hash."""

    def __init__(self, park, actions, margin=1.0, static_boxes=(), sustained_every_ticks=1, static_near=None):
        self.park = park
        self.actions = actions
        self.margin = margin
        # A new contact is corrected at once; a contact that persists only every N ticks after that.
        self.sustained_every_ticks = max(1, sustained_every_ticks)
        self._touching_before = set()
        self._last_corrected = {}
        # Axis-aligned footprints (x0, z0, x1, z1) of static geometry; contact with them is corrected too.
        self.static_boxes = list(static_boxes)
        # Or static_near(x, z, reach): the boxes that may lie within reach of (x, z), for geometry that changes or is large.
        self.static_near = static_near or (lambda x, z, reach: self.static_boxes)
        self.watched = set()
        self.contacts = 0
        self.corrections = 0

    def watch(self, ball_id):
        self.watched.add(ball_id)

    def unwatch(self, ball_id):
        self.watched.discard(ball_id)

    def _snapshot(self):
        balls = self.park.balls
        dt = self.park.tickInterval / 1000.0
        rows = []
        for ball_id in list(self.watched):
            b = balls.get(ball_id)
            if b is None:
                self.watched.discard(ball_id)
                continue
            reach = b.radius + math.sqrt(b.vx * b.vx + b.vy * b.vy + b.vz * b.vz) * dt
            rows.append((ball_id, b.x, b.y, b.z, reach, b.isFree))
        return rows

    def _static_contacts(self, rows, touching):
        for ball_id, x, _y, z, reach, is_free in rows:
            if not is_free:
                continue
            limit = reach + self.margin
            for x0, z0, x1, z1 in self.static_near(x, z, limit):
                dx = max(x0 - x, 0.0, x - x1)
                dz = max(z0 - z, 0.0, z - z1)
                if dx * dx + dz * dz < limit * limit:
                    self.contacts += 1
                    touching.add(ball_id)
                    break

    def find_contacts(self):
        rows = self._snapshot()
        touching = set()
        self._static_contacts(rows, touching)
        if len(rows) < 2:
            return touching
        cell = 2.0 * max(r[4] for r in rows) + self.margin
        grid = defaultdict(list)
        for row in rows:
            grid[(int(row[1] // cell), int(row[2] // cell), int(row[3] // cell))].append(row)
        for (cx, cy, cz), members in grid.items():
            for dx, dy, dz in NEIGHBOURS:
                others = grid.get((cx + dx, cy + dy, cz + dz))
                if not others:
                    continue
                for a in members:
                    for b in others:
                        if a[0] >= b[0]:
                            continue
                        limit = a[4] + b[4] + self.margin
                        ddx, ddy, ddz = a[1] - b[1], a[2] - b[2], a[3] - b[3]
                        if ddx * ddx + ddy * ddy + ddz * ddz < limit * limit:
                            self.contacts += 1
                            if a[5]:
                                touching.add(a[0])
                            if b[5]:
                                touching.add(b[0])
        return touching

    def flush(self):
        balls = self.park.balls
        tick = self.park.currentTime
        touching = self.find_contacts()
        for ball_id in touching:
            if ball_id in self._touching_before:
                if tick - self._last_corrected.get(ball_id, -10 ** 9) < self.sustained_every_ticks:
                    continue
            b = balls[ball_id]
            self.actions.set_ball_position(ball_id, b.x, b.y, b.z)
            self.actions.set_ball_velocity(ball_id, b.vx, b.vy, b.vz)
            self._last_corrected[ball_id] = tick
            self.corrections += 1
        for ball_id in self._touching_before - touching:
            self._last_corrected.pop(ball_id, None)
        self._touching_before = touching
