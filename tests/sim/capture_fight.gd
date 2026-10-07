extends SceneTree
## 場景接進遊戲後的「打一段」錄影（2026-10-05）：擬人機器人代打、Boss 照 AI，第一階段和第二階段各錄一段全畫面
## （960×540，每個物理幀一張；先留在記憶體、錄完才存檔，特效照真實時間計時才不會被拉長）。
## 需要畫面：godot --path . -s res://tests/sim/capture_fight.gd -- --out=<資料夾> [--seconds=6]

func _initialize() -> void:
	var out := ""
	var seconds := 6.0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.get_slice("=", 1)
		elif a.begins_with("--seconds="):
			seconds = float(a.get_slice("=", 1))
	var scene: PackedScene = load(ProjectSettings.get_setting("application/run/main_scene"))
	var arena := scene.instantiate() as CombatArena
	root.add_child(arena)
	_run.call_deferred(arena, out, seconds)


func _run(arena: CombatArena, out: String, seconds: float) -> void:
	for phase in [1, 2]:
		var dir := out.path_join("fight_phase%d" % phase)
		DirAccess.make_dir_recursive_absolute(dir)
		arena.bot_driver = HumanBot.new(4242 + phase)
		arena.reset_battle()
		if phase == 2:
			arena.sim.boss.phase = 2
			arena.sim.boss.hp = roundi(VeltharisData.MAX_HP * 0.45)
		for i in 90:
			await physics_frame
		var shots: Array[Image] = []
		var n := int(seconds * 60)
		var last := -1
		while shots.size() < n:
			await RenderingServer.frame_post_draw
			if arena.sim.frame == last:
				continue
			last = arena.sim.frame
			var img := arena.get_viewport().get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			shots.append(img)
			arena.sim.player.hp = maxi(arena.sim.player.hp, 30)      # 錄影時主角不要死
		for i in shots.size():
			shots[i].save_png(dir.path_join("f%04d.png" % (i + 1)))
		print("fight phase %d: %d frames" % [phase, shots.size()])
	quit()
