#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 devflow 记录里的数据门禁结论（证据可核，而不是看 CLI 摘要）。

用法：python3 check_record.py <item-id> <期望>  期望 ∈ pass|blocked
退出码 0 = 符合期望；1 = 不符合。
"""
import json
import sys


def main() -> int:
    item, expect = sys.argv[1], sys.argv[2]
    path = f".devflow/.local/items/{item}/STATUS.json"
    d = json.load(open(path, encoding="utf-8"))
    recs = [r for r in d["lastRun"]["records"] if r["gate"] == "data"]
    if not recs:
        print("没有 data 门禁记录")
        return 1
    r = recs[-1]
    tail = r.get("outputTail") or ""
    print(f"exit={r['exitCode']} command={r['command']}")
    print(f"tail={tail.splitlines()[-1] if tail else '(空)'}")
    if expect == "pass":
        return 0 if r["exitCode"] == 0 else 1
    # blocked：退出码必须非零，且输出里有明确的失败证据
    return 0 if r["exitCode"] != 0 and "FAIL data-audit blocked" in tail else 1


if __name__ == "__main__":
    raise SystemExit(main())
