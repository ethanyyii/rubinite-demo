extends SceneTree
## 無介面測試：godot --headless --path . -s res://tests/unit/run_tests.gd
## 全部通過時結束碼為 0，否則為 1。
##
## - 測試在第一個 process 幀執行（這時場景樹已就緒，加入的節點會收到 _ready）。
## - 測試期間的腳本錯誤與 push_error 也算失敗（用 Logger 攔截），避免「執行到一半出錯卻算通過」。
## - 可用 -- --filter=<字串> 只跑檔名或方法名包含該字串的測試。

const ROOT := "res://tests/unit"


class ErrorCounter extends Logger:
	var errors: Array[String] = []
	var _mutex := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, _script_backtraces: Array) -> void:
		if error_type == ERROR_TYPE_WARNING:
			return
		_mutex.lock()
		errors.append("%s (%s:%d @ %s)" % [rationale if not rationale.is_empty() else code, file, line, function])
		_mutex.unlock()

	func count() -> int:
		_mutex.lock()
		var n := errors.size()
		_mutex.unlock()
		return n


var _counter := ErrorCounter.new()


func _initialize() -> void:
	OS.add_logger(_counter)
	process_frame.connect(_run, CONNECT_ONE_SHOT)


func _run() -> void:
	var filter := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--filter="):
			filter = arg.trim_prefix("--filter=")
	var files: Array[String] = []
	_collect(ROOT, files)
	files.sort()
	var passed := 0
	var failed := 0
	for path in files:
		var script: Script = load(path)
		if script == null or not script.can_instantiate():
			print("LOAD ERROR  %s" % path)
			failed += 1
			continue
		for method in script.get_script_method_list():
			var name: String = method["name"]
			if not name.begins_with("test_"):
				continue
			if not filter.is_empty() and not (path.get_file().contains(filter) or name.contains(filter)):
				continue
			var before := _counter.count()
			var case: TestCase = script.new()
			case.before_each()
			case.call(name)
			case.after_each()
			var new_errors := _counter.errors.slice(before)
			if case.failures.is_empty() and new_errors.is_empty():
				passed += 1
			else:
				failed += 1
				print("FAIL  %s::%s" % [path.get_file(), name])
				for f in case.failures:
					print("      %s" % f)
				for e in new_errors:
					print("      ERROR %s" % e)
	print("\n%d passed, %d failed" % [passed, failed])
	OS.remove_logger(_counter)
	if passed + failed == 0:
		print("沒有執行任何測試（檢查 --filter 或測試資料夾）")
		quit(1)
		return
	quit(1 if failed > 0 else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		_collect(dir_path.path_join(sub), out)
	for file in dir.get_files():
		if file.begins_with("test_") and file.ends_with(".gd") and file != "test_case.gd":
			out.append(dir_path.path_join(file))
