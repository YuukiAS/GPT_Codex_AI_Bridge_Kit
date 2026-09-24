# GPT-Codex AI Bridge Kit

这是一个用来组织 **ChatGPT/GPT 与 Codex 协作** 的本地工具包。

它解决的问题很实际：项目做久以后，真正麻烦的往往不是“让 Codex 写代码”，而是怎么让不同机器上的 Codex 遵守同一套长期规则，怎么把 GPT 的规划稳定交给 Codex，怎么在重要任务结束前增加独立复核，以及怎么把论文、通知、视觉检查这些能力接进现有科研仓库，而不是每个项目重新搭一套脚手架。

这个仓库的原则是：**默认保持简单，需要什么再加什么。** 普通项目通常只需要机器级规则和基础交接；只有确实需要时，才启用独立复核、高风险闭环、长期运行、通知、Overleaf 同步或视觉/文本复核。

当前集成版本：`0.9.1`（Reviewed Mode first-bootstrap normal entry 已完成候选实现；这不是 GitHub release/tag 声明）。

## 一眼看懂：我到底该装什么

整个工具包分成三层：

```text
机器层：一台机器 / 一个 CODEX_HOME 配一次
└── Machine Policy

项目层：每个 Git 仓库按需安装
├── Lite                 基础 GPT ↔ Codex 交接，默认推荐
├── Reviewed Mode        GPT 先规划，Codex 执行，再由 GPT 独立复核
├── Controlled Mode      高风险任务的严格闭环
├── Persistent Run       长期 Goal 的 tmux 持久执行能力
├── Notifications        任务结束或运行层进展后发通知
├── Overleaf Bridge      只把论文目录同步到 Overleaf
├── Visual Review        对图片、PPT 截图等做独立视觉检查
└── Text Review / Transform

任务层：某一次具体工作的实例
├── Lite 任务
├── Reviewed Mode 任务
└── Controlled Mode 任务
```

绝大多数新项目建议从这里开始：

```text
Machine Policy + Lite
```

不要因为项目大、文件多、运行时间长，就自动启用 Control。是否需要更重的流程，取决于“错误通过的代价”，而不是代码行数。

## 三档工作模式

```text
Lite
最轻量，普通任务默认使用

Reviewed Mode
GPT 先规划，Codex 执行，再由 GPT 独立复核

Controlled Mode
高风险任务的严格多角色控制与验证
```

这些是面向用户讨论和选择 workflow 时使用的显示名称。具体命令仍保持兼容：Reviewed Mode 使用 `ai-bridge reviewed-handoff ...`，Controlled Mode 使用 `ai-bridge agent-flow ...`。机器级能力当前显示为 **Machine Policy**，兼容命令仍是 `ai-bridge host ...`。

## 版本演进

本表是 README 中唯一的版本历史摘要。它回答“每个版本增加或改变了什么”；后面的功能章节只说明当前怎么使用。

| 版本 | 新增 / 主要变化 | 用户实际得到什么 |
|---|---|---|
| `0.1.0` | Lite Handoff、任务文件、执行结果和基础初始化/验证入口。 | 可以用 `prompts/tasks/<task_key>.md` 和 `results/<task_key>/result.md` 做最基础的 GPT -> Codex -> GPT 交接。 |
| `0.2.0` | Machine Policy 成为机器级配置层。 | 可以用 `ai-bridge host install/status/validate` 管理 `$CODEX_HOME`，把机器规则和项目初始化分开。 |
| `0.2.1` | Host Policy 用户叙述改为中文优先。 | Codex 给用户看的进度、计划和结果默认更符合中文工作流。 |
| `0.3.0` | Generic Notifier。 | 可以通过结构化 brief 发送一次性终态邮件，并保留 Lite 兼容。 |
| `0.3.1` | Notifier 邮件中文优先。 | 通知邮件对中文用户更直接，同时保留 task key、路径、branch 等技术字面量。 |
| `0.4.0` | Controlled Mode / Agent-Flow。 | 高风险任务可以使用 Planner、Critic、Controller、Verifier、Executor 的严格闭环。 |
| `0.5.0` | Reviewed Mode。 | 可以让 GPT 先冻结方案，Codex 执行，再由 GPT 最多两轮独立复核。 |
| `0.5.1` | Host Policy Git 授权语义和 External GPT 等待规则。 | 普通当前分支开发更顺，外部 Planner/Reviewer/Critic 的正常等待不会被误判为失败。 |
| `0.5.2` | Visual Review。 | 图片、PPT 截图、视觉结果可以生成独立可验证的视觉证据。 |
| `0.5.3` | Visual Review GitHub Actions 安装和 evidence writeback 加固。 | 视觉复核能在 consumer 仓库更稳定地安装、触发和写回证据。 |
| `0.5.4` | Visual Review 默认模型更新。 | 未显式覆盖模型时，视觉复核使用当前统一默认模型。 |
| `0.6.0` | Overleaf Bridge。 | 科研 monorepo 中 Codex 仍读整个仓库，但只把论文目录安全同步到 Overleaf。 |
| `0.6.1` | Lite / Review / Control 显示名、Text Review / Text Transform、Production Plugin Replay、Review watcher lifecycle/status、Notifier ownership hardening。 | 私有文本可加密复核/转换；插件可受控本机回归；Review watcher 和通知边界更清楚。 |
| `0.7.0` | Goal Fidelity / anti-degradation。 | 完成声明必须对应原始目标，不能把降级替代、窄证据或 blacklist-only 检查包装成完整完成。 |
| `0.7.1` | Review Plan V2 与历史 V1 兼容。 | 新冻结方案必须包含 Goal Fidelity contract，旧 frozen Plan 不必迁移也能继续验证。 |
| `0.7.2` | Slurm 只读 inspection 低打扰规则。 | 直接 `squeue`、`sinfo`、`sacct`、`sstat`、`sprio`、`scontrol show ...` / `ping` 不再反复审批，调度器/任务 mutation 仍审批。 |
| `0.7.3` | 低风险 unattended diagnostics 误拒绝修正。 | 直接 `ps`、`git fetch --all --prune`、`tmux ls/list-sessions/has-session` 可低打扰执行，process/tmux mutation 仍审批。 |
| `0.8.0` | Persistent Run。 | 长期 Goal 可以通过明确 kickoff、canonical tmux、lock/heartbeat/checkpoint/resume evidence 持久运行。 |
| `0.8.1` | Persistent Run authoring 和启动前授权 preflight。 | GPT 写长期 Goal 时必须说明 backend、run key、资源边界和完成标准；Codex 启动前会检查当前用户授权。 |
| `0.8.2` | Text Review 付费复核预算收窄 contract。 | 私有文本复核可以绑定更严格的 call count、费用、模型和 retry 边界，超界前默认失败。 |
| `0.8.3` | Lite fresh-repo scaffold、root `AGENTS.md` 保留和 fallback versioning。 | 新仓库初始化更干净，已有根规则不被误覆盖。 |
| `0.8.4` | Reviewed Handoff 语义 task key。 | 新 Review 任务默认用 `<scope-token>--<goal-token>`，历史编号任务仍可读取和验证。 |
| `0.8.5` | Default-mode required human gate transport 修正。 | 必需人工输入使用 durable transcript wait/resume，不依赖会自动 resolve 的默认模式问题卡。 |
| `0.9.0` | 低打扰操作收口：current-repo safe reads、GitHub HTTPS bounded publisher、Reviewed worktree materializer、Persistent Run progress/ETA/stalled、Notifications operational progress。 | 安全原生命令更少被误拦；GitHub HTTPS 普通发布和冻结 Review worktree 有受边界约束入口；SSH/custom、危险 Git、自动控制和语义 PASS 仍不被放权。 |
| `0.9.1` | Reviewed Mode first bootstrap normal entry。 | brand-new Reviewed task 可以通过 `ai-bridge reviewed-handoff task bootstrap` 创建 exact reviewed branch/worktree 和首份 REQUEST/CURRENT；existing task resume 继续走 artifact-bound `materialize-worktree`，raw `git worktree add` 仍不作为正常 fallback。 |

本项目采用 `0.x` 迭代方式。每个 `0.x` 小版本通常代表一项可独立使用的能力进入稳定工作流；补丁版本主要用于安全性、兼容性和默认行为修正。这不是严格的 Semantic Versioning 承诺，而是当前阶段的版本阅读方式。

## Machine Policy：先配置 Codex 的长期规则

先安装本仓库：

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
```

然后对当前 `CODEX_HOME` 安装机器级规则：

```bash
ai-bridge host install
ai-bridge host validate
```

如果一台机器上存在多个不同的 `CODEX_HOME`，它们应视为不同的 Codex 身份，分别配置。

Machine Policy 主要管理：

```text
$CODEX_HOME/config.toml
$CODEX_HOME/AGENTS.md
$CODEX_HOME/rules/ai-bridge-global.rules
```

它负责的是长期行为，例如：

- 用户可见的进度、计划、测试结果和完成报告默认使用自然中文。
- 普通局部实现由 Codex 自行判断；真正会改变架构、范围、部署、Git 分支策略或科研语义的歧义才询问用户。
- 当前 `main` 分支上的安全 `fetch`、快进 `pull`、正常 `add/commit` 尽量减少重复授权。
- 当前仓库范围的 `gh auth status --`、`gh pr list --`、`gh pr status --`、`gh issue list --`、`gh issue status --` 和 `gh run list --` 可低打扰读取；`--repo`、token display、任意 `gh api` 和 positional view 仍走审批路径。
- 常见 Slurm 只读查询如 `squeue`、`sinfo`、`sacct`、`sstat`、`sprio`、`scontrol show ...` 和 `scontrol ping` 尽量减少重复授权；资源申请、任务状态修改和调度器修改仍走审批。
- `ps`、`tmux ls` / `tmux list-sessions` / `tmux has-session` 这类只读 host/session inspection，以及 `git fetch --all --prune` 这类已配置远端同步，尽量减少重复授权。
- 如果下一步明确属于外部 GPT Planner/Reviewer/Critic，等待 GPT 不应被误判为任务失败。

### GitHub HTTPS 普通发布

已经在当前分支完成任务、同名远端分支已经存在、且 remote 是 GitHub HTTPS 时，低打扰发布使用单一受边界约束入口：

```bash
ai-bridge host publish-current-branch \
  --expected-repo <owner/repo> \
  --expected-branch <branch>
```

这两个参数只是 equality assertion；真实 repo、branch、upstream、remote ref、transport、credential 和 hook 边界都由 helper 从当前 Git 状态重新读取。

可信低打扰路径只包括：

```text
https://github.com/<owner>/<repo>.git
+ existing system/global/gh credential helper
```

SSH、scp-style 和 custom transport 会默认失败并回到普通原始 Git push 审批。Bridge Kit 不配置 SSH key、ssh-agent 或 `known_hosts`，也不会替你把 remote 从 HTTPS 改成 SSH。raw `git push origin main` 保持审批路径；`force push`、改 remote、删除分支、`reset --hard`、`git clean` 等危险操作仍然不能因为“自动化”而放开。

Machine Policy 会尽量非破坏式修改已有配置，并在需要时创建备份。

## Lite：新项目默认安装

进入一个正式 Git 仓库后：

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

Lite 会给项目建立一套轻量、可版本控制的 GPT ↔ Codex 交接结构。核心关系可以理解成：

```text
GPT 写清楚要做什么
        ↓
prompts/tasks/<task_key>.md
        ↓
Codex 执行
        ↓
results/<task_key>/result.md
        ↓
需要时再由 GPT 复核
```

常见目录包括：

```text
AGENTS.md
prompts/
results/
docs/
.agents/skills/agent-task-executor/
```

Lite 并不意味着“只能做小任务”。普通功能开发、修 bug、文档整理、常规重构，甚至较大的实现，只要不要求独立角色闭环，通常都够用。

`ai-bridge init` 只配置当前项目，不会偷偷修改你的 `$CODEX_HOME`，也不会自动安装下面那些可选能力。

## Reviewed Mode：GPT 先定方案、完成后再独立复核

如果某项工作不能让 Codex 一边执行一边自己决定产品语义或科研方向，但又没有必要上最重的 Controlled Mode，可以使用 Reviewed Mode。

最直观的流程是：

```text
GPT Planner
先把方案写清楚并冻结
        ↓
Codex Executor
按方案实现
        ↓
GPT Reviewer
读取真实 Git diff、测试和结果独立复核
        ↓
必要时允许一轮 Codex 返修
        ↓
最终交给用户
```

安装命令仍使用兼容 CLI 名称：

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

创建具体任务：

```bash
ai-bridge reviewed-handoff task init \
  --target /path/to/project \
  --task-key repo--example \
  --objective "这里写任务目标"
```

新的 Reviewed Handoff task 默认使用 semantic key：`<scope-token>--<goal-token>`，例如 `repo--example`。历史 numbered task 继续可验证，不需要迁移。

这套流程默认最多两轮 GPT 复核。第一轮如果返回 `REVISE`，允许 Codex 自动返修一次；第二轮仍未通过，就进入人工决策，不继续无限循环。

如果复核已经 `PASS` 并进入 `AWAIT_HUMAN_DECISION`，但用户阅读全文或检查 artifact 后明确拒绝当前结果，使用 `ai-bridge reviewed-handoff human record --decision REJECT --route REVISE|NEEDS_GPT_PLANNER` 记录这次 human decision。只需按冻结 Plan 修复时回到 `REVISE`；如果拒绝理由证明 Plan 自身需要一次最小修订，则回到 `NEEDS_GPT_PLANNER`。这个入口不会重置 `review_round`，不会删除原 Reviewer PASS，也不会在预算用尽后开启第三轮。

Codex 侧可以运行轻量监视器，在 `PLAN_FROZEN` 或 `REVISE` 时启动执行：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

生产环境可以用 machine-local lifecycle 命令管理唯一后台 watcher：

```bash
ai-bridge reviewed-handoff watcher start --target /path/to/project --branch <existing-authorized-branch>
ai-bridge reviewed-handoff watcher stop --target /path/to/project --branch <existing-authorized-branch>
ai-bridge reviewed-handoff watcher restart --target /path/to/project --branch <existing-authorized-branch>
```

同一个 `target + branch` 只允许一个正式 watcher。第二个实例会返回 `ALREADY_RUNNING` 和真实 PID；如果 Bridge Kit 源码已经更新，`watcher status` 会显示 `RESTART_REQUIRED`，但不会自动打断正在工作的 watcher。

监视器不会自行创建分支或 PR。它也不会把 Codex Executor 变成新的决策角色：Executor 只执行冻结方案并提交结果，发布仍由 watcher 在验证后完成。

Reviewed Mode 有两条受边界约束的 worktree 路径。

brand-new task 第一次创建 reviewed branch/worktree 时，使用当前用户已经批准的 exact repo/task/path/base effect，然后走：

```bash
ai-bridge reviewed-handoff task bootstrap \
  --target /path/to/project \
  --task-key repo--example \
  --expected-repo owner/name \
  --expected-worktree /absolute/path/to/project-repo--example \
  --expected-base-ref origin/main \
  --expected-base-commit <base-commit> \
  --objective "这里写任务目标"
```

这个入口会派生固定分支 `reviewed/<task_key>`，创建 exact worktree，并把首份 `REQUEST.md` / `CURRENT.json` 只写在新 reviewed worktree 中。它是 authorization-bound first bootstrap，不是永久 generic allow，也不会让用户手工拼 `git worktree add` 或自己组装控制文件。

已经存在 task artifacts 后，恢复或重新物化 exact worktree 继续使用：

```bash
ai-bridge reviewed-handoff materialize-worktree ...
```

`materialize-worktree` 只接受已冻结的 `REQUEST.md` / `CURRENT.json` scope。它可以从本地 artifacts 恢复，也可以在 canonical main 没有 task files 时，先从 exact remote reviewed branch 读取并校验 `REQUEST.md` / `CURRENT.json`，再 checkout/materialize。它不会按分支名盲目收养远端任务，也不会把 remote metadata 复制回 canonical main。

这两条路径都不会变成通用 `git worktree` / branch wrapper，也不会替用户选择新分支、改 remote 或创建 PR。raw `git worktree add` 仍留在普通审批路径。

`PLAN_FROZEN` 只有在当前 `PLAN.md` 结构合法时才会被 watcher 视为可执行。外部 GPT、CI、Text Review 或 Visual Review 尚未给出新决定时，属于正常等待，而不是 `BLOCKED`。

详细状态规则和边界见：

```text
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
```

## Controlled Mode：高风险任务的严格闭环

Control 面向“错误通过的代价很高”的任务，例如：

- 科研方法或系统架构的大改；
- 昂贵训练或长时间计算；
- 数据、安全或隐私敏感逻辑；
- 生产部署；
- 重要迁移；
- 必须能证明“为什么可以判定通过”的工作。

安装命令仍使用兼容 CLI 名称：

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

它会增加 `automation/agent_flow/` 控制目录，但不会替换 Lite，也不会自行创建 Git 分支。

整体分工可以直观理解成：

```text
Planner      决定要实现什么
Critic       检查方案和最终闭环是否真的成立
Controller   只负责机械路由，不替人做判断
Verifier     根据冻结要求建立验证标准
Executor     只负责实现
Human        最终保留人工决定权
```

Control 比 Review 更重，因为它会显式保存冻结要求、验证依据、稳定审查对象和最终独立检查。它的目的不是“堆更多 Agent”，而是避免同一个角色既写要求、又改实现、又自己宣布通过。

一个项目只需安装一次 Control；每个高风险任务再单独创建任务实例：

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key repo--example
```

详细设计见：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
```

## Persistent Run：长期 Goal 的持久执行

Persistent Run 是项目层可选能力，不是第四套 workflow。Lite / Review / Control 三档 workflow 保持不变；Persistent Run 只解决长期任务在 Codex / SSH 断开后如何继续运行、如何恢复、以及如何避免临时发明后台机制的问题。

安装到某个 Git 仓库：

```bash
ai-bridge persistent-run install --target /path/to/project
ai-bridge persistent-run validate --target /path/to/project
```

安装后只会写入：

```text
automation/persistent_run/README.md
automation/persistent_run/CONTRACT_TEMPLATE.md
automation/persistent_run/KICKOFF_TEMPLATE.md
AGENTS.md 中的 ai-bridge-kit:persistent-run managed block
```

它不会安装 Lite / Review / Control，不会修改 `$CODEX_HOME`，不会创建 `.codex/rules`，也不会放开全局 `tmux new-session`、`setsid`、`nohup`、`sbatch`、`salloc` 或 generic shell/Python。

给某个已经冻结的 Goal 生成 kickoff 授权文本：

```bash
ai-bridge persistent-run prompt kickoff \
  --target /path/to/project \
  --goal prompts/tasks/repo--long-run.md
```

这个命令只打印用户可见授权，不会启动 tmux。用户把这段 kickoff 发给 Codex 后，Codex 才能针对同一个 frozen Goal 使用 canonical `tmux` session 启动或恢复。已有兼容 run 时应 resume，不重复启动；`tmux` session、Slurm job、PID、heartbeat 或 checkpoint 只能证明活动或状态，不能替代原 Goal 的完成标准。

当前 Persistent Run 还可以把长期任务的运行状态说清楚：

- 当前 stage；
- 真实 progress fraction；
- 有依据 ETA，或者在证据不足时返回 `UNKNOWN`；
- 从真实 no-progress evidence 推出的 stalled 状态；
- latest/history/reconnect 查询。

这些运行进展可以通过 Notifications 投影出去。这里报告的是运行进展，不是自动控制：Bridge Kit 不会因此自动重启任务、取消任务、扩资源，也不会把 heartbeat、PID、tmux session 或 ETA 当成 Goal 完成。

GPT 写长期 Goal/task 时要先判断 execution lifetime。`run overnight`、`unattended`、`run until morning`、`leave it running`、`survive disconnect` 或 `resume persistent Goal` 这类要求意味着需要 Persistent Run contract，但不代表必须把 Lite 任务改成 Reviewed Mode / Controlled Mode。如果仓库没有安装 Persistent Run，也没有用户选择的等价项目原生合同，不要把任务写成普通 live Codex session。

Codex 收到 task 后会在实质执行前检查是否存在可预见的 approval-sensitive effect。仓库里的 Goal/Plan/contract 只证明 frozen scope，不等于当前用户授权；如果当前用户消息没有包含同一个 frozen Goal 的 bounded kickoff 授权，Codex 应先显示 kickoff 并等待用户发送，而不是先启动 tmux 或做大量前置工作。

## Notifications：按结构化 brief 发通知

Notifier 只负责通知，不负责决定任务是不是完成。

权责边界是：语义决定者写结构化 brief，Notifications 只做 deterministic 渲染、去重和 SMTP 发送。Planner/Reviewer/Critic/Final Critic 可以写自己决定对应的终态、人工等待或里程碑 brief；Controller/watcher 只可以写 operational failure/status/progress brief。Executor/Codex 不能决定 PASS，不能写自由文本式用户结论邮件，也不能绕过 notifier 的 send-once/dedupe。

如果项目需要终态邮件，先同步私有配置并发一封真实测试邮件：

```bash
cd /path/to/project
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
```

任务完成后，工作流可以生成：

```text
results/<task_key>/notification_brief.json
```

再发送：

```bash
ai-bridge notifier send results/<task_key>/notification_brief.json
```

推荐这种一次性发送方式，不要求为了通知常驻一个 tmux、systemd 或后台轮询进程。

向后兼容的旧 `notification_brief.json` 仍表示 terminal/user-decision 通知。需要 workflow 继续运行的非阻塞里程碑通知时，可以写入：

```text
results/<task_key>/notifications/<event>.json
```

新结构化 brief 使用短字段，例如 `event_type`、`status`、`decision_authority`、`key_conclusion`、`next_step`、`action_required` 和 `evidence_paths`。邮件正文由 notifier 模板渲染成简洁中文，而不是让 Executor 生成整封自由文本邮件。重复 brief 会按内容 digest 去重，不会重复发送。

Operational progress 可以报告运行层进展或阻塞，但不能声称 semantic PASS、READY、release readiness 或 final completion。邮件密码等秘密配置保存在本地私有文件，不应提交到项目仓库。

## Overleaf Bridge：一个科研仓库里同时管代码和论文

Overleaf Bridge 针对很常见的科研项目结构：

```text
research-repo/
├── code/
├── analysis/
├── data/
├── results/
├── docs/
└── paper/
    ├── manuscript/
    ├── notes/
    └── submission/
```

我们希望 Codex 在整个仓库根目录工作，这样它写论文时可以同时检查代码、实验结果和研究文档；但 Overleaf 只应该看到真正的论文源码，例如 `paper/manuscript/`。

### 为什么不能直接用 Overleaf 的 GitHub 同步

Overleaf 的 GitHub 同步面向整个 GitHub 仓库，不能只选一个子目录。因此这里不用“让 Overleaf 从 GitHub 拉 `paper/manuscript/`”这种方式。

Overleaf Bridge 的做法是：

```text
完整科研 GitHub 仓库
        │
        ├── Codex 读取整个项目
        │
        └── paper/manuscript/
                 │
                 ▼
        本机的 Overleaf Git 镜像
                 │
                 ▼
             Overleaf
```

科研仓库本身不会增加一个 `overleaf` remote，也不会改变 `origin` 或分支结构。

### 第一次安装

先在科研仓库中指定论文根目录：

```bash
ai-bridge overleaf install \
  --target /path/to/research-repo \
  --paper-root paper/manuscript
```

项目里会保存可版本控制的配置：

```text
automation/overleaf/config.toml
```

然后在 Overleaf 创建一个空白项目，删除默认 `main.tex`，取得它的 Git URL，再执行：

```bash
ai-bridge overleaf connect \
  --target /path/to/research-repo \
  --remote-url https://git@git.overleaf.com/<PROJECT_ID> \
  --bootstrap
```

Overleaf 项目可能使用 `main`、`master` 或其他默认分支。Bridge Kit 会读取项目实际声明的远端分支，并把结果保存在本机 `connection.json` 中；科研仓库的 `config.toml` 不需要配置 `main/master`。

Overleaf 的 token 不写入本仓库，也不写入 `connection.json`；认证交给正常的 Git credential helper。

### 日常怎么用

Codex 在本地写完论文后，推荐顺序是：

```text
修改论文
-> 本地编译 / 检查
-> commit
-> git push origin main
-> ai-bridge overleaf status
-> ai-bridge overleaf push
```

如果导师或合作者直接在 Overleaf 修改：

```text
ai-bridge overleaf status
-> ai-bridge overleaf pull
-> 检查 git diff
-> 本地重新编译
-> commit
-> git push origin main
```

`pull` 只把 Overleaf 修改带回论文目录，不会替你自动 commit，也不会自动推 GitHub。

Bridge 会记录上一次成功同步时的内容摘要，并比较上次同步版本、本地论文和 Overleaf 当前版本。只有本地改了可以 `push`；只有 Overleaf 改了可以 `pull`；两边都从上次同步后发生不同修改时会判定为分叉并拒绝自动覆盖。

同步前先让非 excluded 的 `paper_root` 保持 clean：tracked、staged、deleted、renamed 或 untracked manuscript 文件都应先 review/compile/commit，避免未提交草稿被用作 baseline 或被 pull 覆盖。`exclude_paths` 只用于 Overleaf 编译不需要的 GitHub-only 文件；编译需要的 `.tex`、`.bib`、figures、tables 和 style/class 文件必须留在 publication projection 中。

每台机器的 `connection.json` 和 `mirror/` 都在 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/`，不提交到 GitHub；多台机器要各自 `connect`。Overleaf Bridge 不会自动实时同步，它是一个按需、可检查、尽量不覆盖别人修改的论文同步层。

常用命令：

```bash
ai-bridge overleaf status --target /path/to/research-repo
ai-bridge overleaf push --target /path/to/research-repo
ai-bridge overleaf pull --target /path/to/research-repo
ai-bridge overleaf validate --target /path/to/research-repo
```

## Visual Review：给图片和视觉产物增加独立检查

Visual Review 用来检查真正需要“看图”才能判断的问题，例如：

- PPT 或 PDF 页面是否排版异常；
- 图中文字是否被裁切；
- 视觉结果是否符合给定检查标准；
- 某个实现是否与参考截图明显不一致。

它不是新的工作流角色，而是给 Review、Control 或普通项目提供一份可验证的视觉证据。

安装和预检：

```bash
ai-bridge visual-review install --target /path/to/project
ai-bridge visual-review preflight --target /path/to/project
```

默认通过 GitHub Actions 调用 OpenAI 图像输入能力。GitHub Secret 名称统一为：

```text
OPENAI_VISUAL_REVIEW_API_KEY
```

生成的结果通常写到：

```text
results/<task_key>/visual_review/VISUAL_REVIEW.json
```

Bridge Kit 不会把 API key 写进仓库，也不会打印 secret 值。

在 Review 中，`ci_required=true` 的视觉任务先发布实现、渲染图片和 `visual_inputs.json`，然后停在 `WAITING_FOR_CI` / `ci_status=PENDING`。CI 通过后才进入 `READY_FOR_GPT_REVIEW`，此时缺少 `VISUAL_REVIEW.json` 是正常的 `waiting_visual_review_evidence`；只有 fresh visual evidence 返回后，Scheduled GPT Reviewer 才开始正式 review。`PASS` 和 `human_gate_reason=PASS` 仍然必须绑定当前 implementation 的 visual PASS evidence。

Visual Review workflow 只在 `main` / `reviewed/**` 上的 `results/**/visual_review/visual_inputs.json` 改动或手动 `workflow_dispatch` 时运行。普通非视觉任务不会触发一个容易被误读为“视觉已审查并 PASS”的 AI Bridge Visual Review job；evidence writeback 会写回触发它的同一个 branch。

默认隐私策略是保守的：安装视觉复核能力不等于允许自动上传患者影像、私有临床数据、未公开科研图片、凭据或其他敏感内容。没有明确外部上传授权时应拒绝。

## Text Review / Text Transform：给私有文本增加独立处理证据

Text Review 用于 Review 中这类场景：最终验收必须读完整 user-facing Markdown/plain text，但正文不能作为 plaintext 提交到 public task branch。它不是新的 GPT role，而是和 Visual Review 平级的 evidence producer。

默认路径是：

```text
private local text
-> age public-key encryption
-> encrypted payload + manifest committed to reviewed task branch
-> GitHub Actions ephemeral decrypt
-> OpenAI Responses API text review with store=false
-> results/<task_key>/text_review/TEXT_REVIEW.json
-> Scheduled GPT Reviewer consumes evidence
```

安装和预检：

```bash
ai-bridge text-review install --target /path/to/project
ai-bridge text-review preflight --target /path/to/project
```

配置加密 transport：

```bash
ai-bridge text-review configure --target /path/to/project --repo owner/name
```

这会生成 age keypair，通过 `gh secret set` 把 private identity 写入 GitHub Secret：

```text
AI_BRIDGE_PRIVATE_REVIEW_AGE_KEY
```

并把 public recipient 写入：

```text
automation/reviewed_handoff/private_text_review.age.pub
```

如果 `gh` 权限不够，用户只需要手动配置这一个 GitHub Secret；不要把 secret 粘贴到聊天或仓库里。

OpenAI key 优先使用未来通用名称：

```text
OPENAI_REVIEW_API_KEY
```

同时兼容已有 Visual Review secret：

```text
OPENAI_VISUAL_REVIEW_API_KEY
```

所以已经接入 Visual Review 的 repository 不需要为了 Text Review 再创建第二个 OpenAI key。默认模型可用 `OPENAI_TEXT_REVIEW_MODEL` 或 CLI `--model` 显式覆盖。

加密一个本机私有 Markdown artifact：

```bash
ai-bridge text-review encrypt \
  --target /path/to/project \
  --task-key repo--text-review \
  --input /private/path/final.md \
  --output results/repo--text-review/text_review/payload.age \
  --manifest results/repo--text-review/text_review/text_inputs.json \
  --implementation-commit <commit> \
  --rubric "Read the complete artifact and decide whether it satisfies the frozen user-facing prose requirements." \
  --external-upload-authorization "User authorized private text review through OpenAI Responses API with store=false for this task."
```

`TEXT_REVIEW.json` 会记录 `task_key`、`workflow_type`、`review_kind`、模型、prompt version、manifest identity、plaintext SHA-256、reviewed input identity、decision、item reviews、blocking findings 和 notes；它不会包含完整 private input。

在 Review 中，若 `CURRENT.text_review_required=true`，缺少 `TEXT_REVIEW.json`、plaintext SHA mismatch、manifest identity mismatch 或旧 artifact evidence 都不能支持 PASS，也不会消耗 review round；系统会等待 Text Review evidence 或要求恢复。

Text Transform 使用同一类加密 transport 做私有 Markdown/plain-text 转换：Git 中只保存 ciphertext、manifest 和元数据，GitHub Actions 临时解密、调用 OpenAI Responses API with `store=false`，再把生成结果加密给本机 output recipient。它适合需要外部模型处理私有文本、但不能把 plaintext 提交到仓库的转换任务。

## Production Plugin Replay：受控本机插件回归

`ai-bridge plugin-replay` 是 Machine Policy 预授权的窄入口，不是新的 workflow。

它用于已经授权的本机 production plugin repair/replay：让 fresh Codex runtime 在 write-isolated replay workspace 中测试当前 Codex identity 中已安装的插件。

调用方必须指定目标 Git 仓库、已安装插件名、任务/说明文件和一个或多个显式 input file。input 默认必须位于 target Git repo 内；外部文件只能先放入 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/inbox/` 这个固定 trusted inbox。task/说明文件只能来自 target repo、当前 caller repo 或 trusted inbox。

每次运行只把这些文件复制到 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/<run-id>/`，child Codex 的 cwd 是 write-isolated workspace，默认 `workspace-write`、`approval_policy=never`、本地 replay 网络关闭，且使用当前 Codex identity，不允许通过该入口切换到另一个 `CODEX_HOME`。完整输出保留在本机 state 目录。

当前 Codex runtime 仍可能读取同一用户可读文件；wrapper 会如实记录 read-scope diagnostic，但不把它包装成 strict read isolation。Machine Policy 不会因此放开 raw `codex exec`、裸 shell/python、任意私人路径作为 replay input、整个 consumer repo 写入、外部上传、危险 Git、发布或部署。

常用形态：

```bash
ai-bridge plugin-replay \
  --target /path/to/project \
  --plugin <plugin> \
  --task <task-file> \
  --input <explicit-file>
```

## 常见选择

### 普通代码仓库

```text
Machine Policy
+ Lite
```

### 需要 GPT 先做方案、Codex 实现、GPT 再独立看一遍

```text
Machine Policy
+ Lite
+ Reviewed Mode
```

### 高风险科研、生产或安全敏感任务

```text
Machine Policy
+ Lite
+ Controlled Mode
```

### 长期 Goal 需要断线后继续运行

在原有 Lite / Reviewed Mode / Controlled Mode 组合上再加：

```text
Persistent Run
```

### 需要完成后邮件提醒，或报告运行层进展

在上述任意组合上再加：

```text
Notifications
```

### 科研仓库同时放代码和论文，并希望用 Overleaf 协作

```text
Machine Policy
+ Lite
+ Overleaf Bridge
```

### 图片/PPT/视觉结果必须真正看图审核

按需增加：

```text
Visual Review
```

### 私有 Markdown/plain text 需要独立全文检查或转换

按需增加：

```text
Text Review / Text Transform
```

不要同时把所有可选层都装上，除非项目确实同时需要它们。

## 常用命令速查

```bash
# 机器级长期规则
ai-bridge host install
ai-bridge host status
ai-bridge host validate

# GitHub HTTPS 当前分支低打扰发布
ai-bridge host publish-current-branch --expected-repo <owner/repo> --expected-branch <branch>

# 普通项目交接
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project

# 独立 GPT 复核
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
ai-bridge reviewed-handoff task bootstrap --target /path/to/project --task-key repo--example --expected-repo owner/name --expected-worktree /absolute/path --expected-base-ref origin/main --expected-base-commit <base-commit> --objective "这里写任务目标"
ai-bridge reviewed-handoff materialize-worktree ...

# 高风险闭环
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project

# 长期 Goal 的持久执行 contract
ai-bridge persistent-run install --target /path/to/project
ai-bridge persistent-run validate --target /path/to/project
ai-bridge persistent-run prompt kickoff --target /path/to/project --goal prompts/tasks/repo--long-run.md

# 邮件通知
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
ai-bridge notifier send results/<task_key>/notification_brief.json

# Overleaf
ai-bridge overleaf install --target /path/to/project --paper-root paper/manuscript
ai-bridge overleaf connect --target /path/to/project --remote-url <OVERLEAF_GIT_URL> --bootstrap
ai-bridge overleaf status --target /path/to/project
ai-bridge overleaf push --target /path/to/project
ai-bridge overleaf pull --target /path/to/project
ai-bridge overleaf validate --target /path/to/project

# 视觉检查
ai-bridge visual-review install --target /path/to/project
ai-bridge visual-review preflight --target /path/to/project

# 文本复核 / 转换
ai-bridge text-review install --target /path/to/project
ai-bridge text-review preflight --target /path/to/project
ai-bridge text-review configure --target /path/to/project --repo owner/name

# 本机真实插件回归
ai-bridge plugin-replay --target /path/to/project --plugin <plugin> --task <task-file> --input <explicit-file>
```

## 设计原则

这套工具长期遵守几条简单原则：

1. **项目本身才是权威来源。** 任务状态、论文、实现和结果应留在 Git 或明确的本地状态中，不依赖某个 Codex 对话线程记住一切。
2. **默认轻量。** 普通任务不要为了“显得可靠”而强行使用高风险闭环。
3. **角色分工要有意义。** 独立复核的价值在于判断权分离，不在于角色数量。
4. **Git 操作尽量安全且低打扰。** 正常开发可以自动化，改变分支结构和破坏性操作必须保守。
5. **秘密信息不进仓库。** 邮件密码、Overleaf token、OpenAI API key 等都应保存在合适的私有位置。
6. **等待不是失败。** 当任务明确交给外部 GPT 处理时，短时间没有新决定属于正常等待。
7. **完成要对应原始目标。** 不能把没有命中 blacklist、窄范围测试通过、helper path 成功、toy/synthetic evidence 或降级 fallback 包装成完整目标完成。
8. **对真实风险严格，对形式主义克制。** 需要证明时就建立证据链；普通任务不为了流程漂亮增加无必要复杂度。

## 进一步阅读

快速上手：

```text
QUICKSTART.md
```

主要实现规格：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
docs/V0_6_OVERLEAF_BRIDGE_IMPLEMENTATION_SPEC.md
docs/PROJECT_STATE_BRIDGE_ROADMAP.md
```

版本变化：

```text
CHANGELOG.md
```

仓库维护规则：

```text
AGENTS.md
```

如果只是第一次使用，不需要先读完这些规格。通常从本文的“Machine Policy”“Lite”和对应的可选能力开始即可。
