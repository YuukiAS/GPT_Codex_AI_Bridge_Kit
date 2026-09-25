# TODO — Bridge main / formal release distribution drift

Status: NEW / HIGH PRIORITY / RELEASE-DISTRIBUTION BLOCKER
Recorded: 2026-09-25

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
