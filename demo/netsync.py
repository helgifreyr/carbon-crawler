from collections import defaultdict

import blue
import destiny
from destiny.net import client as dclient
from destiny.net import server as dserver


def to_wire(obj):
    return blue.marshal.Save(obj)


def from_wire(data):
    return blue.marshal.Load(data)


class Players(dserver.ClientInterestsInterface, dserver.CharacterInterestsInterface, dserver.BallInfoInterface):
    """Each connected client is one character that owns one ball and watches its bubble."""

    def __init__(self):
        self.ball_for_client = {}
        self._clients_for_ball = defaultdict(set)
        self._chars_for_ball = defaultdict(set)

    def add(self, client_id, own_ball):
        self.ball_for_client[client_id] = own_ball
        self.add_client_interest(own_ball, client_id)
        self.add_interest(own_ball, client_id)

    def remove(self, client_id):
        own_ball = self.ball_for_client.pop(client_id, None)
        if own_ball is not None:
            self.remove_client_interest(own_ball, client_id)
            self.remove_character_interest(own_ball, client_id)

    def add_client_interest(self, ball_id, client_id):
        self._clients_for_ball[ball_id].add(client_id)

    def get_all_interested_ball_ids(self):
        return [b for b, clients in self._clients_for_ball.items() if clients]

    def get_interested_client_ids_for_ball(self, ball_id):
        return list(self._clients_for_ball.get(ball_id, ()))

    def remove_client_interest(self, ball_id, client_id):
        self._clients_for_ball[ball_id].discard(client_id)

    def has_client_interest(self, ball_id):
        return bool(self._clients_for_ball.get(ball_id))

    def add_interest(self, ball_id, char_id):
        self._chars_for_ball[ball_id].add(char_id)

    def get_interested_character_ids_for_ball(self, ball_id):
        return list(self._chars_for_ball.get(ball_id, ()))

    def remove_character_interest(self, ball_id, character_id):
        self._chars_for_ball[ball_id].discard(character_id)

    def get_client_id_for_character(self, character_id):
        return character_id if character_id in self.ball_for_client else None

    def get_character_for_ball(self, ball_id):
        chars = self.get_characters_for_ball(ball_id)
        return chars[0] if chars else None

    def get_characters_for_ball(self, ball_id):
        return [c for c, owned in self.ball_for_client.items() if owned == ball_id]


class ServerSync:
    def __init__(self, park, send):
        self.park = park
        self.park.isMaster = True
        self.players = Players()
        self.network = _Network(send)
        self.actions = dserver.Actions(park)
        self.bubbles = dserver.BubbleUpdater(park)
        self.batcher = dserver.ParkUpdateBatcher(park, self.network, self.players, self.players, self.bubbles)
        self.ticker = dserver.Ticker(park, self.players, self.actions, self.batcher)
        self._joining = []

    def join(self, client_id, own_ball):
        self.players.add(client_id, own_ball)
        self._joining.append(client_id)

    def leave(self, client_id):
        self.players.remove(client_id)

    def pre_tick(self):
        # Actions are stamped currentTime + 1 and must go out before Evolve advances currentTime to match.
        self.ticker.tick()
        self.batcher.send_batch()

    def post_tick(self):
        for client_id in self._joining:
            self.batcher.send_full_state_update(client_id, self.players.ball_for_client[client_id])
        self._joining = []
        self.batcher.send_batch()

    def step(self):
        self.pre_tick()
        self.park.Evolve()
        self.post_tick()


class _Network(dserver.NetworkInterface):
    def __init__(self, send):
        self._send = send

    def singlecast(self, updates):
        for client_id, method, state, wait_for_bubble, _count in updates:
            self._send([client_id], (method, state, wait_for_bubble))

    def narrowcast(self, updates):
        for client_ids, method, state, wait_for_bubble, _count in updates:
            self._send(list(client_ids), (method, state, wait_for_bubble))


class _ClientCallbacks(dclient.ClientTickerInterface, dclient.TickErrorHandlerInterface):
    def __init__(self, on_desync, on_set_state):
        self.on_desync = on_desync
        self._on_set_state = on_set_state
        self.set_states = 0

    def set_ballpark(self, ballpark):
        pass

    def on_set_state(self):
        self.set_states += 1
        self._on_set_state()

    def on_ballpark_local_action(self, func_name, args):
        pass

    def should_log_actions(self):
        return False

    def get_ball_destruction_delay(self, ball, is_terminal=False):
        return 0

    def get_ball_destruction_delays(self, ball_ids, is_release=False):
        return {ball_id: 0 for ball_id in ball_ids}

    def clean_up_after_ball_removal(self, ball_id, ball, is_terminal=False):
        pass

    def clean_up_after_multiple_ball_removal(self, ball_ids, is_release=False):
        pass

    def on_fatal_desync(self):
        self.on_desync(fatal=True)

    def on_recoverable_desync(self):
        self.on_desync(fatal=False)


class _Ticker(dclient.Ticker):
    """destiny.net's client Ticker with its two catch-up constants made configurable."""

    max_future_ticks = 3
    catch_up_backlog = 1

    def do_pre_tick(self):
        # Same as destiny.net.client.Ticker.do_pre_tick (MIT, CCP ehf.), except the hardcoded 3 and 1.
        while len(self._history) > 0:
            state, wait_for_bubble = self._history[0]
            if wait_for_bubble:
                return
            event_stamp = state[0][0]
            if event_stamp > self._current_time and event_stamp - self._current_time < self.max_future_ticks:
                break
            self._real_flush_state(state)
            del self._history[0]
            if self._state_is_valid and self._should_rebase:
                self.store_state(mid_tick=True)
            if len(self._history) > self.catch_up_backlog:
                if self._history[0][1]:
                    return
                self._ballpark._parent_Evolve()


class ClientSync:
    def __init__(self, on_desync=lambda fatal: None, park=None, on_set_state=lambda: None):
        self.park = park if park is not None else destiny.Ballpark()
        self.callbacks = _ClientCallbacks(on_desync, on_set_state)
        self.ticker = _Ticker(self.callbacks, self.callbacks)
        self.ticker.set_ballpark(self.park)

    @property
    def synced(self):
        return self.callbacks.set_states > 0

    def receive(self, message):
        method, state, wait_for_bubble = message
        if method == "DoDestinyUpdate":
            self.ticker.update(state, wait_for_bubble)

    def pre_tick(self):
        self.ticker.do_pre_tick()

    def post_tick(self, stamp):
        self.ticker.do_post_tick(stamp)

    def step(self):
        was_synced = self.synced
        self.pre_tick()
        # A SetState already carries the server's post-Evolve tick, so don't evolve on the tick it lands.
        if was_synced:
            self.park._parent_Evolve()
            self.post_tick(self.park.currentTime)
