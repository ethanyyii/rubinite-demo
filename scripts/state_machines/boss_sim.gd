class_name BossSim
extends RefCounted
## Boss 的狀態機（combat-design §11、boss-veltharis.md）。

enum State { IDLE, WALK, ATTACK, BOUNCED, STAGGER, BROKEN, EXECUTED, RISING, TRANSITION, DEAD }

const STATE_NAMES := ["IDLE", "WALK", "ATTACK", "BOUNCED", "STAGGER", "BROKEN", "EXECUTED", "RISING",
	"TRANSITION", "DEAD"]

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


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


func tick() -> void:
	pass


## 是否有實體碰撞（騰空時沒有）
func has_body() -> bool:
	return state != State.DEAD


## 能否被鎖定／輔助瞄準
func is_targetable() -> bool:
	return state != State.DEAD


## 能否被玩家的攻擊打中
func can_be_hit() -> bool:
	return state != State.DEAD


## 被玩家的攻擊打中（combat-design §11.3：扣 HP、削韌）。
func receive_player_hit(atk: PlayerAttackData) -> void:
	hp = maxi(hp - atk.damage, 0)
	if atk.toughness > 0:
		toughness = maxf(toughness - atk.toughness, 0.0)
		last_toughness_damage = sim.combat_frame
	sim.emit(&"boss_hit", {"damage": atk.damage, "attack": atk.id, "pos": pos})


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start
