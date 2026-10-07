"""Act templates: a designer's macro graph with variation, and its instantiation into one concrete graph per run.

A template node has an id, a type (start, path, checkpoint, vault, arena, boss), a size range in floor cells, and
optionally a chance to exist and a repeat range; a repeated node becomes a chain. Edges join node ids."""
import json
import os

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "res", "arpg", "acts")


def load(name):
    with open(os.path.join(TEMPLATES, name + ".json")) as f:
        return json.load(f)


class Graph:
    """Concrete regions and links: nodes are dicts (id, type, area, depth); edges are (a, b, kind) by node index.

    depth is how far along the main route a node is, from 0 at the start to 1 at the boss."""

    def __init__(self, template):
        self.template = template
        self.nodes, self.edges = [], []

    def add(self, node_id, kind, area):
        self.nodes.append({"id": node_id, "type": kind, "area": area, "depth": 0.0})
        return len(self.nodes) - 1

    def neighbours(self, k):
        return [b if a == k else a for a, b, _ in self.edges if k in (a, b)]

    def route(self):
        """Node indices along the main route, start to boss: the path over edges that aren't branches."""
        start = next(k for k, n in enumerate(self.nodes) if n["type"] == "start")
        boss = next(k for k, n in enumerate(self.nodes) if n["type"] == "boss")
        came, frontier = {start: None}, [start]
        while frontier:
            k = frontier.pop(0)
            for a, b, kind in self.edges:
                if kind == "branch" or k not in (a, b):
                    continue
                other = b if a == k else a
                if other not in came:
                    came[other] = k
                    frontier.append(other)
        path, k = [], boss
        while k is not None:
            path.append(k)
            k = came.get(k)
        return path[::-1]


def instantiate(template, rng):
    g = Graph(template)
    ends = {}
    for spec in template["nodes"]:
        if rng.random() > spec.get("chance", 1.0):
            continue
        lo, hi = spec.get("repeat", (1, 1))
        count = rng.randint(lo, hi)
        chain = [g.add("%s%d" % (spec["id"], c) if count > 1 else spec["id"], spec["type"], rng.randint(*spec["size"]))
                 for c in range(count)]
        for a, b in zip(chain, chain[1:]):
            g.edges.append((a, b, "main"))
        ends[spec["id"]] = chain
    for edge in template["edges"]:
        a, b = edge[0], edge[1]
        kind = edge[2] if len(edge) > 2 else "main"
        if a not in ends or b not in ends:
            continue
        # A link out of a chain leaves from its last member; a branch may leave from any of them.
        src = rng.choice(ends[a]) if kind == "branch" else ends[a][-1]
        g.edges.append((src, ends[b][0], kind))
    route = g.route()
    for order, k in enumerate(route):
        g.nodes[k]["depth"] = order / max(1, len(route) - 1)
    for k, node in enumerate(g.nodes):
        if k not in route:
            node["depth"] = max((g.nodes[o]["depth"] for o in g.neighbours(k)), default=0.0)
    return g
