I explicitly authorize execution of the referenced frozen Goal using its Persistent Run contract.

Goal: `__GOAL_PATH__`
Goal SHA-256: `__GOAL_SHA256__`

Start or resume the required persistent tmux session for this Goal because its frozen contract has already selected a terminal-owned survive-disconnect topology. Execute the already-authorized work, use only the resources authorized by that Goal, write its declared artifacts, and allow the run to continue after Codex / SSH disconnect.

Do not ask again merely because this same frozen Goal is long-running, detached or unattended.

This authorization is not a universal unattended approval. It does not permit scope expansion, different compute resources, scheduler submission/allocation/cancellation, sudo, or fallback to another persistence backend unless the Goal explicitly permits it.

Use the exact production entry:

```bash
ai-bridge persistent-run start --target <exact-repo> --goal __GOAL_PATH__ --expected-goal-sha256 __GOAL_SHA256__
```

Reconnect with the same Goal identity through `persistent-run status`. A
stale/mismatched/partial run must remain UNKNOWN/UNAVAILABLE or CONFLICT; it
must not be relaunched or taken over automatically.
