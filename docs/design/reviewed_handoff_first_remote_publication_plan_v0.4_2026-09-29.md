# Reviewed Handoff 首次远端发布设计 Plan v0.4

Plan version: **0.4**  
Date: **2026-09-29**  
Status: **READY FOR INDEPENDENT CRITIC RE-REVIEW / DESIGN ONLY**  
Target repo: **YuukiAS/GPT_Codex_AI_Bridge_Kit**  
Design topic: **reviewed-handoff--first-remote-publication**  
Source branch/ref: **main**  
Source baseline: **main @ 7573dba5a9d8085480d25feab7e86ccd90d6538f**  
Previous Plan: **docs/design/reviewed_handoff_first_remote_publication_plan_v0.3_2026-09-29.md @ 7573dba5a9d8085480d25feab7e86ccd90d6538f**  
Prior durable Critic review: **docs/design/reviewed_handoff_first_remote_publication_critic_review_v0.1_2026-09-29.md @ 6043689d6464fc64f51666a9198ffd509fff5a70**  
Current Critic handoff: **BR-FRP-F01=CLOSED; BR-FRP-F02=STILL_OPEN; NEW_BLOCKERS=NONE**

本 Plan 是 v0.3 的完整替代版，不是 patch note。本轮只补 `BR-FRP-F02` 的 raw-object truth fence。  
不得据此修改 production source、创建 implementation branch/worktree、修改或安装 Machine Policy、发布 Bridge、修改 Presentations consumer、准备 execution package，或新增 workflow/state/database/token/receipt/watcher/controller。

## 1. 已通过内容全部冻结

继续使用已经通过方向审查的入口：

~~~text
ai-bridge reviewed-handoff task publish-first \
  --task-key <semantic-task-key> \
  --expected-repo <owner/repo>
~~~

继续保持：

~~~text
BR-FRP-F01 = CLOSED

first publication history = exactly one commit

captured HEAD = exactly one direct child of CURRENT.base_commit

single commit tree effect =
A automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
A automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
only

rename detection = disabled
merge = rejected
copy distinction = unchanged
~~~

同时保持：

- bootstrap zero-network；
- generic `host publish-current-branch` semantics 不变；
- fixed internal empty-expect lease；
- remote create + post-read 成功后才绑定 upstream；
- ambiguous publication fail closed；
- reviewed_runner / watcher / Executor publication authority 不变；
- Presentations F03 仍绑定本 Bridge task；
- 不新增 gate。

## 2. 当前唯一剩余风险：validation view 与 pushed object truth 分离

v0.3 已经关闭普通 history laundering、revert、rename 与 merge side-history，但 security-critical Git inspection 仍可能默认读取 replacement-adjusted logical view。

Git 官方 `git-replace` 文档确认：

- replacement refs 位于 `refs/replace/*`；
- replacement objects 默认被绝大多数 Git commands 使用；
- `git --no-replace-objects <command>` 可固定关闭 replacement object substitution；
- **pack transfer** 属于默认不使用 replacement objects 的 reachability/transfer 路径。

因此存在真实 mismatch：

~~~text
实际 captured HEAD object/tree
= REQUEST + CURRENT + forbidden source

refs/replace/<HEAD>
= benign replacement
  parent = base
  tree = REQUEST + CURRENT only

普通 cat-file / diff-tree / history inspection
= 可能看到 replacement view

push / pack transfer
= 发布实际原始 commit object
~~~

本轮 disposable Git probe 复现了这一点：

- 普通 `git cat-file commit <HEAD>` 看到 replacement tree；
- `git --no-replace-objects cat-file commit <HEAD>` 看到原始 tree；
- 普通 `git diff-tree` 只看到 REQUEST/CURRENT；
- no-replacement `diff-tree` 额外看到 `src/leak.txt`；
- 实际 push 后 remote tree 确实包含 `src/leak.txt`。

这证明该风险不是理论假设。

Git 的 legacy `info/grafts` 还可以伪造 commit parents。官方 repository layout 与 Git source 都确认 graft file 用 fake parent records 改写 ancestry view，因此普通 revision traversal 不能作为 raw-parent authority。

## 3. 现实方案比较

### 方案 A：禁止任何 replacement ref

优点：概念简单。

问题：

- replacement refs 可能与当前 task 无关；
- loose/packed refs 都要正确发现；
- 仍需单独处理 legacy graft；
- 比“只让安全检查忽略 replacement”更宽、更扰民。

不选。

### 方案 B：raw-object authority + active graft fail-closed

做法：

- security-critical inspection 固定使用 `git --no-replace-objects`；
- parent/tree/blob/path 全部从原始 object identity 读取；
- active `info/grafts` 直接 fail closed；
- push 也使用同一固定 no-replacement invocation，确保 validation 与 mutation command 的 object semantics 对齐。

这是最小方案，选择。

### 方案 C：Bridge 自己解析 object database / packfile

能得到 raw truth，但等于重写 Git plumbing，复杂且没有必要。

不选。

## 4. Raw-object authority contract

### 4.1 固定 no-replacement Git invocation

所有决定 first-publication 安全性的 Git object/history commands，必须由 helper 自己固定成：

~~~text
git --no-replace-objects <command>
~~~

或一个实现上完全等价、调用者不可覆盖的固定机制。

至少包括：

- captured HEAD/object type resolution；
- raw commit content；
- raw parent/tree extraction；
- base commit raw content；
- tree/path comparison；
- exact tree entry/blob lookup；
- REQUEST/CURRENT blob读取；
- secondary revision-count consistency check；
- final pre-mutation raw-object recheck；
- actual push invocation。

caller 不能通过参数、环境或 config 选择是否启用 replacement objects。

不得把“当前 repo 没有 replace ref”当成安全前提；即使存在与本 task 无关的 replacement refs，security-critical authority仍必须读取原始 objects。

### 4.2 captured HEAD 必须是原始 commit OID

冻结：

~~~text
captured_head = exact current HEAD ref OID
~~~

随后使用 no-replacement object read 验证它确实是 commit object。

不能用 replacement-adjusted pretty history 产生另一个“逻辑 HEAD”作为发布 authority。

## 5. Raw direct-parent authority

v0.3 的“一提交模型”不变，但 parent authority 改为 raw commit object。

helper 必须读取：

~~~text
git --no-replace-objects cat-file commit <captured_head>
~~~

或等价 raw commit-content primitive。

从**实际 commit object header**直接提取：

- `tree <oid>`
- 全部 `parent <oid>`

要求：

~~~text
raw parent count = 1
raw only parent = CURRENT.base_commit
~~~

这才是 BR-FRP-F02 的核心 ancestry authority。

不得仅依赖：

- `git log`；
- 普通 `rev-list`；
- replacement/graft-adjusted history display；
- first-parent presentation。

同样读取 `CURRENT.base_commit` 的原始 commit object，并取得其 raw tree OID。

## 6. Legacy info/grafts：最小 fail-closed

Git grafts 会让 Git pretend commit parent set 与真实 commit object 不同。

v0.4 不新增 graft-aware ancestry engine，而是直接把 active graft 排除出 trusted first-publication safe class。

### 6.1 正确定位

在 linked worktree 中不得猜 `.git/info/grafts`。

使用 Git 自己的 repository path resolution，等价于：

~~~text
git rev-parse --path-format=absolute --git-path info/grafts
~~~

以取得实际 graft path；这会遵守 worktree/common-dir 布局。

### 6.2 active graft 定义

Git 当前 source 对 graft file 的行为是：

- trailing whitespace trim；
- blank line忽略；
- 第一字符为 `#` 的行忽略；
- 其他行尝试解析为 graft record。

因此 trusted helper 可采用更保守但仍准确的门禁：

- 文件不存在：PASS；
- 仅 blank / 第一字符 `#` comment lines：PASS；
- 任何其他非空记录行：FAIL CLOSED；
- malformed non-comment record：同样 FAIL CLOSED，不尝试修复。

失败语义：

~~~text
ACTIVE_GRAFTS_REQUIRE_ORDINARY_APPROVAL
~~~

不修改、不删除、不 convert graft file。

### 6.3 recheck

active-graft check 至少：

1. initial raw-object preflight；
2. final pre-push safety recheck；

都必须执行。

raw direct-parent object check 仍是核心 authority；graft check 是为了禁止 revision-traversal view 与 raw object truth 分叉。

## 7. Raw tree/path/blob authority

### 7.1 不从 replacement-adjusted commit 取 tree

从 raw base commit 与 raw captured HEAD commit header分别取得：

~~~text
base_tree_oid
head_tree_oid
~~~

所有后续 path/blob检查都从这两个原始 tree OID 出发。

### 7.2 exact single-commit tree effect

仍要求 captured HEAD raw only parent == base。

然后在 no-replacement authority 下比较 raw trees，等价于：

~~~text
git --no-replace-objects diff-tree   -r   --name-status   --no-renames   -z   <base_tree_oid>   <head_tree_oid>
~~~

结果必须严格是：

~~~text
A automation/reviewed_handoff/tasks/<task_key>/REQUEST.md
A automation/reviewed_handoff/tasks/<task_key>/CURRENT.json
~~~

且无第三条 raw path。

两条允许 path 在 raw base tree 中必须不存在。

rename/copy/merge语义继续沿用 v0.3：

- rename detection disabled；
- changed/deleted copy source成为额外 path则 fail；
- unchanged source + 新增合法 path不构成隐藏 source change；
- merge因 raw parent count != 1 直接 fail。

### 7.3 raw blob identity

从 raw `head_tree_oid` 解析两条 exact tree entries。

两者必须是普通 file/blob，不得是 symlink、submodule 或 tree。

随后用 no-replacement raw blob read读取 REQUEST/CURRENT 内容，并复用现有 schema/parser semantics 校验：

- task key；
- base commit/base branch；
- frozen sibling worktree locator；
- `PLAN_REQUESTED`；
- `RUN_GPT_PLANNER`；
- `plan_revision=0`；
- `implementation_commit=null`；
- REQUEST/CURRENT task/base/worktree identity一致。

不得先用普通 `HEAD:path` 读取 replacement-adjusted blob，再声称是 raw authority。

## 8. rev-list 只降级为一致性证据

v0.3 的：

~~~text
CURRENT.base_commit..captured HEAD reachable commit count = 1
~~~

可以保留，但不再是核心 security authority。

只有在：

- active graft check PASS；
- no-replacement mode固定；

之后才可执行 secondary `rev-list` consistency check。

即使该 secondary check 异常，也只能导致 fail closed；它绝不能覆盖或替代：

~~~text
raw captured HEAD commit
-> exact one raw parent
-> raw parent == CURRENT.base_commit
~~~

raw direct-parent object truth 才决定“一提交”合同是否成立。

## 9. Mutation command 与 raw truth 对齐

Git 官方文档已经说明 pack transfer 默认不使用 replacement objects；本 Plan 仍选择更明确的固定 mutation invocation：

~~~text
git --no-replace-objects push ...
~~~

理由不是增加新权限，而是让 validation 和 mutation 都显式处于同一个 no-replacement object语义下，避免未来实现者误读。

其余 BR-FRP-F01 已通过合同完全不变：

~~~text
--force-with-lease=refs/heads/reviewed/<task_key>:
~~~

caller仍不能传：

- lease；
- expected OID；
- ref；
- refspec；
- force；
- destination；
- remote。

继续保留：

- exact pre-read absence；
- exact captured raw HEAD -> exact destination；
- no leading `+`；
- canonical GitHub HTTPS transport/config/hook/environment fences；
- push success；
- post-read remote SHA == captured raw HEAD；
- already-existing remote ref永远不可被 helper更新。

## 10. Final pre-mutation recheck

任何 remote/config mutation 前，helper 必须再次确认：

- current repo/worktree不变；
- current branch仍是 derived reviewed branch；
- current HEAD OID == captured_head；
- worktree clean；
- active graft仍不存在；
- raw captured HEAD commit object仍满足 exact parent/tree identity；
- raw base/head tree diff仍只有 exact A/A REQUEST/CURRENT；
- raw blobs仍通过 identity/state contract；
- remote/config/transport/hook/environment仍满足既有 fences；
- remote exact destination仍 absent；
- upstream仍未设置。

如果其中任何一项变化，FAIL CLOSED。

这不是新 state machine，只是同一个 bounded mutation 前的 final safety recheck。

## 11. 普通 history laundering / rename / merge gate不回归

v0.4 仍要求：

~~~text
actual raw HEAD
= exactly one direct child of raw CURRENT.base_commit

raw tree effect
= exact A REQUEST + A CURRENT only
~~~

因此以下旧攻击继续 fail：

- production/source commit -> revert/delete -> metadata commit；
- 两个 metadata-only commits；
- one commit + third path；
- rename unallowed path -> allowed path；
- merge commit；
- merge side history；
- REQUEST/CURRENT在 base已存在；
- status不是 exact A/A。

raw-object fence只是确保这些判断观察到的就是**将被发布的原始 object truth**，没有重新设计一提交模型。

## 12. FP-G2 更新：不新增 Gate

这仍属于现有 `FP-G2 — history-safe first-publication fence`，不新增 Gate。

除 v0.3 已冻结 negatives 外，至少新增两个 deterministic regression：

### FP-G2-R15 — replace-ref view split

构造：

~~~text
actual captured HEAD:
  raw parent = base
  raw tree =
    A REQUEST
    A CURRENT
    A src/leak.txt

refs/replace/<HEAD>:
  benign replacement commit
  parent = base
  tree =
    A REQUEST
    A CURRENT
~~~

证明普通 replacement-aware Git view可以看似 benign。

然后运行 `publish-first`：

~~~text
=> MUST FAIL BEFORE ANY REMOTE/CONFIG MUTATION
=> failure is caused by raw no-replacement tree/path fence
~~~

并证明 remote ref未创建、upstream未写入。

### FP-G2-R16 — info/grafts ancestry spoof

构造实际多提交 history，使普通 ancestry traversal在 active `info/grafts` 下看似：

~~~text
HEAD parent = base
base..HEAD count = 1
~~~

然后运行 `publish-first`：

~~~text
=> MUST FAIL BEFORE ANY REMOTE/CONFIG MUTATION
=> ACTIVE_GRAFTS_REQUIRE_ORDINARY_APPROVAL
~~~

不允许 helper自动删除/convert graft。

### 既有 FP-G2 negatives继续保留

包括：

- revert/history laundering；
- multiple metadata commits；
- third production/test/result/PLAN/doc/task path；
- rename bypass；
- changed/deleted copy source；
- invalid copied artifact content；
- merge/side history；
- base已有 REQUEST/CURRENT；
- non-A/A status；
- missing/partial/mismatched blobs；
- wrong task/base/worktree/state/action/revision/implementation identity；
- dirty worktree。

所有失败都必须在 remote/config mutation 前。

## 13. FP-G1–FP-G6 整体保持

### FP-G1
atomic first-create；`BR-FRP-F01` 继续 CLOSED。

### FP-G2
本轮只增加 raw-object / graft truth fence；不拆新 Gate。

### FP-G3
raw `git push -u`、raw force-with-lease、caller lease/ref/refspec、arbitrary branch、force/tag/delete/mirror/remap/alternate upstream继续 gated。

### FP-G4
generic `host publish-current-branch` existing-branch semantics不变。

### FP-G5
local/remote-only materialize/resume、watcher authority、bootstrap zero-network不变。

### FP-G6
仍必须使用一个新的真实 consumer task。

已经手工 `git push -u` 的
`product-ui-copy--cross-plugin-production-integration`
只能作为 root-cause evidence，不能冒充 fresh positive。

本设计轮不得创建 FP-G6 task。

## 14. Presentations dependency保持不变

当前 AI_Skills main 仍记录：

~~~text
PRES-S1-ER-F01 = CLOSED
PRES-S1-ER-F02 = CLOSED
PRES-S1-ER-F03 = STILL_OPEN
READY_FOR_CODEX = NO
~~~

F03 仍绑定：

~~~text
YuukiAS/GPT_Codex_AI_Bridge_Kit
reviewed-handoff--first-remote-publication
~~~

本轮 raw-object truth fence不改变 consumer contract，因此：

~~~text
PRESENTATIONS_DEPENDENCY_CHANGE = NO
PRESENTATIONS_MUTATION = NO
~~~

只有 Bridge 完成 design PASS -> execution-ready PASS -> implementation/tests -> fresh real-consumer validation -> installed/available command verification 后，才回 Presentations做 narrow F03 re-review。

## 15. 实现边界仍未授权

本轮不得准备 execution package。

如果后续 design Critic PASS，Planner才可进入下一阶段，预计实现边界仍只可能涉及：

- `ai_bridge_kit/reviewed_handoff.py` 与 CLI route；
- 最小复用/抽取 Host transport/config/environment/hook fence；
- Machine Policy / managed AGENTS一个 bounded action；
- Reviewed Handoff docs；
- focused/full regression tests。

本 Plan 不授权任何这些实现动作。

## 16. 外部事实与现实 probe

2026-09-29 已复核：

Git `git-replace` 官方文档：
- replacement refs默认影响多数 Git commands；
- `git --no-replace-objects` 可禁用；
- pack transfer属于默认不使用 replacement refs 的例外。

Git repository layout：
- `info/grafts` 记录 fake commit ancestry；
- graft机制已过时并会造成 object transfer问题。

Git worktree / rev-parse：
- linked worktree 中不要自行猜 `$GIT_DIR` / `$GIT_COMMON_DIR`；
- `git rev-parse --git-path ...` 应用于直接访问 repository-internal path。

Git source `commit.c`：
- graft parser忽略空行与第一字符为 `#` 的 comment；
- 其他行按 fake parent record解析。

本轮 disposable local probe同时确认：
- replacement-aware cat-file/diff可隐藏 raw forbidden path；
- no-replacement cat-file/diff可看到 raw path；
- push后的 bare remote得到 raw original commit/tree；
- active info/grafts可让普通 rev-list count看成伪造的一提交，而 raw cat-file parent仍显示真实 parent。

References:
- https://git-scm.com/docs/git-replace
- https://git-scm.com/docs/gitrepository-layout
- https://git-scm.com/docs/git-worktree
- https://git-scm.com/docs/git-rev-parse
- https://github.com/git/git/blob/master/commit.c

## 17. Planner 结论

~~~text
PLANNER_RESULT=READY_FOR_CRITIC
PLAN_VERSION=0.4

BR-FRP-F01=
CLOSED_AND_UNCHANGED

BR-FRP-F02=
CLOSED_IN_DESIGN_BY_RAW_OBJECT_TRUTH_FENCE

REPLACEMENT_OBJECTS=
IGNORED_FOR_ALL_SECURITY_CRITICAL_INSPECTION

RAW_GIT_AUTHORITY=
GIT_NO_REPLACE_OBJECTS_FIXED_BY_HELPER

RAW_PARENT_AUTHORITY=
CAT_FILE_ACTUAL_COMMIT_OBJECT

RAW_TREE_BLOB_AUTHORITY=
ACTUAL_OBJECT_OIDS_ONLY

ACTIVE_INFO_GRAFTS=
FAIL_CLOSED

REV_LIST=
SECONDARY_CONSISTENCY_ONLY

FIRST_PUBLICATION_HISTORY=
EXACTLY_ONE_RAW_DIRECT_CHILD_COMMIT

FIRST_COMMIT_RAW_TREE_EFFECT=
EXACT_A_REQUEST_AND_A_CURRENT_ONLY

BR-FRP-F01_ATOMIC_LEASE=
UNCHANGED

UPSTREAM_SEQUENCE=
UNCHANGED

AMBIGUOUS_PUBLICATION=
UNCHANGED_FAIL_CLOSED

GENERIC_PUBLISHER=
UNCHANGED

WATCHER_AUTHORITY=
UNCHANGED

BOOTSTRAP_ZERO_NETWORK=
UNCHANGED

PRESENTATIONS_F03=
UNCHANGED_GENERIC_BRIDGE_DEPENDENCY

NEW_GATE=
NO

IMPLEMENTATION_AUTHORIZATION=
NO

EXECUTION_PACKAGE=
NOT_STARTED

NEXT_HANDOFF=
CRITIC
~~~

README checked: design-only revision; no update required now.  
CHANGELOG checked: design-only revision; no update required now.
