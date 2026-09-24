extends Node2D
## 地面圖層（畫在地面之上、角色之下）：
## - 判定預覽（plan §4：出招時用半透明色塊預覽攻擊範圍，F6 關閉）。畫的是 sim 裡實際的判定形狀。
##   起手期間淡淡顯示，越接近命中越明顯；判定期間最明顯。可格擋為紅、不可格擋為白。
## - 衝擊環（灰燼衝擊的實際特效，不受 F6 影響）。

const SH := CombatTypes.Shape

var arena: CombatArena


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	z_index = -10


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	var sim := arena.sim
	var pb := sim.boss.preview_hitbox()
	if not pb.is_empty():
		var hit: BossHitData = pb["hit"]
		if hit.shape == SH.RING and pb["active"]:
			_draw_ring(pb)
		if arena.attack_preview and not pb["resolved"]:
			_draw_boss_preview(pb)
	if arena.attack_preview:
		var hb := sim.player.attack_hitbox()
		if not hb.is_empty():
			HitboxDraw.draw_player_hitbox(self, hb, Color(0.4, 0.65, 1.0, 0.28), Color(0.6, 0.8, 1.0, 0.7))


func _draw_boss_preview(pb: Dictionary) -> void:
	var hit: BossHitData = pb["hit"]
	var base := Palette.PREVIEW_BLOCKABLE if hit.is_blockable() else Palette.PREVIEW_UNBLOCKABLE
	var active: bool = pb["active"]
	var k: float = pb["progress"]
	var fill := base
	fill.a = 0.32 if active else 0.05 + 0.13 * k
	var outline := base
	outline.a = 0.8 if active else 0.25 + 0.35 * k
	if hit.shape == SH.RING:
		# 起手期間畫出環會到達的最大範圍
		if not active:
			draw_arc(pb["origin"], hit.radius, 0, TAU, 64, outline, 1.0)
			DrawUtil.fill_ellipse(self, pb["origin"], Vector2(hit.radius, hit.radius), Color(1, 1, 1, 0.03 + 0.05 * k), 48)
		return
	HitboxDraw.draw_boss_hitbox(self, hit, pb["origin"], pb["dir"], fill, outline)


func _draw_ring(pb: Dictionary) -> void:
	var hit: BossHitData = pb["hit"]
	var outer: float = pb["ring_radius"]
	var inner := maxf(outer - hit.thickness, 0.0)
	draw_colored_polygon(DrawUtil.ring_points(pb["origin"], outer, inner), Color(1.0, 0.85, 0.6, 0.75))
	draw_arc(pb["origin"], outer, 0, TAU, 64, Color(1, 1, 1, 0.9), 2.0)
