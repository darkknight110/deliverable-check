#!/usr/bin/env bash
# 验证"一条命令接好"：devflow init --with-preflight 之后，数据没体检就发不出去。
#
# 依赖：devflow-kit ≥ 1.28.0（DEVFLOW 指向 bin/devflow）、deliverable-check（PREFLIGHT_HOME）。
# 用法：
#   DEVFLOW=../devflow-kit/bin/devflow PREFLIGHT_HOME=.. bash examples/devflow-gate/verify-init.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEVFLOW="${DEVFLOW:-devflow}"
export PREFLIGHT_HOME="${PREFLIGHT_HOME:-$REPO}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass=0; fail=0
ok()  { echo "  [OK] $*"; pass=$((pass+1)); }
bad() { echo "  [NG] $*"; fail=$((fail+1)); }

echo "== 0. 空项目 + 一条命令接入"
cd "$WORK"
mkdir -p 交付
"$DEVFLOW" init --name preflight-demo --with-preflight >/dev/null 2>&1
python3 - <<'PY' && ok "preflight 门禁与 release.requires 已登记" || bad "devflow.json 没登记上"
import json
d = json.load(open("devflow.json"))
assert "preflight" in d.get("gates", {}), d.get("gates")
assert "preflight" in d.get("release", {}).get("requires", []), d.get("release")
PY
# 这次只验证 preflight 的接线：init 生成的 build/test 是**占位脚本**（必然失败），
# 真实项目里要换成自己的命令。这里替换成可过的版本，避免它们盖住 preflight 的结论。
python3 - <<'PYJSON'
import json
d = json.load(open("devflow.json"))
for name in ("build", "test"):
    if name in d["gates"]:
        d["gates"][name] = {
            "run": "echo ok",
            "negative_control": "sh -c 'echo FAIL placeholder; exit 1'",
        }
json.dump(d, open("devflow.json", "w"), ensure_ascii=False, indent=2)
PYJSON

for f in scripts/preflight-gate.sh scripts/preflight-should-fail.sh; do
  [ -x "$f" ] && ok "生成且可执行：$f" || bad "缺少可执行脚本：$f"
done

echo "== 1. 负向对照必须失败（现场造脏表）"
if ./scripts/preflight-should-fail.sh >/tmp/pi-neg.log 2>&1; then
  bad "负向对照竟然通过了 —— 门禁是恒真"
else
  grep -q "FAIL preflight blocked" /tmp/pi-neg.log && ok "负向对照失败，且带 FAIL 证据" || bad "负向对照失败但无证据"
fi

echo "== 2. 交付目录为空：不许放行"
if ./scripts/preflight-gate.sh 交付 >/tmp/pi-empty.log 2>&1; then
  bad "空目录被判为可交付（假通过）"
else
  grep -q "no files found" /tmp/pi-empty.log && ok "空目录被拦（no files found）" || bad "拦住了但原因不明"
fi

echo "== 3. 脏数据：发布必须被拦"
"$DEVFLOW" new --slug p1 --tier micro --title "发布脏数据" >/dev/null 2>&1
ITEM="$(ls -1t .devflow/.local/items | head -1)"
cp /tmp/preflight-empty 2>/dev/null || true
python3 - "$REPO" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/tools")
import make_dirty_fixture
make_dirty_fixture.build("交付/订单明细.xlsx")
PY
if "$DEVFLOW" advance "$ITEM" --to released >/tmp/pi-rel.log 2>&1; then
  bad "脏数据竟然发布成功"
else
  grep -q "preflight" /tmp/pi-rel.log && ok "released 被 preflight 拦住" || bad "拦住了但原因不是 preflight"
fi

echo "== 4. 换成干净数据：可以发布"
python3 - <<'PY'
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["订单号", "区域", "金额(元)"])
ws.append(["SO-1", "华东", 1200]); ws.append(["SO-2", "华南", 800])
wb.save("交付/订单明细.xlsx")
PY
if "$DEVFLOW" advance "$ITEM" --to released >/tmp/pi-ok.log 2>&1; then
  ok "干净数据发布通过"
else
  bad "干净数据被拦（不应该）：$(tail -3 /tmp/pi-ok.log)"
fi

echo
echo "通过 $pass 项，失败 $fail 项"
[ "$fail" -eq 0 ] && echo "一条命令接入验收通过" || echo "一条命令接入验收失败"
[ "$fail" -eq 0 ]
