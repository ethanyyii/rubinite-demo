class_name PlayerAnim
extends RefCounted
## 主角的精靈圖選格（art-progress「給下一個視窗：把主角精靈圖接進遊戲」、附錄 B）。
##
## 每個戰鬥幀呼叫一次 update()（頓幀時戰鬥幀不動，畫面就停在那一格）：依 PlayerSim 的狀態決定畫哪一張圖
## （KnightSheets 的鍵）、哪一列（方向）、哪一欄，以及精靈圖的腳底相對程式位置的偏移。只讀取 sim，不改動它。
## 走路類的循環、起跑與停步、蓄力的收勢、接段選哪個開頭要記得上一幀畫了什麼，所以記在這裡。

const S := PlayerSim.State
const SHEETS := KnightSheets.SHEETS
## 四方向的列（精靈圖由上到下）與各自的面向
const VIEWS: Array[String] = ["south", "east", "north", "west"]
const VIEW_DIRS: Array[Vector2] = [Vector2.DOWN, Vector2.RIGHT, Vector2.UP, Vector2.LEFT]
## 兩列式動作（倒地、擊飛、起身前段、死亡）：第 0 列攻擊者在右、第 1 列在左
const ROW_ATTACKER_RIGHT := 0
const ROW_ATTACKER_LEFT := 1
## 面向在斜角附近時，要超過斜角這麼多度才換方向（類比搖桿在 45° 附近不會來回閃；鍵盤的斜向保持原本的方向）
const ROW_HYSTERESIS_DEG := 6.0
## 擊飛的拋物線最高點（px；畫面用，程式只有水平位移）
const LAUNCH_LIFT := 14.0

## 這一幀要畫的格
var sheet := "idle"
var row := 0
var col := 0
## 精靈圖的腳底相對程式位置的偏移：攻擊前進時畫面在換圖那一幀才跟上（第 2 批決定 2）、擊飛的高度
var offset := Vector2.ZERO
## 這一幀是躺在地上的圖（畫面用：陰影變寬）
var lying := false

var _p: PlayerSim
var _frame := -1
## 這個戰鬥幀選格時看到的狀態，與選格前「上一幀畫了什麼」（同一幀重選時用）
var _sig: Array = []
var _before: Array = [-1, "", 0]
var _prev_state := -1
var _prev_sheet := ""
var _prev_col := 0
var _row := -1
## 攻擊：這一段開始的戰鬥幀、這一段是不是播「從站姿的開頭」
var _attack_start := -1
var _attack_entry := false
## 移動類：循環走到第幾張（小數，依移動距離前進）、上一幀畫的是哪一類
var _cycle := 0.0
var _loco := ""
var _run_start_at := -1
## 奔跑放開搖桿：循環照 2 模擬幀一張繼續播到能接停步的那張；停步開始的幀與版本
var _run_release := false
var _run_frame_at := -1
var _run_stop_at := -1
var _run_stop_col := 0
var _idle_since := 0
var _idle_start := -1
var _charge_out_at := -1
var _down_start := -1
var _down_from_launch := false


## 四方向裡最接近 dir 的一列（斜角算側面）
static func view_of(dir: Vector2) -> int:
	if absf(dir.x) >= absf(dir.y):
		return 1 if dir.x >= 0.0 else 3
	return 0 if dir.y > 0.0 else 2


## t 落在 durs[from..to) 的哪一欄（超過就停在最後一欄）
static func span_col(durs: Array, t: int, from := 0, to := -1) -> int:
	var end := durs.size() if to < 0 else to
	var acc := 0
	for i in range(from, end):
		acc += int(durs[i])
		if t < acc:
			return i
	return end - 1


## durs[from..to) 當循環播，第 t 幀是哪一欄
static func loop_col(durs: Array, t: int, from: int, to: int) -> int:
	var total := 0
	for i in range(from, to):
		total += int(durs[i])
	return span_col(durs, posmod(t, total), from, to)


static func durs_sum(durs: Array, from := 0, to := -1) -> int:
	var end := durs.size() if to < 0 else to
	var acc := 0
	for i in range(from, end):
		acc += int(durs[i])
	return acc


static func col_named(sheet_key: String, frame_name: String) -> int:
	return (SHEETS[sheet_key]["names"] as Array).find(frame_name)


## 程式在攻擊的第 e 幀之後前進了多少（player_sim._run_state_frame：判定期間每幀平均前進）
static func attack_advance(a: PlayerAttackData, e: int) -> float:
	var st := a.startup_frames()
	var n := a.active_end_frame() - st
	return a.advance * clampf(float(e - st + 1) / n, 0.0, 1.0)


## 移動方向相對面向：前進、後退、往角色的左邊（side）、右邊（rside）
static func step_kind(facing: Vector2, move: Vector2) -> String:
	var a := facing.angle_to(move)
	if absf(a) <= PI * 0.25 + 0.0001:
		return "fwd"
	if absf(a) >= PI * 0.75 - 0.0001:
		return "back"
	return "side" if a < 0.0 else "rside"


## 每個戰鬥幀呼叫一次；同一個戰鬥幀重複呼叫不會重算（頓幀時畫面停在那一格）。
## 例外：同一個戰鬥幀裡狀態、格擋或彈返變了（受擊在模擬的一步之外結算，例如測試與截圖腳本），就照新的狀態重選
func update(p: PlayerSim) -> void:
	var now := p.sim.combat_frame
	if p != _p or now < _frame:
		_reset(p)
	var sig := [p.state, p.state_start, p.last_parry_frame, p.last_block_frame]
	if now == _frame:
		if sig == _sig:
			return
		# 重選時「上一幀畫了什麼」仍是上一個戰鬥幀的
		_prev_state = _before[0]
		_prev_sheet = _before[1]
		_prev_col = _before[2]
	else:
		_before = [_prev_state, _prev_sheet, _prev_col]
	_frame = now
	_sig = sig
	offset = Vector2.ZERO
	lying = false
	_pick(p, now)
	_prev_state = p.state
	_prev_sheet = sheet
	_prev_col = col


func _reset(p: PlayerSim) -> void:
	_p = p
	_frame = -1
	_sig = []
	_prev_state = -1
	_prev_sheet = ""
	_row = -1
	_attack_start = -1
	_cycle = 0.0
	_loco = ""
	_run_start_at = -1
	_run_release = false
	_run_stop_at = -1
	_idle_start = -1
	_charge_out_at = -1
	_down_start = -1


## 面向的列（帶遲滯：斜角附近保持上一幀的方向）。每幀只對 p.facing 呼叫一次
func _facing_row(dir: Vector2) -> int:
	var r := view_of(dir)
	if _row >= 0 and r != _row and dir.normalized().dot(VIEW_DIRS[_row]) >= cos(deg_to_rad(45.0 + ROW_HYSTERESIS_DEG)):
		r = _row
	_row = r
	return r


## 兩列式動作：攻擊者在右還是在左（受擊時從主角指向攻擊者的方向；正上下方時看面向）
static func side_row(p: PlayerSim) -> int:
	var x := p.last_hit_dir.x
	if absf(x) < 0.001:
		x = p.facing.x
	return ROW_ATTACKER_RIGHT if x >= 0.0 else ROW_ATTACKER_LEFT


func _show(key: String, r: int, c: int) -> void:
	sheet = key
	row = r
	col = c


func _timeline(key: String, r: int, t: int) -> void:
	_show(key, r, span_col(SHEETS[key]["durs"], t))


## 依名字排的時間表（死亡、擊飛落地：倒地的幾張照另一組時間）
func _named_timeline(key: String, r: int, table: Array, t: int) -> void:
	var acc := 0
	var name: String = table[table.size() - 1][0]
	for entry: Array in table:
		acc += int(entry[1])
		if t < acc:
			name = entry[0]
			break
	_show(key, r, col_named(key, name))


func _pick(p: PlayerSim, now: int) -> void:
	var e := p.state_elapsed()
	var frow := _facing_row(p.facing)
	var moving := p.vel.length_squared() > 0.0
	if p.state != S.IDLE and p.state not in PlayerSim.LOCOMOTION_STATES:
		_loco = ""
	if p.state != S.IDLE:
		# 起跑、停步只在待機裡播；被其他動作打斷就不再接回來
		_run_start_at = -1
		_run_release = false
		_run_stop_at = -1
	match p.state:
		S.ATTACK:
			_pick_attack(p, e, frow)
		S.CHARGE:
			var cd: Array = SHEETS["charge"]["durs"]
			var in_len := durs_sum(cd, 0, 2)
			if e < in_len:
				_loco = ""
				_show("charge", frow, span_col(cd, e, 0, 2))
			elif moving:
				_walk_cycle(p, "charge_walk", frow)
			else:
				_loco = ""
				_show("charge", frow, loop_col(cd, e - in_len, 2, 6))
		S.THRUST:
			_timeline("thrust", frow, e)
		S.EXECUTE:
			_timeline("execute", frow, e)
		S.DODGE:
			_pick_dodge(p, e, frow)
		S.BLOCK:
			_pick_guard(p, now, frow, moving)
		S.HEAL:
			var hd: Array = SHEETS["heal"]["durs"]
			if moving and e >= durs_sum(hd, 0, 2) and e < durs_sum(hd, 0, 6):
				_walk_cycle(p, "heal_walk", frow)
			else:
				_loco = ""
				_timeline("heal", frow, e)
		S.STAGGER:
			_timeline("stagger", view_of(p.last_hit_dir), e)
		S.LAUNCHED:
			var ld: Array = SHEETS["launch"]["durs"]
			_show("launch", side_row(p), loop_col(ld, e, 0, ld.size()))
			var k := clampf(float(e) / Frames.of(PlayerData.LAUNCH_TIME), 0.0, 1.0)
			offset = Vector2(0, -4.0 * LAUNCH_LIFT * k * (1.0 - k))
			lying = true
		S.DOWN:
			if p.state_start != _down_start:
				_down_start = p.state_start
				_down_from_launch = _prev_state == S.LAUNCHED
			if _down_from_launch:
				_named_timeline("knockdown", side_row(p), KnightSheets.LAUNCH_DOWN, e)
			else:
				_timeline("knockdown", side_row(p), e)
			lying = col >= col_named("knockdown", "著地")
		S.GETUP:
			var floor_len := durs_sum(SHEETS["getup_floor"]["durs"])
			if e < floor_len:
				_timeline("getup_floor", side_row(p), e)
				lying = true
			else:
				_timeline("getup", frow, e - floor_len)
		S.POSTURE_BREAK:
			_pick_posture_break(e, frow)
		S.DEAD:
			_named_timeline("knockdown", side_row(p), KnightSheets.DEATH, e)
			lying = col >= col_named("knockdown", "著地")
		_:
			_pick_idle(p, now, frow, moving)


## 輕攻擊：畫格照這一段的模擬幀；在上一段「回站姿」的畫格或待機中（接段寬限）接段時，第一張播從站姿的開頭
func _pick_attack(p: PlayerSim, e: int, frow: int) -> void:
	var key := "attack%d" % (p.combo_index + 1)
	var t: Dictionary = SHEETS[key]
	if p.state_start != _attack_start:
		_attack_start = p.state_start
		_attack_entry = int(t["entry_col"]) >= 0 and (_prev_state == S.IDLE or _was_late())
	var firsts: Array = t["first"]
	var c := 0
	for i in firsts.size():
		if e >= int(firsts[i]):
			c = i
	_show(key, frow, int(t["entry_col"]) if _attack_entry and c == 0 else c)
	# 精靈圖畫在「這一張開始那一幀程式所在的位置」：站地的腳不滑，畫面在換圖時才跟上
	offset = -p.facing * (attack_advance(p.attack, e) - float(t["adv"][c]))


func _was_late() -> bool:
	if not _prev_sheet.begins_with("attack"):
		return false
	var late: Array = SHEETS[_prev_sheet]["late"]
	return _prev_col < late.size() and bool(late[_prev_col])


## 閃身（定案 6）：往前或側邊閃畫衝刺（朝閃身方向）；往後超過 90° 畫後跳（朝面向）。
## 收招：衝刺朝面向時用煞停，側閃（衝刺方向和面向不同列）轉回面向、用後跳的落地
func _pick_dodge(p: PlayerSim, e: int, frow: int) -> void:
	if absf(p.facing.angle_to(p.dodge_dir)) > PI * 0.5 + 0.0001:
		_timeline("backstep", frow, e)
		return
	var drow := frow if p.dodge_dir.is_equal_approx(p.facing) else view_of(p.dodge_dir)
	var dd: Array = SHEETS["dash"]["durs"]
	if e < durs_sum(dd, 0, 2) or drow == frow:
		_timeline("dash", drow, e)
	else:
		_timeline("backstep", frow, e)


## 格擋：按住時四個階段的呼吸；普通格擋受力 6 幀；完美彈返停在頓幀加 6 幀，再兩張收回；移動時慢步腿
func _pick_guard(p: PlayerSim, now: int, frow: int, moving: bool) -> void:
	var gd: Array = SHEETS["guard"]["durs"]
	var deflect := int(gd[5]) - FeedbackData.hitstop_frames(&"perfect_parry")
	var parry_end := p.last_parry_frame + deflect + int(gd[6]) + int(gd[7])
	var hit_end := p.last_block_frame + int(gd[4])
	if now < parry_end:
		_loco = ""
		var since := now - p.last_parry_frame
		_show("guard", frow, 5 if since < deflect else span_col(gd, since - deflect, 6, 8))
	elif now < hit_end:
		_loco = ""
		_show("guard", frow, 4)
	elif moving:
		_walk_cycle(p, "guard_walk", frow)
	else:
		# 呼吸從按下格擋、或彈返收回／受力結束時的第 1 階段開始（收回的兩張是往按住的第 1 張內插的）
		_loco = ""
		_show("guard", frow, loop_col(gd, now - maxi(p.state_start, maxi(parry_end, hit_end)), 0, 4))


## 架勢崩潰：膝蓋一軟、跪地，搖晃四個階段重複到撐起前，撐起、半站
func _pick_posture_break(e: int, frow: int) -> void:
	var d: Array = SHEETS["guard_break"]["durs"]
	var total := Frames.of(PlayerData.POSTURE_BREAK_TIME)
	var pre := durs_sum(d, 0, 3)
	var post := durs_sum(d, 7, 9)
	if e < pre:
		_show("guard_break", frow, span_col(d, e, 0, 3))
	elif e < total - post:
		_show("guard_break", frow, loop_col(d, e - pre, 3, 7))
	else:
		_show("guard_break", frow, span_col(d, e - (total - post), 7, 9))


## 移動類的循環（格擋、蓄力、治療移動用各自的一組；鎖定走路、走路、奔跑在 _pick_idle）：
## 依移動方向和面向選前進／後退／側移，張數依移動距離前進（全速時每張停 durs 個模擬幀，慢的時候跟著慢，腳不滑）
func _walk_cycle(p: PlayerSim, key: String, frow: int) -> void:
	var kind := step_kind(p.facing, p.vel)
	var names: Array = SHEETS[key]["names"]
	var first := names.find(kind + " 1")
	var n := 8 if kind == "fwd" or kind == "back" else 4
	_cycle_frame(p, key, frow, first, n, key)


## 顯示循環目前那一張（first 起 n 張），然後依這一幀的速度往前推。上一幀不是移動類時從第 1 張開始；
## 同一類裡換方向（前進 ↔ 側移）或換圖（走路 ↔ 格擋移動）時接著目前的步相
func _cycle_frame(p: PlayerSim, key: String, r: int, first: int, n: int, family: String) -> void:
	if _loco == "":
		_cycle = 0.0
	_loco = family
	_show(key, r, first + posmod(int(_cycle), n))
	var cap := p.max_speed_for(p.state, p.locked, p.running)
	_cycle += p.vel.length() / cap / float(SHEETS[key]["durs"][col])


## 待機（含走、跑、鎖定走路）：蓄力沒蓄滿放開的收勢、起跑、停步、呼吸
func _pick_idle(p: PlayerSim, now: int, frow: int, moving: bool) -> void:
	if p.state_start != _idle_start:
		_idle_start = p.state_start
		_charge_out_at = now if _prev_state == S.CHARGE else -1
	# 搖桿有沒有按著（放開時程式在 4 幀內減速停下）
	var held := moving and not p.is_braking()
	if _charge_out_at >= 0:
		var cd: Array = SHEETS["charge"]["durs"]
		if held or now - _charge_out_at >= durs_sum(cd, 6, 8):
			_charge_out_at = -1  # 收勢是純畫面，任何輸入立即打斷
		else:
			_loco = ""
			_show("charge", frow, span_col(cd, now - _charge_out_at, 6, 8))
			return
	if held:
		_run_release = false
		_run_stop_at = -1
	if held and p.running:
		_pick_run(p, now, frow)
		return
	if held or (moving and _loco == "walk"):
		if p.locked and step_kind(p.facing, p.vel) != "fwd":
			var kind := step_kind(p.facing, p.vel)
			var names: Array = SHEETS["walk_locked"]["names"]
			_cycle_frame(p, "walk_locked", frow, names.find(kind + " 1"), 8 if kind == "back" else 4, "walk")
		else:
			_cycle_frame(p, "walk", frow, 1, 8, "walk")
		return
	if (_loco == "run" or _run_release or _run_stop_at >= 0) and _pick_run_stop(now, frow):
		return
	if _prev_sheet != "idle":
		_idle_since = now
	_loco = ""
	_show("idle", frow, loop_col(SHEETS["idle"]["durs"], now - _idle_since, 0, 4))


## 奔跑：從站著（或停步中）起跑先播起跑兩張，接循環的 RUN_START_PHASE；從走路直接接循環
func _pick_run(p: PlayerSim, now: int, frow: int) -> void:
	var rd: Array = SHEETS["run"]["durs"]
	var s1 := col_named("run", "起跑 1")
	if _loco != "run" and _loco != "run_start" and _loco != "walk":
		_run_start_at = now
	if _run_start_at >= 0:
		var t := now - _run_start_at
		if t < durs_sum(rd, s1, s1 + 2):
			_loco = "run_start"
			_show("run", frow, span_col(rd, t, s1, s1 + 2))
			return
		_run_start_at = -1
		_cycle = float(KnightSheets.RUN_START_PHASE[VIEWS[frow]])
	_loco = "run"
	_show("run", frow, posmod(int(_cycle), 8))
	_cycle += p.vel.length() / p.max_speed_for(p.state, p.locked, p.running) / float(rd[col])


## 放開搖桿時的奔跑：循環照每張的停留幀數繼續播，到能接停步 1 的那張（RUN_STOP_FROM）就接停步 1A／1B、2、3。
## 放開那一幀的那張不能接時先播下一張。回傳 false ＝停步播完了（回待機）
func _pick_run_stop(now: int, frow: int) -> bool:
	var rd: Array = SHEETS["run"]["durs"]
	if _run_stop_at < 0:
		var table: Array = KnightSheets.RUN_STOP_FROM[VIEWS[frow]]
		var j := posmod(int(_cycle), 8)
		var stop := false
		if not _run_release:
			_run_release = true
			_run_frame_at = now
			if String(table[j]) != "":
				stop = true
			else:
				j = posmod(j + 1, 8)
		elif now - _run_frame_at >= int(rd[j]):
			if String(table[j]) != "":
				stop = true
			else:
				j = posmod(j + 1, 8)
				_run_frame_at = now
		_cycle = float(j)
		if not stop:
			_loco = "run"
			_show("run", frow, j)
			return true
		_run_stop_at = now
		_run_stop_col = col_named("run", "停步 1" + String(table[j]))
	var t := now - _run_stop_at
	var s2 := col_named("run", "停步 2")
	var first_len := int(rd[_run_stop_col])
	if t >= first_len + durs_sum(rd, s2, s2 + 2):
		_run_stop_at = -1
		_run_release = false
		return false
	_loco = "run_stop"
	_show("run", frow, _run_stop_col if t < first_len else span_col(rd, t - first_len, s2, s2 + 2))
	return true
