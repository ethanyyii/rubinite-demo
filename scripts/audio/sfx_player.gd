extends Node
## 播放合成音效：啟動時合成全部音效，之後用一組 AudioStreamPlayer 輪流播放。

const VOICES := 10

var _streams := {}
var _players: Array[AudioStreamPlayer] = []
var _next := 0
## 最近播放的音效名稱（驗證用）
var history: Array[StringName] = []


func _ready() -> void:
	for n: StringName in SfxSynth.NAMES:
		_streams[n] = SfxSynth.make(n)
	for i in VOICES:
		var p := AudioStreamPlayer.new()
		p.name = "Voice%d" % i
		add_child(p)
		_players.append(p)


func has_sound(sfx_name: StringName) -> bool:
	return _streams.has(sfx_name)


func play(sfx_name: StringName, volume_db: float = 0.0, pitch: float = 1.0) -> void:
	if not _streams.has(sfx_name):
		push_error("沒有這個音效：%s" % sfx_name)
		return
	history.append(sfx_name)
	if history.size() > 32:
		history.pop_front()
	var p := _players[_next]
	_next = (_next + 1) % _players.size()
	p.stream = _streams[sfx_name]
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.play()
