"""Karst dissolution: Darcy flow between heads the graph sets (recharge at the start, a spring at the boss) dissolves
layered, fractured limestone where it flows; porosity raises permeability, so flow focuses into cave channels."""
import math

import numpy as np

from arpg_gen.layout import smooth_noise


def rock(owner, rng):
    """Solubility and fracture fields: bedding planes and two joint sets, softer inside the graph's regions."""
    nz, nx = owner.shape
    zz, xx = np.mgrid[0:nz, 0:nx].astype(float)
    inside = (owner >= 0).astype(float)
    for _ in range(4):
        inside = (inside + np.roll(inside, 1, 0) + np.roll(inside, -1, 0) + np.roll(inside, 1, 1) + np.roll(inside, -1, 1)) / 5
    dip = rng.uniform(-0.4, 0.4)
    bedding = np.sin((zz * math.cos(dip) + xx * math.sin(dip)) / rng.uniform(3.0, 5.0) + smooth_noise((nz, nx), rng, 25) * 6)
    solubility = (0.25 + 0.75 * inside) * (0.75 + 0.25 * bedding) * (0.7 + 0.6 * smooth_noise((nz, nx), rng, 8))
    fractures = np.zeros((nz, nx))
    for angle in (rng.uniform(0, math.pi), rng.uniform(0, math.pi)):
        spacing = rng.uniform(7, 12)
        phase = (xx * math.cos(angle) + zz * math.sin(angle)) / spacing + smooth_noise((nz, nx), rng, 30) * 2
        fractures += np.exp(-((phase - np.round(phase)) * spacing / 1.6) ** 2) * (smooth_noise((nz, nx), rng, 12) > 0.45)
    return solubility, np.clip(fractures, 0, 1)


def heads(graph, pos, r, shape):
    """Fixed-head cells (mask, value): a disk at each anchor, head falling along the route from 1 to 0."""
    nz, nx = shape
    zz, xx = np.mgrid[0:nz, 0:nx]
    fixed = np.zeros(shape, bool)
    value = np.zeros(shape)
    for k, node in enumerate(graph.nodes):
        disk = np.hypot(xx - pos[k, 0], zz - pos[k, 1]) <= max(2.0, r[k] * 0.25)
        h = 1.0 - node["depth"]
        if node["type"] == "vault":
            h = min(1.0, h + 0.2)
        fixed |= disk
        value[disk] = h
    return fixed, value


def solve_head(K, fixed, value, h, sweeps):
    """Red-black over-relaxed Gauss-Seidel on div(K grad h) = 0, with no flow through the grid's edges."""
    Kp = np.pad(K, 1, mode="edge")
    c = Kp[1:-1, 1:-1]
    faces = [2 * c * n / (c + n + 1e-12) for n in (Kp[:-2, 1:-1], Kp[2:, 1:-1], Kp[1:-1, :-2], Kp[1:-1, 2:])]
    faces[0][0, :] = 0
    faces[1][-1, :] = 0
    faces[2][:, 0] = 0
    faces[3][:, -1] = 0
    total = faces[0] + faces[1] + faces[2] + faces[3] + 1e-12
    nz, nx = K.shape
    checker = (np.add.outer(np.arange(nz), np.arange(nx)) % 2).astype(bool)
    free_red, free_black = ~fixed & checker, ~fixed & ~checker
    h = np.where(fixed, value, h)
    for _ in range(sweeps):
        for free in (free_red, free_black):
            hp = np.pad(h, 1, mode="edge")
            new = (faces[0] * hp[:-2, 1:-1] + faces[1] * hp[2:, 1:-1] + faces[2] * hp[1:-1, :-2]
                   + faces[3] * hp[1:-1, 2:]) / total
            h[free] = new[free] * 1.8 - h[free] * 0.8
    return h


def flux(K, h):
    gz, gx = np.gradient(h)
    return K * np.hypot(gx, gz)


def simulate(graph, pos, r, owner, rng, steps=40, sweeps=60, feedback=7.0, rate=0.06):
    """Runs the dissolution; returns the fields (porosity, flux, head, solubility, fractures) as a dict."""
    solubility, fractures = rock(owner, rng)
    fixed, value = heads(graph, pos, r, owner.shape)
    porosity = np.zeros(owner.shape)
    h = np.full(owner.shape, 0.5)
    q = np.zeros(owner.shape)
    for step in range(steps):
        K = (0.05 + fractures) * solubility * np.exp(feedback * porosity)
        h = solve_head(K, fixed, value, h, sweeps if step else sweeps * 4)
        q = flux(K, h)
        q /= np.percentile(q, 99) + 1e-12
        porosity = np.clip(porosity + rate * solubility * np.clip(q, 0, 3) * (1 - porosity), 0, 1)
    return {"porosity": porosity, "flux": q, "head": h, "solubility": solubility, "fractures": fractures}
