from collections import deque

import destiny
from scene import build_scene

TRAIL_LENGTH = 400
TICK_RATES = [0.5, 1, 2, 4, 8, 16, 32]
ORBIT_RANGE = 150.0


class Tracked:
    def __init__(self, name, ball):
        self.name = name
        self.ball = ball
        self.prev = self.cur = (ball.x, ball.y, ball.z)
        self.trail = deque(maxlen=TRAIL_LENGTH)

    def snapshot(self):
        self.prev = self.cur
        self.cur = (self.ball.x, self.ball.y, self.ball.z)
        self.trail.append(self.cur)

    def position(self, alpha):
        return tuple(p + (c - p) * alpha for p, c in zip(self.prev, self.cur))


class Sim:
    def __init__(self):
        self.park = destiny.Ballpark()
        self.tracked = [Tracked(name, ball) for name, ball in build_scene(self.park).items()]
        self.anchor = self.tracked[0]
        self.movable = [t for t in self.tracked if t.ball.maxVelocity > 0]
        self.selected_index = 0
        self.rate_index = TICK_RATES.index(4)
        self.paused = False
        self.accumulator = 0.0
        self.tick = 0
        self.goto_marker = None
        self.ticked = False

    @property
    def selected(self):
        return self.movable[self.selected_index]

    @property
    def tick_rate(self):
        return TICK_RATES[self.rate_index]

    @property
    def alpha(self):
        return min(1.0, self.accumulator * self.tick_rate)

    def update(self, dt):
        self.ticked = False
        if self.paused:
            return
        tick_seconds = 1.0 / self.tick_rate
        self.accumulator += dt
        while self.accumulator >= tick_seconds:
            self.park.Evolve()
            for t in self.tracked:
                t.snapshot()
            self.tick += 1
            self.accumulator -= tick_seconds
            self.ticked = True

    def select_next(self):
        self.selected_index = (self.selected_index + 1) % len(self.movable)

    def faster(self):
        self.rate_index = min(len(TICK_RATES) - 1, self.rate_index + 1)

    def slower(self):
        self.rate_index = max(0, self.rate_index - 1)

    def toggle_pause(self):
        self.paused = not self.paused

    def goto(self, point):
        self.park.GotoPoint(self.selected.ball.id, *point)
        self.goto_marker = point

    def orbit_anchor(self):
        self.park.Orbit(self.selected.ball.id, self.anchor.ball.id, ORBIT_RANGE)
        self.goto_marker = None

    def follow_next(self):
        target = self.movable[(self.selected_index + 1) % len(self.movable)]
        self.park.FollowBall(self.selected.ball.id, target.ball.id)
        self.goto_marker = None

    def stop(self):
        self.park.Stop(self.selected.ball.id)
        self.goto_marker = None

    def status_lines(self):
        b = self.selected.ball
        speed = (b.vx ** 2 + b.vy ** 2 + b.vz ** 2) ** 0.5
        return [
            "tick %d   %s ticks/s%s" % (self.tick, self.tick_rate, "   PAUSED" if self.paused else ""),
            "selected: %s   pos (%.0f, %.0f, %.0f)   speed %.1f / %.1f m/s" % (
                self.selected.name, b.x, b.y, b.z, speed, b.maxVelocity),
        ]

    def close(self):
        self.park.ClearAll()
