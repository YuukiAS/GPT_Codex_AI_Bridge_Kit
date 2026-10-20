# Bridge Kit 0.11.0 最终正常入口验收记录

实现与非 live 验证保持通过，但最终验收未完成，不能交付正式发布决定。
本轮唯一 canary 因执行方编写的旁路记录器错误，在 primary child 启动前退出。
该错误不构成已证实的 Bridge 产品缺陷；没有修改生产源码，也没有消耗模型或 Gmail。
另一次收尾只读检查发现，writing-style inventory 又回到 0.4，机器身份修复未稳定。

## 不变的候选与已有验证

唯一 production candidate：`391ff889ad156540727da168fb608c5f37dbbdfc`。
分支后续只新增 results 证据，不是新候选。
v6 package：`0dfc767e42c12c016fa906bdcfeece051dc49bb3`。

50 项定向测试、Python 3.9/3.12 各 490 项全量、source-document identity
与同 SHA hosted CI 均保持原 PASS；本轮未重跑这些 Gate 或 C1–C4 长 canary。
CI run：`39353877948`，head SHA 为上述候选。
冻结 owner 未改变，C1–C5 已有能力验证保留；C6 非 live 通过。
最终 C5/C6 Persistent 通知链没有通过，历史 direct delivery 不替代本次验收。

## 机器 plugin refresh 的真实前后观测

只执行一次用户指定的 `codex plugin add writing-style@yuukias-ai-skills --json`。
命令 exit 0，返回 version 0.5；立即真实验证唯一 installed/enabled、inventory 0.5、
manifest 0.5、两个 skill 存在，production resolver PASS。
按当前用户的条件式决定，该时点进入 PROCEED_TO_FINAL_EVALUATION。
原始命令结果及立即验证见 `PLUGIN_REFRESH.json`。

收尾时真实只读检查再次观察 inventory 0.4、manifest 0.5，production resolver 返回
`WRITING_STYLE_PLUGIN_VERSION_MISMATCH`，两个 skill 文件仍存在。
宿主机非 sandbox 检查也确认同一结果，见 `PLUGIN_FINAL_PREFLIGHT.json`。
没有重复 refresh、改用其他安装机制、手改 manifest、修改 AI_Skills 或放宽 resolver。
因此不能用先前即时 PASS 声称环境已稳定修复。

## 唯一一次正式 canary

使用 disposable Git repo，冻结 progress none、owner none、source NONE、Notify ON、
recipient override NONE、60 分钟 cadence 与 5 秒自然 exit 0 的合成 child。
正式 CLI start 返回 NEW_START，生产命令创建 full launch_id 命名的 exact tmux session，
启动正常 `_supervise`；没有直接调用任何通知、renderer 或 SMTP 函数。
task-local `TMUX_TMPDIR` 只隔离 socket，便于继承旁路观察环境，不接管既有会话。

launch_id：`23ddf3d1a9736ae4c9602ac0f114eae1efe2e0d4ed106529642eca4178ddd78b`。
supervisor Python startup PID 为 450890；仅记录到启动，没有成功 fork primary child。
start、原始 trace、fixture 和未修改的观察器完整内容保存在
`FINAL_NORMAL_ENTRY_RAW_EVIDENCE.json`。

实际问题属于验收观察器：其 audit callback 把 child Popen 的 `cwd=Path(...)`
未经转换交给 `json.dumps`，触发 `TypeError: Object of type PosixPath is not JSON serializable`。
生产使用 Path cwd 合法；Python 3.12 POSIX audit 在 fork 前暴露原始 Path。
纯离线调用同一 audit event 重现该错误，没有调用实际 Popen、supervisor、模型或 SMTP。
重现 traceback 见 `OBSERVER_DIAGNOSIS.json`。
原 tmux pane stderr 未保存，不把诊断重现冒充现场原始 traceback。

真实宿主机 status 确认 exact session 已消失，binding 留在 START_REQUESTED，
返回 UNKNOWN/UNAVAILABLE；progress 为 UNKNOWN。见 `FINAL_NORMAL_ENTRY_STATUS.json`。
没有 child-start/exit marker、child_pid、真实 exit_code 或任何该 repo 的 Notifier claim。
没有把 primary child 的预期 exit 0 当作真实 exit；supervisor 实际 exit code 未捕获。

## 预算、停止与发布边界

实际消耗：1 次 canary start、0 次真实模型、0 次 SMTP attempt、0 封邮件、0 次 send-test。
runtime_start/runtime_terminal 均未到达，没有第三个事件、fallback 邮件或自动重试。
只有一个 canary 授权，失败后未修补观察器重跑、relaunch、takeover 或直接补发通知。
验收失败不冒充 C6 PASS；当前 final evaluation incomplete、release decision ready=false。

machine Notifier 仍 VALID/0600，config digest 与本轮前相同；账号、FROM、默认收件人不变。
没有保存密码、凭据或 auth 配置内容。用户 `.gitignore` 的 SHA-256 仍为
`6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7`，未暂存。
remote release 仍为 `9db19b0409816c22042a246b35a33e1d34fedd0a`；没有移动 release/tag/Marketplace。

报告按写作保真与中文审校保留原始失败、未知 exit 和授权边界，不把实现完成升级为最终验收完成。
