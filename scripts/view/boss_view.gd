extends Node2D
## Boss 的畫面（2026-10-05 接進遊戲；之前是佔位的膠囊和長方形大劍）。
## 精靈圖：BossAnim 每個戰鬥幀選格（CombatArena 在 sim.step() 之後呼叫 sim_stepped()），子節點用調色盤著色器
## 畫打包好的格子（BossSprites）。受擊閃白、失衡時紅火暗下、死亡後化為灰燼消散在著色器裡做。
## 程式畫的特效照舊：腳下的影子（墜王之躍騰空時變小）、落點陰影、起手預兆（劍變亮紅、延遲停住時劍閃爍和符文、
## 灰燼衝擊的頭盔十字紅光＋頭頂星形）、第二階段劍上的火焰。劍的位置用幀表每一張記下的握柄、劍尖。
## 只讀取 BossSim 的狀態，不改動它。

const R := VeltharisData.HURT_RADIUS
const H := VeltharisData.HEIGHT
const BS := BossSim.State
const TG := CombatTypes.Telegraph
const S := preload("res://scripts/view/boss_sprites.gd")
## 頭頂星形、畫面外指示用的倍率（舊的佔位圖形照 120px 的 Boss 寫的）
const K := VeltharisData.HEIGHT / 120.0
const SHADER := preload("res://scripts/view/boss_palette.gdshader")
const FADE_TIME := 1.6                    # 死亡：跪下、往前垂之後化為灰燼的時間（boss §8.2，程式做）
const FLARE_ARMS := Vector2(80, 34)       # 頭盔十字紅光最大時的長度（tools/boss_rig/export_cleave.py 的 FLARE_ARMS）
const FLARE_MIN := 0.35

var arena: CombatArena
var anim := BossAnim.new()
var _flash_white := 0.0
var _sprite: BossSprite
var _over: Over
var _mat: ShaderMaterial

## 畫出來的身體（目前這一格）相對腳底的範圍：主角在 Boss 後面被擋住時畫剪影（player_view）、頭頂星形的位置
static var _live_rect := {}


class BossSprite extends Node2D:
	var tex: Texture2D
	var src := Rect2()
	var dst := Rect2()

	func _draw() -> void:
		if tex != null:
			draw_texture_rect_region(tex, dst, src)


class Over extends Node2D:
	var view: Node2D

	func _draw() -> void:
		view.draw_over(self)


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	_mat.set_shader_parameter("palette", S.palette())
	# 打包好的圖在開場一次載完（第一次用到才載會在出招時卡一下）
	for i in (S.data()["atlases"] as Array).size():
		S.atlas(i)
	_sprite = BossSprite.new()
	_sprite.name = "Sprite"
	_sprite.material = _mat
	add_child(_sprite)
	_over = Over.new()
	_over.name = "Over"
	_over.view = self
	add_child(_over)
	anim.update(arena.sim.boss)


## CombatArena 每次 sim.step() 之後呼叫：一個戰鬥幀都不漏（頓幀時戰鬥幀不動，畫面停在那一格）
func sim_stepped() -> void:
	anim.update(arena.sim.boss)


func _process(delta: float) -> void:
	var b: BossSim = arena.sim.boss
	position = b.pos.round()
	_flash_white = maxf(_flash_white - delta, 0.0)  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	var alpha := 1.0
	if b.state == BS.DEAD and anim.done_at >= 0:
		alpha = 1.0 - clampf(float(b.state_elapsed() - anim.done_at) / Frames.of(FADE_TIME), 0.0, 1.0)
	_mat.set_shader_parameter("alpha", alpha)
	_mat.set_shader_parameter("mix_amount", 0.8 if _flash_white > 0.0 else 0.0)
	_mat.set_shader_parameter("darken", 0.45 if b.state in [BS.BROKEN, BS.EXECUTED] else 0.0)
	if anim.frame_id >= 0:
		var f := S.frame(anim.frame_id)
		_sprite.tex = S.atlas(int(f[0]))
		_sprite.src = Rect2(f[1], f[2], f[3], f[4])
		_sprite.dst = Rect2(Vector2(f[5], f[6]) + anim.offset, Vector2(f[3], f[4]))
		_live_rect[b.get_instance_id()] = _sprite.dst
	else:
		_sprite.tex = null
	queue_redraw()
	_sprite.queue_redraw()
	_over.modulate.a = alpha
	_over.queue_redraw()


func flash_hit() -> void:
	_flash_white = FeedbackData.BOSS_FLASH_TIME


# --- 精靈圖下面：影子 -------------------------------------------------------------

func _draw() -> void:
	var b: BossSim = arena.sim.boss
	if b.move != null and b.move.airborne_start >= 0.0 and b.state == BS.ATTACK and b.state_elapsed() < b.hit_start_frame(0):
		_draw_landing_shadow(b)
	var shrink := 1.0 - 0.5 * clampf(anim.lift / 92.0, 0.0, 1.0)
	DrawUtil.fill_ellipse(self, Vector2(0, 2), Vector2(R + 8, 12) * shrink, Palette.SHADOW, 24)


## 落點陰影：追蹤玩家，越接近落地越小；縮到最小的瞬間就是落地時機（boss §5.2）
func _draw_landing_shadow(b: BossSim) -> void:
	var local := b.landing_target - b.pos
	var land := b.hit_start_frame(0)
	var k := clampf(float(b.state_elapsed()) / float(land), 0.0, 1.0)
	var r := lerpf(64.0, 30.0, k) * K
	DrawUtil.fill_ellipse(self, local, Vector2(r, r * 0.45), Color(0, 0, 0, 0.25 + 0.3 * k), 28)
	DrawUtil.stroke_ellipse(self, local, Vector2(r, r * 0.45), Color(0.8, 0.2, 0.1, 0.5 + 0.4 * k), 1.0, 28)


# --- 精靈圖上面：預兆、火焰 ---------------------------------------------------------

## 這一張的握柄、劍尖（相對腳底；攻擊的圖才有）
func _blade() -> Array:
	var c := S.clip(anim.clip)
	if not c.has("at") or anim.col >= (c["at"] as Array).size():
		return []
	var p: Array = c["at"][anim.col][anim.row]
	if p[1] == null:
		return []
	return [Vector2(p[0][0], p[0][1]) + anim.offset, Vector2(p[1][0], p[1][1]) + anim.offset]


func draw_over(node: Node2D) -> void:
	var b: BossSim = arena.sim.boss
	var tg := b.telegraph()
	var blade := _blade()
	if tg == TG.NORMAL and not blade.is_empty():
		# 起手：劍變亮紅
		var g := Palette.TELEGRAPH
		g.a = 0.4
		node.draw_line(blade[0].round(), blade[1].round(), g, 7.0)
	elif tg == TG.DELAYED and not blade.is_empty():
		# 延遲停住：劍身閃爍（紅白交替，每 4 幀）＋沿劍身的符文輪流亮起
		var on := (b.state_elapsed() >> 2) % 2 == 0
		var c := Palette.TELEGRAPH if on else Color(1, 0.9, 0.85)
		c.a = 0.45
		node.draw_line(blade[0].round(), blade[1].round(), c, 7.0)
		var d: Vector2 = (blade[1] - blade[0])
		var n := 5
		var lit := (b.state_elapsed() >> 1) % n
		for k in n:
			var pt: Vector2 = (blade[0] + d * (0.15 + 0.17 * k)).round()
			node.draw_rect(Rect2(pt - Vector2(1, 1), Vector2(3, 3)), Color(1, 1, 1) if k == lit else Color(1, 0.85, 0.8, 0.8))
	_draw_flare(node, b)
	if tg == TG.DANGER:
		_draw_danger_star(node, b)
	if (b.phase == 2 or b.state == BS.TRANSITION) and not blade.is_empty():
		_draw_flames(node, blade)


## 灰燼衝擊：頭盔十字閃一下紅光（最亮的那一刻是危險預兆開始；淡入淡出約 0.3 秒；橫寬直窄）。
## 頭盔上的十字變亮畫在精靈圖裡，光芒由這裡畫（幀表 flash：哪一幀、在哪裡、大小與亮度的曲線）
func _draw_flare(node: Node2D, b: BossSim) -> void:
	if b.state != BS.ATTACK:
		return
	var c := S.clip(anim.clip)
	if not c.has("flash"):
		return
	var e := b.state_elapsed()
	for fl: Dictionary in c["flash"]:
		var rel := e - int(fl["peak"])
		for pt: Array in fl["curve"]:
			if int(pt[0]) != rel:
				continue
			var at: Array = fl["at"][anim.row]
			var center := Vector2(float(at[0]), float(at[1])) + anim.offset
			var size := float(pt[1])
			var level := float(pt[2])
			_cross(node, center, FLARE_ARMS * size, Color(0.86, 0.15, 0.2, 0.85 * level))
			if level > 0.5:
				_cross(node, center, FLARE_ARMS * size * 0.45, Color(0.95, 0.55, 0.45, 0.8 * level))
			if level > 0.75:
				DrawUtil.fill_ellipse(node, center, Vector2(4, 3), Color(1.0, 0.85, 0.75, level), 12)


func _cross(node: Node2D, c: Vector2, arms: Vector2, col: Color) -> void:
	var w := maxf(2.0, arms.y * 0.18)
	var h := maxf(2.0, arms.x * 0.06)
	node.draw_colored_polygon(PackedVector2Array([c + Vector2(-arms.x, 0), c + Vector2(0, -h), c + Vector2(arms.x, 0),
		c + Vector2(0, h)]), col)
	node.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -arms.y), c + Vector2(w, 0), c + Vector2(0, arms.y),
		c + Vector2(-w, 0)]), col)


## 危險預兆：頭頂的白色星形圖示（色盲也能辨識的形狀）
func _draw_danger_star(node: Node2D, b: BossSim) -> void:
	var top := body_rect(b).position.y
	var c := Vector2(0, top - 22 * K * 0.5)
	var pulse := 1.0 + 0.2 * sin(Time.get_ticks_msec() * 0.03)
	DrawUtil.fill_ellipse(node, c, Vector2(15, 15) * pulse, Color(1, 1, 1, 0.25), 20)
	node.draw_colored_polygon(DrawUtil.star_points(c, 11.0 * pulse, 4.5 * pulse), Palette.DANGER)
	var pts := DrawUtil.star_points(c, 12.0 * pulse, 5.0 * pulse)
	pts.append(pts[0])
	node.draw_polyline(pts, Color(0.2, 0.2, 0.25), 1.0)


## 第二階段：大劍燃起更猛烈的火焰（boss §5）
func _draw_flames(node: Node2D, blade: Array) -> void:
	var t := Time.get_ticks_msec() * 0.001
	var hand: Vector2 = blade[0]
	var d: Vector2 = (blade[1] - blade[0])
	for i in 7:
		var k := float(i) / 6.0
		var base := hand + d * (0.12 + k * 0.88)
		var flick := sin(t * 18.0 + i * 1.7) * 2.0
		var up := Vector2(0, -6.0 - 4.0 * absf(sin(t * 11.0 + i)))
		var c := Palette.BOSS_EMBER.lerp(Color(1, 0.9, 0.4), 0.5 + 0.5 * sin(t * 9.0 + i))
		c.a = 0.85
		node.draw_line(base.round(), (base + up + Vector2(flick, 0)).round(), c, 2.0)


# --- 給別的畫面讀的 -------------------------------------------------------------------

## 畫出來的身體（目前這一格）相對腳底的範圍：主角在 Boss 後面被擋住時畫剪影（player_view）。
## 畫面還沒畫過這個 Boss（測試）時，照它現在的狀態選一格量
static func body_rect(b: BossSim) -> Rect2:
	var id := b.get_instance_id()
	if _live_rect.has(id):
		return _live_rect[id]
	var a := BossAnim.new()
	a.update(b)
	if a.frame_id < 0:
		return Rect2(-R - 1, -H - 1, 2 * R + 2, H + 2)
	var f := S.frame(a.frame_id)
	return Rect2(Vector2(f[5], f[6]) + a.offset, Vector2(f[3], f[4]))


## 墜王之躍的騰空高度（負值往上；精靈圖已經畫高了，準星跟著升高用）
static func leap_lift(b: BossSim) -> float:
	if not b.is_airborne():
		return 0.0
	var c := S.clip("boss_leap")
	return -float(c["lift"][S.col_at(c["holds"], b.state_elapsed())])
