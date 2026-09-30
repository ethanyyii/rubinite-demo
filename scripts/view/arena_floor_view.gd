extends Node2D
## 地面圖層（arena.md §3）：石磚廣場、中央石台、血跡、積水、斷劍、外圍斷牆。
## 最底層，不參與 Y 排序。

const HALF := ArenaGeometry.HALF_SIZE
## 場地放大 1.5 倍（2026-09-30）：固定位置、大小的裝飾照這個倍率放大
const K := 1.5


func _ready() -> void:
	z_index = -20
	queue_redraw()


func _draw() -> void:
	# 森林背景與外圍
	draw_rect(Rect2(-1000, -700, 2000, 1400), Palette.BACKDROP)
	DrawUtil.fill_ellipse(self, Vector2(0, 9), HALF + Vector2(165, 120), Palette.FOLIAGE, 64)
	DrawUtil.fill_ellipse(self, Vector2(0, 6), HALF + Vector2(78, 57), Palette.RUBBLE, 64)
	_draw_rubble_ring()

	# 廣場
	DrawUtil.fill_ellipse(self, Vector2.ZERO, HALF, Palette.FLOOR, 64)
	for i in range(1, 5):
		var k := float(i) / 5.0
		DrawUtil.stroke_ellipse(self, Vector2.ZERO, HALF * k, Palette.FLOOR_LINE, 1.0, 96)
	for i in 16:
		var a := TAU * i / 16.0
		var dir := Vector2(cos(a), sin(a))
		var inner := Vector2(dir.x * HALF.x * 0.2, dir.y * HALF.y * 0.2)
		var outer := Vector2(dir.x * HALF.x, dir.y * HALF.y)
		draw_line(inner.round(), outer.round(), Palette.FLOOR_LINE, 1.0)
	# 石磚明暗交錯
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in 200:
		var a := rng.randf() * TAU
		var r := sqrt(rng.randf()) * 0.95
		var p := Vector2(cos(a) * HALF.x * r, sin(a) * HALF.y * r).round()
		draw_rect(Rect2(p, Vector2(rng.randi_range(6, 14), rng.randi_range(3, 6))), Palette.FLOOR_LIGHT)
	DrawUtil.stroke_ellipse(self, Vector2.ZERO, HALF, Palette.RUBBLE_LIGHT, 2.0, 96)

	# 中央石台（灰燼王座的遺跡）
	DrawUtil.fill_ellipse(self, Vector2(0, 3), Vector2(62, 34) * K, Palette.FLOOR_LINE, 48)
	DrawUtil.fill_ellipse(self, Vector2.ZERO, Vector2(60, 32) * K, Palette.DAIS, 48)
	DrawUtil.stroke_ellipse(self, Vector2.ZERO, Vector2(46, 24) * K, Palette.FLOOR_LINE, 1.0, 48)
	DrawUtil.fill_ellipse(self, Vector2(0, -3), Vector2(22, 11) * K, Palette.ASH, 32)

	# 血跡與積水
	for b: Array in [[Vector2(-120, 60), Vector2(18, 6)], [Vector2(150, -70), Vector2(12, 5)],
			[Vector2(60, 120), Vector2(9, 4)], [Vector2(-200, -40), Vector2(14, 5)]]:
		DrawUtil.fill_ellipse(self, (b[0] as Vector2) * K, (b[1] as Vector2) * K, Palette.BLOOD, 16)
	for w: Array in [[Vector2(180, 80), Vector2(26, 8)], [Vector2(-90, -130), Vector2(20, 6)],
			[Vector2(-250, 30), Vector2(16, 5)]]:
		DrawUtil.fill_ellipse(self, (w[0] as Vector2) * K, (w[1] as Vector2) * K, Palette.PUDDLE, 20)

	# 邊緣的斷劍（過去挑戰者留下的）
	for i in 16:
		var a := TAU * (i + 0.37) / 16.0
		var base := Vector2(cos(a) * (HALF.x - 14), sin(a) * (HALF.y - 10)).round()
		var tilt := Vector2(sin(a * 3.0) * 3.0, -12).round()
		draw_line(base, base + tilt, Palette.GREATSWORD, 2.0)
		draw_line(base + tilt * 0.35 + Vector2(-3, 0), base + tilt * 0.35 + Vector2(3, 0), Palette.GREATSWORD_DARK, 1.0)


func _draw_rubble_ring() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	for i in 105:
		var a := TAU * i / 105.0 + rng.randf() * 0.05
		var r := 1.0 + rng.randf() * 0.12
		var p := Vector2(cos(a) * (HALF.x + 33) * r, sin(a) * (HALF.y + 24) * r).round()
		var s := Vector2(rng.randi_range(8, 18), rng.randi_range(5, 10))
		draw_rect(Rect2(p - s * 0.5, s), Palette.RUBBLE_LIGHT if i % 3 == 0 else Palette.RUBBLE)
	# 北側的斷牆與王旗（arena.md §1）
	for x: float in [-225.0, 225.0]:
		var base := Vector2(x, -HALF.y - 39)
		draw_rect(Rect2(base + Vector2(-40, -34), Vector2(80, 34)), Palette.RUBBLE_LIGHT)
		draw_rect(Rect2(base + Vector2(-40, -34), Vector2(80, 4)), Palette.PILLAR)
		draw_rect(Rect2(base + Vector2(-8, -30), Vector2(16, 26)), Palette.BANNER)
		draw_rect(Rect2(base + Vector2(-3, -24), Vector2(6, 6)), Palette.BANNER_GOLD)
		draw_line(base + Vector2(-40, -20), base + Vector2(-20, -8), Palette.VINE, 2.0)
