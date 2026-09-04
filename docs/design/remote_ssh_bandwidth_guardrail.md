# Codex Remote SSH bandwidth guardrail

## Purpose

Bridge Kit manages Codex identities and workflows across local and remote environments. It therefore needs a generic safety rule for Codex Desktop Remote SSH: sustained multi-MB/s traffic may be caused by the remote Codex app-server feature surface rather than project I/O or the SSH/Cloudflare transport itself.

This document is intentionally transport-agnostic. It applies to Remote SSH over direct TCP, Tailscale, Cloudflare Access, jump hosts, or other SSH transports.

## Known upstream failure mode

OpenAI Codex has public reports that match this failure mode:

- `openai/codex#37726`: with Remote SSH and `apps=true`, remote `codex app-server proxy` can sustain roughly 4 MB/s over SSH; disabling `apps` drops the traffic effectively to zero.
- `openai/codex#34901`: `app/list/updated` may deliver the complete merged App Directory (2,402 entries in the report) even when `app/list` is paginated; the example notification was about 3.15 MB.
- `openai/codex#38480`: `app/installed` / `app/list` polling may repeatedly rebuild the `codex_apps` MCP session, causing idle CPU/network churn.
- `openai/codex#41573`: a separate `plugin/list` problem can emit multi-megabyte WebSocket frames and trigger Remote SSH code-1006 reconnects; `remote_plugin=false` reduced the reported response size, but this is a separate mitigation and must not be applied without matching evidence.

`codex app-server proxy` bridges the remote app-server control socket to stdin/stdout over the SSH channel. Consequently, repeated Apps/App Directory payloads appear as SSH/cloudflared/network traffic even when the repository itself is not transferring large files.

## Default safety policy

1. Do not diagnose sustained Remote SSH bandwidth as an SSH/tunnel failure solely because `ssh`, `cloudflared`, Tailscale, or a jump host carries the bytes.
2. Do not repair Codex app-server bandwidth by killing, restarting, disabling, deleting, or recreating server-side production tunnels/services.
3. If the user has declared a production tunnel set immutable, that constraint is absolute until the user explicitly authorizes a server-side change in the current task.
4. Client-side Remote SSH sessions may be disconnected only when the task explicitly permits local connection interruption. Prefer targeting the exact local `ssh`/transport process and Host; do not broadly kill unrelated sessions.
5. Remote feature changes are scoped by remote `$CODEX_HOME`, not by the local laptop/workstation. Resolve the actual remote Codex identity before changing feature state.

## Remote preflight

For a Linux remote used by Codex Desktop Remote SSH, first inspect:

```bash
codex features list
```

When the host exhibits sustained unexplained app-server/SSH traffic and `apps=true`, the current validated workaround is:

```bash
codex features disable apps
```

Then reconnect only the affected client Remote SSH session so a new `codex app-server proxy` observes the feature state.

Do not restart the production SSH/Cloudflare/Tailscale infrastructure to make this take effect.

## When to keep `apps=false`

Until the upstream Remote SSH Apps bandwidth regression is confirmed fixed for the deployed Codex runtime, remote Codex identities used for long-lived Desktop Remote SSH should keep `apps=false` when Apps/connectors are not required on that remote runtime.

This is not a recommendation to disable Apps globally on every local Codex identity. Local Desktop/CLI identities and remote app-server identities may have different operational needs.

After a Codex upgrade, remote runtime reinstall, or `$CODEX_HOME` replacement, re-check the feature state rather than assuming it persisted.

## Verification

A useful post-change A/B is:

1. capture 30 seconds of the client physical NIC and the affected SSH transport;
2. verify `apps=false` on the remote identity;
3. reconnect only the client Remote SSH session;
4. capture another 30 seconds under comparable workload.

Sustained `>1 MB/s` while idle or doing only light metadata work should be treated as an investigation trigger, not accepted as normal Remote SSH overhead.

If traffic remains high with `apps=false`, inspect app-server logs and request types before changing network infrastructure. In particular:

- repeated `app/list`, `app/installed`, or Apps MCP initialization suggests the Apps path is still involved;
- very large `plugin/list` responses plus WebSocket `1006` suggest the separate remote-plugin issue;
- thread hydration/reconnect loops are another independent class and should be diagnosed from app-server/Desktop timestamps rather than by modifying SSH topology.

## Host Policy integration

Bridge Kit Host Policy should preserve the following semantic rule in generated/global AGENTS guidance:

> Remote Codex troubleshooting must distinguish app-server/application traffic from transport failure. Do not mutate production server tunnels or SSH infrastructure as a workaround for Codex Remote SSH bandwidth/reconnect problems. Check the remote Codex identity and feature state first; use client-local disconnects only when needed and explicitly permitted.

Any future implementation that automates remote diagnostics should default to read-only inspection. A command that changes remote feature state, terminates a client session, or mutates infrastructure must remain separately scoped and auditable.
