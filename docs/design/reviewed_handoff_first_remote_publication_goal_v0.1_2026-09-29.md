# Reviewed Handoff First Remote Publication — Canonical Goal v0.1

Goal version: **0.1**  
Date: **2026-09-29**  
Task key: **reviewed-handoff--first-remote-publication**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Target branch: **main**  
Future execution worktree: **/home/yuukias/GPT_Codex_AI_Bridge_Kit**  
Approved design: **docs/design/reviewed_handoff_first_remote_publication_plan_v0.4_2026-09-29.md @ cedd6f1dc2c13af7e237fc0ab2c07ba73700472a**  
Design PASS transfer: **docs/design/reviewed_handoff_first_remote_publication_design_pass_transfer_v0.1_2026-09-29.md**  
Status: **FROZEN EXECUTION GOAL / AWAITING EXECUTION_READY CRITIC REVIEW / NOT EXECUTION AUTHORIZATION**

This Goal converts the already-PASS design into a bounded implementation contract. It does not reopen architecture and does not itself authorize implementation, Machine Policy mutation, consumer execution, or release.

## 1. Positive completion

Implementation is complete only when one exact final Bridge candidate proves all of the following:

1. production CLI exposes exactly:
   `ai-bridge reviewed-handoff task publish-first --task-key <semantic-task-key> --expected-repo <owner/repo>`;
2. caller cannot select lease, expected OID, ref, refspec, force, destination, remote, or upstream;
3. branch, destination, source, and remote are fixed by the helper:
   - branch = `reviewed/<task_key>`;
   - destination = `refs/heads/reviewed/<task_key>`;
   - source = captured raw HEAD OID;
   - remote = `origin`;
4. all security-critical commit/tree/blob/history inspection uses fixed no-replacement semantics;
5. active legacy `info/grafts` fails closed before any remote/config mutation;
6. actual raw HEAD is exactly one direct child of `CURRENT.base_commit`;
7. the only raw single-commit tree effect is:
   - `A automation/reviewed_handoff/tasks/<task_key>/REQUEST.md`;
   - `A automation/reviewed_handoff/tasks/<task_key>/CURRENT.json`;
8. both paths are absent from the raw base tree, are regular files/blobs in the raw HEAD tree, and pass the frozen task/base/worktree/state identity contract;
9. final pre-mutation recheck repeats the complete raw-object, worktree, branch, config, transport, hook, destination-absence, and upstream-unset fences;
10. first remote creation uses the fixed internal empty-expect lease:
    `--force-with-lease=refs/heads/reviewed/<task_key>:`;
11. pre-read confirms destination absence, the explicit push has no leading `+`, push succeeds, and post-read remote SHA equals captured raw HEAD;
12. an already-existing destination is never updated by `publish-first`;
13. local upstream is bound only after successful remote creation plus post-read identity:
    - `branch.<branch>.remote = origin`;
    - `branch.<branch>.merge = refs/heads/reviewed/<task_key>`;
14. upstream-binding partial failure never deletes or rewrites the remote ref and never reports complete success;
15. ambiguous publication fails closed: no blind retry, auto-adopt, force, remote delete, or history rewrite;
16. generic `host publish-current-branch` behavior is unchanged;
17. bootstrap remains zero-network; materialize/resume and reviewed_runner/watcher publication authority remain unchanged;
18. Machine Policy allows only the bounded `reviewed-handoff task publish-first` entry while raw `git push -u`, raw force-with-lease, arbitrary new branches/refspecs, force/tag/delete/mirror/remap/alternate upstream remain gated;
19. FP-G1 through FP-G6 all pass on the same final Bridge candidate;
20. current package/runtime/docs are internally consistent as the next PATCH candidate;
21. no formal release ref, tag, PR, merge, or Presentations mutation occurs in this implementation task.

## 2. Exact implementation placement

Future execution is frozen to the existing canonical Bridge checkout:

```text
repo = YuukiAS/GPT_Codex_AI_Bridge_Kit
branch = main
worktree = /home/yuukias/GPT_Codex_AI_Bridge_Kit
```

Do not create another implementation branch or sibling worktree for this Bridge task.

At execution start, verify exact repo identity, branch, worktree path, current HEAD, clean/dirty ownership, origin identity, and current package version. If the canonical placement differs materially, stop with `NEEDS_GPT_PLANNER`; do not silently substitute another checkout.

## 3. Exact implementation surface

### 3.1 Primary production/runtime files

Allowed:

```text
ai_bridge_kit/reviewed_handoff.py
templates/host/rules/ai-bridge-global.rules
templates/host/GLOBAL_AGENTS_SNIPPET.md
templates/reviewed_handoff/README.md
```

`ai_bridge_kit/reviewed_handoff.py` owns:

- parser/routing for `task publish-first`;
- raw-object/graft/history/path/blob validation;
- exact first-publication transaction;
- upstream sequencing;
- partial/ambiguous failure semantics.

Top-level routing already sends all `reviewed-handoff` commands through `ai_bridge_kit.bridge_cli -> reviewed_handoff.main`; therefore:

```text
ai_bridge_kit/bridge_cli.py = SHOULD_NOT_CHANGE
ai_bridge_kit/cli.py = SHOULD_NOT_CHANGE
```

### 3.2 Host fence reuse

Conditionally allowed:

```text
ai_bridge_kit/host.py
```

Only if needed to avoid duplicating the existing GitHub HTTPS transport/config/environment/hook safety policy.

Permitted delta is limited to an internal shared extraction/refactor of already-existing publisher fences. Existing public `publish_current_branch()` success/failure semantics, existing-branch requirement, upstream requirement, remote-ahead behavior, result shape, and caller contract must remain unchanged.

If implementation would require changing generic publisher behavior, return `NEEDS_GPT_PLANNER`.

### 3.3 User-facing/runtime consistency files

Allowed and required where stated:

```text
AGENTS.md
README.md
CHANGELOG.md
pyproject.toml
ai_bridge_kit/__init__.py
```

- `AGENTS.md`: update the repository's Host-policy description so the exact Reviewed first-publication exception no longer contradicts the new bounded route; raw first push remains gated.
- `README.md`: required because `publish-first` is a user-visible Reviewed Handoff normal entry; update capability/command guidance, not duplicate version history.
- `CHANGELOG.md`: required at candidate version closure.
- `pyproject.toml` and `ai_bridge_kit/__init__.py`: version parity.
- `QUICKSTART.md`: checked at package preparation; it currently does not document Reviewed first-bootstrap normal-entry commands, so **no update is required** unless execution preflight finds a directly conflicting statement. Do not expand scope merely to add another command list.

### 3.4 Focused tests

Allowed:

```text
tests/test_reviewed_handoff.py
tests/test_host_policy.py
tests/test_reviewed_runner.py
tests/test_version_parity.py
```

`tests/test_reviewed_runner.py` is regression-only unless a directly matching authority test is needed; production `reviewed_runner.py` remains should-not-change.

Other test files require a direct demonstrated gap and must not broaden production scope.

## 4. Hard should-not-change surfaces

Unless a new execution blocker proves the approved scope impossible, do not change:

```text
ai_bridge_kit/bridge_cli.py
ai_bridge_kit/cli.py
ai_bridge_kit/reviewed_runner.py
bootstrap public contract
materialize-worktree public contract
Reviewed state/schema/transition model
watcher/Executor publication authority
generic publish-current-branch public semantics
release/ref machinery
Presentations consumer
```

No new workflow/state/database/token/receipt/watcher/controller.

## 5. Exact CLI contract

The only new public command is:

```bash
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
```

No additional public options for:

```text
lease
expected OID
ref
refspec
force
destination
remote
upstream
target worktree
transport
```

The helper derives the current repo/worktree from cwd and the exact branch/destination from `task_key`.

## 6. Raw-object validation order

Before any remote/config mutation:

```text
exact repo/worktree/derived reviewed branch
-> clean worktree
-> capture exact HEAD OID
-> fixed no-replacement raw object/type read
-> resolve actual graft path; active info/grafts => fail closed
-> read raw HEAD commit object
-> raw parent count = 1
-> raw only parent = captured CURRENT.base_commit
-> read raw base commit object
-> obtain raw base/head tree OIDs
-> raw base tree: REQUEST/CURRENT absent
-> no-renames raw tree diff = exact A/A REQUEST/CURRENT only
-> raw tree-entry lookup
-> REQUEST/CURRENT regular blob reads from raw head tree
-> task/base/worktree/state/action/revision/implementation identity PASS
-> optional no-replacement rev-list count=1 as secondary consistency evidence
-> full final pre-mutation recheck
```

Security-critical object/history commands must use helper-fixed `git --no-replace-objects ...` or an exactly equivalent caller-invariant mechanism.

Raw direct-parent object truth is authoritative; `rev-list` cannot override it.

Active non-comment/nonblank `info/grafts` fails `ACTIVE_GRAFTS_REQUIRE_ORDINARY_APPROVAL`; helper does not delete, convert, or repair grafts.

## 7. Atomic publication and recovery

Fixed publication:

```text
remote = origin
source = captured raw HEAD OID
destination = refs/heads/reviewed/<task_key>
lease = --force-with-lease=refs/heads/reviewed/<task_key>:
no leading +
```

Pre-read exact destination must be absent.

Push invocation must use the same fixed no-replacement semantics as validation and preserve the existing GitHub HTTPS/config/environment/hook fences.

Success requires:

```text
push exit success
AND
post-read exact destination SHA == captured raw HEAD
```

A failed push is not auto-adopted even if post-read happens to equal captured HEAD.

Only after successful post-read may local upstream be bound.

If upstream binding fails:

- do not delete/rewrite remote;
- roll back only invocation-owned local branch config when still unchanged;
- report `REMOTE_CREATED_UPSTREAM_BIND_FAILED`;
- do not report complete success.

Ambiguous push:

- fail closed;
- no blind retry;
- no auto-adopt;
- no remote delete;
- no force/history rewrite.

## 8. Execution phases

### Phase 0 — drift and authority preflight

Read latest main/AGENTS/design/Goal/package. Verify:

- exact Bridge canonical placement;
- current package version still matches the package assumption;
- no material overlapping production change has already solved or changed the design;
- Presentations F03 remains dependency-only;
- future FP-G6 AI_Skills task/branch/worktree are absent and unoccupied without creating them.

If material drift exists, stop for Planner/Critic.

### Phase 1 — implement approved Bridge delta

Implement only the frozen surface.

Do not install Machine Policy or create the consumer task yet.

### Phase 2 — development regression

Run focused deterministic tests repeatedly as needed while fixing implementation defects.

Then run the full local suite.

### Phase 3 — version/docs closure and final candidate freeze

If current version is still `0.9.2`, bump exactly once to `0.9.3`, update README/CHANGELOG/version parity, rerun required tests, commit the exact candidate on Bridge `main`, and publish only through the existing bounded main publisher.

Record the exact candidate commit.

No source/docs/version change after candidate freeze without invalidating affected final-candidate evidence.

Wait for real GitHub Tests CI on that candidate.

### Phase 4 — final-candidate deterministic FP-G1–FP-G5

Run the acceptance matrix against the exact frozen candidate. Full suite must pass on the same candidate.

### Phase 5 — bounded local candidate activation

Only after deterministic final-candidate gates pass:

- verify actual `ai-bridge` executable/import identity;
- if stale, perform one bounded editable refresh of this exact candidate;
- backup current managed Host files;
- install the exact candidate Machine Policy once for `/home/yuukias/.codex`;
- run `ai-bridge host validate`;
- verify `reviewed-handoff task publish-first` resolves to `allow`;
- verify raw `git push --force-with-lease`, raw `git push -u`, and arbitrary new-branch forms remain `prompt`;
- verify `ai-bridge reviewed-handoff task publish-first --help` is available from the installed executable.

If candidate activation/Host validation regresses, restore the exact managed-file backup and stop. Do not repeatedly reinstall.

This activation is candidate validation, not formal release.

### Phase 6 — FP-G6 fresh real consumer

Use exactly:

```text
consumer repo =
YuukiAS/AI_Skills_Collection

canonical checkout =
/home/yuukias/AI_Skills_Collection

task key =
workflow-core--first-remote-publication-gate

derived branch =
reviewed/workflow-core--first-remote-publication-gate

derived sibling worktree =
/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate

base =
execution-time post-sync origin/main OID
```

This task must be absent locally/remotely before the Gate. Do not create it before Phase 6.

Use the installed final Bridge candidate:

```text
approved Kickoff
-> git fetch --all --prune on canonical consumer
-> task bootstrap
-> one ordinary commit containing only A REQUEST + A CURRENT
-> task publish-first
-> exact remote SHA + local upstream verification
-> fetch/read remote REQUEST/CURRENT and confirm PLAN_REQUESTED / RUN_GPT_PLANNER
```

No AI_Skills production source, tests, PLAN.md, results artifact, version, generated payload, or Presentations file may change.

Do not delete the remote branch as cleanup; deletion is not authorized. The resulting branch is durable FP-G6 evidence.

The already manually first-pushed `product-ui-copy--cross-plugin-production-integration` is root-cause evidence only and cannot satisfy FP-G6.

### Phase 7 — pre-final handoff

Write durable evidence tying FP-G1–FP-G6, local/full tests, CI, installed identity, version/docs, and FP-G6 consumer identity to the same candidate, then stop for independent pre-final Critic.

No formal release/ref/tag advancement occurs in this Goal.

## 9. Version and release boundary

Current verified version:

```text
CURRENT_VERSION = 0.9.2
pyproject.toml = 0.9.2
ai_bridge_kit.__version__ = 0.9.2
```

Decision:

```text
VERSION_BUMP_DECISION = PATCH
TARGET_VERSION_IF_BUMP = 0.9.3
RATIONALE = backward-compatible repair completing the already-advertised Reviewed Handoff first-bootstrap/remote-handoff normal path; no new product family or incompatible contract
```

This matches the repository default: compatible reliability/behavior repair -> PATCH. The earlier `0.9.1` first-bootstrap normal-entry command was likewise shipped as a patch-level Reviewed Handoff repair.

If execution-time package version is no longer exactly `0.9.2`, do not silently reserve/overwrite `0.9.3`; stop for Planner on version/source drift.

README update is required before candidate freeze because the normal user command changes. CHANGELOG and both version owners are required before candidate freeze.

Formal release is separate:

- do not create tag;
- do not advance `release` ref;
- do not claim distribution complete;
- formal distribution remains owned by AI Skills Maintainer / bridge-kit-maintainer after required final review.

## 10. Presentations boundary

Keep:

```text
PRES-S1-ER-F03 = STILL_OPEN
READY_FOR_CODEX = NO
```

Do not modify Presentations.

Only after Bridge implementation, final-candidate FP-G1–FP-G6, installed/available command verification, and later formal closure as required may Presentations return for narrow F03 re-review.

## 11. Stop / recovery conditions

Return to Planner/Critic if:

- approved implementation surface is insufficient;
- generic publisher public semantics would need to change;
- raw-object/graft contract cannot be implemented without broader Git authority;
- target version/source has material drift;
- exact Bridge canonical placement differs;
- Machine Policy candidate cannot preserve dangerous-neighbor prompts;
- final candidate changes after gate freeze;
- FP-G6 task/branch/worktree already exists or conflicts;
- real consumer requires AI_Skills production changes;
- any gate suggests force/delete/remap/provider API/new state/database/watcher/controller.

Do not solve a stop condition with a weaker proxy.

## 12. Completion claim

This Goal may ultimately claim only:

> the exact Bridge candidate provides a bounded, raw-object-safe, atomic first remote publication entry for brand-new Reviewed Handoff control metadata, preserves existing publication/resume/watcher boundaries, and passes FP-G1–FP-G6 including one fresh AI_Skills real-consumer normal-entry gate.

It does not claim:

- formal release/distribution complete;
- Presentations F03 closed;
- all machines updated;
- generic Git push newly trusted;
- arbitrary remote-branch creation.
