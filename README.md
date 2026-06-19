# GPT-Codex AI Bridge Kit

这套 kit 解决的问题很具体：把 ChatGPT 和 Codex 之间反复复制粘贴长 prompt 的工作方式，改成一套固定文件协议。CLI 命令叫 `ai-bridge`，强调它是 GPT 和 Codex 之间的本地文件桥。

核心思路是让 ChatGPT 负责整理想法、计划、研究判断和复盘，让 Codex 只执行清晰、受控、可追踪的任务单。人类不需要每次重新组织一大段临时 prompt，只需要批准、否决、换方向，或者要求 ChatGPT 开下一张任务单。

## 核心目录

在真实项目中，本 kit 默认使用两类目录：

- `prompts/`：面向模型或 agent 的输入材料总目录。
- `prompts/tasks/`：可执行 handoff 任务目录，也是 Codex 默认唯一任务入口。
- `docs/notes/`：研究笔记、方案分析、会议记录、实验复盘等参考材料目录。
- `docs/wiki/`：长期研究知识库，用于沉淀论文摘要、报告摘要、概念、对比、gap 和综合讨论。

`docs/notes/` 和 `docs/wiki/` 都不直接驱动 Codex 执行。Codex 不应主动把这里的长文当任务做。如果某篇 note 或 wiki 结论后来需要落地，应先由 ChatGPT 提炼成新的 `prompts/tasks/<id>_task.md`。

## 核心循环

1. ChatGPT 生成任务单：
   `prompts/tasks/<id>_task.md`
2. Codex 读取任务单，按授权执行，并写回结果：
   `prompts/tasks/<id>_result.md`
3. ChatGPT 读取 task 和 result，生成复盘：
   `prompts/tasks/<id>_review.md`
4. 人类根据 review 批准、否决、停止、回滚、换方向，或要求生成下一张 task。

这个循环把“口头交代”变成了可审计文件：任务边界、允许动作、禁止动作、证据、命令、修改文件、失败信息和下一步判断都能留在项目里。

## Kit 内容

- `chatgpt/`：可直接复制给 ChatGPT 的提示词，用于写 task、note、review 和下一任务。
- `codex/`：可直接复制给 Codex 的启动提示词、`AGENTS.md` 片段和 repo-local skill。
- `templates/`：真实项目初始化时使用的规则和 Markdown 模板。
- `examples/example_project/`：一个完整闭环示例。
- `scripts/`：初始化和验证脚本，只使用 Python 标准库。

## 初始化到真实项目

如果想以后在任意仓库里用一个短命令部署，先在本机安装一次：

```bash
pip install -e /path/to/gpt-codex-ai-bridge-kit
```

之后进入任意真实项目根目录，运行一个词：

```bash
ai-bridge
```

它等价于初始化当前目录，并默认创建或更新 `AGENTS.md` 中的协议片段、`prompts/`、`docs/notes/` 和 repo-local Codex skill。

这里使用一个很薄的 CLI，而不是更复杂的服务或 MCP 编排。原因是这个工具包的核心资产是仓库里的 Markdown 协议文件；CLI 只负责把这些文件稳定部署到任意项目中。

也可以显式指定目标项目：

```bash
ai-bridge init --target /path/to/project
```

脚本会在目标项目中创建：

```text
AGENTS.md
prompts/
  AGENT_RULES.md
  CHATGPT_RULES.md
  templates/
  tasks/
docs/
  notes/
  wiki/
    index.md
    log.md
    papers/
    concepts/
    entities/
    comparisons/
    gaps/
    synthesis/
.agents/
  skills/
    agent-task-executor/
      SKILL.md
```

默认不会覆盖已存在文件。确实需要覆盖模板文件时再使用：

```bash
ai-bridge init --target /path/to/project --force
```

如果不想安装 CLI，也可以在本 kit 根目录运行兼容脚本：

```bash
python scripts/init_handoff_workspace.py --target /path/to/project
```

初始化后，项目内会包含给 ChatGPT/GitHub MCP 读取的 `prompts/CHATGPT_RULES.md`，以及给 Codex 读取的 `prompts/AGENT_RULES.md`。

## 验证真实项目

```bash
ai-bridge validate --target /path/to/project
```

验证脚本会检查：

- `AGENTS.md` 是否存在。
- `prompts/AGENT_RULES.md` 是否存在。
- `prompts/CHATGPT_RULES.md` 是否存在。
- `prompts/tasks/` 是否存在。
- `docs/notes/` 是否存在。
- `docs/wiki/` 和 `docs/wiki/index.md` 是否存在。
- `*_task.md` 是否包含 YAML frontmatter。
- task frontmatter 是否包含必要字段。
- `*_result.md` 和 `*_review.md` 命名是否能对应到已有 task。

发现问题时脚本会返回非零退出码，便于以后接入更严格的检查。

## 什么时候写 task，什么时候写 note

写 task 的情况：

- 需要 Codex 执行明确动作。
- 需要改代码、跑测试、检查日志、生成文件或做受控 shell command。
- 有明确停止条件和结果回写要求。

写 note 的情况：

- 只是研究分析、方案比较、会议记录、文献总结、想法沉淀或复盘。
- 还没有决定要 Codex 执行。
- 内容很长，不适合作为直接任务。

原则：note 可以成为 task 的背景材料，但 note 本身不是任务入口。

## 什么时候写 wiki

写 wiki 的情况：

- 仓库里有论文、报告或实验记录，需要以后反复引用。
- ChatGPT 或 Codex 生成了一个 report，值得沉淀成长期知识。
- 多篇论文之间需要对比、概念抽象、gap 梳理或假设管理。

默认写入 `docs/wiki/`。新增或更新 wiki 页面后，更新 `docs/wiki/index.md`，并 append `docs/wiki/log.md`。如果 wiki 中的某个方向要执行，再生成新的 `prompts/tasks/<id>_task.md`。

## 默认协议

本 kit 的默认协议是 `prompts/` 加 `docs/notes/`。如果某些项目偏好隐藏目录，可以自行改写模板，但建议先保持默认路径，直到团队已经稳定使用这套协议。
