# GPT-Codex AI Bridge Kit

This kit is a local file bridge for ChatGPT/GPT and Codex. Lite Handoff remains
the default protocol for ordinary repositories. Host Policy, Generic Notifier,
and Optional Agent-Flow Core are separate layers that can be adopted only when
they are needed.

The original protocol was a simple loop:

1. ChatGPT writes `prompts/tasks/<task_key>.md`.
2. Codex executes the task and writes `results/<task_key>/result.md`.
3. ChatGPT reviews the result and writes `results/<task_key>/review.md`.

That loop remains valid. The kit now defines four layers:

```text
1. Host Policy
2. Lite Handoff
3. Generic Notifier
4. Optional Agent-Flow Core
```

Host-level Codex policy is installed once per Codex identity, while repo-level
handoff protocol is initialized once per repository. Agent-Flow is an explicit
opt-in layer for high-risk work; it is not installed by `ai-bridge init` and does
not replace Lite Handoff.

## Core Idea

The strategic planning layer is the user-supervised ChatGPT/GPT thread. It owns
direction, research judgment, task design, review interpretation, and next-task
planning.

The execution-control layer may be a Codex controller session. It can build an
execution plan, launch or prepare executor/auditor subtasks, collect evidence,
write a controller report, and commit/push when the audited promotion gate
passes. It must not invent a new direction. If a new direction is needed, it
outputs `NEEDS_GPT_PLANNER` and stops.

## Lite Handoff

Lite Handoff remains the default workflow:

```text
Planner -> Codex -> result -> optional GPT review
```

Existing repositories can continue using:

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

No notifier, polling process, tmux session, or Agent-Flow runtime is required for
old Lite Handoff repositories.

## Optional Agent-Flow Core

Agent-Flow Core adds a reusable high-risk control plane:

```text
Planner
-> Initial Critic
-> Controller
-> Verifier
-> Executor
-> Planner repair loop
-> Final Critic
-> Human gate
```

It provides Project Profile, Role Authority Policy, Requirement Ledger, typed
Finding schema, change classification, canonical implementation/verifier source
manifests, Stable Review Snapshot, compact Review Bundle validation, deterministic
routing, detached worktree planning, Final Critic gate checks, and terminal
notification brief generation for the existing Generic Notifier.

Install it only for repositories that need high-risk autonomous execution:

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
ai-bridge agent-flow task init --target /path/to/project --task-key 001_example
```

Snapshot and validation tools:

```bash
ai-bridge agent-flow snapshot --target /path/to/project --task-key 001_example
ai-bridge agent-flow bundle validate --target /path/to/project --task-key 001_example
ai-bridge agent-flow classify-change --target /path/to/project --path src/example.py
ai-bridge agent-flow route --target /path/to/project --task-key 001_example
ai-bridge agent-flow prompt --target /path/to/project planner
```

Agent-Flow install is additive and idempotent. It does not modify `$CODEX_HOME`,
remotes, branches, notifier state, or Lite Handoff files. Branch topology remains
user-controlled; Verifier and Executor isolation defaults to detached worktree
plans unless the user explicitly authorizes role branches.

## Generic Notifier

Generic Notifier is an optional terminal email notification feature. The default
mode is one-shot:

```text
Goal / Controller reaches a legal terminal state
-> write results/<task_key>/notification_brief.json
-> ai-bridge notifier send results/<task_key>/notification_brief.json
-> send one SMTP email
-> record local send success/failure
-> stop
```

Default new-project usage:

```bash
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
ai-bridge notifier send results/<task_key>/notification_brief.json
```

Core CLI:

```bash
ai-bridge notifier send <brief_path>
ai-bridge notifier send-test
ai-bridge notifier once
ai-bridge notifier run
ai-bridge notifier status
```

`send <brief_path>` is the recommended path. It sends one explicit terminal
brief and uses local state under `.ai-bridge/state/notifier.json` for
send-once/dedup and failed-send retry.

`send-test` uses the same SMTP backend and must send a real email before a
machine/project is marked `NOTIFIER_READY`.

`once` scans `results/*/notification_brief.json` once. On first startup, it
baselines existing terminal briefs and does not backfill historical
notifications.

`run` is optional polling compatibility mode. It is not an installation
requirement and is not needed for `NOTIFIER_READY`.

tmux is optional, not required, and not managed by Bridge Kit. Users who want a
long-running process may host `ai-bridge notifier run` themselves through tmux,
screen, nohup, systemd, or another local deployment choice.

### Terminal Brief Schema

Standard path:

```text
results/<task_key>/notification_brief.json
```

Required fields:

```json
{
  "schema": "ai-bridge.notification_brief.v1",
  "project": "example-project",
  "task_key": "001_example_task",
  "terminal_status": "complete",
  "key_conclusion": "The task reached a terminal state.",
  "next_step": "Review evidence and decide the next task.",
  "evidence_paths": ["results/001_example_task/result.md"]
}
```

Supported `terminal_status` values:

```text
complete
blocked
awaiting_human
```

Optional fields include `commit_status`, `push_status`, `details`, `jobs`,
`duration`, `branch`, and `version`. Generic Notifier does not require Slurm,
GPU, training, reviewer/controller, commit, or push fields.

The notifier does not infer scientific/product conclusions. It only sends the
brief's declared conclusion.

### SMTP Backend

v0.3.0 implements only SMTP email:

```text
smtp.gmail.com
port 587
STARTTLS
```

Environment/private keys:

```text
AI_BRIDGE_NOTIFY_SMTP_USER
AI_BRIDGE_NOTIFY_SMTP_PASSWORD
AI_BRIDGE_NOTIFY_FROM
AI_BRIDGE_NOTIFY_TO
AI_BRIDGE_NOTIFY_SUBJECT_PREFIX
```

Emails include both plain text and HTML alternatives and intentionally stay
short: project, task, status, conclusion, next step, and key evidence.

## Private Bootstrap

Bridge Kit does not bootstrap rclone OAuth, create Google tokens, manage rclone
remotes, or download rclone credentials from Google Drive. Each machine must
already have a user-configured rclone remote.

Private notifier configuration is pulled from an existing rclone source:

```bash
export AI_BRIDGE_PRIVATE_RCLONE_SOURCE='<remote>:Private/GPT_Codex_AI_Bridge_Kit/notifier.env'
ai-bridge private sync --profile notifier
```

The sync is pull-only:

1. check `rclone` exists;
2. check the configured source can be copied;
3. download to `.ai-bridge/private/notifier.env`;
4. try `chmod 0600`;
5. verify required notifier keys exist;
6. never print secret values;
7. never upload or modify the Google Drive source.

If rclone is missing, the CLI reports `RCLONE_NOT_CONFIGURED`. If the source is
unset or unavailable, it reports `PRIVATE_SOURCE_UNAVAILABLE`.

Public examples use only:

```text
sender@example.org
recipient@example.org
```

## Optional Polling Mode

One-shot notifier sends are preferred. Polling exists for compatibility:

```bash
ai-bridge notifier once
ai-bridge notifier run --poll-seconds 60
```

First polling startup records existing terminal briefs as baseline and does not
send historical notifications. Later new terminal briefs may be sent, with
failed sends retried because failed events are not marked as sent.

## Shared Codex Configuration

Host policy and the shared config profile let multiple repositories reuse
user-level Codex defaults instead of reconfiguring each repo.

Reference file:

```text
templates/host/CODEX_CONFIG_PROFILE.md
```

The managed host policy keeps:

```toml
[features]
memories = true
default_mode_request_user_input = true
```

The current Codex CLI feature discovery confirms both features are available on
this host. If a future Codex install lacks one, `ai-bridge host validate` should
report incompatibility rather than silently pretending it works.

## Host Policy And Repo Handoff

```text
                  GPT-Codex AI Bridge Kit
                           |
             +-------------+-------------+
             |                           |
      Host Policy                  Repo Handoff
      once / CODEX_HOME            once / repository
             |                           |
   config.toml                     AGENTS.md
   AGENTS.md                       prompts/
   rules/                          results/
                                  docs/
                                  .agents/skills/
             |
      all repositories
      using this CODEX_HOME
```

Host policy is installed once for each Codex host, server, Workstation, WSL
identity, native Windows identity, or explicit `$CODEX_HOME`. It manages Codex
defaults that should apply across repositories.

```text
Host Policy
├── Codex config defaults
├── feature flags
├── execpolicy allow rules
├── global Git/branch behavior
└── global user-facing narrative language
```

The default user-facing narrative language is Simplified Chinese, while
repository artifacts continue to follow repository/task-specific language
conventions.

Codex Desktop / Goal mode may save long objectives as attachments such as
`$CODEX_HOME/attachments/.../goal-objective.md` and ask the session to read that
objective file before continuing. That mechanism is normal and does not need to
be disabled, bypassed, or repeated in every Goal. Host Policy provides the
session-level default: interactive narrative remains Simplified Chinese even
when the objective file, commands, repository documentation, terminal output, or
upstream documentation are in English.

Repo handoff is initialized separately in each repository. It creates the
version-controlled handoff files for that project and does not silently modify
`$CODEX_HOME`.

Repo-local `.codex/config.toml` or `.codex/rules/` may override or further
tighten host policy. Memories help with long-term context, but repository files
such as `AGENTS.md`, tasks, results, reviews, and docs remain the authoritative
project state.

## Core Directories

```text
prompts/
  AGENT_RULES.md
  CHATGPT_RULES.md
  HANDOFF_ROLES.md
  HANDOFF_STATE_MACHINE.md
  CONTROLLER_TASK_PROTOCOL.md
  MECHANISM_GATE_TEMPLATE.md
  tasks/
  templates/
docs/
  notes/
  wiki/
results/
```

Task names use:

```text
<id>_<short_slug>
```

Example: `002_fix_ci`, `20260702_api_docs`. New task files live at
`prompts/tasks/<task_key>.md`; do not add `_task`.

## File Mapping

Normal execution task:

```text
prompts/tasks/<task_key>.md
results/<task_key>/result.md
results/<task_key>/review.md
results/<task_key>/MANIFEST.md
```

Controller task:

```text
prompts/tasks/<task_key>.md
results/<task_key>/controller_report.md
results/<task_key>/subagents/executor_prompt.md
results/<task_key>/subagents/auditor_prompt.md
results/<task_key>/result.md
results/<task_key>/review.md
results/<task_key>/MANIFEST.md
```

`docs/notes/` and `docs/wiki/` are reference stores. They are not default Codex
execution entries.

## Recommended Workflow

1. ChatGPT/GPT main thread acts as planner and writes either a normal execution
   task or a controller task.
2. The user starts a Codex session with the GPT-authored task.
3. For a normal execution task, Codex executor performs the authorized work and
   writes `result.md`.
4. For a controller task, Codex execution controller starts separate executor and
   auditor sessions when the runtime supports it.
5. If subagent launch is unavailable, the controller writes prompt files under
   `results/<task_key>/subagents/` and marks `NEEDS_SUBAGENT_LAUNCH` or
   `NEEDS_HUMAN_APPROVAL`.
6. Executor writes result and artifacts.
7. Auditor performs read-only evidence audit with a claim ledger.
8. Controller writes `controller_report.md`.
9. If `auto_git_commit: true`, `auto_git_push: true`, audit passes, and no human
   approval is triggered, the controller commits and pushes to the remote.
10. ChatGPT/GPT reads the review or controller report and decides the next task,
    stop, rollback, or human approval path.

The default planning assumption is that successful controller tasks synchronize
remote state. Later GPT planning should prefer checking the remote repository
state instead of relying on unpushed local state.

## Roles

- Planner: `ChatGPT/GPT thread`.
- Strategic controller: `user-supervised GPT thread`.
- Execution controller: `Codex controller session` inside a controller task.
- Executor: `Codex executor session`.
- Auditor/reviewer: separate Codex auditor session or ChatGPT reviewer with
  enough file evidence.

Auditors are read-only. Executor self-assessment is not final completion.
Controller reports do not replace GPT strategic judgment.

## Task Types

Normal execution task:

- `task_type: "execution"`
- One executor session.
- Writes `results/<task_key>/result.md`.
- May require later audit depending on `review_required`.

Controller task:

- `task_type: "controller"`
- `controller_mode: true`
- Codex controller coordinates executor/auditor subtasks inside GPT-defined
  scope.
- Writes `results/<task_key>/controller_report.md`.
- Commits/pushes only after the task promotion gate passes and approval policy
  allows it.

## Frontmatter

Legacy fields remain valid:

```yaml
task_key: "002_fix_ci"
project: "project-name"
status: "READY"
executor: "Codex executor session"
risk_level: "low"
allow_code_change: true
allow_shell_command: true
allow_network: false
allow_external_upload: false
requires_human_approval: false
```

New protocol fields:

```yaml
task_type: "execution"
controller_mode: false
planner: "ChatGPT/GPT thread"
strategic_controller: "user-supervised GPT thread"
execution_controller: "none"
auditor: "ChatGPT reviewer"
review_required: false
mechanism_class: "general"
promotion_gate: "..."
failure_escalation_policy: "..."
forbidden_substitutes: []
required_evidence: []
allowed_next_states: []
auto_git_commit: true
auto_git_push: true
```

For low-risk tasks, new fields can use defaults, `none`, or empty lists. For
medium/high risk tasks and controller tasks, fill them explicitly.

## Project-Specific Gates

This kit intentionally stays domain-neutral. It does not define domain-specific
mechanism gates. Real repositories should define their own gates in `AGENTS.md`,
project rules, or skills, then reference those gates from task files.

## Language Policy

Protocol keys, YAML fields, file paths, controlled state enums, command names,
code identifiers, and API names should remain English. Human-readable prose in
task bodies, results, reviews, controller reports, notes, and next-task
explanations should follow the user's language or the target repository's
project rules.

If a project prefers Chinese, write human-readable task/review/report prose
primarily in Chinese while keeping protocol fields and controlled values in
English. Do not force English prose globally just because this kit's protocol
documentation is written in English. Project-level language rules win unless
they would break machine-readable protocol fields.

## Install And Initialize

Install the package:

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
```

### Once Per Codex Host / Identity

```bash
ai-bridge host install
ai-bridge host validate
```

Use `--codex-home /explicit/path` when managing a non-default Codex Home. Codex
Home resolution is:

1. explicit `--codex-home`
2. `$CODEX_HOME`
3. `~/.codex`

Every host command prints the final Codex Home it uses.

`ai-bridge host install` non-destructively maintains:

```text
$CODEX_HOME/config.toml
$CODEX_HOME/AGENTS.md
$CODEX_HOME/rules/ai-bridge-global.rules
```

It preserves unrelated config fields and unknown TOML content, updates only the
managed keys, and backs up modified files under:

```text
$CODEX_HOME/ai-bridge-kit/backups/<timestamp>/
```

Managed config values:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
approvals_reviewer = "auto_review"

[sandbox_workspace_write]
network_access = true

[features]
default_mode_request_user_input = true
memories = true
```

Managed execpolicy rules allow only these Git push prefixes:

```text
git push origin ...
git push --set-upstream origin ...
git push -u origin ...
```

They do not authorize force push, remote changes, remote branch/tag deletion,
arbitrary shell, arbitrary Python, `danger-full-access`, or
`approval_policy = "never"`.

The host `AGENTS.md` managed block says Codex should continue on the current
branch by default and must not create a new branch or PR without explicit user
authorization. Material ambiguity should be asked through user input; routine
implementation details should be decided locally and carried through.

The same managed block also sets user-facing narrative language policy:
interactive progress, plans, status explanations, approval questions, risk
explanations, test summaries, completion reports, and blocker reports default to
Simplified Chinese unless the user explicitly asks for another language.
Technical literals such as code, shell commands, file paths, Git refs,
configuration keys, YAML/TOML fields, protocol state names, API identifiers, and
exact quoted errors remain in their original form. This is not a Codex
`config.toml` language key; `ai-bridge host status` reports it as Bridge Kit
policy state with `narrative_language: zh-CN`.

### Once Per Repository

Initialize any repository:

```bash
ai-bridge init --target /path/to/project
```

Or run `ai-bridge` from the target repository root.

By default, existing files are not overwritten. Use `--force` to refresh managed
templates. Repo initialization only manages repository handoff files such as
`AGENTS.md`, `prompts/`, `results/`, `docs/`, and the repo-local Codex skill.
It may report host policy status, but it does not install host policy.

## Validate

Validate host policy:

```bash
ai-bridge host status
ai-bridge host validate
```

Validate repo handoff:

```bash
ai-bridge validate --target /path/to/project
```

Strict mode upgrades protocol warnings to errors:

```bash
ai-bridge validate --target /path/to/project --strict
```

Validation checks directory layout, task frontmatter, task/result/review mapping,
controller report expectations, review-required tasks, promotion-like states
without audit evidence, and unexplained skipped auto commit/push.

Old projects remain compatible: missing new protocol fields are warnings for
medium/high risk or controller tasks, and only strict mode upgrades those
warnings to errors.

## Kit Contents

- `chatgpt/`: reusable prompts for task writing, evidence audit, next-task
  planning, notes, and wiki work.
- `codex/`: Codex start prompt, `AGENTS.md` snippet, and repo-local skill.
- `templates/`: files copied into target repositories plus host desired-state
  templates under `templates/host/`.
- `examples/example_project/`: minimal end-to-end examples.
- `ai_bridge_kit/cli.py`: standard-library CLI.
- `ai_bridge_kit/host.py`: host-level Codex policy install/status/validation.

## New Server Short Path

On each new Codex host or identity:

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
ai-bridge host install
ai-bridge host validate
```

Then initialize each repository separately:

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

## New Project Notifier Flow

Machine one-time setup:

1. Configure an rclone remote manually.
2. Set `AI_BRIDGE_PRIVATE_RCLONE_SOURCE` to the private notifier env path.

Project setup:

```bash
ai-bridge init --target /path/to/project
cd /path/to/project
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
```

Mark `NOTIFIER_READY` only after the real Gmail SMTP test email is actually
sent.

Goal terminal step:

```text
results/<task_key>/notification_brief.json
```

```bash
ai-bridge notifier send results/<task_key>/notification_brief.json
```

Optional legacy/polling:

```bash
ai-bridge notifier run
```

tmux remains optional and unmanaged by Bridge Kit.
