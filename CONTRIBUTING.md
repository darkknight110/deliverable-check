# 参与贡献

交付前体检（数据 / 方案 / 返工）。MIT 许可，欢迎 issue 和 PR。

## 本地跑起来

```bash
git clone https://github.com/darkknight110/deliverable-check.git
cd deliverable-check
pipx install git+https://github.com/darkknight110/deliverable-check.git
```

## 提交前必须跑

```bash
python -m unittest discover -s tests -v
```

CI 会跑同样的命令；本地绿了再提 PR。

## 约定

- **先有证据，再下结论**：新增检查项要能给出可复核的证据，不靠"感觉"。
- **失败要出声**：不确定就报错或警告，绝不静默放行。
- **诚实边界**：做不到的能力写进文档，不写成"已支持"。
- 检查项要么能给出**证据**，要么不要加；误报一次，门禁就会被关掉。

## 提交信息

`<type>(<scope>): <摘要>`，不超过 72 字；一个提交只做一件事。
