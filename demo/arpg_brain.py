"""The fighting mind of a computer-controlled mage: it reads the client's park and state and acts through `acts`.

The headless companion sends its acts straight to the server; the client's autopilot plays them through the viewer."""
import math

import blue

import arpg_world as world
from arpg_nav import Nav
from arpg_state import mana_at

MANA = {name: spell["mana"] for name, spell in world.SPELLS.items()}
FOLLOW_M, KEEP_CLEAR_M, ENGAGE_M = 6.0, 3.2, 14.0
SHRINE_STAND_M = 2.0
LOOT_SEEK_M = 16.0
REPLAN_S, STUCK_S, STUCK_M = 0.6, 1.0, 0.35
# Dodging: roll out of a slam or a meteor that would land on it, or across a shot about to hit.
DODGE_LEAD_S, SHOT_LOOK_S, SHOT_NEAR_M, JUMP_LEAD_S, ROLL_ODDS = 0.5, 0.35, 0.9, 0.25, 0.25
RAIN = world.KINDS["warlord"]["rain"]
_nav = None


def nav():
    """The navigation grid for the level being played, rebuilt when the level changes."""
    global _nav
    if _nav is None or _nav.level is not world.LEVEL:
        _nav = Nav()
    return _nav


class NetActs:
    """Acts as plain messages to the server."""

    def __init__(self, client):
        self.client = client

    def goto(self, x, z):
        self.client.send("goto", x, 0.0, z)

    def direction(self, ax, az):
        self.client.send("dir", ax, az)

    def stop(self):
        self.client.send("stop")

    def blink(self, x, z):
        self.client.send("blink", x, z)

    def roll(self, dx, dz):
        self.client.send("roll", dx, dz)

    def jump(self):
        self.client.send("jump")

    def cast(self, spell, x=None, z=None, yaw=None):
        if yaw is not None:
            self.client.send("aim", yaw)
        message = {"bolt": "cast"}.get(spell, spell)
        self.client.send(*((message,) if x is None else (message, x, z)))

    def pick(self, choice):
        self.client.send("pick", choice)

    def ready(self):
        self.client.send("ready", True)


class Brain:
    """Follows the nearest other player, keeps clear of melee, casts what suits the moment, hunts stragglers, and
    between waves walks to the shrine to ready up. Upgrades are spent as soon as they arrive."""

    def __init__(self, client, state, acts, rng):
        self.client, self.state, self.acts, self.rng = client, state, acts, rng
        self.next_cast = 0
        self.route, self.goal, self.replan_at = [], None, 0
        self.track, self.moving, self.unstick_until, self.unstick_dir = [], False, 0, (0.0, 0.0)
        self.dangers, self.lanes, self.roll_ready, self.jump_ready = [], [], 0, 0

    def warn(self, key, name, data):
        """Hears an event from the server; slams and meteor rain become areas to be out of when they land."""
        now = self._now()
        if name == "slam":
            ball = self.client.park.balls.get(key)
            if ball is not None:
                self.dangers.append((ball.x, ball.z, data["radius"], now + int(data["windup"] * 1e7), True))
        elif name == "rain":
            for x, z in data["points"]:
                self.dangers.append((x, z, RAIN["radius"], now + int(RAIN["delay_s"] * 1e7), True))
        elif name == "fuse":
            x, z = data["at"]
            self.dangers.append((x, z, data["radius"], now + int(data["seconds"] * 1e7), False))
        elif name == "charge":
            ball = self.client.park.balls.get(key)
            if ball is not None:
                lands = now + int(data["windup"] * 1e7)
                self.lanes.append((ball.x, ball.z) + tuple(data["to"]) + (data["width"] / 2, lands, lands + int(0.8 * 1e7)))

    def me(self):
        return self.state.get(self.client.own_ball) or {}

    def mana(self):
        return mana_at(self.me(), self.client.park.currentTime, (self.client.tick_ms or 10) / 1000.0)

    def balls(self, lo, hi):
        return [b for i, b in self.client.park.balls.items() if lo <= i < hi]

    def leader(self, own):
        humans = [b for b in self.balls(world.PLAYER_BASE, world.ENEMY_BASE)
                  if b.id != own.id and not (self.state.get(b.id) or {}).get("dead")]
        return min(humans, key=lambda b: math.hypot(b.x - own.x, b.z - own.z), default=None)

    def _now(self):
        return blue.os.GetWallclockTimeNow()

    def travel(self, own, x, z):
        """Walks toward (x, z) around the walls, replanning every so often or when the goal moves."""
        now = self._now()
        self.moving = True
        if self.goal is None or math.hypot(self.goal[0] - x, self.goal[1] - z) > 1.5 or now >= self.replan_at:
            self.route, self.goal = nav().path(own.x, own.z, x, z), (x, z)
            self.replan_at = now + int(REPLAN_S * 1e7)
        while len(self.route) > 1 and math.hypot(self.route[0][0] - own.x, self.route[0][1] - own.z) < 0.7:
            self.route.pop(0)
        self.acts.goto(*(self.route[0] if self.route else (x, z)))

    def halt(self):
        self.moving, self.goal = False, None
        self.acts.stop()

    def free_direction(self, own, ax, az):
        """(ax, az), or the nearest turn of it that doesn't walk straight into a wall."""
        for turn in (0, 30, -30, 60, -60, 90, -90, 135, -135, 180):
            a = math.radians(turn)
            dx, dz = ax * math.cos(a) - az * math.sin(a), ax * math.sin(a) + az * math.cos(a)
            if nav().clear(own.x, own.z, own.x + dx * 2.0, own.z + dz * 2.0):
                return dx, dz
        return ax, az

    def check_stuck(self, own):
        now = self._now()
        self.track = [(t, x, z) for t, x, z in self.track if now - t < STUCK_S * 1e7] + [(now, own.x, own.z)]
        t0, x0, z0 = self.track[0]
        if self.moving and now - t0 > STUCK_S * 0.8 * 1e7 and math.hypot(own.x - x0, own.z - z0) < STUCK_M:
            a = self.rng.uniform(0, 2 * math.pi)
            self.unstick_dir = self.free_direction(own, math.sin(a), math.cos(a))
            self.unstick_until = now + int(0.5 * 1e7)
            self.replan_at, self.track = 0, []
        return now < self.unstick_until

    def wanted_orb(self, own, me, anywhere=False):
        hp_low = me.get("hp", 0) < 0.7 * me.get("max_hp", 1)
        mana_low = self.mana() < 0.5 * me.get("mana_max", 1)
        best = None
        for lid, orb in self.state.entities.items():
            if not (isinstance(lid, int) and lid >= world.LOOT_BASE and "loot" in orb):
                continue
            if not (anywhere or (orb["loot"] == "health" and hp_low) or (orb["loot"] == "mana" and mana_low)):
                continue
            d = math.hypot(orb["x"] - own.x, orb["z"] - own.z)
            if (anywhere or d < LOOT_SEEK_M) and (best is None or d < best[0]):
                best = (d, orb["x"], orb["z"])
        return best

    def think(self):
        own = self.client.park.balls.get(self.client.own_ball)
        me = self.me()
        if own is None or not me or me.get("dead"):
            return
        if me.get("offer") and self.rng.random() < 0.05:
            self.acts.pick(self.rng.randrange(len(me["offer"])))
        if self.check_stuck(own):
            self.acts.direction(*self.unstick_dir)
            return
        if self.dodge(own):
            return
        game = self.state.get("game") or {}
        phase = game.get("phase", "fight")
        if phase == "advance":
            # Through the open gate and well into the next room, where the next fight starts.
            x0, _, x1, _ = world.room_rect(game.get("room", 0) + 1)
            self.travel(own, x0 + min(6.0, (x1 - x0) / 3), self.rng.uniform(-1.0, 1.0) if self.goal is None else self.goal[1])
            return
        if phase == "victory":
            self.halt()
            return
        if phase != "fight":
            orb = self.wanted_orb(own, me, anywhere=True)
            if orb is not None:
                self.travel(own, orb[1], orb[2])
            else:
                self.use_shrine(own, me)
            return
        enemies = sorted(((math.hypot(e.x - own.x, e.z - own.z), e) for e in self.balls(world.ENEMY_BASE, world.PROJECTILE_BASE)),
                         key=lambda pair: pair[0])
        self.move(own, me, enemies)
        self.attack(own, me, enemies)

    def dodge(self, own):
        now = self._now()
        self.dangers = [d for d in self.dangers if d[3] > now]
        self.lanes = [lane for lane in self.lanes if lane[6] > now]
        away, landing = self.lane_escape(own, now), None
        for x, z, radius, lands, ground in self.dangers if away is None else ():
            d = math.hypot(own.x - x, own.z - z)
            if d < radius + world.PLAYER_RADIUS and lands - now < DODGE_LEAD_S * 1e7:
                away = ((own.x - x) / d, (own.z - z) / d) if d > 1e-3 else (1.0, 0.0)
                landing = lands if ground else None
                break
        # A ground hit about to land can be hopped over; otherwise roll clear of it now and then, or wait to hop.
        if landing is not None and now >= self.jump_ready and landing - now < JUMP_LEAD_S * 1e7:
            self.jump_ready = now + int((world.JUMP["s"] + world.JUMP["cooldown_s"] + 0.1) * 1e7)
            self.acts.jump()
            return False
        if now < self.roll_ready or (landing is not None and now >= self.jump_ready and self.rng.random() > ROLL_ODDS):
            return False
        if away is None:
            away = self.shot_coming(own)
        if away is None:
            return False
        self.roll_ready = now + int((world.ROLL["cooldown_s"] + 0.1) * 1e7)
        self.moving, self.goal = True, None
        self.acts.roll(*self.free_direction(own, *away))
        return True

    def lane_escape(self, own, now):
        """Sideways out of a hound's lane when its charge is close, else None; a charge can't be jumped."""
        for ax, az, bx, bz, half, lands, _ in self.lanes:
            if lands - now > DODGE_LEAD_S * 1e7:
                continue
            lx, lz = bx - ax, bz - az
            length2 = lx * lx + lz * lz or 1.0
            t = max(0.0, min(1.0, ((own.x - ax) * lx + (own.z - az) * lz) / length2))
            mx, mz = own.x - (ax + lx * t), own.z - (az + lz * t)
            if math.hypot(mx, mz) < half + 0.3:
                length = math.sqrt(length2)
                side = 1.0 if mx * -lz + mz * lx >= 0 else -1.0
                return -lz / length * side, lx / length * side
        return None

    def shot_coming(self, own):
        """A sideways direction to roll if an enemy shot will pass close by within SHOT_LOOK_S, else None."""
        for shot in self.balls(world.SPIT_BASE, world.LOOT_BASE):
            rx, rz = own.x - shot.x, own.z - shot.z
            speed2 = shot.vx * shot.vx + shot.vz * shot.vz
            if speed2 < 1.0:
                continue
            t = (rx * shot.vx + rz * shot.vz) / speed2
            if not 0.0 < t < SHOT_LOOK_S:
                continue
            mx, mz = rx - shot.vx * t, rz - shot.vz * t
            if math.hypot(mx, mz) < SHOT_NEAR_M + world.PLAYER_RADIUS:
                speed = math.sqrt(speed2)
                side = 1.0 if (mx * -shot.vz + mz * shot.vx) >= 0 else -1.0
                return (-shot.vz / speed * side, shot.vx / speed * side)
        return None

    def use_shrine(self, own, me):
        sx, sz = world.SHRINE
        if math.hypot(own.x - sx, own.z - sz) > world.SHRINE_RANGE - 0.4:
            self.travel(own, sx + SHRINE_STAND_M * 0.7, sz - SHRINE_STAND_M * 0.7)
            return
        self.halt()
        if not me.get("ready"):
            self.acts.ready()

    def move(self, own, me, enemies):
        leader = self.leader(own)
        # Bloaters are kept further off than the rest: their fuse lights within a couple of metres.
        close = [e for d, e in enemies if d < KEEP_CLEAR_M + e.radius + (1.5 if self.kind(e) == "bloater" else 0.0)]
        hurt = me.get("hp", 0) < 0.35 * me.get("max_hp", 1)
        orb = None if close else self.wanted_orb(own, me)
        if close:
            ax = sum(own.x - e.x for e in close)
            az = sum(own.z - e.z for e in close)
            n = math.hypot(ax, az) or 1.0
            ax, az = self.free_direction(own, ax / n, az / n)
            reach = world.SPELLS["blink"]["range"]
            self.moving, self.goal = True, None
            if hurt and self.mana() >= MANA["blink"]:
                self.acts.blink(*world.blink_target(own.x, own.z, own.x + ax * reach, own.z + az * reach))
            else:
                self.acts.direction(ax, az)
        elif orb is not None:
            self.travel(own, orb[1], orb[2])
        elif enemies and (enemies[0][0] > ENGAGE_M or not self.clear_shot(own, enemies[0][1])):
            # Nothing to shoot from here: go and find it, around the walls.
            _, e = enemies[0]
            self.travel(own, e.x, e.z)
        elif leader is not None and math.hypot(leader.x - own.x, leader.z - own.z) > FOLLOW_M:
            side = 1.0 if own.id % 2 else -1.0
            self.travel(own, leader.x + side * 2.0, leader.z + 2.0)
        else:
            self.halt()

    def kind(self, e):
        return (self.state.get(e.id) or {}).get("kind")

    def shielded(self, own, e):
        """True if e is a shieldbearer facing this mage, so a bolt from here would be blocked."""
        face = (self.state.get(e.id) or {}).get("face")
        if self.kind(e) != "shieldbearer" or face is None:
            return False
        to_me = math.atan2(own.x - e.x, own.z - e.z)
        arc = world.KINDS["shieldbearer"]["shield"]["arc_deg"]
        return abs((to_me - face + math.pi) % (2 * math.pi) - math.pi) < math.radians(arc / 2)

    def clear_shot(self, own, e):
        return not world.segment_hits_box(own.x, own.z, e.x, e.z, world.PROJECTILE_RADIUS)

    def attack(self, own, me, enemies):
        now = blue.os.GetWallclockTimeNow()
        if now < self.next_cast or not enemies:
            return
        self.next_cast = now + int(self.rng.uniform(0.22, 0.4) * 1e7)
        level, mana = me.get("level", 1), self.mana()
        d, target = enemies[0]
        # A shaman in sight is shot first: left alone it keeps its pack healed and hurried.
        for dist, e in enemies:
            if dist < ENGAGE_M and self.kind(e) == "shaman" and self.clear_shot(own, e):
                d, target = dist, e
                break
        if self.shielded(own, target):
            # A bolt would only glance off that shield: pick something else, or reach round it with chain lightning.
            other = next(((dist, e) for dist, e in enemies if dist < ENGAGE_M and not self.shielded(own, e)
                          and self.clear_shot(own, e)), None)
            if other is not None:
                d, target = other
            elif world.spell_unlocked("chain", level) and mana >= MANA["chain"]:
                self.acts.cast("chain", target.x, target.z, math.atan2(target.x - own.x, target.z - own.z))
                return
            else:
                return
        nova_r = world.spell(me, "nova")["radius"]
        near = sum(1 for dist, e in enemies if dist < nova_r + e.radius)
        if near >= 3 and mana >= MANA["nova"]:
            self.acts.cast("nova")
            return
        if d > ENGAGE_M or not self.clear_shot(own, target):
            return
        lead = d / world.SPELLS["bolt"]["speed"]
        tx, tz = target.x + target.vx * lead, target.z + target.vz * lead
        cluster = max(enemies, key=lambda pair: sum(1 for _, o in enemies if math.hypot(o.x - pair[1].x, o.z - pair[1].z) < 3.0))[1]
        packed = sum(1 for _, o in enemies if math.hypot(o.x - cluster.x, o.z - cluster.z) < 3.0)

        def aimed(spell, x, z):
            self.acts.cast(spell, x, z, math.atan2(x - own.x, z - own.z))

        if world.spell_unlocked("meteor", level) and packed >= 4 and mana >= MANA["meteor"] + 10:
            aimed("meteor", cluster.x, cluster.z)
        elif world.spell_unlocked("frost", level) and sum(1 for dist, _ in enemies if dist < 6.0) >= 2 and mana >= MANA["frost"] + 10:
            aimed("frost", target.x, target.z)
        elif world.spell_unlocked("chain", level) and len(enemies) >= 2 and mana >= MANA["chain"] + 10 and self.rng.random() < 0.5:
            aimed("chain", target.x, target.z)
        elif mana >= MANA["bolt"]:
            aimed("bolt", tx, tz)
