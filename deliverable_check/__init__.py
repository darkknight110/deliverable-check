"""deliverable-check：交付前体检（方案结构 / AI 味与返工 / 数据体检）。"""

__version__ = "1.0.0"

import sys as _sys  # noqa: E402


def utf8_stdio() -> None:
    """Windows 控制台默认不是 UTF-8，输出 ⛔/✓ 会 UnicodeEncodeError（直接崩，不是难看）。"""
    for stream in (_sys.stdout, _sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                      # noqa: BLE001
            pass
