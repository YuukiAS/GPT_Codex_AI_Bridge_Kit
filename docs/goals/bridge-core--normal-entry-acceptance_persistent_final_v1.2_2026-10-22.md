# Bridge Kit 正常入口最终业务任务：Persistent Goal v1.2

日期：2026-10-22
task_key：bridge-core--normal-entry-acceptance
状态：待 execution-ready Critic 与用户 Kickoff 授权；此文件不是执行许可。

Persistent execution: REQUIRED
Backend: tmux
Goal source: docs/goals/bridge-core--normal-entry-acceptance_persistent_final_v1.2_2026-10-22.md
Run/session key: bridge-core--normal-entry-acceptance-final-v1_2
Working directory: .
Launch argv: ["/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit/private/exports/bridge-core--normal-entry-acceptance/candidate-venv/bin/python","results/bridge-core--normal-entry-acceptance/validation/run_once.py","--plan","docs/design/0.11.1_normal_entry_capability_acceptance_execution_plan_v1.2_2026-10-22.md"]
Progress mode: count
Progress owner: bridge-child
Progress source locator: bridge-state
Expected progress update seconds: 300
Notify: ON
Recipient override: NONE
Notification cadence minutes: 60
External notification attempt cap: 6

## 业务任务与进度含义

唯一业务仍是用户要求的十二项 Bridge Kit 正式能力正常入口验收，Program Run 唯一排除。主进程必须消费真实正式入口或完整原始证据，完成十二行退出前证据核查，生成 `results/bridge-core--normal-entry-acceptance/validation/PRE_TERMINAL_FINDINGS.md` 和 `EVIDENCE_INDEX.json`；每一行记录消费者、入口、候选身份、原始依据、实质判断及缺失事实。

主进程仅通过 `/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit/private/exports/bridge-core--normal-entry-acceptance/candidate-venv/bin/ai-bridge persistent-run progress update` 自己报告完成的退出前证据行数，`count/total=12` 不代表十二项能力已最终通过。Persistent 和 Notifier 的真实退出码、终态持久化、最后通知只能写为 `PENDING_POST_EXIT`；主进程不可以在尚在运行时认定自己已退出，也不能补写不存在的 SMTP 证据。

## 唯一运行来源

专用候选虚拟环境 Python：`/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit/private/exports/bridge-core--normal-entry-acceptance/candidate-venv/bin/python`；CLI：`/overflow/htzhu/mingcheng_new/GPT_Codex_AI_Bridge_Kit/private/exports/bridge-core--normal-entry-acceptance/candidate-venv/bin/ai-bridge`。待 0.11.2 最终候选提交冻结后，必须离线构建、非 editable 安装此 SHA 的包；验证解释器、安装源码、版本、wheel 摘要、CLI、工作树 HEAD 与冻结候选全部对应。正式 start/status/recover、tmux Supervisor（使用调用方 `sys.executable`）、主进程和 progress update 均通过此同一环境，不调用机器已有的 0.11.1、系统 `python3` 或其它分支。

用上述唯一 CLI 执行正式 `persistent-run start`，参数 `--target .`、`--goal docs/goals/bridge-core--normal-entry-acceptance_persistent_final_v1.2_2026-10-22.md` 与 `--expected-goal-sha256` 必须逐字使用同版 Canonical Goal 中外部冻结的准确 64 位 SHA-256；本文件自身不嵌入自身摘要，以免产生哈希自引用。单个 Goal 不允许自动第二次 start、更换子进程或调用额外模型。

## 运行完成后的判断

在该进程退出、Supervisor 记录真实 `child.wait()`、保存最终进度和 `exit_code`、尝试终态通知后，由**同一现有最终验收步骤**使用以上 CLI/Goal SHA 调用 `persistent-run status`，读取原始 binding 与 Notifier attempt/SMTP 记录，再补齐 Persistent/Notifier 两行并生成最终 `NORMAL_ENTRY_ACCEPTANCE.md` 与完整 `EVIDENCE_INDEX.json`。任何缺证或失败记 NO，进程退出零或 SMTP_ACCEPTED 不自动代表业务通过。

ETA 数值正例按同版 Proposal/Plan 中用户批准的受控时钟测试，以真实格式进度 `(0s,2/12),(300s,5/12),(600s,8/12)` 经同一候选生产进度发布/观察代码得到；不要求真实任务人为运行十分钟，不把受控时间称为墙钟时间或真实发信。独立的真实正常入口、Gmail、六席预算、第七次阻断与恢复依旧必须符合原批准产品标准。

任何真实模型、SMTP 或 AI_Skills 消费者的最终 GitHub 写入，都必须先得到 execution-ready Critic、当前用户 Kickoff 和实现后 pre-final 独立 Critic 放行；本文件不授权生产影响或正式发布。
