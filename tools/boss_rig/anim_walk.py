"""Boss walk, dragging the greatsword (走路：緩步逼近；快步＝同一組每張停 2 幀), and the clips
that join it to the standing pose: walk_start (站姿 → 走路) and walk_stop (走路 → 站姿).

User 2026-09-30: drag the sword (its perspective right in all four directions), lean forward
(the weight ahead of the feet), and animate going into and out of the walk.

Clips (every pose is held gait.HOLD = 4 combat frames at 60 px/s, 2 at 120 px/s):
  walk        20 poses, loops. Legs from gait.py (one model for all directions): the planted
              foot moves back 4 px per pose, exactly what the game moves the Boss.
  walk_start  START_N = 10 poses from the standing pose: a half step (4 poses, the game moves
              him 16 px) then the loop's poses 0-5, while the sword comes down from the
              planted pose to the drag and the body leans in. The loop goes on at START_JOIN.
  walk_stop   STOP_N = 8 poses back to the standing pose, from the loop's poses STOP_FROM
              (0, 5, 10, 15: each heel strike and each mid-stance): the feet are gathered
              under the hips one after the other, the body straightens, the sword is pulled
              up and planted. The Boss does not move during it (the game stops him at once).
Frame: 256 x 272, foot anchor (128, 208) - 48 rows more below the feet than the idle's frame,
for the back view's sword (it trails towards the camera, below the foot line).

Part by part (animation-review §4.2), side view; front and back read the same numbers through
the 0.35 depth foreshortening:
  legs     - heel strike, flat, toe-off, swing (gait.py); side view: posed from the concept
             (limb.py), the far leg darker and 2 px up; front/back: the approved leg pixels,
             rows dropped or duplicated between hip, knee and ankle, feet brought in under
             the hips (FEET_IN) - the standing pose's wide stance is for standing (§4.3)
  hips     - 1-4 px below standing height: lowest with both feet down, highest over the
             planted foot; front/back: sway 2 px towards the planted foot
  chest    - leans forward LEAN_DEG degrees about the hips (side view: every row above the
             belt is shifted forward in proportion to its height, the head about 8 px; front:
             the chest and head sit LEAN_ROWS px lower, back: higher - a lean towards / away
             from the camera) and counter-turns against the legs by 1 px
  head     - follows the chest one pose late
  sword    - dragged behind on the right (drag.py: one 3D pose projected into each view); the
             tip stays on the ground, the fist rides on the body one pose late. In the loop
             the sword is rendered once per view and only sheared in whole pixels (tip fixed,
             fist moved), so its texture does not shimmer
  sword arm - hangs from the shoulder, the fist at its end in line with the forearm, the sword
             passing through the fist (drag.clean_sword: the sword without the standing pose's
             fist). Side: upper arm, forearm and fist posed on joints (arm.py), in the
             transitions by IK from the shoulder to the hand; front: the other arm's pixels
             mirrored; back: the concept's own hanging arm (which the standing pose hides)
             with a fist seen from the thumb's side - the thumb is towards the blade, which
             trails behind (user 2026-09-30)
  free arm - front/back: swings against its own leg (the fist rises and falls 3 px); facing
             left it is the near arm (arm.py), swinging SWING_SIDE px about the shoulder
  facing left - not facing right mirrored: the sword is in the right hand, on the far side
             (side.py). The sword is drawn behind the body and cape, its hand hidden by the
             torso, its tip further from the camera than the hand (higher on screen)
  cape     - top on the shoulders; squashed rather than lowered when the hips drop; side:
             trails behind and flutters once per step; front/back: sways after the hips
  tabard, chain, side cloth - hang from the belt, swing later than the hips
"""
import math
from PIL import Image, ImageDraw
import boss as B
import rig
import labels
import gait
import limb
import anim_idle
import drag

N = gait.POSES
HOLD = gait.HOLD
FW, FH = rig.FW, 272
START_N = 10
START_HALF = 4           # poses of the half step before the loop's poses begin
START_JOIN = START_N - START_HALF      # the loop goes on at this pose after walk_start
STOP_N = 8
STOP_FROM = (0, 5, 10, 15)
LEAN_DEG = 6.0
LEAN_ROWS = 3
FEET_IN = 4              # front/back: each foot this much closer to the centre line than standing
ARM_SWING = 8.0          # how far the free fist swings forward and back (x DEPTH on screen)
FAR_UP = 2               # the side view's far leg is drawn this much higher (it is further away)
DEPTH = drag.DEPTH
DREF = 2                 # the loop's sword and arm are rendered with the hips this far down
SWORD_BEHIND = 0.4       # front/back: the sword changes sides of the body at this blend
DRAG_ARM = (6.0, 12.0)   # side view, the dragging arm: upper arm, forearm degrees back from straight down
ELBOW0 = (158, 215)      # side view, local px: the elbow of the approved standing pose (at the chest)
SWING_SIDE = 5           # facing left: px the free fist swings forward and back
FAR_BARE = 0.35          # facing left: from this blend on the far hand is behind the torso (bare sword)


def _frac(v, a, b):
    return min(1.0, max(0.0, (v - a) / (b - a))) if b != a else (1.0 if v >= b else 0.0)


def piecewise(y, src, tgt):
    """Row map: source row for target row y, given matching landmark rows (both increasing);
    rigid outside the landmarks."""
    if y <= tgt[0]:
        return y - (tgt[0] - src[0])
    for k in range(len(tgt) - 1):
        if y <= tgt[k + 1]:
            if tgt[k + 1] == tgt[k]:
                return src[k + 1]
            return src[k] + (y - tgt[k]) * (src[k + 1] - src[k]) / (tgt[k + 1] - tgt[k])
    return y - (tgt[-1] - src[-1])


# ------------------------------------------------------------------ what each pose is made of
# The four ways the Boss moves (boss_sim.gd walks him at 60 px/s in all of them):
#   walk      forward (approach)
#   back      backwards, still facing the player (retreat while the player is down)
#   strafe_r  sideways towards his own right, facing the player (the breather's circling)
#   strafe_l  sideways towards his own left
# They share the dragged sword and the arm that holds it, so the game can switch between them
# without the sword jumping; they differ in the legs, the lean and the cape.
KINDS = ('walk', 'back', 'strafe_r', 'strafe_l')
LEAN_OF = {'walk': 1.0, 'back': 0.0, 'strafe_r': 0.5, 'strafe_l': 0.5}    # share of LEAN_DEG
TRAIL_OF = {'walk': 1.0, 'back': -0.4, 'strafe_r': 0.0, 'strafe_l': 0.0}  # side view: how far the cape trails behind
HIP_HALF = 17.0          # front/back: each hip joint this far from the centre line
STRAFE_IN = 11           # back view: the boots stand 30 px out; in the sidestep they are under the hips (19)
CROSS = 8.0              # strafing: the trailing foot swings this far forward, around the other leg
LIFT_STRAFE = 6.0        # strafing: how high the swinging foot is lifted


def _walk_state(p):
    s = math.sin(2 * math.pi * (p - 0.05))
    return {'D': round(gait.drop(p)), 'tw': -round(math.cos(2 * math.pi * p)), 'sw': round(2 * s),
            'sw1': round(s), 'legR': gait.leg(p), 'legL': gait.leg(p, True), 'inR': FEET_IN,
            'inL': FEET_IN, 'arm': math.cos(2 * math.pi * p), 'p': p}


def strafe_foot(phi, trailing):
    """One foot of the sidestep at phase phi (0 = it lands): (sideways position along the
    travel direction relative to its hip, forward offset, height of the ankle, on the ground).
    The same numbers as the walk (gait.STRIDE a cycle, gait.STANCE on the ground), so the
    planted foot moves back exactly what the game moves the Boss. The trailing foot (the one
    on the far side from where he is going) swings forward around the other leg and lands
    across it; the leading foot steps straight out."""
    phi %= 1.0
    if phi < gait.STANCE:
        return gait.REACH - gait.STRIDE * phi, 0.0, gait.ANKLE_H, True
    v = (phi - gait.STANCE) / (1 - gait.STANCE)
    x = -gait.REACH + 2 * gait.REACH * gait.smooth(v)
    arc = math.sin(math.pi * v)
    return x, (CROSS * arc if trailing else 0.0), gait.ANKLE_H + LIFT_STRAFE * arc, False


def _strafe_leg(phi, trailing, side, hip):
    """A leg state of the sidestep. side +1: towards his right. 'lat' is the foot's sideways
    offset (his right +) from where it stands."""
    x, fwd, z, down = strafe_foot(phi, trailing)
    L = gait.solve(hip, (fwd, z), 0.0, down)
    L['lat'] = side * x
    L['phi'] = phi % 1.0
    return L


def loop_state(i, kind='walk'):
    p = gait.phase(i % N)
    if kind == 'walk':
        s = _walk_state(p)
    elif kind == 'back':
        # the walk run backwards: each foot reaches back, lands toe first and leaves heel
        # last; the parts that follow late still follow what was shown before (the clip's
        # order), so nothing leads
        s = _walk_state((1.0 - p) % 1.0)
    else:
        side = 1 if kind == 'strafe_r' else -1
        hip = gait.hip_z(p)
        lead, trail = _strafe_leg(p, False, side, hip), _strafe_leg(p + 0.5, True, side, hip)
        s = {'D': round(gait.drop(p)), 'tw': 0, 'sw': 0, 'sw1': 0, 'inR': STRAFE_IN, 'inL': STRAFE_IN, 'arm': 0.0,
             'p': p, 'legR': lead if side > 0 else trail, 'legL': trail if side > 0 else lead}
    s.update(b=1.0, amp=1.0, kind=kind, lean=LEAN_OF[kind])
    return s


STAND = {'D': 0, 'tw': 0, 'sw': 0, 'sw1': 0, 'b': 0.0, 'legR': gait.standing_leg(), 'legL': gait.standing_leg(),
         'inR': 0, 'inL': 0, 'arm': 0.0, 'p': 0.0, 'amp': 0.0, 'kind': 'walk', 'lean': 1.0}


class Clip:
    """Poses in order; at(i) with i < 0 gives what was shown before the clip (the parts that
    follow late read it)."""

    def __init__(self, name, states, before):
        self.name, self.states, self.before = name, states, before

    def at(self, i):
        return self.states[i] if i >= 0 else self.before(-i - 1)

    def __len__(self):
        return len(self.states)


def walk_clip(kind='walk'):
    return Clip(kind, [loop_state(i, kind) for i in range(N)], lambda k: loop_state(N - 1 - k, kind))


# Where the loop goes on after <kind>_start: the start clips end with six of the loop's own
# poses (START_FIRST .. START_FIRST + 5), so the loop continues at START_JOIN.
START_FIRST = {'walk': 0, 'back': 8, 'strafe_r': 0, 'strafe_l': 0}
START_JOINS = {k: (v + START_N - START_HALF) % N for k, v in START_FIRST.items()}


def start_clip(kind='walk'):
    """Standing -> moving. Poses 0-3: one foot takes a half step while the other stays planted
    (the game already carries the body 4 px a pose past it); then six of the loop's poses.
      walk    the right foot steps forward, the loop's poses 0-5 follow
      back    the right foot reaches back and lands toe first where the backward loop's pose 8
              has it (24 px behind), poses 8-13 follow
      strafe  the foot on the side he is going to steps out, poses 0-5 follow"""
    # the stepping foot over the four poses: (distance along the travel direction, lift), pitch
    swing = {'walk': [((1.0, 2.0), -6.0), ((6.0, 5.0), -4.0), ((13.0, 5.0), 2.0), ((19.0, 2.5), 8.0)],
             'back': [((-2.0, 2.0), -6.0), ((-7.0, 5.0), -12.0), ((-12.0, 5.0), -18.0), ((-15.5, 3.5), -23.0)],
             'strafe': [((2.0, 2.5), 0.0), ((8.0, 5.0), 0.0), ((15.0, 5.0), 0.0), ((21.0, 2.0), 0.0)]}
    move = -1 if kind == 'back' else 1                   # the planted foot drifts against the travel
    states = []
    for k in range(START_N):
        b = gait.smooth((k + 1) / START_N)
        if k < START_HALF:
            D = k + 1
            hip = gait.HIP_REST - D
            u = gait.smooth((k + 1) / START_HALF)
            if kind in ('walk', 'back'):
                (sx, sz), pitch = swing[kind][k]
                s = {'D': D, 'tw': -round(u) * move, 'sw': -1 if k else 0, 'sw1': 0,
                     'legR': gait.solve(hip, (sx, gait.ANKLE_H + sz), pitch, False),
                     'legL': gait.solve(hip, (-4.0 * k * move, gait.ANKLE_H), 0.0),
                     'inR': k + 1, 'inL': k + 1, 'arm': u * move, 'p': (k - START_HALF) / N}
            else:
                side = 1 if kind == 'strafe_r' else -1
                (sx, sz), _ = swing['strafe'][k]
                lead = gait.solve(hip, (0.0, gait.ANKLE_H + sz), 0.0, False)
                lead['lat'] = side * sx
                trail = gait.solve(hip, (0.0, gait.ANKLE_H), 0.0)
                trail['lat'] = side * -4.0 * k
                inward = round(STRAFE_IN * (k + 1) / START_HALF)
                s = {'D': D, 'tw': 0, 'sw': 0, 'sw1': 0, 'inR': inward, 'inL': inward, 'arm': 0.0,
                     'p': (k - START_HALF) / N, 'legR': lead if side > 0 else trail, 'legL': trail if side > 0 else lead}
            s.update(kind=kind, lean=LEAN_OF[kind])
        else:
            s = dict(loop_state(START_FIRST[kind] + k - START_HALF, kind))
        s['b'] = s['amp'] = b
        states.append(s)
    return Clip(f'{kind}_start', states, lambda k: STAND)


def stop_clip(entry, kind='walk'):
    """Moving -> standing from loop pose `entry`: the foot that is in the air (or the one
    furthest from under the hips) is set down under the hips first, then the other is brought
    back; hips rise, the body straightens, the sword is pulled up and planted."""
    s0 = loop_state(entry, kind)
    legs = {'R': s0['legR'], 'L': s0['legL']}
    away = lambda k: abs(legs[k]['ankle'][0]) + abs(legs[k].get('lat', 0.0))
    air = [k for k in 'RL' if not legs[k]['down']]
    if air:
        first = air[0]
    elif kind == 'walk':
        first = min('RL', key=lambda k: legs[k]['ankle'][0])        # the rear foot
    else:
        first = max('RL', key=away)
    states = []
    for j in range(STOP_N):
        u = {first: gait.smooth(min(1.0, (j + 1) / 4)), ('L' if first == 'R' else 'R'): gait.smooth(_frac(j, 2, 6))}
        D = round(s0['D'] * (1 - gait.smooth(j / (STOP_N - 1))))
        hip = gait.HIP_REST - D
        b = 1 - gait.smooth((j + 1) / (STOP_N + 1))
        s = {'D': D, 'b': b, 'amp': b, 'tw': round(s0['tw'] * b), 'sw': round(s0['sw'] * b),
             'sw1': round(s0['sw1'] * b), 'arm': s0['arm'] * b, 'p': s0['p'], 'kind': kind, 'lean': LEAN_OF[kind]}
        for k in 'RL':
            a0, p0 = legs[k]['ankle'], legs[k]['pitch']
            x = a0[0] * (1 - u[k])
            far = away(k) > 3 or not legs[k]['down']
            z = a0[1] + (gait.ANKLE_H - a0[1]) * u[k] + (3.0 * math.sin(math.pi * u[k]) if far else 0.0)
            L = gait.solve(hip, (x, z), p0 * (1 - u[k]), u[k] in (0.0, 1.0) and legs[k]['down'] or u[k] == 1.0)
            if 'lat' in legs[k]:
                L['lat'] = legs[k]['lat'] * (1 - u[k])
            s['leg' + k] = L
            s['in' + k] = round(s0['in' + k] * (1 - u[k]))
        states.append(s)
    return Clip(f'{kind}_stop_{entry}', states, lambda k: loop_state(entry - k, kind))


# ------------------------------------------------------------------ layers, built once per view
# the shoulder plate of the sword arm (local px): drawn over the arm that hangs from under it
PAULDRON = {
    'front': [(98, 128), (118, 102), (138, 98), (140, 66), (150, 66), (153, 96), (170, 92), (172, 46),
              (181, 46), (184, 92), (190, 100), (190, 196), (150, 204), (112, 200), (98, 190)],
}
# back view, local px: the whole right arm down to the cuff (the standing sprite erases it below
# the elbow), the row of the elbow, where the fist goes
BACK_ARM = [(236, 108), (262, 100), (290, 112), (302, 150), (298, 200), (300, 245), (314, 262), (314, 300),
            (310, 336), (270, 336), (266, 298), (262, 255), (244, 240), (236, 200), (232, 150)]
BACK_ELBOW_ROW = 262
BACK_FIST = (290, 351)

_built = {}


def _fist_centre(layer, rows=13):
    x0, y0, x1, y1 = layer.bbox()
    fist = [q for q in layer.pix if q[1] >= y1 - rows]
    return sum(q[0] for q in fist) / len(fist), (y1 - rows + y1 - 1) / 2


def _layers(direction):
    if direction in ('right', 'left'):
        if 'side' not in _built:
            S = dict(side.layers())
            lay = S['lay']
            S['place0'] = drag.standing('right', lay)
            _built['side'] = S
        return _built['side']
    if direction in _built:
        return _built[direction]
    view = rig.VIEW_OF[direction]
    layers, order = anim_idle.build_layers(direction, cape_reach=10)
    lay = rig.Layout(view)
    S = {'layers': layers, 'lay': lay, 'order': order, 'view': view,
         'sm': {k: lay.local_to_final((0, v))[1] for k, v in anim_idle.SEAMS[view].items()}}
    allpix = set()
    for L in layers.values():
        allpix |= set(L.pix)
    sword = set(layers['sword'].pix)
    # nothing hangs under the boots: the cloth underlays stop at the hem (ragged)
    hem = lay.local_to_final((0, 640))[1]
    boots = set()
    for name in ('leg_l', 'leg_r'):
        boots |= {q for q in layers[name].pix if q[1] > hem - (q[0] * 7 % 3)}
    for name in ('cape', 'drape'):
        if name in layers:
            layers[name].under = {q: c for q, c in layers[name].under.items() if q not in boots}
    # the sword is no longer where the standing pose has it: no underlay pretends to know
    # what was behind it (front view: except beside the fist, where the shadowed sword arm
    # is - a few px of the torso's underlay stand in for it while the hand comes down)
    keep_above = lay.local_to_final((0, 330))[1] if direction == 'down' else -1
    for name, L in layers.items():
        if name != 'sword':
            L.under = {q: c for q, c in L.under.items() if q not in sword or (name == 'body' and q[1] < keep_above)}
    if direction == 'down':
        mask = rig.poly_mask(view, [PAULDRON[view]], lay)
        body = layers['body']
        S['pauldron'] = rig.Layer('pauldron', {q: c for q, c in body.pix.items() if q in mask})
        body.pix = {q: c for q, c in body.pix.items() if q not in mask}
        body.under.update({q: c for q, c in S['pauldron'].pix.items()})   # the row maps read one layer
        # the screen-right leg shows from the knee down; its shin runs up under the drape
        rig.extend_up(layers['leg_r'], allpix - set(layers['cape'].pix), 12)
        # the cape where the planted sword stood: the other side's drape, mirrored
        cape = layers['cape']
        for (x, y), c in list(cape.pix.items()):
            q = (2 * rig.AX - x, y)
            if x > rig.AX and (q not in allpix or q in sword) and y > S['sm']['chest']:
                cape.pix[q] = c
        # the sword arm hanging: the free arm's pixels mirrored
        arm_pix = layers['arm'].pix
        S['arm2'] = rig.Layer('arm2', {(2 * rig.AX - x, y): c for (x, y), c in arm_pix.items()})
        S['hand1'] = _fist_centre(S['arm2'])
    else:
        for name in ('leg_l', 'leg_r'):
            rig.extend_up(layers[name], allpix, 14)
        arm_l = layers['arm']
        S['free'] = rig.Layer('free', {q: c for q, c in arm_l.pix.items() if q[0] < rig.AX},
                              {q: c for q, c in arm_l.under.items() if q[0] < rig.AX})
        # the sword arm: the concept's own hanging right arm (the standing pose erases it below
        # the elbow: the hand is up on the grip), stylised the same way - not the erased one,
        # so there is no seam at the cut
        full = Image.new('RGBA', lay.canvas_size, (0, 0, 0, 0))
        full.alpha_composite(B.ref('back'), (idle.PAD, idle.PAD))
        orig = rig.pixels(B.stylize(lay.canvas_to_work(full), B.load_palette()))
        mask = rig.poly_mask(view, [BACK_ARM], lay)
        armour = lambda c: not rig.is_cloth(c) and not (c[0] - c[1] > 35 and B.lum(c) < 110)    # not the cape's reds
        whole = {q: c for q, c in orig.items() if q in mask and armour(c)}
        elbow = lay.local_to_final((0, BACK_ELBOW_ROW))[1]
        S['hand1'] = lay.local_to_final(BACK_FIST)
        # the fist: seen from the thumb's side (the blade trails towards the camera from the
        # thumb side of the fist) - the front view's hanging fist, which shows that side
        fist = arm.fist_only(S['hand1'], (0.0, 1.0), (FW, FH), mirror=True)
        fore = {q: c for q, c in whole.items() if q[1] >= elbow}
        top = min(q[1] for q in fist)
        fore = {q: c for q, c in fore.items() if q[1] < top + 2}
        fore.update(fist)
        S['forearm'] = rig.Layer('forearm', fore)
        S['fist_rows'] = max(q[1] for q in fist) - top + 1
    S['place0'] = drag.standing(view, lay)
    _built[direction] = S
    return S


import idle      # noqa: E402  (used by _layers for the back view's arm)
import side      # noqa: E402
import arm       # noqa: E402
import fleg      # noqa: E402


# ------------------------------------------------------------------ shared pieces of a pose
def cape_src(sm, d_top, d_hem, top_dx, trail):
    """Inverse map of a cape layer: its top rides the shoulders (dx top_dx, dy d_top), the hem
    gives d_hem, rows are dropped in between; trail(t) is the sideways offset at height t
    (0 top .. 1 hem)."""
    top, hem = sm['cape_top'], sm['cape_hem']
    def src(x, y):
        t = _frac(y - d_top, top, hem)
        dy = round(d_top + (d_hem - d_top) * t)
        t = _frac(y - dy, top, hem)
        return x - (round(top_dx * (1 - t)) + trail(t)), y - dy
    return src


def _hem(clip, i):
    s = clip.at(i - 2)
    return -1 if s['D'] in (1, 2) and s['amp'] > 0.5 else 0


def shear_to(pix, tip, grip, delta):
    """A rendered sword (or arm) with its far end (tip) fixed and its near end (grip) moved by
    `delta` whole px: every pixel moves in proportion to how far along it is. No resampling."""
    if delta == (0, 0):
        return pix
    ax = (grip[0] - tip[0], grip[1] - tip[1])
    n2 = ax[0] ** 2 + ax[1] ** 2
    out = {}
    xs = [q[0] for q in pix]
    ys = [q[1] for q in pix]
    for y in range(min(ys) - 3, max(ys) + 4):
        for x in range(min(xs) - 3, max(xs) + 4):
            t = min(1.2, max(0.0, ((x - tip[0]) * ax[0] + (y - tip[1]) * ax[1]) / n2))
            c = pix.get((x - round(t * delta[0]), y - round(t * delta[1])))
            if c is not None:
                out[(x, y)] = c
    return out


_swords = {}


def split_at_grip(pix, place):
    """A drawn sword as (pommel side, blade side) of the grip point."""
    g, ax = place['grip'], place['axis']
    back, front = {}, {}
    for (x, y), c in pix.items():
        (front if (x + 0.5 - g[0]) * ax[0] + (y + 0.5 - g[1]) * ax[1] >= 0 else back)[(x, y)] = c
    return back, front


def sword_pixels(S, b, hand1, shift, far=False, source='bare'):
    """The view's sword for blend b (0 standing .. 1 dragged). hand1: where the dragging fist
    is with the body at rest (final px); shift: (dx, dy) the body has moved it this pose.
    b = 1: one cached render with the fist DREF px down, sheared to the fist (tip fixed), so
    the blade's texture does not shimmer. Returns (pixels, placement)."""
    view, lay = S['view'], S['lay']
    if b >= 1.0:
        key = (view, far)
        if key not in _swords:
            place = drag.dragged(view, DREF, lay, hand=(hand1[0], hand1[1] + DREF), far=far)
            _swords[key] = (drag.sword_image(view, place, (FW, FH), source='bare'), place)
        pix, place = _swords[key]
        delta = (shift[0], shift[1] - DREF)
        g = place['grip']
        moved = dict(place, grip=(g[0] + delta[0], g[1] + delta[1]))
        return shear_to(pix, drag.tip_of(view, place), g, delta), moved
    p1 = drag.dragged(view, shift[1], lay, hand=(hand1[0] + shift[0], hand1[1] + shift[1]), far=far)
    place = drag.blend(S['place0'], p1, b)
    if view == 'right':
        # the tip stays on the ground while the sword swings back (and comes towards / goes
        # away from the camera: lower / higher on screen)
        im, pts, _ = drag.sword_source(view)
        n = math.hypot(pts['tip'][0] - pts['grip'][0], pts['tip'][1] - pts['grip'][1])
        ground = rig.AY + 0.9 + (drag.tip_of(view, p1)[1] - (rig.AY + 0.9)) * b
        place['grip'] = (place['grip'][0], ground - place['axis'][1] * n)
    return drag.sword_image(view, place, (FW, FH), source=source), place


def _finish(direction, out):
    pix = rig.composite(out)
    rig.fill_pinholes(pix, anim_idle.standing_pinholes(direction))
    B.drop_specks(pix)
    return pix


# ------------------------------------------------------------------ side views
_arm_cache = {}


def pose_side(clip, i, far=False):
    """A side-view pose in facing-right space. far = the Boss faces left (mirrored by
    render()): the sword is in the far hand, the near arm hangs free."""
    S = _layers('right')
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    s, s1 = clip.at(i), clip.at(i - 1)
    d, d1, b = s['D'], s1['D'], s['b']
    belt = sm['belt']
    lean_full = math.tan(math.radians(LEAN_DEG))
    lean_kind = lean_full * s['lean']
    lean = lean_kind * b
    # the visible shoulder goes back when its own leg is forward: the right one at pose 0
    tw, tw1 = (-s['tw'], -s1['tw']) if far else (s['tw'], s1['tw'])
    # sidesteps: a foot towards the camera is lower on screen, one further away higher (0.35
    # of the distance, as everywhere); his right side is the camera's side unless he faces left
    cam = -1 if far else 1
    def seen(L):
        lat = L.get('lat', 0.0)
        if not lat:
            return L, 0.0
        P = gait.solve(L['hip'][1], (L['ankle'][0], L['ankle'][1] - DEPTH * lat * cam), L['pitch'], L['down'])
        return P, lat * cam
    (near_leg, near_depth), (far_leg, far_depth) = (seen(s['legL']), seen(s['legR'])) if far else (seen(s['legR']), seen(s['legL']))
    # the legs are HIP_HALF either side of the centre: the far foot is nearer the camera than
    # the near one only while it crosses in front
    far_on_top = far_depth - HIP_HALF > near_depth + HIP_HALF

    def chest_dx(sy, t, ln=lean):
        """Forward shift of a source row: the lean grows with the height above the belt, the
        counter-turn comes in over the 6 rows above it."""
        return round(ln * max(0.0, belt - sy)) + round(t * (1 - _frac(sy, belt - 6, belt)))

    sh0 = S['shoulder']
    shoulder = (sh0[0] + chest_dx(sh0[1], tw), sh0[1] + d)
    # the dragging hand with the body at rest (hips DREF down, full lean): at the end of the
    # arm hanging from the shoulder
    sh_ref = (sh0[0] + round(lean_full * max(0.0, belt - sh0[1])), sh0[1] + DREF)
    J_ref = arm.hanging(sh_ref, *DRAG_ARM)
    hand1 = (J_ref['hand'][0], J_ref['hand'][1] - DREF)
    # the hand follows the right shoulder a pose late; with less lean the shoulder (and the
    # hand under it) is further back
    rise = max(0.0, belt - sh0[1])
    kdx = round(lean_kind * rise) - round(lean_full * rise)
    sword, place = sword_pixels(S, b, hand1, (s1['tw'] + kdx, d1), far=far,
                                source='bare' if (not far or b >= FAR_BARE) else 'fist')

    out = []
    if far:
        if b < FAR_BARE:
            # the far forearm still reaches past the chest to the fist on the grip
            g0 = S['place0']['grip']
            mx, my = round(place['grip'][0] - g0[0]), round(place['grip'][1] - g0[1])
            out.append({(x + mx, y + my): c for (x, y), c in S['farwrist'].pix.items()})
        out.append(sword)                                 # behind the cape and the body
    # cape: top on the shoulders; trails behind (-x) when he walks forward, is pushed a little
    # forward when he backs up, hangs straight in a sidestep; flutters once per step
    drift = 2.0 * TRAIL_OF[s['kind']]
    def trail(t):
        return -round(t ** 1.5 * (drift + 1.5 * math.sin(4 * math.pi * s['p'] - 1.0 - 1.5 * t)) * s['amp'])
    out.append(rig.warp(layers['cape'], cape_src(sm, d, _hem(clip, i), chest_dx(sm['cape_top'] + 8, tw), trail)))

    # between the legs, then the far leg
    out.append(rig.warp(S['backdrop'], lambda x, y: (x, y - d)))
    far_pix = {(x, y - FAR_UP): c for (x, y), c in limb.darken(limb.leg_pixels(far_leg)).items()}
    if not far_on_top:
        out.append(far_pix)

    # the tabard in front of the legs: its top on the belt, the hem a pose later; swings once per step
    ht, hh = sm['hang_top'], sm['hang_hem']
    sw = round(1.2 * math.sin(4 * math.pi * s1['p']) * s1['amp'])
    def cloth_src(x, y):
        sy = round(piecewise(y, [ht, hh], [ht + d, hh + d1]))
        return x - round(sw * _frac(sy, ht, hh)), sy
    out.append(rig.warp(layers['cloth'], cloth_src))
    out.append(limb.leg_pixels(near_leg))
    if far_on_top:
        out.append(far_pix)

    # body: hips drop; above the belt the chest leans and counter-turns
    body_src = lambda x, y: (x - chest_dx(y - d, tw), y - d)
    out.append(rig.warp(layers['body'], body_src, pad=16))

    if far:
        # the near arm hangs free from the shoulder and swings against the near (left) leg
        fa = S['free_arm']
        J = S['free_joints']
        swing = round(SWING_SIDE * s['arm'])
        mx, my = round(shoulder[0] - sh0[0]), round(shoulder[1] - sh0[1])
        pix = {(x + mx, y + my): c for (x, y), c in fa.pix.items()}
        sh = (J['shoulder'][0] + mx, J['shoulder'][1] + my)
        hd = (J['hand'][0] + mx, J['hand'][1] + my)
        out.append(shear_to(pix, sh, hd, (swing, 0)))
    else:
        out.append(sword)
        # the arm that holds it: from the shoulder to the fist on the grip
        if b >= 1.0:
            if 'loop' not in _arm_cache:
                _arm_cache['loop'] = arm.near(arm.render(J_ref, (FW, FH)))
            pix = shear_to(_arm_cache['loop'], J_ref['hand'], sh_ref, (round(shoulder[0] - sh_ref[0]), round(shoulder[1] - sh_ref[1])))
            g = place['grip']
            pix = shear_to(pix, shoulder, J_ref['hand'], (round(g[0] - J_ref['hand'][0]), round(g[1] - J_ref['hand'][1])))
        else:
            # between the standing pose's elbow (the approved sprite's, at the chest) and the
            # hanging arm's; the forearm runs from there to the fist wherever the sword has it
            # (half-way down it points towards the camera: short on screen)
            e0 = lay.local_to_final(ELBOW0)
            e0 = (e0[0] + chest_dx(e0[1], tw), e0[1] + d)
            e1 = (J_ref['elbow'][0] + shoulder[0] - sh_ref[0], J_ref['elbow'][1] + shoulder[1] - sh_ref[1])
            elbow = (e0[0] + (e1[0] - e0[0]) * b, e0[1] + (e1[1] - e0[1]) * b)
            pix = arm.near(arm.render(arm.pose(shoulder, elbow, place['grip']), (FW, FH)))
        out.append(pix)
    out.append(rig.warp(S['pauldron'], body_src, pad=16))
    out.append(rig.warp(layers['head'], lambda x, y: (x - chest_dx(y - d1, tw1), y - d1), pad=16))
    return _finish('right', out)


# ------------------------------------------------------------------ front and back views
# landmark rows of the front view's legs, local px: hip joint, knee, ankle (leg_r shows from
# the knee down)
FRONT_LEG = {'leg_l': (344, 500, 600), 'leg_r': (None, 525, 600)}


def leg_deltas(L, sign):
    """How far a leg's knee and ankle move on screen in the front (sign +1) or back (-1) view:
    height changes plus DEPTH of the forward distance."""
    dk = -(L['knee'][1] - (gait.ANKLE_H + gait.SHIN)) + sign * DEPTH * L['knee'][0]
    da = -(L['ankle'][1] - gait.ANKLE_H) + sign * DEPTH * L['ankle'][0]
    return dk, da


def _leg_front_src(layer, lay, L, d, hip_dx, foot_dx, marks):
    """Front view leg: rows remapped between hip joint, knee, ankle, sole; sheared from the
    hips' sideways shift to the foot's."""
    dk, da = leg_deltas(L, +1)
    hip, knee, ankle = (None if v is None else lay.local_to_final((0, v))[1] for v in marks)
    sole = rig.AY
    if hip is None:
        src = [knee, ankle, sole]
        tgt = [knee + dk, ankle + da, sole + da]
        top = tgt[0] - (knee - min(q[1] for q in layer.pix))
    else:
        src = [hip, knee, ankle, sole]
        tgt = [hip + d, knee + dk, ankle + da, sole + da]
        top = tgt[0]
    def f(x, y):
        sy = round(piecewise(y, src, tgt))
        dx = round(hip_dx + (foot_dx - hip_dx) * _frac(y, top, tgt[-1]))
        return x - dx, sy
    return f


def _hang_src(layer, top_shift, hand, fist_rows=13, hide_above=False):
    """A hanging arm drawn from its shoulder (its top rows moved by top_shift) to its fist
    (the last fist_rows rows, centred on `hand`): rows dropped or duplicated in between, the
    sideways shift running from the shoulder's to the fist's. hand None: only top_shift."""
    x0, y0, x1, y1 = layer.bbox()
    fist_top = y1 - fist_rows
    fist = [q for q in layer.pix if q[1] >= fist_top]
    fx = sum(q[0] for q in fist) / len(fist)
    fy = (fist_top + y1 - 1) / 2
    hx, hy = hand
    tgt_fist = round(hy - (fy - fist_top))
    tgt_top = y0 + top_shift[1]
    dxf = round(hx - fx)
    if tgt_fist <= tgt_top:                 # the hand is above the part's top: only the fist shows
        if hide_above:
            return lambda x, y: None        # (back view: the raised hand is in front of the body)
        return lambda x, y: (x - dxf, y - (tgt_fist - fist_top)) if y >= tgt_fist else None
    src, tgt = [y0, fist_top, y1], [tgt_top, tgt_fist, tgt_fist + (y1 - fist_top)]
    def f(x, y):
        dx = round(top_shift[0] + (dxf - top_shift[0]) * _frac(y, tgt[0], tgt[1]))
        return x - dx, round(piecewise(y, src, tgt))
    return f


def _front_back(direction, clip, i):
    sign = 1 if direction == 'down' else -1       # forward is down-screen in the front view
    S = _layers(direction)
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    s, s1, s2 = clip.at(i), clip.at(i - 1), clip.at(i - 2)
    d, d1, b = s['D'], s1['D'], s['b']
    kind = s['kind']
    strafe = kind.startswith('strafe')
    k_kind = sign * round(LEAN_ROWS * s['lean'])
    k = sign * round(LEAN_ROWS * b * s['lean'])   # the chest's rows: lower in front, higher behind
    # screen x of the Boss's right side: left in the front view, right in the back view
    hipx = -sign * s['sw']
    cx, hx = -sign * s['sw1'], -sign * s1['sw1']
    belt, chest = sm['belt'], sm['chest']
    arm_extra = sign * round(DEPTH * ARM_SWING * s['arm'])
    # a sidestep leaves the cape behind: it hangs towards where he came from
    drift = (sign if kind == 'strafe_r' else -sign) * 2.0 if strafe else 0.0

    def trail(t):
        j = clip.at(i - 2 - round(2 * t))
        return round(t ** 1.5 * (2.5 * -sign * math.sin(2 * math.pi * (j['p'] - 0.05)) + drift
                                 + (0.8 * math.sin(4 * math.pi * j['p']) if strafe else 0.0)) * j['amp'])
    cape = rig.warp(layers['cape'], cape_src(sm, d + k, _hem(clip, i), cx, trail), pad=16)
    # the dragging fist is where the hanging arm's own fist is (it rides on the chest)
    kf = sign * LEAN_ROWS
    h1 = (S['hand1'][0], S['hand1'][1] + kf)
    # while the sword is still upright in front of the body it keeps its own fist (front view:
    # with the shadowed arm behind it, which joins the fist to the shoulder)
    source = 'bare' if b >= SWORD_BEHIND else ('raw' if direction == 'down' else 'fist')
    sword, place = sword_pixels(S, b, h1, (-sign * s1['sw1'], d1 + k_kind - kf), source=source)
    hand = place['grip']
    head = rig.warp(layers['head'], lambda x, y: (x - hx, y - d1 - k), pad=16)

    # chest: the lean's rows are taken out of (front) or added to (back) the belly
    top = min(q[1] for q in layers['head'].pix)
    rows_src, rows_tgt = [top, chest, belt], [top + d + k, chest + d + k, belt + d]
    def body_src(x, y):
        sy = round(piecewise(y, rows_src, rows_tgt))
        t = 1 - _frac(sy, belt - 6, belt)
        return x - round(hipx + (cx - hipx) * t), sy

    out = []
    if direction == 'down':
        out.append(cape)
        if b >= SWORD_BEHIND:
            out.append(sword)
        if strafe:
            # the legs swing sideways from the hips and cross: posed from the concept (fleg.py);
            # the trailing leg passes in front (nearer the camera), so it is drawn over the other
            right = fleg.leg(s['legR'], 'R', d, hipx, lay)
            left = fleg.leg(s['legL'], 'L', d, hipx, lay)
            out.extend([right, left] if kind == 'strafe_r' else [left, right])
        else:
            out.append(rig.warp(layers['leg_l'], _leg_front_src(layers['leg_l'], lay, s['legR'], d, hipx, s['inR'],
                                                              FRONT_LEG['leg_l']), pad=16))
            out.append(rig.warp(layers['leg_r'], _leg_front_src(layers['leg_r'], lay, s['legL'], d, hipx, -s['inL'],
                                                              FRONT_LEG['leg_r']), pad=16))
        out.append(rig.warp(layers['drape'], cape_src(sm, d + k, _hem(clip, i), cx, trail), pad=16))
        out.append(rig.warp(layers['body'], body_src, pad=16))
        ht, hh = sm['hang_top'], sm['hang_hem']
        for name, late, amp in (('chain', 4, 1.3), ('tabard', 3, 1.0)):
            hemx = -sign * clip.at(i - late)['sw'] * amp
            def hang_src(x, y, hemx=hemx):
                t = _frac(y - d, ht, hh)
                return x - round(hipx + (hemx - hipx) * t), y - d
            out.append(rig.warp(layers[name], hang_src))
        free = layers['arm']
        fb = free.bbox()
        out.append(rig.warp(free, lambda x, y: (x - cx, round(piecewise(y, [fb[1], fb[3] - 1],
                                                                        [fb[1] + d + k, fb[3] - 1 + d + k + arm_extra]))),
                            pad=16))
        if b > 0:
            out.append(rig.warp(S['arm2'], _hang_src(S['arm2'], (cx, d + k), hand), pad=60))
        out.append(rig.warp(S['pauldron'], body_src, pad=16))
        out.append(head)
        if b < SWORD_BEHIND:
            out.append(sword)
    else:
        if b < SWORD_BEHIND:
            out.append(sword)
        boots = [('leg_l', s['legL'], s['inL']), ('leg_r', s['legR'], -s['inR'])]
        if kind == 'strafe_l':
            boots.reverse()         # the trailing foot crosses in front of him: behind, seen from the back
        for name, L, inward in boots:
            da = round(leg_deltas(L, -1)[1])
            dx = inward + round(L.get('lat', 0.0))        # his right is screen right here
            out.append(rig.warp(layers[name], lambda x, y, da=da, dx=dx: (x - dx, y - da), pad=30))
        out.append(cape)
        free = S['free']
        fb = free.bbox()
        out.append(rig.warp(free, lambda x, y: (x - cx, round(piecewise(y, [fb[1], fb[3] - 1],
                                                                        [fb[1] + d + k, fb[3] - 1 + d + k + arm_extra]))),
                            pad=16))
        # the sword arm: the approved arm (down to just below the elbow) rides on the chest;
        # the forearm and fist come down into view as the hand is lowered (pointing away from
        # the camera they are foreshortened: rows dropped); the blade comes towards the
        # camera from the thumb side of the fist, so the pommel is behind the arm and the
        # blade over it
        pommel, blade = split_at_grip(sword, place) if b >= SWORD_BEHIND else ({}, {})
        out.append(pommel)
        out.append(rig.warp(layers['arm'], lambda x, y: (x - cx, y - d - k) if x - cx >= rig.AX else None, pad=16))
        if b >= SWORD_BEHIND:
            out.append(rig.warp(S['forearm'], _hang_src(S['forearm'], (cx, d + k), hand, S['fist_rows'], True), pad=60))
        out.append(blade)
        out.append(head)
    return _finish(direction, out)


# ------------------------------------------------------------------ clips -> frames
def render(direction, clip):
    """Every pose of a clip as {(x, y): colour} in the 256 x FH walk frame."""
    if direction == 'left':
        return [side.mirror(pose_side(clip, i, far=True)) for i in range(len(clip))]
    if direction == 'right':
        return [pose_side(clip, i) for i in range(len(clip))]
    return [_front_back(direction, clip, i) for i in range(len(clip))]


_frames = {}


def clip_of(name):
    """'<kind>', '<kind>_start' or '<kind>_stop_<entry>' (kind in KINDS) -> Clip."""
    if name in KINDS:
        return walk_clip(name)
    if name.endswith('_start'):
        return start_clip(name[:-len('_start')])
    kind, entry = name.rsplit('_stop_', 1)
    return stop_clip(int(entry), kind)


def frames(direction, name='walk'):
    """Cached frames of a clip (see clip_of)."""
    key = (direction, name)
    if key not in _frames:
        _frames[key] = render(direction, clip_of(name))
    return _frames[key]
