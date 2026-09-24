class_name BossMoveData
extends Resource
## Boss 的一招：依序的幾擊，加上最後一擊之後的收招。

@export var id := &""
@export var display_name := ""
@export var hits: Array[BossHitData] = []
## 最後一擊判定結束後的收招秒數
@export var recovery := 1.0
## 起手期間朝玩家逼近的速度（px/s）；0 = 原地出招。方向鎖定後停止移動。
@export var startup_advance_speed := 0.0
## 逼近到這個距離（中心距）就停下
@export var advance_stop_distance := 70.0
## 懲罰技（combat-design §11.6 ★2）
@export var is_punish := false
## 騰空開始時間（秒，從出招開始算）。負數表示不會騰空。墜王之躍用。
@export var airborne_start := -1.0
## 除錯 F3 模式下對應的數字鍵（0 表示沒有）
@export var debug_key := 0


## 各擊判定開始的幀（從出招開始算）。每段間隔各自換算後相加。
func hit_start_frames() -> PackedInt32Array:
	var out := PackedInt32Array()
	var t := 0
	for h in hits:
		t += Frames.of(h.interval)
		out.append(t)
	return out


func last_hit_end_frame() -> int:
	var starts := hit_start_frames()
	return starts[starts.size() - 1] + Frames.of(hits[hits.size() - 1].active)


func total_frames() -> int:
	return last_hit_end_frame() + Frames.of(recovery)


func first_startup() -> float:
	return hits[0].interval


func last_hit() -> BossHitData:
	return hits[hits.size() - 1]
