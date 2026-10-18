# Bridge Kit Planner/Critic 治理职责归位修正 — Execution-ready Critic Review v0.1

日期：2026-10-18

## Active Review Context

- target_repo: `YuukiAS/GPT_Codex_AI_Bridge_Kit`
- target_plugin_or_domain: Bridge Kit governance / maintenance
- design_topic_or_task_key: `bridge-kit--planner-critic-governance-layer-correction`
- source_branch_or_ref: `main`
- review_stage: `EXECUTION_READY_REVIEW_R0`
- approved proposal: `docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md` v0.1 @ `d4b694673501d4933eca5cd68394c740c0cb823d`
- approved design Critic review: `docs/design/bridge_kit_planner_critic_governance_layer_correction_critic_review_v0.1_2026-10-18.md` @ `6dc54a6d8f25e50e48d81853b347844d960fd613`
- execution package commit: `fee2150240a9e047c63fc453e1b549e3409a987a`
- Execution Plan: `docs/design/bridge_kit_planner_critic_governance_layer_correction_execution_plan_v0.1_2026-10-18.md`
- Canonical Goal: `docs/design/bridge_kit_planner_critic_governance_layer_correction_goal_v0.1_2026-10-18.md`
- Kickoff Draft: `docs/design/bridge_kit_planner_critic_governance_layer_correction_kickoff_v0.1_2026-10-18.md`

## 1. 结论

`CRITIC_RESULT=PASS`

`READY_FOR_CODEX=YES`

本次批准的是一个非常窄的 owner-correction 实现：从消费者 Control Critic 模板中删除错误放置的 `LOW_FRICTION_OPERATION_REVIEW` 专章，增加一个正式 Control 安装分发回归，并做既有 Host/Persistent should-not-change 回归。

本次 PASS 不授权重新设计 Host Policy、修改 root AGENTS、修改 Control role/schema/state、修改消费者仓库、修改 CODEX_HOME、执行当前 0.11 v0.6、编写 v0.7、移动 release 或调用 paid/external 服务。

## 2. 强制来源与 package identity

实际读取 AI_Skills_Collection 最新 main：

- Planner Role Contract 1.5，blob `f7980a08307f06bd93ed71e0c4b7d4b58fcb19e6`
- Critic Role Contract 1.5，blob `2362aaa510cd506b4d740ea02a2bc8c40edb778a`
- Plugin Capability Gate Policy 1.1，blob `1b9d5509ef0d78c5548ee031b87c8c086d2327ab`

没有发现会改变本 execution-ready 判断的角色合同漂移。

比较：

`6dc54a6d8f25e50e48d81853b347844d960fd613...fee2150240a9e047c63fc453e1b549e3409a987a`

结果为 exactly one commit ahead，只新增三份 execution-package 文档：

1. `bridge_kit_planner_critic_governance_layer_correction_execution_plan_v0.1_2026-10-18.md`
2. `bridge_kit_planner_critic_governance_layer_correction_goal_v0.1_2026-10-18.md`
3. `bridge_kit_planner_critic_governance_layer_correction_kickoff_v0.1_2026-10-18.md`

没有夹带产品源码、模板、Host Policy 或测试修改。

## 3. 三份执行包一致性

Execution Plan、Canonical Goal 和 Kickoff 对以下内容一致：

- 唯一 production 修改是删除 `templates/agent_flow/prompts/CRITIC.md` 中的错误专章；
- 唯一新增回归落在 `tests/test_agent_flow.py`；
- `CHANGELOG.md` 仅在现有 0.11 source-candidate 记账规则要求时做机械同步；
- root `AGENTS.md` 不修改；
- Control Planner / Controller / Verifier / Executor / role policy / schema / state graph 不修改；
- Host Policy / Persistent Run / Review / Notifier / runtime / paid-review 不修改；
- v0.6 历史对象不修改、不执行；
- v0.7 不在本任务中生成；
- package version 继续 `0.11.0`，release 不移动。

没有发现 Goal 比 Plan 更宽，也没有发现 Kickoff 比 Goal/Plan 授权更宽。

## 4. Control owner / distribution 验收

新增 regression 设计验证的是正确对象：

- 走正式 `agent-flow install`；
- 安装 disposable consumer；
- exact compare installed `automation/agent_flow/prompts/CRITIC.md` 与 canonical template；
- 确认错误 maintenance 专章不再传播；
- 同时确认 REQUIRED_INITIAL / STANDBY / REQUIRED_CONTRACT_REVIEW / REQUIRED_FINAL_AUDIT 仍存在；
- 保留既有 roles/schema regression。

这足以证明本任务要求的 “错误 Bridge maintenance policy 不再通过 Control distribution 传播”。

它没有被错误描述为 Host Policy 安全证明，Host 行为仍由既有 Host test matrix 证明。

## 5. should-not-change 回归

当前 `tests/test_host_policy.py` 已包含真实 execpolicy 行为断言，包括：

- `git fetch origin main => allow`
- `git fetch --all --prune => allow`
- `git pull --ff-only origin main => allow`
- arbitrary fetch URL/refspec => prompt
- rebase/autostash => prompt
- force push => prompt
- tmux read => allow / mutation => prompt

因此本任务只要求重跑既有 Host regression，不需要再造一套同义安全测试。

Host AGENTS 仍持有 optional diagnostic / bounded raw-fallback 边界，Persistent Run 仍持有 same-frozen-Goal 恢复不重复索权语义。本任务禁止修改这些来源，并要求重跑 `tests/test_persistent_run.py`，因此 should-not-change 边界与本任务 blast radius 匹配。

## 6. 0.11 v0.6 冻结顺序

三份执行包一致冻结：

1. 先实现 owner correction；
2. 得到真实 implementation commit；
3. 输出 `V06_DIRECT_EXECUTION_ALLOWED=NO`；
4. 输出真实 `OWNER_CORRECTION_IMPLEMENTATION_COMMIT`；
5. `NEXT_HANDOFF=PLANNER`；
6. Codex 停止；
7. 下一 Planner 才能从 post-correction main 生成最小 v0.7。

Kickoff 明确禁止：

- 执行 v0.6；
- 生成 v0.7；
- 预写未知 implementation SHA；
- 重开 G02/G06/G07/G10/G12/G14 等 0.11 设计。

因此 owner correction 与现有 v0.6 的冲突不会被留给 Executor 临场解释。

## 7. 版本与授权

当前 main package version 是 `0.11.0`；formal release 内容仍是 `0.10.0`；CHANGELOG 仍标记 0.11.0 为 source candidate / formal release pending。

本 package 正确保持：

- 不 bump 0.11.1；
- 不建 stable tag；
- 不移动 release；
- 不单独 formal release。

Kickoff 的授权 envelope 仅允许：

- 删除错误 Control Critic 专章；
- 增加窄分发回归；
- 指定本地/deterministic tests；
- 条件性 CHANGELOG 机械同步；
- 当前 main 普通 task-owned commit；
- 仅在现有规则已经允许时使用 bounded current-branch publisher 做非强制同名 publication。

并明确禁止 raw push、force、rebase、autostash、branch/worktree topology mutation、Host Policy/root AGENTS/Control 架构/consumer/CODEX_HOME/paid API/v0.6/v0.7/release 等越界动作。

## 8. 外部核查

本轮针对性复核 Git 官方文档：

- `git fetch` 的 `--prune` 会删除远端已不存在的 remote-tracking refs；
- `git pull --ff-only` 只允许 fast-forward，分叉时失败。

这些具体命令行为属于 Host Policy exact command shape / behavior test 的产品边界，而不是消费者 Control Critic 的合同审查职责。外部核查没有暴露新的 execution-ready blocker。

## 9. PASS 边界

本次 PASS 证明：execution package 已经完整、一致、范围足够窄，Codex 不需要再做产品或架构决定即可执行 owner correction。

本次 PASS 不证明：

- implementation 已完成；
- 0.11.0 整体 execution-ready；
- 0.11 Gate 已通过；
- 0.11.0 已正式发布；
- v0.7 已生成或批准。

`APPROVED_PROPOSAL_PATH=docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md`

`APPROVED_GOAL_PATH=docs/design/bridge_kit_planner_critic_governance_layer_correction_goal_v0.1_2026-10-18.md`

`APPROVED_KICKOFF_PATH=docs/design/bridge_kit_planner_critic_governance_layer_correction_kickoff_v0.1_2026-10-18.md`

`APPROVED_COMMIT=fee2150240a9e047c63fc453e1b549e3409a987a`

`READY_FOR_CODEX=YES`

`NEXT_HANDOFF=CODEX`
