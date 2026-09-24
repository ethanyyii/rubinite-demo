# 進度紀錄

> 每次開始或被喚醒時先讀這份。每完成一個步驟就更新。

## 目前狀態

- M1 完成。下一步：M2 攻擊、閃身、鎖定。
- 基準 commit：`137a9ed Baseline: project skeleton before M0`。

## 架構摘要（接手時先看）

- **決定性模擬與畫面分離**：`CombatSim`（`scripts/combat/combat_sim.gd`）是純邏輯，每個物理幀 `step(InputFrame)` 一次。
  遊戲場景 `CombatArena`（`scripts/view/combat_arena.gd`）只把輸入送進去、讀狀態畫圖、依事件做特效。
  無介面測試與批次模擬直接跑 `CombatSim`，不需要畫面。
- 角色是 `PlayerSim`、`BossSim`（`scripts/state_machines/`），用弱參照指回 sim，避免循環參照洩漏。
- 碰撞與判定都自己算（`HitGeometry`、`ArenaGeometry`），不用物理引擎，保證決定性。
- 時間：全部以 60Hz 幀計，`Frames.of(秒)` 一律 `roundi`。頓幀期間 `combat_frame` 暫停，期間按的鍵延到頓幀結束後送出。
- 資料：`VeltharisData`（Boss 招式，每一擊一筆 `BossHitData`）、`PlayerData`（主角數值與攻擊表）、`FeedbackData`（頓幀與震動）。
- 除錯鍵在 `CombatArena._unhandled_input`（只在除錯建置）：F1 資訊、F2 慢動作、F3 手動出招、F4 無敵、F5 重置、F6 判定預覽開關（額外加的）。

## 工具與驗證方式

- `tests/check.sh`：零警告檢查（`tests/lint_scripts.gd`，需 `--debug`）＋全部單元測試。新增 `class_name` 後加 `--import`。
- 測試執行器 `tests/unit/run_tests.gd` 會把測試期間的腳本錯誤算成失敗（原本的執行器會把出錯的測試算通過）。
- 畫面證據：遊戲執行中用 godot-ai `game_eval` 呼叫 `get_tree().current_scene.save_screenshot("res://docs/evidence/M<n>/xx.png")`（2 倍放大）。
- godot-ai 注意事項：
  - 編輯器開著時新增 `class_name` 檔案，`filesystem_manage scan` 不一定會登記類別；要對新檔案呼叫 `filesystem_manage reimport`（paths）才會更新 `global_script_class_cache.cfg`，否則遊戲會出現「找不到類別」的解析錯誤。
  - 執行遊戲一律 `project_run(autosave=false)`，避免編輯器把記憶體中的舊場景寫回磁碟。
  - 除錯鍵要用 `input_key` 注入（`input_sequence` 走 action，不會觸發 `_unhandled_input`）。
  - 無介面 `--debug` 會啟用 stdin 除錯器，遇錯會卡住；lint 執行時要 `< /dev/null`。

## 里程碑

| 里程碑 | 狀態 | commit | 備註 |
|---|---|---|---|
| M0 基礎架構 | 完成 | f99599f | 輸入對應、資料格式、佔位圖形、除錯工具、場地、鏡頭 |
| M1 移動與鏡頭 | 完成 | M1 commit | 速度表、加減速、面向、Y 排序、邊界與柱子碰撞、鏡頭安全區 |
| M2 攻擊、閃身、鎖定 | 未開始 | | |
| M3 格擋、彈返、受擊 | 未開始 | | |
| M4 Boss 框架與第一階段 | 未開始 | | |
| M5 第二階段與完整流程 | 未開始 | | |
| M6 打擊感與調校 | 未開始 | | |

## M0 驗證紀錄

- 自動測試：`tests/check.sh` → lint 33 個腳本 0 則問題；單元測試 26 通過 0 失敗；無介面啟動 300 幀零錯誤零警告。
- 輸入對應：用 godot-ai `input_map_manage` 寫入 project.godot（鍵盤＋Xbox 手把），`test_input_map.gd` 逐一比對 §3。
- 戰鬥資料：`test_combat_data.gd` 讀取兩個階段的全部招式，逐擊比對 boss §4 數值、主角 §8.1 表、§12 打擊感表。
- 畫面：`docs/evidence/M0/`
  - `01_arena_default.png`：場地、柱子、主角、Boss、HUD。
  - `02_arena_debug_f1.png`：F1 除錯資訊（受擊圓、柱子碰撞、場地邊界、狀態與數值）。
  - `03_debug_flags_f2_f3_f4_f6.png`：F2/F3/F4/F6 開啟時右上角的標示。實際注入按鍵後 `Engine.time_scale` = 0.25、`god_mode` = true；F5 重置後幀數歸零、無敵保留。
- 遊戲執行記錄：零錯誤、零警告（game 日誌只有外掛自己的訊息）。
- 獨立審查（第 1 輪）：PASS，無阻擋性問題。已處理的次要問題：主角面向正上方時劍被身體擋住（改畫在身側）；
  check.sh 加入無介面啟動主場景的錯誤檢查；手把 device 改為 -1；補齊二階段招式、Boss 常數、AI 權重、主角常數的資料測試；
  測試數為 0 時執行器回報失敗；空資料夾加 .gitkeep；鏡頭上方活動範圍加大；CombatArena 加 class_name；
  文件未定的數值補記到 tuning-log。

## M1 驗證紀錄

- 自動測試：`tests/check.sh` → lint 36 個腳本 0 則問題；單元測試 59 通過；無介面啟動零錯誤。
  - `test_player_movement.gd`：5 幀到全速（第 4 幀 80）、4 幀停下（從走或跑都是）、跑 160、跑轉走、
    位移 = 速度積分、斜向不加速、類比輸入按比例、轉向不滑行、未鎖定面向移動方向、§5 速度表（含格擋／蓄力／治療不能跑）、
    6 個方向跑 8 秒都停在邊界上、沿邊界滑動、不穿柱子、不穿 Boss、按下同一幀就開始移動。
  - `test_arena_geometry.gd`：橢圓 720×400、推出柱子、每根柱子前後都能站、判定形狀的相交測試。
  - `test_view_occlusion.gd`：玩家在柱子後方 → 柱子半透明；在前方 → 不透明；角色與柱子在同一個 Y 排序層；
    鏡頭目標在全場任意位置都讓玩家完整留在安全區；平滑後的鏡頭在玩家往四個方向奔跑時每一幀也都在安全區內。
- 畫面驗證（godot-ai，實際按住 `move_*`／`run` 動作）：
  - 走 119 幀位移 197.5px、峰值速度 100；跑 60 幀位移 158.7px、峰值 160；放開 10 幀後速度 0。與逐幀積分一致。
  - `docs/evidence/M1/01_behind_pillar.png`：走到柱子後方，柱子畫在玩家上面且半透明（alpha 0.45）。
  - `docs/evidence/M1/02_in_front_of_pillar.png`：走到柱子前方，玩家畫在柱子上面，柱子不透明。
  - `docs/evidence/M1/03_arena_edge.png`：往西南跑 200 幀，停在橢圓邊界上（正規化值 1.0），腳底在 Boss 血條上方。
- 移動的實作選擇：方向立即跟隨輸入（不滑行），速率線性加速（5 幀到頂）；減速以開始減速時的速度 ÷ 4，
  所以無論從走或跑都在 4 幀停下；進入上限較低的狀態（格擋、蓄力、治療）時 4 幀內降到新上限。
- 獨立審查（第 1 輪）：PASS，無阻擋性問題。已處理：跑進格擋／治療會滑行 11–22 幀（改為 4 幀內降速）；
  外部寫入速度後減速量沒有重置；極小輸入會把面向變成零向量；奔跑旗標在非 IDLE 狀態殘留；
  平滑後的鏡頭會讓玩家腳底短暫進入 Boss 血條（鏡頭改在物理幀更新，平滑後再套安全區）；
  場地碰撞多做幾輪；柱子遮擋判定改用常數；M1 自訂的數值補記到 tuning-log。夾擊與頭頂預兆出畫面列入已知問題（M4）。

## 偏離文件或詮釋的地方

- 新增 F6 切換「出招判定預覽」（plan §4 說判定預覽要能用除錯開關關閉，但 §5 表格沒有對應按鍵）。
- 角色與場地碰撞不用 Godot 物理引擎，改用自寫的圓形／橢圓碰撞（決定性、可在無介面批次模擬中快速執行）。

- 手把綁定：godot-ai 寫入的手把事件 device 為 0（只認第一支手把），工具無法改成 -1；
  改在啟動時由 `InputFrame.use_all_joypads()` 統一設為 -1（有測試）。
- F3 的數字鍵選招延到 M4（Boss 招式實作時）才做；目前 F3 只是開關。

## 需要使用者

（目前沒有）

## 已知問題

- （M4 處理）玩家被 Boss 與牆夾住時，兩者可能重疊約 3px（先推玩家離開 Boss，再夾回場內）；Boss 會移動後要補「夾擊」測試。
- （M4 處理）玩家在場地最南端時，Boss 頭頂約 40px 在畫面外；危險預兆的頭頂符文可能看不到。M4 做預兆時要加畫面內的提示（例如畫面邊緣指示或把符文夾在畫面內）。
