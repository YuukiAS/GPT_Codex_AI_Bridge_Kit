# Critic Review — Reviewed Handoff 首次远端发布设计 v0.1

**Review stage:** `BRIDGE_FIRST_REMOTE_PUBLICATION_DESIGN`  
**Target repo:** `YuukiAS/GPT_Codex_AI_Bridge_Kit`  
**Target domain:** Reviewed Handoff / Bridge Kit core  
**Task key:** `reviewed-handoff--first-remote-publication`  
**Reviewed plan:** `docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md`  
**Reviewed plan commit:** `54bf116c38638753a0579b5f18c19fc6c0239fd6`  
**Bridge main inspected:** `0a6d55361f358cd38aee48e92af9ecf701145c64`  
**Verdict:** **REVISE**

## 1. 用户可读结论

方向是对的：根因确实在 Bridge，而不是 Presentations / Product UI Copy consumer；选择一个 Reviewed Handoff 专用的窄 `task publish-first` 动作，也比把网络发布塞进 `task bootstrap`、放宽 generic publisher、或继续让用户手工 `git push -u` 更合理。

当前不能 PASS 的原因只有两个，而且都在这个新 helper 的安全边界本身，不要求重做架构：

1. Plan 依赖 “`ls-remote` 先确认不存在 -> 普通 non-force push -> post-read” 来保证 first-create，但这不是原子的。官方 Git 文档明确提供了更窄的 compare-and-swap 语义：`--force-with-lease=<refname>:<expect>` 的空 `<expect>` 表示“该远端 ref 必须不存在”。当前 Plan 明确要求任何已存在的同名远端 branch 都 fail closed；仅 precheck + ordinary push 在并发创建恰好可 fast-forward 的情况下不能保证这条合同。
2. Plan 要把 `publish-first` 设为 Machine Policy allow，但目前没有冻结“首发 commit 只能包含 first-bootstrap REQUEST/CURRENT control metadata”的 diff fence。只检查 CURRENT 仍是 `PLAN_REQUESTED / RUN_GPT_PLANNER`、worktree clean、HEAD descended from base，并不能阻止一个误行为 Executor 先 commit 其他 source 再借 allow helper 一起发布。

除此之外，root cause、owner、selected architecture、危险邻居隔离、existing publisher/resume regression 以及 fresh real-consumer gate 的方向都成立。

## 2. Root cause

`ROOT_CAUSE_VERDICT = PASS`

Current production source confirms:

- `reviewed-handoff task bootstrap` derives `reviewed/<task_key>`, creates the deterministic sibling worktree and first REQUEST/CURRENT, and deliberately performs zero network operations.
- `host publish-current-branch` requires the current branch already have `branch.<branch>.remote=origin`, same-name merge ref, and an already-existing same-name remote branch.
- Therefore brand-new Reviewed first publication deterministically fails the current bounded publisher path before push.
- The trigger TODO records a real AI_Skills consumer where this happened.

This is a cross-repo Reviewed Handoff capability gap. It does not belong in Presentations or another consumer.

## 3. Selected architecture

`SELECTED_ARCHITECTURE_VERDICT = PASS_DIRECTION / REVISE_NARROW_SAFETY_DETAILS`

Option B — dedicated:

`ai-bridge reviewed-handoff task publish-first --task-key <task> --expected-repo <owner/repo>`

is the best of the considered options:

- keeps bootstrap's accepted zero-network boundary;
- keeps generic `host publish-current-branch` as existing-branch publisher;
- avoids consumer-local wrappers;
- avoids new workflow/state/auth database;
- caller cannot choose branch, refspec, remote, transport, force, tag, delete, mirror or upstream.

No simpler existing mature entry provides the same bounded “new remote branch for this exact Reviewed task” capability.

## 4. Blocking findings

### BR-FRP-F01 — First-creation race is not fail-closed under the Plan's own contract

**Requirement**

The Plan says `publish-first` is only for a branch that does not already exist remotely, and any pre-push observation of an existing same-name remote branch must fail closed. It also asks the Critic to judge the residual race between absence check and push.

**Direct evidence**

The selected sequence is:

`ls-remote says absent -> gap -> ordinary non-force exact refspec push -> post-read`.

Official `git-push` documentation states:

- a refspec fixes source/destination;
- a leading `+` is force;
- ordinary push refuses non-fast-forward branch updates;
- `--force-with-lease=<refname>:<expect>` checks the current remote ref against an exact expected value;
- when `<expect>` is the empty string, the named remote ref must not already exist.

With the current Plan, another actor can create the same branch after `ls-remote`. If that concurrent tip is an ancestor of the captured local HEAD, the ordinary non-force push can legally fast-forward it and the post-read can still equal captured HEAD. The helper would report success even though the branch was no longer absent at mutation time.

**Causal risk**

That violates the helper's declared “first publication only / existing remote always fail closed” identity. It can mask a concurrent/double bootstrap and makes the Machine Policy allow weaker than the documented safety contract.

**Minimum closure condition**

Revise the Plan to use an atomic create-if-absent guard for the one derived destination ref.

The smallest Git-native mechanism is an **internal fixed** lease assertion equivalent to:

`--force-with-lease=refs/heads/reviewed/<task_key>:`

combined with the exact derived non-delete refspec and all existing pre/post checks.

Important boundary:
- caller still cannot supply any lease/ref/refspec/force option;
- raw `git push --force-with-lease` remains approval-gated;
- the helper must reject any non-empty expected OID / alternate ref / caller-selected lease;
- this is not generic force authority: the empty expectation means “destination must not exist”, so an already-existing ref cannot be overwritten.

An equivalent provider-side compare-and-create primitive could also close the race, but provider API is unnecessary here.

The existing pre-`ls-remote` and post-read SHA checks should remain as diagnostics and identity evidence; they do not replace the atomic absence guard.

---

### BR-FRP-F02 — Missing first-publication diff/path fence

**Requirement**

The new command is proposed as a permanent Machine Policy allow action specifically for the first control-plane publication:

`bootstrap -> commit REQUEST/CURRENT -> publish-first -> external Planner`.

Before `PLAN_FROZEN`, the first publication must not carry product/source implementation.

**Direct evidence**

Plan v0.1 requires:
- committed REQUEST/CURRENT;
- correct task/base/worktree identity;
- `PLAN_REQUESTED / RUN_GPT_PLANNER`;
- clean worktree;
- HEAD descended from frozen base.

It does **not** require the committed diff from frozen `base_commit` to captured HEAD to be restricted to the exact first-bootstrap control metadata paths.

A clean worktree only means “no uncommitted changes”; it does not prove the commit contains only REQUEST/CURRENT.

**Causal risk**

An Executor or other process could commit unrelated source/product changes while CURRENT still says `PLAN_REQUESTED`, then invoke the permanently allowed helper. The helper would publish those changes without another approval, defeating the intended control-plane-only first handoff and weakening the authorization boundary.

**Minimum closure condition**

Before any remote/config mutation, freeze a first-publication path fence:

- compute the committed path diff from frozen `CURRENT.base_commit` to captured HEAD;
- require it to be non-empty and restricted to the exact task's first-bootstrap control artifacts:
  - `automation/reviewed_handoff/tasks/<task_key>/REQUEST.md`
  - `automation/reviewed_handoff/tasks/<task_key>/CURRENT.json`
- require both exact blobs to be present in captured HEAD and validate against the task/base/worktree/current-state contract;
- reject any other committed path.

If current Reviewed bootstrap legitimately requires another tracked first-handoff file, the revised Plan must name that exact path explicitly rather than allow a generic task/result directory.

This path fence applies only to `publish-first`; later normal Reviewed publication continues through the existing mechanisms.

## 5. Authorization boundary

`AUTHORIZATION_BOUNDARY_VERDICT = REVISE_PENDING_F02; OTHERWISE_DIRECTIONALLY_SOUND`

A narrow Machine Policy allow is reasonable **if** the helper itself mechanically proves:

- exact current repo;
- exact task-derived branch/worktree;
- exact first-handoff state;
- exact first-control-metadata committed diff;
- exact same-name origin destination;
- canonical HTTPS transport/config/hook/environment;
- atomic remote-ref absence;
- post-read exact SHA.

With those fences, this is the already-authorized exact Reviewed branch effect, not arbitrary remote-branch creation.

No authorization database, token, receipt store, new CURRENT field, watcher, controller or new workflow is justified.

Raw `git push -u`, arbitrary new branches, alternate upstream, force, tag/delete/mirror and caller-selected transport remain gated.

## 6. Remote race

`REMOTE_RACE_VERDICT = REVISE_ATOMIC_ABSENCE_GUARD_REQUIRED`

The current residual race is small but not compatible with the Plan's own “remote ref must not exist” invariant. Post-push readback proves final identity, not that the ref was absent at mutation.

Use Git's fixed empty-expect lease internally or an equivalently narrow atomic primitive. Do not expand to generic force/provider API.

## 7. Capability gates

`FP_GATE_VERDICT = REVISE_G1_G2_NEED_F01_F02; G3_G6_DIRECTIONALLY_PASS`

- **FP-G1** remains correct but must prove the atomic create-if-absent path.
- **FP-G2** must add the committed path/diff fence and concurrent-existing-ref case.
- **FP-G3** is correct: raw first push, arbitrary branch/refspec, force variants, tag/delete/mirror/remap/alternate upstream remain gated. If the implementation internally uses the fixed empty-expect lease, tests must prove callers cannot generalize it and raw force-with-lease remains gated.
- **FP-G4** is correct: generic existing-branch publisher must not change.
- **FP-G5** is correct: local + remote-only resume remain unchanged.
- **FP-G6** is necessary and correctly requires a genuinely new real consumer task after deterministic tests. Product UI Copy is root-cause evidence only.

All release-critical gates should bind to one final Bridge candidate.

## 8. Overengineering

`OVERENGINEERING_VERDICT = PASS`

The selected dedicated action is smaller than:
- modifying bootstrap into a network/commit/publication transaction;
- teaching generic Host publisher Reviewed semantics;
- adding an authorization database/state machine;
- using a watcher/controller;
- adding per-consumer workarounds.

The two requested revisions are fences inside the same chosen helper, not new architecture.

## 9. Presentations dependency

`PRESENTATIONS_DEPENDENCY_VERDICT = WAITING_ON_BRIDGE_IMPLEMENTATION`

The dependent Presentations Stage 1 package remains frozen at:

`results/presentations--stage1-front-door-two-template-foundation/EXECUTION_PACKAGE_V1_1.md @ 049847f4638bb339229c748d3b8f97bd41fae72d`

`PRES-S1-ER-F03` remains open.

Do not amend Presentations merely because this Bridge design is being revised. After Bridge design PASS, the sequence is still:

Bridge execution package -> execution-ready Critic PASS -> Bridge implementation/tests -> fresh real consumer -> installed/available command verification -> narrow Presentations F03 re-review.

## 10. External targeted verification

Official Git documentation supports the underlying design:
- exact refspecs bind source/destination;
- ordinary pushes reject non-fast-forward branch updates;
- upstream tracking maps to branch remote/merge fields;
- most importantly for this review, `--force-with-lease=<refname>:<expect>` with empty `<expect>` requires that remote ref not already exist.

This gives a native atomic absence assertion and avoids relying on a TOCTOU-only `ls-remote` check.

## 11. Verdict

```text
RESULT = REVISE
REVIEW_STAGE = BRIDGE_FIRST_REMOTE_PUBLICATION_DESIGN

REVIEWED_PLAN =
docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md

REVIEWED_PLAN_COMMIT =
54bf116c38638753a0579b5f18c19fc6c0239fd6

TASK_KEY =
reviewed-handoff--first-remote-publication

ROOT_CAUSE_VERDICT = PASS
SELECTED_ARCHITECTURE_VERDICT = PASS_DIRECTION_REVISE_NARROW_SAFETY_DETAILS
AUTHORIZATION_BOUNDARY_VERDICT = REVISE_PENDING_FIRST_PUBLICATION_DIFF_FENCE
REMOTE_RACE_VERDICT = REVISE_ATOMIC_ABSENCE_GUARD_REQUIRED
FP_GATE_VERDICT = REVISE_G1_G2
OVERENGINEERING_VERDICT = PASS
PRESENTATIONS_DEPENDENCY_VERDICT = WAITING_ON_BRIDGE_IMPLEMENTATION

READY_FOR_BRIDGE_EXECUTION_PACKAGE = NO
```

Stable findings:
- `BR-FRP-F01`
- `BR-FRP-F02`

No implementation, branch/worktree creation, Machine Policy mutation, install or release is authorized.
