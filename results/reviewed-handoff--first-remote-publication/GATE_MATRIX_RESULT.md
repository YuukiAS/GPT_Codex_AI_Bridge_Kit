# Reviewed Handoff First Remote Publication — Gate Matrix Result

Final candidate: `db258e410a902337a826909f990d4dafb585b615`

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

- Positive helper test created the exact derived reviewed branch/ref and bound
  upstream only after mocked post-read SHA equality.
- Push argv includes
  `--force-with-lease=refs/heads/reviewed/<task_key>:` and no leading `+`.
- Existing destination rejects with `REMOTE_TASK_BRANCH_ALREADY_EXISTS`.
- Concurrent-create simulation rejects failed lease output without binding
  upstream.
- Local bare-Git semantics test proves the empty expected lease rejects an
  already-existing destination with a different remote tip.
- FP-G6 real GitHub consumer created exactly one absent remote branch:
  `origin/reviewed/workflow-core--first-remote-publication-gate`.

## FP-G2 — History/raw-object/path/blob fence

Result: `PASS`

Evidence:

- Positive helper test validates raw direct child, raw `A/A` REQUEST/CURRENT,
  regular blobs, task identity, base identity, worktree locator, and first-state
  CURRENT contract.
- Deterministic pre-network negatives cover:
  - source leak in same first commit;
  - two-commit branch;
  - wrong state;
  - wrong next_action;
  - nonzero review_round;
  - nonzero plan_revision;
  - non-null implementation_commit;
  - active grafts;
  - SSH transport.
- Replace-ref regression proves ordinary replacement-aware history can appear
  benign while `--no-replace-objects` exposes the illegal source path; helper
  rejects before remote/config mutation.
- Comments-only/blank graft file remains accepted.

## FP-G3 — Dangerous-neighbor isolation

Result: `PASS`

Evidence:

- Installed Machine Policy validation reports:
  - `ai-bridge reviewed-handoff task publish-first ... => allow`;
  - `git push -u origin test-branch => prompt`;
  - `git push --set-upstream origin test-branch => prompt`;
  - `git push origin --force main => prompt`;
  - `git push origin main --force => prompt`;
  - `git push origin main --force-with-lease => prompt`;
  - `git push --force-with-lease origin main => prompt`;
  - `git push origin --delete test-branch => prompt`;
  - `git push origin test-branch => prompt`.
- Parser rejects selector expansion such as `--remote`.

## FP-G4 — Generic publisher should-not-change

Result: `PASS`

Evidence:

- Focused host publisher regression tests passed inside:
  `tests.test_host_policy`.
- Existing same-name GitHub HTTPS publication behavior remains covered.
- Wrong repo/branch, remote-ahead, missing same-name remote, SSH/scp/custom
  transports, fetch/push mismatch, process environment/config/askpass/
  credential/hook fences, mirror/followTags/submodule/push-option/signing
  fences, and Reviewed executor guard regressions remain covered.
- No new branch creation behavior was added to `host publish-current-branch`.

## FP-G5 — Reviewed lifecycle should-not-change

Result: `PASS`

Evidence:

- Focused Reviewed regressions passed inside:
  `tests.test_reviewed_handoff` and `tests.test_reviewed_runner`.
- Bootstrap still requires exact repo/task/base/deterministic sibling behavior,
  origin-only fetch profile, zero fetch/ls-remote/push/provider calls, existing
  reviewed remote-branch rejection, executable/output fences, and invocation
  rollback.
- Materialize/resume still covers local artifact-bound resume, remote-only
  exact reviewed-branch resume, remote metadata validation before checkout,
  partial local metadata fail-closed behavior, and canonical main preservation.
- Watcher/Executor publication authority remains unchanged.

## FP-G6 — Fresh real consumer

Result: `PASS`

Evidence file:

`results/reviewed-handoff--first-remote-publication/FP_G6_REAL_CONSUMER.md`

Key identity:

```text
CONSUMER_REPOSITORY=YuukiAS/AI_Skills_Collection
BASE=8d53dbbd8d67615e7ddb0b018f2109a3d8104178
TASK=workflow-core--first-remote-publication-gate
BRANCH=reviewed/workflow-core--first-remote-publication-gate
WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
REMOTE_BRANCH_SHA=3faaa9f3be702fdbb7f96ff3eb66d25d574dd227
```

## Not claimed

```text
FORMAL_RELEASE_DISTRIBUTION=NOT_CLAIMED
PRESENTATIONS_F03=NOT_CLOSED
ALL_MACHINES_UPDATED=NOT_CLAIMED
GENERIC_GIT_PUSH_TRUSTED=NO
ARBITRARY_REMOTE_BRANCH_CREATION_TRUSTED=NO
```
