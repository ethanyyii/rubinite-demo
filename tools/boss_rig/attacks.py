"""The Boss's attacks as key poses in time (3D, attack3d.py) and the poses sampled from them.

A clip is a list of keys (combat frame, settings); a pose is everything at one moment:
  D      hips this far below standing (px)          hx   hips this far forward of the anchor (the
  lx     extra forward lean (degrees, - = back)          weight shifts onto the front foot)
  tw     the upper body's turn (degrees, + = towards his left: the right shoulder forward)
  bow    head down (degrees; - = up)                ck   the cape's hem swung forward (+) / back (px)
  cs     the cape swung to his right (+) / left (front and back views, px at the hem)
  fist   the right fist's centre (F, R, U)          two  1 = the left hand on the grip, 0 = it hangs
  dir    the sword's direction, (psi, el) (attack3d.direction); roll: its flat (attack3d.width),
         unless the sword is swinging: then the edge leads (the width along the way it moves)
  ht     the hips' turn (degrees, + = towards his left, like tw): the whole body turns with a
         step, not only the chest - each leg hangs from its own hip joint, HIP_HALF either side
  feet   'R' and 'L': (x forward of the anchor, out = sideways away from the centre line, z of
         the ankle, pitch) - the legs are solved from the hips to these. A key may leave a foot
         out (None): that foot is in the air between the keys either side that have it
Interpolation: Catmull-Rom through the keys for the numbers, the fist and the sword's direction
(normalised), so a stroke runs on through its keys without stopping; a key repeated holds still.
Each foot has its own track (the keys that give it): it moves from one of its keys to the next
(eased), lifted on the way when it goes further than a few px - so one step can span several of
the body's keys (user 2026-10-01: one foot at a time, the step lands with the blow).

Timing comes from the game (veltharis_data.gd; the art follows the hit boxes): see each clip.
"""
import math
import attack3d as A
import carry
import gait

# ------------------------------------------------------------------ the carry (start and end of every attack)
CARRY_FIST = carry.FIST
CARRY_DIR = A.angles(carry.pose3(1.0)[0])          # (162, 6)
STAND_FOOT = (0.0, 0.0, gait.ANKLE_H, 0.0)


def carry_key(**kw):
    k = dict(D=0, hx=0.0, ht=0.0, lx=0.0, tw=0.0, bow=0.0, ck=0.0, cs=0.0, fist=CARRY_FIST, dir=CARRY_DIR,
             roll=0.0, two=0.0, lfree=0.0, lhand=(0.0, 0.0, 0.0), swing=0.0, arm_k=1.0, shrug=0.0, draw_in=0.0,
             feet={'R': STAND_FOOT, 'L': STAND_FOOT})
    k.update(kw)
    return k


def boot_drop(pitch):
    import anim_kneel
    return anim_kneel.boot_drop(pitch)


SCALARS = ('D', 'hx', 'ht', 'lx', 'tw', 'bow', 'ck', 'cs', 'roll', 'two', 'lfree', 'swing', 'arm_k', 'shrug', 'draw_in',
           'glow', 'bend', 'lgrab', 'lift')
# arm_k, shrug, draw_in: the cleave's arms over the head (attack3d.arm_lengths, _girdle); glow: the
# helmet's cross lit red (the ash impact, anim_attack.glow_head); bend: bent forward at the waist (the
# judgment thrust, attack3d.bend_point); lgrab: the free left hand takes the grip from where it swings
# (the upswing, attack3d.fists); the defaults draw every other attack exactly as before
# lift: the whole man off the ground (the king's leap, px; attack3d.shoulder, anim_attack.render_pose)
SCALAR_DEFAULT = {'arm_k': 1.0}
CLAMP01 = ('two', 'lfree', 'swing', 'glow', 'lgrab')


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


HIP_HALF = 17.0          # each hip joint this far from the centre line (anim_walk.HIP_HALF)
LEG_TURN_MAX = 22.0      # the whole-body turn: the legs' hip joints turn this far at most (hip_x)


def hip_x(st, side_):
    """How far forward of the anchor a leg's hip joint is: the hips' hx, and the hips' turn ht
    bringing the right hip forward (+) and the left back (the turn as the yaw of attack3d)."""
    sgn = 1.0 if side_ == 'R' else -1.0
    ht = st.get('ht', 0.0)
    if st.get('whole_turn'):
        ht = (ht + 180.0) % 360.0 - 180.0          # turned whole circles (the ash spin): the same hips
        # the legs are solved in the side plane (a knee always bends forward): turned further
        # than this the back hip comes over the back foot and both knees fold forward - he looks
        # as if he sits down. The rest of the turn shows in the front / back hips, the lean, the
        # arms; the leg geometry turns as far as the two-handed swing's
        ht = max(-LEG_TURN_MAX, min(LEG_TURN_MAX, ht))
    return st['hx'] + sgn * HIP_HALF * math.sin(math.radians(ht))


class Clip:
    """keys: [(frame, settings)], frame 0 first. at(t) -> the pose at combat frame t. Each
    foot's track is the keys that give it (a key's feet may leave one out, or give None)."""

    def __init__(self, name, keys, steps=None, advance=None, musts=(), whole_turn=False, still=False, ground=False,
                 lead=True, tall=False, flashes=(), spin=False, back=None, exact_cape=False, upwrap=False,
                 behind=None, left_own=False):
        """steps: {'R': [(frame, foot)], ...} - foot keys between the body's keys (where a step
        leaves the ground or lands). advance: combat frame -> px the game has moved the Boss
        forward since the move started (the twin slash's step before its second hit,
        veltharis_data TWIN_STEP_DISTANCE); the keys are then in the ground's (world)
        coordinates and at() gives everything relative to where the game has the Boss, which is
        what the sprite is drawn about. musts: frames that must each be a pose of their own (the
        game moves the Boss every frame there: a pose held longer would carry the planted foot
        along)."""
        self.name = name
        self.keys = keys
        self.adv = advance or (lambda t: 0.0)
        self.musts = tuple(musts)
        self.whole_turn = whole_turn      # front / back views draw the hips' turn too (anim_attack.front_back)
        # still: the fists, the sword's direction and the elbows hold between two equal keys too
        # (the scalars always do). The cleave's sword stuck in the ground must not drift while the
        # curve through the keys either side bends past it (animation-review §4.3: a weapon in
        # the ground does not move); the earlier clips are drawn without it, unchanged
        self.still = still
        # ground: the blade may go into the ground (what is below it is not drawn); lead False: the
        # keys' flat all through, even swinging fast (widths()). Either may be a frame: from there on
        # (ground) / before it (lead) - the triple slash's twin-slash part is drawn as the twin slash
        self.ground = ground
        self.lead = lead
        # tall: the sword is drawn on the cleave's taller canvas all through (anim_attack.sword_canvas:
        # raised over his head the blade reaches above the attack container)
        self.tall = tall
        # flashes: the frames the helmet's cross flashes at (its brightness from flash_level, not the keys)
        self.flashes = tuple(flashes)
        # spin: the whole body may turn right round (the ash spin): each view draws it with the facing it is
        # nearest (anim_attack.render_spun)
        self.spin = spin
        # back: (from, to) frames the sword is slung on his back and the right hand is free (the king's leap)
        self.back = back
        # exact_cape: the side view's cape crouched deeper than anim_attack.CAPE_EXACT_D solved right (the
        # judgment thrust's is drawn as approved)
        self.exact_cape = exact_cape
        # upwrap: the side views' shoulder plate turn wraps at the arm straight up (anim_attack.plate_turn; the leap)
        self.upwrap = upwrap
        # left_own: the arms drawn longer (arm_k) is the right arm only; the left keeps its length (attack3d.arm_scale; the
        # leap's blow is the right fist's)
        self.left_own = left_own
        # behind: (from, to) frames the free arms swing right back behind him: the front view draws what of them is
        # behind his back behind him, the back view over the slung sword (anim_attack.front_back; the leap's wind-up)
        self.behind = behind
        self.tracks = {}
        for s in 'RL':
            tr = {t: k['feet'][s] for t, k in keys if k['feet'].get(s) is not None}
            tr.update(dict((steps or {}).get(s, ())))
            self.tracks[s] = sorted(tr.items())

    def _seg(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return 0, 0.0
        for i in range(len(ks) - 1):
            if t <= ks[i + 1][0]:
                return i, (t - ks[i][0]) / (ks[i + 1][0] - ks[i][0])
        return len(ks) - 2, 1.0

    def _four(self, i):
        ks = self.keys
        return [ks[max(0, min(len(ks) - 1, j))][1] for j in (i - 1, i, i + 1, i + 2)]

    def at(self, t):
        i, u = self._seg(t)
        K4 = self._four(i)
        out = {}
        for k in SCALARS:
            dv = SCALAR_DEFAULT.get(k, 0.0)
            if K4[1].get(k, dv) == K4[2].get(k, dv):
                v = K4[1].get(k, dv)          # a value held between two keys stays put (no overshoot past it)
            else:
                v = _catmull(*[(kk.get(k, dv),) for kk in K4], u)[0]
            if k in CLAMP01:
                v = min(1.0, max(0.0, v))
            out[k] = v
        out['D'] = round(out['D'])          # whole pixels (animation-review §4.4: half-pixel heights re-sample the trim)
        def held(k):
            """The four keys for field k: under `still`, two equal keys either side hold it."""
            if self.still and K4[1].get(k) == K4[2].get(k):
                return [K4[1]] * 4
            return K4
        out['fist'] = _catmull(*[kk['fist'] for kk in held('fist')], u)
        out['lhand'] = _catmull(*[kk['lhand'] for kk in held('lhand')], u)
        dirs = [A.direction(*kk['dir']) for kk in held('dir')]
        out['axis'] = A.unit(_catmull(*dirs, u))
        # the flat: each key's width (its 'flat' hint, or its roll), interpolated, then made
        # square to the blade
        flats = [kk.get('flat') or A.width(A.direction(*kk['dir']), kk['roll']) for kk in K4]
        flats = [f if A.dot(f, flats[1]) >= 0 else A.mul(f, -1) for f in flats]
        f = _catmull(*flats, u)
        a = out['axis']
        f = A.sub(f, A.mul(a, A.dot(f, a)))
        out['flat'] = A.unit(f) if A.norm(f) > 1e-6 else A.width(a, out['roll'])
        # where the elbows point (attack3d.POLE by default)
        for k in ('poleR', 'poleL'):
            ps = [kk.get(k) or A.POLE[k[-1]] for kk in K4]
            out[k] = A.unit(_catmull(*ps, u))
        out['feet'] = {s: self._foot(s, t) for s in 'RL'}
        # world -> where the game has the Boss
        a = self.adv(t)
        if a:
            out['hx'] -= a
            out['fist'] = (out['fist'][0] - a,) + tuple(out['fist'][1:])
            out['feet'] = {k: (f[0] - a,) + tuple(f[1:]) for k, f in out['feet'].items()}
        out['adv'] = a
        out['t'] = t
        out['whole_turn'] = self.whole_turn
        if self.tall:
            out['tall'] = True
        if self.spin:
            out['spin'] = True
        if self.back and self.back[0] <= t < self.back[1]:
            out['back'] = True
        if self.behind and self.behind[0] <= t < self.behind[1]:
            out['arms_behind'] = True
        if self.left_own:
            out['left_own'] = True
        if self.exact_cape:
            out['exact_cape'] = True
        if self.upwrap:
            out['upwrap'] = True
        if self.flashes:
            out['glow'] = flash_level(t, self.flashes)
        if self.ground is True or (self.ground is not False and t >= self.ground):
            # the blade may go into the ground; and the cleave bends over far (30 degrees, the hips
            # 16 px down): the front / back views draw each layer further from where it stands
            # (anim_attack: WHOLE_PAD, as the one-handed slashes)
            out['ground'] = True
            out['deep'] = True
        return out

    def _foot(self, s, t):
        tr = self.tracks[s]
        if t <= tr[0][0]:
            j, u = 0, 0.0
        elif t >= tr[-1][0]:
            j, u = max(0, len(tr) - 2), 1.0
        else:
            j = max(i for i in range(len(tr)) if tr[i][0] <= t)
            u = (t - tr[j][0]) / (tr[j + 1][0] - tr[j][0])
        a = tr[j][1]
        b = tr[j + 1][1] if len(tr) > 1 else a
        w = gait.smooth(u)
        x, out, z, pitch = (a[c] + (b[c] - a[c]) * w for c in range(4))
        far = math.hypot(b[0] - a[0], b[1] - a[1]) > 6.0
        if far:
            z += 7.0 * math.sin(math.pi * u)          # a step: the foot is lifted on the way
        # a heel coming up pivots on the toe: the ankle rises so the toe stays on the ground
        z = max(z, boot_drop(pitch))
        return (x, out, z, pitch, not far or u in (0.0, 1.0))


SLOW, FAST = 0.04, 0.10      # radians a frame: below SLOW the keys' flat, above FAST the edge leads
FLAT_R = A.unit((1.0, 1.0, 0.0))     # held up beside the right shoulder: the flat turned half-way between
FLAT_L = A.unit((1.0, -1.0, 0.0))    # forward and outward (as the concept holds it standing), seen in all four views


def widths(clip, times):
    """The sword's width direction at each of `times`: while it swings fast the edge leads
    (the width along the way the blade moves); slow or still, the keys' roll."""
    out = []
    for t in times:
        s = clip.at(t)
        a = s['axis']
        w0 = s['flat']
        a1, a2 = clip.at(t - 1)['axis'], clip.at(t + 1)['axis']
        mv = A.sub(a2, a1)
        mv = A.sub(mv, A.mul(a, A.dot(mv, a)))
        speed = A.norm(mv) / 2          # radians per frame
        lead = clip.lead if isinstance(clip.lead, bool) else t < clip.lead
        if speed > 1e-4 and lead:
            w1 = A.unit(mv)
            if A.dot(w1, w0) < 0:
                w1 = A.mul(w1, -1)
            k = min(1.0, max(0.0, (speed - SLOW) / (FAST - SLOW)))     # the edge leads only in a stroke
            w = A.unit(A.lerp(w0, w1, k))
        else:
            w = w0
        out.append(w)
    return out


def poses(clip, times):
    """The states at `times` (combat frames), with the sword's width (widths()), ready to draw."""
    ws = widths(clip, times)
    out = []
    for i, (t, w) in enumerate(zip(times, ws)):
        s = clip.at(t)
        s['w3'] = w
        s['name'] = clip.name
        s['i'] = i
        out.append(s)
    return out


# ------------------------------------------------------------------ C1 王權橫掃 (royal sweep), two hands
# veltharis_data: _sweep_hit 起手 0.8 (48 frames) -> 判定 0.15 (9) -> 收招 0.9 (54; 二階段 x0.75);
# the twin slash's first hit: 起手 48, 判定 6, then C2. Sector 150 degrees in front, radius 155.
#
# With the right fist high on the grip by the pommel and the left just above the guard (the
# user's grip), the sword is raised beside the right shoulder, blade back and up over it (where
# the carry already has it), and comes down across his front in a falling sweep to knee height
# in front of him, on round to his left.
#
# The feet (user 2026-10-01: "the Boss looks like he jumps: the left foot goes forward and the
# right back before the swing ... the sword goes from the right shoulder towards the left foot,
# so only step out the right foot as he swings, the whole body turning a little with it; for
# the second cut the right foot goes back and the left steps out"): the windup is the upper
# body's alone - both feet stay where the carry has them, the hips hardly move. The right foot
# leaves the ground as the sword comes down (STEP_FROM) and lands with the blow (the hit box's
# middle); the hips go forward onto it and turn with it (ht). One foot at a time.
W = 48            # first frame of the hit box
STEP_FROM = 44    # the stepping foot leaves the ground (the stroke starts after frame 40)
# User 2026-10-01 (after the third version): "as he swings the upper body must go further
# forward, the weight further forward - now even with the step the weight feels in the middle;
# the weight should go forward with the step, and leaning the upper body forward lets the sword
# go lower and reach further, so it more easily reaches the player's height". So the step is a
# lunge, longer than a walking step's half (the walk's feet are 24 px either side of the hips):
# the front foot lands 36 px ahead, the hips go two thirds of the way onto it, the chest leans
# 20 degrees over the front knee, and at the blow the tip is at the hit box's edge (155) and
# below the player's height (40 px up).
RF = (36.0, -2.0, gait.ANKLE_H, 0.0)      # the right foot stepped in with the royal sweep (a little in, towards the cut's line)
# The twin slash: the first cut is the quick one (a hit box a third shorter), a shorter step;
# the right foot stays there (user 2026-10-01: "for the second cut just step the left foot
# straight forward, don't bring the right foot back - the price is that the Boss moves forward a
# little over the two cuts, I accept that, the game has to change too"). The game moves him
# forward TWIN_STEP before the second hit box (veltharis_data TWIN_STEP_DISTANCE, the same
# number): after it the right foot is where the game has him and the left foot steps out ahead,
# a lunge from there as long as the royal sweep's (the finisher).
TWIN_STEP = 28.0
TWIN_STEP_FRAMES = 12                     # veltharis_data TWIN_STEP_TIME 0.2 s
RF_QUICK = (TWIN_STEP, 0.0, gait.ANKLE_H, 0.0)
LF = (36.0, -2.0, gait.ANKLE_H, 0.0)      # the left foot stepped in with the second cut (from where the game has him)
STAND = STAND_FOOT


def with_poles(keys, table):
    """Set where the elbows point (poleR, poleL: 3D directions, attack3d.solve_arm) at the keys'
    frames: {frame: (poleR, poleL)}. User 2026-10-01: "the shoulders do not carry the upper arms
    round, only the forearms swing" - with every elbow bending down (the default) the upper arms
    stayed under the shoulder plates or pointed at the camera; each pose now says where its
    elbows go (raised out to the side with the sword up by the shoulder, across the chest, out
    behind on the follow-through) so the upper arms swing with the stroke."""
    out = []
    for t, k in keys:
        if t in table:
            k = dict(k)
            k['poleR'], k['poleL'] = table[t]
        out.append((t, k))
    return out


OUT_R, OUT_L = (-0.2, 1.0, 0.25), (-0.2, -1.0, 0.25)          # elbow raised out to its side, level
ACROSS_R, ACROSS_L = (1.0, -0.1, -0.2), (1.0, 0.1, -0.2)      # elbow forward, the arm across the chest
DOWN_R, DOWN_L = (0.0, 0.6, -1.0), (0.0, -0.6, -1.0)          # arms reaching forward: elbows down and out
BEHIND_R, BEHIND_L = (-0.5, 1.0, -0.2), (-0.5, -1.0, -0.2)    # elbow out behind (the follow-through's bent arm)
CROSS_R, CROSS_L = (0.5, 0.0, -1.0), (0.5, 0.0, -1.0)         # the straight arm across the body
RISE_R, RISE_L = (0.0, 1.0, -0.8), (0.0, -1.0, -0.8)          # lifting the sword in front: elbows down and out
POLES_C1 = {
    8: ((0.1, 1.0, -0.4), (1.0, 0.3, -0.6)),
    24: (OUT_R, ACROSS_L), 40: (OUT_R, ACROSS_L),
    46: ((0.0, 1.0, -0.2), (1.0, -0.1, -0.6)),
    48: ((0.1, 1.0, -0.6), (0.6, -0.5, -1.0)),
    51: (DOWN_R, DOWN_L), 52: (DOWN_R, DOWN_L),
    53: ((0.4, 0.3, -1.0), (-0.3, -1.0, -0.6)), 55: ((0.4, 0.3, -1.0), (-0.3, -1.0, -0.6)),
    54: (CROSS_R, BEHIND_L), 58: (CROSS_R, BEHIND_L), 64: (CROSS_R, BEHIND_L), 76: (CROSS_R, BEHIND_L),
    86: (RISE_R, RISE_L),
    94: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)),
}


def c1_windup():
    """Carry -> cocked (frames 0 .. 46): shared by the royal sweep and the twin slash. The feet
    stay; the upper body turns to his right and the sword goes up beside the right shoulder; the
    hips sink a little (3 px, the knees giving) and the weight settles back (1.5 px)."""
    k = []
    k.append((0, carry_key()))
    # the left hand comes up to the grip; the hands come in from the shoulder
    k.append((8, carry_key(D=1, tw=-16, lx=-1, fist=(13.0, 11.0, 127.0), dir=(156.0, 22.0), two=0.7, bow=-3, flat=FLAT_R)))
    # cocked: turned to his right, the weight back, the sword raised beside his right shoulder,
    # blade back and up over it
    k.append((24, carry_key(D=3, hx=-1.0, tw=-36, lx=-4, fist=(8.0, 8.0, 121.0), dir=(150.0, 54.0), two=1.0, flat=FLAT_R,
                            bow=2, ck=-2, cs=-3)))
    k.append((40, carry_key(D=3, hx=-1.5, tw=-40, lx=-5, fist=(7.0, 8.0, 122.0), dir=(152.0, 58.0), two=1.0, flat=FLAT_R,
                            bow=3, ck=-3, cs=-4)))
    # the stroke starts; the right foot is off the ground (STEP_FROM) and on its way forward
    k.append((46, carry_key(D=4, hx=2.5, tw=-30, lx=0, fist=(15.0, 7.0, 116.0), dir=(118.0, 26.0), two=1.0,
                            bow=4, ck=-2, cs=-3, feet={'R': None, 'L': STAND})))
    return k


def c1_sweep(active):
    """The sweep from W: down across his front to below the player's height in front of him, the
    right foot landing with the blow, the weight going onto it, the hips turning to his left
    with it and the chest leaning in over the front knee. `active` frames of hit box (9 the
    royal sweep, 6 the twin slash): the sword crosses the 150-degree sector in front of him in
    that time."""
    f = active / 9.0
    in_air = {'R': None, 'L': STAND}
    if active == 9:
        planted = {'R': RF, 'L': STAND}
        hx, D, lx, ht = (9.5, 24.0, 25.0, 24.5), (7, 11, 11, 11), (9, 20, 18, 16), (6, 16, 19, 21)
        fists = ((28.0, 5.0, 104.0), (52.0, -2.0, 84.0), (42.0, -16.0, 84.0), (34.0, -21.0, 84.0))
        els = (3.0, -26.0, -31.0, -28.0)
    else:
        # the twin slash's first cut: the quick one, a shorter step and the hips less far
        planted = {'R': RF_QUICK, 'L': STAND}
        hx, D, lx, ht = (9.0, 20.5, 21.0, 20.0), (7, 10, 10, 10), (8, 20, 17, 15), (6, 14, 18, 20)
        fists = ((27.0, 5.0, 104.0), (49.0, -2.0, 85.0), (38.0, -15.0, 85.0), (30.0, -20.0, 85.0))
        els = (3.0, -25.0, -30.0, -27.0)
    return [
        (W, carry_key(D=D[0], hx=hx[0], ht=ht[0], tw=-12, lx=lx[0], fist=fists[0], dir=(78.0, els[0]), two=1.0,
                      bow=6, ck=-1, cs=-1, feet=in_air)),
        (W + round(4 * f), carry_key(D=D[1], hx=hx[1], ht=ht[1], tw=4, lx=lx[1], fist=fists[1], dir=(0.0, els[1]),
                                     two=1.0, bow=9, ck=2, cs=2, feet=planted)),
        (W + round(7 * f), carry_key(D=D[2], hx=hx[2], ht=ht[2], tw=26, lx=lx[2], fist=fists[2], dir=(-70.0, els[2]),
                                     two=1.0, bow=8, ck=3, cs=5, feet=planted)),
        (W + round(10 * f), carry_key(D=D[3], hx=hx[3], ht=ht[3], tw=36, lx=lx[3], fist=fists[3], dir=(-110.0, els[3]),
                                      two=1.0, bow=7, ck=3, cs=6, feet=planted)),
    ]


def c1_steps(contact, foot=RF):
    return {'R': [(STEP_FROM, STAND), (contact, foot)]}


def c1_keys():
    k = c1_windup() + c1_sweep(9)
    planted = {'R': RF, 'L': STAND}
    # follow-through: carried on, slowing; held over the front knee (the long recovery is the opening)
    k.append((W + 16, carry_key(D=11, hx=24.0, ht=21, tw=40, lx=15, fist=(32.0, -21.0, 86.0), dir=(-128.0, -26.0), two=1.0,
                                bow=7, ck=1, cs=4, feet=planted)))
    k.append((W + 28, carry_key(D=10, hx=23.0, ht=19, tw=38, lx=14, fist=(32.0, -20.0, 87.0), dir=(-126.0, -24.0), two=1.0,
                                bow=5, ck=0, cs=2, feet=planted)))
    # recovery: the weight goes back onto the left foot, the sword is lifted in front of him,
    # upright before his right shoulder, and laid back on it (the way the walk's start clip
    # puts it there); the right foot comes back (C1_BACK); the left hand lets go
    k.append((W + 38, carry_key(D=7, hx=12.0, ht=8, tw=16, lx=4, fist=(26.0, -2.0, 106.0), dir=(-50.0, 30.0), two=1.0,
                                roll=80.0, feet=planted)))
    k.append((W + 46, carry_key(D=3, hx=2.0, ht=2, tw=4, lx=1, fist=(21.0, 12.0, 122.0), dir=(-18.0, 80.0), two=0.5,
                                flat=FLAT_R, feet={'R': None, 'L': STAND})))
    k.append((W + 54, carry_key(D=1, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), two=0.0, roll=30.0)))
    k.append((W + 60, carry_key()))
    return k


C1_BACK = (W + 38, W + 50)        # the right foot steps back under him


def c1():
    """王權橫掃: windup 48, hit 9 (frames 48 .. 56), recovery 54 -> 111 frames."""
    st = c1_steps(W + 4)
    st['R'] += [(C1_BACK[0], RF), (C1_BACK[1], STAND)]
    return Clip('c1', with_poles(c1_keys(), POLES_C1), st)


# ------------------------------------------------------------------ C2 反手橫斬 (the twin slash's second hit)
# veltharis_data: _twin_first 起手 48, 判定 6; _twin_second 0.9 s (54 frames) after the first hit
# starts, 判定 6, then 收招 1.0 (60). The sword is on his left after the first hit: it is raised
# beside his left shoulder (with the left hand by the guard, his natural side) and comes back
# across his front, left to right, falling below the player's height in front of him.
# The feet (user 2026-10-01: "for the second cut just step the left foot straight forward, don't
# bring the right foot back"): the right foot stays where the first cut put it (RF_QUICK) and
# takes his weight while the sword goes up on his left; the left foot steps straight through,
# past it, and lands with the blow (frame 105), the hips going onto it and turning to his right.
# The game moves him forward TWIN_STEP in the 12 frames before the hit box (TWIN_STEP_FROM ..
# W2 - 1; veltharis_data TWIN_STEP_DISTANCE / TWIN_STEP_TIME): the keys are in the ground's
# (world) coordinates, the clip draws them about where the game has him (Clip.advance). After
# the step the right foot is just where the game has him - the second cut is the first cut's
# lunge mirrored, from there; in the recovery the left foot comes back beside the right.
W2 = W + 54        # the second hit box
TWIN_STEP_FROM = W2 - TWIN_STEP_FRAMES    # the game's step: frames 90 .. 101
TWIN_STEP2 = W2 - 6                       # the left foot leaves the ground
TWIN_END = (W2 + 40, W2 + 52)             # the left foot comes back beside the right


def twin_advance(t):
    """px the game has moved the Boss forward at combat frame t (after that frame's update:
    boss_sim moves TWIN_STEP / TWIN_STEP_FRAMES a frame from TWIN_STEP_FROM on)."""
    return TWIN_STEP * min(1.0, max(0.0, (t - TWIN_STEP_FROM + 1) / TWIN_STEP_FRAMES))


def ahead(t, k, dx=TWIN_STEP):
    """A key written about where the game has him after the step, put on the ground (world):
    the hips, the fist and the feet dx further forward."""
    k = dict(k)
    k['hx'] = k['hx'] + dx
    k['fist'] = (k['fist'][0] + dx,) + tuple(k['fist'][1:])
    k['feet'] = {s_: (None if f is None else (f[0] + dx,) + tuple(f[1:])) for s_, f in k['feet'].items()}
    return t, k


def twin_keys():
    k = c1_windup() + c1_sweep(6)
    planted = {'R': RF_QUICK, 'L': STAND}
    # carried on round to his left, slowing, the weight staying on the right foot (it does not
    # come back); the sword comes up in front of him (tip forward and up), stands upright
    # before his left shoulder and is laid back over it - cocked on his left, the way it came
    # off the right shoulder for the first hit, mirrored (straight up past the side would drive
    # the blade through the shoulder plate). The hips stay over the right foot, ready to step
    # through
    k.append((W + 12, carry_key(D=10, hx=19.0, ht=20, tw=40, lx=13, fist=(28.0, -20.0, 86.0), dir=(-126.0, -23.0), two=1.0,
                                bow=6, ck=2, cs=5, feet=planted)))
    k.append((W + 21, carry_key(D=9, hx=20.0, ht=14, tw=34, lx=6, fist=(33.0, -10.0, 106.0), dir=(-62.0, 28.0), two=1.0,
                                roll=80.0, bow=4, ck=0, cs=4, feet=planted)))
    k.append((W + 28, carry_key(D=8, hx=20.5, ht=12, tw=38, lx=2, fist=(33.0, -8.0, 118.0), dir=(-100.0, 78.0), two=1.0,
                                flat=FLAT_L, bow=2, ck=-1, cs=3, feet=planted)))
    k.append((W + 36, carry_key(D=8, hx=21.0, ht=12, tw=40, lx=-2, fist=(31.0, -8.0, 121.0), dir=(-150.0, 40.0), two=1.0,
                                flat=FLAT_L, bow=2, ck=-2, cs=3, feet=planted)))
    k.append((W + 46, carry_key(D=8, hx=22.0, ht=12, tw=44, lx=-3, fist=(31.0, -8.0, 122.0), dir=(-152.0, 44.0), two=1.0,
                                flat=FLAT_L, bow=3, ck=-3, cs=4, feet=planted)))
    # the second stroke: the left foot is off the ground (TWIN_STEP2) and steps through, landing
    # with the blow; past his front the left hand lets go (it cannot follow the grip round to his
    # right) and the right carries the sword on. From here on: about where the game has him after
    # its step (ahead())
    in_air = {'R': STAND, 'L': None}
    planted = {'R': STAND, 'L': LF}
    k.append(ahead(W + 51, carry_key(D=8, hx=2.0, ht=4, tw=32, lx=4, fist=(17.0, -7.0, 116.0), dir=(-120.0, 26.0), two=1.0,
                                     bow=4, ck=-2, cs=3, feet=in_air)))
    k.append(ahead(W2, carry_key(D=8, hx=12.0, ht=-4, tw=14, lx=9, fist=(28.0, -5.0, 104.0), dir=(-78.0, 3.0), two=1.0,
                                 bow=6, ck=-1, cs=1, feet=in_air)))
    k.append(ahead(W2 + 3, carry_key(D=11, hx=24.0, ht=-16, tw=-4, lx=20, fist=(52.0, 2.0, 84.0), dir=(0.0, -26.0), two=1.0,
                                     bow=9, ck=2, cs=-2, feet=planted)))
    k.append(ahead(W2 + 5, carry_key(D=11, hx=25.0, ht=-19, tw=-20, lx=18, fist=(38.0, 12.0, 85.0), dir=(66.0, -31.0), two=0.55,
                                     bow=8, ck=3, cs=-5, feet=planted)))
    k.append(ahead(W2 + 8, carry_key(D=11, hx=24.5, ht=-21, tw=-30, lx=16, fist=(34.0, 20.0, 84.0), dir=(104.0, -28.0), two=0.0,
                                     bow=7, ck=3, cs=-6, feet=planted)))
    # follow-through, held over the front knee; then the weight comes back onto the right foot,
    # the right hand lifts the sword onto the shoulder (up beside the plate first, the blade out
    # past it, then turned back over it) and the left foot comes back beside the right (TWIN_END)
    k.append(ahead(W2 + 14, carry_key(D=11, hx=24.0, ht=-21, tw=-34, lx=15, fist=(30.0, 24.0, 86.0), dir=(118.0, -25.0), two=0.0,
                                      bow=6, ck=1, cs=-4, feet=planted)))
    k.append(ahead(W2 + 30, carry_key(D=10, hx=23.0, ht=-19, tw=-32, lx=14, fist=(30.0, 24.0, 87.0), dir=(120.0, -23.0), two=0.0,
                                      bow=4, ck=0, cs=-2, feet=planted)))
    k.append(ahead(W2 + 40, carry_key(D=7, hx=12.0, ht=-8, tw=-16, lx=4, fist=(28.0, 27.0, 116.0), dir=(112.0, 10.0), two=0.0,
                                      feet=planted)))
    k.append(ahead(W2 + 48, carry_key(D=2, hx=2.0, ht=-2, tw=-6, fist=(19.0, 25.0, 134.0), dir=(135.0, 8.0), two=0.0,
                                      feet={'R': STAND, 'L': None})))
    k.append(ahead(W2 + 56, carry_key(D=1, fist=(16.0, 23.5, 135.0), dir=(156.0, 6.0), two=0.0)))      # straightening last, the hips square
    k.append(ahead(W2 + 62, carry_key()))
    return k


def twin_steps():
    st = c1_steps(W + 3, RF_QUICK)
    st['L'] = [(TWIN_STEP2, STAND), (W2 + 3, ahead(0, carry_key(feet={'R': STAND, 'L': LF}))[1]['feet']['L']),
               (TWIN_END[0], (LF[0] + TWIN_STEP,) + LF[1:]), (TWIN_END[1], (TWIN_STEP,) + STAND[1:])]
    return st


POLES_TWIN = {
    8: POLES_C1[8], 24: POLES_C1[24], 40: POLES_C1[40], 46: POLES_C1[46], 48: POLES_C1[48],
    51: (DOWN_R, DOWN_L), 53: POLES_C1[53], 55: POLES_C1[55],
    60: (CROSS_R, BEHIND_L),
    69: (RISE_R, RISE_L),
    76: ((0.6, 0.4, -1.0), (-0.1, -1.0, -0.6)),
    84: (ACROSS_R, OUT_L), 94: (ACROSS_R, OUT_L),
    99: ((1.0, 0.1, -0.6), (0.0, -1.0, -0.2)),
    102: ((0.6, 0.5, -1.0), (0.1, -1.0, -0.6)),
    105: (DOWN_R, DOWN_L),
    107: ((-0.2, 1.0, -0.5), (0.3, 0.3, -1.0)),
    110: ((-0.3, 1.0, -0.4), None), 116: ((-0.3, 1.0, -0.4), None), 132: ((-0.3, 1.0, -0.4), None),
    142: ((-0.2, 1.0, -0.5), None), 150: ((-0.2, 1.0, -0.5), None),
}


def twin():
    """雙斬: C1 (windup 48, hit 6: 48 .. 53) then C2 (hit 102 .. 107), recovery 60 -> 168 frames;
    the game steps him forward TWIN_STEP before the second hit box."""
    return Clip('twin', with_poles(twin_keys(), POLES_TWIN), twin_steps(), advance=twin_advance,
                musts=range(TWIN_STEP_FROM, W2))


# ------------------------------------------------------------------ 快斬連段: the two one-handed quick slashes
# veltharis_data quick_combo_2 / _3: _quick_light 起手 0.4 s (24 frames), 判定 0.1 (6); the second
# 0.6 s (36) after the first starts, 判定 6; quick_combo_2 then 收招 0.9 (54; 二階段 x0.75 -> 41),
# 120 frames. quick_combo_3's third hit (C5 上挑, 0.8 s after the second) is not drawn yet: up to
# the second hit box's end the two versions are the same frames. Sector 150 degrees, radius 155.
#
# User 2026-10-02: "the first cut sweeps from right to left, the second from left to right
# ('橫掃': a level sweep), and mind the weight - swinging the first cut the body turns much more
# than with two hands, the whole body turns". One-handed (user 2026-09-30: light attacks one
# hand): nothing holds the swing back, so the hips (ht up to 44 degrees; the royal sweep 21) and
# the chest (tw -55 -> +80; the royal sweep -40 -> +40) turn round together, the lean goes the way
# the body faces (Clip(whole_turn=True): attack3d.lean_heading, and the front / back views turn
# the hips too), the free left arm swings with it (lfree, lhand: forward across him in the
# windup, flung back to his left on the forehand, out to his left on the backhand), the back heel
# comes up and pivots on the ball (the toe stays down).
#   - the cut is level: through the sector the blade slopes down from the fist at the same angle
#     (el -24 .. -28), so the tip runs round at 31 .. 42 px (the player is 40), not the royal
#     sweep's falling diagonal
#   - the forehand: cocked with the blade straight back past his right side (seen from the side
#     it reads as drawn back, not hanging by the leg), the right foot steps in with it (a light
#     cut, a shorter lunge: QUICK_STEP) and lands with the blow; carried on round to his left
#   - the backhand: the follow-through runs on into the backhand's load (the chest already turned
#     to his left, the right shoulder towards the target - the way a one-handed backhand is
#     loaded); the weight rocks back onto the left foot, then the right foot steps on another 12
#     px and out to his right, landing with the blow (the right side leads a one-handed backhand).
#     He does not move forward (the handoff: the game would have to move him for the back foot
#     to step through; that was not asked for - the user can choose it)
Q1 = 24            # the first hit box (24 .. 29)
Q2 = Q1 + 36       # the second (60 .. 65)
QUICK_END = Q2 + 6 + 54
QUICK_STEP_FROM = 19
RQ1 = (24.0, -4.0, gait.ANKLE_H, 0.0)     # the right foot stepped in with the forehand (in: across, towards the cut's line)
RQ2 = (36.0, 5.0, gait.ANKLE_H, 0.0)      # ... on further with the backhand, and out towards where it sweeps
LBALL = (0.0, 0.0, gait.ANKLE_H, -20.0)   # the back foot's heel up, pivoting on the ball
LBALL2 = (0.0, 0.0, gait.ANKLE_H, -14.0)
QUICK_BACK = (88, 100)                    # the right foot comes back under him
QUICK_ENTRY = ((0, 3, 6, 9), 6, 12)       # starting from a move: times, first foot under him, second (the windup is 24)


def quick_keys():
    k = []
    air = {'R': None, 'L': STAND}
    p1 = {'R': RQ1, 'L': LBALL}
    k.append((0, carry_key()))
    # the knees give before the hips turn (a turned hip over a straight leg would stretch it)
    k.append((3, carry_key(D=1, tw=-6, lx=0.3, fist=(12.0, 27.0, 132.0), dir=(157.0, 10.0), flat=FLAT_R,
                           lfree=0.25, lhand=(3.0, 3.0, 4.0))))
    # the sword off the shoulder, out and back past his right side; the left hand comes up
    k.append((6, carry_key(D=1, tw=-20, ht=-4, lx=1, fist=(8.0, 32.0, 130.0), dir=(152.0, 14.0), flat=FLAT_R,
                           lfree=0.6, lhand=(8.0, 8.0, 10.0), bow=-2)))
    # cocked: hips and chest turned to his right, the blade straight back level past his right
    # side, the left hand forward across him
    k.append((14, carry_key(D=3, hx=-1.5, tw=-55, ht=-12, lx=4, fist=(-10.0, 40.0, 112.0), dir=(142.0, -6.0), flat=FLAT_R,
                            lfree=1.0, lhand=(20.0, 18.0, 24.0), bow=2, ck=-3, cs=-4)))
    # the stroke: the right foot off the ground (QUICK_STEP_FROM), the hips leading the turn
    k.append((QUICK_STEP_FROM, carry_key(D=4, hx=0.0, tw=-52, ht=-7, lx=5, fist=(-4.0, 42.0, 104.0), dir=(132.0, -12.0),
                                         flat=FLAT_R, lfree=1.0, lhand=(18.0, 14.0, 20.0), bow=3, ck=-3, cs=-4, feet=air)))
    k.append((21, carry_key(D=5, hx=2.5, tw=-42, ht=-5, lx=8, fist=(6.0, 42.0, 98.0), dir=(120.0, -14.0),
                            lfree=1.0, lhand=(14.0, 8.0, 18.0), bow=4, ck=-2, cs=-3, feet=air)))
    k.append((Q1, carry_key(D=8, hx=9.4, ht=8, tw=-20, lx=14, fist=(30.0, 34.0, 89.0), dir=(78.0, -26.0),
                            lfree=1.0, lhand=(6.0, 0.0, 16.0), bow=5, ck=-1, cs=-1, feet=air)))
    # the blow: the right foot lands, the weight goes onto it, the hips and chest turn through
    k.append((Q1 + 3, carry_key(D=12, hx=18.9, ht=26, tw=22, lx=28, fist=(58.0, 6.0, 86.0), dir=(0.0, -28.0),
                                lfree=1.0, lhand=(-12.0, -8.0, 16.0), bow=8, ck=2, cs=3, feet=p1)))
    k.append((Q1 + 5, carry_key(D=12, hx=19.3, ht=36, tw=50, lx=26, fist=(46.0, -16.0, 86.0), dir=(-70.0, -25.0),
                                lfree=1.0, lhand=(-18.0, -10.0, 17.0), bow=8, ck=3, cs=5, feet=p1)))
    # carried on round to his left: hips 44, chest 72 degrees round; the left arm flung back
    k.append((Q1 + 8, carry_key(D=11, hx=18.9, ht=44, tw=72, lx=23, fist=(34.0, -20.0, 92.0), dir=(-132.0, -12.0),
                                lfree=1.0, lhand=(-22.0, -12.0, 18.0), bow=7, ck=3, cs=6, feet=p1)))
    # the backhand's load: the weight rocks back onto the left foot (its heel down), the sword
    # goes on round behind his left side, level
    p1b = {'R': RQ1, 'L': STAND}
    k.append((38, carry_key(D=9, hx=12.0, ht=40, tw=76, lx=13, fist=(21.0, -26.0, 96.0), dir=(-150.0, -8.0), flat=FLAT_L,
                            lfree=1.0, lhand=(-16.0, -6.0, 14.0), bow=4, ck=1, cs=4, feet=p1b)))
    k.append((48, carry_key(D=8, hx=8.6, ht=38, tw=80, lx=9, fist=(14.0, -26.0, 98.0), dir=(-160.0, -4.0), flat=FLAT_L,
                            lfree=1.0, lhand=(-8.0, -2.0, 12.0), bow=3, ck=0, cs=3, feet=p1b)))
    air2 = {'R': None, 'L': STAND}
    k.append((54, carry_key(D=8, hx=9.4, ht=34, tw=72, lx=11, fist=(20.0, -24.0, 95.0), dir=(-135.0, -16.0),
                            lfree=1.0, lhand=(-8.0, -4.0, 14.0), bow=4, ck=0, cs=2, feet=air2)))
    k.append((Q2, carry_key(D=10, hx=18.4, ht=18, tw=42, lx=17, fist=(43.0, -22.0, 89.0), dir=(-78.0, -26.0),
                            lfree=1.0, lhand=(-12.0, -8.0, 16.0), bow=6, ck=-1, cs=1, feet=air2)))
    # the backhand's blow: the right foot lands further on, the hips and chest unwind to his right
    p2 = {'R': RQ2, 'L': LBALL2}
    k.append((Q2 + 3, carry_key(D=12, hx=27.9, ht=-2, tw=0, lx=28, fist=(60.0, 16.0, 86.0), dir=(0.0, -28.0),
                                lfree=1.0, lhand=(-18.0, -12.0, 18.0), bow=8, ck=2, cs=-2, feet=p2)))
    k.append((Q2 + 5, carry_key(D=12, hx=27.9, ht=-10, tw=-22, lx=26, fist=(50.0, 32.0, 86.0), dir=(70.0, -25.0),
                                lfree=1.0, lhand=(-22.0, -14.0, 20.0), bow=8, ck=3, cs=-5, feet=p2)))
    k.append((Q2 + 8, carry_key(D=11, hx=27.0, ht=-16, tw=-46, lx=23, fist=(38.0, 36.0, 92.0), dir=(130.0, -12.0),
                                lfree=1.0, lhand=(-22.0, -16.0, 22.0), bow=7, ck=3, cs=-6, feet=p2)))
    k.append((78, carry_key(D=10, hx=26.1, ht=-15, tw=-42, lx=20, fist=(37.0, 36.0, 93.0), dir=(134.0, -8.0),
                            lfree=1.0, lhand=(-18.0, -12.0, 18.0), bow=5, ck=1, cs=-3, feet=p2)))
    # recovery: the weight back onto the left foot, the sword up beside the plate and onto the
    # shoulder (the twin slash's way), the right foot back under him (QUICK_BACK)
    k.append((QUICK_BACK[0], carry_key(D=7, hx=14.4, ht=-6, tw=-16, lx=4, fist=(28.0, 27.0, 116.0), dir=(112.0, 10.0),
                                       lfree=0.6, lhand=(-6.0, -4.0, 6.0), feet={'R': RQ2, 'L': STAND})))
    k.append((96, carry_key(D=2, hx=1.8, ht=-2, tw=-6, fist=(19.0, 25.0, 134.0), dir=(135.0, 8.0),
                            lfree=0.2, lhand=(-2.0, 0.0, 2.0), feet={'R': None, 'L': STAND})))
    k.append((106, carry_key(D=1, fist=(16.0, 23.5, 135.0), dir=(156.0, 6.0))))
    k.append((114, carry_key()))
    return k


# User 2026-10-02 (after the first version): "the right arm must reach out as he swings, so it
# carries the body's weight; the left hand has many problems - with the first cut it turns
# towards the right hand, with the second it twists straight out". The first version bent the
# sword arm (the fist 80% of the arm's length from the shoulder at the blow: only the forearm
# swung), took the left hand across his body to the right in the windup and put it in the upper
# body's frame far behind him (turned 70-80 degrees, "behind" is over on his right), and flung it
# out level at shoulder height on the backhand with the elbow's pole left in the world frame.
# Now: through each stroke the sword arm is straight (QUICK_REACH of its length, at the angle
# given: the fist sweeps round the shoulder at full reach) and the weight goes further onto the
# front foot with it; the free left fist stays on his own left side, below the shoulder, carried
# round by the turn (QUICK_LEFT: from its shoulder, the upper body's frame), its elbow pointing
# back and out in the upper body's frame (it turns with him).
QUICK_REACH = 0.98       # of the arm, from where its shoulder goes with it (attack3d.girdles)
QUICK_ARM = {          # frame: (azimuth, elevation) of the straight sword arm, (share of its reach)
    # (third version) straight from the windup to the follow-through: the upper arm and the
    # forearm go round the shoulder as one lever, the elbow does not whip the forearm
    14: (125.0, -18.0, 0.97), QUICK_STEP_FROM: (115.0, -24.0, 0.98), 21: (95.0, -27.0, 1.0),
    Q1: (40.0, -32.0, 1.0), Q1 + 3: (0.0, -50.0, 1.0), Q1 + 5: (-40.0, -38.0, 1.0), Q1 + 8: (-80.0, -24.0, 0.97),
    38: (-95.0, -24.0, 0.95), 48: (-100.0, -22.0, 0.95), 54: (-90.0, -26.0, 0.99),
    Q2: (-40.0, -32.0, 0.99), Q2 + 3: (0.0, -50.0, 0.99), Q2 + 5: (40.0, -38.0, 0.99), Q2 + 8: (85.0, -22.0, 0.97), 78: (88.0, -20.0, 0.95),
}
LEFT_HANG = (1.0, -2.8, -36.6)        # the hanging left fist from its shoulder (attack3d.HANG_L)
QUICK_LEFT = {         # frame: the left fist from its shoulder, in the upper body's frame (F, R, U; - R = out)
    6: (8.0, -4.0, -34.0), 14: (16.0, -6.0, -28.0), QUICK_STEP_FROM: (10.0, -7.0, -30.0), 21: (8.0, -8.0, -31.0),
    Q1: (0.0, -8.0, -32.0), Q1 + 3: (-12.0, -8.0, -30.0), Q1 + 5: (-15.0, -9.0, -29.0), Q1 + 8: (-16.0, -10.0, -28.0),
    38: (-8.0, -8.0, -32.0), 48: (2.0, -6.0, -33.0), 54: (0.0, -7.0, -33.0), Q2: (-4.0, -8.0, -32.0),
    Q2 + 3: (-14.0, -12.0, -28.0), Q2 + 5: (-16.0, -13.0, -27.0), Q2 + 8: (-16.0, -14.0, -26.0), 78: (-12.0, -10.0, -29.0),
    QUICK_BACK[0]: (-4.0, -4.0, -34.0), 96: (0.0, -3.0, -36.0),
}
POLE_L_BODY = (-0.6, -0.5, -0.6)      # the free elbow: back and out, in the upper body's frame
QUICK_POLE_R = {       # frame: the sword arm's elbow, in the upper body's frame
    14: (-0.2, 1.0, 0.25), QUICK_STEP_FROM: (-0.2, 1.0, 0.1), Q1: (0.0, 0.6, -1.0), Q1 + 3: (0.0, 0.6, -1.0),
    Q1 + 8: (0.5, 0.0, -1.0), 48: (0.4, 0.2, -1.0), Q2: (0.4, 0.3, -1.0), Q2 + 3: (0.0, 0.6, -1.0),
    Q2 + 8: (-0.2, 1.0, -0.3), 78: (-0.2, 1.0, -0.3),
}


# User 2026-10-02 (after the second version): "the swing still feels like only the elbow turning
# the forearm; the shoulder must carry the upper arm round - the upper arm always moves". Drawn
# with each part in its own colour: the shoulder plate stood still through the whole stroke (its
# turn pinned at its limit: measured from the carry, where the arm is up by the shoulder) and
# covered the 13 px upper arm. `swing` (1 through the strokes, 0 in the carry) makes the plate turn
# about the stroke's own middle (anim_attack.plate_turn), the shoulder travel further with the
# arm (attack3d.SWING_FWD, GIRDLE_IN), and in the front view an upper arm reaching towards the
# camera is drawn over the plate it comes out from under.
QUICK_SWING = {0: 0.0, 3: 0.0, 6: 0.5, QUICK_BACK[0]: 0.5, 96: 0.0, 106: 0.0, 114: 0.0}


def quick_arms(keys):
    """The arms of the quick slashes' keys (QUICK_ARM, QUICK_LEFT, the poles, QUICK_SWING)."""
    out = []
    for t, k in keys:
        k = dict(k)
        k['swing'] = QUICK_SWING.get(t, 1.0)
        st = dict(k, whole_turn=True)
        if t in QUICK_ARM:
            az, el = QUICK_ARM[t][:2]
            share = QUICK_ARM[t][2] if len(QUICK_ARM[t]) > 2 else QUICK_REACH
            u = A.direction(az, el)
            # from where the shoulder goes with the straight arm (the girdle follows it out)
            sh = A.add(A.shoulder('R', st), A.sub(A._girdle('R', u, k['tw'], k['swing']), A.carry_girdle()))
            k['fist'] = A.add(sh, A.mul(u, share * A.ARM))
        if t in QUICK_LEFT:
            k['lhand'] = A.sub(QUICK_LEFT[t], LEFT_HANG)
        if k.get('lfree', 0.0) > 0:
            k['poleL'] = A.yaw(POLE_L_BODY, k['tw'])
        if t in QUICK_POLE_R:
            k['poleR'] = A.yaw(QUICK_POLE_R[t], k['tw'])
        out.append((t, k))
    return out


def quick_steps():
    return {'R': [(QUICK_STEP_FROM, STAND), (Q1 + 3, RQ1), (54, RQ1), (Q2 + 3, RQ2), (QUICK_BACK[0], RQ2),
                  (QUICK_BACK[1], STAND)]}


QUICK_ARC = (22, 23, 25, 26, 28, 30, 58, 59, 61, 62, 64, 66)   # frames the straight arm is also set at


def _arc_keys(clip, keys):
    """Keys at QUICK_ARC between the straight-arm keys: between two of them the fist would cut
    the chord, come nearer the shoulder and bend the elbow (the third version measured 45-48
    degrees as each stroke starts); here it goes round the shoulder at full reach (the arm's
    direction interpolated by angle). Everything else is the clip's own value at that frame."""
    arm_t = sorted(QUICK_ARM)
    out = []
    for t in QUICK_ARC:
        a = max(x for x in arm_t if x < t)
        b = min(x for x in arm_t if x > t)
        u = (t - a) / (b - a)
        A0, A1 = QUICK_ARM[a], QUICK_ARM[b]
        az = A0[0] + ((A1[0] - A0[0] + 180.0) % 360.0 - 180.0) * u
        el = A0[1] + (A1[1] - A0[1]) * u
        share = (A0[2] if len(A0) > 2 else QUICK_REACH) * (1 - u) + (A1[2] if len(A1) > 2 else QUICK_REACH) * u
        k = contact_key(clip, t)
        # a foot on its way stays a step (in the air between its own keys)
        st = clip.at(t)
        k['feet'] = {s_: (None if not st['feet'][s_][4] else k['feet'][s_]) for s_ in 'RL'}
        k['lfree'] = st['lfree']
        out.append((t, k, (az, el, share)))
    return out


def quick():
    """快斬連段 (two-hit version): windup 24, hit 6 (24 .. 29), hit 6 (60 .. 65), recovery 54 ->
    120 frames."""
    keys = quick_arms(quick_keys())
    base = Clip('quick', keys, quick_steps(), whole_turn=True)
    extra = []
    for t, k, (az, el, share) in _arc_keys(base, keys):
        st = dict(k, whole_turn=True)
        uu = A.direction(az, el)
        sh = A.add(A.shoulder('R', st), A.sub(A._girdle('R', uu, k['tw'], k['swing']), A.carry_girdle()))
        k['fist'] = A.add(sh, A.mul(uu, share * A.ARM))
        extra.append((t, k))
    keys = sorted(keys + extra, key=lambda tk: tk[0])
    return Clip('quick', keys, quick_steps(), whole_turn=True)


def quick_bounce():
    """The second (last) quick slash parried: BOUNCED 0.8 s (48 frames), the heavy bounce's poses
    two thirds as long."""
    keys, steps = bounce_keys(contact_key(quick(), Q2 + 3), scale=2.0 / 3.0)
    return Clip('quick_bounce', with_poles(keys, {round(t * 2 / 3): v for t, v in POLES_BOUNCE.items()}), steps,
                whole_turn=True)


# ------------------------------------------------------------------ C5 上挑: the quick combo's third hit (quick_combo_3)
# veltharis_data quick_combo_3: the two light slashes (as quick_combo_2), then 0.8 s after the second
# starts (48 frames) the third: 判定 0.1 s (108 .. 113), heavy, a 120-degree sector in front, radius
# SWEEP_RADIUS 155, launching; parried it bounces him 1.2 s; 收招 0.9 s (54; 二階段 x0.75 -> 41): 168 frames.
# Up to the second cut's follow-through (Q2 + 8) the keys are the quick slashes' own (the same frames
# up to the second hit box's end, as the triple slash shares the twin slash's).
# The second cut leaves the sword low behind him on his right, one-handed, the arm straight, the chest
# turned to his right, the weight on the right foot ahead. From there it runs on into the upswing's load:
# he sinks right down and bends over (bend: the chest turned down about the belt, as the judgment thrust),
# the chest turning on further to his right, the blade pressed low behind him on the right, its tip near
# the ground; the free left hand comes across and takes the grip (heavy: two hands) - held a moment, low,
# the blade trailing behind him (the read: about to scoop up). Then the scoop: the legs drive him up, the
# bend comes out and he arches back, the chest unwinds from his right round to his left, both arms swing
# the blade from low behind him on his right forward and up: entering the sector low on his right front,
# straight ahead at the hit box's edge at the player's height, leaving it on his left front rising (the
# edge leading: a cut). The back (left) heel comes up and he pivots on the ball; neither foot leaves its
# place. The blade carries on up over his left shoulder, he holds it there arched back (the opening),
# then brings it down before him, upright before his right shoulder and back onto it (the way the sweeps
# put it back), the left hand letting go, the right foot stepping back under him.
Q3 = Q2 + 48                  # 108: the third hit box (108 .. 113)
QUICK3_END = Q3 + 6 + 54      # 168
QUICK3_LOW = (92, 100)        # held low before the scoop
QUICK3_TOP = (120, 128)       # held up over the left shoulder after it
QUICK3_BACK = (140, 152)      # the right foot back under him
QUICK3_SHARED = Q2 + 8        # the quick slashes' keys up to here


def q3key(**kw):
    """A key of the upswing: the free left hand takes the grip from where it swings (lgrab)."""
    k = carry_key(swing=1.0, lgrab=1.0, lfree=1.0)
    k.update(kw)
    return k


def quick3_keys():
    k = [kv for kv in quick().keys if kv[0] <= QUICK3_SHARED]
    p2 = {'R': RQ2, 'L': LBALL2}
    flat = {'R': RQ2, 'L': STAND}
    piv = {'R': RQ2, 'L': LBALL}
    # held low: turned far round to his right (the chest 72 degrees, as far as the quick slashes turn it to
    # his left), sunk and bent over; both fists before the right hip (the left arm across him - with the
    # right hand by the pommel the right side is the grip's awkward one: turned less, the left hand
    # cannot reach), the blade sloping down behind him on his right to a tip 8 px off the ground
    low = q3key(D=22, hx=24.0, ht=-14, tw=-72, lx=0, bend=36.0, bow=-24, fist=(37.0, 20.0, 69.0), dir=(148.0, -28.0),
                flat=FLAT_R, two=1.0, ck=-3, cs=-6, feet=flat)
    k += [
        # the follow-through sinks on into the load: the right arm draws in, the blade lowered behind him,
        # the left hand coming across
        (76, q3key(D=15, hx=26.0, ht=-15, tw=-58, lx=12, bend=14.0, bow=-6, fist=(30.0, 40.0, 76.0), dir=(138.0, -18.0),
                   flat=FLAT_R, two=0.0, lhand=(-2.0, 2.0, 14.0), ck=0, cs=-6, feet=p2)),
        (84, q3key(D=20, hx=25.0, ht=-14, tw=-68, lx=3, bend=30.0, bow=-18, fist=(35.0, 25.0, 71.0), dir=(145.0, -25.0),
                   flat=FLAT_R, two=0.6, lhand=(8.0, 8.0, 16.0), ck=-2, cs=-6, feet=flat)),
        (QUICK3_LOW[0], low),
        (QUICK3_LOW[1], low),
        # the scoop: up off the legs, unbending, the chest unwinding to his left, the blade swung round
        # in front and up
        (104, q3key(D=20, hx=24.5, ht=-10, tw=-58, lx=0, bend=34.0, bow=-22, fist=(44.0, 16.0, 70.0), dir=(118.0, -25.0),
                    two=1.0, ck=-2, cs=-4, feet=piv)),
        (Q3, q3key(D=17, hx=25.0, ht=-2, tw=-30, lx=0, bend=29.0, bow=-18, fist=(45.0, 4.0, 70.0), dir=(60.0, -24.0),
                   two=1.0, ck=0, cs=-1, feet=piv)),
        (Q3 + 2, q3key(D=14, hx=25.0, ht=6, tw=-6, lx=0, bend=25.0, bow=-14, fist=(44.0, -2.0, 72.0), dir=(4.0, -17.0),
                       two=1.0, ck=2, cs=2, feet=piv)),
        (Q3 + 3, q3key(D=13, hx=24.5, ht=9, tw=4, lx=0, bend=22.0, bow=-12, fist=(45.0, -8.0, 74.0), dir=(-16.0, -8.0),
                       two=1.0, ck=3, cs=3, feet=piv)),
        (Q3 + 5, q3key(D=9, hx=23.0, ht=14, tw=24, lx=-2, bend=12.0, bow=-9, fist=(38.0, -18.0, 88.0), dir=(-60.0, 35.0),
                       two=1.0, ck=4, cs=5, feet=piv)),
        # carried on up over his left shoulder, arched back; held there (the opening)
        (116, q3key(D=5, hx=19.0, ht=18, tw=34, lx=-8, bend=0.0, bow=-8, fist=(30.0, -14.0, 108.0), dir=(-108.0, 55.0),
                    flat=FLAT_L, two=1.0, ck=3, cs=4, feet=piv)),
        (QUICK3_TOP[0], q3key(D=4, hx=16.0, ht=16, tw=36, lx=-9, bow=-6, fist=(26.0, -10.0, 120.0), dir=(-150.0, 48.0),
                              flat=FLAT_L, two=1.0, ck=1, cs=3, feet=flat)),
        (QUICK3_TOP[1], q3key(D=4, hx=16.0, ht=16, tw=36, lx=-9, bow=-6, fist=(26.0, -10.0, 120.0), dir=(-150.0, 48.0),
                              flat=FLAT_L, two=1.0, ck=0, cs=2, feet=flat)),
        # down before him, upright, across to before the right shoulder (the weight back onto the left
        # foot, the right foot stepping back under him), laid back on it; the left hand lets go
        (134, q3key(D=7, hx=14.0, ht=8, tw=16, lx=0, bow=0, fist=(30.0, -2.0, 110.0), dir=(-60.0, 66.0),
                    flat=A.unit((1.0, -0.6, 0.0)), two=1.0, swing=0.5, ck=0, feet=flat)),
        (QUICK3_BACK[0], q3key(D=8, hx=12.0, ht=4, tw=4, lx=1, fist=(21.0, 12.0, 122.0), dir=(-18.0, 80.0), flat=FLAT_R,
                               two=0.6, swing=0.3, lhand=(4.0, 2.0, 8.0), feet=flat)),
        (146, q3key(D=4, hx=3.0, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), roll=30.0, two=0.0, swing=0.0, lfree=0.5,
                    lhand=(2.0, 0.0, 4.0), feet={'R': None, 'L': STAND})),
        (154, carry_key(D=1)),
        (QUICK3_END - 6, carry_key()),
    ]
    return with_body_poles(k, POLES_Q3)


# where the elbows point after the second cut, in the upper body's frame (turned with it, attack3d.yaw)
POLES_Q3 = {
    76: ((-0.6, 1.0, -0.4), (0.6, -0.2, -1.0)),
    84: ((-0.6, 1.0, -0.6), (0.6, 0.2, -1.0)),
    QUICK3_LOW[0]: ((-0.6, 1.0, -0.6), (0.6, 0.2, -1.0)), QUICK3_LOW[1]: ((-0.6, 1.0, -0.6), (0.6, 0.2, -1.0)),
    104: ((-0.3, 1.0, -0.8), (0.4, 0.0, -1.0)),
    Q3: ((0.0, 0.6, -1.0), (0.0, -0.6, -1.0)), Q3 + 2: ((0.0, 0.6, -1.0), (0.0, -0.6, -1.0)),
    Q3 + 3: ((0.0, 0.6, -1.0), (0.0, -0.6, -1.0)),
    Q3 + 5: ((0.4, 0.6, -0.8), (-0.2, -1.0, -0.4)),
    116: ((1.0, -0.1, -0.2), (-0.2, -1.0, 0.25)),
    QUICK3_TOP[0]: ((1.0, -0.1, -0.2), (-0.2, -1.0, 0.25)), QUICK3_TOP[1]: ((1.0, -0.1, -0.2), (-0.2, -1.0, 0.25)),
    134: ((0.0, 1.0, -0.8), (0.0, -1.0, -0.8)),
    QUICK3_BACK[0]: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)),
}


def with_body_poles(keys, table):
    """with_poles() for poles given in the upper body's frame: turned with each key's tw."""
    out = []
    for t, k in keys:
        if t in table:
            k = dict(k)
            k['poleR'], k['poleL'] = (A.yaw(p, k['tw']) for p in table[t])
        out.append((t, k))
    return out


def quick3_steps():
    return {'R': [(QUICK_STEP_FROM, STAND), (Q1 + 3, RQ1), (54, RQ1), (Q2 + 3, RQ2), (QUICK3_BACK[0], RQ2),
                  (QUICK3_BACK[1], STAND)]}


def quick3():
    """快斬連段 (three-hit version): the two quick slashes (hits 24, 60), then the upswing (hit 108),
    recovery 54 -> 168 frames."""
    # lead: the edge leads through the strokes; from the top over the left shoulder on, the keys' flat
    # (put back on the shoulder fast the edge would lead, then flash flat as it slows)
    return Clip('quick3', quick3_keys(), quick3_steps(), whole_turn=True, musts=tuple(range(Q3, Q3 + 7)),
                lead=QUICK3_TOP[0] - 2, exact_cape=True)


QUICK3_CONTACT = Q3 + 2       # the blade straight ahead (the bounce starts here)


def quick3_bounce():
    """The upswing parried (bounce_time 1.2: BOUNCED 72 frames) from its contact: two-handed, the
    heavy bounce (the blade knocked up and back over his head onto the shoulder); the bend comes out
    as he is jolted upright."""
    c = contact_key(quick3(), QUICK3_CONTACT)
    s = quick3().at(QUICK3_CONTACT)
    c['bend'] = s['bend']
    c['lfree'], c['lgrab'] = 0.0, 0.0          # both hands on the grip: the left is jarred off it, then hangs
    keys, steps = bounce_keys(c)
    keys = [(t, dict(k, bend={4: 8.0}.get(t, k.get('bend', 0.0)))) for t, k in keys]
    return Clip('quick3_bounce', with_poles(keys, POLES_BOUNCE), steps, whole_turn=True, exact_cape=True)


# ------------------------------------------------------------------ C3 墜誓下劈 (the oath cleave), two hands
# veltharis_data _cleave_hit: 起手 1.0 s (60 frames) -> 判定 0.1 (6: 60 .. 65) -> 收招 1.2 (72; 二階段
# x0.75 -> 54): 138 frames. A straight line in front, 165 long, 53 wide (CLEAVE_LENGTH / _WIDTH).
# The delayed version (oath_cleave_delayed, 40%): the sword is at its highest at 0.8 s (hold_start,
# frame 48) and stays there, still, for 0.6 s (delay_hold: boss_sim moves him not at all and the
# pose must not move - combat-design §11.6 rule 8), then comes down the same way: 174 frames, the
# hit box 96 .. 101. The sheet is the same: the pose at CLEAVE_TOP is held 36 frames longer.
#
# The highest point (user 2026-10-03, the first version rejected: "the cleave is raised over the
# head - you only have it held at the shoulder"): both fists right over the helmet, above its crown
# (163 px), the blade back over his head and up (40 degrees), the chest arched back (8 degrees) and
# square to the front. With these arms (36 px from shoulders at 112) both fists cannot get over a
# helmet that with its crown reaches 160: shoulders shrugged up (the shoulder blades turn up with
# both arms over the head, `shrug`, `draw_in`) and the chest arched back got them to the forehead
# (147 px) at the most; the arms are drawn longer as they go up (`arm_k`, at the most ARM_K_TOP at
# the highest point, back to 1 by the time they reach forward to strike: attack3d.arm_lengths) -
# the stylised proportions (a helmet as tall as a third of him) make a straight overhead lift
# otherwise impossible (animation-review §4.3: the move's pose is not lowered because the rig cannot
# reach it). Fists in front of the face instead covered the visor from the front (the forearms
# across it); over the helmet the forearms are behind it and the head is drawn over them
# (anim_attack.behind_head): the visor shows between the arms.
# The blade's flat (user 2026-10-03: "the edges face front and back, so from the side you see the
# whole blade, but from the front and the back only a thin line"): from the highest point through
# the cut, in the ground and out of it, the width is in the vertical plane through the blade
# (roll 90: one edge forward, one back, the flats to his left and right). From the front and the
# back the sword coming down at the camera and stuck in the ground before him is its thickness
# (carry.THICK), not its width. Lifted off the shoulder (lying flat) it turns edge-up on the way up.
# The cut comes straight down the line in front: the blade falls forward in the vertical plane
# ahead of him, accelerating; the right foot steps in (one foot, as the sweeps: the windup is the
# upper body's) and lands with the blow; the hips go two thirds of the way onto it and turn a
# little to his left (the right shoulder drives forward), the chest leans in over the front knee.
# As the hit box is on the tip passes 165 px out through the player's height (40 px) and then
# bites into the ground (CLEAVE_BITE px deep, about 140 px out) and stays there: the recovery
# opens with the sword stuck in the ground (boss-veltharis §4.3: the biggest opening of the fight)
# while he stays bent over it. Then he wrenches it out (the weight back onto the left foot, the
# fists pulling back along the blade until the tip is free), lifts it upright in front of his
# right shoulder and lays it back on the shoulder (the way every attack puts it back), the right
# foot stepping back under him.
CLEAVE_W = 60                 # the hit box (60 .. 65)
CLEAVE_TOP = 48               # the highest point (hold_start 0.8 s); the delayed version holds it 36 frames
CLEAVE_HOLD = 36              # delay_hold 0.6 s
CLEAVE_CONTACT = CLEAVE_W + 3          # the tip through the player's height at the hit box's edge
CLEAVE_STEP_FROM = 53         # the right foot leaves the ground (the stroke under way)
CLEAVE_END = CLEAVE_W + 6 + 72         # 138
CLEAVE_STUCK = (67, 96)       # the blade in the ground, still
CLEAVE_BACK = (106, 118)      # the right foot back under him
RC = (40.0, -1.0, gait.ANKLE_H, 0.0)    # the right foot stepped in with the cleave
UP_OUT_R, UP_OUT_L = (-0.15, 1.0, 0.45), (-0.15, -1.0, 0.45)    # both arms up: the elbows raised out to the sides
EDGE = 90.0                   # roll: the blade's width in its own vertical plane (the edges front and back)
ARM_K_TOP = 1.45              # the arms over the head drawn this many times as long (attack3d.arm_lengths)
SHRUG_TOP, DRAW_IN_TOP = 5.0, 3.0     # px: the shoulders up and in with both arms over the head


def overhead(k, shrug, draw_in=None):
    """The arms on their way over the head: drawn k times as long, the shoulders shrug px further up
    (and in, in proportion)."""
    return dict(arm_k=k, shrug=shrug, draw_in=DRAW_IN_TOP * shrug / SHRUG_TOP if draw_in is None else draw_in)


def cleave_keys():
    k = []
    planted = {'R': RC, 'L': STAND}
    air = {'R': None, 'L': STAND}
    k.append((0, carry_key()))
    # the left hand comes up to the grip as the fists rise off the shoulder; the hilt goes up over
    # the right shoulder and in over the head, the blade still back behind him (where the carry has
    # it) and rising; it turns from lying flat to edge-up on the way
    k.append((8, carry_key(D=1, tw=-3, lx=-1, fist=(13.0, 19.0, 141.0), dir=(168.0, 14.0), two=0.5, roll=35.0,
                           **overhead(1.1, 1.0))))
    k.append((16, carry_key(D=1, hx=-0.5, tw=-3, lx=-3, fist=(9.0, 14.0, 153.0), dir=(172.0, 32.0), two=0.8, roll=70.0,
                            bow=-1, ck=-1, **overhead(1.3, 2.5))))
    k.append((24, carry_key(D=1, hx=-1.0, tw=-2, lx=-5, fist=(1.0, 3.5, 159.5), dir=(178.0, 38.0), two=1.0, roll=EDGE,
                            bow=-2, ck=-1, **overhead(1.44, 4.0))))
    # the highest point: both fists over the helmet, the blade back over his head, the chest arched
    # back; held still from CLEAVE_TOP - 4 (the delayed version holds it, motionless)
    top = carry_key(D=1, hx=-1.5, tw=0, lx=-8, fist=(-4.0, 0.0, 163.0), dir=(180.0, 40.0), two=1.0, roll=EDGE,
                    bow=-3, ck=-2, **overhead(ARM_K_TOP, SHRUG_TOP))
    k.append((34, dict(top, lx=-7, fist=(-2.0, 2.0, 162.0), dir=(179.0, 39.0), **overhead(1.45, 4.8))))
    k.append((CLEAVE_TOP - 4, top))
    k.append((CLEAVE_TOP, top))
    # the stroke: the fists come forward over his head and down, the blade swings up over him and
    # falls forward, faster and faster; the arms back to their length as they reach forward; the
    # right foot off the ground (CLEAVE_STEP_FROM), the hips after it
    k.append((51, carry_key(D=2, hx=-1.0, tw=0, lx=-7, fist=(3.0, 0.0, 159.0), dir=(180.0, 62.0), two=1.0,
                            roll=EDGE, bow=-3, ck=-2, **overhead(1.44, 4.8))))
    k.append((54, carry_key(D=4, hx=2.5, ht=2, tw=2, lx=0, fist=(14.0, 0.0, 151.0), dir=(0.0, 82.0), two=1.0,
                            roll=EDGE, bow=0, ck=-1, feet=air, **overhead(1.4, 3.5))))
    k.append((57, carry_key(D=7, hx=9.0, ht=5, tw=4, lx=9, fist=(29.0, 0.0, 137.0), dir=(0.0, 52.0), two=1.0,
                            roll=EDGE, bow=3, ck=0, feet=air, **overhead(1.21, 1.5))))
    k.append((59, carry_key(D=9, hx=15.0, ht=8, tw=5, lx=16, fist=(41.0, 0.0, 120.0), dir=(0.0, 30.0), two=1.0,
                            roll=EDGE, bow=5, ck=1, feet=air, **overhead(1.06, 0.5))))
    k.append((61, carry_key(D=11, hx=21.0, ht=10, tw=6, lx=21, fist=(53.0, 0.5, 96.0), dir=(0.0, 6.0), two=1.0,
                            roll=EDGE, bow=7, ck=2, feet=air)))
    # the blow: the right foot lands, the tip passes the hit box's edge at the player's height
    k.append((CLEAVE_CONTACT, carry_key(D=15, hx=28.0, ht=12, tw=7, lx=30, fist=(60.0, 0.0, 84.0), dir=(0.0, -26.0),
                                        two=1.0, roll=EDGE, bow=9, ck=3, feet=planted)))
    # into the ground: the blade bites and stops; he goes on down over it
    k.append((65, carry_key(D=16, hx=28.5, ht=12, tw=8, lx=30, fist=(59.0, 0.0, 82.0), dir=(0.0, -45.0), two=1.0,
                            roll=EDGE, bow=9, ck=3, feet=planted)))
    stuck = carry_key(D=16, hx=29.0, ht=12, tw=8, lx=30, fist=(60.0, 0.0, 82.0), dir=(0.0, -47.5), two=1.0,
                      roll=EDGE, bow=8, ck=2, feet=planted)
    k.append((CLEAVE_STUCK[0], stuck))
    k.append((CLEAVE_STUCK[1], stuck))
    # wrenched out: the weight back onto the left foot, the fists pulled back along the blade
    k.append((101, carry_key(D=14, hx=24.0, ht=10, tw=7, lx=25, fist=(53.0, 0.0, 89.4), dir=(0.0, -47.5), two=1.0,
                             roll=EDGE, bow=6, ck=1, feet=planted)))
    k.append((106, carry_key(D=9, hx=14.0, ht=6, tw=3, lx=12, fist=(40.0, 2.0, 98.0), dir=(-4.0, -8.0), two=1.0,
                             roll=EDGE, bow=4, ck=0, feet=planted)))
    # lifted upright before his right shoulder, laid back on it (the way the sweeps put it back);
    # the right foot steps back under him (CLEAVE_BACK), the left hand lets go
    k.append((112, carry_key(D=6, hx=6.0, ht=3, tw=2, lx=4, fist=(28.0, 8.0, 112.0), dir=(-12.0, 48.0), two=1.0,
                             roll=-30.0, bow=2, feet={'R': None, 'L': STAND})))
    k.append((118, carry_key(D=3, hx=1.5, ht=0, tw=1, lx=1, fist=(21.0, 13.0, 123.0), dir=(-18.0, 80.0), two=0.5,
                             flat=FLAT_R)))
    k.append((126, carry_key(D=1, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), two=0.0, roll=30.0)))
    k.append((132, carry_key()))
    return k


CLEAVE_MUSTS = (CLEAVE_TOP,) + tuple(range(CLEAVE_W, CLEAVE_W + 7))


def cleave_steps():
    return {'R': [(CLEAVE_STEP_FROM, STAND), (CLEAVE_CONTACT, RC), (CLEAVE_BACK[0], RC), (CLEAVE_BACK[1], STAND)]}


POLES_CLEAVE = {
    8: ((0.1, 1.0, -0.4), (1.0, 0.3, -0.6)),
    16: ((0.0, 1.0, 0.0), (0.4, -1.0, -0.3)), 24: (UP_OUT_R, UP_OUT_L), 34: (UP_OUT_R, UP_OUT_L), CLEAVE_TOP - 4: (UP_OUT_R, UP_OUT_L), CLEAVE_TOP: (UP_OUT_R, UP_OUT_L),
    51: (UP_OUT_R, UP_OUT_L),
    54: ((0.1, 1.0, 0.1), (0.1, -1.0, 0.1)),
    57: ((0.2, 1.0, -0.4), (0.2, -1.0, -0.4)),
    59: ((0.1, 0.8, -0.8), (0.1, -0.8, -0.8)),
    61: (DOWN_R, DOWN_L), CLEAVE_CONTACT: (DOWN_R, DOWN_L), 65: (DOWN_R, DOWN_L),
    CLEAVE_STUCK[0]: (DOWN_R, DOWN_L), CLEAVE_STUCK[1]: (DOWN_R, DOWN_L),
    101: (DOWN_R, DOWN_L), 106: (RISE_R, RISE_L), 112: (RISE_R, RISE_L),
    118: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)),
}


def cleave():
    """墜誓下劈: windup 60 (the highest point at 48), hit 6 (60 .. 65), recovery 72 -> 138 frames.
    Poses of their own (musts): the highest point (the delayed version holds it) and every frame of
    the hit box (the bounce starts on the contact)."""
    return Clip('cleave', with_poles(cleave_keys(), POLES_CLEAVE), cleave_steps(), musts=CLEAVE_MUSTS, still=True,
                ground=True, lead=False, tall=True)


def cleave_bounce():
    """墜誓下劈 parried (bounce_time 1.2: BOUNCED 72 frames), from its contact: the blade is knocked
    up before it reaches the ground."""
    keys, steps = bounce_keys(contact_key(cleave(), CLEAVE_CONTACT))
    return Clip('cleave_bounce', with_poles(keys, POLES_BOUNCE), steps, tall=True)


# ------------------------------------------------------------------ 灰燼衝擊 (the ash impact): the sword plunged into the ground
# veltharis_data _impact_ring(1.1): 起手 1.1 s (66 frames; the last 0.6 s the danger telegraph, drawn
# by code: white light, white runes over his head) -> the ring from frame 66 (0.2 s) -> 收招 1.4 s (84):
# 162 frames. Phase 2's 雙重衝擊: a second ring 0.9 s (54) after the first (frame 120, its own 0.6 s
# telegraph from 84), 收招 1.4 x 0.75 (63): 195 frames. Unblockable: no bounce.
# User 2026-10-03 (second version): "改成劍尖朝下，雙手往地面下插的插劍，然後劍尖朝下但手一樣要舉過頭頂
# 蓄力" - not the cleave's cut: the sword turned tip-down and plunged. Off the shoulder the sword goes
# round in front of him the way he puts it down standing (carry.pose3, the stop's route backwards:
# up over the shoulder, forward, down) until it hangs tip-down before his chest, both hands on the
# grip (the right by the pommel, on top; the left below it, by the guard); then both hands lift it
# straight up until they are over his head, the blade hanging tip-down in front of his face, and he
# holds it there (the charge: veltharis_data's danger time, the last 0.6 s before the ring; the white
# telegraph is drawn by code), arched back, the blade angled a little forward past his face
# (impact_top), the helmet's cross lit red; then, standing (no step, no bending), his arms drive
# it straight down into the ground steeply (80 degrees) about 45 px ahead of him as the ring goes out
# (the ring is centred on him). The edges front and back all through, as the cleave holds it (a sword turned over end to
# end in both hands keeps its edges front and back): from the front and the back the hanging and the
# planted blade are a thin line. It stays in through the ring and the recovery, comes straight up
# out of the ground along its line and goes back onto the shoulder the way it came (carry.pose3).
# The double impact pulls it straight up out of the ground and lifts it over his head again for the
# second plunge.
IMPACT_RING = 66
IMPACT_END = IMPACT_RING + 12 + 84            # 162
IMPACT_RING2 = IMPACT_RING + 54               # 120: the double impact's second ring
DOUBLE_END = IMPACT_RING2 + 12 + 63           # 195
DANGER = 36                                   # veltharis_data danger_time 0.6 s: the charge before each ring
IMPACT_TOP = IMPACT_RING - DANGER             # 30: the hands over his head (held from 26 until the plunge)
PLUNGE = 6                                    # frames from the hands over his head to the blade in the ground
IMPACT_DIR = (0.0, -80.0)                     # the plunged blade: steep, straight ahead
IMPACT_FIST = (24.0, 0.0, 107.7)              # the right fist as the blade goes in (frame P): 8.5 px deep, standing
# The helmet's cross flashes red, once, as the charge begins (user 2026-10-03: "我要的是頭盔附近閃一下十字
# 紅光，像絕區零的怪在攻擊前會閃的那種光一樣……劍插下去前十字紅光要閃一下，警示玩家"): brightest at the start
# of the game's danger time (the 0.6 s the player has to get out of the ring), fading in before and out
# after (FLASH_CURVE); the cross lights up with it (glow, anim_attack.glow_head, Clip(flashes=)); the
# flare round it (a wide cross of light by the helmet) is drawn by code - export_cleave gives the
# frames, the curve and where (json 'flash'), the previews draw a stand-in. It replaces the whole-body
# white light of the danger telegraph for this move.
# User 2026-10-04: "閃光需要有淡入和淡出，不是突然出現光的貼圖，是有過程的": the flash fades in over the
# 6 frames before the danger time starts, is brightest as it starts, holds and fades out over 10: about
# a third of a second. FLASH_CURVE: (frames from the peak, brightness 0 .. 1), straight lines between;
# the helmet's cross (glow) and the code's flare follow the same curve.
FLASH_CURVE = ((-6, 0.0), (-4, 0.35), (-2, 0.7), (0, 1.0), (4, 1.0), (8, 0.6), (12, 0.35), (14, 0.0))
FLASH_SPAN = (FLASH_CURVE[0][0], FLASH_CURVE[-1][0])


def flash_level(t, peaks):
    """The flash's brightness at combat frame t, the flashes peaking at `peaks`."""
    best = 0.0
    for p in peaks:
        k = t - p
        for (k0, v0), (k1, v1) in zip(FLASH_CURVE, FLASH_CURVE[1:]):
            if k0 <= k <= k1:
                best = max(best, v0 + (v1 - v0) * (k - k0) / (k1 - k0))
                break
    return best


def flash_musts(peaks, levels=(0.3, 0.65)):
    """Frames where the drawn cross changes (its brightness crosses a step of anim_attack.glow_head):
    each a pose of its own, so a held pose does not carry the change on."""
    step = lambda v: sum(v >= x for x in levels)
    out = []
    for p in peaks:
        for t in range(p + FLASH_SPAN[0], p + FLASH_SPAN[1] + 2):
            if step(flash_level(t, peaks)) != step(flash_level(t - 1, peaks)):
                out.append(t)
    return tuple(out)


def _route(b, **kw):
    """A key on the way between the carry (b = 1) and the sword hanging tip-down before him (b = 0):
    carry.pose3's direction and flat (the route he puts the sword down by, standing)."""
    ax, w = carry.pose3(b)
    return carry_key(dir=A.angles(ax), flat=w, **kw)


def impact_top(**kw):
    """Both hands right over his head, the blade tip-down past his face and angled forward (68 degrees
    down: straight down from there it would go through the helmet; hands in front of his face held it
    straight down, but from the front the forearms then covered the visor), arched back; the cross
    on the helmet flashes as he holds it (Clip(flashes=), FLASH_CURVE)."""
    k = carry_key(D=1, hx=-1.0, lx=-10, fist=(-1.0, 2.0, 163.0), dir=(0.0, -68.0), two=1.0, roll=EDGE, bow=-3, ck=-2,
                  **overhead(ARM_K_TOP, SHRUG_TOP))
    k.update(kw)
    return k


def impact_raise(t0=0):
    """Carry -> the sword round in front of him, tip-down (t0 .. t0 + 19) -> lifted over his head
    (t0 + 26, held): the cross flashes as the charge begins (IMPACT_TOP)."""
    return [
        (t0, carry_key()),
        (t0 + 5, _route(0.82, D=1, fist=(18.0, 21.0, 138.0), two=0.25, **overhead(1.03, 0.3))),
        (t0 + 10, _route(0.58, D=1, lx=-1, fist=(22.0, 15.0, 134.0), two=0.55, **overhead(1.06, 0.6))),
        (t0 + 13, _route(0.4, D=1, lx=-1, fist=(22.0, 10.0, 131.0), two=0.75, bow=-1, **overhead(1.09, 0.9))),
        (t0 + 16, _route(0.22, D=1, lx=-1, fist=(22.0, 7.0, 130.0), two=0.9, bow=-1, **overhead(1.12, 1.2))),
        (t0 + 19, carry_key(D=1, lx=-2, fist=(21.0, 5.0, 132.0), dir=(0.0, -72.0), two=1.0, roll=EDGE, bow=-1,
                            **overhead(1.18, 1.6))),
        (t0 + 22, carry_key(D=1, hx=-0.5, lx=-5, fist=(14.0, 4.0, 146.0), dir=(0.0, -76.0), two=1.0, roll=EDGE, bow=-2,
                            ck=-1, **overhead(1.3, 3.0))),
        (IMPACT_TOP - 4, impact_top()),
        (IMPACT_TOP, impact_top()),
    ]


def _driven(d):
    """The right fist d px further along the planted blade's line (+ = in, - = out)."""
    return A.add(IMPACT_FIST, A.mul(A.direction(*IMPACT_DIR), d))


def impact_plant(P):
    """The plunge, standing (user 2026-10-03: "右腳不用往前踏，也不用彎腰，單純手舉過頭頂把劍插下去就好"):
    from the hands over his head (held until P - PLUNGE) the arms drive the sword straight down in
    front of him; the blade in the ground from P (the ring's first frame), driven in along its line."""
    return [
        (P - PLUNGE, impact_top()),
        (P - 4, carry_key(D=1, hx=-0.5, lx=-5, fist=(6.0, 1.0, 152.0), dir=(0.0, -74.0), two=1.0, roll=EDGE, bow=0, ck=-1,
                          **overhead(1.3, 3.0))),
        (P - 2, carry_key(D=1, lx=-1, fist=(16.0, 0.5, 134.0), dir=(0.0, -78.0), two=1.0, roll=EDGE, bow=3, ck=0,
                          **overhead(1.15, 1.2))),
        (P - 1, carry_key(D=2, lx=1, fist=(21.0, 0.0, 120.0), dir=(0.0, -79.0), two=1.0, roll=EDGE, bow=5, ck=1,
                          **overhead(1.07, 0.4))),
        (P, carry_key(D=2, lx=2, fist=IMPACT_FIST, dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=6, ck=2)),
        impact_planted(P + 2, bow=6, ck=1),
    ]


def impact_planted(t, **kw):
    """Standing over the planted sword, both hands on it (it does not move)."""
    k = carry_key(D=2, lx=2, fist=_driven(3.3), dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=5, ck=0)
    k.update(kw)
    return t, k


def impact_pull(t0):
    """Straight up out of the ground along its line (t0 .. t0 + 6), lifted tip-down, then round
    onto the shoulder the way it came (carry.pose3); the carry from t0 + 36."""
    return [
        (t0 + 6, carry_key(D=1, lx=1, fist=_driven(-16.0), dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=3)),
        (t0 + 12, carry_key(D=1, fist=(24.0, 3.0, 130.0), dir=(0.0, -75.0), two=1.0, roll=EDGE, bow=2)),
        (t0 + 18, _route(0.33, D=1, fist=(22.0, 9.0, 130.0), two=0.8, bow=1)),
        (t0 + 24, _route(0.6, D=1, fist=(21.0, 14.0, 133.0), two=0.5)),
        (t0 + 30, _route(0.85, D=1, fist=(17.0, 20.0, 135.0), two=0.15)),
        (t0 + 36, carry_key()),
    ]


RAISE_POLES = {5: ((0.1, 1.0, -0.4), (1.0, 0.3, -0.6)), 10: (RISE_R, RISE_L), 13: (RISE_R, RISE_L),
               16: (RISE_R, RISE_L), 19: (DOWN_R, DOWN_L), 22: ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
               IMPACT_TOP - 4: (UP_OUT_R, UP_OUT_L), IMPACT_TOP: (UP_OUT_R, UP_OUT_L)}


def poles_plant(P):
    return {P - PLUNGE: (UP_OUT_R, UP_OUT_L), P - 4: ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
            P - 2: ((0.1, 1.0, -0.5), (0.1, -1.0, -0.5)), P - 1: (DOWN_R, DOWN_L), P: (DOWN_R, DOWN_L),
            P + 2: (DOWN_R, DOWN_L)}


def poles_pull(t0):
    return {t0: (DOWN_R, DOWN_L), t0 + 6: (DOWN_R, DOWN_L), t0 + 12: (DOWN_R, DOWN_L), t0 + 18: (RISE_R, RISE_L),
            t0 + 24: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0))}


def _raise_poles(*tables):
    out = dict(RAISE_POLES)
    for tb in tables:
        out.update(tb)
    return out


IMPACT_PULL = 124             # the single impact: out of the ground from here
# the plunge a pose a frame (the hands come down from over his head 15 px a frame)
IMPACT_MUSTS = (IMPACT_TOP,) + flash_musts((IMPACT_TOP,)) + tuple(range(IMPACT_RING - PLUNGE, IMPACT_RING + 1))
# starting from a move the sword goes round from the shoulder to tip-down in front in 22 frames:
# every 2 frames (every 4 the tip moved 86-95 px a pose)
IMPACT_ENTRY = (tuple(range(0, 24, 2)), 12, 24)


def impact_keys():
    return impact_raise() + impact_plant(IMPACT_RING) + [impact_planted(IMPACT_PULL)] + impact_pull(IMPACT_PULL)


def impact():
    """灰燼衝擊: tip-down over his head (the cross lit) from frame 26, held through the charge (the
    last 0.6 s), plunged at frame 66 (the ring), recovery 84 -> 162. The feet do not move."""
    return Clip('impact', with_poles(impact_keys(), _raise_poles(poles_plant(IMPACT_RING), poles_pull(IMPACT_PULL))),
                {}, musts=IMPACT_MUSTS, still=True, ground=True, lead=False, tall=True, flashes=(IMPACT_TOP,))


# The double impact (phase 2 only; user 2026-10-03: "雙重衝擊波是二階段的boss招式嗎？如果是的話第二下不用再
# 拔起來插一次了，全身用力往下壓一下就好，不用把劍拔出來"): the first plunge as the ash impact; the sword
# stays in the ground, he stands over it, hands on the hilt; the cross flashes as the second ring's
# danger time begins (frame 84, veltharis_data gives each ring its own); he draws himself up (114 ..
# 118) and throws his whole weight down onto the hilt as the second ring goes out (120: the hips
# drop, the chest goes over the hilt, the arms push down - the sword does not move), straightens up,
# pulls it out (157) and puts it back on the shoulder: recovery 63.
DOUBLE_TOP2 = IMPACT_RING2 - DANGER           # 84: the second ring's danger time begins (the flash)
DOUBLE_PULL2 = 157             # out of the ground; the carry from DOUBLE_END - 2: one pose of it at the end
PRESS = (IMPACT_RING2 - 6, IMPACT_RING2 - 2)  # drawn up, then down onto the hilt
DOUBLE_MUSTS = IMPACT_MUSTS + (DOUBLE_TOP2,) + flash_musts((DOUBLE_TOP2,)) + tuple(range(PRESS[0], IMPACT_RING2 + 2))


def double_keys():
    P2 = IMPACT_RING2
    _, over = impact_planted(0)
    k = impact_raise() + impact_plant(IMPACT_RING)
    k += [
        (PRESS[0], over),
        # drawn up over the hilt, then the whole weight thrown down onto it
        (PRESS[1], carry_key(D=0, lx=-3, fist=over['fist'], dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=-2, ck=-1)),
        (P2, carry_key(D=9, lx=13, fist=over['fist'], dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=9, ck=2)),
        (P2 + 3, carry_key(D=10, lx=14, fist=over['fist'], dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=9, ck=2)),
        (P2 + 14, carry_key(D=5, lx=7, fist=over['fist'], dir=IMPACT_DIR, two=1.0, roll=EDGE, bow=6, ck=1)),
        impact_planted(P2 + 26),
        impact_planted(DOUBLE_PULL2),
    ] + impact_pull(DOUBLE_PULL2)
    return k


def double_impact():
    """雙重衝擊 (phase 2): the plunge at 66, the weight thrown onto the planted sword at 120 (each ring
    with its flash at the start of its danger time), recovery 63 -> 195."""
    poles = _raise_poles(poles_plant(IMPACT_RING), poles_pull(DOUBLE_PULL2))
    return Clip('double_impact', with_poles(double_keys(), poles), {}, musts=DOUBLE_MUSTS, still=True,
                ground=True, lead=False, tall=True, flashes=(IMPACT_TOP, DOUBLE_TOP2))


# ------------------------------------------------------------------ 三斬 (phase 2): the twin slash, then the cleave
# veltharis_data triple_slash: _twin_first, _twin_second(false), _cleave_hit(1.0): the third hit 1.0 s
# (60 frames) after the second starts - frame W2 + 60 = 162, its highest point at W2 + 48 = 150 (the
# delayed version: held 36 frames there, the hit at 198); recovery 1.2 x 0.75 (phase 2 only: the
# sheet is drawn with the cleave's 72-frame recovery and played with hold_phase2's 54).
# The second cut's follow-through (one-handed, the sword low on his right, the left foot 36 px ahead
# of the right, the game having moved him 28 px) runs on into the cleave's raise: the weight comes
# back onto the right foot, the sword is lifted on his right side, the left hand takes the grip
# again, the left foot steps back beside the right (one foot at a time; he does not move forward
# again), and by TRIPLE_TOP - 4 he is in the cleave's highest point - from there on everything is
# the cleave's, about where the game has him (ahead()).
TRIPLE_SHIFT = W2                          # the cleave's frame t is the triple's t + 102
TRIPLE_W3 = CLEAVE_W + TRIPLE_SHIFT        # 162
TRIPLE_TOP = CLEAVE_TOP + TRIPLE_SHIFT     # 150
TRIPLE_END = CLEAVE_END + TRIPLE_SHIFT     # 240 as drawn (phase 1 timing); played with the phase 2 recovery: 222
TRIPLE_LBACK = (128, 138)                  # the left foot back beside the right


def triple_keys():
    k = [kv for kv in twin_keys() if kv[0] <= W2 + 8]
    planted = {'R': STAND, 'L': LF}
    # (the flat as the second cut's edge left it: with the default, lying level, it turned 61 degrees
    # between two poses as the swing slowed down - a flash)
    k.append(ahead(W2 + 16, carry_key(D=10, hx=21.0, ht=-18, tw=-28, lx=13, fist=(31.0, 23.0, 88.0), dir=(116.0, -20.0),
                                      two=0.0, flat=A.unit((-0.91, -0.42, 0.0)), bow=5, ck=1, cs=-4, feet=planted)))
    # the weight back towards the right foot (the hips staying between the feet until the left
    # foot lifts), the sword lifted out on his right, outside the shoulder plate (straight up past
    # it would go through it), the left hand coming back
    k.append(ahead(W2 + 22, carry_key(D=8, hx=11.0, ht=-9, tw=-17, lx=5, fist=(26.0, 23.0, 104.0), dir=(108.0, 14.0),
                                      two=0.3, flat=FLAT_R, bow=2, ck=0, cs=-2, feet=planted)))
    k.append(ahead(TRIPLE_LBACK[0], carry_key(D=7, hx=7.0, ht=-6, tw=-15, lx=2, fist=(23.0, 22.0, 110.0), dir=(110.0, 36.0),
                                              two=0.6, flat=FLAT_R, bow=0, ck=0, cs=-1, feet=planted)))
    # the left foot steps back beside the right (TRIPLE_LBACK) as the sword goes up past the plate
    k.append(ahead(W2 + 30, carry_key(D=4, hx=2.0, ht=-3, tw=-13, lx=-2, fist=(17.0, 16.0, 128.0), dir=(126.0, 60.0),
                                      two=0.5, flat=FLAT_R, bow=-1, ck=-1, feet={'R': STAND, 'L': None}, **overhead(1.12, 1.0))))
    # on up over his head (the cleave's raise): the hilt up over the right shoulder first, then in
    # over the helmet (straight in, the blade would cut through it), the blade back over it, edge-up
    k.append(ahead(W2 + 35, carry_key(D=3, hx=0.0, tw=-8, lx=-4, fist=(11.0, 12.0, 147.0), dir=(150.0, 52.0), two=0.8,
                                      roll=72.0, bow=-2, ck=-2, **overhead(1.3, 2.5))))
    k.append(ahead(W2 + 38, carry_key(D=2, hx=-1.0, tw=-4, lx=-5, fist=(4.0, 4.0, 152.0), dir=(172.0, 54.0), two=1.0,
                                      roll=EDGE, bow=-3, ck=-2, **overhead(1.42, 3.5))))
    k += [ahead(t + TRIPLE_SHIFT, kk) for t, kk in cleave_keys() if t >= CLEAVE_TOP - 4]
    return k


def triple_steps():
    R = [(STEP_FROM, STAND), (W + 3, RF_QUICK)]
    R += [(t + TRIPLE_SHIFT, (f[0] + TWIN_STEP,) + f[1:]) for t, f in cleave_steps()['R']]
    L = [(TWIN_STEP2, STAND), (W2 + 3, ahead(0, carry_key(feet={'R': STAND, 'L': LF}))[1]['feet']['L']),
         (TRIPLE_LBACK[0], (LF[0] + TWIN_STEP,) + LF[1:]), (TRIPLE_LBACK[1], (TWIN_STEP,) + STAND[1:])]
    return {'R': R, 'L': L}


def triple():
    """三斬: the twin slash (hits 48, 102; the game's step before the second), the cleave (hit 162)."""
    poles = {t: v for t, v in POLES_TWIN.items() if t <= W2 + 8}
    poles.update({W2 + 16: ((-0.3, 1.0, -0.4), None), W2 + 22: ((0.0, 1.0, -0.4), (1.0, 0.3, -0.6)),
                  TRIPLE_LBACK[0]: ((0.0, 1.0, -0.2), (0.8, -0.3, -0.5)),
                  W2 + 30: ((0.0, 1.0, 0.1), (0.4, -1.0, -0.3)), W2 + 38: (UP_OUT_R, UP_OUT_L)})
    poles.update({t + TRIPLE_SHIFT: v for t, v in POLES_CLEAVE.items() if t >= CLEAVE_TOP - 4})
    musts = tuple(range(TWIN_STEP_FROM, W2)) + tuple(t + TRIPLE_SHIFT for t in CLEAVE_MUSTS)
    # the edge leads through the twin slash's two cuts (drawn as the twin slash); from the second
    # cut's follow-through on, the keys' flat (lifted up over the head the blade is not cutting:
    # with the edge leading it turned 62 degrees in a pose as the lift sped up - a flash)
    return Clip('triple', with_poles(triple_keys(), poles), triple_steps(), advance=twin_advance, musts=musts,
                still=True, ground=TRIPLE_TOP - 4, lead=W2 + 12, tall=True)


# ------------------------------------------------------------------ choosing the poses
TIP_STEP = 80.0       # px the sword's tip may move on screen between two poses (the Boss's limit, checks_hit)
HAND_STEP = 16.0       # px the fists may move (a part's limit, checks.STEP_MAX)
VIEWS3 = (('front', False), ('right', False), ('back', False), ('right', True))


FORWARD_ON_SCREEN = {'right': (1.0, 0.0), 'front': (0.0, 1.0), 'back': (0.0, -1.0)}   # the game moves him 1:1


def on_screen(view, p, adv, far=False):
    """Screen offset of a 3D point (relative to where the game has the Boss) once the game's
    move `adv` is added (it moves the sprite 1:1 in every view, the top-down ground)."""
    x, y = A.project(view, p, far)
    fx, fy = FORWARD_ON_SCREEN[view]
    return x + fx * adv, y + fy * adv


def screen_step(a, b):
    """Largest on-screen move of the tip and of the right fist between two states, over the views
    (with the game's move between them)."""
    worst_tip = worst_hand = 0.0
    pts = [(A.tip(a), A.tip(b), 'tip'), (a['fist'], b['fist'], 'hand')]
    if a.get('arm_k', 1.0) != 1.0 or b.get('arm_k', 1.0) != 1.0:
        # the arms over the head (the cleave): the left fist is the top of him and goes up faster
        # than the right (it is further along the raised grip) - it is held to the limit too
        la, lb = A.fists(a)[1], A.fists(b)[1]
        if la is not None and lb is not None:
            pts.append((la, lb, 'hand'))
    for view, far in VIEWS3:
        for p, q, kind in pts:
            pa, pb = on_screen(view, p, a.get('adv', 0.0), far), on_screen(view, q, b.get('adv', 0.0), far)
            dd = math.dist(pa, pb)
            if kind == 'tip':
                worst_tip = max(worst_tip, dd)
            else:
                worst_hand = max(worst_hand, dd)
    return worst_tip, worst_hand


def sample(clip, end, must=(), max_hold=6, tip=TIP_STEP * 0.85, hand=HAND_STEP * 0.85):
    """Pose times from 0 to `end` (exclusive): every `must` time, and as few others as keep the
    tip and the fists within their limits (with a margin), no pose held longer than max_hold.
    Returns (times, holds)."""
    must = sorted(set(must) | {0})
    times = [0]
    t = 0
    while True:
        nxt = None
        lim = min([m for m in must if m > t] + [end, t + max_hold])
        for c in range(lim, t, -1):
            a, b = clip.at(t), clip.at(c)
            wt, wh = screen_step(a, b)
            if (wt <= tip and wh <= hand) or c == t + 1:
                nxt = c
                break
        if nxt >= end:
            break
        times.append(nxt)
        t = nxt
    holds = [b - a for a, b in zip(times, times[1:] + [end])]
    return times, holds


# ------------------------------------------------------------------ starting from a move
# The Boss mostly starts an attack straight from moving (WALK -> IDLE -> ATTACK one frame apart,
# boss_sim.gd): the sword is already on the shoulder, the legs are mid-stride and the chest leans
# with the walk. The first poses of the windup then start from the loop's pose: pose 0 IS that
# loop pose (the game shows no jump), and over the next ENTRY_TIMES the feet go from where the
# loop has them to where the attack wants them, the lean from the walk's to the attack's. From
# ENTRY_END on the attack's own poses follow. Like the stop clips: one version for each of the
# loop's poses 0, 5, 10, 15 (the nearest is chosen, at most 2 poses off).
ENTRY_TIMES = (0, 4, 8, 12, 16, 20)
ENTRY_END = 24
ENTRY_FROM = (0, 5, 10, 15)
ENTRY_HALF = 12          # the first foot is under him by then, the second by ENTRY_END


def loop_feet(st):
    """A loop state's (anim_walk.loop_state) legs as this module's feet: (x, out, z, pitch,
    down, lat) - out from the front views' inward shift (anim_walk FEET_IN, STRAFE_IN), lat the
    sidestep's sideways offset (drawn as the sidestep draws it)."""
    out = {}
    for k in 'RL':
        L = st['leg' + k]
        lat = L.get('lat', 0.0)
        out[k] = (L['ankle'][0], -st['in' + k], L['ankle'][1], L['pitch'], L['down'], lat)
    return out


def entry_order(s0, kind):
    """Which foot comes under him first (anim_walk.stop_clip's choice): the one in the air, or
    walking forward the rear one, otherwise the one furthest from under him."""
    legs = {'R': s0['legR'], 'L': s0['legL']}
    air = [k for k in 'RL' if not legs[k]['down']]
    if air:
        return air[0]
    if kind == 'walk':
        return min('RL', key=lambda k: legs[k]['ankle'][0])
    return max('RL', key=lambda k: abs(legs[k]['ankle'][0]) + abs(legs[k].get('lat', 0.0)))


def entry(clip, kind, entry_pose, times=ENTRY_TIMES, half=ENTRY_HALF, end=ENTRY_END, to_end=False):
    """States for `times` starting from loop pose `entry_pose` of `kind` (anim_walk.KINDS);
    the first is the loop pose itself (draw it with anim_walk). One foot at a time (user
    2026-10-01): the first (entry_order) steps under him by `half` while the other stays
    planted (its foot rolling flat), then the other steps under him by `end` (ENTRY_*; the quick
    slashes' shorter windup: QUICK_ENTRY). to_end: each foot goes straight to where the clip has
    it at `end` (the judgment thrust's windup steps the right foot back: from a move it steps
    there directly, not first under him and then back - one step for each foot)."""
    import anim_walk as AW
    s0 = AW.loop_state(entry_pose, kind)
    f0 = loop_feet(s0)
    first = entry_order(s0, kind)
    span = {first: (0, half), ('L' if first == 'R' else 'R'): (half, end)}
    lean0 = AW.LEAN_DEG * AW.LEAN_OF[kind]
    states = poses(clip, list(times))
    goal = clip.at(end)['feet'] if to_end else None
    for st in states:
        t = st['t']
        w = gait.smooth(t / end)
        st['lx'] = lean0 + (st['lx'] - lean0) * w
        st['D'] = round(s0['D'] + (st['D'] - s0['D']) * w)
        feet = {}
        for k in 'RL':
            a, b = f0[k], (goal or st['feet'])[k]
            t0, t1 = span[k]
            u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            ww = gait.smooth(u)
            pitch0 = a[3]
            z0 = a[2]
            if k != first and a[4]:
                # planted, waiting for its step: the foot rolls flat on the ground
                v = gait.smooth(min(1.0, t / half))
                pitch0 = a[3] * (1 - v)
                z0 = a[2] + (gait.ANKLE_H - a[2]) * v
            x = a[0] + (b[0] - a[0]) * ww
            o = a[1] + (b[1] - a[1]) * ww
            z = z0 + (b[2] - z0) * ww
            far = math.hypot(b[0] - a[0], b[1] - a[1]) + abs(a[5]) > 6.0
            if far and 0 < u < 1:
                z += 6.0 * math.sin(math.pi * u)
            pitch = pitch0 + (b[3] - pitch0) * ww
            lat = a[5] * (1 - ww)
            feet[k] = (x, o, max(z, boot_drop(pitch)), pitch, not (far and 0 < u < 1), lat)
        st['feet'] = feet
        st['entry'] = (kind, entry_pose)
        st['name'] = f'{clip.name}_{kind}_{entry_pose}'
    states[0]['loop'] = (kind, entry_pose)
    return states


# ------------------------------------------------------------------ bounced off a perfect parry
# BOUNCED (1.2 s after a heavy hit is parried, boss_sim): the first pose is the attack's own
# contact (the hit box's middle: the blade straight ahead, low). The parry knocks the blade
# up; the left hand is jarred off the grip; the blade goes on up over his head and down onto
# the right shoulder - the way the carry's start clip lifts it (forward, up, over), not back
# through his arm - while he rocks back on his heels and the feet come together: he ends in
# the carry, ready to move (the breather walks next: anim_kneel.carry_start).
BOUNCE_BACK = (10, 28)     # the stepped-in foot comes back under him (the other one never moved)


def bounce_keys(contact, scale=1.0):
    """The bounce from the attack's contact: the knock rocks him back off the front foot onto
    the other (which has stayed where it was since the windup), then the front foot steps back -
    one foot (the steps returned). The hips come back from over the front foot (two thirds of a
    36 px lunge) at no more than the stepping foot's pace, so the front foot lifts only once
    they are over the back one."""
    c = dict(contact)
    front = max('RL', key=lambda k: c['feet'][k][0])
    stance = dict(c['feet'])
    stance = {k_: (f[:2] + (gait.ANKLE_H, 0.0) if k_ != front else f) for k_, f in stance.items()}   # the back heel comes down
    lift = {front: None, ('L' if front == 'R' else 'R'): STAND}
    ht, hx = c['ht'], c['hx']
    T = lambda t: round(t * scale)
    # one-handed (the quick slashes) the free left arm is thrown out by the jar, then hangs
    free = c.get('lfree', 0.0) > 0
    jar = dict(lfree=1.0, lhand=(-10.0, -12.0, 20.0)) if free else {}
    settle = dict(lfree=0.5, lhand=(-4.0, -4.0, 8.0)) if free else {}
    k = [(0, c)]
    k.append((T(4), carry_key(**jar, D=c['D'] - 1, hx=hx - 7.0, ht=0.6 * ht, tw=0, lx=6, fist=(hx + 18.0, 1.0, 108.0), dir=(0.0, 32.0),
                           two=0.5, bow=-6, ck=3, feet=stance)))
    # the hips stay near enough the front foot for it to be lifted (a longer lunge keeps them further on)
    k.append((T(10), carry_key(**settle, D=8, hx=max(6.0, stance[front][0] - 30.0), ht=0.3 * ht, tw=0, lx=-7, fist=(27.0, 6.0, 124.0), dir=(-12.0, 72.0),
                               two=0.0, roll=90.0, bow=-13, ck=5, feet=stance)))
    k.append((T(20), carry_key(D=5, hx=-1.0, tw=0, lx=-10, fist=(18.0, 14.0, 132.0), dir=(162.0, 58.0), two=0.0, roll=40.0,
                               bow=-12, ck=4, feet=lift)))
    k.append((T(34), carry_key(D=2, lx=-6, fist=(16.0, 21.0, 134.0), dir=(162.0, 18.0), bow=-6, ck=2)))
    k.append((T(52), carry_key(lx=-2, bow=-1)))
    k.append((T(66), carry_key()))
    return k, {front: [(T(BOUNCE_BACK[0]), stance[front]), (T(BOUNCE_BACK[1]), STAND)]}


def contact_key(clip, t):
    """The keys' settings at frame t of a clip (to start another clip from that pose)."""
    s = clip.at(t)
    k = carry_key(D=s['D'], hx=s['hx'], ht=s['ht'], lx=s['lx'], tw=s['tw'], bow=s['bow'], ck=s['ck'], cs=s['cs'],
                  fist=s['fist'], dir=A.angles(s['axis']), roll=s['roll'], two=s['two'],
                  lfree=s['lfree'], lhand=s['lhand'], feet={side_: tuple(s['feet'][side_][:4]) for side_ in 'RL'})
    k['poleR'], k['poleL'] = s['poleR'], s['poleL']
    k['swing'] = s.get('swing', 0.0)
    return k


POLES_BOUNCE = {4: (DOWN_R, None), 10: ((0.0, 1.0, -0.4), None), 20: ((-0.2, 1.0, 0.0), None)}


def c1_bounce():
    keys, steps = bounce_keys(contact_key(c1(), W + 4))
    return Clip('c1_bounce', with_poles(keys, POLES_BOUNCE), steps)


def twin_bounce():
    keys, steps = bounce_keys(contact_key(twin(), W2 + 3))
    return Clip('twin_bounce', with_poles(keys, POLES_BOUNCE), steps)


# ------------------------------------------------------------------ C4 裁決突刺 (the judgment thrust), two hands
# veltharis_data judgment_thrust: 起手 0.6 s (36 frames) -> the lunge 0.2 s (12 frames, frames 36 .. 47),
# the hit box on all through it: a capsule SWORD_REACH (150) long, THRUST_WIDTH wide, from where the game
# has him, while the game moves him LUNGE_DISTANCE (160 px) forward, the same each frame (boss_sim) ->
# 收招 0.8 s (48; 二階段 x0.75 -> 36): 96 frames. Heavy: parried, BOUNCED 1.2 s. The punish move (the
# player's posture broken: always this one).
#
# The windup (user 2026-10-04: "劍收到側腰沒錯，要收在右側，同時右腳也要往後張開，左右腳變成左腳在前右腳在後，
# 且打開的寬度大於肩距，身體也要往下前傾"), then after the first version: "突刺的身體還是壓得不夠低，整個身體
# 要彎下去，頭的高度只在劍的上面一點點這麼彎，手要續力到身體後面，讓頭幾乎要跟劍尖一樣位置（比劍尖後面一點），
# 整個人會因為彎腰變扁，腳也要再張開一點，然後彈射出去時是右腳（在後面的腳）用力蹬，讓整個身體飛出去".
# So: the sword comes off the shoulder the way the sweeps put it back (lifted, upright before the right
# shoulder, the tip lowered forward) and is drawn back past his right hip - the fists behind the hips,
# the blade along his right side under the bent chest, its tip out ahead of his face, the edges up and
# down; he bends right over at the waist (bend: the chest turned down about the belt, attack3d.bend_point
# - the lean lx only shears, the head would stay as high), the head lifted to look ahead but only just
# over the blade; the upper body coiled to his right; the right foot alone steps back THRUST_STANCE px
# (the shoulders are 41 apart), the hips low, the weight on the front (left) foot. The blade is 118 px
# from the grip, longer than he is bent over: drawn back as far as the arms go (the right fist 6 px behind
# the hips) its tip is still about THRUST_TIP_AHEAD px past his face.
# The lunge: the right foot drives him off (its leg straightening as the hips go forward over the left
# foot, the heel up), the arms drive the sword straight out, the chest uncoils part way; then he flies -
# both feet off the ground, low and flat, the right leg stretched out behind from the push, the left knee
# reaching through - and lands on the left foot (planted from there, the game carries him over it), the
# right foot coming down behind as the lunge ends. Through the hit box the tip is about 150 px ahead of
# where the game has him (the capsule's end), at the player's height. Each frame of the lunge is a pose of
# its own (the game moves him 13 px a frame). Both feet move in the lunge - the game moves him 160 px in
# 0.2 s; outside it, one foot at a time.
# The recovery: held bent over the front knee a moment (the opening), straightening up as the sword is
# drawn back in, the left foot steps back under him, the sword is lifted upright before the right
# shoulder and laid back on it, the right foot steps up beside the left: the carry, where the game has him.
THRUST_W = 36                                  # the hit box (36 .. 47); the game moves him those 12 frames
LUNGE = 160.0                                  # veltharis_data LUNGE_DISTANCE
LUNGE_FRAMES = 12                              # the hit box's active 0.2 s
THRUST_END = THRUST_W + LUNGE_FRAMES + 48      # 96
THRUST_STANCE = 60.0                           # px the right foot steps back (the shoulders are 41 apart; the first version 44)
THRUST_RB = (-THRUST_STANCE, 0.0, gait.ANKLE_H, 0.0)
THRUST_LAND = {'R': (-40.0, 0.0, gait.ANKLE_H, 0.0), 'L': (14.0, 0.0, gait.ANKLE_H, 0.0)}   # about where the game ends
THRUST_RSTEP = (10, 22)                        # the right foot steps back
THRUST_LLAND = THRUST_W + 10                   # the left foot lands (in the air from THRUST_W)
THRUST_RLAND = THRUST_W + 11                   # the right foot comes down behind
THRUST_LBACK = (62, 72)                        # recovery: the left foot steps back under him
THRUST_RUP = (76, 88)                          # ... then the right foot up beside it
THRUST_REACH = 40.0                            # px the right fist is ahead of the hips with the arms driven out
THRUST_BEND = 62.0                             # degrees bent at the waist, driven out (cocked: 64)
THRUST_TIP_AHEAD = 83                          # px the cocked tip is ahead of his head's centre (measured; about 70 past the face)
# from a move the sword comes off the shoulder and swings up before it fast: every 2 frames (every 4
# the tip moved 100-107 px a pose, as the ash impact's)
THRUST_ENTRY = (tuple(range(0, ENTRY_END, 2)), ENTRY_HALF, ENTRY_END, True)


def lunge_advance(t):
    """px the game has moved him forward at combat frame t (after that frame's update)."""
    return LUNGE * min(1.0, max(0.0, (t - THRUST_W + 1) / LUNGE_FRAMES))


def _lunging(t, k):
    """A key written about where the game has him at frame t, put on the ground."""
    return ahead(t, k, dx=lunge_advance(t))


def _cocked(**kw):
    """Bent right over, the sword drawn back past the right hip, the wide stance, coiled to his right.
    The head lifted (bow < 0) to look ahead over the blade."""
    k = carry_key(D=28, hx=-12.0, ht=-16, tw=-30, lx=0, bend=64.0, bow=-38, ck=-3, cs=-2, fist=(-7.0, 18.0, 62.0),
                  dir=(-16.0, -4.0), roll=EDGE, two=1.0, feet={'R': THRUST_RB, 'L': STAND})
    k.update(kw)
    return k


def _thrust_out(**kw):
    """The sword driven out ahead, both arms straight, bent right over (the head just over the hands)."""
    k = carry_key(D=24, hx=6.0, ht=-2, tw=-15, lx=0, bend=THRUST_BEND, bow=-38, ck=-5, cs=-1, dir=(0.0, -13.0), roll=EDGE,
                  two=1.0, feet={'R': None, 'L': None})
    k.update(kw)
    if 'fist' not in kw:
        k['fist'] = (k['hx'] + THRUST_REACH, 2.0, 88.0 - k['D'])      # the arms out from the shoulders, wherever the hips are
    if 'dir' not in kw:
        k['dir'] = (0.0, -13.0 - 0.5 * (24 - k['D']))                 # higher in the air, the tip angled down to stay at his height
    return k


def thrust_keys():
    W_ = THRUST_W
    k = [(0, carry_key()),
         # off the shoulder the way the sweeps put it back, reversed: lifted, the left hand coming up,
         # upright before the right shoulder, then the tip lowered forward as he starts to bend
         (6, carry_key(D=1, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), roll=30.0, two=0.2)),
         (12, carry_key(D=6, tw=-8, lx=2, bend=8.0, fist=(21.0, 12.0, 120.0), dir=(-18.0, 80.0), flat=FLAT_R, two=0.6)),
         (18, carry_key(D=16, hx=-8.0, ht=-8, tw=-26, bend=34.0, bow=-15, ck=-1, fist=(14.0, 11.0, 92.0), dir=(-6.0, 6.0),
                        roll=EDGE, two=1.0, feet={'R': None, 'L': STAND})),
         # cocked: drawn back past the right hip, bent right over, the right foot back - held (the read)
         (24, _cocked(D=26, hx=-11.5, tw=-29, bend=62.0, bow=-37, ck=-2, fist=(-6.0, 18.0, 63.0), dir=(-15.0, -4.0))),
         (32, _cocked()),
         # the drive: the right leg pushes the hips forward over the left foot, the fists go forward,
         # the chest uncoils, the right heel comes up (a pose a frame: the fists travel 12-16 px a frame)
         (W_ - 3, _cocked(D=27, hx=-10.0, ht=-14, tw=-28, bend=63.5, bow=-38, fist=(3.0, 14.0, 62.0), dir=(-11.0, -7.0))),
         (W_ - 2, _cocked(D=26, hx=-7.0, ht=-10, tw=-25, bend=63.0, bow=-38, fist=(15.0, 9.0, 62.0), dir=(-6.0, -10.0))),
         (W_ - 1, _cocked(D=26, hx=-4.5, ht=-6, tw=-23, bend=62.5, bow=-38, fist=(27.0, 5.0, 62.0), dir=(-3.0, -12.0)))]
    # the lunge, about where the game has him: a key every frame (the game moves him every frame). The
    # game starts at 13 px a frame at once: the hips drop back behind where it has him for the first
    # frames (on screen he speeds up instead of jumping 19 px), then come on over the front foot as it
    # lands. In the air the hips ride a little higher; they land low again
    hxs = (-6.0, -7.0, -6.5, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0)
    Ds = (25, 23, 21, 19, 18, 18, 18, 19, 20, 22, 24, 24)
    cks = (-4, -5, -6, -6, -6, -6, -6, -5, -4, -3, -2, -2)
    tws = (-21, -17, -15, -15, -15, -15, -15, -15, -15, -15, -15, -15)
    for i, (h, D_, c, w) in enumerate(zip(hxs, Ds, cks, tws)):
        k.append(_lunging(W_ + i, _thrust_out(hx=h, D=D_, ck=c, tw=w,
                                              feet=(THRUST_LAND if i == LUNGE_FRAMES - 1 else {'R': None, 'L': None}))))
    # stopped: held there a frame (the game stops at once)
    k.append(ahead(W_ + LUNGE_FRAMES, _thrust_out(hx=2.0, ck=-2, feet=THRUST_LAND), dx=LUNGE))
    # recovery, where the game ends (LUNGE on)
    end = lambda t, kk: ahead(t, kk, dx=LUNGE)
    land = THRUST_LAND
    k += [end(51, _thrust_out(D=24, hx=3.0, ck=1, feet=land)),
          end(56, _thrust_out(D=24, hx=2.5, bend=58.0, bow=-36, ck=0, feet=land)),
          # straightening up, drawn back in, the weight back between the feet; the left foot steps back
          end(THRUST_LBACK[0], carry_key(D=18, hx=-2.0, ht=-8, tw=-22, bend=30.0, bow=-18, ck=-1, fist=(22.0, 8.0, 80.0),
                                         dir=(-6.0, -4.0), roll=EDGE, two=1.0, feet=land)),
          end(THRUST_LBACK[1], carry_key(D=12, hx=-12.0, ht=-8, tw=-14, bend=8.0, lx=2, bow=-4, fist=(14.0, 10.0, 100.0),
                                         dir=(-10.0, 34.0), roll=EDGE, two=1.0, feet={'R': land['R'], 'L': STAND})),
          # upright before the right shoulder, laid back on it; the right foot up beside the left
          end(78, carry_key(D=6, hx=-8.0, ht=-4, tw=-6, lx=3, fist=(14.0, 12.0, 120.0), dir=(-18.0, 80.0), flat=FLAT_R,
                            two=0.5, feet={'R': None, 'L': STAND})),
          end(86, carry_key(D=2, hx=-1.0, fist=(16.0, 20.0, 131.0), dir=(162.0, 40.0), roll=30.0, two=0.0)),
          end(93, carry_key())]
    return k


def thrust_steps():
    W_ = THRUST_W
    adv = lunge_advance
    H_ = gait.ANKLE_H
    # the push: the heel comes up as the drive starts (the toe on the ground), then the right leg is
    # stretched out behind him in the air and comes down behind as he lands (a key every frame: the
    # foot is where it is drawn)
    R = [(THRUST_RSTEP[0], STAND), (THRUST_RSTEP[1], THRUST_RB), (W_ - 3, THRUST_RB), (W_ - 1, THRUST_RB[:3] + (-35.0,))]
    rair = {W_: (-60.0, 24.0, -50.0), W_ + 1: (-60.0, 27.0, -45.0)}
    for t, x in zip(range(W_ + 2, THRUST_RLAND - 2), (-58.0, -56.0, -55.0, -53.5, -52.5, -51.0, -49.0)):
        rair[t] = (x, 28.0, -38.0)
    rair[THRUST_RLAND - 2] = (-47.0, 24.0, -25.0)
    rair[THRUST_RLAND - 1] = (-43.0, 19.0, -10.0)
    R += [(t, (x + adv(t), 0.0, z, p)) for t, (x, z, p) in sorted(rair.items())]
    R += [(THRUST_RLAND, (THRUST_LAND['R'][0] + LUNGE,) + THRUST_LAND['R'][1:])]
    R += [(THRUST_RUP[0], (THRUST_LAND['R'][0] + LUNGE,) + THRUST_LAND['R'][1:]), (THRUST_RUP[1], (LUNGE,) + STAND[1:])]
    lw = THRUST_LAND['L'][0] + LUNGE
    # the left foot leaves the ground with the push and reaches through in the air (lifted, the toe
    # coming up to land on the heel), lands ahead of him; planted from there on while the game carries
    # him over it
    air = ((-8.0, 19.0, 0.0), (-4.0, 22.0, 0.0), (3.0, 23.0, 2.0), (10.0, 24.0, 4.0), (17.0, 24.0, 6.0),
           (24.0, 23.0, 8.0), (30.0, 22.0, 9.0), (34.0, 21.0, 10.0), (37.0, 19.5, 10.0), (38.0, H_ + 1.5, 8.0))
    L = [(W_ - 1, STAND)] + [(W_ + i, (x + adv(W_ + i), 0.0, z, p)) for i, (x, z, p) in enumerate(air)]
    L += [(THRUST_LLAND, (lw,) + THRUST_LAND['L'][1:]),
          (THRUST_LBACK[0], (lw,) + THRUST_LAND['L'][1:]), (THRUST_LBACK[1], (LUNGE,) + STAND[1:])]
    return {'R': R, 'L': L}


POLES_THRUST = {
    6: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)), 12: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)),
    18: (RISE_R, (0.6, -0.2, -1.0)),
    # cocked: the right elbow back and out behind the hip, the left across under the chest
    24: ((-1.0, 0.6, 0.0), (0.2, 0.2, -1.0)), 32: ((-1.0, 0.6, 0.0), (0.2, 0.2, -1.0)),
    THRUST_W - 3: ((-0.9, 0.6, -0.3), (0.3, 0.0, -1.0)), THRUST_W - 2: ((-0.6, 0.8, -0.6), (0.2, -0.2, -1.0)),
    THRUST_W - 1: ((-0.2, 0.8, -0.8), (0.1, -0.4, -1.0)),
    THRUST_W: (DOWN_R, DOWN_L), THRUST_W + 4: (DOWN_R, DOWN_L), THRUST_W + 8: (DOWN_R, DOWN_L),
    THRUST_W + 11: (DOWN_R, DOWN_L), THRUST_W + 12: (DOWN_R, DOWN_L), 51: (DOWN_R, DOWN_L), 56: (DOWN_R, DOWN_L),
    THRUST_LBACK[0]: ((-0.5, 0.8, -0.6), (0.2, -0.3, -1.0)), THRUST_LBACK[1]: (RISE_R, RISE_L),
    78: ((-0.1, 1.0, -0.6), (0.6, -0.4, -1.0)),
}


def thrust():
    """裁決突刺: windup 36, the lunge (hit box) 36 .. 47 with the game moving him 160 px, recovery 48 -> 96."""
    # musts: every frame of the lunge (the game moves him); every other frame as the weight comes back
    # off the front foot and he straightens; lead False: a thrust, not a cut - the edges stay up and
    # down while it drives out (with the edge leading the flat turned flat)
    # exact_cape (2026-10-05, user: "修"): crouched 28 px the side cape no longer stands over his head
    return Clip('thrust', with_poles(thrust_keys(), POLES_THRUST), thrust_steps(), advance=lunge_advance,
                musts=tuple(range(THRUST_W, THRUST_W + LUNGE_FRAMES + 1)) + THRUST_BACK_MUSTS, lead=False,
                exact_cape=True)


THRUST_BACK_MUSTS = tuple(range(52, 74, 2))
THRUST_CONTACT = THRUST_W + 11       # the bounce starts from the lunge's last frame (landed, the sword out)


def thrust_bounce():
    """Parried (BOUNCED 1.2 s): the sword knocked up and back over his head onto the shoulder, he is
    jolted upright (the bend gone in a few frames) and rocks back onto the right foot; the left foot
    steps back under him, then the right foot up beside it - one foot at a time - into the carry, where
    the game has him."""
    c = contact_key(thrust(), THRUST_CONTACT)          # about where the game has him (it does not move now)
    c['bend'] = THRUST_BEND
    fL, fR = c['feet']['L'], c['feet']['R']
    k = [(0, c),
         (4, carry_key(D=c['D'] - 4, hx=c['hx'] - 6.0, ht=-2, tw=-4, bend=30.0, bow=-14, ck=3, fist=(c['hx'] + 24.0, 2.0, 92.0),
                       dir=(0.0, 30.0), two=0.5, feet={'R': fR, 'L': fL})),
         (10, carry_key(D=12, hx=-6.0, ht=-4, tw=0, lx=-7, bend=4.0, fist=(21.0, 6.0, 122.0), dir=(-12.0, 72.0), two=0.0,
                        roll=90.0, bow=-13, ck=5, feet={'R': fR, 'L': fL})),
         (20, carry_key(D=11, hx=-14.0, ht=-4, lx=-10, fist=(4.0, 14.0, 132.0), dir=(162.0, 58.0), two=0.0, roll=40.0,
                        bow=-12, ck=4, feet={'R': fR, 'L': None})),
         (34, carry_key(D=8, hx=-13.0, ht=-3, lx=-6, fist=(3.0, 21.0, 134.0), dir=(162.0, 18.0), bow=-6, ck=2,
                        feet={'R': fR, 'L': STAND})),
         (52, carry_key(D=2, hx=-1.0, lx=-2, bow=-1, fist=(CARRY_FIST[0] - 1.0,) + CARRY_FIST[1:], feet={'R': None, 'L': STAND})),
         (60, carry_key(D=1, bow=-0.5)),
         (66, carry_key())]
    steps = {'L': [(12, fL), (28, STAND)], 'R': [(36, fR), (52, STAND)]}
    return Clip('thrust_bounce', with_poles(k, {4: (DOWN_R, None), 10: ((0.0, 1.0, -0.4), None),
                                                20: ((-0.2, 1.0, 0.0), None)}), steps, exact_cape=True)


# ------------------------------------------------------------------ C6 灰燼迴旋 (the ash spin), one hand, phase 2
# veltharis_data ash_spin (user 2026-10-04: one turn, one hit - it was two): 起手 0.9 s (54 frames) -> 判定 0.25 s
# (15: 54 .. 68), a circle of SPIN_RADIUS 165 all round him -> 收招 1.2 s (72; phase 2's own, not shortened): 141
# frames. Heavy; parried it bounces him 1.2 s. The user: "迴旋用右手單手拿劍轉一圈的過程蹲下，所以轉完會是蹲下狀態" -
# the sword in the right hand alone, one full turn, crouching down as he turns: he ends it crouched.
# The windup (boss-veltharis §5.1: the greatsword dragging, the body twisting): the right hand takes the sword off the
# shoulder down to his right side, the blade trailing behind him on his right, its tip on the ground; the left foot
# steps in under him (it will be the pivot: the game does not move him, he turns about where he stands); the hips and
# the chest coil round to his right, he sinks; the blade lifts off the ground as the turn starts.
# The turn (the hit box, a frame each): round to his left, the whole body (hips leading the chest), 24 degrees a
# frame - the blade, the straight right arm out on his right, sweeps the full circle at knee height (the tip 150+ px
# out); he pivots on the ball of the left foot (heel up) and the right foot comes off the ground and round with him
# (tucked behind the pivot), crouching and bending over as he goes; the free left arm flung out for balance, the
# cape flying out behind the turn. Each view draws him with the facing he is nearest (Clip(spin=True),
# anim_attack.render_spun). The turn runs on past the target: the right foot lands behind him (a wide crouch), the
# arm whips the blade across his front to his left and it stops there, low; he holds the crouch (the opening).
# Then he rises, the right foot steps up, the sword comes back before him, upright before the right shoulder, onto
# it; the left foot steps back out to its place: the carry. Turned a full circle, the carry is at tw 360.
SPIN_W = 54                   # the hit box (54 .. 68)
SPIN_N = 15
SPIN_END = SPIN_W + SPIN_N + 72      # 141
SPIN_RATE = 24.0              # degrees a frame through the hit box
SPIN_LIN = (32, 42)           # the left foot steps in under him (the pivot)
SPIN_RUP = 52                 # the right foot leaves the ground
SPIN_RLAND = SPIN_W + SPIN_N + 1     # ... and lands behind him (70)
SPIN_HOLD = (76, 90)          # crouched, the blade stopped low on his left (the opening)
SPIN_RBACK = (96, 108)        # the right foot steps up beside the pivot
SPIN_LBACK = (118, 128)       # the left foot steps back out to its place
SPIN_DRAG = (148.0, -31.0)    # the blade trailing behind him on his right, the tip on the ground
LPIVOT = (0.0, -17.0, gait.ANKLE_H, 0.0)         # the left foot in under him (on the centre line): the pivot
LPIVOT_UP = (0.0, -17.0, gait.ANKLE_H, -20.0)      # on the ball, the heel up
RTUCK = (-12.0, -11.0, gait.ANKLE_H + 10.0, -25.0)  # the right foot in the air, behind the pivot (the hips' frame)
RBEHIND = (-44.0, -13.0, gait.ANKLE_H, 0.0)         # landed behind him
SPIN_ARM = 0.98               # the sword arm straight
SPIN_BEND = 10.0              # degrees bent over by the end of the turn (more as it runs on)


def spin_heading(t):
    """The body's turn (degrees, + = to his left) through the hit box and the run-on: SPIN_RATE a frame from -20
    at the hit box's first frame, easing to 360 three frames after it."""
    if t <= SPIN_W + SPIN_N:
        return -20.0 + SPIN_RATE * (t - SPIN_W)
    run = {SPIN_W + SPIN_N + 1: 350.0, SPIN_W + SPIN_N + 2: 356.0, SPIN_W + SPIN_N + 3: 359.0}
    return run.get(t, 360.0)


def _spin_fist(k, arm_az, arm_el):
    """The straight sword arm (its direction in the upper body's frame: azimuth + = his right, elevation) -> the
    right fist, from where the shoulder goes with the arm (quick_arms)."""
    st = dict(k, whole_turn=True)
    u = A.yaw(A.direction(arm_az, arm_el), k['tw'])
    sh = A.add(A.shoulder('R', st), A.sub(A._girdle('R', u, k['tw'], k['swing']), A.carry_girdle()))
    return A.add(sh, A.mul(u, SPIN_ARM * A.ARM))


def _drag(t, tw, ht, D, fx, fr, psi, **kw):
    """A key of the drag: the right fist at (fx, fr) and the height that puts the tip on the ground (DRAG_TIP up),
    the blade at azimuth psi."""
    k = carry_key(D=D, tw=tw, ht=ht, roll=90.0, **kw)
    k['fist'] = (fx, fr, DRAG_FIST_Z - 0.0)
    el = -math.degrees(math.asin((DRAG_FIST_Z - D * 0.0 - DRAG_TIP) / A.SWORD_LEN))
    k['dir'] = (psi, el)
    return t, k


DRAG_FIST_Z = 72.0            # the right fist at the hip, the arm hanging (the shoulder 112 up, the arm 36 long)
DRAG_TIP = 2.5                # px: the tip on the ground (touching it; the curve between the keys dips a px)


def spin_keys():
    k = [(0, carry_key())]
    # off the shoulder, out and down to his right side, the blade trailing back (the quick slash's way off it)
    k.append((3, carry_key(D=1, tw=-6, lx=0.3, fist=(12.0, 27.0, 132.0), dir=(157.0, 10.0), flat=FLAT_R,
                           lfree=0.25, lhand=(3.0, 3.0, 4.0))))
    k.append((6, carry_key(D=1, tw=-9, ht=-2, lx=1, fist=(8.0, 32.0, 128.0), dir=(153.0, 12.0), flat=FLAT_R,
                           lfree=0.5, lhand=(5.0, 2.0, 6.0))))
    k.append((11, carry_key(D=2, tw=-11, ht=-4, lx=1, fist=(4.0, 34.0, 112.0), dir=(151.0, -6.0), roll=30.0,
                            lfree=0.7, lhand=(7.0, 1.0, 7.0))))
    k.append((17, carry_key(D=3, tw=-13, ht=-6, lx=2, fist=(1.0, 34.0, 90.0), dir=(150.0, -24.0), roll=70.0,
                            lfree=0.85, lhand=(8.0, 0.0, 8.0))))
    lh = dict(lfree=1.0, lhand=(10.0, -2.0, 10.0))
    k.append(_drag(23, -15, -8, 4, -2.0, 34.0, 148.0, lx=3, bow=2, **lh))
    k.append(_drag(30, -15, -8, 4, -2.0, 34.0, 148.0, lx=3, bow=2, **lh))
    # the coil: hips and chest round to his right, sinking; the left foot steps in under him (SPIN_LIN), the
    # blade dragged where it lies (the tip stays on the ground behind him on his right)
    k.append(_drag(36, -30, -18, 5, -4.0, 33.0, 149.0, lx=3, bow=2, ck=-1, cs=-1, lfree=1.0, lhand=(12.0, 1.0, 12.0)))
    k.append(_drag(43, -50, -32, 8, -8.0, 31.0, 150.0, lx=3, bow=2, ck=-2, cs=-3, lfree=1.0, lhand=(14.0, 4.0, 14.0),
                   feet={'R': STAND, 'L': LPIVOT}))
    k.append(_drag(50, -64, -46, 10, -11.0, 30.0, 148.0, lx=3, bow=3, ck=-3, cs=-4, lfree=1.0, lhand=(16.0, 6.0, 16.0),
                   feet={'R': STAND, 'L': LPIVOT_UP}))
    # the turn: the blade lifted off the ground as it starts (the edge turning from down to leading), then the hit
    # box a frame each: crouching as he turns (bent only a little: bent over far, the side views' cape rides up over
    # the head and the four drawings jump as the facing changes), then bending over as the turn runs on
    k.append((SPIN_RUP, carry_key(D=11, tw=-54, ht=-40, lx=2, bow=3, fist=(-8.0, 33.0, 72.0), dir=(132.0, -24.0), roll=70.0,
                                  lfree=1.0, lhand=(12.0, 0.0, 16.0), ck=-3, cs=-2, feet={'R': None, 'L': LPIVOT_UP})))
    blade = {t: 90.0 - spin_heading(t) for t in range(SPIN_W, SPIN_W + SPIN_N + 1)}       # the blade's azimuth (world)
    for t, psi in zip(range(SPIN_W + SPIN_N + 1, SPIN_HOLD[0] + 1), (-274.0, -298.0, -321.0, -342.0, -360.0, -374.0, -382.0)):
        blade[t] = psi
    for t in range(SPIN_W, SPIN_HOLD[0]):
        H = spin_heading(t) if t <= SPIN_W + SPIN_N + 3 else 360.0
        u2 = min(1.0, max(0.0, (t - SPIN_W) / SPIN_N))
        run = t > SPIN_W + SPIN_N
        j = t - SPIN_W - SPIN_N
        D = round(12 + 14 * u2) if not run else 26
        bend = SPIN_BEND * u2 if not run else min(32.0, SPIN_BEND + 4.0 * j)
        tw = H - 8.0 if not run else H - 8.0 + 2.0 * j
        b_az = blade[t] + tw                     # the blade in the upper body's frame
        b_el = -20.0 + 6.0 * u2 if not run else -14.0 - 1.0 * j
        arm_az = b_az + 6.0 if not run else b_az + 4.0
        roll = max(0.0, 45.0 - 25.0 * (t - SPIN_W))
        kk = carry_key(D=D, tw=tw, ht=H + 8.0 - (2.0 * j if run else 0.0), hx=-1.4 * j if run else 0.0, lx=0, bend=bend,
                       bow=-8.0 * u2, swing=1.0, lfree=1.0,
                       lhand=(-14.0, -10.0, 24.0), ck=-4, cs=7, feet={'R': None, 'L': LPIVOT_UP}, two=0.0, roll=roll)
        kk['fist'] = _spin_fist(kk, arm_az, -38.0 if not run else -40.0)
        kk['dir'] = (b_az - tw, b_el)
        if run:
            kk['feet'] = {'R': RBEHIND, 'L': LPIVOT_UP if t < SPIN_RLAND + 2 else LPIVOT}
        k.append((t, kk))
    # held crouched, the blade stopped low on his left before him, the left arm out (the opening)
    hold = carry_key(D=26, tw=366.0, ht=358.0, hx=-8.0, bend=32.0, bow=-14, swing=1.0, lfree=1.0, lhand=(-8.0, -14.0, 22.0),
                     ck=-1, cs=3, feet={'R': RBEHIND, 'L': LPIVOT})
    hold['fist'] = _spin_fist(hold, -12.0, -40.0)
    hold['dir'] = (-382.0, -20.0)
    k.append((SPIN_HOLD[0], hold))
    k.append((SPIN_HOLD[1], hold))
    # the weight onto the left foot, the right foot steps up beside it while he rises; the blade back round before
    # him and up, upright before the right shoulder, onto it; then the left foot back out to its place
    k.append((94, carry_key(D=24, tw=362.0, ht=360.0, hx=-1.0, bend=24.0, bow=-8, fist=(30.0, -6.0, 66.0),
                            dir=(-28.0 - 362.0, -6.0), roll=40.0, swing=0.6, lfree=0.8, lhand=(-6.0, -10.0, 16.0),
                            feet={'R': RBEHIND, 'L': LPIVOT})))
    k.append((SPIN_RBACK[0], carry_key(D=22, tw=360.0, ht=360.0, hx=0.5, bend=14.0, bow=-3, fist=(28.0, 0.0, 96.0),
                                       dir=(-30.0 - 360.0, 50.0), roll=60.0, swing=0.3, lfree=0.6, lhand=(0.0, -4.0, 8.0),
                                       feet={'R': None, 'L': LPIVOT})))
    k.append((SPIN_RBACK[1], carry_key(D=6, tw=360.0, ht=360.0, hx=0.0, lx=1, fist=(21.0, 12.0, 122.0), dir=(-18.0 - 360.0, 80.0),
                                       flat=FLAT_R, lfree=0.3, lhand=(0.0, -2.0, 4.0), feet={'R': STAND, 'L': LPIVOT})))
    k.append((SPIN_LBACK[0], carry_key(D=3, tw=360.0, ht=360.0, hx=1.5, fist=(17.0, 20.0, 131.0), dir=(162.0 - 360.0, 40.0),
                                       roll=30.0, lfree=0.0, feet={'R': STAND, 'L': LPIVOT})))
    k.append((SPIN_LBACK[1], carry_key(D=1, tw=360.0, ht=360.0, dir=(CARRY_DIR[0] - 360.0, CARRY_DIR[1]))))
    k.append((SPIN_END - 6, carry_key(tw=360.0, ht=360.0, dir=(CARRY_DIR[0] - 360.0, CARRY_DIR[1]))))
    return k


def spin_steps():
    """The feet: the left steps in under him (the pivot) and back out at the end; the right comes off the ground
    as the turn starts, round with him in the air (tucked behind the pivot in the hips' frame: a key a frame),
    lands behind him, then steps up beside the pivot."""
    R = [(SPIN_RUP, STAND)]
    for t in range(SPIN_RUP + 1, SPIN_RLAND):
        H = spin_heading(t) + 8.0 if t >= SPIN_W else -44.0 + 4.0 * (t - SPIN_RUP)
        w = min(1.0, (t - SPIN_RUP) / 3.0)
        # from its place to the tuck, carried round with the hips
        bx = RTUCK[0] * w
        br = AT_R(RTUCK[1]) * w + 17.0 * (1 - w)
        x, r, _ = A.yaw((bx, br, 0.0), H)
        R.append((t, (x, r - 17.0, RTUCK[2] * w + gait.ANKLE_H * (1 - w), RTUCK[3] * w)))
    R += [(SPIN_RLAND, RBEHIND), (SPIN_RBACK[0], RBEHIND), (SPIN_RBACK[1], STAND)]
    L = [(SPIN_LIN[0], STAND), (SPIN_LIN[1], LPIVOT), (SPIN_LBACK[0], LPIVOT), (SPIN_LBACK[1], STAND)]
    return {'R': R, 'L': L}


def AT_R(out):
    """The right foot's sideways place (+ = his right) for an 'out' from its hip's line."""
    return 17.0 + out


POLES_SPIN = {
    9: ((0.1, 1.0, -0.4), (0.0, -0.6, -1.0)), 24: ((-0.4, 1.0, -0.6), (0.4, -0.6, -1.0)),
    30: ((-0.4, 1.0, -0.6), (0.4, -0.6, -1.0)), 50: ((-0.6, 1.0, -0.4), (0.6, -0.4, -1.0)),
}


def spin():
    """灰燼迴旋 (phase 2; one turn, one hit since 2026-10-04): windup 54, the turn (hit box) 54 .. 68, recovery 72 ->
    141 frames."""
    keys = with_body_poles(spin_keys(), POLES_SPIN)
    for t, kk in keys:
        if SPIN_W <= t <= SPIN_HOLD[1]:
            kk['poleR'] = A.yaw((-0.2, 1.0, -0.6), kk['tw'])
            kk['poleL'] = A.yaw(POLE_L_BODY, kk['tw'])
    # lead False: the keys' flat all through (the edge turns from down, dragging, to leading as the turn starts:
    # with the edge led by the speed it turned 50 degrees in a pose as the blade lifted)
    return Clip('spin', keys, spin_steps(), whole_turn=True, spin=True,
                musts=tuple(range(SPIN_RUP, SPIN_HOLD[0] + 1)), lead=False, exact_cape=True)


SPIN_CONTACT = SPIN_W + 5     # the blade straight ahead in the turn (the bounce starts here)


def spin_bounce():
    """The spin parried (BOUNCED 1.2 s) as the blade passes straight ahead: the turn is knocked back the way it came
    (the body unwinds to face the target), the blade up over his head and down onto the shoulder; the right foot,
    in the air, comes down under him, he rises out of the crouch, the left foot steps back out to its place."""
    c = contact_key(spin(), SPIN_CONTACT)
    s = spin().at(SPIN_CONTACT)
    c['bend'] = s['bend']
    c['feet'] = {'R': None, 'L': LPIVOT_UP}
    tw, ht = c['tw'], c['ht']
    k = [(0, c),
         (4, carry_key(D=c['D'] - 1, tw=tw - 34.0, ht=ht - 34.0, bend=8.0, lx=2, bow=-8, fist=None, dir=(-30.0, 40.0),
                       roll=60.0, swing=0.6, lfree=1.0, lhand=(-10.0, -12.0, 20.0), ck=3, cs=-4, feet={'R': None, 'L': LPIVOT})),
         (10, carry_key(D=12, tw=16.0, ht=10.0, lx=-7, fist=(26.0, 6.0, 122.0), dir=(-12.0, 72.0), roll=90.0, bow=-13, ck=5,
                        swing=0.3, lfree=0.6, lhand=(-4.0, -4.0, 8.0), feet={'R': STAND, 'L': LPIVOT})),
         (20, carry_key(D=7, tw=4.0, ht=2.0, lx=-10, fist=(18.0, 14.0, 132.0), dir=(162.0, 58.0), roll=40.0, bow=-12, ck=4,
                        lfree=0.2, lhand=(0.0, 0.0, 2.0), feet={'R': STAND, 'L': LPIVOT})),
         (34, carry_key(D=3, lx=-6, fist=(16.0, 21.0, 134.0), dir=(162.0, 18.0), bow=-6, ck=2, feet={'R': STAND, 'L': LPIVOT})),
         (52, carry_key(lx=-2, bow=-1)),
         (66, carry_key())]
    # the knocked blade at frame 4: up off his front, where the arm is swung back to
    st = dict(k[1][1], whole_turn=True)
    k[1][1]['fist'] = _spin_fist(st, 40.0, -10.0)
    steps = {'R': [(0, spin().at(SPIN_CONTACT)['feet']['R'][:4]), (8, STAND)],
             'L': [(36, LPIVOT), (50, STAND)]}
    poles = {4: (A.yaw((0.0, 1.0, -0.4), k[1][1]['tw']), A.yaw(POLE_L_BODY, k[1][1]['tw'])),
             10: ((0.0, 1.0, -0.4), A.yaw(POLE_L_BODY, 16.0)), 20: ((-0.2, 1.0, 0.0), None)}
    return Clip('spin_bounce', with_poles(k, poles), steps, whole_turn=True, spin=True, exact_cape=True)


# ------------------------------------------------------------------ C7 墜王之躍 (the king's leap), phase 2
# veltharis_data kings_leap: 起手 0.7 s (42 frames, the crouch) -> in the air 0.8 s (frames 42 .. 89: the game moves him
# in a straight line from where he took off to where he lands, the distance not fixed; the landing place follows the
# player until 0.3 s before it lands, frame 72) -> the landing is the hit, 判定 0.1 s (90 .. 95), a circle of
# LEAP_RADIUS 80 round him, launching -> 收招 1.0 s (60; phase 2's own): 156 frames. Heavy: parried, 1.2 s.
# User 2026-10-04: "劍會收放在背上（斜掛著），然後蹲下蓄力準備起跳，起跳後落地用右手全頭砸向地面，之後再把劍從背上拿下來
# 恢復正常姿勢" ("全頭" is 拳頭: the right fist). So: the right hand lifts the sword off the shoulder and slings it on his
# back (attack3d.back_sword: the grip behind the right shoulder, the blade down across his back), lets go; he sinks
# into a deep crouch, both arms swung back, and springs: the legs and the arms drive him up, he leaves the ground. In
# the air (the height is drawn in the sprite: lift; the game moves him along the ground, the feet are off it) he
# rises, the legs tucked, then as the landing place is locked he tips forward, the right fist drawn up and back, and
# comes down: the left foot reaching ahead, the right knee down behind (the approved kneel's legs), the right fist
# smashed into the ground before him on his right as he lands - the hit (the shockwave is the code's). With his short
# arms (a helmet a third of his height) the fist reaches the ground only bent right over in the kneel and with the
# arm drawn longer for the blow (arm_k, as the cleave's arms over the head; at most ARM_K_MAX). The fist stays down
# through the impact; he rises, reaches back over the right shoulder for the hilt, draws the sword up out along its
# line, swings it up over his head and forward, upright before the right shoulder and back onto it; the right foot,
# then the left, step back under him: the carry.
LEAP_UP = 42                  # off the ground (veltharis_data airborne_start 0.7 s)
LEAP_LOCK = 72                # the landing place locked (lock_before 0.3 s)
LEAP_W = 90                   # landed: the hit box (90 .. 95)
LEAP_END = LEAP_W + 6 + 60    # 156
LEAP_PEAK = 92.0              # px off the ground at the top of the leap
LEAP_BACK = (16, 118)         # the sword on his back, the right hand free
LEAP_CROUCH = (26, 37)        # down in the crouch, gathering himself for the leap
LEAP_ENTRY = (tuple(range(0, LEAP_BACK[0], 2)), 8, LEAP_BACK[0])  # starting from a move: both feet under him before he sinks
#   (ENTRY_*; a pose every 2 frames: the sling is quick)
LEAP_SMASH = (LEAP_W, 110)    # the fist on the ground
LEAP_RSTEP = (120, 130)       # the right foot (the knee down behind) steps up under him
LEAP_LSTEP = (134, 144)       # then the left foot back from ahead
SMASH_ARM_K = 1.48            # the right arm drawn this much longer for the blow (attack3d.arm_lengths)
SMASH_FIST_Z = 7.4            # the fist's centre over the ground as it lands: the drawn fist (pointing down) reaches 6.4 px below it
KNEEL_R = (-35.95, 0.0, 23.0, -70.0)       # anim_kneel.kneel_legs(41): the right knee down, toes tucked behind
KNEEL_L = (26.09, 0.0, gait.ANKLE_H, 0.0)  # ... the left foot flat ahead
KNEEL_D = 41


def leap_lift(t):
    """px off the ground at combat frame t: a throw up and down, from the frame before the take-off to the landing."""
    if not (LEAP_UP - 1 < t < LEAP_W):
        return 0.0
    u = (t - (LEAP_UP - 1)) / (LEAP_W - (LEAP_UP - 1))
    return 4.0 * LEAP_PEAK * u * (1.0 - u)


def _slung(k):
    """A key's right fist and blade where the slung sword is (attack3d.back_sword) for that key's body."""
    st = dict(k, whole_turn=False)
    st['back'] = True
    g, ax, w = A.back_sword(st)
    return g, A.angles(ax), w


def _left_at(k, rel):
    """Key k with the free left fist at `rel` from its shoulder (F, R, U px; lhand from where it hangs)."""
    hang = A.free_left(dict(k, lhand=(0.0, 0.0, 0.0)))
    return dict(k, lhand=A.yaw(A.sub(A.add(A.shoulder('L', k), rel), hang), -k.get('tw', 0.0)))


LEFT_FLUNG = (-30.0, -8.0, 12.0)   # the landing: the free left arm flung back and up behind him, near straight


def _arms_at(k, fist):
    """Key k with the right fist at `fist` and the free left fist mirrored across him (lhand from where it hangs)."""
    k = dict(k, fist=fist)
    hang = A.free_left(dict(k, lhand=(0.0, 0.0, 0.0)))
    k['lhand'] = A.sub((fist[0], -fist[1], fist[2]), hang)
    return k


LEAP_COCKED = (8.0, 5.0, 16.0)  # the cocked right fist from its shoulder (F, R, U px): before it, at the chin
LEAP_POLE_COCKED = (-1.0, 0.4, 0.3)  # ... the elbow drawn back and up


def _fist_cocked(k):
    """Key k with the right arm cocked for the blow (LEAP_COCKED; its elbow by POLES_LEAP)."""
    return dict(k, fist=A.add(A.shoulder('R', k), LEAP_COCKED))


def leap_rel_keys():
    """The leap's keys as if on the ground: the feet and the free fist relative to the body (leap() adds the lift)."""
    k = [(0, carry_key())]
    # the sword lifted off the shoulder, the hilt carried back over it, the blade swinging down behind him
    # (quick: the crouch is the long part - user 2026-10-05 "起跳的蓄力久一點")
    k.append((4, carry_key(D=1, tw=-4, fist=(13.0, 25.0, 142.0), dir=(170.0, 16.0), roll=20.0, lfree=0.2, lhand=(2.0, 0.0, 3.0))))
    k.append((8, carry_key(D=1, tw=-6, fist=(2.0, 22.0, 149.0), dir=(-165.0, -18.0), roll=60.0, lfree=0.3, lhand=(2.0, 0.0, 4.0))))
    k.append((12, carry_key(D=1, tw=-4, fist=(-12.0, 16.0, 145.0), dir=(-120.0, -48.0), roll=80.0, lfree=0.3, lhand=(2.0, 0.0, 4.0))))
    at = carry_key(D=1, tw=0, lfree=0.3, lhand=(2.0, 0.0, 4.0))
    g, d, w = _slung(at)
    at.update(fist=g, dir=d, flat=w)
    k.append((LEAP_BACK[0] - 2, at))
    k.append((LEAP_BACK[0], at))
    # the hand lets go and comes down; he sinks, both arms swung back (the wind-up), and stays down gathering
    # himself - LEAP_CROUCH: still sinking a little, the arms drawing further back - then drives up off the legs
    # (off the hilt the hand comes down outside the shoulder, the elbow dropping behind - straight down from the hilt it
    # passed by the shoulder joint, the arm folded tight and the elbow flicked out before it)
    off = carry_key(D=2, bend=2.0, lx=0.5, lfree=0.38, lhand=(2.5, 0.0, 4.5), bow=0.5)
    k.append((LEAP_BACK[0] + 1, dict(off, fist=A.add(A.shoulder('R', off), (-12.0, 16.0, 8.0)))))
    drop = carry_key(D=3, bend=4.0, lx=1, lfree=0.45, lhand=(3.0, 0.0, 5.0), bow=1)
    k.append((LEAP_BACK[0] + 2, dict(drop, fist=A.add(A.shoulder('R', drop), (-8.0, 24.0, -14.0)))))
    k.append((LEAP_BACK[0] + 4, carry_key(D=8, bend=10.0, lx=2, fist=(10.0, 26.0, 84.0), lfree=0.6, lhand=(4.0, 0.0, 6.0), bow=2)))
    # (user 2026-10-05 "起跳的過程，手要往身後蓄力": both arms swung right back behind him, up over the shoulders' height,
    # clear of the slung blade; then down past the hips and forward and up as he drives off)
    k.append((LEAP_CROUCH[0], _arms_at(carry_key(D=30, bend=33.0, bow=-16, lfree=1.0, ck=-2), (-16.0, 28.0, 64.0))))
    k.append((LEAP_CROUCH[0] + 6, _arms_at(carry_key(D=33, bend=40.0, bow=-18, lfree=1.0, ck=-2), (-22.0, 28.0, 80.0))))
    k.append((LEAP_CROUCH[1], _arms_at(carry_key(D=33, bend=42.0, bow=-20, lfree=1.0, ck=-2), (-24.0, 27.0, 84.0))))
    k.append((38, _arms_at(carry_key(D=28, bend=34.0, bow=-16, lfree=1.0, ck=-2), (-10.0, 29.0, 62.0))))
    k.append((39, _arms_at(carry_key(D=20, bend=20.0, bow=-11, lfree=1.0, ck=-3,
                                    feet={'R': (0.0, 0.0, gait.ANKLE_H, -15.0), 'L': (0.0, 0.0, gait.ANKLE_H, -15.0)}), (4.0, 28.0, 58.0))))
    k.append((40, _arms_at(carry_key(D=13, bend=11.0, bow=-10, lfree=1.0, ck=-3,
                                    feet={'R': (0.0, 0.0, gait.ANKLE_H, -20.0), 'L': (0.0, 0.0, gait.ANKLE_H, -20.0)}), (14.0, 27.0, 84.0))))
    k.append((41, carry_key(D=7, bend=4.0, bow=-9, fist=(22.0, 25.0, 122.0), lfree=1.0, lhand=(16.0, 2.0, 40.0), ck=-4,
                            feet={'R': (0.0, 0.0, gait.ANKLE_H, -25.0), 'L': (0.0, 0.0, gait.ANKLE_H, -25.0)})))
    # off the ground: stretched out, the arms flung up; then the legs tucked as he rises
    k.append((LEAP_UP, carry_key(D=6, lx=-2, bow=-8, fist=(24.0, 24.0, 131.0), lfree=1.0, lhand=(20.0, 2.0, 46.0), ck=-5,
                                 feet={'R': (2.0, 0.0, 12.0, -45.0), 'L': (-2.0, 0.0, 12.0, -45.0)})))
    k.append((50, carry_key(D=14, lx=0, bow=-6, fist=(24.0, 30.0, 120.0), lfree=1.0, lhand=(16.0, -2.0, 36.0), ck=-6,
                            feet={'R': (4.0, 0.0, 18.0, -30.0), 'L': (-4.0, 0.0, 16.0, -35.0)})))
    k.append((62, carry_key(D=20, lx=2, bow=-4, fist=(14.0, 30.0, 100.0), lfree=1.0, lhand=(10.0, -6.0, 22.0), ck=-3,
                            feet={'R': (6.0, 0.0, 22.0, -20.0), 'L': (-6.0, 0.0, 20.0, -25.0)})))
    # the landing place is locked: he tips forward, the right arm cocked - the elbow drawn back and up, the fist
    # still before the shoulder at his chin (user 2026-10-05: "手肘往後，不是拳頭…拳頭一樣在前面": drawn up and back
    # whole, the forearm turned over backwards) - the left hand forward
    k.append((LEAP_LOCK, _fist_cocked(carry_key(D=22, bend=16.0, bow=-12, lfree=1.0, lhand=(22.0, 4.0, 26.0),
                                           ck=0, feet={'R': (0.0, 0.0, 20.0, -25.0), 'L': (6.0, 0.0, 20.0, -15.0)}))))
    k.append((80, _fist_cocked(carry_key(D=28, bend=42.0, bow=-26, lfree=1.0, lhand=(24.0, 2.0, 22.0), ck=2,
                                    feet={'R': (-10.0, 0.0, 15.0, -45.0), 'L': (10.0, 0.0, 15.0, -5.0)}))))
    k.append((84, _left_at(carry_key(D=36, bend=60.0, bow=-37, fist=(28.0, 27.0, 72.0), lfree=1.0, ck=3, arm_k=1.25,
                                     feet={'R': (-30.0, 0.0, 24.0, -65.0), 'L': (24.0, 0.0, 18.0, 0.0)}), (-16.0, -8.0, -18.0))))
    k.append((88, _left_at(carry_key(D=40, bend=68.0, bow=-42, tw=6.0, fist=(32.0, 25.0, 30.0), lfree=1.0, ck=4, arm_k=SMASH_ARM_K,
                                     feet={'R': (-34.0, 0.0, 23.0, -68.0), 'L': (26.0, 0.0, 16.6, 0.0)}), (-26.0, -8.0, 4.0))))
    # landed (the hit): the right knee down, the left foot ahead, bent right over, the right fist on the ground
    land = _left_at(carry_key(D=KNEEL_D, bend=70.0, bow=-44, tw=8.0, fist=(32.0, 24.0, SMASH_FIST_Z), lfree=1.0,
                              ck=4, arm_k=SMASH_ARM_K, feet={'R': KNEEL_R, 'L': KNEEL_L}), LEFT_FLUNG)
    k.append((LEAP_W, land))
    k.append((LEAP_SMASH[1], _left_at(dict(land, ck=1), (-26.0, -8.0, 4.0))))
    # rising, the right hand back over the shoulder to the hilt
    rise = carry_key(D=37, bend=50.0, bow=-26, tw=-2.0, lfree=0.8, lhand=(-8.0, -8.0, 16.0), arm_k=1.2, feet={'R': KNEEL_R, 'L': KNEEL_L})
    rise['fist'] = (22.0, 26.0, 50.0)
    k.append((114, rise))
    grab = carry_key(D=30, bend=20.0, bow=-8, tw=-8.0, lfree=0.6, lhand=(-2.0, -4.0, 8.0), feet={'R': KNEEL_R, 'L': KNEEL_L})
    g, d, w = _slung(grab)
    grab.update(fist=g, dir=d, flat=w)
    k.append((LEAP_BACK[1], grab))
    # drawn up out along its line (rising), the blade swung out behind him to his right and up, over his head to
    # upright before the right shoulder, laid back on it; the right foot, then the left, step back under him
    pull = dict(grab)
    pull['fist'] = A.add(g, (-4.0, 3.0, 14.0))          # up and back along the blade, clear of the shoulder plate
    pull.update(D=22, bend=8.0, bow=-3, tw=-6.0, feet={'R': None, 'L': KNEEL_L})
    k.append((123, pull))
    k.append((128, carry_key(D=14, tw=-4, fist=(-16.0, 22.0, 132.0), dir=(176.0, -24.0), roll=70.0, lfree=0.3,
                             lhand=(0.0, -2.0, 4.0), feet={'R': STAND, 'L': KNEEL_L})))
    k.append((132, carry_key(D=10, tw=-2, fist=(-8.0, 22.0, 134.0), dir=(170.0, 48.0), roll=80.0, lfree=0.1, feet={'R': STAND, 'L': KNEEL_L})))
    k.append((135, carry_key(D=8, tw=-1, fist=(6.0, 19.0, 131.0), dir=(176.0, 76.0), roll=85.0, feet={'R': STAND, 'L': KNEEL_L})))
    k.append((139, carry_key(D=6, fist=(20.0, 14.0, 124.0), dir=(-18.0, 80.0), flat=FLAT_R, feet={'R': STAND, 'L': None})))
    k.append((145, carry_key(D=2, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), roll=30.0, feet={'R': STAND, 'L': STAND})))
    k.append((LEAP_END - 6, carry_key()))
    return k


def leap_rel_steps():
    return {'R': [(LEAP_RSTEP[0], KNEEL_R), (LEAP_RSTEP[1], STAND)], 'L': [(LEAP_LSTEP[0], KNEEL_L), (LEAP_LSTEP[1], STAND)]}


def _snapshot(s, lift):
    """Keys from a state: everything the keys carry, the fist and the feet put up `lift` px."""
    # (rounded: a key read back off the curve at its own frame comes out a hair off, and two keys meant to be equal
    # - a value held - would then be curved between)
    k = carry_key(**{n: (s[n] if n == 'D' else round(s[n], 6)) for n in SCALARS if n in s})
    k['fist'] = (round(s['fist'][0], 6), round(s['fist'][1], 6), round(s['fist'][2], 6) + lift)
    r6 = lambda v: tuple(round(x, 6) for x in v)
    k['dir'] = r6(A.angles(s['axis']))
    k['flat'] = r6(s['flat'])
    k['lhand'] = r6(s['lhand'])
    k['poleR'], k['poleL'] = r6(s['poleR']), r6(s['poleL'])
    k['feet'] = {n: (round(f[0], 6), round(f[1], 6), round(f[2], 6) + lift, round(f[3], 6)) for n, f in s['feet'].items()}
    k['lift'] = lift
    return k


POLE_DOWN_BACK = (-1.0, 0.4, -0.3)      # the hanging arm's elbow: behind it
POLE_SWUNG_BACK = (-0.6, 0.4, 0.8)      # the arm swung back behind him: the elbow behind and up
POLE_L_FLUNG = (-0.6, -0.4, 0.8)        # the landing: the free left arm flung back for balance, its elbow behind and up


def _mirror(p):
    return (p[0], -p[1], p[2])


POLES_LEAP = {
    4: ((0.1, 1.0, -0.4), None), 8: ((-0.4, 1.0, 0.4), None), 12: ((-0.2, 1.0, 0.6), None), LEAP_BACK[0]: ((0.0, 1.0, 0.5), None),
    # (the hand off the hilt down by his side and the arms swung back behind him: the elbows behind - pointing down they
    # came out before the shoulder with the fist behind it, the forearm bent back the wrong way; user 2026-10-05
    # "收劍後的幾貞手又後翻了")
    LEAP_BACK[0] - 2: ((0.0, 1.0, 0.5), None), LEAP_BACK[0] + 1: ((-0.4, 0.2, 1.0), None), LEAP_BACK[0] + 2: ((-0.6, 0.6, -0.5), None), LEAP_BACK[0] + 4: (POLE_DOWN_BACK, None),
    LEAP_CROUCH[0]: (POLE_SWUNG_BACK, _mirror(POLE_SWUNG_BACK)), LEAP_CROUCH[0] + 6: (POLE_SWUNG_BACK, _mirror(POLE_SWUNG_BACK)),
    LEAP_CROUCH[1]: (POLE_SWUNG_BACK, _mirror(POLE_SWUNG_BACK)), 38: ((-0.6, 0.4, 0.6), (-0.6, -0.4, 0.6)),
    39: ((-1.0, 0.4, 0.0), (-1.0, -0.4, 0.0)), 40: ((0.3, 0.8, -0.6), None),
    LEAP_UP: ((0.3, 0.8, -0.6), None), LEAP_LOCK: (LEAP_POLE_COCKED, None), 80: (LEAP_POLE_COCKED, None),
    84: ((0.2, 1.0, 0.0), POLE_L_FLUNG), 88: ((-0.2, 1.0, 0.2), POLE_L_FLUNG), LEAP_W: ((-0.6, 0.8, 0.2), POLE_L_FLUNG),
    LEAP_SMASH[1]: ((-0.6, 0.8, 0.2), POLE_L_FLUNG),
    114: ((-0.3, 1.0, -0.4), None), LEAP_BACK[1]: ((0.0, 1.0, 0.6), None), 123: ((0.0, 1.0, 0.6), None),
    128: ((-0.2, 1.0, 0.2), None), 132: ((-0.2, 1.0, 0.4), None), 135: ((0.0, 1.0, 0.2), None), 139: ((-0.1, 1.0, -0.6), None),
}


def leap():
    """墜王之躍 (phase 2): crouch 0 .. 41, in the air 42 .. 89 (the game moves him), landed - the hit box - 90 .. 95, the fist on
    the ground to 110, recovery to 156. The sword slung on his back 16 .. 117."""
    rel_keys = leap_rel_keys()
    rel = Clip('leap_rel', [(t, dict(kk, poleL=kk.get('poleL') or A.yaw(POLE_L_BODY, kk.get('tw', 0.0))))
                            for t, kk in with_poles(rel_keys, POLES_LEAP)], leap_rel_steps())
    times = sorted(set(t for t, _ in rel_keys) | set(range(LEAP_UP - 1, LEAP_W + 1)))
    keys = [(t, _snapshot(rel.at(t), leap_lift(t))) for t in times]
    # the fist stays on the ground through the impact: the same key at both ends (exactly)
    smash = dict(keys)[LEAP_SMASH[0]]
    keys = [(t, dict(kk, fist=smash['fist'], feet=smash['feet'], dir=smash['dir'])) if t == LEAP_SMASH[1] else (t, kk)
            for t, kk in keys]
    return Clip('leap', keys, back=LEAP_BACK, musts=tuple(range(LEAP_UP - 4, LEAP_W + 3)), lead=False, still=True,
                exact_cape=True, upwrap=True, behind=(LEAP_BACK[0], LEAP_UP), left_own=True)


LEAP_CONTACT = LEAP_W + 2     # the landing's frame the bounce starts from (the fist on the ground)


def leap_bounce():
    """The landing parried (BOUNCED 1.2 s): the fist knocked up off the ground, he is thrown back up out of the kneel,
    the right foot steps up under him, then the left; he reaches back over the right shoulder, draws the sword off his
    back (up out along its line), swings it up over his head and forward and lays it on the shoulder: the carry."""
    base = leap()
    c = base.at(LEAP_CONTACT)
    k0 = _snapshot(c, 0.0)
    keys = [(0, k0)]
    keys.append((4, carry_key(D=36, bend=40.0, bow=-30, tw=4.0, fist=(30.0, 26.0, 40.0), lfree=1.0, lhand=(-18.0, -12.0, 30.0),
                              ck=5, arm_k=1.2, feet={'R': KNEEL_R, 'L': KNEEL_L})))
    keys.append((10, carry_key(D=30, bend=14.0, lx=-8, bow=-14, tw=-4.0, fist=(14.0, 28.0, 84.0), lfree=0.8,
                               lhand=(-6.0, -8.0, 14.0), ck=4, feet={'R': KNEEL_R, 'L': KNEEL_L})))
    grab = carry_key(D=22, bend=10.0, lx=-4, bow=-6, tw=-6.0, lfree=0.5, lhand=(-2.0, -4.0, 8.0), feet={'R': STAND, 'L': KNEEL_L})
    g, d, w = _slung(grab)
    grab.update(fist=g, dir=d, flat=w)
    keys.append((BOUNCE_GRAB, grab))
    pull = dict(grab)
    pull['fist'] = A.add(g, (-4.0, 3.0, 14.0))
    pull.update(D=14, bend=4.0, lx=-2, feet={'R': STAND, 'L': None})
    keys.append((BOUNCE_GRAB + 6, pull))
    keys.append((BOUNCE_GRAB + 12, carry_key(D=8, tw=-4, fist=(-16.0, 22.0, 136.0), dir=(176.0, -24.0), roll=70.0, lfree=0.2,
                                             feet={'R': STAND, 'L': STAND})))
    keys.append((BOUNCE_GRAB + 17, carry_key(D=6, tw=-2, fist=(-8.0, 22.0, 136.0), dir=(170.0, 48.0), roll=80.0)))
    keys.append((BOUNCE_GRAB + 21, carry_key(D=5, tw=-1, fist=(6.0, 19.0, 133.0), dir=(176.0, 76.0), roll=85.0)))
    keys.append((BOUNCE_GRAB + 24, carry_key(D=4, fist=(20.0, 14.0, 124.0), dir=(-18.0, 80.0), flat=FLAT_R)))
    keys.append((BOUNCE_GRAB + 30, carry_key(D=2, fist=(17.0, 20.0, 131.0), dir=(162.0, 40.0), roll=30.0)))
    keys.append((66, carry_key()))
    poles = {4: ((0.2, 1.0, -0.6), POLE_L_FLUNG), 10: ((-0.3, 1.0, -0.4), None), BOUNCE_GRAB: ((0.0, 1.0, 0.6), None),
             BOUNCE_GRAB + 6: ((0.0, 1.0, 0.6), None), BOUNCE_GRAB + 12: ((-0.2, 1.0, 0.2), None),
             BOUNCE_GRAB + 17: ((-0.2, 1.0, 0.4), None), BOUNCE_GRAB + 21: ((0.0, 1.0, 0.2), None),
             BOUNCE_GRAB + 24: ((-0.1, 1.0, -0.6), None)}
    # (the first key's left elbow is the leap's at the contact: the bounce's first pose is the leap's)
    keys = [(t, dict(kk, poleL=kk.get('poleL') or A.yaw(POLE_L_BODY, kk.get('tw', 0.0)))) for t, kk in with_poles(keys, poles)]
    steps = {'R': [(10, KNEEL_R), (BOUNCE_GRAB - 2, STAND)], 'L': [(BOUNCE_GRAB + 2, KNEEL_L), (BOUNCE_GRAB + 12, STAND)]}
    return Clip('leap_bounce', keys, steps, back=(0, BOUNCE_GRAB), lead=False, exact_cape=True, upwrap=True, left_own=True)


BOUNCE_GRAB = 24              # the bounce: the right hand takes the hilt off his back
