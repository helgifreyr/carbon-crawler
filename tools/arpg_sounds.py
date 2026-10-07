"""Sound recipes for the ARPG: each takes a seeded rng and a pitch factor and returns mono samples at sfx.RATE."""
import numpy as np

from sfx import (bandpass, crackle, crush, drive, env, highpass, lowpass, mix, osc, room, steps, sweep, t_axis,
                 vibrato, white)

C4 = 261.63


def note(semitones):
    return C4 * 2 ** (semitones / 12.0)


def bolt(rng, p):
    d = 0.42
    whoosh = bandpass(white(d, rng), sweep(d, 700 * p, 3200 * p), 1.8) * env(d, 0.03, 0.02, 0.35, 2.0)
    body = osc("saw", sweep(d, 180 * p, 420 * p)) * env(d, 0.005, 0.0, 0.18, 2.5) * 0.35
    roar = lowpass(white(d, rng), 900) * env(d, 0.01, 0.05, 0.3) * 0.6
    return room(mix(whoosh, lowpass(body, 2500), roar, crackle(d, rng, 500, 0.25) * 0.4), 0.12)


def impact(rng, p):
    d = 0.5
    thump = osc("sine", sweep(d, 170 * p, 45 * p)) * env(d, 0.002, 0.0, 0.2, 2.0, punch=1.5)
    burst = lowpass(white(d, rng), sweep(d, 4500, 400)) * env(d, 0.001, 0.0, 0.12, 2.0) * 1.4
    return room(lowpass(drive(mix(thump, burst, crackle(d, rng, 900, 0.3) * 0.6), 2.0), sweep(d, 9000, 700)), 0.18)


def nova(rng, p):
    d = 1.0
    boom = osc("sine", sweep(d, 95 * p, 32 * p)) * env(d, 0.004, 0.02, 0.6, 2.2, punch=1.0)
    blast = lowpass(white(d, rng), sweep(d, 6000, 250)) * env(d, 0.002, 0.03, 0.7, 2.0) * 1.3
    ring = osc("triangle", vibrato(sweep(d, 640 * p, 380 * p), 9, 0.02)) * env(d, 0.01, 0.0, 0.5, 2.5) * 0.15
    return room(lowpass(drive(mix(boom, blast, ring, crackle(d, rng, 600, 0.5) * 0.5), 2.5), sweep(d, 8000, 300)), 0.25, 1.2)


def blink(rng, p):
    d = 0.38
    rise = osc("sine", vibrato(sweep(d, 320 * p, 2200 * p), 30, 0.04)) * env(d, 0.005, 0.0, 0.3, 1.5)
    shimmer = osc("triangle", steps(d, [note(24) * p, note(31) * p, note(28) * p, note(36) * p])) * env(d, 0.0, 0.05, 0.3) * 0.3
    air = highpass(white(d, rng), sweep(d, 1500, 6000)) * env(d, 0.02, 0.0, 0.25) * 0.25
    return room(mix(rise * 0.6, shimmer, air), 0.3, 1.3)


def chain(rng, p):
    d = 0.45
    jumps = np.repeat(rng.uniform(300, 1600, 24), int(d * 48000) // 24 + 1)[:int(d * 48000)] * p
    zap = crush(osc("square", jumps, duty=0.3), 5, 2) * env(d, 0.002, 0.05, 0.38, 1.5) * 0.5
    buzz = osc("saw", vibrato(np.full(int(d * 48000), 110 * p), 55, 0.3)) * env(d, 0.002, 0.08, 0.35) * 0.4
    sizzle = highpass(white(d, rng), 3500) * env(d, 0.001, 0.02, 0.3, 2.0) * 0.6
    return room(drive(mix(zap, lowpass(buzz, 3000), sizzle, crackle(d, rng, 1500, 0.35)), 1.6), 0.15)


def meteor_fall(rng, p):
    d = 0.8
    whistle = osc("sine", sweep(d, 1700 * p, 380 * p)) * env(d, 0.25, 0.4, 0.15, 1.0) * 0.4
    rush = bandpass(white(d, rng), sweep(d, 3000, 600), 1.2) * env(d, 0.4, 0.35, 0.05, 1.0)
    return room(mix(whistle, rush), 0.2)


def meteor(rng, p):
    d = 1.6
    sub = osc("sine", sweep(d, 75 * p, 24 * p)) * env(d, 0.003, 0.05, 1.0, 2.0, punch=1.2)
    blast = lowpass(white(d, rng), sweep(d, 7000, 150)) * env(d, 0.002, 0.05, 1.2, 2.2) * 1.6
    debris = crackle(d, rng, 700, 0.9) * 0.9
    rumble = lowpass(white(d, rng), 180) * env(d, 0.05, 0.3, 1.0) * 2.0
    return room(lowpass(drive(mix(sub, blast, debris, rumble), 3.0), sweep(d, 7000, 180)), 0.28, 1.4)


def frost(rng, p):
    d = 0.75
    hiss = bandpass(white(d, rng), sweep(d, 7000, 2500), 1.2) * env(d, 0.02, 0.1, 0.55, 1.8) * 0.8
    chimes = [osc("sine", np.full(int(d * 48000), note(n) * p)) * env(d, 0.002 + 0.04 * i, 0.0, 0.5 - 0.06 * i, 2.5)
              for i, n in enumerate((31, 38, 43, 47))]
    crack = crackle(d, rng, 900, 0.15) * 0.7
    return room(mix(hiss, *[c * 0.18 for c in chimes], crack), 0.35, 1.3)


def spit(rng, p):
    d = 0.3
    blob = osc("sine", sweep(d, 520 * p, 140 * p)) * env(d, 0.003, 0.0, 0.18, 2.0) * 0.7
    wet = lowpass(white(d, rng), sweep(d, 2400, 500)) * env(d, 0.002, 0.0, 0.12, 2.0)
    return room(mix(blob, wet), 0.1)


def swipe(rng, p):
    d = 0.24
    air = bandpass(white(d, rng), sweep(d, 3200 * p, 900 * p), 1.4) * env(d, 0.05, 0.0, 0.17, 1.6)
    return room(lowpass(air, 5000) * 0.7, 0.08)


def roll(rng, p):
    d = 0.36
    cloth = bandpass(white(d, rng), sweep(d, 1800 * p, 700 * p), 1.1) * env(d, 0.04, 0.05, 0.22, 1.4) * 0.55
    thump = osc("sine", sweep(d, 120 * p, 60 * p)) * env(d, 0.002, 0.0, 0.1, 2.0, punch=0.8) * 0.5
    scuff = lowpass(white(d, rng), 2200) * env(d, 0.12, 0.02, 0.16, 2.0) * 0.35
    return room(mix(cloth, thump, scuff), 0.08)


def fuse(rng, p):
    # A bloater about to go: a wet, swelling hiss.
    d = 0.9
    hiss = bandpass(white(d, rng), sweep(d, 1500, 4200), 1.4) * env(d, 0.2, 0.6, 0.08, 1.0) * 0.5
    gurgle = osc("sine", vibrato(sweep(d, 90 * p, 180 * p), 14, 0.25)) * env(d, 0.1, 0.6, 0.1, 1.2) * 0.4
    return room(mix(hiss, gurgle), 0.12)


def splat(rng, p):
    d = 0.9
    pop = osc("sine", sweep(d, 140 * p, 40 * p)) * env(d, 0.002, 0.0, 0.25, 2.0, punch=1.4)
    slosh = lowpass(white(d, rng), sweep(d, 3000, 300)) * env(d, 0.003, 0.05, 0.55, 2.0) * 1.2
    return room(lowpass(drive(mix(pop, slosh, crackle(d, rng, 400, 0.4) * 0.5), 2.0), 3500), 0.2)


def clang(rng, p):
    # A shot glancing off an iron shield.
    d = 0.6
    partials = [osc("sine", np.full(int(d * 48000), f * p)) * env(d, 0.001, 0.0, 0.45 - 0.08 * i, 2.5) * (0.4 - 0.08 * i)
                for i, f in enumerate((520, 1310, 2170, 3020))]
    tick = highpass(white(d, rng), 2500) * env(d, 0.001, 0.0, 0.03, 2.0) * 0.6
    return room(mix(*partials, tick), 0.15)


def gate(rng, p):
    # A portcullis moving: chain links rattling over a grinding rumble, ending on a heavy clunk.
    d = 1.8
    chain = bandpass(crackle(d, rng, 60, 0.9), 3200, 1.5) * env(d, 0.05, 1.2, 0.4, 1.0) * 1.6
    grind = lowpass(white(d, rng), 420) * env(d, 0.2, 1.1, 0.4, 1.0) * 0.9
    rumble = osc("saw", vibrato(np.full(int(d * 48000), 48 * p), 7, 0.08)) * env(d, 0.2, 1.1, 0.4, 1.0) * 0.25
    clunk = osc("sine", sweep(d, 95 * p, 40 * p)) * env(d, 0.002, 0.0, 0.3, 2.0, punch=1.5)
    clunk = np.concatenate([np.zeros(int(1.35 * 48000)), clunk[:int(0.45 * 48000)]])
    return room(lowpass(drive(mix(chain, grind, rumble, clunk), 1.6), 5000), 0.25)


def snarl(rng, p):
    # A hound winding up to charge: a rising, rasping growl.
    d = 0.75
    growl = osc("saw", vibrato(sweep(d, 70 * p, 120 * p), 22, 0.12)) * env(d, 0.05, 0.4, 0.25, 1.4)
    rasp = bandpass(white(d, rng), sweep(d, 500, 1400), 2.0) * env(d, 0.05, 0.4, 0.25, 1.4) * 0.6
    return room(lowpass(drive(mix(growl * 0.5, rasp), 1.8), 2400), 0.15)


def mend(rng, p):
    # A hollow rising chant over a breath of air: the shaman's mending.
    d = 0.9
    chant = osc("triangle", vibrato(sweep(d, note(-5) * p, note(2) * p), 5, 0.03)) * env(d, 0.08, 0.2, 0.5, 1.6) * 0.35
    fifth = osc("sine", vibrato(sweep(d, note(2) * p, note(9) * p), 5, 0.03)) * env(d, 0.12, 0.2, 0.45, 1.6) * 0.2
    air = bandpass(white(d, rng), sweep(d, 1200, 3400), 1.5) * env(d, 0.1, 0.1, 0.5, 1.4) * 0.3
    return room(mix(lowpass(chant, 2600), fifth, air), 0.35, 1.3)


def jump(rng, p):
    # A push-off whoosh, then the landing thud when the clip touches down (0.47 s in).
    d, land = 0.75, 0.47
    push = bandpass(white(d, rng), sweep(d, 900 * p, 2400 * p), 1.2) * env(d, 0.02, 0.0, 0.2, 1.8) * 0.4
    n = int(land * 48000)
    thud = np.zeros(int(d * 48000))
    tail = osc("sine", sweep(d - land, 110 * p, 50 * p)) * env(d - land, 0.002, 0.0, 0.12, 2.0, punch=1.0) * 0.6
    scuff = lowpass(white(d - land, rng), 1600) * env(d - land, 0.002, 0.0, 0.1, 2.0) * 0.5
    thud[n:n + len(tail)] = (tail + scuff)[:len(thud) - n]
    return room(mix(push, thud), 0.1)


def slam(rng, p):
    d = 1.0
    thud = osc("sine", sweep(d, 70 * p, 28 * p)) * env(d, 0.002, 0.03, 0.55, 2.0, punch=1.5)
    dirt = lowpass(white(d, rng), sweep(d, 1500, 120)) * env(d, 0.002, 0.04, 0.6, 2.0) * 1.5
    return room(lowpass(drive(mix(thud, dirt, crackle(d, rng, 300, 0.5) * 0.6), 3.0), sweep(d, 3500, 150)), 0.22, 1.2)


def death(rng, p):
    d = 0.7
    pitch = vibrato(sweep(d, 900 * p, 230 * p), 13, 0.05)
    squeal = bandpass(osc("saw", pitch), pitch * 1.5, 2.0) * env(d, 0.01, 0.05, 0.55, 1.5)
    growl = lowpass(osc("square", sweep(d, 130 * p, 70 * p), duty=0.4), 700) * env(d, 0.01, 0.1, 0.5) * 0.5
    return room(drive(mix(squeal, growl), 1.5), 0.15)


def hurt(rng, p):
    d = 0.28
    pitch = sweep(d, 230 * p, 150 * p)
    voice = bandpass(osc("saw", pitch), 750, 1.5) + bandpass(osc("saw", pitch), 1600, 3.0) * 0.4
    hit = lowpass(white(d, rng), 2000) * env(d, 0.0, 0.0, 0.05) * 0.6
    return room(mix(voice * env(d, 0.01, 0.03, 0.2, 1.5), hit), 0.1)


def _arpeggio(notes, d, kind, p, gap_fill=0.0):
    tones = []
    step = d / (len(notes) + 1.5)
    for i, n in enumerate(notes):
        tone = osc(kind, np.full(int((d - i * step) * 48000), note(n) * p)) * env(d - i * step, 0.004, 0.0,
                                                                                   step * 2.5 + gap_fill, 2.0)
        tones.append(np.concatenate([np.zeros(int(i * step * 48000)), tone]))
    return mix(*tones)


def pickup_health(rng, p):
    return room(lowpass(_arpeggio([12, 16, 19], 0.35, "triangle", p), 4000), 0.2)


def pickup_mana(rng, p):
    return room(lowpass(_arpeggio([19, 24, 28, 31], 0.35, "square", p) * 0.6, 3500), 0.25)


def levelup(rng, p):
    fanfare = _arpeggio([12, 16, 19, 24, 28], 0.9, "square", p, 0.2) * 0.5
    sparkle = highpass(white(0.9, rng), 6000) * env(0.9, 0.3, 0.2, 0.4) * 0.15
    return room(mix(lowpass(fanfare, 3200), sparkle), 0.3, 1.3)


def wave_start(rng, p):
    d = 1.6
    horn = mix(*[osc("saw", vibrato(np.full(int(d * 48000), note(n) * p), 5, 0.006)) for n in (-17, -10, -5)])
    return room(lowpass(horn, sweep(d, 400, 1600)) * env(d, 0.35, 0.6, 0.6, 1.5), 0.35, 1.5)


def wave_clear(rng, p):
    return room(lowpass(_arpeggio([7, 12, 16, 19, 24], 1.1, "triangle", p, 0.4), 4000), 0.35, 1.4)


def defeat(rng, p):
    return room(lowpass(_arpeggio([7, 3, 0, -5], 1.5, "saw", p, 0.6) * 0.6, 1400), 0.4, 1.5)


def roar(rng, p):
    d = 1.6
    pitch = vibrato(sweep(d, 95 * p, 62 * p), 7, 0.06)
    growl = lowpass(drive(osc("saw", pitch) + 0.5 * osc("square", pitch * 1.01, duty=0.4), 2.5), 900)
    breath = bandpass(white(d, rng), 600, 1.0) * 0.5
    return room(mix(growl, breath) * env(d, 0.15, 0.5, 0.9, 1.5), 0.3, 1.4)


RECIPES = {
    "cast": bolt, "impact": impact, "nova": nova, "blink": blink, "chain": chain, "meteor_fall": meteor_fall,
    "meteor": meteor, "frost": frost, "spit": spit, "swipe": swipe, "roll": roll, "jump": jump, "mend": mend, "snarl": snarl, "fuse": fuse, "splat": splat,
    "clang": clang, "gate": gate, "slam": slam, "death": death, "hurt": hurt,
    "pickup_health": pickup_health, "pickup_mana": pickup_mana, "levelup": levelup, "wave_start": wave_start,
    "wave_clear": wave_clear, "defeat": defeat, "roar": roar,
}
# One-off cues get a single take; frequent sounds get several so repeats don't sound identical.
VARIATIONS = {"roar": 1, "levelup": 1, "wave_start": 1, "wave_clear": 1, "defeat": 1, "meteor": 2, "nova": 2, "slam": 2}
