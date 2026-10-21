# 更新记录

## 1.0.0

首个可安装版本（`pipx install git+…`）。

- `preflight`：一个入口按类型分派（`.xlsx` / `.csv` / `.tsv` / `.md` / `.docx`），阻断时 `exit 1`
- `audit-data`：数据体检（小计混明细、文本数字、合计对不上、重复主键、空值率）
- `proposal-baseline` / `ai-flavor`：方案骨架与返工曲线，支持 `--redact`
- CLI 契约：`--version`、`--exclude`、`--max-files`
- CSV/TSV：自动识别 UTF-8 / GB18030（Excel 中文版导出）
- 演示：脏表被拦 → 修好通过（GIF + 四格故事板，CI 可重生成）
- 测试 45 项；CI 覆盖 Python 3.9/3.11/3.12/3.13 + 每日定时
