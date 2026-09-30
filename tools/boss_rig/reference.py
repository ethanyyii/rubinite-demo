"""Cut the Boss views out of the concept sheet at full resolution and clean them.

    python3 tools/boss_rig/reference.py            # writes tools/boss_rig/ref/*.png + ref.json

The concept sheet (docs/art-reference/veltharis-concept.webp, 2026-09-30 third version: about
5.2 heads, the greatsword reaching the chin, the fist high on the grip - the user's reference
for "sword bigger, hand higher") shows four views on one row: front, back, facing right,
facing left (facing left is not used, see VIEWS). It is AI-generated "pixel art" with no regular pixel grid, so unlike the
knight we do not try to recover native pixels: every view is cut out at sheet resolution,
cleaned here, and scaled down to the final size in one step later (boss.stylize).

Cleaning per view:
  - background: flood fill from the sheet border over pixels within BG_TOL of the backdrop
    colour, grown into the darker glow around the figures (grow_into_halo), then a seeded flood fill (3 px dilation, clipped to the view's column band) so
    the neighbouring views are not picked up; backdrop seen through gaps (between cape
    tatters) is enclosed by the figure and removed separately (paper_pockets);
  - ground: everything below the soles, and the shadow in a band above them (except the
    boots, the cape hem and the sword tip);
  - swords (front, right, left): the red flames around the blade are effects
    (boss-veltharis §8.2: drawn by code). Per row the blade runs from its outermost pale
    rim pixel on the left to the one on the right; everything in the sword's zone outside
    the blade, the hilt and the body is removed.
"""
import json
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'docs', 'art-reference', 'veltharis-concept.webp')
OUT = os.path.join(HERE, 'ref')
BG = (40, 42, 46)       # backdrop colour of the sheet
BG_TOL = 16             # sum of |channel difference| that still counts as backdrop

# view -> (column band on the sheet, seed inside the figure). Bands split at the columns
# where neighbouring figures come closest (fewest figure pixels in the column).
# The sheet's facing-left view is not used: its sword is shorter and the fist lower than in
# the facing-right view (the user's reference is "sword bigger, hand higher"), so facing left
# is facing right mirrored (user 2026-09-30: mirroring left is acceptable).
VIEWS = {
    'front': ((0, 110, 455, 850), (250, 450)),
    'back': ((455, 110, 780, 850), (610, 450)),
    'right': ((780, 110, 1108, 850), (920, 450)),
}
# sheet rows of the crown tip (topmost pixel of the crown's tallest spike) and the soles, body
# centre column on the ground (between the boots; side view: under the hip), measured on 2x
# zooms with a grid (2026-09-30, third concept: the long sword held high). All views stand on
# one ground line at one scale, so boss.View scales every view by the FRONT view's height.
CROWN_TIP = {'front': 131, 'back': 135, 'right': 128}
SOLE = {'front': 810, 'back': 810, 'right': 812}
BODY_CX = {'front': 255, 'back': 620, 'right': 925}
GROUND_BAND = 12        # rows above the sole where shadow is removed outside the boots
BOOTS = {
    'front': [(100, 735, 212, 815), (300, 735, 408, 815)],
    'back': [(488, 738, 572, 815), (668, 738, 752, 815)],
    'right': [(858, 725, 998, 816)],
}

# The swords. blade: first/last blade row and a rough guide (row, left x, right x) traced on
# 2x zooms; the real edges are the outermost pale rim pixels near it (blade_span). hilt:
# pommel, grip, the fist on it and the crossguard. zone: where the flames are (everything in
# it that is not blade, hilt or body is removed). body_edge: (row, x) of the body's edge next
# to the sword, body_side: which side of it the body is (+1 right, -1 left); blade_edge: below
# the crossguard the body starts right at the blade's edge. pommel/grip/tip: the sword's axis
# (grip = the fist); lower_hand: where the second hand goes in two-handed attacks (just above
# the crossguard).
SWORDS = {
    'front': {
        'blade': (400, 812, [(400, 40, 120), (500, 34, 114), (600, 30, 108), (700, 34, 100), (780, 42, 82),
                             (812, 48, 56)]),
        'hilt': [(88, 219), (116, 219), (123, 245), (128, 278), (130, 336), (150, 345), (170, 370), (168, 408),
                 (140, 412), (30, 412), (16, 392), (22, 355), (60, 336), (62, 280), (82, 250)],
        'zone': [(0, 212), (84, 212), (84, 336), (170, 336), (170, 820), (0, 820)],
        'body_side': +1, 'body_edge': [(336, 130), (420, 128), (600, 124), (820, 120)], 'blade_edge': True,
        'recolor': 32,
        'pommel': (101, 220), 'grip': (95, 305), 'lower_hand': (97, 332), 'tip': (50, 808),
    },
    'right': {
        'blade': (425, 816, [(425, 998, 1070), (500, 1002, 1066), (600, 1006, 1062), (700, 1010, 1060),
                             (780, 1026, 1056), (816, 1040, 1050)]),
        'hilt': [(1008, 234), (1034, 234), (1040, 262), (1048, 290), (1050, 340), (1040, 352), (1060, 375),
                 (1084, 395), (1084, 432), (1060, 442), (975, 442), (960, 420), (966, 390), (990, 375),
                 (1003, 352), (988, 340), (984, 300), (1005, 262)],
        'zone': [(986, 345), (1110, 345), (1110, 822), (986, 822)],
        'body_side': -1, 'body_edge': [(345, 986), (822, 986)],
        'pommel': (1020, 236), 'grip': (1018, 318), 'lower_hand': (1020, 370), 'tip': (1045, 815),
    },
}
# the back view's right arm (screen right seen from behind): its elbow; the hanging forearm and
# fist are erased there (the hand is up on the sword's grip, hidden behind the shoulder)
BACK_ELBOW = (745, 425)

# enclosed backdrop-coloured regions at least this big are backdrop; smaller ones only near
# the hem (dark armour next to the outline can match the backdrop in small patches)
POCKET_MIN, POCKET_MIN_LOW, POCKET_LOW_BAND = 60, 30, 110


def lum(c):
    return (c[0] * 3 + c[1] * 4 + c[2] * 2) / 9


def near_backdrop(c):
    return abs(c[0] - BG[0]) + abs(c[1] - BG[1]) + abs(c[2] - BG[2]) < BG_TOL


def background_mask(sheet):
    """255 = figure, 0 = backdrop connected to the sheet border."""
    diff = ImageChops.difference(sheet, Image.new('RGB', sheet.size, BG))
    r, g, b = diff.split()
    tot = ImageChops.add(ImageChops.add(r, g), b)
    m = tot.point(lambda v: 255 if v < BG_TOL else 0)
    W, H = sheet.size
    for x in range(0, W, 4):
        for y in (0, H - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    for y in range(0, H, 4):
        for x in (0, W - 1):
            if m.getpixel((x, y)) == 255:
                ImageDraw.floodfill(m, (x, y), 128)
    fg = m.point(lambda v: 0 if v == 128 else 255)
    return grow_into_halo(sheet, fg)


# The third concept has a darker glow around each figure (28-35 grey against the 40-46
# backdrop), which filled the gaps between the crown and shoulder spikes. The background grows
# into it: neutral (channels within HALO_SPREAD), lum HALO_LUM, blue not below red. The near-black
# outline (lum < 22) stops it, so it does not leak into the dark armour.
HALO_LUM = (22, 50)
HALO_SPREAD = 9


def is_halo(c):
    r, g, b = c
    L = (r * 3 + g * 4 + b * 2) / 9
    return max(c) - min(c) <= HALO_SPREAD and HALO_LUM[0] <= L <= HALO_LUM[1] and b >= r - 2


def grow_into_halo(sheet, fg):
    from collections import deque
    p, q = sheet.load(), fg.load()
    W, H = sheet.size
    dq = deque((x, y) for y in range(H) for x in range(W) if q[x, y] == 0)
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and q[nx, ny] and is_halo(p[nx, ny]):
                q[nx, ny] = 0
                dq.append((nx, ny))
    return fg


def is_backdrop_patch(cs):
    """The backdrop is a flat neutral grey: a patch of it averages neutral (red and blue within
    4 of green) and has some pixels within 5 of the exact backdrop colour. The back view's dark
    cape panel is also within BG_TOL of the backdrop, but it is tinted purple (red and blue
    6-10 above green) and has almost no exact matches, so it stays."""
    n = len(cs)
    r, g, b = (sum(c[i] for c in cs) / n for i in range(3))
    exact = sum(1 for c in cs if abs(c[0] - BG[0]) + abs(c[1] - BG[1]) + abs(c[2] - BG[2]) <= 5) / n
    return r - g <= 4 and b - g <= 4 and exact >= 0.05


def paper_pockets(sheet, region, box, sole):
    """Backdrop seen through gaps is enclosed by the figure, so the border flood fill misses
    it: remove backdrop-coloured components (4-connected) of POCKET_MIN+ pixels, or
    POCKET_MIN_LOW+ near the hem."""
    p = sheet.load()
    r = region.load()
    seen = set()
    removed = 0
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if (x, y) in seen or not r[x, y] or not near_backdrop(p[x, y]):
                continue
            comp, st = [], [(x, y)]
            seen.add((x, y))
            while st:
                a, b = st.pop()
                comp.append((a, b))
                for q in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if box[0] <= q[0] < box[2] and box[1] <= q[1] < box[3] and q not in seen \
                            and r[q] and near_backdrop(p[q]):
                        seen.add(q)
                        st.append(q)
            low = max(q[1] for q in comp) > sole - POCKET_LOW_BAND
            if len(comp) >= (POCKET_MIN_LOW if low else POCKET_MIN) and is_backdrop_patch([p[q] for q in comp]):
                for q in comp:
                    r[q] = 0
                removed += len(comp)
    return removed


def isolate(sheet, fg, name):
    box, seed = VIEWS[name]
    clip = Image.new('L', sheet.size, 0)
    ImageDraw.Draw(clip).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=255)
    f = ImageChops.multiply(fg, clip)
    m = f.filter(ImageFilter.MaxFilter(3))
    ImageDraw.floodfill(m, seed, 100)
    region = ImageChops.multiply(m.point(lambda v: 255 if v == 100 else 0), f)
    n = paper_pockets(sheet, region, box, SOLE[name])
    print(f'  {name}: {n} px of enclosed backdrop removed')
    out = sheet.convert('RGBA')
    out.putalpha(region)
    return out


def cut_ground(im, name, keep=None):
    """Remove everything below the soles and the shadow band above them outside the boots
    (keep(x, y) -> True protects other things standing on the ground: the sword tip)."""
    p = im.load()
    box = VIEWS[name][0]
    sole = SOLE[name]
    boots = BOOTS[name]
    for y in range(sole - GROUND_BAND, box[3]):
        for x in range(box[0], box[2]):
            if not p[x, y][3] or (keep and keep(x, y) and y <= sole):
                continue       # the sword tip is kept down to the sole row, not into the ground
            in_boot = any(b[0] <= x < b[2] and b[1] <= y < b[3] for b in boots)
            if y > sole or not in_boot and not cape_hem(p[x, y], y, sole):
                p[x, y] = (0, 0, 0, 0)


def cape_hem(c, y, sole):
    """Cape hem tips reach into the ground band; the shadow is a dull grey."""
    r, g, b = c[:3]
    reddish = r > g + 40 and r > 70
    purple = b > g + 12 and r > g + 5 and lum(c) > 35
    return y < sole - 3 and (reddish or purple)


# ------------------------------------------------------------------ swords
def is_pale(c):
    """The blade's rim: light and not strongly saturated (the flame glow is saturated red)."""
    return c[3] and lum(c) > 125 and max(c[:3]) - min(c[:3]) < 90 and c[1] > 95


def guide(rows, y):
    for (y0, a0, b0), (y1, a1, b1) in zip(rows, rows[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
    return rows[-1][1:]


def blade_span(p, blade):
    """Per row, the blade from its outermost left rim pixel to its outermost right rim pixel
    (+2 px of outline), searched within 8 px of the guide; smoothed over +-3 rows so the
    serration's notches do not cut into the blade."""
    top, bottom, rows = blade
    raw = {}
    for y in range(top, bottom + 1):
        a, b = guide(rows, y)
        xs = [x for x in range(int(a) - 8, int(b) + 9) if is_pale(p[x, y])]
        raw[y] = (min(xs) - 2, max(xs) + 2) if xs else (round(a), round(b))
    span = {}
    for y in raw:
        near = [raw[q] for q in range(y - 3, y + 4) if q in raw]
        span[y] = (min(v[0] for v in near), max(v[1] for v in near))
    return span


def polyline_x(pts, y):
    for (y0, x0), (y1, x1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
    return pts[-1][1]


def is_flame(c):
    """Flame streaks and their glow: saturated, bright reds and pinks."""
    r, g, b = c[:3]
    return r > 150 and r > g + 60 and r > b + 45


def recolor_flames(p, span, width, side):
    """Flame streaks over the cape next to the blade (within `width` px of it on the body's
    side): grow the streak mask 1 px into reddish glow, then repaint each pixel with the
    median of the non-flame pixels around it, from the streak's edges inwards."""
    todo = set()
    for y, (a, b) in span.items():
        xs = range(b + 1, b + 1 + width) if side > 0 else range(a - width, a)
        for x in xs:
            if p[x, y][3] and is_flame(p[x, y]):
                todo.add((x, y))
    for (x, y) in list(todo):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                c = p[q]
                inside = q[1] in span and span[q[1]][0] <= q[0] <= span[q[1]][1]
                if q not in todo and c[3] and not inside and c[0] > 110 and c[0] > c[1] + 45:
                    todo.add(q)
    for _ in range(16):
        if not todo:
            break
        done = {}
        for (x, y) in todo:
            nb = [p[x + dx, y + dy] for dx in range(-4, 5) for dy in range(-4, 5)
                  if (x + dx, y + dy) not in todo and p[x + dx, y + dy][3] and not is_flame(p[x + dx, y + dy])]
            if len(nb) >= 6:
                nb.sort(key=lum)
                done[(x, y)] = nb[len(nb) // 2]
        for q, c in done.items():
            p[q] = c
            todo.discard(q)


def clean_sword(im, name):
    """Remove the flames around a sword. Returns (sword mask image, blade span)."""
    sw = SWORDS[name]
    p = im.load()
    span = blade_span(p, sw['blade'])
    hilt = Image.new('L', im.size, 0)
    ImageDraw.Draw(hilt).polygon(sw['hilt'], fill=255)
    hilt = hilt.filter(ImageFilter.MaxFilter(3))
    zone = Image.new('L', im.size, 0)
    ImageDraw.Draw(zone).polygon(sw['zone'], fill=255)
    k, z = hilt.load(), zone.load()
    xs = [q[0] for q in sw['zone']]
    ys = [q[1] for q in sw['zone']]
    for y in range(min(ys), max(ys) + 1):
        edge = polyline_x(sw['body_edge'], y)
        if sw.get('blade_edge') and y in span:
            edge = min(edge, span[y][1]) if sw['body_side'] > 0 else max(edge, span[y][0])
        for x in range(min(xs), max(xs) + 1):
            if not z[x, y] or k[x, y]:
                continue
            if y in span and span[y][0] <= x <= span[y][1]:
                continue
            on_body = (x - edge) * sw['body_side'] > 0
            if not on_body:
                p[x, y] = (0, 0, 0, 0)
    if sw.get('recolor'):
        recolor_flames(p, span, sw['recolor'], sw['body_side'])
    mask = Image.new('L', im.size, 0)
    q = mask.load()
    for y, (a, b) in span.items():
        for x in range(a, b + 1):
            q[x, y] = 255
    mask = ImageChops.lighter(mask, hilt)
    return ImageChops.multiply(mask, im.getchannel('A')), span


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith('.png'):
            os.remove(os.path.join(OUT, f))
    sheet = Image.open(SRC).convert('RGB')
    fg = background_mask(sheet)
    meta = {}
    for name in VIEWS:
        im = isolate(sheet, fg, name)
        sword_mask = None
        if name in SWORDS:
            sword_mask, span = clean_sword(im, name)
            cut_ground(im, name, lambda x, y, s=span: y in s and s[y][0] <= x <= s[y][1])
        else:
            cut_ground(im, name)
        box = im.getbbox()
        ox, oy = box[0], box[1]
        entry = {'origin': [ox, oy], 'crown_tip': CROWN_TIP[name] - oy, 'sole': SOLE[name] - oy,
                 'cx': BODY_CX[name] - ox}
        im.crop(box).save(os.path.join(OUT, name + '.png'))
        if sword_mask is not None:
            sword = Image.new('RGBA', im.size, (0, 0, 0, 0))
            sword.paste(im, (0, 0), sword_mask)
            sb = sword.getbbox()
            sword.crop(sb).save(os.path.join(OUT, f'sword_{name}.png'))
            sw = SWORDS[name]
            entry['sword'] = {'origin': [sb[0], sb[1]], 'pommel': list(sw['pommel']), 'grip': list(sw['grip']),
                              'lower_hand': list(sw['lower_hand']), 'tip': list(sw['tip'])}
        if name == 'back':
            entry['elbow'] = list(BACK_ELBOW)
        entry['size'] = [box[2] - box[0], box[3] - box[1]]
        meta[name] = entry
        print(name, entry)
    with open(os.path.join(OUT, 'ref.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)


if __name__ == '__main__':
    main()
