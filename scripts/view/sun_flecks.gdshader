shader_type canvas_item;
render_mode blend_add;
// 穿過樹冠的陽光在地上晃動的小光斑（arena.md §4「斑駁光影」；2026-10-06）。畫在地面上、角色底下（不是畫面上的一層）。
// TEXTURE：陽光照到哪裡（tools/arena_art 輸出的 sun_mask.png，地面圖的四分之一大小，亮＝陽光斑點裡），
// 光斑只出現在那裡面；每個世界像素一個值（照像素畫的格子），風吹時光斑慢慢移動、變形、閃爍。
// floor_size：地面圖的像素大小；strength：最亮時加多少（第二階段由程式淡到 0）。
uniform vec2 floor_size = vec2(1600.0, 1140.0);
uniform float strength = 0.16;
uniform vec4 warm : source_color = vec4(1.0, 0.82, 0.52, 1.0);

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void fragment() {
	vec2 p = floor(UV * floor_size);
	float mask = texture(TEXTURE, UV).r;
	float t = TIME;
	vec2 drift = vec2(sin(t * 0.31), cos(t * 0.23)) * 1.6;
	float n = noise(p / vec2(11.0, 7.0) + drift) * 0.7 + noise(p / vec2(5.0, 3.5) - drift * 1.7 + t * 0.12) * 0.3;
	float fleck = step(0.7 - mask * 0.06, n);
	float edge = step(0.75 - mask * 0.06, n);
	float a = (fleck * 0.55 + edge * 0.45) * smoothstep(0.15, 0.6, mask);
	COLOR = vec4(warm.rgb * strength * a, 1.0);
}
