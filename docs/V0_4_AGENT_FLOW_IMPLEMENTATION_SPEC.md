# Bridge Kit v0.4.0 — Reusable Control Implementation Specification

Status: **READY FOR CODEX IMPLEMENTATION**

Current stable package baseline: `0.3.1`

Target package version: `0.4.0`

This specification translates the post-CARE extraction decisions into an implementable Bridge Kit release. It is intentionally narrower and simpler than the full CARE prototype.

Required reading order:

```text
README.md
docs/CARE_AGENT_FLOW_V3_POSTMORTEM_20260811.md
docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md
docs/TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md
this file
```

If the old TODO still says `DESIGN ONLY / DO NOT IMPLEMENT YET`, the wait condition is superseded by `docs/AGENT_FLOW_V3_POST_CARE_EXTRACTION_DECISIONS.md`: the CARE stress test and final Planner/Critic closure are complete.

---

## 1. Product goal

Bridge Kit currently provides three reusable layers:

```text
Host Policy
Lite
Generic Notifier
```

v0.4.0 adds a fourth, optional layer:

```text
Reusable Control
```

The intended user experience is:

```text
# once per Codex identity
ai-bridge host install

# once per repository
ai-bridge init --target /repo

# only when the repository needs high-risk autonomous execution
ai-bridge agent-flow install --target /repo
ai-bridge agent-flow validate --target /repo

# initialize a high-risk task without inventing branch topology
ai-bridge agent-flow task init --target /repo --task-key <task_key>
```

Lite remains the default and must not become slower or more complex.

---

## 2. Architectural split

### 2.1 Control

Domain-neutral code owned by Bridge Kit:

- workflow schemas;
- role authority policy;
- task/current state validation;
- finding classification and routing;
- change classification and evidence invalidation;
- Requirement Ledger schema/validation;
- semantic source manifest generation;
- Stable Review Snapshot generation;
- Review Bundle validation;
- role/session/worktree receipts;
- deterministic Controller transition logic;
- reusable Planner/Critic prompt templates;
- terminal notifier adapter;
- generic toy portability profiles.

### 2.2 Project Profile

Repository-specific configuration supplies only facts that genuinely vary by project:

```text
project identity and objective
repository truth/bootstrap files
artifact language policy
contract/source paths
optional visual source manifest
implementation semantic path rules
verifier semantic path rules
runtime adapter
CI adapter / workflow name
external-data/service boundaries
expensive-operation authorization boundary
human decision boundary
notification policy
integration branch policy
role isolation policy
```

The Project Profile must not redefine the five role authorities.

### 2.3 Project adapters

Optional adapters may implement project-specific runtime/verifier behavior. Examples include GPU probes, Slurm, databases, browsers, deployment or scientific evaluators.

Adapters return typed evidence/findings. They do not alter core routing semantics.

---

## 3. Repository layout

Control installation should be additive and clearly separate from Lite.

Recommended tracked layout:

```text
automation/
  agent_flow/
    README.md
    schema.json
    ROLE_AUTHORITY_POLICY.md
    PROJECT_PROFILE.json
    templates/
      requirement_ledger.template.json
      implementation_source_manifest.template.json
      verifier_source_manifest.template.json
      source_snapshot.template.json
      review_bundle.template.json
      routing_policy.template.json
    prompts/
      PLANNER.md
      CRITIC.md
      CONTROLLER.md
      VERIFIER.md
      EXECUTOR.md
    tasks/
      <task_key>/
        REQUEST.json
        CURRENT.json
        PLANNER_DRAFT.md                 # created when planning occurs
        FROZEN_CONTRACT.md               # created/frozen by Critic
        REQUIREMENT_LEDGER.json          # created/frozen by Critic
        IMPLEMENTATION_SOURCE_MANIFEST.json
        VERIFIER_SOURCE_MANIFEST.json
        SOURCE_SNAPSHOT.json
        repairs/

results/
  <task_key>/
    REVIEW_BUNDLE.json
    controller_report.md
    planner_reviews/
    critic_reviews/
    verification/
    implementation/
    receipts/
    notification_brief.json              # only when terminal/notifiable
```

Do not create this tree for ordinary Lite-only repositories unless the user explicitly installs Control.

Machine-local runtime state belongs outside Git, for example under a configurable user state root:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/agent-flow/<repo-id>/<task-key>/
```

It may contain:

```text
exact session/thread IDs
absolute worktree paths
PIDs/process metadata
local logs
private runtime bindings
secrets or secret references
```

Tracked receipts should use portable identifiers/placeholders where exact local paths are not needed for repository review.

---

## 4. CLI contract

Keep all existing commands backward compatible.

Add the following command family.

### 4.1 Install/status/validate

```bash
ai-bridge agent-flow install --target <repo>
ai-bridge agent-flow status --target <repo>
ai-bridge agent-flow validate --target <repo>
```

Requirements:

- `install` is idempotent.
- existing project files are preserved unless inside an explicitly managed block/template.
- no branch is created.
- no remote is modified.
- no CODEX_HOME host config is silently changed.
- `status` is read-only.
- `validate` is deterministic and dependency-light.

### 4.2 Task initialization

```bash
ai-bridge agent-flow task init \
  --target <repo> \
  --task-key <task_key>
```

Optional arguments may include already-authorized facts such as:

```text
--integration-branch <existing-branch>
--max-repair-rounds <n>
--profile <high-risk>
```

If no integration branch is supplied, use the currently checked-out branch as the default target. Do not create `develop`, `agent-flow/*`, or any other branch automatically.

Task initialization should create a minimal `REQUEST.json` and `CURRENT.json` with state `PLAN_REQUESTED` and explicit unset/not-yet-frozen fields. It must not fabricate a frozen contract hash.

### 4.3 Snapshot and bundle tools

```bash
ai-bridge agent-flow snapshot --target <repo> --task-key <task_key>
ai-bridge agent-flow bundle validate --target <repo> --task-key <task_key>
```

`snapshot` generates canonical semantic source manifests and `SOURCE_SNAPSHOT.json` from the Project Profile and current tracked content.

It must clearly distinguish semantic content digests from Git locator SHAs.

### 4.4 Routing / change classification

Provide a deterministic interface such as:

```bash
ai-bridge agent-flow classify-change --target <repo> --task-key <task_key> --base <ref> --head <ref>
ai-bridge agent-flow route --target <repo> --task-key <task_key>
```

Exact command names may be adjusted if the CLI design has a materially cleaner shape, but the capabilities must exist and remain deterministic.

`route` reads machine state/findings and returns the next role/action without domain interpretation.

### 4.5 Prompt access

Extend the existing prompt-printing capability or add:

```bash
ai-bridge agent-flow prompt planner
ai-bridge agent-flow prompt critic
ai-bridge agent-flow prompt controller
ai-bridge agent-flow prompt verifier
ai-bridge agent-flow prompt executor
```

These are reusable control-plane prompts. They read current repository schema/profile on each run instead of hard-coding one project's states.

---

## 5. Role authority

The repository template must carry a generic `ROLE_AUTHORITY_POLICY.md` derived from the CARE-tested policy.

### Planner

May decide:

- interpretation of user/product/scientific intent;
- initial contract;
- what constitutes success/failure;
- classification of disputes/findings;
- implementation review;
- repair findings;
- `PLANNER_PASS_CANDIDATE`.

Must not:

- modify implementation;
- modify verifier source;
- run Controller mechanics;
- fabricate runtime evidence.

### Critic

Modes:

```text
REQUIRED_INITIAL
STANDBY
REQUIRED_CONTRACT_REVIEW
REQUIRED_FINAL_AUDIT
COMPLETE
```

May decide:

- whether the initial contract/ledger is complete;
- deterministic contract repair;
- whether a real contract ambiguity/contradiction remains;
- final independent closure audit.

Must not become a generic implementation reviewer or appear in every repair loop.

### Controller

May decide only mechanical orchestration:

- exact-role session start/resume;
- worktree setup within already-authorized Git topology;
- typed routing;
- change classification;
- minimum evidence invalidation/rerun set;
- commit integration;
- CI invocation;
- bundle construction/validation;
- retries;
- state transitions that do not fabricate Planner/Critic judgment;
- terminal notifier call.

Controller must not choose product/scientific semantics.

### Verifier

May create:

- tests;
- known-bads;
- mutations;
- independent reference oracles;
- diagnostics;
- verification receipts.

A blocking finding must cite a frozen requirement. Otherwise it is diagnostic or requires Planner contract interpretation.

### Executor

May:

- implement production/source changes authorized by the frozen contract;
- run authorized implementation/runtime commands;
- create implementation evidence.

Must not:

- modify contract/ledger;
- modify verifier-owned source;
- weaken verification;
- branch on protected test IDs/mutation names/verifier mode;
- create fake/synthetic evidence instead of exercising the normal path;
- decide final PASS.

---

## 6. Requirement Ledger

Control tasks require a frozen machine-readable ledger.

Minimum entry shape:

```json
{
  "requirement_id": "REQ_EXAMPLE_001",
  "source": {
    "path": "automation/agent_flow/tasks/<task>/FROZEN_CONTRACT.md",
    "clause": "..."
  },
  "type": "IMPLEMENTATION",
  "blocking": true,
  "owner_role": "executor",
  "verifier_authority": "...",
  "threshold": null,
  "threshold_provenance": null,
  "change_requires_contract_review": false
}
```

Supported generic requirement types should remain compact, for example:

```text
PRODUCT_OR_SCIENTIFIC
IMPLEMENTATION
RUNTIME
INFERENCE_OR_OUTPUT
EVALUATION
PROVENANCE
PROCESS
DIAGNOSTIC
```

Numeric thresholds are blocking only when sourced from the frozen contract/ledger or a mechanically derived invariant that does not change product/scientific semantics.

Derived invariants should record parent requirement IDs and derivation.

---

## 7. Finding schema and routing

Use exactly one primary classification per finding:

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

Each blocking finding should minimally include:

```text
finding_id
classification
blocking
owner_role / target_role
requirement_ids
summary
observed_evidence
required_repair
required_regression_evidence
forbidden_workaround
created_against_review_target_id when applicable
```

Fixed routes:

```text
IMPLEMENTATION_BUG -> Executor
VERIFIER_BUG -> Verifier
VERIFIER_CONTRACT_DRIFT -> Planner adjudication, then Verifier or contract-review path
EVIDENCE_GAP -> owning role
PROVENANCE_BINDING_GAP -> Controller
OPERATIONAL_FAILURE -> Controller same-scope recovery
RUNTIME_ENVIRONMENT_FAILURE -> Controller/runtime adapter
CONTRACT_AMBIGUITY -> Planner; Critic only if contract review is needed
CONTRACT_CONTRADICTION -> Planner -> Critic
DIAGNOSTIC_ANOMALY -> Planner diagnostic review
SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED -> user
```

A Controller-originated user escalation without Planner's scientific/product classification must fail validation.

---

## 8. State machine

Do not copy CARE's full historical transitional-state explosion.

Recommended generic normal states:

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

Generic exception/terminal states:

```text
NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE
BLOCKED_REQUIRED_SOURCE
BLOCKED_ROLE_ISOLATION
BLOCKED_CONTRACT_DRIFT
BLOCKED_CI
STOPPED_MAX_ROUNDS
STOPPED_USER
```

Operational/provenance repair details should normally live in typed finding metadata and `next_action`, not one unique state per repair variant.

State transitions must have evidence predicates. Examples:

```text
PLAN_READY_FOR_CRITIC
requires a current Planner draft artifact.

PLAN_FROZEN
requires Critic freeze artifact + frozen contract + Requirement Ledger.

VERIFIER_FROZEN
requires current verifier semantic digest + required verifier-owned evidence; a worktree fast-forward alone is invalid.

READY_FOR_PLANNER_REVIEW
requires a current review_target_id + valid Review Bundle + required CI/evidence for that target.

PLANNER_PASS_CANDIDATE
requires Planner artifact bound to current review_target_id.

READY_FOR_CRITIC_FINAL_AUDIT
requires valid Planner pass-candidate artifact.

PLANNER_PASS
requires current Final Critic pass artifact.

AWAIT_HUMAN_DECISION
requires final pass and terminal policy; no autonomous next scientific/product stage.
```

Write decision/review artifacts before updating `CURRENT.json` to the corresponding new state.

---

## 8.1 External GPT wait contract

As of Bridge Kit `0.5.1`, Control uses the generic External GPT wait
contract. When the current state or `next_action` is owned by an external
Planner, Critic, Final Critic, or equivalent reasoning role, absence of a fresh
artifact is `waiting_external_review`, not a terminal blocker.

Covered states include `PLAN_REQUESTED`, `PLAN_READY_FOR_CRITIC`,
`READY_FOR_PLANNER_REVIEW`, `WAITING_FOR_EXTERNAL_GPT`,
`CONTRACT_REVIEW_REQUIRED`, `READY_FOR_CRITIC_FINAL_AUDIT`, and
`CRITIC_FINAL_REVISE`. These are examples, not the whole detection rule:
Controller should prefer state ownership, `next_action`, role policy,
repository schema, and workflow contract.

`MIN_EXTERNAL_GPT_WAIT = 2 hours` is the minimum normal grace period after a
published handoff to an external GPT role. It is not an automatic deadline.
After 2 hours, silence remains waiting if state/evidence are valid and there is
no concrete connector/auth/scheduler/schema/artifact-access/user-decision or
workflow-contract failure.

Waiting does not consume `max_repair_rounds`, Critic lifecycle budget, heavy
Verifier rerun budget, blocked-audit attempts, or semantic invalidation budget.
Rounds and repair attempts move only after a fresh external decision for the
current `request_nonce` and `review_target_id`.

Stale Planner/Critic artifacts are historical context. A Planner finding,
Planner pass candidate, Critic freeze, or Final Critic audit bound to an old
`request_nonce` or `review_target_id` must not trigger repair, final pass, or
terminal block for the current target.

External-review `BLOCKED` requires observed evidence that waiting cannot recover
automatically, such as a disabled/deleted/expired scheduled automation,
repeated connector/auth failure, missing external role installation, invalid
repository state, inaccessible required artifacts, visual-review access
impossibility, a required user product/scientific/branch decision, or a
workflow-defined hard deadline.

---

## 9. Semantic source manifests and Stable Review Snapshot

This is a central v0.4 requirement.

### 9.1 Canonical implementation source manifest

Generate exactly one canonical manifest from Project Profile rules.

Example:

```json
{
  "schema": "AI_BRIDGE_IMPLEMENTATION_SOURCE_MANIFEST_V1",
  "task_key": "...",
  "paths": [
    {"path": "src/a.py", "sha256": "..."}
  ],
  "semantic_digest_sha256": "..."
}
```

Sort paths deterministically. Hash file content, not mtimes.

### 9.2 Canonical verifier source manifest

Same concept for verifier-owned semantic source.

Do not duplicate these path lists inside `SOURCE_SNAPSHOT.json`.

### 9.3 Source Snapshot

`SOURCE_SNAPSHOT.json` binds:

```text
task/request identity
frozen_contract_sha256
requirement_ledger_sha256
implementation_semantic_digest_sha256
verifier_semantic_digest_sha256
optional runtime/profile identity relevant to semantic review
review_target_id
created locator Git SHA(s)
```

The locator commit is audit metadata, not part of `review_target_id` unless a project explicitly declares a Git object itself as semantic source.

### 9.4 Review target

Use deterministic canonical JSON serialization for the semantic tuple and SHA-256 it.

Conceptually:

```text
review_target_id = sha256(canonical_json({
  task_identity,
  frozen_contract_sha256,
  requirement_ledger_sha256,
  implementation_semantic_digest_sha256,
  verifier_semantic_digest_sha256
}))
```

Do not include:

```text
CURRENT commit
Controller merge commit
receipt hashes
review packet hash
notifier hash
CI receipt commit
human-readable report commit
documentation-only files outside declared semantic source
```

Regression test this aggressively.

---

## 10. Change classification and incremental invalidation

Implement a deterministic change classifier independent from finding classification.

Required classes:

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

The Project Profile identifies semantic path groups and control-plane paths.

Minimum rerun policy:

```text
CONTRACT_CHANGED
  -> Critic re-freeze / new semantic target / dependent evidence invalidated

REQUIREMENT_LEDGER_CHANGED
  -> new semantic target / affected verifier/runtime evidence

IMPLEMENTATION_SOURCE_CHANGED
  -> affected runtime probes + heavy Verifier + CI

VERIFIER_SOURCE_CHANGED
  -> verifier tests/mutations + runtime probes required by changed oracle + CI when needed

RUNTIME_ENVIRONMENT_CHANGED
  -> environment-dependent evidence only

CI_WORKFLOW_CHANGED
  -> CI only

CONTROL_PLANE_ONLY_CHANGED
  -> schema/state/routing validation only

RECEIPT_OR_MANIFEST_ONLY_CHANGED
  -> lightweight provenance/Review Bundle validation only

CURRENT_OR_ROUTING_ONLY_CHANGED
  -> state validation only

DOC_ONLY_CHANGED
  -> no semantic evidence invalidation

NO_RELEVANT_CHANGE
  -> no rerun
```

The Controller must record the selected change class and rerun plan.

A second heavy Verifier run against the same `review_target_id` requires a recorded semantic invalidation reason. Tests should reject automatic repeated heavy runs caused only by Controller bookkeeping.

---

## 11. Review Bundle

`REVIEW_BUNDLE.json` is the compact current evidence packet for Planner and Final Critic.

It should contain references to current evidence required by the contract/ledger, not every historical artifact.

Minimum conceptual shape:

```text
schema
task_key
request_nonce
review_target_id
frozen_contract_sha256
requirement_ledger_sha256
implementation_semantic_digest_sha256
verifier_semantic_digest_sha256
required_evidence[]
ci_receipt when required
runtime_receipts when required
open_findings[]
previous_findings_summary or refs, not full history
bundle_sha256
```

Historical role/session/watchboard/smoke receipts remain audit history and should not be copied into every active bundle by default.

The bundle validator must reject evidence bound to a different semantic target when the evidence type is target-sensitive.

---

## 12. Planner workflow

Reusable Planner prompt should read the repository's current schema and Project Profile each run.

### Initial planning

At `PLAN_REQUESTED`:

1. read objective and repository truth sources;
2. inspect required visual sources when profile says visual inspection is required;
3. read current implementation/history relevant to the objective;
4. produce a complete draft with no material product/scientific blanks;
5. write draft artifact;
6. transition to `PLAN_READY_FOR_CRITIC` last.

Planner must not implement code.

### Implementation review

At `READY_FOR_PLANNER_REVIEW`:

1. validate current semantic target/bundle;
2. inspect current implementation/verifier/evidence before prior findings;
3. classify current defects with typed findings;
4. only then read prior findings and check closure;
5. return:

```text
PLANNER_REVISE_EXECUTOR
PLANNER_REVISE_VERIFIER
PLANNER_REVISE_BOTH
PLANNER_PASS_CANDIDATE
```

If a real contract ambiguity/contradiction emerges, route to contract review rather than silently rewriting the frozen contract.

Planner should not turn ordinary implementation bugs into user questions. If
Planner cannot write a fresh decision for the current `review_target_id` in the
current run, leave `CURRENT` unchanged and report `waiting_external_review`.
Old Planner findings or pass candidates for a previous target are stale context
only.

---

## 13. Critic workflow

Reusable Critic prompt reads `critic_mode` from current state/profile.

### Initial audit

At `REQUIRED_INITIAL`:

- independently audit the Planner draft;
- directly repair deterministic omissions/ambiguity;
- create/freeze `FROZEN_CONTRACT.md`;
- create/freeze `REQUIREMENT_LEDGER.json`;
- ensure no unresolved material choices remain;
- write freeze artifact;
- update state last.

Only genuine competing scientific/product alternatives route to the user.

### Standby

At `STANDBY`, exit without writes/notification.

### Contract review

Invoke only when Planner identifies contract ambiguity/contradiction that cannot be resolved as an implementation or verifier bug.

### Final audit

At `REQUIRED_FINAL_AUDIT`, Final Critic audits closure, not implementation convenience.

At minimum check:

```text
frozen contract not silently weakened
Requirement Ledger not expanded by runtime roles
Planner did not leave a blocking requirement unresolved
Verifier did not create uncited blocking requirement/threshold
Executor did not add test-aware alternate behavior
prior Planner blockers have closure evidence
Review Bundle is bound to current review_target_id
required CI/evidence passes
no unresolved contract ambiguity/contradiction
```

Return:

```text
CRITIC_FINAL_PASS
CRITIC_FINAL_REVISE
```

Final Critic must not edit implementation/verifier code.

If Critic or Final Critic has not produced a fresh artifact for the current
`request_nonce`/`review_target_id`, Controller must wait. Silence and stale
Critic artifacts are not `BLOCKED` and do not consume repair or heavy-verifier
budget.

---

## 14. Controller and role runner

v0.4 should implement a deterministic orchestration core without embedding project science.

### 14.1 Exact role identity

For Controller / Verifier / Executor, record exact session/thread identity when available.

Never use `--last` as the production resume identity.

A launcher adapter should return a normalized role receipt:

```text
role
session/thread id
runtime adapter
worktree path or portable worktree id
base semantic target / task nonce
allowed write scope
start/resume status
last produced role commit/evidence id
```

### 14.2 Worktree strategy and branch policy

The host policy says branch creation is user-controlled. Control must comply.

Default behavior:

- Controller uses current/already-authorized integration branch.
- Verifier and Executor get distinct worktrees.
- If no new role branches were explicitly authorized, create detached worktrees at the appropriate base commit.
- Role commits may be produced from detached HEAD and returned by exact commit SHA for Controller integration.
- Do not create a remote branch as a workaround.
- If a project genuinely requires persistent role branches, ask for explicit authorization before creating them.

Do not hard-code `develop`.

### 14.3 Integration

Only Controller integrates role changes into the authorized integration branch.

Integration order is determined by current typed task state, not by which role finishes first.

Before integrating, validate role authority/write scope. A role commit touching forbidden paths must be rejected/routed rather than silently merged.

### 14.4 Same-scope recovery

Controller automatically handles:

```text
CI retry when policy permits
runtime adapter failure
session resume/repair
provenance rebinding
receipt correction
state repair
```

without escalating to the user unless Planner has classified a real scientific/product choice.

---

## 15. Verifier behavior

Verifier should be created/frozen before Executor implementation for high-risk tasks when the Project Profile requires independent oracle design.

The verifier package may include:

```text
public tests
protected/independent known-bads
mutations
reference implementations/oracles
runtime probes
diagnostics
```

Generic core must support protected verifier details being omitted from Executor prompts while acknowledging this is process isolation, not a cryptographic security boundary.

A useful test hook is allowed only if it observes/disables the same ordinary path. An alternate test-only business path is forbidden.

The generic verifier framework should support both:

```text
blocking contract-bound checks
diagnostic-only observations
```

and keep that distinction machine-readable.

---

## 16. Executor behavior

Executor receives:

- frozen contract;
- Requirement Ledger entries relevant to implementation;
- public verification contract/tests as policy allows;
- current repair findings;
- authorized runtime boundaries;
- explicit forbidden workarounds.

Executor should not be shown protected mutation names/fixture details when avoidable.

Executor result must distinguish:

```text
source changes
runtime evidence
known incomplete items
operational failures
claims
```

Executor cannot self-promote to Planner/Final Critic PASS.

---

## 17. CI boundary

Generic hosted CI is a deterministic evidence layer.

It may validate:

- schema/state consistency;
- role authority/write-scope rules;
- source-manifest/snapshot consistency;
- stale target bindings;
- unit tests safe for the hosted runner;
- Review Bundle format;
- anti-overengineering invariants.

It must not pretend to validate private data, unavailable hardware, external protected services, or domain-specific scientific fidelity that the runner cannot execute.

Green CI is necessary when Project Profile requires it, but not sufficient for Planner/Final Critic PASS.

---

## 18. Notifier integration

Reuse v0.3 notifier commands and configuration.

Control should emit a terminal brief only at configured terminal/user-decision states, especially:

```text
AWAIT_HUMAN_DECISION
NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE
STOPPED_MAX_ROUNDS
```

Normal states such as CI running, Planner waiting, Critic standby, implementation repair, verifier repair, provenance repair and runtime retry should not send terminal email by default.

The notifier consumes state; it does not decide state.

The generic notifier's structured milestone path is available for other
workflows that explicitly opt in, but it does not change Control's default
notification policy. Control still emits notifier briefs only for true
terminal/user-decision states unless a future Project Profile explicitly
defines a narrower milestone policy.

---

## 19. Host Policy integration

Control project installation must not modify `$CODEX_HOME`.

The existing Host Policy remains the source of user-level behavior, including:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
approvals_reviewer = "auto_review"

[features]
default_mode_request_user_input = true
memories = true
```

and global AGENTS policies for Chinese narrative, material ambiguity questions, Git branch creation and dangerous Git operations.

If role-specific CODEX_HOME isolation is enabled by a Project Profile/runtime adapter, the implementation must document how host defaults are inherited or intentionally overlaid. It must not silently create weaker role homes.

---

## 20. Deterministic validation

Prefer Python standard library for generic schema/validation logic where practical.

`ai-bridge agent-flow validate` should detect at least:

- malformed/missing task/request/current pair;
- invalid task key/nonce/state;
- nonexistent contract/ledger refs for states that require them;
- role authority overlap;
- same Verifier/Executor session when separation is required;
- same worktree for isolated roles;
- Controller attempting implementation/verifier edits;
- Verifier blocking finding without requirement binding;
- Controller-originated scientific/product user escalation without Planner classification;
- stale Review Bundle target;
- duplicate semantic path definitions or source-manifest ambiguity;
- fake Verifier freeze without current evidence;
- invalid Final Critic transition;
- terminal pass without Final Critic in high-risk profile;
- branch configuration requesting creation without authorization metadata if the tool supports role branches.

Validation messages should identify the invariant and repair owner, not merely say `invalid`.

---

## 21. Anti-overengineering regression tests

These tests are mandatory because CARE showed that a reasoning model will otherwise keep adding provenance until the control plane dominates the task.

At minimum test:

1. Receipt-only change does not alter `review_target_id`.
2. `CURRENT.json`-only change does not trigger heavy Verifier.
3. Documentation-only change does not invalidate semantic evidence.
4. Controller integration/receipt commit with identical semantic source does not alter target.
5. Control-plane-only lifecycle change does not restart Executor/Verifier.
6. Runtime evidence cannot directly or indirectly hash itself.
7. One canonical implementation source manifest supplies the implementation digest.
8. One canonical verifier source manifest supplies the verifier digest.
9. Review Bundle excludes superseded historical smoke by default.
10. Verifier cannot create an uncited blocking threshold.
11. Verifier diagnostic can remain diagnostic despite a large numeric difference.
12. Controller cannot map Verifier FAIL directly to user choice.
13. Executor test-aware alternate behavior is rejected.
14. Fake Verifier freeze after only a worktree fast-forward is rejected.
15. Contract ambiguity routes to Planner/Critic.
16. Ordinary implementation bug does not invoke Critic.
17. Planner cannot final-pass without current Final Critic in high-risk mode.
18. Final Critic cannot edit implementation.
19. A second heavy Verifier run against unchanged target requires an explicit semantic invalidation reason.
20. Provenance-only repair uses lightweight validation.
21. UI/status projection prefers authoritative typed state over historical keywords.
22. Generic profile contains no CARE/MyoPS/nnU-Net/Slurm-required field.
23. Control install creates no Git branch.
24. Detached role worktree strategy functions without new branch creation in the generic test harness.

---

## 22. Portability acceptance profiles

At least two non-CARE profiles must ship under examples/tests.

### Toy A — Python library

Exercise:

```text
Planner draft
-> Critic freeze
-> Verifier oracle
-> Executor implementation bug
-> Verifier finding
-> Planner repair
-> Executor correction
-> Stable Review Snapshot unchanged for receipt-only update
-> Planner pass candidate
-> Final Critic pass
-> human gate
```

Inject at least one fake Verifier freeze and one uncited verifier threshold; both must fail correctly.

### Toy B — small application/data processor

Exercise:

```text
Project Profile
-> implementation + verifier semantic manifests
-> control-plane-only change
-> no heavy rerun
-> real contract ambiguity
-> Planner/Critic contract review
-> new semantic target
-> implementation repair
-> final pass
```

No GPU, Slurm, medical data or private services should be needed.

---

## 23. Backward compatibility

v0.4 must preserve:

```text
ai-bridge
ai-bridge init
ai-bridge validate
ai-bridge prompt
ai-bridge where
ai-bridge host ...
ai-bridge notifier ...
```

Existing initialized repositories must remain valid without adopting Control.

Do not change Lite task/result mapping simply to reuse Control state.

Control may reference the same `task_key` and `results/<task_key>/` convention, but its control-plane files are additive.

---

## Optional shared Visual Review evidence

Control may opt into the shared Bridge Kit Visual Review evidence producer through Project Profile `optional_visual_source_policy`. This policy is the canonical visual configuration surface; do not add a competing Control-specific visual review client or a new visual role.

Default policy:

```json
{
  "enabled": false,
  "manifest_path": ""
}
```

When enabled, `VISUAL_REVIEW.json` is review evidence. It must be bound to the current Control identity:

```text
task_key
request_nonce
review_target_id
frozen_contract_sha256
requirement_ledger_sha256
implementation_semantic_digest_sha256
verifier_semantic_digest_sha256
input image SHA-256 values
visual manifest / rubric identity
```

Visual Review evidence must not change `review_target_id`, must not trigger heavy Verifier rerun by itself, and should classify as evidence / receipt / manifest change unless a Project Profile explicitly makes some visual configuration file a semantic source. Controller owns only mechanical checks: whether visual review is required, whether the evidence exists, whether it binds the current target, and whether the Review Bundle references it. Controller must not judge visual quality.

Verifier may produce deterministic visual-adjacent evidence such as render success, file existence, image dimensions, corruption checks, blank detection, and expected artifact presence when those checks derive from frozen requirements. Verifier must not pretend those checks are model visual judgment.

Planner consumes current `VISUAL_REVIEW.json` alongside the frozen contract, Requirement Ledger, Verifier evidence, implementation evidence, CI, and Review Bundle. Final Critic checks that visual evidence belongs to the current target and that Planner did not ignore a blocking visual requirement; it does not become a visual designer.

Default privacy policy is `PUBLIC_SAFE_ONLY`. If `external_boundaries.requires_private_data=true`, Visual Review must fail closed unless `optional_visual_source_policy.external_upload_authorization` explicitly permits external upload for the current project/task.

---

## 24. Versioning and recovery

Before v0.4 implementation changes begin, protect the current v0.3.1 baseline.

Current known baseline:

```text
package version: 0.3.1
main commit: edbc9bcf87cba80462bcc6c06d3938154c3f9e00
```

Required implementation workflow:

- check whether tag `v0.3.1` exists;
- if absent, create annotated `v0.3.1` pointing exactly to the baseline commit above and push the tag;
- if it exists at the same commit, reuse it;
- if it exists elsewhere, do not move/delete/overwrite it; report the conflict;
- do not create a new development branch without explicit user authorization;
- implement on the currently authorized branch;
- ordinary commit/push to `origin` is allowed under Host Policy;
- after v0.4 implementation/tests pass, bump package version to `0.4.0`;
- do not automatically create `v0.4.0` tag unless the user has explicitly authorized release tagging at that point.

---

## 25. Implementation sequence

Recommended order to control risk and avoid one giant unreviewable refactor:

### Phase A — schemas and pure logic

- templates/layout;
- Project Profile;
- Requirement Ledger validation;
- source manifests;
- Stable Review Snapshot;
- change classifier;
- typed routing;
- unit tests.

### Phase B — task/state CLI

- install/status/validate;
- task init;
- snapshot;
- bundle validation;
- deterministic state transition helpers.

### Phase C — role/controller interfaces

- exact session identity model;
- detached worktree strategy;
- role receipts;
- Controller routing/integration abstractions;
- no domain-specific runner assumptions.

### Phase D — Planner/Critic/Verifier/Executor prompt templates

- prompts read schemas/profile at runtime;
- initial Critic direct repair;
- Planner independent-current-review order;
- Final Critic lifecycle.

### Phase E — notifier + portability closure

- terminal notifier adapter;
- Toy A and Toy B;
- anti-overengineering tests;
- full old regression suite;
- README/migration docs.

Do not advance to later phases by weakening failed tests in earlier phases.

---

## 26. Completion definition for v0.4.0

v0.4.0 is complete when a user can initialize a normal repository exactly as before, optionally install Control, initialize a high-risk task without creating a branch, generate and validate a stable semantic target, route typed findings without Controller domain judgment, execute the control-plane lifecycle through the two non-CARE portability examples, perform Final Critic closure, and reach a terminal human gate without CARE-specific assumptions.

The release should make orchestration simpler than the CARE prototype. If the implementation requires users to reason about dozens of receipt hashes or manually repair normal session/CI/provenance transitions, it has failed the extraction goal even if all files technically exist.
