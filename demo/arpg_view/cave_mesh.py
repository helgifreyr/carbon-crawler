"""Cave walls by dual-grid marching squares: each cell corner picks a rock shape from its four cells, and the shapes
are roughened by one world-space noise so neighbouring pieces stay joined. Pure Python, built at load time."""
import math

from arpg_layout import FLOOR_Y, WALL_BASE_Y, WALL_H
from arpg_map import CELL, FLOOR

TOP = WALL_BASE_Y + WALL_H
BOTTOM = FLOOR_Y - 0.15
ROWS, CONTOUR_STEP, BORDER_STEP = 5, 0.5, 1.0
ROUGH_M, LUMP_M, CEILING_M = 0.32, 1.6, 0.35

# Tile points in half-cell units around the corner vertex: corners, edge midpoints.
A, B, C, D = (-1, -1), (1, -1), (-1, 1), (1, 1)
T, BM, L, R = (0, -1), (0, 1), (-1, 0), (1, 0)
# Case bits: rock in the -x-z, +x-z, -x+z and +x+z cells is 1, 2, 4 and 8. Each case is a list of (rock polygon,
# wall edge): the polygon caps the rock at wall height, the edge is where the wall face stands.
CASES = {
    1: [([A, T, L], (L, T))], 2: [([T, B, R], (T, R))], 4: [([L, BM, C], (L, BM))], 8: [([R, D, BM], (R, BM))],
    3: [([A, B, R, L], (L, R))], 12: [([L, R, D, C], (L, R))], 5: [([A, T, BM, C], (T, BM))],
    10: [([T, B, D, BM], (T, BM))],
    9: [([A, T, L], (L, T)), ([R, D, BM], (R, BM))], 6: [([T, B, R], (T, R)), ([L, BM, C], (L, BM))],
    7: [([A, B, R, BM, C], (R, BM))], 11: [([A, B, D, BM, L], (L, BM))], 13: [([A, T, R, D, C], (T, R))],
    14: [([T, B, D, C, L], (L, T))],
    15: [([A, T, B, R, D, BM, C, L], None)],
}


def _hash(i, j, k):
    h = (i * 73856093) ^ (j * 19349663) ^ (k * 83492791)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h & 0xFFFF) / 32767.5 - 1.0


def _value_noise(x, y, z, seed):
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - xi, y - yi, z - zi
    fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    total = 0.0
    for dx, wx in ((0, 1 - fx), (1, fx)):
        for dy, wy in ((0, 1 - fy), (1, fy)):
            for dz, wz in ((0, 1 - fz), (1, fz)):
                total += wx * wy * wz * _hash(xi + dx + seed, yi + dy, zi + dz)
    return total


class Rough:
    """A displacement for every world point, the same for every piece that shares the point."""

    def __init__(self):
        self.cache = {}

    def __call__(self, p):
        key = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        hit = self.cache.get(key)
        if hit is None:
            x, y, z = p
            s = 1.0 / LUMP_M
            dx = _value_noise(x * s, y * s, z * s, 11) * ROUGH_M
            dz = _value_noise(x * s, y * s, z * s, 37) * ROUGH_M
            dy = _value_noise(x * 0.5, 0.0, z * 0.5, 71) * CEILING_M if y >= TOP - 1e-6 else 0.0
            hit = self.cache[key] = (x + dx, y + dy, z + dz)
        return hit


def _densify(p, q, step):
    n = max(1, math.ceil(math.dist(p, q) / step - 1e-6))
    return [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n)]


class CaveBuilder:
    """Adds cave rock to MeshBuilders; front is +1 if a triangle's (b - a) x (c - a) is its front face's normal."""

    def __init__(self, cells, front, uv):
        self.cells, self.front, self.uv = cells, front, uv
        self.rough = Rough()

    def triangle(self, mesh, a, b, c, facing):
        pa, pb, pc = self.rough(a), self.rough(b), self.rough(c)
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if (n[0] * facing[0] + n[1] * facing[1] + n[2] * facing[2]) * self.front < 0:
            pb, pc = pc, pb
            n = (-n[0], -n[1], -n[2])
        length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
        normal = (n[0] * self.front / length, n[1] * self.front / length, n[2] * self.front / length)
        for p in (pa, pb, pc):
            mesh.positions.append(p)
            mesh.normals.append(normal)
            mesh.uvs.append(self.uv(p, normal))

    def corner(self, mesh, tops, i, j):
        """The rock where cells (i-1..i, j-1..j) meet: caps on top (into tops) and wall faces toward the floor."""
        cells = self.cells
        rock = [cells.get(i - 1, j - 1) != FLOOR, cells.get(i, j - 1) != FLOOR,
                cells.get(i - 1, j) != FLOOR, cells.get(i, j) != FLOOR]
        case = rock[0] | rock[1] << 1 | rock[2] << 2 | rock[3] << 3
        if case == 0:
            return
        if case == 15 and not any(cells.is_wall(i + di, j + dj) for di in (-1, 0) for dj in (-1, 0)):
            return
        half = CELL / 2
        cx, cz = cells.x0 + i * CELL, cells.z0 + j * CELL

        def world(p, y):
            return cx + p[0] * half, y, cz + p[1] * half

        for poly, wall in CASES[case]:
            boundary = []
            for k, p in enumerate(poly):
                q = poly[(k + 1) % len(poly)]
                on_wall = wall is not None and {p, q} == set(wall)
                boundary += _densify(p, q, (CONTOUR_STEP if on_wall else BORDER_STEP) / half)
            centre = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
            for k, p in enumerate(boundary):
                q = boundary[(k + 1) % len(boundary)]
                self.triangle(tops, world(centre, TOP), world(p, TOP), world(q, TOP), (0.0, 1.0, 0.0))
            if wall is None:
                continue
            a, b = wall
            # The face looks away from the rock: perpendicular to the edge, on the side away from the polygon's centre.
            ex, ez = b[0] - a[0], b[1] - a[1]
            nx, nz = ez, -ex
            if nx * (centre[0] - a[0]) + nz * (centre[1] - a[1]) > 0:
                nx, nz = -nx, -nz
            facing = (nx, 0.0, nz)
            columns = _densify(a, b, CONTOUR_STEP / half) + [b]
            heights = [BOTTOM + (TOP - BOTTOM) * r / ROWS for r in range(ROWS + 1)]
            for c0, c1 in zip(columns, columns[1:]):
                for y0, y1 in zip(heights, heights[1:]):
                    self.triangle(mesh, world(c0, y0), world(c1, y0), world(c1, y1), facing)
                    self.triangle(mesh, world(c0, y0), world(c1, y1), world(c0, y1), facing)
