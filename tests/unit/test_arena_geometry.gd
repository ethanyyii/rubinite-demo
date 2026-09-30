extends TestCase
## 場地橢圓與柱子碰撞（arena.md §2）。


## arena.md §2：1080×600（2026-09-30 使用者：鏡頭拉遠、場地放大 1.5 倍，原 720×400）
func test_ellipse_size_is_1080_by_600() -> void:
	assert_eq(ArenaGeometry.HALF_SIZE, Vector2(540, 300))


func test_points_inside_are_unchanged() -> void:
	for p in [Vector2.ZERO, Vector2(150, 75), Vector2(-450, 0), Vector2(0, -270)]:
		assert_eq(ArenaGeometry.clamp_inside(p, 8.0), p)


func test_outside_points_are_pulled_onto_boundary() -> void:
	for p in [Vector2(750, 0), Vector2(0, 600), Vector2(-600, -450), Vector2(540, 300)]:
		var q := ArenaGeometry.clamp_inside(p, 8.0)
		assert_true(ArenaGeometry.is_inside(q, 8.0), "%s → %s" % [p, q])
		assert_false(ArenaGeometry.is_inside(q, 9.0), "%s 應在邊界上" % q)


func test_resolve_pushes_out_of_pillars() -> void:
	for pillar: Dictionary in ArenaGeometry.PILLARS:
		var c: Vector2 = pillar["pos"]
		var q := ArenaGeometry.resolve(c + Vector2(3, 2), 8.0)
		assert_true(q.distance_to(c) >= pillar["radius"] + 8.0 - 0.001, "推出柱子 %s" % c)


func test_pillars_can_be_walked_behind() -> void:
	# arena.md §3：角色可以走到柱子後方。每根柱子北側都要有可站立的空間。
	for pillar: Dictionary in ArenaGeometry.PILLARS:
		var c: Vector2 = pillar["pos"]
		var behind := c + Vector2(0, -(pillar["radius"] + 8.0 + 4.0))
		assert_true(ArenaGeometry.is_inside(behind, 8.0), "柱子 %s 後方要在場內" % c)
		var front := c + Vector2(0, pillar["radius"] + 8.0 + 4.0)
		assert_true(ArenaGeometry.is_inside(front, 8.0), "柱子 %s 前方要在場內" % c)


func test_hit_geometry_sector() -> void:
	var o := Vector2.ZERO
	var d := Vector2.RIGHT
	assert_true(HitGeometry.circle_hits_sector(Vector2(47, 0), 8, o, d, 40, 100), "邊緣碰到（40+8 ≥ 47）")
	assert_false(HitGeometry.circle_hits_sector(Vector2(60, 0), 8, o, d, 40, 100), "太遠")
	assert_true(HitGeometry.circle_hits_sector(Vector2(20, 22), 8, o, d, 40, 100), "扇形內（約 48°）")
	assert_false(HitGeometry.circle_hits_sector(Vector2(-30, 0), 8, o, d, 40, 100), "背後")
	assert_true(HitGeometry.circle_hits_sector(Vector2(5, 30), 8, o, d, 100, 150), "圓心在 150° 扇形外（約 80°），但碰到邊線")
	assert_false(HitGeometry.circle_hits_sector(Vector2(-20, 40), 8, o, d, 100, 150), "150° 扇形後方")
	assert_true(HitGeometry.circle_hits_sector(Vector2(-50, 0), 8, o, d, 100, 360), "360°")


func test_hit_geometry_rect_ring_capsule() -> void:
	var o := Vector2.ZERO
	var d := Vector2.UP
	assert_true(HitGeometry.circle_hits_rect(Vector2(0, -100), 8, o, d, 110, 40))
	assert_true(HitGeometry.circle_hits_rect(Vector2(27, -50), 8, o, d, 110, 40), "側邊擦到（20+8 ≥ 27）")
	assert_false(HitGeometry.circle_hits_rect(Vector2(29, -50), 8, o, d, 110, 40))
	assert_false(HitGeometry.circle_hits_rect(Vector2(0, -119), 8, o, d, 110, 40))
	assert_false(HitGeometry.circle_hits_rect(Vector2(0, 20), 8, o, d, 110, 40), "背後")
	assert_true(HitGeometry.circle_hits_ring(Vector2(100, 0), 8, o, 100, 16))
	assert_false(HitGeometry.circle_hits_ring(Vector2(70, 0), 8, o, 100, 16), "環內側")
	assert_false(HitGeometry.circle_hits_ring(Vector2(109, 0), 8, o, 100, 16), "環外")
	assert_true(HitGeometry.circle_hits_capsule(Vector2(50, 10), 8, o, Vector2(100, 0), 5))
	assert_false(HitGeometry.circle_hits_capsule(Vector2(50, 14), 8, o, Vector2(100, 0), 5))


func test_is_in_front_180() -> void:
	var p := Vector2.ZERO
	assert_true(HitGeometry.is_in_front(p, Vector2.RIGHT, Vector2(10, 0), 180))
	assert_true(HitGeometry.is_in_front(p, Vector2.RIGHT, Vector2(0, 10), 180), "正側面算在 180° 內")
	assert_false(HitGeometry.is_in_front(p, Vector2.RIGHT, Vector2(-1, 10), 180), "稍微偏後就擋不到")
