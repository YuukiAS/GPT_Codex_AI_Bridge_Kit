# Bridge Kit 0.11.0 修复候选与 Gate 记录

两个 Bridge 实现误判已修复。保存的 C6 trace 在修复后的正式 renderer 中离线回放，
返回 NORMAL_WRITING_STYLE；本地全量回归、C1–C5 与 C6 非 live 验证通过。
新的 hosted CI 尚未全部完成，因此当前还不能说所有 Gate 已通过。
本轮没有真实模型调用或 Gmail 发送；旧 live run 不是新候选的 C6 live PASS。

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
| C6 live | 此新候选没有执行；本轮明确禁止第二次模型和第二封 Gmail | NOT_RUN |

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
返回字段 model_invocations=1 表示一次被录制 response 替代的逻辑步骤，实际新增模型=0、
SMTP=0；C6_OFFLINE_REPLAY.json 的外层字段明确记录该区别。

保存源来自 `c32b910/C6_LIVE_RAW_EVIDENCE.json` 和 `C6_MODEL_JSONL.json`，
stdout SHA-256 为 `542bbbe9b012181b10ce70553f6043a644ca3d0e0512a324ad0c4ba144c99c98`。
旧现场确实发生一次模型、一封 fallback 邮件，SMTP accepted；这些事实及原始记录不改写。
旧 Bridge 误报已由本轮纠正，但旧 run 不被倒签成新 SHA 的最终 live PASS。

## 全量回归、CI、安装与文档

本地 Python 3.12 全量 486 项，120.637 秒、exit 0，8 项 age 可选测试因环境依赖缺失跳过；
Python 3.9 同样 486 项、123.403 秒、exit 0，跳过相同 8 项。
30 项针对性测试 25.727 秒全部通过，真实 Codex execpolicy 检查未跳过。
初次普通 sandbox 跑全量时有 8 个默认机器状态目录只读错误；按正式显式
AI_BRIDGE_STATE_HOME 测试隔离后重跑通过，没有修改 HOME、CODEX_HOME 或生产 transport config。
准备阶段的拒绝与修正记录在 REPAIR_SCOPE_AND_AUTHORITY.json。

Hosted CI：
[run 39281651220](https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/39281651220)，
headSha=`f3c882c5302a1889cac62526e8f025ada0f4d1a5`。直接 job API 已确认 Python 3.9
completed/success；Python 3.x 仍 queued、runner 未分配。run 汇总暂未完成，无 failure
annotation；等待全部真实结果，不引用旧 c32b910 的绿色 run。

SOURCE_DOCUMENT_INSTALL_IDENTITY.json 逐字绑定 README、QUICKSTART、AGENTS、CHANGELOG、
pyproject、__init__、CI，记录独立 editable 安装指向本仓库、version=0.11.0。
临时安装目录中的旧 SHA 字样只是路径 locator，不是候选身份。正式机器 0.10.0 安装未切换。
完整核心 Python 相对 0.10.0 的净非空行增量为 3183；不含 tests/docs/results，不机械压行。

## 剩余边界

当前还需 hosted CI 完成，以及另行授权的新候选 C6 live rerun。
不把本轮离线 replay 或旧邮件 receipt 说成新候选的 live PASS。
没有新建 Goal，没有改变原 Goal 的最终完成标准；当前尚不能报告整个 Goal 完成。
