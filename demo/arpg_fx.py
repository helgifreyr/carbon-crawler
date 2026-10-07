from arpg_anim import find_params

PLACEABLES = "res:/arpg/placeables/%s.red"
POOLS = {"fx_impact": 12, "fx_death": 6, "fx_cast_self": 4, "fx_cast_other": 4, "fx_cast_purple": 4, "fx_cast_amber": 4, "fx_nova": 4, "fx_blink": 6, "fx_slam": 4,
         "fx_levelup": 4, "fx_pickup_health": 6, "fx_pickup_mana": 6, "fx_zap": 12, "fx_frost": 4, "fx_meteor": 4,
         "fx_embers": 24, "fx_mend": 12, "fx_goo": 4}
PARKED = (5000.0, -50.0, 5000.0)  # far outside the room: a parked effect still draws at its default size


class Effect:
    def __init__(self, placeable):
        self.placeable = placeable
        self.params = None
        self.age = None


class ArpgFx:
    """Pools of procedural particle placeables; each one is re-aimed and restarted by resetting its FxTime."""

    def __init__(self, trinity, scene):
        self.pools = {}
        self.next = {}
        for kind, count in POOLS.items():
            pool = []
            for _ in range(count):
                p = trinity.Tr2InteriorPlaceable()
                p.placeableResPath = PLACEABLES % kind
                p.translation = PARKED
                scene.dynamics.append(p)
                pool.append(Effect(p))
            self.pools[kind] = pool
            self.next[kind] = 0

    def spawn(self, kind, position, rotation=None, scale=1.0):
        pool = self.pools.get(kind)
        if not pool:
            return
        effect = pool[self.next[kind]]
        self.next[kind] = (self.next[kind] + 1) % len(pool)
        effect.placeable.translation = tuple(position)
        effect.placeable.scaling = (scale, scale, scale)
        if rotation is not None:
            effect.placeable.rotation = rotation
        effect.age = 0.0

    def update(self, dt):
        for pool in self.pools.values():
            for effect in pool:
                if effect.age is None:
                    continue
                if effect.params is None:
                    effect.params = find_params(effect.placeable, ("FxTime",))
                    if effect.params is None:
                        continue
                effect.age += dt
                for p in effect.params["FxTime"]:
                    duration = p.value[1]
                    p.value = (effect.age, duration, 0.0, 0.0)
                if effect.age > duration:
                    effect.age = None
                    effect.placeable.translation = PARKED
