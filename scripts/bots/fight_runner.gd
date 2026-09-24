class_name FightRunner
extends RefCounted
## 無介面跑一整場戰鬥（plan §7 批次模擬）：機器人操作 CombatSim，收集指標。

const R := CombatSim.BlockResult

## 跑一場。stop_boss_hp：Boss HP 降到這個值以下就算「過關」（例如只驗第一階段時用最大 HP 的一半）。
static func run(seed_value: int, bot: BotController, max_seconds: float = 600.0, stop_boss_hp: int = 0) -> Dictionary:
	var sim := CombatSim.new(seed_value)
	sim.boss.set_ai()
	var max_frames := Frames.of(max_seconds)
	var m := {
		"seed": seed_value, "result": &"timeout", "frames": 0, "combat_frames": 0,
		"damage_taken": 0, "player_hp": 0, "boss_hp": 0, "hits_taken": 0,
		"perfect": 0, "blocked": 0, "hit_by_blockable": 0, "hit_by_unblockable": 0,
		"dodges": 0, "executions": 0, "boss_breaks": 0, "heals": 0, "posture_breaks": 0,
		"moves": {}, "per_move": {},
	}
	var hp_prev := sim.player.hp
	while sim.frame < max_frames:
		sim.step(bot.decide(sim))
		for e in sim.events:
			match e["type"]:
				&"boss_attack":
					var mv: StringName = e["move"]
					m["moves"][mv] = int(m["moves"].get(mv, 0)) + 1
				&"boss_hit_result":
					var g := VeltharisData.group_of(e["move"])
					var pm: Dictionary = m["per_move"].get(g, {"perfect": 0, "blocked": 0, "hit": 0})
					match int(e["result"]):
						R.PERFECT:
							m["perfect"] += 1
							pm["perfect"] += 1
						R.BLOCKED:
							m["blocked"] += 1
							pm["blocked"] += 1
						R.HIT:
							pm["hit"] += 1
							m["hits_taken"] += 1
							if e["blockable"]:
								m["hit_by_blockable"] += 1
							else:
								m["hit_by_unblockable"] += 1
					m["per_move"][g] = pm
				&"dodge":
					m["dodges"] += 1
				&"execution_hit":
					m["executions"] += 1
				&"boss_break":
					m["boss_breaks"] += 1
				&"heal_start":
					m["heals"] += 1
				&"posture_break":
					m["posture_breaks"] += 1
		if sim.player.hp < hp_prev:
			m["damage_taken"] += hp_prev - sim.player.hp
		hp_prev = sim.player.hp
		if sim.player.state == PlayerSim.State.DEAD:
			m["result"] = &"loss"
			break
		if sim.boss.hp <= stop_boss_hp:
			m["result"] = &"win"
			break
	m["frames"] = sim.frame
	m["combat_frames"] = sim.combat_frame
	m["player_hp"] = sim.player.hp
	m["boss_hp"] = sim.boss.hp
	m["seconds"] = snappedf(float(sim.frame) / Frames.FPS, 0.01)
	return m
