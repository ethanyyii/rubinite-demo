"""Pose rig: one pose description -> any of the four views.

The walk rigs (walk_side.py, walk_fb.py) animate one fixed cycle. Every other action is a
set of key poses, so a pose here is data: where the pelvis, feet, hands and sword are in
the character's own 3D space (F = forward, L = the character's left, U = up, in pixels).
Each view projects that space onto the screen, so the four facings of one pose stay the
same pose (animation-review.md §4.3: every facing is still checked on its own).

Appearance still comes from the 40 px library: helmet, plume, cape, scarf, pauldrons,
torso and legs are the reference's pixels (cut exactly as the walk rigs cut them). New
parts are drawn only where the library has nothing usable:
  N1 the sword at any angle (sword.py)
  N2 two-segment arms textured with the reference's own arm pixels, and a gauntlet fist
  N3/N4 follow from N1 + N2 (two-hand grip, the west-facing sword arm)
Layer order is decided per frame from depth, so the sword and the arms can pass in front
of or behind the body."""
import math

from rig import Layer, T, R, S, mat_mul, apply, close_holes, reconnect_specks, axis_map, body_fill, inpaint_reflect, point_in_poly
import sprites as A
import walk_side as W
import walk_fb as F
from walk_side import dimmed, snap
import sword as SW

# ------------------------------------------------------------------ canvases (fixed, 2026-09-27)
# the foot anchor sits 25 px below the canvas centre in both
CANVAS = {'small': (56, 56, 28, 53), 'large': (88, 72, 44, 61)}

# ------------------------------------------------------------------ projection
# Depth (toward / away from the camera) is foreshortened. The reference views are close to
# orthographic (both feet stand on the same row in the side views), so KD is small. In the
# side views the character is turned a little toward the camera: the far side shows a few
# pixels further forward (walk_side FAR_ARM_DX = 3.2 px for a ~21 px shoulder span).
KD = 0.35
KD_FEET = 0.55     # front / back views: a step toward the camera, see _fb_leg
KNEE_OUT = 0.9     # front / back views: how far bent knees spread
FOOT_BELOW = 1     # front / back views: lowest a foot may step toward the camera, px
# front / back views: a sideways foot offset, scaled like the reference's own stances (idle
# boots 16 px apart in front, 13 behind; the walk rig's hips 8.2 / 6.3 apart)
FEET_W = {'south': 1.0, 'north': 0.7, 'east': 1.0, 'west': 1.0}
SIDE_X = 0.15
PROJ = {
    'south': dict(F=(0.0, KD), L=(1.0, 0.0), toward=(1, 0)),     # toward camera = +F
    'north': dict(F=(0.0, -KD), L=(-1.0, 0.0), toward=(-1, 0)),  # toward camera = -F
    # side views: the reference draws both shoulders (and both feet) on the same rows, so the
    # depth axis has no vertical part there; the far side only shows a little further forward
    'east': dict(F=(1.0, 0.0), L=(SIDE_X, 0.0), toward=(0, -1)),  # the right side faces the camera
    'west': dict(F=(-1.0, 0.0), L=(SIDE_X, 0.0), toward=(0, 1)),   # the left side faces the camera
}


def proj(view, v):
    """Character-space vector (f, l, u) -> screen offset (dx, dy)."""
    f, l, u = v
    p = PROJ[view]
    return (f * p['F'][0] + l * p['L'][0], f * p['F'][1] + l * p['L'][1] - u)


def depth(view, v):
    """+ = toward the camera."""
    t = PROJ[view]['toward']
    return v[0] * t[0] + v[1] * t[1]


def vadd(a, b):
    return tuple(x + y for x, y in zip(a, b))


def vsub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def vscale(a, k):
    return tuple(x * k for x in a)


def vlen(a):
    return math.sqrt(sum(x * x for x in a))


def vnorm(a):
    n = vlen(a) or 1.0
    return vscale(a, 1.0 / n)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def ik3(shoulder, hand, l1, l2, hint):
    """Elbow of a two-bone arm in 3D, bending toward `hint` (a direction)."""
    d = vsub(hand, shoulder)
    dist = min(vlen(d), l1 + l2 - 1e-3)
    if dist < 1e-3:
        return vadd(shoulder, vscale(vnorm(hint), l1))
    u = vnorm(d)
    n = vsub(hint, vscale(u, dot(hint, u)))
    if vlen(n) < 1e-6:
        n = (0.0, 0.0, -1.0) if abs(u[2]) < 0.9 else (1.0, 0.0, 0.0)
        n = vsub(n, vscale(u, dot(n, u)))
    n = vnorm(n)
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    return vadd(shoulder, vadd(vscale(u, a), vscale(n, h)))


# ------------------------------------------------------------------ the gauntlet fist (N2)
# 3x3 core in the reference's arm colours: a lit knuckle top-left (palette 1 / 4), dark steel
# below (13 / 14 / 19 / 21),
# outlined like every part of the library
_P = W.PALETTE
FIST = {(0, 0): _P[1], (1, 0): _P[4], (2, 0): _P[13],
        (0, 1): _P[14], (1, 1): _P[13], (2, 1): _P[19],
        (0, 2): _P[19], (1, 2): _P[21], (2, 2): _P[21]}
UPPER, FORE = 6.0, 7.0          # shoulder-elbow, elbow-fist centre (40 px library: rest arm reaches 10-12.5 px)
ARM_R = (2.6, 2.2)              # half-thickness of upper arm and forearm (the reference arms are 5-6 px wide)


def tile_fill(torso, holes):
    """Body backing under the arms: mottled armour in the torso's own colours. The walk's
    mirror fill smears an edge colour across a wide hole into flat stripes, and tiling a
    patch prints a visible grid (animation-review §4.4), so each hole pixel takes a colour
    from the torso's own steel tones (outline and cloth excluded), picked by a fixed hash of
    its position and leaning to the darker half: the body under an arm is in shadow."""
    tones = sorted({c for c in torso.values() if 60 <= sum(c[:3]) <= 420 and not A.is_blue(c)},
                   key=lambda c: sum(c[:3]))
    out = dict(torso)
    if not tones:
        return inpaint_reflect(torso, holes, snap=snap)
    for (x, y) in holes:
        if (x, y) in torso:
            continue
        h = ((x * 73856093) ^ (y * 19349663)) % 1000 / 1000.0
        out[(x, y)] = tones[min(len(tones) - 1, int(len(tones) * 0.75 * h ** 1.4))]
    return out


def bend(anchor, tip, d, length, gamma=1.2):
    """Displacement that bends a strand hanging from `anchor` so its far end (at `tip`,
    relative to the anchor) moves by `d`: every point turns about the anchor by an angle that
    grows toward the end. Lengths are kept, so strands keep their pixels (a plain shear
    stretched or squashed them)."""
    ax, ay = anchor
    tx, ty = tip
    nx, ny = tx + d[0], ty + d[1]
    theta = math.atan2(ny, nx) - math.atan2(ty, tx)
    theta = (theta + math.pi) % (2 * math.pi) - math.pi
    L = math.hypot(tx, ty) or 1.0

    def disp(x, y):
        rx, ry = x - ax, y - ay
        t = max(0.0, min(1.0, math.hypot(rx, ry) / L)) ** gamma
        a = theta * t
        c, s_ = math.cos(a), math.sin(a)
        return rx * c - ry * s_ - rx, rx * s_ + ry * c - ry
    return disp


def fist_pixels(c, dim=1.0):
    cx, cy = int(math.floor(c[0])) - 1, int(math.floor(c[1])) - 1
    body = {(cx + x, cy + y): col + (255,) for (x, y), col in FIST.items()}
    if dim != 1.0:
        body = dimmed(body, dim)
    return body


def limb_pixels(pts, radii, tex, src_box, urange=(0.0, 1.0), glints=None):
    """Capsule segments through pts, textured with the reference's own pixels sampled from
    src_box = (x0, x1, y0, y1): along the limb -> down the box (the part urange of it),
    across -> across the box. The texture skips highlights; instead every highlight of the
    library arm itself (`glints`, in that part of the box) is carried to its place on the
    limb, as the legs do, so the new arm has as many glints as the reference arm."""
    x0, x1, y0, y1 = src_box
    ua, ub = urange
    body = {}
    for si in range(len(pts) - 1):
        (a, b), (c, d) = pts[si], pts[si + 1]
        r = radii[si]
        seglen = math.hypot(c - a, d - b) or 1e-6
        for y in range(int(math.floor(min(b, d) - r - 1)), int(math.ceil(max(b, d) + r + 1))):
            for x in range(int(math.floor(min(a, c) - r - 1)), int(math.ceil(max(a, c) + r + 1))):
                qx, qy = x + 0.5, y + 0.5
                t = max(0.0, min(1.0, ((qx - a) * (c - a) + (qy - b) * (d - b)) / seglen ** 2))
                px_, py_ = a + (c - a) * t, b + (d - b) * t
                dist = math.hypot(qx - px_, qy - py_)
                if dist > r:
                    continue
                side = ((c - a) * (qy - b) - (d - b) * (qx - a)) / seglen
                v = max(-1.0, min(1.0, side / r))
                u = ua + (ub - ua) * (si + t) / (len(pts) - 1)
                sx = int(round(x0 + (v + 1) / 2 * (x1 - x0)))
                sy = int(round(y0 + u * (y1 - y0)))
                col = None
                for ddx, ddy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0)):
                    q = tex.get((sx + ddx, sy + ddy))
                    if q is not None and not A.is_blue(q) and 45 < sum(q[:3]) <= 420:
                        col = q
                        break
                body[(x, y)] = col or A.D2
    segs = len(pts) - 1
    src = glints if glints is not None else tex
    # glints are placed by where they sit on the library arm itself (its own extent), not on
    # the texture box, so none of them falls outside
    gx0, gx1, gy0, gy1 = (min(x for x, _ in src), max(x for x, _ in src), min(y for _, y in src),
                          max(y for _, y in src)) if glints is not None else (x0, x1, y0, y1)
    for (x, y), c in src.items():
        if not (gx0 <= x <= gx1 and gy0 <= y <= gy1) or sum(c[:3]) <= 420 or A.is_blue(c):
            continue
        u = (y - gy0) / max(gy1 - gy0, 1)
        if not (ua <= u < ub or (ub == 1.0 and u == 1.0)):
            continue
        w = (u - ua) / max(ub - ua, 1e-6) * segs
        si = min(segs - 1, int(w))
        t = w - si
        (a, b), (c2, d) = pts[si], pts[si + 1]
        L = math.hypot(c2 - a, d - b) or 1.0
        nx, ny = -(d - b) / L, (c2 - a) / L
        v = (x - gx0) / max(gx1 - gx0, 1) * 2 - 1
        off = -v * radii[si] * 0.6
        key = (math.floor(a + (c2 - a) * t + nx * off), math.floor(b + (d - b) * t + ny * off))
        if key not in body or sum(body[key][:3]) > 420:
            # a glint near the edge, or two glints landing together (a short or foreshortened
            # limb): the nearest free limb pixel takes it, so none is dropped
            near = sorted((q for q in body if sum(body[q][:3]) <= 420),
                          key=lambda q: (q[0] - key[0]) ** 2 + (q[1] - key[1]) ** 2)
            key = near[0] if near and (near[0][0] - key[0]) ** 2 + (near[0][1] - key[1]) ** 2 <= 8 else None
        if key is not None:
            body[key] = c
    return body


def outline(body, out):
    ring = {}
    for (x, y) in body:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in body:
                ring[q] = A.OL
    out.update(ring)
    out.update(body)


# shoulder joints in chest space (origin = centre of the chest at shoulder height): the
# front view's pauldron centres are 21.2 px apart, the back view's 15.2 (the reference draws
# the back narrower); side views follow the front (3.2 px apart after SIDE_X)
CHEST_SH = {'R': (0.0, -10.6, 0.0), 'L': (0.0, 10.6, 0.0)}
SH_HALF = {'south': 10.6, 'north': 7.6, 'east': 10.6, 'west': 10.6}


def chest_sh(view, s_):
    h = SH_HALF[view]
    return (0.0, -h if s_ == 'R' else h, 0.0)


def hand_rel(view, s_, spec):
    """Hand target relative to its shoulder: specs give 'at' (chest space) or 'hand'
    (already shoulder-relative, front-view shoulders)."""
    if 'at' in spec:
        return vsub(spec['at'], chest_sh(view, s_))
    return vadd(vadd(spec['hand'], CHEST_SH[s_]), vscale(chest_sh(view, s_), -1))

def leg_tex(body, pix, hip, ankle, facing, leg_src, lens, radii):
    """sprites.draw_leg_tex without the boot, with the knee kept above the ankle (a copy, so
    the walk's output stays byte-identical)."""
    from limbs import knee_ik, seg_dist
    hx, hy = hip
    ax, ay = ankle
    kx, ky = knee_ik(hx, hy, ax, ay, lens[0], lens[1], forward=facing)
    if ky > ay - 1.0:
        k2 = knee_ik(hx, hy, ax, ay, lens[0], lens[1], forward=-facing)
        if k2[1] < ky:
            kx, ky = k2
        ky = min(ky, ay - 1.0)
    segs = [(hx, hy, kx, ky, radii[0]), (kx, ky, ax, ay, radii[1])]
    l1 = math.hypot(kx - hx, ky - hy)
    l2 = math.hypot(ax - kx, ay - ky)
    total = (l1 + l2) or 1.0
    sx0, sx1, sy0, sy1 = leg_src
    scx, shw = (sx0 + sx1) / 2, (sx1 - sx0) / 2
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
                    if col and not A.is_blue(col):
                        break
                    col = None
                col = col or A.D2
                if (x, y) not in body or si == 1:
                    body[(x, y)] = col
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
    return (kx, ky)


# ------------------------------------------------------------------ views
# Library joints are in native40 coordinates. 'R' / 'L' are the character's right / left.
VIEWS = {
    'south': dict(sprite='front', kind='fb', cfg=F.FRONT,
                  pelvis=(26.1, 40.8), neck=(26.1, 23.7),
                  sh={'R': (14.7, 28.6), 'L': (35.9, 27.8)},
                  leg={'R': 'leg_l', 'L': 'leg_r'},
                  arm={'R': 'arm_l', 'L': 'arm_r'}, paul={'R': 'paul_l', 'L': 'paul_r'},
                  tex={'R': (7, 12, 31, 38), 'L': (32, 38, 31, 38)}),
    'north': dict(sprite='back', kind='fb', cfg=F.BACK,
                  pelvis=(13.3, 40.4), neck=(14.9, 20.8),
                  sh={'L': (6.3, 26.3), 'R': (21.5, 26.3)},
                  leg={'L': 'leg_l', 'R': 'leg_r'},
                  arm={'L': 'arm_l', 'R': None}, paul={'L': 'paul_l', 'R': None},
                  tex={'L': (2, 11, 29, 37), 'R': (2, 11, 29, 37)}),
    'east': dict(sprite='side_right', kind='side', cfg=W.EAST, facing=1,
                 hip=(17.2, 41.0), neck=(19.2, 26.2),
                 sh={'R': (14.0, 29.0), 'L': (17.2, 29.0)},
                 near='R', arm={'R': 'arm', 'L': None}, paul={'R': 'pauldron', 'L': None},
                 tex={'R': (11, 22, 33, 40), 'L': (11, 22, 33, 40)}),
    'west': dict(sprite='side_left', kind='side', cfg=W.WEST, facing=-1,
                 hip=(13.2, 39.4), neck=(9.6, 22.2),
                 sh={'L': (14.4, 24.6), 'R': (11.2, 24.6)},
                 near='L', arm={'L': 'arm', 'R': None}, paul={'L': 'pauldron', 'R': None},
                 tex={'L': (4, 17, 27, 36), 'R': (4, 17, 27, 36)}),
}
# the body under the arms (library coordinates), for the backing fill
BODY_POLY = {
    'south': [(13.5, 24), (37, 24), (37, 31), (36, 40), (15, 40), (13.5, 31)],
    'north': [(5, 22), (26, 22), (26, 40), (5, 40)],
    'east': [(10, 24), (26, 24), (26, 41), (10, 41)],
    'west': [(4, 21), (21, 21), (21, 40), (5, 40)],
}
# idle stance of each foot relative to its own hip, along the facing (side views, from the
# walk rigs' boot cuts: east near boot ankle col 13 / hip 18.2, far 18 / 16.2 ...)
SIDE_REST_DX = {'east': {'R': -5.2, 'L': 1.8}, 'west': {'L': 2.2, 'R': -1.8}}


class PoseRig:
    def __init__(self, view):
        self.view = view
        self.v = VIEWS[view]
        v = self.v
        if v['kind'] == 'side':
            self.base = W.SideRig(v['cfg'])
        else:
            self.base = F.FBRig(v['cfg'])
        self.src = self.base.src
        meta = A.META[v['sprite']]
        self.ox, self.oy = A.CX - meta['cx'], A.GROUND - meta['feet']
        self._rebuild_backing()
        # the far end of each cloth piece, for bending it about its root
        cfg = v['cfg']
        self.tips = {}
        for n, anchor in (('cape', cfg['cape_anchor']), ('plume', cfg['knob'])):
            pts = list(self.base.L[n].pix)
            dmax = max(math.hypot(x + .5 - anchor[0], y + .5 - anchor[1]) for x, y in pts)
            far = [(x + .5, y + .5) for x, y in pts if math.hypot(x + .5 - anchor[0], y + .5 - anchor[1]) > 0.7 * dmax]
            self.tips[n] = (sum(p[0] for p in far) / len(far) - anchor[0], sum(p[1] for p in far) / len(far) - anchor[1])

    def _rebuild_backing(self):
        """The walk rigs back-fill every pixel the arm, pauldron and sword covered: arms
        hardly move in a walk, so it never shows. Here an arm can leave its place, and armour
        painted where the arm hung outside the body would read as a phantom limb. So the
        backing only fills what lies inside the body's own outline, row by row (torso and
        cape span, 1 px margin)."""
        v = self.v
        cfg = v['cfg']
        pix = self.src
        parts = W.split(pix, cfg['parts'](pix) if v['kind'] == 'fb' else cfg['parts'](), 'torso')
        cut = cfg['leg_cut'] if v['kind'] == 'fb' else cfg['cut']
        # the body's own outline under the arms, drawn by eye on the part overlays
        # (inspect_parts.py): arm / pauldron / sword pixels inside it are body to back-fill,
        # pixels outside it are where the limb hung in the air
        movers = [n for n in ('arm', 'arm_l', 'arm_r', 'pauldron', 'paul_l', 'paul_r', 'sword') if n in parts]
        poly = BODY_POLY[self.view]
        holes = {h for n in movers for h in parts[n]
                 if h[1] < cut and point_in_poly(h[0] + 0.5, h[1] + 0.5, poly)}
        # the arms are not grown into here (that painted phantom arms): only cloth and helmet
        over = ('cape', 'scarf', 'helmet') if v['kind'] == 'side' else \
            ('helmet',) + (('cape',) if v['sprite'] == 'back' else ())
        radius = W.FILL_RADIUS if v['kind'] == 'side' else F.FILL_RADIUS
        holes |= body_fill(parts, 'torso', over, cut, radius)
        _, size = A.SPR[v['sprite']]
        # outline pixels of a moving part that the cut left in the torso (they only touch the
        # arm / sword) would stay behind as a stray line when that part moves
        torso = parts['torso']
        dark = lambda c: sum(c[:3]) < 60
        mov = {h for n in movers for h in parts[n]}
        orphans = set()
        for (x, y), c in torso.items():
            if not dark(c):
                continue
            nb = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            if any(q in mov for q in nb) and not any(q in torso and not dark(torso[q]) for q in nb):
                orphans.add((x, y))
        torso = {k: c for k, c in torso.items() if k not in orphans}
        self.base.L['torso'] = Layer('torso', torso, size)
        self.base.L['backing'] = Layer('backing', tile_fill(torso, holes), size)
        if v['sprite'] == 'back':
            # the right arm hides under the cape in the reference; when it rises above the cape
            # it wears the left pauldron, mirrored about the spine
            pl = parts['paul_l']
            cx2 = 2 * 13.9
            self.base.L['paul_l_mirror'] = Layer('paul_l_mirror',
                                                 {(int(round(cx2 - x - 1)), y): c for (x, y), c in pl.items()}, size)

    # -------------------------------------------------------------- helpers
    def lib(self, p):
        """library point -> small-frame point at rest"""
        return (p[0] + self.ox, p[1] + self.oy)

    def render(self, pose, canvas='small'):
        view, v, L = self.view, self.v, self.base.L
        side = v['kind'] == 'side'
        fdir = v.get('facing', 1)
        # a pose may give lean / roll / head / head_tilt / arms per view ('<key>_view':
        # {view: value}), as the sword has dir_view. In the front / back views head_tilt turns
        # the head in the picture plane, so a bow there is a sinking head, not a turned one;
        # and a sword planted beside the feet needs the hand lower in the side views (to reach
        # the floor at a slant) than in front (for a blade long enough to read) (batch 1 heal)
        pose = dict(pose, **{k: pose[k + '_view'][view] for k in ('lean', 'roll', 'head', 'head_tilt', 'arms')
                             if view in pose.get(k + '_view', {})})
        items = []   # (depth, order, fn(px))
        seq = [0]

        def add(dep, fn, name=''):
            seq[0] += 1
            items.append((dep, seq[0], fn, name))

        # ---- body transform: root offset, lean, roll
        rx, ry = proj(view, pose.get('root', (0, 0, 0)))
        base = T(self.ox + rx, self.oy + ry)
        lean = pose.get('lean', 0.0)          # + = forward
        roll = pose.get('roll', 0.0)          # + = toward the character's left
        if side:
            hx, hy = v['hip']
            body = mat_mul(base, R(fdir * lean, hx, hy))
            # roll shows as a small shear of the shoulders along the view's depth: ignore
        else:
            # front / back: the upper body tips toward (south) or away from (north) the camera.
            # The torso keeps every pixel (squashing it would drop detail); the head,
            # shoulders and cape sink over it instead, as a lean reads from the front
            px0, py0 = v['pelvis']
            nx, ny = v['neck']
            h = py0 - ny
            a = math.radians(lean)
            drop = proj(view, (h * math.sin(a), 0, h * math.cos(a) - h))[1]
            rs = 1 if view == 'south' else -1
            body = mat_mul(base, R(rs * roll, px0, py0))
        upper = body if side else mat_mul(T(0, drop), body)
        self.debug['pelvis'] = apply(base, *(v['hip'] if side else v['pelvis']))
        self._upper_drop = 0.0 if side else drop
        # head: follows the neck, never stretched
        neck = v['neck']
        neck_w = apply(upper, *neck)
        head_off = proj(view, pose.get('head', (0, 0, 0)))
        tilt = pose.get('head_tilt', 0.0)
        if side:
            head = mat_mul(T(head_off[0], head_off[1]), mat_mul(body, R(fdir * tilt, *neck)))
        else:
            rs = 1 if view == 'south' else -1
            head = mat_mul(T(neck_w[0] - neck[0] + head_off[0], neck_w[1] - neck[1] + head_off[1]),
                           R(rs * (roll + tilt), *neck))

        # ---- cloth: each strand bends about its root (a rotation growing toward the tip), so
        # it keeps its length and its pixels; only what the pose asks for moves
        cape_v = pose.get('cape', (0, 0, 0))         # hem displacement, character space
        plume_v = pose.get('plume', (0, 0, 0))       # plume tip displacement
        scarf_v = pose.get('scarf', (0, 0, 0))
        cfg = v['cfg']
        cdx, cdy = proj(view, cape_v)
        ax0, ay0 = cfg['cape_anchor']
        clen = cfg['cape_len']
        lowered = max(0.0, -pose.get('root', (0, 0, 0))[2]) + max(0.0, getattr(self, '_upper_drop', 0.0))
        # front / back: the hem's flare follows the body; a breath or a step can make it follow
        # a frame late (animation-review §4.2: cloth ends lag their roots) by adding here
        lowered = max(0.0, lowered + pose.get('cape_lowered_add', 0.0))
        if side:
            cape_disp = bend((ax0, ay0), self.tips['cape'], (cdx, cdy), clen)
        else:
            # a cape seen from the front / back swings sideways (bend) and only lifts at the hem
            # where a lowered body would push it through the floor
            swing = bend((ax0, ay0), self.tips['cape'], (cdx, 0.0), clen)

            # a lowered body puts the hem on the floor: it flares outward (the bend keeps its
            # length) and whatever still reaches the floor lies on it
            flare = bend((ax0, ay0), self.tips['cape'], (cdx + cfg['cape_side'] * min(3.0, lowered) * (1 if view == 'south' else -1), 0.0), clen)

            def cape_disp(x, y, swing=flare):
                return swing(x, y)

        pdx, pdy = proj(view, plume_v)
        kx, ky = cfg['knob']
        plen = W.PLUME_WAVE[3] if side else cfg['plume_len']
        plume_disp = bend((kx, ky), self.tips['plume'], (pdx, pdy), plen)

        sdx, sdy = proj(view, scarf_v)
        if side:
            scx, scy = cfg['scarf_anchor']

            def scarf_disp(x, y):
                t = max(0.0, min(1.0, (y - scy) / cfg['scarf_len']))
                return sdx * t, sdy * t

        # ---- fixed parts, in the walk rigs' order (depth decides where limbs / sword go)
        if side:
            add(-100, lambda px: L['backing'].render(body, out=px), 'backing')
            add(-90, lambda px: L['helmet'].render(mat_mul(head, T(0, 1)), out=px), 'helmet_under')
            add(-80, lambda px: L['cape'].render(body, cape_disp, out=px), 'cape')
            add(0, lambda px: L['torso'].render(body, out=px), 'torso')
            add(10, lambda px: L['scarf'].render(body, scarf_disp, out=px), 'scarf')
            add(40, lambda px: L['plume'].render(head, plume_disp, out=px), 'plume')
            add(50, lambda px: L['helmet'].render(head, out=px), 'helmet')
        elif view == 'south':
            add(-100, lambda px: L['backing'].render(body, out=px), 'backing')
            add(-50, lambda px: L['cape'].render(upper, cape_disp, out=px), 'cape')
            add(-45, lambda px: L['plume'].render(head, plume_disp, out=px), 'plume')
            add(0, lambda px: L['torso'].render(body, out=px), 'torso')
            add(50, lambda px: L['helmet'].render(head, out=px), 'helmet')
        else:
            add(-100, lambda px: L['backing'].render(body, out=px), 'backing')
            add(-40, lambda px: L['helmet'].render(mat_mul(head, T(0, 1)), out=px), 'helmet_under')
            add(0, lambda px: L['torso'].render(body, out=px), 'torso')
            add(30, lambda px: L['cape'].render(upper, cape_disp, out=px), 'cape')
            add(45, lambda px: L['helmet'].render(head, out=px), 'helmet')
            add(46, lambda px: L['plume'].render(head, plume_disp, out=px), 'plume')

        # ---- legs
        feet = pose.get('feet', {})
        self._foot_below = pose.get('foot_below', FOOT_BELOW)
        if side:
            hip_w = apply(base, *v['hip'])
            near = v['near']
            far = 'L' if near == 'R' else 'R'
            for which, s_, dim, dep in (('far', far, 0.78, -60), ('near', near, 1.0, -55)):
                f_, l_, lift, state = feet.get(s_, (0, 0, 0, 'flat'))
                hip = (hip_w[0] + fdir * (1 if which == 'near' else -1), hip_w[1])
                # foot position: its rest stance plus the pose offset, measured from the hip;
                # the root offset moves the hip, so a planted foot is compensated here
                rf = pose.get('root', (0, 0, 0))[0]
                dx = SIDE_REST_DX[view][s_] + f_ - rf
                add(dep, lambda px, which=which, dx=dx, lift=lift, state=state, dim=dim, hip=hip:
                    self._side_leg(px, (dx, lift, state), which, dim, hip), 'leg_' + s_)
        else:
            order = []
            for s_ in ('R', 'L'):
                ft = feet.get(s_, (0, 0, 0))
                f_, l_, lift = ft[:3]
                kn = len(ft) > 3 and ft[3] == 'kneel'
                order.append((depth(view, (f_, l_, 0)), s_, f_, l_, lift, kn))
            for dep, s_, f_, l_, lift, kn in sorted(order):
                add(-60 + dep * 0.01, lambda px, s_=s_, f_=f_, l_=l_, lift=lift, kn=kn:
                    self._fb_leg(px, s_, f_, l_, lift, base, kn), 'leg_' + s_)

        # ---- arms (N2) and sword (N1)
        hands_w = {}
        arms = pose.get('arms', {})
        if 'sword' not in pose and arms.get('R') is None and 'sword' in L:
            # the sword hand is at rest: the library blade rides on the body, as in the walk
            dep_s = {'east': 15, 'west': -75, 'south': 15}.get(view)
            if dep_s is not None:
                add(dep_s, lambda px: L['sword'].render(upper, out=px), 'sword')
        sw = pose.get('sword')
        # a pose may pick a different blade angle per view: a blade pointing straight at the
        # camera is only a few pixels long, so a view can tilt it where it reads (pixel art is
        # drawn per view; the pose stays the same pose)
        blade3 = vnorm(sw.get('dir_view', {}).get(view, sw['dir'])) if sw else None
        for s_ in ('R', 'L'):
            spec = arms.get(s_)
            if spec is not None and 'on_grip' in spec and blade3 is not None:
                # the second hand holds the grip further toward the pommel, whatever the angle
                chest_r = vadd(hand_rel(view, 'R', arms['R']), chest_sh(view, 'R'))
                chest = vsub(chest_r, vscale(blade3, spec['on_grip']))
                spec = {k: val for k, val in spec.items() if k != 'hand'}
                spec['at'] = chest
                arms = dict(arms, **{s_: spec})
            if spec is None:
                # arm at rest: the library arm and pauldron ride on the body
                an, pn = v['arm'].get(s_), v['paul'].get(s_)
                if an:
                    dep_a = 20 if (not side or s_ == v['near']) else -70
                    add(dep_a, lambda px, an=an: L[an].render(upper, out=px), 'arm_' + s_)
                if pn:
                    add(22 if not side else 30, lambda px, pn=pn: L[pn].render(upper, out=px), 'paul_' + s_)
                continue
            sh_w = apply(upper, *v['sh'][s_])
            hand3 = hand_rel(view, s_, spec)
            hint = spec.get('elbow', (0, 0, -1))
            el3 = ik3((0, 0, 0), hand3, UPPER, FORE, hint)
            el_w = vadd(sh_w, proj(view, el3))
            hd_w = vadd(sh_w, proj(view, hand3))
            hands_w[s_] = hd_w
            self.debug.setdefault('hands', {})[s_] = hd_w
            dim = 1.0
            if side and s_ != v['near']:
                dim = 0.62
            # default depth from where the hand is in 3D (toward the camera = +):
            # side views: the near arm is in front of the body, the far arm behind it unless its
            # hand comes round to the front of the chest; front / back views: a hand pushed
            # forward goes in front of (south) or behind (north) the body
            chest = vadd(hand3, chest_sh(view, s_))
            tw = depth(view, chest)
            if side:
                d_up = 20 if s_ == v['near'] else -70
                d_fore = d_up if s_ == v['near'] else (18 if tw > -4 and chest[0] > 3 else -70)
            else:
                d_up = 20 if s_ == 'R' else 12
                if view == 'south':
                    d_fore = d_up if chest[0] < 3 else 26 + (1 if s_ == 'L' else 0)
                else:
                    d_fore = d_up if chest[0] < 3 else -30
                if view == 'north' and s_ == 'R':
                    raised = spec.get('over_cape', chest[2] > 2)
                    d_up = d_fore = 35 if raised else 25
                    spec = dict(spec, over_cape=raised)
            if spec.get('depth_upper') is not None:
                d_up = spec['depth_upper']
            if spec.get('depth_fore') is not None:
                d_fore = spec['depth_fore']
            tex_box = v['tex'][s_]
            add(d_up, lambda px, sh_w=sh_w, el_w=el_w, tb=tex_box, dim=dim, s_=s_:
                self._limb(px, [sh_w, el_w], [ARM_R[0]], tb, dim, (0.0, 0.5), s_), 'upper_' + s_)
            add(d_fore, lambda px, el_w=el_w, hd_w=hd_w, tb=tex_box, dim=dim, s_=s_:
                self._limb(px, [el_w, hd_w], [ARM_R[1]], tb, dim, (0.5, 1.0), s_), 'fore_' + s_)
            d_fist = spec.get('depth_fist')
            d_fist = d_fore + 0.5 if d_fist is None else d_fist
            if sw and (s_ == sw.get('hand', 'R') or 'on_grip' in spec):
                # a fist on the grip is always over the sword it holds (the crossguard would
                # otherwise cut across it when the blade is drawn in front of the body)
                sdep = sw.get('depth', {}).get(view)
                if sdep is None:
                    sdep = self._sword_depth(sw, arms)
                d_fist = max(d_fist, sdep + 0.5)
            add(d_fist, lambda px, hd_w=hd_w, dim=dim:
                outline(fist_pixels(hd_w, dim), px), 'fist_' + s_)
            pn = v['paul'].get(s_)
            if pn is None and view == 'north' and s_ == 'R' and spec.get('over_cape'):
                pn = 'paul_l_mirror'
            if pn and pn in L:
                # the pauldron rides the shoulder and tips a little toward the upper arm
                up2 = proj(view, el3)
                ang = math.degrees(math.atan2(up2[0], up2[1]))       # 0 = arm hanging down
                tip = max(-15.0, min(15.0, -0.3 * ang)) if side else 0.0
                sx_, sy_ = v['sh'][s_]
                pm = mat_mul(upper, R(tip, sx_, sy_))
                add((d_up if not side else 30) + 1, lambda px, pn=pn, pm=pm: L[pn].render(pm, out=px), 'paul_' + s_)
        if sw:
            hand = hands_w.get(sw.get('hand', 'R'))
            if hand is not None and 'planted' in sw:
                # a sword planted in the floor stays where it is while the body bobs over it
                # (the fist slides on the grip): drawn from the hand of the unbobbed pose
                hand = (hand[0] + sw['planted'][0], hand[1] + sw['planted'][1])
            if hand is not None:
                d3 = blade3
                d2 = proj(view, d3)
                ln = math.hypot(*d2)
                # the tip never goes below the floor: past the ground row the blade reads as
                # planted, so it is shortened to touch the floor (animation-review §4.4)
                if ln > 1e-6 and d2[1] > 0:
                    uy = d2[1] / ln
                    room = (A.GROUND - 1.5) - (hand[1] + uy * SW.GUARD_AT)
                    if uy * SW.BLADE * ln > room:
                        ln = max(0.1, room / (uy * SW.BLADE))
                dep = sw.get('depth', {}).get(view)
                if dep is None:
                    dep = self._sword_depth(sw, arms)
                gb = sw.get('grip_back', SW.GRIP_BACK)
                # a posed blade is lit on both rows, so it reads against the dark, speckled
                # armour wherever it crosses the body (animation-review §4.5); a pose may turn
                # it off per view with bright=(views...)
                br = view in sw['bright'] if 'bright' in sw else True
                def draw_sword(px, hand=hand, d2=d2, ln=ln, w=sw.get('width', {}).get(view, 2), gb=gb, br=br):
                    spx, blade = SW.sword_pixels(hand, d2, ln, w, gb, br)
                    # a low hand can still put the guard or pommel under the floor: the whole
                    # sword slides up in the fist (as the walk does), whole pixels only
                    sink = max(y for (_, y) in spx) - A.GROUND
                    if sink > 0:
                        spx = {(x, y - sink): c for (x, y), c in spx.items()}
                        blade = {(x, y - sink) for (x, y) in blade}
                    px.update(spx)
                    self.debug['blade'] = blade
                add(dep, draw_sword, 'sword')

        # every piece is drawn on its own, then laid down in depth order; trace keeps
        # which piece owns each pixel (for inspecting a pose)
        self.trace = {}
        self.pieces = {}
        self.pieces_raw = {}      # as drawn, before cloth folding on the floor
        for dep, _, fn, name in sorted(items, key=lambda it: (it[0], it[1])):
            tmp = {}
            fn(tmp)
            self.pieces_raw.setdefault(name, {}).update(tmp)
            if not name.startswith('leg'):
                # cloth (or a tasset corner) that a lean swings past the floor rests on it
                for k in [k for k in tmp if k[1] > A.GROUND]:
                    c = tmp.pop(k)
                    tmp.setdefault((k[0], A.GROUND), c)
            self._out.update(tmp)
            self.pieces.setdefault(name, {}).update(tmp)
            for k in tmp:
                self.trace[k] = name
        return self._finish(canvas)

    # -------------------------------------------------------------- pieces
    _out = None

    def _sword_depth(self, sw, arms):
        """Where the blade goes in the draw order, from the 3D middle of the blade: in front
        of everything when it is on the camera's side of the body, just over the torso when
        level with it, behind the body when on the far side."""
        view, side = self.view, self.v['kind'] == 'side'
        s_ = sw.get('hand', 'R')
        hand = vadd(hand_rel(view, s_, arms[s_]), chest_sh(view, s_))
        mid = vadd(hand, vscale(vnorm(sw.get('dir_view', {}).get(view, sw['dir'])), 7.5))
        d = depth(view, mid)
        if side:
            return 55 if d > 3 else 17 if d > -3 else -71
        if view == 'south':
            return 55 if d > 4 else 21 if d > -2 else -40
        return 47 if d > 3 else 21 if d > -2 else -31

    def _limb(self, px, pts, radii, box, dim, urange=(0.0, 1.0), side_='R'):
        an = self.v['arm'].get(side_) or next(a for a in self.v['arm'].values() if a)
        body = limb_pixels(pts, radii, self.src, box, urange, self.base.L[an].pix)
        if dim != 1.0:
            body = dimmed(body, dim)
        outline(body, px)

    def _side_leg(self, px, foot, which, dim, hip):
        """The walk rig's side leg (SideRig.leg), except that the knee never folds below the
        ankle: in a crouch the hip comes down close to the ankle and the two-bone solution
        bending forward can drop under the floor. The walk itself is untouched."""
        base = self.base
        c = base.cfg
        f = c['facing']
        dx, lift, state = foot
        pitch, pivot = W.FOOT_POSE.get(state, (0, 'heel'))
        bx0, bx1, by0, by1, bax = c[which + '_boot']
        heel_x = bx0 if f > 0 else bx1 + 1
        toe_x = bx1 + 1 if f > 0 else bx0
        ax = hip[0] + f * dx
        ay = A.GROUND - (by1 - by0 + 1) - lift - (W.TOE_RAISE if state == 'toe' else 0)
        ls = c[which + '_leg']
        ox, oy = self.ox, self.oy
        body = {}
        knee = leg_tex(body, base.shifted(ox, oy), hip, (ax, ay), f,
                       (ls[0] + ox, ls[1] + ox, ls[2] + oy, ls[3] + oy), W.LEG_LENS, W.LEG_RADII)
        self.debug.setdefault('legs', {})[which] = (hip, knee, (ax, ay))
        pvx = heel_x if pivot == 'heel' else toe_x
        world = mat_mul(T(ax - bax, ay - by0), R(f * pitch, pvx, by1 + 1.0))
        base.boots[which].render(world, out=body)
        if dim != 1.0:
            body = dimmed(body, dim)
        outline(body, px)

    def _fb_leg(self, px, s_, f_, l_, lift, base, kneel=False):
        c = self.v['cfg']
        name = self.v['leg'][s_]
        g = c['fleg'][name]
        view = self.view
        hip_d = apply(base, g['dest_x'], g['hip'][1])
        # a step toward / away from the camera is exaggerated a little over the body's KD:
        # at 40 px a 9 px lunge would otherwise move the boot only 3 px
        kf = KD_FEET if view == 'south' else -KD_FEET
        # a foot nearer the camera than the anchor may sit at most FOOT_BELOW px under the
        # ground row (animation-review §4.4: 2 px allowed; the walk uses 1)
        # a pose may allow the rule's full 2 px under the floor (batch 2: a planted foot held
        # back while the program carries the body away from the camera)
        off = (l_ * PROJ[view]['L'][0] * FEET_W[view], min(f_ * kf, getattr(self, '_foot_below', FOOT_BELOW)) - lift)
        ank_d = (g['dest_x'] + self.ox + off[0], g['ankle'][1] + self.oy + off[1])
        boot = self.base.L[name + '_boot']
        top, bot = self._leg_halves(name, g)
        mid = ((g['hip'][0] + g['ankle'][0]) / 2, (g['hip'][1] + g['ankle'][1]) / 2)
        if kneel:
            # knee on the ground: the thigh reaches the floor toward the camera (south) or away
            # (north); the shin and boot lie behind it, the boot's top peeking out
            knee = (ank_d[0], A.GROUND - 1.5 + (0 if view == 'south' else -2))
            bt = T(ank_d[0] - g['ankle'][0], ank_d[1] - g['ankle'][1] - (3 if view == 'south' else 1))
            under = boot.render(bt)
            thigh = {}
            top.render(axis_map(g['hip'], mid, hip_d, ((hip_d[0] + knee[0]) / 2, (hip_d[1] + knee[1]) / 2)), out=thigh)
            bot.render(axis_map(mid, g['ankle'], ((hip_d[0] + knee[0]) / 2, (hip_d[1] + knee[1]) / 2), knee), out=thigh)
            if view == 'south':
                px.update(under)
                px.update(thigh)
            else:
                px.update(thigh)
                px.update(under)
            return
        # bent knees: the two halves of the reference leg meet at a knee pushed outward (a
        # crouch seen from the front reads as knees apart, not as a shorter leg)
        lr = math.hypot(g['ankle'][0] - g['hip'][0], g['ankle'][1] - g['hip'][1])
        lc = math.hypot(ank_d[0] - hip_d[0], ank_d[1] - hip_d[1])
        mx, my = (hip_d[0] + ank_d[0]) / 2, (hip_d[1] + ank_d[1]) / 2
        out_ = math.sqrt(max((lr / 2) ** 2 - (lc / 2) ** 2, 0.0)) * KNEE_OUT
        knee = (mx + g['side'] * out_, my)
        self.debug.setdefault('legs', {})[s_] = (hip_d, knee, ank_d)
        top.render(axis_map(g['hip'], mid, hip_d, knee), out=px)
        bot.render(axis_map(mid, g['ankle'], knee, ank_d), out=px)
        px.update(boot.render(T(ank_d[0] - g['ankle'][0], ank_d[1] - g['ankle'][1])))

    def _leg_halves(self, name, g):
        key = name + '_halves'
        if key not in self.base.L:
            pix = self.base.L[name + '_strip'].pix
            _, size = A.SPR[self.v['sprite']]
            my = (g['hip'][1] + g['ankle'][1]) / 2
            self.base.L[key] = (Layer(name + '_top', {k: c for k, c in pix.items() if k[1] + 0.5 < my}, size),
                                Layer(name + '_bot', {k: c for k, c in pix.items() if k[1] + 0.5 >= my}, size))
        return self.base.L[key]

    def _finish(self, canvas):
        W_, H_, cx, gy = CANVAS[canvas]
        dx, dy = cx - A.CX, gy - A.GROUND
        px = {(x + dx, y + dy): c for (x, y), c in self._out.items()}
        drawn = set(px)
        reconnect_specks(px)
        # poses open wider seams than the walk (cloth touching a leg, an arm against the body)
        close_holes(px, W_, H_, max_size=14)
        # the clean-up may bridge a speck across the floor line: below the ground it may only
        # join a boot (a foot may step 2 px toward the camera), nothing else goes under
        legs = {(x + dx, y + dy) for (x, y), n in self.trace.items() if n.startswith('leg')}
        for k in [k for k in px if k not in drawn and k[1] > gy]:
            if not any((k[0] + a, k[1] + b) in legs for a in (-1, 0, 1) for b in (-1, 0, 1)):
                px.pop(k)
        return px

    def frame(self, pose, canvas='small'):
        """Pixels of one pose on the canvas. Afterwards self.pieces holds each piece as drawn
        (before compositing), self.trace which piece owns each pixel, and self.debug the
        hands and the blade (small-frame coordinates; add canvas_offset() for the canvas)."""
        self._out = {}
        self.debug = {'blade': set()}
        self.canvas = canvas
        return self.render(pose, canvas)

    def canvas_offset(self):
        _, _, cx, gy = CANVAS[self.canvas]
        return cx - A.CX, gy - A.GROUND


_RIGS = {}


def rig(view):
    if view not in _RIGS:
        _RIGS[view] = PoseRig(view)
    return _RIGS[view]


def image(px, canvas='small'):
    from PIL import Image
    W_, H_, _, _ = CANVAS[canvas]
    im = Image.new('RGBA', (W_, H_), (0, 0, 0, 0))
    for (x, y), c in px.items():
        if 0 <= x < W_ and 0 <= y < H_:
            im.putpixel((x, y), c)
    return im
