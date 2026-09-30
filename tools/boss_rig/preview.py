"""Preview helpers for the Boss animations: contact sheets, GIFs, difference views."""
import os
from PIL import Image, ImageDraw, ImageFont
import rig

BG = (58, 56, 60)
GROUND = (110, 104, 100)


def font(size):
    for p in ('/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def union_bbox(frames, pad=3):
    xs = [q[0] for f in frames for q in f]
    ys = [q[1] for f in frames for q in f]
    return min(xs) - pad, min(ys) - pad, max(xs) + 1 + pad, max(ys) + 1 + pad


def render(pix, box, k, bg=BG, ground=True):
    w, h = box[2] - box[0], box[3] - box[1]
    im = Image.new('RGB', (w, h), bg)
    p = im.load()
    if ground:
        gy = rig.AY + 1 - box[1]
        if 0 <= gy < h:
            for x in range(w):
                p[x, gy] = GROUND
    for (x, y), c in pix.items():
        if box[0] <= x < box[2] and box[1] <= y < box[3]:
            p[x - box[0], y - box[1]] = tuple(c[:3])
    return im.resize((w * k, h * k), Image.NEAREST)


def contact(frames, k=3, cols=6, labels=None, diff_from=None, box=None):
    """Frames in a grid. diff_from: a frame; pixels that differ from it are outlined in green
    in a second copy below each frame."""
    box = box or union_bbox(frames)
    tiles = [render(f, box, k) for f in frames]
    if diff_from is not None:
        for i, f in enumerate(frames):
            t = render(f, box, k)
            d = ImageDraw.Draw(t)
            for q in set(f) | set(diff_from):
                if f.get(q) != diff_from.get(q):
                    X, Y = (q[0] - box[0]) * k, (q[1] - box[1]) * k
                    d.rectangle((X, Y, X + k - 1, Y + k - 1), outline=(0, 255, 0))
            both = Image.new('RGB', (t.width, t.height * 2 + 4), BG)
            both.paste(tiles[i], (0, 0))
            both.paste(t, (0, t.height + 4))
            tiles[i] = both
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (tw + 6) + 6, rows * (th + 24) + 6), BG)
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        x, y = 6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 24)
        sheet.paste(t, (x, y + 18))
        d.text((x + 2, y), labels[i] if labels else str(i), font=font(14), fill=(235, 228, 220))
    return sheet


def gif(path, frames, holds, k=3, box=None, offsets=None, grid=None):
    """Animated GIF; holds = combat frames (1/60 s) per pose. offsets: per pose (dx, dy) in
    final px the sprite is moved on the canvas (moving previews); grid: spacing of ground
    marks in px (drawn when moving)."""
    box = box or union_bbox(frames)
    ims = []
    for i, f in enumerate(frames):
        if offsets:
            dx, dy = offsets[i]
            f = {(x + dx, y + dy): c for (x, y), c in f.items()}
        ims.append(render(f, box, k))
    # GIF delays are in 1/100 s: spread the rounding so the loop length stays right
    durs, acc = [], 0.0
    for h in holds:
        t = h * 1000 / 60
        d = round((acc + t) / 10) * 10 - round(acc / 10) * 10
        acc += t
        durs.append(max(20, d))
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=durs, loop=0, disposal=1)
