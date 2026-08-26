# Reviewed Handoff Codex App Visibility Decision 2026-08-26

Status: decided, not adopted for production launcher

## Decision

Reviewed Handoff production Executor launch remains:

```text
watcher -> codex exec -C <repo> -
```

Do not adopt `codex app-server --stdio` as the Reviewed Handoff Executor
launcher yet.

Formal production decision:

```text
DO NOT ADOPT APP SERVER AS REVIEWED HANDOFF EXECUTOR LAUNCHER YET.
```

The current production observability path remains:

1. `ai-bridge reviewed-handoff watcher status`
2. machine-local watcher state
3. optional low-frequency external watchdog
4. Planner/Reviewer structured notifier

Eventually visible Codex App history must not be presented as reliable live
Executor monitoring.

## Scope

This note records local Codex App / Codex App Server capability experiments
completed on 2026-08-26 for Reviewed Handoff observability. It is an engineering
capability record, not a workflow schema, receipt system, or implementation
plan.

This note is about local Codex App thread lifecycle only. It must not be
confused with OpenAI API Assistants Threads.

## Environment

- Repository: `/home/yuukias/GPT_Codex_AI_Bridge_Kit`
- Codex: `codex-cli 0.148.0-alpha.9`
- Official command exercised: `codex app-server --stdio`
- Official protocol generation exercised: `codex app-server generate-json-schema`
  and `codex app-server generate-ts`

Official App Server protocol methods used:

- `initialize`
- `thread/start`
- `thread/name/set`
- `turn/start`
- `thread/read`
- `thread/list`
- `thread/resume`

No experiment manually edited `~/.codex/session_index.jsonl`, a Codex App
database, or private UI state.

## Verified Facts

### Probe 0: durable and eventually App-visible

- Thread id: `01a03c01-e265-7a62-a56b-a85930978bcb`
- Title: `AI Bridge App-visible probe`
- Marker: `AI_BRIDGE_APP_VISIBLE_PROBE_20260826_20260826T025911Z`
- cwd: `/home/yuukias/GPT_Codex_AI_Bridge_Kit`

Verified:

- App Server `thread/start` passed.
- App Server `turn/start` passed.
- App Server `thread/read` passed.
- App Server `thread/list` passed.
- After closing one App Server client and starting a new one,
  `thread/list` / `thread/read` still found the thread.
- `thread/resume` passed before Codex App became an active writer for that
  thread.
- cwd binding remained `/home/yuukias/GPT_Codex_AI_Bridge_Kit`.
- The user confirmed the thread eventually appeared in the Codex App UI under
  the `GPT_Codex_AI_Bridge_Kit` project.
- App -> App Server read passed: a message sent from Codex App was visible via
  App Server `thread/read` on the same thread.

Not verified:

- After Codex App obtained the active writer for the thread, a separate App
  Server client attempting to `thread/resume` / write the same thread received
  an active-writer conflict.

This conflict is a multi-writer / writer-ownership limitation. It is not a
durable lifecycle failure.

### Probe A: single writer

- Thread id: `01a03c0d-4a45-7e32-9175-73c31be24b32`
- Title: `AI Bridge single-writer live probe A`
- Marker: `AI_BRIDGE_SINGLE_WRITER_PROBE_A_20260826T031138Z`

Verified:

- App Server acted as sole writer and completed a real read-only turn in about
  61.5 seconds.
- No active-writer conflict occurred while App Server remained the sole writer.
- `thread/read` / `thread/list` passed.
- `PROBE_PHASE_1`, `PROBE_PHASE_2`, `PROBE_PHASE_3`, and
  `SINGLE_WRITER_PROBE_A_COMPLETE` were persisted.
- The user initially checked while the turn was running and reported
  `NOT_VISIBLE_RUNNING`.
- The user later confirmed the thread did appear automatically in Codex App.

Therefore the initial `NOT_VISIBLE_RUNNING` was an early UI check before App
discovery. It must not be interpreted as permanent invisibility.

### Probe 1: live discovery

- Thread id: `01a03c13-a7cc-79f1-b482-145a942d4910`
- Title: `AI Bridge live discovery probe 1`
- Marker: `AI_BRIDGE_LIVE_DISCOVERY_1_20260826T031836Z`
- Start: `2026-08-26T03:18:36Z`
- Turn complete: approximately `2026-08-26T03:22:56Z`

Human UI checks:

- 30 seconds: `NOT_VISIBLE`
- 60 seconds: `NOT_VISIBLE`
- 120 seconds: `NOT_VISIBLE`

No evidence was obtained that Codex App discovered the thread before the turn
completed. The thread later appeared automatically in Codex App.

### Probe 2: live discovery replication

- Thread id: `01a03c1a-434d-7c02-a2fa-3081178f9a4a`
- Title: `AI Bridge live discovery probe 2`
- Marker: `AI_BRIDGE_LIVE_DISCOVERY_2_20260826T032549Z`
- Start: `2026-08-26T03:25:49Z`
- Turn complete: approximately `2026-08-26T03:29:09Z`

Human UI checks:

- Approximately 30 seconds: `NOT_VISIBLE`
- `2026-08-26T03:31:03Z`: user confirmed Probe 1 and Probe 2 had both appeared
  in the Codex App project list.

No evidence was obtained that Codex App discovered Probe 2 before the turn
completed. The thread later appeared automatically in Codex App.

## Conclusion

Verified:

External official `codex app-server --stdio` can create:

- durable Codex threads;
- correct cwd/project binding;
- persistent `read` / `list` / `resume` lifecycle;
- threads that eventually appear in the Codex App project.

Not verified:

- A newly created external App Server thread is stably and promptly discovered
  by an already-running Codex App while a turn is still executing.
- Codex App is a reliable live monitoring UI for Reviewed Handoff Executor
  progress.
- Multiple App Server/App clients can safely write or take over the same thread.

Current verdict:

```text
APP_VISIBLE_POST_COMPLETION_ONLY
```

This does not mean threads are technically incapable of appearing before
completion. It means the 2026-08-26 experiments only produced reliable
post-completion UI visibility evidence, not bounded live-discovery evidence.

## Production Implication

Reviewed Handoff should not use App Server as its production Executor launcher
yet.

The only product shape that looked plausible was:

```text
one Executor event = one new App Server thread
watcher/App Server = sole writer
Codex App = delayed-discovery observation UI
repair/new Executor event = new thread
no cross-event resume of an old Executor thread
```

However, because live discovery was not verified, this is not production-ready
for Executor monitoring. A running automatic Executor thread should be treated
as read-only from the user's perspective; if a user sends messages into a
running automatic thread, writer ownership can conflict with automation.

## Re-Test Conditions

Do not periodically rerun this probe merely because discovery might be faster on
another attempt.

Re-test only after at least one real product capability changes:

- Codex CLI/App Server version upgrades and changes thread discovery or
  lifecycle behavior.
- Official support appears for connecting to the currently running Codex App
  App Server instance through a stable API.
- Official shared App Server, attach, discover, or IPC mechanism is exposed.
- Codex App explicitly supports live discovery of externally created App Server
  threads.
- Writer ownership or `thread/resume` semantics change.
- Official documentation promises running external threads appear in Codex App
  in real time.

Until then, keep `codex exec` as the Reviewed Handoff production runtime and use
the existing watcher status / notifier observability path.
