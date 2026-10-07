import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.add_dll_directory(os.environ["CARBON_BIN"])

import blue

trinity = blue.LoadExtension("_trinity_dx11")

import carbonapp
from arpg_anim import find_params
from arpg_view.geometry import axis_quat
from offscreen import capture_after

WIDTH, HEIGHT = 1600, 900
ROWS = ["projectile", "fx_cast_self", "fx_impact", "fx_death"]
FRACTIONS = [0.04, 0.12, 0.25, 0.45, 0.7]
COL, ROW = 2.4, 2.2


def main():
    """Every particle effect frozen at a few points of its life, rendered offscreen to demo/out/fx_sheet.png."""
    blue.paths.SetSearchPath("res", os.path.join(os.path.dirname(HERE), "res"))
    device = trinity.TriDevice()
    window = trinity.Tr2MainWindow()
    state = window.GetDefaultState(trinity.Tr2WindowMode.WINDOWED)
    state.width, state.height = WIDTH, HEIGHT
    window.SetWindowState(state)
    scene = trinity.Tr2InteriorScene()
    floor = trinity.Tr2InteriorPlaceable()
    floor.placeableResPath = "res:/arpg/placeables/floor.red"
    scene.dynamics.append(floor)
    instances = []
    for r, name in enumerate(ROWS):
        for c, fraction in enumerate(FRACTIONS):
            p = trinity.Tr2InteriorPlaceable()
            p.placeableResPath = "res:/arpg/placeables/%s.red" % name
            p.translation = ((c - (len(FRACTIONS) - 1) / 2.0) * COL, 0.35, ((len(ROWS) - 1) / 2.0 - r) * ROW)
            p.rotation = axis_quat((0.0, 1.0, 0.0), math.pi / 2)
            scene.dynamics.append(p)
            instances.append((p, fraction))
    view, projection = trinity.TriView(), trinity.TriProjection()
    view.SetLookAtPosition((0.0, 8.0, 8.0), (0.0, 0.0, 0.2), (0.0, 1.0, 0.0))
    projection.PerspectiveFov(math.radians(40.0), WIDTH / float(HEIGHT), 0.1, 200.0)
    jobs = trinity.Tr2RenderJobs()
    device.SetRenderJobs(jobs)
    steps = lambda: [trinity.TriStepClear((0.03, 0.03, 0.04, 1.0), 1.0), trinity.TriStepSetView(view),
                     trinity.TriStepSetProjection(projection), trinity.TriStepUpdate(scene),
                     trinity.TriStepRenderScene(scene)]
    job = trinity.TriRenderJob()
    depth = trinity.Tr2DepthStencil(WIDTH, HEIGHT, trinity.DEPTH_STENCIL_FORMAT.D24S8, 1, 0)
    for step in [trinity.TriStepPushDepthStencil(depth)] + steps() + [trinity.TriStepPopDepthStencil()]:
        job.steps.append(step)
    jobs.recurring.append(job)

    def loop():
        for frame, _ in enumerate(carbonapp.frames()):
            ready = True
            for p, fraction in instances:
                params = find_params(p, ("FxTime",))
                if params is None:
                    ready = False
                    continue
                for q in params["FxTime"]:
                    duration = q.value[1]
                    q.value = (fraction * duration, duration, 0.0, 0.0)
            if ready and frame > 20:
                path = os.path.join(HERE, "out", "fx_sheet.png")
                capture_after(trinity, jobs, WIDTH, HEIGHT, steps(), path)
                print("[fx] saved %s" % path)
                carbonapp.quit()
                return

    carbonapp.spawn(loop)


if __name__ == "__main__":
    carbonapp.run(main, frame_time_ms=16)
