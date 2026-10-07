"""From a concrete graph to space: anchors placed by a constrained force layout, then regions grown around them.

Everything is in cell units on a grid sized from the graph's total area and the template's shape hint."""
import math

import numpy as np

# Rock kept between regions' cores, in cells, and the margin left around the whole act.
GAP, MARGIN = 6.0, 8


def radius(area):
    return math.sqrt(area / math.pi)


def place_anchors(graph, rng, aspect=1.5, steps=400):
    """Anchor positions (n x 2, cells): the main route laid out along x, branches pushed off it, then relaxed."""
    nodes, n = graph.nodes, len(graph.nodes)
    r = np.array([radius(node["area"]) for node in nodes])
    route = graph.route()
    pos = np.zeros((n, 2))
    x = 0.0
    for k in route:
        pos[k] = (x + r[k], rng.uniform(-1, 1) * r[k])
        x += 2 * r[k] + GAP
    for k in range(n):
        if k in route:
            continue
        parent = graph.neighbours(k)[0]
        side = rng.choice((-1.0, 1.0))
        pos[k] = pos[parent] + (rng.uniform(-0.5, 0.5) * r[parent], side * (r[parent] + r[k] + GAP))
    # Fold the route into the shape's aspect: the longer it is than wanted, the more it zigzags across.
    length = x
    width = math.sqrt(sum(math.pi * rr * rr for rr in r) * 2.5 / aspect)
    if length > width * aspect:
        bend = (length / (width * aspect)) - 1.0
        pos[:, 1] += np.sin(pos[:, 0] / max(1.0, length) * math.pi * (1 + 2 * bend)) * width * 0.35
    edges = [(a, b) for a, b, _ in graph.edges]
    for step in range(steps):
        force = np.zeros_like(pos)
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=2) + np.eye(n)
        want = r[:, None] + r[None, :] + GAP
        push = np.clip(want - dist, 0, None) / dist
        np.fill_diagonal(push, 0)
        force += (delta * push[:, :, None]).sum(axis=1) * 0.5
        for a, b in edges:
            d = pos[b] - pos[a]
            length_ab = np.linalg.norm(d) or 1.0
            pull = (length_ab - (r[a] + r[b] + GAP)) / length_ab * 0.1
            force[a] += d * pull
            force[b] -= d * pull
        # Keep the act squashed to its aspect: pull toward the long axis in proportion to the spread across it.
        spread = pos[:, 1] - pos[:, 1].mean()
        force[:, 1] -= spread * 0.002 * aspect
        pos += force * (1.0 - step / steps)
    return pos - pos.min(axis=0) + r.max() + MARGIN, r


def smooth_noise(shape, rng, scale, octaves=4):
    """Fractal value noise in [0, 1] with features about scale cells across."""
    ny, nx = shape
    out = np.zeros(shape)
    total = 0.0
    for o in range(octaves):
        cells = max(2, int(max(nx, ny) / scale * 2 ** o))
        grid = rng.random((cells + 2, cells + 2))
        ys = np.linspace(0, cells, ny)
        xs = np.linspace(0, cells, nx)
        y0, x0 = ys.astype(int), xs.astype(int)
        fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a = grid[y0][:, x0] * (1 - fx) + grid[y0][:, x0 + 1] * fx
        b = grid[y0 + 1][:, x0] * (1 - fx) + grid[y0 + 1][:, x0 + 1] * fx
        out += (a * (1 - fy) + b * fy) / 2 ** o
        total += 1 / 2 ** o
    return out / total


def grow_regions(pos, r, rng):
    """A region index per cell (-1 for rock nobody owns): a power diagram of the anchors with noisy borders."""
    nx = int(np.ceil(pos[:, 0].max() + r.max() + MARGIN))
    nz = int(np.ceil(pos[:, 1].max() + r.max() + MARGIN))
    zz, xx = np.mgrid[0:nz, 0:nx]
    warp = 6.0
    wx = xx + (smooth_noise((nz, nx), rng, 18) - 0.5) * 2 * warp
    wz = zz + (smooth_noise((nz, nx), rng, 18) - 0.5) * 2 * warp
    # Each cell's distance to an anchor, in units of that region's radius; the nearest region within reach owns it.
    d = np.stack([np.hypot(wx - px, wz - pz) / (rr * 1.6) for (px, pz), rr in zip(pos, r)])
    owner = d.argmin(axis=0)
    owner[d.min(axis=0) > 1.0] = -1
    return owner
