"""Shared pixel-art helpers for the arena (2026-10-05): palette ramps, value noise, ordered dither,
and a small RGBA canvas with pixel-level drawing. Pure Python + Pillow (no numpy), like the rigs.

The arena is drawn at the game's own pixel size (1 px = 1 px of the 960 x 540 screen), in the same
dark-outlined style as the characters; every colour comes from the ramps below (darker and less
saturated than the characters: the red Boss and the blue knight read first; red is kept for the Boss -
the banners and the blood are dark brown-reds)."""
import math
import random

from PIL import Image

# ------------------------------------------------------------------ ramps (dark -> light)
STONE = [(22, 22, 20), (32, 32, 28), (43, 43, 37), (55, 54, 46), (67, 65, 55), (80, 77, 64), (94, 90, 75), (110, 105, 87),
         (128, 121, 100)]
STONE_WARM = [(40, 37, 31), (54, 49, 40), (69, 62, 50), (86, 77, 61), (104, 93, 73), (124, 111, 87), (146, 130, 102)]
MOSS = [(20, 28, 18), (28, 39, 23), (37, 51, 28), (48, 65, 34), (61, 80, 40), (78, 96, 48), (98, 113, 58)]
GRASS = [(26, 37, 21), (37, 53, 27), (51, 71, 33), (69, 90, 40), (90, 108, 50), (114, 126, 62)]
EARTH = [(22, 18, 15), (31, 25, 19), (41, 33, 25), (53, 43, 31), (66, 53, 38), (80, 65, 46)]
BARK = [(18, 14, 11), (27, 20, 15), (38, 28, 20), (50, 37, 26), (64, 48, 33), (80, 61, 42)]
LEAF = [(7, 11, 9), (11, 18, 13), (16, 26, 17), (22, 35, 21), (30, 46, 27), (41, 60, 33)]
LEAF_LIT = [(46, 66, 34), (62, 84, 40), (84, 104, 48), (110, 126, 60)]
BLOOD = [(34, 13, 11), (47, 18, 14), (60, 23, 18), (72, 30, 22)]
WATER = [(26, 32, 35), (35, 44, 48), (48, 60, 64), (66, 80, 83), (96, 109, 108), (132, 140, 132)]
BANNER = [(30, 10, 10), (46, 15, 14), (63, 21, 19), (80, 28, 24), (98, 37, 30)]
GOLD = [(70, 57, 30), (96, 79, 40), (124, 103, 52), (152, 128, 66)]
ASH = [(26, 25, 24), (36, 34, 32), (48, 46, 43), (61, 58, 54), (76, 72, 67), (92, 88, 82)]
CHAR = [(14, 12, 11), (22, 19, 17), (31, 27, 24)]
EMBER = [(120, 38, 16), (178, 64, 22), (232, 112, 36), (255, 170, 72), (255, 214, 140)]
STEEL = [(30, 31, 34), (48, 50, 54), (70, 72, 76), (98, 100, 104), (130, 132, 134)]
VINE = [(20, 32, 18), (30, 46, 24), (42, 62, 30), (56, 80, 36), (74, 98, 44)]
OUTLINE = (16, 16, 14)
# 2026-10-06 (more material on the court and round it, the user: no corner leaves, and the screen must not
# go plain): cooler and sandier paving stones mixed in, bone, wild flowers, mushrooms, the braziers' iron
STONE_COOL = [(24, 25, 27), (34, 36, 38), (45, 48, 50), (57, 60, 62), (70, 73, 74), (84, 87, 87), (99, 102, 101),
              (116, 118, 115), (134, 135, 130)]
SAND = [(46, 41, 32), (60, 53, 41), (76, 67, 52), (94, 83, 64), (113, 100, 77), (133, 118, 91), (155, 138, 107)]
BONE = [(62, 58, 49), (96, 90, 77), (132, 124, 106), (168, 160, 138)]
FLOWERS = [(196, 192, 168), (204, 178, 96), (150, 138, 176), (188, 150, 120)]
MUSH = [(64, 48, 36), (112, 88, 64), (160, 138, 104), (196, 180, 146)]
IRON = [(18, 18, 20), (30, 30, 33), (44, 44, 48), (62, 62, 66), (86, 84, 86)]

SUN_DIR = (-0.62, 0.78)          # light from the upper right, falling toward the lower left (screen)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


# ------------------------------------------------------------------ noise
def _h(x, y, seed):
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def hash01(*args):
    n = 2166136261
    for a in args:
        n = ((n ^ (int(a) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    n ^= n >> 15
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 13
    return (n & 0xFFFFFF) / float(0xFFFFFF)


def value_noise(x, y, scale, seed=0):
    """Smooth value noise 0..1 (bilinear with smoothstep) at feature size `scale` px."""
    fx, fy = x / scale, y / scale
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a, b = _h(ix, iy, seed), _h(ix + 1, iy, seed)
    c, d = _h(ix, iy + 1, seed), _h(ix + 1, iy + 1, seed)
    return lerp(lerp(a, b, tx), lerp(c, d, tx), ty)


def fbm(x, y, scale, seed=0, octaves=3):
    v, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        v += amp * value_noise(x, y, scale / (2 ** o), seed + o * 101)
        tot += amp
        amp *= 0.5
    return v / tot


BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def dither(v, x, y):
    """Continuous ramp position v -> an integer index, ordered 4x4 dither between neighbours."""
    base = math.floor(v)
    frac = v - base
    return base + (1 if frac > (BAYER4[y & 3][x & 3] + 0.5) / 16.0 else 0)


def ramp(r, v, x=0, y=0, dith=True):
    """A ramp colour for position v; dith: ordered (Bayer) between neighbours, 'grain': a hashed
    threshold (no regular pattern over big flat areas), False: nearest."""
    if dith == 'grain':
        base = math.floor(v)
        i = base + (1 if v - base > hash01(x, y, 4242) else 0)
    elif dith:
        i = dither(v, x, y)
    else:
        i = int(round(v))
    return r[clamp(i, 0, len(r) - 1)]


# ------------------------------------------------------------------ canvas
class Canvas:
    """RGBA pixels in a dict-free flat list for speed; (0, 0) top-left."""

    def __init__(self, w, h, fill=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new('RGBA', (w, h), fill)
        self.px = self.im.load()

    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        return self.px[x, y] if self.inside(x, y) else (0, 0, 0, 0)

    def set(self, x, y, c, a=255):
        if not self.inside(x, y):
            return
        if len(c) == 4:
            c, a = c[:3], c[3]
        if a >= 255:
            self.px[x, y] = (c[0], c[1], c[2], 255)
        elif a > 0:
            old = self.px[x, y]
            t = a / 255.0
            if old[3] == 0:
                self.px[x, y] = (c[0], c[1], c[2], a)
            else:
                self.px[x, y] = (int(lerp(old[0], c[0], t)), int(lerp(old[1], c[1], t)), int(lerp(old[2], c[2], t)),
                                 max(old[3], a))

    def opaque(self, x, y):
        return self.inside(x, y) and self.px[x, y][3] > 0

    def outline(self, color=OUTLINE, only_new=True):
        """A 1 px dark outline round every opaque pixel (4-neighbourhood), like the characters."""
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[x, y][3]:
                    continue
                if any(self.opaque(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    add.append((x, y))
        for x, y in add:
            self.px[x, y] = color + (255,)

    def bbox(self):
        return self.im.getbbox()

    def save(self, path):
        self.im.save(path)


def line(x0, y0, x1, y1):
    """Pixel line without L corners."""
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    pts = [(x0, y0)]
    while (x0, y0) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
        pts.append((x0, y0))
    return pts


def poly_fill(points):
    """Pixels inside a polygon (even-odd, pixel centres)."""
    ys = [p[1] for p in points]
    out = []
    for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
        yc = y + 0.5
        xs = []
        n = len(points)
        for i in range(n):
            (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            for x in range(int(math.ceil(a - 0.5)), int(math.floor(b - 0.5)) + 1):
                out.append((x, y))
    return out


def blob(cx, cy, rx, ry, seed, rough=0.35, n=24):
    """An irregular closed shape (polygon points) around (cx, cy)."""
    rnd = random.Random(seed)
    pts = []
    phase = rnd.random() * 6.28
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1.0 + rough * (0.6 * math.sin(3 * a + phase) + 0.4 * (rnd.random() * 2 - 1))
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return pts
