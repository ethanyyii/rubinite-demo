"""An earlier version's attack sheets against the current ones, at the same combat frames (each
sheet's boss_attacks.json says which pose is shown at a frame): one row per version and
direction. For the review of a new version (animation-review §5: put the new one beside the
old one); export_attack.py clears the preview folder, so run this after it.

    python3 tools/boss_rig/compare_sheets.py 舊版精靈圖資料夾 輸出.png 圖名 幀,幀,... [方向,...] [舊版名稱 新版名稱]

例：python3 tools/boss_rig/compare_sheets.py /tmp/v2 docs/art-preview/boss/attack/feet_v2_v3_c1.png boss_c1 0,16,32,46,52,64 right,left 第二版 第三版

Before re-exporting, copy the old assets/sprites/boss/boss_*.png and boss_attacks.json to a
folder (the old version is gone otherwise).
"""
import json
import os
import sys
from PIL import Image, ImageDraw
import boss as B
import preview

NEW = os.path.join(B.ROOT, 'assets', 'sprites', 'boss')
DIRS = ('down', 'right', 'up', 'left')
NAMES = {'down': '朝下', 'right': '朝右', 'up': '朝上', 'left': '朝左'}
CELL = (384, 336)
FOOT_Y = 272


FWD = {'right': (1, 0), 'left': (-1, 0), 'down': (0, 1), 'up': (0, -1)}     # the game moves him 1:1 on screen


def cell(folder, sheet, t, d):
    """(the cell shown at combat frame t (the last pose starting at or before it), its offset on
    screen: how far the game has moved him then - the pose's 'advance', the twin slash's step)."""
    meta = json.load(open(os.path.join(folder, 'boss_attacks.json')))[sheet]
    i = max(j for j, p in enumerate(meta['poses']) if p['t'] <= t)
    im = Image.open(os.path.join(folder, sheet + '.png')).convert('RGBA')
    r = DIRS.index(d)
    a = meta['poses'][i].get('advance', 0.0)
    return (im.crop((i * CELL[0], r * CELL[1], (i + 1) * CELL[0], (r + 1) * CELL[1])),
            (round(FWD[d][0] * a), round(FWD[d][1] * a)))


def tile(c, box, k):
    c, (dx, dy) = c
    bg = Image.new('RGBA', c.size, preview.BG + (255,))
    ImageDraw.Draw(bg).line((0, FOOT_Y + 1, c.width, FOOT_Y + 1), fill=preview.GROUND)
    bg.alpha_composite(c, (dx, dy))
    bg = bg.crop(box)
    return bg.resize((bg.width * k, bg.height * k), Image.NEAREST).convert('RGB')


def sheet(old, out, name, times, dirs=('right', 'left', 'down', 'up'), tags=('舊版', '新版'), labels=None,
          box=(110, 60, 290, 290), k=2):
    rows = []
    for d in dirs:
        for tag, folder in zip(tags, (old, NEW)):
            rows.append((f'{NAMES[d]} {tag}', [tile(cell(folder, name, t, d), box, k) for t in times]))
    tw, th = rows[0][1][0].size
    left = 130
    im = Image.new('RGB', (left + len(times) * (tw + 4), 28 + len(rows) * (th + 4) + 8 * (len(dirs) - 1)), preview.BG)
    dr = ImageDraw.Draw(im)
    for j, t in enumerate(times):
        dr.text((left + j * (tw + 4) + 4, 4), labels[j] if labels else f'第 {t} 幀', font=preview.font(16),
                fill=(235, 228, 220))
    y = 28
    for r, (lab, tiles) in enumerate(rows):
        if r and r % 2 == 0:
            y += 8
        dr.text((6, y + 6), lab, font=preview.font(16), fill=(235, 228, 220))
        for j, t in enumerate(tiles):
            im.paste(t, (left + j * (tw + 4), y))
        y += th + 4
    im.save(out)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    old, out, name, times = a[0], a[1], a[2], [int(v) for v in a[3].split(',')]
    dirs = tuple(a[4].split(',')) if len(a) > 4 else ('right', 'left', 'down', 'up')
    tags = (a[5], a[6]) if len(a) > 6 else ('舊版', '新版')
    print(sheet(old, out, name, times, dirs, tags))
