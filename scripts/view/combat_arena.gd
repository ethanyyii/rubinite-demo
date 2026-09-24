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
const FxView := preload("res://scripts/view/fx_view.gd")
const HitboxPreview := preload("res://scripts/view/hitbox_preview_view.gd")
const DebugDriver := preload("res://scripts/view/debug_driver.gd")
const SfxPlayer := preload("res://scripts/audio/sfx_player.gd")

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
var fx: Node2D
var sfx: Node
var pillar_views: Array[Node2D] = []
## M3：Boss 還沒有 AI，平常是訓練木樁（定時出一招，數字鍵換招）；F3 切成手動出招
var training_move := &"royal_sweep"
const TRAINING_INTERVAL := 1.5


func _ready() -> void:
	InputFrame.use_all_joypads()
	sim = CombatSim.new(randi())
	_build()
	_apply_boss_mode()


func _build() -> void:
	var floor_view := FloorView.new()
	floor_view.name = "ArenaFloor"
	add_child(floor_view)

	var preview: Node2D = HitboxPreview.new()
	preview.name = "HitboxPreview"
	preview.setup(self)
	add_child(preview)

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

	fx = FxView.new()
	fx.name = "Fx"
	fx.setup(self)
	add_child(fx)

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

	sfx = SfxPlayer.new()
	sfx.name = "Sfx"
	add_child(sfx)

	if OS.is_debug_build():
		var driver: Node = DebugDriver.new()
		driver.name = "Debug"
		driver.setup(self)
		add_child(driver)


func _physics_process(_delta: float) -> void:
	sim.step(InputFrame.from_devices())
	for e in sim.events:
		_dispatch(e)


## 事件 → 特效、音效、震動（combat-design §6、§12）
func _dispatch(e: Dictionary) -> void:
	match e["type"]:
		&"feedback":
			camera.add_shake(e["shake"], e["shake_time"])
			var pos: Vector2 = e["pos"] + Vector2(0, -24)
			match e["event"]:
				&"light_hit":
					fx.sparks(pos, Palette.PLAYER_LIGHT, 6, 90.0, 0.2)
				&"finisher_hit", &"heavy_hit":
					fx.sparks(pos, Color(0.8, 0.9, 1.0), 12, 130.0, 0.3)
		&"boss_hit":
			boss_view.flash_hit()
			sfx.play(&"hit")
		&"player_attack":
			sfx.play(&"swing_heavy" if e["stage"] == 3 else &"swing_light", 0.0, 1.0 + 0.04 * e["stage"])
		&"player_thrust":
			sfx.play(&"swing_heavy", 0.0, 0.85)
		&"charge_full":
			player_view.flash_charge()
			sfx.play(&"charge_ready")
			fx.add(&"flash_ring", {"pos": e["pos"] + Vector2(0, -20), "r0": 8.0, "r1": 26.0,
				"color": Color(0.85, 0.93, 1.0)}, 0.25)
		&"dodge":
			sfx.play(&"dodge")
		&"perfect_parry":
			# 劍與劍碰撞，接觸點爆出大量白金色火花（§6）
			var p: Vector2 = e["pos"] + Vector2(0, -22)
			fx.sparks(p, Color(1.0, 0.95, 0.7), 26, 170.0, 0.35)
			fx.sparks(p, Color(1, 1, 1), 10, 110.0, 0.2)
			fx.add(&"flash_ring", {"pos": p, "r0": 4.0, "r1": 22.0, "color": Color(1.0, 0.95, 0.75)}, 0.16)
			sfx.play(&"parry")
		&"block":
			# 幾點暗色火星（§6），加一小團被推後揚起的灰塵
			fx.sparks(e["pos"] + Vector2(0, -22), Color(0.8, 0.45, 0.2), 6, 55.0, 0.3)
			fx.sparks(sim.player.pos + Vector2(0, -2), Color(0.55, 0.5, 0.42, 0.8), 5, 25.0, 0.3)
			sfx.play(&"block")
		&"player_hit":
			player_view.flash_hurt()
			sfx.play(&"player_hurt")
			if e["effect"] != CombatTypes.HitEffect.STAGGER:
				sfx.play(&"knockdown")
		&"posture_break":
			sfx.play(&"posture_break")
		&"heal_start":
			sfx.play(&"heal")
		&"boss_swing":
			sfx.play(&"boss_swing")
		&"danger":
			sfx.play(&"danger")


## 重置戰鬥（F5；死亡後重試也走這裡）
func reset_battle() -> void:
	sim.reset(randi())
	hud.reset_trails()
	fx.clear()
	_apply_boss_mode()


## M3：訓練木樁；F3 手動出招
func _apply_boss_mode() -> void:
	if boss_manual:
		sim.boss.set_manual()
	else:
		sim.boss.set_training(training_move, TRAINING_INTERVAL)
	camera.snap()


## 除錯面板的額外行
func extra_debug_lines() -> Array[String]:
	var p := sim.player
	var lines: Array[String] = []
	lines.append("  段數 %d  緩衝 %s  閃身冷卻 %d  無敵 %s  蓄滿 %s" % [p.combo_index + 1,
		String(p.buffered_action) if p.buffered_action != &"" else "-",
		maxi(Frames.of(PlayerData.DODGE_INTERVAL) - (sim.combat_frame - p.last_dodge_start), 0),
		"是" if p.is_invulnerable() else "否", "是" if p.charge_full else "否"])
	return lines


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
		_apply_boss_mode()
	elif event.is_action_pressed(&"debug_god_mode"):
		sim.god_mode = not sim.god_mode
	elif event.is_action_pressed(&"debug_reset"):
		var god := sim.god_mode
		reset_battle()
		sim.god_mode = god
	elif event.is_action_pressed(&"debug_attack_preview"):
		attack_preview = not attack_preview
	elif event is InputEventKey and event.pressed and not event.echo and _number_key(event) >= 0:
		_on_number_key(_number_key(event))
	else:
		return
	get_viewport().set_input_as_handled()


## 數字鍵 1–9、0（= 10）；不是數字鍵回傳 -1
func _number_key(event: InputEventKey) -> int:
	var k := event.keycode
	if k >= KEY_1 and k <= KEY_9:
		return k - KEY_0
	if k == KEY_0:
		return 10
	return -1


## F3 手動模式：數字鍵指定下一招；訓練模式：數字鍵換成訓練的招式
func _on_number_key(n: int) -> void:
	var id := VeltharisData.move_for_key(sim.boss.phase, n)
	if id == &"":
		return
	if boss_manual:
		sim.boss.queue_move(id)
	else:
		training_move = id
		sim.boss.training_move = id


## 存下目前畫面（驗證證據用，plan §6）。factor 為整數倍放大，nearest 取樣。
func save_screenshot(path: String, factor: int = 2) -> Error:
	var img := get_viewport().get_texture().get_image()
	if factor > 1:
		img.resize(img.get_width() * factor, img.get_height() * factor, Image.INTERPOLATE_NEAREST)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	return img.save_png(path)


func _exit_tree() -> void:
	Engine.time_scale = 1.0
