# 把数据体检接进 devflow 门禁

这个目录是可运行的示例：一个 `data` 门禁，**干净表通过、脏表阻断**，而且阻断时记录里有
`exit≠0` + `FAIL data-audit blocked` 两条证据。

```bash
# 需要 devflow-kit；DEVFLOW 指向它的 bin/devflow
DEVFLOW=../devflow-kit/bin/devflow bash examples/devflow-gate/verify.sh
```

实际输出（2026-10-21）：

```
== 1. init + doctor
  [OK] doctor：门禁可用（负向对照生效）
== 3. 干净数据：门禁应通过
  [OK] 通过，且负向对照被验证
== 4. 脏数据：门禁必须阻断
exit=1 command=./scripts/data-gate.sh
tail=FAIL data-audit blocked: 4 blocking findings
  [OK] 阻断，且记录里有 exit≠0 + FAIL 证据
通过 5 项，失败 0 项
```

## 怎么接到你自己的项目

1. 把 `tools/audit_data.py` 复制到项目的 `scripts/audit_data.py`（**单文件、无私有依赖**，只需 `openpyxl`）。
2. 复制两个包装脚本，改掉里面的文件名：
   - `scripts/data-gate.sh` —— 跑**要交付的那张表**，0 = 可交付
   - `scripts/data-should-fail.sh` —— 跑**脏表哨兵**，必须非零
3. 在 `devflow.json` 里声明：

```json
{
  "gates": {
    "data": {
      "run": "./scripts/data-gate.sh",
      "negative_control": "./scripts/data-should-fail.sh"
    }
  }
}
```

4. `devflow doctor` → 结论必须是「门禁可用」；`devflow gate run <变更>` → 干净表 PASS、脏表 BLOCKED。

## 三个容易踩的坑

| 坑 | 现象 | 修法 |
|---|---|---|
| 负向对照写成"一定失败的命令"（如 `false`） | doctor 报「输出中无 FAIL/AssertionError/失败计数」 | 哨兵必须是**真实的脏数据**，让工具自己报出 `FAIL` |
| 只判退出码，不要求失败证据 | 门禁看似生效，其实可能因"文件不存在"而退出 1 | `audit_data.py` 在阻断时会打印 `FAIL data-audit blocked: N ...` |
| 把汇总表当明细表体检 | 真实损益表被误判"不可交付" | 汇总表会被降级为提示；比率列自动跳过 |

> 为什么不用 `count_regex`：数据体检没有"测试数"，只认退出码 + 失败证据。
> 这是 devflow 允许的形态（`G2` 只要求命令原文/退出码/输出尾部），但**负向对照不能省**。
