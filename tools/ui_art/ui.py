"""The combat UI's pixel art (2026-10-06, the user: "UI美化，主角的血條，回血次數要用什麼貼圖，boss的血條都要美化").

    python3 tools/ui_art/ui.py [preview <out.png>]

Writes assets/sprites/ui/: the knight's medallion (his own helmet and blue plume, cut from the idle sprite),
the iron frames round his HP and posture bars, the blue flasks (heal charges: blue is the knight's colour and
his heal is a blue light), the Boss's frame (iron with the points of his crown at both ends, a crown over the
middle) and the two marks for the Boss's two bars. Drawn at the game's pixel size (the 960 x 540 screen),
dark-outlined like the characters; the bars' fills are drawn by the game (hud.gd) inside the frames, so the
sizes here must match hud.gd's layout (LAYOUT below is the one place they are written down)."""
import math
import os
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'sprites', 'ui')

OL = (14, 14, 17)
IRON = [(20, 21, 26), (33, 35, 42), (49, 52, 61), (70, 74, 85), (98, 103, 116), (134, 139, 150)]
GOLD = [(66, 52, 26), (104, 84, 40), (150, 122, 60), (196, 160, 74), (232, 204, 124)]
BLUE = [(14, 28, 66), (30, 62, 138), (60, 124, 222), (112, 182, 255), (186, 226, 255), (240, 250, 255)]
GLASS = [(22, 26, 34), (40, 46, 58), (66, 74, 90), (110, 120, 138)]
CORK = [(52, 36, 24), (86, 62, 40), (122, 92, 60)]
EMBER = [(70, 10, 8), (130, 24, 16), (196, 52, 30), (240, 110, 52), (255, 186, 110)]

# hud.gd draws the fills inside these (inner rects, frame-local): keep both in step
LAYOUT = {
    'hp': (180, 9),        # the knight's HP bar (inner size)
    'posture': (135, 5),
    'boss_hp': (540, 9),
    'boss_tough': (540, 4),
}
FRAME_PAD = 3              # iron round the player's bars
BOSS_PAD_X, BOSS_PAD_Y, BOSS_GAP = 5, 3, 3


class C:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        self.px = self.im.load()

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = tuple(c[:3]) + (c[3] if len(c) > 3 else 255,)

    def get(self, x, y):
        return self.px[x, y] if 0 <= x < self.w and 0 <= y < self.h else (0, 0, 0, 0)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.set(x, y, c)

    def outline(self):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[x, y][3]:
                    continue
                if any(self.get(x + dx, y + dy)[3] == 255 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    add.append((x, y))
        for x, y in add:
            self.set(x, y, OL)

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        self.im.save(os.path.join(OUT, name))


def iron_frame(c, x0, y0, x1, y1, inner):
    """An iron band from (x0, y0) to (x1, y1) (exclusive) round the hole `inner` (x, y, w, h): lit top edge,
    dark bottom, a groove next to the hole; the hole stays clear (the game draws the bar there)."""
    ix, iy, iw, ih = inner
    for y in range(y0, y1):
        for x in range(x0, x1):
            if ix <= x < ix + iw and iy <= y < iy + ih:
                continue
            t = 2
            if y == y0:
                t = 4
            elif y == y0 + 1:
                t = 3
            elif y == y1 - 1:
                t = 1
            if x == x0 or x == x1 - 1:
                t = min(t, 2)
            # the groove round the hole
            if ix - 1 <= x <= ix + iw and iy - 1 <= y <= iy + ih:
                t = 0
            c.set(x, y, IRON[t])


def rivet(c, x, y, gold=False):
    r = GOLD if gold else IRON
    c.set(x, y, r[4 if gold else 5])
    c.set(x + 1, y, r[3 if gold else 4])
    c.set(x, y + 1, r[2 if gold else 3])
    c.set(x + 1, y + 1, r[1 if gold else 2])


def player_bar_frame(name, w, h):
    p = FRAME_PAD
    c = C(w + 2 * p + 2, h + 2 * p + 2)
    iron_frame(c, 1, 1, c.w - 1, c.h - 1, (1 + p, 1 + p, w, h))
    # gold studs at the ends
    rivet(c, 2, c.h // 2 - 1, gold=True)
    rivet(c, c.w - 4, c.h // 2 - 1, gold=True)
    c.outline()
    c.save(name)
    return c


def medallion():
    """A round iron medallion with a gold ring, the knight's own helmet and blue plume inside (cut from his
    idle sprite, facing the viewer: the helmet and plume only, cut off at the neck), on a deep blue field."""
    S = 36
    c = C(S, S)
    cx = cy = (S - 1) / 2
    R = S / 2 - 1
    for y in range(S):
        for x in range(S):
            d = math.hypot(x - cx, y - cy)
            if d > R:
                continue
            if d > R - 2:
                lit = (cx - x) * 0.3 + (cy - y) * 0.7
                c.set(x, y, IRON[4 if lit > 4 else 3 if lit > -4 else 1])
            elif d > R - 3:
                c.set(x, y, GOLD[3] if (x - cx) + (y - cy) < 0 else GOLD[1])
            else:
                v = ((cx - x) * 0.4 + (cy - y) * 0.6) / R
                c.set(x, y, (24, 44, 96) if v > 0.2 else (16, 32, 74) if v > -0.3 else BLUE[0])
    # the knight's head: idle sheet, facing the viewer (row 0), first frame - the plume (rows 5-14) and the
    # helmet with its barred visor and horns (rows 15-26) of the 56 px cell, x 15-44 (the scarf starts at 27)
    sheet = Image.open(os.path.join(ROOT, 'assets', 'sprites', 'player', 'knight_idle.png')).convert('RGBA')
    head = sheet.crop((0, 0, 56, 56)).crop((15, 5, 45, 27))
    hb = head.getbbox()
    head = head.crop(hb)
    ox = int(round(cx - head.width / 2)) + 1
    oy = int(round(cy - head.height / 2)) + 2
    for y in range(head.height):
        for x in range(head.width):
            p = head.getpixel((x, y))
            if p[3] and math.hypot(ox + x - cx, oy + y - cy) <= R - 3:
                c.set(ox + x, oy + y, p)
    c.outline()
    c.save('medallion.png')
    return c


def flask(full):
    """A small round-bellied flask: cork, neck, glass; full: blue light inside with a bright core."""
    W, H = 11, 15
    c = C(W, H)
    cx = 5
    # cork and neck
    for x in range(cx - 1, cx + 2):
        c.set(x, 1, CORK[2 if x <= cx else 1])
        c.set(x, 2, CORK[1])
    for y in (3, 4):
        c.set(cx - 1, y, GLASS[2])
        c.set(cx, y, BLUE[2] if full and y == 4 else GLASS[1])
        c.set(cx + 1, y, GLASS[1])
    # belly
    by, r = 9.5, 4.6
    for y in range(5, 15):
        for x in range(0, W):
            d = math.hypot((x - cx) / r, (y - by) / (r * 0.95))
            if d > 1.0:
                continue
            if full:
                v = 1.0 - d
                level = 1 if y < 7 else 0
                t = 2 + v * 3.2 - level * 1.0 + (0.6 if x < cx else 0)
                col = BLUE[max(0, min(5, int(t)))]
            else:
                col = GLASS[0] if d < 0.8 else GLASS[1]
            c.set(x, y, col)
    # glass glint on the upper left
    c.set(cx - 2, 7, (230, 240, 255) if full else GLASS[3])
    c.set(cx - 3, 8, (200, 220, 245) if full else GLASS[2])
    c.outline()
    c.save('flask_full.png' if full else 'flask_empty.png')
    return c


def crown_points(c, x0, y_base, n, h, flip=False, gold=True):
    """Points of a crown standing on row y_base from x0 (n points, h tall)."""
    ramp = GOLD if gold else IRON
    for k in range(n):
        px = x0 + k * 4
        ph = h if k % 2 == 0 else h - 2
        for d in range(ph):
            y = y_base - d
            c.set(px, y, ramp[3 - (1 if flip else 0)])
            if d < ph - 1:
                c.set(px + 1, y, ramp[1])
        c.set(px, y_base - ph, ramp[4])


def boss_frame():
    """The Boss's frame: an iron band round both bars (HP over toughness) with a gold trim along its top and
    bottom edges and studs along it, the ends capped like his broken crown (a dark iron shield shape, three
    gold points rising from it, a dark red stone), a crown of seven points over the middle."""
    hw, hh = LAYOUT['boss_hp']
    tw, th = LAYOUT['boss_tough']
    px, py, gap = BOSS_PAD_X, BOSS_PAD_Y, BOSS_GAP
    ext = 18                                  # the caps past each end
    top = 12                                  # room above for the crown points
    W = hw + 2 * px + 2 * ext
    H = top + hh + th + gap + 2 * py + 3
    c = C(W, H)
    x0, x1 = ext, ext + hw + 2 * px
    y0, y1 = top, top + hh + th + gap + 2 * py
    hp_hole = (x0 + px, y0 + py, hw, hh)
    t_hole = (x0 + px, y0 + py + hh + gap, tw, th)
    holes = (hp_hole, t_hole)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if any(hx <= x < hx + w and hy <= y < hy + h for hx, hy, w, h in holes):
                continue
            t = 2
            if y == y0 + 1:
                t = 3
            elif y == y1 - 2:
                t = 1
            if any(hx - 1 <= x <= hx + w and hy - 1 <= y <= hy + h for hx, hy, w, h in holes):
                t = 0
            c.set(x, y, IRON[t])
    # gold trim along the top and bottom edges, a little pattern of light and dark
    for x in range(x0 + 1, x1 - 1):
        c.set(x, y0, GOLD[3] if (x // 5) % 2 else GOLD[2])
        c.set(x, y1 - 1, GOLD[1] if (x // 5) % 2 else GOLD[0])
    # studs along the band between the bars, every 60 px
    for x in range(x0 + 30, x1 - 20, 60):
        c.set(x, y0 + py + hh + 1, GOLD[3])
        c.set(x + 1, y0 + py + hh + 1, GOLD[1])
    mid = (y0 + y1) // 2
    for side in (-1, 1):
        edge = x0 if side < 0 else x1 - 1
        for d in range(1, ext):
            x = edge + side * d
            half = int(round((y1 - y0) / 2 + 2 - d * 0.6))
            if half < 1:
                break
            for y in range(mid - half, mid + half + 1):
                t = 4 if y == mid - half else 3 if y < mid - half + 3 else 1 if y > mid + half - 2 else 2
                c.set(x, y, IRON[t])
            c.set(x, mid - half - 1, GOLD[2])
        for k, (dx, ph) in enumerate(((2, 8), (6, 12), (10, 7))):
            px_ = edge + side * dx
            base = mid - int(round((y1 - y0) / 2 + 2 - dx * 0.6)) - 1
            for d in range(ph):
                c.set(px_, base - d, GOLD[3] if d < ph - 1 else GOLD[4])
                if d < ph - 3:
                    c.set(px_ + side, base - d, GOLD[1])
        gx = edge + side * 6
        for (dx, dy, col) in ((0, 0, EMBER[4]), (side, 0, EMBER[3]), (0, 1, EMBER[2]), (side, 1, EMBER[1]),
                              (0, -1, EMBER[2]), (-side, 0, EMBER[2]), (0, 2, EMBER[0])):
            c.set(gx + dx, mid + dy, col)
    # the crown over the middle: a band and seven points (the middle one tallest), a red stone
    mx = W // 2
    for x in range(mx - 13, mx + 14):
        c.set(x, y0 - 1, GOLD[2])
        c.set(x, y0 - 2, GOLD[3] if x < mx else GOLD[2])
    for k, dx in enumerate(range(-12, 13, 4)):
        ph = (4, 6, 5, 9, 5, 6, 4)[k]
        for d in range(ph):
            c.set(mx + dx, y0 - 3 - d, GOLD[3] if d < ph - 1 else GOLD[4])
            if d < ph - 2:
                c.set(mx + dx + 1, y0 - 3 - d, GOLD[1])
    for (dx, dy, col) in ((0, -2, EMBER[3]), (1, -2, EMBER[1]), (0, -3, EMBER[2])):
        c.set(mx + dx, y0 + dy, col)
    c.outline()
    c.save('boss_frame.png')
    return c, (x0 + px, y0 + py)


def boss_pip(full):
    """One of the Boss's two bars: a little ember in a crown-shaped setting (full) or a dark empty setting."""
    c = C(9, 9)
    for y in range(9):
        for x in range(9):
            d = abs(x - 4) + abs(y - 4)
            if d > 4:
                continue
            if d >= 3:
                c.set(x, y, GOLD[3] if (x < 4 or y < 4) else GOLD[1])
            else:
                if full:
                    c.set(x, y, EMBER[4] if d == 0 else EMBER[3] if d == 1 else EMBER[2])
                else:
                    c.set(x, y, IRON[0] if d < 2 else IRON[1])
    c.outline()
    c.save('boss_pip_full.png' if full else 'boss_pip_empty.png')
    return c


def export():
    out = {}
    out['medallion'] = medallion()
    out['hp'] = player_bar_frame('hp_frame.png', *LAYOUT['hp'])
    out['posture'] = player_bar_frame('posture_frame.png', *LAYOUT['posture'])
    out['flask_full'] = flask(True)
    out['flask_empty'] = flask(False)
    out['boss'], hole = boss_frame()
    out['pip_full'] = boss_pip(True)
    out['pip_empty'] = boss_pip(False)
    print('boss frame', out['boss'].w, out['boss'].h, 'hp hole at', hole)
    return out


if __name__ == '__main__':
    parts = export()
    if len(sys.argv) > 2 and sys.argv[1] == 'preview':
        bg = Image.new('RGBA', (700, 120), (40, 44, 40, 255))
        x = 8
        for k in ('medallion', 'hp', 'posture', 'flask_full', 'flask_empty', 'pip_full', 'pip_empty'):
            bg.alpha_composite(parts[k].im, (x, 8))
            x += parts[k].w + 8
        bg.alpha_composite(parts['boss'].im, (8, 60))
        bg.resize((bg.width * 3, bg.height * 3), Image.NEAREST).save(sys.argv[2])
