# TODO — Execution Context Continuity: Canonical Worktree + Mandatory Control Reads

Status: **READY FOR PLANNER INTAKE / NOT IMPLEMENTATION AUTHORIZATION**  
Priority: **CRITICAL — repeated real-user task interruption**  
Date: 2026-10-08  
Task key candidate: `bridge-core--execution-context-continuity`

## User problem

A long-running STAT5060 HW1 closure task exposed a remaining Bridge execution-reliability failure class.

The user had already selected:

```text
repository = YuukiAS/STAT5060-TA
target branch = hw
desired execution location = the current repository checkout
```

The task nevertheless drifted into a separate `/tmp` worktree, then later required repeated approval-sensitive Git topology operations merely to return to the user-selected repository.

In the same task, mandatory V2 controller/authority files on `origin/hw` were not present in the local partial-clone object cache. Raw `git show origin/hw:<path>` attempted lazy object hydration, which required writing protected `.git/objects`; the sandbox failed, Codex requested `require_escalated`, and Auto-review rejected it. Codex then continued from incomplete controller context and missed the already-defined repo-local scientific runtime contract.

That context loss caused a second bad route: it attempted an ad-hoc `/tmp` R library and pre-emptive escalation instead of the repository's required Longleaf + `<repo>/.r-lib` route.

This is not primarily a STAT5060 statistical problem. It is a Bridge normal-entry continuity problem.

## Observed failure chain

### Failure A — execution worktree drift

The task began from an existing STAT5060 checkout, but an older closure candidate worktree existed under:

```text
/tmp/stat5060_hw_closure_worktree
```

The executor treated preservation of that candidate as permission to continue execution there.

Later, when the user explicitly required execution in the current repository checkout on `hw`, the executor encountered:

- `hw` already checked out by the `/tmp` worktree;
- unrelated dirty tutorial work in the current checkout;
- dirty HW candidate work in the `/tmp` worktree.

It then attempted, in separate approval-sensitive steps:

1. move the worktree;
2. detach the worktree to free `hw`;
3. switch the current checkout to `hw`.

This converted one already-decided user goal into repeated Git-topology approvals.

### Failure B — mandatory controller read failed under partial clone

The executor tried to read V2 files using:

```text
git show origin/hw:<path>
```

The required blob was missing locally. Partial-clone hydration attempted to write into the real Git object database, which the ordinary sandbox could not modify.

The executor then requested `require_escalated`; Auto-review rejected it.

The same class of read was attempted again and rejected again.

### Failure C — execution continued without mandatory controller context

After failing to read the V2 Goal/authority, the executor continued from prompt excerpts and one available critic file.

That was incorrect because the V2 Goal required reading:

```text
docs/execution/STAT5060_HW1_REPO_LOCAL_SCIENTIFIC_ENVIRONMENT_V1.md
```

The omitted contract already specified:

```text
Longleaf base runtime
+ repository-local .r-lib
+ repository-local .venv when needed
+ no require_escalated merely for CRAN package installation
+ sequential logitr -> mlogit -> gmnl
```

### Failure D — ad-hoc dependency route and repeated escalation

Because the runtime contract had not been consumed, the executor proposed:

```text
/tmp/stat5060_r_lib
install.packages(c("logitr","mlogit","gmnl"), ...)
require_escalated
```

Auto-review rejected this too.

The package task itself was not the root cause; missing mandatory control context was.

## Product requirement

A normal authorized task must preserve three invariants:

1. **Execution location continuity**  
   Unless the user or frozen Goal explicitly selects another worktree, the checkout from which the task starts is the canonical execution worktree. Discovery of another candidate worktree does not transfer execution ownership to it.

2. **One user decision must not fragment into repeated low-level approvals**  
   When the user has already selected an exact repository + current checkout + target branch, Bridge must not require separate user decisions for move/detach/switch merely to realize that already-approved execution topology.

3. **Mandatory controller context is a hard precondition**  
   If the active Goal/authority/runtime contract is declared mandatory, substantive execution must not begin until it has actually been read. Prompt excerpts or remembered summaries may not silently substitute for an unread required source.

## Proposed direction

This TODO records the product requirement. Planner/Critic must still compare native Codex/Git alternatives before implementation.

### A. Canonical execution worktree binding

At task start, resolve and freeze:

```text
CANONICAL_REPO_ROOT
CANONICAL_WORKTREE
CURRENT_BRANCH
TARGET_BRANCH
CURRENT_HEAD
DIRTY_STATE
WORKTREE_INVENTORY
```

Default rule:

```text
current checkout = canonical execution worktree
alternate worktree execution = forbidden unless explicitly authorized
```

Before substantive work, detect whether the target branch is already owned by another worktree.

Do not create or adopt a `/tmp`, sibling, or second checkout merely because an older candidate exists.

### B. Bounded worktree normalization only for real conflict recovery

If a real pre-existing conflict exists, such as:

```text
current checkout = dirty unrelated branch/work
other worktree = dirty target-branch candidate
user-selected final execution location = current checkout
```

Bridge should determine whether current native policy can safely perform the already-authorized normalization without another product decision.

If not, design one bounded recovery entry rather than broadly allowing raw:

```text
git switch
git checkout
git worktree ...
git stash
```

A bounded recovery entry must prove exact repository/worktrees/target branch, preserve both dirty states, prevent reset/clean/data loss/new branch creation, verify candidate content before/after, and fail closed on ambiguity.

The helper, if required, is for dynamic worktree-safety checks. It must not become a generic Git topology wrapper.

### C. Mandatory control-file read normal entry

Bridge must provide a reliable way to read an exact file from the configured `origin` branch/commit even when the repository is a partial clone and the blob is absent locally.

Planner must compare:

- native direct Git/Codex capability;
- temporary Git object storage using the real object store as read-only alternate;
- a bounded Bridge read entry only if dynamic identity/safety cannot be expressed directly.

The required capability is narrowly:

```text
current repository
+ configured origin
+ exact branch/ref or expected commit
+ one repository-relative file
+ stdout/read result
+ no checkout
+ no ref/branch/upstream/remote/config mutation
+ no working-tree mutation
```

Do not solve this by broadly allowing arbitrary `git show` outside the sandbox.

### D. Controller-read gate

When a Goal/authority declares files mandatory:

```text
MANDATORY_CONTROL_SOURCES_READ = YES
```

must be established before:

- dependency installation;
- capability spikes;
- candidate mutation;
- rendering;
- validation that depends on those sources.

If a required source cannot be read, stop at the smallest truthful source-access blocker. Do not continue from prompt excerpts while claiming the active controller has been consumed.

### E. Do not invent another dependency-management product

Once the required repository-specific runtime contract is actually read, follow it.

For the reproduced STAT5060 case, the correct route is already:

```text
Longleaf runtime
<repo>/.r-lib
logitr first
mlogit only if needed
gmnl only if needed
```

No Bridge R-package wrapper, generic `Rscript` allow rule, or `/tmp` project environment is required.

The existing sandbox-first rule remains: network access or repository-local dependency installation is not by itself a reason to request `require_escalated`.

## Prefix-rule boundary

Do **not** directly add broad allows for:

```text
git show
git switch
git checkout
git worktree
git stash
Rscript
python
bash
sh
install.packages
```

Use direct rules only where command shape alone is sufficient.

Use a bounded Bridge operation only where safety depends on dynamic repository/worktree/branch/path state that prefix matching cannot prove.

## Required regression gates

The eventual candidate must pass real normal-entry tests, not only unit tests or rule-file checks.

### Gate 1 — canonical worktree continuity

Start Codex in repository checkout A with another candidate worktree B present.

PASS requires:

- execution remains in A unless the frozen task explicitly selected B;
- discovery of B does not silently change execution worktree;
- no `/tmp` or sibling worktree is created/adopted as a workaround.

### Gate 2 — dirty dual-worktree normalization

Use a fixture with:

- dirty current checkout on a different branch;
- dirty target-branch candidate in another worktree;
- frozen user decision that final execution must be current checkout + target branch.

PASS requires:

- both dirty states preserved;
- target branch becomes usable in the user-selected checkout;
- candidate content preserved exactly;
- no repeated product-level approval for each internal Git step;
- no reset/clean/new branch/data loss.

### Gate 3 — partial-clone mandatory-source read

Use a real partial clone whose required control-file blob is absent locally.

PASS requires:

- exact mandatory file is successfully read;
- no false claim that an unread file was read;
- no broad Git permission expansion;
- no repeated `require_escalated` cascade.

### Gate 4 — controller-before-execution

Make the mandatory runtime contract materially affect the correct next action.

PASS requires Codex to read it before choosing the runtime/dependency path.

A prompt excerpt that omits the runtime rule must not cause Codex to invent an alternate environment.

### Gate 5 — long-task continuation

One fresh normal Codex run must combine:

```text
worktree preflight
-> mandatory partial-clone control read
-> repository-defined dependency/runtime path
-> required build/QA work
```

A recoverable approval refusal must not trigger repeated/broader escalation attempts or terminate unrelated required work.

### Negative neighbors

Keep gated:

- arbitrary Git topology mutation;
- destructive Git;
- new/unapproved branch creation;
- reset/clean/discard of dirty work;
- arbitrary remote/ref/config mutation;
- system/global dependency installation;
- generic shell/Python/R outside-sandbox allow rules.

## Versioning question

Do not pre-split this failure class into multiple patch releases.

Planner should first determine the actual formal release identity and then prefer one convergence release:

- if `0.10.0` is not yet formally distributed, fold this regression closure into the final `0.10.0` candidate;
- if `0.10.0` is already formally distributed, prefer one `0.10.1` patch unless the reviewed design introduces a genuinely new product capability that justifies a larger bump.

Current repository metadata should be reconciled before freezing the version claim: current README text and current `release` branch/version metadata appear inconsistent about whether `0.10.0` is already the formal distribution target.

## Non-goals

This TODO does not authorize:

- implementation;
- Machine Policy installation;
- production rollout;
- broad Git/R/Python/shell allow rules;
- a new workflow/state machine;
- an authorization database;
- STAT5060-specific Bridge code;
- migration of unrelated worktrees;
- release/tag/ref movement.

## Ownership and next step

This is Bridge-owned because the failure crosses repositories and concerns normal Codex execution location, mandatory controller consumption, partial-clone source access, and approval continuity.

Next step:

```text
Planner proposal
-> independent Critic review
-> one bounded implementation/release package
-> real normal-entry regression gates
```

Do not treat the presence of this TODO as implementation authorization.
