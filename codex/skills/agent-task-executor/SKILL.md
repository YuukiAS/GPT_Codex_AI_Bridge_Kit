# Agent Task Executor

这个 skill 是通用 Codex 执行规程。它可以复制到真实项目：

```text
.agents/skills/agent-task-executor/SKILL.md
```

它不代表某个具体项目任务，只规定如何执行 `prompts/tasks/*_task.md`。

## 触发条件

当用户要求执行某个 handoff task，或任务路径形如：

```text
prompts/tasks/<id>_task.md
```

使用本规程。

## 执行流程

1. 读取项目根目录 `AGENTS.md`，如果存在。
2. 读取 `prompts/AGENT_RULES.md`。
3. 读取指定 `prompts/tasks/<id>_task.md`。
4. 检查 YAML frontmatter。
5. 核对权限字段。
6. 执行任务单中明确授权的动作。
7. 记录读取文件、修改文件、命令、输出摘要、测试结果和失败信息。
8. 写回 `prompts/tasks/<id>_result.md`。
9. 在最终回复中简短说明 result 文件已写入。

## 必查 frontmatter 字段

任务单至少应包含：

```yaml
task_id: "002"
project: "project-name"
status: "ready"
executor: "Codex"
risk_level: "low"
allow_code_change: true
allow_shell_command: true
allow_network: false
allow_external_upload: false
requires_human_approval: false
```

如果字段缺失，应先停止执行，并把缺失字段写入 result 或直接向用户说明无法安全执行。

## 权限解释

- `allow_code_change: false`：不得修改代码或项目文件，只能只读检查，除非 result 文件本身是任务要求的输出。
- `allow_shell_command: false`：不得运行 shell command。
- `allow_network: false`：不得联网、下载依赖、调用外部 API。
- `allow_external_upload: false`：不得上传文件、日志、数据或结果到外部服务。
- `requires_human_approval: true`：执行前必须获得人工批准。

## 禁止行为

- 不要自动上传任何内容。
- 不要删除数据，除非任务单明确授权且风险可控。
- 不要运行任务单未授权的昂贵命令、长时间任务或高资源任务。
- 不要修改高风险配置，除非任务单明确授权。
- 不要把不确定结论写成事实。
- 不要主动把 `docs/notes/` 或 `docs/wiki/` 当作任务执行。
- 不要只在聊天里总结而不写 result 文件。

## result 文件要求

写入：

```text
prompts/tasks/<id>_result.md
```

建议结构：

```markdown
# Result <id>

status: completed

## 执行摘要

## 读取文件

## 修改文件

## 运行命令

## 测试结果

## 失败信息

## git diff 摘要

## 需要人工批准的事项

## 下一步建议
```

## 失败处理

如果遇到以下情况，应停止扩大执行范围：

- 权限字段缺失或互相矛盾。
- task 要求的动作未被 frontmatter 授权。
- 需要联网、上传、删除、昂贵任务或高风险配置改动。
- 关键文件不存在。
- 测试或命令失败，且继续执行可能掩盖问题。

停止后仍应写 result，说明失败点、已完成证据、未完成原因和需要人工决策的事项。
