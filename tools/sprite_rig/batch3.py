"""Batch 3 of the player's actions (docs/art-progress.md, "第 3 批"): charge (with its slow legs),
thrust, execution, dodge (dash, backstep, their stops), run, and the locked walk's backward
and sideways cycles. Decisions of 2026-09-28 (the brief's items 1-10) are cited as "decision n".

Timing is in simulation frames (60 Hz) from scripts/combat/player_data.gd and
scripts/state_machines/player_sim.gd (docs/art-progress.md appendix A); the frame tables are
appendix B.

Movement (decision 1): the program moves the character every sim frame; a foot on the floor
does not slide when each sprite frame is held for (how far that foot moves back per frame) /
(how far the program moves per sim frame) sim frames, at least 2. The run's frames are drawn
for that: its stance foot moves back RUN_STEP px a frame, which is the run's 160 px/s at 2 sim
frames a frame. The user compared 2 / 3 / 4 (export_batch3.py) and chose 2 (2026-09-28).

Per-part plan of the run (animation-review §4.2; side view, near foot = phase 0):

| part | contact (0, 4) | down (1, 5) | passing (2, 6) | flight (3, 7) |
|---|---|---|---|---|
| stance foot | heel lands 8 px ahead | flat, under the knee | flat, behind | pushed off the toe, 1 px up |
| swing foot | kicked up behind | knee drives forward | reaching | reaching forward, about to land |
| pelvis | mid | lowest (+1 px) | mid | highest (-1 px) |
| torso | leans 12 deg throughout | | | |
| arms | against the legs: the off arm swings 5 px, the sword arm 2 px (it carries the sword low behind) | | | |
| sword | low behind the sword side, rides the fist | | | |
| head | the pelvis's height one frame late | | | |
| cape, plume | stream back; each step a small wave that lags the bob | | | |
"""
import math

import pose_rig as PR
import poses as PS
import batch1 as B1

VIEWS = B1.VIEWS
FWD_SCREEN = {'east': (1, 0), 'west': (-1, 0), 'south': (0, 1), 'north': (0, -1)}

# ------------------------------------------------------------------ the run (decision 1, 7, 9)
RUN_SPEED = 160.0                     # player_data.gd SPEED_RUN, px/s
RUN_N = 8
RUN_STEP = RUN_SPEED / 60 * 2         # 5.33 px: stance foot back per frame, no slide at 2 sim frames
# near foot, phase i: (px ahead of its own hip along the facing, lift px, boot state). Stance
# 0-2 moves back RUN_STEP a frame; 3 and 7 are the two flights (both feet off the floor).
# Places are from the pelvis's centre (the side views' near hip sits 1 px forward of it, the far
# one 1 px back): both contacts then show the same stride, 14.5 px.
_C = 8.0
RUN_FOOT = [(_C, 0, 'heel'), (_C - RUN_STEP, 0, 'flat'), (_C - 2 * RUN_STEP, 0, 'flat'),
            (-7.5, 1.0, 'toe'), (-6.5, 4.0, 'swing'), (-1.0, 5.0, 'swing'), (4.0, 3.5, 'swing'),
            (8.5, 1.5, 'reach')]
# the west view's near boot (the library's side_left), pitched back onto its heel, ends with its
# sole 1 px off the floor (east, and the west far boot, do not): that foot sits 1 px lower there
HEEL_SINK = {('west', 'near'): 1.0}
RUN_BOB = (0, 1, 0, -1, 0, 1, 0, -1)  # screen px, + = down: lowest on the loading frame, highest in flight
RUN_ROOT = (1.0, 0.0, -1.0)
RUN_LEAN = 12
RUN_R = (-5.0, -9.5, -7.0)            # the sword hand (batch 0 RUN), low behind the hip
RUN_L = (3.0, 8.5, -5.0)
RUN_SWING = {'R': (2.0, 0.6), 'L': (5.0, 1.5)}   # (fore-aft px, rise px) of each hand's swing


def run_feet(view, i, root):
    """Feet of frame i in the rig's units: side views give each foot's place from its own
    hip (pose_rig SIDE_REST_DX is the idle stance the rig measures from; the root moves the
    hips, not the feet), front / back views a depth offset from the walk stance."""
    v = PR.VIEWS[view]
    rf = root[0]
    out = {}
    if v['kind'] == 'side':
        near = v['near']
        far = 'L' if near == 'R' else 'R'
        for s_, k, hip, which in ((near, i, 1.0, 'near'), (far, (i + 4) % RUN_N, -1.0, 'far')):
            dx, lift, state = RUN_FOOT[k]
            if state == 'heel':
                lift -= HEEL_SINK.get((view, which), 0.0)
            out[s_] = (dx - hip - PR.SIDE_REST_DX[view][s_] + rf, 0.0, lift, state)
        return out
    # front / back: the leg under the character's right is 'near' in phase with the east view
    for s_, k in (('R', i), ('L', (i + 4) % RUN_N)):
        dx, lift, state = RUN_FOOT[k]
        out[s_] = (dx + rf, 0.0, lift, state)
    return out


def run_pose(view, i):
    phi = 2 * math.pi * i / RUN_N
    bob, prev = RUN_BOB[i], RUN_BOB[(i - 1) % RUN_N]
    root = (RUN_ROOT[0], RUN_ROOT[1], RUN_ROOT[2] - bob)
    arms = {}
    for s_, base in (('R', RUN_R), ('L', RUN_L)):
        amp, rise = RUN_SWING[s_]
        # the right foot is ahead at phase 0: the right hand is back then, the left forward
        c = math.cos(phi) * (-1 if s_ == 'R' else 1)
        arms[s_] = PS.hand(s_, base[0] + amp * c, base[1], base[2] + rise * c,
                           elbow=(-1, -0.3, -1) if s_ == 'R' else (-1, 0.3, -1))
    p = dict(root=root, lean=RUN_LEAN, feet=run_feet(view, i, root), arms=arms,
             sword=dict(hand='R', dir=(-0.7, -0.35, -0.6)),
             head=(0, 0, bob - prev),
             cape=(-5 - 0.8 * math.sin(2 * phi - 1.2), 0, 2 + 0.5 * math.sin(2 * phi - 1.8)),
             plume=(-4, 0, 1 + 0.8 * math.sin(2 * phi - 2.0)))
    if view in ('south', 'north'):
        # the cape seen from the front / back: its wave is sideways (walk_pose does the same)
        p['cape'] = (-5, 0.8 * math.sin(2 * phi - 1.2), 2)
        p['plume'] = (-4, 0.8 * math.sin(2 * phi - 1.6), 1)
        p['cape_lowered_add'] = prev - bob
    return B1.resolve(p, view)


# ---- starting and stopping (decision 7; more frames than the brief's one each, see below)
# From standing, the sword swings 41 px to the run's (east): two steps of <= 20 cannot cover it,
# so the start is two frames (2 sim frames each, inside the program's 5-frame acceleration),
# entering the cycle at the phase closest to them. Stopping, the run's 12 deg lean and 14 px
# stride need three steps to the stance: stop 1 (two versions, one for each foot leading),
# stop 2 and 3 (2 sim frames each; the program stops in 4, so the last shows in the idle and any
# input cuts it). When the stick is let go the cycle goes on (the program is still slowing
# down: 4 sim frames = 2 frames) until a frame that can step into a stop 1; RUN_STOP_FROM says
# which: 'A' / 'B', or None = play the next run frame first. Searched (batch 2's way) so every
# step keeps head / torso / feet <= 4 px (the run's own frames: feet 6) and hands / sword <= 20.
RUN_START = {'south': (0, 0.25, 0.6), 'east': (5, 0.25, 0.75), 'north': (3, 0.3, 0.6), 'west': (1, 0.3, 0.65)}
RUN_STOP = {'south': (1, 0.25, 0.55, 0.8), 'east': (1, 0.25, 0.55, 0.8), 'north': (0, 0.25, 0.55, 0.8),
            'west': (1, 0.25, 0.55, 0.8)}


def run_start(view, n):
    k0, a, b = RUN_START[view]
    return B1.lerp_pose(B1.resolve(B1.REST, view), run_pose(view, k0), (a, b)[n], view)


def run_stop(view, which):
    k, t1, t2, t3 = RUN_STOP[view]
    rest = B1.resolve(B1.REST, view)
    if which in ('A', 'B'):
        return B1.lerp_pose(run_pose(view, k if which == 'A' else k + 4), rest, t1, view)
    mid = B1.lerp_pose(run_pose(view, k), run_pose(view, k + 4), 0.5, view)
    return B1.lerp_pose(mid, rest, t2 if which == 2 else t3, view)


_STOP_FROM = {}


def run_stop_from(view):
    """For each run frame (0-7): the stop 1 it can step into ('A' / 'B'), or None."""
    if view not in _STOP_FROM:
        import checks as C
        fr = {f.name: f for f in frames('run', view)}
        pt = lambda f: C._Pt(f, small=True)
        lim = lambda m: (all(m[k] is None or m[k] <= 4 + 1e-6 for k in ('head', 'torso')) and
                         (m['feet'] is None or m['feet'] <= 6 + 1e-6) and
                         all(m[k] is None or m[k] <= 20 + 1e-6 for k in ('hands', 'sword')))
        out = []
        for j in range(RUN_N):
            opts = [w for w in ('A', 'B') if lim(C.screen_moves(pt(fr[f'run {j + 1}']), pt(fr[f'停步 1{w}'])))]
            out.append(opts[0] if opts else None)
        _STOP_FROM[view] = out
    return _STOP_FROM[view]


# ------------------------------------------------------------------ the charge (decisions 2, 3, 6)
# Per-part plan (animation-review §4.2):
# | part | in (0-1, 2-3) | hold (4 on, four phases x 3 sim frames) | out (released early, idle) |
# |---|---|---|---|
# | feet | step into the wide stance, back foot loaded | still | back under the hips |
# | pelvis | drops toward 4 px | tremble 1 px | rises |
# | torso | coils (front / back: tilts toward the off hand) | rides the pelvis | uncoils |
# | sword hand | draws back to the hip, blade levels | still | lowers to the idle grip |
# | off hand | reaches out to aim | still | drops to the side |
# | head | follows the body | a phase late | leads (looks up first) |
# | cape, plume | settle behind | ends a phase late | settle |
CHARGE_HOLD = 3                       # sim frames a phase (decision 3: one cycle 12 frames)
CHARGE_WALK_SWAY = 0.5                # the low stance flares the cape already: 0.8 swung it past its detail count
# 2026-09-28 fix (the user: walking, the east feet stuck together; the west legs a "worm"): the
# charge's feet are 12 px apart, and the slow legs' step (each foot +-3 px, the feet in turn) swung
# that between 6 px (feet together) and 18 (legs stretched past their length). The step length
# comes from the speed and the cadence, so forward / backward the charge walks its own shorter,
# quicker step: six frames of 2 sim frames, the planted foot back 1.33 px a frame (40 px/s: no
# slide), each foot +-2 px, the feet 8-16 px apart. Sidesteps keep the slow legs'.
# Second fix (2026-09-28): the hold's stance is 9 px now (legs within reach, see poses.CHARGE).
# Then the user: the feet move too fast - six frames of 2 sim frames is a 0.2 s cycle, quicker than
# the plain walk's 0.27 s at 100 px/s, for a body moving at 40: a shuffle. Now the charge walks like
# a walk, slowly: eight frames of 3 sim frames (0.4 s, the heal walk's cadence), the planted foot
# back 2 px a frame (40 px/s: no slide), so each foot travels 8 px a cycle and the feet pass under
# the body in turn (a staggered stance cannot keep the front foot in front at this cadence: the feet
# would have to open to 25 px). Each foot swings about a place 4 px in from its hold place, so the
# contact frame (fwd 1) is the hold's own stance: starting and stopping never jump the feet, and no
# foot ever reaches further from the hip than in the hold (the legs keep their shape).
CW_N = 8
CW_HOLD = 3
CW_FOOT = (4.0, 2.0, 0.0, -2.0, -4.0, -2.0, 0.0, 2.0)   # a foot from its walking place, px (planted 0-4)
CW_LIFT = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.5, 1.0)      # off the floor while it swings (5-7)
CW_IN = 4.0                                             # walking place: px in from the hold's place
# walking, both knees nearly straight: the hold's bent front knee (poses._CHARGE_KNEES) rose level
# with the hip when that foot reached ahead (the table shape again, 2026-09-28 second fix)
CW_KNEES = {'L': 1.03, 'R': 1.03}
CW_BOB = (0, 1, 0, 0, 0, 1, 0, 0)                      # the pelvis 1 px down as each foot takes the weight
# sidesteps: four frames of 3 sim frames (0.2 s, the heal's sidestep; before, 2-3 sim frames: 0.15 s).
# The body crosses 8 px a cycle, so each foot steps 8 px: a slower step would open the feet past
# 10 px each side of their place (from the front the legs, ~4 px tall, would lie flat). Each foot
# plants for two frames (2 px a frame toward the trailing side, as the body moves: no slide) and
# swings for two, 1 px up: the feet 4 px nearer / further apart than in the hold, never crossing.
CW_SIDE_HOLD = 3
CW_SIDE_FB = [(-2, 0, 2, 0), (0, 1, 0, 0), (2, 0, -2, 0), (0, 0, 0, 1)]   # (L lateral, L lift, R lateral, R lift)
CW_SIDE_SIDE = [(0, 0), (1, 0), (0, 0), (0, 1)]                          # side views: (near lift, far lift)


def charge_walk_pose(view, i, rev=False):
    """Frame i of the charge's own forward step (rev: backward, made on its own with the lags
    recomputed, batch 3 decision 8). The upper body is the hold's, riding the pelvis rigidly."""
    lag = -1 if rev else 1
    i = (-i) % CW_N if rev else i
    upper = _charge(view)
    st = upper['feet']
    v = PR.VIEWS[view]
    feet = {}
    for s_, k in (('L', i), ('R', (i + CW_N // 2) % CW_N)):     # the left foot leads in the hold
        f0, l0, lift0, state = st[s_]
        lift = CW_LIFT[k]
        inward = -CW_IN if s_ == 'L' else CW_IN
        feet[s_] = (f0 + inward + CW_FOOT[k], l0, lift0 + lift, 'swing' if lift and v['kind'] == 'side' else state)
    bob, prev = CW_BOB[i], CW_BOB[(i - lag) % CW_N]
    phi = 2 * math.pi * i / CW_N
    p = dict(upper)
    p['feet'] = feet
    p['soft_knee'] = CW_KNEES
    p['root'] = B1._add(p.get('root', (0, 0, 0)), (0, 0, -bob))
    p['head'] = B1._add(p.get('head', (0, 0, 0)), (0, 0, bob - prev))
    sw = CHARGE_WALK_SWAY
    if view in ('east', 'west'):
        p['cape'] = B1._add(p.get('cape', (0, 0, 0)), (-sw * math.sin(2 * phi - lag * 1.2), 0, 0))
        p['plume'] = B1._add(p.get('plume', (0, 0, 0)), (0, 0, sw * math.sin(2 * phi - lag * 2.0)))
    else:
        p['cape'] = B1._add(p.get('cape', (0, 0, 0)), (0, sw * math.sin(phi - lag * 1.0), 0))
        p['cape_lowered_add'] = p.get('cape_lowered_add', 0.0) + (prev - bob)
        p['plume'] = B1._add(p.get('plume', (0, 0, 0)), (0, sw * math.sin(phi - lag * 1.6), 0))
    return p


def charge_side_pose(view, i, rev=False):
    """Sidestep frame i (rev: the other way, made on its own): the slow legs' step, wider and slower
    (CW_SIDE_*), on straight knees."""
    p = B1.walk_pose(_charge(view), view, 'side', i, rev=rev, sway=CHARGE_WALK_SWAY,
                     tables=(CW_SIDE_FB, CW_SIDE_SIDE))
    return dict(p, soft_knee=CW_KNEES)


def charge_walk():
    side = [(f'side {i + 1}', CW_SIDE_HOLD, (lambda v, i=i: charge_side_pose(v, i))) for i in range(B1.N_SIDE)]
    rside = [(f'rside {i + 1}', CW_SIDE_HOLD, (lambda v, i=i: charge_side_pose(v, i, rev=True))) for i in range(B1.N_SIDE)]
    fwd = [(f'fwd {i + 1}', CW_HOLD, (lambda v, i=i: charge_walk_pose(v, i))) for i in range(CW_N)]
    back = [(f'back {i + 1}', CW_HOLD, (lambda v, i=i: charge_walk_pose(v, i, rev=True))) for i in range(CW_N)]
    return fwd + side + back + rside


def _charge(view):
    return B1.resolve(PS.CHARGE, view)


def charge_in(view, t, th, tl=None):
    """0-3: the body t of the way from the rest stance into the charge, the head th (behind),
    the off hand tl (it reaches out to aim first: from the guard, where it held the grip at
    the chest, a frame at the body's pace left it 20.1 px to travel, over the hands' 20)."""
    rest, ch = B1.resolve(B1.REST, view), _charge(view)
    p = B1.lerp_pose(rest, ch, t, view)
    p['head'] = B1._lerp((0, 0, 0), ch.get('head', (0, 0, 0)), th)
    if tl is not None:
        p['arms'] = dict(p['arms'], L=B1.lerp_pose(rest, ch, tl, view)['arms']['L'])
    return _readable(view, p)


def _readable(view, p):
    """In and out may turn the blade a little to keep it >= 3:1 (batch 2's readable()): the hold
    and its walk may not (their upper body stays pixel for pixel)."""
    import batch2 as B2
    return B2.readable(view, p)


def charge_out(view, t, th):
    """Released before it was full (decision 6): back to the rest stance; the head th of the
    way (it leads)."""
    rest, ch = B1.resolve(B1.REST, view), _charge(view)
    p = B1.lerp_pose(ch, rest, t, view)
    p['head'] = B1._lerp(ch.get('head', (0, 0, 0)), (0, 0, 0), th)
    return _readable(view, p)


CHARGE_IN_T = ((0.35, 0.25, 0.7), (0.7, 0.55, 0.9))   # (body, head, off hand): two frames of 2 (the front foot steps 10 px)
# 2026-09-28 fix (the charge leans 16 deg over its back foot now): at the body's 0.35 the back view's
# head moved 4.4 px out of the hold; searched again
CHARGE_OUT_T = ((0.3, 0.4), (0.65, 0.75))


# ------------------------------------------------------------------ thrust and execution (decision 5)
# The program carries the character 6 px a sim frame through 0-11 (the thrust; the execution
# closes in at <= 3.2 px a frame), every frame: the picture moves with it (no catching up).
# Per-part plan (animation-review §4.2; D1 is f2):
# | part | f1 push (0-1) | f2 lunge (2-11) | f3 hold (12-15, 16-20) | f4 draw back (21-31) | f5 stance (32-41) |
# |---|---|---|---|---|---|
# | feet | back foot pushes, front foot starts out | long lunge 23 px, back heel up | planted | front foot comes back | idle stance |
# | pelvis | forward, low | 4 px low, 4 px forward | still | rises, back | idle |
# | torso | leans in | leans 24 deg | still | straightens | upright |
# | sword hand | drives forward | arm out, blade level | still | draws the blade back | idle grip |
# | off hand | swings back | back for balance | still | comes forward | at the side |
# | head | a frame behind the body | catches up | 1 px on, then back (the stop) | a frame late | a frame late |
# | cape, plume | still behind the charge | streaming back | thrown forward, then settling | settle | settle |
THRUST_F1_T = (0.5, 0.5)              # (body, head): charge hold -> f1 -> f2, decision 5's 8 px (searched again
                                      # for the 2026-09-28 charge: 7.9 px the larger step)
# the execution's own two starts from the rest stance: (body, head, sword). The feet travel
# 10 px to the lunge, so the body takes even thirds; the sword swings ahead of it in the first
# frame, where an attack's sword is free (batch 2 decision 3): the west library sword hangs
# behind the back, and at the body's pace it swung 25 px between the two starts
EXEC_T = ((0.34, 0.25, 0.75), (0.67, 0.55, 0.92))
THRUST_BACK_T = (0.2, 0.4, 0.6, 0.8)  # f4a, f4b, f5a, f5b toward the rest stance


def _thrust(view):
    return B1.resolve(PS.THRUST, view)


def thrust_push(view):
    ch, th = _charge(view), _thrust(view)
    t, tt = THRUST_F1_T
    p = B1.lerp_pose(ch, th, t, view)
    p['head'] = B1._lerp(ch.get('head', (0, 0, 0)), th.get('head', (0, 0, 0)), tt)
    # the cloth has not caught the lunge yet: still where the charge held it
    p['cape'], p['plume'] = ch.get('cape', (0, 0, 0)), ch.get('plume', (0, 0, 0))
    return p


def thrust_hold(view, k):
    """f3: the body stops (the lunge ends or the blade hits); the head goes on 1 px and comes
    back, the cloth is thrown forward past its streaming place and settles (k = 0, 1)."""
    p = dict(_thrust(view))
    side = view in ('east', 'west')
    if k == 0:
        p['head'] = B1._add(p.get('head', (0, 0, 0)), (1, 0, 0))
        # front / back: depth does not show, so the throw is sideways, toward the cape's side
        p['cape'], p['plume'] = ((-2, 0, 2), (0, 0, 1)) if side else ((-6, 1.5, 5), (-2, 1.2, 1))
    else:
        p['cape'], p['plume'] = ((-3, 0, 3), (-1, 0, 1)) if side else ((-6, 0.5, 5), (-2, 0.4, 1))
    return p


def thrust_back(view, t):
    rest, th = B1.resolve(B1.REST, view), thrust_hold(view, 1)
    p = B1.lerp_pose(th, rest, t, view)
    # the head a little behind the body on the way up; the cloth, which settled through the
    # hold, ahead of it (at the body's pace the west cape still lay on the back leg in f4 and
    # closed a pocket of background there)
    p['head'] = B1._lerp(th.get('head', (0, 0, 0)), (0, 0, 0), max(0.0, t - 0.1))
    tc = min(1.0, t + 0.3)
    p['cape'] = B1._lerp(th.get('cape', (0, 0, 0)), (0, 0, 0), tc)
    p['plume'] = B1._lerp(th.get('plume', (0, 0, 0)), (0, 0, 0), tc)
    return p


def exec_start(view, k):
    """The execution's own starts (decision 5): from the rest stance toward the lunge (the
    thrust's f1 starts from the charge, too far from standing)."""
    rest, th = B1.resolve(B1.REST, view), _thrust(view)
    t, tt, ts = EXEC_T[k]
    p = B1.lerp_pose(rest, th, t, view)
    p['head'] = B1._lerp((0, 0, 0), th.get('head', (0, 0, 0)), tt)
    ahead = B1.lerp_pose(rest, th, ts, view)
    p['sword'] = ahead['sword']
    p['arms'] = dict(p['arms'], R=ahead['arms']['R'])
    p['cape'] = B1._lerp((0, 0, 0), th.get('cape', (0, 0, 0)), tt * 0.6)
    p['plume'] = B1._lerp((0, 0, 0), th.get('plume', (0, 0, 0)), tt * 0.6)
    return p


# the thrust's frames; the execution plays its two starts, then the thrust's f2 onward on its
# own timing (appendix B)
# 2026-10-05 重擊加強：突刺 0.2 → 0.25 秒（120px），前撲多停 3 幀（位移由程式做，同一張滑過去，和原本一樣）
THRUST_FRAMES = [('f1 蹬地', 2, thrust_push), ('f2 前撲', 13, _thrust),
                 ('f3 保持 1', 4, lambda v: thrust_hold(v, 0)), ('f3 保持 2', 5, lambda v: thrust_hold(v, 1)),
                 ('f4 收劍 1', 5, lambda v: thrust_back(v, THRUST_BACK_T[0])), ('f4 收劍 2', 6, lambda v: thrust_back(v, THRUST_BACK_T[1])),
                 ('f5 回站姿 1', 5, lambda v: thrust_back(v, THRUST_BACK_T[2])), ('f5 回站姿 2', 5, lambda v: thrust_back(v, THRUST_BACK_T[3]))]
EXEC_TIMING = (2, 2, 8, 12, 12, 7, 7, 5, 5)   # start 1, start 2, then the thrust's f2-f5 (60 frames)


# ------------------------------------------------------------------ dodge (decision 4)
# 0-10 the program moves 56 px (5.1 px a sim frame, feet off the floor: no slide to hide);
# 11-17 in place. Entering the dodge is not limited (decision 4, as the deflect); from f1 on
# every step is.
# Per-part plan (animation-review §4.2):
# | part | dash f1 (0-1) | dash f2 (2-10, B1) | stop (11-12, 13-14, 15-17) | backstep f1, f2 | landing (11-12, 13-14, 15-17) |
# |---|---|---|---|---|---|
# | feet | off the floor | reach / trail, 1-2 px up | front foot skids, back foot drags in, then the stance | 2-3 px up | land flat, knees give, stance |
# | pelvis | low 3 | low 3 | low 2, rises | up 1 | low 2, rises |
# | torso | leans 28 | leans 28 | 28 -> 8 -> 0 | leans back 10 | back 10 -> 6 -> 0 |
# | arms, sword | trail | trail low behind | come forward for balance, back to the grip | sword in front | settle |
# | head | still back (late) | caught up | a frame late | late | late |
# | cape, plume | still near rest | streaming back | thrown forward, settle | float forward | drop, settle |
# f1: the head left behind (character space). Front / back views do not show depth: there the
# head is left higher (the dash drops the body) / lower (the hop lifts it), and the cloth ends
# swing in sideways, as the thrust's hold does
DODGE_HEAD_LAG = {('dash', 'side'): (-3.0, 0, 1.5), ('backstep', 'side'): (2.0, 0, -1.0),
                  ('dash', 'fb'): (0, 0, 2.0), ('backstep', 'fb'): (0, 0, -1.5)}
DODGE_CLOTH_FB = ((0, -1.5, 0), (0, -1.0, 0))     # f1 cape / plume, front / back views (inward:
                                                  # outward the dash's cape left the 56 px canvas)
# the stop's key pose: the dash's momentum caught on the front foot
SKID = dict(root=(-1, 0, -2), lean=8,
            feet={'R': (-5, 0, 0, 'toe'), 'L': (4, 0, 0, 'flat')},
            arms={'R': PS.hand('R', -2, -10, -7, elbow=(0, -1, -1)), 'L': PS.hand('L', 6, 10, -3, elbow=(0, 1, -1))},
            sword=dict(hand='R', dir=(-0.3, -0.35, -0.9), dir_view={'south': (-0.1, -0.7, -0.7)}),
            cape=(2, 0, 1), plume=(2, 0, 0))
# the landing's key pose: down from the hop, knees giving
LAND = dict(root=(0, 0, -2), lean=-6,
            feet={'R': (-4, 0, 0, 'flat'), 'L': (3, 0, 0, 'flat')},
            arms={'R': PS.hand('R', 5, -8, -6, elbow=(0, -1, -1)), 'L': PS.hand('L', 3, 10, -4, elbow=(0, 1, -1))},
            sword=dict(hand='R', dir=(0.75, -0.3, -0.3), dir_view={'north': (0.6, -0.7, -0.2)}),
            cape=(1, 0, -1), plume=(1, 0, -1))
STOP_T = (('dash', 'skid', 0.5), ('skid', None, 1.0), ('skid', 'rest', 0.65))
# three frames, not the brief's two: from the hop (pelvis 1 px up) to the landing (2 px down) in
# one step moved the head 6 px and the feet 5 (every landing pose tried stayed >= 6 % over)
LAND_T = (('backstep', 'land', 0.5), ('land', None, 1.0), ('land', 'rest', 0.6))


def _key(name, view):
    return B1.resolve({'dash': PS.DASH, 'backstep': PS.BACKSTEP, 'skid': SKID, 'land': LAND, 'rest': B1.REST}[name], view)


def dodge_f1(view, kind):
    """The body already in the dash / backstep; the head and the cloth still behind it."""
    p = dict(_key(kind, view))
    side = view in ('east', 'west')
    p['head'] = B1._add(p.get('head', (0, 0, 0)), DODGE_HEAD_LAG[(kind, 'side' if side else 'fb')])
    if side:
        p['cape'], p['plume'] = (0, 0, 0), (0, 0, 0)
    else:
        p['cape'] = B1._add(p.get('cape', (0, 0, 0)), DODGE_CLOTH_FB[0])
        p['plume'] = B1._add(p.get('plume', (0, 0, 0)), DODGE_CLOTH_FB[1])
    return p


def dodge_between(view, spec):
    a, b, t = spec
    if b is None:
        return dict(_key(a, view))
    return B1.lerp_pose(_key(a, view), _key(b, view), t, view)


# ------------------------------------------------------------------ the locked walk (85 px/s; decisions 1, 8)
# Locked on, the character faces the target and walks any way. Forward is the walk
# (knight_walk.png). Backward is the walk rig's own cycle run the other way (walk_side /
# walk_fb frame(i, rev=True): the head and the cloth still lag in the order shown). The
# sidesteps are the slow legs' four-frame step-out-and-close under the idle's upper body
# (library arms and sword at rest), stepping wider for the speed: 85 px/s is 11 px in the four
# frames at 2 sim frames each, and the ~9 px legs reach about 6 of it, so the feet slide about
# half of it (the brief said so); from the side the step is in depth, which does not show, so
# the feet only lift in turn (as the slow legs do).
LOCKED_HOLD = 2
# (L lateral px, L lift, R lateral px, R lift): the left foot steps out and lands, the right one
# follows and closes; the planted feet move 1.5 px a frame against the move
LOCKED_SIDE_FB = [(0, 0, 0, 0), (3, 2.5, -1.5, 0), (3, 0, -3, 0), (1.5, 0, -1.5, 2.5)]   # a step <= 4 px
LOCKED_SIDE_SIDE = [(0, 0), (3, 0), (0, 0), (0, 3)]


def _locked_upper(view):
    return B1.resolve(dict(root=(0, 0, 0), lean=0, lean_view={'east': 4, 'west': 4}), view)


_WALK_RIGS = {}


def walk_rig(view):
    if view not in _WALK_RIGS:
        import walk_side as W, walk_fb as F
        _WALK_RIGS[view] = {'east': lambda: W.SideRig(W.EAST), 'west': lambda: W.SideRig(W.WEST),
                            'south': lambda: F.FBRig(F.FRONT), 'north': lambda: F.FBRig(F.BACK)}[view]()
    return _WALK_RIGS[view]


def walk_back_frame(view, i):
    r = walk_rig(view)
    f = r.frame(i, rev=True)
    return f.px, dict(r.debug)


# ------------------------------------------------------------------ actions and frames
# (frame name, sim frames it shows, builder(view) -> resolved pose)
ACTIONS = {
    'run': [(f'run {i + 1}', 2, (lambda v, i=i: run_pose(v, i))) for i in range(RUN_N)] +
           [(f'起跑 {n + 1}', 2, (lambda v, n=n: run_start(v, n))) for n in range(2)] +
           [('停步 1A', 2, lambda v: run_stop(v, 'A')), ('停步 1B', 2, lambda v: run_stop(v, 'B')),
            ('停步 2', 2, lambda v: run_stop(v, 2)), ('停步 3', 2, lambda v: run_stop(v, 3))],
    'charge': [(f'in {i + 1}', 2, (lambda v, i=i: charge_in(v, *CHARGE_IN_T[i]))) for i in range(2)] +
              [(f'hold {i + 1}', CHARGE_HOLD, (lambda v, i=i: B1.breathe(_charge(v), v, i))) for i in range(4)] +
              [(f'out {i + 1}', 2, (lambda v, i=i: charge_out(v, *CHARGE_OUT_T[i]))) for i in range(2)],
    'charge_walk': charge_walk(),
    'dash': [('衝刺 1', 2, lambda v: dodge_f1(v, 'dash')), ('衝刺 2', 9, lambda v: _key('dash', v))] +
            [(f'煞停 {i + 1}', d, (lambda v, i=i: dodge_between(v, STOP_T[i]))) for i, d in enumerate((2, 2, 3))],
    'backstep': [('後跳 1', 2, lambda v: dodge_f1(v, 'backstep')), ('後跳 2', 9, lambda v: _key('backstep', v))] +
                [(f'落地 {i + 1}', d, (lambda v, i=i: dodge_between(v, LAND_T[i]))) for i, d in enumerate((2, 2, 3))],
    # a locked sidestep dodge: the dash drawn toward the dodge, the recovery facing the target
    # (decision 6) with the landing frames
    'walk_locked': [(f'back {i + 1}', LOCKED_HOLD, ('walk_back', i)) for i in range(8)] +
                   [(f'{nm} {i + 1}', LOCKED_HOLD, (lambda v, i=i, rev=rev: B1.walk_pose(
                       _locked_upper(v), v, 'side', i, rev=rev, tables=(LOCKED_SIDE_FB, LOCKED_SIDE_SIDE))))
                    for nm, rev in (('side', False), ('rside', True)) for i in range(4)],
    'thrust': THRUST_FRAMES,
    'execute': [('起步 1', EXEC_TIMING[0], lambda v: exec_start(v, 0)), ('起步 2', EXEC_TIMING[1], lambda v: exec_start(v, 1))] +
               [(n, d, b) for (n, _, b), d in zip(THRUST_FRAMES[1:], EXEC_TIMING[2:])],
}
CANVAS = {'run': 'small', 'charge': 'large', 'charge_walk': 'large', 'thrust': 'large', 'execute': 'large',
          'dash': 'small', 'backstep': 'small', 'walk_locked': 'small'}
TITLES = {'run': '奔跑（循環 1–8，起跑 1–2，停步 1A／1B、2、3）',
          'charge': '蓄力（進入、按住 1–4、沒蓄滿放開的收勢 1–2）',
          'charge_walk': '蓄力移動（前進 1–6、往左側移 1–4、後退 1–6、往右側移 1–4）',
          'thrust': '突刺（放開蓄滿的蓄力）',
          'dash': '閃身：衝刺 1、2，煞停 1–3',
          'walk_locked': '鎖定走路（後退 1–8、往左側移 1–4、往右側移 1–4；前進用 knight_walk.png）',
          'backstep': '閃身：後跳 1、2，落地 1–3（鎖定時往側邊閃的收招也用落地）',
          'execute': '處決（起步 1、2 另畫，之後共用突刺 f2–f5，時間不同）'}


class Frame(B1.Frame):
    pass


# actions whose blade may turn a little to stay >= 3:1 against what is behind it (batch 2's
# readable(); not the charge: its walk must keep the hold's upper body pixel for pixel)
READABLE = ('thrust', 'execute', 'dash', 'backstep', 'run')


_CACHE = {}


def frames(action, view):
    key = (action, view)
    if key in _CACHE:
        return _CACHE[key]
    out = []
    canvas = CANVAS[action]
    for name, dur, build in ACTIONS[action]:
        if isinstance(build, tuple) and build[0] == 'walk_back':
            # the walk rig's own frame, run backward: no pose; what the checks need is in debug
            px, dbg = walk_back_frame(view, build[1])
            out.append(Frame(action, name, dur, view, px, {}, {}, {}, dbg, None))
            continue
        pose = build(view)
        if action in READABLE:
            import batch2 as B2
            pose = B2.readable(view, pose)
        r = PR.rig(view)
        px = r.frame(pose, canvas)
        dx, dy = r.canvas_offset()
        sh = lambda d: {(x + dx, y + dy): c for (x, y), c in d.items()}
        # trace, pieces and debug in canvas coordinates (as batch 2 does)
        trace = {(x + dx, y + dy): n for (x, y), n in r.trace.items()}
        dbg = {'blade': {(x + dx, y + dy) for (x, y) in r.debug.get('blade', set())},
               'hands': {k: (x + dx, y + dy) for k, (x, y) in r.debug.get('hands', {}).items()},
               'legs': {k: tuple((q[0] + dx, q[1] + dy) for q in v) for k, v in r.debug.get('legs', {}).items()},
               'pelvis': (r.debug['pelvis'][0] + dx, r.debug['pelvis'][1] + dy)}
        out.append(Frame(action, name, dur, view, px, trace, {n: sh(v) for n, v in r.pieces.items()},
                         {n: sh(v) for n, v in r.pieces_raw.items()}, dbg, pose))
    _CACHE[key] = out
    return out
