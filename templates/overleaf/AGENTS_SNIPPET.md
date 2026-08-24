## Overleaf Bridge

This repository uses the optional AI Bridge Kit Overleaf Bridge.

- Codex may read the whole repository for scientific and technical context.
- Only `__PAPER_ROOT__` is the Overleaf publication root. `__MAIN_DOCUMENT__`
  must resolve inside that publication root.
- Overleaf is a manuscript collaboration mirror, not a second source of truth
  for the full research repository.
- All manuscript assets required by Overleaf compilation must live inside the
  publication root and must not be excluded.
- `exclude_paths` is only for local/GitHub-only files that are not required for
  Overleaf compilation.
- Before `ai-bridge overleaf push`, protect unseen Overleaf edits by checking
  the Bridge baseline against local and remote publication digests.
- After `ai-bridge overleaf pull`, review and compile the manuscript changes,
  then commit and push through the normal GitHub `origin` workflow.
