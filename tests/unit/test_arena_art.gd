extends TestCase
## 競技場正式美術（2026-10-05，tools/arena_art/ 產生 ArenaLayout）：美術不改玩法——
## 碰撞（場地橢圓、柱子）不變；會和角色排序的東西全在場地外；地面圖蓋滿鏡頭看得到的範圍；柱子的圖照柱子的順序。
## 2026-10-06（使用者）：畫面上不放任何場景的東西（拿掉四角的枝葉）；加料都在場景裡：植物隨風擺、火盆第二階段點燃。


func _ell(p: Vector2) -> float:
	var h := ArenaGeometry.HALF_SIZE
	return sqrt((p.x / h.x) * (p.x / h.x) + (p.y / h.y) * (p.y / h.y))


func test_collision_is_unchanged() -> void:
	# arena.md §2、使用者 2026-10-05：場地範圍、四根柱子的位置、出生點都不能動
	assert_eq(ArenaGeometry.HALF_SIZE, Vector2(540, 300))
	var want := [Vector2(-354, 156), Vector2(354, 156), Vector2(-393, -144), Vector2(393, -144)]
	assert_eq(ArenaGeometry.PILLARS.size(), 4)
	for i in 4:
		assert_eq(ArenaGeometry.PILLARS[i]["pos"], want[i], "柱子 %d 的位置" % i)
		assert_near(ArenaGeometry.PILLARS[i]["radius"], 16.0, 0.001)
	assert_eq(ArenaGeometry.PLAYER_SPAWN, Vector2(0, 165))
	assert_eq(ArenaGeometry.BOSS_SPAWN, Vector2(0, -60))


func test_standing_pieces_are_outside_the_court() -> void:
	# 和角色排序的碎石、矮牆、斷劍、灌木都在場地（碰撞的橢圓）外面，不擋在戰鬥區裡
	for p: Dictionary in ArenaLayout.PROPS:
		var pos: Vector2 = p["pos"]
		assert_true(_ell(pos) >= 1.05, "%s 在 %s：橢圓半徑 %.2f" % [p["kind"], pos, _ell(pos)])
		# 南邊只放矮的（膝蓋高）：主角站在南邊緣時，它們蓋不到他
		if pos.y > 250.0 and absf(pos.x) < 380.0:
			assert_true(float(p["top"]) <= 16.0, "南邊的 %s 只有膝蓋高（16px 以內，含描邊）：%d px" % [p["kind"], int(p["top"])])


func test_floor_covers_what_the_camera_shows() -> void:
	var Cam: GDScript = load("res://scripts/view/combat_camera.gd")
	var half: Vector2 = Cam.HALF_VIEW
	var tex: Texture2D = load(ArenaLayout.FLOOR)
	var r := Rect2(ArenaLayout.FLOOR_ORIGIN, tex.get_size())
	var shake := 8.0
	for c in [Cam.LIMIT_MIN, Cam.LIMIT_MAX, Vector2(Cam.LIMIT_MIN.x, Cam.LIMIT_MAX.y), Vector2(Cam.LIMIT_MAX.x, Cam.LIMIT_MIN.y)]:
		var view := Rect2(c - half - Vector2(shake, shake), half * 2.0 + Vector2(shake, shake) * 2.0)
		assert_true(r.encloses(view), "鏡頭中心 %s：畫面 %s 在地面圖 %s 裡" % [c, view, r])


func test_pillars_have_their_art() -> void:
	assert_eq(ArenaLayout.PILLARS.size(), ArenaGeometry.PILLARS.size())
	for a: Dictionary in ArenaLayout.PILLARS:
		var tex: Texture2D = load(a["texture"])
		assert_true(tex != null, a["texture"])


func test_scene_follows_the_bosss_phase() -> void:
	# 第二階段場景變暗變紅、旗子燒起來（2026-10-05 使用者同意）：轉場期間 0→1，之後 1
	var tree := Engine.get_main_loop() as SceneTree
	var arena: CombatArena = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)
	var fv: Node = arena.get_node("ArenaFloor")
	assert_near(fv.scene_phase(), 0.0, 0.001, "第一階段")
	arena.sim.boss.enter_state(BossSim.State.TRANSITION)
	arena.sim.boss.state_start = arena.sim.combat_frame - int(Frames.of(VeltharisData.TRANSITION_TIME) / 2.0)
	assert_near(fv.scene_phase(), 0.5, 0.02, "轉場一半")
	arena.sim.boss.phase = 2
	arena.sim.boss.enter_state(BossSim.State.IDLE)
	assert_near(fv.scene_phase(), 1.0, 0.001, "第二階段")
	tree.root.remove_child(arena)
	arena.free()


func _arena() -> CombatArena:
	var tree := Engine.get_main_loop() as SceneTree
	var arena: CombatArena = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)
	return arena


func _free(arena: CombatArena) -> void:
	arena.get_parent().remove_child(arena)
	arena.free()


func test_nothing_of_the_scene_is_on_the_screen() -> void:
	# 使用者 2026-10-06：「畫面是畫面，場景是場景，不要越界到畫面」——畫面座標的圖層只有 UI（HUD、閃光、除錯資訊）
	assert_false((ArenaLayout as Script).get_script_constant_map().has("FOLIAGE"), "沒有畫面四角的枝葉")
	var arena := _arena()
	var layers: Array[String] = []
	var stack: Array[Node] = [arena]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n is CanvasLayer:
			layers.append(n.name)
		stack.append_array(n.get_children())
	layers.sort()
	assert_eq(layers, ["DebugLayer", "HudLayer"], "畫面座標的圖層只有血條等介面和除錯資訊：%s" % [layers])
	_free(arena)


func test_plants_sway_and_braziers_light_in_phase_two() -> void:
	var arena := _arena()
	var braziers: Array[Node2D] = []
	var plants := 0
	for pv: Node2D in arena.prop_views:
		if pv.data.has("fire"):
			braziers.append(pv)
		if float(pv.data.get("sway", 0.0)) > 0.0:
			plants += 1
			assert_true(pv.sprite.material is ShaderMaterial, "%s 會擺" % pv.data["kind"])
	assert_true(plants >= 20, "會隨風擺的植物：%d" % plants)
	assert_eq(braziers.size(), 4, "四個火盆")
	var fv: Node = arena.get_node("ArenaFloor")
	for i in 30:
		fv._process(1.0 / 30.0)
		for b in braziers:
			b._process(1.0 / 30.0)
	for b in braziers:
		assert_near(b._lit, 0.0, 0.001, "第一階段火盆是冷的")
	arena.sim.boss.phase = 2
	for i in 30:
		fv._process(1.0 / 30.0)
		for b in braziers:
			b._process(1.0 / 30.0)
	for b in braziers:
		assert_near(b._lit, 1.0, 0.001, "第二階段火盆燒起來")
	_free(arena)


func test_crows_fly_off_and_come_back() -> void:
	# 烏鴉（2026-10-06）：主角走近就飛走，附近沒人一陣子後飛回來；Boss 進入轉場就全部飛走、第二階段不回來
	var arena := _arena()
	var crow: Node2D = arena.world.get_node("Crow4")
	var sim := arena.sim
	sim.player.pos = Vector2(0, 150)
	for i in 10:
		crow._process(1.0 / 30.0)
	assert_eq(crow.mode, crow.Mode.PERCHED, "沒人靠近：停著")
	sim.player.pos = crow.home + Vector2(30, 60)
	for i in 30:
		crow._process(1.0 / 30.0)
	assert_true(crow.mode == crow.Mode.FLEEING or crow.mode == crow.Mode.AWAY, "主角走近：飛走")
	sim.player.pos = Vector2(0, 150)
	for i in 420:
		crow._process(1.0 / 30.0)
	assert_eq(crow.mode, crow.Mode.PERCHED, "飛遠、等七秒、飛回來停好（十四秒內）")
	assert_eq(crow._pos, crow.home)
	sim.boss.phase = 2
	for i in 600:
		crow._process(1.0 / 30.0)
	assert_eq(crow.mode, crow.Mode.AWAY, "第二階段：不回來")
	arena.reset_battle()
	assert_eq(crow.mode, crow.Mode.PERCHED, "新的一場：停回原位")
	_free(arena)
