extends SceneTree
## 競技場美術的畫面驗證（2026-10-05）：在真正的遊戲場景裡把主角、Boss 放到指定位置（場地中央、沿著邊緣一圈、
## 四根柱子的前後、鏡頭跑到最邊），第一、二階段和轉場中，各存一張全畫面。
## 需要畫面（不能 --headless）：
## godot --path . -s res://tests/sim/capture_arena.gd -- --out=<資料夾> [--only=名字的開頭]

## [名字, 主角位置, Boss 位置, 第幾階段, 轉場進度（-1：不在轉場）, 等幾幀]
func shots() -> Array:
	var out := [
		["center", Vector2(0, 120), Vector2(0, -60), 1, -1.0, 20],
		["center_p2", Vector2(0, 120), Vector2(0, -60), 2, -1.0, 90],
		["north", Vector2(-60, -280), Vector2(120, -200), 1, -1.0, 40],
		["north_p2", Vector2(-60, -280), Vector2(120, -200), 2, -1.0, 90],
		["south", Vector2(40, 285), Vector2(-60, 120), 1, -1.0, 40],
		["west", Vector2(-525, -20), Vector2(-320, 40), 1, -1.0, 40],
		["east", Vector2(525, 30), Vector2(320, -40), 1, -1.0, 40],
		["nw_corner", Vector2(-390, -200), Vector2(-150, -262), 1, -1.0, 40],
		["ne_corner", Vector2(390, -200), Vector2(150, -262), 1, -1.0, 40],
		["sw_corner", Vector2(-400, 195), Vector2(-200, 100), 1, -1.0, 40],
		["se_corner", Vector2(400, 195), Vector2(200, 100), 1, -1.0, 40],
		["pillar_behind", Vector2(-354, 136), Vector2(-100, 0), 1, -1.0, 40],
		["pillar_front", Vector2(-354, 178), Vector2(-100, 0), 1, -1.0, 40],
		["boss_north_edge", Vector2(-200, -40), Vector2(-260, -255), 1, -1.0, 40],
		["transition_0", Vector2(0, 120), Vector2(0, -60), 1, 0.05, 2],
		["transition_1", Vector2(0, 120), Vector2(0, -60), 1, 0.4, 2],
		["transition_2", Vector2(0, 120), Vector2(0, -60), 1, 0.7, 2],
		["transition_3", Vector2(0, 120), Vector2(0, -60), 1, 0.98, 2],
	]
	# 沿著場地邊緣一圈（主角貼著碰撞的邊緣）
	for i in 16:
		var a := TAU * i / 16.0
		var p := ArenaGeometry.clamp_inside(Vector2(cos(a), sin(a)) * 700.0, PlayerData.HURT_RADIUS)
		out.append(["edge_%02d" % i, p, p * 0.45, 1, -1.0, 30])
	return out


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
	DirAccess.make_dir_recursive_absolute(out)
	for i in 10:
		await physics_frame
	arena.boss_manual = true
	for s: Array in shots():
		if only != "" and not (s[0] as String).begins_with(only):
			continue
		arena.reset_battle()
		var sim := arena.sim
		sim.boss.set_manual()
		sim.boss.phase = s[3]
		sim.boss.move = null
		sim.boss.enter_state(BossSim.State.IDLE)
		sim.player.pos = s[1]
		sim.boss.pos = s[2]
		sim.player.facing = (sim.boss.pos - sim.player.pos).normalized()
		arena.boss_view.anim = BossAnim.new()
		var prog: float = s[4]
		if prog >= 0.0:
			sim.boss.enter_state(BossSim.State.TRANSITION)
			sim.boss.state_start = sim.combat_frame - int(prog * Frames.of(VeltharisData.TRANSITION_TIME))
		arena.camera.snap()
		for i in int(s[5]):
			sim.player.pos = s[1]
			if prog < 0.0:
				sim.boss.pos = s[2]
				if sim.boss.state != BossSim.State.IDLE:
					sim.boss.move = null
					sim.boss.enter_state(BossSim.State.IDLE)
			else:
				sim.boss.state_start = sim.combat_frame - int(prog * Frames.of(VeltharisData.TRANSITION_TIME))
			await physics_frame
		await RenderingServer.frame_post_draw
		var img := arena.get_viewport().get_texture().get_image()
		img.save_png(out.path_join("%s.png" % s[0]))
		print(s[0])
	quit()
