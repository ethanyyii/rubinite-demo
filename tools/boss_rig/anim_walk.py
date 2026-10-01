"""How the Boss moves - forward (walk), backward (back), sideways (strafe_r, strafe_l) - with the
greatsword carried on his right shoulder, and the clips that join each to the standing pose:
<kind>_start (站姿 → 移動) and <kind>_stop (移動 → 站姿).

User 2026-09-30: every way of moving carries the sword level on the right shoulder, the tip
behind him, the right fist on the grip in front of the shoulder (the dragged sword of the first
forward walk is gone: a sword dragged behind only makes sense walking forward). The carry is his
moving / ready pose - every attack will start from it and end in it. Earlier the same day: lean
forward when walking (the weight ahead of the feet), animate going into and out of the walk,
the sword hand is the right hand in every direction (facing left it is on the far side).

Clips (every pose is held gait.HOLD = 4 combat frames at 60 px/s; the forward walk 2 at 120 px/s):
  <kind>        20 poses, loops. Legs from gait.py (one model for all directions): the planted
                foot moves back 4 px per pose, exactly what the game moves the Boss.
  <kind>_start  START_N = 12 poses from the standing pose: a half step (4 poses, the game moves
                him 16 px) then eight of the loop's poses, while the sword goes from planted on
                the ground round in front of him onto the shoulder (carry.py) and the body leans
                in. The loop goes on at START_JOINS[kind].
  <kind>_stop   STOP_N = 10 poses back to the standing pose, from the loop's poses STOP_FROM
                (0, 5, 10, 15: each heel strike and each mid-stance): the feet are gathered
                under the hips one after the other, the body straightens, the sword comes off
                the shoulder, up and round in front of him, and is planted. The Boss does not
                move during it.
Frame: the loops 256 x 224, foot anchor (128, 208) - the same as the idle's. The start and stop
clips: the attack container 384 x 336, foot anchor (192, 272) - the sword stands upright over his
head and points forward past the small frame; their frames' pixels are in the small frame's
coordinates, reaching EXT px past its left, top and right edges.

Part by part (animation-review §4.2), side view; front and back read the same numbers through
the 0.35 depth foreshortening:
  legs     - heel strike, flat, toe-off, swing (gait.py); side view: posed from the concept
             (limb.py), the far leg darker and 2 px up; front/back: the approved leg pixels,
             rows dropped or duplicated between hip, knee and ankle, feet brought in under
             the hips (FEET_IN) - the standing pose's wide stance is for standing (§4.3).
             Backward: the same legs run the other way (toe first); sideways: see loop_state
  hips     - 1-4 px below standing height (2-6 in the sidestep): lowest with both feet down;
             front/back: sway 2 px towards the planted foot
  chest    - leans forward LEAN_DEG degrees about the hips in the forward walk (half of it in
             the sidestep, none backing up): side view, every row above the belt is shifted
             forward in proportion to its height, the head about 5 px; front: the chest and
             head sit LEAN_ROWS px lower, back: higher. Counter-turns against the legs by 1 px
  head     - follows the chest one pose late
  sword    - carried on the right shoulder (carry.py: one 3D pose projected into each view):
             it lies on the shoulder plate and moves with it, in the same pose. Rendered once
             per view and moved in whole pixels: the very same sword in every way of moving,
             and its texture does not shimmer
  sword arm - the right arm in every direction: the upper arm comes forward from under the
             shoulder plate, the forearm goes up to the fist, which holds the grip in front of
             the plate (arm.py: the fist is the arm's, in line with the forearm; the sword,
             drawn without the standing pose's fist, passes through it).
             Facing right it is the near arm, in front of the chest. Facing down the forearm is
             in front of the plate, the pommel towards the camera. Facing up the hand is in
             front of him: only the top of the fist shows over the shoulder. Facing left it is
             the far arm: the body hides it, only the fist with the pommel shows in front of
             the throat
  free arm - front/back: swings against its own leg (the fist rises and falls 3 px); facing
             left it is the near arm (arm.py), swinging SWING_SIDE px about the shoulder
  facing left - not facing right mirrored: the sword is on the far shoulder (side.py), drawn
             behind the body, the cape and the head
  cape     - top on the shoulders; squashed rather than lowered when the hips drop; side:
             trails behind and flutters once per step; front/back: sways after the hips
  tabard, chain, side cloth - hang from the belt, swing later than the hips
"""
import math
import boss as B
import rig
import gait
import limb
import anim_idle
import sword as swd

N = gait.POSES
HOLD = gait.HOLD
FW, FH = rig.FW, rig.FH
# the start and stop clips: the sword swings up in front of him and stands upright over his
# head - drawn in the attack container (384 x 336, foot anchor (192, 272)), which is this
# frame grown by EXT px on the left, the top and the right
EXT = 64
BIG = (FW + 2 * EXT, FH + EXT + 48)
START_N = 12
START_HALF = 4           # poses of the half step before the loop's poses begin
START_JOIN = START_N - START_HALF      # the loop goes on at this pose after walk_start
STOP_N = 10
STOP_FROM = (0, 5, 10, 15)
LEAN_DEG = 6.0
LEAN_ROWS = 3
FEET_IN = 4              # front/back: each foot this much closer to the centre line than standing
ARM_SWING = 8.0          # how far the free fist swings forward and back (x DEPTH on screen)
FAR_UP = 2               # the side view's far leg is drawn this much higher (it is further away)
DEPTH = swd.DEPTH
ELBOW0 = (158, 215)      # side view, local px: the elbow of the approved standing pose (at the chest)
SWING_SIDE = 5           # facing left: px the free fist swings forward and back
# The sword arm while he carries the sword (carry.py): the fist in front of the shoulder plate,
# the forearm upright under it, the elbow forward at the chest, the upper arm coming out from
# under the plate. Elbow relative to the fist, final px:
SIDE_ELBOW = (-5.0, 21.7)        # side views
FRONT_ELBOW = (-5.0, 21.0)       # front view (the elbow a little further out than the fist)
FRONT_ELBOW0 = (95.5, 99.5)      # front view, final px: the standing pose's elbow (behind the fist on the grip:
                                 # the forearm points at the camera)
PLATE_TOP = 75                   # side views, final row: the shoulder plate's top, where the blade lies


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
# They share the sword carried on the shoulder and the arm that holds it, so the game can switch
# between them without the sword jumping; they differ in the legs, the lean and the cape.
KINDS = ('walk', 'back', 'strafe_r', 'strafe_l')
LEAN_OF = {'walk': 1.0, 'back': 0.0, 'strafe_r': 0.5, 'strafe_l': 0.5}    # share of LEAN_DEG
TRAIL_OF = {'walk': 1.0, 'back': -0.4, 'strafe_r': 0.0, 'strafe_l': 0.0}  # side view: how far the cape trails behind
HIP_HALF = 17.0          # front/back: each hip joint this far from the centre line
STRAFE_IN = 11           # back view: the boots stand 30 px out; in the sidestep they are under the hips (19)
CROSS = 8.0              # strafing: the trailing foot swings this far forward, around the other leg
LIFT_STRAFE = 6.0        # strafing: how high the swinging foot is lifted
STRAFE_D = [6, 6, 5, 4, 3, 2, 2, 3, 4, 5]   # strafing: the hips' drop per pose (px; twice a cycle, 1 px steps)


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
        # the feet are up to 78 px apart: the hips sink more than in the walk, so that the
        # legs are never longer than they are (front view: hip to ankle 60 px)
        D = STRAFE_D[i % len(STRAFE_D)]
        hip = gait.HIP_REST - D
        lead, trail = _strafe_leg(p, False, side, hip), _strafe_leg(p + 0.5, True, side, hip)
        s = {'D': D, 'tw': 0, 'sw': 0, 'sw1': 0, 'inR': STRAFE_IN, 'inL': STRAFE_IN, 'arm': 0.0,
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
             # (the toe points down: the ankle stays high enough for it to clear the ground)
             'back': [((-2.0, 2.0), -6.0), ((-7.0, 5.5), -12.0), ((-12.0, 7.0), -18.0), ((-15.5, 7.2), -23.0)],
             'strafe': [((2.0, 2.5), 0.0), ((8.0, 5.0), 0.0), ((15.0, 5.0), 0.0), ((21.0, 2.0), 0.0)]}
    move = -1 if kind == 'back' else 1                   # the planted foot drifts against the travel
    states = []
    for k in range(START_N):
        b = ease((k + 1) / START_N)
        if k < START_HALF:
            D = k + 1 if kind in ('walk', 'back') else k + 2       # the sidestep's loop starts 6 px down
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
        if kind in ('walk', 'back'):
            D = round(s0['D'] * (1 - gait.smooth(j / (STOP_N - 1))))
        else:
            D = round(s0['D'] * (1 - (j + 1) / STOP_N))       # up to 6 px to give back: 1 px a pose
        hip = gait.HIP_REST - D
        b = 1 - ease((j + 1) / (STOP_N + 1))
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
_built = {}


def _layers(direction):
    if direction in ('right', 'left'):
        if 'side' not in _built:
            S = dict(side.layers())
            S['place0'] = swd.standing('right', S['lay'])
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
        # the sword arm (arm.py: the other arm's drawing mirrored) comes out from under the
        # shoulder plate here
        sx, sy = lay.local_to_final(arm.SHOULDER)
        S['shoulder'] = (2 * rig.AX + 1 - sx, sy)
    else:
        for name in ('leg_l', 'leg_r'):
            rig.extend_up(layers[name], allpix, 14)
        arm_l = layers['arm']
        S['free'] = rig.Layer('free', {q: c for q, c in arm_l.pix.items() if q[0] < rig.AX},
                              {q: c for q, c in arm_l.under.items() if q[0] < rig.AX})
        # (the sword arm: the approved sprite's own, down to just below the elbow - the hand is
        # up at the shoulder in front of him, as it is when he stands)
    S['place0'] = swd.standing(view, lay)
    _built[direction] = S
    return S


import side      # noqa: E402
import arm       # noqa: E402
import fleg      # noqa: E402
import carry     # noqa: E402


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
ARM_JOINTS = {}          # (direction, clip, pose) -> the sword arm's joints as drawn (checks.py reads them)
SWORD_DRAWN = {}         # (direction, clip, pose) -> (the sword's pixels before anything covers it, its placement);
                         # facing left: in facing-right space, like the pose itself until render() mirrors it


def sword_pixels(S, b, ride, far=False):
    """The view's sword at blend b (0 planted as he stands .. 1 carried on the shoulder), as
    (pixels, placement). ride: whole px the chest has moved the shoulder - and the carried
    sword on it - from rest. b = 1: one cached render per view, moved by whole pixels, so
    every way of moving shows the very same sword and its texture never shimmers. It is drawn
    without the standing pose's fist: the fist is the arm's (arm.py)."""
    view = S['view']
    if b >= 1.0:
        key = (view, far)
        if key not in _swords:
            place = carry.place(view, 1.0, S['place0'], far)
            _swords[key] = (swd.sword_image(view, place, (FW, FH), source='bare'), place)
        pix, place = _swords[key]
        g = place['grip']
        return _moved(pix, ride), dict(place, grip=(g[0] + ride[0], g[1] + ride[1]))
    place = carry.place(view, b, S['place0'], far, ride)
    return swd.sword_image(view, place, BIG, source='bare', origin=(-EXT, -EXT)), place


def _moved(pix, by):
    if by == (0, 0):
        return pix
    return {(x + by[0], y + by[1]): c for (x, y), c in pix.items()}


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def ease(t):
    """The way up to the shoulder and back down: eased at both ends, but less than smooth() -
    its middle would swing the sword past the body in too few poses (a pop)."""
    return 0.5 * (t + gait.smooth(t))


def reach(shoulder, elbow, hand):
    """The elbow nearest the wanted one that the arm's bones allow: no further from the fist
    than the forearm and fist are long, no further from the shoulder than the upper arm (on
    screen a bone may be shorter - it points at the camera - never longer)."""
    l1, l2, l3 = arm.lengths()
    for _ in range(6):
        for anchor, length in ((hand, l2 + l3), (shoulder, l1)):
            d = math.dist(elbow, anchor)
            if d > length:
                elbow = (anchor[0] + (elbow[0] - anchor[0]) * length / d, anchor[1] + (elbow[1] - anchor[1]) * length / d)
    return elbow


def _finish(direction, out):
    pix = rig.composite(out)
    rig.fill_pinholes(pix, anim_idle.standing_pinholes(direction))
    B.drop_specks(pix)
    return pix


# ------------------------------------------------------------------ side views
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
    # the near leg stays in front: the feet only come level (2 px across at most), and a dark
    # far leg popping in front for a pose or two reads as a flicker (checks.py caught it)
    far_on_top = False

    def chest_dx(sy, t, ln=lean):
        """Forward shift of a source row: the lean grows with the height above the belt, the
        counter-turn comes in over the 6 rows above it."""
        return round(ln * max(0.0, belt - sy)) + round(t * (1 - _frac(sy, belt - 6, belt)))

    sh0 = S['shoulder']
    shoulder = (sh0[0] + chest_dx(sh0[1], tw), sh0[1] + d)
    # the carried sword lies on the shoulder plate and the fist holds it there: both move with
    # the plate's top, in the same pose (it rests on the body: nothing in between could lag)
    ride = (chest_dx(PLATE_TOP, tw), d)
    sword, place = sword_pixels(S, b, ride, far=far)
    SWORD_DRAWN[('left' if far else 'right', clip.name, i)] = (sword, place)
    # the arm that holds it: from under the shoulder plate forward to the elbow, the forearm up
    # to the fist on the grip. Carried: one render, moved with the sword. On the way up from /
    # down to the standing pose: the elbow between the approved sprite's (at the chest) and the
    # carry's, the forearm from there to the fist wherever the sword has it
    g1 = carry.fist_screen('right', far)
    e1 = (g1[0] + SIDE_ELBOW[0], g1[1] + SIDE_ELBOW[1])
    if b >= 1.0:
        J, by = arm.pose(sh0, e1, g1), ride
    else:
        e0 = lay.local_to_final(ELBOW0)
        e0 = (e0[0] + chest_dx(e0[1], tw), e0[1] + d)
        elbow = reach(shoulder, _lerp(e0, (e1[0] + ride[0], e1[1] + ride[1]), b), place['grip'])
        J, by = arm.pose(shoulder, elbow, place['grip']), (0, 0)
    ARM_JOINTS[('left' if far else 'right', clip.name, i)] = J

    out = []
    if far:
        # the sword is on the far shoulder: behind the cape, the body and the head. What shows
        # is the blade behind him and, in front of the throat, the fist with the pommel. The
        # forearm and the elbow are behind the chest: only the fist is drawn (lit like the
        # fist the standing pose shows in front of the chest)
        out.extend([sword, _moved(arm.near(arm.render(J, (FW, FH), parts=('fist',))), by)])
    else:
        # the near arm is lit like the approved side view's forearm
        upper = _moved(arm.near(arm.render(J, (FW, FH), parts=('upper',))), by)
        hand = _moved(arm.near(arm.render(J, (FW, FH), parts=('fore', 'fist'))), by)
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

    pauldron = rig.warp(S['pauldron'], body_src, pad=16)
    head = rig.warp(layers['head'], lambda x, y: (x - chest_dx(y - d1, tw1), y - d1), pad=16)
    if far:
        # the near arm hangs free from the shoulder and swings against the near (left) leg
        fa = S['free_arm']
        J = S['free_joints']
        swing = round(SWING_SIDE * s['arm'])
        mx, my = round(shoulder[0] - sh0[0]), round(shoulder[1] - sh0[1])
        pix = {(x + mx, y + my): c for (x, y), c in fa.pix.items()}
        sh = (J['shoulder'][0] + mx, J['shoulder'][1] + my)
        hd = (J['hand'][0] + mx, J['hand'][1] + my)
        out.extend([shear_to(pix, sh, hd, (swing, 0)), pauldron, head])
    else:
        # the sword is on the camera's side of the head; the upper arm comes out from under
        # the shoulder plate; the forearm and the fist are in front of everything
        out.extend([upper, pauldron, head, sword])
        if b >= carry.ON_SHOULDER:
            # the blade lies on the shoulder plate: the plate's rim hides its lower edge
            out.append({q: c for q, c in pauldron.items() if q in sword and q not in head})
        out.append(hand)
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


_fists = {}


def _front_back(direction, clip, i):
    sign = 1 if direction == 'down' else -1       # forward is down-screen in the front view
    S = _layers(direction)
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    s, s1, s2 = clip.at(i), clip.at(i - 1), clip.at(i - 2)
    d, d1, b = s['D'], s1['D'], s['b']
    kind = s['kind']
    strafe = kind.startswith('strafe')
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
    # the carried sword lies on the shoulder plate, which rides on the chest; the blade and the
    # guard are on / behind the shoulder, the hilt and the fist in front of it
    ride = (cx, d + k)
    sword, place = sword_pixels(S, b, ride)
    SWORD_DRAWN[(direction, clip.name, i)] = (sword, place)
    hilt, blade = carry.split(sword, place)
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
        back = carry.blade_back(b)
        out.append(cape)
        if back:
            out.append(blade)       # back over the shoulder: over the cape, behind the plate's rim and the head
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
        out.append(rig.warp(S['pauldron'], body_src, pad=16))
        out.append(head)
        if not back:
            out.append(blade)       # down, forward or up in front of him: in front
        # the sword arm (arm.py): the upper arm comes forward from under the shoulder plate
        # (short on screen), the forearm goes up to the fist in front of the plate; the pommel
        # points at the camera, so the hilt is over the forearm and the fist closes over it
        g1 = carry.fist_screen('front')
        e1 = (g1[0] + FRONT_ELBOW[0], g1[1] + FRONT_ELBOW[1])
        sh0 = S['shoulder']
        if b >= 1.0:
            J, by = arm.pose(sh0, e1, g1), ride
        else:
            e0 = (FRONT_ELBOW0[0] + cx, FRONT_ELBOW0[1] + d + k)
            sh = (sh0[0] + cx, sh0[1] + d + k)
            J = arm.pose(sh, reach(sh, _lerp(e0, (e1[0] + ride[0], e1[1] + ride[1]), b), place['grip']), place['grip'])
            by = (0, 0)
        ARM_JOINTS[('down', clip.name, i)] = J
        # (lit like the fist on the planted sword, not like the other arm in the cape's shadow)
        out.append(_moved(arm.near(arm.render(J, (FW, FH), parts=('upper', 'fore'))), by))
        out.append(hilt)
        out.append(_moved(arm.near(arm.render(J, (FW, FH), parts=('fist',))), by))
    else:
        # the hilt and the fist are in front of him: behind everything here (the fist's top
        # shows over the shoulder); the blade, once it points back over the shoulder, comes
        # towards the camera: in front of everything. Before that (planted, swinging forward and
        # up in front of him) it is behind him too - only what rises over his shoulder shows
        back = carry.blade_back(b)
        out.append(hilt)
        if b >= 1.0:
            if 'back' not in _fists:
                _fists['back'] = arm.fist_only(carry.fist_screen('back'), (0.0, -1.0), (FW, FH))
            out.append(_moved(_fists['back'], ride))
        else:
            out.append(arm.fist_only(place['grip'], (0.0, -1.0), (FW, FH)))
        if not back:
            out.append(blade)
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
        # the sword arm: the approved arm (down to just below the elbow) rides on the chest; the
        # forearm and the hand are in front of him
        out.append(rig.warp(layers['arm'], lambda x, y: (x - cx, y - d - k) if x - cx >= rig.AX else None, pad=16))
        if back:
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
