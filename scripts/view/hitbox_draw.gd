class_name HitboxDraw
extends RefCounted
## 把 sim 的判定形狀畫出來（判定預覽與 F1 除錯共用）。fill 的 alpha 為 0 時只畫外框。


static func draw_player_hitbox(ci: CanvasItem, hb: Dictionary, fill: Color, outline: Color) -> void:
	var pts := PackedVector2Array()
	match hb["shape"]:
		&"sector":
			pts = DrawUtil.sector_points(hb["origin"], hb["dir"], hb["radius"], hb["arc"])
		&"capsule":
			var a: Vector2 = hb["a"]
			var b: Vector2 = hb["b"]
			var half: float = hb["width"] * 0.5
			var d := (b - a).normalized()
			pts = _capsule_points(a, b, d, half)
	_fill_and_stroke(ci, pts, fill, outline)


static func _capsule_points(a: Vector2, b: Vector2, d: Vector2, half: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var base := d.angle()
	for i in 9:
		var ang := base - PI * 0.5 + PI * i / 8.0
		pts.append(b + Vector2(cos(ang), sin(ang)) * half)
	for i in 9:
		var ang := base + PI * 0.5 + PI * i / 8.0
		pts.append(a + Vector2(cos(ang), sin(ang)) * half)
	return pts


static func _fill_and_stroke(ci: CanvasItem, pts: PackedVector2Array, fill: Color, outline: Color) -> void:
	if pts.size() < 3:
		return
	if fill.a > 0.0:
		ci.draw_colored_polygon(pts, fill)
	var closed := pts.duplicate()
	closed.append(pts[0])
	ci.draw_polyline(closed, outline, 1.0)


## Boss 一擊的判定形狀（衝擊環除外，環由地面特效畫）
static func draw_boss_hitbox(ci: CanvasItem, hit: BossHitData, origin: Vector2, dir: Vector2, fill: Color, outline: Color) -> void:
	var pts := PackedVector2Array()
	match hit.shape:
		CombatTypes.Shape.SECTOR:
			pts = DrawUtil.sector_points(origin, dir, hit.radius, hit.angle_deg, 32)
		CombatTypes.Shape.CIRCLE:
			pts = DrawUtil.sector_points(origin, dir, hit.radius, 360.0, 40)
		CombatTypes.Shape.RECT:
			pts = DrawUtil.rect_points(origin, dir, hit.length, hit.width)
		CombatTypes.Shape.THRUST:
			# 預覽整段突進路徑：劍長 + 突進距離
			pts = _capsule_points(origin, origin + dir * (hit.length + hit.lunge_distance), dir, hit.width * 0.5)
		CombatTypes.Shape.RING:
			return
	_fill_and_stroke(ci, pts, fill, outline)
