"""Checks of the execution (2026-10-05: the 3 s leap and stab, execute.py; animation-review §4, §5).

    python3 tools/sprite_rig/checks_execute.py [--selftest]

Every number the game decides is read from the game's own files (scripts/combat/player_data.gd), not
from execute.py: the length, the leap, the plunge, the twists, the kick, the landing. Exit code 0 when
everything passes. --selftest breaks the animation on purpose in several ways and expects each to fail.
"""
import math
import os
import re
import sys

import checks as C
import execute as E
import pose_rig as PR
import sprites as A

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

# ------------------------------------------------------------------ standards (not read from execute.py)
# frame-to-frame moves on screen (px), the batch 2 / combo4 limits from BODY_PX: the head and torso 4 px
# on the floor (B1_JUMP), the hands and the point 20 px (a swing step). In the air the body moves with the
# throw: the knight's leap rises up to ~9 px a sim frame (80 px in 0.3 s), the jump back lands at ~6 px a
# sim frame, so a frame there may move the body that far times the frames it is held (the Boss's leap,
# animation-review §4.2 "騰空": the height's change per frame follows the throw's speed)
BODY_STEP = C.B1_JUMP
SWING_STEP = C.px(0.5)                  # 20 px: hands, sword point
THROW_SPEED = 10.0                      # px a sim frame, the fastest the throw may carry the body
# the beats where a frame may jump further, each with its reason (animation-review §5: a waiver names why)
BEAT_STEPS = {
    '起跳': ('the push off: the coiled body throws itself up (the sword swings from behind to the front)', 18.0, 32.0),
    '插下去': ('the plunge: the arms drive down from over the head (hitstop holds this frame 0.25 s)', 12.0, 30.0),
    '蹬開': ('the kick: legs straighten, the blade pulled out of him', 12.0, 26.0),
    '後跳 1': ('the hands let go of the grip as he flies back', 12.0, 26.0),
}
ARM_K_MAX = 1.7                         # arms drawn longer only for the sword over the head (the knight's 13 px
                                        # arms reach his brow; the Boss's overhead swing used up to 1.5)
HANG_K_MAX = 1.35                       # both fists on a grip 10 px out in front: the shoulders are 21 px apart
HILT_STILL = 1.0                        # px the right fist may wander while the sword is in the Boss
LIFT_MIN_AT_HIT = 60                    # the plunge is up at the kneeling Boss's chest


def game_numbers():
    """The execution's timing from the game's data (seconds -> frames, as Frames.of rounds)."""
    src = open(os.path.join(ROOT, 'scripts', 'combat', 'player_data.gd'), encoding='utf-8').read()

    def sec(name):
        return float(re.search(rf'const {name}\s*:?=\s*([0-9.]+)', src).group(1))
    twists = re.search(r'const EXECUTE_TWIST_TIMES[^=]*=\s*\[([^\]]+)\]', src).group(1)
    fr = lambda s: int(math.floor(s * 60 + 0.5))
    return dict(total=fr(sec('EXECUTE_TIME')), leap=fr(sec('EXECUTE_LEAP_TIME')), hit=fr(sec('EXECUTE_HIT_TIME')),
                kick=fr(sec('EXECUTE_KICK_TIME')), land=fr(sec('EXECUTE_LAND_TIME')),
                twists=[fr(float(t)) for t in twists.split(',')], perch=sec('EXECUTE_PERCH'))


RESULTS = []


def out(ok, name, info=''):
    RESULTS.append((ok, name, info))
    tag = 'INFO' if ok is None else ('PASS' if ok else 'FAIL')
    print(f'{tag:4}  {name}' + (f'  [{info}]' if info else ''))


def _cen(f, names):
    pts = [q for n in names for q in f.pieces_raw.get(n, {})]
    if not pts:
        return None
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def _d(a, b):
    return None if a is None or b is None else math.hypot(a[0] - b[0], a[1] - b[1])


def _tip(f):
    bl = f.debug.get('blade') or set()
    fist = _cen(f, ('fist_R',))
    if not bl or fist is None:
        return None
    return max(bl, key=lambda q: (q[0] - fist[0]) ** 2 + (q[1] - fist[1]) ** 2)


def step_moves(a, b):
    """Screen moves from frame a to b (both on the same canvas: the air is drawn in)."""
    m = {'head': _d(_cen(a, ('helmet',)), _cen(b, ('helmet',))), 'torso': _d(_cen(a, ('torso',)), _cen(b, ('torso',)))}
    la, lb = a.debug.get('legs') or {}, b.debug.get('legs') or {}
    m['feet'] = max(_d(la[k][2], lb[k][2]) for k in la) if la and set(la) == set(lb) else None
    h = [_d(_cen(a, (n,)), _cen(b, (n,))) for n in ('fist_R', 'fist_L')]
    h = [x for x in h if x is not None]
    m['hands'] = max(h) if h else None
    m['sword'] = _d(_tip(a), _tip(b))
    return m


def fmt(m):
    return ', '.join(f'{k} {v:.1f}' for k, v in m.items() if v is not None)


def timing_checks(fr):
    g = game_numbers()
    total = sum(f.dur for f in fr)
    out(total == g['total'], 'the frames last as long as the game plays the execution', f"{total} / {g['total']} sim frames")
    starts = {f.start for f in fr}
    for beat in ('leap', 'hit', 'kick', 'land'):
        out(g[beat] in starts, f'a new frame starts on the game\'s {beat} (sim frame {g[beat]})',
            next((f.name for f in fr if f.start == g[beat]), 'none'))
    for t in g['twists']:
        f = next((x for x in fr if x.start == t), None)
        out(f is not None and f.name.startswith('轉劍'), f'a twist frame starts on the game\'s twist (sim frame {t})', f.name if f else 'none')
    acc = 0
    for f in fr:
        if f.start != acc:
            out(False, 'frame starts follow their holds', f'{f.name} starts at {f.start}, previous ones end at {acc}')
            break
        acc += f.dur
    else:
        out(True, 'frame starts follow their holds')
    out(all(f.dur >= 2 for f in fr), 'every frame shows at least 2 sim frames', str(min(f.dur for f in fr)))
    return g


def lift_checks(fr, g):
    air = [(f.start, f.dur, f.air) for f in fr]
    out(air[0][2] == 0 and all(a == 0 for s, _, a in air if s < g['leap']), 'on the floor until the leap', '')
    out(all(a == 0 for s, _, a in air if s >= g['land']), 'on the floor from the landing on', '')
    out(all(a > 0 for s, _, a in air if g['leap'] < s < g['land']), 'off the floor between the leap and the landing', '')
    hit = next(a for s, _, a in air if s == g['hit'])
    out(hit >= LIFT_MIN_AT_HIT, f'up at the Boss\'s chest when the blade goes in (>= {LIFT_MIN_AT_HIT} px)', f'{hit} px')
    worst = 0.0
    bad = []
    for (s0, d0, a0), (s1, _, a1) in zip(air, air[1:]):
        speed = abs(a1 - a0) / d0
        worst = max(worst, speed)
        if speed > THROW_SPEED + 1e-6:
            bad.append(f'{s0}->{s1}: {a0}->{a1}')
    out(not bad, f'the height changes at most {THROW_SPEED} px a sim frame (the throw)', '; '.join(bad) or f'largest {worst:.1f}')
    peak = max(air, key=lambda t: t[2])
    out(None, 'INFO the leap\'s top', f'{peak[2]} px at sim frame {peak[0]}')


def step_checks(fr, view):
    bad, worst = [], {}
    for a, b in zip(fr, fr[1:]):
        m = step_moves(a, b)
        air_v = abs(b.air - a.air) / a.dur
        body = max(BODY_STEP, air_v * a.dur + BODY_STEP) if (a.air or b.air) else BODY_STEP
        hand = SWING_STEP + (abs(b.air - a.air) if (a.air or b.air) else 0)
        if b.name in BEAT_STEPS:
            _, body_b, hand_b = BEAT_STEPS[b.name]
            body, hand = max(body, body_b), max(hand, hand_b)
        over = [k for k in ('head', 'torso') if m[k] is not None and m[k] > body + 1e-6]
        over += [k for k in ('hands', 'sword') if m[k] is not None and m[k] > hand + 1e-6]
        if m['feet'] is not None and not (a.air or b.air) and m['feet'] > BODY_STEP + 1e-6 and b.name not in BEAT_STEPS:
            over.append('feet')
        for k, v in m.items():
            if v is not None:
                worst[k] = max(worst.get(k, 0), v)
        if over:
            bad.append(f'{a.name} -> {b.name}: {fmt(m)} (limits body {body:.0f}, hands {hand:.0f})')
    out(not bad, f'{view}: every step within its limit (floor: body {BODY_STEP}, hands {SWING_STEP}; air: + the throw; beats: BEAT_STEPS)',
        '; '.join(bad) or 'largest ' + fmt(worst))
    # from the idle into the first frame, and from the last frame back to the idle (the game plays idle 1 after)
    import batch1 as B1
    idle = next(f for f in B1.frames('idle', view) if f.name == 'idle 1')
    m0 = {'head': _d(_cen(idle, ('helmet',)), _shift(_cen(fr[0], ('helmet',)))),
          'torso': _d(_cen(idle, ('torso',)), _shift(_cen(fr[0], ('torso',))))}
    m1 = {'head': _d(_cen(idle, ('helmet',)), _shift(_cen(fr[-1], ('helmet',)))),
          'torso': _d(_cen(idle, ('torso',)), _shift(_cen(fr[-1], ('torso',))))}
    out(all(v is not None and v <= BODY_STEP + 1e-6 for v in m0.values()), f'{view}: idle -> first frame within {BODY_STEP} px', fmt(m0))
    out(all(v is not None and v <= BODY_STEP + 1e-6 for v in m1.values()), f'{view}: last frame -> idle within {BODY_STEP} px', fmt(m1))


def _shift(p):
    """A point on the 88 x 152 execution canvas -> the 56 x 56 idle canvas (both feet anchors)."""
    if p is None:
        return None
    _, _, ax, ay = PR.CANVAS['exec']
    return (p[0] - ax + 28, p[1] - ay + 53)


def hilt_checks(fr, view, g):
    hang = [f for f in fr if g['hit'] <= f.start < g['kick']]
    fists = [f.debug['hands']['R'] for f in hang]
    ref = fists[0]
    worst = max(_d(ref, q) for q in fists)
    out(worst <= HILT_STILL + 1e-6, f'{view}: the sword stays in the Boss: the right fist on its hilt keeps its place from the plunge to the kick (+-{HILT_STILL} px)',
        f'largest {worst:.2f} px over {len(hang)} frames')
    tips = [_tip(f) for f in hang]
    wt = max(_d(tips[0], t) for t in tips)
    out(wt <= HILT_STILL + 1.5, f'{view}: the point where the blade goes into him stays put (+-{HILT_STILL + 1.5} px)', f'largest {wt:.2f} px')
    # the hilt is turned by each twist: the crossguard is across the blade before the first twist,
    # end-on after it, across again after the second
    gh = {f.start: f.pose['sword'].get('guard_half', 2) for f in hang}
    t1, t2 = g['twists']
    prev = lambda t: gh[max(s_ for s_ in gh if s_ < t)]
    ok = gh.get(t1) == 0 and prev(t1) == 2 and gh.get(t2) == 2 and prev(t2) == 0
    out(ok, f'{view}: each twist turns the hilt a quarter on its frame (crossguard across -> end-on at {t1} -> across at {t2})',
        f'{prev(t1)} -> {gh.get(t1)} at {t1}, {prev(t2)} -> {gh.get(t2)} at {t2}')
    if view in ('east', 'west'):
        seen = min(sum(1 for q in f.debug['blade'] if f.trace.get(q) == 'sword' and q in f.px) for f in hang)
        out(seen >= 6, f'{view}: the blade shows between the fists and the Boss while he hangs (>= 6 px)', f'fewest {seen} px')


def arm_checks(fr, view):
    over, raised = [], []
    for f in fr:
        k = f.pose.get('arm_k', 1.0)
        ks = k.values() if isinstance(k, dict) else [k]
        km = max(ks)
        if km > ARM_K_MAX + 1e-6:
            over.append(f'{f.name} {km:.2f}')
        if km > HANG_K_MAX + 1e-6:
            raised.append(f.name)
    out(not over, f'{view}: arms drawn at most {ARM_K_MAX}x their length', '; '.join(over) or 'ok')
    allowed = {'上升 2', '上升 3', '上升 4', '最高 1', '最高 2', '最高 3', '下刺 1', '上升 1'}
    out(set(raised) <= allowed, f'{view}: arms longer than {HANG_K_MAX}x only while the sword is over the head', ', '.join(raised))


def leg_checks(fr, view):
    """On the floor (the rush, the crouch, the landing, standing up): knees under the hip, legs within
    their length (animation-review §4.3). In the air the legs tuck: reported."""
    bad, info = [], []
    for f in fr:
        if f.name == '站好':
            # the last frame is batch 1's rest stance (B1.REST, approved; the thrust ends on it too): its west
            # knee sits 0.02 of the way down (reported, not this animation's to change)
            knee, _ = C.leg_shape(f, view) if view in ('east', 'west') else (None, None)
            info.append(f'{f.name} (the approved rest stance) knee {knee:.2f}' if knee is not None else f'{f.name} rest stance')
            continue
        if view in ('east', 'west'):
            st = C.leg_stretch(f)
            if max(st) > 1.0 + 1e-6:
                (info if f.air else bad).append(f'{f.name} stretch {max(st):.2f}')
            knee, _ = C.leg_shape(f, view)
            if knee < 0.1 - 1e-6:
                (info if f.air else bad).append(f'{f.name} knee {knee:.2f}')
        else:
            h, _ = C.leg_shape(f, view)
            if h < 2.0 - 1e-6:
                (info if f.air else bad).append(f'{f.name} leg {h:.1f} px')
    out(not bad, f'{view}: on the floor every leg within its length, knees under the hip (fb: >= 2 px on screen)', '; '.join(bad) or 'ok')
    if info:
        out(None, f'INFO {view}: tucked legs in the air, the rest stance', '; '.join(info))


def floor_checks(fr, view):
    """Nothing below the real floor: drawn into the picture, the floor is `air` px under the feet."""
    _, _, ax, ay = PR.CANVAS['exec']
    bad = []
    for f in fr:
        low_leg = max((y for q, n in f.trace.items() if n.startswith('leg') for (x, y) in [q] if q in f.px), default=-1)
        low = max((y for (x, y) in f.px), default=-1)
        if low > ay + C.BELOW_GROUND_MAX or (not f.air and low_leg > ay + C.BELOW_GROUND_MAX):
            bad.append(f'{f.name} lowest {low}, legs {low_leg}')
    out(not bad, f'{view}: nothing below the floor (feet {C.BELOW_GROUND_MAX} px toward the camera at most)', '; '.join(bad) or 'ok')


def tech_checks(fr, view):
    """checks.pose_rows on every frame (palette, canvas, holes, pinholes, specks, piece detail, blade
    contrast); its floor row is measured on the lifted feet line, so in the air it is replaced by
    floor_checks."""
    fails, n = [], 0
    for f in fr:
        for name, ok, info in C.pose_rows('execute', f.pose, 'exec', view):
            if ok is None:
                continue
            if name.startswith('feet at most') or name.startswith('blade contrast'):
                continue
            n += 1
            if not ok:
                fails.append(f'{f.name}: {name} [{info}]')
    out(not fails, f'{view}: technical rows of every frame ({n} rows: palette, canvas, holes, pinholes, specks, detail kept, glints)',
        '; '.join(fails[:8]) + (f' (+{len(fails) - 8})' if len(fails) > 8 else ''))


def contrast_checks(fr, view):
    weak = []
    for f in fr:
        rows = [r for r in C.pose_rows('execute', f.pose, 'exec', view) if r[0].startswith('blade contrast')]
        for name, ok, info in rows:
            if ok is False:
                weak.append(f'{f.name} {info}')
    out(None, f'INFO {view}: blade contrast under {C.CONTRAST_MIN}:1 (the blade over the dark body; in the game it is over the Boss)',
        '; '.join(weak) or 'none')


def run(views=E.VIEWS):
    for v in views:
        print(f'-- {v}')
        fr = E.frames(v)
        g = timing_checks(fr) if v == views[0] else game_numbers()
        if v == views[0]:
            lift_checks(fr, g)
        step_checks(fr, v)
        hilt_checks(fr, v, g)
        arm_checks(fr, v)
        leg_checks(fr, v)
        floor_checks(fr, v)
        tech_checks(fr, v)
        contrast_checks(fr, v)
    fails = [r for r in RESULTS if r[0] is False]
    print(f'\n{sum(1 for r in RESULTS if r[0])} passed, {len(fails)} failed')
    return not fails


def selftest():
    """Break it on purpose: each must fail (animation-review §5: a check proves itself on known cases)."""
    import copy
    cases = []

    def case(name, patch):
        cases.append((name, patch))

    def move_hilt():
        # one hang frame drawn with the hilt 3 px off (as if it slid in the wound)
        pin = E.pin_fist
        calls = [0]

        def drift(pose, view, r, point):
            calls[0] += 1
            return pin(pose, view, r, PR.vadd(point, (3.0, 0.0, 2.0)) if calls[0] == 6 else point)
        E.pin_fist = drift
    case('the hilt drifts during the hang', move_hilt)

    def late_twist():
        for i, (n, s, b) in enumerate(E.FRAMES):
            if n == '轉劍 1':
                E.FRAMES[i] = (n, s + 2, b)
            if n == '轉劍 1 收':
                E.FRAMES[i] = (n, s + 2, b)
    case('the first twist two frames late', late_twist)

    def long_arms():
        E.RAISE['arm_k'] = 2.2
    case('arms drawn 2.2x at the top', long_arms)

    def low_plunge():
        for i, (n, s, b) in enumerate(E.FRAMES):
            if n == '插下去':
                E.FRAMES[i] = (n, s, lambda v: E.key(E.PLUNGE, v, 30))
    case('the plunge drawn at 30 px off the floor', low_plunge)

    def no_turn():
        E.twist.__defaults__  # noqa
        old = E.twist

        def t(k):
            p = old(k)
            p['sword'] = dict(p['sword'], guard_half=2)
            return p
        E.twist = t
        E.FRAMES[:] = [(n, s, b) for n, s, b in E.FRAMES]
    case('the hilt never turns', no_turn)

    def jump_land():
        for i, (n, s, b) in enumerate(E.FRAMES):
            if n.startswith('落下'):
                E.FRAMES[i] = (n, s, lambda v: E.key(E.FLY, v, 60))
    case('the landing drops 60 px in one frame', jump_land)

    import importlib
    import io
    import contextlib
    # the unbroken animation must pass first, or every case would "fail" for the same old reason
    importlib.reload(E)
    RESULTS.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        base = run(('east',))
    print(f"{'baseline passes' if base else 'BASELINE FAILS'}")
    ok_all = base
    for name, patch in cases:
        importlib.reload(E)
        RESULTS.clear()
        patch()
        E._CACHE.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            passed = run(('east',))
        failed = [r[1] for r in RESULTS if r[0] is False]
        print(f"{'caught' if not passed else 'MISSED'}: {name}" + (f'  <- {failed[0]}' if failed else ''))
        ok_all &= not passed
    importlib.reload(E)
    return ok_all


if __name__ == '__main__':
    if '--selftest' in sys.argv[1:]:
        sys.exit(0 if selftest() else 1)
    sys.exit(0 if run() else 1)
