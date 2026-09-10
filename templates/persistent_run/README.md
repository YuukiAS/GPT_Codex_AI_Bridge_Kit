# Persistent Run

这个项目已经启用 AI Bridge Kit 的 Persistent Run。

Persistent Run 是可选项目能力，不是 Lite / Review / Control 之外的第四套 workflow。它只处理一个问题：当某个已经冻结的 Goal 明确要求长期执行时，Codex 应使用项目约定的 canonical tmux session 保持运行、恢复和观察，而不是临时发明 `setsid`、`nohup`、裸后台 `&`、`screen`、`sudo` 或其他 persistence backend。

## 使用边界

Persistent Run 不决定任务目标、科学范围、产品范围、训练预算、数据、模型、资源申请、调度器行为或完成标准。这些继续由原来的 Goal、task 或 workflow 决定。

如果一个 Goal 使用 Persistent Run，应在 Goal 或相邻任务文件中复制或引用 `automation/persistent_run/CONTRACT_TEMPLATE.md`，并填入该 run 的 stable key、资源边界、artifact/state 路径和完成标准。

## GPT 任务写作规则

GPT 写 task 时必须把 execution lifetime 和 Lite / Review / Control workflow 分开判断。overnight、unattended、run until morning、multi-hour、leave it running、survive disconnect 或 resume persistent Goal 是持久执行触发词，但不是自动升级 Review / Control 或 `task_type: "controller"` 的理由。

当用户要求持久执行时，GPT 必须读取本文件和 `automation/persistent_run/CONTRACT_TEMPLATE.md`，并在 task/Goal 中写入 Persistent Run contract。最少要包含：

```text
Persistent execution: REQUIRED
Backend: tmux
Goal source: <repo-relative goal/task path>
Run/session key: <project-owned stable key>
```

同时写清 authorized effects、resource boundary、forbidden expansion、recovery evidence、heartbeat / stage-state / checkpoint / resume semantics，以及原始 positive completion criteria。

如果仓库没有安装 Persistent Run，且用户没有选择等价的项目原生持久执行合同，GPT 不得把需求降级成普通 live Codex session；应报告缺少持久执行能力。

## Kickoff

仓库文件本身不能冒充当前用户授权。真正启动或恢复长期执行前，用户应生成并发送一次 kickoff 授权：

```bash
ai-bridge persistent-run prompt kickoff \
  --target /path/to/repo \
  --goal path/to/goal.md
```

这个命令只打印授权文本，不会创建 tmux session，不会启动任务，也不会扩大 Goal scope。

## Codex 恢复原则

收到 kickoff 后，Codex 应读取 Goal 和 Persistent Run contract，检查 canonical tmux session、项目已有 lock / heartbeat / stage-state / checkpoint / resume evidence，再决定启动或恢复。已有兼容 run 时应 resume，不重复启动。

tmux session、Slurm job、PID、heartbeat 或 checkpoint 只能证明活动或状态，不能证明 Goal 完成。完成声明仍必须由原 Goal 的正向完成标准支持。
