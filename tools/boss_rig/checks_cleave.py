"""Automatic checks for the oath cleave (墜誓下劈, attacks.cleave, export_cleave.py); exit code 1 on
any failure.

    python3 tools/boss_rig/checks_cleave.py [--selftest]

The attack checks (checks_attack: the finished frames, the hands, starting from a move; for the
triple slash's twin-slash part also its sweeps, feet and the game's step) run on these clips too.
What is new for a cut straight down that ends in the ground (boss-veltharis §4.3, §4.6, §5):
  - the game's numbers (veltharis_data.gd: the windups, hit boxes, rings, recoveries, the highest
    point and the delayed hold, the line's length) are the ones the art is drawn to
  - the 3D model at every combat frame: the arms reach, the blade misses the body, the legs
  - the cleave (and the triple slash's third hit): while the hit box is on the blade is in the line
    in front of him (straight ahead, within the line's width), coming down; at the contact the tip
    is at the line's far end (165) at the player's height (checks_attack.PLAYER_HEIGHT)
  - into the ground only once the hit box is on (the ash impact: on each ring's first frame, the
    frame before above it, PLANT_NEAR ahead of him), at most BITE_MAX deep; once in it stays
    (animation-review §4.3: where it goes in moves at most SLOT_MAX while it bites, not at all while
    stuck) and comes out along its own line
  - nothing of the blade drawn more than CUT_BELOW below the foot line in the side views
  - the windup is the upper body's, the right foot steps in and lands with the blow, the weight
    goes onto it (checks_attack's standards)
  - the highest point (the delayed version holds it) is a pose of its own, stopped, the fists at
    their highest; its outline differs from the sweeps' windup (attacks.c1, frame 40) by
    checks_attack.DISTINCT in every view (read apart before they strike)
  - over the head (user 2026-10-03): at the highest point both fists over the helmet's crown and
    within the head's width, the blade back over it; the edges front and back from the highest
    point until the blade is out of the ground (the flats to his sides: a thin line from the front
    and the back), the flat never flashing round between two poses; the arms drawn longer only
    over the head (attack3d.arm_lengths), growing slowly, their own length from each blow on
  - the ash impact (user 2026-10-03, the plunge): standing (the feet never move, no crouch, no bending
    over), the hands over his head held still through the game's danger time (the charge), the
    helmet's cross flashing once as it begins (drawn lit in the front view); the double impact's
    second ring: the sword left in the ground, his weight thrown down onto it
  - shared poses are the same pixels: the impacts' openings and the cleave's (one set of entry
    sheets), the triple slash's and the twin slash's / the cleave's (one bounce sheet)
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
import export_cleave as EC
import export_attack as E

results = CA.results
check = C.check
BITE_MAX = 12.0       # px: the tip's depth in the ground
SLOT_MAX = 10.0       # px: where the blade enters the ground moves this far while it bites in (it cuts a slot)
PULL_TURN = 2.0       # degrees: pulled out along its own line
LINE_TURN = 10.0      # degrees off straight ahead while the hit box is on


def game_numbers():
    """The oath cleave as veltharis_data.gd has it."""
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    f = re.search(r'static func _cleave_hit.*?\n\n', src, re.S).group(0)
    num = lambda pat: float(re.search(pat, f).group(1))
    build = re.search(r'out\[&"oath_cleave"\] = _move\(&"oath_cleave", "[^"]*", \[_cleave_hit\(([0-9.]+), false\)\], '
                      r'([0-9.]+) \* rec', src)
    return {'interval': float(build.group(1)), 'recovery': float(build.group(2)),
            'active': num(r'"active": ([0-9.]+)'), 'delay_hold': num(r'"delay_hold": ([0-9.]+) if delayed'),
            'hold_start': num(r'"hold_start": ([0-9.]+) if delayed'),
            'length': get('CLEAVE_LENGTH'), 'width': get('CLEAVE_WIDTH'), 'phase2': get('PHASE2_RECOVERY_SCALE')}


def game_checks(m):
    g = game_numbers()
    fr = lambda s: round(s * 60)
    ok = (fr(g['interval']) == AT.CLEAVE_W and m.hits[0] == (AT.CLEAVE_W, fr(g['active']))
          and m.total == AT.CLEAVE_W + fr(g['active']) + fr(g['recovery'])
          and fr(g['hold_start']) == AT.CLEAVE_TOP and fr(g['delay_hold']) == AT.CLEAVE_HOLD
          and sum(m.holds_p2) - sum(m.holds) == round(fr(g['recovery']) * g['phase2']) - fr(g['recovery']))
    check(f'{m.sheet}: the game\'s timing (veltharis_data) is the art\'s', ok,
          f'windup {g["interval"]} s, hit {g["active"]} s, recovery {g["recovery"]} s (phase 2 x{g["phase2"]}), '
          f'highest at {g["hold_start"]} s held {g["delay_hold"]} s / art {AT.CLEAVE_W}, {m.hits[0]}, {m.total}, '
          f'{AT.CLEAVE_TOP}, {AT.CLEAVE_HOLD}')
    check(f'{m.sheet}: the game\'s line (veltharis_data CLEAVE_LENGTH) is the art\'s (export_size.RANGES chop)',
          g['length'] == REACH, f'{g["length"]:.0f} x {g["width"]:.0f} / {REACH:.0f}')
    return g


REACH = CA.export_size.RANGES['chop']     # 165: the cleave's line (and the spin's radius)


def body_checks(m):
    """The 3D numbers at every combat frame: the arms reach, the blade misses the body, the legs."""
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
        wl, low, kh = CA.leg_ok(st)
        worst_leg, worst_low = max(worst_leg, wl), min(worst_low, low)
        if kh:
            legs.append(t)
    check(f'model {m.sheet}: both fists within the arms\' reach at every frame', not reach_bad, ', '.join(reach_bad[:6]))
    check(f'model {m.sheet}: the blade never passes through the body, the shoulder plates or the helmet',
          not hits, ', '.join(hits[:6]))
    check(f'model {m.sheet}: no leg reaches further than it is long', worst_leg <= 1.0 + 1e-6, f'longest {worst_leg:.3f}')
    check(f'model {m.sheet}: no boot goes into the ground', worst_low >= -0.6, f'lowest {worst_low:+.2f} px')
    check(f'model {m.sheet}: no knee as high as the hip', not legs, str(legs[:6]))
    return sts


def _entry(s):
    """Where the blade's line meets the ground (F, R)."""
    f, ax = s['fist'], s['axis']
    t0 = f[2] / -ax[2]
    return (f[0] + ax[0] * t0, f[1] + ax[1] * t0)


def ground_spans(sts):
    """[(first, last)] frames the tip is in the ground."""
    out, start = [], None
    for t, s in enumerate(sts):
        under = A.tip(s)[2] < 0.0
        if under and start is None:
            start = t
        if not under and start is not None:
            out.append((start, t - 1))
            start = None
    if start is not None:
        out.append((start, len(sts) - 1))
    return out


def stays(m, sts, span, still, label):
    """In the ground the sword stays: where it goes in moves at most SLOT_MAX while it bites, not at
    all over `still` (frames), and it comes out along its own line."""
    first, last = span
    ents = [_entry(sts[t]) for t in range(first, last + 1)]
    slot = max(math.dist(ents[0], e) for e in ents)
    a, b = still
    held = max(math.dist(_entry(sts[a]), _entry(sts[t])) for t in range(a, b + 1))
    turn = max(math.degrees(math.acos(max(-1.0, min(1.0, A.dot(sts[b]['axis'], sts[t]['axis']))))) for t in range(b, last + 1))
    pulled = max(math.dist(_entry(sts[b]), _entry(sts[t])) for t in range(b, last + 1))
    deep = max(-A.tip(sts[t])[2] for t in range(first, last + 1))
    check(f'model {m.sheet}: {label}: at most {BITE_MAX:.0f} px deep; in the ground the sword stays (where it goes in moves '
          f'at most {SLOT_MAX:.0f} px while it bites, not at all over frames {a}..{b}) and comes out along its line (at most '
          f'{PULL_TURN:.0f} degrees)', deep <= BITE_MAX and slot <= SLOT_MAX and held < 0.3 and turn <= PULL_TURN and pulled < 1.0,
          f'{deep:.1f} px deep, slot {slot:.1f} px, still {held:.2f} px, pulling out {turn:.1f} degrees / {pulled:.2f} px')
    return ents[-1]


def line_checks(m, sts, hit, contact, still, width=None):
    """The cleave's hit: while the hit box is on the blade is in the line ahead (straight, within
    its width) and coming down; at the contact the tip is at the line's far end at the player's
    height; it goes into the ground once the hit box is on (and nowhere else) and stays there."""
    width = width or game_numbers()['width']
    start, n = hit
    psis = [A.angles(sts[t]['axis'])[0] for t in range(start, start + n)]
    side = max(abs(p[1]) for t in range(start, start + n) for p in (sts[t]['fist'], A.tip(sts[t])))
    zs = [A.tip(sts[t])[2] for t in range(start, start + n)]
    check(f'model {m.sheet}: hit {start}: while the hit box is on the blade is in the line ahead (within {LINE_TURN:.0f} '
          f'degrees, {width / 2:.1f} px either side) and coming down', max(abs(p) for p in psis) <= LINE_TURN
          and side <= width / 2 and all(b < a for a, b in zip(zs, zs[1:])),
          'azimuths ' + ' '.join(f'{p:.0f}' for p in psis) + f'; {side:.1f} px off the line; tip ' + ' '.join(f'{z:.0f}' for z in zs))
    tp = A.tip(sts[contact])
    check(f'model {m.sheet}: hit {start}: at the contact (frame {contact}) the tip is at the line\'s far end ({REACH:.0f} px) '
          f'at the player\'s height ({CA.PLAYER_HEIGHT:.0f} px)', tp[0] >= REACH and 0 < tp[2] <= CA.PLAYER_HEIGHT,
          f'{tp[0]:.0f} px out, {tp[2]:.0f} px up')
    spans = ground_spans(sts)
    check(f'model {m.sheet}: the blade goes into the ground once, after hit {start} comes on', len(spans) == 1
          and spans[0][0] >= start, f'in the ground {spans}')
    if len(spans) == 1:
        stays(m, sts, spans[0], still, f'hit {start}')


PLANT_NEAR = (35.0, 90.0)     # px ahead: the ash impact's plunged blade goes in near him (the ring is centred on him)


def plant_checks(m, sts, rings, stills):
    """The ash impact: the blade goes into the ground exactly as each ring starts (above it the frame
    before), PLANT_NEAR ahead of him, and stays (stays())."""
    spans = ground_spans(sts)
    check(f'model {m.sheet}: the blade is in the ground from each ring\'s first frame (above it the frame before), '
          f'and only then', [a for a, _ in spans] == [r for r, _ in rings], f'in the ground {spans}, rings at {[r for r, _ in rings]}')
    for (r, _), sp, still in zip(rings, spans, stills):
        e = stays(m, sts, sp, still, f'ring {r}')
        check(f'model {m.sheet}: ring {r}: the blade goes in {PLANT_NEAR[0]:.0f}..{PLANT_NEAR[1]:.0f} px ahead of him, in line',
              PLANT_NEAR[0] <= e[0] <= PLANT_NEAR[1] and abs(e[1]) < 3, f'{e[0]:.0f} px ahead, {e[1]:+.1f} px aside')


def feet_checks(m, sts, contacts, windup=True):
    """The windup is the upper body's; at each contact the right foot has stepped in and lands with
    it; the weight goes onto it, the chest over it (checks_attack's standards)."""
    both = [t for t in range(1, m.total) if len(CA.moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {m.sheet}: one foot at a time', not both, str(both[:8]))
    hx_jump = max(abs(CA.hips_at(b) - CA.hips_at(a)) for a, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a['D']) for a, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump (at most {CA.HIP_STEP_X} px forward/back, {CA.HIP_STEP_D} px a frame)',
          hx_jump <= CA.HIP_STEP_X and d_jump <= CA.HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    runs = {k: CA.runs(sts, k) for k in 'RL'}
    print('     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in runs[k]) for k in 'RL'))
    if windup:
        first = contacts[0] - 3 - CA.STEP_LEAD
        wind = sts[:first]
        planted = all(CA.foot_at(s, k)[0] == (0.0, 0.0, 0.0) and not CA.foot_at(s, k)[1] for s in wind for k in 'RL')
        hx_w = max(abs(CA.hips_at(s)) for s in wind)
        d_w = max(s['D'] for s in wind)
        check(f'feet {m.sheet}: the windup is the upper body\'s (feet planted, hips within {CA.WINDUP_HX} px and '
              f'{CA.WINDUP_D} px down until frame {first})', planted and hx_w <= CA.WINDUP_HX and d_w <= CA.WINDUP_D,
              f'feet {"planted" if planted else "MOVED"}, hips {hx_w:.1f} px, {d_w} px down')
    for mid in contacts:
        r = [r_ for r_ in runs['R'] if r_[0] <= mid + 1 and r_[1] >= mid - 12]
        if not r:
            check(f'feet {m.sheet}: the blow at {mid} steps the right foot', False, 'no step')
            continue
        a, b = r[0]
        fwd = CA.foot_at(sts[b], 'R')[0][0] - CA.foot_at(sts[a - 1], 'R')[0][0]
        lefts = [r_ for r_ in runs['L'] if r_[1] >= a and r_[0] <= mid + 20]
        check(f'feet {m.sheet}: the blow at {mid} steps the right foot {CA.STEP_MIN:.0f}+ px forward, landing with it '
              f'(+-{CA.LAND_SLACK}); the left foot still', abs(b - mid) <= CA.LAND_SLACK and fwd >= CA.STEP_MIN and not lefts,
              f'off the ground {a}..{b - 1}, lands {b}, {fwd:.0f} px forward; the left foot ' + (str(lefts) if lefts else 'still'))
        st = sts[mid]
        front, back_ = CA.foot_at(st, 'R')[0][0], CA.foot_at(st, 'L')[0][0]
        share = (CA.hips_at(st) - back_) / max(1e-6, front - back_)
        check(f'feet {m.sheet}: at the blow at {mid} the weight is on the front foot ({CA.WEIGHT_FWD:.0%}+), the chest '
              f'leaning {CA.LEAN_MIN:.0f}+', share >= CA.WEIGHT_FWD and st['lx'] >= CA.LEAN_MIN,
              f'hips {share:.0%}, lean {st["lx"]:.0f}')


def top_checks(m, top=AT.CLEAVE_TOP, hit=AT.CLEAVE_W, compare=True):
    """The highest point: a pose of its own (the delayed version holds it), the pose has stopped
    there (from four frames before), the fists at their highest; read apart from the sweeps' windup."""
    clip = m.clip
    a, b = clip.at(top - 4), clip.at(top)
    still = (math.dist(a['fist'], b['fist']) < 0.05 and A.dot(a['axis'], b['axis']) > 0.99999
             and all(abs(a[k] - b[k]) < 0.05 for k in ('D', 'hx', 'lx', 'tw', 'bow')))
    # the raise's highest: the fists (second version: over the head, the blade laid back over it -
    # on the way up and on the way down it passes upright, its tip higher than at the highest point)
    hi = max(clip.at(x)['fist'][2] for x in range(top - 30, hit))
    check(f'{m.sheet}: the highest point (frame {top}, held by the delayed version) is a pose of its own, still from frame '
          f'{top - 4}, the fists at their highest', top in m.times and still and b['fist'][2] >= hi - 0.5,
          f'right fist {b["fist"][2]:.0f} px up (highest {hi:.0f})')
    if not compare:
        return
    c1 = E.Move('boss_c1', AT.c1(), 111, [(48, 9)], 'c1')
    i, j = m.times.index(top), c1.times.index(max(x for x in c1.times if x <= 40))
    for d in rig.DIRS:
        v = C.sil_change(m.frames()[d][i], c1.frames()[d][j])
        check(f'{m.sheet} {d}: the highest point reads apart from the sweeps\' windup (outline {CA.DISTINCT:.0%}+ different)',
              v >= CA.DISTINCT, f'{v:.0%}')


CROWN = A.SH_U + 48.0          # the helmet with its crown, standing (attack3d.body_hits' head column)
OVER_MARGIN = 2.0              # px: the fist centres this far over it at the least
EDGE_OFF = 0.14                # the blade's width at most this far out of its own vertical plane (sin 8 degrees)
TURN_STEP = 35.0               # degrees: the flat turns at most this much from one pose to the next (no flash)
ARM_K_MAX = 1.5                # the arms over the head drawn at most this many times as long
ARM_GROW_PX = 3.0              # ... the whole arm (shoulder to fist) growing or shrinking at most this much a
ARM_K_STEP = ARM_GROW_PX / (A.UPPER + A.FORE)      # frame (a fifth of a fist's step, checks.STEP_MAX 16): 0.10


def over_head_checks(m, top):
    """User 2026-10-03: "the cleave is raised over the head". At the highest point both fists are
    over the helmet's crown (OVER_MARGIN px clear) and over the head (within its width either side),
    the blade back over him (the 3D model: it misses the helmet)."""
    s = m.clip.at(top)
    ar = A.arms(s)
    crown = CROWN - s['D']
    fz = [ar[k][2][2] for k in 'RL']
    side = max(abs(ar[k][2][1]) for k in 'RL')
    back = A.tip(s)[0] < s['fist'][0]
    check(f'{m.sheet}: at the highest point (frame {top}) both fists are over the head ({crown + OVER_MARGIN:.0f}+ px up, '
          f'within {A.HEAD_R:.0f} px either side), the blade back over it',
          min(fz) >= crown + OVER_MARGIN and side <= A.HEAD_R and back and not A.body_hits(s),
          f'fists {fz[0]:.0f} / {fz[1]:.0f} px up, {side:.1f} px aside, tip {A.tip(s)[0] - s["fist"][0]:+.0f} px forward of them')


HELMET = A.SH_U + 36.0         # the helmet's dome (the crown's spikes stand on it up to CROWN)
PLUNGE_DOWN = 55.0             # degrees: the plunge's blade at least this far below level at the highest point


def plunge_top_checks(m, top):
    """User 2026-10-03: the ash impact plunges the sword "tip-down, but the hands raised over the
    head as well to charge". At the highest point the upper (right, by the pommel) fist is over the
    crown, the lower (left, by the guard) over the helmet's dome, both within the head's width either
    side; the blade points down (PLUNGE_DOWN+ below level) in front of him and misses the helmet."""
    s = m.clip.at(top)
    ar = A.arms(s)
    fz = [ar[k][2][2] + s['D'] for k in 'RL']
    side = max(abs(ar[k][2][1]) for k in 'RL')
    down = -A.angles(s['axis'])[1]
    check(f'{m.sheet}: at the highest point (frame {top}) the hands are over the head (the upper fist {CROWN + OVER_MARGIN:.0f}+ '
          f'px up, the lower {HELMET + OVER_MARGIN:.0f}+, within {A.HEAD_R:.0f} px either side), the blade tip-down in front',
          fz[0] >= CROWN + OVER_MARGIN and fz[1] >= HELMET + OVER_MARGIN and side <= A.HEAD_R and down >= PLUNGE_DOWN
          and A.tip(s)[0] > s['fist'][0] and not A.body_hits(s),
          f'fists {fz[0]:.0f} / {fz[1]:.0f} px up, {side:.1f} px aside, the blade {down:.0f} degrees down, '
          f'tip {A.tip(s)[0] - s["fist"][0]:+.0f} px forward of the fists')


STAND_D, STAND_LEAN = 3, 3.0  # px / degrees: the plunge standing (no crouch, no bending over)


def plunge_body_checks(m, sts, rings):
    """User 2026-10-03: "右腳不用往前踏，也不用彎腰，單純手舉過頭頂把劍插下去就好". The feet never move, the
    hips stay over them, and at each plunge he is standing (at most STAND_D down, leaning at most
    STAND_LEAN forward)."""
    moved = [t for t, s in enumerate(sts) for k in 'RL'
             if CA.foot_at(s, k)[0] != (0.0, 0.0, 0.0) or CA.foot_at(s, k)[1]]
    hx = max(abs(CA.hips_at(s)) for s in sts)
    check(f'feet {m.sheet}: the feet never move (no step), the hips over them', not moved and hx <= CA.WINDUP_HX,
          f'moved at {moved[:6]}, hips {hx:.1f} px')
    for r, _ in rings:
        s = sts[r]
        check(f'feet {m.sheet}: at the plunge (frame {r}) he stands (at most {STAND_D} px down, leaning at most '
              f'{STAND_LEAN:.0f} degrees)', s['D'] <= STAND_D and s['lx'] <= STAND_LEAN, f'{s["D"]} px down, lean {s["lx"]:.1f}')


def danger_time():
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    ring = re.search(r'static func _impact_ring.*?\n\n', src, re.S).group(0)
    return round(float(re.search(r'"danger_time": ([0-9.]+)', ring).group(1)) * 60)


def charge_checks(m, sts, rings, tops):
    """User 2026-10-03: the charge is the game's danger time (veltharis_data danger_time, the last
    0.6 s before each ring), and the helmet's cross flashes once as it begins - the warning, "像絕區
    零的怪在攻擊前會閃的那種光", fading in and out ("閃光需要有淡入和淡出", attacks.FLASH_CURVE). Through the
    charge before a plunge the hands are held over his head (tops: the frame he holds from), before
    the double impact's second ring the sword stays in the ground under his hands (None). Drawn: the
    front view at the flash against the same pose unlit."""
    dt = danger_time()
    for (r, _), top in zip(rings, tops):
        a = r - dt
        g = [sts[t]['glow'] for t in range(m.total)]
        lo, hi = a + AT.FLASH_SPAN[0], a + AT.FLASH_SPAN[1]
        rise = all(g[t] <= g[t + 1] + 1e-9 for t in range(lo, a))
        fall = all(g[t] >= g[t + 1] - 1e-9 for t in range(a, hi))
        steps_in = len({round(g[t], 2) for t in range(lo, a + 1)})
        check(f'{m.sheet}: ring {r}: the cross flashes, brightest as the danger time begins (frame {a}), fading in over '
              f'{-AT.FLASH_SPAN[0]} frames and out over {AT.FLASH_SPAN[1]} (no jump: brightness rising then falling, '
              f'3+ steps in), dark outside it and at the ring',
              g[a] >= 0.999 and rise and fall and steps_in >= 3 and g[lo] == 0.0 and g[hi] == 0.0
              and all(v == 0.0 for v in g[hi:r + 1]), f'brightness {[round(g[t], 2) for t in range(lo, hi + 1, 2)]}')
        if top is not None:
            held = max(math.dist(sts[a]['fist'], sts[t]['fist']) for t in range(a, r - AT.PLUNGE + 1))
            check(f'{m.sheet}: ring {r}: through the charge ({a}..{r - AT.PLUNGE}) the hands are held over his head',
                  top == a and held < 0.05, f'over his head from {top}, moving {held:.2f} px')
    lit = [t for t in range(m.total) if sts[t]['glow'] >= AA.GLOW_HALF]
    flashes = [t for t in lit if t - 1 not in lit]
    check(f'{m.sheet}: the cross flashes once for each ring and is dark otherwise', len(flashes) == len(rings),
          f'flashes start at {flashes}')
    a = rings[0][0] - dt
    i = m.times.index(a)
    lit_f = m.frames()['down'][i]
    dark_f = AA.render_pose('down', dict(m.states[i], glow=0.0), m.states[i - 1])
    n = sum(1 for q, c in lit_f.items() if dark_f.get(q) != c)
    check(f'{m.sheet}: the cross is drawn lit at the flash (front view, against the same pose unlit)', n >= 8,
          f'{n} px brighter')


PRESS_D, PRESS_LEAN = 6, 8.0  # the double impact's second ring: the hips this far down, the chest leaning over the hilt


def press_checks(m, sts, r):
    """User 2026-10-03: the double impact's second ring - "全身用力往下壓一下就好，不用把劍拔出來": as it
    goes out his whole weight is thrown down onto the hilt (the hips dropped PRESS_D+, the chest over
    it PRESS_LEAN+) while the sword stays in the ground, not moved (stays()), drawn up just before."""
    s, up = sts[r], sts[AT.PRESS[1]]
    check(f'{m.sheet}: at the second ring (frame {r}) he throws his weight down onto the planted sword (hips {PRESS_D}+ px '
          f'down, leaning {PRESS_LEAN:.0f}+), from drawn up just before', s['D'] >= PRESS_D and s['lx'] >= PRESS_LEAN
          and up['D'] < s['D'] - 4 and up['lx'] < s['lx'] - 8, f'{s["D"]} px down, lean {s["lx"]:.0f} (before: {up["D"]} px, '
          f'{up["lx"]:.0f})')


def edge_checks(m, a, b, label='', turn_from=0):
    """User 2026-10-03: "the edges face front and back - from the side the whole blade, from the
    front and the back only a thin line". From the highest point (a) until it is out of the ground
    (b) the blade's width is in its own vertical plane (the edges front and back, the flats to his
    left and right) in every pose; and nowhere in the move does the flat turn more than TURN_STEP
    from one pose to the next (turning from lying on the shoulder to edge-up without a flash)."""
    off = [(s['t'], abs(s['w3'][1])) for s in m.states if a <= s['t'] <= b]
    worst = max(off, key=lambda x: x[1])
    check(f'{m.sheet}: {label}frames {a}..{b}: the edges face front and back (the width at most {EDGE_OFF:.2f} out of the '
          f'blade\'s vertical plane)', worst[1] <= EDGE_OFF, f'worst {worst[1]:.2f} at frame {worst[0]}')
    turns = []
    sts = [s for s in m.states if s['t'] >= turn_from]
    for p, q in zip(sts, sts[1:]):
        c = abs(A.dot(p['w3'], q['w3']))
        turns.append((q['t'], math.degrees(math.acos(min(1.0, c)))))
    # the flat as seen across the blade: measured against the blade's own turn (a blade swinging
    # round turns its width with it - that is the stroke, not the flat flashing)
    rel = []
    for (p, q), (t, deg) in zip(zip(sts, sts[1:]), turns):
        ax = math.degrees(math.acos(max(-1.0, min(1.0, A.dot(p['axis'], q['axis'])))))
        rel.append((t, max(0.0, deg - ax)))
    w = max(rel, key=lambda x: x[1])
    check(f'{m.sheet}: {label}the flat never turns more than {TURN_STEP:.0f} degrees between two poses (beyond the '
          f'blade\'s own swing) from frame {turn_from}', w[1] <= TURN_STEP, f'worst {w[1]:.0f} degrees at frame {w[0]}')


def arm_k_checks(m, contacts):
    """The arms over the head are drawn longer (attack3d.arm_lengths): at most ARM_K_MAX, growing
    and shrinking by at most ARM_K_STEP a frame, their own length from each contact on (the blow,
    the blade in the ground, the recovery) and at the start and the end."""
    ks = [m.clip.at(t).get('arm_k', 1.0) for t in range(m.total)]
    step = max(abs(b - a) for a, b in zip(ks, ks[1:]))
    after = [t for t in range(m.total) if (t in contacts or t >= contacts[-1]) and abs(ks[t] - 1.0) > 1e-6]
    check(f'{m.sheet}: the arms are drawn longer only over the head (at most x{ARM_K_MAX}, {ARM_GROW_PX:.0f} px a frame; their '
          f'own length at each blow and after it, at the start and the end)',
          max(ks) <= ARM_K_MAX + 1e-6 and step <= ARM_K_STEP and not after and ks[0] == 1.0 and ks[-1] == 1.0,
          f'longest x{max(ks):.2f}, {step:.3f} a frame; longer after a blow at {after[:6]}')


def same_frames(label, a, b, n=None, pairs=None):
    """Poses drawn the same: a's first n with b's (the shared openings), or (i, j) pairs."""
    pairs = pairs or [(i, i) for i in range(n)]
    ok = all(a.frames()[d][i] == b.frames()[d][j] for d in rig.DIRS for i, j in pairs)
    check(label, ok and all(a.times[i] - a.times[pairs[0][0]] == b.times[j] - b.times[pairs[0][1]] for i, j in pairs),
          f'{[(a.times[i], b.times[j]) for i, j in pairs][:3]}...')


CUT_BELOW = math.ceil(A.DEPTH * CA.BLADE_HALF)     # 3 px: the blade's edge towards the camera drawn that much lower


def ground_frame_checks(m, every=False):
    """The side views draw the blade cut at the ground: nothing of it more than CUT_BELOW below the
    foot line (the edge of a blade turned towards the camera is drawn lower by the depth,
    animation-review §4.4; uncut, the tip 5 px in the ground shows 7+ px below)."""
    worst = -99
    for d in ('right', 'left'):
        for s in m.states:
            if not (s.get('ground') or every):
                continue          # the triple slash's twin-slash part: a blade low towards the camera, drawn lower
            sw = CA.drawn(d, s['name'], s['i'])[0]
            if sw:
                worst = max(worst, max(q[1] for q in sw) - rig.AY)
    # (measuring no blade at all is a broken check, not a pass: animation-review §5)
    check(f'{m.sheet}: the blade is cut at the ground (side views: at most {CUT_BELOW} px of it below the foot line)',
          -99 < worst <= CUT_BELOW, f'lowest {worst:+d} px')


def canvas_checks(m):
    """The whole sword is drawn: none of it reaches the edge of the canvas it is drawn on (the cell).
    The first version's cell (the attack container, 272 rows above the feet) cut off the tip of the
    blade raised over his head in the front and back views, and the cell check could not see it - the
    sword is drawn only within the canvas."""
    worst = []
    for s in m.states:
        size, org = AA.sword_canvas(s)
        for d in rig.DIRS:
            sw = AA.SWORD.get((d, s['name'], s['i']))
            if not sw or not sw[0]:
                continue
            xs = [q[0] for q in sw[0]]
            ys = [q[1] for q in sw[0]]
            gap = min(min(xs) - org[0], org[0] + size[0] - 1 - max(xs), min(ys) - org[1], org[1] + size[1] - 1 - max(ys))
            worst.append((gap, s['t'], d))
    w = min(worst)
    check(f'{m.sheet}: the whole sword is inside its cell (never touching the edge)', w[0] >= 1,
          f'closest {w[0]} px from the edge (frame {w[1]}, {w[2]})')


def game_more(ms):
    """The ash impact, the double impact and the triple slash as veltharis_data.gd has them."""
    c, b, im, db, tr = ms
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    ring = re.search(r'static func _impact_ring.*?\n\n', src, re.S).group(0)
    active = round(float(re.search(r'"active": ([0-9.]+)', ring).group(1)) * 60)
    one = re.search(r'out\[&"ash_impact"\] = _move\([^\[]*\[_impact_ring\(([0-9.]+)\)\], ([0-9.]+)', src)
    two = re.search(r'out\[&"double_impact"\] = _move\([^\[]*\[_impact_ring\(([0-9.]+)\), _impact_ring\(([0-9.]+)\)\],\s*'
                    r'([0-9.]+) \* rec', src)
    trip = re.search(r'out\[&"triple_slash"\] = _move\([^\[]*\[_twin_first\(\), _twin_second\(false\),\s*_cleave_hit\(([0-9.]+), '
                     r'false\)\], ([0-9.]+) \* rec', src)
    p2 = game_numbers()['phase2']
    fr = lambda s: round(float(s) * 60)
    r1 = fr(one.group(1))
    check(f'{im.sheet}: the game\'s timing (veltharis_data ash_impact) is the art\'s',
          im.hits == [(r1, active)] and im.total == r1 + active + fr(one.group(2)),
          f'ring {one.group(1)} s for {active} frames, recovery {one.group(2)} s / art {im.hits}, {im.total}')
    a, bb = fr(two.group(1)), fr(two.group(2))
    check(f'{db.sheet}: the game\'s timing (veltharis_data double_impact, phase 2) is the art\'s',
          db.hits == [(a, active), (a + bb, active)] and db.total == a + bb + active + round(fr(two.group(3)) * p2),
          f'rings {two.group(1)} / {two.group(2)} s, recovery {two.group(3)} s x {p2} / art {db.hits}, {db.total}')
    w3 = AT.W2 + fr(trip.group(1))
    check(f'{tr.sheet}: the game\'s timing (veltharis_data triple_slash, phase 2) is the art\'s',
          tr.hits[2] == (w3, 6) and sum(tr.holds_p2) == w3 + 6 + round(fr(trip.group(2)) * p2),
          f'third hit {trip.group(1)} s after the second, recovery {trip.group(2)} s x {p2} / art {tr.hits[2]}, '
          f'{sum(tr.holds_p2)}')


class Part:
    """A view of a move with fewer hits / frames (the triple slash's twin-slash part for
    checks_attack's sweep checks)."""

    def __init__(self, m, hits, total):
        self.__dict__.update(m.__dict__)
        self.hits, self.total = hits, total


def main():
    CA._sync()
    CA.H.CELL = AA.TALL
    CA.H.CELL_TOP = AA.TALL_TOP
    ms = EC.moves()
    c, b, im, db, tr = ms
    game_checks(c)
    game_more(ms)
    # the cleave
    sts = body_checks(c)
    line_checks(c, sts, c.hits[0], AT.CLEAVE_CONTACT, AT.CLEAVE_STUCK)
    feet_checks(c, sts, [AT.CLEAVE_CONTACT])
    top_checks(c)
    over_head_checks(c, AT.CLEAVE_TOP)
    edge_checks(c, AT.CLEAVE_TOP - 4, 101)
    arm_k_checks(c, [AT.CLEAVE_CONTACT])
    # parried: the blade knocked up before the ground
    sts = body_checks(b)
    check(f'model {b.sheet}: the sword\'s tip never goes into the ground', not ground_spans(sts))
    feet_checks(b, sts, [], windup=False)
    # the ash impact, the double impact
    for m, rings, tops in ((im, [(AT.IMPACT_RING, 12)], [AT.IMPACT_TOP]),
                           (db, [(AT.IMPACT_RING, 12), (AT.IMPACT_RING2, 12)], [AT.IMPACT_TOP, None])):
        sts = body_checks(m)
        pull = AT.IMPACT_PULL if m is im else AT.DOUBLE_PULL2
        # one plunge (the double impact's second ring is the weight thrown onto the sword still in the ground)
        plant_checks(m, sts, rings[:1], [(AT.IMPACT_RING + 2, pull)])
        plunge_body_checks(m, sts, rings[:1])
        charge_checks(m, sts, rings, tops)
        if m is db:
            press_checks(m, sts, AT.IMPACT_RING2)
        top_checks(m, AT.IMPACT_TOP, AT.IMPACT_RING, compare=False)
        plunge_top_checks(m, AT.IMPACT_TOP)
        edge_checks(m, AT.IMPACT_TOP - 4, pull + 6)
        arm_k_checks(m, [r for r, _ in rings])
    same_frames(f'{db.sheet}: its poses up to frame {AT.ENTRY_END} are boss_impact\'s (it starts from a move with '
                f'boss_impact\'s entry sheets)', db, im, n=im.times.index(AT.ENTRY_END) + 1)
    # the triple slash: the twin slash's part as the twin slash; the cleave's part as the cleave
    tw = E.Move('boss_twin', AT.twin(), 168, [(48, 6), (102, 6)], 'twin', entry_times=True)
    part = Part(tr, tr.hits[:2], AT.W2 + 30)
    CA.model_checks(part)
    CA.feet_checks(part)
    CA.advance_checks(tr)
    CA.distinct_checks(tr)
    sts = body_checks(tr)
    line_checks(tr, sts, tr.hits[2], AT.TRIPLE_W3 + 3, (AT.CLEAVE_STUCK[0] + AT.TRIPLE_SHIFT, AT.CLEAVE_STUCK[1] + AT.TRIPLE_SHIFT))
    feet_checks(tr, sts, [AT.TRIPLE_W3 + 3], windup=False)
    top_checks(tr, AT.TRIPLE_TOP, AT.TRIPLE_W3, compare=False)
    over_head_checks(tr, AT.TRIPLE_TOP)
    # (the twin slash's part is boss_twin's, approved: the flat turning as the blade goes up to the
    # left shoulder is 52 degrees between frames 80 and 86 there)
    edge_checks(tr, AT.TRIPLE_TOP - 4, 101 + AT.TRIPLE_SHIFT, turn_from=AT.W2 + 8)
    arm_k_checks(tr, [AT.W, AT.W2, AT.TRIPLE_W3 + 3])
    # the twin slash's poses through the second contact (the last hit frame's blade width reads the
    # next frame, where the two part ways); the cleave's from the pose after the highest point (that
    # one's head and cape lag behind a different pose before it)
    n = tr.times.index(AT.W2 + 4) + 1
    same_frames(f'{tr.sheet}: its poses up to the second hit\'s contact are boss_twin\'s', tr, tw, n=n)
    i, j = tr.times.index(AT.TRIPLE_TOP), c.times.index(AT.CLEAVE_TOP)
    pairs = [(i + k, j + k) for k in range(1, len(c.times) - j)]
    same_frames(f'{tr.sheet}: after the highest point its poses are boss_cleave\'s (the third hit\'s bounce is '
                f'boss_cleave_bounce)', tr, c, pairs=pairs)
    # every move: the finished frames, the hands, starting from a move
    for m in ms:
        CA.entry_feet_checks(m)
        CA.frame_checks(m)
        CA.hands_checks(m)
        canvas_checks(m)
        if m is not b:
            ground_frame_checks(m)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Broken on purpose, each must be caught: the stuck sword drifting, the tip in the ground
    before the hit box, a cut off to the side, a step landing late, a highest point that has not
    stopped, the sweeps' windup as the highest point, the impact's planted blade pushed on, the
    impact planted a frame after the ring, the first version's highest point at the chin, its
    blade canted 45 degrees, the arms left long at the blow, the first version's cell cutting off
    the tip over his head, the blade not cut at the ground, the plunge stepping in and bent over,
    the cross not lit at all, lit all through instead of flashing, the double impact's second ring
    without the weight thrown down."""
    CA._sync()
    caught = []
    m = EC.moves()[0]

    def variant(name, edit, steps=None):
        keys = [(t, dict(k)) for t, k in m.clip.keys]
        for t, k in keys:
            edit(t, k)
        cl = AT.Clip(name, keys, steps or {s_: list(v) for s_, v in m.clip.tracks.items()}, musts=AT.CLEAVE_MUSTS,
                     still=True, ground=True, lead=False)
        return E.Move(m.sheet, cl, m.total, m.hits, m.caption, phase2_recovery=EC.PHASE2_RECOVERY)
    # the stuck sword pushed on (the fist moves while it is in the ground)
    def cut(mv):
        line_checks(mv, [mv.clip.at(t) for t in range(mv.total)], mv.hits[0], AT.CLEAVE_CONTACT, AT.CLEAVE_STUCK)
    drift = variant('cleave_drift', lambda t, k: k.update(fist=(66.0, 0.0, 78.0)) if t == AT.CLEAVE_STUCK[1] else None)
    results.clear()
    cut(drift)
    caught.append(results.count(False) >= 1)
    # the tip in the ground before the hit box (the stroke too low), and a cut off to his right
    low = variant('cleave_low', lambda t, k: k.update(dir=(0.0, -10.0)) if t == 59 else None)
    results.clear()
    cut(low)
    caught.append(results.count(False) >= 1)
    aside = variant('cleave_aside', lambda t, k: k.update(dir=(30.0, -26.0)) if t == AT.CLEAVE_CONTACT else None)
    results.clear()
    cut(aside)
    caught.append(results.count(False) >= 1)
    # the step landing late
    st = {'R': [(AT.CLEAVE_STEP_FROM, AT.STAND), (AT.CLEAVE_CONTACT + 4, AT.RC), (AT.CLEAVE_BACK[0], AT.RC),
                (AT.CLEAVE_BACK[1], AT.STAND)]}

    def late_edit(t, k):
        if AT.CLEAVE_CONTACT <= t < AT.CLEAVE_CONTACT + 4:
            k['feet'] = {'R': None, 'L': AT.STAND}
    late = variant('cleave_late', late_edit, st)
    results.clear()
    feet_checks(late, [late.clip.at(t) for t in range(late.total)], [AT.CLEAVE_CONTACT])
    caught.append(results.count(False) >= 1)
    # still moving at the highest point; the sweeps' windup as the highest point
    moving = variant('cleave_moving', lambda t, k: k.update(fist=(18.0, 9.0, 112.0)) if t == AT.CLEAVE_TOP - 4 else None)
    results.clear()
    top_checks(moving)
    caught.append(results.count(False) >= 1)
    c1 = AT.c1().at(40)

    def as_c1(t, k):
        if AT.CLEAVE_TOP - 14 <= t <= AT.CLEAVE_TOP:
            k.update(fist=c1['fist'], dir=A.angles(c1['axis']), tw=c1['tw'], lx=c1['lx'], flat=AT.FLAT_R)
    sweep = variant('cleave_sweep', as_c1)
    results.clear()
    top_checks(sweep)
    caught.append(results.count(False) >= 2)
    # the ash impact's planted blade pushed on before it is pulled out; planted a frame late
    imv = EC.moves()[2]
    for name, edit in (('impact_drag', lambda t, k: k.update(fist=A.add(k['fist'], (6.0, 0.0, 0.0))) if t == AT.IMPACT_PULL else None),
                       ('impact_late', lambda t, k: k.update(fist=(38.0, 0.0, 109.0), dir=(0.0, -60.0)) if t == AT.IMPACT_RING else None)):
        keys = [(t, dict(k)) for t, k in imv.clip.keys]
        for t, k in keys:
            edit(t, k)
        cl = AT.Clip(name, keys, {s_: list(v) for s_, v in imv.clip.tracks.items()}, musts=AT.IMPACT_MUSTS, still=True,
                     ground=True, lead=False)
        mv = E.Move(imv.sheet, cl, imv.total, imv.hits, imv.caption)
        results.clear()
        plant_checks(mv, [cl.at(t) for t in range(mv.total)], [(AT.IMPACT_RING, 12)], [(AT.IMPACT_RING + 2, AT.IMPACT_PULL)])
        caught.append(results.count(False) >= 1)
    # the plunge's second version (the right foot stepping in, crouched and bent over the sword); the
    # cross not lit through the charge
    steps = {'R': [(AT.IMPACT_RING - 9, AT.STAND), (AT.IMPACT_RING, (30.0, -1.0, AT.gait.ANKLE_H, 0.0))]}

    def bent(t, k):
        if t >= AT.IMPACT_RING - 1:
            k.update(D=15, lx=16)
    for name, edit, tracks, check_fn in (
            ('impact_step', bent, steps, lambda mv, sts: plunge_body_checks(mv, sts, [(AT.IMPACT_RING, 12)])),
            ('impact_dark', lambda t, k: k.update(glow=0.0), None,
             lambda mv, sts: charge_checks(mv, sts, [(AT.IMPACT_RING, 12)], [AT.IMPACT_TOP]))):
        keys = [(t, dict(k)) for t, k in imv.clip.keys]
        for t, k in keys:
            edit(t, k)
        cl = AT.Clip(name, keys, tracks or {s_: list(v) for s_, v in imv.clip.tracks.items()}, musts=AT.IMPACT_MUSTS,
                     still=True, ground=True, lead=False, tall=True)
        mv = E.Move(imv.sheet, cl, imv.total, imv.hits, imv.caption)
        results.clear()
        check_fn(mv, [cl.at(t) for t in range(mv.total)])
        caught.append(results.count(False) >= 1)
    # the cross lit all through the raise and the charge (not a flash); the double impact's second ring
    # without the weight thrown onto the sword (standing over it)
    def always(t, k):
        if 5 <= t <= AT.IMPACT_RING - 2:
            k.update(glow=1.0)
    keys = [(t, dict(k)) for t, k in imv.clip.keys]
    for t, k in keys:
        always(t, k)
    cl = AT.Clip('impact_always', keys, {}, musts=AT.IMPACT_MUSTS, still=True, ground=True, lead=False, tall=True)
    mv = E.Move(imv.sheet, cl, imv.total, imv.hits, imv.caption)
    results.clear()
    charge_checks(mv, [cl.at(t) for t in range(mv.total)], [(AT.IMPACT_RING, 12)], [AT.IMPACT_TOP])
    caught.append(results.count(False) >= 1)
    dbv = EC.moves()[3]
    keys = [(t, dict(k, D=2, lx=2) if t >= AT.IMPACT_RING2 - 2 and t <= AT.IMPACT_RING2 + 14 else k)
            for t, k in dbv.clip.keys]
    cl = AT.Clip('double_stand', keys, {}, musts=AT.DOUBLE_MUSTS, still=True, ground=True, lead=False, tall=True)
    results.clear()
    press_checks(dbv, [cl.at(t) for t in range(dbv.total)], AT.IMPACT_RING2)
    caught.append(results.count(False) >= 1)
    # the first version's highest point (both fists at his chin, the blade upright before him: "only
    # held at the shoulder"), its blade canted 45 degrees (seen wide from the front), arms left long
    # at the blow
    def chin(t, k):
        if AT.CLEAVE_TOP - 4 <= t <= AT.CLEAVE_TOP:
            k.update(fist=(16.0, 10.0, 114.0), dir=(176.0, 86.0), flat=AT.FLAT_R, D=3, lx=-6, tw=-14, arm_k=1.0,
                     shrug=0.0, draw_in=0.0)
    v1 = variant('cleave_chin', chin)
    results.clear()
    over_head_checks(v1, AT.CLEAVE_TOP)
    caught.append(results.count(False) >= 1)
    cant = variant('cleave_cant', lambda t, k: k.update(roll=-45.0) if k.get('roll') == AT.EDGE else None)
    results.clear()
    edge_checks(cant, AT.CLEAVE_TOP - 4, 101)
    caught.append(results.count(False) >= 1)
    long_ = variant('cleave_long', lambda t, k: k.update(arm_k=1.2) if t == AT.CLEAVE_CONTACT else None)
    results.clear()
    arm_k_checks(long_, [AT.CLEAVE_CONTACT])
    caught.append(results.count(False) >= 1)
    # the first version's cell (no rows above the attack container): the tip raised over his head
    # is cut off by the canvas
    keep = AA.TALL, AA.TALL_TOP
    AA.TALL, AA.TALL_TOP = (AA.BIG[0], AA.BIG[1] + AA.TALL_EXTRA), 0
    low_cell = variant('cleave_low_cell', lambda t, k: None)
    low_cell.frames()
    results.clear()
    canvas_checks(low_cell)
    AA.TALL, AA.TALL_TOP = keep
    caught.append(results.count(False) >= 1)
    # the blade not cut at the ground
    uncut = variant('cleave_uncut', lambda t, k: None)
    uncut.clip.ground = False
    uncut.states = AT.poses(uncut.clip, uncut.times)
    for s_ in uncut.states:
        s_['deep'] = True
    uncut.frames()
    results.clear()
    ground_frame_checks(uncut, every=True)
    caught.append(results.count(False) >= 1)
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
