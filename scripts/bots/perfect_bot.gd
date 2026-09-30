class_name PerfectBot
extends BotController
## 完美機器人（plan §7）：每一擊都在正確時機彈返或閃身。
## - 可格擋：在「第一次碰到玩家」的前 4 幀按下格擋（完美窗口 0–8 幀的正中間），擋完立刻放開（重新開窗）。
## - 不可格擋（衝擊環）：在碰到前 4 幀閃身，讓無敵第 1–9 幀蓋住環經過的那幾幀。
## - 進攻：只在「下一個可能的威脅」夠遠、來得及取消回防時出招；Boss 失衡就處決。

## 完美窗口的中間：按下後第 4 幀被擊中
const AIM := 4
## 第 1–3 段需要的安全幀數（取消點 14–15 幀 + 按格擋提前 4 幀 + 餘裕）
const SAFE_LIGHT := 21
## 第 4 段不可取消：需要的安全幀數見 BotController.safe_finisher()（收招結束 + 6；停頓中可以格擋、閃身）
## 進攻時保持的中心距離（攻擊範圍 40 + Boss 半徑 35 = 75 以內；最近 8 + 35 = 43）
const ATTACK_DIST := 46.0

var stats := {"parry_attempts": 0, "dodges": 0, "executions": 0}
## false：只防守不進攻（量測「只靠彈返破韌」用）
var offense := true


func decide(sim: CombatSim) -> InputFrame:
	var f := InputFrame.new()
	var p := sim.player
	var b := sim.boss
	var now1 := sim.combat_frame + 1  # 這個輸入會在哪一個戰鬥幀被處理
	var to_boss := b.pos - p.pos
	var dist := to_boss.length()
	if not p.locked and b.is_targetable() and dist <= PlayerData.LOCK_ACQUIRE_RANGE:
		f.lock_pressed = true

	var t := BotController.next_threat(sim)
	if not t.is_empty():
		var hit: BossHitData = t["hit"]
		var overlap: int = t["overlap"]
		if hit.is_blockable():
			if now1 >= overlap - AIM and now1 <= overlap:
				f.block = true  # 從 overlap-4 開始按住，直到這一擊結算
				if now1 == overlap - AIM:
					stats["parry_attempts"] += 1
				return f
		else:
			if now1 == overlap - AIM and p.can_start(&"dodge"):
				f.dodge_pressed = true
				f.move = to_boss.normalized()
				stats["dodges"] += 1
				return f
		# 威脅接近時站定不動（讓預測保持準確）
		if overlap - now1 <= 14:
			return f

	if not offense:
		return f
	# 失衡：走近處決
	if b.state == BossSim.State.BROKEN:
		if b.can_be_executed(p.pos):
			if p.state == PlayerSim.State.IDLE or p.can_start(&"attack"):
				f.attack_pressed = true
				stats["executions"] += 1
		else:
			f.move = to_boss.normalized()
		return f
	if not b.can_be_hit():
		return f

	var safe := BotController.earliest_danger(sim) - now1
	if dist > ATTACK_DIST + 4.0:
		# Boss 出招中還有沒結算的一擊時不走近：預測假設玩家不動，走進近距離招式的範圍會被打中
		var attack_pending := b.state == BossSim.State.ATTACK and b.current_hit_index() >= 0
		if safe > 16 and not attack_pending:
			f.move = to_boss.normalized()
		return f
	# 進攻：能接就接，依安全幀數決定出不出第 4 段
	if p.can_start(&"attack"):
		var next_stage: int = p.next_combo_stage(1)  # 按鍵落在下一幀
		var need := BotController.safe_finisher() if next_stage >= 3 else SAFE_LIGHT
		if safe >= need:
			f.attack_pressed = true
	return f
