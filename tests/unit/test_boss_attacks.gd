extends SimTestCase
## M3：Boss 出招引擎與訓練木樁（定時出一招可設定的攻擊）。
## boss-veltharis §3：起手期間追蹤玩家，命中前 0.2 秒（12 幀）鎖定方向。

const S := PlayerSim.State
const BS := BossSim.State
const TG := CombatTypes.Telegraph


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = Vector2(0, 30)
	sim.player.facing = Vector2.UP


func _start(id: StringName) -> void:
	sim.boss.start_move(VeltharisData.move(1, id))


## 推進到 Boss 出招的第 f 幀（出招那一幀為第 0 幀）
func _to_move_frame(f: int) -> void:
	while boss().state == BS.ATTACK and boss().state_elapsed() < f:
		advance(1)


func test_sweep_hits_idle_player_on_first_active_frame() -> void:
	_start(&"royal_sweep")
	_to_move_frame(47)
	assert_eq(player().hp, PlayerData.MAX_HP, "起手 0.8 秒（48 幀）內沒有判定")
	advance(1)
	assert_eq(boss().state_elapsed(), 48)
	assert_eq(player().hp, PlayerData.MAX_HP - VeltharisData.move(1, &"royal_sweep").hits[0].damage, "第 48 幀命中")
	assert_eq(player().state, S.LAUNCHED, "王權橫掃：擊飛倒地")


func test_move_ends_after_recovery() -> void:
	_start(&"royal_sweep")
	var total := VeltharisData.move(1, &"royal_sweep").total_frames()
	assert_eq(total, 48 + 9 + 54)
	_to_move_frame(total - 1)
	assert_eq(boss().state, BS.ATTACK)
	advance(1)
	assert_eq(boss().state, BS.IDLE)


func test_direction_locks_12_frames_before_hit() -> void:
	# 鎖定前把玩家移到東側：Boss 轉過來，打中；鎖定後才移過去：打不到（150° 扇形）
	for case in [[34, true], [37, false]]:
		sim = CombatSim.new(1)
		sim.boss.pos = Vector2(0, -40)
		sim.player.pos = Vector2(0, 30)
		_start(&"royal_sweep")
		_to_move_frame(case[0])
		sim.player.pos = Vector2(75, -40)
		_to_move_frame(49)
		assert_eq(player().hp < PlayerData.MAX_HP, case[1], "第 %d 幀移到側面：命中=%s" % [case[0], case[1]])


func test_frame_by_frame_block_injection_against_dummy() -> void:
	# plan M3：逐幀注入格擋。命中前 k 幀按下：k ≤ 8 完美彈返，k ≥ 9 普通格擋
	for k in 13:
		sim = CombatSim.new(1)
		held["block"] = false
		sim.boss.pos = Vector2(0, -40)
		sim.player.pos = Vector2(0, 30)
		sim.player.facing = Vector2.UP
		_start(&"royal_sweep")
		_to_move_frame(48 - k - 1)
		held["block"] = true
		event_log.clear()
		advance(1)  # 在第 48 - k 幀按下
		_to_move_frame(49)
		var result := &"perfect" if logged(&"perfect_parry") else (&"block" if logged(&"block") else &"none")
		assert_eq(result, &"perfect" if k <= 8 else &"block", "命中前 %d 幀按下" % k)
		assert_eq(player().hp, PlayerData.MAX_HP, "格擋都不扣 HP（k=%d）" % k)


func test_perfect_parry_of_finisher_bounces_boss() -> void:
	_start(&"royal_sweep")
	_to_move_frame(44)
	held["block"] = true
	_to_move_frame(49)
	assert_eq(boss().state, BS.BOUNCED, "單發重擊被完美彈返：Boss 彈開")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - VeltharisData.PARRY_TOUGHNESS, 0.001)
	var start := boss().state_start
	while boss().state == BS.BOUNCED:
		advance(1)
	assert_eq(sim.combat_frame - start, Frames.of(1.2), "彈開 1.2 秒")


func test_quick_two_hit_finisher_bounce_is_0_8s() -> void:
	_start(&"quick_combo_2")
	_to_move_frame(55)  # 第二擊在第 60 幀
	held["block"] = false
	advance(1)
	held["block"] = true
	_to_move_frame(61)
	assert_eq(boss().state, BS.BOUNCED)
	var start := boss().state_start
	while boss().state == BS.BOUNCED:
		advance(1)
	assert_eq(sim.combat_frame - start, Frames.of(0.8), "輕擊最後一擊彈開 0.8 秒")


func test_perfect_parry_of_middle_hit_continues_combo() -> void:
	# 雙斬第一擊彈掉：Boss 繼續出第二擊（第 102 幀）
	_start(&"twin_slash")
	_to_move_frame(44)
	held["block"] = true
	_to_move_frame(49)
	assert_eq(boss().state, BS.ATTACK, "連段中間被彈返：繼續出招")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - VeltharisData.PARRY_TOUGHNESS, 0.001)
	held["block"] = false
	_to_move_frame(96)
	held["block"] = true
	_to_move_frame(103)
	assert_eq(boss().state, BS.BOUNCED, "第二擊（最後一擊）被彈返：彈開")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - 2 * VeltharisData.PARRY_TOUGHNESS, 0.001)


func test_knocked_down_player_not_hit_by_rest_of_combo() -> void:
	# 雙斬第一擊打倒玩家，第二擊（0.9 秒後）打不到倒地的玩家 ★7
	_start(&"twin_slash")
	_to_move_frame(49)
	assert_eq(player().state, S.DOWN)
	var hp := player().hp
	_to_move_frame(110)
	assert_eq(player().hp, hp, "倒地無敵，第二擊落空")


func test_delayed_cleave_telegraph_and_timing() -> void:
	_start(&"oath_cleave_delayed")
	var hit_at := Frames.of(1.6)
	_to_move_frame(10)
	assert_eq(boss().telegraph(), TG.NORMAL, "起手：一般預兆")
	_to_move_frame(Frames.of(0.8) + 1)
	assert_eq(boss().telegraph(), TG.DELAYED, "停在最高點：延遲專屬預兆（劍身閃爍）")
	var p0 := boss().pos
	sim.player.pos += Vector2(10, 0)
	_to_move_frame(Frames.of(0.8) + Frames.of(0.6) - 1)
	assert_eq(boss().telegraph(), TG.DELAYED)
	assert_eq(boss().pos, p0, "延遲期間位置靜止 ★8")
	_to_move_frame(hit_at - 1)
	assert_eq(player().hp, PlayerData.MAX_HP)
	_to_move_frame(hit_at)
	assert_true(player().hp < PlayerData.MAX_HP, "總起手 1.6 秒後命中")


func test_ash_impact_danger_telegraph_and_ring() -> void:
	_start(&"ash_impact")
	var hit_at := Frames.of(1.1)
	var danger_from := hit_at - Frames.of(0.6)
	_to_move_frame(danger_from - 1)
	assert_ne_telegraph(TG.DANGER, "危險預兆之前")
	event_log.clear()
	_to_move_frame(danger_from)
	assert_eq(boss().telegraph(), TG.DANGER, "最後 0.6 秒危險預兆")
	assert_true(logged(&"danger"), "危險預兆開始時送出事件（音效）")


func assert_ne_telegraph(t: int, msg: String) -> void:
	assert_true(boss().telegraph() != t, msg)


## §4.6 環擴張到 RING_RADIUS（185，2026-09-30 隨 Boss 放大，原 140）；再遠（加上主角受擊圓半徑 8 之外）打不到
func test_ring_hits_only_when_passing_and_not_beyond_its_radius() -> void:
	var r := VeltharisData.RING_RADIUS
	for case in [[60.0, true], [r - 1.0, true], [r + 20.0, false]]:
		sim = CombatSim.new(1)
		sim.boss.pos = Vector2(0, -40)
		sim.player.pos = sim.boss.pos + Vector2(case[0], 0)
		_start(&"ash_impact")
		_to_move_frame(Frames.of(1.1) + Frames.of(0.2) + 2)
		assert_eq(player().hp < PlayerData.MAX_HP, case[1], "距離 %.0f" % case[0])


func test_ring_can_be_dodged() -> void:
	# ★5：環經過任一點的時間短於閃身無敵，閃身躲得掉
	sim.boss.pos = Vector2(0, -40)
	sim.player.pos = sim.boss.pos + Vector2(0, 80)
	_start(&"ash_impact")
	var hit_at := Frames.of(1.1)
	# 環到達 80px 大約在判定第 6 幀；在那之前 3 幀開始閃身（往側面，保持在環的路徑上）
	_to_move_frame(hit_at + 2)
	move = Vector2.RIGHT
	press(&"dodge")
	move = Vector2.ZERO
	_to_move_frame(hit_at + 14)
	assert_eq(player().hp, PlayerData.MAX_HP, "閃身無敵躲過衝擊環")


## §4.4 突進 LUNGE_DISTANCE（160，2026-09-30 隨 Boss 放大，原 120）
func test_thrust_lunges_full_distance() -> void:
	sim.player.pos = Vector2(300, 150)  # 遠離突刺路徑
	sim.boss.pos = Vector2(-150, 0)
	_start(&"judgment_thrust")
	sim.boss.facing = Vector2.RIGHT
	var x0 := boss().pos.x
	var dir := (sim.player.pos - sim.boss.pos).normalized()
	_to_move_frame(Frames.of(0.6) + Frames.of(0.2))
	assert_near(boss().pos.distance_to(Vector2(x0, 0)), VeltharisData.LUNGE_DISTANCE, 0.5, "突進 %.0fpx" % VeltharisData.LUNGE_DISTANCE)
	assert_true(dir.is_finite())


func test_training_dummy_repeats_configured_move() -> void:
	sim.boss.set_training(&"quick_combo_2", 1.0)
	advance(600)
	var starts := 0
	for e in event_log:
		if e["type"] == &"boss_attack":
			starts += 1
			assert_eq(e["move"], &"quick_combo_2")
	assert_true(starts >= 3, "10 秒內至少出招 3 次（實際 %d）" % starts)


func test_manual_mode_performs_queued_move_once() -> void:
	sim.boss.set_manual()
	advance(60)
	assert_eq(boss().state, BS.IDLE, "手動模式不會自己出招")
	sim.boss.queue_move(&"oath_cleave")
	advance(1)
	assert_eq(boss().state, BS.ATTACK)
	assert_eq(boss().move.id, &"oath_cleave")
	advance(300)
	assert_eq(boss().state, BS.IDLE, "只出一次")


func test_boss_faces_player_while_idle() -> void:
	sim.boss.set_training(&"royal_sweep", 5.0)
	sim.player.pos = Vector2(100, -40)
	advance(2)
	assert_near(boss().facing.angle_to(Vector2.RIGHT), 0.0, 0.01)


func test_delayed_hold_pose_is_static_star8() -> void:
	# ★8：延遲期間維持清楚的靜止姿勢。劍在停住開始時已舉到最高點，停住期間每一幀的姿勢都一樣。
	var BossView: GDScript = load("res://scripts/view/boss_view.gd")
	sim.player.pos = Vector2(0, 30)
	_start(&"oath_cleave_delayed")
	var hold_from := Frames.of(0.8)
	var hold_to := hold_from + Frames.of(0.6)
	_to_move_frame(hold_from)
	var ref: Dictionary = BossView.compute_pose(boss())
	var up_dir: Vector2 = ref["dir"]
	assert_true(up_dir.y < -0.9, "停住時劍在最高點（朝上）：%s" % up_dir)
	while boss().state_elapsed() < hold_to - 1:
		advance(1)
		var pose: Dictionary = BossView.compute_pose(boss())
		assert_eq(boss().telegraph(), TG.DELAYED)
		assert_true((pose["dir"] as Vector2).is_equal_approx(up_dir), "第 %d 幀姿勢改變了" % boss().state_elapsed())
		assert_eq(pose["hand"], ref["hand"])


func test_normal_cleave_reaches_top_before_hit() -> void:
	var BossView: GDScript = load("res://scripts/view/boss_view.gd")
	_start(&"oath_cleave")
	_to_move_frame(Frames.of(1.0) - Frames.of(0.2))
	var d: Vector2 = BossView.compute_pose(boss())["dir"]
	assert_true(d.y < -0.9, "普通版在命中前 0.2 秒舉到最高點")


func test_thrust_lunges_along_locked_direction() -> void:
	sim.boss.pos = Vector2(-150, 0)
	sim.player.pos = Vector2(40, 90)
	_start(&"judgment_thrust")
	var lock_at := Frames.of(0.6) - Frames.of(0.2)
	_to_move_frame(lock_at)
	var dir := boss().facing
	var p0 := boss().pos
	sim.player.pos = Vector2(-150, 150)  # 鎖定後玩家移開，突刺方向不變
	_to_move_frame(Frames.of(0.6) + Frames.of(0.2))
	var moved := boss().pos - p0
	assert_near(moved.length(), VeltharisData.LUNGE_DISTANCE, 0.5)
	assert_near(moved.normalized().angle_to(dir), 0.0, 0.01, "沿鎖定的方向突進")


func test_delayed_hold_pose_does_not_flip_when_player_crosses() -> void:
	var BossView: GDScript = load("res://scripts/view/boss_view.gd")
	sim.player.pos = Vector2(30, 30)
	_start(&"oath_cleave_delayed")
	_to_move_frame(Frames.of(0.8) + 1)
	var ref: Dictionary = BossView.compute_pose(boss())
	sim.player.pos = Vector2(-30, 30)  # 玩家繞到另一側
	_to_move_frame(Frames.of(0.8) + 20)
	var pose: Dictionary = BossView.compute_pose(boss())
	assert_true((pose["dir"] as Vector2).is_equal_approx(ref["dir"]), "停住期間不翻面")
	assert_eq(pose["hand"], ref["hand"])


## 雙斬第二刀左腳直接往前踏（2026-10-01 使用者：「揮第二下左腳直接向前踏好了，右腳不要收回了，這樣的代價是
## boss 揮兩劍會前進一點，我接受，遊戲裡也要改」）：命中前 TWIN_STEP_TIME 秒內，沿鎖定的方向前進
## TWIN_STEP_DISTANCE；判定開始時已經踏完，判定期間位置不動（被完美彈返時，彈開的動畫從砍到的位置接上）
func _assert_second_hit_steps(m: BossMoveData) -> void:
	sim.boss.pos = Vector2(-150, 0)
	sim.player.pos = Vector2(300, 150)  # 遠離 Boss 的路徑
	sim.boss.start_move(m)
	var start2 := boss().hit_start_frame(1)
	var step_from := start2 - Frames.of(VeltharisData.TWIN_STEP_TIME)
	# _to_move_frame(f) 之後第 f 幀已經跑完：p0 是踏步開始前一幀的位置
	_to_move_frame(step_from - 1)
	var dir := boss().facing
	var p0 := boss().pos
	sim.player.pos = Vector2(-300, 150)  # 鎖定後玩家移開：踏步方向不變
	_to_move_frame(start2 - 2)
	assert_true(boss().pos.distance_to(p0) < VeltharisData.TWIN_STEP_DISTANCE - 0.5, "%s：踏步在判定前持續進行" % m.id)
	_to_move_frame(start2 - 1)
	var moved := boss().pos - p0
	assert_near(moved.length(), VeltharisData.TWIN_STEP_DISTANCE, 0.5,
		"%s：第二刀前踏 %.0fpx，判定開始前踏完" % [m.id, VeltharisData.TWIN_STEP_DISTANCE])
	assert_near(moved.normalized().angle_to(dir), 0.0, 0.01, "%s：沿鎖定的方向踏" % m.id)
	var p1 := boss().pos
	_to_move_frame(start2 + Frames.of(m.hits[1].active) - 1)
	assert_true(boss().pos.is_equal_approx(p1), "%s：判定期間位置不動" % m.id)


func test_twin_second_hit_steps_forward_before_its_hit_box() -> void:
	_assert_second_hit_steps(VeltharisData.move(1, &"twin_slash"))


func test_triple_slash_second_hit_steps_forward_too() -> void:
	_assert_second_hit_steps(VeltharisData.move(2, &"triple_slash"))


func test_twin_first_hit_does_not_step() -> void:
	sim.boss.pos = Vector2(-150, 0)
	sim.player.pos = Vector2(300, 150)
	_start(&"twin_slash")
	var start1 := boss().hit_start_frame(0)
	_to_move_frame(start1 - Frames.of(0.2))  # 鎖定之後不再逼近
	var p0 := boss().pos
	_to_move_frame(start1 + Frames.of(0.1) - 1)  # 到第一刀判定結束（之後是第二刀的起手，照常逼近）
	assert_true(boss().pos.is_equal_approx(p0), "第一刀原地（右腳踏出是畫面上的動作，位置不動）")
