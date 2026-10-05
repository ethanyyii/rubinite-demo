"""Boss quick combo, three-hit version (快斬連段三連): the two quick slashes, then the upswing (C5 上挑) -
sprite sheets and previews.

    python3 tools/boss_rig/export_upswing.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_quick3.png (the two slashes, the
upswing, the recovery), boss_quick3_bounce.png (the upswing parried). Starting from a move it uses the
quick slashes' own entry sheets (boss_quick_<move>_entry.png: the opening is the same frames). The attack
container 384x336, foot anchor (192, 272); rows down, right, up, left. Timing and the grip / tip per pose
are added to boss_attacks.json (the other attacks' entries are kept). Previews -> docs/art-preview/boss/upswing/.
"""
import json
import os
import shutil
import sys
import rig
import attacks as AT
import anim_attack as AA
import export_anim as EA
import export_hit as EH
import export_attack as E
import boss as B

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'upswing')
NAMES = EA.NAMES
BOX = (-70, -56, 330, 262)
PHASE2_RECOVERY = 41            # veltharis_data: 收招 0.9 s x 0.75


def moves():
    # veltharis_data quick_combo_3: 起手 0.4 / 判定 0.1, 0.6 later 判定 0.1, 0.8 later 判定 0.1 (heavy), 收招 0.9
    q = E.Move('boss_quick3', AT.quick3(), AT.QUICK3_END, [(AT.Q1, 6), (AT.Q2, 6), (AT.Q3, 6)],
               '快斬連段三連（兩段單手快斬 → C5 上挑，雙手）', phase2_recovery=PHASE2_RECOVERY, entry_times=True,
               entry_spec=AT.QUICK_ENTRY)
    # BOUNCED 1.2 s (the third hit is heavy): from its contact
    b = E.Move('boss_quick3_bounce', AT.quick3_bounce(), 72, [], '上挑被彈開',
               first=(q, q.times.index(AT.QUICK3_CONTACT)))
    return [q, b]


def metadata(ms):
    out = E.metadata(ms)
    q, b = ms
    out[q.sheet]['note'] = ('快斬連段三連：第 0–%d 幀和 boss_quick 是同一組圖（從移動出招用 boss_quick_<移動>_entry，第 %d 幀接回）；'
                            '第三擊上挑判定 %d–%d 幀（重擊）。被完美彈返：boss_quick3_bounce 的第一張就是第 %d 幀那一張'
                            % (AT.Q2 + 6, AT.QUICK_ENTRY[2], AT.Q3, AT.Q3 + 5, AT.QUICK3_CONTACT))
    out[b.sheet]['note'] = '上挑被完美彈返（1.2 秒）：最後一張是扛劍站著'
    return out


def sequences(ms):
    q, b = ms
    seq = []
    seq.append(('quick3', '快斬連段三連（一階段）：扛劍站著 → 第一刀 → 第二刀 → 往下沉、雙手握劍、劍壓在右後方低處 → 上挑（判定 0.1 秒）→ '
                '劍舉到左肩上方停一下 → 收招 → 扛劍站著（原地，2 倍）',
                {d: E.carry_for(d, 30) + E.held(q.frames()[d], q.holds) + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(('quick3_p2', '二階段：收招縮短成 0.675 秒（同一組圖）',
                {d: E.carry_for(d, 30) + E.held(q.frames()[d], q.holds_p2) + E.carry_for(d, 40) for d in rig.DIRS}))
    n = len(AT.QUICK_ENTRY[0])
    import export_quick as EQ
    qq = EQ.moves()[0]
    en = qq.entries()[('walk', 10)]
    seq.append(('quick3_walk', '往前走時出招（從走路循環第 10 張接快斬的開頭，一樣的圖）',
                {d: E.loop_for(d, 'walk', 0, 10) + E.held(en[d], q.holds[:n]) + E.held(q.frames()[d][n:], q.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    i = q.times.index(AT.QUICK3_CONTACT)
    seq.append(('quick3_bounce', '上挑在劍到正前方的那一刻被完美彈返：被彈開 1.2 秒 → 扛劍站著',
                {d: E.carry_for(d, 20) + E.held(q.frames()[d][:i], q.holds[:i]) + E.held(b.frames()[d], b.holds)
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    return seq


KEY_POSES = [(AT.Q2 + 3, '第二刀砍到'), (AT.QUICK3_SHARED, '第二刀揮完'), (84, '往下沉、左手握回來'),
             (AT.QUICK3_LOW[1], '劍壓在右後方低處（停住）'), (104, '開始往上撈'), (AT.Q3, '判定開始（右前方）'),
             (AT.QUICK3_CONTACT, '正前方'), (AT.Q3 + 5, '判定結束（左前方往上）'), (AT.QUICK3_TOP[1], '舉到左肩上方（停住）'),
             (134, '劍放下到身前'), (AT.QUICK3_BACK[0], '立在右肩前')]


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


def side_closeup(m, path, picks=(AT.QUICK3_SHARED, 84, AT.QUICK3_LOW[1], 104, AT.Q3, AT.QUICK3_CONTACT, AT.Q3 + 3, AT.Q3 + 5,
                                 116, AT.QUICK3_TOP[1]), box=(0, -10, 310, 215), k=3, cols=5):
    """The side view, 3x: the follow-through, the load, the scoop, up over the shoulder."""
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


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 上挑</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）C5 上挑：快斬連段的第三擊</h1>
<p>還沒接進遊戲。前兩刀和快斬連段二連是同一組圖。第二刀揮完（劍在右後方低處、右手單手）接著往下沉：上身再往右扭、彎腰蹲低，左手從左邊伸過來握回劍柄（重擊雙手），劍往右後方壓低、劍尖快碰到地面，停一下（讀得出「要往上撈」）。上挑：腳一蹬、髖往上，彎腰收回、往後挺，上身從右轉到左，雙手把劍從右後方低處往前、往上撈過去：判定一開始劍在右前方低處，到正前方時劍尖在判定的邊上、主角的高度，判定結束時在左前方往上。劍一路舉到左肩上方停一下（收招的空檔），再放下到身前、立在右肩前、放回右肩，右腳收回來。兩隻腳整招都不離開原位（左腳只用腳掌轉）。四個方向：朝下、朝右、朝上、朝左（朝左不是鏡像）。刀光由程式畫，這裡沒有。</p>
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

HAND_PICKS = [('第二刀揮完', AT.QUICK3_SHARED), ('左手握回來', 84), ('壓在右後方低處', AT.QUICK3_LOW[1]),
              ('開始往上撈', 104), ('判定開始', AT.Q3), ('正前方', AT.QUICK3_CONTACT), ('判定結束', AT.Q3 + 5),
              ('左肩上方', AT.QUICK3_TOP[1]), ('劍放下到身前', 134), ('立在右肩前', AT.QUICK3_BACK[0])]


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    ms = moves()
    for m in ms:
        E.write_sheet(os.path.join(E.SHEETS, m.sheet + '.png'), [m.frames()])
        for d in rig.DIRS:
            E.strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)), flush=True)
        if m.holds_p2:
            print('  phase 2', m.holds_p2, sum(m.holds_p2), flush=True)
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
    q, b = ms
    key_poses(q, os.path.join(OUT, 'key_poses.png'))
    side_closeup(q, os.path.join(OUT, 'side_closeup.png'))
    picks = [(lab, max(i for i, t in enumerate(q.times) if t <= at)) for lab, at in HAND_PICKS]
    E.hands_sheet(os.path.join(OUT, 'hands_boss_quick3.png'), q, picks)
    E.legs_sheet(os.path.join(OUT, 'legs_boss_quick3.png'), q)
    E.legs_sheet(os.path.join(OUT, 'legs_boss_quick3_bounce.png'), b)
    keys_html = ('<figure><img src="key_poses.png"><figcaption>上挑的關鍵姿勢（從精靈圖直接切出來的）</figcaption></figure><br>'
                 '<figure><img src="side_closeup.png"><figcaption>側面 3 倍：第二刀揮完、往下沉、停住、往上撈、判定（108–113）、舉到左肩上方</figcaption></figure>')
    hands_html = ('<figure><img src="hands_boss_quick3.png"><figcaption>' + '、'.join(lab for lab, _ in HAND_PICKS)
                  + '</figcaption></figure>')
    legs_html = ''.join(f'<figure><img src="legs_{m.sheet}.png"><figcaption>{m.caption}（每一張，左上角是第幾個戰鬥幀）</figcaption></figure>'
                        for m in ms)
    sheets_html = ''.join(f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）'
                          f'</figcaption></figure>' for m in ms for d in rig.DIRS)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html, 'keys': keys_html})
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)', flush=True)


if __name__ == '__main__':
    main()
