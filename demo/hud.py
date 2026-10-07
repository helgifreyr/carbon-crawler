# Alegreya Sans for reading, Cinzel's carved capitals for titles (both SIL OFL, licenses next to them).
FONTS = {"body": "res:/fonts/AlegreyaSans-Medium.ttf", "bold": "res:/fonts/AlegreyaSans-Bold.ttf",
         "title": "res:/fonts/Cinzel-Bold.ttf"}
FONT = FONTS["body"]


class Hud:
    def __init__(self, trinity, width, height, lines=4, font_size=16, padding=10):
        self.trinity = trinity
        self.font_size = font_size
        self.padding = padding
        self.line_height = int(font_size * 1.4)

        self.scene = trinity.Tr2Sprite2dScene()
        self.scene.displayWidth, self.scene.displayHeight = width, height

        self.lines = []
        for i in range(lines):
            line = TextLine(trinity, font_size)
            text = line.obj
            text.color = (0.92, 0.95, 1.0, 1.0)
            text.displayX = padding * 2
            text.displayY = padding * 2 + i * self.line_height
            self.scene.children.append(text)
            self.lines.append(line)

        self.panel = trinity.Tr2Sprite2d()
        self.panel.spriteEffect = trinity.TR2_SFX_FILL
        self.panel.blendMode = trinity.TR2_SBM_BLEND
        self.panel.color = (0.02, 0.03, 0.06, 0.65)
        self.panel.displayX = self.panel.displayY = padding
        self.panel.displayHeight = padding * 2 + lines * self.line_height
        self.panel.displayWidth = 200
        self.scene.children.append(self.panel)

    def resize(self, width, height):
        self.scene.displayWidth, self.scene.displayHeight = width, height

    def set_lines(self, strings):
        widest = 0
        for line, string in zip(self.lines, list(strings) + [""] * len(self.lines)):
            line.set(string)
            widest = max(widest, line.width)
        self.panel.displayWidth = widest + self.padding * 2 if widest else 0


class TextLine:
    """A text object and its font measurer."""

    short = 0

    def __init__(self, trinity, size, font="body"):
        self.measurer = trinity.Tr2FontMeasurer()
        self.measurer.font = FONTS[font]
        self.measurer.fontSize = size
        # Tr2FontMeasurer never initialises its width limit, so a fresh one can hold garbage that makes AddText stop
        # after a character or two.
        self.measurer.limit = 0
        self.obj = trinity.Tr2Sprite2dTextObject()
        self.obj.fontMeasurer = self.measurer
        self.string, self.width = None, 0

    def set(self, string):
        if string == self.string:
            return self.width
        measurer = self.measurer
        measurer.Reset()
        measurer.cursorX = 0
        if string:
            added = measurer.AddText(string)
            if added != len(string):
                TextLine.short += 1
                if TextLine.short <= 5:
                    print("[text] short layout: %r -> %d chars; limit %r cursorX %r font %r size %r letterSpace %r" % (
                        string[:24], added, measurer.limit, measurer.cursorX, measurer.font, measurer.fontSize,
                        measurer.letterSpace))
        measurer.CommitText(0, measurer.ascender)
        self.obj.textWidth = max(1, measurer.cursorX)
        self.obj.textHeight = max(1, measurer.ascender - measurer.descender)
        self.string, self.width = string, measurer.cursorX
        return self.width
