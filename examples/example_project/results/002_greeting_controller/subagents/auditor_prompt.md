# Auditor Prompt 002 Greeting Controller

Role: separate Codex auditor session.

Audit only. Do not modify files, do not run repair commands, and do not generate
missing artifacts.

Read:

- `prompts/tasks/002_greeting_controller.md`
- `results/002_greeting_controller/subagents/executor_result.md`
- `src/greeting.py`
- `tests/test_greeting.py`

Write:

- `results/002_greeting_controller/subagents/auditor_review.md`

Use the claim ledger with `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`, or
`CONTRADICTED`.
