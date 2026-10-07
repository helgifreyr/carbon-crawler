import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.add_dll_directory(os.environ["CARBON_BIN"])

import blue

trinity = blue.LoadExtension("_trinity_dx11")

import carbonapp
from arpg_anim import Track, find_params, table
from arpg_view.actors import VAT_PARAMS
from arpg_view.geometry import axis_quat
from offscreen import capture_after

WIDTH, HEIGHT = 1600, 900
MODELS = [m for m in os.environ.get("SHEET_MODELS", "player:player_self,enemy:enemy").split(",")]
SAMPLES = int(os.environ.get("SHEET_SAMPLES", "6"))
FACING = float(os.environ.get("SHEET_FACING", "0.6"))
CLIPS = [c for c in os.environ.get("SHEET_CLIPS", "").split(",") if c]
ZOOM = float(os.environ.get("SHEET_ZOOM", "1"))
COL, ROW = 1.5, 1.9


class Sheet:
    """Each clip of a VAT model as a row of placeables frozen at evenly spaced phases, saved offscreen."""

    def __init__(self, model, placeable):
        self.meta = table(model)
        self.name = model
        self.scene = trinity.Tr2InteriorScene()
        floor = trinity.Tr2InteriorPlaceable()
        floor.placeableResPath = "res:/arpg/placeables/floor.red"
        self.scene.dynamics.append(floor)
        clips = [(c, m) for c, m in self.meta["clips"].items() if not CLIPS or c in CLIPS]
        self.instances = []
        for r, (clip, meta) in enumerate(clips):
            for c in range(SAMPLES):
                p = trinity.Tr2InteriorPlaceable()
                p.placeableResPath = "res:/arpg/placeables/%s.red" % placeable
                p.translation = ((c - (SAMPLES - 1) / 2.0) * COL, 0.0, ((len(clips) - 1) / 2.0 - r) * ROW)
                p.rotation = axis_quat((0.0, 1.0, 0.0), FACING)
                track = Track(clip)
                track.phase = c / float(SAMPLES) if meta["loop"] else c / float(SAMPLES - 1)
                rows = track.rows(meta, self.meta["height"])
                self.instances.append((p, rows + (0.0,)))
                self.scene.dynamics.append(p)
        self.view = trinity.TriView()
        self.view.SetLookAtPosition((0.0, 9.0 / ZOOM + 0.3, 10.5 / ZOOM), (0.0, 0.3, 0.3), (0.0, 1.0, 0.0))
        self.projection = trinity.TriProjection()
        self.projection.PerspectiveFov(math.radians(38.0), WIDTH / float(HEIGHT), 0.1, 200.0)

    def pose(self):
        ready = True
        for p, state in self.instances:
            params = find_params(p, VAT_PARAMS)
            if params is None:
                ready = False
                continue
            for q in params["VatState"] + params["VatFade"]:
                q.value = state
        return ready

    def steps(self):
        return [trinity.TriStepClear((0.05, 0.055, 0.07, 1.0), 1.0),
                trinity.TriStepSetView(self.view),
                trinity.TriStepSetProjection(self.projection),
                trinity.TriStepUpdate(self.scene),
                trinity.TriStepRenderScene(self.scene)]


def main():
    blue.paths.SetSearchPath("res", os.path.join(os.path.dirname(HERE), "res"))
    device = trinity.TriDevice()
    window = trinity.Tr2MainWindow()
    state = window.GetDefaultState(trinity.Tr2WindowMode.WINDOWED)
    state.width, state.height = WIDTH, HEIGHT
    window.SetWindowState(state)
    window.title = "Carbon Crawler - animation sheet"
    jobs = trinity.Tr2RenderJobs()
    device.SetRenderJobs(jobs)
    sheets = [Sheet(*m.split(":")) for m in MODELS]
    job = trinity.TriRenderJob()
    depth = trinity.Tr2DepthStencil(WIDTH, HEIGHT, trinity.DEPTH_STENCIL_FORMAT.D24S8, 1, 0)
    job.steps.append(trinity.TriStepPushDepthStencil(depth))
    for sheet in sheets:
        for step in sheet.steps():
            job.steps.append(step)
    job.steps.append(trinity.TriStepPopDepthStencil())
    jobs.recurring.append(job)

    def loop():
        for frame, _ in enumerate(carbonapp.frames()):
            ready = all([sheet.pose() for sheet in sheets])
            if ready and frame > 20:
                for sheet in sheets:
                    path = os.path.join(HERE, "out", "anim_%s.png" % sheet.name)
                    capture_after(trinity, jobs, WIDTH, HEIGHT, sheet.steps(), path)
                    print("[sheet] saved %s" % path)
                carbonapp.quit()
                return

    carbonapp.spawn(loop)


if __name__ == "__main__":
    carbonapp.run(main, frame_time_ms=16)
