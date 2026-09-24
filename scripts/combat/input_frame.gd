class_name InputFrame
extends RefCounted
## 一個物理幀的輸入快照（combat-design §3）。
## 真人輸入（from_devices）與模擬機器人都產生這個格式，戰鬥模擬只看它。

var move := Vector2.ZERO
## 按住
var run := false
var block := false
var heavy := false
## 這一幀剛按下
var attack_pressed := false
var heavy_pressed := false
var dodge_pressed := false
var lock_pressed := false
var heal_pressed := false
var target_left_pressed := false
var target_right_pressed := false


## 在 _physics_process 中呼叫：is_action_just_pressed 以物理幀為單位。
static func from_devices() -> InputFrame:
	var f := InputFrame.new()
	f.move = Input.get_vector(&"move_left", &"move_right", &"move_up", &"move_down")
	f.run = Input.is_action_pressed(&"run")
	f.block = Input.is_action_pressed(&"block")
	f.heavy = Input.is_action_pressed(&"heavy")
	f.attack_pressed = Input.is_action_just_pressed(&"attack")
	f.heavy_pressed = Input.is_action_just_pressed(&"heavy")
	f.dodge_pressed = Input.is_action_just_pressed(&"dodge")
	f.lock_pressed = Input.is_action_just_pressed(&"lock_on")
	f.heal_pressed = Input.is_action_just_pressed(&"heal")
	f.target_left_pressed = Input.is_action_just_pressed(&"target_left")
	f.target_right_pressed = Input.is_action_just_pressed(&"target_right")
	return f


## 讓所有手把事件接受任何一支手把（device = -1）。
## project.godot 裡的手把綁定是用 godot-ai 寫入的，工具只能寫 device 0；啟動時在這裡統一改成 -1。
static func use_all_joypads() -> void:
	for action in InputMap.get_actions():
		for ev in InputMap.action_get_events(action):
			if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
				ev.device = -1


## 頓幀期間累積的按鍵，頓幀結束後一次送出（頓幀不影響輸入，CLAUDE.md 慣例）。
## other 是較晚的一幀：攻擊／重擊／閃身只保留較晚那一幀的按鍵（緩衝只記最新一次）；
## 鎖定鍵按兩次等於沒按（開關）。
func merge_presses(other: InputFrame) -> void:
	if other.attack_pressed or other.heavy_pressed or other.dodge_pressed:
		attack_pressed = other.attack_pressed
		heavy_pressed = other.heavy_pressed
		dodge_pressed = other.dodge_pressed
	lock_pressed = lock_pressed != other.lock_pressed
	heal_pressed = heal_pressed or other.heal_pressed
	target_left_pressed = target_left_pressed or other.target_left_pressed
	target_right_pressed = target_right_pressed or other.target_right_pressed


func copy_presses_to(other: InputFrame) -> void:
	other.attack_pressed = attack_pressed
	other.heavy_pressed = heavy_pressed
	other.dodge_pressed = dodge_pressed
	other.lock_pressed = lock_pressed
	other.heal_pressed = heal_pressed
	other.target_left_pressed = target_left_pressed
	other.target_right_pressed = target_right_pressed


func has_presses() -> bool:
	return attack_pressed or heavy_pressed or dodge_pressed or lock_pressed or heal_pressed \
		or target_left_pressed or target_right_pressed
