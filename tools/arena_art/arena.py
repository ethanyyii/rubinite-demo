"""The arena's layout and export (2026-10-05).

    python3 tools/arena_art/arena.py [mock]

Writes assets/sprites/arena/ (the floor with the north ruins painted in, every standing piece, the
pillars, the banners and their burnt versions, the sun shafts) and
scripts/view/arena_layout.gd (ArenaLayout: where each piece stands, its anchor, its size), and the
review pictures in docs/art-preview/arena/. `mock`: only the full-screen mock-ups (with the knight and the
Boss) for review, nothing written to the game.

Layers (arena.md §3): the floor (with the north ruins: they stand north of the court, every fighter is
always in front of them) / standing pieces that sort with the fighters (sides and south: knee-high; the
four pillars) / the light (shafts, motes, embers) added on top. Nothing is drawn on the screen itself
(2026-10-06, the user: the corner leaves came off - the screen is the screen, the scene is the scene).
Collision is the court's ellipse (ArenaGeometry) and the pillars' feet: nothing here changes it."""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw

import pix as P
import ground as G
import props as PR

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'assets', 'sprites', 'arena')
PREVIEW = os.path.join(ROOT, 'docs', 'art-preview', 'arena')
LAYOUT = os.path.join(ROOT, 'scripts', 'view', 'arena_layout.gd')

# ArenaGeometry (not changed): the court and the pillars' feet
PILLARS = [((-354, 156), 111), ((354, 156), 87), ((-393, -144), 105), ((393, -144), 120)]

# the north band: painted into the floor picture (always behind every fighter: their feet stay south of
# y -265 (the Boss) / -292 (the knight); these stand at -326 and further north)
NORTH = [
    ('tree', (-585, -360), dict(seed=1, trunk=44, height=360)),
    ('tree', (-430, -372), dict(seed=8, trunk=30, height=360)),
    ('wall', (-330, -338), dict(seed=2, width=176, height=104)),
    ('column', (-172, -333), dict(seed=3, height=126)),
    ('arch', (-10, -342), dict(seed=4)),
    ('pole', (152, -336), dict(seed=5, height=148)),
    ('tree', (262, -376), dict(seed=9, trunk=36, height=360)),
    ('wall', (330, -344), dict(seed=6, width=140, height=86, window=False)),
    ('column', (450, -332), dict(seed=7, height=72)),
    ('tree', (560, -362), dict(seed=10, trunk=50, height=360)),
]
NORTH_BUSHES = [(-480, -330), (-250, -326), (-95, -328), (90, -327), (230, -330), (410, -326), (520, -330), (-560, -332)]
# banners (separate sprites: they burn in the second phase): where they hang (world), length
BANNERS = [((-352, -436), 84, 26), ((158, -481), 92, 28), ((-37, -470), 70, 24)]

# standing pieces that sort with the fighters (outside the court; knee-high at the south). 2026-10-06: the corner
# leaves are gone (the user: nothing may sit on the screen itself - the screen is the screen, the scene is the
# scene - and the screen must not go plain): each corner of the screen, with the camera in the middle, now looks
# out over a group of these (a brazier the Boss's fire lights in the second phase, stones, ferns, a fallen
# challenger's marker), and the sides hold bigger pieces (the old king's head, a fallen trunk) for when the
# camera moves.
SIDES = [
    # the sides
    ('rubble', (-572, -36), dict(seed=21, rx=18)),
    ('fallen_column', (-590, 20), dict(seed=22, length=58)),
    ('sword', (-552, 150), dict(seed=23, tilt=-14)),
    ('grave', (-530, 174), dict(seed=24)),
    ('bush', (-592, -150), dict(seed=26, rx=16)),
    ('sword', (-540, -215), dict(seed=27, tilt=12)),
    ('statue_head', (-596, 104), dict(seed=141)),
    ('boulder', (-600, -100), dict(seed=143, rx=14, ry=9)),
    ('rubble', (575, -70), dict(seed=31, rx=16)),
    ('sword', (568, -48), dict(seed=32, tilt=16)),
    ('bush', (578, 60), dict(seed=33)),
    ('low_wall', (585, 152), dict(seed=34, width=44)),
    ('sword', (520, 228), dict(seed=35, tilt=-12)),
    ('rubble', (610, -175), dict(seed=36, rx=14)),
    ('sword', (540, -205), dict(seed=37, tilt=-8)),
    ('log', (606, 104), dict(seed=142, length=46, radius=7)),
    ('block', (604, -120), dict(seed=144, w=18, h=11, d=7)),
    # the corners of the screen with the camera in the middle
    ('brazier', (-443, -206), dict(seed=101)),
    ('log', (-372, -268), dict(seed=102, length=38)),
    ('boulder', (-478, -252), dict(seed=103, rx=12, ry=8)),
    ('fern', (-415, -282), dict(seed=104, size=13)),
    ('grave', (-318, -292), dict(seed=105)),
    ('grass', (-505, -196), dict(seed=106)),
    ('brazier', (443, -206), dict(seed=111)),
    ('block', (365, -280), dict(seed=112, w=16, h=10, d=6)),
    ('boulder', (488, -246), dict(seed=113, rx=10, ry=7)),
    ('fern', (420, -278), dict(seed=114)),
    ('grave', (300, -300), dict(seed=115)),
    ('grass', (512, -190), dict(seed=116)),
    ('brazier', (-443, 206), dict(seed=121)),
    ('fern', (-482, 236), dict(seed=122)),
    ('boulder', (-398, 262), dict(seed=123, rx=11, ry=7)),
    ('grass', (-420, 236), dict(seed=124)),
    ('brazier', (443, 206), dict(seed=131)),
    ('fern', (482, 236), dict(seed=132)),
    ('block', (398, 262), dict(seed=133, w=14, h=8, d=5)),
    ('grass', (420, 236), dict(seed=134)),
    # the south: knee-high only
    ('low_wall', (-238, 322), dict(seed=41, width=72, height=8)),
    ('rubble', (-92, 318), dict(seed=42, rx=14, n=7)),
    ('low_wall', (58, 330), dict(seed=43, width=56, height=8)),
    ('low_wall', (318, 318), dict(seed=45, width=62, height=8)),
    ('bush', (-386, 296), dict(seed=46, ry=5)),
    ('bush', (420, 292), dict(seed=47, rx=12, ry=5)),
    ('rubble', (-470, 268), dict(seed=48, rx=12, n=6)),
    ('grass', (-160, 318), dict(seed=49, height=9)),
    ('grass', (190, 326), dict(seed=50, height=8)),
    ('fern', (250, 312), dict(seed=51, size=8)),
]
# how far the plants' tops sway in the game (px; 0: they do not)
SWAY = {'fern': 1.5, 'grass': 1.5, 'bush': 0.8}
# the brazier's bowl, from its foot: where the game puts the fire in the second phase
BRAZIER_FIRE = (0, -24)


def scattered():
    """More of the same along the court's sides, denser the further out (arena.md: the edge is made of
    rubble, roots and swords, not an invisible wall): rubble, stones, ferns and grass everywhere outside, broken
    swords and markers only on the sides (they stand 14-20 px: at the south only knee-high things), nothing in
    the north band (the ruins) and none inside the court (r >= 1.08 of the collision ellipse)."""
    rnd = random.Random(77)
    placed = [p for _, p, _ in SIDES]
    out = []
    tries = 0
    while len(out) < 90 and tries < 6000:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        r = 1.08 + rnd.random() ** 1.6 * 0.32
        wx, wy = math.cos(a) * G.HX * r, math.sin(a) * G.HY * r
        if wy < -312 or abs(wx) > 700 or wy > 400:
            continue
        if rnd.random() > (r - 1.0) * 2.4:          # denser the further out
            continue
        if any(math.hypot(wx - px, wy - py) < 26 for px, py in placed):
            continue
        south = wy > 250 and abs(wx) < 380
        kinds = ['rubble', 'bush', 'grass', 'grass'] if south else \
            ['rubble', 'sword', 'sword', 'bush', 'rubble', 'fern', 'grass', 'boulder', 'block', 'grave', 'fern']
        kind = kinds[rnd.randrange(len(kinds))]
        seed = 200 + len(out)
        kw = dict(seed=seed)
        if kind == 'rubble':
            kw.update(rx=rnd.randint(9, 18), n=rnd.randint(5, 10))
        elif kind == 'bush':
            kw.update(rx=rnd.randint(10, 17), ry=rnd.randint(4, 5) if south else rnd.randint(6, 10))
        elif kind == 'grass':
            kw.update(width=rnd.randint(7, 12), height=rnd.randint(6, 9) if south else rnd.randint(8, 12))
        elif kind == 'fern':
            kw.update(size=rnd.randint(9, 14))
        elif kind == 'boulder':
            kw.update(rx=rnd.randint(7, 12), ry=rnd.randint(5, 8))
        elif kind == 'block':
            kw.update(w=rnd.randint(11, 17), h=rnd.randint(7, 10), d=rnd.randint(4, 6))
        else:
            kw.update(tilt=rnd.uniform(-20, 20))
        out.append((kind, (int(wx), int(wy)), kw))
        placed.append((wx, wy))
    return out


def build(kind, kw):
    if kind == 'tree':
        return PR.tree(**kw)
    if kind == 'wall':
        return PR.wall(**kw)
    if kind == 'column':
        return PR.column(**kw)
    if kind == 'arch':
        return PR.arch(**kw)
    if kind == 'pole':
        c, a, _ = PR.pole(**kw)
        return c, a
    if kind == 'rubble':
        return PR.rubble(**kw)
    if kind == 'fallen_column':
        return PR.fallen_column(**kw)
    if kind == 'sword':
        return PR.broken_sword(**kw)
    if kind == 'bush':
        return PR.bush(**kw)
    if kind == 'low_wall':
        return PR.low_wall(**kw)
    if kind == 'brazier':
        return PR.brazier(**kw)
    if kind == 'boulder':
        return PR.boulder(**kw)
    if kind == 'block':
        return PR.block(**kw)
    if kind == 'fern':
        return PR.fern(**kw)
    if kind == 'grass':
        return PR.tall_grass(**kw)
    if kind == 'log':
        return PR.log(**kw)
    if kind == 'statue_head':
        return PR.statue_head(**kw)
    if kind == 'grave':
        return PR.grave(**kw)
    raise KeyError(kind)


SHADOW_K = 0.8          # shadow length per px of height (the late sun, from the upper right)


def cast_shadows():
    """The shadows the north band throws over the floor (2026-10-06): every opaque pixel of a ruin or a trunk,
    at its height above the ground, lands on the ground along the light (P.SUN_DIR) - the walls' and the arch's
    reach just over the court's north edge, the two eastern trunks' cross the north-east of the court as long
    soft bands. 'L', the floor's size; softened so the edges are not hard lines."""
    from PIL import ImageFilter
    im = Image.new('L', (G.W, G.H), 0)
    px = im.load()
    dx, dy = P.SUN_DIR
    for kind, (wx, wy), kw in NORTH:
        c, (ax, ay) = build(kind, kw)
        cp = c.px
        for y in range(c.h):
            z = ay - y
            if z < 0:
                continue
            for x in range(c.w):
                if cp[x, y][3] == 0:
                    continue
                gx = wx + (x - ax) + dx * z * SHADOW_K - G.X0
                gy = wy + dy * z * SHADOW_K - G.Y0
                ix, iy = int(gx), int(gy)
                if 0 <= ix < G.W and 0 <= iy < G.H:
                    px[ix, iy] = 255
    im = im.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.BoxBlur(3))
    return im


def floor_with_north():
    """The floor picture with the north band painted in (back to front by their foot row)."""
    g = G.render(cast=_cache('cast', cast_shadows))
    items = []
    for kind, (wx, wy), kw in NORTH:
        c, (ax, ay) = build(kind, kw)
        items.append((wy, c, wx - ax - G.X0, wy - ay - G.Y0))
    for i, (wx, wy) in enumerate(NORTH_BUSHES):
        c, (ax, ay) = PR.bush(seed=60 + i, rx=16, ry=10)
        items.append((wy + 0.5, c, wx - ax - G.X0, wy - ay - G.Y0))
    for _, c, x, y in sorted(items, key=lambda t: t[0]):
        g.alpha_composite(c.im, (int(x), int(y)))
    return g


def sun_mask():
    """Where the sun comes through the canopy (the floor's lit patches, less in the ruins' shade), a quarter of
    the floor's size: the game's moving sun flecks (sun_flecks.gdshader) only show inside it."""
    w, h = G.W // 4, G.H // 4
    cast = _cache('cast', cast_shadows)
    im = Image.new('L', (w, h), 0)
    px = im.load()
    for y in range(h):
        for x in range(w):
            wx, wy = G.X0 + x * 4 + 2, G.Y0 + y * 4 + 2
            if wy < G.BACKDROP_Y:
                continue
            cs = cast.getpixel((min(G.W - 1, x * 4 + 2), min(G.H - 1, y * 4 + 2))) / 255.0
            v = G.lit_field(wx, wy) * (1.0 - cs) * (1.0 - 0.7 * G.shade_field(wx, wy))
            px[x, y] = int(P.clamp(v, 0.0, 1.0) * 255)
    return im


# where crows sit (2026-10-06): on the stones and the fallen trunk at the court's north-west and north-east,
# and in the grass just north of the court (light enough under them for a black bird to read; not on the
# dark iron of the braziers). (kind of piece or 'ground', its position, x offset on it)
PERCH_ON = [('boulder', (-478, -252), 2), ('log', (-372, -268), 9), ('block', (365, -280), 1), ('boulder', (488, -246), -2),
            ('ground', (-142, -322), 0), ('ground', (-118, -327), 0), ('ground', (212, -318), 0)]


def perches():
    """Each crow's feet (the top edge of the piece it sits on, at the given x offset, or the ground) and the row
    it sorts by (the piece's foot, so it is drawn on top of what it sits on)."""
    out = []
    pieces = {(k, p): kw for k, p, kw in SIDES}
    for kind, (wx, wy), dx in PERCH_ON:
        if kind == 'ground':
            out.append(dict(feet=(float(wx), float(wy)), sort_y=float(wy)))
            continue
        c, (ax, ay) = build(kind, pieces[(kind, (wx, wy))])
        x = ax + dx
        top = next(y for y in range(c.h) if c.px[x, y][3])
        out.append(dict(feet=(float(wx + dx), float(wy - (ay - top))), sort_y=float(wy + 1)))
    return out


def sun_shafts():
    """Sun shafts from the upper right: three soft bands that fade before they reach the south (added on top
    in the game, faint: they must not stripe the court the fighters read)."""
    W, H = G.W, G.H
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    px = im.load()
    shafts = [(1010, 1.0, 30), (1185, 0.8, 42), (1330, 0.65, 24)]
    dx, dy = P.SUN_DIR
    for y in range(H):
        fall = P.clamp(1.0 - y / (H * 0.62), 0.0, 1.0) ** 1.4
        if fall <= 0:
            continue
        for x in range(W):
            a = 0.0
            for (x0, strength, wdt) in shafts:
                cx = x0 + dx * (y / dy)
                d = abs(x - cx)
                if d < wdt:
                    a += strength * (1 - (d / wdt) ** 2)
            if a > 0:
                a *= fall * (0.7 + 0.6 * P.value_noise(x, y, 40, 9))
                px[x, y] = (255, 222, 160, int(P.clamp(a * 34, 0, 48)))
    return im


def mock(cam=(0, -37), knight=(0, 120), boss=(0, -60), phase=1, path=None, with_props=True):
    """A 960 x 540 screen: the floor, the standing pieces and pillars, the two fighters (idle frames), the
    light. phase 2: darker and redder, the banners burning (a still)."""
    W, H = 960, 540
    ox, oy = cam[0] - 480, cam[1] - 270
    scr = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    floor = _cache('floor', floor_with_north)
    scr.alpha_composite(floor.crop((ox - G.X0, oy - G.Y0, ox - G.X0 + W, oy - G.Y0 + H)))
    for (wx, wy), ln, wdt in BANNERS:
        c, (ax, ay) = PR.banner(seed=int(wx) & 255, width=wdt, length=ln, burnt=0.55 if phase == 2 else 0.0)
        scr.alpha_composite(c.im, (int(wx - ax - ox), int(wy - ay - oy)))
    sortable = []
    if with_props:
        for kind, (wx, wy), kw in SIDES + scattered():
            c, (ax, ay) = build(kind, kw)
            sortable.append((wy, c.im, wx - ax - ox, wy - ay - oy))
        for i, ((wx, wy), h) in enumerate(PILLARS):
            c, (ax, ay) = PR.pillar(h, seed=90 + i)
            sortable.append((wy, c.im, wx - ax - ox, wy - ay - oy))
    kn = Image.open(os.path.join(ROOT, 'assets', 'sprites', 'player', 'knight_idle.png')).convert('RGBA').crop((0, 112, 56, 168))
    bs = Image.open(os.path.join(ROOT, 'assets', 'sprites', 'boss', 'boss_idle.png')).convert('RGBA').crop((0, 0, 256, 224))
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((knight[0] - ox - 11, knight[1] - oy - 3, knight[0] - ox + 11, knight[1] - oy + 4), fill=(0, 0, 0, 90))
    sd.ellipse((boss[0] - ox - 46, boss[1] - oy - 8, boss[0] - ox + 46, boss[1] - oy + 8), fill=(0, 0, 0, 90))
    scr.alpha_composite(shadow)
    sortable.append((knight[1], kn, knight[0] - 28 - ox, knight[1] - 53 - oy))
    sortable.append((boss[1], bs, boss[0] - 128 - ox, boss[1] - 208 - oy))
    for _, im, x, y in sorted(sortable, key=lambda t: t[0]):
        scr.alpha_composite(im, (int(x), int(y)))
    if phase == 2:
        tint = Image.new('RGBA', (W, H), (90, 20, 10, 70))
        scr.alpha_composite(tint)
    shafts = _cache('shafts', sun_shafts).crop((ox - G.X0, oy - G.Y0, ox - G.X0 + W, oy - G.Y0 + H))
    if phase == 1:
        add = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        add.alpha_composite(shafts)
        scr = Image.alpha_composite(scr, add)
    if path:
        scr.convert('RGB').save(path)
    return scr


_C = {}


def _cache(k, fn):
    if k not in _C:
        _C[k] = fn()
    return _C[k]


if __name__ == '__main__':
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp'
    if len(sys.argv) > 1 and sys.argv[1] == 'mock':
        mock(path=os.path.join(out, 'mock_center.png'))
        mock(cam=(-120, -170), knight=(-300, -150), boss=(-150, -265), path=os.path.join(out, 'mock_nw.png'))
        mock(cam=(120, 105), knight=(380, 240), boss=(200, 120), path=os.path.join(out, 'mock_se.png'))
        mock(phase=2, path=os.path.join(out, 'mock_phase2.png'))


# ------------------------------------------------------------------ export
def gd(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(round(v, 3)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return '"' + v + '"'
    if isinstance(v, tuple) and len(v) == 2:
        return f'Vector2({gd(float(v[0]))}, {gd(float(v[1]))})'
    if isinstance(v, list):
        return '[' + ', '.join(gd(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{gd(k)}: {gd(x)}' for k, x in v.items()) + '}'
    raise TypeError(v)


def export():
    os.makedirs(OUT, exist_ok=True)
    res = 'res://assets/sprites/arena/'
    floor = floor_with_north()
    floor.save(os.path.join(OUT, 'arena_floor.png'))
    print('floor', floor.size)
    banners = []
    for i, ((wx, wy), ln, wdt) in enumerate(BANNERS):
        for burnt, tag in ((0.0, ''), (0.55, '_burnt')):
            c, (ax, ay) = PR.banner(seed=int(wx) & 255, width=wdt, length=ln, burnt=burnt)
            c.save(os.path.join(OUT, f'banner_{i}{tag}.png'))
        banners.append(dict(texture=res + f'banner_{i}.png', burnt=res + f'banner_{i}_burnt.png', pos=(wx, wy),
                            anchor=(ax, ay), width=wdt, length=ln))
    props = []
    keep = set()
    for i, (kind, (wx, wy), kw) in enumerate(SIDES + scattered()):
        c, (ax, ay) = build(kind, kw)
        bb = c.bbox()
        name = f'prop_{i}_{kind}.png'
        keep.add(name)
        c.save(os.path.join(OUT, name))
        d = dict(texture=res + name, pos=(wx, wy), anchor=(ax, ay), kind=kind,
                 top=ay - bb[1], half_width=max(ax - bb[0], bb[2] - ax), sway=SWAY.get(kind, 0.0))
        if kind == 'brazier':
            d['fire'] = BRAZIER_FIRE
        props.append(d)
    # pictures of pieces no longer in the layout (and the old corner leaves) go
    for f in os.listdir(OUT):
        base = f[:-len('.import')] if f.endswith('.import') else f
        if (base.startswith('prop_') and base not in keep) or base.startswith('foliage_'):
            os.remove(os.path.join(OUT, f))
    pillars = []
    for i, ((wx, wy), h) in enumerate(PILLARS):
        c, (ax, ay) = PR.pillar(h, seed=90 + i)
        c.save(os.path.join(OUT, f'pillar_{i}.png'))
        pillars.append(dict(texture=res + f'pillar_{i}.png', anchor=(ax, ay)))
    sun_shafts().save(os.path.join(OUT, 'sun_shafts.png'))
    sun_mask().save(os.path.join(OUT, 'sun_mask.png'))
    lines = [
        '# Generated by tools/arena_art/arena.py - do not edit (re-run it after changing the arena art).',
        'class_name ArenaLayout',
        'extends RefCounted',
        '## 競技場的美術（2026-10-05）：地面（含北邊的廢墟）、旗子（一般／燒過）、和角色一起排序的東西、柱子的圖、',
        '## 陽光。位置都是世界座標（地面圖的左上角在 FLOOR_ORIGIN），anchor 是圖裡踩在地上的那一點；sway：植物頂端隨風擺幾 px；',
        '## fire：火盆的碗口（相對腳底），第二階段在那裡點火。2026-10-06 拿掉畫面四角的枝葉：畫面上不放任何場景的東西。',
        '',
        f'const FLOOR := "{res}arena_floor.png"',
        f'const FLOOR_ORIGIN := Vector2({G.X0}.0, {G.Y0}.0)',
        f'const SUN_SHAFTS := "{res}sun_shafts.png"',
        f'const SUN_MASK := "{res}sun_mask.png"',
        f'const PERCHES := {gd(perches())}',
        f'const BANNERS := {gd(banners)}',
        f'const PROPS := {gd(props)}',
        f'const PILLARS := {gd(pillars)}',
        '',
    ]
    with open(LAYOUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print('wrote', os.path.relpath(LAYOUT, ROOT))


if __name__ == '__main__' and (len(sys.argv) == 1 or sys.argv[1] == 'export'):
    export()
