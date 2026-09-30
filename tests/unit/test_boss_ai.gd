extends SimTestCase
## M4：boss-veltharis §6 AI 規則。

const BS := BossSim.State
const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	sim.boss.set_ai()
	sim.boss.pos = Vector2(0, -20)
	sim.player.pos = Vector2(0, 60)
	sim.player.facing = Vector2.UP


func _started_moves() -> Array[StringName]:
	var out: Array[StringName] = []
	for e in event_log:
		if e["type"] == &"boss_attack":
			out.append(e["move"])
	return out


## ★2 規則 1：玩家架勢崩潰時立即使用裁決突刺，從崩潰到命中不超過 1.1 秒
func test_posture_break_triggers_punish_thrust_within_1_1s() -> void:
	for seed_value in 12:
		sim = CombatSim.new(seed_value + 100)
		sim.boss.set_ai()
		sim.boss.pos = Vector2(0, -20)
		sim.player.pos = Vector2(0, 50)
		press(&"lock")
		held["block"] = true
		# 等 Boss 出第一招，在第一擊命中前一刻讓架勢歸零
		var guard := 0
		while guard < 1200:
			guard += 1
			advance(1)
			if boss().state == BS.ATTACK and boss().current_hit_index() >= 0:
				var i := boss().current_hit_index()
				var h: BossHitData = boss().move.hits[i]
				if h.is_blockable() and boss().hit_start_frame(i) - boss().state_elapsed() == 1:
					sim.player.posture = 1.0
					break
		event_log.clear()
		advance(1)
		if player().state != S.POSTURE_BREAK:
			# 這一招可能打不到（距離），換下一個種子
			held["block"] = false
			continue
		var broke_at := sim.combat_frame
		held["block"] = false
		var hit_at := -1
		while sim.combat_frame - broke_at <= 80:
			advance(1)
			for e in event_log:
				if e["type"] == &"player_hit" and hit_at < 0:
					hit_at = sim.combat_frame
			if hit_at >= 0:
				break
		var moves := _started_moves()
		assert_true(&"judgment_thrust" in moves, "種子 %d：崩潰後使用裁決突刺（實際 %s）" % [seed_value, moves])
		assert_true(hit_at >= 0, "種子 %d：懲罰技命中" % seed_value)
		assert_true(hit_at - broke_at <= Frames.of(1.1), "種子 %d：%d 幀命中（上限 66）★2" % [seed_value, hit_at - broke_at])
		assert_true(hit_at - broke_at < Frames.of(PlayerData.POSTURE_BREAK_TIME), "在崩潰硬直結束前命中")
		held["block"] = false


## 規則 3：玩家連續普通格擋 3 次後，下一招優先使用灰燼衝擊
func test_three_normal_blocks_then_ash_impact() -> void:
	var ok := 0
	for seed_value in 8:
		sim = CombatSim.new(seed_value + 7)
		sim.boss.set_ai()
		sim.boss.pos = Vector2(0, -20)
		sim.player.pos = Vector2(0, 50)
		sim.player.posture = 10000.0  # 只看 AI 反應，不讓架勢崩潰
		press(&"lock")  # 鎖定：Boss 喘息時繞著玩家走，格擋要一直朝向它
		held["block"] = true
		event_log.clear()
		var guard := 0
		# 等到「連續」普通格擋 3 次（中間被打中或完美彈返會歸零）
		while boss().ai.block_streak < 3 and guard < 5000:
			guard += 1
			advance(1)
			sim.player.posture = 10000.0
			sim.player.hp = PlayerData.MAX_HP  # 被灰燼衝擊打中也不會死
		assert_true(boss().ai.block_streak >= 3, "種子 %d：連續普通格擋到 3 次" % seed_value)
		# 等目前這一招結束，看下一招
		var n_before := _started_moves().size()
		while _started_moves().size() == n_before and guard < 5000:
			guard += 1
			advance(1)
			sim.player.posture = 10000.0
			sim.player.hp = PlayerData.MAX_HP  # 被灰燼衝擊打中也不會死
		var next: StringName = _started_moves()[-1]
		assert_eq(next, &"ash_impact", "種子 %d：連續普通格擋 3 次後的下一招" % seed_value)
		if next == &"ash_impact":
			ok += 1
	assert_eq(ok, 8)


## 規則 4：同一招不會連續使用超過 2 次（以招式群組計，延遲版與普通版算同一招）
func test_same_move_not_more_than_twice_in_a_row() -> void:
	sim.god_mode = true
	advance(60 * 180)
	var groups: Array[StringName] = []
	for m in _started_moves():
		groups.append(VeltharisData.group_of(m))
	assert_true(groups.size() > 40, "3 分鐘內出招 %d 次" % groups.size())
	for i in range(2, groups.size()):
		assert_false(groups[i] == groups[i - 1] and groups[i] == groups[i - 2], "第 %d 招 %s 連續第 3 次" % [i, groups[i]])


## 規則 2：玩家在 HEAL_PUNISH_RANGE（345，原 260）內治療時，70% 機率立刻懲罰（一階段裁決突刺）
func test_heal_punish_rate_about_70_percent() -> void:
	var trials := 120
	var punished := 0
	for t in trials:
		sim = CombatSim.new(1000 + t)
		sim.boss.set_ai()
		sim.boss.pos = Vector2(0, -60)
		sim.player.pos = Vector2(0, 120)  # 180px：中距離
		sim.player.hp = 50
		sim.boss.start_breather(120)
		event_log.clear()
		press(&"heal")
		assert_eq(player().state, S.HEAL)
		advance(Frames.of(VeltharisData.PUNISH_REACTION) + 2)
		var moves := _started_moves()
		if moves.size() > 0 and moves[0] == &"judgment_thrust":
			punished += 1
	var rate := float(punished) / trials
	assert_between(rate, 0.58, 0.82, "懲罰率 %.2f（目標 0.7）" % rate)


func test_heal_beyond_260_not_punished() -> void:
	for t in 30:
		sim = CombatSim.new(2000 + t)
		sim.boss.set_ai()
		# 治療懲罰範圍外 60px（範圍 2026-09-30 起 345，原 260）
		var d := VeltharisData.HEAL_PUNISH_RANGE + 60.0
		sim.boss.pos = Vector2(-d * 0.5, -40)
		sim.player.pos = Vector2(d * 0.5, -40)
		sim.player.hp = 50
		sim.boss.start_breather(120)
		event_log.clear()
		press(&"heal")
		advance(8)
		assert_false(&"judgment_thrust" in _started_moves(), "%.0fpx 外治療不會被立刻懲罰" % VeltharisData.HEAL_PUNISH_RANGE)


## §6.1 距離分段：遠距離一階段只會快步逼近
func test_far_player_is_approached_fast() -> void:
	sim.boss.pos = Vector2(-300, -80)
	sim.player.pos = Vector2(300, 80)
	sim.boss.decide_now()
	advance(3)
	assert_eq(boss().state, BS.WALK)
	assert_eq(boss().walk_speed, VeltharisData.FAST_SPEED, "超過中距離（MID_RANGE）快步")


## 規則 5：每套攻擊之後的喘息 0.8–1.4 秒（一階段）：一招結束到下一招開始至少 48 幀
func test_breather_between_sets_phase1() -> void:
	sim.god_mode = true
	advance(60 * 120)
	var last_end := -1
	var gaps: Array[int] = []
	for e in event_log:
		if e["type"] == &"boss_move_end":
			last_end = e["frame"]
		elif e["type"] == &"boss_attack" and last_end >= 0:
			gaps.append(e["frame"] - last_end)
			last_end = -1
	assert_true(gaps.size() > 10, "兩分鐘內至少 10 套（實際 %d）" % gaps.size())
	for g in gaps:
		assert_true(g >= Frames.of(VeltharisData.BREATHER[0].x), "喘息 %d 幀（至少 48）" % g)
	for b in boss().ai.breather_log:
		assert_between(float(b), Frames.of(0.8), Frames.of(1.4), "喘息長度 %d 幀" % b)



func test_breather_is_full_length_even_if_player_walks_in() -> void:
	# 審查 M4-B1：喘息時玩家走近，喘息也要走滿（不會提早出招）
	sim.god_mode = true
	sim.boss.pos = Vector2(0, -150)
	sim.player.pos = Vector2(0, 150)
	advance(60 * 90)
	var last_end := -1
	var checked := 0
	for e in event_log:
		if e["type"] == &"boss_move_end":
			last_end = e["frame"]
		elif e["type"] == &"boss_attack" and last_end >= 0:
			assert_true(e["frame"] - last_end >= Frames.of(VeltharisData.BREATHER[0].x), "喘息只有 %d 幀" % (e["frame"] - last_end))
			checked += 1
			last_end = -1
	assert_true(checked > 5)


func tick(presses: Array = []) -> void:
	# 這個檔案的玩家一直往 Boss 走（其他測試的 move 預設為零，不受影響）
	if sim.boss.mode == BossSim.Mode.AI and sim.god_mode:
		var to := sim.boss.pos - sim.player.pos
		move = to.normalized() if to.length() > 40.0 else Vector2.ZERO
	super.tick(presses)
