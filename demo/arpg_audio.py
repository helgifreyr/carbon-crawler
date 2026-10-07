import json
import os
import random

import blue

ARPG_AUDIO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "res", "audio", "arpg")
BANKS = ["Common.bnk", "TestOneShot.bnk", "TestLoop.bnk", "NonEssentialSoundBank.bnk", "NonEssentialStream.bnk",
         "TestMusicEssential.bnk"]
LOOP_BANKS = {"ambience": "NonEssentialSoundBank", "fight": "TestLoop", "calm": "NonEssentialStream",
              "boss": "TestMusicEssential"}
MUSIC_FADE_MS = 1500
POOL = 24
STOP_FADE_MS, STEAL_FADE_MS = 30, 25
# Per sound: how many may overlap and the shortest gap between starts, so a clump of imps doesn't stack swipes.
DEFAULT_LIMIT = (4, 0.05)
LIMITS = {"swipe": (3, 0.09), "hurt": (2, 0.15), "impact": (4, 0.04), "death": (3, 0.06), "spit": (3, 0.08),
          "pickup_health": (2, 0.08), "pickup_mana": (2, 0.08)}
UP = (0.0, 1.0, 0.0)
ALIASES = {"pickup:health": "pickup_health", "pickup:mana": "pickup_mana"}
# carbon-audio exposes no bus volume and the test banks have no volume parameter, so volume is distance: a quieter
# setting pushes a sound further out along its own direction from the listener (up to FADE_M extra).
FADE_M = 45.0


class ArpgAudio:
    """Game sounds through carbon-audio (Wwise).

    tools/make_arpg_audio.py packs every sound back to back into one test-bank slot; a sound plays by sending that
    slot's event, seeking to a random take of it and stopping the voice when the take ends."""

    def __init__(self):
        wanted = os.environ.get("ARPG_AUDIO", "1") == "1"
        self.enabled = wanted and os.path.isfile(os.path.join(ARPG_AUDIO, "arpg_events.json"))
        self.loop_ids = {}
        self.played = {}
        self.volume = {"music": 1.0, "sounds": 1.0}
        self.ear = (0.0, 0.0, 0.0)
        self.track, self.playing_track = "fight", None
        if not self.enabled:
            print("[audio] off (run tools/make_arpg_audio.py to build the ARPG banks)" if wanted else "[audio] off")
            return
        import audio2
        from audio2.audiomanager import AudioManager
        with open(os.path.join(ARPG_AUDIO, "arpg_events.json")) as f:
            index = json.load(f)
        if "atlas" not in index:
            print("[audio] off (res/audio/arpg is from an older build; rerun tools/make_arpg_audio.py)")
            self.enabled = False
            return
        self.atlas, self.sounds = index["atlas"], index["sounds"]
        self.loop_events = {"ambience": index["ambience"]}
        music = index.get("music") if os.environ.get("ARPG_MUSIC", "1") == "1" else None
        self.loop_events.update(music if isinstance(music, dict) else {"fight": music} if music else {})
        with open(os.path.join(ARPG_AUDIO, "SoundPrioritizationMetadata.json")) as f:
            metadata = json.load(f)
        for event in metadata["Events"].values():
            if "eventID" in event:
                event["eventID"] = int(event["eventID"])
        blue.paths.SetSearchPath("soundbanks", ARPG_AUDIO)
        self.manager = AudioManager("soundbanks:/", "English(US)", "carbon-crawler")
        self.manager.Initialize(metadata)
        self.manager.Enable(soundBanksToLoad=BANKS)
        # Prioritization culls emitters that move and wakes them on a later tick; every pooled voice moves, so its
        # wait only delays sounds. Two dozen voices need no culling.
        self.manager.DisableSoundPrioritization()
        self.listener = audio2.GetListener()
        self.pool = [audio2.AudEmitter("arpg_sfx_%d" % i) for i in range(POOL)]
        self.stops, self.last_start = {}, {}
        self.rng = random.Random(9)
        self.loops = {name: audio2.AudEmitter("arpg_" + name) for name in self.loop_events}

    def play(self, kind, position):
        kind = ALIASES.get(kind, kind)
        if not self.enabled or self.volume["sounds"] <= 0.0 or kind not in self.sounds:
            return
        now = blue.os.GetWallclockTimeNow()
        limit, spacing = LIMITS.get(kind, DEFAULT_LIMIT)
        active = [k for k, _ in self.stops.values() if k == kind]
        if len(active) >= limit or now - self.last_start.get(kind, 0) < spacing * 1e7:
            return
        offset_ms, length_ms = self.rng.choice(self.sounds[kind])
        free = [i for i in range(POOL) if i not in self.stops]
        slot = free[0] if free else min(self.stops, key=lambda i: self.stops[i][1])
        emitter = self.pool[slot]
        if slot in self.stops:
            emitter.StopEvent(self.atlas, STEAL_FADE_MS)
        emitter.SetPlacement((0.0, 0.0, 1.0), UP, self.faded(position, "sounds"))
        playing = emitter.SendEvent(self.atlas)
        if not playing:
            return
        emitter.SeekOnEventMs(playing, offset_ms)
        self.stops[slot] = (kind, now + int(length_ms * 1e4))
        self.last_start[kind] = now
        self.played[kind] = self.played.get(kind, 0) + 1

    def update(self, position, front, up=UP):
        if not self.enabled:
            return
        self.ear = tuple(position)
        self.listener.SetPosition(tuple(front), tuple(up), tuple(position))
        for name, emitter in self.loops.items():
            kind = "sounds" if name == "ambience" else "music"
            lift = (1.0 - self.volume[kind]) * FADE_M
            emitter.SetPlacement(tuple(front), tuple(up), (position[0], position[1] + lift, position[2]))
        now = blue.os.GetWallclockTimeNow()
        for slot, (_, due) in list(self.stops.items()):
            if now >= due:
                self.pool[slot].StopEvent(self.atlas, STOP_FADE_MS)
                del self.stops[slot]
        # SendEvent queues even before its bank has loaded, so a loop is only started once its bank is in.
        loaded = " ".join(str(b) for b in self.manager.GetLoadedSoundBanks())
        if "ambience" not in self.loop_ids and LOOP_BANKS["ambience"] in loaded:
            self.loop_ids["ambience"] = self.loops["ambience"].SendEvent(self.loop_events["ambience"]) or -1
        wanted = self.track if self.volume["music"] > 0.0 and self.track in self.loops else None
        if wanted != self.playing_track:
            if self.playing_track:
                self.loops[self.playing_track].StopEvent(self.loop_events[self.playing_track], MUSIC_FADE_MS)
                self.playing_track = None
            if wanted and LOOP_BANKS[wanted] in loaded:
                self.loops[wanted].SendEvent(self.loop_events[wanted])
                self.playing_track = wanted

    def set_volumes(self, music=1.0, sounds=1.0):
        self.volume = {"music": max(0.0, min(1.0, music)), "sounds": max(0.0, min(1.0, sounds))}
        if self.enabled and "ambience" in self.loops:
            if self.volume["sounds"] > 0.0:
                self.loops["ambience"].Unmute()
            else:
                self.loops["ambience"].Mute()

    def faded(self, position, kind):
        extra = (1.0 - self.volume[kind]) * FADE_M
        if extra <= 0.0:
            return tuple(position)
        dx, dy, dz = (position[i] - self.ear[i] for i in range(3))
        n = (dx * dx + dy * dy + dz * dz) ** 0.5
        ux, uy, uz = (dx / n, dy / n, dz / n) if n > 1e-3 else UP
        return (self.ear[0] + ux * (n + extra), self.ear[1] + uy * (n + extra), self.ear[2] + uz * (n + extra))

    def set_track(self, name):
        """Fades to another music track ("calm", "fight" or "boss") on the next update."""
        self.track = name

    def report(self):
        if self.enabled:
            print("[audio] ambience %s, music %s, played %s" % ("ambience" in self.loop_ids, self.playing_track,
                                                                 self.played))
