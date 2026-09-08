# AI Bridge Kit Host Policy

## Git Branch Policy

The user is usually the sole developer in these repositories, so branch topology
is a project decision controlled by the user.

- Continue working on the currently checked-out branch by default.
- Normal development on the currently checked-out branch is preauthorized:
  fetch `origin/main`, fast-forward pull the already selected `main` branch when
  the working tree is clean, stage task-owned files, create ordinary commits,
  and push to the explicitly allowed `origin/main` target without repeatedly
  asking the user.
- Check the working tree before synchronization. If it is dirty, determine
  ownership first. Do not default to `git pull --ff-only --autostash ...`,
  `git stash`, `git reset --hard`, or `git restore ...`.
- Before committing, inspect `git diff --cached --stat` and `git diff --cached`
  so unrelated files, generated noise, or secrets are not included.
- Do not create, switch, checkout, rename, delete, or otherwise change arbitrary
  Git branches without explicit user authorization for that branch strategy.
- **Review exception:** when a repository has multiple independent
  Review workflows, the user has authorized one task-owned branch per
  workflow using the deterministic name `reviewed/<task_key>`. Creating,
  selecting and continuing on that exact task branch is part of the authorized
  workflow strategy; do not repeatedly ask whether independent tasks may be
  separated merely because they share a repository.
- A `reviewed/<task_key>` branch is not authority to create unrelated branches,
  change remotes, create PRs, force-push, rewrite history, or choose a different
  integration strategy. If the requested branch does not correspond to the
  current Review task, ask the user.
- Until Bridge Kit provides a first-class bounded task-branch helper, Git
  execpolicy may still surface an approval/user-input interaction for branch
  creation or first push. Treat that as a recoverable authorization interaction,
  not a reason to mark the workflow `BLOCKED`.
- Large scope, many files, incomplete implementation, perceived PR safety, or a
  clean `main` baseline are not independent authorization to invent a branch.
- If the user explicitly selected an existing branch, continue on that branch
  without asking repeatedly.
- Do not create pull requests unless requested.
- Branch topology and branch selection are user decisions; ordinary commits on
  the selected branch are not branch decisions.
- Never rebase pull, autostash pull, force push, use `--force-with-lease`,
  delete remote branches or tags, reset/clean/restore user work, or
  modify/add/remove/remap Git remotes without explicit authorization.

Even if a broad execpolicy rule technically matches a dangerous Git command,
these behavior rules remain binding and must not be bypassed.

## Production Plugin Replay

When the user or a frozen repository workflow has authorized local production
plugin repair/replay, and the task genuinely requires a fresh Codex runtime to
exercise an installed production plugin, use `ai-bridge plugin-replay`.

- Do not assemble a raw nested `codex exec` command and request approval for it
  when the bounded replay wrapper fits the task.
- Private replay inputs must be explicit files inside the target Git repository
  or the fixed machine-local trusted inbox
  `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/inbox/`; do not pass
  arbitrary private absolute paths, recursively ingest parent directories, or
  discover adjacent private files.
- Replay outputs remain machine-local under
  `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/`.
- `plugin-replay` uses the current Codex identity; it is not authority to switch
  to another `CODEX_HOME`.
- Treat plugin replay as write-isolated / execution-bounded trusted-local
  replay. Current Codex runtimes may still read other same-user readable files;
  the wrapper records that read-scope diagnostic honestly and does not claim
  strict filesystem read isolation.
- This authorization does not grant publishing, external upload, dangerous Git,
  branch/remote mutation outside the dedicated Review branch policy,
  release, deployment, or product/scientific scope expansion authority.

## Remote SSH / Production Tunnel Safety

Codex Desktop Remote SSH can generate sustained multi-MB/s transport traffic
because of app-server/application-layer behavior. Do not assume that the SSH,
Cloudflare, Tailscale, jump-host, or other transport carrying those bytes is the
root cause.

- Production server tunnels and SSH infrastructure are not ordinary diagnostic
  knobs. Do not kill, restart, disable, delete, recreate, or rewrite production
  server tunnels/services as a workaround for Codex Remote SSH bandwidth,
  reconnect, app-server, or WebSocket problems unless the user explicitly
  authorizes that server-side infrastructure change in the current task.
- If an environment/project policy declares a production tunnel set immutable,
  that constraint is absolute. Prefer read-only server inspection and
  client-local evidence collection.
- If interruption is necessary and authorized, target only the affected local
  Remote SSH session/process. Do not broadly kill unrelated `ssh`, `cloudflared`,
  Tailscale, or other transport processes.
- Diagnose the remote Codex identity separately from the transport. Resolve the
  actual remote `$CODEX_HOME`, inspect `codex features list`, and correlate
  app-server/Desktop timestamps before changing network topology.
- A known Remote SSH regression can cause repeated Apps/App Directory payloads
  when remote `apps=true`. When sustained app-server/SSH traffic is reproduced
  and Apps are not required on that remote identity, the preferred current
  workaround is `codex features disable apps`, followed by reconnecting only the
  affected client Remote SSH session. This is a Codex feature-state workaround,
  not authority to restart production tunnels.
- Do not disable `plugins`, `remote_plugin`, or other feature surfaces merely by
  analogy. Very large `plugin/list` responses plus WebSocket `1006` are a
  separate failure class and require matching evidence before mitigation.
- After a Codex Desktop/remote runtime upgrade or remote `$CODEX_HOME`
  replacement, re-check relevant feature state and perform a short idle/light
  workload bandwidth sanity check. Sustained MB/s traffic should be investigated
  rather than accepted as normal Remote SSH overhead.

See `docs/design/remote_ssh_bandwidth_guardrail.md` for the evidence model and
upstream issue references.

## User Input Policy

Because host policy enables `default_mode_request_user_input`, ask the user when
ambiguity would materially change architecture, project scope, destructive
actions, branch/integration strategy, deployment strategy, externally visible
behavior, scientifically meaningful substitutions or degradation, or
irreversible and difficult-to-reverse decisions.

Routine implementation details, local refactoring choices, and clearly
reversible small decisions do not require repeated interruption.

Codex must preserve the task's original completion semantics. Do not silently
weaken required data, method, pretrained/model source, budget, execution entry,
tool, renderer, artifact identity, requested scale, or quality bar. A fallback
or proxy counts as original completion only when the GPT-authored task/Plan
explicitly authorizes it as equivalent and names the evidence for that
equivalence; otherwise report it as degraded, diagnostic, partial, or
incomplete evidence, limit the claim scope, and use the existing
`NEEDS_GPT_PLANNER`, `NEEDS_EVIDENCE`, or `STOP` routes.

For long-running goals and repository workflows, **a recoverable question is not
a terminal blocker**. If a path, artifact identity, credential confirmation,
branch/integration choice, or other bounded user decision can unblock progress,
use `request_user_input` / ask the user when an interactive channel is available
and preserve the workflow state. If the issue belongs to a frozen Plan, route it
to the workflow Planner instead. Do not write `BLOCKED` simply because asking is
less convenient than terminating the current run.

## External Planner / Reviewer Waiting

When a repository-controlled workflow says the next action belongs to an
external GPT Planner, Reviewer, Critic, Final Critic, or equivalent reasoning
role, absence of a fresh decision is normal waiting, not implementation
failure.

- Treat `WAITING_FOR_EXTERNAL_GPT` as a generic operational condition, even when
  the repository uses more specific states such as `READY_FOR_GPT_REVIEW`,
  `NEEDS_GPT_PLANNER`, `READY_FOR_PLANNER_REVIEW`, or
  `READY_FOR_CRITIC_FINAL_AUDIT`.
- Independent workflows on dedicated `reviewed/<task_key>` branches must not be
  serialized merely because another task branch is waiting for CI, Planner,
  Reviewer, visual evidence or user input. Continue other independent task
  branches normally.
- Wait at least `MIN_EXTERNAL_GPT_WAIT = 2 hours` from the first published handoff
  into the external-GPT-owned state. Two hours is a minimum normal grace period,
  not an automatic blocking deadline for that task branch.
- After two hours, keep waiting if the repository state is valid, the
  implementation/result artifacts are intact, and there is no concrete
  connector, authentication, scheduler, schema, artifact-access, user-decision,
  or workflow-contract failure.
- Use low-frequency status checks only for the task branch that is actually
  waiting. Do not use low-frequency waiting on one branch as a reason to idle
  unrelated branches.
- Stale Planner/Reviewer/Critic artifacts are not new decisions. A review whose
  `reviewed_commit`, `implementation_commit`, `review_target_id`, snapshot
  identity, or current round does not match the current implementation/review
  target must be treated as stale and must not trigger repair again.
- Pure waiting must not consume `review_round`, `repair_round`,
  `plan_revision`, `retry_count`, `critic_round`, blocked-audit attempts, or
  Executor retry budget. Rounds advance only when the external role writes a
  fresh decision, and repair budget advances only when Codex executes a fresh
  `REVISE`.
- If the current Codex activity cannot remain alive, report
  `waiting_external_review` and leave the repository tracked workflow state
  unchanged. Do not write terminal `FINAL_REPORT.md`, do not change the workflow
  state to `BLOCKED`, and do not ask the user to reset the task.
- `BLOCKED` is a last-resort state. Use it only when observed evidence shows
  that normal waiting, Planner re-entry, user input, Host Policy-authorized
  operation, or bounded recovery cannot resolve the condition. Disabled/deleted
  external automation, repeated connector/authentication failure, invalid
  repository state with no safe migration, inaccessible required artifacts with
  no recovery path, or a genuinely impossible visual-review environment are
  examples. A merge conflict, approval prompt, missing-but-locatable artifact,
  or answerable user question is not automatically `BLOCKED`.

## User-Facing Narrative Language

- Unless the user explicitly requests another language, all user-facing
  narrative must be written in natural Simplified Chinese.
- This applies to progress updates, execution-status explanations, plans and
  plan updates, summaries of objectives or requirements, clarification
  questions, approval questions, risk explanations, test/result summaries,
  completion reports, failure/blocker explanations, and ordinary conversational
  responses.
- Do not switch to English merely because the Goal objective is written partly
  or entirely in English, the objective is loaded from an attachment or
  `goal-objective.md`, repository files, commands, identifiers, or documentation
  are in English, or terminal output or upstream documentation is in English.
- Keep technical literals in their original form when translation would reduce
  precision, including code, shell commands, file paths, Git refs, configuration
  keys, YAML/TOML fields, protocol state names, API/function/class identifiers,
  exact error messages when quoting them, and product/model/library names.
- Repository artifacts are a separate concern from interactive narrative. Do
  not translate or rewrite repository files solely because user-facing narrative
  is Chinese. README files, source comments, documentation, papers, prompts,
  protocol files, commit messages, and other artifacts should follow the
  repository/task-specific language policy unless the user explicitly requests
  otherwise.
- When reporting technical evidence, explain its meaning in Chinese first when
  useful, then preserve the exact English command, identifier, error, or log
  excerpt needed for precision.
