#!/bin/zsh
# 自審第 1 步（plan §6）：零警告檢查＋全部單元測試。任一失敗時結束碼非 0。
# 用法：tests/check.sh [--import]   （新增 class_name 後加 --import）
set -u
cd "$(dirname "$0")/.."
GODOT=${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}

if [[ "${1:-}" == "--import" ]]; then
	$GODOT --headless --path . --import > /dev/null 2>&1
fi

echo "== lint（零警告） =="
$GODOT --headless --debug --path . -s res://tests/lint_scripts.gd < /dev/null 2>&1 | grep -E "^(WARNING|ERROR) |^lint:"
lint=${pipestatus[1]}

echo "== 單元測試 =="
$GODOT --headless --path . -s res://tests/unit/run_tests.gd 2>&1 | grep -vE "^Godot Engine|^\[godot_ai|^$"
tests=${pipestatus[1]}

echo "== 無介面啟動主場景 300 幀（零錯誤、零警告） =="
boot_out=$($GODOT --headless --path . --quit-after 300 2>&1)
boot_issues=$(echo "$boot_out" | grep -E "ERROR|WARNING" | grep -v "addons/godot_ai")
if [[ -n "$boot_issues" ]]; then
	echo "$boot_issues"
	boot=1
else
	echo "啟動正常"
	boot=0
fi

if [[ $lint -ne 0 || $tests -ne 0 || $boot -ne 0 ]]; then
	echo "CHECK FAILED (lint=$lint, tests=$tests, boot=$boot)"
	exit 1
fi
echo "CHECK OK"
