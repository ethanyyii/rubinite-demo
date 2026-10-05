"""Automatic checks for the starts from a planted sword (planted.py, export_planted.py); exit code 1 on any failure.

    python3 tools/boss_rig/checks_planted.py [--selftest]

Reads the drawn pieces export_planted.py kept (.work/planted/), the sheets and boss_attacks.json.
  - every attack sheet whose opening the game plays has its start, and json's holds add up to where it joins (`end`),
    a frame the attack draws a pose at, before its first step
  - the 3D model at every frame of the way (interrupt.problems: the fists within reach, the blade never through him,
    the legs, the tip not into the ground) and every pose within what a pose may move, into the attack's own pose at
    `end` too (interrupt.step_problems)
  - the first pose is the standing sprite itself; to the next one the top of the body and the upper body move at
    most STEP_MAX
  - the drawn poses: the palette, the container (with its top rows), the top of the body and the upper body at most
    STEP_MAX a pose, the tip TIP_STEP (checks_attack.steps), and so into the attack's pose at `end`; the right fist on
    the drawn grip, no arm drawn longer than it is
"""
import json
import math
import os
import sys
import rig
import boss as B
import checks as C
import checks_attack as CA
import checks_hit as H
import anim_attack as AA
import attack3d as A
import interrupt as I
import planted as P
import export_attack as E
import export_interrupt as X
import export_planted as EP

results = CA.results
check = C.check


def load():
    return json.load(open(os.path.join(E.SHEETS, 'boss_attacks.json')))


def table_checks(data):
    missing, sums = [], []
    for sheet in P.JOIN:
        e = data.get(f'{sheet}_planted_entry')
        if not e:
            missing.append(sheet)
            continue
        m = X.source(sheet)
        ok = sum(e['holds']) == e['end'] and e['end'] in m.times and e['end'] in P.JOIN[sheet]
        ok = ok and P.standing_feet(m.states[m.times.index(e['end'])])
        if not ok:
            sums.append(f'{sheet} holds {sum(e["holds"])} end {e["end"]}')
    check('every attack opening the game plays has its start from the planted sword', not missing, ', '.join(missing))
    check('its holds add up to the frame it joins, a pose of the attack before its first step', not sums, ', '.join(sums))


def model_checks(build=P.build):
    bad, steps = [], []
    for sheet in P.JOIN:
        m = X.source(sheet)
        try:
            st = build(m)
        except ValueError as e:
            bad.append(f'{sheet}: {str(e)[:120]}')
            continue
        b = I.problems(st.clip, st.end, st.end)
        if b:
            bad.append(f'{sheet} {b[:2]}')
        sJ = m.states[m.times.index(st.end)]
        s = I.step_problems(st.clip, st.times + [st.end])
        d, t = I.pose_dist(st.clip.at(st.end), sJ)
        if s or d > 0.5 or t > 0.5:
            steps.append(f'{sheet} {s[:2]} end off {d:.1f}/{t:.1f}')
    check('3D: the fists within reach, the blade never through him, the legs, the tip out of the ground', not bad,
          '; '.join(bad[:4]))
    check(f'3D: every pose within {I.STEP_BODY:.0f} px (body) / {I.STEP_TIP:.0f} px (tip) of the last, into the '
          f'attack\'s own pose', not steps, '; '.join(steps[:4]))


def frame_checks(data, piece=EP.piece):
    pal = set(B.load_palette())
    idle = X.sheet_frames('boss_idle', (rig.FW, rig.FH), (rig.AX, rig.AY))
    off_pal, outside, first, fist, long_arm = [], [], [], [], []
    for sheet in P.JOIN:
        pc = piece(sheet)
        AA.SWORD.update(pc['sword'])
        AA.JOINTS.update(pc['joints'])
        e = data[f'{sheet}_planted_entry']
        top = e['cell'][1] - X.AW.BIG[1]
        name = f'P_{sheet}'
        m = X.source(sheet)
        iJ = m.times.index(e['end'])
        sJ, s0 = dict(m.states[iJ], name='J_' + sheet, i=0), dict(m.states[iJ - 1], name='J_' + sheet, i=-1)
        label = f'{sheet} planted start'
        for d in rig.DIRS:
            fr = pc['frames'][d]
            if fr[0] != {q: tuple(c[:3]) for q, c in idle[d][0].items()}:
                first.append(f'{sheet} {d}')
            if sorted({c for f in fr for c in f.values() if tuple(c) not in pal}):
                off_pal.append(f'{sheet} {d}')
            xs = [q[0] for f in fr for q in f]
            ys = [q[1] for f in fr for q in f]
            if (min(xs) < -X.AW.EXT or max(xs) >= X.AW.BIG[0] - X.AW.EXT or min(ys) < -X.AW.EXT - top
                    or max(ys) >= X.AW.BIG[1] - X.AW.EXT):
                outside.append(f'{sheet} {d}')
            # the standing sprite to the first drawn pose (the sword low by his side in both: the head and shoulders)
            dt = abs(H.top(fr[0]) - H.top(fr[1]))
            de = abs(H.edges(fr[0])[0] - H.edges(fr[1])[0])
            check(f'{label} {d}: from the standing sprite the top of the body and the upper body move at most '
                  f'{CA.STEP_MAX} px', dt <= CA.STEP_MAX and de <= CA.STEP_MAX, f'top {dt} edge {de}')
            # the drawn poses, and on into the attack's own pose at `end` (drawn again here, with its records)
            fJ = AA.render_pose(d, sJ, s0)
            names = [(name, i) for i in range(1, len(fr))] + [('J_' + sheet, 0)]
            frames = fr[1:] + [fJ]
            swords = [CA.drawn(d, nm, i)[0] for nm, i in names]
            grips = [CA.grip(d, nm, i) for nm, i in names]
            tips = []
            for nm, i in names:
                pl_ = CA.drawn(d, nm, i)[1]
                tips.append(CA.tip_xy(d, pl_) if pl_ else None)
            arms = [CA.joints(d, nm, i) for nm, i in names]
            CA.steps(label, d, frames, swords, grips, tips, arms)
        for i, s in enumerate(pc['states']):
            if i == 0:
                continue
            for d in rig.DIRS:
                J = AA.JOINTS.get((d, name, i, 'R'))
                rec = AA.SWORD.get((d, name, i))
                if J and rec and math.dist(J['hand'], rec[2]) >= 0.6:
                    fist.append(f'{sheet} {d} {i}')
                for k in 'RL':
                    J = AA.JOINTS.get((d, name, i, k))
                    if J and math.dist(J['shoulder'], J['hand']) > A.arm_lengths(s, k)[3] + 0.5:
                        long_arm.append(f'{sheet} {d} {i}{k}')
    check('the first pose is the standing sprite itself', not first, ', '.join(first[:4]))
    check('every colour in the palette', not off_pal, ', '.join(off_pal[:4]))
    check('inside the container (with its top rows)', not outside, ', '.join(outside[:4]))
    check('holding the sword, the right fist\'s centre is on the drawn grip', not fist, ', '.join(fist[:4]))
    check('no drawn arm longer than the arm', not long_arm, ', '.join(long_arm[:4]))


def main():
    CA._sync()
    data = load()
    table_checks(data)
    model_checks()
    frame_checks(data)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: a way whose sword goes back through his chest; a start that does not
    begin on the standing sprite; a pose in the middle moved 30 px; json's holds not adding up to where it joins."""
    import copy
    CA._sync()
    data = load()
    caught = []

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1

    # the sword pointed back through his chest half-way
    def through(m):
        st = P.build(m)
        keys = list(st.clip.clip.keys)
        t_mid = keys[len(keys) // 2][0] if len(keys) > 2 else keys[-1][0] // 2
        k = dict(keys[-1][1])
        k['dir'] = (180.0, -10.0)
        k['fist'] = (20.0, 0.0, 100.0)
        keys = sorted([kk for kk in keys if kk[0] != t_mid] + [(t_mid, k)], key=lambda kk: kk[0])
        clip = P.AT.Clip('planted', keys, ground=True, lead=False, exact_cape=True, **I._flags(m.clip))
        return P.Start(m.sheet, P.Paced(clip, keys[-1][0], st.end), st.times, st.way)
    caught.append(run(lambda: model_checks(through)))

    def edit(sheet, fn):
        def piece(sh):
            pc = EP.piece(sh)
            if sh == sheet:
                pc = copy.deepcopy(pc)
                fn(pc)
            return pc
        return piece

    def moved(f, dy):
        return {(x, y + dy): c for (x, y), c in f.items()}
    for fn in (lambda pc: [pc['frames'][d].__setitem__(0, pc['frames'][d][1]) for d in rig.DIRS],
               lambda pc: [pc['frames'][d].__setitem__(4, moved(pc['frames'][d][4], -30)) for d in rig.DIRS]):
        caught.append(run(lambda: frame_checks(data, edit('boss_c1', fn))))
    d2 = copy.deepcopy(data)
    d2['boss_cleave_planted_entry']['holds'][-1] += 2
    caught.append(run(lambda: table_checks(d2)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
