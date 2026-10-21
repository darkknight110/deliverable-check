#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文技术方案写作量测：把"这份方案像不像样"拆成可核对的数字。

量什么：
  · 体量：字数、句数、段落数、中文字数
  · 结构：标题层级、章节数、表格数/行数、字符画图数、代码块
  · 行文：平均句长、平均段长、列表项占比
  · 证据密度：数字出现频率、口径/来源/待验证标注频率
  · 断言强度：确定性词（一定/必然/绝对/保证）频率
  · 章节骨架：跨文档统计"哪些章节是标配"

不量什么：不判断"写得好不好"。同一份文档好不好，取决于是给谁看、处在什么阶段 ——
本工具只回答"它有多少骨架、多少证据、多少断言"，判断留给人。

用法：
    python3 tools/measure_proposals.py --out docs/proposal-baseline.json <目录或文件...>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter

from ._text import (  # noqa: E402
    cjk_chars, heading_lines, normalize_heading, paragraphs, per_1k,
    read_text, sentences, strip_markup,
)

# 证据类标注：出现越多，说明作者越愿意把"来源/口径/不确定性"写出来
HEDGE = {
    "口径/来源": r"口径|来源|出处|截至|依据",
    "假设/待验证": r"假设|待验证|待确认|未证实|前提",
    "估算/范围": r"估算|预估|区间|约为|量级",
    "局限/风险": r"风险|局限|边界|不做什么|不在本期",
}
# 断言类：说得越满，越需要证据兜底
CERTAIN = r"一定|必然|绝对|保证|100%|完全|彻底|必然|无损|零风险"
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.M)
NUM = re.compile(r"\d+(?:[.,]\d+)?")
# 方案骨架的"关键词类目"：比精确标题稳（同一件事各家写法不同）
SKELETON = {
    "背景/现状/必要性": r"背景|现状|必要性|痛点|缘起",
    "目标/范围": r"目标|范围|建设内容|总体思路",
    "方案/架构/设计": r"方案|架构|设计|总体",
    "接口/集成/对接": r"接口|集成|对接|契约",
    "实施/计划/工期": r"实施|计划|工期|排期|里程碑",
    "验收/指标": r"验收|指标|KPI|度量|口径",
    "风险/假设/边界": r"风险|假设|边界|不做什么|局限",
    "报价/成本/预算": r"报价|成本|预算|费用|计价",
    "术语/名词": r"术语|名词|缩写|定义",
    "问题/待确认": r"问题|待确认|前置|澄清|疑问",
    "分工/责任": r"分工|责任|角色|职责|边界",
    "运维/培训/交付": r"运维|培训|交付|售后|质保",
}


def count_md(md: str) -> dict:
    body = strip_markup(md)          # 行文：剔除代码、表格、标题
    annot = re.sub(r"```[\s\S]*?```", "", md)  # 标注：保留表格（口径/来源常常只在表里）
    sents = sentences(body)
    paras = paragraphs(body)
    chars = cjk_chars(body)
    hs = heading_lines(md)
    tables = re.findall(r"^\|.+\|\s*$", md, re.M)
    table_rows = [t for t in tables if not re.match(r"^\|[\s:|-]+\|\s*$", t.strip())]
    fences = re.findall(r"^```", md, re.M)
    ascii_diagrams = len(re.findall(r"```[^\n]*\n(?:[^\n]*\n)*?[^\n]*[┌└│├][^\n]*\n(?:[^\n]*\n)*?```", md))
    return {
        "chars": chars,
        "chars_doc": cjk_chars(md),
        "sentences": len(sents),
        "paragraphs": len(paras),
        "avg_sentence_len": round(statistics.mean(len(s) for s in sents), 1) if sents else 0,
        "median_sentence_len": round(statistics.median(len(s) for s in sents), 1) if sents else 0,
        "avg_paragraph_len": round(statistics.mean(len(p) for p in paras), 1) if paras else 0,
        "headings": len(hs),
        "h1": sum(1 for lv, _ in hs if lv == 1),
        "h2": sum(1 for lv, _ in hs if lv == 2),
        "h3": sum(1 for lv, _ in hs if lv == 3),
        "max_depth": max((lv for lv, _ in hs), default=0),
        "table_rows": len(table_rows),
        "table_ratio_per_1k": per_1k(len(table_rows), chars),
        "code_blocks": len(fences) // 2,
        "ascii_diagrams": ascii_diagrams,
        "list_items": len(LIST_ITEM.findall(body)),
        "list_ratio": round(len(LIST_ITEM.findall(body)) / max(1, len(paras)), 2),
        "numbers_per_1k": per_1k(len(NUM.findall(annot)), chars),
        "certain_per_1k": per_1k(len(re.findall(CERTAIN, annot)), chars),
        "hedge": {k: len(re.findall(p, annot)) for k, p in HEDGE.items()},
        "h2_titles": [normalize_heading(t) for lv, t in hs if lv == 2],
    }


def aggregate(docs: list[dict]) -> dict:
    def med(key):
        vals = [d[key] for d in docs if d.get(key)]
        return round(statistics.median(vals), 1) if vals else None

    section_freq = Counter()
    for d in docs:
        for title in set(d["h2_titles"]):
            section_freq[title] += 1
    n = len(docs)
    # 关键词类目覆盖：跨文档统计"这类章节出现在多少份方案里"
    kw_hits = Counter()
    for d in docs:
        joined = " ".join(d["h2_titles"])
        for name, pattern in SKELETON.items():
            if re.search(pattern, joined):
                kw_hits[name] += 1
    skeleton_kw = [
        {"category": k, "docs": v, "share": round(v / n, 2)}
        for k, v in kw_hits.most_common()
    ]
    # 只在 ≥15% 文档里出现的章节才进"骨架候选"，否则会被一次性标题淹没
    skeleton = [
        {"section": s, "docs": c, "share": round(c / n, 2)}
        for s, c in section_freq.most_common(30) if c / n >= 0.15
    ]
    hedge_avg = {}
    for key in HEDGE:
        hedge_avg[key] = round(statistics.mean(d["hedge"][key] for d in docs), 1) if docs else 0

    return {
        "documents": n,
        "chars_total": sum(d["chars_doc"] for d in docs),
        "chars_median": med("chars"),
        "sentences_median": med("sentences"),
        "avg_sentence_len_median": med("avg_sentence_len"),
        "avg_paragraph_len_median": med("avg_paragraph_len"),
        "headings_median": med("headings"),
        "h2_median": med("h2"),
        "max_depth_median": med("max_depth"),
        "table_rows_median": med("table_rows"),
        "table_ratio_per_1k_median": med("table_ratio_per_1k"),
        "numbers_per_1k_median": med("numbers_per_1k"),
        "list_ratio_median": med("list_ratio"),
        "certain_per_1k_median": med("certain_per_1k"),
        "hedge_avg": hedge_avg,
        "skeleton": skeleton,
        "skeleton_keywords": skeleton_kw,
        "docs_with_ascii_diagram": sum(1 for d in docs if d["ascii_diagrams"]),
        "docs_with_tables": sum(1 for d in docs if d["table_rows"]),
    }


def _redact_path(path: str) -> str:
    """把路径换成不可逆的短码：公开基线时不能带客户名与项目名。"""
    import hashlib

    h = hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
    return f"doc-{h}"


def main() -> int:
    from . import utf8_stdio
    utf8_stdio()
    ap = argparse.ArgumentParser(description="量测中文技术方案的结构与行文")
    ap.add_argument("inputs", nargs="+", help="Markdown 文件或目录")
    ap.add_argument("--out", help="输出 JSON")
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--redact", action="store_true", help="输出里隐去真实路径（公开前必须加）")
    args = ap.parse_args()

    paths = []
    for item in args.inputs:
        if os.path.isdir(item):
            for root, _dirs, files in os.walk(item):
                paths += [os.path.join(root, f) for f in files if f.endswith(".md")]
        elif item.endswith(".md"):
            paths.append(item)
    paths = sorted(set(paths))
    if not paths:
        print("没有找到 .md 文件", file=sys.stderr)
        return 2

    docs = []
    for p in paths:
        md = read_text(p)
        try:
            stats = count_md(md)
        except Exception as exc:  # 单篇失败不该让整批中断，但要留痕
            print(f"! 跳过 {p}: {exc}", file=sys.stderr)
            continue
        stats["path"] = _redact_path(p) if args.redact else p
        docs.append(stats)

    full = [d for d in docs if d["h2"] >= 5 and d["chars_doc"] >= 3000]
    agg_all = aggregate(docs)
    agg_full = aggregate(full)
    if args.redact:
        # 逐文档的章节标题会带出项目/行业信息（"多租户冷库""梯控"），公开版只保留聚合结果
        for d in docs:
            d.pop("h2_titles", None)
    payload = {
        "aggregate": agg_all,
        "aggregate_full_proposals": agg_full,
        "documents": docs,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if args.json_only:
        print(text)
    else:
        agg = payload["aggregate_full_proposals"]
        print(f"完整方案 {agg['documents']} 份（共 {payload['aggregate']['documents']} 份 .md），"
              f"{agg['chars_total']:,} 中文字")
        for key in ("chars_median", "avg_sentence_len_median", "avg_paragraph_len_median",
                    "h2_median", "max_depth_median", "table_rows_median",
                    "numbers_per_1k_median", "certain_per_1k_median"):
            print(f"  {key}: {agg[key]}")
        print("  口径/假设标注（均值）:", agg["hedge_avg"])
        print("  高频章节（出现率）:")
        for s in agg["skeleton"][:12]:
            print(f"    {s['share']:.0%}  {s['section']}  ({s['docs']} 份)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
