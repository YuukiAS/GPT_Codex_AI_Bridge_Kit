# Bridge 短期 TODO 已收口

除有意排除的 Program Run 外，没有 active Bridge-owned short-term TODO。
这里核销的是已批准的短期产品合同，不把历史 draft 的每个候选设想升级成承诺。
0.11.0 的实现、最终正常入口验收和正式分发已经完成；0.11.1 只补齐通知 cadence
缺陷与文档总账，不重新验收旧架构，也不声称实现了未来自治项目控制。

| 历史文件（均位于 `docs/`） | 当前状态与实际能力 |
|---|---|
| `TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md` | CLOSED / IMPLEMENTED；Control / Agent-Flow 自 0.4.0 起正式提供，保留设计历史。 |
| `TODO_BOUNDED_REVIEWED_WORKTREE_EXECUTION.md` | CLOSED / IMPLEMENTED；0.9.0 materialize、0.9.1 bootstrap。 |
| `TODO_EXECUTION_CONTEXT_CONTINUITY.md` | CLOSED / IMPLEMENTED / PROVEN；0.11 exact execution/source preflight；旧 worktree exchange / reader 方案排除。 |
| `TODO_EXECUTION_RELIABILITY_CLOSURE.md` | CLOSED / FORMALLY RELEASED；0.10.0 sandbox-first、拒绝分类、publisher 与运行身份诊断。 |
| `TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md` | CLOSED；canonical safe reads、bounded publisher/worktree helper 已提供；plugin-replay 窄保留；更宽原生命令和未来退役设想不阻塞当前发行。 |
| `TODO_HOST_POLICY_SELF_REFRESH_AND_CURRENT_BRANCH_SYNC.md` | CLOSED / IMPLEMENTED 的 Bridge 范围；current-branch FF、instruction budget、身份诊断已提供；机器更新由 AI_Skills owner 负责，无热自更新。 |
| `TODO_LOCAL_AUTONOMOUS_ACCEPTANCE_WORKFLOW.md` | CLOSED / RESCOPED TO AI_Skills workflow-core；domain self-QA 不属于新 Bridge workflow。 |
| `TODO_NEXT_BRIDGE_LOW_FRICTION_CONVERGENCE.md` | CLOSED；组成项由 0.9.x–0.11.1 实现，不拉入 future roadmap。 |
| `TODO_PERSISTENT_RUN_PROGRESS_ETA_REPORTING.md` | CLOSED / IMPLEMENTED / PROVEN；native/bridge-child progress、latest/history、ETA/UNKNOWN、stall、recovery、cadence 与 machine Notifier。 |
| `TODO_RELEASE_MAIN_DISTRIBUTION_DRIFT.md` | 保持 CLOSED；正式分发只跟随 release，不跟随后续 evidence HEAD。 |
| `TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md` | CLOSED / FORMALLY RELEASED；0.9.3 publish-first。 |

## 可核对的实现与证据

- Control：`docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`、`ai_bridge_kit/agent_flow.py`。
- 低打扰 / Reviewed：`results/bridge-core--low-friction-operations-convergence/FINAL_REPORT.md`、
  `results/reviewed-handoff--first-remote-publication/FORMAL_RELEASE_CLOSURE.md`。
- 0.10.0：`results/bridge-core--execution-reliability-closure/` 保留当时阶段性报告的原始限定；
  其后正式 release 基线可在下列 0.11.0 formal closure 的 old-release readback 核对。
- 0.11.0：`results/bridge-core--product-scope-reset/v6/391ff88/ACCEPTANCE_STATUS.json`、
  `replacement/OBSERVATION_SUMMARY.json` 与 `FORMAL_RELEASE_CLOSURE.json`（后两者同一目录下）。
- 0.11.1：`tests/test_persistent_cadence.py` 和
  `results/bridge-core--product-scope-reset/0.11.1/` 的候选绑定测试、CI、diff 与发布记录。
  历史 live 证据仍绑定原 0.11.0 SHA，不倒签成新的 live run。

## 明确不做的事

Program Run 保持 **INTENTIONALLY_EXCLUDED / FUTURE**：未实现自主发现下一任务、长期
自治项目控制、自动任务链或自动生成下一个 Goal。Project State Bridge 等历史 roadmap
同样只是未来设想，不是当前短期 release blocker。AI_Skills machine update 和 workflow-core
的交付准入归各自 owner，不能计作 Bridge active TODO。

```text
ACTIVE_BRIDGE_SHORT_TERM_TODOS=0
INTENTIONALLY_EXCLUDED=Program Run
RESCOPED_OTHER_OWNER=AI_Skills machine update; workflow-core delivery admission
```
