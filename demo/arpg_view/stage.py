import os

from arpg_anim import find_params
from arpg_layout import SHRINE, TORCH_Y, TORCHES
from arpg_view.geometry import axis_quat

PLACEABLES = "res:/arpg/placeables/%s.red"
SEE_THROUGH_RADIUS = float(os.environ.get("ARPG_SEE_THROUGH", "1.7"))
SEE_THROUGH_LIFT = 0.4


class Stage:
    """The Tr2InteriorScene with the room, shrine and torches; the clock every presentation system animates by."""

    def __init__(self, trinity):
        self.trinity = trinity
        self.scene = trinity.Tr2InteriorScene()
        self.clock = 0.0
        self.frame = 0
        self.focus = None
        self.walls = self.placeable("walls")
        self.scene.dynamics.extend([self.placeable("ground"), self.placeable("floor"), self.walls, self.placeable("props")])
        self.wall_params = None
        shrine = self.placeable("shrine")
        shrine.translation = (SHRINE[0], 0.0, SHRINE[1])
        self.scene.dynamics.append(shrine)
        self.torches = []
        for x, z, yaw in TORCHES:
            torch = self.placeable("torch")
            torch.translation = (x, TORCH_Y, z)
            torch.rotation = axis_quat((0.0, 1.0, 0.0), yaw)
            self.scene.dynamics.append(torch)
            self.torches.append([torch, None])

    def placeable(self, name):
        placeable = self.trinity.Tr2InteriorPlaceable()
        placeable.placeableResPath = PLACEABLES % name
        return placeable

    def add(self, placeable):
        self.scene.dynamics.append(placeable)

    def remove(self, placeable):
        self.scene.dynamics.remove(placeable)

    def advance(self, dt):
        self.frame += 1
        self.clock += dt
        for i, entry in enumerate(self.torches):
            if entry[1] is None:
                entry[1] = find_params(entry[0], ("FxTime",))
                if entry[1] is None:
                    continue
            for p in entry[1]["FxTime"]:
                p.value = (self.clock + i * 1.37, 1.0, 0.0, 0.0)

    def set_view(self, eye, focus):
        """Opens a dithered hole in any wall between the camera and the focus point."""
        if focus is None:
            return
        if self.wall_params is None:
            self.wall_params = find_params(self.walls, ("SeeThrough", "EyePos"))
            if self.wall_params is None:
                return
        x, y, z = focus
        self.focus = focus
        for p in self.wall_params["SeeThrough"]:
            p.value = (x, y + SEE_THROUGH_LIFT, z, SEE_THROUGH_RADIUS)
        for p in self.wall_params["EyePos"]:
            p.value = tuple(eye) + (1.0,)
