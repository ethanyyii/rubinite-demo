class_name HumanBot
extends BotController
## 擬人機器人（plan §7）：
## - 看到預兆後 0.25 秒才能反應（每一擊的起手開始算起）；
## - 按鍵時機的誤差為常態分布，標準差 60ms；以完美窗口的中間（碰到前 4 幀）為瞄準點；
## - 延遲攻擊有 30% 機率被騙：照普通版的時機按下並一直按住（變成普通格擋）。
## 進攻與治療的判斷不在 plan 規定內，採用「一般玩家」的保守做法，參數列在下面並寫進報告。

var rng := RandomNumberGenerator.new()
## plan §7 的參數
var reaction_frames := Frames.of(0.25)
var timing_sigma_frames := 0.060 * Frames.FPS
var fooled_chance := 0.3
const AIM := 4
## 進攻判斷（本專案自訂，寫進報告）：
## - 只在看得懂的空檔出手：Boss 被彈開、短僵直、失衡／處決／起身、出招收招、喘息走路；看到空檔後同樣要 0.25 秒反應；
## - Boss 起手預兆亮著（劍變紅、閃爍、危險）時不開新的連段；
## - 每個空檔打幾下是隨機的（1–4 下，權重如下），打完就收手；
## - 安全幀數的估計有誤差（常態分布，標準差 6 幀）；第 4 段有 20% 機率貪刀；血量少到「再被打一下就可能死」（≤ 這個階段 Boss 單擊的最大傷害）時找安全的時機治療。
var safety_sigma_frames := 6.0
var greed_finisher := 0.2
## 治療門檻：HP ≤ Boss 單擊最大傷害 + 這個餘裕
var heal_margin := 0
var hits_per_opening_weights := [0.2, 0.35, 0.25, 0.2]
## 謹慎型（只用於報告的敏感度分析，不是 plan §7 的指標設定）：只在彈開、短僵直、起身時進攻，不打喘息與收招
var cautious := false
## 治療前要求的安全幀數 = 治療時間 + 這個餘裕（原本治療 54 幀時寫死 70 = 54 + 16）
const HEAL_SAFETY_MARGIN := 16
const SAFE_LIGHT := 21
const ATTACK_DIST := 48.0

## 每一擊的計畫：key → {"at": 動作幀, "fooled": bool}
var _plans := {}
var _holding_key := ""
var _last_state := -1
var _state_seen := 0
## 這個空檔打算打幾下、已經打了幾下
var _chain_budget := 0
var _chain_used := 0
var stats := {"fooled": 0, "plans": 0}
## 每個階段 Boss 單擊的最大傷害（治療門檻用）
var _worst_hit := {}


func _init(seed_value: int = 1) -> void:
	rng.seed = seed_value


func reset() -> void:
	_plans.clear()
	_holding_key = ""
	_last_state = -1
	_state_seen = 0
	_chain_budget = 0
	_chain_used = 0


func decide(sim: CombatSim) -> InputFrame:
	var f := InputFrame.new()
	var p := sim.player
	var b := sim.boss
	var now1 := sim.combat_frame + 1
	var to_boss := b.pos - p.pos
	var dist := to_boss.length()
	if b.state != _last_state:
		_last_state = b.state
		_state_seen = sim.combat_frame
	if not p.locked and b.is_targetable() and dist <= PlayerData.LOCK_ACQUIRE_RANGE:
		f.lock_pressed = true

	var t := BotController.next_threat(sim)
	if not t.is_empty():
		var hit: BossHitData = t["hit"]
		var overlap: int = t["overlap"]
		var key := "%d:%d" % [sim.combat_frame - b.state_elapsed(), t["index"]]
		var visible_from: int = t["windup"] + reaction_frames
		if not _plans.has(key) and now1 >= visible_from:
			# 看到了：決定這一擊的時機誤差（之後一直追著實際的攻擊，但誤差固定）
			var fooled := hit.is_delayed() and rng.randf() < fooled_chance
			if fooled:
				stats["fooled"] += 1
			_plans[key] = {"noise": roundi(rng.randfn(0.0, timing_sigma_frames)), "fooled": fooled,
				"visible_from": visible_from}
			stats["plans"] += 1
		if _plans.has(key):
			var plan: Dictionary = _plans[key]
			var target := overlap - AIM
			if plan["fooled"]:
				target -= Frames.of(hit.delay_hold)  # 被騙：照普通版的時機按下（然後一直按住）
			var at := maxi(target + int(plan["noise"]), int(plan["visible_from"]))
			if hit.is_blockable():
				if now1 >= at and now1 <= overlap + 2:
					f.block = true
					_holding_key = key
					return f
			elif now1 == at and p.can_start(&"dodge"):
				f.dodge_pressed = true
				f.move = to_boss.normalized()
				return f
			# 看到攻擊要來了：站定準備（不再往前走）
			return f
		if overlap - now1 <= 14:
			return f

	# 失衡：走近處決（看到之後才反應）
	if b.state == BossSim.State.BROKEN:
		if sim.combat_frame - _state_seen < reaction_frames:
			return f
		if b.can_be_executed(p.pos):
			if p.can_start(&"attack"):
				f.attack_pressed = true
		else:
			f.move = to_boss.normalized()
		return f
	if not b.can_be_hit():
		return f

	var safe := BotController.earliest_danger(sim) - now1 + roundi(rng.randfn(0.0, safety_sigma_frames))
	# 治療：血少、而且看起來安全（離得遠，或 Boss 還有一段空檔）
	if p.hp <= heal_threshold(b.phase) and p.heals > 0 and p.state == PlayerSim.State.IDLE:
		if dist > VeltharisData.HEAL_PUNISH_RANGE or safe >= Frames.of(PlayerData.HEAL_TIME) + HEAL_SAFETY_MARGIN:
			f.heal_pressed = true
			return f
		# 拉開距離再喝
		f.move = -to_boss.normalized()
		f.run = true
		return f
	if dist > ATTACK_DIST + 4.0:
		if safe > 16:
			f.move = to_boss.normalized()
		return f
	if p.can_start(&"attack"):
		# 收招中或接段寬限中（§8.1）按下是接段
		var next_stage: int = p.next_combo_stage(1)  # 按鍵落在下一幀
		var chaining: bool = next_stage > 0
		if not chaining:
			# 開新的連段：要是看得懂的空檔、看到之後過了反應時間、沒有起手預兆
			if not _is_opening(b) or sim.combat_frame - _state_seen < reaction_frames \
					or b.telegraph() != CombatTypes.Telegraph.NONE:
				return f
			_chain_budget = _pick_budget()
			_chain_used = 0
		elif _chain_used >= _chain_budget:
			return f
		var need := SAFE_LIGHT
		if next_stage >= 3:
			need = BotController.safe_finisher() if rng.randf() >= greed_finisher else SAFE_LIGHT + 10
		if safe >= need:
			f.attack_pressed = true
			_chain_used += 1
	return f


## 治療門檻：這個階段 Boss 任何一擊的最大傷害（再被打一下就可能死）
func heal_threshold(phase: int) -> int:
	if not _worst_hit.has(phase):
		var worst := 0
		for id: StringName in VeltharisData.moves(phase):
			for h: BossHitData in VeltharisData.moves(phase)[id].hits:
				worst = maxi(worst, h.damage)
		_worst_hit[phase] = worst
	return int(_worst_hit[phase]) + heal_margin


## 看得懂的空檔
func _is_opening(b: BossSim) -> bool:
	if cautious:
		return b.state in [BossSim.State.BOUNCED, BossSim.State.STAGGER, BossSim.State.RISING]
	match b.state:
		BossSim.State.BOUNCED, BossSim.State.STAGGER, BossSim.State.RISING, BossSim.State.WALK:
			return true
		BossSim.State.ATTACK:
			return b.current_hit_index() < 0  # 收招
	return false


func _pick_budget() -> int:
	var r := rng.randf()
	for i in hits_per_opening_weights.size():
		r -= hits_per_opening_weights[i]
		if r <= 0.0:
			return i + 1
	return hits_per_opening_weights.size()
