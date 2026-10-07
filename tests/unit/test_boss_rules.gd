extends SimTestCase
## M4：combat-design §11 Boss 通用規則：霸體、短僵直與冷卻 ★、韌性回復、失衡與處決。

const BS := BossSim.State
const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -20)
	sim.player.pos = Vector2(0, 30)
	sim.player.facing = Vector2.UP


func _stage4() -> PlayerAttackData:
	return PlayerData.light_attacks()[3]


func test_short_stagger_when_idle_by_stage4_or_heavy() -> void:
	sim.boss.receive_player_hit(_stage4())
	assert_eq(boss().state, BS.STAGGER, "待機時被第 4 段打中：短僵直")
	advance(Frames.of(VeltharisData.SHORT_STAGGER_TIME) - 1)
	assert_eq(boss().state, BS.STAGGER)
	advance(1)
	assert_ne_stagger("0.3 秒後恢復")


func assert_ne_stagger(msg: String) -> void:
	assert_true(boss().state != BS.STAGGER, msg)


func test_light_stages_1_to_3_never_stagger() -> void:
	for i in 3:
		sim = CombatSim.new(1)
		sim.boss.receive_player_hit(PlayerData.light_attacks()[i])
		assert_eq(boss().state, BS.IDLE, "第 %d 段不會短僵直" % (i + 1))


func test_short_stagger_in_recovery() -> void:
	sim.god_mode = true
	sim.boss.start_move(VeltharisData.move(1, &"royal_sweep"))
	var m := boss().move
	while boss().state_elapsed() < m.last_hit_end_frame() + 3:
		advance(1)
	sim.boss.receive_player_hit(PlayerData.heavy_thrust())
	assert_eq(boss().state, BS.STAGGER, "收招期間被重擊打中：短僵直")


func test_short_stagger_cooldown_3s_star6() -> void:
	sim.boss.receive_player_hit(_stage4())
	assert_eq(boss().state, BS.STAGGER)
	var first := sim.combat_frame
	while boss().state == BS.STAGGER:
		advance(1)
	# 冷卻中：再被打不會僵直
	while sim.combat_frame - first < Frames.of(VeltharisData.SHORT_STAGGER_COOLDOWN) - 1:
		sim.boss.receive_player_hit(_stage4())
		assert_true(boss().state != BS.STAGGER, "冷卻中（第 %d 幀）不能再短僵直 ★6" % (sim.combat_frame - first))
		sim.boss.hp = VeltharisData.MAX_HP
		sim.boss.toughness = VeltharisData.MAX_TOUGHNESS
		if boss().state != BS.IDLE:
			return
		advance(1)
	advance(1)
	sim.boss.receive_player_hit(_stage4())
	assert_eq(boss().state, BS.STAGGER, "3 秒後可以再短僵直")


func test_toughness_regen_waits_2s_and_scales_with_hp() -> void:
	sim.boss.toughness = 50.0
	sim.boss.last_toughness_damage = sim.combat_frame
	advance(Frames.of(VeltharisData.TOUGHNESS_REGEN_DELAY) - 1)
	assert_near(boss().toughness, 50.0, 0.001, "2 秒內不回復（tuning-log：2.6 秒）")
	advance(60)
	var base := VeltharisData.TOUGHNESS_REGEN_BASE
	assert_near(boss().toughness, 50.0 + base, 0.05, "滿血時每秒回 10（tuning-log：7）")
	sim = CombatSim.new(1)
	sim.boss.phase = 2  # 半血時一階段會轉場（韌性回滿），這裡直接看二階段
	sim.boss.hp = roundi(VeltharisData.MAX_HP * 0.5)
	sim.boss.toughness = 50.0
	sim.boss.last_toughness_damage = sim.combat_frame
	advance(Frames.of(VeltharisData.TOUGHNESS_REGEN_DELAY) - 1)
	advance(60)
	assert_near(boss().toughness, 50.0 + base * (0.3 + 0.7 * 0.5), 0.05, "半血時每秒回滿血時的 65%")


func test_break_at_zero_toughness() -> void:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().state, BS.BROKEN, "韌性歸零：失衡")
	assert_eq(sim.hitstop, Frames.of(0.15), "失衡頓幀 0.15 秒")
	advance(Frames.of(VeltharisData.BREAK_TIME) - 1)
	assert_eq(boss().state, BS.BROKEN, "失衡 3 秒")
	advance(1)
	assert_eq(boss().state, BS.RISING, "3 秒沒有處決：自行恢復，先起身（2026-10-05 使用者：和處決後一樣花 1 秒）")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS, 0.001, "韌性回滿")
	assert_false(boss().can_be_executed(sim.player.pos), "起身時不能處決")
	advance(Frames.of(VeltharisData.RISE_TIME) - 1)
	assert_eq(boss().state, BS.RISING, "起身 1 秒")
	advance(1)
	assert_true(boss().state in [BS.IDLE, BS.WALK], "起身完才行動")


## 自己站起來和處決後的起身一樣是霸體：重擊打中也不會短僵直
func test_rising_after_a_break_is_super_armored() -> void:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	advance(Frames.of(VeltharisData.BREAK_TIME))
	assert_eq(boss().state, BS.RISING)
	sim.boss.last_short_stagger = -100000
	sim.boss.receive_player_hit(PlayerData.light_attacks()[3])
	assert_eq(boss().state, BS.RISING, "第 4 段打中：不短僵直")


func test_break_interrupts_attack() -> void:
	sim.god_mode = true
	sim.boss.start_move(VeltharisData.move(1, &"twin_slash"))
	advance(10)
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().state, BS.BROKEN, "出招中韌性歸零也會失衡")
	assert_eq(boss().attack_hitbox(), {})


func test_parry_can_break() -> void:
	sim.boss.toughness = 10.0
	sim.god_mode = false
	held["block"] = true
	advance(1)
	sim.apply_boss_hit(VeltharisData.move(1, &"twin_slash").hits[0], sim.boss.pos)
	assert_eq(boss().state, BS.BROKEN, "完美彈返削到 0 也失衡")


func test_execution_within_48px() -> void:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().state, BS.BROKEN)
	var hp0 := boss().hp
	# 距離受擊圓邊緣 48px 內、不限方向：從 Boss 背後按攻擊
	sim.player.pos = sim.boss.pos + Vector2(0, -(VeltharisData.HURT_RADIUS + 40.0))
	sim.player.facing = Vector2.UP  # 背對 Boss 也可以
	press(&"attack")
	assert_eq(player().state, S.EXECUTE, "按攻擊觸發處決")
	assert_eq(boss().state, BS.EXECUTED)
	assert_true(player().is_invulnerable(), "處決期間玩家無敵")
	var start := player().state_start
	# 2026-10-05 使用者：處決 3 秒（躍起下刺），0.8 秒插下去才扣血
	while sim.combat_frame - start < Frames.of(PlayerData.EXECUTE_HIT_TIME) - 1:
		advance(1)
		assert_eq(boss().hp, hp0, "插下去之前不扣血（第 %d 幀）" % (sim.combat_frame - start))
	advance(1)
	assert_eq(sim.combat_frame - start, Frames.of(PlayerData.EXECUTE_HIT_TIME))
	var dmg := roundi(VeltharisData.MAX_HP * VeltharisData.EXECUTE_DAMAGE_RATIO)
	assert_eq(boss().hp, hp0 - dmg, "處決傷害為最大 HP 的 15%（tuning-log：10.5%）")
	assert_eq(sim.hitstop, Frames.of(0.25), "處決頓幀 0.25 秒")
	while player().state == S.EXECUTE:
		assert_true(player().is_invulnerable(), "全程無敵（第 %d 幀）" % (sim.combat_frame - start))
		assert_eq(boss().hp, hp0 - dmg, "只扣一次血")
		assert_eq(boss().state, BS.EXECUTED, "Boss 被處決到最後一幀")
		advance(1)
	assert_eq(sim.combat_frame - start, Frames.of(PlayerData.EXECUTE_TIME), "處決 3 秒")
	assert_eq(boss().state, BS.RISING, "處決後 Boss 起身")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS, 0.001, "韌性回滿")
	var rise_start := boss().state_start
	sim.boss.receive_player_hit(_stage4())
	assert_eq(boss().state, BS.RISING, "起身期間霸體（不會短僵直）")
	while boss().state == BS.RISING:
		advance(1)
	assert_eq(sim.combat_frame - rise_start, Frames.of(VeltharisData.RISE_TIME), "起身 1 秒")


## 處決的時間軸（2026-10-05 使用者同意的分配）：衝上前蓄勢 → 躍起 → 0.8 秒插下去 → 轉劍兩次 → 2.0 秒蹬開 → 2.5 秒落地 → 3 秒站好
func _start_execution_from(offset: Vector2) -> int:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	sim.player.pos = sim.boss.pos + offset
	sim.player.facing = -offset.normalized()
	press(&"attack")
	assert_eq(player().state, S.EXECUTE)
	return player().state_start


func _advance_to(start: int, f: int) -> void:
	advance(start + f - sim.combat_frame)


func test_execution_twists_the_sword_twice() -> void:
	var start := _start_execution_from(Vector2(0, 70))
	_advance_to(start, Frames.of(PlayerData.EXECUTE_TIME))
	var twists: Array[int] = []
	for e in event_log:
		if e["type"] == &"execution_twist":
			twists.append(int(e["frame"]) - start)
	assert_eq(twists, PlayerData.execute_twist_frames(), "轉劍兩次，在插下去和蹬開之間")
	for f in twists:
		assert_true(f > Frames.of(PlayerData.EXECUTE_HIT_TIME) and f < Frames.of(PlayerData.EXECUTE_KICK_TIME), "第 %d 幀" % f)
	var shakes := 0
	for e in event_log:
		if e["type"] == &"feedback" and e["event"] == &"execution_twist":
			shakes += 1
			assert_true(e["shake"] > 0.0 and e["shake"] < FeedbackData.shake(&"execution"), "轉劍：小的震動")
	assert_eq(shakes, 2)
	assert_eq(FeedbackData.hitstop_frames(&"execution_twist"), 0, "轉劍不頓幀（Boss 抽動和騎士的動作對齊戰鬥時間）")


func test_execution_leaps_onto_the_boss_and_jumps_back_off() -> void:
	var dir := Vector2(0.6, 0.8)
	var start := _start_execution_from(dir * 78.0)
	var contact := VeltharisData.HURT_RADIUS + PlayerData.HURT_RADIUS + 2.0
	_advance_to(start, Frames.of(PlayerData.EXECUTE_LEAP_TIME))
	assert_near(player().pos.distance_to(boss().pos), contact, 0.5, "0.4 秒：衝到身體接觸處（起跳點）")
	var prev := player().pos.distance_to(boss().pos)
	while sim.combat_frame - start < Frames.of(PlayerData.EXECUTE_HIT_TIME):
		advance(1)
		var d := player().pos.distance_to(boss().pos)
		assert_true(d <= prev + 0.001, "躍起時越來越近")
		prev = d
	assert_near(player().pos.distance_to(boss().pos), PlayerData.EXECUTE_PERCH, 0.5, "插下去時在 Boss 肩上（影子在他身邊）")
	assert_near((player().pos - boss().pos).normalized().dot(dir), 1.0, 0.01, "從哪一邊來就刺哪一邊")
	var perch := player().pos
	_advance_to(start, Frames.of(PlayerData.EXECUTE_KICK_TIME))
	assert_true(player().pos.is_equal_approx(perch), "掛在劍上：不被推開")
	_advance_to(start, Frames.of(PlayerData.EXECUTE_LAND_TIME))
	assert_near(player().pos.distance_to(boss().pos), PlayerData.EXECUTE_LAND_DIST, 0.5, "2.5 秒落地")
	var land := player().pos
	_advance_to(start, Frames.of(PlayerData.EXECUTE_TIME))
	assert_true(player().pos.is_equal_approx(land), "落地後蹲著站起來，不再移動")
	assert_near(player().facing.dot(-dir), 1.0, 0.01, "全程面向 Boss")
	assert_eq(player().state, S.IDLE)


func test_execution_landing_stays_in_the_arena() -> void:
	# Boss 靠著南邊的牆，主角從牆那一側來：往回跳會跳出場地，改往旁邊跳
	sim.boss.pos = Vector2(0, ArenaGeometry.HALF_SIZE.y - VeltharisData.HURT_RADIUS - 20.0)
	var start := _start_execution_from(Vector2(0, 52))
	_advance_to(start, Frames.of(PlayerData.EXECUTE_LAND_TIME))
	var p := player().pos
	assert_true(ArenaGeometry.resolve(p, PlayerData.HURT_RADIUS).is_equal_approx(p), "落在場地裡、不在柱子裡：%s" % p)
	assert_near(p.distance_to(boss().pos), PlayerData.EXECUTE_LAND_DIST, 0.5)
	# 靠著柱子：落點不在柱子裡
	sim = CombatSim.new(1)
	event_log.clear()
	var pillar: Vector2 = ArenaGeometry.PILLARS[0]["pos"]
	sim.boss.pos = pillar + Vector2(80, 0)
	start = _start_execution_from(Vector2(-50, 0))
	_advance_to(start, Frames.of(PlayerData.EXECUTE_LAND_TIME))
	p = player().pos
	assert_true(ArenaGeometry.resolve(p, PlayerData.HURT_RADIUS).is_equal_approx(p), "不在柱子裡：%s" % p)


func test_lethal_execution_kills_after_the_knight_jumps_off() -> void:
	sim.boss.hp = 30  # 失衡那一下（第 1 段 11）之後剩 19，處決（164）打到 0
	var start := _start_execution_from(Vector2(0, 70))
	_advance_to(start, Frames.of(PlayerData.EXECUTE_HIT_TIME))
	assert_eq(boss().hp, 0, "插下去那一刻 HP 歸零")
	assert_eq(boss().state, BS.EXECUTED, "等騎士蹬開、落地才倒下")
	_advance_to(start, Frames.of(PlayerData.EXECUTE_TIME) - 1)
	assert_eq(boss().state, BS.EXECUTED)
	assert_false(logged(&"boss_dead"))
	advance(1)
	assert_eq(boss().state, BS.DEAD, "處決 3 秒結束時死亡")
	assert_true(logged(&"boss_dead"))


func test_no_execution_beyond_48px() -> void:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	sim.player.pos = sim.boss.pos + Vector2(0, VeltharisData.HURT_RADIUS + 50.0)
	press(&"attack")
	assert_eq(player().state, S.ATTACK, "超過 48px：一般攻擊")


func test_execution_frame_counts() -> void:
	assert_eq(Frames.of(PlayerData.EXECUTE_TIME), 180, "處決 3 秒（2026-10-05 使用者：1 秒太快）")
	assert_eq(Frames.of(PlayerData.EXECUTE_LEAP_TIME), 24, "0–0.4 秒衝上前、壓低蓄勢")
	assert_eq(Frames.of(PlayerData.EXECUTE_HIT_TIME), 48, "0.8 秒插下去")
	assert_eq(PlayerData.execute_twist_frames(), [75, 102], "轉劍兩次")
	assert_eq(Frames.of(PlayerData.EXECUTE_KICK_TIME), 120, "2.0 秒蹬開")
	assert_eq(Frames.of(PlayerData.EXECUTE_LAND_TIME), 150, "2.5 秒落地")
	assert_eq(Frames.of(VeltharisData.BREAK_TIME), 180)
	assert_eq(Frames.of(VeltharisData.RISE_TIME), 60)
	assert_eq(roundi(VeltharisData.MAX_HP * VeltharisData.EXECUTE_DAMAGE_RATIO), 164, "1560 × 10.5% = 163.8 → 164（tuning-log）")
