class_name SfxSynth
extends RefCounted
## 程式合成的佔位音效（combat-design §12：不下載音效包）。22050Hz、16-bit 單聲道。
## 每個音效由正弦、雜訊、簡單濾波與包絡組合，雜訊用固定種子，結果是決定性的。

const RATE := 22050

## §12 需要的音效：揮劍（兩種）、命中、完美彈返的金屬撞擊聲、普通格擋的刮擦聲、閃身、蓄力完成、處決、
## Boss 大劍揮擊、危險預兆音、玩家受擊、倒地。另加治療、架勢崩潰、Boss 失衡。
const NAMES := [&"swing_light", &"swing_heavy", &"hit", &"parry", &"block", &"dodge", &"charge_ready",
	&"execution", &"boss_swing", &"danger", &"player_hurt", &"knockdown", &"heal", &"posture_break",
	&"boss_break"]


static func make(sfx_name: StringName) -> AudioStreamWAV:
	var s: PackedFloat32Array
	match sfx_name:
		&"swing_light":
			s = _whoosh(0.13, 900.0, 3200.0, 0.55, 11)
		&"swing_heavy":
			s = _whoosh(0.22, 600.0, 2200.0, 0.7, 12)
		&"boss_swing":
			s = _mix([_whoosh(0.34, 250.0, 1100.0, 0.8, 13), _tone(0.34, 90.0, 60.0, 0.25, 0.30)])
		&"hit":
			s = _mix([_tone(0.16, 190.0, 70.0, 0.9, 0.08), _noise_burst(0.05, 0.5, 0.25, 14)])
		&"parry":
			# 清脆的金屬撞擊：幾個非整數倍的泛音，快起音、長一點的衰減，開頭加一點雜訊
			s = _mix([_bell(0.6, [1250.0, 1870.0, 2730.0, 3950.0, 5200.0], [1.0, 0.7, 0.5, 0.35, 0.2],
				[0.42, 0.33, 0.24, 0.17, 0.11], 0.0, 0.0), _noise_burst(0.02, 1.0, 0.5, 15)])
		&"block":
			# 沉悶的刮擦：低通雜訊，加一點低頻，沒有明亮的泛音
			s = _mix([_filtered_noise(0.24, 0.06, 0.7, 0.14, 16), _tone(0.14, 200.0, 140.0, 0.45, 0.06)])
		&"dodge":
			s = _whoosh(0.1, 1500.0, 4000.0, 0.4, 17)
		&"charge_ready":
			s = _mix([_bell(0.18, [880.0, 1760.0], [0.6, 0.2], [0.1, 0.06], 0.0, 0.0),
				_delay(_bell(0.22, [1320.0, 2640.0], [0.7, 0.25], [0.14, 0.08], 0.0, 0.0), 0.07)])
		&"execution":
			s = _mix([_bell(0.9, [700.0, 1030.0, 1590.0, 2300.0], [1.0, 0.6, 0.4, 0.25], [0.6, 0.45, 0.3, 0.2], 0.0, 0.0),
				_tone(0.7, 70.0, 38.0, 0.9, 0.35), _noise_burst(0.06, 0.8, 0.4, 18)])
		&"danger":
			# 危險預兆：高而持續的鈴聲加顫音，和彈返聲明顯不同
			s = _bell(0.75, [1568.0, 2352.0, 3136.0], [0.8, 0.45, 0.25], [0.9, 0.7, 0.5], 7.0, 0.35)
		&"player_hurt":
			s = _mix([_square(0.16, 320.0, 150.0, 0.35), _noise_burst(0.06, 0.4, 0.3, 19)])
		&"knockdown":
			s = _mix([_tone(0.4, 85.0, 45.0, 0.9, 0.22), _filtered_noise(0.35, 0.05, 0.5, 0.2, 20)])
		&"heal":
			s = _mix([_bell(0.5, [660.0, 990.0], [0.4, 0.25], [0.35, 0.3], 5.0, 0.2),
				_delay(_bell(0.4, [880.0, 1320.0], [0.35, 0.2], [0.3, 0.25], 5.0, 0.2), 0.12)])
		&"posture_break":
			s = _mix([_bell(0.45, [520.0, 780.0, 1170.0], [0.7, 0.4, 0.25], [0.25, 0.2, 0.15], 0.0, 0.0),
				_square(0.3, 200.0, 90.0, 0.25)])
		&"boss_break":
			s = _mix([_tone(0.6, 60.0, 35.0, 0.9, 0.3), _filtered_noise(0.5, 0.08, 0.7, 0.25, 21),
				_bell(0.5, [400.0, 610.0], [0.4, 0.3], [0.3, 0.25], 0.0, 0.0)])
		_:
			push_error("未知的音效 %s" % sfx_name)
			s = PackedFloat32Array([0.0])
	return _to_stream(_normalize(s, 0.85))


static func _n(duration: float) -> int:
	return maxi(int(duration * RATE), 1)


## 起音 attack 秒、之後以 decay 秒為時間常數指數衰減
static func _env(i: int, attack: float, decay: float) -> float:
	var t := float(i) / RATE
	var a := clampf(t / maxf(attack, 0.0001), 0.0, 1.0)
	return a * exp(-t / maxf(decay, 0.0001))


## 正弦滑音（頻率從 f0 指數滑到 f1）
static func _tone(duration: float, f0: float, f1: float, amp: float, decay: float) -> PackedFloat32Array:
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	var phase := 0.0
	for i in n:
		var k := float(i) / n
		var f := f0 * pow(f1 / f0, k)
		phase += TAU * f / RATE
		out[i] = sin(phase) * amp * _env(i, 0.003, decay)
	return out


static func _square(duration: float, f0: float, f1: float, amp: float) -> PackedFloat32Array:
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	var phase := 0.0
	for i in n:
		var f := lerpf(f0, f1, float(i) / n)
		phase += TAU * f / RATE
		out[i] = (1.0 if sin(phase) >= 0.0 else -1.0) * amp * _env(i, 0.004, duration * 0.4)
	return out


## 鐘聲／金屬：多個泛音，各自衰減；可加顫音（tremolo_hz、深度）
static func _bell(duration: float, freqs: Array, amps: Array, decays: Array, tremolo_hz: float, tremolo_depth: float) -> PackedFloat32Array:
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	for i in n:
		var t := float(i) / RATE
		var v := 0.0
		for j in freqs.size():
			v += sin(TAU * float(freqs[j]) * t) * float(amps[j]) * _env(i, 0.001, float(decays[j]))
		if tremolo_hz > 0.0:
			v *= 1.0 - tremolo_depth * (0.5 + 0.5 * sin(TAU * tremolo_hz * t))
		out[i] = v
	return out


static func _noise_burst(duration: float, amp: float, decay_ratio: float, seed_value: int) -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	for i in n:
		out[i] = rng.randf_range(-1.0, 1.0) * amp * _env(i, 0.001, duration * decay_ratio)
	return out


## 二階低通濾波的雜訊（兩個一階串接；alpha 越小越悶）
static func _filtered_noise(duration: float, alpha: float, amp: float, decay: float, seed_value: int) -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	var y := 0.0
	var y2 := 0.0
	for i in n:
		y += alpha * (rng.randf_range(-1.0, 1.0) - y)
		y2 += alpha * (y - y2)
		out[i] = y2 * amp * 6.0 * _env(i, 0.004, decay)
	return out


## 揮劍的風聲：雜訊通過截止頻率先升後降的低通，鐘形包絡
static func _whoosh(duration: float, f_low: float, f_high: float, amp: float, seed_value: int) -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var n := _n(duration)
	var out := PackedFloat32Array()
	out.resize(n)
	var y := 0.0
	var y2 := 0.0
	for i in n:
		var k := float(i) / n
		var bell := sin(PI * k)
		var fc := lerpf(f_low, f_high, bell)
		var alpha := 1.0 - exp(-TAU * fc / RATE)
		var x := rng.randf_range(-1.0, 1.0)
		y += alpha * (x - y)
		y2 += alpha * (y - y2)
		out[i] = (y - y2 * 0.6) * amp * 2.5 * bell * bell
	return out


static func _delay(s: PackedFloat32Array, seconds: float) -> PackedFloat32Array:
	var pad := PackedFloat32Array()
	pad.resize(_n(seconds))
	pad.append_array(s)
	return pad


static func _mix(parts: Array) -> PackedFloat32Array:
	var n := 0
	for p: PackedFloat32Array in parts:
		n = maxi(n, p.size())
	var out := PackedFloat32Array()
	out.resize(n)
	for p: PackedFloat32Array in parts:
		for i in p.size():
			out[i] += p[i]
	return out


static func _normalize(s: PackedFloat32Array, peak: float) -> PackedFloat32Array:
	var m := 0.0
	for v in s:
		m = maxf(m, absf(v))
	if m <= 0.0:
		return s
	var k := peak / m
	var out := PackedFloat32Array()
	out.resize(s.size())
	for i in s.size():
		out[i] = s[i] * k
	return out


static func _to_stream(s: PackedFloat32Array) -> AudioStreamWAV:
	var data := PackedByteArray()
	data.resize(s.size() * 2)
	for i in s.size():
		data.encode_s16(i * 2, int(clampf(s[i], -1.0, 1.0) * 32767.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	return w


## 取出樣本（測試用）
static func samples_of(w: AudioStreamWAV) -> PackedFloat32Array:
	var n := w.data.size() >> 1
	var out := PackedFloat32Array()
	out.resize(n)
	for i in n:
		out[i] = w.data.decode_s16(i * 2) / 32767.0
	return out
