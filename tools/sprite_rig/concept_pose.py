"""Poses restored from the concept sheet's action thumbnails.

The walk and most key poses are built by moving the 40 px library's parts (pose_rig.py).
Where the rig cannot make a pose the concept sheet does draw (lying down: H), the pose is
restored from the thumbnail's own pixels instead (animation-review.md §4.6), the same way
the library was made from the big views (extract_reference.py, downscale.py):

  1. crop the thumbnail; the paper background (and the ground shadow, dust, labels) is
     flood-filled from the crop border, so light armour glints inside the dark outline stay;
  2. effects are not part of the character (slash arcs, hit sparks): bright blue-white and
     red-yellow pixels are dropped;
  3. area-average down to the final 40 px scale (premultiplied alpha), coverage threshold;
  4. snap to the 40-colour palette, put the 1 px dark outline back where the source edge was
     outline, drop stray specks.

The same restoration gives the thumbnails' silhouettes at the character's scale, for the
same-scale overlays of the key pose sheet (§4.6).

    python3 tools/sprite_rig/concept_pose.py      # writes a check image of the restorations
"""
import math
import os
import sys

from PIL import Image

import sprites as A
import walk_side as W

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CONCEPT = os.path.join(ROOT, 'docs', 'art-reference', 'player-knight-concept.webp')
OUTLINE = A.OL
ALPHA_MIN = 0.45

# thumbnail boxes on the 1536 x 1024 concept sheet (one figure each)
BOX = {
    'A1': (52, 752, 140, 842), 'B1': (840, 750, 962, 842), 'B2': (955, 750, 1050, 842),
    'C1': (22, 872, 158, 978),
    'C2': (160, 872, 300, 978), 'C3': (288, 872, 432, 978), 'C4': (435, 872, 560, 978),
    'D1': (600, 872, 832, 978), 'D2': (815, 872, 990, 978), 'D3': (985, 872, 1160, 978),
    'E': (1195, 750, 1335, 852), 'F': (1355, 750, 1500, 852), 'G': (1195, 892, 1335, 980),
    'H': (1345, 895, 1512, 982),
}


# captions printed inside a thumbnail's box, blanked before extraction
LABELS = {'A1': [(45, 748, 95, 768)]}


def lum(c):
    return (c[0] * 3 + c[1] * 4 + c[2] * 2) / 9


def is_fx(c):
    """Slash arcs (light blue / white glow) and hit sparks (red, orange, yellow)."""
    r, g, b = c[:3]
    if b > 150 and b > r + 30 and lum(c) > 140:        # light blue glow of a slash
        return True
    if r > 170 and r > b + 60:                          # red / orange / yellow spark
        return True
    return False


def figure(ref):
    """{(x, y): colour} of the figure in the thumbnail, at concept-sheet resolution."""
    im = Image.open(CONCEPT).convert('RGB').crop(BOX[ref])
    Wd, Hd = im.size
    p = im.load()
    for (x0, y0, x1, y1) in LABELS.get(ref, ()):
        # a caption printed inside the thumbnail's box (paper colour over it)
        for y in range(y0 - BOX[ref][1], y1 - BOX[ref][1]):
            for x in range(x0 - BOX[ref][0], x1 - BOX[ref][0]):
                if 0 <= x < Wd and 0 <= y < Hd:
                    p[x, y] = p[0, 0]
    bg = [p[0, 0], p[Wd - 1, 0], p[0, Hd - 1], p[Wd - 1, Hd - 1]]
    paper = tuple(sum(c[i] for c in bg) / 4 for i in range(3))

    def backgroundish(c):
        # paper, the ground shadow (a warm grey, lum ~145) and dust: light, low saturation.
        # Armour greys inside the figure are safe: the fill starts at the crop border and
        # stops at the dark outline
        sat = max(c) - min(c)
        return (lum(c) > 128 and sat < 30) or (lum(c) > 150 and sat < 40) or is_fx(c) or \
            (abs(c[0] - paper[0]) + abs(c[1] - paper[1]) + abs(c[2] - paper[2]) < 60)

    outside = set()
    stack = [(x, y) for x in range(Wd) for y in (0, Hd - 1)] + [(x, y) for y in range(Hd) for x in (0, Wd - 1)]
    while stack:
        x, y = stack.pop()
        if (x, y) in outside or not (0 <= x < Wd and 0 <= y < Hd) or not backgroundish(p[x, y]):
            continue
        outside.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    fig = {(x, y): p[x, y] for x in range(Wd) for y in range(Hd)
           if (x, y) not in outside and not is_fx(p[x, y])}
    # paper seen through a loop of the plume or cape is background too: an enclosed paper-
    # coloured pocket of at least 16 concept pixels (a glint on the armour is 1-2 thumbnail
    # pixels, ~4-8 concept pixels, and stays)
    paperish = {k for k, c in fig.items() if lum(c) > 185 and max(c) - min(c) < 30}
    for comp in _components4(paperish):
        if len(comp) >= 16:
            for k in comp:
                fig.pop(k, None)
    # keep the figure: its largest piece and any sizeable piece touching its box (a strand
    # the thumbnail draws detached). Labels, dust and the neighbouring thumbnail's edge lie
    # outside it
    comps = _components(set(fig))
    comps.sort(key=len, reverse=True)
    keep = set(comps[0])
    bx0, by0, bx1, by1 = extent(dict.fromkeys(comps[0]))
    for c in comps[1:]:
        cx0, cy0, cx1, cy1 = extent(dict.fromkeys(c))
        touches = cx1 >= bx0 - 3 and cx0 <= bx1 + 3 and cy1 >= by0 - 3 and cy0 <= by1 + 3
        inside = cx0 >= bx0 - 3 and cx1 <= bx1 + 3
        if len(c) >= 0.02 * len(comps[0]) and touches and inside:
            keep |= set(c)
    return {k: v for k, v in fig.items() if k in keep}


def _components(pts):
    seen, out = set(), []
    for k in pts:
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
                    if q in pts and q not in seen:
                        seen.add(q)
                        st.append(q)
        out.append(comp)
    return out


def _components4(pts):
    seen, out = set(), []
    for k in pts:
        if k in seen:
            continue
        st, comp = [k], []
        seen.add(k)
        while st:
            a = st.pop()
            comp.append(a)
            for q in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if q in pts and q not in seen:
                    seen.add(q)
                    st.append(q)
        out.append(comp)
    return out


def extent(fig):
    xs = [x for x, _ in fig]
    ys = [y for _, y in fig]
    return min(xs), min(ys), max(xs), max(ys)


def restore(ref, scale, fig=None):
    """The thumbnail's figure at `scale` (output px per concept px), palette-snapped,
    outlined, cleaned. Returns {(x, y): rgba} with (0, 0) at the figure's top-left."""
    fig = fig if fig is not None else figure(ref)
    x0, y0, x1, y1 = extent(fig)
    Ws, Hs = x1 - x0 + 1, y1 - y0 + 1
    src = Image.new('RGBA', (Ws, Hs), (0, 0, 0, 0))
    om = Image.new('L', (Ws, Hs), 0)
    for (x, y), c in fig.items():
        src.putpixel((x - x0, y - y0), c + (255,))
    for (x, y), c in fig.items():
        if lum(c) <= 60 and any(q not in fig for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
            om.putpixel((x - x0, y - y0), 255)
    Wt, Ht = max(1, round(Ws * scale)), max(1, round(Hs * scale))
    small = src.convert('RGBa').resize((Wt, Ht), Image.BOX).convert('RGBA')
    omask = om.resize((Wt, Ht), Image.BOX)
    p, q = small.load(), omask.load()
    out = {}
    for y in range(Ht):
        for x in range(Wt):
            c = p[x, y]
            if c[3] >= ALPHA_MIN * 255:
                out[(x, y)] = W.snap(c)
    for (x, y) in list(out):
        edge = any(n not in out for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        if edge and q[x, y] >= 0.3 * 255 and lum(out[(x, y)]) > lum(OUTLINE):
            out[(x, y)] = OUTLINE
    # a 1 px outline all round, like every part of the library
    ring = {}
    for (x, y) in out:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in out:
                ring[n] = OUTLINE
    out.update(ring)
    comps = _components(set(out))
    comps.sort(key=len, reverse=True)
    body = set(comps[0])
    for comp in comps[1:]:
        near = any((x + dx, y + dy) in body for (x, y) in comp for dx in range(-2, 3) for dy in range(-2, 3))
        if len(comp) <= 2 or (len(comp) <= 4 and not near):
            for k in comp:
                out.pop(k)
    ox = min(x for x, _ in out)
    oy = min(y for _, y in out)
    return {(x - ox, y - oy): c for (x, y), c in out.items()}


def silhouette(ref, height_px=None, length_px=None):
    """The thumbnail's silhouette (set of pixels) scaled to the character: standing figures
    by height (plume included), the lying one by length. (0, 0) = top-left of the figure."""
    fig = figure(ref)
    x0, y0, x1, y1 = extent(fig)
    if length_px:
        s = length_px / (x1 - x0 + 1)
    else:
        s = height_px / (y1 - y0 + 1)
    im = Image.new('L', (x1 - x0 + 1, y1 - y0 + 1), 0)
    for (x, y) in fig:
        im.putpixel((x - x0, y - y0), 255)
    Wt, Ht = max(1, round(im.width * s)), max(1, round(im.height * s))
    sm = im.resize((Wt, Ht), Image.BOX)
    return {(x, y) for x in range(Wt) for y in range(Ht) if sm.getpixel((x, y)) >= 128}


# ------------------------------------------------------------------ lying (N7, from H)
# H is a knight lying face down: helmet at the left, cape over the back, boots at the right.
# Its body is longer for its head than the 40 px library (helmet ~0.3 of the length, the
# standing library ~0.5), so the scale is a compromise: 50 px long keeps the helmet ~15 px
# (the standing side helmet is ~20) and still fits the 56 px canvas; the body behind the
# helmet is ~18 px tall with the cape.
LIE_LENGTH = 50
_LIE = {}


def lying_parts():
    """H restored at LIE_LENGTH: (body, cloth) pixel dicts, head at the left, (0, 0) top-left.
    Cloth = the blue plume and cape with their outline, a layer of its own so it can settle
    or fly when the pose is animated."""
    if 'parts' not in _LIE:
        fig = figure('H')
        x0, y0, x1, y1 = extent(fig)
        px = restore('H', LIE_LENGTH / (x1 - x0 + 1), fig)
        cloth = {k: c for k, c in px.items() if A.is_blue(c)}
        for (x, y), c in px.items():
            if (x, y) not in cloth and lum(c) < 45 and \
                    sum(n in cloth for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) >= 2:
                cloth[(x, y)] = c
        body = {k: c for k, c in px.items() if k not in cloth}
        _LIE['parts'] = (body, cloth)
    return _LIE['parts']


def lying_metrics():
    """Sizes of the restored lying body: length, the body's height behind the helmet (cloth
    left out), the helmet's size. In H the helmet is the round mass filling the left ~1/3 of
    the length (checked on the 12x part image); the body is measured past 40 % of it."""
    body, cloth = lying_parts()
    xs = [x for x, _ in body]
    x0, n = min(xs), max(xs) - min(xs) + 1
    helmet = [(x, y) for (x, y), c in body.items() if x < x0 + 0.36 * n and lum(c) > 45]
    hrows = {}
    for _, y in helmet:
        hrows[y] = hrows.get(y, 0) + 1
    hband = [y for y, k in hrows.items() if k >= 3]
    # armour only, rows with a solid band (>= 3 px): the cape's outline and a few dark-blue
    # shade pixels of the cloth lying on the back are not the body; +2 for its outline
    rest = [(x, y) for (x, y), c in body.items() if x > x0 + 0.40 * n and lum(c) > 45]
    rows = {}
    for _, y in rest:
        rows[y] = rows.get(y, 0) + 1
    band = [y for y, k in rows.items() if k >= 3]
    return dict(length=n, body_h=max(band) - min(band) + 1 + 2,
                helmet_w=max(x for x, _ in helmet) - x0 + 1 + 1,
                helmet_h=max(hband) - min(hband) + 1 + 2)


def lying_frame(head_left=True, airborne=False, canvas=(56, 56, 28, 53)):
    """Lying (or launched) pose on the canvas. Head at the left is H as drawn; the other
    side is its mirror (allowed for lying). The sword is drawn apart (N1), on the floor
    beside the knight; airborne, the body tips head-down and the cloth flies up behind."""
    import sword as SW
    from rig import Layer, R, mat_mul, T
    body, cloth = lying_parts()
    allpx = dict(body)
    allpx.update(cloth)
    Wd = max(x for x, _ in allpx) + 1
    Hd = max(y for _, y in allpx) + 1
    if airborne:
        # the cloth billows upward, more toward its free end (the right: the legs' side);
        # each column is stretched up rather than moved, so nothing opens behind it
        allpx = dict(body)
        for x in {x for x, _ in cloth}:
            col = sorted(y for (cx, y) in cloth if cx == x)
            k = int(round(1 + 3 * x / max(Wd - 1, 1)))
            top = col[0]
            for y in col:
                allpx[(x, y - k)] = cloth[(x, y)]
            for y in range(top - k + 1, top):
                allpx.setdefault((x, y), cloth[(x, top)])
            for y in col:
                allpx.setdefault((x, y), cloth[(x, y)])
        lay = Layer('lie', allpx, (Wd + 8, Hd + 8))
        cx, cy = Wd / 2, Hd / 2
        allpx = lay.render(R(-14, cx, cy))
    if not head_left:
        allpx = {(Wd - 1 - x, y): c for (x, y), c in allpx.items()}
    # small pockets the restoration leaves (a loop of the plume narrower than the paper-
    # pocket rule) close up like any seam
    from rig import close_holes
    Wd2 = max(x for x, _ in allpx) + 2
    Hd2 = max(y for _, y in allpx) + 2
    allpx = close_holes({k: c for k, c in allpx.items() if k[0] >= 0 and k[1] >= 0}, Wd2, Hd2, max_size=8)
    Wc, Hc, ax, gy = canvas
    xs = [x for x, _ in allpx]
    ys = [y for _, y in allpx]
    dx = int(round(ax - (min(xs) + max(xs)) / 2))
    dy = gy - max(ys)
    out = {(x + dx, y + dy): c for (x, y), c in allpx.items()}
    if not airborne:
        # the dropped sword lies on the floor at the knight's side, hilt by the hand, blade
        # toward the head; drawn over the body's lower edge (it lies nearer the camera)
        sgn = 1 if head_left else -1
        hand = (ax + sgn * 3, gy - 1.5)
        spx, _ = SW.sword_pixels(hand, (-sgn, 0.0), 1.0, 1)
        sink = max(y for _, y in spx) - gy
        out.update({(x, y - max(sink, 0)): c for (x, y), c in spx.items()})
    return out


if __name__ == '__main__':
    out = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch0')
    os.makedirs(out, exist_ok=True)
    tiles = []
    for ref in ('H', 'G', 'F', 'C2', 'D1'):
        fig = figure(ref)
        x0, y0, x1, y1 = extent(fig)
        s = (48 / (x1 - x0 + 1)) if ref == 'H' else (50 / (y1 - y0 + 1))
        px = restore(ref, s, fig)
        Wd = max(x for x, _ in px) + 1
        Hd = max(y for _, y in px) + 1
        im = Image.new('RGBA', (Wd + 4, Hd + 4), (226, 219, 204, 255))
        for (x, y), c in px.items():
            im.putpixel((x + 2, y + 2), c)
        tiles.append(im.resize((im.width * 6, im.height * 6), Image.NEAREST))
    sheet = Image.new('RGBA', (sum(t.width + 8 for t in tiles), max(t.height for t in tiles)), (30, 30, 34, 255))
    x = 0
    for t in tiles:
        sheet.alpha_composite(t, (x, 0))
        x += t.width + 8
    sheet.save(os.path.join(out, 'concept_restore_check.png'))
    print('wrote', sheet.size)
