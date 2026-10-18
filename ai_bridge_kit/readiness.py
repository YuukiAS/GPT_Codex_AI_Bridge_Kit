from __future__ import annotations

import hashlib
import ast
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.9 CI
    tomllib = None  # type: ignore[assignment]

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
DEFAULT_PROJECT_ROOT_MARKERS = (".git",)
BRIDGE_MANAGED_BLOCK_CAPS = {
    "core": 2048,
    "persistent_run": 4096,
    "overleaf": 2048,
}
BRIDGE_MANAGED_BLOCK_MARKERS = {
    "core": (b"<!-- ai-bridge-kit:start -->", b"<!-- ai-bridge-kit:end -->"),
    "persistent_run": (b"<!-- ai-bridge-kit:persistent-run:start -->", b"<!-- ai-bridge-kit:persistent-run:end -->"),
    "overleaf": (b"<!-- ai-bridge-kit:overleaf:start -->", b"<!-- ai-bridge-kit:overleaf:end -->"),
}


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


def bounded_effect_identity(effect_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Create a comparable scope identity; this digest never grants authority."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", effect_type or ""):
        raise ReadinessError("BOUNDED_EFFECT_TYPE_INVALID", effect_type)
    normalized: dict[str, str] = {}
    for key, value in sorted(fields.items()):
        if key in {"authorized", "approved", "authority"}:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key or ""):
            raise ReadinessError("BOUNDED_EFFECT_FIELD_INVALID", key)
        text_value = str(value).strip()
        if not text_value:
            raise ReadinessError("BOUNDED_EFFECT_FIELD_EMPTY", key)
        normalized[key] = text_value
    if not normalized:
        raise ReadinessError("BOUNDED_EFFECT_FIELDS_REQUIRED", effect_type)
    human = "\n".join([f"effect={effect_type}", *[f"{key}={value}" for key, value in normalized.items()]])
    return {
        "schema": "ai-bridge.authorization.effect.v1",
        "effect_type": effect_type,
        "fields": normalized,
        "human_readable": human,
        "sha256": _sha256_bytes(human.encode("utf-8")),
        "grants_authority": False,
    }


def verify_bounded_effect(expected_sha256: str, effect_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    actual = bounded_effect_identity(effect_type, fields)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or "") or actual["sha256"] != expected_sha256:
        raise ReadinessError(
            "BOUNDED_EFFECT_SCOPE_MISMATCH",
            f"expected={expected_sha256 or 'missing'} actual={actual['sha256']}",
        )
    return actual


def authorization_continuity(
    previous_effect_sha256: str | None,
    effect_type: str,
    fields: dict[str, Any],
    *,
    current_thread_or_session_proven: bool,
) -> dict[str, Any]:
    effect = bounded_effect_identity(effect_type, fields)
    reusable = bool(
        current_thread_or_session_proven
        and previous_effect_sha256
        and previous_effect_sha256 == effect["sha256"]
    )
    return {
        "decision": "REUSE_CURRENT_SCOPE" if reusable else "PROMPT_REQUIRED",
        "reason": "exact_effect_and_lifetime_match" if reusable else "effect_or_lifetime_not_proven",
        "effect": effect,
        "persistent_authorization_store": False,
    }


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


def _git_bytes(
    cwd: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or b"git failed").decode("utf-8", errors="replace").strip()
        raise ReadinessError("GIT_COMMAND_FAILED", detail)
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


def _minimal_toml_loads(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current: dict[str, Any] = data
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            section = stripped.strip("[]").strip()
            current = data
            for part in _split_toml_dotted_key(section):
                current = current.setdefault(part, {})
            continue
        key, sep, value = stripped.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if "#" in value:
            value = value.split("#", 1)[0].rstrip()
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        current[key] = parsed
    return data


def _split_toml_dotted_key(value: str) -> list[str]:
    parts: list[str] = []
    current = ""
    quote: str | None = None
    escaped = False
    for char in value:
        if quote:
            current += char
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current += char
        elif char == ".":
            parts.append(_toml_key_part(current.strip()))
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(_toml_key_part(current.strip()))
    return parts


def _toml_key_part(value: str) -> str:
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        try:
            return str(ast.literal_eval(value))
        except Exception:
            return value[1:-1]
    return value


def _load_toml_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return {}
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        if tomllib is not None:
            return tomllib.loads(raw.decode("utf-8"))
        return _minimal_toml_loads(raw.decode("utf-8"))
    except Exception:
        return None


def _candidate_filenames(config: dict[str, Any]) -> list[str]:
    names = list(INSTRUCTION_FILE_NAMES)
    fallback = config.get("project_doc_fallback_filenames", [])
    if not isinstance(fallback, list):
        return names
    for item in fallback:
        if not isinstance(item, str) or not item:
            continue
        if item in {".", ".."} or "/" in item or "\0" in item or "\\" in item or ":" in item:
            continue
        if item not in names:
            names.append(item)
    return names


def _project_root_markers(config: dict[str, Any]) -> tuple[str, ...] | None:
    raw = config.get("project_root_markers")
    if raw is None:
        return DEFAULT_PROJECT_ROOT_MARKERS
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(item for item in raw if item)
    return None


def _find_instruction_root(cwd: Path, markers: tuple[str, ...]) -> Path:
    cwd = cwd.resolve()
    if not markers:
        return cwd
    cursor = cwd
    while True:
        if any((cursor / marker).exists() for marker in markers):
            return cursor
        if cursor.parent == cursor:
            return cwd
        cursor = cursor.parent


def _project_trust_state(config: dict[str, Any], root: Path) -> str:
    projects = config.get("projects")
    if not isinstance(projects, dict):
        return "UNKNOWN"
    root_resolved = root.resolve()
    best: tuple[int, str] | None = None
    for raw_path, value in projects.items():
        if not isinstance(raw_path, str) or not isinstance(value, dict):
            continue
        try:
            project_path = Path(raw_path).expanduser().resolve()
            root_resolved.relative_to(project_path)
        except Exception:
            continue
        trust = value.get("trust_level") or value.get("trusted")
        trust_text = str(trust).lower()
        if trust_text in {"trusted", "true", "yes"}:
            state = "TRUSTED"
        elif trust_text in {"untrusted", "false", "no"}:
            state = "UNTRUSTED"
        else:
            state = "UNKNOWN"
        score = len(project_path.parts)
        if best is None or score > best[0]:
            best = (score, state)
    return best[1] if best else "UNKNOWN"


def _merge_config(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def effective_instruction_config(root: Path, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    active_env = os.environ if env is None else env
    codex_home = resolve_codex_home(None, active_env)
    codex_config_path = codex_home / "config.toml"
    project_config_path = root / ".codex" / "config.toml"
    codex_config = _load_toml_config(codex_config_path)
    project_config = _load_toml_config(project_config_path)
    if codex_config is None:
        return {
            "state": "UNKNOWN",
            "reason": f"CONFIG_SOURCE_UNREADABLE_OR_INVALID: {codex_config_path}",
            "codex_home": codex_home.as_posix(),
            "max_bytes": None,
            "max_bytes_source": None,
            "instruction_file_names": list(INSTRUCTION_FILE_NAMES),
        }
    if project_config is None:
        return {
            "state": "UNKNOWN",
            "reason": f"CONFIG_SOURCE_UNREADABLE_OR_INVALID: {project_config_path}",
            "codex_home": codex_home.as_posix(),
            "max_bytes": None,
            "max_bytes_source": None,
            "instruction_file_names": list(INSTRUCTION_FILE_NAMES),
        }
    trust_state = _project_trust_state(codex_config, root)
    if trust_state != "TRUSTED":
        return {
            "state": "UNKNOWN",
            "reason": f"PROJECT_TRUST_NOT_VERIFIED: {trust_state}",
            "codex_home": codex_home.as_posix(),
            "project_trust_state": trust_state,
            "max_bytes": None,
            "max_bytes_source": None,
            "instruction_file_names": list(INSTRUCTION_FILE_NAMES),
        }
    root_markers = _project_root_markers(codex_config)
    if root_markers is None:
        return {
            "state": "UNKNOWN",
            "reason": "PROJECT_ROOT_MARKERS_INVALID",
            "codex_home": codex_home.as_posix(),
            "max_bytes": None,
            "max_bytes_source": None,
            "instruction_file_names": list(INSTRUCTION_FILE_NAMES),
        }
    merged = _merge_config(codex_config, project_config)
    max_bytes = merged.get("project_doc_max_bytes", DEFAULT_PROJECT_DOC_MAX_BYTES)
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        return {
            "state": "UNKNOWN",
            "reason": "CONFIG_PROJECT_DOC_MAX_BYTES_INVALID",
            "codex_home": codex_home.as_posix(),
            "max_bytes": None,
            "max_bytes_source": None,
            "instruction_file_names": list(INSTRUCTION_FILE_NAMES),
        }
    max_source = "default"
    if "project_doc_max_bytes" in project_config:
        max_source = f"project:{project_config_path.as_posix()}"
    elif "project_doc_max_bytes" in codex_config:
        max_source = f"codex_home:{codex_config_path.as_posix()}"
    fallback_names = _candidate_filenames(merged)
    instruction_root = _find_instruction_root(cwd or root, root_markers)
    return {
        "state": "VERIFIED",
        "reason": "",
        "codex_home": codex_home.as_posix(),
        "project_trust_state": trust_state,
        "project_root": instruction_root.as_posix(),
        "project_root_markers": list(root_markers),
        "max_bytes": max_bytes,
        "max_bytes_source": max_source,
        "instruction_file_names": fallback_names,
    }


def effective_project_doc_max_bytes(root: Path) -> int:
    config = effective_instruction_config(root)
    if config.get("state") != "VERIFIED" or not isinstance(config.get("max_bytes"), int):
        raise ReadinessError("PROJECT_INSTRUCTION_CONFIG_UNVERIFIED", str(config.get("reason") or "unknown"))
    return int(config["max_bytes"])


def _instruction_budget_config(root: Path, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve native instruction byte settings without treating trust as authority.

    Project trust controls whether Codex consumes project instructions.  It does
    not change the configured byte ceiling, so managed writers can and must
    preflight the projected bytes even before a project has been trusted.
    """
    active_env = os.environ if env is None else env
    codex_home = resolve_codex_home(None, active_env)
    codex_path = codex_home / "config.toml"
    project_path = root / ".codex" / "config.toml"
    codex_config = _load_toml_config(codex_path)
    project_config = _load_toml_config(project_path)
    if codex_config is None or project_config is None:
        bad = codex_path if codex_config is None else project_path
        raise ReadinessError("PROJECT_INSTRUCTION_CONFIG_UNVERIFIED", bad.as_posix())
    merged = _merge_config(codex_config, project_config)
    limit = merged.get("project_doc_max_bytes", DEFAULT_PROJECT_DOC_MAX_BYTES)
    if not isinstance(limit, int) or limit <= 0:
        raise ReadinessError("CONFIG_PROJECT_DOC_MAX_BYTES_INVALID")
    markers = _project_root_markers(codex_config)
    if markers is None:
        raise ReadinessError("PROJECT_ROOT_MARKERS_INVALID")
    source = "default"
    if "project_doc_max_bytes" in project_config:
        source = f"project:{project_path.as_posix()}"
    elif "project_doc_max_bytes" in codex_config:
        source = f"codex_home:{codex_path.as_posix()}"
    return {
        "max_bytes": limit,
        "max_bytes_source": source,
        "instruction_file_names": _candidate_filenames(merged),
        "project_root_markers": markers,
    }


def projected_root_agents_budget(
    target: Path,
    projected_agents: bytes,
    *,
    block_name: str,
    block_bytes: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return the native-discovery byte projection for a root AGENTS mutation."""
    if block_name not in BRIDGE_MANAGED_BLOCK_CAPS:
        raise ReadinessError("BRIDGE_MANAGED_INSTRUCTION_BLOCK_UNKNOWN", block_name)
    cap = BRIDGE_MANAGED_BLOCK_CAPS[block_name]
    if block_bytes > cap:
        raise ReadinessError(
            "BRIDGE_MANAGED_INSTRUCTION_BLOCK_OVER_CAP",
            f"block={block_name} bytes={block_bytes} cap={cap}",
        )
    root = target.expanduser().resolve()
    config = _instruction_budget_config(root, env=env)
    names = tuple(config["instruction_file_names"])
    instruction_root = _find_instruction_root(root, tuple(config["project_root_markers"]))
    sources: list[dict[str, Any]] = []
    remaining = int(config["max_bytes"])
    truncated_at: str | None = None
    projected_total = 0
    for directory in _ancestor_dirs(instruction_root, root):
        selected: Path | None = None
        raw: bytes | None = None
        for name in names:
            candidate = directory / name
            if candidate == root / "AGENTS.md":
                selected = candidate
                raw = projected_agents
                break
            if candidate.is_file():
                selected = candidate
                raw = candidate.read_bytes()
                break
        if selected is None or raw is None:
            continue
        size = len(raw)
        projected_total += size
        relative = _repo_relative(selected, root)
        sources.append({"path": relative, "size_bytes": size})
        if truncated_at is None and size > remaining:
            truncated_at = relative
        remaining -= min(remaining, size)
    managed_blocks: dict[str, int] = {}
    for name, (begin, end) in BRIDGE_MANAGED_BLOCK_MARKERS.items():
        start = projected_agents.find(begin)
        finish = projected_agents.find(end, start + len(begin)) if start >= 0 else -1
        managed_blocks[name] = 0 if start < 0 or finish < 0 else finish + len(end) - start
    user_owned_bytes = max(0, len(projected_agents) - sum(managed_blocks.values()))
    overflow = max(0, projected_total - int(config["max_bytes"]))
    return {
        "schema": "ai-bridge.readiness.projected_instruction_budget.v1",
        "state": "FAIL" if overflow or truncated_at else "PASS",
        "block": block_name,
        "block_bytes": block_bytes,
        "block_cap": cap,
        "bridge_block_bytes": managed_blocks,
        "user_owned_bytes": user_owned_bytes,
        "projected_total_bytes": projected_total,
        "max_bytes": int(config["max_bytes"]),
        "max_bytes_source": config["max_bytes_source"],
        "first_projected_truncation_source": truncated_at,
        "bytes_to_release": overflow,
        "sources": sources,
    }


def preflight_root_agents_mutation(
    target: Path,
    projected_agents: bytes,
    *,
    block_name: str,
    block_bytes: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    projection = projected_root_agents_budget(
        target,
        projected_agents,
        block_name=block_name,
        block_bytes=block_bytes,
        env=env,
    )
    if projection["state"] != "PASS":
        raise ReadinessError(
            "BRIDGE_MANAGED_INSTRUCTION_PROJECTED_OVERFLOW",
            " ".join(
                [
                    f"user_owned_bytes={projection['user_owned_bytes']}",
                    f"block={projection['block']}",
                    f"block_bytes={projection['block_bytes']}",
                    f"bridge_block_bytes={json.dumps(projection['bridge_block_bytes'], sort_keys=True, separators=(',', ':'))}",
                    f"projected_total={projection['projected_total_bytes']}",
                    f"limit={projection['max_bytes']}",
                    f"truncated_at={projection['first_projected_truncation_source']}",
                    f"bytes_to_release={projection['bytes_to_release']}",
                ]
            ),
        )
    return projection


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
    config = effective_instruction_config(root, cwd=effective_cwd)
    names = tuple(config["instruction_file_names"]) if config.get("state") == "VERIFIED" else INSTRUCTION_FILE_NAMES
    instruction_root = Path(config.get("project_root") or root)
    files: list[Path] = []
    for directory in _ancestor_dirs(instruction_root, effective_cwd):
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
    config = effective_instruction_config(root, cwd=cwd or target)
    if config.get("state") != "VERIFIED":
        return {
            "schema": "ai-bridge.readiness.instruction_budget.v1",
            "state": "UNKNOWN",
            "reason": config.get("reason") or "PROJECT_INSTRUCTION_CONFIG_UNVERIFIED",
            "codex_home": config.get("codex_home"),
            "project_trust_state": config.get("project_trust_state"),
            "project_root": config.get("project_root"),
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
        "project_trust_state": config["project_trust_state"],
        "project_root": config["project_root"],
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


def bind_repo_texts_isolated(
    target: Path,
    specs: list[tuple[str, str]],
    *,
    require_github_https: bool = True,
) -> list[BoundText]:
    root = repo_root(target)
    commit = git_text(root, ["rev-parse", "HEAD"])
    expected_repo = _origin_identity(root)
    if expected_repo == "UNKNOWN":
        raise ReadinessError("CONTROL_ORIGIN_IDENTITY_UNVERIFIED")
    bound: list[BoundText] = []
    for label, rel in specs:
        safe_rel = _safe_repo_rel(rel)
        worktree_path = _require_worktree_source_file(root, safe_rel)
        try:
            result = read_control_file_isolated(
                root,
                expected_repo=expected_repo,
                commit=commit,
                path=safe_rel,
                require_github_https=require_github_https,
            )
        except ReadinessError as exc:
            if exc.code == "CONTROL_PATH_NOT_IN_COMMIT":
                raise ReadinessError("MANDATORY_SOURCE_NOT_FROZEN", safe_rel) from exc
            raise
        _assert_mandatory_source_clean_at_head(root, safe_rel)
        text = str(result["text"])
        raw_sha = str(result["sha256"])
        bound.append(
            BoundText(
                label=label,
                path=worktree_path.resolve(),
                relative_path=result["path"],
                size_bytes=int(result["size_bytes"]),
                sha256=raw_sha,
                text=text,
            )
        )
    return bound


def _require_worktree_source_file(root: Path, safe_rel: str) -> Path:
    path = root / safe_rel
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ReadinessError("MANDATORY_SOURCE_MISSING", safe_rel) from exc
    if not stat.S_ISREG(mode):
        raise ReadinessError("MANDATORY_SOURCE_NOT_REGULAR", safe_rel)
    return path


def _assert_mandatory_source_clean_at_head(root: Path, safe_rel: str) -> None:
    _reject_mandatory_source_index_flags(root, safe_rel)
    _reject_mandatory_source_transforms(root, safe_rel)
    diff = _git(root, ["diff", "--no-ext-diff", "--quiet", "HEAD", "--", safe_rel], check=False)
    if diff.returncode == 1:
        raise ReadinessError("MANDATORY_SOURCE_WORKTREE_MISMATCH", safe_rel)
    if diff.returncode != 0:
        raise ReadinessError("MANDATORY_SOURCE_DIFF_FAILED", (diff.stderr or diff.stdout).strip())


def _reject_mandatory_source_index_flags(root: Path, safe_rel: str) -> None:
    result = _git_bytes(
        root,
        ["--literal-pathspecs", "ls-files", "-v", "-z", "--", safe_rel],
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"git ls-files failed").decode("utf-8", errors="replace").strip()
        raise ReadinessError("MANDATORY_SOURCE_INDEX_CHECK_FAILED", detail)
    records = [record for record in result.stdout.split(b"\0") if record]
    if len(records) != 1 or len(records[0]) < 3 or records[0][1:2] != b" ":
        raise ReadinessError("MANDATORY_SOURCE_INDEX_ENTRY_INVALID", safe_rel)
    tag = records[0][:1]
    entry_path = records[0][2:]
    if entry_path != os.fsencode(safe_rel):
        raise ReadinessError("MANDATORY_SOURCE_INDEX_ENTRY_INVALID", safe_rel)
    flags: list[str] = []
    if tag.decode("ascii", errors="ignore").islower():
        flags.append("assume-unchanged")
    if tag in {b"S", b"s"}:
        flags.append("skip-worktree")
    if flags:
        raise ReadinessError("MANDATORY_SOURCE_INDEX_FLAGS_UNSAFE", f"{safe_rel}: {','.join(flags)}")


def _reject_mandatory_source_transforms(root: Path, safe_rel: str) -> None:
    result = _git_bytes(
        root,
        ["check-attr", "-z", "filter", "ident", "working-tree-encoding", "--", safe_rel],
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"git check-attr failed").decode("utf-8", errors="replace").strip()
        raise ReadinessError("MANDATORY_SOURCE_ATTRIBUTE_CHECK_FAILED", detail)
    parts = result.stdout.split(b"\0")
    for index in range(0, max(0, len(parts) - 1), 3):
        if index + 2 >= len(parts):
            break
        _path, attr, value = parts[index : index + 3]
        if value in {b"", b"unspecified", b"unset", b"false"}:
            continue
        name = attr.decode("utf-8", errors="replace")
        rendered = value.decode("utf-8", errors="replace")
        raise ReadinessError("MANDATORY_SOURCE_GIT_ATTRIBUTE_UNSAFE", f"{safe_rel}: {name}={rendered}")


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
    require_github_https: bool = True,
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
    bound = bind_repo_texts_isolated(target, specs, require_github_https=require_github_https)
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
    require_github_https: bool = True,
) -> dict[str, Any]:
    common = preflight_common(target, codex_bin=codex_bin, require_host_ready=require_host_ready)
    specs = [
        ("repo_agents", "AGENTS.md"),
        ("agent_rules", "prompts/AGENT_RULES.md"),
        ("task", f"prompts/tasks/{task_key}.md"),
    ]
    if common["instruction_budget"]["state"] != "PASS":
        raise ReadinessError("PROJECT_INSTRUCTION_BUDGET_EXCEEDED")
    bound = bind_repo_texts_isolated(target, specs, require_github_https=require_github_https)
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


def protected_git_objects_state(root: Path) -> dict[str, str | None]:
    objects = git_text(root, ["rev-parse", "--git-path", "objects"])
    objects_path = Path(objects)
    if not objects_path.is_absolute():
        objects_path = root / objects_path
    if not objects_path.exists():
        return {"objects": None}
    digest = hashlib.sha256()
    for path in sorted(item for item in objects_path.rglob("*") if item.is_file()):
        rel = path.relative_to(objects_path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_bytes(path.read_bytes()).encode("ascii"))
        digest.update(b"\0")
    return {"objects": digest.hexdigest()}


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
    isolated_state_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root(target)
    safe_path = _safe_repo_rel(path)
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit or ""):
        raise ReadinessError("CONTROL_COMMIT_INVALID")
    _reject_control_git_environment(os.environ)
    _reject_control_git_config(root)
    fetch_url = git_text(root, ["remote", "get-url", "origin"])
    try:
        identity = _publisher_github_https_identity(fetch_url) if require_github_https else _canonical_repo_identity(fetch_url)
    except Exception as exc:
        raise ReadinessError("CONTROL_REPO_IDENTITY_UNVERIFIED", str(exc)) from exc
    if identity != expected_repo:
        raise ReadinessError("CONTROL_REPO_IDENTITY_MISMATCH", identity)
    _reject_control_rewrite_refs(root)
    before = protected_git_state(root)
    before_objects = protected_git_objects_state(root)
    original_objects = git_text(root, ["rev-parse", "--git-path", "objects"])
    original_objects_path = Path(original_objects)
    if not original_objects_path.is_absolute():
        original_objects_path = root / original_objects_path
    state_root = isolated_state_root or Path(os.environ.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser() / "readiness" / "objects"
    state_root = state_root.resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-bridge-objects-", dir=state_root) as tmp:
        env = os.environ.copy()
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_OBJECT_DIRECTORY"] = tmp
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = original_objects_path.resolve().as_posix()
        env["GIT_NO_REPLACE_OBJECTS"] = "1"
        _git(root, ["cat-file", "-e", f"{commit}^{{commit}}"], env=env)
        tree_entry = _git_bytes(root, ["ls-tree", "-z", commit, "--", safe_path], env=env)
        if not tree_entry.stdout:
            raise ReadinessError("CONTROL_PATH_NOT_IN_COMMIT", safe_path)
        entry = tree_entry.stdout.rstrip(b"\0")
        header, sep, entry_path = entry.partition(b"\t")
        if not sep:
            raise ReadinessError("CONTROL_TREE_ENTRY_INVALID", safe_path)
        fields = header.split()
        if len(fields) != 3:
            raise ReadinessError("CONTROL_TREE_ENTRY_INVALID", safe_path)
        mode, tree_type, raw_oid = fields
        if entry_path.decode("utf-8", errors="replace") != safe_path:
            raise ReadinessError("CONTROL_TREE_ENTRY_INVALID", safe_path)
        if mode not in {b"100644", b"100755"}:
            if mode == b"120000":
                raise ReadinessError("CONTROL_PATH_SYMLINK", safe_path)
            if mode == b"160000":
                raise ReadinessError("CONTROL_PATH_SUBMODULE", safe_path)
            raise ReadinessError("CONTROL_PATH_NOT_REGULAR_FILE", safe_path)
        if tree_type != b"blob":
            raise ReadinessError("CONTROL_PATH_NOT_BLOB", safe_path)
        blob_oid = raw_oid.decode("ascii")
        blob_type = git_text(root, ["cat-file", "-t", blob_oid], env=env)
        if blob_type != "blob":
            raise ReadinessError("CONTROL_PATH_NOT_BLOB", safe_path)
        expected_size = int(git_text(root, ["cat-file", "-s", blob_oid], env=env))
        result = _git_bytes(root, ["cat-file", "-p", blob_oid], env=env)
        content = result.stdout
        if len(content) != expected_size:
            raise ReadinessError("CONTROL_BLOB_SIZE_MISMATCH", safe_path)
        object_files = sorted(str(path.relative_to(tmp)) for path in Path(tmp).rglob("*") if path.is_file())
    after = protected_git_state(root)
    if before != after:
        raise ReadinessError("PROTECTED_GIT_STATE_CHANGED")
    after_objects = protected_git_objects_state(root)
    if before_objects != after_objects:
        raise ReadinessError("PROTECTED_GIT_OBJECTS_CHANGED")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReadinessError("CONTROL_TEXT_NOT_UTF8", safe_path) from exc
    return {
        "schema": "ai-bridge.readiness.control_file.v1",
        "repo": identity,
        "commit": commit,
        "path": safe_path,
        "blob_oid": blob_oid,
        "sha256": _sha256_bytes(content),
        "size_bytes": len(content),
        "text": text,
        "protected_git_state_unchanged": True,
        "protected_git_objects_unchanged": True,
        "isolated_object_file_count": len(object_files),
    }
