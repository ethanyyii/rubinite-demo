class_name SimTestCase
extends TestCase
## 戰鬥模擬測試的共用工具：建立 sim、組輸入、以「戰鬥幀」推進（跳過頓幀）。

var sim: CombatSim
## 持續按住的狀態（hold / release 設定）
var held := {"run": false, "block": false, "heavy": false}
var move := Vector2.ZERO
## 所有經過的事件（頓幀期間 sim.events 會被清掉，所以測試要看這份）
var event_log: Array[Dictionary] = []


func before_each() -> void:
	sim = CombatSim.new(1)
	held = {"run": false, "block": false, "heavy": false}
	move = Vector2.ZERO
	event_log.clear()


func make_input(presses: Array = []) -> InputFrame:
	var f := InputFrame.new()
	f.move = move
	f.run = held["run"]
	f.block = held["block"]
	f.heavy = held["heavy"]
	for p: StringName in presses:
		match p:
			&"attack":
				f.attack_pressed = true
			&"heavy":
				f.heavy_pressed = true
				f.heavy = true
			&"dodge":
				f.dodge_pressed = true
			&"lock":
				f.lock_pressed = true
			&"heal":
				f.heal_pressed = true
			&"block":
				f.block = true
	return f


## 推進一個物理幀（可能是頓幀）
func tick(presses: Array = []) -> void:
	if &"heavy" in presses:
		held["heavy"] = true
	sim.step(make_input(presses))
	event_log.append_array(sim.events)


## event_log 裡有沒有某種事件
func logged(type: StringName) -> bool:
	for e in event_log:
		if e["type"] == type:
			return true
	return false


## 推進 n 個戰鬥幀（頓幀不算），第一個戰鬥幀帶 presses
func advance(n: int, presses: Array = []) -> void:
	var first := true
	var target := sim.combat_frame + n
	var guard := 0
	while sim.combat_frame < target:
		tick(presses if first else [])
		first = false
		guard += 1
		if guard > n + 600:
			failures.append("advance 卡住（頓幀沒結束？）")
			return


## 按一下（下一個戰鬥幀帶這個按鍵）
func press(action: StringName) -> void:
	advance(1, [action])


func player() -> PlayerSim:
	return sim.player


func boss() -> BossSim:
	return sim.boss


## 讓玩家站在 Boss 正南方 dist（中心距）處、面向 Boss
func place_near_boss(dist: float) -> void:
	sim.boss.pos = Vector2(0, -20)
	sim.player.pos = sim.boss.pos + Vector2(0, dist)
	sim.player.facing = Vector2.UP
	sim.player.vel = Vector2.ZERO
