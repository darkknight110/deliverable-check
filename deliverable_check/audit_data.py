#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据交付体检：在把 Excel 发出去之前，先证明"这个数算得对"。

为什么需要它：做数据分析，算错了**什么都不会发生**——不抛异常、不报 NaN、
不弹警告，交付出去的错误答案和正确答案长得一模一样。

三类真实事故（都在本工具里做成可机械检出的检查项）：
  1. 小计/合计行混在明细里 → 求和翻倍（真实踩过：+161%，零报错）
  2. 数字以文本存储（千分位、带单位）→ 求和为 0 或被静默丢弃
  3. 两级表头 + 合并单元格 → 读表时列错位，口径整体错位

用法：
    python3 tools/audit_data.py 交付表.xlsx [--key-col 订单号] [--sheet Sheet1]
    python3 tools/audit_data.py 交付表.xlsx --json

退出码：0 = 无阻断项；1 = 有阻断项（可直接接进 CI 或 devflow 门禁）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict

# 小计行常常带前缀（「华东小计」），所以不锚定行首，改为"前两个单元格里出现汇总词"
TOTAL_PAT = re.compile(r"(合计|总计|小计|汇总|累计|总额|subtotal|total)", re.I)
NUM_TEXT = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
UNIT_SUFFIX = re.compile(r"^-?\d+(?:\.\d+)?\s*(元|万元|亿元|件|吨|托|箱|kg|KG|天|小时)$")
UNIT_TOKEN = re.compile(r"单位|元|万元|件|吨|托|箱|天|小时|%")
BLOCK = "block"
WARN = "warn"
INFO = "info"


@dataclass
class Finding:
    id: str
    severity: str
    title: str
    detail: str
    evidence: dict = field(default_factory=dict)
    fix: str = ""


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def _num(v):
    """把单元格尽力解析成数字：真正的数字 / 千分位文本 / 带单位文本 → float，否则 None。"""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = _text(v)
    if not s:
        return None
    s2 = s.replace(",", "").replace("，", "")
    m = re.match(r"^-?\d+(?:\.\d+)?$", s2)
    if m:
        return float(s2)
    m = UNIT_SUFFIX.match(s)
    if m:
        return float(re.match(r"^-?\d+(?:\.\d+)?", s).group(0))
    return None


def _decode(raw: bytes) -> str:
    """CSV 编码：先 UTF-8（含 BOM），再 GB18030（Excel 中文版默认导出）。"""
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _csv_rows(path: str) -> tuple[list, str, list]:
    import csv

    delim = "\t" if path.lower().endswith(".tsv") else ","
    text = _decode(open(path, "rb").read())
    rows = list(csv.reader(text.splitlines(), delimiter=delim))
    width = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows, "CSV", []


def audit(path: str, sheet: str | None = None, key_col: str | None = None) -> dict:
    if path.lower().endswith((".csv", ".tsv")):
        rows, sheet_title, merges = _csv_rows(path)
        return _audit_rows(path, rows, sheet_title, merges, key_col)

    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    if sheet:
        ws = wb[sheet]
    else:
        # 自动选"最像数据页"的工作表：数值单元格多、行数多者优先。
        # 封面/说明页（Start Here、Readme、目录）合并单元格多、数字少，会被自动跳过。
        def sheet_score(name):
            sh = wb[name]
            nums = 0
            rows = 0
            for r in sh.iter_rows():
                rows += 1
                nums += sum(1 for c in r if isinstance(c.value, (int, float)) and not isinstance(c.value, bool))
            return nums * 2 + rows

        ws = wb[max(wb.sheetnames, key=sheet_score)]

    rows = [[c.value for c in r] for r in ws.iter_rows()]
    rows = [r for r in rows if any(_text(v) for v in r)]
    merges = [str(r) for r in ws.merged_cells.ranges]
    return _audit_rows(path, rows, ws.title, merges, key_col)


def _audit_rows(path, rows, sheet_title, merges, key_col):
    rows = [r for r in rows if any(_text(v) for v in r)]
    findings: list[Finding] = []
    if not rows:
        return {"file": path, "findings": [asdict(Finding("empty", BLOCK, "空表", "没有任何非空单元格"))],
                "verdict": "blocked"}

    # ── 表头定位：候选行里"像表头"得分最高的一行
    #    纯文本单元格 +1，能解析成数字的 -2，同行有合并导致只剩 1 个值的 -3。
    #    单一"非空最多"会把两级表头的第二行选成表头（实测踩到）。
    def header_score(i):
        vals = [_text(v) for v in rows[i]]
        non_empty = [v for v in vals if v]
        if not non_empty:
            return -99
        text = sum(1 for v in non_empty if _num(v) is None and not UNIT_SUFFIX.match(v))
        nums = sum(1 for v in non_empty if _num(v) is not None)
        return text - 2 * nums - (3 if len(non_empty) <= 1 else 0)

    head_idx = max(range(min(6, len(rows))), key=header_score)
    header = [_text(v) for v in rows[head_idx]]
    data_start = head_idx + 1

    # ── 二级表头（单位/限定词那一行）：并入表头，不当作数据
    if data_start < len(rows):
        sub = [_text(v) for v in rows[data_start]]
        sub_items = [v for v in sub if v]
        looks_like_sub = sub_items and all(len(v) <= 8 for v in sub_items) and all(
            re.match(r"^[（(].*[）)]$|^[\u4e00-\u9fff]{1,4}$", v) for v in sub_items
        )
        if looks_like_sub:
            for ci, v in enumerate(sub):
                if v and ci < len(header):
                    header[ci] = f"{header[ci]}{v}" if header[ci] else v
                elif v:
                    header.append(v)
            data_start += 1

    data = rows[data_start:]

    # ── 1. 合并单元格 / 两级表头
    header_rows = head_idx + 1
    merged_in_header = [m for m in merges if any(
        int(re.findall(r"\d+", m)[1]) <= header_rows for _ in [0]
    )] if merges else []
    if len(merges) >= 3:
        findings.append(Finding(
            "merged-cells", WARN,
            f"存在 {len(merges)} 处合并单元格",
            "合并单元格会让 pandas/openpyxl 读表时列错位，尤其是表头区域",
            {"merges": merges[:5]},
            "交付前取消合并，改成每一行都填满的规范表",
        ))
    if merged_in_header:
        findings.append(Finding(
            "multi-row-header", WARN,
            "表头疑似两级（合并单元格落在表头区）",
            "两级表头必须显式指定 header=[0,1] 才能读对，否则列名会变成 Unnamed",
            {"header_row": header_rows},
            "在表下方加一张「字段说明」表，或把两级表头合并成一行",
        ))

    summary_col = any(re.match(r"^(total|合计|总计|汇总)$", h, re.I) for h in header if h)
    if summary_col:
        findings.append(Finding(
            "summary-layout", INFO,
            "这张表自带合计列/汇总列（疑似汇总表）",
            "汇总表不是明细表：逐列求和没有业务意义，本工具的「翻倍」检查对这类表不适用",
            {"headers": [h for h in header if re.match(r"^(total|合计|总计|汇总)$", h, re.I)]},
            "若要体检明细，请对明细页单独跑一次",
        ))

    # ── 2. 合计/小计行混在明细里
    total_rows = [i for i, r in enumerate(data) if any(TOTAL_PAT.search(_text(v)) for v in r[:2])]
    # 表中间夹小计（或有多处合计）才算高危；表尾一行合计是常见布局，只提示
    intermediate_totals = any(i != len(data) - 1 for i in total_rows)
    if total_rows:
        findings.append(Finding(
            "total-rows-in-data", BLOCK if (len(total_rows) > 1 or intermediate_totals) else INFO,
            f"明细区里有 {len(total_rows)} 行小计/合计",
            "直接对整列求和会把小计再算一遍——这是「求和翻倍」最常见的来源，且不会报错",
            {"rows": [i + head_idx + 2 for i in total_rows][:8]},
            "把小计/合计移到表外（或单独一张汇总表），明细区只放明细",
        ))

    # ── 3. 数字以文本存储
    text_num_cells = 0
    unit_cells = 0
    for r in data:
        for v in r:
            s = _text(v)
            if isinstance(v, str):
                if NUM_TEXT.match(s):
                    text_num_cells += 1
                elif UNIT_SUFFIX.match(s):
                    unit_cells += 1
    if text_num_cells:
        findings.append(Finding(
            "text-numbers", BLOCK,
            f"{text_num_cells} 个单元格是「带千分位的文本数字」",
            "读表时会被当成字符串：求和得 0，或者整列被丢弃 —— 静默发生，无任何提示",
            {"cells": text_num_cells},
            "交付前统一转成数值格式（去千分位、去单位）",
        ))
    if unit_cells:
        findings.append(Finding(
            "unit-in-value", WARN,
            f"{unit_cells} 个单元格把单位写进了数值",
            "「1,200 元」这种写法无法参与计算；单位应放在列名里",
            {"cells": unit_cells},
            "单位提到表头，如「金额(元)」",
        ))

    # ── 4. 校验和：合计行 vs 明细求和
    numeric_cols = {}
    for ci in range(max(len(r) for r in rows)):
        vals = [_num(r[ci]) for r in data if ci < len(r)]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            numeric_cols[ci] = vals
    checks = []
    RATIO_COL = re.compile(r"%|率|比例|占比|ratio|margin|avg|均值|平均", re.I)
    for ci, vals in numeric_cols.items():
        name = header[ci] if ci < len(header) and header[ci] else f"第{ci + 1}列"
        # 比率列不能求和：GM%、占比、均值这类列，合计对不上是正常的
        if RATIO_COL.search(name):
            continue
        detail_vals, total_vals = [], []
        for i, r in enumerate(data):
            v = _num(r[ci]) if ci < len(r) else None
            if v is None:
                continue
            (total_vals if i in total_rows else detail_vals).append(v)
        if total_rows and total_vals and detail_vals:
            s_detail = round(sum(detail_vals), 2)
            s_total = round(sum(total_vals), 2)
            diff = round(s_total - s_detail, 2)
            ok = abs(diff) <= max(0.01, abs(s_detail) * 0.005)
            checks.append({
                "column": name, "detail_sum": s_detail,
                "total_row_sum": s_total, "diff": diff, "consistent": ok,
            })
            if not ok:
                findings.append(Finding(
                    "total-mismatch", BLOCK,
                    f"「{name}」的合计与明细对不上（差 {diff:,.2f}）",
                    "合计行不是明细的校验和，说明有一方错——这正是「合计行当免费校验和」能抓到的问题",
                    {"column": name, "detail_sum": s_detail, "total_row_sum": s_total},
                    "找出差异来源；确认后才可交付",
                ))
        naive = round(sum(vals), 2)
        corrected = round(sum(detail_vals), 2) if total_vals else naive
        if total_vals and naive and abs(naive - corrected) / max(abs(corrected), 1e-9) > 0.01:
            inflate = naive / corrected if corrected else float("inf")
            # 只有"表中间夹着小计"才是高危（求和必翻倍）；表尾一行合计属于常见布局，降级为提示
            sev = BLOCK if (len(total_rows) > 1 or intermediate_totals) and not summary_col else INFO
            findings.append(Finding(
                "double-count", sev,
                f"「{name}」整列求和会放大到 {inflate:.2f} 倍",
                "把明细与小计一起求和，得到的是一个「看起来很正常」的错误数字",
                {"naive_sum": naive, "corrected_sum": corrected, "ratio": round(inflate, 3)},
                "排除小计/合计行后再求和，或把汇总移到表外",
            ))

    # ── 5. 主键重复
    key_idx = 0
    if key_col:
        for i, h in enumerate(header):
            if key_col in h:
                key_idx = i
                break
    keys = [_text(r[key_idx]) for r in data if key_idx < len(r) and _text(r[key_idx])]
    keys = [k for k in keys if not TOTAL_PAT.search(k)]
    dup = {k: keys.count(k) for k in set(keys) if keys.count(k) > 1}
    if dup:
        findings.append(Finding(
            "duplicate-key", WARN,
            f"主键列「{header[key_idx] if key_idx < len(header) else key_idx + 1}」有 {len(dup)} 个重复值",
            "重复主键会让「去重后求和」与「逐行求和」给出两个不同的答案",
            {"examples": list(dup.items())[:5]},
            "确认是业务允许的重复，还是数据重复导入",
        ))

    # ── 6. 空值率与单位
    for ci, name in enumerate(header):
        if not name:
            continue
        col = [r[ci] for r in data if ci < len(r)]
        empty = sum(1 for v in col if not _text(v))
        if col and empty / len(col) > 0.2:
            findings.append(Finding(
                "high-empty", WARN,
                f"「{name}」空值率 {empty / len(col):.0%}",
                "空值率高时，列求和/计数会低估，且没人会发现",
                {"column": name, "empty": empty, "rows": len(col)},
                "确认空值是「无此字段」还是「没录进来」",
            ))
        if ci in numeric_cols and not UNIT_TOKEN.search(name):
            findings.append(Finding(
                "unit-missing", INFO,
                f"数值列「{name}」的表头没有单位",
                "金额、重量、件数混在一起时，口径会在下游被误解",
                {"column": name},
                "表头补单位，如「金额(元)」「重量(吨)」",
            ))

    blocking = [f for f in findings if f.severity == BLOCK]
    return {
        "file": path,
        "sheet": sheet_title,
        "rows": len(data),
        "columns": len(header),
        "checksum": checks,
        "findings": [asdict(f) for f in findings],
        "verdict": "blocked" if blocking else ("warn" if findings else "clean"),
        "summary": {
            "block": len(blocking),
            "warn": sum(1 for f in findings if f.severity == WARN),
            "info": sum(1 for f in findings if f.severity == INFO),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Excel 数据交付体检")
    ap.add_argument("file", help=".xlsx 文件")
    ap.add_argument("--sheet", help="工作表名（默认第一张）")
    ap.add_argument("--key-col", help="主键列名（默认第一列）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    from . import __version__
    ap.add_argument("--version", action="version", version=f"deliverable-check {__version__}")
    args = ap.parse_args()

    report = audit(args.file, args.sheet, args.key_col)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['file']}  [{report['sheet']}]  {report['rows']} 行 × {report['columns']} 列")
        marks = {BLOCK: "⛔", WARN: "⚠", INFO: "ℹ"}
        for f in report["findings"]:
            print(f"  {marks[f['severity']]} {f['title']}")
            print(f"     {f['detail']}")
            if f["fix"]:
                print(f"     修法：{f['fix']}")
        if not report["findings"]:
            print("  ✓ 未发现可机械检出的问题")
        print(f"  结论：{ {'clean': '可交付', 'warn': '有风险项，需确认', 'blocked': '不可交付'}[report['verdict']] }")
        if report["verdict"] == "blocked":
            # 机器可读的失败证据：门禁只认"输出里有明确的失败标记"，不能只靠退出码
            print(f"FAIL data-audit blocked: {report['summary']['block']} blocking findings")
    return 1 if report["verdict"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
