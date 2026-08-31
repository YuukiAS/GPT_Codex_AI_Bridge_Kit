# Host Policy: unattended local plugin repair / replay

Status: planner design note for a bounded Host Policy improvement.

## Problem

A real `AI_Skills_Collection` Reviewed Handoff task exposed an infrastructure failure before the plugin itself could be tested. The Executor needed to launch a fresh local `codex exec` runtime so the installed production plugin could process a user-authorized private research artifact and write the replay output to a local private directory. The outer Codex approval reviewer blocked that nested runtime because the command would pass private content to another Codex/model runtime and write outside the initial workspace root.

This is not a plugin-quality failure. It is a Host Policy / production-replay authorization gap.

The user explicitly authorizes trusted plugin repair workflows on their own machines to do the following without repeated interactive approval:

- process explicitly selected local/private artifacts with an OpenAI Codex production runtime;
- launch a fresh nested Codex runtime when that is necessary to test an installed plugin through its real production entry point;
- write replay outputs only to an explicitly selected local/private replay directory;
- keep the private source and rewritten output out of public Git repositories unless the user separately asks to publish them.

The goal is that plugin repair / replay can run unattended once the workflow and input are already authorized. The user should not need to approve the same safe local production-replay action every time a plugin is refined.

## Existing behavior

Current Host Policy deliberately keeps:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
approvals_reviewer = "auto_review"
```

and only pre-authorizes a small set of normal Git commands in `ai-bridge-global.rules`.

Reviewed Handoff itself already launches its Executor with `codex exec`, but a plugin-repair Executor may need a second fresh Codex runtime to exercise an installed plugin as a normal user would. A raw nested `codex exec` currently falls back to the normal approval reviewer and can therefore block an otherwise fully authorized unattended workflow.

## Rejected shortcuts

Do not solve this by:

- setting global `approval_policy = "never"`;
- setting global `sandbox_mode = "danger-full-access"`;
- broadly allow-listing every `codex exec` invocation;
- broadly allow-listing `bash`, `sh`, `python`, or another general-purpose shell/runtime;
- adding one-off path rules for a single PDF, project, task number, or plugin;
- weakening destructive Git / branch / remote protections.

These approaches either remain fail-closed, remove too much sandboxing, or turn one legitimate replay need into a machine-wide arbitrary execution permission.

## Frozen product decision

Add one bounded Bridge Kit capability for **local production plugin replay** and pre-authorize that capability in Host Policy.

The preferred shape is a Bridge-owned command (exact CLI naming may follow the existing router conventions) that is narrower than raw `codex exec`. Its job is only to launch a fresh Codex runtime for a user-authorized plugin replay with enforceable local boundaries.

The implementation must guarantee all of the following:

1. The child runtime is always launched with a bounded sandbox, not `danger-full-access`.
2. Interactive approval inside the child runtime is disabled only because the wrapper has already validated the replay contract.
3. The target repository is explicit.
4. Input artifacts are explicit. Do not recursively harvest unrelated private files merely because they share a parent directory.
5. Replay output is local and explicit. Private source/output must not be committed or pushed by the replay helper.
6. The helper must not change Git branch topology, remotes, upstreams, tags, or publication targets.
7. The helper must not become an arbitrary shell launcher or a generic way to bypass Host Policy.
8. Direct raw `codex exec` remains governed by the normal Host Policy unless separately authorized.
9. Host Policy should pre-authorize the narrow Bridge-owned replay command so an outer Codex Executor can invoke it without manual or automatic approval review.
10. Existing dangerous-operation prompts and Host Policy behavior must remain unchanged.

A machine-local staging/output area under `AI_BRIDGE_STATE_HOME` / `~/.ai-bridge` is acceptable and may be preferable if it gives a cleaner boundary than granting a nested runtime broad access to an arbitrary source directory. The implementation may copy only the explicitly selected source files into that staging area before launching the child runtime.

## Reviewed Handoff integration

Plugin-repair tasks should use this bounded replay path whenever they need a fresh production Codex/plugin runtime. They should not improvise a raw nested `codex exec` command and then block on approval.

This does not change Planner / Executor / Reviewer authority. The helper only removes repeated host-level approval friction for an already-authorized local replay. It does not authorize scope expansion, destructive actions, external publication, scientific substitutions, or Planner decisions.

## Acceptance

The change is not complete unless all of these are demonstrated:

- `ai-bridge host install` installs the new narrow pre-authorization without switching the machine to `approval_policy = "never"` or `danger-full-access`.
- `ai-bridge host validate` can verify that the bounded replay command is allowed.
- A real local replay can launch a fresh Codex runtime, read one explicitly selected private artifact, and write a local replay output without an approval prompt.
- The same mechanism is generic across plugin repair workflows; it contains no CARE, M&Ms, writing-style, PDF title, task `044`, or project-specific hard-code.
- Direct raw `codex exec` is not globally pre-authorized by the new rule.
- Force push, branch creation/switching, remote mutation, `reset --hard`, `git clean`, and other existing dangerous cases still require approval.
- Tests cover rule installation/validation and the replay helper's path/sandbox contract.
- A dry-run or equivalent prints the exact child runtime command and local paths so the user can audit the boundary.

## Real replay that motivated this change

The first replay after implementation is `AI_Skills_Collection` task `044_writing_style_deep_research_chinese_replay`. Its private research PDF and rewritten text remain local. That task is a replay of a known failure case, not an unseen generalization test.
