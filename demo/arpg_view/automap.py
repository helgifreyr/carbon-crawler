"""The automap: every cell the player has seen, turned to match the camera; a corner minimap, or full size on Tab.

It is drawn as flat triangles in a primitive scene of its own, not as a texture: a texture rewritten as you explore
fills Trinity's sprite atlas, which then shows other sprites' garbage."""
import math
import os

import arpg_world as world
from arpg_map import CELL, FLOOR

FLAT_EFFECT = "res:/graphics/effect/game/flat2d.fx"
REVEAL_M, SUBMIT_S = 14.0, 0.25
PX_PER_CELL = 1.5
MINI_PX, MINI_VIEW_M, FULL_SHARE = 220, 90.0, 0.8
COLORS = {"floor": (0.59, 0.55, 0.48, 0.65), "wall": (0.27, 0.24, 0.22, 0.92), "shrine": (1.0, 0.8, 0.35, 1.0),
          "exit": (0.47, 0.8, 1.0, 1.0)}
OFF_SCREEN = -10000


class Automap:
    def __init__(self, trinity, sprites, make_effect):
        self.trinity = trinity
        self.scene = trinity.Tr2PrimitiveScene()
        self.effect, self.params = make_effect(FLAT_EFFECT, ScreenSize=(1280.0, 800.0, 0.0, 0.0),
                                               MapXform=(1.0, 0.0, 0.0, 0.0), ClipRect=(0.0, 0.0, 0.0, 0.0))
        self.solids = None
        self.dot = trinity.Tr2Sprite2d()
        self.dot.spriteEffect = trinity.TR2_SFX_COPY
        self.dot.blendMode = trinity.TR2_SBM_BLEND
        self.dot.texturePrimary = trinity.Tr2Sprite2dTexture()
        self.dot.texturePrimary.resPath = "res:/arpg/ui/orb_fill.png"
        self.dot.displayX = OFF_SCREEN
        sprites.children.append(self.dot)
        self.level, self.full = None, os.environ.get("ARPG_TEST_FULLMAP") == "1"
        self.since, self.dirty, self.last_reveal = 0.0, False, None
        self.exit_shown = False

    def set_level(self, level, yaw):
        """Starts the map over for a level, with the camera's forward direction pointing up."""
        self.level = level
        cells = level.cells
        fx, fz = -math.sin(yaw), -math.cos(yaw)
        self.right, self.forward = (-fz, fx), (fx, fz)
        corners = [(x, z) for x in cells.extent[0::2] for z in cells.extent[1::2]]
        self.u0, self.v0 = min(self.u(x, z) for x, z in corners), min(self.v(x, z) for x, z in corners)
        self.step = CELL / PX_PER_CELL
        self.width = (max(self.u(x, z) for x, z in corners) - self.u0) / self.step
        self.height = (max(self.v(x, z) for x, z in corners) - self.v0) / self.step
        self.seen = bytearray(cells.nx * cells.nz)
        self.shrine_cells = {cells.cell_of(x, z) for x, z in world.SHRINES}
        if self.solids is not None:
            self.scene.primitives.remove(self.solids)
        self.solids = self.trinity.Tr2SolidSet()
        self.solids.effect = self.effect
        self.scene.primitives.append(self.solids)
        self.exit_shown, self.dirty, self.last_reveal = False, True, None

    def u(self, x, z):
        return x * self.right[0] + z * self.right[1]

    def v(self, x, z):
        return -(x * self.forward[0] + z * self.forward[1])

    def pixel(self, x, z):
        return (self.u(x, z) - self.u0) / self.step, (self.v(x, z) - self.v0) / self.step

    def quad(self, x0, z0, x1, z1, color):
        a, b, c, d = (self.pixel(x, z) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)))
        for p, q, r in ((a, b, c), (a, c, d)):
            self.solids.AddTriangle((p[0], p[1], 0.0), color, (q[0], q[1], 0.0), color, (r[0], r[1], 0.0), color)
        self.dirty = True

    def marker(self, x, z, color, half=1.6):
        self.quad(x - half, z - half, x + half, z + half, color)

    def reveal(self, x, z):
        if self.last_reveal and math.hypot(x - self.last_reveal[0], z - self.last_reveal[1]) < 1.0:
            return
        self.last_reveal = (x, z)
        cells = self.level.cells
        ci, cj = cells.cell_of(x, z)
        r = int(REVEAL_M / CELL)
        markers = []
        for j in range(max(0, cj - r), min(cells.nz, cj + r + 1)):
            for i in range(max(0, ci - r), min(cells.nx, ci + r + 1)):
                k = j * cells.nx + i
                if self.seen[k] or (i - ci) ** 2 + (j - cj) ** 2 > r * r:
                    continue
                self.seen[k] = 1
                if cells.get(i, j) == FLOOR:
                    self.quad(*cells.cell_rect(i, j), COLORS["floor"])
                elif cells.is_wall(i, j):
                    self.quad(*cells.cell_rect(i, j), COLORS["wall"])
                if (i, j) in self.shrine_cells:
                    markers.append(cells.cell_rect(i, j))
        # Markers go in last, so they draw over the cells around them.
        for x0, z0, x1, z1 in markers:
            self.marker((x0 + x1) / 2, (z0 + z1) / 2, COLORS["shrine"])

    def toggle(self):
        self.full = not self.full

    def update(self, dt, own, exit_at, width, height):
        if self.level is not world.LEVEL or self.solids is None or own is None:
            self.hide()
            return
        x, _, z = own
        self.reveal(x, z)
        if exit_at and not self.exit_shown:
            self.marker(exit_at[0], exit_at[1], COLORS["exit"], 2.0)
            self.exit_shown = True
        self.since += dt
        if self.dirty and self.since >= SUBMIT_S:
            self.since, self.dirty = 0.0, False
            self.solids.SubmitChanges()
        px, py = self.pixel(x, z)
        if self.full:
            scale = min(width * FULL_SHARE / self.width, height * FULL_SHARE / self.height)
            box = ((1 - FULL_SHARE) / 2 * width, (1 - FULL_SHARE) / 2 * height, (1 + FULL_SHARE) / 2 * width,
                   (1 + FULL_SHARE) / 2 * height)
        else:
            scale = MINI_PX / (MINI_VIEW_M / self.step)
            box = (width - MINI_PX - 16, 16, width - 16, 16 + MINI_PX)
        # The player sits at the middle of the box; the map slides beneath.
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        self.params["ScreenSize"].value = (float(width), float(height), 0.0, 0.0)
        self.params["MapXform"].value = (scale, cx - px * scale, cy - py * scale, 0.0)
        self.params["ClipRect"].value = box
        size = 10 if self.full else 8
        self.dot.displayX, self.dot.displayY = cx - size / 2, cy - size / 2
        self.dot.displayWidth = self.dot.displayHeight = size
        self.dot.color = (0.4, 0.75, 1.0, 1.0)

    def hide(self):
        self.params["ClipRect"].value = (0.0, 0.0, 0.0, 0.0)
        self.dot.displayX = OFF_SCREEN
