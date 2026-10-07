"""Spectrogram sheet of every ARPG sound (first take) to demo/out/sfx_sheet.png, for checking sounds by eye."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sfx
from arpg_sounds import RECIPES

COLS, W, H = 4, 300, 150


def main():
    names = list(RECIPES)
    sheet = Image.new("RGB", (COLS * W, ((len(names) + COLS - 1) // COLS) * H), (12, 12, 16))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x = sfx.finish(RECIPES[name](np.random.default_rng([sum(map(ord, name)), 0]), 1.0))
        f, _, power = signal.spectrogram(x, sfx.RATE, nperseg=1024, noverlap=768)
        db = 10 * np.log10(power[f < 9000] + 1e-12)
        level = np.clip((db - (db.max() - 70)) / 70, 0, 1)[::-1]
        rgb = (np.stack([level ** 0.7, level ** 1.4, level ** 0.4], -1) * 255).astype(np.uint8)
        left, top = (i % COLS) * W, (i // COLS) * H
        sheet.paste(Image.fromarray(rgb).resize((W - 6, H - 26)), (left + 3, top + 22))
        draw.text((left + 6, top + 5), "%s  %.2fs  rms %.2f" % (name, len(x) / sfx.RATE, np.sqrt(np.mean(x ** 2))),
                  fill=(230, 230, 230))
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo", "out", "sfx_sheet.png")
    sheet.save(path)
    print("[sfx] saved %s" % path)


if __name__ == "__main__":
    main()
