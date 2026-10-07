extends Node2D
## 一根柱子（arena.md §3）：與角色一起依 Y 座標排序；角色走到後面時變半透明。

var pillar: Dictionary
var arena: CombatArena
var _alpha := 1.0
var sprite: Sprite2D


func setup(data: Dictionary, owner_arena: CombatArena) -> void:
	pillar = data
	arena = owner_arena
	position = data["pos"]
	# 正式美術（2026-10-05，tools/arena_art/）：斷柱，照 ArenaGeometry.PILLARS 的順序
	var art: Dictionary = ArenaLayout.PILLARS[ArenaGeometry.PILLARS.find(data)]
	sprite = Sprite2D.new()
	sprite.centered = false
	sprite.texture = load(art["texture"])
	sprite.offset = -(art["anchor"] as Vector2)
	add_child(sprite)


func _process(delta: float) -> void:
	var target := 0.45 if _occludes_someone() else 1.0
	_alpha = move_toward(_alpha, target, delta * 4.0)
	var floor_view: Node = arena.get_node_or_null("ArenaFloor") if arena != null else null
	var tint := Color(1, 1, 1)
	if floor_view != null:
		tint = Color(1, 1, 1).lerp(floor_view.SCENE_TINT, floor_view.scene_phase())
	modulate = Color(tint.r, tint.g, tint.b, _alpha)


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
	# 柱腳的影子（柱子本身是精靈圖）
	DrawUtil.fill_ellipse(self, Vector2(0, 1), Vector2(ArenaGeometry.PILLAR_WIDTH * 0.75, 5), Palette.SHADOW, 16)
