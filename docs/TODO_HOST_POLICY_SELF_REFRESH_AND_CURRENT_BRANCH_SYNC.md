# TODO — Host Policy Self-Refresh and Current-Branch Sync

Status: READY FOR PLANNER INTAKE / TARGET NEXT PATCH RELEASE 0.10.1 / NOT IMPLEMENTATION AUTHORIZATION  
Priority: current-branch sync = HIGH; host-policy self-refresh = MEDIUM  
Date: 2026-10-06

## Real incident

A real STAT5060 Tutorial 1 Rich v2 task reproduced a low-friction bootstrap problem even though Bridge Kit runtime itself was already current at 0.10.0.

Observed sequence:

1. Bridge runtime and formal release were current.
2. The active Codex session still had drifted Host Policy in its current `$CODEX_HOME`.
3. The session could not repair that policy from inside its own sandbox because `$CODEX_HOME` was read-only to the running process and an escalated retry was rejected.
4. `workflow-core 0.5` was also absent from that Codex identity, so the task lost the workflow guidance that should have classified the refusal before repeated retries.
5. The client repository was on an already-selected, already-existing non-main branch. Bridge had low-friction fetch, main-only ff pull, ordinary add/commit, and bounded existing-branch publication, but no bounded helper for syncing that current non-main branch.
6. Rich v2 build/render/QA had already passed, but machine-maintenance state was repeatedly surfaced as if the client artifact itself were blocked.

After a one-time host-policy/plugin refresh from a normal terminal and a fresh Codex session, the existing Rich v2 work was preserved, committed, merged with the remote same branch, and published successfully.


### Independent reproduction — STAT5060 Final Project V5, 2026-10-06

A second real task reproduced the same non-main current-branch sync gap without depending on the earlier Tutorial incident.

Observed state:

- repository: `YuukiAS/STAT5060-TA`;
- already-selected branch: `work/stat5060--final-project-redesign-v1`;
- local task worktree HEAD: `145c7bc265265e4bc266824af8c770d9e3e55014`;
- remote same-name branch HEAD after fetch: `0c34cad7fde752cf7fd66b1ce094e0a7ce30a1df`;
- the local history was strictly behind the fetched remote history and only a fast-forward was required;
- the intended task already authorized ordinary work on the same selected branch and later commit/push;
- Codex could fetch and read the V5 approval artifacts, but could not advance the current non-main branch without asking the user for an explicit one-off authorization;
- the task correctly refused to work around the boundary by manually copying remote file contents into the stale worktree.

The user had to provide an exact sentence authorizing the fast-forward before work could continue.

This reproduces the same capability gap under a different STAT5060 task and confirms that the problem is not specific to Tutorial Rich v2, stale artifact state, or a single Goal wording. The missing primitive is the bounded inbound counterpart to `publish-current-branch`: safely synchronize the already-selected, already-tracked, same-name current branch from `origin/<same-name-branch>`.

This incident also clarifies the ownership boundary:

- a Goal may describe the desired task and branch, but should not need to carry a bespoke raw-Git authorization sentence solely because Bridge lacks a bounded helper;
- the long-term fix belongs in Bridge Kit, not in every project Goal prompt;
- a project Goal may still name the expected repo/branch so the bounded helper can prove scope.

## Candidate A — bounded current-branch fast-forward sync

This is the higher-value addition.

Proposed shape:

```text
ai-bridge host sync-current-branch \
  --expected-repo <owner/repo> \
  --expected-branch <already-selected-branch>
```

It should permit only an already-selected, already-tracked, existing same-name branch to fast-forward from `origin/<same-name-branch>`.

Required preconditions:

- current repository identity equals `--expected-repo`;
- current branch equals `--expected-branch`;
- upstream remote is exactly `origin`;
- upstream merge ref is exactly `refs/heads/<expected-branch>`;
- origin fetch/push identity is canonical GitHub HTTPS;
- remote same-name branch already exists;
- worktree/index are clean before mutation;
- local HEAD is ancestor of remote HEAD;
- operation is strictly fast-forward;
- no rebase, autostash, reset, checkout/switch, branch creation, remote mutation, force, or extra refspec;
- post-update local HEAD == fetched remote HEAD;
- dirty-tree and unrelated-work ownership remain fail-closed.

Why this is worth adding:

- `main` already has a low-friction ff-only path.
- Existing same-name branch publication already has `publish-current-branch`.
- Long-lived work branches are common in real repositories.
- Without the matching inbound primitive, Codex falls back to raw merge/pull command shapes that may be sandbox/approval-sensitive even though the intended effect is bounded and routine.

This should be a Bridge-owned dynamic check, not a broad execpolicy allow for arbitrary `git merge` or `git pull`.


## Recommended 0.10.1 patch scope

Recommended next small release: **0.10.1**.

Keep the patch intentionally narrow:

1. implement Candidate A only: `ai-bridge host sync-current-branch`;
2. add the corresponding Host Policy allow entry for that bounded helper;
3. add positive/negative tests covering the exact non-main same-name fast-forward contract;
4. update README / Quickstart / Host Policy documentation so agents use the helper instead of raw non-main `git pull`;
5. preserve all existing 0.10.0 behavior for `main`, publication, Reviewed Mode and dangerous Git boundaries.

Candidate B (`host refresh-policy`) should remain deferred unless Planner finds a coupling that makes it necessary for the same patch. It is useful but is not required to close the repeatedly reproduced non-main sync defect.

### Required 0.10.1 behavioral contract

The helper should:

- perform its own bounded fetch/read needed to establish `origin/<expected-branch>` state;
- require the current branch to already be the expected branch;
- require an existing same-name upstream on `origin`;
- require a clean index and worktree;
- prove `local HEAD` is an ancestor of the fetched remote HEAD;
- update only the current branch ref/worktree by strict fast-forward;
- never create, switch, rename or delete a branch;
- never rebase, autostash, reset, restore, force, mutate remotes or accept an extra refspec;
- verify post-state equality between local HEAD and fetched remote HEAD;
- fail closed with a specific reason when any precondition is not satisfied.

The helper should be the normal low-friction route for this effect. Raw non-main branch pull/merge should remain approval-sensitive.

### 0.10.1 acceptance evidence

In addition to the existing unit/integration suite, add deterministic fixtures for:

Positive:

- clean current non-main branch behind its exact same-name origin branch;
- zero-op when local and remote are already equal;
- exact post-update OID equality;
- unchanged existing `main` behavior.

Negative:

- dirty worktree or dirty index;
- current branch differs from `--expected-branch`;
- repository differs from `--expected-repo`;
- missing upstream;
- upstream remote is not `origin`;
- upstream merge ref differs from the expected same-name branch;
- remote branch absent;
- local ahead of remote;
- divergent histories;
- active hooks or unsafe Git config/transport conditions covered by the current publisher trust model;
- SSH/scp/custom transport where the bounded GitHub HTTPS contract is required;
- any attempt that would require checkout/switch, branch creation, rebase, reset, autostash, force or remote mutation.

Patch release closure should include:

- version bump to `0.10.1`;
- CHANGELOG entry identifying the two independent STAT5060 reproductions;
- exact-sha CI PASS;
- Host Policy validation including the new helper allow rule;
- formal release/distribution closure through the existing Bridge maintainer path.

## Candidate B — bounded Host Policy self-refresh

Lower priority, but useful for avoiding the stale-policy bootstrap loop.

Possible shape:

```text
ai-bridge host refresh-policy
```

Scope:

- active/current-user `CODEX_HOME` only;
- Bridge-managed `config.toml`, managed AGENTS block, managed rules file, and bounded backup directory only;
- bytes must come from the currently installed formal Bridge release;
- validate runtime/import/source/release identity before mutation;
- reject symlink/path-redirection surprises and unrelated user-owned content;
- validate after mutation;
- return `RELOAD_REQUIRED` when a fresh Codex process is needed.

It must not become:

- a generic `$CODEX_HOME` writer;
- a Marketplace/plugin installer;
- a way to bypass arbitrary Auto-review decisions;
- a generic config mutation primitive.

Why only MEDIUM priority:

- Host Policy updates are occasional, not part of every repository task.
- A fresh session after machine update is already an honest process boundary.
- The current manual `host install` route works outside a stale/read-only running sandbox.
- It is useful mainly to remove the chicken-and-egg case where an outdated active policy prevents its own bounded refresh.

## Workflow semantic follow-up

Machine-policy or plugin maintenance failure must not retroactively invalidate an already-successful client artifact.

If build/render/QA has passed and only sync/commit/publication remains:

- preserve the completed artifact evidence;
- report only the blocked integration/publication effect;
- do not rewrite the entire Goal as artifact failure;
- do not enter repeated blocked-audit loops for the same refusal;
- after a required fresh session, resume the same Goal from the preserved worktree/evidence.

This semantic is primarily owned by workflow-core, while Bridge owns the bounded Git/Host operations.

## Acceptance gates

### Current-branch sync

Positive:
- clean existing non-main branch behind its exact same-name origin branch fast-forwards without interactive approval;
- local/remote OID equality verified;
- existing main behavior remains unchanged.

Negative:
- dirty tree;
- wrong repo/branch;
- no upstream or wrong upstream;
- absent remote branch;
- divergent histories;
- non-GitHub/SSH/custom transport;
- hooks/custom transport/config that exceed current publisher policy;
- branch creation/switching/rebase/reset/remote mutation attempts.

All negatives fail before mutation.

### Host self-refresh

Positive:
- stale managed Host Policy from an older Bridge-managed install refreshes to the exact installed formal-release bytes with backup;
- `host validate` passes afterward;
- fresh-session requirement is reported honestly.

Negative:
- symlink/path redirection;
- unrelated user-owned file mutation;
- non-current `CODEX_HOME`;
- arbitrary plugin install/config mutation;
- source/release identity mismatch.

## Non-goals

- no raw Git allow expansion;
- no automatic rebase/autostash;
- no new branch strategy;
- no raw push fallback;
- no generic privileged shell;
- no workflow-core/plugin installation inside Bridge;
- no attempt to eliminate legitimate fresh-session boundaries.
