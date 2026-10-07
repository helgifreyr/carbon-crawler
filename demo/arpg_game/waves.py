import arpg_world as world
from arpg_game import combat, enemies, loot, progression
from arpg_game.components import Enemy

DEFEAT_S, SPAWN_EVERY_S = 6.0, 0.35


class Waves:
    """Intermission -> fight (enemies trickle in) -> cleared -> next wave; everyone down at once is a defeat."""

    def __init__(self, g, first_wave, base, step, intermission_s):
        self.g = g
        self.wave, self.phase, self.until = first_wave - 1, "intermission", 0
        self.base, self.step, self.intermission_s = base, step, intermission_s
        self.queue, self.next_spawn, self.remaining = [], 0, None

    def start(self):
        self.g.state.spawn("game", wave=0, phase="intermission", until=0, remaining=0)
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
        g.state.set("game", wave=self.wave, phase=phase, until=self.until)

    def update(self):
        g = self.g
        tick = g.park.currentTime
        players = g.player_balls()
        if not players:
            return
        alive = [b for _, b in players if g.alive(b)]
        foes = g.ents.of(Enemy)
        everyone_ready = all((g.state.get(b) or {}).get("ready") for b in alive)
        if self.phase == "intermission" and (tick >= self.until or (everyone_ready and self.wave > 0)):
            for _, b in players:
                g.state.set(b, ready=False)
            self.wave += 1
            self.queue = self.kinds(self.wave)
            self.set_phase("fight")
        elif self.phase == "fight":
            if self.queue and tick >= self.next_spawn:
                kind = self.queue.pop()
                if enemies.spawn(g, kind) is None:
                    self.queue.append(kind)
                self.next_spawn = tick + g.ticks_for(SPAWN_EVERY_S)
            if not self.queue and not foes:
                self.revive_all()
                self.set_phase("intermission", self.intermission_s)
            elif not alive:
                self.queue = []
                for eid in list(foes):
                    combat.kill_enemy(g, eid, None)
                self.set_phase("defeat", DEFEAT_S)
        elif self.phase == "defeat" and tick >= self.until:
            self.wave = 0
            loot.clear(g)
            self.revive_all(reset=True)
            self.set_phase("intermission", 3.0)
        remaining = len(foes) + len(self.queue)
        if remaining != self.remaining:
            self.remaining = remaining
            g.state.set("game", remaining=remaining)

    def revive_all(self, reset=False):
        # A defeat resets everyone to level 1; clearing a wave only brings the fallen back.
        for _, ball_id in self.g.player_balls():
            if reset or not self.g.alive(ball_id):
                progression.respawn_player(self.g, ball_id, reset)
