# Persistent Run Contract

Use this contract only after deciding that the required process/orchestrator is
terminal-owned and must survive Codex/SSH/terminal disconnect. Do not select
this contract solely because the task is long, overnight, unattended or
multi-hour; scheduler-owned batch jobs and already-detached services/jobs should
keep their native lifetime owner.

Persistent execution: REQUIRED
Backend: tmux
Goal source: <repo-relative path>
Run/session key: <project-owned stable key>
Working directory: .
Launch argv: ["python", "-m", "<project-owned-entrypoint>"]
Progress mode: none
Progress owner: none
Progress source locator: NONE
Expected progress update seconds: UNKNOWN
Notify: OFF
Recipient override: NONE
Notification cadence minutes: 60

## Authorized Effects

- Execute the already-frozen task / Goal.
- Use only resources already authorized by that Goal.
- Write the Goal's declared logs, checkpoints, results and state artifacts.
- Continue after Codex / SSH disconnect.

## Resource Boundary

- Compute resources:
- Data/model/source boundary:
- Network/external service boundary:
- Time/budget boundary:
- Cleanup boundary:

## Forbidden Expansion

- Do not change scientific/product scope.
- Do not silently change data, split, model, budget or resource semantics.
- Do not request or cancel resources unless the Goal explicitly allows it.
- Do not switch to `setsid`, `nohup`, bare background `&`, `screen`, `sudo` or another persistence backend because tmux launch or inspection failed.

## Recovery Evidence

- Bridge 使用完整 launch identity 派生唯一
  `ai-bridge-pr-<full-64-hex-launch-id>` session、一个 machine-local binding、
  一个 run-scoped supervisor 和一个 child。
- active compatible binding 只返回 existing；stale、mismatch、partial start 或
  supervisor loss 不自动 relaunch、不 takeover、不猜 terminal。
- exit code 只能来自 supervisor 对真实 child 的 `wait()` observation。

## Heartbeat / Stage-State / Checkpoint / Resume Semantics

- Heartbeat path and expected cadence:
- Stage-state path and state meanings:
- Checkpoint/output path:
- Resume rule for an existing compatible run: return existing; do not start a second child.
- Stale-run or conflicting-run handling: report UNKNOWN/UNAVAILABLE or CONFLICT; do not relaunch or take over.

## Progress Reporting

- Progress mode: count | fraction | stage | none
- Progress owner: bridge-child | project-native | none
- Progress source locator: bridge-state | <repo-relative JSON path> | NONE
- Expected progress update seconds: positive integer | UNKNOWN
- Notify: OFF | ON
- Recipient override: NONE | explicit address frozen by the user
- Notification cadence minutes: integer >= 15; default 60
- Report interval: 60 minutes unless the task contract gives a defensible shorter cadence; do not default below 15 minutes.
- Delivery mode: local latest/history, or Notifications only when an existing authorized provider/recipient is already configured.
- Stall threshold:

Progress truth is owned by the project-native source above. Bridge may normalize, compare, persist latest/history, and optionally project a one-shot operational-progress Notification, but it must not infer domain progress from tmux/session/PID existence alone.

For `bridge-child`, the child writes progress only through `ai-bridge persistent-run progress update`; Bridge injects the run key, progress path, mode, owner, expected cadence and runtime identity. `count` and `fraction` require a real producer. ETA remains `UNKNOWN` until at least three valid quantitative points span at least ten minutes.

## Completion

- Session, job or PID existence is not completion.
- Heartbeat or checkpoint existence is not completion.
- The original Goal's positive completion criteria remain authoritative.
