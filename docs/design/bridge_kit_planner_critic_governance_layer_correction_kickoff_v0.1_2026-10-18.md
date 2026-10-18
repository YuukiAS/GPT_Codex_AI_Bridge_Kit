# Bridge Kit Planner/Critic 治理职责归位修正 — Kickoff Draft v0.1

本文件只供 execution-ready Critic 审查。Critic 只有在同时审查同版本 Execution Plan、Canonical Goal 和本 Kickoff 后，才能决定 READY_FOR_CODEX。

如果独立 Critic 对本执行包给出 PASS 且 READY_FOR_CODEX=YES，只允许把下方唯一 package SHA 占位符机械替换为它实际审过的完整 40 位 package commit；其余正文不得临场扩写。

=== CODEX KICKOFF BODY BEGIN ===

继续 Bridge Kit 自身 Planner/Critic 治理职责归位修正，不重新设计 Bridge Kit。

目标仓库：YuukiAS/GPT_Codex_AI_Bridge_Kit  
执行分支：main  
任务键：bridge-kit--planner-critic-governance-layer-correction  
批准执行包提交：__BRIDGE_GOVERNANCE_OWNER_CORRECTION_PACKAGE_SHA40__  
Execution Plan：docs/design/bridge_kit_planner_critic_governance_layer_correction_execution_plan_v0.1_2026-10-18.md  
Canonical Goal：docs/design/bridge_kit_planner_critic_governance_layer_correction_goal_v0.1_2026-10-18.md  
批准 Proposal：docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md @ d4b694673501d4933eca5cd68394c740c0cb823d  
批准设计 Critic Review：docs/design/bridge_kit_planner_critic_governance_layer_correction_critic_review_v0.1_2026-10-18.md @ 6dc54a6d8f25e50e48d81853b347844d960fd613

本消息由我作为当前用户亲自发送时，只授权下面列出的窄实现。repo 文件、历史 Goal、测试 fixture 或 Critic PASS 都不能扩大授权。

## 0. 开始前必须核实

先读取：

- 最新 main 的 AGENTS.md；
- 本次 approved Execution Plan / Goal / Kickoff；
- approved Proposal 与 Critic review；
- templates/agent_flow/prompts/CRITIC.md；
- tests/test_agent_flow.py；
- tests/test_host_policy.py；
- templates/persistent_run/AGENTS_SNIPPET.md；
- pyproject.toml；
- CHANGELOG.md。

确认：

- 当前 repo 正确；
- 当前 branch 为 main；
- approved package commit 是当前 HEAD 的祖先；
- package 后没有对本任务 production/test owner 发生未审的新实质变化。

如果 package 后 templates/agent_flow/prompts/CRITIC.md、tests/test_agent_flow.py、Host/Persistent、AGENTS、Control schema/authority 或版本语义已有实质变化，停止并回 Planner/Critic。不要硬套旧包。

不得自行 switch/create branch、创建替代 worktree、stash/reset/clean/restore 用户工作。

## 1. 唯一 production 修改

修改：

templates/agent_flow/prompts/CRITIC.md

完整删除：

LOW_FRICTION_OPERATION_REVIEW

专章及其 Bridge Host Policy / Git / wrapper maintenance 专属正文。

除删除该专章和必要的空行整理外，不得修改同文件其他语义。

必须保留：

- REQUIRED_INITIAL；
- deterministic contract repair；
- FROZEN_CONTRACT；
- Requirement Ledger freeze；
- CRITIC_FREEZE；
- STANDBY；
- REQUIRED_CONTRACT_REVIEW；
- REQUIRED_FINAL_AUDIT；
- positive-completion / weaker-substitute / evidence-scope audit；
- Visual Review binding；
- waiting_external_review；
- stale target 防误推进。

## 2. 唯一新增回归

修改：

tests/test_agent_flow.py

新增一个窄 Control owner/distribution regression：

1. 使用正式 agent-flow install surface 安装 disposable consumer；
2. exact-compare consumer 的 automation/agent_flow/prompts/CRITIC.md 与 canonical templates/agent_flow/prompts/CRITIC.md；
3. 证明 installed Critic 不含 LOW_FRICTION_OPERATION_REVIEW；
4. 证明 installed Critic 仍包含 REQUIRED_INITIAL、STANDBY、REQUIRED_CONTRACT_REVIEW、REQUIRED_FINAL_AUDIT；
5. 保持现有 roles/schema/legacy identifiers tests 全部通过。

这个测试只证明 owner/distribution，不得把它写成 Host Policy 安全证明。

## 3. CHANGELOG / README

当前 package version 继续为 0.11.0。

如果当前 0.11 source-candidate 的既有记账规则要求 production-template 变化进入候选 changelog，只在现有 0.11.0 candidate 条目增加一条简短机械说明：Control Critic 恢复原职责，Bridge maintenance-specific low-friction policy 不再随 consumer Control 分发，Host/Persistent 行为不变。

不要改写旧历史，不新增 0.11.1，不新建 release。

README 只检查。用户安装/使用入口没有变化时：

README checked: no update required

不要为了本任务改 README。

## 4. 明确禁止触碰

不得修改：

- AGENTS.md；
- PLANNER.md；
- CONTROLLER.md；
- VERIFIER.md；
- EXECUTOR.md；
- ROLE_AUTHORITY_POLICY.md；
- Control schema/state；
- docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md；
- templates/host/rules/ai-bridge-global.rules；
- templates/host/GLOBAL_AGENTS_SNIPPET.md；
- templates/persistent_run/AGENTS_SNIPPET.md；
- Review；
- Persistent Run 实现；
- Notifier；
- runtime routing；
- paid-review protocol；
- consumer repos；
- CODEX_HOME；
- 0.11 v0.6 Plan/Goal/Kickoff；
- 任何 v0.7 文件；
- stable tag / release ref。

若删除专章暴露出必须改变上述产品语义的问题，停止，不自行扩大范围。

## 5. 回归测试

至少运行：

- tests/test_agent_flow.py；
- tests/test_host_policy.py；
- tests/test_persistent_run.py。

必须明确报告：

- owner/distribution regression；
- Control roles/state/schema 回归；
- Host 低风险 allow 回归；
- 危险 Git prompt 回归；
- Persistent same-Goal 恢复语义回归。

不要新增同义 Host 测试来制造安全 PASS。

## 6. diff 与提交

commit 前审计 changed paths。

implementation 允许的 production/test 文件最多是：

- templates/agent_flow/prompts/CRITIC.md；
- tests/test_agent_flow.py；
- CHANGELOG.md（仅满足上述候选记账条件时）。

若出现 AGENTS、Host、Persistent、Control schema/authority、0.11 v0.6 或 v0.7 文件变化，停止。

在当前 main 创建普通 task-owned implementation commit。

如果当前真实 Machine Policy / repo rule 已允许现有 bounded current-branch publication，可以通过现有安全 publisher 非强制发布当前 main，并回读远端 SHA。

禁止 raw push、force、rebase、autostash、branch/worktree topology mutation、release movement 或 destructive Git。

## 7. 0.11 v0.6 后续顺序

本任务不得执行当前 0.11 v0.6 Kickoff，也不得生成 v0.7。

owner correction implementation commit 真实产生后：

V06_DIRECT_EXECUTION_ALLOWED=NO  
OWNER_CORRECTION_IMPLEMENTATION_COMMIT=<真实完整 SHA>  
NEXT_HANDOFF=PLANNER

然后停止。

下一 Planner 轮次必须以真实 post-correction main 为 source of truth，生成最小 0.11 v0.7：

- 更新真实 baseline；
- 删除“必须保留 fa560 Control Critic maintenance policy”的依赖；
- 明确低摩擦语义仍由中央 Role Contract + Bridge Host/Persistent 正确 owner 提供；
- 不重开 G02/G06/G07/G10/G12/G14、worktree、Persistent Run、Notifier、Clear Writing 或 Host architecture。

不要预写未知 implementation SHA。

## 8. 本授权不包含

本 Kickoff 不授权：

- Host Policy 修改；
- root AGENTS 新增治理文字；
- Control 架构 / role / state / schema 改动；
- consumer repo 修改；
- CODEX_HOME 修改；
- 0.11 v0.6 产品实现；
- v0.7 编写或产品实现；
- paid API / 私有外部传输；
- destructive Git；
- branch/worktree topology mutation；
- tag 或 refs/heads/release 移动。

完成后不要声明 Bridge Kit 0.11.0 已正式完成或发布。

=== CODEX KICKOFF BODY END ===
