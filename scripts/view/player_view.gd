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
## 擊敗 Boss 後鎧甲多一道紅色裂紋（combat-design §15、player-knight §1）；重試後保留
var ember_crack := false
var _stagger_tint := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _process(delta: float) -> void:
	var p: PlayerSim = arena.sim.player
	position = p.pos.round()
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
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
	match p.state:
		S.LAUNCHED, S.DOWN, S.DEAD:
			_draw_lying(p)
			return
		S.GETUP:
			var k := clampf(float(p.state_elapsed()) / Frames.of(PlayerData.GETUP_TIME), 0.0, 1.0)
			_draw_body(p, Vector2.ZERO, 1.0, lerpf(18.0, H, k))
			return
		S.POSTURE_BREAK:
			_draw_posture_break(p)
			return
	if p.state == S.DODGE and p.state_elapsed() < Frames.of(PlayerData.DODGE_TIME):
		_draw_afterimages(p)
	if p.state == S.CHARGE:
		_draw_charge_glow(p)
	if p.state == S.HEAL:
		_draw_heal_glow(p)
	var lean := Vector2.ZERO
	_stagger_tint = 0.0
	if p.state == S.STAGGER:
		# 踉蹌：身體往後仰，整段硬直期間帶紅色（越接近恢復越淡）
		var k := 1.0 - clampf(float(p.state_elapsed()) / Frames.of(PlayerData.STAGGER_TIME), 0.0, 1.0)
		lean = (-p.facing * 3.0 * k + Vector2(0, 1)).round()
		_stagger_tint = 0.55 * k
	_draw_body(p, lean)
	if p.state == S.BLOCK:
		_draw_guard(p)
	else:
		_draw_sword(p)


func _body_color(base: Color) -> Color:
	if _flash_red > 0.0:
		return base.lerp(Color(1, 0.2, 0.2), 0.7)
	if _stagger_tint > 0.0:
		return base.lerp(Color(1, 0.25, 0.25), _stagger_tint)
	if _flash_white > 0.0:
		return base.lerp(Color.WHITE, 0.8)
	return base


func _draw_body(p: PlayerSim, offset := Vector2.ZERO, alpha := 1.0, height := H) -> void:
	# 第 3 段迴旋斬：面甲跟著身體轉一圈
	var f := p.facing.rotated(spin_turn(p))
	var dark := Palette.PLAYER_DARK
	var body := _body_color(Palette.PLAYER)
	var light := _body_color(Palette.PLAYER_LIGHT)
	dark.a = alpha
	body.a = alpha
	light.a = alpha
	DrawUtil.fill_capsule(self, offset + Vector2(0, 1), R + 1, height + 2, dark)
	DrawUtil.fill_capsule(self, offset, R, height, body)
	if alpha < 1.0:
		return
	var top := offset + Vector2(0, H - height)
	# 胸甲高光
	draw_rect(Rect2(top + Vector2(-5 + roundf(f.x * 2), -27), Vector2(3, minf(12.0, height - 26.0))), light)
	# 頭盔面甲：朝面向偏移，背對時看不到
	if f.y > -0.5:
		draw_rect(Rect2(top + Vector2(-4 + roundf(f.x * 3), -35), Vector2(8, 3)), Palette.PLAYER_DARK)
	# 羽飾
	draw_colored_polygon(PackedVector2Array([top + Vector2(-2, -40), top + Vector2(2, -40),
		top + Vector2(-roundf(f.x * 6) + 1, -47)]), Palette.PLAYER_PLUME)
	if ember_crack:
		# 執魂侵蝕：一道紅色裂紋爬上鎧甲
		draw_polyline(PackedVector2Array([top + Vector2(3, -12), top + Vector2(1, -18), top + Vector2(4, -23),
			top + Vector2(2, -29)]), Color(1.0, 0.25, 0.15), 1.0)


## 擊飛（拋物線）、倒地、死亡：身體橫躺
func _draw_lying(p: PlayerSim) -> void:
	var lift := 0.0
	var alpha := 1.0
	if p.state == S.LAUNCHED:
		var k := clampf(float(p.state_elapsed()) / Frames.of(PlayerData.LAUNCH_TIME), 0.0, 1.0)
		lift = -sin(PI * k) * 14.0
	elif p.state == S.DEAD:
		alpha = 1.0 - 0.6 * clampf(float(p.state_elapsed()) / Frames.of(PlayerData.DEATH_TIME), 0.0, 1.0)
	var dark := Palette.PLAYER_DARK
	var body := _body_color(Palette.PLAYER)
	dark.a = alpha
	body.a = alpha
	var c := Vector2(0, -8 + lift).round()
	DrawUtil.fill_capsule_h(self, c + Vector2(0, 1), 21, 9, dark)
	DrawUtil.fill_capsule_h(self, c, 20, 8, body)
	var head_x := 12.0 if p.facing.x < 0.0 else -12.0
	draw_colored_polygon(PackedVector2Array([c + Vector2(head_x, -6), c + Vector2(head_x + signf(head_x) * 7, -3),
		c + Vector2(head_x, 0)]), Palette.PLAYER_PLUME)
	draw_line(c + Vector2(-head_x, 4), c + Vector2(-head_x * 1.9, 9), Palette.SWORD, 2.0)


## 架勢崩潰：單膝跪地、身體搖晃、頭上有暈眩的小點
func _draw_posture_break(p: PlayerSim) -> void:
	var t := float(p.state_elapsed()) / Frames.FPS
	var wobble := Vector2(roundf(sin(t * 14.0) * 1.5), 0)
	_draw_body(p, wobble, 1.0, 30.0)
	draw_line(Vector2(9, -12) + wobble, Vector2(16, 0), Palette.SWORD, 2.0)
	# 頭上繞圈的暈眩星點與驚嘆號（架勢崩潰一眼可辨）
	var outline := Color(0.1, 0.08, 0.05)
	for i in 4:
		var a := t * 6.0 + TAU * i / 4.0
		var dot := Vector2(cos(a) * 11.0, -40 + sin(a) * 3.5).round() + wobble
		draw_rect(Rect2(dot - Vector2(2, 2), Vector2(5, 5)), outline)
		draw_rect(Rect2(dot - Vector2(1, 1), Vector2(3, 3)), Palette.UI_POSTURE)
	var mark := Vector2(0, -54) + wobble
	draw_rect(Rect2(mark + Vector2(-2, -1), Vector2(5, 9)), outline)
	draw_rect(Rect2(mark + Vector2(-2, 9), Vector2(5, 5)), outline)
	draw_rect(Rect2(mark + Vector2(-1, 0), Vector2(3, 7)), Palette.UI_POSTURE_LOW)
	draw_rect(Rect2(mark + Vector2(-1, 10), Vector2(3, 3)), Palette.UI_POSTURE_LOW)


## 格擋：雙手橫劍擋在身前。完美彈返後幾幀劍被撥開並發亮，普通格擋後劍被壓回
func _draw_guard(p: PlayerSim) -> void:
	var f := p.facing
	var now := arena.sim.combat_frame
	var since_parry := now - p.last_parry_frame
	var since_block := now - p.last_block_frame
	var center := (Vector2(0, -20) + f * 9).round()
	var across := f.orthogonal()
	var color := Palette.SWORD
	if since_parry < 10:
		across = across.rotated(0.5)
		center += (f * 3).round()
		color = Color(1.0, 0.93, 0.6)
	elif since_block < 6:
		center -= (f * 3).round()
	draw_line((center - across * 10).round(), (center + across * 10).round(), color, 2.0)
	draw_line((center - across * 10).round(), (center - across * 13).round(), Palette.PLAYER_DARK, 3.0)
	if arena.debug_info and p.is_perfect_window_open():
		# F1 除錯：完美窗口開著時劍身帶一點亮邊
		var c := Color(1, 1, 1, 0.35)
		draw_line((center - across * 10 + f).round(), (center + across * 10 + f).round(), c, 1.0)


func _draw_heal_glow(p: PlayerSim) -> void:
	var t := float(p.state_elapsed()) / Frames.FPS
	var c := Color(0.55, 1.0, 0.8, 0.5)
	DrawUtil.stroke_ellipse(self, Vector2(0, -1), Vector2(12, 5) * (1.0 + 0.1 * sin(t * 12.0)), c, 1.0, 24)
	for i in 5:
		var k := fmod(t * 1.3 + i * 0.2, 1.0)
		var px := Vector2(sin(i * 2.1) * 8.0, -4 - k * 40.0).round()
		var cc := c
		cc.a = 0.8 * (1.0 - k)
		draw_rect(Rect2(px, Vector2(2, 2)), cc)


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


## 揮砍的起點與終點（相對面向的角度，正值是角色的右手側）：四段各自不同（art-progress「四段輕攻擊」）
## 第 1 段斜劈（右 → 左）、第 2 段反手（左 → 右）、第 3 段迴旋斬（轉一圈，劍從左掃過目標到右：spin_turn）。
## 第 4 段雙手高舉劈地另外畫（_draw_chop_sword）
static func swing_range(stage: int) -> Vector2:
	var span := deg_to_rad(PlayerData.ATTACK_ARC_DEG) * 0.55
	if stage == 1 or stage == 2:
		return Vector2(-span, span)
	return Vector2(span, -span)


## 第 3 段迴旋斬：身體往右轉的角度（弧度，畫面上順時針）。起手轉到 270°（右手側對著目標）時判定開始，
## 判定結束轉滿一圈，收招面向目標。劍一直在身體的右手側
static func spin_turn(p: PlayerSim) -> float:
	if p.state != PlayerSim.State.ATTACK or p.combo_index != 2:
		return 0.0
	var e := p.state_elapsed()
	var st := p.attack.startup_frames()
	var act_end := p.attack.active_end_frame()
	if e < st:
		return deg_to_rad(270.0) * float(e) / st
	if e < act_end:
		return deg_to_rad(lerpf(270.0, 360.0, float(e - st + 1) / (act_end - st)))
	return TAU


## 劍的方向：依攻擊段數與幀數做出揮砍姿勢
func _sword_dir(p: PlayerSim) -> Vector2:
	var f := p.facing
	var e := p.state_elapsed()
	match p.state:
		S.ATTACK:
			var a := p.attack
			var st := a.startup_frames()
			var act_end := a.active_end_frame()
			if p.combo_index == 2:
				# 迴旋斬：劍在右手側跟著身體轉；收招從右手側收回正前方
				if e < act_end:
					return f.rotated(PI / 2 + spin_turn(p))
				var rec2 := float(e - act_end) / maxf(a.total_frames() - act_end, 1)
				return f.rotated(lerpf(PI / 2, 0.0, clampf(rec2 * 1.5 - 0.5, 0.0, 1.0)))
			var r := swing_range(p.combo_index)
			var ang: float
			if e < st:
				ang = lerpf(0.0, r.x, float(e) / maxf(st, 1))
			elif e < act_end:
				ang = lerpf(r.x, r.y, float(e - st + 1) / (act_end - st))
			else:
				var rec := float(e - act_end) / maxf(a.total_frames() - act_end, 1)
				ang = lerpf(r.y, 0.0, clampf(rec * 1.5 - 0.5, 0.0, 1.0))
			return f.rotated(ang)
		S.CHARGE:
			return f.rotated(PI * 0.8)
		S.DODGE:
			return -p.dodge_dir.rotated(0.3)
		S.EXECUTE:
			return f
	return f


## 第 4 段：雙手高舉劈地。起手把劍高舉過頭（劍尖朝上），判定期間沿面向往前下劈，劍尖停在前方地面；
## 收招＋停頓一起慢慢收回（劍在地上多停一下）
func _draw_chop_sword(p: PlayerSim) -> void:
	var f := p.facing
	var a := p.attack
	var e := p.state_elapsed()
	var st := a.startup_frames()
	var act_end := a.active_end_frame()
	# k：0 = 高舉過頭，1 = 劈到前下方
	var k: float
	if e < st:
		k = -0.25 * clampf(float(e) / maxf(st - 2, 1), 0.0, 1.0)
	elif e < act_end:
		k = lerpf(-0.25, 1.0, float(e - st + 1) / (act_end - st))
	else:
		var rec := float(e - act_end) / maxf(a.total_frames() - act_end, 1)
		k = lerpf(1.0, 0.4, clampf(rec * 1.5 - 0.5, 0.0, 1.0))
	# 劍在「面向 × 高度」的直立面上轉：角度 0 朝正上方、90° 朝前方、120° 朝前下方
	var th := lerpf(0.0, deg_to_rad(125.0), clampf(k, 0.0, 1.0)) + minf(k, 0.0)
	var hand := (Vector2(0, -34) + f * 3).lerp(Vector2(0, -18) + f * 8, clampf(k, 0.0, 1.0)).round()
	var blade := f * sin(th) + Vector2(0, -cos(th))
	var tip := hand + blade * 19.0
	tip.y = minf(tip.y, 0.0)  # 劍尖不低於地面（腳底那一列）
	draw_line(hand, tip.round(), Palette.SWORD, 2.0)
	# 雙手握柄：護手畫粗一點
	var guard := (hand - blade * 2.0).round()
	draw_line(guard - blade.orthogonal() * 3, guard + blade.orthogonal() * 3, Palette.PLAYER_DARK, 2.0)


func _draw_sword(p: PlayerSim) -> void:
	var f := p.facing
	var sd := _sword_dir(p)
	var length := SWORD_LEN
	# 持劍的手在身體外側，面向正上或正下時劍也不會被身體遮住
	var side := 1.0 if f.x >= -0.2 else -1.0
	var hand := Vector2(side * 9 + roundf(f.x * 2), -17 + roundf(f.y * 3))
	if p.state == S.THRUST or p.state == S.EXECUTE:
		hand = Vector2(roundf(f.x * 8), -16 + roundf(f.y * 4))
		length = 22.0 if p.state == S.THRUST else 26.0
	elif p.state == S.ATTACK:
		if p.combo_index == 3:
			_draw_chop_sword(p)
			return
		# 揮砍時手在身體前方（面向上時在頭頂上方，劍不會被身體蓋住）
		hand = (Vector2(0, -20) + f * 9).round()
	draw_line(hand, (hand + sd * length).round(), Palette.SWORD, 2.0)
	draw_line(hand - sd.orthogonal() * 3, hand + sd.orthogonal() * 3, Palette.PLAYER_DARK, 1.0)
