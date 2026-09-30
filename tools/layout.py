"""ScissorBall 36 – single source of truth for geometry.

Coordinates: millimetres, "hand-local" frame, math convention (y up).
x grows from the inner edge (thumb side, toward the other half) to the outer
edge (pinky side).  Origin = centre of the inner-column bottom-row key.
Physical right half uses the frame as-is; physical left half is mirrored
(x -> -x, rot -> -rot) when exported.
"""
import math

PITCH = 18.0                       # key pitch (X-switch caps are ~16.5 mm)
STAGGER = [0.0, 2.5, 5.0, 0.5, -6.5]   # column stagger (inner -> pinky), from Keyball39 scaled
CAP = 16.5                         # keycap size used for clearance checks
SW_BODY = (14.8, 14.0)             # PG1425 body

BALL_D = 25.0                      # trackball diameter
BALL_C = (26.0, -26.0)             # ball centre (right half only)
BALL_HOUSING_R = 15.0              # outer radius of ball tower at PCB level

# tilt of the key plane (the ball unit stays level on the floor)
TENT_DEG = 10.0                    # inner edge up
TILT_DEG = 5.0                     # front (user) edge up  ("negative tilt")


def finger_keys():
    keys = []
    for c in range(5):
        for r in range(3):                      # r=0 top row
            keys.append(dict(name=f"K{r}{c}", x=c * PITCH,
                             y=(2 - r) * PITCH + STAGGER[c], rot=0.0, row=r, col=c))
    return keys


def thumb_keys(side):
    if side == "right":
        t = [("T0", -26.0, -29.5, 20.0, 3, 0),
             ("T1", -6.0, -24.0, 10.0, 3, 1),
             ("P4", 4 * PITCH, STAGGER[4] - PITCH, 0.0, 3, 4)]   # extra pinky key under col 4
    else:
        t = [("T0", -26.0, -29.5, 20.0, 3, 0),
             ("T1", -6.0, -24.0, 10.0, 3, 1),
             ("T2", 13.5, -22.5, 0.0, 3, 2)]
    return [dict(name=n, x=x, y=y, rot=r, row=row, col=col) for n, x, y, r, row, col in t]


def keys(side):
    return finger_keys() + thumb_keys(side)


# ---- non-key parts (hand-local frame) ----
MCU = dict(x=-22.0, y=30.0, rot=90.0)        # RP2040-Zero, USB-C toward +y (back edge)
TRRS = dict(x=-33.0, y=7.0)                   # PJ-320A: plug mouth at x, body runs +x for 12.1 mm
SENSOR_HDR = dict(x=43.6, y=-13.5)           # 1x8 pads (right only), pin1 at this x, +2.54 each
MOUNT_HOLES = {
    "right": [(-15.0, 10.0), (-8.0, 49.0), (68.0, 44.0), (84.0, 20.0), (-12.0, -10.5), (45.0, -20.0), (72.0, -36.5)],
    "left":  [(-15.0, 10.0), (-8.0, 49.0), (68.0, 44.0), (84.0, 20.0), (-12.0, -10.5), (40.0, -13.5), (84.0, -9.0)],
}


def rect_corners(cx, cy, w, h, rot):
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return pts


def plane_z(x, y, x_ref, y_ref, z_ref):
    """height of the tilted key plane at (x,y): rises toward -x (inner) and -y (front)."""
    return z_ref + (x_ref - x) * math.tan(math.radians(TENT_DEG)) + (y_ref - y) * math.tan(math.radians(TILT_DEG))


def mirror(pt):
    return (-pt[0], pt[1])
