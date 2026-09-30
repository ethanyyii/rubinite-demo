class_name PlayerData
extends RefCounted
## 主角的全部戰鬥數值（combat-design.md）。調整任何數值都要記在 docs/tuning-log.md。

# §4 玩家資源
const MAX_HP := 72  # tuning-log：文件 100
const MAX_POSTURE := 100.0
const HEAL_CHARGES := 3
const HEAL_AMOUNT := 25  # tuning-log：文件 35
const HEAL_TIME := 1.17  # tuning-log：文件 0.9
const POSTURE_REGEN_DELAY := 1.0
const POSTURE_REGEN_PER_SEC := 20.0

# §5 移動（px/s）
const SPEED_WALK := 100.0
const SPEED_RUN := 160.0
const SPEED_LOCKED := 85.0
const SPEED_BLOCK := 50.0
const SPEED_CHARGE := 40.0
const SPEED_HEAL := 30.0
const ACCEL_TIME := 0.08
const DECEL_TIME := 0.06

# plan §4 佔位圖形：腳底圓半徑 8、高約 40
const HURT_RADIUS := 8.0
const HEIGHT := 40.0

# §3 輸入緩衝
const INPUT_BUFFER := 0.15

# §6 格擋與彈返
const PERFECT_WINDOW := 0.15
const REARM_TIME := 0.3
const BLOCK_ARC_DEG := 180.0
const BLOCK_PUSHBACK := 8.0
## 普通格擋被推後的位移分幾幀完成（文件未定）
const BLOCK_PUSHBACK_TIME := 0.07

# §7 閃身
const DODGE_DISTANCE := 56.0
const DODGE_TIME := 0.18
const DODGE_INVULN_START := 0.02
const DODGE_INVULN_END := 0.16
const DODGE_RECOVERY := 0.12
const DODGE_INTERVAL := 0.5

# §8.1 輕攻擊
const ATTACK_ARC_DEG := 100.0
const ATTACK_RADIUS := 40.0
## 第 1–3 段判定結束後多久可以用格擋或閃身取消（§8.3）
const CANCEL_DELAY := 0.05
## 第 1–3 段收招結束後，這段時間內按攻擊仍接下一段（§8.1，2026-09-29 新增；見 tuning-log）
const COMBO_GRACE := 0.2
## 連按時相鄰兩段的判定開始至少相隔這麼久：四刀的節奏一樣（§8.1，2026-09-29 第二次修改；見 tuning-log）。
## 最早接段的幀由它推算（chain_frame），不早於判定結束
const COMBO_INTERVAL := 0.25
## 第 4 段收招之後的停頓：不能出招、不能移動，可以格擋或閃身（§8.1、§8.3，2026-09-29 新增；見 tuning-log）
const FINISHER_END_LAG := 0.2

# §8.2 蓄力重擊
const CHARGE_TIME := 0.9
const THRUST_DISTANCE := 72.0
const THRUST_TIME := 0.2
## 突刺判定：從腳底往前的劍長與寬度（文件未定，取與輕攻擊相同的 40px 攻擊距離）
const THRUST_REACH := 40.0
const THRUST_WIDTH := 16.0

# §9 鎖定
## 2026-09-30 畫面拉遠到 960×540、場地放大 1.5 倍：鎖定距離 ×1.5（原 320、420），畫面上看得到的 Boss 鎖得到
const LOCK_ACQUIRE_RANGE := 480.0
const LOCK_BREAK_RANGE := 630.0
const AIM_ASSIST_ARC_DEG := 60.0
const AIM_ASSIST_RANGE := 80.0

# §10 受擊與懲罰
const STAGGER_TIME := 0.35
const STAGGER_KNOCKBACK := 12.0
const KNOCKDOWN_KNOCKBACK := 24.0
const KNOCKDOWN_DOWN := 0.8
const LAUNCH_DISTANCE := 64.0
const LAUNCH_TIME := 0.35
const LAUNCH_DOWN := 0.6
const GETUP_TIME := 0.5
const POSTURE_BREAK_TIME := 1.2
const DOWN_INVULN_AFTER_GETUP := 0.3
## 踉蹌與倒地的擊退位移分幾秒完成（文件未定）
const KNOCKBACK_TIME := 0.1

# §11.4 處決
const EXECUTE_RANGE := 48.0
const EXECUTE_TIME := 1.0
## 處決突刺命中的時間點（文件未定：突刺＋頓幀＋閃光）
const EXECUTE_HIT_TIME := 0.2

# §14 死亡與重試
const DEATH_TIME := 1.5
const RETRY_PROMPT_TIME := 0.5

static var _light: Array[PlayerAttackData] = []
static var _heavy: PlayerAttackData


## §8.1 輕攻擊四段（依 tuning-log 調整：傷害 15/15/15/25 → 11/11/11/18；削韌 2/2/2/6 → 1.4/1.4/1.4/4.2；
## 第 4 段起手 0.18 → 0.17 → 0.10，2026-09-29 第二、三次修改）
static func light_attacks() -> Array[PlayerAttackData]:
	if _light.is_empty():
		_light = [
			_atk(&"light_1", 0.10, 0.08, 0.25, 11, 1.4, 6.0, true, false, &"light_hit"),
			_atk(&"light_2", 0.10, 0.08, 0.25, 11, 1.4, 6.0, true, false, &"light_hit"),
			_atk(&"light_3", 0.12, 0.08, 0.28, 11, 1.4, 6.0, true, false, &"light_hit"),
			_atk(&"light_4", 0.10, 0.10, 0.45, 18, 4.2, 14.0, false, true, &"finisher_hit", FINISHER_END_LAG),
		]
	return _light


## 最後一段（第 4 段）的索引
static func last_light_stage() -> int:
	return light_attacks().size() - 1


## 第 stage 段（0 起算）最早在第幾幀可以接下一段：讓兩段的判定開始相隔 COMBO_INTERVAL，
## 但不早於這一段判定結束（§8.1）。最後一段不能接，回傳 -1
static func chain_frame(stage: int) -> int:
	if stage >= last_light_stage():
		return -1
	var a := light_attacks()[stage]
	var b := light_attacks()[stage + 1]
	return maxi(a.active_end_frame(), a.startup_frames() + Frames.of(COMBO_INTERVAL) - b.startup_frames())


## §8.2 蓄力重擊的突刺（起手 = 0：蓄力本身就是起手；依 tuning-log：傷害 60 → 42、削韌 15 → 10.5）
static func heavy_thrust() -> PlayerAttackData:
	if _heavy == null:
		_heavy = _atk(&"heavy", 0.0, THRUST_TIME, 0.5, 42, 10.5, THRUST_DISTANCE, false, true, &"heavy_hit")
	return _heavy


static func _atk(id: StringName, startup: float, active: float, recovery: float, damage: int,
		toughness: float, advance: float, cancelable: bool, stagger: bool, feedback: StringName,
		end_lag := 0.0) -> PlayerAttackData:
	var a := PlayerAttackData.new()
	a.id = id
	a.startup = startup
	a.active = active
	a.recovery = recovery
	a.end_lag = end_lag
	a.damage = damage
	a.toughness = toughness
	a.advance = advance
	a.cancelable = cancelable
	a.can_short_stagger = stagger
	a.feedback = feedback
	return a
