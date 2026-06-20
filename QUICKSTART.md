# Quickstart

这是最短使用流程。

## 1. 初始化真实项目

先本地安装一次：

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
```

以后进入任意真实项目根目录，运行：

```bash
ai-bridge
```

也可以指定目标项目：

```bash
ai-bridge init --target /path/to/project
```

如果目标项目已经有同名模板文件，默认不会覆盖。需要覆盖时运行：

```bash
ai-bridge init --target /path/to/project --force
```

`ai-bridge` 默认会创建或更新 `AGENTS.md` 中的协议片段，并安装 repo-local Codex skill。ChatGPT/GitHub MCP 读取 `prompts/CHATGPT_RULES.md`，Codex 读取 `prompts/AGENT_RULES.md`。长期论文和报告知识写入 `docs/wiki/`；任务、实验和脚本产物写入 `results/<task_key>/`。

如果 ChatGPT 没有自动读取仓库规则，只需要在该 ChatGPT Project 的长期 instructions 里放一次：

```text
使用 GitHub MCP 处理仓库时，先读取 AGENTS.md 和 prompts/CHATGPT_RULES.md；需要 Codex 执行时写 prompts/tasks/<task_key>.md。task_key 采用 <id>_<short_slug>，short_slug 控制在 1-3 个词内。
```

以后日常不需要再记完整提示词。

## 2. 日常三句话

给 ChatGPT：

```text
读取 AGENTS.md 和 prompts/CHATGPT_RULES.md，根据当前项目状态生成新的 prompts/tasks/002_fix_ci.md。
```

给 Codex：

```text
读取 AGENTS.md、prompts/AGENT_RULES.md 和 prompts/tasks/002_fix_ci.md，按任务单授权执行，完成后写 results/002_fix_ci/result.md；如有文件型产物，写到 results/002_fix_ci/，并写 results/002_fix_ci/MANIFEST.md。
```

再给 ChatGPT：

```text
读取 prompts/tasks/002_fix_ci.md、results/002_fix_ci/result.md、results/002_fix_ci/MANIFEST.md 和必要产物，写 results/002_fix_ci/review.md，并判断下一步是 GO、STOP、NEEDS_EVIDENCE、NEEDS_HUMAN_APPROVAL 还是 OPEN_NEXT_TASK。
```

## 3. 研究笔记不要变成任务

如果只是研究笔记、方案分析、会议记录、文献总结、实验复盘或想法沉淀，给 ChatGPT：

```text
这只是后续参考，请写到 docs/notes/<date>_<topic>.md，不要生成 Codex task。
```

如果后来要执行 note 里的某个方向，再让 ChatGPT 从 note 中提炼一张新的 `prompts/tasks/<task_key>.md`。

## 4. 文件产物写入 results

如果 Codex 或脚本会生成日志、CSV/JSON、图、压缩包、评估表、长报告或中间输出，任务单应明确：

```text
执行报告写 results/<task_key>/result.md；文件型产物写 results/<task_key>/；产物索引写 results/<task_key>/MANIFEST.md；不要塞进 prompts/tasks/。
```

`results/<task_key>/result.md` 只记录摘要、证据、命令、失败信息、diff 摘要、`results/<task_key>/MANIFEST.md` 和产物清单。

## 5. 论文和 report 写入 wiki

如果仓库里有论文 PDF、论文 Markdown、报告或 Codex 生成的长 report，需要以后复用，不要每次临时重读。给 ChatGPT：

```text
读取 AGENTS.md、prompts/CHATGPT_RULES.md 和 docs/wiki/index.md，把这篇论文或 report 沉淀到 docs/wiki/，更新 index.md 和 log.md；如果要执行其中某个方向，再生成 prompts/tasks/<task_key>.md。
```

常见两步循环：

```text
先让 Codex 总结指定 report 并写 results/010_summarize_report/result.md；再让 ChatGPT 读取 prompts/tasks/010_summarize_report.md、result、MANIFEST 和 docs/wiki/index.md，写 review，必要时沉淀到 docs/wiki/，然后生成下一张 task。
```

## 6. 验证项目

```bash
ai-bridge validate --target /path/to/project
```

输出 `OK` 表示结构和任务文件基本合规。输出 `ERROR` 或 `WARN` 时，先修正路径、frontmatter 或命名，再交给 Codex 执行。
