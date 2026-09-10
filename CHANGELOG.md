# Changelog

## Unreleased

## 0.8.0

- Add Persistent Run as an optional project capability for explicitly authorized
  long-running Goals that need a canonical tmux persistence contract.
- Add `ai-bridge persistent-run install`, `ai-bridge persistent-run validate`,
  and `ai-bridge persistent-run prompt kickoff` without adding a fourth
  workflow, new role, watcher, state machine, daemon, scheduler command, or
  global Host Policy allow rule.
- Install only `automation/persistent_run/README.md`,
  `CONTRACT_TEMPLATE.md`, `KICKOFF_TEMPLATE.md`, and one root `AGENTS.md`
  managed block while preserving user-owned AGENTS content and remaining
  independent of Lite / Review / Control.
- Keep completion authority with the original Goal/task/workflow: tmux session,
  Slurm job, PID, heartbeat, checkpoint, or lock evidence proves state, not
  completion.
- Add unit coverage for install/validate/kickoff path safety, idempotence,
  no-Lite installation, no `$CODEX_HOME` or `.codex/rules` writes, and top-level
  CLI routing.

## 0.7.4

- Add an authorized one-call paid-review extension campaign for pre-request
  unsent-call recovery after a parent campaign has already used its normal
  immutable two-call budget.
- Keep the parent ledger read-only: extension accounting never mutates the
  parent contract, deletes parent reservations, resets historical actual cost,
  or treats a historical non-default parent contract as writable.
- Store the extension under the deterministic child identity
  `<parent>__authorized_extension_1`, require a non-secret human authorization
  receipt, allow exactly one call, disable automatic paid retry, and keep the
  same reviewed Terra model/pricing/service-tier/tools/cache contract.
- Fail closed before `/v1/responses` when the parent is missing, has unverified
  accounting, exceeds aggregate reserved-cost safety, lacks explicit extension
  authorization, or when the child extension has already reserved its one call.
- Include parent/extension identities and aggregate reserved-cost accounting in
  Text Review / Visual Review paid-review receipts.

## 0.7.3

- Reduce reproduced Auto-review false positives for read-only process
  inspection, routine configured-remote Git synchronization, and read-only tmux
  session inspection.
- Add Host Policy execpolicy allow rules for direct `ps`,
  `git fetch --all --prune`, and `tmux ls` / `tmux list-sessions` /
  `tmux has-session` while preserving the existing 0.7.2 Slurm read-only
  allowlist.
- Keep process mutation, resource allocation, Slurm mutation, tmux mutation,
  arbitrary Git fetch forms, generic shell, generic Python, dangerous Git, and
  unrelated unattended orchestration on the existing approval path.
- Extend `ai-bridge host validate` and real Codex execpolicy tests to prove the
  new positive and negative decisions through generated installed rules.

## 0.7.2

- Extend Host Policy execpolicy rules for direct read-only Slurm inspection:
  `squeue`, `sinfo`, `sacct`, `sstat`, `sprio`, `scontrol show ...`, and
  `scontrol ping` no longer require repeated approval on configured hosts.
- Keep Slurm resource allocation, job mutation, scheduler mutation, mutating
  `scontrol`, `sacctmgr modify`, and shell-composed commands on the effective
  approval path, without adding broad shell, Python, script, or HPC allowlists.
- Extend `ai-bridge host validate` and real Codex execpolicy regression tests
  to prove the new positive and negative Slurm decisions through generated
  installed rules rather than Starlark text inspection alone.

## 0.7.1

- Bump current Review Plan artifacts to `AI_BRIDGE_REVIEWED_PLAN_V2`, the Goal
  Fidelity Plan contract introduced by the 0.7 series.
- Keep structurally valid `AI_BRIDGE_REVIEWED_PLAN_V1` frozen Plans compatible
  for repository-wide validation, watcher continuation, and historical tasks
  without mutating old task history.
- Require every new `PLAN_REQUESTED -> PLAN_FROZEN` and
  `NEEDS_GPT_PLANNER -> PLAN_FROZEN` transition to use V2, so current freeze
  paths cannot bypass Goal Fidelity by writing a new V1 Plan.
- Preserve the existing Review workflow schema, CURRENT schema, roles, state
  graph, review/plan limits, Text Review, Visual Review, watcher publication,
  Lite, Control, Host Policy, and Project State Bridge boundaries; no migration
  state, role, watcher, ledger, or consumer rewrite was added.

## 0.7.0

- Add Goal Fidelity / anti-degradation guidance across Lite, Review, and
  Control so completion claims must be supported by the original positive
  result, non-substitutable semantics must not be silently weakened, and final
  claim scope must stay within evidence scope.
- Rewrite the generic Lite `MECHANISM_GATE_TEMPLATE.md` and update task,
  ChatGPT, Codex, review, and Host Policy wording to treat fallbacks, proxies,
  toy/synthetic data, helper-only paths, handmade artifacts, reduced scale, and
  blacklist-only checks as partial/diagnostic evidence unless explicitly
  authorized as equivalent.
- Extend the Review `PLAN.md` template with required
  `## Positive completion` and `## Non-substitutable semantics` sections, and
  require the existing Plan freeze validator to reject 0.7 Plans missing either
  section before `CURRENT.state=PLAN_FROZEN`.
- Update Review Planner, Executor, and Reviewer prompts with semantic red-team,
  fallback/deviation handling, positive-completion checks, and evidence-scope
  limits while keeping roles, state graph, schema, CLI paths, workflow type, and
  watcher behavior unchanged.
- Update Control Planner, Critic, Executor, and Verifier prompts so frozen
  contracts record positive completion, claim scope, non-substitutable
  semantics, and evidence requirements without adding roles, states, schema
  fields, Requirement Ledger changes, verifier rounds, or default API costs.
- Rename the Project State Bridge document to
  `docs/PROJECT_STATE_BRIDGE_ROADMAP.md`, mark it as an unversioned future
  roadmap, and leave Project State Bridge implementation out of this release.

## 0.6.1

- Simplify workflow display names to Lite / Review / Control without changing
  compatibility identifiers or workflow semantics.
- Add `ai-bridge text-transform` as a sibling private UTF-8 Markdown/plain-text
  transform transport: local age encryption publishes only ciphertext,
  manifests, and output public recipients; GitHub Actions decrypts source text
  ephemerally, calls OpenAI Responses API with `store=false`, encrypts the
  generated plaintext back to a local-only output receiver, and writes only
  `output.age` plus `TEXT_TRANSFORM.json` metadata to Git.
- Allow `text-transform` instruction bundles to include UTF-8 JSON files, while
  keeping private source inputs limited to Markdown/plain text.
- Add `ai-bridge text-review` for private UTF-8 Markdown/plain-text artifact
  review: local age public-key encryption publishes only encrypted payloads
  and manifests, GitHub Actions decrypts ephemerally with
  `AI_BRIDGE_PRIVATE_REVIEW_AGE_KEY`, OpenAI Responses API runs with
  `store=false`, and `TEXT_REVIEW.json` records structured findings bound to
  manifest identity and plaintext SHA-256 without storing private plaintext.
- Extend Review with task-local `text_review_required` evidence
  gates so missing, malformed, stale, wrong-plaintext, or non-PASS Text Review
  evidence cannot support PASS and does not consume review rounds while
  evidence is pending.
- Narrow the Visual Review GitHub Actions trigger to `visual_inputs.json`
  changes or manual dispatch so ordinary non-visual tasks no longer display a
  misleading AI Bridge Visual Review PASS job.
- Add `ai-bridge plugin-replay` as a Host Policy-controlled production plugin
  replay wrapper. It stages only explicit files into a machine-local isolated
  run directory, launches child Codex with fixed `workspace-write` /
  `approval_policy=never` / local-network-off settings, records local
  `run.json` metadata and output paths, and rejects arbitrary Codex flag
  passthrough.
- Harden `ai-bridge plugin-replay` before formal enablement: targets must
  resolve to Git repository roots, inputs must resolve inside the target repo
  or the fixed plugin-replay trusted inbox, task files are limited to the
  target repo / caller repo / trusted inbox, public CLI callers cannot switch
  `CODEX_HOME`, filesystem read scope is recorded as a diagnostic, and a
  write-isolation canary fails closed with
  `WRITE_ISOLATION_NOT_ENFORCEABLE` if child Codex can modify files outside
  replay writable roots.
- Extend Host Policy install/validate so
  `$CODEX_HOME/rules/ai-bridge-global.rules` pre-authorizes only the trusted
  `ai-bridge plugin-replay` executable path while raw `codex exec`, broad
  shell/python, destructive Git, branch mutation, remote mutation, and force
  push remain under the existing approval behavior.
- Harden Scheduled GPT terminal transactions for Review by requiring
  a runtime `FINAL_REPORT.md` template preflight before PASS, BLOCKED, or
  human-gate `CURRENT.json` writes.
- Correct the Review visual-review lifecycle for CI-required visual
  tasks: `WAITING_FOR_CI` may carry a valid visual input manifest with pending
  evidence while CI owns the wait, `READY_FOR_GPT_REVIEW` then waits for visual
  evidence without consuming review rounds, and PASS states still require fresh
  visual PASS evidence.
- Keep repository-wide Review validation backward compatible with
  historical terminal `AI_BRIDGE_REVIEWED_FINAL_REPORT_V1` reports that have
  valid frontmatter and substantive legacy sections, while keeping new terminal
  transitions strict against the current `FINAL_REPORT.md` template.
- Add a machine-local Review watcher lifecycle: `watcher start`,
  `watcher stop`, and `watcher restart` enforce one official watcher per
  `target + branch`, record PID/heartbeat/loaded Bridge Kit version and source
  commit, recover dead PID markers, and make `watcher status` report
  `restart_required` when the running watcher loaded older Bridge Kit code.
- Change preexisting dirty working trees from a persistent watcher fatal error
  into `dirty_worktree_wait`: the watcher still launches no Executor and does
  not stash/reset/commit/push, but it records dirty paths, sleeps with bounded
  low-frequency backoff, and resumes routing after the tree is externally
  restored to clean.
- Require `PLAN_FROZEN` to correspond to a structurally valid Review
  `PLAN.md`, including the required `## Out of scope` section, and
  update Planner/Scheduled Planner prompts to self-check the current PLAN
  template before publishing `CURRENT.state=PLAN_FROZEN`.
- Keep the Review persistent watcher alive on `invalid_workflow`
  validation failures: it now records the local status/error, refuses to launch
  Executor, sleeps with low-frequency bounded backoff, and resumes routing
  automatically after the remote workflow is repaired.
- Add a read-only Review watcher status view that reports task,
  state, Executor event, runtime type, optional thread id, start/completion
  timestamps, last exit/result, wait owner, and publication status from
  machine-local state.
- Record the 2026-08-26 Review Codex App/App Server visibility
  decision: official `codex app-server --stdio` can create durable cwd-bound
  threads that eventually appear in Codex App, but bounded live discovery was
  not verified, so production Executor launches remain on `codex exec`.
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
