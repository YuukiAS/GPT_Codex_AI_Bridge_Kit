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
service tier: default
reasoning effort: low
max output tokens: 4096
paid tools: none
prompt cache: explicit mode with no cache breakpoints
```

A retry, workflow rerun, process restart, machine restart or fresh checkout must not reset the campaign budget.

## Pre-request reservation

Before a paid Responses request is sent:

1. construct the exact request;
2. count input tokens through `POST /v1/responses/input_tokens` using the provider-compatible projection of that exact request, preserving provider-supported token-relevant fields and the original `input`, including image inputs when present;
3. validate model, service tier, reasoning, tools and prompt-cache settings;
4. calculate worst-case cost from standard-tier USD 2.50/M input reservation plus bounded maximum output;
5. persistently reserve one paid call and the full worst-case amount;
6. only then send the request.

Reservation is not automatically refunded because actual output is shorter or because the request fails. This is a safety fuse, not accounting reconciliation.

The current reviewed Terra baseline as of 2026-09-03 is:

```text
input: USD 2 / 1M tokens
cached input: USD 0.20 / 1M tokens
output: USD 12 / 1M tokens
cache write: USD 2.50 / 1M tokens
```

Runtime preflight reserves input at USD 2.50 / 1M tokens, the reviewed worst standard input-side rate. Unknown/stale model pricing, model-ID mismatch, unexpected service tier, unsupported long-context pricing above 272,000 input tokens or malformed usage must fail closed.

Successful responses must persist both independent totals:

```text
cumulative_reserved_worst_case_cost_usd
cumulative_actual_model_cost_usd
```

Actual model cost is calculated only from verified standard-tier Terra response usage:

```text
regular_input_tokens = input_tokens - cached_input_tokens - cache_write_tokens
actual_model_cost_usd =
  regular_input_tokens * 2.00 / 1_000_000
  + cached_input_tokens * 0.20 / 1_000_000
  + cache_write_tokens * 2.50 / 1_000_000
  + output_tokens * 12.00 / 1_000_000
```

`usage.output_tokens` already includes reasoning tokens. Do not add reasoning tokens separately. If accounting cannot be verified, record `ACCOUNTING_UNVERIFIED`, preserve the existing reservation and refuse subsequent paid calls in the same campaign.

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

Image inputs must be included unchanged in the same provider-compatible input-token preflight projection. Platform `images/min` capacity is not a budget control.

## Trigger boundary

Paid review should be invoked explicitly by a bounded consumer workflow. Ordinary push/CI must not cause paid model calls.

## Secret boundary

Consumer repository secret names may remain separate for text and visual review. Bridge Kit must not encourage silent fallback from one missing review credential to an unrelated credential path.

Text Review uses `OPENAI_REVIEW_API_KEY` only. Visual Review uses `OPENAI_VISUAL_REVIEW_API_KEY` only. Neither runtime falls back to the other review credential or to a generic `OPENAI_API_KEY`.

Never print, persist or commit secret values.

## Evidence semantics

A Bridge Kit review result is review evidence, not final product authority. Consumer workflow/Planner/user acceptance owns the final product decision.
