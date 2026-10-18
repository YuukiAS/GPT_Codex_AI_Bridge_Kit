# Bridge Kit Planner/Critic 治理职责归位修正 — Execution Plan v0.1

日期：2026-10-18  
任务键：bridge-kit--planner-critic-governance-layer-correction  
目标仓库：YuukiAS/GPT_Codex_AI_Bridge_Kit  
目标领域：Bridge Kit governance / maintenance  
来源分支 / 未来执行分支：main  
执行包父提交：6dc54a6d8f25e50e48d81853b347844d960fd613  
批准 Proposal：docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md @ d4b694673501d4933eca5cd68394c740c0cb823d  
批准 Critic Review：docs/design/bridge_kit_planner_critic_governance_layer_correction_critic_review_v0.1_2026-10-18.md @ 6dc54a6d8f25e50e48d81853b347844d960fd613  
Proposal 版本：v0.1  
Execution Plan 版本：v0.1  
审查阶段：EXECUTION_PACKAGE_PREPARATION_AFTER_DESIGN_PASS  
状态：仅供 execution-ready Critic 审查；本文件本身不授权实现、发布或任何外部副作用。

## 1. 执行目标

本任务只修正一个已确认的治理 owner 错置：

templates/agent_flow/prompts/CRITIC.md 中的 LOW_FRICTION_OPERATION_REVIEW 是 Bridge Kit 产品维护政策，却位于会分发到消费者仓库的 Control 内部 Critic 模板中。

实现完成后应达到：

1. canonical Control Critic 不再携带 Bridge Host Policy / Git / wrapper maintenance 专属章节；
2. Control Critic 原有 initial / contract / final audit 职责完整保留；
3. disposable consumer 通过正式 Control 安装得到与 canonical template 完全一致的 Critic；
4. Bridge 的真实低摩擦行为仍由 Host Policy、Host AGENTS、Persistent Run 与既有行为测试拥有；
5. 根 AGENTS 不增加本任务治理文字；
6. 不新增 Bridge 专属 Planner/Critic Role Contract；
7. package version 继续为 0.11.0，formal release 不移动；
8. owner correction 形成真实 implementation commit 后，当前 0.11 v0.6 不再允许直接执行，必须回 Planner 基于该真实提交生成最小 v0.7 对齐包。

这不是 Control 重构，也不是 Host Policy 返修。

## 2. 已冻结的来源与设计裁定

本执行包基于 AI_Skills_Collection 最新 main 的：

- docs/workflows/PLANNER_ROLE_CONTRACT.md，版本 1.5，blob f7980a08307f06bd93ed71e0c4b7d4b58fcb19e6；
- docs/workflows/CRITIC_ROLE_CONTRACT.md，版本 1.5，blob 2362aaa510cd506b4d740ea02a2bc8c40edb778a；
- docs/workflows/PLUGIN_CAPABILITY_GATE_POLICY.md，版本 1.1，blob 1b9d5509ef0d78c5548ee031b87c8c086d2327ab。

Bridge source of truth 使用当前 main@6dc54a6d8f25e50e48d81853b347844d960fd613，而不是 Proposal 编写时的旧基线。该 main 已包含：

- Proposal；
- 0.11 v0.6 后续 quiescence / reader isolation 设计硬化提交 16ae5fefe8747e54a6db60bd155311daff1efed7；
- 独立 Critic PASS review。

本轮没有新的技术未知项需要重新做外部研究；设计阶段 Critic 已完成针对性官方 Git 核查。本轮只把已批准设计冻结为可执行合同，不重新设计。

Critic 已冻结以下决定：

- 完整删除 LOW_FRICTION_OPERATION_REVIEW 专章；
- 不向根 AGENTS 增加 Proposal 第 3 节的治理段落；
- 不新增第二套 Role Contract；
- 不修改 Host Policy / Persistent Run 产品行为；
- 不修改 Control role authority / schema / state graph；
- owner correction 后必须由后续 Planner 从真实 post-correction main 生成最小 0.11 v0.7；不能预写未来未知 implementation SHA。

## 3. 精确实施范围

### 3.1 必改：Control Critic template

文件：

templates/agent_flow/prompts/CRITIC.md

只删除从标题 LOW_FRICTION_OPERATION_REVIEW 开始、到 STANDBY 前结束的完整专章，包括其中 Bridge Host Policy、Git allow/prompt、wrapper minimization、optional diagnostic 和 approval-frequency maintenance 文字。

删除后必须保持下列既有章节及语义不变：

- REQUIRED_INITIAL；
- deterministic contract repair；
- FROZEN_CONTRACT.md；
- REQUIREMENT_LEDGER.json；
- CRITIC_FREEZE.json；
- STANDBY；
- REQUIRED_CONTRACT_REVIEW；
- REQUIRED_FINAL_AUDIT；
- positive-completion / weaker-substitute / evidence-scope audit；
- Visual Review binding 检查；
- waiting_external_review；
- stale request_nonce / review_target_id 防误推进。

原则上该文件除删除目标专章外不得有其他语义改动。若格式上需要消除删除后多余空行，只允许纯机械整理。

### 3.2 必改：Control distribution / owner regression

文件：

tests/test_agent_flow.py

新增一个窄回归，通过正式 Control install surface 建立 disposable consumer。优先复用现有 CLI / 测试入口，不创建第二套安装 helper。

回归必须直接证明：

1. 正式 agent-flow install 成功；
2. consumer 的 automation/agent_flow/prompts/CRITIC.md 与当前 canonical templates/agent_flow/prompts/CRITIC.md 完全一致；
3. installed consumer Critic 不含 LOW_FRICTION_OPERATION_REVIEW；
4. installed Critic 仍包含 REQUIRED_INITIAL、STANDBY、REQUIRED_CONTRACT_REVIEW、REQUIRED_FINAL_AUDIT；
5. 既有 test_control_roles_and_legacy_identifiers_stay_unchanged 等角色 / schema 回归继续通过。

这项新增测试只证明 owner 与 distribution 边界。不能据此声称 Host Policy 安全已经由该测试证明。

### 3.3 条件性机械同步：CHANGELOG

当前 main package version 为 0.11.0，CHANGELOG 将 0.11.0 标记为 source candidate / formal release pending。

若按当前仓库 0.11 source-candidate 记账惯例需要记录 production-template 的最终变化，则只在现有 0.11.0 candidate 条目中增加一条简短说明：

- Control Critic 恢复到 Control task 自身的 initial / contract / final audit 职责；
- Bridge maintenance-specific low-friction policy 不再随 Control template 分发；
- Host/Persistent 行为边界未改变。

不得：

- 改写历史 fa560 提交；
- 删除历史记录；
- 把这次 correction 写成新 release；
- 增加 0.11.1；
- 写成 Host Policy 功能变化。

README 必须检查，但由于用户安装与正常使用入口没有变化，预期为 README checked: no update required。没有直接证据要求修改时不得改 README。

## 4. 明确禁止修改的范围

除非删除目标专章暴露出纯机械一致性错误，否则本任务不得修改：

- AGENTS.md；
- templates/agent_flow/prompts/PLANNER.md；
- templates/agent_flow/prompts/CONTROLLER.md；
- templates/agent_flow/prompts/VERIFIER.md；
- templates/agent_flow/prompts/EXECUTOR.md；
- templates/agent_flow/ROLE_AUTHORITY_POLICY.md；
- templates/agent_flow/schema.json；
- docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md；
- templates/host/rules/ai-bridge-global.rules；
- templates/host/GLOBAL_AGENTS_SNIPPET.md；
- templates/persistent_run/AGENTS_SNIPPET.md；
- Review；
- Persistent Run 实现；
- Notifier；
- runtime routing；
- paid-review protocol；
- consumer repository；
- CODEX_HOME；
- release ref / stable tag；
- 当前 0.11 v0.6 Plan / Goal / Kickoff；
- 未来 v0.7 文件。

若实施发现必须改变上述任一产品语义，停止，不自行扩大范围；回 Planner / Critic。

## 5. 必须保持的产品不变量

Host/Persistent owner 的现有语义全部是 should-not-change：

- git fetch origin main 继续低摩擦；
- git fetch --all --prune 继续低摩擦；
- git pull --ff-only origin main 继续低摩擦；
- 现有安全 GitHub / Slurm / process / tmux 读取保持当前边界；
- arbitrary URL/refspec 继续受限；
- rebase/autostash 继续受限；
- raw push 继续受限；
- force/delete 继续受限；
- branch/worktree topology mutation 继续受限；
- reset/clean/restore 继续受限；
- optional diagnostic failure 不自动终止整个 Goal；
- bounded normal-entry failure 不授权 raw fallback；
- 同一个 frozen Persistent Goal 的恢复不因长期运行本身重复请求同一批准。

本任务不复制这些规则到 Control Critic。

## 6. 实施前漂移检查

Codex 开始前必须读取：

- 本 Execution Plan；
- 同版本 Canonical Goal；
- 同版本 Kickoff；
- 批准 Proposal；
- 批准 Critic review；
- 当前 main AGENTS；
- 当前 canonical Control Critic；
- tests/test_agent_flow.py；
- tests/test_host_policy.py；
- templates/persistent_run/AGENTS_SNIPPET.md；
- pyproject.toml；
- CHANGELOG.md。

还必须确认：

- 当前仓库是 YuukiAS/GPT_Codex_AI_Bridge_Kit；
- 当前分支是 main；
- approved package commit 是当前 HEAD 的祖先；
- 从 package commit 到执行时 HEAD 若存在新增提交，只允许独立 Critic review / handoff / 无关设计文档等不改变本实施对象的提交。

如果 package 之后 templates/agent_flow/prompts/CRITIC.md、tests/test_agent_flow.py、Host Policy、Persistent Run、root AGENTS、Control schema/authority 或版本语义发生新的实质变化，停止并返回 Planner/Critic；不得根据旧包盲目实施。

不得为了获得干净环境自行新建或切换 branch、创建替代 worktree、reset、stash、clean 或 restore 用户工作。

## 7. 实施步骤

### Stage A — 精确删除

1. 读取 current canonical CRITIC.md。
2. 确认目标专章仍与被批准设计一致。
3. 只删除 LOW_FRICTION_OPERATION_REVIEW 专章。
4. 用 diff 核对该文件其余部分逐字/语义保持。

如果目标章节已被别人删除或被实质改写，先判断是否已经等价完成；不要重复添加/删除其他内容。若无法机械判断，停止。

### Stage B — 增加 owner / distribution regression

1. 在 tests/test_agent_flow.py 中增加一个窄测试。
2. 使用正式 agent-flow install surface 安装 disposable consumer。
3. exact-compare installed consumer Critic 与 canonical template。
4. 断言错误 maintenance 专章不再传播。
5. 断言 Control Critic 四个主要生命周期章节仍存在。
6. 保持已有 roles/schema/legacy identifiers regression。

不要给 Host 安全新增同义关键词测试。

### Stage C — 最小文档机械同步

1. 检查当前 0.11 CHANGELOG 记账规则。
2. 若 production-template 变化按现有 candidate 约定应记录，则只增加一条 0.11 candidate bullet。
3. 检查 README；没有用户入口变化则不修改，并在执行结果中写 README checked: no update required。

### Stage D — 定向回归

至少运行：

- tests/test_agent_flow.py；
- tests/test_host_policy.py；
- tests/test_persistent_run.py。

若仓库当前标准测试入口会自然包含这些测试，可使用标准入口；不得为了本任务修改 CI workflow。

定向结果必须区分：

- 新 owner/distribution regression；
- 既有 Control authority/schema regression；
- Host allow/prompt 行为回归；
- Persistent Run should-not-change 回归。

### Stage E — diff / scope 审计

在 commit 前检查完整 diff。

允许的 production/test 文件最多为：

- templates/agent_flow/prompts/CRITIC.md；
- tests/test_agent_flow.py；
- CHANGELOG.md（仅满足第 3.3 条件时）。

本执行包三份设计文档已在 implementation 前存在，不算 implementation diff。

如果出现 AGENTS.md、Host Policy、Persistent Run、Control schema/role authority、其他 prompt、0.11 v0.6 文件或未来 v0.7 文件变化，视为 scope violation，停止。

### Stage F — 提交与发布

在当前已选 main 上创建普通 task-owned implementation commit。

如当前 Machine Policy / repo 规则仍允许现有 bounded current-branch publication，可使用现有安全 publisher 将当前 main 非强制发布到同名 origin/main，并回读远端 SHA。不得 raw push、force、rebase、autostash、branch creation、upstream mutation 或 release ref movement。

发布后只可称 owner-correction implementation candidate 已落地；不能称 0.11.0 整体完成或正式发布。

## 8. 验收矩阵

| 验收能力 | 真实入口 / 证据 | PASS | FAIL |
| --- | --- | --- | --- |
| canonical Control Critic 职责归位 | current template diff | 只移除错误专章，其余职责保留 | 同时删改其他 Control authority |
| consumer distribution 正确 | disposable agent-flow install | installed Critic 与 canonical 完全一致且无错误专章 | 安装结果漂移或仍传播专章 |
| Control authority 不退化 | 既有 agent-flow tests | roles/schema/initial/contract/final 回归全过 | 角色、state、schema 或 lifecycle 改变 |
| Host 低摩擦不退化 | 现有 host behavior tests | 既有 allow 仍 allow | 任一既有低风险路径被本任务改变 |
| 危险 Git 不放宽 | 现有 host behavior tests | 既有 prompt 仍 prompt | arbitrary/refspec/rebase/raw push/force 等被放宽 |
| Persistent 不退化 | 现有 persistent tests + source diff | 原合同不变，相关回归通过 | 同 Goal 恢复语义或合同发生变化 |
| root AGENTS 不扩张 | implementation diff | AGENTS.md 未修改 | 新治理文字进入 root AGENTS |
| 无第二套 Role Contract | repository diff / tree | 无新 Role Contract | 新增 Bridge-specific 通用角色合同 |
| 版本边界 | pyproject / release | 0.11.0 不变，release 不动 | bump/tag/release movement |
| 0.11 后续顺序正确 | implementation report + handoff | v0.6 明确停止直接执行，回 Planner 生成 post-correction v0.7 | Codex直接执行v0.6或预写未来未知SHA的v0.7 |

这些证据证明本 correction 的职责边界与回归，不证明 0.11.0 其他产品能力已经通过 Gate。

## 9. 0.11 v0.6 的冻结处理

当前历史对象：

docs/design/0.11.0_final_scope_recovery_execution_plan_v0.6_2026-10-18.md  
docs/design/0.11.0_final_scope_recovery_goal_v0.6_2026-10-18.md  
docs/design/0.11.0_final_scope_recovery_kickoff_v0.6_2026-10-18.md

本任务不得修改、覆盖或执行它们。

owner correction 实现提交产生后：

1. 明确记录 V06_DIRECT_EXECUTION_ALLOWED=NO；
2. 记录真实 OWNER_CORRECTION_IMPLEMENTATION_COMMIT；
3. 停止；
4. 下一入口必须是 Planner；
5. Planner 从当时最新 main 生成最小 0.11 v0.7 Plan / Goal / Kickoff；
6. v0.7 只更新真实 baseline、移除“必须保留 fa560 Control Critic maintenance policy”的依赖，并说明低摩擦语义由中央 Role Contract + Bridge Host/Persistent 正确 owner 提供；
7. v0.7 不得重开 G02/G06/G07/G10/G12/G14、worktree、Persistent Run、Notifier、Clear Writing 或 Host architecture。

Codex 不得在本 task 内自行生成 v0.7。

## 10. 版本与发布

产品 package version 继续为 0.11.0。

本 correction：

- 不 bump 0.11.1；
- 不创建 stable tag；
- 不移动 refs/heads/release；
- 不单独 formal release；
- 不生成新的 release candidate，除非后续 0.11 正式候选流程本来就因新 production SHA 需要新的 rc.N。

当前 release package content 仍是 0.10.0；本任务不得改变该事实。

## 11. 风险、停止条件与恢复

主要风险只有四类：

1. 删除范围过宽，误伤 Control Critic 原职责；
2. 测试只扫关键词，没有证明正式安装分发；
3. 顺手修改 Host/Persistent/AGENTS，扩大 blast radius；
4. 实现后直接继续旧 v0.6，造成已知矛盾指令重新进入执行。

对应防线：

- exact diff + installed-vs-canonical byte equality；
- 正式 agent-flow install disposable consumer；
- restricted changed-path audit + 既有 Host/Persistent regression；
- implementation 完成后强制回 Planner，不执行 v0.6。

任何需要改变已批准产品语义的问题都不是本 task 的实现细节，必须停止回 Planner/Critic。

回滚边界只允许回滚本 correction 的 template/test/changelog change；不得将 Host/Persistent/Review/0.11 其他功能一起回滚，也不得把错误 maintenance 专章重新定义成长期正确 owner。

## 12. 权限边界

经 execution-ready Critic PASS 后，用户发送同版本 approved Kickoff 才授权：

- 当前 Bridge main 中删除错误 Control Critic 专章；
- 增加窄 Control distribution/owner regression；
- 运行本 Plan 指定的本地/deterministic 回归；
- 必要的 0.11 candidate CHANGELOG 机械同步；
- 当前 main 上普通 task-owned commit；
- 若现有 Bridge / Machine Policy 已允许，使用现有 bounded current-branch publisher 做非强制同名 main publication并回读 SHA。

不授权：

- Host Policy 修改；
- root AGENTS 修改；
- Control 架构 / role / schema / state 改动；
- consumer repo 修改；
- CODEX_HOME 修改；
- 真实外部服务或 paid API；
- destructive Git；
- branch/worktree topology mutation；
- 0.11 v0.6 产品实现；
- v0.7 编写或产品实现；
- tag / release movement。

## 13. 执行完成时的最小报告

Codex 必须报告：

- base / final implementation commit；
- 实际 changed paths；
- CRITIC.md 删除范围；
- disposable consumer install equality 结果；
- agent-flow / Host / Persistent 回归结果；
- Control role/schema unchanged 证据；
- AGENTS / Host / Persistent / v0.6 unchanged 证据；
- README checked 状态；
- CHANGELOG 是否修改及原因；
- remote main 是否已发布并回读；
- V06_DIRECT_EXECUTION_ALLOWED=NO；
- OWNER_CORRECTION_IMPLEMENTATION_COMMIT=<真实SHA>；
- NEXT_HANDOFF=PLANNER。

不得提前生成 v0.7，不得声明 0.11.0 已正式完成。
