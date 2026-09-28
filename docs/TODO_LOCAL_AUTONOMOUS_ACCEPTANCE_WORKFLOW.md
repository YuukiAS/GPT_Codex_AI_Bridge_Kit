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


## 2026-09-28 Lucerna 12-hour run: orchestration-efficiency lessons

Lucerna's first long Local Review-style closure run exposed a second requirement:
the workflow must optimize **time-to-next-useful-review**, not merely guarantee
fresh-reviewer independence.

Observed auditable intervals from the Lucerna run:

- first broad reviewer evidence window: ~26m;
- Locke reviewer: ~1h19m;
- Aristotle reviewer: ~17m;
- Dalton reviewer: ~9m;
- post-Dalton producer native-smoke repair loop: ~39m on one repeated close/
  capture/readiness mechanism;
- Carver produced failing readiness artifacts within ~1m and additional black
  captures within ~7m, but the orchestrator waited longer before terminating
  the pass;
- the full 12-hour wall-clock run also contains earlier multi-hour spans whose
  exact command-level attribution was not yet available in tracked evidence.

This run shows that reviewer-count limits alone are insufficient. A Local Review
implementation should also track **stage time**, **evidence reuse**, and
**artifact heartbeat**.

### Required future efficiency controls

1. **Cheap producer preflight before a fresh Reviewer**

   Do not spend a fresh Reviewer pass on a candidate that already fails a cheap,
   deterministic prerequisite such as:

   - frontend/DOM readiness;
   - valid non-black capture;
   - native interaction smoke;
   - exact release identity;
   - required local fixture readiness.

   These are producer/preflight gates. A Reviewer should receive a candidate
   only after the cheap prerequisite evidence is green.

2. **Reviewer artifact heartbeat / fail-fast**

   While a Reviewer is running, the orchestrator should watch reviewer-owned
   artifact/event progress.

   If a blocking prerequisite failure is already conclusive, for example:

   ```text
   DOM_NOT_READY
   INVALID_CAPTURE
   RELEASE_IDENTITY_MISMATCH
   NATIVE_INTERACTION_PREREQUISITE_FAIL
   ```

   do not let the Reviewer continue collecting low-value downstream screenshots
   or wait idle for a final prose report. Stop the pass, materialize the finding,
   and route repair immediately.

3. **Evidence dependency graph, not full rerun by default**

   Model acceptance evidence in coarse reusable domains, for example:

   ```text
   build/release identity
   native shell/readiness
   interaction behavior
   state semantics
   copy
   visual composition
   notification behavior
   packaging
   ```

   After a repair, invalidate only domains affected by the changed source/
   mechanism plus dependent gates. Do not automatically regenerate every
   screenshot, notification soak, and packaging artifact when the change cannot
   affect them.

   Fresh Reviewer judgment is still required on the new candidate, but it may
   reuse independently validated unchanged-domain evidence after checking its
   candidate/source binding and invalidation rules.

4. **Mechanism-level repair before repeated native-smoke iterations**

   Multiple consecutive repairs to the same mechanism should switch from
   symptom-level iteration to a diagnostic/root-cause phase before another full
   Reviewer is launched.

   Lucerna's close/capture sequence progressed through readiness, window
   geometry, WebView geometry, and DOM click geometry before converging. Future
   orchestration should classify these as one
   `native-panel-readiness-and-hit-target` mechanism early and demand one
   bounded diagnostic packet before repeated rebuild/review.

5. **Separate diagnostic loop from release-review loop**

   Reviewer should identify a product defect. Once a low-level mechanism is
   known broken, the Producer may run bounded targeted diagnostic/repair loops
   without consuming fresh full Reviewer passes.

   Only return to a fresh Reviewer after the mechanism-specific producer gate is
   stable.

6. **Build/release caching with correctness binding**

   Avoid full packaging rebuilds when only a reviewer artifact or non-packaging
   evidence changes.

   Rebuild exact release when implementation/frontend assets affecting the
   executable change. Rebuild installers only when packaging inputs changed or
   final release identity requires it.

   Cache must always be bound to source/input digests; never reuse stale binaries
   for convenience.

7. **Stage wall-time accounting**

   Persist per-task timing at least for:

   ```text
   producer_analysis
   targeted_tests
   full_tests
   frontend_build
   tauri_release_build
   packaging
   native_smoke
   visual_capture
   reviewer_wait
   reviewer_active
   publisher
   idle/wait
   ```

   This is needed to distinguish expensive but useful validation from accidental
   idle time or repeated evidence generation.

8. **Low-value reviewer detection**

   A reviewer pass is low-value when it spends material wall time after a
   conclusive prerequisite blocker is already known, repeats unchanged evidence,
   or produces no new finding/closure/coverage.

   Two such passes in one task should force orchestrator-policy review before
   continuing.

9. **Canonical hardened acceptance primitives**

   Once a mechanism is fixed generically, preserve it as a reusable tested
   primitive rather than rediscovering it in future projects/runs.

   Candidate primitives include:

   - reliable frontend-mounted readiness handshake;
   - non-black/valid native capture preflight;
   - exact DOM-to-screen hit-target mapping for native UI smoke;
   - titlebar close/Esc/tray reopen smoke;
   - stable reviewer artifact heartbeat;
   - incremental acceptance invalidation.

   This is the main anti-regression lesson: expensive acceptance knowledge should
   become workflow/tooling infrastructure, not remain one-off repair history.

### Promotion implication

Before Local Review is promoted to a stable Bridge Kit workflow, benchmark not
only defect escape rate but also:

- median wall time per useful reviewer pass;
- percentage of reviewer time spent after a conclusive blocker was already
  observable;
- rebuild/package time per repair;
- reused vs regenerated acceptance domains;
- repeated-mechanism repair count;
- time from reviewer blocker evidence to Producer repair start;
- cumulative Codex token use per closed P0/P1/P2 finding.

The workflow should be considered successful only if independence improves
quality **without turning acceptance into an hours-long serial evidence loop**.


## 2026-09-29 requirement: Local Review must self-harden without user/GPT intervention

Lucerna's cost attribution is now sufficient to freeze one additional core
requirement: Local Review must not merely iterate on the product. It must also
**turn recurring review/evidence friction into reusable, tested local
infrastructure during the run**.

The workflow is not successful if every fresh Reviewer rediscovers how to:

- launch the exact native release;
- wait for the real frontend-ready condition;
- obtain a valid non-black screenshot;
- map DOM control geometry to screen coordinates;
- click native controls reliably;
- prove close/Esc/tray-reopen behavior;
- collect notification evidence;
- bind evidence to the exact candidate;
- distinguish product failure from review-harness failure.

### Review-infrastructure finding class

Add an explicit non-product finding category:

`REVIEW_INFRA_GAP`

Examples:

- screenshot helper produces black frames;
- DOM probe runs before frontend mount;
- native hit-target coordinates are unreliable;
- reviewer cannot tell whether the exact release is running;
- the same evidence requires ad-hoc shell reconstruction every pass;
- a capture/native-smoke helper fails nondeterministically.

A `REVIEW_INFRA_GAP` must not be reported to the user as a product defect.

It routes to the local Executor/Orchestrator for tooling hardening.

### Automatic tooling-hardening trigger

Enter `TOOLING_HARDENING_REQUIRED` when any of the following is true:

1. the same evidence-collection action fails twice in one task;
2. two fresh Reviewers need materially the same ad-hoc workaround;
3. a Reviewer pass fails before reaching product judgment because of harness/
   capture/readiness/tooling;
4. more than one manual shell sequence is used to produce the same evidence
   shape;
5. a review-infrastructure mechanism consumes more wall time than the configured
   threshold without producing new product coverage.

This is an internal Local Review transition, not a human/GPT escalation.

### Harden once, reuse afterwards

The hardening loop is:

```text
review infrastructure failure
→ classify REVIEW_INFRA_GAP
→ identify mechanism_key
→ implement/repair one reusable helper
→ add deterministic regression test
→ register capability
→ run cheap capability preflight
→ only then launch a fresh Reviewer
```

Do not repeatedly paste new PowerShell/Python/shell snippets into Reviewer
prompts for the same job.

If a script/helper already exists, repair it in place and strengthen its tests
instead of creating `capture-v2`, `capture-final`, `capture-final2`, etc.

### Project-local capability registry

Local Review should install a small tracked capability registry, with a shape
similar to:

```text
automation/local_review/
  CAPABILITIES.json
  tools/
  fixtures/
  tasks/
```

Exact paths remain an implementation decision, but the registry should record
for each hardened primitive:

```text
capability_id
purpose
platform
entrypoint
inputs
outputs
preconditions
success_contract
regression_test
source_digest
last_validated_candidate
reusable_across_tasks
```

This allows the next Reviewer to ask for a semantic capability such as
`native_panel_capture` or `tray_close_escape_smoke`, rather than reinventing
the command sequence.

Machine-local paths/PIDs/session IDs remain outside Git.

### Script/tool ownership rule

When a repeatable evidence operation is needed, the workflow itself must decide
whether to codify it.

Default rule:

- first one-off diagnostic may remain ad hoc;
- second use of the same operation in the same task must use or create a script/
  helper;
- any operation required by the final acceptance contract must have a stable
  entrypoint before the final Reviewer PASS.

Examples:

- native screenshot capture;
- panel readiness probe;
- button hit-target smoke;
- notification-log snapshot;
- release identity check;
- reviewer artifact heartbeat.

This directly addresses the Lucerna failure mode where screenshot/native-smoke
knowledge was rediscovered over several hours.

### Capability preflight before Reviewer launch

Before each fresh Reviewer, the Orchestrator runs a cheap local preflight over
the capabilities required by that review.

Example:

```text
exact_release_identity=PASS
frontend_ready_probe=PASS
native_panel_capture=PASS
capture_non_black=PASS
tray_close_escape_smoke=PASS
reviewer_output_path=PASS
```

If a capability preflight fails, do not spend a Reviewer pass.

Repair/harden the capability locally first.

### Reviewer prompts consume capabilities, not plumbing

Reviewer instructions should specify **what evidence to obtain**, not how to
rebuild low-level tooling.

Bad:

```text
run this 40-line PowerShell snippet, then inspect HWND coordinates...
```

Good:

```text
use capability native_panel_capture
use capability tray_close_escape_smoke
review the resulting evidence independently
```

The implementation behind the capability remains testable and replaceable.

### Automatic reuse and invalidation

A hardened capability may be reused across Reviewer passes when:

- its source digest is unchanged;
- its own regression test still passes;
- its preconditions still hold;
- candidate changes do not invalidate the capability itself.

Product evidence generated by the capability is still candidate-bound and must
follow normal evidence invalidation rules.

This separates:

- **tool validity** — may persist across candidates;
- **product evidence** — usually bound to one candidate.

### Self-observability is mandatory

Local Review must write its own lightweight orchestration telemetry while it
runs. Do not wait until a 12-hour incident to reconstruct it from mtimes.

At minimum emit append-only events for:

```text
stage_start
stage_end
reviewer_spawn
reviewer_heartbeat
reviewer_first_useful_evidence
reviewer_conclusive_blocker
reviewer_shutdown
repair_start
repair_end
build_start
build_end
capability_preflight
infra_gap_detected
root_cause_mode_entered
candidate_frozen
candidate_invalidated
```

Each event should include timestamp, task key, candidate identity, stage,
mechanism/finding identity where applicable, and bounded token/runtime metrics
when available.

### No silent one-hour gaps

A Local Review run must not have unobserved hour-long gaps by design.

Use stage-specific heartbeat/deadline semantics:

- no useful Reviewer artifact/heartbeat for a bounded interval -> inspect/
  restart the Reviewer locally;
- conclusive blocker observed -> stop downstream Reviewer work immediately;
- build/test subprocess with no progress -> inspect process state before waiting
  indefinitely;
- unknown wait reason -> persist the reason/state instead of silently sleeping.

Exact timeouts should be calibrated empirically and may vary by stage. Avoid one
universal short timeout that kills legitimate builds.

### Learning artifact after every costly mechanism

When a mechanism consumes material repair time or more than one attempt, Local
Review should automatically write a compact machine-readable learning record:

```text
mechanism_key
symptoms
root_cause
hardened_capability
regression_test
affected_surfaces
reusable_scope
future_preflight
time_spent
tokens_spent_if_known
```

If the lesson is consumer-specific, keep it in the consumer repository.

If it is generic across projects, mark:

`BRIDGE_PROMOTION_CANDIDATE=true`

and emit a structured promotion artifact for later Bridge Kit maintenance.
Do not require the user or GPT to manually notice that the same infrastructure
problem has happened repeatedly.

### Autonomy requirement

For Local Review normal operation, neither the user nor external GPT is required
between the frozen initial goal and final acceptance.

The local Orchestrator owns:

- evidence-tool preparation;
- capability hardening;
- Reviewer restart/fallback;
- product repair routing;
- root-cause escalation;
- incremental invalidation;
- timing/heartbeat accounting;
- final bounded promotion decision.

User/GPT involvement remains reserved for the already-defined semantic/human
boundaries, not for ordinary review infrastructure.

This autonomy requirement is a promotion gate for Local Review, not optional
polish.
