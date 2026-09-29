# Reviewed Handoff 首次远端发布设计 Plan v0.3

Plan version: **0.3**  
Date: **2026-09-29**  
Status: **READY FOR INDEPENDENT CRITIC RE-REVIEW / DESIGN ONLY**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Design topic: **reviewed-handoff--first-remote-publication**  
Source baseline: **main @ a06e0158b64d33d0be8b5cfdb658b828f90b2b4e**  
Previous Plan: **docs/design/reviewed_handoff_first_remote_publication_plan_v0.2_2026-09-29.md @ a06e0158b64d33d0be8b5cfdb658b828f90b2b4e**  
Prior durable Critic review: **docs/design/reviewed_handoff_first_remote_publication_critic_review_v0.1_2026-09-29.md @ 6043689d6464fc64f51666a9198ffd509fff5a70**  
Current Critic handoff: **RESULT=REVISE; BR-FRP-F01=CLOSED; BR-FRP-F02=STILL_OPEN; NEW_BLOCKERS=NONE**

本 Plan 是 v0.2 的完整替代版，不是 patch note。本轮只关闭 'BR-FRP-F02'。  
不得据此修改 production source、创建 implementation branch/worktree、修改或安装 Machine Policy、发布 Bridge、修改 Presentations consumer、开始 execution package，或新增 workflow/state/database/token/receipt/watcher/controller。

## 1. 已冻结且不得重开的架构

继续使用已经通过方向审查的 Reviewed Handoff 专用入口：

~~~text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
~~~

职责保持：

~~~text
task bootstrap
= 本地 Reviewed task topology + REQUEST/CURRENT
= zero network
= no commit
= no push

task publish-first
= 只发布 first-bootstrap control metadata
= 只首次创建此前不存在的 exact reviewed remote ref

host publish-current-branch
= 继续只更新 already-existing same-name remote branch
~~~

仍然禁止：

- publication inside bootstrap；
- generic 'publish-current-branch' widening；
- raw 'git push -u' 作为 normal entry；
- consumer-specific wrapper；
- arbitrary branch/ref/refspec/remote/upstream；
- authorization DB/token/receipt；
- new state machine/watcher/controller/workflow。

## 2. 根因与当前真实 bootstrap 产物

根因不变：当前 generic bounded publisher 要求已有 same-name upstream/remote branch，因此 brand-new Reviewed branch 不能首次发布；这是 Bridge 通用缺口，不属于 consumer。

当前 '_initialize_task_files()' 与 'bootstrap_task_worktree()' 的真实行为已经核实：

- 创建 'automation/reviewed_handoff/tasks/<task_key>/REQUEST.md'；
- 创建 'automation/reviewed_handoff/tasks/<task_key>/CURRENT.json'；
- 创建本地空 'results/<task_key>/' 目录；
- 不创建第三个 tracked first-handoff artifact；
- Git 不跟踪空目录；
- bootstrap 本身不 commit、不 push。

因此 first-publication 的 tracked control payload 可以且应当由**一个普通 commit**完整表达为两份新文件，不需要多个 metadata-only commits。

## 3. 正常生命周期

冻结正常路径：

~~~text
一次已批准的 exact Reviewed Kickoff
-> 现有 git fetch --all --prune
-> 现有 task bootstrap
-> exact sibling worktree 中一次普通 commit：
     A REQUEST.md
     A CURRENT.json
-> task publish-first
-> atomic create-if-absent remote publication
-> post-read remote SHA == captured HEAD
-> 成功后才绑定 deterministic same-name origin upstream
-> external GPT Planner
-> 后续正常 Reviewed Handoff
~~~

第一次 publication 只负责让 external Planner 读到 first-bootstrap control plane。  
'PLAN.md'、Planner transaction、Executor product/source、CI/Reviewer publication 均不允许搭首发 commit 一起发布。

## 4. BR-FRP-F02：改为 history-safe 单提交合同

v0.2 只看 'base tree -> captured HEAD tree' 的最终 changed paths，无法阻止中间历史先提交 production/source、随后 revert/remove，再提交 REQUEST/CURRENT 的 history laundering。

v0.3 不再把最终 tree diff 当成唯一 history fence，而是要求**从 frozen base 到 captured HEAD 恰好只有一个直接 child commit**。

### 4.1 先冻结 captured identity

在任何 remote/config mutation 前：

1. 确认 cwd 为当前 Git worktree；
2. 确认 worktree clean；
3. 冻结 'captured_head = HEAD'；
4. 从 **captured HEAD tree** 读取 exact：
   - 'automation/reviewed_handoff/tasks/<task_key>/REQUEST.md'
   - 'automation/reviewed_handoff/tasks/<task_key>/CURRENT.json'
5. 从 captured CURRENT 取得并校验 'base_commit'。

不得用可继续变化的 working-tree 文件替代 captured-tree authority。

### 4.2 exact one-commit ancestry

必须同时证明：

~~~text
captured HEAD 直接 parent 数量 = 1
captured HEAD 唯一 parent = CURRENT.base_commit
CURRENT.base_commit..captured HEAD reachable commit 数量 = 1
~~~

其中“唯一 parent 精确等于 base”是核心机械条件；commit-count 检查作为显式一致性证据保留。

因此以下情况全部在 mutation 前 fail closed：

- base -> production commit -> revert/delete commit -> metadata commit；
- base -> metadata commit 1 -> metadata commit 2；
- merge commit；
- merge side history；
- rebased/synthetic history 中 captured HEAD 不是 base 的直接 child；
- 任何多 commit reachable history。

本轮不允许 first-publication helper 为“方便”放宽成多 metadata commit。

如果未来出现真实 normal-entry 证据证明一提交模型不足，必须重新回 Planner/Critic；届时才允许讨论审计 'base_commit..captured_head' 整个 reachable history 的每个 commit/path union，并显式处理 merge side history。v0.3 不预先实现这套更复杂方案。

### 4.3 base tree 必须没有两份 task artifact

在 frozen 'CURRENT.base_commit' tree 中，下列两条 path 必须都不存在：

~~~text
automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
~~~

任何一条已存在都说明这不是 brand-new first-bootstrap control commit，必须 fail closed。

### 4.4 单 commit 的 exact name-status fence

比较：

~~~text
CURRENT.base_commit
vs
captured HEAD
~~~

但这是在“captured HEAD 唯一 parent就是 base”的前提下进行，因此该 diff 就是**唯一 first-bootstrap commit 本身**的实际 tree effect。

实现时必须：

- recursive；
- machine-readable；
- 禁用 rename inference；
- 不启用 copy detection；
- 不使用会隐藏 parent/path 的 combined merge diff；
- merge 已被 parent-count gate 先行拒绝。

'name-status' 必须严格、无第三项地等于：

~~~text
A  automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
A  automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
~~~

顺序不作为语义要求，但集合与 status 必须精确。

以下均 fail closed：

- 'M'、'D'、'R'、'C' 或其他 status；
- 任何第三条 path；
- production source；
- tests；
- results artifact；
- 'PLAN.md'；
- unrelated docs；
- other task metadata；
- generated/private artifact。

### 4.5 rename / copy 不能绕过

**Rename：**禁用 rename inference 后，若一次 commit 把任何已有 path 改名到允许 path，Git 必须以原 path 删除 + 新 path 添加的 tree effect 暴露；原 path 会成为第三条/非法 path，因此 fail。

**Copy：**不启用 copy detection。若 source path 同时被修改或删除，它会作为额外 changed path 出现并 fail。若只是从 base 中一个完全未变化的文件复制内容到新 REQUEST/CURRENT path，则 Git 历史本身只发生允许 path 的新增；这不属于“隐藏的 production/source change”。最终新增文件仍必须通过下面的 captured-tree identity/content contract，因此复制来源本身不能绕过语义校验。

### 4.6 merge / side history 不能绕过

captured HEAD 必须只有一个 parent，并且该 parent精确等于 'CURRENT.base_commit'。因此 merge commit、第二 parent、side branch history 在进入 path diff 前就被拒绝。

不得使用 '--first-parent' 去忽略 merge side history后继续放行；本轮正确行为是 merge 直接 fail closed。

### 4.7 captured-tree artifact identity 继续完整校验

captured HEAD 中两份 path 必须是正常 first-bootstrap regular files，并继续校验：

- task key == caller task key；
- current branch == derived 'reviewed/<task_key>'；
- 'CURRENT.base_commit' == 唯一 parent；
- 'CURRENT.base_branch = main'；
- frozen Reviewed sibling worktree locator == cwd；
- 'CURRENT.state = PLAN_REQUESTED'；
- 'CURRENT.next_action = RUN_GPT_PLANNER'；
- 'CURRENT.plan_revision = 0'；
- 'CURRENT.implementation_commit = null'；
- REQUEST/CURRENT 的 task/base/worktree identity 相互一致。

如果当前已有 parser 能表达这些检查，复用 parser；不要建立第二套 schema。

所有 ancestry/path/status/blob/identity failure 必须发生在任何 remote/config mutation 前。

## 5. 为什么不采用“多 commit 全历史 union”方案

现实替代方案是：

~~~text
允许多个 metadata-only commits
-> 遍历 base_commit..captured_head 全部 reachable commits
-> 对每个 commit 的全部 parent/path effect 做 union
-> merge side history 也纳入审计
-> union 仍只能 REQUEST/CURRENT
~~~

本轮不选它，原因不是它做不到，而是当前 source 与 normal entry 没有需要：

- bootstrap 一次生成两份 tracked artifact；
- consumer 只需要把这两份 first-control metadata 做一次 ordinary commit；
- 一提交模型直接消除 revert laundering 与 merge side-history问题；
- 多 commit 审计会增加 revision-walk、merge-parent 和 path-union语义，没有真实用户价值。

只有以后出现直接源码/真实 consumer 证据表明单 commit 正常入口不够，才重新设计。

## 6. BR-FRP-F01 保持 CLOSED，不重新设计

继续原样冻结 Critic 已关闭的 atomic first-create contract。

caller 仍只有：

~~~text
--task-key
--expected-repo
~~~

helper 内部固定：

~~~text
branch = reviewed/<task_key>
destination = refs/heads/reviewed/<task_key>
source = captured_head
remote = origin

--force-with-lease=refs/heads/reviewed/<task_key>:
~~~

empty expected 的含义保持：destination ref 在 mutation 时必须不存在。

继续保持：

- caller 不能传 lease/OID/ref/refspec/force/destination/remote；
- raw 'git push --force-with-lease' 继续 gated；
- pre-read exact absence；
- exact captured-HEAD -> exact destination；
- no leading '+'；
- canonical GitHub HTTPS transport/config/hook/environment fences；
- push process success；
- post-read exact remote SHA == captured HEAD；
- helper不能更新任何 already-existing remote ref；
- ambiguous publication fail closed。

v0.3 不修改 F01 的 gate、权限模型或 transport 设计。

## 7. upstream 与 partial failure 保持不变

顺序继续冻结为：

~~~text
atomic remote create success
-> post-read remote SHA == captured HEAD
-> 才绑定 local upstream
~~~

进入 helper 时 'branch.<branch>.remote' 与 'branch.<branch>.merge' 必须未设置。

成功后只能绑定：

~~~text
branch.<branch>.remote = origin
branch.<branch>.merge = refs/heads/reviewed/<task_key>
~~~

如果 upstream bind 失败：

- 不删除 remote；
- 不 rewrite remote；
- 只允许回滚本 invocation 写入、且仍保持预期值的 local config；
- 返回 'REMOTE_CREATED_UPSTREAM_BIND_FAILED'；
- 不声称完整成功。

如果 push 结果不明确：

- 返回 ambiguous first publication；
- 不自动收养失败 push；
- 不 blind retry；
- 不 remote delete。

不新增 state/receipt/database。

## 8. Machine Policy 与 owner 保持不变

Critic 已接受的方向继续冻结：

'task publish-first' 在机械门禁完整后可以是一个窄 Machine Policy allow，因为 helper 能机械证明：

~~~text
current exact repo
+ exact committed bootstrap artifacts
+ captured HEAD is exactly one child commit of frozen base
+ exact A REQUEST/CURRENT only
+ PLAN_REQUESTED / RUN_GPT_PLANNER
+ exact derived reviewed/<task_key>
+ exact origin
+ atomic destination-must-not-exist
= one first-control-metadata publication
~~~

raw 'git push -u'、raw force-with-lease、任意 branch/ref/refspec/upstream、tag/delete/mirror/remap/custom transport 都继续 gated。

generic 'host publish-current-branch' public semantics 不变。  
reviewed_runner / watcher / Executor publication authority 不变。  
bootstrap zero-network contract 不变。

## 9. Presentations F03 truth 保持不变

本轮已读取当前 AI_Skills main 的：

'results/presentations--stage1-front-door-two-template-foundation/F03_BRIDGE_DEPENDENCY.md'

保持：

~~~text
PRES-S1-ER-F01 = CLOSED
PRES-S1-ER-F02 = CLOSED
PRES-S1-ER-F03 = STILL_OPEN
READY_FOR_CODEX = NO
~~~

F03 canonical owner 仍是 Bridge，Bridge task 仍是：

'reviewed-handoff--first-remote-publication'

本轮不得修改 Presentations consumer、Execution Package 或 Kickoff。

如果本 Bridge task 最终完成 design PASS -> execution-ready PASS -> implementation/tests -> fresh real-consumer validation -> installed/available command verification，才回 Presentations 做 narrow F03 re-review。

## 10. Capability / regression gates v0.3

同一个 final Bridge candidate 必须通过以下 gate；本轮只实质加强 FP-G2，其余 gate 保持 v0.2 语义。

### FP-G1 — atomic first-create

Brand-new Reviewed task：

~~~text
bootstrap
-> exact single first-control commit
-> publish-first
~~~

证明：

- fixed empty-expect lease 生效；
- concurrent same-name remote creation不能被 fast-forward；
- exact remote ref 首次创建；
- remote SHA == captured HEAD；
- same-name origin upstream 最终建立；
- 无第二次用户 approval。

### FP-G2 — history-safe first-publication fence

正例必须证明：

~~~text
captured HEAD has exactly one parent
parent == CURRENT.base_commit
rev-list(base..head) count == 1
base tree: REQUEST absent
base tree: CURRENT absent
single-commit --no-renames name-status:
A REQUEST
A CURRENT
captured-tree identity/state contract PASS
~~~

deterministic negatives 至少包括：

1. **history laundering / revert：**
   ~~~text
   base
   -> commit production/source path
   -> later revert/delete it
   -> commit REQUEST/CURRENT
   -> publish-first
   => FAIL BEFORE REMOTE/CONFIG MUTATION
   ~~~
2. 两个 metadata-only commits -> fail；
3. single commit + production source第三条 path -> fail；
4. single commit + tests/results/PLAN.md/other task metadata -> fail；
5. rename from unallowed path to allowed path -> no-renames 暴露额外 D/A -> fail；
6. copy + source changed/deleted -> source path额外出现 -> fail；
7. copied content only新增 allowed path但内容/identity不合法 -> artifact parser fail；
8. merge commit -> parent-count fail；
9. merge side history -> parent-count fail；
10. REQUEST/CURRENT 在 base 已存在 -> fail；
11. REQUEST/CURRENT status 不是 exact A/A -> fail；
12. missing/partial/mismatched blobs -> fail；
13. wrong task/base/worktree/state/next_action/plan_revision/implementation_commit -> fail；
14. dirty worktree -> fail。

所有负例都必须证明在任何 remote/config mutation 前停止。

### FP-G3 — dangerous neighbors remain gated

继续证明：

- raw 'git push -u'；
- raw 'git push --force-with-lease'；
- caller-supplied lease/OID/ref/refspec；
- arbitrary new branch；
- leading '+'；
- force/tag/delete/mirror；
- alternate remote/upstream；
- remote remap/custom transport

均不能进入 trusted path。

### FP-G4 — existing publisher regression

现有 'host publish-current-branch' existing same-name remote branch 的正负行为保持不变。

### FP-G5 — Reviewed lifecycle regression

保持：

- local artifact-bound resume；
- remote-only resume；
- 'materialize-worktree --mode resume'；
- watcher/Executor publication ownership；
- bootstrap zero-network。

### FP-G6 — fresh real consumer

fixture 全部通过后，用一个**新的 brand-new Reviewed task** 在真实 consumer repo 走：

~~~text
approved Kickoff
-> bootstrap
-> exact one-commit A/A control metadata
-> publish-first
-> remote SHA/upstream verification
-> external Planner handoff
~~~

已经手工 'git push -u' 的
'product-ui-copy--cross-plugin-production-integration'
只能作为 root-cause regression evidence，不能作为 fresh positive。

本设计轮不得创建 fresh consumer task，也不得借 Presentations task 偷跑 FP-G6。

## 11. Critic PASS 后的实现边界仍不变

只有 design Critic PASS 后，下一步才允许 Planner准备 execution package；仍不得直接实现。

未来 execution package 的 production delta 预计只允许：

- 'ai_bridge_kit/reviewed_handoff.py' 与 CLI route；
- 最小复用/抽取现有 Host push transport/config/environment/hook fence；
- Machine Policy / managed AGENTS 对一个 bounded action 的规则；
- Reviewed Handoff normal-entry docs；
- focused/full tests。

不得：

- 改 generic publisher public semantics；
- 改 bootstrap zero-network；
- 改 materialize/resume；
- 改 watcher authority；
- 加新 workflow/state/database/controller；
- 加 consumer workaround。

## 12. 外部事实复核与采用决定

2026-09-29 复核 Git 官方文档：

- 'git diff-tree' 可以直接比较两个 tree/commit；
- '--name-status' 输出 changed path 与 status；
- '--no-renames' 关闭 rename detection；
- merge commit 有多个 parent，Git 的 combined/first-parent 展示可能隐藏 side-history 细节，因此本 Plan 不尝试“看起来只改两条 path”后接受 merge，而是在 diff 前直接要求 captured HEAD 唯一 parent == frozen base；
- revision range 'base..head' 表示从 head 可达而从 base 不可达的 commit set，因此 count=1 与 direct-parent gate共同给出清楚的一提交证据。

采用：single direct-child commit + exact A/A no-renames tree effect。  
不采用：final-tree-only fence、first-parent merge忽略、multiple-commit history union。

References:
- https://git-scm.com/docs/git-diff-tree
- https://git-scm.com/docs/git-rev-list

## 13. Planner 结论

~~~text
PLANNER_RESULT=READY_FOR_CRITIC
PLAN_VERSION=0.3

BR-FRP-F01=
CLOSED_AND_UNCHANGED

BR-FRP-F02=
CLOSED_IN_DESIGN_BY_SINGLE_DIRECT_CHILD_COMMIT_FENCE

FIRST_PUBLICATION_HISTORY=
EXACTLY_ONE_COMMIT

CAPTURED_HEAD_PARENT_COUNT=
EXACTLY_ONE

CAPTURED_HEAD_ONLY_PARENT=
CURRENT_BASE_COMMIT

FIRST_COMMIT_NAME_STATUS=
EXACT_A_REQUEST_AND_A_CURRENT_ONLY

RENAME_DETECTION=
DISABLED

MERGE_HISTORY=
REJECTED

PRESENTATIONS_F03=
UNCHANGED_GENERIC_BRIDGE_DEPENDENCY

IMPLEMENTATION_AUTHORIZATION=
NO

EXECUTION_PACKAGE=
NOT_STARTED

NEXT_HANDOFF=
CRITIC
~~~

README checked: design-only revision; no update required now.  
CHANGELOG checked: design-only revision; no update required now.
