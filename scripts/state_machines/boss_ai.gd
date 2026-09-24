class_name BossAI
extends RefCounted
## Boss 的出招選擇（boss-veltharis §6）。只做決策；執行（出招、走路、懲罰）在 BossSim。
## 亂數一律用 sim.rng，同一個種子的整場戰鬥完全重現。

## 已經出過的招式群組（延遲版與普通版算同一招），用來避免同一招連續超過 2 次（§6.2 規則 4）
var history: Array[StringName] = []
## Boss 觀察到的連續普通格擋次數（§6.2 規則 3）：完美彈返、打中玩家、用出灰燼衝擊時歸零
var block_streak := 0
## 每次喘息的長度（幀），測試與統計用
var breather_log: Array[int] = []


static func band(dist: float) -> StringName:
	if dist < VeltharisData.NEAR_RANGE:
		return &"near"
	if dist < VeltharisData.MID_RANGE:
		return &"mid"
	return &"far"


## 選下一個動作：招式 id，或 &"approach_slow" / &"approach_fast"
func choose(boss: BossSim) -> StringName:
	var rng := boss.sim.rng
	var dist := boss.pos.distance_to(boss.sim.player.pos)
	var b := band(dist)
	# 規則 3：連續普通格擋 3 次後，下一招優先使用灰燼衝擊（玩家要在衝擊環範圍內才有意義）
	if block_streak >= VeltharisData.BLOCK_STREAK_FOR_IMPACT and b == &"near":
		block_streak = 0
		return VeltharisData.resolve_choice(&"ash_impact", boss.phase, rng.randf())
	var weights: Dictionary = VeltharisData.WEIGHTS[boss.phase][b]
	var options: Array[StringName] = []
	var total := 0
	for choice: StringName in weights:
		if _repeated_twice(choice):
			continue
		options.append(choice)
		total += int(weights[choice])
	var roll := rng.randi_range(1, total)
	var picked: StringName = options[options.size() - 1]
	for choice in options:
		roll -= int(weights[choice])
		if roll <= 0:
			picked = choice
			break
	if picked == &"approach_slow" or picked == &"approach_fast":
		return picked
	if picked == &"ash_impact" or picked == &"double_impact":
		block_streak = 0
	return VeltharisData.resolve_choice(picked, boss.phase, rng.randf())


## 規則 4：這個選項如果最近兩招都是它，就不能再選（選項名稱就是招式群組名；雙重衝擊算灰燼衝擊）
func _repeated_twice(choice: StringName) -> bool:
	var g := VeltharisData.group_of(choice)
	var n := history.size()
	return n >= VeltharisData.MAX_SAME_MOVE_STREAK and history[n - 1] == g and history[n - 2] == g


func record_move(move_id: StringName) -> void:
	history.append(VeltharisData.group_of(move_id))
	if history.size() > 8:
		history.pop_front()


## 規則 5：每套攻擊之後的喘息（一階段 0.8–1.4 秒、二階段 0.4–0.9 秒）
func breather_frames(boss: BossSim) -> int:
	var r: Vector2 = VeltharisData.BREATHER[boss.phase - 1]
	var f := Frames.of(boss.sim.rng.randf_range(r.x, r.y))
	breather_log.append(f)
	return f
