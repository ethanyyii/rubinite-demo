"""Boss idle and walk: sprite sheets and previews.

    python3 tools/boss_rig/export_anim.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game). Rows: down, right, up, left.
    boss_idle.png        12 columns of 256x224, foot anchor (128, 208); 10 combat frames a pose
    boss_walk.png        20 columns of 256x272, foot anchor (128, 208); 4 combat frames a pose
                         (2 at the fast approach)
    boss_walk_start.png  10 columns of 256x272: standing -> walk; the loop goes on at column
                         anim_walk.START_JOIN (6)
    boss_walk_stop.png   4 x 8 columns of 256x272: walk -> standing, one group of 8 for each of
                         the loop's columns 0, 5, 10, 15 (play the group nearest to the column
                         the walk ends on)
Previews -> docs/art-preview/boss/idle_walk/:
    idle_<dir>.gif, idle_all.gif     the idle at its real timing
    walk_<dir>_slow.mp4, _fast.mp4   the loop, 60 fps, the ground scrolling at the game's speed
    move_<dir>.mp4                   standing -> start -> walk -> stop -> standing, 60 fps, the
                                     ground moving only while the game moves the Boss
    walk_all.gif, move_all.gif       four directions side by side (GIF: one frame per pose)
    *_frames_<dir>.png               every pose; walk_legs_side.png: the side view's legs alone
    index.html                       everything on one page
Needs ffmpeg for the mp4s (skipped with --no-video).
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
FLOOR = (66, 63, 68)
MARK = (96, 91, 96)
GRID = 40                # px between ground marks (one step)
BOX = (8, 40, 248, 252)  # preview window in the walk frame (room for the dragged sword)
IDLE_BOX = (rig.AX - 70, 44, rig.AX + 70, rig.AY + 12)
STEP = gait.STRIDE / gait.POSES      # px the game moves the Boss per pose


def sheet(rows, path, fh):
    """rows: {direction: [frames]} -> one sheet, a row per direction."""
    n = len(rows['down'])
    im = Image.new('RGBA', (rig.FW * n, fh * 4), (0, 0, 0, 0))
    for r, d in enumerate(rig.DIRS):
        for c, f in enumerate(rows[d]):
            im.alpha_composite(rig.image(f, (rig.FW, fh)), (c * rig.FW, r * fh))
    im.save(path)


def floor(size, box, k, direction, shift):
    """Ground with marks every GRID px, moved `shift` px against the walking direction."""
    w, h = size
    im = Image.new('RGB', (w, h), preview.BG)
    d = ImageDraw.Draw(im)
    gy = (rig.AY + 1 - box[1]) * k
    shift = round(shift)
    if direction in ('right', 'left'):
        top = gy - 14 * k
        d.rectangle((0, top, w, h), fill=FLOOR)
        sgn = -1 if direction == 'right' else 1
        x0 = (rig.AX - box[0]) * k
        for n in range(-12, 13):
            x = x0 + (n * GRID + sgn * (shift % GRID)) * k
            d.rectangle((x, gy, x + k - 1, gy + 5 * k), fill=MARK)
    else:
        # seen from the front / back the ground runs up and down the screen (0.35 of the depth)
        top = gy - 40 * k
        d.rectangle((0, top, w, h), fill=FLOOR)
        sgn = -1 if direction == 'down' else 1
        for n in range(-24, 25):
            y = gy + round((n * GRID + sgn * (shift % GRID)) * anim_walk.DEPTH) * k
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


def timeline_move(d, hold=gait.HOLD):
    """Standing, start, walk, stop, standing - what the game would show - per combat frame."""
    stand = rig.pixels(rig.standing()[d])
    walk = anim_walk.frames(d)
    loop = list(range(anim_walk.START_JOIN, gait.POSES)) + list(range(gait.POSES)) + list(range(0, 11))
    stop_from = loop[-1]
    moving = anim_walk.frames(d, 'walk_start') + [walk[i] for i in loop]
    out, dist = [], 0.0
    for _ in range(36):
        out.append((stand, 0.0))
    for f in moving:
        for _ in range(hold):
            dist += STEP / hold
            out.append((f, dist))
    for f in anim_walk.frames(d, f'walk_stop_{stop_from}'):
        for _ in range(hold):
            out.append((f, dist))
    for _ in range(48):
        out.append((stand, dist))
    return out


def video(path, timeline, direction, k=3, box=BOX):
    size = ((box[2] - box[0]) * k, (box[3] - box[1]) * k)
    tmp = tempfile.mkdtemp()
    for n, (f, shift) in enumerate(timeline):
        paste_sprite(floor(size, box, k, direction, shift), f, box, k).save(os.path.join(tmp, f'{n:04d}.png'))
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


def side_by_side(path, timelines, k=2, box=BOX, every=gait.HOLD):
    """All four directions in one GIF, one GIF frame per `every` combat frames."""
    w, h = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    n = len(timelines['down'])
    ims = []
    for i in range(0, n, every):
        im = Image.new('RGB', (w * 4, h), preview.BG)
        for j, d in enumerate(rig.DIRS):
            f, shift = timelines[d][i]
            im.paste(paste_sprite(floor((w, h), box, k, d, shift), f, box, k), (j * w, 0))
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


def hands_sheet(path, idle, walk, k=4):
    """Close-ups of the sword hand: standing (top) and dragging (bottom), four directions."""
    boxes = {'down': (48, 56, 148, 190), 'right': (78, 56, 178, 190), 'up': (108, 56, 208, 190),
             'left': (78, 56, 178, 190)}
    walk_boxes = {'down': (40, 66, 140, 200), 'right': (70, 66, 170, 200), 'up': (112, 66, 212, 200),
                  'left': (86, 66, 186, 200)}
    w, h = 100 * k, 134 * k
    out = Image.new('RGB', (4 * (w + 8), 2 * (h + 8)), preview.BG)
    for j, d in enumerate(rig.DIRS):
        out.paste(preview.render(idle[d][0], boxes[d], k, ground=False), (j * (w + 8), 0))
        out.paste(preview.render(walk[d][5], walk_boxes[d], k, ground=False), (j * (w + 8), h + 8))
    out.save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 待機與走路</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）待機與走路</h1>
<p>還沒接進遊戲。四個方向：朝下、朝右、朝上、朝左。劍一律在右手：朝左時右手在遠側，握劍的手被身體擋住，靠鏡頭的左手是空的（不是朝右的鏡像）。劍上的火焰、符文發光之後由程式畫，這裡沒有。</p>
<h2>握劍的手（放大）</h2>
<figure><img src="hands_closeup.png"><figcaption>上排：站姿。下排：拖劍走路。由左到右朝下、朝右、朝上、朝左</figcaption></figure>
<h2>從站著到走、再停下來（緩步）</h2>
<p>站著 → 起步（劍放倒拖在身後、身體前傾）→ 走 → 停步（收腳、站直、把劍拉回來立好）→ 站著。地面只在 Boss 真的在移動時才動，地上的記號每 40px 一條（一步）。</p>
<figure><img src="move_all.gif"><figcaption>四個方向，遊戲裡的大小（2 倍）</figcaption></figure><br>
%(move)s
<h2>走路循環：緩步（每秒 60px，一步 0.67 秒）</h2>
%(slow)s
<h2>走路循環：快步（每秒 120px，同一組圖播快一倍）</h2>
%(fast)s
<h2>待機（呼吸一輪 2 秒）</h2>
<p>朝下、朝右、朝上和上次一樣；朝左重畫了（劍在遠側的手）。</p>
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
    if video_ok:
        move = ''.join(fig(f'move_{d}.mp4', NAMES[d]) for d in rig.DIRS)
        slow = ''.join(fig(f'walk_{d}_slow.mp4', NAMES[d]) for d in rig.DIRS)
        fast = ''.join(fig(f'walk_{d}_fast.mp4', NAMES[d]) for d in rig.DIRS)
    else:
        move = slow = fast = '<p>（沒有 ffmpeg，略過影片；看上面的 GIF）</p>'
    sheets = ''
    for a, b in (('walk', '走路循環'), ('walk_start', '起步'), ('walk_stop', '停步（從循環第 0、5、10、15 張）')):
        sheets += ''.join(fig(f'{a}_frames_{d}.png', f'{b} {NAMES[d]}') for d in ('down', 'right', 'up'))
    sheets += fig('walk_legs_side.png', '走路循環側面的腿（綠線＝靠鏡頭的腿，藍線＝另一條）')
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'move': move, 'slow': slow, 'fast': fast, 'sheets': sheets})


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    os.makedirs(SHEETS, exist_ok=True)
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    idle = {d: anim_idle.frames(d) for d in rig.DIRS}
    walk = {d: anim_walk.frames(d) for d in rig.DIRS}
    start = {d: anim_walk.frames(d, 'walk_start') for d in rig.DIRS}
    stop = {d: [f for e in anim_walk.STOP_FROM for f in anim_walk.frames(d, f'walk_stop_{e}')] for d in rig.DIRS}
    sheet(idle, os.path.join(SHEETS, 'boss_idle.png'), rig.FH)
    sheet(walk, os.path.join(SHEETS, 'boss_walk.png'), anim_walk.FH)
    sheet(start, os.path.join(SHEETS, 'boss_walk_start.png'), anim_walk.FH)
    sheet(stop, os.path.join(SHEETS, 'boss_walk_stop.png'), anim_walk.FH)
    moves = {d: timeline_move(d) for d in rig.DIRS}
    for d in rig.DIRS:
        preview.gif(os.path.join(OUT, f'idle_{d}.gif'), idle[d], [anim_idle.HOLD] * anim_idle.N, k=3, box=IDLE_BOX)
        if video_ok:
            video(os.path.join(OUT, f'walk_{d}_slow.mp4'), timeline_loop(walk[d], gait.HOLD, 3), d)
            video(os.path.join(OUT, f'walk_{d}_fast.mp4'), timeline_loop(walk[d], gait.HOLD // 2, 6), d)
            video(os.path.join(OUT, f'move_{d}.mp4'), moves[d], d)
        if d != 'left':
            preview.contact(walk[d], k=3, cols=5, box=BOX).save(os.path.join(OUT, f'walk_frames_{d}.png'))
            preview.contact(start[d], k=3, cols=5, box=BOX).save(os.path.join(OUT, f'walk_start_frames_{d}.png'))
            preview.contact(stop[d], k=2, cols=8, box=BOX,
                            labels=[f'{e}:{j}' for e in anim_walk.STOP_FROM for j in range(anim_walk.STOP_N)]).save(
                os.path.join(OUT, f'walk_stop_frames_{d}.png'))
    idle_all(os.path.join(OUT, 'idle_all.gif'), idle)
    side_by_side(os.path.join(OUT, 'walk_all.gif'), {d: timeline_loop(walk[d], gait.HOLD, 1) for d in rig.DIRS})
    side_by_side(os.path.join(OUT, 'move_all.gif'), moves)
    legs_sheet(os.path.join(OUT, 'walk_legs_side.png'))
    hands_sheet(os.path.join(OUT, 'hands_closeup.png'), idle, walk)
    write_html(video_ok)
    print('wrote', SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)')


if __name__ == '__main__':
    main()
