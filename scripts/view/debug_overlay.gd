extends Control
## 除錯資訊（畫面座標）：F1 顯示數值面板；F2–F4 啟用時在右上角標示。

var arena: CombatArena


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(_delta: float) -> void:
	queue_redraw()


func _draw() -> void:
	var font := ThemeDB.fallback_font
	var flags: Array[String] = []
	if arena.slow_motion:
		flags.append("F2 慢動作 0.25x")
	if arena.boss_manual:
		flags.append("F3 手動出招（數字鍵 1–9、0）")
	if arena.sim.god_mode:
		flags.append("F4 無敵")
	if not arena.attack_preview:
		flags.append("F6 判定預覽關")
	# 畫面 960×540（2026-09-30 鏡頭拉遠）：位置與字級照原本的 1.5 倍
	var y := 18.0
	for f in flags:
		_text(font, Vector2(size.x - 12, y), f, HORIZONTAL_ALIGNMENT_RIGHT)
		y += 16.0
	if not arena.debug_info:
		return
	var sim: CombatSim = arena.sim
	var p := sim.player
	var b := sim.boss
	var lines: Array[String] = [
		"FPS %d   幀 %d   戰鬥幀 %d   頓幀 %d" % [Engine.get_frames_per_second(), sim.frame, sim.combat_frame, sim.hitstop],
		"玩家 %s (%d)  HP %d  架勢 %.1f  治療 %d  鎖定 %s" % [p.state_name(), p.state_elapsed(), p.hp, p.posture, p.heals, "是" if p.locked else "否"],
		"  位置 (%.1f, %.1f)  速度 %.1f" % [p.pos.x, p.pos.y, p.vel.length()],
		"Boss %s (%d)  HP %d  韌性 %.1f  階段 %d" % [b.state_name(), b.state_elapsed(), b.hp, b.toughness, b.phase],
	]
	lines.append_array(arena.extra_debug_lines())
	var ly := 66.0
	for line in lines:
		_text(font, Vector2(15, ly), line, HORIZONTAL_ALIGNMENT_LEFT)
		ly += 15.0


func _text(font: Font, at: Vector2, text: String, align: HorizontalAlignment) -> void:
	var w := -1.0
	var pos := at
	if align == HORIZONTAL_ALIGNMENT_RIGHT:
		w = font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
		pos.x -= w
	draw_string_outline(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, 4, Color(0, 0, 0, 0.9))
	draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 0.7))
