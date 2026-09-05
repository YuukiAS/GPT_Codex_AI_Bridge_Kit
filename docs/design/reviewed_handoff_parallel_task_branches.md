# Review: parallel task branches

Status: frozen product decision; branch-aware GPT review can be used now, while first-class task-scoped watcher / branch lifecycle automation remains a runtime follow-up.

## Problem

Review was originally optimized for one active workflow per repository branch. In repositories such as `AI_Skills_Collection`, several independent plugin repairs are often active at the same time. Serializing them on `main` means one task can spend hours waiting for CI or an external GPT Reviewer while an unrelated plugin task is artificially prevented from progressing.

That waiting is not a product requirement. It is an orchestration limitation.

## Product decision

When multiple independent Review workflows are active in the same repository, the default execution topology is **one dedicated branch per workflow**.

Canonical branch name:

```text
reviewed/<task_key>
```

Examples:

```text
reviewed/044_writing_style_deep_research_chinese_replay
reviewed/045_presentations_real_use_regression_hardening
```

The dedicated branch is the task's execution, CI and GPT-review source of truth until an explicit integration step brings the accepted work back to `main`.

Independent task branches may progress concurrently. A task waiting for CI, Planner, Reviewer, visual evidence or user input on one branch must not force unrelated task branches into low-frequency waiting.

## Independence gate

Branch-per-task concurrency applies only when tasks are genuinely independent enough to develop separately.

Usually safe:

- different plugins or clearly separated source areas;
- no shared schema/version/release decision that one task is simultaneously changing;
- no dependency where task B requires task A's unpublished implementation.

Not automatically safe:

- two tasks modifying the same plugin/runtime contract;
- one task changing shared generator/schema/state-machine behavior used by the other;
- release/version operations that must see one integrated repository state;
- tasks whose frozen Plans explicitly depend on each other.

When independence is ambiguous, ask the user / Planner. Do not serialize all workflows by default merely because they share a repository.

## Branch ownership

A dedicated Review branch is task-owned.

- Planner, Executor and Reviewer for that task read/write that branch.
- Scheduled GPT automation must name the branch explicitly and must not silently fall back to `main`.
- CI/check evaluation must use the task branch tip that contains the relevant `CURRENT` state.
- Another task's automation must not write this branch.
- `main` remains the integration baseline, not the live state bus for every concurrent task.

Do not automatically merge a task branch to `main` merely because an Executor finished. Integration happens only after the task's required review/human gate and after conflict/rebase implications are understood.

## Local execution

A local goal working on a dedicated task branch must stay bound to that task and branch. It must not scan another task branch merely because another `CURRENT.json` is executable.

The current generic watcher was originally branch-scoped and can still enumerate multiple executable tasks visible in the same checkout. Therefore branch-per-task is not considered fully automatic until the runtime provides a task-scoped watcher/branch lifecycle path (for example an explicit `--task <task_key>` binding or equivalent narrow wrapper).

Until that runtime follow-up lands:

- explicit task-bound Codex goals may use dedicated branches;
- branch-specific Scheduled GPT review may use dedicated branches;
- do not launch a generic watcher in a way that can accidentally select a different task;
- do not claim first-class automatic parallel watcher support merely because the branches exist.

The required runtime follow-up should be narrow: bind watcher execution/publication to one task + one authorized branch and, if branch creation is automated, use a bounded Bridge-owned helper rather than globally allowing arbitrary Git branch mutation.

## BLOCKED is a last resort

Review must distinguish **needs a decision** from **cannot recover**.

Recoverable cases should not become `BLOCKED` merely to terminate the current process. Examples:

- user must identify the correct local artifact/path;
- user must choose between two branch/integration options;
- a credential or authorization needs confirmation;
- a Planner clarification can resolve a frozen-Plan ambiguity;
- a visual artifact is temporarily unavailable but can be regenerated or located;
- a Host Policy approval/user-input interaction is available;
- another branch has a merge conflict that requires an integration choice.

Routing preference:

1. routine/reversible implementation detail -> Executor resolves it;
2. material frozen-Plan ambiguity -> `NEEDS_GPT_PLANNER`;
3. recoverable user decision in an interactive goal -> use `request_user_input` / ask the user while preserving workflow state;
4. recoverable user decision without an interactive channel -> use the workflow's human-decision route rather than inventing a terminal failure;
5. `BLOCKED` only when there is concrete evidence that normal waiting, Planner re-entry, user input, Host Policy-authorized operation, or bounded recovery cannot resolve the condition.

Every `BLOCKED` must state the observed failure, attempted/available recovery paths, why they cannot work, and the recovery action if one exists.

## Merge / integration

Parallel branches trade waiting for later integration work. That is intentional.

At task acceptance:

- refresh `main`;
- compare the task branch against current `main`;
- if cleanly compatible, integrate through the repository's authorized merge path;
- if there is a semantic conflict, ask Planner/user rather than silently choosing one branch's behavior;
- rerun any integration-sensitive validation required by the repository.

A merge conflict is not automatically a failed task and should not be rewritten as a product `BLOCKED` state.

## Active migration example

`AI_Skills_Collection` tasks 044 and 045 are the first explicit migration case:

```text
reviewed/044_writing_style_deep_research_chinese_replay
reviewed/045_presentations_real_use_regression_hardening
```

They modify different plugin areas and should proceed independently rather than waiting on each other's CI/Reviewer latency. Their Scheduled GPT tasks must remain branch-specific and task-specific.