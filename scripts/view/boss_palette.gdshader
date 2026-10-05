shader_type canvas_item;
// Boss 的精靈圖（tools/boss_rig/export_game.py）：每個像素存的是調色盤索引（0＝透明），這裡查調色盤上色。
// 打包後的圖只有 8 bits 一個像素（Boss 只用 48 色），顯示卡記憶體是彩色圖的四分之一。
// mix_color / mix_amount：受擊閃白；darken：失衡時身上的紅火暗下；alpha：死亡後化為灰燼消散。
uniform sampler2D palette : filter_nearest;
uniform vec4 mix_color : source_color = vec4(1.0);
uniform float mix_amount = 0.0;
uniform float darken = 0.0;
uniform float alpha = 1.0;

void fragment() {
	float i = texture(TEXTURE, UV).r * 255.0;
	if (i < 0.5) {
		discard;
	}
	vec4 c = texelFetch(palette, ivec2(int(i + 0.5), 0), 0);
	c.rgb = mix(c.rgb, mix_color.rgb, mix_amount);
	c.rgb *= 1.0 - darken;
	COLOR = vec4(c.rgb, c.a * alpha);
}
