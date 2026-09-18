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
default_mode_request_user_input = false
```

`default_mode_request_user_input` is deliberately managed to `false`.
Default-mode required human gates use a durable plain-text transcript question
and same-thread resume point because current native Default-mode cards can
auto-resolve. `ai-bridge host validate` still checks that Codex exposes the
feature key, so an upstream removal is reported as unsupported/incompatible
rather than hidden by the desired disabled state. Plan-mode native blocking
semantics remain a separate Codex mode behavior.

## Low-Risk Command Rule Suggestions

These are suggestions for host/project rules, not a broad approval bypass:

- `git status`
- `git diff`
- `git log`
- ordinary `git fetch origin main`
- ordinary `git pull --ff-only origin main` after confirming the working tree is
  clean
- read-only repository inspection
- repository test runner commands
- lint and format commands
- ordinary `git add ...` for task-owned repository files, with staged diff
  inspection before commit
- ordinary `git commit ...` on the already selected current branch
- ordinary `git push origin main` or project-specific ordinary pushes to an
  already authorized current branch

Do not globally allow:

- branch creation, switching, deletion, or renaming;
- first pushes to arbitrary remote branch names;
- rebase pull or autostash pull;
- upstream creation or changes;
- force push;
- broad destructive reset;
- restore/clean operations that discard user work;
- broad `rm -rf`;
- secret upload;
- production deployment;
- external publication;
- production database writes;
- credential modification;
- arbitrary shell or Python.
