class_name FeedbackData
extends RefCounted
## 打擊感表（combat-design §12、§6）。頓幀與震動時間單位是秒。
## 震動時間只有完美彈返在文件中有規定（0.1 秒），其他事件文件未定，取 0.1–0.3 秒。

const TABLE := {
	&"light_hit": {"hitstop": 0.04, "shake": 0.0, "shake_time": 0.0},
	&"finisher_hit": {"hitstop": 0.07, "shake": 2.0, "shake_time": 0.1},
	&"heavy_hit": {"hitstop": 0.10, "shake": 4.0, "shake_time": 0.15},
	&"perfect_parry": {"hitstop": 0.08, "shake": 3.0, "shake_time": 0.1},
	&"normal_block": {"hitstop": 0.0, "shake": 0.0, "shake_time": 0.0},
	&"player_stagger": {"hitstop": 0.06, "shake": 2.0, "shake_time": 0.1},
	&"player_knockdown": {"hitstop": 0.08, "shake": 5.0, "shake_time": 0.2},
	&"boss_break": {"hitstop": 0.15, "shake": 4.0, "shake_time": 0.2},
	&"execution": {"hitstop": 0.25, "shake": 6.0, "shake_time": 0.3},
}

## Boss 被打中時白閃的時間（§12）
const BOSS_FLASH_TIME := 0.06
## 玩家被打中時紅閃的時間（文件未定）
const PLAYER_FLASH_TIME := 0.12


static func hitstop_frames(event: StringName) -> int:
	return Frames.of(TABLE[event]["hitstop"])


static func shake(event: StringName) -> float:
	return TABLE[event]["shake"]


static func shake_time(event: StringName) -> float:
	return TABLE[event]["shake_time"]
