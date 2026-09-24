class_name Frames
extends RefCounted
## 秒與物理幀的換算。
##
## 所有戰鬥判定以 60Hz 物理幀為準（CLAUDE.md 慣例）。文件中的秒數一律經過 of() 換算，
## 取整方式固定為四捨五入（roundi，0.5 遠離零）。測試 test_frames.gd 鎖定這個規則。
##
## 兩種組合方式：
## 1. 文件寫成「起點–終點」的區間（例如閃身無敵 0.02–0.16 秒）：兩個端點各自換算，
##    區間為 [of(start), of(end))，也就是 [1, 10) 共 9 幀。
## 2. 文件寫成一段接一段的時長（起手→判定→收招、連段間隔）：每段各自換算後相加。
##    例如輕攻擊第 1 段 = of(0.10) + of(0.08) + of(0.25) = 6 + 5 + 15 幀。

const FPS := 60


static func of(seconds: float) -> int:
	return roundi(seconds * FPS)


static func sec(frames: int) -> float:
	return float(frames) / FPS
