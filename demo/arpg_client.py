import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import trinity_viewer as tv
from trinity_viewer import OrbitCamera, TrinityViewer, plane_hit, trinity

import blue

import arpg_world as world
import carbonapp
from arpg_state import ClientState, mana_at
from arpg_audio import ArpgAudio
from arpg_front import FrontEnd
from arpg_view.actors import Actors
from arpg_view.effects import Effects
from arpg_view.events import Event, EventBus
from arpg_view.feedback import Feedback
from arpg_view.sounds import Sounds
from arpg_view.automap import Automap
from arpg_view.stage import Stage
from arpg_menu import (BACKDROP, DEFAULT_BINDINGS, Box, LevelUpButton, Menu, Orb, Picture, SpellBar, UpgradeScreen,
                       load_settings, save_settings)
from arpg_ui import Banner, BossBar, FloatingNumbers, WorldBars, projector
from predict import OwnBallPredictor
from scene import add_ball
from arpg_map import Level
from netsim import NetSim
from stats import Samples, TickTimer

AIM_SEND_S = 0.05
AUTOPLAY = os.environ.get("ARPG_AUTOPLAY") == "1"
PROFILE = __import__("cProfile").Profile() if os.environ.get("ARPG_PROFILE") == "1" else None
TEST_FRAMES = {kind: {int(f) for f in os.environ.get("ARPG_TEST_%s_FRAMES" % kind.upper(), "").split(",") if f}
               for kind in ("cast", "nova", "blink", "chain", "meteor", "frost", "pick", "roll", "jump")}
AIM_SEND_MIN_RAD = 0.05

COLORS = {
    "you": (0.2, 0.9, 0.35),
    "player": (0.3, 0.55, 1.0),
    "enemy": (0.9, 0.2, 0.2),
    "projectile": (1.0, 0.85, 0.2),
    "spit": (0.5, 1.0, 0.2),
    "bossshot": (0.7, 0.2, 1.0),
    "dead": (0.35, 0.35, 0.38),
}
HP_BAR_COLORS = ((0.3, 0.85, 0.35, 1.0), (0.85, 0.18, 0.15, 1.0))
WALL_COLOR = (0.35, 0.38, 0.46, 1.0)
VK_W, VK_A, VK_S, VK_D, VK_ESCAPE, VK_TAB, VK_SPACE = ord("W"), ord("A"), ord("S"), ord("D"), 0x1B, 0x09, 0x20
VK_F3, VK_SHIFT = 0x72, 0x10
SCHEMES = ("mouse", "wasd")
RETARGET_EVERY_MS = 100
RETARGET_MIN_MOVE_M = 0.5
MOVE_KEYS = {VK_W: (0, 1), VK_S: (0, -1), VK_A: (-1, 0), VK_D: (1, 0)}
KEY_SLOTS = {ord("Q"): "Q", ord("E"): "E", ord("R"): "R", ord("F"): "F"}
PICK_KEYS = {ord("1"): 0, ord("2"): 1, ord("3"): 2}
# Own events shown the moment the input is made, so the server's echo is dropped; chain and meteor only show the
# clip early, since their effect needs what the server resolved.
PREDICTED, PREDICTED_CLIP = ("cast", "nova", "blink", "frost", "roll", "jump"), ("chain", "meteor")


class ArpgSim(NetSim):
    def __init__(self, host, port, autoconnect=True):
        super().__init__(host, port, autoconnect)
        self.client.message_listeners.append(self._on_message)
        self.kills, self.enemies_alive = {}, 0
        self.state = ClientState(collect_events=True)
        self.input_latency_ms = Samples(200)
        self._pending_input = None
        self.denied_until = 0
        self.roll_ready = self.roll_until = self.jump_ready = self.jump_until = 0
        self.predictor = OwnBallPredictor(self.client)
        self.predictor.enabled = os.environ.get("ARPG_PREDICT", "1") == "1"
        self.debug = os.environ.get("ARPG_DEBUG") == "1"
        self._was_dead = False

    def _name_for(self, ball_id):
        if ball_id == self.client.own_ball:
            return "you"
        if ball_id >= world.BOSS_SHOT_BASE:
            return "bossshot %d" % ball_id
        if ball_id >= world.SPIT_BASE:
            return "spit %d" % ball_id
        if ball_id >= world.PROJECTILE_BASE:
            return "projectile %d" % ball_id
        if ball_id >= world.ENEMY_BASE:
            return "enemy %d" % ball_id
        return "player %d" % ball_id

    def _on_tick(self):
        self.state.apply_until(self.client.park.currentTime)
        super()._on_tick()
        world.sync_gates(self.client.park, self.predictor.park, add_ball)
        for static_id in (world.ROOM, *world.gate_ids()):
            self.tracked_by_id.pop(static_id, None)
        for ball_id, tracked in self.tracked_by_id.items():
            entity = self.state.get(ball_id)
            # Renaming makes the viewer rebuild the sphere, which is how a dead ball turns grey.
            tracked.name = ("dead " if entity and entity.get("dead") else "") + self._name_for(ball_id)
            tracked.color = COLORS[tracked.name.split(" ")[0]]
            tracked.entity = entity
        dead = self.own_dead()
        if dead != self._was_dead:
            self.predictor.reset()
            self._was_dead = dead
        if not dead:
            self.predictor.on_authoritative_tick()
        own = self.tracked_by_id.get(self.client.own_ball)
        if own is not None and not hasattr(own, "authoritative_position"):
            own.authoritative_position = own.position
            own.position = lambda alpha, t=own: self._render_own(t, alpha)
        self._check_input_response()

    def _render_own(self, tracked, alpha):
        predicted = self.predictor.position(alpha) if self.predictor.enabled and not self.own_dead() else None
        return predicted or tracked.authoritative_position(alpha)

    def toggle_prediction(self):
        self.predictor.enabled = not self.predictor.enabled
        self.predictor.reset()

    def _on_message(self, message):
        kind = message[0]
        if kind == "hello" and "level" in self.client.world:
            world.set_level(Level.from_payload(self.client.world["level"]))
        elif kind == "level":
            self.change_level(message[1])
        elif kind == "score":
            self.kills, self.enemies_alive = message[1], message[2]
        elif kind in ("state", "state_full"):
            self.state.receive(message)
        elif kind == "ack":
            self.predictor.on_ack(message[1], message[2])

    def connect(self, host, port, attempts=None):
        """A new session with host:port: everything the last one knew is dropped."""
        self.client.connect(host, port, attempts)
        self.tracked_by_id = {}
        self.kills, self.enemies_alive = {}, 0
        self.state = ClientState(collect_events=True)
        self._render_tick, self._last_frame_time, self.ticked = None, None, False
        self.predictor.park, self.predictor.ready = None, False
        self.predictor.reset()
        self._was_dead = False

    def leave(self):
        self.client.disconnect()

    def change_level(self, payload):
        """A new act: new walls for every park here, and the prediction's world rebuilt from scratch."""
        world.set_level(Level.from_payload(payload))
        self.client.world.update(level=payload, boxes=world.BOXES,
                                 gates={world.GATE_BASE + i: box for i, box in enumerate(world.GATES)})
        self.predictor.park, self.predictor.ready = None, False
        self.predictor.reset()

    def own_entity(self):
        return self.state.get(self.client.own_ball) or {}

    def own_mana(self):
        dt = (self.client.tick_ms or 20) / 1000.0
        return mana_at(self.own_entity(), self.client.park.currentTime, dt)

    def own_dead(self):
        return bool(self.own_entity().get("dead"))

    def _own_velocity(self):
        if self.predictor.enabled:
            predicted = self.predictor.velocity()
            if predicted is not None:
                return predicted
        ball = self.client.park.balls.get(self.client.own_ball)
        return (ball.vx, ball.vz) if ball is not None else (0.0, 0.0)

    def _send_movement(self, *command):
        if self.predictor.enabled and not self.own_dead():
            self.predictor.send(*command)
            self._check_input_response()
        else:
            self.client.send(*command)

    def _mark_input(self):
        self._pending_input = (blue.os.GetWallclockTimeNow(), self._own_velocity())

    def _check_input_response(self):
        if self._pending_input is None:
            return
        sent, (vx0, vz0) = self._pending_input
        vx, vz = self._own_velocity()
        if (vx - vx0) ** 2 + (vz - vz0) ** 2 > 0.25:
            self.input_latency_ms.add(blue.os.TimeDiffInUs(sent, blue.os.GetWallclockTimeNow()) / 1000.0)
            self._pending_input = None

    def goto(self, point, mark=True):
        if mark:
            self._mark_input()
        self._send_movement("goto", point[0], 0.0, point[2])
        self.goto_marker = point

    def move_direction(self, dx, dz):
        self._mark_input()
        self._send_movement("dir", dx, dz)
        self.goto_marker = None

    def stop(self):
        self._mark_input()
        self._send_movement("stop")
        self.goto_marker = None

    def send_aim(self, yaw):
        now = blue.os.GetWallclockTimeNow()
        last_time, last_yaw = getattr(self, "_aim_sent", (0, None))
        if now - last_time < AIM_SEND_S * 1e7:
            return
        if last_yaw is not None and abs((yaw - last_yaw + math.pi) % (2 * math.pi) - math.pi) < AIM_SEND_MIN_RAD:
            return
        self._aim_sent = (now, yaw)
        self.client.send("aim", yaw)

    def can_spend(self, cost):
        if self.own_dead():
            return False
        if self.own_mana() < cost:
            self.denied_until = blue.os.GetWallclockTimeNow() + 3000000
            return False
        return True

    def cast(self, point):
        if not self.can_spend(world.SPELLS["bolt"]["mana"]):
            return False
        self.client.send("cast", point[0], point[2])
        return True

    def nova(self):
        if not self.can_spend(world.SPELLS["nova"]["mana"]):
            return False
        self.client.send("nova")
        return True

    def spell(self, name, point):
        cost = world.SPELLS[name]["mana"]
        if not world.spell_unlocked(name, self.own_entity().get("level", 1)) or not self.can_spend(cost):
            return False
        self.client.send(name, point[0], point[2])
        return True

    def roll(self, dx, dz):
        """Rolls along (dx, dz) when the roll is ready; the cooldown is also kept here, a touch longer than the server's."""
        now = blue.os.GetWallclockTimeNow()
        if self.own_dead() or now < self.roll_ready or now < self.jump_until:
            return False
        self.roll_until = now + int(world.ROLL["s"] * 1e7)
        self.roll_ready = now + int((world.ROLL["cooldown_s"] + 0.05) * 1e7)
        self._mark_input()
        self._send_movement("roll", dx, dz)
        return True

    def jump(self):
        # Like the roll's, the jump's cooldown is also kept here, a touch longer than the server's.
        now = blue.os.GetWallclockTimeNow()
        if self.own_dead() or now < self.jump_ready or now < self.roll_until:
            return False
        self.jump_until = now + int(world.JUMP["s"] * 1e7)
        self.jump_ready = now + int((world.JUMP["s"] + world.JUMP["cooldown_s"] + 0.05) * 1e7)
        self.client.send("jump")
        return True

    def blink(self, point):
        """Blinks toward point; returns (from, to) as predicted here, which the server re-checks and applies."""
        if not self.can_spend(world.SPELLS["blink"]["mana"]):
            return None
        x, _, z = self.own_position()
        tx, tz = world.blink_target(x, z, point[0], point[2])
        self._mark_input()
        self._send_movement("blink", tx, tz)
        return (x, 0.0, z), (tx, 0.0, tz)

    def prediction_line(self):
        p = self.predictor
        if not p.enabled:
            return "prediction OFF (P)   moves when the server confirms"
        return "prediction ON (P)   %.1f ticks ahead   error p50 %.2f m  p95 %.2f m" % (
            p.ahead_ticks, p.error_m.percentile(0.5), p.error_m.percentile(0.95))

    def own_position(self):
        tracked = self.selected
        return tracked.position(self.alpha) if tracked else (0.0, 0.0, 0.0)

    def status_lines(self):
        c = self.client
        if not c.synced:
            if c.connected:
                return ["connected to %s:%d, joining ..." % (c.host, c.port), ""]
            return ["waiting for a server at %s:%d (attempt %d) - is %s running?" % (
                c.host, c.port, getattr(c, "connect_attempts", 0), "run_arpg_server"), ""]
        if not self.debug:
            return []
        s = c.stats
        mine = self.kills.get(c.client_id, 0)
        me = self.own_entity()
        game = self.state.get("game")
        if self.own_dead():
            vitals = "DEAD - back at the end of the wave" if self.state.get("game") else "DEAD - respawning"
        else:
            vitals = "lvl %d   hp %d/%d   mana %d/%d%s" % (
                me.get("level", 1), me.get("hp", 0), me.get("max_hp", 0), self.own_mana(), me.get("mana_max", 0),
                "   NOT ENOUGH MANA" if blue.os.GetWallclockTimeNow() < self.denied_until else "")
        return [
            "arpg client %s   %d ms ticks   input -> motion p50 %.0f ms   rtt %.0f ms   rewinds %d   probe err %.3f m" % (
                c.client_id, c.tick_ms, self.input_latency_ms.percentile(0.5), c.rtt_ms.percentile(0.5),
                s["rewinds"], s["probe_max_err"]),
            self.prediction_line(),
            "%s   kills %d   %s   players %d%s" % (vitals, mine, self.wave_status(game), len(self.kills),
                                                   "   %d upgrade%s to choose (U)" % (
                                                       me.get("picks", 0), "s" if me.get("picks", 0) > 1 else "")
                                                   if me.get("picks") else ""),
        ]

    def seconds_until(self, tick):
        return max(0.0, (tick - self.client.park.currentTime) * (self.client.tick_ms or 10) / 1000.0)

    def wave_status(self, game):
        if not game:
            return "enemies alive %d" % self.enemies_alive
        if game.get("mode") == "act":
            return "%s   %s   checkpoint %d" % (game.get("act"), game.get("phase"), game.get("checkpoint", 0) + 1)
        room = world.ROOMS[game.get("room", 0)]["name"]
        if game["phase"] == "fight":
            return "%s   enemies left %d" % (room if game.get("crawl") else "wave %d" % game["wave"], game.get("remaining", 0))
        if game["phase"] in ("defeat", "victory"):
            return game["phase"]
        if game["phase"] == "advance":
            return "the gate to %s is open" % world.ROOMS[game["room"] + 1]["name"]
        return "wave %d in %.0f s" % (game["wave"] + 1, self.seconds_until(game["until"]))


class ArpgViewer(TrinityViewer):
    title = "Carbon Crawler"
    min_draw_radius = 0.0
    grid_half_lines, grid_spacing = 35, 1.0
    grid_y = -world.PLAYER_RADIUS
    show_trails = False
    near, far = 0.1, 500.0

    def __init__(self, sim):
        self.title = os.environ.get("ARPG_WINDOW_TITLE", self.title)
        self.test_target = None
        self.held = set()
        self._rng = __import__("random").Random(5)
        self.walls_built = False
        self.mouse = None
        self.move_held = False
        self._last_retarget = (0, None)
        self.settings = load_settings()
        scheme = os.environ.get("ARPG_CONTROLS", self.settings["scheme"])
        self.scheme = scheme if scheme in SCHEMES else "wasd"
        self.menu_open = None
        super().__init__(sim)
        self.popups = trinity.Tr2Sprite2dScene()
        self.popups.displayWidth, self.popups.displayHeight = self.viewport_size()
        self.health_bars = WorldBars(trinity, self.popups)
        self.numbers = FloatingNumbers(trinity, self.popups)
        self.banner = Banner(trinity, self.popups)
        self.boss_bar = BossBar(trinity, self.popups)
        self.popup_step.scene = self.popups
        self.menus = trinity.Tr2Sprite2dScene()
        self.menus.displayWidth, self.menus.displayHeight = self.viewport_size()
        # Added first so it draws over every other menu sprite.
        self.pointer = Picture(trinity, self.menus, "cursor", 64)
        self.pointer_hot = load_hotspot()
        # Next, so the menu and loading screens cover every other HUD sprite.
        self.front = FrontEnd(trinity, self.menus, self.settings, self.save_settings)
        self.autopilot = None
        self.health_orb = Orb(trinity, self.menus, (0.85, 0.12, 0.1, 1.0))
        self.mana_orb = Orb(trinity, self.menus, (0.15, 0.35, 1.0, 1.0))
        self.spellbar = SpellBar(trinity, self.menus, world.SPELLS, world.UPGRADES, self.settings, self.save_settings)
        self.esc_menu = Menu(trinity, self.menus, 6)
        self.shrine_menu = Menu(trinity, self.menus, 2, width=420)
        self.upgrade_screen = UpgradeScreen(trinity, self.menus, world.UPGRADES)
        for menu in (self.esc_menu, self.shrine_menu, self.upgrade_screen):
            menu.on_close = self.close_menu
        self.levelup_button = LevelUpButton(trinity, self.menus)
        self.backdrop = Box(trinity, self.menus, BACKDROP)
        self.menu_step.scene = self.menus

    def make_camera(self):
        distance = float(os.environ.get("ARPG_CAM_DISTANCE", "18"))
        pitch = float(os.environ.get("ARPG_CAM_PITCH", "0.95"))
        return OrbitCamera(yaw=math.pi / 4, pitch=pitch, distance=distance, min_distance=4.0, max_distance=90.0)

    def help_lines(self):
        if not self.sim.debug:
            return []
        controls = "MOUSE (hold LMB to move)" if self.scheme == "mouse" else "WASD"
        return ["%s   click a spell slot to rebind it   U: upgrades   wheel: zoom   Esc: menu   F3: hide this   %.0f fps" % (
            controls, blue.os.fps)]

    def save_settings(self):
        self.settings["scheme"] = self.scheme
        save_settings(self.settings)

    def switch_scheme(self):
        self.scheme = SCHEMES[(SCHEMES.index(self.scheme) + 1) % len(SCHEMES)]
        self.save_settings()
        self.held.clear()
        self.move_held = False
        self.sim.stop()

    def update_camera(self):
        x, y, z = self.sim.own_position()
        start, amount, seconds = getattr(self, "_shake", (0, 0.0, 1.0))
        left = 1.0 - blue.os.TimeDiffInMs(start, blue.os.GetWallclockTimeNow()) / 1000.0 / seconds
        if left > 0:
            k = amount * left * left
            x, z = x + (self._rng.random() * 2 - 1) * k, z + (self._rng.random() * 2 - 1) * k
        self.cam.target = (x, y, z)
        super().update_camera()
        self.retarget_held_move()

    def retarget_held_move(self):
        if not self.move_held or self.mouse is None:
            return
        now = blue.os.GetWallclockTimeNow()
        last_time, last_point = self._last_retarget
        if blue.os.TimeDiffInMs(last_time, now) < RETARGET_EVERY_MS:
            return
        point = self._pick(*self.mouse)
        if point is None:
            return
        if last_point is None or (point[0] - last_point[0]) ** 2 + (point[2] - last_point[2]) ** 2 > RETARGET_MIN_MOVE_M ** 2:
            self.sim.goto(point, mark=False)
            self._last_retarget = (now, point)

    def build_static(self, scene):
        self.use_meshes = os.environ.get("ARPG_MESHES", "1") == "1"
        if self.use_meshes:
            self.bus = EventBus()
            self.stage = Stage(trinity)
            self.automap = None
            self.actors = Actors(self.stage, self.bus)
            self.effects = Effects(self.stage, self.bus, self.actors.get)
            self.audio = ArpgAudio()
            self.audio.set_volumes(self.settings["music_volume"], self.settings["sound_volume"])
            Sounds(self.bus, self.audio)
            Feedback(self.bus, self)
            self.bus.on(("arena", "arena_clear", "vault"), self.on_act_event)
            self.mesh_timer, self.frame_ms = TickTimer(), Samples()
            self.grid.ClearLines()
            self.grid.SubmitChanges()
            self._last_frame = blue.os.GetSimTime()

    def build_render_job(self):
        if not self.use_meshes:
            return super().build_render_job()
        self.view = trinity.TriView()
        self.projection = trinity.TriProjection()
        self.jobs = trinity.Tr2RenderJobs()
        self.device.SetRenderJobs(self.jobs)
        self.depth_step = trinity.TriStepPushDepthStencil()
        self.depth_size = None
        self.ensure_depth_buffer()
        job = trinity.TriRenderJob()
        job.name = "carbon_crawler"
        self.main_job = job
        self.popup_step, self.menu_step = trinity.TriStepRenderScene(), trinity.TriStepRenderScene()
        self.map_step = trinity.TriStepRenderScene()
        for step in [self.depth_step] + self.scene_steps(hud=False) + [trinity.TriStepPopDepthStencil(),
                                                                       self.popup_step, self.map_step,
                                                                       trinity.TriStepRenderScene(self.hud.scene),
                                                                       self.menu_step]:
            job.steps.append(step)
        self.jobs.recurring.append(job)

    def scene_steps(self, hud=True):
        # The mesh scene uses normal depth (clear to 1); the overlay primitive scene uses reversed depth (clear to 0).
        steps = [trinity.TriStepClear(tv.CLEAR_COLOR, 1.0),
                 trinity.TriStepSetView(self.view),
                 trinity.TriStepSetProjection(self.projection),
                 trinity.TriStepUpdate(self.stage.scene),
                 trinity.TriStepRenderScene(self.stage.scene),
                 trinity.TriStepClear(None, 0.0),
                 trinity.TriStepRenderScene(self.scene)]
        return steps + ([trinity.TriStepRenderScene(self.hud.scene)] if hud else [])

    def update_mesh_world(self):
        now = blue.os.GetSimTime()
        dt, self._last_frame = (now - self._last_frame) / 1e7, now
        self.frame_ms.add(dt * 1000.0)
        alpha = self.sim.alpha
        if any(TEST_FRAMES.values()) or os.environ.get("ARPG_TEST_OPEN"):
            self._test_cast(alpha)
        self.follow_session()
        self.mesh_timer.begin()
        if PROFILE is not None:
            PROFILE.enable()
        if self.stage.level is not world.LEVEL and "level" in self.sim.client.world:
            self.stage.build_level(world.LEVEL)
        self.actors.sync(self.sim.tracked, alpha, dt, self.aims(alpha))
        self.actors.sync_loot({k: e for k, e in self.sim.state.entities.items()
                               if isinstance(k, int) and k >= world.LOOT_BASE and "loot" in e})
        self.dispatch_events()
        self.effects.update(dt)
        self.stage.advance(dt)
        if PROFILE is not None:
            PROFILE.disable()
        self.mesh_timer.end()
        own = self.actors.get(self.sim.client.own_ball)
        self.stage.set_view(self.cam.eye(), own.last if own is not None else None)
        width, height = self.viewport_size()
        self.popups.displayWidth, self.popups.displayHeight = width, height
        self.numbers.update(dt, projector(self.cam.eye(), self.cam.target, tv.FOV, width, height))
        self.announce_waves()
        self.audio.set_track(self.music_track())
        self.banner.update(dt, width, height)
        if self.automap is None:
            self.automap = Automap(trinity, self.popups, tv.make_effect)
            self.map_step.scene = self.automap.scene
        if self.stage.level is world.LEVEL and self.automap.level is not world.LEVEL:
            self.automap.set_level(world.LEVEL, self.cam.yaw)
        game = self.sim.state.get("game") or {}
        self.automap.update(dt, own.last if own is not None else None,
                            world.LEVEL.features.get("exit") if game.get("exit_open") else None, width, height)
        me = self.sim.own_entity()
        self.menus.displayWidth, self.menus.displayHeight = width, height
        level = me.get("level", 1)
        mana = self.sim.own_mana()
        self.spellbar.update(level, mana, me.get("xp", 0) / float(me.get("xp_next", 1) or 1), self.scheme, width, height,
                             lambda spell: world.spell_unlocked(spell, level), me.get("upgrades") or {})
        self.health_orb.update(me.get("hp", 0) / float(me.get("max_hp", 1) or 1),
                               "%d / %d" % (me.get("hp", 0), me.get("max_hp", 0)), False, width, height)
        self.mana_orb.update(mana / float(me.get("mana_max", 1) or 1), "%d / %d" % (mana, me.get("mana_max", 0)),
                             True, width, height)
        left, top, _ = self.spellbar.layout(width, height)
        self.levelup_button.update(me.get("picks", 0), self.stage.clock, left, top)
        self.update_menus(width, height)
        self.front.draw(self.sim, width, height, self.stage.clock)
        self.update_pointer(dt, width, height)
        boss = next((e for k, e in self.sim.state.entities.items() if isinstance(e, dict) and e.get("kind") == "warlord"),
                    None)
        game = self.sim.state.get("game") or {}
        if game.get("mode") == "act" and game.get("phase") != "boss":
            # An act's Warlord sleeps in its lair from the start; its bar shows once it wakes.
            boss = None
        self.boss_bar.update(boss, width, height)
        # The listener sits on the followed ball, facing the way the camera looks across the floor.
        self.audio.update(self.cam.target, (-math.sin(self.cam.yaw), 0.0, -math.cos(self.cam.yaw)))
        exit_after = int(os.environ.get("VIEWER_EXIT_AFTER", "0"))
        if exit_after and self.frame == exit_after:
            self.audio.report()
            costs = self.mesh_timer.costs_ms
            if PROFILE is not None:
                import pstats
                pstats.Stats(PROFILE).sort_stats("tottime").print_stats(12)
            print("[perf] actors %d  mesh sync p50 %.2f p99 %.2f ms  frame p50 %.2f p99 %.2f ms" % (
                len(self.actors.actors) + len(self.actors.corpses), costs.percentile(0.5), costs.percentile(0.99),
                self.frame_ms.percentile(0.5), self.frame_ms.percentile(0.99)))
            p = self.sim.predictor
            print("[predict] error p50 %.3f p95 %.3f m  correction p95 %.3f max %.3f m" % (
                p.error_m.percentile(0.5), p.error_m.percentile(0.95), p.correction_m.percentile(0.95),
                p.correction_m.percentile(1.0)))
        self.overlay.ClearLines()
        selected = self.sim.selected
        if selected is not None:
            self.add_ring(selected.position(alpha), 0.75, (1, 1, 1, 0.7))
        if self.sim.goto_marker:
            self.add_ring(self.sim.goto_marker, 0.6, (1, 1, 1, 0.9))
        self.draw_telegraphs()
        self.overlay.SubmitChanges()

    def update_pointer(self, dt, width, height):
        if self.autopilot is None:
            self.pointer.hide()
            return
        own = self.sim.own_position() if self.sim.client.synced else None
        project = projector(self.cam.eye(), self.cam.target, tv.FOV, width, height)
        (x, y), pressed = self.autopilot.pointer(dt, project, own, width, height)
        size = 64 * (0.86 if pressed else 1.0)
        hx, hy = self.pointer_hot
        self.pointer.place(x - hx * size / 64.0, y - hy * size / 64.0, size, size)

    def dispatch_events(self):
        own = self.sim.client.own_ball
        for _, key, name, data in self.sim.state.take_events():
            mine = key == own
            if mine and name in PREDICTED:
                continue
            self.bus.emit(Event(name, key, data, self.actors.get(key), animate=not (mine and name in PREDICTED_CLIP)))

    def predict(self, name, **data):
        if self.use_meshes:
            own = self.sim.client.own_ball
            self.bus.emit(Event(name, own, data, self.actors.get(own), present=name in PREDICTED))

    def update_primitives(self):
        if self.use_meshes:
            self.update_mesh_world()
        else:
            self.sim.state.take_events()
            if not self.walls_built and self.sim.client.world.get("boxes"):
                self.build_walls(self.sim.client.world)
            super().update_primitives()
        self.draw_health_bars()

    def draw_health_bars(self):
        alpha = self.sim.alpha
        actors = self.actors.actors if self.use_meshes else {}
        items = []
        for t in self.sim.tracked:
            entity = getattr(t, "entity", None)
            if not entity or "hp" not in entity or entity.get("dead"):
                continue
            fraction = entity["hp"] / float(entity["max_hp"])
            enemy = t.name.startswith("enemy")
            if enemy and fraction >= 1.0:
                continue
            x, y, z = t.position(alpha)
            actor = actors.get(t.ball.id)
            if actor is not None and actor.role == "warlord":
                continue
            if not self.use_meshes:
                lift = 0.9
            elif enemy:
                lift = 1.45 * (actor.size if actor else 1.0)
            else:
                lift = 2.05
            items.append(((x, y + lift, z), fraction, HP_BAR_COLORS[1] if enemy else HP_BAR_COLORS[0]))
        width, height = self.viewport_size()
        scale = max(0.6, min(1.6, 18.0 / self.cam.distance))
        self.health_bars.update(items, projector(self.cam.eye(), self.cam.target, tv.FOV, width, height), scale)

    def build_walls(self, description):
        solids = trinity.Tr2SolidSet()
        solids.effect = self.solid_effect
        y0, y1 = -1.0, -1.0 + description.get("wall_height", 3.0)
        for x0, z0, x1, z1 in description["boxes"]:
            add_box(solids, (x0, y0, z0), (x1, y1, z1), WALL_COLOR)
        solids.SubmitChanges()
        self.scene.primitives.append(solids)
        self.walls_built = True

    def aims(self, alpha):
        aims = {}
        for t in self.sim.tracked:
            entity = getattr(t, "entity", None)
            if entity and "aim" in entity and not entity.get("dead"):
                aims[t.ball.id] = entity["aim"]
        own = self.sim.tracked_by_id.get(self.sim.client.own_ball)
        target = self._pick(*self.mouse) if self.mouse else getattr(self, "test_target", None)
        if own is not None and target is not None and not self.sim.own_dead():
            x, _, z = own.position(alpha)
            if (target[0] - x) ** 2 + (target[2] - z) ** 2 > 0.04:
                yaw = math.atan2(target[0] - x, target[2] - z)
                aims[own.ball.id] = yaw
                self.sim.send_aim(yaw)
        return aims

    def _test_cast(self, alpha):
        # Test hook: aim screen-right of the own ball and cast on the listed frames, for capturing a release.
        own = self.sim.tracked_by_id.get(self.sim.client.own_ball)
        if own is None:
            return
        x, _, z = own.position(alpha)
        self.test_target = (x + 8.0 * math.cos(self.cam.yaw), 0.0, z - 8.0 * math.sin(self.cam.yaw))
        if self.frame in TEST_FRAMES["cast"] and self.sim.cast(self.test_target):
            self.predict("cast")
        if self.frame in TEST_FRAMES["nova"]:
            self.do_nova()
        if self.frame in TEST_FRAMES["blink"]:
            self.do_blink()
        if self.frame in TEST_FRAMES["roll"]:
            self.do_roll()
        if self.frame in TEST_FRAMES["jump"]:
            self.do_jump()
        for name in ("chain", "meteor", "frost"):
            if self.frame in TEST_FRAMES[name]:
                self.do_spell(name)
        if self.frame in TEST_FRAMES["pick"] and self.sim.own_entity().get("offer"):
            self.sim.client.send("pick", 0)
        for step in os.environ.get("ARPG_TEST_OPEN", "").split(","):
            menu, _, at = step.partition(":")
            if not menu or self.frame != int(at or 0):
                continue
            if menu == "picker":
                self.spellbar.toggle("Q")
            elif menu == "close":
                self.spellbar.open_slot = None
                self.close_menu()
            else:
                self.menu_open = menu

    def _pick(self, x, y):
        origin, direction = self.cam.ray(x, y, *self.viewport_size())
        return plane_hit(origin, direction)

    def on_mouse_down(self, button, x, y):
        if AUTOPLAY:
            return
        self.mouse = (x, y)
        if self.front.mode != "playing":
            if self.front.mode == "menu" and button == tv.MOUSE_LEFT:
                self.front.click(x, y)
            return
        if self.menu_open:
            menu = {"esc": self.esc_menu, "shrine": self.shrine_menu, "upgrades": self.upgrade_screen}[self.menu_open]
            if not menu.click(x, y):
                self.close_menu()
            return
        if button == tv.MOUSE_LEFT and self.levelup_button.click(x, y):
            self.menu_open = "upgrades"
            return
        if button == tv.MOUSE_LEFT and self.spellbar.click(x, y):
            return
        point = self._pick(x, y)
        if point is None:
            return
        if button == tv.MOUSE_LEFT and self.clicked_shrine(point):
            return
        if button == tv.MOUSE_LEFT and self.scheme == "mouse":
            self.move_held = True
            self.sim.goto(point)
            self._last_retarget = (blue.os.GetWallclockTimeNow(), point)
        elif button in (tv.MOUSE_LEFT, tv.MOUSE_RIGHT):
            self.use_slot("LMB" if button == tv.MOUSE_LEFT else "RMB")

    def use_slot(self, slot):
        spell = self.settings["bindings"].get(slot)
        if spell and not self.menu_open:
            self.use_spell(spell)

    def use_spell(self, spell):
        if spell == "bolt":
            target = self._pick(*self.mouse) if self.mouse else getattr(self, "test_target", None)
            if target is not None and self.sim.cast(target):
                self.predict("cast")
        elif spell == "nova":
            self.do_nova()
        elif spell == "blink":
            self.do_blink()
        else:
            self.do_spell(spell)

    def shrine_usable(self):
        game = self.sim.state.get("game")
        if game is None:
            return True
        if game.get("mode") == "act":
            return game.get("phase") in ("explore", "exit")
        return game.get("phase") != "fight"

    def near_shrine(self):
        x, _, z = self.sim.own_position()
        return any(math.hypot(x - sx, z - sz) <= world.SHRINE_RANGE for sx, sz in world.SHRINES)

    def clicked_shrine(self, point):
        if all(math.hypot(point[0] - sx, point[2] - sz) > 1.6 for sx, sz in world.SHRINES):
            return False
        if self.shrine_usable() and self.near_shrine():
            self.menu_open = "shrine"
        return True

    def close_menu(self):
        self.menu_open = None
        self.esc_menu.hide()
        self.shrine_menu.hide()
        self.upgrade_screen.hide()
        self.backdrop.hide()

    def leave_game(self):
        self.close_menu()
        self.sim.leave()
        self.front.to_menu()

    def follow_session(self):
        """Moves between menu, loading and play as the connection and the level come and go."""
        sim, front = self.sim, self.front
        client = sim.client
        if front.mode == "loading":
            own = self.actors.get(client.own_ball)
            game = sim.state.get("game") or {}
            steps = ((client.connected, "connecting"), (client.synced, "joining"),
                     (game.get("phase") != "loading", "the next act"),
                     ("level" in client.world, "receiving the world"),
                     (self.stage.level is world.LEVEL, "building the level"),
                     (own is not None and own.placeable.placeableRes is not None, "placing you"))
            waiting = next((why for done, why in steps if not done), "loading models and textures")
            front.check_loading(sim, all(done for done, _ in steps), waiting)
        elif front.mode == "playing":
            game = sim.state.get("game") or {}
            if client.lost:
                front.to_menu("the connection to %s closed" % front.target)
            elif self.stage.level is not world.LEVEL or game.get("phase") == "loading":
                front.begin_loading("the next act")

    def set_volume(self, key, value):
        self.settings[key] = value
        self.audio.set_volumes(self.settings["music_volume"], self.settings["sound_volume"])

    def update_menus(self, width, height):
        if self.menu_open == "shrine" and (not self.shrine_usable() or not self.near_shrine()):
            self.close_menu()
        if self.menu_open != getattr(self, "_menu_shown", None):
            for name, menu in (("esc", self.esc_menu), ("shrine", self.shrine_menu), ("upgrades", self.upgrade_screen)):
                if name != self.menu_open:
                    menu.hide()
            self._menu_shown = self.menu_open
        if not self.menu_open:
            return
        self.backdrop.place(0, 0, width, height)
        if self.menu_open == "esc":
            self.esc_menu.show("MENU", "the game keeps running while this is open", [
                ("Resume", "", self.close_menu, True, "resume"),
                ("Controls: %s" % ("WASD" if self.scheme == "wasd" else "mouse"), "click to switch",
                 self.switch_scheme, True, "controls"),
                ("Music", "%d%%" % round(100 * self.settings["music_volume"]), None, True, "music",
                 self.settings["music_volume"] == 0, self.settings["music_volume"],
                 lambda v: self.set_volume("music_volume", v)),
                ("Sounds", "%d%%" % round(100 * self.settings["sound_volume"]), None, True, "sounds",
                 self.settings["sound_volume"] == 0, self.settings["sound_volume"],
                 lambda v: self.set_volume("sound_volume", v)),
                ("Leave game", "back to the server list", self.leave_game, True, "resume"),
                ("Quit", "", carbonapp.quit, True, "quit"),
            ], width, height)
            return
        me = self.sim.own_entity()
        if self.menu_open == "upgrades":
            self.upgrade_screen.show(me, lambda i: self.sim.client.send("pick", i), width, height)
            return
        ready = bool(me.get("ready"))
        game = self.sim.state.get("game") or {}
        if game.get("mode") == "act":
            self.shrine_menu.show("THE SHRINE", "you will come back to life here if you fall", [
                ("Upgrades", "%d to choose" % me.get("picks", 0) if me.get("picks") else "",
                 lambda: setattr(self, "menu_open", "upgrades"), True, "upgrades")], width, height)
            return
        countdown = "next wave in %.0f s" % self.sim.seconds_until(game["until"]) if game.get("until") else ""
        items = [("Ready for the next wave" if not ready else "Ready - waiting for the others", countdown,
                  lambda: self.sim.client.send("ready", not ready), bool(game), "ready"),
                 ("Upgrades", "%d to choose" % me.get("picks", 0) if me.get("picks") else "",
                  lambda: setattr(self, "menu_open", "upgrades"), True, "upgrades")]
        self.shrine_menu.show("THE SHRINE", "catch your breath - the next wave starts when everyone is ready"
                              if game else "no waves in the sandbox", items, width, height)

    def do_nova(self):
        if self.sim.nova():
            nova = world.spell(self.sim.own_entity(), "nova")
            self.predict("nova", radius=nova["radius"], slow=nova["slow"])
            self.shake(0.12, 0.25)

    def do_blink(self):
        target = self._pick(*self.mouse) if self.mouse else getattr(self, "test_target", None)
        if target is None:
            return
        jump = self.sim.blink(target)
        if jump:
            (x, _, z), (tx, _, tz) = jump
            self.predict("blink", origin=(x, z), dest=(tx, tz), frost=world.spell(self.sim.own_entity(), "blink")["frost"])

    def music_track(self):
        game = self.sim.state.get("game")
        if game is None:
            return "fight"
        if game.get("mode") == "act":
            return {"boss": "boss", "explore": "fight"}.get(game.get("phase"), "calm")
        if game.get("phase") != "fight":
            return "calm"
        boss = game.get("wave", 0) % world.BOSS_EVERY_WAVES == 0
        return "boss" if boss else "fight"

    def announce_waves(self):
        game = self.sim.state.get("game")
        if not game:
            return
        if game.get("mode") == "act":
            self.announce_act(game)
            return
        seen = (game["wave"], game["phase"], game.get("room", 0))
        if seen == getattr(self, "_wave_seen", None):
            return
        first = not hasattr(self, "_wave_seen")
        self._wave_seen = seen
        wave, phase, room = seen
        crawl = game.get("crawl")
        if phase == "fight":
            boss = wave % world.BOSS_EVERY_WAVES == 0
            title, subtitle = (world.ROOMS[room]["name"].upper(), "room %d of %d" % (room + 1, len(world.ROOMS))) if crawl                 else ("WAVE %d" % wave, "")
            self.banner.show(title, subtitle, 2.5, (1.0, 0.45, 0.3) if boss else (1.0, 1.0, 1.0))
            self.audio.play("roar" if boss else "wave_start", self.cam.target)
        elif phase in ("defeat", "victory"):
            # A defeat or a won run starts a new run at level 1, and the spell bar starts over with it.
            self.settings["bindings"].clear()
            self.settings["bindings"].update(DEFAULT_BINDINGS)
            if phase == "victory":
                self.banner.show("VICTORY", "the dungeon is cleared", 5.0, (1.0, 0.85, 0.4))
                self.audio.play("levelup", self.cam.target)
            else:
                self.audio.play("defeat", self.cam.target)
        elif phase == "advance" and not first:
            self.banner.show("ROOM CLEARED", "on to %s" % world.ROOMS[room + 1]["name"], 3.0, (0.85, 0.95, 1.0))
            self.audio.play("wave_clear", self.cam.target)
        elif wave > 0 and not first and not crawl:
            self.audio.play("wave_clear", self.cam.target)

    def on_act_event(self, event):
        if event.name == "arena":
            self.banner.show("THE GATES CLOSE" if event.data["wave"] == 1 else "WAVE %d" % event.data["wave"],
                             "survive three waves", 2.5, (1.0, 0.55, 0.35))
            self.audio.play("roar" if event.data["wave"] == 1 else "wave_start", self.cam.target)
        elif event.name == "arena_clear":
            self.banner.show("THE GATES OPEN", "", 2.5, (0.85, 0.95, 1.0))
            self.audio.play("wave_clear", self.cam.target)
        elif event.name == "vault":
            self.banner.show("TREASURE", "an extra upgrade for everyone (U)", 3.0, (1.0, 0.85, 0.4))
            self.audio.play("levelup", self.cam.target)

    def announce_act(self, game):
        seen = (game.get("seed"), game.get("phase"), game.get("checkpoint", 0))
        before = getattr(self, "_act_seen", None)
        if seen == before:
            return
        self._act_seen = seen
        seed, phase, checkpoint = seen
        if before is None or seed != before[0]:
            self.banner.show(str(game.get("act", "")).upper(), "find the Warlord and the way on", 3.5, (0.85, 0.95, 1.0))
            self.audio.play("wave_start", self.cam.target)
        elif phase != before[1]:
            if phase == "boss":
                self.banner.show("THE WARLORD", "", 2.5, (1.0, 0.45, 0.3))
                self.audio.play("roar", self.cam.target)
            elif phase == "exit":
                self.banner.show("THE WAY ON IS OPEN", "everyone to the light", 3.5, (0.55, 0.85, 1.0))
                self.audio.play("wave_clear", self.cam.target)
            elif phase == "defeat":
                self.settings["bindings"].clear()
                self.settings["bindings"].update(DEFAULT_BINDINGS)
                self.audio.play("defeat", self.cam.target)
        elif checkpoint > before[2]:
            self.banner.show("CHECKPOINT", "you will come back to life here", 2.5, (1.0, 0.85, 0.4))
            self.audio.play("levelup", self.cam.target)

    def draw_telegraphs(self):
        self.effects.draw(self.add_ring, self.overlay.AddLine)
        pulse = 0.5 + 0.5 * math.sin(self.stage.clock * 3.0)
        if self.shrine_usable():
            color = (1.0, 0.8, 0.35, 0.35 + 0.4 * pulse) if self.near_shrine() else (1.0, 0.8, 0.35, 0.2 + 0.2 * pulse)
            for sx, sz in world.SHRINES:
                self.add_ring((sx, -0.45, sz), world.SHRINE_RANGE, color, segments=48)
        game = self.sim.state.get("game") or {}
        if game.get("exit_open") and world.LEVEL.features.get("exit"):
            ex, ez = world.LEVEL.features["exit"]
            for k in range(3):
                self.add_ring((ex, -0.45, ez), 1.2 + k * 0.9 + pulse * 0.5, (0.55, 0.85, 1.0, 0.75 - 0.2 * k), segments=48)

    def do_spell(self, name):
        target = self._pick(*self.mouse) if self.mouse else getattr(self, "test_target", None)
        if target is None or not self.sim.spell(name, target):
            return
        own = self.sim.own_position()
        yaw = math.atan2(target[0] - own[0], target[2] - own[2])
        frost = world.spell(self.sim.own_entity(), "frost")
        self.predict(name, **({"yaw": yaw, "reach": frost["range"], "arc_deg": frost["arc_deg"]} if name == "frost" else {}))

    def shake(self, amount, seconds):
        self._shake = (blue.os.GetWallclockTimeNow(), amount, seconds)

    def on_mouse_up(self, button, x, y):
        if button == tv.MOUSE_LEFT:
            self.move_held = False
            if self.esc_menu.dragging is not None:
                self.esc_menu.release()
                self.save_settings()

    def on_mouse_move(self, x, y):
        if AUTOPLAY:
            return
        self.mouse = (x, y)
        if self.front.mode != "playing":
            self.front.hover(x, y)
            return
        self.spellbar.hover(x, y)
        self.esc_menu.hover(x, y)
        self.shrine_menu.hover(x, y)
        self.upgrade_screen.hover(x, y)
        self.esc_menu.drag(x, y)

    def on_key_down(self, key, flags):
        if AUTOPLAY:
            return
        if self.front.mode != "playing":
            if self.front.mode == "menu":
                self.front.key(key)
            return
        if key == VK_ESCAPE:
            if self.menu_open or self.spellbar.open_slot:
                self.spellbar.open_slot = None
                self.close_menu()
            else:
                self.menu_open = "esc"
        elif key == VK_SHIFT:
            self.do_roll()
        elif key == VK_SPACE:
            self.do_jump()
        elif key == VK_F3:
            self.sim.debug = not self.sim.debug
        elif key == VK_TAB and self.use_meshes and self.automap is not None:
            self.automap.toggle()
        elif key == ord("P"):
            self.sim.toggle_prediction()
        elif key == ord("U"):
            if self.menu_open == "upgrades":
                self.close_menu()
            elif not self.menu_open:
                self.menu_open = "upgrades"
        elif self.menu_open == "upgrades" and key in PICK_KEYS:
            self.sim.client.send("pick", PICK_KEYS[key])
        elif key in KEY_SLOTS:
            self.use_slot(KEY_SLOTS[key])
        elif self.scheme == "wasd" and key in MOVE_KEYS and key not in self.held:
            self.held.add(key)
            self.send_direction()

    def on_key_up(self, key, flags):
        if AUTOPLAY:
            return
        if key in self.held:
            self.held.discard(key)
            self.send_direction()

    def held_direction(self):
        sx = sum(MOVE_KEYS[k][0] for k in self.held)
        sz = sum(MOVE_KEYS[k][1] for k in self.held)
        if sx == 0 and sz == 0:
            return None
        # Screen-relative: "up" is away from the camera, projected onto the floor.
        fx, fz = -math.sin(self.cam.yaw), -math.cos(self.cam.yaw)
        rx, rz = -fz, fx
        dx, dz = sz * fx + sx * rx, sz * fz + sx * rz
        length = math.hypot(dx, dz)
        return dx / length, dz / length

    def send_direction(self):
        direction = self.held_direction()
        if direction is None:
            self.sim.stop()
        else:
            self.sim.move_direction(*direction)

    def do_jump(self):
        if self.sim.jump():
            self.predict("jump")

    def do_roll(self, direction=None):
        """Rolls the way the movement keys point, or else toward the cursor; then queues the movement to resume with."""
        if direction is None and self.scheme == "wasd":
            direction = self.held_direction()
        if direction is None:
            target = self._pick(*self.mouse) if self.mouse else getattr(self, "test_target", None)
            if target is None:
                return
            x, _, z = self.sim.own_position()
            dx, dz = target[0] - x, target[2] - z
            length = math.hypot(dx, dz)
            if length < 1e-3:
                return
            direction = (dx / length, dz / length)
        if not self.sim.roll(*direction):
            return
        self.predict("roll", dir=direction)
        if self.scheme == "wasd":
            self.send_direction()
        elif self.move_held:
            self._last_retarget = (0, None)
            self.retarget_held_move()
        else:
            self.sim.stop()

    def sample_hud(self, count):
        # Test hook: capture the whole frame at random moments, to catch HUD lines that flicker out.
        from offscreen import capture_job
        rng = __import__("random").Random(3)
        out = os.path.join(HERE, "out", "hud_samples")
        blue.synchro.SleepWallclock(6000)
        for i in range(count):
            blue.synchro.SleepWallclock(int(rng.uniform(40, 260)))
            capture_job(trinity, self.main_job, *self.viewport_size(), path=os.path.join(out, "%03d.png" % i), frames=2)

    def start(self):
        self.window.onKeyUp = self.on_key_up
        use_glove_cursor(self.title)
        if os.environ.get("ARPG_HUD_SAMPLES"):
            carbonapp.spawn(self.sample_hud, int(os.environ["ARPG_HUD_SAMPLES"]))
        if AUTOPLAY:
            import arpg_autopilot
            arpg_autopilot.start(self)
        super().start()


def load_hotspot():
    try:
        with open(os.path.join(tv.RES_ROOT, "arpg", "ui", "cursor.json")) as f:
            return tuple(json.load(f)["hotspot"])
    except (OSError, ValueError, KeyError):
        return (4, 3)


def use_glove_cursor(title):
    """Gives the game window the glove cursor (it has none, so Windows shows the busy wheel) and its own icon."""
    import ctypes
    user32 = ctypes.windll.user32
    user32.SetClassLongPtrW.restype = ctypes.c_void_p
    user32.SetClassLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
    user32.LoadCursorFromFileW.restype = ctypes.c_void_p
    cursor = user32.LoadCursorFromFileW(os.path.join(tv.RES_ROOT, "arpg", "ui", "cursor.cur"))
    hwnd = user32.FindWindowW(None, title)
    if not cursor or not hwnd:
        print("[cursor] glove cursor not set (cursor %s, window %s)" % (bool(cursor), bool(hwnd)))
        return
    user32.SetClassLongPtrW(hwnd, -12, cursor)
    user32.SetCursor.argtypes = (ctypes.c_void_p,)
    user32.SetCursor(cursor)
    # The exe carries the stock EVE icon; the game window shows its own in the title bar and taskbar.
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.LoadImageW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
    user32.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
    icon_path = os.path.join(tv.RES_ROOT, "arpg", "ui", "app.ico")
    for which, size, slot in ((1, 32, -14), (0, 16, -34)):
        icon = user32.LoadImageW(None, icon_path, 1, size, size, 0x10)
        if icon:
            user32.SendMessageW(hwnd, 0x80, which, icon)
            user32.SetClassLongPtrW(hwnd, slot, icon)


def add_box(solids, lo, hi, color):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    center = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for quad in faces:
        a, b, c, d = (corners[i] for i in quad)
        for tri in ((a, b, c), (a, c, d)):
            p1, p2, p3 = tri
            # Tr2SolidSet derives the face normal as cross(p1 - p3, p2 - p1); wind it outward.
            n = tv.cross(tv.sub(p1, p3), tv.sub(p2, p1))
            if tv.dot(n, tv.sub(p1, center)) < 0:
                p2, p3 = p3, p2
            solids.AddTriangle(p1, color, p2, color, p3, color)


def main():
    host = os.environ.get("NET_HOST", "127.0.0.1")
    port = int(os.environ.get("NET_PORT", "47400"))
    viewer = ArpgViewer(ArpgSim(host, port, autoconnect=False))
    carbonapp.at_exit(viewer.front.stop_server)
    # ARPG_JOIN=host:port goes straight into that game (tests, the act editor's Play); otherwise the menu, with any
    # NET_HOST/NET_PORT server at the top of its list.
    if os.environ.get("ARPG_TEST_HOST") == "1":
        viewer.front.host(viewer.sim)
    elif os.environ.get("ARPG_JOIN"):
        viewer.front.connect(viewer.sim, os.environ["ARPG_JOIN"], attempts=None)
    elif os.environ.get("NET_HOST") or os.environ.get("NET_PORT"):
        viewer.front.offer("%s:%d" % (host, port))
    viewer.start()


if __name__ == "__main__":
    carbonapp.run(main)
