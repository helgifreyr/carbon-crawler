import os
import shutil
import tempfile

import blue

import arpg_world as world
import carbonapp
from arpg_anim import find_params
from arpg_layout import TORCH_Y
from arpg_view import level_mesh
from arpg_view.geometry import axis_quat

PLACEABLES = "res:/arpg/placeables/%s.red"
SEE_THROUGH_RADIUS = float(os.environ.get("ARPG_SEE_THROUGH", "1.7"))
SEE_THROUGH_LIFT = 0.4
# A gate's portcullis rises GATE_LIFT_M when it opens, at these speeds (m/s): slow going up, slamming down.
GATE_LIFT_M, GATE_RISE, GATE_FALL = 2.9, 1.6, 9.0
# Placeables give up waiting for their lighting after this many frames (they were removed before they loaded).
LIGHT_PATIENCE_FRAMES = 600


class Stage:
    """The Tr2InteriorScene with the level, shrine, torches and gates; the clock every presentation system animates by.

    Level meshes are built at load time into a per-process folder that the "gen:" path points at."""

    def __init__(self, trinity):
        self.trinity = trinity
        self.scene = trinity.Tr2InteriorScene()
        self.clock = 0.0
        self.frame = 0
        self.focus = None
        self.level = None
        self.statics, self.walls, self.torches, self.gates = [], [], [], {}
        self.wall_params = []
        self.light = None
        self.unlit = []
        self.gen_dir = os.path.join(tempfile.gettempdir(), "carbon-crawler", str(os.getpid()))
        os.makedirs(self.gen_dir, exist_ok=True)
        blue.paths.SetSearchPath("gen", self.gen_dir + os.sep)
        carbonapp.at_exit(lambda: shutil.rmtree(self.gen_dir, ignore_errors=True))

    def build_level(self, level):
        """Replaces whatever level the scene holds with this one."""
        for placeable in self.statics:
            self.remove(placeable)
        self.statics, self.walls, self.torches, self.gates, self.wall_params = [], [], [], {}, []
        self.level = level
        prefix = "level%d" % self.frame
        light_name = prefix + "_light.png"
        with open(os.path.join(self.gen_dir, light_name), "wb") as f:
            f.write(level.lightmap["png"])
        self.light = (tuple(level.lightmap["rect"]), "gen:/" + light_name)
        for has_walls, red in level_mesh.build(level, self.gen_dir, prefix, self.light):
            placeable = self.trinity.Tr2InteriorPlaceable()
            placeable.placeableResPath = "gen:/" + red
            self.add_static(placeable)
            if has_walls:
                self.walls.append(placeable)
        if level.shrine:
            shrine = self.placeable("shrine")
            shrine.translation = (level.shrine[0], 0.0, level.shrine[1])
            self.add_static(shrine)
        for x, z, yaw in level.torches:
            torch = self.placeable("torch")
            torch.translation = (x, TORCH_Y, z)
            torch.rotation = axis_quat((0.0, 1.0, 0.0), yaw)
            self.add_static(torch)
            self.torches.append([torch, None])
        for i, (x0, z0, x1, z1) in enumerate(level.gates):
            gate = self.placeable("gate")
            gate.translation = ((x0 + x1) / 2, 0.0, (z0 + z1) / 2)
            self.add_static(gate)
            self.gates[world.GATE_BASE + i] = [gate, 0.0]

    def placeable(self, name):
        """A placeable from the asset library; once it has loaded it is relit with the level's lightmap."""
        placeable = self.trinity.Tr2InteriorPlaceable()
        placeable.placeableResPath = PLACEABLES % name
        self.unlit.append([placeable, self.frame])
        return placeable

    def add(self, placeable):
        self.scene.dynamics.append(placeable)

    def add_static(self, placeable):
        self.statics.append(placeable)
        self.add(placeable)

    def remove(self, placeable):
        self.scene.dynamics.remove(placeable)

    def relight(self):
        # Library placeables are built for the test level's lightmap; point each at this level's once it has loaded.
        if self.light is None or not self.unlit:
            return
        (x0, z0, x1, z1), path = self.light
        rect = (x0, z0, 1.0 / (x1 - x0), 1.0 / (z1 - z0))
        waiting = []
        for entry in self.unlit:
            placeable, since = entry
            res = placeable.placeableRes
            if res is None or res.visualModel is None:
                if self.frame - since < LIGHT_PATIENCE_FRAMES:
                    waiting.append(entry)
                continue
            for mesh in res.visualModel.meshes:
                for area in list(mesh.opaqueAreas) + list(mesh.transparentAreas):
                    if area.effect is None:
                        continue
                    for p in area.effect.parameters:
                        if p.name == "LightMapRect":
                            p.value = rect
                    for r in area.effect.resources:
                        if r.name == "LightMap" and r.resourcePath != path:
                            r.resourcePath = path
        self.unlit = waiting

    def advance(self, dt):
        self.frame += 1
        self.clock += dt
        self.relight()
        for gate_id, entry in self.gates.items():
            target = 0.0 if gate_id in world.shut_gates else GATE_LIFT_M
            if entry[1] != target:
                step = (GATE_RISE if target > entry[1] else GATE_FALL) * dt
                entry[1] = min(target, entry[1] + step) if target > entry[1] else max(target, entry[1] - step)
                x, _, z = entry[0].translation
                entry[0].translation = (x, entry[1], z)
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
        if len(self.wall_params) < len(self.walls):
            self.wall_params = [params for params in (find_params(w, ("SeeThrough", "EyePos")) for w in self.walls) if params]
        x, y, z = focus
        self.focus = focus
        for params in self.wall_params:
            for p in params["SeeThrough"]:
                p.value = (x, y + SEE_THROUGH_LIFT, z, SEE_THROUGH_RADIUS)
            for p in params["EyePos"]:
                p.value = tuple(eye) + (1.0,)
