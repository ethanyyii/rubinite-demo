class_name CombatSim
extends RefCounted
## 整場戰鬥的決定性模擬。每個物理幀呼叫一次 step()。
##
## 遊戲畫面（CombatArena）與無介面的批次模擬共用這一份邏輯：畫面只讀取狀態與事件，
## 不參與判定。所有計時都以幀為單位（Frames）。
##
## 每幀順序：頓幀 → 玩家 → Boss → 判定 → 碰撞推開 → 資源回復。
## 頓幀期間戰鬥時間（combat_frame）暫停，但這段時間按下的鍵會累積，頓幀結束後送出，
## 所以頓幀不會吃掉輸入緩衝（CLAUDE.md 慣例）。

## Boss 的一擊打到玩家的結果
enum BlockResult { MISS, HIT, BLOCKED, PERFECT }

## 物理幀計數（含頓幀）
var frame := 0
## 戰鬥時間（不含頓幀）。所有狀態計時都用這個。
var combat_frame := 0
## 剩餘頓幀
var hitstop := 0
var player: PlayerSim
var boss: BossSim
var rng := RandomNumberGenerator.new()
## 這一幀發生的事件，畫面層用來產生特效、音效、震動
var events: Array[Dictionary] = []
## 除錯：玩家無敵（F4）
var god_mode := false

var _pending := InputFrame.new()


func _init(seed_value: int = 1) -> void:
	reset(seed_value)


func reset(seed_value: int = 1) -> void:
	rng.seed = seed_value
	frame = 0
	combat_frame = 0
	hitstop = 0
	events.clear()
	_pending = InputFrame.new()
	player = PlayerSim.new(self)
	boss = BossSim.new(self)


func step(input: InputFrame) -> void:
	events.clear()
	frame += 1
	if hitstop > 0:
		hitstop -= 1
		_pending.merge_presses(input)
		return
	if _pending.has_presses():
		# 頓幀中累積的按鍵較早，這一幀的按鍵較晚
		_pending.merge_presses(input)
		_pending.copy_presses_to(input)
		_pending = InputFrame.new()
	combat_frame += 1
	player.tick(input)
	for e in events:
		if e["type"] == &"heal_start":
			boss.on_player_heal()
	boss.tick()
	_resolve_player_hits()
	_resolve_boss_hits()
	_resolve_bodies()


## 產生事件。data 會被複製，type 放在 "type" 欄位，發生的戰鬥幀放在 "frame"。
func emit(type: StringName, data: Dictionary = {}) -> void:
	var e := data.duplicate()
	e["type"] = type
	e["frame"] = combat_frame
	events.append(e)


## 打擊感事件：加上頓幀，並送出帶震動資料的事件（FeedbackData）。
func feedback(event: StringName, at: Vector2) -> void:
	hitstop = maxi(hitstop, FeedbackData.hitstop_frames(event))
	emit(&"feedback", {"event": event, "pos": at, "shake": FeedbackData.shake(event),
		"shake_time": FeedbackData.shake_time(event)})


func elapsed_since(start_frame: int) -> int:
	return combat_frame - start_frame


## 玩家的攻擊判定打到 Boss（每段只打中一次）。
func _resolve_player_hits() -> void:
	var hb := player.attack_hitbox()
	if hb.is_empty() or not boss.can_be_hit():
		return
	var r := VeltharisData.HURT_RADIUS
	var hit := false
	match hb["shape"]:
		&"sector":
			hit = HitGeometry.circle_hits_sector(boss.pos, r, hb["origin"], hb["dir"], hb["radius"], hb["arc"])
		&"capsule":
			hit = HitGeometry.circle_hits_capsule(boss.pos, r, hb["a"], hb["b"], hb["width"] * 0.5)
	if not hit:
		return
	var atk: PlayerAttackData = hb["attack"]
	player.on_attack_connected()
	boss.receive_player_hit(atk)
	var contact := boss.pos + (player.pos - boss.pos).limit_length(r)
	feedback(atk.feedback, contact)


## Boss 的攻擊判定打到玩家。玩家無敵時不結算（判定繼續，之後的幀還可能打中）；
## 命中、格擋、彈返都算結算，同一擊只結算一次。
func _resolve_boss_hits() -> void:
	var hb := boss.attack_hitbox()
	if hb.is_empty():
		return
	if not boss_hitbox_overlaps(hb, player.pos, PlayerData.HURT_RADIUS):
		return
	var result := apply_boss_hit(hb["hit"], boss.pos)
	if result != BlockResult.MISS:
		boss.mark_hit_resolved(hb["index"])


## Boss 判定形狀與圓 (c, r) 是否相交
static func boss_hitbox_overlaps(hb: Dictionary, c: Vector2, r: float) -> bool:
	var hit: BossHitData = hb["hit"]
	var o: Vector2 = hb["origin"]
	var d: Vector2 = hb["dir"]
	match hit.shape:
		CombatTypes.Shape.SECTOR:
			return HitGeometry.circle_hits_sector(c, r, o, d, hit.radius, hit.angle_deg)
		CombatTypes.Shape.RECT:
			return HitGeometry.circle_hits_rect(c, r, o, d, hit.length, hit.width)
		CombatTypes.Shape.CIRCLE:
			return HitGeometry.circle_hits_circle(c, r, o, hit.radius)
		CombatTypes.Shape.RING:
			return HitGeometry.circle_hits_ring(c, r, o, hb["ring_radius"], hit.thickness)
		CombatTypes.Shape.THRUST:
			return HitGeometry.circle_hits_capsule(c, r, o, o + d * hit.length, hit.width * 0.5)
	return false


## 結算 Boss 的一擊（範圍已確認重疊；測試也直接呼叫）。from 是攻擊者位置（決定能不能擋、往哪裡退）。
func apply_boss_hit(hit: BossHitData, from: Vector2) -> int:
	var result := player.receive_boss_hit(hit, from)
	if result != BlockResult.MISS:
		# 統計用：哪一招的哪一擊、結果如何
		emit(&"boss_hit_result", {"move": boss.move.id if boss.move != null else &"", "result": result,
			"blockable": hit.is_blockable()})
	var contact := player.pos + (from - player.pos).limit_length(12.0)
	match result:
		BlockResult.PERFECT:
			boss.on_parried(hit)
			feedback(&"perfect_parry", contact)
			emit(&"perfect_parry", {"pos": contact, "toughness": hit.toughness_damage})
		BlockResult.BLOCKED:
			boss.on_blocked(hit)
			feedback(&"normal_block", contact)  # §6：普通格擋沒有頓幀、沒有震動（表中為 0）
			emit(&"block", {"pos": contact, "posture": player.posture})
			if player.state == PlayerSim.State.POSTURE_BREAK:
				boss.on_player_posture_break()
		BlockResult.HIT:
			boss.on_hit_player(hit)
	return result


## 身體碰撞：玩家與 Boss 不重疊，兩者都留在場地內。
## 先把玩家推出 Boss 再夾回場內；如果玩家被夾在 Boss 與牆（或柱子）之間仍然重疊，改把 Boss 往外推。
func _resolve_bodies() -> void:
	var min_d := PlayerData.HURT_RADIUS + VeltharisData.HURT_RADIUS
	if boss.has_body():
		player.pos = _push_apart(player.pos, boss.pos, min_d)
	player.pos = ArenaGeometry.resolve(player.pos, PlayerData.HURT_RADIUS)
	if boss.has_body() and player.pos.distance_to(boss.pos) < min_d - 0.01:
		boss.pos = _push_apart(boss.pos, player.pos, min_d)
	boss.pos = ArenaGeometry.resolve(boss.pos, VeltharisData.HURT_RADIUS)


## 把 a 推到離 b 至少 min_d 的地方
static func _push_apart(a: Vector2, b: Vector2, min_d: float) -> Vector2:
	var d := a - b
	var dist := d.length()
	if dist >= min_d:
		return a
	var n := d / dist if dist > 0.001 else Vector2.DOWN
	return b + n * min_d
