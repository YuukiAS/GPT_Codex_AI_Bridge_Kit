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

收到 kickoff 后，Codex 应读取 Goal 和 Persistent Run contract，检查 canonical tmux session、项目已有 lock / heartbeat / stage-state / checkpoint / resume evidence，再决定启动或恢复。已有兼容 run 时应 resume，不重复启动。

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

如果 contract 的 `Delivery mode` 选择 Notifications，只有在当前机器已经有合法 provider/recipient 配置时才能投射一次 operational-progress brief；不得为了报告进展而新建 credential、recipient、daemon、watcher 或 controller。
