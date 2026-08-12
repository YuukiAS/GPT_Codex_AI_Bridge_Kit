# Codex Instructions for GPT-Codex AI Bridge Kit

本文件是 Codex 在维护本仓库、以及使用本仓库去配置其他机器或 repository 时的操作入口。面向人的总体说明以 `README.md` 为准；实现细节、状态机和 Agent-Flow 约束以 `docs/` 中对应规格为准。

## 1. 先判断作用域，不要把所有能力混成一次安装

Bridge Kit 的能力按作用域分成机器层、项目层和任务层。真正的安装对象只有机器层和项目层；Agent-Flow task 是运行实例，不是第五个安装层。

```text
机器层
└── Host Policy                    once per CODEX_HOME

项目层
├── Lite Handoff                   default per repository
├── Generic Notifier               optional
└── Agent-Flow Core                optional for high-risk repositories

任务层
├── Lite task
└── Agent-Flow task                runtime instance, not installation
```

配置前必须先确认用户要处理的是“新机器/新 Codex identity”“新 repository”“通知能力”还是“某个具体高风险任务”。不要因为用户说“把 Bridge Kit 配上”就静默安装全部可选层。

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

全局 Host AGENTS 必须继续维持这些长期行为：用户可见 narrative 默认使用自然简体中文；会实质改变架构、范围、部署、branch 策略、外部行为或科学/产品语义的歧义应询问用户；普通局部实现细节自行完成；未经明确授权不得创建 branch/PR、force push、删除远端 branch/tag 或修改 remote。

全局 execpolicy 目前只维护以下普通 push 前缀：

```text
git push origin ...
git push --set-upstream origin ...
git push -u origin ...
```

这些规则用于跳过普通 `origin` push 的 manual/auto review。它们不是对危险 Git 行为的授权；危险操作仍受 Host AGENTS 行为规则禁止。

## 3. 新 repository：默认先装 Lite Handoff

绝大多数正式 repository 应先使用 Lite Handoff，而不是 Agent-Flow。

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

不要让 `ai-bridge init` 静默修改 `$CODEX_HOME`，不要静默安装 Notifier，也不要静默安装 Agent-Flow。Host Policy 和 repo Handoff 是两个生命周期。

Lite task 的默认入口仍是：

```text
prompts/tasks/<task_key>.md
```

其结果默认写入：

```text
results/<task_key>/
```

Lite 适用于普通功能开发、bug 修复、常规重构和文档工作，也可以使用现有 Controller task。不要仅因为改动文件多或任务耗时长就自动升级到 Agent-Flow。

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

## 5. Agent-Flow Core：仅对高风险 repository 显式安装

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
替换或破坏 Lite Handoff
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

Agent-Flow v0.4 的当前实现与正确性要求以以下文件为准：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
```

## 6. Agent-Flow task：这是运行实例，不是安装层

在 repository 已安装 Agent-Flow 后，只有出现一项具体高风险任务时才初始化 task：

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key <task_key>
```

这一步创建的是该任务自己的 `REQUEST.json`、`CURRENT.json` 和后续 contract/evidence 生命周期。它不能被描述为“第五层安装”。同一个 Agent-Flow Core 可以承载多个互相独立的 task，每个 task 必须拥有独立 objective、request nonce、frozen contract、Requirement Ledger、review target、repair history 和 human gate。

如果没有一个具体的高风险 objective，不要为了“预先配置好”而创建空 Agent-Flow task。

## 7. 安装决策默认值

当用户只说“在新服务器把 Bridge Kit 配好”，默认完成 package + Host Policy，并验证 Host Policy。不要顺便初始化任意 repository。

当用户只说“把这个 repository 接入 Handoff”，默认安装 Lite Handoff，并检查 Host Policy 状态；不要因为 repository 很复杂就自动加 Agent-Flow。

当用户明确说“这个项目需要终态通知”，在 Lite 基础上配置 Notifier。

当用户明确要求 Agent-Flow，或任务明显属于高风险且用户已经选择 Agent-Flow 工作方式时，再安装 Agent-Flow Core。若是否升级到 Agent-Flow 会实质改变工作流，应向用户确认，而不是自行决定。

当用户说“用 Agent-Flow 做这次 XXX”，如果 repository 尚未安装 Agent-Flow，则先安装/验证 Agent-Flow Core，再为 XXX 创建 task；如果已经安装，则只创建或复用对应 task，不要重复安装整个 Core。

## 8. Git 与 branch 规则

在本仓库及通过本 Kit 管理的 repository 中，默认继续当前 branch。未经用户明确授权，不得执行任何会创建新 branch 的命令，包括 `git switch -c`、`git checkout -b`、`git branch <new>`、通过 worktree 创建 branch，或把新 remote branch 当作“不推当前 branch”的替代方案。

Agent-Flow 为 Verifier/Executor 做角色隔离时，优先使用 detached worktree；如果确实需要长期 role branch，先向用户请求该 branch 的明确授权。

普通已授权 `origin` push 可按 Host Policy 执行。不得自动 force push、`--force-with-lease`、删除远端 branch/tag、添加/删除/重定向 remote。

## 9. 修改本仓库时的文档规则

根 `README.md` 是写给人的。默认必须使用中文自然段落解释整体模型、安装边界和用户路径；不要把 README 写成大量英文协议条款、控制台日志或机器 schema dump。代码、命令、路径、配置键、状态名、API 名称等技术字面量保持英文即可。

根 `AGENTS.md` 是写给 Codex 的操作入口，应保持可执行、明确、低歧义。复杂 Agent-Flow 状态机、schema 和历史设计放在 `docs/`，不要把全部实现规格重复复制到 README。

如果 README 与实现发生冲突，应修 README；如果 Agent-Flow 的实现行为与 `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md` 冲突，应优先按规格修实现，除非用户明确改变了架构决策。

## 10. 兼容性和发布

任何新能力都必须保持以下旧入口可用：

```text
ai-bridge
ai-bridge init
ai-bridge validate
ai-bridge prompt
ai-bridge where
ai-bridge host ...
ai-bridge notifier ...
```

Lite Handoff 不能因为 Agent-Flow 演进而变复杂。Host Policy、Notifier、Agent-Flow 彼此独立，新增一层不得静默改变其他层。

发布前必须运行现有回归测试和对应新功能测试。没有真实 GitHub Actions green evidence 时，不要把“本地测试通过”描述成“远端 CI 已通过”。稳定 tag 不得移动或覆盖；没有用户授权时不要创建新的 release tag。