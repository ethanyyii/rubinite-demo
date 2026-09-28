"""Batch 0 (docs/art-progress.md): the key pose sheet and the new-part design sheets.

    python3 tools/sprite_rig/export_poses.py

Writes to docs/art-preview/player/batch0/ (previews only; nothing goes into the game):
  batch0_key_poses.png   every key pose x four views at the game's 3x, next to its concept
                         thumbnail (same size as the character)
  batch0_new_parts.png   N1 the sword at 16 angles next to the reference blades;
                         N2 the arm and fist next to the library arm (same places, 4 views)
  batch0_closeups.png    6x: N3 guard (east and south first) and parry; N4 the west sword arm;
                         N5 lean / lunge; N6 kneel; N7 lying and launched
  batch0_head_check.png  above the neck, every pose (yellow = background the plume encloses)
  batch0_gaps.png        poses where background shows between an arm / the sword and the body
  batch0_restore_eval.png  review 1 item 5: concept thumbnails restored to 40 px next to the
                         rig's poses, and the restored idle next to the library idle

The concept sheet does not draw its thumbnails at one scale (the action figures are
1.1-1.3x the idle one and differ among themselves), so each thumbnail is shown as tall as the
pose it is compared with (helmet top to floor); the lying H at the scale its restoration
uses. Overlays draw the thumbnail's outline (magenta) on the east view (§4.6).
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

import sprites as A
import pose_rig as P
import poses as Q
import sword as SW
import walk_side as W
import walk_fb as F
import concept_pose as CP

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch0')
CONCEPT = os.path.join(ROOT, 'docs', 'art-reference', 'player-knight-concept.webp')
FLOOR = (226, 219, 204, 255)     # the concept sheet's paper colour: the thumbnails sit on it too
SHADOW = (196, 188, 172, 255)
BG = (30, 30, 34, 255)
VIEWS = ['south', 'east', 'north', 'west']
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
# concept thumbnail named in poses.py -> its box in concept_pose.BOX; overlays only where the
# thumbnail draws the same pose (E, the jump, is only a weight reference for the charge)
REF_KEY = {'C1': 'C1', 'C4': 'C4', 'C2': 'C2', 'C3': 'C3', 'D1': 'D1', 'D2': 'D2', 'D3': 'D3', 'B1': 'B1', 'B': 'B2', 'F': 'F',
           'G(部分)': 'G', '設計圖沒畫(E)': 'E', 'H': 'H'}
OVERLAY = {'C2', 'C3', 'D1', 'D2', 'D3', 'B1', 'B', 'F', 'G(部分)', 'H'}
MAGENTA = (255, 0, 200, 255)
TW = 300            # thumbnail column width in the key pose sheet


def font(size):
    for p in ('/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def cell(px, canvas, k, floor=True):
    W_, H_, cx, gy = P.CANVAS[canvas]
    im = Image.new('RGBA', (W_, H_), FLOOR if floor else (96, 112, 96, 255))
    if floor:
        ImageDraw.Draw(im).ellipse((cx - 14, gy - 2, cx + 14, gy + 3), fill=SHADOW)
    im.alpha_composite(P.image(px, canvas))
    return up(im, k)


def render(name, pose, canvas, view, lying=False):
    if lying:
        return CP.lying_frame(head_left=(view == 'east'), airborne=pose['airborne'])
    return P.rig(view).frame(pose, canvas)


def CP_KEY(ref):
    return REF_KEY.get(ref)


def body_top(fig):
    """Top of the helmet in a thumbnail figure: the first row with a run of at least 8
    armour pixels (a raised blade or the plume are thinner or blue)."""
    arm = {k for k, c in fig.items() if not A.is_blue(c) and not (c[2] > c[0] + 15 and c[2] > 80)}
    for y in sorted({y for _, y in arm}):
        xs = sorted(x for x, yy in arm if yy == y)
        run = best = 1
        for a, b in zip(xs, xs[1:]):
            run = run + 1 if b == a + 1 else 1
            best = max(best, run)
        if best >= 8:
            return y
    return min(y for _, y in arm)


def our_body_height(name, pose, canvas, lying=False):
    """Helmet top to floor of our east view."""
    if lying:
        return None
    r = P.rig('east')
    r.frame(pose, canvas)
    top = min(y for (x, y), n in r.trace.items() if n == 'helmet')
    return A.GROUND - top + 1


_SCALE = {}


def concept_scale(ref, name=None, pose=None, canvas=None, lying=False):
    """Character px per concept px for one thumbnail. The concept sheet does not draw its
    thumbnails at one scale (the action figures are 1.1-1.3x the idle one, and differ among
    themselves), so each is scaled to stand as tall as our pose: helmet top to floor. H is
    shown at the scale its restoration uses."""
    key = CP_KEY(ref)
    if key == 'H':
        x0, _, x1, _ = CP.extent(CP.figure('H'))
        return CP.LIE_LENGTH / (x1 - x0 + 1)
    if (ref, name) not in _SCALE:
        fig = CP.figure(key)
        h_thumb = max(y for _, y in fig) - body_top(fig) + 1
        h_ours = our_body_height(name, pose, canvas) if name else 40
        _SCALE[(ref, name)] = h_ours / h_thumb
    return _SCALE[(ref, name)]


def thumb(ref, k, name=None, pose=None, canvas=None):
    """The concept thumbnail at the character's scale x k (see concept_scale)."""
    key = CP_KEY(ref)
    if key is None:
        return None
    im = Image.open(CONCEPT).convert('RGBA').crop(CP.BOX[key])
    sc = concept_scale(ref, name, pose, canvas) * k
    return im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)


def concept_outline(ref, name=None, pose=None, canvas=None):
    """The thumbnail figure's silhouette at the character's scale (pixel set)."""
    key = CP_KEY(ref)
    fig = CP.figure(key)
    x0, y0, x1, y1 = CP.extent(fig)
    sc = concept_scale(ref, name, pose, canvas)
    im = Image.new('L', (x1 - x0 + 1, y1 - y0 + 1), 0)
    for (x, y) in fig:
        im.putpixel((x - x0, y - y0), 255)
    Wt, Ht = max(1, round(im.width * sc)), max(1, round(im.height * sc))
    sm = im.resize((Wt, Ht), Image.BOX)
    pts = {(x, y) for x in range(Wt) for y in range(Ht) if sm.getpixel((x, y)) >= 128}
    return pts


def feet_centre(pts):
    low = max(y for _, y in pts)
    xs = [x for x, y in pts if y >= low - 3]
    return (min(xs) + max(xs)) / 2, low


def overlay_cell(name, pose, canvas, ref, k, lying=False):
    """East view with the thumbnail's outline laid over it (feet on feet), and how much of
    the two silhouettes overlap (intersection / union)."""
    W_, H_, cx, gy = P.CANVAS[canvas]
    px = render(name, pose, canvas, 'east', lying)
    ours = set(k_ for k_ in px if 0 <= k_[0] < W_ and 0 <= k_[1] < H_)
    theirs = concept_outline(ref, None if lying else name, pose, canvas)
    fx, low = feet_centre(theirs)
    ox, _ = feet_centre(ours)
    dx, dy = round(ox - fx), gy - low
    moved = {(x + dx, y + dy) for x, y in theirs}
    edge = {(x, y) for (x, y) in moved if any(q not in moved for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))}
    im = cell(px, canvas, k)
    d = ImageDraw.Draw(im)
    for (x, y) in edge:
        if 0 <= x < W_ and 0 <= y < H_:
            d.rectangle((x * k, y * k, x * k + k - 1, y * k + k - 1), fill=MAGENTA)
    match = len(ours & moved) / len(ours | moved)
    return im, match


def stack(rows, pad=6, bg=BG):
    w = max(r.width for r in rows)
    h = sum(r.height + pad for r in rows)
    out = Image.new('RGBA', (w, h), bg)
    y = 0
    for r in rows:
        out.alpha_composite(r, (0, y))
        y += r.height + pad
    return out


def hrow(cells, pad=6, bg=BG):
    w = sum(c.width + pad for c in cells)
    h = max(c.height for c in cells)
    out = Image.new('RGBA', (w, h), bg)
    x = 0
    for c in cells:
        out.alpha_composite(c, (x, h - c.height))
        x += c.width + pad
    return out


def label(text, w, size=18, h=26):
    im = Image.new('RGBA', (w, h), BG)
    ImageDraw.Draw(im).text((4, 2), text, fill=(255, 255, 255, 255), font=font(size))
    return im


def key_pose_sheet(k=3):
    rows = []
    cw = P.CANVAS['large'][0] * k
    head = [label('設計圖（縮成與成品等高）', TW, 16), label('朝右＋設計圖輪廓（洋紅）', cw, 16)] + \
        [label(VIEW_ZH[v], cw, 16) for v in VIEWS]
    rows.append(hrow(head))
    for name, pose, canvas, ref, text in Q.KEY_POSES + Q.LYING_POSES:
        lying = (name, pose, canvas, ref, text) in Q.LYING_POSES
        cells = []
        W_, H_, cx, gy = P.CANVAS[canvas]
        # concept thumbnail at the character's scale
        tc = Image.new('RGBA', (TW, P.CANVAS['large'][1] * k), BG)
        t = thumb(ref, k, None if lying else name, pose, canvas)
        if t is not None:
            if t.width > TW:
                t = t.crop(((t.width - TW) // 2, 0, (t.width - TW) // 2 + TW, t.height))
            tc.alpha_composite(t, ((TW - t.width) // 2, max(0, tc.height - t.height - (72 - 61) * k)))
        ImageDraw.Draw(tc).text((4, 4), ref, fill=(230, 230, 230, 255), font=font(14))
        cells.append(tc)
        oc = Image.new('RGBA', (cw, P.CANVAS['large'][1] * k), BG)
        if ref in OVERLAY:
            im, match = overlay_cell(name, pose, canvas, ref, k, lying)
            oc.alpha_composite(im, ((cw - im.width) // 2, (P.CANVAS['large'][3] - gy) * k))
            ImageDraw.Draw(oc).text((4, 4), f'重疊 {round(100 * match)} %', fill=(255, 255, 255, 255), font=font(14))
        cells.append(oc)
        for v in VIEWS:
            slot = Image.new('RGBA', (cw, P.CANVAS['large'][1] * k), BG)
            if lying and v in ('south', 'north'):
                ImageDraw.Draw(slot).text((8, slot.height // 2), '躺姿只做左右', fill=(150, 150, 150, 255), font=font(14))
            else:
                c = cell(render(name, pose, canvas, v, lying), canvas, k)
                # sit every canvas on the same ground line
                slot.alpha_composite(c, ((cw - c.width) // 2, (P.CANVAS['large'][3] - gy) * k))
            cells.append(slot)
        rows.append(label(f'{text}   畫格 {W_}x{H_}', TW + 5 * (cw + 6), 16))
        rows.append(hrow(cells))
    return stack(rows, 2)


def ref_blades(k):
    """The library's own blades (front, east, west), cropped from the idle sprites."""
    cells = []
    for spr, cfg, fb in (('front', F.FRONT, True), ('side_right', W.EAST, False), ('side_left', W.WEST, False)):
        pix, _ = A.SPR[spr]
        parts = W.split(pix, cfg['parts'](pix) if fb else cfg['parts'](), 'torso')
        sw = parts['sword']
        xs = [x for x, _ in sw]
        ys = [y for _, y in sw]
        im = Image.new('RGBA', (max(xs) - min(xs) + 5, max(ys) - min(ys) + 5), (96, 112, 96, 255))
        for (x, y), c in sw.items():
            im.putpixel((x - min(xs) + 2, y - min(ys) + 2), c)
        cells.append(up(im, k))
    return cells


def new_parts_sheet(k=6):
    rows = [label('N1 劍的角度組：每個角度用原圖劍的顏色重畫（劍身不旋轉）。第 1 排劍身 1px，第 2 排 2px（原圖的亮面＋暗面），'
                  '第 3 排＝姿勢裡用的加亮版（兩排都亮，擋在鎧甲前才分得出來，第二版起）', 2400)]
    for width, bright in ((1, False), (2, False), (2, True)):
        cells = []
        for i in range(16):
            ang = math.radians(i * 22.5)
            px, _ = SW.sword_pixels((22.5, 22.5), (math.cos(ang), math.sin(ang)), 1.0, width, bright=bright)
            im = Image.new('RGBA', (45, 45), (96, 112, 96, 255))
            for (x, y), c in px.items():
                if 0 <= x < 45 and 0 <= y < 45:
                    im.putpixel((x, y), c)
            cells.append(up(im, 4))
        rows.append(hrow(cells, 4))
    cells = []
    for ln in (1.0, 0.6, 0.35):
        px, _ = SW.sword_pixels((8, 22), (1, 0.35), ln, 2)
        im = Image.new('RGBA', (30, 36), (96, 112, 96, 255))
        for (x, y), c in px.items():
            if 0 <= x < 30 and 0 <= y < 36:
                im.putpixel((x, y), c)
        cells.append(up(im, k))
    rows.append(label('朝鏡頭／背鏡頭的縮短版（長度 100% / 60% / 35%）　｜　右：零件庫原圖的劍（正面、朝右、朝左），同倍率', 1600))
    rows.append(hrow(cells + ref_blades(k)))
    # N2: textured arm + fist at the library arm's own place, next to the library idle
    rows.append(label('N2 手臂與護手：左＝零件庫待機（原圖手臂）｜右＝新手臂（原圖手臂紋理的兩段式手臂＋護手）放在同一位置', 1600))
    cells = []
    for v in VIEWS:
        spr = P.VIEWS[v]['sprite']
        idle = A.stand_frame(spr).px
        cells.append(cell(idle, 'small', k, floor=False))
        cells.append(cell(P.rig(v).frame(rest_arms_pose(v), 'small'), 'small', k, floor=False))
    rows.append(hrow(cells[:4]))
    rows.append(hrow(cells[4:]))
    fist = Image.new('RGBA', (7, 7), (96, 112, 96, 255))
    for (x, y), c in P.fist_pixels((3.5, 3.5)).items():
        fist.putpixel((x, y), c)
    ring = {}
    P.outline(P.fist_pixels((3.5, 3.5)), ring)
    for (x, y), c in ring.items():
        fist.putpixel((x, y), c)
    rows.append(hrow([label('護手（3x3 加描邊，12 倍）', 300), up(fist, 12)]))
    return stack(rows, 4)


def rest_arms_pose(view):
    """Both arms textured, hands where the library's hands are (for the N2 comparison)."""
    v = P.VIEWS[view]
    arms = {}
    grips = {'south': {'R': (10.6, 37.6), 'L': (36.0, 38.0)}, 'north': {'L': (4.0, 38.5)},
             'east': {'R': (22.4, 38.2)}, 'west': {'L': (4.0, 35.0)}}[view]
    for s_, g in grips.items():
        sx, sy = v['sh'][s_]
        dx, dy = g[0] - sx, g[1] - sy
        pr = P.PROJ[view]
        if view in ('east', 'west'):
            rel = (dx / pr['F'][0], 0.0, -dy)
        else:
            rel = (0.0, dx / pr['L'][0], -dy)
        arms[s_] = dict(hand=rel, elbow=(0, -1 if s_ == 'R' else 1, 0))
    pose = dict(arms=arms)
    if 'R' in arms:
        d = {'south': (0.45, -0.9, -0.9), 'east': (0.8, 0.0, -0.6), 'north': (0, 0, -1), 'west': (0, 0, -1)}[view]
        pose['sword'] = dict(hand='R', dir=d)
    return pose


def closeups(k=6):
    rows = []

    def sec(title, items):
        rows.append(label(title, 1800))
        cells = []
        for name, v, lying in items:
            pose, canvas = POSES[name]
            cells.append(cell(render(name, pose, canvas, v, lying), canvas, k))
        rows.append(hrow(cells))

    sec('N3 格擋 f1（雙手握劍柄，隻狼式）：朝右、朝下（依指示），再來朝上、朝左',
        [('guard', 'east', False), ('guard', 'south', False), ('guard', 'north', False), ('guard', 'west', False)])
    sec('N3 完美彈返 f4（劍往外上方撥開）', [('parry', v, False) for v in ('east', 'south', 'north', 'west')])
    sec('N4 朝左的持劍右臂（原圖在身體後面；不用鏡像）：格擋、輕攻擊 1 頂點、1 揮完、4 揮完',
        [('guard', 'west', False), ('l1_top', 'west', False), ('l1_end', 'west', False), ('l4_end', 'west', False)])
    sec('N5 前傾與前撲的軀幹：閃身衝刺、突刺前撲、輕攻擊 4 揮完（朝右、朝左）',
        [('dash', 'east', False), ('thrust', 'east', False), ('l4_end', 'east', False), ('dash', 'west', False), ('thrust', 'west', False)])
    sec('N6 跪姿（架勢崩潰 f2：單膝跪地、雙手扶著點地的劍）', [('kneel', v, False) for v in VIEWS])
    sec('N7 躺姿（倒地 f4）與擊飛（空中）：從設計圖 H 還原（長 50px），左右為鏡像；劍另畫、布料獨立一層',
        [('down', 'east', True), ('down', 'west', True), ('launch', 'east', True), ('launch', 'west', True)])
    h = thumb('H', k)
    rows.append(hrow([label('設計圖 H（同比例）', 300), h]))
    return stack(rows, 4)


POSES = {n: (p, c) for n, p, c, _, _ in Q.KEY_POSES + Q.LYING_POSES}


def enclosed_mask(px, W_, H_):
    opaque = set(px)
    outside = set()
    stack_ = [(x, y) for x in range(-1, W_ + 1) for y in (-1, H_)] + [(x, y) for y in range(-1, H_ + 1) for x in (-1, W_)]
    while stack_:
        q = stack_.pop()
        if q in outside or q in opaque or not (-1 <= q[0] <= W_ and -1 <= q[1] <= H_):
            continue
        outside.add(q)
        stack_ += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
    return {(x, y) for x in range(W_) for y in range(H_) if (x, y) not in opaque and (x, y) not in outside}


def head_check(k=6):
    rows = [label('頸部以上：每個姿勢（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區）', 1600)]
    for name, pose, canvas, ref, text in Q.KEY_POSES:
        cells = [label(text, 200, 14, 40)]
        for v in VIEWS:
            r = P.rig(v)
            px = r.frame(pose, canvas)
            W_, H_, cx, gy = P.CANVAS[canvas]
            dx, dy = cx - A.CX, gy - A.GROUND
            helm = [(x + dx, y + dy) for (x, y), n in r.trace.items() if n == 'helmet']
            cut = max(y for _, y in helm) + 2
            x0 = min(x for x, _ in helm) - 12
            x1 = max(x for x, _ in helm) + 14
            y0 = min(y for (x, y) in px if x0 <= x < x1) - 1
            tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
            tile.alpha_composite(P.image(px, canvas))
            for (x, y) in enclosed_mask(px, W_, H_):
                if y < cut:
                    tile.putpixel((x, y), (255, 230, 0, 255))
            cells.append(up(tile.crop((max(0, x0), max(0, y0), min(W_, x1), cut)), k))
        rows.append(hrow(cells))
    return stack(rows, 4)


def gaps_sheet(k=6):
    import checks as C
    rows = [label('肢體之間露出的背景（橘色）：手臂或劍和身體之間的空隙，不是零件的破洞', 1600)]
    cells = []
    for name, pose, canvas, ref, text in Q.KEY_POSES:
        for v in VIEWS:
            r = P.rig(v)
            px = r.frame(pose, canvas)
            W_, H_, cx, gy = P.CANVAS[canvas]
            dx, dy = cx - A.CX, gy - A.GROUND
            helm = [y for (x, y), n in r.trace.items() if n == 'helmet']
            holes, gaps = C.hole_kinds(px, W_, H_, max(helm) + dy, r, dx, dy)
            if not gaps:
                continue
            tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
            tile.alpha_composite(P.image(px, canvas))
            for (x, y) in enclosed_mask(px, W_, H_):
                if y > max(helm) + dy:
                    tile.putpixel((x, y), (255, 140, 0, 255))
            cells.append(stack([label(f'{text} {VIEW_ZH[v]}', W_ * k, 14), up(tile, k)], 2))
    if cells:
        rows.append(hrow(cells))
    else:
        rows.append(label('（這一版沒有：所有封閉的背景都已消除）', 1600, 16))
    return stack(rows, 4)


def restore_eval(k=6):
    """Review 1 item 5: would restoring the east key poses straight from the thumbnails be
    more faithful? Each row: thumbnail | restored at the character's scale | the rig's east
    pose. Last row: the idle thumbnail restored next to the library's east idle, the frame
    every animation starts from."""
    rows = [label('第 5 項評估：設計圖小圖 ｜ 直接還原到 40px 尺度 ｜ 骨架做的朝右姿勢（同比例，6 倍）', 1800)]
    for ref, name in (('C2', 'l1_top'), ('D1', 'thrust'), ('F', 'stagger'), ('G(部分)', 'kneel')):
        pose, canvas = POSES[name]
        key = CP_KEY(ref)
        px = CP.restore(key, concept_scale(ref, name, pose, canvas))
        rest = Image.new('RGBA', (max(x for x, _ in px) + 3, max(y for _, y in px) + 3), FLOOR)
        for (x, y), c in px.items():
            rest.putpixel((x + 1, y + 1), c)
        rig_im = cell(render(name, pose, canvas, 'east'), canvas, k)
        rows.append(label(f'{ref} → {name}', 1800, 16))
        rows.append(hrow([thumb(ref, k, name, pose, canvas), up(rest, k), rig_im]))
    fig = CP.figure('A1')
    px = CP.restore('A1', 40 / (max(y for _, y in fig) - body_top(fig) + 1), fig)
    rest = Image.new('RGBA', (max(x for x, _ in px) + 3, max(y for _, y in px) + 3), FLOOR)
    for (x, y), c in px.items():
        rest.putpixel((x + 1, y + 1), c)
    lib = cell(A.stand_frame('side_right').px, 'small', k)
    rows.append(label('待機：設計圖小圖 A1 還原（左）｜ 零件庫朝右待機＝走路與所有動畫的起點（右）', 1800, 16))
    rows.append(hrow([up(rest, k), lib]))
    return stack(rows, 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    outs = {'batch0_key_poses.png': key_pose_sheet(), 'batch0_new_parts.png': new_parts_sheet(),
            'batch0_closeups.png': closeups(), 'batch0_head_check.png': head_check(),
            'batch0_gaps.png': gaps_sheet(), 'batch0_restore_eval.png': restore_eval()}
    for fn, im in outs.items():
        im.convert('RGB').save(os.path.join(OUT, fn))
        print('wrote', os.path.relpath(os.path.join(OUT, fn), ROOT), im.size)


if __name__ == '__main__':
    sys.exit(main())
