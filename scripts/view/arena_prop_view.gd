extends Node2D
## 和角色一起依 Y 排序的場景物件（arena.md §3；2026-10-05 正式美術，2026-10-06 加料）：場地兩側、南邊的碎石、矮牆、
## 斷劍、灌木、石頭、蕨類、長草、倒木、挑戰者的墳、國王的石像頭、火盆。
## 全部在場地（碰撞的橢圓）外面；角色走到它後面、畫面上重疊時變半透明（和柱子一樣）。
## 植物（sway > 0）隨風擺；火盆第一階段冒一縷細煙，第二階段被 Boss 的火點燃（轉場進行到 BRAZIER_LIGHT_AT 時燒起來）。

const SwayShader := preload("res://scripts/view/plant_sway.gdshader")
const BRAZIER_LIGHT_AT := 0.35
const FIRE := Color(1.0, 0.78, 0.34)
const FIRE_DEEP := Color(0.86, 0.2, 0.06)

var data: Dictionary
var arena: CombatArena
var sprite: Sprite2D
var glow: Sprite2D
var _alpha := 1.0
var _rng := RandomNumberGenerator.new()
## 火盆的火焰、煙：{pos（相對腳底）, t, life, vx, vy, smoke}
var _bits: Array[Dictionary] = []
var _lit := 0.0
## 地面圖層（每格的場景階段、變暗的顏色由它算一次，這裡直接讀）
var _floor: Node = null


func setup(d: Dictionary, owner_arena: CombatArena) -> void:
	data = d
	arena = owner_arena
	position = d["pos"]
	sprite = Sprite2D.new()
	sprite.centered = false
	sprite.texture = load(d["texture"])
	sprite.offset = -(d["anchor"] as Vector2)
	add_child(sprite)
	_rng.seed = int(position.x * 31.0 + position.y * 7.0)
	var sway: float = d.get("sway", 0.0)
	if sway > 0.0:
		var m := ShaderMaterial.new()
		m.shader = SwayShader
		m.set_shader_parameter("amp", sway)
		var tex_h := float(sprite.texture.get_height())
		m.set_shader_parameter("foot_v", (d["anchor"] as Vector2).y / tex_h)
		m.set_shader_parameter("top_v", ((d["anchor"] as Vector2).y - float(d["top"])) / tex_h)
		m.set_shader_parameter("phase", position.x * 0.012 + position.y * 0.004)
		sprite.material = m
	if d.has("fire"):
		glow = Sprite2D.new()
		var g := Gradient.new()
		g.set_color(0, Color(FIRE_DEEP, 0.55))
		g.set_color(1, Color(FIRE_DEEP, 0.0))
		var gt := GradientTexture2D.new()
		gt.gradient = g
		gt.fill = GradientTexture2D.FILL_RADIAL
		gt.fill_from = Vector2(0.5, 0.5)
		gt.fill_to = Vector2(1.0, 0.5)
		gt.width = 64
		gt.height = 64
		glow.texture = gt
		glow.scale = Vector2(1.6, 1.1)
		glow.position = d["fire"] as Vector2 + Vector2(0, 4)
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		glow.material = add
		glow.modulate = Color(1, 1, 1, 0)
		add_child(glow)


## 這個物件在畫面上佔的範圍（腳底在下緣中央）
func rect() -> Rect2:
	var hw: float = data["half_width"]
	var top: float = data["top"]
	return Rect2(position.x - hw, position.y - top, hw * 2.0, top + 2.0)


func _process(delta: float) -> void:
	var sim: CombatSim = arena.sim
	var r := rect()
	var covered := _behind(sim.player.pos, PlayerData.HURT_RADIUS, PlayerData.HEIGHT, r) \
		or _behind(sim.boss.pos, VeltharisData.HURT_RADIUS, VeltharisData.HEIGHT, r)
	_alpha = move_toward(_alpha, 0.45 if covered else 1.0, delta * 4.0)
	if _floor == null:
		_floor = arena.get_node_or_null("ArenaFloor")
	var tint := Color(1, 1, 1)
	var k := 0.0
	if _floor != null:
		k = _floor.phase
		tint = _floor.tint
	sprite.modulate = Color(tint.r, tint.g, tint.b, _alpha)
	if data.has("fire"):
		_tick_brazier(delta, k)


func _tick_brazier(delta: float, k: float) -> void:
	_lit = move_toward(_lit, 1.0 if k >= BRAZIER_LIGHT_AT else 0.0, delta * 2.5)
	var bowl: Vector2 = data["fire"]
	if _lit > 0.0:
		# 火焰：一顆顆往上竄、從黃變紅變暗
		var n := int(delta * 46.0 * _lit + _rng.randf())
		for i in n:
			_bits.append({"pos": bowl + Vector2(_rng.randf_range(-6, 6), _rng.randf_range(-1, 1)), "t": 0.0,
				"life": _rng.randf_range(0.3, 0.6), "vx": _rng.randf_range(-3, 3), "vy": _rng.randf_range(-34, -20), "smoke": false})
	elif _rng.randf() < delta * 1.6:
		# 第一階段：冷的灰裡冒一縷細煙
		_bits.append({"pos": bowl + Vector2(_rng.randf_range(-3, 3), 0), "t": 0.0, "life": _rng.randf_range(1.6, 2.4),
			"vx": _rng.randf_range(-2, 2), "vy": _rng.randf_range(-9, -6), "smoke": true})
	for b in _bits:
		b["t"] += delta
		var sway := sin(float(b["t"]) * 5.0 + float(b["vy"])) * (5.0 if b["smoke"] else 7.0)
		b["pos"] += Vector2(float(b["vx"]) + sway, b["vy"]) * delta
	_bits = _bits.filter(func(b: Dictionary) -> bool: return b["t"] < b["life"])
	glow.modulate = Color(1, 1, 1, _lit * (0.8 + 0.2 * sin(Time.get_ticks_msec() * 0.013)))
	queue_redraw()


func _draw() -> void:
	if not data.has("fire"):
		return
	for b in _bits:
		var u: float = b["t"] / b["life"]
		var c: Color
		var size := Vector2(1, 1)
		if b["smoke"]:
			c = Color(0.62, 0.6, 0.56, 0.32 * (1.0 - u) * minf(1.0, u * 6.0))
		else:
			c = FIRE.lerp(FIRE_DEEP, u)
			c.a = 1.0 - u * u
			size = Vector2(2, 2) if u < 0.35 else Vector2(1, 2) if u < 0.7 else Vector2(1, 1)
		draw_rect(Rect2((b["pos"] as Vector2).round(), size), Color(c.r, c.g, c.b, c.a * _alpha))


func _behind(feet: Vector2, r: float, h: float, rect_: Rect2) -> bool:
	return feet.y < position.y and rect_.intersects(Rect2(feet + Vector2(-r, -h), Vector2(2 * r, h)))


func is_translucent() -> bool:
	return _alpha < 0.99
