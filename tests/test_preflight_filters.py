#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight 的过滤能力：排除 glob、文件数上限。"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from deliverable_check import make_dirty_fixture, preflight  # noqa: E402


def clean_xlsx(path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["订单号", "金额(元)"])
    ws.append(["SO-1", 1200]); ws.append(["SO-2", 800])
    wb.save(path)


class TestFilters(unittest.TestCase):
    def test_exclude_glob_生效(self):
        with tempfile.TemporaryDirectory() as td:
            make_dirty_fixture.build(os.path.join(td, "坏表-草稿.xlsx"))
            clean_xlsx(os.path.join(td, "正式表.xlsx"))
            self.assertEqual(preflight.run([td])["verdict"], "blocked")
            r = preflight.run([td], excludes=["*草稿*"])
            self.assertEqual(r["verdict"], "clean", r)

    def test_max_files_截断(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(3):
                clean_xlsx(os.path.join(td, f"{i}.xlsx"))
            r = preflight.run([td], max_files=2)
            self.assertEqual(len(r["data"]), 2)

    def test_英文_help(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "tools", "preflight.py"),
                            "--lang", "en", "--help"], capture_output=True, text=True)
        self.assertIn("Pre-delivery check", r.stdout)

    def test_version_可调用(self):
        from deliverable_check import __version__
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
