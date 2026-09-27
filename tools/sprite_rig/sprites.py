"""The part library: the four recovered reference sprites, the frame layout, and helpers
shared by every animation (textured legs, the idle frame)."""
import math
import os
from PIL import Image
from limbs import knee_ik, seg_dist

# Final character size (2026-09-26, do not change): body from sole to helmet top = 40 px,
# plume extra (about 10 px). Every pixel threshold in checks.py derives from BODY_PX.
BODY_PX = 40
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'native40') + os.sep
FW, FH = 56, 56          # frame size
GROUND = 53              # sole bottom row inside the frame (foot anchor = (CX, GROUND))
CX = 28                  # body centre column inside the frame

OL = (13, 8, 9, 255)     # outline colour of the reference
D2 = (36, 30, 32, 255)   # dark steel, fallback when a texture sample is empty


def load(name):
    im = Image.open(D + name + '_clean.png').convert('RGBA')
    px = {}
    for y in range(im.height):
        for x in range(im.width):
            c = im.getpixel((x, y))
            if c[3]:
                px[(x, y)] = c
    return px, im.size


def is_blue(c):
    return c[2] > c[0] + 25 and c[2] > 60


class Frame:
    """One output frame as a pixel dict on the FW x FH canvas."""

    def __init__(self):
        self.px = {}

    def paste(self, pix, dx=0, dy=0):
        for (x, y), c in pix.items():
            self.px[(x + dx, y + dy)] = c

    def image(self):
        im = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
        for (x, y), c in self.px.items():
            if 0 <= x < FW and 0 <= y < FH:
                im.putpixel((x, y), c)
        return im


def draw_leg_tex(layer, pix, hip, ankle, facing, leg_src, boot_src, dim=1.0, ring_over=None, lens=(4.5, 4.0),
                 radii=(2.4, 2.1)):
    """Leg in a new pose, textured with the reference's own leg pixels.
    leg_src = (x0, x1, y0, y1) region of one original leg (hip..ankle);
    boot_src = (x0, x1, y0, y1, ax) region of one original boot, ax = its ankle column."""
    hx, hy = hip
    ax, ay = ankle
    kx, ky = knee_ik(hx, hy, ax, ay, lens[0], lens[1], forward=facing)
    segs = [(hx, hy, kx, ky, radii[0]), (kx, ky, ax, ay, radii[1])]
    l1 = math.hypot(kx - hx, ky - hy)
    l2 = math.hypot(ax - kx, ay - ky)
    total = l1 + l2
    sx0, sx1, sy0, sy1 = leg_src
    scx, shw = (sx0 + sx1) / 2, (sx1 - sx0) / 2
    body = {}
    for si, (a, b, c, d, r) in enumerate(segs):
        seglen = math.hypot(c - a, d - b) or 1
        for y in range(int(min(b, d) - r - 2), int(max(b, d) + r + 2)):
            for x in range(int(min(a, c) - r - 2), int(max(a, c) + r + 2)):
                dist, side = seg_dist(x + 0.5, y + 0.5, a, b, c, d)
                if dist > r:
                    continue
                t = max(0.0, min(1.0, ((x + 0.5 - a) * (c - a) + (y + 0.5 - b) * (d - b)) / seglen ** 2))
                u = (t * seglen + (l1 if si else 0)) / total
                v_front = -side * facing / r
                srcx = int(round(scx + facing * v_front * shw))
                srcy = int(round(sy0 + u * (sy1 - sy0)))
                col = None
                for dx in (0, -1, 1, -2, 2):
                    col = pix.get((srcx + dx, srcy))
                    if col and not is_blue(col):
                        break
                    col = None
                col = col or D2
                if (x, y) not in body or si == 1:
                    body[(x, y)] = col
    # carry every highlight pixel of the source leg to its place on the posed leg (knee cop,
    # greave glints): sampling the texture per output pixel can step over a 1 px highlight
    # when the knee bends
    for (x, y), c in pix.items():
        if not (sx0 <= x <= sx1 and sy0 <= y <= sy1) or sum(c[:3]) <= 420:
            continue
        u = (y - sy0) / max(sy1 - sy0, 1)
        v_front = (x - scx) / (facing * shw) if shw else 0.0
        dist = u * total
        if dist <= l1 or l2 == 0:
            a, b, c2, d, r = segs[0]
            t = dist / l1 if l1 else 0.0
        else:
            a, b, c2, d, r = segs[1]
            t = (dist - l1) / l2
        cx_, cy_ = a + (c2 - a) * t, b + (d - b) * t
        L = math.hypot(c2 - a, d - b) or 1.0
        nx, ny = -(d - b) / L, (c2 - a) / L
        off = -v_front * r / facing
        key = (math.floor(cx_ + nx * off), math.floor(cy_ + ny * off))
        if key in body:
            body[key] = c
    bx0, bx1, by0, by1, bax = boot_src
    for (x, y), c in pix.items():
        if bx0 <= x <= bx1 and by0 <= y <= by1 and not is_blue(c):
            body[(int(round(ax)) + x - bax, int(round(ay)) + y - by0)] = c
    if dim != 1.0:
        body = {k: (int(c[0] * dim), int(c[1] * dim), int(c[2] * dim), 255) for k, c in body.items()}
    ring = {}
    for (x, y) in body:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in body and (ring_over is None or q in layer.px):
                ring[q] = OL
    layer.px.update(ring)
    layer.px.update(body)


def stand_frame(name):
    """Idle = the reference sprite itself, untouched, placed on the frame."""
    pix, _ = SPR[name]
    m = META[name]
    fr = Frame()
    fr.paste(pix, CX - m['cx'], GROUND - m['feet'])
    return fr


SPR = {n: load(n) for n in ('front', 'side_right', 'back', 'side_left')}

# where each sprite sits in the frame: body centre column and sole row in the sprite
# scale = this library relative to the 50 px one (each view's body scaled to exactly 40 px)
META = {
    'front': dict(cx=26, feet=48, scale=40 / 49),
    'side_right': dict(cx=17, feet=50, scale=40 / 50),
    'back': dict(cx=15, feet=48, scale=40 / 51),
    'side_left': dict(cx=13, feet=46, scale=40 / 50),
}
