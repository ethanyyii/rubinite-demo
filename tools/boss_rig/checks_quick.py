"""Automatic checks for the quick combo's two one-handed slashes (attacks.quick, export_quick.py);
exit code 1 on any failure.

    python3 tools/boss_rig/checks_quick.py [--selftest]

The attack checks (checks_attack: the 3D model at every combat frame, the finished frames, the
hands, starting from a move) run on these clips too; the feet are checked for one-handed cuts,
and what the user asked for on 2026-10-02 is measured:
  "the first cut sweeps from right to left, the second from left to right ('橫掃': level)" -
      while each hit box is on the blade sweeps the sector from his right (first) / his left
      (second), and it is level: the tip stays below the player's height (40 px) and above
      the ground the whole time, the blade's slope changes by at most LEVEL_SPREAD degrees
  "mind the weight - swinging the first cut the body turns much more than with two hands, the
      whole body turns" - from the windup to the follow-through the hips turn at least
      HIP_TURN_K times as far as the two-handed royal sweep's (attacks.c1, read from its clip:
      an independent standard), the chest at least CHEST_TURN_K times; the hips start turning
      no later than the chest (the turn comes from the legs, not the arms); the weight goes
      onto the stepping foot (checks_attack); in the front and back views the upper body and
      the head swing over to the side he turns to (measured on the frames, at least
      SWAY_MIN px from the carry, the right way); the free left fist travels at least
      FREE_ARM_MIN px on screen about its own shoulder in every view (it swings
      with him, it does not hang stiff)
One-handed, the cut's own side leads: both cuts step the right foot (the sword arm's) - the
first in with the forehand, the second further on with the backhand (STEP_MIN forward) - landing
with the blow; never two feet at once; he does not move (no game step).
"""
import math
import sys
import rig
import attacks as AT
import attack3d as A
import anim_attack as AA
import checks as C
import checks_hit as H
import checks_attack as CA
import export_quick as EQ
import export_size

results = CA.results
QUICK_REACH = export_size.RANGES['quick']   # the quick slashes' hit box radius (veltharis_data QUICK_SWEEP_RADIUS)
check = C.check
LEVEL_SPREAD = 8.0    # degrees: the blade's slope through a level sweep (the royal sweep's falls 28)
HIP_TURN_K = 2.0      # the hips' turn, windup to follow-through, against the royal sweep's
CHEST_TURN_K = 1.4    # the chest's
SWAY_MIN = 4          # px the head's column moves sideways in the front / back views
FREE_ARM_MIN = {'down': 12.0, 'up': 12.0, 'right': 30.0, 'left': 30.0}
                      # px the free left fist travels on screen about its shoulder between the windup and the
                      # follow-through. The side views: an arm left hanging is still carried 20-21 px forward
                      # and back by a 70-80 degree turn (selftest), so the arm's own swing must show above that


def turn_range(clip, a, b, key):
    vals = [clip.at(t)[key] for t in range(a, b)]
    return max(vals) - min(vals), vals


def level_checks(m):
    clip = m.clip
    for (start, n), side_ in zip(m.hits, ('right', 'left')):
        sts = [clip.at(t) for t in range(start, start + n)]
        psis = [A.angles(s['axis'])[0] for s in sts]
        els = [A.angles(s['axis'])[1] for s in sts]
        zs = [A.tip(s)[2] for s in sts]
        from_side = (psis[0] > 0) == (side_ == 'right') and (psis[-1] > 0) != (psis[0] > 0)
        check(f'{m.sheet}: hit {start} sweeps from his {side_} across to the other side', from_side,
              'azimuths ' + ' '.join(f'{p:.0f}' for p in psis))
        ok = max(zs) <= CA.PLAYER_HEIGHT and min(zs) > 4 and max(els) - min(els) <= LEVEL_SPREAD
        check(f'{m.sheet}: hit {start} is level (tip below {CA.PLAYER_HEIGHT:.0f} px all through, slope within '
              f'{LEVEL_SPREAD:.0f} degrees)', ok, f'tip {min(zs):.0f}..{max(zs):.0f} px up, slope {min(els):.0f}..{max(els):.0f}')


def turn_checks(m):
    clip, c1 = m.clip, AT.c1()
    ht0, _ = turn_range(c1, 0, AT.W + 30, 'ht')
    tw0, _ = turn_range(c1, 0, AT.W + 30, 'tw')
    a, b = 0, AT.Q1 + 10
    ht1, hts = turn_range(clip, a, b, 'ht')
    tw1, tws = turn_range(clip, a, b, 'tw')
    check(f'{m.sheet}: the first cut turns the hips {HIP_TURN_K}x and the chest {CHEST_TURN_K}x as far as the '
          f'two-handed royal sweep', ht1 >= HIP_TURN_K * ht0 and tw1 >= CHEST_TURN_K * tw0,
          f'hips {ht1:.0f} (royal sweep {ht0:.0f}), chest {tw1:.0f} (royal sweep {tw0:.0f}) degrees')
    # the hips lead: they start turning towards the cut no later than the chest does
    def first_turn(vals):
        lo = min(range(len(vals)), key=lambda i: vals[i])
        return next(i for i in range(lo, len(vals) - 1) if vals[i + 1] - vals[i] > 0.5)
    fh, fc = first_turn(hts), first_turn(tws)
    check(f'{m.sheet}: the first cut\'s turn comes from the hips (they start round no later than the chest)',
          fh <= fc, f'hips from frame {a + fh}, chest from frame {a + fc}')
    ht2, _ = turn_range(clip, 48, AT.Q2 + 10, 'ht')
    tw2, _ = turn_range(clip, 48, AT.Q2 + 10, 'tw')
    check(f'{m.sheet}: the second cut turns the whole body back too (hips at least the royal sweep\'s)',
          ht2 >= ht0 and tw2 >= tw0, f'hips {ht2:.0f}, chest {tw2:.0f} degrees')


HELMET_ROWS = 10      # the helmet's top rows: the free left arm flung up beside the head is not in them
                      # (H.HEAD_ROWS, 30, took it in and read the back view's sway the wrong way)


def head_x(f):
    t = H.top(f)
    xs = [q[0] for q in f if q[1] < t + HELMET_ROWS]
    return sum(xs) / len(xs)


def sway_checks(m):
    """Front and back views: at each follow-through the head has swung over to the side he turns
    to (his left after the forehand, his right after the backhand)."""
    fr = m.frames()
    for t, his in ((AT.Q1 + 8, 'left'), (AT.Q2 + 8, 'right')):
        i = m.times.index(max(x for x in m.times if x <= t))
        for d in ('down', 'up'):
            sw0 = AA.AW.SWORD_DRAWN.get((d, 'carry', 0), ({}, None))[0]
            sw = CA.drawn(d, m.states[i]['name'], i)[0]
            x0 = head_x(H.body(fr[d][0], sw0))
            x1 = head_x(H.body(fr[d][i], sw))
            screen_right = (his == 'left') == (d == 'down')
            dx = x1 - x0
            check(f'{m.sheet} {d}: after the cut at {t} the head swings over to his {his}', (dx if screen_right else -dx) >= SWAY_MIN,
                  f'{dx:+.1f} px')


def free_arm_checks(m):
    for d in rig.DIRS:
        pts = []
        for s in m.states:
            if AT.Q1 - 12 <= s['t'] <= AT.Q2 + 10:
                J = AA.JOINTS.get((d, s['name'], s['i'], 'L'))
                if J:
                    # relative to its own shoulder: the hanging place already rides the turning body
                    pts.append((J['hand'][0] - J['shoulder'][0], J['hand'][1] - J['shoulder'][1]))
        span = max((math.dist(p, q) for p in pts for q in pts), default=0.0)
        check(f'{m.sheet} {d}: the free left fist swings with him ({FREE_ARM_MIN[d]:.0f}+ px on screen from its shoulder)',
              span >= FREE_ARM_MIN[d],
              f'{span:.0f} px over {len(pts)} poses')


STROKE_LEAD = 3       # frames before a hit box: the stroke under way
ELBOW_MAX = 50.0      # degrees the sword arm's elbow may bend through a stroke (the second version: up to 47 with
                      # the windup's bent arm opening on the way - the forearm whipped round by the elbow)
UPPER_SHARE = 0.8     # the upper arm turns at least this share of the forearm's turn through a stroke
PLATE_SWING = 15.0    # degrees the front view's shoulder plate turns through a stroke (the second version: 0, pinned)
ARM_STRAIGHT = 0.9     # the sword arm at each blow: its fist at least this share of the arm's length from the shoulder
LEFT_SIDE = -12.0     # px: the free left fist stays at least this far on his own left of his middle (upper body's frame)
LEFT_BELOW = 10.0     # px: ... and this far below its shoulder


def arm_checks(m):
    """User 2026-10-02 (after the first version): "the right arm must reach out as he swings, so
    it carries the body's weight; the left hand has many problems - with the first cut it turns
    towards the right hand, with the second it twists straight out". At each blow the sword arm
    is straight (its fist ARM_STRAIGHT of the arm's length from its shoulder); at every frame the
    free left fist is on his own left (LEFT_SIDE, in the upper body's frame: it does not cross to
    the right hand) and below its shoulder (LEFT_BELOW: not flung out level)."""
    clip = m.clip
    for start, n in m.hits:
        mid = min(range(start, start + n), key=lambda t: abs(A.angles(clip.at(t)['axis'])[0]))
        sh, e, g, _ = A.arms(clip.at(mid))['R']
        share = A.norm(A.sub(g, sh)) / A.ARM
        check(f'{m.sheet}: hit {start}: the sword arm reaches out straight ({ARM_STRAIGHT:.0%}+ of its length)',
              share >= ARM_STRAIGHT, f'{share:.0%} at frame {mid}')
    # User 2026-10-02 (after the second version): "the swing still feels like only the elbow
    # turning the forearm; the shoulder must carry the upper arm round - the upper arm always
    # moves". Through each stroke (STROKE_LEAD frames before the hit box to its end) the elbow
    # stays nearly straight (ELBOW_MAX), the upper arm turns at least UPPER_SHARE as far as the
    # forearm, and the front / back views' shoulder plate turns PLATE_SWING degrees or more
    for start, n in m.hits:
        ts = range(start - STROKE_LEAD, start + n)
        bends, uppers, fores = [], [], []
        for t in ts:
            sh, e, g, _ = A.arms(clip.at(t))['R']
            u, f = A.unit(A.sub(e, sh)), A.unit(A.sub(g, e))
            bends.append(math.degrees(math.acos(max(-1.0, min(1.0, A.dot(u, f))))))
            uppers.append(u)
            fores.append(f)
        turn = lambda vs: sum(math.degrees(math.acos(max(-1.0, min(1.0, A.dot(a, b))))) for a, b in zip(vs, vs[1:]))
        tu, tf = turn(uppers), turn(fores)
        plates = [AA.plate_turn('down', 'R', clip.at(t)) for t in ts]
        check(f'{m.sheet}: hit {start}: the shoulder carries the upper arm round (elbow within {ELBOW_MAX:.0f} degrees of '
              f'straight, the upper arm turning {UPPER_SHARE:.0%}+ as far as the forearm, the plate {PLATE_SWING:.0f}+ degrees)',
              max(bends) <= ELBOW_MAX and tu >= UPPER_SHARE * tf and max(plates) - min(plates) >= PLATE_SWING,
              f'elbow {min(bends):.0f}..{max(bends):.0f}, upper arm {tu:.0f} / forearm {tf:.0f} degrees, plate '
              f'{max(plates) - min(plates):.0f}')
    worst_side, worst_up, where = -99.0, -99.0, None
    for t in range(m.total):
        st = clip.at(t)
        a = A.arms(st)['L']
        if a is None or st.get('two', 0.0) > 0:
            continue
        sh, e, g, _ = a
        mid = A.mul(A.add(A.shoulder('L', st), A.shoulder('R', st)), 0.5)
        r = A.yaw(A.sub(g, mid), -st['tw'])[1]
        up = g[2] - (sh[2] - LEFT_BELOW)
        if r > worst_side:
            worst_side, where = r, t
        worst_up = max(worst_up, up)
    check(f'{m.sheet}: the free left fist stays on his left ({-LEFT_SIDE:.0f}+ px out from his middle) and '
          f'{LEFT_BELOW:.0f}+ px below its shoulder', worst_side <= LEFT_SIDE and worst_up <= 0,
          f'nearest the middle {-worst_side:.0f} px out (frame {where}); at its highest {LEFT_BELOW - worst_up:.0f} px below '
          f'the shoulder')


PLATE_KEEP = 0.85     # the sword shoulder's plate keeps this share of its pixels in every front / back pose
PIECE_MAX = 40        # px: a piece of the figure cut off from the rest


def pieces(f, mx=PIECE_MAX):
    """Sizes of the pieces of frame f of mx px or fewer that touch nothing else (8-neighbours)."""
    pix, seen, out = set(f), set(), []
    for q0 in pix:
        if q0 in seen:
            continue
        n, stack = 0, [q0]
        seen.add(q0)
        while stack:
            x, y = stack.pop()
            n += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pix and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if n <= mx:
            out.append(n)
    return out


def plate_checks(m):
    """User 2026-10-02 (after the third version): "in the front view the right shoulder plate and
    arm disappear as he swings" - warped with the turned chest the plate was squeezed to a
    quarter (503 px to 137), and moved to the middle with the cape left wide behind it; pieces of
    the shoulder were cut off beside the head. In every front / back pose the sword shoulder's
    plate keeps PLATE_KEEP of its pixels, and no frame has more cut-off pieces (PIECE_MAX) than the
    carry it starts from (the side views' carry has one: a rag of the cape's hem)."""
    sizes = []
    _rp = AA.rotate_pixels

    def counting(pix, pivot, deg, k=4):
        out = _rp(pix, pivot, deg, k)
        sizes.append(len(out))
        return out
    worst, where = 9.0, None
    rest = len(AA.extra('down')['plateR'].pix)
    AA.rotate_pixels = counting
    try:
        for i in range(1, len(m.states)):
            if m.states[i]['t'] >= m.last:
                continue
            for d in ('down', 'up'):
                sizes.clear()
                AA.render_pose(d, m.states[i], m.states[i - 1])
                r = sizes[0] / (rest if d == 'down' else len(AA.extra('up')['plateR'].pix))
                if r < worst:
                    worst, where = r, (d, m.states[i]['t'])
    finally:
        AA.rotate_pixels = _rp
    check(f'{m.sheet}: the sword shoulder\'s plate keeps {PLATE_KEEP:.0%} of itself in every front / back pose',
          worst >= PLATE_KEEP, f'smallest {worst:.0%} ({where})')
    fr = m.frames()
    for d in rig.DIRS:
        base = len(pieces(fr[d][0]))
        bad = [(m.times[i], p) for i, f in enumerate(fr[d]) for p in [pieces(f)] if len(p) > base]
        check(f'{m.sheet} {d}: no piece of the figure cut off from it (no more than the carry\'s {base})', not bad,
              str(bad[:4]))


def feet_checks(m):
    """One-handed: the right foot steps with each cut."""
    clip = m.clip
    sts = [clip.at(t) for t in range(m.total)]
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {m.sheet}: one foot at a time', not both, str(both[:8]))
    hx_jump = max(abs(CA.hips_at(b) - CA.hips_at(a)) for a, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a['D']) for a, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump (at most {CA.HIP_STEP_X} px forward/back, {CA.HIP_STEP_D} px a frame)',
          hx_jump <= CA.HIP_STEP_X and d_jump <= CA.HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    first = m.hits[0][0] - CA.STEP_LEAD
    wind = sts[:first]
    planted = all(CA.foot_at(s, k)[0] == (0.0, 0.0, 0.0) and not CA.foot_at(s, k)[1] for s in wind for k in 'RL')
    hx_w = max(abs(CA.hips_at(s)) for s in wind)
    d_w = max(s['D'] for s in wind)
    check(f'feet {m.sheet}: the windup is the upper body\'s (feet planted, hips within {CA.WINDUP_HX} px and '
          f'{CA.WINDUP_D} px down until frame {first})', planted and hx_w <= CA.WINDUP_HX and d_w <= CA.WINDUP_D,
          f'feet {"planted" if planted else "MOVED"}, hips {hx_w:.1f} px, {d_w} px down')
    check(f'feet {m.sheet}: the left foot never leaves its spot (it pivots on the ball)', not runs['L'], str(runs['L']))
    for start, n in m.hits:
        mid = min(range(start, start + n), key=lambda t: abs(A.angles(clip.at(t)['axis'])[0]))
        r = [r_ for r_ in runs['R'] if r_[0] <= mid + 1 and r_[1] >= mid - 10]
        if not r:
            check(f'feet {m.sheet}: hit {start} steps the right foot', False, 'no step')
            continue
        a, b = r[0]
        fwd = CA.foot_at(sts[b], 'R')[0][0] - CA.foot_at(sts[a - 1], 'R')[0][0]
        check(f'feet {m.sheet}: hit {start} steps the right foot {CA.STEP_MIN:.0f}+ px forward, landing with the blow '
              f'(frame {mid} +-{CA.LAND_SLACK})', abs(b - mid) <= CA.LAND_SLACK and fwd >= CA.STEP_MIN,
              f'off the ground {a}..{b - 1}, lands {b}, {fwd:.0f} px forward')
        st = sts[mid]
        front, back_ = CA.foot_at(st, 'R')[0][0], CA.foot_at(st, 'L')[0][0]
        share = (CA.hips_at(st) - back_) / max(1e-6, front - back_)
        tp = A.tip(st)
        rr = math.hypot(tp[0], tp[1])
        check(f'feet {m.sheet}: hit {start}: the weight on the front foot ({CA.WEIGHT_FWD:.0%}+), the chest leaning '
              f'{CA.LEAN_MIN:.0f}+', share >= CA.WEIGHT_FWD and st['lx'] >= CA.LEAN_MIN,
              f'hips {share:.0%}, lean {st["lx"]:.0f} (frame {mid})')
        check(f'feet {m.sheet}: hit {start}: the blade reaches {QUICK_REACH:.0f} px (the hit box) below the player\'s height',
              rr >= QUICK_REACH and tp[2] <= CA.PLAYER_HEIGHT, f'tip {rr:.0f} px out, {tp[2]:.0f} px up')


def game_radius_checks():
    """The game's radius for the two quick slashes (veltharis_data.gd) is the one the art is
    checked against."""
    import os
    import re
    import boss as B
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    r = float(re.search(r'const QUICK_SWEEP_RADIUS := ([0-9.]+)', src).group(1))
    light = re.search(r'static func _quick_light.*?"radius": (\w+)', src, re.S).group(1)
    check('boss_quick: the game\'s quick slash radius (veltharis_data) is the art\'s', r == QUICK_REACH and
          light == 'QUICK_SWEEP_RADIUS', f'{r:.0f} / {QUICK_REACH} ({light})')


def distinct_checks(m):
    fr = m.frames()
    pairs = [('windup', 14, 48), ('follow-through', AT.Q1 + 8, AT.Q2 + 8)]
    for label, t1, t2 in pairs:
        i = m.times.index(max(t for t in m.times if t <= t1))
        j = m.times.index(max(t for t in m.times if t <= t2))
        for d in rig.DIRS:
            v = C.sil_change(fr[d][i], fr[d][j])
            check(f'{m.sheet} {d}: the two cuts\' {label}s differ in outline by {CA.DISTINCT:.0%} or more', v >= CA.DISTINCT,
                  f'{v:.0%} (frames {m.times[i]} / {m.times[j]})')


def main(only=None):
    CA._sync()
    ms = EQ.moves()
    q, b = ms
    for m in ms:
        CA.model_checks(m)
        if m.hits:
            feet_checks(m)
            level_checks(m)
            turn_checks(m)
            arm_checks(m)
        else:
            CA.feet_checks(m)
        CA.entry_feet_checks(m)
        CA.frame_checks(m)
        CA.hands_checks(m)
    plate_checks(q)
    sway_checks(q)
    game_radius_checks()
    free_arm_checks(q)
    distinct_checks(q)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """A quick slash with the first version's arms must fail the arm check; one with the old
    turn (hips and chest as far as the royal sweep) must fail the turn check; a sweep that
    falls like the royal sweep must fail the level check; a stiff left arm must fail."""
    CA._sync()
    caught = []
    m = EQ.moves()[0]
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    for t, k in keys:
        k['ht'] = k['ht'] * 0.45
        k['tw'] = k['tw'] * 0.6
    small = EQ.E.Move(m.sheet, AT.Clip('quick_small', keys, AT.quick_steps(), whole_turn=True), m.total, m.hits, m.caption)
    results.clear()
    turn_checks(small)
    caught.append(results.count(False) >= 1)
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    for t, k in keys:
        if t == AT.Q1:
            k['dir'] = (78.0, 3.0)
    fall = EQ.E.Move(m.sheet, AT.Clip('quick_fall', keys, AT.quick_steps(), whole_turn=True), m.total, m.hits, m.caption)
    results.clear()
    level_checks(fall)
    caught.append(results.count(False) >= 1)
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    for t, k in keys:
        k['lhand'] = (0.0, 0.0, 0.0)
    stiff = EQ.E.Move(m.sheet, AT.Clip('quick_stiff', keys, AT.quick_steps(), whole_turn=True), m.total, m.hits, m.caption)
    stiff.frames()
    results.clear()
    free_arm_checks(stiff)
    caught.append(results.count(False) >= 4)
    # the first version's arms: bent at the blow, the left hand across to the right, flung out level
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    for t, k in keys:
        if t == AT.Q1 + 3:
            k['fist'] = (58.0, 6.0, 86.0)
        if t == 14:
            k['lhand'] = (20.0, 18.0, 24.0)
        if t == AT.Q2 + 5:
            k['lhand'] = (-22.0, -14.0, 40.0)
    v1 = EQ.E.Move(m.sheet, AT.Clip('quick_v1', keys, AT.quick_steps(), whole_turn=True), m.total, m.hits, m.caption)
    results.clear()
    arm_checks(v1)
    caught.append(results.count(False) >= 2)
    # the second version's: the plate not swinging, the windup's arm bent
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    for t, k in keys:
        k['swing'] = 0.0
        if t == AT.Q1 - 3:
            k['fist'] = (6.0, 42.0, 98.0)
    v2 = EQ.E.Move(m.sheet, AT.Clip('quick_v2', keys, AT.quick_steps(), whole_turn=True), m.total, m.hits, m.caption)
    results.clear()
    arm_checks(v2)
    caught.append(results.count(False) >= 1)
    keys = [(t, dict(k)) for t, k in m.clip.keys]
    st = AT.quick_steps()
    st['L'] = [(50, AT.STAND), (58, (10.0, 0.0, AT.gait.ANKLE_H, 0.0))]
    for t, k in keys:
        if t >= 58:
            k['feet'] = dict(k['feet'], L=(10.0, 0.0, AT.gait.ANKLE_H, 0.0))
    hop = EQ.E.Move(m.sheet, AT.Clip('quick_hop', keys, st, whole_turn=True), m.total, m.hits, m.caption)
    results.clear()
    feet_checks(hop)
    caught.append(results.count(False) >= 2)
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
