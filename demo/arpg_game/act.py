"""An open act on a generated level: explore, activate checkpoints, wake the boss, kill it, and leave by the exit.

The next act is generated on a background thread while this one is played; leaving, or a defeat, swaps it in."""
import math
import os
import tempfile

import arpg_world as world
from arpg_game import combat, enemies, loot, packs, progression
from arpg_game.components import Enemy, Home, Player
from arpg_gen import run
from arpg_map import Level
from scene import add_ball

CHECKPOINT_M, EXIT_M, BOSS_WAKE_M = 7.0, 3.5, 16.0
# Arena enemies arrive at least this far from every player.
ARENA_SPAWN_GAP_M = 6.0
DEFEAT_S = 6.0


class Act:
    def __init__(self, g, template, seed):
        self.g = g
        self.template, self.seed = template, seed
        self.phase, self.until = "explore", 0
        self.checkpoint, self.boss = 0, None
        self.arenas, self.rewarded = [], set()
        self.next_level, self._proc = None, None
        self._next_path = os.path.join(tempfile.gettempdir(), "carbon-crawler-act-%d.bin" % os.getpid())
        self.swap_at = None
        # Players' teleports land a tick after a swap; until then they still stand where the last act ended.
        self.settle_until = 0

    @property
    def features(self):
        return world.LEVEL.features

    def arrival(self):
        """Where players appear: the last checkpoint reached."""
        return tuple(self.features["checkpoints"][self.checkpoint])

    def start(self):
        g = self.g
        g.state.spawn("game", mode="act", act=world.LEVEL.name, phase="explore", checkpoint=0, exit_open=False,
                      seed=self.features["seed"], until=0)
        self.populate()
        self.prepare_next()

    def populate(self):
        g, feats = self.g, self.features
        for k, pack in enumerate(feats["packs"]):
            packs.spawn(g, k, pack)
        self.rewarded = set()
        self.arenas = [{"spec": spec, "cells": {tuple(c) for c in spec["cells"]}, "state": "idle", "wave": 0, "eids": []}
                       for spec in feats.get("arenas", [])]
        self.set_gates(list(world.gate_ids()), open_=True, quiet=True)
        boss_pack = {"at": tuple(feats["boss"]), "kinds": ["warlord"] + ["imp"] * 4}
        eids = packs.spawn(self.g, len(feats["packs"]), boss_pack, leash=0)
        self.boss = eids[0] if eids else None

    def prepare_next(self):
        self.next_level = None
        self.seed += 1
        if os.path.exists(self._next_path):
            os.remove(self._next_path)
        self._proc = run.start(self.template, self.seed, self._next_path)

    def poll_next(self):
        if self._proc is None or self._proc.poll() is None:
            return
        proc, self._proc = self._proc, None
        if proc.returncode == 0:
            self.next_level = Level.from_payload(run.load(self._next_path))
            os.remove(self._next_path)
        else:
            print("[act] generating the next act failed (%d); trying another seed" % proc.returncode)
            self.prepare_next()

    def set_gates(self, gate_ids, open_, quiet=False):
        g = self.g
        for gate_id in gate_ids:
            if open_ and gate_id in g.park.balls:
                g.sync.actions.remove_ball(gate_id)
            elif not open_ and gate_id not in g.park.balls:
                world.add_gate(g.park, add_ball, gate_id)
        if gate_ids and not quiet:
            g.state.event("game", "gate", gate=gate_ids[0], open=open_)
        world.sync_gates(g.park)

    def inside(self, arena, p):
        return world.LEVEL.cells.cell_of(p.x, p.z) in arena["cells"]

    def update_arenas(self, alive):
        g = self.g
        for arena in self.arenas:
            gate_ids = [world.GATE_BASE + k for k in arena["spec"]["gates"]]
            if arena["state"] == "idle":
                if alive and all(self.inside(arena, p) for p in alive):
                    self.set_gates(gate_ids, open_=False)
                    arena["state"], arena["wave"] = "fight", 0
                    g.state.event("game", "arena", wave=1)
                    self.arena_wave(arena, alive)
            elif arena["state"] == "fight":
                if not any(self.inside(arena, p) for p in alive):
                    # Everyone in it fell: the arena resets, its gates open for another try.
                    for eid in arena["eids"]:
                        if g.ents.has(eid, Enemy):
                            combat.kill_enemy(g, eid, None)
                    self.set_gates(gate_ids, open_=True)
                    arena["state"] = "idle"
                elif not any(g.ents.has(eid, Enemy) for eid in arena["eids"]):
                    arena["wave"] += 1
                    if arena["wave"] < len(arena["spec"]["waves"]):
                        g.state.event("game", "arena", wave=arena["wave"] + 1)
                        self.arena_wave(arena, alive)
                    else:
                        arena["state"] = "done"
                        self.set_gates(gate_ids, open_=True)
                        g.state.event("game", "arena_clear")

    def arena_wave(self, arena, alive):
        g = self.g
        cells = world.LEVEL.cells
        spots = [cells.cell_rect(i, j) for i, j in arena["cells"]]
        g.rng.shuffle(spots)
        arena["eids"] = []
        for kind in arena["spec"]["waves"][arena["wave"]]:
            for x0, z0, x1, z1 in spots:
                x, z = (x0 + x1) / 2, (z0 + z1) / 2
                if all(math.hypot(p.x - x, p.z - z) >= ARENA_SPAWN_GAP_M for p in alive)                         and not world.inside_box(x, z, pad=world.KINDS[kind]["radius"]):
                    spots.remove((x0, z0, x1, z1))
                    eid = enemies.spawn(g, kind, (x, z))
                    if eid is not None:
                        g.ents.add(eid, Home(x, z, -1, 0.0))
                        arena["eids"].append(eid)
                    break

    def update_rewards(self):
        g = self.g
        for k, pack in enumerate(self.features["packs"]):
            if pack.get("reward") and k not in self.rewarded and not packs.members(g, k):
                self.rewarded.add(k)
                for _, ball_id in g.player_balls():
                    progression.grant_pick(g, ball_id)
                g.state.event("game", "vault", at=tuple(pack["at"]))

    def set_phase(self, phase, seconds=0.0, **extra):
        g = self.g
        self.phase = phase
        self.until = g.park.currentTime + g.ticks_for(seconds) if seconds else 0
        g.state.set("game", phase=phase, until=self.until, **extra)

    def update(self):
        g = self.g
        tick = g.park.currentTime
        self.poll_next()
        if self.swap_at is not None:
            if tick >= self.swap_at:
                self.finish_swap()
            return
        players = g.player_balls()
        if not players or tick < self.settle_until:
            return
        alive = g.alive_players()
        feats = self.features
        self.update_arenas(alive)
        self.update_rewards()
        for k in range(self.checkpoint + 1, len(feats["checkpoints"])):
            cx, cz = feats["checkpoints"][k]
            if any(math.hypot(p.x - cx, p.z - cz) < CHECKPOINT_M for p in alive):
                self.checkpoint = k
                g.state.set("game", checkpoint=k)
                g.state.event("game", "checkpoint", at=(cx, cz))
        if self.phase == "explore" and self.boss is not None:
            bx, bz = feats["boss"]
            if any(math.hypot(p.x - bx, p.z - bz) < BOSS_WAKE_M for p in alive):
                packs.wake_if_asleep(g, self.boss)
                self.set_phase("boss")
        if self.phase in ("explore", "boss") and self.boss is not None and not g.ents.has(self.boss, Enemy):
            self.boss = None
            self.set_phase("exit", exit_open=True)
            g.state.event("game", "exit_open", at=tuple(feats["exit"]))
        if self.phase == "exit":
            ex, ez = feats["exit"]
            if alive and all(math.hypot(p.x - ex, p.z - ez) < EXIT_M for p in alive) and self.next_level is not None:
                self.begin_swap(reset=False)
        if self.phase != "defeat" and not alive:
            # Everyone down at once ends the run: nobody comes back at a checkpoint.
            for _, player in g.ents.each(Player):
                player.respawn_at = 0
            self.set_phase("defeat", DEFEAT_S)
        elif self.phase == "defeat" and tick >= self.until and self.next_level is not None:
            self.begin_swap(reset=True)

    def begin_swap(self, reset):
        """Clears this act; the level itself changes a tick later, once the old walls' balls are gone."""
        g = self.g
        for eid in list(g.ents.of(Enemy)):
            combat.kill_enemy(g, eid, None)
        loot.clear(g)
        g.sync.actions.remove_ball(world.ROOM)
        for gate_id in world.gate_ids():
            if gate_id in g.park.balls:
                g.sync.actions.remove_ball(gate_id)
        self.reset = reset
        self.swap_at = g.park.currentTime + 2
        self.set_phase("loading")

    def finish_swap(self):
        g = self.g
        self.swap_at = None
        # Players' teleports land a tick after a swap; until then they still stand where the last act ended.
        self.settle_until = 0
        level = self.next_level
        world.set_level(level)
        world.add_room(g.park, add_ball)
        g.broadcast(("level", level.payload()))
        self.checkpoint, self.boss = 0, None
        self.arenas, self.rewarded = [], set()
        for _, ball_id in g.player_balls():
            progression.respawn_player(g, ball_id, self.reset)
        g.state.set("game", act=level.name, checkpoint=0, exit_open=False, seed=level.features["seed"])
        self.set_phase("explore")
        self.settle_until = g.park.currentTime + 5
        self.populate()
        self.prepare_next()
