# Reviewed Handoff First Remote Publication — Acceptance Matrix v0.1

Date: **2026-09-29**  
Task key: **reviewed-handoff--first-remote-publication**  
Approved design: **v0.4 @ cedd6f1dc2c13af7e237fc0ab2c07ba73700472a**  
Canonical Goal: **docs/design/reviewed_handoff_first_remote_publication_goal_v0.1_2026-09-29.md**  
Status: **FROZEN FOR EXECUTION_READY CRITIC REVIEW / NOT EXECUTION AUTHORIZATION**

All release-critical evidence must bind to one exact final Bridge candidate commit. Development regressions may be rerun before freeze; FP-G6 starts only after final candidate freeze, deterministic final-candidate gates, CI, and installed-command verification.

## 1. Required local test commands

Focused final-candidate suite:

```bash
python -m unittest -v \
  tests.test_reviewed_handoff \
  tests.test_host_policy \
  tests.test_reviewed_runner \
  tests.test_repo_cli_compat \
  tests.test_version_parity
```

Full final-candidate suite:

```bash
python -m unittest discover -v
```

Real GitHub CI:

```text
.github/workflows/tests.yml
Python 3.9 = PASS
Python 3.x = PASS
candidate commit = exact final Bridge candidate
```

Do not substitute tests from another commit.

## 2. Mutation-safety evidence convention

For every deterministic negative that claims “before remote/config mutation,” the test must record/assert all applicable pre/post invariants:

- no new destination remote ref;
- existing remote ref OIDs unchanged;
- `branch.<reviewed-branch>.remote` unchanged;
- `branch.<reviewed-branch>.merge` unchanged;
- no push invocation reached when failure belongs to pre-mutation validation;
- no remote delete/rewrite fallback;
- no unrelated worktree/ref/config cleanup.

Existing fake-GitHub network harnesses may be reused for deterministic transport tests. Local bare repositories may be used to prove raw Git lease semantics. Neither substitutes for FP-G6 real GitHub normal-entry evidence.

## 3. FP-G1 — Atomic first-create

Capability: exact first remote creation for one approved Reviewed task, without updating an existing destination and without second user approval.

### Positive

Fixture:

```text
brand-new reviewed task
single raw direct-child commit
A REQUEST.md
A CURRENT.json
destination absent
upstream unset
canonical HTTPS transport/config
```

Required observations:

- helper derives exact branch/ref/remote/source;
- push argv includes fixed
  `--force-with-lease=refs/heads/reviewed/<task_key>:`;
- no caller-controlled lease/refspec;
- push source is captured raw HEAD OID;
- exact remote ref is created;
- post-read SHA equals captured raw HEAD;
- only then local same-name origin upstream is bound;
- command reports success.

### Concurrent-create negative

Deterministic race:

1. helper pre-read observes destination absent;
2. before mutation, another actor creates the exact destination ref, including the important case where concurrent tip is an ancestor of captured HEAD;
3. helper attempts its fixed empty-expect lease publication.

Required result:

```text
lease rejects
existing remote ref is not fast-forwarded/updated
no complete-success result
no remote delete
no unsafe retry
```

Also include a local bare-Git semantics test proving empty expected lease means destination must not exist.

## 4. FP-G2 — History/raw-object/path/blob first-publication fence

Capability: the permanently bounded first-publication entry can publish only the exact first-bootstrap control commit that will actually be transferred.

### Positive

Required:

```text
raw captured HEAD parent count = 1
raw only parent = CURRENT.base_commit
base..HEAD count = 1 secondary check
raw base tree lacks REQUEST/CURRENT
raw no-renames diff:
A REQUEST.md
A CURRENT.json
only
raw HEAD tree entries = regular blobs
captured raw blobs pass task/base/worktree/state contract
```

### Required deterministic negatives

Each must fail before remote/config mutation.

1. history laundering:
   ```text
   base
   -> commit production/source
   -> revert/delete source
   -> commit REQUEST/CURRENT
   -> publish-first
   => FAIL
   ```
2. two metadata-only commits -> FAIL;
3. one commit adds REQUEST/CURRENT + production source -> FAIL;
4. one commit adds REQUEST/CURRENT + test path -> FAIL;
5. one commit adds REQUEST/CURRENT + results artifact -> FAIL;
6. one commit adds REQUEST/CURRENT + PLAN.md -> FAIL;
7. one commit adds REQUEST/CURRENT + unrelated docs -> FAIL;
8. one commit adds REQUEST/CURRENT + other task metadata -> FAIL;
9. rename unallowed path into an allowed path; with rename detection disabled, illegal D/A path effect -> FAIL;
10. copy where source is changed/deleted -> source path appears -> FAIL;
11. unchanged source copied into allowed path but REQUEST/CURRENT content/identity invalid -> parser/identity FAIL;
12. merge commit -> raw parent-count FAIL;
13. merge side-history laundering -> raw parent-count FAIL;
14. REQUEST or CURRENT already exists in raw base tree -> FAIL;
15. either allowed path status is not exact `A` -> FAIL;
16. missing/partial/mismatched blobs -> FAIL;
17. wrong task key -> FAIL;
18. wrong base commit/base branch -> FAIL;
19. wrong frozen sibling worktree locator -> FAIL;
20. wrong current branch -> FAIL;
21. wrong state -> FAIL;
22. wrong next_action -> FAIL;
23. `plan_revision != 0` -> FAIL;
24. `implementation_commit != null` -> FAIL;
25. dirty worktree -> FAIL.

### Replace-ref regression

Construct actual raw HEAD:

```text
raw parent = base
raw tree:
A REQUEST
A CURRENT
A src/leak.txt
```

Install `refs/replace/<HEAD>` pointing to a benign replacement commit whose presented tree contains only REQUEST/CURRENT.

First prove the fixture is meaningful:

- ordinary replacement-aware object/history/tree inspection appears benign;
- `--no-replace-objects` exposes `src/leak.txt`.

Then invoke `publish-first`.

Required:

```text
FAIL BEFORE REMOTE/CONFIG MUTATION
failure attributable to raw/no-replacement tree/path fence
remote destination absent
upstream unset
```

### Graft regression

Construct real multi-commit history, then active `info/grafts` that makes ordinary ancestry display appear as a direct child/count-one history.

Required:

```text
publish-first
=> ACTIVE_GRAFTS_REQUIRE_ORDINARY_APPROVAL
=> FAIL BEFORE REMOTE/CONFIG MUTATION
```

Comments-only/blank graft file may remain accepted; any non-comment/nonblank active/malformed record fails closed.

## 5. FP-G3 — Dangerous-neighbor isolation

Capability: the new bounded allow does not generalize Git publication authority.

Deterministic Host/execpolicy tests must prove:

```text
ai-bridge reviewed-handoff task publish-first ... => allow
git push -u origin ... => prompt
git push --set-upstream origin ... => prompt
git push --force-with-lease ... => prompt
git push origin --force-with-lease ... => prompt
git push origin --force ... => prompt
git push origin --delete ... => prompt
raw arbitrary new branch push => prompt
```

Helper parser/API must expose no option for:

- lease;
- expected OID;
- source/destination ref;
- refspec;
- force;
- remote;
- upstream;
- custom transport.

Negative tests also cover tag/mirror/extra-refspec/remap/custom transport.

Phase-5 installed Machine Policy must reproduce the allow/prompt boundary with real `codex execpolicy check`/Host validation, not only template string checks.

## 6. FP-G4 — Generic publisher should-not-change

Run all current `publish_current_branch` focused regressions in `tests/test_host_policy.py`.

At minimum preserve:

- existing same-name GitHub HTTPS branch positive;
- wrong repo/branch rejects;
- remote-ahead rejects;
- upstream remote/merge requirements unchanged;
- missing same-name remote still rejects;
- SSH/scp/custom transport rejects;
- fetch/push URL mismatch rejects;
- process env/config/askpass/credential/hook fences;
- mirror/followTags/submodule/push-option/signing fences;
- Review executor guard still rejects generic publisher use.

No new-branch creation behavior may be added to `host publish-current-branch`.

## 7. FP-G5 — Reviewed lifecycle should-not-change

Focused regressions must preserve:

### Bootstrap

- exact repo/task/base/deterministic sibling behavior;
- canonical origin-only fetch profile;
- bootstrap performs zero fetch/ls-remote/push/provider calls;
- existing remote reviewed branch blocks bootstrap;
- executable/output redirection fences;
- invocation-local rollback.

### Materialize/resume

- local artifact-bound resume;
- remote-only exact reviewed-branch resume;
- remote metadata read/validated before checkout;
- partial local metadata fail closed;
- wrong task/base/worktree/lineage fail closed;
- canonical main remains unpolluted.

### Watcher / Executor authority

- watcher remains publication owner for implementation progress;
- Executor guard cannot route through generic publisher;
- first-publication helper is unusable after initial `PLAN_REQUESTED / RUN_GPT_PLANNER` control state;
- no new watcher route/state is introduced.

## 8. FP-G6 — Fresh real consumer

This Gate is executed only after:

- exact final Bridge candidate commit frozen;
- final focused suite PASS;
- final full suite PASS;
- real GitHub CI PASS;
- exact candidate installed/available locally;
- candidate Machine Policy validated.

Frozen consumer:

```text
repo = YuukiAS/AI_Skills_Collection
checkout = /home/yuukias/AI_Skills_Collection
task = workflow-core--first-remote-publication-gate
branch = reviewed/workflow-core--first-remote-publication-gate
worktree = /home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
base = Phase-6 post-sync origin/main OID
```

Precondition:

- task metadata absent;
- local branch absent;
- exact remote branch absent;
- sibling path free;
- canonical consumer remote profile passes.

Normal entry:

```text
git fetch --all --prune
-> task bootstrap
-> one ordinary commit containing only A REQUEST + A CURRENT
-> installed ai-bridge reviewed-handoff task publish-first
-> remote exact SHA == local captured HEAD
-> local same-name origin upstream exact
-> fetch/read remote REQUEST/CURRENT
-> CURRENT = PLAN_REQUESTED / RUN_GPT_PLANNER
```

Required user-visible property:

- the user sends the one execution-ready-approved Kickoff containing exact task/branch/worktree/first-publication authorization;
- no second user approval is required merely because the exact remote reviewed branch does not yet exist.

Forbidden FP-G6 substitutions:

- Product UI Copy historical task;
- `/tmp` fixture;
- raw `git push -u`;
- manual second approval;
- alternate branch/worktree;
- Presentations task;
- AI_Skills production source edits;
- helper-only mocked success.

Do not delete FP-G6 remote branch as cleanup.

## 9. Final-candidate identity

Durable execution evidence must record:

```text
FINAL_BRIDGE_COMMIT
FINAL_BRIDGE_VERSION
PYPROJECT_VERSION
RUNTIME___VERSION__
AI_BRIDGE_EXECUTABLE_PATH
AI_BRIDGE_IMPORT_PATH
MACHINE_POLICY_TARGET
HOST_VALIDATE_RESULT
FOCUSED_TEST_RESULT
FULL_TEST_RESULT
GITHUB_CI_RUN/STATUS
FP_G1_RESULT
FP_G2_RESULT
FP_G3_RESULT
FP_G4_RESULT
FP_G5_RESULT
FP_G6_CONSUMER_REPO
FP_G6_TASK
FP_G6_BRANCH
FP_G6_REMOTE_HEAD
```

No evidence from another Bridge commit may be spliced into a final PASS.

Expected durable result paths:

```text
results/reviewed-handoff--first-remote-publication/IMPLEMENTATION_EVIDENCE.md
results/reviewed-handoff--first-remote-publication/GATE_MATRIX_RESULT.md
results/reviewed-handoff--first-remote-publication/FP_G6_REAL_CONSUMER.md
results/reviewed-handoff--first-remote-publication/FINAL_CANDIDATE_IDENTITY.md
```

These files are execution outputs, not new registries/state machines.

## 10. Version closure acceptance

Current verified owners:

```text
pyproject.toml = 0.9.2
ai_bridge_kit.__version__ = 0.9.2
```

If execution preflight still sees `0.9.2`:

- target candidate = `0.9.3`;
- update both version owners;
- `python -m unittest -v tests.test_version_parity` PASS;
- add a `0.9.3` CHANGELOG entry covering the bounded first-publication repair and safety fences;
- update README normal-entry/command guidance;
- do not advance release ref/tag.

If version has drifted, return Planner instead of choosing another release slot automatically.

## 11. Gate completion rule

```text
FP-G1 PASS
AND FP-G2 PASS
AND FP-G3 PASS
AND FP-G4 PASS
AND FP-G5 PASS
AND FP-G6 PASS
AND focused tests PASS
AND full tests PASS
AND real GitHub CI PASS
AND installed identity PASS
AND version/docs parity PASS
= READY_FOR_PRE_FINAL_CRITIC
```

This does not equal formal release/distribution complete.
