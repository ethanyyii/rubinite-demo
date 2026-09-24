extends Node2D
## 地面上的判定預覽（plan §4：出招時用半透明色塊預覽攻擊範圍，F6 關閉）。
## 畫的是 sim 裡實際的判定形狀，不是特效。畫在地面之上、角色之下。

var arena: CombatArena


func setup(owner_arena: CombatArena) -> void:
	arena = owner_arena
	z_index = -10


func _process(_delta: float) -> void:
	visible = arena.attack_preview
	if visible:
		queue_redraw()


func _draw() -> void:
	var hb := arena.sim.player.attack_hitbox()
	if not hb.is_empty():
		HitboxDraw.draw_player_hitbox(self, hb, Color(0.4, 0.65, 1.0, 0.28), Color(0.6, 0.8, 1.0, 0.7))
