# Agent Rules

本示例项目采用 `prompts/` handoff 协议。

## 默认入口

Codex 只从明确指定的 `prompts/tasks/<id>_task.md` 开始执行。`docs/notes/` 和 `docs/wiki/` 是参考目录，不是任务入口。

## 权限边界

Codex 必须遵守 task frontmatter。没有授权时，不得联网、上传、删除数据、运行昂贵命令或修改高风险配置。

## 结果记录

Codex 必须写 `prompts/tasks/<id>_result.md`，记录读取文件、修改文件、命令、测试、失败信息、diff 摘要和下一步建议。

## 证据要求

结论需要引用具体文件、命令或检查结果。不确定内容必须标明不确定性。

## 失败处理

如果无法完成，停止扩大范围，并在 result 中写明缺少什么、失败在哪里、是否需要人工批准。
