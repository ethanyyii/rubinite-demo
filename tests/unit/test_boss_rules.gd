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
	assert_near(boss().toughness, 50.0, 0.001, "2 秒內不回復")
	advance(60)
	assert_near(boss().toughness, 60.0, 0.05, "滿血時每秒回 10")
	sim = CombatSim.new(1)
	sim.boss.hp = roundi(VeltharisData.MAX_HP * 0.5)
	sim.boss.toughness = 50.0
	sim.boss.last_toughness_damage = sim.combat_frame
	advance(Frames.of(VeltharisData.TOUGHNESS_REGEN_DELAY) - 1)
	advance(60)
	assert_near(boss().toughness, 50.0 + 10.0 * (0.3 + 0.7 * 0.5), 0.05, "半血時每秒回 6.5")


func test_break_at_zero_toughness() -> void:
	sim.boss.toughness = 2.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	assert_eq(boss().state, BS.BROKEN, "韌性歸零：失衡")
	assert_eq(sim.hitstop, Frames.of(0.15), "失衡頓幀 0.15 秒")
	advance(Frames.of(VeltharisData.BREAK_TIME) - 1)
	assert_eq(boss().state, BS.BROKEN, "失衡 3 秒")
	advance(1)
	assert_true(boss().state != BS.BROKEN, "3 秒沒有處決：自行恢復")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS, 0.001, "韌性回滿")


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
	advance(Frames.of(PlayerData.EXECUTE_HIT_TIME))
	assert_eq(boss().hp, hp0 - roundi(VeltharisData.MAX_HP * 0.15), "處決傷害為最大 HP 的 15%")
	assert_eq(sim.hitstop, Frames.of(0.25), "處決頓幀 0.25 秒")
	while player().state == S.EXECUTE:
		assert_true(player().is_invulnerable())
		advance(1)
	assert_eq(sim.combat_frame - player().state_start, 0)
	assert_eq(boss().state, BS.RISING, "處決後 Boss 起身")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS, 0.001, "韌性回滿")
	var rise_start := boss().state_start
	sim.boss.receive_player_hit(_stage4())
	assert_eq(boss().state, BS.RISING, "起身期間霸體（不會短僵直）")
	while boss().state == BS.RISING:
		advance(1)
	assert_eq(sim.combat_frame - rise_start, Frames.of(VeltharisData.RISE_TIME), "起身 1 秒")


func test_no_execution_beyond_48px() -> void:
	sim.boss.toughness = 1.0
	sim.boss.receive_player_hit(PlayerData.light_attacks()[0])
	sim.player.pos = sim.boss.pos + Vector2(0, VeltharisData.HURT_RADIUS + 50.0)
	press(&"attack")
	assert_eq(player().state, S.ATTACK, "超過 48px：一般攻擊")


func test_execution_frame_counts() -> void:
	assert_eq(Frames.of(PlayerData.EXECUTE_TIME), 60)
	assert_eq(Frames.of(VeltharisData.BREAK_TIME), 180)
	assert_eq(Frames.of(VeltharisData.RISE_TIME), 60)
	assert_eq(roundi(VeltharisData.MAX_HP * VeltharisData.EXECUTE_DAMAGE_RATIO), 180)
