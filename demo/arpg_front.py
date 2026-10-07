"""The client's front end: the main menu (servers to join, a game to host) and the loading screen in front of play."""
import os
import subprocess

import blue

import carbonapp
from arpg_menu import GOLD, WHITE, DIM, Box, Menu
from arpg_ui import _Text
from net_client import probe

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_PORT = 47400
PROBE_EVERY_MS = 3000
# The loading screen stays up until nothing has been waiting to load for this many frames in a row.
SETTLED_FRAMES = 20
MIN_LOADING_S = 0.6
COVER = (0.02, 0.025, 0.04, 1.0)
VK_BACK, VK_RETURN, VK_ESCAPE, VK_DELETE, VK_OEM_PERIOD, VK_OEM_1, VK_OEM_MINUS = 0x08, 0x0D, 0x1B, 0x2E, 0xBE, 0xBA, 0xBD
MAX_SERVERS = 5


def parse(address):
    host, _, port = address.strip().partition(":")
    return host, int(port) if port.isdigit() else DEFAULT_PORT


class FrontEnd:
    """Owns the menu and loading screens; the viewer asks it what mode the client is in and forwards input."""

    def __init__(self, trinity, scene, settings, save):
        self.settings, self.save = settings, save
        # Sprite scenes draw last-added first: the loading text goes in before the cover behind it.
        self.loading_title = _Text(trinity, scene, 34, "title")
        self.loading_lines = [_Text(trinity, scene, 17) for _ in range(3)]
        self.menu = Menu(trinity, scene, MAX_SERVERS + 3, width=560)
        self.menu.on_close = lambda: None
        self.cover = Box(trinity, scene, COVER)
        self.mode, self.message = "menu", ""
        self.status, self.offered = {}, []
        self.typing = None
        self.hovered = None
        self.server_proc = None
        self.target = None
        self.loading_since, self.settled = 0, 0
        carbonapp.spawn(self._probe_loop)

    # The server list.
    def servers(self):
        listed = [a for a in self.settings["servers"] if a not in self.offered]
        return (self.offered + listed)[:MAX_SERVERS]

    def offer(self, address):
        """Lists a server for this session only (one named in the environment), at the top."""
        if address not in self.offered:
            self.offered.insert(0, address)

    def _probe_loop(self):
        while True:
            if self.mode == "menu":
                for address in self.servers():
                    carbonapp.spawn(self._probe, address)
            blue.synchro.SleepWallclock(PROBE_EVERY_MS)

    def _probe(self, address):
        self.status[address] = probe(*parse(address))

    # Modes.
    def connect(self, sim, address, attempts=5):
        self.target = address
        sim.connect(*parse(address), attempts=attempts)
        self.begin_loading("connecting to %s" % address)

    def begin_loading(self, why):
        self.mode, self.message = "loading", why
        self.loading_since, self.settled = blue.os.GetWallclockTimeNow(), 0

    def to_menu(self, message=""):
        self.mode, self.message = "menu", message
        self.status = {}

    def host(self, sim):
        """Starts a server here and joins it once it is up (generating its first act takes a few seconds)."""
        self.stop_server()
        dev = os.path.join(ROOT, "run_demo.ps1")
        if os.path.exists(dev):
            args = ["pwsh", "-NoProfile", "-File", dev, "-Script", os.path.join(HERE, "arpg_server.py"),
                    "-RunName", "local_server"]
        else:
            args = ["cmd", "/c", os.path.join(ROOT, "arpg_server.cmd")]
        port = int(os.environ.get("ARPG_HOST_PORT", DEFAULT_PORT))
        env = dict(os.environ, NET_PORT=str(port))
        self.server_proc = subprocess.Popen(args, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.connect(sim, "127.0.0.1:%d" % port, attempts=30)
        self.message = "starting a server here"

    def stop_server(self):
        if self.server_proc is not None and self.server_proc.poll() is None:
            # The launcher runs the server as a child: end the whole tree.
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.server_proc.pid)], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.server_proc.wait(5)
        self.server_proc = None

    def check_loading(self, sim, ready, waiting_on):
        """Leaves the loading screen once the world is ready and the resource queue has been empty a while."""
        client = sim.client
        if client.failed:
            self.to_menu("no server answered at %s" % self.target)
            return
        if client.lost:
            self.to_menu("the connection to %s closed" % self.target)
            return
        resman = blue.resMan
        quiet = ready and not resman.pendingLoads and not resman.pendingPrepares
        self.settled = self.settled + 1 if quiet else 0
        self.message = waiting_on
        shown_s = blue.os.TimeDiffInMs(self.loading_since, blue.os.GetWallclockTimeNow()) / 1000.0
        if self.settled >= SETTLED_FRAMES and shown_s >= MIN_LOADING_S:
            self.mode = "playing"

    # Drawing.
    def draw(self, sim, width, height, clock):
        if self.mode == "playing":
            self.cover.hide()
            self.loading_title.place(0, 0, None)
            for line in self.loading_lines:
                line.place(0, 0, None)
            self.menu.hide()
            return
        self.cover.place(0, 0, width, height)
        if self.mode == "loading":
            self.menu.hide()
            self.loading_title.set("LOADING")
            self.loading_title.place((width - self.loading_title.width) / 2, height * 0.42, GOLD)
            dots = "." * (1 + int(clock * 2.5) % 3)
            for line, (text, color) in zip(self.loading_lines, ((self.message + dots, WHITE),
                                                                (self.target or "", DIM), ("", DIM))):
                line.set(text)
                line.place((width - line.width) / 2, height * 0.42 + 58 + 26 * self.loading_lines.index(line), color)
            return
        self.loading_title.place(0, 0, None)
        for line in self.loading_lines:
            line.place(0, 0, None)
        items = []
        for address in self.servers():
            info = self.status.get(address)
            if address not in self.status:
                note = "asking..."
            elif info is None:
                note = "no answer"
            else:
                players = info.get("players", 0)
                note = "%s   %d player%s" % (info.get("act", "?"), players, "" if players == 1 else "s")
            items.append((address, note, lambda a=address: self.connect(sim, a), info is not None, "resume"))
        if self.typing is not None:
            items.append(("Address: %s_" % self.typing, "type host or host:port, Enter adds it, Esc cancels", None,
                          True, "controls"))
        else:
            items.append(("Add a server", "then type its address", self.start_typing, True, "controls"))
        items.append(("Host a game here", "starts a server on this machine and joins it", lambda: self.host(sim),
                      True, "ready"))
        items.append(("Quit", "", carbonapp.quit, True, "quit"))
        note = self.message or "pick a server; hover one and press Delete to forget it"
        self.menu.show("CARBON CRAWLER", note, items, width, height, row_h=46)
        self.menu.close.hide()

    # Input.
    def start_typing(self):
        self.typing = ""

    def click(self, x, y):
        self.menu.click(x, y)

    def hover(self, x, y):
        self.menu.hover(x, y)
        self.hovered = None
        for button, address in zip(self.menu.buttons, self.servers()):
            if button.box.contains(x, y):
                self.hovered = address

    def key(self, key):
        """Keys while the menu is up; True if the key was used."""
        if self.typing is not None:
            if key == VK_RETURN:
                address = self.typing.strip()
                if address and address not in self.settings["servers"]:
                    self.settings["servers"] = (self.settings["servers"] + [address])[-MAX_SERVERS:]
                    self.save()
                self.typing = None
            elif key == VK_ESCAPE:
                self.typing = None
            elif key == VK_BACK:
                self.typing = self.typing[:-1]
            elif len(self.typing) < 40:
                char = {VK_OEM_PERIOD: ".", VK_OEM_1: ":", VK_OEM_MINUS: "-"}.get(key)
                if char is None and (0x30 <= key <= 0x39 or 0x41 <= key <= 0x5A):
                    char = chr(key).lower()
                if char:
                    self.typing += char
            return True
        if key == VK_DELETE and self.hovered and len(self.settings["servers"]) > 1:
            self.settings["servers"].remove(self.hovered)
            self.status.pop(self.hovered, None)
            self.hovered = None
            self.save()
            return True
        return False
