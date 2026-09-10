# Persistent Run Contract

Persistent execution: REQUIRED
Backend: tmux
Goal source: <repo-relative path>
Run/session key: <project-owned stable key>

## Authorized Effects

- Execute the already-frozen task / Goal.
- Use only resources already authorized by that Goal.
- Write the Goal's declared logs, checkpoints, results and state artifacts.
- Continue after Codex / SSH disconnect.

## Forbidden Expansion

- Do not change scientific/product scope.
- Do not silently change data, split, model, budget or resource semantics.
- Do not request or cancel resources unless the Goal explicitly allows it.
- Do not switch to `setsid`, `nohup`, bare background `&`, `screen`, `sudo` or another persistence backend because tmux launch or inspection failed.

## Recovery Evidence

- tmux session identity.
- Project-native lock / heartbeat / stage-state / checkpoint / resume evidence, or equivalent observable state.
- Scheduler/process diagnostics may support diagnosis, but do not override stronger project-native state.

## Completion

- Session, job or PID existence is not completion.
- Heartbeat or checkpoint existence is not completion.
- The original Goal's positive completion criteria remain authoritative.
