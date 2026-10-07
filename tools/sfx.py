"""A small sfxr-style synthesizer: oscillators, slides, envelopes, swept filters, drive and a room reverb."""
import numpy as np
from scipy import signal

RATE = 48000


def t_axis(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def sweep(seconds, start, end, curve="exp"):
    """A per-sample frequency (or any parameter) curve from start to end."""
    u = np.linspace(0.0, 1.0, int(seconds * RATE), endpoint=False)
    if curve == "exp" and start > 0 and end > 0:
        return start * (end / start) ** u
    return start + (end - start) * u


def steps(seconds, values):
    """Holds each value for an equal share of the duration (arpeggios)."""
    n = int(seconds * RATE)
    idx = np.minimum((np.arange(n) * len(values)) // n, len(values) - 1)
    return np.asarray(values, dtype=float)[idx]


def osc(kind, freq, rng=None, duty=0.5):
    phase = np.cumsum(freq) / RATE
    frac = phase % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * phase)
    if kind == "square":
        return np.where(frac < duty, 1.0, -1.0)
    if kind == "saw":
        return 2.0 * frac - 1.0
    if kind == "triangle":
        return 4.0 * np.abs(frac - 0.5) - 1.0
    if kind == "noise":
        # sfxr noise: a new random value every half cycle, so the pitch curve colours the noise.
        rng = rng or np.random.default_rng(0)
        cells = np.floor(phase * 2.0).astype(np.int64)
        values = rng.uniform(-1.0, 1.0, cells.max() + 2)
        return values[cells - cells.min()]
    raise ValueError(kind)


def white(seconds, rng):
    return rng.uniform(-1.0, 1.0, int(seconds * RATE))


def vibrato(freq, rate_hz, depth):
    t = np.arange(len(freq)) / RATE
    return freq * (1.0 + depth * np.sin(2 * np.pi * rate_hz * t))


def env(n_or_seconds, attack=0.005, hold=0.0, decay=0.2, curve=3.0, punch=0.0):
    """Attack, hold, then a power-law decay to silence over the remaining time; punch boosts the first moments."""
    n = n_or_seconds if isinstance(n_or_seconds, int) else int(n_or_seconds * RATE)
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0.0, 1.0)
    d = np.clip(1.0 - (t - attack - hold) / max(decay, 1e-4), 0.0, 1.0) ** curve
    e = np.where(t < attack + hold, a, d)
    if punch:
        e = e * (1.0 + punch * np.exp(-t / 0.03))
    return e


def _swept(x, cutoff, kind, q=0.7, block=256):
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    out = np.empty_like(x)
    zi = None
    for start in range(0, len(x), block):
        stop = min(len(x), start + block)
        fc = float(np.clip(cutoff[start], 20.0, RATE * 0.45))
        if kind == "band":
            bw = fc / max(q, 0.1)
            lo, hi = max(20.0, fc - bw / 2), min(RATE * 0.45, fc + bw / 2)
            b, a = signal.butter(2, [lo, hi], btype="band", fs=RATE)
        else:
            b, a = signal.butter(2, fc, btype=kind, fs=RATE)
        if zi is None or len(zi) != max(len(a), len(b)) - 1:
            zi = signal.lfilter_zi(b, a) * x[start]
        out[start:stop], zi = signal.lfilter(b, a, x[start:stop], zi=zi)
    return out


def lowpass(x, cutoff):
    return _swept(x, cutoff, "low")


def highpass(x, cutoff):
    return _swept(x, cutoff, "high")


def bandpass(x, center, q=1.5):
    return _swept(x, center, "band", q)


def drive(x, amount):
    return np.tanh(x * amount) / np.tanh(amount)


def crush(x, bits=6, hold=3):
    steps_ = 2 ** bits
    y = np.round(x * steps_) / steps_
    return np.repeat(y[::hold], hold)[:len(x)]


def crackle(seconds, rng, density=300.0, decay_s=0.3):
    n = int(seconds * RATE)
    x = np.zeros(n)
    hits = rng.random(n) < density / RATE
    x[hits] = rng.uniform(-1.0, 1.0, hits.sum())
    t = np.arange(n) / RATE
    return lowpass(highpass(x, 1200.0), 6500.0) * 3.0 * np.exp(-t / decay_s) * (1.0 - t / seconds) ** 2


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def room(x, wet=0.18, size=1.0, damp=3500.0, feedback=1.0, tail_s=None):
    """A Schroeder reverb: four combs into two allpasses; size scales the delays, feedback the decay."""
    tail = int((tail_s if tail_s is not None else 0.6 * size) * RATE)
    dry = np.concatenate([x, np.zeros(tail)])
    acc = np.zeros_like(dry)
    for delay_ms, fb in ((29.7, 0.77), (37.1, 0.74), (41.1, 0.72), (43.7, 0.7)):
        d = int(delay_ms * size * RATE / 1000.0)
        a = np.zeros(d + 1)
        a[0], a[d] = 1.0, -min(0.95, fb * feedback)
        acc += signal.lfilter([1.0], a, dry)
    acc = lowpass(acc / 4.0, damp)
    for delay_ms, g in ((5.0, 0.7), (1.7, 0.7)):
        d = int(delay_ms * RATE / 1000.0)
        b = np.zeros(d + 1)
        a = np.zeros(d + 1)
        b[0], b[d], a[0], a[d] = -g, 1.0, 1.0, -g
        acc = signal.lfilter(b, a, acc)
    return dry * (1.0 - wet) + acc * wet


def finish(x, peak=0.85, fade_ms=4.0, tail_db=-60.0):
    """Normalise, trim trailing near-silence and fade the ends so slots never click."""
    x = np.asarray(x, dtype=float)
    top = np.abs(x).max() or 1.0
    x = x / top * peak
    loud = np.nonzero(np.abs(x) > peak * 10 ** (tail_db / 20.0))[0]
    if len(loud):
        x = x[:loud[-1] + 1]
    n = max(1, int(fade_ms * RATE / 1000.0))
    ramp = np.linspace(0.0, 1.0, min(n, len(x)))
    x[:len(ramp)] *= ramp
    x[len(x) - len(ramp):] *= ramp[::-1]
    return x


def resample(x, rate):
    if rate == RATE:
        return x
    return signal.resample_poly(x, rate, RATE)
