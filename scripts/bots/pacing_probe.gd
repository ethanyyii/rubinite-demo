class_name PacingProbe
extends RefCounted
## plan §7「破韌節奏」量測：
## - 只靠彈返：完美機器人只防守不進攻，數 Boss 出了幾套攻擊（招式）才第一次失衡；
## - 只靠攻擊：Boss 不出招（木樁），玩家連續打四段連擊，數幾次四段才失衡。
##   gap_seconds 是兩次四段之間的間隔（0 = 一套接一套；間隔超過 2 秒會觸發韌性回復）。


## 回傳 Boss 第一次失衡前出了幾套攻擊；時限內沒失衡回傳 -1。
## only_parryable：只數至少有一擊可格擋的套路（不可格擋的灰燼衝擊彈返削不到韌，不算）
static func sets_to_break_by_parry(seed_value: int, only_parryable := false, max_seconds: float = 300.0) -> int:
	var sim := CombatSim.new(seed_value)
	sim.boss.set_ai()
	var bot := PerfectBot.new()
	bot.offense = false
	var sets := 0
	while sim.frame < Frames.of(max_seconds):
		sim.step(bot.decide(sim))
		for e in sim.events:
			if e["type"] == &"boss_attack":
				if not only_parryable or _has_blockable(VeltharisData.move(sim.boss.phase, e["move"])):
					sets += 1
			elif e["type"] == &"boss_break":
				return sets
	return -1


static func _has_blockable(m: BossMoveData) -> bool:
	for h in m.hits:
		if h.is_blockable():
			return true
	return false


## 回傳幾次四段連擊（可以是小數：最後一次打到第幾段）才失衡
static func combos_to_break_by_attack(gap_seconds: float) -> float:
	var sim := CombatSim.new(1)
	sim.boss.set_dummy()
	sim.boss.pos = Vector2(0, -20)
	sim.player.pos = Vector2(0, 26)
	sim.player.facing = Vector2.UP
	var hits := 0
	var wait_until := 0
	for i in Frames.of(600.0):
		var f := InputFrame.new()
		var p := sim.player
		if sim.combat_frame >= wait_until and p.can_start(&"attack"):
			if p.state != PlayerSim.State.ATTACK or p.combo_index < 3:
				f.attack_pressed = true
		sim.step(f)
		for e in sim.events:
			if e["type"] == &"boss_hit":
				hits += 1
				if hits % 4 == 0:
					wait_until = sim.combat_frame + Frames.of(0.45) + Frames.of(gap_seconds)
			elif e["type"] == &"boss_break":
				return floorf(hits / 4.0) + (hits % 4) / 4.0
	return -1.0
