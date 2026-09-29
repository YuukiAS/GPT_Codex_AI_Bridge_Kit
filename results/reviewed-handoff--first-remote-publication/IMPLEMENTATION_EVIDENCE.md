# Reviewed Handoff First Remote Publication — Implementation Evidence

Task: `reviewed-handoff--first-remote-publication`

Final candidate: `db258e410a902337a826909f990d4dafb585b615`

## Implemented surface

- Added `ai-bridge reviewed-handoff task publish-first --task-key <semantic-task-key> --expected-repo <owner/repo>`.
- The caller cannot select remote, target worktree, branch, destination, source,
  refspec, lease, force behavior, expected OID, upstream, or transport.
- The helper derives:
  - branch: `reviewed/<task_key>`;
  - destination: `refs/heads/reviewed/<task_key>`;
  - source: captured raw HEAD OID;
  - remote: `origin`.
- It validates raw Git object/history/tree/blob state with
  `git --no-replace-objects`.
- Any active non-comment/nonblank `info/grafts` exits the trusted path before
  remote/config mutation.
- It requires the raw HEAD to be exactly one direct child of
  `CURRENT.base_commit`, with the only raw tree effect:
  - `A automation/reviewed_handoff/tasks/<task_key>/REQUEST.md`;
  - `A automation/reviewed_handoff/tasks/<task_key>/CURRENT.json`.
- It requires `CURRENT.state=PLAN_REQUESTED`,
  `CURRENT.next_action=RUN_GPT_PLANNER`, `review_round=0`,
  `plan_revision=0`, and `implementation_commit=null`.
- It performs final pre-mutation rechecks, then publishes with fixed empty
  expected lease:
  `--force-with-lease=refs/heads/reviewed/<task_key>:` .
- It binds local upstream only after push success and post-read remote SHA
  equality.

## Preserved boundaries

```text
GENERIC_HOST_PUBLISH_CURRENT_BRANCH_PUBLIC_SEMANTICS=UNCHANGED
BOOTSTRAP_ZERO_NETWORK=UNCHANGED
MATERIALIZE_RESUME_AUTHORITY=UNCHANGED
REVIEWED_RUNNER_WATCHER_PUBLICATION_AUTHORITY=UNCHANGED
BRIDGE_CLI_TOP_LEVEL_ROUTING=UNCHANGED
RELEASE_REF_OR_TAG=UNCHANGED
PRESENTATIONS=UNCHANGED
RAW_GIT_PUSH_U=ordinary approval
RAW_FORCE_WITH_LEASE=ordinary approval
SSH_SCP_CUSTOM_TRANSPORT=ordinary approval
```

## Local deterministic evidence

All commands were run from `/home/yuukias/GPT_Codex_AI_Bridge_Kit` at candidate
`db258e410a902337a826909f990d4dafb585b615`.

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
RUN_ID=36528676064
HEAD_SHA=db258e410a902337a826909f990d4dafb585b615
STATUS=completed
CONCLUSION=success
PYTHON_3_X=success
PYTHON_3_9=success
```

## Installed-command evidence

```text
which ai-bridge=/home/yuukias/conda/bin/ai-bridge
ai_bridge_kit.__version__=0.9.3
imported_source=/home/yuukias/GPT_Codex_AI_Bridge_Kit/ai_bridge_kit/__init__.py
imported_source_git_head=db258e410a902337a826909f990d4dafb585b615
publish_first_help=available
host_validate=PASS
```
