"""Batch 1 of the player's actions (docs/art-progress.md): idle; guard hold, plain block hit,
perfect deflect and its return; heal; and one set of slow legs (forward, backward, sidestep to
either side) shared by guard-walk and heal-walk (and by charge-walk in batch 3). All on the
56 x 56 canvas, foot anchor (28, 53).

Batch 3 (decision 8, 2026-09-28): backward and the sidestep to the character's right are no
longer the forward / left cycles played in reverse. Played in reverse, the head and the cloth
ends (computed to lag the frame before) would lead by a frame; they are made on their own with
the legs' phase running the other way and the lags recomputed (walk_pose rev=True). The forward
and left frames are unchanged. Decision 1: each frame is held 2 sim frames walking with the guard
(50 px/s), 3 with the heal (30 px/s), so the planted foot does not slide.

Timing is in simulation frames (60 Hz), from scripts/combat/player_data.gd and
scripts/state_machines/player_sim.gd (docs/art-progress.md appendix A); the frame tables
are appendix B, updated with the batch 1 decisions.

Per-part plan (animation-review §4.2). "Breath" = the four-phase breath of decision 4:
phase 1 is the base pose, 2 sinks, 3 is the lowest (head one phase late, cloth ends last),
4 rises.

| part | idle | guard hold | block hit | deflect -> back | heal | slow legs |
|---|---|---|---|---|---|---|
| legs, feet | still (the library's) | braced, still | back foot slides 1.5 px back | front foot rolls to the toe, back | under the hips, still | walk cycle at half stride; sidestep: step out, close |
| pelvis | breath 1 px | breath 1 px | gives 1 px back | settles | breath 1 px | bob 1 px on the loading frames |
| torso | rides the pelvis | leans 4 deg | leans 2 deg (pushed) | opens, leans back 10 deg | hunched, 14 deg (side) / 8 (front), toward the sword 6 deg | the action's own, rigid |
| arms | the library's, ride the body | two-hand grip, elbows out | hands 2 px toward the chest | sword arm flung up and out, off hand opens | right hand on the pommel, left hand on the chest | the action's own, rigid |
| sword | slides in the fist rather than dig in | across the chest | with the hands | out and up, then halfway back | planted at a slant, tip on the floor | the action's own (heal: tip on the floor) |
| head | a phase late | a phase late | left 1 px forward | tips back | bowed; a phase late | a frame late |
| cape, plume, scarf | ends a phase late | ends a phase late | thrown 1 px forward | flung back | ends a phase late | small wave behind the step |

Parts that do not move have a reason: the idle's feet carry the weight; the guard's and the
heal's arms hold their grip through the breath (the whole upper body rides the pelvis, so the
guard reads the same while it breathes and walks)."""
import math

import sprites as A
import walk_side as W
import walk_fb as F
import pose_rig as PR
import poses as PS
from rig import T, reconnect_specks
from pose_rig import bend

VIEWS = ('south', 'east', 'north', 'west')
SPRITE = {'south': 'front', 'east': 'side_right', 'north': 'back', 'west': 'side_left'}
CLOTH = ('plume', 'cape', 'scarf')

# ------------------------------------------------------------------ the breath (decision 4)
# screen px, + = down; phase 1 is the base pose itself
BODY = (0, 1, 1, 0)          # pelvis and everything it carries
HEAD = (0, 0, 1, 1)          # the head follows one phase late
TIP = (0, 0, 1, 1)           # cape / scarf ends swing one phase after their root (the body)
PLUME_TIP = (0, 0, 0, 1)     # the plume's end one phase after its root (the head)
SWING = 1.5                  # px a cloth end moves when it catches up (1 px moved the end's
                             # centre only 0.3-0.4 px: too little to read as following through)


def resolve(pose, view):
    """The pose as this view draws it: per-view overrides (lean_view, arms_view ...) applied
    and dropped, so later edits are not overridden again by the rig."""
    out = {k: v for k, v in pose.items() if not k.endswith('_view')}
    for k in ('lean', 'roll', 'head', 'head_tilt', 'arms'):
        if view in pose.get(k + '_view', {}):
            out[k] = pose[k + '_view'][view]
    if 'sword' in pose:
        sw = dict(pose['sword'])
        sw['dir'] = sw.get('dir_view', {}).get(view, sw['dir'])
        sw.pop('dir_view', None)
        if view in sw.get('depth', {}):
            sw['depth'] = {view: sw['depth'][view]}
        else:
            sw.pop('depth', None)
        out['sword'] = sw
    return out


def _add(v, d):
    return tuple(a + b for a, b in zip(tuple(v) + (0,) * (3 - len(v)), d))


PLUME_AMP = {'north': 0.67}  # the back view's plume is short: 1.5 px swung its end 3 px (target 1-2)


def cloth_swing(view, amount):
    """A cloth end swinging out by `amount` px, as a character-space displacement: back in the
    side views, outward (the cape's own side, toward the character's left) in front / back."""
    if view in ('east', 'west'):
        return (-amount, 0, 0)
    return (0, amount, 0)


def plume_lag(view, amount):
    """The plume's end left behind by `amount` px when its root (the head) moves down: up in
    front / back; back and up in the side views, where the plume stands nearly upright and a
    purely vertical pull hardly turns it."""
    a = amount * PLUME_AMP.get(view, 1.0)
    if view in ('east', 'west'):
        return (-0.7 * a, 0, 0.7 * a)
    return (0, 0, a)


def plant(pose, bob):
    """A sword planted in the floor (the heal) stays put while the body bobs over it."""
    p = dict(pose)
    p['sword'] = dict(p['sword'], planted=(0.0, -float(bob)))
    return p


def breathe(pose, view, i, planted=False):
    """Phase i (0-3) of the breath on a resolved pose."""
    b, h, t, pt = BODY[i], HEAD[i], TIP[i], PLUME_TIP[i]
    p = dict(pose)
    p['root'] = _add(p.get('root', (0, 0, 0)), (0, 0, -b))
    p['head'] = _add(p.get('head', (0, 0, 0)), (0, 0, b - h))
    p['cape'] = _add(p.get('cape', (0, 0, 0)), cloth_swing(view, SWING * t))
    # front / back: the hem's flare would follow the lowered body at once; the swing above
    # moves it a phase later instead
    p['cape_lowered_add'] = p.get('cape_lowered_add', 0.0) - b
    p['plume'] = _add(p.get('plume', (0, 0, 0)), plume_lag(view, SWING * (h - pt)))
    p['scarf'] = _add(p.get('scarf', (0, 0, 0)), (0, 0, b - t))
    return plant(p, b) if planted else p


# ------------------------------------------------------------------ idle: the library itself
class IdleRig:
    """The idle on the library's own parts, moved by whole pixels only (so phase 1 is the
    library sprite, pixel for pixel; decision: pose_rig redraws the arms, so it cannot)."""

    def __init__(self, view):
        self.view = view
        self.side = view in ('east', 'west')
        spr = SPRITE[view]
        cfg = {'south': F.FRONT, 'north': F.BACK, 'east': W.EAST, 'west': W.WEST}[view]
        self.cfg = cfg
        self.rig = W.SideRig(cfg) if self.side else F.FBRig(cfg)
        m = A.META[spr]
        self.ox, self.oy = A.CX - m['cx'], A.GROUND - m['feet']
        L = self.rig.L
        self.tips = {}
        for n, anchor in (('cape', cfg['cape_anchor']), ('plume', cfg['knob'])):
            pts = list(L[n].pix)
            dmax = max(math.hypot(x + .5 - anchor[0], y + .5 - anchor[1]) for x, y in pts)
            far = [(x + .5, y + .5) for x, y in pts if math.hypot(x + .5 - anchor[0], y + .5 - anchor[1]) > 0.7 * dmax]
            self.tips[n] = (sum(p[0] for p in far) / len(far) - anchor[0], sum(p[1] for p in far) / len(far) - anchor[1])
        # the sword's lowest row: a lower hand slides it up in the fist, never into the floor
        self.sword_low = max(y for _, y in L['sword'].pix) + self.oy if 'sword' in L else None

    def frame(self, i):
        b, h, t, pt = BODY[i], HEAD[i], TIP[i], PLUME_TIP[i]
        if i == 0:
            px = dict(A.stand_frame(SPRITE[self.view]).px)
            self.trace = self._trace0()
            self.pieces = self._pieces_by_trace(px)
            self.debug = {'body': 0, 'head': 0}
            return px
        c, L, ox, oy = self.cfg, self.rig.L, self.ox, self.oy
        body, head = T(ox, oy + b), T(ox, oy + h)
        sb = b if self.sword_low is None else min(b, max(0, A.GROUND - self.sword_low))
        sword = T(ox, oy + sb)
        ax0, ay0 = c['cape_anchor']
        clen = c['cape_len']
        if self.side:
            fdir = c['facing']
            cape_disp = bend((ax0, ay0), self.tips['cape'], (-fdir * SWING * t, 0.0), clen)
        else:
            out_ = c['cape_side'] * (1 if self.view == 'south' else -1)
            cape_disp = bend((ax0, ay0), self.tips['cape'], (out_ * SWING * t, 0.0), clen)
        kx, ky = c['knob']
        plen = W.PLUME_WAVE[3] if self.side else c['plume_len']
        lag = plume_lag(self.view, SWING * (h - pt))
        plume_disp = bend((kx, ky), self.tips['plume'],
                          (lag[0] * c.get('facing', 1) if self.side else 0.0, -lag[2]), plen)
        order = []      # (name, layer, world, disp)
        if self.side:
            scx, scy = c['scarf_anchor']

            def scarf_disp(x, y):
                return 0.0, (t - b) * max(0.0, min(1.0, (y - scy) / c['scarf_len']))
            order += [('backing', L['backing'], body, None),
                      ('helmet_under', L['helmet'], T(ox, oy + h + 1), None),
                      ('cape', L['cape'], body, cape_disp)]
            if c['sword_on'] == 'back':
                order.append(('sword', L['sword'], sword, None))
            order.append(('legs', None, None, None))
            order.append(('torso', L['torso'], body, None))
            if c['sword_on'] == 'arm':
                order.append(('sword', L['sword'], sword, None))
            order += [('scarf', L['scarf'], body, scarf_disp), ('arm', L['arm'], body, None),
                      ('pauldron', L['pauldron'], body, None), ('plume', L['plume'], head, plume_disp),
                      ('helmet', L['helmet'], head, None)]
        elif self.view == 'south':
            order += [('backing', L['backing'], body, None), ('legs', None, None, None),
                      ('cape', L['cape'], body, cape_disp), ('plume', L['plume'], head, plume_disp),
                      ('torso', L['torso'], body, None), ('arm_r', L['arm_r'], body, None),
                      ('paul_r', L['paul_r'], body, None), ('sword', L['sword'], sword, None),
                      ('arm_l', L['arm_l'], body, None), ('paul_l', L['paul_l'], body, None),
                      ('helmet', L['helmet'], head, None)]
        else:
            order += [('backing', L['backing'], body, None), ('legs', None, None, None),
                      ('helmet_under', L['helmet'], T(ox, oy + h + 1), None),
                      ('torso', L['torso'], body, None), ('arm_l', L['arm_l'], body, None),
                      ('paul_l', L['paul_l'], body, None), ('cape', L['cape'], body, cape_disp),
                      ('helmet', L['helmet'], head, None), ('plume', L['plume'], head, plume_disp)]
        px, trace, pieces, raw = {}, {}, {}, {}
        for name, layer, world, disp in order:
            if name == 'legs':
                tmp = self._legs()
            else:
                tmp = layer.render(world, disp)
            raw[name] = dict(tmp)
            if name in CLOTH:
                # a cloth end that the breath swings past the floor rests on it
                for k in [k for k in tmp if k[1] > A.GROUND]:
                    col = tmp.pop(k)
                    tmp.setdefault((k[0], A.GROUND), col)
            px.update(tmp)
            pieces.setdefault(name, {}).update(tmp)
            for k in tmp:
                trace[k] = name
        reconnect_specks(px)
        self._close_new_holes(px, b, h)
        self.trace, self.pieces, self.pieces_raw = trace, pieces, raw
        self.debug = {'body': b, 'head': h}
        return px

    def _close_new_holes(self, px, b, h):
        """Moving parts a pixel apart open seams and pockets the library does not have (at
        the cape's tatters, where the head meets the body). Fill only those: the library's own
        pockets (idle frame 1) are kept wherever they moved with the body or the head, or the
        frames would flicker against frame 1."""
        if not hasattr(self, '_holes0'):
            # each library pocket moves with the part around it (head, body or legs)
            tr = self._trace0()
            self._holes0 = []
            for (x, y) in _enclosed(A.stand_frame(SPRITE[self.view]).px):
                near = [tr.get(q) for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if tr.get(q)]
                grp = 'head' if any(n in ('helmet', 'plume') for n in near) else \
                    'legs' if near and all(n == 'legs' for n in near) else 'body'
                self._holes0.append(((x, y), grp))
            lib = A.stand_frame(SPRITE[self.view]).px
            self._pins0 = {q for q, _ in self._holes0 if _pinhole(lib, q)}
        off = {'head': h, 'body': b, 'legs': 0}
        keep = {(x, y + off[g]) for (x, y), g in self._holes0}
        # a library pocket squeezed to a single pixel by the part moving over it reads as a
        # new pinhole: only the library's own pinholes stay pinholes
        pins0 = {(x, y + off[g]) for (x, y), g in self._holes0 if (x, y) in self._pins0}
        new = [q for q in _enclosed(px) if q not in keep or (_pinhole(px, q) and q not in pins0)]
        todo = set(new)
        while todo:
            done = []
            for (x, y) in sorted(todo):
                for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if q in px:
                        px[(x, y)] = px[q]
                        done.append((x, y))
                        break
            if not done:
                break
            todo -= set(done)
        # filling can leave a kept pocket down to one pixel: close those too
        for q in [q for q in _enclosed(px) if _pinhole(px, q) and q not in pins0]:
            px[q] = px[(q[0] - 1, q[1])]

    def _legs(self):
        ox, oy = self.ox, self.oy
        if self.side:
            return {(x + ox, y + oy): col for (x, y), col in self.rig.parts['legs'].items()}
        out = {}
        for n in ('leg_l', 'leg_r'):
            out.update({(x + ox, y + oy): col for (x, y), col in self.rig.L[n].pix.items()})
        return out

    def _trace0(self):
        tr = {}
        L = self.rig.L
        for n, layer in L.items():
            if n in ('backing',) or n.endswith('_strip') or n.endswith('_boot'):
                continue
            for (x, y) in layer.pix:
                tr[(x + self.ox, y + self.oy)] = 'legs' if n in ('leg_l', 'leg_r') else n
        for k in self._legs():
            tr[k] = 'legs'
        return tr

    def _pieces_by_trace(self, px):
        out = {}
        for k, n in self.trace.items():
            if k in px:
                out.setdefault(n, {})[k] = px[k]
        self.pieces_raw = out
        return out


def _pinhole(px, q):
    x, y = q
    return q not in px and all(n in px for n in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))


def _enclosed(px):
    """Transparent pixels of the frame that cannot be reached from outside it."""
    opaque = set(px)
    outside = set()
    stack = [(x, y) for x in range(-1, A.FW + 1) for y in (-1, A.FH)] + \
            [(x, y) for y in range(-1, A.FH + 1) for x in (-1, A.FW)]
    while stack:
        q = stack.pop()
        if q in outside or q in opaque or not (-1 <= q[0] <= A.FW and -1 <= q[1] <= A.FH):
            continue
        outside.add(q)
        stack += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
    return {(x, y) for x in range(A.FW) for y in range(A.FH) if (x, y) not in opaque and (x, y) not in outside}


_IDLE = {}


def idle_rig(view):
    if view not in _IDLE:
        _IDLE[view] = IdleRig(view)
    return _IDLE[view]


# ------------------------------------------------------------------ in-betweens
def _chest_positions(pose, view):
    """Each hand of a resolved pose as a chest-space point in this view (the second hand on
    the grip is placed from the blade, as the rig does)."""
    arms = pose.get('arms', {})
    out = {}
    blade = PR.vnorm(pose['sword']['dir']) if 'sword' in pose else None
    for s_ in ('R', 'L'):
        spec = arms.get(s_)
        if spec is None or 'on_grip' in spec:
            continue
        out[s_] = PR.vadd(PR.hand_rel(view, s_, spec), PR.chest_sh(view, s_))
    for s_ in ('R', 'L'):
        spec = arms.get(s_)
        if spec is not None and 'on_grip' in spec:
            out[s_] = PR.vsub(out['R'], PR.vscale(blade, spec['on_grip']))
    return out


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def lerp_pose(a, b, t, view):
    """In-between of two resolved poses for one view: body and cloth numbers, hands (as chest
    points), elbow hints and the blade direction are interpolated; discrete choices (foot
    state, draw-order overrides) come from the nearer pose."""
    near = a if t < 0.5 else b
    p = {}
    for k in ('root', 'head', 'cape', 'plume', 'scarf'):
        p[k] = _lerp(a.get(k, (0, 0, 0)), b.get(k, (0, 0, 0)), t)
    for k in ('lean', 'roll', 'head_tilt', 'cape_lowered_add'):
        p[k] = a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * t
    fa, fb = a.get('feet', {}), b.get('feet', {})
    p['feet'] = {}
    for s_ in ('R', 'L'):
        x, y = fa.get(s_, (0, 0, 0, 'flat')), fb.get(s_, (0, 0, 0, 'flat'))
        p['feet'][s_] = _lerp(x[:3], y[:3], t) + ((near['feet'][s_][3] if s_ in near.get('feet', {}) and len(near['feet'][s_]) > 3 else 'flat'),)
    ca, cb = _chest_positions(a, view), _chest_positions(b, view)
    p['arms'] = {}
    for s_ in ('R', 'L'):
        sa, sb = a['arms'][s_], b['arms'][s_]
        spec = {'at': _lerp(ca[s_], cb[s_], t),
                'elbow': _lerp(sa.get('elbow', (0, 0, -1)), sb.get('elbow', (0, 0, -1)), t)}
        for k in ('depth_fore', 'depth_fist', 'depth_upper'):
            if near['arms'][s_].get(k) is not None:
                spec[k] = near['arms'][s_][k]
        p['arms'][s_] = spec
    da, db = PR.vnorm(a['sword']['dir']), PR.vnorm(b['sword']['dir'])
    sw = {'hand': 'R', 'dir': PR.vnorm(_lerp(da, db, t)),
          'grip_back': a['sword'].get('grip_back', 2.0) + (b['sword'].get('grip_back', 2.0) - a['sword'].get('grip_back', 2.0)) * t}
    p['sword'] = sw
    return p


# a relaxed stance in pose_rig terms (both hands hanging at the sides, the sword hanging
# forward-down as the library holds it): the other end of the heal's in / out in-betweens
# the blade points where the library's does in each view (west: hanging behind, the far hand
# holding it; south: down and out to the right hand's side)
_REST_L = PS.hand('L', 0, 12, -10, elbow=(0, 1, 0))
REST = dict(root=(0, 0, 0), lean=0, feet={'R': (0, 0, 0, 'flat'), 'L': (0, 0, 0, 'flat')},
            arms={'R': PS.hand('R', 1, -14, -10, elbow=(0, -1, 0)), 'L': _REST_L},
            arms_view={'west': {'R': PS.hand('R', -2, -12, -10, elbow=(0, -1, 0)), 'L': _REST_L}},
            sword=dict(hand='R', dir=(0.82, -0.1, -0.57),
                       dir_view={'west': (-0.7, -0.1, -0.7), 'south': (0.0, -0.68, -0.73), 'north': (0.0, -0.3, -0.95)}),
            cape=(0, 0, 0), plume=(0, 0, 0))


# ------------------------------------------------------------------ the slow legs (decision 5)
# forward: the walk's own foot cycle at half stride (walk_side.NEAR_FOOT, walk_fb.LIFT), the
# walk's cadence; 1.0 / 0.8 / 0.6x playback for 50 / 40 / 30 px/s (guard / charge / heal).
# backward: the same frames in reverse. sidestep: 4 frames, step out and close.
N_FWD = 8
N_SIDE = 4
SIDE_C0 = 0.4                  # centre of the walk's side-view foot travel (+6.4 .. -5.6)
STRIDE = 0.5
SLOW_LIFT = (1, 0, 0, 0, 0, -1, -2, -1)     # walk_fb.LIFT (1 0 0 0 -1 -2 -3 -2) at half stride, whole px
WALK_BOB = (0, 1, 1, 0, 0, 1, 1, 0)         # 1 px (the walk's is 2 px peak to peak)
# sidestep toward the character's left (the other way = played in reverse): front / back
# views step the left foot out and close the right; side views, where depth has no screen
# height, lift the feet in turn
SIDE_FB = [  # (L lateral px, L lift, R lateral px, R lift)
    (0, 0, 0, 0), (3, 2, 0, 0), (2, 0, -2, 0), (0, 0, -1, 2)]
SIDE_BOB = (0, 0, 1, 0)
SIDE_SIDE = [(0, 0), (2, 0), (0, 0), (0, 2)]  # (near lift, far lift)
# no bob here: two beats in four frames with the head a frame late would jerk the head against
# the body every frame; the body is carried across the screen by the game
SIDE_SIDE_BOB = (0, 0, 0, 0)


def _fb_foot(view, s_, lateral, lift_px):
    """(f, l, lift) for pose_rig._fb_leg from a lateral screen move toward the character's
    left and a vertical offset (+ = toward the camera, - = lifted)."""
    kf = PR.KD_FEET if view == 'south' else -PR.KD_FEET
    f_ = lift_px / kf if lift_px > 0 else 0.0
    lift = -lift_px if lift_px < 0 else 0
    return (f_, lateral / PR.FEET_W[view], lift, 'flat')


def slow_feet(view, kind, i, stance, lag=1, tables=None):
    """Feet, pelvis bob and the bob of the frame shown before (lag = 1: frame i - 1; -1, the
    cycle run backward: frame i + 1) for frame i of the slow legs. tables: the sidestep's own
    (side_fb, side_side) in place of SIDE_FB / SIDE_SIDE (batch 3: the locked walk steps wider). The cycle
    (phase, half stride, lifts) is the same for every action; it swings about the action's own
    stance (`stance` = its pose's feet): the guard keeps its braced, wide feet while it walks,
    the heal its feet under the hips, so starting and stopping never jump the feet."""
    v = PR.VIEWS[view]
    side = v['kind'] == 'side'
    st = {s_: tuple(stance.get(s_, (0, 0, 0, 'flat'))) for s_ in ('R', 'L')}
    near = v.get('near')
    far = ('L' if near == 'R' else 'R') if near else None
    if kind == 'fwd':
        bob, prev = WALK_BOB[i], WALK_BOB[(i - lag) % N_FWD]
        feet = {}
        if side:
            for s_, k in ((near, i), (far, (i + 4) % N_FWD)):
                dx, lift, state = W.NEAR_FOOT[k]
                feet[s_] = (st[s_][0] + STRIDE * (dx - SIDE_C0), st[s_][1], STRIDE * lift, state)
            return feet, bob, prev
        for s_ in ('R', 'L'):
            k = 0 if v['leg'][s_] == 'leg_l' else 4
            ph = (i + k) % N_FWD
            inward = (1 if s_ == 'R' else -1) * (F.INWARD if ph in F.SWING_INWARD else 0)
            f_, l_, lift, _ = _fb_foot(view, s_, inward, SLOW_LIFT[ph])
            feet[s_] = (st[s_][0] + f_, st[s_][1] + l_, lift, 'flat')
        return feet, bob, prev
    bob, prev = (SIDE_SIDE_BOB if side else SIDE_BOB)[i], (SIDE_SIDE_BOB if side else SIDE_BOB)[(i - lag) % N_SIDE]
    side_fb, side_side = tables or (SIDE_FB, SIDE_SIDE)
    if side:
        nl, fl = side_side[i]
        feet = {near: (st[near][0], st[near][1], nl, 'swing' if nl else 'flat'),
                far: (st[far][0], st[far][1], fl, 'swing' if fl else 'flat')}
        return feet, bob, prev
    ll, lu, rl, ru = side_fb[i]
    feet = {}
    for s_, lat, up_ in (('L', ll, lu), ('R', rl, ru)):
        f_, l_, lift, _ = _fb_foot(view, s_, lat, -up_)
        feet[s_] = (st[s_][0] + f_, st[s_][1] + l_, lift, 'flat')
    return feet, bob, prev


def walk_pose(upper, view, kind, i, planted=False, rev=False, sway=0.8, tables=None):
    """The action's upper body (a resolved pose) on the slow legs: the upper body rides the
    pelvis rigidly (decision: 1 px bob only), the head a frame late, the cloth ends in a small
    wave behind the step. rev: frame i of the cycle run the other way (backward, or the
    sidestep to the character's right): the legs at phase -i, the lags recomputed so the head
    and the cloth still follow in the order the frames are shown (batch 3 decision 8)."""
    n = N_FWD if kind == 'fwd' else N_SIDE
    lag = -1 if rev else 1
    i = (-i) % n if rev else i
    feet, bob, prev = slow_feet(view, kind, i, upper.get('feet', {}), lag, tables)
    phi = 2 * math.pi * i / n
    p = dict(upper)
    p['feet'] = feet
    p['root'] = _add(p.get('root', (0, 0, 0)), (0, 0, -bob))
    p['head'] = _add(p.get('head', (0, 0, 0)), (0, 0, bob - prev))
    if view in ('east', 'west'):
        p['cape'] = _add(p.get('cape', (0, 0, 0)), (-sway * math.sin(2 * phi - lag * 1.2), 0, 0))
        p['plume'] = _add(p.get('plume', (0, 0, 0)), (0, 0, sway * math.sin(2 * phi - lag * 2.0)))
    else:
        p['cape'] = _add(p.get('cape', (0, 0, 0)), (0, sway * math.sin(phi - lag * 1.0), 0))
        p['cape_lowered_add'] = p.get('cape_lowered_add', 0.0) + (prev - bob)
        p['plume'] = _add(p.get('plume', (0, 0, 0)), (0, sway * math.sin(phi - lag * 1.6), 0))
    return plant(p, bob) if planted else p


# ------------------------------------------------------------------ the actions
def slow_walk(upper, hold, planted=False, sway=0.8):
    """The slow legs' columns under an action's upper body: forward 1-8, sidestep to the
    character's left 1-4, backward 1-8, sidestep to the right 1-4 (batch 3 decision 8: the
    last two are made on their own, not played in reverse). hold = sim frames a frame shows
    (batch 3 decision 1: the planted foot does not slide at the action's speed); a tuple is a
    pattern the frames take in turn (the charge's 2, 2, 2, 3 averages 2.25). sway = the cloth
    ends' wave, px (the charge's low stance already flares the cape: batch 3 uses less)."""
    holds = hold if isinstance(hold, tuple) else (hold,)
    out = []
    for kind, n, name, rev in (('fwd', N_FWD, 'fwd', False), ('side', N_SIDE, 'side', False),
                               ('fwd', N_FWD, 'back', True), ('side', N_SIDE, 'rside', True)):
        out += [(f'{name} {i + 1}', holds[i % len(holds)], (lambda v, i=i, kind=kind, rev=rev:
                                                           walk_pose(upper(v), v, kind, i, planted, rev, sway))) for i in range(n)]
    return out


# (frame name, sim frames it shows, builder(view) -> resolved pose, or ('idle', phase))
def _guard(view):
    return resolve(PS.GUARD, view)


def _heal(view):
    return resolve(PS.HEAL, view)


def heal_in(view, t, th):
    """0-7 in two frames: the body t of the way into the heal, the head's bow only th of the
    way (it follows the body)."""
    rest, heal = resolve(REST, view), _heal(view)
    p = lerp_pose(rest, heal, t, view)
    p['head_tilt'] = heal.get('head_tilt', 0.0) * th
    p['head'] = _lerp((0, 0, 0), heal.get('head', (0, 0, 0)), th)
    # the plume's counter-swing belongs to the bow: it goes as far as the head has
    p['plume'] = _lerp((0, 0, 0), heal.get('plume', (0, 0, 0)), th)
    return p


def heal_out(view, t, th):
    """62-69 in two frames: the body t of the way back, the head th of the way (it leads the
    way out, looking up)."""
    rest, heal = resolve(REST, view), _heal(view)
    p = lerp_pose(heal, rest, t, view)
    p['head_tilt'] = heal.get('head_tilt', 0.0) * (1 - th)
    p['head'] = _lerp(heal.get('head', (0, 0, 0)), (0, 0, 0), th)
    p['plume'] = _lerp(heal.get('plume', (0, 0, 0)), (0, 0, 0), th)
    return p


def deflect_back(view, t):
    """The 4 frames back from the deflect to the guard, as two in-betweens (t = 1/3, 2/3):
    decision 2 keeps the frame-to-frame limits on the way back, and the front view's point
    travels 44 px (halfway would still be 22 > 20)."""
    p = lerp_pose(resolve(PS.PARRY, view), _guard(view), t, view)
    # the blade comes back round the outside (forward, on the sword side), not across the
    # face: over the lit visor it lost its contrast (animation-review §4.5)
    k = math.sin(math.pi * t)
    p['sword']['dir'] = PR.vnorm(tuple(a + k * b for a, b in zip(p['sword']['dir'], BACK_ARC)))
    return p


# in-between ratios, chosen so every part stays within the frame-to-frame limits in all four
# views (searched; checks.py --batch1 prints the moves): the deflect's point travels up to 44 px
BACK_T = (0.4, 0.65)
BACK_ARC = (0.5, -0.6, 0.0)                   # the returning blade's outward bow (character space)
IN_T = ((0.3, 0.2), (0.65, 0.5))              # (body, head): the head bows after the body
OUT_T = ((0.3, 0.45), (0.7, 0.85))            # the head comes up first

ACTIONS = {
    'idle': [(f'idle {i + 1}', 12, ('idle', i)) for i in range(4)],
    'guard': [(f'hold {i + 1}', 12, (lambda v, i=i: breathe(_guard(v), v, i))) for i in range(4)] + [
        ('hit', 6, lambda v: resolve(PS.GUARD_HIT, v)),
        ('deflect', 11, lambda v: resolve(PS.PARRY, v)),        # hitstop 5 + 6
        ('back 1', 2, lambda v: deflect_back(v, BACK_T[0])), ('back 2', 2, lambda v: deflect_back(v, BACK_T[1]))],
    'heal': [('in 1', 4, lambda v: heal_in(v, *IN_T[0])), ('in 2', 4, lambda v: heal_in(v, *IN_T[1]))] +
            [(f'hold {i + 1}', d, (lambda v, i=i: breathe(_heal(v), v, i, planted=True)))
             for i, d in enumerate((13, 14, 13, 14))] +
            [('out 1', 4, lambda v: heal_out(v, *OUT_T[0])), ('out 2', 4, lambda v: heal_out(v, *OUT_T[1]))],
    'guard_walk': slow_walk(_guard, 2),
    'heal_walk': slow_walk(_heal, 3, planted=True),
}
TITLES = {'idle': '待機', 'guard': '格擋（保持、受力、彈返、收回）', 'heal': '治療',
          'guard_walk': '格擋移動（前進 1–8、往左側移 1–4、後退 1–8、往右側移 1–4）',
          'heal_walk': '治療移動（前進 1–8、往左側移 1–4、後退 1–8、往右側移 1–4）'}


class Frame:
    """One rendered frame and what the checks need about it."""

    def __init__(self, action, name, dur, view, px, trace, pieces, pieces_raw, debug, pose):
        self.action, self.name, self.dur, self.view = action, name, dur, view
        self.px, self.trace, self.pieces, self.pieces_raw, self.debug, self.pose = px, trace, pieces, pieces_raw, debug, pose


_CACHE = {}


def frames(action, view):
    key = (action, view)
    if key in _CACHE:
        return _CACHE[key]
    out = []
    for name, dur, build in ACTIONS[action]:
        if isinstance(build, tuple):
            r = idle_rig(view)
            px = r.frame(build[1])
            out.append(Frame(action, name, dur, view, px, dict(r.trace), r.pieces, r.pieces_raw, dict(r.debug), None))
            continue
        pose = build(view)
        r = PR.rig(view)
        px = r.frame(pose, 'small')
        dbg = dict(r.debug)
        dbg['legs'] = dict(r.debug.get('legs', {}))
        dbg['hands'] = dict(r.debug.get('hands', {}))
        dbg['blade'] = set(r.debug.get('blade', set()))
        out.append(Frame(action, name, dur, view, px, dict(r.trace),
                         {k: dict(v) for k, v in r.pieces.items()},
                         {k: dict(v) for k, v in r.pieces_raw.items()}, dbg, pose))
    _CACHE[key] = out
    return out
