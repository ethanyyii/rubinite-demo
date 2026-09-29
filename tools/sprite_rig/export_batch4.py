"""Batch 4 (docs/art-progress.md, "第 4 批").

    python3 tools/sprite_rig/export_batch4.py            everything
    python3 tools/sprite_rig/export_batch4.py sheets     sprite sheets, sequences and review sheets only (no scenes)

Writes (previews for review; nothing is wired into the game):
  assets/sprites/player/knight_<stagger, guard_break, getup>.png
                                           rows S / E / N / W (the stagger's row = the view facing
                                           the attacker; the get-up's = the program's facing)
  assets/sprites/player/knight_<knockdown, launch, getup_floor>.png
                                           row 1 = the attacker on the right, row 2 = on the left;
                                           the frames of one row come from different views
                                           (batch4.py). Death plays the knockdown's frames on
                                           batch4.DEATH's timing. All 56 x 56, foot anchor (28, 53)
  docs/art-preview/player/batch4/
    batch4_<action>_3x.png / _6x.png       every frame of every row
    batch4_<scene>.gif                     scenes at the simulation's timing (hitstop included), the
                                           camera following the character over a floor grid that
                                           moves with the program's knockback (one GIF frame per
                                           sim frame, 20 ms: 0.83x)
    batch4_player.html                     every scene at the true 60 fps
    batch4_head_check.png, batch4_onion.png, batch4_concept.png, batch4_motion.md
"""
import base64
import io
import json
import math
import os
import sys

from PIL import Image, ImageDraw

import pose_rig as PR
import batch1 as B1
import batch4 as B4
import export_poses as E
from export_poses import up, stack, hrow, label, FLOOR, SHADOW
from export_batch3 import save_gif, FLOOR2, TILE

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch4')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
KEY_ZH = dict(VIEW_ZH, **B4.ROW_ZH)
W_, H_, CX, GY = PR.CANVAS['small']
SHEET_NAMES = {'stagger': 'stagger', 'guard_break': 'guard_break', 'getup': 'getup',
               'knockdown': 'knockdown', 'launch': 'launch', 'getup_floor': 'getup_floor'}


def keys_of(action):
    return B4.VIEWS if action in B4.VIEW_ACTIONS else B4.ROWS


def src_frames(src, key):
    if src in B4.VIEW_ACTIONS or src in B4.ROW_ACTIONS:
        return B4.frames(src, key)
    return B1.frames(src, key)


def sheet_image(src):
    keys = keys_of(src) if (src in B4.VIEW_ACTIONS or src in B4.ROW_ACTIONS) else B4.VIEWS
    fr = {k: src_frames(src, k) for k in keys}
    cols = len(fr[keys[0]])
    sheet = Image.new('RGBA', (W_ * cols, H_ * len(keys)), (0, 0, 0, 0))
    for r, k in enumerate(keys):
        for c, f in enumerate(fr[k]):
            sheet.alpha_composite(PR.image(f.px, 'small'), (c * W_, r * H_))
    return sheet


def write_sheet(action):
    sheet = sheet_image(action)
    path = os.path.join(SHEETS, f'knight_{SHEET_NAMES[action]}.png')
    sheet.save(path)
    return path, sheet


def sequence(action, k):
    keys = keys_of(action)
    fr0 = B4.frames(action, keys[0])
    head = [label('', 150, 14, 40)] + [label(f'{f.name}\n{f.dur} 模擬幀', W_ * k, 14 if k < 5 else 18, 40) for f in fr0]
    rows = [label(f'{B4.TITLES[action]}（{k} 倍）', W_ * k * 5, 18 if k < 5 else 24, 34), hrow(head)]
    for key in keys:
        fr = B4.frames(action, key)
        tag = KEY_ZH[key]
        if key in B4.ROWS:
            seen = []
            for f in fr:
                z = VIEW_ZH.get(f.view, '躺')
                if z not in seen:
                    seen.append(z)
            tag += '\n' + '→'.join(seen)
        rows.append(hrow([label(tag, 150, 14, H_ * k)] + [E.cell(f.px, 'small', k) for f in fr]))
    return stack(rows, 4)


# ------------------------------------------------------------------ scenes
# A timeline row: (src, key, index, world x, world y, height). The camera follows the character
# (x, y); height lifts the picture off its shadow (the launch's arc: the program's to draw).
FWD = {'east': (1, 0), 'west': (-1, 0), 'south': (0, 1), 'north': (0, -1)}
HITSTOP = {'stagger': 4, 'knockdown': 5}          # feedback_data.gd: 0.06 / 0.08 s
LAUNCH_ARC = 16                                   # px at the top of the launch's arc (preview only)
BLOCK_PUSH = (8.0, 4)                             # player_data.gd: normal block 8 px over 4 sim frames


class TL:
    def __init__(self):
        self.rows, self.x, self.y = [], 0.0, 0.0

    def add(self, src, key, idx, n=1, move=(0.0, 0.0), step=0.0, h=0.0):
        for _ in range(n):
            self.x += move[0] * step
            self.y += move[1] * step
            self.rows.append((src, key, idx, self.x, self.y, h))

    def play(self, src, key, names=None, durs=None, move=(0.0, 0.0), steps=None):
        """Frames by name (all by default) for their own or the given durations; steps: the
        program's px per sim frame, one per sim frame played (missing = 0)."""
        fr = src_frames(src, key)
        names = names or [f.name for f in fr]
        by = {f.name: i for i, f in enumerate(fr)}
        q = 0
        for j, nm in enumerate(names):
            i = by[nm]
            d = durs[j] if durs else fr[i].dur
            for _ in range(d):
                st = steps[q] if steps and q < len(steps) else 0.0
                self.add(src, key, i, 1, move, st)
                q += 1


def away(view):
    fx, fy = FWD[view]
    return (-fx, -fy)


def scene_stagger(view):
    t = TL()
    t.add('idle', view, 0, 12)
    mv, st = away(view), 12.0 / 6
    # the hit frame: the first knockback step at once, then the hitstop holds the picture
    t.add('stagger', view, 0, 1, mv, st)
    t.add('stagger', view, 0, HITSTOP['stagger'])
    t.play('stagger', view, durs=[3, 9, 8], move=mv, steps=[st] * 5)
    t.add('idle', view, 0, 18)
    return t


def _knock_in(t, row, first_src, first_idx, dist=24.0):
    """The hit frame and the hitstop; returns the knockback's remaining steps."""
    fv = B4.FACING_VIEW[row]
    mv, st = away(fv), dist / 6
    t.add(first_src, row, first_idx, 1, mv, st)
    t.add(first_src, row, first_idx, HITSTOP['knockdown'])
    return mv, [st] * 5


def _getup(t, row, facing):
    t.play('getup_floor', row)
    t.play('getup', facing)
    t.add('idle', facing, 0, 18)


def scene_knockdown(row, facing):
    def build():
        t = TL()
        t.add('idle', facing, 0, 12)
        mv, steps = _knock_in(t, row, 'knockdown', 0)
        t.play('knockdown', row, durs=[1, 2, 2, 2, 3, 37], move=mv, steps=steps)
        _getup(t, row, facing)
        return t
    return build


def scene_launch(row):
    def build():
        facing = B4.FACING_VIEW[row]
        t = TL()
        t.add('idle', facing, 0, 12)
        fv = B4.FACING_VIEW[row]
        mv, st = away(fv), 64.0 / B4.LAUNCH_AIR
        t.add('launch', row, 0, 1, mv, st, h=_arc(0))
        t.add('launch', row, 0, HITSTOP['knockdown'], h=_arc(0))
        for i in range(1, B4.LAUNCH_AIR):
            t.add('launch', row, (i // 4) % 2, 1, mv, st, h=_arc(i))
        by = {f.name: j for j, f in enumerate(B4.frames('knockdown', row))}
        for nm, d in B4.LAUNCH_DOWN:
            t.add('knockdown', row, by[nm], d)
        _getup(t, row, facing)
        return t
    return build


def _arc(i):
    u = (i + 1) / B4.LAUNCH_AIR
    return 4 * LAUNCH_ARC * u * (1 - u)


def scene_guard_break(view):
    t = TL()
    t.play('guard', view, ['hold 1', 'hold 2', 'hold 3', 'hold 4'] * 2)
    mv, (dist, n) = away(view), BLOCK_PUSH
    sw = ['搖晃 1', '搖晃 2', '搖晃 3', '搖晃 4'] * 2
    names = ['膝蓋一軟 1', '膝蓋一軟 2', '單膝跪地'] + sw + ['撐起', '半站']
    t.play('guard_break', view, names, move=mv, steps=[dist / n] * n)
    t.add('idle', view, 0, 18)
    return t


def scene_break_hit(row):
    def build():
        facing = B4.FACING_VIEW[row]
        t = TL()
        t.play('guard', facing, ['hold 1', 'hold 2'])
        mv, (dist, n) = away(facing), BLOCK_PUSH
        t.play('guard_break', facing, ['膝蓋一軟 1', '膝蓋一軟 2', '單膝跪地', '搖晃 1', '搖晃 2', '搖晃 3'], move=mv, steps=[dist / n] * n)
        mv, steps = _knock_in(t, row, 'knockdown', 0)
        t.play('knockdown', row, durs=[1, 2, 2, 2, 3, 37], move=mv, steps=steps)
        _getup(t, row, facing)
        return t
    return build


def scene_death(row):
    def build():
        facing = B4.FACING_VIEW[row]
        t = TL()
        t.add('idle', facing, 0, 12)
        # death: no knockback (player_sim.gd); the knockdown's hitstop
        t.add('knockdown', row, 0, 1 + HITSTOP['knockdown'])
        by = {f.name: j for j, f in enumerate(B4.frames('knockdown', row))}
        first = True
        for nm, d in B4.DEATH:
            t.add('knockdown', row, by[nm], d - 1 if first else d)
            first = False
        t.add('knockdown', row, by['趴著'], 30)
        return t
    return build


def four(build_view):
    return [(VIEW_ZH[v] + '（攻擊來自這一側）', (lambda v=v: build_view(v))) for v in B4.VIEWS]


SCENES = [
    ('stagger', '踉蹌：待機 → 被打（頓幀 4）→ 踉蹌 21 幀（擊退 12px）→ 待機', four(scene_stagger)),
    ('knockdown', '倒地：待機 → 被打（頓幀 5）→ 轉身撲倒（擊退 24px）→ 趴著 → 起身（跪姿起換回面向）→ 待機',
     [('攻擊者在右，面向右', scene_knockdown('R', 'east')), ('攻擊者在左，面向左', scene_knockdown('L', 'west')),
      ('攻擊者在右，面向左（從背後被打）', scene_knockdown('R', 'west')), ('攻擊者在左，面向右（從背後被打）', scene_knockdown('L', 'east'))]),
    ('launch', '擊飛：被打（頓幀 5）→ 空中 21 幀（64px；高度弧線由程式畫，這裡示意 16px）→ 著地、趴著 36 幀 → 起身 → 待機',
     [('攻擊者在右', scene_launch('R')), ('攻擊者在左', scene_launch('L'))]),
    ('guard_break', '架勢崩潰：格擋 → 普通格擋把架勢打空（推後 8px）→ 崩潰 72 幀 → 待機', four(scene_guard_break)),
    ('break_hit', '架勢崩潰中被打：一律倒地 → 起身 → 待機',
     [('攻擊者在右', scene_break_hit('R')), ('攻擊者在左', scene_break_hit('L'))]),
    ('death', '死亡：被打（頓幀 5，不擊退）→ 倒地的幀、時間拉長，90 幀後停在趴著（淡出由程式做）',
     [('攻擊者在右', scene_death('R')), ('攻擊者在左', scene_death('L'))]),
]
CELL = (104, 88, 52, 70)        # scene cell: w, h, where the foot anchor sits


def frame_px(src, key, idx):
    return src_frames(src, key)[idx].px


def draw_cell(src, key, idx, x, y, h):
    cw, ch, ax, ay = CELL
    im = Image.new('RGBA', (cw, ch), FLOOR)
    d = ImageDraw.Draw(im)
    ox, oy = ax - round(x), ay - round(y)
    for gy in range(-TILE * 2, ch + TILE * 2, TILE):
        for gx in range(-TILE * 2, cw + TILE * 2, TILE):
            wx, wy = gx + (ox % TILE) - TILE, gy + (oy % TILE) - TILE
            if ((wx - ox) // TILE + (wy - oy) // TILE) % 2:
                d.rectangle((wx, wy, wx + TILE - 1, wy + TILE - 1), fill=FLOOR2)
    d.ellipse((ax - 12, ay - 2, ax + 12, ay + 3), fill=SHADOW)
    im.alpha_composite(PR.image(frame_px(src, key, idx), 'small'), (ax - CX, ay - GY - round(h)))
    return im


def scene_gif(name, title, cells, k=3):
    tls = [(lab, b()) for lab, b in cells]
    n = max(len(t.rows) for _, t in tls)
    cw = CELL[0]
    imgs = []
    for i in range(n):
        tiles = []
        for lab, t in tls:
            src, key, idx, x, y, h = t.rows[min(i, len(t.rows) - 1)]
            tiles.append(stack([label(lab, cw * k, 14, 24), up(draw_cell(src, key, idx, x, y, h), k)], 2))
        img = stack([label(f'{title}　GIF 每格 20ms（0.83 倍速；60fps 見 batch4_player.html）', max(cw * k * len(cells) + 18, 1200), 16, 30),
                     hrow(tiles)], 4)
        imgs.append(img.convert('RGB'))
    path = os.path.join(OUT, f'batch4_{name}.gif')
    save_gif(imgs, [20] * len(imgs), path)
    return path, tls


PLAYER = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>第 4 批動畫預覽</title>
<style>
:root { --bg:#1e1e22; --fg:#e8e6e1; --mute:#a9a59c; }
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:14px/1.5 -apple-system, "PingFang TC", "Noto Sans TC", sans-serif; }
h1 { font-size:18px; margin:0 0 4px; } p { margin:0 0 12px; color:var(--mute); }
.bar { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
button { background:#34343a; color:var(--fg); border:1px solid #55555c; border-radius:6px; padding:5px 10px; font:inherit; cursor:pointer; }
button.on { background:#e8e6e1; color:#1e1e22; }
.row { display:flex; gap:10px; flex-wrap:wrap; } .cell b { display:block; font-weight:600; margin-bottom:2px; }
canvas { image-rendering:pixelated; display:block; max-width:100%; }
#title { margin:6px 0 10px; }
</style></head><body>
<h1>第 4 批動畫預覽（60fps，照模擬幀時間，含頓幀）</h1>
<p>鏡頭跟著角色，地面格線照程式的擊退距離捲動。「慢放」是 0.25 倍，「下一幀」一次走一個模擬幀。</p>
<div class="bar" id="scenes"></div>
<div class="bar"><button id="pause">暫停</button><button id="slow">慢放 ×0.25</button><button id="step">下一幀</button><span id="clock" style="align-self:center;color:var(--mute)"></span></div>
<div id="title"></div>
<div class="row" id="cells"></div>
<script>
const DATA = __DATA__;
const K = 3, TILE = 16, CW = __CW__, CH = __CH__, AX = __AX__, AY = __AY__, FW = 56, FH = 56, FCX = 28, FGY = 53;
const imgs = {}; let loaded = 0;
for (const [k, uri] of Object.entries(DATA.sheets)) { const im = new Image(); im.onload = () => { if (++loaded === Object.keys(DATA.sheets).length) start(); }; im.src = uri; imgs[k] = im; }
let scene = 0, t = 0, acc = 0, last = null, paused = false, slow = false, ctxs = [];
function len() { return Math.max(...DATA.scenes[scene].cells.map(c => c.tl.length)); }
function build() {
  const bar = document.getElementById("scenes"); bar.innerHTML = "";
  DATA.scenes.forEach((s, i) => { const b = document.createElement("button"); b.textContent = s.name; b.classList.toggle("on", i === scene); b.onclick = () => { scene = i; t = 0; build(); }; bar.appendChild(b); });
  document.getElementById("title").textContent = DATA.scenes[scene].title;
  const row = document.getElementById("cells"); row.innerHTML = ""; ctxs = [];
  DATA.scenes[scene].cells.forEach(c => { const d = document.createElement("div"); d.className = "cell"; const b = document.createElement("b"); b.textContent = c.label; d.appendChild(b);
    const cv = document.createElement("canvas"); cv.width = CW * K; cv.height = CH * K; d.appendChild(cv); row.appendChild(d); ctxs.push(cv.getContext("2d")); });
  draw();
}
function draw() {
  const s = DATA.scenes[scene];
  document.getElementById("clock").textContent = `模擬幀 ${t} / ${len()}`;
  s.cells.forEach((c, j) => {
    const g = ctxs[j], r = c.tl[Math.min(t, c.tl.length - 1)];
    const [sheet, col, rw, x, y, h] = r;
    g.setTransform(K, 0, 0, K, 0, 0); g.imageSmoothingEnabled = false;
    g.fillStyle = "#e2dbcc"; g.fillRect(0, 0, CW, CH); g.fillStyle = "#d6cebe";
    const ox = AX - Math.round(x), oy = AY - Math.round(y);
    for (let gy = -2 * TILE; gy < CH + 2 * TILE; gy += TILE) for (let gx = -2 * TILE; gx < CW + 2 * TILE; gx += TILE) {
      const wx = gx + ((ox % TILE) + TILE) % TILE - TILE, wy = gy + ((oy % TILE) + TILE) % TILE - TILE;
      if ((((Math.floor((wx - ox) / TILE) + Math.floor((wy - oy) / TILE)) % 2) + 2) % 2) g.fillRect(wx, wy, TILE, TILE);
    }
    g.fillStyle = "#c4bcac"; g.beginPath(); g.ellipse(AX + 0.5, AY + 0.5, 12, 2.5, 0, 0, 7); g.fill();
    g.drawImage(imgs[sheet], col * FW, rw * FH, FW, FH, AX - FCX, AY - FGY - Math.round(h), FW, FH);
  });
}
function start() {
  build();
  document.getElementById("pause").onclick = e => { paused = !paused; e.target.textContent = paused ? "播放" : "暫停"; };
  document.getElementById("slow").onclick = e => { slow = !slow; e.target.classList.toggle("on", slow); };
  document.getElementById("step").onclick = () => { paused = true; document.getElementById("pause").textContent = "播放"; t = (t + 1) % len(); draw(); };
  requestAnimationFrame(tick);
}
function tick(now) {
  if (last === null) last = now; const dt = now - last; last = now;
  if (!paused) { acc += dt * (slow ? 0.25 : 1); while (acc >= 1000 / 60) { acc -= 1000 / 60; t = (t + 1) % len(); } draw(); }
  requestAnimationFrame(tick);
}
</script></body></html>
"""


def player(scene_tls):
    srcs = sorted({r[0] for _, _, tls in scene_tls for _, t in tls for r in t.rows})
    sheets = {}
    for src in srcs:
        buf = io.BytesIO()
        sheet_image(src).save(buf, 'PNG')
        sheets[src] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    scenes = []
    for name, title, tls in scene_tls:
        cells = []
        for lab, t in tls:
            rows = []
            for src, key, idx, x, y, h in t.rows:
                keys = keys_of(src) if (src in B4.VIEW_ACTIONS or src in B4.ROW_ACTIONS) else B4.VIEWS
                rows.append([src, idx, keys.index(key), round(x, 2), round(y, 2), round(h, 2)])
            cells.append(dict(label=lab, tl=rows))
        scenes.append(dict(name=name, title=title, cells=cells))
    cw, ch, ax, ay = CELL
    html = PLAYER.replace('__DATA__', json.dumps(dict(sheets=sheets, scenes=scenes), ensure_ascii=False)) \
                 .replace('__CW__', str(cw)).replace('__CH__', str(ch)).replace('__AX__', str(ax)).replace('__AY__', str(ay))
    path = os.path.join(OUT, 'batch4_player.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return path


SCENE_ZH = {'stagger': '踉蹌', 'knockdown': '倒地與起身', 'launch': '擊飛', 'guard_break': '架勢崩潰',
            'break_hit': '崩潰中被打', 'death': '死亡'}


# ------------------------------------------------------------------ review sheets
def every_frame():
    for action in list(B4.VIEW_ACTIONS) + list(B4.ROW_ACTIONS):
        for key in keys_of(action):
            yield action, key, B4.frames(action, key)


def head_check(k=6):
    from export_poses import enclosed_mask
    rows = [label('頸部以上：第 4 批每一幀（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區；躺姿看頭盔那一段）', 2400, 22, 34)]
    for action, key, fr in every_frame():
        cells = [label(f'{action}\n{KEY_ZH[key]}', 120, 14, 60)]
        for f in fr:
            helm = [q for q, n in f.trace.items() if n == 'helmet' and q in f.px]
            cut = max(y for _, y in helm) + 2
            x0 = max(0, min(x for x, _ in helm) - 12)
            x1 = min(W_, max(x for x, _ in helm) + 14)
            y0 = max(0, min(y for (x, y) in f.px if x0 <= x < x1) - 1)
            tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
            tile.alpha_composite(PR.image(f.px, 'small'))
            for (x, y) in enclosed_mask(f.px, W_, H_):
                if y < cut:
                    tile.putpixel((x, y), (255, 230, 0, 255))
            cells.append(up(tile.crop((x0, y0, x1, cut)), k))
        rows.append(hrow(cells))
    return stack(rows, 4)


def onion(pxs, k=6):
    im = Image.new('RGBA', (W_, H_), (240, 236, 228, 255))
    for px, tint in zip(pxs[:2], [(60, 120, 255), (230, 60, 60)]):
        lay = Image.new('RGBA', (W_, H_), (0, 0, 0, 0))
        for (x, y) in px:
            if 0 <= x < W_ and 0 <= y < H_:
                lay.putpixel((x, y), tint + (110,))
        im.alpha_composite(lay)
    return up(im, k)


ONION = [('stagger', 'f1 後仰', 'stagger', 'f2 退一步'), ('stagger', 'f3 回正', 'idle', 'idle 1'),
         ('knockdown', '踉蹌', 'knockdown', '撲倒'), ('knockdown', '撲倒', 'knockdown', '著地'),
         ('launch', '空中 2', 'knockdown', '著地'), ('knockdown', '趴著', 'getup_floor', '手膝撐地'),
         ('getup_floor', '起身 2', 'getup_floor', '起身 3'), ('getup', '跪姿', 'getup', '站起 1'),
         ('guard', 'hold 1', 'guard_break', '膝蓋一軟 1'), ('guard_break', '膝蓋一軟 2', 'guard_break', '單膝跪地'),
         ('guard_break', '搖晃 2', 'guard_break', '搖晃 4'), ('guard_break', '半站', 'idle', 'idle 1')]


def _named(src, key, name):
    return next(f for f in src_frames(src, key) if f.name == name)


def onion_sheet(k=5):
    rows = [label('洋蔥皮：藍＝前一張、紅＝後一張（5 倍）。兩列式動作用「攻擊者在右」那一列，四方向動作用朝右', 2000, 22, 34)]
    head = [label(f'{a[1]}\n→ {a[3]}', W_ * k, 16, 50) for a in ONION]
    rows.append(hrow([label('', 90, 14, 50)] + head))
    for key4, key2 in (('east', 'R'), ('west', 'L')):
        cells = [label(f'{VIEW_ZH[key4]}／{B4.ROW_ZH[key2]}', 90, 14, H_ * k)]
        for sa, na, sb, nb in ONION:
            ka = key2 if sa in B4.ROW_ACTIONS else key4
            kb = key2 if sb in B4.ROW_ACTIONS else key4
            if sa in B4.ROW_ACTIONS and sb not in B4.ROW_ACTIONS and sb != 'idle':
                kb = B4.AWAY_VIEW[key2]
            cells.append(onion([_named(sa, ka, na).px, _named(sb, kb, nb).px], k))
        rows.append(hrow(cells))
    return stack(rows, 4)


def concept_sheet(k=6):
    """Against the concept's thumbnails, same scale, the thumbnail's outline laid over
    (animation-review §4.6): F (stagger f1), G (kneel; partly the same pose), H (lying), H tilted
    (launched). East views / the attacker-on-the-right row."""
    items = [('F', '踉蹌 f1', B4.frames('stagger', 'east')[0].pose, False),
             ('G(部分)', '架勢崩潰 單膝跪地', B4.frames('guard_break', 'east')[2].pose, False),
             ('G(部分)', '起身 跪姿', B4.frames('getup', 'east')[0].pose, False),
             ('H', '倒地 趴著', dict(airborne=False), True),
             ('H', '擊飛 空中', dict(airborne=True), True)]
    rows = [label('設計圖對照（同比例，洋紅＝設計圖小圖的輪廓，標重疊率）', 1600, 22, 34)]
    cells = []
    for ref, nm, pose, lying in items:
        th = E.thumb(ref, k, None if lying else nm, None if lying else pose, 'small')
        if pose.get('airborne'):
            # H tipped 14 deg: the flat H's outline laid over it measures nothing (batch 0's 23 %)
            px = B4.frames('launch', 'R')[0].px
            cells.append(stack([label(f'{nm}／{ref}（H 傾斜 14°，不疊輪廓）', W_ * k * 2, 18, 30), hrow([th, E.cell(px, 'small', k)])], 2))
            continue
        ov, match = E.overlay_cell(nm, pose, 'small', ref, k, lying)
        cells.append(stack([label(f'{nm}／{ref}　重疊 {round(100 * match)} %', W_ * k * 2, 18, 30), hrow([th, ov])], 2))
    rows.append(hrow(cells[:3]))
    rows.append(hrow(cells[3:]))
    return stack(rows, 4)


def motion_table():
    import export_batch1 as X1
    lines = ['# 第 4 批逐部件動作表', '',
             '由 `tools/sprite_rig/export_batch4.py` 產生（animation-review §5）。座標是 56×56 畫格的像素，y 往下為正。',
             '「骨盆 y」「頭盔頂 y」對照頭晚一拍；布料末端是離頭盔中心最遠的那一點。躺姿、擊飛是設計圖 H 還原的，沒有骨架數字，只列頭盔頂與兩腳。', '']
    for action, key, fr in every_frame():
        lines += [f'## {B4.TITLES[action]}・{KEY_ZH[key]}', '',
                  '| 幀 | 視角 | 模擬幀 | 前傾° | 骨盆 y | 頭盔頂 y | 右拳 | 左拳 | 劍尖 | 兩腳 | 羽飾末端 | 披風末端 |',
                  '|---|---|---|---|---|---|---|---|---|---|---|---|']
        t = 0
        for f in fr:
            m = X1.metrics(f)
            lean = f.pose.get('lean', 0) if f.pose else 0
            pel = f'{f.debug["pelvis"][1]:.1f}' if f.debug.get('pelvis') else '–'
            legs = f.debug.get('legs') or {}
            feet = ' / '.join(f'{kk} {v[2][0]:.1f}' for kk, v in sorted(legs.items())) or '–'
            lines.append(f'| {f.name} | {VIEW_ZH.get(f.view, "躺（H）")} | {t}–{t + f.dur - 1} | {lean:.0f} | {pel} | {X1.fmt(m["helmet_top"])} | '
                         f'{X1.fmt(m["fist_R"])} | {X1.fmt(m["fist_L"])} | {X1.fmt(m.get("tip") or f.debug.get("tip"))} | {feet} | '
                         f'{X1.fmt(m.get("plume_tip"))} | {X1.fmt(m.get("cape_tip"))} |')
            t += f.dur
        lines.append('')
    return '\n'.join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1:] or ['all']
    for action in SHEET_NAMES:
        path, sheet = write_sheet(action)
        print('sheet', os.path.relpath(path, ROOT), sheet.size)
    for action in SHEET_NAMES:
        for k in (3, 6):
            sequence(action, k).save(os.path.join(OUT, f'batch4_{action}_{k}x.png'))
    print('wrote sequences')
    head_check().save(os.path.join(OUT, 'batch4_head_check.png'))
    onion_sheet().save(os.path.join(OUT, 'batch4_onion.png'))
    concept_sheet().save(os.path.join(OUT, 'batch4_concept.png'))
    with open(os.path.join(OUT, 'batch4_motion.md'), 'w', encoding='utf-8') as fh:
        fh.write(motion_table())
    print('wrote review sheets and the motion table')
    if 'sheets' in what:
        return
    scene_tls = []
    for name, title, cells in SCENES:
        path, tls = scene_gif(name, title, cells)
        scene_tls.append((SCENE_ZH[name], title, tls))
        print('wrote', os.path.relpath(path, ROOT))
    print('wrote', os.path.relpath(player(scene_tls), ROOT))


if __name__ == '__main__':
    main()
