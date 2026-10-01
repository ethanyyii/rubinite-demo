"""Automatic checks for the Boss idle and the four ways he moves (walk, back, strafe_r, strafe_l;
loop, start, stop), the greatsword carried on his right shoulder (animation-review §4.4 and the
numbers the poses were designed to; exit code 1 on any failure).

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
import sword as swd
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


SIDES = ('right', 'left')


def sil_change(a, b):
    a, b = set(a), set(b)
    return len(a ^ b) / len(a | b)


def clip_technical(name, direction, frames, stand, loop=True, foot=None):
    pal = set(B.load_palette())
    bad = sorted({c for f in frames for c in f.values() if tuple(c) not in pal})
    check(f'{name}: every colour in the palette', not bad, f'{len(bad)} off-palette')
    xs = [q[0] for f in frames for q in f]
    ys = [q[1] for f in frames for q in f]
    # the loops: the small frame; the start and stop clips: the attack container around it
    e = 0 if loop else anim_walk.EXT
    W, H = (anim_walk.FW, anim_walk.FH) if loop else anim_walk.BIG
    inside = MARGIN - e <= min(xs) and max(xs) < W - e - MARGIN and MARGIN - e <= min(ys) and max(ys) < H - e - MARGIN
    check(f'{name}: inside the {W}x{H} frame', inside, f'x {min(xs) + e}..{max(xs) + e}, y {min(ys) + e}..{max(ys) + e}')
    # foot: how far a foot may be below the foot line (a foot towards the camera: front and
    # back views, and the side views' sidestep). The sword is on the shoulder, or on its way
    # there from where it stands planted: never lower than that
    lim = foot if foot is not None else (0 if direction in SIDES else FOOT_BELOW)
    lim = max(lim, max(q[1] for q in stand) - GROUND)
    check(f'{name}: nothing more than {lim} px below the foot line', max(ys) <= GROUND + lim, f'lowest {max(ys) - GROUND:+d}')
    base_isl = len(islands(stand))
    worst = max(len(islands(f)) for f in frames)
    check(f'{name}: no new 1-2 px specks', worst <= base_isl, f'standing {base_isl}, worst pose {worst}')
    base_pin = len(rig.pinholes(stand))
    pin = max(len(rig.pinholes(f)) for f in frames)
    check(f'{name}: no new 1 px holes', pin <= base_pin + 1, f'standing {base_pin}, worst pose {pin}')
    # after compositing (animation-review §4.1: listed, with the reason when low): the carried
    # sword lies flat (thin from the side) or points away from / towards the camera (short)
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
    """The carried sword alone, as drawn with the body at rest: (pixels, placement)."""
    S = anim_walk._layers(direction)
    key = (S['view'], direction == 'left')
    anim_walk.frames(direction)                   # fills the cache
    return anim_walk._swords[key]


def render_pose(direction, clip, i):
    if direction == 'left':
        return side.mirror(anim_walk.pose_side(clip, i, far=True))
    if direction == 'right':
        return anim_walk.pose_side(clip, i)
    return anim_walk._front_back(direction, clip, i)


def shown(direction, name, i, what):
    """The pixels of a pose that are the sword's ('sword') or the sword arm's ('arm'): the
    pose is drawn again without that part, what differs is what the part shows of itself.
    Returns (pixels shown, pixels the part has before anything covers it)."""
    clip = anim_walk.clip_of(name)
    full = render_pose(direction, clip, i)
    total = [0]
    if what == 'sword':
        real = anim_walk.sword_pixels
        def fake(*a, **kw):
            pix, place = real(*a, **kw)
            total[0] += len(pix)
            return {}, place
        anim_walk.sword_pixels = fake
    else:
        real = (arm.render, arm.fist_only)
        def fake(*a, **kw):
            total[0] += len(real[0](*a, **kw))
            return {}
        def fake_fist(*a, **kw):
            total[0] += len(real[1](*a, **kw))
            return {}
        arm.render, arm.fist_only = fake, fake_fist
        saved = dict(anim_walk._fists)
        anim_walk._fists.clear()
    try:
        bare = render_pose(direction, clip, i)
    finally:
        if what == 'sword':
            anim_walk.sword_pixels = real
        else:
            arm.render, arm.fist_only = real
            anim_walk._fists.clear()
            anim_walk._fists.update(saved)
    return {q: c for q, c in full.items() if bare.get(q) != c}, total[0]


# the tip end of the carried blade, where nothing else is: the pixel furthest out (the rule
# per direction) and everything within TIP_R px of it
TIP_R = 24
TIP_OF = {'right': lambda f: min(f), 'left': lambda f: max(f), 'down': lambda f: min(f, key=lambda q: (q[1], q[0])),
          'up': lambda f: max(f)}


def tip_patch(direction, f):
    t = TIP_OF[direction](f)
    # (from behind the blade is short and ends beside the arm: only its last 12 px are clear of it)
    return t, {(x - t[0], y - t[1]): c for (x, y), c in f.items() if abs(x - t[0]) <= TIP_R and abs(y - t[1]) <= TIP_R
               and (direction != 'up' or x >= t[0] - 12)}


def carry_pose_checks():
    """The carried sword (user 2026-09-30: every way of moving carries the sword level on the
    right shoulder; "the sword's and the hand's four views"): the four views are one pose."""
    W, H = anim_walk.FW, anim_walk.FH
    place = {d: loop_sword(d)[1] for d in rig.DIRS}
    pix = {d: loop_sword(d)[0] for d in rig.DIRS}
    # --- one 3D pose: the four placements are projections of one fist and one blade direction.
    # The projection is stated here on its own (right: x = F, y = -U + 0.35 (R - fist's R);
    # left: the same with -0.35; down: x = -R, y = -U + 0.35 F; up: x = R, y = -U - 0.35 F)
    cx, gy = rig.AX + 0.5, GROUND + 1
    g = {d: place[d]['grip'] for d in rig.DIRS}
    F = g['right'][0] - cx
    U = {'right': gy - g['right'][1], 'left': gy - g['left'][1], 'down': gy - g['down'][1] + 0.35 * F,
         'up': gy - g['up'][1] - 0.35 * F}
    R = {'down': cx - g['down'][0], 'up': g['up'][0] - cx}
    ok = max(U.values()) - min(U.values()) < 1.0 and abs(R['down'] - R['up']) < 1.0 and abs(g['left'][0] - g['right'][0]) < 0.01
    check('carry: the four views put the fist at one point (same height, same distance from his middle)', ok,
          f'height {", ".join(f"{d} {U[d]:.1f}" for d in rig.DIRS)} px; to his right {R["down"]:.1f} / {R["up"]:.1f} px; '
          f'forward {F:.1f} px')
    n = {d: math.hypot(*swd.standing(rig.VIEW_OF.get(d, "right"))['axis']) for d in rig.DIRS}
    a = {d: (place[d]['axis'][0] / n[d], place[d]['axis'][1] / n[d]) for d in rig.DIRS}
    aF, aR = a['right'][0], -a['down'][0]
    aU = 0.35 * aR - a['right'][1]
    want = {'left': (aF, -aU - 0.35 * aR), 'down': (-aR, -aU + 0.35 * aF), 'up': (aR, -aU - 0.35 * aF)}
    err = max(math.dist(a[d], want[d]) for d in want)
    unit = math.sqrt(aF * aF + aR * aR + aU * aU)
    check('carry: the four views show one blade direction (each view is its projection)', err < 0.02 and abs(unit - 1) < 0.02,
          f'direction (forward {aF:.2f}, right {aR:.2f}, up {aU:.2f}), length {unit:.3f}; worst view off by {err:.3f}')
    yaw, tilt = math.degrees(math.atan2(aR, -aF)), math.degrees(math.asin(aU / unit))
    check('carry: the blade points back, level (tilt 0-12 degrees tip-up), a little outwards (yaw 10-25 degrees)',
          aF < 0 and 0 <= tilt <= 12 and 10 <= yaw <= 25, f'tilt {tilt:.1f}, yaw {yaw:.1f} degrees')
    # --- where the fist is: in front of the right shoulder, at the height of the shoulder plate's top
    S = anim_walk._layers('right')
    plate_top = min(q[1] for q in S['pauldron'].pix if 2 <= q[0] - rig.AX <= 10)
    check('carry: the fist is in front of the shoulder plate, at the height of its top', 8 <= F <= 20 and abs(g['right'][1] - plate_top) <= 4,
          f'fist {F:.0f} px ahead of his middle, row {g["right"][1]:.1f}; the plate\'s top row {plate_top}')
    # --- the blade on screen: long from the side, short pointing away (down) or at the camera (up)
    length = {d: math.hypot(*a[d]) for d in rig.DIRS}
    ok = length['right'] > 0.9 and length['left'] > 0.9 and 0.4 <= length['down'] <= 0.65 and 0.3 <= length['up'] <= 0.55
    check('carry: seen from the side the sword shows its length, from the front and from behind it is foreshortened', ok,
          ', '.join(f'{d} {length[d]:.2f}' for d in rig.DIRS) + ' of its length')
    # before compositing (animation-review §4.1): the redrawn sword is the concept's sword, not a
    # simplified one - it keeps its red core and its pale rim in the standing sword's proportions
    for d in rig.DIRS:
        view = rig.VIEW_OF.get(d, 'right')
        full = swd.sword_image(view, swd.standing(view), (W, H), source='bare')
        n0, (c0, g0) = len(full), detail(full)
        n1, (c1, g1) = len(pix[d]), detail(pix[d])
        red, gold = (c1 / n1) / (c0 / n0), (g1 / n1) / (g0 / n0)
        check(f'carried sword {d}: keeps the sword\'s red core and pale rim (each 70-140% of the standing sword\'s share)',
              0.7 <= red <= 1.4 and 0.7 <= gold <= 1.4, f'{n1} px ({n1 / n0:.0%} of the upright sword); red {red:.0%}, gold {gold:.0%}')


def carry_shown_checks():
    """What shows of the carried sword and of the arm that holds it (pose 5 of the walk)."""
    W, H = anim_walk.FW, anim_walk.FH
    grip_row = loop_sword('right')[1]['grip'][1]
    for d in rig.DIRS:
        vis, total = shown(d, 'walk', 5, 'sword')
        stand = rig.pixels(rig.standing()[d])
        xs, ys = [q[0] for q in stand], [q[1] for q in stand]
        out = {'right': min(xs) - min(q[0] for q in vis), 'left': max(q[0] for q in vis) - max(xs),
               'down': min(ys) - min(q[1] for q in vis), 'up': max(q[0] for q in vis) - max(xs)}[d]
        lo = {'right': 0.75, 'left': 0.5, 'down': 0.6, 'up': 0.5}[d]
        need = {'right': 40, 'left': 40, 'down': 12, 'up': 8}[d]
        check(f'carry {d}: the sword is not hidden by the head or the body ({lo:.0%}+ of it shows, {need}+ px past the standing outline)',
              len(vis) / total >= lo and out >= need, f'{len(vis)} of {total} px show ({len(vis) / total:.0%}); {out} px past the outline')
    vis, total = shown('right', 'walk', 5, 'arm')
    check('carry right: the sword arm is the near arm - it shows (70%+ of it)', len(vis) / total >= 0.7, f'{len(vis)} of {total} px')
    vis, total = shown('down', 'walk', 5, 'arm')
    check('carry down: the sword arm is in front of the shoulder plate - it shows (70%+ of it)', len(vis) / total >= 0.7,
          f'{len(vis)} of {total} px')
    vis, total = shown('left', 'walk', 5, 'arm')
    fist_px = len(arm.render(anim_walk.ARM_JOINTS[('left', 'walk', 5)], (W, H), parts=('fist',)))
    whole = len(arm.render(anim_walk.ARM_JOINTS[('left', 'walk', 5)], (W, H)))
    check('carry left: the sword arm is the far arm - the body hides most of it (under 25% of the arm shows: part of the fist)',
          0 < len(vis) <= 0.25 * whole, f'{len(vis)} px of the arm\'s {whole} show (the fist alone is {fist_px} px)')
    check('carry left: the free hand is the near (left) hand - nothing of the sword arm shows below the fist',
          max(q[1] for q in vis) <= grip_row + 12, f'lowest row of the far arm {max(q[1] for q in vis)}')
    vis, total = shown('up', 'walk', 5, 'arm')
    check('carry up: the hand is in front of him - at most the top of the fist shows over the shoulder', len(vis) <= 0.6 * total,
          f'{len(vis)} of {total} px')


def carry_frame_checks():
    """The same sword in every way of moving and in every pose: the blade's tip end (where
    nothing else is) is the same picture, pixel for pixel, only moved."""
    for d in rig.DIRS:
        ref_tip, ref = tip_patch(d, anim_walk.frames(d, 'walk')[0])
        diff, tips = 0, []
        for kind in anim_walk.KINDS:
            for f in anim_walk.frames(d, kind):
                t, patch = tip_patch(d, f)
                tips.append(t)
                diff += patch != ref
        spread = (max(t[0] for t in tips) - min(t[0] for t in tips), max(t[1] for t in tips) - min(t[1] for t in tips))
        check(f'carry {d}: the four ways of moving show the very same sword (the blade\'s end identical in all {len(tips)} poses)',
              diff == 0 and len(ref) > 60, f'{diff} poses differ; {len(ref)} px compared; the tip ranges over {spread[0]} x {spread[1]} px')
    # --- the sword rides on the shoulder: its tip moves with the body, never more than the body does
    for d in rig.DIRS:
        for kind in anim_walk.KINDS:
            fr = anim_walk.frames(d, kind)
            tips = [TIP_OF[d](f) for f in fr]
            step = max(max(abs(tips[i][0] - tips[i - 1][0]), abs(tips[i][1] - tips[i - 1][1])) for i in range(len(tips)))
            rows = [t[1] for t in tips]
            check(f'{kind} {d}: the sword rides on the shoulder (its tip moves at most 1 px per pose, up and down twice a cycle)',
                  step <= 1 and rows[:10] == rows[10:] and 1 <= max(rows) - min(rows) <= 6,
                  f'tip rows {min(rows)}..{max(rows)}, worst step {step} px')
    # facing left the sword is on the far shoulder: its tip is further from the camera, so higher
    tr, tl = TIP_OF['right'](anim_walk.frames('right', 'walk')[0]), TIP_OF['left'](anim_walk.frames('left', 'walk')[0])
    check('carry: facing left the blade\'s tip is further from the camera than facing right (higher on screen)',
          8 <= tr[1] - tl[1] <= 40 and abs((2 * rig.AX - tl[0]) - tr[0]) <= 2, f'tip row {tr[1]} facing right, {tl[1]} facing left')


def carry_checks():
    carry_pose_checks()
    carry_shown_checks()
    carry_frame_checks()


def arm_numbers(joints):
    """(longest upper arm, shortest and longest elbow-to-fist, the fist's worst angle off the
    forearm's line) of the given joint sets; and whether that is an arm (an arm pointing
    towards or away from the camera is shorter on screen, never longer)."""
    l1, l2, l3 = arm.lengths()
    up, fore, off = 0.0, [], 0.0
    for J in joints:
        up = max(up, math.dist(J['shoulder'], J['elbow']))
        fore.append(math.dist(J['elbow'], J['hand']))
        a1 = math.atan2(J['wrist'][1] - J['elbow'][1], J['wrist'][0] - J['elbow'][0])
        a2 = math.atan2(J['hand'][1] - J['wrist'][1], J['hand'][0] - J['wrist'][0])
        off = max(off, abs(math.degrees(math.atan2(math.sin(a1 - a2), math.cos(a1 - a2)))))
    ok = up <= l1 * 1.05 and max(fore) <= (l2 + l3) * 1.08 and off < 1
    return ok, up, min(fore), max(fore), off


def arm_checks():
    """The sword arm as drawn (anim_walk.ARM_JOINTS): an elbow, bones no longer than they are,
    the fist in line with the forearm - in the carry and in every pose of the way up and down."""
    l1, l2, l3 = arm.lengths()
    for d in ('right', 'left', 'down'):
        names = [k for k in anim_walk.KINDS] + [f'{k}_start' for k in anim_walk.KINDS] \
            + [f'{k}_stop_{e}' for k in anim_walk.KINDS for e in anim_walk.STOP_FROM]
        joints = []
        for name in names:
            fr = anim_walk.frames(d, name)
            joints += [anim_walk.ARM_JOINTS[(d, name, i)] for i in range(len(fr))]
        ok, up, lo, hi, off = arm_numbers(joints)
        fore = joints
        check(f'sword arm {d}: bones never longer than they are, the fist in line with the forearm (all {len(fore)} poses)', ok,
              f'upper arm up to {up:.1f} (its length {l1:.1f}), elbow to fist {lo:.1f}..{hi:.1f} (its length {l2 + l3:.1f}) px; '
              f'fist off the forearm\'s line by at most {off:.1f} degrees')
        if d == 'right':
            J = anim_walk.ARM_JOINTS[(d, 'walk', 5)]
            v = (J['hand'][0] - J['elbow'][0], J['hand'][1] - J['elbow'][1])
            ang = math.degrees(math.atan2(v[0], -v[1]))
            check('carry right: the elbow is bent - the forearm goes up to the fist (within 30 degrees of upright), '
                  'the upper arm comes forward from under the shoulder plate', abs(ang) <= 30 and J['elbow'][0] > J['shoulder'][0]
                  and J['elbow'][1] > J['hand'][1] + 15, f'forearm {ang:.0f} degrees from upright, the elbow '
                  f'{J["elbow"][0] - J["shoulder"][0]:.1f} px ahead of the shoulder, {J["elbow"][1] - J["hand"][1]:.1f} px below the fist')
    import inspect
    src = inspect.getsource(anim_walk.sword_pixels)
    check('the carried sword is drawn without the standing pose\'s fist (the arm brings the fist)', "source='bare'" in src
          and "source='fist'" not in src and "source='raw'" not in src)
    bare, withfist = swd.clean_sword('right'), swd.clean_sword('right', fist=True)
    f0, f1 = swd.BARE['right']['fist_rows']
    count = lambda im: sum(1 for y in range(f0, f1) for x in range(im.width) if im.getpixel((x, y))[3])
    check('the fist-less sword has only the grip where the fist was', count(bare) < 0.5 * count(withfist),
          f'{count(bare)} px in the fist\'s rows (with the fist: {count(withfist)})')


def hand_checks():
    """The user's corrections of 2026-09-30 about the standing pose, measured on the frames."""
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
    # moving, facing left: not the mirror of facing right either
    a, b = anim_walk.frames('left', 'walk')[5], anim_walk.frames('right', 'walk')[5]
    b = {(2 * rig.AX - x, y): c for (x, y), c in b.items()}
    diff = sum(1 for q in set(a) | set(b) if a.get(q) != b.get(q)) / len(set(a) | set(b))
    check('walking left is its own picture, not walking right mirrored', diff > 0.05, f'{diff:.1%} of the pixels differ')


def crown(direction, f, stand_lab):
    """The crown tip: the top of what is over the head's columns."""
    hx = [q[0] for q, v in stand_lab.items() if v == 'head']
    ys = [q[1] for q in f if min(hx) - 12 <= q[0] <= max(hx) + 16 and 0 <= q[1] < 80]
    top = min(ys)
    xs = [q[0] for q in f if q[1] == top and min(hx) - 12 <= q[0] <= max(hx) + 16]
    return sum(xs) / len(xs), top


def head_frame(direction, name, i, f, sword, stand_lab):
    """The pose to find the crown in: the frame itself, or - where the sword raised on the way to
    the shoulder is over the head's columns (it would be taken for the crown, or hide it) - the
    same pose drawn again without the sword."""
    hx = [q[0] for q, v in stand_lab.items() if v == 'head']
    if not any(min(hx) - 12 <= x <= max(hx) + 16 and y < 80 for (x, y) in sword):
        return f
    clip = anim_walk.clip_of(name)
    real = anim_walk.sword_pixels
    anim_walk.sword_pixels = lambda *a, **kw: ({}, real(*a, **kw)[1])
    try:
        return render_pose(direction, clip, i)
    finally:
        anim_walk.sword_pixels = real


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
    lows = [max(q[1] for q in f) for f in frames]
    if direction in SIDES:
        ok = all(GROUND - anim_walk.FAR_UP - 1 <= v <= GROUND for v in lows)
        check(f'{name}: a foot is on the ground in every pose (near foot on the foot line, far foot '
              f'{anim_walk.FAR_UP} px up)', ok, f'lowest rows {lows}')
    else:
        check(f'{name}: the feet alternate (the lowest point moves {FOOT_BELOW // 2}+ px over the cycle)',
              max(lows) - min(lows) >= FOOT_BELOW // 2, f'lowest rows {lows}')
    worst = max(sil_change(frames[i], frames[i - 1]) for i in range(len(frames)))
    check(f'{name}: no pose pops (silhouette changes < 12% between neighbours)', worst < 0.12, f'worst {worst:.1%}')


SWORD_STEP = round(20 * K)         # px the sword's tip may move between two poses (the knight's 20 px x 4)


def sword_of(direction, name, i):
    """(footprint, tip, direction of the blade on screen) of the sword as drawn in a pose."""
    pix, place = anim_walk.SWORD_DRAWN[(direction, name, i)]
    view = rig.VIEW_OF.get(direction, 'right')
    tip = swd.tip_of(view, place)
    foot = set(pix)
    if direction == 'left':
        foot = {(2 * rig.AX - x, y) for (x, y) in foot}
    return foot, tip, math.atan2(place['axis'][1], place['axis'][0])


def standing_sword(direction):
    lab = part_labels(direction)
    view = rig.VIEW_OF.get(direction, 'right')
    place = swd.standing(view)
    return {q for q, v in lab.items() if v == 'sword'}, swd.tip_of(view, place), math.atan2(place['axis'][1], place['axis'][0])


def body_change(a, b, sa, sb):
    """Silhouette change between two poses outside the sword (the sword is a long thin thing
    that swings: wherever it is not in both poses the plain measure counts it twice, and once
    it is thin and clear of the body that is 20% of the picture for any turn above 4 degrees -
    it says nothing about how far the sword moved. The sword has its own limits)."""
    mask = sa | sb
    x = {q for q in set(a) ^ set(b) if q not in mask}
    u = {q for q in set(a) | set(b) if q not in mask}
    return len(x) / len(u)


def joined(name, direction, frames, swords):
    """frames: poses in the order shown (the standing sprite or a loop pose at each end);
    swords: sword_of() / standing_sword() of each."""
    ch = [body_change(frames[i], frames[i + 1], swords[i][0], swords[i + 1][0]) for i in range(len(frames) - 1)]
    check(f'{name}: the body joins without a pop (silhouette outside the sword < 20% per pose)', max(ch) < 0.20,
          f'first {ch[0]:.1%}, worst {max(ch):.1%}, last {ch[-1]:.1%}')
    step = [math.dist(swords[i][1], swords[i + 1][1]) for i in range(len(swords) - 1)]
    turn = [abs(math.degrees(math.atan2(math.sin(swords[i + 1][2] - swords[i][2]), math.cos(swords[i + 1][2] - swords[i][2]))))
            for i in range(len(swords) - 1)]
    check(f'{name}: the sword swings without a jump (its tip at most {SWORD_STEP} px per pose)', max(step) <= SWORD_STEP,
          f'tip {min(step):.0f}..{max(step):.0f} px per pose, the blade turns up to {max(turn):.0f} degrees per pose on screen')


def transition_checks(direction, kind='walk'):
    stand = rig.pixels(rig.standing()[direction])
    lab = part_labels(direction)
    loop = anim_walk.frames(direction, kind)
    start = anim_walk.frames(direction, f'{kind}_start')
    foot = STRAFE_FOOT if kind.startswith('strafe') and direction in SIDES else None
    name = f'{kind}_start {direction}'
    clip_technical(name, direction, start, stand, loop=False, foot=foot)
    j = anim_walk.START_JOINS[kind]
    seq = [stand] + start + [loop[j]]
    swords = [standing_sword(direction)] + [sword_of(direction, f'{kind}_start', i) for i in range(len(start))] \
        + [sword_of(direction, kind, j)]
    joined(name, direction, seq, swords)
    poses = [(f'{kind}_start', i) for i in range(len(start))]
    heads = [seq[0]] + [head_frame(direction, n, i, f, sw[0], lab) for (n, i), f, sw in zip(poses, seq[1:-1], swords[1:-1])] + [seq[-1]]
    rows = [crown(direction, f, lab)[1] for f in heads]
    st = [abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1)]
    check(f'{name}: the head moves at most 2 px per pose', max(st) <= 2, f'crown rows {rows}')
    for e in anim_walk.STOP_FROM:
        stop = anim_walk.frames(direction, f'{kind}_stop_{e}')
        name = f'{kind}_stop {direction} from pose {e}'
        clip_technical(name, direction, stop, stand, loop=False, foot=foot)
        seq = [loop[e]] + stop + [stand]
        swords = [sword_of(direction, kind, e)] + [sword_of(direction, f'{kind}_stop_{e}', i) for i in range(len(stop))] \
            + [standing_sword(direction)]
        joined(name, direction, seq, swords)
        poses = [(f'{kind}_stop_{e}', i) for i in range(len(stop))]
        heads = [seq[0]] + [head_frame(direction, n, i, f, sw[0], lab) for (n, i), f, sw in zip(poses, seq[1:-1], swords[1:-1])] + [seq[-1]]
        rows = [crown(direction, f, lab)[1] for f in heads]
        st = [abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1)]
        check(f'{name}: the head moves at most 2 px per pose', max(st) <= 2, f'crown rows {rows}')


STRAFE_FOOT = 9          # side views, sidestep: a foot 24 px towards the camera is 0.35 x 24 = 8.4 px lower


def move_checks(direction, kind):
    """The backward walk and the sidesteps: the loop."""
    stand = rig.pixels(rig.standing()[direction])
    lab = part_labels(direction)
    frames = anim_walk.frames(direction, kind)
    strafe = kind.startswith('strafe')
    name = f'{kind} {direction}'
    clip_technical(name, direction, frames, stand, foot=STRAFE_FOOT if strafe and direction in SIDES else None)
    sx, sy = crown(direction, stand, lab)
    tips = [crown(direction, f, lab) for f in frames]
    rows = [t[1] for t in tips]
    steps = [abs(rows[i] - rows[i - 1]) for i in range(len(rows))]
    check(f'{name}: the head moves at most 1 px per pose, loop included', max(steps) <= 1, f'crown tip rows {rows}')
    bob = max(rows) - min(rows)
    check(f'{name}: the body rises and falls twice a cycle (2-5 px)', 2 <= bob <= 5 and rows[:10] == rows[10:], f'{bob} px')
    # lean: the sidestep keeps half of the walk's forward lean (he faces the player), backing
    # up he is upright
    share = anim_walk.LEAN_OF[kind]
    if direction in SIDES:
        fwd = [(t[0] - sx) * (1 if direction == 'right' else -1) for t in tips]
        want = (2, 5) if strafe else (-2, 2)
        check(f'{name}: lean - the crown {want[0]}..{want[1]} px ahead of where it stands '
              f'({"half the walk\'s lean" if strafe else "upright"})', want[0] <= min(fwd) and max(fwd) <= want[1],
              f'{min(fwd):.0f}..{max(fwd):.0f} px')
    else:
        k = round(anim_walk.LEAN_ROWS * share) * (1 if direction == 'down' else -1)
        lean = [r - sy for r in rows]
        lo, hi = (2 if strafe else 1) + k, (6 if strafe else 4) + k
        check(f'{name}: hips {2 if strafe else 1}-{6 if strafe else 4} px down, the chest {abs(k)} px '
              f'{"lower" if k > 0 else "higher" if k < 0 else "(no lean)"}', lo <= min(lean) and max(lean) <= hi,
              f'crown {min(lean):+d}..{max(lean):+d} px from standing')
    worst = max(sil_change(frames[i], frames[i - 1]) for i in range(len(frames)))
    check(f'{name}: no pose pops (silhouette changes < 12% between neighbours)', worst < 0.12, f'worst {worst:.1%}')


def move_model_checks():
    """model: the legs of the backward walk and the sidestep."""
    per_pose = gait.STRIDE / gait.POSES
    N = gait.POSES
    # backward: the planted foot moves forward under him exactly the game's distance; each
    # foot lands toe first
    st = [anim_walk.loop_state(i, 'back') for i in range(N)]
    slide, toe_first = [], []
    for k in 'RL':
        for i in range(N):
            a, b = st[i]['leg' + k], st[(i + 1) % N]['leg' + k]
            if a['down'] and b['down'] and a['pitch'] == 0 and b['pitch'] == 0:
                slide.append(b['ankle'][0] - a['ankle'][0])
            if not a['down'] and b['down']:
                toe_first.append(b['pitch'])
    check('back (model): the planted foot moves forward under him the game\'s distance per pose (no sliding)',
          all(abs(v - per_pose) < 0.05 for v in slide), f'{min(slide):.2f}..{max(slide):.2f} px per pose, game {per_pose:.2f}')
    check('back (model): each foot lands toe first (the heel is still up when it touches)', all(p < -5 for p in toe_first),
          f'foot pitch at landing {[round(p) for p in toe_first]} deg')
    check('back (model): a cycle is as long as the walk\'s (not quicker steps)', N * gait.HOLD == 80, f'{N * gait.HOLD} frames')
    for kind in ('strafe_r', 'strafe_l'):
        side = 1 if kind == 'strafe_r' else -1
        st = [anim_walk.loop_state(i, kind) for i in range(N)]
        slide, sep, reach, both = [], [], 0.0, 0
        for i in range(N):
            for k in 'RL':
                a, b = st[i]['leg' + k], st[(i + 1) % N]['leg' + k]
                if a['down'] and b['down']:
                    slide.append((a['lat'] - b['lat']) * side)       # along the travel direction
                # front view: hip joint to ankle on screen against the leg's own length
                out = 1.9 + a['lat'] * (1 if k == 'R' else -1)        # the ankle, outwards from its hip
                drop = st[i]['D'] + (a['ankle'][1] - gait.ANKLE_H)
                rest = math.hypot(1.9, 60.3)
                reach = max(reach, math.hypot(out, 60.3 - drop) / rest)
            r, l = st[i]['legR']['lat'], st[i]['legL']['lat']
            sep.append(2 * (anim_walk.HIP_HALF + 1.9) + r - l)       # right ankle minus left ankle (his right +)
            both += st[i]['legR']['down'] and st[i]['legL']['down']
        check(f'{kind} (model): the planted foot moves back the game\'s distance per pose (no sliding)',
              all(abs(v - per_pose) < 0.05 for v in slide), f'{min(slide):.2f}..{max(slide):.2f} px per pose, game {per_pose:.2f}')
        check(f'{kind} (model): the feet come together and step apart, never far across (ankles {min(sep):.0f}..{max(sep):.0f} px apart)',
              -12 <= min(sep) <= 12 and 60 <= max(sep) <= 84, f'standing {2 * (anim_walk.HIP_HALF + 1.9):.0f} px')
        check(f'{kind} (model): the legs are never longer than they are (front view, hip to ankle)', reach <= 1.03,
              f'longest {reach:.1%}')
        check(f'{kind} (model): both feet down in some poses, a cycle as long as the walk\'s', both >= 2 and N * gait.HOLD == 80,
              f'{both} of {N} poses, {N * gait.HOLD} frames')


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
    # every way of moving: the legs of its start and its four stops
    for kind in anim_walk.KINDS:
        st = anim_walk.start_clip(kind).states
        low = min(low_point(s['leg' + k]) for s in st for k in 'RL')
        check(f'{kind}_start (model): heel and toe never below the ground', low > -0.3, f'{low:.2f} px')
        ext = max(math.dist(s['leg' + k]['hip'], s['leg' + k]['ankle']) / reach for s in st for k in 'RL')
        stretched = any(s['leg' + k]['stretched'] for s in st for k in 'RL')
        check(f'{kind}_start (model): the legs are never longer than their bones', not stretched, f'longest {ext:.1%}')
        for e in anim_walk.STOP_FROM:
            sp = anim_walk.stop_clip(e, kind).states
            stretched = any(s['leg' + k]['stretched'] for s in sp for k in 'RL')
            last = sp[-1]
            home = all(abs(last['leg' + k]['ankle'][0]) < 0.01 and abs(last['leg' + k]['ankle'][1] - gait.ANKLE_H) < 0.01
                       and abs(last['leg' + k].get('lat', 0.0)) < 0.01 for k in 'RL')
            low = min(low_point(s['leg' + k]) for s in sp for k in 'RL')
            check(f'{kind}_stop from pose {e} (model): legs within their bones, feet not below the ground, both end under the hips',
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
    # a start clip that jumps straight to the loop (no transition: the sword is on the shoulder at once)
    results = []
    anim_walk.frames('right', 'walk_start')
    drawn = dict(anim_walk.SWORD_DRAWN)
    anim_walk._frames[('right', 'walk_start')] = [anim_walk.frames('right')[6]] * anim_walk.START_N
    for i in range(anim_walk.START_N):
        anim_walk.SWORD_DRAWN[('right', 'walk_start', i)] = anim_walk.SWORD_DRAWN[('right', 'walk', 6)]
    transition_checks('right')
    caught.append(results.count(False) >= 1)
    anim_walk._frames.clear()
    anim_walk._frames.update(saved)
    anim_walk.SWORD_DRAWN.update(drawn)
    # the carry: one view draws the fist 5 px higher than the other three
    results = []
    loop_sword('down')
    key = ('front', False)
    pix, place = anim_walk._swords[key]
    anim_walk._swords[key] = (pix, dict(place, grip=(place['grip'][0], place['grip'][1] - 5)))
    carry_pose_checks()
    anim_walk._swords[key] = (pix, place)
    caught.append(results.count(False) >= 1)
    # facing left made by mirroring facing right (the sword in the wrong hand), and one way of
    # moving whose sword is not the same picture (a row of the blade's end missing)
    results = []
    for d in rig.DIRS:
        for kind in anim_walk.KINDS:
            anim_walk.frames(d, kind)
    saved = dict(anim_walk._frames)
    anim_walk._frames[('left', 'walk')] = [side.mirror(f) for f in anim_walk.frames('right', 'walk')]
    f = dict(anim_walk.frames('right', 'back')[3])
    tip = TIP_OF['right'](f)
    for dx in range(4, 12):
        f.pop((tip[0] + dx, tip[1]), None)
    anim_walk._frames[('right', 'back')] = anim_walk.frames('right', 'back')[:3] + [f] + anim_walk.frames('right', 'back')[4:]
    hand_checks()
    carry_frame_checks()
    caught.append(results.count(False) >= 3)
    anim_walk._frames.clear()
    anim_walk._frames.update(saved)
    # an arm stretched to a fist it cannot reach, and a fist turned away from its forearm
    J = dict(anim_walk.ARM_JOINTS[('right', 'walk', 5)])
    far = dict(J, hand=(J['hand'][0] + 12, J['hand'][1] - 6), wrist=(J['wrist'][0] + 12, J['wrist'][1] - 6))
    bent = dict(J, hand=(J['wrist'][0] + 6, J['wrist'][1]))
    caught.append(not arm_numbers([far])[0] and not arm_numbers([bent])[0] and arm_numbers([J])[0])
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
    hand_checks()
    carry_checks()
    arm_checks()
    move_model_checks()
    for d in rig.DIRS:
        walk_checks(d)
        transition_checks(d)
    for kind in anim_walk.KINDS[1:]:
        for d in rig.DIRS:
            move_checks(d, kind)
            transition_checks(d, kind)
    n = results.count(False)
    print(f'\n{len(results) - n} passed, {n} failed')
    sys.exit(1 if n else 0)


if __name__ == '__main__':
    main()
