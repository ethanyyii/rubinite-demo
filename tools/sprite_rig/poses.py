"""Key poses of batch 0 (docs/art-progress.md): one entry per pose, rendered in all four
views by pose_rig.py. Lying and launched are not posed by the rig: they are restored from
the concept's H (concept_pose.py), head left and its mirror.

Hands are given in chest space: origin = centre of the chest at shoulder height,
(f, l, u) = forward, the character's left, up, in pixels. `hand()` turns that into the
shoulder-relative target the rig wants. Feet: side views use (f offset from the idle
stance, l, lift, boot state); front / back use (f, l, lift[, 'kneel']).

The pose targets (concept thumbnails) are named as in the brief: A idle, B dash, C normal
attack, D skill attack, E jump, F hit, G crouch, H down, I idle with the sword drawn."""
import pose_rig as P


def hand(s, f, l, u, **kw):
    """A hand at (f, l, u) in chest space; the rig measures it from that view's shoulder."""
    spec = dict(at=(float(f), float(l), float(u)))
    spec.update(kw)
    return spec


def two_hand_grip(f, l, u, blade, back=3.0, elbow_up=-1.0):
    """Right hand at (f, l, u); the left hand holds the grip `back` px toward the pommel
    (placed by the rig from the blade angle each view uses). elbow_up: the elbows' hint
    below (-1) or level with (0) the hands; level elbows flare out past the pauldrons."""
    lf, ll, lu = P.vsub((f, l, u), P.vscale(P.vnorm(blade), back))
    return (hand('R', f, l, u, elbow=(0, -1, elbow_up)),
            hand('L', lf, ll, lu, elbow=(0, 1, elbow_up), on_grip=back, depth_fore=18, depth_fist=18.6))


# ------------------------------------------------------------------ guard, parry (batch 1)
GUARD_BLADE = (0.45, 0.75, 0.5)     # forward, to the off-hand side, tip raised (Sekiro guard)
# elbows flare out level with the grip: the blocking stance must read against the idle at a
# glance (review 1, checks.py DISTINCT), and in the back view they are what shows
_gr, _gl = two_hand_grip(6, -4, 3, GUARD_BLADE, elbow_up=0.2)
# a braced stance: the idle's own width (front 16 px, back 13 px between the boot centres)
GUARD = dict(root=(0, 0, -1), lean=4,
             feet={'R': (-1, -4.25, 0, 'flat'), 'L': (2, 4.25, 0, 'flat')},
             arms={'R': _gr, 'L': _gl},
             # front view: a flat bar across the chest (the brief's "horizontal, rise <= 2 px"),
             # lit on both rows so it reads against the dark armour
             sword=dict(hand='R', dir=GUARD_BLADE, grip_back=4.5,
                        dir_view={'west': (0.75, 0.4, 0.5), 'south': (0.2, 1.0, 0.07), 'east': (0.85, 0.3, 0.45)},
                        depth={'north': -31, 'east': 55, 'west': 55, 'south': 55}),
             cape=(-1, 0, 0), plume=(-1, 0, 0))

# the deflect: the blade is flung out and up to the sword side (from pointing across the
# chest to pointing over the right shoulder), the left hand lets go and swings out to the
# other side, the chest opens and the weight settles on the front foot. A different outline
# from the guard at a glance, without the spark (animation-review §4.5)
PARRY = dict(root=(0, 0, -1), lean=-10, roll=5, head_tilt=-6, head=(-1, 0, 0),
             feet={'R': (-3, -4.25, 0, 'toe'), 'L': (4, 4.25, 0, 'flat')},
             arms={'R': hand('R', -1, -17, 7, elbow=(0, -1, 0)), 'L': hand('L', 7, 17, 1, elbow=(0, 1, -0.5))},
             # west: the sword arm is the far one, so the flung blade is shown rising over the
             # head toward the front instead of hiding behind the plume
             sword=dict(hand='R', dir=(-0.2, -0.7, 0.7),
                        dir_view={'west': (0.35, -0.5, 0.8), 'south': (-0.2, -0.5, 0.85)}),
             cape=(-2, 0, 1), plume=(-3, 0, 1))

# ------------------------------------------------------------------ light attacks (batch 2)
# Attack stances (review 1): wide steps, the front knee bent over the front foot, the weight
# low, as in the concept's C2 / C3 / D2 - not the upright idle or guard stance. The left foot
# leads (right-handed sword). Targets in checks.py (ATTACK_STANCE): pelvis at least 3 px lower
# than idle (4 px for stage 4 and the thrust), ankles at least 14 px apart in the side views
# (18 px for stage 4 and the thrust), front / back views at least the idle's width: the feet
# also step 5 px out to either side.
# stage 1 top (C2): sword raised forward-up on the sword side, weight still on the back foot
L1_TOP = dict(root=(-1, -1, -3), lean=-2, roll=-6,
              feet={'R': (-4, -5, 0, 'flat'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', 10, -5, 4, elbow=(0, -1, -1)), 'L': hand('L', 5, 6, -5, elbow=(0, 1, -1))},
              sword=dict(hand='R', dir=(0.65, -0.1, 0.75)),
              cape=(-1, 0, 0), plume=(-1, 0, 0))
# stage 1 follow-through (C3): blade low across to the other side, weight on the front foot
L1_END = dict(root=(2, 2, -4), lean=12, roll=8,
              feet={'R': (-6, -5, 0, 'toe'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', 8, 4, -5, elbow=(0, -1, 0)), 'L': hand('L', -2, 9, -5, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.65, 0.5, -0.45),
                         dir_view={'south': (0.45, 0.85, -0.2), 'north': (0.45, 0.85, -0.2)}),
              cape=(-3, 0, 1), plume=(-3, 0, 1))
# stage 2 follow-through: the backhand ends high on the sword side
L2_END = dict(root=(2, -1, -3), lean=8, roll=-6,
              feet={'R': (-6, -5, 0, 'toe'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', 7, -9, 3, elbow=(0, -1, -1)), 'L': hand('L', 1, 8, -6, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.45, -0.6, 0.65)),
              cape=(-2, 1, 1), plume=(-2, 1, 0))
# stage 4 wind-up: sword drawn far back, body coiled, weight back and low
L4_TOP = dict(root=(-3, -2, -4), lean=-5, roll=-8,
              feet={'R': (-7, -5, 0, 'flat'), 'L': (6, 5, 0, 'flat')},
              arms={'R': hand('R', -5, -9, 3, elbow=(-1, -1, -1)), 'L': hand('L', 6, 4, -3, elbow=(0, 1, -1))},
              sword=dict(hand='R', dir=(-0.7, -0.25, 0.65)),
              cape=(1, 0, 0), plume=(0, 0, 0), scarf=(-2, 0, 2))
# stage 4 mid-swing (D2): crouched in a long lunge, the blade sweeping level across the front
L4_MID = dict(root=(2, 1, -4), lean=16, roll=4,
              feet={'R': (-8, -5, 0, 'toe'), 'L': (7, 5, 0, 'flat')},
              arms={'R': hand('R', 10, 0, -3, elbow=(0, -1, 0)), 'L': hand('L', -4, 10, -2, elbow=(-1, 1, 0))},
              sword=dict(hand='R', dir=(0.85, 0.45, -0.1), dir_view={'south': (0.5, 0.85, 0.1)}),
              cape=(-4, 0, 2), plume=(-3, 0, 1))
# stage 4 follow-through (D3): the sweep ends low in front, a long step in
L4_END = dict(root=(4, 3, -4), lean=20, roll=10,
              feet={'R': (-8, -5, 0, 'toe'), 'L': (8, 5, 0, 'flat')},
              arms={'R': hand('R', 10, 3, -5, elbow=(0, -1, 0)), 'L': hand('L', -3, 9, -3, elbow=(-1, 1, 0))},
              sword=dict(hand='R', dir=(0.8, 0.35, -0.45),
                         dir_view={'south': (0.35, 0.9, -0.1), 'north': (0.35, 0.9, -0.1)}),
              cape=(-5, 0, 4), plume=(-4, 0, 1))

# ------------------------------------------------------------------ charge, thrust (batch 3)
CHARGE = dict(root=(-3, -1, -3), lean=6, roll=-5,
              feet={'R': (-6, -5, 0, 'flat'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', -3, -7, -6, elbow=(-1, -1, 0)), 'L': hand('L', 9, 3, -1, elbow=(0, 1, -1))},
              sword=dict(hand='R', dir=(1.0, -0.35, 0.05), dir_view={'north': (0.6, -0.7, 0.05)}),
              cape=(-1, 0, 0), plume=(-1, 0, 0))
THRUST = dict(root=(4, -1, -4), lean=24, roll=-4,
              feet={'R': (-9, -5, 0, 'toe'), 'L': (9, 5, 0, 'flat')},
              arms={'R': hand('R', 13, -3, -1, elbow=(0, -1, 0)), 'L': hand('L', -6, 8, -3, elbow=(-1, 1, 0))},
              sword=dict(hand='R', dir=(1.0, -0.25, 0.05),
                         dir_view={'south': (0.6, -0.7, 0.1), 'north': (0.6, -0.7, 0.1)}),
              cape=(-6, 0, 5), plume=(-2, 0, 1))

# ------------------------------------------------------------------ locomotion (batch 3)
DASH = dict(root=(-3, 0, -3), lean=28,
            feet={'R': (-8, 0, 1, 'toe'), 'L': (7, 0, 2, 'reach')},
            arms={'R': hand('R', -6, -9, -5, elbow=(1, -1, 0)), 'L': hand('L', -4, 9, -4, elbow=(1, 1, 0))},
            sword=dict(hand='R', dir=(-0.85, -0.35, -0.4), dir_view={'south': (-0.6, -0.7, -0.3)}),
            cape=(-6, 0, 3), plume=(-5, 0, 2))
BACKSTEP = dict(root=(-1, 0, 1), lean=-10,
                feet={'R': (-5, 0, 2, 'toe'), 'L': (3, 0, 3, 'swing')},
                arms={'R': hand('R', 6, -6, -4, elbow=(0, -1, -1)), 'L': hand('L', 3, 9, -2, elbow=(0, 1, -1))},
                sword=dict(hand='R', dir=(0.8, -0.3, 0.2), dir_view={'north': (0.6, -0.7, 0.2)}),
                cape=(4, 0, 2), plume=(5, 0, 1), head=(-1, 0, 0))
RUN = dict(root=(1, 0, -1), lean=12,
           feet={'R': (6, 0, 0, 'heel'), 'L': (-6, 0, 2, 'toe')},
           arms={'R': hand('R', -5, -10, -6, elbow=(1, -1, 0)), 'L': hand('L', 5, 8, -3, elbow=(-1, 1, -1))},
           sword=dict(hand='R', dir=(-0.7, -0.35, -0.6)),
           cape=(-5, 0, 2), plume=(-4, 0, 1))

# ------------------------------------------------------------------ heal (batch 1, standing)
HEAL = dict(root=(0, 0, 0), lean=6, head_tilt=12, head=(0, 0, -1),
            feet={'R': (1, 0, 0, 'flat'), 'L': (-1, 0, 0, 'flat')},
            # the sword stands point-down out at the right side (a different outline from the
            # guard's bar across the chest), the left hand presses the chest
            arms={'R': hand('R', 2, -15, -5, elbow=(0, -1, 0)), 'L': hand('L', 5, 1, -2, elbow=(0, 1, -1), depth_fore=18, depth_fist=19)},
            sword=dict(hand='R', dir=(0.1, -0.2, -1.0)),
            cape=(0, 0, 0))

# ------------------------------------------------------------------ hit reactions (batch 4)
STAGGER = dict(root=(0, 0, 0), lean=-12, head=(-1, 0, 0), head_tilt=-8,
               feet={'R': (-3, 0, 0, 'flat'), 'L': (3, 0, 3, 'swing')},
               arms={'R': hand('R', -3, -12, 1, elbow=(0, -1, 1)), 'L': hand('L', -2, 12, 2, elbow=(0, 1, 1))},
               sword=dict(hand='R', dir=(-0.6, -0.4, 0.7)),
               cape=(4, 0, 1), plume=(4, 0, 0))
# one knee down, both hands on the pommel of the planted sword (the chibi legs are ~8 px, so
# kneeling lowers the hips ~4 px; the head drops further by leaning and bowing)
_kb = (0.35, 0.05, -1.0)
_kr, _kl = two_hand_grip(6, -2, 0, _kb, back=-2.0)
KNEEL = dict(root=(0, 0, -4), lean=14, head=(0, 0, -1), head_tilt=12,
             feet={'R': (-5, 0, 0, 'kneel'), 'L': (4, 0, 0, 'flat')},
             arms={'R': _kr, 'L': dict(_kl, depth_fore=None, depth_fist=None)},
             sword=dict(hand='R', dir=_kb, grip_back=4.5),
             cape=(1, 0, 0), plume=(-5, 0, -1))
# name, pose, canvas, concept thumbnail, label
KEY_POSES = [
    ('guard', GUARD, 'small', '設計圖沒畫', '格擋 f1'),
    ('parry', PARRY, 'small', '設計圖沒畫', '完美彈返 f4'),
    ('l1_top', L1_TOP, 'large', 'C2', '輕攻擊1 f2 頂點'),
    ('l1_end', L1_END, 'large', 'C3', '輕攻擊1 f4 揮完'),
    ('l2_end', L2_END, 'large', '設計圖沒畫', '輕攻擊2 f4 揮完'),
    ('l4_top', L4_TOP, 'large', '設計圖沒畫', '輕攻擊4 f2 蓄勢'),
    ('l4_mid', L4_MID, 'large', 'D2', '輕攻擊4 f3 揮到一半'),
    ('l4_end', L4_END, 'large', 'D3', '輕攻擊4 f4 揮完'),
    ('charge', CHARGE, 'large', '設計圖沒畫(E)', '蓄力 保持'),
    ('thrust', THRUST, 'large', 'D1', '突刺 f2 前撲'),
    ('dash', DASH, 'small', 'B1', '閃身 衝刺'),
    ('backstep', BACKSTEP, 'small', '設計圖沒畫', '閃身 後跳'),
    ('run', RUN, 'small', 'B', '奔跑 接觸'),
    ('heal', HEAL, 'small', '設計圖沒畫', '治療 保持'),
    ('stagger', STAGGER, 'small', 'F', '踉蹌 f1'),
    ('kneel', KNEEL, 'small', 'G(部分)', '架勢崩潰 f2 跪地'),
]
# lying and launched: restored from the concept's H (concept_pose.lying_frame), not posed
# by the rig (review 1: a standing figure turned a quarter does not read as lying down)
LYING_POSES = [
    ('down', dict(airborne=False), 'small', 'H', '倒地 f4 躺姿'),
    ('launch', dict(airborne=True), 'small', 'H', '擊飛 空中'),
]
