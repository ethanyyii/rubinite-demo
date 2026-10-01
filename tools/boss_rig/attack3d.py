"""The Boss's attacks as 3D numbers: where the shoulders, the two fists and the greatsword are in
every pose, before anything is drawn. Every view projects these (anim_attack.py); the four
facings are one 3D pose (animation-review §4.3).

Axes: F forward, R to the Boss's right, U up, final px; origin on the ground under him (the
foot anchor). Directions of the sword: azimuth psi (degrees from forward towards his right: 90 =
to his right, 180 = straight back, -90 = to his left) and elevation el (degrees, + tip up).

  shoulders   the arm joints where the arms come out from under the shoulder plates (the front
              view's drawn shoulders: 20.6 px either side, 112 px up). The upper body turns
              about the vertical axis (tw, degrees, + = towards his left: the right shoulder
              comes forward), leans forward about the belt (lx) and drops with the hips (D)
  fists       the right fist holds the grip at the sword's grip point (the concept's fist, high
              on the grip by the pommel); the left fist, two-handed, is HANDS px further along
              the grip, just above the guard (ref.json lower_hand, user 2026-09-30: heavy attacks
              two-handed, the left hand above the crossguard)
  arms        upper arm, forearm and fist as long as arm.py draws them (13.5, 15.7, 6.6): a
              fist further than that from its shoulder cannot be held - checked (reach())
  sword       grip to tip SWORD_LEN, pommel POMMEL behind the grip; its flat: roll 0 = lying
              level (the width horizontal), 90 = the edge up (the width in the vertical plane
              of the blade)
"""
import math

# ------------------------------------------------------------------ vectors
def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, k):
    return tuple(x * k for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return tuple(x / n for x in a)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def yaw(p, deg):
    """A point or direction turned about the vertical axis, + = towards his left (the forward
    direction turns towards -R; a point on his right shoulder comes forward)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[1] * s, -p[0] * s + p[1] * c, p[2])


def direction(psi, el):
    p, e = math.radians(psi), math.radians(el)
    return (math.cos(p) * math.cos(e), math.sin(p) * math.cos(e), math.sin(e))


def angles(a):
    """(psi, el) of a direction."""
    return math.degrees(math.atan2(a[1], a[0])), math.degrees(math.asin(max(-1.0, min(1.0, a[2]))))


def width(a, roll):
    """The blade's width direction for axis a: roll 0 = level (flat facing up), 90 = in the
    vertical plane through the blade (the edge up / down)."""
    psi, el = angles(a)
    p, e = math.radians(psi), math.radians(el)
    h = (-math.sin(p), math.cos(p), 0.0)
    v = (-math.sin(e) * math.cos(p), -math.sin(e) * math.sin(p), math.cos(e))
    r = math.radians(roll)
    return tuple(math.cos(r) * h[i] + math.sin(r) * v[i] for i in range(3))


# ------------------------------------------------------------------ the body's numbers
SH_F, SH_R, SH_U = 1.0, 20.6, 112.0       # the shoulder joints at rest (front view: 107.9 and 149.1, row 98)
BELT_U = 90.5                             # the lean pivots about the belt (the renderer shifts rows above it)
UPPER, FORE, FIST = 13.46, 15.73, 6.61    # arm.lengths(): shoulder-elbow, elbow-wrist, wrist-fist centre
ARM = UPPER + FORE + FIST
PROTRACT = 3.0                            # px a shoulder may come forward towards a far fist (the shoulder blade)
HANDS = 10.0                              # px along the grip from the right fist to the left (two fists side by side)
SWORD_LEN = 118.0                         # grip point to tip (sword.standing: 117.3 side, 119 front/back)
POMMEL = 20.0                             # grip point back to the pommel's end
HEAD = (0.0, 0.0, 130.0)                  # the helmet's centre (crown tips to the chin: 112 .. 160)
HEAD_R = 11.0


def shoulder(side_, st):
    """Shoulder joint (side_ 'R' or 'L') for a pose: hips dropped D, leaned lx about the belt,
    the upper body turned tw."""
    r = SH_R if side_ == 'R' else -SH_R
    p = yaw((SH_F, r, SH_U), st.get('tw', 0.0))
    lean = math.tan(math.radians(st.get('lx', 0.0)))
    return (p[0] + lean * (SH_U - BELT_U) + st.get('hx', 0.0), p[1], p[2] - st.get('D', 0))


HANG_L = (2.0, -23.4, 75.4)      # the left fist hanging at rest (front view: (151.9, 133.6))


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def fists(st):
    """(right fist, left fist) centres; the left is None one-handed (two = 0). Between 0 and 1
    the left fist is on its way from hanging (carried by the upper body) to the grip."""
    g = st['fist']
    two = st.get('two', 0.0)
    if two <= 0.0:
        return g, None
    grip = add(g, mul(st['axis'], HANDS))
    if two >= 1.0:
        return g, grip
    rest = shoulder('L', {})
    hang = add(shoulder('L', st), yaw(sub(HANG_L, rest), st.get('tw', 0.0)))
    return g, lerp(hang, grip, smooth(two))


def solve_arm(sh, hand, pole):
    """Elbow for a shoulder and a fist centre: the arm's two segments (upper arm; forearm with
    the fist) bend towards `pole`. Returns (elbow, shoulder used, slack px): a fist out of reach
    pulls the shoulder up to PROTRACT px towards it; slack < 0 is how far it is still out of
    reach (not allowed: checked)."""
    d = sub(hand, sh)
    n = norm(d)
    lo = FORE + FIST
    if n > ARM:
        pull = min(PROTRACT, n - ARM + 0.01)
        sh = add(sh, mul(unit(d), pull))
        d = sub(hand, sh)
        n = norm(d)
    slack = ARM - n
    n_ = min(n, ARM - 1e-6)
    u = unit(d)
    a = (UPPER ** 2 - lo ** 2 + n_ ** 2) / (2 * n_)
    h = math.sqrt(max(0.0, UPPER ** 2 - a ** 2))
    pp = sub(pole, mul(u, dot(pole, u)))
    if norm(pp) < 1e-6:
        pp = (0.0, 0.0, -1.0)
    pp = unit(pp)
    return add(add(sh, mul(u, a)), mul(pp, h)), sh, slack


POLE = {'R': (-0.25, 0.45, -1.0), 'L': (-0.25, -0.45, -1.0)}
POLE_HANG = (-0.3, -0.25, -1.0)


# The shoulder girdle follows the upper arm (user 2026-10-01: "the shoulders do not carry the
# upper arms, only the forearms swing"): an upper arm raised lifts the shoulder (and its plate),
# one swung forward brings it forward, one swung out takes it out. px at the most:
GIRDLE_UP = 6.0          # the upper arm straight up (a third of it level, none hanging)
GIRDLE_FWD = 4.5         # the upper arm straight forward (back: the same backwards)
GIRDLE_OUT = 2.0         # the upper arm straight out to its side


def _girdle(k, u, tw):
    """The shoulder's move for upper-arm direction u (from the shoulder to the elbow)."""
    q = yaw(u, -tw)                       # in the upper body's own frame
    side_ = 1.0 if k == 'R' else -1.0
    lift = GIRDLE_UP * min(1.0, max(0.0, (u[2] + 0.4) / 1.4))
    fwd = GIRDLE_FWD * q[0]
    out = GIRDLE_OUT * max(0.0, q[1] * side_)
    return yaw((fwd, out * side_, 0.0), tw)[:2] + (lift,)


_carry_girdle = {}


def carry_girdle():
    """The right shoulder's girdle move in the carry (the pose every attack starts from and
    ends in, drawn as approved): the girdle is measured from it, so the carry itself is not
    moved."""
    if not _carry_girdle:
        import carry
        st = {'fist': carry.FIST}
        sh = shoulder('R', st)
        e, _, _ = solve_arm(sh, carry.FIST, POLE['R'])
        _carry_girdle['R'] = _girdle('R', unit(sub(e, sh)), 0.0)
    return _carry_girdle['R']


def girdles(st):
    """{'R': (dF, dR, dU), 'L': ...}: how far each shoulder joint has moved with its upper arm
    (from where the carry has it: the left from hanging, the right from the carry)."""
    gR, gL = fists(st)
    out = {}
    for k, g in (('R', gR), ('L', gL)):
        if g is None:
            out[k] = (0.0, 0.0, 0.0)
            continue
        sh = shoulder(k, st)
        e, sh1, _ = solve_arm(sh, g, _pole(k, st))
        gd = _girdle(k, unit(sub(e, sh1)), st.get('tw', 0.0))
        if k == 'R':
            gd = sub(gd, carry_girdle())
        else:
            gd = mul(gd, smooth(st.get('two', 0.0)))
        out[k] = gd
    return out


def _pole(k, st):
    pole = st.get('pole' + k) or POLE[k]
    if k == 'L':
        pole = lerp(POLE_HANG, pole, smooth(st.get('two', 0.0)))
    return pole


def arms(st):
    """{'R': (shoulder, elbow, fist, slack), 'L': ... or None}. The left arm hangs (None) when
    the pose is one-handed. The shoulders are where the girdle has taken them (girdles())."""
    gR, gL = fists(st)
    gd = girdles(st)
    out = {}
    for k, g in (('R', gR), ('L', gL)):
        if g is None:
            out[k] = None
            continue
        e, sh, slack = solve_arm(add(shoulder(k, st), gd[k]), g, _pole(k, st))
        out[k] = (sh, e, g, slack)
    return out


def tip(st):
    return add(st['fist'], mul(st['axis'], SWORD_LEN))


def pommel(st):
    return sub(st['fist'], mul(st['axis'], POMMEL))


# ------------------------------------------------------------------ what may not happen
def body_hits(st, step=3.0, start=10.0):
    """Points along the blade (from `start` px past the grip) inside the body: the torso (an
    elliptic column, 13 px front-back, 22 side to side, from the hips to the shoulder joints),
    the shoulder plates (14 px front-back, from 10 to 34 px out, up to 19 px over the joints: the
    carry rests the blade on them)
    and the helmet with the crown (11 px round, 6 px below the shoulder joints up to the crown,
    48 px over them); all turned, leaned and dropped with the upper body. Returns the distances
    along the blade that are inside, and what they hit."""
    hits = []
    tw = st.get('tw', 0.0)
    D = st.get('D', 0)
    lean = math.tan(math.radians(st.get('lx', 0.0)))
    hx = st.get('hx', 0.0)
    t = start
    while t <= SWORD_LEN:
        p = add(st['fist'], mul(st['axis'], t))
        u = p[2] + D                                       # height as if standing
        f = p[0] - hx - lean * max(0.0, u - BELT_U)
        q = yaw((f, p[1], u), -tw)                         # the upper body's own frame
        what = None
        if 60 <= u <= SH_U + 2 and (q[0] / 13.0) ** 2 + (q[1] / 22.0) ** 2 < 1.0:
            what = 'torso'
        elif SH_U - 8 <= u <= SH_U + 19 and abs(q[0]) < 14.0 and 10.0 <= abs(q[1]) <= 34.0:
            what = 'plate'
        elif SH_U - 6 <= u <= SH_U + 48 and q[0] ** 2 + q[1] ** 2 < 11.0 ** 2:
            what = 'head'
        if what:
            hits.append((round(t), what))
        t += step
    return hits


# ------------------------------------------------------------------ projection (stick previews)
DEPTH = 0.35


def project(view, p, far=False):
    """Screen offset (final px) of a 3D point from the foot anchor: facing right, F is screen x
    and R shows as depth; facing down, -R is x and F depth (down-screen)."""
    f, r, u = p
    if view == 'right':
        return (f, -u + (-DEPTH if far else DEPTH) * r)
    if view == 'front':
        return (-r, -u + DEPTH * f)
    return (r, -u - DEPTH * f)
