import os
import sys
import types

import blue

TICKS_PER_SECOND = 10_000_000
_exit_hooks = []


def spawn(fn, *args, **kwargs):
    return blue.pyos.CreateTasklet(fn, args, kwargs)


def at_exit(fn):
    _exit_hooks.append(fn)


def quit(code=0):
    for fn in reversed(_exit_hooks):
        try:
            fn()
        except Exception:
            sys.excepthook(*sys.exc_info())
    sys.stdout.flush()
    sys.stderr.flush()
    blue.os.Terminate(code)


def frames():
    last = blue.os.GetSimTime()
    while True:
        blue.synchro.Yield()
        now = blue.os.GetSimTime()
        yield (now - last) / TICKS_PER_SECOND
        last = now


def run(main, frame_time_ms=0):
    # Under /py the script owns the process; this hands the frame loop to Blue's C++ main loop,
    # which pumps window messages and calls autoexec.run() once before the first frame.
    blue.os.desiredFrameTimeMilliseconds = frame_time_ms or int(os.environ.get("CARBON_FRAME_MS", "0"))
    sys.modules["autoexec"] = types.SimpleNamespace(run=lambda: spawn(main))
    blue.os.StacklessMain()
