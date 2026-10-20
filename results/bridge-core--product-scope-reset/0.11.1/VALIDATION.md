# 0.11.1 修复与非 live 验证完成

唯一生产候选为 `ba9013b9fbbd242e51b09f9d09291f417df17652`。本轮只修通知 cadence，
没有重新设计进程寿命、ETA estimator、Notifier、Clear Writing 或其他 workflow。
源码、测试、README/QUICKSTART/CHANGELOG、TODO 收口和版本均在该候选中冻结。
之后的 results-only 修正和证据提交不是新的生产候选，也不能成为 release target。

## 验证结果

定向 61 项 PASS；Python 3.9 / 3.12 全量各 496 项 PASS、各跳过 8 项 age 依赖测试。
Hosted CI run 39367527196 同 SHA success，Python 3.9 / 3.x 各 496 项、各跳过 4 项
本机 Codex CLI 可选检查；CI 安装 age，补足本地不可用的加密传输覆盖。
本地保留真实 Codex execpolicy 只读校验，不调用模型。

| 要求 | 确定性证据（`tests/test_persistent_cadence.py`，除非另有说明） |
|---|---|
| A/B/C 高频 fraction/count、不刷通知也不 starvation | `test_frequent_fraction_and_count_observations_do_not_spam_or_starve`：每 5 分钟观察，只有 0 分钟 start/resume 和 60 分钟 periodic；65 分钟仍 suppress；latest/history 继续更新。 |
| D/E 阶段与异常提前投递 | `test_early_stage_and_exceptional_status_transitions`：stage、stalled/blocked/failed/complete；重复异常 suppress，恢复正常后再次异常仍能提前发。 |
| F/G ETA material / jitter / UNKNOWN | `test_eta_materiality_uses_last_delivery_and_preserves_threshold`：25% 与 15 分钟边界、累计偏移相对上次投递、已知与 UNKNOWN 双向变化。 |
| cadence 基线与下限 | `test_early_delivery_restarts_cadence_not_observation`；`test_report_enforces_fifteen_minute_floor_and_reads_old_reports`。 |
| H/I terminal 不受 cadence 阻断、transport failure 不影响 child/lifecycle | `test_supervisor_uses_delivery_clock_and_terminal_survives_transport_failure`：真实生产 supervisor 函数配假时钟/假 child/假 sender；0 分钟 start、60 分钟 progress、70 分钟 terminal，所有 transport 均模拟失败，仍记录 child exit 0；更新或不变的 source timestamp 都验证。不是 live canary。 |
| J Persistent/Lite terminal owner 去重 | `tests/test_readiness.py::ReadinessTests.test_persistent_runtime_owner_suppresses_lite_notification`，代码未改，定向与全量均通过。 |

`CANDIDATE_AUDIT.json` 校验所有非 results 候选文件与工作树 bytes 相等，并核对从正式
0.11.0 基线的 diff 只含授权路径。Persistent 只有 `_delivery_decision`、
`report_progress_file`、`supervise_binding` 改变；`estimate_progress_eta`、`_eta_changed`
及其他函数和冻结 owner 原样保留。所有 11 份 TODO 原历史正文保留，已关闭的两份未改。
总账为 0 个 active Bridge-owned short-term TODO；Program Run 是有意排除的未来方向。

## 本地测试入口修正（仅 evidence，不改候选）

早期保护脚本把 `execpolicy check` 的 inert `codex exec` 参数误认为真实模型启动，
并且没有隔离默认 machine state，触发只读文件系统错误。两次无效本地验证的原日志
保留为 `INVALID_GUARD_*` 和 `INVALID_STATE_*`，不记作产品失败或 PASS。
最终脚本只拦实际 exec 子命令/SMTP，并为每次 suite 使用独立临时 state，不改 HOME、
真实 machine config 或用户文件。最终 FULL/TARGETED 日志没有保护脚本触发或测试失败。
其中 mock send_test backend 回归不是运行真实 send-test；模型、Gmail、真实 canary 均为 0。

本报告及现行中文文档已按写作保真与中文审校核对，保留 exact 技术值和证据限定；
没有新建 Planner/Critic 轮次、子 Goal、tag、GitHub Release 或 Marketplace 发布。
