import arpg_world as world
from arpg_game import spatial
from arpg_game.components import Player


def fresh_player_state(g, level=1, xp=0, upgrades=None, picks=0):
    entity = {"level": level, "upgrades": dict(upgrades or {})}
    stats = world.player_stats(entity)
    return dict(hp=stats["max_hp"], max_hp=stats["max_hp"], dead=False, mana=stats["mana_max"],
                mana_max=stats["mana_max"], mana_tick=g.park.currentTime, mana_regen=stats["mana_regen"],
                level=level, xp=xp, xp_next=world.xp_to_next(level), upgrades=entity["upgrades"], picks=picks,
                offer=make_offer(g, entity) if picks else [])


def make_offer(g, entity):
    level = entity.get("level", 1)
    pool = [u for u, up in world.UPGRADES.items()
            if world.upgrade_stacks(entity, u) < up["most"] and (up["spell"] is None or world.spell_unlocked(up["spell"], level))]
    return g.rng.sample(pool, min(world.OFFER_SIZE, len(pool)))


def apply_stats(g, ball_id, heal=False):
    entity = g.state.get(ball_id)
    stats = world.player_stats(entity)
    g.state.set_mana_regen(ball_id, stats["mana_regen"], g.park.currentTime)
    hp = stats["max_hp"] if heal else min(stats["max_hp"], entity["hp"] + max(0, stats["max_hp"] - entity["max_hp"]))
    g.state.set(ball_id, max_hp=stats["max_hp"], mana_max=stats["mana_max"], hp=hp)


def pick_upgrade(g, ball_id, choice):
    entity = g.state.get(ball_id)
    offer = entity.get("offer") or []
    if not 0 <= choice < len(offer):
        return
    upgrades = dict(entity.get("upgrades") or {})
    upgrades[offer[choice]] = upgrades.get(offer[choice], 0) + 1
    picks = entity["picks"] - 1
    g.state.set(ball_id, upgrades=upgrades, picks=picks)
    g.state.event(ball_id, "picked", upgrade=offer[choice])
    g.state.set(ball_id, offer=make_offer(g, g.state.get(ball_id)) if picks else [])
    apply_stats(g, ball_id)


def award_xp(g, ball_id, amount):
    entity = g.state.get(ball_id)
    if entity is None:
        return
    level, xp = entity["level"], entity["xp"] + amount
    gained = 0
    while xp >= world.xp_to_next(level):
        xp -= world.xp_to_next(level)
        level += 1
        gained += 1
    if not gained:
        g.state.set(ball_id, xp=xp)
        return
    g.loot_stats["levelups"] += gained
    g.state.set(ball_id, level=level, xp=xp, xp_next=world.xp_to_next(level), picks=entity.get("picks", 0) + gained)
    g.state.event(ball_id, "levelup", level=level)
    if not entity.get("offer"):
        g.state.set(ball_id, offer=make_offer(g, g.state.get(ball_id)))
    apply_stats(g, ball_id, heal=True)


def place_player(g, ball_id):
    """Moves a player to a free spot where players arrive in the current room."""
    area = spatial.entry_area(g)
    x, z = spatial.free_spot(g, area, min_gap=1.0) or ((area[0] + area[2]) / 2, (area[1] + area[3]) / 2)
    g.sync.actions.set_ball_position(ball_id, x, 0.0, z)
    g.sync.actions.set_ball_velocity(ball_id, 0.0, 0.0, 0.0)


def respawn_player(g, ball_id, reset=False):
    place_player(g, ball_id)
    entity = g.state.get(ball_id) or {}
    if reset:
        g.state.set(ball_id, **fresh_player_state(g))
    else:
        g.state.set(ball_id, **fresh_player_state(g, entity.get("level", 1), entity.get("xp", 0), entity.get("upgrades"),
                                                  entity.get("picks", 0)))


def update_respawns(g):
    tick = g.park.currentTime
    for ball_id, player in g.ents.each(Player):
        if player.respawn_at and player.respawn_at <= tick:
            player.respawn_at = 0
            respawn_player(g, ball_id)
