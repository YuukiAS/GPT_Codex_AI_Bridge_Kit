# Reviewed Handoff First Remote Publication Plan v0.1

Plan version: **0.1**  
Date: **2026-09-29**  
Status: **READY FOR INDEPENDENT CRITIC REVIEW / DESIGN ONLY**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Source ref: **main @ 23e921e37b1178ee44514c0b03dd2d5140d64fb0**  
Design topic: **reviewed-handoff--first-remote-publication**  
Trigger evidence: **docs/TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md**

No implementation branch/worktree, production code, release version, watcher, workflow, authorization store, or consumer workaround is authorized by this Plan.

## 1. Root cause

The failure is in Bridge, not the consumer.

Current `reviewed-handoff task bootstrap` correctly derives and creates only the local
`reviewed/<task_key>` branch, deterministic sibling worktree, and first
`REQUEST.md` / `CURRENT.json`. It intentionally performs no network publication.

Current `host publish-current-branch` is an **existing-branch updater**. Its preflight
requires both:

- `branch.<branch>.remote = origin` and matching merge ref; and
- an already-existing same-name remote branch.

A brand-new Reviewed branch has neither. Therefore the observed
`UPSTREAM_REMOTE_MISMATCH` is expected from the current implementation; even if
upstream were preconfigured, the next guard would reject the missing remote branch.

The current generic publisher therefore cannot close first publication without changing
its declared safety class.

## 2. Alternatives

| Option | Benefit | Main problem | Decision |
|---|---|---|---|
| 1. Add publication to `task bootstrap` | one command, Reviewed-owned | breaks the accepted zero-network/local-topology bootstrap boundary; would also need to own the first commit and remote partial-failure semantics, or else publish only the base commit | **Reject** |
| 2. Add one Reviewed-only first-publication action | keeps bootstrap and generic publisher scopes intact; branch/task identity comes from Reviewed artifacts | adds one narrow publication action and must be strongly fenced | **Select** |
| 3. Extend generic `publish-current-branch` | smallest apparent CLI surface | either turns the generic host publisher into a new-branch creator or forces Host to understand Reviewed task semantics; broadens regression/ownership scope | **Reject** |

A watcher-based first publication is also rejected: first publication is needed before
normal remote Reviewed handoff, and coupling this bootstrap boundary to watcher lifecycle
would add unnecessary runtime semantics.

## 3. Selected normal entry

Add one phase-specific action under the existing Reviewed Handoff owner:

```text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
```

No caller argument may select branch, remote, destination ref, force mode, tag, delete,
push option, upstream name, or transport.

The normal lifecycle becomes:

```text
approved exact Reviewed Kickoff
-> existing git fetch --all --prune
-> existing task bootstrap
-> ordinary task-owned commit containing the first REQUEST/CURRENT snapshot
-> task publish-first
-> re-read exact remote ref and require remote SHA == captured local HEAD
-> normal existing-branch Reviewed lifecycle
```

This is an action inside the existing Reviewed Handoff workflow, not a new workflow or
authorization system.

## 4. Mechanical safety contract

`publish-first` may proceed only if all of the following are proven immediately before
mutation:

1. cwd is the exact Reviewed sibling worktree and repository identity equals
   `--expected-repo`;
2. semantic task key is valid; branch is derived only as `reviewed/<task_key>`;
3. `REQUEST.md` and `CURRENT.json` both exist in the current committed tree, agree on
   task/base/worktree identity, and the frozen worktree locator equals cwd;
4. current branch is exactly the derived Reviewed branch;
5. task is still in initial handoff state `PLAN_REQUESTED / RUN_GPT_PLANNER`; this action
   cannot recreate a deleted remote branch after the workflow has advanced;
6. worktree is clean and HEAD descends from the frozen base commit;
7. canonical origin profile and effective GitHub HTTPS fetch/push identity pass the same
   transport/config/environment/hook fences used by the existing bounded publisher;
8. no same-name remote branch exists on a fresh exact `ls-remote --heads` check;
9. existing branch upstream keys are absent; the action may establish only the deterministic
   pair `remote=origin` and `merge=refs/heads/reviewed/<task_key>`;
10. the pushed refspec is exactly
    `<captured-HEAD>:refs/heads/reviewed/<task_key>`, without `+`, force, tags, delete,
    mirror, extra refspec, push options, signed-push expansion, submodule recursion, or
    caller-selected transport;
11. repo/branch/HEAD/remote/config are rechecked immediately before push;
12. after push, Bridge re-reads the exact remote ref and succeeds only if its SHA equals
    the captured local HEAD.

Upstream configuration is part of this one bounded effect because it is required for later
ordinary existing-branch publication. If publication fails before remote creation, only
upstream keys created by this invocation may be rolled back when still unchanged. Bridge
must never delete or rewrite a remote ref as rollback. If network outcome is ambiguous,
report partial/ambiguous publication and stop; do not retry blindly.

A remote branch that exists at either pre-push check is a hard fail, whether its SHA is
equal, ancestor, descendant, or divergent. The action is first-publication only.

A concurrent remote creation after the final absence check is a residual Git race.
v0.1 deliberately does **not** use `--force-with-lease` or provider API to eliminate it.
The explicit non-force refspec cannot overwrite divergent history, and the mandatory
post-read exposes a mismatched outcome. Critic should decide whether this residual race is
acceptable for the bounded normal path; if not, this Plan must be revised rather than
silently adding force/API authority.

## 5. Authorization and ownership

The new command should be a narrowly allowlisted Bridge operation, analogous to the
already-hardened Reviewed bootstrap/materializer, so the already-approved exact Reviewed
Kickoff does not trigger a second user authorization solely because the remote branch did
not previously exist.

That standing allow is **not** authority to invent a task. Existing behavioral rules still
require an actual user-selected Reviewed task. The helper itself limits the effect to one
initial, artifact-bound `reviewed/<task_key>` branch in the current repo.

Update the managed Host behavior text so that:

- exact first publication through `reviewed-handoff task publish-first` is part of the
  already-authorized Reviewed branch strategy;
- raw `git push -u`, arbitrary new remote branches, alternate upstreams, force/tag/delete,
  remote remap and generic first push remain gated.

Do not add an authorization receipt, token, database, state field, watcher or controller.

## 6. Implementation boundary after Critic PASS

Expected touched layers are limited to:

- `ai_bridge_kit/reviewed_handoff.py` and CLI routing;
- reuse/extraction of existing Host transport/config fences only if needed, without changing
  public `publish-current-branch` behavior;
- Host Machine Policy / managed AGENTS wording for the one new bounded action;
- Reviewed Handoff normal-entry documentation;
- focused tests.

`publish-current-branch`, `materialize-worktree`, watcher publication authority and
resume semantics remain behaviorally unchanged.

## 7. Acceptance and regression gates

Before any release claim, one final candidate must prove:

- **FP-G1 brand-new first publication:** bootstrap -> commit -> `publish-first` creates only
  the exact Reviewed remote branch, binds only same-name origin upstream, and post-read SHA
  equals local HEAD with no second user prompt;
- **FP-G2 fail closed:** wrong repo/task/branch/worktree/state/lineage, dirty or uncommitted
  task metadata, noncanonical remote/transport/config/hook/environment, or any pre-existing
  remote branch causes no remote mutation;
- **FP-G3 forbidden-neighbor regression:** raw first push, arbitrary branch, force,
  force-with-lease, tag, delete, mirror, extra refspec, remote remap and alternate upstream
  remain outside the trusted path;
- **FP-G4 existing publication regression:** current
  `host publish-current-branch` existing-branch positive and negative tests remain unchanged;
- **FP-G5 resume regression:** local and remote-only `materialize-worktree --mode resume`
  behavior remains unchanged;
- **FP-G6 real consumer:** after deterministic fixtures pass, a fresh brand-new Reviewed task
  in a real consumer repo uses the normal entry end-to-end. The already manually published
  `product-ui-copy--cross-plugin-production-integration` task remains root-cause evidence,
  not fresh first-publication proof.

Do not create that fresh consumer task in this design round.

## 8. External reality check

Git's current official `git-push` documentation confirms that an explicit refspec fixes
the source/destination ref, ordinary branch updates are non-force unless `+`/`--force`
is used, and upstream tracking is stored as the branch remote/merge pair or established by
`--set-upstream`.

Adopted: exact explicit refspec, non-force behavior, deterministic same-name upstream.  
Rejected: force/force-with-lease, implicit `push.default`, tags/mirror/delete, arbitrary
caller-selected refspecs.

Reference checked 2026-09-29:
https://git-scm.com/docs/git-push

## 9. Planner result

```text
PLANNER_RESULT=READY_FOR_CRITIC
PLAN_VERSION=0.1
SELECTED_OPTION=REVIEWED_ONLY_FIRST_PUBLICATION_ACTION
GENERIC_PUBLISHER_BEHAVIOR_CHANGE=NO
BOOTSTRAP_NETWORK_BOUNDARY_CHANGE=NO
NEW_WORKFLOW=NO
NEW_AUTHORIZATION_STORE=NO
IMPLEMENTATION_AUTHORIZATION=NO
NEXT_HANDOFF=CRITIC
```

README checked: design-only round; no update required now.  
CHANGELOG checked: design-only round; no update required now.
