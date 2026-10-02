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
BASE_PYTHON_EXECUTABLE=/users/a/e/aereinh/scientific-runtime/python/releases/python-3.12.4-source-b883db4-20261001T144549Z/.venv/bin/python
```

`codex --version` emitted a non-fatal warning before the version string:

```text
WARNING: proceeding, even though we could not create PATH aliases: Read-only file system (os error 30)
codex-cli 0.142.0
```

The required Codex CLI version matched `codex-cli 0.142.0`.

## Candidate Source Identity

```text
CANDIDATE_ROOT=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a
CANDIDATE_SOURCE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source
SOURCE_MATCHES_GIT_ARCHIVE=YES_EXCEPT_GENERATED_PYTHON_BYTECODE_CACHE_AFTER_IMPORT
CANDIDATE_PYPROJECT_VERSION=0.10.0
CANDIDATE___VERSION__=0.10.0
CANDIDATE_TEMPLATE_PRESENT=templates/host/GLOBAL_AGENTS_SNIPPET.md
SOURCE_CODE_FILE_DRIFT=NO
GENERATED_BYTECODE_CACHE_PRESENT=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source/ai_bridge_kit/__pycache__
BYTECODE_CACHE_CLEANUP=NOT_PERFORMED_APPROVAL_TIMEOUT
```

## Editable Install Identity

Candidate install identity was established after rebuilding only the disposable
candidate runtime venv and using local-only editable install semantics.

```text
BUILD_PYTHON=/users/a/e/aereinh/bin/python3
BUILD_TOOL_SITE_PACKAGES=/users/a/e/aereinh/scientific-runtime/python/releases/python-3.12.4-source-b883db4-20261001T144549Z/.venv/lib/python3.12/site-packages
BUILD_SETUPTOOLS_VERSION=84.0.0
EDITABLE_INSTALL=PASS
EDITABLE_WHEEL_SHA256=d8bbd91b1e38bfb3bc554cec6ea3c5295d357f75b3a61f0399dcfc226cd50b9c
```

The normal candidate runtime identity was then validated without temporary
`PYTHONPATH`:

```text
PYTHONPATH=
CANDIDATE_EXECUTABLE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
CANDIDATE_EXECUTABLE_REALPATH=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
AI_BRIDGE_WHERE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source
CANDIDATE_IMPORT_FILE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source/ai_bridge_kit/__init__.py
CANDIDATE_IMPORT_VERSION=0.10.0
CANDIDATE_DISTRIBUTION_VERSION=0.10.0
DIRECT_URL={"dir_info": {"editable": true}, "url": "file:///users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source"}
RUNTIME_TEMPLATE_LOOKUP=PASS
PRODUCTION_BRIDGE_SOURCE_DEPENDENCY=NO
TEMP_BUILD_PYTHONPATH_DEPENDENCY=NO
```

## Candidate Machine Policy Identity

```text
CODEX_HOME=/users/a/e/aereinh/.codex
MANAGED_FILE_BACKUP=PASS
HOST_INSTALL=PASS
HOST_VALIDATE=PASS
HOST_EXECUTABLE_PIN=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
HOST_IMPORT_SOURCE=/users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/source/ai_bridge_kit/host.py
HOST_IMPORT_VERSION=0.10.0
HOST_DISTRIBUTION_METADATA=0.10.0 @ /users/a/e/aereinh/.ai-bridge/candidates/bridge-core--execution-reliability-closure/9db19b0409816c22042a246b35a33e1d34fedd0a/venv/bin/ai-bridge
```

After the fresh Codex child exited, managed `CODEX_HOME` files were restored from
the pre-install backup and hash-verified.

```text
CODEX_HOME_RESTORE_RESULT=PASS_HASH_MATCH
```
