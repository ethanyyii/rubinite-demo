extends Node2D
## 地面圖層（arena.md §3；2026-10-05 正式美術，tools/arena_art/）：石磚廣場、中央灰燼王座的石台、血跡、積水，
## 以及北邊的廢墟（斷牆、拱門、柱子、旗竿、大樹：它們站在場地北邊之外，角色永遠在它們前面，所以直接畫在地面圖裡）。
## 最底層，不參與排序。旗子另外畫（第二階段會燒起來）。
## 2026-10-06：地上穿過樹冠晃動的小光斑（sun_flecks.gdshader）。
## 地面圖、旗子、光斑都畫在這個節點自己的 _draw（旗子的火苗）底下（show_behind_parent）。

const SunFlecks := preload("res://scripts/view/sun_flecks.gdshader")
const SCENE_TINT := Color(0.66, 0.56, 0.54)
## 第二階段：旗子換成燒過的圖的時間點（轉場進度 0–1）
const BANNER_BURN_AT := 0.45

var arena: CombatArena
var floor_sprite: Sprite2D
var flecks: Sprite2D
var banners: Array[Sprite2D] = []
var _banner_tex: Array = []
var _rng := RandomNumberGenerator.new()
## 旗子上的火苗：{pos, t, life, vx}
var _flames: Array[Dictionary] = []
## 這一格的場景階段（scene_phase）與場景變暗的顏色：場景物件每格直接讀，不用每個各算一次
var phase := 0.0
var tint := Color(1, 1, 1)


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _ready() -> void:
	z_index = -20
	floor_sprite = Sprite2D.new()
	floor_sprite.name = "Floor"
	floor_sprite.centered = false
	floor_sprite.texture = load(ArenaLayout.FLOOR)
	floor_sprite.position = ArenaLayout.FLOOR_ORIGIN
	floor_sprite.show_behind_parent = true
	add_child(floor_sprite)
	flecks = Sprite2D.new()
	flecks.name = "SunFlecks"
	flecks.centered = false
	flecks.texture = load(ArenaLayout.SUN_MASK)
	flecks.position = ArenaLayout.FLOOR_ORIGIN
	flecks.scale = floor_sprite.texture.get_size() / flecks.texture.get_size()
	flecks.show_behind_parent = true
	var m := ShaderMaterial.new()
	m.shader = SunFlecks
	m.set_shader_parameter("floor_size", floor_sprite.texture.get_size())
	flecks.material = m
	add_child(flecks)
	for b: Dictionary in ArenaLayout.BANNERS:
		var s := Sprite2D.new()
		s.centered = false
		var tex: Texture2D = load(b["texture"])
		var burnt: Texture2D = load(b["burnt"])
		s.texture = tex
		s.position = (b["pos"] as Vector2) - (b["anchor"] as Vector2)
		s.show_behind_parent = true
		add_child(s)
		banners.append(s)
		_banner_tex.append([tex, burnt])


## 場景跟著 Boss 的階段變化：0＝第一階段，轉場期間 0→1，第二階段 1（2026-10-05 使用者同意）
func scene_phase() -> float:
	if arena == null:
		return 0.0
	var b: BossSim = arena.sim.boss
	if b.state == BossSim.State.TRANSITION:
		return clampf(float(b.state_elapsed()) / Frames.of(VeltharisData.TRANSITION_TIME), 0.0, 1.0)
	return 1.0 if b.phase == 2 else 0.0


func _process(delta: float) -> void:
	var k := scene_phase()
	phase = k
	tint = Color(1, 1, 1).lerp(SCENE_TINT, k)
	floor_sprite.modulate = tint
	(flecks.material as ShaderMaterial).set_shader_parameter("strength", 0.16 * (1.0 - k))
	var burnt := k >= BANNER_BURN_AT
	for i in banners.size():
		banners[i].texture = _banner_tex[i][1] if burnt else _banner_tex[i][0]
		banners[i].modulate = tint
	_tick_flames(delta, k)
	queue_redraw()


## 第二階段：旗子燒過的邊上一直有小火苗往上竄（程式畫的特效）
func _tick_flames(delta: float, k: float) -> void:
	for f in _flames:
		f["t"] += delta
		f["pos"] += Vector2(f["vx"], -18.0) * delta
	_flames = _flames.filter(func(f: Dictionary) -> bool: return f["t"] < f["life"])
	if k < BANNER_BURN_AT:
		return
	for b: Dictionary in ArenaLayout.BANNERS:
		if _rng.randf() < delta * 14.0:
			var w: float = b["width"]
			var bottom: float = (b["pos"] as Vector2).y + 6 + float(b["length"]) * 0.45
			var x: float = (b["pos"] as Vector2).x - w * 0.5 + _rng.randf() * w
			_flames.append({"pos": Vector2(x, bottom + _rng.randf_range(-3, 3)), "t": 0.0,
				"life": _rng.randf_range(0.35, 0.8), "vx": _rng.randf_range(-4, 4)})


func _draw() -> void:
	for f in _flames:
		var u: float = f["t"] / f["life"]
		var c := Color(1.0, 0.75, 0.3).lerp(Color(0.85, 0.2, 0.08), u)
		c.a = 1.0 - u
		draw_rect(Rect2((f["pos"] as Vector2).round(), Vector2(1, 2 if u < 0.5 else 1)), c)
