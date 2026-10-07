extends SceneTree
## 介面美化（2026-10-06）的畫面驗證：幾種狀態各存一張全畫面（開場滿血、雙方受傷、第一管快打空、轉場回滿中、
## 第二階段、Boss 失衡），另外存 Boss 被打中閃白那一格和沒閃的那一格（並排比）。
## 需要畫面：godot --path . -s res://tests/sim/capture_ui.gd -- --out=<資料夾>

## [名字, 玩家 HP 比例, 架勢比例, 剩幾瓶, Boss HP 比例, 第幾階段, 轉場進度（-1 不在轉場）, 失衡]
const STATES := [
	["ui_start", 1.0, 1.0, 3, 1.0, 1, -1.0, false],
	["ui_hurt", 0.45, 0.22, 2, 0.78, 1, -1.0, false],
	["ui_bar1_low", 0.7, 0.8, 1, 0.53, 1, -1.0, false],
	["ui_refill", 0.7, 0.8, 1, 0.5, 1, 0.45, false],
	["ui_phase2", 0.3, 0.6, 0, 0.3, 2, -1.0, false],
	["ui_broken", 0.8, 1.0, 2, 0.66, 1, -1.0, true],
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
	DirAccess.make_dir_recursive_absolute(out)
	for i in 10:
		await physics_frame
	arena.boss_manual = true
	for s: Array in STATES:
		arena.reset_battle()
		var sim := arena.sim
		sim.boss.set_manual()
		sim.boss.phase = s[5]
		sim.boss.move = null
		sim.boss.enter_state(BossSim.State.IDLE)
		sim.player.pos = Vector2(0, 120)
		sim.boss.pos = Vector2(0, -60)
		arena.camera.snap()
		# 先讓殘影條停在受傷前，再扣血：截到「剛受傷、殘影還在」的樣子
		for i in 5:
			await physics_frame
		sim.player.hp = roundi(PlayerData.MAX_HP * s[1])
		sim.player.posture = PlayerData.MAX_POSTURE * s[2]
		sim.player.heals = s[3]
		sim.boss.hp = roundi(VeltharisData.MAX_HP * s[4])
		if s[7]:
			sim.boss.toughness = 0.0
			sim.boss.enter_state(BossSim.State.BROKEN)
		var prog: float = s[6]
		if prog >= 0.0:
			sim.boss.enter_state(BossSim.State.TRANSITION)
			sim.boss.state_start = sim.combat_frame - int(prog * Frames.of(VeltharisData.TRANSITION_TIME))
		for i in 8:
			if prog >= 0.0:
				sim.boss.state_start = sim.combat_frame - int(prog * Frames.of(VeltharisData.TRANSITION_TIME))
			await physics_frame
		await RenderingServer.frame_post_draw
		arena.get_viewport().get_texture().get_image().save_png(out.path_join("%s.png" % s[0]))
		print(s[0])
	# Boss 被打中的閃白：閃、沒閃
	arena.reset_battle()
	arena.sim.boss.set_manual()
	arena.sim.boss.enter_state(BossSim.State.IDLE)
	arena.sim.player.pos = Vector2(0, 120)
	arena.sim.boss.pos = Vector2(0, -60)
	arena.camera.snap()
	for i in 5:
		await physics_frame
	# 截圖時停住 Boss 畫面的更新（不然每格又把閃白強度設回去），直接設強度
	arena.boss_view.set_process(false)
	for pair in [["flash_new", FeedbackData.BOSS_FLASH_AMOUNT], ["flash_none", 0.0]]:
		arena.boss_view._mat.set_shader_parameter("mix_amount", pair[1])
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		arena.get_viewport().get_texture().get_image().save_png(out.path_join("%s.png" % pair[0]))
		print(pair[0])
	quit()
