"""Side-by-side at one pixel scale: concept art downscaled the same way | old 50 px | new 40 px.

    python3 tools/sprite_rig/compare_sizes.py

Writes docs/art-preview/player/knight_40px_vs_50px.png. The old 50 px frames come from the
archived sheet docs/art-preview/player/archive/knight_walk_50px.png (72x70 cells) and the
50 px library native/; the new ones from assets/sprites/player/knight_walk.png.
"""
import os
from PIL import Image, ImageDraw

import sprites as A
from export_walk import FACINGS, CONCEPT, CONCEPT_BOX, ROOT

HERE = os.path.dirname(os.path.abspath(__file__))
OLD_SHEET = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'archive', 'knight_walk_50px.png')
NEW_SHEET = os.path.join(ROOT, 'assets', 'sprites', 'player', 'knight_walk.png')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'knight_40px_vs_50px.png')
OLD_FW, OLD_FH = 72, 70
K = 5                 # display: every sprite pixel is K x K screen pixels, for all columns
PAPER = (237, 230, 218)
BG = (96, 112, 96, 255)
WALK_COL = 3          # which walk frame to show (sheet column; 0 = idle)


def snap_concept(im):
    """Same method as the 40 px library: area average then snap to the palette."""
    pal = [tuple(int(v) for v in l.split()) for l in open(os.path.join(HERE, 'native40', 'palette.txt')) if l.strip()]
    p = im.load()
    for y in range(im.height):
        for x in range(im.width):
            c = p[x, y]
            if sum(abs(c[i] - PAPER[i]) for i in range(3)) < 40:
                continue
            p[x, y] = min(pal, key=lambda q: (q[0] - c[0]) ** 2 * 3 + (q[1] - c[1]) ** 2 * 4 + (q[2] - c[2]) ** 2 * 2) + (255,)
    return im


def main():
    concept = Image.open(CONCEPT).convert('RGBA')
    old = Image.open(OLD_SHEET).convert('RGBA')
    new = Image.open(NEW_SHEET).convert('RGBA')
    labels = ['concept, area-averaged to 40 px', 'old 50 px idle', 'new 40 px idle',
              f'old 50 px walk {WALK_COL}', f'new 40 px walk {WALK_COL}']
    rows = []
    for r, (fac, spr) in enumerate(FACINGS):
        ref = concept.crop(CONCEPT_BOX[spr])
        s = A.META[spr]['scale'] / 4.39          # concept-sheet px -> 40 px library px
        ref = ref.convert('RGBa').resize((round(ref.width * s), round(ref.height * s)), Image.BOX).convert('RGBA')
        ref = snap_concept(ref)
        cells = [ref,
                 old.crop((0, r * OLD_FH, OLD_FW, (r + 1) * OLD_FH)),
                 new.crop((0, r * A.FH, A.FW, (r + 1) * A.FH)),
                 old.crop((WALK_COL * OLD_FW, r * OLD_FH, (WALK_COL + 1) * OLD_FW, (r + 1) * OLD_FH)),
                 new.crop((WALK_COL * A.FW, r * A.FH, (WALK_COL + 1) * A.FW, (r + 1) * A.FH))]
        cells = [c.resize((c.width * K, c.height * K), Image.NEAREST) for c in cells]
        h = max(c.height for c in cells)
        row = Image.new('RGBA', (sum(c.width for c in cells) + 16 * len(cells), h), BG)
        x = 0
        for c in cells:
            row.alpha_composite(c, (x, h - c.height))   # bottoms aligned: feet on one line
            x += c.width + 16
        rows.append(row)
    W = max(r.width for r in rows)
    out = Image.new('RGBA', (W, sum(r.height for r in rows) + 24), BG)
    ImageDraw.Draw(out).text((6, 6), '   |   '.join(labels) + f'   (all at {K}x per sprite pixel)', fill=(255, 255, 255, 255))
    y = 24
    for r in rows:
        out.alpha_composite(r, (0, y))
        y += r.height
    out.save(OUT)
    print('wrote', os.path.relpath(OUT, ROOT), out.size)


if __name__ == '__main__':
    main()
