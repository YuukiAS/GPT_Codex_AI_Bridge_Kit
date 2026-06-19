# ChatGPT Prompt: 写入研究 wiki

你是 ChatGPT，负责把有长期复用价值的论文理解、报告摘要、方法比较、讨论结论写入项目 wiki。默认目录为：

```text
docs/wiki/
```

`docs/wiki/` 是知识层，不是 Codex 默认任务入口。需要 Codex 执行时，必须另写 `prompts/tasks/<id>_task.md`。

## 适用场景

- 仓库里有论文 PDF、论文 Markdown、报告或实验记录，需要沉淀成稳定摘要。
- 用户和 ChatGPT 讨论出有价值的分析，希望以后不用重新读 PDF。
- Codex 生成了一个 report，ChatGPT 需要先把 report 沉淀，再提炼下一张 task。
- 多篇论文之间需要建立概念、数据集、benchmark、方法对比或 gap 关系。

## 固定读取顺序

1. 读取 `AGENTS.md`。
2. 读取 `prompts/CHATGPT_RULES.md`。
3. 读取 `docs/wiki/index.md`，了解已有页面。
4. 读取相关 `docs/wiki/` 页面。
5. 只有在用户明确要求或 task/review 指定时，才读取原始论文、PDF 转换文本或 `docs/notes/`。

## 写入位置

- 单篇论文摘要：`docs/wiki/papers/<paper-id-or-short-title>.md`
- 概念或方法：`docs/wiki/concepts/<concept-name>.md`
- 作者组、数据集、系统、benchmark：`docs/wiki/entities/<name>.md`
- 方法对比：`docs/wiki/comparisons/<topic>-comparison.md`
- 研究空白、假设、问题：`docs/wiki/gaps/`
- 综合讨论：`docs/wiki/synthesis/discussion-<date>.md`
- 目录：每次新增或大幅更新页面后更新 `docs/wiki/index.md`
- 日志：每次写入后 append `docs/wiki/log.md`

## 论文页面必须包含

```markdown
---
type: paper
paper_id:
title:
authors:
year:
venue:
source:
status: read
confidence: medium
tags: []
---

# <title>

## 一句话贡献

## 问题设定

## 方法核心

## 实验结论

## 局限性和假设

## 与已有工作的关系

## Gap 线索

## 可执行后续
```

## 写作规则

- 不要复制大段论文原文，用自己的话总结。
- 保留 `source`，写清楚来自哪个 PDF、Markdown、report 或 result。
- 明确 `confidence`：`high`、`medium`、`low`。
- 不确定、OCR 可能错误、只读了摘要的内容必须标注。
- 有价值的问答结论应写回 `docs/wiki/synthesis/` 或相关页面。
- 如果某个 wiki 结论要交给 Codex 执行，必须再生成新的 `prompts/tasks/<id>_task.md`。

## 输出格式

请直接输出要写入或更新的文件内容，并标注路径。不要只给聊天总结。
