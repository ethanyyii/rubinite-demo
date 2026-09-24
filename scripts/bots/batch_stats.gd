class_name BatchStats
extends RefCounted
## 批次模擬結果的統計（plan §7 指標）。


static func summarize(results: Array) -> Dictionary:
	var wins := 0
	var win_secs: Array[float] = []
	var per_move := {}
	var total_perfect := 0
	var total_blockable := 0
	var zero_damage_wins := 0
	for r: Dictionary in results:
		if r["result"] == &"win":
			wins += 1
			win_secs.append(r["seconds"])
			if r["damage_taken"] == 0:
				zero_damage_wins += 1
		for g: StringName in r["per_move"]:
			var pm: Dictionary = r["per_move"][g]
			var acc: Dictionary = per_move.get(g, {"perfect": 0, "blocked": 0, "hit": 0})
			for k in ["perfect", "blocked", "hit"]:
				acc[k] += pm[k]
			per_move[g] = acc
	var parry_rate := {}
	for g: StringName in per_move:
		var acc: Dictionary = per_move[g]
		var n: int = acc["perfect"] + acc["blocked"] + acc["hit"]
		if g == &"ash_impact":
			continue  # 不可格擋，不算彈返率
		if n > 0:
			parry_rate[String(g)] = snappedf(float(acc["perfect"]) / n, 0.001)
			total_perfect += acc["perfect"]
			total_blockable += n
	var n_games := maxi(results.size(), 1)
	return {
		"win_rate": snappedf(float(wins) / n_games, 0.001),
		"wins": wins,
		"zero_damage_wins": zero_damage_wins,
		"win_seconds_avg": snappedf(_avg(win_secs), 0.1),
		"win_seconds_min": snappedf(win_secs.min() if not win_secs.is_empty() else 0.0, 0.1),
		"win_seconds_max": snappedf(win_secs.max() if not win_secs.is_empty() else 0.0, 0.1),
		"parry_rate_by_move": parry_rate,
		"parry_rate_overall": snappedf(float(total_perfect) / maxi(total_blockable, 1), 0.001),
		"per_move": per_move,
	}


static func _avg(a: Array[float]) -> float:
	if a.is_empty():
		return 0.0
	var s := 0.0
	for v in a:
		s += v
	return s / a.size()
