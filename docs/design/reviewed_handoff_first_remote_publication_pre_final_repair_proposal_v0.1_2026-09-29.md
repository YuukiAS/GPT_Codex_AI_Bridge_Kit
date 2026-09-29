# Reviewed Handoff First Remote Publication — Pre-final Repair Proposal v0.1

Date: **2026-09-29**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Target domain: **Reviewed Handoff / Bridge Kit core**  
Task key: **reviewed-handoff--first-remote-publication**  
Review stage: **pre_final_repair_after_critic_v1**  
Status: **READY FOR INDEPENDENT CRITIC REVIEW / NOT REPAIR AUTHORIZATION**

Approved design:

`docs/design/reviewed_handoff_first_remote_publication_plan_v0.4_2026-09-29.md @ cedd6f1dc2c13af7e237fc0ab2c07ba73700472a`

Execution package:

`docs/design/reviewed_handoff_first_remote_publication_execution_package_v0.1_2026-09-29.md @ ee569d5d08233c664ca9dc5c27473ef4f1622779`

Execution-ready Critic PASS:

`docs/design/reviewed_handoff_first_remote_publication_execution_ready_critic_review_v0.1_2026-09-29.md @ ecfd68f7fbc3317ae027c792b7e40a13121970ba`

Prior final candidate:

`db258e410a902337a826909f990d4dafb585b615`

Prior evidence closure:

`c23a6d6753172230df34f3e74b722af0d716df04`

Pre-final Critic review:

`results/reviewed-handoff--first-remote-publication/PRE_FINAL_CRITIC_REVIEW_V1.md @ 64bdc522926e778fe58b7aaeb8bf03758f0e880f`

## 1. Planner disposition

```text
BR-FRP-PF-F01 = ACCEPT
BR-FRP-F01 = CLOSED / NOT REOPENED
BR-FRP-F02 = CLOSED / NOT REOPENED
NEW_ARCHITECTURE = NO
```

The Critic finding is directly supported by current candidate source.

In `_validate_publish_first_scope()`, the candidate validates task key, first state/action, review/plan counters, implementation binding, worktree locator, base commit shape/existence, raw direct parent, exact A/A tree effect, raw blobs, and branch head identity.

It does **not** validate:

```text
CURRENT.schema == CURRENT_SCHEMA
CURRENT.base_branch == "main"
```

The existing `validate_task()` already treats `CURRENT.schema == CURRENT_SCHEMA` as part of the Reviewed task contract. The frozen Acceptance Matrix already includes wrong base-branch identity among FP-G2 negatives.

Therefore `BR-FRP-PF-F01` is an implementation/acceptance miss inside the already-approved FP-G2 identity fence, not a new architecture problem.

## 2. Minimal repair scope

Production change is limited to:

```text
ai_bridge_kit/reviewed_handoff.py
```

Focused test change is limited to:

```text
tests/test_reviewed_handoff.py
```

Execution evidence may create/update only repair evidence under:

```text
results/reviewed-handoff--first-remote-publication/
```

No change is authorized to:

```text
ai_bridge_kit/host.py
ai_bridge_kit/reviewed_runner.py
ai_bridge_kit/bridge_cli.py
ai_bridge_kit/cli.py
templates/host/**
templates/reviewed_handoff/**
AGENTS.md
README.md
CHANGELOG.md
pyproject.toml
ai_bridge_kit/__init__.py
release/tag/ref machinery
Presentations
```

The public CLI and Machine Policy are already correct and must remain byte/behavior compatible except for the repaired helper's stricter pre-mutation validation outcome.

## 3. Exact code repair

Inside the existing first-publication pre-mutation validation path, after parsing the captured first-bootstrap CURRENT and before any network/config mutation, require:

```text
current_payload.get("schema") == CURRENT_SCHEMA
current_payload.get("base_branch") == "main"
```

Recommended fail-closed errors:

```text
CURRENT_SCHEMA_MISMATCH
CURRENT_BASE_BRANCH_NOT_MAIN
```

Equivalent stable error names are acceptable only if tests bind them and no public behavior outside this failure path changes.

Reuse the existing `CURRENT_SCHEMA` constant. Do not add a second schema, registry, state, parser family, or validation database.

Do not call a broad validator if doing so would silently widen first-publication semantics beyond the frozen first-state contract. The minimum repair is the two missing identity checks on the existing path.

## 4. Deterministic blocker regressions

Add two direct negatives to `tests/test_reviewed_handoff.py`.

### PF-R1 — wrong base branch

Start from the existing legal first-publication fixture, modify the committed CURRENT so:

```text
base_branch = "not-main"
```

while preserving the exact single A/A first-bootstrap commit shape.

Expected:

```text
publish-first = FAIL
failure = CURRENT_BASE_BRANCH_NOT_MAIN (or frozen equivalent)
remote/network mutation = NONE
branch upstream config mutation = NONE
```

### PF-R2 — wrong CURRENT schema

Start from the legal fixture, modify the committed CURRENT so:

```text
schema != CURRENT_SCHEMA
```

while preserving the exact single A/A commit shape.

Expected:

```text
publish-first = FAIL
failure = CURRENT_SCHEMA_MISMATCH (or frozen equivalent)
remote/network mutation = NONE
branch upstream config mutation = NONE
```

The test harness must prove no `ls-remote`, push, or branch-upstream config mutation is reached for these two identity failures.

These are additions inside existing FP-G2. Do not create a new Gate.

## 5. Non-blocking graft observation

The Critic's `_active_graft_lines()` lexical observation is explicitly **not** part of `BR-FRP-PF-F01`.

Disposition:

```text
GRAFT_LEXICAL_OBSERVATION = DEFER_NONBLOCKING
```

Do not touch `_active_graft_lines()` in this repair unless the two-field blocker repair unexpectedly requires that helper, which current source does not show.

Reason: changing graft parsing would enlarge the repaired candidate surface and same-candidate revalidation without closing the actual blocker. Existing graft ancestry-spoof protection remains frozen and must simply rerun on the repaired candidate.

## 6. Version decision

Current main is already:

```text
pyproject.toml = 0.9.3
ai_bridge_kit.__version__ = 0.9.3
CHANGELOG = 0.9.3 entry already present
formal release ref = not advanced
```

This repair is part of the same not-yet-formally-released `0.9.3` candidate.

Freeze:

```text
VERSION_BUMP_DECISION = NONE
REPAIRED_CANDIDATE_VERSION = 0.9.3
TARGET_VERSION_CHANGE = NO
README_CHANGE = NO
CHANGELOG_CHANGE = NO
```

Do not create `0.9.4` for this pre-final repair.

If execution observes a version/release drift away from this state, stop for Planner instead of selecting another version.

## 7. Old candidate evidence becomes historical

Once production source changes:

```text
db258e410a902337a826909f990d4dafb585b615
```

is no longer the final candidate.

The following old evidence remains historical only:

- focused/full tests on `db258e...`;
- GitHub CI run `36528676064`;
- old installed identity/Machine Policy evidence;
- FP-G1–FP-G5 old-candidate evidence;
- old FP-G6 task `workflow-core--first-remote-publication-gate`;
- old FP-G6 remote branch tip `3faaa9f3be702fdbb7f96ff3eb66d25d574dd227`.

No old candidate evidence may be spliced into a repaired-candidate PASS.

## 8. Repaired-candidate rerun contract

After the two-field repair, freeze a new exact Bridge candidate commit on `main` at version `0.9.3`.

The repaired candidate must directly rerun:

### 8.1 Focused regression

```bash
python -m unittest -v \
  tests.test_reviewed_handoff \
  tests.test_host_policy \
  tests.test_reviewed_runner \
  tests.test_repo_cli_compat \
  tests.test_version_parity
```

### 8.2 Full regression

```bash
python -m unittest discover -v
```

### 8.3 Real GitHub CI

The exact repaired candidate must receive PASS for the repository Tests workflow on both configured Python jobs.

### 8.4 FP-G1–FP-G5

Rerun the same approved Gate semantics on the repaired candidate:

```text
FP-G1 atomic first-create
FP-G2 full history/raw-object/path/blob/identity bank, including PF-R1/PF-R2
FP-G3 dangerous-neighbor Machine Policy isolation
FP-G4 generic publisher regression
FP-G5 bootstrap/materialize/resume/watcher authority regression
```

All deterministic negative evidence must again prove no forbidden remote/config mutation.

### 8.5 Installed identity / Machine Policy

Bind installed evidence to the repaired commit:

- actual `ai-bridge` executable path;
- actual imported `ai_bridge_kit` source;
- imported source Git HEAD = repaired candidate;
- `ai-bridge host validate` PASS;
- `publish-first` bounded entry = allow;
- raw `git push -u`, raw force-with-lease, arbitrary new branch push = prompt.

Machine Policy source/templates are unchanged by this repair. Therefore **do not reinstall Machine Policy merely to refresh evidence**. Validate the existing installed managed policy against the repaired candidate.

If validation unexpectedly reports policy drift, stop and return Planner/Critic; do not silently reinstall or widen repair scope.

## 9. New fresh FP-G6 identity

The repaired candidate cannot reuse the old FP-G6 task.

Freeze the new one-shot identity:

```text
consumer repo =
YuukiAS/AI_Skills_Collection

canonical checkout =
/home/yuukias/AI_Skills_Collection

task key =
workflow-core--first-remote-publication-repair-gate

derived branch =
reviewed/workflow-core--first-remote-publication-repair-gate

derived worktree =
/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-repair-gate

base =
repair-execution-time post-sync origin/main OID
```

Planning-time GitHub evidence:

```text
exact remote branch search = ABSENT
exact task-key search on AI_Skills main = ABSENT
```

Local branch/worktree/task-metadata absence cannot be inferred from GitHub and must be checked before FP-G6 mutation.

If any exact local/remote/task/worktree conflict is found at execution, stop for Planner/Critic. Do not choose another task identity ad hoc.

## 10. New FP-G6 normal entry

Only after the repaired candidate has:

- focused PASS;
- full PASS;
- exact-candidate GitHub CI PASS;
- FP-G1–FP-G5 PASS;
- installed identity/Host validation bound to the repaired commit;

run the new consumer Gate:

```text
git fetch --all --prune
-> exact task bootstrap
-> exactly one ordinary commit containing only A REQUEST + A CURRENT
-> repaired-candidate task publish-first
-> remote SHA == local captured HEAD
-> exact origin upstream
-> remote REQUEST/CURRENT readable
-> CURRENT.schema == CURRENT_SCHEMA
-> CURRENT.base_branch == main
-> PLAN_REQUESTED / RUN_GPT_PLANNER
```

Allowed AI_Skills mutation is only this exact first-bootstrap control metadata and exact same-name remote branch.

Forbidden:

- AI_Skills production source;
- tests;
- PLAN.md;
- results artifacts;
- version/generated payload;
- Presentations;
- raw `git push -u`;
- manual second first-publication approval;
- remote branch cleanup/delete.

The resulting branch is durable fresh repaired-candidate evidence.

## 11. Repair evidence outputs

Do not overwrite or reinterpret old candidate evidence as repaired evidence.

Write new candidate-bound files:

```text
results/reviewed-handoff--first-remote-publication/IMPLEMENTATION_EVIDENCE_V2.md
results/reviewed-handoff--first-remote-publication/GATE_MATRIX_RESULT_V2.md
results/reviewed-handoff--first-remote-publication/FP_G6_REAL_CONSUMER_V2.md
results/reviewed-handoff--first-remote-publication/FINAL_CANDIDATE_IDENTITY_V2.md
```

Each must name the repaired Bridge commit and version `0.9.3`.

Then stop for a new independent pre-final Critic review. Do not claim formal release complete.

## 12. Repair authorization envelope

After independent Critic PASS, the user's exact bounded repair authorization may cover only:

### Bridge

```text
repo = YuukiAS/GPT_Codex_AI_Bridge_Kit
branch = main
worktree = /home/yuukias/GPT_Codex_AI_Bridge_Kit
production file = ai_bridge_kit/reviewed_handoff.py
focused test file = tests/test_reviewed_handoff.py
repair evidence = results/reviewed-handoff--first-remote-publication/*V2.md
version = stay 0.9.3
```

Allowed:

- two identity checks;
- two deterministic negatives;
- focused/full tests;
- ordinary task commit;
- existing bounded main publication;
- GitHub CI;
- FP-G1–FP-G5 rerun;
- installed identity / Host validation read/validation;
- exact new FP-G6 consumer task and `publish-first`.

Not authorized:

- other production files;
- Machine Policy install/mutation;
- version bump;
- raw push/force/delete/tag/ref;
- formal release;
- Presentations;
- provider/credential/paid API changes;
- architecture expansion.

## 13. Recovery boundary

### Bridge repair

If the two checks/tests cannot close the blocker without touching another production subsystem, stop for Planner/Critic.

If focused/full/CI fails for an implementation defect inside this exact repair, repair only within the approved two-file surface and freeze a new candidate; rerun all affected same-candidate evidence.

### Installed policy evidence

If Host validation fails because the installed managed policy no longer matches the unchanged candidate policy, stop. Do not reinstall under this repair authorization.

### Fresh FP-G6

If bootstrap fails before mutation, preserve evidence and stop.

If bootstrap creates partial local state, use existing approved bootstrap invocation-local recovery only; no raw Git fallback.

If `publish-first` is partial or ambiguous, preserve exact state and stop. Do not delete the remote branch or silently choose another fresh task.

A consumed/ambiguous FP-G6 identity is not reusable as a fresh positive.

## 14. Presentations and release boundary

Keep:

```text
PRES-S1-ER-F03 = STILL_OPEN
READY_FOR_CODEX = NO
PRESENTATIONS_MUTATION = NO
FORMAL_RELEASE = NO
RELEASE_REF_ADVANCEMENT = NO
TAG = NO
```

Only a new repaired-candidate pre-final PASS can advance this Bridge task toward formal closure. Presentations remains a later narrow F03 re-review.

## 15. Planner result

```text
PLANNER_DISPOSITION=ACCEPT

BLOCKER=BR-FRP-PF-F01

REPAIR_ARCHITECTURE_CHANGE=NO
PRODUCTION_SCOPE=ai_bridge_kit/reviewed_handoff.py
TEST_SCOPE=tests/test_reviewed_handoff.py

REPAIR_CHECKS=
CURRENT.schema == CURRENT_SCHEMA
CURRENT.base_branch == main

VERSION=0.9.3_UNCHANGED

OLD_CANDIDATE=db258e410a902337a826909f990d4dafb585b615
OLD_FP_G6=HISTORICAL_ONLY

NEW_FP_G6_TASK=workflow-core--first-remote-publication-repair-gate
NEW_FP_G6_BRANCH=reviewed/workflow-core--first-remote-publication-repair-gate
NEW_FP_G6_REMOTE_AT_PLANNING=ABSENT

MACHINE_POLICY_REINSTALL=NO
FORMAL_RELEASE=NO
PRESENTATIONS_MUTATION=NO

REPAIR_AUTHORIZED=NO
NEXT_HANDOFF=CRITIC
```
