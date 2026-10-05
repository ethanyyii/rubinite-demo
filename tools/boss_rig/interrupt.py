"""Interrupted attacks (2026-10-05): the Boss broken (BROKEN) or killed (DEAD) in the middle of an attack or of
being bounced, and staggered (STAGGER) during an attack's recovery.

User 2026-10-05: "1 好，現在一次做三種銜接動作" - 出招中被削光韌性跪下、收招時短僵直、出招中死亡 (the three
entries left for "when every attack exists", tools/boss_rig/README.md).

The game (boss_sim.gd): BROKEN comes from any frame of an attack (hit in the windup, broken by a perfect parry at
the contact, hit in the recovery) or of being bounced (hit while bounced - the usual way); never in the air.
STAGGER only in an attack's recovery (current_hit_index() < 0), 0.3 s, then IDLE: it ends in the carry. DEAD from
any frame he can be hit in.

  break (and death)  from the interrupted pose, drawn by the attack rig: the blow's jolt (head back, cape kicked),
                     the left hand lets go, the sword goes down the way he puts it down (carry.pose3: the tip
                     forward and down) and into the ground at his right side, the knees giving - ending on
                     boss_kneel_down's pose JUNCTION_COL as the attack rig draws it (fitted: JUNCTION). The game
                     then plays boss_kneel_down from column JUNCTION_COL + 1 (and for DEAD boss_death's last
                     three) - anim_kneel's own frames.
  stagger            from a recovery pose: the jolt, then the attack's own recovery path to the carry (the way the
                     sword already goes back onto the shoulder: it never passes through him) run in STAGGER's
                     0.3 s; the last pose is the carry (the carry's own renderer, as every attack ends).

Every frame of an attack cannot have its own: each sheet gets a few starting points (exits) and the game takes the
one nearest the pose shown (json). The jump from the pose shown to its exit's first pose is at most HIT_BODY px
(head, fists, grip, feet: 3D) and HIT_TIP px (the sword's tip) - three times the step a pose may move, at the
moment of the blow: the game freezes it (hitstop 0.04 - 0.15 s), flashes him white and shakes the screen
(the knight's hit reactions are allowed a big first move for the same reason, art-progress batch 4).
"""
import math
import attacks as AT
import attack3d as A
import carry
import anim_kneel as K

HIT_BODY, HIT_TIP = 32.0, 120.0
JUNCTION_COL = 3                       # boss_kneel_down's pose the break ends on (the game goes on from the next)
# the attack rig's fit of that pose (D 25, lean 7, bow 14, the legs going down u 0.7, the sword in the ground at
# his right side; outline within 16 % in every view - the 1 - 2 px edges and the cape lying on the ground):
JUNCTION = dict(D=24, lx=4.0, bend=4.0, bow=14.0, ck=-1.0, fist=(24.0, 40.0, 93.0), u=0.7)
ABOVE = dict(D=14, lx=3.0, bend=3.0, bow=10.0, ck=0.0, u=0.45)   # the tip on the ground where it goes in
RECOIL = dict(lx=-4.0, bow=-10.0, ck=3.0)                          # the jolt (boss_kneel_down's pose 0, standing)
STAND_FIST = (21.0, 37.0, 117.0)       # the standing pose's sword hand (sword.standing: side / front / back)
STAGGER = 18                           # combat frames (veltharis_data SHORT_STAGGER_TIME 0.3 s)
HIT_HOLD, MID_HOLD, J_HOLD = 3, 2, 4   # the jolt is held while the game freezes; then a pose every 2 frames
PLANT = 4                              # frames from the tip on the ground to the sword in (two poses: 25 px down)
TIP_PER_POSE = 70.0                    # px the tip travels between two of the bridge's poses (TIP_STEP 80)


# ------------------------------------------------------------------ distances between poses
def head(st):
    p = A.yaw(A.HEAD, st.get('tw', 0.0))
    lv = A.lean_vec(st)
    p = A.bend_point(st, (p[0] + lv[0] * (A.HEAD[2] - A.BELT_U), p[1] + lv[1] * (A.HEAD[2] - A.BELT_U), p[2]))
    return (p[0] + st.get('hx', 0.0), p[1], p[2] - st.get('D', 0) + st.get('lift', 0.0))


def points(st):
    gR, gL = A.fists(st)
    body = {'head': head(st), 'fR': gR, 'grip': A.sword_grip(st)}
    if gL is not None:
        body['fL'] = gL
    for k in 'RL':
        f = st['feet'][k]
        body['foot' + k] = (f[0], f[1], f[2])
    return body, A.tip(st)


VIEWS = (('right', False), ('right', True), ('front', False), ('back', False))   # the side views, near and far


def pose_dist(a, b):
    """(largest move on screen of the head, fists, grip and feet, of the tip) between two poses, over the four views
    (attack3d.project: what each direction draws - the depth a third as long)."""
    (pa, ta), (pb, tb) = points(a), points(b)
    body = tip = 0.0
    for v, far in VIEWS:
        P = lambda p: A.project(v, p, far)
        body = max([body] + [math.dist(P(pa[k]), P(pb[k])) for k in pa if k in pb])
        tip = max(tip, math.dist(P(ta), P(tb)))
    return body, tip


def near(a, b):
    d, t = pose_dist(a, b)
    return d <= HIT_BODY and t <= HIT_TIP


def choose_exits(states, allowed):
    """Pose indices to start from, covering every allowed index (each within HIT_* of one), and the map
    {pose index: exit}. Greedy: from the first uncovered pose, the run it and the next ones share a centre."""
    allowed = sorted(allowed)
    exits = []
    k = 0
    while k < len(allowed):
        run = [allowed[k]]
        best = allowed[k]
        j = k + 1
        while j < len(allowed):
            cand = run + [allowed[j]]
            centres = [c for c in cand if all(near(states[c], states[s]) for s in cand)]
            if not centres:
                break
            run = cand
            best = min(centres, key=lambda c: max(pose_dist(states[c], states[s])[0] / HIT_BODY
                                                  + pose_dist(states[c], states[s])[1] / HIT_TIP for s in run))
            j += 1
        exits.append(best)
        k = j
    which = {}
    for i in allowed:
        which[i] = min(exits, key=lambda e: pose_dist(states[e], states[i])[0] / HIT_BODY + pose_dist(states[e], states[i])[1] / HIT_TIP)
    return exits, which


# ------------------------------------------------------------------ keys
def key_of(s):
    """A key from a drawn state (its sword's drawn width as the flat: no turn of the flat at the jolt)."""
    k = AT.carry_key(**{n: s[n] for n in AT.SCALARS if n in s})
    k['fist'] = tuple(s['fist'])
    k['dir'] = A.angles(s['axis'])
    k['flat'] = tuple(s.get('w3') or s['flat'])
    k['lhand'] = tuple(s['lhand'])
    k['poleR'], k['poleL'] = tuple(s['poleR']), tuple(s['poleL'])
    k['feet'] = {n: tuple(f[:4]) for n, f in s['feet'].items()}
    return k


def jolt(k):
    out = dict(k)
    out['lx'] = k.get('lx', 0.0) + RECOIL['lx']
    out['bow'] = max(-16.0, k.get('bow', 0.0) + RECOIL['bow'])
    out['ck'] = k.get('ck', 0.0) + RECOIL['ck']
    return out


def descent_feet(u, D):
    R, L = K.descent_legs(u, D)
    return {'R': (R['ankle'][0], 0.0, R['ankle'][1], R['pitch']), 'L': (L['ankle'][0], 0.0, L['ankle'][1], L['pitch'])}


def carry_fist(b):
    """The sword hand on the way between standing (b 0) and the carry (b 1): carry.place's 3D."""
    f = A.lerp(STAND_FIST, carry.FIST, b)
    bump = math.sin(math.pi * b)
    return (f[0] + carry.REACH * bump, f[1], f[2] + carry.LIFT * bump)


def carry_sword(b):
    a, w = carry.pose3(b)
    return A.angles(a), w


def body_key(spec, turn):
    """A key of the way down: spec (JUNCTION, ABOVE) with the sword in the ground / above it."""
    d, w = carry_sword(0.0)
    k = AT.carry_key(D=spec['D'], lx=spec['lx'], bend=spec['bend'], bow=spec['bow'], ck=spec['ck'], dir=d, flat=w,
                     ht=turn, tw=turn, feet=descent_feet(spec['u'], spec['D']))
    return k


def junction_key(turn=0.0):
    k = body_key(JUNCTION, turn)
    k['fist'] = JUNCTION['fist']
    return k


def above_key(turn=0.0, D=None):
    """The sword upright over where it goes in, its tip on the ground; the hips D down."""
    spec = dict(ABOVE) if D is None else dict(ABOVE, D=D, u=JUNCTION['u'] * D / JUNCTION['D'])
    k = body_key(spec, turn)
    f = JUNCTION['fist']
    k['fist'] = (f[0], f[1], A.SWORD_LEN + 0.5)
    return k


def waypoint(b, D, u, turn=0.0, lx=0.0, bow=0.0):
    """The sword on its way down (carry.pose3 b: 0.68 upright before the shoulder, 0.34 level forward, 0.2 the tip
    forward and down), the hand as low as the hips are (D)."""
    d, w = carry_sword(b)
    f = carry_fist(b)
    return AT.carry_key(D=D, lx=lx, bow=bow, dir=d, flat=w, fist=(f[0], f[1], f[2] - D), ht=turn, tw=turn, feet=descent_feet(u, D))


def end_turn(ht, spin):
    """The facing he ends in: square to it again (a whole number of turns); turned right round (the ash spin) he goes
    on the way he was turning - turned back, the swung-out blade goes through him."""
    if spin:
        return 360.0 * math.ceil((ht - 10.0) / 360.0)
    return 360.0 * round(ht / 360.0)


# ------------------------------------------------------------------ the break (and death)
class Bridge:
    """A bridge's clip, its pose times and holds (combat frames)."""

    def __init__(self, clip, times, holds, path):
        self.clip, self.times, self.holds, self.path = clip, times, holds, path
        self.total = sum(holds)
        self.spec = None            # what rebuilds it (spec(), from_spec())


def _flags(src):
    return dict(whole_turn=src.whole_turn, spin=src.spin, upwrap=src.upwrap, left_own=getattr(src, 'left_own', False))


def problems(clip, t_end, t_ground):
    """Frames where the 3D model breaks: a fist out of reach, the held blade through the body, a leg longer than it
    is or a boot in the ground, the tip in the ground before it is put in (t_ground) - lower than it was hit (the
    ash spin's drag has it on the ground already)."""
    import checks_attack as CA
    bad = []
    tip0 = A.tip(clip.at(0))[2]
    floor = (min(0.0, tip0) - 0.5) if tip0 > 5.0 else -3.0   # dragged along the ground: it scrapes as it comes up
    for t in range(t_end + 1):
        st = clip.at(t)
        for k, a in A.arms(st).items():
            if a and a[3] < -0.5:
                bad.append((t, 'reach' + k))
        if A.body_hits(st):
            bad.append((t, 'blade in body'))
        wl, low, _ = CA.leg_ok(st)
        if wl > 1.0 + 1e-6 or low < -0.6:
            bad.append((t, 'leg'))
        if t < t_ground and A.tip(st)[2] < floor:
            bad.append((t, 'tip in ground'))
    return bad


STEP_BODY, STEP_TIP = 16.0, 80.0      # px between two poses (checks_attack STEP_MAX, TIP_STEP): head, hands, feet / tip


def step_problems(clip, times):
    """Poses of the bridge that move a part further than a pose may (3D: at least what any view shows)."""
    bad = []
    for a, b in zip(times, times[1:]):
        d, t = pose_dist(clip.at(a), clip.at(b))
        if d > STEP_BODY or t > STEP_TIP:
            bad.append((b, f'step {d:.0f}/{t:.0f}'))
    return bad


def tip_travel(clip, t0, t1):
    out, prev = 0.0, A.tip(clip.at(t0))
    for i in range(1, 4 * (t1 - t0) + 1):
        p = A.tip(clip.at(t0 + i / 4.0))
        out += math.dist(prev, p)
        prev = p
    return out


def _yaw_foot(f, side, delta):
    """A foot (x, out, z, pitch) turned delta degrees about the anchor (out: from its hip's line, + outwards)."""
    lat = (17.0 + f[1]) if side == 'R' else -(17.0 + f[1])
    x, l, _ = A.yaw((f[0], lat, 0.0), delta)
    out = (l - 17.0) if side == 'R' else (-l - 17.0)
    return (x, out) + tuple(f[2:])


def yawed(k, delta):
    """Key k turned delta degrees round him (the ash spin carried on): the body, the arms' reach, the sword, the
    elbows, the feet - the pose as it was, facing further round."""
    out = dict(k)
    out['ht'] = k.get('ht', 0.0) + delta
    out['tw'] = k.get('tw', 0.0) + delta
    hx = (k.get('hx', 0.0), 0.0, 0.0)                    # the body turns about its hips (attack3d.shoulder)
    out['fist'] = A.add(hx, A.yaw(A.sub(k['fist'], hx), delta))
    out['dir'] = (k['dir'][0] - delta, k['dir'][1])         # (azimuth + is towards his right; yaw + towards his left)
    out['flat'] = A.yaw(k['flat'], delta) if k.get('flat') else None
    for p in ('poleR', 'poleL'):
        if k.get(p):
            out[p] = A.yaw(k[p], delta)
    out['feet'] = {n: _yaw_foot(f, n, delta) for n, f in k['feet'].items()}
    return out


SPIN_RATE = 20.0          # degrees a frame he carries the turn on (the spin itself: 24)


class Even:
    """A clip re-timed to an even pace: after the jolt (held `hold` frames) every frame moves the head, hands, feet and
    tip the same share of what a pose may move (pose_dist / STEP_*), so a pose every 2 frames stays within the limits
    without the curves' slow starts and ends stretching it. clip runs t0 .. t1; this one 0 .. T."""

    def __init__(self, clip, t0, t1, hold, share=0.9):
        self.clip, self.t0, self.t1, self.hold = clip, t0, t1, hold
        self.name, self.lead, self.spin = clip.name, clip.lead, clip.spin
        self.keys = clip.keys
        self.ts, self.cs = [t0], [0.0]
        prev = clip.at(t0)
        t = t0
        while t < t1 - 1e-9:
            t = min(t1, t + 0.25)
            cur = clip.at(t)
            d, tp = pose_dist(prev, cur)
            self.ts.append(t)
            self.cs.append(self.cs[-1] + max(d / STEP_BODY, tp / STEP_TIP))
            prev = cur
        poses = max(1, math.ceil(self.cs[-1] / share))
        self.T = hold + 2 * poses

    def src_time(self, t):
        if t <= self.hold:
            return self.t0
        want = min(1.0, (t - self.hold) / (self.T - self.hold)) * self.cs[-1]
        for i in range(1, len(self.cs)):
            if self.cs[i] >= want:
                a, b = self.cs[i - 1], self.cs[i]
                f = 0.0 if b <= a else (want - a) / (b - a)
                return self.ts[i - 1] + (self.ts[i] - self.ts[i - 1]) * f
        return self.t1

    def at(self, t):
        return self.clip.at(self.src_time(t))

    def times(self):
        return [0] + list(range(self.hold, self.T, 2)) + ([self.T] if (self.T - self.hold) % 2 else [])


def even_bridge(clip, t_above, t_end, hold, path):
    """A Bridge on the even pace of clip (checked: its 3D, and no pose moving further than a pose may)."""
    ev = Even(clip, 0.0, t_end, hold)
    times = ev.times()
    if times[-1] != ev.T:
        times.append(ev.T)
    for share in (0.9, 0.75, 0.6):
        ev = Even(clip, 0.0, t_end, hold, share)
        times = ev.times()
        if times[-1] != ev.T:
            times.append(ev.T)
        if not step_problems(ev, times):
            holds = [b - a for a, b in zip(times, times[1:])] + [J_HOLD]
            b = Bridge(ev, times, holds, path)
            b.share = share
            return b
    return None


SEG = 10                  # frames between keys while the way is laid out (re-timed by Even)


def break_bridge(src_clip, s):
    """From drawn state s (an exit) to the junction. Tries the sword's ways down in turn: straight; through the tip
    forward and down; level forward; upright before the shoulder then forward (the way he puts the sword down); the
    hand raised first - the first whose every frame passes problems(); then re-timed to an even pace (Even)."""
    k0 = jolt(key_of(s))
    turn = end_turn(s.get('ht', 0.0), src_clip.spin)
    D0 = s['D']
    flags = _flags(src_clip)
    # turned part of the way round (the ash spin): carried on round as he was, then down
    lead = [(0, k0)]
    delta = turn - s.get('ht', 0.0)
    if abs(delta) > 30.0:
        m = math.ceil(abs(delta) / 30.0)
        for j in range(1, m + 1):
            lead.append((round(SEG * abs(delta) * j / m / 60.0), yawed(k0, delta * j / m)))
        # the swing spent, the arm gives a little (at full reach the next curve would overshoot it)
        k1 = dict(lead[-1][1])
        sh = A.shoulder('R', k1)
        k1['fist'] = A.add(k1['fist'], A.mul(A.unit(A.sub(sh, k1['fist'])), 5.0))
        lead.append((lead[-1][0] + 3, k1))
    kstart = lead[-1][1]
    t = lead[-1][0]
    # the tip goes into the ground with him as low as he was hit (the sword goes in, then he goes down: animation-
    # review §4.2 "武器先到位，身體再下去")
    Da = max(4, min(D0, 18))
    tries = []
    for wps in ([], [0.2], [0.34], [0.68, 0.34], [0.68, 0.2], ['lift', 0.2], ['lift', 0.34]):
        keys = list(lead)
        tk = t
        for j, b in enumerate(wps):
            f = (j + 1) / (len(wps) + 1)
            D = round(D0 + (Da - D0) * f)
            tk += SEG
            if b == 'lift':
                # the sword hand raised first, the tip off the ground (dragged, or low)
                kl = dict(kstart)
                kl['fist'] = A.add(kstart['fist'], (0.0, 0.0, 25.0))
                keys.append((tk, kl))
                continue
            keys.append((tk, waypoint(b, D, JUNCTION['u'] * D / JUNCTION['D'] * f, turn, lx=ABOVE['lx'] * f, bow=ABOVE['bow'] * f)))
        T_a = tk + SEG
        T_j = T_a + SEG // 2
        keys += [(T_a, above_key(turn, Da)), (T_j, junction_key(turn))]
        clip = AT.Clip('bridge', keys, ground=True, lead=False, exact_cape=True, **flags)
        bad = problems(clip, T_j, T_a)
        tries.append((wps, bad[:3]))
        if bad:
            continue
        b = even_bridge(clip, T_a, T_j, HIT_HOLD, wps)
        if b:
            b.flags, b.back = flags, None
            return b
        tries[-1] = (wps, 'steps')
    raise ValueError(f'no way down from {s.get("name")} t {s["t"]}: {tries[-4:]}')


# ------------------------------------------------------------------ the stagger
class StaggerClip:
    """The jolt, then the attack's own recovery from frame te to its end run in STAGGER frames."""

    def __init__(self, src, te, t_end):
        self.src, self.te, self.t_end = src, te, t_end
        self.name = 'stagger'
        self.lead = src.lead
        self.spin = src.spin
        # the recovery's way, measured as Even measures it (every part on screen against what a pose may move; its
        # holds take no time here), run at an even pace
        self.ts, self.ls = [te], [0.0]
        prev = src.at(te)
        t = te
        while t < t_end:
            t = min(t_end, t + 0.5)
            cur = src.at(t)
            d, tp = pose_dist(prev, cur)
            self.ts.append(t)
            self.ls.append(self.ls[-1] + max(d / STEP_BODY, tp / STEP_TIP))
            prev = cur

    def src_time(self, t):
        u = min(1.0, max(0.0, (t - HIT_HOLD) / (STAGGER - 2 - HIT_HOLD)))
        want = u * self.ls[-1]
        for i in range(1, len(self.ls)):
            if self.ls[i] >= want:
                a, b = self.ls[i - 1], self.ls[i]
                f = 0.0 if b <= a else (want - a) / (b - a)
                return self.ts[i - 1] + (self.ts[i] - self.ts[i - 1]) * f
        return self.t_end

    def at(self, t):
        st = self.src.at(self.src_time(t))
        w = 1.0 - A.smooth(min(1.0, max(0.0, (t - HIT_HOLD) / 8.0)))
        for k, v in RECOIL.items():
            st[k] = st.get(k, 0.0) + v * w
        st['bow'] = max(-16.0, st['bow'])
        return st


def stagger_bridge(src_clip, te):
    """Times and holds of the stagger from frame te: a pose every 2 frames (every frame where the tip would move
    more than TIP_PER_POSE); the last, at STAGGER - 2, is the carry."""
    t_end = src_clip.keys[-1][0]
    c = StaggerClip(src_clip, te, t_end)
    times = [0]
    t = HIT_HOLD
    # a lot to do in the 0.3 s (more than 0.6 of a pose's limits a frame): a pose every frame
    step = 1 if c.ls[-1] > 0.6 * (STAGGER - 2 - HIT_HOLD) else 2
    while t < STAGGER - 2:
        times.append(t)
        t += step
    times.append(STAGGER - 2)
    dense = []
    for a, b in zip(times, times[1:]):
        dense.append(a)
        d, tp = pose_dist(c.at(a), c.at(b))
        if b - a == 2 and (tp > TIP_PER_POSE or d > STEP_BODY - 2.0):
            dense.append(a + 1)
    dense.append(times[-1])
    holds = [b - a for a, b in zip(dense, dense[1:])] + [STAGGER - dense[-1]]
    return Bridge(c, dense, holds, 'recovery')


# ------------------------------------------------------------------ the sword on his back (the king's leap)
DRAW_TIMES = (128, 132, 135, 139)      # attacks.leap_rel_keys: the drawn sword up out behind, over, upright


def within_reach(k, p, side='R', margin=2.0):
    """Point p brought in towards the key's shoulder until the arm reaches it with `margin` px to spare."""
    sh = A.shoulder(side, k)
    v = A.sub(p, sh)
    n = A.norm(v)
    lim = A.ARM - margin
    return p if n <= lim else A.add(sh, A.mul(v, lim / n))


def break_bridge_back(src_clip, s):
    """The sword slung on his back (the leap's crouch, its landing, its bounce): the hand goes back over the right
    shoulder to the hilt, draws the sword up out along its line and over to upright before the shoulder (the
    leap's own draw, attacks.leap_rel_keys), then down the way he puts it down into the ground at his side."""
    k0 = jolt(key_of(s))
    D0 = s['D']
    Da = max(4, min(D0, 18))
    leapk = dict(AT.leap_rel_keys())
    flags = _flags(src_clip)

    def body(f):
        # from how he was hit (bent, leaning, the free hand out) towards the way down
        D = round(D0 + (Da - D0) * f)
        return AT.carry_key(D=D, lx=k0['lx'] + (ABOVE['lx'] - k0['lx']) * f, bow=k0['bow'] + (ABOVE['bow'] - k0['bow']) * f,
                            bend=k0.get('bend', 0.0) * (1.0 - f), lfree=(1.0 - f) * k0.get('lfree', 0.0),
                            lhand=A.mul(k0['lhand'], 1.0 - f), arm_k=1.0 + (k0.get('arm_k', 1.0) - 1.0) * (1.0 - f),
                            feet=descent_feet(JUNCTION['u'] * D / JUNCTION['D'] * f, D) if f > 0.5 else k0['feet'])
    keys = [(0, k0)]
    t_grab = SEG
    grab = body(0.45)
    g, d, w = AT._slung(grab)
    grab.update(fist=g, dir=d, flat=w)
    keys.append((t_grab, grab))
    pull = body(0.6)
    g2, _, _ = AT._slung(pull)
    pull.update(fist=within_reach(pull, A.add(g2, (-4.0, 3.0, 10.0))), dir=d, flat=w)
    keys.append((t_grab + SEG // 2, pull))
    t = t_grab + SEG // 2
    for j, tk in enumerate(DRAW_TIMES):
        t += SEG // 2
        src = leapk[tk]
        k = body(0.65 + 0.05 * j)
        # the hand where the leap's draw has it from the shoulder, however low he is
        rel = A.sub(src['fist'], A.shoulder('R', src))
        k.update(fist=within_reach(k, A.add(A.shoulder('R', k), rel)), dir=src['dir'], roll=src.get('roll', 0.0))
        if src.get('flat'):
            k['flat'] = src['flat']
        keys.append((t, k))
    wk = waypoint(0.34, round(D0 + (Da - D0) * 0.8), JUNCTION['u'] * 0.8, lx=ABOVE['lx'] * 0.8, bow=ABOVE['bow'] * 0.8)
    T_a = t + 2 * SEG
    T_j = T_a + SEG // 2
    keys += [(t + SEG, wk), (T_a, above_key(0.0, Da)), (T_j, junction_key(0.0))]
    clip = AT.Clip('bridge', keys, ground=True, lead=False, exact_cape=True, back=(0, t_grab), **flags)
    bad = problems(clip, T_j, T_a)
    if bad:
        raise ValueError(f'no way down (sword on his back) from {s.get("name")} t {s["t"]}: {bad[:4]}')
    b = even_bridge(clip, T_a, T_j, HIT_HOLD, 'draw')
    if not b:
        raise ValueError(f'no way down (sword on his back) from {s.get("name")} t {s["t"]}: steps')
    # the hand lets go of nothing until it takes the hilt: where the even pace puts the grab
    b.grab = next(t for t in b.times if b.clip.src_time(t) >= t_grab)
    b.flags, b.back = flags, (0, t_grab)
    return b


# ------------------------------------------------------------------ covering every sheet, and keeping the plan
def cover(states, allowed, known):
    """{pose index: start} for the allowed poses: a start already made (known: [(start id, its state)]) where one is
    near enough; for the rest new exits (choose_exits). Returns (map, new exits) - map values are start ids or
    ('new', pose index)."""
    out, rest = {}, []
    for i in allowed:
        best = None
        for sid, st in known:
            d, t = pose_dist(st, states[i])
            if d <= HIT_BODY and t <= HIT_TIP:
                score = d / HIT_BODY + t / HIT_TIP
                if best is None or score < best[0]:
                    best = (score, sid)
        if best:
            out[i] = best[1]
        else:
            rest.append(i)
    exits = []
    if rest:
        exits, which = choose_exits(states, rest)
        for i in rest:
            out[i] = ('new', which[i])
    return out, exits


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [_plain(x) for x in v]
    return v


def _tuples(v):
    if isinstance(v, dict):
        return {k: _tuples(x) for k, x in v.items()}
    if isinstance(v, list):
        return tuple(_tuples(x) for x in v)
    return v


def spec(b, kind, source, pose, flags, back=None, te=None):
    """What rebuilds bridge b (json-able)."""
    if kind == 'stagger':
        return {'kind': kind, 'source': source, 'pose': pose, 'te': te}
    ev = b.clip
    return {'kind': kind, 'source': source, 'pose': pose, 'keys': [[t, _plain(k)] for t, k in ev.clip.keys],
            'flags': _plain(flags), 'back': back, 't_end': ev.t1, 'hold': ev.hold, 'share': b.share,
            'path': _plain(b.path), 'grab': getattr(b, 'grab', None)}


def from_spec(sp, src_clip=None):
    if sp['kind'] == 'stagger':
        return stagger_bridge(src_clip, sp['te'])
    keys = [(t, _tuples(k)) for t, k in sp['keys']]
    flags = {k: (tuple(v) if isinstance(v, list) else v) for k, v in sp['flags'].items()}
    back = tuple(sp['back']) if sp['back'] else None
    clip = AT.Clip('bridge', keys, ground=True, lead=False, exact_cape=True, back=back, **flags)
    ev = Even(clip, 0.0, sp['t_end'], sp['hold'], sp['share'])
    times = ev.times()
    if times[-1] != ev.T:
        times.append(ev.T)
    holds = [b - a for a, b in zip(times, times[1:])] + [J_HOLD]
    b = Bridge(ev, times, holds, sp['path'])
    b.share = sp['share']
    if sp.get('grab') is not None:
        b.grab = sp['grab']
    return b
