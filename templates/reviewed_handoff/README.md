# Reviewed Handoff Core

Reviewed Handoff 是 Lite Handoff 与 Agent-Flow 之间的中档工作流。它适合需要 GPT 先做产品/语义规划、Codex 大量实现、随后由独立 GPT 审核一到两轮的任务。

它只有三个逻辑角色：Planner、Executor、Reviewer。Controller 只允许做机械状态推进，不是独立思考角色。

核心流程：

```text
GPT Planner
→ local Codex watcher launches Executor
→ Scheduled GPT Reviewer
→ optional Codex repair
→ Scheduled GPT Reviewer
→ human reads FINAL_REPORT.md
```

GPT 异步唤醒使用 ChatGPT「安排任务」定时检查 GitHub 上的 `CURRENT.json`，不需要 OpenAI API。Codex 异步唤醒由机器上的轻量 watcher 完成：它只处理 `PLAN_FROZEN` 和 `REVISE`，同步当前已授权 branch 后启动一次新的 `codex exec`。Reviewer/Planner 和 Executor 仍然通过 GitHub tracked state 通信，不直接调用彼此。

机器上长期运行 watcher：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

生产环境也可以使用本机 lifecycle 包装命令，避免同一个仓库/分支误启多个正式 watcher：

```bash
ai-bridge reviewed-handoff watcher start --target /path/to/project --branch <existing-authorized-branch>
ai-bridge reviewed-handoff watcher stop --target /path/to/project --branch <existing-authorized-branch>
ai-bridge reviewed-handoff watcher restart --target /path/to/project --branch <existing-authorized-branch>
ai-bridge reviewed-handoff watcher status --target /path/to/project --branch <existing-authorized-branch>
```

`status` 会报告 watcher PID、启动时间、heartbeat、加载的 Bridge Kit 版本/源码 commit、当前 checkout commit、是否需要 restart，以及 active Executor event。

单次检查或部署前 dry run：

```bash
ai-bridge reviewed-handoff watcher once --target /path/to/project --branch <branch> --dry-run
```

Watcher 不创建 branch/PR，不使用 persistent Codex thread receipt，也不建立 SHA event graph。机器本地的 event 去重和日志位于 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/`，不会写进目标 repository。Codex exit code 为 0 也不自动视为成功：只有 task state 真正离开原 executor event 才算有进展；同一 executor event 的执行尝试有界，耗尽后进入可见的 `BLOCKED`，而不是无限重试。

如果 watcher 在 Codex 已提交合法 Executor 结果但发布前退出，重启后只会在 clean、ahead-only、能绑定到当前单一 Executor event、authority validation 和 workflow validation 均通过时恢复发布。dirty、diverged、来源不明或越权 commit 仍 fail closed；Codex 自身仍不得 push。

如果本地 working tree dirty，persistent watcher 不会死亡，也不会尝试接管、stash、reset、commit 或 push 未提交内容；它记录 `dirty_worktree_wait` 和 dirty paths 后低频等待。外部合法动作恢复 clean 后，同一个 watcher 会继续 fetch、validate 并路由当前 `PLAN_FROZEN` / `REVISE` event。

## External GPT wait contract

Executor 成功发布实现并把 `CURRENT` 推进到 GPT-owned state 后，外部 GPT 尚未产出新 decision 属于正常等待，不属于 watcher retry，也不属于 `BLOCKED`。常见等待态包括 `NEEDS_GPT_PLANNER`、`READY_FOR_GPT_REVIEW`，以及 `WAITING_FOR_CI` 在 CI 已经 PASS/FAIL 后需要 Scheduled GPT 继续写 review/transition 的阶段。

如果 `CURRENT.visual_review_required=true` 且不需要 CI，Executor 必须先发布渲染图片和 `results/<task_key>/visual_review/visual_inputs.json`，再进入 `READY_FOR_GPT_REVIEW`。`VISUAL_REVIEW.json` 缺失但 input manifest 有效时是 `waiting_visual_review_evidence`，等待 GitHub Actions 写回 evidence；这不消耗 `review_round`，也不是 `BLOCKED`。

如果同一个视觉任务还设置了 `CURRENT.ci_required=true`，合法顺序是先发布 implementation/render/`visual_inputs.json` 并停在 `WAITING_FOR_CI` / `ci_status=PENDING`。此时 visual evidence 仍可缺失，waiting owner 是 CI。只有 CI PASS 后 Scheduled GPT 才把任务推进到 `READY_FOR_GPT_REVIEW`；随后缺失 `VISUAL_REVIEW.json` 才表示等待 Visual Review evidence。CI FAIL 可以直接进入 `REVISE` 或非 PASS 型终态，不必先等待 Terra evidence。

等待从本轮实现首次正式发布并交棒给外部 GPT 起算，正常 minimum grace 是 `MIN_EXTERNAL_GPT_WAIT = 2 hours`。2 小时不是自动 deadline；超过 2 小时后，只要 repository state 合法、`RESULT.md` 和 `implementation_commit` 仍完整、Scheduled GPT/GitHub connector 没有明确失败，就继续报告 `waiting_external_review`，而不是写 terminal `FINAL_REPORT.md` 或把 `CURRENT.state` 改成 `BLOCKED`。

旧 review 只能作为历史上下文。`REVIEW_<n>.md` 的 `implementation_commit` 必须等于当前 `CURRENT.implementation_commit` 才是 fresh decision；不匹配时视为 stale review，不得重复执行旧 `REVISE`，也不得把旧 PASS/BLOCKED 当成当前实现的结论。等待期间不得增加 `review_round`、`plan_revision`、Executor retry 或 blocked-audit attempts。

只有出现具体不可自动恢复的外部故障证据时才允许 `BLOCKED`，例如 Scheduled GPT 被禁用/删除/过期、GitHub connector/auth 重复失败、workflow 安装损坏、必需 artifact 无法访问、repository state 非法，或确实需要用户作新的产品/科学/branch 决策。每个 `BLOCKED` 必须写清 actual failure、observed evidence、为什么继续等待不能恢复，以及 recovery action。

Reviewed Handoff 刻意不使用 Agent-Flow 的 Requirement Ledger、Stable Review Snapshot、角色 receipt graph 或 provenance hash graph。`base_commit` 与 `implementation_commit` 只作为 Git 定位信息；review 是否通过取决于冻结 Plan、当前 diff、真实测试/CI 和 regression risk。

如果 `CURRENT.ci_required=true`，Executor 只能发布 `WAITING_FOR_CI` 且保持 `CURRENT.ci_status=PENDING`。Scheduled GPT 读取 GitHub 上当前授权 branch tip 的真实 checks；该 branch tip 是普通 CI locator，不要求等于 `implementation_commit`，也不会写入 hash/receipt 链。`CURRENT.ci_status` 是唯一机器 CI 真值，`RESULT.md` 只负责说明本地执行和验证。

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

Review 最多两轮。第二轮仍为 `REVISE` 时必须进入 `AWAIT_HUMAN_DECISION`，不得继续自动返修。Planner 在执行中最多允许一次 scheduled re-plan；再次出现需要改变冻结 Plan 的实质歧义时交给用户。所有终态都必须有 `FINAL_REPORT.md`，因此用户回来后始终有一份面向人的总结可读，而不是只能翻 CI/Reviewer 日志。
