"""The four-hit light combo, second version (docs/art-progress.md, "四段輕攻擊：第二版"; combo4.py).

    python3 tools/sprite_rig/export_combo4.py

Writes (previews for review; nothing is wired into the game):
  assets/sprites/player/knight_attack{1,2,3,4}.png
      sprite sheets, rows S / E / N / W, 88 x 72 cells, foot anchor (44, 61); columns as in
      combo4.STAGES, then (stages 2-4) the entry from the stance (combo4.ENTRY)
  docs/art-preview/player/combo4/
    combo4_stage<n>_3x.png / _6x.png   every frame x four views, labelled with its sim frames, the
                                       program's advance when it shows and, for a turned body, which
                                       view the upper body (or the whole figure) is drawn from
    combo4_silhouettes.png             the four stages' wind-ups and finishes side by side, as drawn and
                                       as black outlines, with the pairwise outline differences
    combo4_legs.png                    the legs alone, hip-knee-ankle lines, every frame
    combo4_<scene>.gif                 four views side by side, one GIF frame a sim frame (20 ms:
                                       0.83x); the camera follows the character, the floor scrolls
                                       with the program's advance, the picture catches up when the
                                       sprite frame changes (batch 2 decision 2)
    combo4_player.html                 the same scenes at the true 60 fps (pause, 0.25x, step)
    combo4_compare.png                 stage 4, the fourth version (the turn, then the cut) and this one
                                       (the hit inside the turn), frame by frame with sim frames
    combo4_head_check.png              above the neck, every frame
    combo4_concept.png                 the east view against the concept's C1-C4 / D2 / D3 (reference
                                       only: the user's move design is the target now), outline overlap %
"""
import base64
import io
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

import pose_rig as PR
import batch1 as B1
import combo4 as C4
import export_poses as E
from export_poses import up, stack, hrow, label, FLOOR, SHADOW, BG

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'combo4')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
W_, H_, CX, GY = PR.CANVAS['large']
SW_, SH_, SCX, SGY = PR.CANVAS['small']
FLOOR2 = (214, 206, 190, 255)
TILE = 16


def columns(stage, view):
    """The frames of a stage's sheet, in column order: the stage, then its entry from the stance."""
    fr = list(C4.frames(stage, view))
    if stage in C4.ENTRY:
        fr += list(C4.frames(stage, view, entry_frames=True))
    return fr


def sheet_image(stage):
    fr = {v: columns(stage, v) for v in C4.VIEWS}
    cols = len(fr['south'])
    sheet = Image.new('RGBA', (W_ * cols, H_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(C4.VIEWS):
        for c, f in enumerate(fr[v]):
            sheet.alpha_composite(PR.image(f.px, 'large'), (c * W_, r * H_))
    return sheet


def idle_sheet():
    im = Image.new('RGBA', (SW_, SH_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(C4.VIEWS):
        im.alpha_composite(PR.image(B1.frames('idle', v)[0].px, 'small'), (0, r * SH_))
    return im


def write_sheets():
    out = []
    for st in (1, 2, 3, 4):
        im = sheet_image(st)
        path = os.path.join(SHEETS, f'knight_{C4.SHEETS[st]}.png')
        im.save(path)
        out.append(f'{os.path.relpath(path, ROOT)} {im.size}')
    return out


def cell(px, k):
    return E.cell(px, 'large', k)


def sequence(stage, k):
    cw = W_ * k
    fr0 = columns(stage, 'south')
    head = [label('', 70, 14, 40)] + [label(f'{f.name}\n{f.first}–{f.last}　前進 {f.adv:.1f}px', cw, 14 if k < 5 else 18, 40)
                                      for f in fr0]
    rows = [label(f'{C4.TITLES[stage]}（{k} 倍；模擬幀 60Hz；「前進」是這張出現時程式已前進的距離，畫面在換圖時跟上；'
                  f'身體扭轉的幾張標出上半身用哪個方向的圖，第 4 段轉身的幾張標出整個人從哪個方向畫）', cw * 6, 18 if k < 5 else 24, 34), hrow(head)]
    for v in C4.VIEWS:
        cells = [label(VIEW_ZH[v], 70, 16, H_ * k)]
        for f in columns(stage, v):
            c = cell(f.px, k)
            note = turn_note(f, v)
            if note:
                d = ImageDraw.Draw(c)
                d.text((4, 2), note, font=E.font(12 if k < 5 else 18), fill=(90, 70, 40, 255))
            cells.append(c)
        rows.append(hrow(cells))
    return stack(rows, 4)


def turn_note(f, v):
    if f.draw_view != v:
        return f'（整個人：{VIEW_ZH[f.draw_view]}的圖）'
    if f.upper_view != v:
        return f'（上半身：{VIEW_ZH[f.upper_view]}的圖）'
    return ''


def legs_sheet(k=6, box=(12, 34, 76, 66)):
    x0, y0, x1, y1 = box
    rows = [label('腿單獨畫出來（髖、膝、踝連線；每一幀、四個方向）：側面膝蓋在髖下方 ≥ 腿高 10%、近側腿 ≤ 1.0、遠側 ≤ 1.1 倍腿長；正面／背面每條腿 ≥ 2px',
                  2400, 20, 34)]
    for st in (1, 2, 3, 4):
        for v in C4.VIEWS:
            cells = [label(f'第 {st} 段\n{VIEW_ZH[v]}', 90, 14, (y1 - y0) * k)]
            for f in columns(st, v):
                im = Image.new('RGBA', (W_, H_), BG)
                for n in ('leg_R', 'leg_L'):
                    for (x, y), c in f.pieces_raw.get(n, {}).items():
                        if 0 <= x < W_ and 0 <= y < H_:
                            im.putpixel((x, y), c)
                im = im.crop(box).resize(((x1 - x0) * k, (y1 - y0) * k), Image.NEAREST)
                d = ImageDraw.Draw(im)
                d.line([(0, (GY + 1 - y0) * k), (im.width, (GY + 1 - y0) * k)], fill=(160, 150, 130, 255))
                for _, (h, kn, a) in f.debug['legs'].items():
                    d.line([((q[0] - x0) * k, (q[1] - y0) * k) for q in (h, kn, a)], fill=(220, 40, 40, 255), width=2)
                cells.append(im)
            rows.append(hrow(cells))
    return stack(rows, 3)


# ------------------------------------------------------------------ scenes
class TL:
    """One timeline per view: per sim frame (sheet key, column, row, camera x, camera y, picture dx, dy)."""

    def __init__(self, view):
        self.view = view
        self.rows = []
        self.base = 0.0            # the program's position (px along the facing) where the stage began

    def idle(self, n):
        fx, fy = C4.FWD_SCREEN[self.view]
        for _ in range(n):
            self.rows.append(('idle', 0, C4.VIEWS.index(self.view), fx * self.base, fy * self.base, 0.0, 0.0))

    def stage(self, st, until=None, entry=False):
        """Play a stage from sim frame 0 up to (not including) `until` (default: to its end); with
        entry, its first frame(s) are the entry from the stance."""
        fx, fy = C4.FWD_SCREEN[self.view]
        main = C4.frames(st, self.view)
        ent = C4.frames(st, self.view, entry_frames=True) if entry else []
        seq = [(i, f) for i, f in enumerate(main)]
        if entry:
            n = C4.ENTRY[st]
            seq = [(len(main) + i, f) for i, f in enumerate(ent)] + seq[n:]
        end = C4.ATTACK[st][2] if until is None else until
        row = C4.VIEWS.index(self.view)
        for e in range(end):
            col, f = next((c, f) for c, f in seq if f.first <= e <= f.last)
            prog = self.base + C4.advance_at(st, e)
            pic = self.base + f.adv
            self.rows.append((f'attack{st}', col, row, fx * prog, fy * prog, fx * (pic - prog), fy * (pic - prog)))
        self.base += C4.ATTACK[st][3]


def chain_at(st):
    return C4.CHAIN[st]


# The fourth version (delivered 2026-09-29; the user then: "在轉身之後還揮了一刀……中間還是間隔了"): stage 3
# chained on frame 12 and stage 4 took 10 frames to its hit - the whole turn, then a cut facing the target.
# Stages 1-3 are drawn the same; its stage 4 plays from its sheet kept in v4/.
PREV_DIR = os.path.join(OUT, 'v4')
PREV_CHAIN3 = 12
PREV_ATTACK4 = (10, 6, 55, 14.0)
PREV_STAGE4 = [(0, 1), (2, 4), (5, 7), (8, 9), (10, 12), (13, 14), (15, 17), (18, 24), (25, 30), (31, 35), (36, 40),
               (41, 45), (46, 50), (51, 54)]
PREV_NAMES4 = ['起轉', '轉身 1', '背對', '轉身 3', '接觸', '揮出', '揮完']


def _prev_advance4(e):
    a0, n, _, total = PREV_ATTACK4
    return 0.0 if e < a0 else total * min(n, e - a0 + 1) / n


def scene_mash_prev(view):
    """The mash as the fourth version played it (for comparison): the whole turn, then the cut."""
    t = TL(view)
    t.idle(20)
    for st in (1, 2):
        t.stage(st, chain_at(st))
    t.stage(3, PREV_CHAIN3)
    fx, fy = C4.FWD_SCREEN[view]
    row = C4.VIEWS.index(view)
    for e in range(PREV_ATTACK4[2]):
        col, (a, _) = next((c, r) for c, r in enumerate(PREV_STAGE4) if r[0] <= e <= r[1])
        prog, pic = t.base + _prev_advance4(e), t.base + _prev_advance4(a)
        t.rows.append(('prevattack4', col, row, fx * prog, fy * prog, fx * (pic - prog), fy * (pic - prog)))
    t.base += PREV_ATTACK4[3]
    t.stage(1)
    t.idle(30)
    return t


def scene_mash(view):
    t = TL(view)
    t.idle(20)
    for st in (1, 2, 3):
        t.stage(st, chain_at(st))
    t.stage(4)
    t.stage(1)
    t.idle(30)
    return t


def scene_slow(view):
    """A slower rhythm: each stage plays out and the next is pressed in the idle (the grace)."""
    t = TL(view)
    t.idle(20)
    t.stage(1)
    t.idle(6)
    t.stage(2, entry=True)
    t.idle(6)
    t.stage(3, entry=True)
    t.idle(6)
    t.stage(4, entry=True)
    t.idle(30)
    return t


def scene_one(st):
    def build(view):
        t = TL(view)
        t.idle(20)
        t.stage(st, entry=st > 1)
        t.idle(30)
        return t
    return build


SCENES = [('mash', '連按（這一版）：四刀每 0.25 秒一刀，第 4 刀在轉身中砍到（側身時劍掃過），轉完就停，停頓後再從第 1 段開始', scene_mash),
          ('mash_prev', '連按（上一版，對照）：同樣每 0.25 秒一刀，第 4 段先轉一圈、轉回來才砍', scene_mash_prev),
          ('slow', '慢節奏：每段收完才按（收招後 0.2 秒內的接段寬限），第 2–4 段用「從站姿」的開頭', scene_slow),
          ('stage1', '第 1 段：右下→左上斜斬（最快、最短的起手）', scene_one(1)),
          ('stage2', '第 2 段：左→右橫斬（從站姿開始）', scene_one(2)),
          ('stage3', '第 3 段：由下往上挑斬（從站姿開始）', scene_one(3)),
          ('stage4', '第 4 段：回旋斬（轉身中砍到）＋停頓（從站姿開始）', scene_one(4))]

CELL = (150, 110, 75, 80)          # scene cell: width, height, where the foot anchor sits


def _sheets():
    if not hasattr(_sheets, 'cache'):
        _sheets.cache = {f'attack{st}': sheet_image(st) for st in (1, 2, 3, 4)}
        _sheets.cache['idle'] = idle_sheet()
        prev = os.path.join(PREV_DIR, 'knight_attack4.png')
        if os.path.exists(prev):
            _sheets.cache['prevattack4'] = Image.open(prev).convert('RGBA')
    return _sheets.cache


def draw_cell(r):
    key, col, row, cx, cy, dx, dy = r
    cw, ch, ax, ay = CELL
    im = Image.new('RGBA', (cw, ch), FLOOR)
    d = ImageDraw.Draw(im)
    ox, oy = ax - round(cx), ay - round(cy)
    for gy in range(-TILE * 2, ch + TILE * 2, TILE):
        for gx in range(-TILE * 2, cw + TILE * 2, TILE):
            wx, wy = gx + (ox % TILE) - TILE, gy + (oy % TILE) - TILE
            if ((wx - ox) // TILE + (wy - oy) // TILE) % 2:
                d.rectangle((wx, wy, wx + TILE - 1, wy + TILE - 1), fill=FLOOR2)
    d.ellipse((ax - 12, ay - 2, ax + 12, ay + 3), fill=SHADOW)
    sh = _sheets()[key]
    fw, fh, fcx, fgy = (SW_, SH_, SCX, SGY) if key == 'idle' else (W_, H_, CX, GY)
    spr = sh.crop((col * fw, row * fh, col * fw + fw, row * fh + fh))
    im.alpha_composite(spr, (ax - fcx + round(dx), ay - fgy + round(dy)))
    return im


def save_gif(images, durations, path, colors=128):
    stack_ = Image.new('RGB', (images[0].width, images[0].height * len(images)))
    for i, g in enumerate(images):
        stack_.paste(g, (0, i * g.height))
    pal = stack_.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, disposal=1)


def scene_gif(name, title, build, k=3):
    tls = [(VIEW_ZH[v], build(v)) for v in C4.VIEWS]
    n = max(len(t.rows) for _, t in tls)
    cw = CELL[0]
    imgs = []
    for i in range(n):
        tiles = [stack([label(lab, cw * k, 14, 24), up(draw_cell(t.rows[min(i, len(t.rows) - 1)]), k)], 2) for lab, t in tls]
        img = stack([label(f'{title}　GIF 每格 20ms（0.83 倍速；60fps 見 combo4_player.html）　模擬幀 {i}',
                           max(cw * k * 4 + 18, 1200), 16, 30), hrow(tiles)], 4)
        imgs.append(img.convert('RGB'))
    path = os.path.join(OUT, f'combo4_{name}.gif')
    save_gif(imgs, [20] * len(imgs), path)
    return tls


PLAYER = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>四段輕攻擊預覽</title>
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
<h1>四段輕攻擊預覽（60fps，照模擬幀時間；不含頓幀）</h1>
<p>鏡頭跟著角色，地面格線照程式的前進捲動；角色的圖在換圖那一幀才跟上程式的位置（站在地上的腳因此不滑）。「慢放」是 0.25 倍，「下一幀」一次走一個模擬幀。</p>
<div class="bar" id="scenes"></div>
<div class="bar"><button id="pause">暫停</button><button id="slow">慢放 ×0.25</button><button id="step">下一幀</button><span id="clock" style="align-self:center;color:var(--mute)"></span></div>
<div id="title"></div>
<div class="row" id="cells"></div>
<script>
const DATA = __DATA__;
const K = 3, TILE = 16, CW = __CW__, CH = __CH__, AX = __AX__, AY = __AY__;
const FR = {idle: [56, 56, 28, 53], attack: [88, 72, 44, 61]};
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
    const [sheet, col, rw, x, y, dx, dy] = r;
    g.setTransform(K, 0, 0, K, 0, 0); g.imageSmoothingEnabled = false;
    g.fillStyle = "#e2dbcc"; g.fillRect(0, 0, CW, CH); g.fillStyle = "#d6cebe";
    const ox = AX - Math.round(x), oy = AY - Math.round(y);
    for (let gy = -2 * TILE; gy < CH + 2 * TILE; gy += TILE) for (let gx = -2 * TILE; gx < CW + 2 * TILE; gx += TILE) {
      const wx = gx + ((ox % TILE) + TILE) % TILE - TILE, wy = gy + ((oy % TILE) + TILE) % TILE - TILE;
      if ((((Math.floor((wx - ox) / TILE) + Math.floor((wy - oy) / TILE)) % 2) + 2) % 2) g.fillRect(wx, wy, TILE, TILE);
    }
    g.fillStyle = "#c4bcac"; g.beginPath(); g.ellipse(AX + 0.5, AY + 0.5, 12, 2.5, 0, 0, 7); g.fill();
    const [fw, fh, fcx, fgy] = sheet === "idle" ? FR.idle : FR.attack;
    g.drawImage(imgs[sheet], col * fw, rw * fh, fw, fh, AX - fcx + Math.round(dx), AY - fgy + Math.round(dy), fw, fh);
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
    sheets = {}
    for key, im in _sheets().items():
        buf = io.BytesIO()
        im.save(buf, 'PNG')
        sheets[key] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    scenes = []
    for name, title, tls in scene_tls:
        cells = [dict(label=lab, tl=[[r[0], r[1], r[2]] + [round(v, 2) for v in r[3:]] for r in t.rows]) for lab, t in tls]
        scenes.append(dict(name=name, title=title, cells=cells))
    cw, ch, ax, ay = CELL
    html = PLAYER.replace('__DATA__', json.dumps(dict(sheets=sheets, scenes=scenes), ensure_ascii=False)) \
                 .replace('__CW__', str(cw)).replace('__CH__', str(ch)).replace('__AX__', str(ax)).replace('__AY__', str(ay))
    path = os.path.join(OUT, 'combo4_player.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return path


# ------------------------------------------------------------------ review sheets
def compare_sheet(k=3):
    """Stage 4, the fourth version and this one, frame by frame up to the finish, with their sim frames: the
    whole turn used to come before the cut; now the hit is inside the turn."""
    rows = [label('第 4 段：上一版（先轉一圈、轉回來才砍，第 10 幀砍到）和這一版（起手短、轉身中側身時砍到，第 6 幀），到揮完為止；'
                  '每張標出模擬幀，紅框是砍到的那張', 2600, 20, 34)]
    path = os.path.join(PREV_DIR, 'knight_attack4.png')
    old = Image.open(path).convert('RGBA') if os.path.exists(path) else None
    for r, v in enumerate(C4.VIEWS):
        if old is not None:
            cells = [label(f'{VIEW_ZH[v]}\n上一版', 90, 14, H_ * k + 20)]
            for c, nm in enumerate(PREV_NAMES4):
                t = Image.new('RGBA', (W_, H_), (205, 198, 184, 255))
                t.alpha_composite(old.crop((c * W_, r * H_, c * W_ + W_, r * H_ + H_)))
                im = up(t, k)
                if nm == '接觸':
                    ImageDraw.Draw(im).rectangle((0, 0, im.width - 1, im.height - 1), outline=(200, 30, 30, 255), width=3)
                a, b = PREV_STAGE4[c]
                cells.append(stack([label(f'{nm} {a}–{b}', W_ * k, 13, 20), im], 0))
            rows.append(hrow(cells))
        cells = [label(f'{VIEW_ZH[v]}\n這一版', 90, 14, H_ * k + 20)]
        for f in C4.frames(4, v):
            im = cell(f.px, k)
            if C4_CONTACT in f.name:
                ImageDraw.Draw(im).rectangle((0, 0, im.width - 1, im.height - 1), outline=(200, 30, 30, 255), width=3)
            cells.append(stack([label(f"{' '.join(f.name.split()[1:])} {f.first}–{f.last}", W_ * k, 13, 20), im], 0))
            if f.name == FINISH4:
                break
        rows.append(hrow(cells))
    return stack(rows, 3)


FINISH4 = 'f7 揮完'
C4_CONTACT = '接觸'


def silhouette_sheet(k=3):
    """The user's test: can a player tell the stage by its outline alone? Wind-ups and finishes of the four
    stages side by side, drawn and black, per view, with the pairwise outline differences
    (checks.outline_shift_share on the whole outline; >= 12 % counts as different)."""
    import checks as C
    import checks_combo4 as K
    rows = [label('只看剪影分得出第幾段嗎：每段的起手與收尾，上排是圖、下排是全黑的輪廓；右邊是兩兩的輪廓差（≥ 12% 算不同，'
                  '相似的姿勢例如走路相鄰兩張是 3% 以下）', 2600, 20, 34)]
    for what, table in (('起手', K.SIGNATURE), ('收尾', K.FINISH)):
        for v in C4.VIEWS:
            fr = {st: next(f for f in C4.frames(st, v) if f.name == table[st]) for st in (1, 2, 3, 4)}
            pics, sils = [label(f'{what}\n{VIEW_ZH[v]}', 70, 14, H_ * k)], [label('', 70, 14, H_ * k)]
            for st in (1, 2, 3, 4):
                f = fr[st]
                pics.append(stack([label(f'第 {st} 段 {f.name}', W_ * k, 13, 20), cell(f.px, k)], 0))
                sil = Image.new('RGBA', (W_, H_), (255, 255, 255, 255))
                for q in f.px:
                    if 0 <= q[0] < W_ and 0 <= q[1] < H_:
                        sil.putpixel(q, (0, 0, 0, 255))
                sils.append(stack([label('', W_ * k, 13, 20), up(sil, k)], 0))
            full = {st: set(f.px) for st, f in fr.items()}
            lines = []
            for a_ in (1, 2, 3, 4):
                for b_ in range(a_ + 1, 5):
                    o = C.outline_shift_share(full[a_], full[b_])
                    lines.append(f'{a_}–{b_}：{round(100 * o)}%' + ('' if o >= C.OUTLINE_DIFF_MIN else '（相近）'))
            rows.append(hrow(pics + [label('\n'.join(lines[:3]), 150, 15, H_ * k + 20)]))
            rows.append(hrow(sils + [label('\n'.join(lines[3:]), 150, 15, H_ * k + 20)]))
    return stack(rows, 3)


# animation-review §4.6: the concept's normal attack C1-C4 and skill attack D2 / D3, against the closest
# frames of the east view. The user's move design (2026-09-29) is the target now; these are reference.
CONCEPT_FRAMES = [('C1', 1, 'f1 壓低'), ('C2', 1, 'f4 接觸'), ('C3', 1, 'f6 揮完'), ('C4', 1, 'f9 回站姿 2'),
                  ('D2', 4, 'f4 接觸'), ('D3', 4, 'f7 揮完')]


def _overlay(f, ref, k):
    """The frame with the thumbnail's outline laid over it (feet on feet), and the silhouettes' overlap."""
    ours = {q for q in f.px if 0 <= q[0] < W_ and 0 <= q[1] < H_}
    theirs = E.concept_outline(ref)
    fx, low = E.feet_centre(theirs)
    ox, _ = E.feet_centre(ours)
    dx, dy = round(ox - fx), GY - low
    moved = {(x + dx, y + dy) for x, y in theirs}
    edge = {(x, y) for (x, y) in moved if any(q not in moved for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))}
    im = cell(f.px, k)
    d = ImageDraw.Draw(im)
    for (x, y) in edge:
        if 0 <= x < W_ and 0 <= y < H_:
            d.rectangle((x * k, y * k, x * k + k - 1, y * k + k - 1), fill=E.MAGENTA)
    return im, len(ours & moved) / len(ours | moved)


def concept_sheet(k=4):
    rows = [label('設計圖對照（朝右）：左＝設計圖小圖，右＝成品疊上小圖輪廓（洋紅），數字是兩個輪廓的重疊率。'
                  '這一版照使用者的動作設計做，設計圖的普通攻擊 C1–C4、技能攻擊 D2／D3 只當參考', 2000, 18, 34)]
    for ref, st, name in CONCEPT_FRAMES:
        f = next(f for f in C4.frames(st, 'east') if f.name == name)
        th = E.thumb(ref, k)
        tc = Image.new('RGBA', (E.TW, H_ * k), BG)
        if th is not None:
            tc.alpha_composite(th, (max(0, (E.TW - th.width) // 2), max(0, H_ * k - th.height)))
        ov, match = _overlay(f, ref, k)
        rows.append(hrow([label(f'{ref}\n第 {st} 段 {f.name}\n重疊 {round(100 * match)}%', 170, 16, H_ * k), tc, ov]))
    return stack(rows, 6)


def head_check(k=5):
    rows = [label('頸部以上：每一幀（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區）', 1800, 22, 34)]
    for st in (1, 2, 3, 4):
        for v in C4.VIEWS:
            cells = [label(f'第 {st} 段\n{VIEW_ZH[v]}', 90, 14, 60)]
            for f in columns(st, v):
                helm = [q for q, n in f.trace.items() if n == 'helmet']
                cut = max(y for _, y in helm) + 2
                x0 = max(0, min(x for x, _ in helm) - 12)
                x1 = min(W_, max(x for x, _ in helm) + 14)
                y0 = max(0, min(y for (x, y) in f.px if x0 <= x < x1) - 1)
                tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
                tile.alpha_composite(PR.image(f.px, 'large'))
                for (x, y) in E.enclosed_mask(f.px, W_, H_):
                    if y < cut:
                        tile.putpixel((x, y), (255, 230, 0, 255))
                cells.append(up(tile.crop((x0, y0, x1, cut)), k))
            rows.append(hrow(cells))
    return stack(rows, 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    wrote = write_sheets()
    for st in (1, 2, 3, 4):
        for k in (3, 6):
            sequence(st, k).save(os.path.join(OUT, f'combo4_stage{st}_{k}x.png'))
    legs_sheet().save(os.path.join(OUT, 'combo4_legs.png'))
    compare_sheet().save(os.path.join(OUT, 'combo4_compare.png'))
    silhouette_sheet().save(os.path.join(OUT, 'combo4_silhouettes.png'))
    head_check().save(os.path.join(OUT, 'combo4_head_check.png'))
    concept_sheet().save(os.path.join(OUT, 'combo4_concept.png'))
    scene_tls = []
    for name, title, build in SCENES:
        scene_tls.append((name, title, scene_gif(name, title, build)))
    player(scene_tls)
    print('\n'.join(wrote))
    print('previews in', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    sys.exit(main())
