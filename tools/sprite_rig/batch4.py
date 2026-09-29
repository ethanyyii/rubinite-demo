"""Batch 4 of the player's actions (docs/art-progress.md, "第 4 批"): stagger, knockdown (the
turn-and-pitch-forward fall), launch, getting up, guard break, death. The brief and the user's
decisions of 2026-09-28 are in art-progress.md ("第 4 批：動作簡報", "給下一個視窗的交接筆記").

Timing is in simulation frames (60 Hz) from scripts/combat/player_data.gd and
scripts/state_machines/player_sim.gd (appendix A): stagger 21 (knockback 12 px over 6, hitstop
4); knockdown 48 (knockback 24 px over 6, hitstop 5) then the get-up 30; launch 21 in the air
(64 px) then 36 down and the get-up; guard break 72 (a hit in it knocks down, or launches);
death 90. None of these can be cancelled. A hit does not turn the program's facing: the
reaction is drawn toward where the blow came from (decision 9), and the idle after it faces
the program's way again.

Sheets and rows. The stagger, the guard break and the get-up from the kneel on are drawn in
the four views (rows S / E / N / W; the stagger's row is the view facing the attacker). The
fall, the lying, the launch and the get-up up to the kneel only lie two ways (decisions 8,
10): a row "attacker on the right" and a row "attacker on the left", whose frames come from
different views: attacker on the right = the recoil facing east, the turn facing the camera,
the stumble and the fall facing west (away), lying head to the left (the concept's H as
drawn; batch 0 lying_frame(head_left=True)). The other row is the same the other way (lying
head right is H mirrored, which lying poses may be).

Frame-to-frame limits (decided in the brief, appendix C): the first frame of a hit reaction
is free (hitstop, shake and flash cover it); the fall's steps allow head / torso 8 px (fast,
large, as batch 2 decision 5); the landing and the push up from the prone H to all fours 10
px (the concept's restored H meets the rig's drawing there); every other step 4 px (head,
torso, feet) and 20 px (hands, sword); each action's last frame within 4 px of idle frame 1.
The turn (east -> front -> west) and the get-up's kneel (from the lying side's view to the
program's facing) change views: those steps cannot be measured and are shown for the eye.
"""
import math

import pose_rig as PR
import poses as PS
import batch1 as B1

VIEWS = B1.VIEWS
hand = PS.hand
FACING_VIEW = {'R': 'east', 'L': 'west'}          # row: where the attacker is -> the view facing it
AWAY_VIEW = {'R': 'west', 'L': 'east'}            # the view facing away from it


class Frame(B1.Frame):
    """One rendered frame (batch 1's fields) and the view it was drawn in; lying frames have
    view 'lie' and their parts traced from the concept's H (concept_pose.lying_frame)."""
    canvas = 'small'


# the plume is a 1-2 px strand: bent through a new angle it is re-sampled and can come out with
# 10-20 % more or fewer pixels than the library's (animation-review §4.1), and a strongly bent
# one can leave the 56 px canvas. A frame where it does takes the nearest bend (at most
# PLUME_NUDGE px from the one asked for, in 0.5 px steps) that keeps both - as batch 2's
# readable() turns a blade by the smallest angle that keeps it readable.
PLUME_NUDGE = 2.0


def _plume_ok(r, px):
    import checks as C
    lib = C.counts(r.base.L['plume'].pix)[0]
    n = C.counts(r.pieces_raw.get('plume', {}))[0]
    inside = all(0 <= x < 56 and 0 <= y < 56 for x, y in px)
    return C.within_piece(n, lib) and inside


def fit_plume(view, pose):
    r = PR.rig(view)
    if _plume_ok(r, r.frame(pose, 'small')):
        return pose
    base = pose.get('plume', (0, 0, 0))
    steps = [k * 0.5 for k in range(-int(PLUME_NUDGE * 2), int(PLUME_NUDGE * 2) + 1)]
    for d in sorted(((a, b) for a in steps for b in steps), key=lambda d: (d[0] ** 2 + d[1] ** 2, d)):
        p = dict(pose, plume=(base[0] + d[0], base[1], base[2] + d[1]))
        if _plume_ok(r, r.frame(p, 'small')):
            return p
    return pose


def render(view, pose, name, dur, action, readable=True):
    """A pose drawn by pose_rig in `view` as a Frame (the checks read trace, pieces, debug)."""
    if readable and 'sword' in pose:
        import batch2 as B2
        pose = B2.readable(view, pose)
    if readable:
        pose = fit_plume(view, pose)
    r = PR.rig(view)
    px = r.frame(pose, 'small')
    dbg = dict(r.debug)
    dbg['legs'] = dict(r.debug.get('legs', {}))
    dbg['hands'] = dict(r.debug.get('hands', {}))
    dbg['blade'] = set(r.debug.get('blade', set()))
    return Frame(action, name, dur, view, px, dict(r.trace), {k: dict(v) for k, v in r.pieces.items()},
                 {k: dict(v) for k, v in r.pieces_raw.items()}, dbg, pose)


def _lerp(a, b, t):
    return B1._lerp(a, b, t)


def rest(view):
    return B1.resolve(B1.REST, view)


# ------------------------------------------------------------------ stagger (4 views)
# Per-part plan (animation-review §4.2; F is f1):
# | part | f1 recoil (0-3) | f2 step back (4-12) | f3 upright (13-20) |
# |---|---|---|---|
# | feet | front foot off the floor 3 px (F) | it comes down; the back foot steps back | back under the hips |
# | pelvis | pushed back (the program's 12 px) | settles | idle |
# | torso | leans back 12 deg | 6 deg | 2 deg |
# | arms, sword | flung out, blade up behind | come down | toward the idle grip |
# | head | a beat late going back (tipped less than the body) | goes back now | comes up |
# | cape, plume | thrown forward | swing back | settle |
STAG_T = (0.36, 0.7)                  # f2, f3: of the way from F to the rest stance
STAG_HEAD = ((0, 0, 0), -2.0)         # f1: the head has not gone back yet (offset, tilt)
# west: -2 left the plume touching the helmet round a 15 px pocket of background (a new one: F's
# own -8 had none); -4 is still behind the body and closes it (-4 in front opened a 38 px one)
STAG_HEAD_VIEW = {'west': ((0, 0, 0), -4.0)}
# f2 (the head catching up) in the west view goes 2 deg past F's -8, so it still reads as going on
# back after the body (with f1 at -4 it moved on only 0.3 px)
STAG_F2_HEAD_VIEW = {'west': ((-1, 0, 0), -10.0)}
STAG_STEP = {'R': (-1.6, 0, 0, 'flat'), 'L': (2.0, 0, 0, 'flat')}   # f2: both feet down, the back one a step back
# f2, f3: the elbows drop and tuck (out to the side, down): F's flung-up elbows, lerped, stuck
# out level and drew the front view's sword arm as a dark lump beside the body
STAG_ELBOW = ((0, 0.6, -1), (0, 0.3, -1))
# The blade from F's (up behind the shoulder) to the idle's: f2 and f3 give it in the sagittal
# plane, degrees up from forward, and its lean to the sword side. Straight from F's to the
# idle's it swung out level to the side (in front it left the 56 px canvas). Each view takes the
# shorter way round to its own idle blade (searched: the point moves <= 20 px a step): east,
# south and north tip it forward over the top and down (their idle blade points forward-down);
# west swings it down behind (the west idle blade hangs behind the back in the far hand).
STAG_BLADE = {'south': (45, 15, -0.4), 'east': (60, 0, -0.55), 'north': (60, 0, -0.4), 'west': (165, 195, -0.4)}


def _blade(angle, lean):
    a = math.radians(angle)
    return PR.vnorm((math.cos(a) * 0.92, lean, math.sin(a) * 0.92))


def _stagger(view):
    return B1.resolve(PS.STAGGER, view)


def stagger(view, k):
    s = _stagger(view)
    if k == 0:
        p = dict(s)
        p['head'], p['head_tilt'] = STAG_HEAD_VIEW.get(view, STAG_HEAD)
        return p
    t = STAG_T[k - 1]
    p = B1.lerp_pose(s, rest(view), t, view)
    if k == 1:
        # the head goes back now, a beat after the body; the feet are both down, a step back
        p['head'], p['head_tilt'] = STAG_F2_HEAD_VIEW.get(view, (s.get('head', (0, 0, 0)), s.get('head_tilt', 0.0)))
        p['feet'] = dict(STAG_STEP)
    e = STAG_ELBOW[k - 1]
    p['arms'] = {s_: dict(a, elbow=(e[0], e[1] if s_ == 'L' else -e[1], e[2])) for s_, a in p['arms'].items()}
    a2, a3, lean = STAG_BLADE[view]
    p['sword'] = dict(p['sword'], dir=_blade(a2 if k == 1 else a3, lean))
    return p


STAGGER_FRAMES = [('f1 後仰', 4, lambda v: stagger(v, 0)), ('f2 退一步', 9, lambda v: stagger(v, 1)),
                  ('f3 回正', 8, lambda v: stagger(v, 2))]


# ------------------------------------------------------------------ the knockdown's fall (two rows)
# The user's decision (2026-09-28): turn and pitch forward. Recoil facing the attacker -> turn
# (the front view) -> stumble away and pitch forward -> face down, the head away from the
# attacker: the way the program's 24 px knockback throws the body, and batch 0's lying pose.
# Per-part plan (animation-review §4.2), attacker on the right (the other row mirrors it):
# | part | recoil 0-1 (east) | turn 2-3 (front) | stumble 4-5 (west) | pitch 6-7 (west) | land 8-10 (H) | down 11-47 (H) |
# |---|---|---|---|---|---|---|
# | feet | front foot flung up 4 px | the fall-side foot steps out | both behind the hips, back toe pushing | legs trailing, knees near the floor | legs out behind, still coming down | still |
# | pelvis | pushed back | dropping, swung toward the fall | low 4, 3 px back | low 4, 9 px back | on the floor | still |
# | torso | leans back 18 deg | tips toward the fall 10 deg | pitches forward 24 deg | 42 deg | flat, tipped 4.5 deg head-down | flat |
# | arms, sword | flung out, blade up behind | the sword arm swings toward the fall, the other trails | both thrown forward | reaching for the floor | sword dropped beside | still |
# | head | late: not back yet | still toward the attacker | still tipped back | catches up, tucks | down | still |
# | cape, plume | thrown forward and down | trail toward the attacker | stream back | stream back | still up | settled |
# The pitch and the stumble sit back from the foot anchor (root f < 0): the lying H is 52 px long
# and centred on the anchor, its pelvis ~8 px behind it, so a fall pivoting on the feet would
# have left the head (and the sword) outside the 56 px canvas (the brief's trial poses were
# 3-10 px outside) and jumped 12-13 px at the landing.
# (the plume is thrown forward and down: forward and up, the west view's rose past the canvas)
RECOIL = dict(root=(0, 0, 0), lean=-18, head=(0, 0, 0), head_tilt=-2,
              feet={'R': (-3, 0, 0, 'flat'), 'L': (4, 0, 4, 'swing')},
              arms={'R': hand('R', -4, -13, 4, elbow=(0, -1, 1)), 'L': hand('L', -3, 13, 5, elbow=(0, 1, 1))},
              sword=dict(hand='R', dir=(-0.55, -0.45, 0.7)),
              cape=(5, 0, 2), plume=(2, 0, -2))
# the turn, facing the camera; row R falls toward the screen's left (the character's right)
TURN = {'R': dict(root=(0, -2, -2), lean=6, roll=-10, head=(0, 1.5, 0), head_tilt=0,
                  feet={'R': (0, -3, 1.5, 'flat'), 'L': (0, 1, 0, 'flat')},
                  arms={'R': hand('R', 3, -14, -5, elbow=(0, -1, 0)), 'L': hand('L', -2, 13, 4, elbow=(0, 1, 1))},
                  sword=dict(hand='R', dir=(0.55, -0.45, -0.7)),
                  cape=(0, 4, 1), plume=(0, 3, 0)),
        'L': dict(root=(0, 2, -2), lean=6, roll=10, head=(0, -1.5, 0), head_tilt=0,
                  feet={'L': (0, 3, 1.5, 'flat'), 'R': (0, -1, 0, 'flat')},
                  arms={'R': hand('R', -2, -13, 4, elbow=(0, -1, 1)), 'L': hand('L', 2, 15, -4, elbow=(0, 1, 0))},
                  sword=dict(hand='R', dir=(-0.3, -0.5, 0.8)),
                  cape=(0, -2, 1), plume=(0, -3, 0))}
# the stumble and the pitch were searched together (both rows) so every step keeps its limit: the
# stumble's feet are already behind the hips (pitching forward over them) and the pitch's legs
# trail back, because the lying H's legs are ~30 % longer than the standing ones (its boots end
# up 23 px behind the anchor): with the feet under the hips a step had to jump 12-20 px
STUMBLE = dict(root=(-3, 0, -4), lean=24, head=(-1, 0, 0.5), head_tilt=-6,
               feet={'L': (-10, 0, 0, 'flat'), 'R': (-12, 0, 1, 'toe')},
               arms={'R': hand('R', 7, -8, -4, elbow=(0, -1, -1)), 'L': hand('L', 7, 8, -3, elbow=(0, 1, -1))},
               sword=dict(hand='R', dir=(0.75, -0.3, -0.6)),
               cape=(-3, 0, 3), plume=(-5, 0, 2))
# the pitch: diving onto the floor, 42 deg, legs trailing, arms reaching for the floor. The
# plume's bend is given before the head's 48 deg turn: trailing back it needs to go back-down
# there; bent further (-12, -8) the east plume lost 17 % of its pixels (animation-review §4.1)
PITCH = dict(root=(-9, 0, -4), lean=42, head=(0.5, 0, -0.5), head_tilt=6,
             feet={'L': (-17.5, 0, 2, 'kneel'), 'R': (-16, 0, 3, 'toe')},
             arms={'R': hand('R', 9, -6, -12, elbow=(0, -1, 0)), 'L': hand('L', 9, 6, -12, elbow=(0, 1, 0))},
             sword=dict(hand='R', dir=(0.5, -0.3, -0.8)),
             cape=(-3, 0, 4), plume=(-8, 0, -5))


def fall(row, k, name, dur, action):
    """The fall's frames k = 0..3 (recoil, turn, stumble, pitch) of row R / L."""
    if k == 0:
        v = FACING_VIEW[row]
        return render(v, B1.resolve(RECOIL, v), name, dur, action)
    if k == 1:
        return render('south', TURN[row], name, dur, action)
    return render(AWAY_VIEW[row], STUMBLE if k == 2 else PITCH, name, dur, action)


# ------------------------------------------------------------------ lying and launched (the concept's H)
# concept_pose.lying_frame draws them (batch 0: H restored, head left as drawn, head right its
# mirror). The landing still has its cloth up (lifted a little, more toward the free end); lying,
# it has settled (batch 0's frame itself); launched, the body tips head-down and the cloth
# streams up (batch 0's), and its second frame only flutters the cloth (the body is the same).
LAND_LIFT = (0.5, 2.0)                # the landing's cloth: px up at the head end, extra toward the free end
# the landing tips head-down a little: pitching forward (or slamming down from the launch) the
# chest and head land first and the legs come down after. Flat, the launch's 14 deg tilt put the
# feet 10.7 px above the lying ones in one step (landing limit 10); 4.5 deg splits it (<= 4 after)
LAND_TILT = 4.5
AIR_FLUTTER = 1.0                     # the launch's second frame: a wave through the streaming cloth, px


def _lift_land(n):
    a, b = LAND_LIFT
    return lambda x: int(round(a + b * x / max(n - 1, 1)))


def _lift_air(n, k):
    base = lambda x: 1 + 3 * x / max(n - 1, 1)
    if k == 0:
        return lambda x: int(round(base(x)))
    return lambda x: int(round(base(x) + AIR_FLUTTER * math.sin(x / max(n - 1, 1) * 2 * math.pi * 1.5 + 1.2)))


def lie(row, kind, name, dur, action):
    """A lying / launched frame of row R (attacker on the right: head to the left) or L, as a
    Frame whose parts come from the H they were restored from (concept_pose.lie_part)."""
    import concept_pose as CP
    body, cloth = CP.lying_parts()
    n = max(x for x, _ in list(body) + list(cloth)) + 1
    labels = {}
    hl = row == 'R'
    if kind == 'down':
        px = CP.lying_frame(head_left=hl, labels=labels)
    elif kind == 'land':
        px = CP.lying_frame(head_left=hl, lift=_lift_land(n), labels=labels, tilt=LAND_TILT)
    else:
        px = CP.lying_frame(head_left=hl, airborne=True, lift=_lift_air(n, 0 if kind == 'air1' else 1), labels=labels)
    pieces = {}
    for q, part in labels.items():
        if q in px:
            pieces.setdefault(part, {})[q] = px[q]
    legs = sorted(pieces.get('legs', {}), key=lambda q: q[0] if hl else -q[0])
    # the ankles: the boots at the legs' far end (the last 6 columns); the hip at their near end
    far = [q for q in legs if abs(q[0] - legs[-1][0]) < 6]
    near = [q for q in legs if abs(q[0] - legs[0][0]) < 4]
    cen = lambda pts: (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    ankle, hip = cen(far), cen(near)
    dbg = {'legs': {'near': (hip, hip, ankle), 'far': (hip, hip, ankle)}, 'pelvis': hip, 'hands': {}, 'blade': set()}
    sw = list(pieces.get('sword', {}))
    if sw:
        # the dropped sword points toward the head: its point is its end on the head's side
        dbg['tip'] = min(sw, key=lambda q: q[0]) if hl else max(sw, key=lambda q: q[0])
    f = Frame(action, name, dur, 'lie', px, dict(labels), pieces, {k: dict(v) for k, v in pieces.items()}, dbg, None)
    f.row, f.kind = row, kind
    return f


# ------------------------------------------------------------------ getting up
# Per-part plan (animation-review §4.2):
# | part | all fours (lying side) | rise 1-4 (lying side) | kneel (program's facing) | stand 1-2 |
# |---|---|---|---|---|
# | feet | both knees down, shins trailing | the front foot comes forward under the body | one knee down (G) | rise, under the hips |
# | pelvis | up off the floor, back | comes forward over the knee | 60 % of the idle's height | up |
# | torso | pushed up, 45 deg | straightens | 14 deg | upright |
# | arms, sword | hands on the floor, the right one on the sword again | push off, the sword comes round to plant | both hands on the pommel | toward the idle grip |
# | head | lifts a beat late | a beat late | bowed | comes up |
# | cape, plume | slides off the back | settles | hangs | settles |
# Four rises, not the brief's three: the front foot comes 16-18 px from the trailing shins to the
# kneel, over the 4 px a step in three (the frame count is a technical choice; 30 sim frames in
# eight frames of 3-5). The kneel's front foot is 4 px nearer than the guard break's (batch 0
# KNEEL; left as approved there): with KNEEL's the step was still 4.4-5.3 px.
ALLFOURS = dict(root=(-10, 0, -5), lean=45, head=(1, 0, -1), head_tilt=5,
                feet={'L': (-16, 0, 0, 'kneel'), 'R': (-12, 0, 0, 'kneel')},
                arms={'R': hand('R', 7, -7, -14, elbow=(0, -1, 0)), 'L': hand('L', 7, 7, -14, elbow=(0, 1, 0))},
                sword=dict(hand='R', dir=(0.9, -0.3, -0.3)), cape=(-1, 0, 2), plume=(-8, 0, -5))
GETUP_KNEEL = dict(PS.KNEEL, feet={'R': (-5, 0, 0, 'kneel'), 'L': (0, 0, 0, 'flat')})
RISE_T = (0.24, 0.47, 0.7, 0.9)       # rise 1-4: of the way from all fours to the kneel (the front
                                      # foot 16 px: <= 4 a step). A part turned through a new angle is
                                      # re-sampled: at 0.25 the east scarf came out 5 px over its 22, at
                                      # 0.2-0.22 the east helmet 5 highlights over its 17 (checks.py)
RISE_HEAD = 0.12                      # the head that much behind the body
STAND_T = (0.35, 0.7)                 # stand 1-2 (and the guard break's push up, half stand): kneel -> rest
STAND_HEAD = 0.1


def _lag(a, b, t, lag, view):
    """a -> b by t, the head `lag` behind (it follows the body)."""
    p = B1.lerp_pose(a, b, t, view)
    th = max(0.0, t - lag)
    p['head'] = _lerp(a.get('head', (0, 0, 0)), b.get('head', (0, 0, 0)), th)
    p['head_tilt'] = a.get('head_tilt', 0.0) + (b.get('head_tilt', 0.0) - a.get('head_tilt', 0.0)) * th
    return p


RISE_PLUME = 0.25                     # the plume's end that much behind (at the body's pace the east
                                      # plume swung forward past the canvas on rise 1-3)


def rise(row, k, name, dur, action):
    v = AWAY_VIEW[row]
    a, b = B1.resolve(ALLFOURS, v), B1.resolve(GETUP_KNEEL, v)
    if k == 0:
        pose = a
    else:
        t = RISE_T[k - 1]
        pose = _lag(a, b, t, RISE_HEAD, v)
        pose['plume'] = _lerp(a.get('plume', (0, 0, 0)), b.get('plume', (0, 0, 0)), max(0.0, t - RISE_PLUME))
    return render(v, pose, name, dur, action)


def stand(view, kneel, k):
    return _lag(B1.resolve(kneel, view), rest(view), STAND_T[k], STAND_HEAD, view)


# ------------------------------------------------------------------ guard break (4 views)
# From the guard (the block that emptied the posture), the knees give (two frames: guard ->
# kneel moves the side views' head 8.1-8.3 px), one knee down leaning on the planted sword
# (batch 0 KNEEL), then a woozy sway: four phases x 6 sim frames (12-59, two rounds), the body
# 1 px to and fro (side to side from the front / back; forward and back from the side, where
# side to side is depth and does not show), the head a phase late, the cape's end a phase after
# the body and the plume's a phase after the head (as the batch 1 breath); then it pushes up (60-65) and half stands (66-71). The sword stays planted while the body
# sways over it (the fists slide on the pommel).
# | part | knees give 1-2 | kneel | sway 1-4 | push up, half stand |
# |---|---|---|---|---|
# | feet | the back knee drops | one knee down | still | rise under the hips |
# | pelvis | drops | 4 px down | 1 px to and fro | up |
# | torso | slumps | 14 deg | rides the pelvis | straightens |
# | arms, sword | the guard's grip slides down onto the pommel, the point to the floor | on the pommel, planted | still (planted) | toward the idle grip |
# | head | a beat late | bowed | a phase late | comes up |
# | cape, plume | settle | hang | ends a phase after the head | settle |
KNEE_T = (0.35, 0.68)
SWAY = (0, 1, 0, -1)                  # px along the sway axis, phase 1-4
SWAY_HOLD = 6
# px a cloth end swings per px of lag: the back and west capes are wide, and at 1 px their far
# quarter hardly moved (the lag did not show, checks.py); 2 px in front and east put the cape
# 1 px outside the canvas, and 1 px shows the lag there
SWAY_CLOTH = {'south': 1.0, 'east': 1.0, 'north': 2.0, 'west': 2.0}


def _guard(view):
    return B1.resolve(PS.GUARD, view)


def _kneel(view):
    return B1.resolve(PS.KNEEL, view)


KNEE_PLUME_LAG = 0.3                  # the plume's end a step behind the body (at the body's pace the
                                      # east plume, bent with the lean, came out 14 % over its pixels)


def knees(view, k):
    a, b, t = _guard(view), _kneel(view), KNEE_T[k]
    p = _lag(a, b, t, 0.15, view)
    p['plume'] = _lerp(a.get('plume', (0, 0, 0)), b.get('plume', (0, 0, 0)), max(0.0, t - KNEE_PLUME_LAG))
    return p


def sway(view, i):
    side = view in ('east', 'west')
    axis = (1, 0, 0) if side else (0, 1, 0)
    b, h, c = SWAY[i], SWAY[(i - 1) % 4], SWAY[(i - 2) % 4]   # body, head, plume end
    p = dict(_kneel(view))
    p['root'] = B1._add(p.get('root', (0, 0, 0)), tuple(b * a for a in axis))
    p['head'] = B1._add(p.get('head', (0, 0, 0)), tuple((h - b) * a for a in axis))
    # as the batch 1 breath: the cape's end a phase after the body, the plume's a phase after
    # the head (its root)
    p['cape'] = B1._add(p.get('cape', (0, 0, 0)), tuple(SWAY_CLOTH[view] * (h - b) * a for a in axis))
    p['plume'] = B1._add(p.get('plume', (0, 0, 0)), tuple(SWAY_CLOTH[view] * (c - h) * a for a in axis))
    dx, dy = PR.proj(view, tuple(b * a for a in axis))
    p['sword'] = dict(p['sword'], planted=(-dx, -dy))
    return p


# ------------------------------------------------------------------ actions
# four-view actions: (name, sim frames, builder(view) -> pose)
VIEW_ACTIONS = {
    'stagger': STAGGER_FRAMES,
    'guard_break': [('膝蓋一軟 1', 3, lambda v: knees(v, 0)), ('膝蓋一軟 2', 3, lambda v: knees(v, 1)),
                    ('單膝跪地', 6, _kneel)] +
                   [(f'搖晃 {i + 1}', SWAY_HOLD, (lambda v, i=i: sway(v, i))) for i in range(4)] +
                   [('撐起', 6, lambda v: stand(v, PS.KNEEL, 0)), ('半站', 6, lambda v: stand(v, PS.KNEEL, 1))],
    'getup': [('跪姿', 4, lambda v: B1.resolve(GETUP_KNEEL, v)), ('站起 1', 4, lambda v: stand(v, GETUP_KNEEL, 0)),
              ('站起 2', 5, lambda v: stand(v, GETUP_KNEEL, 1))],
}
# two-row actions (R: the attacker on the right, L: on the left): (name, sim frames, builder(row, name, dur, action) -> Frame)
ROW_ACTIONS = {
    'knockdown': [('後仰', 2, lambda r, n, d, a: fall(r, 0, n, d, a)), ('轉身', 2, lambda r, n, d, a: fall(r, 1, n, d, a)),
                  ('踉蹌', 2, lambda r, n, d, a: fall(r, 2, n, d, a)), ('撲倒', 2, lambda r, n, d, a: fall(r, 3, n, d, a)),
                  ('著地', 3, lambda r, n, d, a: lie(r, 'land', n, d, a)), ('趴著', 37, lambda r, n, d, a: lie(r, 'down', n, d, a))],
    'launch': [('空中 1', 4, lambda r, n, d, a: lie(r, 'air1', n, d, a)), ('空中 2', 4, lambda r, n, d, a: lie(r, 'air2', n, d, a))],
    'getup_floor': [('手膝撐地', 4, lambda r, n, d, a: rise(r, 0, n, d, a))] +
                   [(f'起身 {k}', d_, (lambda r, n, d, a, k=k: rise(r, k, n, d, a))) for k, d_ in ((1, 3), (2, 3), (3, 3), (4, 4))],
}
# timing tables (sim frames) over the frames above (appendix A, B)
LAUNCH_AIR = 21                       # the two air frames alternate every 4 sim frames
LAUNCH_DOWN = (('著地', 3), ('趴著', 33))    # then the knockdown's landing and lying: 36
DEATH = (('後仰', 4), ('轉身', 4), ('踉蹌', 4), ('撲倒', 4), ('著地', 6), ('趴著', 68))   # 90; the fade is the program's
TITLES = {'stagger': '踉蹌（朝攻擊來源；f1 後仰、f2 退一步、f3 回正）',
          'guard_break': '架勢崩潰（膝蓋一軟 1–2、單膝跪地、搖晃 1–4、撐起、半站）',
          'getup': '起身後段（跪姿起換回程式的面向：跪姿、站起 1–2）',
          'knockdown': '倒地（後仰、轉身、踉蹌、撲倒、著地、趴著）',
          'launch': '擊飛（空中 1、2 交替，接倒地的著地、趴著）',
          'getup_floor': '起身前段（躺的那一側：手膝撐地、起身 1–4）'}
ROWS = ('R', 'L')
ROW_ZH = {'R': '攻擊者在右', 'L': '攻擊者在左'}

_CACHE = {}


def frames(action, key):
    """Frames of a four-view action for a view, or of a two-row action for a row ('R' / 'L')."""
    ck = (action, key)
    if ck in _CACHE:
        return _CACHE[ck]
    if action in VIEW_ACTIONS:
        out = [render(key, build(key), name, dur, action) for name, dur, build in VIEW_ACTIONS[action]]
    else:
        out = [build(key, name, dur, action) for name, dur, build in ROW_ACTIONS[action]]
    _CACHE[ck] = out
    return out


def named(action, key, name):
    return next(f for f in frames(action, key) if f.name == name)
