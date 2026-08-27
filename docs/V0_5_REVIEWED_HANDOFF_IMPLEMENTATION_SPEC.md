# Reviewed Handoff v0.5 Implementation Spec

Status: shipped in `v0.5.0`; `v0.5.1` adds the generic External GPT wait contract without changing the role model.

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
4. Codex executes, verifies, commits and publishes `READY_FOR_GPT_REVIEW`, or `WAITING_FOR_CI` when GitHub CI is required;
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

It may record human-facing observability for the current Executor event: task key, branch, phase, runtime type, App/thread id when a supported runtime can provide one, `started_at`, `completed_at`, `running`, last exit/result, last log path, waiting owner, and last publication status. These fields remain machine-local operational state. They must not be copied into `CURRENT.json`, hashed into semantic identity, or treated as Planner/Reviewer authority.

It also records the local watcher process lifecycle for each `target + branch`: PID, `started_at`, last heartbeat, loaded Bridge Kit package version, loaded Bridge Kit source commit when available, active Executor event, and last status. This process metadata is operational only. It does not create a workflow identity and does not change Planner/Executor/Reviewer authority.

## State machine

Normal states:

```text
PLAN_REQUESTED
PLAN_FROZEN
EXECUTING
WAITING_FOR_CI
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

`PLAN_FROZEN` is executable only when the current `PLAN.md` is structurally
valid against the installed Reviewed Handoff PLAN template: required
frontmatter must exist and all required sections must be present, including
`## Out of scope`. A Planner or Scheduled Planner transaction must write
`PLAN.md` first, re-read it, self-check it against the current
`automation/reviewed_handoff/templates/PLAN.md`, and only then write
`CURRENT.json` with `CURRENT.state=PLAN_FROZEN`. If this self-check fails,
`CURRENT` must remain in a GPT-owned repair/planning state rather than entering
an Executor-owned state.

`READY_FOR_GPT_REVIEW` is not equivalent to completion. It requires a current `RESULT.md`, an `implementation_commit` locator, and `ci_status=PASS` when CI is required.

For CI-required tasks, Codex Executor must stop at `WAITING_FOR_CI` with `CURRENT.ci_status=PENDING`. `CURRENT.ci_status` is the only machine truth for CI. `RESULT.md` is execution narrative and must not be treated as a second CI authority. The Scheduled GPT reviewer reads the real GitHub checks for the current authorized branch tip that contains `CURRENT.state=WAITING_FOR_CI`; that branch tip is the CI locator. It is a normal Git locator, not semantic identity, and it is not written into a hash chain or receipt graph. Do not assume `implementation_commit` equals the GitHub workflow head SHA, because the watcher may publish both implementation and control-plane commits.

For CI-required visual tasks, `WAITING_FOR_CI` may have `visual_review_required=true`, a valid task-local `visual_inputs.json` bound to the current `implementation_commit`, and no `VISUAL_REVIEW.json` yet. That state is owned by CI, not Visual Review. After CI PASS, Scheduled GPT advances the task to `READY_FOR_GPT_REVIEW`; only then does missing visual evidence become `waiting_visual_review_evidence`.

`AWAIT_HUMAN_DECISION` and `BLOCKED` are user-facing terminal states. Every terminal state must have a structurally valid `FINAL_REPORT.md`; the user should never have to reconstruct the outcome from CI logs or Reviewer artifacts.

## External GPT wait contract

When Executor has completed the authorized implementation, the implementation/result commits have been published, and `CURRENT` says the next action belongs to an external GPT Planner/Reviewer/Critic-style role, the task is `waiting_external_review`, not blocked.

Reviewed Handoff examples are `NEEDS_GPT_PLANNER`, `READY_FOR_GPT_REVIEW`, and `WAITING_FOR_CI` after CI has produced a PASS/FAIL state that requires Scheduled GPT to write the next transaction. The generic Bridge Kit policy must not rely only on these exact strings. It should prefer state ownership, `next_action`, role policy, repository schema, and the workflow contract.

`MIN_EXTERNAL_GPT_WAIT = 2 hours` is the minimum normal grace period from the first published handoff into an external-GPT-owned state. It is not an automatic deadline. After two hours, continued silence is still waiting if repository state is valid, the implementation/result artifacts are intact, the Scheduled GPT/GitHub connector mechanism exists, and there is no concrete connector/auth/scheduler/schema/artifact-access/user-decision/workflow-contract failure.

Pure waiting must not increment `review_round`, `plan_revision`, Executor retry counters, repair budget, or blocked-audit attempts. A round advances only when a fresh external decision is written. A repair round advances only when Codex receives and executes a fresh `REVISE`.

Stale review artifacts are not fresh decisions. A `REVIEW_<n>.md` whose `implementation_commit` does not match the current `CURRENT.implementation_commit` is historical context only; it must not drive `REVISE`, `PASS`, or `BLOCKED`, and it must not be replayed by the watcher.

External-review `BLOCKED` requires observed evidence that waiting cannot recover automatically: disabled/deleted/expired Scheduled GPT automation, repeated connector/auth failure, missing external role installation, invalid repository state, inaccessible required review artifact, visual-review access impossibility, required user product/scientific/branch decision, or a workflow-defined hard deadline. Every such blocker must state the actual failure, observed evidence, why waiting longer cannot resolve it, and the recovery action.

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
3. fetch `origin/<branch>` and update only by `merge --ff-only`, except for the narrow unpublished Executor recovery below;
4. validate Reviewed Handoff tracked state;
5. react only to `PLAN_FROZEN` and `REVISE`;
6. launch one fresh `codex exec -C <repo> -` with the task-specific Executor prompt;
7. confirm the task state actually moved away from the triggering event before marking the event complete locally.

It does not create or switch branches, does not create role worktrees, and does not maintain receipts or cryptographic event identities. The event key is a plain local tuple of task/state/review round/plan revision/implementation locator.

The foreground command remains:

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

Production deployments may also use the built-in local lifecycle wrapper:

```bash
ai-bridge reviewed-handoff watcher start --target /path/to/project --branch <branch>
ai-bridge reviewed-handoff watcher stop --target /path/to/project --branch <branch>
ai-bridge reviewed-handoff watcher restart --target /path/to/project --branch <branch>
```

`run` and `start` must both enforce one official watcher per `target + branch`.
If another verified watcher is already alive, the second launch returns
`ALREADY_RUNNING` with the existing PID and does not touch workflow state. A
stale marker whose PID no longer exists may be reclaimed. `stop` must verify
the PID command line, target, and branch before sending a signal; an
unverifiable PID fails closed and is not killed.

The watcher also exposes a read-only status view:

```bash
ai-bridge reviewed-handoff watcher status \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

The status view reports `task`, `state`, `executor_event`, `phase`, `thread_id`, `runtime_type`, `started_at`, `running`, `completed`, `completed_at`, `last_exit_code`, `last_result`, `waiting_owner`, `last_publication_status`, `last_publication_error`, and `last_log_path`. It also reports `watcher_process.alive`, `pid`, `started_at`, `last_heartbeat`, `loaded_bridge_version`, `loaded_bridge_commit`, `current_bridge_commit`, `restart_required`, `active_executor_event`, and last process status. If the running watcher loaded an older Bridge Kit source commit than the current checkout, status must clearly show `restart_required=true`; it must not auto-restart a working watcher.

Codex App visibility is an optional runtime property, not a Reviewed Handoff authority feature. The 2026-08-26 capability record in `docs/REVIEWED_HANDOFF_CODEX_APP_VISIBILITY_DECISION_2026-08-26.md` found that Codex CLI/App Server `0.148.0-alpha.9` with official `codex app-server --stdio` can create durable Codex threads with correct cwd/project binding and eventual Codex App project visibility, but the experiments only produced reliable post-completion UI visibility evidence. They did not verify bounded live discovery of an externally created running thread or safe multi-client writer takeover. Production therefore keeps using `codex exec` and records `runtime_type=codex_exec` with `thread_id=null`.

Do not re-test or adopt an App Server Executor launcher unless a real product capability changes: Codex CLI/App Server changes thread discovery or lifecycle behavior, official support appears for connecting to the currently running Codex App App Server instance through a stable API, a shared App Server / attach / discover / IPC mechanism is exposed, Codex App explicitly supports live discovery of externally created App Server threads, writer ownership / `thread/resume` semantics change, or official documentation promises running external threads appear in Codex App in real time. Implementations must not edit `~/.codex/session_index.jsonl`, Codex App databases, or private UI state to fake App visibility.

If fetched repository state is `invalid_workflow`, the persistent watcher must
fail closed for that cycle: record a clear machine-local status/error, launch
no Executor, write no tracked workflow files, and sleep with low-frequency
bounded backoff before fetching and validating again. This is not an Executor
attempt, not a review round, and not a repair budget event. If Planner later
publishes a valid workflow repair on the authorized branch, the same watcher
process must resume normal routing without requiring a user restart.

If the local working tree is dirty before sync, recovery, or launch, the watcher
must also fail closed for that cycle. It must not launch Codex, reset, checkout,
stash, commit, push, salvage, or guess ownership of uncommitted paths. A
persistent `watcher run` records `dirty_worktree_wait` and the dirty paths in
machine-local state, sleeps with low-frequency bounded backoff, and retries
after the tree is made clean by an external legitimate action. This condition
does not consume an Executor attempt, review round, plan revision, or repair
budget. `watcher once` may return non-zero for the current inability to
progress. True process-level errors, diverged Git states, authority violations,
or unrecoverable publication failures may still stop the persistent watcher.

If the watcher process dies after Codex created valid local Executor commits but before the watcher published them, restart recovery is allowed only when the working tree is clean, the local branch is ahead-only of `origin/<branch>`, the remote `CURRENT.json` at `origin/<branch>` still describes exactly one current Executor event, the local `CURRENT.json` has progressed from that event, Executor authority validation passes, workflow validation passes, and any `implementation_commit` handoff is contained in the unpublished commit range. Dirty, diverged, unauthorized, ambiguous, or event-unbound local commits fail closed and are not auto-published. This recovery does not let Codex push directly and does not bypass Planner or Reviewer authority.

Codex exit code 0 alone is not progress. An event that does not move task state is retried only a bounded number of times. Exhausted attempts publish an operational `BLOCKED` plus `FINAL_REPORT.md` rather than retrying forever or discarding local work.

Bounded retry applies only to Executor-owned events that should have produced progress but did not, for example `PLAN_FROZEN -> codex exec -> PLAN_FROZEN`. It does not apply after Executor has successfully handed off to a GPT-owned state such as `READY_FOR_GPT_REVIEW` or `NEEDS_GPT_PLANNER`. In that case a stable repository state is expected while Scheduled GPT has not yet written a fresh decision.

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
App visibility as workflow identity
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

The Scheduled Task uses GitHub as its transaction surface. It reads tracked workflow artifacts, repository state, and GitHub Actions/checks through the GitHub connector; it does not run the target machine's local `ai-bridge` CLI. Local CLI commands remain for the Codex watcher, local debugging, deterministic validation, and human/manual operation.

Every GPT-owned state change follows the same transaction rule:

1. write the model-owned artifact first, such as `PLAN.md`, `REVIEW_<round>.md`, or `FINAL_REPORT.md`;
2. update `automation/reviewed_handoff/tasks/<task_key>/CURRENT.json` last;
3. re-read the final files and self-check the resulting `state`, `review_round`, `plan_revision`, `ci_status`, round limits, and final-report requirements.

The preferred form is a single Git commit containing the complete transaction. If the GitHub connector cannot conveniently modify all files atomically, artifact commit(s) are allowed before the final `CURRENT.json` commit. An artifact-only commit is not a new workflow state. The local watcher continues to use `CURRENT.json` as the routing source of truth and must fail closed after fetch if validation rejects the remote transaction.

It processes only states that explicitly require GPT work, primarily:

```text
NEEDS_GPT_PLANNER
WAITING_FOR_CI
READY_FOR_GPT_REVIEW
PASS
```

No matching task means no side effects and no user notification.

The same scheduled task can perform the one allowed Planner re-entry and the Reviewer role. It must never impersonate Codex Executor. Executor wake-up belongs to the local watcher.

For `WAITING_FOR_CI`, pending/running GitHub checks require strict no-write behavior. CI PASS means the Scheduled Task writes `CURRENT.ci_status=PASS`, `state=READY_FOR_GPT_REVIEW`, and the correct `next_action`, then may continue Reviewer work in the same run. CI FAIL is recorded as a normal `REVISE` review artifact and consumes the same review-round budget as any Reviewer finding: first failure enters `REVISE`; second failure requires `REVIEW_2.md`, `FINAL_REPORT.md`, `review_limit_reached=true`, `human_gate_reason=REVIEW_LIMIT`, and `AWAIT_HUMAN_DECISION`. If CI status is genuinely unavailable because checks, permissions, or GitHub service state cannot be determined, the Scheduled Task must write a final report and route to `BLOCKED`; it must not synthesize PASS.

For `READY_FOR_GPT_REVIEW`, the remote Reviewer writes `REVIEW_<round>.md` before changing state. PASS also writes `FINAL_REPORT.md` and reaches `AWAIT_HUMAN_DECISION` with `human_gate_reason=PASS`; if the current state graph requires an intermediate `PASS` state, the Scheduled Task may use two mechanical `CURRENT.json` transactions. First `REVISE` reaches `REVISE`. Second `REVISE` writes `REVIEW_2.md` and `FINAL_REPORT.md`, sets `review_limit_reached=true`, and reaches the human gate. `BLOCKED` writes `FINAL_REPORT.md` before entering `BLOCKED`.

For `NEEDS_GPT_PLANNER`, the remote Planner reads the task context, makes at most one minimal re-plan, writes `PLAN.md` first, and writes `CURRENT.json` last with `plan_revision += 1` and `state=PLAN_FROZEN`. A second material re-plan requirement, or any required product/scientific decision, writes `FINAL_REPORT.md` first and then routes `CURRENT.json` to `AWAIT_HUMAN_DECISION` with `human_gate_reason=PLANNER_DECISION`.

## Optional Visual Review evidence

Reviewed Handoff may opt into the shared Bridge Kit Visual Review evidence producer. This is not a new role and must not import Agent-Flow machinery into Reviewed Handoff.

Opt-in is task-local via `CURRENT.visual_review_required=true`. The default evidence path is:

```text
results/<task_key>/visual_review/VISUAL_REVIEW.json
```

For non-CI visual tasks, the Executor must publish the rendered visual inputs and `results/<task_key>/visual_review/visual_inputs.json` before entering `READY_FOR_GPT_REVIEW`. The GitHub Actions Visual Review job can then read the already-published inputs and write `VISUAL_REVIEW.json`. Missing `VISUAL_REVIEW.json` with a valid input manifest is normal `waiting_visual_review_evidence`; missing or invalid input manifest is not a valid handoff.

For CI-required visual tasks, the legal order is:

```text
WAITING_FOR_CI
-> CI PASS
-> READY_FOR_GPT_REVIEW
-> waiting_visual_review_evidence
-> fresh visual evidence
-> GPT Reviewer
```

`WAITING_FOR_CI` with a valid `visual_inputs.json` and pending visual evidence is valid and remains owned by CI. `READY_FOR_GPT_REVIEW` with pending visual evidence is also valid, but the owner is Visual Review and the GPT Reviewer must wait without consuming `review_round`. CI failure may route to `REVISE` or non-PASS terminal states without first requiring Terra evidence. `PASS` and `AWAIT_HUMAN_DECISION` with `human_gate_reason=PASS` remain strict: they require current visual PASS evidence.

For Reviewed Handoff, valid visual evidence is bound to:

```text
task_key
implementation_commit
input image SHA-256 values
visual manifest / rubric identity
```

It must not add `request_nonce`, Requirement Ledger, Stable Review Snapshot, `review_target_id`, role receipt graph, Review Bundle hash, Final Critic, or semantic source manifests.

The Scheduled Reviewer must check `VISUAL_REVIEW.json` before writing `REVIEW_<round>.md`. Missing visual evidence means wait for external visual evidence and do not consume `review_round`. Stale evidence whose `implementation_commit` does not match current `CURRENT.implementation_commit` is invalid and cannot support PASS. A model `REVISE` or `BLOCKED` decision is evidence for the existing Reviewer to consume; it does not create a Visual Reviewer role or a new top-level workflow state.

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

New terminal transitions must validate against the current `FINAL_REPORT.md`
template and its required headings. Repository-wide validation may accept a
historical terminal `AI_BRIDGE_REVIEWED_FINAL_REPORT_V1` report with valid
frontmatter, matching `task_key`, legal `final_decision`, and substantive
legacy sections even if its headings predate the current template. This
compatibility path is only for already-terminal historical tasks and may emit a
non-blocking warning; it must not allow empty reports, malformed frontmatter,
or new terminal transitions to bypass the current template.

A Scheduled GPT Planner/Reviewer transaction that will write `PASS`, `BLOCKED`,
`AWAIT_HUMAN_DECISION`, a review-limit human gate, a planner-decision human
gate, or `PASS -> AWAIT_HUMAN_DECISION` must preflight the final report before
the final `CURRENT.json` write. It must re-read
`automation/reviewed_handoff/templates/FINAL_REPORT.md`, treat the runtime
template as the source of truth, write or update
`results/<task_key>/FINAL_REPORT.md`, re-read the written report, and confirm
that all required H2 headings from the current template are present. If the
report does not satisfy the current template, the transaction must fix the
report first and must not publish terminal `CURRENT` state.

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

For `v0.5.1`, the release gate additionally requires:

- Host Policy managed `AGENTS.md` contains the generic external GPT wait policy;
- Reviewed Handoff reports external silence before and after 2 hours as `waiting_external_review`, not `BLOCKED`;
- stale `REVIEW_<n>.md` artifacts are detected by `implementation_commit` mismatch and do not replay old `REVISE`;
- watcher bounded retry behavior remains intact for true Executor no-progress events.
