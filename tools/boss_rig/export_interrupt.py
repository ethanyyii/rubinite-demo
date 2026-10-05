"""Interrupted attacks (interrupt.py): sprite sheets, json and previews.

    python3 tools/boss_rig/export_interrupt.py all [--jobs 4]     # plan, render (in parallel), assemble
    python3 tools/boss_rig/export_interrupt.py plan | render I N | assemble

plan      every attack and bounce sheet in turn (MODULES' order): each pose he can be hit in gets a start - one made
          for an earlier sheet when its pose is near enough (interrupt.cover: a sheet sharing poses with another, the
          twin slash's first cut, the triple slash, the upswing's first two, the double impact's first), otherwise
          new ones (interrupt.choose_exits) - the break's (and death's) and, in the recovery, the stagger's. Each new
          start's way (interrupt.break_bridge / _back / stagger_bridge) is laid out and kept: .work/interrupt_plan.json.
render    every N-th start from I drawn in the four directions: .work/interrupt/<start>.pkl (frames, the drawn
          swords and arms, the states - for checks_interrupt.py).
assemble  boss_<x>_break.png / boss_<x>_stagger.png (the starts made for sheet boss_<x>: one group of four rows - down,
          right, up, left - each, its poses along; 12 groups a sheet, then boss_<x>_break2 ...). Containers 384 x
          (336 + top), the foot anchor (192, 272 + top): taller where a sword held up goes over the attack container.
          boss_attacks.json: boss_<x>_break / _stagger - for every pose of sheet boss_<x> the start it uses
          ('pose_start' into 'starts'; -1: he cannot be hit there - in the air), each start's sheet, group (rows),
          cell, anchor and holds. After a break the game plays boss_kneel_down from column JUNCTION_COL + 1 (BROKEN),
          for DEAD then boss_death's last three; a stagger's last pose is the carry. Previews: docs/art-preview/boss/
          interrupt/. Not wired into the game.
"""
import json
import os
import pickle
import shutil
import subprocess
import sys
from PIL import Image, ImageDraw
import rig
import preview
import anim_walk as AW
import attacks as AT
import anim_attack as AA
import interrupt as I
import export_attack as E
import export_hit as EH
import export_quick as EQ
import export_cleave as EC
import export_thrust as ET
import export_upswing as EU
import export_spin as ES
import export_leap as EL
import boss as B

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, '.work')
PLAN = os.path.join(WORK, 'interrupt_plan.json')
PIECES = os.path.join(WORK, 'interrupt')
OUT = os.path.join(B.ROOT, 'docs', 'art-preview', 'boss', 'interrupt')
MODULES = (E, EQ, EC, ET, EU, ES, EL)
KNEEL_COLS = list(range(I.JUNCTION_COL + 1, 9))      # boss_kneel_down's poses after the junction
DEATH_COLS = [9, 10, 11]                             # boss_death's last three (from the kneel)
MAX_GROUPS = 12                                       # 48 rows of 336: under 16384 px
KINDS = ('break', 'stagger')

_sources = None


def sources():
    global _sources
    if _sources is None:
        _sources = []
        for mod in MODULES:
            _sources += mod.moves()
    return _sources


def source(sheet):
    return next(m for m in sources() if m.sheet == sheet)


# ------------------------------------------------------------------ plan
def allowed(m, kind):
    if kind == 'break':
        return [i for i, s in enumerate(m.states) if s.get('lift', 0.0) < 0.5]
    if not m.hits:
        return []
    end_hit = m.hits[-1][0] + m.hits[-1][1]
    return [i for i, s in enumerate(m.states) if s['t'] >= end_hit]


def plan():
    starts, out = [], {}
    known = {k: [] for k in KINDS}
    for m in sources():
        out[m.sheet] = {}
        for kind in KINDS:
            al = allowed(m, kind)
            if not al:
                continue
            where, exits = I.cover(m.states, al, known[kind])
            ids = {}
            for e in exits:
                s = m.states[e]
                if kind == 'stagger':
                    b = I.stagger_bridge(m.clip, s['t'])
                    sp = I.spec(b, kind, m.sheet, e, None, te=s['t'])
                else:
                    if s.get('back'):
                        b = I.break_bridge_back(m.clip, s)
                    else:
                        try:
                            b = I.break_bridge(m.clip, s)
                        except ValueError:
                            # the hand on the hilt behind his shoulder (the leap putting the sword on his back):
                            # the way from the back
                            b = I.break_bridge_back(m.clip, s)
                    sp = I.spec(b, kind, m.sheet, e, b.flags, back=b.back)
                sp['id'] = len(starts)
                sp['n'] = len(b.times)
                starts.append(sp)
                ids[e] = sp['id']
                known[kind].append((sp['id'], s))
            ps = [-1] * len(m.states)
            for i, w in where.items():
                ps[i] = ids[w[1]] if isinstance(w, tuple) else w
            out[m.sheet][kind] = ps
            print(m.sheet, kind, 'new', [(e, starts[ids[e]]['n']) for e in exits], 'reused',
                  sorted({w for w in where.values() if not isinstance(w, tuple)}), flush=True)
    os.makedirs(WORK, exist_ok=True)
    with open(PLAN, 'w') as fh:
        json.dump({'starts': starts, 'sheets': out}, fh)
    print('starts', len(starts), 'poses', sum(sp['n'] for sp in starts))


def load_plan():
    return json.load(open(PLAN))


# ------------------------------------------------------------------ render
def bridge_of(sp):
    m = source(sp['source'])
    return I.from_spec(sp, m.clip)


def render_start(sp):
    m = source(sp['source'])
    b = bridge_of(sp)
    name = f'S{sp["id"]}'
    sts = AT.poses(b.clip, b.times)
    for i, st in enumerate(sts):
        st['name'], st['i'] = name, i
    src = m.states[sp['pose']]
    fr = {}
    for d in rig.DIRS:
        out = []
        for i, st in enumerate(sts):
            if sp['kind'] == 'stagger' and i == len(sts) - 1:
                out.append(E.carry_frame(d))
            else:
                out.append(AA.render_pose(d, st, sts[i - 1] if i else src))
        fr[d] = out
    sword = {k: v for k, v in AA.SWORD.items() if k[1] == name}
    joints = {k: v for k, v in AA.JOINTS.items() if k[1] == name}
    lite = [{k: v for k, v in st.items() if not callable(v)} for st in sts]
    return {'frames': fr, 'sword': sword, 'joints': joints, 'states': lite, 'times': b.times, 'holds': b.holds}


def render(i, n, kind=None):
    os.makedirs(PIECES, exist_ok=True)
    pl = load_plan()
    todo = [sp for sp in pl['starts'] if kind is None or sp['kind'] == kind]
    for j, sp in enumerate(todo):
        if j % n != i:
            continue
        path = os.path.join(PIECES, f'{sp["id"]}.pkl')
        with open(path, 'wb') as fh:
            pickle.dump(render_start(sp), fh)
        print('rendered', sp['id'], sp['source'], sp['kind'], sp['pose'], flush=True)


def piece(sid):
    with open(os.path.join(PIECES, f'{sid}.pkl'), 'rb') as fh:
        return pickle.load(fh)


# ------------------------------------------------------------------ assemble
def top_room(frames_):
    """Rows the container needs above the attack container's (a sword held up over it)."""
    low = min(y for fr in frames_ for f in fr for (x, y) in f)
    return max(0, -(low + AW.EXT))


def write(path, groups):
    """groups: [{direction: [frames]}] (any number of poses each) -> top (rows added above)."""
    top = top_room([g[d] for g in groups for d in rig.DIRS])
    top = ((top + 7) // 8) * 8
    cw, ch = AW.BIG[0], AW.BIG[1] + top
    n = max(len(g['down']) for g in groups)
    im = Image.new('RGBA', (cw * n, ch * 4 * len(groups)), (0, 0, 0, 0))
    r = 0
    for g in groups:
        for d in rig.DIRS:
            for c, f in enumerate(g[d]):
                im.alpha_composite(rig.image({(x + AW.EXT, y + AW.EXT + top): v for (x, y), v in f.items()}, (cw, ch)),
                                   (c * cw, r * ch))
            r += 1
    im.save(path)
    return top


def contact(m, kind, ids, path, k=1):
    """Every start sheet m uses (its own and shared): per start four rows - the pose it starts from (the first
    pose of m using it), the way, then (break) boss_kneel_down's poses after the junction."""
    kd = Image.open(os.path.join(E.SHEETS, 'boss_kneel_down.png')).convert('RGBA')
    rows = {'down': 0, 'right': 1, 'up': 2, 'left': 3}
    box = (-70, -110, 330, 270)
    cw, ch = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    data = json.load(open(os.path.join(E.SHEETS, 'boss_attacks.json')))
    src = sheet_frames(m.sheet, tuple(data[m.sheet]['cell']), tuple(data[m.sheet]['anchor']))
    pieces = {sid: piece(sid) for sid in ids}
    plan_ = load_plan()
    first = {}
    for i, sid in enumerate(plan_['sheets'][m.sheet][kind]):
        if sid >= 0 and sid not in first:
            first[sid] = i
    lens = [len(pieces[sid]['frames']['down']) for sid in ids]
    ncols = 1 + max(lens) + (len(KNEEL_COLS) if kind == 'break' else 0)
    img = Image.new('RGB', (ncols * cw, len(ids) * (4 * ch + 24)), (42, 40, 44))
    dr = ImageDraw.Draw(img)
    for j, sid in enumerate(ids):
        y0 = j * (4 * ch + 24)
        p = pieces[sid]
        sp = plan_['starts'][sid]
        dr.text((4, y0 + 4), f'{m.sheet} pose {first[sid]} (t {m.states[first[sid]]["t"]}) -> start {sid} (made for {sp["source"]} '
                f'pose {sp["pose"]})  holds {p["holds"]}', font=preview.font(14), fill=(235, 228, 220))
        for r, d in enumerate(rig.DIRS):
            y = y0 + 24 + r * ch
            img.paste(preview.render(src[d][first[sid]], box, k, bg=(52, 48, 54)), (0, y))
            for c, f in enumerate(p['frames'][d]):
                img.paste(preview.render(f, box, k, bg=(42, 40, 44)), ((1 + c) * cw, y))
            if kind == 'break':
                for c, col in enumerate(KNEEL_COLS):
                    cell = kd.crop((col * 384, rows[d] * 336, (col + 1) * 384, (rows[d] + 1) * 336))
                    cell = cell.crop((box[0] + 64, box[1] + 64, box[2] + 64, box[3] + 64))
                    bg = Image.new('RGBA', cell.size, (36, 34, 40, 255))
                    bg.alpha_composite(cell)
                    img.paste(bg.convert('RGB').resize((cw, ch), Image.NEAREST), ((1 + max(lens) + c) * cw, y))
    # 256 colours (the Boss's 48, the backgrounds, the labels): a third of the size, the same picture
    img.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)


def assemble():
    pl = load_plan()
    starts = pl['starts']
    where = {}
    for m in sources():
        for kind in KINDS:
            own = [sp['id'] for sp in starts if sp['source'] == m.sheet and sp['kind'] == kind]
            for p in range(0, len(own), MAX_GROUPS):
                part = own[p:p + MAX_GROUPS]
                sheet = f'{m.sheet}_{kind}' + (str(p // MAX_GROUPS + 1) if p else '')
                top = write(os.path.join(E.SHEETS, sheet + '.png'), [piece(sid)['frames'] for sid in part])
                for g, sid in enumerate(part):
                    where[sid] = {'sheet': sheet, 'group': g, 'rows': [4 * g + r for r in range(4)],
                                  'cell': [AW.BIG[0], AW.BIG[1] + top], 'anchor': [rig.AX + AW.EXT, rig.AY + AW.EXT + top]}
            print('sheets', m.sheet, kind, len(own), flush=True)
    path = os.path.join(E.SHEETS, 'boss_attacks.json')
    data = json.load(open(path))
    for k in [k for k in data if k.endswith('_break') or k.endswith('_stagger')]:
        del data[k]
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)
    for m in sources():
        for kind in KINDS:
            ps = pl['sheets'][m.sheet].get(kind)
            if not ps:
                continue
            ids = sorted({sid for sid in ps if sid >= 0}, key=lambda sid: ps.index(sid))
            entry = {'source': m.sheet, 'starts': [], 'pose_start': [ids.index(sid) if sid >= 0 else -1 for sid in ps]}
            for sid in ids:
                pc = piece(sid)
                entry['starts'].append(dict(where[sid], start=sid, from_sheet=starts[sid]['source'],
                                            from_pose=starts[sid]['pose'], holds=pc['holds'], frames=sum(pc['holds'])))
            if kind == 'break':
                entry['then'] = {'BROKEN': [{'sheet': 'boss_kneel_down', 'columns': KNEEL_COLS}],
                                 'DEAD': [{'sheet': 'boss_kneel_down', 'columns': KNEEL_COLS},
                                          {'sheet': 'boss_death', 'columns': DEATH_COLS}]}
                entry['note'] = ('%s 出招／被彈開中失衡或死亡：Boss 正在顯示 %s 的第 i 張時被打斷，就播 starts[pose_start[i]]'
                                 '（-1：騰空中打不到）；有些 start 是別招做的（from_sheet），圖在它的 sheet。播完接 '
                                 'boss_kneel_down 第 %s 欄（BROKEN，之後跪著喘）；DEAD 再接 boss_death 第 %s 欄。第一張是被打的'
                                 '一震，遊戲的停頓、閃光、震動蓋在上面'
                                 % (m.sheet, m.sheet, '、'.join(str(c + 1) for c in KNEEL_COLS),
                                    '、'.join(str(c + 1) for c in DEATH_COLS)))
            else:
                entry['note'] = ('%s 收招中被打到短僵直（STAGGER 0.3 秒）：播 starts[pose_start[i]]，最後一張是扛劍站著'
                                 % m.sheet)
            data[f'{m.sheet}_{kind}'] = entry
            contact(m, kind, ids, os.path.join(OUT, f'{m.sheet}_{kind}.png'))
            print('preview', m.sheet, kind, flush=True)
    with open(path, 'w') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print('wrote', E.SHEETS, OUT)


# ------------------------------------------------------------------ previews in time
_sheets = {}


def sheet_frames(sheet, cell=(384, 336), anchor=(192, 272), cols=None):
    """{direction: [frames]} read back from a sprite sheet (frame coordinates: the foot anchor at rig.AX, AY)."""
    key = (sheet, cols)
    if key not in _sheets:
        im = Image.open(os.path.join(E.SHEETS, sheet + '.png')).convert('RGBA')
        cw, ch = cell
        n = im.width // cw
        ox, oy = anchor[0] - rig.AX, anchor[1] - rig.AY
        out = {}
        for r, d in enumerate(rig.DIRS):
            fr = []
            for c in (cols if cols is not None else range(n)):
                px = im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)).load()
                fr.append({(x - ox, y - oy): px[x, y] for x in range(cw) for y in range(ch) if px[x, y][3] > 0})
            out[d] = fr
        _sheets[key] = out
    return _sheets[key]


HITSTOP = {'BROKEN': 9, 'DEAD': 9, 'STAGGER': 6}      # FeedbackData: boss_break 0.15 s; a heavy hit 0.1 s
CASES = [
    ('c1_contact', 'boss_c1', 50, 'BROKEN', '王權橫掃砍到的那一刻（完美彈返把韌性削光）'),
    ('cleave_raised', 'boss_cleave', 40, 'BROKEN', '墜誓下劈舉過頭頂時被打到失衡'),
    ('impact_planted', 'boss_impact', 100, 'BROKEN', '灰燼衝擊劍插在地上時被打到失衡'),
    ('spin_turning', 'boss_spin', 62, 'BROKEN', '灰燼迴旋轉到一半被打到失衡（順著轉完再插劍）'),
    ('leap_landed', 'boss_leap', 100, 'BROKEN', '墜王之躍落地砸拳後被打到失衡（劍在背上：先拔劍）'),
    ('thrust_bounce', 'boss_thrust_bounce', 20, 'BROKEN', '裁決突刺被彈開時被追打到失衡'),
    ('quick3_death', 'boss_quick3', 100, 'DEAD', '上挑蓄力時被打死（跪下、再往前垂）'),
    ('c1_stagger', 'boss_c1', 80, 'STAGGER', '王權橫掃收招時被重擊打到短僵直（0.3 秒，回到扛劍站著）'),
    ('spin_stagger', 'boss_spin', 75, 'STAGGER', '灰燼迴旋收招時被打到短僵直'),
]


def case_parts(sheet, t, what):
    """{direction: [(frame, hold)]}: the carry, the attack up to the pose shown at frame t, the hitstop on the jolt,
    the way, and on (the kneel and its breathing / the last of the death / the carry)."""
    pl = load_plan()
    data = json.load(open(os.path.join(E.SHEETS, 'boss_attacks.json')))
    m = source(sheet)
    i = max(j for j, s in enumerate(m.states) if s['t'] <= t)
    kind = 'stagger' if what == 'STAGGER' else 'break'
    sid = pl['sheets'][sheet][kind][i]
    pc = piece(sid)
    src = sheet_frames(sheet, tuple(data[sheet]['cell']), tuple(data[sheet]['anchor']))
    kd = sheet_frames('boss_kneel_down')
    br = sheet_frames('boss_kneel_breathe')
    de = sheet_frames('boss_death')
    out = {}
    for d in rig.DIRS:
        seq = [] if m.first else [(E.carry_frame(d), 20)]
        seq += list(zip(src[d][:i], m.holds[:i]))
        seq.append((src[d][i], max(1, t - m.states[i]['t'] + 1)))
        holds = list(pc['holds'])
        holds[0] += HITSTOP[what]
        seq += list(zip(pc['frames'][d], holds))
        if what == 'STAGGER':
            seq.append((E.carry_frame(d), 30))
        else:
            seq += [(kd[d][c], h) for c, h in zip(KNEEL_COLS, (4, 4, 4, 2, 2))]
            if what == 'BROKEN':
                seq += [(f, 6) for f in br[d]] * 2
            else:
                seq += [(de[d][c], h) for c, h in zip(DEATH_COLS, (6, 4, 40))]
        out[d] = seq
    return out


def gifs():
    os.makedirs(OUT, exist_ok=True)
    box = (-90, -150, 346, 262)
    html = []
    for name, sheet, t, what, cap in CASES:
        parts = case_parts(sheet, t, what)
        EH.gif4(os.path.join(OUT, f'{name}.gif'), parts, k=1, box=box)
        html.append(f'<h3>{cap}</h3><figure><img src="{name}.gif"><figcaption>四個方向：朝下、朝右、朝上、朝左（1 倍；被打那一張多停'
                    f'遊戲的停頓 {HITSTOP[what]} 幀）</figcaption></figure>')
        print('gif', name, flush=True)
    sheets = sorted(f for f in os.listdir(OUT) if f.endswith('.png'))
    body = ''.join(html) + '<h2>每一招的每個起點（灰底＝被打斷時的那一張；接著銜接；跪下的話最後是 boss_kneel_down 的接下來幾張）</h2>' + ''.join(
        f'<h3>{f[:-4]}</h3><figure><img src="{f}"></figure>' for f in sheets)
    with open(os.path.join(OUT, 'index.html'), 'w') as fh:
        fh.write('<!doctype html><meta charset="utf-8"><title>Boss 被打斷</title><style>body{background:#2a282c;color:#e8e2dc;'
                 'font-family:-apple-system,"PingFang TC",sans-serif;margin:24px}img{image-rendering:pixelated;max-width:100%}'
                 'figure{margin:0 0 20px}</style><h1>Boss 出招中失衡、死亡，收招中短僵直</h1>' + body)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == 'plan':
        plan()
    elif args[0] == 'render':
        render(int(args[1]), int(args[2]), args[3] if len(args) > 3 else None)
    elif args[0] == 'assemble':
        assemble()
        gifs()
    elif args[0] == 'gifs':
        gifs()
    elif args[0] == 'all':
        jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
        plan()
        procs = [subprocess.Popen([sys.executable, __file__, 'render', str(i), str(jobs)]) for i in range(jobs)]
        for p in procs:
            if p.wait():
                raise SystemExit('a render job failed')
        assemble()


if __name__ == '__main__':
    main()
