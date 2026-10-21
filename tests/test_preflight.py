#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight 的单元测试：分派对不对、阻断传不传出去。"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from deliverable_check import preflight  # noqa: E402
from deliverable_check import make_dirty_fixture  # noqa: E402


def write_clean_xlsx(path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["订单号", "区域", "金额(元)"])
    ws.append(["SO-1", "华东", 1200])
    ws.append(["SO-2", "华南", 800])
    wb.save(path)


def write_md(path, text="# 方案\n\n## 一、目标\n\n要做一件事。\n"):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestClassify(unittest.TestCase):
    def test_按扩展名分流(self):
        g = preflight.classify(["a.xlsx", "b.md", "c.docx", "d.txt"])
        self.assertEqual(g["xlsx"], ["a.xlsx"])
        self.assertEqual(g["md"], ["b.md"])
        self.assertEqual(g["docx"], ["c.docx"])


class TestRun(unittest.TestCase):
    def test_干净数据不阻断(self):
        with tempfile.TemporaryDirectory() as td:
            x = os.path.join(td, "clean.xlsx")
            write_clean_xlsx(x)
            r = preflight.run([x])
        self.assertEqual(r["verdict"], "clean")
        self.assertEqual(r["data"][0]["verdict"], "clean")

    def test_脏数据阻断并带出原因(self):
        with tempfile.TemporaryDirectory() as td:
            x = os.path.join(td, "dirty.xlsx")
            make_dirty_fixture.build(x)
            r = preflight.run([x])
        self.assertEqual(r["verdict"], "blocked")
        self.assertTrue(any("放大" in t or "对不上" in t for t in r["data"][0]["blocking"]))

    def test_文档被量测(self):
        with tempfile.TemporaryDirectory() as td:
            m = os.path.join(td, "p.md")
            write_md(m, "# 方案\n\n## 一、目标\n\n做一件事，指标 99%。\n\n## 二、验收指标\n\n| AC | 判据 |\n|---|---|\n| AC-1 | ≥99% |\n")
            r = preflight.run([m])
        self.assertEqual(r["docs"]["documents"], 1)
        self.assertGreaterEqual(r["docs"]["h2_median"], 2)

    def test_多版本触发返工分析(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "x设计方案_V1.0.md")
            b = os.path.join(td, "x设计方案_V1.1.md")
            write_md(a, "# 方案\n\n第一版内容。\n")
            write_md(b, "# 方案\n\n第一版内容，再加一段。\n")
            r = preflight.run([td])
        self.assertIsNotNone(r["rework"])
        self.assertEqual(r["rework"][0]["versions"], 2)

    def test_渲染包含结论(self):
        with tempfile.TemporaryDirectory() as td:
            x = os.path.join(td, "clean.xlsx")
            write_clean_xlsx(x)
            out = preflight.render(preflight.run([x]))
        self.assertIn("交付前体检", out)
        self.assertIn("结论：", out)


if __name__ == "__main__":
    unittest.main()
