"""The arena's standing things (2026-10-05): ruins, pillars, banners, trees, rubble, swords; 2026-10-06 braziers,
stones, ferns, grass, logs, the old king's head, the fallen challengers' markers.

Every piece is drawn here in the arena's pixel style (dark 1 px outline, stone in blocks lit from the upper
right, moss on what faces up, ivy hanging) and returns (Canvas, anchor): the anchor is the pixel that sits
on the floor at the piece's world position (its base, for the y-sort). Designed for this fight, not copied
from the concept art (the user, 2026-10-05: the concept's place is not a place to fight in - same mood,
but a fighting ground): the north side stands tall behind the court and never covers a fighter, the sides
and the south only knee-high things, the four pillars stay where the fight's collision has them."""
import math
import random

import pix as P


# ------------------------------------------------------------------ masonry
def masonry(c, mask, seed, bh=7, bw=(11, 17), tone=4.2, top_rows=None, light=True, mossy=0.0, shade=None):
    """Fill `mask` (set of pixels) with courses of stone blocks: mortar lines, each block its own tone,
    lit top and right edges, a darker bottom edge; `mossy` puts moss on the blocks' tops."""
    rnd = random.Random(seed)
    if not mask:
        return
    ys = [y for _, y in mask]
    y0 = min(ys)
    rows = {}
    for (x, y) in mask:
        rows.setdefault(y, []).append(x)
    # block grid: course k spans rows [y0 + k*bh, ...), joints staggered per course
    joints = {}
    for k in range((max(ys) - y0) // bh + 2):
        xs, x = [], -40 + rnd.randint(0, bw[1])
        while x < 2000:
            xs.append(x)
            x += rnd.randint(*bw)
        joints[k] = xs
    blk = {}
    for (x, y) in mask:
        k = (y - y0) // bh
        j = 0
        js = joints[k]
        lo, hi = 0, len(js) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if js[mid] <= x:
                lo = mid
            else:
                hi = mid - 1
        blk[(x, y)] = (k, lo)
    for (x, y), b in blk.items():
        k, j = b
        up = blk.get((x, y - 1)) != b
        down = blk.get((x, y + 1)) != b
        right = blk.get((x + 1, y)) != b
        left = blk.get((x - 1, y)) != b
        if (down and (x, y + 1) in blk) or (right and (x + 1, y) in blk):
            c.set(x, y, P.STONE[1])
            continue
        h = P.hash01(k, j, seed)
        t = tone + (h - 0.5) * 1.3 + (P.value_noise(x, y, 2.5, seed) - 0.5) * 0.8
        if shade is not None:
            t += shade(x, y)
        if light:
            if up:
                t += 1.0
            elif right:
                t += 0.5
            if left:
                t -= 0.5
        if mossy and up and P.hash01(x, y, seed + 9) < mossy:
            c.set(x, y, P.ramp(P.MOSS, 3.5 + h, x, y, 'grain'))
            continue
        c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))


def top_face(c, pts, seed, tone=5.2, moss=0.55):
    """The upward face of a wall or broken top, seen from above: lighter, mossy."""
    for (x, y) in pts:
        n = P.fbm(x, y, 5, seed, 2)
        if n > 1.0 - moss:
            c.set(x, y, P.ramp(P.MOSS, 3.0 + (n - 0.5) * 4, x, y, 'grain'))
        else:
            c.set(x, y, P.ramp(P.STONE, tone + (n - 0.5) * 2, x, y, 'grain'))


def ivy(c, x0, y0, length, seed, sway=1.0, density=0.75):
    """A strand of ivy hanging from (x0, y0): a wavering stem with leaf clusters, darker in shade."""
    rnd = random.Random(seed)
    x = float(x0)
    for i in range(length):
        y = y0 + i
        x += math.sin(i * 0.35 + seed) * 0.35 * sway + rnd.uniform(-0.25, 0.25)
        xi = int(round(x))
        c.set(xi, y, P.VINE[1])
        if rnd.random() < density:
            for dx, dy in ((-1, 0), (1, 0), (0, 1), (-1, 1), (1, -1)):
                if rnd.random() < 0.55:
                    t = 2.0 + rnd.random() * 2.2 + (0.8 if dx > 0 else 0)
                    c.set(xi + dx, y + dy, P.ramp(P.VINE, t, xi + dx, y + dy, 'grain'))


def moss_drip(c, pts, seed, amount=0.25):
    rnd = random.Random(seed)
    for (x, y) in pts:
        if rnd.random() < amount:
            for k in range(rnd.randint(1, 3)):
                if c.opaque(x, y + k):
                    c.set(x, y + k, P.ramp(P.MOSS, 2.5 + rnd.random() * 2, x, y + k, 'grain'))


def jagged_top(x0, x1, y_base, rough, seed, step=(3, 7)):
    """A broken top edge from x0 to x1 around row y_base: list of (x, y) points."""
    rnd = random.Random(seed)
    pts, x = [], x0
    while x < x1:
        pts.append((x, y_base + rnd.randint(-rough, rough)))
        x += rnd.randint(*step)
    pts.append((x1, y_base + rnd.randint(-rough, rough)))
    return pts


def finish(c):
    c.outline()
    return c


# ------------------------------------------------------------------ pieces
def pillar(height, seed, width=33):
    """A broken column on its plinth (ArenaGeometry.PILLARS: the collision is the plinth's round foot).
    Fluted shaft lit from the right, drums, a broken top seen from above, moss and ivy."""
    pad = 10
    W, H = width + 2 * pad + 8, int(height) + 40
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 8
    rnd = random.Random(seed)
    # plinth: a squat square base, its top seen from above
    pl_w = width + 8
    for y in range(ay - 9, ay + 1):
        for x in range(ax - pl_w // 2, ax + pl_w // 2 + 1):
            fx = (x - (ax - pl_w // 2)) / pl_w
            t = 3.0 + fx * 1.6 + (P.value_noise(x, y, 2.5, seed) - 0.5) * 0.8
            if y <= ay - 7:
                t += 1.6
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    # shaft: a cylinder
    r = width / 2.0
    top_y = ay - 9 - int(height) + 6
    broken = jagged_top(int(ax - r), int(ax + r), top_y, 5, seed + 1, (3, 6))

    def top_at(x):
        for (xa, ya), (xb, yb) in zip(broken, broken[1:]):
            if xa <= x <= xb:
                return ya + (yb - ya) * (x - xa) / max(1, xb - xa)
        return top_y
    flutes = 7
    for x in range(int(ax - r), int(ax + r) + 1):
        u = (x - ax) / r                     # -1 .. 1 across the shaft
        if abs(u) > 1:
            continue
        light = 0.5 + 0.5 * u                 # lit from the right
        ty = int(top_at(x))
        for y in range(ty, ay - 8):
            fl = math.cos((math.asin(max(-1, min(1, u))) / math.pi * 2 + 1) * flutes * math.pi)
            t = 2.4 + light * 3.0 + fl * 0.45 + (P.value_noise(x, y, 3, seed + 2) - 0.5) * 0.7
            drum = (y - ty) % 22 == 21
            if drum:
                t -= 1.4
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
        # the broken top seen from above: a lighter rough face
        for k in range(3):
            if rnd.random() < 0.8:
                c.set(x, ty - k + 2, P.ramp(P.STONE, 5.2 + light, x, ty, 'grain'))
    # moss on the plinth and the shaft's foot, the shaded side
    for x in range(int(ax - r) - 4, int(ax + r) + 5):
        for y in range(ay - 14, ay - 4):
            if c.opaque(x, y) and P.fbm(x, y, 4, seed + 3) > 0.56 - (0.1 if x < ax else 0):
                c.set(x, y, P.ramp(P.MOSS, 2.5 + rnd.random() * 1.5, x, y, 'grain'))
    # ivy from the broken top down the shaded side
    for i in range(rnd.randint(2, 3)):
        sx = int(ax - r * rnd.uniform(0.2, 0.95))
        ivy(c, sx, int(top_at(sx)) + 2, rnd.randint(int(height * 0.3), int(height * 0.8)), seed + 10 + i)
    finish(c)
    return c, (ax, ay)


def wall(width, height, seed, window=True):
    """A ruined wall segment facing the court: courses of blocks, a stepped broken top whose upper face
    shows, a slit window, moss and ivy. Anchor: the middle of its foot."""
    W, H = width + 16, height + 30
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 6
    rnd = random.Random(seed)
    x0, x1 = 8, 8 + width
    top = jagged_top(x0, x1, ay - height, height // 4, seed, (6, 14))
    # stepped: each run of the top is flat (a course broke off), with a few blocks sticking up
    face = set()
    tops = []
    for (xa, ya), (xb, yb) in zip(top, top[1:]):
        y = min(ya, yb)
        for x in range(xa, xb):
            for yy in range(y, ay + 1):
                face.add((x, yy))
            tops.append((x, y))
    if window:
        wx = x0 + width // 2 + rnd.randint(-width // 6, width // 6)
        for x in range(wx - 3, wx + 4):
            for y in range(ay - height + 18, ay - height // 2 + 4):
                face.discard((x, y))
    masonry(c, face, seed, mossy=0.25)
    # window: dark inside, its sill lit
    if window:
        for x in range(wx - 3, wx + 4):
            for y in range(ay - height + 18, ay - height // 2 + 4):
                c.set(x, y, P.LEAF[1] if y > ay - height + 21 else P.STONE[0])
            c.set(x, ay - height // 2 + 4, P.STONE[6])
    # the upper faces of the broken courses (seen from above): 3 px strips
    top_pts = [(x, y - k) for (x, y) in tops for k in range(1, 4)]
    top_face(c, top_pts, seed + 4)
    moss_drip(c, [(x, y) for (x, y) in tops], seed + 5, 0.3)
    for i in range(rnd.randint(7, 11)):
        sx = rnd.randint(x0 + 3, x1 - 3)
        sy = min(y for (x, y) in tops if abs(x - sx) <= 1) if any(abs(x - sx) <= 1 for (x, y) in tops) else ay - height
        ivy(c, sx, sy, rnd.randint(height // 3, height - 6), seed + 20 + i)
    # rubble at the foot
    rubble_into(c, ax, ay, width // 2 + 6, 7, seed + 30, n=width // 5)
    finish(c)
    return c, (ax, ay)


def rubble_into(c, cx, cy, rx, ry, seed, n=8, size=(3, 7)):
    """Fallen blocks heaped at (cx, cy): small bevelled stones."""
    rnd = random.Random(seed)
    stones = sorted(((cx + rnd.uniform(-rx, rx), cy + rnd.uniform(-ry, ry * 0.4)) for _ in range(n)), key=lambda p: p[1])
    for i, (sx, sy) in enumerate(stones):
        w = rnd.randint(*size) + 2
        h = max(2, int(w * rnd.uniform(0.5, 0.8)))
        pts = P.blob(sx, sy - h / 2, w / 2, h / 2, seed + i, rough=0.18, n=8)
        cell = set(P.poly_fill(pts))
        if not cell:
            continue
        ymin = min(y for _, y in cell)
        for (x, y) in cell:
            t = 3.4 + (1.6 if y - ymin < 2 else 0) + (0.6 if x > sx else -0.3) + (P.value_noise(x, y, 2, seed) - 0.5)
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))


def arch(seed, span=70, pier_w=26, h_left=150, h_right=96):
    """A broken archway: two piers, the left still carrying part of its arch, the right broken off.
    Seen through it: dark forest (the ground behind is the backdrop). Anchor: the middle of its foot."""
    W = span + 2 * pier_w + 40
    H = h_left + 50
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 6
    rnd = random.Random(seed)
    lx0 = ax - span // 2 - pier_w
    rx0 = ax + span // 2
    spring = ay - h_left + span // 2 + 14          # where the arch starts on the left pier
    face = set()
    for x in range(lx0, lx0 + pier_w):
        for y in range(ay - h_left + 10, ay + 1):
            face.add((x, y))
    rtop = jagged_top(rx0, rx0 + pier_w, ay - h_right, 6, seed + 1, (4, 8))
    rtops = []
    for (xa, ya), (xb, yb) in zip(rtop, rtop[1:]):
        for x in range(xa, xb):
            y = int(ya + (yb - ya) * (x - xa) / max(1, xb - xa))
            rtops.append((x, y))
            for yy in range(y, ay + 1):
                face.add((x, yy))
    masonry(c, face, seed, bh=8, bw=(10, 14), mossy=0.2)
    # the arch ring: voussoirs from the left pier, broken a third of the way across
    cx_, cy_ = ax, spring
    R0, R1 = span / 2 + 0.5, span / 2 + 12
    ring = []
    for y in range(cy_ - int(R1) - 2, cy_ + 1):
        for x in range(lx0, ax + 10):
            dx, dy = x - cx_, (y - cy_) * 1.0
            d = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(-dy, dx))     # 180 = left, 90 = top
            if R0 <= d <= R1 and ang >= 108 and y <= cy_:
                ring.append((x, y, ang, d))
    for (x, y, ang, d) in ring:
        k = int((ang - 108) / 9)
        joint = abs(((ang - 108) / 9) - round((ang - 108) / 9)) < 0.08 and d > R0 + 1
        if joint:
            c.set(x, y, P.STONE[1])
            continue
        t = 4.0 + P.hash01(k, seed) * 1.2 + (1.0 if d > R1 - 2 else 0) + (P.value_noise(x, y, 2.5, seed) - 0.5) * 0.7
        c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    # the broken end of the arch: jagged, with a block hanging
    # tops (seen from above)
    top_face(c, [(x, ay - h_left + 10 - k) for x in range(lx0, lx0 + pier_w) for k in range(1, 4)], seed + 2)
    top_face(c, [(x, y - k) for (x, y) in rtops for k in range(1, 3)], seed + 3)
    for i in range(6):
        ivy(c, lx0 + 2 + i * 4, ay - h_left + 12, rnd.randint(40, 120), seed + 40 + i)
    for i in range(3):
        ivy(c, rx0 + 3 + i * 8, min(y for _, y in rtops) + 2, rnd.randint(30, 70), seed + 50 + i)
    ring_pts = [(x, y) for (x, y, a, d) in ring if d > R1 - 1.5]
    for i in range(5):
        if ring_pts:
            x, y = ring_pts[rnd.randrange(len(ring_pts))]
            ivy(c, x, y, rnd.randint(14, 40), seed + 60 + i, density=0.9)
    rubble_into(c, ax + span // 4, ay, span // 2, 6, seed + 70, n=10, size=(4, 9))
    finish(c)
    return c, (ax, ay)


def column(height, seed, width=22):
    """A lone broken column on the north side (no collision: it stands behind the court)."""
    return pillar(height, seed, width=width)


def tree(seed, trunk=34, height=330):
    """A big old tree: a flaring trunk with roots over the stones, bark streaks, moss on the shade side.
    The crown is above the screen; the canopy's shade is in the floor and the foreground leaves."""
    W, H = trunk * 3 + 40, height + 20
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 10
    rnd = random.Random(seed)
    for y in range(0, ay + 1):
        flare = 1.0 + 1.6 * max(0.0, (y - (ay - 40)) / 40.0) ** 2
        half = trunk / 2 * flare + math.sin(y * 0.07 + seed) * 1.5
        for x in range(int(ax - half), int(ax + half) + 1):
            u = (x - ax) / half
            light = 0.5 + 0.5 * u
            streak = P.value_noise(x * 3.0, y * 0.35, 4, seed)
            t = 1.2 + light * 2.6 + (streak - 0.5) * 2.0
            if u < -0.2 and P.fbm(x, y, 7, seed + 1) > 0.5:
                c.set(x, y, P.ramp(P.MOSS, 1.5 + light * 2, x, y, 'grain'))
            else:
                c.set(x, y, P.ramp(P.BARK, t, x, y, 'grain'))
    # roots spreading over the floor (they lie on the ground: drawn into the base)
    for i in range(5):
        a = rnd.uniform(-2.6, -0.5) if i % 2 else rnd.uniform(0.5, 2.6)
        x, y = float(ax + math.cos(a) * trunk * 0.6), float(ay - 4)
        th = 5.0
        for k in range(rnd.randint(18, 34)):
            x += math.cos(a) * 1.2
            y += 0.25 + math.sin(k * 0.4) * 0.2
            th = max(1.5, th - 0.12)
            for d in range(int(th)):
                c.set(int(x), int(y) - d, P.ramp(P.BARK, 1.5 + d * 0.6, int(x), int(y) - d, 'grain'))
    finish(c)
    return c, (ax, ay)


def banner(seed, width=22, length=64, burnt=0.0):
    """A torn red banner of the fallen kingdom, gold emblem, hanging from a bar. burnt 0..1: eaten from the
    bottom up, the burnt edge black with glowing embers (the second phase)."""
    W, H = width + 12, length + 14
    c = P.Canvas(W, H)
    rnd = random.Random(seed)
    x0 = 6
    # the bar
    for x in range(x0 - 3, x0 + width + 3):
        c.set(x, 4, P.BARK[3])
        c.set(x, 5, P.BARK[1])
    bottom = [length + 6 - (rnd.randint(0, 14) if (x - x0) % 5 < 3 else rnd.randint(4, 20)) for x in range(width)]
    cut = [int(6 + length * (1.0 - burnt) + rnd.randint(-3, 3)) if burnt > 0 else 10 ** 6 for _ in range(width)]
    for i in range(width):
        x = x0 + i
        fold = math.sin(i / width * math.pi * 3 + seed) * 0.9
        for y in range(6, min(bottom[i], cut[i]) + 1):
            hole = P.value_noise(x, y, 3, seed + 3) > 0.84 and y > 20
            if hole:
                continue
            sway = int(round(math.sin(y * 0.08 + seed) * 1.2 * (y / length)))
            t = 2.0 + fold + (0.6 if i > width * 0.6 else 0) + (P.value_noise(x, y, 2, seed) - 0.5) * 0.6
            c.set(x + sway, y, P.ramp(P.BANNER, t, x + sway, y, 'grain'))
    # emblem: a crown over a flame, in tarnished gold
    ex, ey = x0 + width // 2, 20
    emblem = [(0, -6), (-3, -5), (3, -5), (-3, -4), (0, -4), (3, -4), (-3, -3), (-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3), (3, -3),
              (0, 0), (-1, 1), (0, 1), (1, 1), (-2, 2), (0, 2), (2, 2), (-1, 3), (0, 3), (1, 3), (0, 4), (0, 5)]
    if burnt < 0.7:
        for dx, dy in emblem:
            if c.opaque(ex + dx, ey + dy):
                c.set(ex + dx, ey + dy, P.GOLD[2 if dx >= 0 else 1])
    if burnt > 0:
        # the burnt edge: black, a row of embers
        for i in range(width):
            y = min(bottom[i], cut[i])
            for k in range(3):
                if c.opaque(x0 + i, y - k):
                    c.set(x0 + i, y - k, P.CHAR[1] if k else P.EMBER[2 if rnd.random() < 0.5 else 1])
    finish(c)
    return c, (6 + width // 2, 4)


def pole(height, seed):
    """A banner pole: an old iron-shod wooden post leaning a little, its foot in a block."""
    W, H = 20, height + 12
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    lean = 0.04
    for y in range(ay - height, ay + 1):
        x = ax + (ay - y) * lean
        for d in (-1, 0, 1):
            t = 2.2 + d * 1.0 + (P.value_noise(x, y, 3, seed) - 0.5)
            c.set(int(round(x)) + d, y, P.ramp(P.BARK, t, int(x) + d, y, 'grain'))
    for y in range(ay - height, ay - height + 3):
        x = ax + (ay - y) * lean
        for d in range(-6, 7):
            c.set(int(round(x)) + d, y, P.STEEL[1 if y > ay - height else 2])
    rubble_into(c, ax, ay, 6, 2, seed + 5, n=4)
    finish(c)
    return c, (ax, ay), (int(round(ax + height * lean)) - 6 + 1, ay - height + 1)


def broken_sword(seed, tilt=None):
    """A challenger's sword stuck in the ground: rusted blade, crossguard, grip (14-18 px)."""
    rnd = random.Random(seed)
    W, H = 24, 26
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 3
    a = math.radians(tilt if tilt is not None else rnd.uniform(-18, 18))
    L = rnd.randint(9, 13)
    ux, uy = math.sin(a), -math.cos(a)
    pts = P.line(ax, ay, ax + ux * L, ay + uy * L)
    for i, (x, y) in enumerate(pts):
        rust = P.hash01(x, y, seed) < 0.3
        c.set(x, y, P.EARTH[4] if rust else P.STEEL[3 if i % 4 else 4])
        c.set(x + 1, y, P.STEEL[1])
    gx, gy = pts[-1]
    for d in range(-3, 4):
        c.set(int(gx - uy * d), int(gy + ux * d), P.STEEL[2] if abs(d) < 3 else P.GOLD[0])
    for k in range(1, 5):
        c.set(int(gx + ux * k), int(gy + uy * k), P.BARK[2] if k < 4 else P.STEEL[3])
    # a tuft at its foot
    for d in (-2, -1, 1, 2):
        c.set(ax + d, ay, P.GRASS[2])
        c.set(ax + d, ay - 1, P.GRASS[3] if abs(d) == 1 else (0, 0, 0, 0))
    finish(c)
    return c, (ax, ay)


def low_wall(width, seed, height=12):
    """A knee-high broken wall (south side: it never covers a fighter's body)."""
    W, H = width + 12, height + 14
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    top = jagged_top(6, 6 + width, ay - height, 3, seed, (4, 9))
    face, tops = set(), []
    for (xa, ya), (xb, yb) in zip(top, top[1:]):
        y = min(ya, yb)
        for x in range(xa, xb):
            tops.append((x, y))
            for yy in range(y, ay + 1):
                face.add((x, yy))
    masonry(c, face, seed, bh=5, bw=(7, 11), tone=3.8, mossy=0.35)
    top_face(c, [(x, y - k) for (x, y) in tops for k in range(1, 3)], seed + 2, moss=0.6)
    finish(c)
    return c, (ax, ay)


def rubble(seed, rx=16, ry=5, n=9):
    W, H = rx * 2 + 16, ry * 2 + 20
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 6
    rubble_into(c, ax, ay, rx, ry, seed, n=n, size=(4, 9))
    rnd = random.Random(seed)
    for _ in range(n // 2):
        x = ax + rnd.randint(-rx, rx)
        for k in range(rnd.randint(2, 4)):
            c.set(x, ay - k + rnd.randint(-2, 2), P.GRASS[rnd.randint(2, 4)])
    finish(c)
    return c, (ax, ay)


def fallen_column(seed, length=64, width=16):
    """A column drum lying on its side along the court's edge."""
    W, H = length + 16, width + 16
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 5
    x0 = ax - length // 2
    for x in range(x0, x0 + length):
        for k in range(width):
            y = ay - k
            u = k / width
            t = 2.4 + u * 3.2 + math.cos(u * math.pi * 6) * 0.3 + (P.value_noise(x, y, 3, seed) - 0.5) * 0.7
            if (x - x0) % 24 == 23:
                t -= 1.4
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    # the broken ends: oval faces
    for end, sx in ((0, x0), (1, x0 + length)):
        for k in range(width):
            for d in range(4):
                c.set(sx + (d if end else -d), ay - k, P.ramp(P.STONE, 4.5 + (k / width), sx, ay - k, 'grain'))
    moss_drip(c, [(x, ay - width + 1) for x in range(x0, x0 + length)], seed + 3, 0.35)
    finish(c)
    return c, (ax, ay)


def bush(seed, rx=14, ry=9):
    """A low clump of ferns and leaves (dark, lit tips toward the light)."""
    W, H = rx * 2 + 10, ry * 2 + 10
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    rnd = random.Random(seed)
    for _ in range(rx * ry):
        a = rnd.uniform(math.pi * 1.05, math.pi * 1.95)
        d = rnd.random() ** 0.6
        x = int(ax + math.cos(a) * rx * d)
        y = int(ay + math.sin(a) * ry * 2 * d * 0.9)
        lit = (x - ax) / rx * 0.5 - (y - ay) / (ry * 2) * 0.8
        t = 1.5 + lit * 2.5 + rnd.random()
        c.set(x, y, P.ramp(P.LEAF, t, x, y, 'grain') if t < 4.5 else P.LEAF_LIT[min(3, int(t - 4.5))])
        c.set(x + 1, y, P.ramp(P.LEAF, t - 0.6, x, y, 'grain'))
    finish(c)
    return c, (ax, ay)


# ------------------------------------------------------------------ 2026-10-06: more round the court
# (the user: the corner leaves go - nothing may sit on the screen itself - and the scene must not go plain:
# everything below stands in the world, outside the court, and sorts with the fighters)
def brazier(seed):
    """An iron brazier on a square stone foot, cold ash in its bowl (the game lights it with the Boss's fire in
    the second phase: the flames are drawn by the game, from `fire`). About 24 px tall."""
    W, H = 30, 36
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 5
    rnd = random.Random(seed)
    # the foot: a squat block, its top seen from above
    for y in range(ay - 6, ay + 1):
        for x in range(ax - 7, ax + 8):
            t = 3.0 + (x - ax + 7) / 14 * 1.6 + (P.value_noise(x, y, 2.5, seed) - 0.5) * 0.8 + (1.6 if y <= ay - 5 else 0)
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    # three legs (the back one shows between the front two)
    for y in range(ay - 17, ay - 5):
        k = (y - (ay - 17)) / 12
        for lx in (ax - 3 - k * 3, ax + 3 + k * 3):
            c.set(int(round(lx)), y, P.IRON[3] if lx > ax else P.IRON[1])
        if y > ay - 14:
            c.set(ax, y, P.IRON[0])
    # the bowl: a wide iron cup, its rim an ellipse seen from above, ash and charcoal in it
    for y in range(ay - 22, ay - 16):
        half = 8 - (y - (ay - 22)) * 0.8
        for x in range(int(ax - half), int(ax + half) + 1):
            u = (x - ax) / max(1.0, half)
            c.set(x, y, P.ramp(P.IRON, 1.6 + u * 1.6 + (0.8 if y == ay - 21 else 0), x, y))
    for x in range(ax - 8, ax + 9):
        for y in (ay - 24, ay - 23):
            d = ((x - ax) / 8.5) ** 2 + ((y - (ay - 23.5)) / 2.0) ** 2
            if d <= 1.0:
                c.set(x, y, P.ramp(P.ASH, 2.2 + rnd.random() * 1.6, x, y) if abs(x - ax) < 7 else P.IRON[4 if x > ax else 3])
    for x in range(ax - 7, ax + 8):
        c.set(x, ay - 22, P.IRON[3] if x > ax else P.IRON[2])
    for k in range(4):
        c.set(ax + rnd.randint(-5, 5), ay - 23 - rnd.randint(0, 1), P.CHAR[0])
    finish(c)
    return c, (ax, ay)


def boulder(seed, rx=10, ry=7):
    """A rounded stone half sunk in the grass, moss over its top (lit from the upper right)."""
    W, H = rx * 2 + 8, ry * 2 + 10
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    pts = P.blob(ax, ay - ry, rx, ry, seed, rough=0.22, n=16)
    cell = set(P.poly_fill(pts))
    for (x, y) in cell:
        if y > ay:
            continue
        u, v = (x - ax) / rx, (y - (ay - ry)) / ry
        t = 3.4 + u * 1.2 - v * 1.6 + (P.value_noise(x, y, 3, seed) - 0.5) * 1.0
        if v < -0.25 and P.fbm(x, y, 4, seed + 1) > 0.42:
            c.set(x, y, P.ramp(P.MOSS, 2.8 + u + (P.value_noise(x, y, 2, seed) - 0.5) * 1.5, x, y, 'grain'))
        else:
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    # grass round its foot
    rnd = random.Random(seed)
    for x in range(ax - rx, ax + rx + 1):
        if rnd.random() < 0.5:
            for k in range(rnd.randint(1, 3)):
                c.set(x, ay - k, P.GRASS[rnd.randint(2, 4)])
    finish(c)
    return c, (ax, ay)


def block(seed, w=14, h=9, d=6):
    """A fallen dressed stone block (from the walls): its front face, its top seen from above with moss,
    a chipped corner. Knee-high."""
    W, H = w + 12, h + d + 10
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    rnd = random.Random(seed)
    x0 = ax - w // 2
    chip = rnd.randint(2, 4)
    for y in range(ay - h, ay + 1):
        for x in range(x0, x0 + w):
            if x > x0 + w - chip and y < ay - h + chip:
                continue
            t = 3.0 + (x - x0) / w * 1.0 + (P.value_noise(x, y, 2.5, seed) - 0.5) * 0.9
            c.set(x, y, P.ramp(P.STONE, t, x, y, 'grain'))
    for y in range(ay - h - d, ay - h):
        shift = (ay - h - y)
        for x in range(x0 + shift // 2, x0 + w + shift // 2):
            if x > x0 + w - chip + shift // 2 and y < ay - h - d + chip:
                continue
            n = P.fbm(x, y, 4, seed + 2)
            col = P.ramp(P.MOSS, 2.6 + n * 2.4, x, y, 'grain') if n > 0.45 else P.ramp(P.STONE, 5.0 + n, x, y, 'grain')
            c.set(x, y, col)
    # the side face (right), darker
    for y in range(ay - h - d, ay + 1):
        top = ay - h - (ay - h - y if y < ay - h else 0)
    moss_drip(c, [(x, ay - h) for x in range(x0, x0 + w)], seed + 3, 0.4)
    for x in range(x0 - 1, x0 + w + 1):
        if rnd.random() < 0.6:
            c.set(x, ay + 1 - rnd.randint(0, 1), P.GRASS[rnd.randint(2, 4)])
    finish(c)
    return c, (ax, ay)


def fern(seed, size=12):
    """A fern: fronds rising from the middle and arching over, leaflets along each side, lit toward the tips
    and on the right (the light). Sways in the game."""
    W, H = size * 3 + 6, size + 12
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    rnd = random.Random(seed)
    fronds = rnd.randint(6, 8)
    order = sorted(range(fronds), key=lambda f: abs(f - (fronds - 1) / 2), reverse=True)   # back ones first
    for f in order:
        side = (f / (fronds - 1)) * 2 - 1            # -1 left .. 1 right
        ln = size * rnd.uniform(0.85, 1.15) * (0.8 if abs(side) < 0.3 else 1.0)
        pts = []
        for k in range(int(ln)):
            t = k / ln
            x = ax + side * (k * 0.75 + t * t * ln * 0.45)
            y = ay - k * (1.35 - abs(side) * 0.5) + t * t * ln * (0.25 + abs(side) * 0.55)
            pts.append((int(round(x)), int(round(y)), t))
        for (xi, yi, t) in pts:
            lit = 0.6 * side + 1.4 * t
            c.set(xi, yi, P.ramp(P.LEAF, 2.6 + lit, xi, yi))
        for n, (xi, yi, t) in enumerate(pts):
            if n % 2 or not 0.12 < t < 0.95:
                continue
            for s_ in (-1, 1):
                lx, ly = xi, yi + s_
                if abs(side) > 0.3:
                    lx, ly = xi + s_ * (1 if side > 0 else -1) * 0, yi + s_
                col = P.LEAF_LIT[min(3, int(t * 3 + (side > 0)))] if (s_ < 0 and (t > 0.45 or side > 0.2)) else P.ramp(P.LEAF, 2.2 + t * 2, lx, ly)
                c.set(lx, ly, col)
    finish(c)
    return c, (ax, ay)


def tall_grass(seed, width=10, height=10):
    """A clump of long grass blades, bending, the tips catching the light. Sways in the game."""
    W, H = width + 10, height + 8
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 3
    rnd = random.Random(seed)
    for b in range(width + 6):
        x0 = ax + rnd.uniform(-width / 2, width / 2)
        ln = rnd.randint(height // 3, height)
        bend = rnd.uniform(-0.25, 0.25)
        for k in range(ln):
            x = x0 + bend * k * k / ln
            t = 1.4 + k / ln * 3.4 + (0.5 if bend > 0 else 0)
            c.set(int(round(x)), ay - k, P.ramp(P.GRASS, t, int(x), ay - k))
    for x in range(ax - width // 2 - 1, ax + width // 2 + 2):
        if c.opaque(x, ay - 1):
            c.set(x, ay, P.GRASS[0])
    return c, (ax, ay)


def log(seed, length=40, radius=6):
    """A fallen trunk lying along the court's edge, seen from above and the front: a round body lit along its
    top, bark in long streaks, a broken end showing its pale wood and rings, moss on top, mushrooms."""
    W, H = length + 16, radius * 2 + 14
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    rnd = random.Random(seed)
    x0 = ax - length // 2
    cy = ay - radius
    for x in range(x0, x0 + length):
        wob = int(round(math.sin(x * 0.15 + seed) * 0.6))
        for y in range(cy - radius + wob, cy + radius + 1):
            v = (y - cy) / radius                    # -1 top .. 1 bottom
            streak = P.value_noise(x * 0.35, y * 2.5, 3, seed)
            t = 3.4 - v * 1.6 - abs(v) ** 3 * 1.2 + (streak - 0.5) * 1.8
            if v < -0.35 and P.fbm(x, y, 5, seed + 1) > 0.52:
                c.set(x, y, P.ramp(P.MOSS, 3.0 - v + (P.value_noise(x, y, 2, seed) - 0.5) * 1.5, x, y, 'grain'))
            else:
                c.set(x, y, P.ramp(P.BARK, t, x, y, 'grain'))
    # the broken end: pale wood, rings, a few splinters
    ex = x0 + length
    for y in range(cy - radius, cy + radius + 1):
        v = (y - cy) / radius
        half = int(round(3 * math.sqrt(max(0.0, 1 - v * v))))
        for dx in range(-half, half + 1):
            d = math.hypot(dx / 3.0, v)
            ring = int(d * 4) % 2
            c.set(ex + dx, y, P.ramp(P.SAND, 3.6 - d * 1.4 - ring * 0.8, ex + dx, y))
    for k in range(3):
        sy = cy - radius + rnd.randint(1, radius * 2 - 1)
        for d in range(rnd.randint(2, 4)):
            c.set(ex + 3 + d, sy, P.SAND[3])
    for i in range(rnd.randint(2, 4)):
        mx = rnd.randint(x0 + 4, x0 + length - 6)
        my = cy + rnd.randint(-1, radius - 1)
        for dx in (-1, 0, 1):
            c.set(mx + dx, my - 1, P.MUSH[3] if dx < 1 else P.MUSH[2])
        c.set(mx, my, P.MUSH[1])
    rubble_into(c, ax, ay + 1, length // 2, 2, seed + 5, n=0)
    for x in range(x0 - 2, x0 + length + 3):
        if rnd.random() < 0.55:
            for k in range(rnd.randint(1, 3)):
                c.set(x, ay + 1 - k, P.GRASS[rnd.randint(2, 4)])
    finish(c)
    return c, (ax, ay)


def statue_head(seed):
    """The old king's stone head, fallen from his statue and sunk to the chin in the grass, tilted, facing the
    court: a broken crown, deep-set eyes, a long nose, a stern mouth, a beard; moss over the crown and in the
    hollows, a crack down the face. About 28 px tall."""
    W, H = 40, 40
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 5
    rnd = random.Random(seed)
    tilt = -0.18
    hx, hy, rx, ry = ax, ay - 12, 10, 13
    def put(x, y, col):
        # tilted: shear x by the row
        c.set(int(round(x + (y - ay) * tilt)), y, col)
    for y in range(hy - ry, ay + 1):
        for x in range(hx - rx - 1, hx + rx + 2):
            v = (y - hy) / ry
            half = rx * math.sqrt(max(0.0, 1 - v * v)) if v < 0 else rx * (1 - v * 0.25)
            if abs(x - hx) > half:
                continue
            u = (x - hx) / rx
            t = 3.3 + u * 1.3 - v * 0.6 + (P.value_noise(x, y, 3, seed) - 0.5) * 0.8
            put(x, y, P.ramp(P.STONE_COOL, t, x, y, 'grain'))
    # the crown: a band round the brow, points (two broken)
    for x in range(hx - rx, hx + rx + 1):
        for y in (hy - 8, hy - 7):
            put(x, y, P.STONE_COOL[6 if x > hx else 5] if y == hy - 8 else P.STONE_COOL[3])
    for k, px in enumerate(range(hx - rx + 1, hx + rx, 4)):
        ln = 0 if k in (1, 4) else 4
        for d in range(ln):
            put(px, hy - 9 - d, P.STONE_COOL[6 if px > hx else 5])
            put(px + 1, hy - 9 - d, P.STONE_COOL[4])
    # brow shadow, eyes, nose, mouth, beard
    for x in range(hx - 6, hx + 7):
        put(x, hy - 5, P.STONE_COOL[2])
    for ex in (hx - 4, hx + 3):
        for dx in (0, 1):
            put(ex + dx, hy - 4, P.STONE_COOL[0])
            put(ex + dx, hy - 3, P.STONE_COOL[1])
    for y in range(hy - 4, hy + 2):
        put(hx, y, P.STONE_COOL[6])
        put(hx - 1, y, P.STONE_COOL[2])
    put(hx - 1, hy + 2, P.STONE_COOL[1])
    put(hx, hy + 2, P.STONE_COOL[1])
    for x in range(hx - 3, hx + 4):
        put(x, hy + 4, P.STONE_COOL[1])
    for y in range(hy + 5, ay + 1):
        for x in range(hx - 6, hx + 7):
            if (x + y) % 3 == 0:
                put(x, y, P.STONE_COOL[2])
    # moss over the crown and in the eyes, a crack
    for y in range(hy - ry - 4, hy - 6):
        for x in range(hx - rx, hx + rx + 1):
            if P.fbm(x, y, 4, seed + 4) > 0.5:
                xx = int(round(x + (y - ay) * tilt))
                if c.opaque(xx, y):
                    c.set(xx, y, P.ramp(P.MOSS, 2.8 + P.value_noise(x, y, 2, seed) * 2, xx, y, 'grain'))
    x, y = hx + 5, hy - 7
    for k in range(10):
        put(x, y, P.STONE_COOL[0])
        y += 1
        x += rnd.choice((0, 0, 1, -1))
    # sunk: grass round the chin
    for x in range(hx - rx - 3, hx + rx + 4):
        for k in range(rnd.randint(1, 4)):
            if rnd.random() < 0.75:
                c.set(int(round(x + (ay - ay) * tilt)), ay - k + 1, P.GRASS[rnd.randint(2, 4)])
    finish(c)
    return c, (ax, ay)


def grave(seed, tilt=None):
    """A fallen challenger's marker: a sword stuck in the ground with a helmet hung on its hilt or a shield
    leaning on it (15-20 px)."""
    rnd = random.Random(seed)
    sw, (sax, say) = broken_sword(seed, tilt=tilt if tilt is not None else rnd.uniform(-8, 8))
    W, H = 30, 30
    c = P.Canvas(W, H)
    ax, ay = W // 2, H - 4
    ox, oy = ax - sax, ay - say
    if seed % 2:
        # a shield leaning on it, in front
        c.im.alpha_composite(sw.im, (ox, oy))
        c.px = c.im.load()
        sx, sy = ax + rnd.choice((-3, 3)), ay
        for y in range(sy - 9, sy + 1):
            v = (y - (sy - 9)) / 9
            half = 4.5 if v < 0.55 else 4.5 * (1 - (v - 0.55) / 0.5)
            for x in range(int(sx - half), int(sx + half) + 1):
                edge = abs(x - sx) > half - 1.2 or y == sy - 9
                col = (P.IRON[3] if x > sx else P.IRON[2]) if edge else P.ramp(P.STONE_COOL if seed % 4 == 1 else P.BARK, 3.0 + (x - sx) * 0.2, x, y)
                c.set(x, y, col)
        for k in range(3):
            c.set(sx - 1 + k, sy - 6 + k, P.OUTLINE)
    else:
        c.im.alpha_composite(sw.im, (ox, oy))
        c.px = c.im.load()
        # a helmet hung on the hilt
        top = min(y for x in range(W) for y in range(H) if c.px[x, y][3] and abs(x - ax) < 6)
        hx, hy = ax, top + 3
        for y in range(hy - 3, hy + 3):
            for x in range(hx - 3, hx + 4):
                if (x - hx) ** 2 / 12.0 + (y - hy + 0.5) ** 2 / 9.0 > 1:
                    continue
                c.set(x, y, P.STEEL[4] if y < hy - 1 and x > hx - 2 else P.STEEL[3] if x > hx else P.STEEL[2])
        for x in range(hx - 2, hx + 3):
            c.set(x, hy, P.IRON[0])
    finish(c)
    return c, (ax, ay)
