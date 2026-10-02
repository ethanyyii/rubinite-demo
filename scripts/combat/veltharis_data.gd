class_name VeltharisData
extends RefCounted
## Boss 維爾薩里斯的全部數值與招式資料（boss-veltharis.md）。
## 調整任何數值都要記在 docs/tuning-log.md。

const AT := CombatTypes.AttackType
const FX := CombatTypes.HitEffect
const SH := CombatTypes.Shape

# boss-veltharis §2。體型、距離（2026-09-30 使用者決定，tuning-log）：Boss 放大到 160px（主角 4 倍）、
# 大劍加長（劍首到下巴、握在握柄上段），攻擊範圍照劍實際揮到的距離放大；場地放大 1.5 倍（arena.md）
const MAX_HP := 1560  # tuning-log：文件 1200
const HURT_RADIUS := 35.0
const HEIGHT := 160.0
## 移動速度維持原值：主角的速度沒變，Boss 跟著放大會追得上奔跑（160），喘息時跑不出治療懲罰範圍（審查指出）；
## 大隻的 Boss 走得慢也更有份量
const WALK_SPEED := 60.0
const FAST_SPEED := 120.0
## 突刺的劍長（§4.4）
const SWORD_REACH := 150.0
## §4.1、§4.2、§4.5 橫掃、反手橫斬、上挑的扇形半徑（雙手往前伸直劍尖 149px，加上前傾、踏步）
const SWEEP_RADIUS := 155.0
## §4.5 快斬連段兩刀單手快斬的扇形半徑（2026-10-02 使用者：單手伸直、腰彎下去，劍尖揮到 168–171px，「範圍放大吧」）
const QUICK_SWEEP_RADIUS := 165.0
## §4.3 下劈的直線
const CLEAVE_LENGTH := 165.0
const CLEAVE_WIDTH := 53.0
## §4.4 突刺的寬度與突進距離
const THRUST_WIDTH := 40.0
const LUNGE_DISTANCE := 160.0
## §4.2 雙斬（及三斬）第二刀：左腳直接往前踏、右腳不收回，Boss 揮兩刀前進一步（2026-10-01 使用者：「這樣的
## 代價是 boss 揮兩劍會前進一點，我接受，遊戲裡也要改」）。距離 = 第一刀右腳踏出的距離（動畫 tools/boss_rig
## attacks.RF_QUICK）：踏完後右腳正好在 Boss 的位置上、左腳踏在前面，和第一刀左右對調。
## 命中前 0.2 秒內（方向已鎖定）踏完，判定期間不動。tuning-log 2026-10-01
const TWIN_STEP_DISTANCE := 28.0
const TWIN_STEP_TIME := 0.2
## §4.6 灰燼衝擊的環
const RING_RADIUS := 185.0
const RING_THICKNESS := 21.0
## §5.1 灰燼迴旋的半徑（手臂伸直、雙手）
const SPIN_RADIUS := 165.0
## §5.2 墜王之躍的落地半徑
const LEAP_RADIUS := 80.0
## 近距離招式起手時往前踏到離主角多遠停（文件未定）；下劈起手時的快步速度（文件未定）
const STEP_STOP_DISTANCE := 80.0
const CLEAVE_STEP_SPEED := 120.0

# combat-design §11.2–11.5
const MAX_TOUGHNESS := 70.0  # tuning-log：文件 100
const TOUGHNESS_REGEN_DELAY := 2.6  # tuning-log：文件 2.0
## 每秒回復 = BASE × (FLOOR + (1 - FLOOR) × 剩餘 HP 比例)
const TOUGHNESS_REGEN_BASE := 7.0  # tuning-log：文件 10
const TOUGHNESS_REGEN_FLOOR := 0.3
const SHORT_STAGGER_TIME := 0.3
const SHORT_STAGGER_COOLDOWN := 3.0
const BREAK_TIME := 3.0
const EXECUTE_DAMAGE_RATIO := 0.105  # tuning-log：文件 0.15
const RISE_TIME := 1.0
const PHASE2_HP_RATIO := 0.5
## combat-design §6：完美彈返的削韌（輕擊在連段中間 / 其他：輕擊最後一擊、重擊）
const PARRY_TOUGHNESS_LIGHT_MID := 15  # tuning-log：文件 12
const PARRY_TOUGHNESS := 26  # tuning-log：文件 20
## boss-veltharis §4 每一擊的傷害 × 這個倍率（無條件捨去，保證每一擊都在文件值的 +30% 以內）
const DAMAGE_SCALE := 1.3  # tuning-log：文件 1.0
const TRANSITION_TIME := 1.5

# boss-veltharis §6
const NEAR_RANGE := 165.0
const MID_RANGE := 290.0
const BREATHER := [Vector2(0.8, 1.4), Vector2(0.4, 0.9)]  # [一階段, 二階段]（最短, 最長）
const PUNISH_REACTION := 0.1  # boss-veltharis §4.4：AI 反應 0.1 秒
const HEAL_PUNISH_RANGE := 345.0
const HEAL_PUNISH_CHANCE := 0.7
const BLOCK_STREAK_FOR_IMPACT := 3
const MAX_SAME_MOVE_STREAK := 2
## 緩步逼近／快步逼近一次最多走多久（文件未定）
const APPROACH_MAX_TIME := 1.2
## §5：第二階段所有既有招式的收招縮短 25%
const PHASE2_RECOVERY_SCALE := 0.75
## §4.3、§4.5、§5：隨機版本的比例
const DELAYED_CHANCE := 0.4
const QUICK_TWO_HIT_CHANCE := 0.4

## boss-veltharis §6.1：[階段][距離] → { 選項: 權重 }
## 選項是招式群組或移動；群組再依比例選版本（見 resolve_choice）。
const WEIGHTS := {
	1: {
		&"near": {&"royal_sweep": 20, &"twin_slash": 20, &"oath_cleave": 20, &"quick_combo": 25, &"ash_impact": 15},
		&"mid": {&"judgment_thrust": 45, &"oath_cleave": 20, &"approach_slow": 35},
		&"far": {&"approach_fast": 100},
	},
	2: {
		&"near": {&"royal_sweep": 10, &"triple_slash": 20, &"oath_cleave": 15, &"quick_combo": 20, &"ash_spin": 20, &"double_impact": 15},
		&"mid": {&"judgment_thrust": 45, &"kings_leap": 25, &"approach_slow": 30},
		&"far": {&"kings_leap": 60, &"approach_fast": 40},
	},
}

static var _cache := {}


## 某階段所有招式（含版本），id → BossMoveData。
static func moves(phase: int) -> Dictionary:
	if not _cache.has(phase):
		_cache[phase] = _build(phase)
	return _cache[phase]


static func move(phase: int, id: StringName) -> BossMoveData:
	return moves(phase).get(id)


## 把 AI 選到的群組換成具體招式 id。
static func resolve_choice(choice: StringName, phase: int, roll: float) -> StringName:
	match choice:
		&"oath_cleave":
			return &"oath_cleave_delayed" if roll < DELAYED_CHANCE else &"oath_cleave"
		&"triple_slash":
			return &"triple_slash_delayed" if roll < DELAYED_CHANCE else &"triple_slash"
		&"quick_combo":
			return &"quick_combo_2" if roll < QUICK_TWO_HIT_CHANCE else &"quick_combo_3"
		&"ash_impact":
			return &"double_impact" if phase == 2 else &"ash_impact"
	return choice


## 除錯 F3：數字鍵（1–9，0 = 10）對應的招式；該階段沒有這一招時回傳空字串
static func move_for_key(phase: int, key: int) -> StringName:
	for id: StringName in moves(phase):
		var m: BossMoveData = moves(phase)[id]
		if m.debug_key == key:
			return id
	return &""


static func group_of(move_id: StringName) -> StringName:
	match move_id:
		&"oath_cleave", &"oath_cleave_delayed":
			return &"oath_cleave"
		&"triple_slash", &"triple_slash_delayed":
			return &"triple_slash"
		&"quick_combo_2", &"quick_combo_3":
			return &"quick_combo"
		&"ash_impact", &"double_impact":
			return &"ash_impact"
	return move_id


static func _hit(d: Dictionary) -> BossHitData:
	var h := BossHitData.new()
	for k: String in d:
		assert(k in h, "BossHitData 沒有欄位 %s" % k)
		h.set(k, d[k])
	h.damage = floori(h.damage * DAMAGE_SCALE + 0.000001)
	return h


static func _move(id: StringName, display: String, hits: Array[BossHitData], recovery: float, extra := {}) -> BossMoveData:
	var m := BossMoveData.new()
	m.id = id
	m.display_name = display
	m.hits = hits
	m.recovery = recovery
	for k: String in extra:
		assert(k in m, "BossMoveData 沒有欄位 %s" % k)
		m.set(k, extra[k])
	return m


# --- 共用的單擊定義 -----------------------------------------------------------

## §4.1 王權橫掃：起手 0.8 → 判定 0.15；前方 150° 扇形，半徑 SWEEP_RADIUS
static func _sweep_hit() -> BossHitData:
	return _hit({"attack_type": AT.HEAVY, "interval": 0.8, "active": 0.15, "damage": 28,
		"posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS, "bounce_time": 1.2, "hit_effect": FX.LAUNCH,
		"shape": SH.SECTOR, "radius": SWEEP_RADIUS, "angle_deg": 150.0, "anim": &"C1"})


## §4.2 雙斬第一擊（判定時間文件未定，取 0.1 秒；範圍沿用橫斬的扇形）
static func _twin_first() -> BossHitData:
	return _hit({"attack_type": AT.HEAVY, "interval": 0.8, "active": 0.1, "damage": 26,
		"posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS, "bounce_time": 0.0, "hit_effect": FX.KNOCKDOWN,
		"shape": SH.SECTOR, "radius": SWEEP_RADIUS, "angle_deg": 150.0, "anim": &"C1"})


## §4.2 雙斬第二擊：第一擊之後 0.9 秒；命中前左腳往前踏 TWIN_STEP_DISTANCE
static func _twin_second(is_last: bool) -> BossHitData:
	return _hit({"attack_type": AT.HEAVY, "interval": 0.9, "active": 0.1, "damage": 28,
		"posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS, "bounce_time": 1.2 if is_last else 0.0,
		"hit_effect": FX.LAUNCH, "shape": SH.SECTOR, "radius": SWEEP_RADIUS, "angle_deg": 150.0, "anim": &"C2",
		"step_distance": TWIN_STEP_DISTANCE, "step_time": TWIN_STEP_TIME})


## §4.3 墜誓下劈：起手 1.0 → 判定 0.1；前方直線 CLEAVE_LENGTH、寬 CLEAVE_WIDTH。
## 延遲版：舉到最高點（0.8 秒）停住 0.6 秒，總起手 1.6 秒。
static func _cleave_hit(interval: float, delayed: bool) -> BossHitData:
	return _hit({"attack_type": AT.HEAVY, "interval": interval + (0.6 if delayed else 0.0), "active": 0.1,
		"damage": 32, "posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS, "bounce_time": 1.2,
		"hit_effect": FX.KNOCKDOWN, "shape": SH.RECT, "length": CLEAVE_LENGTH, "width": CLEAVE_WIDTH,
		"delay_hold": 0.6 if delayed else 0.0, "hold_start": 0.8 if delayed else 0.0, "anim": &"C3"})


## §4.6 灰燼衝擊：總起手 1.1 秒（最後 0.6 秒危險預兆）；環 0.2 秒內擴張到 RING_RADIUS，厚 RING_THICKNESS
static func _impact_ring(interval: float) -> BossHitData:
	return _hit({"attack_type": AT.UNBLOCKABLE, "interval": interval, "active": 0.2, "damage": 35,
		"posture_damage": 0, "toughness_damage": 0, "bounce_time": 0.0, "hit_effect": FX.LAUNCH,
		"shape": SH.RING, "radius": RING_RADIUS, "thickness": RING_THICKNESS, "danger_time": 0.6, "anim": &"C3"})


## §4.5 快斬連段的輕擊（判定時間文件未定，取 0.1 秒）
static func _quick_light(interval: float, anim: StringName, is_last: bool) -> BossHitData:
	return _hit({"attack_type": AT.LIGHT, "interval": interval, "active": 0.1, "damage": 15,
		"posture_damage": 20, "toughness_damage": PARRY_TOUGHNESS if is_last else PARRY_TOUGHNESS_LIGHT_MID, "bounce_time": 0.8 if is_last else 0.0,
		"hit_effect": FX.STAGGER, "shape": SH.SECTOR, "radius": QUICK_SWEEP_RADIUS, "angle_deg": 150.0, "anim": anim})


static func _build(phase: int) -> Dictionary:
	var rec := 1.0 if phase == 1 else PHASE2_RECOVERY_SCALE
	var out := {}
	var near_step := {"startup_advance_speed": WALK_SPEED, "advance_stop_distance": STEP_STOP_DISTANCE}

	# §4.1 王權橫掃（單發重擊）
	out[&"royal_sweep"] = _move(&"royal_sweep", "王權橫掃", [_sweep_hit()], 0.9 * rec,
		near_step.merged({"debug_key": 1}))

	# §4.3 墜誓下劈（近到中距離使用：起手期間快步逼近，文件未定速度，取 CLEAVE_STEP_SPEED）
	var cleave_step := {"startup_advance_speed": CLEAVE_STEP_SPEED, "advance_stop_distance": STEP_STOP_DISTANCE}
	out[&"oath_cleave"] = _move(&"oath_cleave", "墜誓下劈", [_cleave_hit(1.0, false)], 1.2 * rec,
		cleave_step.merged({"debug_key": 3}))
	out[&"oath_cleave_delayed"] = _move(&"oath_cleave_delayed", "墜誓下劈（延遲）", [_cleave_hit(1.0, true)], 1.2 * rec,
		cleave_step.merged({"debug_key": 4}))

	# §4.4 裁決突刺（懲罰技）：起手 0.6 → 突進 LUNGE_DISTANCE / 0.2 秒，整段判定 → 收招 0.8
	out[&"judgment_thrust"] = _move(&"judgment_thrust", "裁決突刺", [_hit({"attack_type": AT.HEAVY,
		"interval": 0.6, "active": 0.2, "damage": 26, "posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS,
		"bounce_time": 1.2, "hit_effect": FX.KNOCKDOWN, "shape": SH.THRUST, "length": SWORD_REACH,
		"width": THRUST_WIDTH, "lunge_distance": LUNGE_DISTANCE, "anim": &"C4"})], 0.8 * rec, {"is_punish": true, "debug_key": 5})

	# §4.5 快斬連段：三連 60%、二連 40%。間隔 0.4 / 0.6 / 0.8，收招 0.9
	out[&"quick_combo_3"] = _move(&"quick_combo_3", "快斬連段（三連）", [
		_quick_light(0.4, &"C2", false),
		_quick_light(0.6, &"C1", false),
		_hit({"attack_type": AT.HEAVY, "interval": 0.8, "active": 0.1, "damage": 26, "posture_damage": 35,
			"toughness_damage": PARRY_TOUGHNESS, "bounce_time": 1.2, "hit_effect": FX.LAUNCH, "shape": SH.SECTOR,
			"radius": SWEEP_RADIUS, "angle_deg": 120.0, "anim": &"C5"}),
	], 0.9 * rec, near_step.merged({"debug_key": 6}))
	out[&"quick_combo_2"] = _move(&"quick_combo_2", "快斬連段（二連）", [
		_quick_light(0.4, &"C2", false),
		_quick_light(0.6, &"C1", true),
	], 0.9 * rec, near_step.merged({"debug_key": 7}))

	if phase == 1:
		# §4.2 雙斬
		out[&"twin_slash"] = _move(&"twin_slash", "雙斬", [_twin_first(), _twin_second(true)], 1.0,
			near_step.merged({"debug_key": 2}))
		# §4.6 灰燼衝擊
		out[&"ash_impact"] = _move(&"ash_impact", "灰燼衝擊", [_impact_ring(1.1)], 1.4, {"debug_key": 8})
	else:
		# §5 三斬：C1 → C2 → C3 下劈（與第二擊間隔 1.0 秒，可能是延遲版）。
		# 最後一擊是下劈，收招沿用下劈 1.2 秒 × 0.75。
		out[&"triple_slash"] = _move(&"triple_slash", "三斬", [_twin_first(), _twin_second(false),
			_cleave_hit(1.0, false)], 1.2 * rec, near_step.merged({"debug_key": 2}))
		out[&"triple_slash_delayed"] = _move(&"triple_slash_delayed", "三斬（延遲）", [_twin_first(),
			_twin_second(false), _cleave_hit(1.0, true)], 1.2 * rec, near_step)
		# §5 雙重衝擊：第一個環之後 0.9 秒再擴張第二個環；兩個環都有 0.6 秒危險預兆
		out[&"double_impact"] = _move(&"double_impact", "雙重衝擊", [_impact_ring(1.1), _impact_ring(0.9)],
			1.4 * rec, {"debug_key": 8})
		# §5.1 灰燼迴旋（新招，文件列出的收招 1.2 秒即為二階段數值，不再縮短）
		out[&"ash_spin"] = _move(&"ash_spin", "灰燼迴旋", [
			_hit({"attack_type": AT.HEAVY, "interval": 0.9, "active": 0.1, "damage": 24, "posture_damage": 35,
				"toughness_damage": PARRY_TOUGHNESS, "bounce_time": 0.0, "hit_effect": FX.LAUNCH, "shape": SH.CIRCLE,
				"radius": SPIN_RADIUS, "anim": &"C6"}),
			_hit({"attack_type": AT.HEAVY, "interval": 0.7, "active": 0.1, "damage": 24, "posture_damage": 35,
				"toughness_damage": PARRY_TOUGHNESS, "bounce_time": 1.2, "hit_effect": FX.LAUNCH, "shape": SH.CIRCLE,
				"radius": SPIN_RADIUS, "anim": &"C6"}),
		], 1.2, near_step.merged({"debug_key": 9}))
		# §5.2 墜王之躍：起手 0.7 → 騰空 0.8（落地前 0.3 秒鎖定落點）→ 落地半徑 LEAP_RADIUS → 收招 1.0
		out[&"kings_leap"] = _move(&"kings_leap", "墜王之躍", [_hit({"attack_type": AT.HEAVY,
			"interval": 1.5, "active": 0.1, "damage": 30, "posture_damage": 35, "toughness_damage": PARRY_TOUGHNESS,
			"bounce_time": 1.2, "hit_effect": FX.LAUNCH, "shape": SH.CIRCLE, "radius": LEAP_RADIUS,
			"lock_before": 0.3, "anim": &"C7"})], 1.0, {"airborne_start": 0.7, "debug_key": 10})
	return out
