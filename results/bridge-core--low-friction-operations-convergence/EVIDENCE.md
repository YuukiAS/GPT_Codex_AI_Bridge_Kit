# Bridge Core 0.9.0 Recovery Evidence

Task key: `bridge-core--low-friction-operations-convergence`

Status: `FINAL_CLOSURE_PASS`

This file supersedes the earlier partial recovery evidence that treated a
standard GitHub SSH positive publication as a final release gate. The prior SSH
positive failures remain real historical provenance, but Plan v0.4 removes SSH
positive publication from the 0.9.0 product claim. The independent pre-final
Critic has now reviewed Plan v0.4 plus the current implementation/evidence and
returned PASS, so this document records final closure for the approved
HTTPS-only scope.

## Candidate Identity

- Approved amended plan:
  `docs/design/0.9.0_low_friction_operations_convergence_plan_v0.4_2026-09-24.md`
- Amended recovery goal:
  `docs/design/0.9.0_low_friction_operations_convergence_recovery_goal_v0.2_2026-09-24.md`
- HTTPS-only publisher source correction:
  `160166b0276e3f79e05252c8828f249d1d6409ae`
- Published main baseline observed after an independent later main commit:
  `b933053530cfa9971c735cf38f428ae7cebd46ca`
- Main observed by pre-final Critic:
  `0c7cdba8b12df9b519c83d1b6d5a1a99dd4827ec`
- Branch: `main`
- Canonical worktree: `/home/yuukias/GPT_Codex_AI_Bridge_Kit`
- Remote: `origin -> https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- CODEX_HOME: `/home/yuukias/.codex`

Scope note: `160166b0276e3f79e05252c8828f249d1d6409ae` is the task-owned
publisher correction. `b933053530cfa9971c735cf38f428ae7cebd46ca` was already
the latest published main baseline before this evidence refresh and is not
claimed as part of this HTTPS-only publisher correction.

## Independent Pre-Final Critic Closure

The independent pre-final Critic reviewed the approved Plan v0.4, the
task-owned HTTPS publisher candidate, the current main evidence package, and the
final report. The closure result transferred by the user is:

```text
CRITIC_RESULT=PASS
REVIEW_STAGE=PRE_FINAL
B1_PUBLISH_TRANSPORT_FENCE=CLOSED
B2_PERSISTENT_RUN_REPORTER=CLOSED
B3_REVIEWED_FROZEN_SCOPE=CLOSED
B4_FINAL_GATE_EVIDENCE=CLOSED
G3=PASS
G4=PASS
G14=PASS
PRODUCTION_REPAIR_REQUIRED=NO
READY_FOR_FINAL_CLOSURE=YES
```

No production repair is required after this Critic PASS. The final closure
action is evidence/control-plane only.

## Product Claim After Plan v0.4

- Trusted low-friction publication is GitHub HTTPS only:
  `https://github.com/<owner>/<repo>.git`.
- SSH, scp-style, and custom transports are not trusted low-friction positive
  paths. They route to ordinary approval.
- Effective fetch and push URLs are classified after Git URL rewriting.
- A literal HTTPS remote that is effectively rewritten to SSH/custom fails
  closed before any remote/network Git operation.
- HTTPS fetch with SSH/custom effective push URL fails closed before any
  remote/network Git operation.
- SSH/custom trusted-helper fail-closed remains a security negative gate.
- SSH positive publication is no longer required or claimed.

## Source Changes

- Added a publisher-specific GitHub HTTPS identity parser in
  `ai_bridge_kit/host.py`.
- Kept shared `_canonical_repo_identity()` unchanged so Reviewed Handoff and
  local disposable repo identity continue to support existing HTTPS, SSH, and
  local shapes.
- Moved bounded publisher remote identity classification to the publisher-only
  HTTPS parser while preserving existing transport/config/credential/askpass,
  hook, branch, ancestry, and final recheck fences.
- Added deterministic tests for GitHub HTTPS positive bounded publication,
  SSH/scp/custom effective URL rejection, literal HTTPS rewritten to SSH,
  HTTPS fetch / SSH push mismatch, and shared identity parser compatibility.

## Deterministic Verification

Focused host-policy suite:

```text
python -m unittest tests.test_host_policy
```

Result: `Ran 27 tests ... OK`

Full local suite:

```text
python -m unittest discover -s tests -p 'test_*.py'
```

Result: `Ran 397 tests ... OK`

Diff hygiene:

```text
git diff --check
```

Result: exit 0.

## Live Machine Policy And Runtime Binding

Trusted executable and imported source check:

```text
command -v ai-bridge
python -c "import ai_bridge_kit, ai_bridge_kit.host, ai_bridge_kit.bridge_cli, shutil; ..."
git diff --quiet -- ai_bridge_kit/host.py ai_bridge_kit/bridge_cli.py
git diff --quiet 160166b0276e3f79e05252c8828f249d1d6409ae -- ai_bridge_kit/host.py ai_bridge_kit/bridge_cli.py tests/test_host_policy.py
```

Result:

- Trusted executable: `/home/yuukias/conda/bin/ai-bridge`
- Imported package source:
  `/home/yuukias/GPT_Codex_AI_Bridge_Kit/ai_bridge_kit`
- `host.py`, `bridge_cli.py`, and `tests/test_host_policy.py` matched
  `160166b0276e3f79e05252c8828f249d1d6409ae`.
- Existing editable install already loaded the task-owned final source path for
  the affected publisher entry. No `pip install -e` was run.

Machine Policy validation:

```text
ai-bridge host validate --codex-home /home/yuukias/.codex
```

Result: exit 0.

Important validate observations:

- `overall state: configured`
- `features.default_mode_request_user_input: false (configured)`
- `features.memories: true (configured)`
- `ai-bridge host publish-current-branch ... => allow`
- raw `git push origin main` => prompt
- dangerous Git/shell/tmux/process/Slurm mutation neighbors => prompt/no-match

Managed files did not need refresh, so `ai-bridge host install --codex-home
/home/yuukias/.codex` was not run.

## Normal-Entry Gates Rerun

G3:

- Effective fetch URL:
  `https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- Effective push URL:
  `https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git`
- Bounded publisher command:

```text
python -m ai_bridge_kit.bridge_cli host publish-current-branch --expected-repo YuukiAS/GPT_Codex_AI_Bridge_Kit --expected-branch main
```

Result:

```text
status: published
repo: YuukiAS/GPT_Codex_AI_Bridge_Kit
branch: main
destination: origin/refs/heads/main
pushed_oid: 160166b0276e3f79e05252c8828f249d1d6409ae
transport: GitHub HTTPS
ref update: 7c9fe16..160166b
```

The command used the existing GitHub HTTPS credential path and did not require
repeated approval. The remote accepted the ordinary non-force ref update. The
publisher emitted a local tracking-ref/credential lock warning after the remote
accepted the update; an independent fetch verified the remote state:

```text
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
```

Result at source publication time:

```text
HEAD == origin/main == 160166b0276e3f79e05252c8828f249d1d6409ae
```

G4:

- GitHub HTTPS positive: passed through bounded publisher as above.
- Existing exact-effect/security negatives: retained and covered by
  `tests.test_host_policy`.
- Effective SSH/scp/custom remote fail-closed before network: passed.
- Literal HTTPS rewritten to SSH/custom negative: passed.
- HTTPS fetch / SSH push mismatch negative: passed.
- SSH positive publication: no longer required by Plan v0.4 and not claimed.

Rejected cases prove no remote/network publication through the trusted helper by
mocking publisher network points and asserting they are never reached. Existing
canary tests continue proving injected executables are not run and remote refs
do not change for transport/config/credential/askpass/hook negatives.

G14:

- The task-owned source correction, runtime publisher entry, local deterministic
  tests, live host validation, and HTTPS normal-entry publication all bind to
  `160166b0276e3f79e05252c8828f249d1d6409ae`.
- This evidence refresh records the amended HTTPS-only product claim and no
  longer treats SSH positive publication as a remaining product gate.
- Final documentation now explicitly states:
  - `trusted low-friction = GitHub HTTPS`
  - `SSH/custom = ordinary approval`

## Should-Not-Change Regressions

The full local suite passed after the HTTPS-only publisher change:

```text
python -m unittest discover -s tests -p 'test_*.py'
Ran 397 tests ... OK
```

This includes coverage for B1/B2/B3-adjacent behavior, Reviewed Handoff,
Reviewed runner, Persistent Run, Notifications, plugin-replay, G13, and G15.

External CI:

- GitHub Actions run `35947503209` for
  `160166b0276e3f79e05252c8828f249d1d6409ae`: success.
- GitHub Actions run `35947601396` for
  `b933053530cfa9971c735cf38f428ae7cebd46ca`: success.

## Historical SSH Provenance

Earlier recovery evidence observed real SSH positive failures:

- `ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new git@github.com`
  returned `Permission denied (publickey)` and could not write `known_hosts` in
  the current environment.
- A later strict standard SSH probe failed with `Host key verification failed`.
- A temporary known-hosts authentication probe failed with
  `Permission denied (publickey)`.
- `ssh-add -l` returned `Error connecting to agent: No such file or directory`.

These remain real historical facts under the old scope. They are no longer
release blockers after Plan v0.4 because SSH positive publication is not part of
the HTTPS-only trusted low-friction product claim.

## Current Conclusion

The approved HTTPS-only scope correction has been implemented, tested, published
through GitHub HTTPS, validated against the affected gates, and independently
accepted by the pre-final Critic. Bridge Kit 0.9.0
`bridge-core--low-friction-operations-convergence` is final-closed for the
approved HTTPS-only scope. This is not a claim that SSH/custom transports are
trusted low-friction publication paths.
