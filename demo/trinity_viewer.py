import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Python 3.8+ ignores PATH when resolving an extension's DLLs.
os.add_dll_directory(os.environ["CARBON_BIN"])

import blue

trinity = blue.LoadExtension("_trinity_dx11")

import carbonapp
from hud import Hud
from scene import COLORS
from sim import Sim

RES_ROOT = os.path.join(os.path.dirname(HERE), "res")
SOLID_EFFECT = "res:/graphics/effect/game/solid.fx"
LINE_EFFECT = "res:/graphics/effect/game/line.fx"

WIDTH, HEIGHT = (int(v) for v in os.environ.get("VIEWER_SIZE", "1280x800").split("x"))
FOV = math.radians(45.0)
NEAR, FAR = 1.0, 20000.0
MIN_DRAW_RADIUS = 6.0
CLEAR_COLOR = (0.03, 0.04, 0.07, 1.0)

GRID_MINOR = (0.12, 0.14, 0.2, 1.0)
GRID_MAJOR = (0.2, 0.24, 0.33, 1.0)
GRID_AXIS = (0.31, 0.38, 0.51, 1.0)

VK_TAB, VK_SPACE, VK_ESCAPE = 0x09, 0x20, 0x1B
VK_OEM_PLUS, VK_OEM_MINUS, VK_OEM_4, VK_OEM_6 = 0xBB, 0xBD, 0xDB, 0xDD
MOUSE_LEFT, MOUSE_RIGHT = 0, 1


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def normalize(a):
    length = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def translation_scale(pos, scale):
    return ((scale, 0.0, 0.0, 0.0), (0.0, scale, 0.0, 0.0), (0.0, 0.0, scale, 0.0), (pos[0], pos[1], pos[2], 1.0))


def icosphere(subdivisions):
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [normalize(v) for v in [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    tris = [tuple(verts[i] for i in f) for f in faces]
    for _ in range(subdivisions):
        refined = []
        for a, b, c in tris:
            ab = normalize(tuple((x + y) / 2 for x, y in zip(a, b)))
            bc = normalize(tuple((x + y) / 2 for x, y in zip(b, c)))
            ca = normalize(tuple((x + y) / 2 for x, y in zip(c, a)))
            refined += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        tris = refined
    outward = []
    for a, b, c in tris:
        # Tr2SolidSet derives the face normal as cross(p1 - p3, p2 - p1).
        if dot(cross(sub(a, c), sub(b, a)), a) < 0:
            b, c = c, b
        outward.append((a, b, c))
    return outward


def make_effect(path, **params):
    effect = trinity.Tr2Effect()
    effect.effectFilePath = path
    handles = {}
    for name, value in params.items():
        p = trinity.Tr2Vector4Parameter()
        p.name = name
        p.value = value
        effect.parameters.append(p)
        handles[name] = p
    return effect, handles


class OrbitCamera:
    def __init__(self, yaw=0.8, pitch=0.9, distance=1100.0, min_distance=50.0, max_distance=5000.0):
        self.yaw, self.pitch, self.distance = yaw, pitch, distance
        self.min_distance, self.max_distance = min_distance, max_distance
        self.target = (0.0, 0.0, 0.0)

    def eye(self):
        cp = math.cos(self.pitch)
        tx, ty, tz = self.target
        return (tx + self.distance * cp * math.sin(self.yaw),
                ty + self.distance * math.sin(self.pitch),
                tz + self.distance * cp * math.cos(self.yaw))

    def rotate(self, dx, dy):
        self.yaw -= dx * 0.005
        self.pitch = min(1.5, max(-1.5, self.pitch + dy * 0.005))

    def zoom(self, notches):
        self.distance = min(self.max_distance, max(self.min_distance, self.distance * (1.0 - notches * 0.1)))

    def ray(self, mx, my, width, height):
        eye = self.eye()
        forward = normalize(sub(self.target, eye))
        right = normalize(cross(forward, (0.0, 1.0, 0.0)))
        up = cross(right, forward)
        half_h = math.tan(FOV / 2.0)
        half_w = half_h * width / float(height)
        nx = (2.0 * mx / width - 1.0) * half_w
        ny = (1.0 - 2.0 * my / height) * half_h
        direction = normalize(tuple(f + nx * r + ny * u for f, r, u in zip(forward, right, up)))
        return eye, direction


def plane_hit(origin, direction):
    if abs(direction[1]) < 1e-6:
        return None
    t = -origin[1] / direction[1]
    if t <= 0:
        return None
    return (origin[0] + direction[0] * t, 0.0, origin[2] + direction[2] * t)


def color_of(tracked):
    return getattr(tracked, "color", None) or COLORS.get(tracked.name, (0.4, 0.7, 1.0))


class TrinityViewer:
    title = "Carbon Crawler - destiny viewer (trinity)"
    min_draw_radius = MIN_DRAW_RADIUS
    grid_half_lines, grid_spacing = 20, 50.0
    show_trails = True
    grid_y = 0.0
    near, far = NEAR, FAR

    def __init__(self, sim=None):
        blue.paths.SetSearchPath("res", RES_ROOT)
        self.sim = sim if sim is not None else Sim()
        self.cam = self.make_camera()
        self.dragging = False
        self.last_mouse = None

        self.device = trinity.TriDevice()
        self.window = trinity.Tr2MainWindow()
        state = self.window.GetDefaultState(trinity.Tr2WindowMode.WINDOWED)
        state.width, state.height = WIDTH, HEIGHT
        self.window.SetWindowState(state)
        self.window.title = self.title
        self.window.onClose = self.on_close
        self.window.onMouseDown = self.on_mouse_down
        self.window.onMouseUp = self.on_mouse_up
        self.window.onMouseMove = self.on_mouse_move
        self.window.onMouseWheel = self.on_mouse_wheel
        self.window.onKeyDown = self.on_key_down

        self.build_scene()
        self.hud = Hud(trinity, *self.viewport_size())
        self.build_render_job()

    def build_scene(self):
        self.scene = trinity.Tr2PrimitiveScene()
        self.solid_effect, self.solid_params = make_effect(SOLID_EFFECT, EyePos=self.cam.eye() + (1.0,))
        self.line_effect, _ = make_effect(LINE_EFFECT)

        self.unit_sphere = icosphere(2)
        self.spheres = {}
        self.trails = {}

        self.grid = self.new_lines()
        half, spacing = self.grid_half_lines, self.grid_spacing
        extent = half * spacing
        for i in range(-half, half + 1):
            color = GRID_AXIS if i == 0 else GRID_MAJOR if i % 5 == 0 else GRID_MINOR
            d = i * spacing
            y = self.grid_y
            self.grid.AddLine((d, y, -extent), color, (d, y, extent), color)
            self.grid.AddLine((-extent, y, d), color, (extent, y, d), color)
        self.grid.SubmitChanges()

        self.overlay = self.new_lines()
        self.build_static(self.scene)

    def help_lines(self):
        return ["LMB grid: goto   O: orbit   F: follow   S: stop   TAB: select",
                "RMB drag: rotate   wheel: zoom   [ ]: tick rate   SPACE: pause   %.0f fps" % blue.os.fps]

    def make_camera(self):
        return OrbitCamera()

    def build_static(self, scene):
        pass

    def ensure_primitives(self):
        present = {t.name for t in self.sim.tracked}
        for t in self.sim.tracked:
            if t.name in self.spheres:
                continue
            color = color_of(t) + (1.0,)
            solids = trinity.Tr2SolidSet()
            solids.effect = self.solid_effect
            for a, b, c in self.unit_sphere:
                solids.AddTriangle(a, color, b, color, c, color)
            solids.SubmitChanges()
            self.scene.primitives.append(solids)
            self.spheres[t.name] = solids
            self.trails[t.name] = self.new_lines()
        for name in [n for n in self.spheres if n not in present]:
            self.scene.primitives.remove(self.spheres.pop(name))
            self.scene.primitives.remove(self.trails.pop(name))

    def new_lines(self):
        lines = trinity.Tr2LineSet()
        lines.effect = self.line_effect
        self.scene.primitives.append(lines)
        return lines

    def build_render_job(self):
        self.view = trinity.TriView()
        self.projection = trinity.TriProjection()
        self.jobs = trinity.Tr2RenderJobs()
        self.device.SetRenderJobs(self.jobs)
        self.depth_step = trinity.TriStepPushDepthStencil()
        self.depth_size = None
        self.ensure_depth_buffer()
        job = trinity.TriRenderJob()
        job.name = "carbon_crawler"
        # Tr2PrimitiveScene renders with reversed depth, so depth clears to 0.
        for step in (self.depth_step,
                     trinity.TriStepClear(CLEAR_COLOR, 0.0),
                     trinity.TriStepSetView(self.view),
                     trinity.TriStepSetProjection(self.projection),
                     trinity.TriStepRenderScene(self.scene),
                     trinity.TriStepPopDepthStencil(),
                     trinity.TriStepRenderScene(self.hud.scene)):
            job.steps.append(step)
        self.jobs.recurring.append(job)

    def ensure_depth_buffer(self):
        size = self.viewport_size()
        if size != self.depth_size:
            self.depth_step.depthStencil = trinity.Tr2DepthStencil(
                size[0], size[1], trinity.DEPTH_STENCIL_FORMAT.D24S8, 1, 0)
            self.depth_size = size
            if hasattr(self, "hud"):
                self.hud.resize(*size)

    def on_close(self, *args):
        carbonapp.quit()

    def on_mouse_down(self, button, x, y):
        if button == MOUSE_RIGHT:
            self.dragging = True
            self.last_mouse = (x, y)
        elif button == MOUSE_LEFT:
            origin, direction = self.cam.ray(x, y, *self.viewport_size())
            point = plane_hit(origin, direction)
            if point:
                self.sim.goto(point)

    def on_mouse_up(self, button, x, y):
        if button == MOUSE_RIGHT:
            self.dragging = False

    def on_mouse_move(self, x, y):
        if self.dragging and self.last_mouse:
            self.cam.rotate(x - self.last_mouse[0], y - self.last_mouse[1])
        self.last_mouse = (x, y)

    def on_mouse_wheel(self, delta):
        self.cam.zoom(delta / 120.0)

    def on_key_down(self, key, flags):
        actions = {
            VK_SPACE: self.sim.toggle_pause,
            VK_TAB: self.sim.select_next,
            VK_OEM_6: self.sim.faster, VK_OEM_PLUS: self.sim.faster,
            VK_OEM_4: self.sim.slower, VK_OEM_MINUS: self.sim.slower,
            ord("O"): self.sim.orbit_anchor,
            ord("F"): self.sim.follow_next,
            ord("S"): self.sim.stop,
            VK_ESCAPE: self.on_close,
        }
        action = actions.get(key)
        if action:
            action()

    def viewport_size(self):
        return max(1, self.device.width or WIDTH), max(1, self.device.height or HEIGHT)

    def update_camera(self):
        self.ensure_depth_buffer()
        width, height = self.viewport_size()
        eye = self.cam.eye()
        self.view.SetLookAtPosition(eye, self.cam.target, (0.0, 1.0, 0.0))
        self.projection.PerspectiveFov(FOV, width / float(height), self.near, self.far)
        self.solid_params["EyePos"].value = eye + (1.0,)

    def update_primitives(self):
        self.ensure_primitives()
        alpha = self.sim.alpha
        for t in self.sim.tracked:
            radius = max(self.min_draw_radius, t.ball.radius)
            self.spheres[t.name].localTransform = translation_scale(t.position(alpha), radius)

        if self.sim.ticked and self.show_trails:
            for t in self.sim.tracked:
                lines = self.trails[t.name]
                lines.ClearLines()
                color = color_of(t) + (0.5,)
                points = list(t.trail)
                for a, b in zip(points, points[1:]):
                    lines.AddLine(a, color, b, color)
                lines.SubmitChanges()

        self.overlay.ClearLines()
        selected = self.sim.selected
        if selected is not None:
            self.add_ring(selected.position(alpha), max(self.min_draw_radius, selected.ball.radius) * 2.2, (1, 1, 1, 0.9))
        if self.sim.goto_marker:
            self.add_ring(self.sim.goto_marker, max(self.min_draw_radius, 0.5) * 2.0, (1, 1, 1, 0.9))
        self.overlay.SubmitChanges()

    def add_ring(self, center, radius, color, segments=32):
        cx, cy, cz = center
        points = [(cx + radius * math.cos(2 * math.pi * i / segments), cy,
                   cz + radius * math.sin(2 * math.pi * i / segments)) for i in range(segments + 1)]
        for a, b in zip(points, points[1:]):
            self.overlay.AddLine(a, color, b, color)

    def frame_loop(self):
        exit_after = int(os.environ.get("VIEWER_EXIT_AFTER", "0"))
        autogoto_frame = int(os.environ.get("VIEWER_AUTOGOTO_FRAME", "0"))
        travelled, last = {}, {}
        for dt in carbonapp.frames():
            self.sim.update(dt)
            self.update_camera()
            self.update_primitives()
            self.frame += 1
            if autogoto_frame and self.frame == autogoto_frame:
                gx, gz = (float(v) for v in os.environ.get("VIEWER_AUTOGOTO_POINT", "0,0").split(","))
                self.sim.goto((gx, 0.0, gz))
            if exit_after:
                for t in self.sim.tracked:
                    pos = t.position(1.0)
                    if t.name in last:
                        travelled[t.name] = travelled.get(t.name, 0.0) + sum((a - b) ** 2 for a, b in zip(pos, last[t.name])) ** 0.5
                    last[t.name] = pos
                if self.frame == exit_after:
                    own = self.sim.selected.name if self.sim.selected else None
                    shown = sorted(travelled.items(), key=lambda kv: (kv[0] != own, kv[0]))[:8]
                    print("[viewer] rendered travel: " + ", ".join("%s %.0f m" % kv for kv in shown))
            if exit_after and self.frame == exit_after:
                self.hud_frozen = True
            if exit_after and self.frame >= exit_after + 15:
                self.capture(os.path.join(HERE, "out", "trinity_viewer"))
                carbonapp.quit()

    def capture(self, stem):
        if hasattr(self, "main_job"):
            from offscreen import capture_job
            capture_job(trinity, self.main_job, *self.viewport_size(), path=stem + ".png")
        elif hasattr(self, "scene_steps"):
            from offscreen import capture_after
            width, height = self.viewport_size()
            capture_after(trinity, self.jobs, width, height, self.scene_steps(), stem + ".png")
        else:
            from wincapture import capture_client_bmp
            os.makedirs(os.path.dirname(stem), exist_ok=True)
            capture_client_bmp(self.window.hwnd, stem + ".bmp")

    def title_loop(self):
        while True:
            if getattr(self, "hud_frozen", False):
                return
            self.hud.set_lines(self.sim.status_lines() + self.help_lines())
            blue.synchro.SleepWallclock(250)

    def start(self):
        self.frame = 0
        self.started = blue.os.GetWallclockTimeNow()
        carbonapp.at_exit(self.shutdown)
        carbonapp.spawn(self.frame_loop)
        carbonapp.spawn(self.title_loop)

    def shutdown(self):
        elapsed = blue.os.TimeDiffInMs(self.started, blue.os.GetWallclockTimeNow()) / 1000.0
        print("frames rendered: %d  ticks: %d  avg fps: %.1f" % (self.frame, self.sim.tick, self.frame / max(elapsed, 1e-6)))
        self.sim.close()


def make_sim():
    host = os.environ.get("NET_HOST")
    if host:
        from netsim import NetSim
        return NetSim(host, int(os.environ.get("NET_PORT", "47400")))
    return Sim()


if __name__ == "__main__":
    carbonapp.run(lambda: TrinityViewer(make_sim()).start())
