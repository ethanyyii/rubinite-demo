class_name HitGeometry
extends RefCounted
## 判定形狀與圓形受擊範圍的相交測試。所有角色的受擊範圍都是腳底的圓。


## 圓 (c, r) 是否碰到以 origin 為圓心、朝 dir、半徑 radius、總角度 arc_deg 的扇形。
static func circle_hits_sector(c: Vector2, r: float, origin: Vector2, dir: Vector2, radius: float, arc_deg: float) -> bool:
	var to := c - origin
	var dist := to.length()
	if dist > radius + r:
		return false
	if dist <= r:
		return true  # 圓心幾乎重疊：一定碰到
	if arc_deg >= 360.0:
		return true
	var half := deg_to_rad(arc_deg) * 0.5
	var ang := absf(dir.angle_to(to))
	if ang <= half:
		return true
	# 圓心在扇形外：檢查兩條邊
	var edge_a := dir.rotated(half) * radius
	var edge_b := dir.rotated(-half) * radius
	return _seg_dist(to, Vector2.ZERO, edge_a) <= r or _seg_dist(to, Vector2.ZERO, edge_b) <= r


## 從 origin 往 dir 延伸 length、寬 width 的長方形。
static func circle_hits_rect(c: Vector2, r: float, origin: Vector2, dir: Vector2, length: float, width: float) -> bool:
	var to := c - origin
	var along := to.dot(dir)
	var side := to.dot(dir.orthogonal())
	var nearest := Vector2(clampf(along, 0.0, length), clampf(side, -width * 0.5, width * 0.5))
	return Vector2(along, side).distance_to(nearest) <= r


## 從 a 到 b、半徑 cap_r 的膠囊。
static func circle_hits_capsule(c: Vector2, r: float, a: Vector2, b: Vector2, cap_r: float) -> bool:
	return _seg_dist(c, a, b) <= r + cap_r


static func circle_hits_circle(c: Vector2, r: float, origin: Vector2, radius: float) -> bool:
	return c.distance_to(origin) <= r + radius


## 以 origin 為圓心、外緣半徑 outer、厚 thickness 的環。
static func circle_hits_ring(c: Vector2, r: float, origin: Vector2, outer: float, thickness: float) -> bool:
	var d := c.distance_to(origin)
	var inner := maxf(outer - thickness, 0.0)
	return d + r >= inner and d - r <= outer


## 攻擊方向 attack_from（攻擊者位置）是否在 facing 前方 arc_deg 範圍內。
static func is_in_front(pos: Vector2, facing: Vector2, attack_from: Vector2, arc_deg: float) -> bool:
	var to := attack_from - pos
	if to.length_squared() < 0.0001:
		return true
	return absf(facing.angle_to(to)) <= deg_to_rad(arc_deg) * 0.5 + 0.0001


static func _seg_dist(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var len_sq := ab.length_squared()
	if len_sq < 0.0001:
		return p.distance_to(a)
	var t := clampf((p - a).dot(ab) / len_sq, 0.0, 1.0)
	return p.distance_to(a + ab * t)
