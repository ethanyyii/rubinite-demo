"""The side view's walking legs: the concept's leg cut into thigh, shin and boot, posed on the
gait model's joints at the work resolution, then stylised (boss.stylize) like every Boss frame.

These are the only parts of the walk that are re-rendered from the concept: a leg that swings
20 degrees cannot be made by shifting pixels. Everything else moves in whole pixels (rig.py).
"""
import math
from PIL import Image, ImageDraw
import boss as B
import rig
import gait

VIEW = 'right'
# joints in local px (ref/right.png)
HIP, KNEE, ANKLE = (143, 350), (140, 472), (127, 615)
# parts: polygon (local px), pivot joint. Draw order: shin, boot, thigh (the knee plate is the
# thigh's; the shin runs up under it, and down into the boot, so bending never opens a gap).
# The thigh runs up under the hip armour (the body layer is drawn over it).
PARTS = [
    ('shin', KNEE, [(107, 455), (176, 455), (178, 497), (152, 514), (149, 598), (154, 612), (160, 630),
                    (98, 630), (100, 520), (104, 497)]),
    ('boot', ANKLE, [(84, 684), (84, 650), (98, 622), (100, 600), (150, 600), (154, 612), (200, 650),
                     (205, 684)]),
    ('thigh', HIP, [(107, 300), (186, 300), (184, 440), (180, 480), (166, 495), (140, 499), (115, 495),
                    (107, 482)]),
]
BACK_EDGE = (96, 118)     # local columns where the cape's red touches the back of the leg
FAR_DARKEN = 0.62        # the far leg is the same leg, in shadow
_cache = {}


def _part_images():
    if 'parts' not in _cache:
        src = B.ref(VIEW)
        out = {}
        for name, pivot, poly in PARTS:
            m = Image.new('L', src.size, 0)
            ImageDraw.Draw(m).polygon(poly, fill=255)
            im = Image.new('RGBA', src.size, (0, 0, 0, 0))
            im.paste(src, (0, 0), m)
            # the cape's red edge runs along the back of the leg: not part of the leg
            px = im.load()
            for y in range(im.height):
                for x in range(BACK_EDGE[0], BACK_EDGE[1]):
                    r, g, b, a = px[x, y]
                    if a and r > 60 and r > g + 40:
                        px[x, y] = (0, 0, 0, 0)
            out[name] = (im.convert('RGBa'), pivot)
        _cache['parts'] = out
    return _cache['parts']


def _place(canvas, part, pivot_work, angle_deg, scale):
    """Draw a part on the work canvas with its pivot at pivot_work, rotated by angle_deg
    (clockwise on screen), scaled by `scale` work px per local px."""
    im, pivot = part
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    # output (u, v) -> source: R(-a) * ((u, v) - pivot_work) / scale + pivot
    k = 1 / scale
    m = (c * k, s * k, pivot[0] - (c * pivot_work[0] + s * pivot_work[1]) * k,
         -s * k, c * k, pivot[1] - (-s * pivot_work[0] + c * pivot_work[1]) * k)
    layer = im.transform(canvas.size, Image.AFFINE, m, resample=Image.BICUBIC).convert('RGBA')
    canvas.alpha_composite(layer)


def _angle(rest_a, rest_b, a, b):
    """Clockwise screen angle (degrees) that turns rest_a->rest_b onto a->b (image coords)."""
    r = math.atan2(rest_b[1] - rest_a[1], rest_b[0] - rest_a[0])
    n = math.atan2(b[1] - a[1], b[0] - a[0])
    return math.degrees(n - r)


def joints_work(L, lay=None):
    """A gait.leg() in work px of the frame: hip, knee, ankle."""
    lay = lay or rig.Layout(VIEW)
    hx = lay.local_to_work(HIP)[0]
    ground = (rig.AY + 1) * B.WORK
    return {k: (hx + B.WORK * L[k][0], ground - B.WORK * L[k][1]) for k in ('hip', 'knee', 'ankle')}


def render(L, pal=None, lay=None):
    """One leg posed on the gait model's joints: {(x, y): colour} in the frame (final px)."""
    lay = lay or rig.Layout(VIEW)
    pal = pal or B.load_palette()
    parts = _part_images()
    J = joints_work(L, lay)
    canvas = Image.new('RGBA', (rig.FW * B.WORK, rig.FH * B.WORK), (0, 0, 0, 0))
    ang = {
        'thigh': _angle(HIP, KNEE, J['hip'], J['knee']),
        'shin': _angle(KNEE, ANKLE, J['knee'], J['ankle']),
        'boot': -L['pitch'],
    }
    piv = {'thigh': J['hip'], 'shin': J['knee'], 'boot': J['ankle']}
    for name, _, _ in PARTS:
        _place(canvas, parts[name], piv[name], ang[name], lay.kx)
    bb = canvas.getbbox()
    x0, y0 = bb[0] // 4 * 4 - 8, bb[1] // 4 * 4 - 8
    x1, y1 = (bb[2] + 3) // 4 * 4 + 8, (bb[3] + 3) // 4 * 4 + 8
    crop = canvas.crop((x0, y0, x1, y1))
    small = B.stylize(crop, pal)
    ox, oy = x0 // 4, y0 // 4
    return {(x + ox, y + oy): c for (x, y), c in rig.pixels(small).items()}


def darken(pix, pal=None, k=FAR_DARKEN):
    snap = B.Snapper(pal or B.load_palette())
    return {q: snap(tuple(round(v * k) for v in c)) for q, c in pix.items()}


def leg_pixels(L):
    """render() cached by the leg's numbers."""
    key = tuple(round(v, 2) for v in (*L['hip'], *L['knee'], *L['ankle'], L['pitch']))
    if key not in _cache:
        _cache[key] = render(L, B.load_palette(), rig.Layout(VIEW))
    return _cache[key]


def legs(i):
    """(near, far) leg pixels of walk pose i: the far leg strikes half a cycle later."""
    p = gait.phase(i)
    return leg_pixels(gait.leg(p)), darken(leg_pixels(gait.leg(p, True)))
