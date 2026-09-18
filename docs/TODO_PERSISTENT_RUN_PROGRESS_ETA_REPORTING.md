# TODO — Persistent Run Progress & ETA Reporting

Status: **TODO / requirement captured; implementation not designed yet**

## Problem

Current Persistent Run focuses on making long-running work survive Codex / SSH disconnects and remain recoverable. For real overnight or multi-hour jobs, "the process is still alive" is not enough for the user to decide whether to leave it running, inspect it, or intervene.

The missing capability is regular, user-visible progress reporting with a useful estimate of remaining time.

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
