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

## READY_FOR_PLANNER_REVIEW

Review current reality before prior findings:

1. frozen contract and Requirement Ledger;
2. `SOURCE_SNAPSHOT.json`;
3. implementation semantic manifest and current implementation;
4. verifier semantic manifest and current verifier;
5. current runtime/CI evidence and `REVIEW_BUNDLE.json`;
6. independent judgment;
7. only then previous findings and closure evidence.

Emit exactly one machine artifact:

```text
PLANNER_REVIEW.json
```

Allowed decisions:

- `PLANNER_REVISE_EXECUTOR`
- `PLANNER_REVISE_VERIFIER`
- `PLANNER_REVISE_BOTH`
- `PLANNER_PASS_CANDIDATE`
- `SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED`

For `PLANNER_PASS_CANDIDATE`, also write `PLANNER_PASS_CANDIDATE.json` bound to
the current `review_target_id`.

