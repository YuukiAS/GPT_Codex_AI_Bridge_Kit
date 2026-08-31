# Host Policy: unattended local plugin repair / replay

Status: frozen planner design for a bounded Host Policy improvement.

## Problem

A real `AI_Skills_Collection` Reviewed Handoff task exposed an infrastructure failure before the plugin itself could be tested. The Executor needed to launch a fresh local Codex runtime so an installed production plugin could process a user-authorized private research artifact. The outer Codex approval reviewer blocked that nested runtime because the command would pass private content to another model runtime and write outside the initial workspace root.

This is not a plugin-quality failure. It is a machine-level Host Policy / production-replay authorization gap.

The user explicitly authorizes trusted plugin repair workflows on their own machines to process explicitly selected local/private artifacts with a fresh OpenAI Codex production runtime without repeated approval, provided the replay stays inside a bounded local sandbox and does not publish private content.

## Product boundary

This capability belongs to `GPT_Codex_AI_Bridge_Kit`, not to an individual consumer repository.

- **Host Policy** is the machine-wide authorization source of truth. One `CODEX_HOME` installation applies to all repositories using that Codex identity.
- **Bridge Kit** owns the bounded replay launcher that makes the authorization safe enough to pre-approve.
- **Lite / Reviewed Handoff / other repo workflows** only learn to call the bounded launcher when they need a fresh production plugin runtime. They do not maintain their own permission allowlists.

The intended behavior is:

```text
raw nested `codex exec`                         -> normal Host Policy / approval review
`ai-bridge plugin-replay ...`                  -> globally pre-authorized bounded path
branch / remote / destructive / publication    -> unchanged approval behavior
```

## Existing behavior

Current Host Policy deliberately keeps:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
approvals_reviewer = "auto_review"
```

and only pre-authorizes a small set of ordinary Git commands in `ai-bridge-global.rules`.

Do not change those global defaults just to make plugin replay unattended.

## Rejected shortcuts

Do not solve this by:

- setting global `approval_policy = "never"`;
- setting global `sandbox_mode = "danger-full-access"`;
- broadly allow-listing every `codex exec` invocation;
- broadly allow-listing `bash`, `sh`, `python`, or another general-purpose runtime;
- adding one-off path rules for a single PDF, project, task number, or plugin;
- granting a nested Codex the whole source repository merely because one private artifact is needed;
- weakening destructive Git / branch / remote protections.

A raw `codex exec` prefix is too broad because prefix policy cannot validate all later arguments, paths and configuration overrides. The safe unit to pre-authorize is a Bridge-owned wrapper whose own argument contract is narrow and testable.

## Frozen implementation shape

Implement one first-class Bridge Kit command:

```text
ai-bridge plugin-replay ...
```

The exact option names may follow existing CLI conventions, but the command itself is the stable product boundary.

### 1. Machine-local isolated replay workspace

Each replay creates a fresh machine-local run directory under:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/<run-id>/
```

with a structure such as:

```text
workspace/       # child Codex cwd
inputs/          # copies of explicitly selected source files
outputs/         # replay outputs
run.json         # non-secret run metadata / status
```

Only explicitly listed input files are copied. Do not recursively ingest a parent directory.
“Explicit input” does not mean an arbitrary absolute path. The replay target
must resolve through `git -C <target> rev-parse --show-toplevel` to a canonical
Git repository root. By default, every `--input` file must resolve inside that
target repository root. The only external-file escape hatch is the fixed
machine-local trusted inbox:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/inbox/
```

The caller cannot choose another input root. Path checks must use resolved real
paths, so `..`, relative-path tricks and symlink escapes such as
`repo/link -> ~/.ssh` are rejected. A task/instruction file may resolve inside
the target Git repository, the caller's current Git repository, or the trusted
inbox; it may not be an arbitrary private file. If the caller's current working
directory is not inside a Git repository, task files are limited to the target
repository or trusted inbox.

The child Codex working directory must be this isolated replay workspace, **not the consumer repository**. Do not rely on `--add-dir` as a write fence for the target repository. If additional context is needed, it must be supplied as another explicit input file or a deliberately copied bounded context artifact.

This keeps plugin replay independent of arbitrary repo write access and avoids making a private source directory writable merely to test a plugin.

### 2. Test the installed production plugin, not source-tree imitation

The child runtime must use the current Codex identity / installed plugin
environment from the current process `CODEX_HOME` resolution (`$CODEX_HOME`,
otherwise `~/.codex`). `CODEX_HOME` authorization is per identity:
`plugin-replay` must not let a caller that is approved under one Host Policy
select another Codex identity. The replay helper must not copy `SKILL.md` text
into the prompt and pretend that this is equivalent to running the installed
plugin.

Require the caller to identify the intended plugin (for example `--plugin <name>`). If the current Codex CLI exposes a reliable installed-plugin inspection command, verify the plugin is actually installed; otherwise record the requested plugin name and fail clearly if production invocation cannot find it.

### 3. Child Codex invocation is fixed by the wrapper

The wrapper constructs the child command itself. The caller cannot append arbitrary Codex CLI flags.

Use current CLI-supported argument ordering. In particular, approval policy is a top-level Codex option in current CLI builds, while sandbox / cwd options may be exec-specific. The implementation must inspect/test against the installed CLI rather than assume an invalid argument order.

The child must have these semantic properties:

- approval policy: `never` inside the already validated replay;
- sandbox: bounded, normally `workspace-write`;
- cwd: isolated replay workspace;
- no `danger-full-access`;
- no arbitrary `-c` / config override passthrough from the caller;
- no arbitrary additional writable directory passthrough;
- ephemeral/non-persistent session when supported;
- network disabled by default for local artifact replay unless a future separately reviewed contract introduces an explicitly bounded network mode.

Before running the real replay, the helper must verify that the child Codex
runtime cannot read a known non-sensitive file outside the replay authorization
root. If the current Codex CLI / platform cannot enforce that restricted read
boundary, the helper must fail closed with
`READ_ISOLATION_NOT_ENFORCEABLE` rather than processing private replay inputs.

The helper may use `--skip-git-repo-check` because the isolated replay workspace is not required to be a Git repository.

### 4. Output stays machine-local

Private source and full replay output remain under the machine-local replay run by default.

The helper itself must not:

- `git add` / commit / push replay source or output;
- alter branch topology, remotes, upstreams, tags or release state;
- copy outputs into a public repository automatically;
- print private document contents in dry-run/status output.

Consumer workflows can reference the machine-local output path in their RESULT without committing the private text.

### 5. Host Policy pre-authorizes only this narrow entry point

`ai-bridge host install` must install an execpolicy rule that allows the bounded replay command, not raw `codex exec`.

Conceptually:

```text
ai-bridge plugin-replay ... -> allow
codex exec ...              -> unchanged normal policy
```

Because basename allow rules can be unsafe if a different executable shadows the expected command, Host Policy should pin the trusted `ai-bridge` executable resolution when the current execpolicy supports `host_executable(...)` or an equivalent exact executable constraint. `host validate` must report the resolved trusted executable and fail on drift where practical.

Use execpolicy `match` / `not_match` examples where supported so the rule validates its intended prefix at load/test time.

### 6. Workflow integration is advisory, not a second permission layer

Update generic Bridge Kit Lite / Reviewed Handoff Executor guidance so that when a frozen task genuinely requires a fresh production plugin runtime, it uses `ai-bridge plugin-replay` rather than constructing a raw nested `codex exec` command.

Do not force ordinary implementation tasks through plugin replay. Do not add a new state machine, role, schema family or task type.

## What this authorization does not cover

The global replay authorization does not authorize:

- arbitrary private-file discovery;
- recursive harvesting of user directories;
- secrets ingestion;
- arbitrary external upload;
- unrestricted network access;
- destructive filesystem operations outside the replay workspace;
- branch creation/switching, force push, remote mutation or release publication;
- product/scientific scope expansion;
- replacing Planner / Reviewer authority.

Those actions remain under their existing policy and may still require approval or a separate explicit workflow contract.

## Acceptance

The change is not complete unless all of these are demonstrated:

1. `ai-bridge host install` keeps global `approval_policy = "on-request"`, `sandbox_mode = "workspace-write"`, and `approvals_reviewer = "auto_review"`.
2. `ai-bridge host install` installs the narrow replay pre-authorization for the trusted Bridge executable.
3. `ai-bridge host validate` verifies `ai-bridge plugin-replay ... => allow` and confirms raw `codex exec` did not gain a broad allow.
4. Force push, branch creation/switching, remote mutation, `reset --hard`, `git clean` and existing dangerous cases retain their current approval behavior.
5. The replay helper accepts only explicit input files under the target Git repository or fixed trusted inbox, rejects resolved symlink escapes, and does not recursively stage neighboring files.
6. The child cwd is the isolated machine-local replay workspace; the helper does not expose the whole target repository as a writable child workspace.
7. The child command fixes bounded sandbox + no interactive approval and rejects arbitrary Codex flag passthrough.
8. A dry-run shows target/plugin/input basenames, replay workspace/output path, resolved Codex executable and exact child argv without printing private contents.
9. A real generic local smoke launches a fresh Codex runtime against a small temporary private-like text input and proves the child cannot read a specified neighboring secret outside the replay authorization root before any real private replay proceeds.
10. The smoke is generic: no `writing-style`, CARE, M&Ms, PDF title, task `044` or project-specific hard-code in implementation/tests.
11. The first real consumer replay after the generic smoke is `AI_Skills_Collection` task `044_writing_style_deep_research_chinese_replay`; its private PDF and rewrite remain local.

## Why this is preferred over alternatives

- **Global raw `codex exec` allow** removes too much review because later arguments and paths are not bounded by the prefix alone.
- **Repo-local permission exceptions** duplicate machine policy and would have to be maintained separately for every plugin/repository.
- **Changing global approval to `never`** makes unapproved commands fail rather than providing a selective trusted path and weakens normal interactive review semantics.
- **Giving the child the whole repository or source directory** is unnecessary for a production plugin replay and creates a larger write surface.
- **A Bridge-owned isolated launcher + one Host Policy allow** gives one machine-wide reusable path while preserving the existing review boundary everywhere else.
