extends Node2D
## 主角的畫面：精靈圖（assets/sprites/player/，選哪一格在 PlayerAnim）、腳底陰影，以及程式畫的特效
## （閃身殘影、蓄力與治療的光、架勢崩潰的暈眩星點、受擊與蓄滿的閃色）。刀光在 fx_view。
## 只讀取 PlayerSim 的狀態，不改動它。節點放在腳底（Y 排序依腳底）。

const S := PlayerSim.State
const BossView := preload("res://scripts/view/boss_view.gd")
## 受擊、踉蹌、蓄滿時把精靈圖往某個顏色混（tint.a ＝ 混多少）
const FLASH_SHADER := "shader_type canvas_item;
uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 0.0);
void fragment() {
	COLOR.rgb = mix(COLOR.rgb, tint.rgb, tint.a);
}
"
## 閃身殘影的顏色（程式畫的特效，§7）
const AFTERIMAGE_TINT := Color(0.7, 0.85, 1.0)
## 主角在 Boss 後面被擋住時，畫在最上層的剪影（單色、半透明；看得到姿勢和位置）
const SILHOUETTE_SHADER := "shader_type canvas_item;
uniform vec4 fill : source_color = vec4(0.5, 0.66, 0.96, 0.5);
void fragment() {
	COLOR = vec4(fill.rgb, COLOR.a * fill.a);
}
"
## 剪影的高度：比其他角色都高、比特效層（fx_view，z 20）低
const SILHOUETTE_Z := 15
## 主角的畫面範圍（腳底往上多高、左右多寬），用來判斷有沒有被 Boss 擋住
const BODY_HALF_WIDTH := 12.0
const BODY_HEIGHT := 50.0

var arena: CombatArena
var anim := PlayerAnim.new()
## 精靈圖本體、被 Boss 擋住時的剪影、畫在精靈圖上面的特效（暈眩星點、裂紋）
var body: Sprite2D
var silhouette: Sprite2D
var overlay: Node2D
var _flash_red := 0.0
var _flash_white := 0.0
## 擊敗 Boss 後鎧甲多一道紅色裂紋（combat-design §15、player-knight §1）；重試後保留
var ember_crack := false
var _textures := {}


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	body = Sprite2D.new()
	body.name = "Body"
	body.centered = false
	body.region_enabled = true
	var mat := ShaderMaterial.new()
	var shader := Shader.new()
	shader.code = FLASH_SHADER
	mat.shader = shader
	body.material = mat
	add_child(body)
	silhouette = Sprite2D.new()
	silhouette.name = "Silhouette"
	silhouette.centered = false
	silhouette.region_enabled = true
	silhouette.z_index = SILHOUETTE_Z
	var smat := ShaderMaterial.new()
	var sshader := Shader.new()
	sshader.code = SILHOUETTE_SHADER
	smat.shader = sshader
	silhouette.material = smat
	silhouette.visible = false
	add_child(silhouette)
	overlay = Node2D.new()
	overlay.name = "Overlay"
	overlay.draw.connect(_draw_overlay)
	add_child(overlay)


func texture_of(key: String) -> Texture2D:
	if not _textures.has(key):
		_textures[key] = load(KnightSheets.SHEETS[key]["path"])
	return _textures[key]


## 精靈圖上某一格的範圍
static func region_of(key: String, r: int, c: int) -> Rect2:
	var cell: Vector2i = KnightSheets.SHEETS[key]["cell"]
	return Rect2(Vector2(c * cell.x, r * cell.y), Vector2(cell))


## 戰鬥模擬推進之後由 CombatArena 呼叫（每個物理幀），讓選格不漏掉任何一個戰鬥幀
func sim_stepped() -> void:
	anim.update(arena.sim.player)


func _process(delta: float) -> void:
	var p: PlayerSim = arena.sim.player
	anim.update(p)
	position = p.pos.round()
	var real_dt := delta  # delta 已受 time_scale 影響；頓幀只停戰鬥模擬，不影響這裡
	_flash_red = maxf(_flash_red - real_dt, 0.0)
	_flash_white = maxf(_flash_white - real_dt, 0.0)
	_apply_body(p)
	queue_redraw()
	overlay.queue_redraw()


func flash_hurt() -> void:
	_flash_red = FeedbackData.PLAYER_FLASH_TIME


func flash_charge() -> void:
	_flash_white = 0.12


## 精靈圖畫在腳底加上選格給的偏移（攻擊前進時換圖才跟上、擊飛的高度），取整後相對節點的位置
func _feet_offset(p: PlayerSim, extra := Vector2.ZERO) -> Vector2:
	return (p.pos + anim.offset + extra).round() - p.pos.round()


func _apply_body(p: PlayerSim) -> void:
	var key := anim.sheet
	body.texture = texture_of(key)
	body.region_rect = region_of(key, anim.row, anim.col)
	body.offset = -Vector2(KnightSheets.SHEETS[key]["anchor"])
	body.position = _feet_offset(p)
	var alpha := 1.0
	if p.state == S.DEAD:
		alpha = 1.0 - 0.6 * clampf(float(p.state_elapsed()) / Frames.of(PlayerData.DEATH_TIME), 0.0, 1.0)
	body.modulate = Color(1, 1, 1, alpha)
	(body.material as ShaderMaterial).set_shader_parameter(&"tint", _tint(p))
	var b: BossSim = arena.sim.boss
	silhouette.visible = p.state != S.DEAD and b.state != BossSim.State.DEAD \
		and hidden_by_boss(p.pos + anim.offset, b.pos, BossView.body_rect(b))
	if silhouette.visible:
		silhouette.texture = body.texture
		silhouette.region_rect = body.region_rect
		silhouette.offset = body.offset
		silhouette.position = body.position


## 主角（腳底 feet）在 Boss（腳底 boss_feet，身體範圍 boss_rect 相對腳底）後方、畫面上被擋住一半以上：
## Y 排序會被 Boss 擋住（progress.md 已知問題），要畫剪影。只擦到邊時看得到主角，不必畫
static func hidden_by_boss(feet: Vector2, boss_feet: Vector2, boss_rect: Rect2) -> bool:
	if feet.y >= boss_feet.y:
		return false
	var me := Rect2(feet + Vector2(-BODY_HALF_WIDTH, -BODY_HEIGHT), Vector2(2 * BODY_HALF_WIDTH, BODY_HEIGHT))
	var boss := Rect2(boss_feet + boss_rect.position, boss_rect.size)
	return me.intersection(boss).get_area() >= me.get_area() * 0.5


## 閃色：受擊變紅，踉蹌整段帶紅色（越接近恢復越淡），蓄滿一瞬間變白
func _tint(p: PlayerSim) -> Color:
	if _flash_red > 0.0:
		return Color(1, 0.2, 0.2, 0.7)
	if p.state == S.STAGGER:
		var k := 1.0 - clampf(float(p.state_elapsed()) / Frames.of(PlayerData.STAGGER_TIME), 0.0, 1.0)
		return Color(1, 0.25, 0.25, 0.55 * k)
	if _flash_white > 0.0:
		return Color(1, 1, 1, 0.8)
	return Color(1, 1, 1, 0)


## 畫在精靈圖下面：陰影、閃身殘影、蓄力與治療的光
func _draw() -> void:
	var p: PlayerSim = arena.sim.player
	var shadow_r := Vector2(20, 4) if anim.lying else Vector2(PlayerData.HURT_RADIUS + 3, 4)
	DrawUtil.fill_ellipse(self, Vector2(0, 1), shadow_r, Palette.SHADOW, 16)
	if p.state == S.DODGE and p.state_elapsed() < Frames.of(PlayerData.DODGE_TIME):
		_draw_afterimages(p)
	if p.state == S.CHARGE:
		_draw_charge_glow(p)
	if p.state == S.HEAL:
		_draw_heal_glow(p)


## 閃身的三道殘影（§7：由程式產生）：目前這一格往閃身的反方向拉開、半透明
func _draw_afterimages(p: PlayerSim) -> void:
	var tex := texture_of(anim.sheet)
	var src := region_of(anim.sheet, anim.row, anim.col)
	var anchor := Vector2(KnightSheets.SHEETS[anim.sheet]["anchor"])
	for i in [3, 2, 1]:
		var at := _feet_offset(p, -p.dodge_dir * 9.0 * i) - anchor
		var c := AFTERIMAGE_TINT
		c.a = 0.15 + 0.1 * (3 - i)
		draw_texture_rect_region(tex, Rect2(at, src.size), src, c)


func _draw_heal_glow(p: PlayerSim) -> void:
	var t := float(p.state_elapsed()) / Frames.FPS
	var c := Color(0.55, 1.0, 0.8, 0.5)
	DrawUtil.stroke_ellipse(self, Vector2(0, -1), Vector2(12, 5) * (1.0 + 0.1 * sin(t * 12.0)), c, 1.0, 24)
	for i in 5:
		var k := fmod(t * 1.3 + i * 0.2, 1.0)
		var px := Vector2(sin(i * 2.1) * 8.0, -4 - k * 40.0).round()
		var cc := c
		cc.a = 0.8 * (1.0 - k)
		draw_rect(Rect2(px, Vector2(2, 2)), cc)


func _draw_charge_glow(p: PlayerSim) -> void:
	var k := clampf(float(p.state_elapsed()) / Frames.of(PlayerData.CHARGE_TIME), 0.0, 1.0)
	var pulse := 0.5 + 0.5 * sin(Time.get_ticks_msec() * (0.012 if p.charge_full else 0.006))
	var c := Palette.PLAYER_LIGHT if not p.charge_full else Color(0.9, 0.95, 1.0)
	c.a = 0.25 + 0.45 * k * pulse
	DrawUtil.stroke_ellipse(self, Vector2(0, -20), Vector2(13, 25) * (0.9 + 0.1 * k), c, 1.0, 32)


## 畫在精靈圖上面：架勢崩潰的暈眩星點與驚嘆號、勝利後的裂紋、F1 除錯時完美窗口的提示
func _draw_overlay() -> void:
	var p: PlayerSim = arena.sim.player
	if p.state == S.POSTURE_BREAK:
		_draw_dizzy(p)
	if ember_crack and not anim.lying and p.state != S.DEAD:
		# 執魂侵蝕：一道紅色裂紋爬上胸甲
		overlay.draw_polyline(PackedVector2Array([Vector2(3, -12), Vector2(1, -18), Vector2(4, -23),
			Vector2(2, -29)]), Color(1.0, 0.25, 0.15), 1.0)
	if arena.debug_info and p.is_perfect_window_open():
		DrawUtil.stroke_ellipse(overlay, Vector2(0, -1), Vector2(13, 5), Color(1, 1, 1, 0.6), 1.0, 24)


## 架勢崩潰：頭上繞圈的暈眩星點與驚嘆號（一眼可辨）
func _draw_dizzy(p: PlayerSim) -> void:
	var t := float(p.state_elapsed()) / Frames.FPS
	var outline := Color(0.1, 0.08, 0.05)
	for i in 4:
		var a := t * 6.0 + TAU * i / 4.0
		var dot := Vector2(cos(a) * 11.0, -40 + sin(a) * 3.5).round()
		overlay.draw_rect(Rect2(dot - Vector2(2, 2), Vector2(5, 5)), outline)
		overlay.draw_rect(Rect2(dot - Vector2(1, 1), Vector2(3, 3)), Palette.UI_POSTURE)
	var mark := Vector2(0, -54)
	overlay.draw_rect(Rect2(mark + Vector2(-2, -1), Vector2(5, 9)), outline)
	overlay.draw_rect(Rect2(mark + Vector2(-2, 9), Vector2(5, 5)), outline)
	overlay.draw_rect(Rect2(mark + Vector2(-1, 0), Vector2(3, 7)), Palette.UI_POSTURE_LOW)
	overlay.draw_rect(Rect2(mark + Vector2(-1, 10), Vector2(3, 3)), Palette.UI_POSTURE_LOW)
