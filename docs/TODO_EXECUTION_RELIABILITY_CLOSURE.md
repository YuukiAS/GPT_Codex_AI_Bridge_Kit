# TODO — Bridge Execution Reliability Closure

Status: READY FOR PLANNER INTAKE / NOT IMPLEMENTATION AUTHORIZATION  
Priority: CRITICAL — user requests one convergence release, not another incident-by-incident patch train  
Date: 2026-10-01  
Task key candidate: `bridge-core--execution-reliability-closure`

## User objective

Bridge Kit has accumulated several small reliability releases that each closed a real
failure, but the user is still seeing a worse product-level failure mode: a normal
Codex task can make substantial valid progress and then be terminated because the
executor repeatedly chooses approval/escalation paths for operations that either
belong inside the current workspace sandbox, are optional, or already have a bounded
Bridge normal entry.

The next Bridge release must therefore close the **failure class**, not only the
latest command.

The intended user experience is:

> A normal authorized task should keep running through ordinary build/test/render/QA
> work, use the canonical bounded Bridge entry for the few effects that genuinely
> need one, preserve completed work when one effect is unavailable, and never turn a
> recoverable approval refusal into an escalation cascade that kills the whole task.

The user explicitly does **not** want a sequence of `0.9.4`, `0.9.5`, ... releases
for nearby variants of the same execution-reliability problem. Planner should prefer
one coherent convergence stage, tentatively **0.10.0**, if the final reviewed scope is
substantial enough to satisfy the repository versioning contract. Do not force a
MINOR bump by version cosmetics alone; the release must represent a real compatible
execution-reliability capability stage.

## Latest real incident — STAT5060 Rich Edition

Repository:

`YuukiAS/STAT5060-TA`

Branch:

`work/stat5060--tutorial-01-v2`

The implementation itself completed successfully and was committed locally as:

`511fddfda9721f00c1d8bdb3774d9a17f37c3e95`

The worktree was clean, the branch was ahead of its existing remote by one commit,
and the Rich Edition TeX/PDF, 37 page renders, and evidence package already existed.
The task did not fail because of statistical content, rendering, build correctness,
or repository damage.

### Failure A — optional repo-local cleanup was escalated

Codex attempted repo-local generated-cache cleanup using `rm -rf` with
`require_escalated`. Auto-review rejected it.

The cleanup was not required for the build and should have been skipped after the
refusal rather than becoming part of the task's failure trajectory.

### Failure B — repo-local build/check was escalated

Codex attempted:

`python scripts/tutorial01_rich_build_and_check.py`

with `require_escalated`.

Audit showed that this script writes only within the repository's approved material
and result paths, redirects TeX state into repo-local `results/tutorial-01-rich/texmf-*`
directories, does not use `sudo`, does not install packages, does not mutate PATH,
and does not require system-directory writes.

Therefore:

`REPO_LOCAL_BUILD_REQUIRES_ESCALATION = NO`

This is a normal-entry execution-route failure, not insufficient task authorization.

### Failure C — bounded publisher rejected an ambient askpass environment

Current Bridge 0.9.3 `publish-current-branch` rejects any inherited
`GIT_ASKPASS` or `SSH_ASKPASS` before it constructs its sanitized publication
environment.

The affected Codex Desktop / Remote SSH environment inherited:

`SSH_ASKPASS=/usr/libexec/openssh/gnome-ssh-askpass`

and the bounded publisher returned:

`ASKPASS_REQUIRES_APPROVAL`

The formal Bridge 0.9.3 release target is:

`9dad0ba4bfa54e251f345091c5151ae991251ec9`

so this was **not** evidence that the machine was running an obsolete Bridge source.
The canonical `main` later advanced by release/evidence documentation commits.

The current security boundary was intentionally conservative because Git can use
`GIT_ASKPASS`, `core.askPass`, and finally `SSH_ASKPASS` as executable credential
prompt paths. The defect is that the product currently treats an ambient host value
as an automatic blocker even though the bounded helper later sanitizes these variables
for the actual remote operation.

### Failure D — invalid fallback widened the effect

After the bounded publisher failed closed, Codex fell back to raw:

`git push origin HEAD:work/stat5060--tutorial-01-v2`

and again requested escalation.

Current Machine Policy does not define raw Git push as the automatic fallback for a
failed bounded publisher. The correct behavior should have been to preserve the
already-completed local commit, classify publication as the only unresolved effect,
and stop or recover through the canonical supported route without widening authority.

### Failure E — repeated refusals terminated the trajectory

The sequence was approximately:

`optional cleanup escalation -> refusal -> repo-local build escalation -> refusal -> bounded publisher failure -> raw push escalation -> refusal -> task trajectory terminated`

The product-level failure is not any one rejection. It is that Bridge/Host guidance
did not prevent multiple avoidable escalation attempts from accumulating into loss of
the running task.

## Runtime identity hygiene found during the audit

The affected machine reported:

- `ai-bridge`: `/users/a/e/aereinh/bin/ai-bridge`
- imported source:
  `/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit/ai_bridge_kit/__init__.py`
- package version: `0.9.3`
- source HEAD: `9dad0ba4bfa54e251f345091c5151ae991251ec9`
- duplicate editable metadata for historical `0.9.1` and current `0.9.3`

This was not the cause of the STAT5060 failure because `9dad...` is the formal
0.9.3 release target. It is still weak runtime identity hygiene: production execution
should not require interpreting stale editable metadata or confusing release-target
identity with later documentation-only `main` commits.

## Planner scope for the convergence release

Planner must examine the current 0.9.3 implementation and all still-relevant prior
Auto-review / normal-entry incident evidence before freezing the next release. Do not
implement the bullets below directly from this TODO; they are problem statements and
candidate closure requirements.

### 1. Sandbox-first normal execution

Bridge Machine Policy / installed Host guidance must make the normal execution
decision explicit:

- workspace-contained build/test/lint/render/QA/task scripts run first through the
  normal `workspace-write` path;
- do not request escalation merely because the command is Python, TeX, a build script,
  or produces generated files;
- only an observed sandbox-boundary failure can justify reconsidering execution
  authority;
- do not solve this by globally allowing generic shell/Python.

This must be validated through real normal Codex behavior, not only source wording.

### 2. Refusal classification and escalation-cascade circuit breaker

A rejected or unavailable operation must be classified before the task tries another
authority path:

- optional/non-required effect -> skip and continue;
- sandbox-capable effect that was unnecessarily escalated -> return to normal sandbox
  execution;
- bounded normal entry unavailable -> preserve completed state and report/recover the
  exact unresolved effect;
- true authority/safety boundary -> use the existing bounded approval/HUMAN_ONLY path.

Without new evidence that the required authority changed, one refusal must not trigger
a chain of broader escalation fallbacks.

This must remain behavioral guidance within existing workflow/state surfaces; do not
create a new approval database, refusal state machine, daemon, or controller family.

### 3. Bounded publisher compatibility with ambient host credential UI variables

Re-evaluate the existing publisher's askpass fence using real Git credential semantics
and current Codex Desktop / Remote SSH environments.

Required properties:

- normal GitHub HTTPS publication on an already-authorized existing same-name branch
  works in a representative environment that inherits ordinary host
  `SSH_ASKPASS`;
- the trusted helper must prove that the inherited askpass program cannot be executed
  on its bounded positive path, for example by sanitizing before every remote/network
  operation that could invoke credential prompting;
- `GIT_ASKPASS`, repo/worktree/command-scope `core.askPass`, executable credential
  helper injection, `GIT_SSH`, `GIT_SSH_COMMAND`, custom Git config, hook, wrong
  destination, force, tag, delete, upstream and transport-expansion negatives remain
  fail-closed;
- no raw-push fallback is silently executed when the bounded helper rejects the
  environment.

Do not weaken the security boundary merely to make the positive gate pass.

### 4. Canonical-entry fallback semantics

For every Bridge-owned bounded normal entry that replaces a riskier raw operation,
define the failure behavior explicitly:

- helper success -> continue;
- helper reports an environment/capability blocker -> do not automatically widen to
  the raw operation;
- preserve already-completed task artifacts/commits;
- surface the smallest unresolved effect and legal recovery route;
- if no legal recovery exists, return a truthful recoverable block rather than
  poisoning unrelated completed phases.

The Planner should inventory current Host-preauthorized / bounded execution entries
and decide where this rule is genuinely shared. Do not create one wrapper or rule per
command.

### 5. Runtime/release identity validation

Strengthen `ai-bridge host validate` or the owning runtime-identity path so a machine
can distinguish:

- executable real path;
- imported package source;
- package version;
- source Git HEAD when source is an editable checkout;
- formal Bridge release target/ref;
- dirty source state;
- duplicate/conflicting editable distribution metadata;
- active `CODEX_HOME` and installed Machine Policy identity.

Formal release identity must be compared to the canonical `release` target, not
blindly to the latest `main` HEAD, because evidence/closure documentation may advance
`main` without changing the released runtime.

The Planner must decide whether duplicate historical metadata is a warning or a
validation failure based on whether it can affect actual import/executable resolution.

### 6. Normal-entry release gates across real environments

The next release must not close on unit tests and synthetic execpolicy checks alone.

At minimum design same-final-candidate gates for:

1. repo-local build/test/render/QA completes without unnecessary escalation;
2. optional cleanup refusal does not terminate or redirect the Goal;
3. existing-branch GitHub HTTPS bounded publication succeeds under a representative
   ambient `SSH_ASKPASS` environment;
4. malicious/custom askpass/credential/transport injection remains blocked;
5. bounded publication failure does not trigger raw Git fallback;
6. repeated refusal scenario preserves completed work and produces one truthful
   unresolved-effect handoff instead of a trajectory-killing escalation cascade;
7. existing Reviewed bootstrap / first publication / materialization behavior remains
   correct;
8. existing dangerous Git, arbitrary branch/upstream, force/delete/remap and generic
   shell/Python boundaries remain gated;
9. runtime identity validation correctly accepts the formal release target even when
   `main` has later evidence-only commits, and diagnoses an actually stale/wrong
   runtime;
10. at least one real consumer repository reproduces the original STAT5060-shaped
    path end-to-end on the final candidate.

Gate design should prefer a small number of capability gates that each correspond to
a real user capability/failure mode. Do not inflate the matrix with source-presence
checks.

## Existing work that must not be reopened without regression evidence

The convergence release must preserve, not redesign by default:

- Lite / Reviewed Mode / Controlled Mode taxonomy;
- Reviewed bootstrap and resume normal entries already released in 0.9.1;
- Persistent Run lifetime ownership and progress semantics already released in
  0.9.0-0.9.2;
- Reviewed first remote publication already released in 0.9.3;
- current `release` ref distribution model;
- existing external Planner/Reviewer waiting semantics;
- no generic danger-full-access or `approval_policy=never` path.

Prior TODO/design files remain evidence. Resolved mechanics should enter the regression
bank rather than becoming new architecture work.

Relevant historical inputs include:

- `docs/TODO_HOST_POLICY_READ_ONLY_INSPECTION_AND_WRAPPER_MINIMIZATION.md`
- `docs/TODO_NEXT_BRIDGE_LOW_FRICTION_CONVERGENCE.md`
- `docs/TODO_BOUNDED_REVIEWED_WORKTREE_EXECUTION.md`
- `docs/TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md`
- 0.9.0-0.9.3 design/evidence under `docs/design/` and `results/`

## External reality that Planner/Critic must re-check

Use current official sources rather than assumptions.

Current OpenAI guidance says the sandbox is the normal technical boundary, most
actions should run inside it without approval, and boundary-crossing actions are the
small fraction sent to Auto-review. That supports sandbox-first normal execution
rather than pre-emptive escalation.

Current Git documentation confirms that credential prompting can execute
`GIT_ASKPASS`, then `core.askPass`, then `SSH_ASKPASS`; therefore askpass handling
is a real executable-path safety problem and must be solved by proving non-execution,
not by declaring the variable harmless.

Critic must independently verify both assumptions before approving implementation.

## Version / release strategy

Do not pre-commit to another patch train.

Planner should start from:

`candidate release = 0.10.0 execution-reliability closure`

and test that against the repository version contract.

A `0.10.0` MINOR candidate is justified only if the reviewed final scope forms one
substantial backward-compatible user-visible capability stage: reliable normal
execution that survives optional failures and uses bounded publication correctly
across supported Codex environments.

If Critic concludes the work is only a narrow compatible bug fix and therefore must
remain PATCH by repository policy, Planner must still deliver it as **one** coherent
release rather than serial incident patches, unless an actual safety/recovery
dependency makes a split unavoidable.

No production version bump occurs during planning.

## Completion standard

This TODO is closed only when one final candidate demonstrates that the class of
failure is removed from normal use, not merely that the STAT5060 command now passes.

The final closure must state:

- what ordinary operations can proceed without approval;
- which effects still legitimately cross the sandbox/authority boundary;
- what happens after a refusal;
- how completed work is preserved;
- how bounded-entry failure is recovered without raw fallback;
- how runtime/release identity is verified;
- which previous incident classes were regression-tested;
- what residual cases remain genuinely outside Bridge ownership.

A future unrelated platform change or genuinely new capability may still require
another release. The objective here is to avoid another release for a nearby variant
of the same known execution/approval reliability class.
