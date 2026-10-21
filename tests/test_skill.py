#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKILL.md 的自检测试：外壳写错了，agent 就永远不会选中这个技能。

钉四件事：
  1. frontmatter 三要素齐全（name / description / whenToUse）——缺 whenToUse 技能基本不会被触发；
  2. name 与目录名一致（DSH 按目录名加载）；
  3. 正文引用的每个脚本都真实存在（引用了不存在的路径 = 第一次调用就失败）；
  4. "硬规则"还在（被删掉就等于允许 agent 自己放水）。
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class TestSkillShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.fm = parse_frontmatter(cls.text)

    def test_frontmatter_三要素齐全(self):
        for key in ("name", "description", "whenToUse"):
            self.assertTrue(self.fm.get(key), f"缺少 {key}")

    def test_name_与目录同名(self):
        self.assertEqual(self.fm["name"], os.path.basename(ROOT))

    def test_description_足够长且不超限(self):
        n = len(self.fm["description"])
        self.assertGreater(n, 60, "描述太短，检索不到")
        self.assertLessEqual(n, 1024, "描述过长会被截断")

    def test_whenToUse_覆盖关键触发场景(self):
        w = self.fm["whenToUse"]
        for kw in ("Excel", "方案", "发"):
            self.assertIn(kw, w, f"whenToUse 未覆盖「{kw}」场景")

    def test_引用的脚本都存在(self):
        for rel in re.findall(r"tools/[a-z_]+\.py|examples/[a-z-]+/verify\.sh", self.text):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), f"引用了不存在的路径：{rel}")

    def test_硬规则未被删除(self):
        self.assertIn("不许改阈值", self.text)
        self.assertIn("不许跳过", self.text)
        self.assertIn("不许把 ⛔", self.text)
        self.assertIn("不许自己编数字", self.text)


if __name__ == "__main__":
    unittest.main()
