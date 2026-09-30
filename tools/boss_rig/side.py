"""The side view's layers for everything that is not the approved facing-right standing pose:
the walk in both side directions, and facing left altogether.

Facing left is NOT facing right mirrored (user 2026-09-30: "he holds the sword in his right
hand, so facing left the hand is mostly hidden by the body and the left hand holds nothing;
the idle has the same problem"). Both side directions are built in facing-right space from the
same body (the facing-right view; the concept's own facing-left view draws the sword in the
near hand too, so it is no help) and the left one is mirrored at the very end:

  near sword (facing right)   the sword and the arm that holds it are in front of the body
  far sword (facing left)     the sword is behind the body, its hand hidden by the torso; the
                              near arm hangs free (arm.py) and swings with the walk

What changes against the approved facing-right sprite, for both:
  - the raised forearm is taken off the torso; the torso behind it is copied from the plates
    TORSO_CLONE rows below (there is no drawing of it);
  - the shoulder plate (PAULDRON) becomes its own layer, drawn over the arm that hangs from
    under it;
  - what is left of the raised forearm in front of the chest (its rim, the wrist) is kept as
    `farwrist` for the standing far-sword pose and dropped otherwise.
"""
import boss as B
import rig
import arm
import anim_idle

# local px (ref/right.png)
PAULDRON = [(100, 112), (118, 100), (122, 46), (130, 46), (136, 60), (140, 100), (150, 112), (200, 118),
            (212, 128), (214, 170), (205, 195), (180, 205), (150, 208), (120, 200), (104, 180)]
SHOULDER = (152, 204)            # where the arm comes out from under the shoulder plate
CHEST_FRONT = 207                # column of the torso's front edge at the old forearm's rows
FOREARM_ROWS = (176, 256)
TORSO_CLONE = 14                 # final px below
FREE_ARM = (0.0, 3.0)            # the free arm at rest: upper arm, forearm degrees back from straight down

_S = {}


def _backdrop(layers):
    """What shows between the legs when they part - the dark tabard cloth. The standing leg's
    pixels are recoloured with the cloth layer's pixels of the same row (mirrored about the
    cloth's left edge), darkened; nothing below the cloth's hem."""
    cloth = layers['cloth'].pix
    rows = {}
    for (x, y) in cloth:
        rows.setdefault(y, []).append(x)
    snap = B.Snapper(B.load_palette())
    out = {}
    for (x, y) in layers['leg'].pix:
        xs = rows.get(y)
        if not xs or y > max(rows) - 3 - (x * 7 % 3):
            continue
        x0, w = min(xs), max(xs) - min(xs) + 1
        k = (x0 - 1 - x) % (2 * w)
        sx = x0 + (k if k < w else 2 * w - 1 - k)
        c = cloth.get((sx, y))
        if c is None:
            c = cloth[(min(xs, key=lambda v: abs(v - sx)), y)]
        if B.lum(c) > 60 or rig.is_gold(c):      # the pendant's gold would repeat as dashes
            c = min((cloth[(v, y)] for v in xs), key=B.lum)
        out[(x, y)] = snap(tuple(round(v * 0.7) for v in c))
    return out


def layers():
    """{'layers': {...}, 'pauldron', 'backdrop', 'farwrist', 'lay', 'sm', 'shoulder', 'free_arm',
    'free_hand'} in the facing-right frame (cached)."""
    if _S:
        return _S
    L, order = anim_idle.build_layers('right', cape_reach=10)
    lay = rig.Layout('right')
    sm = {k: lay.local_to_final((0, v))[1] for k, v in anim_idle.SEAMS['right'].items()}
    sword = set(L['sword'].pix)
    # nothing hangs under the boots: the cloth underlays stop at the hem (ragged)
    hem = lay.local_to_final((0, 640))[1]
    boots = {q for q in L['leg'].pix if q[1] > hem - (q[0] * 7 % 3)}
    for name in ('cape', 'cloth'):
        L[name].under = {q: c for q, c in L[name].under.items() if q not in boots}
    # the sword is not where the standing pose has it: no underlay pretends to know what was behind it
    for name, layer in L.items():
        if name != 'sword':
            layer.under = {q: c for q, c in layer.under.items() if q not in sword}
    body = L['body']
    mask = rig.poly_mask('right', [PAULDRON], lay)
    pauldron = rig.Layer('pauldron', {q: c for q, c in body.pix.items() if q in mask})
    body.pix = {q: c for q, c in body.pix.items() if q not in mask}
    body.under.update(pauldron.pix)          # the body's row maps read one layer
    backdrop = rig.Layer('backdrop', _backdrop(L))
    L['cloth'].under = {}                    # the backdrop is what shows behind it
    # the torso behind the raised forearm
    fill = {}
    for (x, y) in L['arm'].pix:
        c = body.pix.get((x, y + TORSO_CLONE))
        if c is not None:
            fill[(x, y)] = c
    body.pix.update(fill)
    body.under = {q: c for q, c in body.under.items() if q not in L['arm'].pix}
    # the rest of the raised forearm, in front of the chest
    x_front = lay.local_to_final((CHEST_FRONT, 0))[0]
    y0, y1 = (lay.local_to_final((0, v))[1] for v in FOREARM_ROWS)
    ahead = lambda q: q[0] > x_front and y0 <= q[1] <= y1
    farwrist = rig.Layer('farwrist', dict(L['arm'].pix))     # drawn behind the body: it hides what it hides
    for layer in (body, L['cape'], L['cloth']):
        farwrist.pix.update({q: c for q, c in layer.pix.items() if ahead(q)})
        layer.pix = {q: c for q, c in layer.pix.items() if not ahead(q)}
        layer.under = {q: c for q, c in layer.under.items() if not ahead(q)}
    shoulder = lay.local_to_final(SHOULDER)
    J = arm.hanging(shoulder, *FREE_ARM)
    _S.update(layers=L, pauldron=pauldron, backdrop=backdrop, farwrist=farwrist, lay=lay, sm=sm, view='right',
              shoulder=shoulder, free_arm=rig.Layer('free_arm', arm.near(arm.render(J, (rig.FW, 272)))), free_joints=J)
    return _S


# bottom to top, the standing pose with the sword in the far hand (facing left, before mirroring)
LEFT_ORDER = ['sword', 'farwrist', 'cape', 'cloth', 'leg', 'body', 'free_arm', 'pauldron', 'head']


def left_layers():
    """The far-sword standing pose as layers (facing-right space): ({name: Layer}, order)."""
    S = layers()
    L = dict(S['layers'])
    L.update(farwrist=S['farwrist'], free_arm=S['free_arm'], pauldron=S['pauldron'])
    return {k: L[k] for k in LEFT_ORDER}, LEFT_ORDER


def mirror(pix):
    """Facing-right space -> facing left: mirrored about the anchor column."""
    return {(2 * rig.AX - x, y): c for (x, y), c in pix.items()}


def standing_left():
    """The facing-left standing sprite: {(x, y): colour}."""
    L, order = left_layers()
    return mirror(rig.composite([L[name].all() for name in order]))
