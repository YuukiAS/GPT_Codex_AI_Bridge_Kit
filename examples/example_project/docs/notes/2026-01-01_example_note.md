# 示例参考笔记：项目结构改进想法

date: 2026-01-01
type: note
status: reference

## 背景

这篇 note 展示 `docs/notes/` 的用途。它记录后续参考想法，但不直接驱动 Codex 执行，也不保存执行产物。

## 主要内容

一个可能的改进方向是给示例项目增加更清楚的 README，解释 `AGENTS.md`、`prompts/AGENT_RULES.md`、`prompts/tasks/` 和 `docs/notes/` 的关系。

## 判断与理由

示例项目越容易读懂，用户越容易把这套协议复制到真实项目。但这个想法不是当前任务，不能因为写在 note 里就让 Codex 自动执行。

## 风险与不确定性

如果 README 写得太长，可能让示例变复杂。更好的做法是保持短文档，只解释最小闭环。

## 如果以后要执行

请先让 ChatGPT 从这篇 note 提炼新的 `prompts/tasks/<task_key>.md`。Codex 只应执行那张 task，而不是直接执行本 note。

## 相关材料

- `prompts/tasks/001_structure_audit.md`：示例结构审计任务。
- `results/001_structure_audit/result.md`：示例 Codex result。
- `results/001_structure_audit/review.md`：示例 ChatGPT review。
- `results/<task_key>/`：示例协议中的文件型产物目录；本示例任务没有生成产物。
