extends SceneTree
## 主角精靈圖接進遊戲後的畫面驗證：在真正的遊戲場景裡照腳本操作主角（走、跑、四段輕攻擊、格擋與彈返、
## 蓄力與突刺、閃身、治療、受擊、死亡），每個物理幀截一張以主角為中心的小圖（含頓幀），另外存幾張全畫面。
## 需要畫面（不能 --headless）：
## godot --path . -s res://tests/sim/capture_player_sprites.gd -- --out=<資料夾> [--only=場景名]
## 之後用 tools/sprite_rig/ingame_gifs.py 把小圖接成 GIF 和總覽圖。Boss 切成手動（不出招）；受擊由腳本直接結算。

const DebugDriver := preload("res://scripts/view/debug_driver.gd")
## 以主角腳底為準的截圖範圍（遊戲畫面座標；2026-09-30 起畫面是 960×540）
const CROP := Vector2i(128, 96)
const FEET_AT := Vector2i(64, 76)


## 照時間表送出輸入的機器人。每一段：[幀數, {move, run, block, heavy, lock, tap: 動作名, every: 每幾幀按一次,
## hit: 受擊種類, from: 攻擊者相對主角的位置}]
class Scripted extends BotController:
	var arena: CombatArena
	var segments: Array = []
	var frame := 0

	func total() -> int:
		var n := 0
		for s: Array in segments:
			n += int(s[0])
		return n

	func decide(sim: CombatSim) -> InputFrame:
		var f := InputFrame.new()
		var t := frame
		frame += 1
		for s: Array in segments:
			var n: int = s[0]
			if t >= n:
				t -= n
				continue
			var o: Dictionary = s[1]
			f.move = o.get("move", Vector2.ZERO)
			f.run = o.get("run", false)
			f.block = o.get("block", false)
			f.heavy = o.get("heavy", false)
			var every: int = o.get("every", 0)
			var tap: StringName = o.get("tap", &"")
			if tap != &"" and (t == 0 or (every > 0 and t % every == 0)):
				match tap:
					&"attack":
						f.attack_pressed = true
					&"heavy":
						f.heavy_pressed = true
						f.heavy = true
					&"dodge":
						f.dodge_pressed = true
					&"heal":
						f.heal_pressed = true
					&"lock":
						f.lock_pressed = true
			if t == 0 and o.has("toughness"):
				sim.boss.toughness = o["toughness"]  # 處決場景：韌性剩一點，這一刀打到就失衡
			if t == 0 and o.has("hit"):
				_hit(sim, o["hit"], sim.player.pos + (o.get("from", Vector2(80, 0)) as Vector2))
			break
		return f

	func _hit(sim: CombatSim, kind: String, from: Vector2) -> void:
		var h: BossHitData
		match kind:
			"light":
				h = VeltharisData.move(1, &"quick_combo_3").hits[0]
			"knockdown":
				h = VeltharisData.move(1, &"oath_cleave").hits[0]
			"launch":
				h = VeltharisData.move(1, &"royal_sweep").hits[0]
		if sim.player.hp > 1:
			sim.player.hp = PlayerData.MAX_HP  # 連續受擊的場景不要被打死（死亡場景 HP 設成 1）
		var before := sim.events.size()
		sim.apply_boss_hit(h, from)
		# 結算在 step 之外，事件要自己送給畫面（閃紅、火花、震動）
		for e in sim.events.slice(before):
			arena._dispatch(e)


## 每個場景：名字、開始時主角的面向、Boss 的位置（相對主角）、時間表、要存全畫面的幀
func scenes() -> Array:
	var R := Vector2.RIGHT
	var L := Vector2.LEFT
	var D := Vector2.DOWN
	var U := Vector2.UP
	return [
		["walk_run", D, Vector2(0, -170), [[24, {}], [36, {"move": R}], [48, {"move": R, "run": true}], [30, {}],
			[30, {"move": D}], [20, {}], [30, {"move": U}], [20, {}]], [80]],
		["combo_mash", R, Vector2(-40, -170), [[8, {}], [150, {"tap": &"attack", "every": 2, "move": R}], [20, {}]], []],
		["combo_mash_down", D, Vector2(0, -170), [[8, {}], [150, {"tap": &"attack", "every": 2, "move": D}], [20, {}]], []],
		["combo_slow", R, Vector2(-40, -170), [[8, {}], [1, {"tap": &"attack", "move": R}], [20, {}], [1, {"tap": &"attack"}], [21, {}],
			[1, {"tap": &"attack"}], [22, {}], [1, {"tap": &"attack"}], [70, {}]], []],
		["guard", R, Vector2(90, 0), [[10, {}], [30, {"block": true}], [1, {"block": true, "hit": "light", "from": Vector2(40, 0)}],
			[30, {"block": true}], [25, {}], [3, {"block": true}], [1, {"block": true, "hit": "light", "from": Vector2(40, 0)}],
			[40, {"block": true}], [40, {"block": true, "move": U}], [40, {"block": true, "move": L}], [20, {}]], [45, 101]],
		["charge_thrust", R, Vector2(0, -170), [[10, {}], [1, {"tap": &"heavy", "heavy": true}], [40, {"heavy": true}],
			[40, {"heavy": true, "move": R}], [20, {"heavy": true}], [60, {}],
			[1, {"tap": &"heavy", "heavy": true}], [20, {"heavy": true}], [30, {}]], []],
		["dodge", R, Vector2(0, -170), [[10, {}], [1, {"tap": &"dodge", "move": R}], [30, {}], [1, {"tap": &"dodge"}], [30, {}],
			[1, {"tap": &"dodge", "move": D}], [30, {}]], []],
		["dodge_locked", U, Vector2(0, -120), [[4, {}], [1, {"tap": &"lock"}], [10, {}], [1, {"tap": &"dodge", "move": R}], [30, {}],
			[30, {"move": L}], [30, {"move": D}], [20, {}]], []],
		["heal", D, Vector2(0, -170), [[10, {}], [1, {"tap": &"heal"}], [30, {}], [30, {"move": L}], [30, {}]], []],
		["hits", R, Vector2(0, -170), [[10, {}], [1, {"hit": "light", "from": Vector2(-60, 0)}], [40, {}],
			[1, {"hit": "knockdown", "from": Vector2(60, 0)}], [100, {}],
			[1, {"hit": "launch", "from": Vector2(-60, 0)}], [110, {}]], [60]],
		["posture_break", R, Vector2(90, 0), [[10, {}], [40, {"block": true}], [1, {"block": true, "hit": "light", "from": Vector2(40, 0)}],
			[90, {}]], []],
		["death", R, Vector2(0, -170), [[10, {}], [1, {"hit": "knockdown", "from": Vector2(60, 0)}], [95, {}]], []],
		# 從奔跑直接接出招、格擋、蓄力、治療；從格擋移動直接出招（第 2 批決定 F、第 3 批決定 7 的試打）
		["run_into", R, Vector2(0, -170), [[10, {}], [30, {"move": R, "run": true}], [1, {"tap": &"attack", "move": R, "run": true}], [35, {}],
			[30, {"move": L, "run": true}], [20, {"block": true}], [15, {}], [30, {"move": R, "run": true}], [1, {"tap": &"heavy", "heavy": true}],
			[15, {"heavy": true}], [15, {}], [30, {"move": L, "run": true}], [1, {"tap": &"heal", "move": L, "run": true}], [75, {}],
			[30, {"block": true, "move": R}], [1, {"tap": &"attack", "block": true, "move": R}], [35, {}]], []],
		# 處決：Boss 韌性剩一點，第 1 段打到就失衡，再按攻擊處決（朝右；朝下時主角在 Boss 後面，畫剪影）
		["execute", R, Vector2(52, 0), [[10, {}], [1, {"tap": &"attack", "toughness": 0.5}], [40, {}], [1, {"tap": &"attack"}], [75, {}]], [60]],
		["execute_down", D, Vector2(0, 52), [[10, {}], [1, {"tap": &"attack", "toughness": 0.5}], [40, {}], [1, {"tap": &"attack"}], [75, {}]], [60]],
		# 主角在 Boss 正後方（北側）：Y 排序時被 Boss 擋住
		["behind_boss", D, Vector2(0, 36), [[20, {}], [20, {"tap": &"attack", "every": 2}], [20, {}], [30, {"move": L}], [20, {}]], [15, 32, 100]],
	]


func _initialize() -> void:
	var out := ""
	var only := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.get_slice("=", 1)
		elif a.begins_with("--only="):
			only = a.get_slice("=", 1)
	var scene: PackedScene = load(ProjectSettings.get_setting("application/run/main_scene"))
	var arena := scene.instantiate() as CombatArena
	root.add_child(arena)
	_run.call_deferred(arena, out, only)


func _run(arena: CombatArena, out: String, only: String) -> void:
	for i in 10:
		await physics_frame
	arena.boss_manual = true
	for sc: Array in scenes():
		if only != "" and sc[0] != only:
			continue
		await _scene(arena, out, sc)
	quit()


func _scene(arena: CombatArena, out: String, sc: Array) -> void:
	var scene_name: String = sc[0]
	var dir := out.path_join(scene_name)
	DirAccess.make_dir_recursive_absolute(dir)
	arena.reset_battle()
	var sim := arena.sim
	sim.player.pos = Vector2(0, 40)
	sim.player.facing = sc[1]
	sim.boss.pos = sim.player.pos + (sc[2] as Vector2)
	if scene_name == "death":
		sim.player.hp = 1
	if scene_name == "posture_break":
		sim.player.posture = 1.0
	var bot := Scripted.new()
	bot.arena = arena
	bot.segments = sc[3]
	arena.bot_driver = bot
	arena.camera.snap()
	# 照正常速度跑（Godot 4.7 的 time_scale 只放慢畫面的計時、不放慢物理幀，慢動作會把閃色、火花拉長）；
	# 截圖留在記憶體，每個物理幀之後都來得及畫一次。漏掉的幀（畫面來不及）在 log 裡看得出來
	var fulls: Array = sc[4]
	var last := -1
	var n := bot.total()
	var rows := []
	# 截圖先留在記憶體，場景結束才存檔：每一步都存檔會拖慢畫面，特效的計時（照真實時間）就和實際遊玩不同
	var crops: Array[Image] = []
	var names: Array[String] = []
	while bot.frame < n:
		await RenderingServer.frame_post_draw
		if sim.frame == last:
			continue
		last = sim.frame
		var img := arena.get_viewport().get_texture().get_image()
		var feet := Vector2i((arena.player_view as Node2D).get_global_transform_with_canvas().origin.round())
		var crop := Image.create(CROP.x, CROP.y, false, img.get_format())
		crop.blit_rect(img, Rect2i(feet - FEET_AT, CROP), Vector2i.ZERO)
		crops.append(crop)
		names.append(dir.path_join("f%04d.png" % bot.frame))
		var p := sim.player
		var a: PlayerAnim = arena.player_view.anim
		rows.append("%d\t%d\t%s\t%d\t%s\t%d\t%d\t%d" % [bot.frame, sim.combat_frame, p.state_name(), p.state_elapsed(), a.sheet, a.row, a.col, sim.hitstop])
		if bot.frame in fulls:
			crops.append(img)
			names.append(dir.path_join("full_%04d.png" % bot.frame))
	arena.bot_driver = null
	for i in crops.size():
		crops[i].save_png(names[i])
	var fh := FileAccess.open(dir.path_join("log.tsv"), FileAccess.WRITE)
	fh.store_string("frame\tcombat\tstate\telapsed\tsheet\trow\tcol\thitstop\n" + "\n".join(rows) + "\n")
	fh.close()
	print("%s: %d frames" % [scene_name, rows.size()])
