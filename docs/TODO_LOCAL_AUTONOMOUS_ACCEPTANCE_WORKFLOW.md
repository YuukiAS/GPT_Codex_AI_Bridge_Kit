# TODO — Local Autonomous Acceptance Workflow

Status: NEW / DESIGN CANDIDATE  
Priority: MEDIUM-HIGH — extracted from the Lucerna final-acceptance workflow on 2026-09-28.

## Why this TODO exists

Lucerna exposed a workflow gap between Lite, Reviewed Mode, and Controlled Mode.

The useful pattern was:

```text
GPT freezes the product/acceptance contract once
→ local Codex Executor implements/builds
→ fresh local Codex Reviewer independently exercises the exact native release
→ blocking findings return to Executor
→ rebuild
→ new fresh Reviewer
→ repeat until P0/P1/P2 = 0
→ user sees only the final candidate or a genuine human-only action
```

The important property is that ordinary QA stays local and autonomous after the
initial GPT contract. The workflow must not stop on external GPT Planner/Critic
wait states during normal implementation/review/repair.

This pattern was materially better suited to Lucerna release finishing than
installing Controlled Mode, because the remaining uncertainty was product
quality and native interaction correctness rather than high-risk scientific,
security, migration, or provenance semantics.

## Why this is not Lite

Lite is intentionally minimal:

```text
GPT task
→ Codex execution
→ result
```

It does not provide a required independent fresh-reviewer loop, reviewer-owned
evidence, automatic repair/re-review, or a hard final promotion gate.

The Lucerna pattern needs those guarantees.

## Why this is not Reviewed Mode

Reviewed Mode is centered on an external GPT reviewer:

```text
GPT Planner
→ Codex Executor
→ Scheduled GPT Reviewer
→ optional repair
→ Scheduled GPT Reviewer
→ human
```

That is valuable when independent GPT semantic/product judgment is the point of
the review.

The Lucerna pattern differs:

- GPT should normally enter once to freeze the contract/rubric;
- ordinary review is performed by a fresh local Codex context;
- the Reviewer can directly exercise the native app on the same machine;
- repair/re-review should continue without waiting for Scheduled GPT;
- no external-GPT grace/wait state should interrupt the local QA loop;
- the user should not be promoted to manual QA merely because an external GPT
  review has not arrived.

This is therefore operationally lighter than Reviewed Mode even though its local
native QA can be more thorough for desktop/software acceptance.

It must not claim the same semantic independence as an external GPT reviewer for
open-ended product/scientific judgment. The contract must already be sufficiently
frozen.

## Why this is not Controlled Mode

Controlled Mode is for high-risk work and deliberately adds:

- Planner / Critic / Controller / Verifier / Executor authority separation;
- Project Profile;
- Requirement Ledger;
- semantic source manifests;
- Stable Review Snapshot / review-target binding;
- typed routing and evidence invalidation;
- Final Critic gate;
- external Planner/Critic ownership for judgment states.

Those controls are appropriate when a false pass has high scientific, security,
migration, deployment, or provenance cost.

For bounded software finishing, they can create unnecessary external-role wait
gates and operational friction.

The Lucerna pattern should not require:

- Requirement Ledger machinery;
- Stable Review Snapshot;
- Final Critic;
- external Planner/Critic polling;
- Control role graph;
- Control task state machine.

## Candidate positioning

This looks like a distinct reusable workflow candidate, provisionally:

```text
Local Acceptance / Local Review Loop
```

Exact name and CLI are intentionally **not frozen** in this TODO.

Conceptually it sits between Lite and Reviewed in orchestration weight:

```text
Lite
  lowest ceremony, no mandatory independent reviewer

Local autonomous acceptance candidate
  one GPT contract
  local Executor ↔ fresh local Reviewer repair loop
  native-app/product QA
  no external GPT wait in ordinary loop

Reviewed Mode
  external GPT review rounds
  stronger independent semantic/product review

Controlled Mode
  full high-risk multi-role/provenance control plane
```

This is not necessarily a permanent fourth top-level mode. Before implementation,
decide whether it should become:

1. a first-class workflow; or
2. a reusable independent-local-review layer attached to Lite.

Do not decide that question from Lucerna alone.

## Core semantics worth preserving from the Lucerna reproduction

A future design should preserve these behavioral requirements:

- candidate SHA/release identity is frozen for each review pass;
- Reviewer is a fresh context that did not implement the candidate;
- Reviewer is read-only against production code;
- Reviewer owns its own evidence;
- any production-source repair invalidates the previous review;
- after repair, a new fresh Reviewer reviews the new candidate;
- ordinary P0/P1/P2 defects route automatically back to Executor;
- same defect class recurring should trigger shared-mechanism/root-cause repair,
  not endless local patching;
- native subagent unavailability should have a fresh isolated local Codex
  process/session fallback;
- ordinary review/runtime/tooling problems should not be escalated to the user
  until bounded local fallbacks are exhausted;
- user interruption is reserved for genuine human-only auth/secret/personal
  choice or final subjective acceptance.

## Best-fit tasks

Likely good fits:

- desktop/mobile/web product finishing;
- native UI acceptance;
- release-candidate polishing;
- interaction/copy/visual/state/notification QA;
- bounded implementation where product semantics are already frozen;
- tasks where same-machine interaction evidence is more useful than another
  remote semantic review round.

Likely bad fits:

- scientific-method choices;
- statistical inference semantics;
- security-sensitive migrations;
- production deployment with material blast radius;
- privacy-sensitive external-data decisions;
- irreversible data operations;
- tasks whose main uncertainty is the correctness of the frozen plan itself.

Those should remain Reviewed or Controlled according to risk.

## Key product distinction to keep explicit

Local Reviewer independence is **context/process independence**, not independent
external-model authority.

Do not market this workflow as a substitute for Reviewed Mode when the task
requires an independent GPT semantic judgment.

Its value is different:

> GPT freezes what “good” means once; Codex locally keeps implementing and
> independently checking until the build actually satisfies it.

## Evidence before promotion

Before adding a new public mode/command, collect at least several real consumer
reproductions and compare:

- user interruption count;
- time-to-final-candidate;
- defect escape rate after local Reviewer PASS;
- cases where Reviewed Mode catches semantic defects the local Reviewer misses;
- cases where Controlled Mode adds meaningful safety versus pure ceremony;
- reliability of fresh local Reviewer launch across Windows/macOS/Linux Codex
  environments.

At minimum, validate on more than Lucerna before deciding first-class workflow
status.

## Non-goals for this TODO

Do not yet:

- add a new CLI command;
- change the public three-mode documentation;
- modify Reviewed or Controlled state machines;
- weaken external GPT review semantics;
- add a new watcher/daemon;
- install new project scaffolding;
- claim this is already a supported Bridge Kit workflow.

This TODO records a real workflow gap and the observed successful shape so it can
be evaluated deliberately instead of re-invented inside future product repos.
