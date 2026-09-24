class_name CombatArena
extends Node2D
## 競技場主場景：持有 CombatSim，每個物理幀送入輸入並把事件分派給畫面、鏡頭與音效。
## 戰鬥判定全部在 CombatSim；這裡只負責呈現與除錯工具（plan §5）。

const FloorView := preload("res://scripts/view/arena_floor_view.gd")
const PillarView := preload("res://scripts/view/pillar_view.gd")
const PlayerView := preload("res://scripts/view/player_view.gd")
const BossView := preload("res://scripts/view/boss_view.gd")
const CameraView := preload("res://scripts/view/combat_camera.gd")
const HudView := preload("res://scripts/view/hud.gd")
const DebugWorldView := preload("res://scripts/view/debug_world_view.gd")
const DebugOverlay := preload("res://scripts/view/debug_overlay.gd")

const SLOW_MOTION_SCALE := 0.25

var sim: CombatSim
## 除錯開關（plan §5）
var debug_info := false
var slow_motion := false
var boss_manual := false
var attack_preview := true

var world: Node2D
var player_view: Node2D
var boss_view: Node2D
var camera: Camera2D
var hud: Control
var pillar_views: Array[Node2D] = []


func _ready() -> void:
	InputFrame.use_all_joypads()
	sim = CombatSim.new(randi())
	_build()


func _build() -> void:
	var floor_view := FloorView.new()
	floor_view.name = "ArenaFloor"
	add_child(floor_view)

	world = Node2D.new()
	world.name = "World"
	world.y_sort_enabled = true
	add_child(world)

	for pillar: Dictionary in ArenaGeometry.PILLARS:
		var pv: Node2D = PillarView.new()
		pv.name = "Pillar%d" % pillar_views.size()
		pv.setup(pillar, self)
		world.add_child(pv)
		pillar_views.append(pv)

	boss_view = BossView.new()
	boss_view.name = "Boss"
	boss_view.setup(self)
	world.add_child(boss_view)

	player_view = PlayerView.new()
	player_view.name = "Player"
	player_view.setup(self)
	world.add_child(player_view)

	var debug_world: Node2D = DebugWorldView.new()
	debug_world.name = "DebugWorld"
	debug_world.setup(self)
	add_child(debug_world)

	camera = CameraView.new()
	camera.name = "Camera"
	add_child(camera)
	camera.setup(self)
	camera.make_current()

	var hud_layer := CanvasLayer.new()
	hud_layer.name = "HudLayer"
	hud_layer.layer = 10
	add_child(hud_layer)
	hud = HudView.new()
	hud.name = "Hud"
	hud_layer.add_child(hud)
	hud.setup(self)

	var debug_layer := CanvasLayer.new()
	debug_layer.name = "DebugLayer"
	debug_layer.layer = 20
	add_child(debug_layer)
	var overlay: Control = DebugOverlay.new()
	overlay.name = "DebugOverlay"
	debug_layer.add_child(overlay)
	overlay.setup(self)


func _physics_process(_delta: float) -> void:
	sim.step(InputFrame.from_devices())
	for e in sim.events:
		_dispatch(e)


func _dispatch(e: Dictionary) -> void:
	match e["type"]:
		&"feedback":
			camera.add_shake(e["shake"], e["shake_time"])


## 重置戰鬥（F5；死亡後重試也走這裡）
func reset_battle() -> void:
	sim.reset(randi())
	hud.reset_trails()
	camera.snap()


## 除錯面板的額外行（之後的里程碑擴充）
func extra_debug_lines() -> Array[String]:
	return []


func _unhandled_input(event: InputEvent) -> void:
	if not OS.is_debug_build():
		return
	if event.is_action_pressed(&"debug_info"):
		debug_info = not debug_info
	elif event.is_action_pressed(&"debug_slowmo"):
		slow_motion = not slow_motion
		Engine.time_scale = SLOW_MOTION_SCALE if slow_motion else 1.0
	elif event.is_action_pressed(&"debug_boss_manual"):
		boss_manual = not boss_manual
	elif event.is_action_pressed(&"debug_god_mode"):
		sim.god_mode = not sim.god_mode
	elif event.is_action_pressed(&"debug_reset"):
		var god := sim.god_mode
		reset_battle()
		sim.god_mode = god
	elif event.is_action_pressed(&"debug_attack_preview"):
		attack_preview = not attack_preview
	else:
		return
	get_viewport().set_input_as_handled()


## 存下目前畫面（驗證證據用，plan §6）。factor 為整數倍放大，nearest 取樣。
func save_screenshot(path: String, factor: int = 2) -> Error:
	var img := get_viewport().get_texture().get_image()
	if factor > 1:
		img.resize(img.get_width() * factor, img.get_height() * factor, Image.INTERPOLATE_NEAREST)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	return img.save_png(path)


func _exit_tree() -> void:
	Engine.time_scale = 1.0
