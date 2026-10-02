"""Boss quick combo (快斬連段): the two one-handed quick slashes - sprite sheets and previews.

    python3 tools/boss_rig/export_quick.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_quick.png (the two slashes
and the recovery), boss_quick_bounce.png (the second slash parried), boss_quick_<move>_entry.png
(starting from a move). The attack container 384x336, foot anchor (192, 272); rows down, right,
up, left. Timing and the grip / tip per pose are added to boss_attacks.json (the other attacks'
entries are kept). Previews -> docs/art-preview/boss/quick/ (its own folder: export_attack.py
clears docs/art-preview/boss/attack/).
"""
import json
import os
import shutil
import sys
import rig
import anim_walk as AW
import attacks as AT
import export_anim as EA
import export_hit as EH
import export_attack as E
import boss as B

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'quick')
NAMES = EA.NAMES
BOX = (-70, -56, 330, 262)


def moves():
    # veltharis_data quick_combo_2: 起手 0.4 / 判定 0.1, 0.6 later 判定 0.1, 收招 0.9 (二階段 0.675 -> 41)
    q = E.Move('boss_quick', AT.quick(), AT.QUICK_END, [(AT.Q1, 6), (AT.Q2, 6)],
               '快斬連段（單手：第一刀從右到左、第二刀從左到右）', phase2_recovery=41, entries=True,
               entry_spec=AT.QUICK_ENTRY)
    # BOUNCED 0.8 s (a light hit): from the second slash's contact
    b = E.Move('boss_quick_bounce', AT.quick_bounce(), 48, [], '快斬第二刀被彈開',
               first=(q, q.times.index(AT.Q2 + 3)))
    return [q, b]


def sequences(ms):
    q, b = ms
    seq = []
    seq.append(('quick', '快斬連段（二連，一階段）：扛劍站著 → 起手 0.4 秒 → 第一刀（0.1 秒）→ 0.6 秒後第二刀（0.1 秒）→ 收招 0.9 秒 → 扛劍站著',
                {d: E.carry_for(d, 30) + E.held(q.frames()[d], q.holds) + E.carry_for(d, 40) for d in rig.DIRS}))
    seq.append(('quick_p2', '快斬連段（二階段：收招縮短成 0.675 秒，同一組圖）',
                {d: E.carry_for(d, 30) + E.held(q.frames()[d], q.holds_p2) + E.carry_for(d, 40) for d in rig.DIRS}))
    n = len(AT.QUICK_ENTRY[0])
    en = q.entries()[('walk', 10)]
    seq.append(('quick_walk', '往前走時出招（從走路循環第 10 張直接接快斬）',
                {d: E.loop_for(d, 'walk', 0, 10) + E.held(en[d], q.holds[:n]) + E.held(q.frames()[d][n:], q.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    en = q.entries()[('strafe_r', 5)]
    seq.append(('quick_strafe', '側移時出招（從往右側移的循環第 5 張直接接快斬）',
                {d: E.loop_for(d, 'strafe_r', 0, 5) + E.held(en[d], q.holds[:n]) + E.held(q.frames()[d][n:], q.holds[n:])
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    i = q.times.index(AT.Q2 + 3)
    seq.append(('quick_bounce', '第二刀在砍到的那一刻被完美彈返：被彈開 0.8 秒 → 扛劍站著',
                {d: E.carry_for(d, 20) + E.held(q.frames()[d][:i], q.holds[:i]) + E.held(b.frames()[d], b.holds)
                 + E.carry_for(d, 40) for d in rig.DIRS}))
    return seq


KEY_POSES = [(0, '扛劍站著'), (14, '起手：劍拉到右後方'), (AT.Q1 + 3, '第一刀砍到'), (AT.Q1 + 7, '第一刀揮完'),
             (47, '第二刀蓄力：劍在左後方'), (AT.Q2 + 3, '第二刀砍到'), (AT.Q2 + 7, '第二刀揮完'), (79, '收招前')]


def key_poses(m, path):
    """The key poses, four directions side by side, cut from the frames (2x)."""
    from PIL import Image, ImageDraw
    import preview
    cw, top, left = 200, 30, 70
    fr = m.frames()
    out = Image.new('RGBA', (left + len(KEY_POSES) * cw, top + 4 * 200), (42, 40, 44, 255))
    d = ImageDraw.Draw(out)
    f = preview.font(13)
    for r, dd in enumerate(rig.DIRS):
        d.text((6, top + r * 200 + 90), NAMES[dd], font=f, fill=(235, 228, 220))
    for c, (t, lab) in enumerate(KEY_POSES):
        i = max(j for j, x in enumerate(m.times) if x <= t)
        d.text((left + c * cw + 4, 8), lab, font=f, fill=(235, 228, 220))
        for r, dd in enumerate(rig.DIRS):
            tile = rig.image({(x - 28, y - 26): v for (x, y), v in fr[dd][i].items()}, (cw, 200))
            out.alpha_composite(tile, (left + c * cw, top + r * 200))
    out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 快斬連段</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）快斬連段：兩段單手快斬</h1>
<p>還沒接進遊戲。右手單手握劍：第一刀從右到左橫掃、第二刀從左到右橫掃。單手揮沒有左手牽制，整個身體跟著轉（髖、腿、肩、頭），空著的左手跟著甩，重心跟著踏出去的右腳走。四個方向：朝下、朝右、朝上、朝左（朝左不是鏡像）。刀光、劍身符文由程式畫，這裡沒有。</p>
<h2>關鍵姿勢（四個方向，2 倍）</h2>
<figure><img src="key_poses.png"><figcaption>從精靈圖直接切出來的</figcaption></figure>
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張）</h2>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''


def main():
    video_ok = '--no-video' not in sys.argv and shutil.which('ffmpeg')
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)
    ms = moves()
    sheets_html = ''
    for m in ms:
        E.write_sheet(os.path.join(E.SHEETS, m.sheet + '.png'), [m.frames()])
        if m.has_entries:
            ents = m.entries()
            for kind in AW.KINDS:
                E.write_sheet(os.path.join(E.SHEETS, f'{m.sheet}_{EA.SHEET_OF[kind][len("boss_"):]}_entry.png'),
                              [ents[(kind, e)] for e in AT.ENTRY_FROM])
        for d in rig.DIRS:
            E.strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
            sheets_html += f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）</figcaption></figure>'
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)))
        if m.holds_p2:
            print('  phase 2', m.holds_p2, sum(m.holds_p2))
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path)) if os.path.exists(path) else {}
    data.update(E.metadata(ms))
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
    q = ms[0]
    key_poses(q, os.path.join(OUT, 'key_poses.png'))
    picks = [('扛劍站著', 0), ('起手（劍在右後方）', 14), ('第一刀砍到', AT.Q1 + 3), ('第一刀揮完（左邊）', AT.Q1 + 8),
             ('第二刀起手（劍在左後方）', 48), ('第二刀砍到', AT.Q2 + 3), ('第二刀揮完（右邊）', AT.Q2 + 8),
             ('收招：舉到肩上', 96)]
    picks = [(lab, max(i for i, t in enumerate(q.times) if t <= at)) for lab, at in picks]
    E.hands_sheet(os.path.join(OUT, 'hands_boss_quick.png'), q, picks)
    hands_html = '<figure><img src="hands_boss_quick.png"><figcaption>' + '、'.join(lab for lab, _ in picks) + '</figcaption></figure>'
    E.legs_sheet(os.path.join(OUT, 'legs_boss_quick.png'), q)
    legs_html = '<figure><img src="legs_boss_quick.png"><figcaption>快斬連段（每一張，左上角是第幾個戰鬥幀）</figcaption></figure>'
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html})
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)')


if __name__ == '__main__':
    main()
