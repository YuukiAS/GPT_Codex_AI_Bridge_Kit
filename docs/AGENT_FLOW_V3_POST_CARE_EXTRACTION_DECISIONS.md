# Agent-Flow v3 Post-CARE Extraction Decisions

Status: **IMPLEMENTATION READY**

Target Bridge Kit release: **v0.4.0**

This document is the implementation gate between the earlier design-only blueprint and the next Bridge Kit release.

It should be read together with:

```text
docs/TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
```

The old blueprint deliberately said `DESIGN ONLY / DO NOT IMPLEMENT YET` until the CARE stress test reached full implementation-fidelity closure and a final Planner/Critic gate. CARE has now reached that closure. Therefore the old blueprint remains useful design history, but its wait condition is satisfied. For implementation readiness and scope, this document and `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md` take precedence.

---

## 1. Release decision

Bridge Kit v0.4.0 should begin the reusable Agent-Flow extraction.

It must **not** replace the current lightweight Handoff protocol. The system becomes layered:

```text
Host Policy                        once per CODEX_HOME
  +
Lite Handoff                       default per repository
  +
optional Agent-Flow Core           installed only when selected
  +
Project Profile / adapters         repository-specific
```

Current v0.3.x host configuration and notifier remain separate capabilities and should be reused rather than reimplemented.

---

## 2. Frozen architecture decisions

### Decision 1 — Lite remains the default

Existing:

```bash
ai-bridge init --target <repo>
ai-bridge validate --target <repo>
```

must remain backward compatible and must not silently install the heavy Agent-Flow machinery.

Agent-Flow is explicit opt-in.

### Decision 2 — Agent-Flow is a reusable profile, not a CARE clone

The generic core contains:

- role authority;
- state schema;
- Requirement Ledger;
- typed finding/routing rules;
- semantic source manifests;
- Stable Review Snapshot;
- Review Bundle;
- incremental invalidation;
- deterministic validation;
- role-session orchestration interfaces;
- Final Critic lifecycle;
- terminal notifier hook.

CARE-specific model, medical imaging, Slurm, GPU, route, dataset and mutation semantics stay in CARE.

### Decision 3 — Role authority is frozen

Five logical LLM roles:

```text
Planner
Critic
Controller
Verifier
Executor
```

For high-risk execution, Controller / Verifier / Executor must be independent sessions. Authority is defined by decision rights, not merely file write paths.

Planner owns intent and implementation review.
Critic owns contract audit and final closure audit.
Controller owns deterministic orchestration only.
Verifier owns contract-conformance oracles only.
Executor owns implementation only.

### Decision 4 — Critic is not in every repair loop

Critic modes:

```text
REQUIRED_INITIAL
STANDBY
REQUIRED_CONTRACT_REVIEW
REQUIRED_FINAL_AUDIT
COMPLETE
```

Normal implementation/verifier/runtime/provenance repair keeps Critic in `STANDBY`.

### Decision 5 — Requirement Ledger is mandatory for Agent-Flow

Every blocking verifier finding must bind to a frozen requirement.

The ledger must be compact. It is not a duplicate natural-language contract.

### Decision 6 — Review identity is semantic content, not moving Git history

Stable identity uses:

```text
task/request identity
frozen contract digest
Requirement Ledger digest
implementation semantic-source digest
verifier semantic-source digest
```

Controller/current/receipt/CI-record/doc commits remain locators and audit history.

### Decision 7 — one canonical source manifest per semantic authority domain

Do not let `SOURCE_SNAPSHOT` and implementation/verifier manifests maintain competing critical-path lists.

Required design:

```text
IMPLEMENTATION_SOURCE_MANIFEST.json -> implementation_semantic_digest
VERIFIER_SOURCE_MANIFEST.json       -> verifier_semantic_digest
SOURCE_SNAPSHOT.json                -> references both digests
```

Project Profile declares how those canonical source sets are discovered.

### Decision 8 — incremental invalidation is a core correctness rule

Receipt-only, state-only, documentation-only, CI-only, control-plane-only, implementation-source and verifier-source changes must be distinguished.

The Controller must choose the minimum sufficient rerun set.

`rerun everything for safety` is not an allowed default.

### Decision 9 — Final Critic is a real promotion gate

High-risk terminal lifecycle:

```text
Planner PLANNER_PASS_CANDIDATE
-> READY_FOR_CRITIC_FINAL_AUDIT
-> CRITIC_FINAL_PASS or CRITIC_FINAL_REVISE
-> PLANNER_PASS
-> AWAIT_HUMAN_DECISION
```

Controller transitions around Planner/Critic decisions are mechanical. It may not fabricate those decisions.

### Decision 10 — branch topology remains user-controlled

The generic core must not hard-code `develop` and must not autonomously create branches.

Project Profile may specify an already-authorized integration branch. If the workflow needs a new branch, explicit user authorization is required before creation.

Role isolation should prefer separate worktrees. When no role branch is explicitly authorized, detached worktrees are the preferred default for Verifier/Executor implementation work; Controller may integrate their commit SHAs into the already-authorized integration branch.

### Decision 11 — exact role sessions, not `--last`

Persistent role sessions must have explicit role identity and exact thread/session IDs when the runtime exposes them.

Generic orchestration must not use `codex resume --last` as the role-binding mechanism.

Distinct CODEX_HOME directories may be supported as a strict isolation option, but are not a universal core requirement if exact session IDs, worktree separation and write/authority boundaries are enforceable.

### Decision 12 — machine state is authoritative

Status, watchboards and notifier decisions derive from typed current state and validated evidence.

Historical free text and stale artifact keywords may never override current machine state.

### Decision 13 — machine-local secrets and absolute paths stay local

Tracked state may contain portable placeholders and provenance identifiers. Absolute server paths, PIDs, secrets and private runtime bindings belong in a user-local state root.

### Decision 14 — notifier is terminal plumbing, not orchestration authority

Reuse the v0.3 notifier. Agent-Flow emits a standard `notification_brief.json` only at real terminal/user-decision states.

The later generic notifier structured-brief extension keeps this default:
milestone briefs are opt-in for workflows that need them, not an Agent-Flow
intermediate-state notification trigger.

Notifier does not decide task completion.

### Decision 15 — Host Policy remains separate

Do not duplicate user-level Codex settings inside Agent-Flow project templates.

Continue relying on the existing host layer for:

```text
on-request + workspace-write + auto_review
request_user_input feature
memories
user-facing Chinese narrative
Git push allow rules
branch-creation policy
```

---

## 3. Frozen change classes

Agent-Flow v0.4 must represent semantic invalidation separately from workflow findings.

Recommended change classes:

```text
CONTRACT_CHANGED
REQUIREMENT_LEDGER_CHANGED
IMPLEMENTATION_SOURCE_CHANGED
VERIFIER_SOURCE_CHANGED
RUNTIME_ENVIRONMENT_CHANGED
CI_WORKFLOW_CHANGED
CONTROL_PLANE_ONLY_CHANGED
RECEIPT_OR_MANIFEST_ONLY_CHANGED
CURRENT_OR_ROUTING_ONLY_CHANGED
DOC_ONLY_CHANGED
NO_RELEVANT_CHANGE
```

These are not the same thing as findings such as `IMPLEMENTATION_BUG` or `VERIFIER_BUG`.

A finding answers **what is wrong and who owns repair**.
A change class answers **what evidence has become invalid and what must rerun**.

---

## 4. Frozen finding classes

Use the CARE-tested compact set, with generic wording for the user-facing scientific/product boundary:

```text
IMPLEMENTATION_BUG
VERIFIER_BUG
VERIFIER_CONTRACT_DRIFT
EVIDENCE_GAP
PROVENANCE_BINDING_GAP
OPERATIONAL_FAILURE
RUNTIME_ENVIRONMENT_FAILURE
CONTRACT_AMBIGUITY
CONTRACT_CONTRADICTION
DIAGNOSTIC_ANOMALY
SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED
```

Generic `BLOCKED` without a typed reason is insufficient for Controller routing.

---

## 5. Core state direction

The reusable state machine should be smaller than CARE's historical state set while retaining meaningful authority boundaries.

Target normal lifecycle:

```text
PLAN_REQUESTED
PLAN_READY_FOR_CRITIC
PLAN_FROZEN
CONTROLLER_INITIALIZING
VERIFIER_RUNNING
VERIFIER_FROZEN
EXECUTOR_RUNNING
EVIDENCE_RUNNING
CI_RUNNING
READY_FOR_PLANNER_REVIEW
WAITING_FOR_EXTERNAL_GPT
PLANNER_REVISE_EXECUTOR
PLANNER_REVISE_VERIFIER
PLANNER_REVISE_BOTH
PLANNER_PASS_CANDIDATE
READY_FOR_CRITIC_FINAL_AUDIT
CRITIC_FINAL_REVISE
PLANNER_PASS
AWAIT_HUMAN_DECISION
```

Operational/provenance repair should normally be represented by typed finding/change-class metadata plus `next_action`, rather than multiplying top-level states for every repair subtype.

Exceptional terminal/blocking classes should stay compact:

```text
NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE
BLOCKED_REQUIRED_SOURCE
BLOCKED_ROLE_ISOLATION
BLOCKED_CONTRACT_DRIFT
BLOCKED_CI
STOPPED_MAX_ROUNDS
STOPPED_USER
```

Do not reproduce every CARE transitional state unless a regression test demonstrates that a separate state is necessary.

---

## 6. v0.4 implementation boundary

v0.4.0 is expected to deliver an implementation-ready generic control plane and prove it on small non-CARE tasks.

It should include:

1. Agent-Flow profile installation.
2. Generic schemas/templates.
3. Project Profile.
4. Task initialization.
5. Requirement Ledger and source-manifest tooling.
6. Stable Review Snapshot and Review Bundle tooling.
7. Typed routing and incremental invalidation engine.
8. Deterministic validators.
9. Exact-role-session/worktree orchestration interface.
10. Planner/Critic reusable prompt templates.
11. Final Critic lifecycle.
12. v0.3 notifier terminal integration.
13. At least two portability/smoke profiles with no CARE dependency.
14. Anti-overengineering regression tests.

A fully autonomous arbitrary-cluster scheduler, generic Slurm implementation, hosted visual browser, or ChatGPT Scheduled Task creation API is not required for v0.4.

---

## 7. Explicit non-goals

Do not copy into the generic core:

```text
CARE/MyoPS/nnU-Net semantics
CARE route portfolio/watchboard
CARE GPU partitions
CARE Slurm job schemas
CARE dataset split fields
CARE protected mutation catalogue
CARE absolute paths
hard-coded develop branch
hard-coded CODEX_HOME layout
huge historical runtime manifests
per-receipt hash webs
```

Do not weaken the existing Lite Handoff or Host Policy to make Agent-Flow easier to implement.

---

## 8. Release acceptance

Before Bridge Kit may call the feature stable enough for `0.4.0`, all of these must hold:

- existing v0.3.1 Lite Handoff tests pass unchanged;
- existing Host Policy tests pass unchanged;
- existing notifier tests pass unchanged;
- a repository can install Agent-Flow without CARE-specific content;
- a repository can uninstall/ignore Agent-Flow without breaking Lite Handoff;
- no new branch is created during normal profile/task initialization;
- source snapshot has one canonical implementation source manifest and one canonical verifier source manifest;
- receipt/state/doc-only changes do not change `review_target_id`;
- control-plane-only change does not request heavy verification;
- verifier cannot emit a blocking uncited threshold;
- Controller cannot directly turn verifier/runtime/provenance failure into user choice;
- fake Verifier freeze without new required evidence is rejected;
- Planner review reads current target before prior findings;
- Final Critic is mandatory only for the high-risk Agent-Flow profile;
- terminal notifier fires only after a true terminal/user-decision state;
- at least two non-CARE portability tests complete end-to-end at control-plane level.

The implementation details are frozen in `docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md`.
