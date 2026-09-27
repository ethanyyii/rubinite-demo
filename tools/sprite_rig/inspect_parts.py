"""Overlay each rig part in its own colour on the sprite, to check the part cut.

    python3 tools/sprite_rig/inspect_parts.py out.png

Left: the sprite. Right: the same pixels tinted by part. A part cut is right when every
tint sits on the thing it names (helmet on the helmet, legs only below the tassets...).
"""
import sys
from PIL import Image, ImageDraw

import sprites as A
import walk_side as W
import walk_fb as F

COL = {'plume': (255, 60, 200), 'legs': (150, 150, 150), 'leg_l': (120, 120, 120), 'leg_r': (190, 190, 190),
       'cape': (40, 200, 255), 'sword': (255, 255, 0), 'scarf': (0, 255, 120), 'helmet': (255, 140, 0),
       'pauldron': (180, 90, 255), 'paul_l': (180, 90, 255), 'paul_r': (120, 60, 255), 'arm': (255, 40, 40),
       'arm_l': (255, 40, 40), 'arm_r': (255, 120, 60), 'torso': (60, 110, 60)}


def parts_of(name):
    pix, _ = A.SPR[name]
    if name in ('front', 'back'):
        cfg = F.FRONT if name == 'front' else F.BACK
        return W.split(pix, cfg['parts'](pix), 'torso')
    cfg = W.EAST if name == 'side_right' else W.WEST
    return W.split(pix, cfg['parts'](), 'torso')


def main(out, k=12):
    tiles = []
    for name in ('front', 'side_right', 'back', 'side_left'):
        _, (w, h) = A.SPR[name]
        im = Image.new('RGBA', (w * k * 2 + 12, h * k + 16), (30, 30, 30, 255))
        ImageDraw.Draw(im).text((2, 2), name, fill=(255, 255, 255, 255))
        for part, px in parts_of(name).items():
            tint = COL.get(part, (255, 255, 255))
            for (x, y), c in px.items():
                mix = tuple((c[i] + tint[i]) // 2 for i in range(3)) + (255,)
                im.paste(c, (x * k, 16 + y * k, x * k + k, 16 + y * k + k))
                im.paste(mix, (w * k + 12 + x * k, 16 + y * k, w * k + 12 + x * k + k, 16 + y * k + k))
        tiles.append(im)
    W_ = max(t.width for t in tiles)
    sheet = Image.new('RGBA', (W_, sum(t.height + 8 for t in tiles)), (30, 30, 30, 255))
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height + 8
    sheet.save(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'parts.png')
