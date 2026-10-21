#!/usr/bin/env bash
# 把"数据体检"接进 devflow：初始化 → 建变更 → 跑门禁 → 换脏表验证真的会阻断。
#
# 依赖：devflow-kit（DEVFLOW 指向 bin/devflow），python3 + openpyxl。
# 用法：
#   DEVFLOW=../devflow-kit/bin/devflow bash examples/devflow-gate/verify.sh
#
# 这个脚本本身就是证据：它证明"接了门禁"不是一句声明，而是**脏数据会被拦下**。
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEVFLOW="${DEVFLOW:-devflow}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0; fail=0
ok()   { echo "  [OK] $*"; pass=$((pass+1)); }
bad()  { echo "  [NG] $*"; fail=$((fail+1)); }

command -v "$DEVFLOW" >/dev/null 2>&1 || { echo "找不到 devflow（设 DEVFLOW=.../bin/devflow）"; exit 2; }

echo "== 0. 准备临时项目"
cd "$WORK"
mkdir -p data scripts
cp "$HERE/devflow.json" .
cp "$HERE/scripts/data-gate.sh" "$HERE/scripts/data-should-fail.sh" scripts/
cp "$REPO/tools/audit_data.py" scripts/
chmod +x scripts/*.sh

python3 - "$REPO" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/tools")
from openpyxl import Workbook
import make_dirty_fixture
make_dirty_fixture.build("data/dirty.xlsx")
wb = Workbook(); ws = wb.active
ws.append(["订单号", "区域", "金额(元)"])
ws.append(["SO-1", "华东", 1200]); ws.append(["SO-2", "华南", 800])
wb.save("data/clean.xlsx")
PY
ok "生成 clean.xlsx / dirty.xlsx"

echo "== 1. init + doctor"
"$DEVFLOW" init --name data-delivery >/dev/null 2>&1
doc="$("$DEVFLOW" doctor 2>&1)"
if echo "$doc" | grep -q "门禁可用"; then ok "doctor：门禁可用（负向对照生效）"; else bad "doctor 未通过：$(echo "$doc" | tail -3)"; fi

echo "== 2. 建变更"
"$DEVFLOW" new --slug data-check --tier micro --title "交付数据表" >/dev/null 2>&1
ITEM="$(ls -1t .devflow/.local/items 2>/dev/null | head -1)"
[ -n "$ITEM" ] && ok "变更：$ITEM" || bad "建变更失败"

echo "== 3. 干净数据：门禁应通过"
if "$DEVFLOW" gate run "$ITEM" >/tmp/dg-pass.log 2>&1; then
  grep -q "负向对照返回 1 且输出含失败证据" /tmp/dg-pass.log && ok "通过，且负向对照被验证" || ok "通过"
else
  bad "干净数据被拦下（不应该）：$(tail -3 /tmp/dg-pass.log)"
fi

echo "== 4. 脏数据：门禁必须阻断"
cp data/dirty.xlsx data/clean.xlsx
if "$DEVFLOW" gate run "$ITEM" >/tmp/dg-block.log 2>&1; then
  bad "脏数据竟然通过了 —— 这道门禁是摆设"
else
  # CLI 只报 BLOCKED，证据在 STATUS.json 的记录里 —— 这正是 devflow「证据可核」的设计：
  # 每条结论必须带命令原文、退出码、输出尾部。
  if python3 "$HERE/check_record.py" "$ITEM" blocked; then
    ok "阻断，且记录里有 exit≠0 + FAIL 证据"
  else
    bad "退出了但记录里缺失败证据"
  fi
fi

echo "== 5. 发布前置：数据没修好，不许 released"
"$DEVFLOW" new --slug release-check --tier micro --title "发布数据" >/dev/null 2>&1
ITEM2="$(ls -1t .devflow/.local/items 2>/dev/null | head -1)"
if "$DEVFLOW" advance "$ITEM2" --to released >/tmp/dg-release.log 2>&1; then
  bad "脏数据竟然发布成功 —— release.requires 没生效"
else
  grep -qE "拒绝推进|data" /tmp/dg-release.log && ok "released 被拦住（release.requires=data 生效）" || bad "拦住了但原因不明"
fi

echo
echo "通过 $pass 项，失败 $fail 项"
[ "$fail" -eq 0 ] && echo "数据门禁接入验收通过" || echo "数据门禁接入验收失败"
[ "$fail" -eq 0 ]
