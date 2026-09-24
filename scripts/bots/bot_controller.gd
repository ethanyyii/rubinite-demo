class_name BotController
extends RefCounted
## 模擬玩家（plan §7）的共用部分。機器人只透過 InputFrame 操作，和真人一樣受所有規則限制。
##
## 威脅預測：讀 Boss 目前的出招資料，算出接下來每一擊「第一次碰到玩家」的戰鬥幀（假設玩家不動）。
## 方向在命中前 0.2 秒鎖定、之後 Boss 不再移動（突刺與衝擊環例外，都有算進去），
## 所以只要在鎖定之後才依預測行動，預測就是準的。

## 玩家不動時，Boss 接下來會碰到玩家的每一擊：[{index, hit, start, overlap, windup}]（都是絕對戰鬥幀）
static func predict_threats(sim: CombatSim) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var b := sim.boss
	if b.state != BossSim.State.ATTACK or b.move == null:
		return out
	var e := b.state_elapsed()
	var now := sim.combat_frame
	var p := sim.player.pos
	for i in b.move.hits.size():
		var hit: BossHitData = b.move.hits[i]
		var start := b.hit_start_frame(i)
		var n := Frames.of(hit.active)
		if e >= start + n or b.is_hit_resolved(i):
			continue
		var lock_at := start - Frames.of(hit.lock_before)
		var origin := b.pos
		var dir := b.facing
		if e < lock_at:
			# 鎖定前：Boss 會轉向玩家；起手逼近會停在 advance_stop_distance
			var to := p - origin
			if to.length_squared() > 0.01:
				dir = to.normalized()
			if b.move.startup_advance_speed > 0.0:
				var d := to.length()
				var can_move := b.move.startup_advance_speed / Frames.FPS * maxi(lock_at - e, 0)
				var target := maxf(b.move.advance_stop_distance, d - can_move)
				origin = p - dir * target
		if b.move.airborne_start >= 0.0:
			origin = b.landing_target  # 墜王之躍：在落點落地（落點追蹤玩家，玩家不動時就是現在的落點）
		var overlap := -1
		# 突刺：目前已經前進的步數（這一幀的判定已經結算過，從下一幀開始預測）
		var steps_done := e - start + 1 if e >= start else 0
		for f in n:
			if start + f <= e:
				continue
			var o := origin
			if hit.lunge_distance > 0.0:
				o = origin + dir * (hit.lunge_distance / n) * (f + 1 - steps_done)
			var hb := {"hit": hit, "origin": o, "dir": dir, "ring_radius": BossSim.ring_radius(hit, f)}
			if CombatSim.boss_hitbox_overlaps(hb, p, PlayerData.HURT_RADIUS):
				overlap = start + f
				break
		if overlap < 0:
			continue
		out.append({"index": i, "hit": hit, "start": now - e + start, "overlap": now - e + overlap,
			"windup": now - e + b.windup_start(i)})
	return out


## 下一個會打到玩家的威脅；沒有時回傳空字典
static func next_threat(sim: CombatSim) -> Dictionary:
	var t := predict_threats(sim)
	return t[0] if not t.is_empty() else {}


## Boss 最快什麼時候能打到玩家（絕對戰鬥幀）：有預測中的威脅就是它；
## 否則是目前動作結束後最快的出招（喘息 + 最短起手 0.4 秒）。懲罰技反應 0.1 秒 + 起手 0.6 秒。
static func earliest_danger(sim: CombatSim) -> int:
	var b := sim.boss
	var now := sim.combat_frame
	var min_startup := Frames.of(0.4)
	var t := next_threat(sim)
	if not t.is_empty():
		return t["overlap"]
	match b.state:
		BossSim.State.ATTACK:
			var remaining := b.move.total_frames() - b.state_elapsed()
			return now + remaining + min_startup
		BossSim.State.BOUNCED:
			return now + b.remaining_frames() + min_startup
		BossSim.State.STAGGER:
			return now + b.remaining_frames() + min_startup
		BossSim.State.BROKEN, BossSim.State.EXECUTED:
			return now + b.remaining_frames() + Frames.of(VeltharisData.RISE_TIME) + min_startup
		BossSim.State.RISING:
			return now + b.remaining_frames() + min_startup
		BossSim.State.WALK:
			return now + mini(b.remaining_frames(), 1) + min_startup
	return now + min_startup


func decide(_sim: CombatSim) -> InputFrame:
	return InputFrame.new()
