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

## 7. 可选：选择更重的 workflow

日常默认是 Lite，也就是 `ai-bridge init` / `ai-bridge validate` 安装的基础交接。

如果需要 GPT 先规划、Codex 执行、再由 GPT 独立复核，使用 Review。命令仍保持兼容名称：

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

如果任务属于高风险科研、生产或安全敏感工作，且需要严格多角色控制与验证，使用 Control。命令仍保持兼容名称：

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

## 8. 可选：同步论文目录到 Overleaf

如果项目是科研 monorepo，Codex 仍应在整个 repository 根目录工作；Overleaf 只应接收论文 publication root，例如 `paper/manuscript`。Overleaf 本身不能从一个 GitHub monorepo 中只 Pull 某个子目录，Overleaf Bridge 是在本机把该目录投影到 Overleaf Git project。

```bash
ai-bridge overleaf install \
  --target /path/to/research-repo \
  --paper-root paper/manuscript
```

在 Overleaf 创建 Blank Project、删除默认 `main.tex` 并取得 Git URL 后：

```bash
ai-bridge overleaf connect \
  --target /path/to/research-repo \
  --remote-url https://git@git.overleaf.com/<PROJECT_ID> \
  --bootstrap
```

新旧 Overleaf 项目可能使用不同默认分支。Bridge Kit 会在 `connect` 时读取
Overleaf Git remote 实际声明的分支，不需要也不应该在科研仓库配置
`main/master`。

日常使用：

```bash
ai-bridge overleaf status --target /path/to/research-repo
ai-bridge overleaf push --target /path/to/research-repo
ai-bridge overleaf pull --target /path/to/research-repo
ai-bridge overleaf validate --target /path/to/research-repo
```

`push` 会拒绝覆盖未拉取的 Overleaf 远端修改；`pull` 会把 Overleaf 改动留在本地 working tree，不会自动 commit 或 `git push origin main`。Overleaf token 由 Git credential helper 处理，不写入 Bridge Kit config。

同步前先让非 excluded 的 `paper_root` 保持 clean：tracked、staged、deleted、renamed 或 untracked manuscript 文件都应先 review/compile/commit，避免未提交草稿被用作 baseline 或被 pull 覆盖。`exclude_paths` 只用于不参与 Overleaf 编译的 GitHub-only 文件；编译需要的 `.tex`、`.bib`、figures、tables 和 style/class 文件必须留在 publication projection 中。

每台机器的 `connection.json` 和 `mirror/` 都在 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/`，不提交到 GitHub；多台机器要各自 `connect`。Overleaf Bridge 不会自动同步，local 和 Overleaf 双边变化时会 fail closed。
