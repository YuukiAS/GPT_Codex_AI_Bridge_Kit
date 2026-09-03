# Paid External Review Safety Contract

Bridge Kit owns generic paid-review transport/runtime safety. Consumer repositories own whether a review is scientifically/product-wise necessary.

The canonical consumer policy for AI_Skills_Collection is `docs/workflows/PAID_EXTERNAL_REVIEW_POLICY.md`; this file freezes the reusable Bridge Kit mechanics so Text Review and Visual Review cannot become unbounded paid pipelines.

## Default runtime contract

Paid external review is final independent QA, not a replacement for the host model's ordinary generation, planning, intermediate reasoning, self-audit or local repair.

Bridge Kit Text Review / Visual Review must support a persistent task campaign budget with these defaults unless a consumer Plan explicitly freezes a stricter user-approved override:

```text
model: gpt-5.6-terra
max paid calls: 2
campaign reserved-cost hard ceiling: USD 0.50
per-call worst-case ceiling: USD 0.25
automatic paid retries: 0
```

A retry, workflow rerun, process restart, machine restart or fresh checkout must not reset the campaign budget.

## Pre-request reservation

Before a paid Responses request is sent:

1. construct the exact request;
2. count its exact input tokens through the provider-supported Responses input-token count path, including image inputs when present;
3. calculate worst-case cost from uncached input plus bounded maximum output;
4. validate model/pricing identity;
5. persistently reserve one paid call and the full worst-case amount;
6. only then send the request.

Reservation is not automatically refunded because actual output is shorter or because the request fails. This is a safety fuse, not accounting reconciliation.

The current reviewed Terra baseline as of 2026-09-03 is:

```text
input: USD 2 / 1M tokens
cached input: USD 0.20 / 1M tokens
output: USD 12 / 1M tokens
```

Runtime preflight uses uncached input. Unknown/stale model pricing or a model-ID mismatch must fail closed.

Do not use Organization Admin API credentials or organization/day cost buckets as the runtime gate.

## Retry classification

Default paid retry count is zero.

At minimum, these errors must fail immediately without sleep/backoff:

```text
credit_balance_exhausted
project_spend_limit_exceeded
organization_spend_limit_exceeded
organization_usage_limit_exceeded
```

If a consumer later authorizes a transient retry, it consumes the same campaign call slot and reservation budget.

## Text Review

Text Review may receive the candidate plus the frozen rubric/context required for independent judgment. It must not silently become a generation service.

## Visual Review

Visual Review uses supported image inputs and returns textual review evidence. It does not enable image generation, web search, file search, computer use or other paid tools unless a separate explicitly authorized product contract requires them.

Image inputs must be included in the same exact-request input-token preflight. Platform `images/min` capacity is not a budget control.

## Trigger boundary

Paid review should be invoked explicitly by a bounded consumer workflow. Ordinary push/CI must not cause paid model calls.

## Secret boundary

Consumer repository secret names may remain separate for text and visual review. Bridge Kit must not encourage silent fallback from one missing review credential to an unrelated credential path.

Never print, persist or commit secret values.

## Evidence semantics

A Bridge Kit review result is review evidence, not final product authority. Consumer workflow/Planner/user acceptance owns the final product decision.
