# Event -> sound; events not listed are silent.
EVENT_SOUNDS = {"cast": "cast", "attack": "swipe", "nova": "nova", "blink": "blink", "levelup": "levelup",
                "frost": "frost", "ring": "nova", "enrage": "roar", "chain": "chain", "meteor": "meteor_fall",
                "rain": "meteor_fall", "impact": "impact", "died": "death", "roll": "roll", "jump": "jump", "mend": "mend", "charge": "snarl",
                "stunned": "impact", "fuse": "fuse", "blocked": "clang"}
# Feedback meant for one player: only heard when it happens to your own character.
PERSONAL = ("levelup", "pickup", "damaged")


class Sounds:
    """Plays each event's sound where it happened."""

    def __init__(self, bus, audio):
        self.audio = audio
        bus.on(list(EVENT_SOUNDS) + ["pickup", "damaged", "landed"], self.on_event)

    def on_event(self, event):
        if not event.present:
            return
        name, data, actor = event.name, event.data, event.actor
        if name in PERSONAL and (actor is None or actor.role != "you"):
            return
        position = event.position
        if name == "pickup":
            sound = "pickup:" + data["loot"]
        elif name == "damaged":
            sound = "hurt"
        elif name == "landed":
            sound = {"meteor": "meteor", "rain": "meteor", "burst": "splat"}.get(data["kind"], "slam")
            position = data["center"]
        elif name == "attack" and actor is not None and actor.role == "spitter":
            sound = "spit"
        else:
            sound = EVENT_SOUNDS[name]
        if name == "chain":
            (x, z), y = data["path"][-1], position[1] if position else 0.0
            position = (x, y, z)
        elif name == "meteor":
            position = (data["at"][0], 2.0, data["at"][1])
        elif name in ("fuse", "blocked"):
            position = (data["at"][0], 0.5, data["at"][1])
        elif name == "blink" and data.get("dest"):
            position = (data["dest"][0], position[1] if position else 0.0, data["dest"][1])
        if sound and position is not None:
            self.audio.play(sound, position)
