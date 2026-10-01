"""The Boss's attacks (攻擊) drawn in four directions from the 3D poses of attacks.py / attack3d.py.

What is new against the moves and the hit reactions (anim_walk, anim_kneel):
  - both arms are posed from 3D joints (attack3d.arms: the two fists on one grip, each arm bent
    towards its pole) and projected into the view relative to the shoulder the view draws; the
    front view's left arm, the side views' far arm and both back-view arms were never posed
    before. The approved arms are taken off the body where they would be left behind
    (ARM_OFF), the shoulder plates are kept over the posed upper arms (PLATES)
  - the sword is drawn at its 3D direction (sword.sword_image) and split by depth into what is
    behind the body / the cape and what is in front of it (tiers()), pixel by pixel along the
    blade: a sword swinging round him passes behind and in front of him within one stroke
  - the upper body turns (tw) - every row above the belt is remapped as the surface of an
    elliptic cylinder turned about the vertical axis (Twist): the shoulder that comes forward
    moves towards the front, the far edge folds away, the near one opens; front and back views
    also move the turned surface down where it comes towards the camera (DEPTH)
  - the hips can move forward of the anchor (hx: the weight onto the front foot)
Everything else (hips down D, the lean lx, the bowed head, the cape's kick, the legs from the
gait model) is drawn the same way as before; the head follows the chest a pose late.

Facing left is built in facing-right space with the sword hand on the far side and mirrored
(side.py), as everywhere.
"""
import math
from PIL import Image
import boss as B
import rig
import gait
import limb
import arm
import side
import carry
import anim_idle
import anim_walk as AW
import anim_kneel as K
import sword as swd
import attack3d as A
import attacks as AT

FW, FH, AX, AY = rig.FW, rig.FH, rig.AX, rig.AY
DEPTH = swd.DEPTH
EXT, BIG = AW.EXT, AW.BIG
piecewise, _frac = AW.piecewise, AW._frac
HIP_HALF = 17.0
LEAN_ROWS, LEAN_DEG = AW.LEAN_ROWS, AW.LEAN_DEG


# ------------------------------------------------------------------ the turned upper body
class Twist:
    """Columns of a body seen as an elliptic cylinder (half-width a across the screen, b in
    depth, centre column x0) turned by th degrees (+ = the screen-right side goes away and the
    surface moves right... see project(): x' = x cos + depth sin). src(x) gives the source column
    for a target column and dy(x) how far down the target row of that column comes from (the
    surface coming towards the camera is lower, DEPTH)."""
    _cache = {}

    def __new__(cls, x0, a, b, th):
        key = (round(x0, 2), a, b, round(th))
        if key not in cls._cache:
            obj = super().__new__(cls)
            obj._build(x0, a, b, round(th))
            cls._cache[key] = obj
        return cls._cache[key]

    def _build(self, x0, a, b, th):
        self.th = th
        c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
        best = {}
        u = -a - 40.0
        samples = []
        while u <= a + 40.0:
            uu = max(-a, min(a, u))
            ph = math.asin(uu / a)
            x, dpt = a * math.sin(ph), b * math.cos(ph)
            x1 = x * c + dpt * s
            d1 = -x * s + dpt * c
            # outside the ellipse: rigid with its edge
            x1 += (u - uu)
            # the surface faces the camera if its normal does after the turn
            nx, nd = math.sin(ph) / a, math.cos(ph) / b
            vis = -nx * s + nd * c > -1e-6 or abs(u) > a
            samples.append((u, x1, d1 - dpt, vis))
            u += 0.25
        for u, x1, dd, vis in samples:
            if not vis:
                continue
            col = math.floor(x1 + x0)
            prev = best.get(col)
            if prev is None or dd > prev[1]:
                best[col] = (u + x0, dd)
        cols = sorted(best)
        self.lo, self.hi = cols[0], cols[-1]
        self.table = {}
        for col in range(self.lo, self.hi + 1):
            if col in best:
                self.table[col] = best[col]
            else:
                near = min(cols, key=lambda v: abs(v - col))
                self.table[col] = best[near]
        # forward map of a point (the drawn shoulders)
        self.fwd_samples = [(u + x0, x1 + x0, dd) for u, x1, dd, vis in samples]

    def src(self, x):
        """(source column (float), depth change) for target column x, or None."""
        if x < self.lo or x > self.hi:
            return None
        return self.table[x]

    def fwd(self, x):
        """Target column and depth change of source column x (a point on the surface)."""
        best = min(self.fwd_samples, key=lambda v: abs(v[0] - x))
        return best[1], best[2]


SIDE_NEAR = 0.6                # side views: share of the shoulder's 3D move the near plate makes on screen
SIDE_CHEST = 0.25                # ... the chest
TWIST_FB = (34.0, 14.0)         # front / back: half the shoulders' width, half the chest's depth
FB_DRAW = 0.7                   # front / back: share of the turn drawn (all of it stretches the plates' tassels into blocks)
TWIST_X0 = {'right': 127.0, 'down': AX + 0.5, 'up': AX + 0.5}


def twist_weight(sy, sm):
    """How much of the turn a source row takes: none at the belt, all of it from 12 rows up."""
    return _frac(sm['belt'] - sy, 0, 12)


# ------------------------------------------------------------------ the sword
def place(view, axis3, w3, grip, stand, far=False):
    """The sword's placement (sword.standing() format) for a 3D direction and width at a screen
    grip point (the right fist's centre)."""
    k = math.hypot(*stand['axis'])
    Av = tuple(c * k for c in swd.project_vec(view, axis3, far))
    Wv = tuple(c * k / swd.FLAT_SEEN for c in swd.project_vec(view, w3, far))
    hand = stand['axis'][0] * stand['width'][1] - stand['axis'][1] * stand['width'][0]
    if (Av[0] * Wv[1] - Av[1] * Wv[0]) * hand < 0:
        Wv = (-Wv[0], -Wv[1])
    n = math.hypot(*Av)
    if n > 1e-6:
        # seen edge-on the blade still shows its own thickness (carry.place)
        u = (Av[0] / n, Av[1] / n)
        across = u[0] * Wv[1] - u[1] * Wv[0]
        sgn = 1.0 if hand > 0 else -1.0
        if across * sgn < carry.THICK * k:
            add = carry.THICK * k * sgn - across
            Wv = (Wv[0] - u[1] * add, Wv[1] + u[0] * add)
    return {'grip': grip, 'axis': Av, 'width': Wv, 'len': stand['len']}


def along(pix, pl):
    """{pixel: distance from the grip along the sword in final px (3D, + towards the tip)}."""
    g, ax, wd = pl['grip'], pl['axis'], pl['width']
    k = pl['len'] / max(1e-6, pl.get('sheet_len', 1.0))
    det = ax[0] * wd[1] - ax[1] * wd[0]
    out = {}
    for (x, y) in pix:
        dx, dy = x + 0.5 - g[0], y + 0.5 - g[1]
        t = (dx * wd[1] - dy * wd[0]) / det if abs(det) > 1e-9 else 0.0
        out[(x, y)] = t * pl['k']
    return out


def sword_split(view, pix, pl, fist3, axis3, tier_of):
    """The drawn sword split into tiers by the depth of each pixel's point on the blade:
    {tier: (hilt pixels, blade pixels)}."""
    g, ax, wd = pl['grip'], pl['axis'], pl['width']
    det = ax[0] * wd[1] - ax[1] * wd[0]
    kk = math.hypot(*AW._layers({'right': 'right', 'front': 'down', 'back': 'up'}[view])['place0']['axis'])
    hilt_at = carry.HILT
    out = {}
    nA = math.hypot(*ax)
    for (x, y), c in pix.items():
        dx, dy = x + 0.5 - g[0], y + 0.5 - g[1]
        if abs(det) > 1e-9 and nA > 0.12 * kk:
            t = (dx * wd[1] - dy * wd[0]) / det * kk          # final px along the sword
        else:
            t = 60.0                                          # pointing at the camera: one depth for all of it
        p = A.add(fist3, A.mul(axis3, t))
        tier = tier_of(p)
        h, b = out.setdefault(tier, ({}, {}))
        (b if t >= hilt_at else h)[(x, y)] = c
    return out


# ------------------------------------------------------------------ the arms
def screen(view, p3, anchor3, anchor_xy, far=False):
    v = swd.project_vec(view, A.sub(p3, anchor3), far)
    return (anchor_xy[0] + v[0], anchor_xy[1] + v[1])


def elevation(p3):
    """A side view's point: the side sprites are drawn as elevations (both shoulders at one
    height), so a point's screen position does not depend on its depth - the carry's fist
    (carry.fist_screen) is placed the same way. Only directions (the blade from the grip) are
    projected with the depth (sword.project_vec). Facing right and facing left then show a pose's
    hands at the same height (anchoring them to the near shoulder put them 7 px higher facing
    right and 7 px lower facing left than the other: 14 px apart)."""
    return (AX + 0.5 + p3[0], AY + 1 - p3[2])


def posed_arms(view, s, grip_xy, drawn, far=False):
    """Screen joints of the posed arms: {k: (J, shoulder3, elbow3, fist3)}. The fists are where
    the sword says (the right fist on the grip point, the left HANDS further along it, or on its
    way there: the right fist's screen position plus the projected 3D offset), so both are on
    the drawn grip whatever the drawn shoulders; the elbow is the 3D elbow projected from the
    drawn shoulder, kept within the bones' lengths (AW.reach). A drawn shoulder further from its
    fist than the arm is long (the side views' far shoulder, drawn where its plate is) is drawn
    nearer: it is under the shoulder plate or behind the body."""
    arms = A.arms(s)
    gR3 = s['fist']
    out = {}
    for k in 'RL':
        a = arms[k]
        if a is None:
            continue
        sh3, e3, g3, _ = a
        sxy = drawn[k][0]
        g = screen(view, g3, gR3, grip_xy, far)
        n = math.dist(sxy, g)
        if n > A.ARM - 0.3:
            f = (A.ARM - 0.3) / n
            sxy = (g[0] + (sxy[0] - g[0]) * f, g[1] + (sxy[1] - g[1]) * f)
        e = elevation(e3) if view == 'right' else screen(view, e3, sh3, sxy, far)
        e = AW.reach(sxy, e, g)
        # the fist keeps its length on screen (arm.pose): a forearm pointing at the camera
        # that is drawn shorter than the fist would push the fist off the grip - the elbow is
        # kept at least that far from the fist's centre
        l3 = A.FIST + 1.6
        n = math.dist(e, g)
        if n < l3:
            v = (e[0] - g[0], e[1] - g[1]) if n > 0.3 else (sxy[0] - g[0], sxy[1] - g[1])
            m_ = math.hypot(*v) or 1.0
            e = (g[0] + v[0] / m_ * l3, g[1] + v[1] / m_ * l3)
        J = arm.pose(sxy, e, g)
        out[k] = (J, sh3, e3, g3)
    return out


def arm_pieces(J, mirror, frame=(FW, FH)):
    """(upper, forearm, fist) pixels of an arm on joints J, lit as a near arm."""
    return tuple(arm.near(arm.render(J, frame, mirror=mirror, parts=(p,))) for p in ('upper', 'fore', 'fist'))


def far_lit(pix, k=0.68):
    return limb.darken(pix, k=k)


def solve_arms(st):
    """{'R': (shoulder3, elbow3, fist3, slack), 'L': ... or None (hanging: the approved arm)}."""
    return A.arms(st)


# ------------------------------------------------------------------ approved arms off, shoulder plates kept
# final px. ARM_OFF: the approved right upper arm left on the front view's body (the planted
# sword's arm); PLATES: the shoulder plate (and the fur, the tassel's top) over where a posed
# upper arm comes out
ARM_OFF = {'down': [(89, 84), (100, 82), (107, 90), (107, 100), (104, 107), (93, 107), (88, 98)]}
TASSELS = {'R': [(100, 88), (111, 88), (112, 115), (100, 115)], 'L': [(135, 88), (148, 88), (148, 115), (135, 115)]}
PLATES = {
    'down': {'L': [(131, 73), (148, 69), (160, 77), (163, 91), (159, 98), (147, 100), (137, 99), (132, 91)]},
    'up': {'R': [(129, 72), (146, 70), (160, 76), (164, 90), (160, 98), (148, 99), (136, 96), (130, 88)],
           'L': [(90, 80), (106, 76), (118, 80), (118, 92), (112, 98), (98, 99), (90, 94)]},
}
_extra = {}


def _poly_px(poly):
    pts = set()
    x0, x1 = int(min(q[0] for q in poly)) - 1, int(max(q[0] for q in poly)) + 2
    y0, y1 = int(min(q[1] for q in poly)) - 1, int(max(q[1] for q in poly)) + 2
    for y in range(y0, y1):
        for x in range(x0, x1):
            if rig.in_poly((x + 0.5, y + 0.5), poly):
                pts.add((x, y))
    return pts


def rotate_pixels(pix, pivot, deg, k=4):
    """Whole-pixel art turned about `pivot` (frame px) by `deg` (clockwise on screen): every
    pixel is split into k x k samples, the samples are turned, and each target pixel takes the
    most common colour of the samples that land in it (if half of it or more is covered). The
    art keeps its own colours and texture (nothing is re-stylised); 0 degrees gives the same
    pixels."""
    if abs(deg) < 0.5:
        return dict(pix)
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)
    buckets = {}
    for (x, y), col in pix.items():
        for i in range(k):
            for j in range(k):
                px, py = x + (i + 0.5) / k - pivot[0], y + (j + 0.5) / k - pivot[1]
                q = (math.floor(px * c - py * s_ + pivot[0]), math.floor(px * s_ + py * c + pivot[1]))
                buckets.setdefault(q, []).append(col)
    out = {}
    for q, cols in buckets.items():
        if len(cols) >= k * k // 2:
            out[q] = max(set(cols), key=cols.count)
    return out


def under_fill(source, region, exclude, reach=14, shade=0.8, top=None):
    """Colours for `region` (the pixels a shoulder plate covers at rest), from the armour
    below it reflected upwards column by column (rig.extend_up's way: the texture goes on), the
    columns with nothing below grown in from the sides; darkened (in the plate's shadow): what
    shows of the shoulder when the plate turns away. Nothing above `top` (over the shoulder
    there is only the collar, behind)."""
    snap = B.Snapper(B.load_palette())
    known = {q: c for q, c in source.items() if q not in exclude}
    todo = {q for q in set(region) - set(known) if top is None or q[1] >= top}
    out = {}
    cols = {}
    for (x, y) in todo:
        cols.setdefault(x, []).append(y)
    for x, ys in cols.items():
        y_b = max(ys) + 1
        while (x, y_b) not in known and y_b < max(ys) + 6:
            y_b += 1
        if (x, y_b) not in known:
            continue
        for y in ys:
            m = (x, 2 * y_b - 1 - y)
            c = known.get(m)
            if c is None:
                c = known[(x, y_b)]
            out[(x, y)] = c
    # under a plate is the shoulder's armour: the banners and trim that hang below a plate are
    # not reflected up into it (they made red blocks), the darkest armour tone stands in
    dark = min((c for c in known.values() if not rig.is_cloth(c) and not rig.is_gold(c) and B.lum(c) > 20), key=B.lum)
    out = {q: (dark if rig.is_cloth(c) or rig.is_gold(c) else c) for q, c in out.items()}
    rest = todo - set(out)
    if rest:
        out.update(_grow_fill(known, rest, reach))
    return {q: snap(tuple(round(v * shade) for v in c)) for q, c in out.items()}


def _grow_fill(known, todo, reach):
    """Colours for `region` (the pixels a shoulder plate covers at rest) taken from the nearest
    pixel of `source` outside `exclude`, darkened (it is in the plate's shadow): what shows of
    the shoulder when the plate turns away. Grown ring by ring, so it follows the colours
    around it."""
    todo = set(todo)
    out = {}
    frontier = {q for q in known if any((q[0] + dx, q[1] + dy) in todo for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for _ in range(reach):
        new = {}
        for (x, y) in frontier:
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in todo and q not in new:
                    new[q] = known.get((x, y)) or out.get((x, y))
        if not new:
            break
        for q, c in new.items():
            out[q] = c
            todo.discard(q)
        frontier = set(new)
    return out


def _fragments(pix, plates, top, margin=3):
    """Body pixels above `top` within a plate's columns (spikes and slivers the plate's outline
    left on the body: with the plate in place they belong to it, with the plate turned they
    float): {pixels}."""
    xs = {}
    for (x, y) in plates:
        xs.setdefault(y, []).append(x)
    lo = min(x for x, _ in plates) - margin
    hi = max(x for x, _ in plates) + margin
    return {q for q in pix if q[1] < top and lo <= q[0] <= hi}


def extra(direction):
    """Layers the attacks need that the walk does not: front - the body without the approved
    right upper arm, the left shoulder plate; back - the shoulder plates (from the arms layer),
    the cape behind the arms; the drawn shoulders."""
    if direction in _extra:
        return _extra[direction]
    S = AW._layers(direction)
    L = S['layers']
    E = {}
    if direction == 'down':
        off = _poly_px(ARM_OFF['down'])
        body = L['body']
        E['body'] = rig.Layer('body', {q: c for q, c in body.pix.items() if q not in off},
                              {q: c for q, c in body.under.items() if q not in off})
        plate = _poly_px(PLATES['down']['L'])
        # the red tassels hang from the shoulder plates: they go with them
        tas = {k: {q for q in _poly_px(v) if q in body.pix and rig.is_cloth(body.pix[q])} for k, v in TASSELS.items()}
        E['plateL'] = rig.Layer('plateL', {q: c for q, c in body.pix.items() if q in plate or q in tas['L']})
        E['plateR'] = rig.Layer('plateR', dict(S['pauldron'].pix, **{}))
        E['plateR'].pix.update({q: body.pix[q] for q in tas['R']})
        # the shoulder plates turn with the upper arms: under them, the shoulders (filled from
        # the pixels around them), not another copy of the plate
        plates = set(E['plateL'].pix) | set(E['plateR'].pix)
        b = E['body']
        top = S['shoulder'][1] - 8
        fill = under_fill(b.all(), plates, plates, top=top)
        # (no fragment clean-up here: the two plates span the neck, which stays)
        b.pix = {q: c for q, c in b.pix.items() if q not in plates}
        b.under = {q: c for q, c in b.under.items() if q not in plates}
        b.under.update(fill)
        lay = S['lay']
        E['shoulder'] = {'R': S['shoulder'], 'L': lay.local_to_final(arm.SHOULDER)}
        # the cape behind the approved right upper arm: what the cape layer has there (its
        # underlay reaches under the body); nothing else to show
    elif direction == 'up':
        armL = L['arm']
        plates = {k: _poly_px(v) for k, v in PLATES['up'].items()}
        E['plateR'] = rig.Layer('plateR', {q: c for q, c in armL.pix.items() if q in plates['R']})
        E['plateL'] = rig.Layer('plateL', {q: c for q, c in armL.pix.items() if q in plates['L']})
        # the cape where the arms hung: the other side's cape mirrored about the centre line,
        # under everything (the cape layer's own pixels win)
        cape = L['cape']
        fill = {}
        arm_px = set(armL.pix) | set(armL.under)
        for (x, y) in arm_px:
            if (x, y) in cape.pix:
                continue
            m = (2 * AX - x, y)
            c = cape.pix.get(m)
            if c is not None and m not in arm_px:
                fill[(x, y)] = c
        # (the cape's own underlay under the arms grew into blocks outside its outline)
        under = {q: c for q, c in cape.under.items() if q not in arm_px}
        under.update(fill)
        E['cape'] = rig.Layer('cape', dict(cape.pix), under)
        E['shoulder'] = {'R': (AX + 0.5 + A.SH_R, 97.0), 'L': (AX + 0.5 - A.SH_R, 97.0)}
    else:
        body = L['body']
        plates = set(S['pauldron'].pix)
        top = S['shoulder'][1] - 12
        fill = under_fill(body.all(), plates, plates, top=top)
        frag = _fragments(body.all(), plates, top)
        E['body'] = rig.Layer('body', {q: c for q, c in body.pix.items() if q not in plates and q not in frag},
                              dict({q: c for q, c in body.under.items() if q not in plates and q not in frag}, **{}))
        E['body'].under.update(fill)
        E['shoulder'] = {'near': S['shoulder']}
    _extra[direction] = E
    return E


# ------------------------------------------------------------------ the shoulder plates turn with the upper arms
# User 2026-10-01: "the shoulders do not carry the upper arms round; only the forearms swing".
# The plate sits on the top of the upper arm and turns PLATE_FOLLOW of the way the upper arm
# swings in the plane the view sees: seen from the side, its swing forward / back (flexion);
# from the front or behind, its swing out to the side (abduction) - measured in the upper
# body's own frame, from where the carry has it (the right arm up to the fist on the shoulder,
# the left hanging), so the carry's plates do not move. At most PLATE_MAX; about a point PLATE_UP
# px over the arm's root. (Measured on screen instead, an arm pointing at the camera turned the
# front view's plate 40 degrees.)
PLATE_FOLLOW = 0.6
PLATE_MAX = 30.0
PLATE_MAX_FB = 18.0      # front / back: the plates are wide and spiky there, a bigger turn reads as a jumble
PLATE_UP = 19.0
_ref = {}


def _swing(k, st):
    """An arm's upper arm in the upper body's own frame: {'side': (degrees forward from
    hanging, share of it in that plane), 'front': (degrees out to its side from hanging,
    share)}; None for a hanging (approved) left arm. An upper arm pointing along the view
    (forward, seen from the front) has a small share there and turns the plate less."""
    a = A.arms(st)[k]
    if a is None:
        return None
    sh, e = a[0], a[1]
    q = A.unit(A.yaw(A.sub(e, sh), -st.get('tw', 0.0)))
    side_ = 1.0 if k == 'R' else -1.0
    return {'side': (math.degrees(math.atan2(q[0], -q[2])), math.hypot(q[0], q[2])),
            'front': (math.degrees(math.atan2(q[1] * side_, -q[2])), math.hypot(q[1], q[2]))}


def _reference(k):
    if k not in _ref:
        import attacks as AT
        st = AT.Clip('ref', [(0, AT.carry_key(two=0.002)), (1, AT.carry_key(two=0.002))]).at(0)
        _ref[k] = _swing(k, st)
    return _ref[k]


def plate_turn(direction, k, s, far=False):
    """Degrees (clockwise on screen, facing-right space for the side views) the shoulder plate
    of arm k turns in pose s."""
    sw, ref = _swing(k, s), _reference(k)
    if sw is None or ref is None:
        return 0.0
    plane = 'side' if direction in ('right', 'left') else 'front'
    (ang, w), (ang0, w0) = sw[plane], ref[plane]
    d = ((ang - ang0 + 180.0) % 360.0 - 180.0) * min(w, w0)
    if plane == 'side':
        deg = -d                            # forward: the plate's lower edge goes forward (screen right)
    else:
        out_right = (k == 'L') == (direction == 'down')     # screen right is outwards for this arm
        deg = -d if out_right else d
    mx = PLATE_MAX if plane == 'side' else PLATE_MAX_FB
    return max(-mx, min(mx, PLATE_FOLLOW * deg))


# ------------------------------------------------------------------ side views
def side_tier(far):
    cam = -1.0 if far else 1.0

    def tier(p):
        return 'near' if p[1] * cam >= 0.0 else 'far'
    return tier


def pose_side(s, s1, far=False):
    """A side-view pose (facing-right space; far: the Boss faces left, mirrored by render())."""
    S = AW._layers('right')
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    d, d1 = s['D'], s1['D']
    hx, hx1 = round(s['hx']), round(s1['hx'])
    belt = sm['belt']
    lean, lean1 = math.tan(math.radians(s['lx'])), math.tan(math.radians(s1['lx']))
    # the turn, seen from the side: the near shoulder plate goes forward / back, the chest
    # less; the far shoulder plate the other way - turned towards the camera it comes out in
    # front of the chest. Whole pixels, no stretching (stretched columns smear the plates)
    sn = math.sin(math.radians(-s['tw'] if far else s['tw']))
    near_dx = round(SIDE_NEAR * A.SH_R * sn)
    chest_tw = round(SIDE_CHEST * A.SH_R * sn)
    far_dx = -near_dx
    cam = -1 if far else 1

    def chest_dx(sy, ln=lean):
        return round(ln * max(0.0, belt - sy))

    def body_src(x, y, extra=0):
        sy = y - d
        w = twist_weight(sy, sm)
        return x - hx - chest_dx(sy) - round((chest_tw + extra) * w), sy

    def plate_src(x, y):
        return body_src(x, y, near_dx - chest_tw)

    def at(p):
        """Where the near shoulder joint is drawn (it moves with the shoulder plate)."""
        return (p[0] + hx + chest_dx(p[1]) + near_dx, p[1] + d)

    # legs: the feet where the pose has them, the hips at hx
    feet = s['feet']
    hip_z = gait.HIP_REST - d

    def leg(side_):
        # each leg from its own hip joint: the hips' turn brings one forward, the other back
        x, out, z, pitch, down = feet[side_][:5]
        lat = feet[side_][5] if len(feet[side_]) > 5 else (out if side_ == 'R' else -out)
        hxs = AT.hip_x(s, side_)
        L = gait.solve(hip_z, (x - hxs, z - DEPTH * lat * cam), pitch, down)
        return {k: ((v[0] + hxs, v[1]) if k in ('hip', 'knee', 'ankle') else v) for k, v in L.items()}
    near_leg, far_leg = (leg('L'), leg('R')) if far else (leg('R'), leg('L'))

    # the arms: near = the one on the camera's side
    arms = A.arms(s)
    near_k, far_k = ('L', 'R') if far else ('R', 'L')
    # the shoulders go with their upper arms (attack3d.girdles), and their plates with them
    gd = A.girdles(s)
    g_near = (round(gd[near_k][0]), -round(gd[near_k][2]))
    g_far = (round(gd[far_k][0]), -round(gd[far_k][2]))
    sh_drawn = at(S['shoulder'])
    sh_drawn = (sh_drawn[0] + g_near[0], sh_drawn[1] + g_near[1])
    sh_near3 = A.shoulder(near_k, s)
    sh_far3 = A.shoulder(far_k, s)
    # the far shoulder where its plate is drawn (FAR_UP higher, like the far leg)
    sh_far_drawn = (sh_drawn[0] - g_near[0] + far_dx - near_dx + g_far[0], sh_drawn[1] - g_near[1] - AW.FAR_UP + g_far[1])
    drawn = {near_k: (sh_drawn, sh_near3), far_k: (sh_far_drawn, sh_far3)}
    # the sword: grip at the right fist, from the drawn right shoulder
    shR_xy, shR3 = drawn['R']
    grip = elevation(s['fist'])
    pl = place('right', s['axis'], s['w3'], grip, S['place0'], far)
    pix = swd.sword_image('right', pl, BIG, source='bare', origin=(-EXT, -EXT))
    key = ('left' if far else 'right', s.get('name'), s.get('i'))
    SWORD[key] = (pix, pl, grip)
    split = sword_split('right', pix, pl, s['fist'], s['axis'], side_tier(far))
    pieces = {}
    for k, (J, sh3, e3, g3) in posed_arms('right', s, grip, drawn, far).items():
        P = arm_pieces(J, True)
        if k == far_k:
            P = tuple(far_lit(p) for p in P)
        pieces[k] = (P, J)
        JOINTS[key + (k,)] = J
    farH, farB = split.get('far', ({}, {}))
    nearH, nearB = split.get('near', ({}, {}))

    out = [farB]
    if far_k in pieces:
        out.extend(pieces[far_k][0])
    out.append(farH)
    # cape: top on the shoulders (turning with them), the hem kicked by ck
    ck = s.get('ck', 0.0)
    cape = layers['cape']
    top, hem = sm['cape_top'], sm['cape_hem']

    def cape_src(x, y):
        # the top rides the shoulders, the hem stays on the ground (anim_walk.cape_src)
        t = _frac(y - d, top, hem)
        dy = round(d * (1 - t))
        t = _frac(y - dy, top, hem)
        x1 = x - round(hx * (1 - t)) - round(chest_dx(top + 8) * (1 - t)) - round(ck * t ** 1.5)
        return x1, y - dy
    dkey = 'left' if far else 'right'
    far_plate = far_lit(K.warp(S['pauldron'], lambda x, y: body_src(x - g_far[0], y + AW.FAR_UP - g_far[1], far_dx - chest_tw),
                               pad=16))
    if far_k in pieces:
        far_plate = rotate_pixels(far_plate, (sh_far_drawn[0], sh_far_drawn[1] - PLATE_UP),
                                  plate_turn(dkey, far_k, s))
    if far_dx <= 0:
        out.append(far_plate)                     # behind him: under the cape
    out.append(K.warp(cape, cape_src, pad=24))
    if far_dx > 0:
        out.append(far_plate)                     # turned towards the camera: in front of the cape, behind the chest
    out.append(K.warp(S['backdrop'], lambda x, y: (x - hx, y - d) if y <= AY else None))
    out.append({(x, y - AW.FAR_UP): c for (x, y), c in limb.darken(limb.leg_pixels(far_leg)).items()})
    ht, hh = sm['hang_top'], sm['hang_hem']
    sw = round(0.5 * s1.get('ck', 0.0))

    def cloth_src(x, y):
        # the tabard hangs from the belt (d) to a hem that stays above the ground
        sy = round(piecewise(y, [ht, hh], [ht + d, hh + min(d1, 2)]))
        t = _frac(sy, ht, hh)
        return x - round(hx * (1 - 0.5 * t)) + round(sw * t), sy
    out.append(K.warp(layers['cloth'], cloth_src))
    out.append(limb.leg_pixels(near_leg))
    body = K.warp(extra('right')['body'], body_src, pad=16)
    out.append(body)
    if near_k in pieces:
        out.append(pieces[near_k][0][0])          # the upper arm, under the shoulder plate
    elif far:
        out.append(free_arm(S, s, sh_drawn))
    near_plate = K.warp(S['pauldron'], lambda x, y: plate_src(x - g_near[0], y - g_near[1]), pad=16)
    if near_k in pieces:
        near_plate = rotate_pixels(near_plate, (sh_drawn[0], sh_drawn[1] - PLATE_UP),
                                   plate_turn(dkey, near_k, s))
    out.append(near_plate)
    out.append(side_head(S, s, s1, far))
    out.append(nearB)
    if near_k in pieces:
        out.append(pieces[near_k][0][1])          # forearm
    out.append(nearH)
    if near_k in pieces:
        out.append(pieces[near_k][0][2])          # fist
    return AW._finish('right', out)


def free_arm(S, s, sh_drawn):
    """Facing left, one-handed: the near (left) arm hangs as in the walk, carried by the shoulder."""
    fa, J = S['free_arm'], S['free_joints']
    mx, my = round(sh_drawn[0] - S['shoulder'][0]), round(sh_drawn[1] - S['shoulder'][1])
    return {(x + mx, y + my): c for (x, y), c in fa.pix.items()}


def side_head(S, s, s1, far):
    """The head follows the chest a pose late (at most K.HEAD_LAG px behind); bowed it turns
    about the neck; it does not turn with the shoulders (it keeps looking where he strikes)."""
    lay, sm = S['lay'], S['sm']
    belt = sm['belt']
    d1 = K.lagged(s['D'], s1['D'])
    lean1 = math.tan(math.radians(s1['lx']))
    hx1 = K.lagged(round(s['hx']), round(s1['hx']))
    bow = s1.get('bow', 0.0)
    pv = lay.local_to_final(K.HEAD_PIVOT)
    dx = round(lean1 * max(0.0, belt - pv[1])) + hx1
    if abs(bow) < 0.5:
        return K.warp(S['layers']['head'], lambda x, y: (x - dx, y - d1), pad=16)
    return {(x + dx, y + d1): c for (x, y), c in K.head_side(bow).items()}


# ------------------------------------------------------------------ front and back views
def fb_tier(direction):
    if direction == 'down':
        def tier(p):
            return 'back' if p[0] < -12.0 else ('mid' if p[0] < 4.0 else 'front')
    else:
        def tier(p):
            return 'back' if p[0] > 0.0 else 'front'
    return tier


def front_back(direction, s, s1):
    sign = 1 if direction == 'down' else -1
    view = 'front' if direction == 'down' else 'back'
    S = AW._layers(direction)
    E = extra(direction)
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    # the hips forward show as lower (front) / higher (back)
    fwd = round(sign * DEPTH * s['hx'])
    fwd1 = round(sign * DEPTH * s1['hx'])
    d, d1 = s['D'] + fwd, s1['D'] + fwd1
    k = sign * round(s['lx'] * LEAN_ROWS / LEAN_DEG)
    k1 = sign * round(s1['lx'] * LEAN_ROWS / LEAN_DEG)
    belt, chest = sm['belt'], sm['chest']
    top = min(q[1] for q in layers['head'].pix)
    rows_src, rows_tgt = [top, chest, belt], [top + d + k, chest + d + k, belt + d]
    th = FB_DRAW * s['tw']
    tws = Twist(TWIST_X0[direction], TWIST_FB[0], TWIST_FB[1], th)

    def body_src(x, y):
        sy = round(piecewise(y, rows_src, rows_tgt))
        w = twist_weight(sy, sm)
        if w <= 0.0:
            return x, sy
        r = tws.src(x)
        if r is None:
            return None
        sx, dd = r
        return round(x + (sx - x) * w), round(sy - DEPTH * dd * w)

    def at(p):
        """Where a source point of the upper body is drawn."""
        w = twist_weight(p[1], sm)
        x1, dd = tws.fwd(p[0])
        y = piecewise(p[1], rows_tgt, rows_src) if False else p[1] + d + k
        return (p[0] + (x1 - p[0]) * w, y + DEPTH * dd * w)

    cs = s.get('cs', 0.0)

    def trail(t):
        return round(sign * -cs * t ** 1.5)
    cape_layer = E.get('cape', layers['cape'])
    cape = rig.warp(cape_layer, _cape_src(sm, d + k, cape_twist(tws), trail), pad=24)

    # legs
    feet = s['feet']
    hip_z = gait.HIP_REST - s['D']

    def legL(side_):
        x, out, z, pitch, down = feet[side_][:5]
        hxs = AT.hip_x(s, side_)
        L = gait.solve(hip_z, (x - hxs, z), pitch, down)
        L = {kk: ((v[0] + hxs, v[1]) if kk in ('hip', 'knee', 'ankle') else v) for kk, v in L.items()}
        if len(feet[side_]) > 5 and abs(feet[side_][5]) >= 0.5:
            L['lat'] = feet[side_][5]
        return L
    LR, LL = legL('R'), legL('L')
    inR, inL = -round(feet['R'][1]), -round(feet['L'][1])
    sideways = 'lat' in LR or 'lat' in LL

    # arms and sword
    arms = A.arms(s)
    shd = E['shoulder']
    gd = A.girdles(s)
    gs = {}
    for kk in 'RL':
        v = swd.project_vec(view, gd[kk])
        gs[kk] = (round(v[0]), round(v[1]))
    drawn = {kk: (at(shd[kk])[0] + gs[kk][0], at(shd[kk])[1] + gs[kk][1]) for kk in 'RL'}

    def plate(layer, kk):
        """A shoulder plate carried by its shoulder (the girdle's move, whole px) and turned
        with its upper arm."""
        dx, dy = gs[kk]
        pix = rig.warp(layer, lambda x, y: body_src(x - dx, y - dy), pad=16)
        if kk in pieces:
            pix = rotate_pixels(pix, (drawn[kk][0], drawn[kk][1] - PLATE_UP), plate_turn(direction, kk, s))
        return pix
    shR3 = A.shoulder('R', s)
    grip = screen(view, s['fist'], shR3, drawn['R'])
    pl = place(view, s['axis'], s['w3'], grip, S['place0'])
    pix = swd.sword_image(view, pl, BIG, source='bare', origin=(-EXT, -EXT))
    SWORD.update({(direction, s.get('name'), s.get('i')): (pix, pl, grip)})
    split = sword_split(view, pix, pl, s['fist'], s['axis'], fb_tier(direction))
    pieces = {}
    for kk, (J, sh3, e3, g3) in posed_arms(view, s, grip, {k_: (v, None) for k_, v in drawn.items()}).items():
        # front: the right arm is the left arm's drawing mirrored (as the carry); the left arm
        # as drawn. Back: the other way round (seen from behind)
        mirror = (kk == 'R') if direction == 'down' else (kk == 'L')
        pieces[kk] = (arm_pieces(J, mirror), (sh3, e3, g3))
        JOINTS[(direction, s.get('name'), s.get('i'), kk)] = J

    head = rig.warp(layers['head'], lambda x, y: (x, y - K.lagged(d + k, d1 + k1) - _bow_sink(direction, s1)), pad=16)
    out = []
    if direction == 'down':
        bH, bB = split.get('back', ({}, {}))
        mH, mB = split.get('mid', ({}, {}))
        fH, fB = split.get('front', ({}, {}))
        out += [bB, bH, cape, mB, mH]
        if sideways:
            # a sidestep's legs swing sideways: drawn from the concept as the sidestep draws them
            import fleg
            right = fleg.leg(LR, 'R', s['D'], 0, lay)
            left = fleg.leg(LL, 'L', s['D'], 0, lay)
            out.extend([right, left] if s.get('entry', ('',))[0] == 'strafe_r' else [left, right])
        else:
            out.append(rig.warp(layers['leg_l'], AW._leg_front_src(layers['leg_l'], lay, LR, d, 0, inR, AW.FRONT_LEG['leg_l']), pad=16))
            out.append(rig.warp(layers['leg_r'], AW._leg_front_src(layers['leg_r'], lay, LL, d, 0, -inL, AW.FRONT_LEG['leg_r']), pad=16))
        out.append(rig.warp(layers['drape'], _cape_src(sm, d + k, cape_twist(tws), trail), pad=16))
        out.append(rig.warp(E['body'], body_src, pad=16))
        ht, hh = sm['hang_top'], sm['hang_hem']
        for name, amp in (('chain', 0.6), ('tabard', 0.4)):
            hemx = round(-sign * s1.get('cs', 0.0) * amp)

            def hang_src(x, y, hemx=hemx):
                t = _frac(y - d, ht, hh)
                return x - round(hemx * t), y - d
            out.append(rig.warp(layers[name], hang_src))
        if arms['L'] is None:
            # the left arm hangs as approved, riding on the chest
            fb = layers['arm'].bbox()
            out.append(rig.warp(layers['arm'], lambda x, y: body_src(x, y), pad=16))
        order = sorted(pieces, key=lambda kk: -pieces[kk][1][1][0] * 0 + pieces[kk][1][1][0])
        for kk in order:
            out.append(pieces[kk][0][0])                         # upper arms
        out.append(plate(E['plateR'], 'R'))
        out.append(plate(E['plateL'], 'L'))
        out.append(head)
        out.append(fB)
        for kk in order:
            out.append(pieces[kk][0][1])                         # forearms
        out.append(fH)
        for kk in sorted(pieces, key=lambda kk: pieces[kk][1][2][0]):
            out.append(pieces[kk][0][2])                         # fists, the nearer on top
    else:
        bH, bB = split.get('back', ({}, {}))
        fH, fB = split.get('front', ({}, {}))
        hidden = {kk: [] for kk in 'RL'}
        shown = {kk: [] for kk in 'RL'}
        for kk, (P, (sh3, e3, g3)) in pieces.items():
            segs = ((P[0], sh3, e3), (P[1], e3, g3), (P[2], g3, g3))
            for px_, p0, p1 in segs:
                m = A.lerp(p0, p1, 0.5)
                (hidden if (m[0] > 4.0 and abs(m[1]) < 18.0) else shown)[kk].append(px_)
        out += [bB]
        for kk in 'RL':
            out += hidden[kk]
        out += [bH]
        boots = [('leg_l', LL, inL), ('leg_r', LR, -inR)]
        if s.get('entry', ('',))[0] == 'strafe_l':
            boots.reverse()
        for name, L, inward in boots:
            da = round(AW.leg_deltas(L, -1)[1])
            dx = inward + round(L.get('lat', 0.0))
            out.append(rig.warp(layers[name], lambda x, y, da=da, dx=dx: (x - dx, y - da), pad=30))
        out.append(cape)
        if arms['L'] is None:
            free = S['free']
            out.append(rig.warp(free, lambda x, y: body_src(x, y), pad=16))
        for kk in 'RL':
            out += shown[kk]
        out.append(plate(E['plateR'], 'R'))
        out.append(plate(E['plateL'], 'L'))
        out.append(head)
        out += [fB, fH]
    return AW._finish(direction, out)


def _bow_sink(direction, s1):
    bow1 = s1.get('bow', 0.0)
    return round(K.HEAD_SINK[direction] * max(0.0, bow1)) - round(0.15 * min(0.0, bow1))


def cape_twist(tws):
    return tws


def _cape_src(sm, d_top, tws, trail):
    """A cape / drape layer: its top rides the shoulders (and turns with them), the hem gives
    `trail(t)` sideways."""
    top, hem = sm['cape_top'], sm['cape_hem']

    def src(x, y):
        # the top rides the shoulders (d_top), the hem stays on the ground: rows are dropped in
        # between (anim_walk.cape_src)
        t = _frac(y - d_top, top, hem)
        dy = round(d_top * (1 - t))
        t = _frac(y - dy, top, hem)
        sy = y - dy
        x1 = x - trail(t)
        w = (1 - t) ** 2
        if w > 0.05:
            r = tws.src(x1)
            if r is not None:
                x1 = round(x1 + (r[0] - x1) * w)
        return x1, sy
    return src


# ------------------------------------------------------------------ poses -> frames
JOINTS = {}
SWORD = {}          # (direction, clip name, pose) -> (sword pixels before anything covers them, placement, grip)


def render_pose(direction, s, s1):
    if direction == 'left':
        return side.mirror(pose_side(s, s1, far=True))
    if direction == 'right':
        return pose_side(s, s1)
    return front_back(direction, s, s1)
