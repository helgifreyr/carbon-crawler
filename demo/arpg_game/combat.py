import math

import blue

import arpg_world as world
from arpg_game import loot, progression
from arpg_game.components import Burster, Enemy, Player, Slowed, Winding


def enemies_near(g, x, z, radius):
    balls = g.park.balls
    for eid in list(g.ents.of(Enemy)):
        e = balls.get(eid)
        if e is not None:
            d = math.hypot(e.x - x, e.z - z)
            if d <= radius + e.radius:
                yield eid, e, d


def enemies_in_cone(g, x, z, yaw, reach, arc_deg):
    found, balls = [], g.park.balls
    for eid in g.ents.of(Enemy):
        e = balls.get(eid)
        if e is None:
            continue
        dx, dz = e.x - x, e.z - z
        d = math.hypot(dx, dz)
        angle = abs((math.atan2(dx, dz) - yaw + math.pi) % (2 * math.pi) - math.pi)
        if d <= reach + e.radius and (d < 0.8 or angle <= math.radians(arc_deg)):
            found.append((d, eid, e))
    return sorted(found)


def push_enemy(g, eid, vx, vz):
    """Knocks an enemy back at (vx, vz) scaled by its kind's push; a slam winding up is not interrupted."""
    enemy = g.ents.get(eid, Enemy)
    if enemy is not None and not g.ents.has(eid, Winding):
        scale = enemy.spec["push"]
        g.sync.actions.set_ball_velocity(eid, vx * scale, 0.0, vz * scale)


def hit_enemy(g, eid, amount, owner, push=None):
    """Damages an enemy, killing it at 0 HP; True if it died."""
    if g.state.damage(eid, amount):
        kill_enemy(g, eid, owner)
        return True
    if push is not None:
        push_enemy(g, eid, *push)
    return False


def slow(g, eid):
    until = g.park.currentTime + g.ticks_for(world.SLOW_S)
    enemy = g.ents.get(eid, Enemy)
    if enemy is None:
        return
    if not g.ents.has(eid, Slowed):
        g.sync.actions.set_max_speed(eid, enemy.base_speed * world.SLOW_FACTOR)
    g.ents.add(eid, Slowed(until))
    g.state.set(eid, slowed=until)


def expire_slows(g):
    tick = g.park.currentTime
    for eid, slowed, enemy in g.ents.each(Slowed, Enemy):
        if tick >= slowed.until:
            g.ents.discard(eid, Slowed)
            g.sync.actions.set_max_speed(eid, enemy.base_speed)


def blocks(shield, vx, vz):
    """True if a shot moving along (vx, vz) arrives inside the shield's front arc."""
    speed = math.hypot(vx, vz) or 1.0
    fx, fz = math.sin(shield.yaw), math.cos(shield.yaw)
    return (-vx * fx - vz * fz) / speed >= math.cos(math.radians(shield.arc_deg / 2))


def light_burst(g, eid, burster, owner, pop):
    """Starts a bloater's fuse: the blast lands where it stands (hitting players and enemies), and it pops with it."""
    from arpg_game import spells
    e = g.park.balls.get(eid)
    if e is None or burster.lit:
        return
    burster.lit = True
    at = g.park.currentTime + g.ticks_for(burster.fuse_s)
    spells.strike_later(g, at, e.x, e.z, burster.radius, burster.damage, None, "players", ground=False)
    spells.strike_later(g, at, e.x, e.z, burster.radius, burster.damage, owner, "enemies")
    if pop:
        burster.pops_at = at
        g.sync.actions.stop(eid)
    g.stats["bursts"] += 1
    g.state.event(eid, "fuse", at=(round(e.x, 2), round(e.z, 2)), radius=burster.radius, seconds=burster.fuse_s)


def kill_enemy(g, eid, owner):
    e, enemy = g.park.balls.get(eid), g.ents.get(eid, Enemy)
    burster = g.ents.get(eid, Burster)
    if burster is not None and not burster.lit:
        light_burst(g, eid, burster, owner, pop=False)
    if owner is not None and e is not None and enemy is not None:
        progression.award_xp(g, world.PLAYER_BASE + owner, enemy.spec["xp"])
        loot.drop(g, e.x, e.z, enemy.spec)
    if enemy is not None:
        g.state.event(eid, "slain", kind=enemy.kind, by=owner)
    g.ents.destroy(eid)
    g.state.remove(eid)
    g.corrections.unwatch(eid)
    g.sync.actions.remove_ball(eid)
    if owner in g.kills:
        g.kills[owner] += 1
    if g.mode == "sandbox":
        g.respawns.append(blue.os.GetWallclockTimeNow() + int(g.respawn_s * 1e7))


def hurt_player(g, ball_id, amount, ground=False):
    # A roll makes a player untouchable; a jump lifts them over hits that land on the ground.
    player = g.ents.get(ball_id, Player)
    if player is not None and g.park.currentTime < player.roll_until:
        g.stats["dodged"] += 1
        return
    if ground and player is not None and g.park.currentTime < player.jump_until:
        g.stats["jumped"] += 1
        return
    if g.state.damage(ball_id, amount):
        player_died(g, ball_id)


def player_died(g, ball_id):
    g.state.set(ball_id, dead=True)
    g.sync.actions.stop(ball_id)
    player = g.ents.get(ball_id, Player)
    if g.mode == "sandbox" and player is not None:
        player.respawn_at = g.park.currentTime + g.ticks_for(world.PLAYER_DEAD_S)
