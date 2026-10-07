extends Node2D
## 一隻烏鴉（2026-10-06，場景加料）：停在場地外圈（火盆邊、倒木、墳上、北邊草地），和角色一起依 Y 排序；
## 偶爾低頭啄一下、轉頭。主角或 Boss 走近時飛走，過一陣子（附近沒人）再飛回來；Boss 一進轉場全部飛走，第二階段不回來。
## 飛的時候在所有東西上面（在空中）。1–5 px，不擋戰鬥。

const BODY := Color(0.07, 0.07, 0.08)
const SHEEN := Color(0.2, 0.21, 0.26)
const STARTLE := 115.0
const CALM := 170.0
const AWAY_TIME := 7.0

enum Mode { PERCHED, FLEEING, AWAY, RETURNING }

var arena: CombatArena
## 停的地方（腳）；節點的位置是排序用的那一列（停在物件上時是物件的腳底，畫在物件前面），畫的時候往上移 _lift
var home: Vector2
var _sort_y := 0.0
var _lift := 0.0
var _pos := Vector2.ZERO
var mode := Mode.PERCHED
var _v := Vector2.ZERO
var _t := 0.0
var _away := 0.0
var _from := Vector2.ZERO
var _face := 1.0
var _rng := RandomNumberGenerator.new()


func setup(perch: Dictionary, owner_arena: CombatArena, seed_: int) -> void:
	home = perch["feet"]
	_sort_y = perch["sort_y"]
	_pos = home
	arena = owner_arena
	_rng.seed = seed_
	_t = _rng.randf() * 10.0
	_face = -1.0 if _rng.randf() < 0.5 else 1.0


func _phase() -> float:
	var fv: Node = arena.get_node_or_null("ArenaFloor")
	return fv.scene_phase() if fv != null else 0.0


func _near(r: float) -> bool:
	var sim: CombatSim = arena.sim
	return sim.player.pos.distance_to(home) < r or sim.boss.pos.distance_to(home) < r + VeltharisData.HURT_RADIUS


func _process(delta: float) -> void:
	_t += delta
	var k := _phase()
	match mode:
		Mode.PERCHED:
			if k > 0.02 or _near(STARTLE):
				mode = Mode.FLEEING
				_v = Vector2(signf(home.x) * _rng.randf_range(30, 70), _rng.randf_range(-80, -50))
				_face = signf(_v.x)
			elif _rng.randf() < delta * 0.3:
				_face = -_face
		Mode.FLEEING:
			_v += Vector2(0, -25) * delta
			_pos += _v * delta
			if _pos.y < home.y - 260:
				mode = Mode.AWAY
				_away = 0.0
		Mode.AWAY:
			_away += delta
			if k <= 0.0 and _away > AWAY_TIME and not _near(CALM):
				mode = Mode.RETURNING
				_from = home + Vector2(signf(home.x) * 160.0, -220.0)
				_away = 0.0
		Mode.RETURNING:
			_away += delta / 1.6
			var u := minf(_away, 1.0)
			_pos = _from.lerp(home, u) + Vector2(0, -sin(u * PI) * 20.0)
			_face = signf(home.x - _from.x)
			if k > 0.02 or _near(STARTLE):
				mode = Mode.FLEEING
				_v = Vector2(signf(home.x) * 50.0, -70.0)
			elif u >= 1.0:
				mode = Mode.PERCHED
				_pos = home
	position = Vector2(_pos.x, _sort_y + (_pos.y - home.y))
	_lift = _sort_y - home.y
	visible = mode != Mode.AWAY
	z_index = 30 if mode == Mode.FLEEING or mode == Mode.RETURNING else 0
	queue_redraw()


## 新的一場：回到原位停著
func perch_again() -> void:
	mode = Mode.PERCHED
	_pos = home


func _draw() -> void:
	var f := _face
	if mode == Mode.PERCHED:
		# 停著：身體、頭、嘴，偶爾低頭啄一下
		var peck := fmod(_t, 4.3) < 0.25
		draw_rect(_r(-2, -3, 4, 3, f), BODY)
		draw_rect(_r(-1, -3, 2, 1, f), SHEEN)
		draw_rect(_r(1, -5 if not peck else -3, 2, 2, f), BODY)
		draw_rect(_r(3, -4 if not peck else -2, 1, 1, f), SHEEN)
		draw_rect(_r(-3, -2, 1, 1, f), BODY)
		draw_rect(_r(-1, 0, 1, 1, f), BODY)
		draw_rect(_r(1, 0, 1, 1, f), BODY)
	else:
		# 飛：翅膀上下兩張
		var up := int(_t * 12.0) % 2 == 0
		draw_rect(_r(-1, -1, 3, 2, f), BODY)
		draw_rect(_r(2, -2, 1, 1, f), BODY)
		draw_rect(_r(-3, -2 if up else 0, 2, 1, f), BODY)
		draw_rect(_r(2, -2 if up else 0, 2, 1, f), SHEEN)


## 朝左時左右翻過來
func _r(x: float, y: float, w: float, h: float, f: float) -> Rect2:
	return Rect2(Vector2(x if f > 0.0 else -x - w, y - _lift), Vector2(w, h))
