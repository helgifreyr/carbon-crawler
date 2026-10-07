import itertools
import math

import arpg_world as world
from arpg_game.components import Loot

_ids = itertools.count(world.LOOT_BASE)


def drop(g, x, z, spec):
    # A kind with "loot" always drops that many of each orb (spread wider the more there are); others roll the odds.
    tick = g.park.currentTime
    guaranteed = spec.get("loot", 0)
    spread = 0.6 if guaranteed <= 1 else 1.8
    for kind, orb in world.LOOT.items():
        drops = guaranteed or int(g.rng.random() < orb["chance"])
        for _ in range(drops):
            lid = next(_ids)
            ox, oz = g.rng.uniform(-spread, spread), g.rng.uniform(-spread, spread)
            g.ents.add(lid, Loot(kind, x + ox, z + oz, tick + g.ticks_for(world.LOOT_LIFETIME_S)))
            g.loot_stats["dropped"] += 1
            g.state.spawn(lid, loot=kind, x=x + ox, z=z + oz)


def update(g):
    orbs = g.ents.of(Loot)
    if not orbs:
        return
    tick = g.park.currentTime
    players = g.alive_players()
    for lid, orb in list(orbs.items()):
        taker = next((p for p in players if math.hypot(p.x - orb.x, p.z - orb.z) < world.LOOT_PICKUP_M), None)
        if taker is not None:
            amount = world.LOOT[orb.kind]["amount"]
            if orb.kind == "health":
                g.state.heal(taker.id, amount)
            else:
                g.state.restore_mana(taker.id, amount, tick)
            g.state.event(taker.id, "pickup", loot=orb.kind, amount=amount)
            g.loot_stats["picked"] += 1
        if taker is not None or tick >= orb.expires:
            remove(g, lid)


def remove(g, lid):
    g.ents.destroy(lid)
    g.state.remove(lid)


def clear(g):
    for lid in list(g.ents.of(Loot)):
        remove(g, lid)
