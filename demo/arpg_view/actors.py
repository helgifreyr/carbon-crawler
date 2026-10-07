import math

import blue

from arpg_anim import FADE_S, Animator, find_params, heading_sign, table
from arpg_view.events import Event
from arpg_view.geometry import axis_quat, quat_mul
from arpg_world import KINDS, PLAYER_BASE

ROLE_PLACEABLES = {
    "you": "player_self",
    "player": "player_other",
    "dead": "player_dead",
    "enemy": "enemy",
    "spitter": "spitter",
    "brute": "brute",
    "warlord": "warlord",
    "shaman": "shaman",
    "hound": "hound",
    "bloater": "bloater",
    "shieldbearer": "shieldbearer",
    "projectile": "projectile",
    "spit": "spit",
    "bossshot": "bossshot",
}
# Each player keeps one colour on every screen, by the order they joined; your own mage is marked by its ring.
PLAYER_COLORS = ("self", "other", "purple", "amber")
KIND_ROLES = {"imp": "enemy", "spitter": "spitter", "brute": "brute", "warlord": "warlord", "shaman": "shaman", "hound": "hound",
              "bloater": "bloater", "shieldbearer": "shieldbearer"}
ENEMY_ROLES = tuple(KIND_ROLES.values())
ROLE_MODELS = {"you": "player", "player": "player", "dead": "player", "enemy": "enemy", "spitter": "enemy",
               "brute": "enemy", "warlord": "enemy", "shaman": "shaman", "hound": "hound", "bloater": "bloater",
               "shieldbearer": "shieldbearer"}
# The clip each event plays on its actor, and how fast; a slam's clip is stretched over its windup.
EVENT_CLIPS = {"cast": "cast", "attack": "attack", "nova": "cast", "slam": "attack", "chain": "cast", "meteor": "cast",
               "frost": "cast", "ring": "attack", "rain": "attack", "enrage": "attack", "roll": "roll", "jump": "jump",
               "mend": "attack", "charge": "charge"}
# The hound's crouch (0.625 s) is stretched over its 0.75 s wind-up.
EVENT_RATES = {"slam": 0.34, "enrage": 0.4, "charge": 0.83}
# A roll is over in a third of a second, so it blends in faster than the usual crossfade.
EVENT_FADES = {"roll": 0.04, "jump": 0.04}
SLAM_WINDUP_S = KINDS["brute"]["slam"]["windup_s"]
SLOW_TINT, HASTE_TINT = (0.55, 0.8, 1.0, 0.6), (0.35, 1.0, 0.8, 0.2)
LOOT_BOB_M, LOOT_BOB_HZ, LOOT_SPIN = 0.08, 1.2, 1.6
HITSTOP_S = 0.07
TELEPORT_M = 2.0
FACE_TARGET_M = {"enemy": 4.0, "brute": 4.5, "spitter": 13.0, "warlord": 40.0, "shaman": 14.0, "hound": 12.0, "bloater": 3.0,
                 "shieldbearer": 6.0}
BOLT_LIFETIME_S = 1.5
ONE_SHOTS = ("cast", "attack", "roll", "jump")
VAT_PARAMS = ("VatState", "VatFade", "Flash", "Tint")
TURN_RATE = 14.0
HIT_FLASH_S = 0.14
FLASH_PEAK = 0.85
MOVING_SPEED = 0.6
LEAN = {"you": 0.16, "player": 0.16, "enemy": 0.22, "spitter": 0.2, "brute": 0.12, "warlord": 0.08, "shaman": 0.18, "hound": 0.12,
        "bloater": 0.1, "shieldbearer": 0.1}
FULL_SPEED = {"you": 7.0, "player": 7.0, "enemy": 4.5, "spitter": 3.8, "brute": 2.4, "warlord": 3.4, "shaman": 3.2, "hound": 4.6,
              "bloater": 2.0, "shieldbearer": 2.2}
ENEMY_SIZES = {"enemy": (0.9, 1.1), "spitter": (0.74, 0.84), "brute": (1.6, 1.75), "warlord": (2.5, 2.5),
               "shaman": (0.95, 1.05), "hound": (1.2, 1.32), "bloater": (1.0, 1.1), "shieldbearer": (1.3, 1.4)}
CORPSE_HOLD_S, CORPSE_SINK_S, CORPSE_SINK_DEPTH = 2.0, 1.2, 1.2
# Bolts fly at chest height; a new one starts at its caster's staff orb and eases onto its real path.
BOLT_LIFT, BOLT_BLEND_M, CASTER_SEARCH_M = 0.35, 1.2, 2.5
CASTER_ROLES = ("you", "player")
MISSILE_ROLES = ("projectile", "spit", "bossshot")
POSE_LOD_M, POSE_LOD_EVERY = 15.0, 3


def muzzle():
    meta = table("player")
    clip = meta["clips"]["cast"]
    return meta["sockets"]["orb"][clip["row"] + round(clip["events"]["release"] * (clip["frames"] - 1))]


def player_color(key):
    return PLAYER_COLORS[(key - PLAYER_BASE - 1) % len(PLAYER_COLORS)]


def orb_world(actor):
    """Where the staff orb is at a cast's release, for an actor at its last drawn pose."""
    mx, my, mz = muzzle()
    yaw = actor.yaw or 0.0
    c, s = math.cos(yaw), math.sin(yaw)
    return actor.last[0] + mx * c + mz * s, actor.last[1] + my, actor.last[2] - mx * s + mz * c


class Actor:
    def __init__(self, role, key):
        self.placeable = None
        self.role = None
        self.yaw = None
        self.last = None
        self.velocity = (0.0, 0.0)
        self.speed = 0.0
        self.last_hp = None
        self.flash_start = None
        self.flash_written = 0.0
        self.tinted, self.tint_written = None, (0.0, 0.0, 0.0, 0.0)
        self.hitstop_until = 0
        self.key = key
        self.size = 1.0
        if role in ENEMY_SIZES:
            lo, hi = ENEMY_SIZES[role]
            self.size = lo + (hi - lo) * ((key * 2654435761) % 1000) / 999.0
        model = ROLE_MODELS.get(role)
        self.animator = Animator(model) if model else None
        self.params = None
        self.corpse_age = None
        self.bolt_offset = None
        self.fx_params = None
        self.travel = 0.0
        self.age = 0.0

    def rolling(self):
        return self.animator is not None and self.animator.playing() == "roll" and not self.animator.finished()


class Actors:
    """One placeable per drawn ball and loot orb: role, movement, facing, clips, hit flash, corpses.

    Damage, deaths and missile impacts it notices are emitted on the bus as damaged / died / impact events."""

    def __init__(self, stage, bus):
        self.stage, self.bus = stage, bus
        self.actors = {}
        self.corpses = []
        self.loot = {}
        bus.on(EVENT_CLIPS, self.on_event)

    def get(self, key):
        return self.actors.get(key)

    def on_event(self, event):
        actor = event.actor
        if not event.animate or actor is None or actor.animator is None:
            return
        rate = EVENT_RATES.get(event.name, 1.0)
        if event.name == "slam":
            rate *= SLAM_WINDUP_S / event.data.get("windup", SLAM_WINDUP_S)
        actor.animator.play(EVENT_CLIPS[event.name], restart=True, rate=rate, fade_s=EVENT_FADES.get(event.name, FADE_S))

    def _set_role(self, actor, role):
        if actor.placeable is not None:
            self.stage.remove(actor.placeable)
        name = "player_" + player_color(actor.key) if role in CASTER_ROLES else ROLE_PLACEABLES[role]
        actor.placeable = self.stage.placeable(name)
        actor.placeable.scaling = (actor.size,) * 3
        actor.role = role
        actor.params = None
        self.stage.add(actor.placeable)

    def sync(self, tracked, render_tick, dt, aims=None):
        aims = aims or {}
        now = blue.os.GetWallclockTimeNow()
        present = set()
        # Enemies near a player face that player, not their movement: pressed up against one, collision corrections
        # keep shoving them backwards and a movement-facing imp would flip away and back.
        targets = [a.last for a in self.actors.values() if a.role in CASTER_ROLES and a.last is not None]
        for t in tracked:
            role = t.name.split(" ")[0]
            if role not in ROLE_PLACEABLES:
                continue
            key = t.ball.id
            present.add(key)
            entity = getattr(t, "entity", None) or {}
            if role == "enemy":
                # An enemy's kind arrives on the state channel; until then (a tick at most) it isn't drawn.
                if "kind" not in entity:
                    continue
                role = KIND_ROLES[entity["kind"]]
            actor = self.actors.get(key)
            if actor is None:
                actor = self.actors[key] = Actor(role, key)
                if role == "projectile":
                    actor.bolt_offset = self._launch_offset(t.position(render_tick))
            if actor.role != role:
                self._set_role(actor, role)
            actor.age += dt
            actor.tinted = (SLOW_TINT if render_tick < entity.get("slowed", -1)
                            else HASTE_TINT if render_tick < entity.get("hasted", -1) else None)
            self._watch_hp(actor, entity, now)
            aim = aims.get(key)
            if aim is None and "face" in entity:
                aim = entity["face"]
            if actor.rolling():
                aim = None
            if aim is None and role in ENEMY_ROLES:
                aim = self._face_target(actor, targets)
            self._move(actor, role, t.position(render_tick), dt, aim, key in aims and role == "you")
            if actor.animator is not None:
                self._choose_clip(actor, role == "dead" or entity.get("dead"))
                self._animate(actor, dt, now)
        for key in [k for k in self.actors if k not in present]:
            actor = self.actors.pop(key)
            if actor.role in ENEMY_ROLES and actor.animator is not None:
                actor.animator.play("death")
                actor.corpse_age = 0.0
                self.corpses.append(actor)
                self.bus.emit(Event("died", key, actor=actor))
            else:
                if actor.role in MISSILE_ROLES and actor.age < BOLT_LIFETIME_S - 0.1:
                    self.bus.emit(Event("impact", key, actor=actor))
                self.stage.remove(actor.placeable)
        self._update_corpses(dt, now)

    def sync_loot(self, items):
        """Loot orbs from the state channel (id -> {loot, x, z}), bobbing and turning where they lie."""
        for lid in [k for k in self.loot if k not in items]:
            self.stage.remove(self.loot.pop(lid)[0])
        for lid, entity in items.items():
            if lid not in self.loot:
                placeable = self.stage.placeable("loot_" + entity["loot"])
                self.stage.add(placeable)
                self.loot[lid] = (placeable, entity["x"], entity["z"], (lid * 0.61) % 1.0)
            placeable, x, z, phase = self.loot[lid]
            t = self.stage.clock + phase * 3.0
            placeable.translation = (x, LOOT_BOB_M * math.sin(2 * math.pi * LOOT_BOB_HZ * t), z)
            placeable.rotation = axis_quat((0.0, 1.0, 0.0), t * LOOT_SPIN)

    def _watch_hp(self, actor, entity, now):
        if "hp" not in entity:
            return
        if actor.last_hp is not None and entity["hp"] < actor.last_hp:
            actor.flash_start = now
            actor.hitstop_until = now + int(HITSTOP_S * 1e7)
            if actor.last is not None:
                self.bus.emit(Event("damaged", actor.key, {"amount": actor.last_hp - entity["hp"]}, actor))
        actor.last_hp = entity["hp"]

    def _face_target(self, actor, targets):
        if actor.last is None or not targets:
            return None
        x, _, z = actor.last
        tx, _, tz = min(targets, key=lambda p: (p[0] - x) ** 2 + (p[2] - z) ** 2)
        if (tx - x) ** 2 + (tz - z) ** 2 > (FACE_TARGET_M[actor.role] + actor.size) ** 2:
            return None
        return math.atan2(tx - x, tz - z)

    def _launch_offset(self, pos):
        best, best_d = None, CASTER_SEARCH_M
        for actor in self.actors.values():
            if actor.role in CASTER_ROLES and actor.last is not None:
                d = math.hypot(actor.last[0] - pos[0], actor.last[2] - pos[2])
                if d < best_d:
                    best, best_d = actor, d
        if best is None:
            return None
        wx, wy, wz = orb_world(best)
        return (wx - pos[0], wy - (pos[1] + BOLT_LIFT), wz - pos[2])

    def _choose_clip(self, actor, dead):
        animator = actor.animator
        playing = animator.playing()
        if dead:
            animator.play("death")
        elif playing == "death":
            animator.play("idle")
        elif playing in ONE_SHOTS and not animator.finished():
            return
        else:
            animator.play("walk" if actor.speed > MOVING_SPEED else "idle")

    def _animate(self, actor, dt, now):
        animator = actor.animator
        if now < actor.hitstop_until:
            dt = 0.0
        distance = None
        if animator.playing() == "walk" or (animator.previous and animator.previous.clip == "walk"):
            distance = actor.speed * dt * heading_sign(actor.velocity, actor.yaw or 0.0)
        animator.advance(dt, distance)
        if actor.params is None:
            actor.params = find_params(actor.placeable, VAT_PARAMS)
            if actor.params is None:
                return
        # Far from the camera focus the pose is only written every POSE_LOD_EVERY frames, staggered per ball.
        focus = self.stage.focus
        if focus is not None and actor.last is not None and actor.corpse_age is None:
            far = (actor.last[0] - focus[0]) ** 2 + (actor.last[2] - focus[2]) ** 2 > POSE_LOD_M ** 2
            if far and (self.stage.frame + actor.key) % POSE_LOD_EVERY:
                return
        state, fade = animator.params()
        for p in actor.params["VatState"]:
            p.value = state
        for p in actor.params["VatFade"]:
            p.value = fade
        flash = 0.0
        if actor.flash_start is not None:
            flash = max(0.0, 1.0 - (now - actor.flash_start) / (HIT_FLASH_S * 1e7)) * FLASH_PEAK
        if flash != actor.flash_written:
            for p in actor.params["Flash"]:
                p.value = (flash, 0.0, 0.0, 0.0)
            actor.flash_written = flash
        tint = actor.tinted or (0.0, 0.0, 0.0, 0.0)
        if tint != actor.tint_written:
            for p in actor.params["Tint"]:
                p.value = tint
            actor.tint_written = tint

    def _update_corpses(self, dt, now):
        for actor in list(self.corpses):
            actor.corpse_age += dt
            actor.speed = 0.0
            self._animate(actor, dt, now)
            sinking = actor.corpse_age - CORPSE_HOLD_S - 1.0
            if sinking > 0:
                x, y, z = actor.placeable.translation
                actor.placeable.translation = (x, y - CORPSE_SINK_DEPTH * dt / CORPSE_SINK_S, z)
            if sinking > CORPSE_SINK_S:
                self.corpses.remove(actor)
                self.stage.remove(actor.placeable)

    def _move(self, actor, base_role, pos, dt, aim, snap_aim):
        target = aim
        if actor.last is not None and dt > 0:
            dx, dz = pos[0] - actor.last[0], pos[2] - actor.last[2]
            if dx * dx + dz * dz > TELEPORT_M ** 2:
                dx = dz = 0.0
            k = min(1.0, 12.0 * dt)
            vx, vz = actor.velocity
            actor.velocity = (vx + (dx / dt - vx) * k, vz + (dz / dt - vz) * k)
            actor.speed = math.hypot(*actor.velocity)
            if target is None and math.hypot(dx, dz) > 1e-3:
                target = math.atan2(dx, dz)
        actor.last = pos
        if target is not None:
            if actor.yaw is None or snap_aim or base_role in MISSILE_ROLES:
                actor.yaw = target
            else:
                delta = (target - actor.yaw + math.pi) % (2 * math.pi) - math.pi
                actor.yaw += delta * min(1.0, TURN_RATE * dt)
        rotation = axis_quat((0.0, 1.0, 0.0), actor.yaw or 0.0)
        lean = LEAN.get(base_role)
        if lean and actor.speed > 1e-3 and not actor.rolling():
            # Lean into the direction of travel, whichever way the body faces.
            effort = min(1.0, actor.speed / FULL_SPEED[base_role])
            mx, mz = actor.velocity[0] / actor.speed, actor.velocity[1] / actor.speed
            rotation = quat_mul(axis_quat((mz, 0.0, -mx), lean * effort), rotation)
        x, y, z = pos
        if base_role in MISSILE_ROLES:
            if actor.fx_params is None:
                actor.fx_params = find_params(actor.placeable, ("FxTime",))
            for p in (actor.fx_params or {}).get("FxTime", ()):
                p.value = (actor.age, 1.0, 0.0, 0.0)
            if actor.last is not None:
                actor.travel += actor.speed * dt
            y += BOLT_LIFT
            if actor.bolt_offset is not None:
                k = math.exp(-actor.travel / BOLT_BLEND_M)
                x, y, z = x + actor.bolt_offset[0] * k, y + actor.bolt_offset[1] * k, z + actor.bolt_offset[2] * k
        actor.placeable.translation = (x, y + 0.5 * (actor.size - 1.0), z)
        actor.placeable.rotation = rotation
