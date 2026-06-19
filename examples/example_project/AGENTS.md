# Example Project Agents

本示例项目采用 `prompts/` handoff 协议。

Codex 默认读取：

- `prompts/AGENT_RULES.md`
- `prompts/tasks/*_task.md`

Codex 完成后写：

- `prompts/tasks/*_result.md`

ChatGPT 复盘写：

- `prompts/tasks/*_review.md`

`docs/notes/` 和 `docs/wiki/` 只作参考，不直接执行。
