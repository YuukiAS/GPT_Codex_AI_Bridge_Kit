## Persistent Run

本仓库已启用 AI Bridge Kit Persistent Run。它是 terminal-owned、必须 survive disconnect 的可选执行层，不是 Lite / Review / Control 之外的新 workflow、role、watcher 或 state machine。overnight、unattended、multi-hour 本身不选择 tmux；scheduler-owned batch 或 already-detached service 保持原生寿命 owner。

使用前分别判断 upfront authorization、process lifetime owner 和 project-native progress。仅当 Goal/task 写明 `Persistent execution: REQUIRED` 时：

- 读取当前 Goal 和 contract；仓库模板不能代替当前用户对同一 frozen Goal 的 explicit kickoff。缺少授权时，用 `ai-bridge persistent-run prompt kickoff --target <repo> --goal <goal>` 生成并等待用户发送；启动 tmux 或昂贵前置工作前完成此检查。
- normal entry 仅用 `persistent-run start/status`。每个 run 只有一个 full-launch-id exact tmux session、一个 run-scoped supervisor、一个 machine-local binding 和一个 child；使用 Goal 冻结的 launch argv，不发明通用科研 orchestrator。
- compatible active run 只返回 existing。stale、mismatch、partial start 或 supervisor loss 返回 UNKNOWN/UNAVAILABLE 或 CONFLICT，不 relaunch、takeover 或猜 terminal。
- 异常先用 `persistent-run recover` 分类；只有 `SAFE_TO_CLOSE_STALE` 才能带 exact launch id 执行 `persistent-run resolve --close-stale`。不得删除 binding；resolve 不写 exit code 或 semantic completion。exit code 只能来自 supervisor 对真实 child 的 `wait()`。
- 进度只取 contract 的 `Progress source locator`。`bridge-child` 通过 `persistent-run progress update` 原子写入 Bridge 注入路径；supervisor 每 60 秒观察，missing/半写/坏 JSON 不杀 child。count/fraction 至少三个有效点且跨十分钟才估算 ETA。`report/latest` 不需要对应的 tmux session；不要从 tmux/PID 存在推断进度或 ETA。
- `Notify: ON` 只发送运行事实；不得把 start/progress/stall/exit 升级成 Goal PASS/READY/完成。Notifier 未 ready 时不启动新 child；通知失败不杀 child。
- disconnect、optional diagnostic failure 不等于任务失败；优先使用 lock、heartbeat、stage-state、checkpoint、output 等更强证据。同一 frozen Goal 不因长期或 detached 反复授权；artifact、recipient/provider、resource、purpose、backend 或 Goal 外 effect 变化仍需新授权。
- session、Slurm job、PID、heartbeat、checkpoint 只证明活动或状态；原 Goal positive completion criteria 才能证明完成。

不得因 tmux 启动或诊断失败而 fallback 到 `setsid`、`nohup`、裸 `&`、`screen`、`sudo`、新 allocation/cancellation 或其他 backend。canonical launch 被拒绝时报告 exact command/reason，不绕过。
