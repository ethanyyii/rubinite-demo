class_name BossHitData
extends Resource
## Boss 的一擊（CLAUDE.md：每一擊都是一筆資料，★ 規則的測試直接掃描這些欄位）。
## 時間單位一律是秒，執行時用 Frames.of() 換成幀。

## 類型：輕擊／重擊／不可格擋（combat-design §11.1）
@export var attack_type: CombatTypes.AttackType = CombatTypes.AttackType.HEAVY
## 第一擊：從出招開始到判定開始的起手時間。之後各擊：與前一擊判定開始的間隔。
@export var interval := 0.8
## 判定持續時間
@export var active := 0.1
@export var damage := 0
## 普通格擋時玩家扣的架勢（combat-design §6：輕擊 20、重擊 35）
@export var posture_damage := 0
## 完美彈返時 Boss 被削的韌性（combat-design §6）
@export var toughness_damage := 0
## 完美彈返後 Boss 彈開的秒數。0 表示連段中間的一擊，彈返後 Boss 繼續出招。
@export var bounce_time := 0.0
## 命中玩家的反應（combat-design §10）
@export var hit_effect: CombatTypes.HitEffect = CombatTypes.HitEffect.KNOCKDOWN

@export_group("判定形狀")
@export var shape: CombatTypes.Shape = CombatTypes.Shape.SECTOR
@export var radius := 100.0
@export var angle_deg := 150.0
@export var length := 0.0
@export var width := 0.0
@export var thickness := 0.0
## 判定期間 Boss 前進的距離（裁決突刺 LUNGE_DISTANCE，160px）
@export var lunge_distance := 0.0
## 判定開始前 step_time 秒內 Boss 沿鎖定的方向前進的距離，判定開始時已經踏完（雙斬／三斬第二刀左腳往前踏，
## TWIN_STEP_DISTANCE；2026-10-01 使用者）。判定期間位置不動，被完美彈返時彈開的動畫從砍到的位置接上
@export var step_distance := 0.0
@export var step_time := 0.0

@export_group("預兆與方向")
## 命中前幾秒鎖定方向（boss-veltharis §3：0.2 秒；墜王之躍落點 0.3 秒）
@export var lock_before := 0.2
## 延遲版：舉到最高點後停住的秒數（已包含在 interval 內）
@export var delay_hold := 0.0
## 延遲版：從本擊起手開始，到停住的時間點
@export var hold_start := 0.0
## 不可格擋：危險預兆的持續秒數（在判定開始前）
@export var danger_time := 0.0
## 動畫片段代號（boss-veltharis §8.2），佔位圖形用來決定揮劍姿勢
@export var anim := &"C1"


func is_blockable() -> bool:
	return attack_type != CombatTypes.AttackType.UNBLOCKABLE


func is_delayed() -> bool:
	return delay_hold > 0.0


func is_finisher() -> bool:
	return bounce_time > 0.0
