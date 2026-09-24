extends SceneTree
## 破韌節奏（plan §7）：godot --headless --path . -s res://tests/sim/run_pacing.gd -- --games=100 [--seed-base=100] [--out=res://…json]
func _initialize() -> void:
	var games := 30
	var seed_base := 100
	var out := "res://docs/evidence/sim/pacing.json"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--games="):
			games = int(a.get_slice("=", 1))
		elif a.begins_with("--seed-base="):
			seed_base = int(a.get_slice("=", 1))
		elif a.begins_with("--out="):
			out = a.get_slice("=", 1)
	var sets: Array[int] = []
	var parryable: Array[int] = []
	for g in games:
		sets.append(PacingProbe.sets_to_break_by_parry(seed_base + g))
		parryable.append(PacingProbe.sets_to_break_by_parry(seed_base + g, true))
	var result := {
		"games": games,
		"seed_base": seed_base,
		"parry_only_sets_to_break": sets,
		"parry_only_avg": _avg(sets),
		"parry_only_median": _median(sets),
		"parry_only_parryable_sets_to_break": parryable,
		"parry_only_parryable_avg": _avg(parryable),
		"parry_only_parryable_median": _median(parryable),
		"attack_only_combos_back_to_back": PacingProbe.combos_to_break_by_attack(0.0),
		"attack_only_combos_1s_gap": PacingProbe.combos_to_break_by_attack(1.0),
		"attack_only_combos_3s_gap": PacingProbe.combos_to_break_by_attack(3.0),
	}
	print(JSON.stringify(result, "  "))
	var f := FileAccess.open(out, FileAccess.WRITE)
	f.store_string(JSON.stringify(result, "  "))
	f.close()
	quit()


func _avg(a: Array[int]) -> float:
	var ok := a.filter(func(v: int) -> bool: return v >= 0)
	var total := 0.0
	for v: int in ok:
		total += v
	return snappedf(total / maxf(ok.size(), 1), 0.01)


func _median(a: Array[int]) -> float:
	var ok := a.filter(func(v: int) -> bool: return v >= 0)
	ok.sort()
	if ok.is_empty():
		return -1.0
	var mid := floori(ok.size() / 2.0)
	return float(ok[mid]) if ok.size() % 2 == 1 else (ok[mid - 1] + ok[mid]) / 2.0
