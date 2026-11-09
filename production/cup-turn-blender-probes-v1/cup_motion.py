"""Deterministic cup/hand blocking; stdlib only, no Blender import or rendering."""
import math

DURATION = 6.0
FPS = 30
FILM_START_SECONDS = 3.80
HALF_HEIGHT = 0.39
RADIUS = 0.42
LIFT_Z = 1.08
GRIP_START = 1.55
SET_DOWN = 3.95


def smooth(t, a, b):
    u = min(1.0, max(0.0, (t-a)/(b-a)))
    return u*u*u*(10+u*(-15+6*u))


def lerp(a, b, u):
    return a+(b-a)*u


def rotate_x(point, angle):
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return x, y*c-z*s, y*s+z*c


def pose(t):
    """The hand rig shares the cup's transform ONLY through supported transfer.

    Finger opening is separate; the cup is stationary throughout grip/release.
    Counter surface is z=0; the cup origin is its vertical geometric midpoint.
    """
    t = min(DURATION, max(0.0, t))
    if t <= 1.55:
        z, angle = HALF_HEIGHT, 0.0
    elif t <= 1.98:
        z, angle = lerp(HALF_HEIGHT, LIFT_Z, smooth(t, 1.55, 1.98)), 0.0
    elif t <= 3.12:
        z, angle = LIFT_Z, math.pi*smooth(t, 1.98, 3.12)
    elif t <= SET_DOWN:
        z, angle = lerp(LIFT_Z, HALF_HEIGHT, smooth(t, 3.12, SET_DOWN)), math.pi
    else:
        z, angle = HALF_HEIGHT, math.pi
    approach = 1-smooth(t, 0.55, 1.24)
    withdrawal = smooth(t, 4.28, 5.10)
    hand_offset = (2.4*approach+2.4*withdrawal, 0.0, 0.32*approach+0.3*withdrawal)
    opening = 1-smooth(t, 1.24, GRIP_START)+smooth(t, SET_DOWN, 4.28)
    return {
        'time': t,
        'cup_location': (0.0, 0.0, z),
        'cup_angle': angle,
        'hand_location': (hand_offset[0], hand_offset[1], z+hand_offset[2]),
        'hand_angle': angle,
        'finger_opening': min(1.0, opening),
        'supported_by_hand': GRIP_START <= t <= SET_DOWN,
    }


def conservative_bottom(p):
    """Cup body bound. Handle extends only in x, the turn axis, so no lower."""
    a = p['cup_angle']
    return p['cup_location'][2]-HALF_HEIGHT*abs(math.cos(a))-RADIUS*abs(math.sin(a))


def contact_point_world(point, p, hand=False):
    xyz = rotate_x(point, p['hand_angle'] if hand else p['cup_angle'])
    loc = p['hand_location'] if hand else p['cup_location']
    return tuple(a+b for a, b in zip(xyz, loc))
