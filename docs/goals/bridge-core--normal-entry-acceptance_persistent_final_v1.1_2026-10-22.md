# 本轮真实正常入口验收任务：Persistent Goal v1.1

日期：2026-10-22
task_key：bridge-core--normal-entry-acceptance
状态：FROZEN_CONTRACT_FOR_FINAL_EVALUATION；仅在 execution-ready Critic PASS、用户明确批准、实施后的 pre-final Critic 放行后运行。

Persistent execution: REQUIRED
Backend: tmux
Goal source: docs/goals/bridge-core--normal-entry-acceptance_persistent_final_v1.1_2026-10-22.md
Run/session key: bridge-core--normal-entry-acceptance-final-v1_1
Working directory: .
Launch argv: ["python3","results/bridge-core--normal-entry-acceptance/validation/run_once.py","--plan","docs/design/0.11.1_normal_entry_capability_acceptance_execution_plan_v1.1_2026-10-22.md"]
Progress mode: count
Progress owner: bridge-child
Progress source locator: bridge-state
Expected progress update seconds: 300
Notify: ON
Recipient override: NONE
Notification cadence minutes: 60
External notification attempt cap: 6

## 真实业务目标

对固定十二项 Bridge 正式能力逐行通过各自真实正常入口或可核实的历史实证做事实判定，交付原始证据索引与可读结论。不是虚构测试任务、空跑计时器或只测试邮件。Program Run 明确排除。

业务进度单位：已经作出实际证据判定（通过、失败或缺证据）的正式能力行数，total=12；不是 PASS 项数。只有实际完成了一行原始来源核对与结论，primary child 才可通过正式 ai-bridge persistent-run progress update 报一个新 completed 值。不得从另一个 Gate driver 或外部脚本代写进度、制造阶段或直接调用 notifier helper。

## 冻结来源与启动保护

唯一任务方案：docs/design/0.11.1_normal_entry_capability_acceptance_execution_plan_v1.1_2026-10-22.md
唯一消费者/模型/GitHub分支和预算：上述 Plan 同版 Kickoff。
实际生成的 run_once.py 在正式最终候选 commit 中；在 pre-final 复核时必须证明它只执行固定真实入口、不替换模型或专业 reviewer、不预填 progress。启动前必须以 --expected-goal-sha256 绑定本文件实际 SHA-256，并验证当前 HEAD 是同一个已审 candidate。
不得从工作树的动态文件内容推断额外授权。

## 成功边界

正常运行要从正式 persistent-run start 到真正 primary child、supervisor、来源有效进度、status/history/ETA、真实 Notifier/Clear Writing/Gmail 和最后 progress/exit。三个真实有效点跨十分钟后才有 ETA，时间不足、历史证据不适用或业务行数不实则对应验收不通过，不能 sleep、增加无意义计算或第二次最终运行。

六席预算的第七个不同通知事件、抢 terminal reserve、DELIVERY_UNKNOWN、crash/recover/retry 由同一 final candidate 的正式 Persistent 启动入口确定性故障回归单独证明；这些故障回归不得替代本真实运行的外部邮件完整链。任何一项必需 Gate 失败，ALL_FORMAL_CAPABILITIES_ACCEPTED_EXCEPT_PROGRAM_RUN=NO。
