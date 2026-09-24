extends SimTestCase
## M5：combat-design §11.5 階段轉換、boss-veltharis §5 第二階段。

const BS := BossSim.State
const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = Vector2(0, 40)
	sim.player.facing = Vector2.UP


func _half() -> int:
	return roundi(VeltharisData.MAX_HP * VeltharisData.PHASE2_HP_RATIO)


func test_transition_at_half_hp() -> void:
	sim.boss.set_ai()
	sim.boss.hp = _half() + 10
	sim.boss.toughness = 30.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])  # 15 → 降到 50% 以下
	advance(1)
	assert_eq(boss().state, BS.TRANSITION, "HP 降到 50% 以下：進入轉場")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS, 0.001, "韌性回滿")
	assert_false(boss().can_be_hit(), "轉場期間無敵")
	# 玩家的攻擊打不到（CombatSim 在 can_be_hit 為否時不結算）
	var hp := boss().hp
	sim.player.pos = sim.boss.pos + Vector2(0, 45)
	sim.player.facing = Vector2.UP
	press(&"attack")
	advance(12)
	assert_eq(boss().hp, hp, "轉場期間打不到")
	var start := boss().state_start
	while boss().state == BS.TRANSITION:
		advance(1)
	assert_eq(sim.combat_frame - start, Frames.of(VeltharisData.TRANSITION_TIME), "轉場 1.5 秒")
	assert_eq(boss().phase, 2, "進入第二階段")


func test_transition_boundary_is_inclusive_half() -> void:
	sim.boss.set_ai()
	sim.boss.hp = _half() + 1
	advance(2)
	assert_true(boss().state != BS.TRANSITION, "50% + 1 還在一階段")
	sim.boss.hp = _half()
	advance(1)
	assert_eq(boss().state, BS.TRANSITION, "剛好 50%（1560 時為 780）就進入二階段")


func test_transition_interrupts_attack() -> void:
	sim.god_mode = true
	sim.boss.set_ai()
	sim.boss.start_move(VeltharisData.move(1, &"twin_slash"))
	advance(20)
	sim.boss.hp = _half() - 1
	advance(1)
	assert_eq(boss().state, BS.TRANSITION)
	assert_eq(boss().attack_hitbox(), {})


func test_execution_crossing_half_waits_until_execution_ends() -> void:
	sim.boss.set_ai()
	sim.boss.hp = _half() + 100
	sim.boss.toughness = 1.0
	sim.boss.last_toughness_damage = sim.combat_frame
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().state, BS.BROKEN)
	sim.player.pos = sim.boss.pos + Vector2(0, 50)
	press(&"attack")
	assert_eq(boss().state, BS.EXECUTED)
	while player().state == S.EXECUTE:
		advance(1)
		assert_true(boss().state == BS.EXECUTED or boss().state == BS.TRANSITION)
	assert_true(boss().hp <= _half())
	advance(1)
	assert_eq(boss().state, BS.TRANSITION, "處決結束後才轉場（取代起身）")


func test_phase2_uses_phase2_moves_and_breathers() -> void:
	sim.god_mode = true
	sim.boss.set_ai()
	sim.boss.phase = 2
	sim.boss.hp = _half() - 1
	sim.boss.start_breather(10)
	advance(60 * 90)
	var moves := {}
	for e in event_log:
		if e["type"] == &"boss_attack":
			moves[e["move"]] = true
			assert_true(VeltharisData.moves(2).has(e["move"]), "第二階段只用第二階段的招式（%s）" % e["move"])
	assert_false(moves.has(&"twin_slash"), "雙斬在第二階段變成三斬")
	for b in boss().ai.breather_log:
		assert_between(float(b), Frames.of(0.4), Frames.of(0.9), "第二階段喘息 0.4–0.9 秒")


func test_phase2_runtime_recovery_shorter_startup_same() -> void:
	# §11.5：只縮短收招與喘息，不縮短起手
	for id: StringName in VeltharisData.moves(1):
		if not VeltharisData.moves(2).has(id):
			continue
		var m1 := VeltharisData.move(1, id)
		var m2 := VeltharisData.move(2, id)
		assert_eq(m2.hit_start_frames(), m1.hit_start_frames(), "%s 各擊時間相同" % id)
		assert_true(m2.total_frames() < m1.total_frames(), "%s 收招變短" % id)


func test_heal_punish_phase2_is_kings_leap() -> void:
	var got := 0
	for t in 40:
		sim = CombatSim.new(3000 + t)
		sim.boss.set_ai()
		sim.boss.phase = 2
		sim.boss.hp = _half() - 1
		sim.boss.pos = Vector2(0, -80)
		sim.player.pos = Vector2(0, 120)
		sim.player.hp = 50
		sim.boss.start_breather(120)
		event_log.clear()
		press(&"heal")
		advance(8)
		for e in event_log:
			if e["type"] == &"boss_attack" and e["move"] == &"kings_leap":
				got += 1
	assert_between(float(got) / 40.0, 0.5, 0.9, "第二階段治療懲罰用墜王之躍（約 70%）")


func test_kings_leap_airborne_invulnerable_and_lands_near_player() -> void:
	sim.god_mode = true
	sim.boss.phase = 2
	sim.boss.pos = Vector2(-150, -60)
	sim.player.pos = Vector2(120, 80)
	sim.boss.start_move(VeltharisData.move(2, &"kings_leap"))
	var air_from := Frames.of(0.7)
	var land := Frames.of(1.5)
	while boss().state_elapsed() < air_from - 1:
		advance(1)
	assert_true(boss().can_be_hit(), "起手（下蹲）還能被打")
	advance(1)
	assert_true(boss().is_airborne(), "0.7 秒起跳")
	assert_false(boss().can_be_hit(), "騰空期間無法被攻擊")
	assert_false(boss().has_body(), "騰空期間沒有身體碰撞")
	# 鎖定前玩家移動，落點追蹤；鎖定後移動，落點不變
	sim.player.pos = Vector2(60, 100)
	while boss().state_elapsed() < land - Frames.of(0.3) - 1:
		advance(1)
	var target := boss().landing_target
	sim.player.pos = Vector2(-100, 150)
	while boss().state_elapsed() < land:
		advance(1)
	assert_false(boss().is_airborne(), "1.5 秒落地")
	assert_true(boss().landing_target.is_equal_approx(target), "落地前 0.3 秒鎖定落點")
	assert_true(boss().pos.distance_to(target) < 1.0, "落在鎖定的落點")
	assert_true(target.distance_to(Vector2(60, 100)) < 60.0, "落點追蹤到玩家附近")


func test_kings_leap_can_be_parried() -> void:
	sim.boss.phase = 2
	sim.boss.pos = Vector2(-150, -60)
	sim.player.pos = Vector2(100, 60)
	press(&"lock")
	sim.boss.start_move(VeltharisData.move(2, &"kings_leap"))
	var land := Frames.of(1.5)
	while boss().state_elapsed() < land - 4:
		advance(1)
	held["block"] = true
	advance(6)
	assert_true(logged(&"perfect_parry"), "落地重擊可以完美彈返")
	assert_eq(boss().state, BS.BOUNCED)


func test_ash_spin_connects_twice_all_around() -> void:
	# 玩家鎖定並按住格擋（普通格擋兩次），Boss 在北、南兩側都打得到（360°）
	for side in [Vector2(0, -70), Vector2(0, 70)]:
		sim = CombatSim.new(1)
		sim.boss.phase = 2
		sim.boss.pos = Vector2(0, 0)
		sim.player.pos = sim.boss.pos + side
		sim.player.posture = 1000.0
		event_log.clear()
		press(&"lock")
		held["block"] = true
		advance(20)
		sim.boss.start_move(VeltharisData.move(2, &"ash_spin"))
		for i in 150:
			advance(1)
		var n := 0
		for e in event_log:
			if e["type"] == &"boss_hit_result":
				n += 1
		assert_eq(n, 2, "迴旋兩擊都打到（玩家在 %s）" % side)
		held["block"] = false


func test_double_impact_two_rings_each_with_danger() -> void:
	sim.boss.phase = 2
	sim.god_mode = true
	sim.boss.start_move(VeltharisData.move(2, &"double_impact"))
	var dangers := 0
	while boss().state == BS.ATTACK:
		advance(1)
	for e in event_log:
		if e["type"] == &"danger":
			dangers += 1
	assert_eq(dangers, 2, "兩個環各有危險預兆")


func test_boss_death() -> void:
	sim.boss.phase = 2
	sim.boss.hp = 10
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().hp, 0)
	assert_eq(boss().state, BS.DEAD)
	assert_true(logged(&"boss_dead") or _has_event(&"boss_dead"))
	assert_false(boss().can_be_hit())


func _has_event(t: StringName) -> bool:
	for e in sim.events:
		if e["type"] == t:
			return true
	return false


func test_leap_target_stays_in_arena_and_out_of_pillars() -> void:
	# 審查 M5-3：落點陰影就是實際落點（夾回場內、推出柱子）
	var pillar: Dictionary = ArenaGeometry.PILLARS[1]
	var c: Vector2 = pillar["pos"]
	sim.god_mode = true
	sim.boss.phase = 2
	sim.boss.pos = Vector2(-200, 60)
	sim.player.pos = c + Vector2(20, 0)
	sim.boss.start_move(VeltharisData.move(2, &"kings_leap"))
	while boss().state_elapsed() < Frames.of(1.5):
		advance(1)
	var target := boss().landing_target
	assert_true(boss().pos.distance_to(target) < 1.0, "實際落點與陰影一致（差 %.1f）" % boss().pos.distance_to(target))
	assert_true(target.distance_to(c) >= pillar["radius"] + VeltharisData.HURT_RADIUS - 0.1, "落點不在柱子裡")
	assert_true(ArenaGeometry.is_inside(target, VeltharisData.HURT_RADIUS), "落點在場內")
