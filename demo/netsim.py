from collections import deque

import blue

from net_client import NetClient
from scene import COLORS
from sim import Tracked

ANCHOR = 1
ORBIT_RANGE, FOLLOW_RANGE = 150.0, 40.0
# Tasklets run before tick callbacks within a frame, so the newest tick isn't always in yet when drawing.
# Drawing one tick plus one frame (with margin) behind the newest tick always leaves a snapshot on each side.
RENDER_FRAME_MARGIN_MS = 20.0


def render_delay_ticks(tick_ms):
    return 1.0 + RENDER_FRAME_MARGIN_MS / float(tick_ms or 20)
HISTORY_TICKS = 16


class TickTracked(Tracked):
    def __init__(self, name, ball):
        super().__init__(name, ball)
        self.history = deque(maxlen=HISTORY_TICKS)

    def record(self, tick):
        self.snapshot()
        self.history.append((tick, self.cur))

    def position(self, render_tick):
        return position_at(self.history, render_tick, self.cur)


def position_at(history, render_tick, fallback):
    if not history:
        return fallback
    if render_tick <= history[0][0]:
        return history[0][1]
    for (t0, p0), (t1, p1) in zip(history, list(history)[1:]):
        if t0 <= render_tick <= t1:
            f = (render_tick - t0) / float(t1 - t0)
            return tuple(a + (b - a) * f for a, b in zip(p0, p1))
    return history[-1][1]


class NetSim:
    """Same interface as sim.Sim, but the Ballpark is a network client of net_server."""

    def __init__(self, host, port, autoconnect=True):
        self.client = NetClient(host, port, autoconnect=autoconnect)
        self.client.tick_listeners.append(self._on_tick)
        self.tracked_by_id = {}
        self.goto_marker = None
        self.ticked = False
        self._tick_pending = False
        self._render_tick = None
        self._last_frame_time = None
        self.clock_snaps = 0
        self.paused = False

    @property
    def tracked(self):
        return list(self.tracked_by_id.values())

    @property
    def tick(self):
        return self.client.park.currentTime if self.client.synced else 0

    @property
    def selected(self):
        return self.tracked_by_id.get(self.client.own_ball)

    @property
    def alpha(self):
        return self._render_tick if self._render_tick is not None else float(self.tick)

    def advance_render_clock(self):
        if not self.client.synced or not self.client.tick_ms:
            return
        now = blue.os.GetSimTime()
        interval = self.client.tick_ms * 10000.0
        since = max(0.0, (now - self.client.park.time) / interval)
        target = self.client.park.currentTime + since - render_delay_ticks(self.client.tick_ms)
        if self._render_tick is None or abs(target - self._render_tick) > 4.0:
            if self._render_tick is not None:
                self.clock_snaps += 1
            self._render_tick = target
        else:
            self._render_tick += (now - self._last_frame_time) / interval
            self._render_tick += (target - self._render_tick) * 0.1
        self._last_frame_time = now

    def _name_for(self, ball_id):
        if ball_id == ANCHOR:
            return "anchor"
        if ball_id == self.client.own_ball:
            return "you"
        return "ball %d" % ball_id

    def _on_tick(self):
        tick = self.client.park.currentTime
        balls = self.client.park.balls
        for ball_id, ball in balls.items():
            tracked = self.tracked_by_id.get(ball_id)
            if tracked is None:
                tracked = self.tracked_by_id[ball_id] = TickTracked(self._name_for(ball_id), ball)
                tracked.color = COLORS["traveller"] if ball_id == self.client.own_ball else (
                    COLORS.get(tracked.name) or COLORS["follower"])
            tracked.ball = ball
            tracked.record(tick)
        for ball_id in [b for b in self.tracked_by_id if b not in balls]:
            del self.tracked_by_id[ball_id]
        self._tick_pending = True

    def update(self, dt):
        self.ticked, self._tick_pending = self._tick_pending, False
        self.advance_render_clock()

    def goto(self, point):
        self.client.send("goto", *point)
        self.goto_marker = point

    def orbit_anchor(self):
        self.client.send("orbit", ANCHOR, ORBIT_RANGE)
        self.goto_marker = None

    def follow_next(self):
        others = [i for i in self.tracked_by_id if i not in (ANCHOR, self.client.own_ball)]
        if others:
            self.client.send("follow", others[0], FOLLOW_RANGE)
        self.goto_marker = None

    def stop(self):
        self.client.send("stop")
        self.goto_marker = None

    def select_next(self):
        pass

    def faster(self):
        pass

    def slower(self):
        pass

    def toggle_pause(self):
        pass

    def status_lines(self):
        c = self.client
        if not c.synced:
            if c.connected:
                return ["connected to %s:%d, joining ..." % (c.host, c.port), ""]
            return ["waiting for a server at %s:%d (attempt %d) - is %s running?" % (
                c.host, c.port, getattr(c, "connect_attempts", 0), "run_server"), ""]
        s = c.stats
        me = c.park.balls.get(c.own_ball)
        return [
            "net client %s   tick %d (%d ms)   %d behind server   rewinds %d   probe err %.3f m" % (
                c.client_id, c.park.currentTime, c.tick_ms, s["lead"] or 0, s["rewinds"], s["probe_max_err"]),
            "your ball %d  pos (%.0f, %.0f, %.0f)   balls %d   rx %.1f KB" % (
                c.own_ball, me.x if me else 0, me.y if me else 0, me.z if me else 0, len(c.park.balls),
                (c.peer.bytes_received if c.peer else 0) / 1024.0),
        ]

    def close(self):
        pass
