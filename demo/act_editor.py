"""The act editor: edit an act template's macro graph and watch the generator's maps for four seeds follow every edit.

run_demo.ps1 -Script demo\\act_editor.py   (ARPG_ACT names the template in res/arpg/acts; default caves)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.add_dll_directory(os.environ["CARBON_BIN"])

import blue
import numpy as np

trinity = blue.LoadExtension("_trinity_dx11")
import carbonapp
import editor_draw as draw
from arpg_gen import run, template
from arpg_gen.light import png_bytes
from hud import TextLine

ROOT = os.path.dirname(HERE)
WIDTH, HEIGHT = (int(v) for v in os.environ.get("EDITOR_SIZE", "1600x900").split("x"))
SEEDS = 4
REGENERATE_AFTER_S = 0.5
PLAY_PORT = 47420
PLAY_RUNS = ("editor_server", "editor_client")
MOUSE_LEFT = 0
VK = {"delete": 0x2E, "escape": 0x1B, "space": 0x20, "pgup": 0x21, "pgdn": 0x22, "f2": 0x71, "lbracket": 0xDB,
      "rbracket": 0xDD}
SIZE_STEP = 50
REPEATS = [[1, 1], [1, 2], [2, 3], [3, 4]]
CHANCES = [1.0, 0.7, 0.5, 0.3]
TEXT = (0.9, 0.93, 1.0, 1.0)
HELP = ("drag nodes  N new  Del delete  T type  [ ] size  R repeat  H chance  C link (click another: link, branch, none)  "
        "X cut (click another)  L layer  PgUp/PgDn seeds  click a map: pick it  P play it  F2 save  Esc quit")


def end(proc, wait_s=5):
    """Kills a child process if it still runs, and waits for it, so it is never dropped while alive."""
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(wait_s)
    except subprocess.TimeoutExpired:
        pass


class Image:
    """A sprite showing a numpy image; each new image is a new file, swapped in once loaded (sprite textures cache)."""

    def __init__(self, scene, folder):
        self.folder, self.version, self.pending = folder, 0, None
        self.sprite = trinity.Tr2Sprite2d()
        self.sprite.spriteEffect = trinity.TR2_SFX_COPY
        self.sprite.blendMode = trinity.TR2_SBM_BLEND
        self.sprite.displayX = -10000
        self.size = (1, 1)
        scene.children.append(self.sprite)

    def show(self, img):
        self.version += 1
        name = "img%d_%d.png" % (id(self) % 100000, self.version)
        with open(os.path.join(self.folder, name), "wb") as f:
            f.write(png_bytes(img))
        texture = trinity.Tr2Sprite2dTexture()
        texture.resPath = "edit:/" + name
        self.pending = (texture, img.shape[1], img.shape[0])

    def update(self):
        if self.pending is None:
            return
        texture, w, h = self.pending
        if texture.atlasTexture is None or not texture.atlasTexture.isGood:
            return
        texture.srcX, texture.srcY, texture.srcWidth, texture.srcHeight = 0, 0, w, h
        self.sprite.texturePrimary = texture
        self.sprite.SetDirty()
        self.size, self.pending = (w, h), None

    def place(self, x, y, w, h):
        self.sprite.displayX, self.sprite.displayY, self.sprite.displayWidth, self.sprite.displayHeight = x, y, w, h


class Editor:
    def __init__(self, name):
        self.path = template.path_of(name)
        with open(self.path) as f:
            self.tmpl = json.load(f)
        self.tmpl.setdefault("editor", {}).setdefault("positions", {})
        self.work = tempfile.mkdtemp(prefix="act-editor-")
        self.work_template = os.path.join(self.work, "template.json")
        blue.paths.SetSearchPath("res", os.path.join(ROOT, "res"))
        blue.paths.SetSearchPath("edit", self.work + os.sep)
        self.device = trinity.TriDevice()
        self.window = trinity.Tr2MainWindow()
        state = self.window.GetDefaultState(trinity.Tr2WindowMode.WINDOWED)
        state.width, state.height = WIDTH, HEIGHT
        self.window.SetWindowState(state)
        self.window.title = "Carbon Crawler act editor - " + os.path.basename(self.path)
        self.window.onClose = lambda *a: carbonapp.quit()
        self.window.onMouseDown = self.on_mouse_down
        self.window.onMouseUp = self.on_mouse_up
        self.window.onMouseMove = self.on_mouse_move
        self.window.onKeyDown = self.on_key_down
        self.scene = trinity.Tr2Sprite2dScene()
        self.labels = [self.text(14) for _ in range(40)]
        self.captions = [self.text(15) for _ in range(SEEDS)]
        self.lines = [self.text(16, "bold")] + [self.text(15) for _ in range(5)]
        self.graph = Image(self.scene, self.work)
        self.previews = [Image(self.scene, self.work) for _ in range(SEEDS)]
        # A sprite scene draws its children last-added first, so the backgrounds go in last.
        self.panels = [self.panel() for _ in range(3)]
        jobs = trinity.Tr2RenderJobs()
        self.device.SetRenderJobs(jobs)
        job = trinity.TriRenderJob()
        job.name = "act_editor"
        job.steps.append(trinity.TriStepClear((0.05, 0.055, 0.08, 1.0), 1.0))
        job.steps.append(trinity.TriStepRenderScene(self.scene))
        jobs.recurring.append(job)
        self.job = job
        self.seed_base, self.picked, self.layer = 1, 0, 0
        # connecting is None, "link" (C: the next node clicked cycles link, branch, none) or "cut" (X: removes it).
        self.selected, self.connecting, self.drag, self.mouse = None, None, None, (0, 0)
        self.procs, self.results, self.errors = {}, {}, {}
        self.regenerate_at, self.saved, self.status = 0.0, True, ""
        self.play_procs = []
        self.graph_dirty = True
        self.changed(saved=True)

    def panel(self):
        p = trinity.Tr2Sprite2d()
        p.spriteEffect = trinity.TR2_SFX_FILL
        p.blendMode = trinity.TR2_SBM_BLEND
        p.color = (0.08, 0.09, 0.13, 1.0)
        self.scene.children.append(p)
        return p

    def text(self, size, font="body"):
        line = TextLine(trinity, size, font)
        line.obj.color = TEXT
        line.obj.displayX = -10000
        self.scene.children.append(line.obj)
        return line

    # Layout: the graph on the left, the four maps in a 2x2 grid on the right, the node inspector under the graph.
    def areas(self):
        w, h = max(1, self.device.width or WIDTH), max(1, self.device.height or HEIGHT)
        gw = int(w * 0.36)
        return {"graph": (12, 44, gw, h - 44 - 150), "inspector": (12, h - 140, gw, 128),
                "maps": (gw + 24, 44, w - gw - 36, h - 56), "size": (w, h)}

    def nodes(self):
        return self.tmpl["nodes"]

    def node(self, node_id):
        return next((n for n in self.nodes() if n["id"] == node_id), None)

    def default_positions(self):
        """Where unplaced nodes go: the main route left to right across the middle, branches below their parent."""
        ids = [n["id"] for n in self.nodes()]
        main = [(e[0], e[1]) for e in self.tmpl["edges"] if len(e) < 3 or e[2] != "branch"]
        start = next((n["id"] for n in self.nodes() if n["type"] == "start"), ids[0] if ids else None)
        order, frontier = [], [start] if start else []
        while frontier:
            k = frontier.pop(0)
            if k in order:
                continue
            order.append(k)
            frontier += [b for a, b in main if a == k] + [a for a, b in main if b == k]
        out = {k: (0.08 + 0.84 * i / max(1, len(order) - 1), 0.4) for i, k in enumerate(order)}
        hanging = {}
        for e in self.tmpl["edges"]:
            for parent, child in ((e[0], e[1]), (e[1], e[0])):
                if parent in out and child not in out:
                    hanging[parent] = hanging.get(parent, 0) + 1
                    out[child] = (out[parent][0], 0.4 + 0.22 * hanging[parent])
        for i, k in enumerate(ids):
            out.setdefault(k, (0.08 + 0.84 * i / max(1, len(ids) - 1), 0.9))
        return out

    def positions(self):
        """Each node's place in the graph view, in pixels."""
        x, y, w, h = self.areas()["graph"]
        stored, default = self.tmpl["editor"]["positions"], self.default_positions()
        return {n["id"]: tuple(v * s for v, s in zip(stored.get(n["id"], default[n["id"]]), (w, h))) for n in self.nodes()}

    def node_at(self, px, py):
        x, y, _, _ = self.areas()["graph"]
        for node_id, (nx, ny) in self.positions().items():
            if (px - x - nx) ** 2 + (py - y - ny) ** 2 <= 22 ** 2:
                return node_id
        return None

    def changed(self, saved=False):
        self.saved = saved
        self.graph_dirty = True
        with open(self.work_template, "w") as f:
            json.dump(self.tmpl, f, indent=2)
        self.regenerate_at = blue.os.GetWallclockTimeNow() + int(REGENERATE_AFTER_S * 1e7)

    def regenerate(self):
        for proc in self.procs.values():
            end(proc)
        self.procs, self.errors = {}, {}
        for k in range(SEEDS):
            seed = self.seed_base + k
            out = os.path.join(self.work, "act%d.bin" % seed)
            if os.path.exists(out):
                os.remove(out)
            self.procs[seed] = run.start(self.work_template, seed, out, debug=True)
            self.results.pop(seed, None)

    def poll(self):
        for seed, proc in list(self.procs.items()):
            if proc.poll() is None:
                continue
            del self.procs[seed]
            out = os.path.join(self.work, "act%d.bin" % seed)
            if proc.returncode == 0 and os.path.exists(out):
                self.results[seed] = run.load(out)
                self.draw_preview(seed)
            else:
                self.errors[seed] = "failed (exit %d): is there one start, one boss, and a path between them?" % (
                    proc.returncode,)

    def draw_preview(self, seed):
        k = seed - self.seed_base
        if 0 <= k < SEEDS and seed in self.results:
            result = self.results[seed]
            self.previews[k].show(draw.act_image(result["debug"], result["payload"], draw.LAYERS[self.layer]))

    # Editing.
    def toggle_edge(self, a, b):
        edges = self.tmpl["edges"]
        for k, e in enumerate(edges):
            if {e[0], e[1]} == {a, b}:
                if len(e) < 3 or e[2] == "main":
                    edges[k] = [e[0], e[1], "branch"]
                else:
                    del edges[k]
                return
        edges.append([a, b])

    def cut_edge(self, a, b):
        self.tmpl["edges"] = [e for e in self.tmpl["edges"] if {e[0], e[1]} != {a, b}]

    def add_node(self, px, py):
        x, y, w, h = self.areas()["graph"]
        k = 1
        while self.node("node%d" % k):
            k += 1
        node_id = "node%d" % k
        self.nodes().append({"id": node_id, "type": "path", "size": [300, 500]})
        self.tmpl["editor"]["positions"][node_id] = [min(1, max(0, (px - x) / w)), min(1, max(0, (py - y) / h))]
        self.selected = node_id

    def edit_selected(self, key):
        n = self.node(self.selected)
        if n is None:
            return False
        if key == ord("T"):
            n["type"] = draw.TYPES[(draw.TYPES.index(n["type"]) + 1) % len(draw.TYPES)]
        elif key in (VK["lbracket"], VK["rbracket"]):
            step = SIZE_STEP if key == VK["rbracket"] else -SIZE_STEP
            n["size"] = [max(60, n["size"][0] + step), max(100, n["size"][1] + step)]
        elif key == ord("R"):
            current = n.get("repeat", [1, 1])
            n["repeat"] = REPEATS[(REPEATS.index(current) + 1) % len(REPEATS)] if current in REPEATS else [1, 1]
            if n["repeat"] == [1, 1]:
                del n["repeat"]
        elif key == ord("H"):
            current = n.get("chance", 1.0)
            n["chance"] = CHANCES[(CHANCES.index(current) + 1) % len(CHANCES)] if current in CHANCES else 1.0
            if n["chance"] == 1.0:
                del n["chance"]
        elif key == VK["delete"]:
            self.tmpl["nodes"] = [m for m in self.nodes() if m["id"] != self.selected]
            self.tmpl["edges"] = [e for e in self.tmpl["edges"] if self.selected not in e[:2]]
            self.tmpl["editor"]["positions"].pop(self.selected, None)
            self.selected = None
        else:
            return False
        return True

    def save(self):
        with open(self.path, "w", newline="\n") as f:
            json.dump(self.tmpl, f, indent=2)
            f.write("\n")
        self.saved = True
        self.status = "saved " + os.path.relpath(self.path, ROOT)

    def stop_play(self):
        """Stops the game processes this editor started: the ones running from its own run folders."""
        folders = " -or ".join(r"$_.ExecutablePath -like '*\.run\%s\*'" % name for name in PLAY_RUNS)
        subprocess.run(["pwsh", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name = 'exefile_Internal.exe'\" | Where-Object { %s } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % folders],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # Their launchers return once the games are gone.
        for proc in self.play_procs:
            end(proc)
        self.play_procs = []

    def play(self):
        """A server on the picked seed of this template as it stands, and a client to walk it."""
        self.stop_play()
        seed = self.seed_base + self.picked
        play_template = os.path.join(self.work, "play.json")
        shutil.copy(self.work_template, play_template)
        script = os.path.join(ROOT, "run_demo.ps1")
        env = dict(os.environ, ARPG_MODE="act", ARPG_ACT=play_template, ARPG_SEED=str(seed), NET_PORT=str(PLAY_PORT),
                   NET_HOST="127.0.0.1", ARPG_JOIN="127.0.0.1:%d" % PLAY_PORT, PYTHONUNBUFFERED="1")
        for target, run_name in zip(("arpg_server.py", "arpg_client.py"), PLAY_RUNS):
            self.play_procs.append(subprocess.Popen(
                ["pwsh", "-NoProfile", "-File", script, "-Script", os.path.join(HERE, target), "-RunName", run_name],
                env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
            blue.synchro.SleepWallclock(1500)
        self.status = "playing seed %d on port %d" % (seed, PLAY_PORT)

    # Input.
    def on_mouse_down(self, button, x, y):
        if button != MOUSE_LEFT:
            return
        gx, gy, gw, gh = self.areas()["graph"]
        if gx <= x <= gx + gw and gy <= y <= gy + gh:
            hit = self.node_at(x, y)
            if self.connecting and hit and self.selected and hit != self.selected:
                if self.connecting == "cut":
                    self.cut_edge(self.selected, hit)
                else:
                    self.toggle_edge(self.selected, hit)
                self.connecting = None
                self.changed()
            elif hit:
                self.selected, self.drag = hit, hit
                self.graph_dirty = True
            else:
                self.selected, self.connecting = None, None
                self.graph_dirty = True
            return
        for k, rect in enumerate(self.preview_rects()):
            if rect[0] <= x <= rect[0] + rect[2] and rect[1] <= y <= rect[1] + rect[3]:
                self.picked = k

    def on_mouse_up(self, button, x, y):
        if self.drag is not None:
            self.drag = None
            self.changed(saved=False)

    def on_mouse_move(self, x, y):
        self.mouse = (x, y)
        if self.drag is not None:
            gx, gy, gw, gh = self.areas()["graph"]
            self.tmpl["editor"]["positions"][self.drag] = [min(1, max(0, (x - gx) / gw)), min(1, max(0, (y - gy) / gh))]
            self.graph_dirty = True

    def on_key_down(self, key, flags):
        if key == VK["escape"]:
            carbonapp.quit()
        elif key == ord("N"):
            self.add_node(*self.mouse)
            self.changed()
        elif key in (ord("C"), ord("X")) and self.selected:
            mode = "link" if key == ord("C") else "cut"
            self.connecting = None if self.connecting == mode else mode
            self.graph_dirty = True
        elif key == ord("L"):
            self.layer = (self.layer + 1) % len(draw.LAYERS)
            for seed in self.results:
                self.draw_preview(seed)
        elif key in (VK["pgup"], VK["pgdn"]):
            self.seed_base = max(1, self.seed_base + (SEEDS if key == VK["pgdn"] else -SEEDS))
            self.regenerate()
        elif key == VK["space"]:
            self.regenerate()
        elif key == VK["f2"]:
            self.save()
        elif key == ord("P"):
            carbonapp.spawn(self.play)
        elif self.edit_selected(key):
            self.changed()

    # Drawing.
    def preview_rects(self):
        mx, my, mw, mh = self.areas()["maps"]
        cw, ch = (mw - 12) / 2, (mh - 12) / 2
        return [(mx + (k % 2) * (cw + 12), my + (k // 2) * (ch + 12), cw, ch) for k in range(SEEDS)]

    def layout_frame(self):
        areas = self.areas()
        gx, gy, gw, gh = areas["graph"]
        for p, (x, y, w, h) in zip(self.panels, (areas["graph"], areas["inspector"], areas["maps"])):
            p.displayX, p.displayY, p.displayWidth, p.displayHeight = x - 4, y - 4, w + 8, h + 8
        if self.graph_dirty:
            self.graph_dirty = False
            edges = [(e[0], e[1], e[2] if len(e) > 2 else "main") for e in self.tmpl["edges"]]
            self.graph.show(draw.graph_image(int(gw), int(gh), self.nodes(), edges, self.positions(), self.selected,
                                             self.connecting))
        self.graph.place(gx, gy, gw, gh)
        positions = self.positions()
        for label, n in zip(self.labels, self.nodes() + [None] * len(self.labels)):
            if n is None:
                label.set("")
                label.obj.displayX = -10000
                continue
            extra = (" x%d-%d" % tuple(n["repeat"]) if n.get("repeat") else "") + (
                " %d%%" % (n["chance"] * 100) if "chance" in n else "")
            label.set(n["id"] + extra)
            nx, ny = positions[n["id"]]
            k = self.nodes().index(n)
            label.obj.displayX = gx + nx - label.width / 2
            label.obj.displayY = gy + ny + (22 if k % 2 else -44)
        for k, (image, caption, rect) in enumerate(zip(self.previews, self.captions, self.preview_rects())):
            seed = self.seed_base + k
            x, y, w, h = rect
            iw, ih = image.size
            scale = min(w / iw, (h - 24) / ih)
            image.place(x + (w - iw * scale) / 2, y + 22, iw * scale, ih * scale)
            if seed in self.results:
                feats = self.results[seed]["payload"]["features"]
                floor = int(self.results[seed]["debug"]["floor"].sum())
                text = "seed %d   floor %d cells   %d packs   %d arena gates%s" % (
                    feats["seed"], floor, len(feats["packs"]), len(self.results[seed]["payload"]["gates"]),
                    "   < picked" if k == self.picked else "")
            else:
                text = "seed %d   %s" % (seed, self.errors.get(seed, "generating..."))
            caption.set(text)
            caption.obj.displayX, caption.obj.displayY = x, y
            caption.obj.color = (1.0, 0.85, 0.5, 1.0) if k == self.picked else TEXT
        ix, iy, _, _ = areas["inspector"]
        n = self.node(self.selected)
        inspector = ["%s%s   layer: %s" % (os.path.basename(self.path), "" if self.saved else " *", draw.LAYERS[self.layer]),
                     ("%s: %s, %d-%d cells%s%s" % (n["id"], n["type"], n["size"][0], n["size"][1],
                                                     ", repeat %d-%d" % tuple(n["repeat"]) if n.get("repeat") else "",
                                                     ", chance %d%%" % (n["chance"] * 100) if "chance" in n else ""))
                     if n else "no node selected",
                     {"link": "C: click a node to link it", "cut": "X: click a node to cut its link"}.get(self.connecting, ""),
                     self.status, ""]
        title = self.lines[0]
        title.set("ACT EDITOR")
        title.obj.displayX, title.obj.displayY = 14, 12
        help_line = self.lines[5]
        help_line.set(HELP)
        help_line.obj.displayX, help_line.obj.displayY = 150, 14
        for k, (line, string) in enumerate(zip(self.lines[1:5], inspector)):
            line.set(string)
            line.obj.displayX, line.obj.displayY = ix, iy + k * 24

    def test_edits(self, frame):
        """EDITOR_TEST=1: a scripted round of edits, as clicks and keys would make them."""
        steps = {30: lambda: setattr(self, "selected", "pit"), 40: lambda: self.on_key_down(ord("T"), 0),
                 50: lambda: self.on_key_down(VK["rbracket"], 0), 60: lambda: self.on_key_down(ord("R"), 0),
                 70: lambda: self.on_key_down(ord("H"), 0), 80: lambda: self.on_key_down(ord("L"), 0),
                 90: lambda: (self.on_mouse_move(300, 650), self.on_key_down(ord("N"), 0)),
                 100: lambda: self.on_key_down(ord("C"), 0),
                 110: lambda: self.on_mouse_down(MOUSE_LEFT, *self.node_screen("deeps")),
                 120: lambda: (setattr(self, "selected", "hoard"), self.on_key_down(VK["delete"], 0)),
                 130: lambda: setattr(self, "selected", "grotto"), 135: lambda: self.on_key_down(ord("X"), 0),
                 140: lambda: self.on_mouse_down(MOUSE_LEFT, *self.node_screen("pit"))}
        if os.environ.get("EDITOR_TEST_PLAY") == "1":
            steps = {60: lambda: self.on_key_down(ord("P"), 0)}
        if frame in steps:
            steps[frame]()

    def node_screen(self, node_id):
        gx, gy, _, _ = self.areas()["graph"]
        x, y = self.positions()[node_id]
        return gx + x, gy + y

    def frame_loop(self):
        exit_after = int(os.environ.get("EDITOR_EXIT_AFTER", "0"))
        testing = os.environ.get("EDITOR_TEST") == "1"
        frame = 0
        for _ in carbonapp.frames():
            if testing:
                self.test_edits(frame)
            w, h = self.areas()["size"]
            self.scene.displayWidth, self.scene.displayHeight = w, h
            if self.regenerate_at and blue.os.GetWallclockTimeNow() >= self.regenerate_at:
                self.regenerate_at = 0
                self.regenerate()
            self.poll()
            for image in [self.graph] + self.previews:
                image.update()
            self.layout_frame()
            frame += 1
            if exit_after and frame >= exit_after:
                from offscreen import capture_job
                capture_job(trinity, self.job, w, h, path=os.path.join(HERE, "out", "act_editor.png"))
                carbonapp.quit()

    def shutdown(self):
        for proc in self.procs.values():
            end(proc)
        if self.play_procs:
            self.stop_play()
        shutil.rmtree(self.work, ignore_errors=True)


def main():
    editor = Editor(os.environ.get("ARPG_ACT", "caves"))
    carbonapp.at_exit(editor.shutdown)
    carbonapp.spawn(editor.frame_loop)


if __name__ == "__main__":
    carbonapp.run(main)
