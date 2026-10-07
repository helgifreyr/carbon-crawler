import math

from arpg_view.actors import ENEMY_ROLES



class Feedback:
    """HUD reactions to events: floating numbers, banners and camera shake."""

    def __init__(self, bus, viewer):
        self.viewer = viewer
        handlers = {"damaged": self._damaged, "pickup": self._pickup, "enrage": self._enrage,
                    "slain": self._slain, "landed": self._landed}
        for name, handler in handlers.items():
            bus.on([name], lambda event, h=handler: h(event) if event.present else None)

    def _damaged(self, event):
        actor = event.actor
        x, y, z = actor.last
        if actor.role == "you":
            color = (1.0, 0.35, 0.3)
            self.viewer.shake(0.1, 0.2)
        elif actor.role in ENEMY_ROLES:
            color = (1.0, 0.93, 0.75)
        else:
            color = (1.0, 0.6, 0.6)
        self.viewer.numbers.spawn((x, y + 1.3 * actor.size, z), "%d" % round(event.data["amount"]), color)

    def _pickup(self, event):
        if event.position is None:
            return
        x, y, z = event.position
        health = event.data["loot"] == "health"
        self.viewer.numbers.spawn((x, y + 1.7, z), "+%d %s" % (event.data["amount"], "HP" if health else "MP"),
                                  (1.0, 0.45, 0.4) if health else (0.5, 0.7, 1.0))

    def _enrage(self, event):
        self.viewer.shake(0.3, 0.6)

    def _slain(self, event):
        if event.data.get("kind") == "warlord" and event.data.get("by") is not None:
            self.viewer.audio.play("wave_clear", self.viewer.cam.target)
            self.viewer.shake(0.25, 0.8)

    def _landed(self, event):
        own = self.viewer.sim.own_position()
        center, radius = event.data["center"], event.data["radius"]
        if math.hypot(own[0] - center[0], own[2] - center[2]) < radius + 5.0:
            self.viewer.shake(0.22, 0.35)
