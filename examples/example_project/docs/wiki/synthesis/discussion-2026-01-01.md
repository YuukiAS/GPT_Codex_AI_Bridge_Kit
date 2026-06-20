---
type: synthesis
date: 2026-01-01
topic: example handoff knowledge boundaries
confidence: high
---

# Discussion 2026-01-01

## 问题

示例项目为什么同时需要 `prompts/tasks/`、`docs/notes/` 和 `docs/wiki/`。

## 核心结论

- `prompts/tasks/` 是 Codex 可执行任务入口。
- `docs/notes/` 保存临时或半结构化参考笔记。
- `results/` 保存任务或实验生成的文件型产物。
- `docs/wiki/` 保存长期可复用知识，例如论文摘要、报告摘要、概念和综合讨论。

## 可执行后续

如果要把这条结论转成项目改动，应先生成新的 `prompts/tasks/<task_key>.md`。
