extends SimTestCase
## M2：combat-design §8 輕攻擊四段、§8.3 取消規則、§3 輸入緩衝、§12 頓幀。
## 幀數（Frames.of 四捨五入）：第 1、2 段 6/5/15，第 3 段 7/5/17，第 4 段 11/6/27。

const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	place_near_boss(50.0)


func _stage_frames(i: int) -> Array:
	var a: PlayerAttackData = PlayerData.light_attacks()[i]
	return [Frames.of(a.startup), Frames.of(a.active), Frames.of(a.recovery)]


func test_stage_frame_counts() -> void:
	assert_eq(_stage_frames(0), [6, 5, 15])
	assert_eq(_stage_frames(1), [6, 5, 15])
	assert_eq(_stage_frames(2), [7, 5, 17])
	assert_eq(_stage_frames(3), [11, 6, 27])


func test_attack_starts_on_press_frame() -> void:
	press(&"attack")
	assert_eq(player().state, S.ATTACK, "按下的同一幀進入攻擊（輸入延遲 0 幀）")
	assert_eq(player().state_elapsed(), 0)
	assert_eq(player().combo_index, 0)


func test_light_1_hits_on_first_active_frame_only_once() -> void:
	press(&"attack")
	advance(5)
	assert_eq(boss().hp, VeltharisData.MAX_HP, "起手 6 幀內沒有判定")
	advance(1)
	assert_eq(player().state_elapsed(), 6)
	assert_eq(boss().hp, VeltharisData.MAX_HP - 15, "第 6 幀（判定第一幀）命中")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - 2, 0.001)
	advance(4)
	assert_eq(boss().hp, VeltharisData.MAX_HP - 15, "同一段只打中一次")


func test_active_window_edges() -> void:
	# 把 Boss 放在範圍外，在指定的幀移進來，檢查判定窗口的最後一幀與收招第一幀
	for case in [[10, true], [11, false], [5, false]]:
		sim = CombatSim.new(1)
		place_near_boss(50.0)
		var far := sim.boss.pos + Vector2(0, -400)
		var near := sim.boss.pos
		sim.boss.pos = far
		press(&"attack")
		var f: int = case[0]
		while player().state_elapsed() < f - 1:
			advance(1)
		sim.boss.pos = near
		advance(1)
		assert_eq(player().state_elapsed(), f)
		assert_eq(boss().hp < VeltharisData.MAX_HP, case[1], "第 %d 幀移入範圍：命中=%s" % [f, case[1]])


func test_light_1_ends_after_recovery_and_resets_combo() -> void:
	press(&"attack")
	advance(25)
	assert_eq(player().state, S.ATTACK, "第 25 幀仍在收招")
	advance(1)
	assert_eq(player().state, S.IDLE, "6+5+15 = 26 幀後回到待機")
	press(&"attack")
	assert_eq(player().combo_index, 0, "收招結束還沒按就重置回第一段")


func test_pressing_in_recovery_chains_immediately() -> void:
	press(&"attack")
	advance(12)  # elapsed 12：收招中
	press(&"attack")
	assert_eq(player().state, S.ATTACK)
	assert_eq(player().combo_index, 1, "收招期間按攻擊接第 2 段")
	assert_eq(player().state_elapsed(), 0, "立刻開始")


func test_full_combo_damage_and_toughness() -> void:
	# 每段在收招第一幀接下一段
	press(&"attack")
	for i in 3:
		var fr := _stage_frames(i)
		while player().state_elapsed() < fr[0] + fr[1] - 1:
			advance(1)
		press(&"attack")
		assert_eq(player().combo_index, i + 1)
	advance(50)
	assert_eq(boss().hp, VeltharisData.MAX_HP - (15 + 15 + 15 + 25), "四段總傷害 70")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - (2 + 2 + 2 + 6), 0.001, "四段總削韌 12")
	assert_eq(player().state, S.IDLE)


func test_fourth_stage_cannot_chain_or_cancel() -> void:
	_go_to_stage(3)
	var fr := _stage_frames(3)
	while player().state_elapsed() < fr[0] + fr[1] + 3:
		advance(1)
	press(&"dodge")
	assert_eq(player().state, S.ATTACK, "第 4 段收招不能用閃身取消")
	advance(10)
	press(&"attack")
	assert_eq(player().state, S.ATTACK)
	assert_eq(player().combo_index, 3, "第 4 段之後不能再接")


func test_cancel_window_for_stages_1_to_3() -> void:
	for stage in 3:
		sim = CombatSim.new(1)
		place_near_boss(50.0)
		_go_to_stage(stage)
		var fr := _stage_frames(stage)
		var cancel_at: int = fr[0] + fr[1] + Frames.of(PlayerData.CANCEL_DELAY)
		# 取消點前一幀：不能取消（進入緩衝）
		while player().state_elapsed() < cancel_at - 2:
			advance(1)
		sim.player.facing = Vector2.UP
		press(&"dodge")
		assert_eq(player().state_elapsed(), cancel_at - 1)
		assert_eq(player().state, S.ATTACK, "第 %d 段：判定結束 0.05 秒前不能取消" % (stage + 1))
		advance(1)
		assert_eq(player().state, S.DODGE, "第 %d 段：判定結束 0.05 秒（3 幀）後取消，緩衝的閃身立刻執行" % (stage + 1))


func test_startup_cannot_be_cancelled() -> void:
	press(&"attack")
	advance(2)
	press(&"dodge")
	assert_eq(player().state, S.ATTACK, "起手期間不可取消")


func test_buffer_limit_is_9_frames() -> void:
	# 第 1 段收招開始於第 11 幀。第 2 幀按攻擊（9 幀前）會接上；第 1 幀按（10 幀前）不會。
	press(&"attack")
	advance(1)  # elapsed 1
	press(&"attack")  # elapsed 2
	while player().state_elapsed() < 10:
		advance(1)
	advance(1)
	assert_eq(player().combo_index, 1, "9 幀前按下的攻擊在收招開始時執行")
	assert_eq(player().state_elapsed(), 0)

	sim = CombatSim.new(1)
	place_near_boss(50.0)
	press(&"attack")
	press(&"attack")  # elapsed 1：距收招開始 10 幀
	while player().state_elapsed() < 11:
		advance(1)
	assert_eq(player().combo_index, 0, "10 幀前按下的攻擊被丟棄")
	assert_eq(player().state_elapsed(), 11)


func test_buffered_attack_after_fourth_stage_starts_new_combo() -> void:
	_go_to_stage(3)
	var total: int = _stage_frames(3)[0] + _stage_frames(3)[1] + _stage_frames(3)[2]
	while player().state_elapsed() < total - 5:
		advance(1)
	press(&"attack")
	while player().state == S.ATTACK and player().combo_index == 3:
		advance(1)
	assert_eq(player().state, S.ATTACK, "第 4 段結束時執行緩衝的攻擊")
	assert_eq(player().combo_index, 0, "從第 1 段開始")
	assert_eq(player().state_elapsed(), 0)


func test_hitstop_frames_per_stage() -> void:
	press(&"attack")
	advance(5)
	var before := sim.frame
	advance(1)  # 第 6 幀命中
	assert_eq(sim.hitstop, Frames.of(0.04), "輕攻擊命中頓幀 0.04 秒")
	advance(1)
	assert_eq(sim.frame - before, 1 + 2 + 1, "頓幀期間戰鬥時間暫停")


func test_fourth_stage_and_heavy_hitstop() -> void:
	_go_to_stage(3)
	var fr := _stage_frames(3)
	while player().state_elapsed() < fr[0] - 1:
		advance(1)
	advance(1)
	assert_eq(sim.hitstop, Frames.of(0.07), "第 4 段命中頓幀 0.07 秒")


func test_hitstop_does_not_drop_buffered_input() -> void:
	# 命中後的頓幀期間按攻擊：頓幀結束後照樣接下一段（CLAUDE.md：頓幀不影響輸入緩衝）
	press(&"attack")
	advance(6)  # 命中，進入頓幀
	assert_true(sim.hitstop > 0)
	tick([&"attack"])  # 頓幀中按下
	while player().state_elapsed() < 10 and player().combo_index == 0:
		advance(1)
	advance(1)
	assert_eq(player().combo_index, 1, "頓幀中按的攻擊在收招開始時接上第 2 段")


func test_attack_advance_distance() -> void:
	sim.boss.pos = Vector2(0, -300)
	sim.player.pos = Vector2(0, 60)
	sim.player.facing = Vector2.UP
	var y0 := sim.player.pos.y
	press(&"attack")
	advance(30)
	assert_near(y0 - sim.player.pos.y, 6.0, 0.01, "第 1 段前進 6px")


func test_aim_assist_turns_toward_boss_in_front_cone() -> void:
	sim.boss.pos = Vector2(0, 0)
	sim.player.pos = Vector2(40, 60)  # 在右下方：朝上偏約 34°... 距離邊緣約 46px
	sim.player.facing = Vector2(-0.3, -1).normalized()
	press(&"attack")
	var to := (sim.boss.pos - sim.player.pos).normalized()
	assert_near(player().facing.angle_to(to), 0.0, 0.001, "前方 60° 內、80px 內的敵人：自動轉向")


func test_aim_assist_ignores_enemy_outside_cone() -> void:
	sim.boss.pos = Vector2(0, 0)
	sim.player.pos = Vector2(60, 40)
	sim.player.facing = Vector2.UP
	press(&"attack")
	assert_eq(player().facing, Vector2.UP, "不在前方 60° 內：不轉向")


func _go_to_stage(stage: int) -> void:
	press(&"attack")
	for i in stage:
		var fr := _stage_frames(i)
		while player().state_elapsed() < fr[0] + fr[1]:
			advance(1)
		press(&"attack")
	assert_eq(player().combo_index, stage)


func test_heavy_hit_hitstop_is_6_frames() -> void:
	place_near_boss(60.0)
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	var guard := 0
	while boss().hp == VeltharisData.MAX_HP and guard < 30:
		advance(1)
		guard += 1
	assert_eq(sim.hitstop, Frames.of(0.10), "重擊命中頓幀 0.10 秒")


func test_aim_assist_range_is_measured_to_enemy_edge() -> void:
	# 中心距 100（邊緣 74 ≤ 80）：轉向；中心距 110（邊緣 84 > 80）：不轉向
	for case in [[100.0, true], [110.0, false]]:
		sim = CombatSim.new(1)
		sim.boss.pos = Vector2(0, -20)
		var dir := Vector2(0.3, -1).normalized()
		sim.player.pos = sim.boss.pos - dir * case[0]
		sim.player.facing = Vector2.UP
		press(&"attack")
		var turned := absf(player().facing.angle_to(dir)) < 0.001
		assert_eq(turned, case[1], "中心距 %.0f" % case[0])


func test_unlocked_attack_follows_stick_on_press_frame() -> void:
	sim.boss.pos = Vector2(0, -170)
	sim.player.pos = Vector2(0, 60)
	sim.player.facing = Vector2.UP
	move = Vector2.RIGHT
	press(&"attack")
	assert_eq(player().facing, Vector2.RIGHT, "未鎖定：出招方向跟著當下的推桿方向")


func test_heavy_cannot_cancel_light_recovery() -> void:
	press(&"attack")
	advance(15)  # 收招中（判定結束 +4）
	press(&"heavy")
	assert_eq(player().state, S.ATTACK, "重擊不能取消輕攻擊收招")
	# 收招最後 9 幀內按下且仍按住：收招結束時開始蓄力
	while player().state_elapsed() < 20:
		advance(1)
	press(&"heavy")
	while player().state == S.ATTACK:
		advance(1)
	assert_eq(player().state, S.CHARGE, "緩衝的重擊在收招結束時開始蓄力")


func test_attack_does_not_cancel_charge() -> void:
	press(&"heavy")
	advance(10)
	press(&"attack")
	assert_eq(player().state, S.CHARGE, "蓄力中按攻擊不會取消蓄力")


func test_presses_during_hitstop_keep_latest() -> void:
	# 頓幀中先按閃身、再按攻擊：只保留最新的攻擊
	press(&"attack")
	advance(6)
	assert_true(sim.hitstop >= 2)
	tick([&"dodge"])
	tick([&"attack"])
	advance(1)
	assert_eq(player().buffered_action, &"attack", "頓幀中較晚的按鍵覆蓋較早的")


func test_lock_pressed_twice_during_hitstop_cancels_out() -> void:
	press(&"attack")
	advance(6)
	assert_true(sim.hitstop >= 2)
	var was := player().locked
	tick([&"lock"])
	tick([&"lock"])
	advance(1)
	assert_eq(player().locked, was, "鎖定鍵按兩次等於沒按")
