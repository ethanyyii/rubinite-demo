"""Write the player's sprite-sheet frame tables for the game.

    python3 tools/sprite_rig/export_frames.py

Writes scripts/view/knight_sheets.gd (class KnightSheets): for every sheet in
assets/sprites/player/, its cell size, foot anchor, row keys and, column by column, the frame
names and how many simulation frames each shows - read from the same tables that drew the
sheets (the column order is each frames() order). The game picks its cells from this file
(scripts/view/player_anim.gd); tests/unit/test_player_sprites.gd checks the tables against the
combat data (every timed action tiles its program length).

Nothing is drawn here except the run (its stop table is measured on the drawn frames) and the
four-hit combo (its frame spans come out of the pose search), so this takes a while.
"""
import os

import batch1 as B1
import batch3 as B3
import batch4 as B4
import combo4 as C4
import execute as EX

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'scripts', 'view', 'knight_sheets.gd')
VIEWS = list(B1.VIEWS)
SMALL = ((56, 56), (28, 53))
LARGE = ((88, 72), (44, 61))
EXEC = ((88, 152), (44, 141))


def sheet(name, size, rows, names, durs, **extra):
    assert len(names) == len(durs), name
    d = dict(path=f'res://assets/sprites/player/knight_{name}.png', cell=size[0], anchor=size[1], rows=rows,
             names=names, durs=durs)
    d.update(extra)
    return name, d


def plain(action, table, size=SMALL):
    return sheet(action, size, VIEWS, [n for n, _, _ in table], [d for _, d, _ in table])


def attack(stage):
    """A combo stage: its frames (first / last sim frame each, whether it is one of the frames a
    late chain plays the entry from), then the entry from the stance (combo4.ENTRY)."""
    main = {v: C4.frames(stage, v) for v in VIEWS}
    ent = {v: C4.frames(stage, v, entry_frames=True) if stage in C4.ENTRY else [] for v in VIEWS}
    ref = [(f.name, f.first, f.last) for f in main['south']]
    for v in VIEWS:
        assert [(f.name, f.first, f.last) for f in main[v]] == ref, (stage, v)
        assert [(f.name, f.first, f.last) for f in ent[v]] == [(f.name, f.first, f.last) for f in ent['south']]
    names = [f.name for f in main['south']] + [f.name for f in ent['south']]
    durs = [f.dur for f in main['south']] + [f.dur for f in ent['south']]
    extra = dict(first=[f.first for f in main['south']], late=[C4.LATE in f.name for f in main['south']],
                 adv=[f.adv for f in main['south']], entry_col=len(main['south']) if ent['south'] else -1)
    return sheet(C4.SHEETS[stage], LARGE, VIEWS, names, durs, **extra)


def build():
    out = []
    # the walk: column 0 is the stance (the idle's first frame), 1-8 the cycle (export_walk.py)
    out.append(sheet('walk', SMALL, VIEWS, ['stand'] + [f'walk {i + 1}' for i in range(8)], [0] + [2] * 8))
    for action in ('idle', 'guard', 'heal', 'guard_walk', 'heal_walk'):
        out.append(plain(action, B1.ACTIONS[action]))
    for action, name in B3.CANVAS.items():
        size = LARGE if name == 'large' else SMALL
        out.append(plain(action, B3.ACTIONS[action], size))
    for action, table in B4.VIEW_ACTIONS.items():
        out.append(plain(action, table))
    for action, table in B4.ROW_ACTIONS.items():
        out.append(sheet(action, SMALL, list(B4.ROWS), [n for n, _, _ in table], [d for _, d, _ in table]))
    for stage in (1, 2, 3, 4):
        out.append(attack(stage))
    # the execution (2026-10-05, execute.py): the feet's height off the floor per column (drawn into the
    # picture; the game draws the shadow on the floor) and, per row, where the blade goes into the Boss
    fr = {v: EX.frames(v) for v in VIEWS}
    assert all([f.name for f in fr[v]] == [f.name for f in fr['south']] for v in VIEWS)
    assert all([f.air for f in fr[v]] == [f.air for f in fr['south']] for v in VIEWS)
    out.append(sheet('execute', EXEC, VIEWS, [f.name for f in fr['south']], [f.dur for f in fr['south']],
                     lift=[f.air for f in fr['south']], wound=[EX.wound(v) for v in VIEWS]))
    return dict(out)


def gd(v, ind=0):
    """A GDScript constant expression."""
    pad = '\t' * ind
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"'
    if v is None:
        return 'null'
    if isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, int) for x in v):
        return f'Vector2i({v[0]}, {v[1]})'
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(gd(x) for x in v) + ']'
    if isinstance(v, dict):
        items = [f'{pad}\t{gd(k)}: {gd(x, ind + 1)},' for k, x in v.items()]
        return '{\n' + '\n'.join(items) + f'\n{pad}}}'
    raise TypeError(v)


def main():
    sheets = build()
    # the run: which cycle frame can step into which stop 1 ('A' / 'B', or "" = play on), and the
    # cycle frame the two start frames lead into (batch3.RUN_START; art-progress appendix B)
    stop_from = {v: [s or '' for s in B3.run_stop_from(v)] for v in VIEWS}
    start_phase = {v: B3.RUN_START[v][0] for v in VIEWS}
    lines = [
        '# Generated by tools/sprite_rig/export_frames.py - do not edit (re-run it after re-exporting a sheet).',
        'class_name KnightSheets',
        'extends RefCounted',
        '## 主角精靈圖的幀表（art-progress 附錄 B）：每張圖的畫格大小、腳底對齊點、每一列是哪個方向',
        '## （四方向 south／east／north／west，或兩列 R／L＝攻擊者在右／在左），每一欄的名字與停幾個模擬幀。',
        '## 欄的順序就是產生精靈圖時 frames() 的順序。攻擊另有每張的第一個模擬幀（first）、是不是「回站姿」',
        '## （late：從這幾張接下一段時播「從站姿的開頭」）、這張畫在程式前進多少的位置（adv）、從站姿的開頭在哪一欄。',
        '',
        f'const SHEETS := {gd(sheets)}',
        '',
        '## 奔跑放開搖桿時：循環的第幾張可以接停步 1 的哪一個版本（"" ＝ 先播下一張）',
        f'const RUN_STOP_FROM := {gd(stop_from)}',
        '## 起跑兩張之後接循環的第幾張',
        f'const RUN_START_PHASE := {gd(start_phase)}',
        '## 死亡：倒地的六張，時間拉長（batch4.DEATH）',
        f'const DEATH := {gd([[n, d] for n, d in B4.DEATH])}',
        '## 擊飛：空中兩張照 launch 的停留幀數交替，共 LAUNCH_AIR 幀；落地後接倒地的著地、趴著（batch4.LAUNCH_DOWN）',
        f'const LAUNCH_AIR := {B4.LAUNCH_AIR}',
        f'const LAUNCH_DOWN := {gd([[n, d] for n, d in B4.LAUNCH_DOWN])}',
        '',
    ]
    with open(OUT, 'w') as fh:
        fh.write('\n'.join(lines))
    print('wrote', os.path.relpath(OUT, ROOT), len(sheets), 'sheets')


if __name__ == '__main__':
    main()
