---
task_id: "000"
project: "project-name"
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

用一句话说明 Codex 要完成的单一目标。

## 背景

说明为什么要做这件事，以及需要读取哪些项目材料。不要把长期研究笔记直接塞进任务；需要引用 note 时写明具体路径。

## 允许动作

- 读取与本任务直接相关的文件。
- 运行明确必要且低风险的 shell command。
- 按 frontmatter 授权进行文件修改。
- 完成后写 `prompts/tasks/000_result.md`。

## 禁止动作

- 不要联网，除非 `allow_network: true`。
- 不要上传任何内容，除非 `allow_external_upload: true`。
- 不要删除数据。
- 不要扩大到本任务之外的重构或优化。
- 不要主动执行 `docs/notes/` 中未被引用的内容。

## 预期产出

- `prompts/tasks/000_result.md`。
- 如有代码修改，包含修改文件列表和 diff 摘要。
- 如有命令运行，包含命令、目的和结果。

## 停止条件

- 缺少必要文件。
- 发现需要未授权动作。
- 命令失败且继续执行会扩大风险。
- 任务目标已经达到。

## 人工决策点

- 是否允许提升权限。
- 是否接受结果。
- 是否需要开下一张 task。
