# TODO — Bridge main / formal release distribution drift

Status: NEW / LOW PRIORITY / DEFERRED
Recorded: 2026-09-25

## Problem

Bridge Kit production source on `main` is already at `0.9.1`, while the currently consumed formal release/distribution baseline used by machine sync is still `0.8.5`.

Observed consequence:

- repository source and integrated evidence can report `0.9.1`;
- a machine-level "sync this machine" path that intentionally follows the formal released baseline can still remain on `0.8.5`;
- therefore "main implementation closure" is not equivalent to "formal release/distribution closure".

This is a release/distribution lifecycle gap, not evidence that the `0.9.0/0.9.1` implementation itself is incomplete.

## Why this is not urgent

Current Longleaf machines can use the exact checked-out `0.9.1` source/runtime directly when explicitly configured. The immediate Reviewed Mode first-bootstrap failure has already been closed on the production candidate and integrated source.

Do not create a new architecture task merely to remove the version skew.

## Future closure

When Bridge packaging/distribution is next touched, verify the actual release mechanism used by machine sync and decide whether to publish a formal release/tag for the current integrated version.

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
