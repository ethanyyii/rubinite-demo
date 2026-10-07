extends Node2D
## 光影圖層（arena.md §3、§4；2026-10-05 正式美術）：疊在所有東西上（UI 以外）。
## 第一階段：右上方穿過樹冠的陽光光束（加法混合、慢慢明暗）、光束裡飄的灰塵、中央灰燼裡往上飄的幾點火星。
## 第二階段（轉場時漸變）：陽光暗下去、場地中央一圈暗紅的光、整個場地飄滿往上竄的火星（使用者同意的變化）。

const MOTES := 46
const EMBERS_P1 := 3.0          # 每秒從灰燼冒出幾顆（第一階段）
const EMBERS_P2 := 26.0         # 第二階段：整個場地
const DAIS_GLOW := Color(0.9, 0.22, 0.08)

var arena: CombatArena
var shafts: Sprite2D
## 第二階段場地中央的暗紅光：放射漸層（不畫一圈圈的橢圓，不會有色帶）
var glow: Sprite2D
var _rng := RandomNumberGenerator.new()
var _motes: Array[Dictionary] = []
var _embers: Array[Dictionary] = []
var _time := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _ready() -> void:
	z_index = 25
	shafts = Sprite2D.new()
	shafts.name = "SunShafts"
	shafts.centered = false
	shafts.texture = load(ArenaLayout.SUN_SHAFTS)
	shafts.position = ArenaLayout.FLOOR_ORIGIN
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	shafts.material = mat
	add_child(shafts)
	glow = Sprite2D.new()
	glow.name = "Phase2Glow"
	var g := Gradient.new()
	g.set_color(0, Color(DAIS_GLOW, 0.34))
	g.set_color(1, Color(DAIS_GLOW, 0.0))
	g.add_point(0.45, Color(DAIS_GLOW, 0.14))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 256
	gt.height = 256
	glow.texture = gt
	glow.scale = Vector2(560.0 / 256.0, 310.0 / 256.0)
	glow.modulate = Color(1, 1, 1, 0)
	add_child(glow)
	_rng.seed = 17
	for i in MOTES:
		_motes.append({"pos": Vector2(_rng.randf_range(-560, 560), _rng.randf_range(-420, 330)),
			"v": Vector2(_rng.randf_range(-3, 3), _rng.randf_range(-4, 1)), "phase": _rng.randf() * TAU})


func _phase() -> float:
	var fv: Node = arena.get_node_or_null("ArenaFloor") if arena != null else null
	return fv.scene_phase() if fv != null else 0.0


func _process(delta: float) -> void:
	_time += delta
	var k := _phase()
	# 光束慢慢明暗（像樹冠被風吹動），第二階段淡掉
	shafts.modulate = Color(1, 1, 1, (0.85 + 0.15 * sin(_time * 0.6)) * (1.0 - k))
	glow.modulate = Color(1, 1, 1, k * (0.85 + 0.15 * sin(_time * 2.1)))
	for m in _motes:
		m["pos"] += (m["v"] as Vector2) * delta
		if (m["pos"] as Vector2).y < -440 or absf((m["pos"] as Vector2).x) > 600:
			m["pos"] = Vector2(_rng.randf_range(-560, 560), _rng.randf_range(-200, 330))
	var rate := lerpf(EMBERS_P1, EMBERS_P2, k)
	var n := int(rate * delta + _rng.randf())
	for i in n:
		var from_dais := k < 0.5 or _rng.randf() < 0.25
		var p := Vector2(_rng.randf_range(-40, 40), _rng.randf_range(-12, 10)) if from_dais \
			else Vector2(_rng.randf_range(-560, 560), _rng.randf_range(-300, 330))
		_embers.append({"pos": p, "t": 0.0, "life": _rng.randf_range(1.2, 2.6),
			"vx": _rng.randf_range(-6, 6), "vy": _rng.randf_range(-26, -12)})
	for e in _embers:
		e["t"] += delta
		e["pos"] += Vector2(e["vx"] + sin(e["t"] * 3.0 + e["vy"]) * 4.0, e["vy"]) * delta
	_embers = _embers.filter(func(e: Dictionary) -> bool: return e["t"] < e["life"])
	queue_redraw()


func _draw() -> void:
	var k := _phase()
	# 灰塵：只在第一階段、只有光束附近看得清楚（一點一點微微閃）
	if k < 1.0:
		for m in _motes:
			var a := (0.18 + 0.14 * sin(_time * 1.7 + float(m["phase"]))) * (1.0 - k)
			draw_rect(Rect2((m["pos"] as Vector2).round(), Vector2(1, 1)), Color(1.0, 0.92, 0.75, a))
	for e in _embers:
		var u: float = e["t"] / e["life"]
		var c := Color(1.0, 0.72, 0.3).lerp(Color(0.8, 0.18, 0.06), u)
		c.a = (1.0 - u) * (0.9 if u > 0.1 else u * 9.0)
		draw_rect(Rect2((e["pos"] as Vector2).round(), Vector2(1, 1)), c)
