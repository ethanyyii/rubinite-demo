"""Boss animation rig: the approved standing sprites cut into layers, moved in whole pixels.

Why whole pixels (see README "動畫的做法"): the standing sprites are stylised from a painted
concept, full of fine texture. Re-stylising a slightly moved copy re-rolls that texture (the
whole body shimmers). So the small motions (breathing, cloth sway, the bob of a walk, a boot
lifting towards the camera) move the APPROVED pixels by whole final pixels - rows are
duplicated or dropped at seams, never resampled - and frame 1 of the idle is the approved
sprite, pixel for pixel. Only limbs that really rotate (the side view's walking legs, later
the attacks' arms and sword) are posed at the work resolution from the concept and stylised
(limb.py).

Coordinates:
  local  - pixels of ref/<view>.png (what you see when you open the file); polygons are traced
           in these (LOCAL[...] below) on 4x zooms with a 10 px grid;
  final  - pixels of the 256x224 frame (foot anchor at (128, 208)).
Layout(view) maps between them exactly the way idle.frames() places the view.
"""
from PIL import Image, ImageDraw
import boss as B
import idle

FW, FH, AX, AY = 256, 224, 128, 208           # frame of the non-attack animations (final px)
VIEW_OF = {'down': 'front', 'right': 'right', 'up': 'back'}     # left: built in facing-right space (side.py)
DIRS = ('down', 'right', 'up', 'left')


class Layout:
    """Where a concept view lands in the frame (the same arithmetic as idle.frames)."""

    def __init__(self, view, fw=FW, fh=FH, ax=AX, ay=AY, height=B.HEIGHT):
        self.view = view
        canvas, anchor = idle.compose(view)
        self.canvas_size = canvas.size
        bb = canvas.getbbox()
        self.bb = bb
        s = B.sheet_scale(height)
        self.cw, self.ch = bb[2] - bb[0], bb[3] - bb[1]
        self.size = (round(self.cw * s), round(self.ch * s))
        self.kx, self.ky = self.size[0] / self.cw, self.size[1] / self.ch
        fx, fy = ax * B.WORK, ay * B.WORK
        self.off = (round(fx - (anchor[0] - bb[0]) * s), round(fy + B.WORK - (anchor[1] - bb[1] + 1) * s))
        self.frame = (fw, fh)

    def local_to_work(self, p):
        return ((p[0] + idle.PAD - self.bb[0]) * self.kx + self.off[0],
                (p[1] + idle.PAD - self.bb[1]) * self.ky + self.off[1])

    def local_to_final(self, p):
        x, y = self.local_to_work(p)
        return x / B.WORK, y / B.WORK

    def final_to_local(self, p):
        """Final pixel centre -> local coordinates."""
        wx, wy = (p[0] + 0.5) * B.WORK, (p[1] + 0.5) * B.WORK
        return ((wx - self.off[0]) / self.kx + self.bb[0] - idle.PAD,
                (wy - self.off[1]) / self.ky + self.bb[1] - idle.PAD)

    def canvas_to_work(self, canvas):
        """An image on the compose canvas (local + PAD) -> the work-resolution frame."""
        im = canvas.crop(self.bb)
        if im.mode == 'RGBA':
            im = B.premul_resize(im, self.size)
        else:
            im = im.resize(self.size, Image.LANCZOS)
        out = Image.new(im.mode, (self.frame[0] * B.WORK, self.frame[1] * B.WORK), 0)
        out.paste(im, self.off)
        return out


_standing = None


def standing():
    """{direction: the standing sprite} (256x224 final px). Down, right, up: the approved
    sprites from idle.py. Left: NOT the mirror of right (user 2026-09-30: the sword is in his
    right hand, which the body hides when he faces left; the left hand is empty) - side.py."""
    global _standing
    if _standing is None:
        pal = B.load_palette()
        fr = idle.frames(FW, FH, AX, AY)
        _standing = {k: B.stylize(f.im, pal) for k, f in fr.items() if k != 'left'}
        import side
        _standing['left'] = image(side.standing_left())
    return _standing


def pixels(im):
    """{(x, y): (r, g, b)} of the opaque pixels."""
    p = im.load()
    return {(x, y): p[x, y][:3] for y in range(im.height) for x in range(im.width) if p[x, y][3]}


def image(pix, size=(FW, FH)):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    p = im.load()
    for (x, y), c in pix.items():
        if 0 <= x < size[0] and 0 <= y < size[1]:
            p[x, y] = tuple(c[:3]) + (255,)
    return im


def mirror_left(im):
    """An image mirrored about the anchor column's centre (facing-right space -> facing left;
    facing left is not the facing-right sprite mirrored, see side.py)."""
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out.paste(im.transpose(Image.FLIP_LEFT_RIGHT), (2 * AX + 1 - im.width, 0))
    return out


# ------------------------------------------------------------------ polygons
def in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def poly_mask(view, polys, lay=None):
    """Final pixels whose centre is inside any of the polygons (local coordinates)."""
    lay = lay or Layout(view)
    pts = set()
    for poly in polys:
        fin = [lay.local_to_final(q) for q in poly]
        x0, x1 = int(min(q[0] for q in fin)) - 1, int(max(q[0] for q in fin)) + 2
        y0, y1 = int(min(q[1] for q in fin)) - 1, int(max(q[1] for q in fin)) + 2
        for y in range(y0, y1):
            for x in range(x0, x1):
                if in_poly((x + 0.5, y + 0.5), fin):
                    pts.add((x, y))
    return pts


def is_cloth(c):
    """Cape / banner cloth by colour: saturated reds and the violets. The armour's warm dark
    greys fall in the palette's red group too (chroma < 0.08), so they are not cloth."""
    L, a, b = B.oklab(c)
    g = B.hue_group(c)
    return (g == 'violet' and L >= 0.2) or (g == 'red' and (a * a + b * b) ** 0.5 >= 0.08)


def is_gold(c):
    return B.hue_group(c) == 'gold'


# ------------------------------------------------------------------ layers
class Layer:
    """Pixels of one part: `pix` are the approved sprite's own pixels, `under` the underlay
    (pixels hidden at rest, under the layers drawn above it) that shows when parts move apart."""

    def __init__(self, name, pix, under=None):
        self.name = name
        self.pix = pix
        self.under = under or {}

    def get(self, q):
        c = self.pix.get(q)
        return c if c is not None else self.under.get(q)

    def all(self):
        d = dict(self.under)
        d.update(self.pix)
        return d

    def bbox(self):
        ks = list(self.pix) + list(self.under)
        xs = [k[0] for k in ks]
        ys = [k[1] for k in ks]
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def grow_under(layer, allowed, radius):
    """Underlay by dilation: the layer's nearest pixel is copied up to `radius` px into
    `allowed` (pixels covered by layers above it). Short reach only: it smears."""
    known = layer.all()
    frontier = set(known)
    for _ in range(radius):
        new = {}
        for (x, y) in frontier:
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in allowed and q not in known and q not in new:
                    new[q] = known[(x, y)]
        if not new:
            break
        layer.under.update(new)
        known.update(new)
        frontier = set(new)


def mirror_under(layer, allowed, reach):
    """Underlay by reflection: along each row, the layer's own pixels are mirrored about its
    edge up to `reach` px into `allowed`. Keeps the cloth's texture and its ragged hem (each
    row reflects what that row has), where grow_under would smear. Call before grow_under."""
    pix = layer.pix
    new = {}
    for (x, y) in pix:
        for step in (1, -1):
            if (x + step, y) in pix:
                continue
            for k in range(1, reach + 1):
                q = (x + step * k, y)
                if q not in allowed or q in pix:
                    break
                c = pix.get((x - step * (k - 1), y))
                if c is None:
                    break
                new.setdefault(q, c)
    layer.under.update(new)


def extend_up(layer, allowed, reach):
    """Underlay above a part (a shin under the cloth that covers it): each column's top rows
    mirrored upwards, up to `reach` px, inside `allowed`."""
    top = {}
    for (x, y) in layer.pix:
        if x not in top or y < top[x]:
            top[x] = y
    for x, y0 in top.items():
        for k in range(1, reach + 1):
            q = (x, y0 - k)
            if q not in allowed:
                break
            c = layer.pix.get((x, y0 + k - 1))
            if c is None:
                break
            layer.under[q] = c


def fill_pinholes(pix, keep=()):
    """1 px holes (all four neighbours opaque) that seams leave: filled with the darkest
    neighbour. `keep`: the holes the standing sprite has itself (tiny gaps between the cape's
    tatters); each of them may survive once, as the nearest hole within 3 px."""
    holes = pinholes(pix)
    spared = set()
    for kx, ky in keep:
        near = [q for q in holes if q not in spared and abs(q[0] - kx) <= 3 and abs(q[1] - ky) <= 3]
        if near:
            spared.add(min(near, key=lambda q: abs(q[0] - kx) + abs(q[1] - ky)))
    n = 0
    for (x, y) in holes:
        if (x, y) not in spared:
            pix[(x, y)] = min((pix[q] for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))), key=B.lum)
            n += 1
    return n


def pinholes(pix):
    return [(x, y) for (x, y) in {(q[0] + 1, q[1]) for q in pix} if (x, y) not in pix
            and all(q in pix for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))]


def warp(layer, src, bbox=None, pad=12):
    """Inverse map: the pixel drawn at target q is the layer's pixel at src(x, y) (whole
    pixels; None = nothing). Returns {target: colour}."""
    x0, y0, x1, y1 = bbox or layer.bbox()
    out = {}
    get = layer.get
    for y in range(y0 - pad, y1 + pad):
        for x in range(x0 - pad, x1 + pad):
            s = src(x, y)
            if s is None:
                continue
            c = get(s)
            if c is not None:
                out[(x, y)] = c
    return out


def row_table(lift, y0, y1):
    """Rows moved up by lift(source row) px (whole numbers, may differ per row): returns
    {target row: source row}. Where the lift grows upwards the row at the seam is duplicated,
    where it shrinks a row is dropped (the lower one wins, so seams eat into the part above)."""
    table = {}
    for sy in range(y0, y1):              # top to bottom: lower rows overwrite
        table[sy - lift(sy)] = sy
    lo, hi = min(table), max(table)
    last = None
    for ty in range(hi, lo - 1, -1):       # fill gaps with the row below
        if ty in table:
            last = table[ty]
        else:
            table[ty] = last
    return table


def composite(layers_pix):
    """Bottom to top."""
    out = {}
    for pix in layers_pix:
        out.update(pix)
    return out
