# Reviewed Handoff 首次远端发布设计 Plan v0.1

Plan version: **0.1**  
Date: **2026-09-29**  
Status: **READY FOR INDEPENDENT CRITIC REVIEW / DESIGN ONLY**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Source ref: **main @ 23e921e37b1178ee44514c0b03dd2d5140d64fb0**  
Design topic: **reviewed-handoff--first-remote-publication**  
Trigger evidence: **docs/TODO_REVIEWED_HANDOFF_FIRST_REMOTE_PUBLICATION.md**

本 Plan 仅做设计。不得据此创建 implementation branch/worktree、修改 production code、发布新版本、增加 watcher/workflow/授权存储，或让 consumer repo 自行补 workaround。

## 1. 根因

根因在 Bridge，不在 consumer。

当前 `reviewed-handoff task bootstrap` 正确完成本地
`reviewed/<task_key>`、确定性的 sibling worktree，以及首份
`REQUEST.md` / `CURRENT.json`；它按 0.9.1 已接受边界故意不做网络发布。

当前 `host publish-current-branch` 则是**已有远端分支更新器**。它在发布前要求：

- `branch.<branch>.remote = origin` 且 merge ref 同名；
- 远端已经存在同名 branch。

全新 Reviewed branch 两者都没有，因此本次
`UPSTREAM_REMOTE_MISMATCH` 是现有实现的直接结果；即使预先补 upstream，下一道
`REMOTE_SAME_NAME_BRANCH_REQUIRED` 仍会拒绝首次发布。

所以不能把问题归因给 AI_Skills consumer，也不能要求 consumer 自己绕过。

## 2. 三种现实方案

| 方案 | 优点 | 主要问题 | 结论 |
|---|---|---|---|
| 1. 把首次发布直接塞进 `task bootstrap` | 一个入口、owner 正确 | 会打破 0.9.1 已冻结的“bootstrap 只做本地拓扑、零网络”边界；还必须让 bootstrap 接管首个 commit 和远端部分失败恢复 | **不选** |
| 2. 增加 Reviewed 专用的窄首次发布动作 | 保持 bootstrap 与 generic publisher 原职责不变；任务身份可由 Reviewed artifact 约束 | 多一个窄动作，必须严格限制作用域 | **选择** |
| 3. 最小扩展 `publish-current-branch` | 表面代码改动最少 | 要么把 generic Host publisher 变成新远端 branch 创建器，要么迫使 Host 理解 Reviewed task 语义；owner 与回归面都变差 | **不选** |

也不采用 watcher 首次发布：首次远端 branch 正是后续远端 Reviewed Handoff 的前置条件，把这一步绑进 watcher 生命周期只会增加不必要的运行时耦合。

## 3. 选择的正常入口

在现有 Reviewed Handoff 下增加一个阶段专用动作：

```text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
```

调用者不得传入 branch、remote、destination ref、force、tag、delete、push option、upstream 或 transport。

正常路径冻结为：

```text
一次已批准的 exact Reviewed Kickoff
-> 现有 git fetch --all --prune
-> 现有 task bootstrap
-> 提交包含首份 REQUEST/CURRENT 的普通 task-owned commit
-> task publish-first
-> 重新读取 exact remote ref，要求 remote SHA == captured local HEAD
-> 后续正常 existing-branch Reviewed Handoff
```

这是现有 Reviewed Handoff workflow 内的一次窄动作，不是新 workflow，也不是新授权系统。

## 4. 机械安全边界

`publish-first` 在任何远端 mutation 前必须重新证明：

1. 当前 cwd 就是该任务冻结的 Reviewed sibling worktree，repo identity 等于 `--expected-repo`；
2. task key 合法，branch 只能派生为 `reviewed/<task_key>`；
3. `REQUEST.md` 与 `CURRENT.json` 都存在于当前已提交树中，task/base/worktree identity 一致，冻结 worktree locator 等于 cwd；
4. 当前 branch 必须就是派生出的 Reviewed branch；
5. 任务仍处于首次交接状态 `PLAN_REQUESTED / RUN_GPT_PLANNER`；workflow 已推进后不得借此重建被删除的远端 branch；
6. worktree clean，HEAD 是冻结 base commit 的后代；
7. canonical `origin` profile，以及有效 GitHub HTTPS fetch/push identity，继续通过现有 bounded publisher 的 transport/config/environment/hook 防线；
8. fresh exact `ls-remote --heads` 证明同名远端 branch 不存在；
9. 进入时 branch upstream 配置必须为空；本动作只可建立确定性的
   `remote=origin` 与 `merge=refs/heads/reviewed/<task_key>`；
10. 唯一允许的 refspec 是
    `<captured-HEAD>:refs/heads/reviewed/<task_key>`，不得有 `+`、force、tag、delete、mirror、额外 refspec、push option、signed-push 扩张、submodule recursion 或调用者选择的 transport；
11. push 前再次核对 repo/branch/HEAD/remote/config；
12. push 后重新读取 exact remote ref，只有其 SHA 与 captured local HEAD 完全一致才算成功。

同名 upstream 是该 bounded effect 的一部分，因为后续已有分支普通发布需要它。若远端创建前 push 失败，只能在配置仍未被外部改变时回滚本次新增的本地 upstream 键；Bridge 不得为了 rollback 删除或改写远端 ref。网络结果不明确时必须报告 partial/ambiguous publication 并停止，不得盲目重试。

只要任一次发布前检查发现远端 branch 已存在，不论 SHA 相同、祖先、后代还是分叉，都必须 fail closed；该动作只处理首次发布。

Git 在“最后一次远端不存在检查”和实际 push 之间仍有并发竞态。v0.1 明确不使用
`--force-with-lease`，也不引入 provider API。普通 non-force explicit refspec 不会覆盖分叉历史，push 后强制回读可暴露 SHA 不一致。Critic 需要专门判断这个残余竞态是否可接受；若不可接受，应 REVISE 本 Plan，而不是静默扩大 force/API 权限。

## 5. 授权与 owner

新命令应作为一个极窄的 Bridge 受控放行动作加入主机策略（Machine Policy），与当前已硬化的 Reviewed bootstrap/materializer 同类，使已经批准 exact Reviewed task/branch/worktree 的 Kickoff 不会仅因“远端 branch 尚不存在”再次要求用户批准。

这不是“任意创建 Reviewed branch”的权限。行为规则仍要求存在真实、用户已选择的 Reviewed task；helper 自身只能对当前 repo、初始状态、artifact-bound 的唯一
`reviewed/<task_key>` 生效。

同步修改 managed Host 行为文字：

- exact Reviewed task 的首次发布只能通过 `reviewed-handoff task publish-first` 继承已批准的 branch strategy；
- raw `git push -u`、任意新远端 branch、alternate upstream、force/tag/delete、remote remap 与 generic first push 继续走审批路径。

不得增加 authorization receipt/token/database、新 state 字段、watcher 或 controller。

## 6. Critic PASS 后允许设计的实现边界

预期只涉及：

- `ai_bridge_kit/reviewed_handoff.py` 与对应 CLI route；
- 必要时复用/抽取现有 Host transport/config 防线，但不得改变公开
  `publish-current-branch` 的行为；
- Host Machine Policy 与 managed AGENTS 中该一个 bounded action 的规则；
- Reviewed Handoff normal-entry 文档；
- focused tests。

`publish-current-branch`、`materialize-worktree`、reviewed watcher publication authority 与 resume semantics 均保持行为不变。

## 7. 验收与回归

同一个最终 candidate 至少证明：

- **FP-G1 首次发布正例**：bootstrap -> commit -> `publish-first` 只创建 exact Reviewed remote branch，只绑定 same-name `origin` upstream，post-read SHA 等于 local HEAD，且不再次向用户索权；
- **FP-G2 fail closed**：错 repo/task/branch/worktree/state/lineage、dirty 或未提交 task metadata、非 canonical remote/transport/config/hook/environment、任何已存在同名远端 branch，均不得发生远端 mutation；
- **FP-G3 邻近危险形态保持受限**：raw first push、任意 branch、force、force-with-lease、tag、delete、mirror、额外 refspec、remote remap、alternate upstream 均不能借此放开；
- **FP-G4 已有发布不回归**：当前 `host publish-current-branch` 的 existing-branch 正负测试保持原语义；
- **FP-G5 resume 不回归**：本地与 remote-only `materialize-worktree --mode resume` 保持原语义；
- **FP-G6 真实 consumer**：确定性 fixture 全过后，再用一个真实 consumer repo 的**全新** Reviewed task 走 normal entry。已经手工发布过的
  `product-ui-copy--cross-plugin-production-integration` 只能作为根因证据，不能冒充 fresh first-publication 验收。

本设计轮不得创建该 fresh consumer task。

## 8. 外部事实核查

2026-09-29 复核 Git 官方 `git-push` 文档。官方语义支持：显式 refspec 可固定 source/destination；普通 branch push 默认不带 force；upstream tracking 对应 branch 的 remote/merge 配置，也可由 `--set-upstream` 建立。

本 Plan 采用：exact explicit refspec、non-force、确定性 same-name upstream。  
明确不采用：force/force-with-lease、隐式 `push.default`、tag/mirror/delete、调用者任意 refspec。

Reference:
https://git-scm.com/docs/git-push

## 9. Planner 结论

```text
PLANNER_RESULT=READY_FOR_CRITIC
PLAN_VERSION=0.1
SELECTED_OPTION=REVIEWED_ONLY_FIRST_PUBLICATION_ACTION
GENERIC_PUBLISHER_BEHAVIOR_CHANGE=NO
BOOTSTRAP_NETWORK_BOUNDARY_CHANGE=NO
NEW_WORKFLOW=NO
NEW_AUTHORIZATION_STORE=NO
IMPLEMENTATION_AUTHORIZATION=NO
NEXT_HANDOFF=CRITIC
```

README checked: design-only round; no update required now.  
CHANGELOG checked: design-only round; no update required now.
