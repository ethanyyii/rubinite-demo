extends SimTestCase
## M6：打擊感與調校（plan §7、§8 M6）。
## - 頓幀只停戰鬥模擬，不影響 UI（HUD、鏡頭震動）與輸入緩衝（CLAUDE.md）；
## - 輸入延遲：每個動作都在按下的同一個物理幀開始（≤ 1 幀）；
## - 破韌節奏（combat-design §11.3 調參目標）：只靠彈返約 2–3 套、只靠攻擊約 8–10 次四段。

const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -60)
	sim.player.pos = Vector2(0, 60)
	sim.player.facing = Vector2.UP


# --- 頓幀不影響 UI ---------------------------------------------------------------

func _make_arena() -> Node2D:
	var tree := Engine.get_main_loop() as SceneTree
	var arena: Node2D = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)
	return arena


func _free_arena(arena: Node2D) -> void:
	arena.get_parent().remove_child(arena)
	arena.free()


func test_hitstop_does_not_pause_hud_or_camera() -> void:
	var arena := _make_arena()
	var s: CombatSim = arena.sim
	s.boss.set_dummy()
	# 玩家被打（HP 立刻下降），同時進入很長的頓幀
	s.player.hp -= 20
	s.hitstop = 30
	arena.camera.add_shake(6.0, 0.25)
	var cf := s.combat_frame
	var trail0: float = arena.hud._player_hp_trail
	for i in 10:
		arena._physics_process(1.0 / 60.0)
		arena.hud._process(1.0 / 60.0)
		arena.camera._process(1.0 / 60.0)
	assert_eq(s.combat_frame, cf, "頓幀期間戰鬥幀停住")
	assert_true(s.hitstop > 0, "還在頓幀中")
	assert_true(arena.hud._player_hp_trail < trail0, "頓幀期間 HUD 的殘影條照常往下追")
	assert_true(arena.camera._shake_left < 0.25, "頓幀期間鏡頭震動照常衰減（實際時間）")
	assert_near(Engine.time_scale, 1.0, 0.0001, "頓幀不是用 time_scale 做的")
	assert_false(arena.get_tree().paused, "頓幀不是用暫停場景樹做的")
	assert_true(arena.hud.can_process() and arena.camera.can_process(), "頓幀期間 HUD 與鏡頭照常處理")
	_free_arena(arena)


func test_buffered_dodge_survives_long_hitstop() -> void:
	# 輸入緩衝 9 幀以戰鬥幀計；頓幀再長也不會讓緩衝過期
	sim.boss.set_dummy()
	place_near_boss(46.0)
	press(&"attack")
	while sim.hitstop == 0:
		tick()
	sim.hitstop = 30  # 拉長成 30 幀（遠超過緩衝的 9 幀）
	tick([&"dodge"])  # 頓幀第一幀按閃身
	var waited := 1
	while sim.hitstop > 0:
		tick()
		waited += 1
	assert_true(waited >= 30, "頓幀期間經過了 %d 個物理幀" % waited)
	var guard := 0
	while player().state == S.ATTACK and guard < 60:
		advance(1)
		guard += 1
	assert_eq(player().state, S.DODGE, "頓幀中按的閃身在取消點生效")


# --- 輸入延遲 ≤ 1 幀（plan §7） -----------------------------------------------------

func test_every_action_starts_on_the_frame_it_is_pressed() -> void:
	var cases := {
		&"attack": S.ATTACK,
		&"dodge": S.DODGE,
		&"heal": S.HEAL,
	}
	for action: StringName in cases:
		before_each()
		sim.player.hp = 30
		press(action)
		assert_eq(player().state, cases[action], "%s：按下的同一幀開始" % action)
	# 格擋：按住的同一幀
	before_each()
	held["block"] = true
	advance(1)
	assert_eq(player().state, S.BLOCK, "格擋：按下的同一幀開始")
	# 蓄力：按下重擊鍵的同一幀
	before_each()
	tick([&"heavy"])
	assert_eq(player().state, S.CHARGE, "蓄力：按下的同一幀開始")
	# 鎖定：按下的同一幀
	before_each()
	press(&"lock")
	assert_true(player().locked, "鎖定：按下的同一幀")


# --- 破韌節奏（combat-design §11.3；數值依 tuning-log） ----------------------------

func test_attack_only_breaks_in_8_to_10_combos() -> void:
	var combos := PacingProbe.combos_to_break_by_attack(0.0)
	assert_between(combos, 8.0, 10.0, "只靠攻擊（連續四段）：%.2f 次" % combos)
	combos = PacingProbe.combos_to_break_by_attack(1.0)
	assert_between(combos, 8.0, 10.0, "只靠攻擊（每套間隔 1 秒）：%.2f 次" % combos)


func test_parry_only_breaks_in_about_3_sets() -> void:
	# 兩組相隔很遠的種子各 12 個，避免只挑到有利的種子
	var total := 0
	var n := 0
	for base in [1, 3000]:
		for i in 12:
			var sets := PacingProbe.sets_to_break_by_parry(base + i)
			assert_true(sets > 0, "種子 %d：只靠彈返也能破韌" % (base + i))
			total += sets
			n += 1
	var avg := float(total) / n
	# 目標「約 2–3 套」。500 個種子的批次結果：平均 2.8–3.1 套（只數可彈返的 2.5–2.7），見 pacing*.json 與 tuning-log
	assert_between(avg, 2.0, 3.5, "只靠彈返：平均 %.2f 套" % avg)
