I explicitly authorize execution of the referenced frozen Goal using its Persistent Run contract.

Goal: `__GOAL_PATH__`
Repository: `__REPO__`
Run/session key: `__RUN_KEY__`
Goal/contract SHA-256: `__GOAL_SHA256__`
Authorized persistent-launch effect SHA-256: `__EFFECT_SHA256__`

Use the exact bounded entry:

```bash
ai-bridge persistent-run start --target __REPO__ --goal __GOAL_PATH__ --expected-goal-sha256 __GOAL_SHA256__ --authorization-effect-sha256 __EFFECT_SHA256__ --progress-notification-effect-sha256 __PROGRESS_NOTIFICATION_EFFECT_SHA256__ --runtime-notification-effect-sha256 __RUNTIME_NOTIFICATION_EFFECT_SHA256__
```

Start or resume the required persistent tmux session for this Goal because its frozen contract has already selected a terminal-owned survive-disconnect topology. Execute the already-authorized work, use only the resources authorized by that Goal, write its declared artifacts, and allow the run to continue after Codex / SSH disconnect.

Do not ask again merely because this same frozen Goal is long-running, detached or unattended.

This authorization is not a universal unattended approval. It does not permit scope expansion, different compute resources, scheduler submission/allocation/cancellation, sudo, or fallback to another persistence backend unless the Goal explicitly permits it.
