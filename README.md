# GPT-Codex AI Bridge Kit

This kit is a lightweight file bridge for ChatGPT/GPT and Codex. It is not a
service, agent runtime, queue, or MCP orchestration layer. Its job is to give any
repository a stable handoff protocol made of Markdown task, result, audit, and
controller-report files.

The original protocol was a simple loop:

1. ChatGPT writes `prompts/tasks/<task_key>.md`.
2. Codex executes the task and writes `results/<task_key>/result.md`.
3. ChatGPT reviews the result and writes `results/<task_key>/review.md`.

That loop remains valid. The kit now also defines a general two-layer control
model for medium/high risk work: GPT remains the strategic planner, while a
Codex execution controller may coordinate executor and auditor sessions inside a
GPT-authored controller task.

## Core Idea

The strategic planning layer is the user-supervised ChatGPT/GPT thread. It owns
direction, research judgment, task design, review interpretation, and next-task
planning.

The execution-control layer may be a Codex controller session. It can build an
execution plan, launch or prepare executor/auditor subtasks, collect evidence,
write a controller report, and commit/push when the audited promotion gate
passes. It must not invent a new direction. If a new direction is needed, it
outputs `NEEDS_GPT_PLANNER` and stops.

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

Install once:

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
```

Initialize any repository:

```bash
ai-bridge init --target /path/to/project
```

Or run `ai-bridge` from the target repository root.

By default, existing files are not overwritten. Use `--force` to refresh managed
templates.

## Validate

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
- `templates/`: files copied into target repositories.
- `examples/example_project/`: minimal end-to-end examples.
- `ai_bridge_kit/cli.py`: standard-library CLI.
