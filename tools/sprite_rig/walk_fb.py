"""Front / back walk on the cut-out rig. Every part is the reference's own pixels."""
import math
from rig import Layer, T, R, mat_mul, apply, is_blue, inpaint, body_fill, close_holes, inpaint_reflect, reconnect_specks, axis_map
from walk_side import split, inside, not_blue, N, BOB, dimmed, snap
import sprites as A   # part library, frame layout, textured legs

# All coordinates are in the 40 px library (native40/), derived from the 50 px rig with each
# view's exact scale and checked against the 40 px sprites (see walk_side.py).
FRONT = dict(
    sprite='front', pelvis=(26.1, 40.8), neck=(26.1, 23.7), knob=(26.1, 9.0),
    sh_l=(14.7, 28.6), sh_r=(35.9, 27.8), grip=(10.6, 37.6),
    cape_anchor=(38.4, 22.9), cape_len=24.5, cape_side=1,
    plume_len=21.2, plume_side=1,
    leg_cut=41,
    # legs straight down from the hips (the idle pose is a wide, braced stance);
    # 50 px: hips 26.5 / 36.5 (10 apart) -> 8.2 apart here
    fleg={'leg_l': dict(hip=(19.6, 40.4), ankle=(18.8, 45.7), boot_top=46, dest_x=21.6, side=-1),
          'leg_r': dict(hip=(31.4, 40.4), ankle=(34.3, 45.7), boot_top=46, dest_x=29.8, side=1)},
    parts=lambda pix: [
        ('plume', lambda x, y, c: y <= 8 or (y <= 20 and x >= 39) or (y <= 11 and is_blue(c))),
        ('sword', inside([(-0.8, 49.8), (-0.8, 45.7), (7.4, 38.0), (9.4, 37.6), (11.0, 38.8), (3.3, 49.8)], not_blue)),
        ('leg_l', lambda x, y, c: y >= 41 and 12 <= x <= 25 and not is_blue(c)),
        ('leg_r', lambda x, y, c: y >= 41 and 28 <= x <= 40 and not is_blue(c)),
        ('cape', lambda x, y, c: y >= 21 and (x >= 41 or (x >= 38 and is_blue(c)))),
        ('helmet', inside([(12.2, 9.0), (40.0, 9.0), (40.0, 19.6), (35.9, 22.5), (31.0, 23.3), (24.5, 24.5), (18.0, 23.3), (13.1, 20.4)], not_blue)),
        ('arm_l', inside([(7.3, 30.6), (18.8, 30.6), (18.8, 34.3), (15.5, 39.6), (6.5, 39.6)], not_blue)),
        ('paul_l', inside([(9.8, 24.9), (20.4, 24.9), (20.4, 30.6), (9.8, 30.6)], not_blue)),
        ('arm_r', inside([(31.0, 30.6), (40.0, 30.6), (40.0, 39.6), (31.8, 39.6)], not_blue)),
        ('paul_r', inside([(28.6, 23.3), (40.0, 23.3), (40.0, 30.6), (28.6, 30.6)], not_blue)),
    ],
)


def cloth_set(pix, min_y, min_x=-99):
    """Blue cloth plus the dark outline pixels that border it."""
    blue = {k for k, c in pix.items() if is_blue(c) and k[1] >= min_y and k[0] >= min_x}
    edge = set()
    for (x, y) in blue:
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            c = pix.get(q)
            if c and q not in blue and sum(c[:3]) < 135:
                edge.add(q)
    return blue | edge


def back_parts(pix):
    cape = cloth_set(pix, 21, 5)
    return [
        ('plume', lambda x, y, c: y <= 8 or (y <= 11 and (x <= 8 or x >= 20 or is_blue(c)))),
        ('leg_l', lambda x, y, c: y >= 40 and (5 if y < 42 else 2) <= x <= 13 and (x, y) not in cape),
        ('leg_r', lambda x, y, c: y >= 40 and 14 <= x <= 24 and (x, y) not in cape),
        ('cape', lambda x, y, c: (x, y) in cape or (y >= 32 and x >= 26)),
        ('helmet', inside([(3.1, 9.0), (26.7, 9.0), (26.7, 19.2), (22.7, 21.2), (6.3, 21.2), (3.1, 19.2)], not_blue)),
        ('paul_l', inside([(1.6, 22.7), (10.2, 22.7), (10.2, 29.0), (1.6, 29.0)], not_blue)),
        ('arm_l', inside([(-0.8, 29.0), (11.8, 29.0), (13.3, 38.4), (4.7, 38.4), (4.7, 41.6), (-0.8, 41.6)], not_blue)),
    ]


BACK = dict(
    sprite='back', pelvis=(13.3, 40.4), neck=(14.9, 20.8), knob=(15.7, 9.8),
    sh_l=(6.3, 26.3), grip=None,
    cape_anchor=(14.1, 21.6), cape_len=26.7, cape_side=1,
    plume_len=12.5, plume_side=0,
    leg_cut=40,
    # 50 px: hips 14 / 22 (8 apart) -> 6.3 apart here
    fleg={'leg_l': dict(hip=(9.4, 40.0), ankle=(7.8, 45.9), boot_top=46, dest_x=11.0, side=-1),
          'leg_r': dict(hip=(18.0, 40.0), ankle=(19.6, 45.9), boot_top=46, dest_x=17.3, side=1)},
    parts=back_parts,
)

# vertical foot offset per frame for the leg that contacts at frame 0 (+ = toward camera),
# whole pixels so the reference boot pixels are kept (50 px: 1 0 0 0 -1 -3 -4 -2)
LIFT = [1, 0, 0, 0, -1, -2, -3, -2]
SWAY = 0.8                  # pelvis shift over the stance leg, px (50 px: 1.0)
ROLL = 2.2                  # shoulder counter-roll, degrees (unchanged)
ARM_SWING = (0.65, 0.9, 6)  # hand tuck px, hand drop px, degrees (50 px: 0.8, 1.1, 6)
PAUL_DROP = 0.4             # pauldron follows the arm, px (50 px: 0.5)
CAPE_WAVE = (1.3, 0.65, 0.57)   # side swing, flutter, lift px (50 px: 1.6, 0.8, 0.7)
PLUME_WAVE = (1.06, 0.49, 0.65)  # swing, lean, bob px (50 px: 1.3, 0.6, 0.8)
INWARD = 1                  # swinging foot drifts toward the midline, px (50 px: 1)
SWING_INWARD = (5, 6)       # cycle frames of that drift (same frames as 50 px)
FILL_RADIUS = 7             # body backing reaches this far under parts (50 px: 8)


class FBRig:
    def __init__(self, cfg):
        self.cfg = cfg
        pix, size = A.SPR[cfg['sprite']]
        self.src = pix
        parts = split(pix, cfg['parts'](pix), 'torso')
        holes = {h for n in ('arm_l', 'arm_r', 'paul_l', 'paul_r', 'sword') if n in parts for h in parts[n]
                 if h[1] < cfg['leg_cut']}
        # the cape hangs behind the body in the front view, in front of it in the back view
        over = ('helmet', 'arm_l', 'arm_r', 'paul_l', 'paul_r') + (('cape',) if cfg['sprite'] == 'back' else ())
        holes |= body_fill(parts, 'torso', over, cfg['leg_cut'], FILL_RADIUS)
        backing = inpaint_reflect(parts['torso'], holes, snap=snap)
        self.L = {n: Layer(n, p, size) for n, p in parts.items()}
        self.L['backing'] = Layer('backing', backing, size)
        for n, g in cfg['fleg'].items():
            bt = g['boot_top']
            self.L[n + '_strip'] = Layer(n, {k: v for k, v in parts[n].items() if k[1] < bt}, size)
            self.L[n + '_boot'] = Layer(n, {k: v for k, v in parts[n].items() if k[1] >= bt}, size)

    def frame(self, i):
        c = self.cfg
        phi = 2 * math.pi * i / N
        meta = A.META[c['sprite']]
        ox, oy = A.CX - meta['cx'], A.GROUND - meta['feet']
        bob = BOB[i]
        px_, py_ = c['pelvis']
        # pelvis shifts over the stance leg; shoulders roll the other way
        sway = SWAY * math.sin(phi + 0.6)
        roll = -ROLL * math.sin(phi + 0.6)
        base = T(ox + sway, oy)
        root = mat_mul(base, mat_mul(T(0, bob), R(roll, px_, py_)))
        head_lag = BOB[(i - 1) % N] - bob
        head = mat_mul(root, mat_mul(T(0, 0.6 * head_lag), R(-0.6 * roll + 1.2 * math.sin(2 * phi), *c['neck'])))
        # arm swing: 'fwd' > 0 = hand toward the camera (drops a pixel, tucks in)
        fwd_l = -math.cos(phi)
        fwd_r = math.cos(phi)
        tuck, drop, deg = ARM_SWING
        arm_l = mat_mul(root, mat_mul(T(tuck * fwd_l, drop * fwd_l), R(-deg * fwd_l, *c['sh_l'])))
        arm_r = mat_mul(root, mat_mul(T(-tuck * fwd_r, drop * fwd_r), R(deg * fwd_r, *c['sh_r']))) if 'sh_r' in c else None
        paul_l = mat_mul(root, T(0, PAUL_DROP * fwd_l))
        paul_r = mat_mul(root, T(0, PAUL_DROP * fwd_r))

        ax0, ay0 = c['cape_anchor']

        def cape_disp(x, y):
            # hangs from the shoulder line: the top edge stays put, the hem moves most
            v = max(0.0, min(1.0, (y - ay0) / c['cape_len']))
            swing_, flutter, lift = CAPE_WAVE
            return (v ** 1.2 * (swing_ * math.sin(phi - 2.4 * v) + flutter * math.sin(2 * phi - 3 * v)),
                    -lift * v ** 1.5 * (1 + math.sin(2 * phi - 3 * v)))

        kx, ky = c['knob']

        def plume_disp(x, y):
            v = max(0.0, min(1.0, math.hypot(x - kx, y - ky) / c['plume_len']))
            swing_, lean, bob_ = PLUME_WAVE
            return (v * (swing_ * math.sin(phi - 2.6 * v) + lean * c['plume_side']),
                    bob_ * v * math.sin(2 * phi - 2.6 * v - 1.0))

        out = A.Frame()
        px = out.px
        # exposed for checks.py: head height and where each boot landed this frame
        self.debug = {'head_y': apply(head, *c['knob'])[1], 'boots': {}, 'lift': {}}
        # filled body underneath everything (only visible where a moving part uncovers it)
        self.L['backing'].render(root, out=px)
        # legs: straight down from the hips; the swinging leg lifts its knee toward the camera
        # (foreshortened, foot rises), the landing foot steps a pixel toward the camera
        order = []
        for name, k in (('leg_l', 0), ('leg_r', 4)):
            lift = LIFT[(i + k) % N]
            fwd = math.cos(phi - k * math.pi / 4 * 1.0) if k == 0 else math.cos(phi - math.pi)
            order.append((fwd, name, lift, (i + k) % N))
        for fwd, name, lift, phase in sorted(order):
            g = c['fleg'][name]
            hip_d = apply(root, g['dest_x'], g['hip'][1])
            # the swinging foot drifts a pixel toward the midline (feet land almost in line)
            inward = -g['side'] * (INWARD if phase in SWING_INWARD else 0)
            base_x = apply(base, g['dest_x'] + inward, 0)[0]
            ank_d = (base_x, g['ankle'][1] + oy + lift)
            self.L[name + '_strip'].render(axis_map(g['hip'], g['ankle'], hip_d, ank_d), out=px)
            boot = self.L[name + '_boot'].render(T(ank_d[0] - g['ankle'][0], ank_d[1] - g['ankle'][1]))
            px.update(boot)
            self.debug['boots'][name] = set(boot)
            self.debug['lift'][name] = lift
        if c['sprite'] == 'back':
            self.L['helmet'].render(mat_mul(head, T(0, 1)), out=px)
            self.L['torso'].render(root, out=px)
            self.L['arm_l'].render(arm_l, out=px)
            self.L['paul_l'].render(paul_l, out=px)
            self.L['cape'].render(root, cape_disp, out=px)
            self.L['helmet'].render(head, out=px)
            self.L['plume'].render(head, plume_disp, out=px)
            reconnect_specks(px)
            close_holes(px, A.FW, A.FH, max_size=8)
            return out
        self.L['cape'].render(root, cape_disp, out=px)
        self.L['plume'].render(head, plume_disp, out=px)
        self.L['torso'].render(root, out=px)
        self.L['arm_r'].render(arm_r, out=px)
        self.L['paul_r'].render(paul_r, out=px)
        # the sword only translates with the hand (whole pixels) so the thin blade keeps
        # exactly the reference pixels
        gx, gy = apply(arm_l, *c['grip'])
        sword = T(round(gx - c['grip'][0]), round(gy - c['grip'][1]))
        self.L['sword'].render(sword, out=px)
        self.L['arm_l'].render(arm_l, out=px)
        self.L['paul_l'].render(paul_l, out=px)
        self.L['helmet'].render(head, out=px)
        reconnect_specks(px)
        close_holes(px, A.FW, A.FH, max_size=8)
        return out
