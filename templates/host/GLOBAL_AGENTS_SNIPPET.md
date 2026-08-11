# AI Bridge Kit Host Policy

## Git Branch Policy

The user is usually the sole developer in these repositories, so branch topology
is a project decision controlled by the user.

- Continue working on the currently checked-out branch by default.
- Do not create any new Git branch without explicit user authorization for that
  branch.
- This includes `git switch -c ...`, `git checkout -b ...`,
  `git branch <new-branch>`, `git worktree` creating a new branch, or creating a
  new remote branch because the current branch feels inconvenient to push.
- Large scope, many files, incomplete implementation, perceived PR safety, or a
  clean `main` baseline are not authorization to create a branch.
- Explain the risk and ask the user before creating a branch when branch
  strategy is ambiguous.
- If the user explicitly selected an existing branch, continue on that branch
  without asking repeatedly.
- Do not create pull requests unless requested.
- Ordinary commits and authorized pushes on the current branch follow the active
  Git policy.
- Never force push, use `--force-with-lease`, delete remote branches or tags, or
  modify/add/remove/remap Git remotes without explicit authorization.

Even if a broad execpolicy rule technically matches a dangerous Git command,
these behavior rules remain binding and must not be bypassed.

## User Input Policy

Because host policy enables `default_mode_request_user_input`, ask the user when
ambiguity would materially change architecture, project scope, destructive
actions, branch strategy, deployment strategy, externally visible behavior,
scientifically meaningful substitutions or degradation, or irreversible and
difficult-to-reverse decisions.

Routine implementation details, local refactoring choices, and clearly
reversible small decisions do not require repeated interruption.

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
