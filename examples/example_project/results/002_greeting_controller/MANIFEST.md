# Artifact Manifest 002 Greeting Controller

task: `prompts/tasks/002_greeting_controller.md`
result: `results/002_greeting_controller/result.md`
review: `results/002_greeting_controller/review.md`
controller_report: `results/002_greeting_controller/controller_report.md`

## Summary

This directory demonstrates a generic controller workflow:

GPT planner -> Codex execution controller -> Codex executor -> Codex auditor ->
controller report -> GPT next task.

## Artifacts

- `subagents/executor_prompt.md`: fallback prompt for a separate executor
  session.
- `subagents/executor_result.md`: executor result with claims and self-assessed
  status.
- `subagents/auditor_prompt.md`: fallback prompt for a separate read-only
  auditor session.
- `subagents/auditor_review.md`: audit with claim ledger and promotion decision.
- `controller_report.md`: controller summary, promotion decision, commit/push
  policy, and GPT planner need.
- `result.md`: controller-level result summary.
- `review.md`: evidence audit of the example controller output.

## Reproduction

```bash
python -m pytest tests/test_greeting.py
```

Expected result: 2 passed, exit status 0.

## Notes

This is a static example. It records why automatic commit and push were not
executed.
