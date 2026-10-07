"""The arena's floor (2026-10-05): one picture under everything (arena.md §3 "地面", no sorting).

The fight is on a round paved court seen at the game's angle: the court is the collision ellipse itself
(ArenaGeometry.HALF_SIZE 540 x 300, centred on the origin) - its rim is a ring of big curb stones laid
right on that edge, so what the eye reads as the edge is where the characters stop. Inside: rings of paving
stones (worn and lighter toward the middle, mossy toward the rim), a low round dais in the middle with the
heap of ash that was the throne ("A throne of ash", arena.md §1) and a few live embers, dried blood (dark
brown-red: red is the Boss's), a few puddles, dappled sunlight from the upper right. Outside: the paving
breaks up into earth, moss, roots and leaf litter; behind the north ruins, dark forest.

The picture covers the world from (X0, Y0), W x H px: everything the camera can show (x -600..600,
y -440..375) plus the shake and a margin."""
import math
import random

import pix as P

X0, Y0 = -800, -580
W, H = 1600, 1140
HX, HY = 540.0, 300.0                  # ArenaGeometry.HALF_SIZE (the collision ellipse)
R_DAIS = 0.165                         # the dais (r in the ellipse's own measure: 1 = the court's edge)
R_RIM_IN, R_RIM_OUT = 0.985, 1.035     # the curb ring, laid on the collision edge
DR = 0.0435                            # paving ring width (13 px at the north and south, 23 at the sides)
TILE_LEN = 30.0                        # paving stone length along its ring (px of the true circle)
BACKDROP_Y = -332                      # north of this the forest stands behind the ruins

BLOOD_AT = [(-185, 92, 16, 6), (230, -108, 12, 5), (96, 186, 9, 4), (-310, -66, 13, 5), (330, 40, 8, 3)]
PUDDLE_AT = [(268, 124, 26, 8), (-140, -196, 19, 6), (-372, 48, 15, 5)]

# 2026-10-06 (the corner leaves are gone; the court itself carries the scene now - the user: "不能讓畫面變單調，
# 你可以自己加料"):
R_SUN = 0.235                          # a ring of wedge stones round the dais: the kingdom's sun, inlaid
SUN_WEDGES = 24
PATH_HW, KERB = 30, 5                  # the royal way: big slabs from the arch (north) through the dais to the south
PATH_ROW, PATH_SLAB = 13, 20
# battle scars: (x, y, rx, ry) where something heavy struck - shattered stones, cracks running out
CRATERS = [(-236, -18, 17, 8), (262, 84, 14, 7), (118, -232, 12, 6)]
# the fallen: small things lying on the court and round it (kind, x, y, seed)
REMAINS = [('shield', -402, 112, 1), ('helmet', 371, -70, 2), ('bones', -96, 236, 3), ('spear', 196, 214, 4),
           ('shield', 452, 150, 5), ('bones', -478, -128, 6), ('helmet', -170, -262, 7), ('spear', -330, 205, 8),
           ('bones', 300, -232, 9), ('shield', -560, 210, 10), ('helmet', 590, 40, 11), ('skull', 520, -190, 12),
           ('skull', -150, 300, 13), ('spear', 470, 262, 14)]


def ell(wx, wy):
    u, v = wx / HX, wy / HY
    return math.sqrt(u * u + v * v), math.atan2(v, u)


def ring_count(k):
    r_mid = R_DAIS + (k + 0.5) * DR
    return max(10, int(round(2 * math.pi * HX * r_mid / TILE_LEN)))


def tile_of(wx, wy):
    """(ring, segment) of the paving stone under a world point, or None off the paving."""
    r, a = ell(wx, wy)
    if r < R_DAIS or r >= R_RIM_IN:
        if R_RIM_OUT <= r < 1.32:
            # the broken paving beyond the curb (the same rings carried on)
            pass
        else:
            return None
    k = int((r - R_DAIS) / DR)
    n = ring_count(k)
    off = P.hash01(k, 77)
    seg = int(math.floor((a / (2 * math.pi) + 0.5) * n + off)) % n
    return k, seg


def curb_of(wx, wy):
    r, a = ell(wx, wy)
    if not (R_RIM_IN <= r < R_RIM_OUT):
        return None
    n = int(2 * math.pi * HX / 46)
    return int(math.floor((a / (2 * math.pi) + 0.5) * n)) % n


def dais_of(wx, wy):
    """Dais parts: 'rim' slabs, 'groove', 'disk' slabs, 'ash'; with a slab id."""
    r, a = ell(wx, wy)
    if r >= R_DAIS:
        return None
    if r >= 0.135:
        return ('rim', int(math.floor((a / (2 * math.pi) + 0.5) * 14)) % 14)
    if r >= 0.118:
        return ('groove', 0)
    if r >= 0.072:
        return ('disk', int(math.floor((a / (2 * math.pi) + 0.5) * 9 + 0.5)) % 9)
    return ('ash', 0)


def sun_of(wx, wy):
    """The wedge stone of the sun ring round the dais."""
    _, a = ell(wx, wy)
    return int(math.floor((a / (2 * math.pi) + 0.5) * SUN_WEDGES)) % SUN_WEDGES


def path_of(wx, wy):
    """The royal way (north-south through the dais): ('p', row, slab) slabs, ('k', side, n) the kerb."""
    ax = abs(wx)
    if ax >= PATH_HW + KERB:
        return None
    if ax >= PATH_HW:
        return ('k', 1 if wx > 0 else -1, int((wy + 2000) // 22))
    row = int((wy + 2000) // PATH_ROW)
    return ('p', row, int((wx + PATH_HW + (row % 2) * PATH_SLAB // 2) // PATH_SLAB))


def scorch(wx, wy):
    """Soot from the throne's fire: rays of blackened stone running out from the dais, 0..1."""
    r, a = ell(wx, wy)
    if r > 0.5:
        return 0.0
    u = (a / (2 * math.pi) + 0.5) * 40
    reach = 0.05 + 0.24 * P.value_noise(u, 0.5, 1.0, 61) ** 2 + 0.05 * P.value_noise(u, 3.5, 0.33, 62)
    t = (R_DAIS + reach - r) / reach
    if t <= 0:
        return 0.0
    return P.clamp(t, 0.0, 1.0) ** 0.8 * (0.75 + 0.5 * (P.value_noise(wx, wy, 5, 63) - 0.5))


def stone_ramp(tid):
    """Every paving stone its own stone: mostly grey, some sandstone, some cooler grey."""
    h = P.hash01(*[hash(x) & 0xFFFF for x in tid], 55)
    if h < 0.13:
        return P.SAND
    if h < 0.18:
        return P.STONE_COOL
    return P.STONE


def overgrowth(wx, wy, r, shade):
    """Where the forest has taken the paving back: big soft patches, toward the rim and in shade; the
    middle of the court (where the fight is) stays clear. > 0.8: no stone left."""
    if r < 0.42:
        return 0.0
    n = P.fbm(wx, wy, 95, 7, 3)
    return n + (r - 0.62) * 0.95 + shade * 0.22


def sunlit(tone, lit, x, y, base=P.STONE):
    """Stone in the sun turns warm (the light is late-afternoon gold); in shade its own colour."""
    if lit > 0.05 and P.hash01(x, y, 515) < lit:
        return P.ramp(P.STONE_WARM, tone - 1.4, x, y, 'grain')
    return P.ramp(base, tone, x, y, 'grain')


def lit_field(wx, wy):
    """Dappled sunlight through the canopy: patches stretched along the light, 0..1."""
    s = wx * 0.78 - wy * 0.62
    t = wx * 0.62 + wy * 0.78
    v = P.fbm(s * 0.75, t * 1.05, 85, seed=11, octaves=3)
    return P.clamp((v - 0.55) * 6.0, 0.0, 1.0)


def shade_field(wx, wy):
    """Shadow of the north ruins and trees, and of the canopy at the corners, 0..1."""
    north = P.clamp((-wy - 150) / 220.0, 0.0, 1.0)
    corner = P.clamp((abs(wx) - 420) / 240.0, 0.0, 1.0) * P.clamp((abs(wy) - 120) / 200.0, 0.0, 1.0)
    canopy = P.fbm(wx, wy, 140, seed=5, octaves=2)
    return P.clamp(0.55 * north + 0.6 * corner + 0.25 * (canopy - 0.5), 0.0, 1.0)


class Ground:
    def __init__(self, seed=3, cast=None):
        self.c = P.Canvas(W, H, (0, 0, 0, 255))
        self.seed = seed
        self.rnd = random.Random(seed)
        # the long shadows the north ruins and trees throw over the court (late sun from the upper right;
        # arena.cast_shadows): an 'L' picture the floor's size, 255 = full shadow
        self.cast = cast.load() if cast is not None else None

    def cast_at(self, ix, iy):
        return self.cast[ix, iy] / 255.0 if self.cast is not None else 0.0

    # -------------------------------------------------------------- ids
    def build_ids(self):
        """Every pixel's part: ('t', k, seg) paving, ('c', n) curb, ('d', part, id) dais, None ground."""
        self.ids = [[None] * W for _ in range(H)]
        for iy in range(H):
            wy = iy + Y0
            row = self.ids[iy]
            for ix in range(W):
                wx = ix + X0
                r, _ = ell(wx, wy)
                if r > 1.34:
                    continue
                d = dais_of(wx, wy)
                if d:
                    row[ix] = ('d',) + d
                    continue
                if r < R_SUN:
                    row[ix] = ('s', sun_of(wx, wy))
                    continue
                c = curb_of(wx, wy)
                if c is not None:
                    row[ix] = ('c', c)
                    continue
                if r < R_RIM_IN:
                    p = path_of(wx, wy)
                    if p:
                        row[ix] = p
                        continue
                t = tile_of(wx, wy)
                if t:
                    k, seg = t
                    if r >= R_RIM_OUT:
                        # beyond the curb the paving breaks up: fewer stones the further out
                        keep = (1.32 - r) / (1.32 - R_RIM_OUT)
                        if P.hash01(k, seg, 5) > keep ** 1.3 * 0.9 or P.fbm(wx, wy, 60, 9) < 0.38:
                            continue
                    row[ix] = ('t', k, seg)

    def seam(self, ix, iy):
        """A pixel on the border of its stone: its right or lower neighbour belongs to another stone."""
        a = self.ids[iy][ix]
        if a is None:
            return False
        for dx, dy in ((1, 0), (0, 1)):
            x, y = ix + dx, iy + dy
            if 0 <= x < W and 0 <= y < H and self.ids[y][x] != a:
                return True
        return False

    # -------------------------------------------------------------- painting
    def paint(self):
        self.build_ids()
        c = self.c
        for iy in range(H):
            wy = iy + Y0
            for ix in range(W):
                wx = ix + X0
                c.px[ix, iy] = self.pixel(ix, iy, wx, wy) + (255,)
        self.cracks()
        self.decals()
        self.scars()
        self.roots()
        self.tufts()
        self.chips()
        self.remains()
        self.flowers()
        self.mushrooms()
        self.leaves()

    def stone_pixel(self, ix, iy, wx, wy, tid, base):
        """A pixel of a stone: its tone, bevel (lit top and right edges, dark bottom and left), grain."""
        r, _ = ell(wx, wy)
        h = P.hash01(*[hash(x) & 0xFFFF for x in tid])
        tone = base + (h - 0.5) * 1.4
        # grain and wear
        tone += (P.value_noise(wx, wy, 2.5, 21) - 0.5) * 0.7 + (P.value_noise(wx, wy, 9.0, 23) - 0.5) * 0.5
        # bevel: neighbours above / right belong to another stone -> this is a lit edge
        ids = self.ids
        up = iy > 0 and ids[iy - 1][ix] != tid
        right = ix < W - 1 and ids[iy][ix + 1] != tid
        down = iy < H - 1 and ids[iy + 1][ix] != tid
        left = ix > 0 and ids[iy][ix - 1] != tid
        if up:
            tone += 0.95
        elif right:
            tone += 0.5
        if down:
            tone -= 1.6
        elif left:
            tone -= 0.6
        return tone, h

    def pixel(self, ix, iy, wx, wy):
        tid = self.ids[iy][ix]
        r, a = ell(wx, wy)
        cs = self.cast_at(ix, iy)
        lit = lit_field(wx, wy) * (1.0 - cs)
        shade = P.clamp(shade_field(wx, wy) + cs * 0.7, 0.0, 1.0)
        moss_f = P.fbm(wx, wy, 70, seed=13, octaves=3)
        if tid is None:
            return self.earth(ix, iy, wx, wy, r, lit, shade, moss_f)
        kind = tid[0]
        if kind == 't':
            if self.seam(ix, iy):
                # the joint: dark, often green
                if moss_f + (r - 0.4) * 0.35 > 0.52 and P.hash01(ix, iy, 4) < 0.7:
                    return P.ramp(P.MOSS, 1.2 + lit * 1.2 - shade, ix, iy)
                return P.STONE[1] if shade < 0.5 else P.STONE[0]
            k, seg = tid[1], tid[2]
            og = overgrowth(wx, wy, r, shade)
            if og > 0.8:
                return self.earth(ix, iy, wx, wy, r, lit, shade, moss_f, hole=False, overgrown=True)
            missing = r < R_RIM_IN and r > 0.3 and P.hash01(k, seg, 31) < 0.003 + max(0.0, og - 0.6) * 0.3
            if missing:
                return self.earth(ix, iy, wx, wy, r, lit, shade, moss_f, hole=True)
            wear = P.clamp(1.0 - r, 0.0, 1.0) * 0.9
            age = (P.fbm(wx, wy, 120, 29, 2) - 0.5) * 1.6       # whole stretches older / newer
            base = 3.8 + wear + age + lit * 2.0 - shade * 2.2 - (0.9 if r >= R_RIM_OUT else 0.0)
            tone, h = self.stone_pixel(ix, iy, wx, wy, tid, base)
            sc = scorch(wx, wy)
            if sc > 0:
                tone -= sc * 2.4
                if sc > 0.3 and P.hash01(ix, iy, 64) < (sc - 0.3) * 0.9:
                    return P.ramp(P.ASH, 0.6 + (tone - 2.0) * 0.5, ix, iy, 'grain')
            # moss creeping over the outer stones and those in shade, thick round the overgrown patches
            m = moss_f + (r - 0.6) * 0.5 + shade * 0.25 - lit * 0.15 + max(0.0, og - 0.6) * 1.2 - sc
            if m > 0.62 and P.hash01(ix, iy, 8) < (m - 0.62) * 4.0:
                return P.ramp(P.MOSS, 2.2 + lit * 1.8 - shade + (tone - 4.0) * 0.3, ix, iy, 'grain')
            sr = stone_ramp(tid)
            return sunlit(tone - (0.7 if sr is P.SAND else 0.2 if sr is P.STONE_COOL else 0.0), lit, ix, iy, sr)
        if kind == 'p' or kind == 'k':
            # the royal way: big worn slabs (sandstone, smoother - centuries of feet), a dark kerb either side
            if self.seam(ix, iy):
                if r > 0.45 and moss_f + (r - 0.4) * 0.35 > 0.5 and P.hash01(ix, iy, 4) < 0.6:
                    return P.ramp(P.MOSS, 1.2 + lit * 1.2 - shade, ix, iy)
                return P.STONE[1] if kind == 'p' else P.STONE[0]
            og = overgrowth(wx, wy, r, shade) - 0.25
            if og > 0.8:
                return self.earth(ix, iy, wx, wy, r, lit, shade, moss_f, hole=False, overgrown=True)
            sc = scorch(wx, wy)
            if kind == 'k':
                tone, h = self.stone_pixel(ix, iy, wx, wy, tid, 3.3 + lit * 1.4 - shade * 1.8 - sc * 1.5)
                return P.ramp(P.STONE_COOL, tone, ix, iy, 'grain')
            age = (P.fbm(wx, wy, 120, 29, 2) - 0.5) * 1.0
            tone, h = self.stone_pixel(ix, iy, wx, wy, tid, 3.7 + age + lit * 1.8 - shade * 2.0 - sc * 2.0)
            m = moss_f + (r - 0.7) * 0.6 + shade * 0.25 - lit * 0.2 - sc
            if m > 0.66 and P.hash01(ix, iy, 8) < (m - 0.66) * 3.0:
                return P.ramp(P.MOSS, 2.2 + lit * 1.8 - shade, ix, iy, 'grain')
            return sunlit(tone, lit, ix, iy, P.SAND if P.hash01(tid[1], tid[2], 56) < 0.7 else P.STONE)
        if kind == 's':
            # the sun ring: wedges of pale sandstone and dark stone, blackened by the fire next to it
            if self.seam(ix, iy):
                return P.STONE[0]
            sc = scorch(wx, wy)
            light = tid[1] % 2 == 0
            tone, h = self.stone_pixel(ix, iy, wx, wy, tid, (3.8 if light else 3.3) + lit * 1.2 - shade * 1.5 - sc * 1.3)
            if sc > 0.5 and P.hash01(ix, iy, 65) < (sc - 0.5) * 0.7:
                return P.ramp(P.ASH, 1.0 + (tone - 2.0) * 0.4, ix, iy, 'grain')
            return P.ramp(P.SAND if light else P.STONE, tone, ix, iy, 'grain')
        if kind == 'c':
            # the curb: bigger, darker stones; their outer face shows on the south half
            tone, h = self.stone_pixel(ix, iy, wx, wy, tid, 3.6 + lit * 1.2 - shade * 1.8)
            if self.seam(ix, iy):
                return P.STONE[0]
            m = moss_f + shade * 0.3
            if m > 0.6 and P.hash01(ix, iy, 18) < (m - 0.6) * 3.0:
                return P.ramp(P.MOSS, 2.0 + lit, ix, iy, 'grain')
            return P.ramp(P.STONE, tone, ix, iy, 'grain')
        # the dais
        part = tid[1]
        if part == 'ash':
            return self.ash(ix, iy, wx, wy, r)
        if part == 'groove':
            # an engraved ring with a band of worn runes
            rr = (r - 0.118) / (0.135 - 0.118)
            ang = (a / (2 * math.pi) + 0.5) * 96
            rune = (int(ang) % 3 == 0 and 0.25 < rr < 0.75 and P.hash01(int(ang), 3) < 0.7)
            if rr < 0.2 or rr > 0.8:
                return P.STONE[1]
            return P.ramp(P.STONE, 2.2 if rune else 3.4 + lit, ix, iy)
        if self.seam(ix, iy):
            return P.STONE[1]
        warm = P.STONE_WARM if part == 'rim' else P.STONE
        base = (3.2 if part == 'rim' else 4.6) + lit * 1.0 - (P.clamp(0.13 - r, 0, 1) * 18 if part == 'disk' else 0)
        tone, h = self.stone_pixel(ix, iy, wx, wy, tid, base)
        # scorch: the stones round the ash are blackened
        burn = P.clamp((0.12 - r) / 0.05, 0.0, 1.0) * (0.6 + 0.4 * P.value_noise(wx, wy, 6, 41))
        if part == 'disk' and burn > 0.5 and P.hash01(ix, iy, 61) < burn:
            return P.ramp(P.ASH, 1.5 + (tone - 4) * 0.4, ix, iy)
        return P.ramp(warm, tone - (0.0 if part == 'rim' else 0.6), ix, iy, 'grain')

    def earth(self, ix, iy, wx, wy, r, lit, shade, moss_f, hole=False, overgrown=False):
        if wy < BACKDROP_Y and not hole:
            return self.backdrop(ix, iy, wx, wy)
        if hole:
            # a lifted stone's hole: the upper edge in the stones' shadow, a lit lower lip, grass grown in it
            tid_up = self.ids[iy - 2][ix] if iy >= 2 else None
            tid_dn = self.ids[iy + 1][ix] if iy + 1 < H else None
            cur = self.ids[iy][ix]
            if tid_up != cur:
                return P.EARTH[0]
            if tid_dn != cur:
                return P.STONE[3]
            g = P.value_noise(wx * 2.0, wy * 0.5, 1.5, 19)
            if g > 0.45:
                return P.ramp(P.GRASS, 1.4 + g * 2.0 + lit * 1.2, ix, iy, 'grain')
            return P.ramp(P.EARTH, 1.4 + (P.value_noise(wx, wy, 3, 19) - 0.5) * 1.5, ix, iy, 'grain')
        # the forest floor: grass in blades, moss cushions, bare earth and leaf litter in small worn patches;
        # darker the further out (the canopy closes over)
        far = 0.0 if overgrown else P.clamp((r - 1.05) / 0.5, 0.0, 1.0)
        blades = P.value_noise(wx * 2.4, wy * 0.42, 1.7, 87)
        n = P.fbm(wx, wy, 30, 37, 3)
        bare = P.fbm(wx, wy, 18, 91, 2) - (0.04 if overgrown else 0.0)
        hsh = P.hash01(ix, iy, 99)
        if bare > 0.7:
            # bare earth under fallen leaves (gold, brown, a dark red-brown)
            if hsh < 0.22 + (bare - 0.7) * 2.0:
                leaf = (P.GOLD[1], P.GOLD[0], P.EARTH[4], P.BANNER[2], P.EARTH[5])[int(P.hash01(ix, iy, 98) * 5)]
                return P.mix(leaf, (0, 0, 0), 0.15 + far * 0.35 + shade * 0.2)
            tone = 2.3 + (P.value_noise(wx, wy, 4, 17) - 0.5) * 1.6 + lit * 1.2 - shade * 1.2 - far * 1.4
            return P.ramp(P.EARTH, tone, ix, iy, 'grain')
        if moss_f > 0.6:
            tone = 2.0 + (moss_f - 0.6) * 6 + lit * 1.4 - shade * 1.2 - far * 1.3
            return P.ramp(P.MOSS, tone, ix, iy, 'grain')
        if hsh < 0.008:
            return P.ramp(P.STONE, 3 + lit * 2 - far, ix, iy)
        tone = 1.7 + n * 1.5 + (blades - 0.5) * 1.8 + lit * 1.7 - shade * 1.2 - far * 1.5 + (0.3 if overgrown else 0.0)
        return P.ramp(P.GRASS, tone, ix, iy, 'grain')

    def ash(self, ix, iy, wx, wy, r):
        """The heap of ash where the throne burned: grey ash, charred bits, a few embers still alive."""
        n = P.fbm(wx, wy, 7, 51, 3)
        heap = (0.072 - r) / 0.072            # 0 at the edge .. 1 at the middle
        tone = 1.2 + heap * 2.4 + (n - 0.5) * 2.4
        if P.hash01(ix, iy, 71) < 0.06 + heap * 0.05:
            return P.CHAR[int(P.hash01(ix, iy, 72) * 3)]
        if P.hash01(ix, iy, 73) < 0.008 + heap * 0.012:
            return P.EMBER[2 if P.hash01(ix, iy, 74) < 0.5 else 1]
        return P.ramp(P.ASH, tone, ix, iy, 'grain')

    def backdrop(self, ix, iy, wx, wy):
        """North of the court, behind the ruins: undergrowth going into a dark forest of trunks."""
        depth = P.clamp((BACKDROP_Y - wy) / 120.0, 0.0, 1.0)
        n = P.fbm(wx, wy, 22, 81, 3)
        # far trunks: vertical dark columns, faintly lit on their right
        tx = (wx + 900) % 61
        tw = 8 + P.hash01(int((wx + 900) // 61), 5) * 10
        if depth > 0.35 and tx < tw:
            u = tx / tw
            return P.ramp(P.BARK, 0.6 + u * 1.4 - depth * 0.6 + (P.value_noise(wx, wy, 5, 3) - 0.5), ix, iy, 'grain')
        tone = 3.2 - depth * 2.6 + (n - 0.5) * 2.4
        if n > 0.5 or depth > 0.5:
            return P.ramp(P.LEAF, tone + 0.8, ix, iy, 'grain')
        return P.ramp(P.MOSS, tone - 0.4, ix, iy, 'grain')

    def cracks(self):
        """A few stones split by a hairline crack: a short wandering dark line with a lit edge under it."""
        c = self.c
        tiles = {}
        for iy in range(0, H):
            row = self.ids[iy]
            for ix in range(W):
                t = row[ix]
                if t is not None and t[0] == 't':
                    tiles.setdefault(t, []).append((ix, iy))
        for t, pts in tiles.items():
            if P.hash01(t[1], t[2], 91) > 0.08 or len(pts) < 40:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            own = set(pts)
            rnd = random.Random(t[1] * 1000 + t[2])
            x, y = rnd.randint(min(xs) + 2, max(xs) - 2), rnd.randint(min(ys) + 1, max(ys) - 1)
            dx = rnd.choice((-1, 1))
            for _ in range(rnd.randint(5, 11)):
                if (x, y) not in own or (x, y + 1) not in own:
                    break
                c.px[x, y] = P.STONE[1] + (255,)
                if (x, y + 1) in own and rnd.random() < 0.5:
                    c.px[x, y + 1] = P.STONE[5] + (255,)
                x += dx
                if rnd.random() < 0.45:
                    y += rnd.choice((-1, 1))

    # -------------------------------------------------------------- decals
    def to_px(self, wx, wy):
        return int(round(wx - X0)), int(round(wy - Y0))

    def decals(self):
        c = self.c
        for i, (bx, by, rx, ry) in enumerate(BLOOD_AT):
            pts = P.blob(bx - X0, by - Y0, rx, ry, seed=100 + i, rough=0.45)
            for (x, y) in P.poly_fill(pts):
                old = c.px[x, y]
                v = P.value_noise(x, y, 3, 200 + i)
                col = P.BLOOD[1 if v < 0.6 else 2]
                c.px[x, y] = P.mix(old[:3], col, 0.82) + (255,)
            rnd = random.Random(300 + i)
            for _ in range(int(rx * 0.8)):
                a = rnd.random() * 6.28
                d = rx * (1.1 + rnd.random() * 0.9)
                x, y = int(bx - X0 + math.cos(a) * d), int(by - Y0 + math.sin(a) * d * ry / rx)
                c.px[x, y] = P.BLOOD[1] + (255,)
                if rnd.random() < 0.4:
                    c.px[x + 1, y] = P.BLOOD[0] + (255,)
        for i, (wx, wy, rx, ry) in enumerate(PUDDLE_AT):
            pts = P.blob(wx - X0, wy - Y0, rx, ry, seed=400 + i, rough=0.3)
            inside = set(P.poly_fill(pts))
            for (x, y) in inside:
                edge = any((x + dx, y + dy) not in inside for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if edge:
                    c.px[x, y] = P.WATER[0] + (255,)
                    continue
                # the sky (light from the upper right) reflected toward the top right of the pool
                u = ((x - (wx - X0)) / rx) * 0.62 - ((y - (wy - Y0)) / ry) * 0.78
                tone = 1.6 + u * 1.6 + (P.value_noise(x, y, 4, 500 + i) - 0.5)
                c.px[x, y] = P.ramp(P.WATER, tone, x, y) + (255,)
            # a glint
            gx, gy = int(wx - X0 + rx * 0.35), int(wy - Y0 - ry * 0.3)
            for k in range(3):
                if (gx + k, gy) in inside:
                    c.px[gx + k, gy] = P.WATER[5] + (255,)

    # -------------------------------------------------------------- 2026-10-06: what the fights left
    def put(self, x, y, col):
        if 0 <= x < W and 0 <= y < H:
            self.c.px[x, y] = col[:3] + (255,)

    def scars(self):
        """Sword gouges in the paving (a dark groove with a lit lip under it) and the places where something
        heavy struck: shattered stones, cracks running out (CRATERS)."""
        rnd = random.Random(self.seed + 51)
        n = 0
        while n < 16:
            wx, wy = rnd.uniform(-480, 480), rnd.uniform(-270, 270)
            r, _ = ell(wx, wy)
            if not (0.28 < r < 0.9):
                continue
            n += 1
            ang = rnd.uniform(-0.5, 0.5) + (math.pi if rnd.random() < 0.5 else 0.0)
            ln = rnd.randint(9, 20)
            bend = rnd.uniform(-0.04, 0.04)
            x, y = wx - X0, wy - Y0
            for k in range(ln):
                ang += bend
                x += math.cos(ang)
                y += math.sin(ang) * 0.55
                if k in (0, ln - 1) and rnd.random() < 0.5:
                    continue
                xi, yi = int(round(x)), int(round(y))
                self.put(xi, yi, P.STONE[0])
                if 2 < k < ln - 3:
                    self.put(xi, yi + 1, P.STONE[6])
        for i, (cx, cy, rx, ry) in enumerate(CRATERS):
            # the paving shattered into shards (each its own tone, lit upper edge, dark gaps), the middle sunk
            # a little; a few cracks run out into the whole stones round it
            rnd = random.Random(700 + i)
            ox, oy = cx - X0, cy - Y0
            seeds = [(ox + rnd.uniform(-rx, rx), oy + rnd.uniform(-ry, ry)) for _ in range(int(rx * 0.8))]
            area = set(P.poly_fill(P.blob(ox, oy, rx, ry, seed=710 + i, rough=0.3)))
            owner = {}
            for (x, y) in area:
                owner[(x, y)] = min(range(len(seeds)), key=lambda q: (x - seeds[q][0]) ** 2 + ((y - seeds[q][1]) * 1.8) ** 2)
            tones = [rnd.uniform(2.6, 4.6) for _ in seeds]
            gone = {q for q in range(len(seeds)) if rnd.random() < 0.18}
            for (x, y), q in owner.items():
                sink = 1.0 - ((x - ox) / rx) ** 2 - ((y - oy) / ry) ** 2
                if owner.get((x + 1, y), q) != q or owner.get((x, y + 1), q) != q:
                    self.put(x, y, P.STONE[0])
                elif q in gone:
                    self.put(x, y, P.ramp(P.EARTH, 1.2 + P.value_noise(x, y, 2, 730) * 1.4, x, y, 'grain'))
                elif owner.get((x, y - 1), -1) != q:
                    self.put(x, y, P.ramp(P.STONE, tones[q] + 1.6 - sink, x, y))
                else:
                    self.put(x, y, P.ramp(P.STONE, tones[q] - sink * 1.2, x, y, 'grain'))
            for k in range(rnd.randint(5, 7)):
                a = 2 * math.pi * k / 6 + rnd.uniform(-0.4, 0.4)
                x, y = ox + math.cos(a) * rx, oy + math.sin(a) * ry
                for step in range(rnd.randint(int(rx * 0.5), int(rx * 1.1))):
                    a += rnd.uniform(-0.35, 0.35)
                    x += math.cos(a)
                    y += math.sin(a) * 0.55
                    self.put(int(round(x)), int(round(y)), P.STONE[1])
                    if rnd.random() < 0.4:
                        self.put(int(round(x)), int(round(y)) + 1, P.STONE[5])

    def chips(self):
        """Loose chips of stone lying about: none in the middle, more toward the rim and outside."""
        rnd = random.Random(self.seed + 61)
        for _ in range(2600):
            wx, wy = rnd.uniform(-660, 660), rnd.uniform(-330, 420)
            r, _ = ell(wx, wy)
            if r < 0.35 or rnd.random() > (r - 0.35) * 0.55:
                continue
            x, y = int(wx - X0), int(wy - Y0)
            w = rnd.randint(1, 3)
            tone = 4.2 + rnd.random() * 1.5 - (0.8 if r > 1.05 else 0.0)
            for dx in range(w):
                self.put(x + dx, y, P.ramp(P.STONE, tone + 1.0, x + dx, y))
                self.put(x + dx, y + 1, P.STONE[1])

    def remains(self):
        """The challengers who fell here: shields, helmets, a spear, bones (small, dull, lying flat)."""
        for kind, wx, wy, seed in REMAINS:
            rnd = random.Random(900 + seed)
            x0, y0 = int(wx - X0), int(wy - Y0)
            pts = {}
            if kind == 'shield':
                # a heater shield lying on its back, tilted: iron rim, two faded colours, split by a blow
                ang = rnd.uniform(-0.6, 0.6)
                ca, sa = math.cos(ang), math.sin(ang)
                field = (P.STONE_COOL, P.SAND) if seed % 2 else (P.BARK, P.STONE_COOL)
                shape = {}
                for v in range(0, 12):
                    half = 5.5 if v < 6 else 5.5 * (1 - (v - 6) / 6.5)
                    for u in range(-6, 7):
                        if abs(u) > half:
                            continue
                        x = int(round(u * ca - v * 0.6 * sa))
                        y = int(round(u * sa * 0.6 + v * 0.6 * ca)) - 3
                        edge = abs(u) > half - 1.2 or v == 0 or v >= 11
                        shape[(x, y)] = (edge, u)
                for (x, y), (edge, u) in shape.items():
                    if edge:
                        pts[(x, y)] = P.IRON[3] if y < 0 or x > 0 else P.IRON[1]
                    else:
                        pts[(x, y)] = P.ramp(field[0] if u < 0 else field[1], 3.2 - y * 0.12, x0 + x, y0 + y)
                for k in range(5):
                    pts[(k - 2, -2 + k // 2)] = P.OUTLINE
            elif kind == 'helmet':
                # a great helm on its side: dome, eye slit, breaths, a dent
                for y in range(-4, 4):
                    for x in range(-4, 5):
                        if (x / 4.6) ** 2 + ((y + 0.3) / 4.2) ** 2 > 1:
                            continue
                        pts[(x, y)] = P.STEEL[4] if y < -2 and x > -2 else P.STEEL[3] if x > 0 else P.STEEL[2] if y < 2 else P.STEEL[1]
                for x in range(-3, 4):
                    pts[(x, -1)] = P.IRON[0]
                for (x, y) in ((1, 1), (1, 2), (3, 1)):
                    pts[(x, y)] = P.IRON[1]
                pts[(-3, -3)] = P.STEEL[1]
            elif kind == 'spear':
                a = rnd.uniform(-0.5, 0.5) + (math.pi if seed % 2 else 0)
                ln = rnd.randint(16, 24)
                for k in range(ln):
                    x, y = int(round(math.cos(a) * k)), int(round(math.sin(a) * k * 0.55))
                    pts[(x, y)] = P.BARK[3] if k % 5 else P.BARK[2]
                    pts[(x, y + 1)] = P.BARK[1]
                hx, hy = int(round(math.cos(a) * ln)), int(round(math.sin(a) * ln * 0.55))
                for k in range(4):
                    pts[(hx + int(round(math.cos(a) * k)), hy + int(round(math.sin(a) * k * 0.55)))] = P.STEEL[3 if k < 3 else 4]
            if kind in ('bones', 'skull'):
                # a skull (and for 'bones' a few long bones and ribs)
                skull = [(0, -1), (1, -1), (2, -1), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0), (-1, 1), (0, 1), (1, 1), (2, 1), (3, 1),
                         (0, 2), (1, 2), (2, 2)]
                for (x, y) in skull:
                    pts[(x, y)] = P.BONE[3] if y < 1 else P.BONE[2]
                pts[(0, 1)] = P.BONE[0]
                pts[(2, 1)] = P.BONE[0]
                if kind == 'bones':
                    for b in range(rnd.randint(3, 5)):
                        a = rnd.uniform(0, math.pi)
                        bx, by = rnd.randint(-10, 8), rnd.randint(-3, 5)
                        for k in range(rnd.randint(4, 8)):
                            pts[(bx + int(round(math.cos(a) * k)), by + int(round(math.sin(a) * k * 0.5)))] = P.BONE[2 if k % 3 else 3]
            # outline and a soft shadow under it
            for (x, y) in list(pts):
                for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if n not in pts:
                        self.put(x0 + n[0], y0 + n[1], P.OUTLINE)
            for (x, y), col in pts.items():
                self.put(x0 + x, y0 + y, col)

    def flowers(self):
        """Wild flowers: little clusters outside the court and in the outer joints (pale, never red)."""
        rnd = random.Random(self.seed + 71)
        for _ in range(900):
            wx, wy = rnd.uniform(-700, 700), rnd.uniform(-330, 440)
            r, _ = ell(wx, wy)
            if r < 0.8 or wy < BACKDROP_Y + 4:
                continue
            ix, iy = int(wx - X0), int(wy - Y0)
            tid = self.ids[iy][ix] if 0 <= iy < H and 0 <= ix < W else None
            if tid is not None and tid[0] in ('c', 'p', 'k') and not self.seam(ix, iy):
                continue
            if tid is not None and tid[0] == 't' and r < R_RIM_IN and not self.seam(ix, iy):
                continue
            col = P.FLOWERS[rnd.randrange(len(P.FLOWERS))]
            for k in range(rnd.randint(2, 6)):
                x, y = ix + rnd.randint(-4, 4), iy + rnd.randint(-2, 2)
                self.put(x, y + 1, P.GRASS[2])
                self.put(x, y, col)
                if rnd.random() < 0.3:
                    self.put(x + 1, y, P.mix(col, (0, 0, 0), 0.3))

    def mushrooms(self):
        """Pale mushrooms in the shade outside the court, in little groups."""
        rnd = random.Random(self.seed + 81)
        for _ in range(120):
            wx, wy = rnd.uniform(-720, 720), rnd.uniform(-330, 440)
            r, _ = ell(wx, wy)
            if r < 1.08 or wy < BACKDROP_Y + 4:
                continue
            ix, iy = int(wx - X0), int(wy - Y0)
            for k in range(rnd.randint(2, 4)):
                x, y = ix + rnd.randint(-5, 5), iy + rnd.randint(-2, 2)
                big = rnd.random() < 0.4
                self.put(x, y, P.MUSH[1])
                self.put(x, y - 1, P.MUSH[1])
                cap = (-1, 0, 1) if not big else (-2, -1, 0, 1, 2)
                for dx in cap:
                    self.put(x + dx, y - 2, P.MUSH[3] if dx < 1 else P.MUSH[2])
                    self.put(x + dx, y - 3 if abs(dx) < (2 if big else 1) else y - 2,
                             P.MUSH[3] if dx < 1 else P.MUSH[2])
                for dx in range(min(cap) - 1, max(cap) + 2):
                    if not (min(cap) <= dx <= max(cap)):
                        self.put(x + dx, y - 2, P.OUTLINE)
                self.put(x, y + 1, P.OUTLINE)

    def roots(self):
        """Old roots creeping in over the court's rim from the trees (north) and the sides."""
        c = self.c
        rnd = random.Random(self.seed + 21)
        starts = [(-585, -330, 0.9), (-430, -340, 1.3), (262, -345, 1.6), (560, -332, 2.2), (-620, 40, 0.1), (630, -40, 3.1),
                  (-600, 200, -0.4), (610, 210, 3.5)]
        for sx, sy, a in starts:
            for b in range(rnd.randint(2, 3)):
                x, y = float(sx), float(sy)
                ang = a + rnd.uniform(-0.5, 0.5)
                th = rnd.uniform(3.0, 5.0)
                for k in range(rnd.randint(60, 140)):
                    ang += rnd.uniform(-0.15, 0.15)
                    x += math.cos(ang) * 1.3
                    y += math.sin(ang) * 0.75
                    th = max(1.0, th - 0.025)
                    r, _ = ell(x, y)
                    if r < 0.86:
                        break
                    ix, iy = int(x - X0), int(y - Y0)
                    for d in range(int(round(th))):
                        tone = 1.0 + d * 0.9 + (0.6 if d == int(round(th)) - 1 else 0)
                        if 0 <= ix < W and 0 <= iy - d < H:
                            c.px[ix, iy - d] = P.ramp(P.BARK, tone, ix, iy - d, 'grain') + (255,)
                    if 0 <= ix < W and 0 <= iy + 1 < H:
                        c.px[ix, iy + 1] = P.EARTH[0] + (255,)

    def leaves(self):
        """Fallen leaves blown over the court (more toward the trees and the rim)."""
        c = self.c
        rnd = random.Random(self.seed + 33)
        cols = [P.GOLD[1], P.GOLD[0], P.EARTH[4], P.MOSS[4], P.BANNER[3]]
        for _ in range(1600):
            wx, wy = rnd.uniform(-640, 640), rnd.uniform(-330, 400)
            r, _ = ell(wx, wy)
            if rnd.random() > 0.15 + max(0.0, r - 0.5) * 0.9:
                continue
            ix, iy = int(wx - X0), int(wy - Y0)
            col = cols[rnd.randrange(len(cols))]
            c.px[ix, iy] = col + (255,)
            if rnd.random() < 0.6:
                c.px[ix + 1, iy] = P.mix(col, (0, 0, 0), 0.25) + (255,)

    def tufts(self):
        """Grass tufts: in the joints of the outer paving, along the curb, thick outside."""
        c = self.c
        rnd = random.Random(self.seed + 7)
        for _ in range(5200):
            wx = rnd.uniform(X0 + 4, X0 + W - 4)
            wy = rnd.uniform(Y0 + 4, Y0 + H - 4)
            r, _ = ell(wx, wy)
            if wy < BACKDROP_Y - 30:
                continue
            ix, iy = int(wx - X0), int(wy - Y0)
            tid = self.ids[iy][ix]
            if tid is None:
                p = 0.85 if r > 1.06 else 0.0
            elif tid[0] == 't':
                p = (0.05 + max(0.0, r - 0.55) * 0.9) if self.seam(ix, iy) else 0.0
            elif tid[0] == 'c':
                p = 0.5 if self.seam(ix, iy) else 0.0
            else:
                p = 0.0
            if r < 0.3:
                p = 0.0
            if rnd.random() > p:
                continue
            lit = lit_field(wx, wy)
            shade = shade_field(wx, wy)
            blades = rnd.randint(2, 4)
            for b in range(blades):
                bx = ix + rnd.randint(-2, 2)
                hgt = rnd.randint(2, 4)
                lean = rnd.choice((-1, 0, 0, 1))
                for k in range(hgt):
                    x, y = bx + (lean if k >= hgt - 1 else 0), iy - k
                    tone = 1.5 + k * 0.7 + lit * 1.5 - shade
                    if 0 <= x < W and 0 <= y < H:
                        c.px[x, y] = P.ramp(P.GRASS, tone, x, y) + (255,)


def render(path=None, cast=None):
    g = Ground(cast=cast)
    g.paint()
    if path:
        g.c.save(path)
    return g.c.im


if __name__ == '__main__':
    import sys
    render(sys.argv[1] if len(sys.argv) > 1 else '/tmp/ground.png')
