# Project State Bridge — Roadmap

> 状态：未来路线图，版本未分配。本文只记录目标、边界、数据流与验收设想；当前正式 `0.7.0` release 不实现 CLI、同步脚本、GitHub Actions、consumer 安装逻辑或任何 Project State Bridge runtime。

## 1. 为什么需要这一层

Bridge Kit 已经能解决 GPT → Codex 交接、独立复核、通知、视觉检查和 Overleaf 同步，但跨项目仍有一个很朴素的问题：**工作实际发生在 GitHub / Codex / GPT 中，项目总览却很容易变成另一份需要人工维护的账。**

Project State Bridge 的目标不是再造项目管理软件，而是让现有项目管理工具成为“自动更新的投影视图”。第一目标消费者是 Notion，但状态协议本身不得与 Notion 绑定。

最终体验应当是：

```text
GPT / Codex 完成一次有意义的工作
        ↓
Project State Audit
        ↓
GitHub 中更新当前状态 / 追加真正的里程碑
        ↓
GitHub Actions 做机械校验和同步
        ↓
Notion 自动呈现当前状态、看板、路线图、项目历程与已完成成果
```

用户不需要在每轮工作后手工改 Notion。

---

## 2. 核心原则

### 2.1 GitHub 是项目事实源，Notion 是投影视图

第一版坚持单向：

```text
GitHub → Notion
```

不得让 GPT、Codex、GitHub Actions 三方分别直接修改同一套 Notion 状态。GPT 与 Codex 只修改 repository-controlled state；GitHub Actions 是唯一 Notion writer。

这样可以避免：

- 多个 agent 同时覆盖状态；
- Notion 与 repo 对“当前目标”产生两个版本；
- 一次讨论误把项目标成完成；
- 后续无法从 Git 历史解释某个状态为何改变。

### 2.2 “现在”与“历史”必须分开

Project State Bridge 使用两个文件，而不是把所有内容塞进一个不断膨胀的日志：

```text
automation/project_state/
├── PROJECT_STATE.json
└── PROJECT_MILESTONES.json
```

- `PROJECT_STATE.json`：当前快照，可覆盖更新。
- `PROJECT_MILESTONES.json`：只保存值得长期回看的关键节点，按稳定 `milestone_key` 幂等追加/修正。

普通 commit、微小 bug fix、措辞修改、一次临时讨论，不属于 milestone。

### 2.3 Project State Audit 是检查义务，不是强制制造 diff

所有启用 Project State Bridge 的 repo，在 GPT / Codex 完成工作前都要问一次：

> 本轮是否真的改变了项目阶段、当前目标、下一步、阻塞、关键结果、完成状态，或形成了值得长期保留的里程碑？

如果答案是否定的，**state 文件保持不变**。不能为了证明“做过 audit”制造无意义 commit。

---

## 3. 当前状态模型

`PROJECT_STATE.json` 的草案只保存项目级信息，不复制 issue、task、实验日志或聊天记录。

示意：

```json
{
  "schema_version": 1,
  "project_key": "cat-trace",
  "name": "CAT-TRACE",
  "category": "research",
  "status": "active",
  "phase": "theory-validation",
  "current_goal": "完成 open-tail theory 与三数据集验证",
  "next_action": "审查 Theorem 5.1 的完整证明",
  "blocker": null,
  "recent_result": "Group-marked calibration formulation finalized",
  "started_at": "2026-07-01",
  "completed_at": null,
  "final_outcome": null,
  "repo_url": "https://github.com/owner/repo",
  "knowledge_url": null,
  "updated_at": "2026-09-01"
}
```

### 3.1 状态枚举

第一版保持少而稳定：

```text
backlog   待启动
active    推进中
waiting   等待外部条件，但不是故障
blocked   存在真实阻塞
paused    人工暂停
completed 已完成
```

`waiting` 与 `blocked` 必须延续 Bridge Kit 现有语义：正常等待外部 reviewer、数据、CI 或明确时间窗口，不应被误判为阻塞。

### 3.2 哪些字段由自动流程更新

默认可由 GPT / Codex 根据真实工作结果更新：

- `phase`
- `current_goal`
- `next_action`
- `blocker`
- `recent_result`
- `status`（但不得擅自决定 `paused`）
- `completed_at`
- `final_outcome`
- `updated_at`

`project_key` 一旦安装后必须稳定，作为跨 GitHub / Notion 的主键。

### 3.3 哪些字段不应被同步器擅自覆盖

以下属于用户的项目组合管理，而不是 agent 对执行事实的判断：

- Priority / 优先级
- Planned completion / 计划完成
- 是否暂停或归档
- Notion 中纯展示用的标签与个性化排版

这些字段可以由用户明确指令修改，但 GitHub → Notion 的默认同步不得覆盖用户在 Notion 中的选择。

---

## 4. 里程碑模型

`PROJECT_MILESTONES.json` 保存“项目是怎样一步步长出来的”，而不是“最近做了什么”。

示意：

```json
{
  "schema_version": 1,
  "project_key": "gpt-codex-ai-bridge-kit",
  "milestones": [
    {
      "milestone_key": "project-state-design",
      "date": "2026-09-01",
      "kind": "decision",
      "title": "Project State Bridge 方案确定",
      "summary": "确定 GitHub 为事实源，Notion 为单向投影视图。",
      "source_url": "https://github.com/owner/repo/..."
    }
  ]
}
```

### 4.1 什么值得成为 milestone

满足下列任一条件时，Planner / Reviewer / GPT / Codex 应考虑追加 milestone：

1. 项目正式开始；
2. 一个对外或内部稳定版本形成；
3. 核心架构、科研方向或产品范围发生已经被用户采纳的重要决策；
4. 获得改变后续判断的关键理论、实验或数据结果；
5. 论文达到投稿、接收、camera-ready 等真正阶段节点；
6. 一项长期能力首次真正打通；
7. 项目完成。

以下情况默认不记录：

- 单个普通 commit；
- 小 bug 修复；
- 文案、格式、排版微调；
- 尚未采纳的 brainstorming；
- 一次临时失败但没有改变项目路径的实验；
- 单纯“今天又做了一轮”。

### 4.2 milestone 必须可追溯

只要存在真实证据，应填写 `source_url`，优先指向：

- Git commit / release / PR；
- 论文或正式文档；
- tracked experiment report；
- repository 中已冻结的 decision / plan 文件。

不得为了把时间轴填满而猜日期或补造节点。

---

## 5. 项目完成的语义

完成不是把项目从面板上删掉。

当项目真正完成时，应形成一个完整的终态动作：

```text
PROJECT_STATE.status = completed
PROJECT_STATE.completed_at = <date>
PROJECT_STATE.final_outcome = <一句可长期回看的结果>
        +
PROJECT_MILESTONES 追加 kind=completion 的终点
```

Notion 随后把它从“正在推进”移入“已完成”成果视图，并保留：

- 开始时间；
- 完成时间；
- 标签；
- 最终成果；
- 从立项到完成的全部关键里程碑。

“完成”因此是项目历史的一部分，而不是从总控台消失。

---

## 6. GPT 与 Codex 的行为规则

### 6.1 Codex

Project State Bridge 安装后，应在 consumer repo 的 managed AGENTS block 中加入 Project State Audit，作为 Definition of Done 的最后一步之一：

```text
实现 / 实验 / 文档完成
→ 必要验证
→ Project State Audit
→ 仅在真实状态变化时更新 state / milestones
→ staged diff 检查
→ commit / push
```

该规则只对存在 `automation/project_state/` 的 repo 生效，不能让 Host Policy 对所有临时仓库强行生成状态文件。

### 6.2 ChatGPT / 外部 GPT

Bridge Kit 应提供一段可加入 ChatGPT 个性化要求的短规则，而不是把整份协议复制进去。

目标语义：

> 当项目讨论形成已经被用户采纳、且会改变阶段、当前目标、下一步、阻塞、关键结果或里程碑的决定时，在 GitHub 连接可用且用户没有禁止写入时，同步更新对应 repository 的 Project State；探索性讨论和未采纳 brainstorming 不更新。

ChatGPT 没有可用 GitHub 写权限时必须如实说明，不能假装已经同步。

---

## 7. GitHub Actions → Notion

GitHub Actions 是第一版唯一的 Notion writer，而且职责必须保持机械。

触发范围只包含：

```text
automation/project_state/PROJECT_STATE.json
automation/project_state/PROJECT_MILESTONES.json
```

流程：

```text
文件变化
→ JSON/schema validation
→ 读取 project_key / milestone_key
→ 查询 Notion 对应记录
→ upsert 机器拥有的字段
→ 写 Last Synced
→ 结束
```

### 7.1 不做什么

同步 workflow 不调用 OpenAI API，不自己总结 commit，不猜 milestone，不扫描整个仓库推断项目状态。

语义判断属于 GPT / Codex；Action 只负责验证和投影。

### 7.2 Secrets / workspace config

公开 consumer repo 不得提交个人 Notion workspace 标识、token 或私有页面 URL。

至少需要仓库 / environment secret 或等价私有配置：

```text
NOTION_TOKEN
NOTION_PROJECTS_DATA_SOURCE_ID
NOTION_MILESTONES_DATA_SOURCE_ID
```

具体命名在实现阶段冻结。Notion token 永远不得写入 state 文件、日志或 commit。

### 7.3 幂等性

- Project 以 `project_key` upsert；
- Milestone 以 `milestone_key` upsert；
- workflow 重跑不得制造重复项目或重复里程碑；
- Notion 暂时不可用时，GitHub 中的 state 仍然是完整事实源，后续重跑即可恢复投影。

---

## 8. Notion 第一消费者的展示约定

Project State Bridge 不要求 Bridge Kit 接管用户整个 Notion workspace，只定义需要映射的字段与推荐视图。

推荐分成两张关联数据库。

### 8.1 项目

用于“现在”：

- 正在推进：table，聚焦下一步与阻塞；
- 看板：按状态分组；
- 需要处理：只显示 waiting / blocked；
- 路线图：开始 → 计划完成；
- 全部项目：完整信息；
- 已完成：gallery，作为成果归档。

### 8.2 项目历程

用于“从哪里来”：

- 时间轴：按日期展示关键节点；
- 全部节点：可检索的完整 milestone table。

两张表通过 Project relation 关联。

Notion 不复制 task、issue、实验日志、论文全文或 Codex runtime state。

---

## 9. 与现有 Bridge Kit 的关系

Project State Bridge 是**横切的项目层可选能力**，不是新的任务工作流。

它应能与以下能力独立组合：

```text
Lite
Review
Control
Generic Notifier
Visual / Text Review
Overleaf Bridge
```

Review / Control 的内部 `CURRENT.json` 仍属于具体任务状态机，不能直接拿来充当 `PROJECT_STATE.json`。一个 task PASS 也不等于整个 project completed。

---

## 10. Future implementation phase suggestions

### Phase A — 状态协议

- [ ] 冻结 `PROJECT_STATE.schema.json`；
- [ ] 冻结 `PROJECT_MILESTONES.schema.json`；
- [ ] 定义状态枚举、里程碑种类与字段 ownership；
- [ ] 定义 completion 规则；
- [ ] 加入 malformed / stale / duplicate milestone 测试样例。

### Phase B — Bridge Kit 安装与校验

- [ ] 增加 project-state 的 install / validate 能力；
- [ ] 生成 `automation/project_state/`；
- [ ] 非破坏式维护 consumer `AGENTS.md` managed block；
- [ ] 提供 ChatGPT personalization snippet；
- [ ] 保持没有启用该能力的 repo 行为完全不变。

### Phase C — Notion Projection

- [ ] 设计可复用 GitHub Actions workflow；
- [ ] secret / config preflight；
- [ ] project upsert；
- [ ] milestone 幂等 upsert；
- [ ] human-owned 字段保护；
- [ ] Notion 暂时失败后的可重跑恢复；
- [ ] 确认 workflow 不调用 OpenAI API。

### Phase D — 真实 consumer 试点

优先从少量不同类型项目开始，而不是一次铺满所有 repo：

1. Bridge Kit 自身：基础设施项目；
2. 一个科研 repo：验证 theory / experiment / paper milestones；
3. 一个产品 repo：验证版本、产品决策与 completion 语义。

通过后再批量安装到其他项目。

### Phase E — formal release closure

- [ ] README 增加 Project State Bridge；
- [ ] AGENTS 加入维护规则；
- [ ] CHANGELOG 记录正式能力；
- [ ] QUICKSTART 给出最小安装路径；
- [ ] 示例 Notion mapping 文档；
- [ ] 回归测试确认不破坏 v0.1–v0.6 能力；
- [ ] 真实 GitHub → Notion smoke test；
- [ ] 再决定是否分配正式 release version。

---

## 11. 明确不做

第一版不做：

- Notion → GitHub 双向同步；
- 新的 Tasks database；
- 自动把每个 GitHub Issue 复制进 Notion；
- 用 LLM 在 CI 中猜项目状态；
- 对整个 Git 历史逐 commit 生成时间轴；
- 项目间复杂依赖图；
- 资源额度监控（属于 Lucerna 一类运行状态工具）；
- 取代 Zotero / Bobbio / GitHub / Overleaf 的原始内容存储。

---

## 12. Future acceptance criteria

只有同时满足以下条件，Project State Bridge 才算可进入正式版本：

1. consumer repo 可以显式安装 / 卸载或停用该能力，而不影响其他 Bridge Kit workflow；
2. Codex 在启用 repo 中会做 Project State Audit，但无状态变化时不会制造 diff；
3. ChatGPT 有简短、可复用的同步行为约定；
4. 当前状态与 milestone 历史使用两个独立、schema-validated JSON 文件；
5. GitHub Actions 能幂等同步 Project 与 Milestone；
6. Notion 的人工字段不会被默认覆盖；
7. 普通 commit 不会污染 milestone timeline；
8. completion 会留下最终成果和完成节点，而不是简单隐藏项目；
9. Notion API / network 临时故障不会损坏 GitHub 事实源；
10. 至少三个不同类型 consumer 完成真实 smoke test 后再推广。

这套设计的判断标准只有一个：**用户打开 Notion 是为了看项目，而不是为了维护项目。**
