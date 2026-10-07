import math
import random

from arpg_anim import find_params
from arpg_fx import ArpgFx
from arpg_view.actors import BOLT_LIFT, orb_world, player_color
from arpg_view.events import Event
from arpg_view.geometry import axis_quat, look_rotation
from arpg_world import KINDS, SPELLS

NOVA, FROST, METEOR, BLINK = SPELLS["nova"], SPELLS["frost"], SPELLS["meteor"], SPELLS["blink"]
SLAM, RAIN = KINDS["brute"]["slam"], KINDS["warlord"]["rain"]
LIGHTNING_S, EMBERS_EVERY_S, MEND_S = 0.25, 0.07, 0.6
AREA_SHOW_S, AREA_GROW_S = 0.45, 0.12
AREA_COLORS = {"nova": (1.0, 0.55, 0.2), "frost": (0.55, 0.8, 1.0), "meteor": (1.0, 0.8, 0.3), "slam": (1.0, 0.3, 0.15),
               "burst": (0.6, 1.0, 0.25)}
# Telegraph rings as (outline, fill) per kind: gold for the player's own meteor, sickly green for a bloater's burst.
RING_COLORS = {"meteor": ((1.0, 0.8, 0.2, 0.5), (1.0, 0.9, 0.4, 0.95)), "burst": ((0.5, 1.0, 0.2, 0.5), (0.7, 1.0, 0.3, 0.95))}
HOSTILE_RING = ((1.0, 0.25, 0.1, 0.5), (1.0, 0.45, 0.15, 0.95))
FLOOR_Y = -0.45
UP = (0.0, 1.0, 0.0)


class Effects:
    """Particles, telegraphs, lightning, falling meteors, burning ground and area outlines, driven by events.

    A telegraph that runs out emits a landed event (center, radius, kind) for sound and camera shake."""

    def __init__(self, stage, bus, actor=lambda key: None):
        self.stage, self.bus, self.actor = stage, bus, actor
        self.fx = ArpgFx(stage.trinity, stage.scene)
        self.telegraphs, self.lightning, self.falling, self.burns, self.areas = [], [], [], [], []
        self.mends, self.lanes = [], []
        self.rng = random.Random(5)
        handlers = {"cast": self._cast, "nova": self._nova, "blink": self._blink, "frost": self._frost,
                    "levelup": self._levelup, "pickup": self._pickup, "chain": self._chain, "meteor": self._meteor,
                    "slam": self._slam, "rain": self._rain, "impact": self._impact, "died": self._died,
                    "mend": self._mend, "charge": self._charge, "stunned": self._stunned, "fuse": self._fuse,
                    "blocked": self._blocked}
        for name, handler in handlers.items():
            bus.on([name], lambda event, h=handler: h(event) if event.present else None)

    def show_area(self, kind, center, radius, yaw=None, arc=None):
        """An exact outline of where an area effect reached, drawn briefly on the floor."""
        self.areas.append({"kind": kind, "center": center, "radius": radius, "yaw": yaw, "arc": arc,
                           "start": self.stage.clock})

    def _cast(self, event):
        if event.actor is not None and event.actor.last is not None:
            self.fx.spawn("fx_cast_" + player_color(event.actor.key), orb_world(event.actor))

    def _nova(self, event):
        if event.position is None:
            return
        x, y, z = event.position
        radius = event.data.get("radius", NOVA["radius"])
        self.fx.spawn("fx_nova", (x, y - 0.35, z), scale=radius / NOVA["radius"])
        self.show_area("nova", event.position, radius)
        if event.data.get("slow"):
            self.show_area("frost", event.position, radius * 0.97)

    def _blink(self, event):
        y = event.position[1] + 0.5 if event.position else 0.5
        ox, oz = event.data["origin"]
        dest = event.data.get("dest")
        self.fx.spawn("fx_blink", (ox, y, oz))
        self.fx.spawn("fx_blink", (dest[0], y, dest[1]) if dest else (event.position[0], y, event.position[2]))
        if event.data.get("frost"):
            self.show_area("frost", (ox, y, oz), BLINK["frost_radius"])

    def _frost(self, event):
        if event.position is None:
            return
        x, y, z = event.position
        yaw, reach, arc = event.data["yaw"], event.data["reach"], event.data["arc_deg"]
        self.fx.spawn("fx_frost", (x, y - 0.1, z), axis_quat(UP, yaw), scale=reach / FROST["range"])
        self.show_area("frost", event.position, reach, yaw=yaw, arc=math.radians(arc))

    def _levelup(self, event):
        if event.position is not None:
            x, y, z = event.position
            self.fx.spawn("fx_levelup", (x, y - 0.3, z))

    def _pickup(self, event):
        if event.position is not None:
            x, y, z = event.position
            self.fx.spawn("fx_pickup_" + event.data["loot"], (x, y + 0.5, z))

    def _chain(self, event):
        path = event.data["path"]
        y = (event.position[1] if event.position else 0.0) + BOLT_LIFT
        self.lightning.append({"path": [(px, y, pz) for px, pz in path], "until": self.stage.clock + LIGHTNING_S})
        for px, pz in path[1:]:
            self.fx.spawn("fx_zap", (px, y, pz))

    def _charge(self, event):
        # The lane a hound is about to rush down, filling from its end of the lane as the wind-up runs out.
        if event.position is None:
            return
        x, _, z = event.position
        self.lanes.append({"from": (x, z), "to": tuple(event.data["to"]), "width": event.data["width"],
                           "start": self.stage.clock, "end": self.stage.clock + event.data["windup"]})

    def _fuse(self, event):
        x, z = event.data["at"]
        self.telegraphs.append({"center": (x, 0.0, z), "start": self.stage.clock, "kind": "burst",
                                "radius": event.data["radius"], "end": self.stage.clock + event.data["seconds"]})

    def _blocked(self, event):
        x, z = event.data["at"]
        yaw = event.actor.yaw if event.actor is not None and event.actor.yaw is not None else 0.0
        self.fx.spawn("fx_impact", (x, BOLT_LIFT, z), axis_quat(UP, yaw + math.pi))

    def _stunned(self, event):
        if event.position is not None:
            x, y, z = event.position
            for k in range(3):
                a = 2 * math.pi * k / 3
                self.fx.spawn("fx_zap", (x + 0.3 * math.cos(a), y + 0.9, z + 0.3 * math.sin(a)))

    def _mend(self, event):
        # A link from the shaman's staff stone to everyone it touched, held for a moment, and a glow on each.
        if event.actor is None or event.actor.last is None:
            return
        self.mends.append({"from": event.key, "targets": event.data["targets"], "start": self.stage.clock})
        for key in event.data["targets"]:
            target = self.actor(key)
            if target is not None and target.last is not None:
                x, y, z = target.last
                self.fx.spawn("fx_mend", (x, y + 0.4, z))

    def _meteor(self, event):
        x, z = event.data["at"]
        clock = self.stage.clock
        self.telegraphs.append({"center": (x, 0.0, z), "start": clock, "radius": METEOR["radius"],
                                "end": clock + METEOR["delay_s"], "kind": "meteor",
                                "burn": (event.data["burn_radius"], event.data["burn_s"])})
        rock = self.stage.placeable("projectile")
        rock.scaling = (2.4, 2.4, 2.4)
        self.stage.add(rock)
        self.falling.append({"placeable": rock, "start": clock, "from": (x + 5.0, 15.0, z + 5.0), "to": (x, 0.2, z),
                             "params": None})

    def _slam(self, event):
        if event.position is not None:
            self.telegraphs.append({"center": event.position, "start": self.stage.clock, "kind": "slam",
                                    "radius": event.data["radius"], "end": self.stage.clock + event.data["windup"]})

    def _rain(self, event):
        for x, z in event.data["points"]:
            self.telegraphs.append({"center": (x, 0.0, z), "start": self.stage.clock, "kind": "rain",
                                    "radius": RAIN["radius"], "end": self.stage.clock + RAIN["delay_s"]})

    def _impact(self, event):
        x, y, z = event.position
        self.fx.spawn("fx_impact", (x, y + BOLT_LIFT, z), axis_quat(UP, event.actor.yaw or 0.0))

    def _died(self, event):
        x, y, z = event.position
        self.fx.spawn("fx_death", (x, y + 0.5, z), axis_quat(UP, event.actor.yaw or 0.0))

    def update(self, dt):
        clock = self.stage.clock
        for slam in list(self.telegraphs):
            if clock >= slam["end"]:
                self.telegraphs.remove(slam)
                self._land(slam)
        for rock in list(self.falling):
            u = (clock - rock["start"]) / METEOR["delay_s"]
            if u >= 1.0:
                self.falling.remove(rock)
                self.stage.remove(rock["placeable"])
                continue
            a, b = rock["from"], rock["to"]
            rock["placeable"].translation = tuple(p + (q - p) * u * u for p, q in zip(a, b))
            rock["placeable"].rotation = look_rotation(tuple(q - p for p, q in zip(a, b)))
            if rock["params"] is None:
                rock["params"] = find_params(rock["placeable"], ("FxTime",))
            for p in (rock["params"] or {}).get("FxTime", ()):
                p.value = (clock - rock["start"] + 0.3, 1.0, 0.0, 0.0)
        for burn in list(self.burns):
            if clock >= burn["until"]:
                self.burns.remove(burn)
            elif clock >= burn["next"]:
                burn["next"] = clock + EMBERS_EVERY_S
                r = burn["radius"] * math.sqrt((clock * 7.31) % 1.0)
                a = (clock * 13.7) % (2 * math.pi)
                x, _, z = burn["center"]
                self.fx.spawn("fx_embers", (x + r * math.cos(a), -0.4, z + r * math.sin(a)))
        self.lightning = [bolt for bolt in self.lightning if bolt["until"] > clock]
        self.mends = [m for m in self.mends if clock - m["start"] < MEND_S]
        self.lanes = [lane for lane in self.lanes if clock < lane["end"]]
        self.areas = [area for area in self.areas if clock - area["start"] < AREA_SHOW_S]
        self.fx.update(dt)

    def _land(self, slam):
        x, y, z = slam["center"]
        falls = slam["kind"] in ("meteor", "rain")
        if slam["kind"] == "burst":
            self.fx.spawn("fx_goo", (x, y - 0.2, z), scale=slam["radius"] / 3.2)
        else:
            self.fx.spawn("fx_meteor" if falls else "fx_slam", (x, y - 0.4, z),
                          scale=slam["radius"] / (METEOR["radius"] if falls else SLAM["radius"]))
        self.show_area(slam["kind"] if slam["kind"] in ("meteor", "burst") else "slam", slam["center"], slam["radius"])
        if slam["kind"] == "meteor":
            radius, seconds = slam["burn"]
            self.burns.append({"center": slam["center"], "until": self.stage.clock + seconds, "next": self.stage.clock,
                               "radius": radius})
            self.show_area("meteor", slam["center"], radius)
        self.bus.emit(Event("landed", None, {"center": slam["center"], "radius": slam["radius"], "kind": slam["kind"]}))

    def draw(self, add_ring, add_line):
        """Floor rings for telegraphs and areas, and jittered strands for chain lightning, on the overlay."""
        clock = self.stage.clock
        for slam in self.telegraphs:
            u = min(1.0, (clock - slam["start"]) / (slam["end"] - slam["start"]))
            x, _, z = slam["center"]
            edge, fill = RING_COLORS.get(slam["kind"], HOSTILE_RING)
            add_ring((x, FLOOR_Y, z), slam["radius"], edge)
            add_ring((x, FLOOR_Y, z), slam["radius"] * u, fill)
        for bolt in self.lightning:
            for strand in range(2):
                points = []
                for (ax, ay, az), (bx, by, bz) in zip(bolt["path"], bolt["path"][1:]):
                    for k in range(6):
                        u, j = k / 6.0, 0.0 if k == 0 else 0.35
                        points.append((ax + (bx - ax) * u + (self.rng.random() - 0.5) * j,
                                       ay + (by - ay) * u + (self.rng.random() - 0.5) * j,
                                       az + (bz - az) * u + (self.rng.random() - 0.5) * j))
                points.append(bolt["path"][-1])
                color = (0.75, 0.9, 1.0, 1.0) if strand == 0 else (0.35, 0.55, 1.0, 0.8)
                for a, b in zip(points, points[1:]):
                    add_line(a, color, b, color)
        for lane in self.lanes:
            u = min(1.0, (clock - lane["start"]) / (lane["end"] - lane["start"]))
            (ax, az), (bx, bz) = lane["from"], lane["to"]
            length = math.hypot(bx - ax, bz - az) or 1.0
            nx, nz = -(bz - az) / length * lane["width"] / 2, (bx - ax) / length * lane["width"] / 2
            edge, fill = (1.0, 0.3, 0.1, 0.55), (1.0, 0.5, 0.15, 0.95)
            corners = [(ax + nx, az + nz), (bx + nx, bz + nz), (bx - nx, bz - nz), (ax - nx, az - nz)]
            for (px, pz), (qx, qz) in zip(corners, corners[1:] + corners[:1]):
                add_line((px, FLOOR_Y, pz), edge, (qx, FLOOR_Y, qz), edge)
            fx, fz = ax + (bx - ax) * u, az + (bz - az) * u
            for k in (-1.0, 0.0, 1.0):
                add_line((ax + nx * k * 0.6, FLOOR_Y, az + nz * k * 0.6), fill, (fx + nx * k * 0.6, FLOOR_Y, fz + nz * k * 0.6), fill)
            add_line((fx + nx, FLOOR_Y, fz + nz), fill, (fx - nx, FLOOR_Y, fz - nz), fill)
        for mend in self.mends:
            source = self.actor(mend["from"])
            if source is None or source.last is None:
                continue
            fade = 1.0 - (clock - mend["start"]) / MEND_S
            sx, sy, sz = source.last
            start = (sx, sy + 1.1 * source.size, sz)
            for key in mend["targets"]:
                target = self.actor(key)
                if target is None or target.last is None:
                    continue
                tx, ty, tz = target.last
                end = (tx, ty + 0.5 * target.size, tz)
                points = [tuple(a + (b - a) * k / 8.0 for a, b in zip(start, end)) for k in range(9)]
                points = [(px, py + 0.5 * math.sin(math.pi * k / 8.0), pz) for k, (px, py, pz) in enumerate(points)]
                color = (0.35, 1.0, 0.8, 0.9 * fade)
                for lift in (0.0, 0.03):
                    for a, b in zip(points, points[1:]):
                        add_line((a[0], a[1] + lift, a[2]), color, (b[0], b[1] + lift, b[2]), color)
        for area in self.areas:
            age = clock - area["start"]
            grow = min(1.0, age / AREA_GROW_S)
            fade = 1.0 - max(0.0, age - AREA_GROW_S) / (AREA_SHOW_S - AREA_GROW_S)
            color = AREA_COLORS[area["kind"]] + (0.9 * fade,)
            x, _, z = area["center"]
            radius = area["radius"] * grow
            if area["arc"] is None:
                add_ring((x, FLOOR_Y, z), radius, color, segments=48)
                continue
            yaw, arc = area["yaw"], area["arc"]
            points = [(x + radius * math.sin(yaw - arc + 2 * arc * k / 16), FLOOR_Y,
                       z + radius * math.cos(yaw - arc + 2 * arc * k / 16)) for k in range(17)]
            for a, b in zip([(x, FLOOR_Y, z)] + points, points + [(x, FLOOR_Y, z)]):
                add_line(a, color, b, color)
