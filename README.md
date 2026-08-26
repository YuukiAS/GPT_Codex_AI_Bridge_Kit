# GPT-Codex AI Bridge Kit

这是一个用来组织 **ChatGPT/GPT 与 Codex 协作** 的本地工具包。

它解决的问题很实际：项目做久以后，真正麻烦的往往不是“让 Codex 写代码”，而是怎么让不同机器上的 Codex 遵守同一套长期规则，怎么把 GPT 的规划稳定交给 Codex，怎么在重要任务结束前增加独立复核，以及怎么把论文、通知、视觉检查这些能力接进现有科研仓库，而不是每个项目重新搭一套脚手架。

这个仓库的原则是：**默认保持简单，需要什么再加什么。** 普通项目只需要机器级规则和基础交接；只有确实需要时，才启用独立复核、高风险闭环、邮件通知、Overleaf 同步或视觉复核。

当前版本：`0.6.0`。

## 功能与版本

| 能力 | 首次引入 | 作用 |
|---|---:|---|
| Lite Handoff | `0.1.0` | 最基础的 GPT → Codex → 复核文件交接 |
| Host Policy | `0.2.0` | 一台机器上的 Codex 长期配置、Git 行为和通用规则 |
| Generic Notifier | `0.3.0` | 任务合法终态后发送邮件通知 |
| Agent-Flow Core | `0.4.0` | 高风险任务的严格多角色验证闭环 |
| Reviewed Handoff | `0.5.0` | GPT 规划、Codex 执行、GPT 最多两轮独立复核 |
| Visual Review | `0.5.2` | 对图片、PPT 截图等生成可验证视觉证据 |
| Overleaf Bridge | `0.6.0` | 科研单一仓库中只把论文目录安全同步到 Overleaf |

本项目采用 `0.x` 迭代方式。每个 `0.x` 小版本通常代表一项可独立使用的能力进入稳定工作流；后面的补丁版本主要用于安全性、兼容性和默认行为修正。这不是严格的 Semantic Versioning 承诺，而是当前阶段的版本阅读方式。

`0.2.1`、`0.3.1`、`0.5.1`、`0.5.3`、`0.5.4` 主要是已有能力的行为完善、安全修复或默认配置更新，不是新的顶层安装层：

- `0.2.1`：完善 Host Policy 的用户可见中文叙述策略。
- `0.3.1`：Notifier 输出改为中文优先。
- `0.5.1`：稳定 External GPT 等待规则和 Host Policy Git 授权语义。
- `0.5.3`：稳定 Visual Review 的 GitHub Actions 安装和证据文件写回。
- `0.5.4`：更新 Visual Review 默认模型。

## 一眼看懂：我到底该装什么

整个工具包分成三层。

```text
机器层：一台机器 / 一个 CODEX_HOME 配一次
└── Host Policy

项目层：每个 Git 仓库按需安装
├── Lite Handoff          基础 GPT ↔ Codex 交接，默认推荐
├── Reviewed Handoff      GPT 先规划，Codex 执行，再由 GPT 独立复核
├── Generic Notifier      任务结束后发邮件
├── Overleaf Bridge       只把论文目录同步到 Overleaf
├── Visual Review         对图片、PPT 截图等做独立视觉检查
└── Agent-Flow Core       高风险任务的严格闭环

任务层：某一次具体工作的实例
├── Lite 任务
├── Reviewed Handoff 任务
└── Agent-Flow 任务
```

绝大多数新项目建议从这里开始：

```text
Host Policy + Lite Handoff
```

不要因为项目大、文件多、运行时间长，就自动启用 Agent-Flow。是否需要更重的流程，取决于“错误通过的代价”，而不是代码行数。

---

## 1. Host Policy（`0.2.0` 引入）：先配置 Codex 的长期规则

先安装本仓库：

```bash
pip install -e /path/to/GPT_Codex_AI_Bridge_Kit
```

然后对当前 `CODEX_HOME` 安装机器级规则：

```bash
ai-bridge host install
ai-bridge host validate
```

如果一台机器上存在多个不同的 `CODEX_HOME`，它们应视为不同的 Codex 身份，分别配置。

Host Policy 主要管理：

```text
$CODEX_HOME/config.toml
$CODEX_HOME/AGENTS.md
$CODEX_HOME/rules/ai-bridge-global.rules
```

它负责的是长期行为，例如：

- 用户可见的进度、计划、测试结果和完成报告默认使用自然中文；
- 普通局部实现由 Codex 自行判断，真正会改变架构、范围、部署、Git 分支策略或科研语义的歧义才询问用户；
- 当前 `main` 分支上的安全 `fetch`、快进 `pull`、正常 `add/commit/push origin main` 尽量减少重复授权；
- `force push`、改 remote、删除分支、`reset --hard`、`git clean` 等危险操作仍然不能因为“自动化”而放开；
- 如果下一步明确属于外部 GPT Planner/Reviewer/Critic，等待 GPT 不应被误判为任务失败。

Host Policy 会尽量非破坏式修改已有配置，并在需要时创建备份。

---

## 2. Lite Handoff（`0.1.0` 引入）：新项目默认安装

进入一个正式 Git 仓库后：

```bash
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project
```

它会给项目建立一套轻量、可版本控制的 GPT ↔ Codex 交接结构。核心关系可以理解成：

```text
GPT 写清楚要做什么
        ↓
prompts/tasks/<task_key>.md
        ↓
Codex 执行
        ↓
results/<task_key>/result.md
        ↓
需要时再由 GPT 复核
```

常见目录包括：

```text
AGENTS.md
prompts/
results/
docs/
.agents/skills/agent-task-executor/
```

Lite Handoff 并不意味着“只能做小任务”。普通功能开发、修 bug、文档整理、常规重构，甚至较大的实现，只要不要求独立角色闭环，通常都够用。

`ai-bridge init` 只配置当前项目，不会偷偷修改你的 `$CODEX_HOME`，也不会自动安装下面那些可选能力。

---

## 3. Reviewed Handoff（`0.5.0` 引入）：需要 GPT 先定方案、完成后再独立复核

如果某项工作不能让 Codex 一边执行一边自己决定产品语义或科研方向，但又没有必要上最重的 Agent-Flow，可以使用 Reviewed Handoff。

最直观的流程是：

```text
GPT Planner
先把方案写清楚并冻结
        ↓
Codex Executor
按方案实现
        ↓
GPT Reviewer
读取真实 Git diff、测试和结果独立复核
        ↓
必要时允许一轮 Codex 返修
        ↓
最终交给用户
```

安装：

```bash
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project
```

创建具体任务：

```bash
ai-bridge reviewed-handoff task init \
  --target /path/to/project \
  --task-key 001_example \
  --objective "这里写任务目标"
```

这套流程默认最多两轮 GPT 复核。第一轮如果返回 `REVISE`，允许 Codex 自动返修一次；第二轮仍未通过，就进入人工决策，不继续无限循环。

GPT 侧可以通过 ChatGPT「安排任务」定期查看 GitHub 中的任务状态；Codex 侧可以运行轻量监视器，在 `PLAN_FROZEN` 或 `REVISE` 时启动执行：

```bash
ai-bridge reviewed-handoff watcher run \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

监视器不会自行创建分支或 PR。它也不会把 Codex Executor 变成新的决策角色：Executor 只执行冻结方案并提交结果，发布仍由 watcher 在验证后完成。

`PLAN_FROZEN` 只有在当前 `PLAN.md` 结构合法时才会被 watcher 视为可执行；如果 GitHub 上出现临时不合法的 workflow 状态，watcher 会拒绝启动 Executor、记录本机状态并低频重试。Planner 后续修好同一分支后，不需要用户重新启动 watcher。

需要查看后台 Executor 状态时，可以运行：

```bash
ai-bridge reviewed-handoff watcher status \
  --target /path/to/project \
  --branch <existing-authorized-branch>
```

这个状态入口读取本机 watcher state 和仓库中的 `CURRENT.json`，报告 task、当前 state、Executor event、runtime 类型、可用 thread id、started/completed 时间、上次 exit/result、等待 owner 和上次发布状态。当前稳定生产路径仍是 `codex exec`；如果某个 Codex App/App Server 环境能提供可脚本化、可恢复、项目可见的 thread lifecycle，thread id 只能作为本机 operational state 记录，不能进入 Reviewed Handoff workflow identity。

外部 GPT、CI 或 Visual Review 尚未给出新决定时，属于正常等待，而不是 `BLOCKED`。

详细状态规则和边界见：

```text
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
```

---

## 4. Overleaf Bridge（`0.6.0` 引入）：一个科研仓库里同时管代码和论文

这是 `0.6.0` 引入的能力，已完成真实科研仓库与 Overleaf 的双向端到端验证。

它针对很常见的科研项目结构：

```text
research-repo/
├── code/
├── analysis/
├── data/
├── results/
├── docs/
└── paper/
    ├── manuscript/
    ├── notes/
    └── submission/
```

我们希望 Codex 在整个仓库根目录工作，这样它写论文时可以同时检查代码、实验结果和研究文档；但 Overleaf 只应该看到真正的论文源码，例如 `paper/manuscript/`。

### 为什么不能直接用 Overleaf 的 GitHub 同步

Overleaf 的 GitHub 同步面向整个 GitHub 仓库，不能只选一个子目录。因此这里不用“让 Overleaf 从 GitHub 拉 `paper/manuscript/`”这种方式。

Overleaf Bridge 的做法是：

```text
完整科研 GitHub 仓库
        │
        ├── Codex 读取整个项目
        │
        └── paper/manuscript/
                 │
                 ▼
        本机的 Overleaf Git 镜像
                 │
                 ▼
             Overleaf
```

科研仓库本身不会增加一个 `overleaf` remote，也不会改变 `origin` 或分支结构。

### 第一次安装

先在科研仓库中指定论文根目录：

```bash
ai-bridge overleaf install \
  --target /path/to/research-repo \
  --paper-root paper/manuscript
```

项目里会保存可版本控制的配置：

```text
automation/overleaf/config.toml
```

例如：

```toml
schema_version = 1
paper_root = "paper/manuscript"
main_document = "main.tex"
exclude_paths = []
```

然后在 Overleaf 创建一个空白项目，删除默认 `main.tex`，取得它的 Git URL，再执行：

```bash
ai-bridge overleaf connect \
  --target /path/to/research-repo \
  --remote-url https://git@git.overleaf.com/<PROJECT_ID> \
  --bootstrap
```

Overleaf 项目可能使用 `main`、`master` 或其他默认分支。Bridge Kit 会在
`connect` 时读取该项目实际声明的远端分支，并把结果保存在本机
`connection.json` 中；科研仓库的 `config.toml` 不需要配置 `main/master`。

Overleaf 的 token 不写入本仓库，也不写入 `connection.json`；认证交给正常的 Git credential helper。

### 日常怎么用

Codex 在本地写完论文后，推荐顺序是：

```text
修改论文
→ 本地编译 / 检查
→ commit
→ git push origin main
→ ai-bridge overleaf status
→ ai-bridge overleaf push
```

如果导师或合作者直接在 Overleaf 修改：

```text
ai-bridge overleaf status
→ ai-bridge overleaf pull
→ 检查 git diff
→ 本地重新编译
→ commit
→ git push origin main
```

`pull` 只把 Overleaf 修改带回论文目录，不会替你自动 commit，也不会自动推 GitHub。

### 为什么不会轻易覆盖双方修改

Bridge 会记录上一次成功同步时的内容摘要，并比较：

```text
上次同步版本
本地论文
Overleaf 当前版本
```

因此能区分：

- 只有本地改了：可以 `push`；
- 只有 Overleaf 改了：可以 `pull`；
- 两边内容相同：刷新同步基线即可；
- 两边都从上次同步后发生不同修改：判定为分叉，拒绝自动覆盖。

`connect`、`push` 和 `pull` 还要求真正要发布的论文目录处于干净状态。未提交、未跟踪或被忽略但实际存在的论文文件不会被悄悄覆盖。

### `exclude_paths` 是干什么的

它只适合排除 **Overleaf 编译不需要**、但你想留在 GitHub 或本地的辅助文件，例如：

```text
AGENTS.md
README.md
main.pdf
作者自己的本地说明
```

以下文件如果参与论文编译，就不能排除：

```text
.tex
.bib
.sty
.cls
LaTeX 实际引用的图片
LaTeX 实际引用的表格或其他资源
```

所有 Overleaf 编译真正需要的文件，都应该位于 `paper_root` 内并参与同步。

### 多台机器怎么办

下面这些属于每台机器自己的本地状态：

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/
```

如果同一个项目在 Mac、工作站和服务器上都要直接操作 Overleaf，每台机器各自 `connect` 一次即可。不要把上述本地状态提交进 GitHub。

常用命令：

```bash
ai-bridge overleaf status --target /path/to/research-repo
ai-bridge overleaf push --target /path/to/research-repo
ai-bridge overleaf pull --target /path/to/research-repo
ai-bridge overleaf validate --target /path/to/research-repo
```

Overleaf Bridge **不会自动实时同步**。它就是一个按需、可检查、尽量不覆盖别人修改的论文同步层。

---

## 5. Generic Notifier（`0.3.0` 引入）：按结构化 brief 发邮件

Notifier 只负责通知，不负责决定任务是不是完成。

权责边界是：语义决定者写结构化 brief，Generic Notifier 只做 deterministic 渲染、去重和 SMTP 发送。Planner/Reviewer/Critic/Final Critic 可以写自己决定对应的终态、人工等待或里程碑 brief；Controller/watcher 只可以写 operational failure/status brief。Executor/Codex 不能决定 PASS，不能写自由文本式用户结论邮件，也不能绕过 notifier 的 send-once/dedupe。

如果项目需要终态邮件，先同步私有配置并发一封真实测试邮件：

```bash
cd /path/to/project
ai-bridge private sync --profile notifier
ai-bridge notifier send-test
```

任务完成后，工作流可以生成：

```text
results/<task_key>/notification_brief.json
```

再发送：

```bash
ai-bridge notifier send results/<task_key>/notification_brief.json
```

推荐这种一次性发送方式，不要求为了通知常驻一个 tmux、systemd 或后台轮询进程。

向后兼容的旧 `notification_brief.json` 仍表示 terminal/user-decision 通知。需要 workflow 继续运行的非阻塞里程碑通知时，可以写入：

```text
results/<task_key>/notifications/<event>.json
```

新结构化 brief 使用短字段，例如 `event_type`、`status`、`decision_authority`、`key_conclusion`、`next_step`、`action_required` 和 `evidence_paths`。邮件正文由 notifier 模板渲染成简洁中文，而不是让 Executor 生成整封自由文本邮件。重复 brief 会按内容 digest 去重，不会重复发送。

邮件密码等秘密配置保存在本地私有文件，不应提交到项目仓库。

---

## 6. Visual Review（`0.5.2` 引入）：给图片和视觉产物增加独立检查

Visual Review 用来检查真正需要“看图”才能判断的问题，例如：

- PPT 或 PDF 页面是否排版异常；
- 图中文字是否被裁切；
- 视觉结果是否符合给定检查标准；
- 某个实现是否与参考截图明显不一致。

它不是新的工作流角色，而是给 Reviewed Handoff、Agent-Flow 或普通项目提供一份可验证的视觉证据。

安装和预检：

```bash
ai-bridge visual-review install --target /path/to/project
ai-bridge visual-review preflight --target /path/to/project
```

默认通过 GitHub Actions 调用 OpenAI 图像输入能力。GitHub Secret 名称统一为：

```text
OPENAI_VISUAL_REVIEW_API_KEY
```

默认模型为：

```text
gpt-5.6-terra
```

生成的结果通常写到：

```text
results/<task_key>/visual_review/VISUAL_REVIEW.json
```

Bridge Kit 不会把 API key 写进仓库，也不会打印 secret 值。

默认隐私策略是保守的：安装视觉复核能力不等于允许自动上传患者影像、私有临床数据、未公开科研图片、凭据或其他敏感内容。没有明确外部上传授权时应拒绝。

---

## 7. Agent-Flow Core（`0.4.0` 引入）：只有高风险任务才用

Agent-Flow 面向“错误通过的代价很高”的任务，例如：

- 科研方法或系统架构的大改；
- 昂贵训练或长时间计算；
- 数据、安全或隐私敏感逻辑；
- 生产部署；
- 重要迁移；
- 必须能证明“为什么可以判定通过”的工作。

安装：

```bash
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

它会增加 `automation/agent_flow/` 控制目录，但不会替换 Lite Handoff，也不会自行创建 Git 分支。

整体分工可以直观理解成：

```text
Planner      决定要实现什么
Critic       检查方案和最终闭环是否真的成立
Controller   只负责机械路由，不替人做判断
Verifier     根据冻结要求建立验证标准
Executor     只负责实现
Human        最终保留人工决定权
```

Agent-Flow 比 Reviewed Handoff 更重，因为它会显式保存冻结要求、验证依据、稳定审查对象和最终独立检查。它的目的不是“堆更多 Agent”，而是避免同一个角色既写要求、又改实现、又自己宣布通过。

一个项目只需安装一次 Agent-Flow Core；每个高风险任务再单独创建任务实例：

```bash
ai-bridge agent-flow task init \
  --target /path/to/project \
  --task-key 001_example
```

详细设计见：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
```

---

## 8. 常见选择

### 普通代码仓库

```text
Host Policy
+ Lite Handoff
```

### 需要 GPT 先做方案、Codex 实现、GPT 再独立看一遍

```text
Host Policy
+ Lite Handoff
+ Reviewed Handoff
```

### 科研仓库同时放代码和论文，并希望用 Overleaf 协作

```text
Host Policy
+ Lite Handoff
+ Overleaf Bridge
```

### 需要完成后邮件提醒

在上述任意组合上再加：

```text
Generic Notifier
```

### 图片/PPT/视觉结果必须真正看图审核

按需增加：

```text
Visual Review
```

### 高风险科研、生产或安全敏感任务

```text
Host Policy
+ Lite Handoff
+ Agent-Flow Core
```

不要同时把所有可选层都装上，除非项目确实同时需要它们。

---

## 9. 常用命令速查

```bash
# 机器级长期规则
ai-bridge host install
ai-bridge host status
ai-bridge host validate

# 普通项目交接
ai-bridge init --target /path/to/project
ai-bridge validate --target /path/to/project

# 独立 GPT 复核
ai-bridge reviewed-handoff install --target /path/to/project
ai-bridge reviewed-handoff validate --target /path/to/project

# Overleaf
ai-bridge overleaf install --target /path/to/project --paper-root paper/manuscript
ai-bridge overleaf connect --target /path/to/project --remote-url <OVERLEAF_GIT_URL> --bootstrap
ai-bridge overleaf status --target /path/to/project
ai-bridge overleaf push --target /path/to/project
ai-bridge overleaf pull --target /path/to/project
ai-bridge overleaf validate --target /path/to/project

# 视觉检查
ai-bridge visual-review install --target /path/to/project
ai-bridge visual-review preflight --target /path/to/project

# 邮件通知
ai-bridge private sync --profile notifier
ai-bridge notifier send-test

# 高风险闭环
ai-bridge agent-flow install --target /path/to/project
ai-bridge agent-flow validate --target /path/to/project
```

---

## 10. 设计原则

这套工具长期遵守几条简单原则：

1. **项目本身才是权威来源。** 任务状态、论文、实现和结果应留在 Git 或明确的本地状态中，不依赖某个 Codex 对话线程记住一切。
2. **默认轻量。** 普通任务不要为了“显得可靠”而强行使用高风险闭环。
3. **角色分工要有意义。** 独立复核的价值在于判断权分离，不在于角色数量。
4. **Git 操作尽量安全且低打扰。** 正常开发可以自动化，改变分支结构和破坏性操作必须保守。
5. **秘密信息不进仓库。** 邮件密码、Overleaf token、OpenAI API key 等都应保存在合适的私有位置。
6. **等待不是失败。** 当任务明确交给外部 GPT 处理时，短时间没有新决定属于正常等待。
7. **对真实风险严格，对形式主义克制。** 需要证明时就建立证据链；普通任务不为了流程漂亮增加无必要复杂度。

---

## 11. 进一步阅读

快速上手：

```text
QUICKSTART.md
```

主要实现规格：

```text
docs/V0_4_AGENT_FLOW_IMPLEMENTATION_SPEC.md
docs/V0_5_REVIEWED_HANDOFF_IMPLEMENTATION_SPEC.md
docs/V0_6_OVERLEAF_BRIDGE_IMPLEMENTATION_SPEC.md
```

版本变化：

```text
CHANGELOG.md
```

仓库维护规则：

```text
AGENTS.md
```

如果只是第一次使用，不需要先读完这些规格。通常从本文的“新机器”“新项目”和对应的可选能力开始即可。
