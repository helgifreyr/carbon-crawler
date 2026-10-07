import math
import os

import blue
import destiny

import carbonapp
import netproto
from destinyutil import refresh_time_factors
from netsync import ClientSync
from stats import Samples, TickTimer


def apply_destiny_settings(values):
    # destiny.settings are process-wide and must match the server, or collisions resolve differently.
    if not values:
        return
    config = destiny.settings.Get()
    for name, value in values.items():
        setattr(config, name, value)
    destiny.settings.Apply(config)

# Server clock messages are stamped when sent; by the time one arrives the client should still be at least
# one tick short of it, plus enough margin to absorb frame-granular network jitter.
LEAD_MARGIN_MS = float(os.environ.get("LEAD_MARGIN_MS", "15"))
LEAD_BAND_MS = float(os.environ.get("LEAD_BAND_MS", "10"))
STEER_WINDOW_MS = int(os.environ.get("STEER_WINDOW_MS", "1000"))
PING_EVERY_MS = int(os.environ.get("PING_EVERY_MS", "1000"))


class ClientPark(destiny.Ballpark):
    def DoPreTick(self, stamp):
        self.owner.timer.begin()
        self.owner.sync.pre_tick()

    def DoPostTick(self, stamp):
        self.owner.sync.post_tick(stamp)
        self.owner.timer.end()
        self.owner.after_tick()


class NetClient:
    def __init__(self, host="127.0.0.1", port=netproto.DEFAULT_PORT):
        self.host, self.port = host, port
        self.park = ClientPark()
        self.park.owner = self
        self.sync = ClientSync(park=self.park, on_set_state=self._on_set_state, on_desync=self._on_desync)
        self.peer = None
        self.client_id = self.own_ball = None
        self.tick_ms = None
        self.world = {}
        self.pending_probes = {}
        self.timer = TickTimer()
        self.rtt_ms = Samples(200)
        self.lead_window = (None, None)
        self._last_steer = 0
        self._window_min_lead = None
        self.stats = {"rewinds": 0, "probes": 0, "probe_max_err": 0.0, "probe_missing": 0, "probe_late": 0,
                      "desyncs": 0, "adjust_slower": 0, "adjust_faster": 0, "lead": None, "set_states": 0}
        self._refresh_after_tick = False
        self.tick_listeners = []
        self.message_listeners = []
        self._wrap_rewind_counter()
        carbonapp.spawn(self._run)

    @property
    def connected(self):
        return self.peer is not None and self.peer.alive

    @property
    def synced(self):
        return self.sync.synced

    def send(self, *message):
        if self.connected:
            self.peer.send(message)

    def _wrap_rewind_counter(self):
        original = self.sync.ticker.synchronize_to_simulation_time

        def counted(stamp):
            if stamp < self.park.currentTime:
                self.stats["rewinds"] += 1
            return original(stamp)

        self.sync.ticker.synchronize_to_simulation_time = counted

    def _run(self, retry_ms=1000):
        self.connect_attempts = 0
        while True:
            try:
                sock = netproto.connect(self.host, self.port)
                break
            except (ConnectionRefusedError, TimeoutError, OSError):
                self.connect_attempts += 1
                if self.connect_attempts == 1:
                    print("[client] no server at %s:%d yet - retrying every %.0f s" % (self.host, self.port, retry_ms / 1000.0))
                blue.synchro.SleepWallclock(retry_ms)
        print("[client] connected to %s:%d" % (self.host, self.port))
        self.peer = netproto.Peer(sock, self._on_message, lambda p: print("[client] disconnected"))
        carbonapp.spawn(self._ping_loop)

    def _ping_loop(self):
        while self.connected:
            self.send("ping", blue.os.GetWallclockTimeNow())
            blue.synchro.SleepWallclock(PING_EVERY_MS)

    def _on_message(self, peer, message):
        kind = message[0]
        if kind == "destiny":
            self.sync.receive(message[1:])
        elif kind == "clock":
            self._on_clock(message[1])
        elif kind == "probe":
            self._on_probe(message[1], message[2])
        elif kind == "pong":
            self.rtt_ms.add(blue.os.TimeDiffInUs(message[1], blue.os.GetWallclockTimeNow()) / 1000.0)
        elif kind not in ("hello",):
            for listener in self.message_listeners:
                listener(message)
        if kind == "hello":
            _, self.client_id, self.own_ball, self.tick_ms, server_tick = message[:5]
            self.world = message[5] if len(message) > 5 else {}
            apply_destiny_settings(self.world.get("destiny_settings", {}))
            lo = 1 + int(math.ceil(LEAD_MARGIN_MS / self.tick_ms))
            self.lead_window = (lo, lo + max(1, int(math.ceil(LEAD_BAND_MS / self.tick_ms))))
            self.sync.ticker.max_future_ticks = self.lead_window[1] + 3
            self.sync.ticker.catch_up_backlog = self.lead_window[1] + 1
            self.park.tickInterval = self.tick_ms
            self.park.Start()

    def _on_set_state(self):
        self.stats["set_states"] += 1
        self._rebuild_static_geometry()
        refresh_time_factors(self.park)
        self._refresh_after_tick = True

    def _rebuild_static_geometry(self):
        # Full-state streams don't carry mini-geometry, so rebuild it from the server's world description.
        ball = self.park.balls.get(self.world.get("static_ball"))
        if ball is None or len(ball.miniBoxes):
            return
        height = self.world.get("wall_height", 1.0)
        for x0, z0, x1, z1 in self.world.get("boxes", ()):
            ball.AddMiniBox(x0, -1.0, z0, x1 - x0, 0.0, 0.0, 0.0, height, 0.0, 0.0, 0.0, z1 - z0)

    def _on_desync(self, fatal):
        self.stats["desyncs"] += 1
        self.send("reset")

    def after_tick(self):
        if self._refresh_after_tick:
            refresh_time_factors(self.park)
            self._refresh_after_tick = False
        probe = self.pending_probes.pop(self.park.currentTime, None)
        if probe is not None:
            self._compare(probe)
        for listener in self.tick_listeners:
            listener()

    def _on_clock(self, server_tick):
        if not self.synced:
            return
        lead = server_tick - self.park.currentTime
        self.stats["lead"] = lead
        # Per-sample lead jitters by a few ticks because both ends only see packets once per frame;
        # steer on the worst (smallest) lead seen over a window, since lateness is what triggers rewinds.
        if self._window_min_lead is None or lead < self._window_min_lead:
            self._window_min_lead = lead
        now = blue.os.GetWallclockTimeNow()
        if blue.os.TimeDiffInMs(self._last_steer, now) < STEER_WINDOW_MS:
            return
        worst, self._window_min_lead = self._window_min_lead, None
        self._last_steer = now
        self.stats["min_lead"] = worst
        lo, hi = self.lead_window
        if worst < lo or worst > hi:
            self.park.AdjustTimes(((lo + hi) // 2 - worst) * self.tick_ms * 10000)
            self.stats["adjust_slower" if worst < lo else "adjust_faster"] += 1

    def _on_probe(self, tick, positions):
        if not self.synced:
            return
        if tick <= self.park.currentTime:
            self.stats["probe_late"] += 1
        else:
            self.pending_probes[tick] = positions

    def _compare(self, server_positions):
        worst = 0.0
        for ball_id, pos in server_positions.items():
            ball = self.park.balls.get(ball_id)
            if ball is None:
                self.stats["probe_missing"] += 1
                continue
            worst = max(worst, abs(pos[0] - ball.x), abs(pos[1] - ball.y), abs(pos[2] - ball.z))
        self.stats["probes"] += 1
        self.stats["probe_max_err"] = max(self.stats["probe_max_err"], worst)

    def status(self):
        s = self.stats
        return ("tick %s min lead %s (window %s-%s) rewinds %d probes %d err %.4f m missing %d late %d desyncs %d "
                "adj -/+ %d/%d rtt p50 %.1f ms  client tick p50/p99 %.3f/%.3f ms  balls %d  rx %.1f KB") % (
            self.park.currentTime if self.synced else "-", s.get("min_lead"), self.lead_window[0], self.lead_window[1],
            s["rewinds"], s["probes"], s["probe_max_err"], s["probe_missing"], s["probe_late"], s["desyncs"],
            s["adjust_slower"], s["adjust_faster"], self.rtt_ms.percentile(0.5),
            self.timer.costs_ms.percentile(0.5), self.timer.costs_ms.percentile(0.99), len(self.park.balls),
            (self.peer.bytes_received if self.peer else 0) / 1024.0)
