# AI Bridge Kit Shared Codex Configuration Profile

This is a project-agnostic reference for user-level Codex configuration. Install
host policy with:

```bash
ai-bridge host install
ai-bridge host validate
```

## Feature Flags

The current Bridge Kit host policy manages:

```toml
[features]
memories = true
default_mode_request_user_input = true
```

`default_mode_request_user_input` was verified against Codex CLI feature
discovery before being kept in the managed host policy. If a future Codex
installation does not expose it, `ai-bridge host validate` should report the
host as incompatible rather than silently pretending it works.

## Low-Risk Command Rule Suggestions

These are suggestions for host/project rules, not a broad approval bypass:

- `git status`
- `git diff`
- `git log`
- `git fetch`
- read-only repository inspection
- repository test runner commands
- lint and format commands
- ordinary `git commit ...` on the already selected current branch
- ordinary `git push origin main` or project-specific ordinary pushes to an
  already authorized current branch

Do not globally allow:

- branch creation, switching, deletion, or renaming;
- first pushes to arbitrary remote branch names;
- upstream creation or changes;
- force push;
- broad destructive reset;
- broad `rm -rf`;
- secret upload;
- production deployment;
- external publication;
- production database writes;
- credential modification;
- arbitrary shell or Python.
