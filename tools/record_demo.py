"""Records the ARPG demo video with OBS: terminals type the dist launchers, autopiloted clients play, scenes are joined.

OBS captures only the windows this script opens (composed on a 1080p canvas) and the game's own audio, using its own
profile and scene collection, and switches back to yours afterwards. Only processes it started are ever stopped."""
import argparse
import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time
import uuid

import obsws_python as obs
import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "carbon-crawler")
TYPER = os.path.join(ROOT, "tools", "demo", "type_and_run.ps1")
OUT = os.path.join(ROOT, "demo", "out", "video")
SERVER_LOG = os.path.join(DIST, "logs", "arpg_server.log")
PROFILE = COLLECTION = "carbon-crawler demo"
CANVAS_W, CANVAS_H, STRIP_H = 1920, 1080, 270
COMMON = {"NET_PORT": "47410", "NET_HOST": "127.0.0.1"}
SERVER = {"ARPG_MODE": "waves", "INTERMISSION_S": "20"}
BOSS_SERVER = {"ARPG_MODE": "waves", "ARPG_FIRST_WAVE": "5", "INTERMISSION_S": "12", "ARPG_TEST_UPGRADES": "vitality:2"}
CLIENT = {"ARPG_AUTOPLAY": "1"}

user32 = ctypes.windll.user32
SWP_NOZORDER, SWP_NOACTIVATE, WM_CLOSE = 0x0004, 0x0010, 0x0010


def log(*args):
    print("[demo %s]" % time.strftime("%H:%M:%S"), *args, flush=True)


def windows():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title, cls = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append((hwnd, pid.value, title.value, cls.value))
        return True

    user32.EnumWindows(visit, 0)
    return found


def give_back_focus(hwnd):
    """New windows take the keyboard; hand it straight back to whatever the person at the machine was using."""
    if not hwnd or not user32.IsWindow(hwnd):
        return
    # Windows only lets the foreground thread hand focus on, so borrow its input queue for the call.
    ours = ctypes.windll.kernel32.GetCurrentThreadId()
    theirs = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    user32.AttachThreadInput(ours, theirs, True)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(ours, theirs, False)


def obs_window(title, cls, exe):
    # OBS names a window as title:class:exe, with ':' written as '#3A'.
    return ":".join(part.replace(":", "#3A") for part in (title, cls, exe))


def wait_for(test, timeout, what, step=0.2):
    end = time.time() + timeout
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(step)
    raise RuntimeError("timed out waiting for " + what)


class Scene:
    """One recorded scene: the terminals it opened, the processes they started, and the OBS sources showing them."""

    live = []

    def __init__(self, rec, name):
        self.rec, self.name, self.started = rec, name, time.time()
        Scene.live.append(self)
        self.tag = uuid.uuid4().hex[:12]
        self.terminals, self.inputs = [], []
        if os.path.exists(SERVER_LOG):
            os.remove(SERVER_LOG)
        rec.new_scene(name)

    def shells(self):
        # The pwsh processes behind this scene's terminals, recognised by the tag passed to each.
        return [p for p in psutil.process_iter(["name", "cmdline"])
                if p.info["name"] == "pwsh.exe" and self.tag in " ".join(p.info["cmdline"] or [])]

    def ours(self):
        procs = []
        for shell in self.shells():
            try:
                procs += shell.children(recursive=True)
            except psutil.Error:
                pass
        return procs

    def games(self, script):
        found = []
        for p in self.ours():
            try:
                if p.name() == "exefile_Internal.exe" and any(script in part for part in p.cmdline()):
                    found.append(p)
            except psutil.Error:
                pass
        return sorted(found, key=lambda p: p.create_time())

    def terminal(self, title, command, env, rect, delay_s):
        b64 = base64.b64encode(json.dumps(dict(COMMON, **env)).encode()).decode()
        before = user32.GetForegroundWindow()
        # Focus mode drops the tab row and title strip, leaving just the text.
        subprocess.Popen(["wt", "-w", "new", "--focus", "--title", title, "--suppressApplicationTitle",
                          "--colorScheme", "One Half Dark", "pwsh", "-NoProfile",
                          "-ExecutionPolicy", "Bypass", "-File", TYPER, "-Command", command, "-EnvB64", b64,
                          "-DelayS", str(delay_s), "-Dir", DIST, "-Tag", self.tag])
        hwnd, _, _, cls = wait_for(lambda: next((w for w in windows() if w[2] == title), None), 20, "terminal " + title)
        give_back_focus(before)
        # Windows Terminal settles its own size just after opening, so size it again once it has.
        for _ in range(2):
            user32.SetWindowPos(hwnd, 0, 40 + 30 * len(self.terminals), 40 + 30 * len(self.terminals), 620, 175,
                                SWP_NOZORDER | SWP_NOACTIVATE)
            time.sleep(1.0)
        self.terminals.append(hwnd)
        self.inputs.append(self.rec.window_source(self.name, "%s %s" % (self.name, title), obs_window(title, cls, "WindowsTerminal.exe"),
                                                  rect))

    def game(self, index, title, rect, audio=False, timeout=60):
        before = user32.GetForegroundWindow()
        def find():
            clients = self.games("arpg_client.py")
            if len(clients) <= index:
                return None
            pid = clients[index].pid
            return next((w for w in windows() if w[1] == pid and w[2] == title), None)
        hwnd, _, _, cls = wait_for(find, timeout, "client window " + title)
        give_back_focus(before)
        target = obs_window(title, cls, "exefile_Internal.exe")
        self.inputs.append(self.rec.window_source(self.name, "%s %s" % (self.name, title), target, rect))
        if audio:
            self.inputs.append(self.rec.audio_source(self.name, "%s %s audio" % (self.name, title), target))
        return hwnd

    def close_clients(self):
        pids = {p.pid for p in self.games("arpg_client.py")}
        for hwnd, pid, _, _ in windows():
            if pid in pids:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    def finish(self):
        if self in Scene.live:
            Scene.live.remove(self)
        else:
            return
        for p in self.ours():
            try:
                if p.name() == "exefile_Internal.exe":
                    p.terminate()
            except psutil.Error:
                pass
        time.sleep(1.5)
        # A terminal only closes once its shell is gone, so end this scene's tagged shells (and anything left under
        # them) before closing their windows.
        for shell in self.shells():
            for p in shell.children(recursive=True) + [shell]:
                try:
                    p.terminate()
                except psutil.Error:
                    pass
        time.sleep(0.5)
        for hwnd in self.terminals:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        self.rec.drop(self.inputs)
        time.sleep(1.0)


def wait_log(patterns, timeout):
    patterns = [patterns] if isinstance(patterns, str) else patterns

    def seen():
        try:
            with open(SERVER_LOG, encoding="utf-8", errors="replace") as f:
                text = f.read()
                return any(p in text for p in patterns)
        except OSError:
            return False
    try:
        return wait_for(seen, timeout, "server log: %s" % patterns, step=0.5)
    except RuntimeError as e:
        log(e)
        return False


class Recorder:
    def __init__(self):
        cfg = json.load(open(os.path.expandvars(r"%APPDATA%\obs-studio\plugin_config\obs-websocket\config.json")))
        self.c = obs.ReqClient(host="localhost", port=cfg["server_port"], password=cfg.get("server_password"), timeout=10)
        self.files = []

    def setup(self):
        c = self.c
        self.old_profile = c.get_profile_list().current_profile_name
        self.old_collection = c.get_scene_collection_list().current_scene_collection_name
        if PROFILE not in c.get_profile_list().profiles:
            c.create_profile(PROFILE)
        c.set_current_profile(PROFILE)
        time.sleep(1.0)
        os.makedirs(OUT, exist_ok=True)
        c.set_profile_parameter("Output", "Mode", "Simple")
        for key, value in (("FilePath", OUT), ("RecFormat2", "mp4"), ("RecQuality", "HQ"), ("RecEncoder", "nvenc")):
            c.set_profile_parameter("SimpleOutput", key, value)
        c.set_video_settings(60, 1, CANVAS_W, CANVAS_H, CANVAS_W, CANVAS_H)
        if COLLECTION not in c.get_scene_collection_list().scene_collections:
            c.create_scene_collection(COLLECTION)
        else:
            c.set_current_scene_collection(COLLECTION)
        time.sleep(1.5)
        # The collection is ours alone: start it empty, so nothing captures the desktop or the default audio device.
        for i in c.get_input_list().inputs:
            c.remove_input(i["inputName"])
        log("OBS ready: profile and scene collection", PROFILE)

    def new_scene(self, name):
        if name not in [s["sceneName"] for s in self.c.get_scene_list().scenes]:
            self.c.create_scene(name)
            self.c.create_input(name, name + " backdrop", "color_source_v3",
                                {"color": 0xFF120C10, "width": CANVAS_W, "height": CANVAS_H}, True)
        self.c.set_current_program_scene(name)

    def window_source(self, scene, name, target, rect):
        settings = {"window": target, "method": 2, "capture_cursor": False, "client_area": True}
        item = self.c.create_input(scene, name, "window_capture", settings, True).scene_item_id
        x, y, w, h = rect
        self.c.set_scene_item_transform(scene, item, {"positionX": x, "positionY": y, "boundsType": "OBS_BOUNDS_SCALE_INNER",
                                                      "boundsWidth": w, "boundsHeight": h, "boundsAlignment": 0})
        return name

    def audio_source(self, scene, name, target):
        self.c.create_input(scene, name, "wasapi_process_output_capture", {"window": target, "priority": 2}, True)
        return name

    def drop(self, names):
        for name in names:
            try:
                self.c.remove_input(name)
            except Exception:
                pass

    def start(self):
        for _ in range(2):
            self.c.start_record()
            try:
                wait_for(lambda: self.c.get_record_status().output_active, 20, "recording to start")
                return
            except RuntimeError:
                log("recording did not start, retrying")
        raise RuntimeError("OBS would not start recording")

    def stop(self):
        path = self.c.stop_record().output_path
        wait_for(lambda: not self.c.get_record_status().output_active, 20, "recording to stop")
        self.files.append(path)
        log("saved", path)

    def restore(self):
        try:
            self.c.set_current_scene_collection(self.old_collection)
            time.sleep(1.0)
            self.c.set_current_profile(self.old_profile)
            log("OBS back on", self.old_profile, "/", self.old_collection)
        except Exception as e:
            log("could not restore OBS:", e)


def strip(i, n):
    w = CANVAS_W // n
    return (i * w, CANVAS_H - STRIP_H, w, STRIP_H)


GAME_AREA = (0, 0, CANVAS_W, CANVAS_H - STRIP_H)


def half(i):
    return (i * CANVAS_W // 2, 0, CANVAS_W // 2, CANVAS_H - STRIP_H)


def client_env(title, size="1600x675", **extra):
    return dict(dict(CLIENT, VIEWER_SIZE=size, ARPG_WINDOW_TITLE=title, ARPG_CAM_DISTANCE="14"), **extra)


def scene_solo(rec):
    s = Scene(rec, "solo")
    s.terminal("server", r".\arpg_server.cmd", SERVER, strip(0, 2), 1.5)
    rec.start()
    s.terminal("client", r".\arpg_client.cmd", client_env("Carbon Crawler"), strip(1, 2), 4.0)
    s.game(0, "Carbon Crawler", GAME_AREA, audio=True)
    wait_log("wave 2  fight", 240)
    time.sleep(25)
    s.close_clients()
    time.sleep(3)
    rec.stop()
    s.finish()


def scene_pair(rec):
    s = Scene(rec, "pair")
    s.terminal("server", r".\arpg_server.cmd", SERVER, strip(0, 3), 1.5)
    rec.start()
    s.terminal("client 1", r".\arpg_client.cmd", client_env("Carbon Crawler 1", "960x810"), strip(1, 3), 4.0)
    s.terminal("client 2", r".\arpg_client.cmd", client_env("Carbon Crawler 2", "960x810", ARPG_AUDIO="0"), strip(2, 3), 6.5)
    s.game(0, "Carbon Crawler 1", half(0), audio=True)
    s.game(1, "Carbon Crawler 2", half(1))
    wait_log("wave 2  fight", 150)
    time.sleep(35)
    s.close_clients()
    time.sleep(3)
    rec.stop()
    s.finish()


def scene_companion(rec, boss=False):
    s = Scene(rec, "boss" if boss else "companion")
    s.terminal("server", r".\arpg_server.cmd", BOSS_SERVER if boss else SERVER, strip(0, 2), 1.5)
    rec.start()
    # Further out for the boss, so the Warlord stays in frame whichever mage he goes for.
    env = client_env("Carbon Crawler", ARPG_CAM_DISTANCE="19") if boss else client_env("Carbon Crawler")
    s.terminal("client", r".\arpg_client.cmd companion", env, strip(1, 2), 4.0)
    s.game(0, "Carbon Crawler", GAME_AREA, audio=True)
    if boss:
        wait_log(["wave 5  intermission", "wave 6  "], 240)
        time.sleep(5)
    else:
        time.sleep(55)
    s.close_clients()
    time.sleep(3)
    rec.stop()
    s.finish()


def join(files, out):
    listing = os.path.join(OUT, "parts.txt")
    with open(listing, "w") as f:
        for path in files:
            f.write("file '%s'\n" % path.replace("\\", "/"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", out],
                   check=True)
    log("joined", out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", default="solo,pair,companion,boss")
    args = parser.parse_args()
    rec = Recorder()
    rec.setup()
    scenes = {"solo": scene_solo, "pair": scene_pair, "companion": scene_companion,
              "boss": lambda r: scene_companion(r, boss=True)}
    try:
        for name in args.scenes.split(","):
            log("scene", name)
            try:
                scenes[name](rec)
            finally:
                for scene in list(Scene.live):
                    scene.finish()
            time.sleep(2)
    finally:
        if rec.c.get_record_status().output_active:
            rec.stop()
        rec.restore()
    if len(rec.files) > 1:
        join(rec.files, os.path.join(OUT, "carbon_arpg_demo.mp4"))


if __name__ == "__main__":
    sys.exit(main())
