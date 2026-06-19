# ChatGPT Rules

本示例项目采用 `prompts/` handoff 协议。ChatGPT 通过 GitHub MCP 或仓库工具处理本项目时，应先读取 `AGENTS.md` 和本文件。

## 写入位置

- 可执行任务写到 `prompts/tasks/<id>_task.md`。
- Codex result 预期写到 `prompts/tasks/<id>_result.md`。
- ChatGPT review 写到 `prompts/tasks/<id>_review.md`。
- 参考笔记写到 `docs/notes/<date>_<topic>.md`。
- 长期知识写到 `docs/wiki/`。

## 边界

`docs/notes/` 和 `docs/wiki/` 不是 Codex 任务入口。如果要执行其中的方向，先提炼新的 task。
