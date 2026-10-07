"""The execution (2026-10-05: the 3 s leap and stab, execute.py): the sprite sheet and its previews.

    python3 tools/sprite_rig/export_execute.py [sheet]

Writes assets/sprites/player/knight_execute.png (88 x 152 cells, feet anchor (44, 141); rows south,
east, north, west; columns = execute.FRAMES) and, unless `sheet`, the previews in
docs/art-preview/player/execute/. Re-run export_frames.py afterwards (the game's frame table)."""
import os
import sys

from PIL import Image

import pose_rig as PR
import execute as E

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
PREVIEW = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'execute')


def write_sheet():
    W_, H_, _, _ = PR.CANVAS[E.CANVAS]
    fr = {v: E.frames(v) for v in E.VIEWS}
    cols = len(fr['south'])
    sheet = Image.new('RGBA', (W_ * cols, H_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(E.VIEWS):
        for c, f in enumerate(fr[v]):
            sheet.alpha_composite(PR.image(f.px, E.CANVAS), (c * W_, r * H_))
    path = os.path.join(SHEETS, 'knight_execute.png')
    sheet.save(path)
    return path, sheet


def main():
    path, sheet = write_sheet()
    print('sheet', os.path.relpath(path, ROOT), sheet.size)
    if 'sheet' in sys.argv[1:]:
        return
    import preview_execute
    preview_execute.main(PREVIEW)


if __name__ == '__main__':
    main()
