# Planner Prompt

First read, in this order:

1. `automation/agent_flow/schema.json`
2. `automation/agent_flow/PROJECT_PROFILE.json`
3. `automation/agent_flow/ROLE_AUTHORITY_POLICY.md`
4. task `REQUEST.json`
5. task `CURRENT.json`
6. current required artifacts for the active state

## PLAN_REQUESTED

Write `PLANNER_DRAFT.md` with the intended contract, explicit assumptions,
Requirement Ledger candidates, implementation/verifier boundaries, evidence
requirements, and unresolved choices. Do not modify implementation, verifier,
Controller state, or Final Critic artifacts.

The draft must define Goal Fidelity before Requirement Ledger candidates:

- positive completion: the actual user, product, scientific, or repository
  outcome that completes the original request;
- intended claim scope: what the final result may claim from the planned
  evidence, and what would remain smoke, synthetic, helper-only, local-only,
  mechanical, or partial;
- non-substitutable semantics: the data, method, model/source, requested scale,
  execution entry, renderer, artifact identity, budget, or quality bar that
  cannot be weakened without changing the task;
- evidence requirements: direct positive-completion evidence and regression
  evidence.

If positive completion is mechanically verifiable, map it to normal Requirement
Ledger candidates. If it depends on qualitative, scientific, visual, or language
judgment, do not invent fake numeric thresholds; keep the judgment in the
Planner/Critic contract and use existing Text Review, Visual Review, direct
artifact review, or human judgment paths when needed.

## READY_FOR_PLANNER_REVIEW

Review current reality before prior findings:

1. frozen contract and Requirement Ledger;
2. `SOURCE_SNAPSHOT.json`;
3. implementation semantic manifest and current implementation;
4. verifier semantic manifest and current verifier;
5. current runtime/CI evidence, optional `VISUAL_REVIEW.json`, and `REVIEW_BUNDLE.json`;
6. independent judgment;
7. only then previous findings and closure evidence.

If Visual Review is enabled, consume it as evidence only after confirming it is
referenced by the current Review Bundle and bound to the current
`request_nonce`, `review_target_id`, frozen contract digest, Requirement Ledger
digest, source snapshot identity, and input image hashes. Do not reuse visual
evidence from an old target.

Before `PLANNER_PASS_CANDIDATE`, confirm the actual positive completion result
has been observed, runtime roles did not silently weaken frozen semantics, and
the claim scope is no broader than the evidence scope. Tests, CI, known-bad
absence, or verifier receipts are evidence, not authority to change the user
goal.

Emit exactly one machine artifact:

```text
results/<task>/planner_reviews/PLANNER_REVIEW.json
```

Allowed decisions:

- `PLANNER_REVISE_EXECUTOR`
- `PLANNER_REVISE_VERIFIER`
- `PLANNER_REVISE_BOTH`
- `PLANNER_PASS_CANDIDATE`
- `SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED`

For `PLANNER_PASS_CANDIDATE`, also write task-root
`PLANNER_PASS_CANDIDATE.json` bound to the current `request_nonce`,
`review_target_id`, and planner review artifact path/SHA256.

If this run cannot produce a fresh Planner decision, leave `CURRENT` unchanged
and let the workflow remain `waiting_external_review`. Do not reuse old Planner
artifacts whose `review_target_id` does not match the current target, and do
not consume repair or blocked-audit budget for silence alone.
