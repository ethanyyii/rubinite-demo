"""The dragged greatsword: one 3D pose, drawn in every direction by projecting it.

User 2026-09-30: the Boss walks dragging the sword, "the sword's perspective right in all four
directions". So the pose is defined once in 3D and each view only projects it
(animation-review §4.3: four directions are one 3D pose):

  axes      F forward, R to the Boss's right, U up (final px; origin on the ground under the hips)
  hand      hangs at the hip a little behind it (HAND), the arm nearly straight
  sword     from the fist back and down to the ground, turned YAW degrees outwards so it clears
            the legs and the cape; the tip rests on the ground, so its slope follows from the
            hand's height: sin(slope) = hand height / (fist -> tip)
  blade     rolled ROLL degrees from edge-down towards flat-down

  side view   screen = (F, -U + 0.35 (R - hand's R)): the whole sword, slanting back to the ground
              behind the heels; its tip is nearer the camera than the hand, so a little lower
  front view  screen = (-R, -U + 0.35 F): it points away from the camera, so it is short
              (about 0.47 of its length) and runs down and outwards from the fist
  back view   screen = (R, -U - 0.35 F): it points towards the camera, nearly full length,
              past the feet to below the foot line (the walk's frame is taller for this)
0.35 is the depth foreshortening every front/back pose uses (the knight, the Boss's feet).

sword_image(): the concept's sword drawn with any fist position, axis and width vector
(an affine map at the work resolution, then boss.stylize like every rendered part).
Between the standing pose (b = 0: the concept's sword exactly as the approved sprite has it)
and the drag (b = 1) the fist position, the axis and the width vector are interpolated
(vectors by angle and length, so the sword does not shrink half-way).
"""
import math
from PIL import Image
import boss as B
import idle
import rig
import labels

DEPTH = 0.35
YAW = 30.0               # degrees the dragged sword points outwards (to the Boss's right)
ROLL = 12.0              # blade roll: 0 = edge down (the flat upright, the edge ploughing the ground:
                         # how a hanging arm holds it), 90 = flat on the ground. Tried yaw 18-32 x
                         # roll -60..70 in all three views: roll 0 shows the full flat from the side
                         # but a sliver from behind, roll 45+ the reverse; at 12 the side view shows
                         # most of the flat and the other two a blade, not a paddle or a needle. Yaw 30 lets the front
                         # view see it past the cape (the sword points away there: 0.6 of its length)
# the hand of a hanging arm (the concept's own hanging fists: front view 27 px out and 75 up,
# back view 29 out and 77 up); used for the sword's slope and where no arm gives the position
HAND_BACK = 4.0
HAND_OUT = 28.0
HAND_UP = {'front': 76.0, 'back': 76.0, 'right': 76.0}
FLAT_SEEN = math.cos(math.radians(45))   # the concept draws the blade's flat turned 45 degrees


def project_vec(view, v, far=False):
    """A 3D direction (F, R, U) -> screen direction (final px). far: the side view of a Boss
    facing the other way (built in facing-right space, mirrored afterwards): his right side is
    then the far side, so what is further to his right is HIGHER on screen."""
    f, r, u = v
    if view == 'right':
        return (f, -u + (-DEPTH if far else DEPTH) * r)
    if view == 'front':
        return (-r, -u + DEPTH * f)
    return (r, -u - DEPTH * f)


def project(view, p, far=False):
    """A 3D point -> screen offset from the foot anchor (final px). The side view is drawn in
    the plane of the sword hand, the front and back views in the plane of the hips."""
    origin = (0.0, HAND_OUT, 0.0) if view == 'right' else (0.0, 0.0, 0.0)
    return project_vec(view, tuple(a - b for a, b in zip(p, origin)), far)


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


# Clean swords: the concept's sword cut-outs carry the fist that grips them in the standing
# pose and scraps of the arm and cape behind the hilt (hidden in the standing sprites, but they
# show as dark blocks once the sword moves). Every redrawn sword uses a cleaned cut-out:
#   with the fist  - while the sword is still upright in the hand as in the standing pose;
#   bare           - the fist's rows replaced by more of the grip (the visible grip above the
#                    fist repeated): the fist then belongs to the arm (arm.py), in line with
#                    the forearm, and the sword passes through it.
# Image px of ref/sword_<view>.png.
BARE = {
    'front': {'grip_x': (66, 92), 'grip_rows': (36, 54), 'fist_rows': (54, 106), 'pommel_x': (56, 104),
              'fist_x': (46, 102), 'trim_rows': (106, 122), 'hilt_bottom': 200},
    'right': {'grip_x': (54, 75), 'grip_rows': (36, 62), 'fist_rows': (62, 116), 'pommel_x': (44, 84),
              'fist_x': (24, 93), 'trim_rows': (116, 128), 'hilt_bottom': 212},
}
_bare = {}


def _dark(c):
    r, g, b, a = c
    L = (r * 3 + g * 4 + b * 2) / 9
    return a and (L < 46 or (L < 62 and r > g + 25 and r < 120))


def clean_sword(view, fist=False):
    """The view's sword cut-out without the scraps around the hilt; fist False: bare (see BARE)."""
    key = (view, fist)
    if key in _bare:
        return _bare[key]
    cfg = BARE[view]
    im = B.ref('sword_' + view).copy()
    p = im.load()
    W, H = im.size
    gx0, gx1 = cfg['grip_x']
    r0, r1 = cfg['grip_rows']
    f0, f1 = cfg['fist_rows']
    px0, px1 = cfg['pommel_x']
    fx0, fx1 = cfg['fist_x']
    src = {(x, y): p[x, y] for y in range(r0, r1) for x in range(gx0, gx1)}
    for y in range(0, f1):
        for x in range(W):
            if y < r0:
                keep = px0 <= x < px1              # pommel
            elif y < f0:
                keep = gx0 - 2 <= x < gx1 + 2       # the visible grip
            else:
                keep = fist and fx0 <= x < fx1      # the fist's rows
            if not keep:
                p[x, y] = (0, 0, 0, 0)
    if not fist:
        for y in range(f0, f1):
            sy = r0 + (y - f0) % (r1 - r0)
            for x in range(gx0, gx1):
                p[x, y] = src[(x, sy)]
    t0, t1 = cfg['trim_rows']
    for y in range(t0, t1):                         # between the fist and the guard: cuff, shadows
        for x in range(W):
            if not (gx0 - 2 <= x < gx1 + 2) and _dark(p[x, y]):
                p[x, y] = (0, 0, 0, 0)
    # dark scraps around the guard (cape, arm): dark pixels reachable from outside through
    # dark pixels, except a 2 px rim next to the sword itself (its outline)
    hb = cfg['hilt_bottom']
    outside = set()
    st = []
    for y in range(t0, hb):
        for x in range(W):
            if not p[x, y][3]:
                st.append((x, y))
    seen = set(st)
    while st:
        x, y = st.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= q[0] < W and t0 <= q[1] < hb and q not in seen and _dark(p[q]):
                seen.add(q)
                outside.add(q)
                st.append(q)
    solid = lambda q: 0 <= q[0] < W and 0 <= q[1] < H and p[q][3] and not _dark(p[q])
    for (x, y) in outside:
        if not any(solid((x + dx, y + dy)) for dx in range(-2, 3) for dy in range(-2, 3)):
            p[x, y] = (0, 0, 0, 0)
    _bare[key] = im
    return im


def sword_source(view, bare=False, raw=False):
    """The view's sword cut-out at sheet resolution and its points (pommel, grip, tip in image
    px), its standing position (local px of its corner). The back view uses the front view's
    sword mirrored (as the approved back sprite does). bare: cleaned, without the fist;
    raw: the cut-out as it is, with the fist and the shadowed arm behind it (the front view
    while the sword is still upright in front of the body: that shadow is what joins the
    fist to the shoulder); otherwise cleaned, with the fist."""
    src = 'front' if view == 'back' else view
    m = B.meta()[src]
    im = B.ref('sword_' + src) if raw else clean_sword(src, fist=not bare)
    _, pts = idle.sword_cutout(src)
    if view == 'back':
        _, corner = labels.back_sword()
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
        pts = {k: (im.width - 1 - x, y) for k, (x, y) in pts.items()}
    else:
        corner = (m['sword']['origin'][0] - m['origin'][0], m['sword']['origin'][1] - m['origin'][1])
    return im, pts, corner


def standing(view, lay=None):
    """The standing sword's placement in the frame: grip (final px), axis and width vectors
    (final px per sheet px along the blade / across it)."""
    lay = lay or rig.Layout(view)
    im, pts, corner = sword_source(view)
    g = lay.local_to_final((corner[0] + pts['grip'][0], corner[1] + pts['grip'][1]))
    ax = (pts['tip'][0] - pts['grip'][0], pts['tip'][1] - pts['grip'][1])
    n = math.hypot(*ax)
    ea = (ax[0] / n, ax[1] / n)
    ew = (ea[1], -ea[0])
    k = lay.kx / B.WORK
    return {'grip': g, 'axis': (ea[0] * k, ea[1] * k), 'width': (ew[0] * k, ew[1] * k), 'len': n * k}


def dragged(view, drop=0.0, lay=None, hand=None, far=False):
    """The dragged sword's placement in the frame (as standing()); drop = how far the hips are
    below standing height (the hand rides on the body). hand: the fist's screen position
    (final px) when the arm that holds it is drawn (the sword goes where the fist is; each
    view's arm comes from the concept and they agree on the hand within 2-3 px)."""
    lay = lay or rig.Layout(view)
    st = standing(view, lay)
    up = HAND_UP[view] - drop
    if hand is not None and view == 'right':
        up = (rig.AY + 1) - hand[1]
    sin_a = min(0.999, up / st['len'])
    al, ps = math.asin(sin_a), math.radians(YAW)
    a = (-math.cos(al) * math.cos(ps), math.cos(al) * math.sin(ps), -math.sin(al))
    s = (math.sin(ps), math.cos(ps), 0.0)                 # level, across the blade's run
    t = _norm(_cross(s, a))                               # in the vertical plane through the blade
    ro = math.radians(ROLL)
    w = _norm(tuple(math.cos(ro) * t[i] + math.sin(ro) * s[i] for i in range(3)))
    k = lay.kx / B.WORK                                   # final px per sheet px
    A = tuple(c * k for c in project_vec(view, a, far))
    W = tuple(c * k / FLAT_SEEN for c in project_vec(view, w, far))
    # keep the image's handedness (never mirror the sword)
    if (A[0] * W[1] - A[1] * W[0]) * (st['axis'][0] * st['width'][1] - st['axis'][1] * st['width'][0]) < 0:
        W = (-W[0], -W[1])
    if hand is None:
        h = project(view, (-HAND_BACK, HAND_OUT, up), far)
        hand = (rig.AX + 0.5 + h[0], rig.AY + 1 + h[1])
    return {'grip': tuple(hand), 'axis': A, 'width': W, 'len': st['len']}


def _polar(v0, v1, b):
    a0, a1 = math.atan2(v0[1], v0[0]), math.atan2(v1[1], v1[0])
    d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    a = a0 + d * b
    n = math.hypot(*v0) + (math.hypot(*v1) - math.hypot(*v0)) * b
    return (n * math.cos(a), n * math.sin(a))


def blend(p0, p1, b):
    """Placement between standing (b = 0) and dragged (b = 1)."""
    return {'grip': (p0['grip'][0] + (p1['grip'][0] - p0['grip'][0]) * b,
                     p0['grip'][1] + (p1['grip'][1] - p0['grip'][1]) * b),
            'axis': _polar(p0['axis'], p1['axis'], b), 'width': _polar(p0['width'], p1['width'], b)}


def tip_of(view, place):
    """Screen position (final px) of the sword's tip for a placement."""
    im, pts, _ = sword_source(view)
    n = math.hypot(pts['tip'][0] - pts['grip'][0], pts['tip'][1] - pts['grip'][1])
    return (place['grip'][0] + place['axis'][0] * n, place['grip'][1] + place['axis'][1] * n)


def affine_pixels(im, g, ea, G, A, W, frame, pal=None):
    """An RGBa image drawn so that its point g lands on G (final px), its unit direction ea
    maps to A and the direction across it (ea turned a quarter left on screen) to W (final px
    per image px); stylised. Returns {(x, y): colour} in a frame of `frame` final px."""
    ew = (ea[1], -ea[0])
    A = (A[0] * B.WORK, A[1] * B.WORK)
    W = (W[0] * B.WORK, W[1] * B.WORK)
    G = (G[0] * B.WORK, G[1] * B.WORK)
    # canvas = G + M (p - g), M = A ea^T + W ew^T
    m00, m01 = A[0] * ea[0] + W[0] * ew[0], A[0] * ea[1] + W[0] * ew[1]
    m10, m11 = A[1] * ea[0] + W[1] * ew[0], A[1] * ea[1] + W[1] * ew[1]
    det = m00 * m11 - m01 * m10
    i00, i01, i10, i11 = m11 / det, -m01 / det, -m10 / det, m00 / det
    coeff = (i00, i01, g[0] - i00 * G[0] - i01 * G[1], i10, i11, g[1] - i10 * G[0] - i11 * G[1])
    size = (frame[0] * B.WORK, frame[1] * B.WORK)
    canvas = im.transform(size, Image.AFFINE, coeff, resample=Image.BICUBIC).convert('RGBA')
    bb = canvas.getbbox()
    if bb is None:
        return {}
    x0, y0 = max(0, bb[0] // 4 * 4 - 8), max(0, bb[1] // 4 * 4 - 8)
    x1, y1 = min(size[0], (bb[2] + 3) // 4 * 4 + 8), min(size[1], (bb[3] + 3) // 4 * 4 + 8)
    small = B.stylize(canvas.crop((x0, y0, x1, y1)), pal or B.load_palette())
    ox, oy = x0 // 4, y0 // 4
    return {(x + ox, y + oy): c for (x, y), c in rig.pixels(small).items()}


def bone_pixels(im, p_img, q_img, P, Q, frame, width=None, lay_k=None):
    """A limb image drawn with its image points p, q on the screen points P, Q (final px):
    stretched or squashed along the bone, its width kept (width = final px per image px
    across, default the sheet's scale)."""
    ax = (q_img[0] - p_img[0], q_img[1] - p_img[1])
    n = math.hypot(*ax)
    ea = (ax[0] / n, ax[1] / n)
    d = (Q[0] - P[0], Q[1] - P[1])
    m = math.hypot(*d)
    A = (d[0] / n, d[1] / n)
    k = width if width is not None else lay_k
    u = (d[0] / m, d[1] / m)
    W = (u[1] * k, -u[0] * k)
    return affine_pixels(im, p_img, ea, P, A, W, frame)


_img = {}


def sword_image(view, place, frame=(rig.FW, rig.FH), pal=None, source='fist'):
    """The view's sword drawn at a placement: {(x, y): colour} in the frame. source: 'bare'
    (the arm brings its own fist), 'fist' or 'raw' (see sword_source)."""
    key = (view, source)
    if key not in _img:
        im, pts, _ = sword_source(view, bare=source == 'bare', raw=source == 'raw')
        _img[key] = (im.convert('RGBa'), pts)
    im, pts = _img[key]
    g = pts['grip']
    ax = (pts['tip'][0] - g[0], pts['tip'][1] - g[1])
    n = math.hypot(*ax)
    return affine_pixels(im, g, (ax[0] / n, ax[1] / n), place['grip'], place['axis'], place['width'], frame, pal)
