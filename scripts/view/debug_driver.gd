extends Node
## 驗證用的工具（只在除錯建置加入場景，節點名稱 "Debug"）。
## godot-ai 的 game_eval 透過 get_tree().current_scene.get_node("Debug") 呼叫：
## 注入真實按鍵事件、等待模擬狀態、凍結畫面截圖。

var arena: CombatArena


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


## 凍結時間（time_scale = 0）後截圖再恢復，讓截圖停在指定的模擬幀。
func capture(path: String) -> Error:
	var ts := Engine.time_scale
	Engine.time_scale = 0.0
	await get_tree().process_frame
	await get_tree().process_frame
	var err := arena.save_screenshot(path)
	Engine.time_scale = ts
	return err


## 注入真實的鍵盤事件（走完整的輸入流程：InputMap、_unhandled_input）。
func key(keycode: Key, down: bool) -> void:
	var ev := InputEventKey.new()
	ev.keycode = keycode
	ev.physical_keycode = keycode
	ev.pressed = down
	Input.parse_input_event(ev)


## 按一下（按下、等一個物理幀、放開）。返回時按下的那一幀已經處理完。
## physics_frame 訊號在 _physics_process 之前發出，所以放開後再等一幀。
func tap(keycode: Key) -> void:
	key(keycode, true)
	await get_tree().physics_frame
	key(keycode, false)
	await get_tree().physics_frame


## 等到 cond 成立（每個物理幀檢查一次），最多 max_frames 幀
func wait_until(cond: Callable, max_frames: int = 600) -> bool:
	for i in max_frames:
		if cond.call():
			return true
		await get_tree().physics_frame
	return cond.call()
