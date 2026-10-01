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
             roll=0.0, two=0.0, feet={'R': STAND_FOOT, 'L': STAND_FOOT})
    k.update(kw)
    return k


def boot_drop(pitch):
    import anim_kneel
    return anim_kneel.boot_drop(pitch)


SCALARS = ('D', 'hx', 'ht', 'lx', 'tw', 'bow', 'ck', 'cs', 'roll', 'two')
CLAMP01 = ('two',)


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


HIP_HALF = 17.0          # each hip joint this far from the centre line (anim_walk.HIP_HALF)


def hip_x(st, side_):
    """How far forward of the anchor a leg's hip joint is: the hips' hx, and the hips' turn ht
    bringing the right hip forward (+) and the left back (the turn as the yaw of attack3d)."""
    sgn = 1.0 if side_ == 'R' else -1.0
    return st['hx'] + sgn * HIP_HALF * math.sin(math.radians(st.get('ht', 0.0)))


class Clip:
    """keys: [(frame, settings)], frame 0 first. at(t) -> the pose at combat frame t. Each
    foot's track is the keys that give it (a key's feet may leave one out, or give None)."""

    def __init__(self, name, keys, steps=None, advance=None, musts=()):
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
            if K4[1][k] == K4[2][k]:
                v = K4[1][k]          # a value held between two keys stays put (no overshoot past it)
            else:
                v = _catmull(*[(kk[k],) for kk in K4], u)[0]
            if k in CLAMP01:
                v = min(1.0, max(0.0, v))
            out[k] = v
        out['D'] = round(out['D'])          # whole pixels (animation-review §4.4: half-pixel heights re-sample the trim)
        out['fist'] = _catmull(*[kk['fist'] for kk in K4], u)
        dirs = [A.direction(*kk['dir']) for kk in K4]
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
        if speed > 1e-4:
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


# ------------------------------------------------------------------ choosing the poses
TIP_STEP = 80.0        # px the sword's tip may move on screen between two poses (the Boss's limit, checks_hit)
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
    for view, far in VIEWS3:
        for p, q, kind in ((A.tip(a), A.tip(b), 'tip'), (a['fist'], b['fist'], 'hand')):
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


def entry(clip, kind, entry_pose):
    """States for ENTRY_TIMES starting from loop pose `entry_pose` of `kind` (anim_walk.KINDS);
    the first is the loop pose itself (draw it with anim_walk). One foot at a time (user
    2026-10-01): the first (entry_order) steps under him by ENTRY_HALF while the other stays
    planted (its foot rolling flat), then the other steps under him by ENTRY_END."""
    import anim_walk as AW
    s0 = AW.loop_state(entry_pose, kind)
    f0 = loop_feet(s0)
    first = entry_order(s0, kind)
    span = {first: (0, ENTRY_HALF), ('L' if first == 'R' else 'R'): (ENTRY_HALF, ENTRY_END)}
    lean0 = AW.LEAN_DEG * AW.LEAN_OF[kind]
    states = poses(clip, list(ENTRY_TIMES))
    for st in states:
        t = st['t']
        w = gait.smooth(t / ENTRY_END)
        st['lx'] = lean0 + (st['lx'] - lean0) * w
        st['D'] = round(s0['D'] + (st['D'] - s0['D']) * w)
        feet = {}
        for k in 'RL':
            a, b = f0[k], st['feet'][k]
            t0, t1 = span[k]
            u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            ww = gait.smooth(u)
            pitch0 = a[3]
            z0 = a[2]
            if k != first and a[4]:
                # planted, waiting for its step: the foot rolls flat on the ground
                v = gait.smooth(min(1.0, t / ENTRY_HALF))
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


def bounce_keys(contact):
    """The bounce from the attack's contact: the knock rocks him back off the front foot onto
    the other (which has stayed where it was since the windup), then the front foot steps back -
    one foot (the steps returned). The hips come back from over the front foot (two thirds of a
    36 px lunge) at no more than the stepping foot's pace, so the front foot lifts only once
    they are over the back one."""
    c = dict(contact)
    front = max('RL', key=lambda k: c['feet'][k][0])
    stance = dict(c['feet'])
    lift = {front: None, ('L' if front == 'R' else 'R'): STAND}
    ht, hx = c['ht'], c['hx']
    k = [(0, c)]
    k.append((4, carry_key(D=c['D'] - 1, hx=hx - 7.0, ht=0.6 * ht, tw=0, lx=6, fist=(hx + 18.0, 1.0, 108.0), dir=(0.0, 32.0),
                           two=0.5, bow=-6, ck=3, feet=stance)))
    k.append((10, carry_key(D=8, hx=6.0, ht=0.3 * ht, tw=0, lx=-7, fist=(27.0, 6.0, 124.0), dir=(-12.0, 72.0), two=0.0,
                            roll=90.0, bow=-13, ck=5, feet=stance)))
    k.append((20, carry_key(D=5, hx=-1.0, tw=0, lx=-10, fist=(18.0, 14.0, 132.0), dir=(162.0, 58.0), two=0.0, roll=40.0,
                            bow=-12, ck=4, feet=lift)))
    k.append((34, carry_key(D=2, lx=-6, fist=(16.0, 21.0, 134.0), dir=(162.0, 18.0), bow=-6, ck=2)))
    k.append((52, carry_key(lx=-2, bow=-1)))
    k.append((66, carry_key()))
    return k, {front: [(BOUNCE_BACK[0], stance[front]), (BOUNCE_BACK[1], STAND)]}


def contact_key(clip, t):
    """The keys' settings at frame t of a clip (to start another clip from that pose)."""
    s = clip.at(t)
    k = carry_key(D=s['D'], hx=s['hx'], ht=s['ht'], lx=s['lx'], tw=s['tw'], bow=s['bow'], ck=s['ck'], cs=s['cs'],
                  fist=s['fist'], dir=A.angles(s['axis']), roll=s['roll'], two=s['two'],
                  feet={side_: tuple(s['feet'][side_][:4]) for side_ in 'RL'})
    k['poleR'], k['poleL'] = s['poleR'], s['poleL']
    return k


POLES_BOUNCE = {4: (DOWN_R, None), 10: ((0.0, 1.0, -0.4), None), 20: ((-0.2, 1.0, 0.0), None)}


def c1_bounce():
    keys, steps = bounce_keys(contact_key(c1(), W + 4))
    return Clip('c1_bounce', with_poles(keys, POLES_BOUNCE), steps)


def twin_bounce():
    keys, steps = bounce_keys(contact_key(twin(), W2 + 3))
    return Clip('twin_bounce', with_poles(keys, POLES_BOUNCE), steps)
