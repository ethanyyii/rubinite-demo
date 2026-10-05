"""Automatic checks for the judgment thrust (裁決突刺, attacks.thrust, export_thrust.py); exit code 1 on
any failure.

    python3 tools/boss_rig/checks_thrust.py [--selftest]

The attack checks (checks_attack: the finished frames, the hands) run on these clips too. What is new
for a thrust carried forward by the game (boss-veltharis §4.4):
  - the game's numbers (veltharis_data.gd: the windup, the hit box, the recovery and phase 2's, the
    lunge's distance, the sword's reach and the capsule's width) are the ones the art is drawn to;
    the game's move (LUNGE_DISTANCE over the hit box's frames, the same each frame) is the one the
    poses are drawn about, a pose for every one of those frames
  - the 3D model at every combat frame: the arms reach, the blade misses the body, the legs
  - the windup as the user described it (2026-10-04: "劍收到側腰……要收在右側，同時右腳也要往後張開，左右腳
    變成左腳在前右腳在後，且打開的寬度大於肩距，身體也要往下前傾"), held before the drive: the right fist by
    his right hip at the waist, the tip forward; only the right foot has moved, back, the left foot
    ahead of it by more than the shoulders' width; the hips down, the chest leaning forward, the
    weight on the front foot
  - while the hit box is on, the blade lies along the capsule (straight ahead, within its width), the
    tip at its far end (SWORD_REACH, 95%+) at the player's height
  - the feet: one at a time outside the lunge; in the lunge the left foot reaches through and lands
    (planted on the ground from then), the right foot's toe stays on the ground (it drags); the hips
    never jump on screen; ends in the carry where the game has him
  - the edges up and down from the moment the sword is lowered forward until it is lifted back
    (checks_cleave.edge_checks: the flat never flashes round)
  - the cocked pose reads apart from every other attack's windup (checks_attack.DISTINCT, each view)
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
import export_thrust as ET

results = CA.results
check = C.check
SHOULDERS = 2 * A.SH_R          # 41.2 px: the stance wider than the shoulders (the user's words)
HOLD = (24, 32)                 # the cocked pose (the read before the drive)
REACH_SHARE = 0.95              # the tip at least this share of SWORD_REACH ahead while the hit box is on
LINE_TURN = 10.0                # degrees off straight ahead
DROP_COCKED = 12                # px: the hips down (the sweeps' windup sinks 3 - "往下")
# User 2026-10-04, after the first version: "突刺的身體還是壓得不夠低，整個身體要彎下去，頭的高度只在劍的上面一點點這麼
# 彎，手要續力到身體後面……整個人會因為彎腰變扁，腳也要再張開一點，然後彈射出去時是右腳（在後面的腳）用力蹬，讓整個身體
# 飛出去". The first version is what these must catch (--selftest): bent 26 / 30 degrees by a shear (the head
# as high as standing less the hips' drop), the head 25 px over the hands, the stance 44 px, the right toe
# dragging through the lunge
BEND_MIN = 55.0                 # degrees bent at the waist, cocked and in the lunge
HEAD_GAP = (0.0, 12.0)          # px from the head's lowest point down to the blade under it: just over it
FLAT_MAX = 0.70                 # the crown's top at most this share of his standing height (160): flattened
STANCE_MIN = 55.0               # px between the feet cocked (the first version 44: "腳也要再張開一點")
BACK_PULL = 25.0                # px the right fist is behind the head's centre cocked (drawn back along the body: the first version 12)
PUSH_LEG = 0.93                 # the right leg's length share as it leaves the ground: straightened by the push
FLY_MIN = 4                     # frames of the lunge with both feet off the ground (the whole body flies)
WAIST = (A.BELT_U - 14.0, A.BELT_U + 6.0)     # the right fist's height (standing heights: the hips' drop added back)


def game_numbers():
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    f = re.search(r'out\[&"judgment_thrust"\] = _move\(.*?\{"is_punish"', src, re.S).group(0)
    num = lambda pat: float(re.search(pat, f).group(1))
    return {'interval': num(r'"interval": ([0-9.]+)'), 'active': num(r'"active": ([0-9.]+)'),
            'recovery': num(r'\], ([0-9.]+) \* rec'), 'bounce': num(r'"bounce_time": ([0-9.]+)'),
            'lunge': get('LUNGE_DISTANCE'), 'reach': get('SWORD_REACH'), 'width': get('THRUST_WIDTH'),
            'phase2': get('PHASE2_RECOVERY_SCALE')}


def game_checks(m, b):
    g = game_numbers()
    fr = lambda s: round(s * 60)
    ok = (fr(g['interval']) == AT.THRUST_W and m.hits == [(AT.THRUST_W, fr(g['active']))]
          and AT.LUNGE_FRAMES == fr(g['active']) and m.total == AT.THRUST_W + fr(g['active']) + fr(g['recovery'])
          and sum(m.holds_p2) == AT.THRUST_W + fr(g['active']) + round(fr(g['recovery']) * g['phase2'])
          and sum(b.holds) == fr(g['bounce']))
    check(f'{m.sheet}: the game\'s timing (veltharis_data judgment_thrust) is the art\'s', ok,
          f'windup {g["interval"]} s, hit {g["active"]} s, recovery {g["recovery"]} s (phase 2 x{g["phase2"]}), bounce '
          f'{g["bounce"]} s / art {AT.THRUST_W}, {m.hits}, {m.total}, phase 2 {sum(m.holds_p2)}, bounce {sum(b.holds)}')
    advs = [m.clip.at(t)['adv'] for t in range(m.total)]
    moving = [t for t in range(1, m.total) if abs(advs[t] - advs[t - 1]) > 1e-6]
    n = fr(g['active'])
    each = g['lunge'] / n
    ok = (abs(advs[-1] - g['lunge']) < 1e-6 and moving == list(range(AT.THRUST_W, AT.THRUST_W + n))
          and abs(advs[AT.THRUST_W] - each) < 1e-6 and all(abs(advs[t] - advs[t - 1] - each) < 1e-6 for t in moving))
    check(f'{m.sheet}: the game\'s lunge ({g["lunge"]:.0f} px over the hit box\'s {n} frames, {each:.1f} a frame) is the one '
          f'the poses are drawn about', ok, f'{advs[-1]:.1f} px; moving after frames {moving[:1]}..{moving[-1:]}')
    held = [t for t in range(AT.THRUST_W, AT.THRUST_W + n + 1) if t not in m.times]
    check(f'{m.sheet}: a pose for every frame of the lunge (a held pose would carry a planted foot along)', not held, str(held))
    return g


def head_gap(st):
    """px from the head's lowest point (bent: attack3d.bend_point) down to the blade under its centre."""
    hd = A.bend_point(st, A.HEAD)
    hf, hz = hd[0] + st['hx'], hd[2] - st['D']
    f, ax = st['fist'], st['axis']
    bz = f[2] + ax[2] * (hf - f[0]) / ax[0]
    return hz - A.HEAD_R - bz


def crown(st):
    """The crown's top (bent), px over the ground."""
    return A.bend_point(st, (0.0, 0.0, A.SH_U + 48.0))[2] - st['D']


def windup_checks(m, sts):
    """The cocked pose, as the user described it, held HOLD."""
    bad = []
    for t in range(HOLD[0], HOLD[1] + 1):
        s = sts[t]
        f = s['fist']
        psi, el = A.angles(s['axis'])
        fL, fR = s['feet']['L'], s['feet']['R']
        u = f[2] + s['D']
        if not (f[1] >= 10.0 and abs(f[0] - s['hx']) <= 14.0 and WAIST[0] <= u <= WAIST[1]):
            bad.append(f'{t}: fist {tuple(round(v) for v in f)}')
        if not (abs(psi) <= 20.0 and -25.0 <= el <= 10.0):
            bad.append(f'{t}: sword {psi:.0f},{el:.0f}')
    s = sts[HOLD[1]]
    psi, el = A.angles(s['axis'])
    check(f'{m.sheet}: frames {HOLD[0]}..{HOLD[1]}: the sword drawn back to his right hip (the right fist {10}+ px to his '
          f'right, by the hips, at the waist), the tip forward', not bad,
          '; '.join(bad[:4]) or f'fist {tuple(round(v) for v in s["fist"])} (hips {s["hx"]:.0f}, {s["D"]} down), '
                                 f'sword {psi:.0f} / {el:.0f} degrees')
    gap = s['feet']['L'][0] - s['feet']['R'][0]
    left_still = all(CA.foot_at(x, 'L')[0] == (0.0, 0.0, 0.0) and not CA.foot_at(x, 'L')[1] for x in sts[:AT.THRUST_W])
    check(f'{m.sheet}: the right foot alone steps back: the left foot ahead of it by more than the shoulders '
          f'({SHOULDERS:.0f} px); the left foot never leaves its place in the windup', gap > SHOULDERS and left_still,
          f'{gap:.0f} px apart, left foot {"still" if left_still else "MOVED"}')
    front, back_ = s['feet']['L'][0], s['feet']['R'][0]
    share = (s['hx'] - back_) / (front - back_)
    check(f'{m.sheet}: down and bent right over (hips {DROP_COCKED}+ px down, bent {BEND_MIN:.0f}+ degrees at the waist), the '
          f'weight on the front foot ({CA.WEIGHT_FWD:.0%}+)', s['D'] >= DROP_COCKED and s.get('bend', 0.0) >= BEND_MIN
          and share >= CA.WEIGHT_FWD, f'{s["D"]} px down, bent {s.get("bend", 0.0):.0f}, hips {share:.0%} of the way to the front foot')
    gaps = [head_gap(sts[t]) for t in range(HOLD[0], HOLD[1] + 1)]
    tops = [crown(sts[t]) for t in range(HOLD[0], HOLD[1] + 1)]
    check(f'{m.sheet}: the head just over the blade (its lowest point {HEAD_GAP[0]:.0f}..{HEAD_GAP[1]:.0f} px over it), the whole '
          f'man flattened (the crown at most {FLAT_MAX:.0%} of his height)',
          all(HEAD_GAP[0] <= g <= HEAD_GAP[1] for g in gaps) and max(tops) <= FLAT_MAX * B.HEIGHT,
          f'{min(gaps):.1f}..{max(gaps):.1f} px over the blade, crown {max(tops):.0f} px up (of {B.HEIGHT})')
    pull = A.bend_point(s, A.HEAD)[0] + s['hx'] - s['fist'][0]
    check(f'{m.sheet}: the hands drawn back (the right fist {BACK_PULL:.0f}+ px behind the head\'s centre, at most 6 px ahead of '
          f'the hips); the stance {STANCE_MIN:.0f}+ px', pull >= BACK_PULL and s['fist'][0] - s['hx'] <= 6.0 and gap >= STANCE_MIN,
          f'{pull:.0f} px behind the head, {s["fist"][0] - s["hx"]:.0f} px ahead of the hips, {gap:.0f} px apart')
    a, b = sts[HOLD[0]], sts[HOLD[1]]
    moved = max(math.dist(a['fist'], b['fist']), abs(a['hx'] - b['hx']), abs(a['D'] - b['D']))
    check(f'{m.sheet}: the cocked pose is held (frames {HOLD[0]}..{HOLD[1]}: the fist and hips move 4 px at most)', moved <= 4.0,
          f'{moved:.1f} px')


def line_checks(m, sts, g):
    """While the hit box is on: the blade along the capsule straight ahead, the tip at its end, at
    the player's height."""
    bad = []
    tips = []
    for t in range(AT.THRUST_W, AT.THRUST_W + AT.LUNGE_FRAMES):
        s = sts[t]
        tp = A.tip(s)
        psi, el = A.angles(s['axis'])
        tips.append((t, tp))
        if not (abs(psi) <= LINE_TURN and abs(tp[1]) <= g['width'] / 2 and tp[0] >= REACH_SHARE * g['reach']
                and 8.0 <= tp[2] <= CA.PLAYER_HEIGHT):
            bad.append(f'{t}: tip {tuple(round(v) for v in tp)}, {psi:.0f} degrees')
    lo = min(tp[0] for _, tp in tips)
    hi = max(tp[2] for _, tp in tips)
    check(f'{m.sheet}: while the hit box is on the blade lies along the capsule (straight ahead within {LINE_TURN:.0f} degrees, '
          f'the tip within {g["width"] / 2:.0f} px of the line, {REACH_SHARE:.0%}+ of {g["reach"]:.0f} px ahead, at the player\'s '
          f'height)', not bad, '; '.join(bad[:3]) or f'tip {lo:.0f}+ px ahead, {hi:.0f} px up at the most')
    before = A.tip(sts[AT.THRUST_W - 4])[0]
    check(f'{m.sheet}: the thrust is driven out with the lunge (the tip 20+ px further ahead at the hit box than 4 frames '
          f'before)', lo - before >= 20.0, f'{before:.0f} -> {lo:.0f} px')


def feet_checks(m, sts):
    lunge = range(AT.THRUST_W, AT.THRUST_W + AT.LUNGE_FRAMES)
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2 and t not in lunge]
    check(f'feet {m.sheet}: one foot at a time outside the lunge', not both, str(both[:8]))
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    # the left foot lands in the lunge and stays where it landed (on the ground)
    land = AT.THRUST_LLAND
    pts = [CA.foot_at(sts[t], 'L') for t in range(land, AT.THRUST_LBACK[0] + 1)]
    planted = all(not up and math.dist(p, pts[0][0]) < 0.3 for p, up in pts)
    ahead = CA.foot_at(sts[land], 'L')[0][0] - CA.foot_at(sts[AT.THRUST_W - 1], 'L')[0][0]
    check(f'feet {m.sheet}: the left foot reaches through and lands in the lunge (frame {land}), planted from there',
          planted and ahead >= 0.9 * AT.LUNGE, f'{ahead:.0f} px on, {"planted" if planted else "MOVES"}')
    # the push: the right foot on the ground to the last frame before the lunge, its leg straightened as
    # it leaves; then the whole body flies - both feet off the ground
    off = lambda st, k: st['feet'][k][2] - CA.K.boot_drop(st['feet'][k][3]) > CA.GROUND
    last = sts[AT.THRUST_W - 1]
    leg = CA.leg_ok(dict(last, feet={'R': last['feet']['R'], 'L': (last['hx'],) + tuple(last['feet']['L'][1:])}))[0]
    fly = [t for t in lunge if off(sts[t], 'R') and off(sts[t], 'L')]
    check(f'feet {m.sheet}: the right (back) foot drives him off - on the ground until frame {AT.THRUST_W - 1}, its leg '
          f'{PUSH_LEG:.0%}+ straight then - and he flies ({FLY_MIN}+ frames with both feet off the ground)',
          not off(last, 'R') and leg >= PUSH_LEG and len(fly) >= FLY_MIN,
          f'right leg {leg:.0%} at frame {AT.THRUST_W - 1}; both feet off at {fly[:1]}..{fly[-1:]} ({len(fly)} frames)')
    # the hips on screen (where the game has him): no jump
    hx_jump = max(abs(b['hx'] - a['hx']) for a, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a['D']) for a, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump on screen (at most {CA.HIP_STEP_X} px forward/back, {CA.HIP_STEP_D} px a frame)',
          hx_jump <= CA.HIP_STEP_X and d_jump <= CA.HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    bends = [sts[t].get('bend', 0.0) for t in lunge]
    gaps = [head_gap(sts[t]) for t in lunge]
    check(f'feet {m.sheet}: through the lunge bent right over ({BEND_MIN:.0f}+ degrees), the head just over the blade '
          f'({HEAD_GAP[0]:.0f}..{HEAD_GAP[1]:.0f} px), the hips low', min(bends) >= BEND_MIN and all(HEAD_GAP[0] <= g <= HEAD_GAP[1]
          for g in gaps) and min(sts[t]['D'] for t in lunge) >= DROP_COCKED,
          f'bent {min(bends):.0f}+, head {min(gaps):.1f}..{max(gaps):.1f} px over the blade, hips {min(sts[t]["D"] for t in lunge)}+ down')
    end = sts[-1]
    check(f'feet {m.sheet}: it ends standing in the carry where the game has him', all(CA.foot_at(end, k)[0] ==
          (AT.LUNGE, 0.0, 0.0) for k in 'RL') and abs(end['hx']) < 1e-6, str({k: end['feet'][k][:2] for k in 'RL'}))


def bounce_feet(b):
    sts = [b.clip.at(t) for t in range(b.total)]
    both = [t for t in range(1, b.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {b.sheet}: one foot at a time', not both, str(both[:8]))
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{bb}' for a, bb in runs[k]) for k in 'RL'))
    end = sts[-1]
    check(f'feet {b.sheet}: ends in the carry where the game has him',
          all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL'), str({k: end['feet'][k][:2] for k in 'RL'}))
    return sts


def entry_feet_checks(m):
    """Starting from a move: one foot at a time from the loop's pose to the thrust's stance (the right
    foot straight to its place back, the left under him)."""
    bad = []
    times, half, end, _ = m.entry_spec
    for kind in CA.AW.KINDS:
        for e in AT.ENTRY_FROM:
            sts = AT.entry(m.clip, kind, e, *m.entry_spec) + [m.clip.at(end)]
            for i in range(1, len(sts)):
                if len(CA.moving(sts[i - 1], sts[i])) == 2:
                    bad.append(f'{kind}{e}:{sts[i - 1]["t"]}')
    check(f'feet {m.sheet}: starting from a move, one foot at a time (each straight to its place in the thrust\'s stance)', not bad,
          ', '.join(bad[:8]))


OTHERS = (('王權橫掃的起手', AT.c1, 40), ('快斬的起手', AT.quick, 18), ('下劈的最高點', AT.cleave, AT.CLEAVE_TOP),
          ('灰燼衝擊的蓄力', AT.impact, AT.IMPACT_TOP))


def distinct_checks(m, at=HOLD[1]):
    """The cocked pose reads apart from every other attack's windup (animation-review §4.5)."""
    i = max(j for j, t in enumerate(m.times) if t <= at)
    for label, fn, t in OTHERS:
        clip = fn()
        sts = AT.poses(clip, [t - 1, t])
        vals = []
        for d in rig.DIRS:
            other = AA.render_pose(d, sts[1], sts[0])
            vals.append(C.sil_change(m.frames()[d][i], other))
        check(f'{m.sheet}: the cocked pose reads apart from {label} (outline {CA.DISTINCT:.0%}+ different, each view)',
              min(vals) >= CA.DISTINCT, ' '.join(f'{v:.0%}' for v in vals))


# 2026-10-05: the side cape solved right (Clip(exact_cape), user: "修") no longer stands over the head, so the top of
# the body is the head: facing left it drops 20 px from frame 30 to 33 (the deepest crouch before the push-off; facing
# right 16). The approved second version moved the head exactly so - the cape over it hid the drop from this check.
# An in-between pose would shift every later pose's index (the interrupt tables) for 4 px; recorded instead.
CA.STEP_WAIVED[('boss_thrust', 'left')] = 20


def main():
    CA._sync()
    ms = ET.moves()
    m, b = ms
    g = game_checks(m, b)
    sts = CC.body_checks(m)
    windup_checks(m, sts)
    line_checks(m, sts, g)
    feet_checks(m, sts)
    CC.edge_checks(m, 18, 66, label='edges up and down (the width in the blade\'s vertical plane), lowered forward to drawn back in: ')
    CC.body_checks(b)
    bounce_feet(b)
    entry_feet_checks(m)
    distinct_checks(m)
    same = all(b.frames()[d][0] == m.frames()[d][m.times.index(AT.THRUST_CONTACT)] for d in rig.DIRS)
    check(f'{b.sheet}: its first pose is the thrust\'s frame {AT.THRUST_CONTACT} (the lunge\'s end)', same)
    for mv in ms:
        CA.frame_checks(mv, entry_feet=True)
        CA.hands_checks(mv)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: the sword held up by the shoulder in the windup (not at
    the hip); both feet stepping back (the left too); a narrow stance (the right foot only 30 back);
    standing upright in the windup; a thrust that stops short of the capsule's end; drawn about a
    lunge of 120 px (the old number); the hips jumping 12 px into the lunge; the first version (user
    2026-10-04: not low enough) - its lunge with the right toe dragging, its cocked pose leaned by the
    shear with the hands at the belly; bent but the head held well over the blade."""
    CA._sync()
    caught = []
    m = ET.moves()[0]
    g = game_numbers()

    def variant(name, edit, steps_edit=None, advance=None):
        keys = [(t, dict(k)) for t, k in m.clip.keys]
        for t, k in keys:
            edit(t, k)
        tracks = {s_: list(v) for s_, v in m.clip.tracks.items()}
        if steps_edit:
            steps_edit(tracks)
        cl = AT.Clip(name, keys, tracks, advance=advance or AT.lunge_advance, musts=m.clip.musts)
        return cl, [cl.at(t) for t in range(m.total)]

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1
    _, sts = variant('shoulder', lambda t, k: k.update(fist=(18.0, 14.0, 118.0)) if HOLD[0] <= t <= HOLD[1] else None)
    caught.append(run(lambda: windup_checks(m, sts)))

    def left_back(tr):
        tr['L'] = [(10, AT.STAND), (22, (-10.0, 0.0, AT.gait.ANKLE_H, 0.0))] + [x for x in tr['L'] if x[0] > 22]
    _, sts = variant('both', lambda t, k: None, left_back)
    caught.append(run(lambda: windup_checks(m, sts)))

    def narrow(tr):
        tr['R'] = [(t, (-30.0,) + f[1:]) if f[0] == -AT.THRUST_STANCE else (t, f) for t, f in tr['R']]
    _, sts = variant('narrow', lambda t, k: k['feet'].update(R=(-30.0,) + AT.THRUST_RB[1:]) if k['feet'].get('R') == AT.THRUST_RB else None, narrow)
    caught.append(run(lambda: windup_checks(m, sts)))
    _, sts = variant('upright', lambda t, k: k.update(lx=4, D=3) if HOLD[0] <= t <= HOLD[1] else None)
    caught.append(run(lambda: windup_checks(m, sts)))
    _, sts = variant('short', lambda t, k: k.update(fist=(k['fist'][0] - 20.0,) + k['fist'][1:]) if AT.THRUST_W <= t <= AT.THRUST_W + 12 else None)
    caught.append(run(lambda: line_checks(m, sts, g)))
    old = lambda t: 120.0 * min(1.0, max(0.0, (t - AT.THRUST_W + 1) / AT.LUNGE_FRAMES))
    cl, _ = variant('old_lunge', lambda t, k: None, advance=old)

    class Fake:
        pass
    f = Fake()
    f.__dict__.update(m.__dict__)
    f.clip = cl
    caught.append(run(lambda: game_checks(f, ET.moves()[1])))

    # the first version's lunge: the right toe dragging along the ground (no flight)
    def dragging(tr):
        tr['R'] = [(t, (x[0], x[1], 0.0, x[3])) if AT.THRUST_W <= t < AT.THRUST_RLAND else (t, x) for t, x in tr['R']]
    _, sts = variant('dragging', lambda t, k: None, dragging)
    caught.append(run(lambda: feet_checks(m, sts)))
    # the first version's cocked pose: leaned 26 degrees by the shear (not bent), the hands at the belly
    def first(t, k):
        if HOLD[0] <= t <= HOLD[1]:
            k.update(bend=0.0, lx=26, D=16, hx=-9.0, tw=-50, bow=-8, fist=(-2.0, 16.0, 77.0), dir=(-12.0, -9.0))
    _, sts = variant('first', first)
    caught.append(run(lambda: windup_checks(m, sts)))
    # bent, but the head held high (well over the blade)
    _, sts = variant('head_up', lambda t, k: k.update(fist=(k['fist'][0], k['fist'][1], k['fist'][2] - 14.0))
                     if HOLD[0] <= t <= HOLD[1] else None)
    caught.append(run(lambda: windup_checks(m, sts)))
    _, sts = variant('jump', lambda t, k: k.update(hx=k['hx'] + 12.0) if t == AT.THRUST_W else None)
    caught.append(run(lambda: feet_checks(m, sts)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
