"""Parts at sheet resolution: the back view's body without its hanging sword forearm.

The third concept (2026-09-30: "sword bigger, hand higher") draws the long greatsword held high
in the front and facing-right views, so those are used as drawn. Only the back view needs
work: its right arm hangs with the fist at the hip, but the hand is up on the sword's grip
(hidden behind the shoulder from behind), so the forearm and fist are erased (ARM) and the
sword is drawn behind the body (idle.py).
"""
from PIL import Image, ImageDraw, ImageFilter
import boss as B

# erased: the back view's hanging right forearm + fist below the elbow (sheet coordinates);
# FILL: (polygon, (dx, dy)) - erased pixels inside the polygon take the pixel at (x+dx, y+dy)
# of the untouched view (none needed: behind the forearm there is only backdrop)
ARM = {
    'back': {'hidden': [(724, 440), (772, 440), (774, 510), (724, 510)]},
}
FILL = {'back': []}


def _poly_mask(size, origin, pts, grow=0):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).polygon([(x - origin[0], y - origin[1]) for x, y in pts], fill=255)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(2 * grow + 1))
    return m


def body(view):
    """The view with ARM[view]['hidden'] erased and the gaps refilled (FILL)."""
    im = B.ref(view)
    if view not in ARM:
        return im
    orig = im.copy()
    o = B.meta()[view]['origin']
    erase = _poly_mask(im.size, o, ARM[view]['hidden'], grow=1)
    p, e, q = im.load(), erase.load(), orig.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            if e[x, y]:
                p[x, y] = (0, 0, 0, 0)
    for pts, (dx, dy) in FILL[view]:
        fm = _poly_mask(im.size, o, pts).load()
        for y in range(H):
            for x in range(W):
                if not (fm[x, y] and e[x, y]):
                    continue
                for k in (1, 2, 3):
                    sx, sy = x + k * dx, y + k * dy
                    if 0 <= sx < W and 0 <= sy < H and q[sx, sy][3] and not e[sx, sy]:
                        p[x, y] = q[sx, sy]
                        break
    return im
