class_name PlayerAttackData
extends Resource
## 主角的一段攻擊（combat-design §8）。時間單位是秒。

@export var id := &""
@export var startup := 0.1
@export var active := 0.08
@export var recovery := 0.25
@export var damage := 15
## 對 Boss 的削韌（combat-design §11.3）
@export var toughness := 2.0
## 判定期間前進的距離
@export var advance := 6.0
## 收招期間能否用格擋或閃身取消（§8.3）
@export var cancelable := true
## 能否讓 Boss 短僵直（§11.2：第 4 段與重擊）
@export var can_short_stagger := false
## 命中時的打擊感事件（對應 FeedbackData）
@export var feedback := &"light_hit"


func startup_frames() -> int:
	return Frames.of(startup)


func active_end_frame() -> int:
	return Frames.of(startup) + Frames.of(active)


func total_frames() -> int:
	return active_end_frame() + Frames.of(recovery)
