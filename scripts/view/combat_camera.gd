extends Camera2D
## 鏡頭跟隨玩家輕微移動（arena.md §2），並略為偏向 Boss，讓兩者都留在畫面內。
## 震動在 _process 以 delta 計算：頓幀期間照常震動（combat-design §12），F2 慢動作時一起變慢。

## 鏡頭跟隨玩家的比例：場地只比畫面大一點，所以只做輕微移動
const FOLLOW := 0.6
## 焦點從玩家往 Boss 偏移的比例
const LEAN_TO_BOSS := 0.35
## 角色圖形往上延伸（Boss 高 160），焦點往上提一點
const HEIGHT_OFFSET := -37.0
## 鏡頭中心的活動範圍（畫面 960×540，場地 1080×600、含外圍約 1200×740；2026-09-30 鏡頭拉遠、場地放大 1.5 倍）。
## 上方多留一些：Boss 站在北邊緣（y = -265）時王冠尖在 y ≈ -430，鏡頭中心要能到 -430 + 270 = -160 以上。
const LIMIT_MIN := Vector2(-120.0, -170.0)
const LIMIT_MAX := Vector2(120.0, 105.0)
const SMOOTH := 8.0
## 玩家一定要完整留在畫面安全區內：腳底在 Boss 名稱與血條（畫面下緣約 68px）之上，頭頂不出畫面
const HALF_VIEW := Vector2(480.0, 270.0)
## 下緣留給 Boss 名稱與血條（HUD 照 1.5 倍排，約 70px）
const SAFE_BOTTOM := 75.0
const SAFE_TOP := 56.0
const SAFE_SIDE := 24.0
## Boss 王冠上方要留的空間（王冠的尖刺比身高再高幾 px）
const BOSS_TOP_MARGIN := 8.0

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
	return target_for(sim.player.pos, sim.boss.pos)


## 鏡頭中心：先依玩家與 Boss 取焦點並限制在場地範圍內；Boss 的頭頂盡量留在畫面內（2026-09-30：Boss 放大到
## 160 後，站在北邊時王冠會被切掉）；最後保證玩家在安全區內（玩家優先，兩者距離太遠時 Boss 出畫面，HUD 在上緣標方向）。
static func target_for(player_pos: Vector2, boss_pos: Vector2) -> Vector2:
	var focus := player_pos.lerp(boss_pos, LEAN_TO_BOSS)
	var t := (focus * FOLLOW + Vector2(0, HEIGHT_OFFSET)).clamp(LIMIT_MIN, LIMIT_MAX)
	var crown := boss_pos.y - VeltharisData.HEIGHT - BOSS_TOP_MARGIN
	t.y = maxf(minf(t.y, crown + HALF_VIEW.y), LIMIT_MIN.y)
	return clamp_safe(t, player_pos)


## 讓鏡頭中心 c 保證玩家完整在安全區內
static func clamp_safe(c: Vector2, player_pos: Vector2) -> Vector2:
	return Vector2(
		clampf(c.x, player_pos.x + SAFE_SIDE - HALF_VIEW.x, player_pos.x - SAFE_SIDE + HALF_VIEW.x),
		clampf(c.y, player_pos.y + SAFE_BOTTOM - HALF_VIEW.y, player_pos.y - SAFE_TOP + HALF_VIEW.y))


## 鏡頭中心跟模擬同步在物理幀更新（角色也是 60Hz 移動），避免高更新率螢幕上角色相對鏡頭抖動。
## 平滑之後再套一次安全區限制：鏡頭追不上時玩家也不會被 Boss 血條蓋住。
func _physics_process(delta: float) -> void:
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	var sim: CombatSim = arena.sim
	_center = clamp_safe(_center.lerp(_target(), 1.0 - exp(-SMOOTH * real_dt)), sim.player.pos)


func _process(delta: float) -> void:
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	var offset_px := Vector2.ZERO
	if _shake_left > 0.0:
		_shake_left = maxf(_shake_left - real_dt, 0.0)
		var k := _shake_left / _shake_time
		offset_px = Vector2(_rng.randf_range(-1, 1), _rng.randf_range(-1, 1)) * _shake * k
	position = (_center + offset_px).round()


func shake_offset_active() -> bool:
	return _shake_left > 0.0
