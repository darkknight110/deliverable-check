#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口：实现在 deliverable_check/measure_proposals.py（pip 安装后也可用 `measure-proposals` 命令）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deliverable_check.measure_proposals import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
