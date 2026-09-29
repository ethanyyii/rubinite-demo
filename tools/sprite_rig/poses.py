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


def planted(feet):
    """Feet placed the same way in every view (batch 3 fix): {'R' / 'L': (ahead, out, lift,
    state)}, `ahead` = px in front of the foot anchor along the facing, `out` = px to the
    character's side. The rig measures a foot from that view's own idle stance (the library's
    east and west stances differ by 3-4 px), so the same offset put the charge's front foot 12
    px from its hip in the west view (its leg is ~9 px: drawn stretched flat) and 8 in the east.
    Returns a feet_view dict for pose_rig."""
    out = {}
    for view, v in P.VIEWS.items():
        fv = {}
        for s_, (ahead, side, lift, state) in feet.items():
            if v['kind'] == 'side':
                hip = 1.0 if s_ == v['near'] else -1.0
                fv[s_] = (ahead - P.SIDE_REST_DX[view][s_] - hip, side, lift, state)
            else:
                fv[s_] = (ahead, side, lift, state)
        out[view] = fv
    return out


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

# plain block taking a hit (batch 1, 6 frames): the blow pushes the guard in, the hands come
# 2 px toward the chest, the pelvis gives 1 px, the back foot slides 1.5 px back; the head
# and the cloth are left a little forward (they follow a frame later)
_hr, _hl = two_hand_grip(4, -4, 3, GUARD_BLADE, elbow_up=0.2)
GUARD_HIT = dict(GUARD, root=(-1, 0, -1), lean=2, head=(1, 0, 0),
                 feet={'R': (-2.5, -4.25, 0, 'flat'), 'L': (2, 4.25, 0, 'flat')},
                 arms={'R': _hr, 'L': _hl}, cape=(1, 0, 0), plume=(1, 0, 0))

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
# stage 1 follow-through (C3): blade low across to the other side, weight on the front foot.
# Batch 2 decision 4: the pelvis ends 4 px ahead of the top (root f 3; batch 0 had 2)
L1_END = dict(root=(3, 2, -4), lean=12, roll=8,
              feet={'R': (-6, -5, 0, 'toe'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', 8, 4, -5, elbow=(0, -1, 0)), 'L': hand('L', -2, 9, -5, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.65, 0.5, -0.45),
                         dir_view={'south': (0.45, 0.85, -0.2), 'north': (0.45, 0.85, -0.2)}),
              cape=(-3, 0, 1), plume=(-3, 0, 1))
# stage 2 follow-through: the backhand ends high on the sword side. Stage 3 starts from stage
# 1's top after it, so its blade is within 22.5 deg of that top in every view (batch 2 decision
# 4: front / back were 39 / 29 deg off; the blade stands a little straighter there)
L2_END = dict(root=(2, -1, -3), lean=8, roll=-6,
              feet={'R': (-6, -5, 0, 'toe'), 'L': (5, 5, 0, 'flat')},
              arms={'R': hand('R', 7, -9, 3, elbow=(0, -1, -1)), 'L': hand('L', 1, 8, -6, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.45, -0.6, 0.65),
                         dir_view={'south': (0.45, -0.3, 0.8), 'north': (0.45, -0.3, 0.8)}),
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
# Batch 3 decision 2 (user, 2026-09-28) replaces batch 0's charge: from the front and the back
# its blade pointed at the camera and it read as "crouched, hand at the hip" like the heal
# (outline difference 8-10 %). Now: the sword hand drawn back to the hip, the blade level with
# its point forward; the off hand reaching forward and out to aim; the pelvis 4 px down (as the
# thrust) and at least 2 px behind the feet's midpoint in both side views (the library's east and
# west stances differ: the front foot +7, the back foot -5 put it 2.3 / 4.7 px back; weight on the
# back foot; a pelvis 1 px further back instead brought the front view's guard outline down to 12 %); front / back, the upper body
# tilts 8 deg toward the off hand (the heal leans 10 deg toward the sword: the other way) and the
# blade reaches out level on the sword side. Each view's blade angle keeps it level on screen
# (appendix C: +-1 px): the side views level in 3D; the front view rises a little and the back
# view dips a little to cancel the depth's slant on screen.
# Guard vs charge and charge vs heal are hard checks now (>= 12 %, checks.py --batch3).
# Fix of 2026-09-28 (the user, reviewing batch 3 again): the charge is a thrust drawn back, so the
# blade points FORWARD in every view, as perspective shows it: level in the side views, a short
# stub toward the camera from the front, hidden behind the body from the back (only the fist,
# pulled back over the cape). Decision 2's sideways blade in front / back read as charging a sweep.
# And its legs came apart in every view: the legs are ~6 px from hip to ankle, and the pelvis 4 px
# down with the feet 14 px apart put the west front foot 12 px from its hip - a ~9 px leg drawn
# stretched flat ("like a worm"); in front / back, feet stepped in depth were drawn as a squat
# with the knees splayed. Now:
#   - the feet are planted() the same way in every view: 4.5 px ahead / 7 behind the anchor, the
#     back foot 7 px out to the sword side (from the front it sits higher, being further back, and
#     the body leaning over it hid all but 2-3 px of it nearer in);
#   - the pelvis 2.5 px down and 2 back: the front knee bends up and the back leg reaches back (an
#     arch from the side), every near leg within its length standing and walking (checks.py);
#   - front / back knees bend by the legs' real reach (legs3d), the blade is held to the floor at
#     its own depth (floor3d);
#   - without the sideways blade the front view's outline was 9-11 % off the guard's (hard check
#     >= 12 %): the weight sits over the back foot on the sword side, the body leaning 16 deg that
#     way (it shows from the front / back only; upright from the side) - guard vs charge and charge
#     vs heal >= 14 % in every view. Decision 2's lean toward the off hand was only there to set it
#     apart from the heal;
#   - the head 1 px forward (eyes on the target): the thrust's release is two steps of <= 8 px.
# Second fix (2026-09-28, the user: "not fixed"; looked at frame by frame, legs drawn alone):
#   - the side legs' bones are ~1.35x the standing reach, so a foot set ahead of the hip threw the
#     knee up level with the hip: the legs drew as a table (east) or an "M" (west). And the west hip
#     joint sat 2.4 px lower on its leg than the east one: 3.6 px from hip to ankle, any step laid
#     it flat. soft_knee (pose_rig) keeps the bones just longer than the reach (the front knee bends
#     1-2 px forward, the back leg nearly straight) and hangs the west legs from where they part;
#   - from the front / back a foot 7 px back rose 3.9 px (KD_FEET) onto the tassets and hung there
#     with no leg: kd_feet takes the body's own KD, and the stance is 9 px (4.5 each way) with the
#     pelvis 1.5 down: every leg keeps >= 2.5 px on screen and the back boot stays on the floor
#     (walking, the back foot lifted and further away would still climb onto the tassets: fb_leg_min
#     holds each leg at >= 2.5 px on screen, as FOOT_BELOW holds a foot stepping toward the camera).
#     Sideways the feet step 5 px out (the front / back views stand as wide as an attack must);
#   - the 16 deg lean over the back foot (put in to pass the outline check) read as falling over:
#     gone. The body leans 8 deg toward the target instead (coiled, in every view; charge vs heal
#     >= 13 % in every view with the hand 12 px out);
#   - the sword hand sits at the hip's outer side (12 px out, low): from the front the stub toward
#     the camera hangs clear of the body (over the tassets' chain mail it vanished), and it points
#     straight ahead (no toe-in: from the front it drew a slanted stub, not one pointing at us);
#     from behind the hilt shows past the fist (hilt_depth).
# front knee bent a little, back leg nearly straight (the front one was 1.1 until the west legs hung
# crossed like the east ones: its knee then rose level with the hip, table-like)
_CHARGE_KNEES = {'L': 1.05, 'R': 1.03}
CHARGE = dict(root=(-0.5, 0, -1.5), lean=8, legs3d=True, floor3d=True, head=(1, 0, 0),
              soft_knee=_CHARGE_KNEES, kd_feet=0.35, fb_leg_min=2.5, body_hides_far=True,
              feet={'R': (0, 0, 0, 'flat'), 'L': (0, 0, 0, 'flat')},
              # 5 px out to each side: from the front / back an attack stands at least as wide as the
              # idle (checks ATTACK_STANCE, review 1); invisible from the side (SIDE_X)
              feet_view=planted({'R': (-4.5, -5, 0, 'flat'), 'L': (4.5, 5, 0, 'flat')}),
              arms={'R': hand('R', -3, -12, -6, elbow=(-1, -1, 0), over_cape=True),
                    'L': hand('L', 10, 7, -1, elbow=(0, 1, -1))},
              sword=dict(hand='R', dir=(1.0, 0.0, 0.0), hilt_depth={'north': 35.2}),
              cape=(-1, 0, 0), plume=(-1, 0, 0))
# Second fix: the side views are the approved D1 lunge (only the west back knee, thrown up by the
# long bones, now straight: soft_knee); from the front / back the feet foreshorten like the body
# (kd_feet: the back boot rose onto the tassets and came loose from its leg); a foot toward the
# camera may sit the rule's full 2 px under the floor.
THRUST = dict(root=(4, -1, -4), lean=24, roll=-4,
              feet={'R': (-9, -5, 0, 'toe'), 'L': (9, 5, 0, 'flat')},
              # second fix: the sword hand 2 px higher (chest height still, under the visor from the
              # side): from the front, where reaching at the camera carries it down the screen, its
              # point ran 3 px past the floor line and read as stuck in the ground
              arms={'R': hand('R', 13, -3, 1, elbow=(0, -1, 0)), 'L': hand('L', -6, 8, -3, elbow=(-1, 1, 0))},
              # batch 3 decision 9: only the blade's angle turned so it is level on screen (+-1 px;
              # batch 0 had its ends 1.5-4.5 px apart); the body is the approved D1 pose
              # 2026-09-28 fix: forward in every view, as the charge (the front / back views had it
              # turned sideways: a sweep, not a thrust); front / back knees by the 3D reach
              sword=dict(hand='R', dir=(1.0, 0.0, 0.0)), legs3d=True, floor3d=True,
              soft_knee=_CHARGE_KNEES, kd_feet=0.35, foot_below=2, fb_leg_min=2.5, body_hides_far=True,
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
# Batch 1 decision 1 (user, 2026-09-27): leaning on the sword. The guard reads "high, wide,
# level" (blade across the chest, elbows out, braced feet, head up); the heal reads "low,
# narrow, slanted": the sword planted point-down at a slant on the sword side, the right hand
# on the pommel, the body leaning onto it and hunched, the head bowed, the left hand pressed
# to the chest with the elbow tucked, the feet under the hips. Both are long states the player
# can walk in (and cannot block while healing), so the two outlines must differ >= 12 % in
# every view (checks.py DISTINCT). Decision 7 (point down, left hand on the chest, head bowed)
# is kept.
# Per view: in front / back a bow is a sinking head (head_tilt there would turn the helmet in
# the picture plane); the hand sits higher in front (a blade long enough to read: the tip on
# the floor cuts it short) and lower from behind (the tip reaching the floor past the cape);
# side views slant the blade forward to the floor at 45-52 degrees.
_HEAL_L = hand('L', 5, 2, -1, elbow=(0, 1, -1), depth_fore=18, depth_fist=19)
# The lean toward the sword is 10 deg (the brief said 7): with the walking legs shared by both
# actions the front view's outlines only differed 9-11 % at 6 deg (checks.py --batch1).
HEAL = dict(root=(0, 0, -1), lean=14, lean_view={'south': 11, 'north': 11},
            roll=-10,                                 # toward the sword (the character's right)
            head_tilt=6, head_tilt_view={'south': 0, 'north': 0},
            head=(1, 0, -1), head_view={'south': (0, 0, -1), 'north': (0, 0, -1)},
            feet={'R': (0, 0, 0, 'flat'), 'L': (0, 0, 0, 'flat')},
            arms={'R': hand('R', 11, -16, -7, elbow=(0, -1, -1)), 'L': _HEAL_L},
            arms_view={'south': {'R': hand('R', 8, -16, -3, elbow=(0, -1, -1)), 'L': _HEAL_L},
                       'north': {'R': hand('R', 8, -16, -9, elbow=(0, -1, -1)), 'L': _HEAL_L}},
            sword=dict(hand='R', dir=(0.65, -0.3, -0.707),
                       dir_view={'south': (0.0, -0.5, -0.87), 'north': (0.0, -0.55, -0.83),
                                 'west': (0.566, -0.3, -0.788)}),
            cape=(0, 0, 0),
            plume=(-3, 0, 1))                         # the bowed head would curl the plume forward

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
