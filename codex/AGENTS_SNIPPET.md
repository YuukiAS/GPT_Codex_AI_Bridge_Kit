# Handoff Protocol

This repository uses the `prompts/` handoff protocol: a lightweight file bridge
between a GPT strategic planner and Codex execution sessions.

## Read First

- `prompts/AGENT_RULES.md`: Codex execution rules.
- `prompts/CHATGPT_RULES.md`: GPT planning/review rules.
- `prompts/HANDOFF_ROLES.md`: two-layer role model.
- `prompts/HANDOFF_STATE_MACHINE.md`: controlled states.
- `prompts/CONTROLLER_TASK_PROTOCOL.md`: controller task behavior.
- `prompts/tasks/<task_key>.md`: default task entry.

## File Mapping

```text
prompts/tasks/<task_key>.md
results/<task_key>/result.md
results/<task_key>/review.md
results/<task_key>/controller_report.md   # controller tasks
results/<task_key>/MANIFEST.md
```

`docs/notes/` and `docs/wiki/` are reference stores, not default execution
entries.

## Codex Rules

- Execute only the GPT-authored task scope.
- Obey frontmatter permission fields and stop on unauthorized actions.
- If acting as executor, write `result.md` and stop at self-assessment; do not
  claim final audited completion or open the next task.
- If the task requires an auditor and the current session is executor, do not
  also audit.
- If acting as auditor, remain read-only; do not fix code, generate missing
  artifacts, or continue execution.
- If acting as execution controller, coordinate executor/auditor sessions only
  inside the GPT-authored controller task.
- The execution controller must not invent new research/product directions. If a
  new direction is needed, write `NEEDS_GPT_PLANNER`.
- For controller tasks, when audit passes, the promotion gate is satisfied, and
  no human approval gate is triggered, follow `auto_git_commit` and
  `auto_git_push`. If commit or push is skipped, state the reason in
  `controller_report.md`.
