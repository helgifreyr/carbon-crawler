"""A computer-controlled mage that joins the game as an ordinary client and fights alongside the players.

It follows the nearest human, keeps clear of melee, casts whatever suits the moment and, between waves, walks
to the shrine to ready up; it spends its upgrades as soon as it has them. It is a plain network client: the server can't tell it apart."""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import blue

import carbonapp
from arpg_brain import Brain, NetActs
from arpg_state import ClientState
from net_client import NetClient

THINK_MS = 100
GIVE_UP_MS = 60000


class Companion:
    def __init__(self):
        self.client = NetClient()
        self.state = ClientState(collect_events=True)
        self.client.message_listeners.append(self.on_message)
        self.client.tick_listeners.append(self.on_tick)
        self.brain = Brain(self.client, self.state, NetActs(self.client), random.Random(int(os.environ.get("COMPANION_SEED", "4"))))

    def on_tick(self):
        self.state.apply_until(self.client.park.currentTime)
        for _, key, name, data in self.state.take_events():
            self.brain.warn(key, name, data)

    def on_message(self, message):
        if message[0] in ("state", "state_full"):
            self.state.receive(message)

    def run(self):
        start = blue.os.GetWallclockTimeNow()
        while not self.client.synced:
            if blue.os.TimeDiffInMs(start, blue.os.GetWallclockTimeNow()) > GIVE_UP_MS:
                print("[companion] no server - leaving")
                carbonapp.quit()
                return
            blue.synchro.SleepWallclock(50)
        print("[companion] joined as ball %d" % self.client.own_ball)
        # A companion only lives as long as its game: when the server goes away, so does it.
        while self.client.connected:
            blue.synchro.SleepWallclock(THINK_MS)
            self.brain.think()
        print("[companion] server gone - leaving")
        carbonapp.quit()


def main():
    carbonapp.spawn(Companion().run)


if __name__ == "__main__":
    carbonapp.run(main)
