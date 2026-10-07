import itertools
import math

import arpg_world as world
from arpg_game import combat
from arpg_game.components import Projectile, Shield
from scene import add_ball

IDS = {"bolt": itertools.count(world.PROJECTILE_BASE), "spit": itertools.count(world.SPIT_BASE),
       "bossshot": itertools.count(world.BOSS_SHOT_BASE)}


def launch(g, model, x, z, dx, dz, speed, radius, lifetime_s, **projectile):
    """Fires a projectile ball from (x, z) along the unit direction (dx, dz); model picks the id range clients draw by."""
    pid = next(IDS[model])
    add_ball(g.park, pid, x=x, z=z, radius=radius, max_velocity=speed, agility=world.PROJECTILE_AGILITY, is_massive=False)
    g.sync.actions.go_to_direction(pid, dx, 0.0, dz)
    g.sync.actions.set_ball_velocity(pid, dx * speed, 0.0, dz * speed)
    g.ents.add(pid, Projectile(radius=radius, expires=g.park.currentTime + g.ticks_for(lifetime_s), last=(x, z), **projectile))
    return pid


def enemy_shot(g, e, dx, dz, model, speed, damage):
    start = e.radius + world.SHOT_RADIUS + 0.15
    launch(g, model, e.x + dx * start, e.z + dz * start, dx, dz, speed, world.SHOT_RADIUS, world.SHOT_LIFETIME_S,
           owner=None, targets="players", damage=damage)


def _player_hit(players, ax, az, bx, bz, reach):
    sx, sz = bx - ax, bz - az
    length2 = sx * sx + sz * sz or 1e-9
    for pl in players:
        t = max(0.0, min(1.0, ((pl.x - ax) * sx + (pl.z - az) * sz) / length2))
        if math.hypot(ax + sx * t - pl.x, az + sz * t - pl.z) <= reach:
            return pl
    return None


def update(g, grid):
    if not g.ents.of(Projectile):
        return
    players = g.alive_players()
    tick, balls = g.park.currentTime, g.park.balls
    for pid, shot in g.ents.each(Projectile):
        p = balls.get(pid)
        if p is None:
            g.ents.destroy(pid)
            continue
        (ax, az), bx, bz = shot.last, p.x, p.z
        mine = shot.targets == "enemies"
        if mine:
            victim = grid.first_hit(ax, az, bx, bz, shot.radius, shot.hit)
            shield = g.ents.get(victim, Shield) if victim is not None else None
            if shield is not None and combat.blocks(shield, p.vx, p.vz):
                g.shots["blocked"] = g.shots.get("blocked", 0) + 1
                g.state.event(victim, "blocked", at=(round(bx, 2), round(bz, 2)))
                remove(g, pid)
                continue
            if victim is not None:
                g.shots["hit"] += 1
                speed = math.hypot(p.vx, p.vz) or 1.0
                combat.hit_enemy(g, victim, shot.damage, shot.owner, (p.vx / speed * shot.push, p.vz / speed * shot.push))
                if shot.pierce > 0:
                    shot.pierce -= 1
                    shot.hit.add(victim)
                else:
                    remove(g, pid)
                    continue
        else:
            victim = _player_hit(players, ax, az, bx, bz, world.PLAYER_RADIUS + shot.radius)
            if victim is not None:
                combat.hurt_player(g, victim.id, shot.damage)
                remove(g, pid)
                continue
        if tick >= shot.expires:
            g.shots["expired"] += mine
            remove(g, pid)
        elif world.segment_hits_box(ax, az, bx, bz, shot.radius):
            g.shots["wall"] += mine
            remove(g, pid)
        else:
            shot.last = (bx, bz)


def remove(g, pid):
    g.ents.destroy(pid)
    if pid in g.park.balls:
        g.sync.actions.remove_ball(pid)
