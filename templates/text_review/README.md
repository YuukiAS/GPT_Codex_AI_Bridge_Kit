# AI Bridge Text Review

Text Review is a shared optional evidence producer for Review. It is
not a new GPT role. It lets a private UTF-8 Markdown/plain-text artifact be
reviewed by OpenAI through GitHub Actions without committing plaintext.

The production path is:

```text
private local text
-> age public-key encryption
-> encrypted payload + manifest committed to the reviewed task branch
-> GitHub Actions decrypts in a temporary runner directory
-> OpenAI Responses API with store=false reads the complete plaintext
-> results/<task_key>/text_review/TEXT_REVIEW.json
```

Tracked files may include the public age recipient, encrypted payload, manifest
and `TEXT_REVIEW.json`. Tracked files must never include the age private
identity, plaintext artifact or OpenAI API key.

Install:

```bash
ai-bridge text-review install --target /path/to/project
```

Configure transport:

```bash
ai-bridge text-review configure --target /path/to/project --repo owner/name
```

This generates an age keypair, writes the private identity to the GitHub Secret
`AI_BRIDGE_PRIVATE_REVIEW_AGE_KEY` through `gh secret set`, writes the public
recipient to `automation/reviewed_handoff/private_text_review.age.pub`, and
does not print the secret value.

If `gh` permissions are unavailable, configure exactly this GitHub Secret
manually. Do not paste the secret into chat or commit it to the repository.

OpenAI key in CI is:

```text
OPENAI_REVIEW_API_KEY
```

Text Review does not fall back to `OPENAI_VISUAL_REVIEW_API_KEY` or a generic
`OPENAI_API_KEY`.

Every paid Text Review request uses the shared Bridge Kit paid-review guard.
The default campaign contract is `gpt-5.6-terra`, at most two paid calls, USD
0.50 total reserved worst-case cost, USD 0.25 per call, and zero automatic paid
retries, `service_tier=default`, `reasoning.effort=low`,
`max_output_tokens=4096`, no tools, and explicit prompt-cache mode with no
cache breakpoint. The request is counted first through
`POST /v1/responses/input_tokens` using the provider-compatible projection of
the canonical request, input-side reservation uses the conservative
standard-tier USD 2.50/M cache-write rate, the full worst-case amount is reserved in
`results/<task_key>/paid_review_budget.json`, and only then is the Responses
request sent. Requests above 272,000 input tokens fail closed before
`/v1/responses`. GitHub Actions writes the reservation commit before the paid
request so reruns and fresh checkouts cannot reset the campaign budget. Actual
model cost is calculated from successful response usage and never refunds the
reservation.

The model default is `gpt-5.6-terra`. `OPENAI_TEXT_REVIEW_MODEL` and CLI
`--model` remain accepted for interface compatibility, but Bridge Kit currently
fails closed unless the selected model exactly matches reviewed Terra pricing.

Encrypt a private artifact from the user machine:

```bash
ai-bridge text-review encrypt \
  --target /path/to/project \
  --task-key 044_example \
  --input /private/path/final.md \
  --output results/044_example/text_review/payload.age \
  --manifest results/044_example/text_review/text_inputs.json \
  --implementation-commit <commit> \
  --rubric "Read the complete artifact and decide whether it satisfies the frozen user-facing prose requirements." \
  --external-upload-authorization "User authorized private text review through OpenAI Responses API with store=false for this task."
```

The `TEXT_REVIEW.json` evidence contains SHA-256 bindings and structured
findings, paid-review reservation receipt data, actual response usage when the
request succeeds, and no private plaintext.
