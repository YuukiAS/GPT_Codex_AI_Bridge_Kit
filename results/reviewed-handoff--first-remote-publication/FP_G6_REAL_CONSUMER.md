# FP-G6 Real Consumer Evidence

Bridge final candidate:
`db258e410a902337a826909f990d4dafb585b615`

Installed Bridge executable:
`/home/yuukias/conda/bin/ai-bridge`

## Consumer identity

```text
CONSUMER_REPOSITORY=YuukiAS/AI_Skills_Collection
CANONICAL_CHECKOUT=/home/yuukias/AI_Skills_Collection
TASK_KEY=workflow-core--first-remote-publication-gate
DERIVED_BRANCH=reviewed/workflow-core--first-remote-publication-gate
DERIVED_WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
BASE_ORIGIN_MAIN=8d53dbbd8d67615e7ddb0b018f2109a3d8104178
```

## Preflight

```text
git -C /home/yuukias/AI_Skills_Collection fetch --all --prune
RESULT=PASS
```

Pre-existing canonical checkout state was preserved, not cleaned or switched:

```text
BRANCH=reviewed/stat5060--remove-course-material
UPSTREAM=origin/reviewed/stat5060--remove-course-material [gone]
PRE_EXISTING_UNTRACKED_FILES=3
```

Target absence checks:

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
  --task-key workflow-core--first-remote-publication-gate \
  --expected-repo YuukiAS/AI_Skills_Collection \
  --expected-base-commit 8d53dbbd8d67615e7ddb0b018f2109a3d8104178 \
  --objective "Validate Bridge 0.9.3 Reviewed Handoff first remote publication normal entry on AI_Skills_Collection without modifying production source."
```

Result:

```text
BOOTSTRAP=PASS
CREATED_BRANCH=reviewed/workflow-core--first-remote-publication-gate
CREATED_WORKTREE=/home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
```

Committed files:

```text
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-gate/CURRENT.json
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-gate/REQUEST.md
```

Commit:

```text
FIRST_METADATA_COMMIT=3faaa9f3be702fdbb7f96ff3eb66d25d574dd227
```

## Publish-first

Command:

```bash
ai-bridge reviewed-handoff task publish-first \
  --task-key workflow-core--first-remote-publication-gate \
  --expected-repo YuukiAS/AI_Skills_Collection
```

Result:

```text
STATUS=published
REPO=YuukiAS/AI_Skills_Collection
BRANCH=reviewed/workflow-core--first-remote-publication-gate
PUSHED_OID=3faaa9f3be702fdbb7f96ff3eb66d25d574dd227
DESTINATION=origin/refs/heads/reviewed/workflow-core--first-remote-publication-gate
```

Post-publication verification:

```text
REMOTE_SHA=3faaa9f3be702fdbb7f96ff3eb66d25d574dd227
UPSTREAM_REMOTE=origin
UPSTREAM_MERGE=refs/heads/reviewed/workflow-core--first-remote-publication-gate
WORKTREE_STATUS=clean
REMOTE_TRACKING_SHA=3faaa9f3be702fdbb7f96ff3eb66d25d574dd227
```

Remote-tracking `CURRENT.json`:

```text
schema=AI_BRIDGE_REVIEWED_CURRENT_V1
task_key=workflow-core--first-remote-publication-gate
base_branch=main
base_commit=8d53dbbd8d67615e7ddb0b018f2109a3d8104178
state=PLAN_REQUESTED
next_action=RUN_GPT_PLANNER
review_round=0
plan_revision=0
implementation_commit=null
ci_required=false
```

Remote diff from base:

```text
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-gate/CURRENT.json
A automation/reviewed_handoff/tasks/workflow-core--first-remote-publication-gate/REQUEST.md
```

Non-change boundaries:

```text
CANONICAL_ORIGIN_MAIN=8d53dbbd8d67615e7ddb0b018f2109a3d8104178
CANONICAL_MAIN_TASK_METADATA_CREATED=NO
AI_SKILLS_PRODUCTION_SOURCE_CHANGED=NO
AI_SKILLS_TESTS_CHANGED=NO
AI_SKILLS_RESULTS_CHANGED=NO
AI_SKILLS_VERSION_CHANGED=NO
PRESENTATIONS_CHANGED=NO
RAW_GIT_PUSH_U_USED=NO
REMOTE_BRANCH_DELETED_AS_CLEANUP=NO
```
