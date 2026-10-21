#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_data 的单元测试：钉住三类"零报错"事故必须被拦住。"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import audit_data  # noqa: E402
import make_dirty_fixture  # noqa: E402


class TestDirtyWorkbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, "dirty.xlsx")
        make_dirty_fixture.build(cls.path)
        cls.report = audit_data.audit(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ids(self):
        return {f["id"] for f in self.report["findings"]}

    def test_结论是不可交付(self):
        self.assertEqual(self.report["verdict"], "blocked")

    def test_小计行被识别(self):
        self.assertIn("total-rows-in-data", self.ids())

    def test_千分位文本数字被识别(self):
        self.assertIn("text-numbers", self.ids())

    def test_求和放大倍数被算出(self):
        f = next(f for f in self.report["findings"] if f["id"] == "double-count")
        self.assertGreaterEqual(f["evidence"]["ratio"], 2.5)
        self.assertGreater(f["evidence"]["naive_sum"], f["evidence"]["corrected_sum"])

    def test_合计与明细对不上(self):
        self.assertIn("total-mismatch", self.ids())

    def test_主键重复被识别(self):
        self.assertIn("duplicate-key", self.ids())

    def test_单位写进数值被识别(self):
        self.assertIn("unit-in-value", self.ids())


class TestCleanWorkbook(unittest.TestCase):
    def test_干净表不报阻断(self):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["订单号", "区域", "金额(元)"])
        ws.append(["SO-1", "华东", 1200])
        ws.append(["SO-2", "华南", 800])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "clean.xlsx")
            wb.save(path)
            report = audit_data.audit(path)
        self.assertEqual(report["verdict"], "clean", report["findings"])


class TestRatioColumn(unittest.TestCase):
    def test_比率列不做求和校验(self):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["月份", "毛利率(%)"])
        ws.append(["1", 0.66])
        ws.append(["2", 0.65])
        ws.append(["合计", 1.31])
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "ratio.xlsx")
            wb.save(path)
            report = audit_data.audit(path)
        ids = {f["id"] for f in report["findings"]}
        self.assertNotIn("total-mismatch", ids, "比率列相加没有业务意义，不应报错")


if __name__ == "__main__":
    unittest.main()
