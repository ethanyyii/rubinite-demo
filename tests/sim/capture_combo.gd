extends SceneTree
## 遊戲裡連按四段輕攻擊的驗證（art-progress「四段輕攻擊：調整間隔」）：真實按鍵（DebugDriver.key，走完整的
## InputMap 流程）每 2 個物理幀按一次 J，記下每段開始的戰鬥幀，第 4 段在指定的幀凍結截圖。
## 需要畫面（不能 --headless）：
## godot --path . -s res://tests/sim/capture_combo.gd -- --out=res://docs/evidence/combo4b
## Boss 切成手動（不出招）、主角無敵；結果印在標準輸出。

const DebugDriver := preload("res://scripts/view/debug_driver.gd")
const STAGE4_SHOTS: Array[int] = [0, 2, 4, 5, 6, 7, 9, 12, 15, 24, 40]


func _initialize() -> void:
	var out := "res://docs/evidence/combo4b"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.get_slice("=", 1)
	var scene: PackedScene = load(ProjectSettings.get_setting("application/run/main_scene"))
	var arena := scene.instantiate() as CombatArena
	root.add_child(arena)
	_run.call_deferred(arena, out)


func _run(arena: CombatArena, out: String) -> void:
	for i in 10:
		await physics_frame
	var d: DebugDriver = arena.get_node("Debug")
	arena.boss_manual = true
	arena.sim.boss.set_manual()
	arena.sim.god_mode = true
	# 慢動作：每一步模擬之間有好幾個畫面幀，截圖凍結再恢復時不會一口氣補跑好幾步（按鍵的節奏以模擬幀計，不受影響）
	Engine.time_scale = 0.25
	var p := arena.sim.player
	var starts: Array = []
	var last_start := -1
	var shots: Array[String] = []
	var shot_i := 0
	for i in 600:
		d.key(KEY_J, i % 2 == 0 and starts.size() < 4)
		await physics_frame
		# physics_frame 在這一步的模擬之前發出；等到這一幀處理完（畫面上就是這個狀態）再讀
		await process_frame
		var in_finisher := p.state == PlayerSim.State.ATTACK and p.combo_index == PlayerData.last_light_stage()
		if p.state == PlayerSim.State.ATTACK:
			var start := arena.sim.combat_frame - p.state_elapsed()
			if start != last_start:
				last_start = start
				starts.append([start, p.combo_index])
		if in_finisher and shot_i < STAGE4_SHOTS.size() and p.state_elapsed() >= STAGE4_SHOTS[shot_i]:
			var e := p.state_elapsed()
			var path := "%s/stage4_e%02d.png" % [out, e]
			# 截圖存檔會卡一下；期間停住模擬，恢復後才不會一口氣補跑好幾步而跳過要拍的幀
			arena.set_physics_process(false)
			await d.capture(path)
			for k in 3:
				await process_frame
			arena.set_physics_process(true)
			shots.append(path)
			shot_i += 1
		if starts.size() >= 4 and p.state != PlayerSim.State.ATTACK:
			break
	d.key(KEY_J, false)
	Engine.time_scale = 1.0
	var hits: Array = []
	for s in starts:
		hits.append(int(s[0]) + PlayerData.light_attacks()[int(s[1])].startup_frames())
	var gaps: Array = []
	for k in range(1, hits.size()):
		gaps.append(int(hits[k]) - int(hits[k - 1]))
	print("stage starts (combat frame, stage 0-3): ", starts)
	print("hit frames: ", hits, "  gaps: ", gaps)
	print("shots: ", shots)
	quit()
