import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import blue
import destiny

import carbonapp
from net_client import NetClient
from stats import Samples

RUN_SECONDS = float(os.environ.get("BOT_RUN_SECONDS", "20"))
COMMAND_EVERY_MS = int(os.environ.get("BOT_COMMAND_MS", "600"))
REPORT_EVERY_MS = int(os.environ.get("BOT_REPORT_MS", "5000"))
SEED = int(os.environ.get("BOT_SEED", "1"))
CAST = os.environ.get("BOT_CAST") == "1"
GOTO_RANGE = float(os.environ.get("BOT_GOTO_RANGE", "800"))


def wait_for_mode(client, mode, timeout_ms=3000):
    start = blue.os.GetWallclockTimeNow()
    while True:
        ball = client.park.balls.get(client.own_ball)
        if ball is not None and ball.mode == mode:
            return blue.os.TimeDiffInUs(start, blue.os.GetWallclockTimeNow()) / 1000.0
        if blue.os.TimeDiffInMs(start, blue.os.GetWallclockTimeNow()) > timeout_ms:
            return None
        blue.synchro.Yield()


def command_loop(client, rng, input_latency):
    while not client.synced:
        blue.synchro.SleepWallclock(50)
    while True:
        client.send("stop")
        wait_for_mode(client, destiny.DSTBALL_STOP)
        blue.synchro.SleepWallclock(COMMAND_EVERY_MS // 2)
        client.send("goto", rng.uniform(-GOTO_RANGE, GOTO_RANGE), 0.0, rng.uniform(-GOTO_RANGE, GOTO_RANGE))
        latency = wait_for_mode(client, destiny.DSTBALL_GOTO)
        if latency is not None:
            input_latency.add(latency)
        blue.synchro.SleepWallclock(COMMAND_EVERY_MS)
        if CAST:
            for _ in range(3):
                tx, tz = rng.uniform(-GOTO_RANGE, GOTO_RANGE), rng.uniform(-GOTO_RANGE, GOTO_RANGE)
                ball = client.park.balls.get(client.own_ball)
                if ball is not None:
                    client.send("aim", math.atan2(tx - ball.x, tz - ball.z))
                client.send("cast", tx, tz)
                blue.synchro.SleepWallclock(100)
            if ball is not None and rng.random() < 0.3:
                client.send("nova")
            client.send("pick", rng.randrange(3))
            if ball is not None and rng.random() < 0.3:
                client.send("blink", ball.x + rng.uniform(-6, 6), ball.z + rng.uniform(-6, 6))


def main():
    client = NetClient()
    rng = random.Random(SEED)
    input_latency = Samples()
    carbonapp.spawn(command_loop, client, rng, input_latency)
    elapsed, travelled, last = 0, 0.0, None
    while elapsed < RUN_SECONDS * 1000:
        blue.synchro.SleepWallclock(100)
        elapsed += 100
        ball = client.park.balls.get(client.own_ball) if client.synced else None
        if ball is not None:
            pos = (ball.x, ball.y, ball.z)
            if last is not None:
                travelled += sum((a - b) ** 2 for a, b in zip(pos, last)) ** 0.5
            last = pos
        if elapsed % REPORT_EVERY_MS == 0:
            print("[bot %s] %s  input latency p50 %.1f p95 %.1f ms (n=%d)  own ball travelled %.0f m" % (
                client.client_id, client.status(), input_latency.percentile(0.5), input_latency.percentile(0.95),
                len(input_latency), travelled))
    carbonapp.quit()


if __name__ == "__main__":
    carbonapp.run(main, frame_time_ms=5)
