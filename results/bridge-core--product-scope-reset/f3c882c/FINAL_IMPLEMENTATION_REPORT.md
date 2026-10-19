# Bridge Kit 0.11.0 实现收尾

实现与 C1–C6 验证已完成，可交 Final Critic。唯一生产候选为
`f3c882c5302a1889cac62526e8f025ada0f4d1a5`；当前状态是
`READY_FOR_FINAL_CRITIC`，不是 Final Critic PASS，也不是正式发布。

## 范围与身份

任务仍为 `bridge-core--product-scope-reset`，分支仍为
`work/bridge-core--product-scope-reset`。按批准的 v4 Goal/Plan/Architecture 实现，
保留原 Lite/Review/Control authority，未恢复旧 app-server、Progress display thread、
worktree exchange、three-intent event bus 或常驻 Codex reader。

Host 安全操作、exact context/source preflight、三个 AGENTS writer、Persistent
lifecycle/progress/ETA/recovery、机器级 Notifier 与单次 Clear Writing 已完成。
AGENTS 用户区域 byte-preserving，预算超限零 mutation；Notifier 唯一 transport authority
仍是 `~/.ai-bridge/private/notifier.env`，生产进程变量不覆盖；通知失败不改变业务状态。

本次 live 前后均确认生产源码、templates、tests、README/QUICKSTART/AGENTS/CHANGELOG、
version 与 CI 配置逐字匹配该 candidate。独立 editable 安装为 0.11.0，指向本仓库；
正式机器发行安装未切换。后续 results-only evidence commits 不构成新生产候选。
用户 `.gitignore` 原样保留，不纳入提交。

## 同一 SHA 的完整验收

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 确定性回归 | PASS，Python 3.9/3.12 各 486 项、exit 0；30 项定向检查通过 | LOCAL_PY39_TESTS.txt、LOCAL_PY312_TESTS.txt、TARGETED_TESTS.txt |
| C1 Host 边界 | PASS，真实 Codex execpolicy 与 bounded Git 正负例 | TARGETED_TESTS.txt |
| C2 exact context/source | PASS，正常入口及错误 context/source 零 child | C2_CONTEXT_AND_SOURCE_TRUTH.json |
| C3 managed instruction | PASS，三个正常 writer、用户 bytes、overflow、并发写锁 | C3_MANAGED_INSTRUCTION_WRITE.json、TARGETED_TESTS.txt |
| C4 Persistent | PASS，真实正式 start/status/repeat start、615 秒量化进度、ETA、坏进度恢复、真实 child.wait exit 0；身份/recovery 负例 | C4_PRODUCTION_CANARY.json、C4_*.json、TARGETED_TESTS.txt |
| C5 machine Notifier | PASS，一个配置/两个 repo、迁移/冲突、显式 retry、四个真实 consumer、跨 repo 隔离、process override 无效 | C5_MACHINE_NOTIFIER.json、TARGETED_TESTS.txt |
| C6 非 live | PASS，正式 parser/fidelity/fallback、保存 trace 离线 replay、120 秒生产 deadline 的受控 timeout 验证 | C6_OFFLINE_REPLAY.json、C5_C6_TRANSPORT_DEADLINE.json、TARGETED_TESTS.txt |
| C6 live | PASS，一次 gpt-5.6-sol、单 thread/turn、NORMAL_WRITING_STYLE、fidelity PASS、一封 SMTP_ACCEPTED、零重试 | C6_LIVE_RAW_EVIDENCE.json、C6_MODEL_JSONL.json、C6_RENDER_RESULT.json、C6_SMTP_RECEIPT.json |
| hosted CI | PASS，run 39281651220，head SHA 与生产候选完全一致 | HOSTED_CI.json、HOSTED_CI_TEST_SUMMARY.txt |
| 文档/版本/安装身份 | PASS，生产 bytes 未变 | SOURCE_DOCUMENT_INSTALL_IDENTITY.json、C6_LIVE_RAW_EVIDENCE.json |

本地 age 依赖缺失跳过的 8 项在 CI 实际执行；CI 未安装 Codex 的 4 项在本地实际执行。
CI Python 3.x job API 滞后为 queued 的原始响应保留，判断使用 run completed/success
与两组真实 checkout/test 日志，不伪造单 job metadata。

## 最后一次 live 的边界

本次明确授权只适用于 f3c882c，16:28:04–16:28:18 UTC 执行，耗时 13.973 秒。
预检发现机器默认模型已变为 gpt-6.1-sol；归档的临时启动器仅添加官方
`--model gpt-5.6-sol` 参数后 exec 同一个 0.160.1 CLI，未改变持久 config、CODEX_HOME
或生产源码。正式 automatic deliver、一次性 helper、renderer 和 sender 均未替换。

installed/enabled writing-style@yuukias-ai-skills v0.5 的两个真实 Skill 身份、显式
`$writing-fidelity` / `$chinese-prose` 调用、returncode 0 与单次边界共同满足批准的
invocation contract；不要求 JSONL 必须提供 skill-load event。
“不代表目标已完成”保真通过，没有正向 completion 升级，没有 fallback。

唯一 SMTP attempt 为 `96470c569e1d408f808c2abc78e37565`，无 retry parent，
receipt 在 16:28:18 UTC 记录 SMTP_ACCEPTED。账号、FROM、默认 recipient、config digest
全部保持现有值；没有秘密回显、额外私有输入或新 provider。SMTP accepted 不等于
inbox delivered。本次预算已耗尽，不允许再次运行 live harness。

旧 c32b910 的 live failure 与 raw trace 保留；离线修复证明没有冒充新 candidate 的
最终 live PASS。这次新 raw/receipt 才是本候选 C6 live 证据。C1–C5 与 C6 非 live
在同 SHA 已通过，本次没有回归，不重复运行，也不改写其旧执行时间。

## 交接状态

`implementation_complete=true`，`workflow_state=READY_FOR_FINAL_CRITIC`。
当前实现 Goal 达到约定收尾点，未另建 Goal；Final Critic 决定仍待外部角色作出。

`refs/heads/release` 保持 `9db19b0409816c22042a246b35a33e1d34fedd0a`（0.10.0）。
未移动 release/tag，未正式发布 Marketplace；formal distribution-complete=false。
报告与 acceptance 更新只作为结果证据提交和普通同分支发布，不扩大本次授权。
