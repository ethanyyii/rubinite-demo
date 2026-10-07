"""The execution: a leap and a downward stab, 3 seconds (180 sim frames). 2026-10-05, the user chose
"躍起下刺" and three seconds ("1 秒太快……刺進去甚至可以轉動劍，讓整體處決更震撼"); the timing is the one
agreed with the user (docs/art-progress.md "處決動畫"; combat-design §11.4):

| time | knight | game (player_sim._tick_execute) |
|---|---|---|
| 0-0.4 s | rushes in, crouches low (the sword turned point-down in the fist) | closes to body contact (45 px from the Boss's centre) |
| 0.4-0.8 s | leaps; both hands on the grip, raised over the head, point down | the shadow moves in to EXECUTE_PERCH (22 px) |
| 0.8 s (48) | drives it into the Boss's upper chest / neck: damage, hitstop, shake, flash | |
| 0.8-2.0 s | hangs on the sword, presses down; twists it at 75 and 102 | stays |
| 2.0 s (120) | a foot braced on him, kicks off, pulls the sword out, jumps back | flies back to EXECUTE_LAND_DIST (72 px) |
| 2.5 s (150) | lands crouched | |
| 2.5-3.0 s | stands up facing the Boss | |

Height off the floor (`air`) is drawn into the picture (pose_rig `air`); the game draws the shadow at the
feet (as the Boss's leap draws its lift). The leap is a throw: up 80 px at frame 42, falling after it.

Per-part plan (animation-review §4.2):
| part | rush, crouch | leap | plunge | hang, twist | brace, kick | flight, land, stand |
|---|---|---|---|---|---|---|
| legs | a lunge step, then both knees deep (coiled) | push off, then tucked under | tucked, knees forward | hanging, the front foot braced on him; each twist kicks the legs | front foot up on his chest, knees tight; then both straighten | legs come forward under the body; land on both, knees give; rise |
| pelvis | low 2 -> 4 | up with the throw | | swings with each twist | pulled in, then thrown back | low 4 on landing, up to the stance |
| torso | leans in 14-20 deg | upright, back 6 at the top | leans over the hands 18 | 4-8 deg; jerks 8 deg on a twist | leans back 15, then 25 | back -> forward 16 on landing -> upright |
| sword hand | low behind the hip, blade down-back | swings up to the grip over the head | driven down to the chest line | holds the hilt (the sword stays still in the Boss) | pulls the blade out up-back | the blade swung down behind on the sword side |
| off hand | back for the jump | up onto the grip (above the right: the pommel side) | on the grip | on the grip | on the grip, then lets go out for balance | out front for balance, then at the side |
| head | a frame late | tipped back, eyes up | down over the hands | a frame late | back | a frame late |
| cape, plume | stream back | lag down as he rises, then up as he falls | thrown up | hang, swing with the twists | | fly forward on the landing, settle |
"""
import math

import pose_rig as PR
import poses as PS
import batch1 as B1

VIEWS = B1.VIEWS
CANVAS = 'exec'

# ------------------------------------------------------------------ game numbers (player_data.gd)
LEAP_AT, HIT_AT, KICK_AT, LAND_AT, END_AT = 24, 48, 120, 150, 180
TWISTS = (75, 102)

# ------------------------------------------------------------------ the throw
APEX_AT, APEX = 42, 80.0                         # frame and height of the leap's top (feet)
_G = 2.0 * APEX / (APEX_AT - LEAP_AT) ** 2       # px / frame^2 of the rise (and the fall before the plunge)


def leap_air(f):
    """Feet height off the floor at sim frame f of the leap (24-48)."""
    t = f - LEAP_AT
    return max(0.0, (APEX_AT - LEAP_AT) * _G * t - 0.5 * _G * t * t)


# the sword stays in the Boss from the plunge to the kick. Where it goes in (ENTRY): 13 px from the
# Boss's centre toward the knight (his chest's surface; the knight's shadow is EXECUTE_PERCH 22 px from
# the centre), 75 px up (the kneeling Boss's upper chest: his shoulders are 84-94, the crown 107-116;
# measured on boss_kneel_breathe). Its hilt (the right fist's centre) and the blade's direction follow,
# in the knight's own space measured from his shadow (forward, left, up)
PERCH = 28.0
ENTRY = (PERCH - 13.0, -1.0, 75.0)
BLADE_IN = PR.vnorm((0.7, 0.1, -0.7))
SHOW = 0.6                                       # how much of the blade shows outside the Boss
GRIP_BACK = 4.5                                  # two hands on the grip
HILT = PR.vsub(ENTRY, PR.vscale(BLADE_IN, 2.0 + SHOW * 15.0))   # sword.GUARD_AT + the blade that shows
SH_UP = 12.0                                     # chest centre above the hip (side views: the hip 9 px over the feet)
HIP_UP = 9.0
HANG_U = -4.0                                    # hanging: the hands this far over the chest centre
HANG_LEAN = -14
# both fists on a grip in front of the face, 10 px out: the shoulders are 21 px apart, so each 13 px arm
# needs a little more (the left one reaches across and up to the pommel end)
HANG_K = {'R': 1.1, 'L': 1.25}
HANG_AIR = round(HILT[2] - HANG_U - HIP_UP - SH_UP * math.cos(math.radians(HANG_LEAN)))
# the jump back: off the kick a little up (peak 6 frames on), down to the floor at LAND_AT
_KT = LAND_AT - KICK_AT
_KG = 2.0 * HANG_AIR / (_KT * _KT - 12.0 * _KT)
_KV = 6.0 * _KG


def back_air(f):
    t = f - KICK_AT
    return max(0.0, HANG_AIR + _KV * t - 0.5 * _KG * t * t)


def chest_world(air, root, lean):
    """Where the chest-space origin is, in the knight's space from his shadow: the rig turns the upper
    body about the hip by the lean (side views; front / back sink it the same amount)."""
    a = math.radians(lean)
    return (root[0] + SH_UP * math.sin(a), root[1], air + root[2] + HIP_UP + SH_UP * math.cos(a))


def hilt_hand(air, root, lean):
    """The right fist on the hilt that stays in the Boss, in chest space for this body."""
    return PR.vsub(HILT, chest_world(air, root, lean))


def grip(at, blade, back=GRIP_BACK, el_r=(0, -1, 0), el_l=(0, 1, 0)):
    """Both hands on the grip: the right at `at` (chest space), the left `back` px toward the pommel."""
    return {'R': PS.hand('R', *at, elbow=el_r), 'L': PS.hand('L', 0, 0, 0, elbow=el_l, on_grip=back)}


def ease(t):
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ key poses (character space)
REST = B1.REST
LEGS = dict(soft_knee=1.03, legs3d=True, kd_feet=0.35, fb_leg_min=2.5, body_hides_far=True)

# a lunge step in (the game carries him up to 38 px to body contact in 0.4 s)
STEP = dict(LEGS, root=(0, 0, -0.5), lean=12, head=(1, 0, 0),
            feet={'R': (-3.5, -2, 0, 'toe'), 'L': (3, 2, 0, 'flat')},
            arms={'R': PS.hand('R', -4, -11, -8, elbow=(1, -1, 0)), 'L': PS.hand('L', 4, 10, -5, elbow=(0, 1, -1))},
            sword=dict(hand='R', dir=PR.vnorm((-0.3, -0.35, -0.88)), grip_back=2.0),
            cape=(-3, 0, 2), plume=(-2, 0, 1))
# the crouch before the leap: a deep coil, the weight over both feet, the arms back for the swing up;
# the sword point-down behind the sword-side hip (turned in the fist: from here on the grip is reversed
# - at 40 px a reversed grip shows only as the blade hanging down from the fist)
# the knight's legs are ~6 px from hip to ankle: hips more than 1 px down fold the side views' knees over
# the hips or stretch the legs past their length (checks_execute: every combination tried), so the coil is
# the lean (28-32 deg: the head drops 6-7 px) and the arms, not the hips
CROUCH = dict(LEGS, root=(-1, 0, -1), lean=28, head=(1, 0, 0), head_tilt=-6,
              feet={'R': (-4, -3, 0, 'toe'), 'L': (3, 3, 0, 'flat')},
              arms={'R': PS.hand('R', -9, -10, -5, elbow=(1, -1, 0)), 'L': PS.hand('L', -9, 10, -5, elbow=(1, 1, 0))},
              sword=dict(hand='R', dir=PR.vnorm((-0.75, -0.2, -0.62)), grip_back=2.0),
              cape=(-2, 0, 1), plume=(-3, 0, 1))
# the last of the coil: the arms swung all the way back, the head up at the target
COIL = dict(CROUCH, lean=32, head=(1, 0, 1), head_tilt=-12,
            arms={'R': PS.hand('R', -11, -9, -2, elbow=(1, -1, 0.3)), 'L': PS.hand('L', -11, 9, -2, elbow=(1, 1, 0.3))},
            sword=dict(hand='R', dir=PR.vnorm((-0.85, -0.2, -0.48)), grip_back=2.0))
# the push off: legs straight, toes last on the floor, arms swinging forward and up to the grip
TAKEOFF = dict(LEGS, root=(0, 0, 0), lean=6, head=(0, 0, 0), head_tilt=-6,
               feet={'R': (-3, 0, 0, 'toe'), 'L': (1, 0, 0, 'toe')},
               arms=grip((5, -1, 4), PR.vnorm((0.2, 0.0, -1.0)), el_r=(0, -1, -0.5), el_l=(0, 1, -0.5)),
               sword=dict(hand='R', dir=PR.vnorm((0.2, 0.0, -1.0)), grip_back=GRIP_BACK),
               cape=(1, 0, -2), plume=(1, 0, -1))
# the top of the leap: both fists over the helmet, the blade slanting forward past the face (straight
# down it would go through the head: animation-review §4.3, the Boss's plunge). The 13 px arms only reach
# the brow, so in these frames they are drawn longer (ARM_K_TOP; they pass behind the helmet, only the
# fists and the hilt show over it). Legs tucked, the body tipped back, eyes up
ARM_K_TOP = 1.7
RAISE_BLADE = PR.vnorm((0.35, 0.0, -1.0))
RAISE = dict(LEGS, root=(0, 0, 0), lean=-6, head=(-1, 0, 0), head_tilt=-8,
             feet={'R': (-3, 0, 5, 'flat'), 'L': (3, 0, 7, 'flat')},
             arms=grip((1, -1, 22), RAISE_BLADE, el_r=(0, -1, 0.3), el_l=(0, 1, 0.3)),
             sword=dict(hand='R', dir=RAISE_BLADE, grip_back=GRIP_BACK,
                        depth={'south': 52.6, 'east': 52.6, 'west': 52.6, 'north': -35}),
             arm_k=ARM_K_TOP, cape=(2, 0, 3), plume=(2, 0, 3))
# the plunge (frame 48): leaning over the hands driven down to the waist, knees tucked forward
PLUNGE_LEAN = 18
PLUNGE = dict(LEGS, root=(0, 0, 0), lean=PLUNGE_LEAN, head=(1, 0, -1), head_tilt=8,
              feet={'R': (-2, 0, 6, 'flat'), 'L': (4, 0, 8, 'flat')},
              arms=grip(hilt_hand(leap_air(HIT_AT), (0, 0, 0), PLUNGE_LEAN), BLADE_IN, el_r=(0, -1, 0.2), el_l=(0, 1, 0.2)),
              sword=dict(hand='R', dir=BLADE_IN, grip_back=GRIP_BACK, show=SHOW),
              cape=(1, 0, 4), plume=(1, 0, 3))
# hanging on the hilt, the weight pulling it down: arms reaching forward to it (so the hilt and the fists
# show past the helmet), the body leaning back from it, the front foot braced on his chest
HANG = dict(LEGS, root=(0, 0, 0), lean=HANG_LEAN, head=(1, 0, 0), head_tilt=6,
            feet={'R': (4, 0, 4, 'flat'), 'L': (7, 0, 8, 'flat')},
            arms=grip(hilt_hand(HANG_AIR, (0, 0, 0), HANG_LEAN), BLADE_IN, el_r=(-0.3, -1, 0.3), el_l=(-0.3, 1, 0.3)),
            sword=dict(hand='R', dir=BLADE_IN, grip_back=GRIP_BACK, show=SHOW),
            arm_k=HANG_K, cape=(0, 0, 0), plume=(-1, 0, 0))


def at_hilt(pose, air):
    """Put the hands back on the still hilt after an in-between moved the body."""
    p = dict(pose)
    p['arms'] = dict(p['arms'], R=dict(p['arms']['R'], at=hilt_hand(air, p.get('root', (0, 0, 0)), p.get('lean', 0.0))))
    p['sword'] = dict(p['sword'], dir=BLADE_IN, show=SHOW)
    return p


# the twists (75, 102): the hands wring the hilt a quarter turn each way - the crossguard goes from
# across the blade to end-on (guard_half 2 -> 0) and back the second time; the elbows wind up (one high,
# one low) and swap as the hilt turns, the body jerks with the effort and the legs kick
def wind(k):
    """Before twist k (0, 1): elbows set, body coiled the other way, knees drawn up."""
    p = dict(HANG, roll=-4 if k == 0 else 4, lean=HANG_LEAN - 2,
             feet={'R': (-3, 0, 3, 'flat'), 'L': (3, 0, 6, 'flat')},
             arms=grip(HANG['arms']['R']['at'], BLADE_IN, el_r=(0, -1, 0.9), el_l=(0, 1, -0.3)) if k == 0 else
             grip(HANG['arms']['R']['at'], BLADE_IN, el_r=(0, -1, -0.3), el_l=(0, 1, 0.9)),
             sword=dict(HANG['sword'], guard_half=2 if k == 0 else 0))
    return p


def twist(k):
    """Twist k: the hilt turned (guard end-on after the first, across again after the second); the
    elbows swapped, the body jerked (the hit's own reaction is the Boss's twitch, program sparks)."""
    p = dict(HANG, roll=4 if k == 0 else -4, lean=HANG_LEAN + 4, head=(0.5, 0, -0.5), head_tilt=6,
             feet={'R': (1, 0, 2, 'flat'), 'L': (6, 0, 5, 'flat')},
             arms=grip(HANG['arms']['R']['at'], BLADE_IN, el_r=(0, -1, -0.3), el_l=(0, 1, 0.9)) if k == 0 else
             grip(HANG['arms']['R']['at'], BLADE_IN, el_r=(0, -1, 0.9), el_l=(0, 1, -0.3)),
             sword=dict(HANG['sword'], guard_half=0 if k == 0 else 2),
             cape=(1, 0, 2), plume=(2, 0, 1))
    return p


# kicking off (109-120): the front foot up on his chest, knees tight, leaning back on the hilt; at 120
# both legs straighten and throw him back, the blade sliding out along its own line
BRACE = dict(HANG, root=(-1, 0, 1), lean=-10, head=(-1, 0, 0), head_tilt=-4,
             feet={'R': (2, 0, 6, 'flat'), 'L': (7, 0, 10, 'flat')},
             cape=(1, 0, 0), plume=(1, 0, 0))
PULL = 8.0                                       # px the hilt comes back along the blade at the kick
KICK_BLADE = BLADE_IN
KICK = dict(LEGS, root=(-2, 0, 0), lean=-18, head=(-2, 0, 1), head_tilt=-4,
            feet={'R': (6, 0, 5, 'flat'), 'L': (9, 0, 7, 'flat')},
            sword=dict(hand='R', dir=KICK_BLADE, grip_back=GRIP_BACK, show=1.0),
            cape=(4, 0, 2), plume=(4, 0, 2))
KICK['arms'] = grip(PR.vsub(PR.vsub(HILT, PR.vscale(BLADE_IN, PULL)), chest_world(HANG_AIR, KICK['root'], KICK['lean'])),
                    BLADE_IN, el_r=(0, -1, -0.4), el_l=(0, 1, -0.4))
KICK['arm_k'] = HANG_K
# in the air going back: the left hand lets go and goes out front, the sword swings down behind on the
# sword side (still point-down), the legs come forward under him for the landing
FLY = dict(LEGS, root=(0, 0, 0), lean=-6, head=(-1, 0, 0), head_tilt=-4,
           feet={'R': (1, 0, 3, 'flat'), 'L': (5, 0, 4, 'flat')},
           arms={'R': PS.hand('R', -5, -10, -3, elbow=(1, -1, 0)), 'L': PS.hand('L', 7, 8, 0, elbow=(0, 1, -1))},
           sword=dict(hand='R', dir=PR.vnorm((-0.45, -0.25, -0.85)), grip_back=2.0),
           cape=(3, 0, 4), plume=(3, 0, 3))
# landing crouched (150): knees deep, leaning over them, the off hand forward-low, the sword low behind
LAND = dict(LEGS, root=(-1, 0, -1), lean=20, head=(1, 0, 0), head_tilt=4,
            feet={'R': (-4, -3, 0, 'toe'), 'L': (3, 3, 0, 'flat')},
            arms={'R': PS.hand('R', -6, -10, -9, elbow=(1, -1, 0)), 'L': PS.hand('L', 8, 7, -8, elbow=(0, 1, -1))},
            sword=dict(hand='R', dir=PR.vnorm((-0.5, -0.3, -0.81)), grip_back=2.0),
            cape=(-4, 0, 2), plume=(-2, 0, 1))


def _k(p, s_):
    k = p.get('arm_k', 1.0)
    return k.get(s_, 1.0) if isinstance(k, dict) else k


def _lerp_extra(a, b, t, out):
    out['arm_k'] = {s_: _k(a, s_) + (_k(b, s_) - _k(a, s_)) * t for s_ in 'RL'}
    sa, sb = a.get('sword', {}), b.get('sword', {})
    out['sword']['show'] = sa.get('show', 1.0) + (sb.get('show', 1.0) - sa.get('show', 1.0)) * t
    near = sa if t < 0.5 else sb
    for k in ('guard_half', 'depth'):
        if k in near:
            out['sword'][k] = near[k]
    return out


def mix(a, b, t, view, air):
    """In-between of two key poses for one view, `air` px off the floor."""
    ra, rb = B1.resolve(a, view), B1.resolve(b, view)
    p = _lerp_extra(ra, rb, t, B1.lerp_pose(ra, rb, t, view))
    p['air'] = int(round(air))
    return p


def key(a, view, air=0.0):
    return mix(a, a, 0.0, view, air)


def _sink(f):
    """Feet height from the plunge (48) down to the hang (58)."""
    t = ease(min(1.0, max(0.0, (f - HIT_AT) / 10.0)))
    return leap_air(HIT_AT) + (HANG_AIR - leap_air(HIT_AT)) * t


def _kick_pose(view, t, air):
    """The kick's pull: the hands come back along the blade as it slides out (show grows), t 0-1."""
    p = mix(BRACE, KICK, t, view, air)
    hilt = PR.vsub(HILT, PR.vscale(BLADE_IN, PULL * t))
    c = chest_world(air, p['root'], p['lean'])
    p['arms'] = grip(PR.vsub(hilt, c), BLADE_IN, el_r=(0, -1, -0.4), el_l=(0, 1, -0.4))
    p['arm_k'] = HANG_K
    p['sword'] = dict(hand='R', dir=BLADE_IN, grip_back=GRIP_BACK, show=SHOW + (1.0 - SHOW) * t)
    return p


# (name, first sim frame, builder(view)); each frame holds until the next one starts
FRAMES = [
    ('起步', 0, lambda v: mix(REST, STEP, 0.5, v, 0)),
    ('衝', 3, lambda v: key(STEP, v)),
    ('踏', 7, lambda v: mix(STEP, CROUCH, 0.5, v, 0)),
    ('蹲', 11, lambda v: key(CROUCH, v)),
    ('蹲深', 18, lambda v: key(COIL, v)),
    ('起跳', 24, lambda v: mix(COIL, TAKEOFF, 0.6, v, leap_air(24))),
    ('上升 1', 26, lambda v: key(TAKEOFF, v, leap_air(26))),
    ('上升 2', 28, lambda v: mix(TAKEOFF, RAISE, 0.35, v, leap_air(28))),
    ('上升 3', 30, lambda v: mix(TAKEOFF, RAISE, 0.62, v, leap_air(30))),
    ('上升 4', 33, lambda v: mix(TAKEOFF, RAISE, 0.86, v, leap_air(33))),
    ('最高 1', 36, lambda v: key(RAISE, v, leap_air(36))),
    ('最高 2', 39, lambda v: key(RAISE, v, leap_air(39))),
    ('最高 3', 42, lambda v: key(RAISE, v, leap_air(42))),
    ('下刺 1', 44, lambda v: mix(RAISE, PLUNGE, 0.3, v, leap_air(44))),
    ('下刺 2', 46, lambda v: mix(RAISE, PLUNGE, 0.65, v, leap_air(46))),
    ('插下去', HIT_AT, lambda v: key(PLUNGE, v, leap_air(HIT_AT))),
    ('壓下 1', 52, lambda v: at_hilt(mix(PLUNGE, HANG, 0.45, v, _sink(52)), _sink(52))),
    ('壓下 2', 55, lambda v: at_hilt(mix(PLUNGE, HANG, 0.8, v, _sink(55)), _sink(55))),
    ('掛 1', 58, lambda v: at_hilt(key(HANG, v, HANG_AIR), HANG_AIR)),
    ('掛 2', 63, lambda v: at_hilt(mix(HANG, wind(0), 0.4, v, HANG_AIR), HANG_AIR)),
    ('擰 1', 68, lambda v: at_hilt(key(wind(0), v, HANG_AIR), HANG_AIR)),
    ('轉劍 1', TWISTS[0], lambda v: at_hilt(key(twist(0), v, HANG_AIR + 1), HANG_AIR + 1)),
    ('轉劍 1 收', 78, lambda v: at_hilt(mix(twist(0), dict(HANG, sword=dict(HANG['sword'], guard_half=0)), 0.5, v, HANG_AIR), HANG_AIR)),
    ('掛 3', 82, lambda v: at_hilt(key(dict(HANG, sword=dict(HANG['sword'], guard_half=0)), v, HANG_AIR), HANG_AIR)),
    ('掛 4', 89, lambda v: at_hilt(mix(dict(HANG, sword=dict(HANG['sword'], guard_half=0)), wind(1), 0.4, v, HANG_AIR), HANG_AIR)),
    ('擰 2', 95, lambda v: at_hilt(key(wind(1), v, HANG_AIR), HANG_AIR)),
    ('轉劍 2', TWISTS[1], lambda v: at_hilt(key(twist(1), v, HANG_AIR + 1), HANG_AIR + 1)),
    ('轉劍 2 收', 105, lambda v: at_hilt(mix(twist(1), HANG, 0.5, v, HANG_AIR), HANG_AIR)),
    ('抬腳', 109, lambda v: at_hilt(mix(HANG, BRACE, 0.6, v, HANG_AIR + 1), HANG_AIR + 1)),
    ('蹬', 114, lambda v: at_hilt(key(BRACE, v, HANG_AIR + 2), HANG_AIR + 2)),
    ('蹬開', KICK_AT, lambda v: _kick_pose(v, 1.0, back_air(KICK_AT))),
    ('後跳 1', 122, lambda v: mix(KICK, FLY, 0.25, v, back_air(122))),
    ('後跳 2', 125, lambda v: mix(KICK, FLY, 0.5, v, back_air(125))),
    ('後跳 3', 128, lambda v: mix(KICK, FLY, 0.75, v, back_air(128))),
    ('後跳 4', 131, lambda v: key(FLY, v, back_air(131))),
    ('落下 1', 134, lambda v: key(FLY, v, back_air(134))),
    ('落下 2', 137, lambda v: mix(FLY, LAND, 0.12, v, back_air(137))),
    ('落下 3', 140, lambda v: mix(FLY, LAND, 0.24, v, back_air(140))),
    ('落下 4', 142, lambda v: mix(FLY, LAND, 0.34, v, back_air(142))),
    ('落下 5', 144, lambda v: mix(FLY, LAND, 0.44, v, back_air(144))),
    ('落下 6', 146, lambda v: mix(FLY, LAND, 0.56, v, back_air(146))),
    ('落下 7', 148, lambda v: mix(FLY, LAND, 0.7, v, back_air(148))),
    ('落地', LAND_AT, lambda v: key(LAND, v)),
    ('落地 2', 154, lambda v: key(LAND, v)),
    ('起身 1', 160, lambda v: mix(LAND, REST, 0.3, v, 0)),
    ('起身 2', 165, lambda v: mix(LAND, REST, 0.6, v, 0)),
    ('起身 3', 170, lambda v: mix(LAND, REST, 0.85, v, 0)),
    ('站好', 175, lambda v: key(REST, v)),
]


def holds():
    starts = [f[1] for f in FRAMES] + [END_AT]
    return [b - a for a, b in zip(starts, starts[1:])]


def air_of(pose):
    return int(pose.get('air', 0))


class Frame(B1.Frame):
    """One drawn frame; `start` is its first sim frame, `air` how far its feet are off the floor."""


_CACHE = {}


def frames(view):
    """The execution's frames for one view, drawn on the 'exec' canvas (88 x 152, feet anchor (44, 141))."""
    if view in _CACHE:
        return _CACHE[view]
    out = []
    for (name, start, build), dur in zip(FRAMES, holds()):
        pose = build(view)
        r = PR.rig(view)
        px = r.frame(pose, CANVAS)
        if HIT_AT <= start <= KICK_AT:
            # the sword is in the Boss: its hilt is one point in the knight's space (HILT; at the kick pulled
            # PULL px back along the blade), drawn where that point projects in this view. The chest-space
            # hand above is close (chest_world() simplifies the rig's shoulders); the drawn fist is moved
            # the rest of the way (the projection is linear: one correction is exact)
            hilt = HILT if start < KICK_AT else PR.vsub(HILT, PR.vscale(BLADE_IN, PULL))
            pose = pin_fist(pose, view, r, hilt)
            px = r.frame(pose, CANVAS)
        dx, dy = r.canvas_offset()
        sh = lambda d: {(x + dx, y + dy): c for (x, y), c in d.items()}
        trace = {(x + dx, y + dy): n for (x, y), n in r.trace.items()}
        dbg = {'blade': {(x + dx, y + dy) for (x, y) in r.debug.get('blade', set())},
               'hands': {k: (x + dx, y + dy) for k, (x, y) in r.debug.get('hands', {}).items()},
               'legs': {k: tuple((q[0] + dx, q[1] + dy) for q in v) for k, v in r.debug.get('legs', {}).items()},
               'pelvis': (r.debug['pelvis'][0] + dx, r.debug['pelvis'][1] + dy)}
        f = Frame('execute', name, dur, view, px, trace, {n: sh(v) for n, v in r.pieces.items()},
                  {n: sh(v) for n, v in r.pieces_raw.items()}, dbg, pose)
        f.start, f.air = start, air_of(pose)
        out.append(f)
    _CACHE[view] = out
    return out


def target(view, point):
    """A point of the knight's space (forward, left, up from his shadow) on this view's canvas."""
    _, _, ax, ay = PR.CANVAS[CANVAS]
    dx, dy = PR.proj(view, point)
    return (ax + dx, ay + dy)


def pin_fist(pose, view, r, point):
    """The pose with its right fist moved onto `point` as drawn (r has just drawn `pose`)."""
    dx0, dy0 = r.canvas_offset()
    hx, hy = r.debug['hands']['R']
    tx, ty = target(view, point)
    ex, ey = tx - (hx + dx0), ty - (hy + dy0 - pose.get('air', 0) * 0)
    f_, l_, u_ = pose['arms']['R']['at']
    v = PR.VIEWS[view]
    if v['kind'] == 'side':
        f_ += ex * v['facing']
    else:
        l_ += ex * (1 if view == 'south' else -1)
    u_ -= ey
    p = dict(pose)
    p['arms'] = dict(p['arms'], R=dict(p['arms']['R'], at=(f_, l_, u_)))
    return p


def wound(view):
    """Where the blade goes into the Boss on screen while it is in him (the drawn end of the blade, the
    same pixel through the hang), relative to the feet anchor: the game puts the twists' sparks there."""
    fr = next(f for f in frames(view) if f.name == '掛 1')
    hand = fr.debug['hands']['R']
    far = max(fr.debug['blade'], key=lambda q: (q[0] - hand[0]) ** 2 + (q[1] - hand[1]) ** 2)
    _, _, ax, ay = PR.CANVAS[CANVAS]
    return (far[0] - ax, far[1] - ay)
