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


func test_camera_keeps_player_inside_safe_area_everywhere() -> void:
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	for px in range(-350, 351, 50):
		for py in range(-190, 191, 38):
			var p := ArenaGeometry.clamp_inside(Vector2(px, py), 8.0)
			for b in [Vector2(0, -40), Vector2(0, 170), Vector2(-330, 0), Vector2(300, -120)]:
				var c: Vector2 = Cam.target_for(p, b)
				var screen := p - c + Vector2(320, 180)
				assert_true(screen.y <= 360 - 50 + 0.01, "玩家 %s 腳底在 Boss 血條之上（%s）" % [p, screen])
				assert_true(screen.y - PlayerData.HEIGHT >= 0.0, "玩家 %s 頭頂在畫面內" % p)
				assert_true(screen.x >= 24 - 0.01 and screen.x <= 640 - 24 + 0.01, "玩家 %s 左右在畫面內" % p)


func test_smoothed_camera_keeps_player_in_safe_area_while_running() -> void:
	# 審查 M1-4：鏡頭平滑落後時玩家也不能被 Boss 血條蓋住
	var sim := arena.sim
	sim.boss.pos = Vector2(0, -170)
	sim.player.pos = Vector2(0, -120)
	arena.camera.snap()
	var cam: Camera2D = arena.camera
	for dir in [Vector2.DOWN, Vector2.UP, Vector2.LEFT, Vector2.RIGHT]:
		for i in 150:
			var f := InputFrame.new()
			f.move = dir
			f.run = true
			sim.step(f)
			cam._physics_process(1.0 / 60.0)
			var screen: Vector2 = sim.player.pos - cam.get("_center") + Vector2(320, 180)
			assert_true(screen.y <= 360 - 50 + 0.01 and screen.y - PlayerData.HEIGHT >= -0.01, "往 %s 第 %d 幀：%s" % [dir, i, screen])
			assert_true(screen.x >= 24 - 0.01 and screen.x <= 616.01, "往 %s 第 %d 幀：%s" % [dir, i, screen])
			if not (screen.y <= 310.01):
				return
