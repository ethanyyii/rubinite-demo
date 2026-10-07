"""Previews of the execution (export_execute.py calls main): animation-review §5's ways of looking.

- execute_<view>_6x_<n>.png   every frame, 6x, with its name, first sim frame, hold and height
- execute_<view>.gif          the game's timing (60 fps -> 20 ms a frame in the GIF, 0.83x), the shadow on
                              the floor and the floor moved the way the game moves the knight (run in, leap
                              in, jump back); the plunge held 15 frames (the hitstop)
- execute_four.gif            the four views side by side
- with_boss_<case>.gif / .png the knight over the kneeling Boss (boss_executed.png, the same beats) as the game
                              draws them: front (the knight's back to us), from his side, from behind (the
                              knight hidden: the game's blue silhouette)
- legs_<view>.png             the legs alone with hip / knee / ankle lines, 8x
- hands.png                   the fists, the grip and the blade, 6x, four views side by side, key frames
- head_check.png              neck up, 6x (the plume against the helmet)
"""
import os

from PIL import Image, ImageDraw

import pose_rig as PR
import execute as E
from export_poses import up, stack, hrow, label, FLOOR, SHADOW, BG, VIEW_ZH

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
BOSS_SHEET = os.path.join(ROOT, 'assets', 'sprites', 'boss', 'boss_executed.png')
W_, H_, AX, AY = PR.CANVAS[E.CANVAS]
HITSTOP = 15
TILE = 16
FLOOR2 = (214, 206, 190, 255)


def framed(f, k, box=None, floor=True):
    im = Image.new('RGBA', (W_, H_), FLOOR if floor else (0, 0, 0, 0))
    if floor:
        ImageDraw.Draw(im).ellipse((AX - 11, AY - 2, AX + 11, AY + 3), fill=SHADOW)
    im.alpha_composite(PR.image(f.px, E.CANVAS))
    if box:
        im = im.crop(box)
    return up(im, k)


def frame_sheets(out, k=6, per=12):
    paths = []
    for v in E.VIEWS:
        fr = E.frames(v)
        for c in range(0, len(fr), per):
            part = fr[c:c + per]
            cells = []
            for f in part:
                y1 = AY - f.air + 10
                img = framed(f, k, (6, max(0, y1 - 66), W_ - 6, y1))
                cells.append(stack([label(f'{f.name}  @{f.start}  {f.dur} 幀  離地 {f.air}', img.width, 16, 22), img], 2))
            sheet = stack([label(f'處決（躍起下刺）{VIEW_ZH[v]}  第 {c + 1}–{c + len(part)} 張（{k} 倍；每張以腳所在的高度置中）',
                                 1600, 20, 30), hrow(cells)], 4)
            p = os.path.join(out, f'execute_{v}_6x_{c // per + 1}.png')
            sheet.save(p)
            paths.append(p)
    return paths


def ground_path(f):
    """The knight's distance from the Boss's centre at sim frame f (player_sim._tick_execute, from 70)."""
    if f <= E.LEAP_AT:
        return 70 + (45 - 70) * f / E.LEAP_AT
    if f <= E.HIT_AT:
        return 45 + (E.PERCH - 45) * (f - E.LEAP_AT) / (E.HIT_AT - E.LEAP_AT)
    if f <= E.KICK_AT:
        return E.PERCH
    if f <= E.LAND_AT:
        return E.PERCH + (72 - E.PERCH) * (f - E.KICK_AT) / (E.LAND_AT - E.KICK_AT)
    return 72


def timeline(view):
    """[(frame index, sim frame)] one per shown frame, with the hitstop."""
    fr = E.frames(view)
    out = []
    for i, f in enumerate(fr):
        for t in range(f.dur):
            out.append((i, f.start + t))
        if f.start == E.HIT_AT:
            out[-f.dur:-f.dur] = [(i, f.start)] * HITSTOP
    return out


FWD = {'south': (0, 1), 'east': (1, 0), 'north': (0, -1), 'west': (-1, 0)}


def gif_frames(view, k=2, size=(200, 210)):
    """The knight alone on a floor that moves the way the game moves him (toward the Boss = his facing)."""
    fr = E.frames(view)
    fx, fy = FWD[view]
    w, h = size
    imgs = []
    for i, t in timeline(view):
        f = fr[i]
        im = Image.new('RGBA', (w, h), FLOOR)
        d = ImageDraw.Draw(im)
        # the knight stays put; the floor slides under him by how far the game has carried him
        moved = 70 - ground_path(t)
        ox, oy = -fx * moved, -fy * moved
        for y in range(-TILE, h + TILE, TILE):
            for x in range(-TILE, w + TILE, TILE):
                if ((x + int(ox) // TILE * TILE) // TILE + (y + int(oy) // TILE * TILE) // TILE) % 2:
                    d.rectangle((x - int(ox) % TILE, y - int(oy) % TILE, x - int(ox) % TILE + TILE - 1, y - int(oy) % TILE + TILE - 1), fill=FLOOR2)
        gx, gy = w // 2, h - 30
        r = 11 * (1.0 - 0.4 * min(1.0, f.air / 80.0))
        d.ellipse((gx - r, gy - 2, gx + r, gy + 3), fill=(150, 142, 126, 255))
        im.alpha_composite(PR.image(f.px, E.CANVAS), (gx - AX, gy - AY))
        imgs.append(up(im, k).convert('RGB'))
    return imgs


def save_gif(images, path, ms=20):
    pal = images[len(images) // 2].quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, disposal=1)


# ------------------------------------------------------------------ with the Boss
BW, BH, BAX, BAY = 384, 336, 192, 272
BOSS_ROWS = {'down': 0, 'right': 1, 'up': 2, 'left': 3}
CASES = {
    # name: knight view, Boss row, screen direction Boss -> knight, caption
    'front': ('north', 'down', (0, 1), '從 Boss 正面（主角背對鏡頭）'),
    'side': ('east', 'left', (-1, 0), '從側面（Boss 面向主角）'),
    'side_other': ('west', 'right', (1, 0), '從另一側（Boss 面向主角）'),
    'side_shoulder': ('east', 'down', (-1, 0), '從側面（Boss 面向下方：刺在他的肩上）'),
    'back': ('south', 'up', (0, -1), '從 Boss 背後（主角被擋住：藍色剪影）'),
}


def boss_holds():
    """The Boss's EXECUTED clip as the game plays it (boss_frames.json from tools/boss_rig/export_game.py;
    the two tools both have a module called rig, so it is not imported from there)."""
    import json
    with open(os.path.join(ROOT, 'assets', 'sprites', 'boss_game', 'boss_frames.json'), encoding='utf-8') as fh:
        return json.load(fh)['clips']['executed']['holds']


def boss_col(t, holds):
    acc = 0
    for i, h in enumerate(holds):
        acc += h
        if t < acc:
            return i
    return len(holds) - 1


def silhouette(img):
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    src, dst = img.load(), out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if src[x, y][3]:
                dst[x, y] = (128, 168, 245, 128)
    return out


def with_boss(case, k=2, every=1):
    view, brow, (dx, dy), _ = CASES[case]
    boss = Image.open(BOSS_SHEET).convert('RGBA')
    holds = boss_holds()
    fr = E.frames(view)
    W, H = 260, 250
    gx, gy = 130, 160
    imgs = []
    tl = timeline(view)
    for n, (i, t) in enumerate(tl):
        if n % every:
            continue
        f = fr[i]
        im = Image.new('RGBA', (W, H), (92, 96, 84, 255))
        d = ImageDraw.Draw(im)
        bc = boss_col(t, holds)
        b = boss.crop((bc * BW, BOSS_ROWS[brow] * BH, (bc + 1) * BW, (BOSS_ROWS[brow] + 1) * BH))
        dist = ground_path(t)
        kx, ky = gx + dx * dist, gy + dy * dist
        d.ellipse((gx - 46, gy - 8, gx + 46, gy + 8), fill=(70, 72, 64, 255))
        r = 11 * (1.0 - 0.4 * min(1.0, f.air / 80.0))
        d.ellipse((kx - r, ky - 2, kx + r, ky + 3), fill=(70, 72, 64, 255))
        knight = PR.image(f.px, E.CANVAS)
        kpos = (int(round(kx)) - AX, int(round(ky)) - AY)
        front = ky > gy or (dy == 0 and E.HIT_AT - 24 < t < E.LAND_AT) or (dy == 0 and ky >= gy)
        if front:
            im.alpha_composite(b, (gx - BAX, gy - BAY))
            im.alpha_composite(knight, kpos)
        else:
            im.alpha_composite(knight, kpos)
            im.alpha_composite(b, (gx - BAX, gy - BAY))
            im.alpha_composite(silhouette(knight), kpos)
        imgs.append(up(im, k).convert('RGB'))
    return imgs


def legs_sheet(view, k=8):
    fr = E.frames(view)
    cells = []
    for f in fr:
        im = Image.new('RGBA', (W_, H_), FLOOR)
        for n in ('leg_R', 'leg_L'):
            for q, c in f.pieces_raw.get(n, {}).items():
                if 0 <= q[0] < W_ and 0 <= q[1] < H_:
                    im.putpixel(q, c)
        y1 = AY - f.air + 6
        im = up(im.crop((14, max(0, y1 - 30), W_ - 14, y1)), k)
        d = ImageDraw.Draw(im)
        oy = max(0, y1 - 30)
        for _, (hp, kn, an) in (f.debug.get('legs') or {}).items():
            pts = [((p[0] - 14) * k, (p[1] - oy) * k) for p in (hp, kn, an)]
            d.line(pts, fill=(255, 0, 160, 255), width=2)
            for p in pts:
                d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), outline=(255, 0, 160, 255))
        cells.append(stack([label(f'{f.name} 離地 {f.air}', im.width, 14, 20), im], 2))
    rows = [label(f'腿單獨畫出來（髖－膝－踝），{VIEW_ZH[view]}，{k} 倍', 1200, 20, 30)]
    for c in range(0, len(cells), 12):
        rows.append(hrow(cells[c:c + 12]))
    return stack(rows, 4)


HAND_FRAMES = ('蹲深', '最高 2', '插下去', '掛 1', '擰 1', '轉劍 1', '掛 3', '轉劍 2', '蹬開', '後跳 2', '落地')


def hands_sheet(k=6):
    rows = [label('握劍的雙手、劍柄、劍（每一列一張，四個方向並排，6 倍；只畫手臂、拳頭、劍）', 1600, 20, 30)]
    for name in HAND_FRAMES:
        cells = []
        for v in E.VIEWS:
            f = next(x for x in E.frames(v) if x.name == name)
            full = framed(f, 1, floor=False)
            arm = Image.new('RGBA', (W_, H_), FLOOR)
            dim = full.copy()
            dim.putalpha(70)
            arm.alpha_composite(dim)
            for q, n in f.trace.items():
                if n.startswith(('upper_', 'fore_', 'fist_', 'sword')) and q in f.px and 0 <= q[0] < W_ and 0 <= q[1] < H_:
                    arm.putpixel(q, f.px[q])
            hy = int(f.debug['hands']['R'][1])
            cells.append(up(arm.crop((14, max(0, hy - 26), W_ - 14, min(H_, hy + 22))), k))
        rows.append(hrow([label(name, 90, 16, cells[0].height)] + cells))
    return stack(rows, 4)


def head_check(k=6):
    rows = [label('頸部以上（羽飾碰到頭盔、圍出背景：目視），6 倍', 1600, 20, 30)]
    for v in E.VIEWS:
        cells = []
        for f in E.frames(v)[::3]:
            y0 = AY - f.air - 54
            cells.append(up(framed(f, 1).crop((20, max(0, y0), W_ - 20, max(0, y0) + 26)), k // 2 + 1))
        rows.append(hrow([label(VIEW_ZH[v], 60, 16, cells[0].height)] + cells, 2))
    return stack(rows, 4)


def main(out):
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(('.png', '.gif')):
            os.remove(os.path.join(out, f))
    for p in frame_sheets(out):
        print('wrote', os.path.relpath(p, ROOT))
    four = []
    for v in E.VIEWS:
        g = gif_frames(v)
        save_gif(g, os.path.join(out, f'execute_{v}.gif'))
        four.append(g)
        legs_sheet(v).save(os.path.join(out, f'legs_{v}.png'))
    joined = []
    for frames in zip(*four):
        w = sum(x.width for x in frames)
        im = Image.new('RGB', (w, frames[0].height))
        x = 0
        for g in frames:
            im.paste(g, (x, 0))
            x += g.width
        joined.append(im.resize((im.width // 2, im.height // 2), Image.NEAREST))
    save_gif(joined, os.path.join(out, 'execute_four.gif'))
    for case in CASES:
        imgs = with_boss(case)
        save_gif(imgs, os.path.join(out, f'with_boss_{case}.gif'))
        # a strip of the beats
        tl = timeline(CASES[case][0])
        picks = [n for n, (i, t) in enumerate(tl) if t in (10, 23, 36, 42, 48, 58, 75, 102, 118, 121, 130, 150, 179)]
        seen, strip = set(), []
        for n in picks:
            t = tl[n][1]
            if t in seen:
                continue
            seen.add(t)
            strip.append(stack([label(f'第 {t} 幀', imgs[n].width, 14, 20), imgs[n].convert('RGBA')], 2))
        stack([label(CASES[case][3] + '（遊戲倍率 2 倍）', 1600, 20, 30)] + [hrow(strip[c:c + 7]) for c in range(0, len(strip), 7)], 4) \
            .save(os.path.join(out, f'with_boss_{case}.png'))
    hands_sheet().save(os.path.join(out, 'hands.png'))
    head_check().save(os.path.join(out, 'head_check.png'))
    print('previews in', os.path.relpath(out, ROOT))
