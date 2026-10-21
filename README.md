# deliverable-check · 交付前体检

> 三个体检工具，检查三类"看起来正常、其实错了"的交付物：
> **方案写得像不像样**、**稿子有没有 AI 味、改了多少轮**、**数据发出去之前算得对不对**。

全部是**可复跑的测量**，不是打分器。

| 工具 | 回答什么问题 | 产出 |
|---|---|---|
| [`tools/measure_proposals.py`](tools/measure_proposals.py) | 这份方案有多少骨架、多少证据、多少断言？ | 结构/行文基线 JSON + [基线报告](docs/proposal-baseline.md) |
| [`tools/measure_ai_flavor.py`](tools/measure_ai_flavor.py) | 稿子哪些标记在退化？21 个版本到底改了什么？ | 标记密度 + [返工曲线](docs/ai-flavor.md) |
| [`tools/audit_data.py`](tools/audit_data.py) | 这个 Excel 发出去会不会被算错？ | 阻断/警告清单 + [体检报告](docs/data-audit.md)，`exit 1` 可接 CI |

---

## 快速开始

```bash
# 1. 方案基线：量一批 Markdown
python3 tools/measure_proposals.py --out docs/proposal-baseline.json ../项目方案

# 2. AI 味与返工：量一个目录里的 .md/.docx（有版本号会自动串成版本链）
python3 tools/measure_ai_flavor.py --out docs/ai-flavor.json 某项目/导出

# 3. 数据体检：交付前跑一次，阻断即退出码 1
python3 tools/audit_data.py 交付表.xlsx --key-col 订单号
```

零第三方依赖？不完全是：`audit_data` 需要 `openpyxl`，其余两个只用标准库。

---

## 三个已量出来的结论

1. **方案的信息在表里**：34 份完整方案，中位 3,517 字 / 12 个二级章节 / **182 行表格** / 每千字 **82.5** 个数字；但只有 **32%** 写了验收指标、**6%** 写了报价。
2. **返工集中在前 30% 的版本**：一份设计方案改了 21 版、字数 +141%，前 6 次改动平均 5.1%，后 14 次只有 1.7%。第 8 版以后还在逐句润色，边际收益很低。
3. **"禁破折号"是错的**：21 个版本里破折号密度 **+49%**，而真正下降的是黑话密度（**−45%**）和句长（**−36%**）。判据要用数据校准，不能照搬。

---

## 数据体检能拦住什么

在一张"看起来正常"的脏表上（[可现场生成](tools/make_dirty_fixture.py)）：

```
⛔ 明细区里有 2 行小计/合计
⛔ 6 个单元格是「带千分位的文本数字」
⛔ 「金额（元）」整列求和会放大到 2.76 倍
⛔ 「金额（元）」的合计与明细对不上（差 20,500.50）
   结论：不可交付        （退出码 1）
```

而在真实的损益表上，它给出 **0 条阻断**（汇总表会降级为提示）——**不误报**和**不漏报**同样重要。

---

## 测试

```bash
python3 -m unittest discover -s tests -v
```

25 个用例，覆盖：三类事故的检出、干净表不误报、比率列跳过、标记计数、版本排序与返工量。

---

## 边界

- 方案基线来自**自有语料**（6 个项目），不代表行业普遍水平；版本未去重。
- AI 味只给**可测信号**，不判断"像不像人"；经验层（真实细节）测不出来，只能靠人补。
- 数据体检只覆盖 `.xlsx`，只做可机械判定的检查，不替代业务口径评审。
- 三份文档的「边界」一节比结论更重要，建议先读那一节。

---

## 相关

- **[devflow-kit](https://github.com/darkknight110/devflow-kit)** —— 把"交付前必须过门禁"做成流程；本工具的 `exit 1` 可直接挂上去。
- **[md-to-office](https://github.com/darkknight110/md-to-office)** —— 方案最终要变成 Word/PDF，它负责排版与架构图替换。

MIT。
