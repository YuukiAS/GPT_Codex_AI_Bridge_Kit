# Codex Instructions for GPT-Codex AI Bridge Kit

本文件是 Codex 在维护本仓库、以及使用本仓库去配置其他机器或 repository 时的操作入口。面向人的总体说明以 `README.md` 为准；实现细节、状态机和 workflow 约束以 `docs/` 中对应规格为准。

## 0. Bridge 正式分发 owner locator

Bridge runtime、Host、Lite、Review、Control、Persistent Run 的实现 authority 仍然属于本仓库 GPT-Codex AI Bridge Kit。

Bridge 的正式 distribution / version closure，包括移动的 `release` ref，由 AI Skills Maintainer（`ai-skills-core` 内部 `bridge-kit-maintainer`）负责。一次 Bridge formal release 在交给该 owner 完成正式分发闭环前，不得称为 distribution-complete。

完整 fast-forward-only producer contract 单一保存在 `YuukiAS/AI_Skills_Collection` 的 AI Skills Maintainer source/reference layer；本仓库只保留这个 locator，不复制第二套 release engine、policy、watcher、state machine 或 ref 管理实现。

## 1. 先判断作用域，不要把所有能力混成一次安装

Bridge Kit 的能力按作用域分成机器层、项目层和任务层。真正的安装对象只有机器层和项目层；Review task 与 Control task 都是运行实例，不是新的安装层。

```text
机器层
└── Machine Policy                 once per CODEX_HOME, command remains ai-bridge host

项目层
├── Lite                default per repository
├── Reviewed Mode       optional GPT-planned/reviewed workflow
├── Notifications       optional
├── Overleaf Bridge     optional manuscript publication mirror
├── Persistent Run      optional tmux persistence contract for terminal-owned Goals that must survive disconnect
└── Controlled Mode     optional for high-risk repositories

任务层
├── Lite task
├── Reviewed Mode task
└── Controlled Mode task  runtime instance, not installation
```

配置前必须先确认用户要处理的是“新机器/新 Codex identity”“新 repository”“中档 Review”“通知能力”“Overleaf 论文镜像能力”“长期 Goal 的 Persistent Run 能力”还是“某个具体高风险任务”。不要因为用户说“把 Bridge Kit 配上”就静默安装全部可选层。

对既有 repository 做安装、升级或盘点时，必须先做真实 workflow inventory，再决定是否更新 repo 内模板。不要只按猜测目录或截图标签判断。至少检查这些标准位置和关键文件：

```text
automation/reviewed_handoff/
automation/agent_flow/
automation/reviewed_handoff/tasks/*/CURRENT.json
automation/agent_flow/tasks/*/CURRENT.json
automation/agent_flow/ROLE_AUTHORITY_POLICY.md
```

判断规则是：只有 Lite 时通常只更新 Host Policy；发现 `automation/reviewed_handoff/` 时应按 Review 更新控制模板/提示词；发现 `automation/agent_flow/` 时应按 Control 更新控制模板/提示词；发现自定义 Planner/Reviewer 状态机时，先读取其 schema、state ownership、`next_action` 和 workflow contract，再判断是否需要同步 External GPT wait 规则。若用户点名某个 repo “不可能没有”，必须重新查标准控制目录、关键 state 文件和 `AGENTS.md`/`prompts` 中的 workflow marker，不能沿用先前结论。

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
default_mode_request_user_input = false
memories = true
```

`default_mode_request_user_input=false` 是有意配置。Default mode 中真正必需的 `HUMAN_ONLY` 输入用一条 plain-text 问题并停止依赖执行；到 deadline / 本轮结束仍无答案时报告 `GOAL_BLOCKED=YES`、`GOAL_ACHIEVED=NO`、`COMPLETE=NO`、`READY_FOR_USER_REVIEW=NO`。`ai-bridge host validate` 仍必须确认 Codex 支持该 key；Plan-mode native blocking 语义独立。安装 Host Policy 必须非破坏式保留其他 TOML 配置并创建 backup；不得用 `approval_policy = "never"`、`danger-full-access` 或泛化 shell/python allow 解决审批。

全局 Host AGENTS 必须维持这些长期行为：用户可见 narrative 默认自然简体中文；架构、范围、部署、branch 策略、外部行为或科学/产品语义会实质改变时询问用户，普通局部实现细节自行完成；workspace 内 build/test/lint/render/QA/deterministic scripts/task-owned generated output 默认先走普通 `workspace-write`，命令是 Python/TeX/shell/compiler/build tool 或写入允许 workspace 本身都不是 escalation 理由。真实 private transfer、paid/external call、deployment、migration、scheduler/resource allocation、Persistent Run launch、destructive action，或 provider/artifact/recipient/purpose/resource/cost/backend scope 改变，仍走 approval / `HUMAN_ONLY` / Planner / STOP。refusal 后先分类 `OPTIONAL_NOT_REQUIRED`、`SANDBOX_CAPABLE_BUT_ESCALATED`、`BOUNDED_NORMAL_ENTRY_BLOCKER`、`TRUE_AUTHORITY_OR_SAFETY_BOUNDARY`；bounded helper 失败不授权 raw 宽操作。

当前分支普通开发的低打扰前缀只包括：

```text
git fetch origin main
git pull --ff-only origin main
git add ...
git commit ...
ai-bridge host publish-current-branch --expected-repo <owner/repo> --expected-branch <branch>
ai-bridge reviewed-handoff task publish-first --task-key <task_key> --expected-repo <owner/repo>
```

这些规则只覆盖当前已选 `main` 安全同步、task-owned staging、普通 commit、bounded current-branch publisher 和 exact Reviewed first-bootstrap control metadata 首次发布。`git pull --rebase`、`--autostash`、raw `git push origin main`、`git push -u` / `--set-upstream`、创建/删除/重命名/切换 branch、创建新远端 branch、force / `--force-with-lease`、reset/clean/restore、remote mutation 和 PR 创建都必须另获明确授权。

Host Policy 的 read-only diagnostics allowlist 保持窄边界：直接 `squeue`、`sinfo`、`sacct`、`sstat`、`sprio`、`scontrol show ...` / `scontrol ping` 只是 Slurm inspection；`sbatch`、`srun`、`salloc`、`scancel`、mutating `scontrol`、`sacctmgr modify/add/delete` 仍审批。直接 `ps`、`git fetch --all --prune`、`tmux ls` / `tmux list-sessions` / `tmux has-session` 只用于低风险诊断；`kill`、`pkill`、`renice`、`setsid`、`sudo`、generic shell/Python、tmux mutation/control、arbitrary git fetch URL/refspec 和危险 Git 仍 gated。不要把 optional diagnostic failure 升级成新 allocation、cancellation、wrapper 或状态机。

### Production Plugin Replay

Host Policy 可以全局预授权一个受控的真实插件回归入口：

```text
ai-bridge plugin-replay ...
```

当用户或冻结 workflow 已经授权本机 production plugin repair/replay，且确实需要 fresh Codex runtime 测试当前 Codex identity 中已安装的插件时，使用这个入口。不要自行拼 raw nested `codex exec` 再申请审批。

`plugin-replay` 只允许 target Git repo 内文件或 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/inbox/` 的显式 input；symlink resolve 后仍在授权根内。task/instruction file 只能来自 target repo、caller repo 或同一 inbox。replay 使用当前 Codex identity，不切换 `$CODEX_HOME`；输出留在 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/`。它是 write-isolated / execution-bounded trusted-local replay，不授权外部上传、发布、危险 Git、branch/remote mutation、release/deploy 或产品/科学 scope expansion。

### External Planner / Reviewer Waiting

通用 external GPT 等待规则必须保留：当 repo-controlled workflow 表示下一动作属于外部 GPT Planner/Reviewer/Critic/Final Critic 等 reasoning role，未出现新 decision 是正常等待。识别以 state ownership、`next_action`、role policy、schema 和 workflow contract 为准；`READY_FOR_GPT_REVIEW`、`NEEDS_GPT_PLANNER`、`WAITING_FOR_EXTERNAL_GPT` 等只是例子。`MIN_EXTERNAL_GPT_WAIT = 2 hours` 是正常等待下限，不是自动 `BLOCKED` deadline；等待不得消耗 review/repair/plan/retry/critic/blocked-audit 预算。stale Planner/Reviewer/Critic artifact 不能触发 repair 或 PASS。无法保持活动时只报告 `waiting_external_review` 并保持 tracked state；只有 automation disabled/deleted、connector/auth repeated failure、外部角色缺失、非法 state、必需 artifact 不可达、真实 visual 环境不可用、用户必须新决策或 hard deadline 已过等可观察失败，才可写明 evidence 进入 `BLOCKED`。

## 3. 新 repository：默认先装 Lite

绝大多数正式 repository 应先使用 Lite，而不是 Review 或 Control。

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

不要让 `ai-bridge init` 静默修改 `$CODEX_HOME`，不要静默安装 Review、Notifier、Overleaf Bridge 或 Control。Host Policy 和 repo Handoff 是不同生命周期。

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

## 5. Persistent Run：只有长期 Goal 需要持久执行时配置

Persistent Run 是项目层可选能力，不是第四套 workflow。Lite / Review /
Control 三档 workflow 保持不变；Persistent Run 只约束明确标记为 persistent
execution、且实际进程或 orchestrator 由终端拥有并必须在 Codex / SSH /
terminal 断开后继续运行的 Goal 如何通过 canonical tmux session 启动、恢复和观察。

安装命令：

```bash
ai-bridge persistent-run install --target /path/to/project
ai-bridge persistent-run validate --target /path/to/project
```

安装只管理：

```text
automation/persistent_run/README.md
automation/persistent_run/CONTRACT_TEMPLATE.md
automation/persistent_run/KICKOFF_TEMPLATE.md
AGENTS.md 中的 ai-bridge-kit:persistent-run managed block
```

不得因为安装 Persistent Run 而安装 Lite / Review / Control，不得修改
`$CODEX_HOME`、Host Policy 或 `.codex/rules`，不得新增 workflow state machine、
Planner、Reviewer、Critic、Verifier、watcher、daemon、scheduler command 或
background-service command。

0.8.0 的唯一 persistence backend 是 `tmux`。Persistent Run 不全局预授权
`tmux new-session` / `tmux send-keys`，也不放开 `setsid`、`nohup`、裸后台 `&`、
`screen`、`sudo`、`sbatch`、`salloc`、`srun`、`scancel`、generic shell 或
generic Python。需要真实长期启动时，用户必须通过
`ai-bridge persistent-run prompt kickoff --target <repo> --goal <repo-relative-goal>`
生成并发送当前用户可见 kickoff 授权；这个命令只打印文本，不启动 tmux。

0.9.2 起，GPT 写任务时必须把 execution lifetime 与 `task_type` / Lite /
Review / Control workflow 分开判断，并进一步拆开三件事：upfront
authorization readiness、process persistence topology、project-native progress
reporting。overnight、unattended、run until morning、multi-hour 或 leave it
running 只触发这套判断，不自动选择 Persistent Run/tmux，也不是自动升级
Review / Control 或 controller task 的理由。

scheduler-owned batch job（例如已接受的 `sbatch`）或 already-detached
service/job 不应仅因 duration 增加 tmux；应写清 exact scheduler/resource
authorization boundary 和 scheduler/project-native progress evidence，并让原生
owner 负责寿命。terminal-owned foreground process/orchestrator 若必须 survive
Codex / SSH / terminal disconnect，且没有 scheduler/service/project-native owner
已经提供寿命，才选择 Persistent Run/tmux。如果目标仓库已安装
`automation/persistent_run/`，GPT 必须读取其中 README 和
`CONTRACT_TEMPLATE.md`，并在 Goal/task 中写明 `Persistent execution: REQUIRED`、
`Backend: tmux`、`Goal source`、`Run/session key`、authorized effects、resource
boundary、forbidden expansion、recovery evidence、heartbeat / stage-state /
checkpoint / resume semantics 和原始 positive completion criteria。如果确实需要
terminal-owned survive-disconnect 持久执行，但仓库未安装 Persistent Run，且用户
没有选择等价的项目原生持久执行合同，不得降级成普通 live-session task。

Codex 执行前必须做 upfront authorization preflight：先读取 frozen Goal/task 中
正面声明的 approval-sensitive effects，例如 Persistent Run kickoff / canonical
tmux launch、具体 private external transfer、具体 paid/external API call、deployment
或 resource allocation。仓库内 Goal/Plan/contract 是 frozen scope evidence，不等于
当前用户可见授权。若当前用户消息已经包含同一个 frozen effect 的 bounded authorization，
后续到达同一 effect 时不要重复询问；若没有，应在大量前置工作、昂贵执行、长期执行或
canonical launch 前提出绑定具体 Goal、artifact/hash、recipient/provider、purpose、
resource boundary、backend 和 scope limit 的授权请求。新的 artifact、recipient/provider、
resource、purpose、backend 或越界副作用仍需重新授权。

收到 kickoff 后，Codex 应按 Goal/project 指定的 canonical session/run key 检查
`tmux has-session` / `tmux ls`，并读取 lock / heartbeat / stage-state /
checkpoint / resume evidence。已有兼容 run 时 resume，不重复启动。optional
diagnostic failure 不得自动终止整个 Goal；Codex / SSH disconnect 不得解释为实验失败；
session/job/PID/heartbeat/checkpoint 只证明活动或状态，不证明 Goal 完成。资源、科学
scope、训练预算、数据、模型和 completion 继续由原 Goal/task/workflow 决定。

## 6. Overleaf Bridge：只有需要论文 publication mirror 时配置

Overleaf Bridge 是项目层可选 publication mirror，不是 Handoff task、Review、Control、watcher、Scheduled Task 或新 role。Codex 仍读科研 monorepo 根目录；Overleaf 只接收配置的 `paper_root`。Overleaf 不能从 GitHub monorepo 只 Pull 子目录；正确语义是在机器本地维护独立 Overleaf Git mirror，并投影 consumer repo 的 manuscript root。consumer repo 只安装：

```text
automation/overleaf/
├── README.md
└── config.toml
```

并在根 `AGENTS.md` 维护 Overleaf managed block。机器本地 state 放在：

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/
```

`mirror/` 是 Overleaf Git project 的本地 clone；`connection.json` 可保存 URL、baseline digest、remote/local locator 和 managed paths，但不得保存 token。

常用命令：

```bash
ai-bridge overleaf install --target /path/to/repo --paper-root paper/manuscript
ai-bridge overleaf connect --target /path/to/repo --remote-url https://git@git.overleaf.com/<PROJECT_ID> --bootstrap
ai-bridge overleaf status --target /path/to/repo
ai-bridge overleaf push --target /path/to/repo
ai-bridge overleaf pull --target /path/to/repo
ai-bridge overleaf validate --target /path/to/repo
```

不得把 Overleaf 当作科研 repo 第二个 remote；不得修改 consumer repo 的 `origin`、branch topology、upstream 或 remote list，不得 force push、创建 branch/PR/tag/release。认证边界：不添加 `--token`/`--password`，不把 token 写进 URL、state、tracked config、README、日志或异常，真实访问由 Git credential helper 处理。同步必须维护 baseline digest：remote ahead 拒绝 push，local ahead 拒绝 pull，双边不同为 diverged/fail closed；`pull` 只导入 `paper_root`、只删除 Bridge 曾管理的 publication files、保留 `exclude_paths`，不改 `paper_root` 外文件，不自动 commit/push。

## 7. Review：中等风险任务的默认独立复核模式

当任务需要 GPT 先做产品/语义/架构取舍、Codex 执行后再由独立 GPT 审核，但不需要 Control 的独立合同、Verifier 和 Final Critic 时，使用 Review。

典型场景包括外部 repo/skill intake、第三方能力引入、中等重构、文档迁移和普通产品 feature。判断标准不是文件数量，而是 Codex 不应自创产品语义且用户希望实现后有独立 GPT review。

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

三个逻辑角色固定为：

```text
Planner -> Executor -> Reviewer
```

Controller 只做机械状态推进，不是第四个 reasoning role。不得为了“更可靠”新增 Critic、Verifier、Auditor 或 Final Critic；需要这些角色时应直接改用 Control。

Review 的运行原则：

- GPT Planner 负责读取 source of truth、外部来源和已有能力，然后冻结 `PLAN.md`。产品/科学/架构取舍不得留给 Executor 自行决定。
- Executor 只在 `PLAN_FROZEN` 或 `REVISE` 执行。若冻结 Plan 存在无法安全推导的实质歧义，写 `NEEDS_GPT_PLANNER`，不要在 unattended run 中等待用户输入。
- Scheduled GPT Reviewer 只依据冻结 Plan、真实 `base_commit..implementation_commit` diff、当前测试/CI 和已有 regression boundary 审核；“还能更优雅”“可以再抽象一层”不是 blocker。
- 默认最多两轮 GPT review。第一轮 `REVISE` 允许一次 Codex repair；第二轮仍 `REVISE` 必须停止自动返修并进入 human gate。
- Scheduled GPT 最多允许一次最小 Plan revision；再次需要改变冻结 Plan 时必须交给用户。
- 所有终态都必须生成 `FINAL_REPORT.md`。用户最终应能只读这份报告理解解决了什么、改了哪里、获得了什么新能力、哪些方案被拒绝、example usage 和 remaining limitations。

GPT 异步唤醒使用 ChatGPT Scheduled Tasks，通过 GitHub tracked `CURRENT.json` 协作，不使用 OpenAI API；无 Planner/Reviewer task 时无副作用退出。

Codex 异步唤醒由目标机器上的轻量 watcher 完成：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

Watcher 只处理 `PLAN_FROZEN` / `REVISE`，只使用已 checkout 且获授权 branch，不创建 branch/PR；用 `git fetch` + `merge --ff-only` 同步 `origin/<branch>`，dirty fail closed。本地 event 去重与日志放 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/`，不为 watcher state 改目标 repo。每个 executor event 启动一次新 `codex exec`；exit 0 不代表完成，只有 `CURRENT` 离开原 event 才算 progress；尝试有界，耗尽写 operational `BLOCKED` + `FINAL_REPORT.md`。

### Review Anti-Overengineering Invariants

Review 不是“小号 Control”。禁止加入：

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

如果发现一个 false-PASS 风险只能靠以上 Control 证明机制解决，正确动作是升级该任务到 Control，而不是继续加重 Review。

Review v0.5 的权威规格：

```text
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
```

若 Review 依赖完整 Markdown/plain-text artifact 但 plaintext 不能公开提交，使用 Text Review evidence path：本机 `ai-bridge text-review encrypt` 生成 encrypted payload + `text_inputs.json`，GitHub Actions 用 `AI_BRIDGE_PRIVATE_REVIEW_AGE_KEY` 临时解密并调用 OpenAI Responses API `store=false` 产出 `TEXT_REVIEW.json`。它是 Scheduled GPT Reviewer evidence，不是新 role；缺失、stale、plaintext SHA/manifest mismatch 不得 PASS。

## 8. Control：仅对高风险 repository 显式安装

只有当任务需要独立合同审计、独立 Verifier、Stable Review Snapshot、Final Critic 和严格 human gate 时，才在 repository 叠加 Control。

典型场景包括科研架构、昂贵训练/计算、数据或安全敏感逻辑、生产部署、重大迁移，以及 false PASS 代价很高的工作。

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

Control install 必须 additive / idempotent，并且不得：

```text
修改 $CODEX_HOME
修改 Git remote
创建 branch
创建 PR
修改 Notifier secret/state
替换或破坏 Lite / Review
```

Control 的五个长期角色固定为：

```text
Planner
Critic
Controller
Verifier
Executor
```

不要新增重叠 Reviewer/Auditor/Coordinator。Planner 拥有用户/产品/科学意图与实现审查权；Critic 只做 initial/必要 contract/final audit；Controller 只做机械路由；Verifier 基于冻结 requirement 建阻断 oracle；Executor 只负责实现和授权 runtime evidence。Control 必须“严格验证、简单编排”，不要把 CARE 原型的大量 receipt/hash/moving Git target 复制进 generic core；Stable Review Snapshot 语义身份只由合同、Requirement Ledger、implementation semantic source、verifier semantic source 决定，控制面变化默认不触发 heavy re-verification。

### Control Anti-Overengineering Invariants

Semantic identity must stay small. `review_target_id` 只能由 task identity、frozen contract digest、Requirement Ledger digest、implementation semantic digest、verifier semantic digest 组成。未经用户明确架构决策，不得加入 Git locator SHA、`CURRENT.json`、Controller state/merge commit、receipt hashes、Review Bundle hash、Planner/Final Critic artifact hash、CI/runtime/notification/doc-only 文件。Git SHA 可作 locator/provenance，不能改变 semantic review identity。

No provenance hash cycles. 禁止直接或间接 hash cycle；合法结构单向：semantic source -> semantic target -> current evidence -> Review Bundle -> Planner / Final Critic。

Control-plane changes stay lightweight. `CONTROL_PLANE_ONLY_CHANGED`、`RECEIPT_OR_MANIFEST_ONLY_CHANGED`、`CURRENT_OR_ROUTING_ONLY_CHANGED` 和 `DOC_ONLY_CHANGED` 默认不得触发新 semantic target、Executor restart 或 heavy Verifier，除非 Project Profile 明确把相关文件声明为 semantic source。

Heavy verification requires semantic reason. 相同 `review_target_id` 再跑 heavy Verifier 必须有机器可验证的 semantic invalidation；receipt、`CURRENT`、retry、notification、docs 和 provenance repair 不是理由。

Review Bundle stays compact. `REVIEW_BUNDLE.json` 只含当前 target 所需 evidence references；不要复制全部历史 receipts、runtime manifests、smoke history、旧 Planner/Critic packets 或 Controller transaction history。

新增 SHA/digest/receipt/manifest/binding/state 前必须说明防止什么 false PASS、现有 identity/evidence 为何不足、是否导致 receipt/control-plane-only 触发重跑、是否形成 hash dependency chain、是否可用普通字段/locator 替代；无明确收益不增加。

Control v0.4 的当前实现与正确性要求以以下文件为准：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
```

## 9. Control task：这是运行实例，不是安装层

在 repository 已安装 Control 后，只有出现一项具体高风险任务时才初始化 task：

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key <task_key>
```

这一步创建的是该任务自己的 `REQUEST.json`、`CURRENT.json` 和后续 contract/evidence 生命周期。它不能被描述为新的安装层。同一个 Control 可以承载多个互相独立的 task，每个 task 必须拥有独立 objective、request nonce、frozen contract、Requirement Ledger、review target、repair history 和 human gate。

如果没有一个具体的高风险 objective，不要为了“预先配置好”而创建空 Control task。

## 10. 安装决策默认值

当用户只说“在新服务器把 Bridge Kit 配好”，默认完成 package + Host Policy，并验证 Host Policy。不要顺便初始化任意 repository。

当用户只说“把这个 repository 接入 Handoff”，默认安装 Lite，并检查 Host Policy 状态；不要因为 repository 很复杂就自动加 Review 或 Control。

当用户明确要求“GPT 先规划、Codex 实现、再让 GPT 自动审核/返修”，或者明确选择 Review 时，在 Lite 基础上安装 Review。若是否启用独立 GPT review 会实质改变用户工作方式而用户没有表达，应先说明/确认，不要静默升级。

当用户明确说“这个项目需要终态通知”，在所选 workflow 基础上配置 Notifier。

当用户明确说“把论文同步到 Overleaf”“安装 Overleaf Bridge”或等价表达时，在所选 repository 中配置 Overleaf Bridge。若 `paper_root`、`main_document`、真实 Overleaf project URL 或首次接入方向会实质改变论文协作语义，应先确认；不要自行选择 `prefer-local` / `prefer-remote` 或把整个 GitHub repo 导入 Overleaf。

当用户明确说“安装 Persistent Run”“给这个长期 Goal 加持久执行”“生成 persistent kickoff”或等价表达时，只安装/验证 Persistent Run 或打印 kickoff。不要把它升级成 Review / Control，不要创建新的 task state machine，不要启动 tmux，不要把 repo 文件当成当前用户授权。若是否长期运行、run/session key、资源边界或 Goal 文件身份会改变任务语义，应先确认。

当用户明确要求 Control，或任务明显属于高风险且用户已经选择 Control 工作方式时，再安装 Control。若是否升级到 Control 会实质改变工作流，应向用户确认，而不是自行决定。

当用户说“用 Control 做这次 XXX”，如果 repository 尚未安装 Control，则先安装/验证 Control，再为 XXX 创建 task；如果已经安装，则只创建或复用对应 task，不要重复安装整个 Core。

## 11. Git 与 branch 规则

在本仓库及通过本 Kit 管理的 repository 中，默认继续当前 branch。当前已选 `main` 分支上的 `git fetch origin main`、clean worktree 下的 `git pull --ff-only origin main`、task-owned 文件 staging、普通 commit 和 bounded `ai-bridge host publish-current-branch` 是预授权开发动作；raw `git push origin main` 保持审批路径。未经用户明确授权，不得执行任何会创建、切换、checkout、重命名或删除 branch 的命令，包括 `git switch`、`git switch -c`、`git checkout`、`git checkout -b`、`git branch <new>`、`git branch -d/-D/-m`、通过 worktree 创建或选择 branch，或把新 remote branch / upstream 当作“不推当前 branch”的替代方案。

Review watcher 只能同步和使用用户已经授权且当前 checkout 的 branch，不得自动 switch branch。Control 为 Verifier/Executor 做角色隔离时，优先使用 detached worktree；如果确实需要长期 role branch，先向用户请求该 branch 的明确授权。

当前已选 `main` 分支上的安全同步、task-owned staging、普通 commit 和 bounded current-branch publisher 可按 Machine Policy 执行。不得自动 raw push、rebase/autostash pull、force push、`--force-with-lease`、删除远端 branch/tag、设置/改变 upstream、创建新远端分支、reset/clean/restore 用户工作、添加/删除/重定向 remote。

## 12. 修改本仓库时的文档规则

根 `README.md` 是写给人的。默认必须使用中文自然段落解释整体模型、安装边界和用户路径；不要把 README 写成大量英文协议条款、控制台日志或机器 schema dump。代码、命令、路径、配置键、状态名、API 名称等技术字面量保持英文即可。

根 `AGENTS.md` 是写给 Codex 的操作入口，应保持可执行、明确、低歧义。复杂 workflow 状态机、schema 和历史设计放在 `docs/`，不要把全部实现规格重复复制到 README。

README 的信息架构必须保持“版本历史”和“当前使用说明”分离：只能有一个 canonical version-history section，按旧到新记录版本增量；不得同时维护“功能与版本”“版本演进”“某版本解决了什么”等重复历史区。Capability section 描述 current state，标题不写 introduced version；后续版本增强已有 capability 时，只在 version-history 记录增量，并把 capability section 更新为最新完整行为，不在正文里累积 changelog 段落。Capability section 应按用户理解和使用层级排序，而不是发布时间；每次 release/refinement closure 都要检查 README 的整体目录、重复信息和阅读顺序，不能只 append 新段落。

如果 README 与实现发生冲突，应修 README；Review 行为与 `docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md` 冲突时优先修实现；Control 行为与 `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md` 冲突时也优先按规格修实现，除非用户明确改变了架构决策。

## 13. 兼容性和发布

任何新能力都必须保持以下旧入口可用：

```text
ai-bridge
ai-bridge init
ai-bridge validate
ai-bridge prompt
ai-bridge where
ai-bridge host ...
ai-bridge notifier ...
ai-bridge overleaf ...
ai-bridge persistent-run ...
ai-bridge agent-flow ...
```

并保持 Review 新入口：

```text
ai-bridge reviewed-handoff ...
ai-bridge reviewed-handoff watcher ...
```

Lite 不能因为 Review、Overleaf Bridge、Persistent Run 或 Control 演进而变复杂。Host Policy、Lite、Review、Notifier、Overleaf Bridge、Persistent Run、Control 彼此保持清晰边界，新增一层不得静默改变其他层。

发布前必须运行现有回归测试和对应新功能测试。没有真实 GitHub Actions green evidence 时，不要把“本地测试通过”描述成“远端 CI 已通过”。稳定 tag 不得移动或覆盖；没有用户授权时不要创建新的 release tag。
