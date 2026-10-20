# v6 窄修完成，交回同一 Critic

本轮批准的源码、直接测试和当前文档同步已完成。新候选的定向回归、两版本本地全量、
hosted CI、diff boundary 和源码/文档身份核对均通过。最终 Persistent 正常通知链只冻结
合同，没有执行；现在停止，由同一独立 Critic 决定 `PROCEED_TO_FINAL_EVALUATION`
或 `REVISE`。这不是新候选的 live PASS，也不是正式发布。

## Exact identity 与窄修范围

- Approved package：`0dfc767e42c12c016fa906bdcfeece051dc49bb3`，四份 v6 文件均从该
  commit 的 blob 读取；不是按旧 v4/v5 全量计划重做实现。
- FINAL_CANDIDATE_SHA：`0aef27850a91e415305458aef1d1d60506841d9b`。
- Implementation commits：`f5ffe71f93288036bf9cb30c428475ef3b0a534e` 与
  `0aef27850a91e415305458aef1d1d60506841d9b`，后者包含前者的实际 production 修复。
- Branch：`work/bridge-core--product-scope-reset`，通过 bounded 当前分支入口普通发布。
- Production baseline：`f3c882c5302a1889cac62526e8f025ada0f4d1a5`；后续证据提交不替换
  被测生产候选。相对 approved package 只有六个文件变化，其中唯一生产文件为
  `ai_bridge_kit/clear_writing.py`。

正式路线为 installed/enabled `writing-style@yuukias-ai-skills` 的
`writing-fidelity + response-clarity`，prompt 显式调用两个 `$skill-name`。
reader-facing projection 不传六个内部 routing/audit 字段，不要求显示它们的数字或 ID；
start/terminal 的无意义 UNKNOWN ETA 可省略。完整 request 不修改，机械检查仍从
原始 fact_class/authority 限制 runtime 结论强度，包括 status=finished 的终态。
真实进度、版本、数字和仍有意义的不确定性继续保真；one turn、retry=0、90/120 秒、
fallback 与 transport 语义均保持。

README、AGENTS、CHANGELOG 原有旧 route 已同步；QUICKSTART 没有旧 route，保持逐字不变。
文档终审遵循 writing-fidelity/chinese-prose，仅保护事实、候选身份并同步相关说明，
没有借机重写其他能力。AI_Skills、Notifier/Persistent、Host、Review、Control、Overleaf
等冻结 owner 均未修改；另外 19 个 production 文件及 templates/codex/CI tree 与
f3c882c 完全一致。用户 `.gitignore` 未修改或提交，原 SHA-256 保持不变。

## 同 candidate 的非 live 证据

| 检查 | 结果 | Locator |
| --- | --- | --- |
| 新 route、missing response-clarity、显式 prompt、投影、raw runtime 禁止升级、数字/不确定性、one turn、fallback、90/120 秒与四 consumer 隔离 | 50 项 PASS | TARGETED_TESTS.txt |
| Python 3.12 全量 | 490 项，162.425 秒，exit 0，8 skipped | LOCAL_PY312_TESTS.txt |
| Python 3.9 全量 | 490 项，157.756 秒，exit 0，8 skipped | LOCAL_PY39_TESTS.txt |
| hosted CI | run 39352413246，exact candidate，两组各 490 项 PASS，4 skipped | HOSTED_CI.json |
| DNS/connect/TLS 三个受控 hang | 1.5 秒 fixture deadline 内 helper 被 reaped，DELIVERY_UNKNOWN，primary 继续，模型/SMTP 为 0 | TRANSPORT_DEADLINE.json |
| 冻结 owner 与源码/文档/版本/Bridge editable 安装身份 | PASS；writing-style 安装预检另列诊断 | SOURCE_DOCUMENT_IDENTITY.json |

本地完整命令分别为候选 editable 环境 Python 3.12 与 `/usr/bin/python3.9` 执行
`-m unittest discover -v`，仅使用独立 temporary `AI_BRIDGE_STATE_HOME`。测试的 Python
子进程继承 `nonlive_test_guard.py` 对应的审计保护，拒绝真实 canonical CLI exec 和 SMTP；
没有切换 HOME/CODEX_HOME 或用生产 transport 环境变量注入配置。
该保护是测试 harness，不是新增 production 路径，也不声称通用文件系统/网络隔离。

本地缺 age 的 8 项跳过在 CI 实际执行；CI 缺 Codex CLI 的 4 项在本地实际执行。
CI head SHA、两组 checkout SHA、真实测试结果与 terminal success 一致，没有复用旧 CI。
C1–C4 按 v6 合同以 owner bytes 不变及全量回归/CI 证明 should-not-change，未重跑长 canary。
旧 f3c882c direct deliver live 证据仍是历史组件证据，未升级为新 SHA 的完整正常入口链。

## 发现与处理

初次定向检查的两个旧 Notifier scanner 测试只替换 sender，未隔离已安装模型路线。
保护在 subprocess 真正启动前拦截了两个请求，实际模型/SMTP 为 0。仅在
`tests/test_notifier.py` 的这两个方法显式注入零模型 fallback，保留扫描/transport 断言，
不修改 `notifier.py`。新 candidate 的 50 项和两组全量均通过，最终验证期间保护计数未增加。
原始失败保留在 EARLY_NONLIVE_GUARD_DIAGNOSTIC.txt，不当作最终候选 PASS。

另有机器安装环境诊断：只读 plugin inventory 后来回报 version=0.4，而其实际 manifest
为 0.5，生产 resolver 正确返回 WRITING_STYLE_PLUGIN_VERSION_MISMATCH。测试 fixture 的
正式 0.5 路线和缺失/不一致拒绝均通过；这不等于当前机器已具备 live installed identity。
不猜测漂移原因，不修改 AI_Skills/插件安装，不放宽 parser，不消费模型 budget。
该项与源码/文档身份检查分开记录，交同一 Critic 判断；后续任何获准 live 前必须先由
对应 owner 协调并重新验证安装身份，不能用 fixture 或旧解析成功替代。

## 冻结但未执行的最终评估

完整合同在 FINAL_EVALUATION_PLAN.json：一个 disposable Git repo，正式
`persistent-run start`，progress/owner=none、source=NONE、Notify=ON、recipient_override=NONE、
cadence=60min，真实 primary child 约 5 秒后自然 exit 0，短于 60 秒 observation。
预期只有 runtime_start 与 runtime_terminal 两个 automatic logical delivery。

后续最大预算维持一个 canary、最多两次模型、最多两次 Gmail SMTP attempt、零重试、
无额外 send-test、原 provider/account/FROM/default recipient、公有安全合成事实。
passive trace 只能观察正式生产链，不能自己调用 deliver_notification/render_once/
send_auto_email 或注入第三个事件。本轮完全没有消费这些预算。

现在停止。Critic 决定之后仍须用户明确授权，不能凭本报告、冻结预算或旧 live 授权执行。
`release` 仍为 `9db19b0409816c22042a246b35a33e1d34fedd0a`（0.10.0），tag/Marketplace 未推进。
