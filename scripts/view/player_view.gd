extends Node2D
## 主角的佔位圖形（plan §4）：藍色膠囊（腳底圓半徑 8、高 40）、指向面向的白色短線（劍）、腳底橢圓陰影。
## 只讀取 PlayerSim 的狀態，不改動它。

const R := PlayerData.HURT_RADIUS
const H := PlayerData.HEIGHT

var arena: CombatArena
var _flash_red := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _process(delta: float) -> void:
	var p: PlayerSim = arena.sim.player
	position = p.pos.round()
	_flash_red = maxf(_flash_red - delta, 0.0)
	queue_redraw()


func flash_hurt() -> void:
	_flash_red = FeedbackData.PLAYER_FLASH_TIME


func _draw() -> void:
	var p: PlayerSim = arena.sim.player
	DrawUtil.fill_ellipse(self, Vector2(0, 1), Vector2(R + 3, 4), Palette.SHADOW, 16)
	_draw_body(p)
	_draw_sword(p)


func _body_color(base: Color) -> Color:
	if _flash_red > 0.0:
		return base.lerp(Color(1, 0.2, 0.2), 0.7)
	return base


func _draw_body(p: PlayerSim) -> void:
	var f := p.facing
	DrawUtil.fill_capsule(self, Vector2(0, 1), R + 1, H + 2, Palette.PLAYER_DARK)
	DrawUtil.fill_capsule(self, Vector2.ZERO, R, H, _body_color(Palette.PLAYER))
	# 胸甲高光
	draw_rect(Rect2(-5 + roundf(f.x * 2), -27, 3, 12), _body_color(Palette.PLAYER_LIGHT))
	# 頭盔面甲：朝面向偏移，背對時看不到
	if f.y > -0.5:
		draw_rect(Rect2(-4 + roundf(f.x * 3), -35, 8, 3), Palette.PLAYER_DARK)
	# 羽飾
	draw_colored_polygon(PackedVector2Array([Vector2(-2, -40), Vector2(2, -40),
		Vector2(-roundf(f.x * 6) + 1, -47)]), Palette.PLAYER_PLUME)


func _draw_sword(p: PlayerSim) -> void:
	var f := p.facing
	# 持劍的手在身體外側，面向正上或正下時劍也不會被身體遮住
	var side := 1.0 if f.x >= -0.2 else -1.0
	var hand := Vector2(side * 9 + roundf(f.x * 2), -17 + roundf(f.y * 3))
	draw_line(hand, (hand + f * 17).round(), Palette.SWORD, 2.0)
	draw_line(hand - f.orthogonal() * 3, hand + f.orthogonal() * 3, Palette.PLAYER_DARK, 1.0)
