# FP-G6 Real Consumer Evidence V2

Bridge repaired candidate:
`9dad0ba4bfa54e251f345091c5151ae991251ec9`

Installed Bridge executable:
`/home/yuukias/conda/bin/ai-bridge`

## Consumer identity

```text
CONSUMER_REPOSITORY=YuukiAS/AI_Skills_Collection
CANONICAL_CHECKOUT=/home/yuukias/AI_Skills_Collection
TASK_KEY=workflow-core--first-remote-publication-repair-gate
DERIVED_BRANCH=reviewed/workflow-core--first-remote-publication-repair-gate
DERIVED_WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-repair-gate
BASE_ORIGIN_MAIN=a7028195f3e97d32d51c32ef8c87f658f92048e5
```

## Preflight

```text
git -C /home/yuukias/AI_Skills_Collection fetch --all --prune
RESULT=PASS
ORIGIN_MAIN=a7028195f3e97d32d51c32ef8c87f658f92048e5
```

Pre-existing canonical checkout state was preserved, not cleaned, reset, or
switched:

```text
BRANCH=reviewed/stat5060--remove-course-material
UPSTREAM=origin/reviewed/stat5060--remove-course-material [gone]
PRE_EXISTING_UNTRACKED_FILES=3
```

Target absence checks before bootstrap:

```text
REMOTE_BRANCH_ABSENT=YES
LOCAL_BRANCH_ABSENT=YES
DERIVED_WORKTREE_ABSENT=YES
CANONICAL_MAIN_TASK_METADATA_ABSENT=YES
```

## Bootstrap and commit

Command:

```bash
ai-bridge reviewed-handoff task bootstrap \
  --task-key workflow-core--first-remote-publication-repair-gate \
  --expected-repo YuukiAS/AI_Skills_Collection \
  --expected-base-commit a7028195f3e97d32d51c32ef8c87f658f92048e5 \
  --objective "Validate repaired Bridge 0.9.3 Reviewed Handoff first remote publication normal entry on AI_Skills_Collection without modifying production source."
```

Result:

```text
BOOTSTRAP=PASS
CREATED_BRANCH=reviewed/workflow-core--first-remote-publication-repair-gate
CREATED_WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-repair-gate
```

Committed files:

```text
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-repair-gate/CURRENT.json
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-repair-gate/REQUEST.md
```

Commit:

```text
FIRST_METADATA_COMMIT=ddd2844635abeb585e075fbcc18373c730ce61d1
```

## Publish-first

Command:

```bash
ai-bridge reviewed-handoff task publish-first \
  --task-key workflow-core--first-remote-publication-repair-gate \
  --expected-repo YuukiAS/AI_Skills_Collection
```

Result:

```text
STATUS=published
REPO=YuukiAS/AI_Skills_Collection
BRANCH=reviewed/workflow-core--first-remote-publication-repair-gate
PUSHED_OID=ddd2844635abeb585e075fbcc18373c730ce61d1
DESTINATION=origin/refs/heads/reviewed/workflow-core--first-remote-publication-repair-gate
```

Post-publication verification:

```text
REMOTE_SHA=ddd2844635abeb585e075fbcc18373c730ce61d1
UPSTREAM=origin/reviewed/workflow-core--first-remote-publication-repair-gate
WORKTREE_STATUS=clean
REMOTE_CURRENT_SCHEMA=AI_BRIDGE_REVIEWED_CURRENT_V1
REMOTE_CURRENT_BASE_BRANCH=main
REMOTE_CURRENT_BASE_COMMIT=a7028195f3e97d32d51c32ef8c87f658f92048e5
REMOTE_CURRENT_STATE=PLAN_REQUESTED
REMOTE_CURRENT_NEXT_ACTION=RUN_GPT_PLANNER
REMOTE_CURRENT_REVIEW_ROUND=0
REMOTE_CURRENT_PLAN_REVISION=0
REMOTE_CURRENT_IMPLEMENTATION_COMMIT=null
```

Remote diff from base:

```text
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-repair-gate/CURRENT.json
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-repair-gate/REQUEST.md
```

Non-change boundaries:

```text
CANONICAL_ORIGIN_MAIN=a7028195f3e97d32d51c32ef8c87f658f92048e5
REMOTE_MAIN=a7028195f3e97d32d51c32ef8c87f658f92048e5
CANONICAL_MAIN_TASK_METADATA_CREATED=NO
AI_SKILLS_PRODUCTION_SOURCE_CHANGED=NO
AI_SKILLS_TESTS_CHANGED=NO
AI_SKILLS_RESULTS_CHANGED=NO
AI_SKILLS_VERSION_CHANGED=NO
PRESENTATIONS_CHANGED=NO
RAW_GIT_PUSH_U_USED=NO
RAW_FORCE_WITH_LEASE_USED=NO
REMOTE_BRANCH_DELETED_AS_CLEANUP=NO
```
