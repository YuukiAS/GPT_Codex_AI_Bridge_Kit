# AI Bridge Overleaf Bridge

This repository has opted into the optional Overleaf Bridge project capability.

Overleaf does not pull a single folder from a GitHub monorepo. Bridge Kit keeps
Codex working in the full repository while projecting only the configured
manuscript publication root into a machine-local clone of the Overleaf Git
project.

Tracked project config lives here:

```text
automation/overleaf/config.toml
```

Machine-local connection state and the Overleaf Git mirror live outside this
repository:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/
```

Do not commit Overleaf tokens. Bridge Kit uses normal Git authentication and
lets the user's Git credential helper handle any token persistence.
