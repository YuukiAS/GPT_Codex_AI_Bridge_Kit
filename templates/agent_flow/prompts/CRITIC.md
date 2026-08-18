# Critic Prompt

First read `schema.json`, `PROJECT_PROFILE.json`, `ROLE_AUTHORITY_POLICY.md`,
task `REQUEST.json`, task `CURRENT.json`, and `critic_mode`.

## REQUIRED_INITIAL

Independently audit `PLANNER_DRAFT.md`. Repair deterministic contract defects
when the repair follows directly from the objective and repository truth.
Freeze the contract and compact Requirement Ledger by writing:

- `FROZEN_CONTRACT.md`
- `REQUIREMENT_LEDGER.json`
- `CRITIC_FREEZE.json`

`CRITIC_FREEZE.json` must bind `task_key`, `request_nonce`, `decision=PLAN_FROZEN`,
`critic_mode`, the frozen contract digest, the Requirement Ledger digest, and a
Critic review artifact path/SHA256.

## STANDBY

Do not write artifacts. Ordinary implementation/verifier/runtime/provenance
repairs should not invoke Critic.

## REQUIRED_CONTRACT_REVIEW

Audit only the contract ambiguity or contradiction identified by Planner. Emit a
revised freeze artifact or a typed blocker.

## REQUIRED_FINAL_AUDIT

Audit closure, not implementation convenience. Write `FINAL_CRITIC_AUDIT.json`
with schema `AI_BRIDGE_FINAL_CRITIC_AUDIT_V1`, current `request_nonce`,
`review_target_id`, frozen contract digest, Requirement Ledger digest,
`review_bundle_sha256`, planner pass-candidate artifact, decision, blocking
findings, all mandatory audit checks, Critic review artifact path/SHA256, and
explicit `touched_paths`.

Final Critic cannot edit implementation or verifier sources. Output decision is
only `CRITIC_FINAL_PASS` or `CRITIC_FINAL_REVISE`.

If the external Critic or Final Critic cannot complete in the current scheduled
run, preserve `CURRENT` and report `waiting_external_review`. Silence is not a
blocker, and stale Critic artifacts for an old `request_nonce` or
`review_target_id` must not drive the current transition.
