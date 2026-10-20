# Bridge Kit 0.11.0 最终验收完成

本次 replacement 已通过正式 Persistent 正常入口的完整通知链。实现和最终验收均已完成，
可以交由用户决定 formal release；本轮没有执行正式发布，也没有移动 release、tag 或 Marketplace。

唯一生产候选仍为 `391ff889ad156540727da168fb608c5f37dbbdfc`。
后续只提交 results 证据，不替换候选，不修改任何 production、tests 或现行产品文档 bytes。
批准包为 `0dfc767e42c12c016fa906bdcfeece051dc49bb3`。

## 机器身份与观察器

首先读取真实 Marketplace 和 plugin inventory。yuukias-ai-skills 的 source 是
`https://github.com/YuukiAS/AI_Skills_Collection.git`，本机缓存位于
`/users/a/e/aereinh/.codex/.tmp/marketplaces/yuukias-ai-skills`，当前 ref 为 release，
HEAD 为 `fd79c4be54fc50bd66d9a51bbc1e681f361f6a77`。

执行一次获授权的正常 Marketplace upgrade；命令 exit 0、errors 为空、upgradedRoots 为空。
首个即时检查通过，但独立复核又观察 inventory 0.4 / manifest 0.5，因此按同一授权，
仅对 writing-style@yuukias-ai-skills 执行一次正常 remove + add。未手改 metadata 或 manifest，
未修改 AI_Skills_Collection 源码、Bridge resolver 或其他 plugin 的安装配置。

之后两个独立 fresh process、canary 立即启动前、两个真实生产 renderer 以及 canary 后
fresh process 均确认 installed/enabled、inventory 0.5、manifest 0.5、
writing-fidelity 与 response-clarity 存在，production resolver PASS。
证据见 replacement/MACHINE_PLUGIN_REPAIR.json、PLUGIN_STABILITY_PREFLIGHTS.json 与 PRELAUNCH_PREFLIGHT.json。
正常 Marketplace 管理入口可参考 [OpenAI 插件文档](https://developers.openai.com/plugins/build/plugins)。

只在新的 disposable harness 修复观察器：process_spawn 的 cwd 显式转为字符串或 null，
其他路径型审计值使用 os.fspath 序列化。真实 Path cwd Popen smoke 已自然 exit 0；
该 smoke 没有模型、SMTP 或 Persistent launch。观察器没有自行调用任何 delivery、renderer 或 sender；
保存的 AST 检查和原始调用链均验证这一点。

## 正式入口、真实 child 与两条通知

新 disposable repo 为 `/tmp/bridge-final-replacement-9ggq9knx/public-canary`，
run key 为 `bridge-replacement-evaluation`，不同于旧 invalid binding。
progress_mode=none、progress_owner=none、source=NONE、Notify=ON、recipient_override=NONE、
cadence=60min；输入仅为 public-safe synthetic runtime facts，private data=NONE。

正式 persistent-run start 返回 NEW_START，并创建一个 full launch_id 命名的 exact tmux session。
launch_id 为 `dce6d00d4e0e781da326781db3327f363b610cf5b74dd776ecb888f9730eb347`。
supervisor PID=510207，primary child PID=510208；child 的实际父 PID 与 supervisor 一致。
child 从 02:32:26 UTC 起运行约 5.004821 秒后自然退出，supervisor 的 child.wait() 记录真实 exit_code=0。
最终 status 为 TERMINAL、progress 为 UNKNOWN；exact tmux session 已自然消失，没有 relaunch 或 takeover。
通知链在 02:33:15 UTC 结束，没有进入 60 秒 progress observation，也没有第三个事件。

runtime_start 与 runtime_terminal 都由该正式 supervisor 的 _persistent_notification 产生，
经共享 machine Notifier、正式 one-shot renderer 和 Gmail SMTP 完成。
每个事件各一个独立 helper、一个模型 invocation、一个 thread/turn、一次 SMTP attempt。
两者均为 NORMAL_WRITING_STYLE，writing-fidelity + response-clarity 显式调用、fidelity PASS、
无 fallback、模型 retry=0、SMTP automatic retry=0，回执均为 SMTP_ACCEPTED。

实际 start 正文：

> 持久运行的主子进程已启动，这只说明进程已启动，不代表任务已完成。项目 public-canary 的任务及运行标识均为 bridge-replacement-evaluation，当前状态为 RUNNING。请使用 persistent-run status 继续观察同一次启动。

实际 terminal 正文：

> 持久运行的主子进程已以退出码 0 退出，但不能据此认定 Goal 已完成。public-canary 项目任务 bridge-replacement-evaluation 的状态为 EXITED_0；下一步评估原始 Goal 的正向完成证据。

正文没有堆 consumer、fact_class、decision_authority、runtime_id、source_event_id 或 schema，
没有无意义的 UNKNOWN ETA，没有把 exit 0 升级为 Goal PASS、READY 或目标完成。
SMTP_ACCEPTED 仅证明服务器接受，不声称 inbox delivered。

## 同一候选的最终验收与边界

C1–C4 冻结 owner 未改，按 v6 保留此前正常入口证据，并由本候选的全量回归和 CI 证明不变；
不重跑长 canary。C5 保留已有机器/四 consumer 回归并增加本次完整正常入口正例。
C6 的路线、投影、保真、单 turn 与 fallback 确定性回归已通过，本次 live 正例补齐最终完整链。

50 项 targeted、Python 3.9/3.12 各 490 项 full tests 与 source-document identity 保持 PASS。
[Hosted CI run 39353877948](https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit/actions/runs/39353877948)
已只读回查为 completed/success，headSha 正是唯一生产候选；没有触发新 Gate 或重跑 CI。

完整原始 trace、两份模型 JSONL/returncode、实际 prompt、render result、MIME、request、
claim/attempt/receipt、child marker、supervisor/binding lineage、harness 与离线核对结果，
均保存在 replacement/FINAL_NORMAL_ENTRY_RAW_EVIDENCE.json；摘要见 OBSERVATION_SUMMARY.json。
本轮实际预算是一个 replacement canary、两次模型、两次 Gmail SMTP attempt，零重试、零 send-test。
旧 invalid attempt 保留在 INVALID_ATTEMPT_REPORT.md 及原始证据文件；旧 state 未删除、未伪造 terminal，
它没有消耗模型/Gmail 预算，也没有被倒签为成功。

machine Notifier 仍为原机文件、VALID/0600，config digest 前后一致，
provider/account/FROM/default recipient 没有改变；没有复制或记录 App Password。
用户 .gitignore 仍未修改、未暂存，SHA-256 为
`6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7`。

C1–C6 与最终正常入口链均完成，implementation + final evaluation complete，
READY_FOR_RELEASE_DECISION=YES。正式 distribution closure 尚未执行，
refs/heads/release 保持 `9db19b0409816c22042a246b35a33e1d34fedd0a`；没有 tag 或 Marketplace 发布。

本报告经写作保真与中文审校，区分产品验收完成、synthetic child exit 和正式发布决定，不互相替代。
