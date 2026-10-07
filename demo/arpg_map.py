"""A level: a grid of CELL-sized rock and floor cells plus what stands on it, in the form the server sends clients.

Pure Python, so the client needs nothing beyond the engine; generators and light baking live server-side."""
import zlib

CELL = 2.0
ROCK, FLOOR = 0, 1
NEIGHBOURS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


class CellMap:
    """Cell (i, j) covers x0 + i * CELL .. + CELL along x and z0 + j * CELL .. + CELL along z; outside the grid is rock."""

    def __init__(self, origin, nx, nz, cells=None):
        self.x0, self.z0 = origin
        self.nx, self.nz = nx, nz
        self.cells = bytearray(cells) if cells is not None else bytearray(nx * nz)

    @classmethod
    def covering(cls, x0, z0, x1, z1):
        """An all-rock map whose grid covers the rect, with its origin on a multiple of CELL."""
        ox, oz = CELL * (x0 // CELL), CELL * (z0 // CELL)
        return cls((ox, oz), int(-(-(x1 - ox) // CELL)), int(-(-(z1 - oz) // CELL)))

    @property
    def extent(self):
        return self.x0, self.z0, self.x0 + self.nx * CELL, self.z0 + self.nz * CELL

    def get(self, i, j):
        if 0 <= i < self.nx and 0 <= j < self.nz:
            return self.cells[j * self.nx + i]
        return ROCK

    def set(self, i, j, value):
        self.cells[j * self.nx + i] = value

    def cell_of(self, x, z):
        return int((x - self.x0) // CELL), int((z - self.z0) // CELL)

    def cell_rect(self, i, j):
        x, z = self.x0 + i * CELL, self.z0 + j * CELL
        return x, z, x + CELL, z + CELL

    def fill(self, rect, value):
        """Sets every cell whose centre lies inside rect (x0, z0, x1, z1)."""
        x0, z0, x1, z1 = rect
        for j in range(max(0, int((z0 - self.z0) // CELL)), min(self.nz, int(-(-(z1 - self.z0) // CELL)))):
            for i in range(max(0, int((x0 - self.x0) // CELL)), min(self.nx, int(-(-(x1 - self.x0) // CELL)))):
                cx, cz = self.x0 + (i + 0.5) * CELL, self.z0 + (j + 0.5) * CELL
                if x0 <= cx <= x1 and z0 <= cz <= z1:
                    self.set(i, j, value)

    def floor_at(self, x, z):
        return self.get(*self.cell_of(x, z)) == FLOOR

    def is_wall(self, i, j):
        """Rock that touches floor: the only rock anyone can see or bump into."""
        return self.get(i, j) == ROCK and any(self.get(i + di, j + dj) == FLOOR for di, dj in NEIGHBOURS)

    def wall_cells(self):
        return [(i, j) for j in range(self.nz) for i in range(self.nx) if self.is_wall(i, j)]

    def wall_boxes(self):
        """The wall cells merged greedily into as few axis-aligned rects (x0, z0, x1, z1) as rows allow."""
        walls = {cell for cell in self.wall_cells()}
        boxes = []
        for j in range(self.nz):
            i = 0
            while i < self.nx:
                if (i, j) not in walls:
                    i += 1
                    continue
                w = 1
                while (i + w, j) in walls:
                    w += 1
                h = 1
                while all((i + k, j + h) in walls for k in range(w)):
                    h += 1
                for dj in range(h):
                    for k in range(w):
                        walls.discard((i + k, j + dj))
                x0, z0, _, _ = self.cell_rect(i, j)
                boxes.append((x0, z0, x0 + w * CELL, z0 + h * CELL))
                i += w
        return boxes

    def payload(self):
        return {"origin": (self.x0, self.z0), "size": (self.nx, self.nz), "cells": zlib.compress(bytes(self.cells))}

    @classmethod
    def from_payload(cls, p):
        return cls(tuple(p["origin"]), p["size"][0], p["size"][1], zlib.decompress(p["cells"]))


class Level:
    """A map and its contents: rooms (name, rect, wave), gates (boxes), props (kind, x, z, yaw), torches (x, z, yaw),
    the shrine, and a lightmap ({"rect", "png"}) baked for it."""

    def __init__(self, name, cells, rooms=(), gates=(), props=(), torches=(), shrine=None, lightmap=None):
        self.name, self.cells = name, cells
        self.rooms, self.gates = list(rooms), list(gates)
        self.props, self.torches = list(props), list(torches)
        self.shrine, self.lightmap = shrine, lightmap

    def payload(self):
        return {"name": self.name, "cells": self.cells.payload(), "rooms": self.rooms, "gates": self.gates,
                "props": self.props, "torches": self.torches, "shrine": self.shrine, "lightmap": self.lightmap}

    @classmethod
    def from_payload(cls, p):
        rooms = [dict(r, rect=tuple(r["rect"])) for r in p["rooms"]]
        return cls(p["name"], CellMap.from_payload(p["cells"]), rooms, [tuple(g) for g in p["gates"]],
                   [tuple(t) for t in p["props"]], [tuple(t) for t in p["torches"]],
                   tuple(p["shrine"]) if p["shrine"] else None, p["lightmap"])
