class_name PlayerSim
extends RefCounted
## 主角的狀態機（combat-design §3–§10）。
##
## 計時一律用 sim.combat_frame（頓幀期間暫停）。進入狀態的那一幀 state_elapsed() = 0。

enum State { IDLE, ATTACK, CHARGE, THRUST, DODGE, BLOCK, HEAL, STAGGER, LAUNCHED, DOWN, GETUP, POSTURE_BREAK, EXECUTE, DEAD }

const STATE_NAMES := ["IDLE", "ATTACK", "CHARGE", "THRUST", "DODGE", "BLOCK", "HEAL", "STAGGER",
	"LAUNCHED", "DOWN", "GETUP", "POSTURE_BREAK", "EXECUTE", "DEAD"]

## 能自由移動（走、跑、慢走）的狀態
const LOCOMOTION_STATES := [State.IDLE, State.BLOCK, State.CHARGE, State.HEAL]
## 輸入向量小於這個長度視為沒有輸入（避免極小向量把面向變成零向量）
const INPUT_EPSILON := 0.001

## 用弱參照持有 CombatSim，避免 sim ↔ 角色的循環參照造成記憶體洩漏
var sim: CombatSim:
	get:
		return _sim_ref.get_ref()
var _sim_ref: WeakRef
var pos := ArenaGeometry.PLAYER_SPAWN
var vel := Vector2.ZERO
var facing := Vector2.UP
var hp := PlayerData.MAX_HP
var posture := PlayerData.MAX_POSTURE
var heals := PlayerData.HEAL_CHARGES
var state := State.IDLE
var state_start := 0
var locked := false
## 這一幀是否在奔跑（畫面用）
var running := false

# --- 攻擊（§8） ---
## 進行中的輕攻擊段數 0..3（攻擊狀態以外是 0；接段寬限另存在 _grace_stage）
var combo_index := 0
## 進行中的攻擊資料（輕攻擊某段或重擊突刺）
var attack: PlayerAttackData
## 這一段是否已經打中（每段只打中一次）
var attack_connected := false
var charge_full := false
## 剛結束的第 1–3 段（0..2）：待機的前 12 幀內按攻擊接它的下一段（§8.1 接段寬限）；沒有時 -1。進入任何狀態都會清掉
var _grace_stage := -1

# --- 閃身（§7） ---
var dodge_dir := Vector2.DOWN
var last_dodge_start := -100000

# --- 輸入緩衝（§3）：只保留最新一次的攻擊／重擊／閃身 ---
var buffered_action := &""
var buffered_at := -100000

# --- 格擋與彈返（§6） ---
## 最後一次按下格擋的戰鬥幀、這次按下是否開了完美窗口
var block_press_frame := -100000
var block_press_perfect := false
var block_release_frame := -100000
var _block_prev := false
## 最後一次完美彈返／普通格擋的戰鬥幀（畫面用：彈返姿勢）
var last_parry_frame := -100000
var last_block_frame := -100000

# --- 架勢（§4） ---
var last_posture_damage := -100000

# --- 受擊（§10） ---
## 最後一次被打中時，從主角指向攻擊者的方向（畫面用：受擊的動畫朝攻擊來源畫，不影響判定）
var last_hit_dir := Vector2.DOWN
## 擊退／推後：方向、每幀位移、剩餘幀數
var _knock_dir := Vector2.ZERO
var _knock_step := 0.0
var _knock_left := 0
## 倒地多久（倒地 48 幀、擊飛後 36 幀）
var _down_frames := 0
## 倒地無敵延續到這一幀（不含）：起身後 0.3 秒 ★
var _invuln_until := -100000

# 幀數（Frames.of 四捨五入）
var _perfect_window := Frames.of(PlayerData.PERFECT_WINDOW)
var _rearm := Frames.of(PlayerData.REARM_TIME)
var _posture_regen_delay := Frames.of(PlayerData.POSTURE_REGEN_DELAY)
var _heal_frames := Frames.of(PlayerData.HEAL_TIME)
var _buffer_frames := Frames.of(PlayerData.INPUT_BUFFER)
var _cancel_delay := Frames.of(PlayerData.CANCEL_DELAY)
var _combo_grace := Frames.of(PlayerData.COMBO_GRACE)
var _dodge_frames := Frames.of(PlayerData.DODGE_TIME)
var _dodge_total := Frames.of(PlayerData.DODGE_TIME) + Frames.of(PlayerData.DODGE_RECOVERY)
var _dodge_inv_start := Frames.of(PlayerData.DODGE_INVULN_START)
var _dodge_inv_end := Frames.of(PlayerData.DODGE_INVULN_END)
var _dodge_interval := Frames.of(PlayerData.DODGE_INTERVAL)
var _charge_frames := Frames.of(PlayerData.CHARGE_TIME)
var _thrust_frames := Frames.of(PlayerData.THRUST_TIME)
var _thrust_stopped := false

## §5：加速 5 幀、減速 4 幀
var _accel_frames := Frames.of(PlayerData.ACCEL_TIME)
var _decel_frames := Frames.of(PlayerData.DECEL_TIME)
## 開始減速時的速度除以減速幀數：無論從多快開始，都在 4 幀內停下
var _decel_step := 0.0


func _init(owner_sim: CombatSim) -> void:
	_sim_ref = weakref(owner_sim)


## 每個戰鬥幀：鎖定 → 記錄按鍵 → 依時間結束動作 → 格擋（按住優先）→ 開始新動作（含緩衝）→ 治療
## → 本幀的移動與行為 → 架勢回復 → 鎖定距離檢查。
func tick(input: InputFrame) -> void:
	if state == State.DEAD:
		return
	if input.lock_pressed:
		_toggle_lock()
	var block_press := _track_block_edges(input)
	_record_presses(input)
	_advance_state(input)
	_try_block(input)
	if block_press and state != State.BLOCK:
		# 格擋不緩衝（§3）：不能格擋的時候按下，不會開完美窗口
		block_press_perfect = false
	_try_start_actions(input)
	if input.heal_pressed:
		_try_heal()
	_run_state_frame(input)
	_regen_posture()
	_check_lock_range()


func state_name() -> String:
	return STATE_NAMES[state]


func state_elapsed() -> int:
	return sim.combat_frame - state_start


func enter_state(s: State) -> void:
	state = s
	state_start = sim.combat_frame
	_decel_step = 0.0
	_grace_stage = -1
	if not can_run_in(s):
		running = false
	if s != State.ATTACK and s != State.THRUST:
		attack = null


## 是否無敵：閃身第 1–9 幀（§7）；倒地、起身、起身後 0.3 秒（§10 ★）。
func is_invulnerable() -> bool:
	if sim.god_mode:
		return true
	match state:
		State.DODGE:
			var e := state_elapsed()
			return e >= _dodge_inv_start and e < _dodge_inv_end
		State.LAUNCHED, State.DOWN, State.GETUP, State.EXECUTE:
			return true
	return sim.combat_frame < _invuln_until


## 能不能行動（受擊反應、崩潰、死亡中不能）
func is_in_hit_reaction() -> bool:
	return state in [State.STAGGER, State.LAUNCHED, State.DOWN, State.GETUP, State.POSTURE_BREAK, State.DEAD]


## 完美窗口是否開著：格擋中、這次按下有開窗、按下後 9 幀內（第 0–8 幀）
func is_perfect_window_open() -> bool:
	return state == State.BLOCK and block_press_perfect and sim.combat_frame - block_press_frame < _perfect_window


## 目前這一幀有效的攻擊判定；沒有時回傳空字典。由 CombatSim 做相交測試。
func attack_hitbox() -> Dictionary:
	if attack == null or attack_connected:
		return {}
	var e := state_elapsed()
	if state == State.ATTACK:
		if e >= attack.startup_frames() and e < attack.active_end_frame():
			return {"shape": &"sector", "origin": pos, "dir": facing, "radius": PlayerData.ATTACK_RADIUS,
				"arc": PlayerData.ATTACK_ARC_DEG, "attack": attack}
	elif state == State.THRUST:
		if e < _thrust_frames:
			return {"shape": &"capsule", "a": pos, "b": pos + facing * PlayerData.THRUST_REACH,
				"width": PlayerData.THRUST_WIDTH, "attack": attack}
	return {}


## CombatSim 判定命中後呼叫
func on_attack_connected() -> void:
	attack_connected = true
	if state == State.THRUST:
		_thrust_stopped = true


# --- 輸入與動作 -------------------------------------------------------------------

func _record_presses(input: InputFrame) -> void:
	var action := &""
	if input.attack_pressed:
		action = &"attack"
	if input.heavy_pressed:
		action = &"heavy"
	if input.dodge_pressed:
		action = &"dodge"
	if action != &"":
		buffered_action = action
		buffered_at = sim.combat_frame


## 依時間結束的動作：攻擊、突刺、閃身收招結束 → 待機；蓄力放開 → 突刺或取消。
func _advance_state(input: InputFrame) -> void:
	var e := state_elapsed()
	match state:
		State.ATTACK:
			if e >= attack.total_frames():
				var ended := combo_index
				combo_index = 0
				enter_state(State.IDLE)
				if ended < PlayerData.last_light_stage():
					_grace_stage = ended
		State.THRUST:
			if e >= _thrust_frames + Frames.of(attack.recovery):
				enter_state(State.IDLE)
		State.DODGE:
			if e >= _dodge_total:
				enter_state(State.IDLE)
		State.BLOCK:
			if not input.block:
				enter_state(State.IDLE)
		State.HEAL:
			if e >= _heal_frames:
				hp = mini(hp + PlayerData.HEAL_AMOUNT, PlayerData.MAX_HP)
				sim.emit(&"heal_done", {"pos": pos, "hp": hp})
				enter_state(State.IDLE)
		State.STAGGER:
			if e >= Frames.of(PlayerData.STAGGER_TIME):
				enter_state(State.IDLE)
		State.LAUNCHED:
			if e >= Frames.of(PlayerData.LAUNCH_TIME):
				_down_frames = Frames.of(PlayerData.LAUNCH_DOWN)
				enter_state(State.DOWN)
		State.DOWN:
			if e >= _down_frames:
				enter_state(State.GETUP)
		State.GETUP:
			if e >= Frames.of(PlayerData.GETUP_TIME):
				_invuln_until = sim.combat_frame + Frames.of(PlayerData.DOWN_INVULN_AFTER_GETUP)
				enter_state(State.IDLE)
		State.POSTURE_BREAK:
			if e >= Frames.of(PlayerData.POSTURE_BREAK_TIME):
				_end_posture_break()
				enter_state(State.IDLE)
		State.EXECUTE:
			if e >= Frames.of(PlayerData.EXECUTE_TIME):
				enter_state(State.IDLE)
		State.CHARGE:
			if e >= _charge_frames and not charge_full:
				charge_full = true
				sim.emit(&"charge_full", {"pos": pos})
			if not input.heavy:
				if charge_full:
					_start_thrust(input)
				else:
					sim.emit(&"charge_cancel", {"pos": pos})
					enter_state(State.IDLE)


## 執行緩衝中的動作（若這一幀允許）。緩衝在按下後 9 幀內有效（§3：動作結束前 0.15 秒內按下）。
func _try_start_actions(input: InputFrame) -> void:
	if buffered_action == &"":
		return
	if sim.combat_frame - buffered_at > _buffer_frames:
		buffered_action = &""
		return
	if not can_start(buffered_action):
		return
	var action := buffered_action
	buffered_action = &""
	match action:
		&"attack":
			_start_attack(input)
		&"heavy":
			if input.heavy:
				_start_charge()
		&"dodge":
			_start_dodge(input)


## 這一幀能不能開始某個動作（§8.3 取消規則）。
func can_start(action: StringName) -> bool:
	var e := state_elapsed()
	match action:
		&"attack":
			if state == State.IDLE or state == State.BLOCK:
				return true
			# 收招期間按攻擊接下一段，最早在 chain_frame（§8.1：四刀的節奏一樣）；第 4 段之後不能再接
			return state == State.ATTACK and attack.cancelable and combo_index < PlayerData.last_light_stage() \
				and e >= PlayerData.chain_frame(combo_index)
		&"heavy":
			return state == State.IDLE or state == State.BLOCK
		&"dodge":
			if sim.combat_frame - last_dodge_start < _dodge_interval:
				return false
			match state:
				State.IDLE, State.CHARGE, State.BLOCK:
					return true
				State.ATTACK:
					return _can_defend_in_attack(e)
	return false


## 攻擊中能不能用格擋或閃身取消（§8.3）：第 1–3 段判定結束 0.05 秒後；第 4 段只在收招後的停頓中
func _can_defend_in_attack(e: int) -> bool:
	return (attack.cancelable and e >= attack.active_end_frame() + _cancel_delay) \
		or e >= attack.recovery_end_frame()


## 是否在接段寬限中（§8.1：第 1–3 段收招結束後 0.2 秒內的待機）。
## ahead：往後看幾幀（機器人在這一幀之後才決定按鍵，按鍵落在下一幀，所以傳 1）
func in_combo_grace(ahead := 0) -> bool:
	return state == State.IDLE and _grace_stage >= 0 and state_elapsed() + ahead < _combo_grace


## 按攻擊會出第幾段（0..3）：收招中或接段寬限中接下一段，其他情況從第 1 段開始。ahead 同 in_combo_grace
func next_combo_stage(ahead := 0) -> int:
	if state == State.ATTACK and combo_index < PlayerData.last_light_stage():
		return combo_index + 1
	if in_combo_grace(ahead):
		return _grace_stage + 1
	return 0


func _start_attack(input: InputFrame) -> void:
	if sim.boss.can_be_executed(pos):
		_start_execute()
		return
	combo_index = next_combo_stage()
	attack = PlayerData.light_attacks()[combo_index]
	attack_connected = false
	vel = Vector2.ZERO
	_face_for_attack(input)
	enter_state(State.ATTACK)
	sim.emit(&"player_attack", {"stage": combo_index, "pos": pos, "dir": facing})


## §11.4 處決：失衡的 Boss 受擊圓邊緣 48px 內按攻擊，不限方向。歷時 1 秒、全程無敵，
## 突刺在 0.2 秒時命中（最大 HP 的 15%），接頓幀、震動與白色閃光。
func _start_execute() -> void:
	_clear_intent()
	vel = Vector2.ZERO
	var to := sim.boss.pos - pos
	if to.length_squared() > 0.01:
		facing = to.normalized()
	enter_state(State.EXECUTE)
	sim.boss.begin_execution()
	sim.emit(&"player_execute", {"pos": pos, "dir": facing})


func _start_charge() -> void:
	charge_full = false
	enter_state(State.CHARGE)
	sim.emit(&"charge_start", {"pos": pos})


func _start_thrust(input: InputFrame) -> void:
	attack = PlayerData.heavy_thrust()
	attack_connected = false
	_thrust_stopped = false
	vel = Vector2.ZERO
	_face_for_attack(input)
	enter_state(State.THRUST)
	sim.emit(&"player_thrust", {"pos": pos, "dir": facing})


## §7：方向依移動輸入；沒有輸入時往後閃（鎖定中為遠離目標的方向）。
func _start_dodge(input: InputFrame) -> void:
	var dir := input.move.limit_length(1.0)
	if dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		dodge_dir = dir.normalized()
		if not locked:
			facing = dodge_dir
	elif locked:
		var away := pos - sim.boss.pos
		dodge_dir = away.normalized() if away.length_squared() > 0.01 else -facing
	else:
		dodge_dir = -facing
	vel = Vector2.ZERO
	charge_full = false
	combo_index = 0
	last_dodge_start = sim.combat_frame
	enter_state(State.DODGE)
	sim.emit(&"dodge", {"pos": pos, "dir": dodge_dir})


## 攻擊開始時的朝向：鎖定中朝向目標；未鎖定時先轉向當下的移動輸入方向（§9：面向移動方向），
## 再看前方 60°、80px 內有沒有敵人，有就轉向它（輔助瞄準）。80px 以敵人受擊圓的邊緣計算。
func _face_for_attack(input: InputFrame) -> void:
	var to := sim.boss.pos - pos
	if locked and sim.boss.is_targetable() and to.length_squared() > 0.01:
		facing = to.normalized()
		return
	var stick := input.move.limit_length(1.0)
	if stick.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		facing = stick.normalized()
	if to.length_squared() < 0.01 or not sim.boss.is_targetable():
		return
	var in_range := to.length() - VeltharisData.HURT_RADIUS <= PlayerData.AIM_ASSIST_RANGE
	var in_cone := absf(facing.angle_to(to)) <= deg_to_rad(PlayerData.AIM_ASSIST_ARC_DEG) * 0.5
	if in_range and in_cone:
		facing = to.normalized()


## 本幀的移動與行為（狀態可能在這一幀剛進入，elapsed = 0）
func _run_state_frame(input: InputFrame) -> void:
	var e := state_elapsed()
	match state:
		State.ATTACK:
			var a_start := attack.startup_frames()
			var a_frames := attack.active_end_frame() - a_start
			if e >= a_start and e < attack.active_end_frame():
				pos += facing * (attack.advance / a_frames)
		State.THRUST:
			if e < _thrust_frames and not _thrust_stopped:
				pos += facing * (PlayerData.THRUST_DISTANCE / _thrust_frames)
		State.DODGE:
			if e < _dodge_frames:
				pos += dodge_dir * (PlayerData.DODGE_DISTANCE / _dodge_frames)
		State.EXECUTE:
			var hit_at := Frames.of(PlayerData.EXECUTE_HIT_TIME)
			if e < hit_at:
				# 突刺貼近 Boss（停在身體接觸處）
				var to := sim.boss.pos - pos
				var gap := to.length() - (VeltharisData.HURT_RADIUS + PlayerData.HURT_RADIUS + 2.0)
				if gap > 0.0:
					pos += to.normalized() * gap / (hit_at - e)
			elif e == hit_at:
				sim.boss.receive_execution()
		_:
			if state in LOCOMOTION_STATES:
				_tick_locomotion(input)
	_apply_knockback()


# --- 格擋（§6） -----------------------------------------------------------------------

## 追蹤格擋鍵的按下與放開。回傳這一幀是否按下。
## 按下時決定這次有沒有完美窗口：距離上次放開不到 0.3 秒（18 幀）就只算普通格擋（★ 重新開窗）。
## 頓幀期間的按下／放開會合併到頓幀後的第一幀送來。同一幀同時有放開與按下時，一律當作「先放開、再按下」
## （兩者相隔 0 幀 → 只算普通格擋），所以頓幀不能用來繞過重新開窗。
func _track_block_edges(input: InputFrame) -> bool:
	var now := sim.combat_frame
	var press := input.block_pressed or (input.block and not _block_prev)
	var release := input.block_released or (not input.block and _block_prev)
	if release:
		block_release_frame = now
	if press:
		block_press_frame = now
		block_press_perfect = now - block_release_frame >= _rearm
		if not input.block:
			block_release_frame = now  # 按下後又放開（點按）
	_block_prev = input.block
	return press


## 按住格擋、而且這一幀可以格擋時進入格擋（按住的格擋優先於緩衝中的動作）。
func _try_block(input: InputFrame) -> void:
	if not input.block or state == State.BLOCK or not can_block():
		return
	buffered_action = &""
	combo_index = 0
	charge_full = false
	if not locked:
		var stick := input.move.limit_length(1.0)
		if stick.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
			facing = stick.normalized()
	elif sim.boss.is_targetable():
		var to := sim.boss.pos - pos
		if to.length_squared() > 0.01:
			facing = to.normalized()
	enter_state(State.BLOCK)


## 這一幀能不能進入格擋（§8.3：待機、蓄力中隨時；輕攻擊第 1–3 段判定結束 0.05 秒後、第 4 段收招後的停頓）
func can_block() -> bool:
	match state:
		State.IDLE, State.CHARGE, State.BLOCK:
			return true
		State.ATTACK:
			return _can_defend_in_attack(state_elapsed())
	return false


# --- 受擊（§6、§10） --------------------------------------------------------------------

## Boss 的一擊打到玩家（範圍已確認重疊）。回傳 CombatSim.BlockResult。
func receive_boss_hit(hit: BossHitData, from: Vector2) -> int:
	if state == State.DEAD or is_invulnerable():
		return CombatSim.BlockResult.MISS
	var blocking := state == State.BLOCK and hit.is_blockable() \
		and HitGeometry.is_in_front(pos, facing, from, PlayerData.BLOCK_ARC_DEG)
	if blocking:
		if is_perfect_window_open():
			last_parry_frame = sim.combat_frame
			return CombatSim.BlockResult.PERFECT
		_normal_block(hit, from)
		return CombatSim.BlockResult.BLOCKED
	_take_hit(hit, from)
	return CombatSim.BlockResult.HIT


## 普通格擋：不扣 HP；扣架勢；被推後 8px。架勢歸零即崩潰。
func _normal_block(hit: BossHitData, from: Vector2) -> void:
	last_block_frame = sim.combat_frame
	posture = maxf(posture - hit.posture_damage, 0.0)
	last_posture_damage = sim.combat_frame
	_start_knockback(from, PlayerData.BLOCK_PUSHBACK, Frames.of(PlayerData.BLOCK_PUSHBACK_TIME))
	if posture <= 0.0:
		_clear_intent()
		vel = Vector2.ZERO
		enter_state(State.POSTURE_BREAK)
		sim.emit(&"posture_break", {"pos": pos})


## 被打中：扣 HP，依命中效果踉蹌／倒地／擊飛倒地；架勢崩潰中一律倒地（§10）。
func _take_hit(hit: BossHitData, from: Vector2) -> void:
	hp = maxi(hp - hit.damage, 0)
	var to_attacker := from - pos
	last_hit_dir = to_attacker.normalized() if to_attacker.length_squared() > 0.01 else facing
	var effect := hit.hit_effect
	if state == State.POSTURE_BREAK:
		_end_posture_break()
		if effect != CombatTypes.HitEffect.LAUNCH:
			effect = CombatTypes.HitEffect.KNOCKDOWN
	_clear_intent()
	vel = Vector2.ZERO
	if hp <= 0:
		enter_state(State.DEAD)
		sim.feedback(&"player_knockdown", pos)
		sim.emit(&"player_hit", {"pos": pos, "damage": hit.damage, "effect": CombatTypes.HitEffect.KNOCKDOWN})
		sim.emit(&"player_dead", {"pos": pos})
		return
	match effect:
		CombatTypes.HitEffect.STAGGER:
			enter_state(State.STAGGER)
			_start_knockback(from, PlayerData.STAGGER_KNOCKBACK, Frames.of(PlayerData.KNOCKBACK_TIME))
			sim.feedback(&"player_stagger", pos)
		CombatTypes.HitEffect.KNOCKDOWN:
			_down_frames = Frames.of(PlayerData.KNOCKDOWN_DOWN)
			enter_state(State.DOWN)
			_start_knockback(from, PlayerData.KNOCKDOWN_KNOCKBACK, Frames.of(PlayerData.KNOCKBACK_TIME))
			sim.feedback(&"player_knockdown", pos)
		CombatTypes.HitEffect.LAUNCH:
			enter_state(State.LAUNCHED)
			_start_knockback(from, PlayerData.LAUNCH_DISTANCE, Frames.of(PlayerData.LAUNCH_TIME))
			sim.feedback(&"player_knockdown", pos)
	sim.emit(&"player_hit", {"pos": pos, "damage": hit.damage, "effect": effect})


## 受擊、崩潰時清掉玩家的意圖：緩衝、連段、蓄力、進行中的攻擊
func _clear_intent() -> void:
	buffered_action = &""
	combo_index = 0
	charge_full = false
	attack = null


func _end_posture_break() -> void:
	posture = PlayerData.MAX_POSTURE


## 從 from 往外推 dist 像素，分 frames 幀；第一幀立刻套用（命中那一幀就開始退）
func _start_knockback(from: Vector2, dist: float, frames: int) -> void:
	var away := pos - from
	_knock_dir = away.normalized() if away.length_squared() > 0.01 else -facing
	_knock_left = maxi(frames, 1)
	_knock_step = dist / _knock_left
	_apply_knockback()


func _apply_knockback() -> void:
	if _knock_left <= 0:
		return
	pos += _knock_dir * _knock_step
	_knock_left -= 1


## §4：最後一次受到架勢傷害 1 秒後開始回復，每秒 20
func _regen_posture() -> void:
	if state == State.POSTURE_BREAK or posture >= PlayerData.MAX_POSTURE:
		return
	if sim.combat_frame - last_posture_damage >= _posture_regen_delay:
		posture = minf(posture + PlayerData.POSTURE_REGEN_PER_SEC / Frames.FPS, PlayerData.MAX_POSTURE)


# --- 治療（§4） -----------------------------------------------------------------------

## 只能在待機（含移動）中使用；開始時就消耗一次，0.9 秒結束時回 35，期間不可取消
func _try_heal() -> void:
	if state != State.IDLE or heals <= 0:
		return
	heals -= 1
	buffered_action = &""
	enter_state(State.HEAL)
	sim.emit(&"heal_start", {"pos": pos})


# --- 鎖定（§9） --------------------------------------------------------------------

func _toggle_lock() -> void:
	if locked:
		locked = false
		sim.emit(&"lock_off")
	elif sim.boss.is_targetable() and pos.distance_to(sim.boss.pos) <= PlayerData.LOCK_ACQUIRE_RANGE:
		locked = true
		sim.emit(&"lock_on")


## 目標死亡、距離超過 420px 時解除
func _check_lock_range() -> void:
	if locked and (not sim.boss.is_targetable() or pos.distance_to(sim.boss.pos) > PlayerData.LOCK_BREAK_RANGE):
		locked = false
		sim.emit(&"lock_off")


## §5 速度表。wants_run 是「按住奔跑鍵且有移動」；只有 IDLE 能跑（格擋、蓄力、治療時不能跑）。
func max_speed_for(s: State, is_locked: bool, wants_run: bool) -> float:
	match s:
		State.BLOCK:
			return PlayerData.SPEED_BLOCK
		State.CHARGE:
			return PlayerData.SPEED_CHARGE
		State.HEAL:
			return PlayerData.SPEED_HEAL
	if wants_run and can_run_in(s):
		return PlayerData.SPEED_RUN
	return PlayerData.SPEED_LOCKED if is_locked else PlayerData.SPEED_WALK


static func can_run_in(s: State) -> bool:
	return s == State.IDLE


## 這一幀是不是放開搖桿後的減速（畫面用：奔跑放開時接停步）
func is_braking() -> bool:
	return _decel_step > 0.0


## 走、跑、慢走共用的移動（LOCOMOTION_STATES）：方向立即跟隨輸入（不滑行），速率線性變化。
## - 加速：每幀 最高速 ÷ 5，從靜止 5 幀到全速。
## - 放開：以放開當下的速度 ÷ 4 為每幀減量，無論多快都 4 幀停下。
## - 速度上限變低（例如從跑進入格擋）：也用減速規則，4 幀內降到新上限，不滑行。
func _tick_locomotion(input: InputFrame) -> void:
	var dir := input.move.limit_length(1.0)
	var has_input := dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON
	running = can_run_in(state) and input.run and has_input
	var speed := vel.length()
	if not has_input:
		if _decel_step <= 0.0:
			_decel_step = speed / _decel_frames
		speed = move_toward(speed, 0.0, _decel_step)
		if speed <= 0.0:
			_decel_step = 0.0
			vel = Vector2.ZERO
		else:
			vel = vel.normalized() * speed
	else:
		_decel_step = 0.0
		var cap := max_speed_for(state, locked, running)
		var top := cap * dir.length()
		var step := cap / _accel_frames
		if speed > top:
			step = maxf(step, PlayerData.SPEED_RUN / _decel_frames)
		speed = move_toward(speed, top, step)
		vel = dir.normalized() * speed
	pos += vel / Frames.FPS
	_update_facing(dir if has_input else Vector2.ZERO)


## §9：未鎖定時面向移動方向；鎖定時面向目標（奔跑時暫時面向奔跑方向）。
func _update_facing(move_dir: Vector2) -> void:
	if state == State.BLOCK and not locked:
		return  # 未鎖定時格擋：面向固定在舉劍時的方向（側移）
	if locked and not running:
		var to := sim.boss.pos - pos
		if to.length_squared() > 0.01:
			facing = to.normalized()
	elif move_dir.length_squared() > INPUT_EPSILON * INPUT_EPSILON:
		facing = move_dir.normalized()
