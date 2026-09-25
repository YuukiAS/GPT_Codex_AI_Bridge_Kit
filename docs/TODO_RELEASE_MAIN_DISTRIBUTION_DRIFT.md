# TODO — Bridge main / formal release distribution drift

Status: CLOSED / RESOLVED
Recorded: 2026-09-25
Closed: 2026-09-25

## Resolution

Bridge Kit `0.9.1` formal distribution closure was completed on 2026-09-25 by
advancing the existing canonical `release` ref.

Authoritative release source consumed by the normal machine-sync path:

```text
refs/heads/release
```

Release identity:

```text
version: 0.9.1
release ref: origin/release
release target: f8ccfc8cedcc30d2644f23dd54ee00a292e021fd
production identity: a41c2e32c630aaf2a200ca336f04c4ea31650786
previous release baseline: d27259d6706dee951dc0c0ede8c9b03c65f55ca3 (0.8.5)
```

Verification:

- `origin/release` now resolves to
  `f8ccfc8cedcc30d2644f23dd54ee00a292e021fd`.
- `origin/release:pyproject.toml` declares version `0.9.1`.
- `origin/release:ai_bridge_kit/__init__.py` declares `__version__ = "0.9.1"`.
- The machine update path's authoritative source is the formal `release` ref,
  so normal `sync this machine` selection now resolves Bridge Kit `0.9.1`
  instead of `0.8.5`.
- Git tag / GitHub Release are not part of the current canonical Bridge Kit
  machine-sync release mechanism and were not created for this closure.
- `a41c2e32c630aaf2a200ca336f04c4ea31650786..f8ccfc8cedcc30d2644f23dd54ee00a292e021fd`
  contains only final evidence, README documentation, and this distribution
  TODO record; no Bridge production source, Machine Policy, template, test, or
  package-version drift was present.

The remaining history below is retained as provenance for why this closure was
needed.

## Problem

Bridge Kit production source on `main` is already at `0.9.1`, while the currently consumed formal release/distribution baseline used by machine sync is still `0.8.5`.

Observed consequence:

- repository source and integrated evidence can report `0.9.1`;
- a machine-level "sync this machine" path that intentionally follows the formal released baseline can still remain on `0.8.5`;
- therefore "main implementation closure" is not equivalent to "formal release/distribution closure".

This is a release/distribution lifecycle gap, not evidence that the `0.9.0/0.9.1` implementation itself is incomplete.

## Why this is urgent

The normal multi-machine distribution path is part of the user-visible capability. If `sync this machine` follows the formal released baseline and that baseline remains `0.8.5`, then other machines can sync successfully yet still miss the already-integrated `0.9.0/0.9.1` behavior. This means source implementation closure is not sufficient for operational closure across machines.

Treat this as a release/distribution blocker for claiming Bridge `0.9.1` is fully closed for normal multi-machine use. Do not require a new architecture task merely to fix the version skew; the next action is bounded release/distribution closure using the existing release mechanism.

## Future closure

Close this before relying on `sync this machine` as the normal way to propagate Bridge `0.9.1`. Verify the actual release mechanism used by machine sync, then publish/advance the formal release/tag through the existing release process if the current integrated candidate is still the approved release candidate.

Minimum closure evidence:

1. identify the authoritative release source consumed by `sync this machine`;
2. verify repository `main`, package version, formal release/tag, and machine-sync selected version are intentionally aligned;
3. prove one representative machine sync selects the intended released Bridge version;
4. do not silently make machine sync follow arbitrary unreleased `main`;
5. preserve rollback to the previous released version.

If the repository intentionally keeps `main` ahead of formal release, document that state explicitly and ensure user-facing status distinguishes:
- integrated/main version;
- formal released version;
- installed machine version.

## Non-goal

Do not publish a release, create a tag, or change machine sync behavior as part of this TODO record.
