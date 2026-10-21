#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包一致性：版本号、入口命令、包内模块必须与 pyproject 同步。

版本号写两份（__init__ 与 pyproject）极易腐烂；入口写错则是"装得上、跑不起来"。
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


class TestPackaging(unittest.TestCase):
    def test_版本号与_pyproject_一致(self):
        version = re.search(r'^version\s*=\s*"([^"]+)"', read("pyproject.toml"), re.M).group(1)
        from deliverable_check import __version__
        self.assertEqual(__version__, version)

    def test_入口命令指向真实可调用对象(self):
        scripts = re.findall(r'^([\w-]+)\s*=\s*"([\w.]+):(\w+)"', read("pyproject.toml"), re.M)
        self.assertGreaterEqual(len(scripts), 4)
        import importlib
        for _name, module, func in scripts:
            mod = importlib.import_module(module)
            self.assertTrue(callable(getattr(mod, func)), f"{module}:{func} 不可调用")

    def test_包内模块齐全(self):
        import importlib
        for mod in ("audit_data", "measure_proposals", "measure_ai_flavor", "preflight", "make_dirty_fixture", "_text"):
            importlib.import_module(f"deliverable_check.{mod}")


if __name__ == "__main__":
    unittest.main()
