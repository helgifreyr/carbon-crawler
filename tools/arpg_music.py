"""Dungeon synth loops for the ARPG, written as notes and rendered with tools/sfx.py."""
import numpy as np

from sfx import RATE, bandpass, drive, env, lowpass, osc, room, sweep, vibrato, white


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def place(track, start_s, samples, gain=1.0):
    i = int(start_s * RATE)
    end = min(len(track), i + len(samples))
    if end > i:
        track[i:end] += samples[:end - i] * gain


def pad_note(midi, seconds, rng, cutoff=700.0):
    n = int((seconds + 2.0) * RATE)
    voices = sum(osc("saw", vibrato(np.full(n, hz(midi) * 2 ** (c / 1200.0)), 0.3 + 0.1 * k, 0.002))
                 for k, c in enumerate((-8, 0, 7)))
    t = np.arange(n) / RATE
    sweep_ = cutoff + 0.5 * cutoff * np.sin(2 * np.pi * 0.07 * t + rng.uniform(0, 6.28))
    shape = np.clip(t / 1.4, 0, 1) * np.clip((seconds + 1.8 - t) / 1.8, 0, 1)
    return lowpass(voices / 3.0, sweep_) * shape


def choir_note(midi, seconds):
    n = int((seconds + 1.5) * RATE)
    source = osc("saw", vibrato(np.full(n, hz(midi)), 5.0, 0.004))
    vowel = bandpass(source, 780, 2.5) + bandpass(source, 1150, 3.5) * 0.6 + bandpass(source, 2600, 5.0) * 0.15
    t = np.arange(n) / RATE
    return vowel * np.clip(t / 0.9, 0, 1) * np.clip((seconds + 1.2 - t) / 1.2, 0, 1)


def lead_note(midi, seconds, bright=1900.0):
    n = int((seconds + 0.6) * RATE)
    t = np.arange(n) / RATE
    depth = 0.006 * np.clip((t - 0.35) / 0.4, 0, 1)
    freq = hz(midi) * (1.0 + depth * np.sin(2 * np.pi * 5.2 * t))
    tone = lowpass(osc("square", freq, duty=0.32) * 0.6 + osc("triangle", freq), bright)
    return tone * np.clip(t / 0.06, 0, 1) * np.clip((seconds + 0.5 - t) / 0.5, 0, 1)


def bell_note(midi, seconds=2.6):
    freq = np.full(int(seconds * RATE), hz(midi))
    return (osc("sine", freq) + 0.35 * osc("sine", freq * 2.76) + 0.15 * osc("sine", freq * 5.4)) * env(
        seconds, 0.002, 0.0, seconds, 5.0)


def harp_note(midi):
    seconds = 2.4
    freq = np.full(int(seconds * RATE), hz(midi))
    return (osc("triangle", freq) + 0.4 * osc("sine", freq * 2)) * env(seconds, 0.003, 0.0, seconds, 4.0)


def brass_stab(notes, seconds):
    n = int((seconds + 0.4) * RATE)
    t = np.arange(n) / RATE
    voices = sum(osc("saw", np.full(n, hz(m))) for m in notes) / len(notes)
    shape = np.clip(t / 0.03, 0, 1) * np.clip((seconds + 0.3 - t) / 0.3, 0, 1)
    return lowpass(voices, sweep((seconds + 0.4), 2400, 700)) * shape


def bass_note(midi, seconds, gritty=False):
    n = int((seconds + 0.3) * RATE)
    source = osc("saw", np.full(n, hz(midi))) + (0.6 * osc("square", np.full(n, hz(midi) * 1.003)) if gritty else 0)
    t = np.arange(n) / RATE
    return lowpass(source, 300 if not gritty else 520) * np.clip(t / 0.01, 0, 1) * np.clip((seconds + 0.25 - t) / 0.25, 0, 1)


def drum(rng, low=95.0, high=48.0, seconds=1.6):
    boom = osc("sine", sweep(seconds, low, high)) * env(seconds, 0.003, 0.0, seconds * 0.85, 2.2)
    skin = lowpass(white(seconds, rng), sweep(seconds, 1400, 120)) * env(seconds, 0.002, 0.0, 0.25, 2.0) * 0.5
    return boom + skin


def war_drum(rng):
    seconds = 0.5
    body = osc("sine", sweep(seconds, 140, 70)) * env(seconds, 0.002, 0.0, 0.35, 2.5)
    slap = bandpass(white(seconds, rng), 900, 1.2) * env(seconds, 0.001, 0.0, 0.08, 2.0) * 0.7
    return drive(body + slap, 1.6)


def drone(seconds, midi=26):
    t = np.arange(int(seconds * RATE)) / RATE
    # Whole cycles over the loop so the drone meets itself at the seam.
    f = round(hz(midi) * seconds) / seconds
    breath = 0.75 + 0.25 * np.sin(2 * np.pi * t * 2.0 / seconds)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * breath


FIGHT = {
    "bpm": 66.0, "drone": 26, "seed": 66,
    # (chord notes, bass root, bars); two bars each: i VI iv V in D minor, then VI V back to the top.
    "chords": [([50, 53, 57, 62], 38, 2), ([46, 50, 53, 58], 34, 2), ([43, 50, 55, 58], 31, 2), ([45, 52, 57, 61], 33, 2)] * 2
              + [([46, 50, 53, 58], 34, 2), ([45, 52, 57, 61], 33, 2)],
    "melody_bar": 8,
    "melody": [(0, 2, 69), (2, 1, 65), (3, 1, 64), (4, 4, 62), (8, 2, 65), (10, 1, 67), (11, 1, 69), (12, 2, 70),
               (14, 1, 69), (15, 1, 67), (16, 2, 67), (18, 1, 65), (19, 1, 62), (20, 2, 58), (22, 2, 62), (24, 2, 64),
               (26, 1, 61), (27, 1, 64), (28, 4, 69), (32, 3, 70), (35, 1, 69), (36, 4, 65), (40, 2, 64), (42, 2, 61),
               (44, 4, 57)],
    "mix": {"pads": 0.32, "choir": 0.16, "bass": 0.3, "harp": 0.11, "lead": 0.22, "drums": 0.45, "drone": 0.12},
    "full_from": 4,
}
CALM = {
    "bpm": 58.0, "drone": 21, "seed": 58,
    # i VI III VII in A minor, gently, twice.
    "chords": [([57, 60, 64, 69], 45, 2), ([53, 57, 60, 65], 41, 2), ([48, 52, 55, 60], 36, 2), ([55, 59, 62, 67], 43, 2)] * 2,
    "melody_bar": 8, "lead_voice": "bell",
    "melody": [(0, 2, 76), (2, 2, 72), (4, 4, 69), (8, 2, 72), (10, 1, 74), (11, 1, 76), (12, 4, 77), (16, 2, 76),
               (18, 2, 72), (20, 4, 67), (24, 2, 71), (26, 2, 74), (28, 4, 76)],
    "mix": {"pads": 0.22, "choir": 0.1, "bass": 0.16, "harp": 0.16, "lead": 0.2, "drums": 0.0, "drone": 0.08},
    "pad_cutoff": 520.0, "full_from": 2, "harp_eighths": False,
}
BOSS = {
    "bpm": 96.0, "drone": 24, "seed": 96,
    # i VI iv V in C minor, one bar each, driven by a bass ostinato and war drums.
    "chords": [([48, 51, 55, 60], 36, 1), ([44, 48, 51, 56], 32, 1), ([41, 44, 48, 53], 29, 1), ([43, 47, 50, 55], 31, 1)] * 4,
    "melody_bar": 4,
    "melody": [(0, 1.5, 72), (1.5, 0.5, 74), (2, 2, 75), (4, 1.5, 72), (5.5, 0.5, 68), (6, 2, 72), (8, 1.5, 77),
               (9.5, 0.5, 75), (10, 1, 74), (11, 1, 72), (12, 4, 71), (16, 1.5, 75), (17.5, 0.5, 77), (18, 2, 79),
               (20, 1.5, 80), (21.5, 0.5, 79), (22, 2, 77), (24, 2, 75), (26, 2, 74), (28, 4, 71),
               (32, 1.5, 72), (33.5, 0.5, 74), (34, 2, 75), (36, 2, 72), (38, 2, 68), (40, 4, 67), (44, 4, 71)],
    "mix": {"pads": 0.2, "choir": 0.2, "bass": 0.34, "harp": 0.0, "lead": 0.26, "drums": 0.5, "drone": 0.1,
            "brass": 0.24, "war": 0.42},
    "pad_cutoff": 900.0, "full_from": 0, "boss": True,
}
TRACKS = {"fight": FIGHT, "calm": CALM, "boss": BOSS}


def render(track=FIGHT):
    """The whole loop, mono at RATE; the reverb tail is folded onto the start so it repeats seamlessly."""
    rng = np.random.default_rng(track["seed"])
    beat = 60.0 / track["bpm"]
    bars = sum(c[2] for c in track["chords"])
    length = bars * 4 * beat
    tail = 6.0
    n = int((length + tail) * RATE)
    layers = {name: np.zeros(n) for name in ("pads", "choir", "bass", "harp", "lead", "drums", "brass", "war")}
    start = 0.0
    for i, (notes, root, chord_bars) in enumerate(track["chords"]):
        chord_s = chord_bars * 4 * beat
        full = i >= track.get("full_from", 4)
        for m in notes:
            place(layers["pads"], start, pad_note(m, chord_s, rng, track.get("pad_cutoff", 700.0)))
        if track.get("boss"):
            for k in range(int(chord_bars * 8)):
                octave = 12 if k % 4 == 2 else 0
                place(layers["bass"], start + k * beat / 2, bass_note(root + octave, beat / 2 * 0.85, True))
            for k in range(chord_bars * 4):
                if k % 2 == 1:
                    place(layers["brass"], start + k * beat + beat / 2, brass_stab(notes[1:], beat * 0.4))
            for k in range(int(chord_bars * 8)):
                if k in (0, 3, 4, 6) or (full and k == 7):
                    place(layers["war"], start + k * beat / 2, war_drum(rng), 1.0 if k == 0 else 0.6)
            place(layers["drums"], start, drum(rng, 80, 40, 1.2))
        else:
            place(layers["bass"], start, lowpass(osc("saw", np.full(int((chord_s + 1.5) * RATE), hz(root))), 260)
                  * env(chord_s + 1.5, 0.6, chord_s - 0.4, 1.4, 1.5))
            if full and track["mix"]["drums"]:
                place(layers["drums"], start, drum(rng))
                place(layers["drums"], start + 7 * beat, drum(rng), 0.45)
        if full:
            place(layers["choir"], start, choir_note(notes[-1] + 12, chord_s))
        if track["mix"]["harp"]:
            arp = [notes[1] + 12, notes[2] + 12, notes[3] + 12, notes[2] + 12]
            step = beat / 2 if full and track.get("harp_eighths", True) else beat
            for k in range(int(chord_s / step)):
                place(layers["harp"], start + k * step, harp_note(arp[k % len(arp)]), 0.8 if k % 2 == 0 else 0.55)
        start += chord_s
    voice = bell_note if track.get("lead_voice") == "bell" else lead_note
    for beat_at, beats, midi in track["melody"]:
        at = (track["melody_bar"] * 4 + beat_at) * beat
        place(layers["lead"], at, voice(midi) if voice is bell_note else voice(midi, beats * beat))
    mix = track["mix"]
    mixed = sum(layers[name] * mix.get(name, 0.0) for name in layers)
    mixed[:int(length * RATE)] += drone(length, track["drone"]) * mix["drone"]
    wet = room(mixed, wet=0.42 if not track.get("boss") else 0.3, size=2.6, damp=2600.0, feedback=1.18, tail_s=0.0)[:n]
    loop = wet[:int(length * RATE)].copy()
    spill = wet[int(length * RATE):]
    loop[:len(spill)] += spill
    return loop / np.abs(loop).max() * 0.55
