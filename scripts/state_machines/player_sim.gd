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

## §5：加速 5 幀、減速 4 幀
var _accel_frames := Frames.of(PlayerData.ACCEL_TIME)
var _decel_frames := Frames.of(PlayerData.DECEL_TIME)
## 開始減速時的速度除以減速幀數：無論從多快開始，都在 4 幀內停下
var _decel_step := 0.0


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


func tick(input: InputFrame) -> void:
	if state in LOCOMOTION_STATES:
		_tick_locomotion(input)


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
	_update_facing(dir if has_input else Vector2.ZERO)
	pos += vel / Frames.FPS


## §9：未鎖定時面向移動方向；鎖定時面向目標（奔跑時暫時面向奔跑方向）。
func _update_facing(move_dir: Vector2) -> void:
	if locked and not running:
		var to := sim.boss.pos - pos
		if to.length_squared() > 0.01:
			facing = to.normalized()
	elif move_dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		facing = move_dir.normalized()
