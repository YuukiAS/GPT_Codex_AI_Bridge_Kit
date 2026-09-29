# Reviewed Handoff First Remote Publication — Execution Package v0.1

Package version: **0.1**  
Date: **2026-09-29**  
Task key: **reviewed-handoff--first-remote-publication**  
Review stage: **DESIGN_PASS -> EXECUTION_READY CRITIC REVIEW**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Target branch: **main**  
Status: **FROZEN PACKAGE / NOT EXECUTION AUTHORIZATION**

This package translates the already-PASS v0.4 design into the smallest bounded execution contract. It does not reopen architecture and does not authorize implementation until an independent execution-ready Critic PASSes this exact package and the user sends the approved Kickoff.

## 1. Design authority

Approved design:

```text
docs/design/reviewed_handoff_first_remote_publication_plan_v0.4_2026-09-29.md
@ cedd6f1dc2c13af7e237fc0ab2c07ba73700472a
```

Design PASS transfer:

```text
docs/design/reviewed_handoff_first_remote_publication_design_pass_transfer_v0.1_2026-09-29.md
first commit = f773f79b94e03682ccf423131ac5a0ac624a939f
```

Transferred verdict:

```text
RESULT=PASS
BR-FRP-F01=CLOSED
BR-FRP-F02=CLOSED
NEW_BLOCKERS=NONE
DESIGN_PASS_ONLY=YES
IMPLEMENTATION_AUTHORIZED=NO
RELEASE_AUTHORIZED=NO
```

The original independent Critic PASS artifact was not supplied with a repository locator; the transfer record preserves provenance without fabricating an original review path.

## 2. Bound execution objects

Canonical Goal:

```text
docs/design/reviewed_handoff_first_remote_publication_goal_v0.1_2026-09-29.md
first commit = e59ed8c5c79d49e4880b45da524490035fe04c28
```

Acceptance Matrix:

```text
docs/design/reviewed_handoff_first_remote_publication_acceptance_matrix_v0.1_2026-09-29.md
first commit = 3feb24691241c6c546645475a89c7c35440fede2
```

Kickoff Draft:

```text
docs/design/reviewed_handoff_first_remote_publication_kickoff_v0.1_2026-09-29.md
first commit = 028ca32100d7c3f06eb2582db0c109b545777db0
```

These four execution objects plus the approved v0.4 design are the complete package for execution-ready review.

## 3. Future implementation placement

No implementation branch/worktree is created during package preparation.

After execution-ready PASS and user Kickoff, implementation placement is frozen to:

```text
repo = YuukiAS/GPT_Codex_AI_Bridge_Kit
branch = main
worktree = /home/yuukias/GPT_Codex_AI_Bridge_Kit
```

No sibling Bridge implementation worktree and no new Bridge implementation branch.

Execution must preflight that locator. Material mismatch returns Planner.

## 4. Exact production scope

Primary allowed runtime changes:

```text
ai_bridge_kit/reviewed_handoff.py
templates/host/rules/ai-bridge-global.rules
templates/host/GLOBAL_AGENTS_SNIPPET.md
templates/reviewed_handoff/README.md
```

Conditional internal-only sharing surface:

```text
ai_bridge_kit/host.py
```

`host.py` may change only to factor/reuse the already-existing GitHub HTTPS transport/config/environment/hook fences. The public `publish_current_branch()` contract and behavior must remain unchanged.

Required user-facing/version closure surfaces:

```text
AGENTS.md
README.md
CHANGELOG.md
pyproject.toml
ai_bridge_kit/__init__.py
```

Focused test surface:

```text
tests/test_reviewed_handoff.py
tests/test_host_policy.py
tests/test_reviewed_runner.py
tests/test_version_parity.py
```

Hard should-not-change unless execution returns Planner:

```text
ai_bridge_kit/bridge_cli.py
ai_bridge_kit/cli.py
ai_bridge_kit/reviewed_runner.py
Reviewed schema/state/transition model
bootstrap public semantics
materialize-worktree public semantics
generic host publish-current-branch public semantics
release/ref machinery
Presentations consumer
```

`bridge_cli.py` was inspected: it already routes all non-watcher `reviewed-handoff` commands to `reviewed_handoff.main`, so no top-level routing change is needed.

`QUICKSTART.md` was inspected: it does not currently document this Reviewed first-bootstrap publication sequence, so no change is required merely to add another command list.

## 5. Exact CLI and Machine Policy delta

New public command only:

```bash
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
```

No caller-controlled:

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

Machine Policy delta:

- add allow only for the bounded `ai-bridge reviewed-handoff task publish-first` command;
- preserve raw `git push -u`, `--set-upstream`, raw force-with-lease, force, delete, arbitrary branch/refspec/remap/custom transport as prompt/gated;
- managed Host AGENTS must state that an already-approved exact Reviewed task uses this helper for its first control-metadata publication without a second ordinary branch authorization.

No generic Git allow is added.

## 6. Frozen security implementation contract

Before remote/config mutation:

```text
exact reviewed worktree + clean tree
-> capture exact HEAD OID
-> fixed --no-replace-objects raw object authority
-> resolve actual info/grafts path
-> active graft => fail closed
-> raw HEAD commit: exactly one parent
-> raw parent == captured CURRENT.base_commit
-> raw base/head tree OIDs
-> REQUEST/CURRENT absent in raw base tree
-> raw -r --name-status --no-renames -z diff
-> exact A REQUEST + A CURRENT only
-> raw tree entries are regular blobs
-> raw blob REQUEST/CURRENT identity/state PASS
-> secondary no-replacement rev-list count=1
-> complete final pre-mutation recheck
```

Raw commit object truth, not revision-display truth, is authoritative.

Replacement refs may exist, but security-critical reads ignore replacement objects.

Any active nonblank/non-comment `info/grafts` record exits the trusted path; helper does not repair/delete/convert it.

## 7. Frozen atomic publication/recovery contract

Derived effect:

```text
remote = origin
source = captured raw HEAD OID
destination = refs/heads/reviewed/<task_key>
lease = --force-with-lease=refs/heads/reviewed/<task_key>:
no leading +
```

Required:

- pre-read exact destination absent;
- existing Host GitHub HTTPS/config/environment/hook fences;
- final pre-push safety recheck;
- push success;
- post-read exact remote SHA = captured raw HEAD.

Existing destination can never be updated.

Upstream is written only after confirmed remote creation:

```text
branch.<branch>.remote = origin
branch.<branch>.merge = refs/heads/reviewed/<task_key>
```

Upstream partial failure:

- no remote deletion/rewrite;
- rollback only invocation-owned unchanged local config;
- explicit partial result;
- no success claim.

Ambiguous publication:

- fail closed;
- no blind retry;
- no auto-adopt;
- no remote delete;
- no force/history rewrite.

## 8. Executable acceptance

Canonical focused command:

```bash
python -m unittest -v \
  tests.test_reviewed_handoff \
  tests.test_host_policy \
  tests.test_reviewed_runner \
  tests.test_repo_cli_compat \
  tests.test_version_parity
```

Canonical full command:

```bash
python -m unittest discover -v
```

GitHub Tests workflow must PASS on the exact final candidate for both Python 3.9 and current Python 3.x.

Detailed FP-G1–FP-G6 cases are frozen in:

`docs/design/reviewed_handoff_first_remote_publication_acceptance_matrix_v0.1_2026-09-29.md`

Execution-ready Critic must review that matrix directly rather than accepting “tests will be added” as sufficient.

## 9. FP-G1–FP-G6 summary

```text
FP-G1 = atomic create-if-absent + concurrent-create race
FP-G2 = raw-object single-commit history/path/blob fence, including replace/graft attacks
FP-G3 = dangerous-neighbor authorization isolation
FP-G4 = generic existing-branch publisher regression
FP-G5 = bootstrap/resume/materialize/watcher authority regression
FP-G6 = fresh real AI_Skills consumer normal entry
```

All release-critical evidence binds to one final Bridge candidate.

## 10. Frozen FP-G6 real consumer

Executed only after final candidate freeze, deterministic gates, CI, and installed-command verification:

```text
repo = YuukiAS/AI_Skills_Collection
checkout = /home/yuukias/AI_Skills_Collection
task = workflow-core--first-remote-publication-gate
branch = reviewed/workflow-core--first-remote-publication-gate
worktree = /home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
base = execution-time post-sync origin/main OID
```

Allowed consumer mutation is only:

```text
task bootstrap
-> one ordinary commit with A REQUEST + A CURRENT only
-> task publish-first
-> remote SHA/upstream/readability verification
```

No AI_Skills production source, tests, PLAN.md, results artifact, plugin/version/generated payload, or Presentations change.

Do not delete the remote branch after Gate completion.

Historical Product UI Copy cannot satisfy FP-G6.

## 11. Candidate activation boundary

Before FP-G6, exact final candidate must be actually available:

- resolve actual `ai-bridge` executable;
- resolve `ai_bridge_kit` import source;
- if stale, one bounded editable refresh only;
- backup managed Host files;
- one candidate Machine Policy install to `/home/yuukias/.codex`;
- `ai-bridge host validate` PASS;
- installed `task publish-first --help` available;
- installed execpolicy proves new bounded allow and dangerous neighbors remain prompt.

Candidate activation is validation, not formal release.

On regression, restore exact managed-file backup and stop.

## 12. Version decision

Verified current version at package preparation:

```text
CURRENT_VERSION = 0.9.2
pyproject.toml = 0.9.2
ai_bridge_kit.__version__ = 0.9.2
```

Frozen decision:

```text
VERSION_BUMP_DECISION = PATCH
TARGET_VERSION_IF_BUMP = 0.9.3
RATIONALE = backward-compatible repair completing the existing Reviewed Handoff normal path
```

If execution-time version is no longer exactly 0.9.2, return Planner instead of silently taking another release slot.

Before final candidate freeze:

- bump both version owners to 0.9.3;
- version parity test PASS;
- create/update CHANGELOG 0.9.3 entry;
- update README current normal-entry behavior.

The current Unreleased main changes become part of the next package candidate; do not rewrite unrelated historical changelog entries.

Formal distribution is not authorized:

```text
tag = NO
release ref advancement = NO
formal distribution claim = NO
```

Formal release remains a later AI Skills Maintainer / bridge-kit-maintainer responsibility after required review.

## 13. Presentations dependency

Keep unchanged:

```text
PRES-S1-ER-F03 = STILL_OPEN
READY_FOR_CODEX = NO
```

No Presentations mutation is part of this package.

Only after Bridge implementation + same-candidate gates + FP-G6 + installed/available command verification + required closure does Presentations return for narrow F03 re-review.

## 14. Execution authorization boundary

This package itself authorizes nothing.

Only the user later sending the exact Critic-approved Kickoff authorizes:

- the bounded Bridge main implementation;
- ordinary task commits and bounded existing-main publication;
- deterministic/full tests;
- 0.9.3 candidate closure if version preflight still matches;
- one bounded local candidate refresh/Host install with backup;
- exact FP-G6 AI_Skills task/branch/worktree and first publication.

No destructive Git, release/tag/ref advancement, Presentations change, new provider/paid API, or architecture expansion.

## 15. Execution-ready Critic decision requested

Critic should PASS only if the package is sufficient to start implementation without Executor redesign, especially:

- production file scope is minimal and complete;
- CLI/Machine Policy delta is exact;
- raw-object/replace/graft contract is executable;
- atomic lease/upstream/ambiguous recovery is unambiguous;
- focused/full/CI tests directly cover FP-G1–FP-G5;
- FP-G6 is truly fresh, bounded, and scheduled after candidate freeze;
- version 0.9.2 -> 0.9.3 decision is consistent with current policy/source;
- release boundary is separate;
- Presentations remains untouched.

Execution-ready PASS must approve the exact Kickoff Draft; otherwise return REVISE to Planner.

```text
READY_FOR_CODEX = NO
NEXT_HANDOFF = CRITIC
```
