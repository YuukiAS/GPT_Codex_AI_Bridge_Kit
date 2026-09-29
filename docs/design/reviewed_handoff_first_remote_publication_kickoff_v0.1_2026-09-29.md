# Reviewed Handoff First Remote Publication — Kickoff Draft v0.1

Status: **DRAFT FOR EXECUTION_READY CRITIC REVIEW / NOT YET AUTHORIZED**

Approved design:

`docs/design/reviewed_handoff_first_remote_publication_plan_v0.4_2026-09-29.md @ cedd6f1dc2c13af7e237fc0ab2c07ba73700472a`

Canonical Goal:

`docs/design/reviewed_handoff_first_remote_publication_goal_v0.1_2026-09-29.md`

Acceptance Matrix:

`docs/design/reviewed_handoff_first_remote_publication_acceptance_matrix_v0.1_2026-09-29.md`

Only use this Kickoff if an independent execution-ready Critic returns PASS for this exact package and reproduces/approves this exact Kickoff.

---

执行已经 DESIGN PASS 的 Bridge Reviewed Handoff 首次远端发布修复。不要重新设计。

Bridge execution placement:

```text
repo = YuukiAS/GPT_Codex_AI_Bridge_Kit
branch = main
worktree = /home/yuukias/GPT_Codex_AI_Bridge_Kit
task = reviewed-handoff--first-remote-publication
```

严格按 Canonical Goal 与 Acceptance Matrix 实现、测试、冻结 final candidate。

我发送这段经 execution-ready Critic 批准的 Kickoff，即授权本任务：

- 在上述 exact Bridge `main` checkout 修改 Goal 冻结的 source/templates/tests/docs/version files；
- 运行 focused/full unittest、disposable local Git fixtures 与正常 GitHub CI；
- 若执行前版本仍精确为 `0.9.2`，把 candidate bump 到 `0.9.3` 并同步 `pyproject.toml`、`ai_bridge_kit/__init__.py`、README、CHANGELOG；
- 在 Bridge `main` 做 task-owned ordinary commits，并通过现有 bounded `ai-bridge host publish-current-branch --expected-repo YuukiAS/GPT_Codex_AI_Bridge_Kit --expected-branch main` 普通 non-force 发布；
- final deterministic gates PASS 后，若当前本机 Bridge runtime 不是 exact candidate，做一次 bounded editable refresh；
- 对 `/home/yuukias/.codex` 做一次有备份的 exact-candidate Machine Policy install/validate，用于验证新 bounded allow；失败时按 Goal 恢复 managed-file backup，不重复安装；
- 仅为 FP-G6，在 `YuukiAS/AI_Skills_Collection` 使用以下 exact fresh consumer：
  ```text
  task = workflow-core--first-remote-publication-gate
  branch = reviewed/workflow-core--first-remote-publication-gate
  worktree = /home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-gate
  base = 执行时同步后的 exact origin/main OID
  ```
  授权 exact `task bootstrap`、只包含 first-bootstrap REQUEST/CURRENT 的一个普通 commit、以及通过新 `task publish-first` 创建 exact same-name remote branch；不得修改 AI_Skills production source、PLAN.md、results、version、generated payload 或 Presentations。

明确不授权：

- 其他 branch/worktree；
- raw `git push -u` / raw force-with-lease；
- force/tag/delete/mirror/remote remap/history rewrite；
- PR、merge、release tag、`release` ref advancement；
- Presentations mutation；
- 新 workflow/state/database/token/receipt/watcher/controller；
- paid API、新 provider/account/credential/private-data scope；
- 修改 generic `host publish-current-branch` public semantics、bootstrap zero-network、materialize/resume 或 watcher authority。

若 exact placement/version/source 出现 material drift，或 approved surface不足，停止并返回 Planner/Critic，不要自行扩项。

完成 implementation + FP-G1–FP-G6 + installed identity + CI 后，写 Goal 指定的 durable evidence，并停止在 pre-final Critic 边界。不要声称 formal release/distribution complete。
