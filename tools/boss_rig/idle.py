"""The Boss standing pose (idle frame 1) in four directions, at the work resolution.

Third concept (2026-09-30, user: "sword bigger, hand higher"): the long greatsword (pommel at
the chin) stands planted at the Boss's front-right, tip on the ground, the right fist high on
the grip (near the pommel, at shoulder height). One 3D pose for all four (animation-review §4.3):
  - Down: the concept's front view as drawn (the sword beside the right leg).
  - Right: the concept's facing-right view as drawn (the sword in front of the front foot).
    Front and side both show the blade about equally wide: its flat is turned about 45 deg
    between forward and outward.
  - Left: frames() still returns facing right mirrored (the first proposal; the sheet's own
    facing-left view has a shorter sword and a lower fist), but it is NOT used any more:
    user 2026-09-30 - the sword is in the right hand, so facing left the sword arm is on the
    far side, mostly hidden by the body, and the near (left) hand is empty. The facing-left
    sprite is built from the facing-right layers in side.py (rig.standing()['left']).
  - Up: the back view with the hanging forearm erased (parts.body: the hand is up on the grip,
    hidden behind the shoulder) and the front view's sword mirrored (its back) standing behind
    the body at the right arm, tip on the ground: the pommel shows above the shoulder, the cape
    hides most of the blade.
Each view is composed at sheet resolution (ref coordinates + PAD), then scaled to the work
resolution and placed so its foot anchor lands on the frame's.
"""
from PIL import Image
import boss as B
import parts

PAD = 200       # sheet px of room around a view (the sword behind the back view)
# back view: how far out (sheet px, screen right) from the right elbow the sword's grip stands;
# the front view's fist is 30 px further out than its elbow
BACK_GRIP_OUT = 30


class Frame:
    """A work-resolution canvas: FW x FH final px, foot anchor at (AX, AY) final px."""

    def __init__(self, fw, fh, ax, ay):
        self.fw, self.fh, self.ax, self.ay = fw, fh, ax, ay
        self.im = Image.new('RGBA', (fw * B.WORK, fh * B.WORK), (0, 0, 0, 0))

    def anchor(self):
        return self.ax * B.WORK, self.ay * B.WORK


def sword_cutout(view='front'):
    """A view's sword (with the fist on it) at sheet resolution: (image, points) with points
    pommel/grip/lower_hand/tip in the image's coordinates."""
    s = B.meta()[view]['sword']
    ox, oy = s['origin']
    im = B.ref('sword_' + view)
    pts = {k: (s[k][0] - ox, s[k][1] - oy) for k in ('pommel', 'grip', 'lower_hand', 'tip')}
    return im, pts


def compose(view):
    """The view at sheet resolution (ref coordinates + PAD). Returns (image, foot anchor)."""
    m = B.meta()[view]
    base = parts.body(view)
    W, H = base.size[0] + 2 * PAD, base.size[1] + 2 * PAD
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sole = m['sole'] + PAD
    if view == 'back':
        sword, pts = sword_cutout('front')
        sword = sword.transpose(Image.FLIP_LEFT_RIGHT)
        pts = {k: (sword.width - 1 - x, y) for k, (x, y) in pts.items()}
        ex = m['elbow'][0] - m['origin'][0] + PAD
        pos = (ex + BACK_GRIP_OUT - pts['grip'][0], sole - (sword.height - 1))    # tip on the sole row
        canvas.alpha_composite(sword, (round(pos[0]), round(pos[1])))
    canvas.alpha_composite(base, (PAD, PAD))
    return canvas, (m['cx'] + PAD, sole)


def frames(fw, fh, ax, ay, height=B.HEIGHT):
    """{direction: Frame} for down, right, up, left."""
    out = {}
    s = B.sheet_scale(height)
    for d, view in (('down', 'front'), ('right', 'right'), ('up', 'back')):
        im, anchor = compose(view)
        bb = im.getbbox()
        im = im.crop(bb)
        anchor = (anchor[0] - bb[0], anchor[1] - bb[1])
        work = B.premul_resize(im, (round(im.width * s), round(im.height * s)))
        f = Frame(fw, fh, ax, ay)
        fx, fy = f.anchor()
        # the sole row's bottom edge on the bottom edge of the frame's anchor row
        f.im.alpha_composite(work, (round(fx - anchor[0] * s), round(fy + B.WORK - (anchor[1] + 1) * s)))
        out[d] = f
    # left: right mirrored about the anchor column's centre (work x -> 2 * centre - x)
    f = Frame(fw, fh, ax, ay)
    mirrored = out['right'].im.transpose(Image.FLIP_LEFT_RIGHT)
    centre = ax * B.WORK + B.WORK / 2
    f.im.alpha_composite(mirrored, (round(2 * centre - f.im.width), 0))
    out['left'] = f
    return out


def sword_part(height=B.HEIGHT):
    """The front view's greatsword (with the fist) at work scale: (image, grip, tip)."""
    s = B.sheet_scale(height)
    sw, pts = sword_cutout('front')
    im = B.premul_resize(sw, (round(sw.width * s), round(sw.height * s)))
    k = im.width / sw.width
    return im, (pts['grip'][0] * k, pts['grip'][1] * k), (pts['tip'][0] * k, pts['tip'][1] * k)
