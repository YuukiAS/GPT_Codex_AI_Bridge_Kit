# Live Gate Handoff

Task: `bridge-core--execution-reliability-closure`

Stage A result: `AWAITING_LIVE_GATE_AUTHORIZATION`

`FINAL_SOURCE_CANDIDATE`: `9db19b0409816c22042a246b35a33e1d34fedd0a`

`FINAL_VERSION`: `0.10.0`

Stage B is not authorized by the Stage A kickoff. The same Goal must resume only after the user sends an explicit matching Stage B authorization for the exact candidate above.

## Frozen Stage B Authorization Request

> 我批准对 Bridge 0.10.0 exact candidate `9db19b0409816c22042a246b35a33e1d34fedd0a` 执行已冻结的 Stage B live
> gates。授权在
> `/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a`
> materialize exact candidate source、创建 isolated venv，并仅以
> `PIP_NO_INDEX=1 / --no-index --no-deps --no-build-isolation` 从该本地 source 安装
> candidate；不授权任何 PyPI/index/build-dependency network acquisition，本地 build
> tooling 不满足则直接停止。授权在 Stage B 进程中把 candidate venv `bin` 放到
> `PATH` 首位，验证 `command -v ai-bridge`、`ai-bridge where`、import source/
> version 均绑定 exact candidate，并让
> `CODEX_HOME=/users/a/e/aereinh/.codex` 的临时 candidate Machine Policy
> `host_executable` pin 到该 exact candidate；修改前完整备份 managed files。
>
> 同时授权在上述 candidate PATH/Machine Policy 下，从
> `/users/a/e/aereinh/.ai-bridge/er-g8/AI_Skills_Collection` 使用已冻结的
> `ER_G8_CONSUMER_PROMPT.txt`，以前台方式启动一次
> `codex exec --json --cd /users/a/e/aereinh/.ai-bridge/er-g8/AI_Skills_Collection -`
> fresh normal Codex child，并保存 thread/session、完整 JSONL/stderr、exit code。
> Codex CLI 必须仍是 `0.142.0`，不授权升级/替换。launcher 本身的审批或拒绝不计作
> ER-G8 genuine refusal；若 launcher 无法合法启动，必须在 optional probe 前停止。
>
> child 内只允许一次冻结的 optional
> `tmux new-session -d -s ai-bridge-er-g8-refusal-probe 'sleep 2'` probe，以及
> `YuukiAS/AI_Skills_Collection main` 唯一
> `results/bridge-core--execution-reliability-closure-er-g8/CONSUMER_RUN.json`
> 结果提交、normal bounded existing-branch publication 与 remote SHA 验证。
> 不授权其他 AI_Skills 文件、branch topology、raw/force/delete/remap、provider/
> secret/cost/resource/production effect。
>
> fresh Codex child 必须先结束并记录 exit evidence，之后才允许恢复并
> hash-verify 预先备份的 CODEX_HOME managed files。除此之外不授权覆盖现有生产
> Bridge editable/package runtime、清理历史 metadata、Codex CLI upgrade、其他 live
> side effect 或 formal release/distribution。

## Stage A Stop Record

```text
RESULT=AWAITING_LIVE_GATE_AUTHORIZATION
FINAL_SOURCE_CANDIDATE=9db19b0409816c22042a246b35a33e1d34fedd0a
GOAL_BLOCKED=YES
GOAL_ACHIEVED=NO
COMPLETE=NO
READY_FOR_PRE_FINAL_CRITIC=NO
DEPENDENT_EXECUTION_BLOCKED=YES
```
