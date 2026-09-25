# Gate Matrix Result

Task key: `bridge-core--unattended-execution-refinement`
Production candidate: `6bbaca5a3af6240fbc88fa54cf78fa9acc147f67`
Version: `0.9.2`

| Gate | Result | Evidence |
|---|---|---|
| G1 foreseeable approval before precursor work | PASS | Fresh `codex exec` session `01a0d687-844a-7693-8018-826a012eda39` read the fixture and candidate start prompt, performed only read-only preflight, then asked for exact authorization before writing `/tmp/ai-bridge-092-unattended-gates/g1-g2-effect/approved-effect.txt`. |
| G2 same frozen effect not asked twice | PASS | Same session resumed with exact approval reply and wrote only `approved-effect.txt`; final message reported no duplicate approval, and the file content matched `G1_G2_APPROVED_EFFECT`. |
| G3 scheduler-native overnight job does not acquire tmux | PASS | Focused tests cover `chatgpt/GITHUB_MCP_REPO_INSTRUCTIONS.md` and `templates/prompts/templates/TASK_TEMPLATE.md`, proving duration/unattended wording does not automatically select tmux and scheduler-owned batch keeps native lifetime. |
| G4 terminal-owned long orchestrator still uses canonical tmux | PASS | Real bounded tmux smoke created, observed and killed only exact session `ai-bridge-092-g4-smoke`; artifact `G4_SMOKE_PASS` written. |
| G5 progress reporting works without tmux | PASS | `ai-bridge persistent-run report/latest --state-home /tmp/ai-bridge-092-unattended-gates/g5-state` succeeded from project-native JSON with no tmux session; `semantic_completion_claim=false`. |
| G6 new scope reopens human gate | PASS | Prompt/template regression preserves fresh authorization requirement for new resource/provider/artifact/purpose/backend/cost/destructive scope; G1/G2 reuse was limited to one exact same effect. |
| G7 no broad permission expansion | PASS | `persistent_run.py`, `host.py`, Host rules unchanged; focused Host/execpolicy tests passed and keep tmux mutation, `sbatch`, `srun`, generic shell/Python and destructive commands gated. |
| G8 compatibility / existing consumers | PASS | Explicit `Persistent execution: REQUIRED / Backend: tmux` contract remains valid; install/validate fixture passed; DII was not modified. |
| G9 user-facing docs match actual behavior | PASS | README, QUICKSTART, AGENTS, CHANGELOG, authoring prompts and installed templates now share the same 0.9.2 topology/authorization/progress semantics. |

Overall:

```text
G1_G9=PASS
PRODUCTION_CANDIDATE_COMMIT=6bbaca5a3af6240fbc88fa54cf78fa9acc147f67
VERSION=0.9.2
RELEASE_REF_ADVANCED=NO
NEXT_HANDOFF=PRE_FINAL_CRITIC
```
