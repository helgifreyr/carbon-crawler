import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.add_dll_directory(os.environ["CARBON_BIN"])

import blue

trinity = blue.LoadExtension("_trinity_dx11")

import carbonapp
from arpg_view.geometry import axis_quat

WIDTH, HEIGHT = 1400, 700
LINEUP = os.environ.get("GALLERY_LINEUP", "player_self,player_other,player_dead,enemy,projectile").split(",")
SPACING = 1.6
PITCH = float(os.environ.get("GALLERY_PITCH", "0.95"))
DISTANCE = float(os.environ.get("GALLERY_DISTANCE", "9"))
FACING = float(os.environ.get("GALLERY_FACING", "0.5"))
SPIN = float(os.environ.get("GALLERY_SPIN", "0.6"))
CAPTURE_FRAME = int(os.environ.get("GALLERY_CAPTURE_FRAME", "0"))


class Gallery:
    """Every ARPG placeable in a row on the floor, lit like the game, for judging the Blender models."""

    def __init__(self):
        blue.paths.SetSearchPath("res", os.path.join(os.path.dirname(HERE), "res"))
        self.device = trinity.TriDevice()
        self.window = trinity.Tr2MainWindow()
        state = self.window.GetDefaultState(trinity.Tr2WindowMode.WINDOWED)
        state.width, state.height = WIDTH, HEIGHT
        self.window.SetWindowState(state)
        self.window.title = "Carbon Crawler - model gallery"
        self.window.onClose = lambda *a: carbonapp.quit()
        self.scene = trinity.Tr2InteriorScene()
        floor = trinity.Tr2InteriorPlaceable()
        floor.placeableResPath = "res:/arpg/placeables/floor.red"
        self.scene.dynamics.append(floor)
        self.models = []
        for i, name in enumerate(LINEUP):
            p = trinity.Tr2InteriorPlaceable()
            p.placeableResPath = "res:/arpg/placeables/%s.red" % name
            x = (i - (len(LINEUP) - 1) / 2.0) * SPACING
            p.translation = (x, 0.0 if name != "projectile" else 0.3, 0.0)
            self.scene.dynamics.append(p)
            self.models.append(p)
        self.view = trinity.TriView()
        self.projection = trinity.TriProjection()
        self.projection.PerspectiveFov(math.radians(30.0), WIDTH / float(HEIGHT), 0.1, 200.0)
        eye = (0.0, DISTANCE * math.sin(PITCH) + 0.4, DISTANCE * math.cos(PITCH))
        self.view.SetLookAtPosition(eye, (0.0, 0.4, 0.0), (0.0, 1.0, 0.0))
        self.jobs = trinity.Tr2RenderJobs()
        self.device.SetRenderJobs(self.jobs)
        job = trinity.TriRenderJob()
        depth = trinity.Tr2DepthStencil(WIDTH, HEIGHT, trinity.DEPTH_STENCIL_FORMAT.D24S8, 1, 0)
        for step in [trinity.TriStepPushDepthStencil(depth)] + self.scene_steps() + [trinity.TriStepPopDepthStencil()]:
            job.steps.append(step)
        self.jobs.recurring.append(job)

    def scene_steps(self):
        return [trinity.TriStepClear((0.04, 0.045, 0.06, 1.0), 1.0),
                trinity.TriStepSetView(self.view),
                trinity.TriStepSetProjection(self.projection),
                trinity.TriStepUpdate(self.scene),
                trinity.TriStepRenderScene(self.scene)]

    def frame_loop(self):
        t = 0.0
        for frame, dt in enumerate(carbonapp.frames()):
            t += dt
            for p in self.models:
                p.rotation = axis_quat((0.0, 1.0, 0.0), FACING + (t * SPIN if not CAPTURE_FRAME else 0.0))
            if CAPTURE_FRAME and frame == CAPTURE_FRAME:
                from offscreen import capture_after
                path = os.path.join(HERE, "out", os.environ.get("GALLERY_OUT", "gallery") + ".png")
                capture_after(trinity, self.jobs, WIDTH, HEIGHT, self.scene_steps(), path)
                print("[gallery] saved %s" % path)
                carbonapp.quit()


if __name__ == "__main__":
    carbonapp.run(lambda: carbonapp.spawn(Gallery().frame_loop))
