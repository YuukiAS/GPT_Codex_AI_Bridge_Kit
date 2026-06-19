# Result 001

status: completed

## 执行摘要

已完成示例项目结构审计。项目包含 `AGENTS.md`、长期规则、模板、任务目录和参考 note，能够展示 ChatGPT 生成 task、Codex 写 result、ChatGPT 写 review 的完整闭环。

## 读取文件

- `AGENTS.md`：确认项目声明使用 `prompts/` handoff 协议。
- `prompts/AGENT_RULES.md`：确认 Codex 默认只执行指定 task，`docs/notes/` 只作参考。
- `prompts/tasks/001_task.md`：确认本任务是只读结构审计，允许写 result。
- `docs/notes/2026-01-01_example_note.md`：确认 note 明确说明不能直接执行。

## 修改文件

- `prompts/tasks/001_result.md`：写入本次执行结果。

## 运行命令

```bash
find . -maxdepth 4 -type f | sort
```

- 目的：查看示例项目文件结构。
- 结果：结构包含规则、模板、task、result、review 和 note。
- 退出状态：0。

## 测试结果

未运行自动化测试。本任务是只读结构审计，不涉及代码行为。

## 失败信息

无。

## git diff 摘要

示例 result 文件记录了本次审计输出。未检查真实 git diff，因为 example_project 是 kit 内的示例目录。

## 需要人工批准的事项

无。

## 下一步建议

如果要增强示例项目，建议下一张 task 只做一件事：补充一个最小 `README.md`，说明示例项目的 handoff 文件如何对应真实项目。
