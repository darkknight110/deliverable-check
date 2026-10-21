#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 deliverable-check 的真实运行结果，供演示动画渲染。

演示内容：一张"看起来正常"的脏表 → 体检拦下（并给出放大倍数）→ 修好 → 通过。
所有数字来自 `audit_data.audit()` 的真实输出，动画不手写任何结论。

用法：
    python3 tools/demo/capture_preflight.py --out docs/demo-preflight.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import audit_data  # noqa: E402
import make_dirty_fixture  # noqa: E402


def run(cmd: str, cwd: str) -> tuple[str, int]:
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                       env=dict(os.environ, NO_COLOR="1"))
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def clean_workbook(path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["订单号", "区域", "金额(元)"])
    ws.append(["SO-1001", "华东", 12000])
    ws.append(["SO-1002", "华东", 8500.5])
    ws.append(["SO-1003", "华南", 3300])
    ws.append(["SO-1004", "华南", 4500])
    wb.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="preflight-demo-")
    os.makedirs(os.path.join(work, "交付"), exist_ok=True)
    target = os.path.join(work, "交付", "订单明细.xlsx")
    steps = []
    try:
        # 1. 脏表体检
        make_dirty_fixture.build(target)
        text, code = run(f"{sys.executable} {os.path.join(ROOT, 'tools', 'preflight.py')} 交付", work)
        detail = audit_data.audit(target)
        ratio = next((f["evidence"]["ratio"] for f in detail["findings"] if f["id"] == "double-count"), None)
        naive = next((f["evidence"]["naive_sum"] for f in detail["findings"] if f["id"] == "double-count"), None)
        corrected = next((f["evidence"]["corrected_sum"] for f in detail["findings"] if f["id"] == "double-count"), None)
        steps.append({
            "caption": "发出去之前先体检：这张表看起来很正常",
            "cmd": "python3 tools/preflight.py 交付",
            "lines": [l for l in text.splitlines() if l.strip()][-9:],
            "verdict": "blocked" if code != 0 else "clean",
            "numbers": {"detail": corrected, "naive": naive, "ratio": ratio},
        })

        # 2. 修好（演示里就是换成规范表）
        clean_workbook(target)
        steps.append({
            "caption": "把小计移出明细、数字转成数值：结构问题，不是「再算一遍」",
            "cmd": "# 修数据：移除小计行、统一数值格式",
            "lines": [],
            "verdict": "pending",
            "numbers": None,
        })

        # 3. 再体检：通过
        text, code = run(f"{sys.executable} {os.path.join(ROOT, 'tools', 'preflight.py')} 交付", work)
        steps.append({
            "caption": "再跑一遍：0 阻断，可以交付",
            "cmd": "python3 tools/preflight.py 交付",
            "lines": [l for l in text.splitlines() if l.strip()][-6:],
            "verdict": "clean" if code == 0 else "blocked",
            "numbers": None,
        })
    finally:
        shutil.rmtree(work, ignore_errors=True)

    payload = {"steps": steps}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"{args.out}（{len(steps)} 步）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
