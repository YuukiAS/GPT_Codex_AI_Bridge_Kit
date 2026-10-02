# Bridge 0.10.0 Execution Reliability Closure - Gate Matrix

Task: `bridge-core--execution-reliability-closure`

`FINAL_SOURCE_CANDIDATE`: `9db19b0409816c22042a246b35a33e1d34fedd0a`

## Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| `ER-G1` sandbox-first ordinary execution | `PASS` | Fresh normal Codex child launched under candidate PATH/Machine Policy and continued ordinary task execution after the optional launcher-layer decline. |
| `ER-G2` refusal classification | `PASS` | The optional `tmux new-session` request was declined by the launcher approval layer and was not counted as a genuine ER-G8 refusal; no workaround or retry was attempted. |
| `ER-G3` ambient `SSH_ASKPASS` existing-branch publication | `PASS` | AI_Skills publication used bounded `ai-bridge host publish-current-branch --expected-repo YuukiAS/AI_Skills_Collection --expected-branch main`; remote `main` verified at the exact local commit. |
| `ER-G4` config/credential/transport matrix | `PASS` | Stage A deterministic matrix remains valid for the same source candidate. |
| `ER-G5` bounded failure preserves work | `PASS` | Launcher-layer decline remained scoped to the optional probe; required work, commit, publication, child exit evidence, and CODEX_HOME restore all completed without widening to raw operations. |
| `ER-G6` runtime identity truth | `PASS` | Exact editable candidate source, candidate executable, `ai-bridge where`, import source/version, direct_url metadata, runtime template lookup, host_executable pin, and `host validate` all bound to the exact candidate. |
| `ER-G7` released behavior regression | `PASS` | Stage A focused/full/CI regression evidence remains valid; Stage B did not modify production source or rerun Stage A. |
| `ER-G8` one fresh normal Codex child refusal/continuation/publish probe | `PASS_WITH_OPTIONAL_PROBE_LAUNCHER_DECLINED` | Fresh child exit code `0`; optional probe attempted exactly once and declined by launcher; required one-result-file consumer committed and published. |

## Stage A Frozen Evidence

```text
FOCUSED_TESTS=PASS
FULL_TESTS=PASS
GITHUB_CI=PASS
SOURCE_PUBLISH_RESULT=published
SOURCE_CANDIDATE=9db19b0409816c22042a246b35a33e1d34fedd0a
```

Stage A was not rerun during the editable-install recovery.

## Stage B Live Evidence

```text
AFFECTED_CODEX_VERSION=codex-cli 0.142.0
AFFECTED_CODEX_HOME=/users/a/e/aereinh/.codex
CANDIDATE_EXECUTABLE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
CANDIDATE_IMPORT_SOURCE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source/ai_bridge_kit/__init__.py
HOST_VALIDATE_RESULT=PASS
CONSUMER_REPO=YuukiAS/AI_Skills_Collection
CONSUMER_BRANCH=main
CONSUMER_WORKTREE=/users/a/e/aereinh/.ai-bridge/er-g8/AI_Skills_Collection
CONSUMER_PRE_HEAD=72f43c4ec43970ec02f497a2c01dcd54068b508c
CONSUMER_FINAL_HEAD=06d6bd79ddb32c32410b58a521829f74e155db14
CONSUMER_REMOTE_SHA=06d6bd79ddb32c32410b58a521829f74e155db14
REFUSAL_EVENT_RESULT=OPTIONAL_PROBE_DECLINED_BY_LAUNCHER_APPROVAL_LAYER
RESTORE_RESULT=PASS_HASH_MATCH
```

## Status

```text
RESULT=PASS_WITH_OPTIONAL_PROBE_LAUNCHER_DECLINED
READY_FOR_PRE_FINAL_CRITIC=YES
GOAL_ACHIEVED=NO
COMPLETE=NO
DEPENDENT_EXECUTION_BLOCKED=NO
FORMAL_RELEASE_DONE=NO
RELEASE_REF_ADVANCED=NO
CODEX_CLI_UPGRADED=NO
```

This stops at the requested `READY_FOR_PRE_FINAL_CRITIC` boundary.
