extends TestCase
## M1：Y 排序與柱子遮擋（arena.md §3）。角色走到柱子後方時，柱子變半透明；在前方時不透明。

var arena: CombatArena


func before_each() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	arena = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)


func after_each() -> void:
	arena.get_parent().remove_child(arena)
	arena.free()


func _run_views(frames: int) -> void:
	for i in frames:
		for pv in arena.pillar_views:
			pv._process(1.0 / 60.0)


func test_pillar_turns_translucent_when_player_behind() -> void:
	var pillar: Dictionary = ArenaGeometry.PILLARS[0]
	var c: Vector2 = pillar["pos"]
	arena.sim.boss.pos = Vector2(0, -150)
	arena.sim.player.pos = c + Vector2(0, -22)  # 柱子北側（後方）
	_run_views(30)
	assert_true(arena.pillar_views[0].is_translucent(), "玩家在柱子後方時柱子半透明")
	assert_true(arena.pillar_views[0].modulate.a < 0.6)


func test_pillar_stays_opaque_when_player_in_front() -> void:
	var pillar: Dictionary = ArenaGeometry.PILLARS[0]
	var c: Vector2 = pillar["pos"]
	arena.sim.boss.pos = Vector2(0, -150)
	arena.sim.player.pos = c + Vector2(0, 22)  # 柱子南側（前方）
	_run_views(30)
	assert_false(arena.pillar_views[0].is_translucent(), "玩家在柱子前方時柱子不透明")


func test_characters_and_pillars_share_y_sorted_layer() -> void:
	var world: Node2D = arena.get_node("World")
	assert_true(world.y_sort_enabled)
	for pv in arena.pillar_views:
		assert_eq(pv.get_parent(), world)
	assert_eq(arena.player_view.get_parent(), world)
	assert_eq(arena.boss_view.get_parent(), world)


func test_views_are_positioned_at_feet() -> void:
	arena.sim.player.pos = Vector2(12.4, 33.6)
	arena.player_view._process(1.0 / 60.0)
	assert_eq(arena.player_view.position, Vector2(12, 34), "腳底位置取整（Y 排序依腳底）")


func test_camera_view_matches_project_and_hud() -> void:
	# 鏡頭的畫面大小要等於專案的內部解析度，下緣安全區要蓋得住 HUD 的 Boss 名稱與血條（審查指出只拿鏡頭自己的
	# 常數去測，常數本身錯了測不出來）
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	var Hud: GDScript = load("res://scripts/view/hud.gd")
	var view := Vector2(ProjectSettings.get_setting("display/window/size/viewport_width"),
		ProjectSettings.get_setting("display/window/size/viewport_height"))
	assert_eq(Cam.HALF_VIEW * 2.0, view, "鏡頭的畫面 = 內部解析度")
	assert_eq(view, Vector2(960, 540), "arena.md §2：960×540")
	assert_true(Cam.SAFE_BOTTOM >= Hud.BOSS_AREA, "下緣安全區 %.0f 蓋得住 Boss 血條區 %.0f" % [Cam.SAFE_BOTTOM, Hud.BOSS_AREA])


func test_camera_keeps_player_inside_safe_area_everywhere() -> void:
	# 畫面 960×540、場地 1080×600（2026-09-30 鏡頭拉遠、場地放大 1.5 倍）：邊界照鏡頭的常數
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	var half: Vector2 = Cam.HALF_VIEW
	var bottom: float = half.y * 2.0 - Cam.SAFE_BOTTOM
	var side: float = Cam.SAFE_SIDE
	for px in range(-525, 526, 75):
		for py in range(-285, 286, 57):
			var p := ArenaGeometry.clamp_inside(Vector2(px, py), 8.0)
			for b in [Vector2(0, -60), Vector2(0, 255), Vector2(-495, 0), Vector2(450, -180)]:
				var c: Vector2 = Cam.target_for(p, b)
				var screen := p - c + half
				assert_true(screen.y <= bottom + 0.01, "玩家 %s 腳底在 Boss 血條之上（%s）" % [p, screen])
				assert_true(screen.y - PlayerData.HEIGHT >= 0.0, "玩家 %s 頭頂在畫面內" % p)
				assert_true(screen.x >= side - 0.01 and screen.x <= half.x * 2.0 - side + 0.01, "玩家 %s 左右在畫面內" % p)


func test_smoothed_camera_keeps_player_in_safe_area_while_running() -> void:
	# 審查 M1-4：鏡頭平滑落後時玩家也不能被 Boss 血條蓋住
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	var half: Vector2 = Cam.HALF_VIEW
	var bottom: float = half.y * 2.0 - Cam.SAFE_BOTTOM
	var side: float = Cam.SAFE_SIDE
	var sim := arena.sim
	sim.boss.pos = Vector2(0, -255)
	sim.player.pos = Vector2(0, -180)
	arena.camera.snap()
	var cam: Camera2D = arena.camera
	for dir in [Vector2.DOWN, Vector2.UP, Vector2.LEFT, Vector2.RIGHT]:
		for i in 150:
			var f := InputFrame.new()
			f.move = dir
			f.run = true
			sim.step(f)
			cam._physics_process(1.0 / 60.0)
			var screen: Vector2 = sim.player.pos - cam.get("_center") + half
			assert_true(screen.y <= bottom + 0.01 and screen.y - PlayerData.HEIGHT >= -0.01, "往 %s 第 %d 幀：%s" % [dir, i, screen])
			assert_true(screen.x >= side - 0.01 and screen.x <= half.x * 2.0 - side + 0.01, "往 %s 第 %d 幀：%s" % [dir, i, screen])
			if not (screen.y <= bottom + 0.01):
				return


func test_camera_keeps_boss_crown_on_screen_when_both_fit() -> void:
	# 2026-09-30：Boss 放大到 160 後站在北邊時王冠被切掉。兩者上下距離放得下時（主角在 Boss 下方，
	# Boss 頭頂到主角腳底 + 下緣安全區 ≤ 畫面高），王冠要在畫面內
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	var half: Vector2 = Cam.HALF_VIEW
	for bx in [-300.0, 0.0, 300.0]:
		var b := ArenaGeometry.clamp_inside(Vector2(bx, -400), VeltharisData.HURT_RADIUS)
		for dy in [60.0, 150.0, 250.0]:
			var p := ArenaGeometry.clamp_inside(b + Vector2(0, dy), 8.0)
			var c: Vector2 = Cam.target_for(p, b)
			var crown_screen := b.y - VeltharisData.HEIGHT - p.y + p.y - c.y + half.y
			assert_true(crown_screen >= 0.0, "Boss %s、玩家 %s：王冠在畫面內（%.1f）" % [b, p, crown_screen])
