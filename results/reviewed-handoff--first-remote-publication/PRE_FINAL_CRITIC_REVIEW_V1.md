# Pre-final Critic Review — Reviewed Handoff First Remote Publication v1

Date: **2026-09-29**  
Review stage: **PRE_FINAL_CRITIC**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Task key: **reviewed-handoff--first-remote-publication**

## Reviewed identities

Approved design:

`docs/design/reviewed_handoff_first_remote_publication_plan_v0.4_2026-09-29.md`
@ `cedd6f1dc2c13af7e237fc0ab2c07ba73700472a`

Execution package:

`docs/design/reviewed_handoff_first_remote_publication_execution_package_v0.1_2026-09-29.md`
@ `ee569d5d08233c664ca9dc5c27473ef4f1622779`

Execution-ready Critic PASS:

`docs/design/reviewed_handoff_first_remote_publication_execution_ready_critic_review_v0.1_2026-09-29.md`
@ `ecfd68f7fbc3317ae027c792b7e40a13121970ba`

Final Bridge candidate:

`db258e410a902337a826909f990d4dafb585b615`

Evidence closure:

`c23a6d6753172230df34f3e74b722af0d716df04`

GitHub Tests run:

`36528676064`

Fresh real consumer:

`YuukiAS/AI_Skills_Collection`
branch `reviewed/workflow-core--first-remote-publication-gate`
@ `3faaa9f3be702fdbb7f96ff3eb66d25d574dd227`

## Verdict

```text
RESULT=REVISE
READY_FOR_PRE_FINAL_PASS=NO

BR-FRP-F01=CLOSED
BR-FRP-F02=CLOSED

PRE_FINAL_BLOCKER=BR-FRP-PF-F01
NEW_BLOCKERS=1

FINAL_CANDIDATE=db258e410a902337a826909f990d4dafb585b615
EVIDENCE_CLOSURE_COMMIT=c23a6d6753172230df34f3e74b722af0d716df04

NEXT_HANDOFF=PLANNER
```

## What independently passed

The candidate implements the approved bounded `task publish-first` entry on the
frozen production surface. The implementation keeps caller selection narrow,
uses raw/no-replacement object inspection, rejects active grafts, enforces the
single direct-child metadata-only commit shape, uses the fixed empty-expect
lease, verifies post-read remote SHA, and binds upstream only after successful
remote creation.

The candidate changed only the approved production/docs/test/version surfaces;
`bridge_cli.py`, `cli.py`, `reviewed_runner.py`, generic publisher public
semantics, release ref machinery, and Presentations were not modified.

GitHub Actions run `36528676064` is a real push run for exact candidate
`db258e410a902337a826909f990d4dafb585b615`; both Python 3.x and Python 3.9
jobs completed successfully and each ran 429 tests.

The fresh AI_Skills consumer is independently visible on GitHub. Its remote
branch tip is `3faaa9f3be702fdbb7f96ff3eb66d25d574dd227`, exactly one commit above
base `8d53dbbd8d67615e7ddb0b018f2109a3d8104178`, and the only changed paths are
the task's `REQUEST.md` and `CURRENT.json`. The remote CURRENT is
`PLAN_REQUESTED / RUN_GPT_PLANNER` with `base_branch=main`.

The Bridge `release` ref remains at
`6bbaca5a3af6240fbc88fa54cf78fa9acc147f67`; formal distribution was not
advanced.

## BR-FRP-PF-F01 — first-bootstrap CURRENT identity validation is incomplete

### REQUIREMENT

The frozen design and Acceptance Matrix require the first-publication helper to
validate the first-bootstrap task/base/worktree/state identity before any
remote/config mutation. The frozen FP-G2 negatives explicitly include a wrong
base commit/base branch, and the design requires reuse of the existing
CURRENT schema/parser semantics.

A first publication must therefore not make remotely readable a CURRENT object
that is already invalid under the Reviewed Handoff contract.

### DIRECT EVIDENCE

In final candidate `db258e410a902337a826909f990d4dafb585b615`,
`_validate_publish_first_scope()` validates:

- `task_key`;
- `state=PLAN_REQUESTED`;
- `next_action=RUN_GPT_PLANNER`;
- `review_round=0`;
- `plan_revision=0`;
- `implementation_commit=null`;
- worktree locator;
- `base_commit` syntax/existence and raw-parent equality.

It does **not** validate:

- `CURRENT.base_branch == "main"`;
- `CURRENT.schema == CURRENT_SCHEMA`.

The existing repository `validate_task()` does validate
`CURRENT.schema == CURRENT_SCHEMA`, proving this is an existing task-contract
check rather than a new Critic rule.

The focused publish-first tests likewise have no negative for a wrong
`base_branch` or wrong CURRENT schema, although the frozen Acceptance Matrix
requires wrong base-branch identity to fail.

Consequently a valid bootstrap commit can be amended so that, for example,
`base_branch` becomes `not-main` while all fields currently inspected by
`publish-first` remain acceptable. The helper still reaches its publication
path because the raw parent/tree/path checks are unaffected by that metadata
change.

### CAUSAL RISK

The helper is a permanent Machine Policy allow specifically intended to publish
a valid first Reviewed control-plane handoff without a second user approval.

Publishing a CURRENT with a false base branch or invalid schema creates a remote
Reviewed task that the external Planner / later Review validation or
materialize/resume path cannot reliably consume. In particular, remote-only
resume uses the task's `base_branch` to fetch/validate the frozen base.
Therefore this omission can turn the newly repaired normal entry back into a
broken task requiring manual recovery even though `publish-first` reported
success.

This also makes the recorded `FP_G2=PASS` stronger than the actual candidate:
one of the explicitly frozen task/base identity negatives is not enforced.

### MINIMUM CLOSURE

Do not redesign the architecture.

On the existing `_validate_publish_first_scope()` path, before any network or
config mutation:

1. require `CURRENT.base_branch == "main"`;
2. require the current object to satisfy the existing first-state CURRENT
   schema semantics, at minimum `CURRENT.schema == CURRENT_SCHEMA` (reusing
   existing validation where practical rather than creating a parallel schema);
3. add deterministic zero-mutation negatives for wrong `base_branch` and
   wrong CURRENT schema;
4. keep all already-approved raw-object, lease, transport, upstream and
   ambiguous-publication semantics unchanged.

Because this is a production-source change after final-candidate freeze, freeze
a new exact candidate and rerun the same-candidate evidence required by the
Execution Package. Do not splice the old candidate's final evidence into the
new candidate.

The existing FP-G6 branch cannot become the fresh positive for a modified
candidate. Planner must freeze a new bounded fresh-consumer task identity for
the repaired final candidate, then route that exact amendment through the
existing approval/review contract before Codex executes it.

## Non-blocking observation

`_active_graft_lines()` currently uses leading-and-trailing `strip()`.
Upstream Git's graft parser trims trailing whitespace and treats a line as a
comment only when the first character is `#`. Thus a leading-space
`"  #..."` line is not the same lexical class in Git. This does not provide an
ancestry-spoof bypass because malformed graft data is not registered, so it is
not a separate blocker here. If the repair touches this helper, matching the
frozen lexical semantics with trailing-only trimming would improve contract
fidelity without changing architecture.

## Scope of this review

This REVISE does not reopen `BR-FRP-F01` or `BR-FRP-F02`, does not change the
approved dedicated `publish-first` architecture, does not authorize formal
release, and does not modify Presentations.

The blocker is an implementation/acceptance miss inside the already frozen
FP-G2 identity fence.
