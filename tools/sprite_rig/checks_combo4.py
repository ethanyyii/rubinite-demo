"""Checks for the four-hit light combo, second version (combo4.py; docs/art-progress.md, "四段輕攻擊：第二版").

    python3 tools/sprite_rig/checks.py --combo4       # exit code 0 = all passed

Every frame of the four stages and of stages 2-4's entries from the stance, in all four views:
  - the technical checks every pose gets (checks.pose_rows on the frame as drawn - a twisted frame joins
    two views, each piece measured against its own view's library: palette, canvas, floor, holes,
    pinholes, specks, detail kept per piece, arm glints, blade contrast >= 3:1);
  - the leg rules (animation-review §4.3): side views knee under the hip >= 10 % of the hip-to-ankle
    height, near leg <= 1.0 and far leg <= 1.1 of its length; front / back every leg >= 2 px on screen;
    held poses east vs west within 1.5 px;
  - the attack stance (pelvis drop, side ankles apart; front / back at least the idle's width), and the
    tall top of stage 3 (stretched on purpose) apart from the idle and the guard;
  - moves between frames on screen (the picture where it shows: the frame plus the program's advance),
    with the exceptions listed in EXEMPT, each with its reason and cap;
  - the planted foot (side views <= 1 px; front / back reported: batch 2 decision D);
  - chaining at the earliest frame, late chains and the grace into the entries from the stance, entering
    stage 1 from the idle / guard / guard walk, and every stage's last frame vs idle 1;
  - timing: the frames tile each stage's sim frames, >= 2 sim frames each, the contact frame on the first
    active frame;
  - the four stages look different (the user's request, 2026-09-29: "四刀的輪廓都不同，玩家只看剪影也能
    分辨打到第幾段"): their wind-up and finishing frames differ pairwise in every view, by the outline
    alone (>= 12 %; the first version's test also let a blade elsewhere pass, which is what let four
    look-alike stages through);
  - the body turns (the user: shoulders, waist and feet turn together): stages 1-3 each change the drawn
    upper body at least once, stage 4 turns through all four views;
  - the blade in sight, reported per frame.
Thresholds come from checks.py (BODY_PX-derived); the recorded exceptions print their values and fail
again when a value grows past its cap."""
import math

import checks as C
import combo4 as C4
import batch1 as B1
import pose_rig as PR
import sprites as A

LIMIT = C.B1_JUMP                       # 4 px: head, torso, feet
HAND = C.B1_HAND_JUMP                   # 20 px: hands, sword
SWING = C.SWING_JUMP                    # 8 px: head / torso in the swing steps (batch 2 decision 5)

# The attack stance (first version, decision 1: re-derived from the leg reach - the legs are 5-6 px from
# hip to ankle): the pelvis >= 2 px lower than the idle, side ankles >= 11 px apart (the idle's 5-6),
# front / back at least the idle's width.
ATTACK_STANCE_C4 = {  # (stage, frame name): (pelvis drop, side ankles apart)
    (1, 'f1 壓低'): (2.0, 9.0), (1, 'f6 揮完'): (2.0, 9.0), (1, 'f7 收招'): (2.0, 9.0),
    (2, 'f1 落劍'): (2.0, 9.0), (2, 'f4 接觸'): (2.0, 13.0), (2, 'f6 揮完'): (3.0, 10.0), (2, 'f7 收招'): (3.0, 10.0),
    (3, 'f1 沉腰'): (3.0, 10.0),
    (4, 'f7 揮完'): (3.0, 9.0), (4, 'f8 收招 1'): (3.0, 9.0),
}
# stage 3's top stands tall on purpose (the body driven up from the legs): checked for its outline
# against the idle and the guard instead
TALL = [(3, 'f5 挑到頂'), (3, 'f6 收招')]

# The steps allowed past the 4 / 20 px limits, each with its reason and caps (px, on screen):
#   swing - the swing steps (batch 2 decision 5, the user): head / torso 8; feet 4; hands and the blade 20
#           as everywhere (the user tracked the blade's 20 px per step in batch 2, item 7): the arcs get an
#           in-between frame each side of the contact instead
#   twist - the upper body drawn from the next view round (the chest turning 90 deg in the picture for a
#           45 deg twist): the library's torsos and necks are cut differently in each view, so torso and
#           head jump with the view even where the body does not move; held to the swing step's 8 px
#   spin  - stage 4's turn: the whole figure drawn from the view it faces, one view to the next (each
#           view's library head sits 4-8 px from the others'), the stance turning round the pelvis: head /
#           torso / feet 8, hands / sword not limited (the blade circles with the body, a quarter turn a
#           frame: its tip crosses the figure; the cut itself, contact -> follow-through, keeps 20)
#   entry - the entries from the stance: the sword from where it hangs to the wind-up (batch 2
#           decision 3: an attack's first frames move the sword freely); head / torso / feet 4
SWING_SWORD = HAND
TWIST_TORSO = SWING
EXEMPT = {
    # (stage, from index, to index): kind; indexes of combo4.frames(stage, view)
    (1, 0, 1): 'swing', (1, 1, 2): 'swing', (1, 2, 3): 'swing', (1, 3, 4): 'swing+twist', (1, 4, 5): 'swing',
    (1, 6, 7): 'twist',
    (2, 0, 1): 'swing', (2, 1, 2): 'swing+twist', (2, 2, 3): 'swing', (2, 3, 4): 'swing+twist', (2, 4, 5): 'swing',
    (2, 6, 7): 'twist',
    (3, 0, 1): 'swing', (3, 1, 2): 'swing+twist', (3, 2, 3): 'swing', (3, 3, 4): 'swing',
    (4, 0, 1): 'swing+twist', (4, 1, 2): 'swing', (4, 2, 3): 'spin', (4, 3, 4): 'spin', (4, 4, 5): 'spin',
    (4, 5, 6): 'spin',
}
# entry index -> kind (the step from entry frame i to the next; the last goes into the stage's own frame)
ENTRY_EXEMPT = {(2, 1): 'twist', (3, 1): 'twist', (4, 1): 'twist'}
DRIFT_FB = {4: 7.0}                      # front / back feet caps in stage 4 (drift), px
# slow legs (the guard walk, 24 frames: the body leans and bobs with the step) into stage 1's ready
# frame: batch 2 decision F accepted 4.2-4.7 px there, to be play-tested once wired in. Caps per view
SLOW_LEGS_IN = {'south': {'head': 4.0, 'torso': 4.0, 'feet': 4.4},
                'east': {'head': 4.0, 'torso': 4.0, 'feet': 4.4},
                'north': {'head': 4.0, 'torso': 4.0, 'feet': 5.3},     # 5.2 in the first version
                'west': {'head': 4.0, 'torso': 4.0, 'feet': 5.3}}
DISTINCT_MIN = C.OUTLINE_DIFF_MIN
# the frames that make each stage what it is: the wind-up that shows what is coming, and the finish
# stage 4 (2026-09-29 fifth version): its wind-up is short and in motion (the turn starting, drawn with the
# chest turned left - the same view as stage 2's cock, so in the back / left views the two outlines are the
# same); what makes stage 4 what it is, is the hit inside the turn: side-on, the arm and blade straight out
# at the target. That is its signature frame; the turn starting is reported against the others' wind-ups
SIGNATURE = {1: 'f1 壓低', 2: 'f1 落劍', 3: 'f1 沉腰', 4: 'f4 接觸'}
FINISH = {1: 'f6 揮完', 2: 'f6 揮完', 3: 'f5 挑到頂', 4: 'f7 揮完'}
TURN = 'f2 起轉 1'
# pairs the user accepted (2026-09-30, after the fifth version: "沒問題了"): alike by the black outline, apart
# by colour or height. Recorded with the share measured when approved (animation-review §5); a pair that
# gets more alike than recorded fails again
DISTINCT_WAIVED = {   # (view, 'wind-up' / 'finish', stage a, stage b): outline share when accepted
    ('east', 'wind-up', 2, 3): 0.1106, ('west', 'wind-up', 2, 3): 0.0622,
    ('west', 'finish', 1, 2): 0.0679, ('south', 'finish', 3, 4): 0.0861,
}
WAIVE_DISTINCT_EPS = 0.002
CONTACT = '接觸'

BLADE_SEEN_MIN = 8


def _blade_seen(f):
    return {q for q in f.debug['blade'] if f.trace.get(q) == 'sword' and q in f.px}


def _pt(f):
    ox, oy = f.screen_offset()
    return C._Pt(f, ox, oy)


def _limits(kind, view):
    if kind == 'swing':
        return {'head': SWING, 'torso': SWING, 'feet': LIMIT, 'hands': HAND, 'sword': SWING_SWORD}
    if kind == 'twist':
        return {'head': SWING, 'torso': TWIST_TORSO, 'feet': LIMIT, 'hands': HAND, 'sword': HAND}
    if kind == 'swing+twist':
        return {'head': SWING, 'torso': TWIST_TORSO, 'feet': LIMIT, 'hands': HAND, 'sword': SWING_SWORD}
    if kind == 'entry':
        return {'head': LIMIT, 'torso': LIMIT, 'feet': LIMIT, 'hands': HAND}
    if kind == 'spin':
        return {'head': SWING, 'torso': SWING, 'feet': SWING}
    return {'head': LIMIT, 'torso': LIMIT, 'feet': LIMIT, 'hands': HAND, 'sword': HAND}


def _over(m, lim):
    return [k for k, v in lim.items() if m.get(k) is not None and m[k] > v + 1e-6]


def _fmt(m):
    return C._fmt_moves(m)


def _rest_pelvis(dv):
    r = PR.rig(dv)
    r.frame({}, 'large')
    return r.debug['pelvis'][1] + r.canvas_offset()[1]


class Pre:
    """A drawn combo frame as checks.pose_rows reads a rig: its data back in the small frame's
    coordinates of the view its legs are drawn in, each piece's library from its own view."""

    def __init__(self, f):
        W_, H_, cx, gy = PR.CANVAS[C4.CANVAS]
        sx, sy = f.pose.get('screen_shift', (0, 0))
        self.off = (cx - A.CX + int(sx), gy - A.GROUND + int(sy))
        dx, dy = self.off
        back = lambda d: {(x - dx, y - dy): c for (x, y), c in d.items()}
        self.trace = back(f.trace)
        self.pieces = {n: back(v) for n, v in f.pieces.items()}
        self.pieces_raw = {n: back(v) for n, v in f.pieces_raw.items()}
        self.debug = {'blade': {(x - dx, y - dy) for (x, y) in f.debug['blade']},
                      'hands': {k: (x - dx, y - dy) for k, (x, y) in f.debug['hands'].items()}}
        self.arm_view = f.upper_view
        self.f = f

    def canvas_offset(self):
        return self.off

    def lib_pix(self, n):
        return C4.lib_piece(self.f, n)


def frame_rows(f):
    pose = dict(f.pose, sword=f.upper_pose['sword'], blade_tilt=True)
    return C.pose_rows('', pose, C4.CANVAS, f.draw_view, pre=(Pre(f), f.px))


def leg_row(f):
    """(ok, info) for one frame's legs."""
    dv = f.draw_view
    ks, ht = C.leg_shape(f, dv)
    if dv in ('east', 'west'):
        near, far = C.leg_stretch(f, 'near'), C.leg_stretch(f, 'far')
        ok = ks >= C.KNEE_BELOW_MIN and near <= C.LEG_STRETCH_MAX + 1e-6 and far <= C.LEG_STRETCH_FAR + 1e-6
        return ok, f'knee {ks:.2f} of the height under the hip, near {near:.2f} / far {far:.2f} of the leg, planted ' + ('-' if ht is None else f'{ht:.1f} px tall')
    return ks >= C.FB_LEG_SEEN_MIN, f'shortest leg {ks:.1f} px on screen'


def stance(f):
    """(pelvis drop vs idle, ankles apart) as the frame's own (legs) view draws them."""
    dv = f.draw_view
    fr_, fl_, _ = f.pose.get('root', (0, 0, 0))
    sy = f.pose.get('screen_shift', (0, 0))[1]
    drop = f.debug['pelvis'][1] - _rest_pelvis(dv) - PR.proj(dv, (fr_, fl_, 0))[1] - sy
    ank = [v[2][0] for v in f.debug['legs'].values()]
    return drop, abs(ank[0] - ank[1])


def _torso_view(f):
    return (f.upper_view, f.k)


def combo4_checks():
    failed = False

    def out(ok, name, info=''):
        nonlocal failed
        if ok is None:
            print(f'  INFO  {name}  {info}')
            return
        failed |= not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {info}")

    frames = {(st, v, e): C4.frames(st, v, entry_frames=e) for st in (1, 2, 3, 4) for v in C4.VIEWS
              for e in ((False, True) if st in C4.ENTRY else (False,))}
    print(f'== four-hit combo, second version (combo4.py): on screen, head / torso / feet <= {LIMIT} px, hands / sword '
          f'<= {HAND} px; exceptions listed with their caps')

    # ---- every frame: technical checks and the legs
    print('-- every frame: technical checks (checks.pose_rows on the frame as drawn) and the leg rules')
    for (st, v, e), fr in frames.items():
        for f in fr:
            label = f'stage {st} / {f.name} / {v}' + (f' (upper body drawn {f.upper_view})' if f.upper_view != v else '')
            rows = frame_rows(f)
            bad = [(n, i_) for n, ok, i_ in rows if ok is False]
            for n, i_ in bad:
                out(False, f'{label}: {n}', i_)
            ok, info = leg_row(f)
            if bad or not ok:
                out(ok, f'{label}: legs', info)
            else:
                out(True, f'{label}: {len([r for r in rows if r[1] is not None])} technical checks and the legs', info)

    # ---- the attack stance
    print('-- attack stance: pelvis drop, side ankles apart; front / back at least the idle width')
    for (st, name), (drop_min, side_min) in ATTACK_STANCE_C4.items():
        for v in C4.VIEWS:
            f = next(f for f in frames[(st, v, False)] if f.name == name)
            drop, spread = stance(f)
            need = side_min if f.draw_view in ('east', 'west') else C.IDLE_WIDTH[f.draw_view]
            out(drop >= drop_min - 0.05 and spread >= need - 0.05,
                f'stage {st} {name} {v}: pelvis >= {drop_min} px lower than idle, ankles >= {need} px apart',
                f'{drop:.1f} px, {spread:.1f} px')
    mv = lambda s_: {(x + C.SMALL_TO_LARGE[0], y + C.SMALL_TO_LARGE[1]) for (x, y) in s_}
    for st, name in TALL:
        for v in C4.VIEWS:
            f = next(f for f in frames[(st, v, False)] if f.name == name)
            s_top = C._sil(f)
            s_idle = mv(C._sil(B1.frames('idle', v)[0]))
            s_guard = mv(C._sil(next(g for g in B1.frames('guard', v) if g.name == 'hold 1')))
            a_, b_ = C.outline_shift_share(s_top, s_idle), C.outline_shift_share(s_top, s_guard)
            top = min(y for (x, y), n in f.trace.items() if n == 'sword') if any(n == 'sword' for n in f.trace.values()) else None
            helm = min(y for (x, y), n in f.trace.items() if n == 'helmet')
            out(a_ >= DISTINCT_MIN and b_ >= DISTINCT_MIN,
                f'stage {st} {name} {v}: the tall top apart from the idle and the guard (outline >= {DISTINCT_MIN:.0%})',
                f'{round(100 * a_)} % / {round(100 * b_)} %; blade top {"-" if top is None else helm - top} px over the helmet')
    for st, name in ((1, 'f7 收招'), (2, 'f7 收招'), (3, 'f6 收招'), (4, 'f8 收招 1')):
        hts = {v: C.leg_shape(next(f for f in frames[(st, v, False)] if f.name == name), v)[1] for v in ('east', 'west')}
        out(abs(hts['east'] - hts['west']) <= C.SIDE_LEG_SYM,
            f'stage {st} {name}: east vs west planted legs the same height (within {C.SIDE_LEG_SYM} px)',
            f'east {hts["east"]:.1f}, west {hts["west"]:.1f}')

    # ---- moves between frames
    print('-- moves between consecutive frames, on screen')
    for st in (1, 2, 3, 4):
        for v in C4.VIEWS:
            fr = frames[(st, v, False)]
            worst, notes = {}, []
            for i in range(len(fr) - 1):
                m = C.screen_moves(_pt(fr[i]), _pt(fr[i + 1]))
                kind = EXEMPT.get((st, i, i + 1), 'normal')
                lim = _limits(kind, v)
                if st in DRIFT_FB and v in ('south', 'north') and kind in ('normal', 'swing'):
                    lim = dict(lim, feet=DRIFT_FB[st])
                over = _over(m, lim)
                if kind != 'normal':
                    notes.append(f'{fr[i].name}->{fr[i + 1].name} [{kind}] {_fmt(m)}')
                if over:
                    out(False, f'stage {st} {v}: {fr[i].name} -> {fr[i + 1].name} ({kind}) within {lim}', _fmt(m))
                for k, val in m.items():
                    if val is not None and kind == 'normal':
                        worst[k] = max(worst.get(k, 0), val)
            out(True, f'stage {st} {v}: {len(fr) - 1} steps checked against their limits', 'largest ordinary step ' + _fmt(worst))
            for n in notes:
                out(None, f'stage {st} {v}: exception', n)
        if st in C4.ENTRY:
            for v in C4.VIEWS:
                en = frames[(st, v, True)] + [frames[(st, v, False)][C4.ENTRY[st]]]
                for i in range(len(en) - 1):
                    m = C.screen_moves(_pt(en[i]), _pt(en[i + 1]))
                    kind = ENTRY_EXEMPT.get((st, i + 1), 'normal')
                    lim = _limits(kind, v)
                    out(not _over(m, lim), f'stage {st} {v}: entry {en[i].name} -> {en[i + 1].name} ({kind})', _fmt(m))

    # ---- the planted foot
    print(f'-- the foot bearing the weight stays put on screen: side views <= {C.DRIFT_MAX} px; front / back reported (decision D)')
    for st in (1, 2, 3, 4):
        for v in C4.VIEWS:
            fr = frames[(st, v, False)]
            drifts = []
            for a, b in zip(fr, fr[1:]):
                s_ = a.weight
                if s_ is None or s_ != b.weight or a.k or b.k or a.draw_view != b.draw_view:
                    continue
                if a.feet_w[s_][2] or b.feet_w[s_][2]:
                    continue
                pa, pb = _pt(a), _pt(b)
                key = s_ if v in ('south', 'north') else ('near' if PR.VIEWS[v]['near'] == s_ else 'far')
                qa, qb = pa.ankles[key], pb.ankles[key]
                d = abs(qa[0] - qb[0]) if v in ('east', 'west') else abs(qa[1] - qb[1])
                drifts.append((d, f'{a.name}->{b.name} {s_}'))
            w = max(drifts) if drifts else (0.0, '')
            if v in ('east', 'west'):
                out(w[0] <= C.DRIFT_MAX + 1e-6, f'stage {st} {v}: weight foot on screen', f'largest {w[0]:.1f} px ({w[1]})')
            else:
                out(None, f'stage {st} {v}: weight foot on screen (decision D)', f'largest {w[0]:.1f} px ({w[1]})')

    # ---- chains, entries, returns
    print('-- chaining: earliest (the frame shown before combo4.CHAIN -> the stage), late (from the frames back to the stance) and '
          'the grace (-> the entry from the stance), into stage 1 from idle / guard / guard walk, last frame vs idle 1: '
          'head / torso / feet <= 4 px (the sword is free: batch 2 decision 3)')
    body = ('head', 'torso', 'feet')
    lim4 = {k: LIMIT for k in body}
    for v in C4.VIEWS:
        fx, fy = C4.FWD_SCREEN[v]
        idle = B1.frames('idle', v)[0]
        for a_st, b_st in ((1, 2), (2, 3), (3, 4)):
            A_ = frames[(a_st, v, False)]
            adv_a = C4.ATTACK[a_st][3]
            chain = C4.CHAIN[a_st]
            main0, ent0 = frames[(b_st, v, False)][0], frames[(b_st, v, True)][0]
            pm = C._Pt(main0, fx * (adv_a + main0.adv), fy * (adv_a + main0.adv))
            pe = C._Pt(ent0, fx * (adv_a + ent0.adv), fy * (adv_a + ent0.adv))
            for f in A_:
                if f.last < chain - 1:               # never the last frame shown: the next stage starts on `chain`
                    continue
                late = C4.LATE in f.name             # from the frames back to the stance: the entry
                m = C.screen_moves(_pt(f), pe if late else pm)
                out(not _over(m, lim4), f'{v}: stage {a_st} {f.name} -> stage {b_st} {(ent0 if late else main0).name}', _fmt(m))
            m = C.screen_moves(C._Pt(idle, fx * adv_a, fy * adv_a, small=True), pe)
            out(not _over(m, lim4), f'{v}: idle 1 (the grace after stage {a_st}) -> stage {b_st} {ent0.name}', _fmt(m))
        f1 = _pt(frames[(1, v, False)][0])
        for group, srcs, caps in (
                ('idle / guard', [('idle 1', idle)] + [(f'guard {g.name}', g) for g in B1.frames('guard', v) if g.name.startswith('hold')], lim4),
                ('guard walk (exception: slow legs into stage 1)', [(f'guard walk {g.name}', g) for g in B1.frames('guard_walk', v)],
                 SLOW_LEGS_IN[v])):
            worst = (0.0, '', None)
            for nm, src in srcs:
                m = C.screen_moves(C._Pt(src, small=True), f1)
                w = max((m[k] or 0) / caps[k] for k in body)
                if w > worst[0]:
                    worst = (w, nm, m)
            out(worst[0] <= 1 + 1e-6, f'{v}: into stage 1 f1 from {group} (worst: {worst[1]}; caps {caps})', _fmt(worst[2]))
        for st in (1, 2, 3, 4):
            last = frames[(st, v, False)][-1]
            m = C.screen_moves(_pt(last), C._Pt(idle, fx * C4.ATTACK[st][3], fy * C4.ATTACK[st][3], small=True))
            out(not _over(m, lim4), f'{v}: stage {st} {last.name} vs idle 1', _fmt(m))

    # ---- timing
    print('-- timing (player_data.gd / player_sim.gd, 2026-09-29)')
    for st in (1, 2, 3, 4):
        fr = frames[(st, 'east', False)]
        a0, act, total, _ = C4.ATTACK[st]
        tiles = all(fr[i + 1].first == fr[i].last + 1 for i in range(len(fr) - 1)) and fr[0].first == 0 and fr[-1].last == total - 1
        out(tiles and min(f.dur for f in fr) >= 2, f'stage {st}: frames tile 0-{total - 1}, each >= 2 sim frames',
            ', '.join(f'{f.first}-{f.last}' for f in fr))
        hit = next(f for f in fr if f.first <= a0 <= f.last)
        out(CONTACT in hit.name and hit.first == a0, f'stage {st}: the contact frame starts on the first active frame ({a0})', hit.name)
        if st in C4.ENTRY:
            en = frames[(st, 'east', True)]
            main = frames[(st, 'east', False)]
            ok = [(e.first, e.last) for e in en] == [(m.first, m.last) for m in main[:C4.ENTRY[st]]]
            out(ok, f'stage {st}: the entry from the stance keeps the timing of the frames it replaces', ', '.join(e.name for e in en))
    pause = [f.name for f in frames[(4, 'east', False)] if f.last >= C4.RECOVERY_END[4]]
    out(None, f'stage 4: the pause ({C4.RECOVERY_END[4]}-{C4.ATTACK[4][2] - 1}) shows', ', '.join(pause))

    # ---- the body turns
    print('-- the body turns (the user: shoulders, waist and feet together): stages 1-3 draw the upper body from another view '
          'at least once, stage 4 turns through all four views from its first frame to its finish, the contact inside the '
          'turn (not square to the target), square at both ends')
    for v in C4.VIEWS:
        for st in (1, 2, 3):
            fr = frames[(st, v, False)]
            ups = [f.upper_view for f in fr]
            out(any(u != v for u in ups), f'{v}: stage {st} twists', ' '.join(f'{f.name.split()[0]}:{f.upper_view}' for f in fr))
        fr = frames[(4, v, False)]
        i0 = next(i for i, f in enumerate(fr) if CONTACT in f.name)
        i1 = next(i for i, f in enumerate(fr) if f.name == FINISH[4])
        seen = [f.draw_view for f in fr[:i1 + 1]]
        out(set(seen) == set(C4.VIEWS) and fr[0].draw_view == v and fr[i1].draw_view == v and fr[i0].draw_view != v,
            f'{v}: stage 4 turns through the four views from its first frame to its finish, the contact inside the turn',
            ' '.join(seen))

    # ---- the four stages look different (the user's request)
    print(f'-- the four stages look different by the outline alone (checks.outline_shift_share) >= {DISTINCT_MIN:.0%} pairwise: '
          f'wind-ups ({", ".join(SIGNATURE.values())}) and finishes ({", ".join(FINISH.values())}). The whole outline, cape and '
          f'plume in: each stage throws the cloth its own way on purpose (the user: the cape flies opposite to the turn, spreads '
          f'in the spin), and that is what a player sees. Without the cloth: reported')
    for v in C4.VIEWS:
        for what, table in (('wind-up', SIGNATURE), ('finish', FINISH)):
            fr_ = {st: next(f for f in frames[(st, v, False)] if f.name == table[st]) for st in (1, 2, 3, 4)}
            full = {st: set(f.px) for st, f in fr_.items()}
            bare = {st: C._sil(f) for st, f in fr_.items()}
            vals, info, ok = [], [], True
            for a in (1, 2, 3, 4):
                for b in range(a + 1, 5):
                    o = C.outline_shift_share(full[a], full[b])
                    good = o >= DISTINCT_MIN
                    rec = DISTINCT_WAIVED.get((v, what, a, b))
                    waived = not good and rec is not None and o >= rec - WAIVE_DISTINCT_EPS
                    ok &= good or waived
                    vals.append(f'{a}-{b} {round(100 * o)}%' + ('' if good else
                                (f' (alike: accepted 2026-09-30, recorded {100 * rec:.1f}%)' if waived else ' (alike)')))
                    info.append(f'{a}-{b} {round(100 * C.outline_shift_share(bare[a], bare[b]))}%')
            out(ok, f'{v}: {what} frames of the four stages differ by outline', ', '.join(vals))
            out(None, f'{v}: {what} frames, outline without the cloth', ', '.join(info))
        turn = set(next(f for f in frames[(4, v, False)] if f.name == TURN).px)
        rep = [f'{what} {st} {round(100 * C.outline_shift_share(turn, set(next(f for f in frames[(st, v, False)] if f.name == table[st]).px)))}%'
               for what, table in (('wind-up', SIGNATURE), ('finish', FINISH)) for st in (1, 2, 3)]
        out(None, f'{v}: stage 4 {TURN} (the turn starting) against stages 1-3', ', '.join(rep))

    # ---- the blade in sight (reported: a blade on the far side or pointing away is hidden, as it should be)
    print('-- the blade in sight (pixels of the blade drawn), reported')
    for st in (1, 2, 3, 4):
        for v in C4.VIEWS:
            seen = [len(_blade_seen(f)) for f in frames[(st, v, False)]]
            out(None, f'stage {st} {v}', ' '.join(str(s) for s in seen))
    print('COMBO4: ALL PASSED' if not failed else 'COMBO4: SOME CHECKS FAILED')
    return failed
