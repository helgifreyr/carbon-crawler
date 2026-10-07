import time
from collections import deque


class Samples:
    def __init__(self, keep=2000):
        self.values = deque(maxlen=keep)

    def add(self, value):
        self.values.append(value)

    def percentile(self, p):
        if not self.values:
            return float("nan")
        ordered = sorted(self.values)
        return ordered[min(len(ordered) - 1, int(p * len(ordered)))]

    def clear(self):
        self.values.clear()

    def __len__(self):
        return len(self.values)


class TickTimer:
    def __init__(self):
        self.costs_ms = Samples()
        self._start = None

    def begin(self):
        self._start = time.perf_counter()

    def end(self):
        if self._start is not None:
            self.costs_ms.add((time.perf_counter() - self._start) * 1000.0)
            self._start = None
