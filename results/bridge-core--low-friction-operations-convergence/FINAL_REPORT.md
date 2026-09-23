# Bridge Kit 0.9.0 Low-Friction Operations Convergence Recovery

## Status

`47cea1edb5bcb0d8038c4c6bd925f2f1ccd5c90c` repairs B1-B3 from the recovery goal, but this is **not** a full final PASS / release-closure claim.

The previous implementation candidate `88fa67c44e6e491ed548f033ce0d3c33f63525c4` was the pre-final Critic recovery baseline. Its old complete wording is superseded by this report.

## What changed

- Publisher preflight now rejects transport/config/credential/askpass injection before any remote/network Git preflight.
- Persistent Run now has an event-driven reporter with local latest/history and reconnect query.
- Reviewed materializer now uses stable frozen worktree identity, checks bootstrap base lineage, and rolls back only invocation-created local state when safe.

## Verified

- Local focused recovery tests pass: `Ran 121 tests ... OK`.
- Local full suite passes: `Ran 394 tests ... OK`.
- Live `/home/yuukias/.codex` Machine Policy validates.
- Bounded publisher published `47cea1e` to `origin/main`; fetch verified `HEAD == origin/main`.
- Publisher canary negatives did not execute canaries and did not mutate remote refs.
- Reviewed materializer normal-entry sibling bootstrap and `/tmp` rematerialization passed.
- Persistent Run reporter normal-entry multi-event and UNKNOWN/stall cases passed.
- Official Codex plugin reinstall path succeeded for `workflow-core@yuukias-ai-skills`.

## Not Closed

- Standard SSH positive publication could not be proven: GitHub SSH returned `Permission denied (publickey)` and could not write `known_hosts`.
- Notifications delivery could not be tested because no existing provider/recipient is configured.
- GitHub Actions is red because hosted CI lacks `codex` for execpolicy tests.

## Evidence

See `results/bridge-core--low-friction-operations-convergence/EVIDENCE.md`.

## Current Conclusion

Implementation repair is substantially complete, but final release closure remains blocked by environment/evidence gaps rather than source changes. Do not treat this as a completed 0.9.0 release PASS.
