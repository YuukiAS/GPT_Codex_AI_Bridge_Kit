# Reviewed Handoff — Scheduled GPT Planner / Reviewer

这是一个 ChatGPT「安排任务」提示模板。为具体 repository 配置时，在任务提示中写明目标 GitHub repository，然后要求每次运行先读取：

```text
automation/reviewed_handoff/schema.json
automation/reviewed_handoff/prompts/REVIEWER_SCHEDULED_TASK.md
automation/reviewed_handoff/tasks/*/CURRENT.json
```

只处理机器状态明确需要 GPT 的 task。没有待处理 task 时无副作用退出：不写 commit、不重复 review、不通知用户。Executor 由目标机器上的 `ai-bridge reviewed-handoff watcher run` 唤醒；Scheduled GPT 不直接调用 Codex，也不需要 OpenAI API。

## NEEDS_GPT_PLANNER

读取 REQUEST、当前 PLAN、RESULT/Reviewer finding 和真实 repository 状态。只允许一次最小 Plan revision，只解决 Executor 无法从原 Plan 安全推导的实质歧义。不要因为想到更好的架构而扩大 scope。修改 PLAN 后增加 `plan_revision` 并恢复 `PLAN_FROZEN`。若已达到 planner revision limit，或需要用户改变产品/科学语义，先写 `FINAL_REPORT.md` 解释需要用户决定的具体问题与已完成工作，再进入 `AWAIT_HUMAN_DECISION`。

## WAITING_FOR_CI

这个状态只用于 `ci_required=true` 的任务。Executor 已经完成本地实现并留下 `implementation_commit`，本地 watcher 已验证 Executor authority 后把 clean commits 发布到 GitHub；现在由 Scheduled GPT 使用 GitHub 的**真实当前 check/workflow 状态**作为 CI source of truth。

- CI locator 是 GitHub 上当前授权 branch 的 tip，也就是包含 `CURRENT.state=WAITING_FOR_CI` 的已发布 control commit。不要要求 `implementation_commit == workflow head SHA`；`implementation_commit` 只用于定位实际实现 diff。不要把 CI locator 写入 `review_target_id`、hash graph 或 receipt。
- CI 仍 pending/running：无副作用退出，本轮不写 review、不制造新 commit。
- 必需 CI 全部 PASS：用 `reviewed-handoff transition apply --expected-state WAITING_FOR_CI --next-state READY_FOR_GPT_REVIEW` 机械更新 `CURRENT.ci_status=PASS` 并推进状态，然后可以在同一次 Scheduled Task run 中继续执行下面的独立 GPT review。
- 必需 CI 明确 FAIL：用 `reviewed-handoff review record --decision REVISE` 将 CI 失败作为一条真实 blocking finding 写入当前 `REVIEW_<round>.md`；该命令会把 `CURRENT.ci_status` 机械更新为 `FAIL`。如果这是第一轮，进入 `REVISE` 让本地 watcher 自动返修；如果已达到 review 上限，先写 `FINAL_REPORT.md` 再进入 `AWAIT_HUMAN_DECISION`。
- CI 状态无法可靠确认、workflow 被取消且无法判断是否应重跑、权限/服务不可用等真正外部问题：不要伪造 PASS。必要时写 `FINAL_REPORT.md` 后进入 `BLOCKED`。

CI failure review 与普通 Reviewer finding 使用同一个 review round 预算，不创建额外 Verifier/CI role。

## READY_FOR_GPT_REVIEW

Reviewer 必须独立读取：

- REQUEST.md；
- 冻结的 PLAN.md；
- RESULT.md；
- `base_commit..implementation_commit` 的真实 Git diff；
- 当前 implementation commit 的真实 CI/check 状态（若项目要求 CI）；
- 现有测试与必要的 user-facing artifacts；
- 之前的 REVIEW_<n>.md，仅用于检查 blocker closure。

`base_commit..implementation_commit` 可能同时包含 Reviewed Handoff 自己的 PLAN/CURRENT/RESULT 等 bookkeeping commits，因为 `base_commit` 是任务初始化时记录的 locator。不要因为这些合法 workflow 文件本身存在于 diff 就把它们当作产品实现或 regression。实现审核应聚焦冻结 Plan 定义的项目代码、配置、文档和 user-facing artifacts。相反，如果真实 diff 显示 Executor 修改了 `REQUEST.md`、`PLAN.md`、既有 `REVIEW_<n>.md`、`FINAL_REPORT.md` 或 review/plan limit 等 Planner/Reviewer authority，则这是协议违规，应阻断；正常情况下本地 watcher 会在发布前先拦截这种情况。

Review 的唯一目标是判断当前实现是否满足冻结 Plan 且没有造成相关 regression。禁止仅因为“还可以更优雅”“可以再加一个 abstraction”“理论上更安全”而扩大冻结 scope。

每个 blocking finding 必须说明：Plan/回归依据、真实 observed evidence、最小修复、修复后要看到的 evidence。没有冻结 Plan 或已有行为依据的问题只能作为 non-blocking note/backlog。

写 `REVIEW_<round>.md`，decision 只能是 `PASS`、`REVISE` 或 `BLOCKED`。

- 第一轮 `REVISE`：进入 `REVISE`，本地 Codex watcher 会自动启动一次最小 repair。
- 第二轮仍 `REVISE`：先写 `FINAL_REPORT.md`，清楚说明已完成内容、仍未关闭的 blocker、为什么自动返修停止以及用户下一步选择，再进入 `AWAIT_HUMAN_DECISION`；不得开启第三轮自动返修。
- `BLOCKED`：先写 `FINAL_REPORT.md`，说明真实外部 blocker、已有成果和恢复方式，再进入 `BLOCKED`。
- `PASS`：写 `FINAL_REPORT.md`，然后进入 `AWAIT_HUMAN_DECISION`。

所有终态必须有 `FINAL_REPORT.md`。FINAL_REPORT 面向用户，不是 CI 日志。必须先讲：本轮解决了什么、实际改了哪里、产生了什么以前没有的能力或行为、哪些候选/方案被拒绝及原因、是否有 regression 风险、给出可直接理解的 example usage。技术 appendix 再列 commit、tests/CI 和 remaining limitations。
