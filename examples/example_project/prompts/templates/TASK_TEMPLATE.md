---
task_id: "000"
project: "example_project"
status: "ready"
executor: "Codex"
risk_level: "low"
allow_code_change: false
allow_shell_command: true
allow_network: false
allow_external_upload: false
requires_human_approval: false
---

# Task 000

## 目标

完成一个小而明确的项目内任务。

## 背景

说明任务来源和范围。

## 允许动作

- 读取相关文件。
- 运行低风险 shell command。
- 写 result 文件。

## 禁止动作

- 不要联网。
- 不要上传。
- 不要删除数据。
- 不要扩大范围。

## 预期产出

- `prompts/tasks/000_result.md`

## 停止条件

- 目标完成。
- 需要未授权动作。

## 人工决策点

- 是否接受结果。
- 是否开下一张 task。
