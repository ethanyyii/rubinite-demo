extends SimTestCase
## M3：combat-design §6 格擋與彈返、§4 架勢。
## 完美窗口：按下後 9 幀內（第 0–8 幀）被擊中；放開後 18 幀內再按只算普通格擋。

const S := PlayerSim.State
const R := CombatSim.BlockResult


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = Vector2(0, 30)
	sim.player.facing = Vector2.UP


func _heavy() -> BossHitData:
	return VeltharisData.move(1, &"royal_sweep").hits[0]


func _heavy_mid() -> BossHitData:
	return VeltharisData.move(1, &"twin_slash").hits[0]


func _light_mid() -> BossHitData:
	return VeltharisData.move(1, &"quick_combo_3").hits[0]


func _light_last() -> BossHitData:
	return VeltharisData.move(1, &"quick_combo_2").hits[1]


func _unblockable() -> BossHitData:
	return VeltharisData.move(1, &"ash_impact").hits[0]


## 按住格擋 k 幀後被擊中（按下那一幀算第 0 幀）
func _block_then_hit(k: int, hit: BossHitData) -> int:
	held["block"] = true
	advance(1)
	for i in k:
		advance(1)
	return sim.apply_boss_hit(hit, sim.boss.pos)


func test_frames() -> void:
	assert_eq(Frames.of(PlayerData.PERFECT_WINDOW), 9)
	assert_eq(Frames.of(PlayerData.REARM_TIME), 18)


func test_block_starts_on_press_frame() -> void:
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK, "按下同一幀生效")


func test_perfect_window_boundaries() -> void:
	for k in 13:
		sim = CombatSim.new(1)
		before_each_positions()
		held["block"] = false
		var r := _block_then_hit(k, _heavy_mid())
		assert_eq(r, R.PERFECT if k <= 8 else R.BLOCKED, "按下後第 %d 幀被擊中" % k)


func before_each_positions() -> void:
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = Vector2(0, 30)
	sim.player.facing = Vector2.UP


func test_press_on_hit_frame_is_perfect() -> void:
	held["block"] = true
	advance(1)
	# 同一幀：先處理玩家輸入再判定，所以直接走完整管線
	assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), R.PERFECT)


func test_rearm_within_18_frames_is_normal_block() -> void:
	# 按 → 放開 → 17 幀後再按：普通格擋；18 幀後再按：完美
	for case in [[17, R.BLOCKED], [18, R.PERFECT]]:
		sim = CombatSim.new(1)
		before_each_positions()
		held["block"] = true
		advance(3)
		held["block"] = false
		advance(1)  # 放開的那一幀
		advance(case[0] - 1)
		held["block"] = true
		advance(1)  # 放開後第 case[0] 幀按下
		assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), case[1], "放開後 %d 幀再按" % case[0])


func test_holding_block_after_window_is_normal() -> void:
	var r := _block_then_hit(30, _heavy_mid())
	assert_eq(r, R.BLOCKED)


func test_normal_block_costs_posture_not_hp() -> void:
	var r := _block_then_hit(20, _heavy_mid())
	assert_eq(r, R.BLOCKED)
	assert_eq(player().hp, PlayerData.MAX_HP, "普通格擋不扣 HP")
	assert_near(player().posture, PlayerData.MAX_POSTURE - 35, 0.001, "重擊扣架勢 35")
	sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_near(player().posture, PlayerData.MAX_POSTURE - 35 - 20, 0.001, "輕擊扣架勢 20")


func test_normal_block_pushback_8px() -> void:
	var y0 := sim.player.pos.y
	_block_then_hit(20, _heavy_mid())
	advance(10)
	assert_near(sim.player.pos.y - y0, PlayerData.BLOCK_PUSHBACK, 0.01, "被推後 8px（遠離攻擊者）")
	assert_eq(player().state, S.BLOCK, "推後期間仍在格擋")


func test_perfect_parry_costs_nothing_and_breaks_toughness() -> void:
	var r := _block_then_hit(4, _heavy_mid())
	assert_eq(r, R.PERFECT)
	assert_eq(player().hp, PlayerData.MAX_HP)
	assert_near(player().posture, PlayerData.MAX_POSTURE, 0.001, "完美彈返不扣架勢")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - VeltharisData.PARRY_TOUGHNESS, 0.001, "重擊中間：削韌 20（tuning-log：26）")
	sim = CombatSim.new(1)
	before_each_positions()
	held["block"] = false
	_block_then_hit(4, _light_mid())
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - VeltharisData.PARRY_TOUGHNESS_LIGHT_MID, 0.001, "輕擊中間：削韌 12（tuning-log：15）")
	sim = CombatSim.new(1)
	before_each_positions()
	held["block"] = false
	_block_then_hit(4, _light_last())
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - VeltharisData.PARRY_TOUGHNESS, 0.001, "輕擊最後一擊：削韌 20（tuning-log：26）")


func test_perfect_parry_feedback_vs_normal_block() -> void:
	# §6：完美彈返頓幀 0.08 秒（5 幀）、震動 3px 0.1 秒；普通格擋無頓幀、無震動
	_block_then_hit(4, _heavy_mid())
	assert_eq(sim.hitstop, 5, "完美彈返頓幀 5 幀")
	var fb := _find_event(&"feedback")
	assert_eq(fb.get("event"), &"perfect_parry")
	assert_near(fb.get("shake", 0.0), 3.0, 0.001)
	assert_near(fb.get("shake_time", 0.0), 0.1, 0.001)
	assert_false(_find_event(&"perfect_parry").is_empty(), "送出彈返事件（火花、音效）")
	sim = CombatSim.new(1)
	before_each_positions()
	held["block"] = false
	_block_then_hit(20, _heavy_mid())
	assert_eq(sim.hitstop, 0, "普通格擋沒有頓幀")
	assert_true(_find_event(&"feedback").is_empty() or _find_event(&"feedback").get("shake", 0.0) == 0.0, "普通格擋沒有震動")
	assert_false(_find_event(&"block").is_empty(), "送出普通格擋事件（火星、刮擦聲）")


func _find_event(type: StringName) -> Dictionary:
	for e in sim.events:
		if e["type"] == type:
			return e
	return {}


func test_block_arc_is_front_180() -> void:
	# 面向上；攻擊來自正右側（90°）擋得住，偏後 5° 擋不住
	for case in [[Vector2(70, 0), R.BLOCKED], [Vector2(70, 6), R.HIT], [Vector2(0, -70), R.BLOCKED], [Vector2(0, 70), R.HIT]]:
		sim = CombatSim.new(1)
		sim.player.pos = Vector2(0, 30)
		sim.player.facing = Vector2.UP
		sim.boss.pos = sim.player.pos + case[0]
		held["block"] = true
		advance(20)
		sim.player.facing = Vector2.UP
		assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), case[1], "攻擊來自 %s" % case[0])
		held["block"] = false


func test_unblockable_ignores_block_and_parry() -> void:
	var r := _block_then_hit(3, _unblockable())
	assert_eq(r, R.HIT, "不可格擋攻擊：格擋無效")
	assert_eq(player().hp, PlayerData.MAX_HP - _unblockable().damage)


func test_posture_regen_after_1s_at_20_per_sec() -> void:
	_block_then_hit(20, _heavy_mid())
	var p0 := player().posture
	advance(59)
	assert_near(player().posture, p0, 0.001, "1 秒內不回復")
	advance(60)
	assert_near(player().posture, p0 + 20.0, 0.05, "之後每秒回 20")


func test_posture_break_at_zero() -> void:
	held["block"] = true
	advance(20)
	for i in 2:
		sim.apply_boss_hit(_heavy_mid(), sim.boss.pos)
	assert_eq(player().state, S.BLOCK, "兩次重擊普通格擋後剩 30")
	assert_near(player().posture, 30.0, 0.001)
	sim.player.posture = 10.0
	sim.apply_boss_hit(_heavy_mid(), sim.boss.pos)
	assert_eq(player().state, S.POSTURE_BREAK, "架勢歸零即崩潰")
	assert_eq(player().hp, PlayerData.MAX_HP, "崩潰的那一擊不扣 HP")
	# 崩潰 1.2 秒（72 幀）不能做任何動作
	held["block"] = false
	for i in 71:
		advance(1, [&"attack"] if i % 3 == 0 and i < 50 else [])
		assert_eq(player().state, S.POSTURE_BREAK, "第 %d 幀仍崩潰" % (i + 1))
	advance(1)
	assert_eq(player().state, S.IDLE, "72 幀後恢復")
	assert_near(player().posture, PlayerData.MAX_POSTURE, 0.001, "恢復後架勢回滿")


func test_hit_during_posture_break_knocks_down() -> void:
	sim.player.posture = 5.0
	held["block"] = true
	advance(20)
	sim.apply_boss_hit(_heavy_mid(), sim.boss.pos)
	assert_eq(player().state, S.POSTURE_BREAK)
	held["block"] = false
	advance(5)
	sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_eq(player().state, S.DOWN, "崩潰中被輕擊打中也倒地")
	sim = CombatSim.new(1)
	before_each_positions()
	sim.player.posture = 5.0
	held["block"] = true
	advance(20)
	sim.apply_boss_hit(_heavy_mid(), sim.boss.pos)
	held["block"] = false
	advance(5)
	sim.apply_boss_hit(_heavy(), sim.boss.pos)
	assert_eq(player().state, S.LAUNCHED, "崩潰中被帶擊飛的重擊打中：擊飛倒地")


func test_block_is_not_buffered() -> void:
	# 輕攻擊起手中按下格擋並一直按住：到取消點才進入格擋，但沒有完美窗口
	place_near_boss(50.0)
	press(&"attack")
	held["block"] = true
	var cancel_at := PlayerData.light_attacks()[0].active_end_frame() + Frames.of(PlayerData.CANCEL_DELAY)
	while player().state == S.ATTACK:
		advance(1)
	assert_eq(player().state, S.BLOCK)
	assert_eq(player().state_elapsed(), 0)
	assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), R.BLOCKED, "起手中按下的格擋不開完美窗口（格擋不緩衝）")
	assert_eq(PlayerData.light_attacks()[0].active_end_frame() + 3, cancel_at)


func test_block_press_in_recovery_after_cancel_point_is_perfect() -> void:
	place_near_boss(50.0)
	press(&"attack")
	var cancel_at := PlayerData.light_attacks()[0].active_end_frame() + Frames.of(PlayerData.CANCEL_DELAY)
	while player().state_elapsed() < cancel_at - 1:
		advance(1)
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK, "取消點按下格擋：立即格擋")
	assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), R.PERFECT)


func test_entering_block_clears_buffer_and_has_priority() -> void:
	# 閃身中按攻擊（緩衝）並按住格擋：閃身結束時進入格擋（按住的格擋優先），緩衝被清掉
	press(&"dodge")
	advance(11)
	tick([&"attack"])
	held["block"] = true
	while player().state == S.DODGE:
		advance(1)
	assert_eq(player().state, S.BLOCK)
	assert_eq(player().buffered_action, &"", "進入格擋清掉緩衝")
	held["block"] = false
	advance(1)
	assert_eq(player().state, S.IDLE, "放開格擋回到待機，不會冒出之前緩衝的攻擊")


func test_block_cancels_charge() -> void:
	press(&"heavy")
	advance(60)
	assert_true(player().charge_full)
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK, "格擋可以取消蓄力")
	assert_false(player().charge_full)


func test_cannot_block_during_stage4_or_thrust_or_dodge() -> void:
	press(&"dodge")
	held["block"] = true
	advance(3)
	assert_eq(player().state, S.DODGE, "閃身中不能格擋")
	# 第 4 段
	sim = CombatSim.new(1)
	held["block"] = false
	place_near_boss(50.0)
	press(&"attack")
	for i in 3:
		while player().state_elapsed() < PlayerData.chain_frame(i):
			advance(1)
		press(&"attack")
	assert_eq(player().combo_index, 3)
	held["block"] = true
	while player().state == S.ATTACK and player().state_elapsed() < player().attack.recovery_end_frame() - 1:
		advance(1)
		assert_eq(player().state, S.ATTACK, "第 4 段起手到收招結束都不能用格擋取消")
	advance(1)
	assert_eq(player().state, S.BLOCK, "收招後的停頓（§8.1）可以格擋")
	# 突刺
	sim = CombatSim.new(1)
	held["block"] = false
	place_near_boss(100.0)
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	advance(1)
	assert_eq(player().state, S.THRUST)
	held["block"] = true
	for i in 30:
		advance(1)
		assert_eq(player().state, S.THRUST, "突刺全程不能用格擋取消")


func test_block_speed_50() -> void:
	sim.boss.pos = Vector2(0, -170)
	held["block"] = true
	move = Vector2.RIGHT
	advance(20)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_BLOCK, 0.001)


func test_consecutive_normal_blocks_counted() -> void:
	held["block"] = true
	advance(20)
	for i in 3:
		sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_eq(boss().ai.block_streak, 3, "連續普通格擋 3 次（AI 規則 3 用）")
	held["block"] = false
	advance(20)
	held["block"] = true
	advance(1)
	sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_eq(boss().ai.block_streak, 0, "完美彈返重置")
	held["block"] = false
	advance(20)
	held["block"] = true
	advance(20)
	sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_eq(boss().ai.block_streak, 1)
	held["block"] = false
	advance(1)
	sim.apply_boss_hit(_light_mid(), sim.boss.pos)
	assert_eq(boss().ai.block_streak, 0, "被打中重置")


func test_rearm_cannot_be_bypassed_during_parry_hitstop() -> void:
	# ★ 重新開窗：完美彈返的頓幀中放開再按下，恢復後只算普通格擋
	var r := _block_then_hit(3, _heavy_mid())
	assert_eq(r, R.PERFECT)
	assert_true(sim.hitstop >= 3)
	var rel := make_input()
	rel.block = false
	rel.block_released = true
	sim.step(rel)
	var pr := make_input()
	pr.block = true
	pr.block_pressed = true
	sim.step(pr)
	while sim.hitstop > 0:
		sim.step(make_input())
	advance(1)
	assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), R.BLOCKED, "頓幀中放開再按不能繞過 0.3 秒重新開窗")


func test_tap_during_hitstop_registers_release() -> void:
	# 頓幀中點按（按下又放開）：恢復後再按也要等 18 幀才有完美窗口
	held["block"] = false
	press(&"attack")
	place_near_boss(50.0)
	advance(6)
	assert_true(sim.hitstop > 0)
	var tap := make_input()
	tap.block = false
	tap.block_pressed = true
	tap.block_released = true
	sim.step(tap)
	while sim.hitstop > 0:
		sim.step(make_input())
	advance(10)
	held["block"] = true
	advance(1)  # 點按後 11 幀再按：未滿 18 幀
	assert_false(player().block_press_perfect, "點按的放開也算在重新開窗內")


func test_press_release_press_in_one_merged_frame_is_not_perfect() -> void:
	# 待機中遇到頓幀（例如 M4 的失衡頓幀），頓幀中按、放、按：恢復後進入格擋，但只算普通格擋
	advance(5)
	sim.hitstop = 5
	var f1 := make_input()
	f1.block = true
	f1.block_pressed = true
	sim.step(f1)
	var f2 := make_input()
	f2.block = false
	f2.block_released = true
	sim.step(f2)
	var f3 := make_input()
	f3.block = true
	f3.block_pressed = true
	sim.step(f3)
	held["block"] = true
	while sim.hitstop > 0:
		tick()
	advance(1)
	assert_eq(player().state, S.BLOCK)
	assert_false(player().block_press_perfect, "頓幀中按放按：不開完美窗口")
	assert_eq(sim.apply_boss_hit(_heavy_mid(), sim.boss.pos), R.BLOCKED)
