import math

import arpg_world as world
from arpg_game.components import Player

MOVES = ("goto", "dir", "stop")


def apply(g, ball_id, message):
    actions = g.sync.actions
    if message[0] == "goto":
        actions.go_to_point(ball_id, message[1], 0.0, message[3])
    elif message[0] == "dir":
        actions.go_to_direction(ball_id, message[1], 0.0, message[2])
    else:
        actions.stop(ball_id)


def move(g, ball_id, message):
    """Applies a movement command, or holds it until a roll in progress ends; returns the tick it applies on."""
    player = g.ents.get(ball_id, Player)
    if player is not None and g.park.currentTime < player.roll_until:
        player.queued = message
        return player.roll_until + 1
    apply(g, ball_id, message)
    return g.sync.actions._stamp_for_system


def roll(g, ball_id, dx, dz):
    player = g.ents.get(ball_id, Player)
    now = g.park.currentTime
    length = math.hypot(dx, dz)
    if player is None or now < player.roll_ready or now < player.jump_until or length < 1e-6:
        return
    dx, dz = dx / length, dz / length
    g.sync.actions.set_max_speed(ball_id, world.ROLL["speed"])
    g.sync.actions.go_to_direction(ball_id, dx, 0.0, dz)
    player.roll_until = now + g.ticks_for(world.ROLL["s"])
    player.roll_ready = now + g.ticks_for(world.ROLL["cooldown_s"])
    player.queued = None
    g.stats["rolls"] += 1
    g.state.event(ball_id, "roll", dir=(dx, dz))


def jump(g, ball_id):
    player = g.ents.get(ball_id, Player)
    now = g.park.currentTime
    if player is None or now < player.jump_ready or now < player.roll_until:
        return
    player.jump_until = now + g.ticks_for(world.JUMP["s"])
    player.jump_ready = now + g.ticks_for(world.JUMP["s"] + world.JUMP["cooldown_s"])
    g.stats["jumps"] += 1
    g.state.event(ball_id, "jump")


def update_rolls(g):
    """Ends rolls that have run their time: back to walking speed, then whatever movement came in meanwhile."""
    now = g.park.currentTime
    for ball_id, player in g.ents.each(Player):
        if player.roll_until and now >= player.roll_until:
            player.roll_until = 0
            g.sync.actions.set_max_speed(ball_id, world.PLAYER_SPEED)
            queued, player.queued = player.queued, None
            if queued is not None and g.alive(ball_id):
                apply(g, ball_id, queued)
