from collections import defaultdict


class Entities:
    """Components by type, each store keyed by entity id (a Destiny ball id, or an id for effects without a ball).

    Destroying an entity drops every component it has, so no system has to remember to clean up after another."""

    def __init__(self):
        self._stores = defaultdict(dict)

    def add(self, eid, *components):
        for component in components:
            self._stores[type(component)][eid] = component

    def get(self, eid, kind):
        return self._stores[kind].get(eid)

    def has(self, eid, kind):
        return eid in self._stores[kind]

    def discard(self, eid, kind):
        self._stores[kind].pop(eid, None)

    def of(self, kind):
        return self._stores[kind]

    def each(self, kind, *others):
        # A snapshot, so systems may add and destroy entities while iterating.
        for eid, component in list(self._stores[kind].items()):
            rest = [self._stores[o].get(eid) for o in others]
            if all(r is not None for r in rest):
                yield (eid, component, *rest)

    def destroy(self, eid):
        for store in self._stores.values():
            store.pop(eid, None)
