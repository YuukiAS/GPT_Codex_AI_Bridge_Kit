# Reviewed Handoff 首次远端发布设计 Plan v0.2

Plan version: **0.2**  
Date: **2026-09-29**  
Status: **READY FOR INDEPENDENT CRITIC RE-REVIEW / DESIGN ONLY**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Design topic: **reviewed-handoff--first-remote-publication**  
Source baseline: **main @ 6043689d6464fc64f51666a9198ffd509fff5a70**  
Previous Plan: **docs/design/reviewed_handoff_first_remote_publication_plan_v0.1_2026-09-29.md @ 54bf116c38638753a0579b5f18c19fc6c0239fd6**  
Critic review: **docs/design/reviewed_handoff_first_remote_publication_critic_review_v0.1_2026-09-29.md @ 6043689d6464fc64f51666a9198ffd509fff5a70**  
Stable blockers addressed: **BR-FRP-F01, BR-FRP-F02**

本 Plan 是完整替代版，不是 patch note。  
不得据此创建 implementation branch/worktree、修改 Machine Policy、修改 production source、安装/发布 Bridge、或为任何 consumer 写 workaround。

## 1. 结论与不变架构

保留 v0.1 已通过方向审查的 owner 与入口：

```text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
```

仍然不选择：

- 把 publication 放进 `task bootstrap`；
- 放宽 generic `host publish-current-branch`；
- raw `git push -u`；
- consumer-specific wrapper；
- authorization DB/token/receipt；
- watcher/controller/new workflow。

职责继续分开：

```text
task bootstrap
= 只建立本地 Reviewed task topology + REQUEST/CURRENT
= zero network

task publish-first
= 只发布 first-bootstrap control metadata
= 只创建此前不存在的 exact reviewed remote ref

host publish-current-branch
= 继续只更新 already-existing same-name remote branch
```

## 2. 根因保持不变

当前源码仍证明：

1. `reviewed-handoff task bootstrap` 只创建：
   - `reviewed/<task_key>`；
   - deterministic sibling worktree；
   - `REQUEST.md`；
   - `CURRENT.json`；
   - 本地空 `results/<task_key>/` 目录；
   且不 commit、不 push、不访问网络。

2. `host publish-current-branch` 要求：
   - current branch == expected branch；
   - `branch.<branch>.remote = origin`；
   - `branch.<branch>.merge = refs/heads/<branch>`；
   - remote same-name branch 已存在。

因此 brand-new Reviewed task 首次远端发布不是 consumer 缺陷，而是 Bridge 通用 Reviewed Handoff 缺口。

## 3. 正常生命周期

冻结正常路径：

```text
一次已批准的 exact Reviewed Kickoff
-> 现有 git fetch --all --prune
-> 现有 task bootstrap
-> 在 exact sibling worktree 中只提交 first-bootstrap REQUEST/CURRENT
-> task publish-first
-> atomic create-if-absent remote publication
-> post-read remote SHA == captured local HEAD
-> 建立 deterministic same-name origin upstream
-> external GPT Planner
-> 后续正常 Reviewed Handoff
```

`publish-first` 只负责第一次 control-plane handoff。  
Planner transaction、Executor implementation、CI/Reviewer publication 继续走现有 Reviewed 机制。

## 4. BR-FRP-F02：first-publication committed-path fence

这是 v0.2 的第一项新增机械门禁。

### 4.1 从 captured HEAD 读取 control metadata

helper 先冻结：

```text
current repo
current reviewed branch
captured_head = current HEAD
```

要求 worktree clean。

不得直接以可能变化的 working-tree 文件作为最终 authority；应从 captured HEAD tree 读取 exact：

```text
automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
```

解析 `CURRENT.json` 后取得冻结的 `base_commit`。

### 4.2 exact committed diff

计算：

```text
CURRENT.base_commit -> captured_head
```

的 committed changed paths。

要求 changed-path set **非空且严格等于**：

```text
automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
```

当前 bootstrap source 已核实：它实际写出的 tracked first-handoff artifact 只有这两份文件；`results/<task_key>/` 只是空目录，Git 不跟踪目录，因此 v0.2 不增加第三个 path。

建议 implementation 使用能区分状态且禁用 rename inference 的 committed-tree diff；两条路径都应表现为从 base 中不存在到 captured HEAD 中存在的 exact first-bootstrap artifact。任何其他 committed path 都 fail closed。

明确拒绝：

- production source；
- tests；
- arbitrary `results/**`；
- `PLAN.md`；
- unrelated docs；
- 其他 task metadata；
- generated files；
- private artifacts。

### 4.3 blob/state identity

captured HEAD 中两份 blob 都必须存在并通过现有/共享 parser 校验：

- task key == caller task key；
- branch 只能派生为 `reviewed/<task_key>`；
- base commit == `CURRENT.base_commit`；
- base branch == `main`；
- frozen Reviewed sibling worktree locator == current cwd；
- `CURRENT.state = PLAN_REQUESTED`；
- `CURRENT.next_action = RUN_GPT_PLANNER`；
- `CURRENT.plan_revision = 0`；
- `CURRENT.implementation_commit = null`；
- captured HEAD descends from `CURRENT.base_commit`。

只要 path fence 或 metadata identity 任一失败，remote/config mutation 都不得开始。

## 5. BR-FRP-F01：atomic create-if-absent

v0.1 的：

```text
ls-remote absent
-> ordinary non-force push
```

存在 TOCTOU，因此 v0.2 改为 Git-native atomic absence assertion。

### 5.1 caller 永远不能选择 lease

caller 仍只有：

```text
--task-key
--expected-repo
```

helper 内部固定派生：

```text
branch = reviewed/<task_key>
destination = refs/heads/reviewed/<task_key>
source = captured_head
remote = origin
```

内部固定 atomic guard 等价于：

```text
--force-with-lease=refs/heads/reviewed/<task_key>:
```

这里 empty expected value 的唯一语义是：

```text
destination ref must not already exist
```

不得暴露任何参数让 caller 提供：

- lease；
- expected OID；
- ref；
- refspec；
- force；
- destination；
- remote。

raw `git push --force-with-lease` 继续走现有审批路径。

### 5.2 exact push effect

在通过所有前置门禁后，唯一允许的 push effect 为：

```text
origin
captured_head:refs/heads/reviewed/<task_key>
```

配合上述 fixed empty-expect lease。

继续保留 generic publisher 已有的有效安全边界：

- GitHub HTTPS fetch/push identity；
- no custom SSH/askpass/config transport injection；
- no active pre-push hook；
- no mirror；
- `push.followTags=false`；
- no submodule recursion；
- no push option；
- no signed-push expansion；
- sanitized environment；
- final repo/branch/HEAD/config recheck。

不得使用 leading `+`。  
不得 tag/delete/mirror。  
不得 remote remap。  
不得 alternate upstream。

### 5.3 pre-read 与 post-read 仍保留

atomic lease 是 mutation-time authority；pre/post read 仍有诊断与最终 identity 价值。

push 前仍做 exact：

```text
ls-remote --heads origin refs/heads/reviewed/<task_key>
```

要求 absent。

push 后必须重新读取 exact remote ref。

成功必须同时满足：

1. push process 本身报告成功；
2. post-read 只有 exact destination；
3. remote SHA == captured_head。

如果 push process 失败，即使 post-read 恰好等于 captured_head，也**不得**把它自动收养为本 invocation 成功，因为可能是并发 actor 创建了相同 SHA。

如果结果不明确：

```text
AMBIGUOUS_FIRST_PUBLICATION
```

fail closed；不得盲目重试，不得删除 remote ref。

## 6. upstream 绑定顺序

v0.2 冻结：**先完成并确认 remote create，再绑定 local upstream。**

理由：

- push 前写 upstream 会让 failed/lease-rejected first-create 留下误导性 tracking config；
- `--set-upstream` 不能依赖为 captured SHA source 自动建立 current branch upstream；
- upstream 不是 remote create 的安全前提，后续 generic publisher 才需要它。

进入 helper 时要求：

```text
branch.<branch>.remote
branch.<branch>.merge
```

均未设置。

只有在：

```text
push success
AND
post-read remote SHA == captured_head
```

之后，才允许设置：

```text
branch.<branch>.remote = origin
branch.<branch>.merge = refs/heads/reviewed/<task_key>
```

随后重新读取两项配置并要求 exact match。

如果 local upstream binding 失败：

- remote ref 不得 rollback/delete；
- 只回滚本 invocation 已写入、且仍保持 invocation expected value 的 local branch config；
- 返回明确 partial failure：`REMOTE_CREATED_UPSTREAM_BIND_FAILED`；
- 不把任务标成正常完成。

这样 remote publication 与 local tracking 的 authority 不混淆，也不需要新 receipt/state field。

## 7. Machine Policy 与授权边界

Critic 已接受方向：在机械门禁完整后，`task publish-first` 可以是一个窄 Machine Policy allow。

其 authority 不是“创建任意 branch”，而是：

```text
current exact repo
+ current exact reviewed sibling
+ existing committed bootstrap artifacts
+ initial PLAN_REQUESTED/RUN_GPT_PLANNER state
+ exact two-file control-only diff
+ exact derived reviewed/<task_key>
+ exact origin
+ atomic destination-must-not-exist assertion
= one first-control-metadata publication
```

managed Host 行为文字必须明确：

- 用户已批准 exact Reviewed task/branch/worktree 的 Kickoff 后，
  exact first publication 使用 `reviewed-handoff task publish-first`，不重复索权；
- raw `git push -u`、raw `--force-with-lease`、任意新 branch、alternate upstream、
  force/tag/delete/mirror/refspec/remap 继续 gated。

不得新增 authorization DB/token/receipt、新 CURRENT field、watcher 或 controller。

## 8. 与 Presentations Stage 1 的关系

已直接读取当前 AI_Skills main。

Presentations Stage 1 当前唯一未关闭 execution-ready blocker 是：

```text
PRES-S1-ER-F03
= Current Bridge cannot perform required first remote publication
  through an approved bounded normal entry
```

其 canonical dependency 文件已经把 owner/task 明确绑定到：

```text
YuukiAS/GPT_Codex_AI_Bridge_Kit
reviewed-handoff--first-remote-publication
```

而 Presentations v1.1 Kickoff 的首次发布要求恰好是：

```text
bootstrap
-> PLAN_REQUESTED / RUN_GPT_PLANNER
-> commit/publish only first-bootstrap REQUEST/CURRENT
-> no Presentations production source
-> no PLAN.md
-> hand ownership to external GPT Planner
```

这与 v0.2 的 committed-path fence **完全同一问题、同一正常入口**。

因此当前结论：

```text
PRESENTATIONS_NEEDS_ADDITIONAL_BRIDGE_ARCHITECTURE = NO
PRESENTATIONS_F03_IS_THIS_EXACT_BRIDGE_TASK = YES
```

Bridge v0.2 若经 Critic PASS、execution-ready PASS、实现/测试、fresh real-consumer 验证并实际安装可用，Presentations 只需回到 F03 做 narrow re-review。

当前 Presentations v1.1 使用的是泛化措辞：

```text
Use only the repository's currently authorized bounded publication route.
```

因此若最终 production command 与本 Plan 一致，按其自己的
`F03_BRIDGE_DEPENDENCY.md`，不需要为了命令名字机械创建 Presentations v1.2。

本轮不得修改 Presentations consumer package。

## 9. Capability / regression gates v0.2

同一个 final Bridge candidate 必须通过：

### FP-G1 — atomic first-create positive

Brand-new Reviewed task：

```text
bootstrap
-> exact two-file control commit
-> publish-first
```

证明：

- fixed empty-expect lease 实际生效；
- destination 在 mutation 时必须不存在；
- exact remote ref 首次创建；
- remote SHA == captured HEAD；
- deterministic same-name origin upstream 最终建立；
- 无第二次用户 approval。

并加入并发 fixture：pre-read 后另一个 actor 创建 destination，即使其 tip 是 captured HEAD 的 ancestor，publish-first 也必须被 empty-expect lease 拒绝，不得 fast-forward 已存在 ref。

### FP-G2 — first-publication path / identity fence

至少覆盖：

- exact two-path positive；
- production source committed -> fail；
- tests committed -> fail；
- `PLAN.md` committed -> fail；
- results artifact committed -> fail；
- other task metadata committed -> fail；
- REQUEST/CURRENT missing/partial/mismatched -> fail；
- wrong task/base/worktree/state/next_action -> fail；
- dirty worktree -> fail；
- stale/non-descendant base -> fail；
- remote already exists -> fail；
- alternate/noncanonical transport/config/hook/environment -> fail。

任何失败必须发生在 remote/config mutation 前。

### FP-G3 — dangerous neighbors remain gated

证明：

- raw `git push -u`；
- raw `git push --force-with-lease`；
- caller-supplied lease/OID/ref/refspec；
- arbitrary new branch；
- leading `+`；
- force；
- tag/delete/mirror；
- alternate remote/upstream；
- remote remap/custom transport

均不进入 trusted path。

### FP-G4 — existing publisher regression

当前 `host publish-current-branch` 的 existing same-name remote branch 正负行为保持不变。

### FP-G5 — Reviewed resume regression

保持：

- local artifact-bound resume；
- remote-only resume；
- `materialize-worktree --mode resume`；
- watcher/Executor publication ownership。

### FP-G6 — fresh real consumer

fixture 全部通过后，用一个**新的 brand-new Reviewed task** 在真实 consumer repo 走：

```text
approved Kickoff
-> bootstrap
-> exact control-only commit
-> publish-first
-> remote SHA/upstream verification
-> external Planner handoff
```

已经手工 `git push -u` 过的
`product-ui-copy--cross-plugin-production-integration`
只能作为 root-cause regression evidence，不能作为 fresh positive。

Presentations Stage 1 可以在 Bridge central implementation 完成后作为真实 dependent re-review，但本设计轮不得用尚未启动的 Presentations task偷跑 FP-G6。

## 10. 实现边界（仅 Critic PASS 后进入 execution package）

预计 production delta 仍限制在：

- `ai_bridge_kit/reviewed_handoff.py` 与 CLI routing；
- 复用或最小抽取现有 Host push transport/config/environment/hook fence；
- Host Machine Policy / managed AGENTS 对一个新 bounded action 的规则；
- Reviewed Handoff normal-entry docs；
- focused + full regression tests。

不允许：

- 改 generic `publish-current-branch` public semantics；
- 改 bootstrap zero-network contract；
- 改 materialize/resume semantics；
- 改 watcher publication authority；
- 新 workflow/state/database/controller；
- consumer workaround。

## 11. 外部与本地现实核查

2026-09-29 复核 Git 官方 `git-push` 文档：

- explicit refspec 固定 source/destination；
- 普通 branch update 只允许 fast-forward；
- `--force-with-lease=<refname>:<expect>` 会比较 exact expected remote value；
- 当 `<expect>` 为空字符串时，named remote ref **必须不存在**；
- `--set-upstream` 负责建立 tracking information，但 upstream 本质保存为 branch 的 `remote` / `merge` 配置。

本轮还用 disposable local Git repo 验证：
对 **captured commit SHA source** 使用
`git push --set-upstream ... <sha>:<dst>`
不能作为可靠的 current-branch upstream 建立机制，因此 v0.2 不把 remote create 与 upstream 设置混进一个隐式假设；upstream 在 successful post-read 后显式、确定性绑定。

Reference:
https://git-scm.com/docs/git-push

## 12. Planner 结论

```text
PLANNER_RESULT=READY_FOR_CRITIC
PLAN_VERSION=0.2

BR-FRP-F01=
ADD_FIXED_EMPTY_EXPECT_LEASE_ATOMIC_CREATE_IF_ABSENT

BR-FRP-F02=
ADD_EXACT_TWO_FILE_COMMITTED_DIFF_FENCE

SELECTED_ARCHITECTURE=
REVIEWED_TASK_PUBLISH_FIRST

BOOTSTRAP_NETWORK_BOUNDARY_CHANGE=NO
GENERIC_PUBLISHER_BEHAVIOR_CHANGE=NO
RESUME_BEHAVIOR_CHANGE=NO
WATCHER_AUTHORITY_CHANGE=NO

PRESENTATIONS_F03=
SAME_GENERIC_BRIDGE_GAP

PRESENTATIONS_NEEDS_ADDITIONAL_BRIDGE_ARCHITECTURE=NO

IMPLEMENTATION_AUTHORIZATION=NO
NEXT_HANDOFF=CRITIC
```

README checked: design-only revision; no update required now.  
CHANGELOG checked: design-only revision; no update required now.
