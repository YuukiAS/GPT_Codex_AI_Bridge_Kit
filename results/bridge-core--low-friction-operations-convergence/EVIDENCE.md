# Bridge Core 0.9.0 Recovery Evidence

Task key: `bridge-core--low-friction-operations-convergence`

Status: `RECOVERY_IMPLEMENTED_PARTIAL_FINAL_GATES`

This file supersedes the pre-final evidence from baseline
`88fa67c44e6e491ed548f033ce0d3c33f63525c4`. That baseline was useful
implementation provenance, but it was returned for recovery by the pre-final
Critic and is not final PASS evidence.

## Candidate Identity

- Recovery code candidate: `5bf6f401d5fcf98277a031d94abf55ac6ad77da1`
- B1-B3 implementation commit: `47cea1edb5bcb0d8038c4c6bd925f2f1ccd5c90c`
- CI environment gate commit: `5bf6f401d5fcf98277a031d94abf55ac6ad77da1`
- Branch: `main`
- Canonical worktree: `/home/yuukias/GPT_Codex_AI_Bridge_Kit`
- Remote: `origin -> https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- CODEX_HOME: `/home/yuukias/.codex`

## B1-B3 Repairs

- B1: `publish-current-branch` now rejects process transport/config/askpass overrides before any remote/network Git preflight, then runs `ls-remote` and `push` under sanitized environment.
- B2: Persistent Run now has `ai-bridge persistent-run report` and `latest`, with machine-local latest/history, event comparison, dedupe/cadence, ETA materiality, UNKNOWN/stall semantics, and no daemon/watcher/controller.
- B3: Reviewed materializer now treats the frozen worktree locator as stable lexical identity, rejects symlink redirection, verifies bootstrap base lineage against `origin/<base_branch>`, and rolls back only invocation-created local branch/worktree state when safe.

## Deterministic Verification

Focused recovery tests:

```text
python -m unittest tests.test_persistent_run tests.test_host_policy tests.test_reviewed_handoff
```

Result: `Ran 121 tests ... OK`

Full local suite:

```text
python -m unittest discover -s tests -p 'test_*.py'
```

Result: `Ran 394 tests ... OK`

CI environment follow-up:

- `tests.test_upfront_authorization_persistent_authoring.UpfrontAuthorizationPersistentAuthoringTests.test_execpolicy_still_prompts_tmux_mutation_and_fallbacks` now skips only when `codex` CLI is absent.
- On the target machine, where `codex` is installed, the execpolicy probe still ran and passed.
- On hosted GitHub Actions, the skip prevents an infrastructure-only failure from replacing the live Machine Policy validation gate.

Diff hygiene:

```text
git diff --cached --check
```

Result: exit 0 before candidate commit.

## Live Machine Policy

Command:

```text
python -m ai_bridge_kit.bridge_cli host install --codex-home /home/yuukias/.codex
python -m ai_bridge_kit.bridge_cli host validate --codex-home /home/yuukias/.codex
```

Result:

- install returned `No changes needed; host policy is already configured.`
- validate exit 0
- `features.default_mode_request_user_input: false (configured)`
- `features.memories: true (configured)`
- `ai-bridge host publish-current-branch ... => allow`
- `ai-bridge reviewed-handoff materialize-worktree ... => allow`
- safe `gh auth/pr/issue/run ... --` reads => allow
- raw `git push origin main` => prompt
- dangerous Git/shell/tmux/process/Slurm mutation neighbors => prompt/no-match

No new backup directory was created because this recovery did not change the Machine Policy managed files and the install was a no-op.

## Normal-Entry Gates Rerun

G1/G2:

- `gh auth status --` succeeded for account `YuukiAS` without token display.
- `gh pr list --` succeeded.
- `gh run list --` succeeded.
- `host validate` confirmed token display, positional `gh pr view`, `--repo`, arbitrary `gh api`, dangerous Git, shell/Python composition and mutation neighbors remain gated.

G3:

- `ai-bridge host publish-current-branch --expected-repo YuukiAS/GPT_Codex_AI_Bridge_Kit --expected-branch main` published `47cea1edb5bcb0d8038c4c6bd925f2f1ccd5c90c` and later `5bf6f401d5fcf98277a031d94abf55ac6ad77da1` to `origin/main`.
- Follow-up `git fetch origin main` verified the code candidate at `HEAD == origin/main == 5bf6f401d5fcf98277a031d94abf55ac6ad77da1` before later evidence-only reporting updates.
- The push again emitted a local tracking-ref lock warning after the remote accepted the update; the independent fetch verified the remote state.

G4:

- Normal HTTPS publication through the bounded publisher succeeded using existing GitHub HTTPS credential manager.
- CLI canary negatives passed for `GIT_SSH_COMMAND`, `GIT_SSH`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_COUNT`, local `core.sshCommand`, local `credential.helper`, local `core.askPass`, worktree `core.sshCommand`, and worktree `credential.helper`.
- In every canary case the expected rejection occurred, the canary marker remained absent, and the remote ref did not change.
- Required positive standard SSH agent/config publication was not proven: `ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new git@github.com` returned `Permission denied (publickey)` and could not write `known_hosts` in the current environment.

G5/G6/G7:

- `ai-bridge reviewed-handoff materialize-worktree` succeeded for exact sibling bootstrap.
- The same normal entry succeeded for `/tmp`-style rematerialization from an existing `reviewed/<task_key>` remote branch.
- Wrong path failed closed with `WORKTREE_ASSERTION_FAILED`.
- Deterministic tests cover changed symlink target, wrong/occupied path, base lineage mismatch, metadata mismatch, branch ambiguity, and invocation-owned rollback.

G8:

- `ai-bridge plugin-replay --help` still exposes only the narrow production replay shape.
- `ai-bridge plugin-replay --plugin ai-skills-core@yuukias-ai-skills ... --dry-run` accepted explicit repo-local task/input files and produced machine-local replay metadata.
- `codex plugin list` shows `ai-skills-core@yuukias-ai-skills` installed/enabled.
- AI Skills maintainer source still directs production evidence to `ai-bridge plugin-replay --plugin ai-skills-core@yuukias-ai-skills`.

G9:

- Official Codex plugin path was exercised with:
  `codex plugin add workflow-core@yuukias-ai-skills --json`
- It succeeded after allowing writes to the existing Codex plugin cache.
- Result kept the legal production plugin identity: `workflow-core@yuukias-ai-skills`, version `0.3`.
- No Bridge candidate-plugin-replay path was used.

G10/G11:

- `ai-bridge persistent-run report --progress ...` processed a three-event local run.
- First event delivered `start_or_resume`.
- Duplicate/non-material event was marked `suppress`.
- Stage transition delivered with `fraction=0.5`, real unit `epochs`, ETA basis `checkpoint throughput`, and uncertainty `plus/minus 5 minutes`.
- `ai-bridge persistent-run latest --progress ...` returned latest without tmux attach.
- Independent stall case produced `eta=UNKNOWN`, `status=stalled`, preserved last progress timestamp, and did not restart/cancel/mutate resources.

G12:

- `ai-bridge notifier send` rejected an invalid `operational_progress` brief with `status=PASS` before delivery.
- Existing Notifications provider/recipient is not configured: `ai-bridge notifier status` returned `sent_count: 0`, `baseline_initialized: false`, `last_success: null`.
- No test notification was sent and no provider/recipient was created.

G13:

- Real `reviewed_runner.push_guard_environment()` caused generic `publish-current-branch` to refuse before mutation.
- Remote ref did not change.

G14:

- Recovery code candidate, live Machine Policy validation, local full tests and normal-entry probes above all bind to code candidate `5bf6f401d5fcf98277a031d94abf55ac6ad77da1`.
- This evidence file is a later evidence artifact and does not change the source candidate code. It records that full release closure is not claimable because G4 SSH positive and Notifications delivery remain unavailable.

G15:

- No generic Git facade, second publisher, auth DB/token store, wrapper registry, new workflow class, daemon/watcher hierarchy, generic shell/Python allow, force/destructive Git allow, or Host-wide `approval_policy=never` was added.
- Existing narrow plugin-replay child `approval_policy="never"` contract remains isolated and unchanged.

## External CI

GitHub Actions run `35895226965` for `5bf6f401d5fcf98277a031d94abf55ac6ad77da1` passed.

```text
Python 3.9: passed
Python 3.x: passed
```

The earlier hosted failure for `47cea1e` was an infrastructure-only `codex executable not found` failure in the CI environment. The current source candidate keeps the live target-machine execpolicy probe and lets hosted CI skip that single probe only when `codex` is absent.

## Remaining Non-Closure Items

- G4 standard SSH agent/config positive publication is not proven on this machine because GitHub SSH authentication is unavailable.
- Notifications delivery is unavailable because no existing provider/recipient is configured; no new provider/credential/recipient was authorized.

Therefore this recovery cannot honestly be marked final release PASS in the current environment.
