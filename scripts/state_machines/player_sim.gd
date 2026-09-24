class_name PlayerSim
extends RefCounted
## 主角的狀態機（combat-design §3–§10）。

enum State { IDLE, ATTACK, CHARGE, THRUST, DODGE, BLOCK, HEAL, STAGGER, LAUNCHED, DOWN, GETUP, POSTURE_BREAK, EXECUTE, DEAD }

const STATE_NAMES := ["IDLE", "ATTACK", "CHARGE", "THRUST", "DODGE", "BLOCK", "HEAL", "STAGGER",
	"LAUNCHED", "DOWN", "GETUP", "POSTURE_BREAK", "EXECUTE", "DEAD"]

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


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


func tick(_input: InputFrame) -> void:
	pass


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start
