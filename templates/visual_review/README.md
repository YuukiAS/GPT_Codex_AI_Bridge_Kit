# AI Bridge Visual Review

Visual Review is a shared optional evidence producer for Review and Control. It is not a new GPT role and it does not give Planner, Critic, Controller, Verifier, Executor, Scheduled GPT, local Codex, or local watchers access to an OpenAI API key.

Default live execution belongs in GitHub Actions:

```text
trusted branch push / workflow_dispatch
→ render or collect public-safe visual inputs
→ ai-bridge visual-review run
→ results/<task_key>/visual_review/VISUAL_REVIEW.json
→ existing Reviewer / Planner / Final Critic reads tracked evidence
```

The installed workflow installs the canonical Bridge Kit Git source pinned to
the ref rendered at install time. It does not vendor-copy `ai_bridge_kit/` into
the consumer repository and does not run `pip install -e .` against the
consumer project.

The installed workflow runs only on manual `workflow_dispatch`. Consumer
dispatch logic owns when a paid visual review is scientifically/product-wise
necessary.

Use the repository secret name `OPENAI_VISUAL_REVIEW_API_KEY`. In the workflow, map it only inside the visual review job:

```yaml
env:
  OPENAI_VISUAL_REVIEW_API_KEY: ${{ secrets.OPENAI_VISUAL_REVIEW_API_KEY }}
```

The production default Visual Review model is `gpt-5.6-terra`. Ordinary
consumer repositories do not need to set a model variable. An explicit CLI
`--model` value still takes priority over `OPENAI_VISUAL_REVIEW_MODEL`, which
takes priority over the Bridge Kit shared default, but the paid-review guard
currently accepts only the exact reviewed Terra pricing identity.

Every paid Visual Review request uses the shared Bridge Kit paid-review guard.
The default campaign contract is `gpt-5.6-terra`, at most two paid calls, USD
0.50 total reserved worst-case cost, USD 0.25 per call, and zero automatic paid
retries, `service_tier=default`, `reasoning.effort=low`,
`max_output_tokens=4096`, no tools, and explicit prompt-cache mode with no
cache breakpoint. A provider-compatible projection of the canonical request is
counted first through `POST /v1/responses/input_tokens`, with original image
inputs preserved unchanged; input-side reservation uses the conservative
standard-tier USD 2.50/M cache-write rate; the full worst-case
amount is reserved in
`results/<task_key>/paid_review_budget.json`; only then is the Responses request
sent. GitHub Actions uses repo-wide concurrency and writes the reservation
commit before the paid request so reruns and fresh checkouts cannot reset the
campaign budget. Requests above 272,000 input tokens fail closed before
`/v1/responses`. Actual model cost is calculated from successful response usage
and never refunds the reservation.

Unknown pricing or any model mismatch fails closed.

Recommended OpenAI setup:

```text
OpenAI Project: AI Bridge Visual Review
one restricted project-scoped key per repository
```

Default privacy policy is `PUBLIC_SAFE_ONLY`. Do not upload patient images, private clinical data, unpublished research images, credentials, private screenshots, or proprietary assets unless the project profile or task manifest contains explicit external upload authorization.

Visual Review sends image inputs only as Responses input. It does not enable
image generation, web search, file search, computer use or any extra paid tool.

Preflight:

```bash
ai-bridge visual-review preflight --target <repo>
```

This checks whether visual review is configured, whether a GitHub workflow references the standard secret name, and, when `gh` is available and logged in, whether `gh secret list` shows `OPENAI_VISUAL_REVIEW_API_KEY`. It never reads the secret value.

Generated evidence must stay under the repository-relative path
`results/<task_key>/visual_review/**`. Evidence-only commits do not retrigger
the visual review job because the workflow only listens for the input manifest.
