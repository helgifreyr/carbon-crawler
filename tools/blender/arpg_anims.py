import math

from arpg_rig import Clip, X, Y, Z, curve

# Blender axes: +X rotation pitches a bone's tip toward the front (-Y) when it points up and toward the back when
# it hangs down; +Z yaws the front toward +X; +Y rolls the top toward +X.
TAU = 2 * math.pi


def mage_idle(t):
    s = math.sin(TAU * t)
    return {"spine": [(X, 0.03 * s)], "head": [(X, -0.03 * s), (Z, 0.04 * math.sin(TAU * t + 1.0))],
            "arm_f": [(X, 0.06 * s)], "forearm_f": [(X, -0.15)], "arm_s": [(Y, 0.02 * s)],
            "hem": [(Y, 0.015 * s)], "root_loc": (0, 0, 0.008 * (1 + s))}


def mage_walk(t):
    p = TAU * t
    s = math.sin(p)
    return {"root_loc": (0, 0, 0.045 * (1 - math.cos(2 * p)) / 2),
            "hem": [(Y, 0.14 * s), (X, 0.07 * math.sin(2 * p))],
            "spine": [(Z, 0.08 * s), (Y, -0.04 * s), (X, 0.04)],
            "head": [(Z, -0.06 * s)],
            "arm_f": [(X, 0.5 * s)], "forearm_f": [(X, -0.25 - 0.2 * max(0.0, -s))],
            "arm_s": [(X, -0.18 * s)], "forearm_s": [(X, -0.08 * s)]}


# The bolt appears almost at once, so the thrust peaks early (CAST_RELEASE) and is held while it flies off.
CAST_RELEASE = 0.15


def mage_cast(t):
    # The hand pushes forward a little while the wrist tips the staff head down toward the target.
    r = CAST_RELEASE
    return {"arm_s": [(X, curve(t, [(0.0, 0.0), (0.06, -0.3), (r, -0.7), (0.45, -0.65), (1.0, 0.0)]))],
            "forearm_s": [(X, curve(t, [(0.0, 0.0), (0.06, -0.3), (r, 1.25), (0.45, 1.1), (1.0, 0.0)]))],
            "spine": [(X, curve(t, [(0.0, 0.0), (0.06, -0.1), (r, 0.16), (0.45, 0.12), (1.0, 0.0)])),
                      (Z, curve(t, [(0.0, 0.0), (0.06, 0.12), (r, -0.1), (0.45, -0.08), (1.0, 0.0)]))],
            "arm_f": [(X, curve(t, [(0.0, 0.0), (0.06, -0.3), (r, -0.9), (0.45, -0.8), (1.0, 0.0)]))],
            "hem": [(X, curve(t, [(0.0, 0.0), (r, -0.1), (1.0, 0.0)]))]}


def mage_death(t):
    fall = curve(t, [(0.0, 0.0), (0.15, 0.12), (1.0, -1.42)])
    return {"root": [(X, fall)], "root_loc": (0, 0, curve(t, [(0.0, 0.0), (0.2, 0.05), (1.0, 0.4)])),
            "arm_f": [(X, curve(t, [(0.0, 0.0), (0.5, -1.5), (1.0, -0.6)]))],
            "arm_s": [(X, curve(t, [(0.0, 0.0), (0.5, -1.1), (1.0, -0.4)])), (Y, curve(t, [(0.0, 0.0), (1.0, 0.5)]))],
            "head": [(X, curve(t, [(0.0, 0.0), (0.4, -0.3), (1.0, 0.25)]))],
            "hem": [(X, curve(t, [(0.0, 0.0), (1.0, 0.3)]))]}


# Rolling about the root (at the feet) would swing the body round a point on the floor, so the root also slides to
# keep the pivot at the hips, a little lifted mid-roll; the spine and arms tuck in so the staff stays clear.
ROLL_PIVOT = 0.5


def mage_roll(t):
    a = curve(t, [(0.0, 0.0), (0.15, 0.3), (0.85, TAU - 0.3), (1.0, TAU)])
    tuck = curve(t, [(0.0, 0.0), (0.2, 1.0), (0.8, 1.0), (1.0, 0.0)])
    h, lift = ROLL_PIVOT, 0.45 * math.sin(math.pi * t)
    return {"root": [(X, a)], "root_loc": (0, h * math.sin(a), h - h * math.cos(a) + lift - 0.2 * tuck),
            "spine": [(X, 1.0 * tuck)], "head": [(X, 0.7 * tuck)],
            "arm_s": [(X, -0.9 * tuck), (Y, -0.3 * tuck)], "forearm_s": [(X, 1.3 * tuck)],
            "arm_f": [(X, -1.1 * tuck)], "forearm_f": [(X, -0.8 * tuck)],
            "hem": [(X, 0.8 * tuck)]}


# The jump's height is in the clip, so the body rises while the placeable (and its blob shadow) stays on the floor.
JUMP_HEIGHT, TAKEOFF, LANDING = 0.75, 0.12, 0.86


def mage_jump(t):
    air = (t - TAKEOFF) / (LANDING - TAKEOFF)
    lift = JUMP_HEIGHT * math.sin(math.pi * air) if 0.0 < air < 1.0 else 0.0
    dip = curve(t, [(0.0, 0.0), (0.08, -0.1), (TAKEOFF, 0.0), (LANDING, 0.0), (0.93, -0.09), (1.0, 0.0)])
    tuck = curve(t, [(0.0, 0.0), (TAKEOFF, 0.2), (0.45, 1.0), (0.7, 0.8), (LANDING, 0.1), (1.0, 0.0)])
    return {"root_loc": (0, 0, lift + dip), "spine": [(X, 0.25 * tuck - 0.6 * dip)], "head": [(X, -0.15 * tuck)],
            "arm_f": [(X, -1.2 * tuck), (Y, 0.3 * tuck)], "forearm_f": [(X, -0.5 * tuck)],
            "arm_s": [(X, -0.5 * tuck)], "forearm_s": [(X, 0.4 * tuck)], "hem": [(X, 0.35 * tuck)]}


MAGE_CLIPS = [
    Clip("idle", 32, 16, True, mage_idle),
    Clip("walk", 20, 38, True, mage_walk, stride=3.6),
    Clip("cast", 14, 30, False, mage_cast, events={"release": CAST_RELEASE}),
    Clip("death", 24, 30, False, mage_death),
    Clip("roll", 18, 40, False, mage_roll),
    Clip("jump", 22, 40, False, mage_jump),
]


def tail(p, amount):
    return {"tail1": [(Z, amount * math.sin(p))], "tail2": [(Z, amount * 1.3 * math.sin(p - 0.8))],
            "tail3": [(Z, amount * 1.6 * math.sin(p - 1.6)), (X, 0.1 * math.sin(p))]}


def imp_idle(t):
    p = TAU * t
    s = math.sin(p)
    pose = {"chest": [(X, 0.08 + 0.04 * s)], "head": [(X, -0.05 * s), (Z, 0.08 * math.sin(p * 0.5 * 2 + 0.7))],
            "arm.p": [(X, 0.05 * s)], "arm.n": [(X, 0.05 * s)],
            "forearm.p": [(X, -0.15)], "forearm.n": [(X, -0.15)],
            "root_loc": (0, 0, -0.01 * (1 + s))}
    pose.update(tail(p, 0.07))
    return pose


def imp_walk(t):
    p = TAU * t
    s = math.sin(p)
    pose = {"root_loc": (0, 0, 0.035 * (1 - math.cos(2 * p)) / 2),
            "pelvis": [(Y, 0.09 * s)],
            "chest": [(X, 0.14), (Z, -0.12 * s), (Y, -0.05 * s)],
            "head": [(Z, 0.08 * s), (X, -0.08)]}
    for side, phase in ((".p", 0.0), (".n", math.pi)):
        leg = math.sin(p + phase)
        lift = max(0.0, -math.cos(p + phase))
        pose["thigh" + side] = [(X, 0.55 * leg)]
        pose["shin" + side] = [(X, 0.55 * lift)]
        pose["foot" + side] = [(X, -0.35 * lift)]
        pose["arm" + side] = [(X, -0.45 * leg)]
        pose["forearm" + side] = [(X, -0.3 - 0.2 * lift)]
    pose.update(tail(p + 0.5, 0.22))
    return pose


def imp_attack(t):
    # A two-handed pounce: rear back with both claws up, lunge forward and rake down, recover. No twisting, so it
    # reads as an attack from above.
    rear, strike = 0.4, 0.55
    arm = curve(t, [(0.0, 0.0), (rear, -2.3), (strike, -0.3), (0.75, -0.5), (1.0, 0.0)])
    forearm = curve(t, [(0.0, -0.15), (rear, -1.1), (strike, -0.1), (1.0, -0.15)])
    pose = {"chest": [(X, curve(t, [(0.0, 0.1), (rear, -0.35), (strike, 0.55), (0.75, 0.4), (1.0, 0.1)]))],
            "head": [(X, curve(t, [(0.0, 0.0), (rear, 0.25), (strike, -0.25), (1.0, 0.0)]))],
            "pelvis": [(X, curve(t, [(0.0, 0.0), (rear, -0.15), (strike, 0.2), (1.0, 0.0)]))],
            "root_loc": (0, curve(t, [(0.0, 0.0), (rear, 0.12), (strike, -0.35), (0.75, -0.3), (1.0, 0.0)]),
                         curve(t, [(0.0, 0.0), (rear, 0.06), (strike, -0.02), (1.0, 0.0)]))}
    for side in (".p", ".n"):
        pose["arm" + side] = [(X, arm)]
        pose["forearm" + side] = [(X, forearm)]
        pose["thigh" + side] = [(X, curve(t, [(0.0, 0.0), (rear, 0.2), (strike, -0.45), (1.0, 0.0)]))]
        pose["shin" + side] = [(X, curve(t, [(0.0, 0.0), (rear, 0.3), (strike, 0.1), (1.0, 0.0)]))]
    pose.update(tail(TAU * t, 0.25))
    pose["tail1"].append((X, curve(t, [(0.0, 0.0), (rear, -0.4), (strike, 0.3), (1.0, 0.0)])))
    return pose


def imp_death(t):
    topple = curve(t, [(0.0, 0.0), (0.2, -0.15), (1.0, 1.45)])
    pose = {"root": [(Y, topple)], "root_loc": (0, 0, curve(t, [(0.0, 0.0), (1.0, 0.32)])),
            "chest": [(X, curve(t, [(0.0, 0.1), (0.3, -0.35), (1.0, 0.3)]))],
            "head": [(X, curve(t, [(0.0, 0.0), (0.3, -0.5), (1.0, 0.45)]))],
            "tail1": [(Z, curve(t, [(0.0, 0.0), (1.0, 0.4)]))], "tail2": [(Z, curve(t, [(0.0, 0.0), (1.0, 0.3)]))]}
    for side in (".p", ".n"):
        pose["thigh" + side] = [(X, curve(t, [(0.0, 0.0), (1.0, -0.6)]))]
        pose["shin" + side] = [(X, curve(t, [(0.0, 0.0), (1.0, 0.8)]))]
        pose["arm" + side] = [(X, curve(t, [(0.0, 0.0), (0.4, -1.2), (1.0, -0.4)]))]
    return pose


def hound_tail(p, amount):
    return {"tail1": [(Z, amount * math.sin(p)), (X, -0.15)], "tail2": [(Z, amount * 1.4 * math.sin(p - 0.9))]}


def hound_idle(t):
    p = TAU * t
    s = math.sin(p)
    pose = {"chest": [(X, 0.03 * s)], "neck": [(X, -0.04 * s)], "head": [(Z, 0.1 * math.sin(p + 0.6))],
            "jaw": [(X, 0.08 + 0.05 * s)], "root_loc": (0, 0, -0.008 * (1 + s))}
    pose.update(hound_tail(p, 0.25))
    return pose


def hound_walk(t):
    # A trot: diagonal pairs of legs swing together (front left with hind right).
    p = TAU * t
    pose = {"root_loc": (0, 0, 0.03 * (1 - math.cos(2 * p)) / 2), "chest": [(X, 0.03 * math.sin(2 * p))],
            "neck": [(X, -0.05 * math.sin(2 * p))], "jaw": [(X, 0.12)]}
    for side, front_phase, hind_phase in ((".p", 0.0, math.pi), (".n", math.pi, 0.0)):
        for leg, phase in (("front", front_phase), ("hind", hind_phase)):
            swing = math.sin(p + phase)
            lift = max(0.0, -math.cos(p + phase))
            if leg == "front":
                pose["upper" + side] = [(X, 0.5 * swing)]
                pose["lower" + side] = [(X, 0.9 * lift)]
                pose["paw" + side] = [(X, 0.5 * lift)]
            else:
                pose["thigh" + side] = [(X, 0.45 * swing)]
                pose["shin" + side] = [(X, -0.6 * lift)]
                pose["foot" + side] = [(X, 0.6 * lift)]
    pose.update(hound_tail(p, 0.18))
    return pose


def hound_attack(t):
    # A bite: rock back on the haunches, lunge with the jaws open, snap shut, recover.
    rear, strike = 0.35, 0.55
    pose = {"root_loc": (0, curve(t, [(0.0, 0.0), (rear, 0.1), (strike, -0.25), (0.8, -0.2), (1.0, 0.0)]),
                         curve(t, [(0.0, 0.0), (rear, -0.03), (strike, 0.04), (1.0, 0.0)])),
            "chest": [(X, curve(t, [(0.0, 0.0), (rear, -0.15), (strike, 0.1), (1.0, 0.0)]))],
            "neck": [(X, curve(t, [(0.0, 0.0), (rear, -0.3), (strike, 0.25), (1.0, 0.0)]))],
            "head": [(X, curve(t, [(0.0, 0.0), (rear, -0.2), (strike, 0.2), (1.0, 0.0)]))],
            "jaw": [(X, curve(t, [(0.0, 0.1), (rear, 0.3), (0.5, 0.75), (strike + 0.05, 0.05), (1.0, 0.1)]))]}
    for side in (".p", ".n"):
        pose["upper" + side] = [(X, curve(t, [(0.0, 0.0), (rear, 0.2), (strike, -0.55), (1.0, 0.0)]))]
        pose["lower" + side] = [(X, curve(t, [(0.0, 0.0), (rear, 0.3), (strike, 0.1), (1.0, 0.0)]))]
        pose["thigh" + side] = [(X, curve(t, [(0.0, 0.0), (rear, -0.3), (strike, 0.35), (1.0, 0.0)]))]
    pose.update(hound_tail(TAU * t, 0.2))
    return pose


def hound_charge(t):
    # The wind-up before a charge: crouched low, hind legs coiled, head down, quivering.
    k = curve(t, [(0.0, 0.0), (0.25, 1.0), (1.0, 1.0)])
    shake = 0.04 * math.sin(TAU * 9 * t) * k
    pose = {"root_loc": (0, 0.06 * k, -0.1 * k), "chest": [(X, 0.12 * k), (Z, shake)], "neck": [(X, 0.3 * k)],
            "head": [(X, -0.25 * k)], "jaw": [(X, 0.35 * k + shake)], "tail1": [(X, -0.5 * k), (Z, shake * 2)],
            "tail2": [(X, -0.3 * k)]}
    for side in (".p", ".n"):
        pose["upper" + side] = [(X, -0.25 * k)]
        pose["lower" + side] = [(X, 0.35 * k)]
        pose["thigh" + side] = [(X, -0.45 * k)]
        pose["shin" + side] = [(X, 0.5 * k)]
        pose["foot" + side] = [(X, -0.2 * k)]
    return pose


def hound_death(t):
    topple = curve(t, [(0.0, 0.0), (0.2, -0.1), (1.0, 1.5)])
    pose = {"root": [(Y, topple)], "root_loc": (0, 0, curve(t, [(0.0, 0.0), (1.0, 0.22)])),
            "neck": [(X, curve(t, [(0.0, 0.0), (0.3, -0.4), (1.0, 0.2)]))],
            "jaw": [(X, curve(t, [(0.0, 0.1), (0.4, 0.6), (1.0, 0.3)]))],
            "tail1": [(Z, curve(t, [(0.0, 0.0), (1.0, 0.5)]))]}
    for side in (".p", ".n"):
        pose["upper" + side] = [(X, curve(t, [(0.0, 0.0), (1.0, -0.5)]))]
        pose["thigh" + side] = [(X, curve(t, [(0.0, 0.0), (1.0, 0.4)]))]
    return pose


HOUND_CLIPS = [
    Clip("idle", 32, 16, True, hound_idle),
    Clip("walk", 16, 32, True, hound_walk, stride=2.0),
    Clip("attack", 16, 32, False, hound_attack),
    Clip("charge", 20, 32, False, hound_charge),
    Clip("death", 24, 30, False, hound_death),
]


IMP_CLIPS = [
    Clip("idle", 32, 16, True, imp_idle),
    Clip("walk", 16, 32, True, imp_walk, stride=2.2),
    Clip("attack", 16, 32, False, imp_attack),
    Clip("death", 24, 30, False, imp_death),
]
