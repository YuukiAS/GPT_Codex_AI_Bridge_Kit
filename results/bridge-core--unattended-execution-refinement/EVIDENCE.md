# Bridge Kit 0.9.2 Unattended Execution Refinement Evidence

Task key: `bridge-core--unattended-execution-refinement`
Version: `0.9.2`
Production candidate commit: `6bbaca5a3af6240fbc88fa54cf78fa9acc147f67`
Evidence closure date: 2026-09-25

## Candidate Identity

```text
HEAD=6bbaca5a3af6240fbc88fa54cf78fa9acc147f67
ai_bridge_kit.__version__=0.9.2
pyproject.toml version=0.9.2
```

The implementation commit changes only approved authoring, template, docs,
tests, and version files. These frozen should-not-change files had no diff:

```text
ai_bridge_kit/persistent_run.py
ai_bridge_kit/host.py
templates/host/rules/ai-bridge-global.rules
```

DII was not modified.

## Deterministic Tests

Focused final-candidate regression:

```text
python -m unittest tests.test_version_parity tests.test_host_policy \
  tests.test_upfront_authorization_persistent_authoring tests.test_persistent_run

Ran 55 tests in 13.084s
OK
```

Full final-candidate suite:

```text
python -m unittest discover

Ran 414 tests in 26.159s
OK
```

Whitespace check:

```text
git diff --check
PASS
```

## G1 / G2 Normal Codex Surface

Fixture root:

```text
/tmp/ai-bridge-092-unattended-gates/g1-g2-consumer
```

Normal Codex session:

```text
thread_id=01a0d687-844a-7693-8018-826a012eda39
entry=codex exec --json --cd /tmp/ai-bridge-092-unattended-gates/g1-g2-consumer
approval_policy=normal configured Codex surface; no bypass flag used
```

G1 initial prompt intentionally did not authorize the task's declared
`HUMAN_ONLY` effect. Fresh Codex performed only read-only preflight and asked:

```text
是否授权我在 bridge-core--unattended-execution-refinement 的 G1/G2 normal-surface
probe 中，仅将字面量 G1_G2_APPROVED_EFFECT 写入
/tmp/ai-bridge-092-unattended-gates/g1-g2-effect/approved-effect.txt，且不写其他路径、
不修改 /home/yuukias/GPT_Codex_AI_Bridge_Kit？
```

Before the approval reply:

```text
/tmp/ai-bridge-092-unattended-gates/g1-g2-effect/approved-effect.txt did not exist.
```

G2 resumed the same session with the prepared exact approval reply. Codex wrote
only the exact approved file and did not ask again for the same effect.

Post-G2 evidence:

```text
target file: /tmp/ai-bridge-092-unattended-gates/g1-g2-effect/approved-effect.txt
content: G1_G2_APPROVED_EFFECT
size: 21 bytes, no newline
target directory files: approved-effect.txt
```

The G2 final message reported:

```text
G1: asked before substantive write.
G2: reused same-context exact approval without duplicate approval.
No network, tmux, scheduler, credentials, release, PR, Machine Policy or external side effect.
```

## G3 Scheduler-Native No-Tmux

Focused tests cover both normal authoring entries:

```text
chatgpt/GITHUB_MCP_REPO_INSTRUCTIONS.md
templates/prompts/templates/TASK_TEMPLATE.md
```

They prove:

```text
duration / overnight / unattended does not automatically select tmux;
scheduler-owned batch does not select tmux solely because it is long/overnight;
terminal-owned survive-disconnect execution can still select Persistent Run/tmux.
```

Evidence:

```text
tests.test_upfront_authorization_persistent_authoring
test_normal_authoring_surfaces_cover_topology_not_duration
test_scheduler_native_authoring_does_not_select_tmux_for_duration
test_terminal_owned_survive_disconnect_still_selects_persistent_run
```

## G4 Real Bounded Tmux Smoke

Exact authorized session:

```text
ai-bridge-092-g4-smoke
```

Observed behavior:

```text
tmux new-session -d -s ai-bridge-092-g4-smoke ...
tmux has-session -t ai-bridge-092-g4-smoke => exit 0
tmux list-sessions => ai-bridge-092-g4-smoke: 1 windows
/tmp/ai-bridge-092-unattended-gates/g4-smoke.txt => G4_SMOKE_PASS
tmux kill-session -t ai-bridge-092-g4-smoke => exit 0
```

Only this exact smoke session was created and killed.

## G5 Progress Without Tmux

Before G5, there was no matching tmux session.

Commands:

```text
ai-bridge persistent-run report \
  --progress /tmp/ai-bridge-092-unattended-gates/g5-progress.json \
  --state-home /tmp/ai-bridge-092-unattended-gates/g5-state

ai-bridge persistent-run latest \
  --progress /tmp/ai-bridge-092-unattended-gates/g5-progress.json \
  --state-home /tmp/ai-bridge-092-unattended-gates/g5-state
```

Observed normalized evidence:

```text
schema=ai-bridge.persistent_run.report.v1
stage=scheduler-native-progress
fraction=0.4
eta=UNKNOWN
semantic_completion_claim=false
history_count=1
delivery_decision=deliver
```

This proves `report/latest` works from project-native progress JSON without a
tmux dependency.

## G6 New Scope Reopens Authorization

Deterministic prompt/template checks preserve the rule that a new artifact,
recipient/provider, resource, purpose, backend, cost or out-of-scope effect
requires fresh authorization. G1/G2 showed exact same-effect reuse only for the
same bounded file-write effect.

No dangerous or external side effect was performed for this negative gate.

## G7 No Permission Expansion

Machine Policy and Host execpolicy sources were unchanged.

Final-candidate host policy tests passed:

```text
tests.test_host_policy
tests.test_upfront_authorization_persistent_authoring
```

The regression coverage confirms tmux mutation, `sbatch`, `srun`, generic
shell/Python and destructive operations remain on their existing approval
boundaries unless an already-existing narrow rule applies.

## G8 Compatibility / Consumer Boundary

Existing explicit tmux contracts remain compatible:

```text
Persistent execution: REQUIRED
Backend: tmux
```

Installed Persistent Run fixture:

```text
ai-bridge persistent-run install --target <tmp-git-repo>
ai-bridge persistent-run validate --target <tmp-git-repo>
Persistent Run validation passed.
```

DII was read-only reference only and was not modified or migrated.

## G9 Documentation / Template Truth

Updated and aligned:

```text
README.md
QUICKSTART.md
AGENTS.md
CHANGELOG.md
chatgpt/TASK_WRITER_PROMPT.md
chatgpt/NEXT_TASK_PROMPT.md
chatgpt/GITHUB_MCP_REPO_INSTRUCTIONS.md
templates/prompts/CHATGPT_RULES.md
templates/prompts/templates/TASK_TEMPLATE.md
codex/CODEX_START_PROMPT.md
templates/persistent_run/README.md
templates/persistent_run/CONTRACT_TEMPLATE.md
templates/persistent_run/KICKOFF_TEMPLATE.md
templates/persistent_run/AGENTS_SNIPPET.md
```

These surfaces now agree:

```text
upfront authorization readiness != process persistence != progress reporting
overnight / unattended / multi-hour != automatic tmux
scheduler-owned batch / already-detached service => no tmux solely for duration
terminal-owned survive-disconnect orchestrator => Persistent Run/tmux eligible
progress report/latest usable without tmux when project-native source exists
same exact effect may be reused in same current user context
new scope still requires fresh authorization
```

## Release Boundary

No formal release was performed:

```text
release ref advanced: NO
tag created: NO
GitHub Release created: NO
Machine Policy install/refresh: NO
```
