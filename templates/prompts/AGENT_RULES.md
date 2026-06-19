# Agent Rules

本项目采用 `prompts/` handoff 协议。

## 默认入口

Codex 的默认任务入口是：

```text
prompts/tasks/<id>_task.md
```

长期执行规则在：

```text
prompts/AGENT_RULES.md
```

ChatGPT 通过 GitHub MCP 或仓库工具生成 task、note、review 时，应读取：

```text
prompts/CHATGPT_RULES.md
```

Codex 结果回写到：

```text
prompts/tasks/<id>_result.md
```

ChatGPT 复盘写到：

```text
prompts/tasks/<id>_review.md
```

`docs/notes/` 只保存参考笔记，不是默认任务入口。`docs/wiki/` 保存长期研究知识，包括论文摘要、报告摘要、概念、对比、gap 和综合讨论，也不是默认任务入口。只有 task 显式引用某篇 note 或 wiki 页面时，Codex 才能把它作为背景材料读取。

## 权限边界

Codex 必须遵守 task frontmatter：

- `allow_code_change`
- `allow_shell_command`
- `allow_network`
- `allow_external_upload`
- `requires_human_approval`

未授权的动作默认禁止。尤其不要自动联网、上传、删除数据、运行昂贵任务或修改高风险配置。

## 结果记录

每次执行 task 后，Codex 必须写 `prompts/tasks/<id>_result.md`，至少记录：

- 执行摘要。
- 读取文件。
- 修改文件。
- 运行命令。
- 测试结果。
- 失败信息。
- git diff 摘要。
- 需要人工批准的事项。
- 下一步建议。

## 证据要求

结论必须有证据。优先引用：

- 文件路径和行号。
- 命令和退出状态。
- 测试名称和结果。
- diff 摘要。
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
