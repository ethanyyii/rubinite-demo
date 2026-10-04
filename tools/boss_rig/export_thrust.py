"""Boss judgment thrust (裁決突刺, C4 突刺): sprite sheets and previews.

    python3 tools/boss_rig/export_thrust.py [--no-video]

Sprite sheets -> assets/sprites/boss/ (NOT wired into the game): boss_thrust.png, boss_thrust_bounce.png
(parried), boss_thrust_<move>_entry.png (starting from a move). The attack container 384x336, foot
anchor (192, 272); rows down, right, up, left. Every pose is drawn about where the game has him: the
game moves him 160 px forward through the hit box (frames 36 .. 47), each pose's 'advance' in
boss_attacks.json is how far. Timing and the grip / tip per pose are added to boss_attacks.json (the
other attacks' entries are kept). Previews -> docs/art-preview/boss/thrust/.
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

OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'thrust')
NAMES = EA.NAMES
BOX = (-90, -56, 346, 262)                 # in place (the attack container's window)
TRAVEL_BOX = (-250, -150, 506, 430)        # moving with the game (160 px forward in every direction)
PHASE2_RECOVERY = 36                       # veltharis_data: 收招 0.8 s x 0.75


def moves():
    # veltharis_data judgment_thrust: 起手 0.6 / 判定 0.2 (the lunge) / 收招 0.8 (二階段 0.6 -> 36)
    t = E.Move('boss_thrust', AT.thrust(), AT.THRUST_END, [(AT.THRUST_W, AT.LUNGE_FRAMES)], '裁決突刺（C4 突刺，雙手）',
               phase2_recovery=PHASE2_RECOVERY, entries=True, entry_spec=AT.THRUST_ENTRY)
    # BOUNCED 1.2 s, from the lunge's last frame (landed, the sword out)
    b = E.Move('boss_thrust_bounce', AT.thrust_bounce(), 72, [], '裁決突刺被彈開',
               first=(t, t.times.index(AT.THRUST_CONTACT)))
    return [t, b]


def metadata(ms):
    out = E.metadata(ms)
    t = ms[0]
    out[t.sheet]['game_step'] = {'distance': AT.LUNGE, 'frames': [AT.THRUST_W, AT.THRUST_W + AT.LUNGE_FRAMES - 1]}
    out[t.sheet]['note'] = ('裁決突刺：判定 %d–%d 幀（突進），遊戲同時把 Boss 往前移 %d px（每幀一樣多）；每一張照遊戲那一幀的位置畫，'
                            '每張的 advance 是那一張開始時已經移了多少。從移動出招用 boss_thrust_<移動>_entry（第 %d 幀接回）。'
                            '被完美彈返：boss_thrust_bounce 的第一張就是第 %d 幀那一張（突進結束、落地）'
                            % (AT.THRUST_W, AT.THRUST_W + AT.LUNGE_FRAMES - 1, AT.LUNGE, AT.ENTRY_END, AT.THRUST_CONTACT))
    out[ms[1].sheet]['note'] = '裁決突刺被完美彈返（1.2 秒）：遊戲不移動；最後一張是扛劍站著'
    return out


def sequences(ms):
    t, b = ms
    advs = [s['adv'] for s in t.states]
    L = AT.LUNGE
    seq = []
    seq.append(('thrust', '裁決突刺（原地看：遊戲把 Boss 往前移的部分沒有畫）：扛劍站著 → 起手 0.6 秒（劍收到右腰、右腳往後退開、蹲低前傾）→ '
                '突進 0.2 秒（判定）→ 收招 0.8 秒 → 扛劍站著',
                lambda: {d: E.carry_for(d, 30) + E.held(t.frames()[d], t.holds) + E.carry_for(d, 40) for d in rig.DIRS}, BOX, 2))
    seq.append(('thrust_travel', '裁決突刺（照遊戲的位置：突進的 0.2 秒往前移 %d px；1 倍）' % L,
                lambda: {d: E.carry_for(d, 30) + E.travel(d, E.held(t.frames()[d], t.holds), advs)
                         + E.travel(d, E.carry_for(d, 40), [L]) for d in rig.DIRS}, TRAVEL_BOX, 1))
    seq.append(('thrust_p2', '二階段：收招縮短成 0.6 秒（同一組圖；照遊戲的位置，1 倍）',
                lambda: {d: E.carry_for(d, 30) + E.travel(d, E.held(t.frames()[d], t.holds_p2), advs)
                         + E.travel(d, E.carry_for(d, 40), [L]) for d in rig.DIRS}, TRAVEL_BOX, 1))
    eh = [y - x for x, y in zip(AT.ENTRY_TIMES, AT.ENTRY_TIMES[1:] + (AT.ENTRY_END,))]
    n = t.times.index(AT.ENTRY_END)
    for kind, pose, cap in (('walk', 10, '往前走時出招（從走路循環第 10 張直接接突刺）'),
                            ('strafe_l', 5, '側移時出招（從往左側移的循環第 5 張直接接突刺）')):
        seq.append((f'thrust_{kind}', cap + '（原地看）',
                    (lambda kind=kind, pose=pose: {d: E.loop_for(d, kind, 0, pose) + E.held(t.entries()[(kind, pose)][d], eh)
                                                   + E.held(t.frames()[d][n:], t.holds[n:]) + E.carry_for(d, 40)
                                                   for d in rig.DIRS}), BOX, 2))
    i = t.times.index(AT.THRUST_CONTACT)
    seq.append(('thrust_bounce', '突進的最後一刻被完美彈返：被彈開 1.2 秒 → 扛劍站著（原地看）',
                lambda: {d: E.carry_for(d, 20) + E.held(t.frames()[d][:i], t.holds[:i]) + E.held(b.frames()[d], b.holds)
                         + E.carry_for(d, 40) for d in rig.DIRS}, BOX, 2))
    return seq


def strips(m, d, path):
    import preview
    labels = [f'{i}:{t}' for i, t in enumerate(m.times)]
    preview.contact(m.frames()[d], k=1, cols=12, box=BOX, labels=labels).save(path)


KEY_POSES = [(0, '扛劍站著'), (12, '劍立在右肩前'), (18, '劍尖放下、右腳往後'), (32, '起手：劍收在右腰（停住）'),
             (AT.THRUST_W - 1, '刺出'), (AT.THRUST_W, '突進開始（判定）'), (AT.THRUST_W + 5, '突進中'),
             (AT.THRUST_LLAND, '左腳落地'), (AT.THRUST_CONTACT, '突進結束'), (66, '收回'), (76, '劍立在右肩前')]


def key_poses(m, path, cw=380, ch=320):
    from PIL import Image, ImageDraw
    import preview
    top, left = 30, 70
    out = Image.new('RGB', (left + len(KEY_POSES) * cw, top + 4 * ch), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    f = preview.font(13)
    for r, dd in enumerate(rig.DIRS):
        dr.text((6, top + r * ch + 130), NAMES[dd], font=f, fill=(235, 228, 220))
    for c, (t, lab) in enumerate(KEY_POSES):
        sts = AT.poses(m.clip, [max(0, t - 1), t])
        dr.text((left + c * cw + 4, 8), f'{lab}（{t}）', font=f, fill=(235, 228, 220))
        for r, dd in enumerate(rig.DIRS):
            fr = AA.render_pose(dd, sts[1], sts[0])
            out.paste(preview.render(fr, (-60, -50, -60 + cw, -50 + ch), 1, bg=(42, 40, 44)), (left + c * cw, top + r * ch))
    out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(path)


def side_closeup(m, path, picks=(32, 35, 38, 41, 44, 47), box=(30, 80, 310, 215), k=3, cols=3):
    """The side view, 3x: cocked, the push, in the air, landed."""
    from PIL import Image, ImageDraw
    import preview
    cw, ch = box[2] - box[0], box[3] - box[1]
    rows = (len(picks) + cols - 1) // cols
    out = Image.new('RGB', (cols * cw * k, rows * (ch * k + 20)), (42, 40, 44))
    dr = ImageDraw.Draw(out)
    for i, t in enumerate(picks):
        sts = AT.poses(m.clip, [max(0, t - 1), t])
        x, y = (i % cols) * cw * k, (i // cols) * (ch * k + 20)
        out.paste(preview.render(AA.render_pose('right', sts[1], sts[0]), box, k, bg=(42, 40, 44)), (x, y + 20))
        dr.text((x + 4, y + 2), str(t), font=preview.font(14), fill=(235, 228, 220))
    out.save(path)


HTML = '''<!doctype html><meta charset="utf-8"><title>Boss 突刺</title>
<style>body{background:#2a282c;color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}
h2{margin-top:36px}figure{display:inline-block;margin:0 16px 20px 0;vertical-align:top}
figcaption{font-size:14px;color:#b8b0aa;margin-top:4px;max-width:900px}img,video{image-rendering:pixelated;display:block;max-width:100%%}
p{max-width:900px;line-height:1.6}</style>
<h1>Boss（Veltharis）C4 突刺：裁決突刺</h1>
<p>還沒接進遊戲。起手：劍從肩上拿下來、立在右肩前、劍尖往前放下，雙手把劍收到右腰（劍尖朝前），右腳往後退開（左腳在前、右腳在後，兩腳距離比肩寬），蹲低、上身前傾、往右扭。突進：右腳一蹬，雙手把劍直直刺出去，上身壓低，左腳在空中往前跨、落地，右腳在後面拖著；遊戲在這 0.2 秒把 Boss 往前移 160px，每一張照遊戲的位置畫，劍尖一直在他前方約 150px、主角的高度。收招：壓在前腳上停一下，把劍收回來，左腳先退回身體下面，劍立在右肩前、放回肩上，右腳再收上來。四個方向：朝下、朝右、朝上、朝左（朝左不是鏡像）。刀光、殘影、塵土由程式畫，這裡沒有。</p>
<h2>關鍵姿勢（四個方向，2 倍）</h2>
%(keys)s
<h2>遊戲裡會看到的順序</h2>
%(seq)s
<h2>握劍的手（放大 4 倍）</h2>
%(hands)s
<h2>側面的腿（只畫腿，綠線＝靠鏡頭的右腿，藍線＝左腿；每一張，照地面上的位置）</h2>
%(legs)s
<h2>逐張</h2>
%(sheets)s
'''

HAND_PICKS = [('扛劍站著', 0), ('劍立在右肩前', 12), ('劍尖放下', 18), ('收在右腰', 32), ('刺出', AT.THRUST_W - 1),
              ('突進', AT.THRUST_W + 4), ('突進結束', AT.THRUST_CONTACT), ('收回', 66), ('立在右肩前', 76)]


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
            strips(m, d, os.path.join(OUT, f'{m.sheet}_{d}.png'))
        print(m.sheet, len(m.times), list(zip(m.times, m.holds)), flush=True)
        if m.holds_p2:
            print('  phase 2', m.holds_p2, sum(m.holds_p2), flush=True)
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
    tail(ms, seq_html)
    print('wrote', E.SHEETS, 'and', OUT, '(video)' if video_ok else '(no video)', flush=True)


class _Here:
    """A move's states about where the game has him (the legs sheet draws them on the ground otherwise:
    160 px on, off its canvas)."""

    def __init__(self, m):
        self.states = [dict(s, adv=0.0) for s in m.states]


def tail(ms, seq_html):
    t, b = ms
    key_poses(t, os.path.join(OUT, 'key_poses.png'))
    side_closeup(t, os.path.join(OUT, 'side_closeup.png'))
    picks = [(lab, max(i for i, tt in enumerate(t.times) if tt <= at)) for lab, at in HAND_PICKS]
    E.hands_sheet(os.path.join(OUT, 'hands_boss_thrust.png'), t, picks)
    E.legs_sheet(os.path.join(OUT, 'legs_boss_thrust.png'), _Here(t))
    E.legs_sheet(os.path.join(OUT, 'legs_boss_thrust_bounce.png'), _Here(b))
    write_index(ms, seq_html)


def write_index(ms, seq_html):
    keys_html = ('<figure><img src="key_poses.png"><figcaption>裁決突刺的關鍵姿勢</figcaption></figure><br>'
                 '<figure><img src="side_closeup.png"><figcaption>側面 3 倍：起手停住（32）、蹬地（35）、飛出去（38、41、44）、落地（47）</figcaption></figure>')
    hands_html = ('<figure><img src="hands_boss_thrust.png"><figcaption>' + '、'.join(lab for lab, _ in HAND_PICKS)
                  + '</figcaption></figure>')
    legs_html = ''.join(f'<figure><img src="legs_{m.sheet}.png"><figcaption>{m.caption}（每一張，左上角是第幾個戰鬥幀）</figcaption></figure>'
                        for m in ms)
    sheets_html = ''.join(f'<figure><img src="{m.sheet}_{d}.png"><figcaption>{m.caption} {NAMES[d]}（第幾張：從出招開始的第幾個戰鬥幀）'
                          f'</figcaption></figure>' for m in ms for d in rig.DIRS)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write(HTML % {'seq': seq_html, 'sheets': sheets_html, 'hands': hands_html, 'legs': legs_html, 'keys': keys_html})


if __name__ == '__main__':
    main()
