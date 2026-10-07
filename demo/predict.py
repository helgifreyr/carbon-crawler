import itertools
import math

import blue
import destiny

import carbonapp
import arpg_world as world
from destinyutil import refresh_time_factors
from netsim import position_at, render_delay_ticks
from scene import add_ball
from stats import Samples

LEAD_EASE = 0.02
CORRECTION_TAU_S = 0.1
EXTRA_STEPS = 3
SNAP_M = 2.0


class OwnBallPredictor:
    """Draws the client's own ball a fixed K ticks ahead of the render clock so input shows at once.

    Each authoritative tick it rebases on the server state and replays inputs the server hasn't applied yet;
    any jump that causes at the displayed time becomes an offset that fades out instead of a snap."""

    def __init__(self, client):
        self.client = client
        self.enabled = True
        self.ready = False
        self.park = None
        self.seq = itertools.count(1)
        self.lead_samples = Samples(50)
        self.error_m = Samples(500)
        self.correction_m = Samples(500)
        self.reset()

    def reset(self):
        self.pending = []
        self.confirmed = ("stop",)
        self.steps = []
        self.cur = None
        self.predicted_at = {}
        self.display_lead = None
        self.offset = (0.0, 0.0, 0.0)
        self._offset_time = None
        self._render_tick = None
        self.roll = None

    @property
    def ahead_ticks(self):
        return self.display_lead or 0.0

    def _ensure_park(self):
        if self.park is not None:
            return self.ready
        if not self.client.synced:
            return False
        park = destiny.Ballpark()
        park.tickInterval = self.client.tick_ms
        world.add_room(park, add_ball)
        add_ball(park, self.client.own_ball, radius=world.PLAYER_RADIUS, max_velocity=world.PLAYER_SPEED,
                 agility=world.PLAYER_AGILITY)
        self.park = park
        carbonapp.spawn(self._settle_dt)
        return False

    def _settle_dt(self):
        # A park's dt only picks up tickInterval on its first real tick; run one, then drive it by hand.
        self.park.Start()
        while self.park.currentTime < 1:
            blue.synchro.Yield()
        self.park.Pause()
        refresh_time_factors(self.park)
        self.ready = True

    def target_lead(self):
        if len(self.lead_samples):
            return self.lead_samples.percentile(0.5)
        rtt = self.client.rtt_ms.percentile(0.5)
        rtt = 30.0 if math.isnan(rtt) else rtt
        return (self.client.lead_window[1] or 3) + rtt / 2.0 / (self.client.tick_ms or 20) + 1

    def send(self, *command):
        seq = next(self.seq)
        tick = self.client.park.currentTime
        estimate = tick + int(round(self.display_lead if self.display_lead is not None else self.target_lead()))
        self.pending.append({"seq": seq, "command": command, "sent_tick": tick, "stamp": estimate, "acked": False})
        if command[0] == "roll":
            self.roll = (estimate, estimate + self.roll_ticks())
        self.client.send(*(command + (seq,)))
        self.rebuild()

    def on_ack(self, seq, stamp):
        for entry in self.pending:
            if entry["seq"] == seq:
                entry["stamp"], entry["acked"] = stamp, True
                if entry["command"][0] == "roll":
                    self.roll = (stamp, stamp + self.roll_ticks())
                self.lead_samples.add(stamp - entry["sent_tick"])
                return

    def on_authoritative_tick(self):
        tick = self.client.park.currentTime
        applied = [e for e in self.pending if e["acked"] and e["stamp"] < tick]
        if applied:
            # A blink is a one-off jump, not a movement mode, so it never becomes the command replayed each rebuild.
            modes = [("dir",) + e["command"][1:3] if e["command"][0] == "roll" else e["command"]
                     for e in applied if e["command"][0] != "blink"]
            if modes:
                self.confirmed = modes[-1]
            self.pending = [e for e in self.pending if e not in applied]
        ball = self.client.park.balls.get(self.client.own_ball)
        predicted = self.predicted_at.pop(tick, None)
        if predicted is not None and ball is not None:
            self.error_m.add(math.hypot(predicted[0] - ball.x, predicted[2] - ball.z))
        for old in [t for t in self.predicted_at if t < tick]:
            del self.predicted_at[old]
        target = self.target_lead()
        if self.display_lead is None:
            self.display_lead = target
        else:
            self.display_lead += (target - self.display_lead) * LEAD_EASE
        self.rebuild()

    def roll_ticks(self):
        return max(1, int(round(world.ROLL["s"] * 1000.0 / (self.client.tick_ms or 10))))

    def _apply(self, command):
        own = self.client.own_ball
        kind = command[0]
        if kind == "dir":
            self.park.GotoDirection(own, command[1], 0.0, command[2])
        elif kind == "goto":
            self.park.GotoPoint(own, command[1], 0.0, command[3])
        elif kind == "stop":
            self.park.Stop(own)
        elif kind == "blink":
            self.park.SetBallPosition(own, command[1], 0.0, command[2])
        elif kind == "roll":
            self.park.balls[own].maxVelocity = world.ROLL["speed"]
            self.park.GotoDirection(own, command[1], 0.0, command[2])

    def _display_tick(self, render_tick):
        return render_tick + render_delay_ticks(self.client.tick_ms) + (self.display_lead or 0.0)

    def rebuild(self):
        if not self.enabled or not self._ensure_park() or self.display_lead is None:
            return
        source = self.client.park.balls.get(self.client.own_ball)
        if source is None:
            return
        own = self.client.own_ball
        tick = self.client.park.currentTime
        count = int(math.ceil(self.display_lead)) + EXTRA_STEPS
        self.park.SetBallPosition(own, source.x, source.y, source.z)
        self.park.SetBallVelocity(own, source.vx, source.vy, source.vz)
        ball = self.park.balls[own]
        ball.maxVelocity = source.maxVelocity
        self._apply(self.confirmed)
        # The server holds movement sent during a roll until it ends, so the replay does the same.
        start, end = self.roll or (None, None)
        if end is not None and end < tick:
            self.roll = start = end = None
        steps = [(tick, (ball.x, ball.y, ball.z))]
        for step in range(count):
            now_tick = tick + step
            if now_tick == end:
                ball.maxVelocity = world.PLAYER_SPEED
            for entry in self.pending:
                due = max(entry["stamp"], tick)
                if start is not None and entry["command"][0] in ("goto", "dir", "stop") and start <= due <= end:
                    due = end + 1
                if due == now_tick or (step == count - 1 and due > now_tick):
                    self._apply(entry["command"])
            self.park.Evolve()
            steps.append((now_tick + 1, (ball.x, ball.y, ball.z)))
        if self.steps and self._render_tick is not None:
            shown_tick = self._display_tick(self._render_tick)
            before = position_at(self.steps, shown_tick, self.steps[-1][1])
            after = position_at(steps, shown_tick, steps[-1][1])
            jump = tuple(b - a for a, b in zip(after, before))
            size = math.hypot(jump[0], jump[2])
            self.correction_m.add(size)
            # Smoothing is for small disagreements; a teleport (a blink, or a blink landing a tick later) snaps.
            self.offset = (0.0, 0.0, 0.0) if size > SNAP_M else tuple(o + j for o, j in zip(self.offset, jump))
        self.steps, self.cur = steps, steps[-1][1]
        self.predicted_at[tick + int(round(self.display_lead))] = position_at(steps, tick + round(self.display_lead), self.cur)

    def position(self, render_tick):
        if self.cur is None or not self.steps:
            return None
        self._render_tick = render_tick
        now = blue.os.GetSimTime()
        if self._offset_time is not None:
            decay = math.exp(-((now - self._offset_time) / 1e7) / CORRECTION_TAU_S)
            self.offset = tuple(o * decay for o in self.offset)
        self._offset_time = now
        base = position_at(self.steps, self._display_tick(render_tick), self.cur)
        return tuple(b + o for b, o in zip(base, self.offset))

    def velocity(self):
        if self.park is None or not self.ready:
            return None
        ball = self.park.balls.get(self.client.own_ball)
        return (ball.vx, ball.vz) if ball is not None else None
