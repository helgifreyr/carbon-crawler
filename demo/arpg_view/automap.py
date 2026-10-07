"""The automap: every cell the player has seen, turned to match the camera; a corner minimap, or full size on Tab."""
import math
import os

import arpg_world as world
from arpg_map import CELL, FLOOR
from pngfile import palette_png

REVEAL_M, REDRAW_S = 14.0, 0.4
PX_PER_CELL = 1.5
MINI_PX, MINI_VIEW_M, FULL_SHARE = 220, 90.0, 0.8
# Palette: unseen, floor, wall, shrine, exit.
PALETTE = [(0, 0, 0, 0), (150, 140, 122, 165), (70, 62, 56, 235), (255, 205, 90, 255), (120, 205, 255, 255)]
UNSEEN, FLOOR_PX, WALL_PX, SHRINE_PX, EXIT_PX = range(5)
OFF_SCREEN = -10000


def sprite(trinity, scene, path):
    s = trinity.Tr2Sprite2d()
    s.spriteEffect = trinity.TR2_SFX_COPY
    s.blendMode = trinity.TR2_SBM_BLEND
    s.texturePrimary = trinity.Tr2Sprite2dTexture()
    s.texturePrimary.resPath = path
    s.displayX = OFF_SCREEN
    scene.children.append(s)
    return s


class Automap:
    def __init__(self, trinity, scene, gen_dir):
        self.trinity, self.scene, self.gen_dir = trinity, scene, gen_dir
        self.map = self.dot = None
        # Each redraw goes to a new file in a new texture, swapped in once it has loaded (sprite textures are cached).
        self.version, self.pending = 0, None
        self.level, self.full = None, os.environ.get("ARPG_TEST_FULLMAP") == "1"
        self.since, self.dirty, self.last_reveal = 0.0, False, None
        self.exit_shown = False

    def set_level(self, level, yaw):
        """Works out which cell each map pixel shows, with the camera's forward direction pointing up."""
        self.level = level
        cells = level.cells
        fx, fz = -math.sin(yaw), -math.cos(yaw)
        self.right, self.forward = (-fz, fx), (fx, fz)
        corners = [(x, z) for x in cells.extent[0::2] for z in cells.extent[1::2]]
        us = [self.u(x, z) for x, z in corners]
        vs = [self.v(x, z) for x, z in corners]
        self.u0, self.v0 = min(us), min(vs)
        step = CELL / PX_PER_CELL
        self.step = step
        self.width, self.height = int((max(us) - self.u0) / step) + 1, int((max(vs) - self.v0) / step) + 1
        lookup = []
        for py in range(self.height):
            v = self.v0 + (py + 0.5) * step
            for px in range(self.width):
                u = self.u0 + (px + 0.5) * step
                x, z = u * self.right[0] - v * self.forward[0], u * self.right[1] - v * self.forward[1]
                i, j = cells.cell_of(x, z)
                lookup.append(j * cells.nx + i if 0 <= i < cells.nx and 0 <= j < cells.nz else -1)
        self.lookup = lookup
        self.kind = bytearray(cells.nx * cells.nz)
        for j in range(cells.nz):
            for i in range(cells.nx):
                if cells.get(i, j) == FLOOR:
                    self.kind[j * cells.nx + i] = FLOOR_PX
                elif cells.is_wall(i, j):
                    self.kind[j * cells.nx + i] = WALL_PX
        for x, z in world.SHRINES:
            self.mark(x, z, SHRINE_PX)
        self.seen = bytearray(cells.nx * cells.nz)
        self.exit_shown, self.dirty, self.last_reveal = False, True, None
        if self.map is None:
            self.map = sprite(self.trinity, self.scene, "res:/arpg/ui/orb_fill.png")
            self.map.texturePrimary = None
            self.dot = sprite(self.trinity, self.scene, "res:/arpg/ui/orb_fill.png")

    def u(self, x, z):
        return x * self.right[0] + z * self.right[1]

    def v(self, x, z):
        return -(x * self.forward[0] + z * self.forward[1])

    def mark(self, x, z, kind, radius=1):
        cells = self.level.cells
        ci, cj = cells.cell_of(x, z)
        for j in range(cj - radius, cj + radius + 1):
            for i in range(ci - radius, ci + radius + 1):
                if 0 <= i < cells.nx and 0 <= j < cells.nz:
                    self.kind[j * cells.nx + i] = kind

    def reveal(self, x, z):
        if self.last_reveal and math.hypot(x - self.last_reveal[0], z - self.last_reveal[1]) < 1.0:
            return
        self.last_reveal = (x, z)
        cells = self.level.cells
        ci, cj = cells.cell_of(x, z)
        r = int(REVEAL_M / CELL)
        for j in range(max(0, cj - r), min(cells.nz, cj + r + 1)):
            for i in range(max(0, ci - r), min(cells.nx, ci + r + 1)):
                k = j * cells.nx + i
                if not self.seen[k] and (i - ci) ** 2 + (j - cj) ** 2 <= r * r:
                    self.seen[k] = 1
                    self.dirty = True

    def draw(self):
        shown = bytes(self.kind[k] if k >= 0 and self.seen[k] else UNSEEN for k in self.lookup)
        self.version += 1
        name = "automap_%d.png" % self.version
        with open(os.path.join(self.gen_dir, name), "wb") as f:
            f.write(palette_png(self.width, self.height, shown, PALETTE))
        texture = self.trinity.Tr2Sprite2dTexture()
        texture.resPath = "gen:/" + name
        self.pending = (texture, self.version)
        stale = os.path.join(self.gen_dir, "automap_%d.png" % (self.version - 3))
        if os.path.exists(stale):
            os.remove(stale)

    def swap_in(self):
        if self.pending is None:
            return
        texture, _ = self.pending
        atlas = texture.atlasTexture
        if atlas is None or not atlas.isGood:
            return
        self.map.texturePrimary = texture
        self.map.SetDirty()
        self.pending = None

    def toggle(self):
        self.full = not self.full

    def update(self, dt, own, exit_at, width, height):
        if self.level is not world.LEVEL or self.map is None or own is None:
            return
        x, _, z = own
        self.reveal(x, z)
        if exit_at and not self.exit_shown:
            self.mark(exit_at[0], exit_at[1], EXIT_PX)
            self.exit_shown, self.dirty = True, True
        self.since += dt
        if self.dirty and self.since >= REDRAW_S and self.pending is None:
            self.since, self.dirty = 0.0, False
            self.draw()
        self.swap_in()
        if self.map.texturePrimary is None:
            return
        px, py = (self.u(x, z) - self.u0) / self.step, (self.v(x, z) - self.v0) / self.step
        tex = self.map.texturePrimary
        if self.full:
            sx, sy, sw, sh = 0, 0, self.width, self.height
            scale = min(width * FULL_SHARE / sw, height * FULL_SHARE / sh)
            left, top = (width - sw * scale) / 2, (height - sh * scale) / 2
            alpha = 0.92
        else:
            # The corner shows a window of the map around the player.
            sw = sh = min(MINI_VIEW_M / self.step, max(self.width, self.height))
            sx = max(0.0, min(self.width - sw, px - sw / 2))
            sy = max(0.0, min(self.height - sh, py - sh / 2))
            scale = MINI_PX / sw
            left, top = width - MINI_PX - 16, 16
            alpha = 0.85
        tex.srcX, tex.srcY, tex.srcWidth, tex.srcHeight = sx, sy, sw, sh
        m = self.map
        m.displayX, m.displayY = left, top
        m.displayWidth, m.displayHeight = sw * scale, sh * scale
        m.color = (1.0, 1.0, 1.0, alpha)
        size = 8 if not self.full else 10
        d = self.dot
        d.displayX = left + (px - sx) * scale - size / 2
        d.displayY = top + (py - sy) * scale - size / 2
        d.displayWidth = d.displayHeight = size
        d.color = (0.4, 0.75, 1.0, 1.0)

    def hide(self):
        for s in (self.map, self.dot):
            if s is not None:
                s.displayX = OFF_SCREEN
