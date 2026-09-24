extends Control
## 全畫面閃光（處決的白色閃光，combat-design §11.4、§12）。以 delta 淡出，F2 慢動作時一起變慢。

var _color := Color(1, 1, 1, 0)
var _time := 0.0
var _left := 0.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func flash(color: Color, duration: float) -> void:
	_color = color
	_time = duration
	_left = duration


func _process(delta: float) -> void:
	_left = maxf(_left - delta, 0.0)
	queue_redraw()


func _draw() -> void:
	if _left <= 0.0:
		return
	var c := _color
	c.a *= _left / _time
	draw_rect(Rect2(Vector2.ZERO, size), c)
