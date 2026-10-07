import math

from hud import TextLine

NUMBER_LIFE_S, NUMBER_RISE_MPS = 0.7, 1.4
SHADOW = (0.0, 0.0, 0.0)
# Trinity's text blend scales only the glyph colour by alpha, not how much it darkens what is behind it, so
# transparent text still draws dark: text here is either shown opaque or moved off screen.
OFF_SCREEN = -10000.0


class _Text:
    """A text line with Trinity's built-in drop shadow, shown in a colour or cleared."""

    def __init__(self, trinity, scene, size, font="body"):
        self.buffer = TextLine(trinity, size, font)
        self.obj = self.buffer.obj
        offset = max(1, size // 12)
        self.obj.shadowOffset = (offset, offset)
        self.obj.shadowColor = SHADOW + (1.0,)
        self.obj.displayX = OFF_SCREEN
        scene.children.append(self.obj)
        self.width = 0
        self.string = ""

    def set(self, string):
        self.string = string
        self.width = self.buffer.set(string)

    def place(self, x, y, color):
        if color is None:
            # Hidden text also gives back its glyphs: a sprite scene only has room for so much text per frame.
            if self.string:
                self.set("")
            self.obj.displayX = OFF_SCREEN
            return
        self.obj.displayX, self.obj.displayY = x, y
        self.obj.color = tuple(color) + (1.0,)


class FloatingNumbers:
    """Damage numbers that rise from where a hit landed and fade, drawn in the 2D HUD scene."""

    def __init__(self, trinity, scene, count=32, size=22):
        self.items = [[_Text(trinity, scene, size, "bold"), None, 0.0, (1, 1, 1)] for _ in range(count)]
        self.next = 0

    def spawn(self, position, text, color):
        item = self.items[self.next]
        self.next = (self.next + 1) % len(self.items)
        item[0].set(text)
        jitter = ((self.next * 0.37) % 1.0 - 0.5) * 0.5
        item[1], item[2], item[3] = (position[0] + jitter, position[1], position[2]), 0.0, color

    def update(self, dt, project):
        for item in self.items:
            text, position, age, color = item
            if position is None:
                continue
            age += dt
            item[2] = age
            screen = project((position[0], position[1] + NUMBER_RISE_MPS * age, position[2]))
            if age >= NUMBER_LIFE_S or screen is None:
                if age >= NUMBER_LIFE_S:
                    item[1] = None
                text.place(0, 0, None)
                continue
            text.place(screen[0] - text.width / 2.0, screen[1], color)


class Banner:
    """One large centred line with a smaller one under it (wave announcements, level-ups), shown for a while."""

    def __init__(self, trinity, scene, size=40):
        self.text = _Text(trinity, scene, size, "title")
        self.sub = _Text(trinity, scene, 20)
        self.until = 0.0
        self.clock = 0.0
        self.color = (1.0, 1.0, 1.0)

    def show(self, title, subtitle="", seconds=2.0, color=(1.0, 0.85, 0.5)):
        self.text.set(title)
        self.sub.set(subtitle or " ")
        self.color = color
        self.until = self.clock + seconds

    def update(self, dt, width, height):
        self.clock += dt
        shown = self.color if self.clock < self.until else None
        for text, y in ((self.text, height * 0.28), (self.sub, height * 0.28 + 52)):
            text.place((width - text.width) / 2.0, y, shown)


class BossBar:
    """A wide health bar with the boss's name across the top of the screen while a boss is alive."""

    WIDTH, HEIGHT, TOP = 520.0, 12.0, 136.0
    FILL, ENRAGED, BACK = (0.75, 0.12, 0.1, 1.0), (1.0, 0.3, 0.05, 1.0), (0.05, 0.05, 0.07, 0.85)

    def __init__(self, trinity, scene):
        self.name = _Text(trinity, scene, 18, "title")
        self.name.set("THE WARLORD")
        self.fill, self.back = trinity.Tr2Sprite2d(), trinity.Tr2Sprite2d()
        for sprite in (self.fill, self.back):
            sprite.spriteEffect = trinity.TR2_SFX_FILL
            sprite.blendMode = trinity.TR2_SBM_BLEND
            sprite.displayX = OFF_SCREEN
            scene.children.append(sprite)
        self.back.color = self.BACK

    def update(self, boss, width, height):
        if not boss or boss.get("dead") or "hp" not in boss:
            self.name.place(0, 0, None)
            self.fill.displayX = self.back.displayX = OFF_SCREEN
            return
        fraction = max(0.0, boss["hp"] / float(boss["max_hp"]))
        x = (width - self.WIDTH) / 2.0
        self.name.place((width - self.name.width) / 2.0, self.TOP - 26, (1.0, 0.82, 0.5))
        self.back.displayX, self.back.displayY = x - 2, self.TOP - 2
        self.back.displayWidth, self.back.displayHeight = self.WIDTH + 4, self.HEIGHT + 4
        self.fill.displayX, self.fill.displayY, self.fill.displayHeight = x, self.TOP, self.HEIGHT
        self.fill.displayWidth = fraction * self.WIDTH
        self.fill.color = self.ENRAGED if fraction <= 0.5 else self.FILL


class WorldBars:
    """Screen-space health bars over characters: a dark backing with a coloured fill, sized with camera zoom."""

    BACK = (0.05, 0.05, 0.07, 0.85)
    WIDTH, HEIGHT, BORDER = 46.0, 6.0, 1.0

    def __init__(self, trinity, scene, count=96):
        self.bars = []
        for _ in range(count):
            fill, back = trinity.Tr2Sprite2d(), trinity.Tr2Sprite2d()
            # Sprite scenes draw last-added first: add the fill before the backing it sits on.
            for sprite in (fill, back):
                sprite.spriteEffect = trinity.TR2_SFX_FILL
                sprite.blendMode = trinity.TR2_SBM_BLEND
                sprite.displayX = OFF_SCREEN
                scene.children.append(sprite)
            back.color = self.BACK
            self.bars.append((fill, back))

    def update(self, items, project, scale=1.0):
        """items: (world position, fraction 0..1, rgba colour)."""
        w, h, b = self.WIDTH * scale, max(3.0, self.HEIGHT * scale), max(1.0, self.BORDER * scale)
        used = 0
        for position, fraction, color in items:
            if used >= len(self.bars):
                break
            screen = project(position)
            if screen is None:
                continue
            fill, back = self.bars[used]
            used += 1
            x, y = screen[0] - w / 2.0, screen[1] - h / 2.0
            back.displayX, back.displayY, back.displayWidth, back.displayHeight = x - b, y - b, w + 2 * b, h + 2 * b
            fill.displayX, fill.displayY, fill.displayHeight = x, y, h
            fill.displayWidth = max(0.0, min(1.0, fraction)) * w
            fill.color = color
        for fill, back in self.bars[used:]:
            fill.displayX = back.displayX = OFF_SCREEN


def projector(eye, target, fov, width, height):
    """World-to-screen for the orbit camera; returns None for points behind it."""
    fx, fy, fz = (t - e for t, e in zip(target, eye))
    n = math.sqrt(fx * fx + fy * fy + fz * fz) or 1.0
    fx, fy, fz = fx / n, fy / n, fz / n
    # Same basis as OrbitCamera.ray: right = forward x up, up' = right x forward.
    rx, ry, rz = -fz, 0.0, fx
    rn = math.sqrt(rx * rx + rz * rz) or 1.0
    rx, rz = rx / rn, rz / rn
    ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx
    half_h = math.tan(fov / 2.0)
    half_w = half_h * width / float(height)

    def project(p):
        px, py, pz = p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]
        depth = px * fx + py * fy + pz * fz
        if depth < 0.1:
            return None
        sx = (px * rx + pz * rz) / (depth * half_w)
        sy = (px * ux + py * uy + pz * uz) / (depth * half_h)
        return (sx + 1.0) * 0.5 * width, (1.0 - sy) * 0.5 * height
    return project
