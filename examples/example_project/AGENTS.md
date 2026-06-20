# Example Project Agents

本示例项目采用 `prompts/` handoff 协议。

Codex 默认读取：

- `prompts/AGENT_RULES.md`
- `prompts/tasks/<task_key>.md`

Codex 完成后写：

- `results/<task_key>/result.md`
- 文件型产物写 `results/<task_key>/`，并在 result 中列出产物清单。

ChatGPT 复盘写：

- `results/<task_key>/review.md`

`docs/notes/` 和 `docs/wiki/` 只作参考，不直接执行。`docs/notes/` 不保存执行产物。
