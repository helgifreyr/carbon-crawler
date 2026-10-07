"""Builds res/audio/arpg: copies of the Wwise test banks with their media replaced by synthesized ARPG sounds."""
import json
import os
import shutil
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sfx
from arpg_music import TRACKS, render as render_music
from arpg_sounds import RECIPES, VARIATIONS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "res", "audio", "testbanks")
OUT = os.path.join(ROOT, "res", "audio", "arpg")
DEFAULT_TAKES = 3
GAP_S = 0.35
PITCH_SPREAD = 0.07

# Three test-bank media are reused. Every effect goes back to back into one slot (an "atlas") that the client plays
# and seeks into; two looping slots carry the music and the room ambience. Real content would be authored in Wwise.
ATLAS = ("Play_TestOneShot", "Essential_Media/TestOneShot.bnk", 870446094)
MUSIC = {"fight": ("Play_TestLoop", "Essential_Media/TestLoop.bnk", 839160035),
         "calm": ("Play_NonEssentialStream", "Media/192745030.wem", 192745030),
         "boss": ("Play_TestEssential", "Essential_Media/460136326.wem", 460136326)}
AMBIENCE = ("Play_NonEssentialBank", "NonEssentialSoundBank.bnk", 737420022)


def ambience(rate):
    seconds = 12.0
    n = int(seconds * rate)
    t = np.arange(n) / rate
    rng = np.random.default_rng(7)
    # Whole cycles of every partial over the loop length, so the ends meet without a click.
    drone = sum(np.sin(2 * np.pi * (round(f * seconds) / seconds) * t) * a for f, a in ((55.0, 0.5), (55.5, 0.4), (82.5, 0.15)))
    wind = sfx.lowpass(rng.uniform(-1, 1, n), 260) * (0.6 + 0.4 * np.sin(2 * np.pi * t / seconds)) * 3
    drips = np.zeros(n)
    for start in rng.uniform(0.5, seconds - 0.5, 9):
        k, m = int(start * rate), int(0.12 * rate)
        f = sfx.sweep(0.12, 2400, 1100)[:m]
        drips[k:k + m] += np.sin(2 * np.pi * np.cumsum(f) / rate) * np.exp(-np.arange(m) / rate / 0.03) * rng.uniform(0.2, 0.5)
    x = drone * 0.5 + wind * 0.5 + drips
    return x / np.abs(x).max() * 0.6


def build_atlas(rate):
    """All recipes and their variations back to back, separated by silence; returns samples and the index."""
    gap = np.zeros(int(GAP_S * rate))
    # Leading silence: if a seek ever lands a moment late, what plays first is nothing.
    parts, index, cursor = [gap], {}, len(gap)
    for name, recipe in RECIPES.items():
        takes, count = [], VARIATIONS.get(name, DEFAULT_TAKES)
        for take in range(count):
            rng = np.random.default_rng([sum(map(ord, name)), take])
            pitch = 1.0 + PITCH_SPREAD * (take - (count - 1) / 2.0)
            samples = sfx.resample(sfx.finish(recipe(rng, pitch)), rate)
            takes.append([round(cursor * 1000.0 / rate), round(len(samples) * 1000.0 / rate)])
            parts += [samples, gap]
            cursor += len(samples) + len(gap)
        index[name] = takes
    return np.concatenate(parts), index


def chunks(blob, start=12):
    i, out = start, []
    while i + 8 <= len(blob):
        cid, n = blob[i:i + 4], struct.unpack("<I", blob[i + 4:i + 8])[0]
        out.append((cid, i, n))
        i += 8 + n + (n & 1)
    return out


def rewrap(wem, samples):
    """The original .wem with only its PCM data replaced, matching its channel count and sample rate."""
    fmt = next(c for c in chunks(wem) if c[0] == b"fmt ")
    channels, rate = struct.unpack("<HI", wem[fmt[1] + 10:fmt[1] + 16])
    pcm = np.clip(samples * 32767, -32768, 32767).astype("<i2")
    pcm = np.repeat(pcm[:, None], channels, axis=1).tobytes()
    body = b"WAVE"
    for cid, i, n in chunks(wem):
        if cid != b"data":
            body += wem[i:i + 8 + n + (n & 1)]
    body += b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def wem_rate(wem):
    fmt = next(c for c in chunks(wem) if c[0] == b"fmt ")
    return struct.unpack("<I", wem[fmt[1] + 12:fmt[1] + 16])[0]


def rebank(bank, media_id, make):
    parts = {cid: (i, n) for cid, i, n in chunks(bank, 0)}
    didx_i, _ = parts[b"DIDX"]
    mid, offset, size = struct.unpack("<3I", bank[didx_i + 8:didx_i + 20])
    assert mid == media_id, (mid, media_id)
    data_i, _ = parts[b"DATA"]
    old = bank[data_i + 8 + offset:data_i + 8 + offset + size]
    new = make(old)
    hirc_i, hirc_n = parts[b"HIRC"]
    hirc = bytearray(bank[hirc_i:hirc_i + 8 + hirc_n])
    # A sound's source entry is: plugin id, stream type, media id, cache id, in-memory media size.
    at = hirc.find(struct.pack("<I", media_id))
    assert struct.unpack("<I", hirc[at + 8:at + 12])[0] == size
    hirc[at + 8:at + 12] = struct.pack("<I", len(new))
    out = bytearray()
    for cid, i, n in chunks(bank, 0):
        if cid == b"DIDX":
            out += b"DIDX" + struct.pack("<I", 12) + struct.pack("<3I", media_id, 0, len(new))
        elif cid == b"DATA":
            out += b"DATA" + struct.pack("<I", len(new)) + new
        elif cid == b"HIRC":
            out += hirc
        else:
            out += bank[i:i + 8 + n]
    return bytes(out)


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("run tools/fetch_testbanks.sh first")
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    index = {}

    def make_atlas(wem):
        samples, found = build_atlas(wem_rate(wem))
        index.update(found)
        return rewrap(wem, samples)

    slots = [(ATLAS, make_atlas), (AMBIENCE, lambda wem: rewrap(wem, ambience(wem_rate(wem))))]
    for name, slot in MUSIC.items():
        slots.append((slot, lambda wem, name=name: rewrap(wem, sfx.resample(render_music(TRACKS[name]), wem_rate(wem)))))
    for (event, path, media_id), make in slots:
        full = os.path.join(OUT, path)
        blob = open(full, "rb").read()
        out = make(blob) if path.endswith(".wem") else rebank(blob, media_id, make)
        with open(full, "wb") as f:
            f.write(out)
        print("[audio] %-18s %s (%d KB)" % (event, path, len(out) // 1024))
    with open(os.path.join(OUT, "arpg_events.json"), "w", newline="\n") as f:
        json.dump({"atlas": ATLAS[0], "ambience": AMBIENCE[0], "music": {k: v[0] for k, v in MUSIC.items()},
                   "sounds": index}, f, indent=1)
    print("[audio] %d sounds, %d takes" % (len(index), sum(len(t) for t in index.values())))


if __name__ == "__main__":
    main()
