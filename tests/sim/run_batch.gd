extends SceneTree
## 批次模擬（plan §7）：godot --headless --path . -s res://tests/sim/run_batch.gd -- --bot=perfect --games=5 --stop-hp=780
## 結果印在標準輸出，並寫到 docs/evidence/sim/<name>.json。

func _initialize() -> void:
	var opts := {"bot": "perfect", "games": "5", "seed": "1", "stop-hp": "0", "max-seconds": "600", "name": ""}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			var kv := a.substr(2).split("=", true, 1)
			opts[kv[0]] = kv[1]
	var games := int(opts["games"])
	var results: Array = []
	var t0 := Time.get_ticks_msec()
	for g in games:
		var bot: BotController
		if opts["bot"] == "perfect":
			bot = PerfectBot.new()
		else:
			var hb := HumanBot.new(int(opts["seed"]) * 7919 + g)
			hb.cautious = opts["bot"] == "human_cautious"
			bot = hb
		var r := FightRunner.run(int(opts["seed"]) + g, bot, float(opts["max-seconds"]), int(opts["stop-hp"]))
		results.append(r)
		print("game %d: %s  %.1fs  damage %d  boss_hp %d  perfect %d  blocked %d  hits %d  dodges %d  exec %d" % [g,
			r["result"], r["seconds"], r["damage_taken"], r["boss_hp"], r["perfect"], r["blocked"], r["hits_taken"],
			r["dodges"], r["executions"]])
	var summary := BatchStats.summarize(results)
	summary["bot"] = opts["bot"]
	summary["games"] = games
	summary["wall_ms"] = Time.get_ticks_msec() - t0
	print(JSON.stringify(summary, "  "))
	var name: String = opts["name"] if opts["name"] != "" else "%s_%d" % [opts["bot"], games]
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://docs/evidence/sim"))
	var f := FileAccess.open("res://docs/evidence/sim/%s.json" % name, FileAccess.WRITE)
	f.store_string(JSON.stringify({"summary": summary, "games": results}, "  "))
	f.close()
	quit()
