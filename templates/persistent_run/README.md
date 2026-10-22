# Persistent Run

这个项目已经启用 AI Bridge Kit 的 Persistent Run。

Persistent Run 是可选项目能力，不是 Lite / Review / Control 之外的第四套 workflow。它只处理一个问题：当某个已经冻结的 Goal 的实际进程或 orchestrator 由终端拥有，并且必须在 Codex / SSH / terminal 断开后继续运行时，Codex 应使用项目约定的 canonical tmux session 启动、恢复和观察，而不是临时发明 `setsid`、`nohup`、裸后台 `&`、`screen`、`sudo` 或其他 persistence backend。

## 使用边界

Persistent Run 不决定任务目标、科学范围、产品范围、训练预算、数据、模型、资源申请、调度器行为或完成标准。这些继续由原来的 Goal、task 或 workflow 决定。它也不是通用 unattended authorization token：长时间、过夜或无人值守只说明需要启动前授权预检，不能自动推出 tmux。

如果工作已经由调度器或项目原生系统拥有寿命，例如已接受的 `sbatch` batch job，或已有 detached service/job，那么不要仅因运行时间长而套一层 tmux。此时应写清需要授权的调度器/资源 effect、使用 scheduler/project-native progress evidence，并让原生 owner 负责进程寿命。

如果一个 Goal 使用 Persistent Run，应在 Goal 或相邻任务文件中复制或引用 `automation/persistent_run/CONTRACT_TEMPLATE.md`，并填入该 run 的 stable key、资源边界、artifact/state 路径和完成标准。

## GPT 任务写作规则

GPT 写 task 时必须把三件事分开判断：

1. upfront authorization readiness：长时间或无人值守前，哪些可预见且必需的 `HUMAN_ONLY` effect 需要当前用户明确授权；
2. process persistence topology：Codex / SSH / terminal 消失后，谁拥有进程寿命；
3. project-native progress reporting：用什么项目原生证据报告 stage、progress、ETA/UNKNOWN、stalled/blocked/complete/failed 和 reconnect 状态。

overnight、unattended、run until morning、multi-hour 或 leave it running 只触发这套判断，不自动选择 tmux，也不是自动升级 Review / Control 或 `task_type: "controller"` 的理由。

只有当 terminal-owned foreground process/orchestrator 必须 survive disconnect，且没有 scheduler/service/project-native owner 已经提供寿命时，才把 Persistent Run/tmux 写进 task/Goal。survive disconnect 和 resume persistent Goal 仍然是这类拓扑的重要信号。

当用户要求持久执行时，GPT 必须读取本文件和 `automation/persistent_run/CONTRACT_TEMPLATE.md`，并在 task/Goal 中写入 Persistent Run contract。最少要包含：

```text
Persistent execution: REQUIRED
Backend: tmux
Goal source: <repo-relative goal/task path>
Run/session key: <project-owned stable key>
```

同时写清 authorized effects、resource boundary、forbidden expansion、recovery evidence、heartbeat / stage-state / checkpoint / resume semantics，以及原始 positive completion criteria。

如果确实需要 terminal-owned survive-disconnect 持久执行，但仓库没有安装 Persistent Run，且用户没有选择等价的项目原生持久执行合同，GPT 不得把需求降级成普通 live Codex session；应报告缺少持久执行能力。

## Kickoff

仓库文件本身不能冒充当前用户授权。真正启动或恢复长期执行前，用户应生成并发送一次 kickoff 授权：

```bash
ai-bridge persistent-run prompt kickoff \
  --target /path/to/repo \
  --goal path/to/goal.md
```

这个命令只打印授权文本，不会创建 tmux session，不会启动任务，也不会扩大 Goal scope。它只适用于已经选择 Persistent Run/tmux 的 Goal；scheduler-native 或 already-detached 工作不需要伪造 Persistent Run kickoff。

## Codex 恢复原则

收到 kickoff 后，Codex 应使用 `persistent-run start`。Bridge 从 exact Goal
bytes、repo、run key、working directory、launch argv 与固定 `backend=tmux`
计算完整 launch identity，并只创建一个
`ai-bridge-pr-<full-64-hex-launch-id>` session、一个 run-scoped supervisor、
一个 machine-local binding 和一个 child。已有 compatible active run 只返回
existing；stale binding、identity mismatch、partial start 或 supervisor loss
不自动 relaunch、不 takeover、不猜 terminal。exit code 只来自 supervisor
观察到的真实 `child.wait()`。

异常状态不要删除 machine state。先运行 `persistent-run recover`；只有结果为
`SAFE_TO_CLOSE_STALE` 时，才可用带 exact launch id 的
`persistent-run resolve --close-stale`。`resolve` 只关闭重复执行风险，写入
`STALE_CLOSED_WITHOUT_COMPLETION`，不伪造 exit code 或 Goal 完成。

```bash
ai-bridge persistent-run status \
  --target /path/to/repo \
  --goal path/to/goal.md \
  --expected-goal-sha256 <exact-sha256>
```

tmux session、Slurm job、PID、heartbeat 或 checkpoint 只能证明活动或状态，不能证明 Goal 完成。完成声明仍必须由原 Goal 的正向完成标准支持。

## Progress reporter

Persistent Run 的 report/latest 命令可以用项目原生进度 JSON 生成可恢复的本机观察报告。这个能力独立于 tmux：只要有项目原生 progress source，scheduler-native 或 already-detached 工作也可以使用它记录 latest/history。

```bash
ai-bridge persistent-run report \
  --progress /path/to/project-progress.json

ai-bridge persistent-run latest \
  --progress /path/to/project-progress.json
```

`report` 会把 normalized latest 和 bounded recent history 写入 `${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/persistent-run/`。它只比较项目原生事件：stage、真实 completed/total、ETA/UNKNOWN、stall/blocked/complete/failed 等。重复或非实质变化会更新本机 latest/history，但会被标记为 suppressed delivery。

观察记录与上次逻辑投递的进度/时间分开保存。普通 count/fraction 小变化不单独触发
投递；健康进度按上次逻辑投递计算 cadence，默认 60 分钟、非测试最短 15 分钟。
每 5 分钟更新 observation 不会重置计时。start/resume、阶段切换、进入
stalled/blocked/failed、runtime terminal 和重大 ETA 变化可提前发送；已知 ETA 与
`UNKNOWN` 互换总是重大变化，已知时间变化门槛为
`abs(new_finish - previous_finish) >= max(15min, 25% × previous_remaining_time)`。
transport 失败不把后续 observation 变成自动重试，runtime terminal 不受 cadence 阻断。

`bridge-child` producer 使用：

```bash
ai-bridge persistent-run progress update --stage fit --completed 3 --total 10
```

supervisor 每 60 秒读取一次。missing、半写、坏 JSON 或暂时不可读只把当前
observation 标为 unavailable，child 与 supervisor 继续，last-good 不被伪造覆盖。
count/fraction 至少三个有效点且跨十分钟后才形成主动 ETA；stage/none 或证据不足时
诚实保持 `UNKNOWN`。

新 quantitative run 必须冻结实际 producer 和正整数更新间隔，stage/none 必须写
`Progress mode reason`。项目原生 JSON 携带 exact run/runtime 身份及来源实际
`observed_at`，可用独立 `publication_id` 或递增 `publication_sequence`。
重复读取不刷新来源健康时间、不增加 ETA 样本。超过
`max(900s, 3 × expected interval)` 没有新有效发布，当前状态是
`PROGRESS_SOURCE_OVERDUE`，不是业务 stalled；有效平台期、预热/重置、坏源有各自
诊断。status 不重读来源，读取 supervisor 保存的同一份 snapshot；last-good 保留
来源时间，当前不支持的 ETA 为 `UNKNOWN`，经验区间不是校准置信区间。

可选 `External notification attempt cap: 6` 在既有 binding 限制五个普通席与一个
真实 terminal 保留席。席位在 helper 前落盘，失败、未知或崩溃不退还、不 retry；
耗尽只抑制外部通知，不中断 child 或本地进度。RUNNING/child identity、观察与逻辑
投递时钟、真实 exit/末次进度均在相应通知前保存。

正式 supervisor 只在 contract 的 `Notify: ON` 且 machine Notifier readiness 通过后
投递，复用 `~/.ai-bridge/private/notifier.env`，不为报告进展新建 credential、recipient、
daemon、watcher 或 controller。独立 `report/latest` 只记录本机报告和逻辑投递判断；
旧 `delivery_mode=notifications` 本身不授权或建立自动邮件 transport。
