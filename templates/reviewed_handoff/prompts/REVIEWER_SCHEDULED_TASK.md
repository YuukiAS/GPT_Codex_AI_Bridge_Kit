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

## READY_FOR_GPT_REVIEW

Reviewer 必须独立读取：

- REQUEST.md；
- 冻结的 PLAN.md；
- RESULT.md；
- `base_commit..implementation_commit` 的真实 Git diff；
- 当前 implementation commit 的真实 CI/check 状态（若项目要求 CI）；
- 现有测试与必要的 user-facing artifacts；
- 之前的 REVIEW_<n>.md，仅用于检查 blocker closure。

Review 的唯一目标是判断当前实现是否满足冻结 Plan 且没有造成相关 regression。禁止仅因为“还可以更优雅”“可以再加一个 abstraction”“理论上更安全”而扩大冻结 scope。

每个 blocking finding 必须说明：Plan/回归依据、真实 observed evidence、最小修复、修复后要看到的 evidence。没有冻结 Plan 或已有行为依据的问题只能作为 non-blocking note/backlog。

写 `REVIEW_<round>.md`，decision 只能是 `PASS`、`REVISE` 或 `BLOCKED`。

- 第一轮 `REVISE`：进入 `REVISE`，本地 Codex watcher 会自动启动一次最小 repair。
- 第二轮仍 `REVISE`：先写 `FINAL_REPORT.md`，清楚说明已完成内容、仍未关闭的 blocker、为什么自动返修停止以及用户下一步选择，再进入 `AWAIT_HUMAN_DECISION`；不得开启第三轮自动返修。
- `BLOCKED`：先写 `FINAL_REPORT.md`，说明真实外部 blocker、已有成果和恢复方式，再进入 `BLOCKED`。
- `PASS`：写 `FINAL_REPORT.md`，然后进入 `AWAIT_HUMAN_DECISION`。

所有终态必须有 `FINAL_REPORT.md`。FINAL_REPORT 面向用户，不是 CI 日志。必须先讲：本轮解决了什么、实际改了哪里、产生了什么以前没有的能力或行为、哪些候选/方案被拒绝及原因、是否有 regression 风险、给出可直接理解的 example usage。技术 appendix 再列 commit、tests/CI 和 remaining limitations。
