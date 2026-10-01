"""The greatsword carried on the right shoulder: one 3D pose, drawn in every direction by
projecting it.

User 2026-09-30: every way the Boss moves (forward, backward, sideways) he carries the sword
level on his right shoulder - the blade lying on the shoulder plate, the tip behind him, the
hilt in front, the right fist on the grip in front of the shoulder. It is his moving / ready
pose: every attack starts from it and ends in it. "The sword's and the hand's four views" must
be right, so the pose is defined once in 3D and each view only projects it (animation-review
§4.3: four directions are one 3D pose; the weapon is held the same way in all of them).

  axes      F forward, R to the Boss's right, U up (final px; origin on the ground under him)
  fist      FIST: in front of the right shoulder plate, at the height of its top
  sword     from the fist back over the shoulder plate: YAW degrees outwards (the hand is nearer
            the chest than the plate's crown, so the blade runs out to his right behind him) and
            TILT degrees tip-up (the fist is a little below the plate's top)
  blade     lying flat: its width is level (the flat faces up). Seen from the side it is thin
            (0.35 of its width, like everything that lies in depth), from the front and from
            behind it shows its flat

  facing right   screen = (F, -U + 0.35 (R - fist's R)): the whole sword, level, from the fist in
                 front of the chin back over the shoulder plate to 100 px behind him
  facing left    the same with the depth reversed (the sword is on the far shoulder): drawn
                 behind the body; what shows is the blade behind the cape's collar - its tip
                 further from the camera, so higher - and the fist with the pommel in front of
                 the throat
  facing down    screen = (-R, -U + 0.35 F): the blade points away from the camera, so it is
                 short (about half its length) and rises from the shoulder up and outwards,
                 behind the shoulder plate; the fist and the pommel (towards the camera) are in
                 front of the plate
  facing up      screen = (R, -U - 0.35 F): the blade comes towards the camera: short, from the
                 shoulder plate's top down and outwards, in front of everything; the hilt and the
                 fist are behind the shoulder
0.35 is the depth foreshortening every front/back pose uses (the knight, the Boss's feet).

Between the planted sword of the standing pose (b = 0: the concept's sword exactly as the
approved sprite has it) and the carry (b = 1) the sword goes round in front of him (user
2026-10-01: "from the front of the body, round, onto the shoulder - that is how a body does
it"): the tip leaves the ground and swings forward and up, the sword stands upright in front of
the shoulder, then tips back onto it - SWING degrees about one level axis (the one across the
carried blade). Not the short way (96 degrees, the tip back past his right side and up): that
drags the blade up through the arm and the shoulder plate. The fist goes from where it stands
to FIST, a little forward and up on the way (REACH, LIFT: the arm swings the sword up). While
the blade is forward and up it is more than a frame's worth away from him: those poses are
drawn in a larger container (anim_walk). The flat keeps the angle the fist holds it at and
turns level only as the blade comes down onto the shoulder. All four views project that one
motion; putting the sword down goes the same way back.
"""
import math
import boss as B
import rig
import gait
import sword as swd

DEPTH = swd.DEPTH
FIST = (15.0, 23.0, 134.5)      # F, R, U of the fist's centre
YAW = 18.0
TILT = 6.0
LIFT = 5.0                      # px the fist rises half-way, over the straight line
REACH = 5.0                     # px it goes forward half-way (the arm swings the sword up)
SWING = 270.0 - TILT            # degrees from hanging tip-down, forward and over, to the carry
EDGE = (0.35, 0.8)              # the edge leads from the first blend (the tip forward) until the second (tipping
                                # back); then the flat turns level onto the shoulder. A turning blade is seen
                                # edge-on from some view at some moment; ending the turn at 0.8 rather than 0.7
                                # leaves one such moment per view instead of two
STAND_FLAT = 45.0               # standing: the flat is turned this far between forward and outward
# final px along the sword from the grip point to where the guard begins: the hilt (pommel,
# grip) is in front of the shoulder, the guard and the blade lie on / behind it
HILT = 8.5
ON_SHOULDER = 0.9               # from this blend on the blade lies on the shoulder plate
THICK = 0.25                    # the blade's thickness as a share of the width the concept draws it


def _heading():
    p = math.radians(YAW)
    return (-math.cos(p), math.sin(p), 0.0)


def _across():
    """Level, across the carried blade: the axis the sword turns about, and the carried
    blade's width direction."""
    p = math.radians(YAW)
    return (math.sin(p), math.cos(p), 0.0)


def pose3(b):
    """The sword's 3D directions at blend b: (axis from the grip to the tip, width). The tip
    goes from straight down, forward (and a little inwards: the plane of the carried blade),
    up, and over back onto the shoulder."""
    th = math.radians(SWING * b)
    h, n = _heading(), _across()
    f = (-h[0], -h[1], 0.0)                               # forward, a little inwards
    a = (f[0] * math.sin(th), f[1] * math.sin(th), -math.cos(th))
    # perpendicular to both the blade and the turning axis (level while the sword stands):
    # width along m = the edge leads, the flat faces sideways; along n = the flat faces the
    # way it swings
    m = (f[0] * math.cos(th), f[1] * math.cos(th), math.sin(th))
    phi = math.radians(roll(b))
    w = tuple(math.cos(phi) * n[i] + math.sin(phi) * m[i] for i in range(3))
    return a, w


def roll(b):
    """Degrees the flat is turned from lying level (0) towards facing sideways (90), at blend b.
    Standing the fist holds it STAND_FLAT between forward and outward; as the arm swings the
    sword up the wrist turns the edge to lead (a sword is swung edge first, and so both side
    views see its flat while it is forward and upright); tipping back onto the shoulder the
    wrist turns it over to lie flat."""
    up = gait.smooth(b / EDGE[0])
    down = gait.smooth((b - EDGE[1]) / (1.0 - EDGE[1]))
    return ((STAND_FLAT - YAW) + (90.0 - (STAND_FLAT - YAW)) * up) * (1.0 - down)


def blade_back(b):
    """Whether the blade points back over the shoulder (behind his head from the front, towards
    the camera from behind) rather than down, forward or up in front of him."""
    return pose3(b)[0][0] < -0.2


def fist_screen(view, far=False):
    """Where the carrying fist is in the frame (final px), the body at rest."""
    f, r, u = FIST
    if view == 'right':                 # drawn in the plane of the sword hand
        return (rig.AX + 0.5 + f, rig.AY + 1 - u)
    if view == 'front':
        return (rig.AX + 0.5 - r, rig.AY + 1 - u + DEPTH * f)
    return (rig.AX + 0.5 + r, rig.AY + 1 - u - DEPTH * f)


def move_screen(view, v, far=False):
    """A 3D displacement of the fist (F, R, U) on screen (the sword hand's own plane in the side
    views: R shows as depth)."""
    return swd.project_vec(view, v, far)


def _projected(view, b, far, k, stand):
    a, w = pose3(b)
    A = tuple(c * k for c in swd.project_vec(view, a, far))
    W = tuple(c * k / swd.FLAT_SEEN for c in swd.project_vec(view, w, far))
    # keep the image's handedness (never mirror the sword; its two faces are alike)
    if (A[0] * W[1] - A[1] * W[0]) * (stand['axis'][0] * stand['width'][1] - stand['axis'][1] * stand['width'][0]) < 0:
        W = (-W[0], -W[1])
    return A, W


def place(view, b, stand, far=False, ride=(0, 0)):
    """The sword's placement in the frame (as swd.standing()) at blend b. stand: the standing
    placement of this view; ride: how far the chest has carried the shoulder (and the sword on
    it) from where it rests, px."""
    k = math.hypot(*stand['axis'])                  # final px per sheet px
    A, W = _projected(view, b, far, k, stand)
    if b < 1.0:
        # the concept's views are elevations, not projections of one model: what the standing
        # sprite shows differs a little from the projected upright sword; the difference fades
        A0, W0 = _projected(view, 0.0, far, k, stand)
        A = tuple(A[i] + (stand['axis'][i] - A0[i]) * (1 - b) for i in range(2))
        W = tuple(W[i] + (stand['width'][i] - W0[i]) * (1 - b) for i in range(2))
    # seen edge-on the blade still shows its own thickness (half-way up, the view from his
    # left passes from one face of the blade to the other)
    n = math.hypot(*A)
    u = (A[0] / n, A[1] / n)
    across = u[0] * W[1] - u[1] * W[0]
    hand = 1.0 if stand['axis'][0] * stand['width'][1] - stand['axis'][1] * stand['width'][0] > 0 else -1.0
    if across * hand < THICK * k:
        add = THICK * k * hand - across
        W = (W[0] - u[1] * add, W[1] + u[0] * add)
    g0, g1 = stand['grip'], fist_screen(view, far)
    g1 = (g1[0] + ride[0], g1[1] + ride[1])
    bump = move_screen(view, (REACH * math.sin(math.pi * b), 0.0, LIFT * math.sin(math.pi * b)), far)
    grip = (g0[0] + (g1[0] - g0[0]) * b + bump[0], g0[1] + (g1[1] - g0[1]) * b + bump[1])
    # the tip stands on the ground: on screen it never goes lower than that (swinging out
    # towards the camera it would, for the first few degrees)
    sheet = stand['len'] / k
    low = grip[1] + A[1] * sheet - (g0[1] + stand['axis'][1] * sheet)
    if low > 0:
        grip = (grip[0], grip[1] - low)
    return {'grip': grip, 'axis': A, 'width': W, 'len': stand['len']}


def split(pix, place_, along=HILT):
    """A drawn sword as (hilt, blade): the pixels before / after `along` final px from the
    grip point towards the tip (measured along the sword itself, whatever its foreshortening)."""
    g, ax = place_['grip'], place_['axis']
    k = math.hypot(*ax)
    # a pixel's position along the sword in sheet px: invert the placement's affine map
    wd = place_['width']
    det = ax[0] * wd[1] - ax[1] * wd[0]
    sheet = along / (B.sheet_scale() / B.WORK)
    hilt, blade = {}, {}
    for (x, y), c in pix.items():
        dx, dy = x + 0.5 - g[0], y + 0.5 - g[1]
        t = (dx * wd[1] - dy * wd[0]) / det if abs(det) > 1e-9 else (dx * ax[0] + dy * ax[1]) / (k * k)
        (blade if t >= sheet else hilt)[(x, y)] = c
    return hilt, blade
