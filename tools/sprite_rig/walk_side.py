"""Side-view walk on the cut-out rig (east = side_right sprite, west = side_left sprite).

Every body part is the reference's own pixels; only its pose changes per frame."""
import math
from rig import Layer, T, R, mat_mul, apply, point_in_poly, is_blue, inpaint, body_fill, close_holes, inpaint_reflect, reconnect_specks
import sprites as A   # part library, frame layout, textured legs

N = 8   # frames per cycle


def split(pix, parts, default):
    """parts: list of (name, predicate(x, y, c)). First match wins; rest -> default."""
    out = {name: {} for name, _ in parts}
    out[default] = {}
    for (x, y), c in pix.items():
        for name, pred in parts:
            if pred(x, y, c):
                out[name][(x, y)] = c
                break
        else:
            out[default][(x, y)] = c
    return out


def inside(pts, pred=None):
    def f(x, y, c):
        return point_in_poly(x + .5, y + .5, pts) and (pred is None or pred(c))
    return f


not_blue = lambda c: not is_blue(c)

# All coordinates are in the 40 px library (native40/). They were derived from the 50 px
# rig with each view's exact scale (x' = x*s, y' = (y - helmet_top)*s + new_helmet_top) and
# then checked against the 40 px sprites (part overlays), so thresholds that fall inside a
# pixel were decided by looking at the pixels, not by rounding.
EAST = dict(
    sprite='side_right', facing=1, cut=42, hip=(17.2, 41.0),
    neck=(19.2, 26.2), knob=(20.4, 11.4), shoulder=(14.0, 29.0),
    sword_on='arm', grip=(22.4, 38.2), sword_tip=(40.4, 50.6),
    cape_anchor=(12.8, 23.0), cape_len=27.2, scarf_anchor=(24.0, 30.2), scarf_len=11.2,
    parts=lambda: [
        ('plume', lambda x, y, c: y <= 10),
        ('legs', lambda x, y, c: y >= 42 and 10 <= x <= 24),
        ('cape', lambda x, y, c: y >= 21 and (x <= 10 or (x <= 12 and is_blue(c)))),
        ('sword', inside([(24.0, 37.4), (27.2, 36.6), (40.8, 48.6), (40.8, 51.0), (36.0, 51.0), (24.0, 39.8)], not_blue)),
        ('scarf', lambda x, y, c: is_blue(c) and x >= 23 and y >= 29),
        ('helmet', inside([(8.0, 11.0), (30.4, 11.0), (30.4, 27.4), (20.8, 27.4), (17.6, 24.6), (12.0, 23.0), (8.0, 20.6)], not_blue)),
        ('pauldron', inside([(9.6, 25.4), (17.6, 24.6), (18.8, 29.4), (16.8, 32.6), (10.4, 32.6)])),
        ('arm', inside([(10.4, 32.6), (16.8, 32.6), (17.6, 34.6), (21.6, 35.0), (23.6, 38.2), (21.6, 41.4), (14.4, 41.4), (10.4, 39.8)])),
    ],
    # the lit leg texture (knee/greave highlights) is the left half of the idle legs, so the
    # near (undimmed) leg samples it; the far leg is drawn darker for depth
    near_leg=(12, 17, 42, 47), far_leg=(16, 22, 42, 47),
    near_boot=(10, 16, 48, 50, 13), far_boot=(16, 23, 48, 50, 18),
)

WEST = dict(
    sprite='side_left', facing=-1, cut=40, hip=(13.2, 39.4),
    neck=(9.6, 22.2), knob=(9.6, 7.0), shoulder=(14.4, 24.6),
    sword_on='back', grip=(20.0, 35.0), sword_tip=(27.6, 46.6),
    cape_anchor=(20.0, 19.0), cape_len=28.8, scarf_anchor=(7.2, 21.4), scarf_len=10.4,
    parts=lambda: [
        ('plume', lambda x, y, c: y <= 6 or (y <= 8 and x >= 11) or (y <= 17 and x >= 20)),
        ('legs', lambda x, y, c: y >= 40 and 4 <= x <= 21),
        ('sword', inside([(18.4, 33.4), (22.0, 34.2), (28.8, 45.4), (28.4, 47.4), (25.6, 47.4), (18.4, 36.6)], not_blue)),
        ('cape', lambda x, y, c: y >= 19 and (x >= 29 or (x >= 20 and (is_blue(c) or y >= 27)))),
        ('scarf', lambda x, y, c: is_blue(c) and x <= 10 and 21 <= y <= 32),
        ('helmet', inside([(0.0, 6.2), (20.0, 6.2), (20.0, 17.4), (16.0, 19.0), (9.6, 20.6), (8.8, 23.0), (0.0, 23.0)], not_blue)),
        ('pauldron', inside([(8.8, 21.4), (20.8, 21.4), (20.8, 27.0), (8.8, 27.0)], not_blue)),
        ('arm', inside([(10.4, 27.0), (19.2, 27.0), (19.2, 33.4), (14.4, 35.0), (9.6, 37.8), (2.4, 37.8), (2.4, 32.6), (8.0, 31.0), (10.4, 30.2)], not_blue)),
    ],
    near_leg=(7, 12, 38, 43), far_leg=(13, 19, 38, 43),
    near_boot=(4, 12, 44, 46, 10), far_boot=(12, 20, 44, 46, 16),
)

# near-foot keyframes over 8 frames: (ankle dx along facing, lift, foot state)
# 50 px: dx 8 5 1 -3 -7 -4 1 6, lift 0 0 0 0 0 3 5 3
NEAR_FOOT = [(6.4, 0, 'heel'), (4.0, 0, 'flat'), (0.8, 0, 'flat'), (-2.4, 0, 'flat'),
             (-5.6, 0, 'toe'), (-3.2, 2.4, 'swing'), (0.8, 4.0, 'swing'), (4.8, 2.4, 'reach')]
LEG_LENS = (4.96, 4.48)      # thigh, shin (50 px: 6.2, 5.6)
LEG_RADII = (2.4, 2.1)       # thigh, shin half-thickness (50 px: 3.0, 2.6)
TOE_RAISE = 2                # ankle rises when the heel lifts (50 px: 2)
# boot pitch per state (deg, + = toe down for the facing direction) and pivot
FOOT_POSE = {'heel': (-16, 'heel'), 'flat': (0, 'heel'), 'toe': (24, 'toe'),
             'swing': (10, 'heel'), 'reach': (-8, 'heel')}
BOB = [0, 1, 1, -1, 0, 1, 1, -1]   # whole pixels; 50 px had the same (0.8 x 1 rounds to 1)
FAR_ARM_DX = 3.2                   # far shoulder sits this far toward the front (50 px: 4)
CAPE_WAVE = (1.6, 1.04, 0.72)      # trail, wave, lift in px (50 px: 2.0, 1.3, 0.9)
PLUME_WAVE = (0.8, 0.96, 0.72, 17.6)   # trail, wave, bob, length (50 px: 1.0, 1.2, 0.9, 22)
SCARF_WAVE = (0.48, 0.64)          # trail, wave (50 px: 0.6, 0.8)
FILL_RADIUS = 8                    # body backing reaches this far under parts (50 px: 10)


PALETTE = [tuple(int(v) for v in line.split()) for line in open(A.D + 'palette.txt') if line.strip()]
_snap = {}


def snap(c):
    k = c[:3]
    if k not in _snap:
        _snap[k] = min(PALETTE, key=lambda q: (q[0] - k[0]) ** 2 * 3 + (q[1] - k[1]) ** 2 * 4 + (q[2] - k[2]) ** 2 * 2) + (255,)
    return _snap[k]


def dimmed(px, k):
    """Darker copy for far-side limbs, snapped back onto the reference palette."""
    return {p: snap((int(v[0] * k), int(v[1] * k), int(v[2] * k))) for p, v in px.items()}


class SideRig:
    def __init__(self, cfg):
        self.cfg = cfg
        self._shift_cache = {}
        pix, size = A.SPR[cfg['sprite']]
        self.src = pix
        parts = split(pix, cfg['parts'](), 'torso')
        # the torso keeps plausible armour where arm / pauldron / sword used to be
        holes = {h for n in ('arm', 'pauldron', 'sword') for h in parts[n] if h[1] < cfg['cut']}
        holes |= body_fill(parts, 'torso', ('cape', 'scarf', 'helmet', 'arm', 'pauldron'), cfg['cut'], FILL_RADIUS)
        # the filled body is only a backing drawn underneath everything: it shows through
        # where a moving part uncovers the body, and never paints over reference pixels
        backing = inpaint_reflect(parts['torso'], holes, snap=snap)
        self.parts = parts
        self.L = {n: Layer(n, p, size) for n, p in parts.items() if n != 'legs'}
        self.L['backing'] = Layer('backing', backing, size)
        self.boots = {}
        for which in ('near', 'far'):
            bx0, bx1, by0, by1, _ = cfg[which + '_boot']
            self.boots[which] = Layer(which + '_boot', {k: v for k, v in pix.items()
                                                       if bx0 <= k[0] <= bx1 and by0 <= k[1] <= by1 and not is_blue(v)}, size)

    def shifted(self, ox, oy):
        key = (ox, oy)
        if key not in self._shift_cache:
            self._shift_cache[key] = {(x + ox, y + oy): col for (x, y), col in self.src.items()}
        return self._shift_cache[key]

    def leg(self, out, foot, which, dim, hip, ox, oy):
        """Thigh + shin textured from the reference leg; boot = the reference boot pixels
        pitched for heel strike / toe off."""
        c = self.cfg
        f = c['facing']
        dx, lift, state = foot
        pitch, pivot = FOOT_POSE[state]
        bx0, bx1, by0, by1, bax = c[which + '_boot']
        heel_x = bx0 if f > 0 else bx1 + 1
        toe_x = bx1 + 1 if f > 0 else bx0
        ax = hip[0] + f * dx
        # the boot's own height puts its sole on the ground row
        ay = A.GROUND - (by1 - by0 + 1) - lift - (TOE_RAISE if state == 'toe' else 0)
        ls = c[which + '_leg']
        tmp = A.Frame()
        A.draw_leg_tex(tmp, self.shifted(ox, oy), hip, (ax, ay), f,
                       (ls[0] + ox, ls[1] + ox, ls[2] + oy, ls[3] + oy),
                       (0, -1, 0, -1, 0), 1.0, ring_over=True, lens=LEG_LENS, radii=LEG_RADII)
        body = dict(tmp.px)
        pvx = heel_x if pivot == 'heel' else toe_x
        world = mat_mul(T(ax - bax, ay - by0), R(f * pitch, pvx, by1 + 1.0))
        self.boots[which].render(world, out=body)
        if dim != 1.0:
            body = dimmed(body, dim)
        ring = {}
        for (x, y) in body:
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q not in body:
                    ring[q] = A.OL
        out.px.update(ring)
        out.px.update(body)

    def frame(self, i):
        c = self.cfg
        f = c['facing']
        phi = 2 * math.pi * i / N
        meta = A.META[c['sprite']]
        ox, oy = A.CX - meta['cx'], A.GROUND - meta['feet']
        bob = BOB[i]
        hx, hy = c['hip']
        # root: place, bob, lean forward about the hip (deeper on the down beat)
        lean = f * (4.0 + 1.5 * math.sin(2 * phi + 0.8))
        root = mat_mul(T(ox, oy + bob), R(lean, hx, hy))
        # head lags the body by one frame and nods a little
        head_lag = BOB[(i - 1) % N] - bob
        head = mat_mul(root, mat_mul(T(0, 0.6 * head_lag), R(-f * 1.5 * math.sin(2 * phi), *c['neck'])))
        # arms swing opposite their legs; + swing = near hand moves back
        swing = f * 12.0 * math.cos(phi)
        arm = mat_mul(root, R(swing, *c['shoulder']))
        paul = mat_mul(root, R(0.3 * swing, *c['shoulder']))
        sx, sy = c['shoulder']
        far_arm = mat_mul(root, mat_mul(T(f * FAR_ARM_DX, 0), R(-swing, sx, sy)))
        # the sword only translates with the hand that holds it (whole pixels): rotating a
        # 1-2 px blade resamples it thicker/thinner, so the reference blade is kept intact
        if c['sword_on'] == 'arm':
            grip_w = apply(arm, *c['grip'])
        else:
            # hangs from the far hand behind the body, which swings opposite the near arm
            grip_w = apply(mat_mul(root, R(-0.5 * swing, sx, sy)), *c['grip'])
        tx = round(grip_w[0] - c['grip'][0])
        ty = round(grip_w[1] - c['grip'][1])
        # the tip never digs into the floor: the blade slides up inside the fist instead
        while c['sword_tip'][1] + ty > A.GROUND - 0.5:
            ty -= 1
        sword = T(tx, ty)

        ax0, ay0 = c['cape_anchor']
        clen = c['cape_len']

        def cape_disp(px_, py_):
            v = max(0.0, min(1.0, math.hypot(px_ - ax0, py_ - ay0) / clen))
            trail, wave, lift = CAPE_WAVE
            return (-f * v ** 1.3 * (trail + wave * math.sin(2 * phi - 3.2 * v)),
                    -lift * v ** 1.5 * (1 + math.sin(2 * phi - 3.2 * v - 0.6)))

        kx, ky = c['knob']

        def plume_disp(px_, py_):
            trail, wave, bob_, length = PLUME_WAVE
            v = max(0.0, min(1.0, math.hypot(px_ - kx, py_ - ky) / length))
            return (-f * v * (trail + wave * math.sin(2 * phi - 3.0 * v)),
                    bob_ * v * math.sin(2 * phi - 3.0 * v - 1.2))

        scx, scy = c['scarf_anchor']

        def scarf_disp(px_, py_):
            v = max(0.0, min(1.0, (py_ - scy) / c['scarf_len']))
            return -f * v * (SCARF_WAVE[0] + SCARF_WAVE[1] * math.sin(2 * phi - 2.0 * v)), 0

        out = A.Frame()
        px = out.px
        # exposed for checks.py: where the head is this frame
        self.debug = {'head_y': apply(head, *c['knob'])[1]}
        self.L['backing'].render(root, out=px)
        self.L['helmet'].render(mat_mul(head, T(0, 1)), out=px)
        self.L['cape'].render(root, cape_disp, out=px)
        if c['sword_on'] == 'back':
            self.L['sword'].render(sword, out=px)
        hip_w = apply(root, hx, hy)
        near, far = NEAR_FOOT[i], NEAR_FOOT[(i + 4) % N]
        self.leg(out, far, 'far', 0.78, (hip_w[0] - f, hip_w[1]), ox, oy)
        self.leg(out, near, 'near', 1.0, (hip_w[0] + f, hip_w[1]), ox, oy)
        if c['sword_on'] == 'arm':
            px.update(dimmed(self.L['arm'].render(far_arm), 0.62))
        self.L['torso'].render(root, out=px)
        if c['sword_on'] == 'arm':
            self.L['sword'].render(sword, out=px)
        self.L['scarf'].render(root, scarf_disp, out=px)
        self.L['arm'].render(arm, out=px)
        self.L['pauldron'].render(paul, out=px)
        self.L['plume'].render(head, plume_disp, out=px)
        self.L['helmet'].render(head, out=px)
        reconnect_specks(px)
        close_holes(px, A.FW, A.FH, max_size=8)
        return out
