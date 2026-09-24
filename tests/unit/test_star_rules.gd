extends SimTestCase
## combat-design §11.6 的九條 ★ 規則：直接掃描兩個階段的全部招式資料（CLAUDE.md 慣例），
## 資料掃描不夠的地方再用模擬確認。取整規則見 Frames。

const AT := CombatTypes.AttackType
const TG := CombatTypes.Telegraph


func _all_moves() -> Array[BossMoveData]:
	var out: Array[BossMoveData] = []
	for phase in [1, 2]:
		for id: StringName in VeltharisData.moves(phase):
			out.append(VeltharisData.moves(phase)[id])
	return out


func _min_breather_frames() -> int:
	return mini(Frames.of(VeltharisData.BREATHER[0].x), Frames.of(VeltharisData.BREATHER[1].x))


## ★1 輕擊之後的下一擊，間隔至少 0.55 秒（踉蹌 0.35 + 反應 0.2）
func test_star1_gap_after_light_hit() -> void:
	var need := Frames.of(PlayerData.STAGGER_TIME + 0.2)
	assert_eq(need, Frames.of(0.55))
	for m in _all_moves():
		for i in m.hits.size():
			if m.hits[i].attack_type != AT.LIGHT:
				continue
			var gap: int
			if i + 1 < m.hits.size():
				gap = Frames.of(m.hits[i + 1].interval)
			else:
				# 連段的最後一擊：之後至少還有判定剩餘、收招、喘息、下一招起手
				gap = Frames.of(m.hits[i].active) + Frames.of(m.recovery) + _min_breather_frames() + Frames.of(0.4)
			assert_true(gap >= need, "%s 第 %d 擊（輕擊）之後 %d 幀就出下一擊" % [m.id, i + 1, gap])


## ★2 至少一招懲罰技；架勢崩潰到命中不超過 1.1 秒，且小於崩潰硬直 1.2 秒
func test_star2_punish_move_timing() -> void:
	for phase in [1, 2]:
		var punish: BossMoveData = null
		for id: StringName in VeltharisData.moves(phase):
			var m: BossMoveData = VeltharisData.moves(phase)[id]
			if m.is_punish:
				punish = m
		assert_true(punish != null, "第 %d 階段有懲罰技" % phase)
		if punish == null:
			continue
		# 最壞情況：反應 + 起手 + 整段突進才碰到
		var worst := Frames.of(VeltharisData.PUNISH_REACTION) + punish.hit_start_frames()[0] + Frames.of(punish.hits[0].active)
		assert_true(worst <= Frames.of(1.1), "懲罰技最慢 %d 幀命中（上限 66）" % worst)
		assert_true(worst < Frames.of(PlayerData.POSTURE_BREAK_TIME), "小於崩潰硬直 72 幀")


## ★3 可格擋攻擊的第一擊起手至少 0.4 秒，起手期間有可辨識的預兆
func test_star3_first_blockable_hit_startup_and_telegraph() -> void:
	for m in _all_moves():
		var h: BossHitData = m.hits[0]
		if not h.is_blockable():
			continue
		assert_true(Frames.of(h.interval) >= Frames.of(0.4), "%s 第一擊起手 %.2f 秒" % [m.id, h.interval])
		# 實際出招，檢查起手每一幀都有預兆
		sim = CombatSim.new(1)
		sim.player.pos = Vector2(0, 150)
		sim.boss.pos = Vector2(0, -60)
		sim.boss.phase = 1 if VeltharisData.move(1, m.id) == m else 2
		sim.boss.start_move(m)
		for f in m.hit_start_frames()[0]:
			var t := sim.boss.telegraph()
			assert_true(t == TG.NORMAL or t == TG.DELAYED, "%s 起手第 %d 幀沒有預兆" % [m.id, f])
			if t != TG.NORMAL and t != TG.DELAYED:
				break
			advance(1)
			if sim.boss.state != BossSim.State.ATTACK:
				break


## ★4 不可格擋攻擊的危險預兆至少 0.5 秒
func test_star4_danger_telegraph_at_least_half_second() -> void:
	for m in _all_moves():
		var starts := m.hit_start_frames()
		for i in m.hits.size():
			var h: BossHitData = m.hits[i]
			if h.is_blockable():
				continue
			assert_true(Frames.of(h.danger_time) >= Frames.of(0.5), "%s 第 %d 擊危險預兆 %.2f 秒" % [m.id, i + 1, h.danger_time])
			assert_true(h.danger_time <= h.interval, "%s 危險預兆放得進起手時間" % m.id)
			# 實際數危險預兆的幀數
			sim = CombatSim.new(1)
			sim.player.pos = Vector2(0, 170)
			sim.boss.pos = Vector2(0, -150)
			sim.god_mode = true
			sim.boss.start_move(m)
			var danger := 0
			while sim.boss.state == BossSim.State.ATTACK and sim.boss.state_elapsed() < starts[i]:
				if sim.boss.current_hit_index() == i and sim.boss.telegraph() == TG.DANGER:
					danger += 1
				advance(1)
			assert_true(danger >= Frames.of(0.5), "%s 第 %d 擊實際危險預兆 %d 幀" % [m.id, i + 1, danger])


## ★5 不可格擋攻擊在任一點上的判定持續時間不超過閃身無敵的 0.14 秒
func test_star5_unblockable_passes_any_point_faster_than_dodge_iframes() -> void:
	var limit := Frames.of(0.14)
	var dodge_iframes := Frames.of(PlayerData.DODGE_INVULN_END) - Frames.of(PlayerData.DODGE_INVULN_START)
	assert_true(dodge_iframes >= limit)
	for m in _all_moves():
		for h in m.hits:
			if h.is_blockable():
				continue
			assert_eq(h.shape, CombatTypes.Shape.RING, "目前唯一的不可格擋形狀是環")
			var n := Frames.of(h.active)
			var worst := 0
			for d10 in range(0, int(h.radius * 10.0) + 200, 5):
				var d := d10 / 10.0
				var count := 0
				for f in n:
					var hb := {"hit": h, "origin": Vector2.ZERO, "dir": Vector2.DOWN, "ring_radius": BossSim.ring_radius(h, f)}
					if CombatSim.boss_hitbox_overlaps(hb, Vector2(d, 0), PlayerData.HURT_RADIUS):
						count += 1
				worst = maxi(worst, count)
			assert_true(worst <= limit, "%s 的環在某一點停留 %d 幀（上限 %d）" % [m.id, worst, limit])


## ★6 出招期間一律霸體；短僵直冷卻至少 3 秒
func test_star6_super_armor_and_stagger_cooldown() -> void:
	assert_true(VeltharisData.SHORT_STAGGER_COOLDOWN >= 3.0)
	var heavy := PlayerData.heavy_thrust()
	# 起手與判定期間：受傷、被削韌，但不會僵直
	for id: StringName in VeltharisData.moves(1):
		var m: BossMoveData = VeltharisData.moves(1)[id]
		sim = CombatSim.new(1)
		sim.player.pos = Vector2(0, 170)
		sim.boss.pos = Vector2(0, -150)
		sim.god_mode = true
		sim.boss.start_move(m)
		var last_active := m.last_hit_end_frame()
		while sim.boss.state == BossSim.State.ATTACK and sim.boss.state_elapsed() < last_active:
			var hp := sim.boss.hp
			sim.boss.receive_player_hit(heavy)
			assert_eq(sim.boss.state, BossSim.State.ATTACK, "%s 第 %d 幀被重擊打中不能僵直" % [id, sim.boss.state_elapsed()])
			assert_true(sim.boss.hp < hp, "霸體仍會受傷")
			sim.boss.hp = VeltharisData.MAX_HP
			sim.boss.toughness = VeltharisData.MAX_TOUGHNESS
			advance(1)


## ★7 倒地全程無敵，Boss 不能追打倒地的玩家（倒地前已經開始的連段會繼續，但打不到：見 test_boss_attacks）；
## AI 在玩家倒地時不開新的招式，喘息也不靠近（boss §6.2 規則 6：後退或踱步）
func test_star7_ai_does_not_attack_downed_player() -> void:
	sim.boss.set_ai()
	sim.boss.pos = Vector2(0, -20)
	sim.player.pos = Vector2(0, 40)
	sim.apply_boss_hit(VeltharisData.move(1, &"royal_sweep").hits[0], sim.boss.pos)
	assert_eq(sim.player.state, PlayerSim.State.LAUNCHED)
	event_log.clear()
	var frames := 0
	while sim.player.is_invulnerable():
		advance(1)
		frames += 1
	assert_true(frames > 60)
	for e in event_log:
		assert_false(e["type"] == &"boss_attack", "玩家倒地期間 Boss 開始出招")
		assert_false(e["type"] == &"boss_swing", "玩家倒地期間 Boss 揮劍")


func test_star7_breather_does_not_approach_downed_player() -> void:
	# 規則 6：不守在玩家身邊等他起身
	sim.boss.set_ai()
	sim.boss.pos = Vector2(0, -150)
	sim.player.pos = Vector2(0, 150)
	sim.boss.start_breather(120)
	sim.apply_boss_hit(VeltharisData.move(1, &"royal_sweep").hits[0], sim.boss.pos + Vector2(0, 250))
	var d0 := sim.boss.pos.distance_to(sim.player.pos)
	while sim.player.is_invulnerable():
		advance(1)
		assert_true(sim.boss.pos.distance_to(sim.player.pos) >= minf(d0, VeltharisData.NEAR_RANGE) - 1.0, "倒地期間 Boss 不靠近")


## ★8 延遲攻擊在延遲期間維持靜止姿勢，並有專屬預兆（位置與預兆在這裡掃描；姿勢見 test_boss_attacks）
func test_star8_delayed_hits_have_hold_and_own_telegraph() -> void:
	var found := 0
	for m in _all_moves():
		for i in m.hits.size():
			var h: BossHitData = m.hits[i]
			if not h.is_delayed():
				continue
			found += 1
			assert_true(h.hold_start + h.delay_hold <= h.interval, "%s 停住結束後才揮下" % m.id)
			sim = CombatSim.new(1)
			sim.player.pos = Vector2(0, 30)
			sim.boss.pos = Vector2(0, -40)
			sim.god_mode = true
			sim.boss.start_move(m)
			var windup := sim.boss.windup_start(i)
			var hold_from := windup + Frames.of(h.hold_start)
			var hold_to := hold_from + Frames.of(h.delay_hold)
			while sim.boss.state_elapsed() < hold_from:
				advance(1)
			var p0 := sim.boss.pos
			while sim.boss.state_elapsed() < hold_to:
				assert_eq(sim.boss.telegraph(), TG.DELAYED, "%s 延遲期間是延遲專屬預兆" % m.id)
				assert_eq(sim.boss.pos, p0, "%s 延遲期間不移動" % m.id)
				advance(1)
	assert_true(found >= 2, "兩個階段都有延遲版")


## ★9 每一種攻擊都能被完美彈返或閃身應對
## - 可格擋：連段中相鄰兩擊之間，玩家要「擋完放開 → 等 0.3 秒重新開窗 → 再按」，
##   所以兩擊間隔至少 放開 1 幀 + 重新開窗 18 幀 + 瞄準窗口中間 4 幀；否則第二擊不可能完美彈返。
## - 不可格擋：★5 已確認閃身躲得掉；危險預兆夠長，來得及反應（0.25 秒反應 + 按鍵）；相鄰兩個環之間閃身冷卻來得及。
## 完整的實證是完美機器人對每一招零傷害（test_bots）。
func test_star9_every_hit_is_parryable_or_dodgeable() -> void:
	var min_gap := 1 + Frames.of(PlayerData.REARM_TIME) + 4
	for m in _all_moves():
		for i in m.hits.size():
			var h: BossHitData = m.hits[i]
			if i > 0 and h.is_blockable() and m.hits[i - 1].is_blockable():
				assert_true(Frames.of(h.interval) >= min_gap, "%s 第 %d 擊與前一擊只隔 %d 幀，來不及重新開窗" % [m.id, i + 1, Frames.of(h.interval)])
			if not h.is_blockable():
				assert_true(Frames.of(h.danger_time) >= Frames.of(0.25) + Frames.of(PlayerData.DODGE_INVULN_START) + 1)
				if i > 0 and not m.hits[i - 1].is_blockable():
					assert_true(Frames.of(h.interval) >= Frames.of(PlayerData.DODGE_INTERVAL), "%s 兩個環之間閃身冷卻來得及" % m.id)
