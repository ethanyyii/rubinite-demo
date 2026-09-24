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
		input.merge_presses(_pending)
		_pending = InputFrame.new()
	combat_frame += 1
	player.tick(input)
	boss.tick()
	_resolve_bodies()


## 產生事件。data 會被複製，type 放在 "type" 欄位。
func emit(type: StringName, data: Dictionary = {}) -> void:
	var e := data.duplicate()
	e["type"] = type
	events.append(e)


## 打擊感事件：加上頓幀，並送出帶震動資料的事件（FeedbackData）。
func feedback(event: StringName, at: Vector2) -> void:
	hitstop = maxi(hitstop, FeedbackData.hitstop_frames(event))
	emit(&"feedback", {"event": event, "pos": at, "shake": FeedbackData.shake(event),
		"shake_time": FeedbackData.shake_time(event)})


func elapsed_since(start_frame: int) -> int:
	return combat_frame - start_frame


## 身體碰撞：玩家與 Boss 不重疊，兩者都留在場地內。
func _resolve_bodies() -> void:
	if boss.has_body():
		var min_d := PlayerData.HURT_RADIUS + VeltharisData.HURT_RADIUS
		var d := player.pos - boss.pos
		var dist := d.length()
		if dist < min_d:
			var n := d / dist if dist > 0.001 else Vector2.DOWN
			player.pos = boss.pos + n * min_d
	player.pos = ArenaGeometry.resolve(player.pos, PlayerData.HURT_RADIUS)
	boss.pos = ArenaGeometry.resolve(boss.pos, VeltharisData.HURT_RADIUS)
