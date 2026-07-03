---
task_key: "002_greeting_controller"
project: "example_project"
status: "READY"
task_type: "controller"
controller_mode: true
planner: "ChatGPT/GPT thread"
strategic_controller: "user-supervised GPT thread"
execution_controller: "Codex controller session"
executor: "Codex executor session"
auditor: "separate Codex auditor session"
review_required: true
risk_level: "medium"
mechanism_class: "small software behavior change"
promotion_gate: "Executor result includes the script change, tests pass with exit status 0, auditor marks required claims SUPPORTED, and no permission boundary is violated."
failure_escalation_policy: "Controller may request one in-scope executor revision for missing test evidence; if a different feature direction is needed, write NEEDS_GPT_PLANNER and stop."
forbidden_substitutes: ["Do not change the tests only.", "Do not replace the greeting function with unrelated behavior.", "Do not count executor self-assessment as audit."]
required_evidence: ["diff summary for src/greeting.py", "pytest command with exit status 0", "auditor claim ledger", "controller_report.md"]
allowed_next_states: ["EXECUTION_PLANNED", "EXECUTOR_RUNNING", "EXECUTED_UNAUDITED", "AUDITOR_RUNNING", "AUDITED_GO", "NEEDS_EVIDENCE", "NEEDS_REVISION", "NEEDS_HUMAN_APPROVAL", "NEEDS_SUBAGENT_LAUNCH", "NEEDS_GPT_PLANNER", "STOP"]
auto_git_commit: true
auto_git_push: true
allow_code_change: true
allow_shell_command: true
allow_network: false
allow_external_upload: false
requires_human_approval: false
controller_report: "results/002_greeting_controller/controller_report.md"
---

# Task 002 Greeting Controller

## Goal

Coordinate a small software change that makes `src/greeting.py` trim surrounding
spaces from names and use `there` for empty names, then verify it with tests.

## Background

This task demonstrates the general controller workflow:

GPT planner -> Codex execution controller -> Codex executor -> Codex auditor ->
controller report -> GPT next task.

In this example repository the final files already show the expected promoted
state. The protocol files demonstrate how a real controller run would record the
work.

## Mechanism Class And Completion Definition

- Mechanism class: small software behavior change.
- Completion definition: `greet(" Ada ")` returns `Hello, Ada!` and
  `greet("   ")` returns `Hello, there!`.
- Promotion gate: tests pass and auditor marks claims supported.

## Allowed Actions

- Read `src/greeting.py` and `tests/test_greeting.py`.
- Modify `src/greeting.py`.
- Run `python -m pytest tests/test_greeting.py`.
- Write subagent prompts, executor result, auditor review, controller report,
  and manifest under `results/002_greeting_controller/`.
- Commit and push after audit passes if this were a real git run.

## Forbidden Actions

- Do not use network.
- Do not upload files.
- Do not change unrelated files.
- Do not change tests only.
- Do not skip the auditor.

## Forbidden Substitutes

- Changing only documentation.
- Updating only tests without implementing the behavior.
- Claiming completion from executor self-assessment without audit.

## Required Evidence

- `src/greeting.py` diff summary.
- `python -m pytest tests/test_greeting.py` with exit status 0.
- Executor claims in `subagents/executor_result.md`.
- Auditor claim ledger in `subagents/auditor_review.md`.
- Controller report in `controller_report.md`.

## Review Requirements

- `review_required: true`
- Auditor must be separate from executor and read-only.
- Audit status must use a controlled enum.

## Subtask / Subsession Orchestration

If automatic subagent launch is unavailable, controller writes:

```text
results/002_greeting_controller/subagents/executor_prompt.md
results/002_greeting_controller/subagents/auditor_prompt.md
```

This example includes those fallback prompts.

## Expected Output

- `results/002_greeting_controller/subagents/executor_prompt.md`
- `results/002_greeting_controller/subagents/executor_result.md`
- `results/002_greeting_controller/subagents/auditor_prompt.md`
- `results/002_greeting_controller/subagents/auditor_review.md`
- `results/002_greeting_controller/controller_report.md`
- `results/002_greeting_controller/result.md`
- `results/002_greeting_controller/review.md`
- `results/002_greeting_controller/MANIFEST.md`

## Failure Escalation Policy

If tests fail because the implementation is incomplete, the controller may ask
the executor for one in-scope revision. If a different feature is needed, write
`NEEDS_GPT_PLANNER` and stop.

## Git Automatic Commit And Push Policy

Default is `auto_git_commit: true` and `auto_git_push: true`. This example does
not perform a real remote push; the controller report records the reason.

## Stop Conditions

- Required files missing.
- Tests cannot run.
- Auditor does not support required claims.
- New direction is needed.

## Human Decision Points

- Whether to accept this example as a promoted demonstration.
