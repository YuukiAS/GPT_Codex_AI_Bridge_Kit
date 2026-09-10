# Persistent Run

这个项目已经启用 AI Bridge Kit 的 Persistent Run。

Persistent Run 是可选项目能力，不是 Lite / Review / Control 之外的第四套 workflow。它只处理一个问题：当某个已经冻结的 Goal 明确要求长期执行时，Codex 应使用项目约定的 canonical tmux session 保持运行、恢复和观察，而不是临时发明 `setsid`、`nohup`、裸后台 `&`、`screen`、`sudo` 或其他 persistence backend。

## 使用边界

Persistent Run 不决定任务目标、科学范围、产品范围、训练预算、数据、模型、资源申请、调度器行为或完成标准。这些继续由原来的 Goal、task 或 workflow 决定。

如果一个 Goal 使用 Persistent Run，应在 Goal 或相邻任务文件中复制或引用 `automation/persistent_run/CONTRACT_TEMPLATE.md`，并填入该 run 的 stable key、资源边界、artifact/state 路径和完成标准。

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
