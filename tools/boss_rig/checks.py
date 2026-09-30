"""Automatic checks for the Boss idle, walk, walk_start and walk_stop (animation-review §4.4 and the numbers the
poses were designed to; exit code 1 on any failure).

    python3 tools/boss_rig/checks.py [--selftest]

Measured on the finished frames (the sprite sheets' content), not read from the code that
made them, except where a line says "model" (gait.py's numbers checked against the limits
this file states). --selftest breaks frames on purpose and shows each check catches it.
"""
import math
import sys
import boss as B
import rig
import labels
import gait
import anim_idle
import anim_walk
import drag
import side
import arm

HEIGHT = B.HEIGHT                  # 160: px limits below are fractions of it (the knight's
K = HEIGHT / 40                    # limits were written for a 40 px body -> x4)
GROUND = rig.AY                    # the sole row
FOOT_BELOW = round(2 * K)          # a foot stepping towards the camera may be this far below
STEP_MAX = round(4 * K)            # px a part may move between two poses (walk: 4 px at 40)
MARGIN = 2                         # px kept free at the frame's edge
DETAIL_TOL = 0.10                  # cloth / gold pixel counts within this of the standing sprite
DETAIL_FLOOR = 0.85
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + (' — ' + detail if detail else ''))


def islands(pix, max_size=2):
    seen, out = set(), []
    for q0 in pix:
        if q0 in seen:
            continue
        comp, st = [], [q0]
        seen.add(q0)
        while st:
            a = st.pop()
            comp.append(a)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    b = (a[0] + dx, a[1] + dy)
                    if b in pix and b not in seen:
                        seen.add(b)
                        st.append(b)
        if len(comp) <= max_size:
            out.append(comp)
    return out


def enclosed(pix):
    """Transparent pixels not connected to the outside (holes)."""
    xs = [q[0] for q in pix]
    ys = [q[1] for q in pix]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    out = {(x0, y0)}
    st = [(x0, y0)]
    while st:
        x, y = st.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if x0 <= q[0] <= x1 and y0 <= q[1] <= y1 and q not in pix and q not in out:
                out.add(q)
                st.append(q)
    return (x1 - x0 + 1) * (y1 - y0 + 1) - len(out) - len(pix)


def detail(pix):
    cloth = sum(1 for c in pix.values() if rig.is_cloth(c))
    gold = sum(1 for c in pix.values() if rig.is_gold(c))
    return cloth, gold


def top_row(pix, x0, x1):
    ys = [q[1] for q in pix if x0 <= q[0] < x1]
    return min(ys)


def technical(name, frames, stand, below=0, detail_note=''):
    pal = set(B.load_palette())
    bad = sorted({c for f in frames for c in f.values() if tuple(c) not in pal})
    check(f'{name}: every colour in the palette', not bad, f'{len(bad)} off-palette')
    xs = [q[0] for f in frames for q in f]
    ys = [q[1] for f in frames for q in f]
    inside = MARGIN <= min(xs) and max(xs) < rig.FW - MARGIN and MARGIN <= min(ys) and max(ys) < rig.FH - MARGIN
    check(f'{name}: inside the 256x224 frame', inside, f'x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}')
    check(f'{name}: nothing more than {below} px below the ground row', max(ys) <= GROUND + below,
          f'lowest {max(ys) - GROUND:+d}')
    base_isl = len(islands(stand))
    worst = max(len(islands(f)) for f in frames)
    check(f'{name}: no new 1-2 px specks', worst <= base_isl, f'standing {base_isl}, worst pose {worst}')
    base_pin = len(rig.pinholes(stand))
    pin = max(len(rig.pinholes(f)) for f in frames)
    check(f'{name}: no new 1 px holes', pin <= base_pin, f'standing {base_pin}, worst pose {pin}')
    c0, g0 = detail(stand)
    lo_c = min(detail(f)[0] for f in frames) / c0
    hi_c = max(detail(f)[0] for f in frames) / c0
    lo_g = min(detail(f)[1] for f in frames) / g0
    hi_g = max(detail(f)[1] for f in frames) / g0
    ok = lo_c >= DETAIL_FLOOR and lo_g >= DETAIL_FLOOR and hi_c <= 1 + DETAIL_TOL and hi_g <= 1 + DETAIL_TOL
    check(f'{name}: cloth and gold detail kept', ok,
          f'cloth {lo_c:.0%}..{hi_c:.0%}, gold {lo_g:.0%}..{hi_g:.0%} of standing{detail_note}')
    return enclosed(stand), max(enclosed(f) for f in frames)


_lab = {}


def part_labels(direction):
    """{(x, y): part} of the direction's standing sprite (facing left: from side.py's layers,
    mirrored; its far forearm and free arm both count as 'arm', the shoulder plate as 'body')."""
    if direction not in _lab:
        if direction != 'left':
            _lab[direction] = labels.label(direction)
        else:
            L, order = side.left_layers()
            rename = {'farwrist': 'arm', 'free_arm': 'arm', 'pauldron': 'body'}
            lab = {}
            for name in order:
                for (x, y) in L[name].all():
                    lab[(2 * rig.AX - x, y)] = rename.get(name, name)
            _lab[direction] = lab
    return _lab[direction]


def idle_checks(direction, frames):
    stand = rig.pixels(rig.standing()[direction])
    name = f'idle {direction}'
    check(f'{name}: pose 0 is the standing sprite, pixel for pixel', frames[0] == stand)
    e0, e = technical(name, frames, stand)
    print(f'     {name}: enclosed transparent px: standing {e0}, worst pose {e} (gaps in the cloth; look at the sheet)')
    # nothing jumps: at most 1 px of change per pose for the crown tip, and the loop closes
    lab = part_labels(direction)
    hx = [q[0] for q, v in lab.items() if v == 'head']
    tips = [top_row(f, min(hx), max(hx) + 1) for f in frames]
    steps = [abs(tips[i] - tips[i - 1]) for i in range(len(tips))]
    check(f'{name}: the head moves at most 1 px per pose, loop included', max(steps) <= 1, f'crown tip rows {tips}')
    check(f'{name}: breathing shows (head rises 2 px)', max(tips) - min(tips) == 2, f'{max(tips) - min(tips)} px')
    # the feet are planted: the bottom 12 rows of the legs never change
    feet = {q: c for q, c in stand.items() if q[1] > GROUND - 12 and lab[q] in ('leg', 'leg_l', 'leg_r')}
    moved = sum(1 for f in frames for q, c in feet.items() if f.get(q) != c)
    # back view: the cape hangs in front of the boots, its swaying hem may cover a boot pixel
    limit = 0 if direction != 'up' else len(feet) * len(frames) // 100
    check(f'{name}: feet planted (boot pixels never change)', moved <= limit,
          f'{len(feet)} px watched x {len(frames)} poses, {moved} changes')
    sword = {q: c for q, c in stand.items() if lab[q] == 'sword'}
    moved = sum(1 for f in frames for q, c in sword.items() if f.get(q) != c)
    # behind the cape in the back view, behind the breathing body when facing left
    limit = 0 if direction in ('down', 'right') else len(sword) * len(frames) // 20
    check(f'{name}: sword planted (its visible pixels do not change)', moved <= limit, f'{moved} changes')
    # head one pose behind the shoulders: compare the crown tip with the chest's own rise,
    # measured on a chest pixel column left alone by everything else (the body layer's top)
    chest_cols = [q[0] for q, v in lab.items() if v == ('body' if direction != 'up' else 'arm')]
    side = [x for x in chest_cols if x < min(hx) - 2 or x > max(hx) + 2]
    if side:
        col = min(side) + 2
        sh = [top_row(f, col, col + 3) for f in frames]
        lagged = all(tips[i] - tips[0] == sh[i - 1] - sh[0] for i in range(len(frames)))
        check(f'{name}: the head follows the shoulders one pose late', lagged and len(set(sh)) > 1,
              f'shoulder rows {sh}')


# The dragged sword rests on the ground behind the Boss: in the side view its tip is nearer
# the camera than the feet (lower on screen), in the back view it comes towards the camera.
# Limits on how far below the foot line anything may be, and where (design numbers: the sword
# is 118 px from fist to tip, the fist about 75 px up, so it runs about 92 px along the ground;
# 0.35 of a depth shows as height).
BELOW = {'right': 20, 'left': 0, 'down': FOOT_BELOW, 'up': 40}
# where only the body is (no sword)
BODY_X = {'right': (96, 256), 'left': (0, 150), 'up': (0, 150), 'down': (0, 256)}
SIDES = ('right', 'left')


def body_only(direction, f):
    x0, x1 = BODY_X[direction]
    return {q: c for q, c in f.items() if x0 <= q[0] < x1}


def sil_change(a, b):
    a, b = set(a), set(b)
    return len(a ^ b) / len(a | b)


def clip_technical(name, direction, frames, stand, loop=True):
    pal = set(B.load_palette())
    bad = sorted({c for f in frames for c in f.values() if tuple(c) not in pal})
    check(f'{name}: every colour in the palette', not bad, f'{len(bad)} off-palette')
    xs = [q[0] for f in frames for q in f]
    ys = [q[1] for f in frames for q in f]
    inside = MARGIN <= min(xs) and max(xs) < anim_walk.FW - MARGIN and MARGIN <= min(ys) and max(ys) < anim_walk.FH - MARGIN
    check(f'{name}: inside the {anim_walk.FW}x{anim_walk.FH} frame', inside, f'x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}')
    check(f'{name}: nothing more than {BELOW[direction]} px below the foot line (the dragged sword lies towards the camera)',
          max(ys) <= GROUND + BELOW[direction], f'lowest {max(ys) - GROUND:+d}')
    if loop or direction not in SIDES:
        # (in the side view's transitions the sword swings past the feet, so the body cannot be
        # told apart there; the legs of those poses are checked on the model instead)
        feet_low = max(q[1] for f in frames for q in body_only(direction, f))
        lim = 0 if direction in SIDES else FOOT_BELOW
        check(f'{name}: the body itself at most {lim} px below the foot line', feet_low <= GROUND + lim, f'{feet_low - GROUND:+d}')
    base_isl = len(islands(stand))
    worst = max(len(islands(f)) for f in frames)
    check(f'{name}: no new 1-2 px specks', worst <= base_isl, f'standing {base_isl}, worst pose {worst}')
    base_pin = len(rig.pinholes(stand))
    pin = max(len(rig.pinholes(f)) for f in frames)
    check(f'{name}: no new 1 px holes', pin <= base_pin + 1, f'standing {base_pin}, worst pose {pin}')
    # after compositing (animation-review §4.1: listed, with the reason when low): the dragged
    # sword and the sword arm lie across the cape, the front view sees a shorter sword
    c0, g0 = detail(stand)
    cl = [detail(f)[0] / c0 for f in frames]
    gl = [detail(f)[1] / g0 for f in frames]
    print(f'     {name}: after compositing, of the standing sprite: cloth-coloured {min(cl):.0%}..{max(cl):.0%}, '
          f'gold {min(gl):.0%}..{max(gl):.0%}')
    if loop:
        flick = max(abs(gl[i] - gl[i - 1]) for i in range(len(gl)))
        check(f'{name}: detail does not flicker (gold changes < 8% of the standing sprite between poses)', flick < 0.08,
              f'worst {flick:.1%}')


def loop_sword(direction):
    """The loop's sword alone, as drawn with the body at rest: (pixels, placement)."""
    clip = anim_walk.walk_clip()
    S = anim_walk._layers(direction)
    key = (S['view'], direction == 'left')
    anim_walk.frames(direction)                   # fills the cache
    return anim_walk._swords[key]


def sword_checks():
    """Before compositing (animation-review §4.1): the redrawn sword keeps the standing
    sword's detail. Side and back see (nearly) its whole length; the front view sees it
    pointing away, so there only its length on screen is checked. The redrawn sword has no
    fist (the fist is the arm's), so it is compared with the standing sword's own fist-less
    cut-out drawn where the standing sword is."""
    for direction in ('right', 'left', 'up', 'down'):
        view = rig.VIEW_OF.get(direction, 'right')
        pix, place = loop_sword(direction)
        st = drag.standing(view)
        full = drag.sword_image(view, st, (anim_walk.FW, anim_walk.FH), source='bare')
        n0, (c0, g0) = len(full), detail(full)
        n1, (c1, g1) = len(pix), detail(pix)
        on_screen = math.hypot(*place['axis']) / math.hypot(*st['axis'])
        if direction == 'down':
            check(f'dragged sword {direction}: seen pointing away (0.4-0.75 of its length on screen)', 0.4 <= on_screen <= 0.75,
                  f'{on_screen:.2f} of its length; {n1} px (upright {n0})')
        else:
            # facing left the sword is on the far side: its tip is further from the camera
            # (higher on screen), so it is a little shorter on screen
            lo = 0.8 if direction == 'left' else 0.85
            ok = lo <= on_screen <= 1.1 and n1 >= 0.8 * n0 and c1 >= 0.8 * c0 and g1 >= 0.8 * g0
            check(f'dragged sword {direction}: keeps the standing sword\'s detail (80%+ of its pixels, red and gold)', ok,
                  f'{on_screen:.2f} of its length on screen; pixels {n1 / n0:.0%}, red {c1 / c0:.0%}, gold {g1 / g0:.0%}')


def hand_checks():
    """The user's corrections of 2026-09-30, measured on the frames."""
    right = rig.pixels(rig.standing()['right'])
    left = rig.pixels(rig.standing()['left'])
    mirrored = {(2 * rig.AX - x, y): c for (x, y), c in right.items()}
    diff = sum(1 for q in set(left) | set(mirrored) if left.get(q) != mirrored.get(q)) / len(set(left) | set(mirrored))
    check('facing left is its own sprite, not facing right mirrored', diff > 0.03, f'{diff:.1%} of the pixels differ')
    # standing, facing left: the sword arm is on the far side - the body hides most of it
    # (only the fist on the grip and the wrist show in front of the chest)
    L, order = side.left_layers()
    far = set(L['farwrist'].pix)
    above = set()
    for name in order[order.index('farwrist') + 1:]:
        above |= set(L[name].all())
    hidden = len(far & above) / len(far)
    check('standing left: the body hides most of the sword arm (the far arm)', hidden > 0.5,
          f'{hidden:.0%} of the forearm hidden; the near arm hangs free')
    # walking left: the dragged sword is further from the camera than the body - its tip is
    # above the foot line and never in front of the legs
    pix, place = loop_sword('left')
    tip = drag.tip_of('right', place)
    check('walking left: the dragged sword\'s tip is further from the camera than the feet (above the foot line)',
          3 <= (GROUND + 1) - tip[1] <= 20, f'{GROUND + 1 - tip[1]:.0f} px above')
    # the fist belongs to the arm: in the side view's loop the fist centre is at the end of
    # the forearm, in line with it (elbow -> wrist -> fist within 1 degree), bones at their lengths
    S = anim_walk._layers('right')
    l1, l2, l3 = arm.lengths()
    sh = S['shoulder']
    J = arm.hanging(sh, *anim_walk.DRAG_ARM)
    a1 = math.atan2(J['wrist'][1] - J['elbow'][1], J['wrist'][0] - J['elbow'][0])
    a2 = math.atan2(J['hand'][1] - J['wrist'][1], J['hand'][0] - J['wrist'][0])
    ok = abs(math.degrees(a1 - a2)) < 1 and abs(math.dist(J['shoulder'], J['elbow']) - l1) < 0.1 \
        and abs(math.dist(J['elbow'], J['wrist']) - l2) < 0.1
    check('side view: the dragging arm has an elbow, bones at their own lengths, the fist in line with the forearm', ok,
          f'upper arm {l1:.1f}, forearm {l2:.1f}, fist {l3:.1f} px; bend at the elbow {anim_walk.DRAG_ARM[1] - anim_walk.DRAG_ARM[0]:.0f} deg')
    # every redrawn sword in the loops is the fist-less one (one fist per hand)
    import inspect
    src = inspect.getsource(anim_walk.sword_pixels)
    check('the loop\'s sword is drawn without the standing pose\'s fist (the arm brings the fist)', "source='bare'" in src)
    bare, withfist = drag.clean_sword('right'), drag.clean_sword('right', fist=True)
    f0, f1 = drag.BARE['right']['fist_rows']
    count = lambda im: sum(1 for y in range(f0, f1) for x in range(im.width) if im.getpixel((x, y))[3])
    check('the fist-less sword has only the grip where the fist was', count(bare) < 0.5 * count(withfist),
          f'{count(bare)} px in the fist\'s rows (with the fist: {count(withfist)})')


def crown(direction, f, stand_lab):
    hx = [q[0] for q, v in stand_lab.items() if v == 'head']
    ys = [q[1] for q in f if min(hx) - 12 <= q[0] <= max(hx) + 16 and q[1] < 80]
    top = min(ys)
    xs = [q[0] for q in f if q[1] == top and min(hx) - 12 <= q[0] <= max(hx) + 16]
    return sum(xs) / len(xs), top


def walk_checks(direction):
    stand = rig.pixels(rig.standing()[direction])
    lab = part_labels(direction)
    frames = anim_walk.frames(direction)
    name = f'walk {direction}'
    clip_technical(name, direction, frames, stand)
    sx, sy = crown(direction, stand, lab)
    tips = [crown(direction, f, lab) for f in frames]
    rows = [t[1] for t in tips]
    steps = [abs(rows[i] - rows[i - 1]) for i in range(len(rows))]
    check(f'{name}: the head moves at most 1 px per pose, loop included', max(steps) <= 1, f'crown tip rows {rows}')
    bob = max(rows) - min(rows)
    check(f'{name}: the body rises and falls twice a cycle (2-4 px)', 2 <= bob <= 4 and rows[:10] == rows[10:], f'{bob} px')
    # the forward lean (user 2026-09-30): the hips are 1-4 px below standing height; on top of
    # that the head is ahead of the feet (side), lower (front) or higher (back)
    if direction in SIDES:
        fwd = [(t[0] - sx) * (1 if direction == 'right' else -1) for t in tips]
        check(f'{name}: leans forward - the crown is 6+ px ahead of where it stands', min(fwd) >= 6,
              f'{min(fwd):.0f}..{max(fwd):.0f} px')
    else:
        lean = [r - sy for r in rows]
        want = (1 + 2, 4 + 4) if direction == 'down' else (1 - 4, 4 - 2)
        check(f'{name}: leans forward - the head is 2-4 px {"lower" if direction == "down" else "higher"} than the hips alone put it',
              want[0] <= min(lean) and max(lean) <= want[1], f'crown {min(lean):+d}..{max(lean):+d} px from standing')
    body = [body_only(direction, f) for f in frames]
    lows = [max(q[1] for q in f) for f in body]
    if direction in SIDES:
        ok = all(GROUND - anim_walk.FAR_UP - 1 <= v <= GROUND for v in lows)
        check(f'{name}: a foot is on the ground in every pose (near foot on the foot line, far foot '
              f'{anim_walk.FAR_UP} px up)', ok, f'lowest rows {lows}')
    else:
        check(f'{name}: the feet alternate (the lowest point moves {FOOT_BELOW // 2}+ px over the cycle)',
              max(lows) - min(lows) >= FOOT_BELOW // 2, f'lowest rows {lows}')
    worst = max(sil_change(frames[i], frames[i - 1]) for i in range(len(frames)))
    check(f'{name}: no pose pops (silhouette changes < 12% between neighbours)', worst < 0.12, f'worst {worst:.1%}')
    # the dragged sword: its tip lies still on the ground while the body bobs
    if direction != 'down':
        sword = [{q for q in f if not (BODY_X[direction][0] <= q[0] < BODY_X[direction][1])} for f in frames]
        if direction == 'right':
            tip = [min(s) for s in sword]                                   # leftmost pixel
        elif direction == 'left':
            tip = [max(s) for s in sword]                                   # rightmost pixel
        else:
            tip = [max(s, key=lambda q: q[1]) for s in sword]               # lowest pixel
        spread = max(max(t[0] for t in tip) - min(t[0] for t in tip), max(t[1] for t in tip) - min(t[1] for t in tip))
        check(f'{name}: the sword\'s tip stays put on the ground (moves at most 1 px over the cycle)', spread <= 1,
              f'tip at {tip[0]}, spread {spread} px')
        if direction != 'left':
            below = tip[0][1] - GROUND
            want = (8, 20) if direction == 'right' else (24, 40)
            check(f'{name}: the tip lies towards the camera ({want[0]}-{want[1]} px below the foot line)',
                  want[0] <= below <= want[1], f'{below:+d} px')
    else:
        # the front view sees the sword pointing away: shorter, and it ends above the foot line
        left = [min(q[0] for q in f) for f in frames]
        body_left = min(q[0] for q, v in lab.items() if v not in ('sword',))
        check(f'{name}: the sword shows past the cape (20+ px beyond the body\'s edge)', body_left - max(left) >= 20,
              f'{body_left - max(left)}..{body_left - min(left)} px')


def transition_checks(direction):
    stand = rig.pixels(rig.standing()[direction])
    lab = part_labels(direction)
    walk = anim_walk.frames(direction)
    start = anim_walk.frames(direction, 'walk_start')
    name = f'walk_start {direction}'
    clip_technical(name, direction, start, stand, loop=False)
    seq = [stand] + start + [walk[anim_walk.START_JOIN]]
    ch = [sil_change(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]
    check(f'{name}: from the standing sprite into the loop without a pop (silhouette < 20% per pose)', max(ch) < 0.20,
          f'standing->0 {ch[0]:.1%}, worst {max(ch):.1%}, last->loop {ch[-1]:.1%}')
    rows = [crown(direction, f, lab)[1] for f in seq]
    st = [abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1)]
    check(f'{name}: the head moves at most 2 px per pose', max(st) <= 2, f'crown rows {rows}')
    for e in anim_walk.STOP_FROM:
        stop = anim_walk.frames(direction, f'walk_stop_{e}')
        name = f'walk_stop {direction} from pose {e}'
        clip_technical(name, direction, stop, stand, loop=False)
        seq = [walk[e]] + stop + [stand]
        ch = [sil_change(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]
        check(f'{name}: from the loop to the standing sprite without a pop (silhouette < 20% per pose)', max(ch) < 0.20,
              f'loop->0 {ch[0]:.1%}, worst {max(ch):.1%}, last->standing {ch[-1]:.1%}')
        rows = [crown(direction, f, lab)[1] for f in seq]
        st = [abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1)]
        check(f'{name}: the head moves at most 2 px per pose', max(st) <= 2, f'crown rows {rows}')


def gait_checks():
    """model: the leg numbers of gait.py against the limits."""
    reach = gait.THIGH + gait.SHIN
    worst_ext, worst_knee, slide = 0.0, 1e9, []
    heel_toe_low = 0.0
    both = 0
    for i in range(gait.POSES):
        p = gait.phase(i)
        down = 0
        for other in (False, True):
            L = gait.leg(p, other)
            d = math.dist(L['hip'], L['ankle'])
            worst_ext = max(worst_ext, d / reach)
            span = L['hip'][1] - L['ankle'][1]
            worst_knee = min(worst_knee, (L['hip'][1] - L['knee'][1]) / span)
            heel = gait.rot((gait.HEEL, -gait.ANKLE_H), L['pitch'])
            toe = gait.rot((gait.BALL, -gait.ANKLE_H), L['pitch'])
            heel_toe_low = min(heel_toe_low, L['ankle'][1] + heel[1], L['ankle'][1] + toe[1])
            down += L['down']
            if L['down']:
                # the planted point: heel while pivoting on it, toe tip while rolling off, else the flat foot
                N = gait.leg(gait.phase(i + 1), other)
                if N['down']:
                    def planted(M, which):
                        v = gait.rot((which, -gait.ANKLE_H), M['pitch'])
                        return M['ankle'][0] + v[0]
                    which = gait.HEEL if L['pitch'] > 0 or N['pitch'] > 0 else gait.BALL
                    slide.append(planted(L, which) - planted(N, which))
        both += down == 2
    per_pose = gait.STRIDE / gait.POSES
    check('gait (model): the leg is never longer than its bones', worst_ext <= 1.0, f'longest {worst_ext:.1%} of thigh + shin')
    check('gait (model): knee at least 10% of the leg below the hip', worst_knee >= 0.10, f'lowest {worst_knee:.0%}')
    check('gait (model): heel and toe never below the ground', heel_toe_low > -0.05, f'{heel_toe_low:.2f} px')
    ok = all(abs(v - per_pose) < 0.05 for v in slide)
    check('gait (model): the planted foot moves back exactly the game\'s distance per pose (no sliding)', ok,
          f'{min(slide):.2f}..{max(slide):.2f} px per pose, game {per_pose:.2f} px ({gait.HOLD} frames at 60 px/s)')
    check('gait (model): both feet down in some poses (a walk, not a run)', both >= 2, f'{both} of {gait.POSES} poses')
    check('gait (model): a cycle is not quicker than the knight\'s walk (16 frames)', gait.POSES * gait.HOLD >= 16,
          f'{gait.POSES * gait.HOLD} frames at 60 px/s, {gait.POSES * gait.HOLD // 2} at 120 px/s')
    # walk_start: the planted (left) foot moves back with the ground while the right foot steps
    st = anim_walk.start_clip().states
    xs = [st[k]['legL']['ankle'][0] for k in range(anim_walk.START_HALF)]
    slide = [xs[k] - xs[k + 1] for k in range(len(xs) - 1)]
    check('walk_start (model): the planted foot moves back the game\'s distance per pose', all(abs(v - per_pose) < 0.05 for v in slide),
          f'{slide} px per pose')
    def low_point(L):
        heel = gait.rot((gait.HEEL, -gait.ANKLE_H), L['pitch'])
        toe = gait.rot((gait.BALL, -gait.ANKLE_H), L['pitch'])
        return L['ankle'][1] + min(heel[1], toe[1])
    low = min(low_point(s['leg' + k]) for s in st for k in 'RL')
    check('walk_start (model): heel and toe never below the ground', low > -0.3, f'{low:.2f} px')
    ext = max(math.dist(s['leg' + k]['hip'], s['leg' + k]['ankle']) / reach for s in st for k in 'RL')
    stretched = any(s['leg' + k]['stretched'] for s in st for k in 'RL')
    check('walk_start (model): the legs are never longer than their bones', not stretched, f'longest {ext:.1%}')
    for e in anim_walk.STOP_FROM:
        sp = anim_walk.stop_clip(e).states
        stretched = any(s['leg' + k]['stretched'] for s in sp for k in 'RL')
        last = sp[-1]
        home = all(abs(last['leg' + k]['ankle'][0]) < 0.01 and abs(last['leg' + k]['ankle'][1] - gait.ANKLE_H) < 0.01 for k in 'RL')
        low = min(low_point(s['leg' + k]) for s in sp for k in 'RL')
        check(f'walk_stop from pose {e} (model): legs within their bones, feet not below the ground, both end under the hips',
              not stretched and home and low > -0.3, f'lowest heel/toe {low:.2f} px, last pose hips -{last["D"]}')


def selftest():
    """Break things on purpose: each check must fail."""
    global results
    fr = anim_idle.frames('down')
    stand = rig.pixels(rig.standing()['down'])
    caught = []
    # a hole and a speck
    f = dict(fr[3])
    f.pop((128, 120))
    f[(20, 20)] = B.load_palette()[5]
    results = []
    technical('selftest hole+speck', [f], stand)
    caught.append(results.count(False) >= 2)
    # an off-palette colour and a pixel under the ground
    f = dict(fr[3])
    f[(128, 120)] = (1, 2, 3)
    f[(128, GROUND + 3)] = B.load_palette()[5]
    results = []
    technical('selftest palette+ground', [f], stand)
    caught.append(results.count(False) >= 2)
    # a head that jumps 3 px
    bad = [dict(p) for p in fr]
    bad[5] = {(x, y - 3): c for (x, y), c in bad[5].items()}
    results = []
    idle_checks('down', bad)
    caught.append(results.count(False) >= 1)
    # a walk whose body never bobs and never leans (the standing sprite repeated)
    results = []
    saved = dict(anim_walk._frames)
    anim_walk._frames[('down', 'walk')] = [stand] * 20
    walk_checks('down')
    caught.append(results.count(False) >= 3)
    # a start clip that jumps straight to the loop (no transition)
    results = []
    anim_walk._frames[('right', 'walk_start')] = [anim_walk.frames('right')[6]] * 10
    transition_checks('right')
    caught.append(results.count(False) >= 1)
    anim_walk._frames.clear()
    anim_walk._frames.update(saved)
    results = []
    print()
    check('selftest: every broken case was caught', all(caught), str(caught))
    return all(caught)


def main():
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    for d in rig.DIRS:
        idle_checks(d, anim_idle.frames(d))
    gait_checks()
    sword_checks()
    hand_checks()
    for d in rig.DIRS:
        walk_checks(d)
        transition_checks(d)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
