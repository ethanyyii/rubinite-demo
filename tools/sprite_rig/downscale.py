"""Build the final-size part library native40/ from the recovered library native/.

    python3 tools/sprite_rig/downscale.py

The character size is final: body (sole to helmet top) = 40 px, plume extra.
Each view is scaled so its own body is exactly 40 rows (the concept views differ by
1-2 px, so a single factor would make the height jump when the knight turns).

Steps per view:
  1. area-average downscale (premultiplied alpha), aligned so the helmet top and the sole
     land exactly on pixel rows;
  2. coverage threshold -> silhouette;
  3. snap every colour to the existing 40-colour palette;
  4. repair: 1 px outline around the silhouette, re-attach or drop specks;
  5. hand patches (PATCHES below) for the design's key marks that averaging blurs.
"""
import os
import sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'native')
DST = os.path.join(HERE, 'native40')
BODY_PX = 40
# body band in the 50 px library: (helmet top row, sole row), measured on the rig's helmet part
BODY = {'front': (11, 59), 'side_right': (14, 63), 'back': (11, 61), 'side_left': (9, 58)}
ALPHA_MIN = 0.45    # coverage needed for a pixel to stay opaque


def load_palette():
    with open(os.path.join(SRC, 'palette.txt')) as fh:
        return [tuple(int(v) for v in line.split()) for line in fh if line.strip()]


PAL = load_palette()
OUTLINE = (13, 8, 9, 255)   # the reference outline colour
_snap = {}


def snap(c):
    k = c[:3]
    if k not in _snap:
        _snap[k] = min(PAL, key=lambda q: (q[0] - k[0]) ** 2 * 3 + (q[1] - k[1]) ** 2 * 4 + (q[2] - k[2]) ** 2 * 2)
    return _snap[k]


def lum(c):
    return (c[0] * 3 + c[1] * 4 + c[2] * 2) / 9


def outline_mask(im):
    """Source pixels that are the dark outline: near-black and touching the outside."""
    W, H = im.size
    p = im.load()
    m = Image.new('L', im.size, 0)
    q = m.load()
    for y in range(H):
        for x in range(W):
            c = p[x, y]
            if not c[3] or lum(c) > 40:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < W and 0 <= ny < H) or p[nx, ny][3] == 0:
                    q[x, y] = 255
                    break
    return m


def downscale(name):
    im = Image.open(os.path.join(SRC, name + '_clean.png')).convert('RGBA')
    top, sole = BODY[name]
    s = BODY_PX / (sole - top + 1)
    r_top = round(top * s)
    W = round(im.width * s)
    H = r_top + BODY_PX + round((im.height - sole - 1) * s)
    # source box that maps helmet top -> row r_top and sole bottom -> row r_top + 40
    # (the source gets a transparent margin so the box never starts at a negative offset)
    pad = 4
    y0 = pad + top - r_top / s
    box = (float(pad), y0, pad + W / s, y0 + H / s)

    def resize(src, mode):
        padded = Image.new(mode, (src.width + 2 * pad, src.height + 2 * pad), 0 if mode == 'L' else (0, 0, 0, 0))
        padded.paste(src, (pad, pad))
        if mode == 'RGBA':
            return padded.convert('RGBa').resize((W, H), Image.BOX, box=box).convert('RGBA')
        return padded.resize((W, H), Image.BOX, box=box)

    return resize(im, 'RGBA'), resize(outline_mask(im), 'L'), s, r_top


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


def build(name):
    small, omask, s, r_top = downscale(name)
    W, H = small.size
    p = small.load()
    om = omask.load()
    out = {}
    for y in range(H):
        for x in range(W):
            c = p[x, y]
            if c[3] >= ALPHA_MIN * 255:
                out[(x, y)] = snap(c) + (255,)
    # 1 px outline: silhouette-edge pixels whose source area was mostly outline go dark again
    for (x, y) in list(out):
        edge = any(q not in out for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        if edge and om[x, y] >= 0.3 * 255 and lum(out[(x, y)]) > lum(OUTLINE):
            out[(x, y)] = OUTLINE
    # stray specks: tiny islands are dropped - any of 1-2 px, and up to 4 px when they sit
    # more than 2 px away from the body (thin strand tips close to the body stay)
    comps = components(out)
    comps.sort(key=len, reverse=True)
    body = set(comps[0])
    for comp in comps[1:]:
        near = any((x + dx, y + dy) in body for (x, y) in comp for dx in range(-2, 3) for dy in range(-2, 3))
        if len(comp) <= 2 or (len(comp) <= 4 and not near):
            for k in comp:
                out.pop(k)
    return out, (W, H), s, r_top


# ------------------------------------------------------------------ hand patches
# palette colours used by the patches (all from palette.txt)
SLIT = (24, 18, 23, 255)       # visor slit / mail shadow
BAR = (144, 130, 123, 255)     # visor bar
BAR_LO = (97, 86, 82, 255)     # visor bar, bottom row (shadow)
RIDGE = (181, 168, 161, 255)   # visor centre ridge
MAIL_LO = (36, 30, 32, 255)    # chain mail dark dot
MAIL_HI = (121, 107, 102, 255)  # chain mail light dot


def repaint(pix, xs, ys, rule):
    """rule(x, y, c) -> new colour or None; outline and blue cloth are never touched."""
    for y in ys:
        for x in xs:
            c = pix.get((x, y))
            if c is None or c == OUTLINE or lum(c) < 14 or (c[2] > c[0] + 25 and c[2] > 60):
                continue
            new = rule(x, y, c)
            if new is not None:
                pix[(x, y)] = new


def patch_front(pix):
    # visor: vertical bars, the design's key mark. Bars on odd columns (centre ridge at 25,
    # the helmet's middle), slits on even columns, last row in shadow.
    repaint(pix, range(20, 32), range(15, 21),
            lambda x, y, c: SLIT if x % 2 == 0 else (RIDGE if x == 25 else (BAR_LO if y == 20 else BAR)))
    # chain mail skirt: averaging turned the fine checker into noise; a regular dot grid
    repaint(pix, range(19, 29), range(36, 40),
            lambda x, y, c: MAIL_LO if (x + y) % 2 == 0 else MAIL_HI)
    # the plume's hanging strand merged into the right horn when averaged; the 50 px sprite
    # has a gap there, so reopen it (otherwise the plume reads as a closed loop)
    pix.pop((36, 11), None)


def patch_side_right(pix):
    # side visor (front of the helmet, facing right): bars on odd columns, slits on even
    repaint(pix, range(22, 29), range(15, 21),
            lambda x, y, c: SLIT if x % 2 == 0 else (BAR_LO if y == 20 else BAR))


def patch_side_left(pix):
    # side visor (facing left)
    repaint(pix, range(1, 8), range(12, 18),
            lambda x, y, c: SLIT if x % 2 == 1 else (BAR_LO if y == 17 else BAR))


PATCHES = {'front': patch_front, 'side_right': patch_side_right, 'side_left': patch_side_left}


def save(pix, size, path):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    for (x, y), c in pix.items():
        im.putpixel((x, y), c)
    im.save(path)


def main():
    os.makedirs(DST, exist_ok=True)
    for name in BODY:
        pix, size, s, r_top = build(name)
        if name in PATCHES:
            PATCHES[name](pix)
        save(pix, size, os.path.join(DST, name + '_clean.png'))
        print(f'{name:10s} scale {s:.4f} size {size} helmet top row {r_top} sole row {r_top + BODY_PX - 1}')
    with open(os.path.join(DST, 'palette.txt'), 'w') as fh:
        fh.write('\n'.join('%d %d %d' % c for c in PAL))


if __name__ == '__main__':
    sys.exit(main())
