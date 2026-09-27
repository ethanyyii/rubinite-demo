"""Render the player walk animation and write it into the project.

    python3 tools/sprite_rig/export_walk.py

Writes
  assets/sprites/player/knight_walk.png          sprite sheet (the game asset)
  docs/art-preview/player/knight_walk_*.gif        previews (4 facings, then one per facing)
  docs/art-preview/player/knight_walk_vs_reference.png   concept art | idle | walk frames
  docs/art-preview/player/knight_walk_head_check.png     heads only, plume/helmet contact for review
"""
import os
import sys
from PIL import Image, ImageDraw

import sprites as A
import walk_side as W
import walk_fb as F

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEET = os.path.join(ROOT, 'assets', 'sprites', 'player', 'knight_walk.png')
PREVIEW = os.path.join(ROOT, 'docs', 'art-preview', 'player')
CONCEPT = os.path.join(ROOT, 'docs', 'art-reference', 'player-knight-concept.webp')

# row order of the sheet; sprite = which reference view it is built from
FACINGS = [('south', 'front'), ('east', 'side_right'), ('north', 'back'), ('west', 'side_left')]
# where each view sits on the concept sheet (for the comparison image)
CONCEPT_BOX = {'front': (18, 118, 300, 410), 'side_right': (762, 118, 990, 410),
               'back': (540, 118, 762, 410), 'side_left': (318, 118, 522, 410)}
FLOOR = (74, 70, 66, 255)
SHADOW = (48, 44, 42, 255)
N = W.N


def rigs():
    return {'front': F.FBRig(F.FRONT), 'side_right': W.SideRig(W.EAST),
            'back': F.FBRig(F.BACK), 'side_left': W.SideRig(W.WEST)}


def all_frames():
    """{facing: [idle, walk0 .. walk7]} as RGBA images."""
    r = rigs()
    return {fac: [A.stand_frame(spr).image()] + [r[spr].frame(i).image() for i in range(N)]
            for fac, spr in FACINGS}


def upscale(im, k, bg=None):
    big = im.resize((im.width * k, im.height * k), Image.NEAREST)
    if bg is None:
        return big
    out = Image.new('RGBA', big.size, bg)
    out.alpha_composite(big)
    return out


def on_floor(im):
    cell = Image.new('RGBA', (A.FW, A.FH), FLOOR)
    ImageDraw.Draw(cell).ellipse((A.CX - 14, A.GROUND - 2, A.CX + 14, A.GROUND + 3), fill=SHADOW)
    cell.alpha_composite(im)
    return cell


def save_gif(frames, path, colors):
    stack = Image.new('RGB', (frames[0].width, frames[0].height * len(frames)))
    for i, g in enumerate(frames):
        stack.paste(g, (0, i * g.height))
    pal = stack.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=100, loop=0)


def main():
    frames = all_frames()
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)

    # sprite sheet: rows S/E/N/W, column 0 = idle, columns 1-8 = walk cycle
    sheet = Image.new('RGBA', (A.FW * (N + 1), A.FH * len(FACINGS)), (0, 0, 0, 0))
    for r, (fac, _) in enumerate(FACINGS):
        for c, im in enumerate(frames[fac]):
            sheet.alpha_composite(im, (c * A.FW, r * A.FH))
    sheet.save(SHEET)

    # four facings side by side, 4x
    gif = []
    for i in range(N):
        row = Image.new('RGBA', (A.FW * len(FACINGS), A.FH), FLOOR)
        for c, (fac, _) in enumerate(FACINGS):
            row.alpha_composite(on_floor(frames[fac][i + 1]), (c * A.FW, 0))
        gif.append(upscale(row, 4).convert('RGB'))
    save_gif(gif, os.path.join(PREVIEW, 'knight_walk_preview.gif'), 128)

    # one facing per gif, 6x
    for fac, _ in FACINGS:
        save_gif([upscale(on_floor(frames[fac][i + 1]), 6).convert('RGB') for i in range(N)],
                 os.path.join(PREVIEW, f'knight_walk_{fac}.gif'), 96)

    # comparison: concept art (same pixel scale) | idle | walk frames
    k = 3
    concept = Image.open(CONCEPT).convert('RGBA')
    rows = []
    for r, (fac, spr) in enumerate(FACINGS):
        ref = concept.crop(CONCEPT_BOX[spr])
        # one 50 px library pixel is ~4.39 concept-sheet pixels; the 40 px library is scaled from it
        sc = k * A.META[spr]['scale'] / 4.39
        ref = ref.resize((round(ref.width * sc), round(ref.height * sc)), Image.LANCZOS)
        b = Image.new('RGBA', ref.size, (237, 230, 218, 255))
        b.alpha_composite(ref)
        strip = upscale(sheet.crop((0, r * A.FH, sheet.width, (r + 1) * A.FH)), k)
        h = max(b.height, strip.height)
        row = Image.new('RGBA', (b.width + 20 + strip.width, h), (96, 112, 96, 255))
        row.alpha_composite(b, (0, h - b.height))
        row.alpha_composite(strip, (b.width + 20, h - strip.height))
        rows.append(row)
    out = Image.new('RGBA', (max(r.width for r in rows), sum(r.height for r in rows) + 26), (96, 112, 96, 255))
    ImageDraw.Draw(out).text((6, 6), 'concept sheet (same pixel scale) | idle = 40 px library | walk 1-8',
                             fill=(255, 255, 255, 255))
    y = 26
    for row in rows:
        out.alpha_composite(row, (0, y))
        y += row.height
    out.save(os.path.join(PREVIEW, 'knight_walk_vs_reference.png'))
    head_check(frames)
    print('wrote', os.path.relpath(SHEET, ROOT), sheet.size, 'and previews in', os.path.relpath(PREVIEW, ROOT))


def head_check(frames, k=6):
    """Above the neck, for a visual review (checks.py does not test it): every frame's head,
    with background enclosed by the plume touching the helmet tinted yellow."""
    import walk_side as W_, walk_fb as F_
    neck = {'front': F_.FRONT['neck'][1], 'back': F_.BACK['neck'][1],
            'side_right': W_.EAST['neck'][1], 'side_left': W_.WEST['neck'][1]}
    rows = []
    for fac, spr in FACINGS:
        cut = int(neck[spr] + A.GROUND - A.META[spr]['feet']) + 2
        tiles = []
        for im in frames[fac]:
            px = im.load()
            opaque = {(x, y) for x in range(A.FW) for y in range(A.FH) if px[x, y][3]}
            outside, stack = set(), [(x, y) for x in range(-1, A.FW + 1) for y in (-1, A.FH)] + \
                [(x, y) for y in range(-1, A.FH + 1) for x in (-1, A.FW)]
            while stack:
                q = stack.pop()
                if q in outside or q in opaque or not (-1 <= q[0] <= A.FW and -1 <= q[1] <= A.FH):
                    continue
                outside.add(q)
                stack += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
            tile = Image.new('RGBA', (A.FW, cut), (96, 112, 96, 255))
            tile.alpha_composite(im.crop((0, 0, A.FW, cut)))
            for x in range(A.FW):
                for y in range(cut):
                    if (x, y) not in opaque and (x, y) not in outside:
                        tile.putpixel((x, y), (255, 230, 0, 255))
            tiles.append(upscale(tile, k))
        row = Image.new('RGBA', (sum(t.width + 6 for t in tiles), tiles[0].height), (30, 30, 30, 255))
        x = 0
        for t in tiles:
            row.paste(t, (x, 0))
            x += t.width + 6
        rows.append(row)
    out = Image.new('RGBA', (max(r.width for r in rows), sum(r.height + 8 for r in rows) + 20), (30, 30, 30, 255))
    ImageDraw.Draw(out).text((6, 4), 'above the neck: idle | walk 1-8  (yellow = background enclosed by plume touching helmet)',
                             fill=(255, 255, 255, 255))
    y = 20
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + 8
    out.save(os.path.join(PREVIEW, 'knight_walk_head_check.png'))


if __name__ == '__main__':
    sys.exit(main())
