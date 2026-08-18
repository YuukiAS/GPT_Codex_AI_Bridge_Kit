# Agent-Flow Core

This directory is installed only when a repository explicitly opts into
high-risk Agent-Flow control-plane workflow.

Lite Handoff remains the default Bridge Kit workflow. Agent-Flow adds a compact
role-authority model, Project Profile, Requirement Ledger, semantic source
manifests, Stable Review Snapshot, typed findings, deterministic routing,
transition predicates, Final Critic gate, and a terminal notification brief
handoff to the existing Generic Notifier.

Agent-Flow installation must not modify `$CODEX_HOME`, create branches, modify
remotes, start role sessions, or send notifier messages.

## External GPT wait contract

Agent-Flow follows the Bridge Kit generic external GPT wait contract. When
Controller/Executor/Verifier have produced the required artifacts and the next
state is owned by an external Planner, Critic, or Final Critic, silence is
`waiting_external_review`, not `BLOCKED`.

Common Agent-Flow states covered by this rule include `PLAN_REQUESTED`,
`PLAN_READY_FOR_CRITIC`, `READY_FOR_PLANNER_REVIEW`,
`WAITING_FOR_EXTERNAL_GPT`, `CONTRACT_REVIEW_REQUIRED`, and
`READY_FOR_CRITIC_FINAL_AUDIT`. The current `request_nonce` and
`review_target_id` remain the identity checks for fresh external artifacts.
Stale Planner/Critic artifacts for an old target are context only and must not
trigger repair or final pass.

`MIN_EXTERNAL_GPT_WAIT = 2 hours` is the minimum normal grace period, not a
blocking deadline. Waiting does not consume repair rounds, Critic rounds, heavy
Verifier budget, blocked-audit attempts, or semantic invalidation budget. Only
observable external failure evidence, invalid state, inaccessible required
artifacts, a required user decision, or a workflow-defined hard deadline may
produce a terminal blocker.
