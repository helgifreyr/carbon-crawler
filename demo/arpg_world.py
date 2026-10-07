import os

import arpg_layout
from arpg_layout import (ENEMY_RADIUS, PLAYER_RADIUS, PROJECTILE_RADIUS, PROP_SIZE, SHRINE_HALF, SHRINE_RANGE, WALL_BASE_Y,
                         WALL_H)
from arpg_map import Level

ROOM = 1
# Each gate is a ball of its own holding one collision box. Moving a ball leaves its boxes where they were, so a gate
# opens by removing its ball and shuts by adding it again.
GATE_BASE = 2
PLAYER_BASE, ENEMY_BASE, PROJECTILE_BASE, SPIT_BASE = 1000, 100000, 1000000, 2000000

DESTINY_SETTINGS = {"useIterativeCollision": True}

PLAYER_SPEED = 7.0
# A dodge roll: a short burst of speed in one direction, untouchable while it lasts.
ROLL = {"speed": 10.0, "s": 0.45, "cooldown_s": 1.0}
# A jump keeps its momentum and clears what lands on the ground (slams, meteor rain), but not shots.
JUMP = {"s": 0.55, "cooldown_s": 0.8}
PROJECTILE_SPEED, PROJECTILE_LIFETIME_S = 30.0, 1.5

PLAYER_HP, LEVEL_HP = 100, 15
MANA_MAX, MANA_REGEN_PER_S = 100.0, 15.0
PLAYER_DEAD_S = 3.0
SLOW_FACTOR, SLOW_S = 0.45, 3.0

# Spells as data: the server's spell systems read the effect and its parameters; upgrades modify the parameters.
# ARPG_UNLOCK_ALL=1 opens every spell regardless of level.
SPELLS = {
    "bolt": {"label": "Firebolt", "mana": 10, "level": 1, "effect": "projectile",
             "damage": 25, "speed": PROJECTILE_SPEED, "lifetime_s": PROJECTILE_LIFETIME_S, "push": 3.0, "pierce": 0},
    "nova": {"label": "Nova", "mana": 30, "level": 1, "effect": "burst", "damage": 20, "radius": 4.0, "push": 12.0, "slow": 0},
    "blink": {"label": "Blink", "mana": 20, "level": 1, "effect": "blink",
              "range": 7.0, "frost": 0, "frost_radius": 3.0, "frost_damage": 12},
    "chain": {"label": "Chain Lightning", "mana": 18, "level": 2, "effect": "chain",
              "damage": 22, "range": 12.0, "arc_deg": 35.0, "jumps": 4, "jump_m": 5.0, "decay": 0.85},
    "meteor": {"label": "Meteor", "mana": 35, "level": 3, "effect": "strike", "damage": 55, "radius": 3.2, "range": 14.0,
               "delay_s": 0.8, "push": 12.0, "burn_radius": 2.4, "burn_s": 3.0, "burn_every_s": 0.5, "burn_damage": 4},
    "frost": {"label": "Frost Wave", "mana": 25, "level": 4, "effect": "cone", "damage": 12, "range": 7.0, "arc_deg": 35.0,
              "slow": 1},
}
UNLOCK_ALL = os.environ.get("ARPG_UNLOCK_ALL") == "1"


def spell_unlocked(spell, level):
    return UNLOCK_ALL or level >= SPELLS[spell]["level"]


# Level-up upgrades, drawn as the icon with the badge on it. Each mod is (spell, "player" or "*" for every spell, parameter, "add" or "scale", amount per stack):
# a parameter ends up as (base + adds) * product of (1 + scale) over the upgrades that touch it.
UPGRADES = {
    "pierce": {"icon": "bolt", "badge": "pierce", "label": "Piercing Bolt", "text": "Firebolt passes through one more enemy", "most": 3, "spell": "bolt",
               "mods": [("bolt", "pierce", "add", 1)]},
    "bolt_power": {"icon": "bolt", "badge": "power", "label": "Searing Bolt", "text": "Firebolt deals 30% more damage", "most": 3, "spell": "bolt",
                   "mods": [("bolt", "damage", "scale", 0.3)]},
    "nova_radius": {"icon": "nova", "badge": "expand", "label": "Wide Nova", "text": "Nova reaches 1 m further", "most": 2, "spell": "nova",
                    "mods": [("nova", "radius", "add", 1.0)]},
    "nova_slow": {"icon": "nova", "badge": "frost", "label": "Frost Nova", "text": "Nova also slows what it hits", "most": 1, "spell": "nova",
                  "mods": [("nova", "slow", "add", 1)]},
    "blink_frost": {"icon": "blink", "badge": "frost", "label": "Cold Departure", "text": "Blink leaves a burst of frost behind", "most": 1, "spell": "blink",
                    "mods": [("blink", "frost", "add", 1)]},
    "chain_jumps": {"icon": "chain", "badge": "fork", "label": "Forked Lightning", "text": "Chain Lightning jumps 2 more times", "most": 2, "spell": "chain",
                    "mods": [("chain", "jumps", "add", 2)]},
    "meteor_burn": {"icon": "meteor", "badge": "flame", "label": "Lingering Flames", "text": "Meteor's burning ground is 50% larger and lasts longer", "most": 2,
                    "spell": "meteor", "mods": [("meteor", "burn_radius", "scale", 0.5), ("meteor", "burn_s", "scale", 0.5)]},
    "frost_range": {"icon": "frost", "badge": "expand", "label": "Blizzard", "text": "Frost Wave reaches 2 m further and wider", "most": 2, "spell": "frost",
                    "mods": [("frost", "range", "add", 2.0), ("frost", "arc_deg", "add", 8.0)]},
    "spell_power": {"icon": "arcane", "badge": "power", "label": "Arcane Power", "text": "All spells deal 12% more damage", "most": 5, "spell": None,
                    "mods": [("*", "damage", "scale", 0.12), ("blink", "frost_damage", "scale", 0.12)]},
    "mana_regen": {"icon": "mana", "badge": "cycle", "label": "Flowing Mana", "text": "Mana regenerates 3 per second faster", "most": 3, "spell": None,
                   "mods": [("player", "mana_regen", "add", 3.0)]},
    "mana_max": {"icon": "mana", "badge": "plus", "label": "Deep Reserves", "text": "25 more maximum mana", "most": 2, "spell": None,
                 "mods": [("player", "mana_max", "add", 25.0)]},
    "vitality": {"icon": "heart", "badge": "plus", "label": "Vitality", "text": "25 more maximum health", "most": 3, "spell": None,
                 "mods": [("player", "max_hp", "add", 25)]},
}
OFFER_SIZE = 3


def upgrade_stacks(entity, upgrade):
    return (entity.get("upgrades") or {}).get(upgrade, 0)


def _modified(base, target, entity):
    adds, scales = {}, {}
    for upgrade, stacks in (entity.get("upgrades") or {}).items():
        for who, param, op, amount in UPGRADES[upgrade]["mods"]:
            if param not in base or not (who == target or (who == "*" and target != "player")):
                continue
            if op == "add":
                adds[param] = adds.get(param, 0) + amount * stacks
            else:
                scales[param] = scales.get(param, 1.0) * (1.0 + amount * stacks)
    out = dict(base)
    for param in adds.keys() | scales.keys():
        value = (base[param] + adds.get(param, 0)) * scales.get(param, 1.0)
        out[param] = int(round(value)) if isinstance(base[param], int) else value
    return out


def spell(entity, name):
    """A spell's parameters for this caster, with its upgrades applied."""
    return _modified(SPELLS[name], name, entity or {})


def player_stats(entity):
    """Max HP, max mana and mana regen from level and upgrades."""
    level = entity.get("level", 1)
    return _modified({"max_hp": PLAYER_HP + LEVEL_HP * (level - 1), "mana_max": MANA_MAX, "mana_regen": MANA_REGEN_PER_S},
                     "player", entity)


# Enemy kinds as bundles of behaviours: each behaviour key becomes a server component of the same shape.
# push scales knockback (brutes barely budge); cooldown_s paces attacks; loot is a guaranteed drop count per kind.
KINDS = {
    "imp": {"hp": 40, "speed": (3.0, 4.5), "radius": 0.5, "push": 1.0, "xp": 10, "cooldown_s": 1.0,
            "melee": {"damage": 8, "reach": 0.35}},
    "spitter": {"hp": 30, "speed": (3.2, 3.8), "radius": 0.45, "push": 1.2, "xp": 15, "cooldown_s": 2.4, "jitter": 0.15,
                "keep_range": {"near": 6.5, "far": 11.0}, "spit": {"speed": 13.0, "damage": 12}},
    "brute": {"hp": 160, "speed": (2.0, 2.4), "radius": 0.9, "push": 0.25, "xp": 40, "cooldown_s": 2.8, "loot": 1,
              "slam": {"reach": 2.6, "radius": 3.0, "windup_s": 0.8, "damage": 30}},
    "hound": {"hp": 60, "speed": (4.2, 4.8), "radius": 0.55, "push": 0.8, "xp": 20, "cooldown_s": 1.0,
              "melee": {"damage": 9, "reach": 0.35},
              "charge": {"min_range": 4.0, "max_range": 11.0, "windup_s": 0.75, "speed": 15.0, "distance": 10.0,
                         "damage": 22, "stun_s": 1.4, "cooldown_s": 4.0}},
    "bloater": {"hp": 70, "speed": (1.8, 2.2), "radius": 0.6, "push": 0.6, "xp": 20, "cooldown_s": 1.0,
                "burst": {"radius": 3.2, "damage": 30, "fuse_s": 0.9, "trigger_m": 1.6}},
    "shieldbearer": {"hp": 150, "speed": (2.0, 2.3), "radius": 0.75, "push": 0.3, "xp": 35, "cooldown_s": 1.6, "loot": 1,
                     "melee": {"damage": 16, "reach": 0.45},
                     "shield": {"arc_deg": 110.0, "turn_rate": 2.2}},
    "shaman": {"hp": 55, "speed": (2.8, 3.2), "radius": 0.45, "push": 1.1, "xp": 25, "cooldown_s": 4.5, "jitter": 0.15,
               "keep_range": {"near": 6.0, "far": 10.0},
               "mend": {"radius": 8.0, "heal": 25, "haste": 1.35, "haste_s": 2.0}},
    "warlord": {"hp": 1400, "speed": (2.6, 2.6), "radius": 1.3, "push": 0.0, "xp": 300, "cooldown_s": 2.4, "loot": 3,
                "boss": True,
                "slam": {"reach": 4.5, "radius": 4.2, "windup_s": 1.0, "damage": 35},
                "ring": {"shots": 14, "speed": 9.0, "damage": 14},
                "rain": {"radius": 2.6, "delay_s": 1.2, "damage": 25, "per_player": 3, "enraged_only": True},
                "enrage": {"at": 0.5, "cooldown_s": 1.6, "speedup": 1.3, "summon": 4, "summon_kind": "imp"}},
}
SHOT_RADIUS, SHOT_LIFETIME_S = 0.2, 3.5
BOSS_EVERY_WAVES, BOSS_ESCORT = 5, 6
BOSS_SHOT_BASE = 2500000
EFFECT_BASE = 4000000  # server-only areas (strikes, burning ground): never balls, never replicated

LOOT_BASE = 3000000
LOOT = {"health": {"chance": 0.18, "amount": 30}, "mana": {"chance": 0.22, "amount": 40}}
LOOT_PICKUP_M, LOOT_LIFETIME_S = 1.1, 25.0


def xp_to_next(level):
    return int(60 * level ** 1.5)


# Destiny's velocity time constant is mass * agility / friction, with friction ~1e6 and mass 13e6.
FRICTION_OVER_MASS = 1e6 / 13e6
PLAYER_TAU_S = float(os.environ.get("PLAYER_TAU_S", "0.01"))
PLAYER_AGILITY = PLAYER_TAU_S * FRICTION_OVER_MASS
ENEMY_AGILITY = 0.15 * FRICTION_OVER_MASS
PROJECTILE_AGILITY = 0.01 * FRICTION_OVER_MASS



# The level being played, and what follows from it; set_level replaces them all. Every process starts on the test level:
# the server may pick another, and clients take whatever the server sends.
LEVEL = ROOMS = GATES = BOXES = BOUNDS = SHRINE = SHRINES = None


def set_level(level):
    """Makes level the one every box test, room lookup and gate here refers to."""
    global LEVEL, ROOMS, GATES, BOXES, BOUNDS, SHRINE, SHRINES, _index
    LEVEL, ROOMS, GATES, SHRINE = level, level.rooms, level.gates, level.shrine
    # Every shrine: an act's checkpoints (the first is where it starts), or the level's one shrine.
    SHRINES = [tuple(c) for c in level.features.get("checkpoints", [])] or ([SHRINE] if SHRINE else [])
    BOUNDS = level.cells.extent
    props = [(x - PROP_SIZE[k] / 2, z - PROP_SIZE[k] / 2, x + PROP_SIZE[k] / 2, z + PROP_SIZE[k] / 2)
             for k, x, z, _ in level.props if k in PROP_SIZE]
    shrine = [(x - SHRINE_HALF, z - SHRINE_HALF, x + SHRINE_HALF, z + SHRINE_HALF) for x, z in SHRINES]
    BOXES = level.cells.wall_boxes() + props + shrine
    _index = {}
    for box in BOXES:
        for i in range(int((box[0] - 1.0) // INDEX_CELL), int((box[2] + 1.0) // INDEX_CELL) + 1):
            for j in range(int((box[1] - 1.0) // INDEX_CELL), int((box[3] + 1.0) // INDEX_CELL) + 1):
                _index.setdefault((i, j), []).append(box)
    shut_gates.clear()
    shut_gates.update(gate_ids())


def room_at(x, z, margin=0.0):
    """The index of the room whose floor contains (x, z), at least margin in from its walls, or None."""
    for i, room in enumerate(ROOMS):
        x0, z0, x1, z1 = room["rect"]
        if x0 + margin <= x <= x1 - margin and z0 + margin <= z <= z1 - margin:
            return i
    return None


def world_description():
    return {"destiny_settings": DESTINY_SETTINGS, "static_ball": ROOM, "boxes": BOXES, "wall_height": WALL_H,
            "gates": {GATE_BASE + i: box for i, box in enumerate(GATES)}, "level": LEVEL.payload()}


def apply_settings():
    import destiny
    config = destiny.settings.Get()
    for name, value in DESTINY_SETTINGS.items():
        setattr(config, name, value)
    destiny.settings.Apply(config)


def add_box(ball, box, origin=(0.0, 0.0)):
    """A collision box on a ball; its corners are given in the world, the box is stored relative to origin."""
    x0, z0, x1, z1 = box
    ball.AddMiniBox(x0 - origin[0], WALL_BASE_Y, z0 - origin[1], x1 - x0, 0.0, 0.0, 0.0, WALL_H, 0.0, 0.0, 0.0, z1 - z0)


def gate_centre(gate_id):
    x0, z0, x1, z1 = GATES[gate_id - GATE_BASE]
    return (x0 + x1) / 2, (z0 + z1) / 2


def add_room(park, add_ball):
    """The static walls, and one ball per gate, all shut."""
    room = add_ball(park, ROOM, max_velocity=0.0, radius=0.0, is_free=False, is_massive=False, is_interactive=True)
    park.SetBallFree(ROOM, False)
    for box in BOXES:
        add_box(room, box)
    for gate_id in gate_ids():
        add_gate(park, add_ball, gate_id)
    return room


def add_gate(park, add_ball, gate_id):
    """A gate's ball stands at the gate itself: a static ball only collides with what comes near it, wherever its
    boxes reach, so one at the origin with its box far away never stops anyone."""
    cx, cz = gate_centre(gate_id)
    gate = add_ball(park, gate_id, x=cx, z=cz, max_velocity=0.0, radius=0.0, is_free=False, is_massive=False,
                    is_interactive=True)
    park.SetBallFree(gate_id, False)
    add_box(gate, GATES[gate_id - GATE_BASE], (cx, cz))
    return gate


def gate_ids():
    return range(GATE_BASE, GATE_BASE + len(GATES))


# Which gates are shut, for the box tests below; each process updates it from its own park with sync_gates.
shut_gates = set()


def sync_gates(park, mirror=None, add_ball=None):
    """Reads which gates a park has into shut_gates, giving a replicated gate ball back its box (replication carries
    no boxes). With mirror, a second park gets the same gates. True if any gate changed."""
    shut = set()
    for gate_id in gate_ids():
        ball = park.balls.get(gate_id)
        if ball is None:
            continue
        shut.add(gate_id)
        if not len(ball.miniBoxes):
            add_box(ball, GATES[gate_id - GATE_BASE], gate_centre(gate_id))
    if mirror is not None:
        for gate_id in gate_ids():
            if gate_id in shut and gate_id not in mirror.balls:
                add_gate(mirror, add_ball, gate_id)
            elif gate_id not in shut and gate_id in mirror.balls:
                mirror.RemoveBall(gate_id)
    if shut == shut_gates:
        return False
    shut_gates.clear()
    shut_gates.update(shut)
    return True


def room_rect(index):
    return ROOMS[index]["rect"]


# Static boxes bucketed into INDEX_CELL squares, so a point test only looks at the boxes near it.
INDEX_CELL = 4.0
_index = {}


def boxes_near(x, z, pad=0.0):
    """Static boxes and shut gates that may lie within pad (up to 1 m) of (x, z)."""
    found = _index.get((int(x // INDEX_CELL), int(z // INDEX_CELL)), ())
    if pad > 1.0:
        found = {b for i in range(int((x - pad) // INDEX_CELL), int((x + pad) // INDEX_CELL) + 1)
                 for j in range(int((z - pad) // INDEX_CELL), int((z + pad) // INDEX_CELL) + 1) for b in _index.get((i, j), ())}
    if shut_gates:
        found = list(found) + [GATES[g - GATE_BASE] for g in shut_gates]
    return found


def inside_box(x, z, pad=0.0):
    return any(x0 - pad <= x <= x1 + pad and z0 - pad <= z <= z1 + pad for x0, z0, x1, z1 in boxes_near(x, z, pad))


def blink_target(x, z, tx, tz, radius=PLAYER_RADIUS):
    """Where a blink from (x, z) toward (tx, tz) lands: at most the blink range away, short of any wall."""
    dx, dz = tx - x, tz - z
    length = (dx * dx + dz * dz) ** 0.5
    if length < 1e-3:
        return x, z
    reach = min(length, SPELLS["blink"]["range"])
    dx, dz = dx / length, dz / length
    best = (x, z)
    steps = int(reach / 0.25)
    for i in range(1, steps + 1):
        px, pz = x + dx * reach * i / steps, z + dz * reach * i / steps
        if inside_box(px, pz, radius + 0.05):
            break
        best = (px, pz)
    return best


def segment_hits_box(ax, az, bx, bz, radius):
    # Coarse swept test: sample the segment at quarter-radius steps.
    length = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
    steps = max(1, int(length / max(radius * 0.25, 1e-3)))
    for i in range(steps + 1):
        t = i / steps
        if inside_box(ax + (bx - ax) * t, az + (bz - az) * t, radius):
            return True
    return False


set_level(arpg_layout.test_level())
