# CARE Agent-Flow v3 Stress-Test Postmortem

Date: 2026-08-11

Status: **CARE stress test complete / reusable extraction input**

Source repository: `YuukiAS/CARE_Challenge`

Primary evaluated branch: `develop`

This document records what the CARE Agent-Flow v3 experiment actually taught us before the workflow is extracted into `GPT_Codex_AI_Bridge_Kit`. It is intentionally not a copy of CARE's automation tree. The purpose is to separate the invariants that prevented false PASS from the CARE-specific machinery that should not be generalized.

The earlier design document `docs/TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md` stated that reusable implementation should wait until CARE reached implementation-fidelity closure and the final Planner/Critic gate. That precondition is now satisfied: the final CARE Planner review returned `PLANNER_PASS`, the Final Critic returned `CRITIC_FINAL_PASS`, stable review identity remained unchanged, and neither the final control-plane migration nor Final Critic audit requested another heavy Verifier, runtime/model probe, formal training, outer-data access, or deployment action.

---

## 1. What was actually stress-tested

CARE began with a strict five-role model:

```text
Planner
-> Critic
-> Controller
-> Verifier
-> Executor
-> Planner re-entry / repair
-> human gate
```

The experiment then grew into a real long-lived workflow with:

- independent GPT Planner and Critic control-plane prompts;
- persistent Controller, Verifier and Executor Codex sessions;
- role isolation and exact-resume receipts;
- a frozen scientific contract;
- a machine-readable Requirement Ledger;
- public and protected verifier cases;
- mutation-based known-bad checks;
- server-local GPU/runtime evidence;
- hosted CI;
- repeated implementation and verifier repair rounds;
- moving-target and provenance repairs;
- Stable Review Snapshot migration;
- a late Final Critic lifecycle migration;
- terminal notifier integration.

The `develop` branch accumulated hundreds of commits during this exercise. That scale is evidence that the workflow was tested under real repair pressure, but it is also evidence that the CARE prototype became too state-heavy. The generic Bridge Kit must preserve the useful control invariants while sharply reducing orchestration bookkeeping.

---

## 2. Closure evidence

The final CARE state binds the following conclusions:

```text
initial_critic_decision = PLAN_FROZEN
planner_decision = PLANNER_PASS
critic_decision = CRITIC_FINAL_PASS
implementation_complete = true
ci_status = PASS
open_scientific_choices = []
```

The final review uses `STABLE_REVIEW_SNAPSHOT`. Git SHAs are explicitly treated as provenance locators rather than the semantic review identity, and receipt/state/document-only changes do not invalidate the current review target.

The Final Critic explicitly recorded:

```text
review_target_identity_unchanged = true
heavy_verifier_rerun_requested = false
runtime_or_model_probe_rerun_requested = false
formal_training_authorized = false
outer_access_authorized = false
deployment_authorized = false
```

This matters because the final control-plane repair added a Final Critic phase after the semantic implementation had already passed. CARE correctly classified that migration as `CONTROL_PLANE_ONLY_CHANGED`: the process could be tightened without pretending that model semantics had changed and without rerunning expensive scientific verification.

Key final artifacts:

```text
CARE_Challenge@develop:
automation/agent_flow_v3/tasks/care-ase-faithful/CURRENT.json
results/agent_flow_v3/care-ase-faithful/planner_reviews/round_001_reentry_009.json
results/agent_flow_v3/care-ase-faithful/critic_reviews/final_critic_review.json
results/agent_flow_v3/care-ase-faithful/final_critic_lifecycle_migration_receipt.json
```

---

## 3. What actually prevented false PASS

### 3.1 Independent Critic must repair deterministic contract defects before freeze

The useful role of the initial Critic was not to add another approval loop. It caught contradictions that would have produced a superficially valid implementation with incorrect scientific semantics: decoder reset, no-T2 supervision leakage, fold leakage, incompatible checkpoint splicing, undefined hard-negative/loss semantics, and runtime plans that could legally terminate without performing the intended work.

The generic invariant is:

> The initial Critic independently audits the Planner contract. If one repair is logically determined by the user objective, repository evidence, and existing policy, Critic repairs it in the same pass and re-audits the full contract. It escalates only a genuinely unresolved scientific/product choice.

Do not copy the CARE-specific architecture clauses. Preserve the direct-repair rule and exact contract freeze.

Relevant CARE history:

```text
7d64bba81b47a40e3c21778bda575930cf8f856c  review: record CARE-ASE critic revision decision
91b8e77558e717140bf25a120b9211a0c847b544  automation: add scheduled Critic prompt for agent-flow v3
```

### 3.2 Requirement Ledger prevents Verifier authority drift

CARE exposed a particularly important failure: the Verifier promoted a comparison that was not a contract requirement into a blocking threshold. It required real CNN logits under different receptive-field contexts to agree at `1e-6`, even though the contract required canonical inference-path semantics, genuine tile-local forwards, and one global post-aggregation bias—not equality of two physically different contexts.

This was repaired as `VERIFIER_CONTRACT_DRIFT`; the comparison remained useful as a diagnostic but stopped being a scientific gate.

The generic invariant is:

> Every blocking verifier finding must cite an existing frozen requirement. A verifier may derive mechanically implied invariants, but it cannot invent a new scientific requirement or uncited numeric threshold. Unsupported observations are diagnostic or are routed to Planner for contract interpretation.

The Requirement Ledger should remain compact and authoritative enough to answer: what requirement is being tested, who owns it, whether it is blocking, what verifier semantics are allowed, and where any numeric threshold comes from.

Relevant artifact:

```text
results/agent_flow_v3/care-ase-faithful/controller_same_scope_verifier_contract_drift_repair_receipt.json
```

### 3.3 State transitions require new evidence, not merely a new commit or synchronized worktree

The orchestrator once marked the Verifier frozen after its worktree merely fast-forwarded to `origin/develop`. No new verifier repair commit, verifier fingerprint, or non-fixture executable receipt had been produced.

The generic invariant is:

> A workflow state that claims new evidence must prove that the required evidence artifact changed and is valid. Git movement, state-file edits, worktree synchronization, or a new Controller receipt are not substitutes for role-owned evidence.

This is why the generic state machine must have transition predicates, not keyword/commit heuristics.

Relevant artifact:

```text
results/agent_flow_v3/care-ase-faithful/orchestrator_false_positive_verifier_freeze_repair_receipt.json
```

### 3.4 Stable Review Snapshot is superior to a moving integration tuple

CARE initially bound too much evidence to exact integration commits. Every merge or receipt commit could make the previous tuple stale, producing large provenance-rebind loops even when implementation and verifier semantics were unchanged.

The successful correction was to define a stable semantic review target from content rather than Controller history.

The generic invariant is:

```text
review_target_id = semantic identity only

semantic inputs:
- task/request identity
- frozen contract digest
- Requirement Ledger digest
- implementation semantic-source digest
- verifier semantic-source digest

not semantic identity:
- Controller merge commit
- CURRENT commit
- receipt commit
- notifier/report commit
- CI receipt commit
- documentation-only commit
```

Git SHAs remain useful provenance locators. They do not automatically become independent invalidation keys.

### 3.5 Use one canonical semantic source manifest per authority domain

The final Planner and Final Critic both identified the same nonblocking debt: `SOURCE_SNAPSHOT` had a narrower implementation path list than the actual implementation source manifest. The review remained safe because `REVIEW_BUNDLE -> implementation_fingerprint -> source_manifest` covered the wider semantic source set and Planner independently inspected the omitted files.

The generic correction is simpler than adding more hashes:

> Do not maintain two competing lists of implementation-critical paths. Build the implementation semantic digest from one canonical implementation source manifest, and the verifier semantic digest from one canonical verifier source manifest. `SOURCE_SNAPSHOT` references those digests instead of redefining their path sets.

This removes an entire class of dual-truth provenance bugs.

### 3.6 Provenance failures are not scientific choices

At one point CARE had dozens of stale/missing transaction, manifest, artifact-SHA, checkpoint, runtime and CI bindings. The verifier correctly failed closed, but these failures did not imply a scientific dilemma.

The generic invariant is:

```text
PROVENANCE_BINDING_GAP -> Controller / lightweight provenance repair
SCIENTIFIC_CHOICE_REQUIRED -> user only after Planner classification
```

The Controller must never turn operational/provenance friction into a user scientific decision merely because it cannot immediately reconcile receipts.

The generic extraction should go further than CARE: most receipt-only rebinds should not return to Executor at all when semantic source content is unchanged.

### 3.7 Fail-closed means no false PASS, not stop everything

CARE required many same-scope repairs: wrong runtime environment, unavailable GPU partition, stale receipt, verifier bug, session repair, CI/provenance repair, and implementation bug.

The useful invariant is:

```text
RECOVERABLE_TASK_LOCAL_FAILURE
-> owning role or Controller same-scope recovery
-> continue current task

CONTRACT_REVIEW_REQUIRED
-> Planner/Critic

HUMAN_SCIENTIFIC_DECISION_REQUIRED
-> user
```

Fail-closed should prevent promotion while evidence is invalid. It should not convert every recoverable defect into a human gate or restart the entire workflow.

### 3.8 Planner reviews current reality before prior findings

The final Planner pass records an important review-order rule: current implementation, verifier, runtime evidence, and semantic sources were reviewed before prior findings. Only afterward were historical findings used to verify closure.

The generic invariant is:

> A reviewer must form an independent view of the current target before reading prior findings. Otherwise the review can degenerate into a checklist that verifies only known problems and misses new regressions.

### 3.9 Final Critic is a closure auditor, not a second implementation reviewer

The original v3 state machine ended Planner PASS directly at the human gate. CARE later added a Final Critic phase as a control-plane-only migration without invalidating semantic evidence.

The final lifecycle that survived the stress test is:

```text
Planner: PLANNER_PASS_CANDIDATE
-> Controller: READY_FOR_CRITIC_FINAL_AUDIT
-> Final Critic
   - CRITIC_FINAL_PASS
   - CRITIC_FINAL_REVISE
-> Controller mechanically routes PASS
-> AWAIT_HUMAN_DECISION
```

Final Critic checks contract weakening, Requirement Ledger integrity, verifier authority, test-aware implementation, closure of Planner findings, Stable Review Snapshot coherence, and CI binding. It does not rerun implementation review from scratch and cannot edit implementation.

### 3.10 Control-plane-only changes must not reopen semantic verification

The late Final Critic migration is the cleanest concrete test of incremental invalidation. It changed the lifecycle schema and routing but preserved all stable semantic identities and correctly performed:

```text
executor_restarted = false
verifier_restarted = false
heavy_verifier_rerun = false
runtime_model_probe_rerun = false
scientific_contract_changed = false
```

This should become a first-class generic change class: `CONTROL_PLANE_ONLY_CHANGED`.

### 3.11 Watchboards and status UIs must derive from authoritative typed state

An earlier CARE watchboard misrepresented a route because historical packet keywords overrode the current planning-rereview state. The repair made `PLANNING_REVISION_READY_FOR_CRITIC_REREVIEW` authoritative and explicitly kept Controller authority false until the critic token existed.

The generic invariant is:

> UI/watchboard state is a projection of typed machine state and validated receipts. Historical logs, free-text keywords, and stale result packets must never override the authoritative current state.

Relevant history:

```text
6c8d6f26ed4907ee59023795265ee4e1c53fb2b8  Fix watchboard critic rereview status
```

### 3.12 Session provenance matters, but server-private paths should stay private

CARE found that exact role identity and resume history matter. It also found that absolute server paths should not be copied into tracked public receipts. The repair kept sanitized tracked receipts and wrote exact machine paths into a server-local private state root.

Generic invariant:

> Track portable role identity and semantic receipts in Git; keep machine-specific absolute paths, PIDs, secrets, and exact local runtime bindings in a user-local runtime state root. Do not require a public repository to encode one server's filesystem.

---

## 4. What should not be copied from CARE

The following mechanisms were useful as stress-test evidence but should not become generic defaults:

- hard-coded `develop` as the universal integration branch;
- hard-coded CARE worktree paths or CODEX_HOME locations;
- mandatory Slurm/GPU concepts in the core schema;
- medical-imaging-specific verifier fields;
- one SHA field for every receipt and transition;
- a global runtime manifest containing every historical smoke artifact;
- exact integration-SHA equality as the semantic review identity;
- repeated heavy Verifier runs after receipt/state-only changes;
- nested provenance rebind loops for bookkeeping-only drift;
- requiring every Controller bookkeeping commit to produce a new review identity;
- treating scheduled-GPT waiting as workflow failure;
- using historical free text to infer authority/state;
- copying CARE's protected mutation catalogue into unrelated projects;
- requiring distinct CODEX_HOME values when exact thread identity plus worktree/write-scope isolation is sufficient for a target environment;
- automatically creating Git branches as a safety reaction.

The Bridge Kit host policy already establishes that new branches are user-controlled. Generic Agent-Flow must respect that policy. High-risk role isolation should default to separate worktrees and exact role sessions; if role-specific branches are required, their creation must be explicitly authorized. Detached worktrees are a valid default implementation strategy when no new branch has been authorized.

---

## 5. Generic role authority frozen after CARE

The following role model should be treated as stable for the first reusable implementation.

### Planner

Owns user intent, initial contract, contract interpretation, implementation review, typed repair findings, and `PLANNER_PASS_CANDIDATE`.

Must not implement code, edit verifier source, or perform Controller mechanics.

### Critic

Owns initial contract audit/freeze, conditional contract ambiguity/contradiction audit, and final independent closure audit.

During ordinary implementation repair it is `STANDBY`.

### Controller

Owns only orchestration: role start/resume, state, deterministic routing, integration, CI invocation, incremental invalidation classification, review-bundle construction, retries, and terminal notifier trigger.

It should be the least domain-intelligent role.

### Verifier

Owns tests, known-bads, mutations, diagnostics, and verification receipts derived from frozen requirements.

It may strengthen how a requirement is tested; it may not expand what the requirement means.

### Executor

Owns implementation and authorized runtime execution.

It cannot edit the contract/verifier, manufacture receipts, or create verifier/test-aware alternate business logic.

---

## 6. Generic typed routing frozen after CARE

Use typed findings rather than free-text `BLOCKED`:

```text
IMPLEMENTATION_BUG -> Executor
VERIFIER_BUG -> Verifier
VERIFIER_CONTRACT_DRIFT -> Planner adjudication + Verifier
EVIDENCE_GAP -> owning role
PROVENANCE_BINDING_GAP -> Controller
OPERATIONAL_FAILURE -> Controller same-scope recovery
RUNTIME_ENVIRONMENT_FAILURE -> Controller/runtime repair
CONTRACT_AMBIGUITY -> Planner; Critic only if contract review is required
CONTRACT_CONTRADICTION -> Planner -> Critic
DIAGNOSTIC_ANOMALY -> Planner diagnostic review
SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED -> user
```

Controller may ask the user for a scientific/product choice only when Planner has classified it as such and same-scope implementation, verification, runtime, CI, or provenance repair cannot resolve it.

---

## 7. Incremental invalidation policy frozen after CARE

This is a core extraction requirement, not an optimization to add later.

```text
CONTRACT_CHANGED
-> Critic re-freeze
-> new Requirement Ledger as needed
-> new semantic review target
-> invalidate dependent verifier/runtime evidence

REQUIREMENT_LEDGER_CHANGED
-> new semantic review target
-> rerun affected verifier/runtime evidence

IMPLEMENTATION_SOURCE_CHANGED
-> implementation semantic digest changes
-> affected runtime probes
-> heavy Verifier
-> CI

VERIFIER_SOURCE_CHANGED
-> verifier semantic digest changes
-> affected verifier tests/mutations
-> only runtime probes required by changed oracle
-> CI when repository-safe code changed

RUNTIME_ENVIRONMENT_CHANGED
-> rerun only environment-dependent evidence
-> do not change semantic source identity unless source changed

CI_WORKFLOW_CHANGED
-> CI only

CONTROL_PLANE_ONLY_CHANGED
-> state/schema/routing validation only
-> no Executor restart
-> no heavy Verifier
-> no model/runtime probe

RECEIPT_OR_MANIFEST_ONLY_CHANGED
-> lightweight Review Bundle/provenance validation only

CURRENT_OR_ROUTING_ONLY_CHANGED
-> state validation only

DOC_ONLY_CHANGED
-> no semantic evidence invalidation
```

A second heavy Verifier run for the same semantic implementation revision requires an explicit invalidation reason.

---

## 8. Source index used for this extraction

Initial v3 design and automation on CARE `main`:

```text
f76e6020ca580814183851424dee22287c21774c  separated planner/controller/verifier/executor protocol
21e6ce015c8306b5edf7abf89c2514cae6522de2  initial state schema
6f7fffca1f2a80ece4a75a8ebb5000da31faee0a  deterministic validator
9323b855df0ff58e096aff83bd34f0993d9171b9  scheduled Planner prompt
91b8e77558e717140bf25a120b9211a0c847b544  scheduled Critic prompt
```

Planning/Critic repair history:

```text
7d64bba81b47a40e3c21778bda575930cf8f856c  critic revision decision
fa4be4ae44e2fd3fde206e6d572006d3b21e884d  controller bound to final critic amendment
38551ed98a42b005a1a3f0b793efdef700037ee8  critic rereview blocker repair
6c8d6f26ed4907ee59023795265ee4e1c53fb2b8  watchboard rereview state repair
```

Final stress-test artifacts on CARE `develop`:

```text
automation/agent_flow_v3/ROLE_AUTHORITY_POLICY.md
automation/agent_flow_v3/schema.json
automation/agent_flow_v3/tasks/care-ase-faithful/CURRENT.json
automation/agent_flow_v3/tasks/care-ase-faithful/REQUIREMENT_LEDGER.json
automation/agent_flow_v3/tasks/care-ase-faithful/SOURCE_SNAPSHOT.json
results/agent_flow_v3/care-ase-faithful/REVIEW_BUNDLE.json
results/agent_flow_v3/care-ase-faithful/planner_reviews/round_001_reentry_009.json
results/agent_flow_v3/care-ase-faithful/critic_reviews/final_critic_review.json
results/agent_flow_v3/care-ase-faithful/final_critic_lifecycle_migration_receipt.json
results/agent_flow_v3/care-ase-faithful/controller_same_scope_verifier_contract_drift_repair_receipt.json
results/agent_flow_v3/care-ase-faithful/orchestrator_false_positive_verifier_freeze_repair_receipt.json
results/agent_flow_v3/care-ase-faithful/production_session_repair_receipt.json
```

---

## 9. Extraction conclusion

CARE validates the main thesis of the earlier reusable blueprint, but it also narrows it.

The reusable system should be strict about **meaning** and lightweight about **bookkeeping**:

```text
freeze intent
-> freeze requirements
-> isolate authority
-> verify real execution
-> bind semantic source content
-> rerun only what semantic change invalidates
-> independent Planner review
-> independent Final Critic closure audit
-> human decision
```

The generic system should not ask the user to supervise hashes, session repair, CI rebinding, or internal routing. Those are Controller mechanics. The user should re-enter only for a real product/scientific choice or the final decision gate.
