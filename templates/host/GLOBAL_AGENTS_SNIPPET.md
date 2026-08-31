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
- Do not create, switch, checkout, rename, delete, or otherwise change Git
  branches without explicit user authorization for that specific branch action.
- This includes `git switch ...`, `git switch -c ...`, `git checkout ...`,
  `git checkout -b ...`, `git branch <new-branch>`, `git branch -d/-D/-m ...`,
  `git worktree add ...` when it creates or selects a branch, setting upstream,
  deleting remote branches, or creating a new remote branch because the current
  branch feels inconvenient to push.
- Large scope, many files, incomplete implementation, perceived PR safety, or a
  clean `main` baseline are not authorization to create a branch.
- Explain the risk and ask the user before creating a branch when branch
  strategy is ambiguous.
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
- Private replay inputs must be explicit files selected by the caller; do not
  recursively ingest parent directories or discover adjacent private files.
- Replay outputs remain machine-local under
  `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/`.
- This authorization does not grant publishing, external upload, dangerous Git,
  branch/remote mutation, release, deployment, or product/scientific scope
  expansion authority.

## User Input Policy

Because host policy enables `default_mode_request_user_input`, ask the user when
ambiguity would materially change architecture, project scope, destructive
actions, branch strategy, deployment strategy, externally visible behavior,
scientifically meaningful substitutions or degradation, or irreversible and
difficult-to-reverse decisions.

Routine implementation details, local refactoring choices, and clearly
reversible small decisions do not require repeated interruption.

## External Planner / Reviewer Waiting

When a repository-controlled workflow says the next action belongs to an
external GPT Planner, Reviewer, Critic, Final Critic, or equivalent reasoning
role, absence of a fresh decision is normal waiting, not implementation
failure.

- Treat `WAITING_FOR_EXTERNAL_GPT` as a generic operational condition, even when
  the repository uses more specific states such as `READY_FOR_GPT_REVIEW`,
  `NEEDS_GPT_PLANNER`, `READY_FOR_PLANNER_REVIEW`, or
  `READY_FOR_CRITIC_FINAL_AUDIT`.
- Wait at least `MIN_EXTERNAL_GPT_WAIT = 2 hours` from the first published handoff
  into the external-GPT-owned state. Two hours is a minimum normal grace period,
  not an automatic blocking deadline.
- After two hours, keep waiting if the repository state is valid, the
  implementation/result artifacts are intact, and there is no concrete
  connector, authentication, scheduler, schema, artifact-access, user-decision,
  or workflow-contract failure.
- Use low-frequency status checks while waiting. A normal check should only
  refresh the authorized branch, read the current workflow state, compare the
  current implementation/review target with the newest external decision, and
  inspect required CI/check state when relevant.
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
- Only mark external-review waiting as `BLOCKED` when there is observed evidence
  that waiting cannot recover automatically, such as a disabled/deleted/expired
  Scheduled Task, repeated connector/authentication failure, missing required
  external role installation, invalid repository state, inaccessible required
  review artifacts, a visual-review access impossibility, a required user
  product/scientific/branch decision, or a workflow-defined hard deadline.

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
