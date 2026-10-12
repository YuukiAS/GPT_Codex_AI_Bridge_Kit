from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .host import _canonical_repo_identity, _publisher_github_https_identity


DEFAULT_PROJECT_DOC_MAX_BYTES = 32768
INSTRUCTION_FILE_NAMES = ("AGENTS.override.md", "AGENTS.md")


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


def _parse_project_doc_max_bytes(config: Path) -> int | None:
    if not config.exists():
        return None
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"(?m)^\s*project_doc_max_bytes\s*=\s*(\d+)\s*$", text)
    if not match:
        return None
    return int(match.group(1))


def effective_project_doc_max_bytes(root: Path) -> int:
    configured = _parse_project_doc_max_bytes(root / ".codex" / "config.toml")
    return configured if configured and configured > 0 else DEFAULT_PROJECT_DOC_MAX_BYTES


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
    files: list[Path] = []
    for directory in _ancestor_dirs(root, effective_cwd):
        for name in INSTRUCTION_FILE_NAMES:
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
    limit = max_bytes or effective_project_doc_max_bytes(root)
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


def preflight_common(target: Path, *, expected_branch: str | None = None, require_clean: bool = False) -> dict[str, Any]:
    root = repo_root(target)
    branch = _current_branch(root)
    if expected_branch and branch != expected_branch:
        raise ReadinessError("BRANCH_NOT_READY", f"actual={branch} expected={expected_branch}")
    status = _git(root, ["status", "--porcelain=v1", "-uall"]).stdout
    if require_clean and status.strip():
        raise ReadinessError("DIRTY_WORKTREE_NOT_READY", status.strip())
    try:
        origin_identity = _origin_identity(root)
    except ReadinessError:
        origin_identity = "UNKNOWN"
    return {
        "root": root.as_posix(),
        "branch": branch,
        "head": git_text(root, ["rev-parse", "HEAD"]),
        "origin_identity": origin_identity,
        "dirty": bool(status.strip()),
        "dirty_status": status.strip(),
        "instruction_budget": audit_instruction_budget(root),
    }


def preflight_reviewed_event(target: Path, task_key: str, current: dict[str, Any], *, branch: str) -> dict[str, Any]:
    common = preflight_common(target, expected_branch=branch, require_clean=True)
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
    bound = bind_repo_texts(target, specs)
    try:
        current_from_disk = json.loads(bound[-1].text)
    except json.JSONDecodeError as exc:
        raise ReadinessError("CURRENT_JSON_INVALID") from exc
    if current_from_disk.get("task_key") != task_key:
        raise ReadinessError("CURRENT_TASK_KEY_MISMATCH")
    if current_from_disk.get("state") != state:
        raise ReadinessError("CURRENT_STATE_CHANGED_BEFORE_LAUNCH")
    if common["instruction_budget"]["state"] != "PASS":
        raise ReadinessError("PROJECT_INSTRUCTION_BUDGET_EXCEEDED")
    return {**common, "task_key": task_key, "source_bindings": _binding_records(bound), "source_texts": bound}


def preflight_lite_task(target: Path, task_key: str) -> dict[str, Any]:
    common = preflight_common(target)
    specs = [
        ("repo_agents", "AGENTS.md"),
        ("agent_rules", "prompts/AGENT_RULES.md"),
        ("task", f"prompts/tasks/{task_key}.md"),
    ]
    bound = bind_repo_texts(target, specs)
    if common["instruction_budget"]["state"] != "PASS":
        raise ReadinessError("PROJECT_INSTRUCTION_BUDGET_EXCEEDED")
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
    fetch_url = git_text(root, ["remote", "get-url", "origin"])
    identity = _publisher_github_https_identity(fetch_url) if require_github_https else _canonical_repo_identity(fetch_url)
    if identity != expected_repo:
        raise ReadinessError("CONTROL_REPO_IDENTITY_MISMATCH", identity)
    before = protected_git_state(root)
    original_objects = git_text(root, ["rev-parse", "--git-path", "objects"])
    original_objects_path = Path(original_objects)
    if not original_objects_path.is_absolute():
        original_objects_path = root / original_objects_path
    with tempfile.TemporaryDirectory(prefix="ai-bridge-objects-") as tmp:
        env = os.environ.copy()
        env["GIT_OBJECT_DIRECTORY"] = tmp
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = original_objects_path.resolve().as_posix()
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
