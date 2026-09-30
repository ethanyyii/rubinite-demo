extends Node2D
## 短暫特效層（畫在角色之上）：刀光、命中火花、鎖定準星等。
## 特效以 _process 的 delta 播放：頓幀（只停戰鬥模擬）期間繼續；F2 慢動作時一起變慢。只讀取 sim 的狀態與事件。

const BossView := preload("res://scripts/view/boss_view.gd")
const PlayerView := preload("res://scripts/view/player_view.gd")

var arena: CombatArena
## 每個特效：{kind, pos, dir, t, life, ...}
var _fx: Array[Dictionary] = []
var _rng := RandomNumberGenerator.new()


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	z_index = 20


func clear() -> void:
	_fx.clear()


func add(kind: StringName, data: Dictionary, life: float) -> void:
	var e := data.duplicate()
	e["kind"] = kind
	e["t"] = 0.0
	e["life"] = life
	_fx.append(e)


## 命中火花：n 顆從 pos 往外飛
func sparks(pos: Vector2, color: Color, n: int, speed: float, life: float, dir := Vector2.ZERO, spread := PI) -> void:
	var parts: Array = []
	for i in n:
		var base := dir.angle() if dir != Vector2.ZERO else 0.0
		var a := base + _rng.randf_range(-spread, spread)
		parts.append({"v": Vector2(cos(a), sin(a)) * speed * _rng.randf_range(0.4, 1.0), "size": _rng.randi_range(1, 2)})
	add(&"sparks", {"pos": pos, "color": color, "parts": parts}, life)


func _process(delta: float) -> void:
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	for e in _fx:
		e["t"] += real_dt
	_fx = _fx.filter(func(e: Dictionary) -> bool: return e["t"] < e["life"])
	queue_redraw()


func _draw() -> void:
	_draw_lock_reticle()
	_draw_player_attack()
	for e in _fx:
		var k: float = e["t"] / e["life"]
		match e["kind"]:
			&"sparks":
				var p0: Vector2 = e["pos"]
				var col: Color = e["color"]
				var t: float = e["t"]
				col.a = 1.0 - k * k
				for part: Dictionary in e["parts"]:
					var v: Vector2 = part["v"]
					var p := p0 + v * t + Vector2(0, 40.0 * t * t)
					var sz: int = part["size"]
					draw_rect(Rect2(p.round(), Vector2(sz, sz)), col)
			&"flash_ring":
				var c2: Color = e["color"]
				c2.a *= 1.0 - k
				draw_arc(e["pos"], lerpf(e["r0"], e["r1"], k), 0, TAU, 32, c2, 2.0)
			&"ember_stream":
				_draw_ember_stream(e, k)


## 勝利：紅色餘燼沿弧線從 Boss 流向主角
func _draw_ember_stream(e: Dictionary, k: float) -> void:
	var from: Vector2 = e["from"]
	var to := arena.sim.player.pos + Vector2(0, -22)
	var t: float = e["t"]
	var n := 26
	for i in n:
		var ph := fmod(t * 0.9 + float(i) / n, 1.0)
		if ph > k * 1.6 + 0.05:
			continue  # 一開始只有前面幾顆，慢慢變多
		var mid := (from + to) * 0.5 + Vector2(sin(i * 1.7) * 40.0, -50.0)
		var a := from.lerp(mid, ph)
		var b := mid.lerp(to, ph)
		var p := a.lerp(b, ph)
		var c := Palette.BOSS_EMBER.lerp(Color(1, 0.3, 0.2), ph)
		c.a = 0.9 * (1.0 - absf(ph - 0.5) * 1.2) * (1.0 - maxf(k - 0.85, 0.0) * 6.0)
		draw_rect(Rect2(p.round() - Vector2(1, 1), Vector2(2 + (i % 2), 2 + (i % 2))), c)


## 刀光依玩家的狀態與幀數畫出（頓幀時跟著凍結）：輕攻擊的判定期間與收招開頭、突刺期間。
func _draw_player_attack() -> void:
	var p: PlayerSim = arena.sim.player
	if p.attack == null:
		return
	var e := p.state_elapsed()
	if p.state == PlayerSim.State.ATTACK:
		var st := p.attack.startup_frames()
		var act_end := p.attack.active_end_frame()
		var tail := 5
		# 第 4 段：轉身（起手就開始）時身邊淡淡一圈，畫到轉完為止（PlayerView.FINISHER_TURN_START–END）
		var finisher := p.combo_index == 3
		var ring_from := PlayerView.FINISHER_TURN_START if finisher else st
		var turn_end := PlayerView.FINISHER_TURN_END if finisher else act_end
		if e < mini(st, ring_from) or e >= maxi(act_end, turn_end) + tail:
			return
		var sweep := clampf(float(e - st + 1) / (act_end - st), 0.0, 1.0)
		var fade := 1.0 - clampf(float(e - act_end + 1) / (tail + 1), 0.0, 1.0)
		if p.combo_index == 2:
			# 第 3 段由下往上挑斬：沿面向的直立弧，從前下方挑到頭頂
			_draw_chop(p.pos, p.facing, PlayerData.ATTACK_RADIUS, sweep, fade, true)
		else:
			# 刀光掃過的方向和劍一樣（player_view.swing_range：第 1 段右 → 左、第 2 段左 → 右、第 4 段轉身中
			# 右 → 左），範圍夾在判定的扇形內
			var r: Vector2 = PlayerView.swing_range(p.combo_index)
			var half := deg_to_rad(PlayerData.ATTACK_ARC_DEG) * 0.5
			var from := clampf(r.x, -half, half)
			var to := clampf(r.y, -half, half)
			if finisher:
				# 回旋斬：轉身期間身邊淡淡畫一圈（只是轉身的樣子，判定仍是前方的扇形）
				var ring := Palette.SLASH
				ring.a *= 0.3 * (1.0 - clampf(float(e - turn_end + 1) / (tail + 1), 0.0, 1.0))
				DrawUtil.stroke_ellipse(self, p.pos + Vector2(0, -14), Vector2(PlayerData.ATTACK_RADIUS, PlayerData.ATTACK_RADIUS * 0.55), ring, 2.0, 32)
			if e >= st and e < act_end + tail:
				_draw_slash(p.pos, p.facing, from, to, PlayerData.ATTACK_RADIUS, 2.0, sweep, fade)
	elif p.state == PlayerSim.State.THRUST:
		var n := Frames.of(PlayerData.THRUST_TIME)
		if e >= n + 4:
			return
		var c := Palette.SLASH
		c.a *= 1.0 - clampf(float(e - n) / 4.0, 0.0, 1.0)
		var base := p.pos + Vector2(0, -16)
		draw_line((base - p.facing * 20).round(), (base + p.facing * PlayerData.THRUST_REACH).round(), c, 3.0)


## 直立弧的刀光（第 3 段挑斬，rising：從前方地面挑到頭頂上方；判定仍是 100° 扇形）
func _draw_chop(pos: Vector2, dir: Vector2, r: float, sweep: float, fade: float, rising := false) -> void:
	var shoulder := pos + Vector2(0, -20)
	var c := Palette.SLASH
	c.a *= fade
	var pts := PackedVector2Array()
	var inner := PackedVector2Array()
	var steps := 10
	for i in steps + 1:
		var u := sweep * float(i) / steps
		var th := lerpf(deg_to_rad(125.0), -0.2, u) if rising else lerpf(-0.2, deg_to_rad(125.0), u)
		var d := dir * sin(th) + Vector2(0, -cos(th))
		var o := shoulder + d * r
		o.y = minf(o.y, pos.y)
		var thick := lerpf(0.15, 0.4, float(i) / steps)
		pts.append(o)
		inner.append(shoulder + d * r * (1.0 - thick))
	var poly := pts.duplicate()
	inner.reverse()
	poly.append_array(inner)
	var fill := c
	fill.a *= 0.45
	if poly.size() >= 3 and Geometry2D.triangulate_polygon(poly).size() > 0:
		draw_colored_polygon(poly, fill)
	draw_polyline(pts, c, 2.0)


## 輕攻擊的刀光：沿攻擊扇形（半徑 40）從 from 掃到 to 的弧（相對面向的角度，正值是角色的右手側；俯視角，貼齊判定）
func _draw_slash(pos: Vector2, dir: Vector2, from: float, to_end: float, r: float, width: float, sweep: float, fade: float) -> void:
	var origin: Vector2 = pos + Vector2(0, -14)
	var to := lerpf(from, to_end, sweep)
	var c := Palette.SLASH
	c.a *= fade
	var outer := PackedVector2Array()
	var inner := PackedVector2Array()
	var steps := 12
	for i in steps + 1:
		var a := dir.angle() + lerpf(from, to, float(i) / steps)
		var d := Vector2(cos(a), sin(a))
		# 刀光前緣最亮最粗，尾端變細
		var thick := lerpf(0.25, 0.45, float(i) / steps)
		outer.append(origin + d * r)
		inner.append(origin + d * r * (1.0 - thick))
	if outer.size() < 2:
		return
	var poly := outer.duplicate()
	inner.reverse()
	poly.append_array(inner)
	var fill := c
	fill.a *= 0.45
	draw_colored_polygon(poly, fill)
	draw_polyline(outer, c.lightened(0.4), width)


## §13：鎖定中目標身上顯示準星
func _draw_lock_reticle() -> void:
	var sim: CombatSim = arena.sim
	if not sim.player.locked or arena.end_state != &"" or sim.player.state == PlayerSim.State.DEAD:
		return
	var c := sim.boss.pos + Vector2(0, -60 + BossView.leap_lift(sim.boss))
	var pulse := 1.0 + 0.15 * sin(Time.get_ticks_msec() * 0.008)
	var s := 7.0 * pulse
	var col := Color(1, 1, 1, 0.9)
	for d in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]:
		draw_line((c + d * s).round(), (c + d * (s + 4)).round(), col, 1.0)
	draw_rect(Rect2(c.round() - Vector2(1, 1), Vector2(2, 2)), col)
