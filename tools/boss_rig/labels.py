"""Which part every pixel of the approved standing sprites belongs to.

    python3 tools/boss_rig/labels.py <out dir>      # debug overlays, one per view

Polygons are in local coordinates (pixels of ref/<view>.png), traced on 4x zooms with a 10 px
grid. A final pixel takes the label of the first rule its centre matches (ORDER); everything
left over is the cape. Parts:
  sword   - the greatsword with the fist on it (planted; carried in the walk)
  head    - helmet and crown
  body    - armour, arms, tabard, chains (everything that rides on the chest and hips)
  leg_l, leg_r - screen-left / screen-right leg (down, up: boots only in the back view)
  leg     - the side view's near leg (replaced by posed legs in the walk, limb.py)
  arm     - front, back: the hanging arm(s); side: the forearm (bridges the chest and the fist
            on the planted sword)
  tabard, chain - front: the tabard and the chain with the cross pendant hanging from the belt
  cloth   - the side view's tabard hanging in front of the legs
  drape   - the front view's cloak panel that hangs in FRONT of the screen-right thigh
  cape    - the rest: cloak, fur collar
"""
import os
import sys
from PIL import Image, ImageDraw
import boss as B
import idle
import rig

POLY = {
    'front': {
        'head': [[(192, 18), (205, 8), (227, 0), (250, 8), (262, 18), (264, 62), (254, 72), (254, 105),
                  (244, 120), (208, 120), (198, 105), (198, 72), (188, 62)]],
        'leg_l': [[(128, 286), (192, 286), (192, 470), (186, 500), (180, 540), (180, 590), (186, 605),
                   (190, 682), (84, 682), (84, 650), (100, 620), (112, 598), (126, 590), (126, 540),
                   (113, 500), (118, 460), (122, 400), (126, 340)]],
        'leg_r': [[(292, 492), (350, 478), (350, 560), (346, 590), (356, 602), (380, 628), (392, 660),
                   (392, 682), (288, 682), (288, 602), (292, 590)]],
        'body': [
            # chest, pauldrons (with the screen-left spikes), hips
            [(98, 128), (118, 102), (138, 98), (140, 66), (150, 66), (153, 96), (170, 92), (172, 46),
             (181, 46), (184, 92), (200, 95), (262, 95), (300, 100), (298, 288), (138, 288), (150, 250),
             (150, 215), (115, 207), (98, 200)],
        ],
        # the hanging arm and fist (screen right)
        'arm': [[(298, 192), (345, 186), (362, 245), (364, 290), (358, 335), (372, 350), (372, 386),
                 (322, 390), (316, 340), (306, 300), (296, 262)]],
        'tabard': [[(188, 288), (262, 288), (262, 530), (245, 560), (238, 595), (222, 595), (212, 560),
                    (190, 530)]],
        # chain and cross pendant hanging from the belt
        'chain': [[(264, 288), (296, 288), (296, 480), (294, 590), (270, 590), (268, 480)]],
        'drape': [[(296, 262), (316, 340), (322, 390), (372, 386), (372, 470), (350, 478), (292, 492),
                   (296, 480)]],
    },
    'right': {
        'head': [[(136, 60), (140, 30), (150, 22), (165, 15), (180, 0), (188, 0), (205, 18), (214, 60),
                  (214, 105), (200, 118), (150, 118), (140, 100)]],
        # forearm: elbow cop to the wrist (the fist is on the sword)
        'arm': [[(150, 190), (200, 186), (216, 183), (222, 200), (222, 226), (200, 236), (170, 246),
                 (150, 240)]],
        'leg': [[(104, 345), (182, 345), (182, 440), (178, 495), (150, 515), (148, 598), (152, 612),
                 (200, 650), (204, 684), (84, 684), (84, 650), (100, 620), (100, 520), (104, 490)]],
        # the tabard hanging in front of the legs (dark cloth, red edge, cross pendant)
        'cloth': [[(182, 330), (206, 330), (206, 645), (150, 645), (148, 520), (178, 495), (182, 440)]],
        'body': [[(100, 112), (118, 100), (122, 46), (130, 46), (136, 60), (140, 100), (150, 118),
                  (200, 118), (212, 128), (216, 183), (150, 190), (150, 240), (222, 226), (208, 250),
                  (206, 330), (182, 330), (182, 345), (104, 345), (110, 250), (100, 200)]],
    },
    'back': {
        'head': [[(116, 60), (122, 20), (135, 12), (150, 0), (158, 0), (170, 12), (182, 20), (190, 60),
                  (190, 92), (180, 100), (125, 100), (116, 90)]],
        'arm': [
            [(28, 150), (75, 150), (72, 200), (66, 235), (62, 290), (56, 330), (52, 372), (10, 372),
             (6, 330), (8, 290), (6, 240), (18, 200)],
            [(236, 108), (262, 100), (290, 112), (302, 150), (298, 200), (300, 245), (314, 262), (312, 298),
             (266, 298), (262, 255), (244, 240), (236, 200), (232, 150)],
        ],
        'leg_l': [[(52, 598), (100, 598), (104, 625), (116, 650), (118, 682), (30, 682), (32, 650), (46, 625)]],
        'leg_r': [[(228, 598), (278, 598), (282, 625), (296, 650), (298, 682), (212, 682), (214, 650),
                   (226, 625)]],
    },
}
ORDER = {
    'front': ['sword', 'head', 'arm', 'tabard', 'chain', 'body', 'leg_l', 'leg_r', 'drape'],
    'right': ['sword', 'head', 'arm', 'body', 'leg', 'cloth'],
    'back': ['head', 'arm', 'leg_l', 'leg_r', 'sword'],
}
# leg polygons are drawn generously; cloth-coloured pixels inside them stay cape (the tattered
# hem hanging over the knee)
CLOTH_STAYS_CAPE = {'front': ('leg_r',), 'back': ('leg_l', 'leg_r', 'arm')}


def back_sword():
    """The back view's sword as idle.compose places it: (image, local position of its corner)."""
    m = B.meta()['back']
    sword, pts = idle.sword_cutout('front')
    sword = sword.transpose(Image.FLIP_LEFT_RIGHT)
    gx = sword.width - 1 - pts['grip'][0]
    ex = m['elbow'][0] - m['origin'][0]
    return sword, (round(ex + idle.BACK_GRIP_OUT - gx), m['sole'] - (sword.height - 1))


def sword_pixels(view, lay):
    """Final pixels covered by the view's sword cut-out (the back view's stands behind the
    body: the rules before it in ORDER take what the body covers)."""
    m = B.meta()[view]
    if view == 'back':
        sw, (ox, oy) = back_sword()
    else:
        sw = B.ref('sword_' + view)
        ox, oy = m['sword']['origin'][0] - m['origin'][0], m['sword']['origin'][1] - m['origin'][1]
    a = sw.getchannel('A').load()
    out = set()
    x0, y0 = lay.local_to_final((ox, oy))
    x1, y1 = lay.local_to_final((ox + sw.width, oy + sw.height))
    for y in range(int(y0) - 1, int(y1) + 2):
        for x in range(int(x0) - 1, int(x1) + 2):
            lx, ly = lay.final_to_local((x, y))
            hit = 0
            for dx in (-1.5, 0, 1.5):
                for dy in (-1.5, 0, 1.5):
                    sx, sy = int(lx + dx - ox), int(ly + dy - oy)
                    if 0 <= sx < sw.width and 0 <= sy < sw.height and a[sx, sy] >= 128:
                        hit += 1
            if hit >= 5:
                out.add((x, y))
    return out


def label(direction):
    """{(x, y): part} for every opaque pixel of the standing sprite (down, right, up)."""
    view = rig.VIEW_OF[direction]
    lay = rig.Layout(view)
    pix = rig.pixels(rig.standing()[direction])
    masks = {'sword': sword_pixels(view, lay)}
    for name, polys in POLY[view].items():
        masks[name] = rig.poly_mask(view, polys, lay)
    keep_cape = CLOTH_STAYS_CAPE.get(view, ())
    out = {}
    for q, c in pix.items():
        lab = 'cape'
        for name in ORDER[view]:
            if q in masks.get(name, ()):
                if name in keep_cape and rig.is_cloth(c):
                    continue
                lab = name
                break
        out[q] = lab
    absorb_islands(out)
    return out


ISLAND = 12


def absorb_islands(lab):
    """Small islands of a label (stray flame pixels beside the sword, a few cape-coloured
    pixels inside the armour) take the label around them; otherwise they are left behind, or
    drag a blob of underlay along, when their neighbours move."""
    seen = set()
    for q0 in list(lab):
        if q0 in seen:
            continue
        name = lab[q0]
        comp, st = [], [q0]
        seen.add(q0)
        while st:
            a = st.pop()
            comp.append(a)
            for b in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if b not in seen and lab.get(b) == name:
                    seen.add(b)
                    st.append(b)
        if len(comp) >= ISLAND:
            continue
        around = {}
        for a in comp:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    v = lab.get((a[0] + dx, a[1] + dy))
                    if v is not None and v != name:
                        around[v] = around.get(v, 0) + 1
        if around:
            new = max(around, key=around.get)
            for a in comp:
                lab[a] = new


TINT = {'sword': (255, 255, 0), 'head': (0, 255, 255), 'body': (0, 120, 255), 'leg_l': (0, 255, 0),
        'leg_r': (255, 0, 255), 'leg': (0, 255, 0), 'arm': (255, 128, 0), 'cloth': (255, 0, 255),
        'drape': (255, 128, 0), 'tabard': (255, 0, 0), 'chain': (255, 255, 255), 'cape': (255, 255, 255), 'boot_l': (0, 255, 0), 'boot_r': (255, 0, 255)}


def overlay(direction, k=5):
    im = rig.standing()[direction]
    lab = label(direction)
    bb = im.getbbox()
    out = Image.new('RGB', ((bb[2] - bb[0] + 4) * k * 2, (bb[3] - bb[1] + 4) * k), (60, 110, 60))
    p = im.load()
    d = ImageDraw.Draw(out)
    W = (bb[2] - bb[0] + 4) * k
    for (x, y), name in lab.items():
        c = p[x, y][:3]
        X, Y = (x - bb[0] + 2) * k, (y - bb[1] + 2) * k
        d.rectangle((X, Y, X + k - 1, Y + k - 1), fill=c)
        t = TINT[name]
        if name == 'cape':
            m = tuple(v // 3 for v in c)
        else:
            m = tuple((a + b) // 2 for a, b in zip(c, t))
        d.rectangle((W + X, Y, W + X + k - 1, Y + k - 1), fill=m)
    for v in range(0, bb[3] - bb[1] + 4, 10):
        d.text((2, v * k), str(v + bb[1] - 2), fill=(255, 255, 0))
    for v in range(0, bb[2] - bb[0] + 4, 10):
        d.text((v * k, 2), str(v + bb[0] - 2), fill=(255, 255, 0))
    return out


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for dname in sys.argv[2:] or ['down']:
        overlay(dname).save(os.path.join(out, f'labels_{dname}.png'))
        lab = label(dname)
        counts = {}
        for v in lab.values():
            counts[v] = counts.get(v, 0) + 1
        print(dname, counts)
