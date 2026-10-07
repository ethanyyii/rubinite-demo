shader_type canvas_item;
// 場地外圈的植物（蕨類、長草、灌木）隨風擺動（2026-10-06）：每一列整數像素平移，越靠上移越多、根部不動，
// 不旋轉、不重新取樣（像素畫的細線不會變粗變細）。amp：頂端最多移幾 px；foot_v、top_v：圖裡根部那一列、
// 植物最高那一列的 UV.y；phase：每一叢不同（照世界座標給，風像一陣一陣吹過去）。
uniform float amp = 1.0;
uniform float foot_v = 0.9;
uniform float top_v = 0.3;
uniform float phase = 0.0;
uniform float speed = 1.4;
// 節點的 modulate（第二階段變暗、被角色擋住時半透明）：fragment 裡的 COLOR 已經乘過一次圖的顏色，所以從 vertex 帶過來
varying vec4 tint;

void vertex() {
	tint = COLOR;
}

void fragment() {
	vec2 px = 1.0 / vec2(textureSize(TEXTURE, 0));
	float h = clamp((foot_v - UV.y) / max(foot_v - top_v, 0.01), 0.0, 1.0);
	float gust = (sin(TIME * speed + phase) + 0.45 * sin(TIME * speed * 2.3 + phase * 1.7)) / 1.45;
	float shift = round(gust * amp * h * h);
	COLOR = texture(TEXTURE, UV - vec2(shift * px.x, 0.0)) * tint;
}
