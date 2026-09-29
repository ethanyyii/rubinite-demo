"""Before / after sheet for the charge and thrust fixes of 2026-09-28 (docs/art-progress.md,
"修正：蓄力與突刺"): the approved batch 3 version (git HEAD's sprites), the first fix (the user: "not
fixed"; rebuilt here from its pose data - the rig's second-fix switches are all off for it, so it
draws as it did) and the current one, side by side in every view.

  python3 tools/sprite_rig/export_charge_fix.py

writes docs/art-preview/player/batch3/batch3_charge_fix_compare.png (whole figures, 4x) and
batch3_charge_fix_legs.png (the lower body, 6x: where the legs broke)."""
import io
import os
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import poses as PS            # noqa: E402
import batch3 as B3           # noqa: E402
from export_poses import font  # noqa: E402

OUT = 'docs/art-preview/player/batch3'
SHEETS = 'assets/sprites/player'
VIEWS = ('south', 'east', 'north', 'west')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
BG = (226, 218, 200, 255)

# the first fix's pose data, as it stood before the second fix (git: uncommitted, so kept here)
FIX1_CHARGE = dict(root=(-2, -2, -2.5), lean=0, roll=-16, legs3d=True, floor3d=True, head=(1, 0, 0),
                   feet={'R': (0, 0, 0, 'flat'), 'L': (0, 0, 0, 'flat')},
                   feet_view=PS.planted({'R': (-7, -7, 0, 'flat'), 'L': (4.5, 4, 0, 'flat')}),
                   arms={'R': PS.hand('R', -3, -10, -3, elbow=(-1, -1, 0), over_cape=True),
                         'L': PS.hand('L', 11, 9, 1, elbow=(0, 1, -1))},
                   sword=dict(hand='R', dir=(1.0, -0.12, 0.0)), cape=(-1, 0, 0), plume=(-1, 0, 0))
FIX1_THRUST = dict(root=(4, -1, -4), lean=24, roll=-4,
                   feet={'R': (-9, -5, 0, 'toe'), 'L': (9, 5, 0, 'flat')},
                   arms={'R': PS.hand('R', 13, -3, -1, elbow=(0, -1, 0)), 'L': PS.hand('L', -6, 8, -3, elbow=(-1, 1, 0))},
                   sword=dict(hand='R', dir=(1.0, -0.12, 0.0)), legs3d=True, floor3d=True,
                   cape=(-6, 0, 5), plume=(-2, 0, 1))
# the first fix's forward step (batch3.charge_walk_pose as it stood then): six frames of 2 sim frames
F1_N, F1_FOOT, F1_LIFT, F1_BOB = 6, (2.0, 0.67, -0.67, -2.0, -0.67, 0.67), (0.0, 0.0, 0.0, 0.0, 1.5, 1.0), (0, 1, 0, 0, 1, 0)


def fix1_walk_pose(view, i):
    import math
    import batch1 as B1
    import pose_rig as PR
    upper = B1.resolve(FIX1_CHARGE, view)
    near = PR.VIEWS[view].get('near', 'R')
    feet = {}
    for s_, k in ((near, i), ('L' if near == 'R' else 'R', (i + F1_N // 2) % F1_N)):
        f0, l0, lift0, state = upper['feet'][s_]
        lift = F1_LIFT[k]
        feet[s_] = (f0 + F1_FOOT[k], l0, lift0 + lift, 'swing' if lift and PR.VIEWS[view]['kind'] == 'side' else state)
    bob, prev = F1_BOB[i], F1_BOB[(i - 1) % F1_N]
    phi = 2 * math.pi * i / F1_N
    p = dict(upper, feet=feet)
    p['root'] = B1._add(p['root'], (0, 0, -bob))
    p['head'] = B1._add(p['head'], (0, 0, bob - prev))
    if view in ('east', 'west'):
        p['cape'] = B1._add(p['cape'], (-0.5 * math.sin(2 * phi - 1.2), 0, 0))
        p['plume'] = B1._add(p['plume'], (0, 0, 0.5 * math.sin(2 * phi - 2.0)))
    else:
        p['cape'] = B1._add(p['cape'], (0, 0.5 * math.sin(phi - 1.0), 0))
        p['cape_lowered_add'] = prev - bob
        p['plume'] = B1._add(p['plume'], (0, 0.5 * math.sin(phi - 1.6), 0))
    return p

# (label, action, frame name in batch 3, sheet file, column)
ITEMS = [('蓄力 按住', 'charge', 'hold 1', 'knight_charge.png', 2),
         ('蓄力移動 前進 3', 'charge_walk', 'fwd 3', 'knight_charge_walk.png', 2),
         ('突刺 前撲', 'thrust', 'f2 前撲', 'knight_thrust.png', 1)]


def head_cell(sheet, col, row):
    data = subprocess.run(['git', 'show', f'HEAD:{SHEETS}/{sheet}'], capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(data)).convert('RGBA')
    return im.crop((col * 88, row * 72, col * 88 + 88, row * 72 + 72))


def now_cell(sheet, col, row):
    im = Image.open(f'{SHEETS}/{sheet}').convert('RGBA')
    return im.crop((col * 88, row * 72, col * 88 + 88, row * 72 + 72))


def frame_image(f):
    im = Image.new('RGBA', (88, 72), (0, 0, 0, 0))
    for (x, y), c in f.px.items():
        if 0 <= x < 88 and 0 <= y < 72:
            im.putpixel((x, y), c)
    return im


def fix1_cells():
    """The first fix's frames, rebuilt: its pose data and its walk step (the rig's second-fix
    switches are off for them, so they draw as they did)."""
    import pose_rig as PR
    save = (PS.CHARGE, PS.THRUST)
    PS.CHARGE, PS.THRUST = FIX1_CHARGE, FIX1_THRUST
    B3._CACHE.clear()
    try:
        out = {}
        for _, action, name, _, _ in ITEMS:
            for view in VIEWS:
                if action == 'charge_walk':
                    i = int(name.split()[1]) - 1
                    r = PR.rig(view)
                    out[(action, view)] = PR.image(r.frame(fix1_walk_pose(view, i), 'large'), 'large')
                    continue
                f = next(f for f in B3.frames(action, view) if f.name == name)
                out[(action, view)] = frame_image(f)
        return out
    finally:
        PS.CHARGE, PS.THRUST = save
        B3._CACHE.clear()


def sheet(cells, box, k, path, title):
    bw, bh = box[2] - box[0], box[3] - box[1]
    cw, ch = bw * k, bh * k
    ver = ('第 3 批核准版', '上一版修正', '這一版')
    left, top, gap = 64, 66, 6
    W = left + len(ITEMS) * (3 * (cw + 2) + gap)
    H = top + len(VIEWS) * (ch + 2)
    img = Image.new('RGB', (W, H), (34, 34, 42))
    d = ImageDraw.Draw(img)
    d.text((8, 4), title, font=font(20), fill=(240, 240, 240))
    for ii, (label, action, _, _, _) in enumerate(ITEMS):
        x0 = left + ii * (3 * (cw + 2) + gap)
        d.text((x0, 30), label, font=font(15), fill=(240, 240, 240))
        for vi, view in enumerate(VIEWS):
            for j in range(3):
                c = cells[(j, action, view)].crop(box).resize((cw, ch), Image.NEAREST)
                bg = Image.new('RGBA', (cw, ch), BG)
                dd = ImageDraw.Draw(bg)
                gy = (61 - box[1] + 1) * k
                dd.line([(0, gy), (cw, gy)], fill=(175, 165, 145, 255))
                bg.alpha_composite(c)
                img.paste(bg, (x0 + j * (cw + 2), top + vi * (ch + 2)))
                if vi == 0:
                    d.text((x0 + j * (cw + 2) + 2, 48), ver[j], font=font(13), fill=(210, 210, 210))
    for vi, view in enumerate(VIEWS):
        d.text((8, top + vi * (ch + 2) + 6), VIEW_ZH[view], font=font(15), fill=(240, 240, 240))
    img.save(path)
    print('wrote', path, img.size)


def main():
    f1 = fix1_cells()
    cells = {}
    for _, action, _, sheet_name, col in ITEMS:
        for vi, view in enumerate(VIEWS):
            cells[(0, action, view)] = head_cell(sheet_name, col, vi)
            cells[(1, action, view)] = f1[(action, view)]
            cells[(2, action, view)] = now_cell(sheet_name, col, vi)
    sheet(cells, (8, 6, 88, 68), 4, f'{OUT}/batch3_charge_fix_compare.png',
          '蓄力、突刺：第 3 批核准版 → 上一版修正（你說沒修好）→ 這一版，4 倍')
    sheet(cells, (18, 40, 72, 66), 6, f'{OUT}/batch3_charge_fix_legs.png',
          '下半身放大 6 倍：腿的形狀')


if __name__ == '__main__':
    main()
