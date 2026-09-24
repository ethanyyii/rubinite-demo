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


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


func tick() -> void:
	_tick_state()
	if not (state == State.ATTACK and current_hit_index() >= 0 and in_hold(current_hit_index(), state_elapsed())):
		draw_side = 1.0 if facing.x >= 0.0 else -1.0


func _tick_state() -> void:
	match state:
		State.IDLE:
			_face_player()
			_decide()
		State.ATTACK:
			_tick_attack()
		State.BOUNCED:
			if state_elapsed() >= _bounce_frames:
				_end_action()


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start


func enter_state(s: State) -> void:
	state = s
	state_start = sim.combat_frame


## 是否有實體碰撞（騰空時沒有）
func has_body() -> bool:
	return state != State.DEAD


## 能否被鎖定／輔助瞄準
func is_targetable() -> bool:
	return state != State.DEAD


## 能否被玩家的攻擊打中
func can_be_hit() -> bool:
	return state != State.DEAD


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


func queue_move(move_id: StringName) -> void:
	_queued_move = move_id


func _decide() -> void:
	match mode:
		Mode.TRAINING:
			if sim.combat_frame >= _next_attack_frame:
				start_move(VeltharisData.move(phase, training_move))
		Mode.MANUAL:
			if _queued_move != &"":
				var m := VeltharisData.move(phase, _queued_move)
				_queued_move = &""
				if m != null:
					start_move(m)


## 一個動作（出招、彈開）結束，回到待機
func _end_action() -> void:
	move = null
	enter_state(State.IDLE)
	if mode == Mode.TRAINING:
		_next_attack_frame = sim.combat_frame + Frames.of(training_interval)


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
		# 起手：鎖定前追蹤玩家方向；延遲停住期間不移動（姿勢靜止），但方向照常追蹤到鎖定點
		if e < lock_at:
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
	return {"hit": hit, "origin": pos, "dir": facing, "shape": hit.shape, "active": e >= start,
		"resolved": _hit_resolved[i], "progress": clampf(float(e - windup) / maxf(start - windup, 1), 0.0, 1.0),
		"ring_radius": ring_radius(hit, e - start) if e >= start else 0.0}


func mark_hit_resolved(i: int) -> void:
	_hit_resolved[i] = true


# --- 被彈返、被格擋、命中 --------------------------------------------------------------

## 完美彈返（combat-design §6）：削韌；單發或最後一擊讓 Boss 彈開
func on_parried(hit: BossHitData) -> void:
	_lose_toughness(hit.toughness_damage)
	if hit.bounce_time > 0.0 and state == State.ATTACK:
		_bounce_frames = Frames.of(hit.bounce_time)
		move = null
		enter_state(State.BOUNCED)
		sim.emit(&"boss_bounced", {"pos": pos, "time": hit.bounce_time})


func on_blocked(_hit: BossHitData) -> void:
	pass


func on_hit_player(_hit: BossHitData) -> void:
	pass


func _lose_toughness(amount: float) -> void:
	if amount <= 0.0:
		return
	toughness = maxf(toughness - amount, 0.0)
	last_toughness_damage = sim.combat_frame


## 被玩家的攻擊打中（combat-design §11.3：扣 HP、削韌）。
func receive_player_hit(atk: PlayerAttackData) -> void:
	hp = maxi(hp - atk.damage, 0)
	_lose_toughness(atk.toughness)
	sim.emit(&"boss_hit", {"damage": atk.damage, "attack": atk.id, "pos": pos})
