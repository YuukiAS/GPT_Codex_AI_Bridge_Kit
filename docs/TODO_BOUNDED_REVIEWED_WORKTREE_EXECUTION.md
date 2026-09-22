# TODO — Bounded Reviewed Worktree Execution

Status: NEW / POST-0.8.5

Source: real Project Thread Handoff implementation failure on 2026-09-22.

## Failure

A frozen current-user kickoff explicitly authorized:

- repo: `YuukiAS/AI_Skills_Collection`
- task key: `science-communication--project-thread-handoff`
- branch: `reviewed/science-communication--project-thread-handoff`
- sibling worktree: `../AI_Skills_Collection-science-communication-project-thread-handoff`
- base: `origin/main`

Codex correctly recognized that the exact effect was already authorized. The
normal command was:

```bash
git worktree add -b reviewed/science-communication--project-thread-handoff \
  ../AI_Skills_Collection-science-communication-project-thread-handoff \
  origin/main
```

The command first surfaced an approval interaction. After the user explicitly
approved that exact command, Auto-review rejected it again because the current
environment policy forbids the required escalated sandbox permission and exposes
no approval override.

This is stronger than a duplicate-question defect: the approved workflow has no
legal execution path for the frozen sibling worktree.

## Current 0.8.5 boundary

Bridge 0.8.5 intentionally keeps generic:

```text
git worktree add -> prompt
```

and the managed Host guidance already says that, until Bridge provides a
first-class bounded task-branch helper, branch/worktree creation may still
surface an approval interaction.

The new evidence shows that an approval interaction is not always sufficient:
the platform can reject the escalation even after explicit current-user
approval.

## Ownership

Bridge Kit owns the cross-repo execution primitive.

AI_Skills/workflow-core owns the consumer behavior that should call that
primitive for reviewed tasks. Do not duplicate the helper inside
AI_Skills_Collection.

## Candidate direction

Design, through the normal Planner/Critic process, the smallest trusted bounded
helper for reviewed task branch/worktree creation. Exact command/name remains a
future design decision; the capability should approximately:

1. verify canonical repository identity;
2. verify a semantic task key;
3. require branch exactly matching the authorized `reviewed/<task_key>` identity;
4. require the exact authorized worktree locator and reject path substitution;
5. require an allowed base ref such as the frozen `origin/main`;
6. fail closed on occupied path, repo mismatch, branch mismatch or existing
   unrelated worktree;
7. perform only the bounded branch/worktree mutation;
8. expose a Host-policy-sanctioned path for that trusted helper;
9. keep raw arbitrary `git worktree add`, branch switching/creation, remote
   mutation, force/destructive Git and shell composition on the normal approval
   path.

Do not solve this by globally allowing `git worktree add`, setting
`danger-full-access`, changing `approval_policy` to `never`, or letting
individual product repos invent local wrappers.

## Consumer expectation

Once the Bridge primitive exists, AI_Skills/workflow-core Reviewed Handoff should
prefer it whenever the current-user kickoff already freezes exact
repo/task/branch/worktree authorization.

If the helper is absent or the active Host/platform cannot safely execute the
frozen effect, fail early with `UNSUPPORTED_WITH_EVIDENCE` or the existing
Planner/recovery route. Do not repeatedly ask the user to approve the same exact
command, and do not silently switch to `/tmp`, another worktree path, the dirty
canonical checkout, or another branch.

## Promotion gates

1. Exact authorized reviewed branch + sibling worktree succeeds without a second
   user approval interaction.
2. Arbitrary branch or alternate path fails closed.
3. Raw generic `git worktree add` remains approval-gated.
4. Occupied/mismatched worktree identity fails closed.
5. At least two different repositories use the same helper without repo-specific
   hardcoding.
6. workflow-core normal entry consumes the Bridge helper and preserves the
   frozen Goal/Kickoff semantics.
7. No new authorization database, state machine, watcher or broad Git allowlist
   is introduced.
