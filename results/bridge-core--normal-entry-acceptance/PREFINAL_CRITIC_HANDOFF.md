# 0.11.2 候选已完成实现与非 live 验证，待独立审查

批准范围内的 Host、Persistent、Notifier 与 Text Transform 修复已经完成。源码候选、离线安装、本地回归和 hosted CI 绑定同一提交；本轮没有启动最终批次，没有真实模型、付费 API 或 Gmail 调用，也没有更新正式机器安装或发行分支。下一步由独立 Critic 审查是否可进入已冻结的最终验收，不能将本交接当作其决定。

## 唯一身份与权限

- task：`bridge-core--normal-entry-acceptance`，沿用当前 Goal。
- approved package：`f87763e64d57784d11f69dcc1f3b63a898405d5c`；execution-ready PASS / READY_FOR_CODEX=YES 来自当前用户，不捏造独立 review 文件。
- branch：`work/bridge-core--product-scope-reset`。
- FINAL_CANDIDATE_SHA：`717d5b27bbca5d451276e6e4399ac7fc8107cf24`，version `0.11.2`。
- `44984ade5edeef5a60ef6cf8dd8d6faffbc34317` 只是已被替代的中间实现提交，不得拼接其测试或 CI 作为最终候选的结果。
- 正式 `release` 与当前 Longleaf canonical runtime 仍为 `0.11.1@ba9013b9fbbd242e51b09f9d09291f417df17652`；本轮不发布。
- 后续只增 results 证据，不改变上述 candidate；用户 `.gitignore` 保持原字节，未进入 commit。

## 实际修复

Host 的 sync 采用现有 GitHub HTTPS identity 检查，不放宽 Review/local identity parser；SSH/scp/file/非 GitHub/URL rewrite/错误作用范围在 effect 前拒绝。execpolicy 原始 `no_match` 明确保留为 `RULE_NO_MATCH / NATIVE_APPROVAL_UNVERIFIED`，不再改写成观察到的 prompt。

Persistent 把 publication identity/time 与 observation time 分开。重复读不增加 ETA 点或刷新健康时间；预热/重置、有效平台、坏源与来源超期有独立诊断，保留带来源时间的 last-good。status、binding history 和通知使用同一持久快照。RUNNING/PID/start、逻辑投递时钟、真实 wait 退出码和末次进度均先落盘后通知。ETA 统计函数及 recovery/resolve/run binding/tmux identity 等冻结函数逐字未变。

六席预算只落在既有 binding：五个普通席与一个真实 terminal 专席，helper 前持久占位。Notifier 从可信 state root 与 repo/run 推导 canonical binding，核对 Goal/launch/event/request digest/slot/cap/no-retry。失败、UNKNOWN、helper loss 和重复入口均不能退款或自动重试；席位耗尽不影响 child 或本地进度。permit 不进入 NotificationRequest 或模型输入。

Text Transform 复用现有 paid_review 的计数、锁、单次 USD0.25 上限、预留 Git 写回和实际用量回执。预留失败不发 Responses；重复及并发入口不重复计数/付费，zero-billing 预留也不能重用。Actions 按 branch 串行且 checkout 当前 ref，避免 rerun 回到旧 SHA 丢失已提交的预留。最终 writeback 暂存密文、结果和实际账本三项；账目未证时停止。未修改 paid_review、Text/Visual Review owner。

非 editable wheel 包含原有模板及 codex assets；未改 Lite/Review/Control/Overleaf/Clear Writing/Plugin Replay 核心。首个私有 Python3.12 环境因共享库依赖不能裸启动，已保留为本地 evaluator 环境诊断；最终固定路径使用独立可启动的 Python3.9 venv，仍安装同一最终 source SHA 的离线 wheel。没有用旧 CLI、PATH 替身或 symlink 转授候选信任。

## 同 SHA 证据

证据目录：`results/bridge-core--normal-entry-acceptance/validation/`。

| 检查 | 结果 | 原始证据 |
| --- | --- | --- |
| Python3.9 full | 522 tests，0 failure/error/skip | `LOCAL_PY39_TESTS.log` |
| Python3.12 full | 522 tests，0 failure/error/skip | `LOCAL_PY312_TESTS.log` |
| installed candidate targeted | 35 tests，0 failure/error/skip，生产 import 来自 venv | `INSTALLED_TARGETED_TESTS.log` |
| hosted CI | PASS，两个版本各522 tests；各4项 Codex-CLI 依赖跳过已由本机覆盖 | `HOSTED_CI.json`、`HOSTED_CI.log`；run `39791918957` |
| 离线非 editable 安装 | PASS；固定 CLI/Python、版本、wheel digest、所有 Python/template/codex bytes | `CANDIDATE_INSTALL_IDENTITY.json`、`OFFLINE_INSTALL.log` |
| diff/source-document identity | PASS；仅批准四个 Python owner+version；冻结 owner/ETA/恢复函数和六份批准来源原样 | `SOURCE_DOCUMENT_IDENTITY.json` |
| 受控 ETA | PASS；生产 publish/observe，0/300/600秒的2/5/8 of12，第三点预计余400秒 | `CONTROLLED_ETA_BUDGET_RAW.json` |
| 六席/失败/UNKNOWN/crash | PASS；production start→supervisor→binding→Notifier guard，真实短本地 child；只有外部边界为替身 | 同上；不是 live Gmail/Persistent final canary |
| 候选绝对 CLI 负例 | 4个真实平台入口拒绝，ref readback 不变；另有受控 fetch 边界的真实本地 Git FF 回归 | `DIRECT_CANDIDATE_CLI.json`、installed targeted log |
| machine 与 installed skill | writing-style0.5，两个批准 skill 存在；Notifier VALID/0600，已有 transport_ready=true | `MACHINE_AND_CANDIDATE_PREFLIGHT.json` |

CI：https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/39791918957

## 必须保留的环境与证据边界

当前机器 Host 相对正式0.11.1模板已有 drift：`default_mode_request_user_input` 为 true，managed AGENTS/rules 摘要也不同。原受信 CLI 的只读 validate 返回1；不得改成 PASS，也未运行 host install。其五个受信 wrapper 在原生 `--resolve-host-executables` 检查中可匹配 allow，add/commit 为 allow；部分普通 Git read 在该 Bridge rules 文件中是 no_match。没有用这个静态规则结果宣称当前会话已加载或 native approval 已通过。旧0.11.1日志中的 `prompt (no_match)` 不构成 prompt 事实；候选日志保留真实 no_match。候选绝对 CLI 的普通平台调用已实际执行，不借旧程序代验收；未来真正 HTTPS consumer FF 仍待最终外部授权。

机器 Notifier 复用现有账号与收件配置，不修改 provider/FROM/recipient：SMTP user `humc2013@gmail.com`，FROM/default TO `1155246312@link.cuhk.edu.hk`，prefix `[AI Bridge]`。只读结果不包含 password。SMTP readiness 是历史测试证据，不是本轮投递事实。

Text Transform 的冻结输入 SHA 和 instruction blob 已核对；既有 Actions secret 只检查 metadata，三项所需 secret 均 PRESENT，没有读 secret value。当前消费者尚无本任务 workflow（符合尚未执行初始发布），默认机器 PATH 没有 age；本地加密回归使用 `/tmp/bridge-nac-test-tools.YmR31B` 中从正式 age v1.2.1 源编译的真实工具，未做机器安装。输出接收密钥须在获准后经正式 create-output-receiver 创建并在第一次消费者远端写前冻结；不得临时换输入解密身份或宣称已经核对 secret value。

历史能力的完整原始证据不能只凭已发布版本或摘要自动通过。Review 的 CURRENT/REVIEW_2/RESULT/FINAL_REPORT 已实际全文读取；其旧 CI FAIL 与 bounded reviewer PASS 保持区别。055 Text Review 的完整结果与实际计费回执、manifest 已读：Terra 实际返回 BLOCKED，指早停文字/公式不一致，这是审核业务结果，不改写为文本产品质量 PASS。完整原文及 Overleaf0.6/Visual Review 原始输入链尚未全部就地定位；最终批次不得用 schema、摘要或本次 mock 补齐。详见 `HISTORICAL_EVIDENCE_INVENTORY.md`。

## 唯一后续边界

请独立 Critic 对该 exact candidate 给 `PROCEED_TO_FINAL_EVALUATION` 或 `REVISE`，明确处理以上机器 drift 与历史原始证据缺口；不重设计产品，不以本交接代替独立决定。只有获得 PROCEED 且用户明确批准具体外部作用，才能执行 v1.2 已冻结的最终一次批次。

外部预算仍为未消费、未授权：Lite≤1、Control≤6、PluginReplay≤1、Persistent Clear Writing≤6 个既定模型调用；SMTP≤6；Text Transform count≤1、Terra Responses≤1、USD0.25、同一消费者 branch≤3次 non-force 写。全部零自动重试，不增加 paid Visual/Text Review、Overleaf sync、Slurm、release/tag/Marketplace。

`run_once.py` 已固定在 candidate 中，只生成退出前 findings/index，12/12 表示核查行数，不表示12项PASS；自身终态留 PENDING_POST_EXIT。同一现有执行任务在真实 wait/TERMINAL/最后通知后读 status/binding/attempt，再补最终报告；没有第二个业务 child 或 finalizer。

状态：`READY_FOR_PREFINAL_CRITIC`；独立决定 `PENDING`；最终 live `NOT_RUN`；`ALL_FORMAL_CAPABILITIES_ACCEPTED_EXCEPT_PROGRAM_RUN=NO`；Program Run `INTENTIONALLY_EXCLUDED`。本交接不是 Goal 的最终完成声明。
