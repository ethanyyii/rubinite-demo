class_name BossAnim
extends RefCounted
## Boss 的選格（2026-10-05 接進遊戲）：每個戰鬥幀依 BossSim 決定畫哪一段（clip，BossSprites 的幀表）、哪一列
## （方向）、哪一張，精靈圖相對 Boss 位置的偏移，以及離地多高（墜王之躍）。CombatArena 每次 sim.step() 之後
## 呼叫 update()；頓幀時戰鬥幀不動、不呼叫，畫面停在那一格。只讀取 BossSim，不改動它。
##
## 站著有兩種：劍立在地上（planted：待機、停步之後、起身之後）和扛劍（carry：出招、被彈開、收招中短僵直之後）。
## - 走路：從劍立在地上起步播 <移動>_start、從扛劍播 <移動>_cstart，播完照走的距離前進循環（每 4px 一張）。
##   往前走、後退、往他的右手邊／左手邊側移各一組；換組時欄不變。
## - 走路 → 待機：遊戲常常從走路直接出招（WALK → IDLE → ATTACK 隔一幀），所以待機的前 STOP_PENDING 幀
##   循環照舊；之後才播停步（從最近的一組），停完是劍立在地上的待機。
## - 出招：從走路（含停步前那兩幀）出招播「從移動出招」的開頭（循環最近的一欄那組），之後接攻擊本身；
##   第二階段有自己的收招（holds_phase2）；延遲版在最高點那張多停。精靈圖畫在遊戲移動前的位置的（雙斬的踏步、
##   突刺），偏移＝−面向 ×（遊戲現在的前進量 − 這一張的 advance）。
## - 被彈開：這一招的被彈開（第一張就是砍到的那一張）；被打斷（失衡、死亡、收招中短僵直）：
##   被打斷時正在顯示的那一張的起點（interrupt 表），失衡接 boss_kneel_down 交接之後的幾張、跪著喘；
##   死亡再接 boss_death 最後三張。從走路中：<移動>_stagger／_kneel（循環最近的一欄那組）。
## - 方向：面向換算成四方向，在斜角附近要超過 ROW_HYSTERESIS_DEG 才換；延遲版停住期間不換（★8）。

const BS := BossSim.State
const S := preload("res://scripts/view/boss_sprites.gd")
const ROW_HYSTERESIS_DEG := 6.0
const STOP_PENDING := 2
const LOOP_POSES := 20
const STOP_FROM := [0, 5, 10, 15]
const KNEEL_TAIL := [4, 5, 6, 7, 8]
const KNEEL_TAIL_HOLDS := [4, 4, 4, 2, 2]
const DEATH_TAIL := [9, 10, 11]
const DEATH_TAIL_HOLDS := [6, 4, 4]
const RISE_SPEED := 2.0          # 失衡自己站起來時（遊戲已經開始走）起身播兩倍速
const ROW_ANGLE := {"right": 0.0, "down": 90.0, "left": 180.0, "up": -90.0}

var clip := "idle"
var col := 0
var row := "down"
var offset := Vector2.ZERO
var lift := 0.0
var frame_id := -1
var done_at := -1                # 這個狀態播的那一串播完的那一幀（狀態經過的幀數；死亡：從這裡開始化為灰燼）
var visual := "planted"          # 現在是什麼樣子：planted / carry / loop / attack / bounce / kneel / other

var _state := -1
var _start := -1
var _seq: Array = []             # [[clip, cols 或 null, holds 或 null], ...]
var _seq_loop := false
var _seq_t0 := 0
var _seq_end := "planted"
var _kind := "walk"
var _loop_pos := 0.0
var _last_pos := Vector2.ZERO
var _pending := 0
var _intro_done := true
var _rise_pending := false
var _move_id := StringName()
var _sheet := ""
var _pose := -1
var _holds: Array = []
var _entry := ""
var _entry_end := 0


func update(b: BossSim) -> void:
	if b.state != _state or b.state_start != _start:
		var prev := _state
		_state = b.state
		_start = b.state_start
		_enter(b, prev)
	_update_row(b)
	_tick(b)
	_last_pos = b.pos
	frame_id = S.frame_at(S.clip(clip), row, col)


# --- 進入狀態 ------------------------------------------------------------------------

func _enter(b: BossSim, prev: int) -> void:
	offset = Vector2.ZERO
	lift = 0.0
	done_at = -1
	match b.state:
		BS.IDLE:
			_enter_idle(prev)
		BS.WALK:
			_enter_walk(b)
		BS.ATTACK:
			_enter_attack(b)
		BS.BOUNCED:
			var mv := S.move(_move_id)
			var name: String = mv.get("bounce") if mv.get("bounce") != null else "bounce"
			_sheet = name
			visual = "bounce"
		BS.STAGGER:
			_enter_stagger(prev)
		BS.BROKEN:
			_play(_down_to_kneel(prev) + [["kneel_breathe", null, null]], true, "kneel")
		BS.EXECUTED:
			_play([["executed", null, null]], false, "kneel")
		BS.RISING:
			_play([["rise", null, null]], false, "planted")
		BS.TRANSITION:
			_enter_transition(prev)
		BS.DEAD:
			_enter_dead(prev)


func _enter_idle(prev: int) -> void:
	_pending = 0
	match prev:
		BS.WALK:
			_pending = STOP_PENDING                 # 循環照舊；可能下一幀就出招
			_seq = []
		BS.ATTACK, BS.BOUNCED:
			_show_carry()
		BS.STAGGER:
			match _seq_end:
				"loop":
					_pending = STOP_PENDING
					_seq = []
					visual = "loop"
				"carry":
					_show_carry()
				_:
					_play([["idle", null, null]], true, "planted")
		BS.BROKEN:
			# 失衡 3 秒自己站起來（遊戲接著就走）：起身加快
			_rise_pending = true
			_play([["rise", null, _scaled(S.clip("rise")["holds"], 1.0 / RISE_SPEED)]], false, "planted")
		_:
			_play([["idle", null, null]], true, "planted")


func _show_carry() -> void:
	_play([["carry", null, null]], true, "carry")
	visual = "carry"


func _enter_walk(b: BossSim) -> void:
	_kind = _walk_kind(b, Vector2.ZERO)
	var hold := maxi(1, roundi(4.0 * VeltharisData.WALK_SPEED / maxf(b.walk_speed, 1.0)))
	_intro_done = false
	if _rise_pending:
		_rise_pending = false
		var rise := _scaled(S.clip("rise")["holds"], 1.0 / RISE_SPEED)
		_play([["rise", null, rise], [_kind + "_start", null, _filled(S.clip(_kind + "_start")["holds"].size(), hold)]],
			false, "loop")
	elif visual == "loop":
		_intro_done = true
		_seq = []
	elif visual == "carry" and S.has_clip(_kind + "_cstart"):
		_play([[_kind + "_cstart", null, null]], false, "loop")
	else:
		_play([[_kind + "_start", null, _filled(S.clip(_kind + "_start")["holds"].size(), hold)]], false, "loop")
	visual = "loop" if _intro_done else "other"


func _enter_attack(b: BossSim) -> void:
	_move_id = b.move.id
	var mv := S.move(_move_id)
	_sheet = mv["sheet"]
	var c := S.clip(_sheet)
	_holds = (c["holds_phase2"] if b.phase == 2 and c.has("holds_phase2") else c["holds"]).duplicate()
	if mv.get("delayed", false) and c.has("delayed"):
		var dl: Dictionary = c["delayed"]
		_holds[int(dl["pose"])] = int(_holds[int(dl["pose"])]) + int(dl["extra_hold"])
	_entry = ""
	if visual == "loop" and mv.get("entries") != null:
		var e := _nearest_from(int(_loop_pos) % LOOP_POSES)
		var name := "%s_%s_entry_%d" % [mv["entries"], _kind, e]
		if S.has_clip(name):
			_entry = name
			_entry_end = int(S.clip(name)["end"])
	visual = "attack"


func _enter_stagger(prev: int) -> void:
	if prev == BS.ATTACK:
		var start := _interrupt_start("stagger")
		if start != "":
			_play([[start, null, null]], false, "carry")
			return
	if visual == "loop":
		_play([["%s_stagger_%d" % [_kind, _nearest_from(int(_loop_pos) % LOOP_POSES)], null, null]], false, "loop")
		return
	_play([["stagger", null, null]], false, "planted")


## 跪下的那一段（失衡、死亡、從移動中轉場用）：從攻擊／被彈開是被打斷的銜接＋boss_kneel_down 交接之後；
## 從走路是 <移動>_kneel；扛劍站著用往前走第 0 欄那組；其他從站姿跪下
func _down_to_kneel(prev: int) -> Array:
	if prev in [BS.ATTACK, BS.BOUNCED]:
		var start := _interrupt_start("break")
		if start != "":
			return [[start, null, null], ["kneel_down", KNEEL_TAIL, KNEEL_TAIL_HOLDS]]
	var from := visual if visual != "other" else _seq_end
	if from == "loop":
		return [["%s_kneel_%d" % [_kind, _nearest_from(int(_loop_pos) % LOOP_POSES)], null, null]]
	if from == "carry":
		return [["walk_kneel_0", null, null]]
	return [["kneel_down", null, null]]


func _enter_transition(prev: int) -> void:
	var total := Frames.of(VeltharisData.TRANSITION_TIME)
	if visual == "kneel" or prev in [BS.BROKEN, BS.EXECUTED]:
		_play([["transition_kneel", null, null]], false, "planted")
		return
	var tk: Array = S.clip("transition_kneel")["holds"]
	var tail_cols := range(1, tk.size())
	if prev in [BS.ATTACK, BS.BOUNCED]:
		var start := _interrupt_start("break")
		if start != "":
			var tb := S.total(S.clip(start)["holds"])
			var tail_holds := _fit(tk.slice(1), total - tb)
			_play([[start, null, null], ["transition_kneel", tail_cols, tail_holds]], false, "planted")
			return
	if visual == "loop":
		# README「從移動中轉場」：<移動>_kneel 每張 2 幀，接 transition_kneel 第 2–8 欄每張 3 幀、第 9–16 欄 5 5 5 5 5 5 2 2，
		# 最後一張多停 5 幀（共 1.5 秒）
		var kn := "%s_kneel_%d" % [_kind, _nearest_from(int(_loop_pos) % LOOP_POSES)]
		var n: int = S.clip(kn)["holds"].size()
		_play([[kn, null, _filled(n, 2)], ["transition_kneel", range(1, 8), _filled(7, 3)],
			["transition_kneel", range(8, 16), [5, 5, 5, 5, 5, 5, 2, 7]]], false, "planted")
		return
	_play([["transition", null, null]], false, "planted")


func _enter_dead(prev: int) -> void:
	var tail := [["death", DEATH_TAIL, DEATH_TAIL_HOLDS]]
	if prev in [BS.ATTACK, BS.BOUNCED]:
		var start := _interrupt_start("break")
		if start != "":
			_play([[start, null, null], ["kneel_down", KNEEL_TAIL, KNEEL_TAIL_HOLDS]] + tail, false, "kneel")
			return
	if visual == "kneel" or prev in [BS.BROKEN, BS.EXECUTED]:
		_play(tail, false, "kneel")
		return
	var from := visual if visual != "other" else _seq_end
	if from == "loop" or from == "carry":
		_play(_down_to_kneel(prev) + tail, false, "kneel")
		return
	_play([["death", null, null]], false, "kneel")


# --- 每一幀 --------------------------------------------------------------------------

func _tick(b: BossSim) -> void:
	var e := b.state_elapsed()
	match b.state:
		BS.ATTACK:
			_tick_attack(b, e)
		BS.BOUNCED:
			var c := S.clip(_sheet)
			_pose = S.col_at(c["holds"], e)
			clip = _sheet
			col = _pose
			lift = float(c["lift"][_pose]) if c.has("lift") else 0.0
		BS.WALK:
			_tick_walk(b, e)
		BS.IDLE:
			if _pending > 0:
				_pending -= 1
				clip = _kind
				col = int(_loop_pos) % LOOP_POSES
				if _pending == 0:
					var stop := "%s_stop_%d" % [_kind, _nearest_from(int(_loop_pos) % LOOP_POSES)]
					_play([[stop, null, null], ["idle", null, null]], true, "planted", e + 1)
					visual = "other"
				return
			_tick_seq(e)
		_:
			_tick_seq(e)


func _tick_attack(b: BossSim, e: int) -> void:
	var c := S.clip(_sheet)
	_pose = S.col_at(_holds, e)
	if _entry != "" and e < _entry_end:
		clip = _entry
		col = S.col_at(S.clip(_entry)["holds"], e)
	else:
		clip = _sheet
		col = _pose
	lift = float(c["lift"][_pose]) if c.has("lift") else 0.0
	offset = Vector2.ZERO
	if c.has("game_step") and clip == _sheet:
		var ts: Array = c["t"]
		var adv: Array = c["advance"]
		var a0 := float(adv[_pose])
		var now := a0
		if _pose + 1 < ts.size() and float(adv[_pose + 1]) != a0:
			var span := float(int(ts[_pose + 1]) - int(ts[_pose]))
			now = a0 + (float(adv[_pose + 1]) - a0) * clampf(float(e - int(ts[_pose])) / span, 0.0, 1.0)
		offset = -b.facing * (now - a0)


func _tick_walk(b: BossSim, e: int) -> void:
	var moved := b.pos - _last_pos
	_kind = _walk_kind(b, moved)
	if not _intro_done:
		_tick_seq(e)
		if done_at >= 0:
			_intro_done = true
			visual = "loop"
			var joins: int = int(S.clip(_kind + "_start").get("joins", 0))
			_loop_pos = float(joins)
		else:
			return
	_loop_pos = fposmod(_loop_pos + moved.length() / float(S.clip(_kind).get("step", 4.0)), LOOP_POSES)
	clip = _kind
	col = int(_loop_pos) % LOOP_POSES


## 往前走、後退、往他的右手邊／左手邊側移（面向下時他的右手邊是畫面左邊）
func _walk_kind(b: BossSim, moved: Vector2) -> String:
	match b.walk_mode:
		&"approach":
			return "walk"
		&"retreat":
			return "back"
	var right := b.facing.rotated(PI / 2.0)
	var side := moved
	if side.length_squared() < 0.0001:
		var to := b.sim.player.pos - b.pos
		side = to.orthogonal().normalized() * b._strafe_sign
	return "strafe_r" if side.dot(right) > 0.0 else "strafe_l"


func _update_row(b: BossSim) -> void:
	if b.state == BS.ATTACK and b.move != null:
		var i := b.current_hit_index()
		if i >= 0 and b.in_hold(i, b.state_elapsed()):
			return                                   # ★8：延遲停住期間姿勢完全靜止
	var f := b.facing
	if f.length_squared() < 0.0001:
		return
	var a := rad_to_deg(atan2(f.y, f.x))
	if absf(wrapf(a - float(ROW_ANGLE[row]), -180.0, 180.0)) <= 45.0 + ROW_HYSTERESIS_DEG:
		return
	var best := row
	var bd := 999.0
	for r: String in ROW_ANGLE:
		var d := absf(wrapf(a - float(ROW_ANGLE[r]), -180.0, 180.0))
		if d < bd:
			bd = d
			best = r
	row = best


# --- 播一串 --------------------------------------------------------------------------

func _play(seq: Array, loop: bool, end_visual: String, t0 := 0) -> void:
	_seq = seq
	_seq_loop = loop
	_seq_end = end_visual
	_seq_t0 = t0
	done_at = -1
	visual = "other" if not (loop and seq.size() == 1) else end_visual


func _tick_seq(e: int) -> void:
	if _seq.is_empty():
		return
	var t := e - _seq_t0
	for k in _seq.size():
		var part: Array = _seq[k]
		var c := S.clip(part[0])
		var holds: Array = part[2] if part[2] != null else c["holds"]
		var cols: Array = part[1] if part[1] != null else range(holds.size())
		var n := S.total(holds)
		var last := k == _seq.size() - 1
		if t < n or (last and _seq_loop):
			if last and _seq_loop:
				# the looping part (breathing, standing): he is in it from its first frame
				if done_at < 0:
					done_at = e
					visual = _seq_end
				t = t % n
			clip = part[0]
			col = int(cols[S.col_at(holds, t)])
			return
		t -= n
	# 播完：停在最後一張
	var lp: Array = _seq[-1]
	var lc := S.clip(lp[0])
	var lh: Array = lp[2] if lp[2] != null else lc["holds"]
	var lcols: Array = lp[1] if lp[1] != null else range(lh.size())
	clip = lp[0]
	col = int(lcols[-1])
	if done_at < 0:
		done_at = e
		visual = _seq_end


# --- 小工具 --------------------------------------------------------------------------

func _interrupt_start(kind: String) -> String:
	var it := S.interrupt(_sheet)
	if not it.has(kind):
		return ""
	var ps: Array = it[kind]["pose_start"]
	if _pose < 0 or _pose >= ps.size() or int(ps[_pose]) < 0:
		return ""
	return it[kind]["starts"][int(ps[_pose])]


func _nearest_from(c: int) -> int:
	var best := 0
	var bd := 99
	for e: int in STOP_FROM:
		var d := absi(c - e)
		d = mini(d, LOOP_POSES - d)
		if d < bd:
			bd = d
			best = e
	return best


func _filled(n: int, h: int) -> Array:
	var out := []
	for i in n:
		out.append(h)
	return out


func _scaled(holds: Array, k: float) -> Array:
	var out := []
	for h in holds:
		out.append(maxi(1, roundi(float(h) * k)))
	return out


## holds 照比例縮到總長 total（每張至少 1 幀）
func _fit(holds: Array, total: int) -> Array:
	var n := S.total(holds)
	var out := []
	var acc := 0.0
	var done := 0
	for i in holds.size():
		acc += float(holds[i]) * float(total) / float(n)
		var h := maxi(1, roundi(acc) - done)
		out.append(h)
		done += h
	return out
