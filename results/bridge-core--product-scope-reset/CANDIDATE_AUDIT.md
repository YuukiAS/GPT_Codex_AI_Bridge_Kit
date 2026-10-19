# Bridge Kit 0.11.0 候选复核与恢复点

普通 helper 入口缺陷已修复，候选已通过 C1–C5 和确定性回归。用户在普通聊天授权后，
C6 已真实执行一次模型和一次 Gmail SMTP 发送，零重试；但两个必需 skill 的实际消费
无法由 JSONL 证明，生产路径按合同改用 deterministic fallback。因此 C6 未通过，
Goal 尚未完成，也不能交为 final Critic PASS。本次调用与发送额度已经用尽，不再尝试。

## 候选身份与纠错

- 用户指定的原候选：`147279107e3811dee279a337b85febb4e6c468b8`。
- 复核撤销原候选的 C5/C6 完整 PASS：生产父进程执行
  `python -m ai_bridge_kit.notifier _deliver-helper`，而模块没有 `__main__`
  入口；helper 退出码为 0，但不执行 delivery，也不生成 attempt。
- 修复后的生产候选：`c32b9100c673ac3c9472d52271709989438bbf99`。
  修复仅为 `notifier.py` 的模块入口和一项真实 helper 子进程回归。
- 同一分支：`work/bridge-core--product-scope-reset`，普通 non-force push。
- 旧 SHA 不被重新解释为修复后的源码；旧证据保留在本目录根部，新证据统一在
  `c32b910/`。后续只添加本目录证据时，被测生产候选仍是 `c32b910…`，不是证据提交。
- 原有 `.gitignore` 不暂存、不提交、不修改；SHA-256 保持
  `6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7`。

此次撤销来自真实 helper 子进程检查，不是因代码行数，也没有改变 v4 产品架构、
Gate 标准或 recovery 语义。原候选的失败保存在 `C5_C6_NORMAL_HELPER_FAILURE.json`。

## 当前 Gate 证据

| Gate | 修复后候选的证据 | 当前判断 |
| --- | --- | --- |
| C1 | 真实 Codex `execpolicy check` 正负例，真实受限同步与 dirty/main 拒绝；`c32b910/C1_C3_C4_C5_C6_TARGETED.txt` | PASS |
| C2 | `c32b910/C2_CONTEXT_AND_SOURCE_TRUTH.json`：Lite、Review 的计数 executable，Control 真实 launch adapter；错误 context/source 时零 child，partial clone 隔离 fallback | PASS |
| C3 | `c32b910/C3_MANAGED_INSTRUCTION_WRITE.json`：三个 CLI writer under-limit、overflow 全项目快照不变；targeted bank 另含真实并发 writer 与混合换行用户 bytes 断言 | PASS |
| C4 | `c32b910/C4_*.json`：正式 start/status/repeated start，同一 child 的坏 JSON、恢复、原生 warm-up、真实 exit；负例在 targeted bank | PASS |
| C5 | `c32b910/C5_MACHINE_NOTIFIER.json`：正式 CLI migrate 同/冲突、不删旧文件；两 repo 同一 config，冲突环境变量无效；真实 helper 并发去重/显式 retry lineage。四 consumer authority/nonfatal/suppression 在 targeted bank | PASS（无真实 SMTP） |
| C6 non-live | `c32b910/C5_C6_TRANSPORT_DEADLINE.json`：真实 helper 在受控 DNS/SMTP_CONNECT/TLS 挂起阶段被父 deadline 结束；模型与网络被测试审计钩子禁止。确定性 parser/fidelity/fallback 回归通过；15:34 UTC 主机边界 installed identity 已恢复一致 | PASS；不等于 live skill consumption |
| C6 live | `c32b910/C6_LIVE_SUMMARY.json`、`C6_LIVE_RAW_EVIDENCE.json`、`C6_MODEL_JSONL.json`：一 turn、模型一次、SMTP accepted 一次、retry 0；两个必需 skill 消费无证据，触发 fallback | FAIL：skill consumption 未证实；transport/fallback 单项通过 |

C2 的成功 child 是无模型的计数程序；C5 使用合成凭据、显式隔离 machine root 和
本地 SMTP 替身。它们只验证被冻结的执行/transport 边界，不伪称真实模型或 Gmail。
三个 hang 探针注入 1.5 秒测试 deadline；生产常量仍为 120 秒。测试不把网络故障
标成业务失败，也不自动重发 `DELIVERY_UNKNOWN`。

C4 canary 的唯一 child PID 为 3028502，15:18:11 UTC 启动，15:29:41 UTC 自然退出。
进度点时间为 15:18:11、15:23:26、15:28:26，跨 615 秒；中途 child 自己写入坏 JSON，
正式 status 返回进度 UNKNOWN 但仍 RUNNING，随后同一 child 恢复合法数据。
supervisor 形成 ETA `2026-10-19T15:33:33+00:00`，区间为
`15:33:26–15:33:41 UTC`。终态 exit_code=0，recover=TERMINAL，并明确要求另验原 Goal
完成标准。机器重启/丢失 supervisor/stale/mismatch/partial-start 的负例是受控 binding
身份注入与正常 recovery 函数验证，没有真实重启机器或破坏生产进程。

## 测试、CI 和安装核对

本地 Python 3.12：481 项，exit 0，8 项 age 相关可选测试跳过；Python 3.9：481 项，
exit 0，同样跳过 8 项。另有 25 项针对性验证全部通过，其中真实 Codex execpolicy
正负例未跳过。各 stdout 摘要在 `c32b910/LOCAL_*_TESTS.txt`。

Hosted CI 为 [run 39276862997](https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/39276862997)，
`headSha=c32b9100c673ac3c9472d52271709989438bbf99`，Python 3.9 和 3.x 均 success。
两个 job 各跑 481 项、跳过 4 项 Codex CLI 不存在的可选检查；这些在 Longleaf 的
targeted bank 实际执行。CI 的 age 测试没有借用本地 skip 作为 PASS。

README、QUICKSTART、AGENTS、CHANGELOG、双版本源及 CI 文件逐字与候选 Git blob
一致，hash 记录在 `c32b910/SOURCE_DOCUMENT_IDENTITY.json`。文档已核对 machine-only
Notifier、notify 默认 OFF、三点/十分钟 ETA、UNKNOWN/recover/resolve、SMTP accepted
边界、Clear Writing fallback/nonfatal 行为和原 Review/Control authority。

独立候选安装入口为 `/tmp/bridge-011-1472791-final-install/bin/ai-bridge`；目录名只是
安装环境 locator，不是候选 SHA。editable direct_url 绑定本仓库，版本为 0.11.0，
生产 bytes 与修复后候选一致；分支 HEAD 另含本目录证据提交，不冒充被测源码 SHA。
正式机器分发的 0.10.0 安装没有被切换。

Codex 仍为 `/users/a/e/aereinh/bin/codex`、0.160.1，
`CODEX_HOME=/users/a/e/aereinh/.codex`、OpenAI / `gpt-5.6-sol`。
复核期间发现 writing-style inventory 0.4 与 marketplace manifest 0.5 不一致；已用
`codex plugin add writing-style@yuukias-ai-skills --json` 刷新本机安装到一致的 0.5。
两个必需 skill `writing-fidelity`、`chinese-prose` 曾在这次刷新后从正式 installed/enabled
plugin 定位成功，未修改 AI_Skills_Collection 源码。但 15:27 UTC 的后续核验中，
inventory 又报告 0.4，manifest 仍为 0.5，resolver 返回
`WRITING_STYLE_PLUGIN_VERSION_MISMATCH`。15:34 UTC 的续查中，普通读取及实际 C6
主机边界均已恢复为 inventory/manifest 0.5 一致，两个必需 skill 均可定位，
machine Notifier 同时保持 VALID/transport_ready。最新证据见
`c32b910/LATEST_WRITING_STYLE_IDENTITY.json`；15:27 的失败仍可从 evidence commit
`a2fbd3e07aa1788f1ce261a565beb8d5e72752d3` 读取。此次续查没有再次安装插件，
也没有改 catalog、重启 daemon 或调用模型；安装身份阻断已关闭，但定位不冒充 live consumption。

机器 Notifier 仍是 `~/.ai-bridge/private/notifier.env`、0600、VALID、
transport_ready=true。已有用户确认收件的 send-test 是单独的兼容路径证据；它没有
调用 Clear Writing，不能用来关闭 C6 自动 production Gate。没有复制或记录 App Password。

核心生产 Python 相对正式 0.10.0 基线的非空行统计在
`c32b910/CORE_PYTHON_DELTA.json`：新增 3337、删除 165、净增 3172；不计 tests/docs/results。
这反映 v4 的后续范围，不把旧 checkpoint 的 1754 统计冒充当前值，也不机械压缩代码。

## C6 实际执行、失败证据与恢复点

此前平台自动审批两次拒绝 live 命令，未创建进程，未消耗额度。随后用户在普通聊天
明确回复“授权对 c32b910 执行上述 C6 live，一次模型、一封邮件、零重试，并完成收尾”，
该授权阻断已经解除，不能继续把本轮失败归因于平台审批或用户没有授权。

本轮执行绑定 `c32b9100c673ac3c9472d52271709989438bbf99`，使用已核对的 Codex
0.160.1 / `gpt-5.6-sol`、原 CODEX_HOME 和原 machine Notifier。15:41:49 UTC 开始，
15:42:02 UTC 记录 `SMTP_ACCEPTED`，总用时 12.370465 秒，未超过生产 120 秒 deadline。
只创建一个 logical event、一个 attempt、一份 accepted receipt；模型 invocation=1，
turn=1，automatic retry=0。SMTP accepted 不证明 inbox delivered，也未要求用户确认收件。

安全合成 NotificationRequest、实际模型 JSONL、render result、claim/attempt/receipt 已归档
到 `c32b910/C6_LIVE_RAW_EVIDENCE.json`。未输出或记录 App Password；请求不含私有正文、
日志、凭据、review body 或任意 evidence_paths。正式父进程/真实 helper 未被替换；
临时观察钩子仅记录 render 返回与 JSONL，并用 O_EXCL marker 阻止第二次模型启动。

实际模型 exit 0，JSONL 有一个 thread.started、turn.started、turn.completed，但仅有一条
agent_message 和一条 runtime warning，没有 skill/command_execution 消费事件。正式 parser
返回 `CODEX_SKILL_CONSUMPTION_UNPROVEN: writing-fidelity,chinese-prose`。因此不能因为
installed/enabled identity 正确、模型文本可读或 SMTP 成功，就宣称两个 skill 已被消费。
当前 prompt 只引用 skill 名，没有在 prompt 中明确绑定 resolver 得到的 exact skill paths；
这是后续修复需要处理的正常入口缺口，不能用宽松 parser 把缺失证据改判 PASS。

对同一已保存模型文本做纯离线 fidelity replay，还复现了
`CLEAR_WRITING_CONCLUSION_STRENGTHENED`：原 request 与模型都包含“不代表目标已完成”，
但当前 substring 检查把否定句里的“目标已完成”判为增强结论。这是独立误报，不是实际
模型宣称完成。本轮运行首先被 skill parser 拒绝；离线 replay 只揭示后续检查的问题，
没有绕过生产检查或发送模型文本。

`verify_c6_recorded_trace.py` 可重现上述两个结果，并验证实际发送文本逐字等于正式
`render_auto_plain(request)`；脚本 audit hook 禁止 subprocess 和 socket，新增模型/SMTP=0。
fallback 与非致命 transport 单项成立，但不能替代 v4 要求的正常 skill consumption。

本次授权的一次模型、一封邮件已全部消耗。需要先修复 exact installed-skill 消费和
否定句保真处理、冻结并验证修复候选；若继续关闭 live Gate，必然需要第二次真实模型
验证，因此停在用户明确规定的次数边界。不修改当前冻结 production bytes、不自动 retry，
也不再次运行 send-test。现有 C1–C5/CI 结果不被偷换到未来修复 SHA。

尚未达到 `C1–C6 完整证据已准备，可交 final Critic`。Goal 未完成；不把本报告
作为终态通过，不移动 `refs/heads/release`、tag 或 Marketplace。正式 release 仍为
`9db19b0409816c22042a246b35a33e1d34fedd0a`。
