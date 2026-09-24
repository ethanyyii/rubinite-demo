extends SceneTree

const ROOT := "res://tests/unit"


func _initialize() -> void:
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
			var case: TestCase = script.new()
			case.before_each()
			case.call(name)
			case.after_each()
			if case.failures.is_empty():
				passed += 1
			else:
				failed += 1
				print("FAIL  %s::%s" % [path.get_file(), name])
				for f in case.failures:
					print("      %s" % f)
	print("\n%d passed, %d failed" % [passed, failed])
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
