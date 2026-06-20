# Agent Rules

本项目采用 `prompts/` handoff 协议。

## 默认入口

Codex 的默认任务入口是：

```text
prompts/tasks/<task_key>.md
```

`task_key` 必须使用 `<id>_<short_slug>`，其中 `short_slug` 控制在 1-3 个词内，用下划线连接，例如 `002_fix_ci`、`20260620_t2_edema_pilot`。新任务文件位于 `prompts/tasks/`，不再追加 `_task` 后缀。

长期执行规则在：

```text
prompts/AGENT_RULES.md
```

ChatGPT 通过 GitHub MCP 或仓库工具生成 task、note、review 时，应读取：

```text
prompts/CHATGPT_RULES.md
```

Codex 执行报告写到同名 results 目录：

```text
results/<task_key>/result.md
```

任务、实验、审计或脚本生成的文件型产物也写到同名目录：

```text
results/<task_key>/
```

ChatGPT 复盘写到：

```text
results/<task_key>/review.md
```

`prompts/tasks/<task_key>.md` 只保存任务单。`results/<task_key>/result.md` 是执行报告和证据索引。需要保存日志、表格、图、导出包、长报告或中间输出时，必须写入同名 `results/<task_key>/`，并在 result 中列出路径、生成命令和用途。

对应关系必须保持一眼可查：

```text
prompts/tasks/<task_key>.md
results/<task_key>/result.md
results/<task_key>/review.md
results/<task_key>/MANIFEST.md
```

如果创建了 `results/<task_key>/`，必须同时写或更新 `results/<task_key>/MANIFEST.md`，至少包含 task、result、review 的相对路径以及该目录下每个关键产物的用途。不要把其他 task 的产物混进同一个 `results/<task_key>/`。

`docs/notes/` 只保存参考笔记、方案分析、会议记录和讨论沉淀，不保存执行产物，也不是默认任务入口。`docs/wiki/` 保存长期研究知识，包括论文摘要、报告摘要、概念、对比、gap 和综合讨论，也不是默认任务入口。只有 task 显式引用某篇 note 或 wiki 页面时，Codex 才能把它作为背景材料读取。

## 权限边界

Codex 必须遵守 task frontmatter：

- `allow_code_change`
- `allow_shell_command`
- `allow_network`
- `allow_external_upload`
- `requires_human_approval`

未授权的动作默认禁止。尤其不要自动联网、上传、删除数据、运行昂贵任务或修改高风险配置。

## 结果记录

每次执行 task 后，Codex 必须写 `results/<task_key>/result.md`，至少记录：

- 执行摘要。
- 读取文件。
- 修改文件。
- 运行命令。
- 测试结果。
- 失败信息。
- git diff 摘要。
- `results/<task_key>/` 产物清单和 `results/<task_key>/MANIFEST.md` 路径；没有额外文件型产物时写“无”。
- 需要人工批准的事项。
- 下一步建议。

## 证据要求

结论必须有证据。优先引用：

- 文件路径和行号。
- 命令和退出状态。
- 测试名称和结果。
- diff 摘要。
- `results/<task_key>/` 中的产物路径。
- 明确的错误信息。
- 被 task 显式引用的 `docs/wiki/` 页面。

不确定的判断必须标明不确定性，不要写成事实。

## 失败处理

如果任务无法安全完成，Codex 应停止扩大范围，并在 result 中说明：

- 已完成什么。
- 卡在哪里。
- 缺少什么权限或材料。
- 是否需要人工批准。
- 建议下一张 task 解决什么单一问题。

## 人工审批机制

以下动作需要 task 显式授权；没有授权时必须停止并请求人工批准：

- 联网、下载依赖或调用外部 API。
- 上传文件、日志、数据或结果。
- 删除数据。
- 运行高成本、长时间或高资源命令。
- 修改安全、权限、部署、生产或数据迁移配置。
