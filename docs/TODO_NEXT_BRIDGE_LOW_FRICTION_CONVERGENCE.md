# TODO — Next Bridge Low-Friction Operations Convergence

Status: READY FOR PLANNER INTAKE / NOT IMPLEMENTATION AUTHORIZATION  
Priority: HIGH  
Date: 2026-09-23

## User objective

The next Bridge Kit workflow should, as far as one coherent architecture/release
allows, close the current cluster of user-facing operational friction instead of
opening one small workflow per Auto-review incident.

The product goal is simple:

> Auto-review should protect genuinely risky effects without turning ordinary
> development, diagnosis, publication to an already-authorized task branch, or
> long-running progress observation into repeated user interruptions.

The next workflow should prefer removing unnecessary control-plane friction and
custom wrappers over adding new machinery.

## Include in the next workflow if technically coherent

### A. Read-only Host Policy expansion

Source:

`docs/TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md`

Design and validate a broader direct-allow surface for ordinary read-only Git /
GitHub inspection, including the candidate families already recorded there:

- local Git status/diff/log/show/rev-parse/branch-list/remote inspection;
- worktree/list/files/tag inspection;
- `gh auth status` and common `gh ... view/list` forms;
- safe configured-`origin` reachability probes.

The default solution is direct execpolicy allow for demonstrably read-only
command shapes, not one new `ai-bridge` wrapper per command.

Also fix failure semantics so Auto-review refusal of an optional diagnostic does
not by itself become evidence that Git/auth/remote is broken or that the whole
Goal is terminally blocked.

### B. Ordinary push to an already-authorized existing task branch

Source:

`docs/TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md`

Observed real failure:

`git push origin review/01047-clear-writing`

was blocked even though the task branch was already selected/authorized and the
remote branch already existed.

The next workflow should find the smallest safe way to make ordinary non-force
publication to the exact already-authorized task branch low-friction, while
keeping:

- new/unapproved remote branch creation;
- upstream changes;
- force push;
- remote deletion/remap;
- wrong-branch publication

gated.

Do not assume that only `main` is a legitimate low-friction development
branch.

### C. Reviewed branch/worktree materialization and resume

Source:

`docs/TODO_BOUNDED_REVIEWED_WORKTREE_EXECUTION.md`

Two real failures now exist:

1. exact authorized new reviewed branch/worktree creation could still be
   rejected after approval;
2. an existing remote reviewed task whose local worktree disappeared required
   the user to repeat the exact authorization merely to rematerialize the same
   task surface.

Before implementing another helper, test whether current Codex/Host Policy
primitives can legally express the bounded effect directly. Retain a Bridge
helper only if dynamic repo/task/branch/path identity genuinely cannot be
enforced with the native policy surface.

### D. Wrapper minimization / retirement audit

Source:

`docs/TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md`

Inventory current Bridge CLI surfaces and distinguish real product/workflow
commands from permission-bypass wrappers.

Current known Host-Policy-preauthorized wrapper candidate:

`ai-bridge plugin-replay`

Re-evaluate it against current official Codex plugin/Marketplace authoring and
testing flows before retaining it.

Repository history is relevant:

- Bridge briefly implemented `candidate-plugin-replay`;
- it was completely rolled back before release in
  `b6ab9ac74a01eb0a7e96fb0dca38d7c0a8a48e69`;
- AI_Skills later retained repo-local candidate replay tooling;
- subsequent AI_Skills planning explicitly adopted official Codex
  plugin/Marketplace commands and fresh-session boundaries for plugin
  installation/update.

The Planner must determine whether `plugin-replay` still provides a unique,
currently needed capability. If not, plan its deprecation/removal and consumer
migration rather than preserving it because it already exists.

Do not create a wrapper registry, permission-bypass framework, or new
state-machine family.

### E. Persistent Run regular progress / ETA reporting

Source:

`docs/TODO_PERSISTENT_RUN_PROGRESS_ETA_REPORTING.md`

The user explicitly wants this handled soon.

A persistent/overnight run must not leave the user waiting for hours with only
"process/session still alive" evidence.

The next design should provide the smallest reusable way to surface:

- current stage;
- concrete progress since the last report;
- count/fraction when a real denominator exists;
- defensible remaining-time / expected-finish estimate, or `UNKNOWN`;
- ETA uncertainty / material ETA movement;
- last real progress time;
- normal / slow / stalled / blocked interpretation;
- completion/failure.

Progress should be surfaced periodically at a reasonable cadence through an
existing authorized delivery surface when available, not merely retrievable by
manually attaching to tmux. Do not invent fake percentages/ETAs and do not add
automatic intervention/cancellation authority.

This must remain Persistent Run observability, not a fourth workflow, scheduler,
new controller hierarchy, or mandatory notification stack.

## Prefer one workflow, but do not force false coupling

Planner should start from the assumption that A-D are one coherent Host Policy /
low-friction execution refinement and should be handled together if practical.

Persistent Run progress/ETA (E) should also be included in the same next
workflow if doing so does not force a bad shared runtime abstraction. It is
acceptable for one reviewed task/release to contain multiple bounded
implementation phases if they share the same release and regression closure.

Split E into a separately approved immediate follow-up only if the Planner can
show a concrete architecture/recovery/test reason why combining it would create
a worse implementation. Do not split merely because the files live in a
different Bridge module.

## Explicitly out of this next workflow unless new evidence says otherwise

Do not pull these historical/future roadmaps into this usability convergence
merely because they are TODO-like documents:

- `docs/TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md` — design history; current
  Control implementation authority lives elsewhere.
- `docs/PROJECT_STATE_BRIDGE_ROADMAP.md` — future product roadmap, not part of
  the present Auto-review / Persistent Run usability failures.

Do not reopen unrelated Text/Visual Review, Overleaf, Notifier, Control, or
Project State architecture without a direct dependency.

## Planner questions

The next Planner must answer from current source and current official Codex
behavior:

1. Which read-only commands can be directly allowed with narrow execpolicy
   shapes today?
2. Can an already-authorized existing non-main branch push be represented
   directly without broadly allowing arbitrary/new branch publication?
3. Can reviewed branch/worktree bootstrap/rematerialization be performed
   natively after current-user authorization, or is one bounded helper genuinely
   necessary?
4. Does `ai-bridge plugin-replay` still provide unique value over official
   Codex local Marketplace/plugin reinstall/fresh-session testing? If yes, what
   exact value; if no, what is the migration/removal path?
5. What is the smallest truthful Persistent Run progress/ETA contract, cadence
   and delivery mechanism that works without a new orchestration system?
6. What failure/approval semantics prevent Auto-review false positives from
   redirecting a task into false `BLOCKED` or repeated user interaction?
7. Can all accepted changes ship as one Bridge release/workflow without creating
   hidden coupling or an oversized state machine?

## Success criteria for the eventual workflow

The eventual implementation should be judged by normal user behavior, not rule
text alone.

At minimum it should demonstrate:

- a Git/GitHub diagnostic session completes ordinary read-only inspection
  without approval interruptions;
- nearby mutation/dangerous commands remain gated;
- an ordinary push to an already-authorized existing task branch completes
  without a repeated user authorization;
- reviewed task branch/worktree bootstrap/resume no longer repeats the same
  user decision, using native policy if sufficient and a helper only if proven
  necessary;
- retained wrappers have an explicit unique capability and removed wrappers have
  migrated consumers;
- a representative persistent long run surfaces periodic truthful progress and
  remaining-time information without requiring manual tmux inspection;
- no false terminal `BLOCKED` is produced merely because an optional diagnostic
  was denied;
- no generic shell/Python/Git mutation allowlist, danger-full-access, approval
  bypass, wrapper framework, new authorization database, or new workflow class
  is introduced.

## Governance

This document is backlog consolidation only.

Host Policy behavior, wrapper retirement, reviewed worktree mutation semantics,
and Persistent Run reporting are production/workflow changes. The next step is a
Planner proposal followed by independent Critic review before implementation.
