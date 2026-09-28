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
        'guard_walk': [('guard_walk', f'fwd {i}', 'guard_walk', f'fwd {i % 8 + 1}') for i in range(1, 9)] +
                      [('guard_walk', f'side {i}', 'guard_walk', f'side {i % 4 + 1}') for i in range(1, 5)] +
[],
        'heal_walk': [('heal_walk', f'fwd {i}', 'heal_walk', f'fwd {i % 8 + 1}') for i in range(1, 9)] +
                     [('heal_walk', f'side {i}', 'heal_walk', f'side {i % 4 + 1}') for i in range(1, 5)] +
[],
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
            for kind in ('fwd', 'side'):
                fr = [f for f in B.frames(action, view) if f.name.startswith(kind)]
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
                near = [f.debug['legs']['near'][2][0] for f in B.frames(action, view) if f.name.startswith('fwd')]
                walk = [W_.NEAR_FOOT[i][0] for i in range(8)]
                rng, wrng = max(near) - min(near), max(walk) - min(walk)
                out(abs(rng - HALF_STRIDE * wrng) <= 1.0, f'{action} {view}: stride half the walk', f'{rng:.1f} px vs walk {wrng:.1f}')
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


def batch2_checks():
    import batch1 as B1
    import batch2 as B2
    import poses as PQ
    import pose_rig as PR
    import math as _m
    import walk_side as W_
    failed = False

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

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
        out(lo <= lean <= hi, f'stage {st}: follow-through lean {lo}-{hi} deg', f'{lean} deg')
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
        out(max(steps) <= B1_HAND_JUMP + 1e-6, f'item 7 {view}', f'{steps[0]:.1f} / {steps[1]:.1f} px')
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
                    bad.append(f'{fr[i].name} -> {fr[i + 1].name}: {_fmt_moves(m)}')
                for k, v in m.items():
                    if v is not None:
                        worst[k] = max(worst.get(k, 0), v)
            out(not bad, f'stage {st} {view}: {len(fr) - 1} steps within the limits', '; '.join(bad) or 'largest ' + _fmt_moves(worst))
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
            out(w[0] <= DRIFT_MAX + 1e-6, f'stage {st} {view}: weight foot on screen', f'largest {w[0]:.1f} px ({w[1]})')
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
            out(_ok(m), f'{view}: chain stage {a_st} {a.name} -> stage {b_st} {b.name} (sim frame {B2.ATTACK[a_st][0] + B2.ATTACK[a_st][1]})', _fmt_moves(m))
            for late in B2.frames(a_st, view)[(4 if a_st != 3 else 3):]:     # the recovery frames
                pl = pt(late)
                m = screen_moves(pl, pb)
                out(_ok(m, sword=False), f'{view}: late chain stage {a_st} {late.name} -> stage {b_st} {b.name} (decision 3: head / torso / feet <= 4)', _fmt_moves(m))
        f1 = B2.frames(1, view)[0]
        p1 = pt(f1)
        idle = B1.frames('idle', view)[0]
        guard = [f for f in B1.frames('guard', view) if f.name.startswith('hold')]
        slow = B1.frames('guard_walk', view)
        for label, src in [('idle 1', idle)] + [(f'guard {g.name}', g) for g in guard] + [(f'guard walk {g.name}', g) for g in slow]:
            m = screen_moves(_Pt(src, small=True), p1)
            out(_ok(m, sword=False), f'{view}: {label} -> stage 1 f1 (decision 3: the sword is free)', _fmt_moves(m))
        for st in (1, 2, 4):
            last = B2.frames(st, view)[-1]
            m = screen_moves(pt(last), _Pt(idle, fx * total(st), fy * total(st), small=True))
            ok = all(m[k] is None or m[k] <= RETURN_MAX + 1e-6 for k in ('head', 'torso', 'feet'))
            out(ok, f'{view}: stage {st} {last.name} vs idle 1: head, torso, feet within {RETURN_MAX} px', _fmt_moves(m))
    print('BATCH 2: ALL PASSED' if not failed else 'BATCH 2: SOME CHECKS FAILED')
    return failed


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--poses' in args:
        sys.exit(1 if pose_checks() else 0)
    if '--batch1' in args:
        sys.exit(1 if batch1_checks() else 0)
    if '--batch2' in args:
        sys.exit(1 if batch2_checks() else 0)
    sys.exit(main())
