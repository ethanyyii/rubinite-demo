"""Shared Boss (Veltharis) helpers: size constants, the cleaned concept views, the work
resolution and the one-step stylised downscale that every Boss frame goes through.

How a Boss frame is made (different from the knight, see README):
  1. the cleaned concept views (reference.py -> ref/) are scaled to the work resolution,
     WORK px per final px, so the crown tip to sole spans WORK * height rows;
  2. parts are posed / composited at the work resolution (smooth resampling is fine here);
  3. stylize() turns the work image into the final pixel art in three layers: the armour
     and cloth base (median filter, box downscale by WORK), then the gold trim and the red
     runes on top wherever they cover enough of the final pixel; snap to the shared palette,
     dark outline on the silhouette, drop specks. Every direction and every frame goes through the same step, so they all
     share one look and one palette.
"""
import colorsys
import json
import math
import os
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REF = os.path.join(HERE, 'ref')
PALETTE_FILE = os.path.join(HERE, 'palette.txt')

# Boss height, front view's crown tip to sole, in final px. User 2026-09-30: 160 (4x the knight's
# 40; 140 read as "a father spanking his son"), sword and attack ranges scaled up with it.
# Waiting for the user to confirm the four directions at this size (see art-progress).
HEIGHT = 160
WORK = 4                # work px per final px
OUTLINE = (12, 7, 12)   # the concept's outline colour (darkest cluster of the palette)
ALPHA_MIN = 0.5         # coverage for a final pixel to be opaque
PALETTE_SIZE = 48
MEDIAN = 5              # work px; smooths the concept's texture noise in the base layer
GOLD_MIN = 0.35         # coverage of gold / pale work pixels that makes a final pixel gold
RED_MIN = 0.25          # same for the glowing red



def lum(c):
    return (c[0] * 3 + c[1] * 4 + c[2] * 2) / 9


def meta():
    with open(os.path.join(REF, 'ref.json')) as fh:
        return json.load(fh)


def ref(name):
    return Image.open(os.path.join(REF, name + '.png')).convert('RGBA')


def premul_resize(im, size, box=None, resample=Image.LANCZOS):
    return im.convert('RGBa').resize(size, resample, box=box).convert('RGBA')


class View:
    """One concept view at the work resolution. anchor = (body centre column, sole row).
    Every view uses the front view's scale (they stand on one ground line on one sheet), so
    `height` is the front view's crown tip to sole; a view whose crown is drawn taller (the
    side views' spike) stays taller."""

    def __init__(self, name, height=HEIGHT, mirror=False):
        allm = meta()
        m = allm[name]
        f = allm['front']
        src = ref(name)
        s = WORK * height / (f['sole'] - f['crown_tip'])
        self.scale = s
        self.name = name
        self.origin = m['origin']
        W, H = round(src.width * s), round(src.height * s)
        self.im = premul_resize(src, (W, H))
        self.anchor = (m['cx'] * s, m['sole'] * s)
        self.mirror = mirror
        if mirror:
            self.im = self.im.transpose(Image.FLIP_LEFT_RIGHT)
            self.anchor = (W - self.anchor[0], self.anchor[1])

    def to_work(self, sheet_xy):
        """Sheet coordinates -> this view's work image coordinates."""
        x = (sheet_xy[0] - self.origin[0]) * self.scale
        y = (sheet_xy[1] - self.origin[1]) * self.scale
        if self.mirror:
            x = self.im.width - x
        return x, y


def sheet_scale(height=HEIGHT):
    """Work px per sheet px (the front view's crown tip to sole = WORK * height)."""
    f = meta()['front']
    return WORK * height / (f['sole'] - f['crown_tip'])


def load_palette():
    with open(PALETTE_FILE) as fh:
        return [tuple(int(v) for v in line.split()) for line in fh if line.strip()]


def oklab(c):
    """sRGB (0-255) -> OKLab; palette matching is done here so hues (the violet cloth, the
    gold trim) are not traded for a closer grey the way plain RGB distance does."""
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in c[:3])
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def hue_group(c):
    """neutral (armour greys), red (cape, banners, runes), violet (the cloth under the cape,
    the fur), gold (trim, bone, the blade's rim)."""
    L, a, b = oklab(c)
    chroma = (a * a + b * b) ** 0.5
    if kind(c) == 'gold':
        return 'gold'
    if chroma < 0.03:
        return 'neutral'
    hue = math.degrees(math.atan2(b, a)) % 360
    if 300 <= hue or hue < 45:
        return 'red' if (hue < 45 or hue >= 345) else 'violet'
    return 'violet' if 200 <= hue < 300 else 'neutral'


# palette slots per hue group (minimums; the rest follow the pixel counts)
GROUP_MIN = {'neutral': 10, 'red': 10, 'violet': 8, 'gold': 7}


def build_palette(images):
    """Palette of the opaque pixels of the given final-size images: median cut per hue group
    so the small groups (violet cloth, gold trim) keep their own colours, + the outline."""
    groups = {k: [] for k in GROUP_MIN}
    for im in images:
        data = im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()
        for c in data:
            if c[3]:
                groups[hue_group(c)].append(c[:3])
    free = PALETTE_SIZE - 1 - sum(GROUP_MIN.values())
    total = sum(len(v) for v in groups.values())
    slots = {k: GROUP_MIN[k] + round(free * len(v) / total) for k, v in groups.items()}
    while sum(slots.values()) > PALETTE_SIZE - 1:
        slots[max(slots, key=slots.get)] -= 1
    cols = set()
    for k, px in groups.items():
        if not px:
            continue
        strip = Image.new('RGB', (len(px), 1))
        strip.putdata(px)
        n = min(slots[k], len(set(px)))
        q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = q.getpalette()[:n * 3]
        cols |= {tuple(pal[i * 3:i * 3 + 3]) for i in range(n)}
    cols.discard(OUTLINE)
    return [OUTLINE] + sorted(cols, key=lum)


def save_palette(pal):
    with open(PALETTE_FILE, 'w') as fh:
        fh.write('\n'.join('%d %d %d' % c for c in pal) + '\n')


class Snapper:
    """Nearest palette colour in OKLab."""

    def __init__(self, pal):
        self.pal = pal
        self.lab = [oklab(c) for c in pal]
        self.cache = {}

    def __call__(self, c):
        k = c[:3]
        if k not in self.cache:
            L, a, b = oklab(k)
            i = min(range(len(self.pal)), key=lambda j: (self.lab[j][0] - L) ** 2 + (self.lab[j][1] - a) ** 2
                    + (self.lab[j][2] - b) ** 2)
            self.cache[k] = self.pal[i]
        return self.cache[k]


def outline_mask(im):
    """Work pixels that are the dark outline: near-black and within 2 px of transparency."""
    a = im.getchannel('A').point(lambda v: 255 if v >= 128 else 0)
    near_edge = a.filter(ImageFilter.MinFilter(5)).point(lambda v: 0 if v else 255)
    dark = Image.new('L', im.size, 0)
    p, d, n = im.load(), dark.load(), near_edge.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            c = p[x, y]
            if c[3] >= 128 and n[x, y] and lum(c) < 34:
                d[x, y] = 255
    return dark


def kind(c):
    """Which layer a work pixel belongs to: 'red' (glowing runes, the visor), 'gold' (the
    gold trim, bone, the pale blade rim) or None (the armour and cloth base)."""
    r, g, b = c[:3]
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    L = lum(c)
    if r > 150 and r > g + 70 and r > b + 50:
        return 'red'
    if L > 105 and 0.04 < h < 0.17 and s > 0.12:
        return 'gold'
    if L > 150:
        return 'gold'
    return None


def downscale(work):
    """Work image -> the three layers at final size:
    base  - the median-filtered work image, box-averaged (smooth plates and cloth: the
            concept's texture noise would otherwise snap to speckle);
    gold, red - (coverage, average colour) of the thin bright details, which a plain average
            would blur into the dark base.
    Also returns the outline coverage."""
    W, H = work.size
    assert W % WORK == 0 and H % WORK == 0, (W, H)
    size = (W // WORK, H // WORK)
    base = premul_resize(work.filter(ImageFilter.MedianFilter(MEDIAN)), size, resample=Image.BOX)
    p = work.load()
    masks = {k: Image.new('L', work.size, 0) for k in ('gold', 'red')}
    cols = {k: Image.new('RGBA', work.size, (0, 0, 0, 0)) for k in ('gold', 'red')}
    mp = {k: m.load() for k, m in masks.items()}
    cp = {k: c.load() for k, c in cols.items()}
    for y in range(H):
        for x in range(W):
            c = p[x, y]
            if c[3] >= 128:
                k = kind(c)
                if k:
                    mp[k][x, y] = 255
                    cp[k][x, y] = c
    layers = {k: (masks[k].resize(size, Image.BOX), premul_resize(cols[k], size, resample=Image.BOX))
              for k in masks}
    om = outline_mask(work).resize(size, Image.BOX)
    return base, layers, om


def stylize(work, pal):
    """Final pixel art from a work image (sizes must be multiples of WORK)."""
    base, layers, om = downscale(work)
    snap = Snapper(pal)
    W, H = base.size
    bp, o = base.load(), om.load()
    gm, gc = (v.load() for v in layers['gold'])
    rm, rc = (v.load() for v in layers['red'])
    out = {}
    for y in range(H):
        for x in range(W):
            c = bp[x, y]
            if c[3] < ALPHA_MIN * 255:
                continue
            if rm[x, y] >= RED_MIN * 255:
                out[(x, y)] = snap(rc[x, y])
            elif gm[x, y] >= GOLD_MIN * 255:
                out[(x, y)] = snap(gc[x, y])
            else:
                out[(x, y)] = snap(c)
    for (x, y) in list(out):
        edge = any(q not in out for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        if edge and o[x, y] >= 0.3 * 255:
            out[(x, y)] = OUTLINE
    drop_specks(out)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    q = im.load()
    for (x, y), c in out.items():
        q[x, y] = c + (255,)
    return im


def raw_colours(work):
    """Unsnapped final-size colours (for building the palette): base, with gold/red on top."""
    base, layers, _ = downscale(work)
    out = base.copy()
    p = out.load()
    gm, gc = (v.load() for v in layers['gold'])
    rm, rc = (v.load() for v in layers['red'])
    for y in range(out.height):
        for x in range(out.width):
            if p[x, y][3] >= ALPHA_MIN * 255:
                if rm[x, y] >= RED_MIN * 255:
                    p[x, y] = rc[x, y][:3] + (255,)
                elif gm[x, y] >= GOLD_MIN * 255:
                    p[x, y] = gc[x, y][:3] + (255,)
                else:
                    p[x, y] = p[x, y][:3] + (255,)
            else:
                p[x, y] = (0, 0, 0, 0)
    return out


def components(pix):
    seen, out = set(), []
    for k in pix:
        if k in seen:
            continue
        st, comp = [k], []
        seen.add(k)
        while st:
            a = st.pop()
            comp.append(a)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (a[0] + dx, a[1] + dy)
                    if q in pix and q not in seen:
                        seen.add(q)
                        st.append(q)
        out.append(comp)
    return out


def drop_specks(out):
    """Islands of 1-2 px, and up to 5 px when more than 2 px from the main body."""
    comps = components(out)
    comps.sort(key=len, reverse=True)
    body = set(comps[0]) if comps else set()
    for comp in comps[1:]:
        near = any((x + dx, y + dy) in body for (x, y) in comp for dx in range(-2, 3) for dy in range(-2, 3))
        if len(comp) <= 2 or (len(comp) <= 5 and not near):
            for k in comp:
                out.pop(k)
