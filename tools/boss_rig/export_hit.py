"""Boss hit reactions and the kneel (受擊、跪地): sprite sheets and previews.

    python3 tools/boss_rig/export_hit.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game). Rows: down, right, up, left
(the walk-entry sheets: 16 rows, four directions for each of the loop's poses 0, 5, 10, 15).
Cells are 256x224 with the foot anchor at (128, 208), or the attack container 384x336 with it at
(192, 272) where the sword swings out or the cape lies on the ground towards the camera
(SHEETS below says which). Timing: combat frames per pose, anim_kneel's clips (README table).
Previews -> docs/art-preview/boss/hit_kneel/ (index.html).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from PIL import Image, ImageDraw
import boss as B
import rig
import gait
import limb
import anim_walk as AW
import anim_kneel as K
import preview
import export_anim as EA

SHEETS = EA.SHEETS
OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'hit_kneel')
NAMES = EA.NAMES
KIND_SHEET = EA.SHEET_OF
KIND_NAMES = EA.KIND_NAMES
BOX = (-40, -40, 296, 236)          # preview window (small-frame coordinates; the big container reaches further)
MARGIN = 2


def clips():
    """[(sheet name, [Timed clips that go in it, in row order])]."""
    out = [('boss_stagger', [K.stagger()]), ('boss_bounce', [K.bounce()]),
           ('boss_kneel_down', [K.kneel_down()]), ('boss_kneel_breathe', [K.breathe()]),
           ('boss_executed', [K.executed()]), ('boss_rise', [K.rise()]), ('boss_death', [K.death()]),
           ('boss_transition', [K.transition()]), ('boss_transition_kneel', [K.transition(True)])]
    for kind in AW.KINDS:
        name = KIND_SHEET[kind]
        out.append((name + '_stagger', [K.stagger(kind, e) for e in K.STOP_FROM]))
        out.append((name + '_kneel', [K.walk_kneel(kind, e) for e in K.STOP_FROM]))
        out.append((name + '_cstart', [K.carry_start(kind)]))
    return out


_frames = {}


def frames(clip):
    """{direction: [frames]} of a clip (cached by name)."""
    if clip.name not in _frames:
        _frames[clip.name] = {d: K.render(d, clip) for d in rig.DIRS}
    return _frames[clip.name]


def fits_small(all_frames):
    for f in all_frames:
        for (x, y) in f:
            if not (MARGIN <= x < rig.FW - MARGIN and MARGIN <= y < rig.FH - MARGIN):
                return False
    return True


def write_sheet(path, groups):
    """groups: [{direction: [frames]}] -> one sheet; rows: each group's four directions. Returns
    the cell size used."""
    every = [f for g in groups for d in rig.DIRS for f in g[d]]
    big = not fits_small(every)
    cw, ch = AW.BIG if big else (rig.FW, rig.FH)
    off = AW.EXT if big else 0
    n = len(groups[0]['down'])
    im = Image.new('RGBA', (cw * n, ch * 4 * len(groups)), (0, 0, 0, 0))
    r = 0
    for g in groups:
        for d in rig.DIRS:
            for c, f in enumerate(g[d]):
                im.alpha_composite(rig.image({(x + off, y + off): v for (x, y), v in f.items()}, (cw, ch)), (c * cw, r * ch))
            r += 1
    im.save(path)
    return (cw, ch), big


# ------------------------------------------------------------------ previews
def timeline(parts):
    """parts: [(frame, hold)] -> one frame per combat frame."""
    out = []
    for f, h in parts:
        out.extend([f] * h)
    return out


def held(clip, d):
    return list(zip(frames(clip)[d], clip.holds))


def stand_for(d, n):
    return [(rig.pixels(rig.standing()[d]), n)]


def loop_for(d, kind, start, n):
    fr = AW.frames(d, kind)
    return [(fr[(start + i) % gait.POSES], gait.HOLD) for i in range(n)]


def breathe_for(d, frames_left):
    c = K.breathe()
    fr = frames(c)[d]
    out, i = [], 0
    while frames_left > 0:
        h = min(c.holds[i % len(fr)], frames_left)
        out.append((fr[i % len(fr)], h))
        frames_left -= h
        i += 1
    return out


BREAK = 180          # BROKEN, VeltharisData.BREAK_TIME


def sequences():
    """What the game would show, per direction: [(title, caption, {direction: [(frame, hold)]})]."""
    kd, ex, ri = K.kneel_down(), K.executed(), K.rise()
    down_n = sum(kd.holds)
    seq = []
    seq.append(('break', '失衡（站著被削光韌性）：跪下、跪著喘氣到 3 秒、起身、站著',
                {d: stand_for(d, 30) + held(kd, d) + breathe_for(d, BREAK - down_n) + held(ri, d) + stand_for(d, 40)
                 for d in rig.DIRS}))
    seq.append(('execute', '失衡後在第 1.5 秒被處決：被處決 1 秒（0.2 秒時刺中）、起身',
                {d: stand_for(d, 30) + held(kd, d) + breathe_for(d, 90 - down_n) + held(ex, d) + held(ri, d)
                 + stand_for(d, 40) for d in rig.DIRS}))
    wk = K.walk_kneel('walk', 10)
    seq.append(('walk_break', '往前走時失衡（從循環第 10 張）：劍從肩上繞到身前插進地面、跪下、喘氣、起身',
                {d: loop_for(d, 'walk', 0, 10) + held(wk, d) + breathe_for(d, BREAK - sum(wk.holds)) + held(ri, d)
                 + stand_for(d, 40) for d in rig.DIRS}))
    st, ws = K.stagger(), K.stagger('walk', 10)
    seq.append(('stagger', '短僵直：站著被打中 → 站著；往前走時被打中（循環第 10 張）→ 接著走',
                {d: stand_for(d, 30) + held(st, d) + stand_for(d, 40) + loop_for(d, 'walk', 0, 10) + held(ws, d)
                 + loop_for(d, 'walk', 10, 20) for d in rig.DIRS}))
    bo, bs, cs = K.bounce(), K.bounce(False), K.carry_start('strafe_r')
    seq.append(('bounce', '被彈開：重擊（1.2 秒）→ 扛劍站著 → 喘息時的側移；輕擊（0.8 秒）同一組圖播快',
                {d: held(bo, d) + held(cs, d) + loop_for(d, 'strafe_r', AW.START_JOINS['strafe_r'], 10)
                 + held(bs, d) + held(cs, d) + loop_for(d, 'strafe_r', AW.START_JOINS['strafe_r'], 10) for d in rig.DIRS}))
    tr, tk = K.transition(), K.transition(True)
    seq.append(('transition', '階段轉場（1.5 秒）：站著 → 單膝跪地 → 披風翻飛 → 起身；處決後直接轉場（從跪姿開始）',
                {d: stand_for(d, 30) + held(tr, d) + stand_for(d, 40) + held(kd, d) + breathe_for(d, 40) + held(ex, d)
                 + held(tk, d) + stand_for(d, 40) for d in rig.DIRS}))
    de = K.death()
    seq.append(('death', '死亡：跪下、往前垂、停住（灰燼消散由程式畫）',
                {d: stand_for(d, 30) + held(de, d)[:-1] + [(frames(de)[d][-1], 90)] for d in rig.DIRS}))
    return seq


def video(path, tl, k=3, box=BOX):
    tmp = tempfile.mkdtemp()
    for n, f in enumerate(tl):
        preview.render(f, box, k).save(os.path.join(tmp, f'{n:04d}.png'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '60', '-i', os.path.join(tmp, '%04d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '10', '-movflags', '+faststart', path], check=True)
    shutil.rmtree(tmp)


def gif4(path, parts, k=2, box=BOX):
    """The four directions side by side, one GIF frame per pose (its hold as the delay)."""
    w, h = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    n = len(parts['down'])
    ims, holds = [], []
    for i in range(n):
        im = Image.new('RGB', (w * 4, h), preview.BG)
        for j, d in enumerate(rig.DIRS):
            im.paste(preview.render(parts[d][i][0], box, k), (j * w, 0))
        ims.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
        holds.append(parts['down'][i][1])
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=EA.gif_durations(holds), loop=0)


def legs_sheet(path, k=5):
    """The side view's legs alone with hip, knee, ankle: the way down from standing and from the
    walk (loop pose 10), the kneel."""
    lay = rig.Layout('right')
    box = (70, 118, 190, 214)
    rows = []
    for c in (K.kneel_down(), K.walk_kneel('walk', 10)):
        tiles = []
        for st in c.states:
            near, far = st['legR'], st['legL']
            f = {(x, y - AW.FAR_UP): v for (x, y), v in limb.darken(limb.leg_pixels(far)).items()}
            f.update(limb.leg_pixels(near))
            t = preview.render(f, box, k)
            d = ImageDraw.Draw(t)
            for L, up, col in ((far, AW.FAR_UP, (90, 150, 255)), (near, 0, (120, 255, 120))):
                J = limb.joints_work(L, lay)
                pts = [((J[n][0] / B.WORK - box[0]) * k, (J[n][1] / B.WORK - up - box[1]) * k) for n in ('hip', 'knee', 'ankle')]
                d.line(pts, fill=col, width=2)
            tiles.append(t)
        rows.append(tiles)
    tw, th = rows[0][0].size
    cols = max(len(r) for r in rows)
    out = Image.new('RGB', (cols * (tw + 4), len(rows) * (th + 4)), preview.BG)
    for r, tiles in enumerate(rows):
        for c, t in enumerate(tiles):
            out.paste(t, (c * (tw + 4), r * (th + 4)))
    out.save(path)


def hands_sheet(path, k=4):
    """The sword hand, the hilt and the shoulder (animation-review §5) in the four directions,
    cropped around the grip: standing, the kneel, the execution's jolt, the sword going into
    the ground from the shoulder, the bounce's contact and the knock, the stagger."""
    stages = [('站姿', None, 0),
              ('跪姿', K.kneel_down(), -1),
              ('被處決（往後仰）', K.executed(), 3),
              ('走路中失衡：劍插地前', K.walk_kneel('walk', 10), 6),
              ('走路中失衡：劍插進地面', K.walk_kneel('walk', 10), 8),
              ('被彈開：劍揮出去的那一刻', K.bounce(), 0),
              ('被彈開：劍被彈上去', K.bounce(), 2),
              ('短僵直（站著）', K.stagger(), 1)]
    rows = []
    for label, clip, i in stages:
        tiles = []
        for d in rig.DIRS:
            if clip is None:
                f = rig.pixels(rig.standing()[d])
                g = K.swd.standing(rig.VIEW_OF.get(d, 'right'))['grip']
                if d == 'left':
                    g = (2 * rig.AX - g[0], g[1])
            else:
                f = frames(clip)[d][i]
                j = i % len(clip)
                g = AW.SWORD_DRAWN[(d, clip.name, j)][1]['grip']
                if d == 'left':
                    g = (2 * rig.AX - g[0], g[1])
            box = (round(g[0]) - 42, round(g[1]) - 44, round(g[0]) + 42, round(g[1]) + 40)
            tiles.append(preview.render(f, box, k, ground=False))
        rows.append((label, tiles))
    EA._labelled(rows, path, rows[0][1][0].size, left=220)


def four_sheet(path, k=3):
    """The kneel next to the standing pose, four directions."""
    box = (40, 30, 216, 232)
    rows = [('站姿', [preview.render(rig.pixels(rig.standing()[d]), box, k) for d in rig.DIRS]),
            ('跪姿', [preview.render(frames(K.kneel_down())[d][-1], box, k) for d in rig.DIRS])]
    EA._labelled(rows, path, rows[0][1][0].size, left=70)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 受擊與跪地</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）受擊與跪地</h1>
<p>還沒接進遊戲。四個方向：朝下、朝右、朝上、朝左（朝左不是朝右的鏡像：劍在右手，朝左時在遠側）。跪姿照使用者的指定：<b>右膝跪地（左腳在前、左膝立起）、劍插在地上、右手握著、頭向下看</b>。劍上的火焰、失衡時火焰暗下、處決的刀光、死亡的灰燼都由程式畫，這裡沒有。</p>
<h2>跪姿：四個方向</h2>
<figure><img src="kneel_four.png"><figcaption>上排站姿、下排跪姿（3 倍）</figcaption></figure>
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
<figure><img src="hands_kneel.png"><figcaption>由上到下：站姿、跪姿、被處決往後仰、走路中失衡（劍插地前、插進地面）、被彈開（揮出去、被彈上去）、短僵直</figcaption></figure>
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝另一條）</h2>
<figure><img src="kneel_legs.png"><figcaption>上排：站著跪下；下排：往前走時跪下</figcaption></figure>
<h2>逐張</h2>
%(sheets)s
'''


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    os.makedirs(SHEETS, exist_ok=True)
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    report = []
    sheets_html = ''
    for name, group in clips():
        groups = [frames(c) for c in group]
        cell, big = write_sheet(os.path.join(SHEETS, name + '.png'), groups)
        report.append((name, [c.name for c in group], cell, [c.holds for c in group]))
        for d in rig.DIRS:
            fr = [f for g in groups for f in g[d]]
            labels = [f'{c.name.split("_")[-1] if len(group) > 1 else ""}:{i}' for c in group for i in range(len(c))]
            cols = len(group[0])
            preview.contact(fr, k=2 if len(fr) <= 20 else 1, cols=cols, box=BOX, labels=labels).save(
                os.path.join(OUT, f'{name}_{d}.png'))
            sheets_html += f'<figure><img src="{name}_{d}.png"><figcaption>{name} {NAMES[d]}</figcaption></figure>'
        print(name, cell, [len(c) for c in group])
    seq_html = ''
    for title, cap, parts in sequences():
        gif4(os.path.join(OUT, f'{title}_all.gif'), parts)
        seq_html += f'<h3>{cap}</h3><figure><img src="{title}_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>'
        if video_ok:
            for d in rig.DIRS:
                video(os.path.join(OUT, f'{title}_{d}.mp4'), timeline(parts[d]))
            seq_html += ''.join(f'<figure><video src="{title}_{d}.mp4" autoplay loop muted playsinline controls></video>'
                                f'<figcaption>{NAMES[d]}（60fps，3 倍）</figcaption></figure>' for d in rig.DIRS)
    four_sheet(os.path.join(OUT, 'kneel_four.png'))
    hands_sheet(os.path.join(OUT, 'hands_kneel.png'))
    legs_sheet(os.path.join(OUT, 'kneel_legs.png'))
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html})
    for name, cl, cell, holds in report:
        print(name, cell, cl, holds)
    print('wrote', SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)')


if __name__ == '__main__':
    main()
