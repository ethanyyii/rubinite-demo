"""The Boss's hit reactions and the kneel (受擊、跪地), four directions.

User 2026-10-01: the kneel is "right knee on the ground (one knee down), the sword stuck in the
ground, the head looking down". The break (失衡), the execution (被處決), the phase transition
(階段轉場) and death all start from it; rising is the kneel played backwards (boss-veltharis §8.2).
The stagger (短僵直) and the bounce (被彈開) are the two hit reactions.

How the frames are made: the same pose renderer as the four ways of moving (anim_walk), widened:
a state may also lower the hips far (D up to ~45 px: the cloth that reaches the ground folds onto
it), lean the chest by an extra angle (lx, + forward), bow the head (bow, degrees chin-down: the
side views turn the concept's head, the front sinks it behind the gorget, the back behind the
cape's collar), keep the sword planted as the approved standing sprite has it (planted: its own
pixels, fist and forearm, moved with the fist; what goes below the ground is in the ground), rest
the free hand on the raised knee (rest), and kick the cape (ck). A state without these keys draws
exactly what anim_walk draws (checked: verify()).

Directions: down, right, up, left; facing left is built in facing-right space with the sword in
the far hand and mirrored (side.py), as everywhere.
"""
import math
from PIL import Image, ImageDraw
import boss as B
import rig
import gait
import limb
import arm
import side
import carry
import anim_idle
import anim_walk as AW
import sword as swd
import labels

FW, FH, AX, AY = rig.FW, rig.FH, rig.AX, rig.AY
DEPTH = swd.DEPTH
piecewise = AW.piecewise
_frac = AW._frac
GROUND = {'right': 209, 'down': 208, 'up': 208}     # the approved planted sword's lowest row: the ground
FIST_ROW = {'right': 92, 'down': 90, 'up': 90}      # its fist (the grip), final px
LEG_FLOOR = AY + 12                                  # legs: nothing below this (a foot ahead of him is lower)


# ------------------------------------------------------------------ the kneel in numbers
# side model units (gait.py): x forward of the hip joint, z up from the ground, final px
KNEE_Z = 9.5            # the kneeling knee's joint above the ground: the knee plate, drawn, rests on it
                        # (5.5 sank the drawn knee 4 px into the ground; checks_hit measures it)
TUCK_PITCH = -70.0      # the kneeling foot: toes tucked under, the boot nearly upright, toe down
TUCK_Z = 23.0           # its ankle: high enough that the toe just touches the ground (boot_drop)
D_KNEEL = round(gait.HIP_REST - (KNEE_Z + gait.THIGH))    # 41: hips this much lower than standing


def leg(hip_z, knee, ankle, pitch, down=True):
    """A leg from explicit joints (gait.solve's format)."""
    return {'hip': (0.0, hip_z), 'knee': tuple(knee), 'ankle': tuple(ankle), 'pitch': pitch, 'down': down,
            'stretched': False}


def kneel_legs(D=D_KNEEL):
    """Right knee on the ground under the hip, its shin back along the ground, toes tucked;
    left foot flat ahead, its shin upright, its knee up."""
    hip = gait.HIP_REST - D
    kz = KNEE_Z
    kx = -math.sqrt(max(0.0, gait.THIGH ** 2 - (hip - kz) ** 2))
    a = math.asin((TUCK_Z - kz) / gait.SHIN)
    right = leg(hip, (kx, kz), (kx - gait.SHIN * math.cos(a), TUCK_Z), TUCK_PITCH)
    lz = gait.ANKLE_H + gait.SHIN
    lx = math.sqrt(max(0.0, gait.THIGH ** 2 - (lz - hip) ** 2))
    left = leg(hip, (lx, lz), (lx, gait.ANKLE_H), 0.0)
    return right, left


def solve(hip_z, ankle, pitch, down=True, knee_back=False):
    """gait.solve, with the knee behind the hip-ankle line when knee_back (the kneeling leg on
    its way down: the knee goes down in front of the foot that slides back)."""
    L = gait.solve(hip_z, ankle, pitch, down)
    return L


# ------------------------------------------------------------------ the bowed head (side views)
HEAD_PIVOT = (172, 116)          # ref/right.png px: the neck, under the back of the helmet
_heads = {}


def head_side(bow):
    """The side view's head turned `bow` degrees chin-down about the neck, as {(x, y): colour}
    where the approved head is (the pivot stays put). bow 0: the approved head's own pixels."""
    if abs(bow) < 0.5:
        return AW._layers('right')['layers']['head'].pix
    # turned and resampled, the head's gold trim comes out between 84% and 112% of the approved
    # head's depending on the angle: an angle whose head keeps it badly is replaced by the
    # nearest one (1 degree off) that keeps it (animation-review §4.1: detail within 85%..115%)
    key = round(bow)
    for k in (key, key + 1, key - 1, key + 2, key - 2):
        if k and HEAD_GOLD[0] <= _head_gold(k) <= HEAD_GOLD[1]:
            return _render_head(k)
    return _render_head(key)


HEAD_GOLD = (0.88, 1.12)


def _head_gold(k):
    g0 = sum(1 for c in AW._layers('right')['layers']['head'].pix.values() if rig.is_gold(c))
    return sum(1 for c in _render_head(k).values() if rig.is_gold(c)) / g0


def _render_head(key):
    if key not in _heads:
        src = B.ref('right')
        poly = labels.POLY['right']['head'][0]
        m = Image.new('L', src.size, 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        im = Image.new('RGBA', src.size, (0, 0, 0, 0))
        im.paste(src, (0, 0), m)
        lay = rig.Layout('right')
        canvas = Image.new('RGBA', (FW * B.WORK, FH * B.WORK), (0, 0, 0, 0))
        limb._place(canvas, (im.convert('RGBa'), HEAD_PIVOT), lay.local_to_work(HEAD_PIVOT), key, lay.kx)
        _heads[key] = arm._stylize(canvas)
    return _heads[key]


# ------------------------------------------------------------------ helpers
def warp(layer, src, pad=8, down=64, side_=24):
    """rig.warp over the layer's box grown `down` px downwards and `side_` sideways (a layer
    moved far would otherwise be cut where its box ends)."""
    x0, y0, x1, y1 = layer.bbox()
    return rig.warp(layer, src, (x0 - side_, y0 - 8, x1 + side_, y1 + down), pad)


def bottom(layer):
    return max(q[1] for q in layer.pix)


def fold(y, top, low, d, floor, k):
    """Source row for target row y of cloth hanging from `top` down to its lowest row `low`,
    moved down d px. What would go below `floor` folds onto the ground: the part that still
    hangs keeps its length, the rest is squashed into the last rows above the floor, k of its
    length. None below the floor; also returns u (0 .. 1 through the fold band, 0 above it)."""
    if y > floor:
        return None, 0.0
    over = low + d - floor
    if over <= 0:
        return y - d, 0.0
    band = max(1, round(k * over))
    if y <= floor - band:
        return y - d, 0.0
    u = (y - (floor - band)) / band
    s0 = floor - band - d
    return round(s0 + (low - s0) * u), u


def lie(y, top, low, d, floor):
    """Source row for cloth that reaches the ground and lies on it towards the camera (in front
    of a figure seen from the front, behind one seen from behind): below the floor, 0.35 of its
    length. Also returns u (0 .. 1 over the lying part)."""
    over = low + d - floor
    if y <= floor or over <= 0:
        sy = y - d
        return (sy if sy <= low else None), 0.0
    n = max(1, round(DEPTH * over))
    if y > floor + n:
        return None, 1.0
    u = (y - floor) / n
    s0 = floor - d
    return round(s0 + (low - s0) * u), u


# ------------------------------------------------------------------ side views
SWORD_TOP_SIDE = 71


def pose_side(clip, i, far=False):
    """A side-view pose in facing-right space (far: the Boss faces left, mirrored by render())."""
    S = AW._layers('right')
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    s, s1 = clip.at(i), clip.at(i - 1)
    d, d1, b = s['D'], s1['D'], s['b']
    belt = sm['belt']
    kneel = 'pile' in s
    lean_full = math.tan(math.radians(AW.LEAN_DEG))
    lean = lean_full * s['lean'] * b + math.tan(math.radians(s.get('lx', 0.0)))
    tw, tw1 = (-s['tw'], -s1['tw']) if far else (s['tw'], s1['tw'])
    cam = -1 if far else 1

    def seen(L):
        lat = L.get('lat', 0.0)
        if not lat:
            return L, 0.0
        P = gait.solve(L['hip'][1], (L['ankle'][0], L['ankle'][1] - DEPTH * lat * cam), L['pitch'], L['down'])
        return P, lat * cam
    (near_leg, _), (far_leg, _) = (seen(s['legL']), seen(s['legR'])) if far else (seen(s['legR']), seen(s['legL']))

    def chest_dx(sy, t, ln=lean):
        return round(ln * max(0.0, belt - sy)) + round(t * (1 - _frac(sy, belt - 6, belt)))

    sh0 = S['shoulder']
    shoulder = (sh0[0] + chest_dx(sh0[1], tw), sh0[1] + d)
    ride = (chest_dx(AW.PLATE_TOP, tw), d)
    sk = s.get('sk', (0, 0))
    plant = (chest_dx(FIST_ROW['right'], tw) + sk[0], d + sk[1])     # the planted sword rides with the fist
    br = s.get('br', 0)            # breathing: the chest and shoulders rise br px (the head a pose later)
    if br:
        top_b = min(q[1] for q in layers['head'].pix)
        rs, rt = [top_b, sm['chest'], belt], [top_b + d - br, sm['chest'] + d - br, belt + d]

        def body_src(x, y):
            sy = round(piecewise(y, rs, rt))
            return x - chest_dx(sy, tw), sy
        shoulder = (shoulder[0], shoulder[1] - br)
    else:
        body_src = lambda x, y: (x - chest_dx(y - d, tw), y - d)
    floor = AY
    out = []
    if s.get('planted'):
        # the approved sword, fist and forearm: the sword and the fist move with the fist, the
        # forearm between the elbow (on the chest) and the wrist (on the sword). tilt: the tip
        # stays planted and the sword leans with the hand
        if 'tilt_from' in s:
            # stuck in the ground: where it went in (the hips D_KNEEL down, leaning tilt_from);
            # the hand's later moves lean it about where it enters the ground, and the forearm
            # bridges from the chest to the fist on it
            base = round(math.tan(math.radians(s['tilt_from'])) * max(0.0, belt - FIST_ROW['right'])) + sk[0]
            sword = planted_sword('right', layers, (base, D_KNEEL + sk[1]), False)
            sword = lean_about_ground(sword, plant[0] - base)
            sk = (sk[0], D_KNEEL + sk[1] - d)
            plant = (plant[0], d + sk[1])
        else:
            sword = planted_sword('right', layers, plant, s.get('tilt', False))
        xe, xw = (lay.local_to_final((v, 0))[0] for v in anim_idle.FOREARM)

        def fore_src(x, y):
            t = _frac(x, xe, xw)
            return body_src(x - round(sk[0] * t), y - round((sk[1] + br) * t))
        forearm = warp(S['farwrist'], fore_src, pad=16)
        g0 = S['place0']['grip']
        AW.SWORD_DRAWN[('left' if far else 'right', clip.name, i)] = (sword, {'grip': (g0[0] + plant[0], g0[1] + plant[1])})
        hand = None
    else:
        place0 = S['place0']
        g0 = place0['grip']
        stand = dict(place0, grip=(g0[0] + plant[0], g0[1] + plant[1]))
        sword, place = sword_pixels('right', S, b, ride, far, stand, s)
        AW.SWORD_DRAWN[('left' if far else 'right', clip.name, i)] = (sword, place)
        g1 = carry.fist_screen('right', far)
        e1 = (g1[0] + AW.SIDE_ELBOW[0], g1[1] + AW.SIDE_ELBOW[1])
        if b >= 1.0 and not s.get('grip3'):
            J, by = arm.pose(sh0, e1, g1), ride
        else:
            e0 = lay.local_to_final(AW.ELBOW0)
            e0 = (e0[0] + chest_dx(e0[1], tw), e0[1] + d)
            want = AW._lerp(e0, (e1[0] + ride[0], e1[1] + ride[1]), b)
            if 'elbow' in s:
                want = (place['grip'][0] + s['elbow'][0], place['grip'][1] + s['elbow'][1])
            elbow = AW.reach(shoulder, want, place['grip'])
            J, by = arm.pose(shoulder, elbow, place['grip']), (0, 0)
        AW.ARM_JOINTS[('left' if far else 'right', clip.name, i)] = J
        if far:
            hand = AW._moved(arm.near(arm.render(J, (FW, FH), parts=('fist',))), by)
        else:
            upper = AW._moved(arm.near(arm.render(J, (FW, FH), parts=('upper',))), by)
            hand = AW._moved(arm.near(arm.render(J, (FW, FH), parts=('fore', 'fist'))), by)

    if far:
        if s.get('planted'):
            out.extend([sword, forearm])
        else:
            out.extend([sword, hand])
    # cape: top on the shoulders; trails behind when he walks forward; a kick (ck) swings the
    # hem; kneeling, what reaches the ground folds onto it and spreads out behind him
    drift = 2.0 * AW.TRAIL_OF[s['kind']]
    ck = s.get('ck', 0.0)

    def trail(t):
        return -round(t ** 1.5 * (drift + 1.5 * math.sin(4 * math.pi * s['p'] - 1.0 - 1.5 * t)) * s['amp']) \
            + round(ck * t ** 1.5)
    if kneel:
        cape = layers['cape']
        top, low = sm['cape_top'], bottom(cape)
        tdx = chest_dx(top + 8, tw)

        cf, ph = s.get('cf', 0.0), s.get('ph', 0.0)
        lift = round(CAPE_LIFT * cf)

        def cape_src(x, y):
            # a flaring cape (cf) is blown back and lifted off the ground: its rows from the
            # top down are shown higher, more the further down they are
            yy = y + round(lift * _frac(y - d, top, low))
            sy, u = fold(yy, top, low, d, floor, s['pile'] * (1 - cf))
            if sy is None:
                return None
            t = _frac(sy, top, low)
            sy += round(br * (1 - t))
            fl = round(cf * (CAPE_BACK * t ** 1.3 + CAPE_FLAP * t * math.sin(2 * math.pi * (ph - 0.8 * t))))
            return x - round(tdx * (1 - t)) - trail(t) + round(s['spread'] * u * (1 - cf)) + fl, sy
        out.append(warp(cape, cape_src, pad=40))
    else:
        out.append(rig.warp(layers['cape'], AW.cape_src(sm, d, AW._hem(clip, i), chest_dx(sm['cape_top'] + 8, tw), trail)))

    stand_legs = s.get('stand_legs', False)
    if not stand_legs:
        # between the legs, then the far leg
        out.append(warp(S['backdrop'], lambda x, y: (x, y - d) if y <= floor else None))
        out.append({(x, y - AW.FAR_UP): c for (x, y), c in limb.darken(limb.leg_pixels(far_leg)).items()})
    ht, hh = sm['hang_top'], sm['hang_hem']
    sw = round(1.2 * math.sin(4 * math.pi * s1['p']) * s1['amp'])
    if kneel:
        cloth = layers['cloth']
        low = bottom(cloth)

        def cloth_src(x, y):
            sy, u = fold(y, ht, low, d, floor, s['pile'])
            return None if sy is None else (x - round(sw * _frac(sy, ht, hh)), sy)
        out.append(warp(cloth, cloth_src))
    else:
        def cloth_src(x, y):
            sy = round(piecewise(y, [ht, hh], [ht + d, hh + d1]))
            return x - round(sw * _frac(sy, ht, hh)), sy
        out.append(rig.warp(layers['cloth'], cloth_src))
    # standing still (the stagger from the standing pose): the approved legs, untouched
    out.append(layers['leg'].all() if stand_legs else limb.leg_pixels(near_leg))

    out.append(warp(layers['body'], body_src, pad=16))
    pauldron = warp(S['pauldron'], body_src, pad=16)
    head = side_head(S, s, s1, chest_dx, far)
    if far:
        out.extend([free_arm_side(S, s, shoulder, sh0, near_leg), pauldron, head])
    elif s.get('planted'):
        out.extend([pauldron, forearm, head, sword])
    else:
        out.extend([upper, pauldron, head, sword])
        if b >= carry.ON_SHOULDER:
            out.append({q: c for q, c in pauldron.items() if q in sword and q not in head})
        out.append(hand)
    return AW._finish('right', out)


HEAD_LAG = 2      # px: the head follows the chest a pose late, but never more than this behind it
                  # (the walk moves 1-2 px a pose; the body drops up to 14 px a pose going down)


def lagged(now, before):
    return now - max(-HEAD_LAG, min(HEAD_LAG, now - before))


def side_head(S, s, s1, chest_dx, far):
    """The head follows the chest a pose late; bowed (s1['bow']) it turns about the neck."""
    lay, sm = S['lay'], S['sm']
    d1 = lagged(s['D'], s1['D'] - s1.get('br', 0))
    tw1 = -s1['tw'] if far else s1['tw']
    hd = s1.get('hd', (0, 0))
    bow = s1.get('bow', 0.0)
    if abs(bow) < 0.5:
        return warp(S['layers']['head'], lambda x, y: (x - chest_dx(y - d1, tw1) - hd[0], y - d1 - hd[1]), pad=16)
    pv = lay.local_to_final(HEAD_PIVOT)
    dx, dy = chest_dx(pv[1], tw1) + hd[0], d1 + hd[1]
    return {(x + dx, y + dy): c for (x, y), c in head_side(bow).items()}


CAPE_LIFT = 18      # px a fully flaring cape's hem lifts (the transition: the flames surge)
CAPE_BACK = 22      # side views: px it is blown back at the hem
CAPE_FLAP = 4       # px of the flap travelling down it
CAPE_FAN = 0.35     # front, back: how much wider it spreads at the hem
REST_HAND = (2.0, -7.0)      # side views: the resting fist from the near knee joint (final px; on the knee cap)


def free_arm_side(S, s, shoulder, sh0, near_leg):
    """Facing left: the near (left) arm, hanging and swinging with the walk, or (rest) its hand
    on the raised knee."""
    fa, J = S['free_arm'], S['free_joints']
    mx, my = round(shoulder[0] - sh0[0]), round(shoulder[1] - sh0[1])
    r = s.get('rest', 0.0)
    if r <= 0.0:
        swing = round(AW.SWING_SIDE * s['arm'])
        pix = {(x + mx, y + my): c for (x, y), c in fa.pix.items()}
        sh = (J['shoulder'][0] + mx, J['shoulder'][1] + my)
        hd = (J['hand'][0] + mx, J['hand'][1] + my)
        return AW.shear_to(pix, sh, hd, (swing, 0))
    kj = limb.joints_work(near_leg)['knee']
    knee = (kj[0] / B.WORK, kj[1] / B.WORK)
    hand1 = (knee[0] + REST_HAND[0], knee[1] + REST_HAND[1])
    sh = (J['shoulder'][0] + mx, J['shoulder'][1] + my)
    hand0 = (J['hand'][0] + mx, J['hand'][1] + my)
    hand = AW._lerp(hand0, hand1, r)
    elbow0 = (J['elbow'][0] + mx, J['elbow'][1] + my)
    # the elbow bends back and out as the hand comes forward onto the knee
    elbow = AW.reach(sh, (elbow0[0] - 2 * r, elbow0[1] + 1 * r), hand)
    return arm.near(arm.render(arm.pose(sh, elbow, hand), (FW, FH)))


def planted_sword(direction, layers, plant, tilt):
    """The approved planted sword (with its fist) moved with the fist by `plant`; below the
    ground it is in the ground. tilt: its tip stays where it is planted, the sword leans with
    the hand (sheared, no resampling)."""
    pix = layers['sword'].pix
    g = GROUND[direction]
    if tilt:
        view = rig.VIEW_OF[direction]
        st = swd.standing(view, rig.Layout(view))
        tip = swd.tip_of(view, st)
        return AW.shear_to(pix, tip, st['grip'], plant)
    return {(x + plant[0], y + plant[1]): c for (x, y), c in pix.items() if y + plant[1] <= g}


def lean_about_ground(pix, dx):
    """A planted sword leaned so that its top moves dx px sideways while the row at the ground
    stays (sheared row by row, no resampling)."""
    if not dx or not pix:
        return pix
    y0 = min(q[1] for q in pix)
    g = max(q[1] for q in pix)
    return {(x + round(dx * (g - y) / (g - y0)), y): c for (x, y), c in pix.items()}


def sword_pixels(view, S, b, ride, far, stand, s):
    """The sword in the hand at blend b (anim_walk.sword_pixels), its standing end at `stand`
    (the planted sword where this pose has the fist); the fist moved by s['grip3'] (F, R, U px)
    if given. Below the ground it is in the ground."""
    g3 = s.get('grip3')
    if b >= 1.0 and not g3:
        return AW.sword_pixels(S, b, ride, far)
    place = carry.place(view, b, stand, far, ride)
    if g3:
        m = carry.move_screen(view, g3, far)
        place = dict(place, grip=(place['grip'][0] + m[0], place['grip'][1] + m[1]))
    if 'axis3' in s:
        k = math.hypot(*stand['axis'])
        a, w = s['axis3']
        A = tuple(c * k for c in swd.project_vec(view, a, far))
        W = tuple(c * k / swd.FLAT_SEEN for c in swd.project_vec(view, w, far))
        hand = stand['axis'][0] * stand['width'][1] - stand['axis'][1] * stand['width'][0]
        if (A[0] * W[1] - A[1] * W[0]) * hand < 0:
            W = (-W[0], -W[1])
        place = dict(place, axis=A, width=W)
    pix = swd.sword_image(view, place, AW.BIG, source='bare', origin=(-AW.EXT, -AW.EXT))
    g = GROUND['right' if view == 'right' else ('down' if view == 'front' else 'up')]
    if s.get('sink'):
        pix = {q: c for q, c in pix.items() if q[1] <= g}
    return pix, place


# ------------------------------------------------------------------ front and back views
def boot_low(L, sign):
    """The lowest screen offset of a boot (heel, toe) in the front (sign +1) or back (-1) view,
    relative to a flat foot under the hip: height plus DEPTH of the forward distance."""
    pts = [gait.rot((gait.HEEL, -gait.ANKLE_H), L['pitch']), gait.rot((gait.BALL + 4, -gait.ANKLE_H), L['pitch'])]
    ys = [-(L['ankle'][1] + z) + sign * DEPTH * (L['ankle'][0] + x) for x, z in pts]
    ys0 = [gait.ANKLE_H - gait.ANKLE_H + sign * DEPTH * x for x in (gait.HEEL, gait.BALL + 4)]
    return max(ys) - max(ys0)


def _leg_front_k(layer, lay, L, d, hip_dx, foot_dx, marks):
    """anim_walk._leg_front_src for the kneel: rows between hip, knee, ankle, sole; a shin that
    folds back behind the knee (the kneeling leg's, going away from the camera) is hidden, and
    a knee on the ground stays on it."""
    dk, _ = AW.leg_deltas(L, +1)
    da = boot_low(L, +1)
    hip, knee, ankle = (None if v is None else lay.local_to_final((0, v))[1] for v in marks)
    sole = AY
    cut = None
    if hip is None:
        src, tgt = [knee, ankle, sole], [knee + dk, ankle + da, sole + da]
        top = tgt[0] - (knee - min(q[1] for q in layer.pix))
    else:
        src, tgt = [hip, knee, ankle, sole], [hip + d, knee + dk, ankle + da, sole + da]
        top = tgt[0]
        if tgt[2] <= tgt[1] + 2:                 # the ankle above the knee on screen: the shin is behind it
            src, tgt, cut = src[:2], tgt[:2], knee
    floor = AY + 1 if cut is not None else LEG_FLOOR

    def f(x, y):
        if y > floor:
            return None
        sy = round(piecewise(y, src, tgt))
        if cut is not None and sy > cut:
            return None
        dx = round(hip_dx + (foot_dx - hip_dx) * _frac(y, top, tgt[-1]))
        return x - dx, sy
    if cut is None:
        return [f]

    # the foot behind the bent knee (the shin is hidden behind it, the boot shows below the knee
    # until the knee is on the ground and covers it): the boot's rows, its lowest point where
    # the model has it, drawn behind the thigh and knee
    def boot(x, y):
        sy = y - round(da)
        if not ankle <= sy <= sole or y > AY + 1:
            return None
        return x - round(foot_dx), sy
    return [boot, f]


def leg_front(layer, lay, L, d, hip_dx, foot_dx, marks, own=False):
    """The pieces of a front-view leg (behind first) as one {(x, y): colour}. own: only the
    leg's own pixels (not the shin it has under the drape)."""
    src = rig.Layer(layer.name, layer.pix) if own else layer
    return rig.composite([warp(src, f, pad=16) for f in _leg_front_k(layer, lay, L, d, hip_dx, foot_dx, marks)])


def _free_front(free, d, k, cx, arm_extra, r):
    """The front view's free arm: hanging (anim_walk) or (rest) its hand on the raised knee: the
    forearm comes towards the camera (short on screen) and in over the knee."""
    fb = free.bbox()
    if r <= 0.0:
        return rig.warp(free, lambda x, y: (x - cx, round(piecewise(y, [fb[1], fb[3] - 1],
                                                                    [fb[1] + d + k, fb[3] - 1 + d + k + arm_extra]))),
                        pad=16) if d < 16 else warp(free, lambda x, y: (x - cx, round(piecewise(
                            y, [fb[1], fb[3] - 1], [fb[1] + d + k, fb[3] - 1 + d + k + arm_extra]))), pad=16)
    e0, w0 = FREE_FRONT['elbow'], FREE_FRONT['wrist']
    e1 = e0 + d + k
    fore = round((w0 - e0) * (1 - r) + FREE_FRONT['fore'] * r)
    inward = FREE_FRONT['inward'] * r

    def src(x, y):
        sy = round(piecewise(y, [fb[1], e0, w0, fb[3] - 1], [fb[1] + d + k, e1, e1 + fore, e1 + fore + fb[3] - 1 - w0]))
        t = _frac(sy, e0, w0)
        return x - cx + round(inward * t), sy
    return warp(free, src, pad=16)


_fc = {}


def _front_cape():
    """The front view's cape for poses with the planted sword or kneeling: anim_walk's, without
    the fill it adds between the boots (pixels the approved sprite does not have there; it keeps
    the fill behind where the sword stood, which shows when the sword goes down)."""
    if not _fc:
        L = AW._layers('down')['layers']['cape']
        appr = rig.pixels(rig.standing()['down'])
        sword = set(AW._layers('down')['layers']['sword'].pix)
        _fc['cape'] = rig.Layer('cape', {q: c for q, c in L.pix.items() if q in appr or q in sword}, L.under)
    return _fc['cape']


SWORD_ARM = {'x': 110, 'rows': (84, 100)}    # front view, final px: the approved sword arm in the body layer
RAISED_KNEE = 10.0       # front view: a left knee this far ahead of the hip comes in front of the hip armour
# the front view's free arm resting on the knee (rows of the approved arm, final px)
FREE_FRONT = {'elbow': 112, 'wrist': 127, 'fore': 3, 'inward': -5}
FREE_BACK_ELBOW = 113          # back view: below this the forearm reaches forward, out of sight
HEAD_SINK = {'down': 0.25, 'up': 0.2}    # px the head sinks per degree of bow (front, back)


def front_back(direction, clip, i):
    sign = 1 if direction == 'down' else -1
    S = AW._layers(direction)
    layers, lay, sm = S['layers'], S['lay'], S['sm']
    s, s1 = clip.at(i), clip.at(i - 1)
    d, d1, b = s['D'], s1['D'], s['b']
    kind = s['kind']
    kneel = 'pile' in s
    strafe = kind.startswith('strafe')
    rows_lean = AW.LEAN_ROWS * b * s['lean'] + s.get('lx', 0.0) * AW.LEAN_ROWS / AW.LEAN_DEG
    k = sign * round(rows_lean)
    rows_lean1 = AW.LEAN_ROWS * s1['b'] * s1['lean'] + s1.get('lx', 0.0) * AW.LEAN_ROWS / AW.LEAN_DEG
    k1 = sign * round(rows_lean1)
    hipx = -sign * s['sw']
    cx, hx = -sign * s['sw1'], -sign * s1['sw1']
    belt, chest = sm['belt'], sm['chest']
    arm_extra = sign * round(DEPTH * AW.ARM_SWING * s['arm'])
    drift = (sign if kind == 'strafe_r' else -sign) * 2.0 if strafe else 0.0
    ck = s.get('ck', 0.0)
    floor = AY

    def trail(t):
        j = clip.at(i - 2 - round(2 * t))
        return round(t ** 1.5 * (2.5 * -sign * math.sin(2 * math.pi * (j['p'] - 0.05)) + drift
                                 + (0.8 * math.sin(4 * math.pi * j['p']) if strafe else 0.0)) * j['amp'])
    flare, ph = s.get('cf', 0.0), s.get('ph', 0.0)
    lift = round(CAPE_LIFT * flare)
    br = s.get('br', 0)
    cape_layer = layers['cape']
    if direction == 'down' and (kneel or s.get('planted')):
        cape_layer = _front_cape()
    if kneel:
        top_c, low_c = sm['cape_top'], bottom(cape_layer)
        if direction == 'down':
            # behind him: what reaches the ground folds onto it behind him (higher on screen)
            # and spreads out to the sides
            cfl = floor - s.get('cape_up', 4)

            def cape_src(x, y):
                # the hips carry it (d); the lean moves its top only (k), the hem stays
                yy = y + round(lift * _frac(y - d - k, top_c, low_c))
                sy, u = fold(yy, top_c, low_c, d, cfl, s['pile'] * (1 - flare))
                if sy is None:
                    return None
                t = _frac(sy, top_c, low_c)
                sy += round(br * (1 - t)) - round(k * (1 - t))
                fan = 1 + s.get('fan', 0.25) * u * (1 - flare) + CAPE_FAN * flare * t
                fl = round(flare * CAPE_FLAP * 0.5 * t * math.sin(2 * math.pi * (ph - 0.8 * t)))
                return round(AX + (x - cx * (1 - t) - trail(t) - fl - AX) / fan), sy
        else:
            # behind him, seen from behind: it lies on the ground towards the camera (lower)
            def cape_src(x, y):
                yy = y + round(lift * _frac(y - d - k, top_c, low_c))
                sy, u = lie(yy, top_c, low_c, d, floor) if flare < 0.5 else fold(yy, top_c, low_c, d, floor, 0.25)
                if sy is None:
                    return None
                t = _frac(sy, top_c, low_c)
                sy += round(br * (1 - t)) - round(k * (1 - t))
                fan = 1 + s.get('fan', 0.25) * u * (1 - flare) + CAPE_FAN * flare * t
                fl = round(flare * CAPE_FLAP * 0.5 * t * math.sin(2 * math.pi * (ph - 0.8 * t)))
                return round(AX + (x - cx * (1 - t) - trail(t) - fl - AX) / fan), sy
        cape = warp(cape_layer, cape_src, pad=24)
    else:
        def trail_k(t):
            return trail(t) + round(ck * t ** 1.5)
        cape = rig.warp(cape_layer, AW.cape_src(sm, d + k, AW._hem(clip, i), cx, trail_k), pad=16)

    sk = s.get('sk', (0, 0))
    top = min(q[1] for q in layers['head'].pix)
    br = s.get('br', 0)
    rows_src, rows_tgt = [top, chest, belt], [top + d + k, chest + d + k, belt + d]
    fist_row = FIST_ROW[direction]
    plant = (cx + sk[0], round(piecewise(fist_row, rows_tgt, rows_src)) - fist_row + sk[1])
    arm_gap = 0
    if s.get('planted') and 'tilt_from' in s:
        # stuck in the ground where it went in (the hips D_KNEEL down, leaning tilt_from): it
        # stays; the sword arm stretches from the shoulder to the fist on it (front view)
        kt = sign * round(s['tilt_from'] * AW.LEAN_ROWS / AW.LEAN_DEG)
        rt = [top + D_KNEEL + kt, chest + D_KNEEL + kt, belt + D_KNEEL]
        py = round(piecewise(fist_row, rt, rows_src)) - fist_row + sk[1]
        arm_gap = py - plant[1]
        plant = (plant[0], py)
    if br:
        # breathing: the chest and shoulders rise; the planted sword (and its fist) do not
        rows_tgt = [top + d + k - br, chest + d + k - br, belt + d]
        arm_gap += br
    if s.get('planted'):
        sword = planted_sword(direction, layers, plant, s.get('tilt', False))
        g0 = S['place0']['grip']
        place = {'grip': (g0[0] + plant[0], g0[1] + plant[1])}
    else:
        ride = (cx, d + k)
        place0 = S['place0']
        g0 = place0['grip']
        stand = dict(place0, grip=(g0[0] + plant[0], g0[1] + plant[1]))
        sword, place = sword_pixels('front' if direction == 'down' else 'back', S, b, ride, False, stand, s)
        hilt, blade = carry.split(sword, place)
    AW.SWORD_DRAWN[(direction, clip.name, i)] = (sword, place)
    bow1 = s1.get('bow', 0.0)
    hd = s1.get('hd', (0, 0))
    sink = round(HEAD_SINK[direction] * max(0.0, bow1)) - round(0.15 * min(0.0, bow1))
    br1 = s1.get('br', 0)
    hy = lagged(d + k, d1 + k1 - br1)
    head = warp(layers['head'], lambda x, y: (x - hx - hd[0], y - hy - sink - hd[1]), pad=16)

    def body_src(x, y, arm=True):
        sy = piecewise(y, rows_src, rows_tgt)
        if arm and arm_gap and direction == 'down' and x <= SWORD_ARM['x']:
            # the sword arm, from under the shoulder plate down to the elbow behind the fist,
            # goes from the chest's move to the fist's
            for _ in range(3):
                sy = piecewise(y - _frac(sy, *SWORD_ARM['rows']) * arm_gap, rows_src, rows_tgt)
        sy = round(sy)
        t = 1 - _frac(sy, belt - 6, belt)
        return x - round(hipx + (cx - hipx) * t), sy

    out = []
    LEGS.clear()
    if direction == 'down':
        out.append(cape)
        back = (not s.get('planted')) and carry.blade_back(b)
        if back:
            out.append(blade)
        # the sidestep's legs swing sideways: drawn from the concept (fleg) as in the walk; once
        # a falling Boss has them back under him, rows of the approved legs as for the kneel
        sideways = strafe and (not kneel or max(abs(s['legR'].get('lat', 0.0)), abs(s['legL'].get('lat', 0.0))) >= 0.5)
        raised = kneel and not sideways and s['legL']['knee'][0] > RAISED_KNEE
        if sideways:
            import fleg
            right = fleg.leg(s['legR'], 'R', d, hipx, lay)
            left = fleg.leg(s['legL'], 'L', d, hipx, lay)
            out.extend([right, left] if kind == 'strafe_r' else [left, right])
            LEGS.extend([right, left])
        elif kneel:
            out.append(leg_front(layers['leg_l'], lay, s['legR'], d, hipx, s['inR'], AW.FRONT_LEG['leg_l']))
            LEGS.append(out[-1])
            if not raised:
                out.append(leg_front(layers['leg_r'], lay, s['legL'], d, hipx, -s['inL'], AW.FRONT_LEG['leg_r']))
                LEGS.append(out[-1])
        else:
            out.append(rig.warp(layers['leg_l'], AW._leg_front_src(layers['leg_l'], lay, s['legR'], d, hipx, s['inR'],
                                                                   AW.FRONT_LEG['leg_l']), pad=16))
            out.append(rig.warp(layers['leg_r'], AW._leg_front_src(layers['leg_r'], lay, s['legL'], d, hipx, -s['inL'],
                                                                   AW.FRONT_LEG['leg_r']), pad=16))
        if kneel:
            low_d = bottom(layers['drape'])

            def drape_src(x, y):
                sy, u = lie(y, top_c, low_d, d, floor)
                if sy is None:
                    return None
                t = _frac(sy, top_c, low_d)
                sy -= round(k * (1 - t))
                return x - round(cx * (1 - t)) - trail(t), sy
            out.append(warp(layers['drape'], drape_src, pad=16))
        else:
            out.append(rig.warp(layers['drape'], AW.cape_src(sm, d + k, AW._hem(clip, i), cx, trail), pad=16))
        body = warp(layers['body'], body_src, pad=16)
        out.append(body)
        if kneel and raised:
            # his left knee comes up towards the camera at the hips' height: in front of the hip
            # armour and the drape (its own pixels: the shin it has under the drape stays there)
            out.append(leg_front(layers['leg_r'], lay, s['legL'], d, hipx + s.get('kneeL', 0), -s['inL'],
                                 AW.FRONT_LEG['leg_r'], own=True))
            LEGS.append(out[-1])
        ht, hh = sm['hang_top'], sm['hang_hem']
        for name, late, amp in (('chain', 4, 1.3), ('tabard', 3, 1.0)):
            hemx = -sign * clip.at(i - late)['sw'] * amp
            if kneel:
                low_h = bottom(layers[name])

                def hang_src(x, y, hemx=hemx, low_h=low_h):
                    sy, u = lie(y, ht, low_h, d, floor)
                    if sy is None:
                        return None
                    t = _frac(sy, ht, hh)
                    return x - round(hipx + (hemx - hipx) * t), sy
                out.append(warp(layers[name], hang_src))
            else:
                def hang_src(x, y, hemx=hemx):
                    t = _frac(y - d, ht, hh)
                    return x - round(hipx + (hemx - hipx) * t), y - d
                out.append(rig.warp(layers[name], hang_src))
        out.append(_free_front(layers['arm'], d - br, k, cx, arm_extra, s.get('rest', 0.0)))
        out.append(warp(S['pauldron'], lambda x, y: body_src(x, y, False), pad=16))
        if bow1 > 0:
            # bowed: the chin goes behind the gorget
            mine = set(body)
            head = {q: c for q, c in head.items() if q not in mine or q not in layers['body'].pix and
                    body_src(*q) not in layers['body'].pix}
        out.append(head)
        if s.get('planted'):
            out.append(sword)
            return AW._finish(direction, out)
        if not back:
            out.append(blade)
        g1 = carry.fist_screen('front')
        e1 = (g1[0] + AW.FRONT_ELBOW[0], g1[1] + AW.FRONT_ELBOW[1])
        sh0 = S['shoulder']
        if b >= 1.0 and not s.get('grip3'):
            J, by = arm.pose(sh0, e1, g1), ride
        else:
            e0 = (AW.FRONT_ELBOW0[0] + cx, AW.FRONT_ELBOW0[1] + d + k)
            sh = (sh0[0] + cx, sh0[1] + d + k)
            want = AW._lerp(e0, (e1[0] + ride[0], e1[1] + ride[1]), b)
            if 'elbow_front' in s:
                want = (place['grip'][0] + s['elbow_front'][0], place['grip'][1] + s['elbow_front'][1])
            J = arm.pose(sh, AW.reach(sh, want, place['grip']), place['grip'])
            by = (0, 0)
        AW.ARM_JOINTS[('down', clip.name, i)] = J
        out.append(AW._moved(arm.near(arm.render(J, (FW, FH), parts=('upper', 'fore'))), by))
        out.append(hilt)
        out.append(AW._moved(arm.near(arm.render(J, (FW, FH), parts=('fist',))), by))
    else:
        back = (not s.get('planted')) and carry.blade_back(b)
        if s.get('planted'):
            out.append(sword)
        else:
            out.append(hilt)
            if b >= 1.0 and not s.get('grip3'):
                if 'back' not in AW._fists:
                    AW._fists['back'] = arm.fist_only(carry.fist_screen('back'), (0.0, -1.0), (FW, FH))
                out.append(AW._moved(AW._fists['back'], ride))
            else:
                out.append(arm.fist_only(place['grip'], (0.0, -1.0), (FW, FH)))
            if not back:
                out.append(blade)
        boots = [('leg_l', s['legL'], s['inL']), ('leg_r', s['legR'], -s['inR'])]
        if kind == 'strafe_l':
            boots.reverse()
        for name, L, inward in boots:
            if kneel:
                da = round(boot_low(L, -1))
            else:
                da = round(AW.leg_deltas(L, -1)[1])
            dx = inward + round(L.get('lat', 0.0))
            out.append(warp(layers[name], lambda x, y, da=da, dx=dx: (x - dx, y - da), pad=30))
            LEGS.append(out[-1])
        if kneel:
            # the kneeling (right) foot, toes tucked, is behind the knee on the ground (towards the
            # camera): the hanging cape hides its top, its heel and sole show over the cape lying
            # on the ground
            boot_r = out.pop()
            out.append(head_back_sink(head, cape, bow1, layers))
            out.append({q: c for q, c in cape.items() if q[1] > floor})
            out.append(boot_r)
            out.append({q: c for q, c in cape.items() if q[1] <= floor})
        else:
            out.append(head_back_sink(head, cape, bow1, layers))
            out.append(cape)
        free = S['free']
        fb = free.bbox()
        r = s.get('rest', 0.0)
        if r > 0:
            ce = FREE_BACK_ELBOW + round((fb[3] - FREE_BACK_ELBOW) * (1 - r))

            def free_src(x, y):
                sy = round(piecewise(y, [fb[1], fb[3] - 1], [fb[1] + d - br + k, fb[3] - 1 + d - br + k + arm_extra]))
                return None if sy > ce else (x - cx, sy)
            out.append(warp(free, free_src, pad=16))
        else:
            out.append(warp(free, lambda x, y: (x - cx, round(piecewise(y, [fb[1], fb[3] - 1],
                                                                        [fb[1] + d - br + k, fb[3] - 1 + d - br + k + arm_extra]))),
                            pad=16))
        out.append(warp(layers['arm'], lambda x, y: (x - cx, y - d - k + br) if x - cx >= AX else None, pad=16))
        if back:
            out.append(blade)
        if not bow1 > 0:
            out.append(head)
    return AW._finish(direction, out)


LEGS = []          # the leg pieces the last front / back pose drew (legs_only() reads them)


def legs_only(direction, clip, i):
    """Just the legs of a front / back pose (animation-review §5: look at the legs alone)."""
    front_back(direction, clip, i)
    return rig.composite(list(LEGS))


def head_back_sink(head, cape, bow, layers):
    """Back view: a bowed head goes down in front of the cape's collar (the collar covers it):
    drawn under the cape. Not bowed: nothing here (the head is drawn on top as usual)."""
    return head if bow > 0 else {}


# ------------------------------------------------------------------ clips -> frames
def render(direction, clip):
    if direction == 'left':
        return [side.mirror(pose_side(clip, i, far=True)) for i in range(len(clip))]
    if direction == 'right':
        return [pose_side(clip, i) for i in range(len(clip))]
    return [front_back(direction, clip, i) for i in range(len(clip))]


def verify(n=3):
    """The renderer draws exactly what anim_walk draws for the walk's own poses, and exactly the
    approved standing sprites for the planted standing pose. Returns {name: pixels that differ}."""
    out = {}
    for kind in AW.KINDS:
        clip = AW.walk_clip(kind)
        for d in rig.DIRS:
            ref = AW.frames(d, kind)
            mine = render(d, AW.Clip(clip.name, clip.states[:n], clip.before))
            out[f'{kind} {d}'] = sum(len(set(a.items()) ^ set(b.items())) for a, b in zip(ref, mine))
    stand = AW.Clip('stand', [STAND], lambda k: STAND)
    for d in rig.DIRS:
        out[f'stand {d}'] = len(set(render(d, stand)[0].items()) ^ set(rig.pixels(rig.standing()[d]).items()))
    return out


STAND = dict(AW.STAND, planted=True, stand_legs=True)


# front view: the kneel's knees apart (a wide base reads as kneeling, not as a short man standing)
SPLAY_KNEE = 8           # px the raised left knee is out to his left (screen right)
SPLAY_FOOT = 10          # ... and its foot
SPLAY_R = -3             # the kneeling right knee, out to his right (screen left)


# The sword goes in with the hand as he goes down, D_KNEEL px deep as the knee lands (the hips
# overshoot 2 px more: the sword does not go with them); from then on it is stuck where it went
# in: the hand's later moves lean it about where it enters the ground (tilt_from), the sword
# arm bridges the difference, and it does not come back up until he rises
KNEEL_SWORD_LEAN = 10.0


def kneel_state(**kw):
    R, L = kneel_legs()
    st = dict(AW.STAND, D=D_KNEEL, legR=R, legL=L, planted=True, lx=8.0, bow=24.0, pile=0.25, spread=-8,
              fan=0.25, cape_up=4, inR=SPLAY_R, inL=-SPLAY_FOOT, kneeL=SPLAY_KNEE, rest=1.0,
              tilt_from=KNEEL_SWORD_LEAN)
    st.update(kw)
    return st


def still(st, n=1, name='still'):
    """A clip of one pose held (what came before it is the same pose)."""
    return AW.Clip(name, [st] * n, lambda k: st)


# ------------------------------------------------------------------ the clips
def _lerp(a, b, t):
    return a + (b - a) * t


def descent_legs(u, D, step=1.0):
    """The legs on the way down to the kneel, u 0 (standing) .. 1 (kneeling), hips D px down.
    The right foot slides back on its toe and tucks under while the knee goes down; the left
    foot steps forward first (lifted on the way: step) and plants."""
    if u >= 1.0:
        return kneel_legs(D)
    R1, L1 = kneel_legs(D_KNEEL)
    hip = gait.HIP_REST - D
    a = gait.smooth(u)
    pitch = _lerp(0.0, TUCK_PITCH, gait.smooth(u * 1.2))
    ra = (_lerp(0.0, R1['ankle'][0], a), max(_lerp(gait.ANKLE_H, R1['ankle'][1], a), boot_drop(pitch)))
    right = gait.solve(hip, ra, pitch)
    v = min(1.0, u * 1.6)
    la = (_lerp(0.0, L1['ankle'][0], gait.smooth(v)), gait.ANKLE_H + 6.0 * step * math.sin(math.pi * v))
    left = gait.solve(hip, la, 0.0, v >= 1.0)
    return right, left


_drops = {}


def boot_drop(pitch):
    """How far the side view's boot reaches below its ankle at this pitch (final px): the
    ankle must be at least this high for the boot to stay on the ground."""
    key = round(pitch, 1)
    if key not in _drops:
        lay = rig.Layout('right')
        k = lay.kx / B.WORK
        poly = [p for n, _, p in limb.PARTS if n == 'boot'][0]
        a = math.radians(-pitch)
        c, sn = math.cos(a), math.sin(a)
        low = max(sn * (x - limb.ANKLE[0]) * k + c * (y - limb.ANKLE[1]) * k for x, y in poly)
        # the polygon is drawn generously; the boot's sole is ROW px above its lowest point
        rest = max((y - limb.ANKLE[1]) * k for x, y in poly)
        _drops[key] = low - rest + gait.ANKLE_H
    return _drops[key]


def _hold_states(states, holds):
    return list(zip(states, holds))


# combat frames each pose is shown (the game's clocks: boss_sim.gd, veltharis_data.gd)
class Timed(AW.Clip):
    """A clip with a hold (combat frames) per pose."""

    def __init__(self, name, states, holds, before):
        super().__init__(name, states, before)
        self.holds = holds


def kneel_down(name='kneel_down', before=None):
    """Standing (sword planted) -> kneeling: the BROKEN entry, ~0.45 s. Pose 0 is the hit (the
    legs still standing: the approved legs), then the legs buckle - the right foot slides back
    and the knee goes down, the left foot steps forward - the body folds forward over the
    sword, which goes into the ground with the hand on it, the head drops."""
    before = before or (lambda k: STAND)
    K = kneel_state
    keys = [
        # D, lean, bow, legs u, rest, cape kick
        dict(D=0, lx=-4.0, bow=-10.0, ck=3.0, stand_legs=True, tilt=True),
        dict(D=7, lx=2.0, bow=3.0, u=0.2, ck=1.0),
        dict(D=16, lx=5.0, bow=9.0, u=0.45, ck=0.0),
        dict(D=25, lx=7.0, bow=14.0, u=0.7, ck=-1.0),
        dict(D=D_KNEEL - 7, lx=8.0, bow=20.0, u=0.9, ck=-2.0),
        dict(D=D_KNEEL + 2, lx=10.0, bow=27.0, u=1.0, rest=0.4, ck=-1.0),
        dict(D=D_KNEEL, lx=9.0, bow=25.0, u=1.0, rest=0.8),
        dict(D=D_KNEEL, lx=8.0, bow=24.0, u=1.0, rest=1.0),
        dict(D=D_KNEEL, lx=8.0, bow=24.0, u=1.0, rest=1.0),      # (the head, a pose late, settles)
    ]
    holds = [3, 3, 3, 4, 4, 4, 4, 2, 2]
    states = []
    for kk in keys:
        st = dict(K())
        st.update({k: v for k, v in kk.items() if k != 'u'})
        if kk.get('stand_legs'):
            st.pop('tilt_from', None)
            st['sk'] = (0, 0)
            st['legR'] = st['legL'] = gait.standing_leg()
            st['inL'] = st['inR'] = st['kneeL'] = 0
            st['rest'] = 0.0
        else:
            u = kk['u']
            st['legR'], st['legL'] = descent_legs(u, st['D'])
            if u < 1.0:
                # still going down: the sword goes in with the hand
                st.pop('tilt_from', None)
                st['sk'] = (0, 0)
            st['inL'] = round(-SPLAY_FOOT * u)
            st['inR'] = round(SPLAY_R * u)
            st['kneeL'] = round(SPLAY_KNEE * u)
            st.setdefault('rest', 0.0)
        states.append(st)
    return Timed(name, states, holds, before)


def _base(**kw):
    st = dict(kneel_state())
    st.update(kw)
    return st


def _seq(name, keys, before, legs=None):
    """A Timed clip from (hold, state overrides) on the kneel; legs(st) may replace the legs."""
    states, holds = [], []
    for hold, kw in keys:
        st = _base(**kw)
        if 'D' in kw:
            st['legR'], st['legL'] = kneel_legs(st['D'])
        if legs:
            legs(st)
        states.append(st)
        holds.append(hold)
    return Timed(name, states, holds, before)


KNEEL = None


def kneel_pose():
    global KNEEL
    if KNEEL is None:
        KNEEL = kneel_state()
    return KNEEL


# breathing while he kneels (BROKEN, after kneel_down): heavy, 0.8 s a breath; the chest and
# shoulders rise up to 2 px, the head a pose later, the cape's top with them
BREATH = [0, 1, 2, 2, 2, 1, 1, 0]
BREATH_HOLD = 6


def breathe():
    states = [_base(br=v) for v in BREATH]
    return Timed('kneel_breathe', states, [BREATH_HOLD] * len(BREATH), lambda k: states[-1 - k % len(states)])


def executed():
    """EXECUTED (1.0 s, PlayerData.EXECUTE_TIME): kneeling until the execution lands at 0.2 s
    (EXECUTE_HIT_TIME), then the jolt - the chest pushed back, the head snapped up - he slumps
    lower over the sword and settles back into the kneel (RISING follows)."""
    tf = KNEEL_SWORD_LEAN
    return _seq('executed', [
        (6, dict(br=0)), (6, dict(br=1)),
        (4, dict(D=D_KNEEL - 1, lx=-5.0, bow=-12.0, ck=3.0, tilt_from=tf)),
        (5, dict(D=D_KNEEL - 1, lx=-7.0, bow=-16.0, ck=4.0, tilt_from=tf)),
        (3, dict(D=D_KNEEL, lx=3.0, bow=10.0, ck=1.0, tilt_from=tf)),
        (6, dict(D=D_KNEEL + 2, lx=12.0, bow=34.0, ck=-2.0, tilt_from=tf)),
        (8, dict(D=D_KNEEL + 2, lx=11.0, bow=31.0, tilt_from=tf)),
        (8, dict(D=D_KNEEL + 1, lx=10.0, bow=28.0, tilt_from=tf)),
        (8, dict(D=D_KNEEL + 1, lx=9.0, bow=26.0, tilt_from=tf)),
        (3, dict()), (3, dict()),
    ], lambda k: kneel_pose())





def rise(name='rise', holds=(8, 9, 9, 8, 8, 8, 5, 5), extra=None):
    """RISING (1.0 s): kneeling -> standing with the sword planted, the way down played
    backwards (boss-veltharis §8.2) without the hit: it pushes down a little (the overshoot of
    the way down), then up, the left foot comes back, the right foot under him, the sword comes
    out of the ground with the hand. The breather that follows starts from standing (walk_start)."""
    down = kneel_down()
    states = [dict(st) for st in reversed(down.states[1:-2])] + [dict(STAND), dict(STAND)]
    for st in states[:-1]:
        st.pop('ck', None)
    if extra:
        for st, kw in zip(states, extra):
            st.update(kw)
    return Timed(name, states, list(holds), lambda k: kneel_pose())


def death():
    """DEAD: the kneel_down, then he slumps over the sword and stays (the ashes are drawn by code)."""
    down = kneel_down('death')
    slump = [_base(D=D_KNEEL + 1, lx=10.0, bow=30.0), _base(D=D_KNEEL + 2, lx=12.0, bow=34.0)]
    for st in slump:
        st['legR'], st['legL'] = kneel_legs(st['D'])
    slump.append(dict(slump[-1]))
    return Timed('death', down.states + slump, down.holds + [6, 4, 4], down.before)


def transition(from_kneel=False):
    """TRANSITION (1.5 s, invulnerable, VeltharisData.TRANSITION_TIME): down on one knee (fast),
    the surge - the head comes up, the cape is blown back and up (the flames surging are drawn by
    code) - and he rises with the cape still flaring, settling as he stands. from_kneel: the
    execution already put him on his knee (EXECUTED -> TRANSITION) - no way down."""
    keys = []
    if not from_kneel:
        down = kneel_down('transition')
        states = [dict(st) for st in down.states]
        holds = [2, 2, 2, 3, 3, 3, 3, 2, 1]
    else:
        states, holds = [], []
    surge = [(5, dict(bow=14.0, cf=0.3, ph=0.0)), (5, dict(bow=4.0, lx=5.0, cf=0.7, ph=0.25)),
             (5, dict(bow=-4.0, lx=3.0, cf=1.0, ph=0.5)), (5, dict(bow=-4.0, lx=3.0, cf=1.0, ph=0.75)),
             (5, dict(bow=-4.0, lx=3.0, cf=1.0, ph=1.0))]
    if from_kneel:
        surge = [(11, dict(bow=24.0))] + surge + [(5, dict(bow=-4.0, lx=3.0, cf=1.0, ph=1.25)),
                                                  (5, dict(bow=-4.0, lx=3.0, cf=1.0, ph=1.5))]
    for hold, kw in surge:
        states.append(_base(**kw))
        holds.append(hold)
    up = rise('transition_rise')
    rise_states = [dict(st) for st in up.states]
    flare = [(0.9, 1.25 + 0.25 * j) for j in range(len(rise_states) - 1)]
    for j, st in enumerate(rise_states[:-2]):
        f = 1.0 - 0.6 * j / (len(rise_states) - 3)
        st.update(cf=f, ph=1.5 + 0.25 * j, bow=min(st['bow'], -2.0 + 2 * j), lx=min(st.get('lx', 0), 3.0))
    states += rise_states
    holds += [6, 6, 6, 6, 6, 6, 4, 4]
    assert sum(holds) == 90 and len(holds) == len(states), (sum(holds), len(holds), len(states))
    name = 'transition_kneel' if from_kneel else 'transition'
    return Timed(name, states, holds, (lambda k: kneel_pose()) if from_kneel else (lambda k: STAND))


# ------------------------------------------------------------------ from moving
STOP_FROM = AW.STOP_FROM          # the loop poses a reaction can start from (as the stop clips): 0, 5, 10, 15
LAT_POSES = 4                     # poses a sidestep's feet take to come under him when he is broken
WALK_SWING = 8                    # poses the sword takes from the shoulder down into the ground (264 degrees;
                                  # 7 let its tip move up to 93 px a pose, over the 80 px limit)


def _toward(L0, L1, w, hip):
    """A leg between two leg states: ankle, pitch and sideways offset blended by w, solved at
    the hip height (a foot that moves far is lifted on the way)."""
    a0, a1 = L0['ankle'], L1['ankle']
    far = math.dist(a0, a1) > 6.0
    lift = 5.0 * math.sin(math.pi * w) if far else 0.0
    a = (_lerp(a0[0], a1[0], w), _lerp(a0[1], a1[1], w) + lift)
    pitch = _lerp(L0['pitch'], L1['pitch'], w)
    a = (a[0], max(a[1], boot_drop(pitch)))
    L = gait.solve(hip, a, pitch, w >= 1.0 or (L0['down'] and not far))
    lat = _lerp(L0.get('lat', 0.0), L1.get('lat', 0.0), w)
    if abs(lat) >= 0.5:
        L['lat'] = lat
    return L


def recoil(st, a):
    """The upper body thrown back by a hit, a = 0 .. 1: the chest rocks back, the head snaps
    up, the cape's hem swings forward. The legs and the sword's hold do not change."""
    out = dict(st)
    out.update(lx=st.get('lx', 0.0) - RECOIL_LEAN * a, bow=st.get('bow', 0.0) - RECOIL_BOW * a, ck=RECOIL_CAPE * a)
    return out


RECOIL_LEAN = 9.0        # degrees the chest is thrown back at the most
RECOIL_BOW = 16.0        # degrees the head snaps back (up)
RECOIL_CAPE = 5.0        # px the cape's hem swings forward
# (hold, recoil): 0.3 s. The last two poses are at rest: the head follows a pose late, so the
# clip's last pose is the pose he came from, exactly
STAGGER = [(3, 0.6), (4, 1.0), (4, 0.55), (3, 0.15), (2, 0.0), (2, 0.0)]


def stagger(kind=None, entry=0):
    """STAGGER (0.3 s, SHORT_STAGGER_TIME): rocked back by the hit and back to the pose he was
    in. kind None: standing (the sword planted, its tip stays put and it leans with the hand);
    else from the loop's pose `entry` of that way of moving (the legs stay where they are, the
    sword rides on the shoulder) - the loop goes on from that pose afterwards."""
    if kind is None:
        base = dict(STAND, tilt=True)
        before = lambda k: STAND
        name = 'stagger'
    else:
        base = AW.loop_state(entry, kind)
        before = lambda k: AW.loop_state(entry - 1 - k, kind)
        name = f'{kind}_stagger_{entry}'
    states = [recoil(base, a) if a else (dict(STAND) if kind is None else dict(base)) for _, a in STAGGER]
    return Timed(name, states, [h for h, _ in STAGGER], before)


def walk_kneel(kind, entry):
    """BROKEN (and death, the transition) while moving: from the loop's pose `entry`, the hit
    (the walk's pose, rocked back), then the sword comes off the shoulder the way the stop clips
    put it down - up, upright in front of him, the tip forward and down - and goes into the
    ground as the right knee reaches it; the feet go from where they were to the kneel."""
    w0 = AW.loop_state(entry, kind)
    before = lambda k: AW.loop_state(entry - 1 - k, kind)
    states = [recoil(w0, 0.7)]
    holds = [3]
    # The sword takes the stop clips' way down (264 degrees) in seven poses while the knees
    # give a little; it reaches the ground upright as the hips are 15 px down - driven in that
    # deep - and then he goes down on it as from standing.
    # (u: the way down, b: the sword 1 on the shoulder .. 0 planted, D, lean, bow)
    n = WALK_SWING
    keys = [(0.35 * (j + 1) / n, 0.91 - 0.84 * j / (n - 1), round(w0['D'] + (15 - w0['D']) * (j + 1) / n),
             6.0 * (j + 1) / n, 13.0 * j / (n - 1)) for j in range(n)]
    for j, (u, b, D, lx, bow) in enumerate(keys):
        st = _base(D=D, lx=lx, bow=bow, rest=0.0, b=b, planted=False, sink=True, lean=AW.LEAN_OF[kind], sk=(0, 0))
        st.pop('tilt_from', None)
        R1, L1 = descent_legs(u, D)
        w = gait.smooth(min(1.0, u * 2.0))
        hip = gait.HIP_REST - D
        st['legR'] = _toward(w0['legR'], R1, w, hip)
        st['legL'] = _toward(w0['legL'], L1, w, hip)
        # a sidestep's feet come under him first (the front view draws sideways legs from the
        # concept and legs under him from the approved rows: the change is made while they are
        # nearly straight)
        wl = gait.smooth(min(1.0, (j + 1) / LAT_POSES))
        for side_ in ('legR', 'legL'):
            if 'lat' in w0[side_]:
                lat = w0[side_]['lat'] * (1 - wl)
                if abs(lat) >= 0.5:
                    st[side_]['lat'] = lat
                else:
                    st[side_].pop('lat', None)
        st['inR'] = round(_lerp(w0['inR'], 0, w))
        st['inL'] = round(_lerp(w0['inL'], -SPLAY_FOOT * u, w))
        st['kneeL'] = round(SPLAY_KNEE * u * w)
        st['kind'] = kind
        states.append(st)
        holds.append(4)
    for u, D, lx, bow, rest in ((0.6, 24, 7.0, 16.0, 0.0), (0.85, D_KNEEL - 7, 8.0, 20.0, 0.0), (1.0, D_KNEEL + 2, 10.0, 27.0, 0.4),
                                (1.0, D_KNEEL, 9.0, 25.0, 0.8), (1.0, D_KNEEL, 8.0, 24.0, 1.0)):
        st = _base(D=D, lx=lx, bow=bow, rest=rest)
        if u < 1.0:
            st.pop('tilt_from', None)
            st['sk'] = (0, 0)
        R1, L1 = descent_legs(u, D)
        if u < 1.0:
            hip = gait.HIP_REST - D
            st['legR'] = _toward(w0['legR'], R1, 1.0, hip)
            st['legL'] = _toward(w0['legL'], L1, 1.0, hip)
            st['inL'] = round(-SPLAY_FOOT * u)
            st['inR'] = round(SPLAY_R * u)
            st['kneeL'] = round(SPLAY_KNEE * u)
        else:
            st['legR'], st['legL'] = R1, L1
        states.append(st)
        holds.append(4)
    states.append(dict(states[-1]))          # (the head, a pose late, settles)
    holds[-1:] = [2, 2]
    return Timed(f'{kind}_kneel_{entry}', states, holds, before)


# ------------------------------------------------------------------ the bounce
CARRY_STAND = dict(AW.STAND, b=1.0, lean=0.0, amp=0.0)     # standing, the sword on the shoulder


def bounce(long=True):
    """BOUNCED (1.2 s after a heavy hit is parried, 0.8 s after the light combo's last): the
    representative contact pose (the sword swung out forward at chest height, the right foot
    forward - until the attacks exist), the sword knocked up and back, the body rocked back on
    its heels, the sword let go on over onto the shoulder and the feet brought together: he
    ends standing with the sword on the shoulder, ready to move (the breather walks next)."""
    lunge = AW.loop_state(0, 'walk')
    keys = [
        # b, fist offset (F, R, U), elbow (side, rel. fist), lean, bow, ck, legs w (0 lunge .. 1 together)
        (0.34, (16.0, 0.0, -6.0), (-15.0, 5.0), 10.0, 2.0, -1.0, 0.0),
        (0.45, (13.0, 0.0, 2.0), None, 3.0, -6.0, 2.0, 0.05),
        (0.56, (8.0, 0.0, 9.0), None, -4.0, -12.0, 4.0, 0.15),
        (0.66, (3.0, 0.0, 12.0), None, -9.0, -14.0, 5.0, 0.3),
        (0.76, (0.0, 0.0, 11.0), None, -10.0, -13.0, 4.0, 0.5),
        (0.85, (0.0, 0.0, 6.0), None, -7.0, -8.0, 2.0, 0.7),
        (0.93, (0.0, 0.0, 2.0), None, -3.0, -2.0, 0.0, 0.9),
        (0.99, (0.0, 0.0, 0.0), None, -1.0, 0.0, 0.0, 1.0),
    ]
    states = []
    stand = gait.standing_leg()
    for b, g3, el, lx, bow, ck, w in keys:
        st = dict(CARRY_STAND, b=b, lx=lx, bow=bow, ck=ck, grip3=g3)
        if el:
            st['elbow'] = el
        D = round(_lerp(lunge['D'], 0, w))
        hip = gait.HIP_REST - D
        st['D'] = D
        st['legR'] = _toward(lunge['legR'], stand, gait.smooth(w), hip)
        st['legL'] = _toward(lunge['legL'], stand, gait.smooth(w), hip)
        st['inR'] = round(_lerp(lunge['inR'], 0, w))
        st['inL'] = round(_lerp(lunge['inL'], 0, w))
        states.append(st)
    states.append(dict(CARRY_STAND))
    # the knock is fast (the tip moves up to 80 px a pose), the recovery slow
    holds = [4, 2, 3, 5, 8, 10, 12, 12, 16] if long else [3, 2, 2, 3, 5, 7, 8, 8, 10]
    return Timed('bounce' if long else 'bounce_short', states, holds, lambda k: states[0])


def carry_start(kind):
    """Standing with the sword on the shoulder (where the bounce ends) -> moving: the start clip's
    legs and lean, the sword staying on the shoulder."""
    c = AW.start_clip(kind)
    states = []
    for k, st in enumerate(c.states):
        st = dict(st)
        st['lean'] = AW.LEAN_OF[kind] * st['b']
        st['b'] = 1.0
        states.append(st)
    return Timed(f'{kind}_cstart', states, [AW.HOLD] * len(states), lambda k: CARRY_STAND)
