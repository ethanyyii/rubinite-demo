extends TestCase
## 輸入對應必須與 combat-design §3 一致（鍵盤＋Xbox 手把）。

## 動作 → [鍵盤按鍵, 手把事件]。手把事件："b<按鈕>" 或 "a<軸>:<方向>"
const EXPECTED := {
	&"move_left": [KEY_A, "a0:-1"],
	&"move_right": [KEY_D, "a0:1"],
	&"move_up": [KEY_W, "a1:-1"],
	&"move_down": [KEY_S, "a1:1"],
	&"attack": [KEY_J, "b%d" % JOY_BUTTON_X],
	&"heavy": [KEY_U, "b%d" % JOY_BUTTON_Y],
	&"block": [KEY_K, "b%d" % JOY_BUTTON_LEFT_SHOULDER],
	&"dodge": [KEY_SPACE, "b%d" % JOY_BUTTON_A],
	&"run": [KEY_SHIFT, "b%d" % JOY_BUTTON_RIGHT_SHOULDER],
	&"lock_on": [KEY_TAB, "b%d" % JOY_BUTTON_RIGHT_STICK],
	&"target_left": [KEY_Q, "a%d:-1" % JOY_AXIS_RIGHT_X],
	&"target_right": [KEY_E, "a%d:1" % JOY_AXIS_RIGHT_X],
	&"heal": [KEY_R, "b%d" % JOY_BUTTON_B],
}

## plan §5 除錯鍵
const DEBUG := {
	&"debug_info": KEY_F1,
	&"debug_slowmo": KEY_F2,
	&"debug_boss_manual": KEY_F3,
	&"debug_god_mode": KEY_F4,
	&"debug_reset": KEY_F5,
}


func test_gameplay_actions_match_doc() -> void:
	for action: StringName in EXPECTED:
		assert_true(InputMap.has_action(action), "缺少動作 %s" % action)
		if not InputMap.has_action(action):
			continue
		var keys := []
		var pads := []
		for ev in InputMap.action_get_events(action):
			if ev is InputEventKey:
				var k: InputEventKey = ev
				keys.append(k.keycode if k.keycode != KEY_NONE else k.physical_keycode)
			elif ev is InputEventJoypadButton:
				pads.append("b%d" % (ev as InputEventJoypadButton).button_index)
			elif ev is InputEventJoypadMotion:
				var m: InputEventJoypadMotion = ev
				pads.append("a%d:%d" % [m.axis, signi(roundi(m.axis_value))])
		assert_eq(keys, [EXPECTED[action][0]], "%s 的鍵盤按鍵" % action)
		assert_eq(pads, [EXPECTED[action][1]], "%s 的手把按鍵" % action)


func test_debug_keys_match_plan() -> void:
	for action: StringName in DEBUG:
		assert_true(InputMap.has_action(action), "缺少除錯動作 %s" % action)
		if not InputMap.has_action(action):
			continue
		var ev: InputEventKey = InputMap.action_get_events(action)[0]
		assert_eq(ev.keycode, DEBUG[action], "%s" % action)


func test_move_actions_have_small_deadzone() -> void:
	for action: StringName in [&"move_left", &"move_right", &"move_up", &"move_down"]:
		assert_near(InputMap.action_get_deadzone(action), 0.2, 0.001)


func test_joypad_events_accept_any_device_after_setup() -> void:
	InputFrame.use_all_joypads()
	for action in InputMap.get_actions():
		for ev in InputMap.action_get_events(action):
			if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
				assert_eq(ev.device, -1, "%s 的手把事件應接受任何手把" % action)
