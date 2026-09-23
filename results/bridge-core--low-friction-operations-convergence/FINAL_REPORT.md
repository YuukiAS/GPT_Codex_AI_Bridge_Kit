# Bridge Kit 0.9.0 Low-Friction Operations Convergence Recovery

## Status

`37a773cd83971d64f194a7d82c55a24889bd8164` is the current recovery code candidate. It includes the B1-B3 repairs from `47cea1edb5bcb0d8038c4c6bd925f2f1ccd5c90c`, a CI environment guard for hosted runners without `codex`, and a Python 3.14 test cleanup stability fix, but this is **not** a full final PASS / release-closure claim.

The previous implementation candidate `88fa67c44e6e491ed548f033ce0d3c33f63525c4` was the pre-final Critic recovery baseline. Its old complete wording is superseded by this report.

## What changed

- Publisher preflight now rejects transport/config/credential/askpass injection before any remote/network Git preflight.
- Persistent Run now has an event-driven reporter with local latest/history and reconnect query.
- Reviewed materializer now uses stable frozen worktree identity, checks bootstrap base lineage, and rolls back only invocation-created local state when safe.

## Verified

- Local focused recovery tests pass: `Ran 121 tests ... OK`.
- Local full suite passes: `Ran 394 tests ... OK`.
- GitHub Actions run `35895831666` passed on Python 3.9 and Python 3.x.
- Live `/home/yuukias/.codex` Machine Policy validates.
- Bounded publisher published recovery code candidate `37a773c` to `origin/main`; fetch verified it before later evidence-only reporting updates.
- Publisher canary negatives did not execute canaries and did not mutate remote refs.
- Reviewed materializer normal-entry sibling bootstrap and `/tmp` rematerialization passed.
- Persistent Run reporter normal-entry multi-event and UNKNOWN/stall cases passed.
- Official Codex plugin reinstall path succeeded for `workflow-core@yuukias-ai-skills`.
- Notifications delivery is now proven through existing configuration: `send-test` and a structured `operational_progress` brief both sent successfully.

## Not Closed

- Standard SSH positive publication could not be proven: GitHub SSH returned `Permission denied (publickey)` and could not write `known_hosts`.

## Evidence

See `results/bridge-core--low-friction-operations-convergence/EVIDENCE.md`.

## Current Conclusion

Implementation repair is substantially complete, but final release closure remains blocked by the missing standard GitHub SSH positive path. Do not treat this as a completed 0.9.0 release PASS.
