#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_ai_flavor 的单元测试：标记可数、版本可排序、返工量可算。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from deliverable_check import measure_ai_flavor as af  # noqa: E402


class TestMetrics(unittest.TestCase):
    def test_黑话按每千字归一(self):
        text = "我们要赋能业务，形成闭环，打造生态。" * 10
        m = af.metrics(text)
        self.assertGreater(m["lexical"]["管理黑话"], 20)
        self.assertGreater(m["lexical_per_1k"]["管理黑话"], 50)

    def test_破折号计数(self):
        m = af.metrics("这不是优化——这是重做。")
        self.assertEqual(m["lexical"]["破折号"], 1)

    def test_抽象句比例(self):
        # 第一句无数字无专名无引号；第二句有数字
        text = "我们要提升整体效率。二期在 2026 年上线。"
        m = af.metrics(text)
        self.assertAlmostEqual(m["abstract_ratio"], 0.5, places=2)

    def test_空文本不炸(self):
        m = af.metrics("")
        self.assertEqual(m["chars"], 0)
        self.assertEqual(m["abstract_ratio"], 0)


class TestVersioning(unittest.TestCase):
    def test_版本号解析(self):
        self.assertEqual(af.version_key("今天吃啥不麻烦设计方案_V1.20.docx"), (1, 20))
        self.assertEqual(af.version_key("今天这一顿设计方案_V1.0.docx"), (1, 0))
        self.assertIsNone(af.version_key("交接卡片.md"))

    def test_文档类型归组(self):
        self.assertEqual(af.doc_family("今天吃啥呀设计方案_V1.7.docx"), "设计方案")
        self.assertEqual(af.doc_family("吃啥不麻烦施工手册_V1.2.docx"), "施工手册")

    def test_版本链按版本号排序而不是字典序(self):
        docs = [
            {"name": "x设计方案_V1.10.docx", "family": "设计方案", "version": (1, 10), "text": "abcdefghij"},
            {"name": "x设计方案_V1.9.docx", "family": "设计方案", "version": (1, 9), "text": "abcdefghi"},
            {"name": "x设计方案_V1.2.docx", "family": "设计方案", "version": (1, 2), "text": "abcdef"},
        ]
        chains = af.chain_analysis(docs)
        self.assertEqual(chains[0]["versions"], ["x设计方案_V1.2.docx", "x设计方案_V1.9.docx", "x设计方案_V1.10.docx"])

    def test_返工量在完全相同与完全不同之间(self):
        same = af.chain_analysis([
            {"name": "a设计方案_V1.0.docx", "family": "设计方案", "version": (1, 0), "text": "同样的内容"},
            {"name": "a设计方案_V1.1.docx", "family": "设计方案", "version": (1, 1), "text": "同样的内容"},
        ])
        self.assertEqual(same[0]["steps"][0]["rewrite_share"], 0.0)
        diff = af.chain_analysis([
            {"name": "b设计方案_V1.0.docx", "family": "设计方案", "version": (1, 0), "text": "甲乙丙丁"},
            {"name": "b设计方案_V1.1.docx", "family": "设计方案", "version": (1, 1), "text": "戊己庚辛"},
        ])
        self.assertGreater(diff[0]["steps"][0]["rewrite_share"], 0.8)


if __name__ == "__main__":
    unittest.main()
