# TODO — Reusable Agent-Flow v3 Blueprint

Status: **CARE gate complete / design history retained**

The CARE stress test has reached implementation-fidelity closure and the final
Planner/Critic gate. This older blueprint is retained as design history, but
implementation readiness and current scope now live in:

```text
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
```

Do not replace Lite Handoff. Reusable Agent-Flow is now an explicit opt-in
control-plane layer for high-risk repositories.

The purpose of this TODO is to preserve the architecture, role boundaries,
anti-overengineering lessons, and portability requirements learned from the
CARE run before those details are forgotten or re-invented differently in the
next project.

---

## 1. Why this exists

The future Bridge Kit should support two very different workloads without
forcing every repository through the same amount of ceremony.

### Goal A — reliable high-risk implementation

For scientific, architecture-changing, long-running, deployment-sensitive, or
otherwise high-risk tasks, the system should be able to take a user-approved
objective and drive it through planning, independent contract audit,
implementation, independent verification, repair, final audit, and a final
human gate with minimal manual supervision.

### Goal B — preserve the existing lightweight handoff

Low-risk work should remain simple. A small documentation change, ordinary
refactor, formatting change, simple utility, low-risk UI edit, or similar task
should not be forced through Critic + Verifier + persistent sessions + heavy
runtime evidence.

The Bridge Kit should therefore support at least two modes:

```text
Lite Handoff
Planner -> Codex -> result -> optional GPT review

Agent-Flow
Planner
-> Initial Critic
-> Controller
-> Verifier
-> Executor
-> Planner repair loop
-> Final Critic
-> Planner final PASS
-> Human gate
```

A future risk policy may add intermediate profiles, but the core rule is:
**proof burden must be proportional to task risk**.

---

## 2. Primary lesson from the CARE stress test

CARE demonstrated that strict scientific verification is valuable, but it also
showed that strict verification can be confused with excessive orchestration
bookkeeping.

The reusable design must preserve:

- faithful implementation against an explicit contract;
- independent Verifier authority;
- real executable tests rather than receipt-only claims;
- anti-test-awareness protections for the Executor;
- Planner implementation review;
- Critic independent contract audit;
- fail-closed behavior against false PASS;
- exact role separation for high-risk tasks;
- a genuine human gate for scientific/product decisions.

The reusable design must **not** preserve unnecessary complexity such as:

- moving targets caused by every Controller merge commit;
- requiring every receipt commit to become a new implementation identity;
- hash cycles between implementation fingerprints and runtime bundles;
- re-running expensive verification after receipt-only or state-only changes;
- large manifests containing every historical smoke artifact;
- treating every conservative uncertainty as a new blocker;
- treating fail-closed as "stop the entire goal immediately";
- adding provenance fields that no downstream decision actually consumes.

A specific design risk observed during the CARE run is over-defensive
implementation behavior: when a strong reasoning model is asked to make a
process "safe", it may keep adding hashes, immutable receipts, repeated gates,
and defensive checks until the orchestration layer becomes more complex than
the task itself. This has been particularly noticeable in the current GPT-5.6
planning/critique loop. The reusable system must constrain this tendency by
policy and tests rather than relying on the model to self-limit.

---

## 3. Non-negotiable simplicity principles

These principles should become part of the future Bridge Kit core.

### 3.1 Scientific verification can be strict; orchestration should be simple

Do not weaken domain fidelity to make the workflow fast. Instead, remove
redundant bookkeeping around the fidelity checks.

### 3.2 Bind evidence to stable content, not moving Git history

Git SHAs are useful locators and provenance metadata. They should not make the
review identity move every time the Controller writes a receipt or merges a
role commit.

### 3.3 Evidence provenance must be a DAG, never a hash cycle

Allowed:

```text
Contract
-> Source Snapshot
-> Runtime / Verifier / CI Evidence
-> Review Bundle
-> Planner
```

Forbidden:

```text
implementation fingerprint
-> hashes runtime bundle
-> runtime bundle embeds implementation fingerprint
```

No artifact may require a mathematical self-hash fixed point.

### 3.4 Receipt-only changes must not invalidate expensive execution

Changing `CURRENT.json`, a Controller routing receipt, a human-readable report,
or a manifest wrapper must not automatically re-run the model or the full
Verifier.

### 3.5 Heavy verification runs only when semantic inputs change

Default invalidation policy:

```text
IMPLEMENTATION_SOURCE_CHANGED
-> runtime probes + heavy Verifier + CI

VERIFIER_SOURCE_CHANGED
-> Verifier tests/mutations
-> rerun only runtime probes required by the changed oracle
-> CI if repository-safe source changed

CI_WORKFLOW_CHANGED
-> CI only

RECEIPT_OR_MANIFEST_ONLY_CHANGED
-> lightweight bundle validation only

CURRENT_OR_ROUTING_ONLY_CHANGED
-> no heavy Verifier
-> no model/runtime probe

DOC_ONLY_CHANGED
-> no scientific evidence invalidation
```

The Controller must classify the change and choose the minimum sufficient
re-run set. "For safety, rerun everything" is not an acceptable default.

### 3.6 Fail-closed prevents false PASS; it does not require maximal re-execution

A recoverable task-local error should route to the owning role and continue.
Fail-closed is an evidence rule, not a reason to turn every defect into a human
block or a full workflow restart.

### 3.7 Every gate must justify its cost

Every blocking gate should have:

```text
owner
source requirement
failure classification
repair route
expected runtime cost
why a cheaper check is insufficient
```

If a gate cannot explain why it is necessary, it should be diagnostic rather
than blocking.

### 3.8 Minimize hashes

Use hashes only where they prevent a concrete false-PASS/provenance failure.
The default should be a small number of stable identities, not one SHA field per
artifact per state transition.

Suggested minimum identities for high-risk Agent-Flow:

```text
frozen_contract_hash
requirement_ledger_hash
review_target_id
review_bundle_hash
```

Git commit SHAs remain recorded as locators, but they should not all become
independent blocking identities.

---

## 4. Stable Review Snapshot — replace the over-strict immutable transaction

The future generic design should use a **Stable Review Snapshot** rather than a
large moving "immutable transaction" bound to every intermediate commit.

### 4.1 Stable review target

Create one `review_target_id` from semantic content only:

```text
request/task identity
+ frozen contract hash
+ requirement ledger hash
+ implementation critical-source digest
+ verifier critical-source digest
```

The following must **not** change `review_target_id`:

- Controller merge commit;
- CURRENT/state commit;
- receipt commit;
- manifest commit;
- CI receipt commit;
- notifier/report commit;
- documentation-only commit.

Only semantic changes to implementation, Verifier, contract, or requirement
ledger should invalidate the target.

### 4.2 Minimal Review Bundle

Do not make one global runtime manifest contain every historical smoke and
session artifact.

Keep historical receipts for audit/history, but the current Planner review
should receive a minimal `REVIEW_BUNDLE.json` containing only evidence relevant
to the current target, for example:

```text
review_target_id
frozen contract / requirement ledger refs
current runtime evidence required by the contract
current checkpoint/resume evidence when required
current inference/deployment/evaluator evidence when required
heavy Verifier PASS receipt
CI PASS receipt
```

Historical visual smoke, session smoke, watcher smoke, old final states, and
superseded role receipts belong in history, not in the active blocking bundle.

### 4.3 Default expensive-path budget

For one semantic implementation revision, the normal target should be at most:

```text
one necessary heavy Verifier pass
+ one hosted CI pass
+ one lightweight Review Bundle validation
```

A second heavy Verifier pass requires an explicit semantic reason. Post-CI
receipt binding alone is not enough.

---

## 5. Role authority blueprint

Role boundaries must be defined by **decision authority**, not only by file
write scope.

### 5.1 Planner

Planner is the task/scientific/product intent owner and implementation reviewer.

Planner owns:

- understanding the user objective;
- reading project-specific evidence and context;
- authoring the initial contract;
- deciding what constitutes success/failure;
- implementation review against the frozen contract;
- interpreting disputes between Verifier and Executor;
- deciding whether a finding is implementation, verification, contract, or
  scientific/product choice;
- issuing repair findings;
- issuing `PLANNER_PASS_CANDIDATE`;
- final `PLANNER_PASS` after the final Critic audit.

Planner must not:

- implement production code;
- edit Verifier source;
- perform Controller routing mechanics;
- invent provenance complexity without a concrete failure mode;
- turn ordinary implementation bugs into user decisions.

### 5.2 Critic

Critic is the independent contract-quality auditor, not a second implementation
reviewer.

Critic works at exactly three logical moments:

1. **Initial contract audit — required**
   - independently inspect the task and project evidence;
   - repair omissions/ambiguity;
   - challenge unnecessary complexity;
   - freeze the contract;
   - freeze the Requirement Ledger.

2. **Contract review — conditional**
   - only when Planner identifies a real contract ambiguity, contradiction, or
     missing scientific/product requirement that cannot be resolved as an
     implementation bug;
   - deterministic clarification should be repaired directly;
   - only genuinely meaningful alternatives go to the user.

3. **Final audit — required**
   - after Planner produces `PLANNER_PASS_CANDIDATE`;
   - verify that the contract was not silently weakened;
   - verify that Verifier did not expand its authority;
   - verify all blocking requirements have closure evidence;
   - verify the final review snapshot is coherent;
   - return final-pass or revision/contract-review routing.

During ordinary implementation repairs Critic is `STANDBY` and must perform no
writes.

Critic must not be inserted into every code-repair loop merely because a
conservative process "feels safer".

### 5.3 Controller

Controller should intentionally be the least scientifically intelligent role.
It is the orchestration/state owner.

Controller owns:

- start/resume of roles;
- role/session isolation;
- deterministic routing from typed findings;
- integration of role commits;
- CI invocation;
- minimal evidence/bundle construction;
- retry/state bookkeeping;
- notifier trigger at true terminal states.

Controller must not:

- interpret scientific/product semantics;
- invent requirements or thresholds;
- edit implementation;
- edit Verifier oracle source;
- convert a Verifier failure directly into a human scientific choice;
- require more provenance than the active protocol defines;
- create new moving targets because it made another bookkeeping commit.

The ideal Controller behavior is:

```text
read typed state
-> look up routing table
-> execute minimum required transition
```

### 5.4 Verifier

Verifier is the contract-conformance oracle builder.

Verifier owns:

- tests;
- known-bads;
- mutations;
- independent executable probes;
- verification receipts;
- diagnostics.

Verifier may make tests stronger, but cannot expand the contract.

Every blocking Verifier finding should cite the requirement it verifies. If no
frozen requirement supports the finding, it must be diagnostic or sent to
Planner for contract interpretation.

Verifier must not:

- invent a blocking numeric threshold because it appears conservative;
- convert a diagnostic anomaly into failure without requirement authority;
- change implementation;
- require the Executor to implement test-specific behavior;
- repeatedly execute heavy verification after receipt-only changes.

### 5.5 Executor

Executor is the implementation owner.

Executor owns:

- production implementation;
- authorized runtime commands;
- implementation-specific runtime evidence;
- repairs requested by Planner/Verifier through the Controller.

Executor must not:

- change the contract;
- change Verifier source;
- weaken tests;
- detect test/verifier mode and alter normal behavior;
- create synthetic effects solely to satisfy interventions;
- manufacture receipts instead of executing the claimed path;
- decide the final PASS.

For high-risk Agent-Flow, Controller / Verifier / Executor should remain distinct
persistent sessions. Short-lived subagents are acceptable only for read-only
mapping/search or in Lite mode where the risk policy explicitly allows it.

---

## 6. Requirement Ledger

High-risk mode should retain a compact Requirement Ledger because it solved a
real CARE failure mode: Verifier creating requirements that did not exist in
the contract.

Each blocking requirement should include only information necessary for
routing and verification, for example:

```text
requirement_id
source clause
requirement type
blocking yes/no
owner
allowed verifier semantics
numeric threshold only when source exists
change_requires_contract_review
```

Do not turn the ledger into a second full copy of the contract.

---

## 7. Finding classification and routing

The generic core should use typed findings rather than free-text `BLOCKED`.
A compact set is enough:

```text
IMPLEMENTATION_BUG -> Executor
VERIFIER_BUG -> Verifier
VERIFIER_CONTRACT_DRIFT -> Planner adjudication + Verifier
EVIDENCE_GAP -> owning role
PROVENANCE_BINDING_GAP -> Controller
OPERATIONAL_FAILURE -> Controller same-scope recovery
RUNTIME_ENVIRONMENT_FAILURE -> Controller/runtime repair
CONTRACT_AMBIGUITY -> Planner -> Critic when needed
CONTRACT_CONTRADICTION -> Planner -> Critic
DIAGNOSTIC_ANOMALY -> Planner diagnostic review
SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED -> user
```

Human escalation must be exceptional. Runtime, CI, receipt, session, rollout,
Verifier bugs, implementation bugs, and provenance bookkeeping are not human
scientific/product decisions.

---

## 8. Simplified lifecycle

### 8.1 Initial phase

```text
User objective
-> Planner contract
-> Initial Critic audit/freeze
-> Controller
-> Verifier definition
-> Executor implementation
```

### 8.2 Normal repair loop

```text
Executor/Verifier result
-> minimum required heavy checks
-> CI
-> lightweight Review Bundle validation
-> Planner review
-> typed repair
-> owning role
-> repeat
```

Critic stays in `STANDBY` during ordinary implementation repair.

### 8.3 Contract problem

```text
Planner detects contract ambiguity/contradiction
-> Critic contract review
-> deterministic re-freeze
-> resume implementation loop
```

Only genuinely unresolved scientific/product alternatives go to the user.

### 8.4 Final phase

```text
Planner: PLANNER_PASS_CANDIDATE
-> Final Critic audit
-> if pass: Planner final PLANNER_PASS
-> Controller terminal bookkeeping/notifier
-> Human gate
```

Controller must never fabricate Planner or Critic decisions.

---

## 9. Risk profiles

The future Bridge Kit should not make Agent-Flow mandatory for every task.
Suggested direction:

### Lite

Use for ordinary low-risk work.

```text
Planner -> Executor -> result -> optional review
```

No persistent Controller/Verifier/Critic required by default.

### Standard

Possible future profile for medium-risk implementation:

```text
Planner -> Controller -> Executor -> tests/CI -> Planner
```

Critic/Verifier enabled only by policy triggers.

### High-risk Agent-Flow

Use for:

- scientific architecture implementation;
- safety/data-sensitive logic;
- expensive training/compute;
- production deployment;
- migrations with substantial state risk;
- tasks where false PASS is expensive.

Use the full role graph and Requirement Ledger, but still follow the minimal
re-execution rules above.

The eventual `ai-bridge init` should support a mode/profile selector rather
than copying the heaviest protocol into every repository.

---

## 10. Project Profile — what changes between repositories

The Agent-Flow Core should be domain-neutral. A new repository should provide a
small Project Profile rather than redefine every role.

Suggested project-specific inputs:

```text
project objective / product or research context
bootstrap files and repository truth sources
scientific/product contract sources
visual sources when needed
critical implementation paths
runtime environment/bindings
data/external-service boundaries
project-specific verifier adapters/tests
training/deployment authorization policy
human decision boundaries
notification policy
```

Planner / Critic / Controller / Verifier / Executor role definitions stay
constant. Only project knowledge and verification adapters change.

This is the intended portability model for future repositories such as
SeminarArc, CUHK-Date, and other research/software projects.

---

## 11. Scheduled Planner and Critic

Future ChatGPT Scheduled Tasks should use stable control-plane prompts that read
the latest repository schema and role prompt on every run.

Do not permanently hard-code a narrow state list in the ChatGPT control-plane
prompt.

Long-term intended behavior:

```text
Planner Scheduled Task = enabled
Critic Scheduled Task = enabled
```

Both remain enabled. GitHub state decides whether they actually work.

Critic runs only when its mode is:

```text
REQUIRED_INITIAL
REQUIRED_CONTRACT_REVIEW
REQUIRED_FINAL_AUDIT
```

When `STANDBY`, Critic exits with no writes and no notification.

Users should not manually pause/resume Critic every implementation round.

---

## 12. Reusable notifier

Bridge Kit v0.3.0 introduces Generic Notifier support while keeping Agent-Flow
v3 itself in design-only status.

Confirmed v0.3.0 notifier direction:

```text
one-shot terminal hook is the default
tmux is not a dependency
polling run is optional compatibility
rclone machine bootstrap is user-managed
private sync is pull-only
real email send-test is the NOTIFIER_READY gate
```

Default terminal hook:

```text
Goal / Controller terminal state
-> results/<task_key>/notification_brief.json
-> ai-bridge notifier send results/<task_key>/notification_brief.json
```

Supported CLI:

```text
ai-bridge notifier send <brief_path>
ai-bridge notifier send-test
ai-bridge notifier once
ai-bridge notifier run
ai-bridge notifier status
```

`ai-bridge notifier run` is optional long-running polling mode. It must not be
treated as the default installation path, and Bridge Kit must not require tmux,
daemon, systemd, or a process supervisor.

Project configuration should define terminal/notifiable states through explicit
`notification_brief.json` files. Nonterminal states such as normal repair, CI
running, waiting for Planner/Critic, or role `STANDBY` should not create terminal
notifications.

Secrets and recipient details belong in user-local config/environment, not in
project repositories.

Do not copy CARE-specific route watchboard, route_A/B/C, Slurm mandatory fields,
runtime-home discovery, worktree assumptions, immutable notification
transactions, moving SHAs, large manifests, or multi-receipt hash coupling into
the generic notifier core.

---

## 13. Shared Codex configuration

The Bridge Kit should eventually support a reusable user-level Codex profile so
projects do not repeat low-risk permission and feature configuration.

Planned direction includes:

```toml
[features]
memories = true
```

The desired `default_mode_request_user_input = true` behavior should also be
supported if the installed Codex version exposes that setting; implementation
must verify the real supported config key rather than assuming an undocumented
field.

Common low-risk operations should be allowlisted centrally where appropriate.
High-risk actions must remain gated by risk profile and explicit project/user
policy.

Do not solve approval fatigue by globally disabling all approvals.

---

## 14. Generic anti-overengineering tests

The reusable implementation should include project-agnostic regression tests for
workflow complexity itself.

At minimum:

1. Receipt-only change does not trigger heavy Verifier.
2. State-only change does not trigger model/runtime probes.
3. Documentation-only change does not invalidate scientific evidence.
4. Controller merge commit does not change review target if semantic content is unchanged.
5. Runtime evidence cannot hash itself directly or indirectly.
6. Review Bundle does not include superseded historical smoke by default.
7. Verifier cannot invent uncited blocking threshold.
8. Controller cannot map Verifier FAIL directly to human choice.
9. Executor test-aware implementation is rejected.
10. Contract ambiguity routes to Critic.
11. Ordinary implementation bug does not route to Critic.
12. Planner cannot final-PASS without Final Critic in high-risk mode.
13. Final Critic cannot edit implementation.
14. One semantic implementation revision does not run heavy Verifier twice without an explicit invalidation reason.
15. A provenance-only fix is routed to lightweight validation.
16. Generic workflow works without CARE/MyoPS/nnU-Net-specific fields.

---

## 15. Portability acceptance tests

Before promoting Agent-Flow into the stable Bridge Kit, test it on at least two
small non-CARE profiles.

Suggested examples:

### Toy A — Python library task

Exercise:

- initial Planner/Critic;
- Requirement Ledger;
- Executor bug;
- Verifier finding;
- Planner repair;
- Final Critic;
- final PASS.

### Toy B — small app/data-processing task

Exercise:

- project-specific verification adapter;
- Controller routing;
- CI;
- low-cost Review Bundle;
- a contract ambiguity that correctly invokes Critic;
- final PASS.

The generic core must not require medical imaging, GPU, model training, or
CARE-specific terminology.

---

## 16. Migration plan after CARE is finished

Do not implement this TODO immediately.

After the CARE Agent-Flow run reaches full fidelity closure:

1. Freeze the CARE final postmortem.
2. List every real false-PASS class that the workflow successfully prevented.
3. List every process/gate that consumed time without preventing a real failure.
4. Remove or downgrade unnecessary gates before extraction.
5. Extract only domain-neutral Agent-Flow Core into this Bridge Kit.
6. Keep CARE-specific adapters in CARE, not in Bridge Kit Core.
7. Preserve the current Lite Handoff as the default low-risk path.
8. Add reusable notifier support.
9. Add shared Codex profile/config support.
10. Add Project Profile templates.
11. Run non-CARE portability tests.
12. Only then decide whether the new Agent-Flow mode becomes stable/default for medium/high-risk projects.

---

## 17. Required CARE postmortem inputs for later extraction

The future extraction should explicitly capture these already-observed CARE
failure classes:

- missing/invalid persistent rollout session;
- wrong runtime Python/environment binding;
- Executor test-aware/synthetic intervention behavior;
- receipt laundering / declaration-only proof;
- pseudo-tiling and fake execution evidence;
- loss label correct but formula wrong;
- Verifier contract drift / invented threshold;
- Controller over-escalation to human decision;
- stale implementation/verifier/CI bindings;
- moving Git integration target;
- runtime identity self-reference/hash cycle;
- oversized global runtime manifest;
- repeated heavy verification on provenance-only changes;
- async GPT wait incorrectly treated as blocked;
- Critic lifecycle initially too narrow;
- root project state becoming stale relative to task-level machine state.

For each item, the postmortem should record:

```text
symptom
root cause
what actually prevented false PASS
generic invariant
minimum sufficient regression test
what complexity should NOT be copied forward
```

---

## 18. Design review checklist before implementation

When CARE is complete and this TODO is about to become code, the implementation
proposal must answer all of the following before any large refactor starts:

1. What is the minimum workflow needed for low-risk tasks?
2. What exact risk conditions activate Agent-Flow?
3. What four or fewer stable hashes/IDs are genuinely necessary?
4. What changes invalidate heavy runtime evidence?
5. What changes require only lightweight validation?
6. Why does each blocking gate exist?
7. How expensive is each gate?
8. Can Controller routing be implemented without interpreting domain semantics?
9. Can Verifier be strict without adding contract requirements?
10. Can Planner review a compact bundle instead of dozens of receipts?
11. Can Critic remain independent without appearing in every repair iteration?
12. Can a new repository adopt the framework by writing only a small Project Profile?
13. Can users keep Planner/Critic scheduled tasks enabled without manual per-round control?
14. Can notifier and common Codex settings be installed once per user rather than once per repo?
15. Does the proposed design reduce total orchestration complexity compared with the CARE prototype?

If the answer to 15 is no, do not implement the proposal.

---

## 19. Target end state

The future Bridge Kit should let a user do roughly this:

```text
1. Initialize a repository with ai-bridge.
2. Select Lite / Standard / Agent-Flow risk profile.
3. Provide a small Project Profile and the current goal.
4. Let Planner and Critic define/freeze the high-level contract when required.
5. Let Controller/Verifier/Executor execute and repair automatically.
6. Let Planner perform implementation review.
7. Let Critic return only for contract problems and the final independent audit.
8. Notify the user only at a real decision/terminal point.
```

The user should spend time on product/research decisions, not on supervising
session IDs, receipt hashes, repeated verifier runs, CI binding, or internal
agent routing.

That is the standard this TODO should be judged against when CARE is finished.
