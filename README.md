# GPT-Codex AI Bridge Kit

这是一个用于 ChatGPT/GPT 与 Codex 协作的本地工作流工具包。它的目标不是再造一个复杂的 Agent 平台，而是把长期配置、项目交接、独立 GPT 复核、高风险任务闭环和终态通知拆成彼此独立的层，让不同项目只安装自己真正需要的部分。

最重要的理解方式不是“有几个安装等级”，而是分成三个作用域：**机器层、项目层和任务层**。其中真正需要安装的只有机器层和项目层；Reviewed Handoff task 与 Agent-Flow task 都只是某一次工作的运行实例，不是新的安装层。

```text
机器层
└── Host Policy                    每个 CODEX_HOME 安装一次

项目层
├── Lite Handoff                   每个正式项目默认安装
├── Reviewed Handoff               需要 GPT 规划 + 独立复核时可选
├── Generic Notifier               需要终态邮件时可选安装
└── Agent-Flow Core                高风险项目显式安装

任务层
├── Lite task                      一份轻量任务交接文件
├── Reviewed Handoff task          一次最多两轮 GPT review 的中档工作流
└── Agent-Flow task                一次独立的高风险工作流实例
```

## 新机器和新项目应该怎么装

一台新的服务器、工作站、WSL 环境或其他独立 Codex identity，首先安装本工具包，然后配置一次 Host Policy。`CODEX_HOME` 不同时，应视为不同的 Codex identity，分别安装。

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
ai-bridge host install
ai-bridge host validate
```

随后，每个正式 repository 单独初始化 Lite Handoff。普通开发到这里通常已经足够，不需要因为项目文件很多、修改范围大或存在 Controller 就自动安装更重的 workflow。

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

如果任务需要 GPT 先冻结产品/语义决策、Codex 执行后再由独立 GPT 审核一到两轮，但又不值得引入 Agent-Flow 的 Requirement Ledger、独立 Verifier 和 Final Critic，可以叠加 Reviewed Handoff：

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

如果这个项目需要任务结束后自动发邮件，再配置 Generic Notifier；如果项目要执行科研架构重构、昂贵训练、数据敏感逻辑、生产部署或其他“错误通过的代价很高”的任务，再显式安装 Agent-Flow。

```bash
# 可选：终态邮件
cd /path/to/project
ai-bridge private sync --profile notifier
ai-bridge notifier send-test

# 可选：高风险 Agent-Flow
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

换句话说，推荐默认路径是 **Host Policy + Lite Handoff**。Reviewed Handoff、Notifier 和 Agent-Flow 都是按需叠加的能力，不应静默安装。

## Host Policy：一台机器上的 Codex 长期怎么工作

Host Policy 属于机器层，写入当前实际使用的 `$CODEX_HOME`，而不是某个 repository。Codex Home 的解析顺序是显式 `--codex-home`、环境变量 `$CODEX_HOME`、最后才是 `~/.codex`。所有 host 命令都会打印最终使用的路径，避免在多服务器、多账户、Windows/WSL 并存时修改错身份。

```bash
ai-bridge host install
ai-bridge host status
ai-bridge host validate
```

它非破坏式维护以下文件，并在改动前把原文件备份到 `$CODEX_HOME/ai-bridge-kit/backups/<timestamp>/`：

```text
$CODEX_HOME/config.toml
$CODEX_HOME/AGENTS.md
$CODEX_HOME/rules/ai-bridge-global.rules
```

当前长期配置保持：

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
approvals_reviewer = "auto_review"

[sandbox_workspace_write]
network_access = true

[features]
default_mode_request_user_input = true
memories = true
```

`default_mode_request_user_input = true` 的目的，是让 Codex 在默认协作模式下遇到会实质改变架构、范围、部署方式、Git 工作流或科学/产品语义的歧义时可以直接询问用户，而不需要为了提问专门进入 Plan mode。普通实现细节仍应自行判断，不应不断打断用户。`memories = true` 用于辅助长期上下文，但 repository 中的协议、任务和结果文件仍然是项目状态的权威来源。

Host Policy 还在全局 `AGENTS.md` 中维护长期行为约束：用户可见的进度说明、计划、风险解释、测试总结和完成报告默认使用自然的简体中文；代码、路径、命令、配置键、状态名和精确错误信息保持原始技术字面量。Goal mode 把过长目标保存成 `$CODEX_HOME/attachments/.../goal-objective.md` 是正常机制，不需要每个 Goal 再重复写“请用中文”。

Git 方面，Codex 默认继续当前已经 checkout 的 branch。当前已选 `main` 分支上的普通 `git fetch origin main`、clean worktree 下的 `git pull --ff-only origin main`、task-owned 文件的 `git add ...`、`git commit ...` 和 `git push origin main` 是低打扰开发动作，不应仅因为 sandbox 要写 `.git`，或因为文件多、commit message 长、feature 已完成而反复询问。同步前必须先检查 working tree；如果 dirty，先判断修改 ownership，不得默认 `git pull --ff-only --autostash ...`、`git stash`、`git reset --hard` 或 `git restore ...`。提交前必须检查 `git diff --cached --stat` 和 `git diff --cached`，避免提交无关文件或 secret。未经用户针对具体分支动作的明确授权，不得因为“修改很大”“PR 更安全”或“main 是干净基线”而自行创建、切换、checkout、重命名或删除 branch，也不得自行创建 PR、force push、删除远端 branch/tag、设置 upstream 或修改 remote。

Host Policy 还定义了一条通用 external GPT 等待规则：当 repository workflow 已经把下一步交给外部 GPT Planner、Reviewer、Critic、Final Critic 或同类 reasoning role 时，尚未出现新 decision 是 `waiting_external_review`，不是 `BLOCKED`。正常最短等待窗口是 `MIN_EXTERNAL_GPT_WAIT = 2 hours`；2 小时不是自动截止线。只要仓库状态合法、实现和结果 artifact 完整、外部 GPT/connector/scheduler 没有明确失败，就继续低频等待。旧 review 只有在 `implementation_commit`、`review_target_id`、snapshot identity 或当前 round 匹配当前目标时才是 fresh decision；不匹配就是 stale context，不能重复触发旧 `REVISE`，也不能消耗 review/repair budget。

`$CODEX_HOME/rules/ai-bridge-global.rules` 则用于减少普通开发动作的审批等待。目前长期授权的 execpolicy 前缀是：

```text
git fetch origin main
git pull --ff-only origin main
git add ...
git commit ...
git push origin main
```

这意味着当前 `main` 分支的安全同步、staging、普通 commit 和默认 `origin/main` push 可以跳过人工审批和 auto-review。其他长期分支如果也需要同样低打扰，应由项目规则或用户明确授权补充，不靠全局 `git push origin ...` 宽前缀猜测。`git pull --rebase ...`、`git pull ... --autostash`、`git push origin <new-branch>`、`git push -u origin ...`、`git push --set-upstream origin ...`、`git push origin --delete ...`、常见 force-push 形态、branch switch/checkout/worktree add/branch 删除重命名、`git reset --hard`、`git clean`、`git restore` 和 remote 增删改都必须回到用户确认。危险 Git 行为仍由全局行为政策禁止；execpolicy 技术上匹配某条命令不代表可以绕过“分支策略由用户决定”。项目自己的 `.codex/config.toml` 或 `.codex/rules/` 仍可进一步收紧这些默认策略。

## Lite Handoff：每个项目默认的 GPT ↔ Codex 交接层

Lite Handoff 是本工具包最基础、也最常用的项目层。它适合普通功能开发、修 bug、文档更新、常规重构，以及虽然工作量不小、但不需要独立 GPT 复核或五角色证据闭环的任务。

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

初始化后，项目会得到一套可以随 repository 一起版本控制的交接结构：

```text
AGENTS.md

prompts/
├── AGENT_RULES.md
├── CHATGPT_RULES.md
├── HANDOFF_ROLES.md
├── HANDOFF_STATE_MACHINE.md
├── CONTROLLER_TASK_PROTOCOL.md
├── tasks/
└── templates/

results/
docs/notes/
docs/wiki/

.agents/skills/agent-task-executor/SKILL.md
```

最简单的 Lite 流程仍然只是：GPT 写任务，Codex 执行并写结果，之后按需要再由 GPT 审查。

```text
prompts/tasks/<task_key>.md
        ↓
Codex
        ↓
results/<task_key>/result.md
        ↓
可选 review
```

Lite 并不等于“只能做小修改”。它仍然支持 Controller task、审计、自动 commit/push 等现有 Handoff 能力。它与更重模式的主要区别不是代码量，而是证明和独立复核负担。

`ai-bridge init` 只管理 repository 内的 Handoff 文件。它可以显示 Host Policy 状态，但不会静默修改 `$CODEX_HOME`；同样也不会自动安装 Reviewed Handoff、Notifier 或 Agent-Flow。

## Reviewed Handoff：GPT 规划、Codex 执行、GPT 最多复核两轮

Reviewed Handoff 是 v0.5 新增的中档模式。它面向这样一类任务：Lite 只让 Codex 自己执行和总结显得太松，但 Agent-Flow 的独立 Critic、Verifier、Requirement Ledger、Stable Review Snapshot 又明显太重。例如外部 repository/skill intake、中等规模重构、第三方能力引入、文档体系迁移、普通产品 feature 等。

```text
GPT Planner
→ local Codex watcher launches Executor
→ Scheduled GPT Reviewer
→ optional Codex repair
→ Scheduled GPT Reviewer
→ Human reads FINAL_REPORT.md
```

Planner 负责先把语义、产品和架构取舍冻结进 `PLAN.md`，Executor 不再自行重新发明这些决定。Reviewer 只依据冻结 Plan、真实 Git diff、当前测试/CI 和相关 regression boundary 审核，不允许因为“还可以更优雅”而扩大 scope。

安装一次 Reviewed Handoff Core：

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

每项任务单独初始化：

```bash
ai-bridge reviewed-handoff task init \
  --target /path/to/project \
  --task-key 001_external_repo_intake \
  --objective "Evaluate and integrate selected external capabilities"
```

GPT 侧异步唤醒使用 ChatGPT「安排任务」周期检查 GitHub 上的 `CURRENT.json`；没有待审任务时无副作用退出。这里不需要 OpenAI API。Codex 侧由机器上的轻量 watcher 负责在 `PLAN_FROZEN` 或 `REVISE` 时启动 Executor：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

Watcher 只同步当前已经 checkout/授权的 branch，不创建 branch/PR。机器本地的事件去重与日志放在 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/`，不进入 repository。Codex 返回 0 也不自动算完成，只有任务状态真正推进才算 executor event 成功；同一 event 的自动尝试有界，避免死循环。

Executor 成功发布实现并进入 `READY_FOR_GPT_REVIEW`、`NEEDS_GPT_PLANNER` 或 CI 已完成后等待 Reviewer 处理的 `WAITING_FOR_CI` 时，watcher 会把它报告为 `waiting_external_review`。这类等待不计入 executor retry，不写 terminal `FINAL_REPORT.md`，也不把 `CURRENT.state` 改成 `BLOCKED`。只有 Scheduled GPT 明确被禁用/删除/过期、GitHub connector/auth 重复失败、workflow state 非法、必需 review artifact 无法访问，或确实需要用户作新产品/科学/branch 决策时，才允许 terminal blocking。

Reviewed Handoff 的默认 review 上限是两轮：第一轮 `REVISE` 允许一次 Codex repair；第二轮仍 `REVISE` 必须停在 `AWAIT_HUMAN_DECISION`。执行中如果出现冻结 Plan 无法安全推导的实质歧义，Scheduled GPT 最多允许一次最小 re-plan；再次需要改变 Plan 则交给用户。所有终态都必须生成 `FINAL_REPORT.md`，因此用户回来后只需要读一份面向人的报告。

如果任务要求 GitHub CI，Codex Executor 只能把任务推进到 `WAITING_FOR_CI` 并保持 `CURRENT.ci_status=PENDING`；真实 CI 结果由 Scheduled GPT 从 GitHub checks 读取。`CURRENT.ci_status` 是唯一机器真值，`RESULT.md` 只记录执行叙述。CI locator 使用包含 `WAITING_FOR_CI` 的当前 branch tip，不要求它等于 `implementation_commit`，也不引入 hash/receipt 链。

Reviewed Handoff 刻意**不**使用 Agent-Flow 的 `review_target_id`、Requirement Ledger、semantic source manifest、role receipt graph、Review Bundle SHA 或 Final Critic。`base_commit` / `implementation_commit` 只是让 GPT 定位真实 diff 的 Git locator。如果某项任务真的需要这些证明机制，应直接升级到 Agent-Flow，而不是把 Reviewed Handoff 继续加重。

对于旧版本误退出的任务，比如 Executor 已完成并把仓库停在 `READY_FOR_EXTERNAL_PLANNER_REVIEW` 或 `READY_FOR_GPT_REVIEW`，但 Codex Goal 因旧 blocked-audit 规则结束，升级 Host Policy/Bridge Kit 后不需要重置 `CURRENT`，也不要伪造 Planner decision。重新进入 session 后同步 `main`、读取 `CURRENT`、确认当前 `implementation_commit`，把旧 commit 上的 Planner/Reviewer review 识别为 stale，然后继续等待新的 external GPT review 即可。

详细规格见 `docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md`。

## Generic Notifier：可选的终态邮件能力

Notifier 是横向可选能力，不决定任务是否完成，只负责把已经合法到达的终态发送给用户。默认推荐 one-shot，而不是常驻轮询进程。

项目第一次启用时，先从用户已经配置好的私有来源拉取邮件配置，再发送一次真实测试邮件：

```bash
cd /path/to/project
export AI_BRIDGE_PRIVATE_RCLONE_SOURCE='<remote>:Private/GPT_Codex_AI_Bridge_Kit/notifier.env'
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
```

Bridge Kit 不负责创建 rclone OAuth、不生成 Google token，也不会把本地 secret 上传回远端。私有配置默认落在 `.ai-bridge/private/notifier.env`，并尽量限制为用户可读写。

任务真正结束时，工作流生成：

```text
results/<task_key>/notification_brief.json
```

然后直接发送：

```bash
ai-bridge notifier send results/<task_key>/notification_brief.json
```

`send` 是推荐路径；`once` 和 `run` 只作为兼容的扫描/轮询模式存在。tmux、systemd、nohup 等进程托管方式都不是 Bridge Kit 的安装依赖。

目前通知器使用 SMTP/STARTTLS。所需私有键包括：

```text
AI_BRIDGE_NOTIFY_SMTP_USER
AI_BRIDGE_NOTIFY_SMTP_PASSWORD
AI_BRIDGE_NOTIFY_FROM
AI_BRIDGE_NOTIFY_TO
AI_BRIDGE_NOTIFY_SUBJECT_PREFIX
```

## Agent-Flow Core：高风险项目才安装的闭环控制层

Agent-Flow 是项目层的可选高风险工作流。它适用于科研架构实现、昂贵训练或计算、数据/安全敏感逻辑、生产部署、重要迁移，以及其他“false PASS 比多做一次验证更贵”的任务。

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

安装后，项目会增加独立的 `automation/agent_flow/` 控制平面，其中包含 Project Profile、角色权限、状态 schema、Planner/Critic/Controller/Verifier/Executor 提示模板以及 Requirement Ledger、source manifest、Review Bundle 等模板。它不会修改 `$CODEX_HOME`、不会替换 Lite Handoff，也不会为了角色隔离自行创建 branch。

高风险流程的目标结构是：

```text
Planner
→ Initial Critic
→ Controller
→ Verifier
→ Executor
→ Planner repair loop
→ Final Critic
→ Human gate
```

这里的重点不是“多几个 Agent”，而是把不同判断权分开。Planner 负责用户目标和实现审查；Critic 负责初始合同审计、必要的合同复审和最终独立闭环；Controller 只做机械路由；Verifier 只能依据冻结 requirement 建立验证 oracle；Executor 只负责实现，不能改合同或验证规则，也不能自行宣布最终通过。

Agent-Flow 还使用 Stable Review Snapshot，把真正影响语义的合同、Requirement Ledger、实现源码和 Verifier 源码与 Controller receipt、CURRENT 状态、文档、通知等控制平面变化分开。目标是只有语义变化才触发昂贵重验证，receipt-only、state-only 或 control-plane-only 修改不能默认“为了安全全部重跑”。详细设计和当前实现约束见 `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`。

Agent-Flow 也使用同一 external GPT wait contract。`PLAN_REQUESTED`、`PLAN_READY_FOR_CRITIC`、`READY_FOR_PLANNER_REVIEW`、`WAITING_FOR_EXTERNAL_GPT`、`CONTRACT_REVIEW_REQUIRED`、`READY_FOR_CRITIC_FINAL_AUDIT` 等由 Planner/Critic/Final Critic 拥有下一步的状态，在没有 fresh artifact 时都只是等待。fresh 判断继续使用 Agent-Flow 自己的 `request_nonce`、`review_target_id` 和 Review Bundle 绑定；旧 target 的 Planner findings、Planner pass candidate 或 Final Critic audit 不会触发当前目标的 repair/pass/block。

Anti-overengineering 原则也在这里生效：Agent-Flow 只对合同、Requirement Ledger、实现语义源码和验证语义源码建立稳定 `review_target_id`。Git 提交、状态文件、通知、普通 receipt 和文档变化可以作为 provenance 或说明，但不应因为自身变化触发新的语义审核对象或昂贵重跑。设计目标是严格验证业务/科学语义，而不是建立复杂的 provenance 链。

## Agent-Flow task：不是新的安装层

Agent-Flow Core 在一个 repository 中只需要安装一次，但同一个项目可能先后执行多个完全不同的高风险任务。每个任务都需要独立的 objective、request nonce、冻结合同、Requirement Ledger、review target、修复历史和最终人工决策，因此需要单独创建 task 实例。

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key 001_registration_refactor
```

这一步不是“再安装一层 Agent-Flow”，而只是创建一次工作流实例。

Agent-Flow 的辅助工具包括：

```bash
ai-bridge agent-flow snapshot --target /path/to/project --task-key 001_example
ai-bridge agent-flow bundle validate --target /path/to/project --task-key 001_example
ai-bridge agent-flow classify-change --target /path/to/project --path src/example.py
ai-bridge agent-flow route --target /path/to/project --task-key 001_example
ai-bridge agent-flow transition plan --target /path/to/project --task-key 001_example
ai-bridge agent-flow transition apply --target /path/to/project --task-key 001_example --expected-state PLAN_REQUESTED --next-state PLAN_READY_FOR_CRITIC
ai-bridge agent-flow terminal-brief --target /path/to/project --task-key 001_example
ai-bridge agent-flow prompt --target /path/to/project planner
```

## 如何选择

如果只是给一台新机器建立长期 Codex 默认行为，配置 Host Policy；如果只是让一个新 repository 能被 GPT 和 Codex 稳定交接，安装 Lite Handoff。普通明确需求直接交给 Codex 完成时，继续使用 Lite。

如果任务里真正需要 GPT 先做语义/产品判断，再让 Codex 实现，并希望实现后由独立 GPT 审核一到两轮，优先使用 Reviewed Handoff。**大量文件、复杂实现本身不要求 Agent-Flow；是否需要独立合同/Verifier/Final Critic 才是升级高风险模式的关键。**

如果希望任务完成或真正阻塞时收到邮件，再加 Notifier。不要因为“可能以后会用”就在所有 repository 中预装私有通知配置。

如果某个项目确实需要高风险、长链路、独立验证的自动闭环，再安装 Agent-Flow。不要为了“更严谨”把 Agent-Flow 的 provenance 机制复制进 Reviewed Handoff。

## 验证与维护

主机层使用：

```bash
ai-bridge host status
ai-bridge host validate
```

Lite Handoff 使用：

```bash
ai-bridge validate --target /path/to/project
ai-bridge validate --target /path/to/project --strict
```

Reviewed Handoff 使用：

```bash
ai-bridge reviewed-handoff status --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
ai-bridge reviewed-handoff watcher once --target /path/to/project --branch <branch> --dry-run
```

Agent-Flow 使用：

```bash
ai-bridge agent-flow status --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

Notifier 使用：

```bash
ai-bridge notifier status
```

Host Policy 安装是非破坏式的；Lite、Reviewed Handoff 和 Agent-Flow 初始化也应保持幂等。不要通过手工复制 `$CODEX_HOME` 文件到项目目录来“统一配置”，也不要把 repository 的 workflow 模板反向当成服务器全局策略。

## 仓库内容和进一步文档

`chatgpt/` 保存 GPT 侧可复用提示，`codex/` 保存 Codex 启动提示和 repo-local skill，`templates/` 保存 Lite、Host、Reviewed Handoff 和 Agent-Flow 的 desired-state 模板，`ai_bridge_kit/` 是 CLI 与核心实现，`tests/` 是回归测试。长期协议细节放在 `docs/`，README 只负责告诉人“这套工具是什么、该装什么、什么时候装”。

当前核心规格包括：

```text
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
```

如果以后让 Codex 在新服务器或新 repository 上配置这套工具，根目录 `AGENTS.md` 是机器执行入口；README 是给人阅读和理解整体模型的入口。
