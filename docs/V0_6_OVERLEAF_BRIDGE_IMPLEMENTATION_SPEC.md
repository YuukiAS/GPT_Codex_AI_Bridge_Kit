# Overleaf Bridge v0.6 Implementation Spec

Status: implementation plan for `v0.6.0`.

## 1. Product role

Overleaf Bridge is an **optional project-level integration** in GPT-Codex AI Bridge Kit. It is not a new Handoff role, state machine, watcher, reviewer, or asynchronous workflow.

Its purpose is to support the common research-repository layout where Codex must work with the **entire repository** (code, analysis, results, documentation, and manuscript) while Overleaf must receive **only one publication-ready manuscript directory**.

Canonical example:

```text
research-repo/
├── code/
├── analysis/
├── data/
├── results/
├── docs/
├── paper/
│   ├── manuscript/       # publication root sent to Overleaf
│   ├── notes/            # local/GitHub only
│   └── submission/       # local/GitHub only
└── AGENTS.md
```

The required information flow is:

```text
whole GitHub repository
        │
        ├── Codex reads code / results / docs / paper
        │
        └── Codex writes paper/manuscript
                    │
                    ▼
             Overleaf Bridge
                    │
                    ▼
          Overleaf project root
```

Overleaf must not receive `code/`, `analysis/`, `data/`, `results/`, `docs/`, Handoff control files, or other repository content merely because they share the same GitHub repository.

## 2. Why this is a Bridge Kit capability

The feature belongs in `GPT_Codex_AI_Bridge_Kit` rather than a separate repository because it is another optional repository integration, analogous in lifecycle to other project-level capabilities:

```text
machine layer
└── Host Policy

project layer
├── Lite
├── Review        optional
├── Generic Notifier        optional
├── Control         optional
└── Overleaf Bridge         optional
```

Installing Overleaf Bridge must not silently install Review, Control, Notifier, Visual Review, or any external GPT automation.

## 3. External constraints from Overleaf

The implementation must follow current Overleaf Git Integration behavior:

- use Overleaf **Git Integration**, not GitHub Synchronization, because GitHub Synchronization works at repository level and cannot expose only a monorepo subdirectory;
- Overleaf Git Integration exposes each project as a Git remote and supports push/pull;
- Overleaf permits one linear Git branch per project; Bridge Kit resolves the
  actual branch from the remote during `connect`;
- authentication is token-based; Git username is `git` and the authentication token is used as the password;
- tokens are secrets and must never be committed, printed, accepted in a command-line flag, or persisted by Bridge Kit;
- users may rely on their normal Git credential helper for token persistence.

Official references at planning time:

- https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git
- https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git/git-integration-authentication-tokens
- https://docs.overleaf.com/integrations-and-add-ons/git-integration-and-github-synchronization/git-integration/advanced-git-operations

## 4. Core design decision: do not add an Overleaf remote to the research repository

The target research repository must keep its normal Git topology, typically:

```text
origin -> GitHub
main   -> canonical research branch
```

Overleaf Bridge must **not** run any of the following against the target repository as part of normal installation or sync:

```text
git remote add overleaf ...
git remote set-url ...
git branch --set-upstream-to ...
git push --force ...
git reset --hard ...
git clean ...
```

This is important for two reasons:

1. Host Policy deliberately treats remote mutation and branch-topology changes as user-controlled actions.
2. The Overleaf project represents only a manuscript subdirectory, so treating it as a normal remote of the full research repository is semantically incorrect.

Instead, Bridge Kit owns a **machine-local mirror repository** outside the research repository.

Default state location:

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/              # local clone of the Overleaf Git project
```

This machine-local state is operational only. It must not be committed to the consumer repository.

`connection.json` may contain the Overleaf Git URL and synchronization metadata, but never an authentication token.

## 5. Tracked consumer-project installation

Installing the feature into a consumer repository should create only a small, explicit project contract:

```text
automation/overleaf/
├── README.md
└── config.toml
```

and a managed block in the consumer repository's root `AGENTS.md`.

Suggested `config.toml` schema:

```toml
schema_version = 1
paper_root = "paper/manuscript"
main_document = "main.tex"

# Repository-relative paths inside paper_root that are intentionally local-only.
# These files are not published to Overleaf and are preserved during pull.
exclude_paths = []
```

Rules:

- `paper_root` must be relative to repository root;
- absolute paths and path traversal (`..`) are invalid;
- resolved paths must remain inside the repository;
- `main_document` must resolve inside `paper_root`;
- the Overleaf remote branch is resolved during `connect` from the actual Git
  remote and is stored only in machine-local `connection.json`;
- configuration contains no remote URL and no secret;
- installation is idempotent and non-destructive;
- existing unrelated `AGENTS.md` content must be preserved.

The managed AGENTS block should explain, in concise form:

- Codex may and should use the whole repository as scientific/technical context;
- only `paper_root` is publishable to Overleaf;
- Overleaf is a collaboration mirror, not a second canonical research repository;
- final manuscript assets needed by LaTeX must live inside the publication root;
- `ai-bridge overleaf push` must not be used to overwrite unseen remote edits;
- after `ai-bridge overleaf pull`, local changes should be reviewed/compiled/committed and then pushed to the normal GitHub `origin` through the repository's ordinary workflow.

## 6. CLI surface

Add a dedicated router module rather than expanding the legacy CLI further:

```text
ai_bridge_kit/overleaf.py
```

and route it from `ai_bridge_kit/bridge_cli.py`.

Required commands:

```bash
ai-bridge overleaf install \
  --target /path/to/repo \
  --paper-root paper/manuscript \
  [--main-document main.tex]

ai-bridge overleaf connect \
  --target /path/to/repo \
  --remote-url https://git@git.overleaf.com/<PROJECT_ID> \
  [--bootstrap]

ai-bridge overleaf status --target /path/to/repo
ai-bridge overleaf push   --target /path/to/repo
ai-bridge overleaf pull   --target /path/to/repo
ai-bridge overleaf validate --target /path/to/repo
```

Do not add a token argument.

Do not make Overleaf synchronization automatic on ordinary `git push origin main`. v0.6 is intentionally user/Codex-triggered, not a background poller.

## 7. Publication content model

The bridge publishes a **content projection**, not a second copy of the research repository's Git history.

For local-to-Overleaf publication, source content must be generated from the configured publication root. The implementation should prefer Git-tracked content and must not accidentally ship cache/build garbage merely because it exists in the working directory.

Recommended behavior:

1. determine tracked files under `paper_root`;
2. apply `exclude_paths`;
3. preserve their paths relative to `paper_root`;
4. materialize that set into the machine-local Overleaf mirror;
5. delete previously published files that are no longer in the current publication set;
6. leave `.git/` untouched;
7. commit the mirror change and push the mirror's resolved remote branch to Overleaf.

Therefore:

```text
repo/paper/manuscript/main.tex
```

must appear in Overleaf as:

```text
main.tex
```

not as:

```text
paper/manuscript/main.tex
```

No file outside `paper_root` may be published.

`exclude_paths` must support project-local files such as manuscript-specific `AGENTS.md`, local README files, or a tracked compiled `main.pdf` that should remain in GitHub but not be mirrored to Overleaf.

## 8. Synchronization safety model

The primary safety requirement is **never silently overwrite collaborator edits made in Overleaf**.

Bridge Kit must maintain a synchronization baseline in machine-local state. Use a deterministic content digest over the published file set, based on relative path plus bytes. At minimum store:

```text
last_synced_digest
last_remote_commit
last_local_commit_or_locator
```

The remote commit is an operational locator only; Overleaf's internal history and Git commits are not one-to-one.

For each operation, compute:

```text
baseline = last_synced_digest
local    = current publication digest
remote   = current Overleaf mirror digest after fetch/update
```

Interpretation:

```text
local == baseline and remote == baseline   -> synced
local != baseline and remote == baseline   -> local ahead
local == baseline and remote != baseline   -> remote ahead
local == remote and local != baseline      -> equivalent changes; refresh baseline
local != baseline and remote != baseline
  and local != remote                      -> diverged
```

### Push

`push` must:

1. validate installation and connection;
2. refuse if the publishable portion of `paper_root` contains uncommitted changes that would make the user believe unsaved/uncommitted content is being published;
3. fetch/update the machine-local Overleaf mirror first;
4. compute local/remote/baseline digests;
5. if remote is ahead, refuse and instruct the user/Codex to pull first;
6. if diverged, refuse without changing either side;
7. if already synced/equivalent, perform no unnecessary commit;
8. if only local is ahead, mirror the local publication set, commit, push to the resolved Overleaf branch, then update the baseline.

No force push in normal operation.

### Pull

`pull` must:

1. validate installation and connection;
2. fetch/update the machine-local Overleaf mirror first;
3. compute local/remote/baseline digests;
4. if local is ahead and remote is unchanged, make no destructive change and report that local work is ahead;
5. if diverged, refuse without changing either side;
6. if only remote is ahead, copy the remote publication set into `paper_root`;
7. propagate remote deletions only for paths previously managed/published by the bridge;
8. preserve configured `exclude_paths` and everything outside `paper_root`;
9. update the synchronization baseline;
10. **do not automatically commit or push `origin`**. Leave the imported manuscript changes in the target working tree so Codex/user can review, compile, and commit them through the normal project workflow.

A subsequent `push` must fail clearly if those pulled changes remain uncommitted and the command's semantics require a committed publication snapshot.

## 9. Bootstrap and connection semantics

The normal first-use workflow is:

1. user creates a **Blank Project** in Overleaf;
2. user deletes Overleaf's generated default `main.tex`, leaving no meaningful manuscript content;
3. user obtains the project's Git URL;
4. user creates/uses an Overleaf Git authentication token through Overleaf Account Settings;
5. user runs `ai-bridge overleaf connect ... --bootstrap`;
6. Git asks for the token through the normal credential flow if it is not already stored by the user's credential helper.

`connect --bootstrap` must:

- clone/fetch the Overleaf project into the machine-local mirror;
- verify the current remote project tree is empty of meaningful user files before seeding it;
- fail closed rather than overwrite a non-empty existing Overleaf manuscript;
- publish the current configured manuscript content;
- establish the first synchronization baseline.

`connect` without `--bootstrap` should only establish/re-establish a connection when current local publication content and remote content are already identical. If they differ and no baseline exists, fail with a clear explanation rather than guessing which side is authoritative.

More advanced first-connect conflict/adoption modes are explicitly out of scope for v0.6. They may be added only after the basic workflow is validated on a real project.

## 10. Authentication and secret handling

The bridge must never:

- accept `--token ...`;
- embed a token in a Git URL;
- write a token into `connection.json`, tracked config, logs, tests, README examples, exceptions, or process output;
- implement a custom credential database.

Use normal Git authentication. For Overleaf Cloud, normalize/document URLs in the token-compatible form:

```text
https://git@git.overleaf.com/<PROJECT_ID>
```

where username is `git` and the token is supplied as the Git password.

Authentication failures must be reported as authentication failures. Do not retry indefinitely and do not silently downgrade to password-based authentication.

## 11. Validation and status behavior

`validate` should be deterministic and should not require network access for the project-structure checks. It must validate at least:

- target is inside a Git repository;
- installation files exist and parse;
- schema version supported;
- `paper_root` is safe and exists;
- `main_document` exists inside `paper_root`;
- tracked config has no remote branch; when connected, `connection.json` stores a non-empty resolved remote branch;
- excluded paths are safe descendants of `paper_root`;
- no configured publication path escapes through symlink/path traversal;
- target repository `origin` is not modified by the bridge;
- no tracked secret/token field exists in Overleaf config.

It may emit a warning (not necessarily a hard failure) when common LaTeX references appear to escape the publication root, for example `../` references from `.tex` files, because such a manuscript will compile locally but fail once only `paper_root` is mirrored.

`status` should provide a concise human-readable summary containing:

- installed/not installed;
- connected/not connected;
- paper root;
- main document;
- Overleaf remote host/project locator with no credentials;
- synchronization condition: synced / local ahead / remote ahead / diverged / unknown;
- whether publishable manuscript changes are uncommitted;
- recommended next action.

## 12. Files expected in Bridge Kit implementation

Expected implementation footprint (Codex may adjust exact helper placement if repository conventions demand it):

```text
ai_bridge_kit/
├── bridge_cli.py                  # add overleaf routing
└── overleaf.py                    # new implementation

templates/
└── overleaf/
    ├── README.md
    ├── config.toml
    └── AGENTS_SNIPPET.md

tests/
├── test_bridge_cli_router.py      # routing regression
└── test_overleaf.py               # new core tests

docs/
└── V0_6_OVERLEAF_BRIDGE_IMPLEMENTATION_SPEC.md

README.md
QUICKSTART.md
AGENTS.md
CHANGELOG.md
pyproject.toml
ai_bridge_kit/__init__.py
```

Do not refactor unrelated Control, Review, Visual Review, Notifier, or Host Policy code merely to share abstractions.

## 13. Required tests

Tests must use temporary local Git repositories / bare remotes to simulate Overleaf. The test suite must not require a real Overleaf account, token, network connection, GitHub repository, or LaTeX installation.

Required behavioral coverage:

1. `install` creates the tracked Overleaf config/templates and managed AGENTS block.
2. Re-running `install` is idempotent.
3. Unsafe/escaping `paper_root`, `main_document`, and exclude paths are rejected.
4. `connect --bootstrap` succeeds only against an empty simulated remote.
5. Bootstrap refuses a non-empty remote and preserves its content.
6. A push maps `paper_root` to remote project root and publishes no repository-external content.
7. Push excludes configured local-only manuscript paths.
8. Push propagates deletion of previously published files.
9. Push refuses when remote changed since baseline.
10. Pull imports remote edits/additions/deletions when local publication content is unchanged.
11. Pull preserves exclude paths and all paths outside `paper_root`.
12. Diverged local+remote changes fail closed with neither side overwritten.
13. Equivalent local and remote content refreshes baseline without a spurious commit.
14. Token-like secret values never appear in tracked config or normal command output.
15. Overleaf routing does not break existing `ai-bridge`, `reviewed-handoff`, or `visual-review` command routing.
16. Existing test suite remains green.

Where practical, test state transitions using real Git subprocesses rather than mocking every Git command, because the main risk is incorrect Git/content synchronization semantics.

## 14. Documentation requirements

README and QUICKSTART should explain the user flow in plain terms:

```text
one research repo
+ one publication root
+ one Overleaf project
```

Typical usage:

```bash
ai-bridge overleaf install \
  --target /path/to/research-repo \
  --paper-root paper/manuscript

ai-bridge overleaf connect \
  --target /path/to/research-repo \
  --remote-url https://git@git.overleaf.com/<PROJECT_ID> \
  --bootstrap

ai-bridge overleaf status --target /path/to/research-repo
ai-bridge overleaf push --target /path/to/research-repo
ai-bridge overleaf pull --target /path/to/research-repo
```

Documentation must state explicitly:

- Overleaf does **not** pull a GitHub monorepo subfolder itself;
- Bridge Kit publishes that subfolder to the Overleaf Git project;
- GitHub `origin/main` remains the canonical whole-project repository;
- Overleaf edits must be pulled before a conflicting push;
- tokens are handled by Git credential tooling, not stored by Bridge Kit.

## 15. Versioning and release boundary

This is a new user-facing project-level capability, so implementation should bump:

```text
0.5.4 -> 0.6.0
```

Update both:

```text
pyproject.toml
ai_bridge_kit/__init__.py
```

and add a `0.6.0` entry to `CHANGELOG.md`.

Do not create a Git tag or GitHub Release unless the repository's existing release process explicitly requires it or the user separately authorizes it.

## 16. Acceptance gate for this round

This round is complete only when all of the following are true:

1. generic Overleaf Bridge implementation is present in Bridge Kit;
2. all required local/bare-remote tests pass;
3. the full existing test suite passes;
4. docs and CLI help are consistent with actual behavior;
5. no real Overleaf token/project is required for tests;
6. no target-repository remote mutation is part of the design;
7. no secret persistence is introduced;
8. package version is `0.6.0`;
9. changes are committed and pushed to `origin/main`;
10. working tree is clean after publication.

**Do not adapt TRACE in this implementation round.** TRACE is the first real consumer validation and will be handled only after this generic Bridge Kit implementation is reviewed and accepted.

## 17. Next round: TRACE validation target

After v0.6 implementation passes review, adapt `YuukiAS/TRACE` with approximately:

```text
paper_root = "paper/manuscript"
main_document = "main.tex"
```

Before connecting to a real Overleaf project, inspect TRACE's current manuscript-only files and choose explicit `exclude_paths` for local-only material such as manuscript-level agent instructions, local README files, or tracked compiled outputs.

The real acceptance test will be:

- Codex still opens and reasons over the entire TRACE repository;
- Overleaf receives only the publication projection from `paper/manuscript/`;
- `main.tex` is at Overleaf project root and compiles there;
- code/data/docs/results never appear in Overleaf;
- a small Overleaf-side test edit can be pulled back into TRACE without touching files outside the manuscript root.
