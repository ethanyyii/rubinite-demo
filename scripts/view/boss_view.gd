extends Node2D
## Boss 的佔位圖形（plan §4）：紅色大膠囊（腳底圓半徑 26、高 120）、灰色長方形大劍。
## 預兆（plan §4、boss §7）：一般起手時劍變亮紅；延遲停住時劍閃爍；危險預兆為全身閃白＋頭頂白色星形。
## 只讀取 BossSim 的狀態，不改動它。

const R := VeltharisData.HURT_RADIUS
const H := VeltharisData.HEIGHT
const BS := BossSim.State
const TG := CombatTypes.Telegraph
const BLADE := 70.0

var arena: CombatArena
var _flash_white := 0.0


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena


func _process(delta: float) -> void:
	var b: BossSim = arena.sim.boss
	position = b.pos.round()
	# 死亡：跪地後化為灰燼消散（boss §8.2，程式做）
	if b.state == BS.DEAD:
		modulate.a = 1.0 - clampf(float(b.state_elapsed()) / Frames.of(1.6), 0.0, 1.0)
	else:
		modulate.a = 1.0
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	_flash_white = maxf(_flash_white - real_dt, 0.0)
	queue_redraw()


func flash_hit() -> void:
	_flash_white = FeedbackData.BOSS_FLASH_TIME


func _draw() -> void:
	var b: BossSim = arena.sim.boss
	var side := b.draw_side
	var tg := b.telegraph()
	var pose := compute_pose(b)
	var body_off: Vector2 = pose["body"]
	var lift := _leap_lift(b)
	if b.move != null and b.move.airborne_start >= 0.0 and b.state == BS.ATTACK and b.state_elapsed() < b.hit_start_frame(0):
		_draw_landing_shadow(b)
	DrawUtil.fill_ellipse(self, Vector2(0, 2), Vector2(R + 8, 10) * (1.0 - 0.5 * clampf(-lift / 70.0, 0.0, 1.0)), Palette.SHADOW, 24)
	if b.state == BS.EXECUTED:
		_draw_fallen(side)
		return
	if lift < 0.0:
		draw_set_transform(Vector2(0, lift))
	var sword_behind: bool = pose["behind"]
	if sword_behind:
		_draw_sword(b, pose, tg)
	_draw_body(b, side, body_off, tg)
	if not sword_behind:
		_draw_sword(b, pose, tg)
	if tg == TG.DANGER:
		_draw_danger_star(body_off)
	if b.phase == 2 or b.state == BS.TRANSITION:
		_draw_flames(b, pose)
	draw_set_transform(Vector2.ZERO)


## 墜王之躍的騰空高度（負值往上）。準星也用這個跟著升高
static func leap_lift(b: BossSim) -> float:
	return _leap_lift(b)


static func _leap_lift(b: BossSim) -> float:
	if not b.is_airborne():
		return 0.0
	var air_from := Frames.of(b.move.airborne_start)
	var land := b.hit_start_frame(0)
	var t := float(b.state_elapsed() - air_from) / float(land - air_from)
	return -sin(PI * t) * 70.0


## 落點陰影：追蹤玩家，越接近落地越小；縮到最小的瞬間就是落地時機（boss §5.2）
func _draw_landing_shadow(b: BossSim) -> void:
	var local := b.landing_target - b.pos
	var land := b.hit_start_frame(0)
	var k := clampf(float(b.state_elapsed()) / float(land), 0.0, 1.0)
	var r := lerpf(64.0, 30.0, k)
	DrawUtil.fill_ellipse(self, local, Vector2(r, r * 0.45), Color(0, 0, 0, 0.25 + 0.3 * k), 28)
	DrawUtil.stroke_ellipse(self, local, Vector2(r, r * 0.45), Color(0.8, 0.2, 0.1, 0.5 + 0.4 * k), 1.0, 28)


## 第二階段：大劍燃起更猛烈的火焰（boss §5）；轉場時全身冒火
func _draw_flames(b: BossSim, pose: Dictionary) -> void:
	var t := Time.get_ticks_msec() * 0.001
	var hand: Vector2 = pose["hand"] + Vector2((pose["body"] as Vector2).x, 0)
	var d: Vector2 = pose["dir"]
	var length: float = pose["len"]
	for i in 7:
		var k := float(i) / 6.0
		var base := hand + d * (12.0 + k * (length - 12.0))
		var flick := sin(t * 18.0 + i * 1.7) * 2.0
		var up := Vector2(0, -6.0 - 4.0 * absf(sin(t * 11.0 + i)))
		var c := Palette.BOSS_EMBER.lerp(Color(1, 0.9, 0.4), 0.5 + 0.5 * sin(t * 9.0 + i))
		c.a = 0.85
		draw_line(base.round(), (base + up + Vector2(flick, 0)).round(), c, 2.0)
	if b.state == BS.TRANSITION:
		for i in 10:
			var a := t * 4.0 + TAU * i / 10.0
			var p := Vector2(cos(a) * 30.0, -60.0 + sin(a * 1.3) * 45.0)
			var c2 := Palette.BOSS_EMBER
			c2.a = 0.7
			draw_rect(Rect2(p.round(), Vector2(2, 3)), c2)


func _body_color(base: Color, tg: int) -> Color:
	if _flash_white > 0.0:
		return base.lerp(Color.WHITE, 0.8)
	var b: BossSim = arena.sim.boss
	if b.state == BS.BROKEN or b.state == BS.EXECUTED:
		# 失衡：身上的紅火暗下來（§11.4）
		return base.darkened(0.45)
	if tg == TG.DANGER:
		# 危險預兆：全身閃白（快速脈動）
		var k := 0.8 + 0.15 * sin(Time.get_ticks_msec() * 0.03)
		return base.lerp(Palette.DANGER, k)
	return base


func _draw_body(b: BossSim, side: float, off: Vector2, tg: int) -> void:
	var h := H + off.y  # off.y < 0 時變矮（蹲下）
	DrawUtil.fill_capsule(self, Vector2(off.x, 1), R + 1, h + 2, _body_color(Palette.BOSS_DARK, tg))
	DrawUtil.fill_capsule(self, Vector2(off.x, 0), R, h, _body_color(Palette.BOSS, tg))
	var top := -h
	# 披風下襬與胸甲
	draw_rect(Rect2(off.x - R + 4, top + 50, 2 * R - 8, 6), _body_color(Palette.BOSS_DARK, tg))
	draw_rect(Rect2(off.x - 12 + side * 4, top + 28, 24, 18), _body_color(Palette.BOSS_LIGHT, tg))
	# 執魂的紅火裂紋
	var ember := _body_color(Palette.BOSS_EMBER, tg)
	var o := Vector2(off.x, top + 120)
	draw_polyline(PackedVector2Array([o + Vector2(-6, -60), o + Vector2(-2, -48), o + Vector2(-8, -36), o + Vector2(-4, -22)]), ember, 1.0)
	draw_polyline(PackedVector2Array([o + Vector2(10, -58), o + Vector2(6, -44), o + Vector2(12, -30)]), ember, 1.0)
	# 頭部與發光的眼（朝面向偏移）
	var eye := Vector2(off.x + side * 6 + roundf(b.facing.x * 2), top + 16)
	if b.facing.y > -0.5:
		draw_rect(Rect2(eye + Vector2(-5, 0), Vector2(4, 2)), ember)
		draw_rect(Rect2(eye + Vector2(2, 0), Vector2(4, 2)), ember)
	# 王冠
	for x: float in [-10.0, -3.0, 4.0]:
		var cx := off.x + x
		draw_colored_polygon(PackedVector2Array([Vector2(cx, top + 4), Vector2(cx + 6, top + 4), Vector2(cx + 3, top - 4)]), Palette.BOSS_CROWN)


## 被處決：倒在地上（跪地片段的延伸，demo 簡化為橫躺）
func _draw_fallen(side: float) -> void:
	var c := Vector2(0, -20)
	DrawUtil.fill_capsule_h(self, c + Vector2(0, 1), 58, 25, _body_color(Palette.BOSS_DARK, CombatTypes.Telegraph.NONE))
	DrawUtil.fill_capsule_h(self, c, 56, 24, _body_color(Palette.BOSS, CombatTypes.Telegraph.NONE))
	for x: float in [-4.0, 3.0, 10.0]:
		var cx := -side * 50.0 + x
		draw_colored_polygon(PackedVector2Array([Vector2(cx, -30), Vector2(cx + 5, -30), Vector2(cx + 2, -38)]), Palette.BOSS_CROWN)
	_draw_blade(Vector2(side * 30, -8), Vector2(side, 0.15).normalized(), 70.0, Palette.GREATSWORD_DARK, false)
	var ember := Palette.BOSS_EMBER.darkened(0.5)
	draw_polyline(PackedVector2Array([c + Vector2(-20, -4), c + Vector2(-5, 2), c + Vector2(10, -3)]), ember, 1.0)


## 危險預兆：頭頂的白色星形圖示（色盲也能辨識的形狀）
func _draw_danger_star(off: Vector2) -> void:
	var c := Vector2(off.x, -H - 22 + off.y)
	var pulse := 1.0 + 0.2 * sin(Time.get_ticks_msec() * 0.03)
	DrawUtil.fill_ellipse(self, c, Vector2(15, 15) * pulse, Color(1, 1, 1, 0.25), 20)
	draw_colored_polygon(DrawUtil.star_points(c, 11.0 * pulse, 4.5 * pulse), Palette.DANGER)
	draw_polyline(_closed(DrawUtil.star_points(c, 12.0 * pulse, 5.0 * pulse)), Color(0.2, 0.2, 0.25), 1.0)


func _closed(pts: PackedVector2Array) -> PackedVector2Array:
	var out := pts.duplicate()
	out.append(pts[0])
	return out


## 依狀態與幀數算出姿勢：劍的方向、長度、握劍位置、身體偏移（靜態函式，測試直接呼叫）。
static func compute_pose(b: BossSim) -> Dictionary:
	var f := b.facing
	var side := b.draw_side
	var rest := Vector2(side * 0.35, 1.0).normalized()
	var pose := {"dir": rest, "len": BLADE, "hand": Vector2(side * 22, -58), "body": Vector2.ZERO, "behind": f.y < -0.35}
	match b.state:
		BS.ATTACK:
			_attack_pose(b, pose, side)
		BS.STAGGER:
			# 短僵直：往後一縮
			var k2 := 1.0 - clampf(float(b.state_elapsed()) / Frames.of(VeltharisData.SHORT_STAGGER_TIME), 0.0, 1.0)
			pose["body"] = Vector2(-side * 5.0 * k2, -4.0 * k2)
			pose["dir"] = rest.rotated(-side * 0.4 * k2)
		BS.TRANSITION, BS.DEAD:
			# 轉場：單膝跪地後起身（前半跪、後半站起）；死亡：跪地
			var k4 := clampf(float(b.state_elapsed()) / Frames.of(VeltharisData.TRANSITION_TIME), 0.0, 1.0)
			var kneel := 1.0 if b.state == BS.DEAD else clampf(2.0 - k4 * 2.0, 0.0, 1.0)
			pose["body"] = Vector2(side * 2.0 * kneel, -34.0 * kneel)
			pose["dir"] = Vector2(side * 0.2, 1.0).normalized().lerp(Vector2(side * 0.3, -1.0).normalized(), 1.0 - kneel).normalized()
			pose["hand"] = Vector2(side * 24, lerpf(-58.0, -30.0, kneel))
			pose["len"] = lerpf(BLADE, 34.0, kneel)
		BS.BROKEN:
			# 失衡：跪地，劍插在身旁
			pose["body"] = Vector2(side * 2.0, -34.0)
			pose["dir"] = Vector2(side * 0.2, 1.0).normalized()
			pose["hand"] = Vector2(side * 24, -30)
			pose["len"] = 34.0
		BS.RISING:
			# 起身：從跪地慢慢站直
			var k3 := clampf(float(b.state_elapsed()) / Frames.of(VeltharisData.RISE_TIME), 0.0, 1.0)
			pose["body"] = Vector2(side * 2.0 * (1.0 - k3), -34.0 * (1.0 - k3))
			pose["hand"] = Vector2(side * 22, lerpf(-30.0, -58.0, k3))
			pose["len"] = lerpf(34.0, BLADE, k3)
		BS.BOUNCED:
			# 被彈開：頓幀期間（戰鬥幀不前進）劍停在指向玩家的碰撞位置（劍與劍碰撞），之後身體後仰、劍被震到上方
			var k := clampf(float(b.state_elapsed()) / 10.0, 0.0, 1.0)
			var clash := b.sim.player.pos - b.pos + Vector2(0, 30)
			var clash_dir := clash.normalized() if clash.length_squared() > 0.01 else f
			pose["dir"] = clash_dir.lerp(Vector2(-side * 0.4, -1.0).normalized(), k).normalized()
			pose["body"] = Vector2(-side * 4.0 * k, -6.0 * k)
			pose["behind"] = k > 0.5
	return pose


static func _attack_pose(b: BossSim, pose: Dictionary, side: float) -> void:
	var m := b.move
	if m == null:
		return
	var f := b.facing
	var e := b.state_elapsed()
	var i := b.current_hit_index()
	var in_recovery := i < 0
	if in_recovery:
		i = m.hits.size() - 1
	var hit: BossHitData = m.hits[i]
	var start := b.hit_start_frame(i)
	var windup := b.windup_start(i)
	var active_n := Frames.of(hit.active)
	var p := clampf(float(e - windup) / maxf(start - windup, 1), 0.0, 1.0)  # 起手進度
	var q := clampf(float(e - start + 1) / active_n, 0.0, 1.0)  # 判定進度
	var rec := 0.0
	if in_recovery:
		var rec_start := start + active_n
		rec = clampf(float(e - rec_start) / maxf(m.total_frames() - rec_start, 1), 0.0, 1.0)
	var rest: Vector2 = pose["dir"]
	var up := Vector2(side * 0.15, -1.0).normalized()
	var phase_active := e >= start and not in_recovery
	match hit.anim:
		&"C1", &"C2":
			var s := 1.0 if hit.anim == &"C1" else -1.0
			var end := f.rotated(1.3 * s)
			if in_recovery:
				pose["dir"] = end.lerp(rest, _ease_back(rec)).normalized()
			elif phase_active:
				pose["dir"] = f.rotated(lerpf(-1.3, 1.3, q) * s)
				pose["len"] = BLADE + 18.0
			elif m.hits.size() == 1:
				# 單發大橫掃：劍壓低、橫拉到身體外側（大動作，一看就知道只有一擊）
				pose["dir"] = rest.lerp(Vector2(side * 1.0, 0.35).normalized(), p).normalized()
				pose["hand"] = Vector2(side * 28, -44)
				pose["len"] = BLADE + 10.0
				pose["body"] = Vector2(-side * 3.0 * p, 0)
				pose["behind"] = false
			else:
				# 連段的起手：劍直立扛在肩上（反手 C2 扛在另一側）
				pose["dir"] = rest.lerp(Vector2(side * s * 0.4, -1.0).normalized(), p).normalized()
				pose["hand"] = Vector2(side * s * 20, -70)
				pose["behind"] = false
				pose["front"] = true
		&"C3":
			if hit.shape == CombatTypes.Shape.RING:
				# 插地：舉到頭頂後把劍插進腳前的地面
				if phase_active or in_recovery:
					pose["dir"] = Vector2(side * 0.1, 1.0).normalized()
					pose["hand"] = Vector2(side * 8, -40)
					pose["len"] = 40.0
					pose["body"] = Vector2(0, -8)
				else:
					pose["dir"] = rest.lerp(up, clampf(p * 1.4, 0.0, 1.0)).normalized()
			elif in_recovery:
				# 下劈後劍卡在地上（全場最大的反擊窗口）
				pose["dir"] = f
				pose["len"] = 92.0
				pose["hand"] = Vector2(side * 10, -34) + f * 10
				pose["body"] = Vector2(0, -10)
			elif phase_active:
				pose["dir"] = up.lerp(f, q).normalized()
				pose["len"] = lerpf(BLADE, 92.0, q)
			else:
				# 舉劍：延遲版在 hold_start 舉到最高點，停住期間姿勢完全靜止（★8）；
				# 普通版在命中前 0.2 秒舉到最高點。劍畫在身體前面，舉高的劍與延遲預兆才看得清楚
				var raise_end := windup + Frames.of(hit.hold_start) if hit.is_delayed() else start - Frames.of(0.2)
				var r := clampf(float(e - windup) / maxf(raise_end - windup, 1), 0.0, 1.0)
				pose["dir"] = rest.lerp(up, r).normalized()
				pose["hand"] = Vector2(side * 18, -64)
				pose["behind"] = false
				pose["front"] = true
		&"C4":
			if in_recovery:
				pose["dir"] = f.lerp(rest, _ease_back(rec)).normalized()
			elif phase_active:
				pose["dir"] = f
				pose["len"] = 100.0
				pose["hand"] = Vector2(0, -50) + f * 12
			else:
				# 突刺預備：劍收到腰側、劍尖朝後，身體前傾（boss §4.4）
				pose["dir"] = Vector2(-side, 0.15).lerp(-f, 0.3).normalized()
				pose["hand"] = Vector2(side * 26, -44)
				pose["len"] = 64.0
				pose["body"] = Vector2(side * 3.0 * p, 0)
		&"C5":
			var low := f.rotated(2.6 * side)
			if in_recovery:
				pose["dir"] = up.lerp(rest, _ease_back(rec)).normalized()
			elif phase_active:
				pose["dir"] = low.lerp(up, q).normalized()
				pose["len"] = BLADE + 14.0
			else:
				pose["dir"] = rest.lerp(low, p).normalized()
		&"C6":
			if phase_active:
				var d := f.rotated(TAU * q * side)
				pose["dir"] = d
				pose["len"] = 96.0
				pose["behind"] = d.y < 0.0
			elif in_recovery:
				pose["dir"] = f.lerp(rest, _ease_back(rec)).normalized()
			else:
				pose["dir"] = (-f).lerp(rest, 0.3).normalized()
		&"C7":
			# 墜王之躍：下蹲（身體變矮）→ 騰空舉劍 → 落地重擊劍插在前方
			var air_from := Frames.of(m.airborne_start)
			if phase_active or in_recovery:
				pose["dir"] = f
				pose["len"] = 90.0
				pose["body"] = Vector2(0, -8)
			elif e < air_from:
				pose["body"] = Vector2(0, -14.0 * clampf(float(e) / air_from, 0.0, 1.0))
				pose["dir"] = rest
			else:
				pose["dir"] = up
	var sword_dir: Vector2 = pose["dir"]
	if not pose.has("front"):
		pose["behind"] = pose["behind"] or sword_dir.y < -0.6


static func _ease_back(k: float) -> float:
	return clampf(k * 1.5 - 0.5, 0.0, 1.0)


func _draw_sword(b: BossSim, pose: Dictionary, tg: int) -> void:
	var color := Palette.GREATSWORD
	var glow := false
	match tg:
		TG.NORMAL:
			color = Palette.TELEGRAPH  # 起手：劍變亮紅
			glow = true
		TG.DELAYED:
			# 延遲停住：劍身閃爍（紅白交替，每 4 幀）
			var on := (b.state_elapsed() >> 2) % 2 == 0
			color = Palette.TELEGRAPH if on else Color(1, 0.9, 0.85)
			glow = true
	var off: Vector2 = pose["body"]
	var hand: Vector2 = pose["hand"] + Vector2(off.x, 0)
	_draw_blade(hand, pose["dir"], pose["len"], color, glow)
	if tg == TG.DELAYED:
		# 延遲專屬預兆：劍身符文閃爍（沿劍身的白色光點輪流亮起）
		var d: Vector2 = pose["dir"]
		var n := 5
		var lit := (b.state_elapsed() >> 1) % n
		for k in n:
			var pt := (hand + d * (14.0 + k * 11.0)).round()
			var c := Color(1, 1, 1) if k == lit else Color(1, 0.85, 0.8, 0.8)
			draw_rect(Rect2(pt - Vector2(1, 1), Vector2(3, 3)), c)


func _draw_blade(hand: Vector2, dir: Vector2, length: float, color: Color, glow: bool) -> void:
	var side := dir.orthogonal() * 4.0
	var tip := hand + dir * length
	if glow:
		var g := color
		g.a = 0.35
		draw_line(hand.round(), tip.round(), g, 12.0)
	draw_colored_polygon(PackedVector2Array([(hand + side).round(), (tip + side * 0.6).round(),
		(tip + dir * 6).round(), (tip - side * 0.6).round(), (hand - side).round()]), color)
	draw_line(hand.round(), (hand + dir * (length - 4)).round(), Palette.GREATSWORD_DARK, 1.0)
	# 護手與劍柄
	draw_line((hand + dir.orthogonal() * 9).round(), (hand - dir.orthogonal() * 9).round(), Palette.GREATSWORD_DARK, 3.0)
	draw_line(hand.round(), (hand - dir * 12).round(), Palette.BOSS_DARK, 3.0)
