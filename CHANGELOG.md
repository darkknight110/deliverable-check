# 更新记录

## 1.0.2

- 发布到 PyPI：`pipx install deliverable-check`（README 安装命令同步更新）

## 1.0.1

- `preflight` 增加 Word 表格数值审计（合计混明细、带格式数字、合计对不上）
- 全部入口命令补 `--version`；`--lang en` 英文帮助
- 修 Windows 控制台非 UTF-8 时打印符号崩溃
- 发布流程加 `twine check`，上传前先验元数据

## 1.0.0

首个可安装版本（`pipx install git+…`）。

- `preflight`：一个入口按类型分派（`.xlsx` / `.csv` / `.tsv` / `.md` / `.docx`），阻断时 `exit 1`
- `audit-data`：数据体检（小计混明细、文本数字、合计对不上、重复主键、空值率）
- `proposal-baseline` / `ai-flavor`：方案骨架与返工曲线，支持 `--redact`
- CLI 契约：`--version`、`--exclude`、`--max-files`
- CSV/TSV：自动识别 UTF-8 / GB18030（Excel 中文版导出）
- 演示：脏表被拦 → 修好通过（GIF + 四格故事板，CI 可重生成）
- 测试 45 项；CI 覆盖 Python 3.9/3.11/3.12/3.13 + 每日定时
