extends TestCase
## M5：combat-design §14 死亡與重試（從死亡到可以操作 ≤ 3 秒）、勝利演出後可以重試。用真的競技場場景測。

var arena: CombatArena


func before_each() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	arena = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)


func after_each() -> void:
	arena.get_parent().remove_child(arena)
	arena.free()


func _step(n: int) -> void:
	for i in n:
		arena._physics_process(1.0 / 60.0)


func test_death_to_control_within_3_seconds() -> void:
	_step(5)
	var sim := arena.sim
	sim.player.hp = 1
	sim.apply_boss_hit(VeltharisData.move(1, &"royal_sweep").hits[0], sim.boss.pos)
	assert_eq(sim.player.state, PlayerSim.State.DEAD)
	var frames := 0
	while frames < 400:
		_step(1)
		frames += 1
		var p := arena.sim.player
		if arena.end_state == &"" and p.state == PlayerSim.State.IDLE and p.hp == PlayerData.MAX_HP:
			break
	assert_eq(arena.end_state, &"", "重置了戰鬥")
	assert_true(frames <= Frames.of(3.0), "從死亡到可以操作 %d 幀（上限 180）" % frames)
	assert_eq(arena.sim.player.hp, PlayerData.MAX_HP)
	assert_eq(arena.sim.player.heals, PlayerData.HEAL_CHARGES, "治療補滿")
	assert_eq(arena.sim.boss.hp, VeltharisData.MAX_HP, "Boss 滿血")
	assert_eq(arena.sim.boss.phase, 1)


func test_death_animation_then_retry_prompt() -> void:
	_step(5)
	arena.sim.player.hp = 1
	arena.sim.apply_boss_hit(VeltharisData.move(1, &"royal_sweep").hits[0], arena.sim.boss.pos)
	_step(Frames.of(PlayerData.DEATH_TIME) - 2)
	assert_false(arena.retry_prompt_visible(), "死亡動畫 1.5 秒內還沒顯示再戰")
	_step(4)
	assert_true(arena.retry_prompt_visible(), "死亡動畫之後顯示「再戰」")


func test_victory_then_retry_within_3_seconds() -> void:
	_step(5)
	var sim := arena.sim
	sim.boss.phase = 2
	sim.boss.hp = 5
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(sim.boss.state, BossSim.State.DEAD)
	var frames := 0
	while not arena.retry_prompt_visible() and frames < 400:
		_step(1)
		frames += 1
	assert_true(frames <= Frames.of(3.0), "勝利後 %d 幀可以重試（上限 180）" % frames)
	arena.request_retry()
	_step(2)
	assert_eq(arena.end_state, &"", "按下再戰就重置")
	assert_eq(arena.sim.boss.hp, VeltharisData.MAX_HP)
	assert_eq(arena.sim.boss.phase, 1)


func test_victory_marks_player_armor() -> void:
	_step(5)
	arena.sim.boss.hp = 5
	arena.sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	_step(Frames.of(3.0))
	assert_true(arena.player_view.ember_crack, "擊敗 Boss 後主角鎧甲多一道紅色裂紋（§15）")


func test_attack_during_victory_absorb_does_not_skip_victory() -> void:
	# 審查 M5-1：演出期間按攻擊鍵不會在提示出現時自動重置
	_step(5)
	arena.sim.boss.hp = 5
	arena.sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	_step(20)
	arena.request_retry()  # 提示還沒出現：無效
	while not arena.retry_prompt_visible():
		_step(1)
	_step(30)
	assert_eq(arena.end_state, &"victory", "提示出現後停在勝利畫面，等玩家按下")
	arena.request_retry()
	_step(1)
	assert_eq(arena.end_state, &"")
	assert_eq(arena.sim.player.state, PlayerSim.State.IDLE, "再戰那一下不會帶進新的一場")
