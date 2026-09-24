extends Node2D
## 主角的佔位圖形（plan §4）：藍色膠囊（腳底圓半徑 8、高 40）、指向面向的白色短線（劍）、腳底橢圓陰影。
## 只讀取 PlayerSim 的狀態，不改動它。

const R := PlayerData.HURT_RADIUS
const H := PlayerData.HEIGHT
const S := PlayerSim.State
## 劍長（畫面用）
const SWORD_LEN := 17.0

var arena: CombatArena
var _flash_red := 0.0
var _flash_white := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _process(delta: float) -> void:
	var p: PlayerSim = arena.sim.player
	position = p.pos.round()
	var real_dt := delta / maxf(Engine.time_scale, 0.001)
	_flash_red = maxf(_flash_red - real_dt, 0.0)
	_flash_white = maxf(_flash_white - real_dt, 0.0)
	queue_redraw()


func flash_hurt() -> void:
	_flash_red = FeedbackData.PLAYER_FLASH_TIME


func flash_charge() -> void:
	_flash_white = 0.12


func _draw() -> void:
	var p: PlayerSim = arena.sim.player
	DrawUtil.fill_ellipse(self, Vector2(0, 1), Vector2(R + 3, 4), Palette.SHADOW, 16)
	if p.state == S.DODGE and p.state_elapsed() < Frames.of(PlayerData.DODGE_TIME):
		_draw_afterimages(p)
	if p.state == S.CHARGE:
		_draw_charge_glow(p)
	_draw_body(p)
	_draw_sword(p)


func _body_color(base: Color) -> Color:
	if _flash_red > 0.0:
		return base.lerp(Color(1, 0.2, 0.2), 0.7)
	if _flash_white > 0.0:
		return base.lerp(Color.WHITE, 0.8)
	return base


func _draw_body(p: PlayerSim, offset := Vector2.ZERO, alpha := 1.0) -> void:
	var f := p.facing
	var dark := Palette.PLAYER_DARK
	var body := _body_color(Palette.PLAYER)
	var light := _body_color(Palette.PLAYER_LIGHT)
	dark.a = alpha
	body.a = alpha
	light.a = alpha
	DrawUtil.fill_capsule(self, offset + Vector2(0, 1), R + 1, H + 2, dark)
	DrawUtil.fill_capsule(self, offset, R, H, body)
	if alpha < 1.0:
		return
	# 胸甲高光
	draw_rect(Rect2(offset + Vector2(-5 + roundf(f.x * 2), -27), Vector2(3, 12)), light)
	# 頭盔面甲：朝面向偏移，背對時看不到
	if f.y > -0.5:
		draw_rect(Rect2(offset + Vector2(-4 + roundf(f.x * 3), -35), Vector2(8, 3)), Palette.PLAYER_DARK)
	# 羽飾
	draw_colored_polygon(PackedVector2Array([offset + Vector2(-2, -40), offset + Vector2(2, -40),
		offset + Vector2(-roundf(f.x * 6) + 1, -47)]), Palette.PLAYER_PLUME)


## 閃身的三道殘影（§7：由程式產生）
func _draw_afterimages(p: PlayerSim) -> void:
	for i in [3, 2, 1]:
		var off: Vector2 = (-p.dodge_dir * 9.0 * i).round()
		_draw_body(p, off, 0.18 + 0.12 * (3 - i))


func _draw_charge_glow(p: PlayerSim) -> void:
	var k := clampf(float(p.state_elapsed()) / Frames.of(PlayerData.CHARGE_TIME), 0.0, 1.0)
	var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() * (0.012 if p.charge_full else 0.006))
	var c := Palette.PLAYER_LIGHT if not p.charge_full else Color(0.9, 0.95, 1.0)
	c.a = 0.25 + 0.45 * k * pulse
	DrawUtil.stroke_ellipse(self, Vector2(0, -20), Vector2(13, 25) * (0.9 + 0.1 * k), c, 1.0, 32)


## 劍的方向：依攻擊段數與幀數做出揮砍姿勢（第 2 段反手、第 4 段大幅度）
func _sword_dir(p: PlayerSim) -> Vector2:
	var f := p.facing
	var e := p.state_elapsed()
	match p.state:
		S.ATTACK:
			var a := p.attack
			var st := a.startup_frames()
			var act_end := a.active_end_frame()
			var span := deg_to_rad(PlayerData.ATTACK_ARC_DEG) * (0.8 if p.combo_index == 3 else 0.55)
			var from := -span
			var to := span
			if p.combo_index == 1:
				from = span
				to = -span
			var ang: float
			if e < st:
				ang = lerpf(0.0, from, float(e) / maxf(st, 1))
			elif e < act_end:
				ang = lerpf(from, to, float(e - st + 1) / (act_end - st))
			else:
				var rec := float(e - act_end) / maxf(a.total_frames() - act_end, 1)
				ang = lerpf(to, 0.0, clampf(rec * 1.5 - 0.5, 0.0, 1.0))
			return f.rotated(ang)
		S.CHARGE:
			return f.rotated(PI * 0.8)
		S.DODGE:
			return -p.dodge_dir.rotated(0.3)
	return f


func _draw_sword(p: PlayerSim) -> void:
	var f := p.facing
	var sd := _sword_dir(p)
	var length := SWORD_LEN
	# 持劍的手在身體外側，面向正上或正下時劍也不會被身體遮住
	var side := 1.0 if f.x >= -0.2 else -1.0
	var hand := Vector2(side * 9 + roundf(f.x * 2), -17 + roundf(f.y * 3))
	if p.state == S.THRUST:
		hand = Vector2(roundf(f.x * 8), -16 + roundf(f.y * 4))
		length = 22.0
	elif p.state == S.ATTACK:
		# 揮砍時手在身體前方（面向上時在頭頂上方，劍不會被身體蓋住）
		hand = (Vector2(0, -20) + f * 9).round()
	draw_line(hand, (hand + sd * length).round(), Palette.SWORD, 2.0)
	draw_line(hand - sd.orthogonal() * 3, hand + sd.orthogonal() * 3, Palette.PLAYER_DARK, 1.0)
