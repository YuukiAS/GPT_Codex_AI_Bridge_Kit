## Persistent Run

本仓库已启用 AI Bridge Kit 的 Persistent Run。

Persistent Run 是可选项目能力，不是 Lite / Review / Control 之外的第四套 workflow，也不是新的 Planner / Reviewer / Critic / Verifier / watcher / state machine。它只约束明确标记为 persistent execution、且实际进程或 orchestrator 由终端拥有并必须 survive Codex/SSH/terminal disconnect 的 Goal 如何通过 canonical tmux session 启动、恢复和观察。

长时间、overnight、unattended 或 multi-hour 本身不是 tmux 选择条件。执行前先分开判断：upfront authorization readiness、process persistence topology、project-native progress reporting。scheduler-owned batch job（例如已接受的 `sbatch`）或 already-detached service/job 不应仅因 duration 增加 tmux；它们仍要按普通规则处理调度器/资源授权和项目原生进度证据。

当当前 Goal/task/contract 明确写明 `Persistent execution: REQUIRED` 时：

- 先读取当前 Goal/task 和其中的 Persistent Run contract；不要把仓库模板本身当成已经获得当前用户授权。
- 在任何 substantive execution、expensive/long-running precursor work 或 canonical launch 前，确认当前用户可见请求中已经包含针对同一个 frozen Goal 的 explicit persistent kickoff authorization。用户可用 `ai-bridge persistent-run prompt kickoff --target <repo> --goal <repo-relative-goal>` 生成这段授权。
- 如果当前用户消息没有这段 bounded kickoff authorization，应先生成并显示该 kickoff prompt，然后等待用户把它作为当前消息发送回来；不要先启动 tmux，也不要先做大量前置工作。
- 使用 `tmux` 作为 0.11.0 唯一 persistence backend；收到 exact kickoff 后只用其中的 `ai-bridge persistent-run start` 幂等启动/恢复，用 `persistent-run status` 诊断，不手工拼另一个 launcher。
- `start` 必须先核 Goal hash/effect identity并连接同一 official shared app-server；无法证明时以 `PROGRESS_THREAD_SHARED_APP_SERVER_UNAVAILABLE` 在新 primary 前停止。
- 使用项目/Goal 自己授权的 launcher 或命令，不要发明 Bridge Kit 通用科研 orchestrator。
- 启动后检查 tmux session 和最强的项目原生进度证据；Codex / SSH disconnect 不得被解释为实验或任务失败。
- Progress display thread只接收同一shared app-server的注入文本，不运行业务/model reader turn。进度来自 contract 的项目原生 source；`report/latest` 不需要对应的 tmux session，仍可独立诊断，不要从 tmux/PID 存在推断百分比或ETA。
- 后续恢复同一个 frozen Goal 时，不要仅因为任务长期运行、detached 或 unattended 而反复要求相同批准；新的 artifact、recipient/provider、resource、purpose、backend 或 Goal 外副作用仍按正常审批规则处理。
- optional diagnostic failure 不得自动终止整个 Goal；如果 lock、heartbeat、stage-state、checkpoint 或 output evidence 提供了更强状态，应以这些证据为准。
- tmux session、Slurm job、PID、heartbeat 或 checkpoint 只证明活动或状态，不证明 Goal 完成；原 Goal 的 positive completion criteria 仍是完成声明的唯一依据。

禁止因为 tmux 启动或诊断不方便而自动 fallback 到 `setsid`、`nohup`、裸后台 `&`、`screen`、`sudo`、新 allocation、cancellation 或其他 persistence mechanism。若 explicit kickoff 后 canonical tmux launch 仍被拒绝，报告 exact rejected command 和 exact rejection reason，不要绕过。
