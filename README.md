# GPT-Codex AI Bridge Kit

This kit is a lightweight file bridge for ChatGPT/GPT and Codex. It is not a
service, agent runtime, queue, or MCP orchestration layer. Its job is to give any
repository a stable handoff protocol made of Markdown task, result, audit, and
controller-report files.

The original protocol was a simple loop:

1. ChatGPT writes `prompts/tasks/<task_key>.md`.
2. Codex executes the task and writes `results/<task_key>/result.md`.
3. ChatGPT reviews the result and writes `results/<task_key>/review.md`.

That loop remains valid. The kit now also defines a two-layer operating model:
host-level Codex policy is installed once per Codex identity, while repo-level
handoff protocol is initialized once per repository. For medium/high risk work,
GPT remains the strategic planner, while a Codex execution controller may
coordinate executor and auditor sessions inside a GPT-authored controller task.

## Planned Agent-Flow v3

A future reusable high-risk Agent-Flow mode is being stress-tested first in the
CARE-ASE project. It is intentionally **not implemented in this kit yet**. The
current lightweight handoff remains the active protocol until the CARE run
finishes and the design is simplified/extracted.

The blueprint is tracked in:

```text
docs/TODO_AGENT_FLOW_V3_REUSABLE_BLUEPRINT.md
```

The planned design keeps independent Planner/Critic/Controller/Verifier/Executor
roles for high-risk work while explicitly avoiding the over-engineered
provenance/hash/moving-target behavior exposed by the first CARE production run.

## Core Idea

The strategic planning layer is the user-supervised ChatGPT/GPT thread. It owns
direction, research judgment, task design, review interpretation, and next-task
planning.

The execution-control layer may be a Codex controller session. It can build an
execution plan, launch or prepare executor/auditor subtasks, collect evidence,
write a controller report, and commit/push when the audited promotion gate
passes. It must not invent a new direction. If a new direction is needed, it
outputs `NEEDS_GPT_PLANNER` and stops.

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
