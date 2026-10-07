"""Images for the act editor, drawn with numpy: the macro graph, and a generated act in one of its layers."""
import numpy as np

TYPE_COLORS = {"start": (80, 200, 90), "path": (140, 140, 185), "checkpoint": (235, 200, 60), "vault": (205, 120, 225),
               "arena": (235, 140, 45), "boss": (225, 60, 50)}
TYPES = list(TYPE_COLORS)
LAYERS = ["cells", "regions", "porosity", "flux", "head", "rock"]
BACKGROUND = (14, 16, 24)


def blank(w, h, color=BACKGROUND):
    img = np.empty((h, w, 3), np.uint8)
    img[:] = color
    return img


def disc(img, x, y, r, color):
    h, w, _ = img.shape
    y0, y1, x0, x1 = max(0, int(y - r)), min(h, int(y + r) + 1), max(0, int(x - r)), min(w, int(x + r) + 1)
    if y0 >= y1 or x0 >= x1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    inside = (xx - x) ** 2 + (yy - y) ** 2 <= r * r
    img[y0:y1, x0:x1][inside] = color


def line(img, a, b, color, width=2.0, dashed=False):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    for k in range(n):
        if dashed and (k // 6) % 2:
            continue
        t = k / max(1, n - 1)
        disc(img, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, width / 2, color)


def graph_image(w, h, nodes, edges, positions, selected=None, connecting=False):
    """The template's graph: edges (dashed for branches), nodes as discs sized by their area, the selection ringed."""
    img = blank(w, h, (18, 20, 30))
    for a, b, kind in edges:
        if a in positions and b in positions:
            line(img, positions[a], positions[b], (120, 125, 150) if kind == "branch" else (210, 215, 235), 3,
                 dashed=kind == "branch")
    for node in nodes:
        x, y = positions[node["id"]]
        r = 10 + (sum(node["size"]) / 2) ** 0.5 * 0.6
        if node["id"] == selected:
            disc(img, x, y, r + 5, (255, 120, 255) if connecting else (255, 255, 255))
        disc(img, x, y, r, TYPE_COLORS.get(node["type"], (200, 200, 200)))
    return img


def act_image(debug, payload, layer, scale=3):
    """A generated act drawn in one layer, with its shrines, packs, gates, boss and exit on top; scale px per cell."""
    floor, owner = debug["floor"], debug["owner"]
    fields = debug["fields"]
    nz, nx = floor.shape
    if layer == "cells":
        img = np.where(floor[..., None], np.array((150, 140, 122), np.uint8), np.array((30, 28, 30), np.uint8))
    elif layer == "regions":
        img = np.full((nz, nx, 3), 30, np.uint8)
        for k, node in enumerate(debug["nodes"]):
            color = np.array(TYPE_COLORS.get(node["type"], (200, 200, 200)), np.uint8)
            img[owner == k] = (color * 0.45).astype(np.uint8)
            img[(owner == k) & floor] = color
    else:
        if layer == "flux":
            value = np.log10(fields["flux"] + 1e-3)
        elif layer == "rock":
            value = fields["solubility"] + fields["fractures"]
        else:
            value = fields[layer]
        value = (value - value.min()) / (value.max() - value.min() + 1e-12)
        heat = np.stack([np.clip(value * 2.2, 0, 1), np.clip(value * 1.6 - 0.3, 0, 1), np.clip(value * 0.8, 0, 1)], -1)
        img = (heat * 255).astype(np.uint8)
        img[~floor] = (img[~floor] * 0.45).astype(np.uint8)
    img = np.repeat(np.repeat(img, scale, axis=0), scale, axis=1).copy()
    feats = payload["features"]

    def mark(point, r, color):
        disc(img, point[0] / 2.0 * scale, point[1] / 2.0 * scale, r, color)

    for x0, z0, x1, z1 in payload["gates"]:
        mark(((x0 + x1) / 2, (z0 + z1) / 2), scale * 0.7, (90, 220, 255))
    for pack in feats["packs"]:
        mark(pack["at"], scale * (1.2 + 0.25 * len(pack["kinds"])) * 0.5, (255, 215, 90) if pack.get("reward") else (230, 70, 60))
    for point in feats["checkpoints"]:
        mark(point, scale * 1.4, (255, 205, 90))
    mark(feats["boss"], scale * 2.2, (255, 40, 40))
    mark(feats["exit"], scale * 1.6, (120, 205, 255))
    return img
