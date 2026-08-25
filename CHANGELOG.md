# Changelog

## Unreleased

- Add a read-only Reviewed Handoff watcher status view that reports task,
  state, Executor event, runtime type, optional thread id, start/completion
  timestamps, last exit/result, wait owner, and publication status from
  machine-local state.
- Keep Reviewed Handoff production Executor launches on the existing
  `codex exec` path after real Codex App/App Server probing showed connector
  task create/list/read/resume works but shell-facing app-server proxy did not
  provide a stable embeddable watcher lifecycle.
- Extend Generic Notifier with backwards-compatible structured briefs for
  semantic terminal/awaiting-human notifications, operational blocked
  notifications, and opt-in non-blocking milestone notifications under
  `results/<task_key>/notifications/*.json`.
- Enforce notifier ownership boundaries so semantic notification briefs must
  come from Planner/Reviewer/Critic/Final Critic, operational blocked briefs
  from Controller/watcher, and Executor cannot forge PASS or milestone
  conclusion emails.

## 0.6.0

- Add optional project-level Overleaf Bridge with
  `ai-bridge overleaf install|connect|status|push|pull|validate`.
- Keep Codex working in the whole research repository while publishing only the
  configured manuscript `paper_root` into a machine-local Overleaf Git mirror.
- Add baseline/local/remote content digest checks so push and pull fail closed
  on remote-ahead or diverged manuscript edits instead of overwriting
  collaborator changes.
- Store Overleaf connection metadata under
  `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/` while keeping
  tokens out of tracked config, `connection.json`, CLI flags, and normal output.
- Add local Git/bare-remote regression tests for bootstrap, projection
  flattening, excludes, deletion, pull import, divergence, equivalent content,
  token leakage, validation, and router compatibility.
- Harden first-consumer safety before TRACE adaptation by requiring a clean
  non-excluded publication root for connect/bootstrap/push/pull, refusing dirty
  or untracked manuscript pull overwrite risks, validating secret-like
  `connection.json` fields, and expanding the consumer Overleaf README.
- Detect the actual Overleaf remote branch during `connect` instead of assuming
  `master`, keeping the resolved branch in machine-local `connection.json` so
  projects using `main`, `master`, or another declared branch remain compatible.
- Validate the Overleaf Bridge path with a real research-repository bootstrap
  and bidirectional Overleaf pull/push smoke test.

## 0.5.4

- Change the Shared Visual Review production default model from
  `gpt-4.1-mini` to `gpt-5.6-terra` for generic, Reviewed Handoff, Agent-Flow,
  and future consumer repositories that do not set a model override.
- Keep `OPENAI_VISUAL_REVIEW_MODEL` as the optional repository/environment
  override, with explicit CLI `--model` still taking priority over the
  environment variable and shared default.
- Preserve the per-consumer `OPENAI_VISUAL_REVIEW_API_KEY` secret contract; the
  model default change does not introduce shared API keys or role-specific model
  configuration.

## 0.5.3

- Harden Visual Review GitHub Actions installation for consumer repositories by
  rendering a pinned canonical Bridge Kit Git source instead of installing the
  consumer repository with `pip install -e .`.
- Fix first-run Visual Review evidence write-back by staging the generated
  evidence path before checking the cached diff, so untracked
  `VISUAL_REVIEW.json` files are committed.
- Restrict generated visual evidence paths to repository-relative
  `results/<task_key>/visual_review/**` locations and ignore the full visual
  evidence directory in the workflow trigger to avoid evidence-only retriggers.
- Preserve the existing `OPENAI_VISUAL_REVIEW_API_KEY` secret contract and
  missing-secret skip behavior without changing role/state/schema/rubric scope.

## 0.5.2

- Add shared optional Visual Review core with a single `ai_bridge_kit.visual_review`
  implementation for visual source manifests, image SHA binding, OpenAI
  Responses API image input, Structured Outputs validation, and tracked
  `VISUAL_REVIEW.json` evidence.
- Add `ai-bridge visual-review install|preflight|run|validate`, GitHub Actions
  templates, and the standard `OPENAI_VISUAL_REVIEW_API_KEY` secret contract
  with metadata-only preflight.
- Wire Visual Review into Reviewed Handoff as lightweight
  `implementation_commit`-bound evidence that can wait without consuming review
  rounds.
- Wire Visual Review into Agent-Flow through existing
  `optional_visual_source_policy`, current `review_target_id` binding, Review
  Bundle evidence validation, and evidence-only change classification.
- Keep default behavior unchanged when visual review is not enabled and keep
  OpenAI SDK out of the default dependency set.

## 0.5.1

- Correct Host Policy Git authorization semantics: ordinary commits on the
  selected branch are preauthorized, safe `origin/main` fetch and fast-forward
  pull are preauthorized, ordinary task-owned staging and `origin/main` pushes
  remain preauthorized, and arbitrary remote branch pushes plus branch topology
  changes such as switch/checkout/worktree add/upstream setup/remote branch
  deletion now route to user confirmation.
- Expand Host Policy validation to exercise real `codex execpolicy check`
  outcomes for safe sync, staging, commit, ordinary push, unsafe pull, upstream
  push, branch mutation, destructive Git, remote mutation, and remote branch
  mutation commands.
- Add the generic External GPT wait contract across Host Policy, Reviewed
  Handoff, and Agent-Flow. External Planner/Reviewer/Critic silence now reports
  `waiting_external_review` instead of terminal blocking, with
  `MIN_EXTERNAL_GPT_WAIT = 2 hours` as a minimum grace period rather than an
  automatic deadline.
- Detect stale external decisions by the workflow's existing identity semantics:
  Reviewed Handoff compares `REVIEW_<n>.md` `implementation_commit` against the
  current `CURRENT.implementation_commit`, while Agent-Flow keeps using
  `request_nonce` and `review_target_id`. Stale reviews no longer replay old
  `REVISE` decisions or consume review/repair budget.
- Keep Reviewed Handoff watcher bounded retry for real Executor no-progress
  events, while reporting successful handoff states as
  `waiting_external_review` without incrementing local Executor attempts.

## 0.5.0

- Add Reviewed Handoff as a bounded middle workflow between Lite Handoff and high-risk Agent-Flow.
- Add GPT Planner -> Codex Executor -> Scheduled GPT Reviewer lifecycle with at most two review rounds and one scheduled Plan revision before human escalation.
- Add `ai-bridge reviewed-handoff ...` routing through a compatibility wrapper while preserving existing CLI implementation paths.
- Add a lightweight local Codex watcher for zero-touch `PLAN_FROZEN` / `REVISE` execution, with machine-local state, fast-forward-only branch sync, bounded retries, real state-progress detection, and visible operational blocking instead of endless retry loops.
- Add machine-validated Plan, Result, Review, CI-readiness, review-limit, and all-terminal final-report gates without importing Agent-Flow Requirement Ledger, Stable Review Snapshot, receipt graphs, or provenance hash chains.
- Add a Scheduled Task prompt that uses ChatGPT Automations plus GitHub-tracked `CURRENT.json` state instead of OpenAI API calls.
- Stabilize Reviewed Handoff CI authority and watcher publication semantics: CI-required execution now routes through `WAITING_FOR_CI`, `CURRENT.ci_status` is the single CI machine truth, Scheduled GPT uses the published branch tip as the real GitHub checks locator, and Executor publication remains watcher-owned.

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
- Close final provenance blockers by binding semantic snapshots to current
  frozen contract and Requirement Ledger hashes, requiring contract-review
  refreeze to produce a new semantic target before runtime repair resumes, and
  making production transition predicates reject `fake-test` role receipts.

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

## 0.2.1

- Bump the package version after Host Policy narrative-language work.
- Keep user-facing Host Policy guidance oriented around natural Simplified
  Chinese while preserving technical literals.

## 0.2.0

- Add Codex Host Policy management as a machine-level layer separate from
  repository handoff setup.
- Add `ai-bridge host install|status|validate` for `$CODEX_HOME` configuration,
  global `AGENTS.md` guidance, and low-friction safe Git policy rules.
- Keep project initialization focused on repository handoff files instead of
  silently changing machine-level Codex configuration.

## 0.1.0

- Add the initial Lite Handoff repository protocol for GPT-authored task files,
  Codex execution results, and GPT review.
- Add the base `prompts/tasks/<task_key>.md` and `results/<task_key>/result.md`
  workflow shape, with repository initialization and validation entry points.
- Add the repo-local Codex executor skill/frontmatter validation used by the
  early handoff flow.
