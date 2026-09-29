# TODO — Reviewed Handoff 首次远端发布闭环

状态：NEW  
优先级：HIGH  
记录日期：2026-09-29

## 真实失败

在 `YuukiAS/AI_Skills_Collection` 的 Reviewed Handoff 任务：

`product-ui-copy--cross-plugin-production-integration`

中，用户已通过批准后的 Kickoff 明确授权 exact task、branch、worktree。Bridge 0.9.1 成功完成本地首次 bootstrap：

- 创建 `reviewed/product-ui-copy--cross-plugin-production-integration`
- 创建对应 sibling worktree
- 写入 REQUEST/CURRENT
- 当前状态为 `PLAN_REQUESTED / RUN_GPT_PLANNER`

但首次把该 exact reviewed branch 发布到 GitHub 时，现有 bounded publisher 返回：

`UPSTREAM_REMOTE_MISMATCH`

原因：`publish-current-branch` 只支持已存在并已 tracking 的同名远端分支；全新 Reviewed task 的远端分支尚不存在。结果是用户已经在 Kickoff 授权 branch/worktree 后，还被要求再次批准一次 `git push -u`。

用户随后手工批准 exact non-force first push 后，远端分支成功创建，远端 SHA 与本地一致，证明缺口在 Bridge 的首次发布路径，而不是任务本身。

## 期望行为

一次已经明确授权 exact task / `reviewed/<task_key>` / worktree 的 Kickoff，应能完成：

`本地 bootstrap -> exact reviewed branch 首次普通非强制发布 -> 校验远端 SHA -> 后续 Reviewed Handoff`

同一 exact branch 的首次普通发布不应再次向用户索权。

## 约束

不得通过以下方式解决：

- 放宽通用 `git push`
- 允许任意新远端分支
- 允许 force/tag/delete/remote remap
- 把 generic `publish-current-branch` 变成任意分支创建器
- 新增授权数据库、状态机或控制层
- 要求每个 consumer repo 自己写 workaround

优先比较最小实现：

1. 在 Reviewed Handoff 首次 bootstrap 正常入口内补齐 bounded first publication；
2. 或增加一个仅由已验证 Reviewed task identity 驱动的窄发布动作；
3. 只有有充分理由时才修改通用 publisher。

必须继续验证 repo/task/branch/remote/transport/lineage，且发布后重新读取远端 ref，要求远端 SHA 与本地一致。

## 完成标准

至少证明：

1. brand-new Reviewed task 在一次已批准 Kickoff 后，可完成 exact branch/worktree bootstrap 和首次同名远端发布，不再次询问用户；
2. 错 repo、错 branch、错 remote、已有冲突远端、force/tag/delete 等继续 fail closed；
3. 已有分支的普通发布行为不回归；
4. 已有 resume/materialize-worktree 行为不回归；
5. 至少一个真实 consumer 通过正常入口复现并验证修复；
6. 不引入新的 workflow、授权存储、watcher 或泛化 Git wrapper。

## 责任边界

这是跨 repo 的 Reviewed Handoff 通用能力缺口，归 Bridge Kit。consumer repo 只应使用修复后的正常入口，不应各自补授权或 push 规则。
