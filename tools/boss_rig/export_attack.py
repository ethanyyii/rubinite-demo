"""Boss attacks (攻擊): sprite sheets and previews.

    python3 tools/boss_rig/export_attack.py [--no-video] [名稱…]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game). Rows: down, right, up, left;
cells: the attack container 384x336, foot anchor (192, 272). The entry sheets (starting from a
move) hold 16 rows: four directions for each of the loop's poses 0, 5, 10, 15. Timing: combat
frames per pose (MOVES below; README table). Previews -> docs/art-preview/boss/attack/.
"""
import os
import shutil
import sys
from PIL import Image, ImageDraw
import boss as B
import rig
import gait
import limb
import anim_walk as AW
import anim_kneel as K
import anim_attack as AA
import attacks as AT
import attack3d as A
import preview
import export_anim as EA
import export_hit as EH

SHEETS = EA.SHEETS
OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'attack')
NAMES = EA.NAMES
BOX = (-90, -56, 346, 262)          # preview window (small-frame coordinates; wide enough for the twin slash's step)
SCREEN_FWD = {'right': (1, 0), 'left': (-1, 0), 'down': (0, 1), 'up': (0, -1)}     # the game moves him 1:1 on screen


def travel(d, parts, advs):
    """Preview parts [(frame, hold)] moved on screen by how far the game has moved the Boss at
    each (advs: px, one per part) - the previews show him where the game puts him."""
    fx, fy = SCREEN_FWD[d]
    out = []
    for (f, h), a in zip(parts, advs):
        dx, dy = round(fx * a), round(fy * a)
        out.append(({(x + dx, y + dy): c for (x, y), c in f.items()} if (dx or dy) else f, h))
    return out


def phase2(holds, times, from_t, frames):
    """The same poses with the recovery (poses from `from_t` on) re-timed to `frames` (the
    second phase's recovery is 0.75 as long, boss-veltharis §5): each hold scaled, rounding
    carried so the total is exact, no hold under 1."""
    head = [h for h, t in zip(holds, times) if t < from_t]
    tail = [h for h, t in zip(holds, times) if t >= from_t]
    k = frames / sum(tail)
    out, acc, done = [], 0.0, 0
    for h in tail:
        acc += h * k
        n = max(1, round(acc) - done)
        out.append(n)
        done += n
    out[-1] += frames - sum(out)
    return head + out


class Move:
    """One attack's clip, its poses and their holds, for each way the game plays it."""

    def __init__(self, sheet, clip, total, hits, caption, phase2_recovery=None, entries=False, first=None,
                 entry_times=False):
        """entries: draw the starts from a move (the entry sheets); entry_times: only sample the
        same opening poses (an attack that shares another's entry sheets: the twin slash)."""
        self.sheet, self.clip, self.total, self.hits, self.caption = sheet, clip, total, hits, caption
        self.has_entries = entries
        self.first = first              # (Move, pose index): pose 0 is that move's frame (the bounce's contact)
        last = clip.keys[-1][0]
        must = {0, last}
        if entries or entry_times:
            must |= set(AT.ENTRY_TIMES) | {AT.ENTRY_END}
        must |= set(clip.musts)          # the game moving him every frame there (the twin slash's step)
        for start, n in hits:
            must |= {start, start + n}
        self.times, self.holds = AT.sample(clip, total, must=sorted(must))
        self.holds_p2 = None
        if phase2_recovery:
            end_hit = hits[-1][0] + hits[-1][1]
            self.holds_p2 = phase2(self.holds, self.times, end_hit, phase2_recovery)
        self.states = AT.poses(clip, self.times)
        self.last = last

    def frames(self):
        """{direction: [frames]}: pose 0 and the final carry drawn by the carry's own renderer
        (anim_kneel: the attack starts from and ends in exactly the pose he moves in)."""
        if not hasattr(self, '_fr'):
            fr = {}
            for d in rig.DIRS:
                out = []
                for i, s in enumerate(self.states):
                    if i == 0 and self.first:
                        m, j = self.first
                        out.append(m.frames()[d][j])
                    elif i == 0 or s['t'] >= self.last:
                        out.append(carry_frame(d))
                    else:
                        out.append(AA.render_pose(d, s, self.states[i - 1]))
                fr[d] = out
            self._fr = fr
        return self._fr

    def entries(self):
        """{(kind, pose): {direction: [frames for ENTRY_TIMES]}}: the first poses when the attack
        starts from a move (attacks.entry)."""
        if not hasattr(self, '_en'):
            out = {}
            for kind in AW.KINDS:
                for e in AT.ENTRY_FROM:
                    st = AT.entry(self.clip, kind, e)
                    fr = {}
                    for d in rig.DIRS:
                        f = [AW.frames(d, kind)[e]]
                        for i in range(1, len(st)):
                            f.append(AA.render_pose(d, st[i], st[i - 1]))
                        fr[d] = f
                    out[(kind, e)] = fr
            self._en = out
        return self._en


_carry = {}


def carry_frame(d):
    if d not in _carry:
        c = AW.Clip('carry', [K.CARRY_STAND], lambda k: K.CARRY_STAND)
        _carry[d] = K.render(d, c)[0]
    return _carry[d]


def moves():
    # veltharis_data: royal_sweep 起手 0.8 / 判定 0.15 / 收招 0.9 (二階段 0.675 -> 41 frames);
    # twin_slash 起手 0.8 / 判定 0.1, 0.9 later 判定 0.1, 收招 1.0 (phase 1 only)
    c1 = Move('boss_c1', AT.c1(), 111, [(48, 9)], '王權橫掃（C1 橫斬，雙手）', phase2_recovery=41, entries=True)
    tw = Move('boss_twin', AT.twin(), 168, [(48, 6), (102, 6)], '雙斬（C1 橫斬 → C2 反手橫斬，雙手）', entry_times=True)
    # BOUNCED (1.2 s): from each move's own contact (the hit box's middle)
    b1 = Move('boss_c1_bounce', AT.c1_bounce(), 72, [], '王權橫掃被彈開', first=(c1, c1.times.index(AT.W + 4)))
    b2 = Move('boss_twin_bounce', AT.twin_bounce(), 72, [], '雙斬第二刀被彈開', first=(tw, tw.times.index(AT.W2 + 3)))
    return [c1, tw, b1, b2]


def write_sheet(path, groups):
    """groups: [{direction: [frames]}] -> one sheet in the attack container."""
    cw, ch = AW.BIG
    off = AW.EXT
    n = len(groups[0]['down'])
    im = Image.new('RGBA', (cw * n, ch * 4 * len(groups)), (0, 0, 0, 0))
    r = 0
    for g in groups:
        for d in rig.DIRS:
            for c, f in enumerate(g[d]):
                im.alpha_composite(rig.image({(x + off, y + off): v for (x, y), v in f.items()}, (cw, ch)), (c * cw, r * ch))
            r += 1
    im.save(path)


# ------------------------------------------------------------------ previews
def held(frames_, holds):
    return list(zip(frames_, holds))


def carry_for(d, n):
    return [(carry_frame(d), n)]


def loop_for(d, kind, start, n):
    fr = AW.frames(d, kind)
    return [(fr[(start + i) % gait.POSES], gait.HOLD) for i in range(n)]


def sequences(ms):
    seq = []
    c1, tw, b1, b2 = ms
    seq.append(('c1', '王權橫掃（一階段）：扛劍站著 → 起手 0.8 秒 → 判定 0.15 秒 → 收招 0.9 秒 → 扛劍站著',
                {d: carry_for(d, 30) + held(c1.frames()[d], c1.holds) + carry_for(d, 40) for d in rig.DIRS}))
    seq.append(('c1_p2', '王權橫掃（二階段：收招縮短成 0.675 秒，同一組圖）',
                {d: carry_for(d, 30) + held(c1.frames()[d], c1.holds_p2) + carry_for(d, 40) for d in rig.DIRS}))
    tw_adv = [s['adv'] for s in tw.states]
    step = AT.TWIN_STEP
    seq.append(('twin', '雙斬：起手 0.8 秒 → 第一刀（0.1 秒）→ 0.9 秒後第二刀（0.1 秒；第二刀前遊戲把 Boss 往前移 %d px）→ 收招 1.0 秒 → '
                '扛劍站著（比開始時前進一步）' % step,
                {d: carry_for(d, 30) + travel(d, held(tw.frames()[d], tw.holds), tw_adv) + travel(d, carry_for(d, 40), [step])
                 for d in rig.DIRS}))
    en = c1.entries()[('walk', 10)]
    n = len(AT.ENTRY_TIMES)
    seq.append(('c1_walk', '往前走時出招（從走路循環第 10 張直接接王權橫掃）',
                {d: loop_for(d, 'walk', 0, 10) + held(en[d], c1.holds[:n]) + held(c1.frames()[d][n:], c1.holds[n:])
                 + carry_for(d, 40) for d in rig.DIRS}))
    en = c1.entries()[('strafe_r', 5)]
    seq.append(('twin_strafe', '側移時出招（從往右側移的循環第 5 張直接接雙斬；開頭和王權橫掃同一組）',
                {d: loop_for(d, 'strafe_r', 0, 5) + held(en[d], tw.holds[:n])
                 + travel(d, held(tw.frames()[d][n:], tw.holds[n:]), tw_adv[n:]) + travel(d, carry_for(d, 40), [step])
                 for d in rig.DIRS}))
    i1 = c1.times.index(AT.W + 4)
    seq.append(('c1_bounce', '王權橫掃在砍到的那一刻被完美彈返：被彈開 1.2 秒 → 扛劍站著',
                {d: carry_for(d, 20) + held(c1.frames()[d][:i1], c1.holds[:i1]) + held(b1.frames()[d], b1.holds)
                 + carry_for(d, 40) for d in rig.DIRS}))
    i2 = tw.times.index(AT.W2 + 3)
    seq.append(('twin_bounce', '雙斬第二刀被完美彈返：被彈開 1.2 秒 → 扛劍站著',
                {d: carry_for(d, 20) + travel(d, held(tw.frames()[d][:i2], tw.holds[:i2]), tw_adv[:i2])
                 + travel(d, held(b2.frames()[d], b2.holds), [step] * len(b2.holds)) + travel(d, carry_for(d, 40), [step])
                 for d in rig.DIRS}))
    return seq


def strips(m, d, path):
    fr = m.frames()[d]
    labels = [f'{i}:{t}' for i, t in enumerate(m.times)]
    preview.contact(fr, k=1, cols=12, box=BOX, labels=labels).save(path)


def grip_at(m, d, i):
    """Where the right fist is in pose i (frame coordinates; the carry's own record for the
    poses drawn by the carry's renderer)."""
    s = m.states[i]
    rec = AA.SWORD.get((d, s['name'], s['i']))
    if rec and not (i == 0 or s['t'] >= m.last) or (rec and m.first):
        g = rec[2]
    else:
        carry_frame(d)
        g = AW.SWORD_DRAWN[(d, 'carry', 0)][1]['grip']
    return (2 * rig.AX - g[0], g[1]) if d == 'left' else g


def hands_sheet(path, m, picks, k=4):
    """The hands, the hilt and the shoulders, cropped around the grip, four directions."""
    rows = []
    fr = m.frames()
    for label, i in picks:
        tiles = []
        for d in rig.DIRS:
            g = grip_at(m, d, i)
            box = (round(g[0]) - 40, round(g[1]) - 40, round(g[0]) + 40, round(g[1]) + 40)
            tiles.append(preview.render(fr[d][i], box, k, ground=False))
        rows.append((label, tiles))
    EA._labelled(rows, path, rows[0][1][0].size, left=260)


def legs_sheet(path, m, k=4):
    """The side view's legs alone with hip, knee, ankle lines (green: the near leg)."""
    lay = rig.Layout('right')
    reach = max(s['feet'][k][0] + s.get('adv', 0.0) for s in m.states for k in 'RL')
    box = (60, 110, max(200, round(rig.AX + reach + 40)), 214)
    tiles = []
    for s in m.states:
        hip_z = gait.HIP_REST - s['D']
        Ls = []
        a = s.get('adv', 0.0)          # on the ground: where the game has him added back
        for side_ in ('R', 'L'):
            x, out, z, pitch, down = s['feet'][side_][:5]
            hx = AT.hip_x(s, side_)
            L = gait.solve(hip_z, (x - hx, z), pitch, down)
            Ls.append({kk: ((v[0] + hx + a, v[1]) if kk in ('hip', 'knee', 'ankle') else v) for kk, v in L.items()})
        near, far = Ls
        f = {(x, y - AW.FAR_UP): v for (x, y), v in limb.darken(limb.leg_pixels(far)).items()}
        f.update(limb.leg_pixels(near))
        t = preview.render(f, box, k)
        dr = ImageDraw.Draw(t)
        for L, up, col in ((far, AW.FAR_UP, (90, 150, 255)), (near, 0, (120, 255, 120))):
            J = limb.joints_work(L, lay)
            pts = [((J[n][0] / B.WORK - box[0]) * k, (J[n][1] / B.WORK - up - box[1]) * k) for n in ('hip', 'knee', 'ankle')]
            dr.line(pts, fill=col, width=2)
        dr.text((3, 3), str(s['t']), fill=(255, 255, 0))
        tiles.append(t)
    cols = 8
    tw_, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new('RGB', (cols * (tw_ + 4), rows * (th + 4)), preview.BG)
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * (tw_ + 4), (i // cols) * (th + 4)))
    out.save(path)


def metadata(ms):
    """What the game needs to play the sheets: for every sheet its poses (combat frame they
    start at, hold, the second phase's hold), the hit boxes (frames), and per pose and
    direction where the right fist (the grip) and the sword's tip are in the cell (px from the
    cell's top left; the foot anchor is (192, 272)) - for the trails and the rune glow, which
    are drawn by code."""
    out = {}
    for m in ms:
        poses = []
        for i, s in enumerate(m.states):
            p = {'t': s['t'], 'hold': m.holds[i], 'advance': round(s.get('adv', 0.0), 2)}
            if m.holds_p2:
                p['hold_phase2'] = m.holds_p2[i]
            where = {}
            for d in rig.DIRS:
                src = (m.first[0], m.first[1]) if (i == 0 and m.first) else (m, i)
                ss = src[0].states[src[1]]
                rec = AA.SWORD.get((d, ss['name'], ss['i']))
                if rec:
                    pl, g = rec[1], rec[2]
                else:
                    carry_frame(d)
                    pl = AW.SWORD_DRAWN[(d, 'carry', 0)][1]
                    g = pl['grip']
                view = 'right' if d in ('right', 'left') else ('front' if d == 'down' else 'back')
                tip = K.swd.tip_of(view, pl) if 'axis' in pl else None
                if d == 'left':
                    g = (2 * rig.AX - g[0], g[1])
                    tip = (2 * rig.AX - tip[0], tip[1]) if tip else None
                where[d] = {'grip': [round(g[0] + AW.EXT, 1), round(g[1] + AW.EXT, 1)],
                            'tip': [round(tip[0] + AW.EXT, 1), round(tip[1] + AW.EXT, 1)] if tip else None}
            p['at'] = where
            poses.append(p)
        out[m.sheet] = {'cell': list(AW.BIG), 'anchor': [rig.AX + AW.EXT, rig.AY + AW.EXT], 'frames': m.total,
                        'hits': [{'start': a, 'frames': n} for a, n in m.hits], 'poses': poses}
        if m.sheet == 'boss_twin':
            # the game moves him forward before the second hit (veltharis_data TWIN_STEP_DISTANCE /
            # TIME); each pose's 'advance' is how far it has at that pose's first frame
            out[m.sheet]['game_step'] = {'distance': AT.TWIN_STEP, 'frames': [AT.TWIN_STEP_FROM, AT.W2 - 1]}
    return out


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 攻擊</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）攻擊：橫斬、反手橫斬（雙手）</h1>
<p>還沒接進遊戲。四個方向：朝下、朝右、朝上、朝左（朝左不是朝右的鏡像：右手在劍首那一端、左手在護手上方；朝左時右手在遠側）。每一招從扛劍出手、收招回到扛劍。刀光、劍身符文的預兆、火花由程式畫，這裡沒有。</p>
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張）</h2>
<p>一次只動一隻腳：起手時兩腳不動，揮劍時踏出一隻腳、落地和砍到同時，收招時那隻腳收回來。</p>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    os.makedirs(SHEETS, exist_ok=True)
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    ms = moves()
    sheets_html = ''
    for m in ms:
        write_sheet(os.path.join(SHEETS, m.sheet + '.png'), [m.frames()])
        if m.has_entries:
            ents = m.entries()
            for kind in AW.KINDS:
                write_sheet(os.path.join(SHEETS, f'{m.sheet}_{EA.SHEET_OF[kind][len("boss_"):]}_entry.png'),
                            [ents[(kind, e)] for e in AT.ENTRY_FROM])
        for d in rig.DIRS:
            strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
            sheets_html += f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）</figcaption></figure>'
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)))
        if m.holds_p2:
            print('  phase 2', m.holds_p2, sum(m.holds_p2))
    import json
    with open(os.path.join(SHEETS, 'boss_attacks.json'), 'w') as fh:
        json.dump(metadata(ms), fh, ensure_ascii=False, indent=1)
    seq_html = ''
    for title, cap, parts in sequences(ms):
        EH.gif4(os.path.join(OUT, f'{title}_all.gif'), parts, box=BOX)
        seq_html += f'<h3>{cap}</h3><figure><img src="{title}_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>'
        if video_ok:
            for d in rig.DIRS:
                EH.video(os.path.join(OUT, f'{title}_{d}.mp4'), EH.timeline(parts[d]), box=BOX)
            seq_html += ''.join(f'<figure><video src="{title}_{d}.mp4" autoplay loop muted playsinline controls></video>'
                                f'<figcaption>{NAMES[d]}（60fps，3 倍）</figcaption></figure>' for d in rig.DIRS)
    hands_html = ''
    W, W2 = AT.W, AT.W2
    for m, picks in ((ms[0], [('扛劍站著', 0), ('左手握上來', 8), ('起手（劍舉在右肩旁）', 40), ('砍到（正前方）', W + 4),
                              ('揮完（左邊低處）', W + 28), ('收招：劍立在身前', W + 46)]),
                     (ms[1], [('第二刀起手（劍舉在左肩旁）', W + 46), ('第二刀砍到（正前方）', W2 + 3),
                              ('第二刀揮完（右手單手）', W2 + 14), ('收招：舉到肩上', W2 + 48)])):
        name = f'hands_{m.sheet}.png'
        # the pose shown at each time (the last one starting at or before it)
        picks = [(lab, max(i for i, t in enumerate(m.times) if t <= at)) for lab, at in picks]
        hands_sheet(os.path.join(OUT, name), m, picks)
        hands_html += f'<figure><img src="{name}"><figcaption>{m.caption}：' + '、'.join(lab for lab, _ in picks) + '</figcaption></figure>'
    legs_html = ''
    for m in ms[:2]:
        name = f'legs_{m.sheet}.png'
        legs_sheet(os.path.join(OUT, name), m)
        legs_html += f'<figure><img src="{name}"><figcaption>{m.caption}（每一張，左上角是第幾個戰鬥幀）</figcaption></figure>'
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html})
    print('wrote', SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)')


if __name__ == '__main__':
    main()
