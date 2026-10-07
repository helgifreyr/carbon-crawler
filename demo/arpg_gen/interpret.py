"""From simulated fields to cells: each region keeps its most dissolved cells up to its size, wide channels between
regions stay open, specks are cleaned up, and missing links are carved along the cheapest dissolved path."""
import heapq

import numpy as np

from arpg_map import FLOOR, ROCK


def blur(a, passes=2):
    for _ in range(passes):
        p = np.pad(a, 1, mode="edge")
        a = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + 2 * p[1:-1, 1:-1]) / 6
    return a


def neighbours_floor(floor):
    p = np.pad(floor.astype(int), 1)
    return sum(p[1 + dz:p.shape[0] - 1 + dz, 1 + dx:p.shape[1] - 1 + dx]
               for dz in (-1, 0, 1) for dx in (-1, 0, 1) if dz or dx)


def carve_cells(graph, pos, r, owner, fields, chamber=0.3, channel_quantile=0.965):
    """The floor mask, and the per-cell score the repair pass digs along."""
    nz, nx = owner.shape
    zz, xx = np.mgrid[0:nz, 0:nx]
    dissolved = blur(fields["porosity"], 2)
    dissolved /= dissolved.max() + 1e-12
    floor = np.zeros(owner.shape, bool)
    score = dissolved.copy()
    for k, node in enumerate(graph.nodes):
        mine = owner == k
        near = np.clip(1.0 - np.hypot(xx - pos[k, 0], zz - pos[k, 1]) / r[k], 0, 1)
        s = dissolved + chamber * near
        score[mine] = s[mine]
        values = s[mine]
        if values.size:
            keep = np.sort(values)[-min(values.size, node["area"])]
            floor |= mine & (s >= keep)
    floor |= dissolved >= np.quantile(dissolved, channel_quantile)
    for _ in range(2):
        n = neighbours_floor(floor)
        floor = (floor & (n >= 2)) | (~floor & (n >= 6))
    return floor, score


def components(floor):
    """Connected floor components (4-neighbour) as a label grid, 0 for rock."""
    nz, nx = floor.shape
    label = np.zeros(floor.shape, int)
    count = 0
    for z0, x0 in zip(*np.nonzero(floor)):
        if label[z0, x0]:
            continue
        count += 1
        label[z0, x0] = count
        stack = [(z0, x0)]
        while stack:
            z, x = stack.pop()
            for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = z + dz, x + dx
                if 0 <= a < nz and 0 <= b < nx and floor[a, b] and not label[a, b]:
                    label[a, b] = count
                    stack.append((a, b))
    return label


def anchor_cell(floor, pos, k):
    """The floor cell nearest an anchor."""
    zs, xs = np.nonzero(floor)
    i = np.argmin((xs - pos[k, 0]) ** 2 + (zs - pos[k, 1]) ** 2)
    return zs[i], xs[i]


def dig(floor, score, start, goal):
    """Opens the cheapest path from start to goal, three cells wide, cost falling with how dissolved the rock is."""
    nz, nx = floor.shape
    cost = np.where(floor, 0.2, 1.0 / (0.05 + score))
    dist = {start: 0.0}
    came = {}
    frontier = [(0.0, start)]
    while frontier:
        d, cell = heapq.heappop(frontier)
        if cell == goal:
            break
        if d > dist.get(cell, 1e18):
            continue
        z, x = cell
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = z + dz, x + dx
            if 1 <= a < nz - 1 and 1 <= b < nx - 1:
                nd = d + cost[a, b]
                if nd < dist.get((a, b), 1e18):
                    dist[(a, b)], came[(a, b)] = nd, cell
                    heapq.heappush(frontier, (nd, (a, b)))
    cell = goal
    while cell in came:
        z, x = cell
        floor[z - 1:z + 2, x - 1:x + 2] = True
        cell = came[cell]


def repair(graph, pos, floor, score):
    """Makes sure every link of the graph is walkable, digging along the score where it isn't; returns digs made."""
    digs = 0
    for a, b, _ in graph.edges:
        label = components(floor)
        ca, cb = anchor_cell(floor, pos, a), anchor_cell(floor, pos, b)
        if label[ca] != label[cb]:
            dig(floor, score, ca, cb)
            digs += 1
    label = components(floor)
    keep = label[anchor_cell(floor, pos, 0)]
    floor &= label == keep
    return digs


def to_cells(floor):
    """The floor mask as a flat FLOOR/ROCK bytearray in CellMap order (row j is z, column i is x)."""
    return bytearray(np.where(floor, FLOOR, ROCK).astype(np.uint8).tobytes())
