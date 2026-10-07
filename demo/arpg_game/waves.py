import arpg_world as world
from arpg_game import combat, enemies, loot, progression, spatial
from arpg_game.components import Enemy
from scene import add_ball

DEFEAT_S, VICTORY_S, SPAWN_EVERY_S = 6.0, 10.0, 0.35
# Once someone is in the next room, the rest get this long to follow before they're brought along.
STRAGGLE_S = 12.0
# How far inside a room's walls a player must be to count as having entered it.
INSIDE_M = 1.5


class Waves:
    """Intermission -> fight (enemies trickle in) -> cleared -> next wave; everyone down at once is a defeat.
    In a crawl each room is one fight: clearing it opens the next room's gate, its fight starts once everyone is
    through, and clearing the last room wins the run."""

    def __init__(self, g, first_wave, base, step, intermission_s, crawl=False):
        self.g = g
        self.wave, self.phase, self.until = first_wave - 1, "intermission", 0
        self.base, self.step, self.intermission_s = base, step, intermission_s
        self.crawl = crawl
        self.queue, self.next_spawn, self.remaining = [], 0, None
        self.straggle_until = None

    def start(self):
        g = self.g
        # ARPG_FIRST_ROOM starts a crawl further in: the gates behind are open, apart from the one into this room.
        for gate_id in range(world.GATE_BASE, world.GATE_BASE + g.room - 1):
            open_gate(g, gate_id)
        g.state.spawn("game", wave=0, phase="intermission", until=0, remaining=0, room=g.room, crawl=self.crawl)
        self.set_phase("intermission", 3.0)

    def kinds(self, wave):
        if wave % world.BOSS_EVERY_WAVES == 0:
            # The queue pops from the end: the boss arrives first, its escort after.
            return ["imp"] * world.BOSS_ESCORT + ["warlord"]
        count = self.base + self.step * wave
        spitters = round(count * min(0.3, 0.1 * wave)) if wave >= 2 else 0
        brutes = max(1, round(count * min(0.2, 0.05 * (wave - 2)))) if wave >= 3 else 0
        shamans = max(1, round(count * 0.08)) if wave >= 3 else 0
        hounds = max(1, round(count * min(0.2, 0.06 * wave))) if wave >= 2 else 0
        bloaters = max(1, round(count * 0.08)) if wave >= 4 else 0
        shields = 1 + wave // 5 if wave >= 4 else 0
        special = (["spitter"] * spitters + ["brute"] * brutes + ["shaman"] * shamans + ["hound"] * hounds
                   + ["bloater"] * bloaters + ["shieldbearer"] * shields)
        kinds = special + ["imp"] * max(0, count - len(special))
        self.g.rng.shuffle(kinds)
        return kinds

    def set_phase(self, phase, seconds=0.0):
        g = self.g
        self.phase = phase
        self.until = g.park.currentTime + g.ticks_for(seconds) if seconds else 0
        g.state.set("game", wave=self.wave, phase=phase, until=self.until, room=g.room)

    def begin_fight(self, wave):
        g = self.g
        for _, b in g.player_balls():
            g.state.set(b, ready=False)
        self.wave = wave
        self.queue = self.kinds(wave)
        self.set_phase("fight")

    def update(self):
        g = self.g
        tick = g.park.currentTime
        players = g.player_balls()
        if not players:
            return
        alive = [b for _, b in players if g.alive(b)]
        foes = g.ents.of(Enemy)
        everyone_ready = all((g.state.get(b) or {}).get("ready") for b in alive)
        if self.phase == "intermission" and (tick >= self.until or (everyone_ready and (self.wave > 0 or self.crawl))):
            self.begin_fight(world.ROOMS[g.room]["wave"] if self.crawl else self.wave + 1)
        elif self.phase == "fight":
            if self.queue and tick >= self.next_spawn:
                kind = self.queue.pop()
                if enemies.spawn(g, kind) is None:
                    self.queue.append(kind)
                self.next_spawn = tick + g.ticks_for(SPAWN_EVERY_S)
            if not self.queue and not foes:
                self.revive_all()
                self.cleared()
            elif not alive:
                self.queue = []
                for eid in list(foes):
                    combat.kill_enemy(g, eid, None)
                self.set_phase("defeat", DEFEAT_S)
        elif self.phase == "advance":
            self.advance(alive, tick)
        elif self.phase in ("defeat", "victory") and tick >= self.until:
            self.new_run()
        remaining = len(foes) + len(self.queue)
        if remaining != self.remaining:
            self.remaining = remaining
            g.state.set("game", remaining=remaining)

    def cleared(self):
        g = self.g
        if not self.crawl:
            self.set_phase("intermission", self.intermission_s)
        elif g.room + 1 < len(world.ROOMS):
            open_gate(g, world.GATE_BASE + g.room)
            self.straggle_until = None
            self.set_phase("advance")
        else:
            self.set_phase("victory", VICTORY_S)

    def advance(self, alive, tick):
        """Waits for every living player to step into the next room, then shuts its gate behind them and fights."""
        g = self.g
        balls = g.park.balls
        nxt = g.room + 1
        inside = [b for b in alive if world.room_at(balls[b].x, balls[b].z, INSIDE_M) == nxt]
        if not inside:
            return
        if self.straggle_until is None:
            self.straggle_until = tick + g.ticks_for(STRAGGLE_S)
        if len(inside) < len(alive) and tick < self.straggle_until:
            return
        g.room = nxt
        for b in alive:
            if b not in inside:
                progression.place_player(g, b)
        shut_gate(g, world.GATE_BASE + nxt - 1)
        loot.clear(g)
        self.begin_fight(world.ROOMS[nxt]["wave"])

    def new_run(self):
        # A defeat or a won run starts over in the hall at level 1, with every gate shut again.
        g = self.g
        self.wave = 0
        g.room = 0
        loot.clear(g)
        self.revive_all(reset=True)
        for gate_id in world.gate_ids():
            shut_gate(g, gate_id)
        self.set_phase("intermission", 3.0)

    def revive_all(self, reset=False):
        # A new run resets everyone to level 1; clearing a wave only brings the fallen back.
        for _, ball_id in self.g.player_balls():
            if reset or not self.g.alive(ball_id):
                progression.respawn_player(self.g, ball_id, reset)


def open_gate(g, gate_id):
    if gate_id in g.park.balls:
        g.sync.actions.remove_ball(gate_id)
        g.state.event("game", "gate", gate=gate_id, open=True)
    world.sync_gates(g.park)


def shut_gate(g, gate_id):
    if gate_id not in g.park.balls:
        world.add_gate(g.park, add_ball, gate_id)
        g.state.event("game", "gate", gate=gate_id, open=False)
    world.sync_gates(g.park)
