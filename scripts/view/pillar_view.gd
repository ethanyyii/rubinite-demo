extends Node2D
## 一根柱子（arena.md §3）：與角色一起依 Y 座標排序；角色走到後面時變半透明。

var pillar: Dictionary
var arena: CombatArena
var _alpha := 1.0


func setup(data: Dictionary, owner_arena: CombatArena) -> void:
	pillar = data
	arena = owner_arena
	position = data["pos"]


func _process(delta: float) -> void:
	var target := 0.45 if _occludes_someone() else 1.0
	_alpha = move_toward(_alpha, target, delta * 4.0)
	modulate.a = _alpha


func _occludes_someone() -> bool:
	var rect := ArenaGeometry.pillar_rect(pillar)
	var sim: CombatSim = arena.sim
	return _behind(sim.player.pos, PlayerData.HURT_RADIUS, PlayerData.HEIGHT, rect) \
		or _behind(sim.boss.pos, VeltharisData.HURT_RADIUS, VeltharisData.HEIGHT, rect)


## 角色（腳底 feet、半寬 r、高 h）在柱子後方且畫面上重疊
func _behind(feet: Vector2, r: float, h: float, rect: Rect2) -> bool:
	return feet.y < position.y and rect.intersects(Rect2(feet + Vector2(-r, -h), Vector2(2 * r, h)))


func is_translucent() -> bool:
	return _alpha < 0.99


func _draw() -> void:
	var h: float = pillar["height"]
	var w := ArenaGeometry.PILLAR_WIDTH
	DrawUtil.fill_ellipse(self, Vector2(0, 1), Vector2(w * 0.7, 5), Palette.SHADOW, 16)
	# 柱基
	draw_rect(Rect2(-w * 0.5 - 3, -8, w + 6, 8), Palette.PILLAR_DARK)
	# 柱身
	draw_rect(Rect2(-w * 0.5, -h, w, h - 8), Palette.PILLAR)
	draw_rect(Rect2(-w * 0.5, -h, 4, h - 8), Palette.PILLAR_DARK)
	draw_rect(Rect2(w * 0.5 - 5, -h, 5, h - 8), Palette.FLOOR_LIGHT)
	for y in range(int(-h) + 14, -8, 14):
		draw_line(Vector2(-w * 0.5, y), Vector2(w * 0.5, y), Palette.PILLAR_DARK, 1.0)
	# 斷口
	var top := PackedVector2Array([Vector2(-w * 0.5, -h), Vector2(-w * 0.5 + 5, -h - 6),
		Vector2(-2, -h - 2), Vector2(4, -h - 8), Vector2(w * 0.5, -h - 3), Vector2(w * 0.5, -h)])
	draw_colored_polygon(top, Palette.PILLAR)
	# 藤蔓
	draw_polyline(PackedVector2Array([Vector2(-w * 0.5, -h * 0.8), Vector2(-3, -h * 0.62),
		Vector2(5, -h * 0.5), Vector2(-4, -h * 0.3), Vector2(2, -12)]), Palette.VINE, 2.0)
