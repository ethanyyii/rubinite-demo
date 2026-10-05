"""Automatic checks for the ash spin (灰燼迴旋, C6 迴旋, attacks.spin, export_spin.py); exit code 1 on any failure.

    python3 tools/boss_rig/checks_spin.py [--selftest]

The attack checks (checks_attack: the finished frames, the hands) run on these clips too. What is new for a turn
right round (user 2026-10-04: "迴旋用右手單手拿劍轉一圈的過程蹲下，所以轉完會是蹲下狀態"; one turn, one hit):
  - the game's numbers (veltharis_data.gd ash_spin: one hit, the windup, the 0.25 s hit box, the recovery, the
    bounce, the circle's radius) are the art's
  - the 3D model at every combat frame: the arms reach, the blade misses the body; the legs measured in the frame
    the body is turned to (the leg model is the facing's side plane)
  - the windup: the sword off the shoulder, trailing behind him on his right with its tip on the ground (touching
    it, not in it); the body coiled to his right before the turn
  - the turn: one-handed (the left hand free), round to his left the whole way; while the hit box is on the tip goes
    round the full circle (one frame to the next at most 30 degrees), 0.9 x the radius out or more, at the player's
    height; he crouches and bends over as he turns (at the start up, at the end down); every sheet row is drawn with
    all four facings in turn (the renderer turns the facing with the body)
  - the feet: the left foot is the pivot (in under him before the turn, never leaving its place until the recovery,
    on the ball through the turn), the right foot is off the ground through the turn and lands behind him; one foot
    at a time, the hips never jump
  - crouched still after the turn (the opening), the blade low before him on his left; the carry at the end
  - the flat never flashes round between two poses (beyond the blade's own swing)
  - the coil reads apart from every other attack's windup
"""
import math
import os
import re
import sys
import boss as B
import rig
import attacks as AT
import attack3d as A
import anim_attack as AA
import checks as C
import checks_attack as CA
import checks_cleave as CC
import checks_upswing as CU
import export_spin as ES

results = CA.results
check = C.check
REACH_SHARE = 0.9           # the tip at least this share of the radius out through the hit box
TURN_STEP = 30.0            # degrees the tip may go round from one frame to the next
FULL = 360.0                # degrees round through the hit box (its frames and the one after: 15 steps)
FULL_SLACK = 6.0
DRAG_TIP = (-0.5, 4.0)      # px: the dragged tip touches the ground (the curve between the keys dips half a px)
DRAG = (23, 50)             # frames the blade is dragged
DRAG_BEHIND = 40.0          # px the dragged tip is behind him, and out to his right
COIL = -45.0                # degrees: the hips and chest coiled to his right before the turn, at least
START_D = 14                # px down as the turn starts, at most
END_D = 25                  # ... and as it completes, at least, bent over END_BEND
END_BEND = 28.0
HOLD_D = 24
HOLD_STILL = 4.0


def faced(s):
    """The state in the frame the body is turned to (anim_attack.render_spun's)."""
    k = AA.spin_quarters(s)
    return AA.spun(s, k, strict=False) if k % 4 else dict(s, tw=s['tw'] - 90 * k, ht=s['ht'] - 90 * k)


def game_numbers():
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    f = re.search(r'out\[&"ash_spin"\] = _move\(.*?\], ([0-9.]+), near_step', src, re.S)
    body = f.group(0)
    hits = re.findall(r'_hit\(\{(.*?)\}\)', body, re.S)
    num = lambda pat, s: float(re.search(pat, s).group(1))
    return {'hits': len(hits), 'interval': num(r'"interval": ([0-9.]+)', hits[0]), 'active': num(r'"active": ([0-9.]+)', hits[0]),
            'bounce': num(r'"bounce_time": ([0-9.]+)', hits[0]), 'recovery': float(f.group(1)),
            'circle': 'SH.CIRCLE' in hits[0] and 'SPIN_RADIUS' in hits[0], 'radius': get('SPIN_RADIUS')}


def game_checks(m, b):
    g = game_numbers()
    fr = lambda s: CU.round_half_up(s * 60)
    ok = (g['hits'] == 1 and m.hits == [(fr(g['interval']), fr(g['active']))] and (AT.SPIN_W, AT.SPIN_N) == m.hits[0]
          and m.total == fr(g['interval']) + fr(g['active']) + fr(g['recovery']) and sum(b.holds) == fr(g['bounce']) and g['circle'])
    check(f'{m.sheet}: the game\'s timing (veltharis_data ash_spin: one hit since 2026-10-04) is the art\'s', ok,
          f'game {g["hits"]} hit(s), windup {g["interval"]} s, hit {g["active"]} s, recovery {g["recovery"]} s, bounce '
          f'{g["bounce"]} s, circle {g["circle"]} / art {m.hits}, {m.total} frames, bounce {sum(b.holds)}')
    return g


def model_checks(m):
    sts = [m.clip.at(t) for t in range(m.total)]
    reach_bad, hits, legs = [], [], []
    worst_leg, worst_low = 0.0, 99.0
    for t, st in enumerate(sts):
        for k, a in A.arms(st).items():
            if a and a[3] < -0.5:
                reach_bad.append(f'{t}{k}({a[3]:.1f})')
        h = A.body_hits(st)
        if h:
            hits.append(f'{t}:{h[0][1]}')
        wl, low, kh = CA.leg_ok(faced(st))
        worst_leg, worst_low = max(worst_leg, wl), min(worst_low, low)
        if kh:
            legs.append(t)
    check(f'model {m.sheet}: both fists within the arms\' reach at every frame', not reach_bad, ', '.join(reach_bad[:6]))
    check(f'model {m.sheet}: the blade never passes through the body, the shoulder plates or the helmet', not hits,
          ', '.join(hits[:6]))
    check(f'model {m.sheet}: no leg reaches further than it is long (measured in the facing the body is turned to)',
          worst_leg <= 1.0 + 1e-6, f'longest {worst_leg:.3f}')
    check(f'model {m.sheet}: no boot goes into the ground', worst_low >= -0.6, f'lowest {worst_low:+.2f} px')
    check(f'model {m.sheet}: no knee as high as the hip', not legs, str(legs[:6]))
    low = [(t, A.tip(s)[2]) for t, s in enumerate(sts) if not (DRAG[0] <= t <= DRAG[1])]
    w = min(low, key=lambda x: x[1])
    check(f'model {m.sheet}: the tip is never in the ground (outside the drag)', w[1] > 0.5, f'lowest {w[1]:.1f} px at frame {w[0]}')
    return sts


def drag_checks(m, sts):
    bad = []
    for t in range(DRAG[0], DRAG[1] + 1):
        tp = A.tip(sts[t])
        if not (DRAG_TIP[0] <= tp[2] <= DRAG_TIP[1] and tp[0] <= -DRAG_BEHIND and tp[1] >= DRAG_BEHIND):
            bad.append(f'{t}: tip {tuple(round(v, 1) for v in tp)}')
    one = all(sts[t]['two'] <= 0.0 for t in range(DRAG[0], AT.SPIN_HOLD[1] + 1))
    check(f'{m.sheet}: frames {DRAG[0]}..{DRAG[1]}: the blade dragged behind him on his right, the tip on the ground '
          f'({DRAG_TIP[0]}..{DRAG_TIP[1]} px up, {DRAG_BEHIND:.0f}+ px behind and out), one-handed', not bad and one,
          '; '.join(bad[:4]) or f'tips {min(A.tip(sts[t])[2] for t in range(DRAG[0], DRAG[1] + 1)):.1f}..'
                                 f'{max(A.tip(sts[t])[2] for t in range(DRAG[0], DRAG[1] + 1)):.1f} px up')
    s = sts[DRAG[1]]
    check(f'{m.sheet}: coiled to his right before the turn (hips and chest {-COIL:.0f}+ degrees)', s['tw'] <= COIL and s['ht'] <= COIL,
          f'chest {s["tw"]:.0f}, hips {s["ht"]:.0f} at frame {DRAG[1]}')


def turn_checks(m, sts):
    a, n = m.hits[0]
    ts = list(range(a, a + n + 1))
    psis = [A.angles(sts[t]['axis'])[0] for t in ts]
    # unwrapped: the way round from each frame to the next
    steps = [((q - p + 180.0) % 360.0) - 180.0 for p, q in zip(psis, psis[1:])]
    total = sum(steps)
    tips = [A.tip(sts[t]) for t in range(a, a + n)]
    rs = [math.hypot(p[0], p[1]) for p in tips]
    zs = [p[2] for p in tips]
    check(f'model {m.sheet}: while the hit box is on the blade goes round the full circle to his left ({FULL:.0f} degrees '
          f'over its {n} frames and on into the next, at most {TURN_STEP:.0f} a frame)',
          abs(total + FULL) <= FULL_SLACK and all(-TURN_STEP <= st < 0 for st in steps),
          f'{total:.0f} degrees, steps {min(steps):.0f}..{max(steps):.0f}')
    g = game_numbers()
    check(f'model {m.sheet}: the tip {REACH_SHARE:.0%}+ of the radius ({g["radius"]:.0f}) out, at the player\'s height '
          f'({CA.PLAYER_HEIGHT:.0f}) all through the hit box', min(rs) >= REACH_SHARE * g['radius'] and max(zs) <= CA.PLAYER_HEIGHT
          and min(zs) >= 8.0, f'{min(rs):.0f}..{max(rs):.0f} px out, {min(zs):.0f}..{max(zs):.0f} px up')
    one = all(sts[t]['two'] <= 0.0 and sts[t]['lfree'] > 0.5 for t in range(a, a + n))
    check(f'{m.sheet}: one-handed through the turn (the left hand free, flung out)', one)
    turned = sts[AT.SPIN_HOLD[0]]['ht'] - sts[DRAG[1]]['ht']
    mono = all(sts[t + 1]['tw'] > sts[t]['tw'] and sts[t + 1]['ht'] > sts[t]['ht'] for t in range(a - 2, a + n))
    check(f'{m.sheet}: the whole body turns round to his left, the hips and the chest, without stopping through the hit box '
          f'(the hips {FULL:.0f}+ degrees from the coil to the hold)', mono and turned >= FULL, f'hips {turned:.0f} degrees')
    s0, s1, sh = sts[a], sts[a + n], sts[AT.SPIN_HOLD[0]]
    turn_bend = max(sts[t].get('bend', 0.0) for t in range(a, a + n + 1))
    check(f'{m.sheet}: he crouches as he turns (at most {START_D} px down as it starts, {END_D}+ px as it completes) and is bent '
          f'over {END_BEND:.0f}+ degrees once it has run on (the hold); bent at most {AT.SPIN_BEND:.0f} through the turn itself',
          s0['D'] <= START_D and s1['D'] >= END_D and sh.get('bend', 0.0) >= END_BEND and turn_bend <= AT.SPIN_BEND + 0.5,
          f'{s0["D"]} -> {s1["D"]} px, bent {turn_bend:.0f} at most through the turn, {sh.get("bend", 0.0):.0f} in the hold')


def facing_checks(m):
    """Every sheet row is drawn with all four facings in turn through the hit box (the renderer turns with him)."""
    a, n = m.hits[0]
    seen = {}
    for d in rig.DIRS:
        used = set()
        for s in m.states:
            if a <= s['t'] < a + n:
                k = AA.spin_quarters(s) % 4
                used.add(AA.TURN_ORDER[(AA.TURN_ORDER.index(d) + k) % 4])
        seen[d] = used
    check(f'{m.sheet}: every row shows all four facings through the turn', all(len(v) == 4 for v in seen.values()),
          ', '.join(f'{d} {len(v)}' for d, v in seen.items()))


def feet_checks(m, sts):
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {m.sheet}: one foot at a time (never both off their spot in one frame)', not both, str(both[:8]))
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    piv = range(AT.SPIN_LIN[1], AT.SPIN_LBACK[0] + 1)
    p0 = CA.foot_at(sts[piv[0]], 'L')[0]
    still = all(CA.foot_at(sts[t], 'L')[0] == p0 and not CA.foot_at(sts[t], 'L')[1] for t in piv)
    under = abs(p0[0]) < 0.5 and abs(AT.HIP_HALF + p0[1]) < 0.5          # out -17: on his centre line
    a, n = m.hits[0]
    ball = all(sts[t]['feet']['L'][3] <= -10.0 for t in range(a, a + n))
    check(f'feet {m.sheet}: the left foot is the pivot: in under him (the centre line) before the turn, never leaving its '
          f'place until the recovery (frames {piv[0]}..{piv[-1]}), on the ball through the turn', still and under and ball,
          f'{"still" if still else "MOVES"}, at {tuple(round(v, 1) for v in p0)}, ball {ball}')
    air = all(CA.foot_at(sts[t], 'R')[1] for t in range(a, a + n))
    land = CA.foot_at(sts[AT.SPIN_RLAND], 'R')
    check(f'feet {m.sheet}: the right foot is off the ground through the turn and lands behind him (frame {AT.SPIN_RLAND})',
          air and not land[1] and land[0][0] <= -30.0, f'off {air}, lands at {tuple(round(v) for v in land[0])}')
    hx_jump = max(abs(b['hx'] - a_['hx']) for a_, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a_['D']) for a_, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump (at most {CA.HIP_STEP_X} px forward/back, {CA.HIP_STEP_D} px up/down a frame)',
          hx_jump <= CA.HIP_STEP_X and d_jump <= CA.HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    turned = [t for t in range(m.total) if AA.spin_quarters(sts[t]) % 4 and abs(sts[t]['hx']) > 0.5]
    check(f'feet {m.sheet}: turned away from the facing the hips stay over the anchor (the turn is about where the game has him)',
          not turned, str(turned[:6]))
    end = sts[-1]
    check(f'feet {m.sheet}: it ends standing in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL')
          and abs(end['hx']) < 1e-6, str({k: end['feet'][k][:2] for k in 'RL'}))


def hold_checks(m, sts):
    a, b = AT.SPIN_HOLD
    s = sts[b]
    tp = A.tip(s)
    psi = A.angles(s['axis'])[0]
    moved = max(max(math.dist(sts[t]['fist'], sts[a]['fist']), abs(sts[t]['hx'] - sts[a]['hx']), abs(sts[t]['D'] - sts[a]['D']))
                for t in range(a, b + 1))
    check(f'{m.sheet}: after the turn he stays crouched ({HOLD_D}+ px down, frames {a}..{b}, still), the blade low before him '
          f'on his left', min(sts[t]['D'] for t in range(a, b + 1)) >= HOLD_D and moved <= HOLD_STILL and -80.0 <= psi <= -10.0
          and 2.0 <= tp[2] <= 30.0, f'{s["D"]} px down, moved {moved:.1f} px, blade {psi:.0f} degrees, tip {tp[2]:.0f} px up')


def bounce_checks(m, b):
    sts = [b.clip.at(t) for t in range(b.total)]
    both = [t for t in range(1, b.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {b.sheet}: one foot at a time', not both, str(both[:8]))
    turned = [t for t in range(b.total) if AA.spin_quarters(sts[t]) % 4 and abs(sts[t]['hx']) > 0.5]
    check(f'feet {b.sheet}: turned away from the facing the hips stay over the anchor', not turned, str(turned[:6]))
    end = sts[-1]
    check(f'feet {b.sheet}: ends in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL'),
          str({k: end['feet'][k][:2] for k in 'RL'}))
    same = all(b.frames()[d][0] == m.frames()[d][m.times.index(AT.SPIN_CONTACT)] for d in rig.DIRS)
    check(f'{b.sheet}: its first pose is the spin\'s frame {AT.SPIN_CONTACT} (the blade straight ahead)', same)


def spin_feet_below(m, d):
    """How far below the foot line a row may draw the feet: each pose's feet in the facing it is drawn with (the
    turned body shows another facing), a foot towards the camera DEPTH of its distance lower - the front view a foot
    ahead, the back view one behind, the side views a foot out towards the camera (the sidestep's rule: checks.STRAFE_FOOT,
    approved with the sidesteps) - +1 for the boot's own rounding; the feet as they stand (checks_hit.BELOW) at least."""
    worst = 0.0
    for s in m.states:
        k = AA.spin_quarters(s) if s.get('spin') else 0
        d2 = AA.TURN_ORDER[(AA.TURN_ORDER.index(d) + k) % 4]
        f = faced(s) if s.get('spin') else s
        for side_ in 'RL':
            x, out = f['feet'][side_][:2]
            lat = out if side_ == 'R' else -out
            drop = {'down': x, 'up': -x, 'right': lat, 'left': -lat}[d2]
            worst = max(worst, A.DEPTH * drop)
    return max(CA.H.BELOW[d], math.ceil(worst) + 1)


OTHERS = CU.OTHERS + (('上挑的蓄力', AT.quick3, AT.QUICK3_LOW[1]),)


def distinct_checks(m, at=DRAG[1]):
    i = max(j for j, t in enumerate(m.times) if t <= at)
    for label, fn, t in OTHERS:
        clip = fn()
        sts = AT.poses(clip, [t - 1, t])
        vals = [C.sil_change(m.frames()[d][i], AA.render_pose(d, sts[1], sts[0])) for d in rig.DIRS]
        check(f'{m.sheet}: the coil reads apart from {label} (outline {CA.DISTINCT:.0%}+ different, each view)',
              min(vals) >= CA.DISTINCT, ' '.join(f'{v:.0%}' for v in vals))


def main():
    CA._sync()
    m, b = ES.moves()
    game_checks(m, b)
    sts = model_checks(m)
    drag_checks(m, sts)
    turn_checks(m, sts)
    facing_checks(m)
    feet_checks(m, sts)
    hold_checks(m, sts)
    CU.flat_checks(m, 0)
    model_checks(b)
    bounce_checks(m, b)
    distinct_checks(m)
    for mv in (m, b):
        CA.frame_checks(mv, below=spin_feet_below)
        CA.hands_checks(mv)
        CC.canvas_checks(mv)
    CA.entry_feet_checks(m)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: half a turn (the hips and the blade 180 degrees); a turn held stiff
    upright (no crouch); the tip lifted off the ground in the drag; the left foot stepping in the turn; the right
    foot staying on the ground; two-handed; the game's two hits; a blade swung high through the turn; the renderer
    keeping one facing (no turn drawn)."""
    CA._sync()
    caught = []
    m, b = ES.moves()

    def variant(edit, steps_edit=None):
        keys = [(t, dict(k)) for t, k in m.clip.keys]
        for t, k in keys:
            edit(t, k)
        tracks = {s_: list(v) for s_, v in m.clip.tracks.items()}
        if steps_edit:
            steps_edit(tracks)
        cl = AT.Clip('spin_bad', keys, tracks, whole_turn=True, spin=True, musts=m.clip.musts)
        return [cl.at(t) for t in range(m.total)]

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1
    a, n = AT.SPIN_W, AT.SPIN_N

    def half(t, k):
        if a <= t <= AT.SPIN_HOLD[1]:
            f = 0.5
            H = (k['tw'] + 20.0) * f - 20.0
            d = H - k['tw']
            k.update(tw=k['tw'] + d, ht=k['ht'] + d, fist=A.yaw(k['fist'], d))
            k['dir'] = (k['dir'][0] - d, k['dir'][1])
    sts = variant(half)
    caught.append(run(lambda: turn_checks(m, sts)))
    sts = variant(lambda t, k: k.update(D=8, bend=0.0) if a <= t <= a + n + 3 else None)
    caught.append(run(lambda: turn_checks(m, sts)))
    sts = variant(lambda t, k: k.update(fist=(k['fist'][0], k['fist'][1], k['fist'][2] + 12.0)) if DRAG[0] <= t <= DRAG[1] else None)
    caught.append(run(lambda: drag_checks(m, sts)))

    def left_step(tr):
        tr['L'] = sorted([x for x in tr['L']] + [(a + 3, AT.LPIVOT), (a + 7, (10.0, -17.0, AT.gait.ANKLE_H, 0.0))])
    sts = variant(lambda t, k: k['feet'].pop('L', None) if a + 3 < t < a + 7 else None, left_step)
    caught.append(run(lambda: feet_checks(m, sts)))

    def right_down(tr):
        tr['R'] = [(t, (x[0], x[1], AT.gait.ANKLE_H, 0.0)) for t, x in tr['R']]
    sts = variant(lambda t, k: None, right_down)
    caught.append(run(lambda: feet_checks(m, sts)))
    sts = variant(lambda t, k: k.update(two=1.0) if a <= t <= a + n else None)
    caught.append(run(lambda: turn_checks(m, sts)))

    class Fake:
        pass
    f = Fake()
    f.__dict__.update(m.__dict__)
    f.hits = [(AT.SPIN_W, 6), (AT.SPIN_W + 42, 6)]
    caught.append(run(lambda: game_checks(f, b)))
    sts = variant(lambda t, k: k.update(dir=(k['dir'][0], 10.0)) if a <= t <= a + n else None)
    caught.append(run(lambda: turn_checks(m, sts)))
    g = Fake()
    g.__dict__.update(m.__dict__)
    g.states = [dict(s, tw=0.0, ht=0.0) for s in m.states]
    caught.append(run(lambda: facing_checks(g)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
