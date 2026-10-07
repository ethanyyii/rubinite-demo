extends TestCase
## 介面（combat-design §13；2026-10-06 使用者）：Boss 的血條分兩管——第一階段一管（HP 的上半），打空進入第二階段，
## 轉場的 1.5 秒裡血條回滿，第二階段再一管。只是顯示：遊戲規則（HP 一半進第二階段）不變。

const Hud := preload("res://scripts/view/hud.gd")


func test_first_bar_is_the_upper_half_of_the_hp() -> void:
	var m := VeltharisData.MAX_HP
	assert_near(Hud.boss_bar_ratio(1, -1.0, m, -1), 1.0, 0.001, "滿血")
	assert_near(Hud.boss_bar_ratio(1, -1.0, roundi(m * 0.75), -1), 0.5, 0.01, "HP 75%：第一管剩一半")
	assert_near(Hud.boss_bar_ratio(1, -1.0, roundi(m * 0.5), -1), 0.0, 0.001, "HP 一半：第一管打空")
	assert_near(Hud.boss_bar_ratio(1, -1.0, roundi(m * 0.4), -1), 0.0, 0.001, "失衡、處決中跨過一半：還是空的，不會變負的")


func test_the_bar_refills_during_the_transition() -> void:
	var half := roundi(VeltharisData.MAX_HP * 0.5)
	assert_near(Hud.boss_bar_ratio(1, 0.0, half, half), 0.0, 0.001, "轉場開始：空的")
	var mid := Hud.boss_bar_ratio(1, 0.5, half, half)
	assert_true(mid > 0.2 and mid < 0.8, "轉場一半：正在回滿（%.2f）" % mid)
	assert_near(Hud.boss_bar_ratio(1, 1.0, half, half), 1.0, 0.001, "轉場結束：滿的")


func test_second_bar_is_full_at_the_start_of_phase_two() -> void:
	var m := VeltharisData.MAX_HP
	var half := roundi(m * 0.5)
	assert_near(Hud.boss_bar_ratio(2, -1.0, half, half), 1.0, 0.001, "第二階段開始：滿的")
	assert_near(Hud.boss_bar_ratio(2, -1.0, roundi(half * 0.5), half), 0.5, 0.01)
	assert_near(Hud.boss_bar_ratio(2, -1.0, 0, half), 0.0, 0.001, "打死：空的")
	# 處決把 HP 從一半以上直接打到一半以下：第二管從那時剩下的血算起，開始時一樣是滿的
	var left := roundi(m * 0.43)
	assert_near(Hud.boss_bar_ratio(2, -1.0, left, left), 1.0, 0.001, "跨過一半才轉場：第二管照樣從滿的開始")
	# 不知道轉場時剩多少（例如測試直接把階段設成 2）：照 HP 的一半算
	assert_near(Hud.boss_bar_ratio(2, -1.0, half, -1), 1.0, 0.001)


func test_boss_flash_is_faint() -> void:
	# 使用者 2026-10-06：Boss 受擊的閃白「微微的看得出來就好」
	assert_true(FeedbackData.BOSS_FLASH_AMOUNT > 0.0 and FeedbackData.BOSS_FLASH_AMOUNT <= 0.3,
		"閃白強度 %.2f" % FeedbackData.BOSS_FLASH_AMOUNT)
