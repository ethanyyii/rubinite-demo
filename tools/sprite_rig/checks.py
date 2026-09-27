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
    'charge': (px(0.075), px(0.35)),
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
DISTINCT = [('guard', 'parry')]
# reported: idle vs guard / charge stay 8-12 % / 6-26 % (3-4x the alike level) with the
# guard's pelvis at the approved 1 px; pushing them past 12 % would need a deeper crouch
# than the brief's guard target, so that is the user's call
DISTINCT_INFO = [('idle', 'guard'), ('idle', 'charge'), ('guard', 'l1_top'), ('guard', 'heal'),
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
    low_leg, low_other = -1, -1
    legpx = {(x + dx, y + dy) for (x, y), n in r.trace.items() if n.startswith('leg')}
    for (x, y) in p:
        n = r.trace.get((x - dx, y - dy), '')
        if n == '' and any((x + a, y + b) in legpx for a in (-1, 0, 1) for b in (-1, 0, 1)):
            n = 'leg (clean-up)'      # a seam the clean-up closed on a boot
        if n.startswith('leg'):
            low_leg = max(low_leg, y)
        else:
            low_other = max(low_other, y)
    rows.append((f'feet at most {BELOW_GROUND_MAX} px below ground, nothing else below it',
                 low_leg <= gy + BELOW_GROUND_MAX and low_other <= gy, f'feet row {low_leg}, others {low_other}, ground {gy}'))
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


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--poses' in args:
        sys.exit(1 if pose_checks() else 0)
    sys.exit(main())
