# Codex Instructions for GPT-Codex AI Bridge Kit

本文件是 Codex 在维护本仓库、以及使用本仓库去配置其他机器或 repository 时的操作入口。面向人的总体说明以 `README.md` 为准；实现细节、状态机和 workflow 约束以 `docs/` 中对应规格为准。

## 1. 先判断作用域，不要把所有能力混成一次安装

Bridge Kit 的能力按作用域分成机器层、项目层和任务层。真正的安装对象只有机器层和项目层；Reviewed Handoff task 与 Agent-Flow task 都是运行实例，不是新的安装层。

```text
机器层
└── Host Policy                    once per CODEX_HOME

项目层
├── Lite Handoff                   default per repository
├── Reviewed Handoff               optional GPT-planned/reviewed workflow
├── Generic Notifier               optional
└── Agent-Flow Core                optional for high-risk repositories

任务层
├── Lite task
├── Reviewed Handoff task
└── Agent-Flow task                runtime instance, not installation
```

配置前必须先确认用户要处理的是“新机器/新 Codex identity”“新 repository”“中档 Reviewed Handoff”“通知能力”还是“某个具体高风险任务”。不要因为用户说“把 Bridge Kit 配上”就静默安装全部可选层。

## 2. 新机器 / 新 Codex identity

先确保本 package 可执行，然后安装 Host Policy。一个物理机器上如果存在不同 `$CODEX_HOME`，它们是不同 Codex identity，应分别处理。

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
ai-bridge host install
ai-bridge host validate
```

Codex Home 解析顺序必须是：显式 `--codex-home`，其次 `$CODEX_HOME`，最后 `~/.codex`。执行 host write 前必须明确打印实际目标路径，避免 Windows、WSL、服务器多身份或自定义 CODEX_HOME 下写错位置。

Host Policy 只管理以下用户级目标，不得把它们复制进 repository：

```text
$CODEX_HOME/config.toml
$CODEX_HOME/AGENTS.md
$CODEX_HOME/rules/ai-bridge-global.rules
```

必须保持的配置目标是：

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

安装必须非破坏式保留其他 TOML 配置，并在修改已有文件前创建 backup。不要通过 `approval_policy = "never"`、`danger-full-access` 或泛化 shell/python allow 解决审批问题。

全局 Host AGENTS 必须继续维持这些长期行为：用户可见 narrative 默认使用自然简体中文；会实质改变架构、范围、部署、branch 策略、外部行为或科学/产品语义的歧义应询问用户；普通局部实现细节自行完成；当前已选 `main` 分支上的 `git fetch origin main`、clean worktree 下的 `git pull --ff-only origin main`、task-owned 文件的 `git add ...`、普通 commit 和 `git push origin main` 可自动完成；同步前检查 working tree，dirty 时先判断 ownership，不得默认 autostash/stash/reset/restore；commit 前检查 staged diff；未经明确授权不得创建、切换、checkout、重命名或删除 branch，不得创建 PR、设置/改变 upstream、创建新远端分支、rebase/autostash pull、force push、删除远端 branch/tag、reset/clean/restore 用户工作或修改 remote。

全局 execpolicy 目前只维护当前分支普通开发所需的低打扰前缀：

```text
git fetch origin main
git pull --ff-only origin main
git add ...
git commit ...
git push origin main
```

这些规则用于跳过当前已选 `main` 分支安全同步、task-owned staging、普通 commit 和默认 `origin/main` push 的 manual/auto review。其他长期分支如果也需要低打扰 push，应由项目规则或用户明确授权补充，不得靠泛化 `git push origin ...` 猜测。`git pull --rebase ...`、`git pull ... --autostash`、`git push -u origin ...`、`git push --set-upstream origin ...`、`git push origin <new-branch>`、`git push origin --delete ...`、force push、创建或改变 upstream、创建新远端分支等不是普通同步或普通 push，必须先问用户。它们也不是对危险 Git 行为的授权；危险操作仍受 Host AGENTS 行为规则禁止。

## 3. 新 repository：默认先装 Lite Handoff

绝大多数正式 repository 应先使用 Lite Handoff，而不是 Reviewed Handoff 或 Agent-Flow。

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

Lite 初始化只管理 repository 内的长期交接结构，包括：

```text
AGENTS.md
prompts/
results/
docs/
.agents/skills/agent-task-executor/SKILL.md
```

不要让 `ai-bridge init` 静默修改 `$CODEX_HOME`，不要静默安装 Reviewed Handoff、Notifier 或 Agent-Flow。Host Policy 和 repo Handoff 是不同生命周期。

Lite task 的默认入口仍是：

```text
prompts/tasks/<task_key>.md
```

其结果默认写入：

```text
results/<task_key>/
```

Lite 适用于普通功能开发、bug 修复、常规重构和文档工作，也可以使用现有 Controller task。不要仅因为改动文件多或任务耗时长就自动升级工作流。

## 4. Generic Notifier：只有需要终态邮件时配置

Notifier 是 transport，不拥有 completion authority。用户需要终态邮件时才配置：

```bash
cd /path/to/project
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
```

`send-test` 必须真实发送成功后才能把该机器/项目视为 notifier ready。Secrets 保持在用户本地/private config，不得提交 repository，也不得打印 secret value。

推荐终态路径是：

```text
results/<task_key>/notification_brief.json
```

随后：

```bash
ai-bridge notifier send results/<task_key>/notification_brief.json
```

不要把 tmux、systemd、长期 polling watcher 当作 Notifier 的默认安装要求。`once` / `run` 只是可选兼容方式。

## 5. Reviewed Handoff：中等风险任务的默认独立复核模式

当任务需要 GPT 先做产品/语义/架构取舍、Codex 执行后再由独立 GPT 审核，但不需要 Agent-Flow 的独立合同、Verifier 和 Final Critic 时，使用 Reviewed Handoff。

典型场景包括外部 repository/skill intake、第三方能力引入、中等规模重构、文档体系迁移和普通产品 feature。它的判断标准不是修改文件数量，而是：Codex 不应该自己发明产品语义，并且用户希望实现后有一次真正独立的 GPT review。

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

三个逻辑角色固定为：

```text
Planner -> Executor -> Reviewer
```

Controller 只做机械状态推进，不是第四个 reasoning role。不得为了“更可靠”新增 Critic、Verifier、Auditor 或 Final Critic；需要这些角色时应直接改用 Agent-Flow。

Reviewed Handoff 的运行原则：

- GPT Planner 负责读取 source of truth、外部来源和已有能力，然后冻结 `PLAN.md`。产品/科学/架构取舍不得留给 Executor 自行决定。
- Executor 只在 `PLAN_FROZEN` 或 `REVISE` 执行。若冻结 Plan 存在无法安全推导的实质歧义，写 `NEEDS_GPT_PLANNER`，不要在 unattended run 中等待用户输入。
- Scheduled GPT Reviewer 只依据冻结 Plan、真实 `base_commit..implementation_commit` diff、当前测试/CI 和已有 regression boundary 审核；“还能更优雅”“可以再抽象一层”不是 blocker。
- 默认最多两轮 GPT review。第一轮 `REVISE` 允许一次 Codex repair；第二轮仍 `REVISE` 必须停止自动返修并进入 human gate。
- Scheduled GPT 最多允许一次最小 Plan revision；再次需要改变冻结 Plan 时必须交给用户。
- 所有终态都必须生成 `FINAL_REPORT.md`。用户最终应能只读这份报告理解解决了什么、改了哪里、获得了什么新能力、哪些方案被拒绝、example usage 和 remaining limitations。

GPT 异步唤醒使用 ChatGPT Scheduled Tasks/「安排任务」，通过 GitHub tracked `CURRENT.json` 与 Codex 协作，不使用 OpenAI API。没有需要 Planner/Reviewer 的 task 时，Scheduled Task 必须无副作用退出，不重复 review、不写无意义 commit、不通知用户。

Codex 异步唤醒由目标机器上的轻量 watcher 完成：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

Watcher 只处理 `PLAN_FROZEN` / `REVISE`，只使用已经 checkout 且获授权的 branch，不创建 branch/PR。它通过 `git fetch` + `merge --ff-only` 同步 `origin/<branch>`，working tree 不干净时 fail closed。机器本地 event 去重与日志必须存放在 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/`，不得为了 watcher state 修改目标 repository。

Watcher 不保留 persistent role thread、独立 worktree receipt 或 hash event identity。每个 executor event 启动一次新的 `codex exec`。Codex exit 0 本身不代表完成；只有 `CURRENT` 真正离开原 event 才算 progress。同一 event 自动执行尝试必须有界，耗尽时发布可见 operational `BLOCKED` 和 `FINAL_REPORT.md`，不得无限循环。

### Reviewed Handoff Anti-Overengineering Invariants

Reviewed Handoff 不是“小号 Agent-Flow”。禁止加入：

```text
request nonce
Requirement Ledger
Stable Review Snapshot
review_target_id
semantic source manifest
role receipt graph
Review Bundle SHA
artifact SHA graph
Final Critic
independent Verifier role
```

`base_commit` 和 `implementation_commit` 只是 Reviewer 定位真实 diff 的 Git locator，不是 workflow identity。不要因为 control-plane/state commit 移动就产生新的 review object。

如果发现一个 false-PASS 风险只能靠以上 Agent-Flow 证明机制解决，正确动作是升级该任务到 Agent-Flow，而不是继续加重 Reviewed Handoff。

Reviewed Handoff v0.5 的权威规格：

```text
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
```

## 6. Agent-Flow Core：仅对高风险 repository 显式安装

只有当任务需要独立合同审计、独立 Verifier、Stable Review Snapshot、Final Critic 和严格 human gate 时，才在 repository 叠加 Agent-Flow。

典型适用场景包括科研架构实现、昂贵训练/计算、数据或安全敏感逻辑、生产部署、重大迁移，以及 false PASS 代价很高的工作。

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

Agent-Flow install 必须 additive / idempotent，并且不得：

```text
修改 $CODEX_HOME
修改 Git remote
创建 branch
创建 PR
修改 Notifier secret/state
替换或破坏 Lite Handoff / Reviewed Handoff
```

Agent-Flow 的五个长期角色固定为：

```text
Planner
Critic
Controller
Verifier
Executor
```

不要新增功能重叠的 Reviewer/Auditor/Coordinator 角色来扩大流程。Planner 拥有用户/产品/科学意图与实现审查权；Critic 只参与 initial contract audit、必要 contract review 和 final audit；Controller 只做机械状态/路由；Verifier 只能基于冻结 requirement 建立阻断 oracle；Executor 只负责实现和授权 runtime evidence。

Agent-Flow 的核心设计必须保持“严格验证、简单编排”。不要把 CARE 原型中的大量 receipt/hash/moving Git target 复制进 generic core。Stable Review Snapshot 的语义身份只能由真正的合同、Requirement Ledger、implementation semantic source 和 verifier semantic source 决定；CURRENT、Controller receipt、通知、文档等控制平面变化不得默认触发 heavy re-verification。

### Agent-Flow Anti-Overengineering Invariants

Semantic identity must stay small. `review_target_id` 只能由 task identity、frozen contract digest、Requirement Ledger digest、implementation semantic digest 和 verifier semantic digest 组成。未经用户明确架构决策，不得把 Git locator SHA、`CURRENT.json`、Controller state、Controller merge commit、role/session receipt hashes、Review Bundle hash、Planner review packet hash、Final Critic artifact hash、CI-record commit、runtime receipt commit、notification brief 或 documentation-only files 加入 `review_target_id`。Git SHA 可以作为 locator/provenance，但不能因为 Git history 移动而改变 semantic review identity。

No provenance hash cycles. 禁止设计 `A hashes B`、`B hashes C`、`C hashes A`，也禁止通过 commit、receipt、manifest 的相互绑定间接形成 cycle。合法结构必须保持单向：semantic source -> semantic target -> current evidence -> Review Bundle -> Planner / Final Critic。

Control-plane changes stay lightweight. `CONTROL_PLANE_ONLY_CHANGED`、`RECEIPT_OR_MANIFEST_ONLY_CHANGED`、`CURRENT_OR_ROUTING_ONLY_CHANGED` 和 `DOC_ONLY_CHANGED` 默认不得触发新 semantic target、Executor restart 或 heavy Verifier，除非 Project Profile 明确把相关文件声明为 semantic source。

Heavy verification requires semantic reason. 相同 `review_target_id` 的第二次 heavy Verifier 必须具有机器可验证的 semantic invalidation reason；receipt update、`CURRENT` update、Controller retry、notification、documentation 和 provenance repair 不是 heavy rerun 理由。

Review Bundle stays compact. `REVIEW_BUNDLE.json` 只包含当前 target 所需的 current evidence references。不得重新引入 all historical receipts、giant runtime manifests、full smoke history、all previous Planner/Critic packets 或 all Controller transaction history。历史 artifact 可以保留供审计，但不能默认复制进每个 current Review Bundle。

New provenance fields need justification. 未来如果 Codex 认为需要增加新的 SHA、digest、receipt、manifest、binding 或 state，必须先回答：它防止什么具体 false PASS；现有 semantic identity / typed evidence 为什么不能解决；它是否会导致 receipt-only 或 control-plane-only change 触发昂贵重跑；是否形成新的 hash dependency chain；是否可以通过普通字段或 locator 解决而无需 hash。没有明确收益时不增加。

Agent-Flow v0.4 的当前实现与正确性要求以以下文件为准：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
```

## 7. Agent-Flow task：这是运行实例，不是安装层

在 repository 已安装 Agent-Flow 后，只有出现一项具体高风险任务时才初始化 task：

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key <task_key>
```

这一步创建的是该任务自己的 `REQUEST.json`、`CURRENT.json` 和后续 contract/evidence 生命周期。它不能被描述为新的安装层。同一个 Agent-Flow Core 可以承载多个互相独立的 task，每个 task 必须拥有独立 objective、request nonce、frozen contract、Requirement Ledger、review target、repair history 和 human gate。

如果没有一个具体的高风险 objective，不要为了“预先配置好”而创建空 Agent-Flow task。

## 8. 安装决策默认值

当用户只说“在新服务器把 Bridge Kit 配好”，默认完成 package + Host Policy，并验证 Host Policy。不要顺便初始化任意 repository。

当用户只说“把这个 repository 接入 Handoff”，默认安装 Lite Handoff，并检查 Host Policy 状态；不要因为 repository 很复杂就自动加 Reviewed Handoff 或 Agent-Flow。

当用户明确要求“GPT 先规划、Codex 实现、再让 GPT 自动审核/返修”，或者明确选择 Reviewed Handoff 时，在 Lite 基础上安装 Reviewed Handoff。若是否启用独立 GPT review 会实质改变用户工作方式而用户没有表达，应先说明/确认，不要静默升级。

当用户明确说“这个项目需要终态通知”，在所选 workflow 基础上配置 Notifier。

当用户明确要求 Agent-Flow，或任务明显属于高风险且用户已经选择 Agent-Flow 工作方式时，再安装 Agent-Flow Core。若是否升级到 Agent-Flow 会实质改变工作流，应向用户确认，而不是自行决定。

当用户说“用 Agent-Flow 做这次 XXX”，如果 repository 尚未安装 Agent-Flow，则先安装/验证 Agent-Flow Core，再为 XXX 创建 task；如果已经安装，则只创建或复用对应 task，不要重复安装整个 Core。

## 9. Git 与 branch 规则

在本仓库及通过本 Kit 管理的 repository 中，默认继续当前 branch。当前已选 `main` 分支上的 `git fetch origin main`、clean worktree 下的 `git pull --ff-only origin main`、task-owned 文件 staging、普通 commit 和 `git push origin main` 是预授权开发动作；其他明确获授权的普通 `origin` push 可按项目规则执行。未经用户明确授权，不得执行任何会创建、切换、checkout、重命名或删除 branch 的命令，包括 `git switch`、`git switch -c`、`git checkout`、`git checkout -b`、`git branch <new>`、`git branch -d/-D/-m`、通过 worktree 创建或选择 branch，或把新 remote branch / upstream 当作“不推当前 branch”的替代方案。

Reviewed Handoff watcher 只能同步和使用用户已经授权且当前 checkout 的 branch，不得自动 switch branch。Agent-Flow 为 Verifier/Executor 做角色隔离时，优先使用 detached worktree；如果确实需要长期 role branch，先向用户请求该 branch 的明确授权。

当前已选 `main` 分支上的安全同步、task-owned staging、普通 commit 和 `origin/main` push 可按 Host Policy 执行。不得自动 rebase/autostash pull、force push、`--force-with-lease`、删除远端 branch/tag、设置/改变 upstream、创建新远端分支、reset/clean/restore 用户工作、添加/删除/重定向 remote。

## 10. 修改本仓库时的文档规则

根 `README.md` 是写给人的。默认必须使用中文自然段落解释整体模型、安装边界和用户路径；不要把 README 写成大量英文协议条款、控制台日志或机器 schema dump。代码、命令、路径、配置键、状态名、API 名称等技术字面量保持英文即可。

根 `AGENTS.md` 是写给 Codex 的操作入口，应保持可执行、明确、低歧义。复杂 workflow 状态机、schema 和历史设计放在 `docs/`，不要把全部实现规格重复复制到 README。

如果 README 与实现发生冲突，应修 README；Reviewed Handoff 行为与 `docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md` 冲突时优先修实现；Agent-Flow 行为与 `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md` 冲突时也优先按规格修实现，除非用户明确改变了架构决策。

## 11. 兼容性和发布

任何新能力都必须保持以下旧入口可用：

```text
ai-bridge
ai-bridge init
ai-bridge validate
ai-bridge prompt
ai-bridge where
ai-bridge host ...
ai-bridge notifier ...
ai-bridge agent-flow ...
```

并保持 Reviewed Handoff 新入口：

```text
ai-bridge reviewed-handoff ...
ai-bridge reviewed-handoff watcher ...
```

Lite Handoff 不能因为 Reviewed Handoff 或 Agent-Flow 演进而变复杂。Host Policy、Lite、Reviewed Handoff、Notifier、Agent-Flow 彼此保持清晰边界，新增一层不得静默改变其他层。

发布前必须运行现有回归测试和对应新功能测试。没有真实 GitHub Actions green evidence 时，不要把“本地测试通过”描述成“远端 CI 已通过”。稳定 tag 不得移动或覆盖；没有用户授权时不要创建新的 release tag。
