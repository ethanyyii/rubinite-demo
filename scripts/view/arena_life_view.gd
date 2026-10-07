extends Node2D
## 場地裡的小生命（2026-10-06，使用者：拿掉畫面四角的枝葉後畫面不能變單調，可以自己加料）。全部在世界座標、
## 1–2 px，不擋戰鬥：
## - 從樹冠飄下來的葉子（第二階段換成灰燼片）
## - 場地外圈花叢附近飛的白蛾（第一階段；轉場時飛走）
## - 外圈樹蔭裡一閃一閃的螢火蟲（第一階段）
## 畫在角色上面（葉子、蛾在空中），在光影圖層下面。

const LEAVES := [Color(0.6, 0.5, 0.25), Color(0.47, 0.37, 0.17), Color(0.4, 0.45, 0.2), Color(0.5, 0.26, 0.16)]
const ASH := [Color(0.42, 0.4, 0.38), Color(0.3, 0.28, 0.27), Color(0.55, 0.52, 0.48)]
const MOTH := Color(0.86, 0.84, 0.76)
const FIREFLY := Color(0.85, 0.95, 0.45)
## 蛾、螢火蟲在哪幾個地方（場地外圈、鏡頭在中間時畫面的四個角看得到的地方）
const MOTH_SPOTS: Array[Vector2] = [Vector2(-430, -260), Vector2(452, -250), Vector2(-470, 228), Vector2(470, 240), Vector2(-590, 60), Vector2(600, 20)]
const FIREFLY_AREAS: Array[Rect2] = [Rect2(-640, -330, 200, 120), Rect2(440, -330, 200, 120), Rect2(-660, 160, 190, 200), Rect2(470, 160, 190, 200)]

var arena: CombatArena
var _rng := RandomNumberGenerator.new()
var _falling: Array[Dictionary] = []
var _moths: Array[Dictionary] = []
var _flies: Array[Dictionary] = []
var _time := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _ready() -> void:
	z_index = 24
	_rng.seed = 29
	for i in MOTH_SPOTS.size():
		_moths.append({"home": MOTH_SPOTS[i], "pos": MOTH_SPOTS[i], "phase": _rng.randf() * TAU, "away": Vector2.ZERO})
	for a: Rect2 in FIREFLY_AREAS:
		for i in 4:
			_flies.append({"pos": a.position + Vector2(_rng.randf() * a.size.x, _rng.randf() * a.size.y), "area": a,
				"phase": _rng.randf() * TAU, "v": Vector2(_rng.randf_range(-4, 4), _rng.randf_range(-3, 3))})


func _phase() -> float:
	var fv: Node = arena.get_node_or_null("ArenaFloor") if arena != null else null
	return fv.scene_phase() if fv != null else 0.0


func _view() -> Rect2:
	var cam: Camera2D = arena.camera if arena != null else null
	var c := cam.position if cam != null else Vector2.ZERO
	return Rect2(c - Vector2(500, 300), Vector2(1000, 600))


func _process(delta: float) -> void:
	_time += delta
	var k := _phase()
	var view := _view()
	# 葉子／灰燼：從畫面上方的樹冠飄下來，左右晃，落到地上停一下再淡掉
	var rate := lerpf(5.0, 9.0, k)
	if _rng.randf() < rate * delta:
		_falling.append({"pos": Vector2(view.position.x + _rng.randf() * view.size.x, view.position.y + _rng.randf() * view.size.y * 0.7),
			"fall": _rng.randf_range(40.0, 120.0), "t": 0.0, "v": _rng.randf_range(9, 15), "sway": _rng.randf_range(4, 9),
			"ph": _rng.randf() * TAU, "ash": k >= 0.5, "c": _rng.randi() % 4})
	for f in _falling:
		f["t"] += delta
		if f["fall"] > 0.0:
			var dy: float = f["v"] * delta
			f["fall"] -= dy
			f["pos"] += Vector2(cos(float(f["t"]) * 2.2 + float(f["ph"])) * float(f["sway"]) * delta * 2.0 + 3.0 * delta, dy)
	_falling = _falling.filter(func(f: Dictionary) -> bool: return f["fall"] > -40.0 and f["t"] < 16.0)
	for f in _falling:
		if f["fall"] <= 0.0:
			f["fall"] -= delta * 12.0
	# 蛾：繞著花叢不規則地飛；轉場時往外飛走
	for m in _moths:
		var t := _time * 1.3 + float(m["phase"])
		var home: Vector2 = m["home"]
		if k > 0.05:
			m["away"] += Vector2(signf(home.x) * 40.0, -30.0) * delta
		else:
			m["away"] = Vector2.ZERO
		m["pos"] = home + Vector2(sin(t) * 14.0 + sin(t * 2.7) * 5.0, cos(t * 1.4) * 7.0 + sin(t * 3.1) * 3.0) + m["away"]
	# 螢火蟲：慢慢漂、一閃一閃
	for fl in _flies:
		var a: Rect2 = fl["area"]
		fl["v"] += Vector2(_rng.randf_range(-6, 6), _rng.randf_range(-6, 6)) * delta
		fl["v"] = (fl["v"] as Vector2).limit_length(6.0)
		fl["pos"] += (fl["v"] as Vector2) * delta
		if not a.has_point(fl["pos"]):
			fl["v"] = (a.get_center() - (fl["pos"] as Vector2)).normalized() * 4.0
	queue_redraw()


func _draw() -> void:
	var k := _phase()
	for f in _falling:
		var a := 1.0 if float(f["fall"]) > 0.0 else clampf(1.0 + float(f["fall"]) / 40.0, 0.0, 1.0)
		var c: Color = ASH[int(f["c"]) % 3] if f["ash"] else LEAVES[int(f["c"])]
		var p: Vector2 = (f["pos"] as Vector2).round()
		var flip: bool = int(float(f["t"]) * 4.0 + float(f["ph"])) % 2 == 0 and float(f["fall"]) > 0.0
		draw_rect(Rect2(p, Vector2(2, 1) if flip else Vector2(1, 1)), Color(c, a))
	if k < 0.6:
		for m in _moths:
			var p: Vector2 = (m["pos"] as Vector2).round()
			var up := int(_time * 14.0 + float(m["phase"]) * 3.0) % 2 == 0
			var a := 1.0 - k / 0.6
			draw_rect(Rect2(p, Vector2(1, 1)), Color(MOTH, a))
			draw_rect(Rect2(p + Vector2(-1, -1 if up else 0), Vector2(1, 1)), Color(MOTH, a * 0.8))
			draw_rect(Rect2(p + Vector2(1, -1 if up else 0), Vector2(1, 1)), Color(MOTH, a * 0.8))
	if k < 1.0:
		for fl in _flies:
			var glow := 0.5 + 0.5 * sin(_time * 2.3 + float(fl["phase"]))
			if glow > 0.35:
				draw_rect(Rect2((fl["pos"] as Vector2).round(), Vector2(1, 1)), Color(FIREFLY, (glow - 0.35) * 1.4 * (1.0 - k)))
