class_name CombatTypes
extends RefCounted
## 戰鬥共用的列舉。

## combat-design §11.1
enum AttackType { LIGHT, HEAVY, UNBLOCKABLE }

## combat-design §10：命中玩家時的反應
enum HitEffect { STAGGER, KNOCKDOWN, LAUNCH }

## 判定形狀
## SECTOR：以攻擊者為圓心、朝向為中線的扇形（radius, angle_deg）
## RECT：從攻擊者往前延伸的長方形（length, width）
## CIRCLE：以攻擊者為圓心的圓（radius）
## RING：以攻擊者為圓心向外擴張的環（radius = 最大半徑, thickness）
## THRUST：從攻擊者往前延伸的膠囊，攻擊者同時前進（length = 劍長, width, lunge_distance）
enum Shape { SECTOR, RECT, CIRCLE, RING, THRUST }

## plan §4、boss-veltharis §7：起手預兆
enum Telegraph { NONE, NORMAL, DELAYED, DANGER }


static func attack_type_name(t: AttackType) -> String:
	return ["輕擊", "重擊", "不可格擋"][t]


static func hit_effect_name(e: HitEffect) -> String:
	return ["踉蹌", "倒地", "擊飛倒地"][e]
