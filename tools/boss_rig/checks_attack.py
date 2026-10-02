"""Automatic checks for the Boss's attacks (attacks.py, anim_attack.py, export_attack.py); exit
code 1 on any failure.

    python3 tools/boss_rig/checks_attack.py [--selftest]

"model" lines check the 3D numbers the poses are built from, at every combat frame of every
clip (the arms can reach the grip, the blade does not pass through the body, the legs, the tip
in the hit box's sector while the hit box is on); the rest is measured on the finished frames
(the sprite sheets' content). --selftest breaks numbers and frames on purpose and shows each
check catches it.
"""
import math
import sys
import boss as B
import rig
import gait
import anim_walk as AW
import anim_kneel as K
import anim_attack as AA
import attacks as AT
import attack3d as A
import export_attack as E
import export_size
import checks as C
import checks_hit as H

STEP_MAX = C.STEP_MAX                 # 16 px: a part may move this much between two poses
TIP_STEP = H.TIP_STEP                 # 80 px: the sword's tip between two poses
SECTOR = 75.0                         # half the sweep's hit box (150 degrees, veltharis_data)
REACH = export_size.RANGES['sweep']   # 155 px: the hit box's radius
results = []
check = C.check


def _sync():
    C.results = results
    H.results = results


# ------------------------------------------------------------------ the 3D numbers
def leg_ok(st):
    """(longest leg as a share of its length, lowest point of a boot (px), knee above the hip)."""
    hip_z = gait.HIP_REST - st['D']
    worst, low, knee_hi = 0.0, 99.0, False
    for k in 'RL':
        x, out, z, pitch, down = st['feet'][k][:5]
        hx = AT.hip_x(st, k)
        n = math.hypot(x - hx, z - hip_z)
        worst = max(worst, n / (gait.THIGH + gait.SHIN))
        L = gait.solve(hip_z, (x - hx, z), pitch, down)
        low = min(low, z - K.boot_drop(pitch))
        if L['knee'][1] > hip_z - 0.1 * (hip_z - z):
            knee_hi = True
    return worst, low, knee_hi


def model_checks(m):
    clip = m.clip
    end = m.total
    reach_bad, hits, legs, tips = [], [], [], []
    worst_leg, worst_low = 0.0, 99.0
    for t in range(end):
        st = clip.at(t)
        for k, a in A.arms(st).items():
            if a and a[3] < -0.5:
                reach_bad.append(f'{t}{k}({a[3]:.1f})')
        h = A.body_hits(st)
        if h:
            hits.append(f'{t}:{h[0][1]}')
        wl, low, kh = leg_ok(st)
        worst_leg, worst_low = max(worst_leg, wl), min(worst_low, low)
        if kh:
            legs.append(t)
        tips.append(A.tip(st)[2])
    check(f'model {m.sheet}: both fists within the arms\' reach at every frame (a shoulder may come 3 px forward)',
          not reach_bad, ', '.join(reach_bad[:6]))
    check(f'model {m.sheet}: the blade never passes through the body, the shoulder plates or the helmet',
          not hits, ', '.join(hits[:6]))
    check(f'model {m.sheet}: no leg reaches further than it is long', worst_leg <= 1.0 + 1e-6, f'longest {worst_leg:.3f}')
    check(f'model {m.sheet}: no boot goes into the ground', worst_low >= -0.6, f'lowest {worst_low:+.2f} px')
    check(f'model {m.sheet}: no knee as high as the hip', not legs, str(legs[:6]))
    check(f'model {m.sheet}: the sword\'s tip never goes into the ground', min(tips) > 4, f'lowest {min(tips):.0f} px up')
    # the hit boxes: while one is on, the blade sweeps the sector in front of him, and at its
    # middle the tip reaches the hit box's edge
    for start, n in m.hits:
        psis = [A.angles(clip.at(t)['axis'])[0] for t in range(start, start + n)]
        side_ = 1 if psis[0] > 0 else -1
        inside = all(abs(p) <= SECTOR + 20 for p in psis)
        crosses = min(abs(p) for p in psis) < 15
        check(f'model {m.sheet}: hit {start}..{start + n - 1}: the blade crosses the 150-degree sector in front while '
              f'the hit box is on', inside and crosses, 'azimuths ' + ' '.join(f'{p:.0f}' for p in psis))
        mid = min(range(start, start + n), key=lambda t: abs(A.angles(clip.at(t)['axis'])[0]))
        tp = A.tip(clip.at(mid))
        r = math.hypot(tp[0], tp[1])
        check(f'model {m.sheet}: hit {start}: the tip reaches the hit box\'s edge in front ({REACH} px, at least 90%)',
              r >= 0.9 * REACH, f'{r:.0f} px at frame {mid}, {tp[2]:.0f} px up')
        enter = psis[0] * side_
        check(f'model {m.sheet}: hit {start}: the blade enters the sector as the hit box comes on (60..100 degrees)',
              60 <= enter <= 100, f'{psis[0]:.0f}')


# ------------------------------------------------------------------ the feet
# User 2026-10-01 (third version): "before the swing the left foot goes forward and the right
# back - the whole Boss looks like he jumps; it must not. The sword goes from the right shoulder
# towards the left foot, so only step out the right foot as he swings, the whole body turning a
# little with it; for the second cut the right foot goes back and the left steps out (it now
# goes from the left shoulder to the right)". The standards come from those words and from the
# sword (which side a cut comes from), not from attacks.py's foot tables:
#   - one foot at a time: never both feet off their spot (lifted, or the ankle moved along the
#     ground) in the same combat frame (the same pose, starting from a move)
#   - the windup is the upper body's: until STEP_LEAD frames before the first hit box opens (a
#     step belongs to the stroke, not the windup) both feet are where the carry has them and the
#     hips move no more than WINDUP_HX forward / back, WINDUP_D down
#   - each cut steps out the foot on the side it comes from (the blade's side as the hit box
#     opens), forward at least STEP_MIN, and it lands with the blow: within LAND_SLACK frames of
#     the frame the blade is straight ahead
#   - (user 2026-10-01, after the third version: "for the second cut just step the left foot
#     straight forward, don't bring the right foot back") the first cut's foot stays where it
#     landed until the second cut's foot is down, and the second steps past it (lands at least
#     STEP_MIN ahead of it, on the ground)
#   - the hips never jump: per combat frame at most HIP_STEP_X forward / back, HIP_STEP_D down / up
# Positions are on the ground (world): where the game has him (the state's 'adv') added back.
# User 2026-10-01, the same time: "as he swings the upper body must go further forward, the
# weight further forward ... the weight should go forward with the step, and leaning forward
# lets the sword go lower and reach further, so it reaches the player's height more easily":
#   - at each blow the hips are at least WEIGHT_FWD of the way from the back foot to the front
#     one, the chest leans at least LEAN_MIN, the tip reaches the hit box's edge (REACH) and is
#     below the player's height (PLAYER_HEIGHT)
STEP_LEAD = 8         # combat frames: a heavy step may leave the ground this long before the hit box
WINDUP_HX = 2.0       # px: the weight settling back a little
WINDUP_D = 4          # px: the knees giving a little (more reads as crouching to jump)
STEP_MIN = 12.0       # px forward: a step, not a shuffle (an eighth of his leg's reach is 8)
LAND_SLACK = 1        # combat frames
HIP_STEP_X = 4.5      # px a combat frame: no faster than the stepping foot travels on average (the royal
                      # sweep's 36 px in 8 frames). User 2026-10-01: the weight goes forward WITH the step
                      # (it was 2.5 before that: the walk moves the hips 1, the fast approach 2)
HIP_STEP_D = 2        # px a combat frame
GROUND = 0.5          # px above the boot's lowest reach: the foot is off the ground
WEIGHT_FWD = 0.6      # share of the stance: clearly onto the front foot (the middle is 0.5; the third version was 0.46)
LEAN_MIN = 15.0       # degrees of chest lean at the blow (the third version: 12)
PLAYER_HEIGHT = 40.0  # the player's body (CLAUDE.md: 40 px, the plume aside)


def foot_at(st, k):
    """(position on the ground (x, out, sideways), lifted) of a foot in a state; x on the ground
    (where the game has him, 'adv', added back)."""
    f = st['feet'][k]
    x, out, z, pitch = f[:4]
    lat = f[5] if len(f) > 5 else 0.0
    return (x + st.get('adv', 0.0), out, lat), z > K.boot_drop(pitch) + GROUND


def hips_at(st):
    return st['hx'] + st.get('adv', 0.0)


def moving(a, b):
    """The feet that are off their spot going from state a to state b."""
    out = set()
    for k in 'RL':
        pa, _ = foot_at(a, k)
        pb, up = foot_at(b, k)
        if up or math.dist(pa, pb) > 0.3:
            out.add(k)
    return out


def runs(states, k):
    """[(first, last)] index runs where foot k is off its spot (states one combat frame apart)."""
    out, start = [], None
    for i in range(1, len(states)):
        on = k in moving(states[i - 1], states[i])
        if on and start is None:
            start = i
        if not on and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(states) - 1))
    return out


def feet_checks(m):
    clip = m.clip
    sts = [clip.at(t) for t in range(m.total)]
    both = [t for t in range(1, m.total) if len(moving(sts[t - 1], sts[t])) == 2]
    check(f'feet {m.sheet}: one foot at a time (never both off their spot in one frame)', not both, str(both[:8]))
    hx_jump = max(abs(hips_at(b) - hips_at(a)) for a, b in zip(sts, sts[1:]))
    d_jump = max(abs(b['D'] - a['D']) for a, b in zip(sts, sts[1:]))
    check(f'feet {m.sheet}: the hips never jump (at most {HIP_STEP_X} px forward/back, {HIP_STEP_D} px up/down a frame)',
          hx_jump <= HIP_STEP_X and d_jump <= HIP_STEP_D, f'worst {hx_jump:.2f} px, {d_jump} px')
    steps_ = {k: runs(sts, k) for k in 'RL'}
    print(f'     steps: ' + '; '.join(f'{k} ' + ' '.join(f'{a}..{b}' for a, b in steps_[k]) for k in 'RL'))
    if not m.hits:
        return
    first = m.hits[0][0] - STEP_LEAD
    wind = sts[:first]
    planted = all(foot_at(s, k)[0] == (0.0, 0.0, 0.0) and not foot_at(s, k)[1] for s in wind for k in 'RL')
    hx_w = max(abs(hips_at(s)) for s in wind)
    d_w = max(s['D'] for s in wind)
    check(f'feet {m.sheet}: the windup is the upper body\'s (feet where the carry has them, hips within '
          f'{WINDUP_HX} px and {WINDUP_D} px down until frame {first})', planted and hx_w <= WINDUP_HX and d_w <= WINDUP_D,
          f'feet {"planted" if planted else "MOVED"}, hips {hx_w:.1f} px, {d_w} px down')
    prev = None
    for start, n in m.hits:
        psis = [A.angles(clip.at(t)['axis'])[0] for t in range(start, start + n)]
        side_ = 'R' if psis[0] > 0 else 'L'
        mid = min(range(start, start + n), key=lambda t: abs(A.angles(clip.at(t)['axis'])[0]))
        runs_ = steps_[side_]
        if not runs_:
            check(f'feet {m.sheet}: hit {start} steps out the {side_} foot', False, 'no step')
            continue
        a, b = min(runs_, key=lambda r: abs(r[1] - mid))
        land = b
        fwd = foot_at(sts[b], side_)[0][0] - foot_at(sts[a - 1], side_)[0][0]
        check(f'feet {m.sheet}: hit {start} (from his {"right" if side_ == "R" else "left"}) steps out the '
              f'{"right" if side_ == "R" else "left"} foot, landing with the blow (frame {mid} +-{LAND_SLACK})',
              abs(land - mid) <= LAND_SLACK and fwd >= STEP_MIN, f'off the ground {a}..{b - 1}, lands {land}, {fwd:.0f} px forward')
        # the weight with the step, the chest over it, the blade low and long
        st = sts[mid]
        other = 'L' if side_ == 'R' else 'R'
        front, back_ = foot_at(st, side_)[0][0], foot_at(st, other)[0][0]
        share = (hips_at(st) - back_) / max(1e-6, front - back_)
        tp = A.tip(st)
        r = math.hypot(tp[0], tp[1])
        check(f'feet {m.sheet}: hit {start}: the weight is on the front foot (hips {WEIGHT_FWD:.0%}+ of the way) and '
              f'the chest leans {LEAN_MIN:.0f}+ degrees', share >= WEIGHT_FWD and st['lx'] >= LEAN_MIN,
              f'hips {share:.0%} of the way from the back foot, lean {st["lx"]:.0f} degrees (frame {mid})')
        check(f'feet {m.sheet}: hit {start}: the blade reaches the hit box\'s edge ({REACH:.0f}) below the player\'s height '
              f'({PLAYER_HEIGHT:.0f} px)', r >= REACH and tp[2] <= PLAYER_HEIGHT, f'tip {r:.0f} px out, {tp[2]:.0f} px up')
        if prev:
            pk, pland = prev
            moved = [r_ for r_ in steps_[pk] if r_[0] <= land and r_[1] > pland]
            gap = fwd_land = foot_at(sts[land], side_)[0][0] - foot_at(sts[land], pk)[0][0]
            check(f'feet {m.sheet}: hit {start}: the first cut\'s foot stays where it landed, this one steps past it',
                  pk != side_ and not moved and gap >= STEP_MIN,
                  f'{pk} {"moved " + str(moved) if moved else "stays"}; {side_} lands {fwd_land:.0f} px ahead of it')
        prev = (side_, land)


def game_numbers():
    """TWIN_STEP_DISTANCE / TWIN_STEP_TIME as the game has them (scripts/combat/veltharis_data.gd)."""
    import os
    import re
    src = open(os.path.join(B.ROOT, 'scripts', 'combat', 'veltharis_data.gd')).read()
    get = lambda n: float(re.search(r'const %s := ([0-9.]+)' % n, src).group(1))
    return get('TWIN_STEP_DISTANCE'), get('TWIN_STEP_TIME')


def advance_checks(m):
    """The twin slash: the game's step before the second hit (veltharis_data) is the one the art
    is drawn about - the same distance and frames - and after it the first cut's foot is just
    where the game has him."""
    dist, secs = game_numbers()
    frames = round(secs * 60)
    clip = m.clip
    start2 = m.hits[1][0]
    advs = [clip.at(t)['adv'] for t in range(m.total)]
    moving_at = [t for t in range(1, m.total) if abs(advs[t] - advs[t - 1]) > 1e-6]
    ok = (abs(advs[-1] - dist) < 1e-6 and moving_at == list(range(start2 - frames, start2))
          and all(abs(advs[t] - advs[t - 1] - dist / frames) < 1e-6 for t in moving_at))
    check(f'{m.sheet}: the game\'s step before the second hit ({dist:.0f} px in {frames} frames, veltharis_data) is the '
          f'one the sprites are drawn about', ok, f'{advs[-1]:.1f} px over frames {moving_at[:1]}..{moving_at[-1:]}')
    st = clip.at(start2)
    x = st['feet']['R'][0]
    check(f'{m.sheet}: after the step the right foot is where the game has him', abs(x) < 0.5, f'{x:.1f} px')
    mt = set(m.times)
    held = [t for t in range(start2 - frames, start2) if t not in mt]
    check(f'{m.sheet}: one pose for every frame of the game\'s step (a held pose would carry the planted foot along)',
          not held, str(held))


def entry_feet_checks(m):
    """Starting from a move: one foot at a time from the loop's pose to the attack's own."""
    if not m.has_entries:
        return
    bad = []
    for kind in AW.KINDS:
        for e in AT.ENTRY_FROM:
            times, _, end = m.entry_spec
            sts = AT.entry(m.clip, kind, e, *m.entry_spec) + [m.clip.at(end)]
            for i in range(1, len(sts)):
                if len(moving(sts[i - 1], sts[i])) == 2:
                    bad.append(f'{kind}{e}:{times[i - 1]}')
    check(f'feet {m.sheet}: starting from a move, one foot at a time', not bad, ', '.join(bad[:8]))


# ------------------------------------------------------------------ the frames
def drawn(d, name, i):
    """(sword pixels as drawn before anything covers them, placement) of a pose (facing left:
    mirrored to the frame)."""
    rec = AA.SWORD.get((d, name, i))
    if not rec:
        return {}, None
    sw, pl, g = rec
    if d == 'left':
        sw = {(2 * rig.AX - x, y): c for (x, y), c in sw.items()}
    return sw, pl


def grip(d, name, i):
    rec = AA.SWORD.get((d, name, i))
    if not rec:
        return None
    g = rec[2]
    return (2 * rig.AX - g[0], g[1]) if d == 'left' else g


def tip_xy(d, pl):
    view = 'right' if d in ('right', 'left') else ('front' if d == 'down' else 'back')
    t = K.swd.tip_of(view, pl)
    return (2 * rig.AX - t[0], t[1]) if d == 'left' else t


ARM_NEAR = 7          # px around a posed arm's bones that are the arm, not the upper body


def _seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    n2 = vx * vx + vy * vy
    t = 0.0 if n2 < 1e-9 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / n2))
    return math.dist(p, (a[0] + t * vx, a[1] + t * vy))


def without_arms(f, arms):
    """A frame without the pixels near the posed arms' bones (arms: [joints] in frame
    coordinates). The checks_hit measure dropped everything within 26 px of the grip: with the
    hands raised by the head (the windups) that dropped the head too and the measure jumped."""
    if not arms:
        return f
    segs = []
    for J in arms:
        pts = [J['shoulder'], J['elbow'], J['wrist'], J['hand']]
        segs += list(zip(pts, pts[1:]))
    return {q: c for q, c in f.items()
            if all(_seg_dist((q[0] + 0.5, q[1] + 0.5), a, b) > ARM_NEAR for a, b in segs)}


def edges(f):
    t = H.top(f)
    xs = [q[0] for q in f if q[1] < t + H.HEAD_ROWS]
    return round(sum(xs) / len(xs))


def joints(d, name, i):
    """The posed arms of a pose (anim_attack), or the carry's sword arm (anim_walk / anim_kneel
    record it for the carry and the loops), in frame coordinates."""
    out = [J for J in (AA.JOINTS.get((d, name, i, k)) for k in 'RL') if J]
    if not out:
        J = AW.ARM_JOINTS.get((d, name, i))
        out = [J] if J else []
    if d == 'left':
        out = [{n: (2 * rig.AX - v[0], v[1]) for n, v in J.items()} for J in out]
    return out


def steps(label, d, frames, swords, grips, tips, arms=None, offs=None):
    """Between two poses: the top of the body and the upper body's mean column (its top rows,
    without the sword and the posed arms) move at most STEP_MAX; the tip at most TIP_STEP. On
    screen: offs, (dx, dy) per pose, is how far the game has moved the sprite (the twin slash's
    step)."""
    worst_top, worst_edge, worst_tip = 0, 0, 0.0
    where = None
    arms = arms or [None] * len(frames)
    offs = offs or [(0, 0)] * len(frames)
    for j, (a, b) in enumerate(zip(frames, frames[1:])):
        oa, ob = offs[j], offs[j + 1]
        ba, bb = H.body(a, swords[j]), H.body(b, swords[j + 1])
        dt = abs(H.top(ba) + oa[1] - H.top(bb) - ob[1])
        if arms[j] is not None and arms[j + 1] is not None:
            ea, eb = (edges(without_arms(ba, arms[j])),), (edges(without_arms(bb, arms[j + 1])),)
        else:
            ea, eb = H.edges(ba, grips[j]), H.edges(bb, grips[j + 1])
        de = max(abs(p + oa[0] - q - ob[0]) for p, q in zip(ea, eb))
        if dt > worst_top or de > worst_edge:
            where = j
        worst_top, worst_edge = max(worst_top, dt), max(worst_edge, de)
        if tips[j] and tips[j + 1]:
            worst_tip = max(worst_tip, math.dist((tips[j][0] + oa[0], tips[j][1] + oa[1]),
                                                 (tips[j + 1][0] + ob[0], tips[j + 1][1] + ob[1])))
    check(f'{label} {d}: the top of the body moves at most {STEP_MAX} px a pose', worst_top <= STEP_MAX, f'worst {worst_top} px')
    check(f'{label} {d}: the upper body moves sideways at most {STEP_MAX} px a pose', worst_edge <= STEP_MAX,
          f'worst {worst_edge} px (pose {where})')
    check(f'{label} {d}: the sword tip moves at most {TIP_STEP} px a pose', worst_tip <= TIP_STEP, f'worst {worst_tip:.0f} px')


def below_allowed(m, d):
    """How far below the foot line this direction may draw: H.BELOW for the feet; a blade low
    and towards the camera (in front of him seen from the front, on his near side seen from
    the side) is drawn below them by perspective: its 3D point's screen offset from the foot
    anchor (attack3d.project: DEPTH of the distance towards the camera, minus the height), at
    both edges of the blade (BLADE_HALF along its width), +1 for the outline."""
    view = 'right' if d in ('right', 'left') else ('front' if d == 'down' else 'back')
    far = d == 'left'
    worst = -99.0
    for s in m.states:
        for t in range(0, int(A.SWORD_LEN) + 1, 4):
            p = A.add(s['fist'], A.mul(s['axis'], t))
            for e in (-BLADE_HALF, BLADE_HALF):
                worst = max(worst, A.project(view, A.add(p, A.mul(s['w3'], e)), far)[1])
    return max(H.BELOW[d], math.ceil(worst) + 1)


BLADE_HALF = 7.0      # px: half the blade's width at the guard (the concept's blade at 160 px), its edges


def feet_below(m, d):
    """How far below the foot line the body (without the sword) may draw: H.BELOW for the
    feet as they stand, or a foot stepped towards the camera - DEPTH of its distance (the front
    view: a foot ahead of him, the back view: one behind), +1 for the boot's own rounding. The
    blade is checked in 3D instead (model: never into the ground); for it the screen allowance
    was below_allowed(), but the front view draws the lean deeper than the 3D shoulders
    (LEAN_ROWS: a lean seen from the front brings the chest towards the camera), so a blade held
    low towards the camera comes out up to 11 px lower than its 3D projection - that line was
    for the blade, not for the legs (animation-review §5: a relaxed line only for its part)."""
    xs = [s['feet'][k][0] for s in m.states for k in 'RL']
    if d == 'down':
        return max(H.BELOW[d], math.ceil(A.DEPTH * max(xs)) + 1)
    if d == 'up':
        return max(H.BELOW[d], math.ceil(A.DEPTH * -min(xs)) + 1)
    # the side views: a foot stepped out sideways towards the camera (DEPTH of it lower), at most
    # the 2 px animation-review §4.4 allows a foot stepped towards the camera
    cam = 1.0 if d == 'right' else -1.0
    lats = [(s['feet'][k][1] if k == 'R' else -s['feet'][k][1]) * cam for s in m.states for k in 'RL']
    return max(H.BELOW[d], min(2, math.ceil(A.DEPTH * max(lats) - 0.25)))


def frame_checks(m):
    fr = m.frames()
    carry = {d: E.carry_frame(d) for d in rig.DIRS}
    for d in rig.DIRS:
        f = fr[d]
        swords = [drawn(d, s['name'], s['i'])[0] for s in m.states]
        grips = [grip(d, s['name'], s['i']) for s in m.states]
        tips = []
        for i, s in enumerate(m.states):
            pl = drawn(d, s['name'], s['i'])[1]
            tips.append(tip_xy(d, pl) if pl else None)
        # the first and the last poses are the carry itself (its sword is the carry's), or
        # the first is another move's frame (the bounce starts on the attack's contact)
        if m.first:
            src, sj = m.first
            ss = src.states[sj]
            swords[0] = drawn(d, ss['name'], ss['i'])[0]
            grips[0] = grip(d, ss['name'], ss['i'])
            pl = drawn(d, ss['name'], ss['i'])[1]
            tips[0] = tip_xy(d, pl) if pl else None
        c0 = AW.SWORD_DRAWN.get((d, 'carry', 0))
        for j in ((len(m.states) - 1,) if m.first else (0, len(m.states) - 1)):
            if not swords[j] and c0:
                sw, pl = c0
                if d == 'left':
                    sw = {(2 * rig.AX - x, y): c for (x, y), c in sw.items()}
                swords[j] = sw
                g = pl['grip']
                grips[j] = (2 * rig.AX - g[0], g[1]) if d == 'left' else g
                tips[j] = tip_xy(d, pl) if 'axis' in pl else None
        H.technical(m.sheet, d, f, feet_below(m, d), low_frames=[H.body(f_, sw) for f_, sw in zip(f, swords)])
        arms = [joints(d, s['name'], s['i']) for s in m.states]
        arms[-1] = joints(d, 'carry', 0)
        if m.first:
            ss = m.first[0].states[m.first[1]]
            arms[0] = joints(d, ss['name'], ss['i'])
        else:
            arms[0] = joints(d, 'carry', 0)
        fx, fy = E.SCREEN_FWD[d]
        offs = [(round(fx * s_.get('adv', 0.0)), round(fy * s_.get('adv', 0.0))) for s_ in m.states]
        steps(m.sheet, d, f, swords, grips, tips, arms, offs)
        if m.first:
            src, j = m.first
            H.same(f'{m.sheet} {d}', f[0], src.frames()[d][j], f'starts on {src.sheet}\'s contact (its pose {j})')
        else:
            H.same(f'{m.sheet} {d}', f[0], carry[d], 'starts on the carry (standing, the sword on the shoulder)')
        H.same(f'{m.sheet} {d}', f[-1], carry[d], 'ends on the carry')
    # starting from a move: pose 0 is the loop's pose, then on into the attack's own poses
    n = len(m.entry_spec[0])
    for (kind, e), en in (m.entries().items() if m.has_entries else ()):
        for d in rig.DIRS:
            H.same(f'{m.sheet} from {kind} {e} {d}', en[d][0], AW.frames(d, kind)[e], 'starts on the loop\'s pose')
            seq = en[d] + [fr[d][n]]
            names = [(f'{m.clip.name}_{kind}_{e}', i) for i in range(n)] + [(m.clip.name, n)]
            sw = [drawn(d, nm, i)[0] for nm, i in names]
            gr = [grip(d, nm, i) for nm, i in names]
            tp = [tip_xy(d, drawn(d, nm, i)[1]) if drawn(d, nm, i)[1] else None for nm, i in names]
            ls = AW.SWORD_DRAWN.get((d, kind, e))
            if ls:
                s0, p0 = ls
                if d == 'left':
                    s0 = {(2 * rig.AX - x, y): c for (x, y), c in s0.items()}
                sw[0] = s0
                g = p0['grip']
                gr[0] = (2 * rig.AX - g[0], g[1]) if d == 'left' else g
            # moving sideways the foot towards the camera is lower: no lower than in the loop it
            # comes from (+1: the same foot drawn with the knee bent another way)
            loop_low = max(q[1] for f in AW.frames(d, kind) for q in f) - rig.AY + 1
            H.technical(f'{m.sheet} from {kind} {e}', d, en[d], max(below_allowed(m, d), loop_low))
            ar = [joints(d, nm, i) for nm, i in names]
            ar[0] = joints(d, kind, e)
            steps(f'{m.sheet} from {kind} {e}', d, seq, sw, gr, tp, ar)


def hands_checks(m):
    """The fists are on the drawn grip: the right fist's centre is the grip point, the left
    HANDS px along the sword (or on its way), in every view."""
    worst = 0.0
    for s in m.states[1:-1]:
        for d in rig.DIRS:
            J = AA.JOINTS.get((d, s['name'], s['i'], 'R'))
            g = AA.SWORD[(d, s['name'], s['i'])][2]
            if J:
                worst = max(worst, math.dist(J['hand'], g))
    check(f'{m.sheet}: the right fist\'s centre is on the drawn grip in every view', worst < 0.6, f'worst {worst:.2f} px')
    long_ = []
    for key, J in AA.JOINTS.items():
        if key[1] != m.clip.name:
            continue
        n = math.dist(J['shoulder'], J['hand'])
        if n > A.ARM + 0.5:
            long_.append(f'{key[0]}:{key[2]}{key[3]} {n:.1f}')
    check(f'{m.sheet}: no drawn arm longer than the arm (shoulder to fist {A.ARM:.1f} px)', not long_, ', '.join(long_[:6]))


DISTINCT = 0.12      # animation-review §4.5: two hits of one combo differ by this much in outline


def distinct_checks(m):
    """The twin slash's two hits read as two different strokes from the outline alone: the
    windups (the sword up beside the right / the left shoulder) and the follow-throughs (low on
    his left, two hands / low on his right, one hand) differ by DISTINCT or more, whole outline
    (sword and cape included). The contact moments are alike on purpose: both the blade
    straight ahead at knee height (the hit box's middle) - only listed."""
    fr = m.frames()
    pairs = [('windup', 40, AT.W + 46), ('follow-through', AT.W + 12, AT.W2 + 14)]
    for label, t1, t2 in pairs:
        i, j = m.times.index(min(m.times, key=lambda t: abs(t - t1))), m.times.index(min(m.times, key=lambda t: abs(t - t2)))
        for d in rig.DIRS:
            v = C.sil_change(fr[d][i], fr[d][j])
            check(f'{m.sheet} {d}: the two hits\' {label}s differ in outline by {DISTINCT:.0%} or more', v >= DISTINCT,
                  f'{v:.0%} (frames {m.times[i]} / {m.times[j]})')
    i, j = m.times.index(AT.W + 3), m.times.index(AT.W2 + 3)
    print('     contacts: ' + ', '.join(f'{d} {C.sil_change(fr[d][i], fr[d][j]):.0%}' for d in rig.DIRS))


def shared_opening(ms):
    """The twin slash starts with the royal sweep's windup and shares its entry sheets (which
    join the attack at ENTRY_END): the poses up to there are the same frames."""
    c1, tw = ms[0], ms[1]
    n = c1.times.index(AT.ENTRY_END) + 1
    same = c1.times[:n] == tw.times[:n] and all(c1.frames()[d][i] == tw.frames()[d][i] for d in rig.DIRS for i in range(n))
    check('boss_twin: its poses up to frame {} are boss_c1\'s (the entry sheets join both at pose {})'.format(
        AT.ENTRY_END, n), same, f'{c1.times[:n]} / {tw.times[:n]}')


def main():
    _sync()
    ms = E.moves()
    shared_opening(ms)
    for m in ms:
        model_checks(m)
        feet_checks(m)
        if m.sheet == 'boss_twin':
            advance_checks(m)
        entry_feet_checks(m)
        frame_checks(m)
        hands_checks(m)
        if m.sheet == 'boss_twin':
            distinct_checks(m)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    return n


def selftest():
    """Break numbers and frames on purpose: each must be caught."""
    caught = []
    _sync()
    m = E.moves()[0]
    # an arm out of reach, a blade through the head
    clip = m.clip
    keys = [(t, dict(k)) for t, k in clip.keys]
    keys[3][1]['fist'] = (10.0, 30.0, 122.0)
    keys[6][1]['fist'] = (2.0, 0.0, 150.0)
    bad = E.Move(m.sheet, AT.Clip('c1_bad', keys), m.total, m.hits, m.caption)
    results.clear()
    model_checks(bad)
    caught.append(results.count(False) >= 2)
    # the second version's feet: the left foot forward and the right back together in the
    # windup; a step landing late
    keys2 = [(t, dict(k)) for t, k in clip.keys]
    for i in (2, 3):
        keys2[i][1]['feet'] = {'R': (-6.0, 2.0, gait.ANKLE_H, 0.0), 'L': (24.0, 2.0, gait.ANKLE_H, 0.0)}
    v2 = E.Move(m.sheet, AT.Clip('c1_v2', keys2), m.total, m.hits, m.caption)
    results.clear()
    feet_checks(v2)
    caught.append(results.count(False) >= 2)
    keys3 = [(t, dict(k)) for t, k in clip.keys]
    for t, k in keys3:
        if AT.W <= t < AT.W + 8:
            k['feet'] = {'R': None, 'L': AT.STAND}
    late = AT.Clip('c1_late', keys3, {'R': [(AT.STEP_FROM, AT.STAND), (AT.W + 8, AT.RF)]})
    results.clear()
    feet_checks(E.Move(m.sheet, late, m.total, m.hits, m.caption))
    caught.append(results.count(False) >= 1)
    # the third version's blow: the hips in the middle, upright, the blade at the player's head
    keys4 = [(t, dict(k)) for t, k in clip.keys]
    for t, k in keys4:
        if t == AT.W + 4:
            k.update(hx=12.0, lx=12, fist=(38.0, -2.0, 99.0), dir=(0.0, -20.0))
    mid = AT.Clip('c1_v3', keys4, {s_: list(v) for s_, v in clip.tracks.items()})
    results.clear()
    feet_checks(E.Move(m.sheet, mid, m.total, m.hits, m.caption))
    caught.append(results.count(False) >= 2)
    # the sprites drawn about a different step than the game's
    tw = E.moves()[1]
    off = AT.Clip('twin_off', tw.clip.keys, {s_: list(v) for s_, v in tw.clip.tracks.items()},
                  advance=lambda t: 0.75 * AT.twin_advance(t), musts=tw.clip.musts)
    results.clear()
    advance_checks(E.Move(tw.sheet, off, tw.total, tw.hits, tw.caption, entry_times=True))
    caught.append(results.count(False) >= 2)
    # a hit box that comes on before the blade is round in front
    late = E.Move(m.sheet, m.clip, m.total, [(40, 9)], m.caption)
    results.clear()
    model_checks(late)
    caught.append(results.count(False) >= 1)
    # frames: a head that jumps 20 px, an off-palette colour, a tip that jumps
    d = 'right'
    fr = [dict(f) for f in m.frames()[d]]
    fr[5] = {(x, y - 20 if y < 150 else y): c for (x, y), c in fr[5].items()}
    fr[6][(128, 150)] = (1, 2, 3)
    results.clear()
    H.technical('selftest', d, fr)
    swords = [drawn(d, s['name'], s['i'])[0] for s in m.states]
    grips = [grip(d, s['name'], s['i']) for s in m.states]
    tips = [(0, 0)] * len(fr)
    tips[8] = (200, 0)
    steps('selftest', d, fr, swords, grips, tips)
    caught.append(results.count(False) >= 3)
    results.clear()
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(1 if main() else 0)
