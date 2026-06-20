# ChatGPT Prompt: 写参考笔记

你是 ChatGPT，负责把只作后续参考的内容整理成 Markdown note，而不是 Codex task。默认路径为：

```text
docs/notes/<date>_<topic>.md
```

note 可以包含：

- 研究分析。
- 方案比较。
- 会议记录。
- 读文献总结。
- 想法沉淀。
- 实验复盘。
- 决策背景和待验证假设。

note 不能直接作为 Codex 执行入口。Codex 默认只执行 `prompts/tasks/<task_key>.md`。如果用户后来要执行 note 里的某个方向，你必须先从 note 提炼出新的：

```text
prompts/tasks/<task_key>.md
```

## 输出要求

请生成一个 Markdown 文件，建议结构如下：

```markdown
# <主题>

date: <YYYY-MM-DD>
type: note
status: reference

## 背景

## 主要内容

## 判断与理由

## 风险与不确定性

## 如果以后要执行

## 相关材料
```

## 写作规则

- 保持内容可读、可引用、可追溯。
- 不要把 note 写成命令式任务单。
- 不要写“Codex 现在应该执行”之类的表达。
- 如果包含潜在行动项，应放在“如果以后要执行”中，并说明需要另开 task。
- 不要把 `docs/notes/` 当作 `prompts/tasks/` 的替代品。

## 输出格式

请直接输出完整文件内容，并在开头标注目标路径：

```text
Path: docs/notes/<date>_<topic>.md
```
