# Workflow Identity And Gate Lifecycle Evidence

Task key: `cross-repo--workflow-identity-gate-lifecycle`  
Human label: 工作流命名与插件回归机制完善（AI_Skills + Bridge）  
Production candidate commit: `2a842371c35769ce7694c642fde852df57de6679`  
Branch: `reviewed/cross-repo--workflow-identity-gate-lifecycle`

## Remote Identity Gate

- Bridge remote identity was checked before branch/worktree creation.
- `origin` fetch/push URL: `https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- Baseline `origin/main`: `afb2414`

## Local Validation

- `python -m unittest tests.test_reviewed_handoff tests.test_reviewed_runner` -> PASS, 105 tests after semantic task-key changes.
- `python -m unittest tests.test_repo_cli_compat` -> PASS, 4 tests.
- `python -m unittest tests.test_reviewed_handoff tests.test_reviewed_runner tests.test_repo_cli_compat tests.test_upfront_authorization_persistent_authoring` -> PASS, 118 tests.
- `python -m unittest discover -s tests` -> PASS, 367 tests.

## CLI Smoke

Fixture target: initialized temporary project with Lite plus Reviewed Handoff installed.

- `reviewed-handoff task init --task-key repo--feature` -> PASS.
- `reviewed-handoff task init --task-key 001_feature` -> rejected with exit code 2 and no traceback.
- Repeating `reviewed-handoff task init --task-key repo--feature` -> collision rejected with exit code 2 and no traceback.
- Manually seeded existing legacy task/result `001_legacy` plus semantic `repo--feature` -> `reviewed-handoff validate` PASS.
- Lite workspace with `prompts/tasks/repo--lite.md` and `prompts/tasks/001_legacy.md` -> `ai-bridge validate` PASS.

This evidence covers new semantic task creation, legacy read/validate compatibility, collision handling, user-facing CLI error behavior, and normal Lite validation.
