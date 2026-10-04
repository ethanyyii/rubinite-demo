"""Boss oath cleave (墜誓下劈, C3 下劈): sprite sheets and previews.

    python3 tools/boss_rig/export_cleave.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_cleave.png (the cleave; the
delayed version plays the same poses with the highest one held longer), boss_cleave_bounce.png
(parried), boss_cleave_<move>_entry.png (starting from a move). The attack container 384x336,
foot anchor (192, 272); rows down, right, up, left. Timing and the grip / tip per pose are added
to boss_attacks.json (the other attacks' entries are kept). Previews ->
docs/art-preview/boss/cleave/ (its own folder: export_attack.py clears docs/art-preview/boss/attack/).
"""
import json
import math
import os
import shutil
import sys
import rig
import anim_walk as AW
import attacks as AT
import attack3d as A
import sword as swd
import anim_attack as AA
import export_anim as EA
import export_hit as EH
import export_attack as E
import boss as B

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'cleave')
NAMES = EA.NAMES
BOX = (-90, -92, 346, 290)          # down to the blade in the ground seen from the front, up to it over his head
PHASE2_RECOVERY = 54          # veltharis_data: 收招 1.2 s x 0.75


def moves():
    # veltharis_data oath_cleave: 起手 1.0 / 判定 0.1 / 收招 1.2 (二階段 0.9 -> 54); the delayed
    # version: the highest point (0.8 s) held 0.6 s longer
    c = E.Move('boss_cleave', AT.cleave(), AT.CLEAVE_END, [(AT.CLEAVE_W, 6)], '墜誓下劈（C3 下劈，雙手）',
               phase2_recovery=PHASE2_RECOVERY, entries=True)
    # BOUNCED 1.2 s: from the contact (the tip through the player's height at the hit box's edge)
    b = E.Move('boss_cleave_bounce', AT.cleave_bounce(), 72, [], '墜誓下劈被彈開',
               first=(c, c.times.index(AT.CLEAVE_CONTACT)))
    # ash_impact (phase 1): 起手 1.1, the ring 0.2, 收招 1.4; double_impact (phase 2): a second ring
    # 0.9 s after the first, 收招 1.4 x 0.75. The ash impact has its own raise (tip-down over his head) and
    # entry sheets; the double impact opens the same way and shares them
    i = E.Move('boss_impact', AT.impact(), AT.IMPACT_END, [(AT.IMPACT_RING, 12)], '灰燼衝擊（雙手舉過頭、劍尖朝下插進地面，不可格擋）',
               entries=True, entry_spec=AT.IMPACT_ENTRY)
    d = E.Move('boss_double_impact', AT.double_impact(), AT.DOUBLE_END, [(AT.IMPACT_RING, 12), (AT.IMPACT_RING2, 12)],
               '雙重衝擊（二階段，插地兩次）', entry_times=True, entry_spec=AT.IMPACT_ENTRY)
    # triple_slash (phase 2): the twin slash's two cuts, the cleave 1.0 s after the second; its recovery
    # is phase 2's (hold_phase2). It opens as the royal sweep does: the C1 entry sheets
    t = E.Move('boss_triple', AT.triple(), AT.TRIPLE_END, [(AT.W, 6), (AT.W2, 6), (AT.TRIPLE_W3, 6)],
               '三斬（二階段：雙斬 → 下劈）', phase2_recovery=PHASE2_RECOVERY, entry_times=True)
    return [c, b, i, d, t]


def delayed_holds(m, holds=None, top=AT.CLEAVE_TOP):
    """The delayed version's holds: the highest point's pose held CLEAVE_HOLD frames longer."""
    out = list(holds or m.holds)
    out[m.times.index(top)] += AT.CLEAVE_HOLD
    return out


def bite(d, s):
    """Where on screen (cell px) the blade goes into the ground, or None (above it)."""
    f, ax = s['fist'], s['axis']
    if A.tip(s)[2] >= 0.0 or ax[2] >= 0.0:
        return None
    t0 = f[2] / -ax[2]
    view = 'right' if d in ('right', 'left') else ('front' if d == 'down' else 'back')
    g = AA.SWORD[(d, s['name'], s['i'])][2]          # facing left: in facing-right space, mirrored below
    v = swd.project_vec(view, ax, d == 'left')
    p = (g[0] + v[0] * t0, g[1] + v[1] * t0)
    if d == 'left':
        p = (2 * rig.AX - p[0], p[1])
    return [round(p[0] + AW.EXT, 1), round(p[1] + AW.EXT + AA.TALL_TOP, 1)]


# The flare (drawn by code; the previews draw a stand-in). User 2026-10-04: "紅色閃光要再更大更明顯一點，
# 要比頭都大很多" and then "閃光需要有淡入和淡出……十字閃光的橫軸可以放更長一點，變成有點寬的閃光，這樣可以體
# 積更大同時又不影響boss的可視身體": a wide cross of light, FLARE_ARMS px from the middle at its largest
# (left-right, up-down; the helmet is 22 px wide, 48 tall), growing and brightening as it fades in and
# shrinking and dimming as it fades out with attacks.FLASH_CURVE (brightness) - its size FLARE_SCALE of
# the largest at each brightness.
FLARE_ARMS = (80, 34)
FLARE_MIN = 0.35              # the size at the faintest (the brightest is 1)


def flare_curve():
    """[(frames from the peak, size 0 .. 1, brightness 0 .. 1)] for every frame of the flash."""
    out = []
    for k in range(AT.FLASH_SPAN[0], AT.FLASH_SPAN[1] + 1):
        v = AT.flash_level(k, (0,))
        if v > 0:
            out.append((k, round(FLARE_MIN + (1 - FLARE_MIN) * v, 3), round(v, 3)))
    return out


def flash_points(m):
    """[(frame, {direction: (x, y) in frame coordinates})]: where the helmet's cross is at each
    flash (the danger time's start): the lit pixels' middle, front and sides (lit against the same
    pose unlit); from behind the cross does not show - the flare is put over the helmet, the front
    view's point mirrored."""
    out = []
    dt = AT.DANGER
    rings = [h[0] for h in m.hits]
    for r in rings:
        a = r - dt
        i = m.times.index(a)
        at = {}
        for d in ('down', 'right', 'left'):
            lit_f = m.frames()[d][i]
            dark_f = AA.render_pose(d, dict(m.states[i], glow=0.0), m.states[i - 1])
            q = [p for p, c in lit_f.items() if dark_f.get(p) != c]
            if q:
                at[d] = (sum(x for x, _ in q) / len(q), sum(y for _, y in q) / len(q))
        # a side whose visor the raised near arm covers: the other side's point mirrored (the light
        # comes from the helmet either way)
        for d, o in (('right', 'left'), ('left', 'right')):
            if d not in at:
                at[d] = (2 * rig.AX - at[o][0], at[o][1])
        at['up'] = (2 * rig.AX - at['down'][0], at['down'][1])
        out.append((a, at))
    return out


def flare(center, size, level):
    """A stand-in for the code's flare (the previews only; palette colours): a wide red cross of light,
    the long arms left-right and the short ones up-down tapering from a thick root to a point, short
    rays on the diagonals, a red glow round the middle, a small pale core. size (0 .. 1) scales it;
    level (brightness 0 .. 1) dims it: fainter it is darker red and sparser (every pixel kept by a
    fixed pattern only while the level is above its threshold), the pale core and the light red only
    near full."""
    cx, cy = round(center[0]), round(center[1])
    pale, light, red, dark, darker = (222, 189, 163), (223, 125, 112), (194, 32, 48), (168, 22, 40), (119, 18, 34)
    rank = {darker: 0, dark: 1, red: 2, light: 3, pale: 4}
    px = {}

    def colour(f):
        if f < 0.1 and level > 0.75:
            return pale
        if f < 0.3 and level > 0.5:
            return light
        return red if level > 0.45 else (dark if level > 0.25 else darker)

    def keep(q):
        # a fixed ordered pattern: at full brightness every pixel, fainter fewer (dissolving)
        th = ((q[0] * 7 + q[1] * 13) % 16) / 16.0
        return th < min(1.0, level * 1.6)

    def put(q, c):
        if keep(q) and (q not in px or rank[c] > rank[px[q]]):
            px[q] = c

    def ray(dx, dy, length, root):
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        for k in range(int(length * 2) + 1):
            t = k / 2.0
            f = t / max(1.0, length)
            half = root * (1.0 - f) ** 1.3
            for j in range(-int(half + 1), int(half + 1) + 1):
                if abs(j) <= half:
                    put((round(cx + ux * t - uy * j * 0.5), round(cy + uy * t + ux * j * 0.5)),
                        colour(max(f, abs(j) / max(1.0, half) * 0.5)))
    H, V = FLARE_ARMS[0] * size, FLARE_ARMS[1] * size
    # a small, sparse glow round the middle (the head stays visible through it)
    halo = V * 0.3
    for dx in range(-int(halo * 1.4), int(halo * 1.4) + 1):
        for dy in range(-int(halo), int(halo) + 1):
            if (dx / 1.4) ** 2 + dy * dy <= halo * halo and dx % 2 == 0 and dy % 2 == 0:
                put((cx + dx, cy + dy), red if level > 0.45 else dark)
    # the wide band left-right: thick in the middle (about V / 2 across), pointed at the ends; the
    # up-down arms short and thin
    for dx, dy, L, root in ((1, 0, H, max(3.0, V / 4.0)), (-1, 0, H, max(3.0, V / 4.0)),
                            (0, 1, V, max(1.5, V / 10.0)), (0, -1, V, max(1.5, V / 10.0))):
        ray(dx, dy, L, root)
    for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        ray(dx, dy, V * 0.45, max(1.0, V / 14.0))
    core = max(1, round(V / 9))
    if level > 0.6:
        for dx in range(-core, core + 1):
            for dy in range(-core, core + 1):
                if dx * dx + dy * dy <= core * core:
                    px[(cx + dx, cy + dy)] = pale
    return px


def with_flash(part, offset, points, d):
    """A preview sequence [(frame, hold)] with the stand-in flare drawn over the flash's frames (its
    size and brightness from flare_curve): pose holds that span the flash are split into single
    frames."""
    curve = {k: (sz, lv) for k, sz, lv in flare_curve()}
    at = {}
    for a, pt in points:
        for k, v in curve.items():
            at[offset + a + k] = (pt[d], v)
    out, t = [], 0
    for f, h in part:
        for j in range(h):
            tt = t + j
            if tt in at:
                g = dict(f)
                (c, (sz, lv)) = at[tt]
                g.update(flare(c, sz, lv))
                out.append((g, 1))
            elif out and out[-1][0] is f:
                out[-1] = (f, out[-1][1] + 1)
            else:
                out.append((f, 1))
        t += h
    return out


def metadata(ms, names=None):
    names = names or [m.sheet for m in ms]
    c, b, i, d, t = ms
    out = E.metadata([m for m in ms if m.sheet in names])
    for m in ms:
        if m.sheet not in names:
            continue
        # the blade in the ground reaches further down, raised over his head further up: a taller cell,
        # the anchor TALL_TOP lower; every position in it moves down with it
        out[m.sheet]['cell'] = list(AA.TALL)
        out[m.sheet]['anchor'] = [rig.AX + AW.EXT, rig.AY + AW.EXT + AA.TALL_TOP]
        for p in out[m.sheet]['poses']:
            for w in p['at'].values():
                for k in ('grip', 'tip'):
                    if w.get(k):
                        w[k] = [w[k][0], round(w[k][1] + AA.TALL_TOP, 1)]
        for j, s in enumerate(m.states):
            if s['t'] >= m.last or not s.get('ground'):
                continue
            bt = {dd: bite(dd, s) for dd in rig.DIRS}
            if any(bt.values()):
                out[m.sheet]['poses'][j]['bite'] = bt
    for m, top, hit in ((c, AT.CLEAVE_TOP, AT.CLEAVE_W), (t, AT.TRIPLE_TOP, AT.TRIPLE_W3)):
        if m.sheet not in names:
            continue
        k = m.times.index(top)
        hits = [{'start': a, 'frames': n} for a, n in m.hits[:-1]] + [{'start': hit + AT.CLEAVE_HOLD, 'frames': 6}]
        out[m.sheet]['delayed'] = {
            'pose': k, 'extra_hold': AT.CLEAVE_HOLD, 'frames': m.total + AT.CLEAVE_HOLD, 'hits': hits,
            'note': '延遲版：同一組圖，第 %d 張（下劈的最高點，第 %d 幀）多停 %d 幀，停住期間完全不動' % (k, top, AT.CLEAVE_HOLD)}
    for m in (i, d):
        if m.sheet in names:
            # the helmet's cross flashes at each danger time's start (user 2026-10-03): drawn lit in the
            # sheet; the flare round it is the code's - where (cell px) and when
            curve = flare_curve()
            out[m.sheet]['flash'] = [{
                'peak': a, 'start': a + curve[0][0], 'end': a + curve[-1][0],
                'size': [2 * FLARE_ARMS[0], 2 * FLARE_ARMS[1]],
                'curve': [[k, sz, lv] for k, sz, lv in curve],
                'note': '每一幀：[距離最亮那一幀幾幀, 大小(相對 size), 亮度]；十字形的光芒橫寬直窄，淡入淡出',
                'at': {dd: [round(p[0] + AW.EXT, 1), round(p[1] + AW.EXT + AA.TALL_TOP, 1)] for dd, p in at.items()}}
                for a, at in flash_points(m)]
    if i.sheet in names:
        out['boss_impact']['note'] = ('灰燼衝擊（一階段）：第 %d 幀劍插進地面＝衝擊環開始；第 30 幀起的危險預兆由程式畫；從移動出招用'
                                      ' boss_impact_<移動>_entry（雙重衝擊共用）' % AT.IMPACT_RING)
    if d.sheet in names:
        out['boss_double_impact']['note'] = ('雙重衝擊（二階段，收招已是 0.75 倍）：第 %d、%d 幀兩次插進地面＝兩個衝擊環'
                                         % (AT.IMPACT_RING, AT.IMPACT_RING2))
    if t.sheet in names:
        out['boss_triple']['note'] = ('三斬（只在二階段）：照 hold_phase2 播（收招 0.9 秒）；第三刀被完美彈返時播 boss_cleave_bounce'
                                  '（第一張就是第三刀砍到那一張）')
        out['boss_triple']['game_step'] = {'distance': AT.TWIN_STEP, 'frames': [AT.TWIN_STEP_FROM, AT.W2 - 1]}
    return out


def lambda_seq(title, cap, fn):
    return title, cap, fn


def sequences(ms):
    """[(title, caption, parts())]: parts drawn only when asked for (each part of the export draws its own)."""
    c, b, im, db, tr = ms
    seq = []
    seq.append(lambda_seq('cleave', '墜誓下劈（一階段）：扛劍站著 → 起手 1.0 秒（0.8 秒舉到最高點）→ 判定 0.1 秒 → 收招 1.2 秒（劍卡在地上）→ 扛劍站著',
                lambda: {d: E.carry_for(d, 30) + E.held(c.frames()[d], c.holds) + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(lambda_seq('cleave_delayed', '延遲版：舉到最高點停住 0.6 秒（完全不動；劍身符文閃爍由程式畫）→ 劈下（總起手 1.6 秒）',
                lambda: {d: E.carry_for(d, 30) + E.held(c.frames()[d], delayed_holds(c)) + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(lambda_seq('cleave_p2', '二階段：收招縮短成 0.9 秒（同一組圖）',
                lambda: {d: E.carry_for(d, 30) + E.held(c.frames()[d], c.holds_p2) + E.carry_for(d, 40) for d in rig.DIRS}))
    # the entry poses (ENTRY_TIMES), then the cleave's own from the pose at ENTRY_END (the raise is
    # sampled more densely than every 4 frames: its pose index there is not len(ENTRY_TIMES))
    eh = [b - a for a, b in zip(AT.ENTRY_TIMES, AT.ENTRY_TIMES[1:] + (AT.ENTRY_END,))]
    n = c.times.index(AT.ENTRY_END)
    seq.append(lambda_seq('cleave_walk', '往前走時出招（從走路循環第 10 張直接接下劈）',
                lambda: {d: E.loop_for(d, 'walk', 0, 10) + E.held(c.entries()[('walk', 10)][d], eh) + E.held(c.frames()[d][n:], c.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(lambda_seq('cleave_strafe', '側移時出招（從往左側移的循環第 5 張直接接下劈）',
                lambda: {d: E.loop_for(d, 'strafe_l', 0, 5) + E.held(c.entries()[('strafe_l', 5)][d], eh) + E.held(c.frames()[d][n:], c.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    i = c.times.index(AT.CLEAVE_CONTACT)
    seq.append(lambda_seq('cleave_bounce', '在砍到的那一刻被完美彈返：被彈開 1.2 秒 → 扛劍站著',
                lambda: {d: E.carry_for(d, 20) + E.held(c.frames()[d][:i], c.holds[:i]) + E.held(b.frames()[d], b.holds)
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(lambda_seq('impact', '灰燼衝擊（一階段，不可格擋）：劍從肩上繞到身前、舉過頭頂 → 舉著劍蓄力 0.6 秒，蓄力一開始頭盔的十字閃一下紅光（十字形的光芒由程式畫，這裡畫的是示意）→ 站著把劍插進地面、衝擊環擴散（由程式畫）→ 收招 1.4 秒 → 扛劍站著',
                lambda: {d: with_flash(E.carry_for(d, 30) + E.held(im.frames()[d], im.holds) + E.carry_for(d, 40), 30,
                                       flash_points(im), d) for d in rig.DIRS}))
    seq.append(lambda_seq('double_impact', '雙重衝擊（二階段）：插地 → 劍留在地上，第二個環的蓄力一開始十字再閃一下 → 全身往下壓、放出第二個衝擊環（劍不拔出來）→ 收招',
                lambda: {d: with_flash(E.carry_for(d, 30) + E.held(db.frames()[d], db.holds) + E.carry_for(d, 40), 30,
                                       flash_points(db), d) for d in rig.DIRS}))
    advs = [s_['adv'] for s_ in tr.states]
    step = AT.TWIN_STEP
    seq.append(lambda_seq('triple', '三斬（二階段）：雙斬兩刀（第二刀前遊戲把 Boss 往前移 %d px）→ 第二刀之後 1.0 秒下劈 → 收招 0.9 秒' % step,
                lambda: {d: E.carry_for(d, 30) + E.travel(d, E.held(tr.frames()[d], tr.holds_p2), advs) + E.travel(d, E.carry_for(d, 40), [step])
                 for d in rig.DIRS}))
    seq.append(lambda_seq('triple_delayed', '三斬（延遲版）：第三刀舉到最高點停住 0.6 秒',
                lambda: {d: E.carry_for(d, 30) + E.travel(d, E.held(tr.frames()[d], delayed_holds(tr, tr.holds_p2, AT.TRIPLE_TOP)), advs)
                 + E.travel(d, E.carry_for(d, 40), [step]) for d in rig.DIRS}))
    return seq


def strips(m, d, path):
    import preview
    labels = [f'{i}:{t}' for i, t in enumerate(m.times)]
    preview.contact(m.frames()[d], k=1, cols=12, box=BOX, labels=labels).save(path)


KEY_POSES = {
    'boss_cleave': [(0, '扛劍站著'), (18, '舉起'), (AT.CLEAVE_TOP, '最高點（延遲版停在這裡）'), (57, '劈下'),
                    (AT.CLEAVE_CONTACT, '砍到'), (72, '劍卡在地上'), (102, '拔出'), (118, '立在身前')],
    'boss_impact': [(9, '劍從肩上繞到身前'), (18, '劍尖朝下'), (AT.IMPACT_TOP, '舉過頭頂蓄力（十字亮紅光）'), (63, '往下插'),
                    (AT.IMPACT_RING, '插進地面＝衝擊環'), (100, '插著不動'), (AT.IMPACT_PULL + 6, '往上拔出'),
                    (AT.IMPACT_PULL + 24, '繞回肩上')],
    'boss_triple': [(AT.W2 + 8, '第二刀揮完'), (AT.W2 + 22, '重心回右腳、劍從右邊舉起'), (AT.W2 + 30, '左腳收回'),
                    (AT.TRIPLE_TOP, '最高點'), (AT.TRIPLE_W3 + 3, '第三刀砍到'), (AT.TRIPLE_W3 + 10, '劍卡在地上')],
}


def key_poses(m, path, cw=300, ch=372):
    """The key poses, four directions side by side (each drawn at its own frame, 1x; the sheet
    is doubled)."""
    from PIL import Image, ImageDraw
    import preview
    top, left = 30, 70
    picks = KEY_POSES[m.sheet]
    out = Image.new('RGB', (left + len(picks) * cw, top + 4 * ch), (42, 40, 44))
    d = ImageDraw.Draw(out)
    f = preview.font(13)
    for r, dd in enumerate(rig.DIRS):
        d.text((6, top + r * ch + 130), NAMES[dd], font=f, fill=(235, 228, 220))
    for c, (t, lab) in enumerate(picks):
        sts = AT.poses(m.clip, [max(0, t - 2), t])
        d.text((left + c * cw + 4, 8), lab, font=f, fill=(235, 228, 220))
        for r, dd in enumerate(rig.DIRS):
            fr = AA.render_pose(dd, sts[1], sts[0])
            out.paste(preview.render(fr, (18, -92, 18 + cw, -92 + ch), 1, bg=(42, 40, 44)), (left + c * cw, top + r * ch))
    out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 下劈</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）C3 下劈：墜誓下劈、灰燼衝擊、三斬</h1>
<p>還沒接進遊戲。雙手把劍從肩上舉過頭頂（雙手在王冠上方，劍往後倒在頭的上方，刀鋒朝前後：側面看到整片劍身，正面、背面只看到一條細細的劍），身體往後挺；手臂短、頭盔大，照真的手臂長度雙手只到額頭，所以舉過頭的那段手臂畫長（最多 1.45 倍，劈下去時縮回原長）；劈下時右腳踏出、和砍到同時落地，重心壓到前腳、上身前傾；劍尖在判定期間經過 165px、主角的高度，接著砍進地面卡住（收招一開始劍卡在地上不動）；之後重心退回左腳、把劍沿著劍身拔出來，立在右肩前、放回肩上，右腳收回。延遲版用同一組圖，最高點那一張多停 0.6 秒。灰燼衝擊（不可格擋）是插劍：劍從肩上繞到身前、劍尖朝下，雙手把劍舉過頭頂，舉著劍蓄力 0.6 秒（蓄力一開始頭盔的十字閃一下紅光），再站著把劍插進身前的地面（衝擊環從 Boss 擴散）；二階段的雙重衝擊劍留在地上，第二個環前十字再閃一次，全身往下壓放出第二個環。三斬是雙斬的兩刀接下劈：第二刀揮完後左腳收回、劍從右邊舉到最高點，之後和下劈一樣。四個方向：朝下、朝右、朝上、朝左（朝左不是鏡像）。刀光、劍身符文、白光預兆、衝擊環、地面的裂痕由程式畫，這裡沒有。</p>
<h2>關鍵姿勢（四個方向，2 倍）</h2>
%(keys)s
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張）</h2>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''


PARTS = {      # --part=: one group at a time (each run stays short); without it, all of them
    'cleave': ('boss_cleave', 'boss_cleave_bounce'),
    'impact': ('boss_impact', 'boss_double_impact'),
    'triple': ('boss_triple',),
}
SEQ_OF = {'cleave': ('cleave', 'cleave_delayed', 'cleave_p2', 'cleave_walk', 'cleave_strafe', 'cleave_bounce'),
          'impact': ('impact', 'double_impact'), 'triple': ('triple', 'triple_delayed')}


def hand_picks(c, im, tr):
    return {c.sheet: [('扛劍站著', 0), ('舉起', 18), ('最高點', AT.CLEAVE_TOP), ('劈下', 57), ('過水平', 61),
                      ('砍到', AT.CLEAVE_CONTACT), ('劍卡在地上', 72), ('拔出', 102), ('立在身前', 118), ('放回肩上', 126)],
            im.sheet: [('繞到身前', 9), ('劍尖朝下', 18), ('舉過頭頂', AT.IMPACT_TOP), ('往下插', AT.IMPACT_RING - 2),
                       ('插地', AT.IMPACT_RING), ('插著', 100), ('拔出', AT.IMPACT_PULL + 6), ('繞回肩上', AT.IMPACT_PULL + 24)],
            tr.sheet: [('第二刀揮完', AT.W2 + 8), ('劍從右邊舉起', AT.TRIPLE_LBACK[0]), ('左手握回', AT.W2 + 38),
                       ('最高點', AT.TRIPLE_TOP), ('第三刀砍到', AT.TRIPLE_W3 + 3)]}


def index_html(ms, seqs):
    """The preview page from whatever files the parts have written so far."""
    have = set(os.listdir(OUT))
    seq_html = ''
    for title, cap, _ in seqs:
        if f'{title}_all.gif' not in have:
            continue
        seq_html += f'<h3>{cap}</h3><figure><img src="{title}_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>'
        seq_html += ''.join(f'<figure><video src="{title}_{d}.mp4" autoplay loop muted playsinline controls></video>'
                            f'<figcaption>{NAMES[d]}（60fps，3 倍）</figcaption></figure>' for d in rig.DIRS
                            if f'{title}_{d}.mp4' in have)
    c, b, im, db, tr = ms
    picks = hand_picks(c, im, tr)
    hands_html = ''.join(f'<figure><img src="hands_{m.sheet}.png"><figcaption>{m.caption}：' + '、'.join(lab for lab, _ in picks[m.sheet])
                         + '</figcaption></figure>' for m in (c, im, tr) if f'hands_{m.sheet}.png' in have)
    legs_html = ''.join(f'<figure><img src="legs_{m.sheet}.png"><figcaption>{m.caption}（每一張，左上角是第幾個戰鬥幀）</figcaption></figure>'
                        for m in (c, im, db, tr) if f'legs_{m.sheet}.png' in have)
    sheets_html = ''.join(f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）'
                          f'</figcaption></figure>' for m in ms for d in rig.DIRS if f'{m.sheet}_{d}.png' in have)
    keys_html = ''.join(f'<figure><img src="key_poses_{m.sheet}.png"><figcaption>{m.caption}</figcaption></figure><br>'
                        for m in (c, im, tr) if f'key_poses_{m.sheet}.png' in have)
    if 'impact_glow.png' in have:
        keys_html += ('<figure><img src="impact_glow.png"><figcaption>灰燼衝擊：頭盔的十字跟著閃光變亮（第 24、26、30、38、44 幀；'
                      '朝下、朝右、朝左，4 倍）：淡入、最亮、淡出。十字形的光芒由程式畫（json 的 flash），這張只有角色身上的十字</figcaption></figure><br>')
    if 'impact_flare.png' in have:
        keys_html += ('<figure><img src="impact_flare.png"><figcaption>灰燼衝擊：十字紅光閃一下，淡入、最亮、淡出（四個方向，2 倍）。'
                      '光芒由程式畫，這是示意：最大時寬 160px、高 68px（頭盔寬 22px），紅色為主（json 的 flash：時間、亮度曲線、位置、size）</figcaption></figure><br>')
    if 'top_v1_v2.png' in have:
        keys_html += ('<figure><img src="top_v1_v2.png"><figcaption>最高點：第一版（上，雙手在下巴、劍直立在身前、劍面斜 45°）和這一版'
                      '（下，雙手舉過頭頂、劍往後倒、刀鋒朝前後），每一列四個方向，2 倍</figcaption></figure>')
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html, 'keys': keys_html})


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    part = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--part=')), None)
    names = PARTS[part] if part else sum(PARTS.values(), ())
    os.makedirs(OUT, exist_ok=True)
    ms = moves()
    mine = [m for m in ms if m.sheet in names]
    for m in mine:
        E.write_sheet(os.path.join(E.SHEETS, m.sheet + '.png'), [m.frames()], AA.TALL, AA.TALL_TOP)
        if m.has_entries:
            ents = m.entries()
            for kind in AW.KINDS:
                E.write_sheet(os.path.join(E.SHEETS, f'{m.sheet}_{EA.SHEET_OF[kind][len("boss_"):]}_entry.png'),
                              [ents[(kind, e)] for e in AT.ENTRY_FROM], AA.TALL, AA.TALL_TOP)
        for d in rig.DIRS:
            strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)), flush=True)
        if m.holds_p2:
            print('  phase 2', m.holds_p2, sum(m.holds_p2), flush=True)
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    data.update({k: v for k, v in metadata(ms, names).items() if k in names})
    with open(path, 'w') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    seqs = sequences(ms)
    for title, cap, fn in seqs:
        if part and title not in SEQ_OF[part]:
            continue
        parts = fn()
        EH.gif4(os.path.join(OUT, f'{title}_all.gif'), parts, box=BOX)
        if video_ok:
            for d in rig.DIRS:
                EH.video(os.path.join(OUT, f'{title}_{d}.mp4'), EH.timeline(parts[d]), box=BOX)
        print('preview', title, flush=True)
    c, b, im, db, tr = ms
    for m in (c, im, tr):
        if m.sheet in names:
            key_poses(m, os.path.join(OUT, f'key_poses_{m.sheet}.png'))
    picks = hand_picks(c, im, tr)
    for m in (c, im, tr):
        if m.sheet in names:
            E.hands_sheet(os.path.join(OUT, f'hands_{m.sheet}.png'), m,
                          [(lab, max(i for i, t in enumerate(m.times) if t <= at)) for lab, at in picks[m.sheet]])
    for m in (c, im, db, tr):
        if m.sheet in names:
            E.legs_sheet(os.path.join(OUT, f'legs_{m.sheet}.png'), m)
    index_html(ms, seqs)
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)', flush=True)


if __name__ == '__main__':
    main()
