import math


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def look_rotation(direction):
    """Quaternion turning the model's forward (+Z) onto direction."""
    n = math.sqrt(sum(c * c for c in direction)) or 1.0
    dx, dy, dz = (c / n for c in direction)
    # Rotation axis is +Z x d, angle is acos(d.z).
    ax, ay = -dy, dx
    s = math.hypot(ax, ay)
    if s < 1e-6:
        return (0.0, 0.0, 0.0, 1.0) if dz > 0 else (0.0, 1.0, 0.0, 0.0)
    return axis_quat((ax / s, ay / s, 0.0), math.acos(max(-1.0, min(1.0, dz))))


def axis_quat(axis, angle):
    s = math.sin(angle / 2.0)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0))
