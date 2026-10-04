"""Automatic checks for the Boss's hit reactions and the kneel (anim_kneel.py, export_hit.py);
exit code 1 on any failure.

    python3 tools/boss_rig/checks_hit.py [--selftest]

Measured on the finished frames where it can be (what the sprite sheets hold); "model" lines
check the numbers the poses are built from (the legs, the kneel) against limits stated here.
--selftest breaks frames on purpose and shows each check catches it.
"""
import math
import sys
import boss as B
import rig
import gait
import limb
import anim_walk as AW
import anim_kneel as K
import export_hit as E
import checks as C

GROUND = rig.AY
STEP_MAX = C.STEP_MAX                 # 16 px: a part may move this much between two poses
TIP_STEP = 80                         # px the sword's tip may move between two poses (the carry's limit)
SIDES = ('right', 'left')
# how far below the foot line a direction may draw (each with its reason):
BELOW = {'right': 1,                  # side views: everything stands on the line (the planted sword's tip is
         'left': 1,                   # 1 px under it in the approved sprite)
         'down': round(K.DEPTH * 25) + 2,   # the left foot 25 px ahead of him; the tabard lying on the ground before him
         'up': None}                  # the tucked boot behind him (towards the camera): toe_below() below


def toe_below():
    """Back view: the kneeling foot is behind him on the ground, its toe tucked under: DEPTH of
    its distance below the foot line (anim_kneel.boot_low, from the leg model), +1 for the boot's
    own last row. Only the kneel's tucked boot reaches that far; it is the lowest thing drawn."""
    worst = max(K.boot_low(K.kneel_legs(D)[0], -1) for D in range(K.D_KNEEL - 2, K.D_KNEEL + 3))
    return math.ceil(worst) + 1


BELOW['up'] = toe_below()
results = []
check = C.check
ONLY = [a for a in sys.argv[1:] if not a.startswith('--')]     # clip name filters (development)


def _sync():
    C.results = results


CELL = None          # a taller attack container for the move being checked (the cleave: anim_attack.TALL)
CELL_TOP = 0         # ... its rows above the attack container's (anim_attack.TALL_TOP)


def container(frames):
    big = not E.fits_small(frames)
    e = AW.EXT if big else 0
    t = CELL_TOP if big and CELL else 0
    W, H = (CELL or AW.BIG) if big else (rig.FW, rig.FH)
    xs = [q[0] for f in frames for q in f]
    ys = [q[1] for f in frames for q in f]
    ok = (E.MARGIN - e <= min(xs) and max(xs) < W - e - E.MARGIN and E.MARGIN - e - t <= min(ys)
          and max(ys) < H - e - t - E.MARGIN)
    return ok, (W, H), (min(xs) + e, max(xs) + e, min(ys) + e + t, max(ys) + e + t)


def technical(name, d, frames, below=None, low_frames=None):
    """low_frames: measure "below the foot line" on these instead (the attacks: the body without
    the sword - the blade held low towards the camera is drawn below the line by perspective and
    is checked in 3D, above the ground, instead)."""
    stand = rig.pixels(rig.standing()[d])
    pal = set(B.load_palette())
    bad = sorted({c for f in frames for c in f.values() if tuple(c) not in pal})
    check(f'{name} {d}: every colour in the palette', not bad, f'{len(bad)} off-palette')
    ok, size, ext = container(frames)
    check(f'{name} {d}: inside the {size[0]}x{size[1]} cell', ok, f'x {ext[0]}..{ext[1]}, y {ext[2]}..{ext[3]}')
    low = max(q[1] for f in (low_frames or frames) for q in f) - GROUND
    lim = BELOW[d] if below is None else max(BELOW[d], below)
    check(f'{name} {d}: nothing more than {lim} px below the foot line', low <= lim, f'lowest {low:+d}')
    base_isl = len(C.islands(stand))
    worst = max(len(C.islands(f)) for f in frames)
    check(f'{name} {d}: no new 1-2 px specks', worst <= base_isl, f'standing {base_isl}, worst pose {worst}')
    base_pin = len(rig.pinholes(stand))
    pin = max(len(rig.pinholes(f)) for f in frames)
    check(f'{name} {d}: no new 1 px holes', pin <= base_pin + 1, f'standing {base_pin}, worst pose {pin}')
    c0, g0 = C.detail(stand)
    cl = [C.detail(f)[0] / c0 for f in frames]
    gl = [C.detail(f)[1] / g0 for f in frames]
    print(f'     {name} {d}: after compositing, of the standing sprite: cloth-coloured {min(cl):.0%}..{max(cl):.0%}, '
          f'gold {min(gl):.0%}..{max(gl):.0%}')


def body(f, sword):
    """A frame without the sword (the pixels the sword drew that nothing covers). Bits of at most
    BLADE_BITS pixels on where the sword was drawn (or in a hole in it) and joined to nothing else
    are the blade too (a pinhole in the blade filled at the end, a blade pixel recoloured where its layers
    meet: alone 24 px over his head they read as the top of the body jumping 27 px - the cleave's
    triple slash, 2026-10-03)."""
    out = {q: c for q, c in f.items() if sword.get(q) != c}
    # on the blade: where the sword drew, or a hole in it (all four sides the sword) - not merely
    # touching it (a crown spike beside the planted blade is the body)
    near = lambda q: q in sword or all(n in sword for n in ((q[0] - 1, q[1]), (q[0] + 1, q[1]), (q[0], q[1] - 1),
                                                           (q[0], q[1] + 1)))
    seen = set()
    for q0 in [q for q in out if near(q)]:
        if q0 in seen:
            continue
        comp, todo = {q0}, [q0]
        while todo and len(comp) <= BLADE_BITS:
            x, y = todo.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n in out and n not in comp:
                        comp.add(n)
                        todo.append(n)
        seen |= comp
        if len(comp) <= BLADE_BITS and all(near(q) for q in comp):
            for q in comp:
                del out[q]
    return out


BLADE_BITS = 4


def top(f):
    return min(q[1] for q in f)


ARM_R = 26
HEAD_ROWS = 30


def grip_of(d, name, i):
    """Where the sword hand is."""
    sw, place = AW.SWORD_DRAWN.get((d, name, i), ({}, None))
    if not place:
        return None
    g = place['grip']
    return (2 * rig.AX - g[0], g[1]) if d == 'left' else g


def edges(f, grip=None):
    """Where the upper body is across the frame: the mean column of the HEAD_ROWS rows under the
    top (head, shoulders, the cape's top), without the sword and the sword arm (what is within
    ARM_R px of the grip). (Tried and dropped: the extremes of the body - as he goes down the
    knees and the cape on the ground come into any window; the middle column of the top 20
    rows, or the crown's top - they flip between the head and the cape's fur, or between two
    crown spikes of the same height, 16 px apart, in the approved walk itself.)"""
    if grip:
        f = {q: c for q, c in f.items() if math.dist(q, grip) > ARM_R}
    t = top(f)
    xs = [q[0] for q in f if q[1] < t + HEAD_ROWS]
    return (round(sum(xs) / len(xs)),)


def drawn(d, name, i):
    """The sword a pose drew (facing left: recorded in facing-right space, mirrored here)."""
    sw, place = AW.SWORD_DRAWN.get((d, name, i), ({}, None))
    if d == 'left' and sw:
        sw = {(2 * rig.AX - x, y): c for (x, y), c in sw.items()}
    return sw, place


def steps(name, d, clip, frames, before=None, before_sword=None, before_grip=None, given=None):
    """Between two poses (and from what was shown before the clip): the body's top moves at
    most STEP_MAX px; the sword's tip at most TIP_STEP px; the outline without the sword
    changes less than 30% (a fall of 14 px a pose; the walk's is < 20%)."""
    seq = ([before] if before is not None else []) + frames
    swords = ([before_sword or {}] if before is not None else []) + [drawn(d, clip.name, i)[0] for i in range(len(clip))]
    # the sword arm moves with the sword: the head and shoulders are measured without it (what is
    # within ARM_R px of the grip)
    grips = ([before_grip] if before is not None else []) + [grip_of(d, clip.name, i) for i in range(len(clip))]
    if given:
        swords = [g[0] for g in given]
        grips = [None if not g[1] else ((2 * rig.AX - g[1]['grip'][0], g[1]['grip'][1]) if d == 'left' else g[1]['grip'])
                 for g in given]
    # (the share of the outline that changes is not a measure here: a narrow side view leaning
    # 4 px changes 30% of it - it only lists how much changes)
    worst_top, worst_edge, worst_sil = 0, 0, 0.0
    for a, b, sa, sb, ga, gb in zip(seq, seq[1:], swords, swords[1:], grips, grips[1:]):
        ba, bb = body(a, sa), body(b, sb)
        worst_top = max(worst_top, abs(top(ba) - top(bb)))
        ea, eb = edges(ba, ga), edges(bb, gb)
        worst_edge = max(worst_edge, max(abs(p - q) for p, q in zip(ea, eb)))
        worst_sil = max(worst_sil, C.sil_change(ba, bb))
    check(f'{name} {d}: the top of the body moves at most {STEP_MAX} px a pose', worst_top <= STEP_MAX, f'worst {worst_top} px')
    check(f'{name} {d}: the upper body moves sideways at most {STEP_MAX} px a pose', worst_edge <= STEP_MAX,
          f'worst {worst_edge} px (outline changes up to {worst_sil:.0%})')
    tips = []
    for i in range(len(clip) if not given else 0):
        sw, place = AW.SWORD_DRAWN.get((d, clip.name, i), ({}, None))
        if place and 'axis' in place:
            tips.append(K.swd.tip_of('right' if d in SIDES else ('front' if d == 'down' else 'back'), place))
        else:
            tips.append(None)
    jumps = [math.dist(a, b) for a, b in zip(tips, tips[1:]) if a and b]
    if jumps:
        check(f'{name} {d}: the sword tip moves at most {TIP_STEP} px a pose', max(jumps) <= TIP_STEP,
              f'worst {max(jumps):.0f} px')


def same(name, a, b, what):
    n = len(set(a.items()) ^ set(b.items()))
    check(f'{name}: {what}', n == 0, f'{n} px differ')


def model_checks():
    """The legs of every pose: no leg longer than it is, no boot into the ground, the kneeling
    knee on the ground, the tucked toe on it."""
    reach = gait.THIGH + gait.SHIN
    worst_len, worst_low = 0.0, 0.0
    names = []
    for name, group in E.clips():
        for clip in group:
            for i, st in enumerate(clip.states):
                for side in ('legR', 'legL'):
                    L = st[side]
                    n = math.dist(L['hip'], L['ankle'])
                    worst_len = max(worst_len, n / reach)
                    pts = [gait.rot((gait.HEEL, -gait.ANKLE_H), L['pitch']), gait.rot((gait.BALL, -gait.ANKLE_H), L['pitch'])]
                    low = min(L['ankle'][1] + z for _, z in pts)
                    low = min(low, L['ankle'][1] - K.boot_drop(L['pitch']) + 0.0)
                    if low < -0.6:
                        names.append(f'{clip.name}:{i}:{side}')
                    worst_low = min(worst_low, low)
    check('model: no leg reaches further than it is long', worst_len <= 1.0 + 1e-6, f'longest {worst_len:.3f} of the leg')
    check('model: no boot goes into the ground', worst_low >= -0.6, f'lowest {worst_low:+.2f} px {names[:4]}')
    R, L = K.kneel_legs()
    check('model: the kneeling knee is on the ground (its joint KNEE_Z above it)', abs(R['knee'][1] - K.KNEE_Z) < 0.6,
          f'knee at {R["knee"][1]:.2f}')
    toe = R['ankle'][1] - K.boot_drop(R['pitch'])
    check('model: the tucked toe touches the ground', -0.6 <= toe <= 1.0, f'{toe:+.2f} px')
    check('model: the left foot is flat on the ground ahead of him', L['pitch'] == 0 and abs(L['ankle'][1] - gait.ANKLE_H) < 0.01
          and L['ankle'][0] > 15, f'ankle {L["ankle"][0]:.1f} ahead')
    check('model: the thighs are as long as they are', all(abs(math.dist(X['hip'], X['knee']) - gait.THIGH) < 0.05 for X in (R, L)),
          ', '.join(f'{math.dist(X["hip"], X["knee"]):.2f}' for X in (R, L)))
    # the knee on the ground, as drawn (side view): the kneeling leg's lowest pixel on the foot line
    pix = limb.leg_pixels(R)
    lowest = max(q[1] for q in pix)
    check('kneel right: the kneeling leg rests on the foot line', abs(lowest - GROUND) <= 1, f'lowest row {lowest - GROUND:+d}')


def sword_checks():
    """The planted sword in the kneel is the approved sword pushed D_KNEEL px into the ground in
    every direction (one 3D pose); nothing of it below the ground; the bowed head's detail."""
    for d in rig.DIRS:
        kneel = E.frames(K.kneel_down())[d][-1]
        sw, place = AW.SWORD_DRAWN[(d, 'kneel_down', len(K.kneel_down()) - 1)]
        stand_sw = AW._layers('right' if d in SIDES else d)['layers']['sword'].pix
        h0 = max(q[1] for q in stand_sw) - min(q[1] for q in stand_sw) + 1
        h1 = max(q[1] for q in sw) - min(q[1] for q in sw) + 1
        sink = h0 - h1
        check(f'kneel {d}: the sword goes {K.D_KNEEL} px into the ground (lean included)', abs(sink - K.D_KNEEL) <= 6,
              f'{sink} px of it gone ({h1} of {h0} px show)')
    over = []
    for name, group in E.clips():
        for clip in group:
            for d in rig.DIRS:
                g = K.GROUND['right' if d in SIDES else d]
                for i in range(len(clip)):
                    sw, place = AW.SWORD_DRAWN.get((d, clip.name, i), ({}, None))
                    st = clip.states[i]
                    if (st.get('planted') or st.get('sink')) and sw and max(q[1] for q in sw) > g:
                        over.append(f'{clip.name}:{i}:{d}')
    check('the planted sword: nothing of it below the ground', not over, ', '.join(over[:6]))
    # the turned heads (side views) keep the approved head's gold and red
    approved = AW._layers('right')['layers']['head'].pix
    g0 = sum(1 for c in approved.values() if rig.is_gold(c))
    r0 = sum(1 for c in approved.values() if B.kind(c) == 'red' or (c[0] > 150 and c[0] > c[1] + 70))
    bows = sorted({round(st.get('bow', 0)) for _, group in E.clips() for clip in group for st in clip.states} - {0})
    worst = []
    for bw in bows:
        h = K.head_side(bw)
        g = sum(1 for c in h.values() if rig.is_gold(c)) / g0
        worst.append((g, bw))
    lo, hi = min(worst), max(worst)
    check('the turned heads keep the approved head\'s gold (85%..115%)', lo[0] >= 0.85 and hi[0] <= 1.15,
          f'{lo[0]:.0%} (bow {lo[1]}) .. {hi[0]:.0%} (bow {hi[1]})')


def join_checks():
    """Each clip starts from what was shown before it and ends on what comes next."""
    stand = {d: rig.pixels(rig.standing()[d]) for d in rig.DIRS}
    kd = E.frames(K.kneel_down())
    kneel = {d: kd[d][-1] for d in rig.DIRS}
    for d in rig.DIRS:
        st = E.frames(K.stagger())[d]
        same(f'stagger {d}', st[-1], stand[d], 'ends on the standing sprite')
        for kind in AW.KINDS:
            loop = AW.frames(d, kind)
            for e in K.STOP_FROM:
                # the legs stay where the loop had them; the cape and the tabard swing as the
                # loop's last poses had them swinging, not exactly: the loop goes on from the next
                # pose within the step limits
                c = K.stagger(kind, e)
                fr = E.frames(c)[d]
                n = len(set(fr[-1].items()) ^ set(loop[e].items()))
                print(f'     {c.name} {d}: the last pose differs from the loop\'s pose {e} in {n} px (the cloth)')
                nxt = (e + 1) % gait.POSES
                steps(f'{c.name} -> loop {nxt}', d, AW.Clip(c.name + '_join', [None, None], None), [fr[-1], loop[nxt]],
                      None, None, None, [drawn(d, c.name, len(c) - 1), drawn(d, kind, nxt)])
            for e in K.STOP_FROM:
                fr = E.frames(K.walk_kneel(kind, e))[d]
                same(f'{kind}_kneel_{e} {d}', fr[-1], kneel[d], 'ends on the kneel')
            c = K.carry_start(kind)
            cs = E.frames(c)[d]
            j = AW.START_JOINS[kind]
            steps(f'{c.name} -> loop {j}', d, AW.Clip(c.name + '_join', [None, None], None), [cs[-1], loop[j]],
                  None, None, None, [drawn(d, c.name, len(c) - 1), drawn(d, kind, j)])
        same(f'rise {d}', E.frames(K.rise())[d][-1], stand[d], 'ends on the standing sprite')
        same(f'transition {d}', E.frames(K.transition())[d][-1], stand[d], 'ends on the standing sprite')
        same(f'transition_kneel {d}', E.frames(K.transition(True))[d][-1], stand[d], 'ends on the standing sprite')
        same(f'executed {d}', E.frames(K.executed())[d][0], kneel[d], 'starts on the kneel')
        same(f'executed {d}', E.frames(K.executed())[d][-1], kneel[d], 'ends on the kneel')
        same(f'breathe {d}', E.frames(K.breathe())[d][0], kneel[d], 'starts on the kneel')
        de = E.frames(K.death())[d]
        check(f'death {d}: starts with the kneel_down', all(set(a.items()) == set(b.items()) for a, b in zip(de, kd[d])), '')
        # the kneel_down's first pose: the hit lands on the standing pose - the legs do not move yet
        below = lambda f: {q: c for q, c in f.items() if q[1] > 150}
        n = len(set(below(kd[d][0]).items()) ^ set(below(stand[d]).items()))
        print(f'     kneel_down {d}: pose 0 differs from the standing sprite below row 150 in {n} px (the cape\'s hem swings)')


def breath_checks():
    for d in rig.DIRS:
        fr = E.frames(K.breathe())[d]
        tops = [top(f) for f in fr]
        moves = [abs(a - b) for a, b in zip(tops, tops[1:] + tops[:1])]
        check(f'breathe {d}: the head moves at most 2 px a pose, around the loop', max(moves) <= 2, f'tops {tops}')


def clip_checks():
    stand = {d: rig.pixels(rig.standing()[d]) for d in rig.DIRS}
    for name, group in E.clips():
        for clip in group:
            if ONLY and not any(o in clip.name for o in ONLY):
                continue
            kind = clip.states[0].get('kind', 'walk')
            for d in rig.DIRS:
                fr = E.frames(clip)[d]
                # moving sideways the foot towards the camera is lower: no lower than in the loop it comes from
                # (+1: the same foot drawn with the knee bent another way can come out 1 px lower)
                src_low = max(q[1] for f in AW.frames(d, kind) for q in f) - GROUND + 1 if kind != 'walk' else None
                technical(clip.name, d, fr, src_low)
                b = clip.before(0)
                before_sword = None
                before_grip = None
                if b is K.STAND or b is AW.STAND:
                    before = stand[d]
                    g = K.swd.standing(rig.VIEW_OF.get(d, 'right'))['grip']
                    before_grip = (2 * rig.AX - g[0], g[1]) if d == 'left' else g
                elif clip.name.startswith(tuple(f'{k}_' for k in AW.KINDS)) and '_cstart' not in clip.name:
                    e = (int(clip.name.rsplit('_', 1)[1]) - 1) % gait.POSES
                    before = AW.frames(d, kind)[e]
                    before_sword = drawn(d, kind, e)[0]
                    before_grip = grip_of(d, kind, e)
                elif clip.name in ('executed', 'kneel_breathe', 'transition_kneel'):
                    before = E.frames(K.kneel_down())[d][-1]
                    before_grip = grip_of(d, 'kneel_down', len(K.kneel_down()) - 1)
                else:
                    before = None
                steps(clip.name, d, clip, fr, before, before_sword, before_grip)


def main():
    _sync()
    if not ONLY:
        model_checks()
        sword_checks()
        join_checks()
        breath_checks()
    clip_checks()
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Break frames on purpose: each must be caught."""
    global results
    caught = []
    _sync()
    d = 'right'
    clip = K.kneel_down()
    fr = [dict(f) for f in E.frames(clip)[d]]
    # a head that jumps 20 px, a pixel under the ground, an off-palette colour
    bad = [dict(f) for f in fr]
    bad[3] = {(x, y - 20 if y < 150 else y): c for (x, y), c in bad[3].items()}
    bad[4][(128, GROUND + 4)] = B.load_palette()[5]
    bad[5][(128, 150)] = (1, 2, 3)
    results.clear()
    technical('selftest', d, bad)
    steps('selftest', d, clip, bad, rig.pixels(rig.standing()[d]))
    caught.append(results.count(False) >= 3)
    # a stagger that does not come back to the standing sprite (1 px)
    results.clear()
    f = dict(E.frames(K.stagger())[d][-1])
    f.pop(next(iter(f)))
    same('selftest stagger', f, rig.pixels(rig.standing()[d]), 'ends on the standing sprite')
    caught.append(results.count(False) == 1)
    # a sword tip that jumps 120 px between two poses
    results.clear()
    c = K.walk_kneel('walk', 0)
    E.frames(c)
    key = (d, c.name, 3)
    sw, place = AW.SWORD_DRAWN[key]
    AW.SWORD_DRAWN[key] = (sw, dict(place, grip=(place['grip'][0] + 120, place['grip'][1])))
    steps('selftest tip', d, c, E.frames(c)[d])
    AW.SWORD_DRAWN[key] = (sw, place)
    caught.append(results.count(False) >= 1)
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
