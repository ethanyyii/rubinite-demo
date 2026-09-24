class_name PerfRecorder
extends Node
## 效能量測（plan §7：有畫面執行 3 分鐘，平均 ≥ 59fps，最低 ≥ 55fps）。
## 掛到場景上就開始記錄每一個畫面幀的實際間隔；result() 回傳統計。
## 「最低 fps」用每一整秒的畫面幀數（與 Engine.get_frames_per_second 相同的算法），另外附上最慢單幀。
## 設定 out_path 時，量完會把結果寫成 JSON 並結束遊戲（`--perf=秒數` 用，見 CombatArena._setup_perf_run）。

var duration := 180.0
## 可選：量測對象的競技場（統計死亡、勝利次數）
var arena: CombatArena = null
var out_path := ""

var _elapsed := 0.0
var _frames := 0
var _second_frames := 0
var _second_start := 0.0
var _per_second: Array[int] = []
var _worst_dt := 0.0
var _slow_frames := 0  # 單幀超過 1/55 秒的次數
var _missed_vsync := 0  # 單幀超過 1.5 / 60 秒（掉了一次垂直同步）的次數
var _start_usec := 0
var _last_usec := 0
var _draw_calls_sum := 0.0
var _draw_calls_max := 0.0
var _nodes_max := 0.0
var _objects_start := 0.0
var _deaths := 0
var _wins := 0
var _last_end_state := &""
var _written := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_start_usec = Time.get_ticks_usec()
	_last_usec = _start_usec
	_objects_start = Performance.get_monitor(Performance.OBJECT_COUNT)


func _process(_delta: float) -> void:
	if done():
		if out_path != "" and not _written:
			_write_and_quit()
		return
	# 用實際時間量測（不受 time_scale 影響）
	var now := Time.get_ticks_usec()
	var dt := (now - _last_usec) / 1000000.0
	_last_usec = now
	_elapsed = (now - _start_usec) / 1000000.0
	_frames += 1
	_second_frames += 1
	_worst_dt = maxf(_worst_dt, dt)
	if dt > 1.0 / 55.0:
		_slow_frames += 1
	if dt > 1.5 / 60.0:
		_missed_vsync += 1
	if _elapsed - _second_start >= 1.0:
		_per_second.append(_second_frames)
		_second_frames = 0
		_second_start += 1.0
	var dc := Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
	_draw_calls_sum += dc
	_draw_calls_max = maxf(_draw_calls_max, dc)
	_nodes_max = maxf(_nodes_max, Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
	if arena != null and arena.end_state != _last_end_state:
		_last_end_state = arena.end_state
		if _last_end_state == &"death":
			_deaths += 1
		elif _last_end_state == &"victory":
			_wins += 1


func done() -> bool:
	return _elapsed >= duration


func result() -> Dictionary:
	var min_fps := 0
	if not _per_second.is_empty():
		min_fps = _per_second.min()
	return {
		"seconds": snappedf(_elapsed, 0.01),
		"frames": _frames,
		"avg_fps": snappedf(_frames / maxf(_elapsed, 0.001), 0.01),
		"min_fps_per_second": min_fps,
		"worst_frame_ms": snappedf(_worst_dt * 1000.0, 0.01),
		"frames_slower_than_55fps": _slow_frames,
		"frames_missing_vsync": _missed_vsync,
		"draw_calls_avg": snappedf(_draw_calls_sum / maxi(_frames, 1), 0.1),
		"draw_calls_max": _draw_calls_max,
		"nodes_max": _nodes_max,
		"objects_start": _objects_start,
		"objects_end": Performance.get_monitor(Performance.OBJECT_COUNT),
		"deaths": _deaths,
		"wins": _wins,
		"vsync_mode": DisplayServer.window_get_vsync_mode(),
		"screen_refresh_rate": DisplayServer.screen_get_refresh_rate(),
		"window_size": [DisplayServer.window_get_size().x, DisplayServer.window_get_size().y],
		"per_second": _per_second,
		"done": done(),
	}


func _write_and_quit() -> void:
	_written = true
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f == null:
		push_error("寫不出效能結果：%s" % out_path)
	else:
		f.store_string(JSON.stringify(result(), "  "))
		f.close()
	print("perf: %s" % JSON.stringify(result()))
	get_tree().quit()
