# Rubinite Demo：戰鬥 Demo

俯視角 2D 像素動作遊戲的單一 Boss 戰鬥 demo。核心循環：讀招 → 劍彈返 → 削韌 → 處決。

## 目前階段與工作模式（先讀這一節）

- **第一階段（機制）已完成**：M0–M6 全部 commit，報告在 `docs/final-report.md`。戰鬥用佔位圖形運作，之後除非使用者要求，不再動機制。
- **現在是第二階段（美術），採「互動模式」**：使用者在場、逐項確認。**下面「工作流程（無人值守模式）」只適用於第一階段的機制開發，做美術時不要照它做**：不要跑啟動檢查、不要 caffeinate、不要連續自己做完。
- 做美術／動畫時：
  1. 先讀 `docs/art-progress.md`（美術進度、定案、下一步；**從這裡接續**），再讀 `docs/animation-review.md`（審查標準與過去被糾正的錯誤）和 `tools/sprite_rig/README.md`（工具與交接筆記）。
  2. 主角尺寸已定案：身體 40px（羽飾另計）、精靈格 56×56、腳底對齊點 (28, 53)；攻擊類動作用 88×72、腳底對齊點 (44, 61)。四個方向（朝下、朝右、朝上、朝左；朝左是設計圖的側面，不是朝右的鏡像）。不可再更動。
  3. **每個新動作（或一組動作）開工前，先交「動作簡報」，等使用者確認後才畫。** 簡報要有關鍵姿勢、幀數與時間、四個方向的處理、設計圖的對應小圖、量化目標、預期做不到的地方。
  4. 動畫的時間要符合戰鬥模擬的幀資料（見 `combat-design.md` 與 `progress.md`），美術配合判定，不是判定配合美術。特效（刀光、火花、殘影）由程式畫，不算在角色動畫裡。
  5. 交件依 `animation-review.md` §6：列出通過的檢查、無法驗證的項目、和文件不同的地方。預覽用精靈圖與 GIF，**不要接進遊戲**，除非使用者明講。
  6. 不用 PixelLab（要用要先報價並取得同意）。
- 只有使用者明確要求改機制時，才回到無人值守流程。

## 開工前先讀

1. `docs/plan.md`：里程碑、驗收標準、工作流程（**依這份的順序做**）
2. `docs/combat-design.md`：所有戰鬥規則與數值（標 ★ 的規則不可違反）
3. `docs/boss-veltharis.md`：Boss 招式、AI、動畫需求
4. `docs/player-knight.md`、`docs/arena.md`：主角與場地
5. `docs/art-reference/`：設計圖（Godot 已用 `.gdignore` 排除，不會被匯入）
6. `docs/animation-review.md`：製作角色動畫時的審查標準，交件前逐條自審

`docs/world-lore-draft.md` 是完整遊戲用的設定，demo 不需要讀。

## 環境

- Godot 4.7：`/Applications/Godot.app/Contents/MacOS/Godot`（以下簡寫 `godot`）
- 內部解析度 640×360，整數倍放大到 1920×1080，材質取樣為 nearest。
- 無介面測試：`godot --headless --path . -s res://tests/unit/run_tests.gd`（全部通過時結束碼為 0）
- 新增 `class_name` 之後要先跑 `godot --headless --path . --import`，否則無介面模式找不到類別。
- MCP（設定在 `.mcp.json`，含 token，**不可 commit**）：
  - `godot-ai`：**Godot 編輯器視窗必須開著**才能連線（無介面模式下外掛會停用）。用來執行遊戲、截圖、注入輸入、查詢即時節點狀態。
  - `pixellab`：像素美術生成。**第一階段禁止使用**，每次生成都會扣額度。
- 外掛會自動維護 autoload `_mcp_game_helper`，不要刪。

## 工作流程（無人值守模式，僅限第一階段的機制開發）

使用者不在場，整個流程由你自己推進。細節見 `docs/plan.md` §3、§6、§7。

- **第一次開工時，先做 `plan.md` §3 的啟動檢查**（確認 godot-ai 連得上），並在第一則訊息一行回報結果。
- **每次開始或被喚醒時，先讀 `docs/progress.md`**，從上次停下的地方繼續。
- 依序完成 M0 → M6。每個里程碑都要跑完 `plan.md` §6 的自審流程（自動測試、畫面驗證、模擬玩家、獨立審查、紀錄與 commit），通過才進下一個。
- **不要停下來等使用者，也不要為了回報進度而結束工作。** 只有在 M6 完成、`docs/final-report.md` 寫好之後才結束。
- 遇到需要使用者的事：記在 `progress.md` 的「需要使用者」，採取最保守的替代做法，繼續往下做。
- 決定性的邏輯（數值、狀態機、判定窗口）先寫測試再實作。測試放在 `tests/unit/test_*.gd`，繼承 `TestCase`。
- 手感以 `plan.md` §7 的客觀指標判斷。不要只憑感覺宣稱「手感很好」；指標沒達標就是沒達標。
- 調整任何數值都要記錄在 `docs/tuning-log.md`：改了什麼、為什麼、依據哪個指標。
- 開工時在背景執行 `caffeinate -dims`，防止電腦睡眠；結束時停掉它。
- 通過自審的里程碑在本機 commit，訊息以 `M0:`、`M1:`… 開頭。只 commit，不 push。

## 慣例

- 所有戰鬥數值放在資料裡（`Resource` 或常數表），不寫死在邏輯中；註明對應的文件章節，例如 `# combat-design §6`。
- Boss 每一擊都是一筆資料（類型、起手、間隔、傷害、架勢傷害、削韌、彈開時間、命中效果），★ 規則的測試直接掃描這些資料。
- 時間判定以物理幀（60Hz）為準；文件中的秒數換算成幀數時，取整方式要一致並寫在測試裡。
- 頓幀不可影響 UI 與輸入緩衝。
- 資料夾：`scenes/`、`scripts/combat/`、`scripts/state_machines/`、`scripts/autoload/`、`assets/`、`tests/unit/`。

## Godot 4 常見錯誤（AI 常寫成 Godot 3 語法）

| 錯誤 | 正確 |
|---|---|
| `deg2rad()` / `rad2deg()` | `deg_to_rad()` / `rad_to_deg()` |
| `KinematicBody2D` | `CharacterBody2D` |
| `move_and_slide(velocity, Vector2.UP)` | 設定 `velocity` 後呼叫 `move_and_slide()` |
| `yield(...)` | `await ...` |
| `rand_range()` | `randf_range()` / `randi_range()` |
| `set_shader_param()` | `set_shader_parameter()` |
| `BUTTON_LEFT` | `MOUSE_BUTTON_LEFT` |
| `File` / `Directory` | `FileAccess` / `DirAccess` |
| `export var` / `onready var` | `@export var` / `@onready var` |

不確定某個 API 是否存在時，先查 Godot 4.7 文件，或用 godot-ai 在編輯器裡驗證，不要憑記憶。

## 不要做的事

- 不要使用 PixelLab 或任何付費生成，除非先報價並取得使用者同意。
- 不要 commit `.mcp.json`（內含 PixelLab token），也不要 push。
- 不要跳過任何里程碑的自審流程。
- 不要違反文件中的 ★ 規則；實作上真的做不到時，記在 `progress.md` 並在最終報告說明。
- 不要下載任何素材或套件；佔位音效用程式合成。
