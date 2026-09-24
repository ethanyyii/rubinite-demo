extends TestCase


func test_main_scene_loads() -> void:
	var path: String = ProjectSettings.get_setting("application/run/main_scene")
	assert_true(ResourceLoader.exists(path), "main scene %s is missing" % path)


func test_runner_reports_values() -> void:
	assert_eq(2 + 3, 5)
	assert_near(0.1 + 0.2, 0.3, 0.0001)
