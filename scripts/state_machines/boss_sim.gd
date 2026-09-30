class_name BossSim
extends RefCounted
## Boss 的狀態機（combat-design §11、boss-veltharis.md）。
##
## 出招引擎：每招是一串 BossHitData，各擊的判定開始幀 = 各段間隔換算後相加（BossMoveData.hit_start_frames）。
## 起手期間追蹤玩家，命中前 lock_before 秒鎖定方向（boss §3）。延遲版在停住期間姿勢與位置靜止（★8）。
## 控制模式：DUMMY（木樁，不出招）、TRAINING（訓練木樁，定時出同一招）、MANUAL（F3，數字鍵指定）、AI（M4）。

enum State { IDLE, WALK, ATTACK, BOUNCED, STAGGER, BROKEN, EXECUTED, RISING, TRANSITION, DEAD }
enum Mode { DUMMY, TRAINING, MANUAL, AI }

const STATE_NAMES := ["IDLE", "WALK", "ATTACK", "BOUNCED", "STAGGER", "BROKEN", "EXECUTED", "RISING",
	"TRANSITION", "DEAD"]
const TG := CombatTypes.Telegraph
const SH := CombatTypes.Shape

## 用弱參照持有 CombatSim，避免 sim ↔ 角色的循環參照造成記憶體洩漏
var sim: CombatSim:
	get:
		return _sim_ref.get_ref()
var _sim_ref: WeakRef
var pos := ArenaGeometry.BOSS_SPAWN
var facing := Vector2.DOWN
var hp := VeltharisData.MAX_HP
var toughness := VeltharisData.MAX_TOUGHNESS
var phase := 1
var state := State.IDLE
var state_start := 0
## 最後一次被削韌的戰鬥幀（§11.3 韌性回復計時）
var last_toughness_damage := -100000
var mode := Mode.DUMMY
## 畫面用：Boss 只畫左右兩個朝向（boss §8.1）。延遲停住期間鎖住左右，姿勢才不會因為玩家繞到另一側而翻面（★8）
var draw_side := 1.0

# --- 出招 ---
var move: BossMoveData
var _hit_starts := PackedInt32Array()
## 每一擊是否已經有結果（命中、格擋或彈返）：同一擊只結算一次
var _hit_resolved: Array[bool] = []
var _danger_sent: Array[bool] = []
## 彈開的持續幀數
var _bounce_frames := 0

# --- 訓練木樁／手動 ---
var training_move := &"royal_sweep"
var training_interval := 2.0
var _next_attack_frame := 0
var _queued_move := &""

# --- AI（boss §6） ---
var ai := BossAI.new()
## 走路（喘息、逼近、側移、後退）：模式、速度、結束幀、停下距離、側移方向
var walk_mode := &"strafe"
var walk_speed := VeltharisData.WALK_SPEED
var _walk_until := 0
var _walk_stop := 0.0
var _strafe_sign := 1.0
## 這次走路是不是喘息（§6.2 規則 5）：喘息一定走滿時間；逼近（AI 選到的動作）走到距離就立刻決定下一招
var _walk_is_breather := false
## 待執行的懲罰技（架勢崩潰、治療）：在這一幀開始；-1 表示沒有
var _punish_at := -1
var _punish_move := &""
## 最後一次短僵直開始的幀（★6 冷卻 3 秒）
var last_short_stagger := -100000
## 最近一個結束的動作（測試與統計用）
var last_action := &""

# --- 墜王之躍（boss §5.2） ---
## 起跳時的位置與目前的落點（落地前 0.3 秒鎖定）
var _takeoff_pos := Vector2.ZERO
var landing_target := Vector2.ZERO
## 落點落在玩家前方這個距離（從起跳方向算），讓 Boss 落在玩家面前而不是頭上
const LEAP_LAND_OFFSET := 53.0  # 原 40；Boss 放大 4/3（2026-09-30，tuning-log）


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


func tick() -> void:
	if state == State.DEAD:
		return
	_check_phase_transition()
	_tick_state()
	_regen_toughness()
	if not (state == State.ATTACK and current_hit_index() >= 0 and in_hold(current_hit_index(), state_elapsed())):
		draw_side = 1.0 if facing.x >= 0.0 else -1.0


func _tick_state() -> void:
	# 待執行的懲罰技（AI 反應 0.1 秒後）
	if _punish_at >= 0 and sim.combat_frame >= _punish_at and state in [State.IDLE, State.WALK]:
		var m := VeltharisData.move(phase, _punish_move)
		_punish_at = -1
		start_move(m)
		return
	var e := state_elapsed()
	match state:
		State.IDLE:
			_face_player()
			_decide()
		State.WALK:
			_tick_walk()
		State.ATTACK:
			_tick_attack()
		State.BOUNCED:
			if e >= _bounce_frames:
				_end_action(true)
		State.STAGGER:
			if e >= Frames.of(VeltharisData.SHORT_STAGGER_TIME):
				_end_action(false)
		State.BROKEN:
			if e >= Frames.of(VeltharisData.BREAK_TIME):
				# 3 秒內沒有處決：自行恢復，韌性回滿（§11.4）
				toughness = VeltharisData.MAX_TOUGHNESS
				sim.emit(&"boss_recover", {"pos": pos})
				_end_action(true)
		State.EXECUTED:
			if e >= Frames.of(PlayerData.EXECUTE_TIME):
				toughness = VeltharisData.MAX_TOUGHNESS
				enter_state(State.RISING)
				_check_phase_transition()  # 處決把 HP 打到一半以下：起身直接換成轉場
		State.RISING:
			if e >= Frames.of(VeltharisData.RISE_TIME):
				_end_action(true)
		State.TRANSITION:
			if e >= Frames.of(VeltharisData.TRANSITION_TIME):
				phase = 2
				sim.emit(&"boss_phase2", {"pos": pos})
				_end_action(true)


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start


func enter_state(s: State) -> void:
	state = s
	state_start = sim.combat_frame


## 是否有實體碰撞（騰空時沒有）
func has_body() -> bool:
	return state != State.DEAD and not is_airborne()


## 能否被鎖定／輔助瞄準（騰空中仍可鎖定）
func is_targetable() -> bool:
	return state != State.DEAD


## 能否被玩家的攻擊打中（轉場無敵 §11.5、騰空 §5.2、被處決中）
func can_be_hit() -> bool:
	return state not in [State.DEAD, State.EXECUTED, State.TRANSITION] and not is_airborne()


## 墜王之躍的騰空期間（起跳到落地前一幀）
func is_airborne() -> bool:
	if state != State.ATTACK or move == null or move.airborne_start < 0.0:
		return false
	var e := state_elapsed()
	return e >= Frames.of(move.airborne_start) and e < _hit_starts[0]


## 落點：玩家前方 LEAP_LAND_OFFSET（從起跳位置看過去），並夾回場內、推出柱子（落點陰影就是實際落點）
static func leap_target(from: Vector2, player_pos: Vector2) -> Vector2:
	var d := player_pos - from
	if d.length() <= LEAP_LAND_OFFSET:
		return ArenaGeometry.resolve(from, VeltharisData.HURT_RADIUS)
	return ArenaGeometry.resolve(player_pos - d.normalized() * LEAP_LAND_OFFSET, VeltharisData.HURT_RADIUS)


## §11.5：HP 降到 50% 以下進入第二階段。失衡、被處決中等處決結束（起身直接換成轉場）。
func _check_phase_transition() -> void:
	if phase != 1 or hp > roundi(VeltharisData.MAX_HP * VeltharisData.PHASE2_HP_RATIO):
		return
	if state in [State.BROKEN, State.EXECUTED, State.TRANSITION, State.DEAD]:
		return
	move = null
	_punish_at = -1
	toughness = VeltharisData.MAX_TOUGHNESS
	enter_state(State.TRANSITION)
	sim.feedback(&"boss_break", pos + Vector2(0, -VeltharisData.HEIGHT / 3.0))
	sim.emit(&"boss_transition", {"pos": pos})


func _die() -> void:
	move = null
	_punish_at = -1
	enter_state(State.DEAD)
	sim.emit(&"boss_dead", {"pos": pos})


## 失衡中、玩家在受擊圓邊緣 48px 內（不限方向）時可以處決（§11.4）
func can_be_executed(player_pos: Vector2) -> bool:
	return state == State.BROKEN and player_pos.distance_to(pos) - VeltharisData.HURT_RADIUS <= PlayerData.EXECUTE_RANGE


# --- 控制模式 -----------------------------------------------------------------------

func set_dummy() -> void:
	mode = Mode.DUMMY


## 訓練木樁：每招結束後 interval 秒再出同一招
func set_training(move_id: StringName, interval: float) -> void:
	mode = Mode.TRAINING
	training_move = move_id
	training_interval = interval
	_next_attack_frame = sim.combat_frame + Frames.of(interval)


## F3：停止自動出招，改由 queue_move 指定
func set_manual() -> void:
	mode = Mode.MANUAL
	_queued_move = &""


## AI（boss §6）。開場先喘息一下
func set_ai() -> void:
	mode = Mode.AI
	start_breather(Frames.of(1.0))


## 測試與開場用：進入喘息（走路），持續 frames 幀
func start_breather(frames: int) -> void:
	move = null
	var dist := pos.distance_to(sim.player.pos)
	_strafe_sign = 1.0 if sim.rng.randf() < 0.5 else -1.0
	if dist > VeltharisData.NEAR_RANGE and not _player_is_down():
		_start_walk(&"approach", VeltharisData.WALK_SPEED, frames, VeltharisData.NEAR_RANGE - 20.0)
	else:
		_start_walk(&"strafe", VeltharisData.WALK_SPEED, frames, 0.0)
	_walk_is_breather = true


## 測試用：下一幀立刻決定下一個動作
func decide_now() -> void:
	move = null
	enter_state(State.IDLE)


func queue_move(move_id: StringName) -> void:
	_queued_move = move_id


func _decide() -> void:
	match mode:
		Mode.AI:
			_ai_decide()
		Mode.TRAINING:
			if sim.combat_frame >= _next_attack_frame:
				start_move(VeltharisData.move(phase, training_move))
		Mode.MANUAL:
			if _queued_move != &"":
				var m := VeltharisData.move(phase, _queued_move)
				_queued_move = &""
				if m != null:
					start_move(m)


## 一個動作（出招、彈開、僵直、失衡、起身）結束。AI 模式下 breather 為 true 時先喘息，否則立刻決定下一招。
func _end_action(breather: bool = true) -> void:
	if state == State.ATTACK:
		sim.emit(&"boss_move_end", {"move": move.id})
		last_action = &"attack_end"
	move = null
	enter_state(State.IDLE)
	if mode == Mode.TRAINING:
		_next_attack_frame = sim.combat_frame + Frames.of(training_interval)
	elif mode == Mode.AI and breather:
		start_breather(ai.breather_frames(self))


# --- AI 執行 -----------------------------------------------------------------------

## 玩家倒地時不出招，後退或踱步（§6.2 規則 6）
func _player_is_down() -> bool:
	return sim.player.state in [PlayerSim.State.LAUNCHED, PlayerSim.State.DOWN, PlayerSim.State.GETUP] \
		or sim.player.state == PlayerSim.State.DEAD


func _ai_decide() -> void:
	if _punish_at >= 0:
		return  # 等懲罰技
	var dist := pos.distance_to(sim.player.pos)
	if _player_is_down():
		if dist < VeltharisData.NEAR_RANGE:
			_start_walk(&"retreat", VeltharisData.WALK_SPEED, 20, 0.0)
		else:
			_start_walk(&"strafe", VeltharisData.WALK_SPEED, 20, 0.0)
		return
	var choice := ai.choose(self)
	match choice:
		&"approach_slow":
			_start_walk(&"approach", VeltharisData.WALK_SPEED, Frames.of(VeltharisData.APPROACH_MAX_TIME), VeltharisData.NEAR_RANGE - 10.0)
		&"approach_fast":
			_start_walk(&"approach", VeltharisData.FAST_SPEED, Frames.of(VeltharisData.APPROACH_MAX_TIME), VeltharisData.MID_RANGE - 20.0)
		_:
			start_move(VeltharisData.move(phase, choice))


func _start_walk(mode_name: StringName, speed: float, frames: int, stop_distance: float) -> void:
	_walk_is_breather = false
	walk_mode = mode_name
	walk_speed = speed
	_walk_until = sim.combat_frame + frames
	_walk_stop = stop_distance
	enter_state(State.WALK)


## 走路：一律面向玩家。
## - 逼近（AI 選到的動作）：走到停下距離或時間到就決定下一招。
## - 喘息：一定走滿時間（§6.2 規則 5）；逼近到停下距離後改成側移。玩家倒地時不靠近：近距離（NEAR_RANGE）內後退、否則側移（規則 6）。
func _tick_walk() -> void:
	_face_player()
	var to := sim.player.pos - pos
	var dist := to.length()
	var step := walk_speed / Frames.FPS
	if _walk_is_breather and _player_is_down():
		walk_mode = &"retreat" if dist < VeltharisData.NEAR_RANGE else &"strafe"
	match walk_mode:
		&"approach":
			if dist <= _walk_stop:
				if _walk_is_breather:
					walk_mode = &"strafe"
				else:
					enter_state(State.IDLE)
					return
			else:
				pos += to / maxf(dist, 0.001) * minf(step, dist - _walk_stop)
		&"strafe":
			var side := to.orthogonal().normalized() * _strafe_sign
			var next := pos + side * step
			if not ArenaGeometry.is_inside(next, VeltharisData.HURT_RADIUS + 4.0):
				_strafe_sign = -_strafe_sign
			else:
				pos = next
		&"retreat":
			var next := pos - to / maxf(dist, 0.001) * step
			if ArenaGeometry.is_inside(next, VeltharisData.HURT_RADIUS + 4.0):
				pos = next
			else:
				walk_mode = &"strafe"
	if sim.combat_frame >= _walk_until:
		enter_state(State.IDLE)


## 玩家架勢崩潰（★2、§6.2 規則 1）：立刻中斷目前的動作，0.1 秒反應後出裁決突刺
func on_player_posture_break() -> void:
	if mode != Mode.AI or state in [State.BOUNCED, State.STAGGER, State.BROKEN, State.EXECUTED, State.RISING,
			State.TRANSITION, State.DEAD]:
		return
	_schedule_punish(&"judgment_thrust")


## 玩家在 HEAL_PUNISH_RANGE 內治療（§6.2 規則 2）：70% 機率立刻懲罰（一階段裁決突刺、二階段墜王之躍）。
## 只在 Boss 空檔（待機、走路、收招）時中斷；正在起手或判定就讓這一招打完。
func on_player_heal() -> void:
	if mode != Mode.AI or pos.distance_to(sim.player.pos) > VeltharisData.HEAL_PUNISH_RANGE:
		return
	var free := state in [State.IDLE, State.WALK] or (state == State.ATTACK and current_hit_index() < 0)
	if not free:
		return
	if sim.rng.randf() < VeltharisData.HEAL_PUNISH_CHANCE:
		_schedule_punish(&"judgment_thrust" if phase == 1 else &"kings_leap")


func _schedule_punish(move_id: StringName) -> void:
	move = null
	enter_state(State.IDLE)
	_punish_move = move_id
	_punish_at = sim.combat_frame + Frames.of(VeltharisData.PUNISH_REACTION)


# --- 出招引擎 -----------------------------------------------------------------------

func start_move(m: BossMoveData) -> void:
	move = m
	_hit_starts = m.hit_start_frames()
	_hit_resolved.clear()
	_danger_sent.clear()
	for i in m.hits.size():
		_hit_resolved.append(false)
		_danger_sent.append(false)
	_face_player()
	enter_state(State.ATTACK)
	if m.airborne_start >= 0.0:
		_takeoff_pos = pos
		landing_target = leap_target(pos, sim.player.pos)
	ai.record_move(m.id)
	sim.emit(&"boss_attack", {"move": m.id, "pos": pos})


## 目前（或下一個）判定的是第幾擊；收招中回傳 -1
func current_hit_index() -> int:
	var e := state_elapsed()
	for i in move.hits.size():
		if e < _hit_starts[i] + Frames.of(move.hits[i].active):
			return i
	return -1


func hit_start_frame(i: int) -> int:
	return _hit_starts[i]


## 第 i 擊的起手開始幀（第一擊是 0，之後是前一擊的判定開始）
func windup_start(i: int) -> int:
	return 0 if i == 0 else _hit_starts[i - 1]


func _tick_attack() -> void:
	var e := state_elapsed()
	if e >= move.total_frames():
		_end_action()
		return
	var i := current_hit_index()
	if i < 0:
		return  # 收招
	var hit: BossHitData = move.hits[i]
	var start := _hit_starts[i]
	var lock_at := start - Frames.of(hit.lock_before)
	if e < start:
		if move.airborne_start >= 0.0:
			_tick_leap(e, start, lock_at)
		# 起手：鎖定前追蹤玩家方向；延遲停住期間不移動（姿勢靜止），但方向照常追蹤到鎖定點
		elif e < lock_at:
			_face_player()
			if not in_hold(i, e):
				_advance_toward_player()
		if hit.attack_type == CombatTypes.AttackType.UNBLOCKABLE and not _danger_sent[i] \
				and e >= start - Frames.of(hit.danger_time):
			_danger_sent[i] = true
			sim.emit(&"danger", {"pos": pos})
	else:
		if e == start:
			sim.emit(&"boss_swing", {"pos": pos, "anim": hit.anim, "type": hit.attack_type})
		if hit.lunge_distance > 0.0:
			# 判定期間：突刺前進
			pos += facing * (hit.lunge_distance / Frames.of(hit.active))


## 墜王之躍：下蹲（0.7 秒）→ 騰空（0.8 秒）飛向落點；落點追蹤玩家到落地前 0.3 秒鎖定
func _tick_leap(e: int, land_at: int, lock_at: int) -> void:
	var air_from := Frames.of(move.airborne_start)
	if e < lock_at:
		_face_player()
		landing_target = leap_target(_takeoff_pos, sim.player.pos)
	if e < air_from:
		return
	var t := float(e - air_from + 1) / float(land_at - air_from)
	pos = _takeoff_pos.lerp(landing_target, clampf(t, 0.0, 1.0))


## 延遲版的停住期間（★8：維持清楚的靜止姿勢：舉劍停在最高點、不移動）
func in_hold(i: int, e: int) -> bool:
	var hit: BossHitData = move.hits[i]
	if hit.delay_hold <= 0.0:
		return false
	var hold_from := windup_start(i) + Frames.of(hit.hold_start)
	return e >= hold_from and e < hold_from + Frames.of(hit.delay_hold)


func _advance_toward_player() -> void:
	if move.startup_advance_speed <= 0.0:
		return
	var to := sim.player.pos - pos
	var dist := to.length()
	if dist <= move.advance_stop_distance:
		return
	var step := minf(move.startup_advance_speed / Frames.FPS, dist - move.advance_stop_distance)
	pos += to / dist * step


func _face_player() -> void:
	var to := sim.player.pos - pos
	if to.length_squared() > 0.01:
		facing = to.normalized()


## 起手預兆（plan §4、boss §7）：一般起手 NORMAL、延遲停住 DELAYED、不可格擋最後 danger_time 秒 DANGER
func telegraph() -> int:
	if state != State.ATTACK:
		return TG.NONE
	var i := current_hit_index()
	if i < 0:
		return TG.NONE
	var e := state_elapsed()
	var hit: BossHitData = move.hits[i]
	var start := _hit_starts[i]
	if e >= start:
		return TG.NONE
	if hit.attack_type == CombatTypes.AttackType.UNBLOCKABLE:
		return TG.DANGER if e >= start - Frames.of(hit.danger_time) else TG.NORMAL
	if in_hold(i, e):
		return TG.DELAYED
	return TG.NORMAL


## 目前生效的攻擊判定；沒有時回傳空字典。由 CombatSim 做相交測試。
func attack_hitbox() -> Dictionary:
	if state != State.ATTACK:
		return {}
	var i := current_hit_index()
	if i < 0 or _hit_resolved[i]:
		return {}
	var e := state_elapsed()
	var start := _hit_starts[i]
	if e < start:
		return {}
	var hit: BossHitData = move.hits[i]
	var hb := {"hit": hit, "index": i, "origin": pos, "dir": facing, "shape": hit.shape}
	if hit.shape == SH.RING:
		hb["ring_radius"] = ring_radius(hit, e - start)
	return hb


## 衝擊環第 f 幀（判定第 0 幀起算）的外緣半徑：判定期間內從 0 線性擴張到最大半徑
static func ring_radius(hit: BossHitData, f: int) -> float:
	return hit.radius * float(f + 1) / Frames.of(hit.active)


## 預覽用：目前這一擊（起手中也回傳）；沒有時回傳空字典
func preview_hitbox() -> Dictionary:
	if state != State.ATTACK:
		return {}
	var i := current_hit_index()
	if i < 0:
		return {}
	var hit: BossHitData = move.hits[i]
	var e := state_elapsed()
	var start := _hit_starts[i]
	var windup := windup_start(i)
	var origin := landing_target if move.airborne_start >= 0.0 else pos
	return {"hit": hit, "origin": origin, "dir": facing, "shape": hit.shape, "active": e >= start,
		"resolved": _hit_resolved[i], "progress": clampf(float(e - windup) / maxf(start - windup, 1), 0.0, 1.0),
		"ring_radius": ring_radius(hit, e - start) if e >= start else 0.0}


func mark_hit_resolved(i: int) -> void:
	_hit_resolved[i] = true


func is_hit_resolved(i: int) -> bool:
	return _hit_resolved[i]


## 目前狀態還剩幾幀（機器人判斷空檔用）
func remaining_frames() -> int:
	var e := state_elapsed()
	match state:
		State.ATTACK:
			return move.total_frames() - e
		State.WALK:
			return _walk_until - sim.combat_frame
		State.BOUNCED:
			return _bounce_frames - e
		State.STAGGER:
			return Frames.of(VeltharisData.SHORT_STAGGER_TIME) - e
		State.BROKEN:
			return Frames.of(VeltharisData.BREAK_TIME) - e
		State.EXECUTED:
			return Frames.of(PlayerData.EXECUTE_TIME) - e
		State.RISING:
			return Frames.of(VeltharisData.RISE_TIME) - e
	return 0


# --- 被彈返、被格擋、命中 --------------------------------------------------------------

## 完美彈返（combat-design §6）：削韌；單發或最後一擊讓 Boss 彈開
func on_parried(hit: BossHitData) -> void:
	ai.block_streak = 0
	_lose_toughness(hit.toughness_damage)
	if hit.bounce_time > 0.0 and state == State.ATTACK:
		_bounce_frames = Frames.of(hit.bounce_time)
		move = null
		enter_state(State.BOUNCED)
		sim.emit(&"boss_bounced", {"pos": pos, "time": hit.bounce_time})


func on_blocked(_hit: BossHitData) -> void:
	ai.block_streak += 1


func on_hit_player(_hit: BossHitData) -> void:
	ai.block_streak = 0


func _lose_toughness(amount: float) -> void:
	if amount <= 0.0:
		return
	toughness = maxf(toughness - amount, 0.0)
	last_toughness_damage = sim.combat_frame
	if toughness <= 0.0 and state not in [State.BROKEN, State.EXECUTED, State.RISING, State.TRANSITION, State.DEAD]:
		_enter_break()


## §11.4 失衡：跪地 3 秒，中斷任何動作
func _enter_break() -> void:
	move = null
	_punish_at = -1
	enter_state(State.BROKEN)
	sim.feedback(&"boss_break", pos + Vector2(0, -VeltharisData.HEIGHT / 3.0))
	sim.emit(&"boss_break", {"pos": pos})


## §11.3 韌性回復：2 秒沒被削韌後，每秒回 10 ×（0.3 + 0.7 × 剩餘 HP 比例）
func _regen_toughness() -> void:
	if state in [State.BROKEN, State.EXECUTED] or toughness >= VeltharisData.MAX_TOUGHNESS:
		return
	if sim.combat_frame - last_toughness_damage < Frames.of(VeltharisData.TOUGHNESS_REGEN_DELAY):
		return
	var ratio := float(hp) / VeltharisData.MAX_HP
	var per_sec := VeltharisData.TOUGHNESS_REGEN_BASE * (VeltharisData.TOUGHNESS_REGEN_FLOOR + (1.0 - VeltharisData.TOUGHNESS_REGEN_FLOOR) * ratio)
	toughness = minf(toughness + per_sec / Frames.FPS, VeltharisData.MAX_TOUGHNESS)


## 被玩家的攻擊打中（combat-design §11.2–11.3）：扣 HP、削韌；
## 第 4 段或重擊在 Boss 待機、走路、收招時打中，而且距上次短僵直 3 秒以上（★6），才短僵直 0.3 秒。
## 出招的起手與判定期間一律霸體。
func receive_player_hit(atk: PlayerAttackData) -> void:
	hp = maxi(hp - atk.damage, 0)
	sim.emit(&"boss_hit", {"damage": atk.damage, "attack": atk.id, "pos": pos})
	if hp <= 0:
		_die()
		return
	_lose_toughness(atk.toughness)
	if atk.can_short_stagger and _can_short_stagger():
		move = null
		last_short_stagger = sim.combat_frame
		enter_state(State.STAGGER)
		sim.emit(&"boss_stagger", {"pos": pos})


func _can_short_stagger() -> bool:
	if sim.combat_frame - last_short_stagger < Frames.of(VeltharisData.SHORT_STAGGER_COOLDOWN):
		return false
	match state:
		State.IDLE, State.WALK:
			return true
		State.ATTACK:
			return current_hit_index() < 0  # 收招
	return false


# --- 處決（§11.4） --------------------------------------------------------------------

## 玩家開始處決：Boss 倒地，和玩家的處決動作同步 1 秒
func begin_execution() -> void:
	enter_state(State.EXECUTED)
	sim.emit(&"execution_start", {"pos": pos})


## 處決突刺命中：最大 HP 的 15%
func receive_execution() -> void:
	var dmg := roundi(VeltharisData.MAX_HP * VeltharisData.EXECUTE_DAMAGE_RATIO)
	hp = maxi(hp - dmg, 0)
	sim.feedback(&"execution", pos + Vector2(0, -VeltharisData.HEIGHT / 3.0))
	sim.emit(&"execution_hit", {"pos": pos, "damage": dmg})
	if hp <= 0:
		_die()
