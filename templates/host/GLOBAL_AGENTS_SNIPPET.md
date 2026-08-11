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
