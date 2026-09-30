"""The four-hit light combo, second version (docs/art-progress.md, "四段輕攻擊：第二版", 2026-09-29): the
user's own move design, on the 88 x 72 canvas, foot anchor (44, 61). The first version (all four
attacks read as "a blob and a thin line": arms and a 2 px blade moving, the body hardly turning) was
turned down; this one moves the whole body - shoulders, waist and feet turn together, the cape flies
the other way - and every stage has its own line and its own outline:

  1  right-low -> left-high rising diagonal (quick, short): low with the sword trailing behind on the
     right, the front foot steps, the blade rises across, the chest turns left, the cape flies right
  2  left -> right horizontal at chest height: from stage 1's end the blade drops to the left side (no
     re-draw), the waist turns back hard to the right, a longer step, the blade ends out on the right
  3  right-low -> overhead rising cut (heavy): the waist sinks, the point pressed low on the right, the
     body drives up from the legs, chest lifted, the blade ends straight up over the head
  4  a turning cut (one full turn to the left, not a top), the hit inside the turn: the blade swung down to
     behind on the right, the chest starts to turn with the blade hanging back, then - the body side-on to
     the target - the straight arm whips the blade across it (the hit); the turn goes on, the blade trailing,
     the cape flung wide, and ends square to the target, low, the blade low behind on the right; the pause.
     Its wind-up is 6 frames like stages 1-2's (2026-09-29, third mechanic change). Earlier versions turned
     before the cut (second, fourth) or cut before turning (third); the user read each as two moves with a
     stop between ("在轉身之後還揮了一刀……第三段連接第四段中間還是間隔了")

Character space: F forward, L the character's left, U up (px); right-handed, the left foot leads.

How the body turns (the rig cannot twist a waist: the library has four views, no three-quarter view):
  - twisted frames (space 'L' / 'R'): legs and head are drawn facing the target, the upper body (torso,
    pauldrons, cape, scarf, arms, sword) from the next view round - a quarter turn left or right. The
    twist the pose is written for is half of that (45 deg, TWIST): arms, blade and cloth are given in
    that half-turned space and turned the rest of the way onto the drawn torso, so a blade that points
    out to the left of the twisted chest still shows in all four views (posed for the drawn 90 deg, it
    hid behind the body in most of them). One 3D pose for all four views (animation-review §4.3).
  - stage 4's turn (k = 3, 2, 1): the whole figure drawn from the view it faces at that moment, the pose in
    the turned body's own space; its contact frame is the first of them (side-on, the blade at the target).

Timing is in simulation frames (60 Hz) from scripts/combat/player_data.gd and player_sim.gd:

| stage | start-up | active (advance) | recovery | pause | total | chain |
|---|---|---|---|---|---|---|
| 1 | 0-5 | 6-10 | 11-25 | - | 26 | from 15 (and 12 frames after the end, in the idle) |
| 2 | 0-5 | 6-10 | 11-25 | - | 26 | from 14 (same) |
| 3 | 0-6 | 7-11 | 12-28 | - | 29 | from 16 (same) |
| 4 | 0-5 | 6-11 | 12-38 | 39-50 | 51 | - (block / dodge in the pause) |

Mashing, the hits land 15 frames apart (PlayerData.COMBO_INTERVAL, 2026-09-29 second change: the user
asked for longer, even gaps; third change: stage 4's start-up 6 frames like stages 1-2, so 3 -> 4 reads like
1 -> 2 and 2 -> 3: the hit, the follow-through held a moment, a short wind-up, the hit).

The program moves the character forward on the active frames (6 px; stage 4 14 px). As batch 2
(decision 2): the picture catches up with the program when the sprite frame changes, so feet and the
pelvis are given where they are on the floor from where the stage began ("world"), and each frame is
drawn back by the advance at its first sim frame.

Legs: as the first version (the charge's second fix): planted() feet, soft side knees, front / back
feet foreshortened like the body (kd_feet), every leg >= 2.5 px on screen (fb_leg_min), the front / back
knees bent by the 3D reach (legs3d), the body hiding what is behind it (body_hides_far). The blades are
drawn with the camera's tilt in the side views too (blade_tilt): a blade swung toward / away from the
camera runs down / up the screen, as it does in the front / back views, instead of shrinking to a stub.
"""
import json
import math

import batch1 as B1
import poses as PS
import pose_rig as PR
import sprites as A
from rig import close_holes, reconnect_specks

VIEWS = B1.VIEWS
CANVAS = 'large'
FWD_SCREEN = {'east': (1, 0), 'west': (-1, 0), 'south': (0, 1), 'north': (0, -1)}

# player_data.gd light_attacks(): (start-up frames, active frames, total frames, advance px);
# stage 4's total includes the 12-frame pause after its recovery (FINISHER_END_LAG)
ATTACK = {1: (6, 5, 26, 6.0), 2: (6, 5, 26, 6.0), 3: (7, 5, 29, 6.0), 4: (6, 6, 51, 14.0)}
RECOVERY_END = {1: 26, 2: 26, 3: 29, 4: 39}
# PlayerData.chain_frame(): the earliest frame of a stage the next may start on - the hits 15 frames apart
# (COMBO_INTERVAL 0.25 s), never before the active frames end. The last frame shown is the one before it
CHAIN = {1: 15, 2: 14, 3: 16}
GRACE = 12                    # COMBO_GRACE: the next stage may start this many frames into the idle


def advance_at(stage, e):
    """Program advance (px along the facing) after sim frame e of the stage."""
    a0, n, _, total = ATTACK[stage]
    if e < a0:
        return 0.0
    return total * min(n, e - a0 + 1) / n


hand = PS.hand
# soft_knee 1.02: an attack's legs reach further and lower (first version, decision 2)
LEGS = dict(legs3d=True, floor3d=True, soft_knee={'L': 1.02, 'R': 1.02}, kd_feet=0.35,
            fb_leg_min=2.5, foot_below=2, body_hides_far=True, blade_tilt=True)


def pose(**kw):
    p = dict(LEGS)
    p['feet'] = {'R': (0, 0, 0, 'flat'), 'L': (0, 0, 0, 'flat')}
    p.update(kw)
    return p


# ------------------------------------------------------------------ spaces
# 'W' the target's frame (the legs, the head, stage 1-4's untwisted frames); 'L' / 'R' the chest turned
# TWIST deg to the left / right. A twisted frame's upper body is drawn a quarter turn round (TORSO_K,
# quarter turns clockwise as drawn_view counts them), so its vectors are turned the other TWIST on.
TWIST = 45.0
SPACE = {'W': 0.0, 'L': TWIST, 'R': -TWIST}
TORSO_K = {'L': 3, 'R': 1}
CLOTH = ('cape', 'plume', 'scarf')


def rot(v, deg):
    """(F, L, U) turned counter-clockwise (seen from above: toward the character's left) by deg."""
    if not deg:
        return tuple(v)
    a = math.radians(deg)
    f, l = v[0], v[1]
    return (f * math.cos(a) - l * math.sin(a), f * math.sin(a) + l * math.cos(a)) + tuple(v[2:])


def rotate_pose(p, deg):
    """Hands, elbow hints, the blade and the cloth of a pose turned by deg (the body's own numbers -
    root, lean, feet, head - stay)."""
    q = dict(p)
    if not deg:
        return q
    if 'arms' in p:
        arms = {}
        for s_, spec in p['arms'].items():
            sp = dict(spec)
            for k in ('at', 'elbow'):
                if k in sp:
                    sp[k] = rot(sp[k], deg)
            arms[s_] = sp
        q['arms'] = arms
    if 'sword' in p:
        q['sword'] = dict(p['sword'], dir=rot(p['sword']['dir'], deg))
    for k in CLOTH:
        if k in p:
            q[k] = rot(p[k], deg)
    return q


def convert(p, a, b):
    """A pose written in space a, rewritten in space b."""
    return rotate_pose(p, SPACE[a] - SPACE[b])


def to_torso(p, side):
    """A twist-space pose onto the drawn torso (a quarter turn to that side)."""
    return rotate_pose(p, SPACE[side] - (90.0 if side == 'L' else -90.0))


# ------------------------------------------------------------------ turning (stage 4's spin)
# A frame may be drawn turned k quarter turns clockwise (to the character's right) from the row's
# facing: the east row's k = 1 is drawn from the south view, and so on. Its pose is then in the
# turned body's own space; world vectors (the target's frame: ahead, to the left) are turned in.
CW = ['east', 'south', 'west', 'north']


def drawn_view(view, k):
    return CW[(CW.index(view) + k) % 4]


def to_body(ao, k):
    """World (ahead, left) -> the body's (ahead, left), the body turned k quarter turns right."""
    a, o = ao
    return [(a, o), (-o, a), (-a, -o), (o, -a)][k % 4]


def rest_feet(view):
    """The idle stance in planted() terms, per view (the library's own stances differ: the side
    views stand staggered, the front / back views side by side at the idle's width)."""
    if view in ('east', 'west'):
        near = PR.VIEWS[view]['near']
        return {s_: (PR.SIDE_REST_DX[view][s_] + (1.0 if s_ == near else -1.0), 4.0 if s_ == 'L' else -4.0, 0, 'flat')
                for s_ in ('R', 'L')}
    return {'R': (0.0, -4.0, 0, 'flat'), 'L': (0.0, 4.0, 0, 'flat')}


def _lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def lerp_feet(fa, fb, t):
    """In-between of two world feet dicts (the foot state from the nearer end)."""
    out = {}
    for s_ in ('R', 'L'):
        a, b = fa[s_], fb[s_]
        out[s_] = _lerp(a[:3], b[:3], t) + ((a if t < 0.5 else b)[3],)
    return out


def shift_feet(feet, d):
    return {s_: (v[0] + d,) + tuple(v[1:]) for s_, v in feet.items()}


def rig_feet(feet_w, view, dv, adv, k, root_l, body_feet=False):
    """World feet (planted terms, before the program's advance) -> the rig's feet for the drawn
    view dv: moved back by the advance, turned into the body (k), converted by planted(); side
    views take back what the root's sideways offset shows (SIDE_X), as batch 2 did."""
    moved = {}
    for s_, (a, o, lift, st) in feet_w.items():
        if body_feet:
            sa, so = to_body((-adv, 0.0), k)
            ab, ob = a + sa, o + so
        else:
            ab, ob = to_body((a - adv, o), k)
        moved[s_] = (ab, ob, lift, st)
    fv = PS.planted(moved)[dv]
    if dv in ('east', 'west'):
        fdir = PR.VIEWS[dv]['facing']
        fv = {s_: (v[0] - PR.SIDE_X * root_l * fdir,) + tuple(v[1:]) for s_, v in fv.items()}
    return fv


# Front / back views: the program's advance moves the picture 1:1 on screen, depth shows at KD (0.35):
# the pose is drawn around its own pelvis and the whole picture moved on screen (first version,
# decision 4), at most FB_SHIFT_MAX px.
FB_SHIFT_MAX = 6.0


def build(pose, feet_w, view, adv, k=0, body_feet=False):
    """A frame's rig pose (for the drawn view) from a world pose (k = 0: its root is world, from
    where the stage began) or a turned body pose (k != 0: its root is the body's own, the advance
    turned in)."""
    dv = drawn_view(view, k)
    p = B1.resolve(pose, dv)
    root = tuple(p.get('root', (0, 0, 0)))
    shift = (0, 0)
    fb_turned = body_feet and view in ('south', 'north')
    if fb_turned:
        # a turned body in a front / back row: the program's advance is up / down the screen 1:1 while the
        # drawn view may show it as depth (0.35) or across. Drawn round its own pelvis (the advance taken
        # as far as the pelvis has come), the rest shown by moving the picture - as decision 4
        ua = to_body((1.0, 0.0), k)
        wa = root[0] * ua[0] + root[1] * ua[1]
        n = int(round(max(-FB_SHIFT_MAX, min(FB_SHIFT_MAX, wa - adv))))
        adv = wa
        fx, fy = FWD_SCREEN[view]
        shift = (fx * n, fy * n)
    sa, so = to_body((-adv, 0.0), k)
    p['root'] = (root[0] + sa, root[1] + so, root[2])
    p['feet'] = rig_feet(feet_w, view, dv, adv, k, p['root'][1], body_feet)
    p.pop('feet_view', None)
    if not fb_turned and dv not in ('east', 'west'):
        d = p['root'][0]
        p['root'] = (0.0,) + tuple(p['root'][1:])
        p['feet'] = {s_: (v[0] - d,) + tuple(v[1:]) for s_, v in p['feet'].items()}
        n = int(round(max(-FB_SHIFT_MAX, min(FB_SHIFT_MAX, d))))
        fx, fy = FWD_SCREEN[dv]
        shift = (fx * n, fy * n)
    if shift != (0, 0):
        p['screen_shift'] = shift
    return p, dv


# ------------------------------------------------------------------ rendering
class F:
    """One rendered frame on the canvas: px, trace (pixel -> piece), pieces (as composited),
    pieces_raw (each piece whole, before folding and hiding: the checks measure these), debug (blade,
    hands, legs, pelvis), the rig pose (face pose for twisted frames), draw_view (legs and head),
    upper_view (torso, arms, sword) and lib_view (which library each piece comes from)."""


HEAD_PIECES = ('helmet', 'helmet_under', 'plume')
HEAD_BLEND = 0.5


def _grab(r):
    dx, dy = r.canvas_offset()
    mv = lambda d: {(x + dx, y + dy): c for (x, y), c in d.items()}
    return dict(trace={(x + dx, y + dy): n for (x, y), n in r.trace.items()},
                pieces={n: mv(v) for n, v in r.pieces.items()},
                raw={n: mv(v) for n, v in r.pieces_raw.items()},
                depths=dict(r.depths),
                blade={(x + dx, y + dy) for (x, y) in r.debug.get('blade', set())},
                hands={k: (x + dx, y + dy) for k, (x, y) in r.debug.get('hands', {}).items()},
                legs={k: tuple((q[0] + dx, q[1] + dy) for q in v) for k, v in r.debug.get('legs', {}).items()},
                pelvis=(r.debug['pelvis'][0] + dx, r.debug['pelvis'][1] + dy),
                neck=(r.debug['neck'][0] + dx, r.debug['neck'][1] + dy),
                gy=PR.CANVAS[CANVAS][3] + r._shift[1])


def render(pose, dv):
    """Render a rig pose in view dv; trace, pieces and debug moved onto the canvas (and by the pose's
    screen shift, front / back views)."""
    r = PR.rig(dv)
    px = r.frame(pose, CANVAS)
    g = _grab(r)
    f = F()
    f.px, f.trace, f.pieces, f.pieces_raw = px, g['trace'], g['pieces'], g['raw']
    f.debug = {'blade': g['blade'], 'hands': g['hands'], 'legs': g['legs'], 'pelvis': g['pelvis'], 'neck': g['neck']}
    f.pose, f.upper_pose = pose, pose
    f.draw_view = f.upper_view = dv
    f.lib_view = {}
    f.gy = g['gy']
    return f


# the face half of a twisted frame keeps the idle's arms (they are not drawn: only its legs and head are)
_FACE_KEEP = ('root', 'head', 'head_tilt', 'feet') + tuple(LEGS)


def twist_poses(pose_t, side):
    """(face pose in world space, upper pose on the drawn torso) of a twisted frame."""
    face = {k: v for k, v in pose_t.items() if k in _FACE_KEEP}
    face['arms'] = B1.REST['arms']
    face['sword'] = dict(B1.REST['sword'])
    face['plume'] = rot(pose_t.get('plume', (0, 0, 0)), SPACE[side])     # the plume rides the head
    up = to_torso({k: v for k, v in pose_t.items() if k not in ('head', 'head_tilt', 'plume')}, side)
    up['root'] = (0.0, 0.0, pose_t.get('root', (0, 0, 0))[2])
    return face, up


def render_twist(pose_t, feet_w, view, adv, side):
    """A twisted frame: legs and head (and plume) from the row's own view, everything else from the
    view a quarter turn to `side`, its pelvis on the legs' pelvis and the head on its neck. Pieces are
    laid down by their draw depth (both views count depth the same way: torso 0, helmet 45-50, what is
    in front of the body 55); cloth pushed below the floor by the join rests on it."""
    face, up = twist_poses(pose_t, side)
    pf, dvf = build(face, feet_w, view, adv, 0)
    pu, dvu = build(up, feet_w, view, adv, TORSO_K[side])
    rf = PR.rig(dvf)
    rf.frame(pf, CANVAS)
    gf = _grab(rf)
    ru = PR.rig(dvu)
    ru.frame(pu, CANVAS)
    gu = _grab(ru)
    du = (int(round(gf['pelvis'][0] - gu['pelvis'][0])), int(round(gf['pelvis'][1] - gu['pelvis'][1])))
    # the head sits between the drawn torso's neck and where the legs' own view carries it: the four
    # library views put the neck 2-5 px apart relative to the pelvis, and a head riding the torso's neck
    # jumped that far each time the chest turned (on top of the body's own move)
    nu = tuple(gu['neck'][i] + du[i] + HEAD_BLEND * (gf['neck'][i] - gu['neck'][i] - du[i]) for i in (0, 1))
    dh = (int(round(nu[0] - gf['neck'][0])), int(round(nu[1] - gf['neck'][1])))
    items = []
    for n, pix in gu['pieces'].items():
        if n.startswith('leg') or n in HEAD_PIECES:
            continue
        items.append((gu['depths'][n], len(items), n, pix, gu['raw'].get(n, {}), du))
    for n, pix in gf['pieces'].items():
        if n.startswith('leg'):
            items.append((gf['depths'][n], len(items), n, pix, gf['raw'].get(n, {}), (0, 0)))
        elif n in HEAD_PIECES:
            items.append((gf['depths'][n], len(items), n, pix, gf['raw'].get(n, {}), dh))
    gy = gf['gy']
    px, trace, pieces, raw = {}, {}, {}, {}
    for _, _, n, pix, rpix, d in sorted(items, key=lambda it: (it[0], it[1])):
        tmp = {(x + d[0], y + d[1]): c for (x, y), c in pix.items()}
        raw[n] = {(x + d[0], y + d[1]): c for (x, y), c in rpix.items()}
        if not n.startswith('leg') and not n.startswith('sword'):
            for k in [k for k in tmp if k[1] > gy]:
                c = tmp.pop(k)
                tmp.setdefault((k[0], gy), c)
        px.update(tmp)
        pieces.setdefault(n, {}).update(tmp)
        for k in tmp:
            trace[k] = n
    # the upper body's backing is cut to its own view's legs: where the legs' view stands wider, the
    # background between a leg and the torso or cape is enclosed. Such pockets (below the neck, above the
    # floor) take the legs' own view's backing - the body under them - pixel for pixel
    W_, H_, _, _ = PR.CANVAS[CANVAS]
    back_f = gf['pieces'].get('backing', {})
    neck_y = max(y for (x, y), n in trace.items() if n == 'helmet') if any(n == 'helmet' for n in trace.values()) else 0
    for q in _enclosed(px, W_, H_):
        if neck_y < q[1] < gy and q in back_f:
            px[q] = back_f[q]
            trace[q] = 'backing'
            pieces.setdefault('backing', {})[q] = back_f[q]
    # pose_rig._finish on the joined picture
    drawn = set(px)
    reconnect_specks(px)
    close_holes(px, W_, H_, max_size=14)
    legs = {k for k, n in trace.items() if n.startswith('leg')}
    for k in [k for k in px if k not in drawn and k[1] > gy]:
        if not any((k[0] + a, k[1] + b) in legs for a in (-1, 0, 1) for b in (-1, 0, 1)):
            px.pop(k)
    f = F()
    f.px, f.trace, f.pieces, f.pieces_raw = px, trace, pieces, raw
    mv = lambda q: (q[0] + du[0], q[1] + du[1])
    f.debug = {'blade': {mv(q) for q in gu['blade']}, 'hands': {k: mv(q) for k, q in gu['hands'].items()},
               'legs': gf['legs'], 'pelvis': gf['pelvis'], 'neck': nu}
    f.pose, f.upper_pose = pf, pu
    f.draw_view, f.upper_view = dvf, dvu
    f.lib_view = {n: (dvf if (n.startswith('leg') or n in HEAD_PIECES) else dvu) for n in pieces}
    f.gy = gy
    f.side = side
    return f


def _enclosed(px, W_, H_):
    opaque = set(px)
    outside = set()
    stack = [(x, y) for x in range(-1, W_ + 1) for y in (-1, H_)] + [(x, y) for y in range(-1, H_ + 1) for x in (-1, W_)]
    while stack:
        q = stack.pop()
        if q in outside or q in opaque:
            continue
        x, y = q
        if x < -1 or y < -1 or x > W_ or y > H_:
            continue
        outside.add(q)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return {(x, y) for x in range(W_) for y in range(H_) if (x, y) not in opaque and (x, y) not in outside}


def render_spec(view, pose, feet, adv, space='W', k=0, body_feet=False):
    if space in ('L', 'R'):
        return render_twist(pose, feet, view, adv, space)
    p, dv = build(pose, feet, view, adv, k, body_feet)
    return render(p, dv)


# ------------------------------------------------------------------ measuring and searching
LIMITS = {'head': 4.0, 'torso': 4.0, 'feet': 4.0, 'hands': 20.0, 'sword': 20.0}
SWING_LIMITS = dict(LIMITS, head=8.0, torso=8.0)       # batch 2 decision 5: the swing steps

_PCACHE = {}


def _key(*a):
    try:
        return json.dumps(a, sort_keys=True, default=str)
    except TypeError:
        return None


def parts(view, pose, feet_w, adv, space='W', k=0, body_feet=False):
    """Where the parts of a frame are on screen (the picture moved by the advance)."""
    import checks as C
    key = _key(view, pose, feet_w, adv, space, k, body_feet)
    if key is not None and key in _PCACHE:
        return _PCACHE[key]
    f = render_spec(view, pose, feet_w, adv, space, k, body_feet)
    fx, fy = FWD_SCREEN[view]
    out = C._Pt(f, fx * adv, fy * adv)
    out.legbad = leg_penalty(f, f.draw_view) + detail_penalty(f)
    out.frame = f
    if key is not None:
        _PCACHE[key] = out
    return out


def leg_penalty(f, dv):
    """How far a frame's legs are outside the leg rules (animation-review §4.3; 0 = inside): side
    views knee under the hip >= 10 %, near leg <= 1.0 and far <= 1.1 of its length; front / back
    every leg >= 2 px on screen."""
    import checks as C
    ks, _ = C.leg_shape(f, dv)
    if dv in ('east', 'west'):
        return (max(0.0, C.KNEE_BELOW_MIN - ks) + max(0.0, C.leg_stretch(f, 'near') - C.LEG_STRETCH_MAX) +
                max(0.0, C.leg_stretch(f, 'far') - C.LEG_STRETCH_FAR)) * 10
    return max(0.0, C.FB_LEG_SEEN_MIN - ks)


def lib_piece(f, n):
    """The library piece a drawn piece is measured against (its own view's)."""
    dv = f.lib_view.get(n, f.upper_view if n not in HEAD_PIECES else f.draw_view)
    L = PR.rig(dv).base.L
    import checks as C
    if n in C.LIB_PIECES:
        return L[n].pix if n in L else None
    if n in ('paul_R', 'paul_L'):
        lib = PR.VIEWS[dv]['paul'][n[-1]]
        return L[lib].pix if lib and lib in L else None
    return None


def detail_penalty(f):
    """How many library pieces lost or gained detail past the rule (animation-review §4.1, measured
    before compositing: checks.within_piece). Half-pixel heights and new angles resample the thin
    strips (scarf, helmet glints) and add or drop 10-40 % of their pixels."""
    import checks as C
    bad = 0
    for n in C.LIB_PIECES + ('paul_R', 'paul_L'):
        if n not in f.pieces_raw:
            continue
        lib = lib_piece(f, n)
        if lib is None:
            continue
        (b, h), (b0, h0) = C.counts(f.pieces_raw[n]), C.counts(lib)
        if not ((b0 == 0 or C.within_piece(b, b0)) and (h0 == 0 or C.within_piece(h, h0))):
            bad += 1
    return float(bad)


def worst(steps, skip=(), limits=None):
    import checks as C
    w = 0.0
    for a, b in steps:
        w = max(w, 1.0 + getattr(a, 'legbad', 0.0) if getattr(a, 'legbad', 0.0) > 0 else 0.0,
                1.0 + getattr(b, 'legbad', 0.0) if getattr(b, 'legbad', 0.0) > 0 else 0.0)
        m = C.screen_moves(a, b)
        for key, lim in (limits or LIMITS).items():
            if key in skip or m.get(key) is None:
                continue
            w = max(w, m[key] / lim)
    return w


def lerp(a, b, t, view, sa='W', sb='W', space='W'):
    """In-between of two poses (written in spaces sa, sb) in space `space`."""
    a2, b2 = convert(a, sa, space), convert(b, sb, space)
    return B1.lerp_pose(B1.resolve(a2, view), B1.resolve(b2, view), t, view)


def search_between(view, before, pose_a, pose_b, specs, after, grid, limits_in=None, limits_out=None,
                   skip_last=(), extra=None, sa='W', sb='W'):
    """In-betweens of pose_a -> pose_b (one per spec, their t rising through the grid) keeping every
    step (before -> 1 -> ... -> after) within the limits as far as possible. specs = [(feet, adv[,
    space])] per in-between; before / after = parts (or lists of them, or None). Returns (worst,
    [poses])."""
    import itertools
    n = len(specs)
    best = None
    cache = {}
    for ts in itertools.combinations(grid, n):
        ps = []
        for t, sp in zip(ts, specs):
            feet, adv = sp[0], sp[1]
            space = sp[2] if len(sp) > 2 else 'W'
            if (t, adv, space) not in cache:
                p = lerp(pose_a, pose_b, t, view, sa, sb, space)
                if extra:
                    p = extra(p, t)
                cache[(t, adv, space)] = (p, parts(view, p, feet, adv, space))
            ps.append(cache[(t, adv, space)])
        steps = []
        if before is not None:
            for bf in (before if isinstance(before, list) else [before]):
                steps.append((bf, ps[0][1]))
        steps += [(ps[i][1], ps[i + 1][1]) for i in range(n - 1)]
        w = worst(steps, limits=limits_in)
        if after is not None:
            for af in (after if isinstance(after, list) else [after]):
                w = max(w, worst([(ps[-1][1], af)], skip_last, limits=limits_out))
        if best is None or w < best[0] - 1e-9:
            best = (w, [p for p, _ in ps])
    return best


GRID = tuple(round(0.15 + 0.05 * i, 2) for i in range(15))       # 0.15 .. 0.85


def rest_pose(total):
    """The idle stance's upper body (batch 1 REST) as a world pose at the stage's end."""
    p = pose(**{k: v for k, v in B1.REST.items() if k != 'feet'})
    p['root'] = (float(total), 0.0, 0.0)
    return p


def rest_world(view, total):
    return shift_feet(rest_feet(view), total)


def idle_pts(view, adv):
    import checks as C
    fx, fy = FWD_SCREEN[view]
    return C._Pt(B1.frames('idle', view)[0], fx * adv, fy * adv, small=True)


def spec(name, first, last, pose_, feet, weight, space='W', k=0, body_feet=False, swing=False):
    return dict(name=name, first=first, last=last, pose=pose_, feet=feet, weight=weight, space=space, k=k,
                body_feet=body_feet, swing=swing)


def sp_parts(view, stage, s_):
    return parts(view, s_['pose'], s_['feet'], advance_at(stage, s_['first']), s_['space'], s_['k'], s_['body_feet'])


def _add3(v, d):
    return tuple(a + b for a, b in zip(v, d))


# ================================================================== key poses
# World roots are from where the stage began (before the program's advance). Twisted poses ('L' / 'R')
# give arms, blade and cloth in the half-turned space (TWIST) and root / head / feet for the legs and
# head (world); their `lean` is the drawn torso's own. Every attack frame stands >= 2 px lower than the
# idle (the attack stance) except stage 3's top, which drives up on purpose; the pelvis stays within the
# legs' reach of both feet (<= 7 px ahead / behind at 2 px down: the legs are ~9.4 px long, the hips ~6 px
# up), and whole pixels high (a half pixel resamples the thin strips).

# ---- stage 1: right-low -> left-high rising diagonal, quick
# the wind-up: a little lower, the sword on the right behind the hip, near waist height, pointing back
# along the floor; the weight on the back foot, the front foot lifting to step
S1_WIND = pose(root=(-1.5, 0, -2), lean=8,
               arms={'R': hand('R', -6, -12, -9, elbow=(0, -1, 0)), 'L': hand('L', 6, 6, -3, elbow=(0, 1, -1))},
               sword=dict(hand='R', dir=(-0.633, -0.754, -0.174)), cape=(3, 0, 1), plume=(2, 0, 1))
# contact: the front foot down, the blade rising across the front
S1_HIT = pose(root=(1.5, 0, -2), lean=10,
              arms={'R': hand('R', 9, -3, -1, elbow=(0, -1, 0)), 'L': hand('L', 2, 8, -4, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.75, 0.25, 0.6)), cape=(-5, 0, 3), plume=(-3, 0, 1))
# the end: the chest and shoulders turned left with the blade, the blade out high on the left, the body
# upright; the cape thrown the other way by the sudden turn
S1_END = pose(root=(3, 0, -2), lean=0, head=(0, 0, 0.5),
              arms={'R': hand('R', 4, 0, 0, elbow=(0, -1, -0.5)), 'L': hand('L', -3, 9, -5, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.0, 0.966, 0.259)), cape=(-6, -8, 6), plume=(-4, -4, 2))

# ---- stage 2: left -> right horizontal at chest height
# the cock: stage 1's blade let fall to the left side at chest height (no re-draw), the chest still
# turned left, the weight back
S2_COCK = pose(root=(-1, 0, -2), lean=4,
               arms={'R': hand('R', 3, 1, -3, elbow=(0, -1, 0)), 'L': hand('L', -3, 10, -5, elbow=(0, 1, 0))},
               sword=dict(hand='R', dir=(-0.866, 0.5, 0.0)), cape=(-2, -6, 4), plume=(-2, -3, 1))
# contact: the waist turning back, the blade level through the target, the long step landing
S2_HIT = pose(root=(0, 0, -2), lean=12,
              arms={'R': hand('R', 10, -3, 0, elbow=(0, -1, 0)), 'L': hand('L', 0, 9, -4, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.95, -0.25, 0.05)), cape=(-6, 3, 4), plume=(-4, 2, 1))
# the end: low in the long step, the chest turned right, the arm out on the right, the blade on past it
S2_END = pose(root=(3, 0, -3), lean=10,
              arms={'R': hand('R', 7, -16, 0, elbow=(0, -1, 0)), 'L': hand('L', 0, 10, -4, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.66, -0.74, -0.1)), cape=(-6, 8, 6), plume=(-4, 5, 2))

# ---- stage 3: heavy rising cut, right-low -> overhead
# the sink: the waist down deepest of the combo, the chest still turned right, the point pressed low
S3_SINK = pose(root=(-2, 0, -3), lean=14,
               arms={'R': hand('R', 8, -8, -5, elbow=(0, -1, 0)), 'L': hand('L', 5, 5, -5, elbow=(0, 1, -1))},
               sword=dict(hand='R', dir=(0.664, -0.242, -0.707)), cape=(2, 2, 1), plume=(1, 2, 1))
# contact: the legs drive the body up, the blade rising in front
S3_HIT = pose(root=(0, 0, 0), lean=0,
              arms={'R': hand('R', 9, -4, 3, elbow=(0, -1, 0)), 'L': hand('L', 1, 9, -5, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.45, 0.1, 0.89)), cape=(-2, 0, -2), plume=(-1, 0, -2))
# the top: stretched tall (up on the back foot's toes), the chest lifted, the blade straight up
S3_TOP = pose(root=(1.5, 0, 1), lean=-12, head_tilt=-8,
              arms={'R': hand('R', 3, -10, 9, elbow=(0, -1, 0)), 'L': hand('L', -5, 13, -3, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(0.05, 0.25, 0.97)), cape=(2, 0, -2), plume=(-2, 0, -2))
S3_HOLD = dict(S3_TOP, root=(2, 0, 0), head=(0, 0, -0.5), head_tilt=-6, lean=-9, cape=(1, 0, 0), plume=(-1, 0, -1),
               sword=dict(S3_TOP['sword'], dir=(0.15, 0.3, 0.94)))

# ---- stage 4: the turn is the cut - one heavy spin to the left, the blade held out, trailing the body
# (2026-09-29, fifth version; the user after the fourth: "在轉身之後還揮了一刀……第三段連接第四段中間還是間隔了":
# the hit has to be inside the turn, and nothing swung after it). Where the blade points, seen from above
# (deg to the left of the target): swung down from over the head to behind on the right (-110) - the
# wind-up, as short as stages 1-2's; the chest starts to turn left and the blade trails out on the right
# (-110, -70); the body side-on to the target (turned a quarter), the arm straight out, the blade sweeps
# through the target (0: the hit); the turn goes on with the blade trailing (80, 160) and ends square to
# the target, low, the blade out low behind on the right (240 = -120). It points at the target once.
# the wind-up: the blade swung down from over the head to behind on the right at chest height, the body
# sinking, the weight on the back foot
S4_WIND = pose(root=(-3, 0, -2), lean=0, head=(-1, 0, 0.5),
               arms={'R': hand('R', -4, -11, 1, elbow=(0, -1, 0)), 'L': hand('L', 5, 6, -2, elbow=(0, 1, -1))},
               sword=dict(hand='R', dir=(-0.34, -0.93, 0.12)), cape=(1, 2, 1), plume=(1, 1, 0))
# the turn starting: the chest turned left ('L', 45 deg), the arm straight out on the right, the blade
# trailing it (written in the half-turned space: -155 and -115 from the chest): the blade hangs back while the
# chest turns, then whips round into the hit
S4_TURN1 = pose(root=(-2, 0, -2), lean=2,
                arms={'R': hand('R', -2, -12, 0, elbow=(0, -1, 0)), 'L': hand('L', 3, 8, -2, elbow=(0, 1, 0))},
                sword=dict(hand='R', dir=(-0.9, -0.43, 0.0)), cape=(-4, -6, 4), plume=(-2, -3, 1))
S4_TURN2 = pose(root=(-1, 0, -2), lean=2,
                arms={'R': hand('R', 1, -12, 0, elbow=(0, -1, 0)), 'L': hand('L', 2, 8, -2, elbow=(0, 1, 0))},
                sword=dict(hand='R', dir=(-0.42, -0.91, -0.05)), cape=(-6, -8, 6), plume=(-3, -4, 1))
# the turn, drawn from the view the body faces (k quarter turns clockwise = 3, 2, 1: a turn to the left),
# in the turned body's own space: the arm straight out on the right, the blade trailing (pointing out to the
# right, a little behind as the turn speeds up); the cape flung out wide behind the turn. k = 3 is the hit:
# side-on, the blade through the target
SPIN_POSE = pose(root=(0, 0, -2), lean=0,
                 arms={'R': hand('R', 2, -12, 0, elbow=(0, -1, 0)), 'L': hand('L', 1, 8, -3, elbow=(0, 1, 0))},
                 sword=dict(hand='R', dir=(0.0, -1.0, -0.05)), cape=(-8, -10, 8), plume=(-4, -5, 2))
SPIN_POSES = {3: SPIN_POSE,
              2: dict(SPIN_POSE, sword=dict(hand='R', dir=(-0.17, -0.98, -0.08)), cape=(-9, -10, 10)),
              1: dict(SPIN_POSE, arms={'R': hand('R', 1, -11, -1, elbow=(0, -1, 0)), 'L': hand('L', 1, 8, -3, elbow=(0, 1, 0))},
                      sword=dict(hand='R', dir=(-0.34, -0.93, -0.12)), cape=(-8, -10, 9))}
# the feet turn with the body (stepping round, carried on with the program's advance), in the body's own
# space round the pelvis
SPIN_FEET = {'R': (-3, -3.5, 0, 'flat'), 'L': (2.5, 3.5, 0, 'flat')}
SPIN_ROOT = {3: 3.0, 2: 4.0, 1: 5.0}      # the pelvis (world, ahead) while turning
# the end: square to the target again, lowest of the combo, the blade out low behind on the right; the
# cape still trailing the turn, settling over the hold
S4_END = pose(root=(7.5, 0, -3), lean=4, head=(-1.5, 0, 0.5),
              arms={'R': hand('R', -2, -12, -3, elbow=(0, -1, 0)), 'L': hand('L', 3, 9, -2, elbow=(0, 1, 0))},
              sword=dict(hand='R', dir=(-0.5, -0.75, -0.43)), cape=(-5, -7, 5), plume=(-3, -3, 1))
S4_HOLD1 = dict(S4_END, lean=8, head=(-0.5, 0, 0), cape=(-4, -4, 3), plume=(-3, -2, 1))
S4_HOLD2 = dict(S4_HOLD1, lean=12, head=(0, 0, -0.5), cape=(-2, -2, 1), plume=(-2, -1, 0))


# ================================================================== frames
def search_frames(view, stage, a, sa, b, sb, specs, grid=None, before=(), after=(), between=None, extra=None):
    """In-betweens of key a (space sa) -> key b (space sb): one per spec (each drawn in its own space),
    their t rising through the grid, keeping every step within its limits as far as possible:
    before -> first (each (parts, limits, skip) in `before`), between the in-betweens (`between`), last ->
    after. Returns the poses."""
    import itertools
    grid = grid or GRID
    between = between or SWING_LIMITS
    cache = {}
    best = None
    for ts in itertools.combinations(grid, len(specs)):
        ps = []
        for t, sp in zip(ts, specs):
            key = (t, sp['first'])
            if key not in cache:
                p = lerp(a, b, t, view, sa, sb, sp['space'])
                if extra:
                    p = extra(p, t)
                cache[key] = (p, sp_parts(view, stage, dict(sp, pose=p)))
            ps.append(cache[key])
        w = 0.0
        for src, lim, skip in before:
            w = max(w, worst([(src, ps[0][1])], skip, lim))
        for i in range(len(ps) - 1):
            w = max(w, worst([(ps[i][1], ps[i + 1][1])], (), between))
        for dst, lim, skip in after:
            w = max(w, worst([(ps[-1][1], dst)], skip, lim))
        if best is None or w < best[0] - 1e-9:
            best = (w, [p for p, _ in ps])
    return best[1]


def recovery(view, stage, hold, s_hold, returns, total, hold_space='W'):
    """The frames back to the stance after the hold (drawn untwisted), searched so every step (and the
    step into the idle) stays within the limits."""
    rest = rest_pose(total)
    a = sp_parts(view, stage, s_hold)
    b = idle_pts(view, total)
    hw = convert(hold, hold_space, 'W')

    def extra(p, t):
        p['cape'] = _lerp(hw.get('cape', (0, 0, 0)), (0, 0, 0), min(1.0, t + 0.2))
        p['plume'] = _lerp(hw.get('plume', (0, 0, 0)), (0, 0, 0), min(1.0, t + 0.2))
        p['head'] = _lerp(hold.get('head', (0, 0, 0)), (0, 0, 0), max(0.0, t - 0.1))
        return p
    lim = TWIST_LIMITS if hold_space != 'W' else LIMITS
    poses = search_frames(view, stage, hold, hold_space, rest, 'W', returns, before=[(a, lim, ())],
                          after=[(b, LIMITS, ('hands',))], between=LIMITS, extra=extra)
    for r, p in zip(returns, poses):
        r['pose'] = p


SOFT_LIMITS = dict(LIMITS, head=5.5, torso=5.5, feet=5.5)
# the twisted upper body drawn from the next view round: the library's torsos and necks are cut differently
# in each view, so the torso and the head jump with the view (checks_combo4 'twist'); held to a swing step's
# head / torso 8 px
TWIST_LIMITS = SWING_LIMITS
SPIN_LIMITS = {'head': 8.0, 'torso': 8.0, 'feet': 8.0}
CHAIN_LIMITS = {'head': 4.0, 'torso': 4.0, 'feet': 4.0}      # into a stage's first frame: the sword is free


def _into_stage1_sources(view):
    """(hard, soft): the idle and the guard's hold (<= 4 px), the guard walk's frames (the slow legs:
    batch 2 decision F, placed as well as they go without hurting the others)."""
    import checks as C
    hard = [idle_pts(view, 0.0)] + [C._Pt(f, small=True) for f in B1.frames('guard', view)[:4]]
    soft = [C._Pt(f, small=True) for f in B1.frames('guard_walk', view)]
    return hard, soft


def stage1_ready(view, s_wind):
    """Stage 1's first frame is its wind-up, entered from the idle, the guard and its slow legs (the
    sword is free on an attack's first frame: batch 2 decision 3): how far down the wind-up goes, the
    front foot and the head are chosen so all of those steps stay within head / torso / feet 4 (the slow
    legs 5.5)."""
    hard, soft = _into_stage1_sources(view)
    rest = rest_pose(0.0)
    best = None
    for t in (1.0,):
        base = lerp(rest, S1_WIND, t, view)
        for fl in S1_WIND_FRONT:
            feet = {'R': s_wind['feet']['R'], 'L': (fl, 5, 1, 'swing')}
            for h in ((0, 0, 0), (-0.5, 0, -0.5), (0.5, 0, -0.5), (0, 0, -1), (-1, 0, -1), (0.5, 0, 0), (-0.5, 0, 0)):
                p = dict(base, head=h)
                pr = parts(view, p, feet, 0.0)
                w = max(worst([(s_, pr) for s_ in hard], skip=('hands', 'sword')),
                        worst([(s_, pr) for s_ in soft], skip=('hands', 'sword'), limits=SOFT_LIMITS))
                if best is None or w < best[0] - 1e-9:
                    best = (w, p, feet)
    s_wind['pose'], s_wind['feet'] = best[1], best[2]


def _halfway(hold, rw):
    """The first frame back to the stance: both feet halfway, the back one lifted."""
    h = lerp_feet(hold, rw, 0.5)
    return {'R': h['R'][:2] + (1.0, 'swing'), 'L': hold['L']}


def _swing_between(view, stage, S, i, j, k_in, extra=None):
    """Fill S[i+1 .. j-1] (k_in specs) between keys S[i] and S[j], every step a swing step."""
    a, b = S[i], S[j]
    mids = S[i + 1:j]
    poses = search_frames(view, stage, a['pose'], a['space'], b['pose'], b['space'], mids,
                          before=[(sp_parts(view, stage, a), _step_limits(a, mids[0]), ())],
                          after=[(sp_parts(view, stage, b), _step_limits(mids[-1], b), ())], extra=extra)
    for sp, p in zip(mids, poses):
        sp['pose'] = p


def _step_limits(a, b):
    if a['k'] or b['k']:
        return SPIN_LIMITS
    return TWIST_LIMITS if a['space'] != b['space'] else SWING_LIMITS


# ---- stage 1
S1_FEET = {'wind': {'R': (-6, -5, 0, 'flat'), 'L': (3, 5, 1, 'swing')},
           'rise1': {'R': (-6, -5, 0, 'flat'), 'L': (4, 5, 1, 'swing')},
           'rise': {'R': (-6, -5, 0, 'flat'), 'L': (5.5, 5, 0.5, 'reach')},
           'hit': {'R': (-6, -5, 0, 'flat'), 'L': (7, 5, 0, 'flat')},
           'out': {'R': (-4.5, -5, 0.5, 'swing'), 'L': (7, 5, 0, 'flat')},
           'end': {'R': (-3.5, -5, 0, 'flat'), 'L': (7, 5, 0, 'flat')}}


S1_WIND_FRONT = (3.0, 3.5)                 # the front foot lifting to step (ahead of the anchor, px)


def stage1(view):
    rw = rest_world(view, 6.0)
    S = [spec('f1 壓低', 0, 1, S1_WIND, S1_FEET['wind'], 'R'),
         spec('f2 起揮 1', 2, 3, None, S1_FEET['rise1'], 'R', swing=True),
         spec('f3 起揮 2', 4, 5, None, S1_FEET['rise'], 'R', swing=True),
         spec('f4 接觸', 6, 7, S1_HIT, S1_FEET['hit'], 'L', swing=True),
         spec('f5 揮出', 8, 9, None, S1_FEET['out'], 'L', space='L', swing=True),
         spec('f6 揮完', 10, 11, S1_END, S1_FEET['end'], 'L', space='L', swing=True),
         spec('f7 收招', 12, 17, None, S1_FEET['end'], 'L', space='L'),
         spec('f8 回站姿 1', 18, 21, None, None, 'L'),
         spec('f9 回站姿 2', 22, 25, None, rw, None)]
    stage1_ready(view, S[0])
    _swing_between(view, 1, S, 0, 3, 2)
    _swing_between(view, 1, S, 3, 5, 1)
    S[6]['pose'] = dict(S1_END, head=(0.5, 0, 0), cape=(-4, -6, 4), plume=(-3, -3, 1))
    S[7]['feet'] = _halfway(S1_FEET['end'], rw)
    recovery(view, 1, S[6]['pose'], S[6], S[7:], 6.0, hold_space='L')
    return S


# ---- stage 2
S2_FEET = {'cock': {'R': (-7.5, -5, 0, 'flat'), 'L': (2, 5, 0, 'flat')},
           'sweep1': {'R': (-7.5, -5, 0, 'flat'), 'L': (3, 5, 1, 'swing')},
           'sweep': {'R': (-7.5, -5, 0, 'flat'), 'L': (4.5, 5, 1, 'swing')},
           'hit': {'R': (-7.5, -5, 0, 'flat'), 'L': (7, 5, 0, 'flat')},
           'out': {'R': (-5.5, -5, 0.5, 'swing'), 'L': (7, 5, 0, 'flat')},
           'end': {'R': (-4, -5, 0, 'flat'), 'L': (7, 5, 0, 'flat')}}


def stage2(view):
    rw = rest_world(view, 6.0)
    S = [spec('f1 落劍', 0, 1, S2_COCK, S2_FEET['cock'], 'R', space='L'),
         spec('f2 橫掃 1', 2, 3, None, S2_FEET['sweep1'], 'R', space='L', swing=True),
         spec('f3 橫掃 2', 4, 5, None, S2_FEET['sweep'], 'R', swing=True),
         spec('f4 接觸', 6, 7, S2_HIT, S2_FEET['hit'], 'L', swing=True),
         spec('f5 揮出', 8, 9, None, S2_FEET['out'], 'L', space='R', swing=True),
         spec('f6 揮完', 10, 11, S2_END, S2_FEET['end'], 'L', space='R', swing=True),
         spec('f7 收招', 12, 17, None, S2_FEET['end'], 'L', space='R'),
         spec('f8 回站姿 1', 18, 21, None, None, 'L'),
         spec('f9 回站姿 2', 22, 25, None, rw, None)]
    # the first frame: stage 1's blade let fall to the left side (the sword is free on an attack's first
    # frame, batch 2 decision 3), then the sweep through two in-betweens to the contact
    _swing_between(view, 2, S, 0, 3, 2)
    _swing_between(view, 2, S, 3, 5, 1)
    S[6]['pose'] = dict(S2_END, head=(0, 0, -0.5), cape=(-4, 6, 4), plume=(-3, 4, 1))
    S[7]['feet'] = _halfway(S2_FEET['end'], rw)
    recovery(view, 2, S[6]['pose'], S[6], S[7:], 6.0, hold_space='R')
    return S


# ---- stage 3
S3_FEET = {'sink': {'R': (-9, -5, 0, 'flat'), 'L': (3.5, 5, 0, 'flat')},
           'lift1': {'R': (-8.5, -5, 0.5, 'swing'), 'L': (3.5, 5, 0, 'flat')},
           'lift': {'R': (-7.5, -5, 0.5, 'swing'), 'L': (3.5, 5, 0, 'flat')},
           'hit': {'R': (-6, -5, 0.5, 'swing'), 'L': (3.5, 5, 0, 'flat')},
           'top': {'R': (-3, -5, 0.5, 'toe'), 'L': (3.5, 5, 0, 'flat')},
           'hold': {'R': (-1.5, -5, 0, 'flat'), 'L': (3.5, 5, 0, 'flat')}}


def stage3(view):
    rw = rest_world(view, 6.0)
    S = [spec('f1 沉腰', 0, 2, S3_SINK, S3_FEET['sink'], 'L', space='R'),
         spec('f2 起挑 1', 3, 4, None, S3_FEET['lift1'], 'L', space='R', swing=True),
         spec('f3 起挑 2', 5, 6, None, S3_FEET['lift'], 'L', swing=True),
         spec('f4 接觸', 7, 8, S3_HIT, S3_FEET['hit'], 'L', swing=True),
         spec('f5 挑到頂', 9, 11, S3_TOP, S3_FEET['top'], 'L', swing=True),
         spec('f6 收招', 12, 17, S3_HOLD, S3_FEET['hold'], 'L'),
         spec('f7 回站姿 1', 18, 21, None, None, 'L'),
         spec('f8 回站姿 2', 22, 25, None, None, 'R'),
         spec('f9 回站姿 3', 26, 28, None, rw, None)]
    # the first frame: the waist sinks, the point pressed low (the sword is free on an attack's first
    # frame), held three frames: then the drive up through two in-betweens to the contact
    _swing_between(view, 3, S, 0, 3, 2)
    S[6]['feet'] = _halfway(S3_FEET['hold'], rw)
    S[7]['feet'] = {'R': rw['R'], 'L': lerp_feet(S3_FEET['hold'], rw, 0.5)['L'][:2] + (1.0, 'swing')}
    recovery(view, 3, S3_HOLD, S[5], S[6:], 6.0)
    return S


# ---- stage 4
# stage 3 seen from stage 4's start (6 px on): its top / hold pelvis at -4.5 / -4, feet R -9 / -7.5, L -2.5.
# The spin pivots on the spot (the stance turning round the pelvis); the front foot lands ahead with the
# cut and the body is carried on with the program's 14 px (front / back views can hold the picture back
# only 6 px: FB_SHIFT_MAX), the rest walked in the rise
S4_FEET = {'wind': {'R': (-7, -5, 0, 'flat'), 'L': (-1, 5, 0, 'flat')},
           'turn1': {'R': (-6, -5, 0, 'flat'), 'L': (0, 5, 0, 'flat')},
           'turn2': {'R': (-5, -5, 0.5, 'swing'), 'L': (0.5, 5, 0, 'flat')},
           'end': {'R': (1, -5, 0, 'flat'), 'L': (10.5, 5, 0, 'flat')}}
RISE = [(0.25, 0.0), (0.5, 0.0), (0.75, 0.5), (1.0, 0.5)]     # (back foot, front foot) share of the way to the stance


def _spin_spec(name, first, last, k):
    """A turn frame: its root and feet in the turned body's own space (the body pivots on the spot)."""
    p = dict(SPIN_POSES[k])
    rb = to_body((SPIN_ROOT[k], 0.0), k)
    p['root'] = (rb[0], rb[1], p['root'][2])
    feet = {s_: (v[0] + rb[0], v[1] + rb[1]) + tuple(v[2:]) for s_, v in SPIN_FEET.items()}
    return spec(name, first, last, p, feet, None, k=k, body_feet=True, swing=True)


def _s3_last(view):
    """Stage 3's frames that may be the last one shown before stage 4 starts (the chain on, not the frames
    back to the stance: those chain into the entry), where they show from stage 4's start."""
    import checks as C
    fx, fy = FWD_SCREEN[view]
    return [C._Pt(f, fx * (f.adv - 6.0), fy * (f.adv - 6.0)) for f in frames(3, view)
            if f.last >= CHAIN[3] - 1 and LATE not in f.name]


def start_pose(view, s_next, srcs=None, feet=None):
    """Stage 4's first frame (or its entry from the stance: srcs, feet): the arms and blade the wind-up key's
    (the sword is free on an attack's first frame, batch 2 decision 3); how far the body has come from srcs
    toward the key is searched so the step in keeps head / torso / feet <= 4 and the step into the next
    frame its limits."""
    base = rest_pose(0.0) if srcs is not None else dict(S3_HOLD, root=_add3(S3_HOLD['root'], (-6.0, 0, 0)))
    srcs = _s3_last(view) if srcs is None else srcs
    feet = S4_FEET['wind'] if feet is None else feet
    nxt = sp_parts(view, 4, s_next)
    best = None
    for t in tuple(round(0.3 + 0.05 * i, 2) for i in range(15)):
        p = lerp(base, S4_WIND, t, view)
        p['arms'], p['sword'] = S4_WIND['arms'], S4_WIND['sword']
        pr = parts(view, p, feet, 0.0)
        w = max(worst([(s_, pr) for s_ in srcs], skip=('hands', 'sword'), limits=CHAIN_LIMITS),
                worst([(pr, nxt)], limits=TWIST_LIMITS))
        if best is None or w < best[0] - 1e-9:
            best = (w, p)
    return best[1]


def stage4(view):
    rw = rest_world(view, 14.0)
    S = [spec('f1 落劍', 0, 1, None, S4_FEET['wind'], 'R', swing=True),
         spec('f2 起轉 1', 2, 3, S4_TURN1, S4_FEET['turn1'], 'R', space='L', swing=True),
         spec('f3 起轉 2', 4, 5, S4_TURN2, S4_FEET['turn2'], 'L', space='L', swing=True),
         _spin_spec('f4 接觸', 6, 8, 3),
         _spin_spec('f5 背對', 9, 11, 2),
         _spin_spec('f6 轉身 3', 12, 14, 1),
         spec('f7 揮完', 15, 17, S4_END, S4_FEET['end'], 'R', swing=True),
         spec('f8 收招 1', 18, 24, S4_HOLD1, S4_FEET['end'], 'R'),
         spec('f9 收招 2', 25, 30, S4_HOLD2, S4_FEET['end'], 'R'),
         spec('f10 起身 1', 31, 34, None, None, 'L'),
         spec('f11 起身 2', 35, 38, None, None, 'L'),
         spec('f12 起身 3', 39, 42, None, None, 'R'),
         spec('f13 起身 4', 43, 46, None, None, 'R'),
         spec('f14 回站姿', 47, 50, None, rw, None)]
    # the wind-up: the arms and blade the key's, the body from stage 3's last frames (searched)
    S[0]['pose'] = start_pose(view, S[1])
    # rising: the back foot comes up in two lifted steps while the front holds the weight, then the front
    # foot steps (lifted) and the stance at the program's end (14 px on)
    hf = S4_FEET['end']
    rises = S[9:13]
    prev_t = (0.0, 0.0)
    for r, (tr, tl) in zip(rises, RISE):
        # a foot moving this frame is lifted; one that has arrived (or waits) stands
        fr = lerp_feet(hf, rw, tr)['R'][:2] + ((1.0, 'swing') if tr != prev_t[0] and tr < 1 else (0, 'flat'))
        fl = lerp_feet(hf, rw, tl)['L'][:2] + ((1.0, 'swing') if tl != prev_t[1] else (0, 'flat'))
        r['feet'] = {'R': fr, 'L': fl}
        r['weight'] = 'L' if tr != prev_t[0] else 'R'
        prev_t = (tr, tl)
    stance = rest_pose(14.0)

    def rise_extra(p, t):
        p['cape'], p['plume'] = _lerp((-2, -2, 1), (0, 0, 0), t), _lerp((-2, -1, 0), (0, 0, 0), t)
        p['head'] = _lerp((0, 0, -0.5), (0, 0, 0), t)
        return p
    ret = rises + [S[13]]
    poses = search_frames(view, 4, S4_HOLD2, 'W', stance, 'W', ret, grid=tuple(round(0.15 + 0.05 * i, 2) for i in range(18)),
                          before=[(sp_parts(view, 4, S[8]), LIMITS, ())], after=[(idle_pts(view, 14.0), LIMITS, ('hands',))],
                          between=LIMITS, extra=rise_extra)
    for r, p in zip(ret, poses):
        r['pose'] = p
    return S


STAGES = {1: stage1, 2: stage2, 3: stage3, 4: stage4}


# ---- entries from the stance: with the combo grace a stage often starts from the idle stance (a late
# press), and a press in the previous stage's last recovery frames starts it from nearly the stance too.
# Stages 2-4's first frames come out of the previous follow-through (the earliest chain); from the stance
# they jump. So each has an entry drawn from the stance as well (untwisted): searched between the idle and
# the stage's own frame after its first. The game plays it when the stage starts from the idle (grace) or
# from the previous stage's recovery frames (f6 on), the other one otherwise.
ENTRY = {2: 1, 3: 1, 4: 1}           # how many frames the entry replaces
LATE = '回站姿'                       # a chain from the previous stage's frames with this in the name plays the entry


def entry(stage, view):
    import checks as C
    main = STAGES[stage](view)
    n = ENTRY[stage]
    nxt = main[n]
    rest = rest_pose(0.0)
    fx, fy = FWD_SCREEN[view]
    prev_adv = ATTACK[stage - 1][3]
    # sources: the idle (the grace) and the previous stage's frames back to the stance (回站姿), where
    # they show on this stage's screen; into the entry the sword is free (an attack's first frame, batch 2
    # decision 3), head / torso / feet <= 4
    srcs = [idle_pts(view, 0.0)] + [C._Pt(f, fx * (f.adv - prev_adv), fy * (f.adv - prev_adv))
                                    for f in frames(stage - 1, view) if LATE in f.name]
    b = sp_parts(view, stage, nxt)
    rw = rest_world(view, 0.0)
    if stage == 4:
        # stage 4's entry is its wind-up drawn from the stance: the arms and blade the key's, the body searched
        sp = dict(main[0], name=main[0]['name'] + '（從站姿）', space='W', k=0, body_feet=False,
                  feet=lerp_feet(rw, main[0]['feet'], 0.6))
        sp['pose'] = start_pose(view, main[1], srcs=srcs, feet=sp['feet'])
        return [sp]
    # the next frame's pose, untwisted (a spin frame's pose is the turned body's: the entry goes to the
    # stage's own untwisted first key instead)
    if nxt['k']:
        target, tspace = main[0]['pose'], main[0]['space']
    else:
        target, tspace = nxt['pose'], nxt['space']
    specs = []
    for i in range(n):
        t = (i + 1) / (n + 1)
        sp = dict(main[i])
        sp['name'] = main[i]['name'] + '（從站姿）'
        sp['feet'] = lerp_feet(rw, nxt['feet'] if not nxt['body_feet'] else main[i]['feet'], t)
        sp['space'], sp['k'], sp['body_feet'] = 'W', 0, False
        specs.append(sp)

    def extra(p, t):
        p['head'] = _lerp((0, 0, 0), target.get('head', (0, 0, 0)), min(1.0, t + 0.2))
        return p
    grid = tuple(round(0.1 + 0.025 * i, 3) for i in range(33)) if not nxt['k'] else tuple(round(0.5 + 0.05 * i, 2) for i in range(11))
    poses = search_frames(view, stage, rest, 'W', target, tspace, specs, grid=grid,
                          before=[(s_, CHAIN_LIMITS, ('hands', 'sword')) for s_ in srcs],
                          after=[(b, _step_limits(specs[-1], nxt), ())], between=SWING_LIMITS, extra=extra)
    for sp, p in zip(specs, poses):
        sp['pose'] = p
    return specs


SHEETS = {1: 'attack1', 2: 'attack2', 3: 'attack3', 4: 'attack4'}
TITLES = {1: '輕攻擊第 1 段（右下→左上斜斬）', 2: '輕攻擊第 2 段（左→右橫斬）', 3: '輕攻擊第 3 段（由下往上挑斬）',
          4: '輕攻擊第 4 段（回旋斬：轉身中砍到＋停頓）'}


class Frame:
    def __init__(self, stage, sp, view, adv, f):
        self.stage, self.name, self.first, self.last = stage, sp['name'], sp['first'], sp['last']
        self.view, self.k, self.space = view, sp['k'], sp['space']
        self.draw_view, self.upper_view = f.draw_view, f.upper_view
        self.dur = self.last - self.first + 1
        self.adv, self.weight, self.swing = adv, sp['weight'], sp['swing']
        self.feet_w = sp['feet']
        self.px, self.trace, self.pieces, self.pieces_raw, self.debug = f.px, f.trace, f.pieces, f.pieces_raw, f.debug
        self.pose, self.upper_pose, self.lib_view, self.gy = f.pose, f.upper_pose, f.lib_view, f.gy
        self.spec_pose = sp['pose']

    def screen_offset(self):
        fx, fy = FWD_SCREEN[self.view]
        return fx * self.adv, fy * self.adv


_CACHE = {}
# animation-review §4.5: every blade >= 3:1 against what is behind it. A frame whose blade crosses a lit
# patch (the visor, a pauldron's glint, the plume's light blue) turns the blade by the smallest nudge that
# clears it (batch 2's readable(), on the frame as drawn: a twisted frame's blade lies over the other
# view's pieces)
CONTRAST_MIN = 3.0
NUDGES = [(x, y, z) for k in (0.1, 0.2, 0.3) for (x, y, z) in
          ((k, 0, 0), (-k, 0, 0), (0, k, 0), (0, -k, 0), (0, 0, k), (0, 0, -k))]


def blade_contrast(f):
    import checks as C
    import checks_combo4 as K
    pre = K.Pre(f)
    vals = [v for v, _ in C.blade_contrast(pre, f.px, *pre.canvas_offset()) if v is not None]
    return min(vals) if vals else None


def readable(view, sp, adv):
    """(pose, frame) of a spec, the blade nudged if it does not read against what is behind it."""
    f = render_spec(view, sp['pose'], sp['feet'], adv, sp['space'], sp['k'], sp['body_feet'])
    c = blade_contrast(f)
    if c is None or c >= CONTRAST_MIN:
        return sp['pose'], f
    d0 = PR.vnorm(sp['pose']['sword']['dir'])
    for n in NUDGES:
        p = dict(sp['pose'], sword=dict(sp['pose']['sword'], dir=PR.vnorm(_add3(d0, n))))
        f2 = render_spec(view, p, sp['feet'], adv, sp['space'], sp['k'], sp['body_feet'])
        c2 = blade_contrast(f2)
        if c2 is None or c2 >= CONTRAST_MIN:
            return p, f2
    return sp['pose'], f


def frames(stage, view, entry_frames=False):
    """The stage's frames; entry_frames: its entry from the stance instead (see ENTRY)."""
    key = (stage, view, entry_frames)
    if key in _CACHE:
        return _CACHE[key]
    out = []
    for sp in (entry(stage, view) if entry_frames else STAGES[stage](view)):
        adv = advance_at(stage, sp['first'])
        p, f = readable(view, sp, adv)
        sp = dict(sp, pose=p)
        out.append(Frame(stage, sp, view, adv, f))
    _CACHE[key] = out
    return out
