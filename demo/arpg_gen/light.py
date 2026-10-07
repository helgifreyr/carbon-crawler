"""The lightmap for a level: top-down torch light with hard 2D shadows from the walls, blurred, as PNG bytes."""
import struct
import zlib

import numpy as np

from arpg_layout import LIGHTMAP_PX_PER_M

TORCH_REACH_M, TORCH_COLOR = 9.0, (1.0, 0.6, 0.28)


def bake(level):
    x0, z0, x1, z1 = level.cells.extent
    walls = level.cells.wall_boxes()
    w, h = int((x1 - x0) * LIGHTMAP_PX_PER_M), int((z1 - z0) * LIGHTMAP_PX_PER_M)
    xs = x0 + (np.arange(w) + 0.5) / LIGHTMAP_PX_PER_M
    zs = z0 + (np.arange(h) + 0.5) / LIGHTMAP_PX_PER_M
    light = np.zeros((h, w))
    reach = TORCH_REACH_M
    with np.errstate(divide="ignore", invalid="ignore"):
        for tx, tz, _ in level.torches:
            i0, i1 = np.searchsorted(xs, tx - reach), np.searchsorted(xs, tx + reach)
            j0, j1 = np.searchsorted(zs, tz - reach), np.searchsorted(zs, tz + reach)
            gx, gz = np.meshgrid(xs[i0:i1], zs[j0:j1])
            dx, dz = tx - gx, tz - gz
            falloff = np.clip(1.0 - np.hypot(dx, dz) / reach, 0.0, 1.0) ** 1.8
            lit = np.ones_like(falloff, dtype=bool)
            for bx0, bz0, bx1, bz1 in walls:
                if bx1 < tx - reach or bx0 > tx + reach or bz1 < tz - reach or bz0 > tz + reach:
                    continue
                ax, bx = (bx0 - gx) / dx, (bx1 - gx) / dx
                az, bz = (bz0 - gz) / dz, (bz1 - gz) / dz
                tmin = np.maximum(np.minimum(ax, bx), np.minimum(az, bz))
                tmax = np.minimum(np.maximum(ax, bx), np.maximum(az, bz))
                lit &= ~((tmax >= tmin) & (tmax > 0.0) & (tmin < 1.0))
            light[j0:j1, i0:i1] += falloff * lit
    for _ in range(3):
        padded = np.pad(light, 1, mode="edge")
        light = sum(padded[1 + a:h + 1 + a, 1 + b:w + 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1)) / 9.0
    rgb = np.clip(light, 0.0, 1.0)[..., None] * np.array(TORCH_COLOR)[None, None, :]
    return {"rect": (x0, z0, x1, z1), "png": png_bytes((rgb * 255 + 0.5).astype(np.uint8))}


def png_bytes(rgb):
    """An 8-bit RGB PNG; row 0 of the array is the image's top row."""
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
