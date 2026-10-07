from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(slots=True)
class Event:
    """Something that happened to an entity: from the server's event channel, predicted locally, or derived here.

    animate says whether the actor's clip should play; present whether effects, sound and HUD should react."""
    name: str
    key: object
    data: dict = field(default_factory=dict)
    actor: object = None
    animate: bool = True
    present: bool = True

    @property
    def position(self):
        return self.actor.last if self.actor is not None else None


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)

    def on(self, names, handler):
        for name in names:
            self._handlers[name].append(handler)

    def emit(self, event):
        for handler in self._handlers.get(event.name, ()):
            handler(event)
