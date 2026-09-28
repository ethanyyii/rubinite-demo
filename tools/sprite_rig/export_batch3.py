"""Batch 3 (docs/art-progress.md, "第 3 批").

    python3 tools/sprite_rig/export_batch3.py            everything
    python3 tools/sprite_rig/export_batch3.py run        the run sheet and its 2 / 3 / 4 comparison only

Writes (previews for review; nothing is wired into the game):
  assets/sprites/player/knight_<run, charge, charge_walk, thrust, execute, dash, backstep,
      walk_locked>.png                     rows S / E / N / W; columns as in batch3.ACTIONS;
                                           56 x 56 (28, 53) or 88 x 72 (44, 61) as batch3.CANVAS
  docs/art-preview/player/batch3/
    batch3_<action>_3x.png / _6x.png       every frame x four views
    batch3_<scene>.gif                     scenes at the simulation's timing, the camera following the
                                           character over a floor grid that moves at the program's
                                           speed (one GIF frame per sim frame, 20 ms: 0.83x)
    batch3_player.html                     every scene at the true 60 fps
    batch3_head_check.png, batch3_onion.png, batch3_outlines.png, batch3_concept.png, batch3_motion.md
    batch3_run_compare_<view>.gif          decision 1: the same eight frames held 2 / 3 / 4 sim
                                           frames each, the character crossing a floor grid at
                                           the program's 160 px/s, one GIF frame per sim frame
                                           (20 ms: a GIF cannot show 60 fps, so 0.83x speed)
    batch3_run_compare.html                the same at the true 60 fps (canvas, all four views)
    batch3_run_3x.png / _6x.png            the eight frames x four views
"""
import base64
import io
import os
import sys

from PIL import Image, ImageDraw

import pose_rig as PR
import batch3 as B3
import export_poses as E
from export_poses import up, stack, hrow, label, FLOOR, SHADOW, BG

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SHEETS = os.path.join(ROOT, 'assets', 'sprites', 'player')
OUT = os.path.join(ROOT, 'docs', 'art-preview', 'player', 'batch3')
VIEW_ZH = {'south': '朝下', 'east': '朝右', 'north': '朝上', 'west': '朝左'}
TILE = 16                                     # floor grid, px
FLOOR2 = (214, 206, 190, 255)


def write_sheet(action, name):
    canvas = B3.CANVAS[action]
    W_, H_, _, _ = PR.CANVAS[canvas]
    fr = {v: B3.frames(action, v) for v in B3.VIEWS}
    cols = len(fr['south'])
    sheet = Image.new('RGBA', (W_ * cols, H_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(B3.VIEWS):
        for c, f in enumerate(fr[v]):
            sheet.alpha_composite(PR.image(f.px, canvas), (c * W_, r * H_))
    path = os.path.join(SHEETS, f'knight_{name}.png')
    sheet.save(path)
    return path, sheet


def sequence(action, k, note=''):
    canvas = B3.CANVAS[action]
    W_ = PR.CANVAS[canvas][0]
    fr0 = B3.frames(action, 'south')
    head = [label('', 70, 14, 40)] + [label(f'{f.name}\n{f.dur} 模擬幀', W_ * k, 14 if k < 5 else 18, 40) for f in fr0]
    rows = [label(f'{B3.TITLES[action]}（{k} 倍）{note}', W_ * k * 5, 18 if k < 5 else 24, 34), hrow(head)]
    for v in B3.VIEWS:
        rows.append(hrow([label(VIEW_ZH[v], 70, 16, PR.CANVAS[canvas][1] * k)] +
                         [E.cell(f.px, canvas, k) for f in B3.frames(action, v)]))
    return stack(rows, 4)


def save_gif(images, durations, path, colors=128):
    stack_ = Image.new('RGB', (images[0].width, images[0].height * min(len(images), 12)))
    step = max(1, len(images) // 12)
    for i, g in enumerate(images[::step][:12]):
        stack_.paste(g, (0, i * g.height))
    pal = stack_.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in images]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, disposal=1)


def floor(im):
    """A checker floor fixed to the world (the camera does not move in these previews)."""
    d = ImageDraw.Draw(im)
    for y in range(0, im.height, TILE):
        for x in range(0, im.width, TILE):
            if (x // TILE + y // TILE) % 2:
                d.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=FLOOR2)


# ------------------------------------------------------------------ run: 2 / 3 / 4 comparison
RUN_HOLDS = (2, 3, 4)
RUN_T = 96                                     # sim frames: 6 / 4 / 3 whole cycles, 256 px


def run_compare(view, k=3):
    fx, fy = B3.FWD_SCREEN[view]
    fr = B3.frames('run', view)
    W_, H_, CX, GY = PR.CANVAS['small']
    dist = B3.RUN_SPEED / 60 * RUN_T
    side = fx != 0
    pad = 6
    # one lane per hold: a row (side views) or a column (front / back)
    lw = (W_ + round(dist) + 2 * pad) if side else (W_ + 2 * pad)
    lh = (H_ + 2 * pad) if side else (H_ + round(dist) + 2 * pad)
    # where the foot anchor starts in a lane
    sx = pad + CX if fx >= 0 else lw - pad - (W_ - CX)
    sy = pad + GY if fy >= 0 else lh - pad - (H_ - GY)
    tag_h = 40
    notes = {2: '每張 2 模擬幀：一輪 0.27 秒，站地腳不滑', 3: '每張 3 模擬幀：一輪 0.40 秒，站地腳每張滑 2.7px',
             4: '每張 4 模擬幀（原定）：一輪 0.53 秒，站地腳每張滑 5.3px'}
    imgs = []
    for t in range(RUN_T):
        lanes = []
        for d in RUN_HOLDS:
            f = fr[(t // d) % B3.RUN_N]
            im = Image.new('RGBA', (lw, lh), FLOOR)
            floor(im)
            ax = round(sx + fx * B3.RUN_SPEED / 60 * t)
            ay = round(sy + fy * B3.RUN_SPEED / 60 * t)
            ImageDraw.Draw(im).ellipse((ax - 12, ay - 2, ax + 12, ay + 3), fill=SHADOW)
            im.alpha_composite(PR.image(f.px, 'small'), (ax - CX, ay - GY))
            lanes.append(up(im, k))
        if side:
            rows = [label(f'奔跑 {VIEW_ZH[view]}　160px/s　GIF 每格 20ms（實際速度的 0.83 倍；60fps 的版本見 HTML）',
                          lanes[0].width, 16, 30)]
            for d, ln in zip(RUN_HOLDS, lanes):
                rows.append(label(notes[d], ln.width, 16, 26))
                rows.append(ln)
            img = stack(rows, 4)
        else:
            cols = []
            for d, ln in zip(RUN_HOLDS, lanes):
                cols.append(stack([label(notes[d].replace('：', '\n'), ln.width, 14, tag_h), ln], 4))
            img = stack([label(f'奔跑 {VIEW_ZH[view]}　160px/s　GIF 每格 20ms（0.83 倍）', lw * k * 3, 16, 30), hrow(cols)], 4)
        imgs.append(img.convert('RGB'))
    path = os.path.join(OUT, f'batch3_run_compare_{view}.gif')
    save_gif(imgs, [20] * len(imgs), path)
    return path


HTML = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>奔跑播放速度比較</title>
<style>
:root { --bg:#1e1e22; --fg:#e8e6e1; --mute:#a9a59c; }
body { margin:0; padding:16px; background:var(--bg); color:var(--fg);
       font:14px/1.5 -apple-system, "PingFang TC", "Noto Sans TC", sans-serif; }
h1 { font-size:18px; margin:0 0 4px; } p { margin:0 0 12px; color:var(--mute); }
.bar { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
button { background:#34343a; color:var(--fg); border:1px solid #55555c; border-radius:6px; padding:6px 12px; font:inherit; cursor:pointer; }
button.on { background:#e8e6e1; color:#1e1e22; }
canvas { image-rendering:pixelated; display:block; max-width:100%; }
.lane { margin:0 0 10px; } .lane b { display:block; margin-bottom:4px; font-weight:600; }
.wrap { overflow-x:auto; }
</style></head><body>
<h1>奔跑：每張停 2／3／4 模擬幀</h1>
<p>同一組 8 張，角色照程式速度（160px/s）在地面格線上移動，60fps。站地腳相對地面格線的滑動就是差別。</p>
<div class="bar" id="views"></div>
<div class="bar"><button id="pause">暫停</button><button id="slow">慢放 ×0.25</button></div>
<div class="wrap" id="lanes"></div>
<script>
const SHEET = "data:image/png;base64,__SHEET__";
const VIEWS = ["south","east","north","west"], ZH = {south:"朝下",east:"朝右",north:"朝上",west:"朝左"};
const FWD = {east:[1,0],west:[-1,0],south:[0,1],north:[0,-1]};
const W = 56, H = 56, CX = 28, GY = 53, N = 8, SPEED = __SPEED__, T = __T__, K = 3, TILE = 16;
const HOLDS = [2,3,4], NOTE = {2:"每張 2 模擬幀：一輪 0.27 秒，站地腳不滑", 3:"每張 3 模擬幀：一輪 0.40 秒，站地腳每張滑 2.7px", 4:"每張 4 模擬幀（原定）：一輪 0.53 秒，站地腳每張滑 5.3px"};
let view = "east", paused = false, slow = false, t = 0, acc = 0, last = null;
const img = new Image(); img.src = SHEET;
const vb = document.getElementById("views");
VIEWS.forEach(v => { const b = document.createElement("button"); b.textContent = ZH[v]; b.onclick = () => { view = v; build(); }; b.dataset.v = v; vb.appendChild(b); });
document.getElementById("pause").onclick = e => { paused = !paused; e.target.textContent = paused ? "播放" : "暫停"; };
document.getElementById("slow").onclick = e => { slow = !slow; e.target.classList.toggle("on", slow); };
let lanes = [];
function build() {
  [...vb.children].forEach(b => b.classList.toggle("on", b.dataset.v === view));
  const box = document.getElementById("lanes"); box.innerHTML = ""; lanes = [];
  const [fx, fy] = FWD[view], dist = SPEED / 60 * T, side = fx !== 0, pad = 6;
  const lw = side ? W + Math.round(dist) + 2 * pad : W + 2 * pad, lh = side ? H + 2 * pad : H + Math.round(dist) + 2 * pad;
  const holder = document.createElement("div"); holder.style.display = side ? "block" : "flex"; holder.style.gap = "12px";
  HOLDS.forEach(d => {
    const div = document.createElement("div"); div.className = "lane";
    const b = document.createElement("b"); b.textContent = NOTE[d]; div.appendChild(b);
    const c = document.createElement("canvas"); c.width = lw * K; c.height = lh * K; div.appendChild(c);
    holder.appendChild(div);
    lanes.push({d, c, ctx: c.getContext("2d"), lw, lh, fx, fy,
      sx: fx >= 0 ? pad + CX : lw - pad - (W - CX), sy: fy >= 0 ? pad + GY : lh - pad - (H - GY)});
  });
  box.appendChild(holder); t = 0; draw();
}
function draw() {
  const row = VIEWS.indexOf(view);
  for (const L of lanes) {
    const g = L.ctx; g.imageSmoothingEnabled = false; g.setTransform(K,0,0,K,0,0);
    g.fillStyle = "#e2dbcc"; g.fillRect(0, 0, L.lw, L.lh); g.fillStyle = "#d6cebe";
    for (let y = 0; y < L.lh; y += TILE) for (let x = 0; x < L.lw; x += TILE) if (((x / TILE) + (y / TILE)) % 2) g.fillRect(x, y, TILE, TILE);
    const ax = Math.round(L.sx + L.fx * SPEED / 60 * t), ay = Math.round(L.sy + L.fy * SPEED / 60 * t);
    g.fillStyle = "#c4bcac"; g.beginPath(); g.ellipse(ax + 0.5, ay + 0.5, 12, 2.5, 0, 0, 7); g.fill();
    const f = Math.floor(t / L.d) % N;
    g.drawImage(img, f * W, row * H, W, H, ax - CX, ay - GY, W, H);
  }
}
function tick(now) {
  if (last === null) last = now;
  const dt = now - last; last = now;
  if (!paused) {
    acc += dt * (slow ? 0.25 : 1);
    while (acc >= 1000 / 60) { acc -= 1000 / 60; t = (t + 1) % T; }
    draw();
  }
  requestAnimationFrame(tick);
}
img.onload = () => { build(); requestAnimationFrame(tick); };
</script></body></html>
"""


def run_html(sheet):
    buf = io.BytesIO()
    sheet.save(buf, 'PNG')
    html = HTML.replace('__SHEET__', base64.b64encode(buf.getvalue()).decode()) \
               .replace('__SPEED__', repr(B3.RUN_SPEED)).replace('__T__', str(RUN_T))
    path = os.path.join(OUT, 'batch3_run_compare.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return path


SHEET_NAMES = {'run': 'run', 'charge': 'charge', 'charge_walk': 'charge_walk', 'thrust': 'thrust', 'execute': 'execute',
               'dash': 'dash', 'backstep': 'backstep', 'walk_locked': 'walk_locked'}


def export_run():
    path, sheet = write_sheet('run', 'run')
    print('sheet', path, sheet.size)
    for v in B3.VIEWS:
        print('wrote', run_compare(v))
    print('wrote', run_html(sheet))


# ------------------------------------------------------------------ scenes: one entry per sim frame
# (source, frame index, world x, world y): the camera follows the character, the floor scrolls
# under it, so a planted foot that slides shows against the grid. Sources: batch 3 actions, the
# batch 1 actions (idle, guard_walk, heal_walk) and the walk itself.
import batch1 as B1

LEFT_SCREEN = {'south': (1, 0), 'north': (-1, 0), 'east': (0, -1), 'west': (0, 1)}   # the character's left
LEFT_VIEW = {'south': 'east', 'north': 'west', 'east': 'north', 'west': 'south'}      # facing its left
RUN_PREVIEW_HOLD = 2        # decision 1: the user chose 2 from the 2 / 3 / 4 comparison (2026-09-28)


def src_frames(src, view):
    if src in B3.ACTIONS:
        return B3.frames(src, view)
    if src == 'walk':
        return _walk_frames(view)
    return B1.frames(src, view)


_WALK = {}


def _walk_frames(view):
    if view not in _WALK:
        r = B3.walk_rig(view)
        _WALK[view] = [type('F', (), {'px': r.frame(i).px, 'name': f'walk {i + 1}', 'dur': 2})() for i in range(8)]
    return _WALK[view]


def canvas_of(src):
    return B3.CANVAS.get(src, 'small')


class TL:
    def __init__(self, view):
        self.view, self.rows, self.x, self.y = view, [], 0.0, 0.0

    def hold(self, src, idx, n, move=(0.0, 0.0), speeds=None):
        """n sim frames of one frame; move = screen direction, speeds = px per sim frame."""
        for k in range(n):
            sp = speeds[k] if speeds else 0.0
            self.x += move[0] * sp
            self.y += move[1] * sp
            self.rows.append((src, idx, self.x, self.y))

    def play(self, src, names, move=(0.0, 0.0), speed=0.0, durs=None):
        fr = src_frames(src, self.view)
        by = {f.name: i for i, f in enumerate(fr)}
        for j, nm in enumerate(names):
            i = by[nm]
            d = durs[j] if durs else fr[i].dur
            self.hold(src, i, d, move, [speed] * d)


def cyc(prefix, n, times=1, start=0):
    return [f'{prefix} {(start + i) % n + 1}' for i in range(n * times)]


def scene_run(v):
    t = TL(v)
    fwd = B3.FWD_SCREEN[v]
    t.hold('idle', 0, 12)
    acc = [B3.RUN_SPEED * (k + 1) / 5 / 60 for k in range(5)]
    t.hold('run', 8, 2, fwd, acc[:2])
    t.hold('run', 9, 2, fwd, acc[2:4])
    k0 = B3.RUN_START[v][0]
    names = cyc('run', 8, 3, k0)
    fr = B3.frames('run', v)
    by = {f.name: i for i, f in enumerate(fr)}
    sp = [acc[4]] + [B3.RUN_SPEED / 60] * 200
    q = 0
    for nm in names:
        t.hold('run', by[nm], RUN_PREVIEW_HOLD, fwd, sp[q:q + RUN_PREVIEW_HOLD])
        q += RUN_PREVIEW_HOLD
    # let go: the program slows over 4 sim frames; the run goes on to a frame that can stop
    dec = [B3.RUN_SPEED / 60 * (1 - (k + 1) / 4) for k in range(4)] + [0.0] * 20
    q = 0
    table = B3.run_stop_from(v)
    j = (k0 + len(names)) % 8
    while table[j] is None:
        t.hold('run', by[f'run {j + 1}'], RUN_PREVIEW_HOLD, fwd, dec[q:q + RUN_PREVIEW_HOLD])
        q += RUN_PREVIEW_HOLD
        j = (j + 1) % 8
    for nm in (f'停步 1{table[j]}', '停步 2', '停步 3'):
        t.hold('run', by[nm], 2, fwd, dec[q:q + 2])
        q += 2
    t.hold('idle', 0, 18)
    return t


def scene_walk_locked(v):
    t = TL(v)
    fwd, left = B3.FWD_SCREEN[v], LEFT_SCREEN[v]
    sp = 85.0 / 60
    t.hold('idle', 0, 12)
    t.play('walk', cyc('walk', 8, 2), fwd, sp, durs=[2] * 16)
    t.play('walk_locked', cyc('back', 8, 2), (-fwd[0], -fwd[1]), sp)
    t.play('walk_locked', cyc('side', 4, 3), left, sp)
    t.play('walk_locked', cyc('rside', 4, 3), (-left[0], -left[1]), sp)
    t.hold('idle', 0, 12)
    return t


def scene_slow(action, base, speed):
    def build(v):
        t = TL(v)
        fwd, left = B3.FWD_SCREEN[v], LEFT_SCREEN[v]
        sp = speed / 60
        t.play(base[0], [base[1]], durs=[12])
        t.play(action, cyc('fwd', 8, 2), fwd, sp)
        t.play(action, cyc('back', 8, 2), (-fwd[0], -fwd[1]), sp)
        t.play(action, cyc('side', 4, 3), left, sp)
        t.play(action, cyc('rside', 4, 3), (-left[0], -left[1]), sp)
        t.play(base[0], [base[1]], durs=[12])
        return t
    return build


def scene_charge_thrust(v):
    t = TL(v)
    fwd = B3.FWD_SCREEN[v]
    t.hold('idle', 0, 12)
    t.play('charge', ['in 1', 'in 2'])
    n = 4
    while n < 60:
        for i in range(4):
            t.play('charge', [f'hold {i + 1}'])
            n += B3.CHARGE_HOLD
    # released full: the thrust, 6 px a sim frame through 0-11 (appendix A)
    fr = B3.frames('thrust', v)
    q = 0
    for i, f in enumerate(fr):
        sp = [6.0 if q + k < 12 else 0.0 for k in range(f.dur)]
        t.hold('thrust', i, f.dur, fwd, sp)
        q += f.dur
    t.hold('idle', 0, 18)
    return t


def scene_charge_cancel(v):
    t = TL(v)
    t.hold('idle', 0, 12)
    t.play('charge', ['in 1', 'in 2'] + [f'hold {i + 1}' for i in range(4)] * 2 + ['out 1', 'out 2'])
    t.hold('idle', 0, 18)
    return t


def scene_execute(v, approach=30.0):
    t = TL(v)
    fwd = B3.FWD_SCREEN[v]
    t.hold('idle', 0, 12)
    fr = B3.frames('execute', v)
    q = 0
    for i, f in enumerate(fr):
        sp = [approach / 12 if q + k < 12 else 0.0 for k in range(f.dur)]
        if q == 12:
            t.hold('execute', i, 15)          # the hit: 15 frames of hitstop (appendix A)
        t.hold('execute', i, f.dur, fwd, sp)
        q += f.dur
    t.hold('idle', 0, 18)
    return t


def scene_dodge(action, back=False, locked_side=False):
    def build(v):
        t = TL(v)
        t.hold('idle', 0, 12)
        if locked_side:
            dv = LEFT_VIEW[v]
            mv = LEFT_SCREEN[v]
        else:
            dv = v
            mv = B3.FWD_SCREEN[v] if not back else (-B3.FWD_SCREEN[v][0], -B3.FWD_SCREEN[v][1])
        fr = B3.frames(action, dv)
        sp = 56.0 / 11
        q = 0
        for i, f in enumerate(fr[:2]):
            t.rows += []
            for k in range(f.dur):
                t.x += mv[0] * sp
                t.y += mv[1] * sp
                t.rows.append((('view', dv, action), i, t.x, t.y))
            q += f.dur
        rec = 'backstep' if (back or locked_side) else action
        fr2 = B3.frames(rec, v)
        for i, f in list(enumerate(fr2))[2:]:
            t.hold(rec, i, f.dur)
        t.hold('idle', 0, 18)
        return t
    return build


SCENES = [
    ('run', '奔跑：起跑 → 循環 → 放開搖桿（繼續播到能停的那張）→ 停步 1–3 → 待機（160px/s，每張 2 模擬幀）', scene_run),
    ('walk_locked', '鎖定走路 85px/s：前進（走路）、後退、往左、往右側移，每張 2 模擬幀', scene_walk_locked),
    ('guard_walk', '格擋移動 50px/s：前進、後退、往左、往右（每張 2 模擬幀）', scene_slow('guard_walk', ('guard', 'hold 1'), 50.0)),
    ('charge_walk', '蓄力移動 40px/s：前進、後退、往左、往右（每張 2／2／2／3 模擬幀）', scene_slow('charge_walk', ('charge', 'hold 1'), 40.0)),
    ('heal_walk', '治療移動 30px/s：前進、後退、往左、往右（每張 3 模擬幀）', scene_slow('heal_walk', ('heal', 'hold 1'), 30.0)),
    ('charge_thrust', '蓄力 → 蓄滿放開 → 突刺（0–11 每幀 6px）→ 收招 → 待機', scene_charge_thrust),
    ('charge_cancel', '蓄力沒蓄滿就放開 → 收勢 → 待機', scene_charge_cancel),
    ('execute', '處決：貼近 30px → 第 12 幀命中、頓幀 15 → 收招 → 待機', scene_execute),
    ('dash', '閃身：衝刺 56px → 煞停 → 待機', scene_dodge('dash')),
    ('backstep', '閃身：後跳 56px → 落地 → 待機', scene_dodge('backstep', back=True)),
    ('dodge_side', '鎖定時往角色左邊閃：衝刺畫閃身方向，收招轉回面向、用落地', scene_dodge('dash', locked_side=True)),
]


def frame_px(v, src, idx):
    if isinstance(src, tuple):
        _, dv, act = src
        return B3.frames(act, dv)[idx].px, canvas_of(act)
    return src_frames(src, v)[idx].px, canvas_of(src)


CELL = (104, 88, 52, 70)        # scene cell: w, h, where the foot anchor sits


def scene_gif(name, title, build, k=3):
    tls = {v: build(v) for v in B3.VIEWS}
    n = max(len(t.rows) for t in tls.values())
    cw, ch, ax, ay = CELL
    imgs = []
    for i in range(n):
        cells = []
        for v in B3.VIEWS:
            rows = tls[v].rows
            src, idx, x, y = rows[min(i, len(rows) - 1)]
            im = Image.new('RGBA', (cw, ch), FLOOR)
            d = ImageDraw.Draw(im)
            ox, oy = ax - round(x), ay - round(y)          # the world's origin on this cell
            for gy in range(-TILE * 2, ch + TILE * 2, TILE):
                for gx in range(-TILE * 2, cw + TILE * 2, TILE):
                    wx, wy = gx + (ox % TILE) - TILE, gy + (oy % TILE) - TILE
                    if ((wx - ox) // TILE + (wy - oy) // TILE) % 2:
                        d.rectangle((wx, wy, wx + TILE - 1, wy + TILE - 1), fill=FLOOR2)
            d.ellipse((ax - 12, ay - 2, ax + 12, ay + 3), fill=SHADOW)
            px, canvas = frame_px(v, src, idx)
            W_, H_, CX, GY = PR.CANVAS[canvas]
            im.alpha_composite(PR.image(px, canvas), (ax - CX, ay - GY))
            cells.append(up(im, k))
        img = stack([label(f'{title}　GIF 每格 20ms（0.83 倍速；60fps 見 batch3_player.html）', cw * k * 4 + 18, 16, 30),
                     hrow([stack([label(VIEW_ZH[v], cw * k, 16, 24), c], 2) for v, c in zip(B3.VIEWS, cells)])], 4)
        imgs.append(img.convert('RGB'))
    path = os.path.join(OUT, f'batch3_{name}.gif')
    save_gif(imgs, [20] * len(imgs), path)
    return path, tls


PLAYER = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>第 3 批動畫預覽</title>
<style>
:root { --bg:#1e1e22; --fg:#e8e6e1; --mute:#a9a59c; }
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:14px/1.5 -apple-system, "PingFang TC", "Noto Sans TC", sans-serif; }
h1 { font-size:18px; margin:0 0 4px; } p { margin:0 0 12px; color:var(--mute); }
.bar { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px; }
button { background:#34343a; color:var(--fg); border:1px solid #55555c; border-radius:6px; padding:5px 10px; font:inherit; cursor:pointer; }
button.on { background:#e8e6e1; color:#1e1e22; }
.row { display:flex; gap:10px; flex-wrap:wrap; } .cell b { display:block; font-weight:600; margin-bottom:2px; }
canvas { image-rendering:pixelated; display:block; }
#title { margin:6px 0 10px; }
</style></head><body>
<h1>第 3 批動畫預覽（60fps，照模擬幀時間）</h1>
<p>鏡頭跟著角色，地面格線照程式的速度捲動：站地腳相對格線有沒有滑一看就知道。「慢放」是 0.25 倍。</p>
<div class="bar" id="scenes"></div>
<div class="bar"><button id="pause">暫停</button><button id="slow">慢放 ×0.25</button><button id="step">下一幀</button><span id="clock" style="align-self:center;color:var(--mute)"></span></div>
<div id="title"></div>
<div class="row" id="cells"></div>
<script>
const DATA = __DATA__;
const VIEWS = ["south","east","north","west"], ZH = {south:"朝下",east:"朝右",north:"朝上",west:"朝左"};
const K = 3, TILE = 16, CW = __CW__, CH = __CH__, AX = __AX__, AY = __AY__;
const imgs = {}; let loaded = 0;
for (const [k, uri] of Object.entries(DATA.sheets)) { const im = new Image(); im.onload = () => { if (++loaded === Object.keys(DATA.sheets).length) start(); }; im.src = uri; imgs[k] = im; }
let scene = 0, t = 0, acc = 0, last = null, paused = false, slow = false;
const cells = {};
function build() {
  const bar = document.getElementById("scenes"); bar.innerHTML = "";
  DATA.scenes.forEach((s, i) => { const b = document.createElement("button"); b.textContent = s.name; b.classList.toggle("on", i === scene); b.onclick = () => { scene = i; t = 0; build(); }; bar.appendChild(b); });
  document.getElementById("title").textContent = DATA.scenes[scene].title;
  const row = document.getElementById("cells"); row.innerHTML = "";
  VIEWS.forEach(v => { const d = document.createElement("div"); d.className = "cell"; const b = document.createElement("b"); b.textContent = ZH[v]; d.appendChild(b);
    const c = document.createElement("canvas"); c.width = CW * K; c.height = CH * K; d.appendChild(c); row.appendChild(d); cells[v] = c.getContext("2d"); });
  draw();
}
function draw() {
  const s = DATA.scenes[scene];
  const n = Math.max(...VIEWS.map(v => s.tl[v].length));
  document.getElementById("clock").textContent = `模擬幀 ${t} / ${n}`;
  for (const v of VIEWS) {
    const g = cells[v], rows = s.tl[v], r = rows[Math.min(t, rows.length - 1)];
    const [sheet, col, row, x, y] = r, meta = DATA.meta[sheet];
    g.setTransform(K, 0, 0, K, 0, 0); g.imageSmoothingEnabled = false;
    g.fillStyle = "#e2dbcc"; g.fillRect(0, 0, CW, CH); g.fillStyle = "#d6cebe";
    const ox = AX - Math.round(x), oy = AY - Math.round(y);
    for (let gy = -2 * TILE; gy < CH + 2 * TILE; gy += TILE) for (let gx = -2 * TILE; gx < CW + 2 * TILE; gx += TILE) {
      const wx = gx + ((ox % TILE) + TILE) % TILE - TILE, wy = gy + ((oy % TILE) + TILE) % TILE - TILE;
      if ((((Math.floor((wx - ox) / TILE) + Math.floor((wy - oy) / TILE)) % 2) + 2) % 2) g.fillRect(wx, wy, TILE, TILE);
    }
    g.fillStyle = "#c4bcac"; g.beginPath(); g.ellipse(AX + 0.5, AY + 0.5, 12, 2.5, 0, 0, 7); g.fill();
    g.drawImage(imgs[sheet], col * meta.w, row * meta.h, meta.w, meta.h, AX - meta.cx, AY - meta.gy, meta.w, meta.h);
  }
}
function start() {
  build();
  document.getElementById("pause").onclick = e => { paused = !paused; e.target.textContent = paused ? "播放" : "暫停"; };
  document.getElementById("slow").onclick = e => { slow = !slow; e.target.classList.toggle("on", slow); };
  document.getElementById("step").onclick = () => { paused = true; document.getElementById("pause").textContent = "播放"; t = (t + 1) % Math.max(...VIEWS.map(v => DATA.scenes[scene].tl[v].length)); draw(); };
  requestAnimationFrame(tick);
}
function tick(now) {
  if (last === null) last = now; const dt = now - last; last = now;
  if (!paused) { acc += dt * (slow ? 0.25 : 1); const n = Math.max(...VIEWS.map(v => DATA.scenes[scene].tl[v].length));
    while (acc >= 1000 / 60) { acc -= 1000 / 60; t = (t + 1) % n; } draw(); }
  requestAnimationFrame(tick);
}
</script></body></html>
"""


def sheet_image(src):
    """The sheet a scene's frames come from (the files written to assets/, or built here)."""
    canvas = canvas_of(src)
    W_, H_, _, _ = PR.CANVAS[canvas]
    fr = {v: src_frames(src, v) for v in B3.VIEWS}
    cols = len(fr['south'])
    sheet = Image.new('RGBA', (W_ * cols, H_ * 4), (0, 0, 0, 0))
    for r, v in enumerate(B3.VIEWS):
        for c, f in enumerate(fr[v]):
            sheet.alpha_composite(PR.image(f.px, canvas), (c * W_, r * H_))
    return sheet


def player(scene_tls):
    import json
    srcs = set()
    for _, _, tls in scene_tls:
        for v, t in tls.items():
            for src, _, _, _ in t.rows:
                srcs.add(src[2] if isinstance(src, tuple) else src)
    sheets, meta = {}, {}
    for src in sorted(srcs):
        buf = io.BytesIO()
        sheet_image(src).save(buf, 'PNG')
        sheets[src] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        W_, H_, CX, GY = PR.CANVAS[canvas_of(src)]
        meta[src] = dict(w=W_, h=H_, cx=CX, gy=GY)
    scenes = []
    for name, title, tls in scene_tls:
        tl = {}
        for v, t in tls.items():
            rows = []
            for src, idx, x, y in t.rows:
                if isinstance(src, tuple):
                    rows.append([src[2], idx, B3.VIEWS.index(src[1]), round(x, 2), round(y, 2)])
                else:
                    rows.append([src, idx, B3.VIEWS.index(v), round(x, 2), round(y, 2)])
            tl[v] = rows
        scenes.append(dict(name=name, title=title, tl=tl))
    cw, ch, ax, ay = CELL
    html = PLAYER.replace('__DATA__', json.dumps(dict(sheets=sheets, meta=meta, scenes=scenes), ensure_ascii=False)) \
                 .replace('__CW__', str(cw)).replace('__CH__', str(ch)).replace('__AX__', str(ax)).replace('__AY__', str(ay))
    path = os.path.join(OUT, 'batch3_player.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    return path


# ------------------------------------------------------------------ review sheets
def head_check(k=6):
    from export_poses import enclosed_mask
    rows = [label('頸部以上：第 3 批每一幀（黃色＝羽飾碰到頭盔圍出的背景，自動檢查不看這一區）', 2000, 22, 34)]
    for action in B3.ACTIONS:
        canvas = B3.CANVAS[action]
        W_, H_, _, _ = PR.CANVAS[canvas]
        for v in B3.VIEWS:
            cells = [label(f'{action}\n{VIEW_ZH[v]}', 120, 14, 60)]
            for f in B3.frames(action, v):
                helm = [q for q, n in f.trace.items() if n == 'helmet'] or \
                       [q for q in f.px if q[1] < min(y for _, y in f.px) + 18]
                cut = max(y for _, y in helm) + 2
                x0 = max(0, min(x for x, _ in helm) - 12)
                x1 = min(W_, max(x for x, _ in helm) + 14)
                y0 = max(0, min(y for (x, y) in f.px if x0 <= x < x1) - 1)
                tile = Image.new('RGBA', (W_, H_), (96, 112, 96, 255))
                tile.alpha_composite(PR.image(f.px, canvas))
                for (x, y) in enclosed_mask(f.px, W_, H_):
                    if y < cut:
                        tile.putpixel((x, y), (255, 230, 0, 255))
                cells.append(up(tile.crop((x0, y0, x1, cut)), k))
            rows.append(hrow(cells))
    return stack(rows, 4)


def onion(pxs, canvas, k=6):
    W_, H_, _, _ = PR.CANVAS[canvas]
    im = Image.new('RGBA', (W_, H_), (240, 236, 228, 255))
    for px, tint in zip(pxs[:2], [(60, 120, 255), (230, 60, 60)]):
        lay = Image.new('RGBA', (W_, H_), (0, 0, 0, 0))
        for (x, y) in px:
            if 0 <= x < W_ and 0 <= y < H_:
                lay.putpixel((x, y), tint + (110,))
        im.alpha_composite(lay)
    return up(im, k)


def to_canvas(px, src_canvas, dst_canvas):
    if src_canvas == dst_canvas:
        return px
    o = (16, 8) if src_canvas == 'small' else (-16, -8)
    return {(x + o[0], y + o[1]): c for (x, y), c in px.items()}


ONION = [(('charge', 'hold 1'), ('thrust', 'f1 蹬地')), (('thrust', 'f1 蹬地'), ('thrust', 'f2 前撲')),
         (('thrust', 'f3 保持 2'), ('thrust', 'f4 收劍 1')), (('thrust', 'f5 回站姿 2'), ('idle', 'idle 1')),
         (('idle', 'idle 1'), ('execute', '起步 1')), (('execute', '起步 1'), ('execute', '起步 2')),
         (('dash', '衝刺 2'), ('dash', '煞停 1')), (('dash', '煞停 1'), ('dash', '煞停 2')),
         (('backstep', '後跳 2'), ('backstep', '落地 1')), (('run', 'run 2'), ('run', '停步 1A')),
         (('run', '停步 1A'), ('run', '停步 2')), (('charge', 'hold 1'), ('charge', 'out 1'))]


def onion_sheet(k=5):
    rows = [label('洋蔥皮：藍＝前一張、紅＝後一張（88×72 畫格，5 倍）', 2000, 22, 34)]
    head = [label('', 70, 14, 50)] + [label(f'{a[1]}\n→ {b[1]}', 88 * k, 16, 50) for a, b in ONION]
    rows.append(hrow(head))
    for v in B3.VIEWS:
        cells = [label(VIEW_ZH[v], 70, 16, 72 * k)]
        for a, b in ONION:
            fa = next(f for f in src_frames(a[0], v) if f.name == a[1])
            fb = next(f for f in src_frames(b[0], v) if f.name == b[1])
            cells.append(onion([to_canvas(fa.px, canvas_of(a[0]), 'large'), to_canvas(fb.px, canvas_of(b[0]), 'large')], 'large', k))
        rows.append(hrow(cells))
    return stack(rows, 4)


def outline_sheet(k=5):
    import checks as C
    rows = [label('格擋（藍）、蓄力（橘）、治療（綠）的輪廓，白＝重疊（不含披風、羽飾、圍巾）；決定 2：兩兩差 ≥ 12%', 2000, 22, 34)]
    pairs = [(('guard', 'hold 1'), ('charge', 'hold 1')), (('charge', 'hold 1'), ('heal', 'hold 1')),
             (('guard_walk', 'fwd 3'), ('charge_walk', 'fwd 3')), (('charge_walk', 'side 2'), ('heal_walk', 'side 2')),
             (('charge_walk', 'back 5'), ('heal_walk', 'back 5'))]
    col = {'guard': (70, 150, 255, 255), 'guard_walk': (70, 150, 255, 255), 'charge': (255, 140, 40, 255),
           'charge_walk': (255, 140, 40, 255), 'heal': (90, 200, 90, 255), 'heal_walk': (90, 200, 90, 255)}
    for a, b in pairs:
        cells = [label(f'{a[0]} {a[1]}\n對 {b[0]} {b[1]}', 190, 14, 72 * k)]
        for v in B3.VIEWS:
            fa = next(f for f in src_frames(a[0], v) if f.name == a[1])
            fb = next(f for f in src_frames(b[0], v) if f.name == b[1])
            sa = {q for q in to_canvas(fa.px, canvas_of(a[0]), 'large') if True}
            sil = lambda f, src: set(to_canvas({q: 1 for q in f.px if f.trace.get(q, '') not in B1.CLOTH}, canvas_of(src), 'large'))
            s1, s2 = sil(fa, a[0]), sil(fb, b[0])
            share = C.outline_shift_share(s1, s2)
            im = Image.new('RGBA', (88, 72), (40, 40, 44, 255))
            for q in s1 | s2:
                if 0 <= q[0] < 88 and 0 <= q[1] < 72:
                    im.putpixel(q, (235, 235, 235, 255) if (q in s1 and q in s2) else (col[a[0]] if q in s1 else col[b[0]]))
            big = up(im, k)
            ImageDraw.Draw(big).text((6, 4), f'{VIEW_ZH[v]} {round(100 * share)} %', fill=(255, 255, 0, 255), font=E.font(22))
            cells.append(big)
        rows.append(hrow(cells))
    return stack(rows, 4)


def concept_sheet(k=6):
    """East views against the concept's thumbnails, same height, the thumbnail's outline laid
    over (animation-review §4.6): D1 (thrust f2, execution shared), B1 (dash f2), B (run contact)."""
    items = [('thrust', 'f2 前撲', 'D1'), ('dash', '衝刺 2', 'B1'), ('run', 'run 1', 'B')]
    rows = [label('設計圖對照（朝右，同高，洋紅＝設計圖小圖的輪廓，標重疊率）', 1600, 22, 34)]
    cells = []
    for act, nm, ref in items:
        f = next(x for x in B3.frames(act, 'east') if x.name == nm)
        canvas = B3.CANVAS[act]
        ov, match = E.overlay_cell(nm, f.pose, canvas, ref, k)
        th = E.thumb(ref, k, nm, f.pose, canvas)
        cells.append(stack([label(f'{B3.TITLES[act].split("（")[0]} {nm}／{ref}　重疊 {round(100 * match)} %', 88 * k * 2, 18, 30),
                            hrow([th, ov])], 2))
    rows.append(hrow(cells))
    return stack(rows, 4)


def motion_table():
    import export_batch1 as X1
    lines = ['# 第 3 批逐部件動作表', '',
             '由 `tools/sprite_rig/export_batch3.py` 產生（animation-review §5）。座標是各自畫格的像素（56×56 或 88×72），y 往下為正。',
             '「骨盆 y」「頭盔頂 y」對照頭晚一拍；布料末端是離頭盔中心最遠的那一點。後退的走路是走路骨架畫的，沒有部件表，只列頭與髖的高度。', '']
    for action in B3.ACTIONS:
        for v in B3.VIEWS:
            fr = B3.frames(action, v)
            lines += [f'## {B3.TITLES[action]}・{VIEW_ZH[v]}', '',
                      '| 幀 | 模擬幀 | 前傾° | 骨盆 y | 頭盔頂 y | 右拳 | 左拳 | 劍尖 | 兩腳中心 x | 羽飾末端 | 披風末端 |',
                      '|---|---|---|---|---|---|---|---|---|---|---|']
            t = 0
            for f in fr:
                if f.pose is None:
                    lines.append(f'| {f.name} | {t}–{t + f.dur - 1} | – | {f.debug["hip_y"]:.1f} | 頭 {f.debug["head_y"]:.1f} | | | | | | |')
                    t += f.dur
                    continue
                m = X1.metrics(f)
                lean = f.pose.get('lean', 0)
                pel = f'{m["pelvis"][1]:.1f}' if m['pelvis'] else '–'
                feet = ' / '.join(f'{kk} {x:.1f}' for kk, x in sorted(m['feet'].items())) or '（離地）'
                lines.append(f'| {f.name} | {t}–{t + f.dur - 1} | {lean:.0f} | {pel} | {X1.fmt(m["helmet_top"])} | '
                             f'{X1.fmt(m["fist_R"])} | {X1.fmt(m["fist_L"])} | {X1.fmt(m["tip"])} | {feet} | '
                             f'{X1.fmt(m["plume_tip"])} | {X1.fmt(m["cape_tip"])} |')
                t += f.dur
            lines.append('')
    return '\n'.join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1:] or ['all']
    if 'run' in what:
        export_run()
        return
    for action, name in SHEET_NAMES.items():
        path, sheet = write_sheet(action, name)
        print('sheet', os.path.relpath(path, ROOT), sheet.size)
    print('wrote', run_html(Image.open(os.path.join(SHEETS, 'knight_run.png'))))
    for action in B3.ACTIONS:
        for k in (3, 6):
            p = os.path.join(OUT, f'batch3_{action}_{k}x.png')
            sequence(action, k).save(p)
    print('wrote sequences')
    if 'sheets' in what:
        head_check().save(os.path.join(OUT, 'batch3_head_check.png'))
        onion_sheet().save(os.path.join(OUT, 'batch3_onion.png'))
        outline_sheet().save(os.path.join(OUT, 'batch3_outlines.png'))
        concept_sheet().save(os.path.join(OUT, 'batch3_concept.png'))
        with open(os.path.join(OUT, 'batch3_motion.md'), 'w', encoding='utf-8') as fh:
            fh.write(motion_table())
        print('wrote review sheets and the motion table')
        return
    scene_tls = []
    for name, title, build in SCENES:
        path, tls = scene_gif(name, title, build)
        scene_tls.append((name, title, tls))
        print('wrote', os.path.relpath(path, ROOT))
    print('wrote', os.path.relpath(player(scene_tls), ROOT))
    head_check().save(os.path.join(OUT, 'batch3_head_check.png'))
    onion_sheet().save(os.path.join(OUT, 'batch3_onion.png'))
    outline_sheet().save(os.path.join(OUT, 'batch3_outlines.png'))
    concept_sheet().save(os.path.join(OUT, 'batch3_concept.png'))
    with open(os.path.join(OUT, 'batch3_motion.md'), 'w', encoding='utf-8') as fh:
        fh.write(motion_table())
    print('wrote review sheets and the motion table')


if __name__ == '__main__':
    main()
