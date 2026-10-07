"""ARPG_AUTOPLAY=1: the client plays itself with the companion's brain, through the same paths a player's input takes."""
import random

import blue

import carbonapp
from arpg_brain import Brain

THINK_MS = 100
MENU_S, AIM_HOLD_S = 1.4, 0.6
CURSOR_RATE, CLICK_S = 14.0, 0.12


class ViewerActs:
    """Brain acts played through the viewer: casts show at once, and picks and readying open their menus first."""

    def __init__(self, viewer):
        self.v = viewer
        self.pending = None
        self.release_aim_at = 0
        self.stopped = False
        self.cursor, self.click_until, self.menu_target = None, 0, None

    def _now(self):
        return blue.os.GetWallclockTimeNow()

    def goto(self, x, z):
        self.stopped = False
        self.v.sim.goto((x, 0.0, z), mark=False)
        self.v.sim.goto_marker = None

    def direction(self, ax, az):
        self.stopped = False
        self.v.sim.move_direction(ax, az)

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.v.sim.stop()

    def _aim(self, x, z):
        self.v.test_target = (x, 0.0, z)
        self.click_until = self._now() + int(CLICK_S * 1e7)
        self.release_aim_at = self._now() + int(AIM_HOLD_S * 1e7)

    def blink(self, x, z):
        self.stopped = False
        self._aim(x, z)
        self.v.do_blink()

    def roll(self, dx, dz):
        self.stopped = False
        self.v.do_roll((dx, dz))

    def jump(self):
        self.v.do_jump()

    def cast(self, spell, x=None, z=None, yaw=None):
        if x is not None:
            self._aim(x, z)
        self.v.use_spell(spell)

    def _after_menu(self, menu, action, target):
        if self.pending is None:
            self.v.menu_open = menu
            self.menu_target = target
            self.pending = (self._now() + int(MENU_S * 1e7), action)

    def pick(self, choice):
        self._after_menu("upgrades", lambda: self.v.sim.client.send("pick", choice),
                         lambda: self.v.upgrade_screen.actions[choice][0] if choice < len(self.v.upgrade_screen.actions) else None)

    def ready(self):
        if self.v.near_shrine():
            self._after_menu("shrine", lambda: self.v.sim.client.send("ready", True),
                             lambda: self.v.shrine_menu.buttons[0].box.rect)
        else:
            self.v.sim.client.send("ready", True)

    def update(self):
        now = self._now()
        if self.pending is not None and now >= self.pending[0]:
            _, action = self.pending
            self.pending, self.menu_target = None, None
            action()
            self.click_until = now + int(CLICK_S * 1e7)
            self.v.close_menu()
        if self.release_aim_at and now >= self.release_aim_at:
            self.release_aim_at = 0
            self.v.test_target = None

    def pointer(self, dt, project, own, width, height):
        """Where the glove is drawn this frame and whether it is pressed: it glides to the aim point or menu button."""
        goal = None
        rect = self.menu_target() if self.menu_target else None
        if rect:
            goal = (rect[0] + rect[2] * 0.3, rect[1] + rect[3] * 0.5)
        elif self.v.test_target is not None:
            goal = project(self.v.test_target)
        elif own is not None:
            goal = project((own[0] + 2.0, own[1], own[2] - 1.0))
        if goal is None:
            goal = (width / 2.0, height / 2.0)
        if self.cursor is None:
            self.cursor = goal
        k = min(1.0, CURSOR_RATE * dt)
        self.cursor = (self.cursor[0] + (goal[0] - self.cursor[0]) * k, self.cursor[1] + (goal[1] - self.cursor[1]) * k)
        return self.cursor, self._now() < self.click_until


def run(viewer):
    acts = viewer.autopilot
    sim = viewer.sim
    brain = Brain(sim.client, sim.state, acts, random.Random(7))
    viewer.bus.on(("slam", "rain", "charge", "fuse"), lambda event: brain.warn(event.key, event.name, event.data))
    while True:
        blue.synchro.SleepWallclock(THINK_MS)
        if sim.client.synced:
            brain.think()
            acts.update()


def start(viewer):
    viewer.autopilot = ViewerActs(viewer)
    carbonapp.spawn(run, viewer)
