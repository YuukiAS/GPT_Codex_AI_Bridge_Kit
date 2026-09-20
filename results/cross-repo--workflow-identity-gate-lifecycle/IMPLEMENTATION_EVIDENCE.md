# Workflow Identity And Gate Lifecycle Evidence

Task key: `cross-repo--workflow-identity-gate-lifecycle`  
Human label: 工作流命名与插件回归机制完善（AI_Skills + Bridge）  
Production candidate commit: `7f2707dd4020951650d561303c82a17e22b27317`  
Branch: `reviewed/cross-repo--workflow-identity-gate-lifecycle`

## Remote Identity Gate

- Bridge remote identity was checked before branch/worktree creation.
- `origin` fetch/push URL: `https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- Baseline `origin/main`: `afb2414`

## Local Validation

- `python -m unittest tests.test_reviewed_handoff tests.test_reviewed_runner` -> PASS, 105 tests after semantic task-key changes.
- `python -m unittest tests.test_repo_cli_compat` -> PASS, 6 tests after standalone-validator regression coverage was added.
- `python -m unittest tests.test_reviewed_handoff tests.test_reviewed_runner tests.test_repo_cli_compat tests.test_upfront_authorization_persistent_authoring` -> PASS, 120 tests.
- `python -m unittest discover -s tests` -> PASS, 369 tests.

## Critic R1 Repair

Closed blocker: `C-WIGL-I1-STANDALONE-VALIDATOR-SHADOWING`.

- `scripts/validate_handoff_workspace.py` no longer shadows the imported `ai_bridge_kit.task_keys` module with a local `task_keys` set.
- The standalone script now prepends the current checkout root to `sys.path`, so direct execution validates the task branch implementation rather than an unrelated installed package.
- `tests/test_repo_cli_compat.py` now executes `scripts/validate_handoff_workspace.py` as a standalone subprocess for both semantic-plus-existing-legacy PASS and malformed semantic FAIL.

Standalone smoke with a temporary initialized workspace:

- `repo--feature.md` plus existing legacy `001_legacy.md` -> exit code 0; `PASSED: 0 errors, 0 warning(s)`; no traceback.
- malformed `repo---feature.md` -> exit code 1 with `filename task_key must be either legacy <id>_<1-3-word_slug> or semantic <scope-token>--<goal-token>`; no traceback.

## CLI Smoke

Fixture target: initialized temporary project with Lite plus Reviewed Handoff installed.

- `reviewed-handoff task init --task-key repo--feature` -> PASS.
- `reviewed-handoff task init --task-key 001_feature` -> rejected with exit code 2 and no traceback.
- Repeating `reviewed-handoff task init --task-key repo--feature` -> collision rejected with exit code 2 and no traceback.
- Manually seeded existing legacy task/result `001_legacy` plus semantic `repo--feature` -> `reviewed-handoff validate` PASS.
- Lite workspace with `prompts/tasks/repo--lite.md` and `prompts/tasks/001_legacy.md` -> `ai-bridge validate` PASS.

This evidence covers new semantic task creation, legacy read/validate compatibility, collision handling, user-facing CLI error behavior, and normal Lite validation.
