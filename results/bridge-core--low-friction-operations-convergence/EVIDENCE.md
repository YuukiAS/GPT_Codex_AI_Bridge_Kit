# Bridge Core 0.9.0 Evidence

Task key: `bridge-core--low-friction-operations-convergence`

## Phase 0

- Canonical checkout: `/home/yuukias/GPT_Codex_AI_Bridge_Kit`
- Branch: `main`
- `HEAD` and `origin/main` after `git fetch origin main`: `8d098bd3351eab9cb5403f2688ff5f53f22f8395`
- Origin fetch/push URL: `https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- Current CODEX_HOME resolved by Bridge: `/home/yuukias/.codex`
- Runtime versions recorded before implementation:
  - Codex: `codex-cli 0.148.0-alpha.9`
  - Git: `git version 2.43.0`
  - GitHub CLI: `gh version 2.97.0 (2026-07-31)`
  - Python: `Python 3.13.5`
- Current `codex execpolicy --help` exposes prefix-rule checking only; no dynamic exact-effect permission primitive was present in the local runtime.

Startup dirty state:

- `AGENTS.md` had one pre-existing 8-line addition for the Bridge formal distribution owner locator. It is within the task-owned README/AGENTS/release-boundary documentation scope and was preserved.

## Local Verification

Focused verification:

```text
python -m unittest tests.test_host_policy tests.test_reviewed_handoff tests.test_persistent_run tests.test_notifier tests.test_bridge_cli_router tests.test_version_parity
```

Result: `Ran 141 tests ... OK`

Full verification:

```text
python -m unittest discover -s tests -p 'test_*.py'
```

Result: `Ran 385 tests ... OK`

Temporary Machine Policy install/validate:

```text
python -m ai_bridge_kit.bridge_cli host install --codex-home <tmp>
python -m ai_bridge_kit.bridge_cli host validate --codex-home <tmp>
```

Result: exit 0. The temporary policy proved:

- `ai-bridge plugin-replay ... => allow`
- `ai-bridge host publish-current-branch ... => allow`
- `ai-bridge reviewed-handoff materialize-worktree ... => allow`
- safe current-scope `gh auth/pr/issue/run ... --` reads => allow
- token display, positional `gh pr view`, `--repo`, and `gh api` => prompt
- raw `git push origin main` => prompt
- dangerous Git, branch topology mutation, shell/Python composition, tmux mutation, process mutation, Slurm mutation => prompt/no-match

Persistent Run progress CLI probe:

```text
python -m ai_bridge_kit.bridge_cli persistent-run progress --evidence <tmp> --stalled-after-seconds 3600
```

Result: emitted `schema=ai-bridge.persistent_run.progress.v1`, `fraction=0.5`, `eta=UNKNOWN`, `status=stalled`, and `semantic_completion_claim=false`.

Plugin inventory:

- `codex plugin list` showed installed/enabled production plugins including `sites@openai-bundled`, `workflow-core@yuukias-ai-skills`, and `ai-skills-core@yuukias-ai-skills`.
- `AI_Skills_Collection/plugins/codex/plugins/ai-skills-core/skills/maint/SKILL.md` currently instructs production evidence to use `ai-bridge plugin-replay --plugin ai-skills-core@yuukias-ai-skills` or the exact installed plugin id.

## Gate Summary

- G1/G2: covered by temporary Machine Policy `host validate` execpolicy matrix and focused tests.
- G3/G4: covered by real disposable bare-remote publication tests plus transport/config/credential/askpass/hook negative tests. Final `origin/main` publication must use the same bounded publisher after commit.
- G5/G6/G7: covered by disposable Reviewed Mode bootstrap/rematerialization tests and wrong/occupied path fail-closed tests.
- G8/G9: plugin-replay remains narrow; current installed plugin inventory and AI_Skills maintainer consumer point to production `plugin-replay`; candidate-plugin-replay remains absent from production CLI.
- G10/G11: covered by Persistent Run normalizer tests and CLI probe.
- G12: covered by Notifications operational-progress tests; progress briefs cannot claim semantic PASS/READY/release completion.
- G13: covered by publisher rejection under `AI_BRIDGE_REVIEWED_RUNNER_PUSH_GUARD`.
- G14: covered by version bump, README/QUICKSTART/CHANGELOG display taxonomy, compatibility-preserving CLI identifiers, and same-candidate test runs.
- G15: no generic shell/Python allow, danger-full-access, auth DB/token store, wrapper registry, new workflow class, mandatory watcher, or generic Host-wide `approval_policy=never` was added. Existing narrow plugin-replay child contract remains tested.

## Post-Commit Closure

- Create final candidate commit.
- Publish `main` to `origin/main` through `ai-bridge host publish-current-branch`.
- Run the authorized live Machine Policy install/validate on `/home/yuukias/.codex`.
- Record the final commit, live install result, and publish verification in the operator final response. These facts are post-commit effects and cannot be self-contained in the same committed artifact without changing that artifact's own commit identity.
