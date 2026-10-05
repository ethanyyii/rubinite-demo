"""Automatic checks for the quick combo's third hit, the upswing (C5 上挑, attacks.quick3,
export_upswing.py); exit code 1 on any failure.

    python3 tools/boss_rig/checks_upswing.py [--selftest]

The attack checks (checks_attack: the finished frames, the hands) run on these clips too. What is new:
  - the game's numbers (veltharis_data.gd quick_combo_3: the three intervals, the hit boxes, the
    recovery and phase 2's, the third hit's bounce, its 120-degree sector and radius) are the art's
  - the two quick slashes are the quick combo's own frames up to the second hit box's end (the entry
    sheets are shared)
  - the 3D model at every combat frame: the arms reach, the blade misses the body, the legs, the tip
    never in the ground
  - the load, held before the scoop: sunk and bent over, both hands on the grip, the blade low behind
    him on his right (the tip near the ground, behind and out to his right), held still
  - the hit: two-handed; the blade comes into the 120-degree sector low on his right front, crosses the
    front with the tip at the hit box's edge at the player's height, and leaves it on his left rising -
    from his right to his left and from low to high all the way (the tip higher every frame)
  - the body: the chest unwinds from his right round to his left, the legs drive the hips up, the bend
    comes out; he ends the stroke arched back with the blade up over his left shoulder
  - the feet: neither leaves its place from the second cut to the recovery (the back heel may come up:
    pivoting on the ball), one at a time throughout, the hips never jump, the weight on the front foot
    in the load and at the blow, the carry at the end
  - the flat never flashes round between two poses (beyond the blade's own swing)
  - the held load reads apart from every other attack's windup (checks_attack.DISTINCT, each view)
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
import export_upswing as EU

results = CA.results
check = C.check
SECTOR_HALF = 60.0          # half the third hit's sector (veltharis_data angle_deg 120)
ENTER = (45.0, 80.0)        # degrees to his right the blade is as the hit box comes on (the sector's edge, 60)
CROSS = 15.0                # degrees: within this of straight ahead at one frame at least
RISE_END = 20.0             # degrees: the blade's elevation as the hit box closes (rising)
RISE_GAIN = 90.0            # px the tip rises through the hit box at the least
LOW_DROP = 18               # px: the hips down in the load
LOW_BEND = 30.0             # degrees bent at the waist in the load
LOW_TIP = (4.0, 22.0)       # px: the tip's height in the load (near the ground, not in it)
LOW_BEHIND = 30.0           # px the tip is behind the hips in the load
LOW_OUT = 40.0              # px the tip is out to his right in the load
HOLD_STILL = 4.0            # px the fists / hips may move while the load is held
CHEST_LOW = -60.0           # degrees: the chest turned to his right in the load at the least
CHEST_END = 20.0            # ... and to his left as the hit box closes
UP_END = 6                  # px: the hips at most this far down once the stroke is through (frame 116)
ARCH = -6.0                 # degrees: the lean arched back at the top at the least
FLASH_TURN = CC.TURN_STEP   # degrees: the flat between two poses (beyond the blade's own swing)


def round_half_up(x):
    return math.floor(x + 0.5)


def game_numbers():
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    f = re.search(r'out\[&"quick_combo_3"\] = _move\(.*?\], ([0-9.]+) \* rec', src, re.S)
    body = f.group(0)
    third = re.search(r'_hit\(\{(.*?)\}\)', body, re.S).group(1)
    num = lambda pat, s=third: float(re.search(pat, s).group(1))
    lights = [float(x) for x in re.findall(r'_quick_light\(([0-9.]+)', body)]
    return {'intervals': lights + [num(r'"interval": ([0-9.]+)')], 'active': num(r'"active": ([0-9.]+)'),
            'light_active': float(re.search(r'static func _quick_light.*?"active": ([0-9.]+)', src, re.S).group(1)),
            'recovery': float(f.group(1)), 'bounce': num(r'"bounce_time": ([0-9.]+)'), 'angle': num(r'"angle_deg": ([0-9.]+)'),
            'radius': get('SWEEP_RADIUS') if 'SWEEP_RADIUS' in third else None, 'phase2': get('PHASE2_RECOVERY_SCALE'),
            'heavy': 'AT.HEAVY' in third}


def game_checks(m, b):
    g = game_numbers()
    fr = lambda s: round_half_up(s * 60)
    starts, t = [], 0
    for iv in g['intervals']:
        t += fr(iv)
        starts.append(t)
    hits = [(starts[0], fr(g['light_active'])), (starts[1], fr(g['light_active'])), (starts[2], fr(g['active']))]
    total = starts[2] + fr(g['active']) + fr(g['recovery'])
    p2 = starts[2] + fr(g['active']) + fr(g['recovery'] * g['phase2'])
    ok = (m.hits == hits and m.total == total and sum(m.holds_p2) == p2 and sum(b.holds) == fr(g['bounce'])
          and (AT.Q1, AT.Q2, AT.Q3) == tuple(starts) and g['heavy'])
    check(f'{m.sheet}: the game\'s timing (veltharis_data quick_combo_3) is the art\'s', ok,
          f'game hits {hits}, {total} frames, phase 2 {p2}, bounce {fr(g["bounce"])}, heavy {g["heavy"]} / art {m.hits}, '
          f'{m.total}, phase 2 {sum(m.holds_p2)}, bounce {sum(b.holds)}')
    check(f'{m.sheet}: the third hit\'s sector is {2 * SECTOR_HALF:.0f} degrees, radius {CA.REACH:.0f} (veltharis_data)',
          g['angle'] == 2 * SECTOR_HALF and g['radius'] == CA.REACH, f'{g["angle"]} degrees, radius {g["radius"]}')
    return g


def shared_checks(m):
    """Through the second hit box the poses are the quick combo's own frames (the pose after it, frame
    66, has the blade's flat from the way it moves on - the upswing's own)."""
    import export_quick as EQ
    q = EQ.moves()[0]
    n = max(i for i, t in enumerate(q.times) if t <= AT.Q2 + 5) + 1
    CC.same_frames(f'{m.sheet}: its poses up to frame {AT.Q2 + 5} (the second hit box\'s last) are boss_quick\'s', m, q, n)
    return q


def model_checks(m):
    sts = CC.body_checks(m)
    low = min(A.tip(s)[2] for s in sts)
    check(f'model {m.sheet}: the sword\'s tip never goes into the ground', low > LOW_TIP[0], f'lowest {low:.1f} px up')
    return sts


def low_checks(m, sts):
    """The load, held QUICK3_LOW: sunk, bent, both hands, the blade low behind him on his right."""
    a, b = AT.QUICK3_LOW
    bad = []
    for t in range(a, b + 1):
        s = sts[t]
        tp = A.tip(s)
        if not (s['D'] >= LOW_DROP and s.get('bend', 0.0) >= LOW_BEND and s['two'] >= 1.0):
            bad.append(f'{t}: D {s["D"]}, bent {s.get("bend", 0.0):.0f}, two {s["two"]:.2f}')
        if not (LOW_TIP[0] <= tp[2] <= LOW_TIP[1] and s['hx'] - tp[0] >= LOW_BEHIND and tp[1] >= LOW_OUT):
            bad.append(f'{t}: tip {tuple(round(v) for v in tp)}')
        if s['tw'] > CHEST_LOW:
            bad.append(f'{t}: chest {s["tw"]:.0f}')
    s = sts[b]
    tp = A.tip(s)
    check(f'{m.sheet}: frames {a}..{b}: sunk ({LOW_DROP}+ px) and bent over ({LOW_BEND:.0f}+ degrees), both hands on the grip, '
          f'the chest turned to his right ({-CHEST_LOW:.0f}+ degrees), the blade low behind him on his right (the tip '
          f'{LOW_TIP[0]:.0f}..{LOW_TIP[1]:.0f} px up, {LOW_BEHIND:.0f}+ px behind the hips, {LOW_OUT:.0f}+ px out)', not bad,
          '; '.join(bad[:4]) or f'D {s["D"]}, bent {s["bend"]:.0f}, chest {s["tw"]:.0f}, tip {tuple(round(v) for v in tp)}')
    moved = max(max(math.dist(sts[t]['fist'], sts[a]['fist']), abs(sts[t]['hx'] - sts[a]['hx']), abs(sts[t]['D'] - sts[a]['D']))
                for t in range(a, b + 1))
    check(f'{m.sheet}: the load is held (frames {a}..{b}: the fists and hips move {HOLD_STILL:.0f} px at most)',
          moved <= HOLD_STILL, f'{moved:.1f} px')
    front, back_ = s['feet']['R'][0], s['feet']['L'][0]
    share = (s['hx'] - back_) / (front - back_)
    check(f'{m.sheet}: the weight on the front (right) foot in the load ({CA.WEIGHT_FWD:.0%}+)', share >= CA.WEIGHT_FWD,
          f'{share:.0%}')


def hit_checks(m, sts):
    a, n = m.hits[2]
    ts = list(range(a, a + n))
    ang = [A.angles(sts[t]['axis']) for t in ts]
    tips = [A.tip(sts[t]) for t in ts]
    psis = [p for p, _ in ang]
    check(f'model {m.sheet}: the upswing\'s blade comes into the sector low on his right front as the hit box comes on '
          f'({ENTER[0]:.0f}..{ENTER[1]:.0f} degrees), all through within {SECTOR_HALF:.0f} (+20) of straight ahead, from his '
          f'right to his left', ENTER[0] <= psis[0] <= ENTER[1] and all(abs(p) <= SECTOR_HALF + 20 for p in psis)
          and all(q < p for p, q in zip(psis, psis[1:])) and psis[-1] <= -SECTOR_HALF + 15,
          'azimuths ' + ' '.join(f'{p:.0f}' for p in psis))
    mid = min(ts, key=lambda t: abs(A.angles(sts[t]['axis'])[0]))
    tp = A.tip(sts[mid])
    r = math.hypot(tp[0], tp[1])
    check(f'model {m.sheet}: straight ahead (frame {mid}) the tip is at the hit box\'s edge ({CA.REACH:.0f} px) at the player\'s '
          f'height ({CA.PLAYER_HEIGHT:.0f})', abs(A.angles(sts[mid]['axis'])[0]) <= CROSS and r >= CA.REACH
          and tp[2] <= CA.PLAYER_HEIGHT, f'{r:.0f} px out, {tp[2]:.0f} px up, {A.angles(sts[mid]["axis"])[0]:.0f} degrees')
    zs = [p[2] for p in tips]
    check(f'model {m.sheet}: from low to high - the tip higher every frame of the hit box, {RISE_GAIN:.0f}+ px in all, the '
          f'blade {RISE_END:.0f}+ degrees up as it closes', all(q > p for p, q in zip(zs, zs[1:]))
          and zs[-1] - zs[0] >= RISE_GAIN and ang[-1][1] >= RISE_END,
          'tip heights ' + ' '.join(f'{z:.0f}' for z in zs) + f', last {ang[-1][1]:.0f} degrees up')
    two = min(sts[t]['two'] for t in range(AT.QUICK3_LOW[0], a + n))
    check(f'{m.sheet}: two-handed from the load through the hit box (heavy)', two >= 1.0, f'two {two:.2f}')
    s0, s1 = sts[AT.QUICK3_LOW[1]], sts[a + n - 1]
    st = sts[116]
    check(f'{m.sheet}: the whole body: the chest unwinds from his right ({s0["tw"]:.0f}) round to his left ({CHEST_END:.0f}+ as '
          f'the hit box closes), the hips driven up (at most {UP_END} px down by frame 116), the bend out, arched back '
          f'({ARCH:.0f} degrees) at the top', s1['tw'] >= CHEST_END and st['D'] <= UP_END and st.get('bend', 0.0) < 1.0
          and sts[AT.QUICK3_TOP[1]]['lx'] <= ARCH,
          f'chest {s0["tw"]:.0f} -> {s1["tw"]:.0f}, hips {st["D"]} down at 116, bent {st.get("bend", 0.0):.0f}, '
          f'lean {sts[AT.QUICK3_TOP[1]]["lx"]:.0f} at the top')
    s = sts[AT.QUICK3_TOP[1]]
    psi, el = A.angles(s['axis'])
    check(f'{m.sheet}: the stroke ends with the blade up over his left shoulder (tip up and back, on his left), held '
          f'{AT.QUICK3_TOP[0]}..{AT.QUICK3_TOP[1]}', psi <= -100 and el >= 30 and s['fist'][1] < 0
          and math.dist(sts[AT.QUICK3_TOP[0]]['fist'], s['fist']) <= HOLD_STILL, f'{psi:.0f} / {el:.0f} degrees, '
          f'fist {tuple(round(v) for v in s["fist"])}')


def feet_checks(m, sts):
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {m.sheet}: one foot at a time (never both off their spot in one frame)', not both, str(both[:8]))
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    span = range(AT.QUICK3_SHARED, AT.QUICK3_BACK[0] + 1)
    still = {k: all(CA.foot_at(sts[t], k)[0] == CA.foot_at(sts[span[0]], k)[0] and not CA.foot_at(sts[t], k)[1] for t in span)
             for k in 'RL'}
    piv = sts[AT.QUICK3_CONTACT]['feet']['L'][3]
    check(f'feet {m.sheet}: neither foot leaves its place from the second cut to the recovery (frames {span[0]}..{span[-1]}); '
          f'the back heel up at the blow (pivoting on the ball)', all(still.values()) and piv <= -10.0,
          f'{still}, left foot pitch {piv:.0f} at frame {AT.QUICK3_CONTACT}')
    hx_jump = max(abs(b['hx'] - a['hx']) for a, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a['D']) for a, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump (at most {CA.HIP_STEP_X} px forward/back, {CA.HIP_STEP_D} px up/down a frame)',
          hx_jump <= CA.HIP_STEP_X and d_jump <= CA.HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    s = sts[AT.QUICK3_CONTACT]
    share = (s['hx'] - s['feet']['L'][0]) / (s['feet']['R'][0] - s['feet']['L'][0])
    check(f'feet {m.sheet}: the weight on the front foot at the blow ({CA.WEIGHT_FWD:.0%}+)', share >= CA.WEIGHT_FWD, f'{share:.0%}')
    end = sts[-1]
    check(f'feet {m.sheet}: it ends standing in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL')
          and abs(end['hx']) < 1e-6, str({k: end['feet'][k][:2] for k in 'RL'}))


def flat_checks(m, frm=AT.QUICK3_SHARED):
    """The flat never turns more than FLASH_TURN between two poses beyond the blade's own swing
    (checks_cleave.edge_checks' second half)."""
    sts = [s for s in m.states if s['t'] >= frm]
    rel = []
    for p, q in zip(sts, sts[1:]):
        deg = math.degrees(math.acos(min(1.0, abs(A.dot(p['w3'], q['w3'])))))
        ax = math.degrees(math.acos(max(-1.0, min(1.0, A.dot(p['axis'], q['axis'])))))
        rel.append((q['t'], max(0.0, deg - ax)))
    w = max(rel, key=lambda x: x[1])
    check(f'{m.sheet}: the flat never turns more than {FLASH_TURN:.0f} degrees between two poses (beyond the blade\'s own '
          f'swing) from frame {frm}', w[1] <= FLASH_TURN, f'worst {w[1]:.0f} degrees at frame {w[0]}')


def bounce_checks(m, b):
    sts = [b.clip.at(t) for t in range(b.total)]
    both = [t for t in range(1, b.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {b.sheet}: one foot at a time', not both, str(both[:8]))
    end = sts[-1]
    check(f'feet {b.sheet}: ends in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL'),
          str({k: end['feet'][k][:2] for k in 'RL'}))
    same = all(b.frames()[d][0] == m.frames()[d][m.times.index(AT.QUICK3_CONTACT)] for d in rig.DIRS)
    check(f'{b.sheet}: its first pose is the upswing\'s frame {AT.QUICK3_CONTACT} (the blade straight ahead)', same)


OTHERS = (('快斬的起手', AT.quick, 14), ('王權橫掃的起手', AT.c1, 40), ('下劈的最高點', AT.cleave, AT.CLEAVE_TOP),
          ('灰燼衝擊的蓄力', AT.impact, AT.IMPACT_TOP), ('突刺的起手', AT.thrust, 32))


def distinct_checks(m, at=AT.QUICK3_LOW[1]):
    """The held load reads apart from every other attack's windup (animation-review §4.5)."""
    i = max(j for j, t in enumerate(m.times) if t <= at)
    for label, fn, t in OTHERS:
        clip = fn()
        sts = AT.poses(clip, [t - 1, t])
        vals = [C.sil_change(m.frames()[d][i], AA.render_pose(d, sts[1], sts[0])) for d in rig.DIRS]
        check(f'{m.sheet}: the held load reads apart from {label} (outline {CA.DISTINCT:.0%}+ different, each view)',
              min(vals) >= CA.DISTINCT, ' '.join(f'{v:.0%}' for v in vals))


def main():
    CA._sync()
    m, b = EU.moves()
    game_checks(m, b)
    shared_checks(m)
    sts = model_checks(m)
    low_checks(m, sts)
    hit_checks(m, sts)
    feet_checks(m, sts)
    flat_checks(m)
    CC.body_checks(b)
    bounce_checks(m, b)
    distinct_checks(m)
    for mv in (m, b):
        CA.frame_checks(mv)
        CA.hands_checks(mv)
        CC.canvas_checks(mv)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: the load standing up (not sunk, not bent); the load
    one-handed; a falling cut (high to low through the hit box); the blade short of the hit box's edge
    straight ahead; the left foot stepping in the scoop; the chest not unwinding (turned the twin
    slash's 40 degrees); a hit box timed off the game's; a frame of the opening differing from the
    quick combo's."""
    CA._sync()
    caught = []
    m, b = EU.moves()

    def variant(edit, steps_edit=None):
        keys = [(t, dict(k)) for t, k in m.clip.keys]
        for t, k in keys:
            edit(t, k)
        tracks = {s_: list(v) for s_, v in m.clip.tracks.items()}
        if steps_edit:
            steps_edit(tracks)
        cl = AT.Clip('quick3_bad', keys, tracks, whole_turn=True, musts=m.clip.musts)
        return [cl.at(t) for t in range(m.total)]

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1
    lo = AT.QUICK3_LOW
    sts = variant(lambda t, k: k.update(D=4, bend=0.0) if lo[0] <= t <= lo[1] else None)
    caught.append(run(lambda: low_checks(m, sts)))
    sts = variant(lambda t, k: k.update(two=0.0) if lo[0] <= t <= AT.Q3 + 5 else None)
    caught.append(run(lambda: (low_checks(m, sts), hit_checks(m, sts))))
    # a falling cut: the blade comes down from high on his right to low on his left
    def falling(t, k):
        if AT.Q3 <= t <= AT.Q3 + 5:
            psi, el = A.angles(A.direction(*k['dir']))
            k['dir'] = (psi, -el - 10.0)
    sts = variant(falling)
    caught.append(run(lambda: hit_checks(m, sts)))
    sts = variant(lambda t, k: k.update(fist=(k['fist'][0] - 18.0,) + k['fist'][1:]) if AT.Q3 <= t <= AT.Q3 + 3 else None)
    caught.append(run(lambda: hit_checks(m, sts)))

    def left_step(tr):
        tr['L'] = sorted(tr['L'] + [(102, AT.STAND), (106, (14.0, 0.0, AT.gait.ANKLE_H, 0.0))])
    sts = variant(lambda t, k: k['feet'].pop('L', None) if 102 < t < 106 else None, left_step)
    caught.append(run(lambda: feet_checks(m, sts)))
    sts = variant(lambda t, k: k.update(tw=max(-40.0, min(40.0, k['tw']))) if t > AT.QUICK3_SHARED else None)
    caught.append(run(lambda: (low_checks(m, sts), hit_checks(m, sts))))

    class Fake:
        pass
    f = Fake()
    f.__dict__.update(m.__dict__)
    f.hits = [(AT.Q1, 6), (AT.Q2, 6), (AT.Q3 + 6, 6)]
    caught.append(run(lambda: game_checks(f, b)))
    g = Fake()
    g.__dict__.update(m.__dict__)
    fr = {d: list(v) for d, v in m.frames().items()}
    fr['down'][5] = dict(fr['down'][5])
    q = next(iter(fr['down'][5]))
    fr['down'][5][q] = (1, 2, 3, 255)
    g.frames = lambda: fr
    caught.append(run(lambda: shared_checks(g)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
