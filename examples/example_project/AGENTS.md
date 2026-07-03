# Example Project Agents

This example project uses the `prompts/` handoff protocol.

Read:

- `prompts/AGENT_RULES.md`
- `prompts/CHATGPT_RULES.md`
- `prompts/HANDOFF_ROLES.md`
- `prompts/HANDOFF_STATE_MACHINE.md`
- `prompts/CONTROLLER_TASK_PROTOCOL.md`

Default task entry:

- `prompts/tasks/<task_key>.md`

Normal executor output:

- `results/<task_key>/result.md`
- `results/<task_key>/MANIFEST.md`

Controller task output:

- `results/<task_key>/controller_report.md`
- `results/<task_key>/subagents/executor_prompt.md`
- `results/<task_key>/subagents/auditor_prompt.md`
- executor result and read-only auditor review

Example tasks:

- `001_structure_audit`: original simple execution/review loop.
- `002_greeting_controller`: GPT planner -> Codex execution controller -> Codex
  executor -> Codex auditor -> controller report -> GPT next task.

Language policy: keep protocol fields, paths, enums, commands, and code
identifiers in English; human-readable prose may follow the user's language or
project rules.

`docs/notes/` and `docs/wiki/` are reference stores and are not executed unless a
task explicitly references them.
