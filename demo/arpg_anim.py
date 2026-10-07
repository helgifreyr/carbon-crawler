import json
import math
import os

ANIMS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "res", "arpg", "anims")
FADE_S = 0.15
_tables = {}


def table(model):
    if model not in _tables:
        with open(os.path.join(ANIMS, model + ".json")) as f:
            _tables[model] = json.load(f)
    return _tables[model]


class Track:
    def __init__(self, clip, rate=1.0):
        self.clip = clip
        self.rate = rate
        self.phase = 0.0

    def finished(self, meta):
        return not meta["loop"] and self.phase >= 1.0

    def advance(self, meta, dt, distance):
        dt *= self.rate
        if meta["loop"] and meta["stride"] and distance is not None:
            self.phase = (self.phase + distance / meta["stride"]) % 1.0
        elif meta["loop"]:
            self.phase = (self.phase + dt * meta["fps"] / meta["frames"]) % 1.0
        else:
            self.phase = min(1.0, self.phase + dt * meta["fps"] / (meta["frames"] - 1))

    def rows(self, meta, height):
        n = meta["frames"]
        if meta["loop"]:
            f = (self.phase % 1.0) * n
            a = int(f) % n
            b = (a + 1) % n
        else:
            f = self.phase * (n - 1)
            a = min(int(f), n - 1)
            b = min(a + 1, n - 1)
        row = meta["row"]
        return (row + a + 0.5) / height, (row + b + 0.5) / height, f - int(f)


class Animator:
    """Plays one baked clip at a time on a VAT model, crossfading from the previous one."""

    def __init__(self, model):
        self.meta = table(model)
        self.current = Track("idle")
        self.previous = None
        self.fade, self.fade_s = 1.0, FADE_S

    def playing(self):
        return self.current.clip

    def finished(self):
        return self.current.finished(self.meta["clips"][self.current.clip])

    def play(self, clip, restart=False, rate=1.0, fade_s=FADE_S):
        if clip == self.current.clip and not restart:
            return
        self.previous, self.fade, self.fade_s = self.current, 0.0, fade_s
        self.current = Track(clip, rate)

    def advance(self, dt, distance=None):
        clips = self.meta["clips"]
        self.current.advance(clips[self.current.clip], dt, distance)
        if self.previous is not None:
            self.previous.advance(clips[self.previous.clip], dt, distance)
            self.fade = min(1.0, self.fade + dt / self.fade_s)
            if self.fade >= 1.0:
                self.previous = None

    def params(self):
        height = self.meta["height"]
        clips = self.meta["clips"]
        to = self.current.rows(clips[self.current.clip], height)
        if self.previous is None:
            return to + (0.0,), to + (0.0,)
        frm = self.previous.rows(clips[self.previous.clip], height)
        w = self.fade * self.fade * (3 - 2 * self.fade)
        return frm + (0.0,), to + (w,)


def find_params(placeable, names):
    """The per-instance effect parameters with the given names, or None until the placeable has loaded."""
    res = placeable.placeableRes
    if res is None or res.visualModel is None:
        return None
    found = {name: [] for name in names}
    for mesh in res.visualModel.meshes:
        for area in list(mesh.opaqueAreas) + list(mesh.transparentAreas):
            if area.effect is None:
                continue
            for p in area.effect.parameters:
                if p.name in found:
                    found[p.name].append(p)
    return found if any(found.values()) else None


def heading_sign(velocity, yaw):
    speed = math.hypot(*velocity)
    if speed < 1e-3:
        return 1.0
    forward = (velocity[0] * math.sin(yaw) + velocity[1] * math.cos(yaw)) / speed
    return -1.0 if forward < -0.35 else 1.0
