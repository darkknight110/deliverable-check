#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前体检：一个入口，按文件类型自动分派到三个体检器。

为什么要有它：技能说明里写"先跑数据体检、再跑方案基线"是一回事，
让 agent 只记**一条命令**是另一回事。入口越少，被真正执行的概率越高。

分派规则：
    .xlsx / .csv / .tsv         → 数据体检（有阻断则退出码 1）
    .md / .docx                 → 方案结构量测（信息性，不阻断）
    同类型的多个版本（≥2）        → 追加返工分析（相邻版本改动量）

用法：
    python3 tools/preflight.py 交付/明细.xlsx 方案/方案.md
    python3 tools/preflight.py --json 交付/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile

from . import audit_data
from . import measure_ai_flavor as af
from . import measure_proposals as mp


def collect(inputs, excludes=(), max_files=2000):
    """收集文件。excludes 是 glob；超过 max_files 时截断并提示（不静默扫全盘）。"""
    import fnmatch

    paths = []
    for item in inputs:
        if os.path.isdir(item):
            for root, _dirs, files in os.walk(item):
                for f in files:
                    if f.lower().endswith((".xlsx", ".csv", ".tsv", ".md", ".docx")) and not f.startswith("~$"):
                        paths.append(os.path.join(root, f))
        elif os.path.isfile(item):
            paths.append(item)
    out = [p for p in sorted(set(paths)) if not any(fnmatch.fnmatch(p, pat) for pat in excludes)]
    if len(out) > max_files:
        print(f"⚠ 文件数 {len(out)} 超过上限 {max_files}，只体检前 {max_files} 个（用 --max-files 调整）",
              file=sys.stderr)
        out = out[:max_files]
    return out


def classify(paths):
    out = {"xlsx": [], "md": [], "docx": []}
    for p in paths:
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        if ext in ("csv", "tsv"):
            ext = "xlsx"
        if ext in out:
            out[ext].append(p)
    return out


def doc_metrics(paths):
    """文档结构指标：md 直接读，docx 先抽文本。"""
    rows = []
    for p in paths:
        try:
            text = af.docx_to_markdown(p) if p.lower().endswith(".docx") else mp.read_text(p)
            m = mp.count_md(text)
        except Exception:
            continue
        m["path"] = p
        rows.append(m)
    if not rows:
        return None
    return {
        "documents": len(rows),
        "chars_median": round(statistics.median(r["chars"] for r in rows), 1),
        "h2_median": round(statistics.median(r["h2"] for r in rows), 1),
        "table_rows_median": round(statistics.median(r["table_rows"] for r in rows), 1),
        "acceptance_share": round(sum(1 for r in rows if any("验收" in t or "指标" in t for t in r["h2_titles"])) / len(rows), 2),
        "pricing_share": round(sum(1 for r in rows if any("报价" in t or "成本" in t for t in r["h2_titles"])) / len(rows), 2),
    }


def rework(paths):
    """同一文档类型的多版本 → 返工曲线。"""
    docs = []
    for p in paths:
        name = os.path.basename(p)
        v = af.version_key(name)
        if not v:
            continue
        try:
            text = af.extract_docx(p) if p.lower().endswith(".docx") else af.read_text(p)
        except Exception:
            continue
        docs.append({"name": name, "family": af.doc_family(name), "version": v, "text": text})
    chains = [c for c in af.chain_analysis(docs) if len(c["versions"]) >= 2]
    if not chains:
        return None
    out = []
    for c in chains:
        rw = [s["rewrite_share"] for s in c["steps"]]
        out.append({
            "family": c["family"],
            "versions": len(c["versions"]),
            "chars": f"{c['steps'][0]['chars_from']} → {c['steps'][-1]['chars_to']}",
            "rewrite_mean": round(statistics.mean(rw), 3),
            "rewrite_first6": round(statistics.mean(rw[:6]), 3) if len(rw) >= 6 else None,
            "rewrite_rest": round(statistics.mean(rw[6:]), 3) if len(rw) > 6 else None,
        })
    return out


def run(inputs, excludes=(), max_files=2000):
    paths = collect(inputs, excludes, max_files)
    groups = classify(paths)
    report = {"data": [], "docs": None, "rework": None, "verdict": "clean", "empty": False}
    if not paths:
        # 空目录不能算"可交付"：门禁指向错路径时，最容易发生的假通过就是"什么都没检查"。
        report["empty"] = True
        report["verdict"] = "blocked"
        return report

    for p in groups["xlsx"]:
        try:
            r = audit_data.audit(p)
        except Exception as exc:
            r = {"file": p, "verdict": "blocked", "findings": [{"severity": "block", "title": f"无法读取：{exc}"}], "summary": {"block": 1}}
        report["data"].append({
            "file": p,
            "sheet": r.get("sheet"),
            "rows": r.get("rows"),
            "verdict": r.get("verdict"),
            "blocking": [f["title"] for f in r.get("findings", []) if f["severity"] == "block"],
        })
        if r.get("verdict") == "blocked":
            report["verdict"] = "blocked"

    # Word 表格里的数字：结构量测看不到，单独审
    for p in groups["docx"]:
        try:
            t = audit_data.audit_docx_tables(p)
        except Exception as exc:
            t = {"verdict": "warn", "findings": [{"severity": "warn", "title": f"表格无法审计：{exc}"}]}
        report.setdefault("docx_tables", []).append({
            "file": p,
            "tables": t.get("tables"),
            "verdict": t.get("verdict"),
            "blocking": [f["title"] for f in t.get("findings", []) if f["severity"] == "block"],
            "warnings": [f["title"] for f in t.get("findings", []) if f["severity"] == "warn"],
        })
        if t.get("verdict") == "blocked":
            report["verdict"] = "blocked"

    report["docs"] = doc_metrics(groups["md"] + groups["docx"])
    report["rework"] = rework(groups["md"] + groups["docx"])
    return report


def render(report) -> str:
    lines = ["交付前体检"]
    if report.get("empty"):
        lines.append("  ⛔ 没有找到可体检的文件（.xlsx / .md / .docx）——检查路径是否指错")
    if report["data"]:
        lines.append("· 数据：")
        for d in report["data"]:
            mark = {"clean": "✓", "warn": "⚠", "blocked": "⛔"}.get(d["verdict"], "?")
            lines.append(f"    {mark} {os.path.basename(d['file'])} [{d['sheet']}] {d['rows']} 行 → {d['verdict']}")
            for t in d["blocking"]:
                lines.append(f"      ⛔ {t}")
    if report.get("docx_tables"):
        lines.append("· Word 表格：")
        for t in report["docx_tables"]:
            if not t["tables"]:
                continue
            mark = "⛔" if t["verdict"] == "blocked" else ("⚠" if t["warnings"] else "✓")
            lines.append(f"    {mark} {os.path.basename(t['file'])} {t['tables']} 张表 → {t['verdict']}")
            for b in t["blocking"]:
                lines.append(f"      ⛔ {b}")
    if report["docs"]:
        d = report["docs"]
        lines.append(f"· 文档：{d['documents']} 份，中位 {d['chars_median']:.0f} 字 / {d['h2_median']:.0f} 个二级章节 / "
                     f"{d['table_rows_median']:.0f} 行表格；验收指标 {d['acceptance_share']:.0%}、报价 {d['pricing_share']:.0%}")
        # 只有"像方案"的文档才提示覆盖率：技术说明、基线文档本来就不该有报价
        looks_like_proposal = d["chars_median"] >= 1500 and d["h2_median"] >= 5
        if looks_like_proposal and d["acceptance_share"] < 0.5:
            lines.append("    ⚠ 验收指标覆盖率偏低：先补『做完算不算成』再发")
        if looks_like_proposal and d["pricing_share"] < 0.3:
            lines.append("    ℹ 多数文档没有报价/成本：确认是阶段未到，还是不敢定价")
    if report["rework"]:
        lines.append("· 版本链：")
        for c in report["rework"]:
            lines.append(f"    {c['family']} {c['versions']} 版（{c['chars']} 字），改动均值 {c['rewrite_mean']:.1%}，"
                         f"前 6 次 {c['rewrite_first6']:.1%} / 之后 {c['rewrite_rest']:.1%}")
            if c["rewrite_rest"] is not None and c["rewrite_rest"] < 0.02:
                lines.append("      ℹ 已进入抛光阶段：再润色收益很低，要么接受，要么回结构层重写")
    lines.append(f"结论：{'⛔ 不可交付（先修阻断项）' if report['verdict'] == 'blocked' else '可交付（警告项需人工确认）'}")
    return "\n".join(lines)


def main() -> int:
    argv = sys.argv[1:]
    lang = "en" if "--lang" in argv and argv[argv.index("--lang") + 1:argv.index("--lang") + 2] == ["en"] else "zh"

    def _t(zh, en):
        return en if lang == "en" else zh

    ap = argparse.ArgumentParser(description=_t("交付前体检：一个入口，按类型分派",
                                                "Pre-delivery check: one entry, dispatched by file type"))
    ap.add_argument("inputs", nargs="+", help=_t("文件或目录", "Files or directories"))
    ap.add_argument("--json", action="store_true", help=_t("输出 JSON", "Emit JSON"))
    ap.add_argument("--exclude", action="append", default=[],
                    help=_t("排除的 glob，可重复（如 '*草稿*'）", "Exclude glob, repeatable (e.g. '*draft*')"))
    ap.add_argument("--max-files", type=int, default=2000,
                    help=_t("最多体检多少个文件（默认 2000）", "Max files to check (default 2000)"))
    from . import __version__
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help=_t("帮助语言", "Help language"))
    ap.add_argument("--version", action="version", version=f"deliverable-check {__version__}")
    args = ap.parse_args()

    report = run(args.inputs, args.exclude, args.max_files)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    if report["verdict"] == "blocked":
        # 机器可读的失败证据：门禁不能只看退出码（"文件不存在"也可能返回 1）
        blocks = sum(len(d["blocking"]) for d in report["data"])
        if report.get("empty"):
            print("FAIL preflight blocked: no files found")
        else:
            print(f"FAIL preflight blocked: {blocks} blocking findings")
    return 1 if report["verdict"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
