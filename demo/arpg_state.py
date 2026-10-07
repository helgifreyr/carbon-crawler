from collections import deque

MANA_FIELDS = ("mana", "mana_max", "mana_tick", "mana_regen")


def mana_at(entity, tick, dt):
    if "mana" not in entity:
        return 0.0
    regen = entity["mana_regen"] * max(0, tick - entity["mana_tick"]) * dt
    return min(entity["mana_max"], entity["mana"] + regen)


class ServerState:
    """Authoritative per-ball game state. Only changes are sent, stamped with the tick they happened on.

    Mana is sent as (value, tick, regen rate) and extrapolated by clients, so regeneration costs no traffic."""

    def __init__(self, dt):
        self.dt = dt
        self.entities = {}
        self._dirty = {}
        self._removed = []
        self._events = []

    def spawn(self, ball_id, **fields):
        self.entities[ball_id] = dict(fields)
        self._dirty[ball_id] = dict(fields)

    def set(self, ball_id, **fields):
        entity = self.entities.get(ball_id)
        if entity is None:
            return
        entity.update(fields)
        self._dirty.setdefault(ball_id, {}).update(fields)

    def event(self, ball_id, name, **data):
        # One-shot happenings (a cast, a slam, a pickup) ride the next flush instead of living on the entity.
        self._events.append((ball_id, name, data))

    def remove(self, ball_id):
        if self.entities.pop(ball_id, None) is not None:
            self._dirty.pop(ball_id, None)
            self._removed.append(ball_id)

    def get(self, ball_id):
        return self.entities.get(ball_id)

    def mana(self, ball_id, tick):
        entity = self.entities.get(ball_id)
        return mana_at(entity, tick, self.dt) if entity else 0.0

    def spend_mana(self, ball_id, cost, tick):
        current = self.mana(ball_id, tick)
        if current < cost:
            return False
        self.set(ball_id, mana=current - cost, mana_tick=tick)
        return True

    def restore_mana(self, ball_id, amount, tick):
        current = self.mana(ball_id, tick)
        self.set(ball_id, mana=min(self.entities[ball_id]["mana_max"], current + amount), mana_tick=tick)

    def set_mana_regen(self, ball_id, regen, tick):
        # Re-anchor at the current value so clients' extrapolation doesn't jump when the rate changes.
        self.set(ball_id, mana=self.mana(ball_id, tick), mana_tick=tick, mana_regen=regen)

    def heal(self, ball_id, amount):
        entity = self.entities.get(ball_id)
        if entity is not None and not entity.get("dead"):
            self.set(ball_id, hp=min(entity["max_hp"], entity["hp"] + amount))

    def damage(self, ball_id, amount):
        entity = self.entities.get(ball_id)
        if entity is None or entity.get("dead"):
            return False
        hp = max(0, entity["hp"] - amount)
        self.set(ball_id, hp=hp)
        return hp == 0

    def snapshot(self):
        return {ball_id: dict(fields) for ball_id, fields in self.entities.items()}

    def flush(self, send, tick):
        if self._dirty or self._removed or self._events:
            send(("state", tick, self._dirty, self._removed, self._events))
            self._dirty, self._removed, self._events = {}, [], []


class ClientState:
    """Mirror of ServerState, applied on the client's own tick so it lines up with Destiny movement."""

    def __init__(self, collect_events=False):
        self.entities = {}
        self._pending = deque()
        self.collect_events = collect_events
        self.events = []

    def receive(self, message):
        kind, tick = message[0], message[1]
        if kind == "state_full":
            self._pending.append((tick, None, message[2], (), ()))
        elif kind == "state":
            self._pending.append((tick, message[2], None, message[3], message[4] if len(message) > 4 else ()))

    def apply_until(self, tick):
        while self._pending and self._pending[0][0] <= tick:
            at, changes, full, removed, events = self._pending.popleft()
            if full is not None:
                self.entities = {ball_id: dict(fields) for ball_id, fields in full.items()}
            for ball_id, fields in (changes or {}).items():
                self.entities.setdefault(ball_id, {}).update(fields)
            for ball_id in removed:
                self.entities.pop(ball_id, None)
            if self.collect_events:
                self.events.extend((at, ball_id, name, data) for ball_id, name, data in events)

    def take_events(self):
        events, self.events = self.events, []
        return events

    def get(self, ball_id):
        return self.entities.get(ball_id)
