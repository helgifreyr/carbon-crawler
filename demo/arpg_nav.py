"""Paths around the dungeon's walls for computer-controlled mages: A* on a 0.5 m grid, then shortened by line of sight."""
import heapq
import math

import arpg_world as world

CELL = 0.5
CLEARANCE = world.PLAYER_RADIUS + 0.2


class Nav:
    def __init__(self):
        self.x0, self.z0, x1, z1 = world.BOUNDS
        self.nx, self.nz = int((x1 - self.x0) / CELL), int((z1 - self.z0) / CELL)
        # The grid leaves the gates out; cells a gate covers are looked up in self.gate_at while it is shut.
        shut = set(world.shut_gates)
        world.shut_gates.clear()
        self.open = [[not world.inside_box(*self.center(i, j), pad=CLEARANCE) for j in range(self.nz)]
                     for i in range(self.nx)]
        world.shut_gates.update(shut)
        self.gate_at = {}
        for k, (gx0, gz0, gx1, gz1) in enumerate(world.GATES):
            i0, j0 = self.cell(gx0 - CLEARANCE, gz0 - CLEARANCE)
            i1, j1 = self.cell(gx1 + CLEARANCE, gz1 + CLEARANCE)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    self.gate_at[(i, j)] = world.GATE_BASE + k

    def passable(self, i, j):
        return self.open[i][j] and self.gate_at.get((i, j)) not in world.shut_gates

    def center(self, i, j):
        return self.x0 + (i + 0.5) * CELL, self.z0 + (j + 0.5) * CELL

    def cell(self, x, z):
        return (min(self.nx - 1, max(0, int((x - self.x0) / CELL))), min(self.nz - 1, max(0, int((z - self.z0) / CELL))))

    def nearest_open(self, i, j):
        if self.passable(i, j):
            return i, j
        for r in range(1, 8):
            for di in range(-r, r + 1):
                for dj in (-r, r) if abs(di) != r else range(-r, r + 1):
                    a, b = i + di, j + dj
                    if 0 <= a < self.nx and 0 <= b < self.nz and self.passable(a, b):
                        return a, b
        return i, j

    def clear(self, ax, az, bx, bz):
        return not world.segment_hits_box(ax, az, bx, bz, CLEARANCE)

    def path(self, ax, az, bx, bz):
        """Waypoints from (ax, az) to (bx, bz) that keep clear of walls; just the goal when it's in plain sight."""
        if self.clear(ax, az, bx, bz):
            return [(bx, bz)]
        start, goal = self.nearest_open(*self.cell(ax, az)), self.nearest_open(*self.cell(bx, bz))
        came, cost = {start: None}, {start: 0.0}
        frontier = [(0.0, start)]
        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            ci, cj = current
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                a, b = ci + di, cj + dj
                if not (0 <= a < self.nx and 0 <= b < self.nz and self.passable(a, b)):
                    continue
                if di and dj and not (self.passable(ci + di, cj) and self.passable(ci, cj + dj)):
                    continue
                step = cost[current] + (1.414 if di and dj else 1.0)
                if step < cost.get((a, b), 1e9):
                    cost[(a, b)], came[(a, b)] = step, current
                    heapq.heappush(frontier, (step + math.hypot(goal[0] - a, goal[1] - b), (a, b)))
        if goal not in came:
            return [(bx, bz)]
        cells, node = [], goal
        while node is not None:
            cells.append(node)
            node = came[node]
        points = [self.center(i, j) for i, j in reversed(cells)] + [(bx, bz)]
        # Keep only the turns: from each point, jump to the furthest one still in sight.
        smooth, here = [], (ax, az)
        k = 0
        while k < len(points):
            far = k
            for m in range(len(points) - 1, k, -1):
                if self.clear(here[0], here[1], points[m][0], points[m][1]):
                    far = m
                    break
            smooth.append(points[far])
            here = points[far]
            k = far + 1
        return smooth
