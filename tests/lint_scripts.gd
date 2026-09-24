extends SceneTree
## 零警告檢查（plan §6.1）：載入專案所有 .gd（不含 addons），攔截 GDScript 警告與錯誤。
## 用法：godot --headless --debug --path . -s res://tests/lint_scripts.gd
## 必須加 --debug，GDScript 才會在編譯時回報警告。有任何警告或錯誤時結束碼為 1。

const SKIP_DIRS := ["res://addons", "res://.godot", "res://docs"]


class Collector extends Logger:
	var lines: Array[String] = []
	var _mutex := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, _script_backtraces: Array) -> void:
		if file.begins_with("res://addons"):
			return
		var kind := "WARNING" if error_type == ERROR_TYPE_WARNING else "ERROR"
		_mutex.lock()
		lines.append("%s %s (%s:%d @ %s)" % [kind, rationale if not rationale.is_empty() else code, file, line, function])
		_mutex.unlock()


var _collector := Collector.new()


func _initialize() -> void:
	OS.add_logger(_collector)
	var files: Array[String] = []
	_collect("res://", files)
	files.sort()
	for path in files:
		if path == get_script().resource_path:
			continue
		var s := ResourceLoader.load(path)
		if s == null:
			_collector.lines.append("ERROR 無法載入 %s" % path)
	OS.remove_logger(_collector)
	for l in _collector.lines:
		print(l)
	print("lint: %d 個腳本，%d 則問題" % [files.size(), _collector.lines.size()])
	quit(1 if not _collector.lines.is_empty() else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	for skip in SKIP_DIRS:
		if dir_path.begins_with(skip):
			return
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		_collect(dir_path.path_join(sub), out)
	for file in dir.get_files():
		if file.ends_with(".gd"):
			out.append(dir_path.path_join(file))
