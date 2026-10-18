# Bridge Kit Planner/Critic 治理职责归位修正 — Canonical Goal v0.1

日期：2026-10-18  
任务键：bridge-kit--planner-critic-governance-layer-correction  
目标仓库：YuukiAS/GPT_Codex_AI_Bridge_Kit  
执行分支：main  
执行包父提交：6dc54a6d8f25e50e48d81853b347844d960fd613  
批准 Proposal：docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md @ d4b694673501d4933eca5cd68394c740c0cb823d  
批准 Critic Review：docs/design/bridge_kit_planner_critic_governance_layer_correction_critic_review_v0.1_2026-10-18.md @ 6dc54a6d8f25e50e48d81853b347844d960fd613  
Goal 版本：v0.1  
状态：等待 execution-ready Critic 审查。

## 1. 正面完成目标

在不重新设计 Bridge Kit 的前提下，把错误放在消费者 Control Critic 中的 Bridge maintenance-specific 低摩擦治理专章删除，使职责重新落到已存在的正确 owner，同时证明 Control 的正式职责、Host/Persistent 产品行为和版本/发布边界均未发生非预期变化。

真正完成必须同时观察到：

1. templates/agent_flow/prompts/CRITIC.md 不再含 LOW_FRICTION_OPERATION_REVIEW 专章；
2. REQUIRED_INITIAL、STANDBY、REQUIRED_CONTRACT_REVIEW、REQUIRED_FINAL_AUDIT 及其既有合同冻结、Requirement Ledger、positive-completion、weaker-substitute、evidence scope、waiting_external_review 语义仍存在；
3. 正式 agent-flow install 到 disposable consumer 后，installed Control Critic 与 canonical template 完全一致；
4. installed Control Critic 不再传播 Bridge Host Policy / Git / wrapper maintenance 专属政策；
5. Control roles/state/schema 不变；
6. 现有 Host Policy allow/prompt 行为回归通过；
7. Persistent Run 既有同 Goal 恢复/审批语义未改；
8. root AGENTS 未因本任务增加治理文字；
9. 仓库未新增 Bridge-specific Planner/Critic Role Contract；
10. package version 仍为 0.11.0，formal release 未移动；
11. 当前 0.11 v0.6 不被继续直接执行；实现完成后回 Planner，使用真实 implementation commit 生成最小 v0.7。

## 2. 不可替代语义

本 Goal 不能用以下替代品冒充完成：

- 只在文档中说 owner 已修正，但 canonical Control template 仍含错误专章；
- 只检查关键词，没有通过正式 agent-flow install 验证 consumer distribution；
- 删除错误专章的同时删掉 Control Critic 正常 initial / contract / final authority；
- 通过修改 Host Policy 来“补偿” owner correction；
- 把原章节搬到 root AGENTS 或另建 Bridge Role Contract；
- 修改 v0.6 历史对象来掩盖冲突；
- 预先写一个绑定未知未来 implementation SHA 的 v0.7；
- 用 tests green 声称 0.11.0 整体已通过或正式发布。

## 3. 精确允许修改

实施期允许的 production/test 文件只有：

- templates/agent_flow/prompts/CRITIC.md；
- tests/test_agent_flow.py；
- CHANGELOG.md，仅在当前 0.11 source-candidate 记账规则要求 production-template 变化时做一条机械同步。

本执行包文档本身在 implementation 前已经存在。

README 只检查，不因本任务自动修改。

## 4. 明确禁止修改

不得修改：

- AGENTS.md；
- Control Planner / Controller / Verifier / Executor prompt；
- ROLE_AUTHORITY_POLICY.md；
- Control schema / state graph；
- docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md；
- Host Policy rules / Host AGENTS；
- Persistent Run template / implementation；
- Review；
- Notifier；
- runtime routing；
- paid-review protocol；
- consumer repos；
- CODEX_HOME；
- 0.11 v0.6 Plan / Goal / Kickoff；
- v0.7 files；
- package version；
- release ref / stable tag。

发现必须改变上述语义时，STOP 并回 Planner/Critic。

## 5. 必须保持的低摩擦与安全边界

本 Goal 不重新定义具体 Host 行为；以下只作为 regression invariants：

- git fetch origin main、git fetch --all --prune、git pull --ff-only origin main 的当前低摩擦语义保持；
- arbitrary URL/refspec、rebase/autostash、raw push、force/delete、branch/worktree topology、reset/clean/restore 的当前限制保持；
- optional diagnostic failure 不自动终止整个 Goal；
- bounded normal-entry failure 不授权 raw fallback；
- 同一个 frozen Persistent Goal 恢复不因长期运行本身重复索权。

这些语义继续由现有 Host/Persistent owner 提供，不能复制回 Control Critic。

## 6. 最小验证合同

必须运行并通过：

- tests/test_agent_flow.py；
- tests/test_host_policy.py；
- tests/test_persistent_run.py。

新增 owner/distribution regression 必须：

- 走正式 agent-flow install；
- 创建 disposable consumer；
- exact-compare installed 与 canonical Critic；
- 证明错误专章不再传播；
- 证明核心 Control Critic lifecycle 标记仍在。

同时以 implementation diff 证明 AGENTS、Host/Persistent、Control schema/role authority、v0.6 没有被本任务改动。

## 7. 0.11 后续顺序

owner correction implementation commit 产生前，不生成 v0.7。

implementation 完成后，本 Goal 的最后动作是：

V06_DIRECT_EXECUTION_ALLOWED=NO  
OWNER_CORRECTION_IMPLEMENTATION_COMMIT=<真实 commit>  
NEXT_HANDOFF=PLANNER

下一 Planner 必须从当时最新 main 生成最小 0.11 v0.7，只对齐真实 baseline 与错误 owner 依赖；不得重开 v0.6 其余冻结设计。

## 8. 完成与非完成声明

满足本 Goal 只能声明：

Bridge Kit governance owner correction implementation completed within the approved narrow scope.

这不代表：

- Bridge Kit 0.11.0 整体 implementation complete；
- 0.11.0 execution-ready；
- 0.11.0 final Gate PASS；
- formal release complete；
- Host Policy 获得新授权；
- Control 架构发生扩展；
- v0.7 已生成或已批准。
