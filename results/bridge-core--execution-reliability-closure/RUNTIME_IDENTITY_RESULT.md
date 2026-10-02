# Runtime Identity Result

Task: `bridge-core--execution-reliability-closure`

Stage: `B`

`FINAL_SOURCE_CANDIDATE`: `9db19b0409816c22042a246b35a33e1d34fedd0a`

## Base Runtime

```text
BASE_CODEX=/users/a/e/aereinh/codex-runtime/bin/codex
BASE_CODEX_VERSION=codex-cli 0.142.0
BASE_PYTHON=/users/a/e/aereinh/bin/python3
BASE_PYTHON_VERSION=Python 3.12.4
```

`codex --version` emitted a non-fatal warning before the version string:

```text
WARNING: proceeding, even though we could not create PATH aliases: Read-only file system (os error 30)
codex-cli 0.142.0
```

The required Codex CLI version matched `codex-cli 0.142.0`.

## Candidate Source Identity

```text
CANDIDATE_SOURCE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source
CANDIDATE_PYPROJECT_VERSION=0.10.0
CANDIDATE_SOURCE_VERSION=0.10.0
```

## Candidate Install Identity

Candidate install identity was established after the bounded local-only wheel
recovery:

```text
BUILD_PYTHON=/users/a/e/aereinh/bin/python3
BUILD_SETUPTOOLS_VERSION=84.0.0
WHEEL_SHA256=cac5c13e66d1b2127d2189215ca6adeb270074633202b01475f81817f3e020a3
CANDIDATE_EXECUTABLE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
CANDIDATE_IMPORT_SOURCE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/lib/python3.12/site-packages/ai_bridge_kit/__init__.py
CANDIDATE_IMPORT_VERSION=0.10.0
CANDIDATE_DISTRIBUTION_VERSION=0.10.0
```

Host install identity could not be completed because the candidate wheel omitted
runtime template data required by `ai-bridge host install`:

```text
MISSING_RUNTIME_DATA=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/lib/python3.12/site-packages/templates/host/GLOBAL_AGENTS_SNIPPET.md
HOST_VALIDATE_RESULT=NOT_RUN_HOST_INSTALL_FAILED
CODEX_HOME=/users/a/e/aereinh/.codex
CODEX_HOME_RESTORE_RESULT=PASS_HASH_MATCH
HOST_EXECUTABLE_PIN_UPDATED=NO
```

The stop happened before fresh Codex child launch. Managed CODEX_HOME files were
restored from pre-install backups and hash-verified.
