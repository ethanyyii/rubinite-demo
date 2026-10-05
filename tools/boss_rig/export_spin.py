"""Boss ash spin (灰燼迴旋, C6 迴旋, phase 2): sprite sheets and previews.

    python3 tools/boss_rig/export_spin.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_spin.png, boss_spin_bounce.png (parried),
boss_spin_<move>_entry.png (starting from a move). The attack container 384x336, foot anchor (192, 272); rows down,
right, up, left - each row the sheet's facing: through the turn the body is drawn with the facing it is nearest to
(anim_attack.render_spun), so every row shows all four drawings in turn. Timing and the grip / tip per pose are added
to boss_attacks.json (the other attacks' entries are kept). Previews -> docs/art-preview/boss/spin/.
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

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'spin')
NAMES = EA.NAMES
BOX = (-90, -56, 346, 262)


def moves():
    # veltharis_data ash_spin (2026-10-04: one turn, one hit): 起手 0.9 / 判定 0.25 / 收招 1.2 (phase 2's own)
    s = E.Move('boss_spin', AT.spin(), AT.SPIN_END, [(AT.SPIN_W, AT.SPIN_N)], '灰燼迴旋（C6 迴旋，右手單手，二階段）',
               entries=True)
    # BOUNCED 1.2 s, from the frame the blade passes straight ahead
    b = E.Move('boss_spin_bounce', AT.spin_bounce(), 72, [], '灰燼迴旋被彈開', first=(s, s.times.index(AT.SPIN_CONTACT)))
    return [s, b]


def metadata(ms):
    out = E.metadata(ms)
    s, b = ms
    out[s.sheet]['note'] = ('灰燼迴旋（二階段，2026-10-04 起只轉一圈、只打一下）：判定 %d–%d 幀，Boss 往他的左邊轉一整圈（遊戲不移動他）；'
                            '每一列是那一列的面向，轉身時身體用最接近的面向畫，所以每一列都會輪流出現四個面向。從移動出招用 '
                            'boss_spin_<移動>_entry（第 %d 幀接回）。被完美彈返：boss_spin_bounce 的第一張就是第 %d 幀那一張（劍掃過正前方）'
                            % (AT.SPIN_W, AT.SPIN_W + AT.SPIN_N - 1, AT.ENTRY_END, AT.SPIN_CONTACT))
    out[b.sheet]['note'] = '灰燼迴旋被完美彈返（1.2 秒）：轉身被打回來、站起來、劍回到肩上；最後一張是扛劍站著'
    return out


def sequences(ms):
    s, b = ms
    seq = []
    seq.append(('spin', '灰燼迴旋（二階段）：扛劍站著 → 起手 0.9 秒（劍從肩上放到右後方拖地、上身和髖往右扭）→ 往左轉一圈（判定 0.25 秒，邊轉邊蹲下）→ '
                '蹲著停住 → 收招 1.2 秒 → 扛劍站著（2 倍）',
                {d: E.carry_for(d, 30) + E.held(s.frames()[d], s.holds) + E.carry_for(d, 40) for d in rig.DIRS}))
    n = len(AT.ENTRY_TIMES)
    en = s.entries()[('walk', 10)]
    seq.append(('spin_walk', '往前走時出招（從走路循環第 10 張直接接迴旋）',
                {d: E.loop_for(d, 'walk', 0, 10) + E.held(en[d], s.holds[:n]) + E.held(s.frames()[d][n:], s.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    en = s.entries()[('strafe_l', 5)]
    seq.append(('spin_strafe', '側移時出招（從往左側移的循環第 5 張直接接迴旋）',
                {d: E.loop_for(d, 'strafe_l', 0, 5) + E.held(en[d], s.holds[:n]) + E.held(s.frames()[d][n:], s.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    i = s.times.index(AT.SPIN_CONTACT)
    seq.append(('spin_bounce', '劍掃過正前方的那一刻被完美彈返：被彈開 1.2 秒 → 扛劍站著',
                {d: E.carry_for(d, 20) + E.held(s.frames()[d][:i], s.holds[:i]) + E.held(b.frames()[d], b.holds)
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    return seq


KEY_POSES = [(11, '劍從肩上放下'), (30, '劍拖在右後方'), (50, '往右扭（蓄力）'), (AT.SPIN_W, '開始轉（判定）'),
             (AT.SPIN_W + 2, ''), (AT.SPIN_CONTACT, '劍掃過正前方'), (AT.SPIN_W + 8, '轉到背對'), (AT.SPIN_W + 11, ''),
             (AT.SPIN_W + 14, '判定最後一幀'), (AT.SPIN_RLAND + 2, '轉完：劍甩到左前方'), (AT.SPIN_HOLD[1], '蹲著停住'),
             (102, '站起來、劍舉起'), (AT.SPIN_RBACK[1], '立在右肩前')]


def key_poses(m, path, cw=380, ch=330):
    from PIL import Image, ImageDraw
    import preview
    top, left = 30, 70
    fr = m.frames()
    out = Image.new('RGB', (left + len(KEY_POSES) * cw, top + 4 * ch), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    f = preview.font(13)
    for r, dd in enumerate(rig.DIRS):
        dr.text((6, top + r * ch + 130), NAMES[dd], font=f, fill=(235, 228, 220))
    for c, (t, lab) in enumerate(KEY_POSES):
        i = max(j for j, x in enumerate(m.times) if x <= t)
        dr.text((left + c * cw + 4, 8), f'{lab}（{m.times[i]}）', font=f, fill=(235, 228, 220))
        for r, dd in enumerate(rig.DIRS):
            out.paste(preview.render(fr[dd][i], (-80, -60, -80 + cw, -60 + ch), 1, bg=(42, 40, 44)), (left + c * cw, top + r * ch))
    out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(path)


def turn_closeup(m, d, path, box=(-60, 0, 320, 222), k=2, cols=6):
    """Every pose of the turn (the hit box and the run-on), one row of the sheet, 2x."""
    from PIL import Image, ImageDraw
    import preview
    idx = [i for i, t in enumerate(m.times) if AT.SPIN_RUP <= t <= AT.SPIN_RLAND + 3]
    cw, ch = box[2] - box[0], box[3] - box[1]
    rows = (len(idx) + cols - 1) // cols
    out = Image.new('RGB', (cols * cw * k, rows * (ch * k + 20)), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    fr = m.frames()[d]
    for n, i in enumerate(idx):
        x, y = (n % cols) * cw * k, (n // cols) * (ch * k + 20)
        out.paste(preview.render(fr[i], box, k, bg=(42, 40, 44)), (x, y + 20))
        dr.text((x + 4, y + 2), str(m.times[i]), font=preview.font(14), fill=(235, 228, 220))
    out.save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 灰燼迴旋</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）C6 迴旋：灰燼迴旋（二階段）</h1>
<p>還沒接進遊戲。遊戲已改成只轉一圈、只打一下（判定 0.25 秒）。起手：右手把劍從肩上拿下來，放到右邊、劍尖往後拖在地上，左腳踩到身體下面（等一下當軸），上身和髖往右扭、蹲低（蓄力）。判定：右手臂伸直、劍平伸，往他的左邊轉一整圈，劍掃過他四周，邊轉邊蹲下、彎腰；左腳用腳掌當軸原地轉，右腳離地跟著繞，轉完落在後面變成寬的蹲姿；左手往外甩保持平衡，披風往外甩。轉完劍甩到左前方低處停住，蹲著停一下（收招的空檔），再站起來，右腳收上來，劍舉到身前、立在右肩前、放回肩上，左腳退回原位。每一列是那一列的面向：轉身的時候身體用最接近的面向畫，所以每一列都會輪流出現正面、側面、背面。刀光由程式畫，這裡沒有。</p>
<h2>關鍵姿勢（四個方向，2 倍）</h2>
%(keys)s
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>轉身那段逐張（2 倍）</h2>
%(turn)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張）</h2>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''

HAND_PICKS = [('劍從肩上放下', 11), ('劍拖在右後方', 30), ('往右扭', 50), ('開始轉', AT.SPIN_W), ('劍掃過正前方', AT.SPIN_CONTACT),
              ('轉到背對', AT.SPIN_W + 8), ('判定最後一幀', AT.SPIN_W + 14), ('蹲著停住', AT.SPIN_HOLD[1]), ('劍舉起', 102),
              ('立在右肩前', AT.SPIN_RBACK[1])]


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
            E.strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)), flush=True)
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    data.update(metadata(ms))
    with open(path, 'w') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    seq_html = ''
    for title, cap, parts in sequences(ms):
        EH.gif4(os.path.join(OUT, f'{title}_all.gif'), parts, box=BOX)
        seq_html += f'<h3>{cap}</h3><figure><img src="{title}_all.gif"><figcaption>四個方向（2 倍）</figcaption></figure><br>'
        if video_ok:
            for d in rig.DIRS:
                EH.video(os.path.join(OUT, f'{title}_{d}.mp4'), EH.timeline(parts[d]), box=BOX)
            seq_html += ''.join(f'<figure><video src="{title}_{d}.mp4" autoplay loop muted playsinline controls></video>'
                                f'<figcaption>{NAMES[d]}（60fps，3 倍）</figcaption></figure>' for d in rig.DIRS)
        print('preview', title, flush=True)
    s, b = ms
    key_poses(s, os.path.join(OUT, 'key_poses.png'))
    for d in rig.DIRS:
        turn_closeup(s, d, os.path.join(OUT, f'turn_{d}.png'))
    picks = [(lab, max(i for i, t in enumerate(s.times) if t <= at)) for lab, at in HAND_PICKS]
    E.hands_sheet(os.path.join(OUT, 'hands_boss_spin.png'), s, picks)
    E.legs_sheet(os.path.join(OUT, 'legs_boss_spin.png'), _Faced(s))
    E.legs_sheet(os.path.join(OUT, 'legs_boss_spin_bounce.png'), _Faced(b))
    keys_html = '<figure><img src="key_poses.png"><figcaption>灰燼迴旋的關鍵姿勢（從精靈圖直接切出來的）</figcaption></figure>'
    turn_html = ''.join(f'<figure><img src="turn_{d}.png"><figcaption>{NAMES[d]}：轉身那段（第 {AT.SPIN_RUP}–{AT.SPIN_RLAND + 3} 幀）'
                        f'每一張</figcaption></figure>' for d in rig.DIRS)
    hands_html = ('<figure><img src="hands_boss_spin.png"><figcaption>' + '、'.join(lab for lab, _ in HAND_PICKS)
                  + '</figcaption></figure>')
    legs_html = ''.join(f'<figure><img src="legs_{m.sheet}.png"><figcaption>{m.caption}（每一張，照身體轉過去的面向看）</figcaption></figure>'
                        for m in ms)
    sheets_html = ''.join(f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）'
                          f'</figcaption></figure>' for m in ms for d in rig.DIRS)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html, 'keys': keys_html,
                         'turn': turn_html})
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)', flush=True)


class _Faced:
    """A move's states seen in the frame the body is turned to (the legs sheet solves the legs in the side
    plane of the facing drawn)."""

    def __init__(self, m):
        out = []
        for s in m.states:
            k = AA.spin_quarters(s) if s.get('spin') else 0
            out.append(AA.spun(s, k, strict=False) if k % 4 else dict(s, tw=s['tw'] - 90 * k, ht=s['ht'] - 90 * k))
        self.states = out


if __name__ == '__main__':
    main()
