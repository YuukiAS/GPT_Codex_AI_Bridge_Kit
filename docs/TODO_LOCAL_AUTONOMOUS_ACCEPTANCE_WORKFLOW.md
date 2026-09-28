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


## 2026-09-28 naming / product-shape recommendation

After comparing the existing Lite, Reviewed Mode, and Controlled Mode semantics,
the current recommendation is to preserve four distinct workflow levels rather
than folding local autonomous acceptance into Lite or Reviewed.

Provisional **display names**:

```text
Lite
Local Review
GPT Review
Governed
```

Meaning:

- **Lite** — one bounded GPT→Codex handoff; no mandatory independent review loop.
- **Local Review** — GPT freezes the goal/rubric once, then local Codex Executor
  and fresh local Codex Reviewer iterate autonomously until the bounded promotion
  gate passes.
- **GPT Review** — current Reviewed Mode semantics: GPT planning plus an external
  GPT review decision after implementation; preserves stronger independent
  semantic/product judgment.
- **Governed** — current Controlled Mode semantics: full high-risk
  Planner/Critic/Controller/Verifier/Executor authority separation, frozen
  requirements/provenance, and Final Critic closure.

These names are intentionally role/assurance-oriented. Exact CLI command names
and compatibility aliases remain an implementation decision. Existing
`reviewed-handoff` and `agent-flow` commands must remain backward compatible
if display names change.

The strongest reason to keep four levels is that **Local Review and GPT Review
solve different uncertainty**:

- Local Review answers: “Did we actually build and polish the already-frozen
  product correctly?”
- GPT Review answers: “Does an independent GPT agree that the semantics/product
  result are correct?”
- Governed answers: “Can we prove a high-risk task passed under separated
  authority and bound evidence?”

Do not make Lite implicitly launch reviewers; Lite should stay cheap and
predictable.

## ChatGPT Work boundary

Current OpenAI product documentation treats ChatGPT Work and Codex as separate
experiences. Work can operate on local folders in the ChatGPT desktop app when
the user explicitly opens/grants them, but there is currently no documented
supported Codex CLI/harness command that launches a ChatGPT Work conversation.

Therefore a future Local Review workflow must **not depend on Codex launching
GPT Work**.

Preferred Local Review runtime:

1. native fresh Codex subagent/context when supported;
2. fresh isolated local Codex process/session fallback.

ChatGPT Work may be an **optional additional product reviewer** when explicitly
started by the user or when a future supported programmatic handoff exists. It
must not be a required transition in Local Review.

The existing GPT Review workflow may continue to use external GPT transports
(such as Scheduled GPT) independently of Local Review. A future transport
abstraction may support Work, but only after a supported launch/handoff surface
exists.

## Bounded-loop / token-cost requirements

Local Review must never be an unbounded Executor↔Reviewer loop.

Recommended default budgets to validate experimentally:

```text
initial reviewer pass: 1
max repair rounds: 3
max fresh reviewer passes: 4 total
same exact finding allowed after repair: 1 recurrence
same finding class before root-cause escalation: 2 occurrences
root-cause consolidation pass: 1
parallel reviewers by default: 1
```

After budget exhaustion, do not silently keep spending tokens. Produce one
bounded terminal handoff such as `LOCAL_REVIEW_BUDGET_EXHAUSTED` with a compact
finding summary and an explicit next route (typically GPT Review or human
decision depending on task semantics).

Additional cost controls:

- Reviewer reads the frozen goal, current diff/source, exact release and
  task-owned evidence; it should not reread unrelated repository history every
  round.
- No new Reviewer pass when production source/relevant artifact identity did not
  change.
- After a repair, invalidate only evidence affected by the change rather than
  blindly regenerating every expensive artifact.
- Same defect twice should trigger shared-mechanism/root-cause repair instead of
  repeated symptom patches.
- Track reviewer/repair round counts and, when available from the runtime,
  cumulative token usage and wall time.
- Optional soft budgets for cumulative tokens/wall time may warn the Controller;
  a hard loop-count budget remains required even when token accounting is
  unavailable.

These defaults are candidates, not yet released contract. Lucerna and at least
one additional consumer such as Bobbio should be used as real validation before
the workflow is promoted to a stable public mode.


## 2026-09-28 refinement: display name = Pro; progress-bounded loop, not fixed four-pass cap

### Naming

Update the provisional display-name recommendation to:

```text
Lite
Local Review
GPT Review
Pro
```

`Pro` is the display name for the current Controlled Mode / `agent-flow`
workflow. Existing CLI names such as `agent-flow` remain compatibility
interfaces unless a later release deliberately adds aliases.

The four levels then read naturally:

- **Lite** — execute the frozen task.
- **Local Review** — local Executor + fresh local Reviewer until product-quality
  acceptance.
- **GPT Review** — external GPT judgment after implementation.
- **Pro** — full high-risk role/provenance/evidence governance.

### Do not hard-stop only because reviewer pass count reached 4

A fixed `max_reviewer_passes_total=4` is too crude for complex products.

The real safety requirement is:

> continue while each round is making material, auditable progress; stop or
> escalate when review/repair becomes stagnant, repetitive, or cost-inefficient.

Use a **progress-bounded** loop with both soft and hard limits.

Recommended candidate policy:

```text
soft_reviewer_pass_budget = 4
soft_repair_round_budget = 3
hard_reviewer_pass_budget = 8
hard_repair_round_budget = 7
max_consecutive_low_progress_rounds = 2
max_same_mechanism_recurrences_after_repair = 1
max_root_cause_repair_attempts_per_mechanism = 1
parallel_reviewers = 1
```

The soft budget is not a stop condition. Crossing it requires an explicit
`CONTINUE_WITH_PROGRESS` decision backed by progress evidence.

The hard budget is a safety fuse, not the normal stopping criterion. A future
task may override it explicitly when the frozen task itself is unusually large,
but the workflow must never have an unbounded default.

### Meaningful progress

Each Reviewer pass compares the new blocking finding set with the previous pass.

A round counts as **meaningful progress** when at least one of these is true and
no already-repaired blocking mechanism has regressed:

1. one or more prior P0/P1/P2 findings are independently verified closed;
2. aggregate blocking severity decreases;
3. a previously blocked primary user flow becomes independently usable;
4. a shared mechanism repair closes multiple prior findings at once;
5. the new Reviewer reaches materially new acceptance coverage and exposes
   genuinely distinct blocking defects that were not observable before the prior
   repairs.

Finding new defects alone is not enough if the previously known blockers remain
unchanged.

A round is **low progress** when, for example:

- most blocking findings are repeats of the prior round;
- the same user-visible failure remains after a claimed repair;
- only wording/location of the same mechanism changes;
- source changes occur but no prior blocker is independently closed;
- the Reviewer re-reports essentially the same defect packet with different
  phrasing.

Two consecutive low-progress rounds should stop normal symptom repair and route
to root-cause consolidation or an escalation decision.

### Finding identity: exact finding vs finding class vs mechanism

Do not use only free-form prose similarity.

Every blocking finding should carry three identities:

```text
finding_id
finding_class
mechanism_key
```

Definitions:

- `finding_id` — one concrete observed defect on one reviewed candidate.
- `finding_class` — the violated product invariant/category.
- `mechanism_key` — the suspected shared implementation mechanism that should
  be repaired if defects recur.

Recommended compact `finding_class` taxonomy for Local Review:

```text
INTERACTION_ACTION_LIFECYCLE
INTERACTION_NATIVE_SHELL
COPY_PRESENTATION_BOUNDARY
COPY_TERMINOLOGY
VISUAL_COMPONENT_GRAMMAR
VISUAL_LAYOUT_HIERARCHY
STATE_AGGREGATION
STATE_IDENTITY
NOTIFICATION_ELIGIBILITY
NOTIFICATION_INCIDENT_LIFECYCLE
AUTH_SETUP_FLOW
PERSISTENCE_RESUME
PACKAGING_RELEASE_IDENTITY
OTHER_PRODUCT_INVARIANT
```

This taxonomy is intentionally about violated invariants, not specific screens.

Examples:

```text
"Needs sign-in + Sync now" on Overleaf
→ finding_class = INTERACTION_ACTION_LIFECYCLE
→ mechanism_key = overleaf-action-from-status

"Repair" button visible with no available repair
→ finding_class = INTERACTION_ACTION_LIFECYCLE
→ mechanism_key = action-visibility-from-capability

five cards leaking backend detail strings
→ finding_class = COPY_PRESENTATION_BOUNDARY
→ mechanism_key = normal-ui-consumes-backend-detail

Longleaf says Unavailable while a primary route is Ready
→ finding_class = STATE_AGGREGATION
→ mechanism_key = longleaf-top-level-availability-aggregation

same notification reappears because a value/error string changed
→ finding_class = NOTIFICATION_INCIDENT_LIFECYCLE
→ mechanism_key = notification-semantic-incident-identity
```

### When to force root-cause repair

The Orchestrator should require `ROOT_CAUSE_REPAIR_REQUIRED` when any of these
conditions is met:

1. the same `mechanism_key` produces a blocking finding after one repair that
   claimed to address that mechanism;
2. two or more findings in one pass share the same `mechanism_key`;
3. the same `finding_class` appears in two consecutive review passes on
   different surfaces and the evidence suggests one shared implementation path;
4. a repair closes one symptom but creates another blocking symptom through the
   same component/presentation/state mechanism;
5. two consecutive rounds are low-progress.

The root-cause repair packet must include:

```text
mechanism_key
affected_findings[]
affected_surfaces[]
violated_invariant
evidence
previous_repairs[]
required_mechanism_level_regression
```

After a root-cause repair, the next fresh Reviewer must explicitly test both:

- the original concrete finding(s);
- a sibling/adjacent state that exercises the same mechanism.

This is how Codex is told to stop patching symptoms.

### Continue/stop decision after soft budget

After the soft reviewer budget is reached, the Orchestrator may continue only if:

```text
MEANINGFUL_PROGRESS=YES
NO_UNRESOLVED_RECURRENCE=YES
NEXT_REVIEW_HAS_NEW_VALUE=YES
WITHIN_HARD_BUDGET=YES
```

Otherwise stop with a bounded terminal state such as:

`LOCAL_REVIEW_STAGNATED` or `LOCAL_REVIEW_BUDGET_EXHAUSTED`.

For a complex product, distinct defects that keep getting fixed are therefore
allowed to continue past four reviews. The loop stops because progress has
stalled or the hard safety fuse is reached, not merely because the project was
complex.
