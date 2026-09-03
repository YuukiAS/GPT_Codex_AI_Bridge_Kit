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
service tier: default
reasoning effort: low
max output tokens: 4096
paid tools: none
prompt cache: explicit mode with no cache breakpoints
```

Before each paid Responses request:

1. construct the exact request;
2. count input tokens using `POST /v1/responses/input_tokens` with the provider-compatible projection of the exact request; original `input` values, including Visual Review image inputs, must pass through unchanged;
3. verify exact model, service tier, reasoning, tools and prompt-cache identity;
4. calculate worst-case cost with standard-tier USD 2.50/M input reservation and the bounded maximum output;
5. persistently reserve one call slot plus the full worst-case amount before sending;
6. only then send the review request.

Reservation must survive process/workflow rerun and must not be automatically refunded after failure or shorter actual output.

Use a consumer-provided task/campaign identity and a safe locking/concurrency strategy so two concurrent runs cannot both spend the same remaining campaign budget.

Current Terra price identity reviewed 2026-09-03:

```text
input = USD 2 / 1M tokens
cached input = USD 0.20 / 1M tokens
output = USD 12 / 1M tokens
cache write = USD 2.50 / 1M tokens
```

Preflight uses the conservative USD 2.50/M standard input-side reservation rate. Model/pricing mismatch, unknown price, unexpected service tier, malformed usage or input above the 272,000-token long-context threshold must fail closed.

Successful responses persist verified actual usage and both campaign totals:

```text
cumulative_reserved_worst_case_cost_usd
cumulative_actual_model_cost_usd
```

Actual model cost is:

```text
regular_input_tokens = input_tokens - cached_input_tokens - cache_write_tokens
actual_model_cost_usd =
  regular_input_tokens * 2.00 / 1_000_000
  + cached_input_tokens * 0.20 / 1_000_000
  + cache_write_tokens * 2.50 / 1_000_000
  + output_tokens * 12.00 / 1_000_000
```

Reasoning tokens are diagnostic because `usage.output_tokens` already includes them. If accounting cannot be verified, record `ACCOUNTING_UNVERIFIED`, preserve the reservation and refuse subsequent paid calls in the same campaign.

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
- cumulative actual model cost;
- no secret value.

Text Review must use only `OPENAI_REVIEW_API_KEY`; Visual Review must use only `OPENAI_VISUAL_REVIEW_API_KEY`. Neither runtime may borrow the other key or a generic `OPENAI_API_KEY`.

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
