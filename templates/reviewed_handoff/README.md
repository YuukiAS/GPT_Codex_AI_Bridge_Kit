# Reviewed Handoff Core

Reviewed Handoff 是 Lite Handoff 与 Agent-Flow 之间的中档工作流。它适合需要 GPT 先做产品/语义规划、Codex 大量实现、随后由独立 GPT 审核一到两轮的任务。

它只有三个逻辑角色：Planner、Executor、Reviewer。Controller 只允许做机械状态推进，不是独立思考角色。

核心流程：

```text
GPT Planner
→ Codex Executor
→ Scheduled GPT Reviewer
→ optional Codex repair
→ Scheduled GPT Reviewer
→ human reads FINAL_REPORT.md
```

Scheduled Reviewer 使用 ChatGPT「安排任务」定时检查 GitHub 上的 `CURRENT.json`。没有待处理状态时必须无副作用退出。它不需要 OpenAI API。

Reviewed Handoff 刻意不使用 Agent-Flow 的 Requirement Ledger、Stable Review Snapshot、角色 receipt graph 或 provenance hash graph。`base_commit` 与 `implementation_commit` 只作为 Git 定位信息；review 是否通过取决于冻结 Plan、当前 diff、真实测试/CI 和 regression risk。

每个任务的机器状态位于：

```text
automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
```

人类/模型交接 artifact：

```text
automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
automation/reviewed_handoff/tasks/<task_key>/PLAN.md
results/<task_key>/RESULT.md
results/<task_key>/REVIEW_1.md
results/<task_key>/REVIEW_2.md    # optional
results/<task_key>/FINAL_REPORT.md
```

Review 最多两轮。第二轮仍为 `REVISE` 时必须进入 `AWAIT_HUMAN_DECISION`，不得继续自动返修。Planner 在执行中最多允许一次 scheduled re-plan；再次出现需要改变冻结 Plan 的实质歧义时交给用户。
