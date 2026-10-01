"""The front view's legs for the sidestep: the concept's leg swung sideways from the hip.

In the walk the front view's legs are the approved sprite's pixels with rows dropped or
duplicated (a foot coming towards the camera only changes height). In a sidestep the feet
travel 48 px sideways on screen, one to one - that cannot be done by shifting rows - so the
leg is drawn from the concept: one part from the hip to the ankle (thigh, knee plate, shin),
mapped onto the screen line hip -> ankle (a lifted foot makes it shorter: the knee bends
towards the camera), and the boot, set flat at the ankle. Stylised like every rendered part.

The concept's front view shows only the Boss's right leg (screen left) in full - the cloak
hangs in front of his left thigh - so the left leg is the right one mirrored.
"""
import math
from PIL import Image, ImageDraw
import boss as B
import rig
import gait
import arm

# ref/front.png px
HIP, ANKLE = (160, 344), (152, 600)
LEG_POLY = [(128, 286), (192, 286), (192, 470), (186, 500), (180, 540), (180, 590), (186, 604), (112, 604),
            (126, 590), (126, 540), (113, 500), (118, 460), (122, 400), (126, 340)]
BOOT_POLY = [(110, 594), (188, 594), (190, 676), (84, 676), (84, 650), (100, 620)]
SOLE_ROW = 675
FRAME = (rig.FW, rig.FH)
_parts = {}
_cache = {}


def _part(poly):
    src = B.ref('front')
    m = Image.new('L', src.size, 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    im = Image.new('RGBA', src.size, (0, 0, 0, 0))
    im.paste(src, (0, 0), m)
    px = im.load()
    for y in range(min(q[1] for q in poly), min(src.height, max(q[1] for q in poly) + 1)):
        for x in range(min(q[0] for q in poly), min(src.width, max(q[0] for q in poly) + 1)):
            if px[x, y][3] and arm._is_cloth(px[x, y]):      # the cape behind the leg
                px[x, y] = (0, 0, 0, 0)
    return im.convert('RGBa')


def render(hip, ankle):
    """His right leg (screen left) with the hip joint and the ankle at these screen points
    (final px): {(x, y): colour}."""
    key = (round(hip[0], 1), round(hip[1], 1), round(ankle[0], 1), round(ankle[1], 1))
    if key in _cache:
        return _cache[key]
    if not _parts:
        _parts['leg'] = _part(LEG_POLY)
        _parts['boot'] = _part(BOOT_POLY)
    k = B.sheet_scale()
    W = B.WORK
    canvas = Image.new('RGBA', (FRAME[0] * W, FRAME[1] * W), (0, 0, 0, 0))
    arm._place_bone(canvas, _parts['leg'], HIP, ANKLE, (hip[0] * W, hip[1] * W), (ankle[0] * W, ankle[1] * W), k)
    # the boot: flat, its ankle on the ankle
    drop = (SOLE_ROW - ANKLE[1]) * k
    arm._place_bone(canvas, _parts['boot'], ANKLE, (ANKLE[0], SOLE_ROW), (ankle[0] * W, ankle[1] * W),
                    (ankle[0] * W, ankle[1] * W + drop), k)
    out = arm._stylize(canvas)
    _cache[key] = out
    return out


def rest(lay):
    """Where the approved sprite has his right leg's hip joint and ankle (final px)."""
    return lay.local_to_final(HIP), lay.local_to_final(ANKLE)


def leg(L, which, d, hipx, lay):
    """A sidestep leg in the front view. L: the leg's state (lat = sideways offset of the foot,
    his right +; ankle = (forward, height)); which 'R' or 'L'; d: hip drop; hipx: the hips'
    sideways shift on screen."""
    hip0, ankle0 = rest(lay)
    lat = L.get('lat', 0.0)
    rise = L['ankle'][1] - gait.ANKLE_H
    fwd = L['ankle'][0]
    dy = -rise + 0.35 * fwd                      # a foot forward of him is nearer the camera: lower
    if which == 'R':
        # his right is screen left: a foot towards his right moves to -x
        return render((hip0[0] + hipx, hip0[1] + d), (ankle0[0] - lat, ankle0[1] + dy))
    # the left leg: the right leg's drawing mirrored about the anchor column. In the mirrored
    # picture his left foot's offset towards his right is +x, which mirrors back to -x.
    pix = render((hip0[0] - hipx, hip0[1] + d), (ankle0[0] + lat, ankle0[1] + dy))
    return {(2 * rig.AX - x, y): c for (x, y), c in pix.items()}
