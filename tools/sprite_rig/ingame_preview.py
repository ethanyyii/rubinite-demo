"""Turn the in-game captures of tests/sim/capture_player_sprites.gd into preview videos.

    python3 tools/sprite_rig/ingame_preview.py <capture dir> <out dir> [--scale=K] [--gif] [--sheet=N]

For each scene folder (f0001.png ... and log.tsv: one crop around the player per physics frame,
hitstop frames included): <scene>.mp4 at 60 fps (the game's own speed; needs ffmpeg), each
sprite pixel K x K (default 3). Full-screen shots (full_*.png) are copied at 2x as <scene>_full_*.png.
--gif also writes <scene>.gif (20 ms a frame: GIFs cannot do 60 fps, so 0.83x). --sheet=N writes
<scene>_sheet.png, every N-th frame labelled with the state, its frame and the sprite cell shown
(for checking by eye; not for the preview page).
"""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw


def rows(d):
    with open(os.path.join(d, 'log.tsv')) as fh:
        head = fh.readline().rstrip('\n').split('\t')
        return [dict(zip(head, line.rstrip('\n').split('\t'))) for line in fh if line.strip()]


def frames(d, log, k):
    out = []
    for r in log:
        im = Image.open(os.path.join(d, 'f%04d.png' % int(r['frame']))).convert('RGB')
        out.append(im.resize((im.width * k, im.height * k), Image.NEAREST))
    return out


def mp4(ims, path):
    tmp = tempfile.mkdtemp()
    try:
        for i, im in enumerate(ims):
            im.save(os.path.join(tmp, '%05d.png' % i))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '60', '-i', os.path.join(tmp, '%05d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '12', '-preset', 'slow',
                        '-tune', 'animation', path], check=True)
    finally:
        shutil.rmtree(tmp)


def gif(ims, path):
    step = max(1, len(ims) // 40)
    sample = ims[::step][:40]
    stack = Image.new('RGB', (ims[0].width, ims[0].height * len(sample)))
    for i, f in enumerate(sample):
        stack.paste(f, (0, i * f.height))
    pal = stack.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in ims]
    q[0].save(path, save_all=True, append_images=q[1:], duration=20, loop=0)


def sheet(d, log, path, every, k=2, cols=10):
    pick = [r for r in log if int(r['frame']) % every == 0]
    im0 = Image.open(os.path.join(d, 'f%04d.png' % int(pick[0]['frame'])))
    w, h = im0.width * k, im0.height * k
    lab = 14
    out = Image.new('RGB', (cols * w, ((len(pick) + cols - 1) // cols) * (h + lab)), (255, 255, 255))
    dr = ImageDraw.Draw(out)
    for i, r in enumerate(pick):
        im = Image.open(os.path.join(d, 'f%04d.png' % int(r['frame']))).convert('RGB').resize((w, h), Image.NEAREST)
        x, y = (i % cols) * w, (i // cols) * (h + lab)
        out.paste(im, (x, y + lab))
        stop = ' hitstop' if int(r['hitstop']) > 0 else ''
        dr.text((x + 2, y + 1), f"{r['frame']} {r['state']} e{r['elapsed']} {r['sheet']} r{r['row']}c{r['col']}{stop}",
                fill=(0, 0, 0))
    out.save(path)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opts = dict((a[2:].split('=', 1) + [''])[:2] for a in sys.argv[1:] if a.startswith('--'))
    src, dst = args
    k = int(opts.get('scale') or 3)
    os.makedirs(dst, exist_ok=True)
    for scene in sorted(os.listdir(src)):
        d = os.path.join(src, scene)
        if not os.path.isfile(os.path.join(d, 'log.tsv')):
            continue
        log = rows(d)
        ims = frames(d, log, k)
        mp4(ims, os.path.join(dst, f'{scene}.mp4'))
        if 'gif' in opts:
            gif(ims, os.path.join(dst, f'{scene}.gif'))
        if opts.get('sheet'):
            sheet(d, log, os.path.join(dst, f'{scene}_sheet.png'), int(opts['sheet']))
        for f in sorted(os.listdir(d)):
            if f.startswith('full_'):
                im = Image.open(os.path.join(d, f)).convert('RGB')
                im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(dst, f'{scene}_{f}'))
        print(scene, len(log), 'frames')


if __name__ == '__main__':
    main()
