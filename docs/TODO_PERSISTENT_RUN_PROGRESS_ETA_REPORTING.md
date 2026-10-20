# TODO — Persistent Run Progress & ETA Reporting

Status: **CLOSED / IMPLEMENTED / PROVEN (0.11.0 + 0.11.1 cadence repair)**

当前实现支持 project-native / bridge-child progress、latest/history、ETA/UNKNOWN、
stall 和显式 recover/resolve，并复用 machine Notifier transport。0.11.1 将最新观察
与上次逻辑投递的进度/时间分开：小 count/fraction 变化不绕过 cadence，频繁观察
也不推迟周期投递；默认 60 分钟、非测试最短 15 分钟。阶段、异常、终态和重大 ETA
变化仍可提前发送，已知 ETA ↔ UNKNOWN 总是重大变化。

实现：`ai_bridge_kit/persistent_run.py`；直接回归：
`tests/test_persistent_cadence.py`、`tests/test_persistent_run.py`、`tests/test_readiness.py`。
ETA estimator、生命周期、恢复分类与底层 Lite terminal 去重合同保持不变。
正式 normal-entry full chain 的历史证据：
`results/bridge-core--product-scope-reset/v6/391ff88/ACCEPTANCE_STATUS.json` 和
`results/bridge-core--product-scope-reset/v6/391ff88/replacement/OBSERVATION_SUMMARY.json`；
该短 canary 证明正式传输链，不冒充 60 分钟 cadence 实测。cadence 由 0.11.1 的
确定性时钟回归、全量本地测试和同 SHA CI 验证，不重新跑历史 live Gate。

没有原 Codex thread progress injection，不依赖 app-server、Progress display thread
或持久 reader。没有自动干预、取消或完成判定；旧设想不构成恢复废弃架构的要求。
总账见 [TODO 收口摘要](BRIDGE_TODO_CLOSURE_SUMMARY.md)。

## Historical request (superseded by the released contract)

## User-confirmed urgency

On 2026-09-23 the user explicitly reconfirmed that this should be handled in the
next Bridge workflow if practical. Persistent work must not leave the user
waiting for hours without knowing whether real progress is being made or how
much time is plausibly left.

The required experience is not merely an on-demand status command. During a
real long-running/persistent run, the system should surface periodic progress
updates at a reasonable cadence when an already-authorized delivery surface is
available, while avoiding minute-by-minute spam.

## Problem

Current Persistent Run focuses on making long-running work survive Codex / SSH disconnects and remain recoverable. For real overnight or multi-hour jobs, "the process is still alive" is not enough for the user to decide whether to leave it running, inspect it, or intervene.

The missing capability is regular, user-visible progress reporting with a useful estimate of remaining time.

A long run that is healthy but silent for hours is not an acceptable normal user experience merely because tmux/session/heartbeat evidence exists.

## Required user capability

For an overnight / unattended / persistent job, the user should be able to tell, without manually opening the tmux session:

- what stage the job is currently in;
- what concrete progress has been made since the previous report;
- what fraction / count of the known work is complete when the task exposes a meaningful denominator;
- the current estimated remaining time / expected completion time when a defensible estimate can be made;
- how uncertain that estimate is, or `UNKNOWN` when the run does not expose enough information for a trustworthy ETA;
- whether progress appears normal, stalled, materially slower than expected, or blocked;
- when the last real progress event occurred.

The purpose is operational decision support: the user should have enough information to decide whether the run should simply continue or whether manual inspection/intervention is warranted.

## Reporting behavior to design later

Do not implement a fixed mechanism from this TODO alone. The later Planner/Critic design round should decide the smallest reusable mechanism.

At minimum, consider:

1. A report at start/resume, important stage transitions, completion, failure, and material stalls.
2. Periodic reports during long stages at a configurable/adaptive cadence rather than noisy minute-by-minute spam.
3. ETA based on real stage counters, observed throughput, scheduler/runtime evidence, or project-provided estimates. Never invent a percentage or ETA merely to fill the field.
4. Re-estimation when throughput changes materially, with visible indication that the ETA moved.
5. Persistent/reportable state that survives ChatGPT/Codex/SSH disconnects and can be queried after reconnect.
6. Optional delivery through an existing notifier/channel where appropriate, without making a new notification stack mandatory for every repository.
7. No automatic cancellation, resource mutation, scope expansion, or other intervention merely because a report detects slow progress. Intervention remains a user/project decision unless separately authorized.

## Architectural boundary

This should extend Persistent Run observability, not create a new workflow class, controller role, watcher hierarchy, or mandatory orchestration system.

Project-specific jobs may expose different notions of progress (epochs, samples, files, simulation replicates, pipeline stages, scheduler wall time, etc.). Bridge Kit should standardize only the reusable reporting contract and transport/state hooks; the project remains responsible for supplying truthful task-specific progress signals.

## Future acceptance target

A representative real multi-hour / overnight Persistent Run should be able to demonstrate that:

- progress reports appear regularly without requiring a live Codex session;
- reports reflect actual run state rather than synthetic/fixed percentages;
- ETA is updated from observed evidence when possible and explicitly marked unknown when not possible;
- stage transitions, stalls, completion, and failure are surfaced promptly;
- after reconnect, the latest report and recent progress history are still available;
- the user can use the information to decide whether intervention is necessary.

Implementation route, cadence defaults, notifier integration, schema/state shape, and tests remain for a later reviewed design round.
