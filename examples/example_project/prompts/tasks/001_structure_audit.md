---
task_key: "001_structure_audit"
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

# Task 001 Structure Audit

## 目标

审计示例项目结构，并提出最小改进建议。

## 背景

这是一个演示 handoff 协议的最小项目。任务只要求读取项目结构和现有 handoff 文件，不要求修改任何项目文件。

## 允许动作

- 读取 `AGENTS.md`、`prompts/AGENT_RULES.md`、`prompts/tasks/001_structure_audit.md` 和 `docs/notes/2026-01-01_example_note.md`。
- 运行低风险只读 shell command，例如列出文件树。
- 写 `results/001_structure_audit/result.md`。
- 写 `results/001_structure_audit/MANIFEST.md`。

## 禁止动作

- 不要修改除 `results/001_structure_audit/` 以外的文件。
- 不要联网。
- 不要上传。
- 不要删除数据。
- 不要执行 `docs/notes/` 中的想法；note 只能作为背景参考。

## 预期产出

- `results/001_structure_audit/result.md`，包含结构审计摘要、读取文件、运行命令、测试结果、失败信息、diff 摘要和一个最小改进建议。
- `results/001_structure_audit/MANIFEST.md`，索引本任务的 task、result、review 和关键产物。

## 停止条件

- 已完成结构审计并写入 result。
- 发现需要修改项目文件或联网。

## 人工决策点

- 是否接受最小改进建议。
- 是否由 ChatGPT 把建议提炼成下一张 task。
