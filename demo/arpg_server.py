import itertools
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import blue
import destiny

import arpg_world as world
from arpg_game import combat, enemies, loot, progression, projectiles, spatial, spells
from arpg_game import movement as move
from arpg_game.components import Enemy, Enrage, Player, Projectile
from arpg_game.entities import Entities
from arpg_game.waves import Waves
from arpg_state import ServerState
import carbonapp
import netproto
from collisions import ContactCorrections
from destinyutil import refresh_time_factors
from netsync import ServerSync
from scene import add_ball
from stats import Samples, TickTimer

TICK_MS = int(os.environ.get("TICK_MS", "10"))
PORT = int(os.environ.get("NET_PORT", netproto.DEFAULT_PORT))
ENEMIES = int(os.environ.get("ENEMIES", "40"))
AGGRO_RANGE = float(os.environ.get("AGGRO_RANGE", "25"))
RESPAWN_S = float(os.environ.get("RESPAWN_S", "3"))
SUSTAINED_EVERY = int(os.environ.get("SUSTAINED_CORRECT_EVERY", "15"))
CORRECT_COLLISIONS = os.environ.get("CORRECT_COLLISIONS", "1") == "1"
CLOCK_EVERY_MS, PROBE_EVERY_MS, PROBE_BALLS = 50, 500, 32
RUN_SECONDS = float(os.environ.get("SERVER_RUN_SECONDS", "0"))
MODE = os.environ.get("ARPG_MODE", "waves")
TEST_PICKS = int(os.environ.get("ARPG_TEST_PICKS", "0"))
TEST_UPGRADES = {k: int(v) for k, v in (p.split(":") for p in os.environ.get("ARPG_TEST_UPGRADES", "").split(",") if p)}
INTERMISSION_S = float(os.environ.get("INTERMISSION_S", "30"))
WAVE_AGGRO_RANGE = 200.0
WAVE_BASE, WAVE_STEP = (int(v) for v in os.environ.get("WAVE_SIZE", "8,4").split(","))
SPELL_MESSAGES = {"cast": "bolt", "nova": "nova", "chain": "chain", "meteor": "meteor", "frost": "frost"}
ENEMY_MIX = [(k, float(w)) for k, w in (part.split(":") for part in
             os.environ.get("ENEMY_MIX", "imp:0.6,spitter:0.25,brute:0.15").split(","))]


class ServerPark(destiny.Ballpark):
    def DoPreTick(self, stamp):
        game.timer.begin()
        game.sync.pre_tick()
        game.phase_mark = time.perf_counter()

    def DoPostTick(self, stamp):
        marks = [time.perf_counter()]
        game.sync.post_tick()
        game.after_tick()
        marks.append(time.perf_counter())
        if CORRECT_COLLISIONS:
            game.corrections.flush()
        marks.append(time.perf_counter())
        game.state.flush(game.broadcast, game.park.currentTime)
        marks.append(time.perf_counter())
        game.timer.end()
        for name, begin, end in zip(("evolve", "game", "corrections", "state"), [game.phase_mark] + marks, marks):
            game.phases[name].add((end - begin) * 1000.0)
        game.ticks += 1


class ArpgServer:
    """Networking, message routing and the tick: the game itself lives in arpg_game's components and systems."""

    def __init__(self):
        world.apply_settings()
        self.park = ServerPark()
        self.park.tickInterval = TICK_MS
        self.sync = ServerSync(self.park, self._send)
        self.corrections = ContactCorrections(self.park, self.sync.actions, margin=0.1, static_boxes=world.BOXES,
                                              sustained_every_ticks=SUSTAINED_EVERY)
        self.rng = random.Random(11)
        self.mode, self.respawn_s = MODE, RESPAWN_S
        self.ents = Entities()
        self.state = ServerState(TICK_MS / 1000.0)
        self.waves = Waves(self, int(os.environ.get("ARPG_FIRST_WAVE", "1")), WAVE_BASE, WAVE_STEP, INTERMISSION_S)
        self.peers = {}
        self.client_ids = itertools.count(1)
        self.respawns = []
        self.kills = {}
        self.loot_stats = {"dropped": 0, "picked": 0, "levelups": 0}
        self.stats = {"rolls": 0, "dodged": 0, "jumps": 0, "jumped": 0, "mends": 0, "charges": 0, "charge_hits": 0,
                      "stuns": 0, "bursts": 0}
        self.shots = {k: 0 for k in ('received', 'no_mana', 'dead', 'spawned', 'hit', 'wall', 'expired')}
        self.ticks = 0
        self.timer = TickTimer()
        self.phases = {name: Samples(500) for name in ("evolve", "game", "corrections", "state")}
        self.phase_mark = 0.0
        world.add_room(self.park, add_ball)

    def broadcast(self, message):
        for peer in list(self.peers.values()):
            peer.send(message)

    def _send(self, client_ids, message):
        for client_id in client_ids:
            peer = self.peers.get(client_id)
            if peer:
                peer.send(("destiny",) + message)

    def player_balls(self):
        return [(c, b) for c, b in self.sync.players.ball_for_client.items() if b in self.park.balls]

    def alive(self, ball_id):
        entity = self.state.get(ball_id)
        return entity is not None and not entity.get("dead")

    def alive_players(self):
        balls = self.park.balls
        return [balls[b] for _, b in self.player_balls() if self.alive(b)]

    def ticks_for(self, seconds):
        return max(1, int(round(seconds * 1000.0 / TICK_MS)))

    def pick_kind(self):
        roll = self.rng.random() * sum(w for _, w in ENEMY_MIX)
        for kind, weight in ENEMY_MIX:
            roll -= weight
            if roll <= 0:
                return kind
        return ENEMY_MIX[-1][0]

    def on_connect(self, sock, address):
        client_id = next(self.client_ids)
        ball_id = world.PLAYER_BASE + client_id
        peer = netproto.Peer(sock, lambda p, msg: self.on_message(client_id, msg),
                             lambda p: self.on_disconnect(client_id))
        self.peers[client_id] = peer
        x, z = spatial.free_spot(self, (-world.ROOM_W / 2 + 2, -world.ROOM_W / 2 + 8), min_gap=2.0) or (-25.0, 0.0)
        add_ball(self.park, ball_id, x=x, z=z, radius=world.PLAYER_RADIUS, max_velocity=world.PLAYER_SPEED,
                 agility=world.PLAYER_AGILITY, is_interactive=True)
        self.corrections.watch(ball_id)
        self.kills[client_id] = 0
        self.ents.add(ball_id, Player(client_id, (x, z)))
        self.state.spawn(ball_id, **progression.fresh_player_state(self, upgrades=TEST_UPGRADES, picks=TEST_PICKS))
        self.sync.join(client_id, ball_id)
        if os.environ.get("LOOT_TEST") == "1":
            loot.drop(self, x + 0.3, z, world.KINDS["brute"])
        peer.send(("hello", client_id, ball_id, TICK_MS, self.park.currentTime, world.world_description()))
        peer.send(("state_full", self.park.currentTime, self.state.snapshot()))
        print("client %d connected from %s:%d -> ball %d" % ((client_id,) + address + (ball_id,)))

    def on_disconnect(self, client_id):
        self.peers.pop(client_id, None)
        ball_id = self.sync.players.ball_for_client.get(client_id)
        self.sync.leave(client_id)
        self.kills.pop(client_id, None)
        if ball_id is not None:
            self.ents.destroy(ball_id)
            self.state.remove(ball_id)
        if ball_id is not None and ball_id in self.park.balls:
            self.corrections.unwatch(ball_id)
            self.sync.actions.remove_ball(ball_id)
        print("client %d disconnected" % client_id)

    def on_message(self, client_id, message):
        kind = message[0]
        peer = self.peers.get(client_id)
        if kind == "ping":
            if peer:
                peer.send(("pong",) + message[1:])
            return
        ball_id = self.sync.players.ball_for_client.get(client_id)
        if ball_id is None or ball_id not in self.park.balls:
            return
        if kind == "reset":
            self.sync.join(client_id, ball_id)
            return
        if kind == "cast":
            self.shots["received"] += 1
        if not self.alive(ball_id):
            if kind == "cast":
                self.shots["dead"] += 1
            return
        movement = {"goto": 4, "dir": 3, "stop": 1, "blink": 3, "roll": 3}
        if kind in movement:
            stamp = self.sync.actions._stamp_for_system
            if kind in move.MOVES:
                stamp = move.move(self, ball_id, message[:movement[kind]])
            elif kind == "blink":
                spells.cast(self, client_id, ball_id, "blink", message[1], message[2])
            else:
                move.roll(self, ball_id, message[1], message[2])
            if len(message) > movement[kind] and peer:
                # Commands received between ticks are stamped with the tick they'll be applied on.
                peer.send(("ack", message[movement[kind]], stamp))
        elif kind in SPELL_MESSAGES:
            spells.cast(self, client_id, ball_id, SPELL_MESSAGES[kind], *message[1:3])
        elif kind == "jump":
            move.jump(self, ball_id)
        elif kind == "pick":
            progression.pick_upgrade(self, ball_id, int(message[1]))
        elif kind == "ready":
            self.state.set(ball_id, ready=bool(message[1]))
        elif kind == "aim":
            self.state.set(ball_id, aim=float(message[1]))

    def after_tick(self):
        # The systems, in order; Destiny has already moved every ball this tick.
        grid = spatial.EnemyGrid(self)
        enemies.melee(self, grid)
        enemies.attack(self)
        enemies.charge(self)
        enemies.bursters(self)
        enemies.turn_shields(self, TICK_MS / 1000.0)
        loot.update(self)
        move.update_rolls(self)
        spells.update_areas(self)
        combat.expire_slows(self)
        enemies.expire_hastes(self)
        progression.update_respawns(self)
        if MODE == "waves":
            self.waves.update()
        projectiles.update(self, grid)

    def ai_loop(self):
        while True:
            blue.synchro.SleepWallclock(250)
            now = blue.os.GetWallclockTimeNow()
            due = [t for t in self.respawns if t <= now]
            self.respawns = [t for t in self.respawns if t > now]
            for _ in due:
                enemies.spawn(self, self.pick_kind())
            enemies.steer(self, AGGRO_RANGE if MODE == "sandbox" else WAVE_AGGRO_RANGE)

    def clock_loop(self):
        while True:
            blue.synchro.SleepWallclock(CLOCK_EVERY_MS)
            self.broadcast(("clock", self.park.currentTime))

    def probe_loop(self):
        while True:
            blue.synchro.SleepWallclock(PROBE_EVERY_MS)
            if not self.peers:
                continue
            balls = self.park.balls
            ids = [b for _, b in self.player_balls()]
            foes = self.ents.of(Enemy)
            ids += self.rng.sample(sorted(foes), min(PROBE_BALLS, len(foes)))
            self.broadcast(("probe", self.park.currentTime, {i: (balls[i].x, balls[i].y, balls[i].z) for i in ids if i in balls}))
            self.broadcast(("score", dict(self.kills), len(foes)))

    def report_loop(self):
        last_ticks, last_time, last_sent = 0, blue.os.GetWallclockTimeNow(), 0
        while True:
            blue.synchro.SleepWallclock(5000)
            now = blue.os.GetWallclockTimeNow()
            seconds = blue.os.TimeDiffInMs(last_time, now) / 1000.0
            sent = sum(p.bytes_sent for p in self.peers.values())
            costs = self.timer.costs_ms
            print("[arpg] tick %d  %.1f/%.1f ticks/s  enemies %d  projectiles %d  tick p50 %.3f p99 %.3f ms  clients %d  out %.1f KB/s  kills %s  corrections %d" % (
                self.park.currentTime, (self.ticks - last_ticks) / seconds, 1000.0 / TICK_MS, len(self.ents.of(Enemy)),
                len(self.ents.of(Projectile)), costs.percentile(0.5), costs.percentile(0.99), len(self.peers),
                max(0, sent - last_sent) / 1024.0 / seconds, dict(self.kills), self.corrections.corrections))
            print("[arpg]   shots %s  loot %s  %s" % (self.shots, self.loot_stats, self.stats))
            print("[arpg]   players " + "  ".join("%d: lvl %s %s" % (b, (self.state.get(b) or {}).get("level"),
                                                                    (self.state.get(b) or {}).get("upgrades"))
                                              for _, b in self.player_balls()))
            if MODE == "waves":
                bosses = ["%d/%d%s" % (self.state.get(b)["hp"], self.state.get(b)["max_hp"], " enraged" if rage.active else "")
                          for b, rage in self.ents.each(Enrage)]
                w = self.waves
                print("[arpg]   wave %d  %s  remaining %s  alive players %d  boss %s" % (
                    w.wave, w.phase, w.remaining, len(self.alive_players()), bosses or "-"))
            print("[arpg]   p50 ms: " + "  ".join("%s %.2f" % (n, p.percentile(0.5)) for n, p in self.phases.items()))
            for p in self.phases.values():
                p.clear()
            costs.clear()
            last_ticks, last_time, last_sent = self.ticks, now, sent

    def start(self):
        self.park.Start()
        while self.park.currentTime < 1:
            blue.synchro.Yield()
        refresh_time_factors(self.park)
        if MODE == "sandbox":
            for _ in range(ENEMIES):
                enemies.spawn(self, self.pick_kind())
        else:
            self.waves.start()
        netproto.serve(PORT, self.on_connect)
        print("[arpg] %s mode, %d ms ticks, room %.0fx%.0f m, %d enemies, listening on %d" % (
            MODE, TICK_MS, world.ROOM_W, world.ROOM_D, len(self.ents.of(Enemy)), PORT))
        for loop in (self.ai_loop, self.clock_loop, self.probe_loop, self.report_loop):
            carbonapp.spawn(loop)
        if RUN_SECONDS:
            blue.synchro.SleepWallclock(int(RUN_SECONDS * 1000))
            carbonapp.quit()


game = None


def main():
    global game
    game = ArpgServer()
    game.start()


if __name__ == "__main__":
    carbonapp.run(main, frame_time_ms=max(1, min(10, TICK_MS // 2)))
