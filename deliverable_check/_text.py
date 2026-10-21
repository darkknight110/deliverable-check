#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享文本度量：中文文档的句子、段落、标记统计。

三条规则决定了这里面所有函数的形状：
  1. **只数可核对的东西**：句长、段长、标记出现次数。不打"专业度 8.7 分"这种分。
  2. **分母统一**：所有比率都按"每千字"或"每千句"，否则长短文档不可比。
  3. **中文断句按标点**，不按空白 —— 中文没有空格分词，按空白切会把整段当一句。
"""
from __future__ import annotations

import re

CJK = r"\u4e00-\u9fff"
SENT_END = "。！？；!?;"
_PARA_SPLIT = re.compile(r"\n\s*\n")
_SENT_SPLIT = re.compile(f"[{SENT_END}]")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def strip_markup(md: str) -> str:
    """去掉代码块/表格/图片/链接标记，只留正文，避免把代码当行文统计。"""
    text = re.sub(r"```[\s\S]*?```", "", md)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # 表格行不是行文：留着会把整张表并成一句"超长句"，把平均句长拉到 80+
    text = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("|"))
    # 标题行同理（没有句末标点，会把下一段并进来）
    text = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))
    return text


def paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in _PARA_SPLIT.split(text)]
    return [p for p in parts if p and not p.startswith("#")]


def sentences(text: str) -> list[str]:
    raw = _SENT_SPLIT.split(text)
    return [s.strip() for s in raw if len(s.strip()) >= 2]


def cjk_chars(text: str) -> int:
    return len(re.findall(f"[{CJK}]", text))


def per_1k(count: int, chars: int) -> float:
    return round(count * 1000 / chars, 2) if chars else 0.0


def heading_lines(md: str) -> list[tuple[int, str]]:
    out = []
    for line in md.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def normalize_heading(title: str) -> str:
    """去掉编号与装饰，用于跨文档统计"哪些章节是标配"。"""
    t = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", title)
    t = re.sub(r"^\d+(\.\d+)*[、.．)）]?\s*", "", t)
    t = re.sub(r"[（(][^）)]*[）)]$", "", t)
    return t.strip(" ：:·—-")
