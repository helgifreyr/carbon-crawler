"""Draws the ARPG HUD textures into res/arpg/ui: spell icons, the health/mana orb layers and the slot frame."""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "res", "arpg", "ui")
ICON, ORB, SS = 128, 256, 4


def grid(n):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    return (x + 0.5) / n * 2 - 1, (y + 0.5) / n * 2 - 1


def rgba(r, g, b, a):
    return Image.fromarray((np.clip(np.dstack([r, g, b, a]), 0, 1) * 255).astype(np.uint8), "RGBA")


def glow(layer, radius, strength=1.0):
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = np.asarray(blurred).astype(np.float32)
        a[..., 3] = np.clip(a[..., 3] * strength, 0, 255)
        blurred = Image.fromarray(a.astype(np.uint8), "RGBA")
    return blurred


def canvas():
    return Image.new("RGBA", (ICON * SS, ICON * SS), (0, 0, 0, 0))


def backdrop(inner, outer):
    x, y = grid(ICON)
    r = np.clip(np.hypot(x, y * 1.05 + 0.1) / 1.35, 0, 1)
    color = [inner[i] * (1 - r) + outer[i] * r for i in range(3)]
    return rgba(*color, np.ones_like(r))


def compose(base, symbol, glow_color, radius=6, strength=1.6):
    symbol = symbol.resize((ICON, ICON), Image.LANCZOS)
    halo = Image.new("RGBA", symbol.size, glow_color + (0,))
    halo.putalpha(symbol.getchannel("A"))
    out = base.copy()
    out.alpha_composite(glow(halo, radius, strength))
    out.alpha_composite(symbol)
    return vignette(out)


def vignette(img):
    x, y = grid(ICON)
    edge = np.clip((np.maximum(abs(x), abs(y)) - 0.72) / 0.28, 0, 1) ** 1.5
    a = np.asarray(img).astype(np.float32) / 255
    a[..., :3] *= (1 - 0.6 * edge)[..., None]
    return Image.fromarray((a * 255).astype(np.uint8), "RGBA")


def s(v):
    return v * ICON * SS


def fireball(d, cx, cy, r, tail_dx, tail_dy, colors):
    for k in range(18, 0, -1):
        t = k / 18
        px, py = cx + tail_dx * t, cy + tail_dy * t
        rr = r * (1 - 0.75 * t)
        c = colors[0] if t > 0.55 else colors[1]
        d.ellipse([s(px - rr), s(py - rr), s(px + rr), s(py + rr)], fill=c + (int(255 * (1 - t) ** 0.8),))
    for rr, c in ((r, colors[1]), (r * 0.72, colors[2]), (r * 0.42, (255, 255, 235))):
        d.ellipse([s(cx - rr), s(cy - rr), s(cx + rr), s(cy + rr)], fill=c + (255,))


def icon_bolt():
    img = canvas()
    fireball(ImageDraw.Draw(img), 0.6, 0.4, 0.17, -0.42, 0.42, [(200, 40, 10), (255, 120, 20), (255, 210, 80)])
    return compose(backdrop((0.35, 0.1, 0.03), (0.08, 0.02, 0.01)), img, (255, 120, 30))


def icon_nova():
    img = canvas()
    d = ImageDraw.Draw(img)
    for k in range(16):
        a = 2 * math.pi * k / 16
        r0, r1 = 0.12, 0.44 if k % 2 == 0 else 0.34
        d.line([s(0.5 + r0 * math.cos(a)), s(0.5 + r0 * math.sin(a)), s(0.5 + r1 * math.cos(a)), s(0.5 + r1 * math.sin(a))],
               fill=(255, 190, 90, 255), width=int(s(0.035)))
    d.ellipse([s(0.2), s(0.2), s(0.8), s(0.8)], outline=(255, 150, 50, 255), width=int(s(0.05)))
    d.ellipse([s(0.39), s(0.39), s(0.61), s(0.61)], fill=(255, 245, 210, 255))
    return compose(backdrop((0.38, 0.16, 0.04), (0.08, 0.03, 0.01)), img, (255, 140, 40))


def icon_blink():
    img = canvas()
    d = ImageDraw.Draw(img)
    for ghost, (x, alpha) in enumerate(((0.3, 70), (0.42, 130), (0.56, 255))):
        d.ellipse([s(x - 0.09), s(0.28), s(x + 0.09), s(0.46)], fill=(200, 160, 255, alpha))
        d.polygon([(s(x - 0.13), s(0.8)), (s(x), s(0.42)), (s(x + 0.13), s(0.8))], fill=(150, 100, 255, alpha))
    for k in range(40):
        t = k / 40
        a = t * 4 * math.pi
        r = 0.05 + 0.13 * t
        x, y = 0.74 + r * math.cos(a), 0.3 + r * math.sin(a) * 0.8
        d.ellipse([s(x - 0.012), s(y - 0.012), s(x + 0.012), s(y + 0.012)], fill=(235, 220, 255, 255))
    return compose(backdrop((0.2, 0.08, 0.35), (0.04, 0.02, 0.08)), img, (170, 110, 255))


def icon_chain():
    img = canvas()
    d = ImageDraw.Draw(img)
    main = [(0.62, 0.08), (0.42, 0.42), (0.58, 0.46), (0.34, 0.92)]
    branch = [(0.47, 0.44), (0.72, 0.62), (0.66, 0.78)]
    for path, w in ((main, 0.07), (branch, 0.04)):
        d.line([(s(x), s(y)) for x, y in path], fill=(150, 190, 255, 255), width=int(s(w)), joint="curve")
        d.line([(s(x), s(y)) for x, y in path], fill=(245, 250, 255, 255), width=int(s(w * 0.4)), joint="curve")
    return compose(backdrop((0.1, 0.14, 0.38), (0.02, 0.03, 0.09)), img, (120, 160, 255), radius=7, strength=2.0)


def icon_meteor():
    img = canvas()
    d = ImageDraw.Draw(img)
    fireball(d, 0.62, 0.62, 0.2, -0.45, -0.45, [(170, 40, 10), (255, 110, 20), (255, 190, 60)])
    d.ellipse([s(0.47), s(0.47), s(0.77), s(0.77)], fill=(70, 45, 35, 255))
    for cx, cy, r in ((0.58, 0.56, 0.05), (0.68, 0.67, 0.035), (0.55, 0.69, 0.03)):
        d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=(45, 28, 22, 255))
    d.arc([s(0.47), s(0.47), s(0.77), s(0.77)], 180, 300, fill=(255, 160, 60, 255), width=int(s(0.03)))
    return compose(backdrop((0.32, 0.12, 0.04), (0.07, 0.02, 0.01)), img, (255, 100, 20))


def icon_frost():
    img = canvas()
    d = ImageDraw.Draw(img)
    for k in range(6):
        a = math.pi / 2 + 2 * math.pi * k / 6
        ex, ey = 0.5 + 0.38 * math.cos(a), 0.5 - 0.38 * math.sin(a)
        d.line([s(0.5), s(0.5), s(ex), s(ey)], fill=(220, 240, 255, 255), width=int(s(0.045)))
        for t, size in ((0.55, 0.12), (0.78, 0.08)):
            bx, by = 0.5 + 0.38 * t * math.cos(a), 0.5 - 0.38 * t * math.sin(a)
            for side in (-1, 1):
                b = a + side * math.radians(45)
                d.line([s(bx), s(by), s(bx + size * math.cos(b)), s(by - size * math.sin(b))],
                       fill=(200, 230, 255, 255), width=int(s(0.03)))
    d.ellipse([s(0.44), s(0.44), s(0.56), s(0.56)], fill=(255, 255, 255, 255))
    return compose(backdrop((0.06, 0.2, 0.34), (0.01, 0.04, 0.08)), img, (120, 200, 255))


def slot_frame():
    n = ICON
    x, y = grid(n)
    edge = np.maximum(abs(x), abs(y))
    ring = np.clip(1 - abs(edge - 0.93) / 0.07, 0, 1)
    light = 0.65 + 0.35 * (-y * 0.7 - x * 0.3)
    return rgba(0.72 * light, 0.55 * light, 0.3 * light, ring)


def orb_layers():
    x, y = grid(ORB)
    r = np.hypot(x, y)
    inside = np.clip((0.86 - r) * ORB / 4, 0, 1)
    z = np.sqrt(np.clip(1 - (r / 0.86) ** 2, 0, 1))
    swirl = 0.5 + 0.5 * np.sin(6 * x + 4 * np.sin(5 * y) + 3 * r)
    shade = 0.35 + 0.65 * z ** 0.7 * (0.85 + 0.15 * swirl)
    fill = rgba(shade, shade, shade, inside)
    spec = np.exp(-(((x + 0.28) / 0.22) ** 2 + ((y + 0.38) / 0.14) ** 2)) * 0.75
    rim = np.clip((r - 0.62) / 0.24, 0, 1) ** 2 * 0.55
    glass = rgba(np.ones_like(r), np.ones_like(r), np.ones_like(r), np.clip(spec * inside, 0, 1))
    shadow = rgba(np.zeros_like(r), np.zeros_like(r), np.zeros_like(r), rim * inside)
    ring = np.clip(1 - abs(r - 0.92) / 0.075, 0, 1)
    light = 0.6 + 0.4 * (-y * 0.8 - x * 0.2) / max(1e-3, 1.0)
    frame = rgba(0.7 * light, 0.52 * light, 0.28 * light, ring)
    frame.alpha_composite(shadow)
    frame.alpha_composite(glass)
    return fill, frame


def icon_arcane():
    img = canvas()
    d = ImageDraw.Draw(img)
    for k in range(8):
        a = math.pi / 2 + 2 * math.pi * k / 8
        r = 0.4 if k % 2 == 0 else 0.2
        d.polygon([(s(0.5 + r * math.cos(a)), s(0.5 - r * math.sin(a))),
                   (s(0.5 + 0.07 * math.cos(a + 1.2)), s(0.5 - 0.07 * math.sin(a + 1.2))),
                   (s(0.5), s(0.5)), (s(0.5 + 0.07 * math.cos(a - 1.2)), s(0.5 - 0.07 * math.sin(a - 1.2)))],
                  fill=(230, 180, 255, 255))
    d.ellipse([s(0.42), s(0.42), s(0.58), s(0.58)], fill=(255, 245, 255, 255))
    return compose(backdrop((0.28, 0.08, 0.36), (0.06, 0.01, 0.08)), img, (200, 120, 255))


def drop(d, cx, cy, r, color, shine):
    d.polygon([(s(cx), s(cy - 2.0 * r)), (s(cx - r * 0.93), s(cy - 0.35 * r)), (s(cx + r * 0.93), s(cy - 0.35 * r))], fill=color)
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=color)
    d.ellipse([s(cx - r * 0.55), s(cy - r * 0.6), s(cx - r * 0.15), s(cy - r * 0.1)], fill=shine)


def icon_mana():
    img = canvas()
    drop(ImageDraw.Draw(img), 0.5, 0.6, 0.22, (70, 130, 255, 255), (200, 225, 255, 255))
    return compose(backdrop((0.06, 0.12, 0.34), (0.01, 0.02, 0.08)), img, (90, 140, 255))


def icon_heart():
    img = canvas()
    d = ImageDraw.Draw(img)
    for cx in (0.38, 0.62):
        d.ellipse([s(cx - 0.15), s(0.25), s(cx + 0.15), s(0.55)], fill=(220, 40, 50, 255))
    d.polygon([(s(0.235), s(0.45)), (s(0.765), s(0.45)), (s(0.5), s(0.8))], fill=(220, 40, 50, 255))
    d.ellipse([s(0.29), s(0.31), s(0.37), s(0.39)], fill=(255, 170, 170, 255))
    return compose(backdrop((0.34, 0.06, 0.06), (0.08, 0.01, 0.01)), img, (255, 60, 60))


BADGE = 64


def badge(draw_symbol):
    n = BADGE * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([n * 0.04, n * 0.04, n * 0.96, n * 0.96], fill=(25, 20, 14, 255), outline=(225, 175, 80, 255), width=int(n * 0.07))
    draw_symbol(d, lambda v: v * n)
    return img.resize((BADGE, BADGE), Image.LANCZOS)


GOLD_SYM = (255, 225, 140, 255)


def sym_plus(d, b):
    d.rectangle([b(0.42), b(0.24), b(0.58), b(0.76)], fill=GOLD_SYM)
    d.rectangle([b(0.24), b(0.42), b(0.76), b(0.58)], fill=GOLD_SYM)


def sym_power(d, b):
    d.polygon([(b(0.5), b(0.2)), (b(0.78), b(0.52)), (b(0.6), b(0.52)), (b(0.6), b(0.8)), (b(0.4), b(0.8)),
               (b(0.4), b(0.52)), (b(0.22), b(0.52))], fill=GOLD_SYM)


def sym_fork(d, b):
    w = int(b(0.08))
    d.line([b(0.5), b(0.8), b(0.5), b(0.5)], fill=GOLD_SYM, width=w)
    for x in (0.26, 0.5, 0.74):
        d.line([b(0.5), b(0.5), b(x), b(0.22)], fill=GOLD_SYM, width=w)


def sym_pierce(d, b):
    w = int(b(0.08))
    d.line([b(0.18), b(0.5), b(0.7), b(0.5)], fill=GOLD_SYM, width=w)
    d.polygon([(b(0.84), b(0.5)), (b(0.62), b(0.32)), (b(0.62), b(0.68))], fill=GOLD_SYM)
    d.rectangle([b(0.4), b(0.26), b(0.47), b(0.74)], outline=GOLD_SYM, width=int(b(0.04)))


def sym_expand(d, b):
    for (x, y), (dx, dy) in (((0.2, 0.2), (1, 1)), ((0.8, 0.2), (-1, 1)), ((0.2, 0.8), (1, -1)), ((0.8, 0.8), (-1, -1))):
        d.polygon([(b(x), b(y)), (b(x + dx * 0.24), b(y)), (b(x), b(y + dy * 0.24))], fill=GOLD_SYM)
        d.line([b(x), b(y), b(x + dx * 0.22), b(y + dy * 0.22)], fill=GOLD_SYM, width=int(b(0.07)))


def sym_frost(d, b):
    for k in range(3):
        a = math.pi * k / 3
        d.line([b(0.5 + 0.3 * math.cos(a)), b(0.5 + 0.3 * math.sin(a)), b(0.5 - 0.3 * math.cos(a)), b(0.5 - 0.3 * math.sin(a))],
               fill=(190, 230, 255, 255), width=int(b(0.08)))


def sym_flame(d, b):
    d.polygon([(b(0.5), b(0.16)), (b(0.72), b(0.52)), (b(0.66), b(0.78)), (b(0.34), b(0.78)), (b(0.28), b(0.52)),
               (b(0.42), b(0.36))], fill=(255, 140, 40, 255))
    d.polygon([(b(0.5), b(0.44)), (b(0.6), b(0.66)), (b(0.5), b(0.76)), (b(0.4), b(0.66))], fill=(255, 230, 120, 255))


def sym_cycle(d, b):
    w = int(b(0.08))
    d.arc([b(0.22), b(0.22), b(0.78), b(0.78)], 200, 340, fill=GOLD_SYM, width=w)
    d.arc([b(0.22), b(0.22), b(0.78), b(0.78)], 20, 160, fill=GOLD_SYM, width=w)
    d.polygon([(b(0.74), b(0.2)), (b(0.84), b(0.42)), (b(0.62), b(0.4))], fill=GOLD_SYM)
    d.polygon([(b(0.26), b(0.8)), (b(0.16), b(0.58)), (b(0.38), b(0.6))], fill=GOLD_SYM)


def sym_play(d, b):
    d.polygon([(b(0.38), b(0.26)), (b(0.76), b(0.5)), (b(0.38), b(0.74))], fill=GOLD_SYM)


def sym_move(d, b):
    w = int(b(0.07))
    d.line([b(0.5), b(0.22), b(0.5), b(0.78)], fill=GOLD_SYM, width=w)
    d.line([b(0.22), b(0.5), b(0.78), b(0.5)], fill=GOLD_SYM, width=w)
    for tip, l, r in (((0.5, 0.16), (0.4, 0.3), (0.6, 0.3)), ((0.5, 0.84), (0.4, 0.7), (0.6, 0.7)),
                      ((0.16, 0.5), (0.3, 0.4), (0.3, 0.6)), ((0.84, 0.5), (0.7, 0.4), (0.7, 0.6))):
        d.polygon([(b(tip[0]), b(tip[1])), (b(l[0]), b(l[1])), (b(r[0]), b(r[1]))], fill=GOLD_SYM)


def sym_note(d, b):
    d.ellipse([b(0.26), b(0.6), b(0.46), b(0.76)], fill=GOLD_SYM)
    d.ellipse([b(0.54), b(0.52), b(0.74), b(0.68)], fill=GOLD_SYM)
    d.rectangle([b(0.41), b(0.26), b(0.46), b(0.69)], fill=GOLD_SYM)
    d.rectangle([b(0.69), b(0.2), b(0.74), b(0.61)], fill=GOLD_SYM)
    d.polygon([(b(0.41), b(0.26)), (b(0.74), b(0.18)), (b(0.74), b(0.3)), (b(0.41), b(0.38))], fill=GOLD_SYM)


def sym_speaker(d, b):
    d.polygon([(b(0.22), b(0.4)), (b(0.36), b(0.4)), (b(0.52), b(0.24)), (b(0.52), b(0.76)), (b(0.36), b(0.6)),
               (b(0.22), b(0.6))], fill=GOLD_SYM)
    for r in (0.14, 0.26):
        d.arc([b(0.5 - r), b(0.5 - r), b(0.5 + r + 0.08), b(0.5 + r)], -45, 45, fill=GOLD_SYM, width=int(b(0.05)))


def sym_quit(d, b):
    d.arc([b(0.24), b(0.26), b(0.76), b(0.78)], -60, 240, fill=(255, 150, 120, 255), width=int(b(0.07)))
    d.line([b(0.5), b(0.18), b(0.5), b(0.5)], fill=(255, 150, 120, 255), width=int(b(0.07)))


def sym_flag(d, b):
    d.rectangle([b(0.3), b(0.18), b(0.35), b(0.82)], fill=GOLD_SYM)
    d.polygon([(b(0.35), b(0.2)), (b(0.76), b(0.33)), (b(0.35), b(0.48))], fill=(255, 120, 70, 255))


def menu_off():
    n = BADGE * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([n * 0.2, n * 0.8, n * 0.8, n * 0.2], fill=(20, 10, 8, 255), width=int(n * 0.14))
    d.line([n * 0.2, n * 0.8, n * 0.8, n * 0.2], fill=(230, 60, 50, 255), width=int(n * 0.08))
    return img.resize((BADGE, BADGE), Image.LANCZOS)


MENU = {"resume": sym_play, "controls": sym_move, "music": sym_note, "sounds": sym_speaker, "quit": sym_quit,
        "ready": sym_flag, "upgrades": sym_plus}
BADGES = {"plus": sym_plus, "power": sym_power, "fork": sym_fork, "pierce": sym_pierce, "expand": sym_expand,
          "frost": sym_frost, "flame": sym_flame, "cycle": sym_cycle}
ICONS = {"bolt": icon_bolt, "nova": icon_nova, "blink": icon_blink, "chain": icon_chain, "meteor": icon_meteor,
         "frost": icon_frost, "arcane": icon_arcane, "mana": icon_mana, "heart": icon_heart}


def write_cur(img, hotspot, path):
    """A Windows .cur: one 32-bit image with alpha (rows bottom-up) and an all-clear AND mask."""
    import struct
    w, h = img.size
    pixels = np.asarray(img.convert("RGBA"))[::-1, :, [2, 1, 0, 3]].tobytes()
    mask = bytes(((w + 31) // 32) * 4 * h)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0) + pixels + mask
    head = struct.pack("<HHH", 0, 2, 1) + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hotspot[0], hotspot[1],
                                                      len(dib), 22)
    with open(path, "wb") as f:
        f.write(head + dib)


def make_cursor():
    """The Blender render (tools/blender/render_cursor.py) cut down to cursor size, with a dark edge and its hotspot."""
    src = os.path.join(OUT, "cursor_render.png")
    if not os.path.exists(src):
        print("no cursor_render.png - run tools/blender/render_cursor.py in Blender first")
        return
    import json
    meta = json.load(open(src.replace(".png", ".json")))
    img = Image.open(src).convert("RGBA")
    tip = (meta["hotspot"][0] * img.width, meta["hotspot"][1] * img.height)
    x0, y0, x1, y1 = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    side = max(x1 - x0, y1 - y0) + 24
    left, top = min(x0, int(tip[0]) - 6) - 6, min(y0, int(tip[1]) - 6) - 6
    img = img.crop((left, top, left + side, top + side))
    tip = (tip[0] - left, tip[1] - top)
    for size, name in ((64, "cursor.png"), (48, None)):
        small = img.resize((size, size), Image.LANCZOS)
        alpha = small.getchannel("A")
        edge = alpha.filter(ImageFilter.MaxFilter(3))
        out = Image.new("RGBA", small.size, (10, 6, 16, 0))
        out.putalpha(edge.point(lambda a: int(a * 0.85)))
        out.alpha_composite(small)
        hot = (int(round(tip[0] * size / side)), int(round(tip[1] * size / side)))
        if name:
            out.save(os.path.join(OUT, name))
            with open(os.path.join(OUT, "cursor.json"), "w") as f:
                json.dump({"hotspot": hot, "size": size}, f)
        else:
            write_cur(out, hot, os.path.join(OUT, "cursor.cur"))
    print("cursor: hotspot", hot, "of 48")


def make_app_icon():
    """The window and exe icon: the firebolt in a rounded gold-rimmed tile, at every size Windows asks for."""
    n = 256
    art = icon_bolt().resize((n, n), Image.LANCZOS)
    big = n * SS
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.2), fill=255)
    mask = mask.resize((n, n), Image.LANCZOS)
    rim = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle([big * 0.02, big * 0.02, big * 0.98, big * 0.98], radius=int(big * 0.19),
                                          outline=(230, 180, 90, 255), width=int(big * 0.035))
    tile = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    tile.paste(art, (0, 0), mask)
    tile.alpha_composite(rim.resize((n, n), Image.LANCZOS))
    tile.save(os.path.join(OUT, "app.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    tile.save(os.path.join(OUT, "app.png"))


def main():
    make_cursor()
    make_app_icon()
    os.makedirs(OUT, exist_ok=True)
    for name, make in ICONS.items():
        make().save(os.path.join(OUT, "icon_%s.png" % name))
    for name, symbol in BADGES.items():
        badge(symbol).save(os.path.join(OUT, "badge_%s.png" % name))
    for name, symbol in MENU.items():
        badge(symbol).save(os.path.join(OUT, "menu_%s.png" % name))
    menu_off().save(os.path.join(OUT, "menu_off.png"))
    slot_frame().save(os.path.join(OUT, "slot_frame.png"))
    fill, frame = orb_layers()
    fill.save(os.path.join(OUT, "orb_fill.png"))
    frame.save(os.path.join(OUT, "orb_frame.png"))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(OUT)), "..", "demo"))
    from arpg_world import UPGRADES
    sheet = Image.new("RGBA", (ICON * len(UPGRADES), ICON * 2 + BADGE + 8), (30, 30, 34, 255))
    for i, name in enumerate(list(MENU) + ["off"]):
        sheet.alpha_composite(Image.open(os.path.join(OUT, "menu_%s.png" % name)), (i * (BADGE + 8) + 4, ICON * 2 + 4))
    for i, name in enumerate(ICONS):
        sheet.alpha_composite(Image.open(os.path.join(OUT, "icon_%s.png" % name)), (i * ICON, 0))
    for i, up in enumerate(UPGRADES.values()):
        sheet.alpha_composite(Image.open(os.path.join(OUT, "icon_%s.png" % up["icon"])), (i * ICON, ICON))
        mark = Image.open(os.path.join(OUT, "badge_%s.png" % up["badge"])).resize((56, 56), Image.LANCZOS)
        sheet.alpha_composite(mark, (i * ICON + ICON - 60, ICON * 2 - 60))
    out = os.path.join(os.path.dirname(os.path.dirname(OUT)), "..", "demo", "out")
    os.makedirs(out, exist_ok=True)
    sheet.save(os.path.join(out, "ui_sheet.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
