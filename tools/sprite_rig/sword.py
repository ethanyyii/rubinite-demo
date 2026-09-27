"""The sword at any angle (new part N1).

The reference blade cannot be rotated (a 1-2 px blade resampled at a new angle gets thicker,
thinner or brighter: animation-review.md §4.4), so every angle is drawn afresh with the
reference's own colours, following how the 40 px library draws it:

- blade: a 1 px core line (edge-on) or 2 px (flat toward the camera); the lit side uses the
  reference's blade highlights (palette 0 / 1 / 2), the shadow side its mid greys (10 / 11 / 13);
- a dark outline (palette 35) all round, like the library blade;
- crossguard across the blade, dark steel with lighter ends; grip dark brown; pommel.

Coordinates are output-frame pixels (floats). `hand` is the centre of the fist that holds
the grip; the guard sits just past the fist along `d`."""
import math

import walk_side as W

P = W.PALETTE
OUT = P[35] + (255,)
LIT = [P[0] + (255,), P[1] + (255,), P[2] + (255,)]           # near the guard -> near the tip
SHADE = [P[11] + (255,), P[10] + (255,), P[13] + (255,)]
GUARD_END = P[2] + (255,)
GUARD_MID = P[14] + (255,)
GRIP = [P[21] + (255,), P[13] + (255,)]
POMMEL = P[4] + (255,)

BLADE = 15.0       # blade length at full length (40 px library: 15-16 px past the guard)
GUARD_AT = 2.0     # guard centre, px past the fist centre
GUARD_HALF = 2     # crossguard reaches this many px each side (5 px wide, like the library)
GRIP_BACK = 2.0    # pommel end, px behind the fist centre (one hand); two hands: 4.5


def line(x0, y0, x1, y1):
    """8-connected pixel line without L-shaped corners (pixel-perfect)."""
    x0, y0, x1, y1 = (int(math.floor(v)) for v in (x0, y0, x1, y1))
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    pts = [(x0, y0)]
    while (x0, y0) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
        pts.append((x0, y0))
    # drop the middle pixel of any L corner (a-b-c where a and c touch diagonally)
    out = []
    for p in pts:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if abs(a[0] - p[0]) == 1 and abs(a[1] - p[1]) == 1 and (b[0] == a[0] or b[1] == a[1]):
                out.pop()
        out.append(p)
    return out


def sword_pixels(hand, d, length=1.0, width=2, grip_back=GRIP_BACK, bright=False):
    """Pixels of the whole sword. d = screen direction of the blade (any length);
    length = on-screen fraction of the full blade (foreshortening toward / away from the
    camera). bright = both rows of a 2 px blade in the lit colours: a blade held flat in
    front of the dark armour (the front-view guard) reads as a light bar, not as one more
    glint among the armour's speckles. Returns {(x, y): colour} and the blade's pixel set."""
    n = math.hypot(*d) or 1.0
    ux, uy = d[0] / n, d[1] / n
    hx, hy = hand
    gx, gy = hx + ux * GUARD_AT, hy + uy * GUARD_AT
    L = max(1.0, BLADE * length)
    core = line(gx + ux * 1.0, gy + uy * 1.0, gx + ux * L, gy + uy * L)
    steep = abs(uy) > abs(ux)
    px = {}
    blade = set()
    for i, (x, y) in enumerate(core):
        t = i / max(1, len(core) - 1)
        lit = LIT[0] if t < 0.45 else LIT[1] if t < 0.85 else LIT[2]
        if i % 5 == 3 and t < 0.85:
            lit = LIT[1]
        if bright:
            lit = LIT[1] if (i % 5 == 3 or t >= 0.85) else LIT[0]
        px[(x, y)] = lit
        blade.add((x, y))
        if width == 2 and i < len(core) - 1:
            # the shadow side is away from the light (top-left): right of a steep blade,
            # under a shallow one
            q = (x + 1, y) if steep else (x, y + 1)
            if q not in px:
                px[q] = LIT[1] if bright else SHADE[i % 3]
                blade.add(q)
    # crossguard: a short bar across the blade
    perp = (-uy, ux)
    ends = line(gx - perp[0] * GUARD_HALF, gy - perp[1] * GUARD_HALF,
                gx + perp[0] * GUARD_HALF, gy + perp[1] * GUARD_HALF)
    for j, q in enumerate(ends):
        px[q] = GUARD_END if j in (0, len(ends) - 1) else GUARD_MID
    # grip (mostly under the fist) and pommel
    grip = line(gx - ux * 1.0, gy - uy * 1.0, hx - ux * grip_back, hy - uy * grip_back)
    for j, q in enumerate(grip):
        if q not in px:
            px[q] = GRIP[j % 2]
    pm = (int(math.floor(hx - ux * (grip_back + 1.0))), int(math.floor(hy - uy * (grip_back + 1.0))))
    if pm not in px:
        px[pm] = POMMEL
    # dark outline round everything
    ring = {}
    for (x, y) in px:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in px:
                ring[q] = OUT
    ring.update(px)
    return ring, blade
