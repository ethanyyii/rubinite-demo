extends TestCase
## 主場景能建立、跑幾幀而不出錯。


func test_arena_scene_builds_and_steps() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	var scene: PackedScene = load("res://scenes/levels/combat_arena.tscn")
	assert_true(scene != null, "主場景讀不到")
	if scene == null:
		return
	var arena: Node2D = scene.instantiate()
	tree.root.add_child(arena)
	for i in 30:
		arena._physics_process(1.0 / 60.0)
	assert_true(arena.sim != null)
	assert_eq(arena.sim.frame, 30)
	assert_true(arena.get_node_or_null("World/Player") != null, "有主角")
	assert_true(arena.get_node_or_null("World/Boss") != null, "有 Boss")
	assert_eq(arena.get_node("World").get_child_count(), ArenaGeometry.PILLARS.size() + 2)
	tree.root.remove_child(arena)
	arena.free()


func test_sim_is_deterministic_for_same_seed() -> void:
	var a := CombatSim.new(42)
	var b := CombatSim.new(42)
	for i in 120:
		var f := InputFrame.new()
		f.move = Vector2(1, 0.5).normalized() if i < 60 else Vector2.ZERO
		a.step(f)
		var g := InputFrame.new()
		g.move = f.move
		b.step(g)
	assert_eq(a.player.pos, b.player.pos)
	assert_eq(a.boss.pos, b.boss.pos)
