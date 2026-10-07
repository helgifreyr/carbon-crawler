COLORS = {
    "anchor": (1.0, 0.8, 0.0),
    "orbiter": (1.0, 0.63, 0.0),
    "traveller": (0.0, 0.62, 0.18),
    "follower": (0.9, 0.16, 0.22),
}

BALL_MASS = 13000000.0
AGILITY = 0.9
SPEED_FRACTION = 0.95


def add_ball(park, object_id, x=0.0, y=0.0, z=0.0, max_velocity=10.0, radius=2.0,
             is_free=True, is_global=False, is_massive=True, is_interactive=False, is_space_junk=False,
             mass=BALL_MASS, agility=AGILITY):
    ball = park.AddBall(
        object_id, mass, radius, max_velocity,
        is_free, is_global, is_massive, is_interactive, is_space_junk,
        x, y, z, 0.0, 0.0, 0.0,
        agility, SPEED_FRACTION,
    )
    park.SetBallFree(ball.id, True)
    ball.maxVelocity = max_velocity
    ball.Agility = agility
    ball.speedFraction = SPEED_FRACTION
    return ball


def build_scene(park):
    anchor = add_ball(park, 1, max_velocity=0.0, radius=20.0)
    orbiter = add_ball(park, 2, x=200.0)
    traveller = add_ball(park, 3, x=-300.0, z=-300.0, max_velocity=15.0)
    follower = add_ball(park, 4, x=300.0, z=300.0, max_velocity=12.0)

    park.Orbit(orbiter.id, anchor.id, 150.0)
    park.GotoPoint(traveller.id, 300.0, 0.0, -300.0)
    park.FollowBall(follower.id, traveller.id)

    return {"anchor": anchor, "orbiter": orbiter, "traveller": traveller, "follower": follower}
