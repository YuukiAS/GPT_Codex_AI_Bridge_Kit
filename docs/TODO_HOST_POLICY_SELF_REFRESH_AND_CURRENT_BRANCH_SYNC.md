# TODO — Host Policy Self-Refresh and Current-Branch Sync

Status: READY FOR PLANNER INTAKE / NOT IMPLEMENTATION AUTHORIZATION  
Priority: current-branch sync = HIGH; host-policy self-refresh = MEDIUM  
Date: 2026-10-04

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
