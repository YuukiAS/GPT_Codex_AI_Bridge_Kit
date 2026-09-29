# Reviewed Handoff First Remote Publication — Pre-final Repair Kickoff Draft v0.1

Status: **DRAFT FOR CRITIC REVIEW / NOT YET AUTHORIZED**

Repair proposal:

`docs/design/reviewed_handoff_first_remote_publication_pre_final_repair_proposal_v0.1_2026-09-29.md`

Blocking finding:

`BR-FRP-PF-F01`

Only use this Kickoff after an independent Critic PASSes the exact repair proposal and approves this exact bounded text.

---

执行 Reviewed Handoff 首次远端发布的最小 pre-final repair。不要重新设计架构。

Bridge repair placement:

```text
repo = YuukiAS/GPT_Codex_AI_Bridge_Kit
branch = main
worktree = /home/yuukias/GPT_Codex_AI_Bridge_Kit
task = reviewed-handoff--first-remote-publication
version = remain 0.9.3
```

我发送这段经 Critic 批准的 repair Kickoff，仅授权：

1. 修改：
   ```text
   ai_bridge_kit/reviewed_handoff.py
   tests/test_reviewed_handoff.py
   ```

2. 在现有 `publish-first` pre-mutation validation 中补：
   ```text
   CURRENT.schema == CURRENT_SCHEMA
   CURRENT.base_branch == "main"
   ```

3. 增加两个 zero-mutation deterministic negatives：
   - wrong base_branch；
   - wrong CURRENT schema。

4. 保持所有已批准语义不变：
   - dedicated `task publish-first` CLI；
   - caller 参数边界；
   - raw/no-replacement object authority；
   - active graft fail-closed；
   - single direct-child A/A REQUEST/CURRENT fence；
   - fixed empty-expect lease；
   - transport fences；
   - post-read SHA；
   - upstream sequencing；
   - partial/ambiguous failure；
   - generic publisher；
   - bootstrap/materialize/resume/watcher authority；
   - Machine Policy dangerous-neighbor prompts。

5. 修复后冻结新的 exact Bridge candidate，版本仍为 `0.9.3`，运行并绑定到该 candidate：
   - focused tests；
   - full tests；
   - GitHub CI；
   - FP-G1–FP-G5；
   - installed executable/import identity；
   - `ai-bridge host validate`；
   - Machine Policy allow/prompt boundary验证。

6. 不重新安装或修改 Machine Policy。若现有 installed policy validation 不再 PASS，停止并返回 Planner/Critic。

7. 仅在上述 repaired candidate 全部通过后，执行新的 fresh FP-G6：

   ```text
   repo = YuukiAS/AI_Skills_Collection
   checkout = /home/yuukias/AI_Skills_Collection
   task = workflow-core--first-remote-publication-repair-gate
   branch = reviewed/workflow-core--first-remote-publication-repair-gate
   worktree = /home/yuukias/AI_Skills_Collection-workflow-core--first-remote-publication-repair-gate
   base = 执行时同步后的 exact origin/main OID
   ```

   只授权：
   - exact `task bootstrap`；
   - 一个只包含 A REQUEST + A CURRENT 的普通 commit；
   - repaired-candidate `task publish-first`；
   - remote SHA / upstream / remote CURRENT 验证。

8. 新 FP-G6 执行前必须再次证明 exact local branch/worktree/task metadata 与 remote branch 都不存在；若冲突，停止，不得临时换 task identity。

9. 写新的 repaired-candidate evidence：
   ```text
   results/reviewed-handoff--first-remote-publication/IMPLEMENTATION_EVIDENCE_V2.md
   results/reviewed-handoff--first-remote-publication/GATE_MATRIX_RESULT_V2.md
   results/reviewed-handoff--first-remote-publication/FP_G6_REAL_CONSUMER_V2.md
   results/reviewed-handoff--first-remote-publication/FINAL_CANDIDATE_IDENTITY_V2.md
   ```

明确不授权：

- 修改其他 production source；
- 修改 `_active_graft_lines()` 仅为非阻塞 lexical observation；
- 修改/安装 Machine Policy；
- 版本 bump 到 0.9.4 或其他版本；
- raw `git push -u` / raw force-with-lease；
- force/delete/tag/release ref/PR/merge；
- Presentations；
- AI_Skills production source/tests/PLAN/results/version/generated payload；
- paid API/provider/credential changes；
- 新 workflow/state/database/token/receipt/watcher/controller。

Bridge main publication仍只使用已有 bounded：

`ai-bridge host publish-current-branch --expected-repo YuukiAS/GPT_Codex_AI_Bridge_Kit --expected-branch main`

如果修复需要扩大 production scope、Machine Policy、版本或 architecture，停止并返回 Planner/Critic。

完成 repaired candidate + same-candidate evidence + fresh FP-G6 后，停止在新的 independent pre-final Critic 边界，不要宣称 formal release 或 Presentations F03 已关闭。
