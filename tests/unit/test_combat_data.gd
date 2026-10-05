extends TestCase
## 戰鬥資料能被讀取，且與文件數值一致（M0：Resource 格式；★ 規則的掃描在 test_star_rules.gd）。
## 表格裡寫的是文件值；M6 依 plan §7 調整過的數值在下面的 TUNED_* 對照（每一筆都記在 docs/tuning-log.md），
## 並檢查調整幅度都在文件值的 ±30% 內。

## tuning-log：Boss 每一擊的傷害 × 1.3，無條件捨去
const TUNED_BOSS_DAMAGE_SCALE := 1.3
## tuning-log：完美彈返的削韌 12 → 15、20 → 26
const TUNED_PARRY_TOUGHNESS := {0: 0, 12: 15, 20: 26}
## tuning-log：主角傷害
const TUNED_PLAYER_DAMAGE := {15: 11, 25: 18, 60: 42, 70: 49}
## tuning-log：主角攻擊的削韌 × 0.7
const TUNED_PLAYER_TOUGHNESS := {2: 1.4, 6: 4.2, 15: 10.5, 22: 15.4}
## tuning-log：單一常數 [文件值, 調整後]
const TUNED_CONSTANTS := {
	"VeltharisData.MAX_HP": [1200, 1560],
	"VeltharisData.MAX_TOUGHNESS": [100.0, 70.0],
	"VeltharisData.TOUGHNESS_REGEN_DELAY": [2.0, 2.6],
	"VeltharisData.TOUGHNESS_REGEN_BASE": [10.0, 7.0],
	"VeltharisData.EXECUTE_DAMAGE_RATIO": [0.15, 0.105],
	"PlayerData.MAX_HP": [100, 72],
	"PlayerData.HEAL_TIME": [0.9, 1.17],
}


static func tuned_boss_damage(doc: int) -> int:
	return floori(doc * TUNED_BOSS_DAMAGE_SCALE + 0.000001)


func _tuned(key: String) -> Variant:
	return TUNED_CONSTANTS[key][1]


func test_tuned_values_within_30_percent_of_doc() -> void:
	# plan §7：只能在文件數值的 ±30% 內調整
	for key: String in TUNED_CONSTANTS:
		var pair: Array = TUNED_CONSTANTS[key]
		var ratio := float(pair[1]) / float(pair[0])
		assert_between(ratio, 0.7 - 0.000001, 1.3 + 0.000001, "%s：%s → %s" % [key, pair[0], pair[1]])
	for table: Dictionary in [TUNED_PARRY_TOUGHNESS, TUNED_PLAYER_DAMAGE, TUNED_PLAYER_TOUGHNESS]:
		for doc: int in table:
			if doc == 0:
				continue
			var ratio := float(table[doc]) / float(doc)
			assert_between(ratio, 0.7 - 0.000001, 1.3 + 0.000001, "%s → %s" % [doc, table[doc]])
	for doc: int in [15, 24, 26, 28, 30, 32, 35]:
		var ratio := float(tuned_boss_damage(doc)) / doc
		assert_between(ratio, 1.0, 1.3 + 0.000001, "Boss 傷害 %d → %d" % [doc, tuned_boss_damage(doc)])
	assert_near(VeltharisData.DAMAGE_SCALE, TUNED_BOSS_DAMAGE_SCALE)
	assert_eq(VeltharisData.PARRY_TOUGHNESS_LIGHT_MID, TUNED_PARRY_TOUGHNESS[12])
	assert_eq(VeltharisData.PARRY_TOUGHNESS, TUNED_PARRY_TOUGHNESS[20])


## 文件表格的一列（[間隔, 判定, 傷害, 架勢, 削韌, 彈開, 類型, 命中效果]）換成調整後的值
static func _tuned_row(r: Array) -> Array:
	var out := r.duplicate()
	out[2] = tuned_boss_damage(r[2])
	out[4] = TUNED_PARRY_TOUGHNESS[r[4]]
	return out


func test_boss_moves_are_resources() -> void:
	for phase in [1, 2]:
		var moves := VeltharisData.moves(phase)
		assert_true(moves.size() >= 7, "第 %d 階段的招式數量" % phase)
		for id: StringName in moves:
			var m: BossMoveData = moves[id]
			assert_true(m is Resource, "%s 應是 Resource" % id)
			assert_eq(m.id, id)
			assert_true(m.hits.size() >= 1, "%s 至少一擊" % id)
			for h in m.hits:
				assert_true(h is BossHitData)
				assert_true(h.interval > 0.0 and h.active > 0.0, "%s 時間必須為正" % id)


func test_phase1_move_list_matches_doc() -> void:
	var ids := VeltharisData.moves(1).keys()
	ids.sort()
	var expected := [&"ash_impact", &"judgment_thrust", &"oath_cleave", &"oath_cleave_delayed",
		&"quick_combo_2", &"quick_combo_3", &"royal_sweep", &"twin_slash"]
	expected.sort()
	assert_eq(ids, expected)


func test_phase2_move_list_matches_doc() -> void:
	var ids := VeltharisData.moves(2).keys()
	ids.sort()
	var expected := [&"ash_spin", &"double_impact", &"judgment_thrust", &"kings_leap", &"oath_cleave",
		&"oath_cleave_delayed", &"quick_combo_2", &"quick_combo_3", &"royal_sweep", &"triple_slash",
		&"triple_slash_delayed"]
	expected.sort()
	assert_eq(ids, expected)


## boss-veltharis §4 的每一擊：[間隔, 判定, 傷害, 架勢, 削韌, 彈開, 類型, 命中效果]
func test_phase1_hit_values_match_doc() -> void:
	var AT := CombatTypes.AttackType
	var FX := CombatTypes.HitEffect
	var table := {
		&"royal_sweep": [[0.8, 0.15, 28, 35, 20, 1.2, AT.HEAVY, FX.LAUNCH]],
		&"twin_slash": [[0.8, 0.1, 26, 35, 20, 0.0, AT.HEAVY, FX.KNOCKDOWN], [0.9, 0.1, 28, 35, 20, 1.2, AT.HEAVY, FX.LAUNCH]],
		&"oath_cleave": [[1.0, 0.1, 32, 35, 20, 1.2, AT.HEAVY, FX.KNOCKDOWN]],
		&"oath_cleave_delayed": [[1.6, 0.1, 32, 35, 20, 1.2, AT.HEAVY, FX.KNOCKDOWN]],
		&"judgment_thrust": [[0.6, 0.2, 26, 35, 20, 1.2, AT.HEAVY, FX.KNOCKDOWN]],
		&"quick_combo_3": [[0.4, 0.1, 15, 20, 12, 0.0, AT.LIGHT, FX.STAGGER], [0.6, 0.1, 15, 20, 12, 0.0, AT.LIGHT, FX.STAGGER],
			[0.8, 0.1, 26, 35, 20, 1.2, AT.HEAVY, FX.LAUNCH]],
		&"quick_combo_2": [[0.4, 0.1, 15, 20, 12, 0.0, AT.LIGHT, FX.STAGGER], [0.6, 0.1, 15, 20, 20, 0.8, AT.LIGHT, FX.STAGGER]],
		&"ash_impact": [[1.1, 0.2, 35, 0, 0, 0.0, AT.UNBLOCKABLE, FX.LAUNCH]],
	}
	for id: StringName in table:
		var m := VeltharisData.move(1, id)
		var rows: Array = table[id]
		assert_eq(m.hits.size(), rows.size(), "%s 的擊數" % id)
		for i in mini(rows.size(), m.hits.size()):
			var h: BossHitData = m.hits[i]
			var r: Array = _tuned_row(rows[i])
			var got := [h.interval, h.active, h.damage, h.posture_damage, h.toughness_damage, h.bounce_time, h.attack_type, h.hit_effect]
			for j in r.size():
				if typeof(r[j]) == TYPE_FLOAT:
					assert_near(got[j], r[j], 0.0001, "%s 第 %d 擊欄位 %d" % [id, i + 1, j])
				else:
					assert_eq(got[j], r[j], "%s 第 %d 擊欄位 %d" % [id, i + 1, j])


func test_phase1_recovery_matches_doc() -> void:
	var rec := {&"royal_sweep": 0.9, &"twin_slash": 1.0, &"oath_cleave": 1.2, &"oath_cleave_delayed": 1.2,
		&"judgment_thrust": 0.8, &"quick_combo_3": 0.9, &"quick_combo_2": 0.9, &"ash_impact": 1.4}
	for id: StringName in rec:
		assert_near(VeltharisData.move(1, id).recovery, rec[id], 0.0001, "%s 收招" % id)


## boss-veltharis §4–§5 的範圍（2026-09-30 使用者：Boss 放大到 160、大劍加長（劍首到下巴、握在上段），範圍照劍
## 實際揮到的距離放大；舊值 100／110／40／120／140／16／60／100）
func test_ranges_match_doc() -> void:
	for id: StringName in [&"royal_sweep", &"twin_slash"]:
		for h: BossHitData in VeltharisData.move(1, id).hits:
			assert_eq(h.shape, CombatTypes.Shape.SECTOR, "%s" % id)
			assert_near(h.angle_deg, 150.0)
			assert_near(h.radius, 155.0, 0.0001, "%s 半徑 155" % id)
	# 快斬連段的兩刀單手快斬：半徑 165（2026-10-02 使用者：單手伸直、腰彎下去，劍尖畫到 168–171px，「範圍放大吧」）
	for id: StringName in [&"quick_combo_2", &"quick_combo_3"]:
		for i in 2:
			var q := VeltharisData.move(1, id).hits[i]
			assert_eq(q.shape, CombatTypes.Shape.SECTOR, "%s 第 %d 擊" % [id, i + 1])
			assert_near(q.angle_deg, 150.0)
			assert_near(q.radius, 165.0, 0.0001, "%s 第 %d 擊半徑 165" % [id, i + 1])
	var upslash := VeltharisData.move(1, &"quick_combo_3").hits[2]
	assert_near(upslash.radius, 155.0)
	assert_near(upslash.angle_deg, 120.0)
	var cleave := VeltharisData.move(1, &"oath_cleave").hits[0]
	assert_eq(cleave.shape, CombatTypes.Shape.RECT)
	assert_near(cleave.length, 165.0)
	assert_near(cleave.width, 53.0)
	var thrust := VeltharisData.move(1, &"judgment_thrust").hits[0]
	assert_near(thrust.length, 150.0)
	assert_near(thrust.width, 40.0)
	assert_near(thrust.lunge_distance, 160.0)
	# 雙斬／三斬第二刀前踏（2026-10-01 使用者）；其他每一擊都不踏
	for phase in [1, 2]:
		for id: StringName in VeltharisData.moves(phase):
			var m := VeltharisData.move(phase, id)
			for i in m.hits.size():
				var stepping := id in [&"twin_slash", &"triple_slash", &"triple_slash_delayed"] and i == 1
				assert_near(m.hits[i].step_distance, VeltharisData.TWIN_STEP_DISTANCE if stepping else 0.0, 0.0001,
					"%s 第 %d 擊前踏" % [id, i + 1])
				if stepping:
					assert_true(m.hits[i].step_time <= m.hits[i].lock_before + 0.0001, "%s：踏步在方向鎖定之後" % id)
	var ring := VeltharisData.move(1, &"ash_impact").hits[0]
	assert_eq(ring.shape, CombatTypes.Shape.RING)
	assert_near(ring.radius, 185.0)
	assert_near(ring.thickness, 21.0)
	assert_near(ring.danger_time, 0.6)
	var leap := VeltharisData.move(2, &"kings_leap")
	assert_near(leap.airborne_start, 0.7)
	assert_near(leap.hits[0].radius, 80.0)
	assert_near(leap.hits[0].lock_before, 0.3)
	var spin := VeltharisData.move(2, &"ash_spin").hits[0]
	assert_eq(spin.shape, CombatTypes.Shape.CIRCLE)
	assert_near(spin.radius, 165.0)


func test_delayed_cleave_holds_at_top() -> void:
	var h := VeltharisData.move(1, &"oath_cleave_delayed").hits[0]
	assert_near(h.delay_hold, 0.6)
	assert_near(h.interval, 1.6, 0.0001, "總起手 1.6 秒")
	assert_true(h.hold_start + h.delay_hold < h.interval, "停住結束後還要揮下")


func test_hit_start_frames_accumulate_rounded_intervals() -> void:
	var m := VeltharisData.move(1, &"quick_combo_3")
	assert_eq(m.hit_start_frames(), PackedInt32Array([24, 60, 108]))
	assert_eq(m.total_frames(), 108 + 6 + 54)


func test_player_attack_table_matches_doc() -> void:
	# combat-design §8.1：[起手, 判定, 收招, 傷害, 削韌, 前進]
	var table := [[0.10, 0.08, 0.25, 15, 2, 6.0], [0.10, 0.08, 0.25, 15, 2, 6.0],
		[0.12, 0.08, 0.28, 15, 2, 6.0], [0.10, 0.10, 0.45, 25, 6, 14.0]]
	var attacks := PlayerData.light_attacks()
	assert_eq(attacks.size(), 4)
	for i in 4:
		var a := attacks[i]
		var r: Array = table[i]
		assert_near(a.startup, r[0])
		assert_near(a.active, r[1])
		assert_near(a.recovery, r[2])
		assert_eq(a.damage, TUNED_PLAYER_DAMAGE[r[3]], "第 %d 段傷害（tuning-log）" % (i + 1))
		assert_near(a.toughness, TUNED_PLAYER_TOUGHNESS[r[4]], 0.0001, "第 %d 段削韌（tuning-log）" % (i + 1))
		assert_near(a.advance, r[5])
		assert_eq(a.cancelable, i < 3, "第 %d 段取消規則" % (i + 1))
		assert_eq(a.can_short_stagger, i == 3)
		# §8.1（2026-09-29）：只有第 4 段收招後有停頓
		assert_near(a.end_lag, PlayerData.FINISHER_END_LAG if i == 3 else 0.0)
	var heavy := PlayerData.heavy_thrust()
	# 2026-10-05 重擊加強（使用者 2026-09-30 拍板）：文件值 傷害 60 → 70、削韌 15 → 22、突刺 72 → 120px、0.2 → 0.25 秒
	assert_eq(heavy.damage, TUNED_PLAYER_DAMAGE[70], "重擊傷害（tuning-log）")
	assert_near(heavy.toughness, TUNED_PLAYER_TOUGHNESS[22], 0.0001, "重擊削韌（tuning-log）")
	assert_near(heavy.recovery, 0.5)
	assert_near(heavy.advance, 120.0)
	assert_near(PlayerData.THRUST_DISTANCE, 120.0)
	assert_eq(Frames.of(PlayerData.THRUST_TIME), 15)
	assert_false(heavy.cancelable)
	assert_true(heavy.can_short_stagger)


func test_feedback_table_matches_doc() -> void:
	# combat-design §12：[頓幀, 震動]
	var table := {&"light_hit": [0.04, 0.0], &"finisher_hit": [0.07, 2.0], &"heavy_hit": [0.10, 4.0],
		&"perfect_parry": [0.08, 3.0], &"player_stagger": [0.06, 2.0], &"player_knockdown": [0.08, 5.0],
		&"boss_break": [0.15, 4.0], &"execution": [0.25, 6.0], &"normal_block": [0.0, 0.0]}
	for ev: StringName in table:
		assert_near(FeedbackData.TABLE[ev]["hitstop"], table[ev][0], 0.0001, "%s 頓幀" % ev)
		assert_near(FeedbackData.shake(ev), table[ev][1], 0.0001, "%s 震動" % ev)
	assert_near(FeedbackData.shake_time(&"perfect_parry"), 0.1, 0.0001, "§6 完美彈返震動 0.1 秒")
	assert_near(FeedbackData.BOSS_FLASH_TIME, 0.06)


func test_phase2_recovery_is_25_percent_shorter_and_startups_unchanged() -> void:
	var p1 := VeltharisData.moves(1)
	var p2 := VeltharisData.moves(2)
	for id: StringName in p1:
		if not p2.has(id):
			continue
		var a: BossMoveData = p1[id]
		var b: BossMoveData = p2[id]
		assert_near(b.recovery, a.recovery * 0.75, 0.0001, "%s 二階段收招" % id)
		assert_eq(b.hits.size(), a.hits.size(), id)
		for i in a.hits.size():
			assert_near(b.hits[i].interval, a.hits[i].interval, 0.0001, "%s 第 %d 擊起手／間隔不縮短" % [id, i + 1])
	# 0.9 × 0.75 = 0.675 秒 = 40.5 幀，取整規則為 roundi → 41（釘住，避免換算方式悄悄改變）
	assert_eq(Frames.of(VeltharisData.move(2, &"royal_sweep").recovery), 41)


func test_phase2_new_moves_match_doc() -> void:
	var AT := CombatTypes.AttackType
	var FX := CombatTypes.HitEffect
	# boss §5：[間隔, 判定, 傷害, 架勢, 削韌, 彈開, 類型, 命中效果]
	var table := {
		&"triple_slash": [[0.8, 0.1, 26, 35, 20, 0.0, AT.HEAVY, FX.KNOCKDOWN], [0.9, 0.1, 28, 35, 20, 0.0, AT.HEAVY, FX.LAUNCH],
			[1.0, 0.1, 32, 35, 20, 1.2, AT.HEAVY, FX.KNOCKDOWN]],
		&"triple_slash_delayed": [[0.8, 0.1, 26, 35, 20, 0.0, AT.HEAVY, FX.KNOCKDOWN], [0.9, 0.1, 28, 35, 20, 0.0, AT.HEAVY, FX.LAUNCH],
			[1.6, 0.1, 32, 35, 20, 1.2, AT.HEAVY, FX.KNOCKDOWN]],
		&"double_impact": [[1.1, 0.2, 35, 0, 0, 0.0, AT.UNBLOCKABLE, FX.LAUNCH], [0.9, 0.2, 35, 0, 0, 0.0, AT.UNBLOCKABLE, FX.LAUNCH]],
		# 灰燼迴旋：2026-10-04 使用者決定只轉一圈、只打一下（tuning-log）
		&"ash_spin": [[0.9, 0.25, 24, 35, 20, 1.2, AT.HEAVY, FX.LAUNCH]],
		&"kings_leap": [[1.5, 0.1, 30, 35, 20, 1.2, AT.HEAVY, FX.LAUNCH]],
	}
	for id: StringName in table:
		var m := VeltharisData.move(2, id)
		var rows: Array = table[id]
		assert_eq(m.hits.size(), rows.size(), "%s 的擊數" % id)
		for i in mini(rows.size(), m.hits.size()):
			var h: BossHitData = m.hits[i]
			var r: Array = _tuned_row(rows[i])
			var got := [h.interval, h.active, h.damage, h.posture_damage, h.toughness_damage, h.bounce_time, h.attack_type, h.hit_effect]
			for j in r.size():
				if typeof(r[j]) == TYPE_FLOAT:
					assert_near(got[j], r[j], 0.0001, "%s 第 %d 擊欄位 %d" % [id, i + 1, j])
				else:
					assert_eq(got[j], r[j], "%s 第 %d 擊欄位 %d" % [id, i + 1, j])
	# 收招：三斬沿用下劈 1.2 × 0.75；雙重衝擊 1.4 × 0.75；新招依文件（不再縮短，見 tuning-log）
	assert_near(VeltharisData.move(2, &"triple_slash").recovery, 0.9)
	assert_near(VeltharisData.move(2, &"double_impact").recovery, 1.05)
	assert_near(VeltharisData.move(2, &"ash_spin").recovery, 1.2)
	assert_near(VeltharisData.move(2, &"kings_leap").recovery, 1.0)


func test_boss_constants_match_doc() -> void:
	assert_eq(VeltharisData.MAX_HP, _tuned("VeltharisData.MAX_HP"))
	assert_near(VeltharisData.HEIGHT, 160.0)
	assert_near(VeltharisData.HURT_RADIUS, 35.0)
	assert_near(VeltharisData.WALK_SPEED, 60.0)
	assert_near(VeltharisData.FAST_SPEED, 120.0)
	assert_near(VeltharisData.MAX_TOUGHNESS, _tuned("VeltharisData.MAX_TOUGHNESS"))
	assert_near(VeltharisData.TOUGHNESS_REGEN_DELAY, _tuned("VeltharisData.TOUGHNESS_REGEN_DELAY"))
	assert_near(VeltharisData.TOUGHNESS_REGEN_BASE, _tuned("VeltharisData.TOUGHNESS_REGEN_BASE"))
	assert_near(VeltharisData.TOUGHNESS_REGEN_FLOOR, 0.3)
	assert_near(VeltharisData.SHORT_STAGGER_TIME, 0.3)
	assert_near(VeltharisData.SHORT_STAGGER_COOLDOWN, 3.0)
	assert_near(VeltharisData.BREAK_TIME, 3.0)
	assert_near(VeltharisData.EXECUTE_DAMAGE_RATIO, _tuned("VeltharisData.EXECUTE_DAMAGE_RATIO"))
	assert_near(VeltharisData.RISE_TIME, 1.0)
	assert_near(VeltharisData.PHASE2_HP_RATIO, 0.5)
	assert_near(VeltharisData.TRANSITION_TIME, 1.5)
	assert_near(VeltharisData.NEAR_RANGE, 165.0)
	assert_near(VeltharisData.MID_RANGE, 290.0)
	assert_eq(VeltharisData.BREATHER[0], Vector2(0.8, 1.4))
	assert_eq(VeltharisData.BREATHER[1], Vector2(0.4, 0.9))
	assert_near(VeltharisData.PUNISH_REACTION, 0.1)
	assert_near(VeltharisData.HEAL_PUNISH_RANGE, 345.0)
	assert_near(VeltharisData.HEAL_PUNISH_CHANCE, 0.7)
	assert_eq(VeltharisData.BLOCK_STREAK_FOR_IMPACT, 3)
	assert_eq(VeltharisData.MAX_SAME_MOVE_STREAK, 2)
	assert_near(VeltharisData.DELAYED_CHANCE, 0.4)
	assert_near(VeltharisData.QUICK_TWO_HIT_CHANCE, 0.4)


func test_ai_weights_match_doc() -> void:
	var w := VeltharisData.WEIGHTS
	assert_eq(w[1][&"near"], {&"royal_sweep": 20, &"twin_slash": 20, &"oath_cleave": 20, &"quick_combo": 25, &"ash_impact": 15})
	assert_eq(w[1][&"mid"], {&"judgment_thrust": 45, &"oath_cleave": 20, &"approach_slow": 35})
	assert_eq(w[1][&"far"], {&"approach_fast": 100})
	assert_eq(w[2][&"near"], {&"royal_sweep": 10, &"triple_slash": 20, &"oath_cleave": 15, &"quick_combo": 20, &"ash_spin": 20, &"double_impact": 15})
	assert_eq(w[2][&"mid"], {&"judgment_thrust": 45, &"kings_leap": 25, &"approach_slow": 30})
	assert_eq(w[2][&"far"], {&"kings_leap": 60, &"approach_fast": 40})


func test_player_constants_match_doc() -> void:
	# §4
	assert_eq(PlayerData.MAX_HP, _tuned("PlayerData.MAX_HP"))
	assert_near(PlayerData.MAX_POSTURE, 100.0)
	assert_eq(PlayerData.HEAL_CHARGES, 3)
	# 2026-10-05 使用者：每次治療回最大 HP 的五分之三（先試三分之二，使用者改成五分之三「比較平衡」；之後升級最大 HP
	# 會變多，跟著比例走）。現在最大 HP 72：三分之一 24（原本的治療量 25 約等於這個）、五分之三 43.2 → 43
	assert_near(PlayerData.HEAL_RATIO, 0.6)
	assert_eq(PlayerData.heal_amount(), 43)
	assert_eq(PlayerData.heal_amount(PlayerData.MAX_HP), 43)
	assert_eq(PlayerData.heal_amount(120), 72, "最大 HP 變多時跟著比例")
	assert_near(PlayerData.HEAL_TIME, _tuned("PlayerData.HEAL_TIME"))
	assert_near(PlayerData.POSTURE_REGEN_DELAY, 1.0)
	assert_near(PlayerData.POSTURE_REGEN_PER_SEC, 20.0)
	# §5
	assert_near(PlayerData.SPEED_WALK, 100.0)
	assert_near(PlayerData.SPEED_RUN, 160.0)
	assert_near(PlayerData.SPEED_LOCKED, 85.0)
	assert_near(PlayerData.SPEED_BLOCK, 50.0)
	assert_near(PlayerData.SPEED_CHARGE, 40.0)
	assert_near(PlayerData.SPEED_HEAL, 30.0)
	assert_near(PlayerData.ACCEL_TIME, 0.08)
	assert_near(PlayerData.DECEL_TIME, 0.06)
	# §3、§6
	assert_near(PlayerData.INPUT_BUFFER, 0.15)
	assert_near(PlayerData.PERFECT_WINDOW, 0.15)
	assert_near(PlayerData.REARM_TIME, 0.3)
	assert_near(PlayerData.BLOCK_ARC_DEG, 180.0)
	assert_near(PlayerData.BLOCK_PUSHBACK, 8.0)
	# §7
	assert_near(PlayerData.DODGE_DISTANCE, 56.0)
	assert_near(PlayerData.DODGE_TIME, 0.18)
	assert_near(PlayerData.DODGE_INVULN_START, 0.02)
	assert_near(PlayerData.DODGE_INVULN_END, 0.16)
	assert_near(PlayerData.DODGE_RECOVERY, 0.12)
	assert_near(PlayerData.DODGE_INTERVAL, 0.5)
	# §8
	assert_near(PlayerData.ATTACK_ARC_DEG, 100.0)
	assert_near(PlayerData.ATTACK_RADIUS, 40.0)
	assert_near(PlayerData.CANCEL_DELAY, 0.05)
	assert_near(PlayerData.COMBO_GRACE, 0.2)
	assert_near(PlayerData.FINISHER_END_LAG, 0.2)
	assert_near(PlayerData.CHARGE_TIME, 0.9)
	assert_near(PlayerData.THRUST_DISTANCE, 120.0)  # 2026-10-05 重擊加強（原 72）
	assert_near(PlayerData.THRUST_TIME, 0.25)  # 原 0.2
	# §9
	# 2026-09-30 畫面拉遠到 960×540，鎖定距離 ×1.5（半個畫面寬）；tuning-log
	assert_near(PlayerData.LOCK_ACQUIRE_RANGE, 480.0)
	assert_near(PlayerData.LOCK_BREAK_RANGE, 630.0)
	assert_near(PlayerData.AIM_ASSIST_ARC_DEG, 60.0)
	assert_near(PlayerData.AIM_ASSIST_RANGE, 80.0)
	# §10
	assert_near(PlayerData.STAGGER_TIME, 0.35)
	assert_near(PlayerData.STAGGER_KNOCKBACK, 12.0)
	assert_near(PlayerData.KNOCKDOWN_KNOCKBACK, 24.0)
	assert_near(PlayerData.KNOCKDOWN_DOWN, 0.8)
	assert_near(PlayerData.LAUNCH_DISTANCE, 64.0)
	assert_near(PlayerData.LAUNCH_TIME, 0.35)
	assert_near(PlayerData.LAUNCH_DOWN, 0.6)
	assert_near(PlayerData.GETUP_TIME, 0.5)
	assert_near(PlayerData.POSTURE_BREAK_TIME, 1.2)
	assert_near(PlayerData.DOWN_INVULN_AFTER_GETUP, 0.3)
	# §11.4、§14
	assert_near(PlayerData.EXECUTE_RANGE, 48.0)
	assert_near(PlayerData.EXECUTE_TIME, 1.0)
	assert_near(PlayerData.DEATH_TIME, 1.5)
