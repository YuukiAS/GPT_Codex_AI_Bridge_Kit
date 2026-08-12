# Reviewed Handoff v0.5 Implementation Spec

Status: implementation candidate for audit before `v0.5.0` tag.

## Product role

Reviewed Handoff is the middle workflow between Lite Handoff and high-risk Agent-Flow. It is intended for tasks where GPT should make the semantic/product plan, Codex should perform the implementation, and an independent GPT should review the real implementation once or twice before the user sees the final report.

Typical examples include external repository intake, medium-scale refactors, third-party capability adoption, documentation-system migrations, ordinary product features with semantic choices, and other tasks where Lite is too weak but Agent-Flow would impose unnecessary proof machinery.

Reviewed Handoff is not a smaller Agent-Flow. It has three logical roles only:

```text
Planner -> Executor -> Reviewer
```

The Controller is mechanical state handling, not an additional reasoning role.

## User interaction goal

The intended experience is:

1. the user provides the objective and source material once;
2. GPT Planner freezes the implementation plan;
3. a persistent lightweight machine watcher sees `PLAN_FROZEN` and launches Codex Executor;
4. Codex executes, verifies, commits and publishes `READY_FOR_GPT_REVIEW`;
5. a ChatGPT Scheduled Task reviews GitHub state asynchronously;
6. the local watcher automatically launches one Codex repair when the first review returns `REVISE`;
7. the second review must either pass, block, or escalate to the user;
8. the user returns to a single `FINAL_REPORT.md`.

No OpenAI API is required for the Planner/Reviewer loop. ChatGPT Scheduled Tasks are the asynchronous GPT wake-up mechanism, while GitHub-tracked task state is the communication bus. The Codex side uses a local watcher rather than asking the user to manually restart Codex after each GPT decision.

## Files

Project installation adds:

```text
automation/reviewed_handoff/
  README.md
  schema.json
  prompts/
    PLANNER.md
    CODEX_EXECUTOR.md
    REVIEWER_SCHEDULED_TASK.md
  templates/
    REQUEST.md
    PLAN.md
    RESULT.md
    REVIEW.md
    FINAL_REPORT.md
  tasks/
```

Each task uses:

```text
automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
automation/reviewed_handoff/tasks/<task_key>/PLAN.md
automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
results/<task_key>/RESULT.md
results/<task_key>/REVIEW_1.md
results/<task_key>/REVIEW_2.md        # optional
results/<task_key>/FINAL_REPORT.md
```

Git history preserves older versions of mutable Markdown artifacts. Reviewed Handoff does not create a parallel history manifest.

Watcher operational state and logs are machine-local and deliberately live outside the repository:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/watcher.json
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/reviewed-handoff/<repo>/logs/
```

This local state is operational dedup/retry state only. It is not workflow identity and is never part of GPT review semantics.

## State machine

Normal states:

```text
PLAN_REQUESTED
PLAN_FROZEN
EXECUTING
READY_FOR_GPT_REVIEW
REVISE
PASS
AWAIT_HUMAN_DECISION
```

Exceptional states:

```text
NEEDS_GPT_PLANNER
BLOCKED
```

The canonical transition graph lives in `schema.json` and the Python core. Illegal transitions fail closed.

`READY_FOR_GPT_REVIEW` is not equivalent to completion. It requires a current `RESULT.md`, an `implementation_commit` locator, and `ci_status=PASS` when CI is required.

`AWAIT_HUMAN_DECISION` and `BLOCKED` are user-facing terminal states. Every terminal state must have a structurally valid `FINAL_REPORT.md`; the user should never have to reconstruct the outcome from CI logs or Reviewer artifacts.

## Review limit

`max_review_rounds` is 1 or 2 and defaults to 2.

With the default:

```text
Review 1 PASS   -> final report -> human gate
Review 1 REVISE -> one Codex repair
Review 2 PASS   -> final report -> human gate
Review 2 REVISE -> final report -> AWAIT_HUMAN_DECISION
```

There is no automatic third review/repair cycle. This is a product invariant, not a soft prompt preference.

## Planner re-entry

Execution can route to `NEEDS_GPT_PLANNER` when Codex encounters a material ambiguity that cannot be safely derived from the frozen Plan. The Scheduled GPT may make one minimal Plan revision (`max_plan_revisions=1`). A second material re-plan requirement writes a final report and escalates to the user.

Planner re-entry is not permission to redesign the task. It exists only to preserve zero-touch operation for one resolvable ambiguity.

## Codex watcher

The repository state alone does not wake Codex. Reviewed Handoff therefore includes a deliberately small persistent watcher:

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

The watcher performs only operational orchestration:

1. require a Git repository on an existing checked-out branch;
2. refuse dirty working trees before sync/launch;
3. fetch `origin/<branch>` and update only by `merge --ff-only`;
4. validate Reviewed Handoff tracked state;
5. react only to `PLAN_FROZEN` and `REVISE`;
6. launch one fresh `codex exec -C <repo> -` with the task-specific Executor prompt;
7. confirm the task state actually moved away from the triggering event before marking the event complete locally.

It does not create or switch branches, does not use persistent thread IDs, does not create role worktrees, and does not maintain receipts or cryptographic event identities. The event key is a plain local tuple of task/state/review round/plan revision/implementation locator.

Codex exit code 0 alone is not progress. An event that does not move task state is retried only a bounded number of times. Exhausted attempts publish an operational `BLOCKED` plus `FINAL_REPORT.md` rather than retrying forever or discarding local work.

## Reviewer authority

Reviewer checks only:

- whether the frozen Plan was actually implemented;
- whether Plan acceptance gates are met;
- whether relevant existing behavior regressed;
- whether prior blocking findings were actually closed;
- whether current tests/CI and user-facing artifacts support the claimed result.

Reviewer must not make a new feature, abstraction, style preference, or theoretical improvement blocking merely because it would be nicer. New scope belongs in non-blocking backlog unless it is required by the frozen Plan or a real regression boundary.

## Anti-overengineering boundary

Reviewed Handoff deliberately does **not** use:

```text
request nonce
Requirement Ledger
Stable Review Snapshot
review_target_id
semantic source manifests
role receipt graph
Review Bundle hash
artifact SHA graph
Final Critic
independent Verifier role
persistent role thread binding
role worktree identity
```

`base_commit` and `implementation_commit` are locators so GPT can inspect the real Git diff. They are not workflow identity and do not invalidate the task merely because control-plane commits move.

Do not add Agent-Flow provenance machinery to Reviewed Handoff unless a concrete false-PASS case cannot be addressed by the frozen Plan, the real diff, tests/CI, and bounded GPT review. If that level of proof is required, use Agent-Flow instead of enlarging Reviewed Handoff.

## Scheduled Task contract

A repository using Reviewed Handoff should normally have one ChatGPT Scheduled Task. Each run reads the repository's `schema.json`, scheduled reviewer prompt, and all task `CURRENT.json` files.

It processes only states that explicitly require GPT work, primarily:

```text
NEEDS_GPT_PLANNER
READY_FOR_GPT_REVIEW
PASS
```

No matching task means no side effects and no user notification.

The same scheduled task can perform the one allowed Planner re-entry and the Reviewer role. It must never impersonate Codex Executor. Executor wake-up belongs to the local watcher.

## Final report

The final report is user-facing and required for all terminal states. Its first sections describe:

- what the task solved;
- what changed and where;
- what new capability/behavior now exists;
- what was deliberately rejected or left unchanged;
- concrete example usage;
- regression status and remaining limitations.

If the automatic loop stops because of review-limit, planner ambiguity or operational blockage, the same report must instead explain what completed successfully, what remains unresolved, why automation stopped and what human decision/recovery is required.

Commit IDs, tests, CI and artifact paths belong in the technical appendix rather than dominating the report.

## Release requirements

Before tagging `v0.5.0`:

- all existing Lite/Host/Notifier/Agent-Flow tests remain green;
- Reviewed Handoff install is additive and branch-free;
- illegal state jumps fail closed;
- Plan/Result/Review artifacts are validated;
- all terminal states require a valid Final Report;
- review round limit is machine-enforced;
- one-plan-revision limit is machine-enforced;
- manual state transitions cannot bypass GPT review artifacts;
- CI-required tasks cannot become review-ready before PASS;
- the local watcher state lives outside the repository;
- watcher dry-run does not mutate workflow state;
- Codex exit 0 without state progress is not treated as completed;
- watcher reacts only to Executor-owned states and never creates/switches branches;
- no Agent-Flow provenance fields appear in Reviewed Handoff current state;
- GitHub Actions is green on Python 3.9 and current Python.
