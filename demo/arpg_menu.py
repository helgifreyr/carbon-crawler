"""Clickable 2D UI for the ARPG client: health and mana orbs, the spell bar and its picker, the Esc and shrine menus.

Sprite scenes draw children last-added first, so every widget adds its text before the box behind it."""
import json
import math
import os

from arpg_ui import OFF_SCREEN, _Text

SETTINGS = os.path.join(os.path.expanduser("~"), ".carbon-crawler", "arpg_settings.json")
SLOTS = ["LMB", "RMB", "Q", "E", "R", "F"]
DEFAULT_BINDINGS = {"LMB": "bolt", "RMB": "nova", "Q": "blink", "E": "chain", "R": "meteor", "F": "frost"}

PANEL = (0.03, 0.04, 0.07, 0.9)
BUTTON, HOVER, DISABLED = (0.12, 0.13, 0.19, 0.95), (0.22, 0.24, 0.34, 0.97), (0.08, 0.08, 0.1, 0.9)
GOLD, WHITE, DIM, POOR = (1.0, 0.85, 0.4), (0.95, 0.96, 1.0), (0.55, 0.56, 0.62), (1.0, 0.5, 0.42)
BACKDROP = (0.0, 0.0, 0.0, 0.45)
UI = "res:/arpg/ui/%s.png"


def load_settings():
    # Spell bindings belong to a run (a character starts at level 1 with the defaults); the rest is saved.
    try:
        with open(SETTINGS) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    def volume(key, old):
        value = data.get(key, 1.0 if data.get(old, True) else 0.0)
        return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 1.0
    servers = [s for s in data.get("servers", []) if isinstance(s, str)] or ["127.0.0.1:47400"]
    return {"bindings": dict(DEFAULT_BINDINGS), "scheme": data.get("scheme", "wasd"),
            "music_volume": volume("music_volume", "music"), "sound_volume": volume("sound_volume", "sounds"),
            "servers": servers}


def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w") as f:
            json.dump({k: v for k, v in settings.items() if k != "bindings"}, f, indent=1)
    except OSError:
        pass


class Box:
    def __init__(self, trinity, scene, color):
        self.sprite = trinity.Tr2Sprite2d()
        self.sprite.spriteEffect = trinity.TR2_SFX_FILL
        self.sprite.blendMode = trinity.TR2_SBM_BLEND
        self.sprite.color = color
        self.sprite.displayX = OFF_SCREEN
        scene.children.append(self.sprite)
        self.rect = None

    def place(self, x, y, w, h, color=None):
        self.rect = (x, y, w, h)
        self.sprite.displayX, self.sprite.displayY, self.sprite.displayWidth, self.sprite.displayHeight = x, y, w, h
        if color is not None:
            self.sprite.color = color

    def hide(self):
        self.rect = None
        self.sprite.displayX = OFF_SCREEN

    def contains(self, x, y):
        if self.rect is None:
            return False
        bx, by, bw, bh = self.rect
        return bx <= x <= bx + bw and by <= y <= by + bh


class Button:
    """A menu row: an icon in a slot frame, a label and a note; `action` runs on click while enabled."""

    ICON = 36

    def __init__(self, trinity, scene, size=16, small=13):
        self.top = _Text(trinity, scene, size)
        self.bottom = _Text(trinity, scene, small)
        self.off = Picture(trinity, scene, "menu_off", 64)
        self.icon = Picture(trinity, scene, "menu_resume", 64)
        self.frame = Picture(trinity, scene, "slot_frame", 128)
        self.box = Box(trinity, scene, BUTTON)
        self.action, self.enabled, self.hover = None, True, False
        self.text, self.icon_name, self.crossed = (None, None), None, False

    def set(self, top, bottom="", action=None, enabled=True, icon=None, crossed=False):
        if (top, bottom) != self.text:
            self.text = (top, bottom)
            self.top.set(top)
            self.bottom.set(bottom)
        self.action, self.enabled, self.icon_name, self.crossed = action, enabled, icon, crossed

    def place(self, x, y, w, h, top_color=WHITE, bottom_color=DIM):
        color = DISABLED if not self.enabled else HOVER if self.hover else BUTTON
        self.box.place(x, y, w, h, color)
        left = x + 12
        if self.icon_name:
            size = self.ICON
            iy = y + (h - size) / 2.0
            self.icon.show("menu_" + self.icon_name)
            self.icon.place(left, iy, size, size, (1.0, 1.0, 1.0, 1.0) if self.enabled else (0.4, 0.4, 0.42, 1.0))
            lit = self.hover and self.enabled
            self.frame.place(left - 3, iy - 3, size + 6, size + 6, (1.0, 0.9, 0.6, 1.0) if lit else (0.8, 0.8, 0.8, 1.0))
            if self.crossed:
                self.off.place(left, iy, size, size)
            else:
                self.off.hide()
            left += size + 12
        else:
            for part in (self.icon, self.off, self.frame):
                part.hide()
        two = bool(self.text[1])
        self.top.place(left, y + (6 if two else (h - 20) / 2.0), top_color if self.enabled else DIM)
        self.bottom.place(left, y + 27, bottom_color if two else None)

    def hide(self):
        # Hidden text gives its glyphs back, so the next set() must lay it out again.
        self.text = (None, None)
        for part in (self.box, self.frame, self.icon, self.off):
            part.hide()
        self.top.place(0, 0, None)
        self.bottom.place(0, 0, None)

    def click(self, x, y):
        if self.box.contains(x, y):
            if self.enabled and self.action:
                self.action()
            return True
        return False


class Picture:
    """A textured sprite from res:/arpg/ui, tinted by its colour; crop() shows only part of the texture."""

    def __init__(self, trinity, scene, name, size):
        self.sprite = trinity.Tr2Sprite2d()
        self.sprite.spriteEffect = trinity.TR2_SFX_COPY
        self.sprite.blendMode = trinity.TR2_SBM_BLEND
        self.texture = trinity.Tr2Sprite2dTexture()
        self.sprite.texturePrimary = self.texture
        self.sprite.displayX = OFF_SCREEN
        self.size, self.name = size, None
        self.show(name)
        scene.children.append(self.sprite)

    def show(self, name):
        if name != self.name:
            self.name = name
            self.texture.resPath = UI % name
            self.crop(0.0, 1.0)

    def crop(self, top, bottom):
        self.texture.srcX, self.texture.srcWidth = 0, self.size
        self.texture.srcY, self.texture.srcHeight = top * self.size, (bottom - top) * self.size

    def place(self, x, y, w, h, color=(1.0, 1.0, 1.0, 1.0)):
        self.sprite.displayX, self.sprite.displayY, self.sprite.displayWidth, self.sprite.displayHeight = x, y, w, h
        self.sprite.color = color

    def hide(self):
        self.sprite.displayX = OFF_SCREEN


class Orb:
    """A glass globe that drains from the top, with its value written across it."""

    SIZE, MARGIN = 150, 22

    def __init__(self, trinity, scene, color):
        self.text = _Text(trinity, scene, 16)
        self.frame = Picture(trinity, scene, "orb_frame", 256)
        self.fill = Picture(trinity, scene, "orb_fill", 256)
        self.back = Picture(trinity, scene, "orb_fill", 256)
        self.color = color

    def update(self, fraction, label, right, width, height):
        size = self.SIZE
        x = width - self.MARGIN - size if right else self.MARGIN
        y = height - self.MARGIN - size
        fraction = max(0.0, min(1.0, fraction))
        self.back.place(x, y, size, size, (0.09, 0.08, 0.1, 1.0))
        self.fill.crop(1.0 - fraction, 1.0)
        self.fill.place(x, y + size * (1.0 - fraction), size, size * fraction, self.color)
        self.frame.place(x, y, size, size)
        self.text.set(label)
        self.text.place(x + (size - self.text.width) / 2.0, y + size / 2.0 - 10, WHITE)


class SpellBar:
    """Six icon slots in the bottom centre with the XP bar under them; clicking one opens an icon picker."""

    SLOT, GAP, BOTTOM, XP_H = 58, 6, 18, 7
    PICK, BADGE = 46, 22

    def __init__(self, trinity, scene, spells, upgrades, settings, on_change):
        self.spells = spells
        self.order = list(spells)
        self.settings, self.on_change = settings, on_change
        self.tip = _Text(trinity, scene, 15)
        self.tip_note = _Text(trinity, scene, 12)
        self.keys = [_Text(trinity, scene, 13, "bold") for _ in SLOTS]
        self.notes = [_Text(trinity, scene, 11) for _ in SLOTS]
        for slot, key in zip(SLOTS, self.keys):
            key.set(slot)
        # Each spell's learned upgrades sit as badges along the top edge of its slot, with a count past one.
        self.spell_upgrades = {s: [u for u, data in upgrades.items() if data["spell"] == s] for s in spells}
        most = max(len(names) for names in self.spell_upgrades.values())
        self.badge_counts = [[_Text(trinity, scene, 12, "bold") for _ in range(most)] for _ in SLOTS]
        self.badges = [[Picture(trinity, scene, "badge_plus", 64) for _ in range(most)] for _ in SLOTS]
        self.upgrades, self.learned = upgrades, {}
        self.frames = [Picture(trinity, scene, "slot_frame", 128) for _ in SLOTS]
        self.icons = [Picture(trinity, scene, "icon_bolt", 128) for _ in SLOTS]
        self.backs = [Box(trinity, scene, BUTTON) for _ in SLOTS]
        self.pick_frames = [Picture(trinity, scene, "slot_frame", 128) for _ in range(len(spells) + 1)]
        self.pick_icons = [Picture(trinity, scene, "icon_bolt", 128) for _ in spells]
        self.clear_text = _Text(trinity, scene, 20)
        self.pick_backs = [Box(trinity, scene, BUTTON) for _ in range(len(spells) + 1)]
        self.panel = Box(trinity, scene, PANEL)
        self.xp_fill = Box(trinity, scene, (0.95, 0.75, 0.25, 0.95))
        self.xp_back = Box(trinity, scene, (0.05, 0.05, 0.08, 0.85))
        self.open_slot, self.mouse, self.unlocked, self.scheme = None, None, lambda spell: True, "wasd"

    def bound(self, slot):
        return self.settings["bindings"].get(slot)

    def bind(self, slot, spell):
        self.settings["bindings"][slot] = spell
        self.open_slot = None
        self.on_change()

    def toggle(self, slot):
        self.open_slot = None if self.open_slot == slot else slot

    def layout(self, width, height):
        total = len(SLOTS) * self.SLOT + (len(SLOTS) - 1) * self.GAP
        left = (width - total) / 2.0
        top = height - self.BOTTOM - self.XP_H - 6 - self.SLOT
        return left, top, total

    def update(self, level, mana, xp_fraction, scheme, width, height, unlocked, learned):
        self.unlocked, self.scheme, self.learned = unlocked, scheme, learned
        left, top, total = self.layout(width, height)
        hovered = None
        for i, slot in enumerate(SLOTS):
            x = left + i * (self.SLOT + self.GAP)
            spell = self.bound(slot)
            back, icon, frame, key, note = self.backs[i], self.icons[i], self.frames[i], self.keys[i], self.notes[i]
            back.place(x, top, self.SLOT, self.SLOT, BUTTON)
            frame.place(x - 2, top - 2, self.SLOT + 4, self.SLOT + 4)
            key.place(x + self.SLOT - 5 - key.width, top + self.SLOT - 17, GOLD)
            if self._over(x, top, self.SLOT, self.SLOT):
                hovered = (x, slot, spell)
            mouse_move = slot == "LMB" and scheme == "mouse"
            self._place_badges(i, None if mouse_move else spell, x, top)
            if mouse_move or spell is None:
                icon.hide()
                note.set("move" if mouse_move else "+")
                note.place(x + (self.SLOT - note.width) / 2.0, top + self.SLOT / 2.0 - 9, DIM)
                continue
            icon.show("icon_" + spell)
            ready = unlocked(spell)
            if not ready:
                tint = (0.28, 0.28, 0.3, 1.0)
            elif mana < self.spells[spell]["mana"]:
                tint = (1.0, 0.42, 0.38, 1.0)
            else:
                tint = (1.0, 1.0, 1.0, 1.0)
            icon.place(x + 3, top + 3, self.SLOT - 6, self.SLOT - 6, tint)
            if ready:
                note.place(0, 0, None)
            else:
                note.set("lvl %d" % self.spells[spell]["level"])
                note.place(x + (self.SLOT - note.width) / 2.0, top + self.SLOT / 2.0 - 9, WHITE)
        xp_top = top + self.SLOT + 6
        self.xp_back.place(left, xp_top, total, self.XP_H)
        self.xp_fill.place(left, xp_top, total * max(0.0, min(1.0, xp_fraction)), self.XP_H)
        picked = self._place_picker(left, top)
        self._place_tip(picked or (hovered and hovered[2] and hovered), top)

    def _taken(self, spell):
        return [(u, self.learned[u]) for u in self.spell_upgrades.get(spell, ()) if self.learned.get(u)]

    def _place_badges(self, i, spell, x, top):
        taken = self._taken(spell)
        size, gap = self.BADGE, 7
        x0 = x + (self.SLOT - len(taken) * size - (len(taken) - 1) * gap) / 2.0
        for k, (badge, count) in enumerate(zip(self.badges[i], self.badge_counts[i])):
            if k >= len(taken):
                badge.hide()
                count.place(0, 0, None)
                continue
            name, stacks = taken[k]
            bx, by = x0 + k * (size + gap), top - size / 2.0
            badge.show("badge_" + self.upgrades[name]["badge"])
            badge.place(bx, by, size, size)
            if stacks > 1:
                count.set(str(stacks))
                count.place(bx + size - 2, by + size - 13, GOLD)
            else:
                count.place(0, 0, None)

    def _place_picker(self, left, top):
        cells = self.pick_backs
        if self.open_slot is None:
            for parts in (self.pick_backs, self.pick_frames, self.pick_icons):
                for part in parts:
                    part.hide()
            self.clear_text.place(0, 0, None)
            self.panel.hide()
            return None
        n, size, gap = len(cells), self.PICK, 6
        width = n * size + (n - 1) * gap
        anchor = left + SLOTS.index(self.open_slot) * (self.SLOT + self.GAP) + self.SLOT / 2.0
        x0 = max(8.0, anchor - width / 2.0)
        y0 = top - 16 - self.BADGE / 2.0 - size
        self.panel.place(x0 - 8, y0 - 8, width + 16, size + 16)
        hovered = None
        for i in range(n):
            x = x0 + i * (size + gap)
            spell = self.order[i] if i < len(self.order) else None
            over = self._over(x, y0, size, size)
            cells[i].place(x, y0, size, size, HOVER if over else BUTTON)
            self.pick_frames[i].place(x - 2, y0 - 2, size + 4, size + 4)
            if spell is None:
                self.clear_text.set("x")
                self.clear_text.place(x + (size - self.clear_text.width) / 2.0, y0 + size / 2.0 - 13, DIM)
                if over:
                    hovered = (x, None, "clear")
                continue
            tint = (1.0, 1.0, 1.0, 1.0) if self.unlocked(spell) else (0.28, 0.28, 0.3, 1.0)
            self.pick_icons[i].show("icon_" + spell)
            self.pick_icons[i].place(x + 3, y0 + 3, size - 6, size - 6, tint)
            if over:
                hovered = (x, None, spell)
        return hovered and (hovered[0], None, hovered[2], y0)

    def _place_tip(self, target, top):
        if not target:
            self.tip.place(0, 0, None)
            self.tip_note.place(0, 0, None)
            return
        x, spell = target[0], target[2]
        y = (target[3] if len(target) > 3 else top - self.BADGE / 2.0) - 46
        if spell == "clear":
            name, note = "Clear slot", ""
        else:
            data = self.spells[spell]
            name = data["label"]
            note = "%d mana" % data["mana"] if self.unlocked(spell) else "unlocks at level %d" % data["level"]
            for name, stacks in self._taken(spell):
                note += "   %s%s" % (self.upgrades[name]["label"], " x%d" % stacks if stacks > 1 else "")
        self.tip.set(name)
        self.tip_note.set(note or " ")
        self.tip.place(x, y, WHITE)
        self.tip_note.place(x, y + 20, DIM if spell == "clear" or self.unlocked(spell) else POOR)

    def _over(self, x, y, w, h):
        return self.mouse is not None and x <= self.mouse[0] <= x + w and y <= self.mouse[1] <= y + h

    def click(self, x, y):
        self.mouse = (x, y)
        for i, cell in enumerate(self.pick_backs):
            if self.open_slot is not None and cell.contains(x, y):
                spell = self.order[i] if i < len(self.order) else None
                if spell is None or self.unlocked(spell):
                    self.bind(self.open_slot, spell)
                return True
        for slot, back in zip(SLOTS, self.backs):
            if back.contains(x, y):
                if not (slot == "LMB" and self.scheme == "mouse"):
                    self.toggle(slot)
                return True
        if self.open_slot is not None:
            self.open_slot = None
            return True
        return False

    def hover(self, x, y):
        self.mouse = (x, y)


class UpgradeIcon:
    """An upgrade drawn as its skill's icon with a badge in the corner for what it changes."""

    def __init__(self, trinity, scene):
        self.badge = Picture(trinity, scene, "badge_plus", 64)
        self.icon = Picture(trinity, scene, "icon_bolt", 128)
        self.frame = Picture(trinity, scene, "slot_frame", 128)

    def place(self, upgrade, x, y, size, tint=(1.0, 1.0, 1.0, 1.0)):
        self.icon.show("icon_" + upgrade["icon"])
        self.badge.show("badge_" + upgrade["badge"])
        self.icon.place(x, y, size, size, tint)
        self.frame.place(x - 2, y - 2, size + 4, size + 4)
        b = size * 0.46
        self.badge.place(x + size - b * 0.85, y + size - b * 0.85, b, b)

    def hide(self):
        for part in (self.badge, self.icon, self.frame):
            part.hide()


class UpgradeScreen:
    """Level-up choices as three cards (click or 1/2/3), and every upgrade learned so far; hover shows what it does."""

    WIDTH, CARD, ICON, LEARNED = 600, 172, 96, 38

    def __init__(self, trinity, scene, upgrades):
        self.upgrades = upgrades
        self.tip = _Text(trinity, scene, 15)
        self.title = _Text(trinity, scene, 22, "title")
        self.note = _Text(trinity, scene, 14)
        self.learned_title = _Text(trinity, scene, 13)
        self.card_names = [_Text(trinity, scene, 16, "title") for _ in range(3)]
        self.card_stacks = [_Text(trinity, scene, 12) for _ in range(3)]
        self.card_keys = [_Text(trinity, scene, 13) for _ in range(3)]
        self.counts = [_Text(trinity, scene, 12) for _ in upgrades]
        self.card_icons = [UpgradeIcon(trinity, scene) for _ in range(3)]
        self.learned_icons = [UpgradeIcon(trinity, scene) for _ in upgrades]
        self.close = CloseX(trinity, scene)
        self.cards = [Box(trinity, scene, BUTTON) for _ in range(3)]
        self.edges = [Box(trinity, scene, Menu.BRONZE) for _ in range(4)]
        self.panel = Box(trinity, scene, PANEL)
        self.texts = [self.tip, self.title, self.note, self.learned_title] + self.card_names + self.card_stacks + \
            self.card_keys + self.counts
        self.mouse, self.actions, self.on_close = None, [], None

    def _over(self, x, y, w, h):
        return self.mouse is not None and x <= self.mouse[0] <= x + w and y <= self.mouse[1] <= y + h

    def show(self, entity, on_pick, width, height):
        offer, picks, owned = entity.get("offer") or [], entity.get("picks", 0), entity.get("upgrades") or {}
        x0, y0 = (width - self.WIDTH) / 2.0, height * 0.16
        self.title.set("LEVEL %d" % entity.get("level", 1))
        self.title.place(x0 + 20, y0 + 14, GOLD)
        self.note.set("%d upgrade%s to choose - click one, or press 1-3" % (picks, "s" if picks != 1 else "") if picks
                      else "nothing to choose - every level brings a new upgrade")
        self.note.place(x0 + 20, y0 + 46, DIM)
        tip = None
        self.actions = []
        gap = (self.WIDTH - 40 - 3 * self.CARD) / 2.0
        card_y = y0 + 80
        card_h = self.ICON + 74
        for i in range(3):
            x = x0 + 20 + i * (self.CARD + gap)
            if i >= len(offer):
                for part in (self.cards[i], self.card_icons[i]):
                    part.hide()
                for text in (self.card_names[i], self.card_stacks[i], self.card_keys[i]):
                    text.place(0, 0, None)
                continue
            up = self.upgrades[offer[i]]
            over = self._over(x, card_y, self.CARD, card_h)
            self.cards[i].place(x, card_y, self.CARD, card_h, HOVER if over else BUTTON)
            self.card_icons[i].place(up, x + (self.CARD - self.ICON) / 2.0, card_y + 14, self.ICON)
            name, stack, key = self.card_names[i], self.card_stacks[i], self.card_keys[i]
            name.set(up["label"])
            name.place(x + (self.CARD - name.width) / 2.0, card_y + self.ICON + 24, WHITE)
            have = owned.get(offer[i], 0)
            stack.set("%d / %d" % (have + 1, up["most"]) if up["most"] > 1 else "")
            stack.place(x + (self.CARD - stack.width) / 2.0, card_y + self.ICON + 46, DIM)
            key.set(str(i + 1))
            key.place(x + 8, card_y + 6, GOLD)
            self.actions.append(((x, card_y, self.CARD, card_h), lambda i=i: on_pick(i)))
            if over:
                tip = up
        learned_y = card_y + card_h + 22
        self.learned_title.set("LEARNED" if owned else "LEARNED - nothing yet")
        self.learned_title.place(x0 + 20, learned_y, DIM)
        row_y, n = learned_y + 24, 0
        for icon, count in zip(self.learned_icons, self.counts):
            icon.hide()
            count.place(0, 0, None)
        for upgrade, stacks in owned.items():
            up = self.upgrades[upgrade]
            x = x0 + 20 + n * (self.LEARNED + 8)
            self.learned_icons[n].place(up, x, row_y, self.LEARNED)
            count = self.counts[n]
            count.set("%d" % stacks if up["most"] > 1 else "")
            count.place(x + 3, row_y + 2, WHITE)
            if self._over(x, row_y, self.LEARNED, self.LEARNED):
                tip = up
            n += 1
        tip_y = row_y + self.LEARNED + 18
        if tip is not None:
            self.tip.set("%s: %s" % (tip["label"], tip["text"]))
            self.tip.place(x0 + 20, tip_y, WHITE)
        else:
            self.tip.place(0, 0, None)
        h = tip_y + 32 - y0
        self.panel.place(x0, y0, self.WIDTH, h)
        for edge, rect in zip(self.edges, ((x0, y0, self.WIDTH, 2), (x0, y0 + h - 2, self.WIDTH, 2), (x0, y0, 2, h),
                                           (x0 + self.WIDTH - 2, y0, 2, h))):
            edge.place(*rect)
        self.close.hover = self._over(x0 + self.WIDTH - CloseX.SIZE - 10, y0 + 10, CloseX.SIZE, CloseX.SIZE)
        self.close.place(x0, y0, self.WIDTH)

    def hide(self):
        for text in self.texts:
            text.place(0, 0, None)
        self.close.hide()
        for part in self.cards + self.card_icons + self.learned_icons + self.edges + [self.panel]:
            part.hide()
        self.actions = []

    def click(self, x, y):
        self.mouse = (x, y)
        if self.close.contains(x, y):
            if self.on_close:
                self.on_close()
            return True
        for (bx, by, bw, bh), action in self.actions:
            if bx <= x <= bx + bw and by <= y <= by + bh:
                action()
                return True
        return self.panel.contains(x, y)

    def hover(self, x, y):
        self.mouse = (x, y)


class LevelUpButton:
    """A pulsing gold button left of the spell bar while upgrades wait; it opens the upgrade screen."""

    SIZE = 44

    def __init__(self, trinity, scene):
        self.count = _Text(trinity, scene, 13)
        self.label = _Text(trinity, scene, 11)
        self.badge = Picture(trinity, scene, "badge_plus", 64)
        self.rect = None

    def update(self, picks, clock, right_edge, top):
        if not picks:
            self.hide()
            return
        size = self.SIZE * (1.0 + 0.06 * math.sin(clock * 5.0))
        x, y = right_edge - self.SIZE - 14, top + 7
        self.rect = (x, y, self.SIZE, self.SIZE)
        c = (self.SIZE - size) / 2.0
        self.badge.place(x + c, y + c, size, size)
        self.count.set(str(picks))
        self.count.place(x + self.SIZE - 8, y - 6, GOLD)
        self.label.set("U")
        self.label.place(x + 2, y + self.SIZE - 12, GOLD)

    def hide(self):
        self.rect = None
        self.badge.hide()
        self.count.place(0, 0, None)
        self.label.place(0, 0, None)

    def click(self, x, y):
        if self.rect is None:
            return False
        bx, by, bw, bh = self.rect
        return bx <= x <= bx + bw and by <= y <= by + bh


class Slider:
    """A 0..1 bar with a knob; click or drag along it, in 5% steps."""

    def __init__(self, trinity, scene):
        self.knob = Box(trinity, scene, GOLD + (1.0,))
        self.fill = Box(trinity, scene, (0.78, 0.6, 0.3, 0.95))
        self.track = Box(trinity, scene, (0.04, 0.04, 0.06, 0.95))
        self.on_change, self.hit = None, None

    def place(self, x, y, w, value, on_change):
        self.on_change = on_change
        self.track.place(x, y - 3, w, 6)
        self.fill.place(x, y - 3, w * value, 6)
        self.knob.place(x + w * value - 5, y - 9, 10, 18)
        self.hit = (x - 8, y - 14, w + 16, 28)

    def hide(self):
        for part in (self.knob, self.fill, self.track):
            part.hide()
        self.hit = None

    def grab(self, x, y):
        if self.hit is None or self.on_change is None:
            return False
        hx, hy, hw, hh = self.hit
        if not (hx <= x <= hx + hw and hy <= y <= hy + hh):
            return False
        self.drag(x)
        return True

    def drag(self, x):
        hx, _, hw, _ = self.hit
        value = max(0.0, min(1.0, (x - hx - 8) / (hw - 16)))
        self.on_change(round(value * 20) / 20.0)


class CloseX:
    """The small x in a panel's top-right corner."""

    SIZE = 26

    def __init__(self, trinity, scene):
        self.text = _Text(trinity, scene, 16)
        self.box = Box(trinity, scene, BUTTON)
        self.text.set("x")
        self.hover = False

    def place(self, panel_x, panel_y, panel_w):
        x, y = panel_x + panel_w - self.SIZE - 10, panel_y + 10
        self.box.place(x, y, self.SIZE, self.SIZE, HOVER if self.hover else BUTTON)
        self.text.set("x")
        self.text.place(x + (self.SIZE - self.text.width) / 2.0, y + 2, GOLD if self.hover else WHITE)

    def hide(self):
        self.box.hide()
        self.text.place(0, 0, None)

    def contains(self, x, y):
        return self.box.contains(x, y)


class Menu:
    """A centred bronze-framed panel with a title, a note, a close x and a column of icon rows (some with a slider)."""

    BRONZE = (0.62, 0.47, 0.25, 1.0)
    SLIDER_W = 150

    def __init__(self, trinity, scene, rows, width=380):
        self.title = _Text(trinity, scene, 22, "title")
        self.note = _Text(trinity, scene, 14)
        self.close = CloseX(trinity, scene)
        self.sliders = [Slider(trinity, scene) for _ in range(rows)]
        self.buttons = [Button(trinity, scene, 16, 13) for _ in range(rows)]
        self.rule = Box(trinity, scene, GOLD + (0.7,))
        self.edges = [Box(trinity, scene, self.BRONZE) for _ in range(4)]
        self.panel = Box(trinity, scene, PANEL)
        self.width, self.open = width, False
        self.on_close, self.dragging = None, None

    def show(self, title, note, items, width, height, row_h=50):
        """items: (label, note, action, enabled[, icon[, crossed[, slider value, on_change]]]) per row."""
        x, y = (width - self.width) / 2.0, height * 0.22
        self.title.set(title)
        self.note.set(note or " ")
        self.title.place(x + 20, y + 14, GOLD)
        self.close.place(x, y, self.width)
        self.rule.place(x + 20, y + 44, self.width - 40, 1)
        self.note.place(x + 20, y + 52, DIM)
        for i, (button, slider) in enumerate(zip(self.buttons, self.sliders)):
            if i >= len(items):
                button.hide()
                slider.hide()
                continue
            item = tuple(items[i]) + (None, False, None, None)[len(items[i]) - 4:]
            top, bottom, action, enabled, icon, crossed, value, on_change = item[:8]
            button.set(top, bottom, action, enabled, icon, crossed)
            row_y = y + 82 + i * (row_h + 8)
            button.place(x + 16, row_y, self.width - 32, row_h)
            if value is None:
                slider.hide()
            else:
                slider.place(x + self.width - 32 - self.SLIDER_W, row_y + row_h / 2.0, self.SLIDER_W, value, on_change)
        h = 98 + len(items) * (row_h + 8)
        self.panel.place(x, y, self.width, h)
        for edge, rect in zip(self.edges, ((x, y, self.width, 2), (x, y + h - 2, self.width, 2), (x, y, 2, h),
                                           (x + self.width - 2, y, 2, h))):
            edge.place(*rect)

    def hide(self):
        self.title.place(0, 0, None)
        self.note.place(0, 0, None)
        self.close.hide()
        for button, slider in zip(self.buttons, self.sliders):
            button.hide()
            slider.hide()
        for part in self.edges + [self.rule, self.panel]:
            part.hide()
        self.dragging = None

    def click(self, x, y):
        if self.close.contains(x, y):
            if self.on_close:
                self.on_close()
            return True
        for slider in self.sliders:
            if slider.grab(x, y):
                self.dragging = slider
                return True
        for button in self.buttons:
            if button.click(x, y):
                return True
        return self.panel.contains(x, y)

    def drag(self, x, y):
        if self.dragging is not None:
            self.dragging.drag(x)

    def release(self):
        self.dragging = None

    def hover(self, x, y):
        self.close.hover = self.close.contains(x, y)
        for button in self.buttons:
            button.hover = button.box.contains(x, y)
