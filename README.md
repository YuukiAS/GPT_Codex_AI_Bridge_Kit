# GPT-Codex AI Bridge Kit

这是一个用于 ChatGPT/GPT 与 Codex 协作的本地工作流工具包。它的目标不是再造一个复杂的 Agent 平台，而是把长期配置、项目交接、高风险任务闭环和终态通知拆成彼此独立的层，让不同项目只安装自己真正需要的部分。

最重要的理解方式不是“有五个安装等级”，而是分成三个作用域：**机器层、项目层和任务层**。其中真正需要安装的只有机器层和项目层；Agent-Flow 的 task 只是某一次高风险工作的运行实例，不是新的安装层。

```text
机器层
└── Host Policy                    每个 CODEX_HOME 安装一次

项目层
├── Lite Handoff                   每个正式项目默认安装
├── Generic Notifier               需要终态邮件时可选安装
└── Agent-Flow Core                高风险项目显式安装

任务层
├── Lite task                      一份轻量任务交接文件
└── Agent-Flow task                一次独立的高风险工作流实例
```

## 新机器和新项目应该怎么装

一台新的服务器、工作站、WSL 环境或其他独立 Codex identity，首先安装本工具包，然后配置一次 Host Policy。`CODEX_HOME` 不同时，应视为不同的 Codex identity，分别安装。

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
ai-bridge host install
ai-bridge host validate
```

随后，每个正式 repository 单独初始化 Lite Handoff。普通开发到这里通常已经足够，不需要因为项目文件很多、修改范围大或存在 Controller 就自动安装 Agent-Flow。

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
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

换句话说，推荐默认路径是 **Host Policy + Lite Handoff**。Notifier 和 Agent-Flow 都是按需叠加的能力，不应静默安装。

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

Git 方面，Codex 默认继续当前已经 checkout 的 branch。未经用户针对新 branch 的明确授权，不得因为“修改很大”“PR 更安全”或“main 是干净基线”而自行创建 branch 或 PR，也不得自行 force push、删除远端 branch/tag 或修改 remote。

`$CODEX_HOME/rules/ai-bridge-global.rules` 则用于减少普通 push 的审批等待。目前长期授权的 execpolicy 前缀是：

```text
git push origin ...
git push --set-upstream origin ...
git push -u origin ...
```

这意味着普通 `origin` push 可以跳过人工审批和 auto-review。危险 Git 行为仍由全局行为政策禁止；不要把这组前缀理解成对 force push、远端删除或 remote 修改的授权。项目自己的 `.codex/config.toml` 或 `.codex/rules/` 仍可进一步收紧这些默认策略。

## Lite Handoff：每个项目默认的 GPT ↔ Codex 交接层

Lite Handoff 是本工具包最基础、也最常用的项目层。它适合普通功能开发、修 bug、文档更新、常规重构，以及虽然工作量不小、但不需要独立五角色证据闭环的任务。

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

Lite 并不等于“只能做小修改”。它仍然支持 Controller task、审计、自动 commit/push 等现有 Handoff 能力。它与 Agent-Flow 的主要区别不是代码量，而是证明负担：Lite 不强制独立 Verifier、Requirement Ledger、Stable Review Snapshot 和 Final Critic。

`ai-bridge init` 只管理 repository 内的 Handoff 文件。它可以显示 Host Policy 状态，但不会静默修改 `$CODEX_HOME`；同样也不会自动安装 Notifier 或 Agent-Flow。

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

## Agent-Flow task：不是第五个安装层

Agent-Flow Core 在一个 repository 中只需要安装一次，但同一个项目可能先后执行多个完全不同的高风险任务。每个任务都需要独立的 objective、request nonce、冻结合同、Requirement Ledger、review target、修复历史和最终人工决策，因此需要单独创建 task 实例。

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key 001_registration_refactor
```

这一步不是“再安装一层 Agent-Flow”，而只是创建一次工作流实例。概念上类似：

```text
CardiacNexus
├── Agent-Flow Core                 项目只安装一次
├── task 001_registration_refactor  一次具体高风险任务
├── task 002_segmentation_upgrade   另一次具体高风险任务
└── task 003_deployment_validation  另一次具体高风险任务
```

Lite Handoff 其实也有 task，只不过它通常是一份 `prompts/tasks/<task_key>.md` 交接文件；Agent-Flow task 则是一个拥有独立状态、合同、证据和完整生命周期的运行实例。用户在日常使用中不应该把 `task init` 当成基础设施安装动作。

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

如果只是给一台新机器建立长期 Codex 默认行为，配置 Host Policy；如果只是让一个新 repository 能被 GPT 和 Codex 稳定交接，安装 Lite Handoff。绝大多数项目以这两层作为默认起点。

如果希望任务完成或真正阻塞时收到邮件，再加 Notifier。不要因为“可能以后会用”就在所有 repository 中预装私有通知配置。

如果某个项目确实需要高风险、长链路、独立验证的自动闭环，再安装 Agent-Flow。**修改很多文件、任务很复杂、需要 Controller，并不自动等于必须使用 Agent-Flow**；真正的判断标准是错误通过的代价，以及是否需要独立合同/验证/最终审计。

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

Agent-Flow 使用：

```bash
ai-bridge agent-flow status --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

Notifier 使用：

```bash
ai-bridge notifier status
```

Host Policy 安装是非破坏式的；Lite 和 Agent-Flow 初始化也应保持幂等。不要通过手工复制 `$CODEX_HOME` 文件到项目目录来“统一配置”，也不要把 repository 的 Agent-Flow 模板反向当成服务器全局策略。

## 仓库内容和进一步文档

`chatgpt/` 保存 GPT 侧可复用提示，`codex/` 保存 Codex 启动提示和 repo-local skill，`templates/` 保存 Lite、Host 和 Agent-Flow 的 desired-state 模板，`ai_bridge_kit/` 是 CLI 与核心实现，`tests/` 是回归测试。长期协议细节和 Agent-Flow 的设计决策放在 `docs/`，README 只负责告诉人“这套工具是什么、该装什么、什么时候装”。

Agent-Flow v0.4 的实现规格与 CARE 压力测试经验分别见：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
```

如果以后让 Codex 在新服务器或新 repository 上配置这套工具，根目录 `AGENTS.md` 是机器执行入口；README 是给人阅读和理解整体模型的入口。
