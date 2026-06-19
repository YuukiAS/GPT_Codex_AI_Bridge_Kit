# ChatGPT + GitHub MCP Repository Instructions

当你通过 GitHub MCP 或类似仓库工具处理一个采用本 kit 的项目时，请先读取仓库内规则，不要临时发明 handoff 路径。

## 固定读取顺序

1. 读取仓库根目录 `AGENTS.md`。
2. 读取 `prompts/CHATGPT_RULES.md`。
3. 如果要让 Codex 执行，读取 `prompts/AGENT_RULES.md` 和现有 `prompts/tasks/`。
4. 如果只是参考背景，再读取用户明确指定的 `docs/notes/` 或 `docs/wiki/` 文件。

## 固定写入规则

- 可执行任务写到 `prompts/tasks/<id>_task.md`。
- Codex 结果预期写到 `prompts/tasks/<id>_result.md`。
- 复盘写到 `prompts/tasks/<id>_review.md`。
- 研究笔记、方案分析、会议记录和实验复盘写到 `docs/notes/<date>_<topic>.md`。
- 论文摘要、报告摘要、概念、方法对比、gap 和综合讨论写到 `docs/wiki/`。

## 不要做的事

- 不要把 `docs/notes/` 里的长文直接当 Codex task。
- 不要把 `docs/wiki/` 里的结论直接当 Codex task。
- 不要把 task 写到 issue、PR description 或聊天正文里作为唯一来源。
- 不要让 Codex 猜测 result 路径；task 必须明确要求写 `prompts/tasks/<id>_result.md`。
- 不要在没有用户要求时创建 GitHub issue、PR、label 或自动化 workflow。

## 任务生成规则

如果用户要求“开下一步”“让 Codex 做”“生成任务单”“handoff 给 Codex”，请生成一张小任务：

```text
prompts/tasks/<next_id>_task.md
```

这张 task 必须包含 YAML frontmatter，并写清楚允许动作、禁止动作、预期产出、停止条件和人工决策点。

如果 task 依赖论文或长期研究结论，应显式引用相关 `docs/wiki/` 页面，而不是要求 Codex 重新从 PDF 猜上下文。

## 复盘规则

如果用户要求检查 Codex 执行结果，请读取：

```text
prompts/tasks/<id>_task.md
prompts/tasks/<id>_result.md
```

然后写：

```text
prompts/tasks/<id>_review.md
```

review 必须给出 `GO`、`STOP`、`NEEDS_EVIDENCE`、`NEEDS_HUMAN_APPROVAL` 或 `OPEN_NEXT_TASK`。
