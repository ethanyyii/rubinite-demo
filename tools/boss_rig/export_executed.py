"""Only the Boss's EXECUTED sheet (2026-10-05: 3 s, anim_kneel.executed()) and its contact previews,
without re-exporting every hit / kneel clip (export_hit.py does them all, ~15 minutes).

    python3 tools/boss_rig/export_executed.py

Then re-run export_game.py (the game's packed frames)."""
import os

import anim_kneel as K
import export_hit as EH
import preview
import rig


def main():
    clip = K.executed()
    groups = [EH.frames(clip)]
    cell, big = EH.write_sheet(os.path.join(EH.SHEETS, 'boss_executed.png'), groups)
    print('boss_executed', cell, len(clip), sum(clip.holds))
    os.makedirs(EH.OUT, exist_ok=True)
    for d in rig.DIRS:
        fr = groups[0][d]
        preview.contact(fr, k=1, cols=len(fr), box=EH.BOX, labels=[f':{i}' for i in range(len(fr))]).save(
            os.path.join(EH.OUT, f'boss_executed_{d}.png'))


if __name__ == '__main__':
    main()
