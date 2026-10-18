# Bridge Kit Planner/Critic 治理层归位修正 — 独立 Critic Review v0.1

日期：2026-10-18

## Active Review Context

- target_repo: `YuukiAS/GPT_Codex_AI_Bridge_Kit`
- target_plugin_or_domain: Bridge Kit governance / maintenance
- design_topic_or_task_key: `bridge-kit--planner-critic-governance-layer-correction`
- source_branch_or_ref: `main`
- proposal_path_and_version: `docs/design/bridge_kit_planner_critic_governance_layer_correction_proposal_v0.1_2026-10-18.md` v0.1
- proposal_commit: `d4b694673501d4933eca5cd68394c740c0cb823d`
- review_stage: `DESIGN_PROPOSAL_REVIEW_R0`

## 1. 总结论

`CRITIC_RESULT=PASS`

本次批准的是 **Bridge Kit 自身 Planner/Critic 治理职责的 owner correction 设计方向**，不是 0.11.0 整体 execution-ready PASS，也不授权实现、Host Policy 修改、Control 架构变化、消费者仓库修改或正式发布。

Proposal 对根因的判断正确：提交 `fa560cb36f8203866e9d3e237d6879578377be0e` 把 Bridge Kit 产品维护层的低摩擦政策写进了消费者 Control 的 Critic 模板。低摩擦原则本身没有问题，错误在于 owner。Control Critic 应恢复为 Control task 的初始合同审查、必要合同复核与最终 closure audit，不应携带 Bridge Kit Host Policy、Git command policy、wrapper strategy 的产品维护职责。

本轮不需要第二套 Bridge 专属 Planner/Critic Role Contract，也不需要新增角色、schema、workflow、state、watcher、database、wrapper 或 Control mode。

## 2. 强制来源核对

实际读取 AI_Skills_Collection 最新 main：

- `docs/workflows/PLANNER_ROLE_CONTRACT.md`：1.5，blob `f7980a08307f06bd93ed71e0c4b7d4b58fcb19e6`
- `docs/workflows/CRITIC_ROLE_CONTRACT.md`：1.5，blob `2362aaa510cd506b4d740ea02a2bc8c40edb778a`
- `docs/workflows/PLUGIN_CAPABILITY_GATE_POLICY.md`：1.1，blob `1b9d5509ef0d78c5548ee031b87c8c086d2327ab`

与 Proposal 编写时记录一致，没有发现会改变本审查结论的新版本漂移。

中央 1.5 已经真实覆盖本轮大部分网页端通用治理语义：先确认 canonical owner；比较更简单路线；新增控制层必须证明已有 owner 不足；审查总耗时、人工往返、等待、费用与故障面；不能仅以“更保险”为理由增加复杂度；workflow hardening 还必须检查是否造成正常情况过度限制、重复审批或状态复杂度。

因此，本轮没有证据支持再建立一套 Bridge 专属网页端 Role Contract。

## 3. Control Critic 的 owner 裁定

实际读取当前 Bridge main 的：

- `templates/agent_flow/prompts/CRITIC.md`
- `templates/agent_flow/prompts/PLANNER.md`
- `templates/agent_flow/prompts/CONTROLLER.md`
- `templates/agent_flow/prompts/VERIFIER.md`
- `templates/agent_flow/ROLE_AUTHORITY_POLICY.md`
- `templates/agent_flow/README.md`
- `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`

Control 的正式角色边界很明确：

- Planner：用户/产品/科学意图、合同解释、实现审查和 repair direction；
- Critic：required initial audit、必要 contract review、required final audit；
- Controller：机械路由；
- Verifier：冻结 requirement 下的验证；
- Executor：实现与授权 runtime evidence。

`ROLE_AUTHORITY_POLICY.md` 明确写明 Critic 只参与 required initial audit、required contract review 和 required final audit；v0.4 spec 也明确 Critic 不得成为通用 implementation reviewer 或进入每轮 repair loop。

`templates/agent_flow/README.md` 同时证明这些模板只在消费者仓库显式安装 Control 时分发。因此 `LOW_FRICTION_OPERATION_REVIEW` 不是“放在这里也没坏处”的通用原则，而是会把 Bridge Kit 自身 Host/Git/wrapper 产品维护政策分发给消费者 Control Critic。

**裁定：Proposal 正确。该专章应从 `templates/agent_flow/prompts/CRITIC.md` 完整删除；其余 Control Critic authority 保持不变。**

## 4. 历史提交核对

实际读取提交：

`fa560cb36f8203866e9d3e237d6879578377be0e`
`docs: make Bridge Critic preserve low-friction operations`

该提交只修改：

`templates/agent_flow/prompts/CRITIC.md`

唯一实质新增就是：

`## LOW_FRICTION_OPERATION_REVIEW`

没有同时修改：

- `tests/test_agent_flow.py`
- `CHANGELOG.md`
- `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`
- Host Policy
- Persistent Run
- 其他 Control prompt

所以 owner correction 的直接回滚面确实很窄。Git 历史应保持原样，不应改写历史 CHANGELOG 来假装该提交从未发生。

## 5. 低摩擦原则的正确 owner

实际读取：

- `templates/host/rules/ai-bridge-global.rules`
- `templates/host/GLOBAL_AGENTS_SNIPPET.md`
- `templates/persistent_run/AGENTS_SNIPPET.md`
- `AGENTS.md`
- `tests/test_host_policy.py`

当前真实产品 owner 已经覆盖关键行为：

### Host Policy rules

直接 allow：

- `git fetch origin main`
- `git fetch --all --prune`
- `git pull --ff-only origin main`
- 安全的 GitHub 当前仓库读取
- Slurm 只读
- process 只读
- tmux 只读
- 既有 bounded semantic helpers

继续 prompt：

- arbitrary URL/refspec
- rebase / autostash
- raw `git push origin main`
- force / force-with-lease
- branch/worktree topology mutation
- reset / clean / restore
- remote mutation

### Host AGENTS

已经要求：

- optional process/tmux diagnostic imperfect 时，不得自动终止 unattended Goal；
- 不得把 failed diagnostic 扩大为 `setsid`、`sudo`、新 allocation、`scancel`、generic shell workaround 或 tmux/process mutation；
- bounded normal-entry blocker 不授权 raw fallback。

### Persistent Run

已经要求：

- 恢复同一个 frozen Goal 时，不因长期运行、detached 或 unattended 反复请求相同批准；
- 新 artifact/provider/resource/purpose/backend 或 Goal 外 effect 才重新审批；
- optional diagnostic failure 不自动终止整个 Goal。

### Tests

`tests/test_host_policy.py` 已经真实验证低风险 allow 与危险邻居 prompt，包括 fast-forward pull、rebase/autostash、force push、tmux mutation 等，不是仅靠文档声称安全。

**裁定：删除 Control Critic 专章不会删除低摩擦产品能力，也不会放宽危险操作。具体命令边界继续由 Host Policy + Host/Persistent AGENTS + 行为测试拥有。**

## 6. 根 AGENTS 是否还要新增一段

这里选择 Proposal 已经列出的更小替代：

**本轮不要向根 `AGENTS.md` 再新增“审批本身有成本”的治理段落。**

理由有三点。

第一，中央 Critic Role Contract 1.5 已经明确要求审查总耗时、人工往返、等待、费用和故障面，并明确要求 workflow hardening 检查“是否过度限制正常情况、是否造成新的重复审批或状态复杂度”。这已经覆盖“审批本身不是零成本”的通用审查原则。

第二，Bridge 当前根 `AGENTS.md` 和 Host/Persistent policy 已经给出了具体低打扰行为和恢复边界。网页端 Planner/Critic 按中央 Role Contract 读取目标 repo AGENTS 与相关 policy 后，已有足够直接证据判断某个新设计是否把低风险正常入口重新推回重复审批。

第三，当前根 `AGENTS.md` 实测仍为 32355 UTF-8 bytes、488 行，而且 0.11 正在专门收口 instruction budget。为了重复一个已经存在于中央合同和 repo policy 中的原则，再增加根指令没有足够收益。

因此，本次 owner correction 的最小实现应是：

- 删除错误 Control Critic 专章；
- 不向根 AGENTS 新增同义治理文字；
- 不复制具体 Git allowlist 到任何新的治理层。

这不是否定低摩擦原则，而是把它留在正确 owner。

## 7. 是否需要第二套 Bridge Planner/Critic Role Contract

不需要。

当前有效结构已经足够：

`AI_Skills_Collection 最新 Planner/Critic Role Contract`
→ `Bridge 最新 AGENTS / repo-specific policy`
→ `当前 Bridge Proposal / Plan / evidence`
→ 独立 Web Critic
→ 经批准后 Codex

Bridge 历史 0.9 / 0.10 / 0.11 设计本来也一直通过读取中央 Role Contract 工作。没有直接证据证明这个模式无法承担 Bridge 维护。

新增：

- `Bridge/docs/workflows/PLANNER_ROLE_CONTRACT.md`
- `Bridge/docs/workflows/CRITIC_ROLE_CONTRACT.md`

只会产生第二套通用合同、版本漂移和 owner 冲突，收益不成立。

## 8. 测试与回归范围

Proposal 的测试方向足够，但要保持窄。

推荐增加一个 Control distribution/owner regression：

1. 使用正式 `agent-flow install` / template distribution surface 安装 disposable consumer；
2. 验证 installed Control Critic 与当前 canonical Control Critic 一致；
3. 验证已删除的 Bridge-maintenance-only 专章不会传播到消费者。

这项测试只证明“owner 与 distribution 边界”，不能声称证明 Host Policy 安全。

不需要因为删除该段新增一套 Host 安全测试。只需重跑现有 `tests/test_host_policy.py` 行为矩阵，确认现有 allow/prompt 语义未变化。

`tests/test_agent_flow.py` 当前没有要求 `LOW_FRICTION_OPERATION_REVIEW` 必须存在，所以不存在需要同步删除的既有正向断言。

不改历史 CHANGELOG；如当前 0.11 source-candidate changelog 按仓库发布规则需要记录最终 production-template 变化，可在后续 execution package 中按现有 0.11 closure 机械处理，但不能用 changelog 重写历史。

## 9. 当前 0.11 v0.6 的直接冲突

这里确认 Proposal 判断成立，而且需要显式解决。

当前 `docs/design/0.11.0_final_scope_recovery_execution_plan_v0.6_2026-10-18.md` 明确写道：

- v0.6 设计基线为 `fa560cb36f8203866e9d3e237d6879578377be0e`；
- 相比 v0.5，唯一已有文件变化是 Control Critic；
- v0.6 “保留该变化”，下一 Critic 必须连同当前 Control Critic authority 一并核实。

一旦本 owner correction 落地，这句话就成为过期且与新设计直接冲突的执行要求。

**裁定：需要一个最小 superseding v0.7 execution package。**

不应篡改既有 v0.6 历史对象，也不应靠口头说明让未来 Codex猜哪条优先。v0.7 只允许做以下 alignment：

- 更新设计基线到 owner correction 后的真实 main；
- 删除“必须保留 fa560 Control Critic maintenance policy”的依赖；
- 明确低摩擦产品语义由中央 Role Contract + Bridge Host/Persistent 正确 owner 提供；
- 保留 v0.6 其他所有已冻结设计，不重开 G02/G06/G07/G10/G12/G14、Persistent Run、Notifier、Clear Writing、worktree 或 Host 架构。

当前 main 在 Proposal 后又有 `16ae5fefe8747e54a6db60bd155311daff1efed7`，只对 0.11 v0.6 的 quiescence / reader isolation 做进一步设计硬化；这不改变本 owner correction 判断，但 Planner 生成 v0.7 时必须从最新 main 读取，不能回退到 Proposal 编写基线。

## 10. 版本与发布

实际读取当前：

- main `pyproject.toml`：`0.11.0`
- release ref 内容的 `pyproject.toml`：`0.10.0`
- main `CHANGELOG.md`：`0.11.0 - 2026-10-12 (source candidate; formal release pending)`

因此 Proposal 的版本判断正确：

- 本 correction 属于 0.11.0 开发期普通修正；
- 不 bump `0.11.1`；
- 不新建 stable tag；
- 不单独 formal release；
- 如果发生在某个 frozen rc SHA 之后，只生成新的 `0.11.0-rc.N @ exact SHA`；
- 网页端 Planner/Critic 对中央合同 + Bridge main policy 的消费不依赖 formal package release。

## 11. 外部核查

本轮只做了与 owner 判断直接相关的小规模官方核查。

Git 官方 `git-fetch` 文档明确说明 fetch 会更新本地 remote-tracking refs；`--prune` 删除远端已不存在的 remote-tracking refs。官方 `git-pull` 文档说明 pull 先 fetch，再集成；`--ff-only` 只允许 fast-forward，出现 divergent local history 时失败。

来源：

- https://git-scm.com/docs/git-fetch
- https://git-scm.com/docs/git-pull

这些是具体命令行为和 ref mutation 语义，应该由 Host Policy 的 exact command shape、负例和行为测试拥有。把这些产品级 allow/prompt 决策再写进每个消费者 Control Critic，并不能增强 Git 本身的安全边界，反而造成职责重复和传播错误 owner。

外部核查没有发现需要保留 `LOW_FRICTION_OPERATION_REVIEW` 在消费者 Control Critic 中的理由。

## 12. PASS 边界

本次批准：

1. 删除 Control Critic 中错误 owner 的 `LOW_FRICTION_OPERATION_REVIEW` 专章；
2. 保留 Control Critic 原有 initial / contract / final audit authority；
3. 不改 Host Policy、Persistent Run 或其安全行为；
4. 不新增根 AGENTS 治理段落；
5. 不新增 Bridge 专属 Planner/Critic Role Contract；
6. 增加窄的 Control distribution/owner regression，并重跑现有 Host 行为回归；
7. 通过最小 v0.7 对齐当前 0.11 execution package，避免保留错误 owner 的矛盾指令；
8. 保持 package version `0.11.0`，不移动 formal release。

本次 PASS **不代表**：

- owner correction 已经实现；
- 0.11.0 已 execution-ready；
- 0.11.0 已通过最终 Gate；
- Host Policy 有任何新授权；
- Control 架构获得任何扩展；
- formal release 获得批准。

`CRITIC_RESULT=PASS`

`READY_FOR_CODEX=NO`

`NEXT_HANDOFF=PLANNER`
