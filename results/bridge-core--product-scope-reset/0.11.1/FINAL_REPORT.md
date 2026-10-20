# Bridge Kit 0.11.1 已正式发布，Longleaf 已更新

本轮已修复最后确认的通知 cadence 缺陷，并完成历史 TODO、README、QUICKSTART、
CHANGELOG 和版本收口。唯一生产候选和正式 release 均为
`ba9013b9fbbd242e51b09f9d09291f417df17652`；后续 results-only HEAD 不是发行目标。

普通 count/fraction 变化只更新观察；周期从上次逻辑投递计时，默认 60 分钟、非测试
最短 15 分钟。频繁 observation 不再刷邮件，也不会让周期通知持续推迟。阶段、异常、
重大 ETA 变化和 runtime terminal 仍可提前通知。邮件失败不改变 child/lifecycle，
不变成自动重试；底层 Lite terminal 去重不变。

ETA 算法未改：同 stage/total，最近最多 60 分钟 / 12 点，至少三个有效点且跨十分钟，
用近期正向速率中位数估算剩余时间并保留原区间算法。证据不足、stage/none、回退、
stage/total 改变或长 gap 重置 warm-up 时允许 UNKNOWN，不编造完成时间。

机器 Notifier 仍复用原 `~/.ai-bridge/private/notifier.env`（0600），新项目不复制 secret，
进程通知环境变量不覆盖该生产文件；默认 notify=OFF，recipient_override 只影响本次
逻辑投递。自动表达仍为 writing-fidelity + response-clarity，失败 deterministic fallback；
SMTP accepted 不等于收件箱投递。本轮未发送任何真实邮件，也未调用模型或运行 canary。

定向 61 项、本地 Python 3.9 / 3.12 各 496 项（各 8 skips）及同 SHA hosted CI PASS。
CI run 39367527196 的两个环境各 496 项（各 4 skips），具体互补覆盖、原始日志和本地
保护脚本/state 隔离修正见 `VALIDATION.md`。diff/source-document identity PASS，
其他冻结 runtime owner 未改，用户 `.gitignore` 原样保留。

11 份历史 TODO 均核对当前实现与正式证据，原设计正文保留，Bridge-owned 短期 active
TODO 为 0；Program Run 保持有意排除的未来能力。AI_Skills machine update / workflow-core
交付准入属于其他 owner，不重新计入 Bridge 待办。

正式 owner 已通过 non-force fast-forward 将 release 从
`391ff889ad156540727da168fb608c5f37dbbdfc` 推进到上述候选；重新 fetch 与远端 readback
精确匹配，两处正式版本均为 0.11.1。Longleaf 唯一 canonical checkout clean、ancestry-safe
快进并刷新现有 editable package。实际 `ai-bridge where`、import source/version 和
distribution metadata 均验证来自 canonical release checkout 的 0.11.1，而非开发目录。
完整命令回执见 `FORMAL_RELEASE_CLOSURE.json`。

release push 自动触发的同 SHA CI run 39368496066 也已 success，见 `RELEASE_CI.json`；
没有手动重跑已完成的 Gate。

当前 Bridge 短期收尾任务已完成。没有新建 Goal、Planner/Critic 轮次、tag、GitHub Release
或 Marketplace 发布，没有 force/reset/clean/stash，也没有更新其他 consumer。
