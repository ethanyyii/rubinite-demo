"""Boss king's leap (墜王之躍, C7 躍起與落地, phase 2): sprite sheets and previews.

    python3 tools/boss_rig/export_leap.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_leap.png, boss_leap_bounce.png (parried),
boss_leap_<move>_entry.png (starting from a move). The attack container 384x336, foot anchor (192, 272); rows down,
right, up, left. In the air (frames 42 .. 89) the height is drawn in the sprite (each pose's 'lift' in
boss_attacks.json: px he is off the ground, for the code's shadow); the game moves him along the ground from the
take-off to the landing place in a straight line (veltharis_data airborne_start / boss_sim._tick_leap), the sheet
does not. Timing and the grip / tip per pose are added to boss_attacks.json (the other attacks' entries are kept).
Previews -> docs/art-preview/boss/leap/ (one sequence in place, one moved 240 px along the ground as the game does).
"""
import json
import os
import shutil
import sys
import rig
import anim_walk as AW
import attacks as AT
import anim_attack as AA
import export_anim as EA
import export_hit as EH
import export_attack as E
import boss as B

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'leap')
NAMES = EA.NAMES
BOX = (-90, -150, 346, 262)                 # in place: room over his head for the leap
TRAVEL = 240.0                              # px the previews move him through the air (the game's distance is not fixed)
TRAVEL_BOX = (-250, -230, 506, 430)


def moves():
    # veltharis_data kings_leap: 起手 0.7 / 騰空 0.8 (the landing is the hit) / 判定 0.1 / 收招 1.0 (phase 2's own)
    m = E.Move('boss_leap', AT.leap(), AT.LEAP_END, [(AT.LEAP_W, 6)], '墜王之躍（C7 躍起與落地，二階段）', entries=True,
               entry_spec=AT.LEAP_ENTRY)
    b = E.Move('boss_leap_bounce', AT.leap_bounce(), 72, [], '墜王之躍被彈開', first=(m, m.times.index(AT.LEAP_CONTACT)))
    return [m, b]


def metadata(ms):
    out = E.metadata(ms)
    m, b = ms
    for mv in ms:
        for p, s in zip(out[mv.sheet]['poses'], mv.states):
            p['lift'] = round(s.get('lift', 0.0), 1)
    out[m.sheet]['air'] = {'from': AT.LEAP_UP, 'to': AT.LEAP_W - 1, 'lock': AT.LEAP_LOCK}
    out[m.sheet]['note'] = ('墜王之躍（二階段）：第 %d–%d 幀騰空（遊戲把 Boss 從起跳點直線移到落點；每張的 lift 是他離地多高，'
                            '給程式畫地上的影子；精靈圖裡已經畫高了，不要再往上移），第 %d 幀落地＝判定（右拳砸在地上，衝擊波由程式畫）。'
                            '從移動出招用 boss_leap_<移動>_entry（第 %d 幀接回）。被完美彈返：boss_leap_bounce 的第一張就是第 %d 幀那一張'
                            % (AT.LEAP_UP, AT.LEAP_W - 1, AT.LEAP_W, AT.LEAP_ENTRY[2], AT.LEAP_CONTACT))
    out[b.sheet]['note'] = '墜王之躍被完美彈返（1.2 秒）：被震起來、站起來、從背上拔劍放回肩上；最後一張是扛劍站著'
    return out


def advs(m):
    """px the preview moves him along the ground at each pose (the game's straight line, boss_sim._tick_leap)."""
    out = []
    for s in m.states:
        t = s['t']
        u = (t - AT.LEAP_UP + 1) / (AT.LEAP_W - AT.LEAP_UP)
        out.append(TRAVEL * min(1.0, max(0.0, u)) if t >= AT.LEAP_UP else 0.0)
    return out


def with_shadow(frames, lifts):
    """Each frame with a stand-in for the code's shadow under him (smaller and fainter the higher he is)."""
    out = []
    for f, L in zip(frames, lifts):
        g = dict()
        w = max(14.0, 46.0 - 0.25 * L)
        h = w * 0.3
        for y in range(round(rig.AY - h), round(rig.AY + h) + 1):
            for x in range(round(rig.AX - w), round(rig.AX + w) + 1):
                if ((x - rig.AX) / w) ** 2 + ((y - rig.AY) / h) ** 2 <= 1.0:
                    g[(x, y)] = (24, 20, 26, 255)
        g.update(f)
        out.append(g)
    return out


def sequences(ms):
    m, b = ms
    seq = []
    lifts = [s.get('lift', 0.0) for s in m.states]
    seq.append(('leap', '墜王之躍（原地看，地上的黑影是示意：遊戲由程式畫）：扛劍站著 → 劍收到背上 → 蹲下蓄力 → 起跳、騰空 0.8 秒 → '
                '落地右拳砸地（判定）→ 收招 1.0 秒（從背上拔劍、放回肩上）→ 扛劍站著',
                lambda: {d: E.carry_for(d, 30) + E.held(with_shadow(m.frames()[d], lifts), m.holds) + E.carry_for(d, 40)
                         for d in rig.DIRS}, BOX, 2))
    av = advs(m)
    seq.append(('leap_travel', '墜王之躍（照遊戲的位置：騰空的 0.8 秒往前移 %d px，實際距離看主角在哪；1 倍）' % TRAVEL,
                lambda: {d: E.carry_for(d, 30) + E.travel(d, E.held(with_shadow(m.frames()[d], lifts), m.holds), av)
                         + E.travel(d, E.carry_for(d, 40), [TRAVEL]) for d in rig.DIRS}, TRAVEL_BOX, 1))
    times, _, end = AT.LEAP_ENTRY
    eh = [y - x for x, y in zip(times, times[1:] + (end,))]
    j = m.times.index(end)
    seq.append(('leap_walk', '往前走時出招（從走路循環第 10 張直接接墜王之躍）',
                lambda: {d: E.loop_for(d, 'walk', 0, 10) + E.held(m.entries()[('walk', 10)][d], eh)
                         + E.held(with_shadow(m.frames()[d][j:], lifts[j:]), m.holds[j:]) + E.carry_for(d, 40)
                         for d in rig.DIRS}, BOX, 2))
    i = m.times.index(AT.LEAP_CONTACT)
    seq.append(('leap_bounce', '落地砸地的那一刻被完美彈返：被彈開 1.2 秒（站起來、從背上拔劍）→ 扛劍站著',
                lambda: {d: E.carry_for(d, 20) + E.held(with_shadow(m.frames()[d][:i], lifts[:i]), m.holds[:i])
                         + E.held(b.frames()[d], b.holds) + E.carry_for(d, 40) for d in rig.DIRS}, BOX, 2))
    return seq


KEY_POSES = [(8, '劍往背上收'), (AT.LEAP_BACK[0], '劍斜掛在背上'), (AT.LEAP_CROUCH[0], '蹲下'), (AT.LEAP_CROUCH[1], '蓄力到最低'), (40, '蹬地'), (AT.LEAP_UP, '離地'),
             (52, '往上、收腿'), (66, '最高點'), (AT.LEAP_LOCK, '鎖定：前傾、右手收拳'), (84, '往下掉'), (88, ''),
             (AT.LEAP_W, '落地：右拳砸地（判定）'), (114, '站起來'), (AT.LEAP_BACK[1], '握住背上的劍柄'), (130, '拔出來'),
             (139, '舉過頭'), (142, '立在右肩前')]


def key_poses(m, path, cw=400, ch=420):
    from PIL import Image, ImageDraw
    import preview
    top, left = 30, 70
    fr = m.frames()
    out = Image.new('RGB', (left + len(KEY_POSES) * cw, top + 4 * ch), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    f = preview.font(13)
    for r, dd in enumerate(rig.DIRS):
        dr.text((6, top + r * ch + 160), NAMES[dd], font=f, fill=(235, 228, 220))
    for c, (t, lab) in enumerate(KEY_POSES):
        i = max(j for j, x in enumerate(m.times) if x <= t)
        dr.text((left + c * cw + 4, 8), f'{lab}（{m.times[i]}）', font=f, fill=(235, 228, 220))
        for r, dd in enumerate(rig.DIRS):
            out.paste(preview.render(fr[dd][i], (-80, -150, -80 + cw, -150 + ch), 1, bg=(42, 40, 44)), (left + c * cw, top + r * ch))
    out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(path)


def side_closeup(m, path, picks=(AT.LEAP_BACK[0], AT.LEAP_CROUCH[0], AT.LEAP_CROUCH[1], 40, AT.LEAP_UP, 66, AT.LEAP_LOCK, 84, 88, AT.LEAP_W, AT.LEAP_BACK[1], 130, 139),
                 box=(20, -100, 290, 215), k=3, cols=7):
    from PIL import Image, ImageDraw
    import preview
    cw, ch = box[2] - box[0], box[3] - box[1]
    rows = (len(picks) + cols - 1) // cols
    out = Image.new('RGB', (cols * cw * k, rows * (ch * k + 20)), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    fr = m.frames()['right']
    for n, t in enumerate(picks):
        i = max(j for j, x in enumerate(m.times) if x <= t)
        x, y = (n % cols) * cw * k, (n // cols) * (ch * k + 20)
        out.paste(preview.render(fr[i], box, k, bg=(42, 40, 44)), (x, y + 20))
        dr.text((x + 4, y + 2), str(m.times[i]), font=preview.font(14), fill=(235, 228, 220))
    out.save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 墜王之躍</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）C7 躍起與落地：墜王之躍（二階段）</h1>
<p>還沒接進遊戲。起手：右手把劍從肩上提起來、往後放到背上斜掛（握柄在右肩後上方、劍身斜斜往下經過背後到左腰後面），放手；蹲下、停住蓄力（兩手往後擺，停著時再往下壓一點、手再往後拉），腳一蹬、兩手往前上甩，離地。騰空 0.8 秒：遊戲把他從起跳點直線移到落點，高度畫在圖裡（最高約 90px；地上的影子由程式畫，預覽裡的黑影是示意）；先往上、收腿，落點鎖定時身體往前傾、右手收拳（手肘往後上拉、拳頭留在右肩前、下巴的高度），往下掉時左腳往前伸、右膝往下。落地＝判定：右膝跪地、左腳踩在前面（和跪地的姿勢同一套腿），整個人壓低，右拳砸在身前右側的地面；衝擊波由程式畫。拳頭停在地上一會兒，再站起來，右手往右肩後面握住背上的劍柄，把劍往上拔出來、從頭上方往前繞、立在右肩前、放回肩上，右腳、左腳依序收回來。四個方向：朝下、朝右、朝上、朝左（朝左不是鏡像）。</p>
<h2>關鍵姿勢（四個方向，2 倍）</h2>
%(keys)s
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張，騰空時照離地的高度）</h2>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''

HAND_PICKS = [('劍往背上收', 8), ('劍斜掛在背上', AT.LEAP_BACK[0]), ('蹲下蓄力', AT.LEAP_CROUCH[1]), ('鎖定：右手收拳', AT.LEAP_LOCK),
              ('落地砸地', AT.LEAP_W), ('站起來', 114), ('握住背上的劍柄', AT.LEAP_BACK[1]), ('拔出來', 130), ('舉過頭', 139),
              ('立在右肩前', 142)]


class _Down:
    """A move's states put down on the ground (the legs sheet draws the legs in its own small window)."""

    def __init__(self, m):
        self.states = [AA.lowered(s) for s in m.states]


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    ms = moves()
    for m in ms:
        E.write_sheet(os.path.join(E.SHEETS, m.sheet + '.png'), [m.frames()])
        if m.has_entries:
            ents = m.entries()
            for kind in AW.KINDS:
                E.write_sheet(os.path.join(E.SHEETS, f'{m.sheet}_{EA.SHEET_OF[kind][len("boss_"):]}_entry.png'),
                              [ents[(kind, e)] for e in AT.ENTRY_FROM])
        for d in rig.DIRS:
            import preview
            labels = [f'{i}:{t}' for i, t in enumerate(m.times)]
            preview.contact(m.frames()[d], k=1, cols=12, box=BOX, labels=labels).save(os.path.join(OUT, f'{m.sheet}_{d}.png'))
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)), flush=True)
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    data.update(metadata(ms))
    with open(path, 'w') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    seq_html = ''
    for title, cap, fn, box, k in sequences(ms):
        parts = fn()
        EH.gif4(os.path.join(OUT, f'{title}_all.gif'), parts, k=k, box=box)
        seq_html += f'<h3>{cap}</h3><figure><img src="{title}_all.gif"><figcaption>四個方向（{k} 倍）</figcaption></figure><br>'
        if video_ok:
            for d in rig.DIRS:
                EH.video(os.path.join(OUT, f'{title}_{d}.mp4'), EH.timeline(parts[d]), k=3 if k == 2 else 2, box=box)
            seq_html += ''.join(f'<figure><video src="{title}_{d}.mp4" autoplay loop muted playsinline controls></video>'
                                f'<figcaption>{NAMES[d]}（60fps）</figcaption></figure>' for d in rig.DIRS)
        print('preview', title, flush=True)
    m, b = ms
    key_poses(m, os.path.join(OUT, 'key_poses.png'))
    side_closeup(m, os.path.join(OUT, 'side_closeup.png'))
    picks = [(lab, max(i for i, t in enumerate(m.times) if t <= at)) for lab, at in HAND_PICKS]
    E.hands_sheet(os.path.join(OUT, 'hands_boss_leap.png'), m, picks)
    E.legs_sheet(os.path.join(OUT, 'legs_boss_leap.png'), _Down(m))
    E.legs_sheet(os.path.join(OUT, 'legs_boss_leap_bounce.png'), _Down(b))
    keys_html = ('<figure><img src="key_poses.png"><figcaption>墜王之躍的關鍵姿勢（從精靈圖直接切出來的）</figcaption></figure><br>'
                 '<figure><img src="side_closeup.png"><figcaption>側面 3 倍：劍掛在背上、蹲下蓄力、蹬地、離地、最高點、鎖定、往下掉、'
                 '落地砸地、握劍柄、拔劍、舉過頭</figcaption></figure>')
    hands_html = ('<figure><img src="hands_boss_leap.png"><figcaption>' + '、'.join(lab for lab, _ in HAND_PICKS)
                  + '</figcaption></figure>')
    legs_html = ''.join(f'<figure><img src="legs_{mv.sheet}.png"><figcaption>{mv.caption}（每一張）</figcaption></figure>' for mv in ms)
    sheets_html = ''.join(f'<figure><img src="{mv.sheet}_{d}.png"><figcaption>{mv.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）'
                          f'</figcaption></figure>' for mv in ms for d in rig.DIRS)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html, 'keys': keys_html})
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)', flush=True)


if __name__ == '__main__':
    main()
