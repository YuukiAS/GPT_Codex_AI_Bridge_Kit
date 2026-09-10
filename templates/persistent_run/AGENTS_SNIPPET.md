## Persistent Run

本仓库已启用 AI Bridge Kit 的 Persistent Run。

Persistent Run 是可选项目能力，不是 Lite / Review / Control 之外的第四套 workflow，也不是新的 Planner / Reviewer / Critic / Verifier / watcher / state machine。它只约束明确标记为 persistent execution 的长期 Goal 如何通过 canonical tmux session 启动、恢复和观察。

当当前 Goal/task/contract 明确写明 `Persistent execution: REQUIRED` 时：

- 先读取当前 Goal/task 和其中的 Persistent Run contract；不要把仓库模板本身当成已经获得当前用户授权。
- 在任何 substantive execution、expensive/long-running precursor work 或 canonical launch 前，确认当前用户可见请求中已经包含针对同一个 frozen Goal 的 explicit persistent kickoff authorization。用户可用 `ai-bridge persistent-run prompt kickoff --target <repo> --goal <repo-relative-goal>` 生成这段授权。
- 如果当前用户消息没有这段 bounded kickoff authorization，应先生成并显示该 kickoff prompt，然后等待用户把它作为当前消息发送回来；不要先启动 tmux，也不要先做大量前置工作。
- 使用 `tmux` 作为 0.8.0 唯一 persistence backend，并使用 Goal/project 指定的 canonical session/run key。
- 启动前先用 `tmux has-session` / `tmux ls` 和项目已有 lock / heartbeat / stage-state / checkpoint / resume evidence 判断是否已有兼容 run；已有兼容 run 时 resume，不重复启动。
- 使用项目/Goal 自己授权的 launcher 或命令，不要发明 Bridge Kit 通用科研 orchestrator。
- 启动后检查 tmux session 和最强的项目原生进度证据；Codex / SSH disconnect 不得被解释为实验或任务失败。
- 后续恢复同一个 frozen Goal 时，不要仅因为任务长期运行、detached 或 unattended 而反复要求相同批准；新的 artifact、recipient/provider、resource、purpose、backend 或 Goal 外副作用仍按正常审批规则处理。
- optional diagnostic failure 不得自动终止整个 Goal；如果 lock、heartbeat、stage-state、checkpoint 或 output evidence 提供了更强状态，应以这些证据为准。
- tmux session、Slurm job、PID、heartbeat 或 checkpoint 只证明活动或状态，不证明 Goal 完成；原 Goal 的 positive completion criteria 仍是完成声明的唯一依据。

禁止因为 tmux 启动或诊断不方便而自动 fallback 到 `setsid`、`nohup`、裸后台 `&`、`screen`、`sudo`、新 allocation、cancellation 或其他 persistence mechanism。若 explicit kickoff 后 canonical tmux launch 仍被拒绝，报告 exact rejected command 和 exact rejection reason，不要绕过。
