# Bridge Kit 0.9.0 Low-Friction Operations Convergence

## What this task solved

This 0.9.0 candidate moves low-friction operations away from broad raw Git trust and into bounded Machine Policy operations. Routine safe reads are quieter, existing-branch publication has one exact-effect helper, Reviewed Mode can rematerialize frozen task worktrees, and Persistent Run progress can be reported without fake percentages or fake ETAs.

## What changed

- Added `ai-bridge host publish-current-branch`.
- Added `ai-bridge reviewed-handoff materialize-worktree`.
- Added Persistent Run progress normalization.
- Extended Notifications with operational-progress briefs that cannot claim semantic PASS/READY/release completion.
- Updated Machine Policy rules, README, QUICKSTART, AGENTS guidance, CHANGELOG, and version metadata to `0.9.0`.

## New capabilities / behavior

- Current-repository GitHub diagnostics such as `gh pr list --` and `gh run list --` can be allowed directly while `--repo`, token display, arbitrary `gh api`, and positional view forms remain gated.
- Raw `git push origin main` is no longer the low-friction publication path; use `ai-bridge host publish-current-branch --expected-repo <owner/repo> --expected-branch <branch>`.
- Reviewed Mode worktree materialization reads the frozen worktree locator from `REQUEST.md` and base identity from `CURRENT.json`; caller arguments only assert equality.
- Persistent Run reports `ETA=UNKNOWN` unless the producer supplied a defensible basis.

## Example usage

```bash
ai-bridge host publish-current-branch \
  --expected-repo YuukiAS/GPT_Codex_AI_Bridge_Kit \
  --expected-branch main

ai-bridge reviewed-handoff materialize-worktree \
  --target /path/to/project \
  --task-key repo--feature \
  --expected-repo YuukiAS/project \
  --expected-worktree /absolute/frozen/worktree \
  --expected-base-ref origin/main \
  --mode resume

ai-bridge persistent-run progress \
  --evidence /path/to/project-native-progress.json \
  --stalled-after-seconds 3600
```

## Regression and remaining limitations

Local focused tests and the full repository suite pass on the candidate. The live Machine Policy install and `origin/main` publication are post-commit closure steps and are recorded in the operator final response, because recording those exact post-commit effects inside this committed artifact would change the artifact's own commit identity.

## Technical appendix

See `results/bridge-core--low-friction-operations-convergence/EVIDENCE.md` for gate evidence and command results.
