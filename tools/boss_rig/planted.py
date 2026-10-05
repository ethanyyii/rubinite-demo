"""Starting an attack with the sword planted (2026-10-05): the Boss standing with the sword's tip in the ground (the
idle; after the walk's stop, a rise, a stagger from standing) starts an attack.

User 2026-10-05: "好，補" - the start from a planted sword (art-progress "Boss 接進遊戲：交件", decision 3: the attack's
first pose is the carry, so the sword jumped from the ground onto the shoulder).

Every attack starts from the carry and its windup's time is the game's (veltharis_data): there is no time to put the
sword on the shoulder first. So, like the starts from a move (attacks.entry), the first JOIN[sheet] frames are drawn
again: from the standing pose (the fist at interrupt.STAND_FIST, the blade hanging tip down into the ground:
carry.pose3(0) - sword.standing has it within 3 degrees of upright in every view) straight to where the attack has
the sword at frame JOIN - the tip coming up out of the ground forward first (carry.pose3's way: "from the front of
the body, round"), through as few of its waypoints as the 3D allows (interrupt.problems: the fists within reach, the
blade not through him, the tip not into the ground). The feet do not move: every JOIN is before the attack's first
step. Paced: a pose every 2 frames, eased at both ends (anim_walk.ease), each pose within what a pose may move
(interrupt.STEP_*); the game then plays the attack from frame JOIN.

The first pose is the standing sprite itself (export_planted): the concept's four views are elevations, not projections
of one model, and the projected standing pose differs from them (8 - 13 % of the outline; facing down the planted tip
shows 11 px lower: it is 21 px in front of him). anim_walk fades that difference out as the sword comes up; the attack
rig cannot, so the drawn way begins already moving (the tip out of the ground, the knees giving).
"""
import math
import attacks as AT
import attack3d as A
import anim_walk as AW
import interrupt as I

# the sheet whose opening the game plays (export_game.MOVES' entries) -> the attack's frames the start may join, in
# the order tried (the latest first: the most time; only frames before the attack's first step)
JOIN = {'boss_c1': (24,), 'boss_quick': (14,), 'boss_cleave': (24,), 'boss_impact': (24,), 'boss_thrust': (12, 10),
        'boss_spin': (24, 20, 16, 12), 'boss_leap': (16, 20, 12)}
SEG = 10                  # frames between the keys while the way is laid out (re-paced to JOIN)
LIFT_OUT = 0.1            # carry.pose3 blend: the tip just out of the ground, swinging forward
# the sword's way up (carry.pose3 blends), tried in turn; 0.9 / 1.0: nearly / onto the shoulder first (the king's
# leap then takes it over onto his back the way the attack does from the carry)
WAYS = ([], [0.2], [0.34], [0.2, 0.34], [0.34, 0.68], [0.2, 0.68], [0.68], [0.34, 0.68, 0.9], [0.34, 0.68, 1.0])


def stand_key():
    """The standing pose: the fist where it rests on the planted sword, the blade hanging tip down into the ground."""
    d, w = I.carry_sword(0.0)
    return AT.carry_key(dir=d, flat=w, fist=I.STAND_FIST)


def way_key(b, D):
    """carry.pose3's way up at blend b (0.2 the tip forward and down, 0.34 level forward, 0.68 upright before the
    shoulder), the knees bent D px (the attack's at JOIN: the hips may then shift without stretching a leg); the fist
    where carry.place has it standing (a few px of knee do not lower it: the tip stays out of the ground)."""
    d, w = I.carry_sword(b)
    return AT.carry_key(D=D, dir=d, flat=w, fist=I.carry_fist(b))


class Paced:
    """The bridge's clip 0 .. t1 run in exactly T frames, eased at both ends, every part's on-screen motion measured as
    interrupt.Even measures it."""

    def __init__(self, clip, t1, T):
        self.clip, self.t1, self.T = clip, t1, T
        self.name, self.lead, self.spin = clip.name, clip.lead, clip.spin
        self.keys = clip.keys
        self.ts, self.cs = [0.0], [0.0]
        prev = clip.at(0.0)
        t = 0.0
        while t < t1 - 1e-9:
            t = min(t1, t + 0.25)
            cur = clip.at(t)
            d, tp = I.pose_dist(prev, cur)
            self.ts.append(t)
            self.cs.append(self.cs[-1] + max(d / I.STEP_BODY, tp / I.STEP_TIP))
            prev = cur

    def src_time(self, t):
        want = AW.ease(min(1.0, max(0.0, t / self.T))) * self.cs[-1]
        for i in range(1, len(self.cs)):
            if self.cs[i] >= want:
                a, b = self.cs[i - 1], self.cs[i]
                f = 0.0 if b <= a else (want - a) / (b - a)
                return self.ts[i - 1] + (self.ts[i] - self.ts[i - 1]) * f
        return self.t1

    def at(self, t):
        return self.clip.at(self.src_time(t))

    def times(self):
        """A pose every 2 frames; every frame where two poses 2 frames apart would move further than a pose may (the
        tip pulled out of the ground into a fast windup: interrupt.stagger_bridge does the same)."""
        out = []
        for a in range(0, self.T, 2):
            out.append(a)
            d, tp = I.pose_dist(self.at(a), self.at(min(a + 2, self.T)))
            if a + 1 < self.T and (d > I.STEP_BODY or tp > I.STEP_TIP):
                out.append(a + 1)
        return out


class Start:
    def __init__(self, sheet, paced, times, way):
        self.sheet, self.clip, self.times, self.way = sheet, paced, times, way
        self.holds = [b - a for a, b in zip(times, times[1:] + [paced.T])]
        self.end = paced.T


def standing_feet(s):
    return all(abs(a - b) < 0.5 for k in 'RL' for a, b in zip(s['feet'][k][:4], AT.STAND_FOOT))


def build(m):
    """The start from the planted sword for attack Move m (its sheet in JOIN): the first frame and way that pass the
    3D and the step limits."""
    tries = []
    for J in JOIN[m.sheet]:
        sJ = m.states[m.times.index(J)]
        if not standing_feet(sJ):
            tries.append((J, 'feet'))
            continue
        st = _build(m, J, sJ, tries)
        if st:
            return st
    raise ValueError(f'no way up for {m.sheet}: {tries}')


def _build(m, J, sJ, tries):
    kJ = I.key_of(sJ)
    flags = I._flags(m.clip)
    for wps in WAYS:
        # the knees give as the tip comes out of the ground (straight legs cannot let the hips shift later)
        D = max(1, int(kJ['D']))
        keys = [(0, stand_key()), (SEG // 2, way_key(LIFT_OUT, D))]
        t = SEG // 2
        for b in wps:
            t += SEG
            keys.append((t, way_key(b, D)))
        t += SEG
        keys.append((t, kJ))
        clip = AT.Clip('planted', keys, ground=True, lead=False, exact_cape=True, **flags)
        bad = I.problems(clip, t, t)
        if bad:
            tries.append((J, wps, bad[:2]))
            continue
        p = Paced(clip, t, J)
        bad = I.problems(p, J, J)                     # every frame as it is drawn (sampled where the paced way falls)
        if bad:
            tries.append((J, wps, 'paced', bad[:2]))
            continue
        times = p.times()
        steps = I.step_problems(p, times + [J])
        if steps:
            tries.append((J, wps, steps[:2]))
            continue
        return Start(m.sheet, p, times, wps)
    return None


def report(st):
    """(largest step of the body, of the tip) between its poses, and into the attack at JOIN."""
    ts = st.times + [st.end]
    worst = (0.0, 0.0)
    for a, b in zip(ts, ts[1:]):
        d, t = I.pose_dist(st.clip.at(a), st.clip.at(b))
        worst = (max(worst[0], d), max(worst[1], t))
    return worst
