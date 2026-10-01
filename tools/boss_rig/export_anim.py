"""Boss idle and the four ways he moves: sprite sheets and previews.

    python3 tools/boss_rig/export_anim.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game). Rows: down, right, up, left.
    boss_idle.png             12 columns of 256x224, foot anchor (128, 208); 10 combat frames a pose
For each way of moving (256x224 cells, foot anchor (128, 208), 4 combat frames a pose;
walk also 2 at the fast approach); the sword is carried on the right shoulder in all of them:
    boss_walk.png             forward, 20 columns
    boss_walk_back.png        backwards (retreat), 20 columns
    boss_strafe_r.png         sideways towards his own right, 20 columns
    boss_strafe_l.png         sideways towards his own left, 20 columns
    <name>_start.png          12 columns of 384x336, foot anchor (192, 272) (the sword goes up
                              over his head): standing -> moving; the loop goes on at column
                              anim_walk.START_JOINS[kind] (walk 8, back 16, strafe 8)
    <name>_stop.png           4 x 10 columns of 384x336, foot anchor (192, 272): moving ->
                              standing, one group of 10 for each of the loop's columns 0, 5, 10,
                              15 (play the group nearest to the column the loop ends on)
Previews -> docs/art-preview/boss/idle_walk/:
    idle_<dir>.gif, idle_all.gif     the idle at its real timing
    walk_<dir>_slow.mp4, _fast.mp4   the forward loop, 60 fps
    move_<dir>.mp4, move_all.gif     forward: standing -> start -> loop -> stop -> standing
    move_<kind>_<dir>.mp4, move_<kind>_all.gif   the same for back, strafe_r, strafe_l
    *_frames_<dir>.png               every pose; walk_legs_side.png: the side view's legs alone
    carry_four.png                   the carry in the four directions, side by side
    hands_closeup.png                the sword hand at 5x: standing, half-way up, carrying (each
                                     way of moving), half-way down - in the four directions
    index.html                       everything on one page
In the videos the Boss stays put and the ground moves under him the way the game moves him
(60 px/s on screen in every direction: the game is top-down, nothing is foreshortened), only
while he moves; a mark every 40 px (one step). Needs ffmpeg (skipped with --no-video).
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
import anim_idle
import anim_walk
import preview

SHEETS = os.path.join(B.ROOT, 'assets', 'sprites', 'boss')
OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'idle_walk')
NAMES = {'down': '朝下', 'right': '朝右', 'up': '朝上', 'left': '朝左'}
SHEET_OF = {'walk': 'boss_walk', 'back': 'boss_walk_back', 'strafe_r': 'boss_strafe_r', 'strafe_l': 'boss_strafe_l'}
KIND_NAMES = {'walk': '往前走', 'back': '後退', 'strafe_r': '往他的右手邊側移', 'strafe_l': '往他的左手邊側移'}
FACING = {'down': (0, 1), 'right': (1, 0), 'up': (0, -1), 'left': (-1, 0)}
FLOOR = (66, 63, 68)
MARK = (96, 91, 96)
GRID = 40                # px between ground marks (one step)
BOX = (8, 16, 248, 222)  # preview window in the walk frame (room for the carried sword)
# ... and for anything with the way up / down in it: the sword stands over his head and points
# forward past the small frame
MOVE_BOX = (-40, -56, 296, 222)
IDLE_BOX = (rig.AX - 70, 44, rig.AX + 70, rig.AY + 12)
STEP = gait.STRIDE / gait.POSES      # px the game moves the Boss per pose
STOP_AT = 10                         # the previews stop the loop on this pose


def travel(direction, kind):
    """Where the Boss goes on screen: (dx, dy) unit vector."""
    fx, fy = FACING[direction]
    if kind == 'walk':
        return fx, fy
    if kind == 'back':
        return -fx, -fy
    rx, ry = -fy, fx                 # his right: screen left when he faces the camera
    return (rx, ry) if kind == 'strafe_r' else (-rx, -ry)


def sheet(rows, path, fh, big=False):
    """rows: {direction: [frames]} -> one sheet, a row per direction. big: cells of the attack
    container (anim_walk.BIG), the frames moved by anim_walk.EXT."""
    n = len(rows['down'])
    cw, ch = anim_walk.BIG if big else (rig.FW, fh)
    off = anim_walk.EXT if big else 0
    im = Image.new('RGBA', (cw * n, ch * 4), (0, 0, 0, 0))
    for r, d in enumerate(rig.DIRS):
        for c, f in enumerate(rows[d]):
            im.alpha_composite(rig.image({(x + off, y + off): v for (x, y), v in f.items()}, (cw, ch)), (c * cw, r * ch))
    im.save(path)


def floor(size, box, k, tv, shift):
    """Ground with marks every GRID px, moved `shift` px against the travel direction tv."""
    w, h = size
    im = Image.new('RGB', (w, h), preview.BG)
    d = ImageDraw.Draw(im)
    gy = (rig.AY + 1 - box[1]) * k
    off = round(shift) % GRID
    if tv[0]:
        top = gy - 14 * k
        d.rectangle((0, top, w, h), fill=FLOOR)
        x0 = (rig.AX - box[0]) * k
        for n in range(-12, 13):
            x = x0 + (n * GRID - tv[0] * off) * k
            d.rectangle((x, gy, x + k - 1, gy + 5 * k), fill=MARK)
    else:
        top = gy - 44 * k
        d.rectangle((0, top, w, h), fill=FLOOR)
        for n in range(-12, 13):
            y = gy + (n * GRID - tv[1] * off) * k
            if top <= y < h:
                d.rectangle((0, y, w, y + k - 1), fill=MARK)
    return im


def paste_sprite(bg, pix, box, k):
    spr = Image.new('RGBA', (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    p = spr.load()
    for (x, y), c in pix.items():
        if box[0] <= x < box[2] and box[1] <= y < box[3]:
            p[x - box[0], y - box[1]] = tuple(c) + (255,)
    spr = spr.resize((spr.width * k, spr.height * k), Image.NEAREST)
    bg.paste(spr, (0, 0), spr)
    return bg


def timeline_loop(frames, hold, loops):
    """[(pose, px the ground has moved)] per combat frame."""
    out, n = [], 0
    for _ in range(loops):
        for f in frames:
            for _ in range(hold):
                out.append((f, n * STEP / hold))
                n += 1
    return out


def timeline_move(d, kind='walk', hold=gait.HOLD):
    """Standing, start, loop, stop, standing - what the game would show - per combat frame."""
    stand = rig.pixels(rig.standing()[d])
    loop = anim_walk.frames(d, kind)
    seq, i = [], anim_walk.START_JOINS[kind]
    while len(seq) < 24 or seq[-1] != STOP_AT:
        seq.append(i % gait.POSES)
        i += 1
    moving = anim_walk.frames(d, f'{kind}_start') + [loop[j] for j in seq]
    out, dist = [], 0.0
    for _ in range(36):
        out.append((stand, 0.0))
    for f in moving:
        for _ in range(hold):
            dist += STEP / hold
            out.append((f, dist))
    for f in anim_walk.frames(d, f'{kind}_stop_{STOP_AT}'):
        for _ in range(hold):
            out.append((f, dist))
    for _ in range(48):
        out.append((stand, dist))
    return out


def video(path, timeline, tv, k=3, box=MOVE_BOX):
    size = ((box[2] - box[0]) * k, (box[3] - box[1]) * k)
    tmp = tempfile.mkdtemp()
    for n, (f, shift) in enumerate(timeline):
        paste_sprite(floor(size, box, k, tv, shift), f, box, k).save(os.path.join(tmp, f'{n:04d}.png'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '60', '-i', os.path.join(tmp, '%04d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '10', '-movflags', '+faststart', path],
                   check=True)
    shutil.rmtree(tmp)


def gif_durations(holds):
    durs, acc = [], 0.0
    for h in holds:
        t = h * 1000 / 60
        durs.append(max(20, round((acc + t) / 10) * 10 - round(acc / 10) * 10))
        acc += t
    return durs


def side_by_side(path, timelines, kind, k=2, box=MOVE_BOX, every=gait.HOLD):
    """All four directions in one GIF, one GIF frame per `every` combat frames."""
    w, h = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    n = len(timelines['down'])
    ims = []
    for i in range(0, n, every):
        im = Image.new('RGB', (w * 4, h), preview.BG)
        for j, d in enumerate(rig.DIRS):
            f, shift = timelines[d][i]
            im.paste(paste_sprite(floor((w, h), box, k, travel(d, kind), shift), f, box, k), (j * w, 0))
        ims.append(im.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=gif_durations([every] * len(ims)), loop=0)


def idle_all(path, idle, k=2):
    box = IDLE_BOX
    w, h = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    ims = []
    for i in range(anim_idle.N):
        im = Image.new('RGB', (w * 4, h), preview.BG)
        for j, d in enumerate(rig.DIRS):
            im.paste(preview.render(idle[d][i], box, k), (j * w, 0))
        ims.append(im)
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=gif_durations([anim_idle.HOLD] * anim_idle.N),
                loop=0)


def legs_sheet(path, k=6):
    """The side view's legs alone (near + far), with the model's hip, knee, ankle."""
    lay = rig.Layout('right')
    box = (76, 118, 184, 214)
    tiles = []
    for i in range(gait.POSES):
        near, far = limb.legs(i)
        f = {(x, y - anim_walk.FAR_UP): c for (x, y), c in far.items()}
        f.update(near)
        t = preview.render(f, box, k)
        d = ImageDraw.Draw(t)
        for other, col in ((True, (90, 150, 255)), (False, (120, 255, 120))):
            L = gait.leg(gait.phase(i), other)
            J = limb.joints_work(L, lay)
            up = anim_walk.FAR_UP if other else 0
            pts = [((J[n][0] / B.WORK - box[0]) * k, (J[n][1] / B.WORK - up - box[1]) * k) for n in ('hip', 'knee', 'ankle')]
            d.line(pts, fill=col, width=2)
            for q in pts:
                d.ellipse((q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3), outline=col)
        d.text((4, 2), f'{i}  hips -{anim_walk.loop_state(i)["D"]}', font=preview.font(14), fill=(235, 228, 220))
        tiles.append(t)
    cols = 5
    tw, th = tiles[0].size
    out = Image.new('RGB', (cols * (tw + 4), (len(tiles) // cols) * (th + 4)), preview.BG)
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * (tw + 4), (i // cols) * (th + 4)))
    out.save(path)


def strafe_legs_sheet(path, loops, k=4):
    """The legs of the sidestep and the backward walk, every other pose, four directions."""
    box = (60, 118, 200, 222)
    rows = []
    for kind in ('strafe_r', 'strafe_l', 'back'):
        for d in rig.DIRS:
            rows.append((f'{KIND_NAMES[kind]} {NAMES[d]}', [loops[kind][d][i] for i in range(0, gait.POSES, 2)]))
    tw, th = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    out = Image.new('RGB', (10 * (tw + 4) + 4, len(rows) * (th + 26) + 4), preview.BG)
    dr = ImageDraw.Draw(out)
    for r, (label, fr) in enumerate(rows):
        y = 4 + r * (th + 26)
        dr.text((6, y), label, font=preview.font(16), fill=(235, 228, 220))
        for c, f in enumerate(fr):
            out.paste(preview.render(f, box, k), (4 + c * (tw + 4), y + 22))
    out.save(path)


HAND_BOX = {'down': (62, 48, 146, 116), 'right': (96, 44, 180, 112), 'up': (110, 44, 194, 112), 'left': (76, 44, 160, 112)}


def _labelled(rows, path, tile, left=150):
    """rows: [(label, [tiles])] -> one sheet, the label left of each row."""
    tw, th = tile
    out = Image.new('RGB', (left + 4 * (tw + 6), 24 + len(rows) * (th + 6)), preview.BG)
    d = ImageDraw.Draw(out)
    for j, name in enumerate(rig.DIRS):
        d.text((left + j * (tw + 6) + 4, 3), NAMES[name], font=preview.font(16), fill=(235, 228, 220))
    for r, (label, tiles) in enumerate(rows):
        y = 24 + r * (th + 6)
        d.text((6, y + 6), label, font=preview.font(16), fill=(235, 228, 220))
        for j, t in enumerate(tiles):
            out.paste(t, (left + j * (tw + 6), y))
    out.save(path)


def hands_sheet(path, k=5):
    """Close-ups of the sword hand, the hilt and the shoulder (animation-review §5): standing,
    half-way up, carrying in each way of moving, half-way down - the four directions side by side."""
    stand = rig.standing()
    stages = [('站姿', lambda d: rig.pixels(stand[d]))]
    stages += [(f'起步第 {i + 1} 張', lambda d, i=i: anim_walk.frames(d, 'walk_start')[i]) for i in (1, 3, 5, 7, 9)]
    stages += [(KIND_NAMES[kind], lambda d, kind=kind: anim_walk.frames(d, kind)[5]) for kind in anim_walk.KINDS]
    stages += [(f'停步第 {i + 1} 張', lambda d, i=i: anim_walk.frames(d, f'walk_stop_{STOP_AT}')[i]) for i in (2, 4, 6, 8)]
    rows = [(label, [preview.render(get(d), HAND_BOX[d], k, ground=False) for d in rig.DIRS]) for label, get in stages]
    _labelled(rows, path, rows[0][1][0].size)


def carry_sheet(path, loops, k=2):
    """The carry in the four directions side by side: one 3D pose, four views."""
    box = (6, 18, 250, 218)
    rows = [(KIND_NAMES[kind], [preview.render(loops[kind][d][5], box, k) for d in rig.DIRS])
            for kind in ('walk', 'back')]
    _labelled(rows, path, rows[0][1][0].size, left=70)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 待機與移動</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）待機與移動</h1>
<p>還沒接進遊戲。四個方向：朝下、朝右、朝上、朝左。<b>所有移動（往前走、後退、左右側移）都把劍橫著扛在右肩上</b>：劍身平放在肩甲上、劍尖朝後、右手在肩膀前握著握柄。劍一律在右手：朝左時右手在遠側，劍和握劍的手被身體擋住，靠鏡頭的左手是空的（不是朝右的鏡像）。劍上的火焰、符文發光之後由程式畫，這裡沒有。</p>
<p>影片裡 Boss 留在原地，地面照遊戲裡的速度（每秒 60px）往反方向移動，只有 Boss 真的在移動時才動；地上的記號每 40px 一條（一步）。</p>
<h2>扛劍的姿勢：四個方向</h2>
<figure><img src="carry_four.png"><figcaption>同一個姿勢從四個方向看（2 倍）。上排往前走（身體前傾），下排後退（身體直立）</figcaption></figure>
<h2>握劍的手（放大 5 倍）</h2>
<figure><img src="hands_closeup.png"><figcaption>由上到下：站姿、把劍從身前往上繞、扛上肩的過程、四種移動、把劍從肩上舉起、在身前放回地上的過程</figcaption></figure>
<h2>往前走：從站著到走、再停下來</h2>
<p>站著 → 起步（劍從身前往上繞一圈扛到肩上、身體前傾）→ 走 → 停步（收腳、站直，劍從肩上舉起、在身前繞下來立回地上）→ 站著。</p>
<figure><img src="move_all.gif"><figcaption>四個方向，遊戲裡的大小（2 倍）</figcaption></figure><br>
%(move)s
<h2>往前走的循環：緩步（每秒 60px，一步 0.67 秒）</h2>
%(slow)s
<h2>往前走的循環：快步（每秒 120px，同一組圖播快一倍）</h2>
%(fast)s
<h2>側移：面向主角，往他自己的右手邊走</h2>
<p>站著 → 起步 → 側移 → 停步 → 站著。「朝下」就是主角在畫面下方、Boss 面向下方，往畫面左邊走（他的右手邊）；「朝右」時他的右手邊是靠鏡頭那一側，所以往畫面下方走。</p>
<figure><img src="move_strafe_r_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>
%(strafe_r)s
<h2>側移：往他自己的左手邊走</h2>
<figure><img src="move_strafe_l_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>
%(strafe_l)s
<h2>後退：面向主角往後走</h2>
<figure><img src="move_back_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>
%(back)s
<figure><img src="strafe_back_legs.png"><figcaption>側移與後退的腿（每隔一張）</figcaption></figure>
<h2>待機（呼吸一輪 2 秒；沒改）</h2>
<figure><img src="idle_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure>
<h2>逐張</h2>
%(sheets)s
'''


def write_html(video_ok):
    def fig(src, cap):
        if src.endswith('.mp4'):
            return (f'<figure><video src="{src}" autoplay loop muted playsinline controls></video>'
                    f'<figcaption>{cap}</figcaption></figure>')
        return f'<figure><img src="{src}"><figcaption>{cap}</figcaption></figure>'
    none = '<p>（沒有 ffmpeg，略過影片；看上面的 GIF）</p>'
    v = {'move': none, 'slow': none, 'fast': none, 'back': none, 'strafe_r': none, 'strafe_l': none}
    if video_ok:
        v['move'] = ''.join(fig(f'move_{d}.mp4', NAMES[d]) for d in rig.DIRS)
        v['slow'] = ''.join(fig(f'walk_{d}_slow.mp4', NAMES[d]) for d in rig.DIRS)
        v['fast'] = ''.join(fig(f'walk_{d}_fast.mp4', NAMES[d]) for d in rig.DIRS)
        for kind in ('back', 'strafe_r', 'strafe_l'):
            v[kind] = ''.join(fig(f'move_{kind}_{d}.mp4', NAMES[d]) for d in rig.DIRS)
    sheets = ''
    for kind in anim_walk.KINDS:
        b = KIND_NAMES[kind]
        sheets += ''.join(fig(f'{kind}_frames_{d}.png', f'{b} {NAMES[d]}') for d in rig.DIRS)
        sheets += ''.join(fig(f'{kind}_start_frames_{d}.png', f'{b}的起步 {NAMES[d]}') for d in rig.DIRS)
        sheets += ''.join(fig(f'{kind}_stop_frames_{d}.png', f'{b}的停步（從循環第 0、5、10、15 張）{NAMES[d]}') for d in rig.DIRS)
    sheets += fig('walk_legs_side.png', '往前走側面的腿（綠線＝靠鏡頭的腿，藍線＝另一條）')
    v['sheets'] = sheets
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % v)


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    os.makedirs(SHEETS, exist_ok=True)
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    idle = {d: anim_idle.frames(d) for d in rig.DIRS}
    sheet(idle, os.path.join(SHEETS, 'boss_idle.png'), rig.FH)
    loops = {}
    for kind in anim_walk.KINDS:
        loop = {d: anim_walk.frames(d, kind) for d in rig.DIRS}
        start = {d: anim_walk.frames(d, f'{kind}_start') for d in rig.DIRS}
        stop = {d: [f for e in anim_walk.STOP_FROM for f in anim_walk.frames(d, f'{kind}_stop_{e}')] for d in rig.DIRS}
        loops[kind] = loop
        name = SHEET_OF[kind]
        sheet(loop, os.path.join(SHEETS, name + '.png'), anim_walk.FH)
        sheet(start, os.path.join(SHEETS, name + '_start.png'), anim_walk.FH, big=True)
        sheet(stop, os.path.join(SHEETS, name + '_stop.png'), anim_walk.FH, big=True)
        moves = {d: timeline_move(d, kind) for d in rig.DIRS}
        tag = '' if kind == 'walk' else kind + '_'
        for d in rig.DIRS:
            tv = travel(d, kind)
            if video_ok:
                video(os.path.join(OUT, f'move_{tag}{d}.mp4'), moves[d], tv)
                if kind == 'walk':
                    video(os.path.join(OUT, f'walk_{d}_slow.mp4'), timeline_loop(loop[d], gait.HOLD, 3), tv)
                    video(os.path.join(OUT, f'walk_{d}_fast.mp4'), timeline_loop(loop[d], gait.HOLD // 2, 6), tv)
            preview.contact(loop[d], k=3, cols=5, box=BOX).save(os.path.join(OUT, f'{kind}_frames_{d}.png'))
            preview.contact(start[d], k=2, cols=6, box=MOVE_BOX).save(os.path.join(OUT, f'{kind}_start_frames_{d}.png'))
            preview.contact(stop[d], k=1, cols=10, box=MOVE_BOX,
                            labels=[f'{e}:{j}' for e in anim_walk.STOP_FROM for j in range(anim_walk.STOP_N)]).save(
                os.path.join(OUT, f'{kind}_stop_frames_{d}.png'))
        side_by_side(os.path.join(OUT, f'move_{tag}all.gif'), moves, kind)
        if kind == 'walk':
            side_by_side(os.path.join(OUT, 'walk_all.gif'), {d: timeline_loop(loop[d], gait.HOLD, 1) for d in rig.DIRS}, kind)
    for d in rig.DIRS:
        preview.gif(os.path.join(OUT, f'idle_{d}.gif'), idle[d], [anim_idle.HOLD] * anim_idle.N, k=3, box=IDLE_BOX)
    idle_all(os.path.join(OUT, 'idle_all.gif'), idle)
    legs_sheet(os.path.join(OUT, 'walk_legs_side.png'))
    strafe_legs_sheet(os.path.join(OUT, 'strafe_back_legs.png'), loops)
    hands_sheet(os.path.join(OUT, 'hands_closeup.png'))
    carry_sheet(os.path.join(OUT, 'carry_four.png'), loops)
    write_html(video_ok)
    print('wrote', SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)')


if __name__ == '__main__':
    main()
