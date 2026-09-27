"""Rebuild the part library (native/*_clean.png + palette.txt) from the concept sheet.

    python3 tools/sprite_rig/extract_reference.py [out_dir]     # default: tools/sprite_rig/native

The concept sheet is AI-generated pixel art on an irregular grid, with non-square pixels
(about 4.0 wide x 4.4 tall on the sheet). Steps:
  1. find the pixel-cell boundaries per axis (dynamic programming on edge strength) and
     take the median colour of each cell's interior;
  2. remove the paper background by flood fill from the border;
  3. squeeze out the most redundant columns so the width/height ratio matches the sheet;
  4. drop the ground shadow and stray specks, then map all four views onto one shared
     40-colour palette.
"""
import os
import sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'art-reference', 'player-knight-concept.webp')
BG = (237, 230, 218)          # paper colour of the concept sheet
SHADOW = (170, 161, 148)      # ground-shadow colour under the feet
# view name -> box on the concept sheet
VIEWS = [('front', (18, 118, 300, 410)), ('side_left', (318, 118, 522, 410)),
         ('back', (540, 118, 762, 410)), ('side_right', (762, 118, 990, 410))]
PALETTE_ORDER = ['front', 'side_right', 'back', 'side_left']


# ------------------------------------------------------------------ 1-2. grid recovery
def edge_profile(px, box, axis):
    x0, y0, x1, y1 = box
    prof = [0.0]
    if axis == 'x':
        for x in range(x0 + 1, x1):
            prof.append(sum(sum(abs(px[x, y][i] - px[x - 1, y][i]) for i in range(3)) for y in range(y0, y1)))
    else:
        for y in range(y0 + 1, y1):
            prof.append(sum(sum(abs(px[x, y][i] - px[x, y - 1][i]) for i in range(3)) for x in range(x0, x1)))
    return prof


def boundaries(prof, lo=3, hi=6, target=4.39, pen=0.15):
    """Cell boundaries maximising edge strength, cells lo..hi px wide (irregular grid)."""
    n = len(prof)
    mean = sum(prof) / n
    NEG = -1e18
    best = [NEG] * n
    prev = [-1] * n
    for k in range(0, hi + 1):
        if k < n:
            best[k] = prof[k]
    for k in range(1, n):
        for g in range(lo, hi + 1):
            j = k - g
            if j < 0 or best[j] == NEG:
                continue
            v = best[j] + prof[k] - pen * mean * (g - target) ** 2
            if v > best[k]:
                best[k] = v
                prev[k] = j
    k = max(range(n - hi, n), key=lambda i: best[i])
    out = []
    while k >= 0:
        out.append(k)
        k = prev[k]
    return out[::-1]


def near_bg(c, tol=46):
    return abs(c[0] - BG[0]) + abs(c[1] - BG[1]) + abs(c[2] - BG[2]) < tol


def light_neutral(c):
    r, g, b = c[:3]
    return min(r, g, b) > 150 and max(r, g, b) - min(r, g, b) < 40


def extract(px, box):
    """Returns (native sprite, width/height ratio of one cell on the sheet)."""
    x0, y0, x1, y1 = box
    bx = boundaries(edge_profile(px, box, 'x'))
    by = boundaries(edge_profile(px, box, 'y'))
    gx = [b2 - b1 for b1, b2 in zip(bx, bx[1:])]
    gy = [b2 - b1 for b1, b2 in zip(by, by[1:])]
    W, H = len(bx) - 1, len(by) - 1
    out = Image.new('RGBA', (W, H))
    for j in range(H):
        for i in range(W):
            xa, xb = x0 + bx[i], x0 + bx[i + 1]
            ya, yb = y0 + by[j], y0 + by[j + 1]
            xs = range(xa + 1, xb - 1) if xb - xa > 2 else range(xa, xb)
            ys = range(ya + 1, yb - 1) if yb - ya > 2 else range(ya, yb)
            s = sorted((px[x, y] for x in xs for y in ys), key=sum)
            out.putpixel((i, j), s[len(s) // 2] + (255,))
    o = out.load()
    stack = [(x, y) for x in range(W) for y in (0, H - 1)] + [(x, y) for y in range(H) for x in (0, W - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < W and 0 <= y < H):
            continue
        seen.add((x, y))
        c = o[x, y]
        if c[3] and (near_bg(c) or light_neutral(c)):
            o[x, y] = (0, 0, 0, 0)
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    out = out.crop(out.getbbox())
    ratio = round(sum(gx) / len(gx), 3) / round(sum(gy) / len(gy), 3)
    return out, ratio


# ------------------------------------------------------------------ 3. aspect correction
def squeeze(im, ratio):
    """Drop the most redundant columns until width = round(width * ratio)."""
    def col(x):
        return [im.getpixel((x, y)) for y in range(im.height)]

    def diff(a, b):
        s = 0
        for p, q in zip(a, b):
            if p[3] == 0 and q[3] == 0:
                continue
            if (p[3] == 0) != (q[3] == 0):
                s += 300
            else:
                s += sum(abs(p[i] - q[i]) for i in range(3))
        return s

    cols = [col(x) for x in range(im.width)]
    target = round(im.width * ratio)
    while len(cols) > target:
        best = None
        for x in range(1, len(cols) - 1):
            c = min(diff(cols[x], cols[x - 1]), diff(cols[x], cols[x + 1]))
            if best is None or c < best[0]:
                best = (c, x)
        del cols[best[1]]
    out = Image.new('RGBA', (len(cols), im.height))
    for x, c in enumerate(cols):
        for y, p in enumerate(c):
            out.putpixel((x, y), p)
    return out


# ------------------------------------------------------------------ 4. cleanup + palette
def components(im):
    W, H = im.size
    p = im.load()
    seen = set()
    out = []
    for y in range(H):
        for x in range(W):
            if p[x, y][3] and (x, y) not in seen:
                st = [(x, y)]
                seen.add((x, y))
                c = []
                while st:
                    a, b = st.pop()
                    c.append((a, b))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            q = (a + dx, b + dy)
                            if 0 <= q[0] < W and 0 <= q[1] < H and q not in seen and p[q][3]:
                                seen.add(q)
                                st.append(q)
                out.append(c)
    return out


def clean(im):
    W, H = im.size
    p = im.load()
    # ground shadow: shadow-coloured pixels in the bottom 4 rows that touch transparency
    changed = True
    while changed:
        changed = False
        for y in range(H - 4, H):
            for x in range(W):
                c = p[x, y]
                if not c[3]:
                    continue
                if sum(abs(c[i] - SHADOW[i]) for i in range(3)) < 30:
                    nb = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
                    if any(not (0 <= a < W and 0 <= b < H) or p[a, b][3] == 0 for a, b in nb):
                        p[x, y] = (0, 0, 0, 0)
                        changed = True
    # stray specks: islands of 1-2 px apart from the main mass
    cs = components(im)
    cs.sort(key=len, reverse=True)
    for c in cs[1:]:
        if len(c) <= 2:
            for a, b in c:
                p[a, b] = (0, 0, 0, 0)
    return im.crop(im.getbbox())


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'native')
    os.makedirs(out_dir, exist_ok=True)
    sheet = Image.open(SRC).convert('RGB')
    px = sheet.load()
    ims = {}
    for name, box in VIEWS:
        raw, ratio = extract(px, box)
        ims[name] = clean(squeeze(raw, ratio))
        print(name, 'cell w/h', round(ratio, 4), 'native', raw.size, '->', ims[name].size)
    allpx = []
    for name in PALETTE_ORDER:
        im = ims[name]
        data = im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()
        allpx += [c[:3] for c in data if c[3]]
    strip = Image.new('RGB', (len(allpx), 1))
    strip.putdata(allpx)
    q = strip.quantize(colors=40, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:40 * 3]
    PAL = [tuple(pal[i * 3:i * 3 + 3]) for i in range(40)]
    cache = {}
    for name in PALETTE_ORDER:
        im = ims[name]
        p = im.load()
        for y in range(im.height):
            for x in range(im.width):
                c = p[x, y]
                if c[3]:
                    k = c[:3]
                    if k not in cache:
                        cache[k] = min(PAL, key=lambda q: (q[0] - k[0]) ** 2 * 3 + (q[1] - k[1]) ** 2 * 4 + (q[2] - k[2]) ** 2 * 2)
                    p[x, y] = cache[k] + (255,)
        im.save(os.path.join(out_dir, name + '_clean.png'))
    with open(os.path.join(out_dir, 'palette.txt'), 'w') as fh:
        fh.write('\n'.join('%d %d %d' % c for c in PAL))
    print('wrote', out_dir)


if __name__ == '__main__':
    main()
