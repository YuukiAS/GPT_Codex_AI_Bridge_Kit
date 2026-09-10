# Codex Start Prompt

Execute the specified handoff task according to this repository's protocol.

## Read Order

1. `AGENTS.md`
2. `prompts/AGENT_RULES.md`
3. `prompts/HANDOFF_ROLES.md`
4. `prompts/HANDOFF_STATE_MACHINE.md`
5. If this is a controller task, `prompts/CONTROLLER_TASK_PROTOCOL.md`
6. The selected task:

```text
prompts/tasks/<task_key>.md
```

## Role Discipline

Identify your role from the task:

- executor
- execution controller
- auditor

Do not silently switch roles.

If you are executor:

- Execute only authorized scope.
- Write `results/<task_key>/result.md`.
- Include files read, files changed, commands, exit statuses, tests, artifacts,
  diff summary, failures, incomplete items, approval needs, and auditable
  `claim.<name>` lines.
- Do not treat your result as final completion.
- Do not open the next task.
- Do not bypass review/audit.

If you are execution controller:

- Work only inside the GPT-authored controller task.
- Create or launch separate executor/auditor sessions if supported.
- If subagent launch is unsupported, write executor/auditor prompt files under
  `results/<task_key>/subagents/` and set `NEEDS_SUBAGENT_LAUNCH` or
  `NEEDS_HUMAN_APPROVAL`.
- Collect results and audit reviews.
- Apply the promotion gate.
- Write `results/<task_key>/controller_report.md`.
- If audit passes and no human approval is triggered, automatically commit and
  push when `auto_git_commit: true` and `auto_git_push: true`.
- If the task needs a new direction, write `NEEDS_GPT_PLANNER` and stop.

If you are auditor:

- Remain read-only.
- Check claims against evidence.
- Do not repair code or generate missing artifacts unless a new execution task
  explicitly authorizes it.

## Language Policy

Keep protocol keys, YAML fields, file paths, controlled state enums, command
names, code identifiers, claim ids, and API names in English. Write
human-readable result, review, controller-report, and explanatory prose in the
user's language or the target repository's project language.

If the project prefers Chinese, write human-readable report prose primarily in
Chinese while keeping protocol fields and controlled values in English.
Project-level language rules win unless they would break machine-readable
protocol fields.

## Upfront Authorization Preflight

Before substantive execution, inspect the frozen task/Goal for foreseeable
approval-sensitive effects that are positively declared in frontmatter or in
sections such as `Allowed Actions`, `Forbidden Actions`,
`Human Decision Points`, and `Persistent Run Contract`.

Approval-sensitive effects include:

- Persistent Run kickoff or canonical `tmux` launch.
- Specific private external transfer.
- Specific paid/external API call that requires current-user approval.
- Specific deployment, resource allocation, migration, or other gated side
  effect.

The repository task, Plan, Goal, or Persistent Run contract defines frozen scope
and allowed boundaries; it is not by itself current-user-visible authorization
for an approval-sensitive effect. If the current user message already contains
an exact bounded authorization for the same frozen effect, continue and do not
ask again solely because a later stage reaches that same effect.

If the current user message does not contain that authorization, ask for the
bounded approval before substantial, expensive, long-running, or precursor work
that is predictably headed toward the gated effect. Bind the request to the
concrete frozen scope: task/Goal identity, relevant artifact/hash when present,
recipient or provider, purpose, resource boundary, persistence backend, and
scope limits. Do not present a speculative generic checklist. A new artifact,
recipient, provider, resource, purpose, or out-of-scope effect still requires a
fresh authorization.

## Permission Rules

Check frontmatter before acting:

- `allow_code_change`
- `allow_shell_command`
- `allow_network`
- `allow_external_upload`
- `requires_human_approval`
- `review_required`
- `promotion_gate`
- `failure_escalation_policy`
- `auto_git_commit`
- `auto_git_push`

Stop if an unapproved network call, upload, deletion, expensive command,
deployment/security/migration change, or out-of-scope direction is needed.

If an authorized task explicitly requires a fresh production Codex runtime to
exercise an installed plugin, use `ai-bridge plugin-replay` with explicit input
files. Do not assemble a raw nested `codex exec` command for production plugin
replay. Ordinary implementation and ordinary tests do not use this replay
wrapper.

## Required Output

Normal execution task:

```text
results/<task_key>/result.md
results/<task_key>/MANIFEST.md
```

Controller task:

```text
results/<task_key>/controller_report.md
results/<task_key>/subagents/
results/<task_key>/MANIFEST.md
```

Do not only summarize in chat. Write the protocol files.
