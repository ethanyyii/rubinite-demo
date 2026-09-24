class_name PlayerSim
extends RefCounted
## 主角的狀態機（combat-design §3–§10）。
##
## 計時一律用 sim.combat_frame（頓幀期間暫停）。進入狀態的那一幀 state_elapsed() = 0。

enum State { IDLE, ATTACK, CHARGE, THRUST, DODGE, BLOCK, HEAL, STAGGER, LAUNCHED, DOWN, GETUP, POSTURE_BREAK, EXECUTE, DEAD }

const STATE_NAMES := ["IDLE", "ATTACK", "CHARGE", "THRUST", "DODGE", "BLOCK", "HEAL", "STAGGER",
	"LAUNCHED", "DOWN", "GETUP", "POSTURE_BREAK", "EXECUTE", "DEAD"]

## 能自由移動（走、跑、慢走）的狀態
const LOCOMOTION_STATES := [State.IDLE, State.BLOCK, State.CHARGE, State.HEAL]
## 輸入向量小於這個長度視為沒有輸入（避免極小向量把面向變成零向量）
const INPUT_EPSILON := 0.001

## 用弱參照持有 CombatSim，避免 sim ↔ 角色的循環參照造成記憶體洩漏
var sim: CombatSim:
	get:
		return _sim_ref.get_ref()
var _sim_ref: WeakRef
var pos := ArenaGeometry.PLAYER_SPAWN
var vel := Vector2.ZERO
var facing := Vector2.UP
var hp := PlayerData.MAX_HP
var posture := PlayerData.MAX_POSTURE
var heals := PlayerData.HEAL_CHARGES
var state := State.IDLE
var state_start := 0
var locked := false
## 這一幀是否在奔跑（畫面用）
var running := false

# --- 攻擊（§8） ---
## 目前（或剛結束）的輕攻擊段數 0..3
var combo_index := 0
## 進行中的攻擊資料（輕攻擊某段或重擊突刺）
var attack: PlayerAttackData
## 這一段是否已經打中（每段只打中一次）
var attack_connected := false
var charge_full := false

# --- 閃身（§7） ---
var dodge_dir := Vector2.DOWN
var last_dodge_start := -100000

# --- 輸入緩衝（§3）：只保留最新一次的攻擊／重擊／閃身 ---
var buffered_action := &""
var buffered_at := -100000

# 幀數（Frames.of 四捨五入）
var _buffer_frames := Frames.of(PlayerData.INPUT_BUFFER)
var _cancel_delay := Frames.of(PlayerData.CANCEL_DELAY)
var _dodge_frames := Frames.of(PlayerData.DODGE_TIME)
var _dodge_total := Frames.of(PlayerData.DODGE_TIME) + Frames.of(PlayerData.DODGE_RECOVERY)
var _dodge_inv_start := Frames.of(PlayerData.DODGE_INVULN_START)
var _dodge_inv_end := Frames.of(PlayerData.DODGE_INVULN_END)
var _dodge_interval := Frames.of(PlayerData.DODGE_INTERVAL)
var _charge_frames := Frames.of(PlayerData.CHARGE_TIME)
var _thrust_frames := Frames.of(PlayerData.THRUST_TIME)
var _thrust_stopped := false

## §5：加速 5 幀、減速 4 幀
var _accel_frames := Frames.of(PlayerData.ACCEL_TIME)
var _decel_frames := Frames.of(PlayerData.DECEL_TIME)
## 開始減速時的速度除以減速幀數：無論從多快開始，都在 4 幀內停下
var _decel_step := 0.0


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


## 每個戰鬥幀：鎖定 → 記錄按鍵 → 依時間結束動作 → 開始新動作（含緩衝）→ 本幀的移動與行為 → 鎖定距離檢查。
func tick(input: InputFrame) -> void:
	if input.lock_pressed:
		_toggle_lock()
	_record_presses(input)
	_advance_state(input)
	_try_start_actions(input)
	_run_state_frame(input)
	_check_lock_range()


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start


func enter_state(s: State) -> void:
	state = s
	state_start = sim.combat_frame
	_decel_step = 0.0
	if not can_run_in(s):
		running = false
	if s != State.ATTACK and s != State.THRUST:
		attack = null


## 是否無敵：閃身第 1–9 幀（§7）；之後的里程碑加入倒地、處決。
func is_invulnerable() -> bool:
	if sim.god_mode:
		return true
	if state == State.DODGE:
		var e := state_elapsed()
		return e >= _dodge_inv_start and e < _dodge_inv_end
	return false


## 目前這一幀有效的攻擊判定；沒有時回傳空字典。由 CombatSim 做相交測試。
func attack_hitbox() -> Dictionary:
	if attack == null or attack_connected:
		return {}
	var e := state_elapsed()
	if state == State.ATTACK:
		if e >= attack.startup_frames() and e < attack.active_end_frame():
			return {"shape": &"sector", "origin": pos, "dir": facing, "radius": PlayerData.ATTACK_RADIUS,
				"arc": PlayerData.ATTACK_ARC_DEG, "attack": attack}
	elif state == State.THRUST:
		if e < _thrust_frames:
			return {"shape": &"capsule", "a": pos, "b": pos + facing * PlayerData.THRUST_REACH,
				"width": PlayerData.THRUST_WIDTH, "attack": attack}
	return {}


## CombatSim 判定命中後呼叫
func on_attack_connected() -> void:
	attack_connected = true
	if state == State.THRUST:
		_thrust_stopped = true


# --- 輸入與動作 -------------------------------------------------------------------

func _record_presses(input: InputFrame) -> void:
	var action := &""
	if input.attack_pressed:
		action = &"attack"
	if input.heavy_pressed:
		action = &"heavy"
	if input.dodge_pressed:
		action = &"dodge"
	if action != &"":
		buffered_action = action
		buffered_at = sim.combat_frame


## 依時間結束的動作：攻擊、突刺、閃身收招結束 → 待機；蓄力放開 → 突刺或取消。
func _advance_state(input: InputFrame) -> void:
	var e := state_elapsed()
	match state:
		State.ATTACK:
			if e >= attack.total_frames():
				combo_index = 0
				enter_state(State.IDLE)
		State.THRUST:
			if e >= _thrust_frames + Frames.of(attack.recovery):
				enter_state(State.IDLE)
		State.DODGE:
			if e >= _dodge_total:
				enter_state(State.IDLE)
		State.CHARGE:
			if e >= _charge_frames and not charge_full:
				charge_full = true
				sim.emit(&"charge_full", {"pos": pos})
			if not input.heavy:
				if charge_full:
					_start_thrust(input)
				else:
					sim.emit(&"charge_cancel", {"pos": pos})
					enter_state(State.IDLE)


## 執行緩衝中的動作（若這一幀允許）。緩衝在按下後 9 幀內有效（§3：動作結束前 0.15 秒內按下）。
func _try_start_actions(input: InputFrame) -> void:
	if buffered_action == &"":
		return
	if sim.combat_frame - buffered_at > _buffer_frames:
		buffered_action = &""
		return
	if not can_start(buffered_action):
		return
	var action := buffered_action
	buffered_action = &""
	match action:
		&"attack":
			_start_attack(input)
		&"heavy":
			if input.heavy:
				_start_charge()
		&"dodge":
			_start_dodge(input)


## 這一幀能不能開始某個動作（§8.3 取消規則）。
func can_start(action: StringName) -> bool:
	var e := state_elapsed()
	match action:
		&"attack":
			if state == State.IDLE:
				return true
			# 收招期間按攻擊接下一段（第 4 段之後不能再接）
			return state == State.ATTACK and attack.cancelable and e >= attack.active_end_frame()
		&"heavy":
			return state == State.IDLE
		&"dodge":
			if sim.combat_frame - last_dodge_start < _dodge_interval:
				return false
			match state:
				State.IDLE, State.CHARGE, State.BLOCK:
					return true
				State.ATTACK:
					return attack.cancelable and e >= attack.active_end_frame() + _cancel_delay
	return false


func _start_attack(input: InputFrame) -> void:
	if state == State.ATTACK:
		combo_index = mini(combo_index + 1, PlayerData.light_attacks().size() - 1)
	else:
		combo_index = 0
	attack = PlayerData.light_attacks()[combo_index]
	attack_connected = false
	vel = Vector2.ZERO
	_face_for_attack(input)
	enter_state(State.ATTACK)
	sim.emit(&"player_attack", {"stage": combo_index, "pos": pos, "dir": facing})


func _start_charge() -> void:
	charge_full = false
	enter_state(State.CHARGE)
	sim.emit(&"charge_start", {"pos": pos})


func _start_thrust(input: InputFrame) -> void:
	attack = PlayerData.heavy_thrust()
	attack_connected = false
	_thrust_stopped = false
	vel = Vector2.ZERO
	_face_for_attack(input)
	enter_state(State.THRUST)
	sim.emit(&"player_thrust", {"pos": pos, "dir": facing})


## §7：方向依移動輸入；沒有輸入時往後閃（鎖定中為遠離目標的方向）。
func _start_dodge(input: InputFrame) -> void:
	var dir := input.move.limit_length(1.0)
	if dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		dodge_dir = dir.normalized()
		if not locked:
			facing = dodge_dir
	elif locked:
		var away := pos - sim.boss.pos
		dodge_dir = away.normalized() if away.length_squared() > 0.01 else -facing
	else:
		dodge_dir = -facing
	vel = Vector2.ZERO
	charge_full = false
	combo_index = 0
	last_dodge_start = sim.combat_frame
	enter_state(State.DODGE)
	sim.emit(&"dodge", {"pos": pos, "dir": dodge_dir})


## 攻擊開始時的朝向：鎖定中朝向目標；未鎖定時先轉向當下的移動輸入方向（§9：面向移動方向），
## 再看前方 60°、80px 內有沒有敵人，有就轉向它（輔助瞄準）。80px 以敵人受擊圓的邊緣計算。
func _face_for_attack(input: InputFrame) -> void:
	var to := sim.boss.pos - pos
	if locked and sim.boss.is_targetable() and to.length_squared() > 0.01:
		facing = to.normalized()
		return
	var stick := input.move.limit_length(1.0)
	if stick.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		facing = stick.normalized()
	if to.length_squared() < 0.01 or not sim.boss.is_targetable():
		return
	var in_range := to.length() - VeltharisData.HURT_RADIUS <= PlayerData.AIM_ASSIST_RANGE
	var in_cone := absf(facing.angle_to(to)) <= deg_to_rad(PlayerData.AIM_ASSIST_ARC_DEG) * 0.5
	if in_range and in_cone:
		facing = to.normalized()


## 本幀的移動與行為（狀態可能在這一幀剛進入，elapsed = 0）
func _run_state_frame(input: InputFrame) -> void:
	var e := state_elapsed()
	match state:
		State.ATTACK:
			var a_start := attack.startup_frames()
			var a_frames := attack.active_end_frame() - a_start
			if e >= a_start and e < attack.active_end_frame():
				pos += facing * (attack.advance / a_frames)
		State.THRUST:
			if e < _thrust_frames and not _thrust_stopped:
				pos += facing * (PlayerData.THRUST_DISTANCE / _thrust_frames)
		State.DODGE:
			if e < _dodge_frames:
				pos += dodge_dir * (PlayerData.DODGE_DISTANCE / _dodge_frames)
		_:
			if state in LOCOMOTION_STATES:
				_tick_locomotion(input)


# --- 鎖定（§9） --------------------------------------------------------------------

func _toggle_lock() -> void:
	if locked:
		locked = false
		sim.emit(&"lock_off")
	elif sim.boss.is_targetable() and pos.distance_to(sim.boss.pos) <= PlayerData.LOCK_ACQUIRE_RANGE:
		locked = true
		sim.emit(&"lock_on")


## 目標死亡、距離超過 420px 時解除
func _check_lock_range() -> void:
	if locked and (not sim.boss.is_targetable() or pos.distance_to(sim.boss.pos) > PlayerData.LOCK_BREAK_RANGE):
		locked = false
		sim.emit(&"lock_off")


## §5 速度表。wants_run 是「按住奔跑鍵且有移動」；只有 IDLE 能跑（格擋、蓄力、治療時不能跑）。
func max_speed_for(s: State, is_locked: bool, wants_run: bool) -> float:
	match s:
		State.BLOCK:
			return PlayerData.SPEED_BLOCK
		State.CHARGE:
			return PlayerData.SPEED_CHARGE
		State.HEAL:
			return PlayerData.SPEED_HEAL
	if wants_run and can_run_in(s):
		return PlayerData.SPEED_RUN
	return PlayerData.SPEED_LOCKED if is_locked else PlayerData.SPEED_WALK


static func can_run_in(s: State) -> bool:
	return s == State.IDLE


## 走、跑、慢走共用的移動（LOCOMOTION_STATES）：方向立即跟隨輸入（不滑行），速率線性變化。
## - 加速：每幀 最高速 ÷ 5，從靜止 5 幀到全速。
## - 放開：以放開當下的速度 ÷ 4 為每幀減量，無論多快都 4 幀停下。
## - 速度上限變低（例如從跑進入格擋）：也用減速規則，4 幀內降到新上限，不滑行。
func _tick_locomotion(input: InputFrame) -> void:
	var dir := input.move.limit_length(1.0)
	var has_input := dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON
	running = can_run_in(state) and input.run and has_input
	var speed := vel.length()
	if not has_input:
		if _decel_step <= 0.0:
			_decel_step = speed / _decel_frames
		speed = move_toward(speed, 0.0, _decel_step)
		if speed <= 0.0:
			_decel_step = 0.0
			vel = Vector2.ZERO
		else:
			vel = vel.normalized() * speed
	else:
		_decel_step = 0.0
		var cap := max_speed_for(state, locked, running)
		var top := cap * dir.length()
		var step := cap / _accel_frames
		if speed > top:
			step = maxf(step, PlayerData.SPEED_RUN / _decel_frames)
		speed = move_toward(speed, top, step)
		vel = dir.normalized() * speed
	pos += vel / Frames.FPS
	_update_facing(dir if has_input else Vector2.ZERO)


## §9：未鎖定時面向移動方向；鎖定時面向目標（奔跑時暫時面向奔跑方向）。
func _update_facing(move_dir: Vector2) -> void:
	if locked and not running:
		var to := sim.boss.pos - pos
		if to.length_squared() > 0.01:
			facing = to.normalized()
	elif move_dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		facing = move_dir.normalized()
