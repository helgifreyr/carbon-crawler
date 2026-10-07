"""Enemy packs placed in a generated level: asleep until a player is seen nearby or one of them is hit, chasing only
within a leash of home, and finding their way around rock along a bounded flow field toward the players."""
import math
from collections import deque

import arpg_world as world
from arpg_game import enemies
from arpg_game.components import Asleep, Enemy, Home
from arpg_map import FLOOR

AGGRO_M, WAKE_LINK_M, LEASH_M = 13.0, 9.0, 36.0
# How far (in cells, along the floor) the flow field reaches from the players.
FIELD_CELLS = 20
STEPS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def spawn(g, index, pack, leash=LEASH_M):
    """The pack's enemies around its spot, asleep."""
    x, z = pack["at"]
    eids = []
    for k, kind in enumerate(pack["kinds"]):
        a = 2 * math.pi * k / max(1, len(pack["kinds"]))
        spot = (x + 1.6 * math.sin(a), z + 1.6 * math.cos(a)) if k else (x, z)
        if world.inside_box(*spot, pad=world.KINDS[kind]["radius"]):
            spot = (x, z)
        eid = enemies.spawn(g, kind, spot)
        if eid is not None:
            g.ents.add(eid, Home(spot[0], spot[1], index, leash), Asleep())
            eids.append(eid)
    return eids


def members(g, pack):
    return [eid for eid, home in g.ents.each(Home) if home.pack == pack]


def wake(g, pack, woken=None):
    """Wakes a pack, and any pack sleeping within WAKE_LINK_M of it."""
    woken = woken if woken is not None else set()
    if pack in woken:
        return
    woken.add(pack)
    mine = members(g, pack)
    for eid in mine:
        if g.ents.has(eid, Asleep):
            g.ents.discard(eid, Asleep)
            g.state.event(eid, "woke")
    balls = g.park.balls
    for eid, home in list(g.ents.each(Home)):
        if home.pack in woken or not g.ents.has(eid, Asleep):
            continue
        if any(math.hypot(home.x - balls[m].x, home.z - balls[m].z) < WAKE_LINK_M for m in mine if m in balls):
            wake(g, home.pack, woken)


def wake_if_asleep(g, eid):
    home = g.ents.get(eid, Home)
    if home is not None and g.ents.has(eid, Asleep):
        wake(g, home.pack)


def update(g):
    """Wakes packs that see a player, and sends the ones that strayed too far back home to sleep."""
    balls = g.park.balls
    players = g.alive_players()
    for eid, home in list(g.ents.each(Home)):
        e = balls.get(eid)
        if e is None:
            continue
        if g.ents.has(eid, Asleep):
            for p in players:
                if math.hypot(p.x - e.x, p.z - e.z) < AGGRO_M and not world.segment_hits_box(e.x, e.z, p.x, p.z, 0.1):
                    wake(g, home.pack)
                    break
        elif home.leash and math.hypot(e.x - home.x, e.z - home.z) > home.leash:
            g.ents.add(eid, Asleep())
            g.sync.actions.go_to_point(eid, home.x, 0.0, home.z)
            entity = g.state.get(eid)
            if entity:
                g.state.set(eid, hp=entity["max_hp"])


def flow_field(g):
    """Floor distance (in cells) to the nearest living player, out to FIELD_CELLS; keyed by cell."""
    cells = world.LEVEL.cells
    dist = {}
    queue = deque()
    for p in g.alive_players():
        cell = cells.cell_of(p.x, p.z)
        dist[cell] = 0
        queue.append(cell)
    while queue:
        i, j = cell = queue.popleft()
        d = dist[cell] + 1
        if d > FIELD_CELLS:
            continue
        for di, dj in STEPS:
            n = (i + di, j + dj)
            if n in dist or cells.get(*n) != FLOOR:
                continue
            # No cutting corners past rock.
            if di and dj and (cells.get(i + di, j) != FLOOR or cells.get(i, j + dj) != FLOOR):
                continue
            dist[n] = d
            queue.append(n)
    return dist


def step_toward_players(g, eid, e, field):
    """Moves an enemy one cell down the flow field; False if it is outside the field."""
    cells = world.LEVEL.cells
    i, j = cells.cell_of(e.x, e.z)
    here = field.get((i, j))
    if here is None:
        return False
    best = min(((field.get((i + di, j + dj), 1 << 30), (i + di, j + dj)) for di, dj in STEPS), default=None)
    if best is None or best[0] >= here:
        return False
    x0, z0, x1, z1 = cells.cell_rect(*best[1])
    g.sync.actions.go_to_point(eid, (x0 + x1) / 2, 0.0, (z0 + z1) / 2)
    return True


def chase_around(g, eid, e, field):
    """For an enemy that can't see a player: down the flow field if it is in it, otherwise back home."""
    if step_toward_players(g, eid, e, field):
        return
    home = g.ents.get(eid, Home)
    if home is not None and not home.leash:
        # Arena and boss enemies never give up: straight for the nearest player.
        target = min(g.alive_players(), key=lambda p: (p.x - e.x) ** 2 + (p.z - e.z) ** 2, default=None)
        if target is not None:
            g.sync.actions.go_to_point(eid, target.x, 0.0, target.z)
        return
    if home is not None and math.hypot(e.x - home.x, e.z - home.z) > 1.5:
        g.sync.actions.go_to_point(eid, home.x, 0.0, home.z)


def asleep(g, eid):
    return g.ents.has(eid, Asleep)


def home_of(g, eid):
    return g.ents.get(eid, Home)
