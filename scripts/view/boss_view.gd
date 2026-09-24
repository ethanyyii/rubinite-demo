extends Node2D
## Boss 的佔位圖形（plan §4）：紅色大膠囊（腳底圓半徑 26、高 120）、灰色長方形大劍。
## 只讀取 BossSim 的狀態，不改動它。

const R := VeltharisData.HURT_RADIUS
const H := VeltharisData.HEIGHT

var arena: CombatArena
var _flash_white := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _process(delta: float) -> void:
	var b: BossSim = arena.sim.boss
	position = b.pos.round()
	var real_dt := delta / maxf(Engine.time_scale, 0.001)
	_flash_white = maxf(_flash_white - real_dt, 0.0)
	queue_redraw()


func flash_hit() -> void:
	_flash_white = FeedbackData.BOSS_FLASH_TIME


func _draw() -> void:
	var b: BossSim = arena.sim.boss
	var side := 1.0 if b.facing.x >= 0.0 else -1.0
	DrawUtil.fill_ellipse(self, Vector2(0, 2), Vector2(R + 8, 10), Palette.SHADOW, 24)
	var sword_behind := b.facing.y < -0.35
	if sword_behind:
		_draw_sword(side)
	_draw_body(b, side)
	if not sword_behind:
		_draw_sword(side)


func _body_color(base: Color) -> Color:
	if _flash_white > 0.0:
		return base.lerp(Color.WHITE, 0.8)
	return base


func _draw_body(b: BossSim, side: float) -> void:
	DrawUtil.fill_capsule(self, Vector2(0, 1), R + 1, H + 2, Palette.BOSS_DARK)
	DrawUtil.fill_capsule(self, Vector2.ZERO, R, H, _body_color(Palette.BOSS))
	# 披風下襬與胸甲
	draw_rect(Rect2(-R + 4, -70, 2 * R - 8, 6), _body_color(Palette.BOSS_DARK))
	draw_rect(Rect2(-12 + side * 4, -92, 24, 18), _body_color(Palette.BOSS_LIGHT))
	# 執魂的紅火裂紋
	var ember := _body_color(Palette.BOSS_EMBER)
	draw_polyline(PackedVector2Array([Vector2(-6, -60), Vector2(-2, -48), Vector2(-8, -36), Vector2(-4, -22)]), ember, 1.0)
	draw_polyline(PackedVector2Array([Vector2(10, -58), Vector2(6, -44), Vector2(12, -30)]), ember, 1.0)
	# 頭部與發光的眼（朝面向偏移）
	var eye := Vector2(side * 6 + roundf(b.facing.x * 2), -104)
	if b.facing.y > -0.5:
		draw_rect(Rect2(eye + Vector2(-5, 0), Vector2(4, 2)), ember)
		draw_rect(Rect2(eye + Vector2(2, 0), Vector2(4, 2)), ember)
	# 王冠
	for x: float in [-10.0, -3.0, 4.0]:
		draw_colored_polygon(PackedVector2Array([Vector2(x, -116), Vector2(x + 6, -116), Vector2(x + 3, -124)]), Palette.BOSS_CROWN)


func _draw_sword(side: float) -> void:
	var hand := Vector2(side * 22, -58)
	# 待機：劍尖斜指地面
	var dir := Vector2(side * 0.35, 1.0).normalized()
	_draw_blade(hand, dir, 70.0, Palette.GREATSWORD)


func _draw_blade(hand: Vector2, dir: Vector2, length: float, color: Color) -> void:
	var side := dir.orthogonal() * 4.0
	var tip := hand + dir * length
	draw_colored_polygon(PackedVector2Array([(hand + side).round(), (tip + side * 0.6).round(),
		(tip + dir * 6).round(), (tip - side * 0.6).round(), (hand - side).round()]), color)
	draw_line(hand.round(), (hand + dir * (length - 4)).round(), Palette.GREATSWORD_DARK, 1.0)
	# 護手與劍柄
	draw_line((hand + dir.orthogonal() * 9).round(), (hand - dir.orthogonal() * 9).round(), Palette.GREATSWORD_DARK, 3.0)
	draw_line(hand.round(), (hand - dir * 12).round(), Palette.BOSS_DARK, 3.0)
