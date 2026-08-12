# Changelog

## 0.4.0

- Add Optional Agent-Flow Core with Project Profile installation, task
  initialization, Requirement Ledger validation, canonical implementation and
  verifier source manifests, Stable Review Snapshot, Review Bundle validation,
  deterministic change classification, typed finding routing, Final Critic
  gate checks, detached worktree planning, and terminal notification brief
  generation for existing Generic Notifier.
- Add `ai-bridge agent-flow ...` CLI commands while keeping Lite Handoff, Host
  Policy, Private Bootstrap, and Generic Notifier backward compatible.
- Convert CARE Agent-Flow lessons into generic regression and portability tests
  without requiring CARE, GPU, Slurm, medical data, fixed branches, private
  paths, or external services.
- Tighten Agent-Flow lifecycle validation with fail-closed state predicates,
  bound Final Critic artifacts, role/session authority checks, multi-change
  invalidation, heavy Verifier rerun guards, terminal brief generation, and CI.
- Close Agent-Flow state-machine authority gaps with a schema-backed transition
  graph, task nonce envelope validation, required evidence file/SHA checks,
  unified current findings, mandatory Final Critic audit checks, and real Toy
  A/B E2E repair lifecycle tests.
- Close final v0.4.0 release blockers for stale semantic snapshots, explicit
  contract-review refreeze gates, role commit provenance, evidence artifact
  semantic binding, single current findings truth, machine review write
  authority, and runtime role receipt predicates.

## 0.3.1

- Change Generic Notifier email subjects and bodies to Chinese-first narrative
  by default while preserving technical literals such as task keys, file paths,
  branch names, and commit/push status values.

## 0.3.0

- Add Generic Notifier with one-shot terminal brief sends, optional polling,
  local dedup/retry state, dry-run, and Gmail SMTP STARTTLS email.
- Add pull-only private notifier config sync from an existing rclone source.
- Add public notifier/private templates and shared Codex config profile docs.
- Keep Lite Handoff backward compatible.
- Keep Agent-Flow v3 as design-only TODO pending CARE closure.
- Record redacted real Gmail notifier E2E receipt in
  `docs/releases/0.3.0_notifier_e2e_redacted.json`.
