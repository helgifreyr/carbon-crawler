import itertools
import math

import arpg_world as world
from arpg_game import combat, projectiles
from arpg_game.components import Burn, Strike

_effect_ids = itertools.count(world.EFFECT_BASE)


def cast(g, client_id, ball_id, name, tx=None, tz=None):
    """Casts a spell for a player if it is unlocked and affordable; the spell's effect decides what happens."""
    entity = g.state.get(ball_id) or {}
    if not world.spell_unlocked(name, entity.get("level", 1)):
        return
    params = world.spell(entity, name)
    caster = g.park.balls[ball_id]
    if params["effect"] == "projectile" and math.hypot(tx - caster.x, tz - caster.z) < 1e-3:
        return
    if not g.state.spend_mana(ball_id, params["mana"], g.park.currentTime):
        if name == "bolt":
            g.shots["no_mana"] += 1
        return
    EFFECTS[params["effect"]](g, client_id, ball_id, caster, params, tx, tz)


def _projectile(g, client_id, ball_id, caster, p, tx, tz):
    g.shots["spawned"] += 1
    g.state.event(ball_id, "cast")
    dx, dz = tx - caster.x, tz - caster.z
    length = math.hypot(dx, dz)
    dx, dz = dx / length, dz / length
    start = world.PLAYER_RADIUS + world.PROJECTILE_RADIUS + 0.1
    projectiles.launch(g, "bolt", caster.x + dx * start, caster.z + dz * start, dx, dz, p["speed"], world.PROJECTILE_RADIUS,
                       p["lifetime_s"], owner=client_id, targets="enemies", damage=p["damage"], pierce=p["pierce"],
                       push=p["push"])


def _burst(g, client_id, ball_id, caster, p, tx, tz):
    g.state.event(ball_id, "nova", radius=p["radius"], slow=p["slow"])
    for eid, e, d in combat.enemies_near(g, caster.x, caster.z, p["radius"]):
        dx, dz = ((e.x - caster.x) / d, (e.z - caster.z) / d) if d > 1e-3 else (1.0, 0.0)
        if not combat.hit_enemy(g, eid, p["damage"], client_id, (dx * p["push"], dz * p["push"])) and p["slow"]:
            combat.slow(g, eid)


def _blink(g, client_id, ball_id, caster, p, tx, tz):
    # The client sends where it predicted the blink lands; the server re-checks range and walls from its own
    # position and applies the same absolute point, so both sides agree whenever the prediction was right.
    x, z = caster.x, caster.z
    slack = 1.5
    if math.hypot(tx - x, tz - z) > p["range"] + slack or world.inside_box(tx, tz, world.PLAYER_RADIUS):
        tx, tz = world.blink_target(x, z, tx, tz)
    g.sync.actions.set_ball_position(ball_id, tx, 0.0, tz)
    g.state.event(ball_id, "blink", origin=(x, z), dest=(tx, tz), frost=p["frost"])
    if p["frost"]:
        for eid, e, d in combat.enemies_near(g, x, z, p["frost_radius"]):
            if not combat.hit_enemy(g, eid, p["frost_damage"], client_id):
                combat.slow(g, eid)


def _chain(g, client_id, ball_id, caster, p, tx, tz):
    yaw = math.atan2(tx - caster.x, tz - caster.z)
    first = combat.enemies_in_cone(g, caster.x, caster.z, yaw, p["range"], p["arc_deg"])
    path, hit = [(caster.x, caster.z)], set()
    damage = p["damage"]
    current = first[0][2] if first else None
    while current is not None and len(hit) <= p["jumps"]:
        hit.add(current.id)
        path.append((current.x, current.z))
        origin = (current.x, current.z)
        combat.hit_enemy(g, current.id, damage, client_id)
        damage = max(1, int(round(damage * p["decay"])))
        nearby = [(d, e) for eid, e, d in combat.enemies_near(g, origin[0], origin[1], p["jump_m"])
                  if eid not in hit and d <= p["jump_m"]]
        current = min(nearby, key=lambda n: n[0])[1] if nearby else None
    if len(path) == 1:
        path.append((caster.x + math.sin(yaw) * p["range"] * 0.5, caster.z + math.cos(yaw) * p["range"] * 0.5))
    g.state.event(ball_id, "chain", path=path)


def _strike(g, client_id, ball_id, caster, p, tx, tz):
    dx, dz = tx - caster.x, tz - caster.z
    d = math.hypot(dx, dz)
    if d > p["range"]:
        tx, tz = caster.x + dx / d * p["range"], caster.z + dz / d * p["range"]
    burn = {k: p["burn_" + k] for k in ("radius", "s", "every_s", "damage")}
    strike_later(g, g.park.currentTime + g.ticks_for(p["delay_s"]), tx, tz, p["radius"], p["damage"], client_id, "enemies",
                 p["push"], burn)
    g.state.event(ball_id, "meteor", at=(tx, tz), burn_radius=burn["radius"], burn_s=burn["s"])


def _cone(g, client_id, ball_id, caster, p, tx, tz):
    yaw = math.atan2(tx - caster.x, tz - caster.z)
    for _, eid, e in combat.enemies_in_cone(g, caster.x, caster.z, yaw, p["range"], p["arc_deg"]):
        if not combat.hit_enemy(g, eid, p["damage"], client_id) and p["slow"]:
            combat.slow(g, eid)
    g.state.event(ball_id, "frost", yaw=yaw, reach=p["range"], arc_deg=p["arc_deg"])


EFFECTS = {"projectile": _projectile, "burst": _burst, "blink": _blink, "chain": _chain, "strike": _strike, "cone": _cone}


def strike_later(g, at, x, z, radius, damage, owner, targets, push=0.0, burn=None, ground=True):
    g.ents.add(next(_effect_ids), Strike(at, x, z, radius, damage, owner, targets, push, burn, ground))


def update_areas(g):
    """Lands strikes that are due (leaving any burn behind) and ticks burning ground."""
    tick = g.park.currentTime
    for sid, strike in g.ents.each(Strike):
        if strike.at > tick:
            continue
        g.ents.destroy(sid)
        if strike.targets == "players":
            for pl in g.alive_players():
                if math.hypot(pl.x - strike.x, pl.z - strike.z) <= strike.radius + world.PLAYER_RADIUS:
                    combat.hurt_player(g, pl.id, strike.damage, ground=strike.ground)
            continue
        for eid, e, d in combat.enemies_near(g, strike.x, strike.z, strike.radius):
            push = ((e.x - strike.x) / d * strike.push, (e.z - strike.z) / d * strike.push) if d > 1e-3 else None
            combat.hit_enemy(g, eid, strike.damage, strike.owner, push)
        if strike.burn:
            b = strike.burn
            g.ents.add(next(_effect_ids), Burn(tick + g.ticks_for(b["s"]), tick, strike.x, strike.z, b["radius"], b["damage"],
                                               b["every_s"], strike.owner))
    for bid, burn in g.ents.each(Burn):
        if tick >= burn.until:
            g.ents.destroy(bid)
        elif tick >= burn.next:
            burn.next = tick + g.ticks_for(burn.every_s)
            for eid, e, d in combat.enemies_near(g, burn.x, burn.z, burn.radius):
                combat.hit_enemy(g, eid, burn.damage, burn.owner)
