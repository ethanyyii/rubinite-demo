"""The greatsword as a part: the concept's sword cut-outs cleaned, and drawn at any placement.

  clean_sword()   the cut-outs without the scraps around the hilt, with or without the fist of
                  the standing pose (the fist belongs to the arm, arm.py)
  standing()      where the approved standing sprite has the sword: grip point, axis, width
  sword_image()   the sword drawn with any grip position, axis and width vector (an affine map
                  at the work resolution, then boss.stylize like every rendered part)
  project_vec()   a 3D direction in a view: F forward, R to the Boss's right, U up; what lies in
                  depth shows 0.35 of its length as height (DEPTH, the foreshortening every
                  front/back pose uses - the knight, the Boss's feet)
How the sword is held while he moves is in carry.py (one 3D pose, projected into each view).
"""
import math
from PIL import Image
import boss as B
import idle
import rig
import labels

DEPTH = 0.35
FLAT_SEEN = math.cos(math.radians(45))   # the concept draws the blade's flat turned 45 degrees: the width it
                                         # shows is this share of the flat's own width


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
    (final px per sheet px along the blade / across it), len (grip to tip, final px)."""
    lay = lay or rig.Layout(view)
    im, pts, corner = sword_source(view)
    g = lay.local_to_final((corner[0] + pts['grip'][0], corner[1] + pts['grip'][1]))
    ax = (pts['tip'][0] - pts['grip'][0], pts['tip'][1] - pts['grip'][1])
    n = math.hypot(*ax)
    ea = (ax[0] / n, ax[1] / n)
    ew = (ea[1], -ea[0])
    k = lay.kx / B.WORK
    return {'grip': g, 'axis': (ea[0] * k, ea[1] * k), 'width': (ew[0] * k, ew[1] * k), 'len': n * k}


def tip_of(view, place):
    """Screen position (final px) of the sword's tip for a placement."""
    im, pts, _ = sword_source(view)
    n = math.hypot(pts['tip'][0] - pts['grip'][0], pts['tip'][1] - pts['grip'][1])
    return (place['grip'][0] + place['axis'][0] * n, place['grip'][1] + place['axis'][1] * n)


def affine_pixels(im, g, ea, G, A, W, frame, pal=None, origin=(0, 0)):
    """An RGBa image drawn so that its point g lands on G (final px), its unit direction ea
    maps to A and the direction across it (ea turned a quarter left on screen) to W (final px
    per image px); stylised. Returns {(x, y): colour} in a frame of `frame` final px whose top
    left corner is `origin` (a larger container: negative)."""
    ew = (ea[1], -ea[0])
    A = (A[0] * B.WORK, A[1] * B.WORK)
    W = (W[0] * B.WORK, W[1] * B.WORK)
    G = ((G[0] - origin[0]) * B.WORK, (G[1] - origin[1]) * B.WORK)
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
    ox, oy = x0 // 4 + origin[0], y0 // 4 + origin[1]
    return {(x + ox, y + oy): c for (x, y), c in rig.pixels(small).items()}


_img = {}


def sword_image(view, place, frame=(rig.FW, rig.FH), pal=None, source='fist', origin=(0, 0)):
    """The view's sword drawn at a placement: {(x, y): colour} in the frame (top left corner at
    `origin`). source: 'bare' (the arm brings its own fist), 'fist' or 'raw' (see sword_source)."""
    key = (view, source)
    if key not in _img:
        im, pts, _ = sword_source(view, bare=source == 'bare', raw=source == 'raw')
        _img[key] = (im.convert('RGBa'), pts)
    im, pts = _img[key]
    g = pts['grip']
    ax = (pts['tip'][0] - g[0], pts['tip'][1] - g[1])
    n = math.hypot(*ax)
    return affine_pixels(im, g, (ax[0] / n, ax[1] / n), place['grip'], place['axis'], place['width'], frame, pal, origin)
