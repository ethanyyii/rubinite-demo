extends Camera2D
## 鏡頭跟隨玩家輕微移動（arena.md §2），並略為偏向 Boss，讓兩者都留在畫面內。
## 震動以實際時間計算，頓幀期間照常震動（combat-design §12）。

## 鏡頭跟隨玩家的比例：場地只比畫面大一點，所以只做輕微移動
const FOLLOW := 0.6
## 焦點從玩家往 Boss 偏移的比例
const LEAN_TO_BOSS := 0.35
## 角色圖形往上延伸（Boss 高 120），焦點往上提一點
const HEIGHT_OFFSET := -28.0
## 鏡頭中心的活動範圍（畫面 640×360，場地與外圍約 800×490）。
## 上方多留一些：Boss 站在北邊緣時頭頂在 y ≈ -294。
const LIMIT_MIN := Vector2(-80.0, -120.0)
const LIMIT_MAX := Vector2(80.0, 70.0)
const SMOOTH := 8.0

var arena: CombatArena
var _shake := 0.0
var _shake_time := 0.0
var _shake_left := 0.0
var _rng := RandomNumberGenerator.new()
var _center := Vector2.ZERO


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	_center = _target()
	position = _center


func add_shake(amount: float, duration: float) -> void:
	if amount <= 0.0 or duration <= 0.0:
		return
	if amount >= _shake * (_shake_left / maxf(_shake_time, 0.001)):
		_shake = amount
		_shake_time = duration
		_shake_left = duration


func snap() -> void:
	_center = _target()
	position = _center.round()


func _target() -> Vector2:
	var sim: CombatSim = arena.sim
	var focus := sim.player.pos.lerp(sim.boss.pos, LEAN_TO_BOSS)
	var t := focus * FOLLOW + Vector2(0, HEIGHT_OFFSET)
	return t.clamp(LIMIT_MIN, LIMIT_MAX)


func _process(delta: float) -> void:
	# 以實際時間計算，慢動作（Engine.time_scale）與頓幀都不影響鏡頭
	var real_dt := delta / maxf(Engine.time_scale, 0.001)
	_center = _center.lerp(_target(), 1.0 - exp(-SMOOTH * real_dt))
	var offset_px := Vector2.ZERO
	if _shake_left > 0.0:
		_shake_left = maxf(_shake_left - real_dt, 0.0)
		var k := _shake_left / _shake_time
		offset_px = Vector2(_rng.randf_range(-1, 1), _rng.randf_range(-1, 1)) * _shake * k
	position = (_center + offset_px).round()


func shake_offset_active() -> bool:
	return _shake_left > 0.0
