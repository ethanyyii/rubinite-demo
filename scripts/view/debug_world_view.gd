extends Node2D
## 除錯（F1）：在世界座標畫出受擊範圍與狀態名稱。

var arena: CombatArena


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	z_index = 50


func _process(_delta: float) -> void:
	visible = arena.debug_info
	if visible:
		queue_redraw()


func _draw() -> void:
	var sim: CombatSim = arena.sim
	var font := ThemeDB.fallback_font
	var p := sim.player
	var b := sim.boss
	# 受擊範圍（腳底的圓）
	draw_arc(p.pos, PlayerData.HURT_RADIUS, 0, TAU, 24, Color(0.3, 1, 0.4, 0.9), 1.0)
	draw_arc(b.pos, VeltharisData.HURT_RADIUS, 0, TAU, 32, Color(0.3, 1, 0.4, 0.9), 1.0)
	draw_line(p.pos, p.pos + p.facing * 14, Color(0.3, 1, 0.4), 1.0)
	draw_line(b.pos, b.pos + b.facing * 34, Color(0.3, 1, 0.4), 1.0)
	# 主角正在生效的攻擊判定（外框）
	var hb := p.attack_hitbox()
	if not hb.is_empty():
		HitboxDraw.draw_player_hitbox(self, hb, Color(0, 0, 0, 0), Color(0.4, 0.8, 1.0, 1.0))
	# 柱子碰撞
	for pillar: Dictionary in ArenaGeometry.PILLARS:
		draw_arc(pillar["pos"], pillar["radius"], 0, TAU, 16, Color(0.9, 0.9, 0.3, 0.8), 1.0)
	# 場地邊界
	var pts := DrawUtil.ellipse_points(Vector2.ZERO, ArenaGeometry.HALF_SIZE, 64)
	pts.append(pts[0])
	draw_polyline(pts, Color(0.9, 0.9, 0.3, 0.6), 1.0)
	# 狀態名稱與數值
	_label(font, p.pos + Vector2(-30, -54), "%s  架勢 %d" % [p.state_name(), roundi(p.posture)])
	_label(font, b.pos + Vector2(32, -40), "%s  韌性 %d" % [b.state_name(), roundi(b.toughness)])


func _label(font: Font, at: Vector2, text: String) -> void:
	draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, 3, Color(0, 0, 0, 0.9))
	draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color(1, 1, 0.6))
