extends SimTestCase
## Boss 精靈圖接進遊戲（2026-10-05）：幀表（tools/boss_rig/export_game.py 產生）和戰鬥資料對得上——每招的總長、
## 判定開始的那一張、第二階段的收招、延遲版多停的幀數、被彈開的長度、被打斷的對照表；BossAnim 照狀態選格。

const BS := BossSim.State
const SP := preload("res://scripts/view/boss_sprites.gd")

var anim: BossAnim


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -60)
	sim.player.pos = Vector2(0, 40)
	anim = BossAnim.new()
	anim.update(sim.boss)


func _step(n: int) -> void:
	for i in n:
		advance(1)
		anim.update(boss())


func _start(phase: int, id: StringName) -> void:
	sim.boss.phase = phase
	sim.boss.start_move(VeltharisData.move(phase, id))
	anim.update(boss())


func _holds(phase: int, id: StringName) -> Array:
	var mv := SP.move(id)
	var c := SP.clip(mv["sheet"])
	var h: Array = (c["holds_phase2"] if phase == 2 and c.has("holds_phase2") else c["holds"]).duplicate()
	if mv["delayed"] and c.has("delayed"):
		h[int(c["delayed"]["pose"])] = int(h[int(c["delayed"]["pose"])]) + int(c["delayed"]["extra_hold"])
	return h


# --- 幀表和戰鬥資料 --------------------------------------------------------------

func test_every_move_lasts_as_long_as_the_game_plays_it() -> void:
	for phase in [1, 2]:
		var ms := VeltharisData.moves(phase)
		for id: StringName in ms:
			var m: BossMoveData = ms[id]
			assert_false(SP.move(id).is_empty(), "%s 沒有對應的精靈圖" % id)
			assert_eq(SP.total(_holds(phase, id)), m.total_frames(), "第 %d 階段 %s 的長度" % [phase, id])


func test_every_hit_starts_on_its_pose() -> void:
	# 判定開始那一幀，畫的是那一擊砍到的那一張（幀表的 hits；延遲版照 delayed 的 hits）
	for phase in [1, 2]:
		var ms := VeltharisData.moves(phase)
		for id: StringName in ms:
			var m: BossMoveData = ms[id]
			var mv := SP.move(id)
			var c := SP.clip(mv["sheet"])
			var hits: Array = c["delayed"]["hits"] if mv["delayed"] else c["hits"]
			var starts := m.hit_start_frames()
			assert_eq(hits.size(), starts.size(), "%s 的擊數" % id)
			for i in starts.size():
				assert_eq(int(hits[i]["start"]), starts[i], "%s 第 %d 擊開始的幀" % [id, i + 1])


func test_bounces_last_the_bounce() -> void:
	for phase in [1, 2]:
		var ms := VeltharisData.moves(phase)
		for id: StringName in ms:
			var m: BossMoveData = ms[id]
			var b = SP.move(id)["bounce"]
			if m.last_hit().bounce_time <= 0.0:
				continue
			assert_true(b != null, "%s 會被彈開，要有被彈開的圖" % id)
			assert_eq(SP.total(SP.clip(b)["holds"]), Frames.of(m.last_hit().bounce_time), "%s 被彈開的長度" % id)


func test_every_clip_has_four_rows_of_its_poses() -> void:
	var n: int = SP.data()["frames"].size()
	for name: String in SP.data()["clips"]:
		var c := SP.clip(name)
		var holds: Array = c["holds"]
		for d: String in SP.DIRS:
			var ids: Array = c["dirs"][d]
			assert_eq(ids.size(), holds.size(), "%s %s：每一張都有" % [name, d])
			for v in ids:
				assert_true(v == null or (int(v) >= 0 and int(v) < n), "%s %s：格的編號" % [name, d])


func test_interrupt_tables_cover_every_pose() -> void:
	for sheet: String in SP.data()["interrupt"]:
		var it := SP.interrupt(sheet)
		var poses: int = SP.clip(sheet)["holds"].size()
		for kind: String in ["break", "stagger"]:
			if not it.has(kind):
				continue
			var ps: Array = it[kind]["pose_start"]
			assert_eq(ps.size(), poses, "%s %s：每一張都有一格" % [sheet, kind])
			for v in ps:
				assert_true(int(v) >= -1 and int(v) < (it[kind]["starts"] as Array).size())
			for st: String in it[kind]["starts"]:
				assert_true(SP.has_clip(st), "%s 的銜接 %s" % [sheet, st])
		assert_true(it.has("break"), "%s 被打斷時能跪下" % sheet)


# --- 選格 ----------------------------------------------------------------------------

func test_idle_stands_with_the_sword_planted() -> void:
	assert_eq(anim.clip, "idle")
	assert_true(anim.frame_id >= 0)


func test_walk_starts_then_loops_by_distance() -> void:
	sim.player.pos = Vector2(0, 400)
	boss().start_breather(120)
	anim.update(boss())
	assert_eq(anim.clip, "walk_start", "從劍立在地上起步")
	_step(SP.total(SP.clip("walk_start")["holds"]) + 2)
	assert_eq(anim.clip, "walk", "起步播完接循環")
	var c0 := anim.col
	_step(16)   # 走 16 幀＝16px（每幀 1px）＝4 張
	assert_eq(posmod(anim.col - c0, 20), 4, "每 4px 一張")


func test_attack_from_walking_uses_its_start_from_a_move() -> void:
	sim.player.pos = Vector2(0, 400)
	boss().start_breather(60)
	anim.update(boss())
	_step(60)
	assert_eq(anim.clip, "walk")
	sim.player.pos = Vector2(0, 40)
	_start(1, &"royal_sweep")
	assert_true(anim.clip.begins_with("boss_c1_walk_entry_"), "從走路直接出招：%s" % anim.clip)
	_step(SP.clip(anim.clip)["end"])
	assert_eq(anim.clip, "boss_c1", "開頭播完接攻擊本身")


func test_attack_from_standing_starts_on_the_carry() -> void:
	_start(1, &"royal_sweep")
	assert_eq(anim.clip, "boss_c1")
	assert_eq(anim.col, 0)


func test_perfect_parry_plays_the_moves_bounce() -> void:
	_start(1, &"royal_sweep")
	_step(boss().hit_start_frame(0) + 2 - boss().state_elapsed())
	boss().on_parried(boss().move.hits[0])
	anim.update(boss())
	assert_eq(boss().state, BS.BOUNCED)
	assert_eq(anim.clip, "boss_c1_bounce")
	assert_eq(anim.col, 0, "被彈開的第一張就是砍到的那一張")


func test_break_mid_attack_goes_down_by_its_start_then_kneels() -> void:
	_start(1, &"royal_sweep")
	_step(30)
	boss().move = null
	boss().enter_state(BS.BROKEN)
	anim.update(boss())
	assert_true(anim.clip.begins_with("start_"), "被打斷的銜接：%s" % anim.clip)
	var n := SP.total(SP.clip(anim.clip)["holds"])
	_step(n)
	assert_eq(anim.clip, "kneel_down", "銜接之後接 boss_kneel_down")
	assert_eq(anim.col, BossAnim.KNEEL_TAIL[0])
	_step(30)
	assert_eq(anim.clip, "kneel_breathe", "跪著喘")


func test_death_mid_attack_kneels_then_falls_forward() -> void:
	_start(1, &"royal_sweep")
	_step(30)
	boss()._die()
	anim.update(boss())
	assert_true(anim.clip.begins_with("start_"))
	_step(120)
	assert_eq(anim.clip, "death")
	assert_eq(anim.col, BossAnim.DEATH_TAIL[-1], "最後停在往前垂的那一張")
	assert_true(anim.done_at >= 0, "播完（開始化為灰燼）")


func test_stagger_in_recovery_goes_back_to_the_carry() -> void:
	_start(1, &"royal_sweep")
	_step(80)
	assert_true(boss().current_hit_index() < 0, "收招中")
	boss().move = null
	boss().enter_state(BS.STAGGER)
	anim.update(boss())
	assert_true(anim.clip.begins_with("start_"), "收招中短僵直：%s" % anim.clip)
	_step(Frames.of(VeltharisData.SHORT_STAGGER_TIME) - 1)
	assert_eq(anim.frame_id, SP.frame_at(SP.clip("carry"), anim.row, 0), "最後一張是扛劍站著")


func test_row_follows_facing_with_hysteresis() -> void:
	boss().facing = Vector2.RIGHT
	anim.update(boss())
	assert_eq(anim.row, "right")
	boss().facing = Vector2.from_angle(deg_to_rad(48.0))   # 斜角附近：還沒超過 45° + 6°
	anim.update(boss())
	assert_eq(anim.row, "right")
	boss().facing = Vector2.from_angle(deg_to_rad(60.0))
	anim.update(boss())
	assert_eq(anim.row, "down")


func test_leap_lift_comes_from_the_sprites() -> void:
	sim.player.pos = Vector2(0, 300)
	_start(2, &"kings_leap")
	var top := 0.0
	while boss().state == BS.ATTACK and boss().state_elapsed() < boss().hit_start_frame(0):
		_step(1)
		top = maxf(top, anim.lift)
	assert_true(top > 80.0, "騰空最高 %.0f px（精靈圖畫的高度）" % top)
