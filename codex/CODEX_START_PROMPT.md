# Codex Start Prompt

请按本项目的 handoff 协议执行指定任务。

## 固定读取顺序

1. 先读取项目根目录的 `AGENTS.md`。
2. 再读取 `prompts/AGENT_RULES.md`。
3. 再读取指定任务单：

```text
prompts/tasks/<id>_task.md
```

## 执行规则

- 必须遵守任务单里的 `允许动作` 和 `禁止动作`。
- 必须检查 YAML frontmatter 中的权限字段。
- 不能擅自扩大范围。
- 不能主动执行 `docs/notes/`，除非任务单显式引用某篇 note 作为背景材料。
- 如果任务单没有授权联网、上传、删除数据、运行昂贵任务或修改高风险配置，遇到这些需求时必须停止。
- 如果需要人工批准，先把需要批准的事项写入 result，不要继续执行。

## 结果回写

完成后必须写：

```text
prompts/tasks/<id>_result.md
```

result 必须包含：

- 执行摘要。
- 读取文件。
- 修改文件。
- 运行命令。
- 测试结果。
- 失败信息。
- 下一步建议。
- git diff 摘要。
- 需要人工批准的事项。

不要只在聊天里总结而不写 result 文件。

## 任务入口

本次要执行的任务是：

```text
prompts/tasks/<id>_task.md
```
