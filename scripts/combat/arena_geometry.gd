class_name ArenaGeometry
extends RefCounted
## 競技場的碰撞形狀（arena.md §2）：720×400 的橢圓戰鬥區，中心在原點，邊緣有幾根柱子。
## 角色都是腳底的圓；柱子用腳底的圓當碰撞，畫面上往上延伸並參與 Y 排序。

const HALF_SIZE := Vector2(360.0, 200.0)

## 柱子：位置、碰撞半徑、畫面高度
const PILLARS := [
	{"pos": Vector2(-236.0, 104.0), "radius": 11.0, "height": 74.0},
	{"pos": Vector2(236.0, 104.0), "radius": 11.0, "height": 58.0},
	{"pos": Vector2(-262.0, -96.0), "radius": 11.0, "height": 70.0},
	{"pos": Vector2(262.0, -96.0), "radius": 11.0, "height": 80.0},
]
## 柱子的畫面寬度（佔位圖形）
const PILLAR_WIDTH := 22.0

const PLAYER_SPAWN := Vector2(0.0, 110.0)
const BOSS_SPAWN := Vector2(0.0, -40.0)


## 把半徑 r 的圓推回場地內、推出柱子之外。
static func resolve(p: Vector2, r: float) -> Vector2:
	var out := p
	for i in 4:
		out = _push_out_of_pillars(out, r)
		out = clamp_inside(out, r)
	return out


## 讓半徑 r 的圓完全留在橢圓內（往中心方向投影到內縮的橢圓上）。
static func clamp_inside(p: Vector2, r: float) -> Vector2:
	var a := HALF_SIZE.x - r
	var b := HALF_SIZE.y - r
	var k := (p.x * p.x) / (a * a) + (p.y * p.y) / (b * b)
	if k <= 1.0:
		return p
	return p / sqrt(k)


static func is_inside(p: Vector2, r: float) -> bool:
	var a := HALF_SIZE.x - r
	var b := HALF_SIZE.y - r
	return (p.x * p.x) / (a * a) + (p.y * p.y) / (b * b) <= 1.0 + 0.0001


static func _push_out_of_pillars(p: Vector2, r: float) -> Vector2:
	var out := p
	for pillar: Dictionary in PILLARS:
		var c: Vector2 = pillar["pos"]
		var min_d: float = pillar["radius"] + r
		var d := out - c
		var dist := d.length()
		if dist < min_d:
			var n := d / dist if dist > 0.001 else Vector2.DOWN
			out = c + n * min_d
	return out


## 柱子畫面佔的長方形（腳底在下緣中央）
static func pillar_rect(pillar: Dictionary) -> Rect2:
	var base: Vector2 = pillar["pos"]
	var h: float = pillar["height"]
	# 含柱基（左右各寬 3px）與上方斷口（8px）
	return Rect2(base.x - PILLAR_WIDTH * 0.5 - 3.0, base.y - h - 8.0, PILLAR_WIDTH + 6.0, h + 14.0)
