# 当前候选：v6 窄修，等待同一 Critic

FINAL_CANDIDATE_SHA=`0aef27850a91e415305458aef1d1d60506841d9b`。
v6 route/projection 窄修、50 项定向回归、两版本各 490 项全量、同 SHA hosted CI 和
diff boundary/source-document identity 已完成。当前交接见
`v6/0aef278/IMPLEMENTATION_HANDOFF.md`、`ACCEPTANCE_STATUS.json` 与 `FINAL_EVALUATION_PLAN.json`。
机器 installed plugin inventory/manifest 版本不一致单列为环境诊断，未放宽生产检查。

最终 Persistent 正常入口通知链尚未运行；本轮模型/Gmail/send-test/final canary 均为 0。
等待同一 Critic 的 PROCEED_TO_FINAL_EVALUATION / REVISE，不请求或消费 live 授权。
下文完整保留的是 f3c882c 历史阶段记录，不是 v6 candidate 的 live PASS 或当前最终验收。

---

# 历史：Bridge Kit 0.11.0 f3c882c 修复候选与 Gate 记录

两个 Bridge 实现误判已修复。保存的 C6 trace 在修复后的正式 renderer 中离线回放，
返回 NORMAL_WRITING_STYLE；本地全量回归、C1–C5 与 C6 非 live 验证通过。
同 SHA 的 hosted CI 已完成并成功，两组执行日志均确认 486 项测试通过。
用户随后明确授权该 exact candidate 最后一次 C6 live；本次一次模型、单 turn、
NORMAL_WRITING_STYLE、保真检查和一次 Gmail SMTP accepted 全部通过，零重试。
C1–C6 全部绑定同一生产候选，当前实现 Goal 已达到 READY_FOR_FINAL_CRITIC。
该状态不是 Final Critic PASS，也不是正式发布；旧 live run 不充当新候选证据。

## 唯一生产候选

- FINAL_CANDIDATE_SHA：`f3c882c5302a1889cac62526e8f025ada0f4d1a5`。
- 分支：`work/bridge-core--product-scope-reset`，普通 non-force 发布。
- 后续 results-only 证据提交不是新生产候选。生产代码、tests、templates、
  README/QUICKSTART/AGENTS/CHANGELOG、双版本源、CI 与候选 Git bytes 核对一致。
- 版本仍为 0.11.0 source candidate；没有宣称正式发行。
- 用户原有 `.gitignore` 未修改、未暂存，SHA-256 为
  `6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7`。
- `refs/heads/release` 仍为正式 0.10.0：
  `9db19b0409816c22042a246b35a33e1d34fedd0a`。没有移动 release、tag 或 Marketplace。

## 本轮修复及原判断纠正

先前 c32b910 的模型 returncode=0，installed writing-style v0.5 和两个必需 skill 身份
均有效，prompt 已显式使用两个 `$skill-name`。该次 JSONL 没有单独的 skill-load 事件，
也没有 shell 读取 SKILL.md；这不应被 Bridge 反推为 skill invocation 失败。

根据用户本轮明确批准的证据语义，启动前仍唯一解析 installed/enabled
`writing-style@yuukias-ai-skills`，验证 manifest/version 与必需 skill 身份；
prompt 从 REQUIRED_SKILLS 生成显式 `$writing-fidelity` 和 `$chinese-prose` 调用。
JSONL 继续用于单 thread/turn、成功边界、顺序和错误校验，不再要求不存在保证的加载事件。
保留 plugin/version/path 和 explicit_prompt invocation metadata，不伪造 skill-load 观测。
正式用法参考 [OpenAI skill invocation 文档](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills)。

fidelity checker 只放行紧邻目标表述的明确否定/限制语义。“不代表目标已完成”、
“并不能说明目标已完成”、“尚不能认定目标已完成”均合法；正向“目标已完成”、
“发布就绪”、READY、RELEASE_READY、Goal PASS 仍被拒绝。否定句后再附加正向升级、
跨句正向声明和双重否定也有拒绝回归。当前 runtime startup warning 不冒充 fatal failure；
真正的顶层/嵌套 error、turn.failed、非法 JSONL 和边界错误仍触发 fallback。

只修改 clear_writing.py、对应 tests 和同步的 README/AGENTS/CHANGELOG；
没有修改 AI_Skills_Collection、provider/recipient、Persistent recovery 语义或产品架构。
QUICKSTART、templates 和 version 无需行为变更，已按新候选逐字核对。
本轮两个已命名写作 Skill 用于报告的中文表达与候选/证据保真，不扩大实现范围。

## 同 SHA 的证据

以下 locator 均在 `f3c882c/`，每份机器证据携带完整 candidate_sha。

| Gate | 正常入口或确定性证据 | 状态 |
| --- | --- | --- |
| C1 | TARGETED_TESTS.txt：真实 Codex execpolicy 正负例、受限同步及 main/dirty 拒绝 | PASS |
| C2 | C2_CONTEXT_AND_SOURCE_TRUTH.json：Lite/Review/Control launch 边界、wrong context/source 零 child、隔离 blob fallback | PASS |
| C3 | C3_MANAGED_INSTRUCTION_WRITE.json：三个 CLI writer、用户 bytes 保留、overflow 零项目 mutation；TARGETED_TESTS.txt 包含并发写锁 | PASS |
| C4 | C4_PRODUCTION_CANARY.json、C4_*.json：正式 start/status/repeat start、坏进度与恢复、原生 ETA、真实 exit/recover；负例在 TARGETED_TESTS.txt | PASS |
| C5 | C5_MACHINE_NOTIFIER.json：同机器配置双 repo、process override 无效、迁移同/冲突且保留 legacy、并发去重/跨 repo 隔离/显式 retry；四 consumer 在 TARGETED_TESTS.txt | PASS，隔离 transport |
| C6 non-live | C6_OFFLINE_REPLAY.json、C5_C6_TRANSPORT_DEADLINE.json、TARGETED_TESTS.txt | PASS |
| C6 live | C6_LIVE_RAW_EVIDENCE.json、C6_MODEL_JSONL.json、C6_RENDER_RESULT.json、C6_SMTP_RECEIPT.json：本次 exact candidate 的真实单次调用与发送 | PASS |

C2 的成功子进程是无模型的计数程序。C5 使用显式 temporary config/state root、
合成凭据和本地 transport 替身；不把这些证据说成真实 Gmail。三个受控 DNS/
SMTP_CONNECT/TLS hang 在 1.5 秒注入 deadline 下均被父进程终止并 reaped，业务继续，
记 DELIVERY_UNKNOWN；生产 deadline 仍为 120 秒，没有自动重发。

C4 使用新的 disposable Git repo `/tmp/bridge-c4-f3c882c`，Notify OFF。
唯一 child PID=3320602，15:56:34 UTC 启动、16:08:19 UTC 自然退出，exit_code=0。
15:56:49、16:02:04、16:07:04 三个真实 count 点跨 615 秒；中途 child 自己写坏 JSON，
supervisor 记录 UNAVAILABLE、status 返回进度 UNKNOWN，但同一 child/supervisor 继续，
随后恢复 AVAILABLE。原生 ETA=16:12:11 UTC，区间 16:12:04–16:12:19 UTC。
repeat start 返回 RETURN_EXISTING；终态 recover 要求另验原 Goal 完成标准。
stale/mismatch/partial-start/supervisor-loss/machine-identity recovery 负例使用受控身份
fixture 与生产 recovery/resolve 函数，没有真实重启机器、破坏性 kill 或手工删除 state。

## 离线 replay 与真实预算

`verify_c6_recorded_trace.py` 用当前安装的真实 plugin inventory/manifest/skill 身份，
只把模型 response 替换为保存的 stdout/returncode，其他 parser、fidelity 和 render_once
均为修复后的生产逻辑。审计钩子禁止 socket 和 model subprocess，唯一允许的 subprocess
是只读 plugin list。结果为 NORMAL_WRITING_STYLE、failure 为空、retry=0。
返回字段 model_invocations=1 表示一次被录制 response 替代的逻辑步骤，该离线回放实际新增模型=0、
SMTP=0；C6_OFFLINE_REPLAY.json 的外层字段明确记录该区别。

保存源来自 `c32b910/C6_LIVE_RAW_EVIDENCE.json` 和 `C6_MODEL_JSONL.json`，
stdout SHA-256 为 `542bbbe9b012181b10ce70553f6043a644ca3d0e0512a324ad0c4ba144c99c98`。
旧现场确实发生一次模型、一封 fallback 邮件，SMTP accepted；这些事实及原始记录不改写。
旧 Bridge 误报已由本轮纠正，但旧 run 不被倒签成新 SHA 的最终 live PASS。

## 新候选的最后一次 C6 live

用户在修复与同 SHA 非 live 证据完成后，明确授权 f3c882c 最多一次真实模型、
一封现有配置 Gmail、零重试。正式 automatic deliver 从 16:28:04 UTC 到
16:28:18 UTC，耗时 13.973 秒；没有重跑 C1–C5 或 C6 非 live，没有改生产源码。

CODEX_HOME 仍为 `/users/a/e/aereinh/.codex`，CLI 仍为
`/users/a/e/aereinh/bin/codex`、0.160.1。预检发现机器默认 model 已变为 gpt-6.1-sol，
因此测试用临时 CLI 启动器仅在 exec 参数中添加 `--model gpt-5.6-sol`，调用同一
canonical CLI；没有改机器 config、CODEX_HOME、provider 或候选源码。
这个启动器是已归档的 Gate harness，不是新增生产组件；plugin list 原样转交，
正式 deliver helper、render_once、parser、fidelity 与 SMTP sender 均未替换。
完整启动参数、启动器和 canonical wrapper digest 均保留，未把 shim 隐瞒为原 CLI 路径。
单次模型参数的正式依据是 [CLI 参数说明](https://learn.chatgpt.com/docs/developer-commands?surface=cli)。

当前 installed/enabled `writing-style@yuukias-ai-skills` inventory/manifest version=0.5，
真实存在 writing-fidelity 与 chinese-prose；生产 prompt 显式调用两个 `$skill-name`。
returncode=0，thread.started / turn.started / turn.completed 各一次；正常输出保留
running、UNKNOWN、任务/运行身份、0.11.0 和“不代表目标已完成”，fidelity 通过。
stdout SHA-256 为 `0b2be74e13485ac545912bc0665ea4597c3451e0d6c2fddad2269edb52913b3e`。
JSONL 的 default_mode_request_user_input 启动警告不是 fatal failure；没有把缺少
skill-load event 误判为未调用 Skill，也没有声称观测到不存在的加载事件。

唯一 machine config 保持 VALID / 0600，digest 与授权前一致；SMTP account、FROM、
默认 recipient 均未变，App Password 没有输出、复制或写入证据。
event key=`3d98e8c6534c98cb6f89272dce7db828e1341cc599ef97d0142c52f40bd9d6d1`，
唯一 attempt=`96470c569e1d408f808c2abc78e37565`，parent_attempt_id=null，
expression_mode=NORMAL_WRITING_STYLE，16:28:18 UTC 记录 SMTP_ACCEPTED receipt。
这只证明 SMTP server 接受，不证明 inbox delivered。一次模型、一封邮件的本次预算已耗尽，
没有任何自动重试，不再执行 live harness。完整原始 JSONL、renderer 返回和 receipt
归档在新候选目录，旧 c32 证据与机器状态未删除。

## 全量回归、CI、安装与文档

本地 Python 3.12 全量 486 项，120.637 秒、exit 0，8 项 age 可选测试因环境依赖缺失跳过；
Python 3.9 同样 486 项、123.403 秒、exit 0，跳过相同 8 项。
30 项针对性测试 25.727 秒全部通过，真实 Codex execpolicy 检查未跳过。
初次普通 sandbox 跑全量时有 8 个默认机器状态目录只读错误；按正式显式
AI_BRIDGE_STATE_HOME 测试隔离后重跑通过，没有修改 HOME、CODEX_HOME 或生产 transport config。
准备阶段的拒绝与修正记录在 REPAIR_SCOPE_AND_AUTHORITY.json。

Hosted CI：
[run 39281651220](https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/39281651220)，
headSha=`f3c882c5302a1889cac62526e8f025ada0f4d1a5`，run=completed/success。
两组真实执行日志均确认 checkout 该 exact SHA 后运行 486 项、OK (skipped=4)。
四项跳过都是 hosted runner 未安装 Codex CLI 的检查，本地定向 bank 已实际执行；
CI 安装了 age，对应八项本地 skip 在 CI 不跳过。
Python 3.x 的 job-list/detail 响应仍显示滞后的 queued，与实际日志及 run 终态不一致；
原始不一致响应保存在 HOSTED_CI.json，未篡改为成功。CI 判断依据是该 run 的成功终态
加上两组实际 checkout/test 日志，而不是旧候选或单个局部步骤。摘要见 HOSTED_CI_TEST_SUMMARY.txt。

SOURCE_DOCUMENT_INSTALL_IDENTITY.json 逐字绑定 README、QUICKSTART、AGENTS、CHANGELOG、
pyproject、__init__、CI，记录独立 editable 安装指向本仓库、version=0.11.0。
临时安装目录中的旧 SHA 字样只是路径 locator，不是候选身份。正式机器 0.10.0 安装未切换。
完整核心 Python 相对 0.10.0 的净非空行增量为 3183；不含 tests/docs/results，不机械压行。

## 收尾与交接

当前 implementation Goal 已完成，状态 READY_FOR_FINAL_CRITIC，详见
`f3c882c/FINAL_IMPLEMENTATION_REPORT.md` 与 `f3c882c/ACCEPTANCE_STATUS.json`。
不新建 Goal，不改变架构或原完成标准，不用后续 results-only 提交替换生产 candidate。
Final Critic 尚未给出最终决定；formal release、tag 和 Marketplace 均未推进，
正式 distribution 仍为 0.10.0。后续评审与正式发布不由本次 live 授权代为完成。
