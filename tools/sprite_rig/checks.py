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


if __name__ == '__main__':
    sys.exit(main())
