# TODO — Host Policy Read-Only Inspection + Wrapper Minimization

Status: NEW / HIGH PRIORITY / SHORT-TERM  
Date: 2026-09-23

## User problem

Auto-review is now rejecting ordinary read-only diagnostics often enough to
change task direction, not merely add one confirmation.

Recent real failure:

- the user asked Codex to inspect Git / remote state;
- Codex needed to determine whether GitHub authentication and a private
  repository were actually reachable;
- direct read-only checks such as `gh auth status` and a precise
  `git ls-remote` probe were rejected by Auto-review;
- because the evidence could not be collected, the task drifted toward
  "Git authentication is blocked / user must repair credentials" and execution
  terminated instead of completing the requested diagnosis.

This is a product-usage regression. Host Policy should not make routine
observation harder than mutation.

## Principle

Prefer this order:

1. direct allow for commands whose observable command shape is read-only and
   low-risk;
2. keep mutation, destructive operations, external publication, secret
   disclosure and dynamically unsafe forms gated;
3. use a Bridge-owned wrapper only when the safety condition genuinely depends
   on dynamic facts that a narrow execpolicy rule cannot express;
4. do not create one `ai-bridge <wrapper>` per Auto-review false positive.

The existing Bridge 0.7.2 / 0.7.3 design already follows this rule for
`squeue`, `ps`, `tmux ls`, and related inspection. This TODO extends the
same product principle to Git / GitHub inspection.

## Candidate direct read-only allow surface

The exact final rule set must be reviewed with real `codex execpolicy check`
evidence. The default direction is direct Host Policy allow, not wrappers.

### Local Git inspection

Candidate commands:

```text
git status
git diff
git diff --cached
git log
git show
git rev-parse
git branch --show-current
git branch --list
git remote -v
git remote get-url
git worktree list
git ls-files
git tag --list
```

These commands inspect repository state and do not intentionally mutate branch
topology, remotes, working-tree content or remote repositories.

Do not broaden this into mutation-capable siblings such as:

```text
git switch
git checkout
git branch -d/-D/-m/-M
git remote add/remove/set-url
git reset --hard
git clean
git restore
```

### GitHub CLI read-only inspection

Candidate commands:

```text
gh auth status
gh repo view
gh pr view
gh pr list
gh issue view
gh issue list
gh run view
gh run list
```

The objective is to let Codex inspect authentication/repository/PR/issue/run
state without a review interruption. This is not permission to print tokens,
read secret values, mutate repository state, authenticate a new account, or
perform write actions.

Nearby mutation commands remain gated, including:

```text
gh auth login
gh auth logout
gh repo create
gh repo delete
gh pr create
gh pr merge
gh issue create
gh run cancel
gh secret ...
```

### Configured-remote reachability

Prefer direct configured-remote probes where the remote identity is already
owned by the current Git repository:

```text
git ls-remote origin
git ls-remote origin refs/heads/main
```

Do not automatically allow arbitrary URL/refspec forms such as:

```text
git ls-remote <arbitrary-url-or-helper>
```

unless real execpolicy semantics prove a narrow safe rule. A configured
`origin` probe is the normal diagnostic target; arbitrary transport/helper
semantics must not be smuggled into a broad prefix allow.

## Failure-semantics requirement

A rejected optional/read-only diagnostic must not itself redirect an otherwise
recoverable Goal into terminal `BLOCKED`.

When a task is only trying to observe state:

- first use the canonical directly allowed inspection surface;
- if one optional probe remains approval-gated, record the unavailable evidence
  precisely;
- do not infer "authentication broken", "remote inaccessible", or "user action
  required" solely because Auto-review rejected the diagnostic command;
- only report a real auth/remote blocker after observable evidence establishes
  that the supported diagnostic path itself fails.

## Wrapper minimization audit

Bridge currently has only one Host-Policy-preauthorized `ai-bridge` command
whose primary purpose is to wrap a lower-level execution path that would
otherwise remain approval-gated:

```text
ai-bridge plugin-replay
```

Other major `ai-bridge` commands are product/workflow surfaces with their own
semantic ownership (Host Policy, Lite/Review/Control, Overleaf mirroring,
notifier transport, Text/Visual Review, Persistent Run contract management),
not merely read-only-command wrappers.

There is also a top-level `reviewed-handoff` compatibility router in
`bridge_cli.py`; that is CLI compatibility plumbing, not a Host Policy
permission-bypass wrapper.

### Historical lesson: candidate plugin replay

Bridge previously designed and briefly implemented a second wrapper,
`ai-bridge candidate-plugin-replay`, then rolled it back before release on
2026-09-08. Repository history:

- design/probe/implementation work culminated in the B0 candidate wrapper;
- commit `b6ab9ac74a01eb0a7e96fb0dca38d7c0a8a48e69`
  ("Rollback unreleased candidate plugin replay") removed that entire
  unreleased capability.

AI_Skills later kept its own repo-local candidate replay tooling, but subsequent
OpenAI/Codex plugin guidance establishes an official local-development flow
based on local/personal marketplaces, `codex plugin add` / reinstall, and a
fresh thread/session. AI_Skills' 2026-09-22 machine-update design explicitly
adopts official Codex plugin/Marketplace commands rather than reimplementing
plugin installation/update mechanics.

Therefore "build another wrapper" is not the default answer to plugin testing
or Auto-review friction.

## Wrapper retirement / simplification candidates

### 1. `ai-bridge plugin-replay` — REVIEW FOR DEPRECATION OR NARROW RETENTION

This is the strongest current removal candidate.

Before retaining it as a permanent Bridge capability, compare its remaining
unique value against the official Codex local Marketplace / plugin reinstall /
fresh-session workflow.

Keep it only if current real workflows still require a capability that the
official flow cannot provide without equivalent new machinery, for example a
fully unattended fresh child over explicitly selected private inputs with
bounded local writes.

If ordinary plugin development, candidate validation and normal-entry testing
can use the official local Marketplace / reinstall / fresh-session path, remove
those responsibilities from `plugin-replay` and from consumer guidance.

Do not remove it blindly: current Bridge/AI_Skills docs and tests still reference
it, so retirement requires a migration/compatibility plan and real replacement
evidence.

### 2. Future reviewed-worktree helper — WRAPPER ONLY IF DIRECT POLICY CANNOT EXPRESS SAFETY

The existing
`docs/TODO_BOUNDED_REVIEWED_WORKTREE_EXECUTION.md` documents a real mutation
problem. Unlike read-only Git inspection, worktree/branch materialization changes
Git topology and safety depends on repo/task/branch/path identity.

Before implementing a helper, explicitly test whether current Host Policy /
execpolicy plus exact current-user authorization can legally execute the frozen
effect directly. Only if native policy cannot express the required dynamic
identity checks should a bounded helper be accepted.

### 3. Read-only Git/GitHub diagnostics — NO WRAPPER

Do not create:

```text
ai-bridge git-auth inspect
ai-bridge git-status ...
ai-bridge github-status ...
```

for ordinary read-only inspection. Prefer direct allow rules with positive and
nearby-negative execpolicy tests.

## Non-candidates for removal solely under this TODO

Do not label these "unnecessary wrappers" merely because they are exposed under
`ai-bridge`:

- `host`: owns machine Host Policy generation/validation;
- `init` / `validate`: own Lite project installation/validation;
- `reviewed-handoff` / watcher: own Review workflow semantics;
- `agent-flow`: owns Control workflow semantics;
- `overleaf`: owns manuscript projection, divergence detection and mirror
  safety, not just raw Git;
- `notifier`: owns notification semantics/dedup/retry;
- `text-review`, `visual-review`, `text-transform`: own encrypted transport,
  evidence binding and paid-review controls;
- `persistent-run`: owns long-Goal contract/install/prompt semantics and does
  not simply preauthorize arbitrary tmux mutation;
- `private sync`: currently a narrow notifier-private-config transport and
  should be reviewed only if that product capability is retired.

These may still be simplified in future, but not merely under the argument that
"all ai-bridge commands are wrappers".

## Promotion gates

### Read-only Host Policy

1. Real `codex execpolicy check` proves the approved local Git inspection
   commands are `allow`.
2. Real checks prove approved `gh` read-only inspection forms are `allow`
   without allowing auth/login or write commands.
3. Configured-origin `git ls-remote` read probes are usable without opening
   arbitrary remote/helper execution.
4. Nearby mutation/destructive commands remain `prompt`.
5. A real Codex diagnostic task can inspect Git/GitHub auth/remote state without
   user interruption or false terminal BLOCKED.
6. No new wrapper is introduced for these read-only commands.

### Wrapper minimization

1. Produce an inventory of every Host-policy-preauthorized wrapper and every
   consumer that still depends on it.
2. Recheck current official OpenAI/Codex capabilities before retaining a custom
   wrapper.
3. For each wrapper retained, name the concrete dynamic safety/product capability
   that direct native commands cannot provide.
4. For each wrapper retired, migrate consumers to the mature official/native
   path and preserve normal-entry evidence.
5. Do not add another permission-bypass wrapper while an equivalent direct
   read-only allow or official product mechanism exists.
6. No new wrapper registry/state machine/database is introduced.

## Ownership and next step

Bridge Kit owns Host Policy and any genuinely necessary cross-repo execution
primitive.

AI_Skills owns cleanup of its repo-local candidate replay tooling and consumer
guidance if that tooling is now redundant with official Codex plugin
development/testing.

Because changing Host Policy allow rules or retiring `plugin-replay` changes
production behavior, implementation must go through the normal Planner/Critic
review. This TODO is evidence and scope, not implementation authorization.

## Additional failure — ordinary push to an already-authorized task branch was blocked

A second Auto-review usability failure was observed on 2026-09-23 in a normal
task branch workflow.

Observed state:

- local branch: `review/01047-clear-writing`;
- local branch was already selected and ahead of its existing remote by one
  ordinary task-owned commit;
- the only remaining publication action was:
  `git push origin review/01047-clear-writing`;
- Codex reported that Auto-review blocked the push and required another explicit
  user authorization before it could publish the already-created commit.

Current Host Policy deliberately allows `git push origin main` but keeps
`git push origin <other-branch>` on the prompt path. That policy is now too
coarse for repositories that already have an explicitly authorized, selected,
existing task/review branch.

The product requirement for the next design round is:

> Once a branch has already been explicitly selected/authorized for the current
> task and the matching remote branch already exists, an ordinary non-force push
> of task-owned commits to that same `origin/<branch>` should not repeatedly
> interrupt the user.

This must **not** silently authorize:

- creation of an arbitrary new remote branch;
- changing or setting upstream;
- pushing to a different branch than the frozen/current task branch;
- force / force-with-lease;
- deletion of remote refs/tags;
- remote remapping;
- bypassing repository-owned publication/reviewer authority.

Planner/Critic must determine the smallest native Host Policy / project-policy
mechanism. Do not pre-commit to a wrapper. In particular, first test whether
current Codex execpolicy and repository-level exact branch rules can represent
"ordinary push to the already-authorized existing task branch" without broadly
allowing `git push origin <anything>`.

Acceptance must include at least:

1. `git push origin main` remains low-friction where already allowed;
2. an ordinary push to an explicitly authorized existing non-main task branch
   succeeds without another user approval;
3. pushing a different/unapproved branch remains gated;
4. creating a new remote branch or changing upstream remains gated;
5. force/deletion/remote mutation remains gated;
6. a rejected push probe alone does not cause a false terminal `BLOCKED`.

