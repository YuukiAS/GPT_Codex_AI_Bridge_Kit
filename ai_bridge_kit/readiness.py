from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .host import (
    REJECTED_GIT_ENV_EXACT,
    REJECTED_GIT_ENV_PREFIXES,
    _canonical_repo_identity,
    _publisher_github_https_identity,
    inspect_host_policy,
    resolve_codex_home,
)


DEFAULT_PROJECT_DOC_MAX_BYTES = 32768
INSTRUCTION_FILE_NAMES = ("AGENTS.override.md", "AGENTS.md")
FALLBACK_INSTRUCTION_FILE_NAMES = ("AGENTS.override.md", "AGENTS.md", "INSTRUCTIONS.md")


class ReadinessError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class BoundText:
    label: str
    path: Path
    relative_path: str
    size_bytes: int
    sha256: str
    text: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(
    cwd: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode != 0:
        raise ReadinessError("GIT_COMMAND_FAILED", (result.stderr or result.stdout or "git failed").strip())
    return result


def git_text(cwd: Path, args: list[str], *, env: dict[str, str] | None = None) -> str:
    return _git(cwd, args, env=env).stdout.strip()


def repo_root(path: Path) -> Path:
    try:
        return Path(git_text(path, ["rev-parse", "--show-toplevel"])).resolve()
    except Exception as exc:
        raise ReadinessError("TARGET_NOT_GIT_REPOSITORY", str(path)) from exc


def repo_root_or_target(path: Path) -> Path:
    try:
        return repo_root(path)
    except ReadinessError:
        return path.resolve()


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_bound_text(path: Path, *, root: Path, label: str) -> BoundText:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReadinessError("MANDATORY_SOURCE_UNREADABLE", path.as_posix()) from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReadinessError("MANDATORY_SOURCE_NOT_UTF8", path.as_posix()) from exc
    return BoundText(
        label=label,
        path=path.resolve(),
        relative_path=_repo_relative(path, root),
        size_bytes=len(raw),
        sha256=_sha256_bytes(raw),
        text=text,
    )


def _read_config_text(config: Path) -> str | None:
    if not config.exists():
        return None
    try:
        return config.read_text(encoding="utf-8")
    except OSError:
        return None


def _parse_project_doc_max_bytes(config: Path) -> int | None:
    text = _read_config_text(config)
    if text is None:
        return None
    match = re.search(r"(?m)^\s*project_doc_max_bytes\s*=\s*(\d+)\s*$", text)
    if not match:
        return None
    return int(match.group(1))


def _parse_project_doc_fallback_file(config: Path) -> str | None:
    text = _read_config_text(config)
    if text is None:
        return None
    match = re.search(r"(?m)^\s*project_doc_fallback_file\s*=\s*[\"']([^\"']+)[\"']\s*$", text)
    return match.group(1).strip() if match and match.group(1).strip() else None


def effective_instruction_config(root: Path, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    active_env = os.environ if env is None else env
    codex_home = resolve_codex_home(None, active_env)
    sources = [
        ("codex_home", codex_home / "config.toml"),
        ("project", root / ".codex" / "config.toml"),
    ]
    max_bytes = DEFAULT_PROJECT_DOC_MAX_BYTES
    max_source = "default"
    fallback_names = list(FALLBACK_INSTRUCTION_FILE_NAMES)
    for label, path in sources:
        if path.exists() and not path.is_file():
            return {
                "state": "UNKNOWN",
                "reason": f"CONFIG_SOURCE_NOT_FILE: {path}",
                "codex_home": codex_home.as_posix(),
                "max_bytes": None,
                "max_bytes_source": None,
                "instruction_file_names": fallback_names,
            }
        if path.exists() and _read_config_text(path) is None:
            return {
                "state": "UNKNOWN",
                "reason": f"CONFIG_SOURCE_UNREADABLE: {path}",
                "codex_home": codex_home.as_posix(),
                "max_bytes": None,
                "max_bytes_source": None,
                "instruction_file_names": fallback_names,
            }
        configured = _parse_project_doc_max_bytes(path)
        if configured is not None:
            if configured <= 0:
                return {
                    "state": "UNKNOWN",
                    "reason": f"CONFIG_PROJECT_DOC_MAX_BYTES_INVALID: {path}",
                    "codex_home": codex_home.as_posix(),
                    "max_bytes": None,
                    "max_bytes_source": None,
                    "instruction_file_names": fallback_names,
                }
            max_bytes = configured
            max_source = f"{label}:{path.as_posix()}"
        fallback = _parse_project_doc_fallback_file(path)
        if fallback and fallback not in fallback_names:
            fallback_names.append(fallback)
    return {
        "state": "VERIFIED",
        "reason": "",
        "codex_home": codex_home.as_posix(),
        "max_bytes": max_bytes,
        "max_bytes_source": max_source,
        "instruction_file_names": fallback_names,
    }


def effective_project_doc_max_bytes(root: Path) -> int:
    config = effective_instruction_config(root)
    if config.get("state") != "VERIFIED" or not isinstance(config.get("max_bytes"), int):
        raise ReadinessError("PROJECT_INSTRUCTION_CONFIG_UNVERIFIED", str(config.get("reason") or "unknown"))
    return int(config["max_bytes"])


def _ancestor_dirs(root: Path, cwd: Path) -> list[Path]:
    root = root.resolve()
    cwd = cwd.resolve()
    try:
        rel = cwd.relative_to(root)
    except ValueError:
        return [root]
    dirs = [root]
    current = root
    for part in rel.parts:
        current = current / part
        dirs.append(current)
    return dirs


def discover_instruction_files(target: Path, *, cwd: Path | None = None) -> list[Path]:
    root = repo_root_or_target(target)
    effective_cwd = (cwd or target).resolve()
    config = effective_instruction_config(root)
    names = tuple(config["instruction_file_names"]) if config.get("state") == "VERIFIED" else INSTRUCTION_FILE_NAMES
    files: list[Path] = []
    for directory in _ancestor_dirs(root, effective_cwd):
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                files.append(candidate)
                break
    return files


def audit_instruction_budget(
    target: Path,
    *,
    cwd: Path | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    root = repo_root_or_target(target)
    config = effective_instruction_config(root)
    if config.get("state") != "VERIFIED":
        return {
            "schema": "ai-bridge.readiness.instruction_budget.v1",
            "state": "UNKNOWN",
            "reason": config.get("reason") or "PROJECT_INSTRUCTION_CONFIG_UNVERIFIED",
            "codex_home": config.get("codex_home"),
            "max_bytes": None,
            "max_bytes_source": None,
            "total_bytes": None,
            "truncated_at": None,
            "files": [],
        }
    limit = max_bytes or int(config["max_bytes"])
    bound_files = [_read_bound_text(path, root=root, label="project_instruction") for path in discover_instruction_files(root, cwd=cwd)]
    total = sum(item.size_bytes for item in bound_files)
    state = "PASS" if total <= limit else "FAIL"
    remaining = limit
    truncated_at: str | None = None
    for item in bound_files:
        if remaining >= item.size_bytes:
            remaining -= item.size_bytes
            continue
        truncated_at = item.relative_path
        break
    return {
        "schema": "ai-bridge.readiness.instruction_budget.v1",
        "state": state,
        "max_bytes": limit,
        "max_bytes_source": config["max_bytes_source"],
        "codex_home": config["codex_home"],
        "total_bytes": total,
        "truncated_at": truncated_at,
        "files": [
            {
                "path": item.relative_path,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in bound_files
        ],
    }


def validate_instruction_budget(target: Path, *, strict: bool = False) -> tuple[list[str], list[str]]:
    audit = audit_instruction_budget(target)
    if audit["state"] == "UNKNOWN":
        line = f"{'ERROR' if strict else 'WARN'} instruction budget unverified: {audit.get('reason')}"
        return [line], [line] if strict else []
    lines = [
        f"OK   instruction budget max_bytes={audit['max_bytes']} total_bytes={audit['total_bytes']}"
        if audit["state"] == "PASS"
        else (
            f"{'ERROR' if strict else 'WARN'} instruction budget exceeded: "
            f"max_bytes={audit['max_bytes']} total_bytes={audit['total_bytes']} truncated_at={audit['truncated_at']}"
        )
    ]
    errors = [] if audit["state"] == "PASS" or not strict else [lines[0]]
    for item in audit["files"]:
        lines.append(f"OK   instruction source {item['path']} bytes={item['size_bytes']} sha256={item['sha256']}")
    return lines, errors


def _safe_repo_rel(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or "." == value:
        raise ReadinessError("CONTROL_PATH_UNSAFE", value)
    return path.as_posix()


def bind_repo_texts(target: Path, specs: list[tuple[str, str]]) -> list[BoundText]:
    root = repo_root(target)
    bound: list[BoundText] = []
    for label, rel in specs:
        safe_rel = _safe_repo_rel(rel)
        path = root / safe_rel
        if not path.is_file():
            raise ReadinessError("MANDATORY_SOURCE_MISSING", safe_rel)
        bound.append(_read_bound_text(path, root=root, label=label))
    return bound


def bind_repo_texts_isolated(target: Path, specs: list[tuple[str, str]]) -> list[BoundText]:
    root = repo_root(target)
    commit = git_text(root, ["rev-parse", "HEAD"])
    expected_repo = _origin_identity(root)
    if expected_repo == "UNKNOWN":
        raise ReadinessError("CONTROL_ORIGIN_IDENTITY_UNVERIFIED")
    require_github_https = not expected_repo.startswith("local:/tmp/")
    bound: list[BoundText] = []
    for label, rel in specs:
        result = read_control_file_isolated(
            root,
            expected_repo=expected_repo,
            commit=commit,
            path=rel,
            require_github_https=require_github_https,
        )
        text = str(result["text"])
        raw = text.encode("utf-8")
        bound.append(
            BoundText(
                label=label,
                path=(root / rel).resolve(),
                relative_path=result["path"],
                size_bytes=int(result["size_bytes"]),
                sha256=str(result["sha256"]),
                text=text,
            )
        )
        if result["sha256"] != _sha256_bytes(raw):
            raise ReadinessError("CONTROL_TEXT_SHA_MISMATCH", rel)
    return bound


def _current_branch(root: Path) -> str:
    branch = git_text(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        raise ReadinessError("DETACHED_HEAD_NOT_READY")
    return branch


def _origin_identity(root: Path) -> str:
    result = _git(root, ["remote", "get-url", "--all", "origin"])
    urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(urls) != 1:
        raise ReadinessError("ORIGIN_URL_AMBIGUOUS")
    return _canonical_repo_identity(urls[0])


def _resolve_executable(name: str) -> str | None:
    path = Path(name).expanduser()
    if path.is_absolute() or "/" in name:
        return path.resolve().as_posix() if path.exists() and os.access(path, os.X_OK) else None
    found = shutil.which(name)
    return str(Path(found).resolve()) if found else None


def _codex_version(codex_bin: str) -> str:
    exe = _resolve_executable(codex_bin)
    if not exe:
        raise ReadinessError("CODEX_EXECUTABLE_UNRESOLVED", codex_bin)
    result = subprocess.run([exe, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise ReadinessError("CODEX_VERSION_UNAVAILABLE", (result.stderr or result.stdout).strip())
    output = (result.stdout or result.stderr or "").strip()
    return output or "UNKNOWN"


def managed_host_identity(target: Path, *, codex_bin: str) -> dict[str, Any]:
    root = repo_root(target)
    codex_home = resolve_codex_home()
    status = inspect_host_policy(codex_home, cwd=root)
    if status.overall_state != "configured":
        raise ReadinessError("HOST_POLICY_NOT_READY", status.overall_state)
    return {
        "codex_bin": _resolve_executable(codex_bin),
        "codex_version": _codex_version(codex_bin),
        "codex_home": codex_home.as_posix(),
        "host_policy_state": status.overall_state,
        "bridge_source": status.imported_package_source.as_posix(),
        "bridge_version": status.imported_package_version,
        "bridge_source_head": status.editable_source_head,
        "bridge_source_dirty_state": status.editable_source_dirty_state,
    }


def preflight_common(
    target: Path,
    *,
    expected_branch: str | None = None,
    require_clean: bool = False,
    codex_bin: str | None = None,
    require_host_ready: bool = False,
) -> dict[str, Any]:
    root = repo_root(target)
    branch = _current_branch(root)
    if expected_branch and branch != expected_branch:
        raise ReadinessError("BRANCH_NOT_READY", f"actual={branch} expected={expected_branch}")
    status = _git(root, ["status", "--porcelain=v1", "-uall"]).stdout
    if require_clean and status.strip():
        raise ReadinessError("DIRTY_WORKTREE_NOT_READY", status.strip())
    try:
        origin_identity = _origin_identity(root)
    except Exception:
        origin_identity = "UNKNOWN"
    instruction_budget = audit_instruction_budget(root, cwd=target)
    if instruction_budget["state"] == "UNKNOWN":
        raise ReadinessError("PROJECT_INSTRUCTION_CONFIG_UNVERIFIED", str(instruction_budget.get("reason") or "unknown"))
    result = {
        "root": root.as_posix(),
        "branch": branch,
        "head": git_text(root, ["rev-parse", "HEAD"]),
        "origin_identity": origin_identity,
        "dirty": bool(status.strip()),
        "dirty_status": status.strip(),
        "instruction_budget": instruction_budget,
    }
    if require_host_ready:
        result["managed_host"] = managed_host_identity(root, codex_bin=codex_bin or "codex")
    return result


def preflight_reviewed_event(
    target: Path,
    task_key: str,
    current: dict[str, Any],
    *,
    branch: str,
    codex_bin: str = "codex",
    require_host_ready: bool = True,
) -> dict[str, Any]:
    common = preflight_common(
        target,
        expected_branch=branch,
        require_clean=True,
        codex_bin=codex_bin,
        require_host_ready=require_host_ready,
    )
    state = current.get("state")
    specs = []
    if (repo_root(target) / "AGENTS.md").is_file():
        specs.append(("repo_agents", "AGENTS.md"))
    specs.extend([
        ("reviewed_readme", "automation/reviewed_handoff/README.md"),
        ("executor_prompt", "automation/reviewed_handoff/prompts/CODEX_EXECUTOR.md"),
        ("request", f"automation/reviewed_handoff/tasks/{task_key}/REQUEST.md"),
        ("plan", f"automation/reviewed_handoff/tasks/{task_key}/PLAN.md"),
        ("current", f"automation/reviewed_handoff/tasks/{task_key}/CURRENT.json"),
    ])
    if common["instruction_budget"]["state"] != "PASS":
        raise ReadinessError("PROJECT_INSTRUCTION_BUDGET_EXCEEDED")
    bound = bind_repo_texts_isolated(target, specs)
    try:
        current_from_disk = json.loads(bound[-1].text)
    except json.JSONDecodeError as exc:
        raise ReadinessError("CURRENT_JSON_INVALID") from exc
    if current_from_disk.get("task_key") != task_key:
        raise ReadinessError("CURRENT_TASK_KEY_MISMATCH")
    if current_from_disk.get("state") != state:
        raise ReadinessError("CURRENT_STATE_CHANGED_BEFORE_LAUNCH")
    return {**common, "task_key": task_key, "source_bindings": _binding_records(bound), "source_texts": bound}


def preflight_lite_task(
    target: Path,
    task_key: str,
    *,
    codex_bin: str = "codex",
    require_host_ready: bool = True,
) -> dict[str, Any]:
    common = preflight_common(target, codex_bin=codex_bin, require_host_ready=require_host_ready)
    specs = [
        ("repo_agents", "AGENTS.md"),
        ("agent_rules", "prompts/AGENT_RULES.md"),
        ("task", f"prompts/tasks/{task_key}.md"),
    ]
    if common["instruction_budget"]["state"] != "PASS":
        raise ReadinessError("PROJECT_INSTRUCTION_BUDGET_EXCEEDED")
    bound = bind_repo_texts_isolated(target, specs)
    return {**common, "task_key": task_key, "source_bindings": _binding_records(bound), "source_texts": bound}


def _binding_records(bound: list[BoundText]) -> list[dict[str, Any]]:
    return [
        {
            "label": item.label,
            "path": item.relative_path,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        }
        for item in bound
    ]


def format_bound_context(bound: list[BoundText]) -> str:
    sections: list[str] = []
    for item in bound:
        sections.append(
            "\n".join(
                [
                    f"### {item.label}: {item.relative_path}",
                    f"sha256: {item.sha256}",
                    f"size_bytes: {item.size_bytes}",
                    "",
                    item.text,
                ]
            )
        )
    return "\n\n".join(sections)


def _git_dir(root: Path) -> Path:
    raw = git_text(root, ["rev-parse", "--git-dir"])
    path = Path(raw)
    return path if path.is_absolute() else root / path


def protected_git_state(root: Path) -> dict[str, str | None]:
    git_dir = _git_dir(root)
    state: dict[str, str | None] = {}
    for rel in ["FETCH_HEAD", "index", "config"]:
        path = git_dir / rel
        state[rel] = _sha256_bytes(path.read_bytes()) if path.exists() and path.is_file() else None
    refs = git_dir / "refs"
    if refs.exists():
        digest = hashlib.sha256()
        for path in sorted(item for item in refs.rglob("*") if item.is_file()):
            digest.update(path.relative_to(git_dir).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        state["refs"] = digest.hexdigest()
    else:
        state["refs"] = None
    return state


def _active_replace_refs(root: Path) -> list[str]:
    result = _git(root, ["for-each-ref", "--format=%(refname)", "refs/replace"], check=False)
    if result.returncode != 0:
        raise ReadinessError("CONTROL_REPLACE_REF_CHECK_FAILED", (result.stderr or result.stdout).strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _active_graft_lines(root: Path) -> list[str]:
    raw = git_text(root, ["rev-parse", "--git-path", "info/grafts"])
    path = Path(raw)
    grafts = path if path.is_absolute() else root / path
    if not grafts.exists():
        return []
    try:
        lines = grafts.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReadinessError("CONTROL_GRAFT_CHECK_FAILED", grafts.as_posix()) from exc
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _reject_control_rewrite_refs(root: Path) -> None:
    replace_refs = _active_replace_refs(root)
    if replace_refs:
        raise ReadinessError("CONTROL_REPLACE_REFS_ACTIVE", ", ".join(replace_refs))
    graft_lines = _active_graft_lines(root)
    if graft_lines:
        raise ReadinessError("CONTROL_GRAFTS_ACTIVE")


def _reject_control_git_environment(env: dict[str, str]) -> None:
    for key in env:
        if key in REJECTED_GIT_ENV_EXACT or key.startswith(REJECTED_GIT_ENV_PREFIXES):
            raise ReadinessError("CONTROL_GIT_ENV_UNSAFE", key)


def _reject_control_git_config(root: Path) -> None:
    result = _git(root, ["config", "--local", "--name-only", "--list"], check=False)
    if result.returncode != 0:
        raise ReadinessError("CONTROL_GIT_CONFIG_UNREADABLE", (result.stderr or result.stdout).strip())
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
    for raw in result.stdout.splitlines():
        key = raw.strip().lower()
        if not key:
            continue
        if key in unsafe_exact or key.startswith(unsafe_prefixes):
            raise ReadinessError("CONTROL_GIT_CONFIG_UNSAFE", key)


def read_control_file_isolated(
    target: Path,
    *,
    expected_repo: str,
    commit: str,
    path: str,
    require_github_https: bool = True,
) -> dict[str, Any]:
    root = repo_root(target)
    safe_path = _safe_repo_rel(path)
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit or ""):
        raise ReadinessError("CONTROL_COMMIT_INVALID")
    _reject_control_git_environment(os.environ)
    _reject_control_git_config(root)
    fetch_url = git_text(root, ["remote", "get-url", "origin"])
    identity = _publisher_github_https_identity(fetch_url) if require_github_https else _canonical_repo_identity(fetch_url)
    if identity != expected_repo:
        raise ReadinessError("CONTROL_REPO_IDENTITY_MISMATCH", identity)
    _reject_control_rewrite_refs(root)
    before = protected_git_state(root)
    original_objects = git_text(root, ["rev-parse", "--git-path", "objects"])
    original_objects_path = Path(original_objects)
    if not original_objects_path.is_absolute():
        original_objects_path = root / original_objects_path
    with tempfile.TemporaryDirectory(prefix="ai-bridge-objects-") as tmp:
        env = os.environ.copy()
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_OBJECT_DIRECTORY"] = tmp
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = original_objects_path.resolve().as_posix()
        env["GIT_NO_REPLACE_OBJECTS"] = "1"
        _git(root, ["cat-file", "-e", f"{commit}^{{commit}}"], env=env)
        blob_oid = git_text(root, ["rev-parse", f"{commit}:{safe_path}"], env=env)
        blob_type = git_text(root, ["cat-file", "-t", blob_oid], env=env)
        if blob_type != "blob":
            raise ReadinessError("CONTROL_PATH_NOT_BLOB", safe_path)
        result = _git(root, ["cat-file", "-p", blob_oid], env=env)
        content = result.stdout.encode("utf-8")
        object_files = sorted(str(path.relative_to(tmp)) for path in Path(tmp).rglob("*") if path.is_file())
    after = protected_git_state(root)
    if before != after:
        raise ReadinessError("PROTECTED_GIT_STATE_CHANGED")
    return {
        "schema": "ai-bridge.readiness.control_file.v1",
        "repo": identity,
        "commit": commit,
        "path": safe_path,
        "blob_oid": blob_oid,
        "sha256": _sha256_bytes(content),
        "size_bytes": len(content),
        "text": content.decode("utf-8"),
        "protected_git_state_unchanged": True,
        "isolated_object_file_count": len(object_files),
    }
