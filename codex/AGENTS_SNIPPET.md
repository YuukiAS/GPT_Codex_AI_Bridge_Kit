# Handoff Protocol

本项目采用 `prompts/` handoff 协议，用于 ChatGPT 和 Codex 之间的文件化交接。

## 默认入口

- `prompts/AGENT_RULES.md`：长期执行规则。
- `prompts/CHATGPT_RULES.md`：ChatGPT 通过 GitHub MCP 或仓库工具写 task、note、review 时应读取的规则。
- `prompts/tasks/<task_key>.md`：唯一默认任务入口；`task_key` 使用 `<id>_<short_slug>`，short slug 控制在 1-3 个词内。
- `results/<task_key>/result.md`：Codex 的执行报告和证据索引。
- `results/<task_key>/review.md`：ChatGPT 的复盘位置。
- `docs/notes/`：参考笔记、方案分析、会议记录和讨论沉淀，不是默认任务入口。
- `results/<task_key>/`：Codex、脚本或实验生成的文件型产物目录；目录名必须与 task 文件名完全一致。
- `docs/wiki/`：长期研究知识库，不是默认任务入口。

## Codex 行为规则

- Codex 开始任务前应读取 `prompts/AGENT_RULES.md` 和指定的 `prompts/tasks/<task_key>.md`。
- Codex 必须遵守 task frontmatter、允许动作、禁止动作和停止条件。
- Codex 完成后必须写 `results/<task_key>/result.md`；如果生成日志、表格、图、导出包、长报告或中间输出，写入同名 `results/<task_key>/`，写 `results/<task_key>/MANIFEST.md`，并在 result 中列出产物清单。
- Codex 不应主动执行 `docs/notes/` 或 `docs/wiki/` 中的内容，除非任务单显式引用某篇 note 或 wiki 页面作为背景材料。
- 如果任务需要联网、上传、删除数据、运行昂贵命令或修改高风险配置，但 task 没有授权，Codex 必须停止并在 result 中请求人工批准。

## ChatGPT / GitHub MCP 行为规则

- ChatGPT 通过 GitHub MCP 处理本仓库时，应先读取 `AGENTS.md` 和 `prompts/CHATGPT_RULES.md`。
- 需要 Codex 执行的内容必须写成 `prompts/tasks/<task_key>.md`。
- 只作参考的研究分析、方案比较、会议记录和复盘应写到 `docs/notes/`。
- 执行产生的文件型产物应写到同名 `results/<task_key>/`，并用 `results/<task_key>/MANIFEST.md` 反向链接 task/result/review；不要塞进 `prompts/tasks/` 或 `docs/notes/`。
- 有长期复用价值的论文摘要、报告摘要、概念、对比、gap 和综合讨论应写到 `docs/wiki/`。
- ChatGPT 不应把 issue、PR description 或聊天正文当作 Codex 的唯一任务来源。
