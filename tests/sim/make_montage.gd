extends SceneTree
## 把多張證據截圖縮成一半、排成格子，存成一張（M6「預兆可讀」的對照表）。
## godot --headless --path . -s res://tests/sim/make_montage.gd -- --out=res://docs/evidence/M6/x.png --cols=3 a.png b.png …
func _initialize() -> void:
	var out := ""
	var cols := 3
	var paths: Array[String] = []
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.get_slice("=", 1)
		elif a.begins_with("--cols="):
			cols = int(a.get_slice("=", 1))
		else:
			paths.append(a)
	if out == "" or paths.is_empty():
		push_error("用法：-- --out=res://… [--cols=N] 圖1.png 圖2.png …")
		quit(1)
		return
	var cell := Vector2i(640, 360)
	var gap := 4
	var rows := ceili(paths.size() / float(cols))
	var img := Image.create(cols * cell.x + (cols - 1) * gap, rows * cell.y + (rows - 1) * gap, false, Image.FORMAT_RGB8)
	img.fill(Color(0.9, 0.9, 0.9))
	for i in paths.size():
		var src := Image.load_from_file(ProjectSettings.globalize_path(paths[i]))
		if src == null:
			push_error("讀不到 %s" % paths[i])
			quit(1)
			return
		src.convert(Image.FORMAT_RGB8)
		src.resize(cell.x, cell.y, Image.INTERPOLATE_NEAREST)
		var at := Vector2i((i % cols) * (cell.x + gap), floori(i / float(cols)) * (cell.y + gap))
		img.blit_rect(src, Rect2i(Vector2i.ZERO, cell), at)
	var err := img.save_png(ProjectSettings.globalize_path(out))
	if err != OK:
		push_error("存不了 %s（錯誤 %d）" % [out, err])
		quit(1)
		return
	print("saved %s (%d images)" % [out, paths.size()])
	quit()
