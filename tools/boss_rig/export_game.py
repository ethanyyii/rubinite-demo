"""The Boss's sprites for the game: every sheet's cells trimmed to what is drawn, the same ones once, packed into
palette-index atlases, with the frame table the game plays them by.

    python3 tools/boss_rig/export_game.py

The sheets in assets/sprites/boss/ are the art's (and the previews'); together they are 1.2 billion pixels - some
wider than a GPU takes - so the game does not load them (assets/sprites/boss/.gdignore). Measured: 12,288 cells
drawn, about 10,300 different, 190 million pixels trimmed; 48 colours (boss.load_palette), alpha 0 or 255. So:

  assets/sprites/boss_game/boss_atlas_<n>.png   4096 x 4096, 8 bits a pixel: 0 transparent, i = palette colour i - 1
  assets/sprites/boss_game/boss_palette.png     64 x 1 RGBA: x = index (the shader's lookup, scripts/view/boss_palette.gdshader)
  assets/sprites/boss_game/boss_frames.json     frames: [atlas, x, y, w, h, ox, oy] - (ox, oy) the trimmed rect's top
                                                left from the foot anchor; clips: name -> {dirs: {down|right|up|left:
                                                [frame]}, holds: [combat frames], ...}; moves: the game's move ids ->
                                                their sheets; interrupt: sheet -> {break|stagger: {pose_start, starts}}

The clips and their holds come from the modules that drew the sheets (anim_walk, anim_idle, export_hit's Timed clips,
the attack exports' Moves and boss_attacks.json), not copied by hand: re-run this after re-exporting any sheet.
"""
import hashlib
import json
import os
from PIL import Image
import rig
import boss as B
import anim_walk as AW
import anim_idle
import gait
import attacks as AT
import export_anim as EA
import export_hit as EH
import export_attack as E
import export_quick as EQ
import export_cleave as EC
import export_thrust as ET
import export_upswing as EU
import export_spin as ES
import export_leap as EL

Image.MAX_IMAGE_PIXELS = None
SHEETS = E.SHEETS
OUT = os.path.join(B.ROOT, 'assets', 'sprites', 'boss_game')
RES = 'res://assets/sprites/boss_game/'
ATLAS = 4096
DIRS = rig.DIRS                              # rows in this order: down, right, up, left
SMALL = ((rig.FW, rig.FH), (rig.AX, rig.AY))
BIG = (AW.BIG, (rig.AX + AW.EXT, rig.AY + AW.EXT))
KEY = (255, 0, 255)                          # stands for transparent while quantizing (not a palette colour)

# the game's moves (veltharis_data) -> the sheet they play, the sheet whose starts-from-a-move they use, the bounce
MOVES = {
    'royal_sweep': ('boss_c1', 'boss_c1', 'boss_c1_bounce'),
    'twin_slash': ('boss_twin', 'boss_c1', 'boss_twin_bounce'),
    'triple_slash': ('boss_triple', 'boss_c1', 'boss_cleave_bounce'),
    'triple_slash_delayed': ('boss_triple', 'boss_c1', 'boss_cleave_bounce'),
    'oath_cleave': ('boss_cleave', 'boss_cleave', 'boss_cleave_bounce'),
    'oath_cleave_delayed': ('boss_cleave', 'boss_cleave', 'boss_cleave_bounce'),
    'judgment_thrust': ('boss_thrust', 'boss_thrust', 'boss_thrust_bounce'),
    'quick_combo_2': ('boss_quick', 'boss_quick', 'boss_quick_bounce'),
    'quick_combo_3': ('boss_quick3', 'boss_quick', 'boss_quick3_bounce'),
    'ash_impact': ('boss_impact', 'boss_impact', None),
    'double_impact': ('boss_double_impact', 'boss_impact', None),
    'ash_spin': ('boss_spin', 'boss_spin', 'boss_spin_bounce'),
    'kings_leap': ('boss_leap', 'boss_leap', 'boss_leap_bounce'),
}
DELAYED = ('triple_slash_delayed', 'oath_cleave_delayed')


class Cells:
    """Every cell the clips use, trimmed, each different one once (frames)."""

    def __init__(self):
        self.frames, self.index, self.images = [], {}, {}
        pal = B.load_palette()
        self.pal = pal
        p = Image.new('P', (1, 1))
        flat = list(KEY) + [c for col in pal for c in col[:3]]
        p.putpalette(flat + [0] * (768 - len(flat)))
        self.pal_image = p

    def sheet(self, name):
        if name not in self.images:
            self.images = {name: Image.open(os.path.join(SHEETS, name + '.png')).convert('RGBA')}   # one at a time
        return self.images[name]

    def cell(self, name, cell, anchor, row, col):
        """Frame id of a sheet's cell (None: nothing drawn)."""
        im = self.sheet(name)
        w, h = cell
        c = im.crop((col * w, row * h, (col + 1) * w, (row + 1) * h))
        bb = c.getbbox()
        if not bb:
            return None
        t = c.crop(bb)
        key = hashlib.md5(t.tobytes()).hexdigest() + f'{bb[0] - anchor[0]},{bb[1] - anchor[1]}'
        if key not in self.index:
            self.index[key] = len(self.frames)
            self.frames.append({'img': self.indexed(t), 'off': (bb[0] - anchor[0], bb[1] - anchor[1])})
        return self.index[key]

    def indexed(self, t):
        """An RGBA cell as palette indices (0 transparent)."""
        bg = Image.new('RGB', t.size, KEY)
        bg.paste(t, mask=t.getchannel('A'))
        q = bg.quantize(palette=self.pal_image, dither=Image.Dither.NONE)
        return Image.frombytes('L', t.size, q.tobytes())


def grid(cells, name, cell, anchor, rows, cols):
    """{direction: [frame ids]} of a group: its four rows (from rows[0]) and the columns."""
    return {d: [cells.cell(name, cell, anchor, rows[0] + r, c) for c in cols] for r, d in enumerate(DIRS)}


def size_of(name):
    im = Image.open(os.path.join(SHEETS, name + '.png'))
    return im.size


def clips(cells):
    out = {}
    # standing (the sword planted) and the four moves: their loops, starts, stops (anim_walk, anim_idle)
    out['idle'] = {'dirs': grid(cells, 'boss_idle', *SMALL, [0], range(anim_idle.N)), 'holds': [anim_idle.HOLD] * anim_idle.N}
    for kind in AW.KINDS:
        name = EA.SHEET_OF[kind]
        out[kind] = {'dirs': grid(cells, name, *SMALL, [0], range(gait.POSES)), 'holds': [gait.HOLD] * gait.POSES,
                     'step': gait.STRIDE / gait.POSES}
        out[kind + '_start'] = {'dirs': grid(cells, name + '_start', *BIG, [0], range(AW.START_N)),
                                'holds': [gait.HOLD] * AW.START_N, 'joins': AW.START_JOINS[kind]}
        for g, e in enumerate(AW.STOP_FROM):
            out[f'{kind}_stop_{e}'] = {'dirs': grid(cells, name + '_stop', *BIG, [0], range(g * AW.STOP_N, (g + 1) * AW.STOP_N)),
                                      'holds': [gait.HOLD] * AW.STOP_N}
    # the hit, kneel and death clips (export_hit, anim_kneel's Timed holds)
    for name, group in EH.clips():
        w, h = size_of(name)
        n = len(group[0])
        cell = (w // n, h // (4 * len(group)))
        anchor = SMALL[1] if cell == SMALL[0] else BIG[1]
        for g, clip in enumerate(group):
            key = name[len('boss_'):]
            if len(group) > 1:
                key += f'_{AW.STOP_FROM[g]}'
            for kind, sheet in EA.SHEET_OF.items():
                key = key.replace(sheet[len('boss_'):], kind, 1) if key.startswith(sheet[len('boss_'):] + '_') else key
            out[key] = {'dirs': grid(cells, name, cell, anchor, [4 * g], range(n)), 'holds': list(clip.holds)}
    # the attacks and bounces (boss_attacks.json), and their starts from a move (the attack exports' Moves)
    data = json.load(open(os.path.join(SHEETS, 'boss_attacks.json')))
    moves = []
    for mod in (E, EQ, EC, ET, EU, ES, EL):
        moves += mod.moves()
    for m in moves:
        js = data[m.sheet]
        cell, anchor = tuple(js['cell']), tuple(js['anchor'])
        c = {'dirs': grid(cells, m.sheet, cell, anchor, [0], range(len(js['poses']))),
             'holds': [p['hold'] for p in js['poses']], 't': [p['t'] for p in js['poses']], 'frames': js['frames'],
             'hits': js['hits'], 'advance': [p['advance'] for p in js['poses']],
             'at': [{d: p['at'][d] for d in DIRS} for p in js['poses']]}
        if 'hold_phase2' in js['poses'][0]:
            c['holds_phase2'] = [p['hold_phase2'] for p in js['poses']]
        if 'lift' in js['poses'][0]:
            c['lift'] = [p['lift'] for p in js['poses']]
        for k in ('delayed', 'flash', 'air', 'game_step'):
            if k in js:
                c[k] = js[k]
        for fl in c.get('flash', []):
            # where the helmet's cross is: from the foot anchor, as everything else
            fl['at'] = {d: [fl['at'][d][0] - anchor[0], fl['at'][d][1] - anchor[1]] for d in DIRS}
        c['at'] = [{d: [p[d]['grip'], p[d]['tip']] for d in DIRS} for p in c['at']]
        for p in c['at']:
            for d in DIRS:
                p[d] = [[v - a for v, a in zip(p[d][0], anchor)], [v - a for v, a in zip(p[d][1], anchor)] if p[d][1] else None]
        out[m.sheet] = c
        if m.has_entries:
            times, _, end = m.entry_spec[:3]
            holds = [b - a for a, b in zip(times, list(times[1:]) + [end])]
            for kind in AW.KINDS:
                name = f'{m.sheet}_{EA.SHEET_OF[kind][len("boss_"):]}_entry'
                for g, e in enumerate(AT.ENTRY_FROM):
                    out[f'{m.sheet}_{kind}_entry_{e}'] = {'dirs': grid(cells, name, cell, anchor, [4 * g], range(len(times))),
                                                          'holds': holds, 'end': end}
    # the starts with the sword planted (export_planted): the first `end` frames of the attacks that open like that sheet
    for key, e in data.items():
        if key.endswith('_planted_entry'):
            out[key] = {'dirs': grid(cells, key, tuple(e['cell']), tuple(e['anchor']), [0], range(len(e['holds']))),
                        'holds': e['holds'], 'end': e['end']}
    # the carry, standing (every attack's first pose)
    out['carry'] = {'dirs': {d: v[:1] for d, v in out['boss_c1']['dirs'].items()}, 'holds': [1]}
    # the interrupted attacks (export_interrupt): every start's way
    interrupt = {}
    for key, e in data.items():
        if not (key.endswith('_break') or key.endswith('_stagger')):
            continue
        kind = 'break' if key.endswith('_break') else 'stagger'
        src = e['source']
        ids = []
        for st in e['starts']:
            ck = f'start_{st["start"]}'
            ids.append(ck)
            if ck not in out:
                out[ck] = {'dirs': grid(cells, st['sheet'], tuple(st['cell']), tuple(st['anchor']), st['rows'],
                                        range(len(st['holds']))), 'holds': st['holds']}
        interrupt.setdefault(src, {})[kind] = {'pose_start': e['pose_start'], 'starts': ids}
        if kind == 'break':
            interrupt[src]['then'] = e['then']
    return out, interrupt


def pack(cells):
    """Shelves, tallest first, in ATLAS-square atlases. Returns the atlases (L images) and frame -> (atlas, x, y)."""
    order = sorted(range(len(cells.frames)), key=lambda i: (-cells.frames[i]['img'].height, -cells.frames[i]['img'].width))
    atlases, where = [], {}
    x = y = shelf = 0
    cur = None
    for i in order:
        t = cells.frames[i]['img']
        w, h = t.width + 1, t.height + 1          # a pixel's gap: nothing bleeds into the next
        if cur is None or x + w > ATLAS:
            x, y, shelf = 0, y + shelf, 0
        if cur is None or y + h > ATLAS:
            cur = Image.new('L', (ATLAS, ATLAS), 0)
            atlases.append(cur)
            x = y = shelf = 0
        cur.paste(t, (x, y))
        where[i] = (len(atlases) - 1, x, y)
        x += w
        shelf = max(shelf, h)
    return atlases, where


def main():
    os.makedirs(OUT, exist_ok=True)
    cells = Cells()
    cl, interrupt = clips(cells)
    print('clips', len(cl), 'frames', len(cells.frames), flush=True)
    atlases, where = pack(cells)
    for f in os.listdir(OUT):
        if f.startswith('boss_atlas_'):
            os.remove(os.path.join(OUT, f))
    for n, a in enumerate(atlases):
        a.save(os.path.join(OUT, f'boss_atlas_{n}.png'), optimize=True)
    pal = Image.new('RGBA', (64, 1), (0, 0, 0, 0))
    for i, c in enumerate(cells.pal):
        pal.putpixel((i + 1, 0), tuple(c[:3]) + (255,))
    pal.save(os.path.join(OUT, 'boss_palette.png'))
    frames = []
    for i, f in enumerate(cells.frames):
        a, x, y = where[i]
        frames.append([a, x, y, f['img'].width, f['img'].height, f['off'][0], f['off'][1]])
    out = {'atlases': [RES + f'boss_atlas_{n}.png' for n in range(len(atlases))], 'palette': RES + 'boss_palette.png',
           'dirs': list(DIRS), 'frames': frames, 'clips': cl, 'interrupt': interrupt,
           'moves': {k: {'sheet': a, 'entries': b, 'bounce': c, 'delayed': k in DELAYED} for k, (a, b, c) in MOVES.items()},
           'kneel_then': {'columns_after_junction': list(range(4, 9))}}
    with open(os.path.join(OUT, 'boss_frames.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    area = sum(f['img'].width * f['img'].height for f in cells.frames)
    print('atlases', len(atlases), 'frames', len(frames), 'Mpx', round(area / 1e6, 1), 'json',
          round(os.path.getsize(os.path.join(OUT, 'boss_frames.json')) / 1e6, 1), 'MB')


if __name__ == '__main__':
    main()
