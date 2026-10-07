extends SimTestCase
## 主角精靈圖接進遊戲（art-progress「給下一個視窗：把主角精靈圖接進遊戲」）：
## 幀表（KnightSheets，由 tools/sprite_rig/export_frames.py 從產生精靈圖的程式讀出）和戰鬥資料的時間一致；
## 選格（PlayerAnim）照附錄 B 的規則選圖、方向、欄與偏移。

const S := PlayerSim.State
const SH := KnightSheets.SHEETS
const SOUTH := 0
const EAST := 1
const NORTH := 2
const WEST := 3

var anim: PlayerAnim


func before_each() -> void:
	super.before_each()
	anim = PlayerAnim.new()
	sim.boss.pos = Vector2(0, -60)
	sim.player.pos = Vector2(0, 20)
	sim.player.facing = Vector2.UP


## 每個物理幀之後選格（和遊戲一樣：CombatArena 在 sim.step 之後呼叫）
func tick(presses: Array = []) -> void:
	super.tick(presses)
	anim.update(player())


func _durs(key: String) -> Array:
	return SH[key]["durs"]


func _col(key: String, frame_name: String) -> int:
	return PlayerAnim.col_named(key, frame_name)


func _shows(key: String, r: int, c: int, msg := "") -> void:
	assert_eq([anim.sheet, anim.row, anim.col], [key, r, c], msg)


# --- 幀表和戰鬥資料 -------------------------------------------------------------------

func test_every_sheet_matches_its_table() -> void:
	for key: String in SH:
		var t: Dictionary = SH[key]
		var tex: Texture2D = load(t["path"])
		assert_true(tex != null, "%s 載入" % key)
		if tex == null:
			continue
		var cell: Vector2i = t["cell"]
		assert_eq(Vector2i(tex.get_width(), tex.get_height()), Vector2i(cell.x * (t["names"] as Array).size(),
			cell.y * (t["rows"] as Array).size()), "%s 的大小 ＝ 格子 × 欄 × 列" % key)
		var anchor: Vector2i = t["anchor"]
		# 兩種畫格（2026-09-27 定案）的腳底都在畫格中心下方 25px；處決（2026-10-05）的畫格往上加高，躍起的高度畫在圖裡，
		# 腳底仍在畫格底下 11px、左右置中
		var want := Vector2i(28, 53) if cell == Vector2i(56, 56) else Vector2i(44, 61)
		if key == "execute":
			want = Vector2i(44, cell.y - 11)
		assert_eq(anchor, want, "%s 的腳底對齊點" % key)


func test_attack_frames_tile_each_stage() -> void:
	var attacks := PlayerData.light_attacks()
	for i in attacks.size():
		var a: PlayerAttackData = attacks[i]
		var t: Dictionary = SH["attack%d" % (i + 1)]
		var firsts: Array = t["first"]
		var durs: Array = t["durs"]
		assert_eq(PlayerAnim.durs_sum(durs, 0, firsts.size()), a.total_frames(), "第 %d 段的畫格鋪滿程式的長度" % (i + 1))
		var acc := 0
		for c in firsts.size():
			assert_eq(int(firsts[c]), acc, "第 %d 段 %s 從第 %d 幀開始" % [i + 1, t["names"][c], acc])
			assert_near(float(t["adv"][c]), PlayerAnim.attack_advance(a, acc), 0.001, "第 %d 段 %s 畫在程式前進後的位置" % [i + 1, t["names"][c]])
			acc += int(durs[c])
		assert_true(firsts.has(a.startup_frames()), "第 %d 段有一張從判定第一幀開始（接觸）" % (i + 1))
		if i == 0:
			assert_eq(int(t["entry_col"]), -1, "第 1 段沒有從站姿的開頭")
		else:
			assert_eq(int(t["entry_col"]), firsts.size(), "第 %d 段從站姿的開頭在最後一欄" % (i + 1))
			assert_eq(int(durs[firsts.size()]), int(durs[0]), "從站姿的開頭和 f1 同樣長")


func test_timed_actions_match_program_lengths() -> void:
	assert_eq(PlayerAnim.durs_sum(_durs("thrust")), Frames.of(PlayerData.THRUST_TIME) + Frames.of(PlayerData.heavy_thrust().recovery), "突刺")
	assert_eq(PlayerAnim.durs_sum(_durs("thrust"), 0, 2), Frames.of(PlayerData.THRUST_TIME), "突刺：蹬地、前撲 ＝ 判定與位移")
	assert_eq(PlayerAnim.durs_sum(_durs("execute")), Frames.of(PlayerData.EXECUTE_TIME), "處決 3 秒")
	var dodge_total := Frames.of(PlayerData.DODGE_TIME) + Frames.of(PlayerData.DODGE_RECOVERY)
	for key: String in ["dash", "backstep"]:
		assert_eq(PlayerAnim.durs_sum(_durs(key)), dodge_total, key)
		assert_eq(PlayerAnim.durs_sum(_durs(key), 0, 2), Frames.of(PlayerData.DODGE_TIME), "%s：位移期間兩張" % key)
	assert_eq(PlayerAnim.durs_sum(_durs("heal")), Frames.of(PlayerData.HEAL_TIME), "治療（程式值 70 幀）")
	assert_eq(PlayerAnim.durs_sum(_durs("stagger")), Frames.of(PlayerData.STAGGER_TIME), "踉蹌")
	assert_eq(PlayerAnim.durs_sum(_durs("knockdown")), Frames.of(PlayerData.KNOCKDOWN_DOWN), "倒地")
	assert_eq(KnightSheets.LAUNCH_AIR, Frames.of(PlayerData.LAUNCH_TIME), "擊飛空中")
	var launch_down := 0
	for entry: Array in KnightSheets.LAUNCH_DOWN:
		launch_down += int(entry[1])
		assert_true(_col("knockdown", entry[0]) >= 0, "擊飛落地用倒地的 %s" % entry[0])
	assert_eq(launch_down, Frames.of(PlayerData.LAUNCH_DOWN), "擊飛後倒地")
	var death := 0
	for entry: Array in KnightSheets.DEATH:
		death += int(entry[1])
		assert_true(_col("knockdown", entry[0]) >= 0, "死亡用倒地的 %s" % entry[0])
	assert_eq(death, Frames.of(PlayerData.DEATH_TIME), "死亡")
	assert_eq(PlayerAnim.durs_sum(_durs("getup_floor")) + PlayerAnim.durs_sum(_durs("getup")), Frames.of(PlayerData.GETUP_TIME), "起身")
	var gb := _durs("guard_break")
	var sway := Frames.of(PlayerData.POSTURE_BREAK_TIME) - PlayerAnim.durs_sum(gb, 0, 3) - PlayerAnim.durs_sum(gb, 7, 9)
	assert_eq(sway % PlayerAnim.durs_sum(gb, 3, 7), 0, "架勢崩潰：搖晃剛好整輪")
	assert_true(sway > 0)
	var deflect := int(_durs("guard")[5]) - FeedbackData.hitstop_frames(&"perfect_parry")
	assert_eq(deflect, 6, "彈返：頓幀 5 幀加 6 幀")
	assert_true(PlayerAnim.durs_sum(_durs("charge"), 0, 2) < Frames.of(PlayerData.CHARGE_TIME), "蓄力進入比蓄滿短")


# --- 方向 --------------------------------------------------------------------------

func test_view_of_directions() -> void:
	assert_eq(PlayerAnim.view_of(Vector2.DOWN), SOUTH)
	assert_eq(PlayerAnim.view_of(Vector2.RIGHT), EAST)
	assert_eq(PlayerAnim.view_of(Vector2.UP), NORTH)
	assert_eq(PlayerAnim.view_of(Vector2.LEFT), WEST)
	assert_eq(PlayerAnim.view_of(Vector2(1, 1).normalized()), EAST, "正斜角算側面")
	assert_eq(PlayerAnim.view_of(Vector2(-0.5, -1)), NORTH)


func test_diagonal_keeps_the_previous_view() -> void:
	advance(1)
	_shows("idle", NORTH, 0, "面向上：朝上那一列")
	move = Vector2(1, -1)
	advance(1)
	assert_eq(anim.row, NORTH, "從朝上按右上：保持朝上（斜角附近不換）")
	move = Vector2.RIGHT
	advance(1)
	assert_eq(anim.row, EAST)
	move = Vector2(1, -1)
	advance(1)
	assert_eq(anim.row, EAST, "從朝右按右上：保持朝右")
	move = Vector2(0.3, -1)
	advance(1)
	assert_eq(anim.row, NORTH, "離斜角夠遠就換")


func test_step_kind_relative_to_facing() -> void:
	assert_eq(PlayerAnim.step_kind(Vector2.UP, Vector2.UP), "fwd")
	assert_eq(PlayerAnim.step_kind(Vector2.UP, Vector2.DOWN), "back")
	assert_eq(PlayerAnim.step_kind(Vector2.UP, Vector2.LEFT), "side", "面向上時往左是角色的左邊")
	assert_eq(PlayerAnim.step_kind(Vector2.UP, Vector2.RIGHT), "rside")
	assert_eq(PlayerAnim.step_kind(Vector2.DOWN, Vector2.RIGHT), "side", "面向鏡頭時往畫面右邊是角色的左邊")


# --- 待機、走、跑 ------------------------------------------------------------------------

func test_idle_breathes_every_12_frames() -> void:
	advance(1)
	_shows("idle", NORTH, 0)
	advance(12)
	assert_eq(anim.col, 1)
	advance(36)
	assert_eq(anim.col, 0, "四個階段一輪 48 幀")


func test_walk_cycle_two_sim_frames_a_frame_at_full_speed() -> void:
	move = Vector2.RIGHT
	advance(1)
	_shows("walk", EAST, 1, "從站著起步：走路第 1 張")
	advance(20)  # 加速完成
	var cols: Array = []
	for i in 18:
		advance(1)
		cols.append(anim.col)
	assert_ne_seq(cols)
	# 全速時每張停 2 模擬幀：頭尾以外，每一段相同的欄剛好 2 幀
	var runs: Array = []
	var n := 1
	for i in range(1, cols.size()):
		if cols[i] == cols[i - 1]:
			n += 1
		else:
			runs.append(n)
			n = 1
	runs.pop_front()
	assert_eq(runs, [2, 2, 2, 2, 2, 2, 2, 2], "全速時每張停 2 模擬幀：%s" % [cols])
	move = Vector2.ZERO
	advance(8)
	_shows("idle", EAST, 0, "停下之後回待機")


## 16 幀裡每一張都出現過（8 張的循環）
func assert_ne_seq(cols: Array) -> void:
	for c in range(1, 9):
		assert_true(cols.has(c), "循環的第 %d 張出現：%s" % [c, cols])


func test_slow_walk_holds_frames_longer() -> void:
	move = Vector2.RIGHT * 0.5
	advance(20)
	var changes := 0
	var last := anim.col
	for i in 40:
		advance(1)
		if anim.col != last:
			changes += 1
			last = anim.col
	assert_eq(changes, 10, "半速時每張停 4 模擬幀（腳不滑）")


func test_locked_walk_picks_by_direction_to_target() -> void:
	player().locked = true
	move = Vector2.DOWN
	advance(1)
	assert_eq([anim.sheet, anim.row, anim.col], ["walk_locked", NORTH, _col("walk_locked", "back 1")], "鎖定往後退：後退那一組，面向目標")
	move = Vector2.LEFT
	advance(1)
	assert_eq(anim.sheet, "walk_locked")
	assert_between(anim.col, _col("walk_locked", "side 1"), _col("walk_locked", "side 4"), "往角色的左邊側移")
	move = Vector2.UP
	advance(1)
	assert_eq(anim.sheet, "walk", "往前走用一般的走路")


func test_run_starts_from_standing_and_stops() -> void:
	held["run"] = true
	move = Vector2.RIGHT
	var s1 := _col("run", "起跑 1")
	advance(1)
	_shows("run", EAST, s1)
	advance(2)
	_shows("run", EAST, s1 + 1)
	advance(2)
	_shows("run", EAST, int(KnightSheets.RUN_START_PHASE["east"]), "起跑兩張之後接循環")
	advance(30)
	assert_true(anim.col < 8, "跑步循環")
	move = Vector2.ZERO
	var seen: Array = []
	for i in 20:
		advance(1)
		seen.append(anim.col)
	var stop2 := _col("run", "停步 2")
	assert_true(seen.has(_col("run", "停步 1A")) or seen.has(_col("run", "停步 1B")), "放開：停步 1 %s" % [seen])
	assert_true(seen.has(stop2) and seen.has(stop2 + 1), "停步 2、3：%s" % [seen])
	assert_eq(anim.sheet, "idle", "停步之後回待機")


func test_action_during_the_run_stop_cancels_it() -> void:
	held["run"] = true
	move = Vector2.RIGHT
	advance(20)
	# 在不能直接接停步的那幾張放開（朝右第 4、5 張都不能接：放開後還要再跑一兩張）
	var table: Array = KnightSheets.RUN_STOP_FROM["east"]
	assert_eq([table[3], table[4]], ["", ""])
	for i in 16:
		if anim.col == 3:
			break
		advance(1)
	assert_eq(anim.col, 3)
	move = Vector2.ZERO
	advance(1)
	assert_eq([anim.sheet, anim.col], ["run", 4], "放開：先跑完下一張")
	press(&"attack")
	assert_eq(anim.sheet, "attack1", "停步中出招：直接出招")
	advance(25)
	assert_eq(player().state, S.ATTACK)
	advance(1)
	assert_eq(player().state, S.IDLE)
	_shows("idle", EAST, 0, "出招之後回待機，不再接回停步")


func test_walking_into_a_run_skips_the_start() -> void:
	move = Vector2.RIGHT
	advance(10)
	held["run"] = true
	advance(1)
	assert_true(anim.sheet == "run" and anim.col < 8, "走路中開始跑：直接接循環")


# --- 輕攻擊 --------------------------------------------------------------------------

func test_attack_frames_follow_the_stage_and_catch_up_on_change() -> void:
	press(&"attack")
	var t: Dictionary = SH["attack1"]
	_shows("attack1", NORTH, 0, "第 1 段 f1")
	var a := player().attack
	for e in range(1, 26):
		advance(1)
		var c := PlayerAnim.span_col(t["durs"], e, 0, (t["first"] as Array).size())
		_shows("attack1", NORTH, c, "第 %d 幀" % e)
		var expect := -player().facing * (PlayerAnim.attack_advance(a, e) - float(t["adv"][c]))
		assert_true(anim.offset.is_equal_approx(expect), "第 %d 幀的偏移 %s" % [e, anim.offset])
		if e == int(t["first"][c]):
			assert_true(anim.offset.is_zero_approx(), "換圖那一幀畫面跟上程式（第 %d 幀）" % e)


func test_mashed_chain_plays_the_normal_first_frame() -> void:
	press(&"attack")
	advance(12)
	press(&"attack")  # 第 13 幀按下：緩衝，最早接段幀接第 2 段
	advance(PlayerData.chain_frame(0) - 13)
	assert_eq(player().combo_index, 1, "連按：第 2 段")
	assert_eq(player().state_elapsed(), 0)
	_shows("attack2", NORTH, 0, "連按接段播本來的 f1")


func test_late_chain_plays_the_entry_from_the_stance() -> void:
	press(&"attack")
	advance(19)
	assert_true(String(SH["attack1"]["names"][anim.col]).contains("回站姿"), "第 1 段在回站姿")
	press(&"attack")
	assert_eq(player().combo_index, 1)
	_shows("attack2", NORTH, int(SH["attack2"]["entry_col"]), "從回站姿接段：從站姿的開頭")
	advance(2)
	_shows("attack2", NORTH, 1, "開頭之後照常")


func test_grace_chain_plays_the_entry_from_the_stance() -> void:
	press(&"attack")
	advance(26)
	assert_eq(player().state, S.IDLE)
	assert_true(player().in_combo_grace())
	press(&"attack")
	assert_eq(player().combo_index, 1, "寬限中接第 2 段")
	_shows("attack2", NORTH, int(SH["attack2"]["entry_col"]))


func test_first_stage_from_idle_has_no_entry() -> void:
	advance(30)
	press(&"attack")
	_shows("attack1", NORTH, 0)


# --- 閃身 --------------------------------------------------------------------------

func test_dodge_without_input_is_a_backstep_facing_forward() -> void:
	press(&"dodge")
	_shows("backstep", NORTH, 0, "沒有輸入往後閃：後跳，朝面向")
	advance(11)
	_shows("backstep", NORTH, _col("backstep", "落地 1"))


func test_dodge_with_input_dashes_toward_it() -> void:
	move = Vector2.RIGHT
	press(&"dodge")
	_shows("dash", EAST, 0)
	advance(11)
	_shows("dash", EAST, _col("dash", "煞停 1"), "往前閃：煞停")


func test_locked_side_dodge_dashes_sideways_and_lands_facing_the_target() -> void:
	player().locked = true
	move = Vector2.RIGHT
	press(&"dodge")
	assert_true(player().facing.is_equal_approx(Vector2.UP), "鎖定：面向目標")
	_shows("dash", EAST, 0, "衝刺畫閃身方向")
	advance(11)
	_shows("backstep", NORTH, _col("backstep", "落地 1"), "收招轉回面向、用落地")


# --- 格擋 --------------------------------------------------------------------------

func _light_hit() -> BossHitData:
	return VeltharisData.move(1, &"quick_combo_3").hits[0]


func test_guard_holds_and_breathes() -> void:
	held["block"] = true
	advance(1)
	_shows("guard", NORTH, 0)
	advance(12)
	_shows("guard", NORTH, 1)


func test_perfect_parry_deflects_then_returns() -> void:
	held["block"] = true
	advance(2)
	assert_eq(sim.apply_boss_hit(_light_hit(), sim.boss.pos), CombatSim.BlockResult.PERFECT)
	anim.update(player())
	_shows("guard", NORTH, 5, "結算在模擬的一步之外：同一個戰鬥幀照新狀態重選，頓幀時已經是撥開")
	var cols: Array = []
	for i in 12:
		advance(1)
		cols.append(anim.col)
	assert_eq(cols, [5, 5, 5, 5, 5, 6, 6, 7, 7, 0, 0, 0], "撥開 6 戰鬥幀（加上頓幀 5 幀）、收回兩張各 2 幀、回格擋")


func test_normal_block_shows_the_hit_frame() -> void:
	held["block"] = true
	advance(12)
	assert_eq(sim.apply_boss_hit(_light_hit(), sim.boss.pos), CombatSim.BlockResult.BLOCKED)
	advance(1)
	_shows("guard", NORTH, 4, "普通格擋受力")
	advance(5)
	assert_ne_col(4)


func assert_ne_col(c: int) -> void:
	assert_true(anim.col != c, "不再是第 %d 欄" % c)


func test_guard_walk_sidesteps() -> void:
	held["block"] = true
	advance(1)
	move = Vector2.RIGHT
	advance(1)
	assert_eq([anim.sheet, anim.row, anim.col], ["guard_walk", NORTH, _col("guard_walk", "rside 1")],
		"未鎖定格擋時面向固定，往右是角色的右邊側移")


# --- 蓄力、治療 ----------------------------------------------------------------------

func test_charge_in_hold_and_early_release() -> void:
	press(&"heavy")
	_shows("charge", NORTH, 0)
	advance(4)
	_shows("charge", NORTH, 2, "按住：顫動第 1 階段")
	advance(3)
	_shows("charge", NORTH, 3)
	held["heavy"] = false
	advance(1)
	assert_eq(player().state, S.IDLE)
	_shows("charge", NORTH, 6, "沒蓄滿放開：收勢")
	advance(2)
	_shows("charge", NORTH, 7)
	advance(2)
	_shows("idle", NORTH, 0)


func test_heal_timeline_and_walk() -> void:
	press(&"heal")
	_shows("heal", NORTH, 0)
	advance(8)
	_shows("heal", NORTH, 2, "按住")
	move = Vector2.RIGHT
	advance(1)
	assert_eq(anim.sheet, "heal_walk", "治療中移動：治療移動")


# --- 受擊 --------------------------------------------------------------------------

func test_stagger_faces_the_attacker() -> void:
	sim.boss.pos = Vector2(80, 20)
	player().facing = Vector2.UP
	sim.apply_boss_hit(_light_hit(), sim.boss.pos)
	advance(1)
	_shows("stagger", EAST, 0, "朝攻擊來源畫（Boss 在右）")
	advance(4)
	_shows("stagger", EAST, 1)


func test_knockdown_rows_and_getup() -> void:
	sim.boss.pos = Vector2(-80, 20)
	player().facing = Vector2.DOWN
	sim.apply_boss_hit(VeltharisData.move(1, &"oath_cleave").hits[0], sim.boss.pos)
	advance(1)
	_shows("knockdown", PlayerAnim.ROW_ATTACKER_LEFT, 0, "攻擊者在左")
	advance(12)
	_shows("knockdown", PlayerAnim.ROW_ATTACKER_LEFT, _col("knockdown", "趴著"))
	assert_true(anim.lying)
	advance(48 - 13)
	assert_eq(player().state, S.GETUP)
	_shows("getup_floor", PlayerAnim.ROW_ATTACKER_LEFT, 0)
	advance(17)
	_shows("getup", SOUTH, 0, "跪姿換回程式的面向")


func test_launch_arcs_then_lands() -> void:
	sim.boss.pos = Vector2(80, 20)
	sim.apply_boss_hit(VeltharisData.move(1, &"royal_sweep").hits[0], sim.boss.pos)
	advance(10)
	assert_eq(anim.sheet, "launch")
	assert_eq(anim.row, PlayerAnim.ROW_ATTACKER_RIGHT)
	assert_true(anim.offset.y < -10.0, "空中：畫面上抬高 %s" % anim.offset)
	advance(11)
	assert_eq(player().state, S.DOWN)
	_shows("knockdown", PlayerAnim.ROW_ATTACKER_RIGHT, _col("knockdown", "著地"), "擊飛落地直接著地，不重播摔倒")
	advance(3)
	assert_eq(anim.col, _col("knockdown", "趴著"))


func test_death_plays_the_fall_slower() -> void:
	player().hp = 1
	sim.boss.pos = Vector2(80, 20)
	sim.apply_boss_hit(_light_hit(), sim.boss.pos)
	assert_eq(player().state, S.DEAD)
	advance(1)
	_shows("knockdown", PlayerAnim.ROW_ATTACKER_RIGHT, 0)
	advance(4)
	assert_eq(anim.col, 1, "死亡：每張 4 幀")
	advance(20)
	assert_eq(anim.col, _col("knockdown", "趴著"))


func test_posture_break_sways_twice() -> void:
	player().posture = 1.0
	held["block"] = true
	advance(12)
	sim.apply_boss_hit(_light_hit(), sim.boss.pos)
	assert_eq(player().state, S.POSTURE_BREAK)
	advance(1)
	_shows("guard_break", NORTH, 0)
	advance(12)
	assert_eq(anim.col, 3, "搖晃 1")
	advance(24)
	assert_eq(anim.col, 3, "第二輪搖晃 1")
	advance(24)
	assert_eq(anim.col, 7, "撐起")


## 躍起下刺（2026-10-05）：插下去、轉劍、蹬開、落地都是新的一張，從遊戲的那一幀開始
func test_execution_frames_meet_the_game_beats() -> void:
	var durs := _durs("execute")
	var starts := {}
	var acc := 0
	for d: int in durs:
		starts[acc] = true
		acc += d
	var beats := {"插下去": Frames.of(PlayerData.EXECUTE_HIT_TIME), "蹬開": Frames.of(PlayerData.EXECUTE_KICK_TIME),
		"落地": Frames.of(PlayerData.EXECUTE_LAND_TIME), "起跳": Frames.of(PlayerData.EXECUTE_LEAP_TIME)}
	for i in PlayerData.execute_twist_frames().size():
		beats["轉劍 %d" % (i + 1)] = PlayerData.execute_twist_frames()[i]
	for name: String in beats:
		assert_true(starts.has(beats[name]), "%s（第 %d 幀）換一張" % [name, beats[name]])
	var lift: Array = SH["execute"]["lift"]
	assert_eq(lift.size(), durs.size(), "每一張都有離地高度")
	assert_eq(int(lift[0]), 0, "從地上開始")
	assert_eq(int(lift[lift.size() - 1]), 0, "落在地上")
	var hit_col := PlayerAnim.span_col(durs, Frames.of(PlayerData.EXECUTE_HIT_TIME))
	assert_true(int(lift[hit_col]) >= 60, "插下去時躍到 Boss 肩頭的高度：%d" % int(lift[hit_col]))
	assert_eq(int(lift[PlayerAnim.span_col(durs, Frames.of(PlayerData.EXECUTE_LAND_TIME))]), 0, "2.5 秒落地")


# --- 畫面 --------------------------------------------------------------------------

func test_silhouette_only_when_behind_the_boss() -> void:
	var PV: GDScript = load("res://scripts/view/player_view.gd")
	var BV: GDScript = load("res://scripts/view/boss_view.gd")
	var boss_feet := Vector2(0, 0)
	var standing: Rect2 = BV.body_rect(sim.boss)
	assert_true(PV.hidden_by_boss(Vector2(0, -30), boss_feet, standing), "Boss 正後方：被擋住，畫剪影")
	assert_false(PV.hidden_by_boss(Vector2(0, 30), boss_feet, standing), "Boss 前方：主角畫在 Boss 上面")
	assert_false(PV.hidden_by_boss(Vector2(60, -30), boss_feet, standing), "Boss 後方但錯開：看得到")
	assert_false(PV.hidden_by_boss(Vector2(0, -200), boss_feet, standing), "遠在 Boss 後面：不重疊")
	# 被處決時 Boss 跪著（美術的跪姿，2026-10-05 接進遊戲；之前的佔位圖形是橫躺）：畫出來的範圍比站著矮，
	# 站在跪著的頭頂上方的主角看得到，Boss 站著時同一個位置會被擋住
	sim.boss.enter_state(BossSim.State.EXECUTED)
	var kneel: Rect2 = BV.body_rect(sim.boss)
	assert_true(kneel.position.y > standing.position.y + 20, "跪著比站著矮：%s / %s" % [kneel, standing])
	var behind := Vector2(0, kneel.position.y - 1)
	assert_false(PV.hidden_by_boss(behind, boss_feet, kneel), "Boss 跪著：擋不住在他頭頂後方的主角")
	assert_true(PV.hidden_by_boss(behind, boss_feet, standing), "同一個位置，Boss 站著時擋住")


func test_view_draws_the_selected_cell() -> void:
	var tree := Engine.get_main_loop() as SceneTree
	var arena: CombatArena = (load("res://scenes/levels/combat_arena.tscn") as PackedScene).instantiate()
	tree.root.add_child(arena)
	arena.sim.player.facing = Vector2.RIGHT
	arena.sim.step(InputFrame.new())
	arena.player_view.sim_stepped()
	arena.player_view._process(1.0 / 60.0)
	var body: Sprite2D = arena.player_view.body
	assert_eq(body.texture.resource_path, "res://assets/sprites/player/knight_idle.png")
	assert_eq(body.region_rect, Rect2(0, 56, 56, 56), "待機朝右：第 2 列第 1 欄")
	assert_eq(body.offset, Vector2(-28, -53), "腳底對齊點在節點位置")
	arena.get_parent().remove_child(arena)
	arena.free()
