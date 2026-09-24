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

## Bridge implementation candidate

- Added `ai-bridge reviewed-handoff task bootstrap` as the first-bootstrap normal entry.
- The command requires exact `--expected-repo`, `--expected-worktree`, `--expected-base-ref`, and `--expected-base-commit`.
- The reviewed branch is fixed to `reviewed/<task_key>` and is not user-selectable.
- First `REQUEST.md` / `CURRENT.json` are created only in the new reviewed worktree, not in canonical main.
- Ordinary `task init` and first bootstrap now share a single initializer.
- `materialize-worktree --mode resume` can recover from remote-only reviewed task metadata after validating remote `REQUEST.md` / `CURRENT.json`.
- Partial local task metadata fails closed with `LOCAL_TASK_METADATA_PARTIAL`.
- Machine Policy keeps `materialize-worktree` on `allow`, but keeps first bootstrap on `prompt`.
- Raw `git worktree add` remains on the ordinary approval path.

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

Full regression suite:

```text
python -m unittest discover -s tests -p 'test_*.py'

OK (401 tests)
```

Markdown/whitespace check:

```text
git diff --check

PASS
```
