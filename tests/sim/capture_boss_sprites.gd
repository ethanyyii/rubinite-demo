extends SceneTree
## Boss 精靈圖接進遊戲後的畫面驗證（2026-10-05）：在真正的遊戲場景裡讓 Boss 照腳本動作（站著、走、每一招、
## 從走路出招、被完美彈返、出招中失衡（跪下、跪著喘、自己站起來）、收招中短僵直、出招中死亡、被處決與起身、
## 階段轉場），每個物理幀截一張以 Boss 為中心的圖（含頓幀），另外存幾張全畫面。
## 需要畫面（不能 --headless）：
## godot --path . -s res://tests/sim/capture_boss_sprites.gd -- --out=<資料夾> [--only=場景名]
## 之後用 python3 tools/sprite_rig/ingame_preview.py <資料夾> docs/art-preview/boss/ingame 接成影片（log.tsv 的欄位
## 和主角的一樣：sheet＝這一幀畫的段名、row、col）。Boss 切成手動；被彈開、失衡、死亡由腳本直接結算。

## 以 Boss 腳底為準的截圖範圍（遊戲畫面座標，畫面 960×540）
const CROP := Vector2i(400, 300)
const FEET_AT := Vector2i(200, 250)

## 每個場景：[名字, 第幾階段, Boss 相對主角的位置, 時間表 [[幀數, {...}], ...], 要存全畫面的幀]
## 時間表的動作（那一段的第一幀做）：move: 出哪一招（招式 id）；engage: AI 出這一招（打不到先走過去，2026-10-05）；
## walk: 喘息走幾幀；player: 主角移到 Boss 的哪裡；
## parry: 等判定開始時完美彈返；break: 韌性削光；die: 打死；stagger: 收招中短僵直；hp_half: HP 降到一半（轉場）；
## execute: 主角處決（按攻擊）
func scenes() -> Array:
	return [
		["stand_walk", 1, Vector2(0, -200), [[30, {}], [1, {"walk": 150}], [150, {}], [1, {"player": Vector2(0, 260)}],
			[60, {}], [1, {"walk": 120, "player": Vector2(0, 110)}], [120, {}], [60, {}]], [20, 120]],
		["sweep", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"royal_sweep"}], [130, {}]], [58]],
		["twin", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"twin_slash"}], [180, {}]], []],
		["quick2", 1, Vector2(-120, 0), [[10, {}], [1, {"move": &"quick_combo_2"}], [130, {}]], []],
		["quick3", 1, Vector2(-120, 0), [[10, {}], [1, {"move": &"quick_combo_3"}], [180, {}]], []],
		["cleave", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"oath_cleave"}], [150, {}]], []],
		["cleave_delayed", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"oath_cleave_delayed"}], [185, {}]], []],
		["thrust", 1, Vector2(-200, 0), [[10, {}], [1, {"move": &"judgment_thrust"}], [110, {}]], [44]],
		["impact", 1, Vector2(0, -150), [[10, {}], [1, {"move": &"ash_impact"}], [175, {}]], [30]],
		["walk_into_sweep", 1, Vector2(0, -260), [[10, {}], [1, {"walk": 150}], [70, {}], [1, {"move": &"royal_sweep"}], [130, {}]], []],
		["sweep_parried", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"royal_sweep", "parry": true}], [140, {}]], []],
		["sweep_broken", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"royal_sweep"}], [30, {}], [1, {"break": true}],
			[260, {}], [1, {"walk": 100}], [100, {}]], [80]],
		["engage_sweep", 1, Vector2(0, -210), [[10, {}], [1, {"engage": &"royal_sweep"}], [200, {}]], []],
		["engage_cleave", 1, Vector2(0, -285), [[10, {}], [1, {"engage": &"oath_cleave"}], [200, {}]], []],
		["short_breather", 2, Vector2(0, -120), [[10, {}], [1, {"move": &"royal_sweep"}], [102, {}], [1, {"walk": 24}],
			[24, {}], [1, {"move": &"quick_combo_2"}], [120, {}]], []],
		["sweep_staggered", 1, Vector2(0, -120), [[10, {}], [1, {"move": &"royal_sweep"}], [75, {}], [1, {"stagger": true}],
			[60, {}]], []],
		["thrust_dies", 1, Vector2(-200, 0), [[10, {}], [1, {"move": &"judgment_thrust"}], [25, {}], [1, {"die": true}], [200, {}]], []],
		["executed", 1, Vector2(0, -60), [[10, {}], [1, {"break": true}], [40, {}], [1, {"execute": true}], [140, {}]], [60]],
		["transition", 1, Vector2(0, -150), [[10, {}], [1, {"hp_half": true}], [110, {}]], [50]],
		["triple", 2, Vector2(0, -120), [[10, {}], [1, {"move": &"triple_slash"}], [240, {}]], []],
		["double_impact", 2, Vector2(0, -150), [[10, {}], [1, {"move": &"double_impact"}], [205, {}]], []],
		["spin", 2, Vector2(-110, 0), [[10, {}], [1, {"move": &"ash_spin"}], [150, {}]], [60]],
		["spin_broken_turning", 2, Vector2(-110, 0), [[10, {}], [1, {"move": &"ash_spin"}], [60, {}], [1, {"break": true}], [120, {}]], []],
		["leap", 2, Vector2(0, -260), [[10, {}], [1, {"move": &"kings_leap"}], [170, {}]], [70]],
		["leap_broken_landed", 2, Vector2(0, -260), [[10, {}], [1, {"move": &"kings_leap"}], [100, {}], [1, {"break": true}], [120, {}]], []],
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


class Idle extends BotController:
	var press_attack_at := -1
	var frame := 0

	func decide(_sim: CombatSim) -> InputFrame:
		var f := InputFrame.new()
		if frame == press_attack_at:
			f.attack_pressed = true
		frame += 1
		return f


func _scene(arena: CombatArena, out: String, sc: Array) -> void:
	var scene_name: String = sc[0]
	var dir := out.path_join(scene_name)
	DirAccess.make_dir_recursive_absolute(dir)
	arena.reset_battle()
	var sim := arena.sim
	sim.boss.set_manual()
	sim.boss.phase = sc[1]
	sim.player.pos = Vector2(0, 60)
	sim.boss.pos = sim.player.pos + (sc[2] as Vector2)
	sim.player.hp = PlayerData.MAX_HP
	# 從站著開始（重設戰鬥時 Boss 會先喘息走路）
	sim.boss.move = null
	sim.boss.enter_state(BossSim.State.IDLE)
	arena.boss_view.anim = BossAnim.new()
	arena.boss_view.anim.update(sim.boss)
	var bot := Idle.new()
	arena.bot_driver = bot
	arena.camera.snap()
	var segs: Array = sc[3]
	var n := 0
	for s: Array in segs:
		n += int(s[0])
	var fulls: Array = sc[4]
	var crops: Array[Image] = []
	var names: Array[String] = []
	var rows := []
	var last := -1
	var parry_pending := false
	var t := 0
	while t < n:
		# 這一幀的動作（每段的第一幀）
		var acc := 0
		for s: Array in segs:
			if t == acc:
				_act(arena, s[1], bot)
				if (s[1] as Dictionary).get("parry", false):
					parry_pending = true
			acc += int(s[0])
		if parry_pending and sim.boss.state == BossSim.State.ATTACK and sim.boss.current_hit_index() >= 0 \
				and sim.boss.state_elapsed() == sim.boss.hit_start_frame(sim.boss.current_hit_index()) \
				and sim.boss.current_hit_index() == sim.boss.move.hits.size() - 1:
			sim.player.hp = PlayerData.MAX_HP
			sim.boss.on_parried(sim.boss.move.hits[-1])
			sim.feedback(&"perfect_parry", sim.boss.pos)
			parry_pending = false
		await RenderingServer.frame_post_draw
		if sim.frame == last:
			continue
		last = sim.frame
		t += 1
		var img := arena.get_viewport().get_texture().get_image()
		var feet := Vector2i((arena.boss_view as Node2D).get_global_transform_with_canvas().origin.round())
		var crop := Image.create(CROP.x, CROP.y, false, img.get_format())
		crop.blit_rect(img, Rect2i(feet - FEET_AT, CROP), Vector2i.ZERO)
		crops.append(crop)
		names.append(dir.path_join("f%04d.png" % t))
		var b := sim.boss
		var a: BossAnim = arena.boss_view.anim
		rows.append("%d\t%d\t%s\t%d\t%s\t%s\t%d\t%d" % [t, sim.combat_frame, b.state_name(), b.state_elapsed(), a.clip, a.row, a.col, sim.hitstop])
		if t in fulls:
			crops.append(img)
			names.append(dir.path_join("full_%04d.png" % t))
		sim.player.hp = PlayerData.MAX_HP     # 主角不要被打死（只看 Boss）
	arena.bot_driver = null
	for i in crops.size():
		crops[i].save_png(names[i])
	var fh := FileAccess.open(dir.path_join("log.tsv"), FileAccess.WRITE)
	fh.store_string("frame\tcombat\tstate\telapsed\tsheet\trow\tcol\thitstop\n" + "\n".join(rows) + "\n")
	fh.close()
	print("%s: %d frames" % [scene_name, rows.size()])


func _act(arena: CombatArena, o: Dictionary, bot: Idle) -> void:
	var sim := arena.sim
	var b := sim.boss
	if o.has("player"):
		sim.player.pos = b.pos + (o["player"] as Vector2)
	if o.has("walk"):
		b.start_breather(int(o["walk"]))
	if o.has("move"):
		b.move = null
		b.start_move(VeltharisData.move(b.phase, o["move"]))
	if o.has("engage"):
		b.move = null
		b.engage(VeltharisData.move(b.phase, o["engage"]))
	if o.get("break", false):
		b._lose_toughness(9999.0)
	if o.get("die", false):
		b.hp = 0
		b._die()
	if o.get("stagger", false):
		b.move = null
		b.last_short_stagger = -9999
		b.enter_state(BossSim.State.STAGGER)
	if o.get("hp_half", false):
		b.hp = roundi(VeltharisData.MAX_HP * VeltharisData.PHASE2_HP_RATIO) - 1
	if o.get("execute", false):
		sim.player.pos = b.pos + Vector2(0, 40)
		bot.press_attack_at = bot.frame
