# Reviewed Handoff First Remote Publication — Implementation Evidence V2

Task: `reviewed-handoff--first-remote-publication`

Repaired candidate: `9dad0ba4bfa54e251f345091c5151ae991251ec9`

Status: `READY_FOR_PRE_FINAL_CRITIC`

## Repair scope

This V2 evidence supersedes V1 for the repaired candidate only. The V1
candidate and old FP-G6 branch remain historical provenance; they are not reused
as final repaired-candidate evidence.

Changed production surface:

```text
ai_bridge_kit/reviewed_handoff.py
tests/test_reviewed_handoff.py
```

Behavior added inside existing `publish-first` pre-mutation validation:

```text
CURRENT.schema == AI_BRIDGE_REVIEWED_CURRENT_V1
CURRENT.base_branch == main
```

New deterministic zero-mutation negatives:

```text
wrong CURRENT schema -> CURRENT_SCHEMA_MISMATCH
wrong base_branch -> CURRENT_BASE_BRANCH_NOT_MAIN
```

Version remains:

```text
PACKAGE_VERSION=0.9.3
PYPROJECT_VERSION=0.9.3
AI_BRIDGE_KIT_VERSION=0.9.3
```

## Preserved boundaries

```text
DEDICATED_TASK_PUBLISH_FIRST_CLI=UNCHANGED
CALLER_SELECTOR_BOUNDARY=UNCHANGED
RAW_NO_REPLACEMENT_OBJECT_AUTHORITY=UNCHANGED
ACTIVE_GRAFT_FAIL_CLOSED=UNCHANGED
SINGLE_DIRECT_CHILD_AA_REQUEST_CURRENT_FENCE=UNCHANGED
FIXED_EMPTY_EXPECT_LEASE=UNCHANGED
TRANSPORT_FENCES=UNCHANGED
POST_READ_SHA=UNCHANGED
UPSTREAM_SEQUENCING=UNCHANGED
PARTIAL_AMBIGUOUS_FAILURE=UNCHANGED
GENERIC_PUBLISHER=UNCHANGED
BOOTSTRAP_MATERIALIZE_RESUME_WATCHER_AUTHORITY=UNCHANGED
MACHINE_POLICY_DANGEROUS_NEIGHBOR_PROMPTS=UNCHANGED
MACHINE_POLICY_INSTALL_OR_REFRESH=NOT_PERFORMED
FORMAL_RELEASE=NOT_CLAIMED
PRESENTATIONS_F03=NOT_CLOSED
```

## Local deterministic evidence

All commands below were run from
`/home/yuukias/GPT_Codex_AI_Bridge_Kit` on candidate
`9dad0ba4bfa54e251f345091c5151ae991251ec9`.

```text
git diff --check
RESULT=PASS
```

```text
python -m unittest -v \
  tests.test_reviewed_handoff \
  tests.test_host_policy \
  tests.test_reviewed_runner \
  tests.test_repo_cli_compat \
  tests.test_version_parity
RESULT=PASS
TESTS=170
```

```text
python -m unittest discover -v
RESULT=PASS
TESTS=429
```

## GitHub CI evidence

```text
WORKFLOW=Tests
RUN_ID=36532618087
HEAD_SHA=9dad0ba4bfa54e251f345091c5151ae991251ec9
STATUS=completed
CONCLUSION=success
PYTHON_3_X=success
PYTHON_3_9=success
URL=https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/36532618087
```

One earlier same-commit run was cancelled by GitHub superseding behavior and is
not used as positive CI evidence:

```text
RUN_ID=36532617892
CONCLUSION=cancelled
```

## Installed-command evidence

```text
which ai-bridge=/home/yuukias/conda/bin/ai-bridge
ai_bridge_kit.__version__=0.9.3
imported_source=/home/yuukias/GPT_Codex_AI_Bridge_Kit/ai_bridge_kit/__init__.py
imported_source_git_head=9dad0ba4bfa54e251f345091c5151ae991251ec9
publish_first_help=available
host_validate=PASS
```

`ai-bridge host validate --codex-home /home/yuukias/.codex` confirmed:

```text
overall state=configured
trusted ai-bridge executable=/home/yuukias/conda/bin/ai-bridge
ai-bridge reviewed-handoff task publish-first ... => allow
git push -u origin test-branch => prompt
git push --set-upstream origin test-branch => prompt
git push origin test-branch => prompt
git push origin --force main => prompt
git push origin main --force-with-lease => prompt
git push --force-with-lease origin main => prompt
git push origin --delete test-branch => prompt
```

No Machine Policy install or refresh was performed during this repair.
