class_name BossSprites
extends RefCounted
## Boss 精靈圖的幀表與打包好的圖（tools/boss_rig/export_game.py 產生 assets/sprites/boss_game/，不要手改；
## 重新輸出任何 Boss 精靈圖之後要重跑）。原始的精靈圖（assets/sprites/boss/）太大，遊戲不載入。
##
## frames[id] = [圖, x, y, 寬, 高, ox, oy]：(ox, oy) 是這一格裁切後左上角相對腳底對齊點的位置。
## clips[名字] = {dirs: {down|right|up|left: [格 id]}, holds: [每張停幾個戰鬥幀], ...}：攻擊另有 t、
## holds_phase2、hits、advance、at（每張每個方向的握柄、劍尖，相對腳底）、delayed、flash、air、lift、game_step。
## moves：遊戲的招式 id → 播哪一張、從移動出招用哪一張的開頭、被彈開播哪一張。
## interrupt：攻擊／被彈開的圖 → {break|stagger: {pose_start: 每一張被打斷時用哪個起點（starts 的索引，-1 沒有）,
## starts: [銜接的 clip 名]}}。

const DATA_PATH := "res://assets/sprites/boss_game/boss_frames.json"
const DIRS: Array[String] = ["down", "right", "up", "left"]

static var _data: Dictionary = {}
static var _atlases: Array = []
static var _palette: Texture2D = null


static func data() -> Dictionary:
	if _data.is_empty():
		var f := FileAccess.open(DATA_PATH, FileAccess.READ)
		assert(f != null, "找不到 %s（先跑 tools/boss_rig/export_game.py）" % DATA_PATH)
		_data = JSON.parse_string(f.get_as_text())
	return _data


static func has_clip(name: String) -> bool:
	return data()["clips"].has(name)


static func clip(name: String) -> Dictionary:
	return data()["clips"][name]


static func move(id: StringName) -> Dictionary:
	return data()["moves"].get(String(id), {})


static func interrupt(sheet: String) -> Dictionary:
	return data()["interrupt"].get(sheet, {})


## 格 id 在第幾欄（某個方向）；沒畫東西的格是 -1
static func frame_at(c: Dictionary, row: String, col: int) -> int:
	var ids: Array = c["dirs"][row]
	var v = ids[clampi(col, 0, ids.size() - 1)]
	return -1 if v == null else int(v)


static func frame(id: int) -> Array:
	return data()["frames"][id]


static func atlas(i: int) -> Texture2D:
	if _atlases.is_empty():
		for p: String in data()["atlases"]:
			_atlases.append(null)
	if _atlases[i] == null:
		_atlases[i] = load(data()["atlases"][i])
	return _atlases[i]


static func palette() -> Texture2D:
	if _palette == null:
		_palette = load(data()["palette"])
	return _palette


## 一段的總長（戰鬥幀）
static func total(holds: Array) -> int:
	var n := 0
	for h in holds:
		n += int(h)
	return n


## 在 holds 裡第 e 幀是第幾張（超過就停在最後一張）
static func col_at(holds: Array, e: int) -> int:
	var acc := 0
	for i in holds.size():
		acc += int(holds[i])
		if e < acc:
			return i
	return holds.size() - 1
