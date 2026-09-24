# Bridge Kit 0.9.0 Low-Friction Operations Convergence Recovery

## Status

`160166b0276e3f79e05252c8828f249d1d6409ae` is the task-owned HTTPS-only
publisher correction candidate. It has been published to `origin/main` through
the bounded GitHub HTTPS publisher and passed local and hosted tests.

This report updates the earlier recovery conclusion after Plan v0.4. The old
SSH positive failure remains historical evidence, but SSH positive publication
is no longer a release gate or product claim for 0.9.0.

Independent pre-final Critic result:

```text
CRITIC_RESULT=PASS
REVIEW_STAGE=PRE_FINAL
B1_PUBLISH_TRANSPORT_FENCE=CLOSED
B2_PERSISTENT_RUN_REPORTER=CLOSED
B3_REVIEWED_FROZEN_SCOPE=CLOSED
B4_FINAL_GATE_EVIDENCE=CLOSED
G3=PASS
G4=PASS
G14=PASS
PRODUCTION_REPAIR_REQUIRED=NO
READY_FOR_FINAL_CLOSURE=YES
```

## What Changed

- Trusted low-friction publication is now GitHub HTTPS only:
  `https://github.com/<owner>/<repo>.git`.
- SSH, scp-style, and custom transports now fail closed in the bounded
  publisher and route to ordinary approval.
- Publisher classification uses effective fetch/push URLs after Git URL
  rewriting.
- Shared `_canonical_repo_identity()` remains unchanged for Reviewed Handoff and
  local disposable repository use.

## Verified

- Focused host-policy tests pass: `Ran 27 tests ... OK`.
- Full local suite passes: `Ran 397 tests ... OK`.
- GitHub Actions passed for the publisher correction commit:
  `35947503209`.
- GitHub Actions passed for the later published main baseline:
  `35947601396`.
- `/home/yuukias/.codex` Machine Policy validates with installed
  `/home/yuukias/conda/bin/ai-bridge`.
- Bounded publisher published `160166b0276e3f79e05252c8828f249d1d6409ae` via
  GitHub HTTPS using existing credentials and ordinary non-force ref update.
- Effective SSH/scp/custom, literal HTTPS rewritten to SSH/custom, and HTTPS
  fetch / SSH push mismatch negatives fail closed before network.

## Product Boundary

- `trusted low-friction = GitHub HTTPS`
- `SSH/custom = ordinary approval`

The previous SSH positive failures are retained as provenance from the old
scope. Plan v0.4 removes SSH positive publication from the product claim; it
does not weaken the SSH/custom security negative gate.

## Evidence

See
`results/bridge-core--low-friction-operations-convergence/EVIDENCE.md`.

## Current Conclusion

The approved HTTPS-only scope correction is final-closed after independent
pre-final Critic PASS. Do not interpret this as a claim that SSH/custom
transports are trusted low-friction publication paths.
