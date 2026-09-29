# Reviewed Handoff First Remote Publication — Gate Matrix Result V2

Repaired candidate: `9dad0ba4bfa54e251f345091c5151ae991251ec9`

## Summary

```text
FP_G1=PASS
FP_G2=PASS
FP_G3=PASS
FP_G4=PASS
FP_G5=PASS
FP_G6=PASS
OVERALL=PASS_FOR_PRE_FINAL_CRITIC
```

## FP-G1 — Atomic first-create

Result: `PASS`

Evidence:

- Positive helper tests create the exact derived reviewed branch/ref and bind
  same-name upstream only after post-read SHA equality.
- Publish argv keeps the fixed empty expected lease:
  `--force-with-lease=refs/heads/reviewed/<task_key>:` with no leading `+`.
- Existing destination rejects with `REMOTE_TASK_BRANCH_ALREADY_EXISTS`.
- Concurrent-create simulation rejects failed lease output without binding
  upstream.
- Local bare-Git semantics remain covered by the focused suite.
- Fresh FP-G6 real GitHub consumer created exactly one absent remote branch:
  `origin/reviewed/workflow-core--first-remote-publication-repair-gate`.

## FP-G2 — History/raw-object/path/blob/identity fence

Result: `PASS`

Evidence:

- Positive helper tests validate raw direct child, raw `A/A` REQUEST/CURRENT,
  regular blobs, task identity, base identity, worktree locator, and first-state
  CURRENT contract.
- Deterministic pre-network negatives now include the repaired identity checks:
  - wrong `CURRENT.schema`;
  - wrong `CURRENT.base_branch`;
  - wrong state;
  - wrong next_action;
  - nonzero review_round;
  - nonzero plan_revision;
  - non-null implementation_commit;
  - source leak in same first commit;
  - two-commit branch;
  - active grafts;
  - SSH transport.
- Replace-ref regression still proves ordinary replacement-aware history can
  appear benign while `--no-replace-objects` exposes the illegal source path;
  helper rejects before remote/config mutation.
- Comments-only/blank graft file remains accepted.

## FP-G3 — Dangerous-neighbor isolation

Result: `PASS`

Evidence:

- Installed Machine Policy validation reports the bounded
  `ai-bridge reviewed-handoff task publish-first ...` entry as `allow`.
- Neighbor dangerous Git shapes remain on the prompt path:
  `git push -u`, `git push --set-upstream`, arbitrary new branch push,
  force, force-with-lease, delete, tag/release-style mutation, and remote/remap
  operations are not trusted by this repair.
- Parser still rejects caller selector expansion such as `--remote`.
- No Machine Policy install or refresh was performed.

## FP-G4 — Generic publisher should-not-change

Result: `PASS`

Evidence:

- Focused host publisher regression tests passed inside
  `tests.test_host_policy`.
- Existing same-name GitHub HTTPS publication behavior remains covered.
- Wrong repo/branch, remote-ahead, missing same-name remote, SSH/scp/custom
  transports, HTTPS fetch / SSH push mismatch, process/config/askpass/
  credential/hook fences, mirror/followTags/submodule/push-option/signing
  fences, and Reviewed executor guard regressions remain covered.
- No behavior was added to `host publish-current-branch`.

## FP-G5 — Reviewed lifecycle should-not-change

Result: `PASS`

Evidence:

- Focused Reviewed regressions passed inside `tests.test_reviewed_handoff` and
  `tests.test_reviewed_runner`.
- Bootstrap still requires exact repo/task/base/deterministic sibling behavior,
  origin-only fetch profile, existing reviewed remote-branch rejection,
  executable/output fences, and invocation rollback.
- Materialize/resume still covers local artifact-bound resume, remote-only exact
  reviewed-branch resume, remote metadata validation before checkout, partial
  local metadata fail-closed behavior, and canonical main preservation.
- Watcher/Executor publication authority remains unchanged.

## FP-G6 — Fresh real consumer

Result: `PASS`

Evidence file:

`results/reviewed-handoff--first-remote-publication/FP_G6_REAL_CONSUMER_V2.md`

Key identity:

```text
CONSUMER_REPOSITORY=YuukiAS/AI_Skills_Collection
BASE=a7028195f3e97d32d51c32ef8c87f658f92048e5
TASK=workflow-core--first-remote-publication-repair-gate
BRANCH=reviewed/workflow-core--first-remote-publication-repair-gate
WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-repair-gate
REMOTE_BRANCH_SHA=ddd2844635abeb585e075fbcc18373c730ce61d1
```

## Not claimed

```text
FORMAL_RELEASE_DISTRIBUTION=NOT_CLAIMED
PRESENTATIONS_F03=NOT_CLOSED
ALL_MACHINES_UPDATED=NOT_CLAIMED
GENERIC_GIT_PUSH_TRUSTED=NO
ARBITRARY_REMOTE_BRANCH_CREATION_TRUSTED=NO
MACHINE_POLICY_REINSTALLED_OR_REFRESHED=NO
```
