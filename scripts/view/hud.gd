extends Control
## 戰鬥 UI（combat-design §13）：左上玩家 HP、架勢、治療次數；下方 Boss 名稱、HP 與韌性。
## 在 _process 更新，不受頓幀影響（頓幀只停戰鬥模擬）。
## 2026-10-06 美化（使用者）：框、徽章、回血瓶、Boss 的框是 tools/ui_art/ui.py 畫的圖（assets/sprites/ui/），
## 條的填色由這裡畫在框的洞裡；Boss 的血條分兩管（第一階段一管、打空進入第二階段時回滿再一管，只是顯示，規則不變）。

const BOSS_NAME := "VELTHARIS · 墮誓之王"
## 版面：畫面從 640×360 拉遠到 960×540（2026-09-30），UI 的位置與大小照原本的 1.5 倍排，
## 在螢幕上的大小和原本一樣（下面的數字都是原本的 1.5 倍）
## Boss 名稱與血條佔用的畫面下緣高度（血條距下緣 40、名稱字高加間隔）；鏡頭的下緣安全區要至少這麼高
const BOSS_BAR_FROM_BOTTOM := 40.0
const BOSS_AREA := 72.0
const BossView := preload("res://scripts/view/boss_view.gd")

const UI := "res://assets/sprites/ui/"
## 框的圖裡，填色那個洞的左上角（tools/ui_art/ui.py：外框 1 px＋鐵框 3 px；Boss 的框左右各有 18 px 的王冠端蓋）
const BAR_HOLE := Vector2(4, 4)
const BOSS_HOLE := Vector2(23, 15)
const BOSS_TOUGH_GAP := 3.0
## 玩家的版面（左上）
const MEDALLION_AT := Vector2(8, 7)
const HP_FRAME_AT := Vector2(46, 10)
const POSTURE_FRAME_AT := Vector2(46, 27)
const FLASKS_AT := Vector2(192, 26)
const FLASK_STEP := 12.0
const HP_SIZE := Vector2(180, 9)
const POSTURE_SIZE := Vector2(135, 5)
const BOSS_SIZE := Vector2(540, 9)
const TOUGH_SIZE := Vector2(540, 4)

# 填色：每種條三個顏色（上緣亮、本色、下緣暗）
const HP_COLS := [Color("f07a66"), Color("cf3b33"), Color("7e1c1c")]
const POSTURE_COLS := [Color("ffe08a"), Color("e3ab32"), Color("8a5f14")]
const POSTURE_LOW_COLS := [Color("ffb070"), Color("ff6a2a"), Color("962f0c")]
const BOSS_COLS := [Color("e0573a"), Color("a51f18"), Color("4e0b09")]
const TOUGH_COLS := [Color("fffaf0"), Color("e9e0cc"), Color("9b927f")]
const HOLE := Color(0.04, 0.04, 0.05)
const TRAIL := Color("f0d7a0")
const GOLD := Color("c4a04a")
const GOLD_DARK := Color("68531f")

var arena: CombatArena
var _player_hp_trail := float(PlayerData.MAX_HP)
var _boss_hp_trail := float(VeltharisData.MAX_HP)
## 第二階段那一管的「滿」＝轉場開始時 Boss 剩的 HP（處決可能把 HP 從一半以上直接打到一半以下）
var _phase2_full := -1
var _tex := {}


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for n in ["medallion", "hp_frame", "posture_frame", "flask_full", "flask_empty", "boss_frame", "boss_pip_full", "boss_pip_empty"]:
		_tex[n] = load(UI + n + ".png")


func _process(delta: float) -> void:
	var sim: CombatSim = arena.sim
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	_player_hp_trail = _trail(_player_hp_trail, sim.player.hp, PlayerData.MAX_HP, real_dt)
	_boss_hp_trail = _trail(_boss_hp_trail, sim.boss.hp, VeltharisData.MAX_HP, real_dt)
	if sim.boss.state == BossSim.State.TRANSITION and _phase2_full < 0:
		_phase2_full = sim.boss.hp
	elif sim.boss.phase == 1 and sim.boss.state != BossSim.State.TRANSITION:
		_phase2_full = -1
	queue_redraw()


func reset_trails() -> void:
	_player_hp_trail = float(PlayerData.MAX_HP)
	_boss_hp_trail = float(VeltharisData.MAX_HP)
	_phase2_full = -1


## 受傷後殘影條延遲往下追（實際時間）
func _trail(current: float, target: float, max_value: float, dt: float) -> float:
	if target >= current:
		return target
	return maxf(target, current - max_value * 0.6 * dt)


## Boss 血條顯示的比例（2026-10-06 使用者：第一階段一管，打空進入第二階段後回滿）。
## phase：Boss 第幾階段；transition_k：轉場進度 0–1（不在轉場時 -1）；hp：HP；
## phase2_full：轉場開始時剩的 HP（第二管的滿格；不知道時 -1，照 HP 的一半算）。
static func boss_bar_ratio(phase: int, transition_k: float, hp: float, phase2_full: int) -> float:
	var half := float(roundi(VeltharisData.MAX_HP * VeltharisData.PHASE2_HP_RATIO))
	if transition_k >= 0.0:
		# 轉場的 1.5 秒裡回滿（先快後慢）
		var u := clampf(transition_k, 0.0, 1.0)
		return 1.0 - (1.0 - u) * (1.0 - u)
	if phase == 1:
		return clampf((hp - half) / (VeltharisData.MAX_HP - half), 0.0, 1.0)
	var full := float(phase2_full) if phase2_full > 0 else half
	return clampf(hp / full, 0.0, 1.0)


func _transition_k(b: BossSim) -> float:
	if b.state != BossSim.State.TRANSITION:
		return -1.0
	return clampf(float(b.state_elapsed()) / Frames.of(VeltharisData.TRANSITION_TIME), 0.0, 1.0)


func _draw() -> void:
	var sim: CombatSim = arena.sim
	var font := ThemeDB.fallback_font
	# --- 玩家（左上）：徽章、HP、架勢、回血瓶 ---
	draw_texture(_tex["medallion"], MEDALLION_AT)
	draw_texture(_tex["hp_frame"], HP_FRAME_AT)
	_fill(Rect2(HP_FRAME_AT + BAR_HOLE, HP_SIZE), float(sim.player.hp) / PlayerData.MAX_HP,
		_player_hp_trail / PlayerData.MAX_HP, HP_COLS)
	draw_texture(_tex["posture_frame"], POSTURE_FRAME_AT)
	var posture_ratio := sim.player.posture / PlayerData.MAX_POSTURE
	_fill(Rect2(POSTURE_FRAME_AT + BAR_HOLE, POSTURE_SIZE), posture_ratio, posture_ratio,
		POSTURE_LOW_COLS if posture_ratio < 0.3 else POSTURE_COLS)
	for i in PlayerData.HEAL_CHARGES:
		var flask: Texture2D = _tex["flask_full"] if i < sim.player.heals else _tex["flask_empty"]
		draw_texture(flask, FLASKS_AT + Vector2(i * FLASK_STEP, 0))
	# --- Boss（下方）：名字、兩管血的標記、框、HP、韌性 ---
	var b := sim.boss
	var bx := roundf((size.x - BOSS_SIZE.x) * 0.5)
	var by := size.y - BOSS_BAR_FROM_BOTTOM
	_draw_boss_name(font, by - 18.0, b)
	draw_texture(_tex["boss_frame"], Vector2(bx, by) - BOSS_HOLE)
	var tk := _transition_k(b)
	var ratio := boss_bar_ratio(b.phase, tk, b.hp, _phase2_full)
	var trail := ratio if tk >= 0.0 else boss_bar_ratio(b.phase, tk, _boss_hp_trail, _phase2_full)
	_fill(Rect2(bx, by, BOSS_SIZE.x, BOSS_SIZE.y), ratio, maxf(trail, ratio), BOSS_COLS, tk >= 0.0, true)
	var t := b.toughness / VeltharisData.MAX_TOUGHNESS
	var tcols := TOUGH_COLS
	if b.state == BossSim.State.BROKEN and floori(Time.get_ticks_msec() / 120.0) % 2 == 0:
		tcols = POSTURE_LOW_COLS
	_fill(Rect2(bx, by + BOSS_SIZE.y + BOSS_TOUGH_GAP, TOUGH_SIZE.x, TOUGH_SIZE.y), t, t, tcols)
	_draw_offscreen_danger(sim)
	_draw_end_overlay(font)


## Boss 的名字：置中、深色描邊，兩側各一條金線（往外變細、末端一顆菱形）；名字右邊兩顆標記＝兩管血（打空一管熄一顆）
func _draw_boss_name(font: Font, baseline: float, b: BossSim) -> void:
	var fs := 14
	var tw := font.get_string_size(BOSS_NAME, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var pips := 2 * 9 + 3
	var total := tw + 8.0 + pips
	var x := roundf((size.x - total) * 0.5)
	draw_string_outline(font, Vector2(x, baseline), BOSS_NAME, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color(0, 0, 0, 0.85))
	draw_string(font, Vector2(x, baseline), BOSS_NAME, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Palette.UI_TEXT)
	var bars_left := 2 if b.phase == 1 and b.state != BossSim.State.TRANSITION else 1
	if b.state == BossSim.State.DEAD:
		bars_left = 0
	for i in 2:
		var tex: Texture2D = _tex["boss_pip_full"] if i < bars_left else _tex["boss_pip_empty"]
		draw_texture(tex, Vector2(x + tw + 8.0 + i * 12.0, baseline - 10.0))
	var mid := baseline - 5.0
	var gap := 10.0
	for side: float in [-1.0, 1.0]:
		var from := x - gap if side < 0.0 else x + total + gap
		var to := from + side * 120.0
		draw_line(Vector2(from, mid), Vector2(to, mid), GOLD, 1.0)
		draw_line(Vector2(from, mid + 1), Vector2(from + side * 70.0, mid + 1), GOLD_DARK, 1.0)
		var d := Vector2(to + side * 3.0, mid)
		draw_colored_polygon(PackedVector2Array([d + Vector2(-3, 0), d + Vector2(0, -3), d + Vector2(3, 0), d + Vector2(0, 3)]), GOLD)


## §14：死亡後「再戰」；勝利後「勝利」與再戰提示
func _draw_end_overlay(font: Font) -> void:
	match arena.end_state:
		&"death":
			var k := clampf(float(arena.end_elapsed()) / Frames.of(PlayerData.DEATH_TIME), 0.0, 1.0)
			draw_rect(Rect2(Vector2.ZERO, size), Color(0.15, 0.0, 0.0, 0.45 * k))
			if arena.retry_prompt_visible():
				_center_text(font, "再戰", 42, size.y * 0.45, Palette.UI_TEXT)
		&"victory":
			var k2 := clampf(float(arena.end_elapsed()) / Frames.of(1.0), 0.0, 1.0)
			var gold := Palette.BOSS_CROWN
			gold.a = k2
			_center_text(font, "勝利", 42, size.y * 0.3, gold)
			var sub := Palette.UI_TEXT
			sub.a = k2
			_center_text(font, "吸收了墮誓之王的執魂", 15, size.y * 0.3 + 27, sub)
			if arena.retry_prompt_visible():
				_center_text(font, "再戰（按攻擊鍵）", 18, size.y * 0.55, Palette.UI_TEXT)


func _center_text(font: Font, text: String, font_size: int, y: float, color: Color) -> void:
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	var pos := Vector2((size.x - w) * 0.5, y)
	draw_string_outline(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, 6, Color(0, 0, 0, color.a * 0.9))
	draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)


## Boss 在畫面外時（場地 600px 高、Boss 160px 高，玩家在最南端時 Boss 可能整個出畫面），
## 在畫面上緣標出 Boss 的方向；危險預兆時頭盔（十字紅光）在畫面外，就在上緣畫星形（plan §7 預兆可讀）。
## 頭頂的星形本身拿掉了（2026-10-05 使用者：有十字紅光就夠了），只剩看不到頭盔時的這個。
func _draw_offscreen_danger(sim: CombatSim) -> void:
	var ct := get_viewport().get_canvas_transform()
	var top: float = BossView.body_rect(sim.boss).position.y  # 畫出來的這一格的頂端
	var head := ct * (sim.boss.pos + Vector2(0, top))
	var danger := sim.boss.telegraph() == CombatTypes.Telegraph.DANGER
	var feet := ct * sim.boss.pos
	var boss_offscreen := feet.y < 6.0
	if not boss_offscreen and not (danger and head.y < 12.0):
		return
	var c := Vector2(clampf(head.x, 30.0, size.x - 30.0), 21.0)
	if boss_offscreen:
		var col := Palette.TELEGRAPH if sim.boss.telegraph() != CombatTypes.Telegraph.NONE else Palette.BOSS_LIGHT
		draw_colored_polygon(PackedVector2Array([c + Vector2(-10, -3), c + Vector2(10, -3), c + Vector2(0, -13)]), col)
	if danger:
		var pulse := 1.0 + 0.2 * sin(Time.get_ticks_msec() * 0.03)
		var sc := c + Vector2(0, 12)
		draw_colored_polygon(DrawUtil.star_points(sc, 13.5 * pulse, 5.7 * pulse), Palette.DANGER)


## 條的填色：洞底色、受傷殘影、本色（上緣一列亮、下半漸暗、右端一格亮邊）；refilling：回滿中，亮邊是白的；
## shimmer：一道淡淡的光每 4 秒從左往右流過（Boss 的血條，像執魂的紅火在流動）
func _fill(r: Rect2, ratio: float, trail: float, cols: Array, refilling := false, shimmer := false) -> void:
	draw_rect(r, HOLE)
	var tw := roundf(r.size.x * clampf(trail, 0.0, 1.0))
	var fw := roundf(r.size.x * clampf(ratio, 0.0, 1.0))
	if tw > fw:
		draw_rect(Rect2(r.position + Vector2(fw, 0), Vector2(tw - fw, r.size.y)), TRAIL)
	if fw <= 0.0:
		return
	var light: Color = cols[0]
	var base: Color = cols[1]
	var dark: Color = cols[2]
	draw_rect(Rect2(r.position, Vector2(fw, r.size.y)), base)
	draw_rect(Rect2(r.position, Vector2(fw, 1)), light)
	if r.size.y >= 7.0:
		draw_rect(Rect2(r.position + Vector2(0, 1), Vector2(fw, 1)), base.lerp(light, 0.4))
		draw_rect(Rect2(r.position + Vector2(0, r.size.y - 3), Vector2(fw, 1)), base.lerp(dark, 0.4))
		draw_rect(Rect2(r.position + Vector2(0, r.size.y - 2), Vector2(fw, 2)), dark)
	elif r.size.y >= 4.0:
		draw_rect(Rect2(r.position + Vector2(0, r.size.y - 1), Vector2(fw, 1)), dark)
	if shimmer:
		var k := fmod(Time.get_ticks_msec() / 4000.0, 1.0)
		var sx := roundf(-40.0 + (fw + 80.0) * k)
		for i in 5:
			var x0 := sx + i * 6.0
			var x1 := minf(x0 + 6.0, fw)
			if x1 > maxf(x0, 0.0):
				var c := light
				c.a = 0.22 * (1.0 - absf(i - 2.0) / 3.0)
				draw_rect(Rect2(r.position + Vector2(maxf(x0, 0.0), 1), Vector2(x1 - maxf(x0, 0.0), r.size.y - 3)), c)
	if fw < r.size.x:
		draw_rect(Rect2(r.position + Vector2(fw - 1, 0), Vector2(1, r.size.y)), Color.WHITE if refilling else light)
