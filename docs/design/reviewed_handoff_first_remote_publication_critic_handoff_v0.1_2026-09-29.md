# Critic Handoff — Reviewed Handoff 首次远端发布 v0.1

**Status:** READY FOR INDEPENDENT CRITIC REVIEW / DESIGN ONLY  
**Date:** 2026-09-29  
**Target repo:** \`YuukiAS/GPT_Codex_AI_Bridge_Kit\`  
**Target domain:** Reviewed Handoff / Bridge Kit core  
**Design topic / task key:** \`reviewed-handoff--first-remote-publication\`  
**Source branch/ref:** \`main\`  
**Current Bridge main bound for this handoff:** \`54bf116c38638753a0579b5f18c19fc6c0239fd6\`

## 1. Proposal under review

Canonical proposal:

\`docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md\`

Review the current file as present at:

\`54bf116c38638753a0579b5f18c19fc6c0239fd6\`

The plan header retains the earlier source baseline \`23e921e...\`; the current file was later localized without changing the selected architecture. Use current \`main\` source as implementation reality.

Trigger evidence:

\`docs/TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md\`

Current dependent consumer blocker:

\`YuukiAS/AI_Skills_Collection\`

\`results/presentations--stage1-front-door-two-template-foundation/CRITIC_EXECUTION_READY_REVIEW_V2.md @ 9a656214b61206221d8d93c19f67488e43d842c5\`

There:

\`PRES-S1-ER-F03 = STILL_OPEN\`

because Presentations can first-bootstrap locally but cannot legally publish first \`REQUEST/CURRENT\` through the current bounded normal entry.

No implementation branch/worktree exists for this Bridge task. No execution package is approved. No implementation is authorized.

---

## 2. Required governance reads

Before judging, read latest \`YuukiAS/AI_Skills_Collection main\`:

- \`docs/workflows/PLANNER_ROLE_CONTRACT.md\`
- \`docs/workflows/CRITIC_ROLE_CONTRACT.md\`
- \`docs/workflows/PLUGIN_CAPABILITY_GATE_POLICY.md\` as a gate-design reference where applicable

Then read latest Bridge \`main\`:

- \`AGENTS.md\`
- \`docs/TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md\`
- \`docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md\`
- current \`ai_bridge_kit/reviewed_handoff.py\`
- current \`ai_bridge_kit/host.py\`
- current CLI route sufficient to confirm production commands
- \`templates/host/rules/ai-bridge-global.rules\`
- \`templates/host/GLOBAL_AGENTS_SNIPPET.md\`
- relevant existing publisher/bootstrap/materializer tests
- current version/release policy if your verdict depends on release classification

Do not infer current behavior from old Bridge design docs when current production source differs.

---

## 3. Direct facts already verified by Planner

Independently re-check these against source.

### Current generic publisher

Current \`host publish-current-branch\` requires before publication:

- current branch equals caller \`expected_branch\`;
- \`branch.<branch>.remote = origin\`;
- \`branch.<branch>.merge = refs/heads/<branch>\`;
- same-name remote branch already exists;
- remote commit is ancestor of current HEAD;
- canonical HTTPS repo/push identity;
- no mirror, follow-tags, recurse-submodules, push options, signing, repo credential helper, active pre-push hook, process transport override.

Therefore a brand-new Reviewed branch with no upstream and no remote ref fails before push, currently observed as:

\`UPSTREAM_REMOTE_MISMATCH\`

and would next fail \`REMOTE_SAME_NAME_BRANCH_REQUIRED\`.

### Current bootstrap

\`reviewed-handoff task bootstrap\` correctly:
- derives only \`reviewed/<task_key>\`;
- derives the deterministic sibling worktree;
- validates current repo/base identity;
- creates first \`REQUEST/CURRENT\` locally;
- deliberately performs zero remote publication.

Do not undo that zero-network bootstrap boundary without a stronger reason.

### Current Machine Policy

Current bounded allow entries exist for:
- \`host publish-current-branch\`;
- \`reviewed-handoff materialize-worktree\`;
- \`reviewed-handoff task bootstrap\`.

Raw \`git push -u\` / \`--set-upstream\`, arbitrary branch creation, force and delete remain gated.

### Current proposed command is design-only

The proposal:

\`ai-bridge reviewed-handoff task publish-first --task-key <task> --expected-repo <owner/repo>\`

does **not** yet exist in production source.

---

## 4. User requirement / product goal

The user has already decided the behavior needed:

> Once an exact Reviewed task, derived branch and sibling worktree have been authorized by the current-user Kickoff, the first ordinary non-force publication of that same exact Reviewed branch must be able to occur through the normal Bridge path without asking the user a second time for the same effect.

The missing normal path currently blocks the generic chronology:

\`\`\`text
approved exact Kickoff
-> local Reviewed task bootstrap
-> first task-owned REQUEST/CURRENT commit
-> exact same-name first remote publication
-> external Planner can read task
-> task-local PLAN_FROZEN
-> normal Reviewed execution
\`\`\`

This is a Bridge generic capability gap. Do not solve it in Presentations or another consumer.

---

## 5. Selected architecture to review

The Plan selects a dedicated narrow action under existing Reviewed Handoff:

\`\`\`text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
\`\`\`

Caller does **not** select:
- branch;
- remote;
- destination ref;
- upstream;
- transport;
- refspec;
- force;
- tag;
- delete;
- mirror;
- push option.

The action derives the exact branch only as:

\`reviewed/<task_key>\`

and acts only from the task's frozen Reviewed sibling worktree.

The Plan explicitly rejects:

1. adding network publication inside \`task bootstrap\`;
2. widening generic \`publish-current-branch\` into a first-branch creator;
3. consumer-local Git wrappers;
4. raw \`git push -u\`;
5. new authorization storage/state/workflow.

---

## 6. Safety contract to review

Before any remote mutation, \`publish-first\` must prove:

1. current cwd is exactly the task-frozen Reviewed sibling worktree;
2. repo identity equals \`--expected-repo\`;
3. task key is valid and branch derives exactly \`reviewed/<task_key>\`;
4. \`REQUEST.md\` and \`CURRENT.json\` exist in the committed tree and agree on task/base/worktree identity;
5. current branch equals the derived branch;
6. task is still at the first handoff state \`PLAN_REQUESTED / RUN_GPT_PLANNER\`;
7. worktree is clean;
8. HEAD descends from the frozen base;
9. canonical origin/HTTPS fetch+push identity and existing transport/config/hook/environment fences pass;
10. fresh exact remote read proves the same-name remote branch is absent;
11. initial upstream config is absent;
12. only deterministic same-name \`origin\` upstream may be established;
13. only exact non-force refspec from captured local HEAD to
    \`refs/heads/reviewed/<task_key>\` may be used;
14. before push, repo/branch/HEAD/remote/config are rechecked;
15. after push, the exact remote ref is re-read and must equal captured local HEAD.

Never permit:
- arbitrary branch/refspec;
- leading \`+\`;
- force/force-with-lease;
- tag/delete/mirror;
- extra refspec;
- remote remap;
- alternate upstream;
- caller-selected transport;
- signed/push-option expansion.

If remote publication result is ambiguous, do not retry blindly and do not delete a possibly-created remote ref.

---

## 7. Residual race / partial-failure question

Independently judge the Plan's handling of the race:

\`\`\`text
ls-remote confirms branch absent
-> time gap
-> ordinary non-force push
\`\`\`

Official Git semantics confirm branch creation is allowed by an exact branch refspec, while ordinary non-force updates do not authorize rewriting an existing divergent branch.

The Plan deliberately does **not** use \`--force-with-lease\` or provider API.

Review whether:

- exact absent precheck;
- non-force exact refspec;
- post-push exact remote-SHA readback;
- fail-closed partial/ambiguous state

are sufficient for this bounded first-publication action.

If not sufficient, give the minimum safer mechanism without broadening force/API/authorization unnecessarily.

---

## 8. Authorization / Machine Policy question

The Plan proposes making only this mechanically-bounded command a Host Machine Policy allow action so an already-approved exact Reviewed Kickoff does not trigger a second approval.

Review whether this is safe given:
- the helper itself derives/fences the only possible branch effect from task artifacts/current repo;
- raw \`git push -u\` remains gated;
- arbitrary remote branch creation remains impossible through the helper;
- no authorization token/database/receipt is added.

Do not require a second user approval merely because the remote branch did not exist yet if the helper can mechanically prove it is the exact already-authorized Reviewed task effect.

Conversely, if the proposed helper is not mechanically narrow enough to justify an allow rule, identify the exact missing fence.

---

## 9. Capability / acceptance gates

Review FP-G1 through FP-G6 as one release-critical set.

### FP-G1 — first publication positive

A brand-new Reviewed task through normal entry must prove:

\`\`\`text
bootstrap
-> first task-owned commit
-> publish-first
-> exact same-name remote Reviewed branch exists
-> remote SHA == captured local HEAD
-> same-name origin upstream established
-> no second user approval for the already-authorized exact effect
\`\`\`

### FP-G2 — fail closed

Before remote mutation, fail for:
- wrong repo;
- wrong task;
- wrong branch/worktree;
- wrong state;
- dirty tree;
- task metadata absent/uncommitted;
- wrong base/lineage;
- noncanonical remote/fetch/push/transport/config/hook/environment;
- any already-existing same-name remote branch.

### FP-G3 — dangerous neighbors remain gated

The new command must not allow:
- raw first push;
- arbitrary new branch;
- force / force-with-lease;
- tag;
- delete;
- mirror;
- custom refspec;
- remote remap;
- alternate upstream.

### FP-G4 — existing publisher unchanged

\`host publish-current-branch\` remains an existing-branch updater with current positive/negative behavior.

### FP-G5 — resume unchanged

Local and remote-only \`materialize-worktree --mode resume\` remain unchanged.

### FP-G6 — real fresh consumer

After deterministic fixtures pass, use a **new** real Reviewed task in a real consumer repo to prove the normal entry. Do not count the already manually-published Product UI Copy task as fresh validation.

The design round itself must not create that consumer task.

---

## 10. Alternative / overengineering check

Explicitly compare:

A. publish inside bootstrap  
B. dedicated \`reviewed-handoff task publish-first\`  
C. widen generic \`host publish-current-branch\`  
D. leave manual second approval/raw push

Judge whether the selected B is the minimum reusable capability.

Do not introduce:
- authorization DB;
- new workflow/state machine;
- watcher/controller;
- generic Git facade;
- consumer-specific wrapper.

---

## 11. External targeted check

Do a small independent external verification against official sources.

At minimum check current official Git documentation for:
- explicit refspec branch creation;
- non-force branch update safety;
- upstream/tracking semantics.

A suitable source is:
- https://git-scm.com/docs/git-push

Optionally verify GitHub push behavior from official GitHub docs if useful.

Do not perform open-ended research.

---

## 12. Presentations dependency boundary

The dependent Presentations Stage 1 package remains frozen:

\`results/presentations--stage1-front-door-two-template-foundation/EXECUTION_PACKAGE_V1_1.md @ 049847f4638bb339229c748d3b8f97bd41fae72d\`

Its current blocker is:

\`PRES-S1-ER-F03\`

Do not redesign Presentations in this review.

If Bridge design PASSes, next handoff is **back to Bridge Planner** to prepare one Bridge execution package. Presentations remains waiting until the generic Bridge capability is actually implemented, tested, and available on the execution machine.

If the final implemented command fits Presentations v1.1's generic phrase “current authorized bounded publication route,” no mechanical Presentations v1.2 should be required.

If actual command/semantics later require an explicit new command in the Presentations Kickoff, that is a later narrow Presentations package amendment after Bridge implementation.

---

## 13. Expected verdict

First give a concise user-readable design judgment.

Then:

\`\`\`text
RESULT = PASS | REVISE
REVIEW_STAGE = BRIDGE_FIRST_REMOTE_PUBLICATION_DESIGN

REVIEWED_PLAN =
docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md

REVIEWED_PLAN_COMMIT =
54bf116c38638753a0579b5f18c19fc6c0239fd6

TASK_KEY =
reviewed-handoff--first-remote-publication

ROOT_CAUSE_VERDICT = ...
SELECTED_ARCHITECTURE_VERDICT = ...
AUTHORIZATION_BOUNDARY_VERDICT = ...
REMOTE_RACE_VERDICT = ...
FP_GATE_VERDICT = ...
OVERENGINEERING_VERDICT = ...
PRESENTATIONS_DEPENDENCY_VERDICT = ...

READY_FOR_BRIDGE_EXECUTION_PACKAGE = YES | NO
\`\`\`

### If REVISE

Use stable finding IDs and include:
- requirement;
- direct evidence;
- causal risk;
- minimum closure.

Then automatically return a complete prompt to the Bridge Planner thread under the Planner–Critic contract.

### If PASS

State clearly:
- PASS approves only Bridge design v0.1;
- it does not authorize implementation, branch/worktree creation, Machine Policy mutation, installation or release;
- next step is Planner preparation of a Bridge Proposal/Plan-derived execution package + Canonical Goal + Kickoff Draft;
- that complete execution package must receive execution-ready Critic PASS before Codex execution;
- do not yet return to Presentations F03 re-review because the production capability is not implemented.

Then automatically return the complete next Bridge Planner prompt.
