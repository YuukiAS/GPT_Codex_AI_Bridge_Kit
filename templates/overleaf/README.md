# AI Bridge Overleaf Bridge

This repository has opted into the optional Overleaf Bridge project capability.

## Core Relationship

The GitHub repository remains the complete research project source of truth.
Codex should still read the full repository for code, analysis, results,
documentation, and manuscript context.

The configured `paper_root` is the only Overleaf publication root. Files inside
that directory are projected to the Overleaf project root, so
`paper/manuscript/main.tex` becomes `main.tex` in Overleaf.

Overleaf is a manuscript collaboration mirror. It is not a second remote for the
whole research repository, and it does not pull a GitHub monorepo subfolder by
itself.

## Codex To Overleaf

Recommended flow:

```text
Codex edits the manuscript
-> compile/check locally
-> commit to the research repository
-> git push origin main
-> ai-bridge overleaf status
-> ai-bridge overleaf push
```

`ai-bridge overleaf push` is not a replacement for the normal GitHub push. It
publishes the committed manuscript projection to the machine-local Overleaf
mirror and then to Overleaf only when the remote side has not changed since the
last Bridge baseline.

## Overleaf To GitHub

When collaborators edit in Overleaf:

```text
ai-bridge overleaf status
-> ai-bridge overleaf pull
-> inspect git diff
-> compile/check locally
-> commit
-> git push origin main
```

`ai-bridge overleaf pull` does not automatically commit and does not push to
GitHub. It leaves manuscript changes in the working tree so they can be
reviewed, compiled, and committed through the normal repository workflow.

## Clean Publication Root

Operations that establish or change the synchronization baseline require a clean
non-excluded publication root:

```text
ai-bridge overleaf connect --bootstrap
ai-bridge overleaf connect
ai-bridge overleaf push
ai-bridge overleaf pull
```

If tracked, staged, deleted, renamed, or untracked publication files are dirty,
Bridge Kit refuses synchronization before changing local files, remote files, or
the baseline. Files listed in `exclude_paths` do not block synchronization
because they are explicitly local/GitHub-only.

## exclude_paths

Use `exclude_paths` for files inside `paper_root` that should stay in GitHub but
must not be sent to Overleaf, for example:

```text
AGENTS.md
README.md
compiled main.pdf
local author notes
local/GitHub-only helper files
```

Do not exclude files required by Overleaf compilation, including:

```text
.tex dependencies
.bib files
.sty files
.cls files
figures used by LaTeX
tables/assets loaded by the manuscript
```

All assets needed by Overleaf compilation must live inside `paper_root` and must
remain publishable.

## Machine-Local State

Connection metadata and the Overleaf Git mirror are machine-local operational
state:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/
```

If the same GitHub repository is used from a Mac, workstation, and server, each
machine that performs Overleaf operations needs its own
`ai-bridge overleaf connect`. Do not copy another machine's
`~/.ai-bridge/overleaf/...` directory into GitHub.

Bridge Kit does not store Overleaf tokens. Git authentication should use the
normal Git credential flow and the user's credential helper.

## Divergence

If the local manuscript and Overleaf both changed since the last Bridge
baseline, Bridge Kit refuses both push and pull instead of guessing which side
should overwrite the other. Resolve the divergence manually, then re-run status
before synchronizing.
