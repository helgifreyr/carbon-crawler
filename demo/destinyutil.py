def refresh_time_factors(park):
    # Ballpark caches exp(-friction*dt/mass) per ball, but changing tickInterval neither updates dt
    # (that happens on the next OnTick) nor those caches. Call this after the first tick at a new interval.
    for ball_id, ball in park.balls.items():
        if ball.isFree and ball.Agility > 0:
            park.SetBallAgility(ball_id, ball.Agility)
