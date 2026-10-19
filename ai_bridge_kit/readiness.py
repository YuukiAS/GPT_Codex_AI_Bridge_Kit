from __future__ import annotations

import ast
import contextlib
import hashlib
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Bridge currently supports Unix hosts
    fcntl = None  # type: ignore[assignment]

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.9
    tomllib = None  # type: ignore[assignment]

from .host import (
    REJECTED_GIT_ENV_EXACT,
    REJECTED_GIT_ENV_PREFIXES,
    _canonical_repo_identity,
    _publisher_github_https_identity,
    resolve_codex_home,
)


DEFAULT_PROJECT_DOC_MAX_BYTES = 32768
INSTRUCTION_FILE_NAMES = ("AGENTS.override.md", "AGENTS.md")
BLOCK_CAPS = {"core": 2048, "persistent_run": 4096, "overleaf": 2048}


class ReadinessError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


def splice_managed_agents_block(
    current: bytes | None,
    block: bytes,
    *,
    begin_marker: bytes,
    end_marker: bytes,
    create_prefix: bytes = b"",
) -> tuple[bytes, str]:
    """Project one Bridge-owned block without changing any surrounding bytes."""
    block_start = block.find(begin_marker)
    block_end = block.find(end_marker, block_start + len(begin_marker))
    if block_start != 0 or block_end < 0:
        raise ReadinessError("BRIDGE_MANAGED_BLOCK_TEMPLATE_INVALID")
    owned_block = block[: block_end + len(end_marker)]
    trailing = block[len(owned_block) :]
    if trailing not in {b"", b"\n", b"\r", b"\r\n"}:
        raise ReadinessError("BRIDGE_MANAGED_BLOCK_TEMPLATE_INVALID")
    if current is None:
        prefix = create_prefix + (b"\n\n" if create_prefix else b"")
        return prefix + block, "CREATE"
    begin_count = current.count(begin_marker)
    end_count = current.count(end_marker)
    if begin_count == 0 and end_count == 0:
        return current + b"\n\n" + block, "APPEND"
    if begin_count != 1 or end_count != 1:
        raise ReadinessError("BRIDGE_MANAGED_BLOCK_MARKERS_INVALID")
    start = current.index(begin_marker)
    end = current.find(end_marker, start + len(begin_marker))
    if end < 0:
        raise ReadinessError("BRIDGE_MANAGED_BLOCK_MARKERS_INVALID")
    marker_end = end + len(end_marker)
    return current[:start] + owned_block + current[marker_end:], "UPDATE"


def _bridge_state_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.environ.get("AI_BRIDGE_STATE_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".ai-bridge").resolve()


@contextlib.contextmanager
def _agents_write_lock(target: Path, *, state_root: Path | None = None):
    if fcntl is None:
        raise ReadinessError("BRIDGE_MANAGED_INSTRUCTION_LOCK_UNAVAILABLE")
    identity = hashlib.sha256(target.resolve().as_posix().encode("utf-8")).hexdigest()
    lock_path = _bridge_state_home(state_root) / "locks" / "agents" / f"{identity}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_replace_bytes(path: Path, payload: bytes, *, existing_mode: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.ai-bridge-", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        os.fchmod(fd, existing_mode if existing_mode is not None else 0o644)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def managed_agents_transaction(
    target: Path,
    block: bytes,
    *,
    begin_marker: bytes,
    end_marker: bytes,
    block_name: str,
    create_prefix: bytes = b"",
    skip_existing: bool = False,
    state_root: Path | None = None,
) -> dict[str, Any]:
    """Serialize Bridge-owned AGENTS writes and preserve all marker-external bytes."""
    target = target.resolve()
    agents = target / "AGENTS.md"
    with _agents_write_lock(target, state_root=state_root) as lock_path:
        current = agents.read_bytes() if agents.is_file() else None
        if current is not None and skip_existing and begin_marker in current and end_marker in current:
            projected, action = current, "SKIP"
        else:
            projected, action = splice_managed_agents_block(
                current,
                block,
                begin_marker=begin_marker,
                end_marker=end_marker,
                create_prefix=create_prefix,
            )
        projection = projected_root_agents_budget(
            target,
            projected,
            block_name=block_name,
            block_bytes=len(block),
        )
        if projected != current:
            observed = agents.read_bytes() if agents.is_file() else None
            if observed != current:
                raise ReadinessError("BRIDGE_MANAGED_INSTRUCTION_EXTERNAL_CONFLICT")
            mode = stat.S_IMODE(agents.stat().st_mode) if agents.exists() else None
            _atomic_replace_bytes(agents, projected, existing_mode=mode)
        return {
            "action": action,
            "path": agents,
            "lock_path": lock_path,
            "projection": projection,
            "bytes": projected,
        }


@dataclass(frozen=True)
class ExecutionLocator:
    repo: str
    repo_root: Path
    worktree_path: Path
    branch: str
    expected_commit: str
    mandatory_sources: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BoundText:
    label: str
    path: Path
    relative_path: str
    repo: str
    expected_commit: str
    blob_oid: str
    size_bytes: int
    sha256: str
    text: str
    read_mode: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(
    cwd: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or b"git failed").decode("utf-8", errors="replace").strip()
        raise ReadinessError("GIT_COMMAND_FAILED", detail)
    return result


def _git_text(cwd: Path, args: list[str], *, env: dict[str, str] | None = None) -> str:
    return _git(cwd, args, env=env).stdout.decode("utf-8", errors="strict").strip()


def repo_root(path: Path) -> Path:
    try:
        return Path(_git_text(path, ["rev-parse", "--show-toplevel"])).resolve()
    except Exception as exc:
        raise ReadinessError("TARGET_NOT_GIT_REPOSITORY", str(path)) from exc


def repo_root_or_target(path: Path) -> Path:
    try:
        return repo_root(path)
    except ReadinessError:
        return path.resolve()


def _safe_repo_rel(value: str) -> str:
    if "\0" in value or "\\" in value:
        raise ReadinessError("MANDATORY_SOURCE_PATH_UNSAFE", value)
    path = PurePosixPath(value)
    if not value or value == "." or path.is_absolute() or ".." in path.parts:
        raise ReadinessError("MANDATORY_SOURCE_PATH_UNSAFE", value)
    return path.as_posix()


def _origin_identity(root: Path, *, require_github_https: bool = False) -> str:
    result = _git(root, ["remote", "get-url", "--all", "origin"])
    urls = [line.strip() for line in result.stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if len(urls) != 1:
        raise ReadinessError("EXECUTION_ORIGIN_IDENTITY_UNVERIFIED", f"origin_url_count={len(urls)}")
    try:
        parser = _publisher_github_https_identity if require_github_https else _canonical_repo_identity
        return parser(urls[0])
    except Exception as exc:
        raise ReadinessError("EXECUTION_ORIGIN_IDENTITY_UNVERIFIED", str(exc)) from exc


def freeze_execution_locator(
    target: Path,
    mandatory_sources: list[tuple[str, str]],
    *,
    expected_repo: str | None = None,
    expected_worktree: Path | None = None,
    expected_branch: str | None = None,
    expected_commit: str | None = None,
    require_github_https: bool = False,
) -> ExecutionLocator:
    root = repo_root(target)
    branch = _git_text(root, ["branch", "--show-current"])
    head = _git_text(root, ["rev-parse", "--verify", "HEAD"])
    repo = _origin_identity(root, require_github_https=require_github_https)
    sources = tuple((label, _safe_repo_rel(path)) for label, path in mandatory_sources)
    return ExecutionLocator(
        repo=expected_repo or repo,
        repo_root=root,
        worktree_path=(expected_worktree or root).resolve(),
        branch=expected_branch or branch,
        expected_commit=expected_commit or head,
        mandatory_sources=sources,
    )


def _worktree_entries(root: Path) -> list[dict[str, str]]:
    raw = _git_text(root, ["worktree", "list", "--porcelain"])
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in [*raw.splitlines(), ""]:
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return entries


def _validate_execution_context(locator: ExecutionLocator) -> Path:
    root = repo_root(locator.worktree_path)
    if root != locator.repo_root.resolve() or root != locator.worktree_path.resolve():
        raise ReadinessError(
            "EXECUTION_WORKTREE_MISMATCH",
            f"actual={root} expected={locator.worktree_path.resolve()}",
        )
    actual_repo = _origin_identity(root)
    if actual_repo != locator.repo:
        raise ReadinessError("EXECUTION_REPO_MISMATCH", f"actual={actual_repo} expected={locator.repo}")
    branch = _git_text(root, ["branch", "--show-current"])
    if branch != locator.branch:
        raise ReadinessError("EXECUTION_BRANCH_MISMATCH", f"actual={branch} expected={locator.branch}")
    head = _git_text(root, ["rev-parse", "--verify", "HEAD"])
    if head != locator.expected_commit:
        raise ReadinessError("EXECUTION_HEAD_MISMATCH", f"actual={head} expected={locator.expected_commit}")
    if not re.fullmatch(r"[0-9a-f]{40}", locator.expected_commit):
        raise ReadinessError("EXECUTION_COMMIT_INVALID", locator.expected_commit)
    expected_ref = f"refs/heads/{locator.branch}"
    matches = [
        item
        for item in _worktree_entries(root)
        if Path(item.get("worktree", "")).resolve() == locator.worktree_path.resolve()
    ]
    if len(matches) != 1:
        raise ReadinessError("EXECUTION_WORKTREE_NOT_REGISTERED")
    entry = matches[0]
    if entry.get("HEAD") != locator.expected_commit or entry.get("branch") != expected_ref:
        raise ReadinessError("EXECUTION_WORKTREE_IDENTITY_MISMATCH")
    return root


def _reject_git_environment(source: dict[str, str]) -> None:
    for key in source:
        if key in REJECTED_GIT_ENV_EXACT or key.startswith(REJECTED_GIT_ENV_PREFIXES):
            raise ReadinessError("SOURCE_GIT_ENV_UNSAFE", key)


def _safe_git_env(*, lazy_fetch: bool) -> dict[str, str]:
    _reject_git_environment(os.environ)
    env = os.environ.copy()
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    if not lazy_fetch:
        env["GIT_NO_LAZY_FETCH"] = "1"
    else:
        env.pop("GIT_NO_LAZY_FETCH", None)
    return env


def _reject_repository_git_ambiguity(root: Path) -> None:
    result = _git(root, ["config", "--local", "--name-only", "--list"], check=False)
    if result.returncode != 0:
        raise ReadinessError("SOURCE_GIT_CONFIG_UNREADABLE")
    unsafe_prefixes = ("url.", "credential.", "filter.")
    unsafe_exact = {
        "core.sshcommand",
        "core.gitproxy",
        "core.fsmonitor",
        "core.hookspath",
        "remote.origin.uploadpack",
        "remote.origin.proxy",
        "http.proxy",
        "https.proxy",
    }
    for raw in result.stdout.decode("utf-8", errors="replace").splitlines():
        key = raw.strip().lower()
        if key in unsafe_exact or key.startswith(unsafe_prefixes):
            raise ReadinessError("SOURCE_GIT_CONFIG_UNSAFE", key)
    replace = _git_text(root, ["for-each-ref", "--format=%(refname)", "refs/replace"])
    if replace:
        raise ReadinessError("SOURCE_REPLACE_REFS_ACTIVE")
    graft_path = Path(_git_text(root, ["rev-parse", "--git-path", "info/grafts"]))
    if not graft_path.is_absolute():
        graft_path = root / graft_path
    if graft_path.is_file():
        lines = [
            line.strip()
            for line in graft_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if lines:
            raise ReadinessError("SOURCE_GRAFTS_ACTIVE")


def _require_worktree_equivalence(root: Path, commit: str, path: str, *, expected_blob_oid: str) -> Path:
    env = _safe_git_env(lazy_fetch=False)
    worktree_path = root / path
    try:
        mode = worktree_path.lstat().st_mode
    except OSError as exc:
        raise ReadinessError("MANDATORY_SOURCE_MISSING", path) from exc
    if not stat.S_ISREG(mode):
        raise ReadinessError("MANDATORY_SOURCE_NOT_REGULAR", path)
    index = _git(root, ["--literal-pathspecs", "ls-files", "-v", "-z", "--", path], env=env, check=False)
    records = [record for record in index.stdout.split(b"\0") if record]
    if index.returncode != 0 or len(records) != 1 or len(records[0]) < 3 or records[0][1:2] != b" ":
        raise ReadinessError("MANDATORY_SOURCE_INDEX_ENTRY_INVALID", path)
    tag, entry_path = records[0][:1], records[0][2:]
    if entry_path != os.fsencode(path):
        raise ReadinessError("MANDATORY_SOURCE_INDEX_ENTRY_INVALID", path)
    if tag.decode("ascii", errors="ignore").islower() or tag in {b"S", b"s"}:
        flag = "skip-worktree" if tag in {b"S", b"s"} else "assume-unchanged"
        raise ReadinessError("MANDATORY_SOURCE_INDEX_FLAGS_UNSAFE", f"{path} ({flag})")
    attrs = _git(root, ["check-attr", "-z", "filter", "ident", "working-tree-encoding", "--", path], env=env)
    parts = attrs.stdout.split(b"\0")
    for index_pos in range(0, max(0, len(parts) - 1), 3):
        if index_pos + 2 >= len(parts):
            break
        _attr_path, attr, value = parts[index_pos : index_pos + 3]
        if value not in {b"", b"unspecified", b"unset", b"false"}:
            raise ReadinessError(
                "MANDATORY_SOURCE_GIT_ATTRIBUTE_UNSAFE",
                f"{path}: {attr.decode(errors='replace')}={value.decode(errors='replace')}",
            )
    diff = _git(
        root,
        ["--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--quiet", commit, "--", path],
        env=env,
        check=False,
    )
    if diff.returncode == 1:
        raise ReadinessError("MANDATORY_SOURCE_WORKTREE_MISMATCH", path)
    if diff.returncode != 0:
        hashed = _git(
            root,
            ["--literal-pathspecs", "hash-object", "--no-filters", "--", path],
            env=env,
            check=False,
        )
        actual_oid = hashed.stdout.decode("ascii", errors="replace").strip()
        if hashed.returncode != 0 or actual_oid != expected_blob_oid:
            raise ReadinessError("MANDATORY_SOURCE_DIFF_FAILED", path)
    return worktree_path


def _tree_blob_oid(root: Path, commit: str, path: str, env: dict[str, str]) -> str:
    _git(root, ["cat-file", "-e", f"{commit}^{{commit}}"], env=env)
    result = _git(root, ["--literal-pathspecs", "ls-tree", "-z", commit, "--", path], env=env)
    entries = [entry for entry in result.stdout.split(b"\0") if entry]
    if len(entries) != 1:
        raise ReadinessError("MANDATORY_SOURCE_NOT_IN_COMMIT", path)
    header, sep, entry_path = entries[0].partition(b"\t")
    fields = header.split()
    if not sep or entry_path != os.fsencode(path) or len(fields) != 3:
        raise ReadinessError("MANDATORY_SOURCE_TREE_ENTRY_INVALID", path)
    mode, kind, oid = fields
    if mode not in {b"100644", b"100755"} or kind != b"blob":
        raise ReadinessError("MANDATORY_SOURCE_NOT_BLOB", path)
    return oid.decode("ascii")


def _read_blob(root: Path, oid: str, path: str, env: dict[str, str]) -> bytes:
    kind = _git_text(root, ["cat-file", "-t", oid], env=env)
    if kind != "blob":
        raise ReadinessError("MANDATORY_SOURCE_NOT_BLOB", path)
    size_text = _git_text(root, ["cat-file", "-s", oid], env=env)
    try:
        size = int(size_text)
    except ValueError as exc:
        raise ReadinessError("MANDATORY_SOURCE_BLOB_SIZE_INVALID", path) from exc
    content = _git(root, ["cat-file", "-p", oid], env=env).stdout
    if len(content) != size:
        raise ReadinessError("MANDATORY_SOURCE_BLOB_SIZE_MISMATCH", path)
    return content


def _git_dir(root: Path) -> Path:
    raw = Path(_git_text(root, ["rev-parse", "--git-dir"]))
    return raw if raw.is_absolute() else (root / raw).resolve()


def _objects_dir(root: Path) -> Path:
    raw = Path(_git_text(root, ["rev-parse", "--git-path", "objects"]))
    return raw if raw.is_absolute() else (root / raw).resolve()


def _digest_tree(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _protected_git_snapshot(root: Path) -> dict[str, str | None]:
    git_dir = _git_dir(root)
    result: dict[str, str | None] = {}
    for rel in ("FETCH_HEAD", "index", "config", "packed-refs"):
        path = git_dir / rel
        result[rel] = _sha256_bytes(path.read_bytes()) if path.is_file() else None
    result["refs"] = _digest_tree(git_dir / "refs")
    result["objects"] = _digest_tree(_objects_dir(root))
    return result


def _promisor_origin(root: Path) -> None:
    result = _git(root, ["config", "--get-regexp", r"^remote\..*\.promisor$"], check=False)
    if result.returncode not in {0, 1}:
        raise ReadinessError("SOURCE_PROMISOR_CONFIG_UNREADABLE")
    remotes: set[str] = set()
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        key, _, value = line.partition(" ")
        if value.strip().lower() in {"true", "1", "yes", "on"}:
            match = re.fullmatch(r"remote\.([^.]*)\.promisor", key)
            if match:
                remotes.add(match.group(1))
    if remotes != {"origin"}:
        raise ReadinessError("SOURCE_PROMISOR_ORIGIN_UNVERIFIED", ",".join(sorted(remotes)) or "none")


def _read_missing_blob_isolated(
    root: Path,
    oid: str,
    path: str,
    *,
    state_root: Path | None,
) -> bytes:
    _promisor_origin(root)
    before = _protected_git_snapshot(root)
    base = (
        state_root
        or Path(os.environ.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser() / "readiness" / "objects"
    ).resolve()
    base.mkdir(parents=True, exist_ok=True)
    original_objects = _objects_dir(root)
    with tempfile.TemporaryDirectory(prefix="ai-bridge-objects-", dir=base) as tmp:
        env = _safe_git_env(lazy_fetch=True)
        env["GIT_OBJECT_DIRECTORY"] = tmp
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = original_objects.as_posix()
        present = _git(root, ["cat-file", "-e", oid], env=env, check=False)
        if present.returncode != 0:
            raise ReadinessError("MANDATORY_SOURCE_ISOLATED_FETCH_FAILED", path)
        content = _read_blob(root, oid, path, env)
    after = _protected_git_snapshot(root)
    if before != after:
        raise ReadinessError("MANDATORY_SOURCE_FALLBACK_MUTATED_REPOSITORY", path)
    return content


def _bind_source(
    root: Path,
    locator: ExecutionLocator,
    label: str,
    path: str,
    *,
    state_root: Path | None,
) -> BoundText:
    env = _safe_git_env(lazy_fetch=False)
    oid = _tree_blob_oid(root, locator.expected_commit, path, env)
    worktree_path = _require_worktree_equivalence(
        root,
        locator.expected_commit,
        path,
        expected_blob_oid=oid,
    )
    exists = _git(root, ["cat-file", "-e", oid], env=env, check=False)
    if exists.returncode == 0:
        content = _read_blob(root, oid, path, env)
        mode = "local"
    elif exists.returncode == 1:
        content = _read_missing_blob_isolated(root, oid, path, state_root=state_root)
        mode = "isolated_fallback"
    else:
        raise ReadinessError("MANDATORY_SOURCE_OBJECT_CHECK_FAILED", path)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReadinessError("MANDATORY_SOURCE_NOT_UTF8", path) from exc
    return BoundText(
        label=label,
        path=worktree_path.resolve(),
        relative_path=path,
        repo=locator.repo,
        expected_commit=locator.expected_commit,
        blob_oid=oid,
        size_bytes=len(content),
        sha256=_sha256_bytes(content),
        text=text,
        read_mode=mode,
    )


def preflight_execution_sources(
    locator: ExecutionLocator,
    *,
    isolated_state_root: Path | None = None,
) -> dict[str, Any]:
    root = _validate_execution_context(locator)
    _reject_repository_git_ambiguity(root)
    bound = [
        _bind_source(root, locator, label, path, state_root=isolated_state_root)
        for label, path in locator.mandatory_sources
    ]
    return {
        "schema": "ai-bridge.execution-source-preflight.v1",
        "repo": locator.repo,
        "root": root.as_posix(),
        "worktree_path": locator.worktree_path.as_posix(),
        "branch": locator.branch,
        "head": locator.expected_commit,
        "source_bindings": _binding_records(bound),
        "source_texts": bound,
    }


def preflight_lite_task(
    target: Path,
    task_key: str,
    *,
    require_github_https: bool = True,
) -> dict[str, Any]:
    sources = [
        ("repo_agents", "AGENTS.md"),
        ("agent_rules", "prompts/AGENT_RULES.md"),
        ("task", f"prompts/tasks/{task_key}.md"),
    ]
    locator = freeze_execution_locator(target, sources, require_github_https=require_github_https)
    result = preflight_execution_sources(locator)
    return {**result, "task_key": task_key}


def preflight_reviewed_event(
    target: Path,
    task_key: str,
    current: dict[str, Any],
    *,
    branch: str,
    require_github_https: bool = True,
) -> dict[str, Any]:
    root = repo_root(target)
    sources: list[tuple[str, str]] = []
    if (root / "AGENTS.md").is_file():
        sources.append(("repo_agents", "AGENTS.md"))
    sources.extend(
        [
            ("reviewed_readme", "automation/reviewed_handoff/README.md"),
            ("executor_prompt", "automation/reviewed_handoff/prompts/CODEX_EXECUTOR.md"),
            ("request", f"automation/reviewed_handoff/tasks/{task_key}/REQUEST.md"),
            ("plan", f"automation/reviewed_handoff/tasks/{task_key}/PLAN.md"),
            ("current", f"automation/reviewed_handoff/tasks/{task_key}/CURRENT.json"),
        ]
    )
    locator = freeze_execution_locator(
        target,
        sources,
        expected_branch=branch,
        require_github_https=require_github_https,
    )
    result = preflight_execution_sources(locator)
    bound = result["source_texts"]
    try:
        disk_current = __import__("json").loads(bound[-1].text)
    except Exception as exc:
        raise ReadinessError("CURRENT_JSON_INVALID") from exc
    if disk_current.get("task_key") != task_key:
        raise ReadinessError("CURRENT_TASK_KEY_MISMATCH")
    if disk_current.get("state") != current.get("state"):
        raise ReadinessError("CURRENT_STATE_CHANGED_BEFORE_LAUNCH")
    return {**result, "task_key": task_key}


def _binding_records(bound: list[BoundText]) -> list[dict[str, Any]]:
    return [
        {
            "label": item.label,
            "repo": item.repo,
            "expected_commit": item.expected_commit,
            "path": item.relative_path,
            "blob_oid": item.blob_oid,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
            "read_mode": item.read_mode,
        }
        for item in bound
    ]


def format_bound_context(bound: list[BoundText]) -> str:
    return "\n\n".join(
        "\n".join(
            [
                f"### {item.label}: {item.relative_path}",
                f"repo: {item.repo}",
                f"expected_commit: {item.expected_commit}",
                f"blob_oid: {item.blob_oid}",
                f"sha256: {item.sha256}",
                f"size_bytes: {item.size_bytes}",
                f"read_mode: {item.read_mode}",
                "",
                item.text,
            ]
        )
        for item in bound
    )


def _minimal_toml_loads(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current = data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]") and not line.startswith("[["):
            current = data
            for part in line[1:-1].split("."):
                key = part.strip().strip('"').strip("'")
                current = current.setdefault(key, {})
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.split("#", 1)[0].strip()
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            parsed = value
        current[key.strip()] = parsed
    return data


def _load_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return {}
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return tomllib.loads(text) if tomllib is not None else _minimal_toml_loads(text)
    except Exception:
        return None


def _project_trust(config: dict[str, Any], root: Path) -> str:
    projects = config.get("projects")
    if not isinstance(projects, dict):
        return "UNKNOWN"
    root = root.resolve()
    best: tuple[int, str] | None = None
    for raw_path, values in projects.items():
        if not isinstance(raw_path, str) or not isinstance(values, dict):
            continue
        try:
            project = Path(raw_path).expanduser().resolve()
            root.relative_to(project)
        except Exception:
            continue
        raw = str(values.get("trust_level", values.get("trusted", ""))).lower()
        state = "TRUSTED" if raw in {"trusted", "true", "yes"} else "UNTRUSTED" if raw in {"untrusted", "false", "no"} else "UNKNOWN"
        if best is None or len(project.parts) > best[0]:
            best = (len(project.parts), state)
    return best[1] if best else "UNKNOWN"


def effective_instruction_config(root: Path, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    active_env = os.environ if env is None else env
    root = root.resolve()
    codex_home = resolve_codex_home(None, active_env)
    global_path = codex_home / "config.toml"
    project_path = root / ".codex" / "config.toml"
    global_config = _load_toml(global_path)
    project_config = _load_toml(project_path)
    if global_config is None or project_config is None:
        return {"state": "UNKNOWN", "reason": "CONFIG_SOURCE_UNREADABLE_OR_INVALID"}
    if project_config:
        trust = _project_trust(global_config, root)
        if trust != "TRUSTED":
            return {"state": "UNKNOWN", "reason": f"PROJECT_TRUST_NOT_VERIFIED: {trust}"}
    merged = dict(global_config)
    merged.update(project_config)
    maximum = merged.get("project_doc_max_bytes", DEFAULT_PROJECT_DOC_MAX_BYTES)
    if not isinstance(maximum, int) or maximum <= 0:
        return {"state": "UNKNOWN", "reason": "CONFIG_PROJECT_DOC_MAX_BYTES_INVALID"}
    names = list(INSTRUCTION_FILE_NAMES)
    fallback = merged.get("project_doc_fallback_filenames", [])
    if isinstance(fallback, list):
        for value in fallback:
            if isinstance(value, str) and value and "/" not in value and "\\" not in value and value not in names:
                names.append(value)
    return {
        "state": "VERIFIED",
        "reason": "",
        "max_bytes": maximum,
        "max_bytes_source": (
            f"project:{project_path}"
            if "project_doc_max_bytes" in project_config
            else f"codex_home:{global_path}"
            if "project_doc_max_bytes" in global_config
            else "native_default"
        ),
        "instruction_file_names": names,
    }


def _selected_instruction_file(root: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def projected_root_agents_budget(
    target: Path,
    projected_agents: bytes,
    *,
    block_name: str,
    block_bytes: int,
) -> dict[str, Any]:
    root = repo_root_or_target(target)
    config = effective_instruction_config(root)
    if config.get("state") != "VERIFIED":
        raise ReadinessError("BRIDGE_MANAGED_INSTRUCTION_CONFIG_UNVERIFIED", str(config.get("reason")))
    cap = BLOCK_CAPS.get(block_name)
    if cap is None:
        raise ReadinessError("BRIDGE_MANAGED_INSTRUCTION_BLOCK_UNKNOWN", block_name)
    if block_bytes > cap:
        raise ReadinessError(
            "BRIDGE_MANAGED_INSTRUCTION_BLOCK_OVERFLOW",
            f"block={block_name} bytes={block_bytes} cap={cap}",
        )
    names = list(config["instruction_file_names"])
    selected = _selected_instruction_file(root, names)
    total = len(projected_agents)
    sources = [{"path": "AGENTS.md", "projected_bytes": len(projected_agents)}]
    if selected is not None and selected.name != "AGENTS.md":
        size = len(selected.read_bytes())
        total += size
        sources.insert(0, {"path": selected.name, "projected_bytes": size})
    limit = int(config["max_bytes"])
    if total > limit:
        first = sources[-1]["path"]
        raise ReadinessError(
            "BRIDGE_MANAGED_INSTRUCTION_PROJECTED_OVERFLOW",
            f"limit={limit} projected_total={total} first_risk_source={first} bytes_to_free={total - limit}",
        )
    return {
        "schema": "ai-bridge.managed-instruction-projection.v1",
        "state": "PASS",
        "block_name": block_name,
        "block_bytes": block_bytes,
        "block_cap": cap,
        "max_bytes": limit,
        "max_bytes_source": config["max_bytes_source"],
        "projected_total": total,
        "sources": sources,
    }


def preflight_root_agents_mutation(
    target: Path,
    projected_agents: bytes | str,
    *,
    block_name: str,
    block_bytes: int,
) -> dict[str, Any]:
    raw = projected_agents.encode("utf-8") if isinstance(projected_agents, str) else projected_agents
    return projected_root_agents_budget(
        target,
        raw,
        block_name=block_name,
        block_bytes=block_bytes,
    )
