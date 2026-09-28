"""Batch 1 (docs/art-progress.md): idle, guard, heal and the slow legs.

    python3 tools/sprite_rig/export_batch1.py

Writes (previews for review; nothing is wired into the game):
  assets/sprites/player/knight_<action>.png   sprite sheets, rows S / E / N / W, 56 x 56 cells,
                                             foot anchor (28, 53); columns as in batch1.ACTIONS
  docs/art-preview/player/batch1/
    batch1_<action>_3x.png / _6x.png         every frame x four views, labelled with its sim frames
    batch1_<action>_<view>.gif               one view, 6x, played at the simulation's timing
    batch1_<action>_all.gif                  the four views side by side, 4x
    batch1_onion.png                         onion skins of the transitions (guard -> hit / deflect
                                             -> back -> guard; idle -> heal in -> hold; out -> idle)
    batch1_head_check.png                    above the neck, every frame (yellow = background the
                                             plume encloses; not in the automatic checks)
    batch1_guard_vs_heal.png                 the two outlines on top of each other, per view, held
                                             and walking, with the measured difference
    batch1_motion.md                         per-part motion table (animation-review §5)
"""
import math
import os
import sys

from PIL import Image, ImageDraw

import sprites as A
import pose_rig as PR
import batch1 as B
from export_poses import font, up, stack, hrow, label, enclosed_mask, FLOOR, SHADOW, BG

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch1')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
FW, FH = A.FW, A.FH


def image(px):
    return PR.image(px, 'small')


def cell(px, k, floor=True):
    im = Image.new('RGBA', (FW, FH), FLOOR if floor else (96, 112, 96, 255))
    if floor:
        ImageDraw.Draw(im).ellipse((A.CX - 14, A.GROUND - 2, A.CX + 14, A.GROUND + 3), fill=SHADOW)
    im.alpha_composite(image(px))
    return up(im, k)


def spans(action):
    """(name, first sim frame, last sim frame) of each frame, in order."""
    out, t = [], 0
    for f in B.frames(action, 'south'):
        out.append((f.name, t, t + f.dur - 1))
        t += f.dur
    return out


# ------------------------------------------------------------------ sheets
def write_sheet(action):
    cols = len(B.ACTIONS[action])
    sheet = Image.new('RGBA', (FW * cols, FH * len(B.VIEWS)), (0, 0, 0, 0))
    for r, v in enumerate(B.VIEWS):
        for c, f in enumerate(B.frames(action, v)):
            sheet.alpha_composite(image(f.px), (c * FW, r * FH))
    path = os.path.join(SHEETS, f'knight_{action}.png')
    sheet.save(path)
    return path, sheet.size


def sequence(action, k):
    sp = spans(action)
    cw = FW * k
    # idle and heal play straight through: their sim-frame ranges; the guard's hit and deflect
    # come whenever the boss strikes, the walks loop at their speed: how long each frame shows
    timeline = action in ('idle', 'heal')
    durs = {f.name: f.dur for f in B.frames(action, 'south')}
    head = [label('', 70, 14, 34)] + [label(f'{n}  {a}–{b}' if timeline else f'{n}  {durs[n]} 幀', cw, 14 if k < 5 else 18, 34)
                                      for n, a, b in sp]
    note = '數字是模擬幀（60Hz）的範圍' if timeline else '每張停幾個模擬幀（60Hz）' + ('；受力、彈返在 Boss 打到時出現' if action == 'guard' else '；前進的播放速度 格擋 1.0 倍、治療 0.6 倍')
    rows = [label(f'{B.TITLES[action]}（{k} 倍；{note}）', cw * 4, 18 if k < 5 else 24, 34), hrow(head)]
    for v in B.VIEWS:
        rows.append(hrow([label(VIEW_ZH[v], 70, 16, FH * k)] + [cell(f.px, k) for f in B.frames(action, v)]))
    return stack(rows, 4)


# ------------------------------------------------------------------ gifs
def ms(sim):
    return int(round(sim * 1000 / 60 / 10)) * 10


def script(action):
    """(frame index, sim frames) to play: a short scene that shows the action in context."""
    fr = B.frames(action, 'south')
    idx = {f.name: i for i, f in enumerate(fr)}
    if action == 'idle':
        return [(i, fr[i].dur) for i in range(4)] * 2
    if action == 'guard':
        hold = [(idx[f'hold {i}'], 12) for i in range(1, 5)]
        return (hold * 2 + [(idx['hit'], 6)] + hold + [(idx['deflect'], 11), (idx['back 1'], 2), (idx['back 2'], 2)] + hold)
    if action == 'heal':
        return [(i, fr[i].dur) for i in range(len(fr))]
    # batch 3 decision 8: backward and the sidestep to the right are their own frames (the
    # forward / left frames played in reverse made the head and the cloth lead)
    cyc = lambda k, n: [(idx[f'{k} {i}'], fr[idx[f'{k} {i}']].dur) for i in range(1, n + 1)]
    return (cyc('fwd', B.N_FWD) * 2 + cyc('back', B.N_FWD) * 2 +
            cyc('side', B.N_SIDE) * 3 + cyc('rside', B.N_SIDE) * 3)


def idle_lead(n_sim):
    """The idle's first frame for n_sim frames (before / after the heal, the guard)."""
    return [('idle', 0, n_sim)]


def save_gif(images, durations, path, colors=128):
    stack_ = Image.new('RGB', (images[0].width, images[0].height * len(images)))
    for i, g in enumerate(images):
        stack_.paste(g, (0, i * g.height))
    pal = stack_.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, disposal=1)


def scene(action, view):
    """[(pixels, sim frames)] for the gif: the guard and the heal start and end in the idle."""
    fr = B.frames(action, view)
    idle = B.frames('idle', view)
    seq = [(fr[i].px, d) for i, d in script(action)]
    if action in ('guard', 'heal'):
        seq = [(idle[0].px, 24)] + seq + [(idle[0].px, 24)]
    return seq


def write_gifs(action):
    names = []
    for v in B.VIEWS:
        seq = scene(action, v)
        imgs = [cell(px, 6).convert('RGB') for px, _ in seq]
        p = os.path.join(OUT, f'batch1_{action}_{v}.gif')
        save_gif(imgs, [ms(d) for _, d in seq], p, 96)
        names.append(p)
    seqs = {v: scene(action, v) for v in B.VIEWS}
    imgs = []
    for i in range(len(seqs['south'])):
        row = Image.new('RGBA', (FW * 4, FH), FLOOR)
        for c, v in enumerate(B.VIEWS):
            row.alpha_composite(cell(seqs[v][i][0], 1), (c * FW, 0))
        imgs.append(up(row, 4).convert('RGB'))
    p = os.path.join(OUT, f'batch1_{action}_all.gif')
    save_gif(imgs, [ms(d) for _, d in seqs['south']], p, 128)
    names.append(p)
    return names


# ------------------------------------------------------------------ review images
def onion(frames_px, k=6):
    """Consecutive frames laid over each other: the previous one tinted blue, the next red,
    the current on top in its colours at 60 %."""
    im = Image.new('RGBA', (FW, FH), (240, 236, 228, 255))
    tints = [(60, 120, 255), (230, 60, 60)]
    for px, tint in zip(frames_px[:2], tints):
        lay = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
        for (x, y) in px:
            if 0 <= x < FW and 0 <= y < FH:
                lay.putpixel((x, y), tint + (110,))
        im.alpha_composite(lay)
    return up(im, k)


def onion_sheet():
    rows = [label('洋蔥皮：藍＝前一張、紅＝後一張，重疊處偏紫（6 倍）', 1800, 22, 34)]
    pairs = [('guard', 'hold 1', 'guard', 'hit'), ('guard', 'hit', 'guard', 'hold 1'),
             ('guard', 'hold 1', 'guard', 'deflect'), ('guard', 'deflect', 'guard', 'back 1'),
             ('guard', 'back 1', 'guard', 'back 2'), ('guard', 'back 2', 'guard', 'hold 1'),
             ('idle', 'idle 1', 'heal', 'in 1'), ('heal', 'in 1', 'heal', 'in 2'), ('heal', 'in 2', 'heal', 'hold 1'),
             ('heal', 'hold 4', 'heal', 'out 1'), ('heal', 'out 1', 'heal', 'out 2'), ('heal', 'out 2', 'idle', 'idle 1')]
    name = lambda act, fr: fr if act == 'guard' else f'{act} {fr}'
    head = [label('', 70, 14, 50)] + [label(f'{name(p[0], p[1])}\n→ {name(p[2], p[3])}', FW * 6, 16, 50)
                                      for p in pairs]
    rows.append(hrow(head))
    for v in B.VIEWS:
        cells = [label(VIEW_ZH[v], 70, 16, FH * 6)]
        for a1, n1, a2, n2 in pairs:
            f1 = next(f for f in B.frames(a1, v) if f.name == n1)
            f2 = next(f for f in B.frames(a2, v) if f.name == n2)
            cells.append(onion([f1.px, f2.px]))
        rows.append(hrow(cells))
    return stack(rows, 4)


def head_check(k=6):
    rows = [label('頸部以上：第 1 批每一幀（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區）', 1800, 22, 34)]
    for action in B.ACTIONS:
        for v in B.VIEWS:
            cells = [label(f'{action}\n{VIEW_ZH[v]}', 110, 14, 60)]
            for f in B.frames(action, v):
                helm = [k_ for k_, n in f.trace.items() if n == 'helmet']
                cut = max(y for _, y in helm) + 2
                x0 = max(0, min(x for x, _ in helm) - 12)
                x1 = min(FW, max(x for x, _ in helm) + 14)
                y0 = max(0, min(y for (x, y) in f.px if x0 <= x < x1) - 1)
                tile = Image.new('RGBA', (FW, FH), (96, 112, 96, 255))
                tile.alpha_composite(image(f.px))
                for (x, y) in enclosed_mask(f.px, FW, FH):
                    if y < cut:
                        tile.putpixel((x, y), (255, 230, 0, 255))
                cells.append(up(tile.crop((x0, y0, x1, cut)), k))
            rows.append(hrow(cells))
    return stack(rows, 4)


def silhouette_px(f):
    return {q for q in f.px if f.trace.get(q, '') not in B.CLOTH}


def guard_vs_heal(k=6):
    import checks as C
    rows = [label('格擋（藍）對治療（橘）的輪廓，白＝重疊；不含披風、羽飾、圍巾。第 1 排站著，第 2–4 排移動中（前進第 1、3 幀，側移第 2 幀）', 2000, 22, 34)]
    pairs = [('guard', 'hold 1', 'heal', 'hold 1'), ('guard_walk', 'fwd 1', 'heal_walk', 'fwd 1'),
             ('guard_walk', 'fwd 3', 'heal_walk', 'fwd 3'), ('guard_walk', 'side 2', 'heal_walk', 'side 2')]
    for a1, n1, a2, n2 in pairs:
        cells = [label(f'{n1}', 110, 16, FH * k)]
        for v in B.VIEWS:
            g = next(f for f in B.frames(a1, v) if f.name == n1)
            h = next(f for f in B.frames(a2, v) if f.name == n2)
            sg, sh = silhouette_px(g), silhouette_px(h)
            share = C.outline_shift_share(sg, sh)
            im = Image.new('RGBA', (FW, FH), (40, 40, 44, 255))
            for q in sg | sh:
                if 0 <= q[0] < FW and 0 <= q[1] < FH:
                    c = (235, 235, 235, 255) if q in sg and q in sh else ((70, 150, 255, 255) if q in sg else (255, 120, 50, 255))
                    im.putpixel(q, c)
            big = up(im, k)
            ImageDraw.Draw(big).text((6, 4), f'{VIEW_ZH[v]} {round(100 * share)} %', fill=(255, 255, 0, 255), font=font(22))
            cells.append(big)
        rows.append(hrow(cells))
    return stack(rows, 4)


# ------------------------------------------------------------------ motion table
def metrics(f):
    """Where the parts are in one frame (small-frame pixels), from the trace."""
    by = {}
    for q, n in f.trace.items():
        if q in f.px:
            by.setdefault(n, []).append(q)

    def cen(n):
        pts = by.get(n)
        if not pts:
            return None
        return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
    m = {}
    helm = by.get('helmet', [])
    m['helmet_top'] = min(y for _, y in helm) if helm else None
    m['head'] = cen('helmet')
    m['torso'] = cen('torso')
    m['fist_R'], m['fist_L'] = cen('fist_R'), cen('fist_L')
    legs = [q for n, pts in by.items() if n.startswith('leg') for q in pts]
    feet = {}
    for n in ('leg_R', 'leg_L'):
        xs = [x for (x, y) in by.get(n, []) if y >= A.GROUND - 2]
        if xs:
            feet[n[-1]] = (min(xs) + max(xs)) / 2
    m['feet'] = feet
    m['feet_low'] = {n[-1]: max(y for _, y in by[n]) for n in ('leg_R', 'leg_L') if n in by}
    sw = by.get('sword', [])
    blade = [q for q in f.debug.get('blade', set())] if f.debug.get('blade') else []
    ref = m['fist_R'] or m['torso']
    if blade and ref:
        m['tip'] = max(blade, key=lambda q: (q[0] - ref[0]) ** 2 + (q[1] - ref[1]) ** 2)
    elif sw and ref:
        m['tip'] = max(sw, key=lambda q: (q[0] - ref[0]) ** 2 + (q[1] - ref[1]) ** 2)
    else:
        m['tip'] = None
    hc = m['head']
    for n in ('plume', 'cape'):
        pts = by.get(n, [])
        m[n + '_tip'] = max(pts, key=lambda q: (q[0] - hc[0]) ** 2 + (q[1] - hc[1]) ** 2) if pts and hc else None
    m['pelvis'] = f.debug.get('pelvis')
    return m


def fmt(p):
    if p is None:
        return '–'
    if isinstance(p, (int, float)):
        return f'{p:.1f}' if isinstance(p, float) else str(p)
    return f'({p[0]:.1f}, {p[1]:.1f})' if isinstance(p[0], float) else f'({p[0]}, {p[1]})'


def motion_table():
    lines = ['# 第 1 批逐部件動作表', '',
             '由 `tools/sprite_rig/export_batch1.py` 產生（animation-review §5）。座標是 56×56 畫格的像素，y 往下為正，地面是第 53 列。',
             '「頭盔頂」「骨盆」的變化對照「頭晚一拍」：骨盆先動、頭盔頂下一張才跟上。布料末端是離頭盔中心最遠的那一點。', '']
    for action in B.ACTIONS:
        for v in B.VIEWS:
            fr = B.frames(action, v)
            lines += [f'## {B.TITLES[action]}・{VIEW_ZH[v]}', '',
                      '| 幀 | 模擬幀 | 前傾° | 骨盆 y | 頭盔頂 y | 右拳 | 左拳 | 劍尖 | 兩腳中心 x | 羽飾末端 | 披風末端 |',
                      '|---|---|---|---|---|---|---|---|---|---|---|']
            t = 0
            for f in fr:
                m = metrics(f)
                lean = f.pose.get('lean', 0) if f.pose else 0
                pel = f'{m["pelvis"][1]:.1f}' if m['pelvis'] else f'+{f.debug.get("body", 0)}'
                feet = ' / '.join(f'{k} {x:.1f}' for k, x in sorted(m['feet'].items())) or '（不動）'
                lines.append(f'| {f.name} | {t}–{t + f.dur - 1} | {lean:.0f} | {pel} | {fmt(m["helmet_top"])} | '
                             f'{fmt(m["fist_R"])} | {fmt(m["fist_L"])} | {fmt(m["tip"])} | {feet} | '
                             f'{fmt(m["plume_tip"])} | {fmt(m["cape_tip"])} |')
                t += f.dur
            lines.append('')
    return '\n'.join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SHEETS, exist_ok=True)
    wrote = []
    for action in B.ACTIONS:
        path, size = write_sheet(action)
        wrote.append(f'{os.path.relpath(path, ROOT)} {size}')
        for k in (3, 6):
            p = os.path.join(OUT, f'batch1_{action}_{k}x.png')
            sequence(action, k).save(p)
        write_gifs(action)
    onion_sheet().save(os.path.join(OUT, 'batch1_onion.png'))
    head_check().save(os.path.join(OUT, 'batch1_head_check.png'))
    guard_vs_heal().save(os.path.join(OUT, 'batch1_guard_vs_heal.png'))
    with open(os.path.join(OUT, 'batch1_motion.md'), 'w', encoding='utf-8') as fh:
        fh.write(motion_table())
    print('\n'.join(wrote))
    print('previews in', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    sys.exit(main())
