extends SimTestCase
## M2：combat-design §7 閃身、§8.2 蓄力重擊、§9 鎖定。

const S := PlayerSim.State


func before_each() -> void:
	super.before_each()
	sim.boss.pos = Vector2(0, -150)
	sim.player.pos = Vector2(0, 60)
	sim.player.facing = Vector2.UP


# --- 閃身 -----------------------------------------------------------------------

func test_dodge_frames() -> void:
	assert_eq(Frames.of(PlayerData.DODGE_TIME), 11)
	assert_eq(Frames.of(PlayerData.DODGE_RECOVERY), 7)
	assert_eq(Frames.of(PlayerData.DODGE_INVULN_START), 1)
	assert_eq(Frames.of(PlayerData.DODGE_INVULN_END), 10)
	assert_eq(Frames.of(PlayerData.DODGE_INTERVAL), 30)


func test_dodge_distance_duration_and_recovery() -> void:
	move = Vector2.RIGHT
	var x0 := sim.player.pos.x
	press(&"dodge")
	assert_eq(player().state, S.DODGE, "按下同一幀開始閃身")
	move = Vector2.ZERO
	advance(10)  # elapsed 10：位移最後一幀
	assert_near(sim.player.pos.x - x0, 56.0, 0.01, "11 幀內移動 56px")
	advance(7)  # elapsed 17：收招最後一幀
	assert_eq(player().state, S.DODGE)
	assert_near(sim.player.pos.x - x0, 56.0, 0.01, "收招不移動")
	advance(1)
	assert_eq(player().state, S.IDLE, "0.18 + 0.12 秒後結束")


func test_dodge_invulnerability_window() -> void:
	press(&"dodge")
	var inv := []
	inv.append(player().is_invulnerable())
	for i in 17:
		advance(1)
		inv.append(player().is_invulnerable())
	var expected := []
	for e in 18:
		expected.append(e >= 1 and e < 10)
	assert_eq(inv, expected, "無敵在第 1–9 幀（0.02–0.16 秒）")


func test_dodge_interval_is_30_frames_between_starts() -> void:
	press(&"dodge")
	advance(17)
	press(&"dodge")  # elapsed 18：閃身已結束，但距上次開始只有 18 幀
	assert_eq(player().state, S.IDLE, "間隔未滿 0.5 秒不能再閃")
	# 緩衝 9 幀：第 21 幀（相隔 30 前 9 幀）按下會在第 30 幀執行
	advance(2)
	press(&"dodge")  # 距上次開始 21 幀
	while sim.combat_frame - player().last_dodge_start < 30 and player().state == S.IDLE:
		advance(1)
	assert_eq(player().state, S.DODGE, "緩衝的閃身在間隔滿 30 幀時執行")
	assert_eq(player().state_elapsed(), 0)


func test_dodge_without_input_goes_backward() -> void:
	sim.player.facing = Vector2.UP
	var p0 := sim.player.pos
	press(&"dodge")
	advance(12)
	assert_near(sim.player.pos.y - p0.y, 56.0, 0.01, "沒有輸入時往後閃（面向的反方向）")
	assert_eq(player().facing, Vector2.UP, "往後閃不轉身")


func test_locked_dodge_without_input_goes_away_from_target() -> void:
	sim.boss.pos = Vector2(-100, 60)
	sim.player.pos = Vector2(0, 60)
	press(&"lock")
	assert_true(player().locked)
	advance(5)
	var p0 := sim.player.pos
	press(&"dodge")
	advance(12)
	assert_near(sim.player.pos.x - p0.x, 56.0, 0.01, "鎖定中往遠離目標的方向閃")


func test_dodge_after_full_charge() -> void:
	press(&"heavy")
	advance(60)
	assert_true(player().charge_full)
	press(&"dodge")
	assert_eq(player().state, S.DODGE, "蓄滿後也能用閃身取消")
	assert_false(player().charge_full, "取消後蓄力歸零")
	held["heavy"] = false
	advance(30)
	assert_eq(player().state, S.IDLE, "閃身後放開重擊鍵不會出招")


func test_locked_dodge_with_input_keeps_facing_target() -> void:
	sim.boss.pos = Vector2(0, -100)
	sim.player.pos = Vector2(0, 60)
	press(&"lock")
	move = Vector2.RIGHT
	press(&"dodge")
	move = Vector2.ZERO
	var to := (sim.boss.pos - sim.player.pos).normalized()
	assert_near(player().facing.angle_to(to), 0.0, 0.05, "鎖定中側閃仍面向目標")
	advance(6)
	assert_true(sim.player.pos.x > 20.0, "往輸入方向（右）閃")


# --- 蓄力重擊 --------------------------------------------------------------------

func test_heavy_charge_and_release_before_full_cancels() -> void:
	place_near_boss(60.0)
	press(&"heavy")
	assert_eq(player().state, S.CHARGE, "按下同一幀開始蓄力")
	advance(52)  # elapsed 52：尚未蓄滿（54 幀）
	assert_false(player().charge_full)
	held["heavy"] = false
	advance(1)
	assert_eq(player().state, S.IDLE, "未蓄滿就放開：取消，不出招")
	advance(40)
	assert_eq(boss().hp, VeltharisData.MAX_HP)


func test_heavy_full_charge_then_thrust() -> void:
	place_near_boss(100.0)
	press(&"heavy")
	advance(53)
	assert_false(player().charge_full, "第 53 幀還沒滿")
	advance(1)
	assert_true(player().charge_full, "0.9 秒（54 幀）蓄滿")
	advance(30)  # 蓄滿後可以繼續按住
	assert_eq(player().state, S.CHARGE)
	held["heavy"] = false
	advance(1)
	assert_eq(player().state, S.THRUST, "放開即出招")
	advance(20)
	assert_eq(boss().hp, VeltharisData.MAX_HP - 49, "重擊傷害 70（2026-10-05 加強，原 60；tuning-log × 0.7：49）")
	assert_near(boss().toughness, VeltharisData.MAX_TOUGHNESS - PlayerData.heavy_thrust().toughness, 0.001, "削韌 15（tuning-log：10.5）")


func test_thrust_distance_and_stops_on_contact() -> void:
	# 沒碰到 Boss：前進 120px / 15 幀，收招 30 幀（2026-10-05 重擊加強：原本 72px / 12 幀）
	sim.player.pos = Vector2(0, 60)
	sim.boss.pos = Vector2(0, -170)
	sim.player.facing = Vector2.RIGHT
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	var x0 := sim.player.pos.x
	advance(1)
	var start := sim.combat_frame
	advance(14)
	assert_near(sim.player.pos.x - x0, 120.0, 0.01, "0.25 秒前進 120px")
	advance(30)
	assert_eq(player().state, S.THRUST, "收招 0.5 秒")
	advance(1)
	assert_eq(player().state, S.IDLE)
	assert_eq(sim.combat_frame - start, 45)
	# 遠的時候碰到 Boss 就停在他面前（剩下的距離不夠穿過去）
	sim = CombatSim.new(1)
	place_near_boss(110.0)
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	var y0 := sim.player.pos.y
	advance(16)
	var moved := y0 - sim.player.pos.y
	assert_true(moved < 120.0 - 1.0, "命中後停下（前進 %.1f）" % moved)
	assert_true(sim.player.pos.y > boss().pos.y, "停在 Boss 面前")
	assert_eq(boss().hp, VeltharisData.MAX_HP - PlayerData.heavy_thrust().damage)


## 2026-10-05 重擊加強：近的時候蓄力，突刺穿過 Boss、落到他背後；Boss 不被推開，主角不會卡在他身體裡
func test_close_thrust_passes_through_the_boss() -> void:
	place_near_boss(60.0)
	var b0 := boss().pos
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	event_log.clear()
	advance(16)
	assert_eq(boss().hp, VeltharisData.MAX_HP - PlayerData.heavy_thrust().damage, "穿過時打中一次")
	assert_true(logged(&"thrust_through"), "穿過去的事件")
	assert_true(boss().pos.is_equal_approx(b0), "Boss 沒有被推開")
	var behind := b0.y - sim.player.pos.y
	assert_true(behind > VeltharisData.HURT_RADIUS + PlayerData.HURT_RADIUS, "落在 Boss 背後（%.1fpx）" % behind)
	assert_near(behind, 120.0 - 60.0, 0.5, "走完整段 120px")


## 穿過去的落點出了場地（Boss 靠牆）：停在他面前
func test_thrust_does_not_pass_through_into_a_wall() -> void:
	sim.boss.pos = Vector2(0, -ArenaGeometry.HALF_SIZE.y + 45.0)
	sim.player.pos = sim.boss.pos + Vector2(0, 60)
	sim.player.facing = Vector2.UP
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	advance(16)
	assert_true(sim.player.pos.y > boss().pos.y, "停在 Boss 面前")
	assert_eq(boss().hp, VeltharisData.MAX_HP - PlayerData.heavy_thrust().damage)


## 使用者 2026-09-30：突刺全程沒有無敵
func test_thrust_has_no_invulnerability() -> void:
	place_near_boss(60.0)
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	advance(1)
	while player().state == S.THRUST:
		assert_false(player().is_invulnerable(), "突刺第 %d 幀不能無敵" % player().state_elapsed())
		advance(1)


func test_charge_moves_slowly_and_cannot_run() -> void:
	press(&"heavy")
	move = Vector2.RIGHT
	held["run"] = true
	advance(20)
	assert_near(sim.player.vel.length(), PlayerData.SPEED_CHARGE, 0.001, "蓄力中慢走 40")


func test_charge_can_be_cancelled_by_dodge() -> void:
	press(&"heavy")
	advance(10)
	press(&"dodge")
	assert_eq(player().state, S.DODGE, "蓄力中隨時可以用閃身取消")


func test_heavy_thrust_cannot_be_cancelled() -> void:
	place_near_boss(100.0)
	press(&"heavy")
	advance(54)
	held["heavy"] = false
	advance(1)
	advance(15)
	press(&"dodge")
	assert_eq(player().state, S.THRUST, "突刺不可取消")


# --- 鎖定 -----------------------------------------------------------------------

## 鎖定距離 480、超過 630 解除（2026-09-30 畫面拉遠、場地放大 1.5 倍，原 320、420；tuning-log）
func test_lock_acquire_range_480() -> void:
	sim.boss.pos = Vector2(-300, 0)
	sim.player.pos = Vector2(-300 + 479, 0)
	press(&"lock")
	assert_true(player().locked, "479px：鎖得到")
	press(&"lock")
	assert_false(player().locked, "再按一次解除")
	sim.player.pos = Vector2(-300 + 481, 0)
	press(&"lock")
	assert_false(player().locked, "481px：鎖不到")


func test_lock_acquire_range_480_diagonal() -> void:
	sim.boss.pos = Vector2(-300, -150)
	var dir := Vector2(1, 0.5).normalized()
	sim.player.pos = sim.boss.pos + dir * 481.0
	press(&"lock")
	assert_false(player().locked, "481px：鎖不到")
	sim.player.pos = sim.boss.pos + dir * 479.0
	press(&"lock")
	assert_true(player().locked, "479px：鎖得到")


func test_lock_breaks_beyond_630() -> void:
	sim.boss.pos = Vector2(-500, 0)
	sim.player.pos = Vector2(-30, 0)
	press(&"lock")
	assert_true(player().locked)
	move = Vector2.RIGHT
	while player().locked and sim.player.pos.x < 520:
		advance(1)
	var d := sim.player.pos.distance_to(sim.boss.pos)
	assert_false(player().locked, "超過 630px 解除")
	assert_between(d, 630.0, 632.0, "在剛超過 630px 時解除（%.2f）" % d)


func test_locked_facing_and_speed() -> void:
	sim.boss.pos = Vector2(0, -100)
	sim.player.pos = Vector2(0, 60)
	press(&"lock")
	move = Vector2.RIGHT
	advance(20)
	var to := (sim.boss.pos - sim.player.pos).normalized()
	assert_near(player().facing.angle_to(to), 0.0, 0.001, "鎖定中面向目標（側移）")
	assert_near(sim.player.vel.length(), PlayerData.SPEED_LOCKED, 0.001, "鎖定中走 85")
	held["run"] = true
	advance(10)
	assert_eq(player().facing, Vector2.RIGHT, "奔跑時暫時面向奔跑方向")
	held["run"] = false
	move = Vector2.ZERO
	advance(5)
	to = (sim.boss.pos - sim.player.pos).normalized()
	assert_near(player().facing.angle_to(to), 0.0, 0.001, "停下後恢復面向目標")


func test_locked_attack_faces_target() -> void:
	sim.boss.pos = Vector2(0, 0)
	sim.player.pos = Vector2(50, 20)
	press(&"lock")
	sim.player.facing = Vector2.DOWN
	press(&"attack")
	var to := (sim.boss.pos - sim.player.pos).normalized()
	assert_near(player().facing.angle_to(to), 0.0, 0.001, "攻擊自動朝向鎖定目標")
