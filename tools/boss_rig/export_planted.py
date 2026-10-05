"""Starting an attack with the sword planted (planted.py): sprite sheets, json and previews.

    python3 tools/boss_rig/export_planted.py [--jobs 4]

Sheets -> assets/sprites/boss/boss_<x>_planted_entry.png (x: the attack sheets whose openings the game plays,
planted.JOIN): one group of four rows (down, right, up, left), its poses along; the attack container 384 x (336 + top),
the foot anchor (192, 272 + top) - taller where the sword goes up over it. boss_attacks.json: boss_<x>_planted_entry
{cell, anchor, holds, end, times, way}: the game plays it from the attack's first frame and the attack itself from
frame `end`. Previews -> docs/art-preview/boss/planted/: standing, the start, the attack on to its first hit.
"""
import json
import os
import pickle
import subprocess
import sys
import rig
import attacks as AT
import anim_attack as AA
import planted as P
import export_attack as E
import export_hit as EH
import export_interrupt as X
import boss as B

HERE = os.path.dirname(os.path.abspath(__file__))
PIECES = os.path.join(HERE, '.work', 'planted')
OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'planted')
NAMES = {'boss_c1': '王權橫掃、雙斬、三斬', 'boss_quick': '快斬連段（二連、三連）', 'boss_cleave': '墜誓下劈（含延遲版）',
         'boss_impact': '灰燼衝擊、雙重衝擊', 'boss_thrust': '裁決突刺', 'boss_spin': '灰燼迴旋', 'boss_leap': '墜王之躍'}


def source(sheet):
    return X.source(sheet)


def render_one(sheet):
    m = source(sheet)
    st = P.build(m)
    name = f'P_{sheet}'
    sts = AT.poses(st.clip, st.times)
    for i, s in enumerate(sts):
        s['name'], s['i'] = name, i
    # the first pose is the standing sprite itself (planted.py: the projected standing pose differs from it)
    idle = X.sheet_frames('boss_idle', (rig.FW, rig.FH), (rig.AX, rig.AY))
    fr = {d: [{q: tuple(c[:3]) for q, c in idle[d][0].items()}] + [AA.render_pose(d, s, sts[i - 1]) for i, s in enumerate(sts) if i]
          for d in rig.DIRS}
    sword = {k: v for k, v in AA.SWORD.items() if k[1] == name}
    joints = {k: v for k, v in AA.JOINTS.items() if k[1] == name}
    lite = [{k: v for k, v in s.items() if not callable(v)} for s in sts]
    drawn0 = {d: AA.render_pose(d, sts[0], sts[0]) for d in rig.DIRS}
    return {'frames': fr, 'holds': st.holds, 'times': st.times, 'end': st.end, 'way': st.way, 'worst': P.report(st),
            'drawn0': drawn0, 'sword': sword, 'joints': joints, 'states': lite}


def render(i, n):
    os.makedirs(PIECES, exist_ok=True)
    for j, sheet in enumerate(P.JOIN):
        if j % n != i:
            continue
        pc = render_one(sheet)
        with open(os.path.join(PIECES, sheet + '.pkl'), 'wb') as fh:
            pickle.dump(pc, fh)
        print('rendered', sheet, 'join', pc['end'], 'way', pc['way'], 'poses', len(pc['holds']), flush=True)


def piece(sheet):
    with open(os.path.join(PIECES, sheet + '.pkl'), 'rb') as fh:
        return pickle.load(fh)


def outline_diff(a, b):
    """Share of the two frames' drawn pixels that only one of them draws."""
    sa, sb = set(a), set(b)
    return len(sa ^ sb) / max(1, len(sa | sb))


def assemble():
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path))
    idle = X.sheet_frames('boss_idle', (rig.FW, rig.FH), (rig.AX, rig.AY))
    os.makedirs(OUT, exist_ok=True)
    html = []
    for sheet in P.JOIN:
        pc = piece(sheet)
        key = f'{sheet}_planted_entry'
        top = X.write(os.path.join(E.SHEETS, key + '.png'), [pc['frames']])
        data[key] = {'cell': [X.AW.BIG[0], X.AW.BIG[1] + top], 'anchor': [rig.AX + X.AW.EXT, rig.AY + X.AW.EXT + top],
                     'holds': pc['holds'], 'times': pc['times'], 'end': pc['end'], 'way': pc['way'],
                     'note': ('劍立在地上時直接出 %s：從出招的第 0 幀播這一段，第 %d 幀起接回攻擊本身（站著、腳不動；劍尖先往前'
                              '離開地面，照這一招的起手接上）' % (sheet, pc['end']))}
        diffs = {d: outline_diff(pc['drawn0'][d], idle[d][0]) for d in rig.DIRS}
        print(sheet, 'join', pc['end'], 'way', pc['way'], 'holds', pc['holds'], 'worst step body %.1f tip %.1f' % pc['worst'],
              'drawn standing pose vs the sprite', {d: round(v, 3) for d, v in diffs.items()}, flush=True)
        # preview: standing (the idle's first pose), the start, the attack on to its first hit and a little past
        js = data[sheet]
        src = X.sheet_frames(sheet, tuple(js['cell']), tuple(js['anchor']))
        m = source(sheet)
        hit = m.hits[0][0] if m.hits else pc['end'] + 30
        parts = {}
        for d in rig.DIRS:
            seq = [(idle[d][0], 30)] + list(zip(pc['frames'][d], pc['holds']))
            for i, s in enumerate(m.states):
                if s['t'] < pc['end']:
                    continue
                if s['t'] > hit + 8:
                    break
                seq.append((src[d][i], m.holds[i]))
            seq[-1] = (seq[-1][0], 40)
            parts[d] = seq
        gif = f'{sheet}_planted.gif'
        EH.gif4(os.path.join(OUT, gif), parts, k=1, box=(-90, -150, 346, 262))
        html.append(f'<h3>{NAMES[sheet]}</h3><figure><img src="{gif}"><figcaption>劍立在地上站著 → 直接出招（前 {pc["end"]} 幀是新畫的'
                    f'起手，之後是這一招本身，到砍到為止）。四個方向：朝下、朝右、朝上、朝左（1 倍）</figcaption></figure>')
    with open(path, 'w') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write('<!doctype html><meta charset="utf-8"><title>Boss 劍立在地上直接出招</title><style>body{background:#2a282c;'
                 'color:#e8e2dc;font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}img{image-rendering:pixelated;'
                 'max-width:100%}figure{margin:0 0 20px}</style><h1>劍立在地上直接出招</h1><p>以前第一張就是扛劍，劍會從地上'
                 '瞬間跳到肩上；現在劍尖先往前離開地面，直接接上這一招的起手。出招的時間和判定都沒變。</p>' + ''.join(html))
    print('wrote', E.SHEETS, OUT)


def main():
    args = sys.argv[1:]
    if args and args[0] == 'render':
        render(int(args[1]), int(args[2]))
        return
    if args and args[0] == 'assemble':
        assemble()
        return
    jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
    procs = [subprocess.Popen([sys.executable, __file__, 'render', str(i), str(jobs)]) for i in range(jobs)]
    for p in procs:
        if p.wait():
            raise SystemExit('a render job failed')
    assemble()


if __name__ == '__main__':
    main()
