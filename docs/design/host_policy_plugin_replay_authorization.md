# Host Policy: unattended local plugin repair / replay

Status: frozen planner design for a bounded Host Policy improvement.

## Problem

A real `AI_Skills_Collection` Reviewed Handoff task exposed an infrastructure failure before the plugin itself could be tested. The Executor needed to launch a fresh local Codex runtime so an installed production plugin could process a user-authorized private research artifact. The outer Codex approval reviewer blocked that nested runtime because the command would pass private content to another model runtime and write outside the initial workspace root.

This is not a plugin-quality failure. It is a machine-level Host Policy / production-replay authorization gap.

The user explicitly authorizes trusted plugin repair workflows on their own machines to process explicitly selected local/private artifacts with a fresh OpenAI Codex production runtime without repeated approval, provided the replay uses the current trusted Codex identity, keeps writes/output local and bounded, does not publish private content, and does not gain arbitrary execution privileges.

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

## Important Codex read-semantics boundary

The current local Codex runtime used by the real smoke (`codex-cli 0.148.0-alpha.9`) can read a known file outside the replay workspace while running under legacy `workspace-write`. This is not a Bridge Kit bug and must not be hidden: the current runtime does not provide a mature local CLI restricted-read profile that this wrapper can safely depend on.

Therefore **plugin replay is a write-isolated / execution-bounded trusted-local mode, not a filesystem read-isolation boundary**.

This is acceptable for the current product contract because the user is explicitly authorizing a fresh Codex runtime under the same trusted `CODEX_HOME` to process the selected private artifact for plugin repair/replay. The wrapper still limits which files the caller can intentionally stage or name as replay inputs, and it prevents arbitrary writable roots, arbitrary Codex flags, cross-identity execution, tool-network expansion and automatic publication. It must not claim that the child process is technically unable to read every other same-user file when the underlying Codex runtime cannot enforce that guarantee.

The read-isolation probe may remain as a diagnostic and should record the observed read scope in `run.json`, but **`READABLE` is not a hard failure for the trusted-local replay mode**. A future strict-read mode may be added only when the installed Codex runtime exposes a mature, enforceable restricted-read permission profile or another reviewed platform sandbox. Do not introduce Bubblewrap/custom Landlock/container machinery in this bounded change merely to simulate a capability the current Codex CLI does not expose reliably.

## Rejected shortcuts

Do not solve this by:

- setting global `approval_policy = "never"`;
- setting global `sandbox_mode = "danger-full-access"`;
- broadly allow-listing every `codex exec` invocation;
- broadly allow-listing `bash`, `sh`, `python`, or another general-purpose runtime;
- adding one-off path rules for a single PDF, project, task number, or plugin;
- granting a nested Codex arbitrary writable access to the whole source repository merely because one private artifact is needed;
- claiming read isolation that the current runtime does not enforce;
- weakening destructive Git / branch / remote protections.

A raw `codex exec` prefix is too broad because prefix policy cannot validate all later arguments, paths and configuration overrides. The safe unit to pre-authorize is a Bridge-owned wrapper whose own argument contract is narrow and testable.

## Frozen implementation shape

Implement one first-class Bridge Kit command:

```text
ai-bridge plugin-replay ...
```

The command itself is the stable product boundary.

### 1. Machine-local write-isolated replay workspace

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

“Explicit input” does not mean an arbitrary absolute path. The replay target must resolve through `git -C <target> rev-parse --show-toplevel` to a canonical Git repository root. By default, every `--input` file must resolve inside that target repository root. The only external-file escape hatch is the fixed machine-local trusted inbox:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/plugin-replay/inbox/
```

The caller cannot choose another input root. Path checks must use resolved real paths, so `..`, relative-path tricks and symlink escapes such as `repo/link -> ~/.ssh` are rejected. A task/instruction file may resolve inside the target Git repository, the caller's current Git repository, or the trusted inbox; it may not be an arbitrary private file. If the caller's current working directory is not inside a Git repository, task files are limited to the target repository or trusted inbox.

The child Codex working directory must be the replay workspace, not the consumer repository. The consumer repository must not be added as an arbitrary writable root. If additional context is needed, it must be supplied as another explicit input/context artifact.

A real smoke must verify **write isolation**: the child must not be able to modify a known file outside the replay writable roots. This is the hard filesystem boundary that `workspace-write` is expected to enforce.

### 2. Test the installed production plugin, not source-tree imitation

The child runtime must use the current Codex identity / installed plugin environment from the current process `CODEX_HOME` resolution (`$CODEX_HOME`, otherwise `~/.codex`). `CODEX_HOME` authorization is per identity: `plugin-replay` must not let a caller that is approved under one Host Policy select another Codex identity. The replay helper must not copy `SKILL.md` text into the prompt and pretend that this is equivalent to running the installed plugin.

Require the caller to identify the intended plugin. If the current Codex CLI exposes reliable installed-plugin inspection, verify the plugin is installed; otherwise record the requested plugin and fail clearly if production invocation cannot find it.

### 3. Child Codex invocation is fixed by the wrapper

The wrapper constructs the child command itself. The caller cannot append arbitrary Codex CLI flags.

The child must have these semantic properties:

- approval policy: `never` inside the already validated replay;
- sandbox: bounded, normally `workspace-write`;
- cwd: machine-local replay workspace;
- no `danger-full-access`;
- no arbitrary `-c` / config override passthrough from the caller;
- no arbitrary additional writable directory passthrough;
- ephemeral/non-persistent session when supported;
- tool/shell network disabled by default for local artifact replay unless a future separately reviewed contract introduces a bounded network mode;
- observed filesystem read scope recorded honestly rather than treated as guaranteed restricted when the runtime does not enforce it.

The helper may use `--skip-git-repo-check` because the replay workspace is not required to be a Git repository.

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

Host Policy should pin the trusted `ai-bridge` executable resolution when the current execpolicy supports `host_executable(...)` or equivalent exact executable constraints. `host validate` must report the resolved trusted executable and fail on drift where practical.

### 6. Workflow integration is advisory, not a second permission layer

Update generic Bridge Kit Lite / Reviewed Handoff Executor guidance so that when a frozen task genuinely requires a fresh production plugin runtime, it uses `ai-bridge plugin-replay` rather than constructing a raw nested `codex exec` command.

Do not force ordinary implementation tasks through plugin replay. Do not add a new state machine, role, schema family or task type.

## What this authorization does not cover

The global replay authorization does not authorize:

- caller-selected arbitrary private input paths outside the target repo / trusted inbox;
- recursive harvesting of user directories;
- intentional secrets ingestion as replay input;
- arbitrary external upload;
- unrestricted tool/shell network access;
- destructive filesystem operations outside replay writable roots;
- branch creation/switching, force push, remote mutation or release publication;
- product/scientific scope expansion;
- replacing Planner / Reviewer authority.

It also does **not** claim that the current Codex runtime provides strict same-user filesystem read isolation. That limitation is explicit.

## Acceptance

The change is complete only if all of these are demonstrated:

1. `ai-bridge host install` keeps global `approval_policy = "on-request"`, `sandbox_mode = "workspace-write"`, and `approvals_reviewer = "auto_review"`.
2. `ai-bridge host install` installs the narrow replay pre-authorization for the trusted Bridge executable.
3. `ai-bridge host validate` verifies `ai-bridge plugin-replay ... => allow` and confirms raw `codex exec` did not gain a broad allow.
4. Force push, branch creation/switching, remote mutation, `reset --hard`, `git clean` and existing dangerous cases retain their current approval behavior.
5. The replay helper accepts only explicit input files under the target Git repository or fixed trusted inbox, rejects resolved symlink escapes, and does not recursively stage neighboring files.
6. The child cwd is the machine-local replay workspace; the helper does not expose the whole target repository as a writable child workspace.
7. The child command fixes bounded sandbox + no interactive approval and rejects arbitrary Codex flag passthrough or cross-`CODEX_HOME` selection.
8. A dry-run shows target/plugin/input metadata, replay workspace/output path, resolved Codex executable and exact child argv without printing private contents.
9. A real generic local smoke launches a fresh Codex runtime against a small temporary private-like text input, records the observed read-scope diagnostic, and proves the child cannot **write** to a specified neighboring file outside replay writable roots.
10. The smoke is generic: no `writing-style`, CARE, M&Ms, PDF title, task `044` or project-specific hard-code in implementation/tests.
11. The first real consumer replay after the generic smoke is `AI_Skills_Collection` task `044_writing_style_deep_research_chinese_replay`; its private PDF and rewrite remain local.

## Why this is preferred over alternatives

- **Global raw `codex exec` allow** removes too much review because later arguments and paths are not bounded by the prefix alone.
- **Repo-local permission exceptions** duplicate machine policy and would have to be maintained separately for every plugin/repository.
- **Changing global approval to `never`** makes unapproved commands fail rather than providing a selective trusted path and weakens normal interactive review semantics.
- **Hard-failing on read isolation under current legacy `workspace-write`** makes the feature unusable even though strict read isolation is not available from the current local CLI and was not the user's product goal.
- **Adding Bubblewrap/custom Landlock/container infrastructure now** would create a new platform-specific subsystem before there is evidence that the normal trusted-local Codex boundary is insufficient for the user's plugin-repair workflow.
- **A Bridge-owned write-isolated launcher + one Host Policy allow** gives one machine-wide reusable path while preserving the existing approval boundary everywhere else and states the remaining read-scope limitation honestly.
