extends TestCase
## M1：combat-design §5 移動。從靜止到全速 0.08 秒（5 幀），停下 0.06 秒（4 幀）。

var sim: CombatSim


func before_each() -> void:
	sim = CombatSim.new(1)
	# 把 Boss 移到遠處，避免身體碰撞干擾移動量測
	sim.boss.pos = Vector2(0, -170)
	sim.player.pos = Vector2(0, 60)


func _move(dir: Vector2, run := false, block := false) -> InputFrame:
	var f := InputFrame.new()
	f.move = dir
	f.run = run
	f.block = block
	return f


func _steps(n: int, dir: Vector2, run := false, block := false) -> void:
	for i in n:
		sim.step(_move(dir, run, block))


func test_walk_reaches_full_speed_in_5_frames() -> void:
	assert_eq(Frames.of(PlayerData.ACCEL_TIME), 5)
	_steps(4, Vector2.RIGHT)
	assert_near(sim.player.vel.length(), 80.0, 0.001, "第 4 幀還沒全速")
	_steps(1, Vector2.RIGHT)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001, "第 5 幀全速")
	_steps(10, Vector2.RIGHT)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001, "維持全速")


func test_walk_stops_in_4_frames() -> void:
	assert_eq(Frames.of(PlayerData.DECEL_TIME), 4)
	_steps(20, Vector2.RIGHT)
	_steps(3, Vector2.ZERO)
	assert_near(sim.player.vel.length(), 25.0, 0.001, "第 3 幀還在減速")
	_steps(1, Vector2.ZERO)
	assert_near(sim.player.vel.length(), 0.0, 0.001, "第 4 幀停下")


func test_run_speed_and_stop_time() -> void:
	_steps(5, Vector2.RIGHT, true)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_RUN, 0.001, "奔跑 5 幀全速")
	_steps(10, Vector2.RIGHT, true)
	_steps(3, Vector2.ZERO, false)
	assert_true(sim.player.vel.length() > 0.0, "放開後第 3 幀還在減速")
	_steps(1, Vector2.ZERO, false)
	assert_near(sim.player.vel.length(), 0.0, 0.001, "奔跑中停下也是 4 幀")


func test_run_to_walk_slows_down() -> void:
	_steps(10, Vector2.RIGHT, true)
	_steps(10, Vector2.RIGHT, false)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001)


func test_displacement_matches_speed() -> void:
	# 起步 5 幀的位移：(20+40+60+80+100)/60；之後每幀 100/60
	var start := sim.player.pos
	_steps(5 + 60, Vector2.RIGHT)
	var expected := (20.0 + 40.0 + 60.0 + 80.0 + 100.0) / 60.0 + 100.0
	assert_near(sim.player.pos.x - start.x, expected, 0.01, "水平位移")
	assert_near(sim.player.pos.y, start.y, 0.001, "沒有垂直位移")


func test_diagonal_is_not_faster() -> void:
	_steps(20, Vector2(1, 1))
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001)
	_steps(20, Vector2(1, 1) * 3.0)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001, "輸入超過 1 也會被限制")


func test_analog_input_scales_speed() -> void:
	_steps(20, Vector2(0.5, 0))
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK * 0.5, 0.001)


func test_turning_does_not_slide() -> void:
	_steps(20, Vector2.RIGHT)
	_steps(1, Vector2.LEFT)
	assert_true(sim.player.vel.x < 0.0, "反向輸入的下一幀就朝新方向移動，不滑行")
	assert_near(sim.player.vel.length(), PlayerData.SPEED_WALK, 0.001, "轉向不掉速")


func test_facing_follows_movement_when_unlocked() -> void:
	_steps(3, Vector2.LEFT)
	assert_eq(sim.player.facing, Vector2.LEFT)
	_steps(3, Vector2(0, 1))
	assert_eq(sim.player.facing, Vector2.DOWN)
	_steps(10, Vector2.ZERO)
	assert_eq(sim.player.facing, Vector2.DOWN, "停下後保持面向")


func test_speed_table_matches_doc() -> void:
	var p := sim.player
	var S := PlayerSim.State
	assert_near(p.max_speed_for(S.IDLE, false, false), 100.0, 0.001, "走")
	assert_near(p.max_speed_for(S.IDLE, false, true), 160.0, 0.001, "跑")
	assert_near(p.max_speed_for(S.IDLE, true, false), 85.0, 0.001, "鎖定中走")
	assert_near(p.max_speed_for(S.IDLE, true, true), 160.0, 0.001, "鎖定中跑")
	assert_near(p.max_speed_for(S.BLOCK, false, false), 50.0, 0.001, "格擋中")
	assert_near(p.max_speed_for(S.BLOCK, false, true), 50.0, 0.001, "格擋中不能跑")
	assert_near(p.max_speed_for(S.CHARGE, false, true), 40.0, 0.001, "蓄力不能跑")
	assert_near(p.max_speed_for(S.HEAL, true, true), 30.0, 0.001, "治療不能跑")


func test_cannot_leave_arena() -> void:
	for dir in [Vector2.RIGHT, Vector2.LEFT, Vector2.UP, Vector2.DOWN, Vector2(1, 1).normalized(), Vector2(-1, -1).normalized()]:
		sim = CombatSim.new(1)
		sim.boss.pos = Vector2(0, -170) if dir.y >= 0.0 else Vector2(0, 170)
		sim.player.pos = Vector2.ZERO
		_steps(60 * 8, dir, true)
		var p := sim.player.pos
		assert_true(ArenaGeometry.is_inside(p, PlayerData.HURT_RADIUS), "往 %s 跑 8 秒後仍在場內：%s" % [dir, p])
		# 應該貼著邊界（不是被卡在很裡面）
		assert_false(ArenaGeometry.is_inside(p, PlayerData.HURT_RADIUS + 2.0), "往 %s 應該到達邊界：%s" % [dir, p])


func test_slides_along_boundary() -> void:
	sim.player.pos = Vector2(0, ArenaGeometry.HALF_SIZE.y - PlayerData.HURT_RADIUS)
	_steps(60, Vector2(1, 1).normalized())
	assert_true(sim.player.pos.x > 30.0, "沿著邊界滑動，而不是卡住：%s" % sim.player.pos)


func test_cannot_walk_through_pillar() -> void:
	var pillar: Dictionary = ArenaGeometry.PILLARS[0]
	var c: Vector2 = pillar["pos"]
	sim.player.pos = c + Vector2(-60, 0)
	for i in 120:
		sim.step(_move(Vector2.RIGHT))
		var d := sim.player.pos.distance_to(c)
		assert_true(d >= pillar["radius"] + PlayerData.HURT_RADIUS - 0.01, "第 %d 幀穿進柱子：距離 %.2f" % [i, d])
		if d < pillar["radius"] + PlayerData.HURT_RADIUS - 0.01:
			return


func test_cannot_walk_through_boss() -> void:
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = Vector2(0, 60)
	_steps(120, Vector2.UP)
	var d := sim.player.pos.distance_to(sim.boss.pos)
	assert_true(d >= PlayerData.HURT_RADIUS + VeltharisData.HURT_RADIUS - 0.01, "不會穿過 Boss：距離 %.2f" % d)
	assert_true(sim.player.pos.y > sim.boss.pos.y, "停在 Boss 前方")


func test_input_delay_is_zero_frames() -> void:
	# plan §7：從按下到動作開始 ≤ 1 個物理幀。移動在按下的同一幀就有速度。
	sim.step(_move(Vector2.RIGHT))
	assert_true(sim.player.vel.x > 0.0, "按下的同一幀開始加速")
	assert_true(sim.player.pos.x > 0.0, "按下的同一幀開始位移")


func test_slowing_to_lower_cap_does_not_slide() -> void:
	# 從跑進入格擋（上限 50）：4 幀內降到新上限，不能慢慢滑行
	_steps(10, Vector2.RIGHT, true)
	_steps(4, Vector2.RIGHT, true, true)
	assert_eq(sim.player.state, PlayerSim.State.BLOCK)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_BLOCK, 0.001, "跑 → 格擋")
	_steps(10, Vector2.RIGHT, true)
	sim.player.enter_state(PlayerSim.State.HEAL)
	_steps(4, Vector2.RIGHT, true)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_HEAL, 0.001, "跑 → 治療")


func test_stop_is_4_frames_even_after_external_velocity() -> void:
	_steps(20, Vector2.RIGHT)
	_steps(10, Vector2.ZERO)
	sim.player.vel = Vector2(PlayerData.SPEED_RUN, 0)  # 例如擊退或閃身結束時留下的速度
	_steps(3, Vector2.ZERO)
	assert_true(sim.player.vel.length() > 0.0)
	_steps(1, Vector2.ZERO)
	assert_near(sim.player.vel.length(), 0.0, 0.001, "仍然 4 幀停下")


func test_tiny_input_does_not_zero_facing() -> void:
	_steps(3, Vector2.LEFT)
	_steps(1, Vector2(1e-30, 0))
	assert_eq(sim.player.facing, Vector2.LEFT, "極小的輸入視為沒有輸入")
	assert_near(sim.player.facing.length(), 1.0, 0.0001)


func test_running_flag_clears_outside_idle() -> void:
	_steps(5, Vector2.RIGHT, true)
	assert_true(sim.player.running)
	_steps(1, Vector2.RIGHT, true, true)
	assert_eq(sim.player.state, PlayerSim.State.BLOCK)
	assert_false(sim.player.running, "格擋中不是奔跑")
