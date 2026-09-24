extends TestCase
## M4：plan §7 模擬機器人。完美機器人（每一擊都在正確時機彈返或閃身）能零傷害擊敗第一階段。


func test_perfect_bot_beats_phase1_without_damage() -> void:
	for seed_value in [1, 2, 3, 4, 5, 6]:
		var r := FightRunner.run(seed_value, PerfectBot.new(), 400.0, roundi(VeltharisData.MAX_HP * VeltharisData.PHASE2_HP_RATIO))
		assert_eq(r["result"], &"win", "種子 %d：擊敗第一階段（%s）" % [seed_value, r])
		assert_eq(r["damage_taken"], 0, "種子 %d：零傷害" % seed_value)
		assert_eq(r["blocked"], 0, "種子 %d：沒有普通格擋（全部完美彈返）" % seed_value)


func test_threat_prediction_matches_actual_hit_frame() -> void:
	# 預測的「第一次碰到玩家」的幀，就是實際結算的幀（玩家不動）
	for id: StringName in VeltharisData.moves(1):
		var sim := CombatSim.new(3)
		sim.boss.pos = Vector2(0, -20)
		sim.player.pos = Vector2(0, 50)
		sim.boss.start_move(VeltharisData.move(1, id))
		var predicted := -1
		var actual := -1
		for i in 200:
			if sim.boss.state != BossSim.State.ATTACK:
				break
			var t := BotController.next_threat(sim)
			if predicted < 0 and not t.is_empty() and sim.boss.state_elapsed() >= t["start"] - sim.combat_frame + sim.boss.state_elapsed() - 12:
				predicted = t["overlap"]
			sim.step(InputFrame.new())
			for e in sim.events:
				if e["type"] == &"boss_hit_result" and actual < 0:
					actual = sim.combat_frame
			if actual >= 0:
				break
		assert_true(actual >= 0, "%s 這個距離要打得到（測試設定）" % id)
		assert_eq(predicted, actual, "%s 預測 %d、實際 %d" % [id, predicted, actual])


func test_human_bot_parameters_match_plan() -> void:
	var h := HumanBot.new(1)
	assert_eq(h.reaction_frames, Frames.of(0.25))
	assert_near(h.timing_sigma_frames, 3.6, 0.001, "60ms")
	assert_near(h.fooled_chance, 0.3, 0.001)



func test_perfect_bot_vs_every_move_at_many_distances() -> void:
	# 審查 M4-2：手動模式逐招、多個距離與角度，完美機器人都零傷害（★9 的實證）
	for phase in [1]:
		for id: StringName in VeltharisData.moves(phase):
			for dist in [40.0, 70.0, 100.0, 140.0, 180.0, 235.0]:
				for ang in [0.0, 1.2]:
					var sim := CombatSim.new(11)
					sim.boss.set_manual()
					sim.boss.phase = phase
					sim.boss.pos = Vector2(0, -40)
					sim.player.pos = sim.boss.pos + Vector2(sin(ang), cos(ang)) * dist
					sim.boss.queue_move(id)
					var bot := PerfectBot.new()
					var blocked := 0
					for i in 360:
						sim.step(bot.decide(sim))
						for e in sim.events:
							if e["type"] == &"block":
								blocked += 1
					assert_eq(sim.player.hp, PlayerData.MAX_HP, "%s 距離 %.0f 角度 %.1f：完美機器人被打中" % [id, dist, ang])
					assert_eq(blocked, 0, "%s 距離 %.0f 角度 %.1f：完美機器人出現普通格擋" % [id, dist, ang])
