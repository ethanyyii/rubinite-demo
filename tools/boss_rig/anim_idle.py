"""Boss idle (待機、喘息): slow breathing, four directions, 12 poses x 10 combat frames = 2.0 s.

Everything is whole-pixel moves of the approved standing sprite (rig.py); pose 0 IS the
approved sprite. Part by part (animation-review §4.2):
  legs, boots  - planted, do not move (weight on both feet)
  hips         - do not move
  belly, chest - rise 1 px, then the chest, shoulders and pauldrons 1 px more (CHEST): a row is
                 duplicated at the belt seam and at the chest seam, nothing is resampled
  head         - follows the chest one pose late
  hanging arm  - rides on the shoulder (rises with the chest)
  sword arm    - the fist stays on the planted sword; the shoulder rises, the forearm bridges
                 (side view: sheared between elbow and wrist). Facing left it is the far arm:
                 only its fist on the grip shows in front of the chest; the near (left) arm
                 hangs free and rides on the chest
  sword        - planted on the ground, does not move (its runes and flames are drawn by code)
  cape         - its top rides on the shoulders; the lift and a slow sway travel down the cloth,
                 the hem 2 poses late and 2 px wide
  tabard, chain, side cloth - hang from the belt: hem sways 1 px, later than the cape
CHEST and SWAY are 0 for the last two poses and pose 0, so with lags of up to 2 poses every
part is at rest in pose 0.
"""
import boss as B
import rig
import labels

N = 12
HOLD = 10                       # combat frames per pose
CHEST = [0, 0, 1, 1, 2, 2, 2, 2, 1, 1, 0, 0]
SWAY = [0, 0.6, 1, 1, 0.6, 0, -0.6, -1, -1, -0.6, 0, 0]
UNDER = 4                       # px of underlay grown under the layers above
UNDER_SHADE = 0.8               # underlays are darkened (they sit in the shadow of the part above)

# bottom to top
Z = {
    'front': ['cape', 'leg_l', 'leg_r', 'drape', 'body', 'chain', 'tabard', 'arm', 'head', 'sword'],
    'right': ['cape', 'cloth', 'leg', 'body', 'arm', 'head', 'sword'],
    'back': ['sword', 'leg_l', 'leg_r', 'cape', 'arm', 'head'],
}
# seams in local rows: the belly rises above BELT, the chest once more above CHEST_SEAM;
# cape: rows of its root (shoulders) and hem
SEAMS = {
    'front': {'belt': 292, 'chest': 205, 'cape_top': 110, 'cape_hem': 660, 'hang_top': 290, 'hang_hem': 590},
    'right': {'belt': 300, 'chest': 205, 'cape_top': 100, 'cape_hem': 670, 'hang_top': 330, 'hang_hem': 640},
    'back': {'belt': 300, 'chest': 205, 'cape_top': 110, 'cape_hem': 660, 'hang_top': 290, 'hang_hem': 590},
}
# side view: the forearm is sheared between the elbow (rises with the chest) and the wrist
# (on the planted sword), local columns
FOREARM = (155, 216)


def build_layers(direction, cape_reach=0):
    """{name: Layer} of the standing sprite with underlays, and the z order. cape_reach > 0
    (the walk, where legs and cloth move apart by more than a few px): the cloth layers are
    first mirrored that far under the layers above them."""
    if direction == 'left':
        import side
        return side.left_layers()
    view = rig.VIEW_OF[direction]
    lab = labels.label(direction)
    pix = rig.pixels(rig.standing()[direction])
    order = Z[view]
    layers = {name: rig.Layer(name, {}) for name in order}
    for q, name in lab.items():
        layers[name].pix[q] = pix[q]
    for i, name in enumerate(order[:-1]):
        above = set()
        for other in order[i + 1:]:
            above |= set(layers[other].pix)
        if cape_reach and name in ('cape', 'drape', 'cloth'):
            rig.mirror_under(layers[name], above, cape_reach)
        rig.grow_under(layers[name], above, UNDER)
    # what shows from under another part is in its shadow: a copied highlight would flash
    snap = B.Snapper(B.load_palette())
    for L in layers.values():
        L.under = {q: snap(tuple(round(v * UNDER_SHADE) for v in c)) for q, c in L.under.items()}
    return layers, order


_keep = {}


def standing_pinholes(direction):
    if direction not in _keep:
        _keep[direction] = rig.pinholes(rig.pixels(rig.standing()[direction]))
    return _keep[direction]


def _frac(v, a, b):
    return min(1.0, max(0.0, (v - a) / (b - a)))


def pose(direction, layers, order, i):
    """Pose i as {(x, y): colour}. Facing left is built in facing-right space (side.py) and
    mirrored by frames()."""
    view = rig.VIEW_OF.get(direction, 'right')
    lay = rig.Layout(view)
    sm = {k: lay.local_to_final((0, v))[1] for k, v in SEAMS[view].items()}
    c = CHEST[i]
    out = []
    for name in order:
        L = layers[name]
        if name in ('cape', 'drape'):
            def src(x, y):
                t = _frac(y, sm['cape_top'], sm['cape_hem'])
                j = (i - round(2 * t)) % N
                return x - round(2.0 * t ** 1.5 * SWAY[j]), y + CHEST[j]
            out.append(rig.warp(L, src))
        elif name in ('body', 'pauldron'):
            table = rig.row_table(lambda sy: (1 if c >= 1 and sy < sm['belt'] else 0)
                                  + (1 if c >= 2 and sy < sm['chest'] else 0), 0, rig.FH)
            out.append(rig.warp(L, lambda x, y: (x, table.get(y, y))))
        elif name in ('tabard', 'chain', 'cloth'):
            late = 0 if name == 'tabard' else 1
            def src(x, y, late=late):
                t = _frac(y, sm['hang_top'], sm['hang_hem'])
                j = (i - late - round(t)) % N
                return x - round(1.2 * t * SWAY[j]), y
            out.append(rig.warp(L, src))
        elif name == 'arm' and view == 'right':
            xe, xw = lay.local_to_final((FOREARM[0], 0))[0], lay.local_to_final((FOREARM[1], 0))[0]
            out.append(rig.warp(L, lambda x, y: (x, y + round(c * (1 - _frac(x, xe, xw))))))
        elif name in ('arm', 'free_arm'):
            out.append(rig.warp(L, lambda x, y: (x, y + c)))
        elif name == 'head':
            h = CHEST[(i - 1) % N]
            out.append(rig.warp(L, lambda x, y: (x, y + h)))
        else:
            out.append(L.all())
    pix = rig.composite(out)
    if i:
        keep = standing_pinholes(direction)
        if direction == 'left':
            keep = [(2 * rig.AX - x, y) for x, y in keep]
        rig.fill_pinholes(pix, keep)
    return pix


def frames(direction):
    layers, order = build_layers(direction)
    fr = [pose(direction, layers, order, i) for i in range(N)]
    if direction == 'left':
        import side
        fr = [side.mirror(f) for f in fr]
    return fr
