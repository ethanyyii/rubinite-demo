class_name PlayerAttackData
extends Resource
## 主角的一段攻擊（combat-design §8）。時間單位是秒。

@export var id := &""
@export var startup := 0.1
@export var active := 0.08
@export var recovery := 0.25
## 收招之後的停頓（§8.1：只有第 4 段）。期間不能出招、不能移動，可以格擋或閃身
@export var end_lag := 0.0
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


## 收招結束（停頓開始）的幀；沒有停頓時等於 total_frames()
func recovery_end_frame() -> int:
	return active_end_frame() + Frames.of(recovery)


func total_frames() -> int:
	return recovery_end_frame() + Frames.of(end_lag)
