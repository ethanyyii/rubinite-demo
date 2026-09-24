extends TestCase
## 秒→幀的取整規則：一律 roundi（四捨五入），區間端點各自換算。


func test_fps_is_60() -> void:
	assert_eq(Frames.FPS, 60)
	assert_eq(ProjectSettings.get_setting("physics/common/physics_ticks_per_second", 60), 60)


func test_rounding_rule_is_round_half_away() -> void:
	assert_eq(Frames.of(0.15), 9, "完美窗口")
	assert_eq(Frames.of(0.3), 18, "重新開窗")
	assert_eq(Frames.of(0.08), 5, "4.8 → 5")
	assert_eq(Frames.of(0.06), 4, "3.6 → 4")
	assert_eq(Frames.of(0.18), 11, "10.8 → 11")
	assert_eq(Frames.of(0.02), 1, "1.2 → 1")
	assert_eq(Frames.of(0.16), 10, "9.6 → 10")
	assert_eq(Frames.of(0.14), 8, "8.4 → 8")
	assert_eq(Frames.of(0.05), 3)
	assert_eq(Frames.of(0.125), 8, "7.5 → 8（遠離零）")
	assert_eq(Frames.of(0.55), 33)
	assert_eq(Frames.of(1.1), 66)
	assert_eq(Frames.of(1.2), 72)


func test_sec_is_inverse_for_whole_frames() -> void:
	for f in [0, 1, 9, 60, 72]:
		assert_eq(Frames.of(Frames.sec(f)), f)
