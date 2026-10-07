extends SceneTree
## 場景裡會動的東西（2026-10-06）：錄幾段全畫面（每個物理幀一張，先留在記憶體、錄完才存檔），看光斑晃動、
## 葉子飄落、蛾、螢火蟲、植物擺動、火盆的煙；轉場那段看烏鴉飛走、旗子燒起來、火盆點燃。
## 需要畫面：godot --path . -s res://tests/sim/capture_ambient.gd -- --out=<資料夾>

## [名字, 主角位置, Boss 位置, 第幾階段, 轉場（true：錄影一開始 Boss 進入轉場）, 秒數, （選用）主角走到哪裡]
const SCENES := [
	["ambient_center", Vector2(0, 120), Vector2(0, -60), 1, false, 5.0],
	["ambient_crows", Vector2(-250, -150), Vector2(150, -150), 1, false, 4.0, Vector2(-395, -180)],
	["ambient_nw", Vector2(-390, -200), Vector2(-150, -262), 1, false, 4.0],
	["ambient_transition", Vector2(0, -200), Vector2(0, 40), 1, true, 4.0],
	["ambient_p2_se", Vector2(400, 195), Vector2(200, 100), 2, false, 3.0],
]


func _initialize() -> void:
	var out := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.get_slice("=", 1)
	var scene: PackedScene = load(ProjectSettings.get_setting("application/run/main_scene"))
	var arena := scene.instantiate() as CombatArena
	root.add_child(arena)
	_run.call_deferred(arena, out)


func _run(arena: CombatArena, out: String) -> void:
	for i in 10:
		await physics_frame
	arena.boss_manual = true
	for s: Array in SCENES:
		var dir := out.path_join(s[0])
		DirAccess.make_dir_recursive_absolute(dir)
		arena.reset_battle()
		var sim := arena.sim
		sim.boss.set_manual()
		sim.boss.phase = s[3]
		sim.boss.move = null
		sim.boss.enter_state(BossSim.State.IDLE)
		for i in 30:
			sim.player.pos = s[1]
			sim.boss.pos = s[2]
			sim.player.facing = (sim.boss.pos - sim.player.pos).normalized()
			arena.camera.snap()
			await physics_frame
		if s[4]:
			sim.boss.enter_state(BossSim.State.TRANSITION)
		var shots: Array[Image] = []
		var n := int(float(s[5]) * 60)
		var last := -1
		while shots.size() < n:
			await RenderingServer.frame_post_draw
			sim.player.pos = s[1] if s.size() < 7 else (s[1] as Vector2).lerp(s[6], minf(1.0, shots.size() / (n * 0.6)))
			sim.boss.pos = s[2]
			if not s[4] and sim.boss.state != BossSim.State.IDLE:
				sim.boss.move = null
				sim.boss.enter_state(BossSim.State.IDLE)
			arena.camera.snap()
			if sim.frame == last:
				continue
			last = sim.frame
			var img := arena.get_viewport().get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			shots.append(img)
		for i in shots.size():
			shots[i].save_png(dir.path_join("f%04d.png" % (i + 1)))
		print("%s: %d frames" % [s[0], shots.size()])
	quit()
