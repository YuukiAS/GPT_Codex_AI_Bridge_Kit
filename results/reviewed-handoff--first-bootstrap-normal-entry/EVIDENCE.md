# Bridge Kit 0.9.1 reviewed first-bootstrap normal entry evidence

Date: 2026-09-24

## Scope

- Task key: `reviewed-handoff--first-bootstrap-normal-entry`
- Bridge repository: `YuukiAS/GPT_Codex_AI_Bridge_Kit`
- Bridge baseline after `git fetch origin main` + fast-forward pull: `e99f17c68bdaa039f1bd1e54b294553a7a7a96fc`
- Consumer repository for the real bootstrap gate: `YuukiAS/AI_Skills_Collection`
- Consumer base observed from `origin/main`: `98b7b875eabedb773f0d1d5bcdcd23217cc9b055`

## Phase 0 preflight

- Bridge `main` was synchronized from `origin/main` before implementation.
- AI_Skills `origin/main` was fetched read-only.
- AI_Skills canonical checkout was not pulled because it had unrelated local state:
  `docs/notes/中文科研长文“说人话 _ 自然重写”的架构决策研究.final.pdf`.
- Target reviewed branch was absent remotely:
  `reviewed/workflow-core--reviewed-first-bootstrap-normal-entry`.
- Target sibling worktree path was absent:
  `/home/yuukias/AI_Skills_Collection-workflow-core--reviewed-first-bootstrap-normal-entry`.

## Pre-recovery Bridge implementation candidate

- Added `ai-bridge reviewed-handoff task bootstrap` as the initial first-bootstrap normal entry.
- The pre-recovery command required exact `--expected-repo`, `--expected-worktree`, `--expected-base-ref`, and `--expected-base-commit`.
- The reviewed branch is fixed to `reviewed/<task_key>` and is not user-selectable.
- First `REQUEST.md` / `CURRENT.json` are created only in the new reviewed worktree, not in canonical main.
- Ordinary `task init` and first bootstrap now share a single initializer.
- `materialize-worktree --mode resume` can recover from remote-only reviewed task metadata after validating remote `REQUEST.md` / `CURRENT.json`.
- Partial local task metadata fails closed with `LOCAL_TASK_METADATA_PARTIAL`.
- The pre-recovery Machine Policy kept `materialize-worktree` on `allow`, but kept first bootstrap on `prompt`.
- Raw `git worktree add` remains on the ordinary approval path.

## Authorization-transport recovery candidate

- Bridge was synchronized to `f0e3175267ef98fadbefe24e31623dcfb88583fe`; drift after `44965d6707d27b48726a967fba46a9d836b7010c` was recovery design/docs only.
- Version remains `0.9.1`.
- `task bootstrap` is now repo-local: the CLI no longer accepts `--target`, `--expected-worktree`, or `--expected-base-ref`.
- Worktree is deterministic: `<cwd-repo-parent>/<cwd-repo-directory-name>-<task_key>`.
- Base is the local post-sync `refs/remotes/origin/main` OID; `--expected-base-commit` is an assertion against that local ref.
- Bootstrap itself performs zero network operations: no `git fetch`, `git ls-remote`, `git push`, or provider call.
- Canonical remote profile is required before mutation:
  configured remotes exactly `origin`; `remote.origin.skipFetchAll` unset/false; `remote.origin.skipDefaultUpdate` unset/false; exactly one `+refs/heads/*:refs/remotes/origin/*` fetch refspec.
- Local `refs/remotes/origin/reviewed/<task_key>` presence fails closed with `REMOTE_TASK_BRANCH_ALREADY_EXISTS`.
- Reachable executable paths fail closed before mutation: `reference-transaction`, `post-checkout`, `post-index-change`, effective `core.hooksPath`, external `filter.*.smudge`, external `filter.*.process`, and external `core.fsmonitor`.
- Task/result output symlink or non-directory redirection fails closed before task state is written.
- Machine Policy recovery changes `task bootstrap` to `allow`, keeps `materialize-worktree` on `allow`, keeps raw `git worktree add` on `prompt`, and keeps `git fetch --all --prune` on `allow`.

## Verification

Focused bootstrap and remote-only resume regression:

```text
python -m unittest \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_creates_exact_first_worktree_without_polluting_main \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_materialize_worktree_remote_only_resume_without_canonical_main_metadata \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_materialize_worktree_local_partial_metadata_fails_closed_before_remote \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_materialize_worktree_resume_uses_remote_task_metadata

OK (4 tests)
```

Syntax check:

```text
python -m py_compile ai_bridge_kit/reviewed_handoff.py ai_bridge_kit/host.py

PASS
```

Focused suites:

```text
python -m unittest tests.test_reviewed_handoff tests.test_host_policy tests.test_version_parity

OK (115 tests)
```

Authorization-transport recovery focused gates:

```text
python -m unittest \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_creates_exact_first_worktree_without_polluting_main \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_rejects_cross_repo_and_stale_base_assertions \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_rejects_noncanonical_remote_profiles \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_uses_post_fetch_local_reviewed_ref_state \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_rejects_reachable_executable_paths \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_rejects_hooks_path_filters_and_fsmonitor \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_rejects_task_output_redirection \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_performs_zero_network_operations \
  tests.test_reviewed_handoff.ReviewedHandoffTests.test_task_bootstrap_cli_rejects_selector_arguments \
  tests.test_host_policy.HostPolicyTests.test_validate_with_real_codex_cli_when_available \
  tests.test_host_policy.HostPolicyTests.test_execpolicy_git_authorization_semantics_with_real_codex_cli_when_available

OK (11 tests)
```

Recovered focused suites:

```text
python -m unittest tests.test_reviewed_handoff tests.test_host_policy tests.test_version_parity

OK (123 tests)
```

Full regression suite:

```text
python -m unittest discover -s tests -p 'test_*.py'

OK (401 tests)
```

Recovered full regression suite:

```text
python -m unittest discover -s tests -p 'test_*.py'

OK (409 tests)
```

Markdown/whitespace check:

```text
git diff --check

PASS
```
