extends TestCase
## 程式合成的佔位音效（combat-design §12）。檢查每個音效都存在、長度合理，
## 並用過零率（明亮程度的粗略指標）確認完美彈返與普通格擋的聲音明顯不同（§6）。


func _zcr(s: PackedFloat32Array) -> float:
	var n := 0
	for i in range(1, s.size()):
		if (s[i - 1] >= 0.0) != (s[i] >= 0.0):
			n += 1
	return float(n) / s.size() * SfxSynth.RATE * 0.5  # 約略的主頻（Hz）


func _peak(s: PackedFloat32Array) -> float:
	var m := 0.0
	for v in s:
		m = maxf(m, absf(v))
	return m


func test_all_required_sounds_exist() -> void:
	# §12 列出的音效
	for n in [&"swing_light", &"swing_heavy", &"hit", &"parry", &"block", &"dodge", &"charge_ready",
			&"execution", &"boss_swing", &"danger", &"player_hurt", &"knockdown"]:
		assert_true(n in SfxSynth.NAMES, "缺少音效 %s" % n)


func test_every_sound_is_audible_and_short() -> void:
	for n: StringName in SfxSynth.NAMES:
		var w := SfxSynth.make(n)
		var s := SfxSynth.samples_of(w)
		var dur := float(s.size()) / SfxSynth.RATE
		assert_between(dur, 0.05, 1.2, "%s 長度" % n)
		assert_between(_peak(s), 0.5, 1.0, "%s 音量" % n)


func test_parry_is_bright_metal_and_block_is_dull() -> void:
	var parry := SfxSynth.samples_of(SfxSynth.make(&"parry"))
	var block := SfxSynth.samples_of(SfxSynth.make(&"block"))
	var zp := _zcr(parry)
	var zb := _zcr(block)
	assert_true(zp > 1000.0, "彈返聲夠清脆（約 %.0f Hz）" % zp)
	assert_true(zb < 700.0, "格擋聲悶（約 %.0f Hz）" % zb)
	assert_true(zp > zb * 3.0, "兩者明顯不同")


## 後半段能量 ÷ 前半段能量：持續的聲音大、短促的聲音小
func _sustain(s: PackedFloat32Array) -> float:
	var half := s.size() >> 1
	var a := 0.0
	var b := 0.0
	for i in half:
		a += s[i] * s[i]
	for i in range(half, s.size()):
		b += s[i] * s[i]
	return b / maxf(a, 0.000001)


func test_danger_cue_differs_from_parry() -> void:
	# 危險預兆是持續、帶顫音的鈴聲；彈返是短促衰減的撞擊聲
	var danger := _sustain(SfxSynth.samples_of(SfxSynth.make(&"danger")))
	var parry := _sustain(SfxSynth.samples_of(SfxSynth.make(&"parry")))
	assert_true(danger > parry * 2.0, "危險預兆音（後/前能量比 %.2f）比彈返聲（%.2f）持續得多" % [danger, parry])


func test_synthesis_is_deterministic() -> void:
	assert_eq(SfxSynth.make(&"block").data, SfxSynth.make(&"block").data)
