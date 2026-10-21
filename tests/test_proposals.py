#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_proposals 的单元测试：结构统计与"表格不算行文"的边界。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import measure_proposals as mp  # noqa: E402
from _text import normalize_heading, strip_markup  # noqa: E402

SAMPLE = """# 某项目方案

## 一、项目背景与必要性

我们要解决库存准确率问题，当前 98.2%。这是第二句话。

## 二、验收指标

| AC | 判据 | 口径 |
|---|---|---|
| AC-1 | 库存准确率 ≥99.5% | 月度盘点 |
| AC-2 | 出库时长 ≤30 分钟 | 系统日志 |

## 三、风险与假设

假设：甲方已有 WMS。待验证：监管仓是否在运行。

```
┌────────┐
│ 平台   │
└────────┘
```
"""


class TestCount(unittest.TestCase):
    def test_章节与层级(self):
        m = mp.count_md(SAMPLE)
        self.assertEqual(m["h1"], 1)
        self.assertEqual(m["h2"], 3)
        self.assertEqual(m["max_depth"], 2)

    def test_表格行不计入行文但计入表格(self):
        m = mp.count_md(SAMPLE)
        self.assertGreaterEqual(m["table_rows"], 2)
        # 表格里的"≥99.5%"不该被算成正文里的数字密度来源
        self.assertLess(m["chars"], m["chars_doc"])

    def test_字符画被识别(self):
        self.assertEqual(mp.count_md(SAMPLE)["ascii_diagrams"], 1)

    def test_口径与假设标注被计数(self):
        m = mp.count_md(SAMPLE)
        self.assertGreaterEqual(m["hedge"]["假设/待验证"], 2)
        self.assertGreaterEqual(m["hedge"]["口径/来源"], 1)

    def test_确定性词计数(self):
        m = mp.count_md("我们保证一定做到，绝不失败。")
        self.assertGreaterEqual(m["certain_per_1k"], 1)


class TestHelpers(unittest.TestCase):
    def test_标题去编号(self):
        self.assertEqual(normalize_heading("一、项目背景与必要性"), "项目背景与必要性")
        self.assertEqual(normalize_heading("2.1 建设目标"), "建设目标")
        self.assertEqual(normalize_heading("验收指标（草案）"), "验收指标")

    def test_strip_markup_去表格与标题(self):
        out = strip_markup(SAMPLE)
        self.assertNotIn("| AC |", out)
        self.assertNotIn("## 二、", out)
        self.assertIn("库存准确率问题", out)


class TestAggregate(unittest.TestCase):
    def test_聚合给出中位数与骨架(self):
        docs = [mp.count_md(SAMPLE) | {"path": "a.md"}]
        agg = mp.aggregate(docs)
        self.assertEqual(agg["documents"], 1)
        self.assertEqual(agg["h2_median"], 3.0)
        self.assertTrue(any(s["category"] == "验收/指标" for s in agg["skeleton_keywords"]))


if __name__ == "__main__":
    unittest.main()
