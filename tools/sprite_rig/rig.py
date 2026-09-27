"""Cut-out rig for pixel sprites.

Each part is a layer holding the reference's own pixels. A part is posed with an affine
transform (hierarchical: child = parent * local) plus an optional per-pixel displacement
(cloth waves). Rendering is by inverse mapping into an 8x EPX-upscaled copy of the layer,
which is the RotSprite idea: small rotations keep crisp, un-blurred pixel art."""
import math
from PIL import Image


# ------------------------------------------------------------------ affine helpers
def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_inv(m):
    a, b, c = m[0]
    d, e, f = m[1]
    det = a * e - b * d
    ia, ib = e / det, -b / det
    id_, ie = -d / det, a / det
    return [[ia, ib, -(ia * c + ib * f)], [id_, ie, -(id_ * c + ie * f)], [0, 0, 1]]


def T(dx, dy):
    return [[1, 0, dx], [0, 1, dy], [0, 0, 1]]


def R(deg, px=0.0, py=0.0):
    """Rotation by deg (screen coords: +deg = clockwise on screen) about (px, py)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    rot = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return mat_mul(T(px, py), mat_mul(rot, T(-px, -py)))


I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def apply(m, x, y):
    return m[0][0] * x + m[0][1] * y + m[0][2], m[1][0] * x + m[1][1] * y + m[1][2]


# ------------------------------------------------------------------ EPX / Scale2x
def scale2x(px, w, h):
    out = {}
    get = lambda x, y: px.get((x, y), None) if 0 <= x < w and 0 <= y < h else None
    for y in range(h):
        for x in range(w):
            P = get(x, y)
            A, B, C, D = get(x, y - 1), get(x + 1, y), get(x - 1, y), get(x, y + 1)
            e0 = e1 = e2 = e3 = P
            if C == A and C != D and A != B:
                e0 = A
            if A == B and A != C and B != D:
                e1 = B
            if D == C and D != B and C != A:
                e2 = C
            if B == D and B != A and D != C:
                e3 = D
            for (dx, dy), e in (((0, 0), e0), ((1, 0), e1), ((0, 1), e2), ((1, 1), e3)):
                if e is not None:
                    out[(2 * x + dx, 2 * y + dy)] = e
    return out, 2 * w, 2 * h


class Layer:
    """Pixels of one part, in the sprite's native coordinates."""

    def __init__(self, name, pix, size):
        self.name = name
        self.pix = dict(pix)
        self.w, self.h = size
        big, bw, bh = self.pix, self.w, self.h
        for _ in range(3):
            big, bw, bh = scale2x(big, bw, bh)
        self.big = big
        xs = [p[0] for p in self.pix] or [0]
        ys = [p[1] for p in self.pix] or [0]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def sample(self, sx, sy):
        return self.big.get((int(math.floor(sx * 8)), int(math.floor(sy * 8))))

    def render(self, world, disp=None, margin=10, out=None):
        """world: affine native->output. disp(sx, sy) -> (dx, dy) displacement in native
        space applied before the affine (cloth). Writes into / returns a dict of pixels.

        Every source pixel is carried forward to where it lands, so 1 px strands and single
        highlight pixels survive the move; the gaps a rotation or stretch opens between
        carried pixels are then filled from the RotSprite-style inverse sample (8x EPX)."""
        inv = self._inverse(world, disp, margin)
        fwd = {}
        for (sx, sy), c in self.pix.items():
            qx, qy = sx + 0.5, sy + 0.5
            if disp is not None:
                dx, dy = disp(qx, qy)
                qx += dx
                qy += dy
            ox, oy = apply(world, qx, qy)
            key = (math.floor(ox), math.floor(oy))
            # two source pixels landing on one output pixel (rotation / compression): a
            # 1 px specular highlight wins, so small bright details are not squeezed out
            if key not in fwd or sum(c[:3]) > sum(fwd[key][:3]) > 0 and sum(c[:3]) > 420:
                fwd[key] = c
            else:
                fwd[key] = fwd[key] if sum(fwd[key][:3]) > 420 else c
        res = out if out is not None else {}
        res.update(fwd)
        for (x, y), c in inv.items():
            if (x, y) in fwd:
                continue
            n = ((x + 1, y) in fwd) + ((x - 1, y) in fwd) + ((x, y + 1) in fwd) + ((x, y - 1) in fwd)
            if n >= 2:
                res[(x, y)] = c
        return res

    def _inverse(self, world, disp, margin):
        inv = mat_inv(world)
        x0, y0, x1, y1 = self.bbox
        corners = [apply(world, x, y) for x in (x0 - margin, x1 + margin) for y in (y0 - margin, y1 + margin)]
        ox0 = int(math.floor(min(c[0] for c in corners)))
        ox1 = int(math.ceil(max(c[0] for c in corners)))
        oy0 = int(math.floor(min(c[1] for c in corners)))
        oy1 = int(math.ceil(max(c[1] for c in corners)))
        res = {}
        for oy in range(oy0, oy1 + 1):
            for ox in range(ox0, ox1 + 1):
                sx, sy = apply(inv, ox + 0.5, oy + 0.5)
                if disp is not None:
                    dx, dy = disp(sx, sy)
                    sx -= dx
                    sy -= dy
                c = self.sample(sx, sy)
                if c is not None:
                    res[(ox, oy)] = c
        return res


# ------------------------------------------------------------------ masks
def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def in_poly(poly):
    return lambda x, y, c: point_in_poly(x + 0.5, y + 0.5, poly)


def is_blue(c):
    return c[2] > c[0] + 25 and c[2] > 60


def inpaint(pix, holes, rounds=12):
    """Fill hole pixels from neighbouring filled pixels (prefers horizontal neighbours so
    armour bands continue)."""
    pix = dict(pix)
    holes = set(holes) - set(pix)
    for _ in range(rounds):
        if not holes:
            break
        new = {}
        for (x, y) in holes:
            for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1), (x - 2, y), (x + 2, y)):
                if q in pix:
                    new[(x, y)] = pix[q]
                    break
        pix.update(new)
        holes -= set(new)
    return pix


def body_fill(parts, torso_name, fill_names, cut, radius=6):
    """Pixels of overlapping parts (cape, arms, helmet rim...) that lie on the body: the
    torso must have armour there too, so moving a part never reveals the background."""
    torso = set(parts[torso_name])
    cand = {p for n in fill_names if n in parts for p in parts[n] if p[1] < cut}
    dist = {p: 0 for p in torso}
    frontier = list(torso)
    for d in range(1, radius + 1):
        nxt = []
        for (x, y) in frontier:
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in cand and q not in dist:
                    dist[q] = d
                    nxt.append(q)
        frontier = nxt
    return {p for p in dist if p not in torso}


def close_holes(px, W, H, max_size=12):
    """Fill small transparent pockets fully enclosed by the silhouette (rotation seams)."""
    opaque = set(px)
    outside = set()
    stack = [(x, y) for x in range(-1, W + 1) for y in (-1, H)] + [(x, y) for y in range(-1, H + 1) for x in (-1, W)]
    while stack:
        p = stack.pop()
        if p in outside or p in opaque:
            continue
        x, y = p
        if x < -1 or y < -1 or x > W or y > H:
            continue
        outside.add(p)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    holes = {(x, y) for x in range(W) for y in range(H) if (x, y) not in opaque and (x, y) not in outside}
    # group and fill small groups from their neighbours
    seen = set()
    for h in list(holes):
        if h in seen:
            continue
        comp, st = [], [h]
        seen.add(h)
        while st:
            a = st.pop()
            comp.append(a)
            for q in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if q in holes and q not in seen:
                    seen.add(q)
                    st.append(q)
        if len(comp) <= max_size:
            todo = set(comp)
            while todo:
                done = []
                for (x, y) in todo:
                    for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if q in px:
                            px[(x, y)] = px[q]
                            done.append((x, y))
                            break
                if not done:
                    break
                todo -= set(done)
    # 1-px pinholes open on one side only diagonally (crack between two parts)
    for x in range(W):
        for y in range(H):
            if (x, y) not in px and (x - 1, y) in px and (x + 1, y) in px and (x, y - 1) in px and (x, y + 1) in px:
                px[(x, y)] = px[(x - 1, y)]
    return px


def inpaint_reflect(pix, holes, darken=0.82, snap=None):
    """Fill holes by mirroring the nearest real pixels across the hole edge (keeps the
    armour's speckled texture instead of smearing one colour), slightly shadowed."""
    pix = dict(pix)
    real = set(pix)
    holes = set(holes) - real
    fills = {}
    for (x, y) in holes:
        src = None
        for d in range(1, 12):
            for sgn in (1, -1):
                e = (x + sgn * d, y)
                if e in real:
                    m = (e[0] + sgn * (d - 1), y)
                    src = pix[m] if m in real else pix[e]
                    break
            if src:
                break
        if src is None:
            for d in range(1, 12):
                for sgn in (1, -1):
                    e = (x, y + sgn * d)
                    if e in real:
                        m = (x, e[1] + sgn * (d - 1))
                        src = pix[m] if m in real else pix[e]
                        break
                if src:
                    break
        if src is not None:
            c = (int(src[0] * darken), int(src[1] * darken), int(src[2] * darken))
            fills[(x, y)] = snap(c) if snap else c + (255,)
    pix.update(fills)
    return pix


def S(sx, sy):
    return [[sx, 0, 0], [0, sy, 0], [0, 0, 1]]


def axis_map(s0, s1, d0, d1):
    """Affine that carries the source segment s0->s1 onto d0->d1 (rotate + stretch along the
    segment, width unchanged). Used to re-pose a limb strip."""
    sx, sy = s1[0] - s0[0], s1[1] - s0[1]
    dx, dy = d1[0] - d0[0], d1[1] - d0[1]
    ls = math.hypot(sx, sy)
    ld = math.hypot(dx, dy)
    ts = math.degrees(math.atan2(-sx, sy))
    td = math.degrees(math.atan2(-dx, dy))
    m = T(-s0[0], -s0[1])
    m = mat_mul(R(-ts), m)
    m = mat_mul(S(1.0, ld / ls), m)
    m = mat_mul(R(td), m)
    return mat_mul(T(d0[0], d0[1]), m)


def reconnect_specks(px, max_size=2):
    """Thin strand tips (plume / cape tatters) can detach by a pixel when the cloth waves.
    Re-attach each tiny island to the nearest body pixel within 2 px with its own colour;
    drop it if nothing is near."""
    seen = set()
    comps = []
    for k in list(px):
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
                    if q in px and q not in seen:
                        seen.add(q)
                        st.append(q)
        comps.append(comp)
    small = [c for c in comps if len(c) <= max_size]
    small_set = {p for c in small for p in c}
    for comp in small:
        best = None
        for (x, y) in comp:
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    q = (x + dx, y + dy)
                    if q in px and q not in small_set:
                        d = max(abs(dx), abs(dy))
                        if best is None or d < best[0]:
                            best = (d, (x, y), q)
        if best is None or best[0] > 2:
            for p in comp:
                px.pop(p, None)
            continue
        _, (x, y), (qx, qy) = best
        # one bridging pixel halfway (diagonal adjacency then connects the island)
        mx, my = x + (1 if qx > x else -1 if qx < x else 0), y + (1 if qy > y else -1 if qy < y else 0)
        if (mx, my) not in px:
            px[(mx, my)] = px[(x, y)]
    return px
