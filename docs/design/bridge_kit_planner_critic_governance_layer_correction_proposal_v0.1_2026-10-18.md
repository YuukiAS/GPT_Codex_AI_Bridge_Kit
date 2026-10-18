# Bridge Kit Planner/Critic 治理层归位修正 — Proposal v0.1

日期：2026-10-18  
目标仓库：`YuukiAS/GPT_Codex_AI_Bridge_Kit`  
目标领域：Bridge Kit 自身维护与治理  
任务键：`bridge-kit--planner-critic-governance-layer-correction`  
来源分支：`main`  
本轮读取基线：`ae15269908dbe5b7666bb347897b8839dfd0fb49`  
审查阶段：`DESIGN_PROPOSAL`  
变更类型：`GOVERNANCE_OWNER_CORRECTION`  
Proposal 版本：`v0.1`  
状态：仅设计，等待独立 Critic；不授权实现、发布、Host Policy 改动或 Control 架构变化。

## 1. 结论

本轮需要修正的是职责归属，不是低摩擦原则本身。

`templates/agent_flow/prompts/CRITIC.md` 中当前的
`LOW_FRICTION_OPERATION_REVIEW` 属于错误 owner。该文件是 Control 安装到消费者仓库后的内部 Critic 模板；它负责冻结当前 Control task 的合同与 Requirement Ledger、处理真实合同歧义，并在终局做独立 closure audit。它不是 ChatGPT Web 上用于设计、维护 Bridge Kit 产品本身的独立 Critic。

因此，不应让消费者 Control Critic 持有 Bridge Kit Host Policy、Git 命令准入、wrapper 取舍和 Bridge 产品摩擦治理职责。该专门章节应从 Control Critic 模板完整删除，而不是因为内容本身合理就继续保留在错误层。

ChatGPT Web 的通用 Planner/Critic 合同继续唯一来自
`YuukiAS/AI_Skills_Collection` 最新 `main` 的：

- `docs/workflows/PLANNER_ROLE_CONTRACT.md`
- `docs/workflows/CRITIC_ROLE_CONTRACT.md`

Bridge Kit 只补充自己的 repo-specific 产品、安全、权限和设计原则，不建立第二套角色合同。

## 2. 已验证的当前事实

### 2.1 中央角色合同

实际读取 AI_Skills_Collection 最新 `main`：

- Planner Role Contract 1.5，blob `f7980a08307f06bd93ed71e0c4b7d4b58fcb19e6`
- Critic Role Contract 1.5，blob `2362aaa510cd506b4d740ea02a2bc8c40edb778a`
- Plugin Capability Gate Policy 1.1，blob `1b9d5509ef0d78c5548ee031b87c8c086d2327ab`

中央 1.5 已经覆盖本轮绝大多数通用治理要求：

- blocker 必须有要求依据、直接证据、因果风险、最小关闭条件和 owner；
- 不能仅因“更保险”继续增加复杂度；
- 必须比较更简单的现实替代；
- 新控制层、watcher、状态机等必须证明既有 canonical owner 不足；
- 正常用户路径必须能被实际追问和验证；
- execution-ready 不能由文档或声明冒充；
- repo 已有规则时应修消费路径，不重复增加同义规则；
- Critic 必须同时检查新增 hardening 是否造成重复审批、状态复杂度或正常入口退化；
- PASS 必须绑定明确对象、版本和阶段，并说明不代表什么。

所以这些通用内容不需要在 Bridge 再复制一套。

### 2.2 Control 内部 Critic 的正式职责

实际读取：

- `templates/agent_flow/ROLE_AUTHORITY_POLICY.md`
- `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`
- `templates/agent_flow/prompts/PLANNER.md`
- `templates/agent_flow/prompts/CRITIC.md`
- `templates/agent_flow/prompts/CONTROLLER.md`
- `templates/agent_flow/prompts/VERIFIER.md`
- `templates/agent_flow/README.md`

Control 的正式设计明确规定 Critic 只在以下模式参与：

`REQUIRED_INITIAL`、`STANDBY`、`REQUIRED_CONTRACT_REVIEW`、
`REQUIRED_FINAL_AUDIT`、`COMPLETE`。

其正式职责是：

- 审核初始合同与 Requirement Ledger 是否完整；
- 做可由 objective/repository truth 直接推出的确定性合同修复；
- 裁定真实合同歧义或矛盾；
- 做最终独立 closure audit。

规格还明确要求 Critic 不得变成通用 implementation reviewer，也不应进入每轮 repair loop。

`templates/agent_flow/README.md` 同时确认整个目录只在消费者仓库显式启用 Control 时安装。因此，把 Bridge 自身 Host Policy / Git / wrapper 的产品维护政策写进该模板，会随着 Control 安装传播到消费者仓库，并让消费者 Control Critic 获得不属于它的 Bridge 产品治理职责。

### 2.3 错误修改的直接历史范围

提交
`fa560cb36f8203866e9d3e237d6879578377be0e`
（`docs: make Bridge Critic preserve low-friction operations`）
只修改了一个文件：

`templates/agent_flow/prompts/CRITIC.md`

唯一实质变化就是新增 `LOW_FRICTION_OPERATION_REVIEW` 章节。

该提交没有同时修改：

- `tests/test_agent_flow.py`
- `CHANGELOG.md`
- `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`
- 其他 Control prompt
- Host Policy 模板
- Persistent Run 模板

所以此次 owner 修正的直接回归面本来就很小，不应扩成 Control 重构或历史清洗。

### 2.4 真实低摩擦行为已经有正确 owner

当前真实行为已经由正确的 Bridge 层拥有：

1. `templates/host/rules/ai-bridge-global.rules`
   - `git fetch origin main`：allow
   - `git fetch --all --prune`：allow
   - `git pull --ff-only origin main`：allow
   - 安全 GitHub / Slurm / process / tmux read：allow
   - raw push、rebase/autostash、branch/worktree topology、force/delete、reset/clean/restore 等：prompt

2. `templates/host/GLOBAL_AGENTS_SNIPPET.md`
   - optional diagnostic 失败不能自动升级成整个 Goal 失败；
   - 不能因为诊断失败扩大到 `setsid`、`sudo`、新 allocation、`scancel` 或更宽操作；
   - 动态安全条件只有确实无法由 native policy 表达时才用 bounded wrapper；
   - bounded normal-entry 失败不能成为 raw operation 的授权。

3. `templates/persistent_run/AGENTS_SNIPPET.md`
   - 同一个 frozen Goal 恢复时，不因长期运行反复请求同一批准；
   - optional diagnostic 失败不能自动终止整个 Goal；
   - 新 artifact/provider/resource/purpose/backend 或 Goal 外副作用仍必须重新审批。

4. `tests/test_host_policy.py`
   已直接验证上述 allow/prompt 行为及其危险邻居，而不是只靠文档文字。

删除错误的 Control Critic 章节不会删除这些真实产品行为，也不会弱化高风险操作的审批边界。

## 3. 唯一需要补充的 Bridge repo-specific 原则

中央 1.5 已覆盖通用的证据、因果、反过度设计和 canonical owner 原则；Bridge 现有 Host/Persistent 规则也已经覆盖具体操作边界。

仍有一个 Bridge 产品层的原则值得在 repo-level owner 中明确，但只需要一小段：

> 维护 Bridge Kit 的安全、Host Policy、审批和正常入口时，审批和额外控制本身也有用户与无人执行成本。Planner/Critic 若提出增加审批频率、wrapper、控制层，或把已有成熟低风险正常入口重新置于审批后，必须给出具体风险证据和因果链，说明现有更窄机制为什么不足，并计入新增交互、中断和自动执行成本；仅“更保守”不是充分理由。具体命令的 allow/prompt 边界继续由现有 Host Policy 模板、相关操作规则和行为测试拥有。

这段不复制具体 Git allowlist，不重新定义中央 Critic blocker 格式，也不建立新的治理文件。它只补中央通用原则无法替代的 Bridge 产品不变量：审批本身是产品成本的一部分。

由于当前 root `AGENTS.md` 已接近默认 instruction byte budget，而且 0.11 当前方案正在要求缩短它，最终实现时这段必须保持极短；若独立 Critic 判断现有 AGENTS + 中央 1.5 已经等价完整覆盖，则可以不新增，不能为了“显式”而重复。

Planner v0.1 的首选仍是加入这一个最小 repo-specific 段落，因为这样以后 Web Planner/Critic 按中央合同读取目标 repo `AGENTS.md` 时，可以直接获得 Bridge 特有的“审批也有产品成本”约束，而无需读取消费者 Control 模板。

## 4. 最终 owner 映射

| 规则类型 | 最终 owner | 本轮动作 |
|---|---|---|
| ChatGPT Web Planner/Critic 通用角色合同 | AI_Skills_Collection Role Contract 1.5 | 不改 |
| Bridge 自身设计中“审批/额外控制也有产品成本” | Bridge 根 `AGENTS.md` | 最多增加一个极短 repo-specific 段落 |
| 具体 Git/Host allow/prompt 边界 | Host Policy rules + Host AGENTS + Host 行为测试 | 不改 |
| optional diagnostic / refusal recovery | Host AGENTS、Persistent Run 现有规则 | 不改 |
| Control task 的合同冻结、Requirement Ledger、最终审计 | Control ROLE_AUTHORITY / v0.4 spec / Control Critic prompt | 删除错误的 Bridge maintenance 专章，恢复职责纯度 |
| 历史变更记录 | Git history / 已有设计历史 | 不重写、不清洗 |
| 0.11 当前执行包中的过期“必须保留该 Control Critic 改动”假设 | 当前 0.11 设计包 | 作为直接依赖交 Critic 裁定最小对齐方式 |

## 5. 拟修改文件

### 5.1 必改

`templates/agent_flow/prompts/CRITIC.md`

完整删除：

`## LOW_FRICTION_OPERATION_REVIEW`

及其专门针对 Bridge Host Policy / Git / wrapper 产品维护的全部正文。

不修改该文件其余 Control Critic 职责。

### 5.2 条件性最小修改

`AGENTS.md`

加入第 3 节所述的一个极短 repo-specific 设计审查原则。不得复制命令 allowlist，不增加新章节体系，不增加角色、状态或 workflow。

如果 Critic 证明现有 AGENTS 已经等价覆盖，则此项取消。

### 5.3 回归测试

`tests/test_agent_flow.py`

推荐增加一个窄的 owner/distribution regression：

- 通过正式 Control template/install surface 获取消费者 Critic；
- 确认消费者 Control Critic 与当前 canonical Control Critic 一致；
- 确认 Bridge-maintenance-only 的 `LOW_FRICTION_OPERATION_REVIEW` 不再随 Control 传播。

这项测试只证明职责边界与分发结果，不冒充 Host Policy 安全语义证明。

`tests/test_host_policy.py`

不改产品语义，只重跑现有行为矩阵，确认：

- 既有低风险 allow 仍 allow；
- arbitrary URL/refspec、rebase/autostash、raw push、force/delete、branch/worktree topology、destructive 操作仍 prompt。

如实现改动没有触及 Host Policy，本轮不新增同义 Host test。

`tests/test_persistent_run.py`

仅在现有 test suite 中回归，不修改 Persistent Run 合同。

### 5.4 当前 0.11 设计包的直接依赖

当前 `main@ae15269908dbe5b7666bb347897b8839dfd0fb49` 的
`docs/design/0.11.0_final_scope_recovery_execution_plan_v0.6_2026-10-18.md`
明确写入了“保留当前 Control Critic 最新变化”的假设，并要求后续 Critic 连同这项变化一起核实。

这与本 Proposal 的 owner 修正直接冲突，因此不能忽略。

Planner 建议：若本 Proposal 经独立 Critic PASS，不回写或篡改已经形成的 v0.6 历史审查对象，而是让当前 0.11 执行包产生一个**最小 superseding alignment**，优先采用连续的 `v0.7`，只删除“必须保留错误 Control Critic 章节”的依赖，并说明 Bridge 低摩擦原则现由中央 Role Contract + Bridge repo-level owner + Host Policy 正确提供。不得借此重开 0.11 架构、Gate、通知、Persistent Run 或 Host 功能设计。

是否确实需要 `v0.7`，由本轮独立 Critic 单独裁定；若有更小且不修改历史对象的合法方式，可采用更小方式。无论采用哪种形式，都不得让未来 Codex 同时收到“删除错误 owner”与“必须保留错误 owner”的矛盾指令。

## 6. 明确不修改的内容

本轮不修改：

- AI_Skills_Collection 的 Planner/Critic Role Contract；
- `PLUGIN_CAPABILITY_GATE_POLICY.md`；
- `templates/agent_flow/ROLE_AUTHORITY_POLICY.md` 的角色模型；
- `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md` 的 Control 架构；
- `templates/agent_flow/prompts/PLANNER.md`；
- `CONTROLLER.md`；
- `VERIFIER.md`；
- Control schema、state、Requirement Ledger schema；
- Host Policy allow/prompt 产品行为；
- Persistent Run 正常实现；
- Review 正常实现；
- Notifier；
- README 用户路径；
- 新角色、新状态、新 schema、新 workflow、新 watcher、新数据库、新 wrapper、新 Control mode。

也不通过修改 CHANGELOG 来“抹掉”提交 `fa560...`。Git history 保持真实。

## 7. 版本与发布判断

当前 `pyproject.toml` 已是 `0.11.0`。

当前 `CHANGELOG.md` 明确把 0.11.0 标为 source candidate，formal release pending；因此本轮属于当前 0.11 开发期内的普通职责归位修正，不需要：

- bump 到 `0.11.1`；
- 新 package version；
- 新 stable tag；
- 单独 release。

若本修正在 0.11 的某个 frozen rc SHA 之后才落地，则按当前 0.11 候选规则生成新的 rc/SHA 即可；这仍不是另一个 package version。

网页端 Planner/Critic 是否读取正确治理规则与 package release 无关。只要 repo `main` 上本修正完成，后续 Bridge 维护轮次就按：

`AI_Skills_Collection 最新 Role Contract -> Bridge 最新 AGENTS / 相关 policy -> Bridge 设计与独立审查 -> 经批准后 Codex 实现`

立即消费正确规则。

## 8. 验收与真实回归

本轮实现完成后必须同时满足：

1. Web Planner/Critic 只使用中央 1.5 作为通用角色合同，并读取 Bridge repo-specific AGENTS/policy。
2. Bridge 不新增第二套 Planner/Critic Role Contract。
3. 消费者安装后的 Control Critic 不再包含 Bridge Host Policy / Git / wrapper 产品维护专章。
4. `tests/test_host_policy.py` 仍证明既有低风险正常入口保持低摩擦。
5. 同一行为矩阵仍证明高风险 Git/外部副作用没有被放宽。
6. optional diagnostic / refusal recovery 的现有 Host/Persistent 规则仍存在且行为未退化。
7. 新增 repo-level 规则若存在，只表达 Bridge 特有的审批成本原则，不复制中央 blocker 规范或具体命令 allowlist。
8. 当前 0.11 活跃执行包不再要求未来实现保留这个错误 owner。
9. 没有新增角色、状态、控制层、wrapper、数据库或用户步骤。
10. README 用户使用方式不变；当前 correction 不依赖 formal 0.11 release 才生效。

## 9. 替代方案与拒绝理由

### 保留 Control Critic 专章

拒绝。内容可能合理，但 owner 错误，而且会传播到消费者仓库。

### 把整段原样搬到根 AGENTS

拒绝。会重复 Host Policy 的具体命令边界、重复中央 Critic 通用规则，同时加重 root AGENTS instruction budget。

### 新建 Bridge 专属 Planner/Critic Role Contract

拒绝。中央 AI Skills 1.5 已经是唯一 Web 角色合同；新建会造成双合同漂移和职责冲突。

### 完全不加 repo-level 原则，只删除 Control 段落

这是现实可行的更小替代。若 Critic 判断中央 1.5 + 当前 AGENTS/Host policy 已足够表达“审批成本也是产品成本”，应选择此更小方案；Planner 不以“必须写得更显式”为理由阻挡。

### 修改 Host Policy 行为来证明 owner correction

拒绝。真实产品行为当前已经在正确 owner 中，当前任务不是重新裁定每条 Git/Host 规则。

## 10. 回滚边界

本轮是纯可逆治理修正，无 schema/state/data migration。

若新增的 root AGENTS 短原则被证明冗余，可以单独删除；不应把回滚定义为重新把 Bridge maintenance 政策塞回消费者 Control Critic。

若 Control template 删除造成意外消费者回归，只回滚与 Control Critic 职责直接相关的模板/test 变更；Host Policy、Persistent Run、Review 和其他 0.11 产品功能不得被一起回滚。

## 11. Critic 需要重点裁定的两点

1. 中央 1.5 + 当前 Bridge AGENTS/Host 规则是否已经完整覆盖“审批本身也有产品成本”。如果已经完整覆盖，取消本 Proposal 对根 AGENTS 的新增；如果未覆盖，只接受第 3 节的最小 repo-specific 规则。
2. 当前 0.11 v0.6 execution package 已经写入“保留错误 Control Critic 变化”的直接冲突。请裁定是否应以最小 `v0.7` superseding package 对齐，或存在更小且不篡改历史对象的合法处理方式。

除此之外，不扩大审查到 0.11 的其他功能架构。

## 12. 本 Proposal 的完成边界

本 Proposal PASS 只批准 owner correction 的设计方向，不批准实现，不批准 formal release，不改变 Host Policy 权限边界，也不证明 0.11 整体 execution-ready。

下一步如果 Critic PASS，应由 Planner 根据通过版本生成窄范围 execution package，再由 Critic 按角色合同审完整执行包后，才可能进入 Codex 实现。
