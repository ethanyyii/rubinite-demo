"""Batch 2 of the player's actions (docs/art-progress.md): light attacks 1-4, on the 88 x 72
canvas, foot anchor (44, 61). Stage 3 is stage 1's f2-f6 with its own timing (no sheet of its
own); the other stages each have a sheet.

Timing is in simulation frames (60 Hz) from scripts/combat/player_data.gd (light_attacks:
startup / active / recovery seconds -> Frames.of, rounded) and player_sim.gd:

| stage | start-up | active (advance) | recovery | chain from | advance |
|---|---|---|---|---|---|
| 1, 2 | 0-5 | 6-10 | 11-25 | 11 | 6 px, 1.2 px a frame |
| 3 | 0-6 | 7-11 | 12-28 | 12 | 6 px |
| 4 | 0-10 | 11-16 | 17-43 | - | 14 px, 2.33 px a frame |

The program moves the character forward during the active frames. Decision 2 (batch 2): the
picture follows the program's position only when the sprite frame changes, so a foot planted
on the floor stays exactly still; the art draws everything in the floor's frame ("world"
feet: where each foot is on the floor, measured from where the stage began) and each frame is
shifted back by the advance at its first sim frame (`advance_at`).

Per-part plan (animation-review §4.2; the brief in docs/art-progress.md, "第 2 批"): stage 1
below; stage 2 is the backhand on the mirrored path (from stage 1's follow-through, the wrist
turns, the blade is cocked on the off side, sweeps across and ends high on the sword side);
stage 4 is the same build, larger (a crouch back, a long coiled apex, the sweep, a long step).

| part | f1 ready (C1) | f2 top (C2) | f3 contact | f4 follow-through (C3) | f5 hold | f6 stance (C4) |
|---|---|---|---|---|---|---|
| feet | back foot back, weight back | wide, front knee bent | back foot pushes (planted), front foot steps out | front foot lands (planted), back foot on its toe | front foot planted, back foot drags in | back to the idle stance |
| pelvis | back 2 px | low 3 px | forward | 4 px ahead of the top | the program catches up: held in place | idle height |
| torso | turned back (decision 12: shown by the sword, arms and cape) | leans back 2 deg | squares up | leans in 12 deg | held | upright |
| sword | low behind | raised forward and up | level in front (the arc's middle) | low across to the off side | settles lower | back to the idle grip |
| off arm | forward for balance | forward | swings back | back | held | at the side |
| head | a frame late | a frame late | left behind the lunge | still behind | catches up | a frame late |
| cape, plume | forward | starting back | thrown against the swing | furthest | still swinging | settling |
"""
import batch1 as B1
import poses as PS
import pose_rig as PR

VIEWS = B1.VIEWS
CANVAS = 'large'
FWD_SCREEN = {'east': (1, 0), 'west': (-1, 0), 'south': (0, 1), 'north': (0, -1)}

# player_data.gd light_attacks(): (start-up frames, active frames, total frames, advance px)
ATTACK = {1: (6, 5, 26, 6.0), 2: (6, 5, 26, 6.0), 3: (7, 5, 29, 6.0), 4: (11, 6, 44, 14.0)}


def advance_at(stage, e):
    """Program advance (px along the facing) after sim frame e of the stage (player_sim.gd:
    +advance / active frames on every active frame, the frame's tick included)."""
    a0, n, _, total = ATTACK[stage]
    if e < a0:
        return 0.0
    return total * min(n, e - a0 + 1) / n


# ------------------------------------------------------------------ feet on the floor
# A frame's feet are given where they stand on the floor, from where the stage began: (f, l,
# lift, state) in the rig's units (side views: along the facing, from the rest stance; front
# / back: toward the camera / to the character's left). The frame's own feet are these shifted
# back by the advance. 'weight' names the foot that carries the weight (it must not move on
# screen while it stays the weight foot).
#
# Front / back views: the rig draws depth squeezed (KD_FEET = 0.55 px a unit), and the
# program's 6-14 px advance toward / away from the camera is far more than the foreshortened
# legs can show (the stances there are 2-3 px deep on screen). The feet use the side views'
# numbers, so a planted foot is held back 55 % of the advance on screen and the rest shows as
# the foot moving with the body (reported by the checks: the view cannot draw more).


def place_feet(feet, view, adv, root=(0, 0, 0)):
    """World feet -> the frame's feet for this view."""
    out = {}
    for s_, (f_, l_, lift, state) in feet.items():
        if view in ('east', 'west'):
            # the rig keeps a foot on the floor when the root moves along the facing; a sideways
            # root shows a little in the side views too (SIDE_X): take that back as well
            fdir = PR.VIEWS[view]['facing']
            out[s_] = (f_ - adv - PR.SIDE_X * root[1] * fdir, l_, lift, state)
        else:
            out[s_] = (f_ - adv, l_, lift, state)
    return out


def _add(v, d):
    return tuple(a + b for a, b in zip(v, d))


def build(upper, feet, view, adv, weight, root=None, **extra):
    """A frame's pose: `upper` is a resolved pose for the body (its own root f is where the
    body is in the frame), `feet` world feet."""
    p = dict(upper)
    if root is not None:
        p['root'] = root
    p['feet'] = place_feet(feet, view, adv, p.get('root', (0, 0, 0)))
    p.update(extra)
    p['_weight'] = weight
    return p


def R(pose, view):
    return B1.resolve(pose, view)


def lerp(a, b, t, view):
    return B1.lerp_pose(a, b, t, view)


# ------------------------------------------------------------------ new poses
hand = PS.hand
# stage 1 f1 (C1 in spirit): the weight goes back, the pelvis back 2 px and the shoulders turn
# away, the blade starts rising in front. C1 draws the blade low behind the back; from there
# to the top (C2) the point travels 42-51 px in one frame, over the 20 px limit, so the blade
# is already on its way up here (the delivery shows C1's outline and the difference)
READY1 = dict(root=(-2.2, -1, -1), lean=0, roll=-6,
              feet={'R': (-2, -3, 0, 'flat'), 'L': (3, 3, 0, 'flat')},
              arms={'R': hand('R', 5, -7, -2, elbow=(-1, -1, -1)), 'L': hand('L', 6, 6, -4, elbow=(0, 1, -1))},
              sword=dict(hand='R', dir=(0.8, -0.15, 0.25)),
              cape=(1, 0, 0), plume=(1, 0, 0), head=(0.5, 0, 0.8))
# stage 2 f2: the backhand cocked on the off side (the blade back past the left hip), the
# shoulders turned to the left, the pelvis back (the follow-through ends 4 px ahead of it)
COCK2 = dict(root=(-2, 1, -3), lean=4, roll=8,
             feet={'R': (-5, -5, 0, 'flat'), 'L': (3, 5, 0, 'flat')},
             arms={'R': hand('R', 4, 6, -2, elbow=(0, -1, 0)), 'L': hand('L', -2, 10, -5, elbow=(0, 1, 0))},
             sword=dict(hand='R', dir=(-0.15, 0.7, 0.45), dir_view={'south': (0.1, 0.55, 0.65), 'north': (0.1, 0.5, 0.7)}),
             cape=(-1, 1, 0), plume=(-1, 0, 0))


def _tip_on_screen(view, pose, adv):
    r = PR.rig(view)
    r.frame(pose, CANVAS)
    fist = r.debug['hands']['R']
    tip = max(r.debug['blade'], key=lambda q: (q[0] - fist[0]) ** 2 + (q[1] - fist[1]) ** 2)
    fx, fy = FWD_SCREEN[view]
    return tip[0] + fx * adv, tip[1] + fy * adv


def contact(a, b, view, specs, head=(-1, 0, 0), cloth=((-2, 0, 1), (-2, 0, 1))):
    """The contact frame between a top and a follow-through: the in-between (its blade may
    lean a little off the straight in-between) that keeps both swing steps within the limits
    (decision 5: head / torso 8 px; hands / sword 20 px; item 7) as far as possible. specs =
    the (feet, adv, weight) of the top, the contact and the follow-through frames."""
    pa, pb = parts(view, a, specs[0][1], specs[0][0], specs[0][2]), parts(view, b, specs[2][1], specs[2][0], specs[2][2])
    best = None
    for i in range(17):
        t = 0.3 + 0.025 * i
        base = lerp(a, b, t, view)
        base['head'] = head
        for nudge in [(0, 0, 0)] + [(x, y, z) for k in (0.05, 0.1, 0.15) for (x, y, z) in
                                    ((k, 0, 0), (-k, 0, 0), (0, k, 0), (0, -k, 0), (0, 0, k), (0, 0, -k))]:
            m = dict(base, sword=dict(base['sword'], dir=PR.vnorm(_add(base['sword']['dir'], nudge))))
            pm = parts(view, m, specs[1][1], specs[1][0], specs[1][2])
            w = worst([(pa, pm), (pm, pb)], limits=SWING_LIMITS)
            if best is None or w < best[0] - 1e-9:
                best = (w, m)
    m = best[1]
    m['cape'], m['plume'] = cloth
    return m


def recover(hold, rest, view, t):
    p = lerp(hold, rest, t, view)
    p['cape'], p['plume'] = _add((-1, 0, 0), (-2 * (1 - t), 0, 0)), (-1, 0, 0)
    return p


# ------------------------------------------------------------------ searching in-betweens
LIMITS = {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.0}
SWING_LIMITS = dict(LIMITS, head=8.0, torso=8.0)        # decision 5


def parts(view, pose, adv, feet=None, weight=None):
    """Where the parts of a posed frame are on screen (the picture moved by the advance)."""
    import checks as C
    p = build(pose, feet, view, adv, weight) if feet is not None else dict(pose)
    p.pop('_weight', None)
    r = PR.rig(view)
    px = r.frame(p, CANVAS)
    dx, dy = r.canvas_offset()

    class F:
        pass
    f = F()
    f.px = px
    f.trace = {(x + dx, y + dy): n for (x, y), n in r.trace.items()}
    f.pieces_raw = {n: {(x + dx, y + dy): c for (x, y), c in v.items()} for n, v in r.pieces_raw.items()}
    f.debug = {'blade': {(x + dx, y + dy) for (x, y) in r.debug.get('blade', set())},
               'hands': {k: (x + dx, y + dy) for k, (x, y) in r.debug.get('hands', {}).items()},
               'legs': {k: tuple((q[0] + dx, q[1] + dy) for q in v) for k, v in r.debug.get('legs', {}).items()}}
    fx, fy = FWD_SCREEN[view]
    return C._Pt(f, fx * adv, fy * adv)


def worst(steps, skip=(), limits=None):
    """Largest move / limit over a list of (parts a, parts b) steps."""
    import checks as C
    w = 0.0
    for a, b in steps:
        m = C.screen_moves(a, b)
        for k, lim in (limits or LIMITS).items():
            if k in skip or m.get(k) is None:
                continue
            w = max(w, m[k] / lim)
    return w


def search_pair(view, a_pts, pose_a, pose_b, specs, b_pts, grid1, grid2, skip_last=()):
    """Two in-betweens from pose_a to pose_b (t1 < t2 from the grids) that keep every step
    within the limits as far as possible: specs = ((feet, adv, weight), (feet, adv, weight)) of
    the two frames; a_pts / b_pts the parts of the frames before and after. Returns (worst
    move / limit, pose 1, pose 2)."""
    best = None
    cache = {}
    for t1 in grid1:
        for t2 in grid2:
            if t2 <= t1:
                continue
            ps = []
            for t, (feet, adv, wgt) in ((t1, specs[0]), (t2, specs[1])):
                if (t, adv) not in cache:
                    pose = lerp(pose_a, pose_b, t, view)
                    cache[(t, adv)] = (pose, parts(view, pose, adv, feet, wgt))
                ps.append(cache[(t, adv)])
            w = max(worst([(a_pts, ps[0][1]), (ps[0][1], ps[1][1])]), worst([(ps[1][1], b_pts)], skip_last))
            if best is None or w < best[0]:
                best = (w, ps[0][0], ps[1][0])
    return best


# ------------------------------------------------------------------ the frames
def _feet(stage, i):
    _, a, _, _, feet, weight = FRAMES[stage][i]
    return feet, advance_at(stage, a), weight


def idle_parts(view, adv):
    import checks as C
    fx, fy = FWD_SCREEN[view]
    return C._Pt(B1.frames('idle', view)[0], fx * adv, fy * adv, small=True)


GRID1 = (0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5)
GRID2 = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9)


def recovery(stage, view, hold, i_hold):
    """The two frames back to the stance after the hold, searched so every step (and the
    step into the idle) stays within the limits."""
    rest = R(B1.REST, view)
    feet, adv, w = _feet(stage, i_hold)
    a = parts(view, hold, adv, feet, w)
    b = idle_parts(view, B2_TOTAL[stage])
    _, p1, p2 = search_pair(view, a, hold, rest, (_feet(stage, i_hold + 1), _feet(stage, i_hold + 2)), b,
                            GRID1, GRID2, skip_last=('hands', 'sword'))
    for p in (p1, p2):
        p['cape'], p['plume'] = (-1, 0, 0), (-1, 0, 0)
    return p1, p2


B2_TOTAL = {st: ATTACK[st][3] for st in ATTACK}


HEADS = [(f, 0, u) for f in (-2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1) for u in (-1, -0.5, 0, 0.5, 1)]


def ready_head(view, ready, top):
    """Stage 1's f1 comes from the idle, the guard (any breath phase) and the slow legs, and
    goes to the top: its head is placed where all of those steps stay within 4 px."""
    fr = _feet(1, 0)
    srcs = [idle_parts(view, 0.0)]
    import checks as C
    for f in B1.frames('guard', view)[:4]:
        srcs.append(C._Pt(f, small=True))
    pt = parts(view, top, *(_feet(1, 1)[1:2]), _feet(1, 1)[0], 'R') if False else parts(view, top, 0.0, _feet(1, 1)[0], 'R')
    best = None
    for h in HEADS:
        p = dict(ready, head=h)
        pr = parts(view, p, fr[1], fr[0], fr[2])
        w = max(worst([(s, pr) for s in srcs], skip=('hands', 'sword')), worst([(pr, pt)]))
        if best is None or w < best[0]:
            best = (w, p)
    return best[1]


def end_head(view, mid, end, hold):
    """Stage 2's follow-through: its head is placed so the swing step into it (8 px), the step
    to the hold and the chain into stage 3's top (4 px) all stay within the limits."""
    pm = parts(view, mid, _feet(2, 2)[1], _feet(2, 2)[0], 'R')
    ph = parts(view, hold, _feet(2, 4)[1], _feet(2, 4)[0], 'L')
    top = R(PS.L1_TOP, view)
    fx, fy = FWD_SCREEN[view]
    pt = parts(view, top, 0.0, _feet(1, 1)[0], 'R')
    pt = type(pt).__new__(type(pt))
    pt.__dict__.update(parts(view, top, 0.0, _feet(1, 1)[0], 'R').__dict__)
    # stage 3's top shows 6 px further on than stage 2's start (the whole advance)
    sh = lambda q: None if q is None else (q[0] + fx * 6.0, q[1] + fy * 6.0)
    pt.head, pt.torso, pt.tip = sh(pt.head), sh(pt.torso), sh(pt.tip)
    pt.fists = {k: sh(v) for k, v in pt.fists.items()}
    pt.ankles = {k: sh(v) for k, v in pt.ankles.items()}
    pt.boots = {(round(x + fx * 6.0), round(y + fy * 6.0)) for (x, y) in pt.boots}
    best = None
    for h in HEADS:
        p = dict(end, head=h)
        pe = parts(view, p, _feet(2, 3)[1], _feet(2, 3)[0], 'L')
        w = max(worst([(pm, pe)], limits=SWING_LIMITS), worst([(pe, ph)]), worst([(pe, pt)]))
        if best is None or w < best[0]:
            best = (w, p)
    return best[1]


def stage1(view):
    """Stage 1 (and 3: its frames 2-7 with stage 3's timing)."""
    top, end = R(PS.L1_TOP, view), R(PS.L1_END, view)
    ready = R(READY1, view)
    end4 = dict(end, head=(-1, 0, 0))
    hold = dict(end, head=(0.5, 0, -0.5), cape=(-4, 0, 2), plume=(-4, 0, 1))
    hold['sword'] = dict(end['sword'], dir=PR.vnorm(_add(end['sword']['dir'], (0, 0, -0.15))))
    mid = contact(top, end4, view, (_feet(1, 1), _feet(1, 2), _feet(1, 3)))
    ready = ready_head(view, ready, top)
    b1, b2 = recovery(1, view, hold, 4)
    return {'ready': ready, 'top': top, 'contact': mid, 'end': end4, 'hold': hold, 'back1': b1, 'back2': b2}


FRAMES = {
    # stage: [(frame name, first sim frame, last sim frame, pose key, world feet, weight foot)]
    1: [('f1 預備', 0, 2, 'ready', {'R': (-2, -3, 1, 'swing'), 'L': (3, 3, 0, 'flat')}, 'L'),
        ('f2 頂點', 3, 5, 'top', {'R': (-4, -5, 0, 'flat'), 'L': (5, 5, 0, 'flat')}, 'R'),
        ('f3 接觸', 6, 7, 'contact', {'R': (-4, -5, 0, 'flat'), 'L': (8.5, 5, 1.5, 'reach')}, 'R'),
        ('f4 揮完', 8, 10, 'end', {'R': (-2.4, -5, 0, 'toe'), 'L': (8.5, 5, 0, 'flat')}, 'L'),
        ('f5 收招', 11, 17, 'hold', {'R': (0.5, -5, 0, 'toe'), 'L': (8.5, 5, 0, 'flat')}, 'L'),
        ('f6 回站姿 1', 18, 21, 'back1', {'R': (3, -4.5, 0, 'flat'), 'L': (8, 4.5, 0, 'flat')}, 'L'),
        ('f6 回站姿 2', 22, 25, 'back2', {'R': (5, -4.25, 0, 'flat'), 'L': (7.5, 4.25, 0, 'flat')}, None)],
}


def stage2(view):
    """Stage 2, the backhand: from stage 1's follow-through the wrist turns the blade over
    (f1), the blade is cocked past the left hip (f2), sweeps level across the front (f3) and
    ends high on the sword side (f4, L2_END)."""
    end1, end = R(PS.L1_END, view), R(PS.L2_END, view)
    cock = R(COCK2, view)
    rest = R(B1.REST, view)
    # stage 1's follow-through, seen from stage 2's start (the program is 2.4 px further on)
    chain = dict(end1, root=_add(end1['root'], (-2.4, 0, 0)))
    turn = lerp(chain, cock, 0.55, view)
    turn['head'] = (0.5, 0, -0.5)
    end4 = dict(end, head=(-1, 0, 0))
    hold = dict(end, head=(0, 0, -0.5), cape=(-4, 1, 2), plume=(-4, 1, 1))
    mid = contact(cock, end4, view, (_feet(2, 1), _feet(2, 2), _feet(2, 3)), cloth=((-2, 1, 1), (-2, 0, 1)))
    end4 = end_head(view, mid, end4, hold)
    b1, b2 = recovery(2, view, hold, 4)
    return {'turn': turn, 'cock': cock, 'contact': mid, 'end': end4, 'hold': hold, 'back1': b1, 'back2': b2}


def stage4(view):
    """Stage 4: a crouch back in two frames (f1), the coiled apex held 7 frames (f2), the sweep
    (f3, D2), the long step (f4, D3), held (f5), rising (f6, two frames), the stance (f7)."""
    top, mid, end = R(PS.L4_TOP, view), R(PS.L4_MID, view), R(PS.L4_END, view)
    end1 = R(PS.L1_END, view)
    rest = R(B1.REST, view)
    chain = dict(end1, root=_add(end1['root'], (-2.4, 0, 0)))     # stage 3's follow-through
    # stage 3's follow-through as seen from stage 4's start: its feet 6 px back (the program
    # finished stage 3's advance), its picture 2.4 px back (it showed at 3.6 of 6)
    ch_feet = {k: (v[0] - 6.0,) + tuple(v[1:]) for k, v in FRAMES[1][3][4].items()}
    a = parts(view, chain, 0.0, ch_feet, 'L')
    b = parts(view, top, *_feet(4, 2)[1:2], _feet(4, 2)[0], 'R') if False else parts(view, top, 0.0, _feet(4, 2)[0], 'R')
    _, c1, c2 = search_pair(view, a, chain, top, (_feet(4, 0), _feet(4, 1)), b, GRID1, GRID2)
    c1['head'], c2['head'] = (0.5, 0, 0), (0.5, 0, 0)
    mid3 = dict(mid, head=(-1, 0, 0))
    # D3 sits 0.5 px back in its frame: with the program's 4.7 px at this frame change the head
    # moved 8.3 px on screen (decision 5: 8); the pelvis is still 6.5 px ahead of the apex
    end4 = dict(end, head=(-1, 0, 0), root=_add(end['root'], (-0.5, 0, 0)))
    # the program is 7 px further on at f5 than at f4: the body is drawn back so it settles
    # 2 px back on screen (and the back foot, still far behind, stays within the leg's reach);
    # rising, it catches the program up
    hold = dict(end, root=(-5, end['root'][1], end['root'][2]), head=(0.5, 0, -0.5), cape=(-6, 0, 4), plume=(-5, 0, 2))
    hold['sword'] = dict(end['sword'], dir=PR.vnorm(_add(end['sword']['dir'], (0, 0, -0.1))))
    stance = recover(hold, rest, view, 0.85)
    f_hold, f_st = _feet(4, 5), _feet(4, 8)
    a = parts(view, hold, f_hold[1], f_hold[0], f_hold[2])
    b = parts(view, stance, f_st[1], f_st[0], f_st[2])
    _, r1, r2 = search_pair(view, a, hold, stance, (_feet(4, 6), _feet(4, 7)), b, GRID1, GRID2)
    for p in (r1, r2):
        p['cape'], p['plume'] = (-2, 0, 1), (-1, 0, 0)
    return {'crouch1': c1, 'crouch2': c2, 'top': top, 'mid': mid3, 'end': end4, 'hold': hold,
            'rise1': r1, 'rise2': r2, 'stance': stance}


FRAMES[2] = [
    ('f1 翻腕', 0, 2, 'turn', {'R': (-7, -5, 0, 'toe'), 'L': (2.5, 5, 0, 'flat')}, 'L'),
    ('f2 反手蓄勢', 3, 5, 'cock', {'R': (-5, -5, 0, 'flat'), 'L': (4.5, 5, 1, 'swing')}, 'R'),
    ('f3 接觸', 6, 7, 'contact', {'R': (-5, -5, 0, 'flat'), 'L': (8, 5, 1.5, 'reach')}, 'R'),
    ('f4 揮完', 8, 10, 'end', {'R': (-1.5, -5, 0, 'flat'), 'L': (8, 5, 0, 'flat')}, 'L'),
    ('f5 收招', 11, 17, 'hold', {'R': (1, -5, 0, 'toe'), 'L': (8, 5, 0, 'flat')}, 'L'),
    ('f6 回站姿 1', 18, 21, 'back1', {'R': (4, -4.5, 0, 'flat'), 'L': (7.5, 4.5, 0, 'flat')}, 'L'),
    ('f6 回站姿 2', 22, 25, 'back2', {'R': (5.5, -4.25, 0, 'flat'), 'L': (7, 4.25, 0, 'flat')}, None)]
# stage 3 = stage 1's f2-f6 at stage 3's timing (start-up 0-6, active 7-11)
FRAMES[3] = [(n, a, b, key, feet, w) for (n, _, _, key, feet, w), (a, b) in
             zip(FRAMES[1][1:], ((0, 6), (7, 8), (9, 11), (12, 19), (20, 24), (25, 28)))]
FRAMES[4] = [
    ('f1 後撤下蹲 1', 0, 1, 'crouch1', {'R': (-8, -5, 0, 'flat'), 'L': (2.5, 5, 0, 'flat')}, 'R'),
    ('f1 後撤下蹲 2', 2, 3, 'crouch2', {'R': (-7.5, -5, 0, 'flat'), 'L': (4.5, 5, 1, 'swing')}, 'R'),
    ('f2 蓄勢頂點', 4, 10, 'top', {'R': (-7, -5, 0, 'flat'), 'L': (6, 5, 0, 'flat')}, 'R'),
    ('f3 揮到一半', 11, 12, 'mid', {'R': (-7, -5, 0, 'toe'), 'L': (9.4, 5, 2, 'reach')}, 'R'),
    ('f4 揮完', 13, 16, 'end', {'R': (-3, -5, 0, 'toe'), 'L': (12.8, 5, 0, 'flat')}, 'L'),
    ('f5 保持', 17, 28, 'hold', {'R': (1, -5, 0, 'toe'), 'L': (12.8, 5, 0, 'flat')}, 'L'),
    ('f6 起身 1', 29, 32, 'rise1', {'R': (4.4, -4.75, 0, 'flat'), 'L': (12.8, 4.75, 0, 'flat')}, 'L'),
    ('f6 起身 2', 33, 36, 'rise2', {'R': (8, -4.5, 0, 'flat'), 'L': (13.3, 4.5, 0, 'flat')}, 'L'),
    ('f7 回站姿', 37, 43, 'stance', {'R': (11.5, -4.25, 0, 'flat'), 'L': (13.8, 4.25, 0, 'flat')}, None)]
POSES = {1: stage1, 2: stage2, 3: stage1, 4: stage4}
SHEETS = {1: 'attack1', 2: 'attack2', 4: 'attack4'}    # stage 3 uses attack1's columns 2-7
TITLES = {1: '輕攻擊第 1 段', 2: '輕攻擊第 2 段（反手）', 3: '輕攻擊第 3 段（共用第 1 段 f2 以後）', 4: '輕攻擊第 4 段'}


CONTRAST_MIN = 3.0
NUDGES = [(a, b, c) for k in (0.08, 0.15, 0.25) for (a, b, c) in
          ((k, 0, 0), (-k, 0, 0), (0, k, 0), (0, -k, 0), (0, 0, k), (0, 0, -k))]


def _contrast(view, pose):
    import checks as C
    r = PR.rig(view)
    px = r.frame(pose, CANVAS)
    dx, dy = r.canvas_offset()
    vals = [v for v, _ in C.blade_contrast(r, px, dx, dy) if v is not None]
    return min(vals) if vals else 99.0


def readable(view, pose):
    """animation-review §4.5: every blade >= 3:1 against what is behind it. A frame whose
    blade lies over a lit patch (the visor, a pauldron's glint) turns the blade by the
    smallest nudge that clears it (at most about 14 degrees)."""
    if 'sword' not in pose or _contrast(view, pose) >= CONTRAST_MIN:
        return pose
    for n in NUDGES:
        p = dict(pose, sword=dict(pose['sword'], dir=PR.vnorm(_add(PR.vnorm(pose['sword']['dir']), n))))
        if _contrast(view, p) >= CONTRAST_MIN:
            return p
    return pose


class Frame:
    def __init__(self, stage, name, first, last, view, adv, weight, px, trace, pieces_raw, debug, pose):
        self.stage, self.name, self.first, self.last, self.view = stage, name, first, last, view
        self.dur = last - first + 1
        self.adv, self.weight = adv, weight
        self.px, self.trace, self.pieces_raw, self.debug, self.pose = px, trace, pieces_raw, debug, pose

    def screen_offset(self):
        """Where the picture sits on screen relative to the stage's start (decision 2)."""
        fx, fy = FWD_SCREEN[self.view]
        return fx * self.adv, fy * self.adv


_CACHE = {}


def frames(stage, view):
    key = (stage, view)
    if key in _CACHE:
        return _CACHE[key]
    poses = POSES[stage](view)
    out = []
    for name, a, b, pk, feet, weight in FRAMES[stage]:
        adv = advance_at(stage, a)
        pose = build(poses[pk], feet, view, adv, weight)
        pose.pop('_weight')
        pose = readable(view, pose)
        r = PR.rig(view)
        px = r.frame(pose, CANVAS)
        dx, dy = r.canvas_offset()
        # trace, pieces and debug are in small-frame coordinates: move them onto the canvas
        sh = lambda d: {(x + dx, y + dy): c for (x, y), c in d.items()}
        trace = {(x + dx, y + dy): n for (x, y), n in r.trace.items()}
        raw = {n: sh(v) for n, v in r.pieces_raw.items()}
        dbg = {'blade': {(x + dx, y + dy) for (x, y) in r.debug.get('blade', set())},
               'hands': {k: (x + dx, y + dy) for k, (x, y) in r.debug.get('hands', {}).items()},
               'legs': {k: tuple((p[0] + dx, p[1] + dy) for p in v) for k, v in r.debug.get('legs', {}).items()},
               'pelvis': (r.debug['pelvis'][0] + dx, r.debug['pelvis'][1] + dy)}
        out.append(Frame(stage, name, a, b, view, adv, weight, px, trace, raw, dbg, pose))
    _CACHE[key] = out
    return out
