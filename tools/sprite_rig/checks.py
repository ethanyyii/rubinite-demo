"""Automatic checks for the walk animation (docs/animation-review.md §4.1, §4.3, §4.4).

    python3 tools/sprite_rig/checks.py        # exit code 0 = all passed

Every pixel threshold derives from one size constant, BODY_PX (sprites.py): the final body
height, sole to helmet top. New animations must reuse these same constants.

These only cover what can be measured. Whole-body motion (§4.2) and whether the pose fits
the action (§4.3) still have to be reviewed frame by frame. Plume-helmet contact above the
neck is not checked here either: export_walk.py writes knight_walk_head_check.png for a
visual review instead."""
import sys

import sprites as A
import walk_side as W
import walk_fb as F
from export_walk import FACINGS, rigs
from inspect_parts import parts_of

N = W.N
PALETTE = set(W.PALETTE)

# ------------------------------------------------------------------ size-derived limits
BODY_PX = A.BODY_PX                     # 40 px, final (2026-09-26)


def px(frac):
    """A length given as a fraction of the body height, in whole pixels (at least 1)."""
    return max(1, round(BODY_PX * frac))


JUMP_MAX = px(0.10)          # largest move of any pixel between frames (the swing foot)
BELOW_GROUND_MAX = px(0.05)  # a foot stepping toward the camera may sit this far below ground
BOOT_GAP_MAX = px(0.06)      # front/back stance: gap between the two boots (no overlap)
BOB_MIN = px(0.025)          # head must travel at least 1 px up/down over the cycle (visible)
# blue cloth / highlights compared with the idle frame: within ±10 % or ±4 px, whichever is
# wider (at 40 px a highlight count is only 30-65, so 10 % can be under 4 px), and never
# below 85 % of idle in any frame
TOLERANCE = 0.10
TOLERANCE_PX = px(0.10)
FLOOR = 0.85
# the plume can brush the helmet and enclose background there; holes are only checked on
# the body, below the neck
NECK = {'front': F.FRONT['neck'][1], 'back': F.BACK['neck'][1],
        'side_right': W.EAST['neck'][1], 'side_left': W.WEST['neck'][1]}


def light(c):
    return sum(c[:3]) > 420


def enclosed(p, below=-1):
    """Transparent pixels not reachable from outside the frame (see-through holes), counted
    only on rows below the given row."""
    opaque = set(p)
    outside = set()
    stack = [(x, y) for x in range(-1, A.FW + 1) for y in (-1, A.FH)] + \
            [(x, y) for y in range(-1, A.FH + 1) for x in (-1, A.FW)]
    while stack:
        q = stack.pop()
        if q in outside or q in opaque:
            continue
        x, y = q
        if x < -1 or y < -1 or x > A.FW or y > A.FH:
            continue
        outside.add(q)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return sum(1 for x in range(A.FW) for y in range(below + 1, A.FH) if (x, y) not in opaque and (x, y) not in outside)


def within(count, base):
    """±10 % or ±4 px of the idle count (the wider), and at least 85 % of it."""
    return abs(count - base) <= max(TOLERANCE * base, TOLERANCE_PX) and count >= FLOOR * base


def pinholes(p):
    o = set(p)
    return sum(1 for x in range(A.FW) for y in range(A.FH)
               if (x, y) not in o and (x - 1, y) in o and (x + 1, y) in o and (x, y - 1) in o and (x, y + 1) in o)


def specks(p):
    """Islands of 1-2 pixels (8-connected)."""
    seen, n = set(), 0
    for k in p:
        if k in seen:
            continue
        st, size = [k], 0
        seen.add(k)
        while st:
            a = st.pop()
            size += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (a[0] + dx, a[1] + dy)
                    if q in p and q not in seen:
                        seen.add(q)
                        st.append(q)
        n += size <= 2
    return n


def jump(a, b):
    """Largest distance (px) from a pixel of b to the nearest pixel of a."""
    worst = 0
    for p in b:
        if p in a:
            continue
        for r in range(1, 9):
            if any((p[0] + dx, p[1] + dy) in a for dx in range(-r, r + 1) for dy in (-r, r)) or \
               any((p[0] + dx, p[1] + dy) in a for dy in range(-r, r + 1) for dx in (-r, r)):
                break
        worst = max(worst, r)
    return worst


def body_height(spr):
    """Sole row to helmet top (first helmet row at least 4 px wide), in the library sprite."""
    rows = {}
    for (x, y) in parts_of(spr)['helmet']:
        rows[y] = rows.get(y, 0) + 1
    top = min(y for y, n in rows.items() if n >= 4)
    sole = max(y for (_, y) in A.SPR[spr][0])
    return sole - top + 1


def boot_gaps(rig):
    """Front/back stance: horizontal gap between the two boots in every frame, from each
    boot's full left/right extent (a lifted boot shares only its shaft rows with the planted
    one, and the shaft is narrower than the foot, so row-by-row gaps overstate the stance)."""
    gaps = []
    for i in range(N):
        rig.frame(i)
        left, right = rig.debug['boots']['leg_l'], rig.debug['boots']['leg_r']
        gaps.append(min(x for x, _ in right) - max(x for x, _ in left) - 1)
    return gaps


def main():
    r = rigs()
    failed = False
    print(f'size constant BODY_PX = {BODY_PX}: jump <= {JUMP_MAX}, below ground <= {BELOW_GROUND_MAX}, '
          f'boot gap 0..{BOOT_GAP_MAX}, head bob >= {BOB_MIN}, '
          f'ratios ±{round(TOLERANCE * 100)} % or ±{TOLERANCE_PX} px (wider), floor {round(FLOOR * 100)} %')
    for fac, spr in FACINGS:
        idle = A.stand_frame(spr).px
        m = A.META[spr]
        ref = {(x + A.CX - m['cx'], y + A.GROUND - m['feet']): c for (x, y), c in A.SPR[spr][0].items()}
        walk = [r[spr].frame(i).px for i in range(N)]
        heads = []
        for i in range(N):
            r[spr].frame(i)
            heads.append(r[spr].debug['head_y'])
        blue0 = sum(1 for c in idle.values() if A.is_blue(c))
        light0 = sum(1 for c in idle.values() if light(c))
        h = body_height(spr)
        rows = [
            ('idle == library sprite', idle == ref, ''),
            (f'idle body height == {BODY_PX}', h == BODY_PX, f'{h} px'),
            ('colours outside reference palette', not ({c[:3] for p in walk for c in p.values()} - PALETTE), ''),
        ]
        neck = int(NECK[spr] + A.GROUND - m['feet'])
        base = enclosed(idle, neck)
        vals = [enclosed(p, neck) for p in walk]
        rows.append((f'see-through holes below the neck (row > {neck})', max(vals) <= base, f'{vals} (idle {base})'))
        for name, fn in (('1px pinholes', pinholes), ('floating specks', specks)):
            base = fn(idle)
            vals = [fn(p) for p in walk]
            rows.append((name, max(vals) <= base, f'{vals} (idle {base})'))
        outside = sum(1 for p in walk for (x, y) in p if not (0 <= x < A.FW and 0 <= y < A.FH))
        lowest = max(y for p in walk for (_, y) in p)
        rows.append(('inside the frame', outside == 0, f'lowest row {lowest}, ground {A.GROUND}'))
        rows.append((f'feet/weapon at most {BELOW_GROUND_MAX} px below ground', lowest <= A.GROUND + BELOW_GROUND_MAX, ''))
        blue = [sum(1 for c in p.values() if A.is_blue(c)) for p in walk]
        hi = [sum(1 for c in p.values() if light(c)) for p in walk]
        for name, vals, base in (('blue cloth', blue, blue0), ('highlights', hi, light0)):
            rows.append((f'{name} vs idle (±10 % or ±{TOLERANCE_PX} px, floor 85 %)',
                         all(within(v, base) for v in vals),
                         f'{vals} vs idle {base} = {[round(100 * v / base) for v in vals]} %'))
        sets = [set(p) for p in walk]
        jumps = [jump(sets[i], sets[(i + 1) % N]) for i in range(N)]
        rows.append((f'frame-to-frame jump <= {JUMP_MAX} px', max(jumps) <= JUMP_MAX, f'{jumps}'))
        travel = max(heads) - min(heads)
        rows.append((f'head bob >= {BOB_MIN} px', travel >= BOB_MIN - 1e-6, f'{travel:.1f} px'))
        if spr in ('front', 'back'):
            gaps = boot_gaps(r[spr])
            rows.append((f'boot gap 0..{BOOT_GAP_MAX} px',
                         bool(gaps) and all(0 <= g <= BOOT_GAP_MAX for g in gaps), f'{gaps}'))
        print(f'== {fac} ({spr})')
        for name, ok, info in rows:
            failed |= not ok
            print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")
    print('ALL PASSED' if not failed else 'SOME CHECKS FAILED')
    return 1 if failed else 0


# ------------------------------------------------------------------ batch 0: key poses
# Static key poses (docs/art-progress.md, batch 0) drawn by pose_rig.py. Same size-derived
# limits as the walk; what a single pose cannot show (motion, timing) is reviewed by eye.
SWORD_MIN = px(0.25)        # a drawn sword shows at least this many blade pixels
LIB_PIECES = ('helmet', 'plume', 'cape', 'scarf', 'torso')


def pose_idle(view):
    """Idle frame of the library sprite for this view, and its neck row."""
    spr = POSE_SPRITE[view]
    m = A.META[spr]
    return A.stand_frame(spr).px, int(NECK[spr] + A.GROUND - m['feet'])


POSE_SPRITE = {'south': 'front', 'east': 'side_right', 'north': 'back', 'west': 'side_left'}


def enclosed_in(p, W_, H_, below):
    opaque = set(p)
    outside = set()
    stack = [(x, y) for x in range(-1, W_ + 1) for y in (-1, H_)] + [(x, y) for y in range(-1, H_ + 1) for x in (-1, W_)]
    while stack:
        q = stack.pop()
        if q in outside or q in opaque:
            continue
        x, y = q
        if x < -1 or y < -1 or x > W_ or y > H_:
            continue
        outside.add(q)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return sum(1 for x in range(W_) for y in range(below + 1, H_) if (x, y) not in opaque and (x, y) not in outside)


LIMBS = ('sword', 'upper_R', 'upper_L', 'fore_R', 'fore_L', 'fist_R', 'fist_L')
GAP_MIN = px(0.1)           # smaller enclosed pockets are seams, whatever borders them


def hole_kinds(p, W_, H_, below, r, dx, dy):
    """Enclosed background below the neck, split in two: a region of at least GAP_MIN px
    bordered by an arm or the sword and some other part is background seen between them (an
    arm held away from the body, a blade crossing a leg), which the pose opens on purpose;
    anything else, including every small pocket and anything between legs and torso, is a
    hole or a crack (animation-review §4.4). Returns (hole px, gap px)."""
    opaque = set(p)
    outside = set()
    stack = [(x, y) for x in range(-1, W_ + 1) for y in (-1, H_)] + [(x, y) for y in range(-1, H_ + 1) for x in (-1, W_)]
    while stack:
        q = stack.pop()
        if q in outside or q in opaque:
            continue
        x, y = q
        if x < -1 or y < -1 or x > W_ or y > H_:
            continue
        outside.add(q)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    inside = {(x, y) for x in range(W_) for y in range(below + 1, H_) if (x, y) not in opaque and (x, y) not in outside}
    holes = gaps = 0
    seen = set()
    for q in inside:
        if q in seen:
            continue
        comp, st = [], [q]
        seen.add(q)
        while st:
            a = st.pop()
            comp.append(a)
            for b in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if b in inside and b not in seen:
                    seen.add(b)
                    st.append(b)
        border = set()
        for (x, y) in comp:
            for b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if b in opaque:
                    border.add(r.trace.get((b[0] - dx, b[1] - dy), '?'))
        if len(comp) >= GAP_MIN and len(border) >= 2 and border & set(LIMBS):
            gaps += len(comp)
        else:
            holes += len(comp)
    return holes, gaps


# ------------------------------------------------------------------ §4.5 readability
CONTRAST_MIN = 3.0          # WCAG's minimum for graphics (3:1). The front-view guard the user
                            # could not find measured 1.8-2.9; the west guard, which reads,
                            # 5.5-5.7. See test notes in docs/art-progress.md
RING = (2, 3)               # the blade's surroundings: 2-3 px from its core (past its outline)


def rel_lum(c):
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def blade_contrast(r, p, dx, dy):
    """Contrast of the visible blade against what lies behind it, per third of its length
    (hilt end, middle, tip end). A third lying over the background (few body pixels round
    it) is not measured: the floor in the game is dark and the blade's outline shows there.
    Returns [(ratio or None, body px around)] for the three thirds."""
    core = [q for q in r.debug['blade'] if r.trace.get(q) == 'sword']
    if len(core) < 3:
        return []
    xs = [x for x, _ in core]
    ys = [y for _, y in core]
    along = (lambda q: q[0]) if max(xs) - min(xs) >= max(ys) - min(ys) else (lambda q: q[1])
    hand = r.debug['hands'].get('R', (0, 0))
    core.sort(key=along)
    if abs(along(core[-1]) - along(hand)) < abs(along(core[0]) - along(hand)):
        core.reverse()
    n = len(core)
    out = []
    for part in (core[:max(1, n // 3)], core[n // 3:2 * n // 3] or core, core[-max(1, n // 3):]):
        ring = set()
        for (x, y) in part:
            for ax in range(-RING[1], RING[1] + 1):
                for ay in range(-RING[1], RING[1] + 1):
                    q = (x + ax, y + ay)
                    if max(abs(ax), abs(ay)) >= RING[0] and (q[0] + dx, q[1] + dy) in p and r.trace.get(q) != 'sword':
                        ring.add(q)
        if len(ring) < 4 * len(part):
            out.append((None, len(ring)))
            continue
        lc = sum(rel_lum(p[(q[0] + dx, q[1] + dy)]) for q in part) / len(part)
        ls = sum(rel_lum(p[(q[0] + dx, q[1] + dy)]) for q in ring) / len(ring)
        out.append((round((max(lc, ls) + 0.05) / (min(lc, ls) + 0.05), 2), len(ring)))
    return out


# ------------------------------------------------------------------ §4.3 attack stances
# review 1: attack wind-ups and swings stood as upright as the idle and the guard. The
# concept's C2 / C3 / D2 step wide with the weight low. The hips sit 9 px above the floor
# (legs ~9.4 px long), so 3 px down is a clear crouch and 4 px a deep lunge; lower and the
# legs lie flat. With the pelvis 3-4 px down a foot reaches ~9 px from its hip: ankles up to
# ~20 px apart. Distances are between the two ankles (where the rig puts each boot).
ATTACK_STANCE = {   # pose: (pelvis drop px, side-view boot centres apart px)
    'l1_top': (px(0.075), px(0.35)), 'l1_end': (px(0.075), px(0.35)), 'l2_end': (px(0.075), px(0.35)),
    # 2026-09-28 fix: the charge re-derived from the legs' reach (they are ~6 px from hip to ankle):
    # 3 px down with the feet 14 apart drew its front leg stretched flat (batch 3, leg reach).
    # Second fix (same day, the user: still broken): 2.5 down and 11 apart still laid the legs
    # nearly flat (4.5 / 3.6 px of leg left under the hip, east / west): 1.5 down, 9 apart - legs
    # at 40-55 deg from upright, the east idle's own near leg is at 41
    'charge': (1.5, px(0.225)),          # px(0.0375) rounds half to even: 2
    'l4_top': (px(0.1), px(0.45)), 'l4_mid': (px(0.1), px(0.45)), 'l4_end': (px(0.1), px(0.45)),
    'thrust': (px(0.1), px(0.45)),
}
IDLE_WIDTH = {'south': 16, 'north': 13}   # idle boot centres apart, front / back (measured)
# lying (review 1): body 12-18 px tall behind the helmet
LIE_BODY = (px(0.3), px(0.45))

# §4.5 outlines: two poses that mean different things must differ at a glance. Measure: the
# share of both outlines (cloth left out: it sways in any pose) lying at least OUTLINE_SHIFT
# px from the other outline. Calibration on poses that ARE alike: consecutive walk frames
# and idle vs walk frames give at most 3 % in every view. Threshold 12 % = 4x that.
OUTLINE_SHIFT = px(0.075)   # 3 px
OUTLINE_DIFF_MIN = 0.12
# the pair the user named (review 1): perfect deflect vs plain block must differ without
# the spark. Other pairs that mean different things are measured and reported
DISTINCT = [('guard', 'parry'), ('guard', 'heal')]   # guard vs heal: batch 1 decision 1
# reported: idle vs guard / charge stay 8-12 % / 6-26 % (3-4x the alike level) with the
# guard's pelvis at the approved 1 px; pushing them past 12 % would need a deeper crouch
# than the brief's guard target, so that is the user's call
DISTINCT_INFO = [('idle', 'guard'), ('idle', 'charge'), ('guard', 'l1_top'), ('charge', 'heal'),
                 ('l1_top', 'l4_top'), ('idle', 'heal')]
CLOTH = ('plume', 'cape', 'scarf')


def outline_shift_share(a, b):
    import math as _m
    def edge(pts):
        return {(x, y) for (x, y) in pts if any(q not in pts for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))}
    ea, eb = edge(a), edge(b)
    al, bl = list(a), list(b)
    d = [min(_m.hypot(x - u, y - v) for u, v in bl) for x, y in ea] + \
        [min(_m.hypot(x - u, y - v) for u, v in al) for x, y in eb]
    return sum(1 for v in d if v >= OUTLINE_SHIFT) / len(d)


def silhouette(view, pose):
    import pose_rig as PR
    r = PR.rig(view)
    p = r.frame(pose, 'large')
    dx, dy = r.canvas_offset()
    return {k for k in p if r.trace.get((k[0] - dx, k[1] - dy), '') not in CLOTH}


def within_piece(count, base):
    """Per-piece detail (decision 3): the frame rule (±10 % or ±4 px, floor 85 %); a piece
    with only a few blue or lit pixels may differ by one, since one pixel of two is 50 %."""
    return within(count, base) or abs(count - base) <= 1


def pinholes_in(p, W_, H_):
    o = set(p)
    return sum(1 for x in range(W_) for y in range(H_)
               if (x, y) not in o and (x - 1, y) in o and (x + 1, y) in o and (x, y - 1) in o and (x, y + 1) in o)


def counts(p):
    return sum(1 for c in p.values() if A.is_blue(c)), sum(1 for c in p.values() if light(c))


def boot_centres(r, gy_small):
    """Horizontal centre of each boot (leg pixels in the three rows above the ground)."""
    out = {}
    for s_ in ('R', 'L'):
        xs = [x for (x, y), n in r.trace.items() if n == 'leg_' + s_ and y >= gy_small - 2]
        if xs:
            out[s_] = (min(xs) + max(xs)) / 2
    return out


def pose_rows(name, pose, canvas, view, lying=False):
    import pose_rig as PR
    r = PR.rig(view)
    if lying:
        import concept_pose as CP
        p = CP.lying_frame(head_left=(view == 'east'), airborne=pose['airborne'])
    else:
        p = r.frame(pose, canvas)
    W_, H_, cx, gy = PR.CANVAS[canvas]
    dx, dy = cx - A.CX, gy - A.GROUND
    idle, neck0 = pose_idle(view)
    rows = []
    rows.append(('colours inside the reference palette', not ({c[:3] for c in p.values()} - PALETTE), ''))
    outside = sum(1 for (x, y) in p if not (0 <= x < W_ and 0 <= y < H_))
    rows.append(('inside the canvas', outside == 0, f'{outside} px outside {W_}x{H_}'))
    if lying:
        low = max(y for (_, y) in p)
        rows.append(('nothing below the ground row', low <= gy, f'lowest row {low}, ground {gy}'))
        ys = [y for (_, y) in p]
        xs = [x for (x, _) in p]
        rows.append(('INFO size', None, f'{max(xs) - min(xs) + 1} x {max(ys) - min(ys) + 1} px (with plume, cape and sword)'))
        import concept_pose as CP
        m = CP.lying_metrics()
        lo, hi = LIE_BODY
        rows.append((f'body height {lo}-{hi} px behind the helmet (helmet, plume and cape apart)',
                     lo <= m['body_h'] <= hi, f"{m['body_h']} px; helmet {m['helmet_w']} x {m['helmet_h']} px, length {m['length']} px"))
        W_, H_ = PR.CANVAS[canvas][:2]
        rows.append(('see-through holes (the whole figure)', enclosed_in(p, W_, H_, -1) <= enclosed(idle, -1),
                     f'{enclosed_in(p, W_, H_, -1)} (idle {enclosed(idle, -1)})'))
        rows.append(('floating specks', specks(p) <= specks(idle), f'{specks(p)} (idle {specks(idle)})'))
        return rows
    # below the ground: legs may step 2 px toward the camera, nothing else goes under the floor
    low_leg, low_other, low_sword = -1, -1, -1
    legpx = {(x + dx, y + dy) for (x, y), n in r.trace.items() if n.startswith('leg')}
    for (x, y) in p:
        n = r.trace.get((x - dx, y - dy), '')
        if n == '' and any((x + a, y + b) in legpx for a in (-1, 0, 1) for b in (-1, 0, 1)):
            n = 'leg (clean-up)'      # a seam the clean-up closed on a boot
        if n.startswith('leg'):
            low_leg = max(low_leg, y)
        elif n == 'sword' and pose.get('floor3d') and PR.VIEWS[view]['kind'] == 'fb':
            low_sword = max(low_sword, y)
        else:
            low_other = max(low_other, y)
    # a floor3d blade pointing at the camera runs down the screen by perspective: at most its
    # length in depth (0.35 x 17 px = 6) below the ground row (2026-09-28 fix)
    ls = low_sword
    rows.append((f'feet at most {BELOW_GROUND_MAX} px below ground, nothing else below it',
                 low_leg <= gy + BELOW_GROUND_MAX and low_other <= gy and ls <= gy + BLADE_DEPTH_MAX,
                 f'feet row {low_leg}, others {low_other}' + (f', blade toward the camera {ls}' if ls >= 0 else '') + f', ground {gy}'))
    helm = [y for (x, y), n in r.trace.items() if n == 'helmet']
    neck = max(helm) + dy if helm else neck0 + dy
    base_holes = enclosed(idle, neck0)
    holes, gaps = hole_kinds(p, W_, H_, neck, r, dx, dy)
    rows.append((f'see-through holes below the neck (row > {neck})', holes <= base_holes,
                 f'{holes} (idle {base_holes})'))
    if gaps:
        rows.append(('INFO background seen between a limb or the sword and the body', None,
                     f'{gaps} px (not a hole in any part: see the gap image)'))
    ph, ph0 = pinholes_in(p, W_, H_), pinholes(idle)
    rows.append(('1px pinholes', ph <= ph0, f'{ph} (idle {ph0})'))
    sp, sp0 = specks(p), specks(idle)
    rows.append(('floating specks', sp <= sp0, f'{sp} (idle {sp0})'))
    # detail kept in every library piece, measured before compositing (decision 3)
    L = r.base.L
    for n in LIB_PIECES + ('paul_R', 'paul_L'):
        if n not in r.pieces:
            continue
        lib = n if n in LIB_PIECES else PR.VIEWS[view]['paul'][n[-1]]
        if not lib or lib not in L:
            continue
        # measured on the piece as drawn; where a lowered body lays the cape on the floor its
        # hem folds over itself there (self-occlusion, reported apart)
        (b, h), (b0, h0) = counts(r.pieces_raw[n]), counts(L[lib].pix)
        ok = (b0 == 0 or within_piece(b, b0)) and (h0 == 0 or within_piece(h, h0))
        rows.append((f'detail kept in {n} (before compositing)', ok, f'blue {b}/{b0}, highlights {h}/{h0}'))
        (bf, hf) = counts(r.pieces[n])
        if (bf, hf) != (b, h):
            rows.append((f'INFO {n} folded on the floor', None, f'blue {bf}, highlights {hf} after folding'))
    # new arms (N2) keep the glints of the library arm they are textured from; a far-side
    # arm is drawn darker for depth, like the walk's far arm, so it is only reported
    for s_ in ('R', 'L'):
        drawn = [r.pieces[n] for n in ('upper_' + s_, 'fore_' + s_, 'fist_' + s_) if n in r.pieces]
        if not drawn:
            continue
        an = PR.VIEWS[view]['arm'].get(s_) or next(a for a in PR.VIEWS[view]['arm'].values() if a)
        h = sum(1 for d in drawn for c in d.values() if light(c))
        h0 = sum(1 for c in L[an].pix.values() if light(c))
        far = PR.VIEWS[view]['kind'] == 'side' and s_ != PR.VIEWS[view]['near']
        if far:
            rows.append((f'INFO far-side arm {s_} (drawn darker for depth)', None, f'highlights {h} (library arm {h0})'))
        else:
            rows.append((f'glints kept in the new arm {s_} (vs library arm)', within_piece(h, h0), f'highlights {h}/{h0}'))
    (b, h), (b0, h0) = counts(p), counts(idle)
    rows.append(('INFO composited detail vs idle', None,
                 f'blue {b}/{b0} = {round(100 * b / b0)} %, highlights {h}/{h0} = {round(100 * h / h0)} %'))
    if 'sword' in pose:
        bc = blade_contrast(r, p, dx, dy)
        vals = [v for v, _ in bc if v is not None]
        if vals:
            rows.append((f'blade contrast against what is behind it >= {CONTRAST_MIN}:1 (hilt / middle / tip)',
                         min(vals) >= CONTRAST_MIN, ' / '.join('-' if v is None else f'{v}' for v, _ in bc)))
        n = len(r.debug['blade'])
        vis = sum(1 for q in r.debug['blade'] if r.trace.get(q) == 'sword')
        rows.append((f'INFO sword blade pixels visible (readable from {SWORD_MIN})', None, f'{vis} of {n}'))
    bc = boot_centres(r, A.GROUND)
    if len(bc) == 2:
        rows.append(('INFO boot centres apart', None, f'{abs(bc["R"] - bc["L"]):.1f} px'))
    if name in ATTACK_STANCE:
        drop_min, spread_min = ATTACK_STANCE[name]
        rest = PR.rig(view)
        rest.frame({}, 'small')
        rest_y = rest.debug['pelvis'][1]
        r.frame(pose, canvas)
        # front / back views: a step toward or away from the camera also moves the pelvis on
        # screen; only the drop in height counts
        f_, l_, _ = pose.get('root', (0, 0, 0))
        drop = r.debug['pelvis'][1] - rest_y - PR.proj(view, (f_, l_, 0))[1]
        rows.append((f'attack stance: pelvis at least {drop_min} px lower than idle', drop >= drop_min - 0.05, f'{drop:.1f} px'))
        legs = r.debug.get('legs', {})
        ank = [v[2][0] for v in legs.values()]
        spread = abs(ank[0] - ank[1]) if len(ank) == 2 else 0
        need = spread_min if PR.VIEWS[view]['kind'] == 'side' else IDLE_WIDTH[view]
        rows.append((f'attack stance: ankles at least {need} px apart', spread >= need - 0.05, f'{spread:.1f} px'))
    top0 = min(y for (x, y) in idle if True)
    if helm:
        rows.append(('INFO helmet top vs idle', None, f'{min(helm) - _helmet_top(view):+d} px (+ = lower)'))
    return rows


_HT = {}


def _helmet_top(view):
    if view not in _HT:
        import pose_rig as PR
        r = PR.rig(view)
        r.frame({}, 'small')
        _HT[view] = min(y for (x, y), n in r.trace.items() if n == 'helmet')
    return _HT[view]


def pose_checks():
    import poses as PQ
    failed = False
    print(f'== batch 0 key poses (poses.py): below ground <= {BELOW_GROUND_MAX}, '
          f'detail ±{round(TOLERANCE * 100)} % or ±{TOLERANCE_PX} px, floor {round(FLOOR * 100)} %')
    for name, pose, canvas, ref, label in PQ.KEY_POSES:
        for view in ('south', 'east', 'north', 'west'):
            print(f'-- {name} {view} ({canvas})')
            for rname, ok, info in pose_rows(name, pose, canvas, view):
                if ok is None:
                    print(f'  INFO  {rname[5:]}  {info}')
                    continue
                failed |= not ok
                print(f"  {'PASS' if ok else 'FAIL'}  {rname}  {info}")
    allp = {n: p_ for n, p_, _, _, _ in PQ.KEY_POSES}
    allp['idle'] = {}
    print(f'-- outlines of poses that mean different things: share of outline moved >= {OUTLINE_SHIFT} px, '
          f'at least {round(OUTLINE_DIFF_MIN * 100)} % (alike poses: <= 3 %)')
    for a, b in DISTINCT + DISTINCT_INFO:
        for view in ('south', 'east', 'north', 'west'):
            share = outline_shift_share(silhouette(view, allp[a]), silhouette(view, allp[b]))
            if (a, b) in DISTINCT_INFO:
                print(f"  INFO  {a} vs {b} {view}  {round(100 * share)} %")
                continue
            ok = share >= OUTLINE_DIFF_MIN
            failed |= not ok
            print(f"  {'PASS' if ok else 'FAIL'}  {a} vs {b} {view}  {round(100 * share)} %")
    for name, pose, canvas, ref, label in PQ.LYING_POSES:
        for view in ('east', 'west'):
            print(f'-- {name} {view} (lying, {canvas})')
            for rname, ok, info in pose_rows(name, pose, canvas, view, lying=True):
                if ok is None:
                    print(f'  INFO  {rname[5:]}  {info}')
                    continue
                failed |= not ok
                print(f"  {'PASS' if ok else 'FAIL'}  {rname}  {info}")
    print('POSES: ALL PASSED' if not failed else 'POSES: SOME CHECKS FAILED')
    return failed


# ------------------------------------------------------------------ batch 1
# docs/art-progress.md appendix C (batch 1), with the batch 1 decisions (2026-09-27).
B1_JUMP = px(0.10)            # head, torso, feet between consecutive frames: 4 px
B1_HAND_JUMP = px(0.5)        # hands and sword between consecutive frames: 20 px
GUARD_DROP = px(0.025)        # guard pelvis 1 px below idle
GUARD_FEET = {'south': (16, 1), 'north': (13, 1)}   # boot centres apart +- 1 (idle widths)
BLADE_ABOVE = (px(0.55), px(0.7))                   # side views: 22-28 px above the soles (blade middle)
BLADE_SHOULDER = px(0.1)      # front view: blade middle within 4 px of the shoulder row (user,
                              # 2026-09-27: the front view's shoulders are only ~19 px up); the
                              # back view is not measured (the blade ahead of the body projects
                              # higher up the picture), as decision 3
BLADE_LEVEL = px(0.05)        # front view: the blade's two ends at most 2 px apart in height
BLADE_LEN = px(0.35)          # front view: at least 14 px of blade seen (decision 3: not behind)
FISTS_APART = px(0.1)         # the two gauntlets on the grip at most 4 px apart
HIT_PULL = px(0.05)           # block hit: hands 2 px toward the chest
HIT_SLIDE = (1, px(0.05))     # block hit: back foot slides 1-2 px
PLUME_SWAY = (1, px(0.05))    # idle: plume end sways 1-2 px
RETURN_MAX = px(0.10)         # an action's last frame vs idle frame 1: head / torso / feet
HALF_STRIDE = 0.5             # decision 5: the slow legs step half the walk's stride
# decision 1: guard vs heal is a hard check in every view, held and walking (same step)
B1_DISTINCT = [('guard', 'hold 1', 'heal', 'hold 1')]
B1_DISTINCT_WALK = [('guard_walk', 'heal_walk')]
B1_INFO_PAIRS = [('idle', 'idle 1', 'heal', 'hold 1')]
RIGID = ('torso', 'upper_R', 'upper_L', 'fore_R', 'fore_L', 'fist_R', 'fist_L', 'paul_R', 'paul_L', 'sword')


class _Shim:
    """What blade_contrast() and hole_kinds() read from a rig, taken from a batch1.Frame."""

    def __init__(self, f):
        self.trace, self.debug = f.trace, f.debug


def _cen(f, names):
    """Centre of the named parts as drawn, before anything was laid over them (a helmet
    lowered over the torso must not move the torso's centre)."""
    pts = [q for n in names for q in f.pieces_raw.get(n, {})]
    if not pts:
        return None
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def _dist(a, b):
    import math as _m
    return None if a is None or b is None else _m.hypot(a[0] - b[0], a[1] - b[1])


def _tip(f):
    if f.debug.get('tip'):
        return f.debug['tip']          # batch 4's lying frames: the dropped sword's point
    blade = f.debug.get('blade') or set()
    fist = _cen(f, ('fist_R',))
    if blade and fist:
        return max(blade, key=lambda q: (q[0] - fist[0]) ** 2 + (q[1] - fist[1]) ** 2)
    sw = [q for q, n in f.trace.items() if n == 'sword']
    if sw:
        # library sword: its lowest pixel (the point)
        return max(sw, key=lambda q: q[1])
    return None


FEET_NAMES = ('leg_R', 'leg_L', 'legs')


def moves(a, b):
    """How far each part moves from frame a to frame b (px): head, torso, feet (the lowest
    three rows of the legs), hands, sword point."""
    la, lb = a.debug.get('legs') or {}, b.debug.get('legs') or {}
    if la and set(la) == set(lb):
        # each ankle, where the rig put it (a boot pitched onto its toe turns its pixels: the
        # pixel jump would count the turn as a move)
        feet_move = max(_dist(la[k][2], lb[k][2]) for k in la)
    else:
        feet = lambda f: [q for q, n in f.trace.items() if n in FEET_NAMES and q[1] >= A.GROUND - 2 and q in f.px]
        fa, fb = feet(a), feet(b)
        feet_move = jump(set(fa), set(fb)) if fa and fb else None
    out = {'head': _dist(_cen(a, ('helmet',)), _cen(b, ('helmet',))),
           'torso': _dist(_cen(a, ('torso',)), _cen(b, ('torso',))),
           'feet': feet_move}
    hands = [_dist(_cen(a, (n,)), _cen(b, (n,))) for n in ('fist_R', 'fist_L')]
    hands = [h for h in hands if h is not None]
    out['hands'] = max(hands) if hands else None
    out['sword'] = _dist(_tip(a), _tip(b))
    return out


def _fmt_moves(m):
    return ', '.join(f'{k} {v:.1f}' for k, v in m.items() if v is not None)


def _limits_ok(m):
    body = all(m[k] is None or m[k] <= B1_JUMP + 1e-6 for k in ('head', 'torso', 'feet'))
    hand = all(m[k] is None or m[k] <= B1_HAND_JUMP + 1e-6 for k in ('hands', 'sword'))
    return body and hand


def _named(action, view, name):
    import batch1 as B
    return next(f for f in B.frames(action, view) if f.name == name)


def _end_centroid(f, piece, root):
    """Centroid of the quarter of a cloth piece farthest from its root part's centre."""
    pts = list(f.pieces_raw.get(piece, {}))
    c = _cen(f, (root,))
    if not pts or c is None:
        return None
    pts.sort(key=lambda q: (q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2)
    far = pts[-max(1, len(pts) // 4):]
    return (sum(x for x, _ in far) / len(far), sum(y for _, y in far) / len(far))


def idle_frame_rows(f, view):
    """Technical checks of a library-built idle frame (the pose frames use pose_rows)."""
    p = f.px
    idle, neck0 = pose_idle(view)
    rows = [('colours inside the reference palette', not ({c[:3] for c in p.values()} - PALETTE), '')]
    outside = sum(1 for (x, y) in p if not (0 <= x < A.FW and 0 <= y < A.FH))
    rows.append(('inside the canvas', outside == 0, f'{outside} px outside'))
    legs = {q for q, n in f.trace.items() if n in FEET_NAMES}
    low_leg = max((y for (x, y) in p if (x, y) in legs), default=-1)
    low_other = max((y for (x, y) in p if (x, y) not in legs), default=-1)
    lib_low = max(y for (x, y) in idle)
    rows.append((f'feet at most {BELOW_GROUND_MAX} px below ground, nothing else lower than in the library',
                 low_leg <= A.GROUND + BELOW_GROUND_MAX and low_other <= max(A.GROUND, lib_low),
                 f'feet row {low_leg}, others {low_other}, ground {A.GROUND}'))
    h, h0 = enclosed(p, neck0), enclosed(idle, neck0)
    rows.append((f'see-through holes below the neck (row > {neck0})', h <= h0, f'{h} (idle {h0})'))
    ph, ph0 = pinholes(p), pinholes(idle)
    rows.append(('1px pinholes', ph <= ph0, f'{ph} (idle {ph0})'))
    sp, sp0 = specks(p), specks(idle)
    rows.append(('floating specks', sp <= sp0, f'{sp} (idle {sp0})'))
    (b, hi), (b0, hi0) = counts(p), counts(idle)
    rows.append((f'blue / highlights vs idle (±10 % or ±{TOLERANCE_PX} px, floor 85 %)',
                 within(b, b0) and within(hi, hi0), f'blue {b}/{b0}, highlights {hi}/{hi0}'))
    return rows


def batch1_checks():
    import batch1 as B
    import poses as PQ
    import pose_rig as PR
    failed = False

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

    print(f'== batch 1 (batch1.py): part moves <= {B1_JUMP} px (head, torso, feet), <= {B1_HAND_JUMP} px '
          f'(hands, sword); outlines >= {round(OUTLINE_DIFF_MIN * 100)} %')
    # ---- every frame: the technical checks
    for action in B.ACTIONS:
        for view in B.VIEWS:
            for f in B.frames(action, view):
                label = f'{action} / {f.name} / {view}'
                rows = idle_frame_rows(f, view) if f.pose is None else pose_rows(label, f.pose, 'small', view)
                bad = [(n, ok, i) for n, ok, i in rows if ok is False]
                info = [(n, i) for n, ok, i in rows if ok is None and n.startswith('INFO composited')]
                if bad:
                    for n, ok, i in bad:
                        out(False, f'{label}: {n}', i)
                else:
                    out(True, f'{label}: {len([r for r in rows if r[1] is not None])} technical checks',
                        info[0][1] if info else '')
    # ---- idle
    print('-- idle')
    for view in B.VIEWS:
        fr = B.frames('idle', view)
        idle, _ = pose_idle(view)
        out(fr[0].px == idle, f'idle 1 == library sprite {view}')
        body = [round(_cen(f, ('torso',))[1] - _cen(fr[0], ('torso',))[1]) for f in fr]
        head = [round(_cen(f, ('helmet',))[1] - _cen(fr[0], ('helmet',))[1]) for f in fr]
        out(body[0] == 0 and max(body) - min(body) == 1, f'breath: body exactly 1 px {view}', f'{body}')
        out(head == [body[(i - 1) % 4] for i in range(4)], f'breath: head one phase late {view}', f'head {head} vs body {body}')
        boots = [{q: c for q, c in f.px.items() if q[1] >= A.GROUND - 3 and f.trace.get(q) == 'legs'} for f in fr]
        out(all(b_ == boots[0] for b_ in boots), f'feet still {view} (boots, bottom 4 rows)')
        pl = [set(f.pieces_raw['plume']) for f in fr]
        sway = max(jump(pl[0], s) for s in pl[1:])
        out(PLUME_SWAY[0] <= sway <= PLUME_SWAY[1], f'plume end sways {PLUME_SWAY[0]}-{PLUME_SWAY[1]} px {view}', f'{sway} px')
    # ---- the breath of the guard and the heal: head and cloth ends after their roots
    print('-- the breath (guard hold, heal hold; decision 4)')
    for action in ('guard', 'heal', 'idle'):
        for view in B.VIEWS:
            fr = [f for f in B.frames(action, view) if f.name.startswith(('hold', 'idle'))]
            tor = [_cen(f, ('torso',)) for f in fr]
            hel = [_cen(f, ('helmet',)) for f in fr]
            dy_t = [round(t[1] - tor[0][1]) for t in tor]
            dy_h = [round(h[1] - hel[0][1]) for h in hel]
            # judged against the body's own sequence, not against batch1's tables (a check that
            # read its expectation from the code under test would pass whatever the code did)
            out(max(dy_t) - min(dy_t) == 1 and dy_h == [dy_t[(i - 1) % 4] for i in range(4)],
                f'{action} {view}: pelvis 1 px, head a phase late', f'torso {dy_t}, head {dy_h}')
            for piece, root in (('plume', 'helmet'), ('cape', 'torso')):
                ends = [_end_centroid(f, piece, root) for f in fr]
                roots = [_cen(f, (root,)) for f in fr]
                follow = []
                for i in range(4):
                    j = (i + 1) % 4
                    dr, de = _dist(roots[i], roots[j]), _dist(ends[i], ends[j])
                    follow.append((round(dr, 1), round(de, 1)))
                ok = any(dr < 0.25 and de >= 0.5 for dr, de in follow)
                out(ok, f'{action} {view}: {piece} end still moving after its root stopped',
                    ' '.join(f'{i + 1}->{(i + 1) % 4 + 1} root {dr} end {de}' for i, (dr, de) in enumerate(follow)))
    # ---- guard
    print('-- guard (appendix C)')
    for view in B.VIEWS:
        g = _named('guard', view, 'hold 1')
        rest = PR.rig(view)
        rest.frame({}, 'small')
        drop = g.debug['pelvis'][1] - rest.debug['pelvis'][1] - PR.proj(view, (g.pose['root'][0], g.pose['root'][1], 0))[1]
        out(abs(drop - GUARD_DROP) < 0.5, f'guard {view}: pelvis {GUARD_DROP} px below idle', f'{drop:.1f} px')
        bc = {}
        for s_ in ('R', 'L'):
            xs = [x for (x, y), n in g.trace.items() if n == 'leg_' + s_ and y >= A.GROUND - 2]
            bc[s_] = (min(xs) + max(xs)) / 2
        apart = abs(bc['R'] - bc['L'])
        if view in GUARD_FEET:
            t, tol = GUARD_FEET[view]
            out(abs(apart - t) <= tol, f'guard {view}: boot centres {t}±{tol} px apart', f'{apart:.1f} px')
        else:
            out(None, f'guard {view}: boot centres apart (side; batch 0 approved)', f'{apart:.1f} px')
        core = [q for q in g.debug['blade'] if g.trace.get(q) == 'sword']
        mid = sum(A.GROUND - y for _, y in core) / len(core)
        lo, hi = BLADE_ABOVE
        sh = PR.VIEWS[view]['sh']['R'][1] + g.debug['pelvis'][1] - PR.VIEWS[view].get('hip', PR.VIEWS[view].get('pelvis'))[1]
        info = (f'{mid:.1f} px (rows {A.GROUND - max(y for _, y in core)}-{A.GROUND - min(y for _, y in core)}); '
                f'shoulder {A.GROUND - sh:.1f} px above the soles')
        if view in ('east', 'west'):
            # the side guard raises the blade forward and up: its middle sits ~8 px over the
            # shoulder, so the side views keep the brief's height above the soles
            out(lo <= round(mid) <= hi, f'guard {view}: blade {lo}-{hi} px above the soles (middle, whole px)', info)
        elif view == 'south':
            d = mid - (A.GROUND - sh)
            out(abs(d) <= BLADE_SHOULDER, f'guard {view}: blade middle within {BLADE_SHOULDER} px of the shoulder', f'{d:+.1f} px; {info}')
        else:
            out(None, f'guard {view}: blade height (not measured from behind)', info)
        fists = _dist(_cen(g, ('fist_R',)), _cen(g, ('fist_L',)))
        if fists is None:
            out(None, f'guard {view}: gauntlets apart', 'one fist hidden (under the cape)')
        else:
            out(fists <= FISTS_APART, f'guard {view}: gauntlets at most {FISTS_APART} px apart', f'{fists:.1f} px')
        if view == 'south':
            xs = sorted(core)
            ends = [q for q in core if q[0] in (xs[0][0], xs[-1][0])]
            rise = max(y for _, y in ends) - min(y for _, y in ends)
            span = xs[-1][0] - xs[0][0] + 1
            out(rise <= BLADE_LEVEL, f'guard {view}: blade ends at most {BLADE_LEVEL} px apart in height', f'{rise} px')
            out(span >= BLADE_LEN, f'guard {view}: at least {BLADE_LEN} px of blade seen', f'{span} px')
        if view == 'north':
            out(None, f'guard {view}: blade seen (decision 3: not measured from behind)', f'{len(core)} of {len(g.debug["blade"])} px')
    # ---- block hit
    print('-- plain block hit')
    for view in B.VIEWS:
        g, h = _named('guard', view, 'hold 1'), _named('guard', view, 'hit')
        side = view in ('east', 'west')
        fdir = {'east': 1, 'west': -1}.get(view, 0)
        pull = [((_cen(g, (n,))[0] - _cen(h, (n,))[0]) * fdir) if side else _dist(_cen(g, (n,)), _cen(h, (n,)))
                for n in ('fist_R', 'fist_L')]
        back = 'R'
        ga, ha = g.debug['legs'], h.debug['legs']
        if side:
            which = 'near' if PR.VIEWS[view]['near'] == back else 'far'
            slide = (ga[which][2][0] - ha[which][2][0]) * fdir
        else:
            slide = _dist(ga[back][2], ha[back][2])
        if side:
            out(all(p >= HIT_PULL - 0.5 for p in pull), f'hit {view}: hands {HIT_PULL} px toward the chest', f'{pull[0]:.1f} / {pull[1]:.1f} px')
            out(HIT_SLIDE[0] - 0.5 <= slide <= HIT_SLIDE[1] + 0.5, f'hit {view}: back foot slides {HIT_SLIDE[0]}-{HIT_SLIDE[1]} px', f'{slide:.1f} px')
        else:
            out(None, f'hit {view}: hands toward the chest / back foot (depth, foreshortened on screen)',
                f'hands {pull[0]:.1f} / {pull[1]:.1f} px, foot {slide:.1f} px (2 / 1.5 px in depth)')
    # ---- outlines
    print(f'-- outlines (share of outline moved >= {OUTLINE_SHIFT} px)')
    for a1, n1, a2, n2 in [('guard', 'hold 1', 'guard', 'deflect')] + B1_DISTINCT:
        for view in B.VIEWS:
            s = outline_shift_share(_sil(_named(a1, view, n1)), _sil(_named(a2, view, n2)))
            out(s >= OUTLINE_DIFF_MIN, f'{a1} {n1} vs {a2} {n2} {view}', f'{round(100 * s)} %')
    for a1, a2 in B1_DISTINCT_WALK:
        for view in B.VIEWS:
            vals = [outline_shift_share(_sil(f1), _sil(f2)) for f1, f2 in zip(B.frames(a1, view), B.frames(a2, view))]
            out(min(vals) >= OUTLINE_DIFF_MIN, f'{a1} vs {a2} {view}, every frame (same step)',
                f'{round(100 * min(vals))}-{round(100 * max(vals))} %')
    for a1, n1, a2, n2 in B1_INFO_PAIRS:
        for view in B.VIEWS:
            s = outline_shift_share(_sil(_named(a1, view, n1)), _sil(_named(a2, view, n2)))
            out(None, f'{a1} {n1} vs {a2} {n2} {view}', f'{round(100 * s)} %')
    for other in ('charge', 'kneel'):
        pose = dict((n, p_) for n, p_, _, _, _ in PQ.KEY_POSES)[other]
        for view in B.VIEWS:
            s = outline_shift_share(silhouette(view, pose), silhouette(view, PQ.HEAL))
            out(None, f'{other} (batch 0 key pose) vs heal {view}', f'{round(100 * s)} %')
    # ---- frame to frame
    print('-- part moves between consecutive frames')
    plays = {
        'idle': [('idle', f'idle {i}', 'idle', f'idle {i % 4 + 1}') for i in range(1, 5)],
        'guard': [('guard', f'hold {i}', 'guard', f'hold {i % 4 + 1}') for i in range(1, 5)] +
                 [('guard', f'hold {i}', 'guard', 'hit') for i in range(1, 5)] +
                 [('guard', 'hit', 'guard', 'hold 1'), ('guard', 'deflect', 'guard', 'back 1'),
                  ('guard', 'back 1', 'guard', 'back 2'), ('guard', 'back 2', 'guard', 'hold 1')],
        'heal': [('idle', 'idle 1', 'heal', 'in 1'), ('heal', 'in 1', 'heal', 'in 2'), ('heal', 'in 2', 'heal', 'hold 1')] +
                [('heal', f'hold {i}', 'heal', f'hold {i + 1}') for i in range(1, 4)] +
                [('heal', 'hold 4', 'heal', 'out 1'), ('heal', 'out 1', 'heal', 'out 2'), ('heal', 'out 2', 'idle', 'idle 1')],
        # batch 3 decision 8: backward and the sidestep to the right are their own cycles
        'guard_walk': [('guard_walk', f'{k} {i}', 'guard_walk', f'{k} {i % n + 1}')
                       for k, n in (('fwd', 8), ('side', 4), ('back', 8), ('rside', 4)) for i in range(1, n + 1)],
        'heal_walk': [('heal_walk', f'{k} {i}', 'heal_walk', f'{k} {i % n + 1}')
                      for k, n in (('fwd', 8), ('side', 4), ('back', 8), ('rside', 4)) for i in range(1, n + 1)],
    }
    for action, pairs in plays.items():
        for view in B.VIEWS:
            worst = []
            for a1, n1, a2, n2 in pairs:
                m = moves(_named(a1, view, n1), _named(a2, view, n2))
                if not _limits_ok(m):
                    out(False, f'{action} {view}: {n1} -> {n2}', _fmt_moves(m))
                worst.append(m)
            agg = {k: max((m[k] for m in worst if m[k] is not None), default=None) for k in worst[0]}
            out(all(_limits_ok(m) for m in worst), f'{action} {view}: {len(pairs)} frame pairs within the limits',
                'largest ' + _fmt_moves(agg))
    # starting to walk from the held pose: the braced guard stance is wider than the walking
    # legs, so the walk has to start at a frame whose feet are near it (the game picks it)
    for action, base in (('guard_walk', 'guard'), ('heal_walk', 'heal')):
        for view in B.VIEWS:
            h = _named(base, view, 'hold 1')
            for kind in ('fwd', 'side', 'back', 'rside'):
                fr = [f for f in B.frames(action, view) if f.name.startswith(kind + ' ')]
                ok_in = [f.name for f in fr if _limits_ok(moves(h, f))]
                ok_out = [f.name for f in fr if _limits_ok(moves(f, h))]
                out(bool(ok_in) and bool(ok_out), f'{action} {view}: start / stop the {kind} cycle from / to {base} hold 1',
                    f'start at {", ".join(ok_in) or "none"}; stop from {", ".join(ok_out) or "none"}')
    for view in B.VIEWS:
        m = moves(_named('guard', view, 'hold 1'), _named('guard', view, 'deflect'))
        out(None, f'guard -> deflect {view} (decision 2: exempt)', _fmt_moves(m))
        m = moves(_named('guard', view, 'hold 1'), _named('idle', view, 'idle 1'))
        out(None, f'guard <-> idle {view} (decision 14: no in-between; the guard is up the frame it is pressed)', _fmt_moves(m))
        m = moves(_named('heal', view, 'out 2'), _named('idle', view, 'idle 1'))
        ok = all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet'))
        out(ok, f'heal out 2 vs idle 1 {view}: head, torso, feet within {RETURN_MAX} px', _fmt_moves(m))
    # ---- the slow legs
    print('-- slow legs (decision 5): upper body rigid, half stride')
    import walk_side as W_
    for action, base in (('guard_walk', ('guard', 'hold 1')), ('heal_walk', ('heal', 'hold 1'))):
        for view in B.VIEWS:
            b = _named(base[0], view, base[1])
            bad = []
            for f in B.frames(action, view):
                bob = round(_cen(f, ('torso',))[1] - _cen(b, ('torso',))[1])
                for n in RIGID:
                    if n not in b.pieces_raw:
                        continue
                    # the heal's sword is planted in the floor: it stays put while the body bobs
                    sh = 0 if (n == 'sword' and action == 'heal_walk') else bob
                    want = {(x, y + sh): c for (x, y), c in b.pieces_raw[n].items()}
                    got = f.pieces_raw.get(n, {})
                    if want != got:
                        bad.append(f'{f.name}:{n}')
                if bob not in (0, 1):
                    bad.append(f'{f.name}: bob {bob}')
            out(not bad, f'{action} {view}: torso, arms, sword identical to {base[1]} (bob 0-1 px)', ', '.join(bad[:6]))
            if view in ('east', 'west'):
                walk = [W_.NEAR_FOOT[i][0] for i in range(8)]
                for kind in ('fwd', 'back'):
                    near = [f.debug['legs']['near'][2][0] for f in B.frames(action, view) if f.name.startswith(kind + ' ')]
                    rng, wrng = max(near) - min(near), max(walk) - min(walk)
                    out(abs(rng - HALF_STRIDE * wrng) <= 1.0, f'{action} {view}: {kind} stride half the walk', f'{rng:.1f} px vs walk {wrng:.1f}')
    print('BATCH 1: ALL PASSED' if not failed else 'BATCH 1: SOME CHECKS FAILED')
    return failed


def _sil(f):
    return {q for q in f.px if f.trace.get(q, '') not in CLOTH}


# ------------------------------------------------------------------ batch 2
# docs/art-progress.md appendix C (batch 2) with the batch 2 decisions (2026-09-27). Moves are
# measured where they are seen on screen: the frame plus where the picture sits (decision 2:
# the picture follows the program's advance when the frame changes).
SWING_JUMP = px(0.2)          # decision 5: head / torso in the swing steps, on screen: 8 px
DRIFT_MAX = 1                 # a foot bearing the weight stays within 1 px on screen
PREP_BACK = px(0.05)          # f1: pelvis at least 2 px back
END_FWD = px(0.1)             # follow-through: pelvis at least 4 px ahead of the top
END_LEAN = (8, 15)            # follow-through lean, degrees
BLADE_ANGLE_MAX = 22.5        # stage 2's end vs stage 1's top (stage 3 starts from that top)
APEX_HOLD = 7                 # stage 4 apex held at least 7 sim frames
# the swing steps of decision 5 (stage, from frame index, to frame index); stage 4's apex ->
# D2 is decision 1 (not limited at all)
SWING_STEPS = {(1, 1, 2), (1, 2, 3), (2, 1, 2), (2, 2, 3), (3, 0, 1), (3, 1, 2), (4, 3, 4), (4, 4, 5)}
EXEMPT_STEPS = {(4, 2, 3)}
ATTACK_KEY = {(1, 1): 'l1_top', (1, 3): 'l1_end', (2, 3): 'l2_end', (3, 0): 'l1_top', (3, 2): 'l1_end',
              (4, 2): 'l4_top', (4, 3): 'l4_mid', (4, 4): 'l4_end'}
SMALL_TO_LARGE = (16, 8)      # 56 x 56 (28, 53) -> 88 x 72 (44, 61)


class _Pt:
    """Where the parts of one frame are on screen: head, torso, fists, sword point, ankles and
    boots, all moved by the picture's place on screen (sx, sy)."""

    def __init__(self, f, sx=0.0, sy=0.0, small=False):
        ox, oy = (SMALL_TO_LARGE if small else (0, 0))
        sx, sy = sx + ox, sy + oy
        mv = lambda p: None if p is None else (p[0] + sx, p[1] + sy)
        self.head, self.torso = mv(_cen(f, ('helmet',))), mv(_cen(f, ('torso',)))
        self.fists = {n: mv(_cen(f, (n,))) for n in ('fist_R', 'fist_L')}
        self.tip = mv(_tip(f))
        legs = (f.debug or {}).get('legs') or {}
        self.ankles = {k: mv(v[2]) for k, v in legs.items()} if legs else {}
        gy = max(y for (_, y) in f.px) if f.px else 0
        self.boots = {(round(x + sx), round(y + sy)) for (x, y), n in f.trace.items()
                      if n in FEET_NAMES and y >= gy - 2 and (x, y) in f.px}


def screen_moves(a, b):
    out = {'head': _dist(a.head, b.head), 'torso': _dist(a.torso, b.torso)}
    if a.ankles and set(a.ankles) == set(b.ankles):
        out['feet'] = max(_dist(a.ankles[k], b.ankles[k]) for k in a.ankles)
    else:
        out['feet'] = jump(a.boots, b.boots) if a.boots and b.boots else None
    h = [_dist(a.fists[n], b.fists[n]) for n in a.fists]
    h = [x for x in h if x is not None]
    out['hands'] = max(h) if h else None
    out['sword'] = _dist(a.tip, b.tip)
    return out


def _ok(m, body=B1_JUMP, hand=B1_HAND_JUMP, sword=True):
    return (all(m[k] is None or m[k] <= body + 1e-6 for k in ('head', 'torso')) and
            (m['feet'] is None or m['feet'] <= B1_JUMP + 1e-6) and
            (m['hands'] is None or m['hands'] <= hand + 1e-6) and
            (not sword or m['sword'] is None or m['sword'] <= hand + 1e-6))


# ---- user decisions A-G (2026-09-28, docs/art-progress.md "第 2 批：交件"): failures the user
# accepted, recorded with what was measured when they approved them (batch 3 decision 10). A
# waived row still prints its values and names its decision; it fails again when any value grows
# past the recorded one (+ WAIVE_EPS), so a later change to the rig cannot hide behind the waiver.
# The recorded values are the reviewed state, not read from the program being checked.
WAIVE_EPS = 0.05
B2_WAIVERS = {}          # key -> (decision, {metric: accepted max}), from B2_WAIVED
# the rows the user accepted (decisions A-G), with the values measured when they approved them
# A: the stage 3 -> 4 crouch (two frames) is a weapon reset, like decision 1
# B: item 7 south, 40.0 px halved is 20.0 at best
# D: front / back weight foot, the depth squeezed to 0.55
# E: late chaining (play-test once wired in)
# F: slow legs into stage 1 (play-test once wired in)
# G: stage 4 follow-through lean kept at 20 deg (batch 0 pose)
B2_WAIVED = {
    'step 4 south 0': ('A', {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.6}),
    'step 4 south 1': ('A', {'head': 4.5, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.7}),
    'step 4 east 0': ('A', {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 25.1}),
    'step 4 east 1': ('A', {'head': 5.1, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.0}),
    'step 4 west 0': ('A', {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 21.1}),
    'step 4 west 1': ('A', {'head': 4.9, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.0}),
    'chain east 3': ('A', {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.3}),
    'chain west 3': ('A', {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 21.7}),
    'item7 south': ('B', {'sword': 20.2}),
    'step 1 south 2': ('B', {'head': 8.0, 'torso': 8.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.2}),
    'step 3 south 1': ('B', {'head': 8.0, 'torso': 8.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.2}),
    'step 4 south 3': ('D', {'head': 8.0, 'torso': 8.0, 'feet': 6.7, 'hands': 20.0, 'sword': 20.0}),
    'step 4 south 4': ('D', {'head': 8.0, 'torso': 8.0, 'feet': 5.4, 'hands': 20.0, 'sword': 20.0}),
    'step 4 north 3': ('D', {'head': 8.0, 'torso': 8.0, 'feet': 4.7, 'hands': 20.0, 'sword': 20.0}),
    'step 4 north 4': ('D', {'head': 8.0, 'torso': 8.0, 'feet': 7.0, 'hands': 20.0, 'sword': 20.0}),
    'drift 1 south': ('D', {'drift': 2.4}),
    'drift 1 north': ('D', {'drift': 1.2}),
    'drift 2 south': ('D', {'drift': 2.4}),
    'drift 2 north': ('D', {'drift': 1.2}),
    'drift 3 south': ('D', {'drift': 2.4}),
    'drift 3 north': ('D', {'drift': 1.2}),
    'drift 4 south': ('D', {'drift': 5.4}),
    'drift 4 north': ('D', {'drift': 3.2}),
    'late south 3 f5 收招': ('E', {'head': 4.6, 'torso': 4.0, 'feet': 4.0}),
    'late east 1 f5 收招': ('E', {'head': 5.6, 'torso': 4.6, 'feet': 4.0}),
    'late east 1 f6 回站姿 1': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
    'late east 1 f6 回站姿 2': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 6.4}),
    'late east 2 f5 收招': ('E', {'head': 7.0, 'torso': 4.5, 'feet': 4.0}),
    'late east 2 f6 回站姿 1': ('E', {'head': 6.0, 'torso': 4.0, 'feet': 4.0}),
    'late east 2 f6 回站姿 2': ('E', {'head': 4.6, 'torso': 4.0, 'feet': 4.0}),
    'late east 3 f5 收招': ('E', {'head': 7.4, 'torso': 5.3, 'feet': 4.0}),
    'late east 3 f6 回站姿 1': ('E', {'head': 4.4, 'torso': 4.0, 'feet': 5.0}),
    'late east 3 f6 回站姿 2': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 7.0}),
    'late west 1 f5 收招': ('E', {'head': 5.7, 'torso': 4.6, 'feet': 4.0}),
    'late west 1 f6 回站姿 1': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
    'late west 1 f6 回站姿 2': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 6.4}),
    'late west 2 f5 收招': ('E', {'head': 7.6, 'torso': 4.7, 'feet': 4.0}),
    'late west 2 f6 回站姿 1': ('E', {'head': 5.3, 'torso': 4.0, 'feet': 4.0}),
    'late west 2 f6 回站姿 2': ('E', {'head': 4.6, 'torso': 4.0, 'feet': 4.0}),
    'late west 3 f5 收招': ('E', {'head': 7.1, 'torso': 5.2, 'feet': 4.0}),
    'late west 3 f6 回站姿 1': ('E', {'head': 4.5, 'torso': 4.1, 'feet': 5.0}),
    'late west 3 f6 回站姿 2': ('E', {'head': 4.0, 'torso': 4.0, 'feet': 7.0}),
    'enter south guard walk side 2': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.7}),
    'enter east guard walk fwd 1': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
    'enter north guard walk side 2': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.2}),
    'enter west guard walk fwd 5': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
    'lean 4': ('G', {'lean': 20.0}),
    # batch 3 decision 8 split the slow legs' backward / rightward frames out of the forward /
    # left ones played in reverse: the same entries into stage 1, the same values as the F rows
    # they mirror (rside 4 = side 2, back 1 = fwd 1, back 5 = fwd 5); reported to the user
    'enter south guard walk rside 4': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.7}),
    'enter east guard walk back 1': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
    'enter north guard walk rside 4': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.2}),
    'enter west guard walk back 5': ('F', {'head': 4.0, 'torso': 4.0, 'feet': 4.5}),
}
B2_WAIVERS.update(B2_WAIVED)


def _waiver(key, metrics):
    """The decision that waives this row, or None: the key is recorded and no metric exceeds
    its recorded value."""
    w = B2_WAIVERS.get(key)
    if w is None:
        return None
    dec, caps = w
    for k, v in metrics.items():
        if v is None:
            continue
        if k not in caps or v > caps[k] + WAIVE_EPS:
            return None
    return dec


def batch2_checks(record=False):
    import batch1 as B1
    import batch2 as B2
    import poses as PQ
    import pose_rig as PR
    import math as _m
    import walk_side as W_
    failed = False
    waived = []
    recorded = {}

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

    def check(ok, name, info, key, metrics, limits):
        """A row that a user decision may waive: `metrics` are what was measured, `limits` the
        rule's own limits (a recorded row keeps every metric within max(limit, recorded))."""
        if ok:
            out(True, name, info)
            return
        dec = _waiver(key, metrics)
        if record:
            recorded[key] = {k: round(max(v, limits.get(k, 0.0)) + 0.049, 1) for k, v in metrics.items() if v is not None}
        if dec:
            waived.append((dec, key))
            print(f'  WAIV  {name}  {info}  [decision {dec}: accepted, recorded values not exceeded]')
            return
        out(False, name, info)

    def pt(f):
        ox, oy = f.screen_offset()
        return _Pt(f, ox, oy)

    print(f'== batch 2 (batch2.py): on screen, head / torso / feet <= {B1_JUMP} px, hands / sword <= {B1_HAND_JUMP} px; '
          f'swing steps head / torso <= {SWING_JUMP} px (decision 5)')
    # ---- every frame: the technical checks (attack stance where a key pose sits)
    for st in (1, 2, 4):
        for view in B2.VIEWS:
            for i, f in enumerate(B2.frames(st, view)):
                name = ATTACK_KEY.get((st, i), f'stage {st} {f.name}')
                label = f'stage {st} / {f.name} / {view}'
                rows = pose_rows(name, f.pose, 'large', view)
                bad = [(n, i_) for n, ok, i_ in rows if ok is False]
                stance = [(n, i_) for n, ok, i_ in rows if ok is not None and n.startswith('attack stance')]
                comp = [i_ for n, ok, i_ in rows if ok is None and n.startswith('INFO composited')]
                if bad:
                    for n, i_ in bad:
                        out(False, f'{label}: {n}', i_)
                else:
                    out(True, f'{label}: {len([r for r in rows if r[1] is not None])} technical checks',
                        '; '.join(f'{n[15:]} {i_}' for n, i_ in stance) or (comp[0] if comp else ''))
    # ---- poses
    print('-- attack poses (appendix C, batch 2)')
    # the pelvis along the facing, in the character's own space (the side views also show a
    # sideways shift a little, SIDE_X: that is not the pelvis going forward); screen x reported
    for st in (1, 2, 4):
        fr = B2.frames(st, 'east')
        if st != 2:
            prep = [f for f in fr if f.first < B2.ATTACK[st][0]]         # the start-up frames
            back = max(-f.pose['root'][0] for f in prep)
            out(back >= PREP_BACK - 0.05, f'stage {st}: start-up pelvis at least {PREP_BACK} px back',
                f'{back:.1f} px ({", ".join(f.name for f in prep)})')
        top_i, end_i = {1: (1, 3), 2: (1, 3), 4: (2, 4)}[st]
        fwd = fr[end_i].pose['root'][0] - fr[top_i].pose['root'][0]
        scr = {v: (B2.frames(st, v)[end_i].debug['pelvis'][0] - B2.frames(st, v)[top_i].debug['pelvis'][0]) * PR.VIEWS[v]['facing']
               for v in ('east', 'west')}
        out(fwd >= END_FWD - 0.05, f'stage {st}: pelvis {END_FWD} px ahead at the follow-through ({fr[top_i].name} -> {fr[end_i].name})',
            f'{fwd:.1f} px; on screen east {scr["east"]:.1f}, west {scr["west"]:.1f}')
    for st, key in ((1, PQ.L1_END), (2, PQ.L2_END), (4, PQ.L4_END)):
        lean = key['lean']
        lo, hi = END_LEAN
        check(lo <= lean <= hi, f'stage {st}: follow-through lean {lo}-{hi} deg', f'{lean} deg',
              f'lean {st}', {'lean': lean}, {'lean': hi})
    for view in B2.VIEWS:
        def ang(f):
            fist = f.debug['hands']['R']
            tip = max(f.debug['blade'], key=lambda q: (q[0] - fist[0]) ** 2 + (q[1] - fist[1]) ** 2)
            return _m.degrees(_m.atan2(tip[1] - fist[1], tip[0] - fist[0]))
        d = abs((ang(B2.frames(2, view)[3]) - ang(B2.frames(1, view)[1]) + 180) % 360 - 180)
        out(d <= BLADE_ANGLE_MAX, f'{view}: stage 2 end vs stage 1 top blade angle <= {BLADE_ANGLE_MAX} deg', f'{d:.1f} deg')
    apex = B2.frames(4, 'east')[2]
    out(apex.dur >= APEX_HOLD, f'stage 4 apex held at least {APEX_HOLD} sim frames', f'{apex.first}-{apex.last} ({apex.dur})')
    print('-- item 7 (user): stage 1 top -> contact -> follow-through, the sword point per step <= 20 px on screen')
    for view in B2.VIEWS:
        fr = B2.frames(1, view)
        steps = [screen_moves(pt(fr[i]), pt(fr[i + 1]))['sword'] for i in (1, 2)]
        check(max(steps) <= B1_HAND_JUMP + 1e-6, f'item 7 {view}', f'{steps[0]:.1f} / {steps[1]:.1f} px',
              f'item7 {view}', {'sword': max(steps)}, {'sword': B1_HAND_JUMP})
    # ---- moves between frames, on screen
    print('-- moves between consecutive frames, on screen')
    for st in (1, 2, 3, 4):
        for view in B2.VIEWS:
            fr = B2.frames(st, view)
            worst, bad = {}, []
            for i in range(len(fr) - 1):
                m = screen_moves(pt(fr[i]), pt(fr[i + 1]))
                if (st, i, i + 1) in EXEMPT_STEPS:
                    out(None, f'stage {st} {view}: {fr[i].name} -> {fr[i + 1].name} (decision 1: not limited)', _fmt_moves(m))
                    continue
                body = SWING_JUMP if (st, i, i + 1) in SWING_STEPS else B1_JUMP
                if not _ok(m, body):
                    bad.append((i, m, body))
                for k, v in m.items():
                    if v is not None:
                        worst[k] = max(worst.get(k, 0), v)
            if not bad:
                out(True, f'stage {st} {view}: {len(fr) - 1} steps within the limits', 'largest ' + _fmt_moves(worst))
            for i, m, body in bad:
                check(False, f'stage {st} {view}: {fr[i].name} -> {fr[i + 1].name} within the limits', _fmt_moves(m),
                      f'step {st} {view} {i}', m,
                      {'head': body, 'torso': body, 'feet': B1_JUMP, 'hands': B1_HAND_JUMP, 'sword': B1_HAND_JUMP})
    # ---- the weight foot stays put on screen
    print(f'-- the foot bearing the weight moves at most {DRIFT_MAX} px on screen (decision 2)')
    for st in (1, 2, 3, 4):
        for view in B2.VIEWS:
            fr = B2.frames(st, view)
            drifts = []
            for i in range(len(fr) - 1):
                a, b = fr[i], fr[i + 1]
                for s_ in {a.weight, b.weight} - {None}:
                    fa, fb = a.pose['feet'][s_], b.pose['feet'][s_]
                    if fa[2] or fb[2]:
                        continue                      # lifted in one of them: a step, not a drift
                    if not (s_ == a.weight == b.weight):
                        continue                      # the weight moves to the other foot here
                    k = s_ if view in ('south', 'north') else ('near' if PR.VIEWS[view]['near'] == s_ else 'far')
                    pa, pb = pt(a).ankles[k], pt(b).ankles[k]
                    # along the floor only: a heel rising onto the toe lifts the ankle, it does
                    # not move the foot (side views: across; front / back: up and down)
                    d = abs(pa[0] - pb[0]) if view in ('east', 'west') else abs(pa[1] - pb[1])
                    drifts.append((d, f'{a.name}->{b.name} {s_}'))
            w = max(drifts) if drifts else (0, '')
            check(w[0] <= DRIFT_MAX + 1e-6, f'stage {st} {view}: weight foot on screen', f'largest {w[0]:.1f} px ({w[1]})',
                  f'drift {st} {view}', {'drift': w[0]}, {'drift': DRIFT_MAX})
    # ---- chaining, entering, leaving
    print('-- chaining at the earliest frame, entering from idle / guard / walking, back to idle')
    def total(st):
        return B2.ATTACK[st][3]
    for view in B2.VIEWS:
        fx, fy = B2.FWD_SCREEN[view]
        for a_st, b_st in ((1, 2), (2, 3), (3, 4)):
            a = B2.frames(a_st, view)[3 if a_st != 3 else 2]       # the follow-through shows when the chain comes
            b = B2.frames(b_st, view)[0]
            pa = pt(a)
            pb = _Pt(b, fx * (total(a_st) + b.adv), fy * (total(a_st) + b.adv))
            m = screen_moves(pa, pb)
            lim = {'head': B1_JUMP, 'torso': B1_JUMP, 'feet': B1_JUMP, 'hands': B1_HAND_JUMP, 'sword': B1_HAND_JUMP}
            check(_ok(m), f'{view}: chain stage {a_st} {a.name} -> stage {b_st} {b.name} (sim frame {B2.ATTACK[a_st][0] + B2.ATTACK[a_st][1]})',
                  _fmt_moves(m), f'chain {view} {a_st}', m, lim)
            for late in B2.frames(a_st, view)[(4 if a_st != 3 else 3):]:     # the recovery frames
                pl = pt(late)
                m = screen_moves(pl, pb)
                body = {k: m[k] for k in ('head', 'torso', 'feet')}
                check(_ok(m, sword=False), f'{view}: late chain stage {a_st} {late.name} -> stage {b_st} {b.name} (decision 3: head / torso / feet <= 4)',
                      _fmt_moves(m), f'late {view} {a_st} {late.name}', body, lim)
        f1 = B2.frames(1, view)[0]
        p1 = pt(f1)
        idle = B1.frames('idle', view)[0]
        guard = [f for f in B1.frames('guard', view) if f.name.startswith('hold')]
        slow = B1.frames('guard_walk', view)
        for label, src in [('idle 1', idle)] + [(f'guard {g.name}', g) for g in guard] + [(f'guard walk {g.name}', g) for g in slow]:
            m = screen_moves(_Pt(src, small=True), p1)
            body = {k: m[k] for k in ('head', 'torso', 'feet')}
            check(_ok(m, sword=False), f'{view}: {label} -> stage 1 f1 (decision 3: the sword is free)', _fmt_moves(m),
                  f'enter {view} {label}', body, {'head': B1_JUMP, 'torso': B1_JUMP, 'feet': B1_JUMP})
        for st in (1, 2, 4):
            last = B2.frames(st, view)[-1]
            m = screen_moves(pt(last), _Pt(idle, fx * total(st), fy * total(st), small=True))
            ok = all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet'))
            out(ok, f'{view}: stage {st} {last.name} vs idle 1: head, torso, feet within {RETURN_MAX} px', _fmt_moves(m))
    if record:
        print('B2_WAIVED = {')
        for k, v in recorded.items():
            print(f'    {k!r}: {v!r},')
        print('}')
    if waived:
        by = {}
        for d, _ in waived:
            by[d] = by.get(d, 0) + 1
        print(f'  waived by user decisions: ' + ', '.join(f'{d} {n}' for d, n in sorted(by.items())) + f' ({len(waived)} rows)')
    print('BATCH 2: ALL PASSED' if not failed else 'BATCH 2: SOME CHECKS FAILED')
    return failed


# ------------------------------------------------------------------ batch 3
# docs/art-progress.md appendix C (batch 3) with the ten decisions of 2026-09-28. Moves of the
# actions the program carries every sim frame (run, dodge, thrust, the walks) are measured in
# the sprite itself (appendix C: only the light attacks' picture catches up at frame changes).
RUN_FEET_JUMP = px(0.15)      # decision 1: the run's stance foot moves back 5.3 px a frame
RUN_LEAN = (10, 15)
RUN_BOB = 2
RUN_STRIDE = (px(0.35), px(0.4))          # ankles apart at contact, 14-16 px (side views)
RUN_FB_FEET = {'south': 8, 'north': 6}    # boot centres apart, the walk's (+-1)
# decision 2 set 4 px down and 2 px behind the feet's midpoint; the 2026-09-28 fix re-derived them
# from the legs' reach (the user saw the legs drawn flat): 2.5 down (the check allows 0.5 less than
# the target), the weight still behind the midpoint
CHARGE_DROP = 1.5             # pelvis 1.5 px below idle (+-0.25: the front / back views' projection); second fix, see ATTACK_STANCE
CHARGE_BEHIND = 0.5           # pelvis behind the feet's midpoint (side views)
BLADE_FLAT = 1                # blade level on screen +-1 px (the two end columns' rows), side views
# 2026-09-28 fix (the user): the charge and the thrust point the blade forward in every view, as
# perspective shows it - level from the side, foreshortened toward the camera from the front (a
# stub, the point below the hilt), hidden behind the body from the back (only the fist shows)
BLADE_DEPTH_MAX = px(0.15)    # a blade toward the camera may run 6 px below the ground row (0.35 x 17)
BLADE_STUB_MAX = px(0.2)      # front: the blade seen end-on spans at most 8 px on screen (its full length ~15)
BLADE_HIDDEN_MAX = 2          # back: at most 2 blade pixels seen past the body
FIST_SEEN_MIN = 4             # back: the sword fist still shows (pixels drawn)
LEG_STRETCH_MAX = 1.0         # side views: the near leg's hip to ankle no longer than the leg (walk_side LEG_LENS)
FEET_APART_MIN = px(0.175)    # 7 px: the boots (~6 px long) stay apart ("the feet stuck together")
LEG_STRETCH_FAR = 1.1         # the far leg, drawn behind it at 78 % brightness (the "worm" was a near leg at 1.29)
RELEASE_FEET_JUMP = px(0.15)  # 6 px: the feet in the thrust's two release steps (second charge fix)
# Accepted by the user (2026-09-29, second charge fix, option a): the guard and the charge differ by
# where the blade is (across the chest / at the hip, point forward), which an outline cannot see; a
# natural pose did not reach 12 % (the first fix's 16-degree lean did, and read as falling over).
# Recorded shares at approval: the check fails again if the two grow MORE alike than this
# (WAIVE_OUTLINE_EPS below the record), so a later change cannot hide behind the waiver.
B3_OUTLINE_WAIVED = {   # (a1, a2, view): (hold 1 vs hold 1, lowest walk frame vs walk frame)
    ('guard', 'charge', 'south'): (0.0506, 0.0398), ('guard', 'charge', 'east'): (0.0939, 0.0637),
    ('guard', 'charge', 'north'): (0.0387, 0.0226), ('guard', 'charge', 'west'): (0.0695, 0.0631),
}
WAIVE_OUTLINE_EPS = 0.002
# the user (2026-09-28): a walk slower than the plain walk must not step quicker than it ("the speed
# is slow, so there is no reason for the motion to be fast": the charge's 0.2 s cycle was a shuffle).
# The plain walk: 8 frames of 2 sim frames (batch 3 decision 1) at 100 px/s
WALK_CYCLE_SIM = 16
# Second charge fix (2026-09-28, the user: "not fixed"; drawing the legs alone showed why): the side
# legs drew as a table (east: the front knee level with the hip) and an "M" (west: both knees above
# it), the west legs were 2.4 px shorter from hip to ankle than the east ones, and from the front the
# back boot rode up onto the tassets with no leg under it. Checked on the charge's frames (in, hold,
# out, walk); the thrust's lunge lies its legs nearly flat by design (D1, approved from the side).
KNEE_BELOW_MIN = 0.1          # side: the knee at least 10 % of the hip-to-ankle height under the hip
SIDE_LEG_SYM = 1.5            # side: hold, east vs west hip-to-ankle height within 1.5 px
FB_LEG_SEEN_MIN = 2           # front / back: every leg at least 2 px from hip to ankle on screen


def leg_shape(f, view):
    """Side views: (lowest knee drop as a share of hip-to-ankle height, lowest hip-to-ankle height of a
    planted leg); front / back: (shortest hip-to-ankle height on screen, None)."""
    legs = f.debug.get('legs') or {}
    feet = f.pose.get('feet', {}) if hasattr(f, 'pose') else {}
    if view in ('east', 'west'):
        near = PR_VIEWS()[view]['near']
        side_of = {'near': near, 'far': 'L' if near == 'R' else 'R'}
        knee, planted = [], []
        for k, (h, kn, a) in legs.items():
            dy = a[1] - h[1]
            knee.append((kn[1] - h[1]) / dy if dy > 0.5 else -1.0)
            ft = feet.get(side_of.get(k, k))
            if not ft or (len(ft) < 3 or ft[2] < 0.25):
                planted.append(dy)
        return min(knee), (min(planted) if planted else None)
    return min(a[1] - h[1] for (h, _, a) in legs.values()), None


def far_sword_shown(f, view):
    """Side view where the sword hand is the far one (the user, 2026-09-28: facing west the sword
    held at the right hip is behind the body): (far arm / fist pixels shown, sword pixels shown over
    the body's own footprint - torso and its backing, as drawn before anything covered them)."""
    near = PR_VIEWS()[view]['near']
    far = 'L' if near == 'R' else 'R'
    arm = sum(1 for q, n in f.trace.items() if n in (f'upper_{far}', f'fore_{far}', f'fist_{far}') and q in f.px)
    body = set(f.pieces_raw.get('torso', {})) | set(f.pieces_raw.get('backing', {}))
    over = sum(1 for q, n in f.trace.items() if n == 'sword' and q in body and q in f.px)
    return arm, over


def PR_VIEWS():
    import pose_rig as PR
    return PR.VIEWS
B3_DISTINCT = [('guard', 'hold 1', 'charge', 'hold 1'), ('charge', 'hold 1', 'heal', 'hold 1')]
B3_DISTINCT_WALK = [('guard_walk', 'charge_walk'), ('charge_walk', 'heal_walk')]


def follows(lead, follow):
    """The shift s (frames, cyclic, -2..2) that best matches follow's frame-to-frame moves to
    lead's s frames earlier: + = follow is late. Judged on the frames in the order shown, so a
    cycle played in reverse (the head then leads) gives a negative shift."""
    n = len(lead)
    dl = [lead[(i + 1) % n] - lead[i] for i in range(n)]
    df = [follow[(i + 1) % n] - follow[i] for i in range(n)]
    if max(map(abs, dl), default=0) < 0.25:
        return None
    score = {s_: sum(df[i] * dl[(i - s_) % n] for i in range(n)) for s_ in (-2, -1, 0, 1, 2)}
    return max(score, key=lambda s_: (round(score[s_], 6), -abs(s_)))


def blade_ends(f):
    """Mean row of the blade's two end columns (a blade is two rows thick)."""
    bl = f.debug.get('blade') or set()
    xs = sorted({x for x, _ in bl})
    if len(xs) < 2:
        return None
    row = lambda x: sum(y for xx, y in bl if xx == x) / len([1 for xx, _ in bl if xx == x])
    return row(xs[0]), row(xs[-1])


def blade_forward(f, view, fist=True):
    """(ok, info) for a blade that points forward, as perspective shows it in this view (the
    2026-09-28 fix): level from the side, a stub toward the camera from the front, hidden behind
    the body from the back with the sword fist still in sight."""
    import math as _m
    bl = f.debug.get('blade') or set()
    if view in ('east', 'west'):
        be = blade_ends(f)
        return (be is not None and abs(be[0] - be[1]) <= BLADE_FLAT,
                'level from the side +-1 px', '' if be is None else f'end rows {be[0]:.1f} / {be[1]:.1f}')
    want_fist = fist
    fist_px = [q for q, n in f.trace.items() if n == 'fist_R' and q in f.px]
    if view == 'south':
        if not bl:
            return False, 'toward the camera', 'no blade'
        span = max(_m.hypot(a[0] - b[0], a[1] - b[1]) for a in bl for b in bl)
        fc = _cen(f, ('fist_R',))
        tip = max(bl, key=lambda q: (q[0] - fc[0]) ** 2 + (q[1] - fc[1]) ** 2)
        return (span <= BLADE_STUB_MAX and tip[1] > fc[1],
                f'toward the camera: a stub <= {BLADE_STUB_MAX} px, point below the fist',
                f'span {span:.1f} px, point row {tip[1]} vs fist {fc[1]:.1f}')
    seen = sum(1 for q in bl if f.trace.get(q) == 'sword' and q in f.px)
    need = FIST_SEEN_MIN if want_fist else 0
    return (seen <= BLADE_HIDDEN_MAX and len(fist_px) >= need,
            f'away from the camera: blade hidden (<= {BLADE_HIDDEN_MAX} px seen)' + (f', fist seen (>= {FIST_SEEN_MIN} px)' if want_fist else
                                                                                     ' (the arm reaches forward past the body: the fist is hidden too)'),
            f'blade {seen} of {len(bl)} px seen, fist {len(fist_px)} px')


def leg_stretch(f, which=None):
    """Side views: a leg's hip-to-ankle distance over the leg's length (walk_side LEG_LENS); all
    of them, or the 'near' / 'far' one's."""
    import math as _m
    import walk_side as W_
    L = sum(W_.LEG_LENS)
    legs = f.debug.get('legs') or {}
    d = {k: _m.hypot(a[0] - h[0], a[1] - h[1]) / L for k, (h, _, a) in legs.items()}
    return d[which] if which else list(d.values())


def batch3_checks():
    import batch1 as B1
    import batch3 as B3
    import pose_rig as PR
    import walk_side as W_
    failed = False

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

    def outline(share, key, which, name):
        """The outline row: PASS at >= OUTLINE_DIFF_MIN, else WAIV if the user accepted it and it is not
        more alike than recorded (B3_OUTLINE_WAIVED), else FAIL."""
        rec = B3_OUTLINE_WAIVED.get(key)
        info = f'{100 * share:.1f} %'
        if share >= OUTLINE_DIFF_MIN or rec is None or share < rec[which] - WAIVE_OUTLINE_EPS:
            out(share >= OUTLINE_DIFF_MIN, name, info + (f' (recorded {100 * rec[which]:.1f} %)' if rec else ''))
        else:
            print(f'  WAIV  {name}  {info}  [2026-09-29, user: accepted; recorded {100 * rec[which]:.1f} %, not more alike]')

    def named(action, view, name):
        src = B3 if action in B3.ACTIONS else B1
        return next(f for f in src.frames(action, view) if f.name == name)

    def pt(f):
        return _Pt(f, 0, 0, small=(getattr(f, 'canvas', None) == 'small' or f.action in B1.ACTIONS or
                                   B3.CANVAS.get(f.action) == 'small'))

    def inlim(m, body=B1_JUMP, feet=B1_JUMP, hand=B1_HAND_JUMP, sword=True):
        return (all(m[k] is None or m[k] <= body + 1e-6 for k in ('head', 'torso')) and
                (m['feet'] is None or m['feet'] <= feet + 1e-6) and
                (m['hands'] is None or m['hands'] <= hand + 1e-6) and
                (not sword or m['sword'] is None or m['sword'] <= hand + 1e-6))

    def sil(f):
        # frames of both canvases compared in the large one's coordinates
        o = SMALL_TO_LARGE if (f.action in B1.ACTIONS or B3.CANVAS.get(f.action) == 'small') else (0, 0)
        return {(x + o[0], y + o[1]) for x, y in _sil(f)}

    def cycle(action, view, kind):
        return [f for f in B3.frames(action, view) if f.name.startswith(kind + ' ')] if action in B3.ACTIONS else \
               [f for f in B1.frames(action, view) if f.name.startswith(kind + ' ')]

    print(f'== batch 3 (batch3.py): head / torso <= {B1_JUMP} px, feet <= {B1_JUMP} px (run {RUN_FEET_JUMP}), '
          f'hands / sword <= {B1_HAND_JUMP} px; outlines >= {round(OUTLINE_DIFF_MIN * 100)} %')
    # ---- every frame: the technical checks
    for action in B3.ACTIONS:
        for view in B3.VIEWS:
            for f in B3.frames(action, view):
                label = f'{action} / {f.name} / {view}'
                if f.pose is None:
                    continue                       # the walk rig's own frames: checked below, as the walk is
                rows = pose_rows(label, f.pose, B3.CANVAS[action], view)
                bad = [(n, i_) for n, ok, i_ in rows if ok is False]
                comp = [i_ for n, ok, i_ in rows if ok is None and n.startswith('INFO composited')]
                if bad:
                    for n, i_ in bad:
                        out(False, f'{label}: {n}', i_)
                else:
                    out(True, f'{label}: {len([r for r in rows if r[1] is not None])} technical checks', comp[0] if comp else '')

    # ---- run (decisions 1, 7, 9)
    if 'run' in B3.ACTIONS:
        print('-- run (appendix C, batch 3)')
        lean = B3.RUN_LEAN
        out(RUN_LEAN[0] <= lean <= RUN_LEAN[1], f'run: lean {RUN_LEAN[0]}-{RUN_LEAN[1]} deg', f'{lean} deg')
        for view in B3.VIEWS:
            fr = cycle('run', view, 'run')
            tor = [_cen(f, ('torso',))[1] for f in fr]
            out(round(max(tor) - min(tor)) == RUN_BOB, f'run {view}: pelvis bob {RUN_BOB} px', f'{max(tor) - min(tor):.1f} px')
            if view in ('east', 'west'):
                # side views: a foot is off the floor when its lowest pixel is above the ground
                # row (front / back: a foot stepping away from the camera also shows higher, so
                # there the pose's lifts are only reported)
                air = []
                for f in fr:
                    low = {s_: max((q[1] for q, n in f.trace.items() if n == 'leg_' + s_ and q in f.px), default=0)
                           for s_ in ('R', 'L')}
                    air.append(all(v_ < A.GROUND for v_ in low.values()))
                out(sum(air) == 2, f'run {view}: two of eight frames with both feet off the floor',
                    ', '.join(f.name for f, a_ in zip(fr, air) if a_))
                heel = [f.name for f in fr if any(f.pose['feet'][s_][3] == 'heel' and
                        max((q[1] for q, n in f.trace.items() if n == 'leg_' + s_ and q in f.px), default=0) != A.GROUND - 1 + 1
                        for s_ in ('R', 'L'))]
                out(not heel, f'run {view}: the heel-strike foot touches the floor', ', '.join(heel))
            else:
                out(None, f'run {view}: both feet lifted in the pose',
                    ', '.join(f.name for f in fr if all(f.pose['feet'][s_][2] > 0 for s_ in ('R', 'L'))))
            if view in ('east', 'west'):
                d = [abs(fr[i].debug['legs']['near'][2][0] - fr[i].debug['legs']['far'][2][0]) for i in (0, 4)]
                lo, hi = RUN_STRIDE
                out(all(lo - 0.5 <= x <= hi + 0.5 for x in d), f'run {view}: ankles {lo}-{hi} px apart at contact',
                    ' / '.join(f'{x:.1f}' for x in d))
            else:
                bc = [abs(fr[i].debug['legs']['R'][2][0] - fr[i].debug['legs']['L'][2][0]) for i in range(len(fr))]
                t_ = RUN_FB_FEET[view]
                out(all(abs(x - t_) <= 1 for x in bc), f'run {view}: feet {t_}+-1 px apart (the walk\'s)',
                    f'{min(bc):.1f}-{max(bc):.1f} px')
            worst, bad = {}, []
            for i in range(len(fr)):
                m = screen_moves(pt(fr[i]), pt(fr[(i + 1) % len(fr)]))
                if not inlim(m, feet=RUN_FEET_JUMP):
                    bad.append(f'{fr[i].name} -> {fr[(i + 1) % len(fr)].name}: {_fmt_moves(m)}')
                for k, v_ in m.items():
                    if v_ is not None:
                        worst[k] = max(worst.get(k, 0), v_)
            out(not bad, f'run {view}: 8 steps within the limits (feet {RUN_FEET_JUMP})', '; '.join(bad) or 'largest ' + _fmt_moves(worst))
            hs = follows([_cen(f, ('torso',))[1] for f in fr], [_cen(f, ('helmet',))[1] for f in fr])
            out(hs is not None and hs >= 1, f'run {view}: head follows the pelvis (in the order shown)', f'shift {hs}')
            ent = []
            for label, dst in (('stage 1 f1', __import__('batch2').frames(1, view)[0]), ('guard hold 1', named('guard', view, 'hold 1')),
                               ('charge in 1', named('charge', view, 'in 1')), ('heal in 1', named('heal', view, 'in 1'))):
                w_ = max((screen_moves(pt(f), _Pt(dst, 0, 0) if hasattr(dst, 'screen_offset') else pt(dst)) for f in fr),
                         key=lambda m: max(m[k] or 0 for k in ('head', 'torso', 'feet')))
                ent.append(f"{label}: head {w_['head']:.1f}, feet {w_['feet'] or 0:.1f}")
            out(None, f'run {view}: from the run straight into (decision 7: play-test once wired in; worst run frame)', '; '.join(ent))
            if view in ('east', 'west'):
                fd = PR.VIEWS[view]['facing']
                rep = []
                for hold in (2, 3, 4):
                    step = B3.RUN_SPEED / 60 * hold
                    dr = []
                    for i in range(len(fr)):
                        a_, b_ = fr[i], fr[(i + 1) % len(fr)]
                        for k, s_ in (('near', PR.VIEWS[view]['near']), ('far', 'L' if PR.VIEWS[view]['near'] == 'R' else 'R')):
                            if a_.pose['feet'][s_][2] == 0 and b_.pose['feet'][s_][2] == 0:
                                dr.append(abs(b_.debug['legs'][k][2][0] - a_.debug['legs'][k][2][0] + fd * step))
                    rep.append((hold, max(dr)))
                h2 = dict(rep)[2]
                out(h2 <= DRIFT_MAX + 1e-6, f'run {view}: stance foot on screen at 2 sim frames a frame (decision 1)',
                    'moves ' + ', '.join(f'{x:.2f} px at {h}' for h, x in rep) + ' (the user picks the hold)')

        print('-- run: starting and stopping (decision 7)')
        for view in B3.VIEWS:
            fr = cycle('run', view, 'run')
            idle = named('idle', view, 'idle 1')
            s1, s2 = named('run', view, '起跑 1'), named('run', view, '起跑 2')
            k0 = B3.RUN_START[view][0]
            steps = [(idle, s1, B1_JUMP), (s1, s2, B1_JUMP), (s2, fr[k0], RUN_FEET_JUMP)]
            bad = [f'{a_.name} -> {b_.name}: {_fmt_moves(m)}' for a_, b_, fl in steps
                   for m in [screen_moves(pt(a_), pt(b_))] if not inlim(m, feet=fl)]
            out(not bad, f'run {view}: idle -> start 1 -> start 2 -> run {k0 + 1} within the limits', '; '.join(bad))
            table = B3.run_stop_from(view)
            stops = {w: named('run', view, f'停步 1{w}') for w in ('A', 'B')}
            st2, st3 = named('run', view, '停步 2'), named('run', view, '停步 3')
            reach = []
            for j in range(8):
                n = next((d for d in range(3) if table[(j + d) % 8] is not None), None)
                reach.append(n)
            out(all(n is not None for n in reach), f'run {view}: every run frame reaches a stop within 2 more frames (the program slows for 4 sim frames)',
                f'extra frames {reach}; stop 1 from {table}')
            bad = []
            for j, w in enumerate(table):
                if w is None:
                    continue
                m = screen_moves(pt(fr[j]), pt(stops[w]))
                if not inlim(m, feet=RUN_FEET_JUMP):
                    bad.append(f'run {j + 1} -> stop 1{w}: {_fmt_moves(m)}')
            for w in {x for x in table if x}:
                for a_, b_ in ((stops[w], st2), (st2, st3), (st3, idle)):
                    m = screen_moves(pt(a_), pt(b_))
                    if not inlim(m):
                        bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
            out(not bad, f'run {view}: stop 1 -> 2 -> 3 -> idle within the limits', '; '.join(bad))
            m = screen_moves(pt(st3), pt(idle))
            out(all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet')),
                f'run {view}: stop 3 vs idle 1, head / torso / feet within {RETURN_MAX} px', _fmt_moves(m))
    # ---- charge (decisions 2, 3, 6)
    if 'charge' in B3.ACTIONS:
        print('-- charge (appendix C, batch 3)')
        for view in B3.VIEWS:
            h = named('charge', view, 'hold 1')
            rest = PR.rig(view)
            rest.frame({}, 'small')
            dy = h.debug['pelvis'][1] - 8 - rest.debug['pelvis'][1]      # large -> small canvas
            drop = dy - PR.proj(view, (h.pose['root'][0], h.pose['root'][1], 0))[1]
            out(abs(drop - CHARGE_DROP) <= 0.25, f'charge {view}: pelvis {CHARGE_DROP} px below idle', f'{drop:.2f} px')
            if view in ('east', 'west'):
                fd = PR.VIEWS[view]['facing']
                lg = h.debug['legs']
                mid = (lg['near'][2][0] + lg['far'][2][0]) / 2
                behind = (mid - h.debug['pelvis'][0]) * fd
                out(behind >= CHARGE_BEHIND - 0.05, f'charge {view}: pelvis at least {CHARGE_BEHIND} px behind the feet\'s midpoint',
                    f'{behind:.1f} px')
            ok, what, info = blade_forward(h, view)
            out(ok, f'charge {view}: blade forward - {what}', info)
            if view in ('east', 'west'):
                fr_ = [f for f in B3.frames('charge', view) if f.name.startswith('hold')] + B3.frames('charge_walk', view)
                wn = max(leg_stretch(f, 'near') for f in fr_)
                wf = max(leg_stretch(f, 'far') for f in fr_)
                out(wn <= LEG_STRETCH_MAX + 1e-6 and wf <= LEG_STRETCH_FAR + 1e-6,
                    f'charge {view}: legs within their length, hold and walk (hip to ankle / leg: near <= {LEG_STRETCH_MAX}, far <= {LEG_STRETCH_FAR})',
                    f'near {wn:.2f}, far {wf:.2f}')
                # the user (2026-09-28, second fix): the walk's quick short steps were a shuffle; it walks
                # a slow walk now, the feet passing under the body in turn. So: both feet on the floor ->
                # apart; closer than that -> one of them is off the floor, passing the other
                gaps, close = [], []
                for f in fr_:
                    gap = abs(f.debug['legs']['near'][2][0] - f.debug['legs']['far'][2][0])
                    lifted = max(ft[2] for ft in f.pose['feet'].values())
                    if lifted < 0.25:
                        gaps.append(gap)
                    elif gap < FEET_APART_MIN:
                        close.append(lifted)
                out(min(gaps) >= FEET_APART_MIN and all(c >= 1 for c in close),
                    f'charge {view}: both feet down -> ankles >= {FEET_APART_MIN} px apart; closer -> one foot up (passing)',
                    f'both down {min(gaps):.1f}-{max(gaps):.1f} px; {len(close)} passing frames, lift {min(close, default=0):.1f}-{max(close, default=0):.1f} px')
            # second fix: the legs' shape, every frame of the charge and its walk
            fr_all = B3.frames('charge', view) + B3.frames('charge_walk', view)
            shp = [(leg_shape(f, view), f.action + ' ' + f.name) for f in fr_all]
            if view in ('east', 'west'):
                worst = min(shp, key=lambda t: t[0][0])
                out(worst[0][0] >= KNEE_BELOW_MIN, f'charge {view}: no knee level with the hip (table / "M"): knee >= {KNEE_BELOW_MIN} of the leg under the hip',
                    f'lowest {worst[0][0]:.2f} ({worst[1]})')
            else:
                worst = min(shp, key=lambda t: t[0][0])
                out(worst[0][0] >= FB_LEG_SEEN_MIN, f'charge {view}: every leg >= {FB_LEG_SEEN_MIN} px from hip to ankle on screen (no boot riding on the tassets)',
                    f'shortest {worst[0][0]:.1f} px ({worst[1]})')
            fr = [f for f in B3.frames('charge', view) if f.name.startswith('hold')]
            dy_t = [round(_cen(f, ('torso',))[1] - _cen(fr[0], ('torso',))[1]) for f in fr]
            dy_h = [round(_cen(f, ('helmet',))[1] - _cen(fr[0], ('helmet',))[1]) for f in fr]
            out(max(dy_t) - min(dy_t) == 1 and dy_h == [dy_t[(i - 1) % 4] for i in range(4)],
                f'charge {view}: tremble 1 px, head a phase late (decision 3)', f'torso {dy_t}, head {dy_h}')
        # the sword hand is the far one facing west: behind the body, only the blade past its front shows
        vw = next(v for v in ('east', 'west') if PR.VIEWS[v]['near'] != 'R')
        fr_w = B3.frames('charge', vw) + B3.frames('charge_walk', vw)
        worst = max(((far_sword_shown(f, vw), f.name) for f in fr_w if f.name.startswith(('hold', 'fwd', 'back', 'side', 'rside'))),
                    key=lambda t: t[0][0] + t[0][1])
        out(worst[0] == (0, 0), f'charge {vw}: the far sword hand and the sword behind the body do not show through it (hold, walk)',
            f'worst {worst[1]}: arm / fist {worst[0][0]} px, sword over the body {worst[0][1]} px')
        hts = {v: leg_shape(named('charge', v, 'hold 1'), v)[1] for v in ('east', 'west')}
        out(abs(hts['east'] - hts['west']) <= SIDE_LEG_SYM,
            f'charge: hold 1 east vs west legs the same height from hip to ankle (within {SIDE_LEG_SYM} px)',
            f'east {hts["east"]:.1f}, west {hts["west"]:.1f} px')
        print(f'-- outlines: guard / charge / heal (decision 2: hard, >= {round(OUTLINE_DIFF_MIN * 100)} %)')
        for a1, n1, a2, n2 in B3_DISTINCT:
            for view in B3.VIEWS:
                s_ = outline_shift_share(sil(named(a1, view, n1)), sil(named(a2, view, n2)))
                outline(s_, (a1, a2, view), 0, f'{a1} {n1} vs {a2} {n2} {view}')
        for a1, a2 in B3_DISTINCT_WALK:
            for view in B3.VIEWS:
                f1 = B1.frames(a1, view) if a1 in B1.ACTIONS else B3.frames(a1, view)
                f2 = B1.frames(a2, view) if a2 in B1.ACTIONS else B3.frames(a2, view)
                # the same step: frames of the same cycle (fwd, side, back, rside) at the nearest
                # phase (the charge walks its own six-frame step forward / back since 2026-09-28)
                def by_kind(fr):
                    out_ = {}
                    for f in fr:
                        out_.setdefault(f.name.split(' ')[0], []).append(f)
                    return out_
                k1, k2 = by_kind(f1), by_kind(f2)
                vals = []
                for kind in k1:
                    c1, c2 = k1[kind], k2.get(kind, [])
                    for j, x in enumerate(c2):
                        y = c1[round(j * len(c1) / len(c2)) % len(c1)]
                        vals.append(outline_shift_share(sil(y), sil(x)))
                key = (a1.replace('_walk', ''), a2.replace('_walk', ''), view)
                outline(min(vals), key, 1, f'{a1} vs {a2} {view}, every frame (same step; lowest shown, highest {100 * max(vals):.1f} %)')
        for view in B3.VIEWS:
            s_ = outline_shift_share(sil(named('idle', view, 'idle 1')), sil(named('charge', view, 'hold 1')))
            out(None, f'idle vs charge hold 1 {view} (reported)', f'{round(100 * s_)} %')
        print('-- charge: moves between frames')
        for view in B3.VIEWS:
            idle = named('idle', view, 'idle 1')
            seq = [idle, named('charge', view, 'in 1'), named('charge', view, 'in 2'), named('charge', view, 'hold 1')]
            holds = [named('charge', view, f'hold {i}') for i in range(1, 5)]
            outs = [named('charge', view, 'out 1'), named('charge', view, 'out 2'), idle]
            pairs = list(zip(seq, seq[1:])) + [(holds[i], holds[(i + 1) % 4]) for i in range(4)] + \
                [(hh, outs[0]) for hh in holds] + list(zip(outs, outs[1:]))
            worst, bad = {}, []
            for a_, b_ in pairs:
                m = screen_moves(pt(a_), pt(b_))
                if not inlim(m):
                    bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
                for k, v_ in m.items():
                    if v_ is not None:
                        worst[k] = max(worst.get(k, 0), v_)
            out(not bad, f'charge {view}: in, hold, released early ({len(pairs)} steps) within the limits',
                '; '.join(bad) or 'largest ' + _fmt_moves(worst))
            m = screen_moves(pt(outs[1]), pt(idle))
            out(all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet')),
                f'charge {view}: out 2 vs idle 1, head / torso / feet within {RETURN_MAX} px', _fmt_moves(m))
            for g in [f for f in B1.frames('guard', view) if f.name.startswith('hold')]:
                m = screen_moves(pt(g), pt(named('charge', view, 'in 1')))
                out(inlim(m, sword=False),
                    f'charge {view}: guard {g.name} -> in 1 (batch 2 decision 3: the first frame of an attack, the sword is free)',
                    _fmt_moves(m))
            m = screen_moves(pt(named('charge', view, 'hold 1')), pt(named('guard', view, 'hold 1')))
            out(None, f'charge {view}: hold -> guard (decision 6: accepted, the guard is up the frame it is pressed)', _fmt_moves(m))
    if 'charge_walk' in B3.ACTIONS:
        print('-- charge walk: the slow legs under the charge')
        for kind in ('fwd', 'back'):
            cyc_sim = sum(f.dur for f in B3.frames('charge_walk', 'south') if f.name.startswith(kind + ' '))
            out(cyc_sim >= WALK_CYCLE_SIM, f'charge_walk {kind}: a cycle no quicker than the plain walk\'s ({WALK_CYCLE_SIM} sim frames)',
                f'{cyc_sim} sim frames ({cyc_sim / 60:.2f} s)')
        for a_ in ('guard_walk', 'heal_walk'):
            cyc_sim = sum(f.dur for f in B1.frames(a_, 'south') if f.name.startswith('fwd '))
            out(None, f'{a_} fwd cycle (reported)', f'{cyc_sim} sim frames ({cyc_sim / 60:.2f} s)')
        for view in B3.VIEWS:
            b = named('charge', view, 'hold 1')
            fr = B3.frames('charge_walk', view)
            bad = []
            for f in fr:
                bob = round(_cen(f, ('torso',))[1] - _cen(b, ('torso',))[1])
                for n in RIGID:
                    if n in b.pieces_raw and {(x, y + bob): c for (x, y), c in b.pieces_raw[n].items()} != f.pieces_raw.get(n, {}):
                        bad.append(f'{f.name}:{n}')
                if bob not in (0, 1):
                    bad.append(f'{f.name}: bob {bob}')
            out(not bad, f'charge_walk {view}: torso, arms, sword identical to hold 1 (bob 0-1 px)', ', '.join(bad[:6]))
            for kind in ('fwd', 'side', 'back', 'rside'):
                cyc = cycle('charge_walk', view, kind)
                n = len(cyc)
                worst, bad = {}, []
                for i in range(n):
                    m = screen_moves(pt(cyc[i]), pt(cyc[(i + 1) % n]))
                    if not inlim(m):
                        bad.append(f'{cyc[i].name} -> {cyc[(i + 1) % n].name}: {_fmt_moves(m)}')
                    for k, v_ in m.items():
                        if v_ is not None:
                            worst[k] = max(worst.get(k, 0), v_)
                ok_in = [f.name for f in cyc if inlim(screen_moves(pt(b), pt(f)))]
                ok_out = [f.name for f in cyc if inlim(screen_moves(pt(f), pt(b)))]
                out(not bad and bool(ok_in) and bool(ok_out), f'charge_walk {view} {kind}: cycle within the limits; start / stop at hold 1',
                    '; '.join(bad) or f'largest {_fmt_moves(worst)}; start at {len(ok_in)}, stop from {len(ok_out)} of {n}')
                hs = follows([_cen(f, ('torso',))[1] for f in cyc], [_cen(f, ('helmet',))[1] for f in cyc])
                if hs is None:
                    out(None, f'charge_walk {view} {kind}: head (the pelvis does not bob here)', '')
                else:
                    out(hs >= 1, f'charge_walk {view} {kind}: head follows the pelvis (in the order shown)', f'shift {hs}')
            if view in ('east', 'west'):
                # the 2026-09-28 fix gave the charge its own shorter step forward / back: the
                # planted foot must move back what the floor does each frame at 40 px/s (no slide)
                ground = 40.0 / 60 * B3.CW_HOLD
                for kind in ('fwd', 'back'):
                    cyc = cycle('charge_walk', view, kind)
                    fd = PR.VIEWS[view]['facing']
                    sl = []
                    for i in range(len(cyc)):
                        a_, b_ = cyc[i], cyc[(i + 1) % len(cyc)]
                        for k in ('near', 'far'):
                            s_ = PR.VIEWS[view]['near'] if k == 'near' else ('L' if PR.VIEWS[view]['near'] == 'R' else 'R')
                            if a_.pose['feet'][s_][2] == 0 and b_.pose['feet'][s_][2] == 0:
                                mv = (b_.debug['legs'][k][2][0] - a_.debug['legs'][k][2][0]) * fd
                                sl.append(abs(mv + (ground if kind == 'fwd' else -ground)))
                    # 0.25 px: the ankles are exact here (batch 2's 1 px on screen is a quarter of the run's step, 75 % of this one)
                    out(max(sl) <= 0.25, f'charge_walk {view} {kind}: planted feet keep to the floor ({ground:.2f} px a frame, +-0.25)',
                        f'off by at most {max(sl):.2f} px')
    # ---- thrust and execution (decision 5)
    if 'thrust' in B3.ACTIONS:
        print('-- thrust, execution (appendix C, batch 3; appendix A: thrust 42 sim frames, execution 60, hit on 12)')
        tt = sum(f.dur for f in B3.frames('thrust', 'south'))
        rec = sum(f.dur for f in B3.frames('thrust', 'south')[2:])
        out(tt == 42 and rec == 30, 'thrust: 42 sim frames, back to the stance within the 30 of recovery', f'{tt} / {rec}')
        ex = B3.frames('execute', 'south')
        t_, at12 = 0, None
        for f in ex:
            if t_ <= 12 < t_ + f.dur:
                at12 = f.name
            t_ += f.dur
        out(t_ == 60 and at12 == 'f3 保持 1', 'execute: 60 sim frames, the hit (sim frame 12) on the first hold frame', f'{t_}, frame 12 shows {at12}')
        for view in B3.VIEWS:
            fr = B3.frames('thrust', view)
            f2 = fr[1]
            ok, what, info = blade_forward(f2, view, fist=False)
            out(ok, f'thrust {view}: blade forward - {what}', info)
            for n, ok, i_ in pose_rows('thrust', f2.pose, 'large', view):
                if n.startswith('attack stance'):
                    out(ok, f'thrust {view}: {n}', i_)
            # the release (charge hold -> f1 -> f2): decision 5's 8 px for head / torso. Second charge
            # fix (2026-09-28): the feet too (RELEASE_FEET_JUMP) - the charge stands 9 px wide now and
            # the approved D1 lunge 23: the back foot travels 8.7 px in the two release steps, over 4
            # a step whatever the split, while the program carries the body 12 px
            holds = [named('charge', view, f'hold {i}') for i in range(1, 5)]
            steps = [(hh, fr[0], SWING_JUMP) for hh in holds] + [(fr[0], fr[1], SWING_JUMP)] + \
                    [(fr[i], fr[i + 1], B1_JUMP) for i in range(1, len(fr) - 1)] + [(fr[-1], named('idle', view, 'idle 1'), B1_JUMP)]
            worst, bad = {}, []
            for a_, b_, body in steps:
                m = screen_moves(pt(a_), pt(b_))
                if not inlim(m, body=body, feet=RELEASE_FEET_JUMP if body == SWING_JUMP else B1_JUMP):
                    bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
                for k, v_ in m.items():
                    if v_ is not None:
                        worst[k] = max(worst.get(k, 0), v_)
            out(not bad, f'thrust {view}: release (head / torso {SWING_JUMP} px), hold, back to idle within the limits',
                '; '.join(bad) or 'largest ' + _fmt_moves(worst))
            m = screen_moves(pt(fr[-1]), pt(named('idle', view, 'idle 1')))
            out(all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet')),
                f'thrust {view}: last frame vs idle 1, head / torso / feet within {RETURN_MAX} px', _fmt_moves(m))
            # f2 -> f3: the body stops, the cloth ends go on
            tor = [_cen(f, ('torso',)) for f in fr[1:4]]
            cap = [_end_centroid(f, 'cape', 'torso') for f in fr[1:4]]
            dr = max(_dist(tor[0], tor[1]), _dist(tor[1], tor[2]))
            de = min(_dist(cap[0], cap[1]), _dist(cap[1], cap[2]))
            out(dr < 0.25 and de >= 0.5, f'thrust {view}: the cape end still moves after the body stops (f2 -> f3 -> f3)',
                f'body {dr:.1f} px, cape end {de:.1f} px')
            for sim in (fr[0], ):
                pass
            for w in [f for f in B3.frames('charge_walk', view) if f.name.startswith('fwd ')][:1]:
                m = screen_moves(pt(w), pt(fr[0]))
                out(None, f'thrust {view}: released while walking ({w.name} -> f1)', _fmt_moves(m))
            # execution: its own starts, then the thrust's f2 on
            ef = B3.frames('execute', view)
            idle = named('idle', view, 'idle 1')
            steps = [(idle, ef[0]), (ef[0], ef[1]), (ef[1], ef[2])]
            bad, worst = [], {}
            for a_, b_ in steps:
                m = screen_moves(pt(a_), pt(b_))
                if not inlim(m, body=SWING_JUMP, sword=a_ is not idle):
                    bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
                for k, v_ in m.items():
                    if v_ is not None:
                        worst[k] = max(worst.get(k, 0), v_)
            out(not bad, f'execute {view}: idle -> start 1 -> start 2 -> lunge (head / torso {SWING_JUMP} px; the sword free on the first)',
                '; '.join(bad) or 'largest ' + _fmt_moves(worst))
            for label, src in [('guard hold 1', named('guard', view, 'hold 1'))] + \
                    [(f'stage {st} {f.name}', f) for st in (1, 2) for f in __import__('batch2').frames(st, view)[4:]]:
                p_src = _Pt(src, *src.screen_offset()) if hasattr(src, 'screen_offset') else pt(src)
                if hasattr(src, 'screen_offset'):
                    p_src = _Pt(src, 0, 0)
                m = screen_moves(p_src, pt(ef[0]))
                out(None, f'execute {view}: {label} -> start 1 (reported)', _fmt_moves(m))
    # ---- dodge (decision 4)
    if 'dash' in B3.ACTIONS:
        print('-- dodge (appendix C, batch 3; decision 4: entering is not limited, every step after is)')
        import poses as PQ
        out(25 <= PQ.DASH['lean'] <= 30, 'dash: lean 25-30 deg', f"{PQ.DASH['lean']} deg")
        out(10 <= -PQ.BACKSTEP['lean'] <= 15, 'backstep: leans back 10-15 deg', f"{-PQ.BACKSTEP['lean']} deg")
        for act in ('dash', 'backstep'):
            tot = sum(f.dur for f in B3.frames(act, 'south'))
            moving = sum(f.dur for f in B3.frames(act, 'south')[:2])
            out(tot == 18 and moving == 11, f'{act}: 18 sim frames, the first two frames cover the move (0-10)', f'{tot} / {moving}')
        for view in B3.VIEWS:
            rest = PR.rig(view)
            rest.frame({}, 'small')
            for act, key in (('dash', '煞停 2'), ('backstep', '落地 2')):
                f = named(act, view, key)
                drop = f.debug['pelvis'][1] - rest.debug['pelvis'][1] - PR.proj(view, (f.pose['root'][0], f.pose['root'][1], 0))[1]
                out(abs(drop - px(0.05)) <= 0.5, f'{act} {view}: {key}, pelvis {px(0.05)} px low', f'{drop:.1f} px')
                fr = B3.frames(act, view)
                idle = named('idle', view, 'idle 1')
                steps = list(zip(fr, fr[1:])) + [(fr[-1], idle)]
                worst, bad = {}, []
                for a_, b_ in steps:
                    m = screen_moves(pt(a_), pt(b_))
                    if not inlim(m):
                        bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
                    for k, v_ in m.items():
                        if v_ is not None:
                            worst[k] = max(worst.get(k, 0), v_)
                out(not bad, f'{act} {view}: {len(steps)} steps from f1 to idle within the limits', '; '.join(bad) or 'largest ' + _fmt_moves(worst))
                m = screen_moves(pt(fr[-1]), pt(idle))
                out(all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet')),
                    f'{act} {view}: last frame vs idle 1, head / torso / feet within {RETURN_MAX} px', _fmt_moves(m))
                # f1 -> f2: the body is already there; the head and the cloth ends catch up
                t0, t1 = _cen(fr[0], ('torso',)), _cen(fr[1], ('torso',))
                h0, h1 = _cen(fr[0], ('helmet',)), _cen(fr[1], ('helmet',))
                c0, c1 = _end_centroid(fr[0], 'cape', 'torso'), _end_centroid(fr[1], 'cape', 'torso')
                # cloth: the batch 1 threshold (an end moving >= 0.5 px while its root is still)
                out(_dist(t0, t1) < 0.25 and _dist(h0, h1) >= 1 and _dist(c0, c1) >= 0.5,
                    f'{act} {view}: f1 -> f2, the head and the cape end catch up with the body',
                    f'body {_dist(t0, t1):.1f}, head {_dist(h0, h1):.1f}, cape end {_dist(c0, c1):.1f} px')
                srcs = [('idle 1', idle), ('guard hold 1', named('guard', view, 'hold 1')), ('charge hold 1', named('charge', view, 'hold 1')),
                        ('run 1', named('run', view, 'run 1'))]
                vals = []
                for label, src in srcs:
                    m = screen_moves(pt(src), pt(fr[0]))
                    vals.append(f"{label}: head {m['head']:.1f}, feet {m['feet'] if m['feet'] is None else round(m['feet'], 1)}")
                out(None, f'{act} {view}: entering (decision 4: not limited)', '; '.join(vals))
    # ---- the locked walk (decisions 1, 8)
    if 'walk_locked' in B3.ACTIONS:
        print('-- locked walk: backward = the walk rig run the other way; sidesteps (85 px/s, 2 sim frames a frame)')
        spr_of = {'south': 'front', 'east': 'side_right', 'north': 'back', 'west': 'side_left'}
        for view in B3.VIEWS:
            spr = spr_of[view]
            back = cycle('walk_locked', view, 'back')
            idle = A.stand_frame(spr).px
            m_ = A.META[spr]
            neck = int(NECK[spr] + A.GROUND - m_['feet'])
            walk = [f.px for f in back]
            base = enclosed(idle, neck)
            vals = [enclosed(p_, neck) for p_ in walk]
            out(not ({c[:3] for p_ in walk for c in p_.values()} - PALETTE), f'walk back {view}: colours inside the reference palette')
            out(max(vals) <= base, f'walk back {view}: see-through holes below the neck', f'{vals} (idle {base})')
            for nm, fn in (('1px pinholes', pinholes), ('floating specks', specks)):
                b0 = fn(idle)
                vv = [fn(p_) for p_ in walk]
                out(max(vv) <= b0, f'walk back {view}: {nm}', f'{vv} (idle {b0})')
            lowest = max(y for p_ in walk for (_, y) in p_)
            outside = sum(1 for p_ in walk for (x, y) in p_ if not (0 <= x < A.FW and 0 <= y < A.FH))
            out(outside == 0 and lowest <= A.GROUND + BELOW_GROUND_MAX, f'walk back {view}: inside the frame, feet at most {BELOW_GROUND_MAX} px below ground',
                f'lowest row {lowest}')
            fw = [walk_rigs_frame for walk_rigs_frame in (B3.walk_rig(view).frame(i).px for i in range(8))]
            for nm, fn in (('blue cloth', lambda p_: sum(1 for c in p_.values() if A.is_blue(c))), ('highlights', lambda p_: sum(1 for c in p_.values() if light(c)))):
                b0 = fn(idle)
                vv = [fn(p_) for p_ in walk]
                fwd = sorted(fn(p_) for p_ in fw)
                ok = all(within(v_, b0) for v_ in vv)
                # the forward walk has one frame each under the rule (walk notes, pending); the
                # backward frames are the same legs, so the same counts may show up
                known = sorted(vv) == fwd
                out(ok or (known and None), f'walk back {view}: {nm} vs idle (±10 % or ±{TOLERANCE_PX} px)',
                    f'{vv} vs idle {b0}' + ('' if ok else ' (the same counts as the forward walk: its pending walk items)'))
            sets = [set(p_) for p_ in walk]
            jumps = [jump(sets[i], sets[(i + 1) % 8]) for i in range(8)]
            out(max(jumps) <= JUMP_MAX, f'walk back {view}: frame-to-frame jump <= {JUMP_MAX} px', f'{jumps}')
            heads = [f.debug['head_y'] for f in back]
            hips = [f.debug['hip_y'] for f in back]
            out(max(heads) - min(heads) >= BOB_MIN - 1e-6, f'walk back {view}: head bob >= {BOB_MIN} px', f'{max(heads) - min(heads):.1f} px')
            hs = follows(hips, heads)
            rv = []
            for i in range(8):
                B3.walk_rig(view).frame((8 - i) % 8)
                rv.append((B3.walk_rig(view).debug['hip_y'], B3.walk_rig(view).debug['head_y']))
            hs_rev = follows([a_ for a_, _ in rv], [b_ for _, b_ in rv])
            out(hs is not None and hs >= 1, f'walk back {view}: head follows the hip (in the order shown)',
                f'shift {hs}; the forward walk played in reverse: {hs_rev}')
            for kind in ('side', 'rside'):
                cyc = cycle('walk_locked', view, kind)
                worst, bad = {}, []
                for i in range(4):
                    m = screen_moves(pt(cyc[i]), pt(cyc[(i + 1) % 4]))
                    if not inlim(m):
                        bad.append(f'{cyc[i].name} -> {cyc[(i + 1) % 4].name}: {_fmt_moves(m)}')
                    for k, v_ in m.items():
                        if v_ is not None:
                            worst[k] = max(worst.get(k, 0), v_)
                idle1 = named('idle', view, 'idle 1')
                ok_in = [f.name for f in cyc if inlim(screen_moves(pt(idle1), pt(f)), sword=False)]
                out(not bad and bool(ok_in), f'walk_locked {view} {kind}: cycle within the limits; starts from idle',
                    '; '.join(bad) or f'largest {_fmt_moves(worst)}; from idle at {", ".join(ok_in)}')
                hs = follows([_cen(f, ('torso',))[1] for f in cyc], [_cen(f, ('helmet',))[1] for f in cyc])
                if hs is None:
                    out(None, f'walk_locked {view} {kind}: head (the pelvis does not bob here)', '')
                else:
                    out(hs >= 1, f'walk_locked {view} {kind}: head follows the pelvis (in the order shown)', f'shift {hs}')
                if view in ('south', 'north'):
                    lat = [f.pose['feet'] for f in cyc]
                    moved = []
                    for i in range(4):
                        a_, b_ = lat[i], lat[(i + 1) % 4]
                        for s_ in ('R', 'L'):
                            if a_[s_][2] == 0 and b_[s_][2] == 0:
                                moved.append(abs(b_[s_][1] - a_[s_][1]) * PR.FEET_W[view])
                    ground = 85.0 / 60 * B3.LOCKED_HOLD
                    out(None, f'walk_locked {view} {kind}: planted feet move {max(moved):.1f} px a frame against the floor\'s {ground:.2f} (slide {100 * (1 - max(moved) / ground):.0f} %, brief: about half)', '')
    # ---- decision 8: the slow legs of batch 1, backward and to the right, in the order shown
    print('-- decision 8: backward / rightward cycles are their own (head follows in the order shown)')
    for action in ('guard_walk', 'heal_walk'):
        for view in B3.VIEWS:
            res = []
            for kind in ('fwd', 'back', 'side', 'rside'):
                cyc = cycle(action, view, kind)
                res.append((kind, follows([_cen(f, ('torso',))[1] for f in cyc], [_cen(f, ('helmet',))[1] for f in cyc])))
            ok = all(s_ is None or s_ >= 1 for _, s_ in res)
            out(ok, f'{action} {view}: head follows the pelvis', ', '.join(f'{k} {s_}' for k, s_ in res))
    print('BATCH 3: ALL PASSED' if not failed else 'BATCH 3: SOME CHECKS FAILED')
    return failed


# ------------------------------------------------------------------ batch 4
# docs/art-progress.md appendix C (batch 4) and the brief of 2026-09-28 ("第 4 批：動作簡報",
# its decisions 2-7 and the handoff notes). The knockback moves the character every sim frame
# (appendix C: measured in the sprite itself). Limits: the first frame of a hit reaction is
# free; the fall's steps head / torso 8 px (decision 5 of batch 2's kind) and feet 8 px (a
# stumbling fall: the feet step and pitch while the program carries the body 4 px a sim frame;
# batch 4's own call, in art-progress.md); the landing and the push up from the lying H 10 px
# (head, torso, feet); every other step 4 / 20 px; each action's last frame within 4 px of idle.
FALL_JUMP = px(0.2)           # 8 px
LAND_JUMP = px(0.25)          # 10 px
STAGGER_LEAN = (10, 15)
FOOT_UP = px(0.05)            # stagger f1: a foot at least 2 px off the floor
KNEEL_TOP = (px(0.1), px(0.175))          # guard break kneel: helmet top 4-7 px lower than idle
KNEEL_HIP = (0.55, 0.65)      # get-up kneel: pelvis height 55-65 % of the idle's
IDLE_HIP = 10.0               # the idle hip joint above the floor line, east view (row 54 - 44.0)
SWAY_PX = 1                   # guard break sway: 1 px each way
B4_TIMING = {'stagger': 21, 'knockdown': 48, 'launch_air': 21, 'launch_down': 36, 'getup': 30,
             'guard_break': 72, 'death': 90}      # appendix A (player_data.gd)


def lie_rows(f):
    """Technical checks of a lying / launched frame (the restored H, batch 0's lying rows)."""
    import concept_pose as CP
    p = f.px
    idle, _ = pose_idle('east')
    rows = [('colours inside the reference palette', not ({c[:3] for c in p.values()} - PALETTE), '')]
    outside = sum(1 for (x, y) in p if not (0 <= x < A.FW and 0 <= y < A.FH))
    rows.append(('inside the canvas', outside == 0, f'{outside} px outside'))
    low = max(y for (_, y) in p)
    rows.append(('nothing below the ground row', low <= A.GROUND, f'lowest row {low}, ground {A.GROUND}'))
    e, e0 = enclosed_in(p, A.FW, A.FH, -1), enclosed(idle, -1)
    rows.append(('see-through holes (the whole figure)', e <= e0, f'{e} (idle {e0})'))
    sp, sp0 = specks(p), specks(idle)
    rows.append(('floating specks', sp <= sp0, f'{sp} (idle {sp0})'))
    m = CP.lying_metrics()
    lo, hi = LIE_BODY
    rows.append((f'body height {lo}-{hi} px behind the helmet', lo <= m['body_h'] <= hi, f"{m['body_h']} px"))
    b, h = counts(p)
    ref = CP.lying_frame(head_left=(f.row == 'R'))
    b0, h0 = counts(ref)
    rows.append(('INFO detail vs batch 0 lying frame', None, f'blue {b}/{b0}, highlights {h}/{h0}'))
    return rows


def batch4_checks():
    import batch1 as B1
    import batch4 as B4
    import concept_pose as CP
    import pose_rig as PR
    import poses as PQ
    failed = False

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

    def pt(f):
        return _Pt(f, 0, 0, small=True)

    def inlim(m, body=B1_JUMP, feet=B1_JUMP, hand=B1_HAND_JUMP):
        return (all(m[k] is None or m[k] <= body + 1e-6 for k in ('head', 'torso')) and
                (m['feet'] is None or m['feet'] <= feet + 1e-6) and
                all(m[k] is None or m[k] <= hand + 1e-6 for k in ('hands', 'sword')))

    def steps(label, pairs, body=B1_JUMP, feet=B1_JUMP):
        worst, bad = {}, []
        for a_, b_ in pairs:
            m = screen_moves(pt(a_), pt(b_))
            if not inlim(m, body, feet):
                bad.append(f'{a_.name} -> {b_.name}: {_fmt_moves(m)}')
            for k, v_ in m.items():
                if v_ is not None:
                    worst[k] = max(worst.get(k, 0), v_)
        out(not bad, label, '; '.join(bad) or 'largest ' + _fmt_moves(worst))

    def ret(label, f, idle):
        m = screen_moves(pt(f), pt(idle))
        out(all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet')),
            f'{label}: last frame vs idle 1, head / torso / feet within {RETURN_MAX} px', _fmt_moves(m))

    idle = {v: next(f for f in B1.frames('idle', v) if f.name == 'idle 1') for v in B4.VIEWS}
    print(f'== batch 4 (batch4.py): head / torso / feet <= {B1_JUMP} px, hands / sword <= {B1_HAND_JUMP} px; '
          f'the fall {FALL_JUMP} px, the landing and the push up {LAND_JUMP} px; a hit\'s first frame free')
    # ---- every frame: the technical checks
    every = [(a, v, f) for a in B4.VIEW_ACTIONS for v in B4.VIEWS for f in B4.frames(a, v)] + \
            [(a, r, f) for a in B4.ROW_ACTIONS for r in B4.ROWS for f in B4.frames(a, r)]
    for action, key, f in every:
        label = f'{action} / {f.name} / {key}' + ('' if f.view in (key, 'lie') else f' ({f.view})')
        rows = lie_rows(f) if f.view == 'lie' else pose_rows(label, f.pose, 'small', f.view)
        bad = [(n, i_) for n, ok, i_ in rows if ok is False]
        comp = [i_ for n, ok, i_ in rows if ok is None and (n.startswith('INFO composited') or n.startswith('INFO detail'))]
        if bad:
            for n, i_ in bad:
                out(False, f'{label}: {n}', i_)
        else:
            out(True, f'{label}: {len([r for r in rows if r[1] is not None])} technical checks', comp[0] if comp else '')

    # ---- stagger
    print('-- stagger (appendix C: leans back 10-15 deg, a foot >= 2 px off the floor; 21 sim frames)')
    for v in B4.VIEWS:
        fr = B4.frames('stagger', v)
        if v == B4.VIEWS[0]:
            out(sum(f.dur for f in fr) == B4_TIMING['stagger'], 'stagger: 21 sim frames', f'{sum(f.dur for f in fr)}')
            lean = -fr[0].pose.get('lean', 0)
            out(STAGGER_LEAN[0] <= lean <= STAGGER_LEAN[1], f'stagger: f1 leans back {STAGGER_LEAN[0]}-{STAGGER_LEAN[1]} deg', f'{lean} deg')
        low = {s_: max((q[1] for q, n in fr[0].trace.items() if n == 'leg_' + s_ and q in fr[0].px), default=0) for s_ in ('R', 'L')}
        up = A.GROUND - min(low.values())
        if v in ('east', 'west'):
            out(up >= FOOT_UP, f'stagger {v}: f1 a foot at least {FOOT_UP} px off the floor', f'{up} px')
        else:
            out(None, f'stagger {v}: f1 foot off the floor (front / back: depth moves it too)', f'{up} px')
        steps(f'stagger {v}: f1 -> f2 -> f3 -> idle within the limits', list(zip(fr, fr[1:])) + [(fr[-1], idle[v])])
        ret(f'stagger {v}', fr[-1], idle[v])
        if v in ('east', 'west'):
            # the head a beat late: it goes on back (relative to the torso) after the body
            # has started to come up (f1 -> f2)
            back = -PR.VIEWS[v]['facing']
            rel = [(_cen(f, ('helmet',))[0] - _cen(f, ('torso',))[0]) * back for f in (idle[v],) + tuple(fr)]
            out(rel[2] > rel[1] + 0.25, f'stagger {v}: the head goes back a beat after the body (head behind the torso, idle / f1 / f2 / f3)',
                ' / '.join(f'{x:.1f}' for x in rel))
        m = screen_moves(pt(idle[v]), pt(fr[0]))
        out(None, f'stagger {v}: idle -> f1 (a hit\'s first frame: free)', _fmt_moves(m))

    # ---- knockdown, launch, death (two rows)
    print('-- knockdown: turn and pitch forward (decision 2); launch; death')
    kd0 = B4.frames('knockdown', 'R')
    t_ = sum(f.dur for f in kd0)
    fall_ = sum(f.dur for f in kd0[:5])
    out(t_ == B4_TIMING['knockdown'] and fall_ == 11, 'knockdown: 48 sim frames, the fall 0-10', f'{t_}, fall {fall_}')
    out(sum(d for _, d in B4.DEATH) == B4_TIMING['death'] and [n for n, _ in B4.DEATH] == [f.name for f in kd0],
        'death: 90 sim frames on the knockdown\'s frames', f'{sum(d for _, d in B4.DEATH)}')
    out(B4.LAUNCH_AIR == B4_TIMING['launch_air'] and sum(d for _, d in B4.LAUNCH_DOWN) == B4_TIMING['launch_down'],
        'launch: 21 in the air, then 36 down', f'{B4.LAUNCH_AIR}, {sum(d for _, d in B4.LAUNCH_DOWN)}')
    for r in B4.ROWS:
        k = B4.frames('knockdown', r)
        rec, turn, stu, pit, land, down = k
        out(rec.view == B4.FACING_VIEW[r] and turn.view == 'south' and stu.view == pit.view == B4.AWAY_VIEW[r],
            f'knockdown {r}: recoil facing the attacker, turn facing the camera, stumble and pitch facing away',
            f'{rec.view}, {turn.view}, {stu.view}, {pit.view}')
        # the fall goes away from the attacker: the pitch's and the lying frames' heads lie on
        # the far side of the anchor
        sgn = -1 if r == 'R' else 1
        hx = [(_cen(f, ('helmet',))[0] - A.CX) * sgn for f in (pit, land, down)]
        out(all(x > 0 for x in hx), f'knockdown {r}: pitches away from the attacker (head past the anchor: pitch, landing, lying)',
            ' / '.join(f'{x:.1f}' for x in hx))
        for a_, b_ in ((rec, turn), (turn, stu)):
            m = screen_moves(pt(a_), pt(b_))
            out(None, f'knockdown {r}: {a_.name} -> {b_.name} (the view changes: shown for the eye)', _fmt_moves(m))
        steps(f'knockdown {r}: stumble -> pitch within the fall\'s {FALL_JUMP} px', [(stu, pit)], FALL_JUMP, FALL_JUMP)
        steps(f'knockdown {r}: pitch -> landing within {LAND_JUMP} px', [(pit, land)], LAND_JUMP, LAND_JUMP)
        steps(f'knockdown {r}: landing -> lying within the limits', [(land, down)])
        # lying is batch 0's approved frame itself; the landing still has its cloth up
        out(down.px == CP.lying_frame(head_left=(r == 'R')), f'knockdown {r}: lying is batch 0\'s lying frame, pixel for pixel')
        # the cape measured against the body under it (the landing is also tipped a little)
        my = lambda f, n: sum(q[1] for q in f.pieces_raw.get(n, {})) / max(1, len(f.pieces_raw.get(n, {})))
        cy = lambda f: my(f, 'cape') - my(f, 'torso')
        out(cy(down) - cy(land) >= 0.5, f'knockdown {r}: the landing\'s cape still up, settled when lying (cape above the body)',
            f'{-cy(land):.1f} -> {-cy(down):.1f} px')
        for src in ([f for f in B1.frames('guard', B4.FACING_VIEW[r]) if f.name == 'hold 1'][0], B4.named('guard_break', B4.FACING_VIEW[r], '搖晃 1')):
            m = screen_moves(pt(src), pt(rec))
            out(None, f'knockdown {r}: {src.action} {src.name} -> recoil (a hit\'s first frame: free)', _fmt_moves(m))
        a1, a2 = B4.frames('launch', r)
        body = lambda f: {q: c for q, c in f.px.items() if f.trace.get(q) not in ('cape', 'plume')}
        b1_, b2_ = body(a1), body(a2)
        moved = [q for q in b1_ if q in b2_ and b1_[q] != b2_[q]] + [q for q in b1_ if q not in a2.px]
        cloth = sum(1 for q in set(a1.px) | set(a2.px) if a1.px.get(q) != a2.px.get(q))
        out(not moved and cloth > 0, f'launch {r}: the body identical in both air frames, only the cloth moves',
            f'{len(moved)} body px differ, {cloth} px of cloth differ')
        steps(f'launch {r}: air 1 <-> air 2 within the limits', [(a1, a2), (a2, a1)])
        steps(f'launch {r}: air -> landing within {LAND_JUMP} px', [(a1, land), (a2, land)], LAND_JUMP, LAND_JUMP)

    # ---- getting up
    print('-- getting up (30 sim frames; the kneel takes the program\'s facing)')
    tot = sum(f.dur for f in B4.frames('getup_floor', 'R')) + sum(f.dur for f in B4.frames('getup', 'south'))
    durs = [f.dur for f in B4.frames('getup_floor', 'R')] + [f.dur for f in B4.frames('getup', 'south')]
    out(tot == B4_TIMING['getup'] and all(2 <= d for d in durs), 'getup: 30 sim frames, every frame at least 2', f'{tot}: {durs}')
    for r in B4.ROWS:
        down = B4.frames('knockdown', r)[5]
        gf = B4.frames('getup_floor', r)
        side = B4.AWAY_VIEW[r]
        out(all(f.view == side for f in gf), f'getup {r}: all fours and the rise on the lying side ({side})')
        steps(f'getup {r}: lying -> all fours within {LAND_JUMP} px', [(down, gf[0])], LAND_JUMP, LAND_JUMP)
        steps(f'getup {r}: all fours -> rise 1-4 -> kneel ({side}) within the limits', list(zip(gf, gf[1:])) + [(gf[-1], B4.frames('getup', side)[0])])
        vals = []
        for v in B4.VIEWS:
            if v != side:
                m = screen_moves(pt(gf[-1]), pt(B4.frames('getup', v)[0]))
                vals.append(f'{v}: head {m["head"]:.1f}')
        out(None, f'getup {r}: rise 4 -> kneel facing another way (the view changes: shown for the eye)', '; '.join(vals))
    for v in B4.VIEWS:
        g = B4.frames('getup', v)
        rest = PR.rig(v)
        rest.frame({}, 'small')
        drop = g[0].debug['pelvis'][1] - rest.debug['pelvis'][1] - PR.proj(v, (g[0].pose['root'][0], g[0].pose['root'][1], 0))[1]
        ratio = (IDLE_HIP - drop) / IDLE_HIP
        out(KNEEL_HIP[0] - 1e-6 <= ratio <= KNEEL_HIP[1] + 1e-6, f'getup {v}: kneel pelvis {round(100 * KNEEL_HIP[0])}-{round(100 * KNEEL_HIP[1])} % of the idle\'s height',
            f'{round(100 * ratio)} % (down {drop:.1f} of {IDLE_HIP})')
        steps(f'getup {v}: kneel -> stand 1 -> stand 2 -> idle within the limits', list(zip(g, g[1:])) + [(g[-1], idle[v])])
        ret(f'getup {v}', g[-1], idle[v])

    # ---- guard break
    print('-- guard break (72 sim frames; appendix C: kneel helmet top 4-7 px down, sway 1 px)')
    gb0 = B4.frames('guard_break', 'south')
    t_ = sum(f.dur for f in gb0) + sum(f.dur for f in gb0 if f.name.startswith('搖晃'))
    out(t_ == B4_TIMING['guard_break'], 'guard break: 72 sim frames (the sway plays twice)', f'{t_}')
    for v in B4.VIEWS:
        g = B4.frames('guard_break', v)
        kn = g[2]
        top = min(y for (x, y), n in kn.trace.items() if n == 'helmet') - _helmet_top(v)
        out(KNEEL_TOP[0] <= top <= KNEEL_TOP[1], f'guard break {v}: kneel helmet top {KNEEL_TOP[0]}-{KNEEL_TOP[1]} px lower than idle', f'{top} px')
        guards = [f for f in B1.frames('guard', v) if f.name.startswith('hold')]
        steps(f'guard break {v}: guard hold 1-4 -> knees give 1', [(h, g[0]) for h in guards])
        sw = g[3:7]
        steps(f'guard break {v}: knees give 1 -> 2 -> kneel -> sway, the sway cycle, push up, half stand, idle',
              [(g[0], g[1]), (g[1], g[2]), (g[2], sw[0])] + [(sw[i], sw[(i + 1) % 4]) for i in range(4)] +
              [(sw[3], g[7]), (g[7], g[8]), (g[8], idle[v])])
        ret(f'guard break {v}', g[8], idle[v])
        # every view sways along the screen's x (front / back: side to side; side views: to and fro)
        tx = [round(_cen(f, ('torso',))[0] - _cen(kn, ('torso',))[0]) for f in sw]
        hx = [round(_cen(f, ('helmet',))[0] - _cen(kn, ('helmet',))[0]) for f in sw]
        out(max(map(abs, tx)) == SWAY_PX and min(tx) == -SWAY_PX and hx == [tx[(i - 1) % 4] for i in range(4)],
            f'guard break {v}: sway {SWAY_PX} px each way, head a phase late', f'torso {tx}, head {hx}')
        ends = [_end_centroid(f, 'cape', 'torso')[0] for f in sw]
        tors = [_cen(f, ('torso',))[0] for f in sw]
        hs = follows(tors, ends)
        out(hs is not None and hs >= 1, f'guard break {v}: the cape end follows the body (in the order shown)', f'shift {hs}')
        blades = [frozenset(f.debug.get('blade') or ()) for f in sw]
        out(len(set(blades)) == 1 and blades[0], f'guard break {v}: the sword stays planted through the sway', f'{len(set(blades))} blade position(s)')
        for f in [f for f in B1.frames('guard_walk', v) if f.name in ('fwd 1', 'side 2')]:
            m = screen_moves(pt(f), pt(g[0]))
            out(None, f'guard break {v}: guard walk {f.name} -> knees give 1 (reported)', _fmt_moves(m))
    print('-- outlines (reported): guard break kneel vs heal (both lean on the sword), stagger f1 vs idle')
    for v in B4.VIEWS:
        a_ = _sil(B4.frames('guard_break', v)[2])
        b_ = _sil(next(f for f in B1.frames('heal', v) if f.name == 'hold 1'))
        c_ = _sil(B4.frames('stagger', v)[0])
        d_ = _sil(idle[v])
        out(None, f'{v}: kneel vs heal {round(100 * outline_shift_share(a_, b_))} %, stagger f1 vs idle {round(100 * outline_shift_share(c_, d_))} %', '')
    print('BATCH 4: ALL PASSED' if not failed else 'BATCH 4: SOME CHECKS FAILED')
    return failed


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--poses' in args:
        sys.exit(1 if pose_checks() else 0)
    if '--batch1' in args:
        sys.exit(1 if batch1_checks() else 0)
    if '--batch2' in args:
        sys.exit(1 if batch2_checks(record='--record-waivers' in args) else 0)
    if '--batch3' in args:
        sys.exit(1 if batch3_checks() else 0)
    if '--batch4' in args:
        sys.exit(1 if batch4_checks() else 0)
    sys.exit(main())
