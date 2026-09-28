"""Batch 2 (docs/art-progress.md): light attacks 1-4.

    python3 tools/sprite_rig/export_batch2.py

Writes (previews for review; nothing is wired into the game):
  assets/sprites/player/knight_attack1.png, knight_attack2.png, knight_attack4.png
      sprite sheets, rows S / E / N / W, 88 x 72 cells, foot anchor (44, 61); columns as in
      batch2.FRAMES (stage 3 plays attack1's columns 2-7 with its own timing)
  docs/art-preview/player/batch2/
    batch2_stage<n>_3x.png / _6x.png   every frame x four views, labelled with its sim frames
                                       and the program's advance when it shows
    batch2_<scene>_<view>.gif, batch2_combo_all.gif
                                       played at the simulation's timing, the picture moving
                                       with the program's advance when the frame changes
                                       (decision 2): combo = 1-2-3-4 chained at the earliest
                                       frame; s1, s12, s123 = stopping after that stage
    batch2_concept.png                 the east view against the concept's C1-C4, D2, D3 (same
                                       height, the thumbnail's outline laid over; overlap %)
    batch2_onion.png                   the swing steps and the chains, onion-skinned
    batch2_head_check.png              above the neck, every frame
"""
import os
import sys

from PIL import Image, ImageDraw

import sprites as A
import pose_rig as PR
import batch1 as B1
import batch2 as B2
import export_poses as E
from export_poses import up, stack, hrow, label, FLOOR, SHADOW, BG

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch2')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
W_, H_, CX, GY = PR.CANVAS['large']


def cell(px, k):
    return E.cell(px, 'large', k)


def write_sheet(stage):
    fr = {v: B2.frames(stage, v) for v in B2.VIEWS}
    cols = len(fr['south'])
    sheet = Image.new('RGBA', (W_ * cols, H_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(B2.VIEWS):
        for c, f in enumerate(fr[v]):
            sheet.alpha_composite(PR.image(f.px, 'large'), (c * W_, r * H_))
    path = os.path.join(SHEETS, f'knight_{B2.SHEETS[stage]}.png')
    sheet.save(path)
    return path, sheet.size


def sequence(stage, k):
    cw = W_ * k
    fr0 = B2.frames(stage, 'south')
    head = [label('', 70, 14, 40)] + [label(f'{f.name}\n{f.first}–{f.last}　前進 {f.adv:.1f}px', cw, 14 if k < 5 else 18, 40)
                                      for f in fr0]
    rows = [label(f'{B2.TITLES[stage]}（{k} 倍；模擬幀 60Hz；「前進」是這張出現時程式已前進的距離，畫面在換圖時跟上）',
                  cw * 5, 18 if k < 5 else 24, 34), hrow(head)]
    for v in B2.VIEWS:
        rows.append(hrow([label(VIEW_ZH[v], 70, 16, H_ * k)] + [cell(f.px, k) for f in B2.frames(stage, v)]))
    return stack(rows, 4)


# ------------------------------------------------------------------ scenes (gifs)
def timeline(view, stages):
    """[(pixels, 'small' or 'large', screen offset (dx, dy), sim frames)]: the idle, the
    stages chained at their earliest frame (the last one plays out), the idle again."""
    fx, fy = B2.FWD_SCREEN[view]
    idle = B1.frames('idle', view)[0].px
    out = [(idle, 'small', (0, 0), 24)]
    base = 0.0
    for n, st in enumerate(stages):
        a0, act, total, adv = B2.ATTACK[st]
        chain = a0 + act if n < len(stages) - 1 else total
        for f in B2.frames(st, view):
            if f.first >= chain:
                break
            show = min(f.last, chain - 1) - f.first + 1
            d = base + f.adv
            out.append((f.px, 'large', (fx * d, fy * d), show))
        base += adv
    out.append((idle, 'small', (fx * base, fy * base), 24))
    return out


def scene_images(view, stages, k=4):
    tl = timeline(view, stages)
    xs = [o[0] for _, _, o, _ in tl]
    ys = [o[1] for _, _, o, _ in tl]
    pad = 8
    Wc = W_ + round(max(xs) - min(xs)) + 2 * pad
    Hc = H_ + round(max(ys) - min(ys)) + 2 * pad
    ox0, oy0 = pad - round(min(xs)), pad - round(min(ys))
    imgs, durs = [], []
    for px, canvas, (dx, dy), n in tl:
        im = Image.new('RGBA', (Wc, Hc), FLOOR)
        ax, ay = ox0 + CX + round(dx), oy0 + GY + round(dy)          # where the foot anchor is
        ImageDraw.Draw(im).ellipse((ax - 14, ay - 2, ax + 14, ay + 3), fill=SHADOW)
        cw, ch, ccx, cgy = PR.CANVAS[canvas]
        im.alpha_composite(PR.image(px, canvas), (ax - ccx, ay - cgy))
        imgs.append(up(im, k).convert('RGB'))
        durs.append(int(round(n * 1000 / 60 / 10)) * 10)
    return imgs, durs


def save_gif(images, durations, path, colors=128):
    stack_ = Image.new('RGB', (images[0].width, images[0].height * len(images)))
    for i, g in enumerate(images):
        stack_.paste(g, (0, i * g.height))
    pal = stack_.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, disposal=1)


SCENES = {'combo': (1, 2, 3, 4), 's1': (1,), 's12': (1, 2), 's123': (1, 2, 3)}


def write_gifs():
    for name, stages in SCENES.items():
        for v in B2.VIEWS:
            imgs, durs = scene_images(v, stages, 5)
            save_gif(imgs, durs, os.path.join(OUT, f'batch2_{name}_{v}.gif'), 96)
    per = {v: scene_images(v, SCENES['combo'], 1) for v in B2.VIEWS}
    n = len(per['south'][0])
    imgs = []
    for i in range(n):
        tiles = [per[v][0][i] for v in B2.VIEWS]
        row = Image.new('RGB', (sum(t.width for t in tiles) + 6 * 3, max(t.height for t in tiles)), (30, 30, 34))
        x = 0
        for t in tiles:
            row.paste(t, (x, 0))
            x += t.width + 6
        imgs.append(row.resize((row.width * 3, row.height * 3), Image.NEAREST))
    save_gif(imgs, per['south'][1], os.path.join(OUT, 'batch2_combo_all.gif'), 128)


# ------------------------------------------------------------------ review images
CONCEPT_FRAMES = [('C1', 1, 0), ('C2', 1, 1), ('C3', 1, 3), ('C4', 1, 6), ('D2', 4, 3), ('D3', 4, 4)]


def concept_sheet(k=4):
    rows = [label('設計圖對照（朝右）：左＝設計圖小圖（縮成和成品同高），右＝成品疊上小圖輪廓（洋紅），數字是兩個輪廓的重疊率', 1800, 20, 34)]
    for ref, st, i in CONCEPT_FRAMES:
        f = B2.frames(st, 'east')[i]
        th = E.thumb(ref, k, f'b2_{ref}', f.pose, 'large')
        tc = Image.new('RGBA', (E.TW, H_ * k), BG)
        if th is not None:
            tc.alpha_composite(th, (max(0, (E.TW - th.width) // 2), max(0, H_ * k - th.height)))
        ov, match = E.overlay_cell(f'b2_{ref}', f.pose, 'large', ref, k)
        rows.append(hrow([label(f'{ref}\n第 {st} 段 {f.name}\n重疊 {round(100 * match)}%', 170, 16, H_ * k), tc, ov]))
    return stack(rows, 6)


def onion(a, b, k=6):
    """Two consecutive frames where they show on screen: the earlier blue, the later red."""
    im = Image.new('RGBA', (W_ + 20, H_), (240, 236, 228, 255))
    for f, tint, off in ((a[0], (60, 120, 255), a[1]), (b[0], (230, 60, 60), b[1])):
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
        for (x, y) in f:
            q = (x + 10 + round(off[0]), y + round(off[1]))
            if 0 <= q[0] < im.width and 0 <= q[1] < im.height:
                lay.putpixel(q, tint + (110,))
        im.alpha_composite(lay)
    return up(im, k)


def onion_sheet():
    rows = [label('洋蔥皮（畫面上的位置，含換圖時程式的前進）：藍＝前一張、紅＝後一張', 2400, 22, 34)]
    pairs = [(1, 0, 1, 1), (1, 1, 1, 2), (1, 2, 1, 3), (1, 3, 1, 4), (2, 1, 2, 2), (2, 2, 2, 3),
             (4, 1, 4, 2), (4, 2, 4, 3), (4, 3, 4, 4), (4, 4, 4, 5)]
    head = [label('', 70, 14, 40)] + [label(f'{s1}段 {B2.FRAMES[s1][i1][0]}\n→ {B2.FRAMES[s2][i2][0]}', (W_ + 20) * 6, 16, 40)
                                      for s1, i1, s2, i2 in pairs]
    rows.append(hrow(head))
    for v in B2.VIEWS:
        fx, fy = B2.FWD_SCREEN[v]
        cells = [label(VIEW_ZH[v], 70, 16, H_ * 6)]
        for s1, i1, s2, i2 in pairs:
            a, b = B2.frames(s1, v)[i1], B2.frames(s2, v)[i2]
            base = min(a.adv, b.adv)
            cells.append(onion((a.px, (fx * (a.adv - base), fy * (a.adv - base))),
                               (b.px, (fx * (b.adv - base), fy * (b.adv - base)))))
        rows.append(hrow(cells))
    return stack(rows, 4)


def head_check(k=5):
    rows = [label('頸部以上：第 2 批每一幀（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區）', 1800, 22, 34)]
    for st in (1, 2, 4):
        for v in B2.VIEWS:
            cells = [label(f'第 {st} 段\n{VIEW_ZH[v]}', 90, 14, 60)]
            for f in B2.frames(st, v):
                helm = [q for q, n in f.trace.items() if n == 'helmet']
                cut = max(y for _, y in helm) + 2
                x0 = max(0, min(x for x, _ in helm) - 12)
                x1 = min(W_, max(x for x, _ in helm) + 14)
                y0 = max(0, min(y for (x, y) in f.px if x0 <= x < x1) - 1)
                tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
                tile.alpha_composite(PR.image(f.px, 'large'))
                for (x, y) in E.enclosed_mask(f.px, W_, H_):
                    if y < cut:
                        tile.putpixel((x, y), (255, 230, 0, 255))
                cells.append(up(tile.crop((x0, y0, x1, cut)), k))
            rows.append(hrow(cells))
    return stack(rows, 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    wrote = []
    for st in (1, 2, 4):
        path, size = write_sheet(st)
        wrote.append(f'{os.path.relpath(path, ROOT)} {size}')
    for st in (1, 2, 3, 4):
        for k in (3, 6):
            sequence(st, k).save(os.path.join(OUT, f'batch2_stage{st}_{k}x.png'))
    write_gifs()
    concept_sheet().save(os.path.join(OUT, 'batch2_concept.png'))
    onion_sheet().save(os.path.join(OUT, 'batch2_onion.png'))
    head_check().save(os.path.join(OUT, 'batch2_head_check.png'))
    print('\n'.join(wrote))
    print('previews in', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    sys.exit(main())
