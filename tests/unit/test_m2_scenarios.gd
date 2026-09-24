extends SimTestCase
## M2 模擬玩家（plan §6.3）：用腳本控制的玩家對木樁跑完整情境，檢查扣血、削韌與動作順序。

const S := PlayerSim.State


## 狂按攻擊：每 2 幀按一次，連打 10 秒。四段一輪，每輪 70 傷害、12 削韌，段數依序 1→2→3→4→1…
func test_mash_attack_cycles_through_four_stages() -> void:
	place_near_boss(46.0)
	var stages: Array[int] = []
	var hits := 0
	for i in 660:
		tick([&"attack"] if i % 2 == 0 and i < 600 else [])
		for e in sim.events:
			if e["type"] == &"player_attack":
				stages.append(e["stage"])
			elif e["type"] == &"boss_hit":
				hits += 1
	assert_true(stages.size() >= 12, "10 秒內至少 3 輪（實際 %d 段）" % stages.size())
	for i in stages.size():
		assert_eq(stages[i], i % 4, "第 %d 次出招應是第 %d 段" % [i + 1, i % 4 + 1])
	assert_eq(hits, stages.size(), "每段都打中")
	var dmg_table: Array[int] = [0, 15, 30, 45]
	var tough_table: Array[int] = [0, 2, 4, 6]
	var full_cycles := floori(hits / 4.0)
	var rem := hits % 4
	assert_eq(VeltharisData.MAX_HP - boss().hp, full_cycles * 70 + dmg_table[rem], "傷害 = 完整輪數 × 70 + 零頭")
	var expected_tough := float(full_cycles * 12 + tough_table[rem])
	assert_near(VeltharisData.MAX_TOUGHNESS - boss().toughness, minf(expected_tough, 100.0), 0.001)


## 兩段後用閃身取消，再打：閃身一定發生在第 2 段判定結束 3 幀後（最早的取消點）
func test_combo_dodge_cancel_loop() -> void:
	place_near_boss(46.0)
	var dodge_elapsed: Array[int] = []
	for i in 400:
		var presses: Array = []
		if player().state == S.IDLE or (player().state == S.ATTACK and player().combo_index == 0):
			presses.append(&"attack")
		elif player().state == S.ATTACK and player().combo_index == 1:
			presses.append(&"dodge")
		var before_state := player().state
		var before_elapsed := player().state_elapsed()
		tick(presses)
		if before_state == S.ATTACK and player().state == S.DODGE:
			dodge_elapsed.append(before_elapsed + 1)
		move = Vector2.UP if player().state == S.IDLE else Vector2.ZERO  # 閃身後走回木樁
	assert_true(dodge_elapsed.size() >= 3, "至少取消 3 次（實際 %d）" % dodge_elapsed.size())
	var a: PlayerAttackData = PlayerData.light_attacks()[1]
	for d in dodge_elapsed:
		assert_eq(d, a.active_end_frame() + Frames.of(PlayerData.CANCEL_DELAY), "取消發生在判定結束 3 幀後")


## 完整情境：從出生點鎖定 → 走近 → 四段連擊 → 往後閃 → 蓄力突刺
func test_full_m2_routine_from_spawn() -> void:
	assert_eq(sim.player.pos, ArenaGeometry.PLAYER_SPAWN)
	press(&"lock")
	assert_true(player().locked, "出生點距離 Boss %.0fpx，可以鎖定" % sim.player.pos.distance_to(sim.boss.pos))
	# 走近到 50px
	move = Vector2.UP
	while sim.player.pos.distance_to(sim.boss.pos) > 50.0:
		advance(1)
	move = Vector2.ZERO
	advance(4)
	# 四段連擊（能接就接）
	var guard := 0
	press(&"attack")
	while guard < 300 and not (player().state == S.IDLE):
		guard += 1
		if player().can_start(&"attack") and player().state == S.ATTACK:
			press(&"attack")
		else:
			advance(1)
	assert_eq(VeltharisData.MAX_HP - boss().hp, 70, "四段連擊 70")
	assert_near(VeltharisData.MAX_TOUGHNESS - boss().toughness, 12.0, 0.001, "四段連擊削韌 12")
	# 往後閃（鎖定中遠離目標）
	var d0 := sim.player.pos.distance_to(sim.boss.pos)
	press(&"dodge")
	advance(20)
	assert_near(sim.player.pos.distance_to(sim.boss.pos) - d0, 56.0, 0.5, "往後閃 56px")
	# 蓄力突刺
	press(&"heavy")
	advance(60)
	held["heavy"] = false
	advance(50)
	assert_eq(VeltharisData.MAX_HP - boss().hp, 70 + 60, "加上重擊 60")
	assert_near(VeltharisData.MAX_TOUGHNESS - boss().toughness, 12.0 + 15.0, 0.001, "加上削韌 15")
	assert_true(player().locked, "全程保持鎖定")
