extends SimTestCase
## M2：combat-design §8 輕攻擊四段、§8.3 取消規則、§3 輸入緩衝、§12 頓幀。
## 幀數（Frames.of 四捨五入）：第 1、2 段 6/5/15，第 3 段 7/5/17，第 4 段 6/6/27（＋停頓 12）。
## 接段（§8.1，2026-09-29 第二次修改）：連按時相鄰兩段的判定開始相隔 0.25 秒（15 幀），
## 所以最早接段在第 1 段第 15 幀、第 2 段第 14 幀、第 3 段第 16 幀（2026-09-29 第三次修改：第 4 段起手 6 幀）。

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
	assert_eq(_stage_frames(3), [6, 6, 27])


func test_chain_frames_give_an_even_rhythm() -> void:
	# §8.1（2026-09-29 第二次修改）：連按時相鄰兩段的判定開始都相隔 COMBO_INTERVAL（15 幀）。
	# 最早接段的幀 = 這一段起手 + 15 − 下一段起手，但不早於判定結束。
	var interval := Frames.of(PlayerData.COMBO_INTERVAL)
	assert_eq(interval, 15)
	var chain: Array = []
	for i in 3:
		chain.append(PlayerData.chain_frame(i))
	assert_eq(chain, [15, 14, 16])
	var L := PlayerData.light_attacks()
	for i in 3:
		assert_true(chain[i] >= L[i].active_end_frame(), "第 %d 段：判定結束前不能接段" % (i + 1))
		assert_eq(chain[i] - L[i].startup_frames() + L[i + 1].startup_frames(), interval,
			"第 %d → %d 段：判定開始相隔 %d 幀" % [i + 1, i + 2, interval])
	assert_eq(PlayerData.chain_frame(3), -1, "第 4 段之後不能接")
	for i in 3:
		assert_true(chain[i] < L[i].total_frames(), "第 %d 段：收招結束前就能接（否則接段寬限會讓節奏提早）" % (i + 1))


func test_attack_pressed_before_chain_frame_waits_for_it() -> void:
	# 第 1 段第 11 幀（判定剛結束）按攻擊：還不能接，緩衝到第 15 幀才出第 2 段；第 14 幀已經可以閃身取消
	press(&"attack")
	while player().state_elapsed() < 10:
		advance(1)
	press(&"attack")  # elapsed 11
	assert_eq(player().state_elapsed(), 11)
	assert_eq(player().combo_index, 0, "判定結束那幀還不能接段")
	assert_false(player().can_start(&"attack"))
	while player().state_elapsed() < 14 and player().combo_index == 0:
		advance(1)
	assert_eq(player().combo_index, 0, "第 14 幀還在第 1 段")
	assert_true(player().can_start(&"dodge"), "第 14 幀已經可以閃身取消（判定結束 + 3 幀，§8.3 不變）")
	advance(1)
	assert_eq(player().combo_index, 1, "第 15 幀接上第 2 段")
	assert_eq(player().state_elapsed(), 0)

	# 第 2、3 段：接段幀前 9 幀按的會接上、10 幀前按的被丟掉（§3 緩衝，和第 1 段同一條規則）
	for stage in [1, 2]:
		for case in [[9, stage + 1], [10, stage]]:
			sim = CombatSim.new(1)
			place_near_boss(50.0)
			_go_to_stage(stage)
			var chain := PlayerData.chain_frame(stage)
			while player().state_elapsed() < chain - int(case[0]) - 1:
				advance(1)
			press(&"attack")
			assert_eq(player().state_elapsed(), chain - int(case[0]))
			while player().state_elapsed() < chain - 1 and player().combo_index == stage:
				advance(1)
			advance(1)
			assert_eq(player().combo_index, case[1], "第 %d 段：接段幀前 %d 幀按攻擊" % [stage + 1, case[0]])


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
	assert_eq(boss().hp, VeltharisData.MAX_HP - PlayerData.light_attacks()[0].damage, "第 6 幀（判定第一幀）命中")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - PlayerData.light_attacks()[0].toughness, 0.001)
	advance(4)
	assert_eq(boss().hp, VeltharisData.MAX_HP - PlayerData.light_attacks()[0].damage, "同一段只打中一次")


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
	advance(Frames.of(PlayerData.COMBO_GRACE) - 1)
	press(&"attack")
	assert_eq(player().combo_index, 0, "收招結束後接段寬限（12 幀）內還沒按就重置回第一段")


func test_combo_continues_within_grace_after_recovery() -> void:
	# §8.1（2026-09-29）：第 1–3 段收招結束後 0.2 秒（12 幀）內按攻擊，仍接下一段。
	# 待機的第 k 幀按下：k ≤ 11 接下一段，k = 12 重置。
	var grace := Frames.of(PlayerData.COMBO_GRACE)
	assert_eq(grace, 12)
	for stage in 3:
		for case in [[1, stage + 1], [grace - 1, stage + 1], [grace, 0]]:
			sim = CombatSim.new(1)
			place_near_boss(50.0)
			_go_to_stage(stage)
			while player().state == S.ATTACK:
				advance(1)
			assert_eq(player().state_elapsed(), 0)
			var k: int = case[0]
			assert_eq(player().next_combo_stage(), stage + 1, "第 %d 段剛結束：下一段是 %d" % [stage + 1, stage + 2])
			advance(k - 1)
			press(&"attack")
			assert_eq(player().state, S.ATTACK)
			assert_eq(player().combo_index, case[1], "第 %d 段結束後待機第 %d 幀按攻擊 → 第 %d 段" % [stage + 1, k, case[1] + 1])


func test_grace_ends_when_another_state_starts() -> void:
	press(&"attack")
	while player().state == S.ATTACK:
		advance(1)
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK)
	held["block"] = false
	advance(1)
	assert_eq(player().state, S.IDLE)
	assert_eq(player().next_combo_stage(), 0, "中間格擋過：寬限取消")
	press(&"attack")
	assert_eq(player().combo_index, 0, "格擋之後從第 1 段開始")


func test_grace_ends_on_dodge_heal_or_hit() -> void:
	# 閃身、治療、被打中都會進入別的狀態，寬限跟著取消
	for kind in [&"dodge", &"heal", &"hit"]:
		sim = CombatSim.new(1)
		place_near_boss(50.0)
		press(&"attack")
		while player().state == S.ATTACK:
			advance(1)
		match kind:
			&"dodge":
				press(&"dodge")
				assert_eq(player().state, S.DODGE)
			&"heal":
				press(&"heal")
				assert_eq(player().state, S.HEAL)
			&"hit":
				var hit: BossHitData = VeltharisData.moves(1).values()[0].hits[0]
				player().receive_boss_hit(hit, boss().pos)
				assert_true(player().is_in_hit_reaction())
		assert_eq(player().next_combo_stage(), 0, "%s 之後寬限取消" % kind)


func test_bot_lookahead_at_grace_boundary() -> void:
	# 機器人在一幀的最後決定、按鍵落在下一幀：next_combo_stage(1) 預告下一幀的段數
	press(&"attack")
	while player().state == S.ATTACK:
		advance(1)
	advance(Frames.of(PlayerData.COMBO_GRACE) - 2)  # 待機第 10 幀
	assert_eq(player().next_combo_stage(1), 1, "下一幀是第 11 幀：還在寬限內")
	advance(1)  # 第 11 幀
	assert_eq(player().next_combo_stage(), 1)
	assert_eq(player().next_combo_stage(1), 0, "下一幀是第 12 幀：寬限已過")


func test_moving_during_grace_keeps_combo() -> void:
	press(&"attack")
	while player().state == S.ATTACK:
		advance(1)
	move = Vector2.RIGHT
	advance(5)
	move = Vector2.ZERO
	press(&"attack")
	assert_eq(player().combo_index, 1, "寬限內走動不會中斷連段")


func test_no_grace_after_fourth_stage() -> void:
	_go_to_stage(3)
	while player().state == S.ATTACK:
		advance(1)
	assert_eq(player().next_combo_stage(), 0)
	press(&"attack")
	assert_eq(player().combo_index, 0, "第 4 段之後一律從第 1 段開始")


func test_fourth_stage_end_lag_frames() -> void:
	# §8.1（2026-09-29）：第 4 段收招之後停頓 0.2 秒（12 幀）。第 4 段共 6 + 6 + 27 + 12 = 51 幀。
	var a: PlayerAttackData = PlayerData.light_attacks()[3]
	assert_eq(Frames.of(PlayerData.FINISHER_END_LAG), 12)
	assert_eq(a.recovery_end_frame(), 39)
	assert_eq(a.total_frames(), 51)
	for i in 3:
		var b: PlayerAttackData = PlayerData.light_attacks()[i]
		assert_eq(b.recovery_end_frame(), b.total_frames(), "第 %d 段沒有停頓" % (i + 1))
	_go_to_stage(3)
	while player().state_elapsed() < 50:
		advance(1)
	assert_eq(player().state, S.ATTACK, "第 50 幀仍在停頓")
	advance(1)
	assert_eq(player().state, S.IDLE, "51 幀後回到待機")


func test_attack_cannot_start_during_end_lag() -> void:
	_go_to_stage(3)
	while player().state_elapsed() < 38:
		advance(1)
	press(&"attack")  # elapsed 39：停頓第 1 幀，離結束 12 幀（超過緩衝 9 幀）
	assert_eq(player().state_elapsed(), 39)
	assert_eq(player().state, S.ATTACK)
	assert_eq(player().combo_index, 3, "停頓中按攻擊不會出招")
	while player().state == S.ATTACK:
		advance(1)
	advance(1)
	assert_eq(player().state, S.IDLE, "離結束 12 幀前按的攻擊被丟棄，不會在停頓後自動出招")


func test_attack_buffered_in_end_lag_starts_right_after() -> void:
	_go_to_stage(3)
	while player().state_elapsed() < 44:
		advance(1)
	press(&"attack")  # elapsed 45：離結束 6 幀
	while player().state == S.ATTACK and player().combo_index == 3:
		advance(1)
	assert_eq(player().state, S.ATTACK, "停頓最後 0.15 秒內按的攻擊在停頓結束時執行")
	assert_eq(player().combo_index, 0)
	assert_eq(player().state_elapsed(), 0)


func test_end_lag_buffer_boundary() -> void:
	# 第 4 段共 51 幀：第 42 幀按的攻擊（離結束 9 幀）會在第 51 幀出招，第 41 幀按的（10 幀）被丟棄
	for case in [[41, false], [42, true]]:
		sim = CombatSim.new(1)
		place_near_boss(50.0)
		_go_to_stage(3)
		while player().state_elapsed() < case[0] - 1:
			advance(1)
		press(&"attack")
		assert_eq(player().state_elapsed(), case[0])
		while player().state == S.ATTACK and player().combo_index == 3:
			advance(1)
		assert_eq(player().state == S.ATTACK, case[1], "停頓第 %d 幀按攻擊：停頓後%s出招" % [case[0], "" if case[1] else "不"])


func test_no_movement_during_end_lag() -> void:
	_go_to_stage(3)
	while player().state_elapsed() < 39:
		advance(1)
	var p0 := player().pos
	move = Vector2.RIGHT
	while player().state_elapsed() < 50:
		advance(1)
	assert_eq(player().state, S.ATTACK)
	assert_eq(player().pos, p0, "停頓中（第 39–50 幀）不能移動")


func test_dodge_and_block_allowed_during_end_lag() -> void:
	# 第 4 段收招（第 12–38 幀）照舊不可取消；停頓（第 39–50 幀）可以閃身或格擋
	_go_to_stage(3)
	while player().state_elapsed() < 37:
		advance(1)
	sim.player.facing = Vector2.UP
	press(&"dodge")  # elapsed 38：收招最後一幀
	assert_eq(player().state, S.ATTACK, "收招中不能閃身")
	advance(1)
	assert_eq(player().state, S.DODGE, "停頓第 1 幀執行緩衝的閃身")

	sim = CombatSim.new(1)
	place_near_boss(50.0)
	_go_to_stage(3)
	while player().state_elapsed() < 38:
		advance(1)
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK, "停頓中可以格擋")


func test_mashing_gives_four_stages_then_a_pause() -> void:
	# 每一幀都按攻擊：1→2→3→4 在最早的幀接上（判定開始每 15 幀一次），第 4 段之後停頓，再從第 1 段開始
	sim.boss.set_dummy()
	sim.boss.pos = Vector2(0, -300)
	sim.player.pos = Vector2(0, 60)
	var starts: Array = []
	for i in 160:
		tick([&"attack"])
		for e in sim.events:
			if e["type"] == &"player_attack":
				starts.append([sim.combat_frame, e["stage"]])
	var stages: Array = []
	var gaps: Array = []
	for i in starts.size():
		stages.append(starts[i][1])
		if i > 0:
			gaps.append(starts[i][0] - starts[i - 1][0])
	assert_eq(stages.slice(0, 5), [0, 1, 2, 3, 0], "連按：四段後回到第 1 段")
	assert_eq(gaps.slice(0, 4), [15, 14, 16, 51], "第 4 段到下一次出招：起手 6 + 判定 6 + 收招 27 + 停頓 12")
	var hits: Array = []
	for i in 4:
		hits.append(starts[i][0] + PlayerData.light_attacks()[starts[i][1]].startup_frames())
	assert_eq([hits[1] - hits[0], hits[2] - hits[1], hits[3] - hits[2]], [15, 15, 15], "四刀的判定開始間隔一樣")


func test_pressing_in_recovery_chains_immediately() -> void:
	press(&"attack")
	advance(15)  # elapsed 15：收招中、已經可以接段
	press(&"attack")
	assert_eq(player().state, S.ATTACK)
	assert_eq(player().combo_index, 1, "收招期間按攻擊接第 2 段")
	assert_eq(player().state_elapsed(), 0, "立刻開始")


func test_full_combo_damage_and_toughness() -> void:
	# 每段在最早可以接段的那幀接下一段
	press(&"attack")
	for i in 3:
		while player().state_elapsed() < PlayerData.chain_frame(i) - 1:
			advance(1)
		press(&"attack")
		assert_eq(player().combo_index, i + 1)
	advance(60)
	assert_eq(boss().hp, VeltharisData.MAX_HP - (11 + 11 + 11 + 18), "四段總傷害 70（tuning-log：11 + 11 + 11 + 18 = 51）")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - (1.4 + 1.4 + 1.4 + 4.2), 0.001, "四段總削韌 12（tuning-log：× 0.7 = 8.4）")
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
	# 第 1 段最早在第 15 幀接段。第 6 幀按攻擊（9 幀前）會接上；第 5 幀按（10 幀前）不會。
	press(&"attack")
	while player().state_elapsed() < 5:
		advance(1)
	press(&"attack")  # elapsed 6
	while player().state_elapsed() < 14:
		advance(1)
	advance(1)
	assert_eq(player().combo_index, 1, "9 幀前按下的攻擊在可以接段時執行")
	assert_eq(player().state_elapsed(), 0)

	sim = CombatSim.new(1)
	place_near_boss(50.0)
	press(&"attack")
	while player().state_elapsed() < 4:
		advance(1)
	press(&"attack")  # elapsed 5：距可以接段 10 幀
	while player().state_elapsed() < 15:
		advance(1)
	assert_eq(player().combo_index, 0, "10 幀前按下的攻擊被丟棄")
	assert_eq(player().state_elapsed(), 15)


func test_buffered_attack_after_fourth_stage_starts_new_combo() -> void:
	_go_to_stage(3)
	var total: int = PlayerData.light_attacks()[3].total_frames()
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
	while player().state_elapsed() < PlayerData.chain_frame(0) - 1 and player().combo_index == 0:
		advance(1)
	advance(1)
	assert_eq(player().combo_index, 1, "頓幀中按的攻擊在可以接段時接上第 2 段")


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
		while player().state_elapsed() < PlayerData.chain_frame(i):
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
