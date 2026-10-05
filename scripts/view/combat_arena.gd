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
## Boss 身上的特效位置原本照 120px 的 Boss 寫；Boss 放大到 160（2026-09-30）後乘上這個倍率
const BOSS_K := VeltharisData.HEIGHT / 120.0
const DebugDriver := preload("res://scripts/view/debug_driver.gd")
const SfxPlayer := preload("res://scripts/audio/sfx_player.gd")
const ScreenFlash := preload("res://scripts/view/screen_flash.gd")

const SLOW_MOTION_SCALE := 0.25

var sim: CombatSim
## 除錯開關（plan §5）
var debug_info := false
var slow_motion := false
var boss_manual := false
var attack_preview := true
## 除錯／效能量測用：設定後由機器人代替鍵盤手把操作主角（勝利後自動再戰）。遊玩時為 null
var bot_driver: BotController = null

var world: Node2D
var player_view: Node2D
var boss_view: Node2D
var camera: Camera2D
var hud: Control
var fx: Node2D
var sfx: Node
var screen_flash: Control
var pillar_views: Array[Node2D] = []

## §14 死亡與重試、勝利演出：&"" 戰鬥中、&"death"、&"victory"
var end_state := &""
var _end_frame := 0
## 勝利：吸收餘燼的演出時間，之後顯示「再戰」（勝利或死亡後 3 秒內可以重試，plan §1）
const VICTORY_ABSORB_TIME := 2.5


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
	screen_flash = ScreenFlash.new()
	screen_flash.name = "ScreenFlash"
	hud_layer.add_child(screen_flash)

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
		_setup_perf_run()


func _physics_process(_delta: float) -> void:
	var input := InputFrame.from_devices() if bot_driver == null else bot_driver.decide(sim)
	if bot_driver != null and end_state == &"victory" and retry_prompt_visible():
		request_retry()
		return
	if end_state == &"victory" and input.attack_pressed and retry_prompt_visible():
		# 按下再戰：這個按鍵不帶進新的一場（否則重置後第一幀就會揮劍）
		request_retry()
		return
	sim.step(input)
	player_view.sim_stepped()
	boss_view.sim_stepped()
	for e in sim.events:
		_dispatch(e)
	_update_end_flow()


## §14：死亡動畫 1.5 秒 → 顯示「再戰」0.5 秒 → 重置（從死亡到可以操作 2 秒，目標 ≤ 3 秒）。
## 勝利：吸收餘燼 2.5 秒後顯示「再戰（按攻擊鍵）」，按下就重置。
func _update_end_flow() -> void:
	if end_state == &"":
		if sim.player.state == PlayerSim.State.DEAD:
			end_state = &"death"
			_end_frame = sim.frame
		elif sim.boss.state == BossSim.State.DEAD:
			end_state = &"victory"
			_end_frame = sim.frame
			_start_victory()
		return
	var elapsed := sim.frame - _end_frame
	match end_state:
		&"death":
			if elapsed >= Frames.of(PlayerData.DEATH_TIME + PlayerData.RETRY_PROMPT_TIME):
				reset_battle()
		&"victory":
			if elapsed == Frames.of(VICTORY_ABSORB_TIME * 0.8):
				player_view.ember_crack = true



func retry_prompt_visible() -> bool:
	var elapsed := sim.frame - _end_frame
	match end_state:
		&"death":
			return elapsed >= Frames.of(PlayerData.DEATH_TIME)
		&"victory":
			return elapsed >= Frames.of(VICTORY_ABSORB_TIME)
	return false


## 勝利後按下再戰：只在提示出現後有效（演出期間按的攻擊鍵不算，避免跳過勝利畫面）
func request_retry() -> void:
	if end_state == &"victory" and retry_prompt_visible():
		reset_battle()


## 死亡或勝利之後經過的物理幀（畫面用）
func end_elapsed() -> int:
	return sim.frame - _end_frame


## 勝利：Boss 的執魂（紅色餘燼）流進主角體內
func _start_victory() -> void:
	sfx.play(&"execution", -6.0, 0.7)
	fx.add(&"ember_stream", {"from": sim.boss.pos + Vector2(0, -60) * BOSS_K}, VICTORY_ABSORB_TIME)
	fx.sparks(sim.boss.pos + Vector2(0, -50) * BOSS_K, Color(0.6, 0.58, 0.55), 40, 60.0, 1.6, Vector2.UP, 0.8)


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
		&"boss_stagger":
			fx.sparks(e["pos"] + Vector2(0, -60) * BOSS_K, Color(1.0, 0.6, 0.3), 8, 80.0, 0.25)
		&"boss_transition":
			# 階段轉換：單膝跪地後起身，火焰更猛烈（boss §5）
			sfx.play(&"boss_break", 0.0, 0.8)
			fx.add(&"flash_ring", {"pos": e["pos"] + Vector2(0, -50) * BOSS_K, "r0": 20.0 * BOSS_K, "r1": 110.0 * BOSS_K, "color": Palette.BOSS_EMBER}, 0.6)
		&"boss_phase2":
			fx.sparks(e["pos"] + Vector2(0, -70) * BOSS_K, Palette.BOSS_EMBER, 30, 140.0, 0.7)
			camera.add_shake(4.0, 0.3)
		&"boss_dead":
			camera.add_shake(5.0, 0.4)
		&"player_dead":
			sfx.play(&"knockdown", 0.0, 0.7)
		&"boss_break":
			# 失衡：紅火暗下、火星散落（§12）
			sfx.play(&"boss_break")
			fx.sparks(e["pos"] + Vector2(0, -60) * BOSS_K, Palette.BOSS_EMBER, 22, 110.0, 0.5)
		&"player_execute":
			sfx.play(&"swing_heavy", 0.0, 0.8)
		&"execution_hit":
			# 處決：白色閃光（§11.4、§12）
			sfx.play(&"execution")
			screen_flash.flash(Color(1, 1, 1, 0.85), 0.35)
			fx.sparks(e["pos"] + Vector2(0, -40), Color(1, 1, 1), 30, 180.0, 0.5)
			fx.sparks(e["pos"] + Vector2(0, -40), Palette.BOSS_EMBER, 20, 120.0, 0.6)
			boss_view.flash_hit()


## 重置戰鬥（F5；死亡後重試也走這裡）
func reset_battle() -> void:
	end_state = &""
	sim.reset(randi())
	hud.reset_trails()
	fx.clear()
	if bot_driver != null:
		bot_driver.reset()
	_apply_boss_mode()


## 效能量測（plan §7）：`godot --path . -- --perf=180 [--perf-out=res://….json]` 由擬人機器人代打、量測有畫面執行的幀率，
## 結果寫成 JSON 後結束（預設 user://perf.json，不會蓋掉證據檔）。只在除錯建置有效。
func _setup_perf_run() -> void:
	var seconds := 0.0
	var out := "user://perf.json"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--perf="):
			seconds = float(a.get_slice("=", 1))
		elif a.begins_with("--perf-out="):
			out = a.get_slice("=", 1)
	if seconds <= 0.0:
		return
	bot_driver = HumanBot.new(12345)
	var rec := PerfRecorder.new()
	rec.name = "PerfRecorder"
	rec.duration = seconds
	rec.arena = self
	rec.out_path = out
	add_child(rec)


## Boss 平常由 AI 控制；F3 切成手動出招（數字鍵指定下一招，練習彈返）
func _apply_boss_mode() -> void:
	if boss_manual:
		sim.boss.set_manual()
	else:
		sim.boss.set_ai()
	camera.snap()


## 除錯面板的額外行
func extra_debug_lines() -> Array[String]:
	var p := sim.player
	var lines: Array[String] = []
	var stage := "%d" % (p.combo_index + 1) if p.state == PlayerSim.State.ATTACK else "-"
	if p.in_combo_grace():
		stage += "（寬限，下一段 %d）" % (p.next_combo_stage() + 1)
	lines.append("  段數 %s  緩衝 %s  閃身冷卻 %d  無敵 %s  蓄滿 %s" % [stage,
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


## 存下目前畫面（驗證證據用，plan §6）。factor 為整數倍放大，nearest 取樣。
func save_screenshot(path: String, factor: int = 2) -> Error:
	var img := get_viewport().get_texture().get_image()
	if factor > 1:
		img.resize(img.get_width() * factor, img.get_height() * factor, Image.INTERPOLATE_NEAREST)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	return img.save_png(path)


func _exit_tree() -> void:
	Engine.time_scale = 1.0
