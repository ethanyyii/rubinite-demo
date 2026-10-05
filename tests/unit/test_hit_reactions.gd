extends SimTestCase
## M3：combat-design §10 受擊反應與倒地無敵 ★、§4 治療。

const S := PlayerSim.State
const R := CombatSim.BlockResult


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -60)
	sim.player.pos = Vector2(0, 20)
	sim.player.facing = Vector2.UP


func _light() -> BossHitData:
	return VeltharisData.move(1, &"quick_combo_3").hits[0]


func _knockdown() -> BossHitData:
	return VeltharisData.move(1, &"oath_cleave").hits[0]


func _launch() -> BossHitData:
	return VeltharisData.move(1, &"royal_sweep").hits[0]


func _hit(h: BossHitData) -> int:
	return sim.apply_boss_hit(h, sim.boss.pos)


func test_frames() -> void:
	assert_eq(Frames.of(PlayerData.STAGGER_TIME), 21)
	assert_eq(Frames.of(PlayerData.KNOCKDOWN_DOWN), 48)
	assert_eq(Frames.of(PlayerData.LAUNCH_TIME), 21)
	assert_eq(Frames.of(PlayerData.LAUNCH_DOWN), 36)
	assert_eq(Frames.of(PlayerData.GETUP_TIME), 30)
	assert_eq(Frames.of(PlayerData.POSTURE_BREAK_TIME), 72)
	assert_eq(Frames.of(PlayerData.DOWN_INVULN_AFTER_GETUP), 18)


func test_light_hit_staggers() -> void:
	var y0 := sim.player.pos.y
	assert_eq(_hit(_light()), R.HIT)
	assert_eq(player().hp, PlayerData.MAX_HP - _light().damage)
	assert_eq(player().state, S.STAGGER)
	assert_eq(sim.hitstop, Frames.of(0.06), "踉蹌頓幀 0.06 秒")
	advance(20)
	assert_eq(player().state, S.STAGGER, "硬直 0.35 秒")
	assert_near(sim.player.pos.y - y0, PlayerData.STAGGER_KNOCKBACK, 0.01, "擊退 12px")
	advance(1)
	assert_eq(player().state, S.IDLE, "21 幀後可以行動")
	assert_false(player().is_invulnerable(), "踉蹌沒有無敵")


func test_stagger_can_be_hit_again() -> void:
	_hit(_light())
	advance(5)
	assert_eq(_hit(_light()), R.HIT, "踉蹌中可以再被打中")
	assert_eq(player().hp, PlayerData.MAX_HP - 2 * _light().damage)


func test_knockdown_timeline_and_invulnerability() -> void:
	var y0 := sim.player.pos.y
	assert_eq(_hit(_knockdown()), R.HIT)
	assert_eq(player().hp, PlayerData.MAX_HP - _knockdown().damage)
	assert_eq(player().state, S.DOWN)
	assert_eq(sim.hitstop, Frames.of(0.08), "倒地頓幀 0.08 秒")
	assert_true(player().is_invulnerable(), "倒地瞬間起無敵 ★")
	advance(47)
	assert_eq(player().state, S.DOWN)
	assert_near(sim.player.pos.y - y0, PlayerData.KNOCKDOWN_KNOCKBACK, 0.01, "擊退 24px")
	advance(1)
	assert_eq(player().state, S.GETUP, "倒地 0.8 秒後起身")
	advance(29)
	assert_eq(player().state, S.GETUP)
	assert_true(player().is_invulnerable())
	advance(1)
	assert_eq(player().state, S.IDLE, "起身 0.5 秒")
	for i in 18:
		assert_true(player().is_invulnerable(), "起身後第 %d 幀仍無敵（0.3 秒）★" % i)
		advance(1)
	assert_false(player().is_invulnerable(), "起身 0.3 秒後解除無敵")


func test_launch_timeline() -> void:
	var y0 := sim.player.pos.y
	_hit(_launch())
	assert_eq(player().state, S.LAUNCHED)
	assert_eq(player().hp, PlayerData.MAX_HP - _launch().damage)
	advance(20)
	assert_eq(player().state, S.LAUNCHED)
	assert_near(sim.player.pos.y - y0, PlayerData.LAUNCH_DISTANCE, 0.01, "0.35 秒飛出 64px")
	advance(1)
	assert_eq(player().state, S.DOWN)
	advance(36)
	assert_eq(player().state, S.GETUP, "倒地 0.6 秒")
	advance(30)
	assert_eq(player().state, S.IDLE, "起身 0.5 秒")


func test_down_player_cannot_be_hit_star7() -> void:
	# ★7：倒地全程無敵，Boss 不能追打倒地的玩家
	_hit(_launch())
	var hp := player().hp
	for i in 21 + 36 + 30 + 18:
		assert_eq(_hit(_light()), R.MISS, "倒地流程第 %d 幀不會被打中" % i)
		advance(1)
	assert_eq(player().hp, hp)
	assert_eq(_hit(_light()), R.HIT, "無敵結束後可以被打中")


func test_hit_clears_buffer_combo_and_charge() -> void:
	press(&"heavy")
	advance(60)
	assert_true(player().charge_full)
	tick([&"attack"])  # 蓄力中按攻擊：進入緩衝
	assert_eq(player().buffered_action, &"attack")
	_hit(_light())
	assert_false(player().charge_full, "受擊清掉蓄力")
	assert_eq(player().buffered_action, &"", "受擊清掉緩衝")
	assert_eq(player().combo_index, 0)


func test_death_at_zero_hp() -> void:
	sim.player.hp = 10
	_hit(_light())
	assert_eq(player().hp, 0)
	assert_eq(player().state, S.DEAD)
	var got_hit_event := false
	for e in sim.events:
		if e["type"] == &"player_hit":
			got_hit_event = true
	assert_true(got_hit_event, "致命一擊也送出受擊事件（紅閃、音效）")
	assert_eq(_hit(_light()), R.MISS, "死亡後不再受擊")


func test_posture_break_stops_movement() -> void:
	held["block"] = true
	move = Vector2.UP  # 往 Boss 的方向（未鎖定時格擋面向舉劍時的推桿方向）
	advance(20)
	assert_true(sim.player.vel.length() > 0.0)
	sim.player.posture = 5.0
	sim.apply_boss_hit(VeltharisData.move(1, &"twin_slash").hits[0], sim.boss.pos)
	assert_eq(player().state, S.POSTURE_BREAK)
	assert_eq(sim.player.vel, Vector2.ZERO, "崩潰時速度歸零")


func test_god_mode_ignores_hits() -> void:
	sim.god_mode = true
	assert_eq(_hit(_launch()), R.MISS)
	assert_eq(player().hp, PlayerData.MAX_HP)


# --- 治療（§4） -------------------------------------------------------------------

func test_heal_takes_heal_time_restores_amount_and_consumes_charge() -> void:
	sim.player.hp = 20
	press(&"heal")
	assert_eq(player().state, S.HEAL)
	assert_eq(player().heals, PlayerData.HEAL_CHARGES - 1, "開始時就消耗一次")
	var n := Frames.of(PlayerData.HEAL_TIME)
	assert_eq(n, 70, "1.17 秒 = 70.2 幀 → 70（tuning-log：文件 0.9 秒 = 54 幀）")
	advance(n - 1)
	assert_eq(player().hp, 20, "治療時間結束時才回血")
	assert_eq(player().state, S.HEAL)
	advance(1)
	assert_eq(player().hp, 20 + 43, "最後一幀回最大 HP 的五分之三：43（2026-10-05；文件原本 35、調過 25）")
	assert_eq(player().state, S.IDLE)


func test_heal_does_not_go_over_max_hp() -> void:
	sim.player.hp = 40
	press(&"heal")
	advance(Frames.of(PlayerData.HEAL_TIME))
	assert_eq(player().hp, PlayerData.MAX_HP, "40 + 43 超過最大 HP：補滿為止")


func test_heal_caps_at_max_hp() -> void:
	sim.player.hp = PlayerData.MAX_HP - 10
	press(&"heal")
	advance(Frames.of(PlayerData.HEAL_TIME) + 5)
	assert_eq(player().hp, PlayerData.MAX_HP)


func test_heal_cannot_be_cancelled_and_moves_slowly() -> void:
	sim.player.hp = 50
	press(&"heal")
	move = Vector2.RIGHT
	held["run"] = true
	advance(10)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_HEAL, 0.001, "治療中移速 30")
	press(&"dodge")
	assert_eq(player().state, S.HEAL, "不能用閃身取消")
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.HEAL, "不能用格擋取消")
	press(&"attack")
	assert_eq(player().state, S.HEAL, "不能用攻擊取消")


func test_heal_interrupted_by_hit_loses_charge() -> void:
	sim.player.hp = 50
	press(&"heal")
	advance(20)
	_hit(_light())
	assert_eq(player().state, S.STAGGER)
	assert_eq(player().heals, PlayerData.HEAL_CHARGES - 1, "被打斷時次數已消耗")
	advance(60)
	assert_eq(player().hp, 50 - _light().damage, "被打斷不回血")


func test_no_heal_without_charges() -> void:
	sim.player.heals = 0
	sim.player.hp = 50
	press(&"heal")
	assert_eq(player().state, S.IDLE)


func test_heal_only_from_free_states() -> void:
	press(&"attack")
	press(&"heal")
	assert_eq(player().state, S.ATTACK, "攻擊中不能治療")
