"""Size and look proposal for the Boss (before any animation): the standing pose in four
directions, side by side with the concept and with the knight, and pasted into real game
frames.

    python3 tools/boss_rig/export_size.py [--palette] [--mock=<dir with below.png, right.png, feet.txt>]

--palette rebuilds tools/boss_rig/palette.txt from the four standing frames (only while the
look is still being settled; afterwards the palette is frozen so every frame shares it).
--mock: game screenshots with the Boss's placeholder hidden (made once with a throwaway
capture script; feet.txt = name, boss feet x y, player feet x y, screen w h).

Writes docs/art-preview/boss/size/.
"""
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont
import boss as B
import idle

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'size')
KNIGHT = os.path.join(B.ROOT, 'assets', 'sprites', 'player', 'knight_idle.png')
KNIGHT_CELL, KNIGHT_ANCHOR = 56, (28, 53)
# proposed frame for the non-attack animations (idle, walk, hit, kneel): final px
FW, FH, AX, AY = 256, 224, 128, 208
# proposed frame for the attacks (container only; the Boss is the same size)
ATK_W, ATK_H, ATK_AX, ATK_AY = 384, 336, 192, 272
ORDER = [('down', '朝下'), ('right', '朝右'), ('up', '朝上'), ('left', '朝左')]
BG = (58, 56, 60, 255)
INK = (235, 228, 220, 255)
DIM = (160, 152, 150, 255)
GROUND = (110, 104, 100, 255)
Z = 3                    # game scale


def font(size):
    for p in ('/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def standing(height=B.HEIGHT, pal=None):
    fr = idle.frames(FW, FH, AX, AY, height)
    if pal is None:
        pal = B.load_palette()
    out = {k: B.stylize(f.im, pal) for k, f in fr.items()}
    if height == B.HEIGHT:
        # facing left is its own sprite (user 2026-09-30: the sword is in the right hand, on
        # the far side when he faces left), built from the facing-right layers (side.py)
        import rig
        out['left'] = rig.standing()['left']
    return out


def knight():
    sheet = Image.open(KNIGHT).convert('RGBA')
    rows = {'down': 0, 'right': 1, 'up': 2, 'left': 3}
    return {k: sheet.crop((0, r * KNIGHT_CELL, KNIGHT_CELL, (r + 1) * KNIGHT_CELL)) for k, r in rows.items()}


def concept(name, height_px, mirror=False):
    """A concept view cut out (ref/), at the front view's scale with its crown-to-sole =
    height_px (all views share it); mirror for facing left (facing right mirrored)."""
    m = B.meta()[name]
    im = B.ref(name)
    s = B.sheet_scale(height_px / B.WORK)
    im = B.premul_resize(im, (round(im.width * s), round(im.height * s)))
    cx, sole = m['cx'] * s, m['sole'] * s
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
        cx = im.width - cx
    return im, (cx, sole)


def text(d, xy, s, size=22, fill=INK, anchor='la'):
    d.text(xy, s, font=font(size), fill=fill, anchor=anchor)


# ------------------------------------------------------------------ 1. four directions
def sheet_directions(boss):
    col = FW * Z + 40
    top = 70
    W = col * 4 + 40
    H = top + FH * Z + 60 + FH * Z + 50
    img = Image.new('RGBA', (W, H), BG)
    d = ImageDraw.Draw(img)
    text(d, (20, 18), f'Boss 站姿四方向：身高 {B.HEIGHT}px（腳底到正面王冠尖），遊戲裡的倍率（3 倍）；框＝提案的畫格 {FW}×{FH}', 26)
    concepts = {'down': concept('front', B.HEIGHT * Z), 'right': concept('right', B.HEIGHT * Z),
                'up': concept('back', B.HEIGHT * Z), 'left': concept('right', B.HEIGHT * Z, mirror=True)}
    ccap = {'down': '設計圖正面', 'right': '設計圖朝右', 'up': '設計圖背面（沒畫劍，劍是補的）',
            'left': '設計圖朝右（左右翻；成品另外畫：右手持劍在遠側）'}
    for i, (k, label) in enumerate(ORDER):
        x0 = 20 + i * col
        # frame box (the proposed grid) and foot anchor
        fx, fy = x0, top
        d.rectangle((fx - 1, fy - 1, fx + FW * Z, fy + FH * Z), outline=(90, 86, 92, 255))
        img.alpha_composite(up(boss[k], Z), (fx, fy))
        axp, ayp = fx + AX * Z, fy + AY * Z + Z
        d.line((fx, ayp, fx + FW * Z - 1, ayp), fill=GROUND)
        text(d, (fx + FW * Z // 2, fy + FH * Z + 8), label, 22, anchor='ma')
        # concept, same height, feet on the same column
        cim, (ccx, csole) = concepts[k]
        cy0 = top + FH * Z + 60
        cx = round(axp - ccx) if k != 'down' else round(axp - ccx)
        img.alpha_composite(cim, (cx, round(cy0 + AY * Z + Z - csole)))
        d.line((fx, cy0 + AY * Z + Z, fx + FW * Z - 1, cy0 + AY * Z + Z), fill=GROUND)
        text(d, (fx + FW * Z // 2, cy0 + FH * Z + 8), ccap[k], 20, DIM, anchor='ma')
    return img


# ------------------------------------------------------------------ 2. next to the knight
def sheet_vs_knight(boss, kn):
    top = 80
    gap = 14
    kw = KNIGHT_CELL * Z
    xs = []
    W = 60 + 4 * (kw + gap) + 30
    for k, _ in ORDER:
        bb = boss[k].getbbox()
        W += (bb[2] - bb[0] + 4) * Z + gap
    W += 40
    ground_y = top + (B.HEIGHT + 16) * Z
    H = ground_y + 40
    img = Image.new('RGBA', (W, H), BG)
    d = ImageDraw.Draw(img)
    text(d, (20, 18), '和主角並排（遊戲倍率 3 倍，同一條地面線）', 26)
    for h, lab in ((40, '主角身體 40px'), (B.HEIGHT, f'Boss {B.HEIGHT}px')):
        y = ground_y - h * Z
        d.line((20, y, W - 20, y), fill=(95, 90, 96, 255))
        text(d, (22, y - 24), lab, 18, DIM)
    d.line((20, ground_y, W - 20, ground_y), fill=GROUND, width=2)
    x = 60
    for k, _ in ORDER:
        img.alpha_composite(up(kn[k], Z), (x, ground_y - (KNIGHT_ANCHOR[1] + 1) * Z))
        x += kw + gap
    x += 30
    for k, _ in ORDER:
        im = boss[k]
        bb = im.getbbox()
        crop = im.crop((bb[0] - 2, 0, bb[2] + 2, im.height))
        img.alpha_composite(up(crop, Z), (x, ground_y - (AY + 1) * Z))
        x += crop.width * Z + gap
    return img


def sheet_reach(boss, kn, pal):
    """Side-on reach check: the Boss facing right, the knight facing left where a sweep can
    just touch it, a ground ruler with the chosen ranges, and the sword laid level with its tip
    at the reaches (ghosts): two hands (heavy) and one hand (light)."""
    r = reach(B.HEIGHT)
    x0 = 60 + 70 * Z
    ruler = 200
    W = x0 + ruler * Z + 640
    ground_y = 110 + (B.HEIGHT + 16) * Z
    H = ground_y + 110
    img = Image.new('RGBA', (W, H), BG)
    d = ImageDraw.Draw(img)
    text(d, (20, 18), f'大劍長度與揮到的最遠距離（身高 {B.HEIGHT}px，3 倍，從 Boss 腳底中心往前量）', 26)
    text(d, (20, 54), f'劍長 {r["sword"]:.0f}px（劍首到下巴高）。半透明的劍＝劍放平時劍尖能到的位置（示意，不是動畫的姿勢）。'
                     f'往側面伸直：雙手 {r["two"][1]:.0f}px、單手 {r["one"][1]:.0f}px。', 18, DIM)
    sweep = RANGES['sweep']
    marks = [(sweep, (255, 210, 120, 255), f'橫掃、反手橫斬、快斬、上挑的判定範圍 {sweep}px（原本 100）'),
             (sweep + KNIGHT_RADIUS, (150, 200, 255, 255), f'主角（受擊圓半徑 8）被打到的最遠位置 {sweep + KNIGHT_RADIUS}px'),
             (RANGES['chop'], (255, 150, 110, 255), f'下劈、迴旋的判定範圍 {RANGES["chop"]}px（原本 110、100）')]
    for v, col, _ in marks:
        X = x0 + v * Z
        for yy in range(100, ground_y, 12):
            d.line((X, yy, X, yy + 6), fill=col)
    d.line((20, ground_y, x0 + ruler * Z + 20, ground_y), fill=GROUND, width=2)
    img.alpha_composite(up(boss['right'], Z), (x0 - AX * Z, ground_y - (AY + 1) * Z))
    kx = x0 + (sweep + KNIGHT_RADIUS) * Z
    img.alpha_composite(up(kn['left'], Z), (kx - KNIGHT_ANCHOR[0] * Z, ground_y - (KNIGHT_ANCHOR[1] + 1) * Z))
    sw, grip, tip = idle.sword_part()
    pad = (-sw.width) % B.WORK, (-sw.height) % B.WORK
    canvas = Image.new('RGBA', (sw.width + pad[0], sw.height + pad[1]), (0, 0, 0, 0))
    canvas.paste(sw, (0, 0))
    small = B.stylize(canvas, pal).rotate(90, expand=True)     # tip now points right
    small = small.crop(small.getbbox())
    shoulder_y = ground_y - round(0.72 * B.HEIGHT * Z)
    ghosts = ((r['two'][0], f'雙手（重攻擊）往前伸直：{r["two"][0]:.0f}px'),
              (r['one'][0], f'單手（輕攻擊）往前伸直：{r["one"][0]:.0f}px'))
    for i, (reach_px, lab) in enumerate(ghosts):
        g = up(small, Z)
        g.putalpha(g.getchannel('A').point(lambda v: min(v, 150)))
        gy = shoulder_y - g.height // 2 + i * (g.height + 30)
        gx = round(x0 + reach_px * Z - g.width)
        img.alpha_composite(g, (gx, gy))
        d.line((gx + g.width, gy - 4, gx + g.width, gy + g.height + 4), fill=INK, width=2)
        text(d, (gx, gy - 28), lab, 18, INK)
    for v in range(0, ruler + 1, 10):
        X = x0 + v * Z
        d.line((X, ground_y + 4, X, ground_y + (14 if v % 50 == 0 else 8)), fill=DIM)
        if v % 50 == 0:
            text(d, (X, ground_y + 18), f'{v}', 16, DIM, 'ma')
    lx = x0 + ruler * Z + 40
    for i, (v, col, lab) in enumerate(marks):
        y = 130 + i * 34
        for xx in range(lx, lx + 30, 10):
            d.line((xx, y + 10, xx + 5, y + 10), fill=col, width=2)
        text(d, (lx + 40, y), lab, 18, col)
    text(d, (lx + 40, 130 + len(marks) * 34), f'突刺：劍 {RANGES["thrust"]}px＋往前衝 {RANGES["lunge"]}px（原本 100＋120）', 18, DIM)
    return img


# Attack ranges for the 160 px Boss with the long greatsword held high (user 2026-09-30: "make
# the lines, you decide"; then "sword bigger, hand higher"). Chosen where the sword tip lands at
# the contact frame (reach() below, 160 px: two hands straight ahead 149, one hand ahead 167,
# with a lean or a step into the swing on top). Old values (120 px Boss, hip-high sword) and the
# shoulder-high sword's in brackets.
RANGES = {
    'sweep': 155,       # C1/C2 sweeps, C5 up-slash radius [100, 140]
    'quick': 165,       # the two one-handed quick slashes (user 2026-10-02: the straight arm and the deep lean reach 168-171, "enlarge the range")
    'chop': 165,        # C3 overhead chop, line length [110, 150]
    'spin': 165,        # C6 spin radius [100, 150]: arms out, two hands
    'thrust': 150,      # C4 sword length of the thrust [100, 135] ...
    'lunge': 160,       # ... plus the lunge [120, 160]
}
KNIGHT_RADIUS = 8


def proposed_ranges(h=None):
    return RANGES['sweep'], RANGES['chop'], RANGES['lunge']


# The front view's right shoulder joint (sheet coordinates, third concept, 2x zoom with a grid)
# and the arm's length as a share of the height (the straight hanging arm of the second concept:
# shoulder -> fist 191 of 657). Two hands on the grip: they reach TWO_HAND of one straight arm,
# in front of the chest (no shoulder offset).
SHOULDER = (145, 290)
ARM_SHARE = 0.29
TWO_HAND = 0.8


def reach(h):
    """Sword length and how far its tip reaches from the Boss's centre on the ground (final
    px, height h), from the front view's proportions and its sword:
    one hand (the fist high on the grip) - arm straight ahead: sqrt(out^2 + (arm + blade)^2);
    out to the side: out + arm + blade;
    two hands (the second hand just above the crossguard) - ahead: TWO_HAND * arm + blade2;
    to the side: out + TWO_HAND * arm + blade2. blade = from that hand to the tip."""
    m = B.meta()['front']
    T = m['sole'] - m['crown_tip']
    k = h / T
    sw = m['sword']
    L = sw['tip'][1] - sw['pommel'][1]
    blade1 = sw['tip'][1] - sw['grip'][1]
    blade2 = sw['tip'][1] - sw['lower_hand'][1]
    out = m['cx'] + m['origin'][0] - SHOULDER[0]
    arm = ARM_SHARE * T
    one = (math.hypot(out, arm + blade1), out + arm + blade1)
    two = (TWO_HAND * arm + blade2, out + TWO_HAND * arm + blade2)
    return {'sword': L * k, 'one': (one[0] * k, one[1] * k), 'two': (two[0] * k, two[1] * k)}


# ------------------------------------------------------------------ 3. in the game
def mock(boss, shot, feet, direction, ring=True):
    """A game screenshot (Boss placeholder hidden) with the standing Boss pasted at its feet,
    the sweep range (yellow) and the Boss's hurt circle (red), scaled to 1920 wide."""
    import sys as _s
    img = Image.open(shot).convert('RGBA')
    bx, by, px, py = feet
    fr = boss[direction]
    if ring:
        r, hr = RANGES['sweep'], 35
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(layer)
        rd.ellipse((bx - r, by - r, bx + r, by + r), outline=(255, 210, 120, 120))
        rd.ellipse((bx - hr, by - hr, bx + hr, by + hr), outline=(255, 120, 120, 100))
        img.alpha_composite(layer)
    img.alpha_composite(fr, (bx - AX, by - AY))    # the knight never overlaps the Boss in these shots
    return up(img, 1920 // img.width)


def main():
    args = sys.argv[1:]
    os.makedirs(OUT, exist_ok=True)
    if '--palette' in args:
        fr = idle.frames(FW, FH, AX, AY)
        pal = B.build_palette([B.raw_colours(f.im) for f in fr.values()])
        B.save_palette(pal)
        print('palette rebuilt:', len(pal), 'colours')
    boss = standing()
    for k, im in boss.items():
        im.save(os.path.join(OUT, f'boss_stand_{k}_x1.png'))
    sheet = Image.new('RGBA', (FW * 4, FH), (0, 0, 0, 0))
    for i, (k, _) in enumerate(ORDER):
        sheet.alpha_composite(boss[k], (i * FW, 0))
    sheet.save(os.path.join(OUT, 'boss_stand_sheet_x1.png'))
    sheet_directions(boss).save(os.path.join(OUT, 'boss_four_directions.png'))
    kn = knight()
    sheet_vs_knight(boss, kn).save(os.path.join(OUT, 'boss_vs_knight.png'))
    sheet_reach(boss, kn, B.load_palette()).save(os.path.join(OUT, 'boss_reach.png'))
    r = reach(B.HEIGHT)
    print('sword %.1f px; one hand ahead %.1f side %.1f; two hands ahead %.1f side %.1f'
          % (r['sword'], *r['one'], *r['two']))
    mock_dir = next((a.split('=', 1)[1] for a in args if a.startswith('--mock=')), None)
    if mock_dir:
        with open(os.path.join(mock_dir, 'feet.txt')) as fh:
            for line in fh:
                if not line.strip():
                    continue
                name, bx, by, px, py, *_ = line.split()
                direction = {'below': 'down', 'right': 'right', 'start': 'down', 'north': 'down'}[name]
                mock(boss, os.path.join(mock_dir, name + '.png'), (int(bx), int(by), int(px), int(py)),
                     direction, ring=name in ('below', 'right')).save(os.path.join(OUT, f'boss_ingame_{name}.png'))
    for k, _ in ORDER:
        print(k, 'bbox', boss[k].getbbox())
    print('wrote', OUT)


if __name__ == '__main__':
    main()
