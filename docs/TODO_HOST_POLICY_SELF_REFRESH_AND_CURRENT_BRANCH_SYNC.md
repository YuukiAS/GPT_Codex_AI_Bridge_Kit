# TODO — Host Policy Self-Refresh and Current-Branch Sync

Status: READY FOR PLANNER INTAKE / NEXT COHERENT RELEASE (VERSION MUST BE VERIFIED) / NOT IMPLEMENTATION AUTHORIZATION  
Priority: current-branch sync = HIGH; mandatory-rule/load + Host identity preflight = CRITICAL; safe Host recovery = HIGH  
Date: 2026-10-06  
Amended: 2026-10-12 — Lucerna rule-budget and installed-identity regression

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

### Independent reproduction — Lucerna instruction truncation and approval drift (2026-10-08–10-12)

Lucerna's root `AGENTS.md` grew to approximately 54 KiB / 710 lines. A fresh
Codex session reported truncation at 32,768 bytes. Despite the Bridge Lite
validation workflow, the project could retain a present, syntactically valid
`AGENTS.md` that Codex did not fully ingest. The agent then requested human
confirmation to replace the root file even though the user-authored governance
Goal explicitly authorized that exact repository-policy rewrite in an isolated
worktree. Its governance run reported `RULE_LOADING=FAIL`,
`RUNTIME_ENFORCEMENT=FAIL` (filesystem protection passed, desktop/process
isolation did not), and `INDEPENDENT_AUDIT=NOT_RUN`.

Evidence boundaries:

- The observed truncation is a concrete rule-delivery failure; it does **not**
  prove every later behavioral error was caused by truncation. Several relevant
  Lucerna UI/fixture constraints already occurred near the start of the file.
- The repeated `AGENTS.md` confirmation is an observed authority-classification
  error, not proof of a platform-level sandbox approval denial. A Goal entered
  directly by the user is not equivalent to an untrusted repository file that
  merely claims authorization.
- Desktop/process enforcement is a consumer operating-system/Codex sandbox
  boundary. Bridge may detect and report that boundary at preflight, but cannot
  declare it enforced merely by installing written rules or hooks.
- Existing Bridge `validate_workspace()` checks expected file existence,
  protocol/frontmatter shape, etc., but currently does not calculate effective
  project-instruction loading bytes. Existing `host validate` diagnostics
  report several identities but do not provide an end-to-end, task-start
  compatibility guarantee for the active Codex session.
- The repository README currently describes source `0.10.0` as a candidate
  and formal distribution `0.9.3`, while `pyproject.toml` read from the
  remote `release` ref advertises `0.10.0`. This is a **reconciliation
  trigger**, not permission to guess which release reference or documentation
  is authoritative. Verify the actual moving ref, imported package and release
  metadata before rewriting version claims.

**Routing:** These Lucerna regressions are part of Candidate B's existing
Host Policy / task-start readiness / safe recovery work, not a new sixth
product feature or a Lucerna-specific Bridge fork. Candidate A below remains
in scope without widening Git mutation authority.

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


## Recommended coherent release scope (version not frozen)

The original 2026-10-06 recommendation was a narrow `0.10.1` patch for
Candidate A, with self-refresh optional. Lucerna's independent rule-loading
failure changes the readiness priority: **Candidate B must now deliver
preflight detection and an honest, tested recovery contract in the same
convergence package**, even if in-session policy mutation remains unsafe and
is explicitly deferred.

Keep exactly the two existing capability areas:

1. **Candidate A — bounded current-branch sync:** preserve the narrow
   existing-branch, same-name, fast-forward-only contract and its tests.
2. **Candidate B — trustworthy machine/project readiness:** enforce strict
   cumulative AGENTS budget checks; identify effective Host Policy, project
   policy and installed/runtime/release identity; detect drift before substantive
   work; provide either a narrowly safe supported refresh or a one-time external
   update + fresh session + same-Goal resume; validate that distribution/docs
   state is truthfully labeled.

Do not add a standalone `rules-budget` product, daemon, new workflow state
machine, generic privilege bypass or a third authority owner. Planner/Critic
must inspect the actual distributed `release` ref before selecting version:
if `0.10.0` is not yet formally distributed, fold this into its reviewed
closure when appropriate; otherwise evaluate one `0.10.1` patch. Do not bump
a version as a substitute for a complete release gate.

### Candidate A behavioral contract (original 0.10.1 proposal)

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

### Candidate A acceptance evidence

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

Release closure, after the actual target/version is independently verified, should include:

- a coherent package/release version reflecting the selected formal target (no unconditional `0.10.1` bump);
- CHANGELOG entry covering both independent STAT5060 reproductions and the Lucerna rule-loading/Host readiness regression;
- exact-sha CI PASS and relevant fresh-consumer acceptance gates;
- Host Policy validation including the new bounded helper allow rule and Candidate B task-start preflight/recovery contract;
- formal release/distribution closure through the existing Bridge maintainer path.

## Candidate B — task-start policy readiness and bounded recovery

Lucerna raises **detection and recovery** to a required capability. A
self-refresh helper remains an implementation option only if its actual
permission/ownership boundary can be proven safe; do not require self-mutation
of a read-only `CODEX_HOME` merely to award a recovery PASS.

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

Why preflight is now critical:

- A partially ingested instruction set can silently invalidate a normal
  project task long before any optional Host refresh is attempted.
- Host, active `CODEX_HOME`, executable/imported source, installed rules and
  project rules must be checked **before** costly execution, not as a late
  bootstrap surprise.
- A fresh session after a safe, external one-time policy update is an
  acceptable boundary; unsupported running-session hot reload is not.
- Repo-local rule validation and Host validation must have one documented
  composition so a caller cannot mistake one for the other.

### B1. Strict effective project-instruction byte budget

Extend existing `ai-bridge validate --strict` rather than introducing a new
feature/command simply to check rule length.

Required semantics:

1. Resolve the **effective** Codex instruction-discovery behavior for the
   actual `CODEX_HOME`, selected repository/worktree and target current
   working directory. Account for applicable global, ancestor, repository
   root and nested `AGENTS.md` / `AGENTS.override.md` / configured fallback
   names according to the runtime's real precedence, not a hard-coded
   root-only list. Clearly distinguish any global instructions exempt from a
   project-byte cap from instructions counted by that cap.
2. Read `project_doc_max_bytes` from the **effective configuration** when
   available. Default to 32,768 bytes only when that is actually the runtime
   default. Inspect user, project and startup override precedence; if a
   session-only override cannot be observed, disclose the unverifiable part
   instead of asserting exact equivalence with an active session.
3. Measure **bytes actually consumed by Codex**, not Unicode characters,
   Markdown lines or total text in linked reference documents. Treat UTF-8,
   line endings and BOM as bytes in the raw file; verify against native
   ingestion/decoding behavior. A Bridge-managed block is already part of its
   owning AGENTS file and must **not** be added a second time. A separate
   reference file named inside AGENTS does not enter the automatic discovery
   budget unless Codex actually discovers it as an instruction file.
4. Show a per-file ledger: discovered path, precedence, raw/effective bytes,
   cumulative bytes, limit, remaining allowance, any repeated/missing blocks,
   and which instruction segment would be omitted or truncated. Detect
   duplicate Bridge managed markers as a separate malformed-install defect,
   without double counting the same physical file.
5. `--strict` must return a nonzero exit code for confirmed over-budget or
   truncated effective mandatory instructions, not a warning. Non-strict
   diagnostics may warn while preserving existing backward compatibility.
   Unknown runtime semantics must be labeled `UNVERIFIED`, never
   `RULE_LOADING_PASS`.
6. When possible, perform one fresh Codex-session canary on the same
   `CODEX_HOME` and current working directory to prove the actual effective
   instructions are consumed. Static byte success and runtime ingestion success
   must remain separate claims. Do not dump secret tokens or full private
   global instructions into logs.

Positive tests: exact boundary, under-budget with Chinese/multibyte text,
managed block present once, root + nested overrides, configured larger limit,
multiple valid worktrees, and a reference document not auto-counted.

Negative tests: Lucerna-shaped ~54 KiB root on a 32,768-byte limit,
cumulative multi-file overflow even when every individual file is small,
CRLF/BOM/multibyte off-by-one errors, duplicate managed markers,
different effective `CODEX_HOME`, stale project override, changed
working directory, and unknown/unsupported effective config.

### B2. Task-start Host and installed identity compatibility

Before substantive work, provide a low-cost **read-only** preflight that
composes existing `host validate` and project `validate --strict` checks,
without obliging every consumer project to install Controlled Mode.

Bind and report:

- active `CODEX_HOME`, effective config and installed Host managed AGENTS
  block / execpolicy identity, including any mismatched installed template;
- exact `ai-bridge` executable, imported `ai_bridge_kit` location,
  package version and editable-source HEAD/dirty state;
- actual formal moving `release` ref/target, package metadata at that
  target, selected distribution source, and active installed package identity;
- project-side managed block/template generation where installed, and the
  effective AGENTS discovery/budget result from B1;
- required workflow plugin availability where the project declares it, without
  silently installing unrelated optional plugins.

Make distinctions explicit: an intentional source candidate on `main` ahead
of formal `release` is not by itself drift; an active installed package or
Host policy that contradicts the **selected formal target** or declared task
contract is drift. Missing access to a remote release ref is `UNVERIFIED`,
not an invented version match. Never quietly declare the newest `main`
commit to be the formal release.

A stale, incomplete, or incompatible mandatory policy is a task-start blocker
for effects depending on it, while unrelated safe work and preservation of
already completed client artifacts remain permitted.

### B3. One-time update, fresh-session recovery and same-Goal resume

First check if bounded in-sandbox repair of Bridge-owned managed files is
both supported and authorized. If not:

1. Preserve original worktree, task identity, dirty state, checkpoints and
   completed artifacts without reset/clean/branch substitution.
2. Return an exact, bounded external update instruction for the **active**
   `CODEX_HOME`; use the installed trusted Bridge identity, create backups,
   refuse symlink/path redirection and non-managed edits, and validate again.
3. Require a **fresh Codex session** when instructions/config cannot be safely
   hot-reloaded. Resume the same Goal/checkpoint once with unchanged
   authorization, not a new task or repeated user approvals.
4. Run task-start preflight before resuming substantive work. If the session
   cannot establish current identity, report a precise unresolved blocker,
   not `PASS` or an endless retry/escalation loop.

Do not let a stale policy self-authorize shell elevation, arbitrarily mutate
`CODEX_HOME`, install plugins, broaden branch/write permissions or bypass
security review. A helper returning `RELOAD_REQUIRED` is valid when it has
actually performed safe changes; a purely read-only diagnostic must not claim
to have refreshed anything.

### B4. Formal distribution and documentation consistency

Cross-check `README.md`, `CHANGELOG.md`, package metadata,
the canonical `release` ref, installed source/runtime identity and the
machine-sync selection. Present three distinct identities when applicable:
unreleased `main` candidate, formally distributed release, and machine
installed version. If a README claim disagrees with actual formal distribution,
correct the documentation in the *same release closure*; if runtime/distribution
does not match the selected formal release, close that release/installation
gap through its existing owner, not by modifying `release` opportunistically.

`YuukiAS/AI_Skills_Collection` / the existing Bridge release owner retains
formal distribution authority. This TODO alone must not move `release`,
change installed `CODEX_HOME` files or perform a version bump.

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

### Project rules / Host readiness / distribution (Lucerna regression)

- `ai-bridge validate --strict` fails nonzero on the actual Lucerna
  32,768-byte truncation reproduction before substantive execution.
- Repeated Bridge managed markers, root+nested cumulative overflow, UTF-8
  multibyte/CRLF/BOM edges, config overrides and false duplicate counting
  have positive/negative deterministic tests. At least one actual fresh Codex
  loading probe validates the model-visible rule surface where supported.
- A stale machine policy or wrong `CODEX_HOME` is diagnosed at task start
  with true executable/import/source/formal-release/installed identities.
  Intentional `main`-ahead-of-release status is reported correctly.
- One existing-policy recovery passes with backups, validation, fresh-session
  reentry and same-task worktree/resume continuity. A read-only or unsupported
  in-session refresh returns `RELOAD_REQUIRED` / a precise blocker, not
  fake auto-repair.
- A fresh consumer gate demonstrates direct user authorization to update an
  exact `AGENTS.md` does **not** cause a duplicate `HUMAN_ONLY` prompt,
  while task text that merely claims to authorize itself does **not** confer
  authority. Preserve legitimate human gates for security/system mutations.
- README / package version / moving `release` / installed runtime are
  reconciled by actual target identity and reviewable evidence. Do not
  publish a release or change `CODEX_HOME` as part of this TODO.
- The same Lucerna-governance-shaped regression must not touch real Lucerna
  foreground UI, fixture runtime, user processes or private provider data.

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

### Host Policy readiness and safe recovery

Positive:
- stale managed Host Policy is detected before expensive consumer work;
- if bounded in-session refresh is safe and implemented, it updates only exact Bridge-owned managed files from the selected formal release, creates backups and verifies afterward;
- otherwise, one scoped out-of-session update plus a fresh Codex session restores valid Host Policy and resumes the **same** Goal from preserved task state;
- `host validate` and project strict validation pass after recovery; required fresh-session boundaries are reported honestly.

Negative:
- symlink/path redirection or unrelated user-owned file mutation;
- non-current `CODEX_HOME` or mismatched source/formal-release identity;
- arbitrary plugin install/config mutation, shell elevation, unauthorized global writes or refusal-cascade fallback;
- pretending that a read-only diagnostic changed active policy, or that the old session automatically ingested refreshed instructions.

## Non-goals

- no separate sixth Lucerna-only feature, duplicate rule-budget service or
  continuously running preflight daemon;
- no claim that AGENTS text, hooks or passing static preflight enforces
  Windows process/desktop isolation; native negative tests remain necessary
  on the consuming platform;
- no task-wide `BLOCKED` claim merely because a safe/optional identity
  diagnostic or unrelated machine refresh is unavailable;
- no raw Git allow expansion;
- no automatic rebase/autostash;
- no new branch strategy;
- no raw push fallback;
- no generic privileged shell;
- no workflow-core/plugin installation inside Bridge;
- no attempt to eliminate legitimate fresh-session boundaries.
