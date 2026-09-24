class_name DrawUtil
extends RefCounted
## 佔位圖形用的繪圖工具。點座標取整，維持像素感。


static func ellipse_points(center: Vector2, radii: Vector2, segments: int = 32) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in segments:
		var a := TAU * i / segments
		pts.append((center + Vector2(cos(a) * radii.x, sin(a) * radii.y)).round())
	return pts


static func fill_ellipse(ci: CanvasItem, center: Vector2, radii: Vector2, color: Color, segments: int = 32) -> void:
	ci.draw_colored_polygon(ellipse_points(center, radii, segments), color)


static func stroke_ellipse(ci: CanvasItem, center: Vector2, radii: Vector2, color: Color, width: float = 1.0, segments: int = 48) -> void:
	var pts := ellipse_points(center, radii, segments)
	pts.append(pts[0])
	ci.draw_polyline(pts, color, width)


## 直立膠囊：腳底在 base，半徑 r，總高 h（含上下半圓）。
static func capsule_points(base: Vector2, r: float, h: float, segments: int = 12) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var bottom := base + Vector2(0, -r)
	var top := base + Vector2(0, -h + r)
	for i in segments + 1:
		var a := PI * i / segments  # 下半圓：從右 (0) 到左 (PI)
		pts.append((bottom + Vector2(cos(a), sin(a)) * r).round())
	for i in segments + 1:
		var a := PI + PI * i / segments  # 上半圓：從左到右
		pts.append((top + Vector2(cos(a), sin(a)) * r).round())
	return pts


static func fill_capsule(ci: CanvasItem, base: Vector2, r: float, h: float, color: Color) -> void:
	ci.draw_colored_polygon(capsule_points(base, r, h), color)


## 水平膠囊（倒地用）：中心 center，半長 half_len，半徑 r。
static func fill_capsule_h(ci: CanvasItem, center: Vector2, half_len: float, r: float, color: Color) -> void:
	var pts := PackedVector2Array()
	var left := center + Vector2(-half_len + r, 0)
	var right := center + Vector2(half_len - r, 0)
	for i in 13:
		var a := -PI * 0.5 + PI * i / 12.0
		pts.append((right + Vector2(cos(a), sin(a)) * r).round())
	for i in 13:
		var a := PI * 0.5 + PI * i / 12.0
		pts.append((left + Vector2(cos(a), sin(a)) * r).round())
	ci.draw_colored_polygon(pts, color)


## 地面上的扇形（俯視角，y 不壓縮：判定就是這個形狀）。
static func sector_points(origin: Vector2, dir: Vector2, radius: float, arc_deg: float, segments: int = 24) -> PackedVector2Array:
	var pts := PackedVector2Array()
	if arc_deg < 360.0:
		pts.append(origin)
	var half := deg_to_rad(arc_deg) * 0.5
	var base := dir.angle()
	for i in segments + 1:
		var a := base - half + deg_to_rad(arc_deg) * i / segments
		pts.append(origin + Vector2(cos(a), sin(a)) * radius)
	return pts


static func rect_points(origin: Vector2, dir: Vector2, length: float, width: float) -> PackedVector2Array:
	var side := dir.orthogonal() * width * 0.5
	return PackedVector2Array([origin + side, origin + dir * length + side,
		origin + dir * length - side, origin - side])


static func ring_points(origin: Vector2, outer: float, inner: float, segments: int = 48) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in segments + 1:
		var a := TAU * i / segments
		pts.append(origin + Vector2(cos(a), sin(a)) * outer)
	for i in segments + 1:
		var a := TAU - TAU * i / segments
		pts.append(origin + Vector2(cos(a), sin(a)) * inner)
	return pts


## 五角星（危險預兆的頭頂圖示）
static func star_points(center: Vector2, outer: float, inner: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in 10:
		var r := outer if i % 2 == 0 else inner
		var a := -PI * 0.5 + PI * i / 5.0
		pts.append((center + Vector2(cos(a), sin(a)) * r).round())
	return pts
