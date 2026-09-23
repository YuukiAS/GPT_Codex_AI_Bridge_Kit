# TODO — Bounded Reviewed Worktree Execution

Status: NEW / POST-0.8.5  
Priority: HIGH — user explicitly requested short-term promotion on 2026-09-23.

Sources:

- real Project Thread Handoff implementation failure on 2026-09-22;
- real Scientific PDF Rendering pre-final recovery resume failure on 2026-09-23.

## Failure 1 — authorized new reviewed branch/worktree still had no legal execution path

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

This is stronger than a duplicate-question defect: the approved workflow had no
legal execution path for the frozen sibling worktree.

## Failure 2 — authorized reviewed-task resume asked again when the local worktree had disappeared

During Scientific PDF Rendering pre-final recovery, the Critic-approved resume
contract already bound the same task to:

- repo: `YuukiAS/AI_Skills_Collection`
- task key: `documents-media--scientific-pdf-rendering-reliability`
- existing remote branch:
  `reviewed/documents-media--scientific-pdf-rendering-reliability`
- exact task worktree:
  `/tmp/ai-skills-documents-media-scientific-pdf-rendering-reliability`

The remote reviewed branch still existed, but the local branch and authorized
`/tmp` worktree were no longer materialized. Codex therefore attempted to
restore the exact frozen task identity from the existing remote branch:

```bash
git worktree add \
  /tmp/ai-skills-documents-media-scientific-pdf-rendering-reliability \
  -b reviewed/documents-media--scientific-pdf-rendering-reliability \
  origin/reviewed/documents-media--scientific-pdf-rendering-reliability
```

Auto-review rejected the command and required the user to authorize the exact
local branch/worktree creation again in the current interaction. The user then
had to repeat the authorization before work could continue.

This second incident is important because it is not only a first-time branch
bootstrap problem. A reviewed task may already have a valid remote branch and a
frozen current-user contract, while its task-local worktree has been cleaned up
or is missing on the current host. Resuming that same task should not require the
user to restate the same branch/worktree decision merely to rematerialize the
already-authorized task execution surface.

## Current 0.8.5 boundary

Bridge 0.8.5 intentionally keeps generic:

```text
git worktree add -> prompt
```

and the managed Host guidance already says that, until Bridge provides a
first-class bounded task-branch helper, branch/worktree creation may still
surface an approval interaction.

The two real failures now show both sides of the gap:

1. an exact newly authorized reviewed branch/worktree can still be impossible to
   create through raw Git even after approval;
2. an already-existing reviewed task can lose its local materialization and
   force the user to repeat the same authorization during resume.

The missing capability is therefore not “allow `git worktree add` globally”.
It is a trusted Bridge-owned primitive that can materialize or rematerialize one
exact reviewed-task execution surface from a frozen current-user contract.

## Ownership

Bridge Kit owns the cross-repo execution primitive.

AI_Skills/workflow-core owns the consumer behavior that should call that
primitive for reviewed tasks. Do not duplicate the helper inside
AI_Skills_Collection.

Host Policy remains the owner of the narrow trusted execution path. Product
repositories remain owners of their task semantics and branch/worktree choices;
Bridge must consume those frozen choices rather than invent them.

## Candidate direction

Design, through the normal Planner/Critic process, the smallest trusted bounded
helper for reviewed task branch/worktree materialization. Exact command/name
remains a future design decision.

The capability should support two explicit cases without turning into a generic
Git wrapper:

### A. Bootstrap an authorized reviewed task

When the frozen current-user contract authorizes a new reviewed task:

1. verify canonical repository identity;
2. verify a semantic task key;
3. require branch exactly matching the authorized
   `reviewed/<task_key>` identity;
4. require the exact authorized worktree locator and reject path substitution;
5. require an allowed frozen base ref such as `origin/main`;
6. fail closed on occupied path, repo mismatch, branch mismatch, unexpected
   existing branch, or unrelated worktree;
7. create only that bounded local branch/worktree;
8. expose a Host-policy-sanctioned path for that trusted helper.

### B. Rematerialize an already-authorized reviewed task

When the frozen task already has the authorized remote reviewed branch but the
local branch/worktree is missing:

1. verify the same repo/task/branch/worktree identity from the frozen current-user
   contract;
2. verify the expected remote reviewed branch exists and resolves to the intended
   task lineage;
3. create/check out only the corresponding local branch into the exact authorized
   worktree path;
4. do not silently substitute `origin/main`, another remote branch, another
   worktree path, or the canonical checkout;
5. do not ask the user to repeat the same authorization solely because local
   task materialization was cleaned up;
6. fail closed if the local/remote branch identity is ambiguous, the target path
   is occupied by unrelated content, or the remote branch no longer matches the
   frozen task identity.

Both cases must keep raw arbitrary `git worktree add`, branch
switching/creation, remote mutation, force/destructive Git and shell composition
on the normal approval path.

Do not solve this by globally allowing `git worktree add`, setting
`danger-full-access`, changing `approval_policy` to `never`, adding a broad
`git switch/checkout` allowlist, or letting individual product repos invent
local wrappers.

## Authorization semantics to preserve

The helper must distinguish:

- **frozen scope evidence** in repo Goal/Plan/contracts;
- **current-user bounded authorization** for the exact task effect;
- **local materialization state**, which may disappear independently of either.

A missing local worktree does not erase a still-valid current-user authorization
for the same exact repo/task/branch/worktree effect. Conversely, a repo document
alone must not be treated as current-user authorization.

The implementation should consume already-valid authorization; it must not
create a new authorization database, infer permission from a task key alone, or
turn historical approvals into open-ended branch authority.

## Consumer expectation

Once the Bridge primitive exists, AI_Skills/workflow-core Reviewed Handoff should
prefer it whenever the current-user kickoff/resume already freezes exact
repo/task/branch/worktree authorization.

The consumer should use the same primitive for:

- first-time reviewed branch/worktree bootstrap;
- same-task resume when the remote reviewed branch exists but the local
  task-owned worktree is missing.

If the helper is absent or the active Host/platform cannot safely execute the
frozen effect, fail early with `UNSUPPORTED_WITH_EVIDENCE` or the existing
Planner/recovery route. Do not repeatedly ask the user to approve the same exact
effect, and do not silently switch to `/tmp`, another worktree path, the dirty
canonical checkout, another branch, or another repository.

## Promotion gates

1. Exact authorized new reviewed branch + worktree succeeds without a second
   user approval interaction.
2. Exact authorized same-task resume can rematerialize an existing remote
   reviewed branch into the frozen worktree without repeated authorization.
3. Arbitrary branch, alternate remote branch, alternate base, or alternate
   worktree path fails closed.
4. Raw generic `git worktree add` and generic branch switch/create remain
   approval-gated.
5. Occupied/mismatched worktree identity and ambiguous local/remote branch
   identity fail closed.
6. A repo Goal/Plan without current-user bounded authorization is insufficient to
   invoke the trusted mutation.
7. At least two different repositories use the same helper without repo-specific
   hardcoding.
8. workflow-core normal entry consumes the Bridge helper for both bootstrap and
   rematerialization while preserving frozen Goal/Kickoff/Resume semantics.
9. Cleanup/removal of a task-local worktree does not silently delete or broaden
   the frozen authorization contract; later same-task rematerialization either
   succeeds under the same exact identity or fails with evidence.
10. No new authorization database, state machine, watcher, generic Git wrapper,
    or broad Git allowlist is introduced.

## Near-term promotion note

This TODO now has two independent real reproductions in the same consumer repo:
one during initial reviewed-task branch/worktree creation and one during
pre-final same-task recovery after local worktree loss. The second reproduction
shows that wording the exact branch/worktree into a reviewed resume prompt is
not sufficient by itself to prevent repeated user interruption.

The next Bridge refinement should therefore promote this TODO through the normal
Planner/Critic architecture review rather than waiting for another occurrence.
## Wrapper-minimization prerequisite

Before implementing a new `ai-bridge` helper for this mutation, follow
`docs/TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md`:

1. first test whether the current Host Policy / execpolicy plus exact
   current-user authorization can legally perform the frozen branch/worktree
   effect directly;
2. do not add a helper merely because Auto-review produced friction;
3. retain a bounded helper only if the real safety condition depends on dynamic
   repo/task/branch/path identity that a narrow native rule cannot express;
4. document why direct native Git remains insufficient before production
   implementation begins.

This worktree case is materially different from read-only Git/GitHub inspection:
read-only inspection should be solved by direct allow rules, not by another
wrapper.

