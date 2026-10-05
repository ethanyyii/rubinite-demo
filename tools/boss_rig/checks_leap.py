"""Automatic checks for the king's leap (墜王之躍, C7 躍起與落地, attacks.leap, export_leap.py); exit code 1 on any failure.

    python3 tools/boss_rig/checks_leap.py [--selftest]

The attack checks (checks_attack: the finished frames, the drawn arms) run on these clips too. What is new
(user 2026-10-04: "劍會收放在背上（斜掛著），然後蹲下蓄力準備起跳，起跳後落地用右手全頭砸向地面，之後再把劍從背上拿下來恢復正常姿勢"):
  - the game's numbers (veltharis_data.gd kings_leap: the crouch, the take-off, the lock, the landing = the hit box,
    the recovery, the bounce, the circle) are the art's
  - the sword on his back: slung there from frame LEAP_BACK[0] (the hand lets go just where the slung grip is: no jump)
    to LEAP_BACK[1] (taken off it again from there); in between the right hand does not touch it, and the hand is free
  - the feet: both on the ground until the take-off, both off it all through the air, both down on landing; one foot at
    a time outside the take-off and the landing; the right knee down on landing (the kneel); the legs never longer
    than they are
  - the height: off the ground only in the air, LEAP_MIN+ px at the top, no jump from one frame to the next beyond a
    thrown body's speed
  - the blow: as he lands the right fist is on the ground (its lowest point 0 .. 2 px over it, in 3D and as drawn in
    the side views), bent right over, and it stays down through the impact
  - the 3D model: the arms reach (the right arm drawn longer only for the blow: at most checks_cleave.ARM_K_MAX), the
    held blade misses the body, the slung sword and every blade above the ground
  - it ends in the carry; the crouch reads apart from every other attack's windup
The knee rule (no knee as high as the hip, checks_attack.leg_ok) is left out while he goes down into and stays in the
kneel: its front knee is that high in the approved kneel (anim_kneel.kneel_legs; user 2026-10-01 "都通過").
"""
import math
import os
import re
import sys
import boss as B
import rig
import anim_kneel as K
import attacks as AT
import attack3d as A
import anim_attack as AA
import checks as C
import checks_attack as CA
import checks_cleave as CC
import checks_upswing as CU
import export_leap as EL

results = CA.results
check = C.check
LEAP_MIN = 70.0             # px off the ground at the top at the least
AIR_STEP = 10.0             # px the hips may rise or fall in a frame (a body thrown 90 px up and back in 0.8 s: 7.7 at most)
GROUND_STEP = 2             # px on the ground (checks_attack.HIP_STEP_D) ...
PUSH_STEP = 8.0             # ... the crouch, the push off (speeding up to the take-off speed, 7.7 a frame) and the weight taken after landing
FIST_TOUCH = (-1.0, 1.0)    # rows below the foot line of the drawn fist's lowest row as it lands (touching it)
FIST_Z = (5.0, 9.0)         # px: the fist's centre over the ground (the drawn fist reaches 6.4 below it)
LAND_BEND = 40.0
FREE_GAP = 8.0              # px the free right fist keeps off the slung grip
KNEEL_SPAN = (80, AT.LEAP_RSTEP[0] + 2)  # going down into the kneel and in it until the right knee comes up (the kneel's rule)
CROUCH = (AT.LEAP_BACK[0], AT.LEAP_UP)  # the crouch for the leap and the push off: down in a sixth of a second, the legs straight in a few frames
BOUNCE_KNEEL = (0, 18)


def game_numbers():
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    f = re.search(r'out\[&"kings_leap"\] = _move\(.*?\{"airborne_start": ([0-9.]+)', src, re.S)
    body = f.group(0)
    num = lambda pat: float(re.search(pat, body).group(1))
    return {'interval': num(r'"interval": ([0-9.]+)'), 'active': num(r'"active": ([0-9.]+)'), 'bounce': num(r'"bounce_time": ([0-9.]+)'),
            'lock': num(r'"lock_before": ([0-9.]+)'), 'recovery': num(r'\], ([0-9.]+), \{"airborne_start"'), 'air': float(f.group(1)),
            'circle': 'SH.CIRCLE' in body and 'LEAP_RADIUS' in body, 'radius': get('LEAP_RADIUS')}


def game_checks(m, b):
    g = game_numbers()
    fr = lambda s: CU.round_half_up(s * 60)
    w = fr(g['interval'])
    ok = (m.hits == [(w, fr(g['active']))] and (AT.LEAP_W, AT.LEAP_UP, AT.LEAP_LOCK) == (w, fr(g['air']), w - fr(g['lock']))
          and m.total == w + fr(g['active']) + fr(g['recovery']) and sum(b.holds) == fr(g['bounce']) and g['circle'])
    check(f'{m.sheet}: the game\'s timing (veltharis_data kings_leap) is the art\'s', ok,
          f'game: off the ground {fr(g["air"])}, locked {w - fr(g["lock"])}, lands (hit) {w}..{w + fr(g["active"]) - 1}, recovery '
          f'{fr(g["recovery"])}, bounce {fr(g["bounce"])} / art {AT.LEAP_UP}, {AT.LEAP_LOCK}, {m.hits}, {m.total} frames, bounce {sum(b.holds)}')
    return g


def model_checks(m, sts, kneel):
    reach_bad, hits, legs = [], [], []
    worst_leg, worst_low, worst_k = 0.0, 99.0, 1.0
    for t, st in enumerate(sts):
        for k, a in A.arms(st).items():
            if a and a[3] < -0.5:
                reach_bad.append(f'{t}{k}({a[3]:.1f})')
        h = A.body_hits(st)
        if h:
            hits.append(f'{t}:{h[0][1]}')
        wl, low, kh = CA.leg_ok(st)
        worst_leg, worst_low = max(worst_leg, wl), min(worst_low, low)
        if kh and not (kneel[0] <= t <= kneel[1]):
            legs.append(t)
        worst_k = max(worst_k, st.get('arm_k', 1.0))
    check(f'model {m.sheet}: both fists within the arms\' reach at every frame', not reach_bad, ', '.join(reach_bad[:6]))
    check(f'model {m.sheet}: the held blade never passes through the body, the shoulder plates or the helmet', not hits,
          ', '.join(hits[:6]))
    check(f'model {m.sheet}: no leg reaches further than it is long', worst_leg <= 1.0 + 1e-6, f'longest {worst_leg:.3f}')
    check(f'model {m.sheet}: no boot goes into the ground', worst_low >= -0.6, f'lowest {worst_low:+.2f} px')
    check(f'model {m.sheet}: no knee as high as the hip (outside the kneel, frames {kneel[0]}..{kneel[1]})', not legs, str(legs[:6]))
    low = min((A.tip(st)[2], t) for t, st in enumerate(sts))
    check(f'model {m.sheet}: the blade\'s tip never in the ground (in the hand or slung on his back)', low[0] > 0.5,
          f'lowest {low[0]:.1f} px at frame {low[1]}')
    check(f'model {m.sheet}: the arms drawn longer only up to x{CC.ARM_K_MAX}', worst_k <= CC.ARM_K_MAX + 1e-6, f'x{worst_k:.2f}')


def elbow_bent_back(sh, e, g):
    """An elbow bent the wrong way, seen from the side (he faces forward all through the leap: the body turned under
    10 degrees): the elbow below the shoulder with the fist behind it while the elbow is before / below the line from
    the shoulder to the fist (the forearm folded back behind the upper arm), or the elbow before the shoulder with the
    fist behind it. (Above the shoulder - the hand reaching back over it for the hilt - the forearm folds back: right.)"""
    if e[2] >= sh[2] + 2.0:
        return False
    d, v = (g[0] - sh[0], g[2] - sh[2]), (e[0] - sh[0], e[2] - sh[2])
    side = d[0] * v[1] - d[1] * v[0]
    return (g[0] < e[0] - 4.0 and side > 2.0) or (e[0] - sh[0] > 4.0 and g[0] - sh[0] < -4.0)


def elbow_checks(mv, sts):
    bad = [f'{t}{k}' for t, st in enumerate(sts) for k, a in A.arms(st).items() if a and elbow_bent_back(*a[:3])]
    check(f'model {mv.sheet}: no elbow bent back the wrong way (the forearm folded back behind the upper arm; user 2026-10-05 '
          f'"手肘往後…拳頭一樣在前面", "收劍後的幾貞手又後翻了")', not bad, ', '.join(bad[:8]))


def back_checks(m, sts):
    a, b = AT.LEAP_BACK
    slung = [t for t in range(m.total) if sts[t].get('back')]
    check(f'{m.sheet}: the sword is slung on his back from frame {a} to {b - 1} (and only then)', slung == list(range(a, b)),
          f'{slung[:1]}..{slung[-1:]}')
    # no jump where the hand lets go of it and takes it again: the held sword, the frame before it is slung and the
    # frame it is taken, is just where the slung one is for that frame's body (the body's own move between frames
    # carries both alike)
    jumps = []
    for t in (a - 1, b):
        h = sts[t]
        g, ax, _ = A.back_sword(dict(h, back=True))
        gh, axh = A.sword_grip(h), A.sword_axis(h)
        jumps.append((math.dist(g, gh), math.degrees(math.acos(max(-1.0, min(1.0, A.dot(ax, axh)))))))
    check(f'{m.sheet}: the hand lets go of the sword and takes it again just where it is slung (frames {a - 1}, {b}: within '
          f'2 px, 4 degrees)', all(d <= 2.0 and r <= 4.0 for d, r in jumps), ', '.join(f'{d:.1f} px {r:.0f} deg' for d, r in jumps))
    touch = [t for t in range(a + 6, b - 6) if math.dist(sts[t]['fist'], A.back_sword(sts[t])[0]) < FREE_GAP]
    check(f'{m.sheet}: in between the right hand is off the hilt ({FREE_GAP:.0f}+ px from it)', not touch, str(touch[:6]))


def feet_checks(m, sts):
    off = lambda st, k: CA.foot_at(st, k)[1]
    before = [t for t in range(AT.LEAP_UP) if off(sts[t], 'R') or off(sts[t], 'L')]
    air = [t for t in range(AT.LEAP_UP, AT.LEAP_W) if not (off(sts[t], 'R') and off(sts[t], 'L'))]
    land = [k for k in 'RL' if off(sts[AT.LEAP_W], k)]
    check(f'feet {m.sheet}: both feet on the ground until the take-off (frame {AT.LEAP_UP}), both off it all through the air, '
          f'both down as he lands (frame {AT.LEAP_W})', not before and not air and not land,
          f'off before: {before[:4]}, on in the air: {air[:4]}, up on landing: {land}')
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2 and not (AT.LEAP_UP - 1 <= t <= AT.LEAP_W)]
    check(f'feet {m.sheet}: one foot at a time outside the leap (frames {AT.LEAP_UP - 1}..{AT.LEAP_W})', not both, str(both[:8]))
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    L = K.gait.solve(K.gait.HIP_REST - sts[AT.LEAP_W]['D'], sts[AT.LEAP_W]['feet']['R'][0::2][:2], sts[AT.LEAP_W]['feet']['R'][3])
    check(f'feet {m.sheet}: the right knee down as he lands (the kneel: its joint {K.KNEE_Z:.1f} px up, 3 px either way)',
          abs(L['knee'][1] - K.KNEE_Z) <= 3.0, f'{L["knee"][1]:.1f} px up')
    hips = [K.gait.HIP_REST - s['D'] + s.get('lift', 0.0) for s in sts]
    steps = [(t, abs(hips[t] - hips[t - 1])) for t in range(1, m.total)]
    crouch = range(CROUCH[0], AT.LEAP_UP)
    settle = range(AT.LEAP_W + 1, AT.LEAP_W + 5)
    ground = [(t, d) for t, d in steps if not (t in crouch or AT.LEAP_UP <= t <= AT.LEAP_W or t in settle) and d > GROUND_STEP]
    push = [(t, d) for t, d in steps if (t in crouch or t in settle) and d > PUSH_STEP]
    # the touchdown frame is the fall's last
    flight = [(t, d) for t, d in steps if AT.LEAP_UP <= t <= AT.LEAP_W and d > AIR_STEP]
    check(f'feet {m.sheet}: the hips never jump (on the ground {GROUND_STEP} px a frame; the crouch for the leap, the push off and '
          f'the weight taken after landing {PUSH_STEP}; in the air {AIR_STEP:.0f})', not ground and not push and not flight, f'{ground[:3]} {push[:3]} {flight[:3]}')
    end = sts[-1]
    check(f'feet {m.sheet}: it ends standing in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL')
          and abs(end['hx']) < 1e-6 and not end.get('back'), str({k: end['feet'][k][:2] for k in 'RL'}))


def height_checks(m, sts):
    lifts = [s.get('lift', 0.0) for s in sts]
    out = [t for t, L in enumerate(lifts) if L > 0.5 and not (AT.LEAP_UP <= t < AT.LEAP_W)]
    top = max(lifts)
    at = lifts.index(top)
    check(f'{m.sheet}: off the ground only in the air (frames {AT.LEAP_UP}..{AT.LEAP_W - 1}), {LEAP_MIN:.0f}+ px at the top',
          not out and top >= LEAP_MIN, f'{top:.0f} px at frame {at}; off the ground out of the air at {out[:4]}')


def blow_checks(m, sts):
    """The fist on the ground as drawn (the handoff: measure the drawn fist): its lowest row on the foot line (FIST_TOUCH,
    side views), from the landing through the impact; in 3D its centre over the ground by about the drawn fist's reach
    below it (the fist pointing down: 6.4 px), and still."""
    a, b = AT.LEAP_SMASH
    zs = [sts[t]['fist'][2] for t in range(a, b + 1)]
    s = sts[a]
    check(f'{m.sheet}: as he lands the right fist comes down on the ground before him and stays (frames {a}..{b}; its centre '
          f'{FIST_Z[0]:.0f}..{FIST_Z[1]:.0f} px up, still), bent right over ({LAND_BEND:.0f}+ degrees)',
          all(FIST_Z[0] <= z <= FIST_Z[1] for z in zs) and max(zs) - min(zs) < 0.5 and s.get('bend', 0.0) >= LAND_BEND,
          f'{min(zs):.1f}..{max(zs):.1f} px, bent {s.get("bend", 0.0):.0f}')
    drawn = []
    for i, st in enumerate(m.states):
        if not (a <= st['t'] <= b):
            continue
        for d in ('right', 'left'):
            J = AA.JOINTS.get((d, m.clip.name, i, 'R'))
            if J:
                fist = AA.arm_pieces(J, True)[2]
                drawn.append(max(y for _, y in fist) - rig.AY)
    check(f'{m.sheet}: the fist is drawn on the ground in the side views (its lowest row {FIST_TOUCH[0]:.0f}..{FIST_TOUCH[1]:.0f} px '
          f'below the foot line: touching it)', drawn and all(FIST_TOUCH[0] <= v <= FIST_TOUCH[1] for v in drawn),
          f'{min(drawn):+d}..{max(drawn):+d}' if drawn else 'no fist measured')


def hands_checks(m):
    """checks_attack.hands_checks for the poses the right hand holds the sword; the drawn arms' lengths for all."""
    worst = 0.0
    free = 0
    for s in m.states[1:-1]:
        for d in rig.DIRS:
            J = AA.JOINTS.get((d, s['name'], s['i'], 'R'))
            g = AA.SWORD[(d, s['name'], s['i'])][2]
            if not J:
                continue
            if s.get('back'):
                free += 1
                continue
            worst = max(worst, math.dist(J['hand'], g))
    check(f'{m.sheet}: holding the sword, the right fist\'s centre is on the drawn grip in every view ({free} poses free)', worst < 0.6,
          f'worst {worst:.2f} px')
    long_ = []
    for key, J in AA.JOINTS.items():
        if key[1] != m.clip.name:
            continue
        n = math.dist(J['shoulder'], J['hand'])
        st = m.states[key[2]] if key[2] < len(m.states) else {}
        lim = A.arm_lengths(st, key[3])[3]
        if n > lim + 0.5:
            long_.append(f'{key[0]}:{key[2]}{key[3]} {n:.1f}/{lim:.1f}')
    check(f'{m.sheet}: no drawn arm longer than the arm (longer only where the pose says so: the blow)', not long_, ', '.join(long_[:6]))


def bounce_checks(m, b):
    sts = [b.clip.at(t) for t in range(b.total)]
    model_checks(b, sts, BOUNCE_KNEEL)
    both = [t for t in range(1, b.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {b.sheet}: one foot at a time', not both, str(both[:8]))
    end = sts[-1]
    check(f'feet {b.sheet}: ends in the carry', all(CA.foot_at(end, k)[0] == (0.0, 0.0, 0.0) for k in 'RL') and not end.get('back'),
          str({k: end['feet'][k][:2] for k in 'RL'}))
    same = all(b.frames()[d][0] == m.frames()[d][m.times.index(AT.LEAP_CONTACT)] for d in rig.DIRS)
    check(f'{b.sheet}: its first pose is the leap\'s frame {AT.LEAP_CONTACT} (landed, the fist on the ground)', same)


def leap_below(m, d):
    """How far below the foot line a row may draw the body: checks_attack.feet_below (the feet; the side views keep the
    rule's 2 px at most) - and the right fist on the ground (landed, the blow), as a foot that far towards the camera:
    from the front DEPTH of its distance ahead, from the side DEPTH of its distance out towards the camera (the
    sidestep's rule, checks.STRAFE_FOOT), +1 for its own rounding."""
    base = CA.feet_below(m, d)
    worst = 0.0
    for s in m.states:
        f = s['fist']
        if f[2] > FIST_Z[1] + 2.0:
            continue
        drop = {'down': f[0], 'up': -f[0], 'right': f[1], 'left': -f[1]}[d]
        worst = max(worst, A.DEPTH * drop + FIST_TOUCH[1])
    return max(base, math.ceil(worst) + 1)


OTHERS = CU.OTHERS + (('上挑的蓄力', AT.quick3, AT.QUICK3_LOW[1]),)


def distinct_checks(m, at=37):
    i = max(j for j, t in enumerate(m.times) if t <= at)
    for label, fn, t in OTHERS:
        clip = fn()
        sts = AT.poses(clip, [t - 1, t])
        vals = [C.sil_change(m.frames()[d][i], AA.render_pose(d, sts[1], sts[0])) for d in rig.DIRS]
        check(f'{m.sheet}: the crouch reads apart from {label} (outline {CA.DISTINCT:.0%}+ different, each view)',
              min(vals) >= CA.DISTINCT, ' '.join(f'{v:.0%}' for v in vals))


def main():
    CA._sync()
    m, b = EL.moves()
    game_checks(m, b)
    sts = [m.clip.at(t) for t in range(m.total)]
    model_checks(m, sts, KNEEL_SPAN)
    elbow_checks(m, sts)
    elbow_checks(b, [b.clip.at(t) for t in range(b.total)])
    back_checks(m, sts)
    feet_checks(m, sts)
    height_checks(m, sts)
    CU.flat_checks(m, 0)
    bounce_checks(m, b)
    distinct_checks(m)
    for mv in (m, b):
        CA.frame_checks(mv, below=leap_below)
        hands_checks(mv)
        CC.canvas_checks(mv)
    blow_checks(m, sts)
    CA.entry_feet_checks(m)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: the sword kept in the hand (never slung); the hand grabbing it from
    somewhere else (a jump); a foot left on the ground in the air; a hop instead of a leap (30 px); the fist stopping
    short of the ground; the fist pushed into the ground; the timing off the game's (landing at 84); both feet stepping
    together on the ground; the legs stretched longer than they are in the air; the elbows pointing down in the crouch
    (as first drawn: swung back, the forearms folded back the wrong way)."""
    CA._sync()
    caught = []
    m, b = EL.moves()

    def variant(edit, back=AT.LEAP_BACK, steps_edit=None):
        keys = [(t, dict(k)) for t, k in m.clip.keys]
        for t, k in keys:
            edit(t, k)
        # the leap's feet are all in its keys (a key a frame through the air): an edit to them is the track; extra
        # steps only where a case adds them (passing the clip's own tracks back would put the edited feet back)
        tracks = {'R': [], 'L': []}
        if steps_edit:
            tracks = {s_: list(v) for s_, v in m.clip.tracks.items()}
            steps_edit(tracks)
        cl = AT.Clip('leap_bad', keys, tracks, back=back, musts=m.clip.musts, lead=False, still=True)
        return [cl.at(t) for t in range(m.total)]

    def run(fn):
        results.clear()
        fn()
        return results.count(False) >= 1
    sts = variant(lambda t, k: None, back=None)
    caught.append(run(lambda: back_checks(m, sts)))
    sts = variant(lambda t, k: k.update(fist=(k['fist'][0] + 20.0,) + k['fist'][1:]) if t == AT.LEAP_BACK[1] else None)
    caught.append(run(lambda: back_checks(m, sts)))
    sts = variant(lambda t, k: k['feet'].update(L=(k['feet']['L'][0], k['feet']['L'][1], AT.gait.ANKLE_H, 0.0))
                  if AT.LEAP_UP + 10 <= t <= AT.LEAP_UP + 20 else None)
    caught.append(run(lambda: feet_checks(m, sts)))
    sts = variant(lambda t, k: k.update(lift=k.get('lift', 0.0) / 3.0))
    caught.append(run(lambda: height_checks(m, sts)))
    sts = variant(lambda t, k: k.update(fist=k['fist'][:2] + (k['fist'][2] + 12.0,)) if AT.LEAP_SMASH[0] <= t <= AT.LEAP_SMASH[1] else None)
    caught.append(run(lambda: blow_checks(m, sts)))
    sts = variant(lambda t, k: k.update(fist=k['fist'][:2] + (k['fist'][2] - 5.0,)) if AT.LEAP_SMASH[0] <= t <= AT.LEAP_SMASH[1] else None)
    caught.append(run(lambda: blow_checks(m, sts)))

    class Fake:
        pass
    f = Fake()
    f.__dict__.update(m.__dict__)
    f.hits = [(84, 6)]
    caught.append(run(lambda: game_checks(f, b)))

    def both(tr):
        tr['R'] = sorted(tr['R'] + [(20, AT.STAND), (28, (10.0, 0.0, AT.gait.ANKLE_H, 0.0))])
        tr['L'] = sorted(tr['L'] + [(20, AT.STAND), (28, (10.0, 0.0, AT.gait.ANKLE_H, 0.0))])
    sts = variant(lambda t, k: None, steps_edit=both)
    caught.append(run(lambda: feet_checks(m, sts)))
    sts = variant(lambda t, k: k['feet'].update(R=(k['feet']['R'][0], 0.0, k['feet']['R'][2] - 30.0, k['feet']['R'][3]))
                  if AT.LEAP_UP + 8 <= t <= AT.LEAP_UP + 30 else None)
    caught.append(run(lambda: model_checks(m, sts, KNEEL_SPAN)))
    sts = variant(lambda t, k: k.update(poleR=(-0.2, 0.8, -1.0), poleL=(-0.2, -0.8, -1.0))
                  if AT.LEAP_CROUCH[0] <= t <= AT.LEAP_CROUCH[1] else None)
    caught.append(run(lambda: elbow_checks(m, sts)))
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
