"""A posable arm for the side views: the concept's hanging left arm (front view) cut into upper
arm, forearm and fist, posed on shoulder - elbow - wrist joints at the work resolution and
stylised like every rendered part (the same method as the legs, limb.py).

User 2026-09-30: the dragging arm was "twisted, the fist crooked and not joined to the arm" -
it had been one arm image stretched from the shoulder to the sword's own fist, which turned
with the sword. Now the arm has an elbow, the fist is part of the arm (in line with the
forearm, always its own size), and the sword passes through the fist (sword.clean_sword).

The source arm is seen from the front; its elbow spike points outwards. Mirrored (the default)
the spike points to screen left = backwards for a Boss facing right.

The same arm holds the sword on the shoulder while he moves (carry.py, anim_walk.py): upper
arm forward from under the shoulder plate, forearm up to the fist on the grip. render() can
draw some of its parts only, so that the shoulder plate goes between the upper arm and the
forearm, and the hilt between the forearm and the fist.
"""
import math
from PIL import Image, ImageDraw
import boss as B
import rig

# ref/front.png px (traced on a 4x zoom with a 10 px grid)
SHOULDER, ELBOW, WRIST, FIST = (322, 205), (326, 262), (336, 328), (334, 356)
PARTS = [
    # name, pivot, the bone it follows, polygon
    ('upper', SHOULDER, (SHOULDER, ELBOW), [(301, 192), (346, 188), (350, 225), (350, 262), (302, 262), (299, 225)]),
    ('fist', WRIST, (WRIST, FIST), [(314, 320), (353, 320), (358, 340), (358, 372), (350, 384), (320, 384),
                                    (310, 368), (310, 336)]),
    ('fore', ELBOW, (ELBOW, WRIST), [(296, 252), (318, 240), (340, 238), (358, 250), (360, 280), (354, 326),
                                     (318, 328), (306, 300), (300, 270)]),
]
NEAR_GAIN = 1.3          # the arm on the camera's side is lit like the approved side view's forearm
                         # (mean brightness 66; the front view's arm, in the cape's shadow, is 46)
_parts = {}
_cache = {}


def _is_cloth(c):
    """The cape behind the arm (reds, violets); the armour is neutral, the trim bright."""
    r, g, b, a = c
    L = (r * 3 + g * 4 + b * 2) / 9
    return L < 110 and (r - g > 45 or (b - g > 12 and r - g > 8))


def scale():
    return B.sheet_scale() / B.WORK


def lengths():
    """Upper arm, elbow -> wrist, wrist -> fist centre, in final px."""
    k = scale()
    return (math.dist(SHOULDER, ELBOW) * k, math.dist(ELBOW, WRIST) * k, math.dist(WRIST, FIST) * k)


def _part_images(mirror):
    if mirror not in _parts:
        src = B.ref('front')
        out = {}
        W = src.width
        for name, pivot, bone, poly in PARTS:
            m = Image.new('L', src.size, 0)
            ImageDraw.Draw(m).polygon(poly, fill=255)
            im = Image.new('RGBA', src.size, (0, 0, 0, 0))
            im.paste(src, (0, 0), m)
            px = im.load()
            for y in range(min(q[1] for q in poly), max(q[1] for q in poly) + 1):
                for x in range(min(q[0] for q in poly), max(q[0] for q in poly) + 1):
                    if px[x, y][3] and _is_cloth(px[x, y]):
                        px[x, y] = (0, 0, 0, 0)
            if mirror:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
                flip = lambda q: (W - 1 - q[0], q[1])
                pivot, bone = flip(pivot), (flip(bone[0]), flip(bone[1]))
            out[name] = (im.convert('RGBa'), pivot, bone)
        _parts[mirror] = out
    return _parts[mirror]


def pose(shoulder, elbow, hand):
    """Joints for given screen points of the shoulder, elbow and fist centre (final px). The
    fist keeps its size; the upper arm and forearm are drawn as long as the points say (an
    arm pointing towards the camera is shorter on screen)."""
    l1, l2, l3 = lengths()
    dx, dy = hand[0] - elbow[0], hand[1] - elbow[1]
    n = math.hypot(dx, dy) or 1.0
    fore = max(1.5, n - l3)
    wrist = (elbow[0] + dx / n * fore, elbow[1] + dy / n * fore)
    hand = (wrist[0] + dx / n * l3, wrist[1] + dy / n * l3)
    return {'shoulder': tuple(shoulder), 'elbow': tuple(elbow), 'wrist': wrist, 'hand': hand}


def hanging(shoulder, upper_deg=0.0, fore_deg=0.0):
    """Joints of an arm hanging from `shoulder`: the upper arm upper_deg and the forearm
    fore_deg back from straight down (degrees; + = towards screen left)."""
    l1, l2, l3 = lengths()
    a, b = math.radians(upper_deg), math.radians(fore_deg)
    elbow = (shoulder[0] - l1 * math.sin(a), shoulder[1] + l1 * math.cos(a))
    wrist = (elbow[0] - l2 * math.sin(b), elbow[1] + l2 * math.cos(b))
    hand = (elbow[0] - (l2 + l3) * math.sin(b), elbow[1] + (l2 + l3) * math.cos(b))
    return {'shoulder': tuple(shoulder), 'elbow': elbow, 'wrist': wrist, 'hand': hand}


def _place_bone(canvas, im, p, q, P, Q, kw):
    """Draw an RGBa part on the work canvas with its image bone p -> q on P -> Q (work px):
    stretched or squashed along the bone, kw work px per image px across it."""
    ax = (q[0] - p[0], q[1] - p[1])
    n = math.hypot(*ax)
    ea = (ax[0] / n, ax[1] / n)
    ew = (ea[1], -ea[0])
    d = (Q[0] - P[0], Q[1] - P[1])
    m = math.hypot(*d)
    A = (d[0] / n, d[1] / n)
    W = (d[1] / m * kw, -d[0] / m * kw)
    m00, m01 = A[0] * ea[0] + W[0] * ew[0], A[0] * ea[1] + W[0] * ew[1]
    m10, m11 = A[1] * ea[0] + W[1] * ew[0], A[1] * ea[1] + W[1] * ew[1]
    det = m00 * m11 - m01 * m10
    i00, i01, i10, i11 = m11 / det, -m01 / det, -m10 / det, m00 / det
    coeff = (i00, i01, p[0] - i00 * P[0] - i01 * P[1], i10, i11, p[1] - i10 * P[0] - i11 * P[1])
    canvas.alpha_composite(im.transform(canvas.size, Image.AFFINE, coeff, resample=Image.BICUBIC).convert('RGBA'))


def _stylize(canvas, pal=None):
    bb = canvas.getbbox()
    if bb is None:
        return {}
    x0, y0 = max(0, bb[0] // 4 * 4 - 8), max(0, bb[1] // 4 * 4 - 8)
    x1 = min(canvas.width, (bb[2] + 3) // 4 * 4 + 8)
    y1 = min(canvas.height, (bb[3] + 3) // 4 * 4 + 8)
    small = B.stylize(canvas.crop((x0, y0, x1, y1)), pal or B.load_palette())
    return {(x + x0 // 4, y + y0 // 4): c for (x, y), c in rig.pixels(small).items()}


def render(J, frame=(rig.FW, rig.FH), mirror=True, pal=None, parts=None):
    """The arm on the joints J (pose() / hanging()): {(x, y): colour} in the frame. parts:
    only these of 'upper', 'fore', 'fist' (another part goes between them in the z order: a
    shoulder plate over the upper arm, a hilt under the fist)."""
    key = (tuple(round(v, 2) for k in ('shoulder', 'elbow', 'wrist', 'hand') for v in J[k]), frame, mirror, parts)
    if key in _cache:
        return _cache[key]
    canvas = Image.new('RGBA', (frame[0] * B.WORK, frame[1] * B.WORK), (0, 0, 0, 0))
    target = {'upper': (J['shoulder'], J['elbow']), 'fore': (J['elbow'], J['wrist']), 'fist': (J['wrist'], J['hand'])}
    k = B.sheet_scale()
    images = _part_images(mirror)
    for name, _, _, _ in PARTS:
        if parts is not None and name not in parts:
            continue
        im, pivot, bone = images[name]
        a, b = target[name]
        if math.dist(a, b) < 1.0:
            continue                       # (an upper arm wholly under the shoulder plate)
        _place_bone(canvas, im, bone[0], bone[1], (a[0] * B.WORK, a[1] * B.WORK), (b[0] * B.WORK, b[1] * B.WORK), k)
    out = _stylize(canvas, pal)
    _cache[key] = out
    return out


def fist_only(hand, direction=(0.0, 1.0), frame=(rig.FW, rig.FH), mirror=False):
    """Just the fist (cuff and knuckles), centred on `hand`, its wrist towards -direction."""
    l1, l2, l3 = lengths()
    wrist = (hand[0] - direction[0] * l3, hand[1] - direction[1] * l3)
    im, pivot, bone = _part_images(mirror)['fist']
    canvas = Image.new('RGBA', (frame[0] * B.WORK, frame[1] * B.WORK), (0, 0, 0, 0))
    _place_bone(canvas, im, bone[0], bone[1], (wrist[0] * B.WORK, wrist[1] * B.WORK),
                (hand[0] * B.WORK, hand[1] * B.WORK), B.sheet_scale())
    return _stylize(canvas)


def near(pix):
    """The arm as the near-side arm of a side view: brightened (NEAR_GAIN), on the palette."""
    snap = B.Snapper(B.load_palette())
    return {q: snap(tuple(min(255, round(v * NEAR_GAIN)) for v in c)) for q, c in pix.items()}
