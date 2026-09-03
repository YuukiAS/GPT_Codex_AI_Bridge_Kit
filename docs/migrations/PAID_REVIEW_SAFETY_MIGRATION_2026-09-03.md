# Paid Review Safety Migration — 2026-09-03

Branch: `reviewed/paid_review_safety_migration_20260903`

This migration is the Bridge Kit companion for `YuukiAS/AI_Skills_Collection` task `infra_paid_review_safety_migration_20260903`.

Read first:

```text
AGENTS.md
docs/PAID_EXTERNAL_REVIEW_POLICY.md
```

## Required implementation

Text Review and Visual Review must share one generic paid-review budget guard rather than implementing separate ad-hoc counters.

Default contract:

```text
model: gpt-5.6-terra
max paid calls: 2
campaign reserved-cost hard ceiling: USD 0.50
per-call worst-case ceiling: USD 0.25
automatic paid retries: 0
```

Before each paid Responses request:

1. construct the exact request;
2. count exact request input tokens using `POST /responses/input_tokens`; image inputs must be included for Visual Review;
3. calculate worst-case cost with uncached input and the bounded maximum output;
4. verify exact model/pricing identity;
5. persistently reserve one call slot plus the full worst-case amount before sending;
6. only then send the review request.

Reservation must survive process/workflow rerun and must not be automatically refunded after failure or shorter actual output.

Use a consumer-provided task/campaign identity and a safe locking/concurrency strategy so two concurrent runs cannot both spend the same remaining campaign budget.

Current Terra price identity reviewed 2026-09-03:

```text
input = USD 2 / 1M tokens
cached input = USD 0.20 / 1M tokens
output = USD 12 / 1M tokens
```

Preflight uses uncached input. Model/pricing mismatch or unknown price must fail closed.

Billing/quota errors such as `credit_balance_exhausted`, project/org spend-limit errors and organization usage-limit errors must fail immediately with zero backoff.

Do not add Organization Admin API credentials or use organization/day cost buckets as the runtime gate.

## Review request boundaries

Text Review remains a review-only operation.

Visual Review uses image inputs only and returns textual review evidence. Do not enable image generation, web search, file search, computer use or other paid tools.

Both review types must expose enough non-secret receipt data for the consumer to prove:

- campaign identity;
- model;
- request count/reservations;
- exact input-token preflight result;
- worst-case reserved cost;
- actual response usage when a response succeeds;
- cumulative reserved cost;
- no secret value.

## Tests before consumer migration

Add regression tests for at least:

- text request preflight;
- visual request preflight including image input;
- per-call ceiling;
- campaign ceiling;
- max call count;
- persistence across restart/rerun;
- same-campaign concurrency/double-spend protection;
- zero automatic retry for billing/quota failures;
- model/pricing mismatch fail-closed;
- Text Review still returns valid review evidence;
- Visual Review still returns valid review evidence;
- no image-generation/tool capability is injected.

Do not perform a live paid OpenAI call in Bridge Kit implementation tests. The consumer migration owns the final tiny public-safe live smoke after the new project-scoped secret is configured.
