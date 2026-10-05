"""Automatic checks for the interrupted attacks (interrupt.py, export_interrupt.py); exit code 1 on any failure.

    python3 tools/boss_rig/checks_interrupt.py [--selftest]

Reads the plan and the drawn pieces export_interrupt.py kept (.work/), the sheets and boss_attacks.json.
  - every pose he can be hit in has its start (break: all but the leap's air; stagger: the recovery), and json says so
  - the jump from a pose to its start's first pose (the jolt) at most interrupt.HIT_BODY / HIT_TIP (+ the jolt)
  - the 3D model at every frame of every way (interrupt.problems: the fists within reach, the held blade never
    through him, the legs, the tip not in the ground before it is put in)
  - the drawn poses: the palette, the container (with its top rows), nothing below the foot line beyond what is
    nearer the camera, the top of the body and the upper body at most STEP_MAX a pose, the tip TIP_STEP
    (checks_attack.steps) - the stagger out of the ash spin's turn TIP_STEP_SPIN; the right fist on the drawn grip,
    no arm drawn longer than it is
  - the break's last pose to boss_kneel_down's next (the junction): the top of the body and the upper body's column
    at most STEP_MAX; the stagger's last pose is the carry
"""
import json
import math
import os
import pickle
import sys
from PIL import Image
import rig
import boss as B
import checks as C
import checks_attack as CA
import checks_hit as H
import anim_walk as AW
import anim_attack as AA
import attack3d as A
import interrupt as I
import export_attack as E
import export_interrupt as X

results = CA.results
check = C.check
JOLT_BODY, JOLT_TIP = 12.0, 20.0     # px the jolt (head back, lean back) adds to the jump
# STAGGER is 0.3 s: from a recovery pose with more to do than FAST_SHARE of 13 frames of poses within the limits can
# (pose_dist against STEP_* summed: the ash spin just out of its turn, the leap's landing with the sword still on his
# back - up out of the crouch / kneel and the sword drawn) the poses move up to these (told to the user)
STAGGER_FRAMES = I.STAGGER - 2 - I.HIT_HOLD
FAST_STEP, FAST_TIP = 22, 100
FAST_SHARE = 0.8                     # (a drawn arm raised over the head reads 2 px further than its 3D)


def _sync():
    CA._sync()


def load():
    pl = X.load_plan()
    data = json.load(open(os.path.join(E.SHEETS, 'boss_attacks.json')))
    return pl, data


def install(pc):
    """Put a piece's drawn swords and arms where checks_attack's helpers look for them."""
    AA.SWORD.update(pc['sword'])
    AA.JOINTS.update(pc['joints'])


def cover_checks(pl, data):
    missing, wrong = [], []
    for m in X.sources():
        for kind in X.KINDS:
            al = set(X.allowed(m, kind))
            ps = pl['sheets'][m.sheet].get(kind, [])
            for i in range(len(m.states)):
                if (i in al) != (bool(ps) and ps[i] >= 0):
                    missing.append(f'{m.sheet} {kind} {i}')
            if al:
                e = data.get(f'{m.sheet}_{kind}')
                if not e or [e['starts'][j]['start'] if j >= 0 else -1 for j in e['pose_start']] != ps:
                    wrong.append(f'{m.sheet}_{kind}')
    check('every pose he can be hit in has its start (break: all but the leap in the air; stagger: the recovery)',
          not missing, ', '.join(missing[:6]))
    check('boss_attacks.json gives each pose its start', not wrong, ', '.join(wrong[:6]))


def jump_checks(pl):
    worst_b, worst_t, where = 0.0, 0.0, ''
    bad = []
    firsts = {}
    for sp in pl['starts']:
        firsts[sp['id']] = X.piece(sp['id'])['states'][0]
    for m in X.sources():
        for kind in X.KINDS:
            for i, sid in enumerate(pl['sheets'][m.sheet].get(kind, [])):
                if sid < 0:
                    continue
                d, t = I.pose_dist(m.states[i], firsts[sid])
                if d > worst_b or t > worst_t:
                    where = f'{m.sheet} {kind} pose {i} -> {sid}'
                worst_b, worst_t = max(worst_b, d), max(worst_t, t)
                if d > I.HIT_BODY + JOLT_BODY or t > I.HIT_TIP + JOLT_TIP:
                    bad.append(f'{m.sheet} {kind} {i}->{sid} {d:.0f}/{t:.0f}')
    check(f'the jump from a pose to its start\'s jolt at most {I.HIT_BODY + JOLT_BODY:.0f} px (head, hands, feet) and '
          f'{I.HIT_TIP + JOLT_TIP:.0f} (tip), on screen', not bad, f'worst {worst_b:.0f}/{worst_t:.0f} ({where}) ' + ', '.join(bad[:4]))


def model_checks(pl):
    bad = []
    for sp in pl['starts']:
        b = X.bridge_of(sp)
        if sp['kind'] == 'stagger':
            pr = I.problems(b.clip, I.STAGGER - 2, 0)
        else:
            t_above = sp['keys'][-2][0]
            tg = next(t for t in range(b.clip.T + 1) if b.clip.src_time(t) >= t_above - 1e-6)
            pr = I.problems(b.clip, b.clip.T, tg)
        if pr:
            bad.append(f'{sp["id"]} ({sp["source"]} {sp["kind"]} {sp["pose"]}): {pr[:2]}')
    check('model: every frame of every way - the fists within reach, the held blade never through him, the legs, '
          'the tip not in the ground before it goes in', not bad, '; '.join(bad[:4]))


def frame_checks(pl, data):
    pal = set(B.load_palette())
    kd = Image.open(os.path.join(E.SHEETS, 'boss_kneel_down.png')).convert('RGBA')
    kd_rows = {'down': 0, 'right': 1, 'up': 2, 'left': 3}
    col = X.KNEEL_COLS[0]
    kd_next = {}
    for d in rig.DIRS:
        cell = kd.crop((col * 384, kd_rows[d] * 336, (col + 1) * 384, (kd_rows[d] + 1) * 336))
        px = cell.load()
        kd_next[d] = {(x - AW.EXT, y - AW.EXT): px[x, y] for x in range(384) for y in range(336) if px[x, y][3] > 0}
    tops = {}
    for key, e in data.items():
        if key.endswith('_break') or key.endswith('_stagger'):
            for st in e['starts']:
                tops[st['start']] = st['cell'][1] - AW.BIG[1]
    off_pal, outside, low, fist, long_arm, junction, stag_end = [], [], [], [], [], [], []
    worst_j = (0, 0)
    carry = {d: E.carry_frame(d) for d in rig.DIRS}
    c0 = {d: AW.SWORD_DRAWN.get((d, 'carry', 0)) for d in rig.DIRS}
    for sp in pl['starts']:
        pc = X.piece(sp['id'])
        install(pc)
        name = f'S{sp["id"]}'
        sts = pc['states']
        label = f'start {sp["id"]} ({sp["source"]} {sp["kind"]} pose {sp["pose"]})'
        top = tops.get(sp['id'], 0)

        class NS:
            states = sts
        for d in rig.DIRS:
            fr = pc['frames'][d]
            bad = sorted({c for f in fr for c in f.values() if tuple(c) not in pal})
            if bad:
                off_pal.append(f'{label} {d}')
            xs = [q[0] for f in fr for q in f]
            ys = [q[1] for f in fr for q in f]
            if min(xs) < -AW.EXT or max(xs) >= AW.BIG[0] - AW.EXT or min(ys) < -AW.EXT - top or max(ys) >= AW.BIG[1] - AW.EXT:
                outside.append(f'{label} {d}')
            n = len(fr)
            names = [(name, i) for i in range(n)]
            swords = [CA.drawn(d, nm, i)[0] for nm, i in names]
            grips = [CA.grip(d, nm, i) for nm, i in names]
            tips = []
            for nm, i in names:
                pl_ = CA.drawn(d, nm, i)[1]
                tips.append(CA.tip_xy(d, pl_) if pl_ else None)
            arms = [CA.joints(d, nm, i) for nm, i in names]
            if sp['kind'] == 'stagger':
                if c0[d]:
                    sw, p0 = c0[d]
                    if d == 'left':
                        sw = {(2 * rig.AX - x, y): c for (x, y), c in sw.items()}
                    g = p0['grip']
                    swords[-1], grips[-1] = sw, ((2 * rig.AX - g[0], g[1]) if d == 'left' else g)
                    tips[-1] = CA.tip_xy(d, p0) if 'axis' in p0 else None
                arms[-1] = CA.joints(d, 'carry', 0)
                if fr[-1] != carry[d]:
                    stag_end.append(f'{label} {d}')
            bodies = [H.body(f_, sw) for f_, sw in zip(fr, swords)]
            lim = max(CA.below_allowed(NS, d), CA.feet_below(NS, d))
            if sp['source'].startswith('boss_spin'):
                # the ash spin's own allowance: its feet as the facing each pose is drawn with has them
                import checks_spin as CS
                lim = max(lim, CS.spin_feet_below(X.source(sp['source']), d))
            lowest = max(q[1] for f in bodies for q in f) - H.GROUND
            if lowest > lim:
                low.append(f'{label} {d} {lowest:+d}/{lim}')
            fast = sp['kind'] == 'stagger' and X.bridge_of(sp).clip.ls[-1] > FAST_SHARE * STAGGER_FRAMES
            if fast:
                old = CA.TIP_STEP, CA.STEP_MAX
                CA.TIP_STEP, CA.STEP_MAX = FAST_TIP, FAST_STEP
            CA.steps(label + (' (more than 0.3 s of moving)' if fast else ''), d, fr, swords, grips, tips, arms)
            if fast:
                CA.TIP_STEP, CA.STEP_MAX = old
            if sp['kind'] == 'break':
                a, b = bodies[-1], kd_next[d]
                dt = abs(H.top(a) - H.top(b))
                ea, eb = H.edges(a, grips[-1]), H.edges(b, None)
                de = max(abs(p - q) for p, q in zip(ea, eb))
                worst_j = max(worst_j, (max(dt, de), sp['id']))
                if dt > CA.STEP_MAX or de > CA.STEP_MAX:
                    junction.append(f'{label} {d} top {dt} edge {de}')
        for i, s in enumerate(sts[:-1] if sp['kind'] == 'stagger' else sts):
            for d in rig.DIRS:
                J = AA.JOINTS.get((d, name, i, 'R'))
                rec = AA.SWORD.get((d, name, i))
                if J and rec and not s.get('back'):
                    if math.dist(J['hand'], rec[2]) >= 0.6:
                        fist.append(f'{label} {d} {i}')
                for k in 'RL':
                    J = AA.JOINTS.get((d, name, i, k))
                    if J and math.dist(J['shoulder'], J['hand']) > A.arm_lengths(s, k)[3] + 0.5:
                        long_arm.append(f'{label} {d} {i}{k}')
    check('every colour in the palette', not off_pal, ', '.join(off_pal[:4]))
    check('inside the container (with its top rows)', not outside, ', '.join(outside[:4]))
    check('nothing below the foot line beyond what is nearer the camera', not low, ', '.join(low[:4]))
    check('holding the sword, the right fist\'s centre is on the drawn grip', not fist, ', '.join(fist[:4]))
    check('no drawn arm longer than the arm', not long_arm, ', '.join(long_arm[:4]))
    check(f'the break\'s last pose to boss_kneel_down column {X.KNEEL_COLS[0] + 1}: the top of the body and the upper body '
          f'at most {CA.STEP_MAX} px', not junction, f'worst {worst_j[0]} (start {worst_j[1]}) ' + ', '.join(junction[:4]))
    check('the stagger ends on the carry', not stag_end, ', '.join(stag_end[:4]))


def main():
    _sync()
    pl, data = load()
    cover_checks(pl, data)
    jump_checks(pl)
    model_checks(pl)
    frame_checks(pl, data)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: a pose given a start far from it; a way whose sword goes through him;
    the break's last pose 30 px off the kneel it goes on to; a pose in a way jumping 30 px; a stagger not ending on
    the carry; a pose without a start."""
    import copy
    _sync()
    pl, data = load()
    caught = []

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1
    # a pose of the royal sweep given the leap's start made for its landing (far from it)
    far = next(sp['id'] for sp in pl['starts'] if sp['source'] == 'boss_leap' and sp['kind'] == 'break' and sp['pose'] > 70)
    p1 = copy.deepcopy(pl)
    p1['sheets']['boss_c1']['break'][0] = far
    caught.append(run(lambda: jump_checks(p1)))
    # a way through him: its first waypoint's sword pointed back through his chest
    sp = copy.deepcopy(next(sp for sp in pl['starts'] if sp['kind'] == 'break' and len(sp['keys']) > 3))
    k = sp['keys'][2][1]
    k['dir'] = [180.0, -10.0]
    k['fist'] = [20.0, 0.0, 100.0]
    p2 = {'starts': [sp], 'sheets': {}}
    caught.append(run(lambda: model_checks(p2)))
    # the pieces: one break's last pose moved up 30 px; a pose in the middle moved 30 px; a stagger's last not the carry
    real_piece = X.piece
    br = next(sp for sp in pl['starts'] if sp['kind'] == 'break')
    st = next(sp for sp in pl['starts'] if sp['kind'] == 'stagger')

    def moved(f, dy):
        return {(x, y + dy): c for (x, y), c in f.items()}

    def edit(sid, fn):
        def piece(i):
            pc = real_piece(i)
            if i == sid:
                pc = copy.deepcopy(pc)
                fn(pc)
            return pc
        return piece
    for sid, fn in ((br['id'], lambda pc: [pc['frames'][d].__setitem__(-1, moved(pc['frames'][d][-1], -30)) for d in rig.DIRS]),
                    (br['id'], lambda pc: [pc['frames'][d].__setitem__(3, moved(pc['frames'][d][3], -30)) for d in rig.DIRS]),
                    (st['id'], lambda pc: [pc['frames'][d].__setitem__(-1, moved(pc['frames'][d][-1], -2)) for d in rig.DIRS])):
        X.piece = edit(sid, fn)
        one = {'starts': [next(sp for sp in pl['starts'] if sp['id'] == sid)], 'sheets': pl['sheets']}
        caught.append(run(lambda: frame_checks(one, data)))
        X.piece = real_piece
    # a pose without its start
    p6 = copy.deepcopy(pl)
    p6['sheets']['boss_quick']['break'][5] = -1
    caught.append(run(lambda: cover_checks(p6, data)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
