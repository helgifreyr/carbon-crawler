import itertools
import math

import destiny

import arpg_world as world
from arpg_game import combat, projectiles, spatial, spells
from arpg_game.components import (BEHAVIOURS, Burster, Charger, Charging, Cooldown, Enemy, Enrage, Hasted, KeepRange, Melee,
                                  Mend, Rain, Ring, Shield, Slammer, Slowed, Spit, Winding)
from scene import add_ball

_ids = itertools.count(world.ENEMY_BASE)


def spawn(g, kind):
    """Adds an enemy ball of this kind, with one component per behaviour its KINDS entry lists."""
    spec = world.KINDS[kind]
    spot = spatial.free_spot(g, (-world.ROOM_W / 2 + 2, world.ROOM_W / 2 - 2), min_player_distance=12.0,
                             min_gap=1.5 + spec["radius"])
    if spot is None:
        return None
    eid = next(_ids)
    speed = g.rng.uniform(*spec["speed"])
    add_ball(g.park, eid, x=spot[0], z=spot[1], radius=spec["radius"], max_velocity=speed, agility=world.ENEMY_AGILITY)
    g.ents.add(eid, Enemy(kind, spec, speed), Cooldown(spec["cooldown_s"], spec.get("jitter", 0.0)),
               *(component(**spec[key]) for key, component in BEHAVIOURS.items() if key in spec))
    g.corrections.watch(eid)
    g.state.spawn(eid, hp=spec["hp"], max_hp=spec["hp"], kind=kind)
    return eid


def _rearm(g, eid, cooldown):
    enrage = g.ents.get(eid, Enrage)
    every = enrage.cooldown_s if enrage is not None and enrage.active else cooldown.every_s
    if cooldown.jitter:
        every *= g.rng.uniform(1.0 - cooldown.jitter, 1.0 + cooldown.jitter)
    cooldown.ready = g.park.currentTime + g.ticks_for(every)


def melee(g, grid):
    tick = g.park.currentTime
    for p in g.alive_players():
        for eid, ex, ez, er in grid.around(p.x, p.z):
            hit, cooldown = g.ents.get(eid, Melee), g.ents.get(eid, Cooldown)
            if hit is None or cooldown.ready > tick or g.ents.has(eid, Charging):
                continue
            reach = world.PLAYER_RADIUS + er + hit.reach
            if (ex - p.x) ** 2 + (ez - p.z) ** 2 > reach * reach:
                continue
            _rearm(g, eid, cooldown)
            g.state.event(eid, "attack")
            combat.hurt_player(g, p.id, hit.damage)
            if not g.alive(p.id):
                break


def attack(g):
    """Slams, ring volleys and rain for every enemy that has them, paced by its cooldown; bosses enrage here too."""
    tick = g.park.currentTime
    players = g.alive_players()
    for eid, enrage, enemy in g.ents.each(Enrage, Enemy):
        _check_enrage(g, eid, enrage, enemy)
    for eid, mend, cooldown in g.ents.each(Mend, Cooldown):
        if tick >= cooldown.ready:
            _mend(g, eid, mend, cooldown)
    ents, balls = g.ents, g.park.balls
    for eid in ents.of(Slammer).keys() | ents.of(Ring).keys() | ents.of(Rain).keys():
        e, cooldown = balls.get(eid), ents.get(eid, Cooldown)
        if e is None or cooldown is None:
            continue
        winding = g.ents.get(eid, Winding)
        if winding is not None:
            if tick >= winding.end:
                g.ents.discard(eid, Winding)
                _rearm(g, eid, cooldown)
                for pl in players:
                    if math.hypot(pl.x - e.x, pl.z - e.z) <= winding.radius + world.PLAYER_RADIUS:
                        combat.hurt_player(g, pl.id, winding.damage, ground=True)
            continue
        if tick < cooldown.ready or not players:
            continue
        slam = g.ents.get(eid, Slammer)
        nearest = min(math.hypot(pl.x - e.x, pl.z - e.z) for pl in players)
        if slam is not None and nearest < slam.reach + e.radius:
            g.sync.actions.stop(eid)
            g.ents.add(eid, Winding(tick + g.ticks_for(slam.windup_s), slam.radius, slam.damage))
            g.state.event(eid, "slam", radius=slam.radius, windup=slam.windup_s)
            continue
        enraged = g.ents.get(eid, Enrage)
        enraged = enraged is not None and enraged.active
        ranged = [c for c in (g.ents.get(eid, Ring), g.ents.get(eid, Rain))
                  if c is not None and (enraged or not getattr(c, "enraged_only", False))]
        if ranged:
            volley = g.rng.choice(ranged)
            (_ring if isinstance(volley, Ring) else _rain)(g, eid, e, volley, players)
            _rearm(g, eid, cooldown)


def _check_enrage(g, eid, enrage, enemy):
    entity = g.state.get(eid)
    if enrage.active or entity is None or entity["hp"] > entity["max_hp"] * enrage.at:
        return
    enrage.active = True
    enemy.base_speed *= enrage.speedup
    g.sync.actions.set_max_speed(eid, enemy.base_speed)
    g.state.event(eid, "enrage")
    g.waves.queue.extend([enrage.summon_kind] * enrage.summon)


def bursters(g):
    """Bloaters light their fuse next to a player, and pop when it runs out."""
    tick, balls = g.park.currentTime, g.park.balls
    players = g.alive_players()
    for eid, burster in g.ents.each(Burster):
        e = balls.get(eid)
        if e is None:
            continue
        if burster.lit:
            if burster.pops_at and tick >= burster.pops_at and g.ents.has(eid, Enemy):
                combat.kill_enemy(g, eid, None)
        elif any(math.hypot(p.x - e.x, p.z - e.z) <= burster.trigger_m + e.radius for p in players):
            combat.light_burst(g, eid, burster, None, pop=True)


def turn_shields(g, dt):
    """Shields swing toward the nearest player at their turn rate; the facing goes out when it has moved enough."""
    players = g.alive_players()
    balls = g.park.balls
    for eid, shield in g.ents.each(Shield):
        e = balls.get(eid)
        if e is None or not players:
            continue
        target = min(players, key=lambda p: (p.x - e.x) ** 2 + (p.z - e.z) ** 2)
        want = math.atan2(target.x - e.x, target.z - e.z)
        delta = (want - shield.yaw + math.pi) % (2 * math.pi) - math.pi
        step = shield.turn_rate * dt
        shield.yaw += max(-step, min(step, delta))
        if abs((shield.yaw - shield.sent + math.pi) % (2 * math.pi) - math.pi) > 0.08:
            shield.sent = shield.yaw
            g.state.set(eid, face=round(shield.yaw, 2))



def charge(g):
    """Hounds: aim down a line at a player, rush along it hitting whoever is in the way, and reel if a wall stops them."""
    tick, balls = g.park.currentTime, g.park.balls
    players = g.alive_players()
    for eid, ch, enemy in g.ents.each(Charger, Enemy):
        e = balls.get(eid)
        if e is None:
            continue
        state = g.ents.get(eid, Charging)
        if state is None:
            _start_charge(g, eid, e, ch, players, tick)
        elif state.phase == "aim" and tick >= state.until:
            g.sync.actions.set_max_speed(eid, ch.speed)
            g.sync.actions.go_to_direction(eid, state.dx, 0.0, state.dz)
            state.phase, state.until = "run", tick + g.ticks_for(ch.distance / ch.speed)
        elif state.phase == "run":
            for pl in players:
                if pl.id not in state.hit and math.hypot(pl.x - e.x, pl.z - e.z) <= e.radius + world.PLAYER_RADIUS + 0.15:
                    state.hit.add(pl.id)
                    g.stats["charge_hits"] += 1
                    combat.hurt_player(g, pl.id, ch.damage)
            wall = world.inside_box(e.x + state.dx * (e.radius + 0.25), e.z + state.dz * (e.radius + 0.25))
            if wall or tick >= state.until:
                g.sync.actions.stop(eid)
                g.sync.actions.set_max_speed(eid, enemy.base_speed * (world.SLOW_FACTOR if g.ents.has(eid, Slowed) else 1.0))
                if wall:
                    state.phase, state.until = "stunned", tick + g.ticks_for(ch.stun_s)
                    g.stats["stuns"] += 1
                    g.state.event(eid, "stunned", seconds=ch.stun_s)
                else:
                    g.ents.discard(eid, Charging)
        elif state.phase == "stunned" and tick >= state.until:
            g.ents.discard(eid, Charging)


def _start_charge(g, eid, e, ch, players, tick):
    if tick < ch.ready or not players:
        return
    target = min(players, key=lambda p: (p.x - e.x) ** 2 + (p.z - e.z) ** 2)
    d = math.hypot(target.x - e.x, target.z - e.z)
    if not ch.min_range <= d <= ch.max_range or world.segment_hits_box(e.x, e.z, target.x, target.z, e.radius):
        return
    dx, dz = (target.x - e.x) / d, (target.z - e.z) / d
    # The rush carries on past the player; the line shown stops where a wall will.
    reach = ch.distance
    for k in range(1, int(ch.distance / 0.25) + 1):
        if world.inside_box(e.x + dx * k * 0.25, e.z + dz * k * 0.25, e.radius):
            reach = k * 0.25
            break
    g.sync.actions.stop(eid)
    g.ents.add(eid, Charging("aim", tick + g.ticks_for(ch.windup_s), dx, dz))
    ch.ready = tick + g.ticks_for(ch.cooldown_s)
    g.stats["charges"] += 1
    g.state.event(eid, "charge", to=(round(e.x + dx * reach, 2), round(e.z + dz * reach, 2)), windup=ch.windup_s,
                  width=round(2 * (e.radius + world.PLAYER_RADIUS), 2))


def _mend(g, eid, mend, cooldown):
    """Heals and hastens every other enemy in reach; the links drawn on the client show who was touched."""
    e = g.park.balls.get(eid)
    if e is None:
        return
    touched = []
    for oid, other, d in combat.enemies_near(g, e.x, e.z, mend.radius):
        entity = g.state.get(oid)
        if oid == eid or entity is None:
            continue
        touched.append(oid)
        g.state.heal(oid, mend.heal)
        hasten(g, oid, mend.haste, mend.haste_s)
    if not touched:
        cooldown.ready = g.park.currentTime + g.ticks_for(0.5)
        return
    _rearm(g, eid, cooldown)
    g.stats["mends"] += 1
    g.state.event(eid, "mend", targets=touched)


def hasten(g, eid, factor, seconds):
    enemy = g.ents.get(eid, Enemy)
    if enemy is None:
        return
    until = g.park.currentTime + g.ticks_for(seconds)
    if not g.ents.has(eid, Slowed):
        g.sync.actions.set_max_speed(eid, enemy.base_speed * factor)
    g.ents.add(eid, Hasted(until))
    g.state.set(eid, hasted=until)


def expire_hastes(g):
    tick = g.park.currentTime
    for eid, hasted, enemy in g.ents.each(Hasted, Enemy):
        if tick >= hasted.until:
            g.ents.discard(eid, Hasted)
            if not g.ents.has(eid, Slowed):
                g.sync.actions.set_max_speed(eid, enemy.base_speed)


def _ring(g, eid, e, ring, players):
    offset = g.rng.uniform(0, 2 * math.pi)
    for k in range(ring.shots):
        a = offset + 2 * math.pi * k / ring.shots
        projectiles.enemy_shot(g, e, math.sin(a), math.cos(a), "bossshot", ring.speed, ring.damage)
    g.state.event(eid, "ring")


def _rain(g, eid, e, rain, players):
    impact = g.park.currentTime + g.ticks_for(rain.delay_s)
    points = []
    for pl in players:
        for k in range(rain.per_player):
            spread = 0.0 if k == 0 else 3.5
            a = g.rng.uniform(0, 2 * math.pi)
            x = max(-world.ROOM_W / 2 + 1, min(world.ROOM_W / 2 - 1, pl.x + spread * math.sin(a)))
            z = max(-world.ROOM_D / 2 + 1, min(world.ROOM_D / 2 - 1, pl.z + spread * math.cos(a)))
            points.append((round(x, 2), round(z, 2)))
            spells.strike_later(g, impact, x, z, rain.radius, rain.damage, None, "players")
    g.state.event(eid, "rain", points=points)


def steer(g, aggro):
    """Movement for every enemy: chase the nearest player, hold a firing distance, or wander when nobody is near."""
    players = g.alive_players()
    tick, balls = g.park.currentTime, g.park.balls
    for eid, enemy in g.ents.each(Enemy):
        e = balls.get(eid)
        if e is None or g.ents.has(eid, Winding) or g.ents.has(eid, Charging):
            continue
        burster = g.ents.get(eid, Burster)
        if burster is not None and burster.lit:
            continue
        target = min(players, key=lambda p: (p.x - e.x) ** 2 + (p.z - e.z) ** 2, default=None)
        d = math.hypot(target.x - e.x, target.z - e.z) if target is not None else 1e9
        keep = g.ents.get(eid, KeepRange)
        if d < aggro and keep is not None:
            _keep_range(g, eid, e, keep, target, d, tick)
        elif d < aggro:
            g.sync.actions.follow_ball(eid, target.id, world.PLAYER_RADIUS + e.radius + 0.2)
        elif e.mode != destiny.DSTBALL_GOTO and g.rng.random() < 0.1:
            spot = spatial.free_spot(g, (-world.ROOM_W / 2 + 2, world.ROOM_W / 2 - 2), min_gap=0.0)
            if spot:
                g.sync.actions.go_to_point(eid, spot[0], 0.0, spot[1])


def _keep_range(g, eid, e, keep, target, d, tick):
    if d < keep.near:
        ax, az = (e.x - target.x) / d, (e.z - target.z) / d
        x = max(-world.ROOM_W / 2 + 1.5, min(world.ROOM_W / 2 - 1.5, e.x + ax * 4.0))
        z = max(-world.ROOM_D / 2 + 1.5, min(world.ROOM_D / 2 - 1.5, e.z + az * 4.0))
        g.sync.actions.go_to_point(eid, x, 0.0, z)
    elif d > keep.far:
        g.sync.actions.follow_ball(eid, target.id, keep.far - 1.5)
    else:
        g.sync.actions.stop(eid)
    spit, cooldown = g.ents.get(eid, Spit), g.ents.get(eid, Cooldown)
    if spit is not None and keep.near * 0.6 < d < keep.far + 2.0 and tick >= cooldown.ready:
        dx, dz = (target.x - e.x) / (d or 1.0), (target.z - e.z) / (d or 1.0)
        projectiles.enemy_shot(g, e, dx, dz, "spit", spit.speed, spit.damage)
        g.state.event(eid, "attack")
        _rearm(g, eid, cooldown)
