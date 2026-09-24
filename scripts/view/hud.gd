extends Control
## 戰鬥 UI（combat-design §13）：左上玩家 HP、架勢、治療次數；下方 Boss 名稱、HP 與韌性。
## 在 _process 更新，不受頓幀影響（頓幀只停戰鬥模擬）。

const BOSS_NAME := "VELTHARIS · 墮誓之王"
const BossView := preload("res://scripts/view/boss_view.gd")

var arena: CombatArena
var _player_hp_trail := float(PlayerData.MAX_HP)
var _boss_hp_trail := float(VeltharisData.MAX_HP)


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	var sim: CombatSim = arena.sim
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	_player_hp_trail = _trail(_player_hp_trail, sim.player.hp, PlayerData.MAX_HP, real_dt)
	_boss_hp_trail = _trail(_boss_hp_trail, sim.boss.hp, VeltharisData.MAX_HP, real_dt)
	queue_redraw()


func reset_trails() -> void:
	_player_hp_trail = float(PlayerData.MAX_HP)
	_boss_hp_trail = float(VeltharisData.MAX_HP)


## 受傷後殘影條延遲往下追（實際時間）
func _trail(current: float, target: float, max_value: float, dt: float) -> float:
	if target >= current:
		return target
	return maxf(target, current - max_value * 0.6 * dt)


func _draw() -> void:
	var sim: CombatSim = arena.sim
	var font := ThemeDB.fallback_font
	# --- 玩家（左上） ---
	var x := 10.0
	var y := 10.0
	_bar(Rect2(x, y, 120, 6), float(sim.player.hp) / PlayerData.MAX_HP, _player_hp_trail / PlayerData.MAX_HP, Palette.UI_HP)
	var posture_ratio := sim.player.posture / PlayerData.MAX_POSTURE
	var posture_color := Palette.UI_POSTURE_LOW if posture_ratio < 0.3 else Palette.UI_POSTURE
	_bar(Rect2(x, y + 9, 90, 4), posture_ratio, posture_ratio, posture_color)
	for i in PlayerData.HEAL_CHARGES:
		var c := Palette.UI_HEAL if i < sim.player.heals else Color(0.25, 0.28, 0.33)
		var p := Vector2(x + 2 + i * 9, y + 17)
		draw_rect(Rect2(p + Vector2(1, 0), Vector2(4, 2)), Palette.UI_FRAME)
		draw_rect(Rect2(p + Vector2(0, 2), Vector2(6, 6)), c)
	# --- Boss（下方） ---
	var w := 360.0
	var bx := (size.x - w) * 0.5
	var by := size.y - 30.0
	draw_string(font, Vector2(bx, by - 3), BOSS_NAME, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Palette.UI_TEXT)
	_bar(Rect2(bx, by, w, 6), float(sim.boss.hp) / VeltharisData.MAX_HP, _boss_hp_trail / VeltharisData.MAX_HP, Palette.UI_BOSS_HP)
	# 第二階段的分界（HP 50%）
	var notch := bx + roundf(w * VeltharisData.PHASE2_HP_RATIO)
	draw_line(Vector2(notch, by - 2), Vector2(notch, by + 7), Palette.UI_FRAME, 1.0)
	var t := sim.boss.toughness / VeltharisData.MAX_TOUGHNESS
	var tcol := Palette.UI_TOUGHNESS
	if sim.boss.state == BossSim.State.BROKEN:
		tcol = Palette.UI_POSTURE_LOW if floori(Time.get_ticks_msec() / 120.0) % 2 == 0 else Palette.UI_TOUGHNESS
	_bar(Rect2(bx, by + 9, w, 3), t, t, tcol)
	_draw_offscreen_danger(sim)
	_draw_end_overlay(font)


## §14：死亡後「再戰」；勝利後「勝利」與再戰提示
func _draw_end_overlay(font: Font) -> void:
	match arena.end_state:
		&"death":
			var k := clampf(float(arena.end_elapsed()) / Frames.of(PlayerData.DEATH_TIME), 0.0, 1.0)
			draw_rect(Rect2(Vector2.ZERO, size), Color(0.15, 0.0, 0.0, 0.45 * k))
			if arena.retry_prompt_visible():
				_center_text(font, "再戰", 28, size.y * 0.45, Palette.UI_TEXT)
		&"victory":
			var k2 := clampf(float(arena.end_elapsed()) / Frames.of(1.0), 0.0, 1.0)
			var gold := Palette.BOSS_CROWN
			gold.a = k2
			_center_text(font, "勝利", 28, size.y * 0.3, gold)
			var sub := Palette.UI_TEXT
			sub.a = k2
			_center_text(font, "吸收了墮誓之王的執魂", 10, size.y * 0.3 + 18, sub)
			if arena.retry_prompt_visible():
				_center_text(font, "再戰（按攻擊鍵）", 12, size.y * 0.55, Palette.UI_TEXT)


func _center_text(font: Font, text: String, font_size: int, y: float, color: Color) -> void:
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var pos := Vector2((size.x - w) * 0.5, y)
	draw_string_outline(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, 4, Color(0, 0, 0, color.a * 0.9))
	draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


## Boss 在畫面外時（場地 400px 高、Boss 120px 高，玩家在最南端時 Boss 可能整個出畫面），
## 在畫面上緣標出 Boss 的方向；危險預兆的頭頂星形在畫面外時也補畫在上緣（plan §7 預兆可讀）。
func _draw_offscreen_danger(sim: CombatSim) -> void:
	var ct := get_viewport().get_canvas_transform()
	var body_y: float = (BossView.compute_pose(sim.boss)["body"] as Vector2).y  # 蹲下、舉劍時的身體偏移（與 boss_view 畫星形的位置一致）
	var head := ct * (sim.boss.pos + Vector2(0, -VeltharisData.HEIGHT + body_y))
	var star := ct * (sim.boss.pos + Vector2(0, -VeltharisData.HEIGHT - 22 + body_y))
	var danger := sim.boss.telegraph() == CombatTypes.Telegraph.DANGER
	var feet := ct * sim.boss.pos
	var boss_offscreen := feet.y < 4.0
	if not boss_offscreen and not (danger and star.y < 16.0):
		return
	var c := Vector2(clampf(head.x, 20.0, size.x - 20.0), 14.0)
	if boss_offscreen:
		var col := Palette.TELEGRAPH if sim.boss.telegraph() != CombatTypes.Telegraph.NONE else Palette.BOSS_LIGHT
		draw_colored_polygon(PackedVector2Array([c + Vector2(-7, -2), c + Vector2(7, -2), c + Vector2(0, -9)]), col)
	if danger:
		var pulse := 1.0 + 0.2 * sin(Time.get_ticks_msec() * 0.03)
		var sc := c + Vector2(0, 8)
		draw_colored_polygon(DrawUtil.star_points(sc, 9.0 * pulse, 3.8 * pulse), Palette.DANGER)


func _bar(r: Rect2, ratio: float, trail: float, color: Color) -> void:
	draw_rect(r.grow(1), Palette.UI_BG)
	var tw := roundf(r.size.x * clampf(trail, 0.0, 1.0))
	if trail > ratio:
		draw_rect(Rect2(r.position, Vector2(tw, r.size.y)), Palette.UI_HP_TRAIL)
	draw_rect(Rect2(r.position, Vector2(roundf(r.size.x * clampf(ratio, 0.0, 1.0)), r.size.y)), color)
	draw_rect(r.grow(1), Palette.UI_FRAME, false, 1.0)
