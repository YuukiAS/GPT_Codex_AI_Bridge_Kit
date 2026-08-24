from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on older runtimes
    tomllib = None  # type: ignore[assignment]


CONFIG_SCHEMA_VERSION = 1
CONNECTION_SCHEMA = "AI_BRIDGE_OVERLEAF_CONNECTION_V1"
REMOTE_BRANCH = "master"
OVERLEAF_BEGIN_MARKER = "<!-- ai-bridge-kit:overleaf:start -->"
OVERLEAF_END_MARKER = "<!-- ai-bridge-kit:overleaf:end -->"
SECRET_KEY_RE = re.compile(r"(token|password|secret|credential)", re.IGNORECASE)


class OverleafError(ValueError):
    pass


@dataclass(frozen=True)
class OverleafConfig:
    target: Path
    paper_root: PurePosixPath
    main_document: PurePosixPath
    remote_branch: str
    exclude_paths: tuple[PurePosixPath, ...]

    @property
    def paper_root_path(self) -> Path:
        return self.target / self.paper_root.as_posix()

    @property
    def main_document_path(self) -> Path:
        return self.paper_root_path / self.main_document.as_posix()


@dataclass(frozen=True)
class Projection:
    files: dict[str, bytes]

    @property
    def digest(self) -> str:
        hasher = hashlib.sha256()
        hasher.update(b"AI_BRIDGE_OVERLEAF_DIGEST_V1\0")
        for rel in sorted(self.files):
            data = self.files[rel]
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(str(len(data)).encode("ascii"))
            hasher.update(b"\0")
            hasher.update(data)
            hasher.update(b"\0")
        return hasher.hexdigest()

    @property
    def paths(self) -> list[str]:
        return sorted(self.files)


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_git(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise OverleafError(message)
    return result


def git_output(cwd: Path, args: list[str]) -> str:
    return run_git(cwd, args).stdout.strip()


def ensure_git_repo(target: Path) -> Path:
    try:
        root = git_output(target, ["rev-parse", "--show-toplevel"])
    except Exception as exc:
        raise OverleafError(f"target is not inside a Git repository: {target}") from exc
    return Path(root).resolve()


def config_path(target: Path) -> Path:
    return target / "automation" / "overleaf" / "config.toml"


def overleaf_root(target: Path) -> Path:
    return target / "automation" / "overleaf"


def _safe_posix_path(raw: str, *, label: str, allow_dot: bool = False) -> PurePosixPath:
    value = str(raw or "").replace("\\", "/").strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise OverleafError(f"{label} must be relative and must not contain '..'")
    if not allow_dot and (value == "." or not path.parts):
        raise OverleafError(f"{label} must not be '.'")
    return path


def _relative_to_paper(path: PurePosixPath, paper_root: PurePosixPath) -> PurePosixPath:
    paper_parts = paper_root.parts
    if path.parts[: len(paper_parts)] == paper_parts:
        rest = path.parts[len(paper_parts) :]
        if not rest:
            raise OverleafError("path must refer to a file inside paper_root")
        return PurePosixPath(*rest)
    return path


def normalize_main_document(raw: str, paper_root: PurePosixPath) -> PurePosixPath:
    path = _safe_posix_path(raw, label="main_document")
    return _relative_to_paper(path, paper_root)


def normalize_exclude_paths(raw_values: Any, paper_root: PurePosixPath) -> tuple[PurePosixPath, ...]:
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list) or not all(isinstance(item, str) for item in raw_values):
        raise OverleafError("exclude_paths must be a list of strings")
    normalized = []
    for item in raw_values:
        path = _safe_posix_path(item, label="exclude_paths entry")
        normalized.append(_relative_to_paper(path, paper_root))
    return tuple(sorted(set(normalized), key=lambda p: p.as_posix()))


def is_excluded(rel: str | PurePosixPath, excludes: tuple[PurePosixPath, ...]) -> bool:
    path = PurePosixPath(str(rel).replace("\\", "/"))
    for exclude in excludes:
        if path == exclude or path.parts[: len(exclude.parts)] == exclude.parts:
            return True
    return False


def _load_toml(path: Path) -> dict[str, Any]:
    text = read_text(path)
    if tomllib is not None:
        return tomllib.loads(text)
    data: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if value.startswith('"') and value.endswith('"'):
            data[key] = value[1:-1]
        elif value.isdigit():
            data[key] = int(value)
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                data[key] = [item.strip().strip('"') for item in inner.split(",")]
        else:
            data[key] = value
    return data


def load_config(target: Path) -> OverleafConfig:
    target = ensure_git_repo(target.resolve())
    path = config_path(target)
    if not path.exists():
        raise OverleafError("Overleaf Bridge is not installed; run ai-bridge overleaf install first")
    raw = _load_toml(path)
    for key in raw:
        if SECRET_KEY_RE.search(str(key)) or str(key) == "remote_url":
            raise OverleafError(f"tracked Overleaf config must not contain secret or remote fields: {key}")
    if raw.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise OverleafError(f"unsupported schema_version: {raw.get('schema_version')}")
    paper_root = _safe_posix_path(str(raw.get("paper_root") or ""), label="paper_root")
    main_document = normalize_main_document(str(raw.get("main_document") or ""), paper_root)
    remote_branch = str(raw.get("remote_branch") or "")
    if remote_branch != REMOTE_BRANCH:
        raise OverleafError("remote_branch must be exactly 'master' in Overleaf Bridge v0.6")
    exclude_paths = normalize_exclude_paths(raw.get("exclude_paths", []), paper_root)
    cfg = OverleafConfig(target, paper_root, main_document, remote_branch, exclude_paths)
    validate_config_paths(cfg)
    return cfg


def validate_config_paths(cfg: OverleafConfig) -> None:
    root = cfg.target.resolve()
    paper = cfg.paper_root_path.resolve()
    if not paper.is_relative_to(root):
        raise OverleafError("paper_root resolves outside target repository")
    if not cfg.paper_root_path.exists() or not cfg.paper_root_path.is_dir():
        raise OverleafError(f"paper_root does not exist: {cfg.paper_root}")
    main = cfg.main_document_path.resolve()
    if not main.is_relative_to(paper):
        raise OverleafError("main_document resolves outside paper_root")
    if not cfg.main_document_path.exists() or not cfg.main_document_path.is_file():
        raise OverleafError(f"main_document does not exist inside paper_root: {cfg.main_document}")
    for exclude in cfg.exclude_paths:
        candidate = (cfg.paper_root_path / exclude.as_posix()).resolve()
        if not candidate.is_relative_to(paper):
            raise OverleafError(f"exclude path escapes paper_root: {exclude}")


def write_config(path: Path, *, paper_root: PurePosixPath, main_document: PurePosixPath) -> None:
    text = "\n".join(
        [
            "schema_version = 1",
            f'paper_root = "{paper_root.as_posix()}"',
            f'main_document = "{main_document.as_posix()}"',
            'remote_branch = "master"',
            "exclude_paths = []",
            "",
        ]
    )
    write_text(path, text)


def install_agents_block(target: Path, cfg: OverleafConfig) -> str:
    snippet = read_text(kit_root() / "templates" / "overleaf" / "AGENTS_SNIPPET.md").strip()
    snippet = snippet.replace("__PAPER_ROOT__", cfg.paper_root.as_posix()).replace(
        "__MAIN_DOCUMENT__", cfg.main_document.as_posix()
    )
    block = f"{OVERLEAF_BEGIN_MARKER}\n{snippet}\n{OVERLEAF_END_MARKER}\n"
    agents = target / "AGENTS.md"
    if not agents.exists():
        write_text(agents, block)
        return f"CREATE {agents}"
    current = read_text(agents)
    if OVERLEAF_BEGIN_MARKER in current and OVERLEAF_END_MARKER in current:
        start = current.index(OVERLEAF_BEGIN_MARKER)
        end = current.index(OVERLEAF_END_MARKER) + len(OVERLEAF_END_MARKER)
        prefix = current[:start].rstrip()
        suffix = current[end:].lstrip()
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(block.rstrip())
        if suffix:
            parts.append(suffix.rstrip())
        updated = "\n\n".join(parts) + "\n"
        action = "UPDATE"
    else:
        updated = current.rstrip() + "\n\n" + block
        action = "APPEND"
    if updated != current:
        write_text(agents, updated)
    return f"{action} Overleaf managed block in {agents}"


def install_overleaf(target: Path, *, paper_root: str, main_document: str = "main.tex") -> list[str]:
    target = ensure_git_repo(target.resolve())
    paper = _safe_posix_path(paper_root, label="paper_root")
    main = normalize_main_document(main_document, paper)
    cfg_path = config_path(target)
    actions: list[str] = []
    if not cfg_path.exists():
        write_config(cfg_path, paper_root=paper, main_document=main)
        actions.append(f"CREATE {cfg_path}")
    else:
        actions.append(f"SKIP existing {cfg_path}")
    cfg = load_config(target)
    source_readme = kit_root() / "templates" / "overleaf" / "README.md"
    readme_path = overleaf_root(target) / "README.md"
    if not readme_path.exists():
        write_text(readme_path, read_text(source_readme))
        actions.append(f"CREATE {readme_path}")
    else:
        actions.append(f"SKIP existing {readme_path}")
    actions.append(install_agents_block(target, cfg))
    return actions


def repo_id(target: Path) -> str:
    try:
        origin = git_output(target, ["remote", "get-url", "origin"])
    except Exception:
        origin = ""
    payload = f"{target.resolve()}\n{origin}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", target.name).strip("-") or "repo"
    return f"{name}-{digest}"


def state_root(target: Path) -> Path:
    base = Path(os.environ.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser()
    return base / "overleaf" / repo_id(target)


def connection_path(target: Path) -> Path:
    return state_root(target) / "connection.json"


def mirror_path(target: Path) -> Path:
    return state_root(target) / "mirror"


def sanitize_remote_url(remote_url: str) -> str:
    url = remote_url.strip()
    if not url:
        raise OverleafError("remote URL is required")
    if SECRET_KEY_RE.search(urlsplit(url).query):
        raise OverleafError("remote URL must not contain credentials or token-like query parameters")
    parts = urlsplit(url)
    if parts.scheme in {"http", "https"}:
        if parts.password:
            raise OverleafError("remote URL must not contain credentials or token-like query parameters")
        if parts.username and parts.username != "git":
            raise OverleafError("Overleaf Git URLs should use username 'git'")
    if re.search(r"://[^/\s]+:[^@\s]+@", url):
        raise OverleafError("remote URL must not contain credentials or token-like query parameters")
    return url


def locator_for_url(remote_url: str) -> str:
    parts = urlsplit(remote_url)
    if parts.scheme and parts.netloc:
        host = parts.hostname or parts.netloc.rsplit("@", 1)[-1]
        path = parts.path.lstrip("/")
        return f"{host}/{path}".rstrip("/")
    return Path(remote_url).name or remote_url


def connection_payload(
    cfg: OverleafConfig,
    remote_url: str,
    *,
    baseline: str | None = None,
    remote_commit: str | None = None,
    local_locator: str | None = None,
    managed_paths: list[str] | None = None,
) -> dict[str, Any]:
    existing = load_json(connection_path(cfg.target)) if connection_path(cfg.target).exists() else {}
    return {
        "schema": CONNECTION_SCHEMA,
        "remote_url": remote_url,
        "remote_branch": cfg.remote_branch,
        "paper_root": cfg.paper_root.as_posix(),
        "last_synced_digest": baseline if baseline is not None else existing.get("last_synced_digest"),
        "last_remote_commit": remote_commit if remote_commit is not None else existing.get("last_remote_commit"),
        "last_local_commit_or_locator": local_locator
        if local_locator is not None
        else existing.get("last_local_commit_or_locator"),
        "managed_paths": managed_paths if managed_paths is not None else existing.get("managed_paths", []),
    }


def load_connection(cfg: OverleafConfig) -> dict[str, Any]:
    path = connection_path(cfg.target)
    if not path.exists():
        raise OverleafError("Overleaf Bridge is not connected; run ai-bridge overleaf connect first")
    data = load_json(path)
    if data.get("schema") != CONNECTION_SCHEMA:
        raise OverleafError("connection.json schema mismatch")
    remote_url = sanitize_remote_url(str(data.get("remote_url") or ""))
    if data.get("remote_branch") != cfg.remote_branch:
        raise OverleafError("connection remote_branch does not match config")
    data["remote_url"] = remote_url
    return data


def save_connection(cfg: OverleafConfig, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if SECRET_KEY_RE.search(text.replace('"remote_url"', "")):
        raise OverleafError("connection metadata must not contain token/password/secret fields")
    write_json(connection_path(cfg.target), payload)


def remote_branch_exists(mirror: Path, branch: str) -> bool:
    result = run_git(mirror, ["ls-remote", "--heads", "origin", branch], check=False)
    if result.returncode != 0:
        raise OverleafError((result.stderr or result.stdout or "git ls-remote failed").strip())
    return bool(result.stdout.strip())


def ensure_mirror(cfg: OverleafConfig, remote_url: str) -> Path:
    mirror = mirror_path(cfg.target)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if not (mirror / ".git").exists():
        if mirror.exists():
            shutil.rmtree(mirror)
        result = subprocess.run(
            ["git", "clone", remote_url, str(mirror)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise OverleafError((result.stderr or result.stdout or "git clone failed").strip())
    else:
        run_git(mirror, ["remote", "set-url", "origin", remote_url])
    run_git(mirror, ["config", "user.email", "ai-bridge-overleaf@example.invalid"])
    run_git(mirror, ["config", "user.name", "AI Bridge Overleaf"])
    if remote_branch_exists(mirror, cfg.remote_branch):
        run_git(mirror, ["fetch", "origin", cfg.remote_branch])
        run_git(mirror, ["checkout", "-B", cfg.remote_branch, f"origin/{cfg.remote_branch}"])
    else:
        run_git(mirror, ["checkout", "-B", cfg.remote_branch])
    return mirror


def _repo_rel_to_publication_rel(cfg: OverleafConfig, repo_rel: str) -> str | None:
    path = PurePosixPath(repo_rel.replace("\\", "/"))
    paper_parts = cfg.paper_root.parts
    if path.parts[: len(paper_parts)] != paper_parts:
        return None
    rest = path.parts[len(paper_parts) :]
    if not rest:
        return None
    rel = PurePosixPath(*rest)
    return None if is_excluded(rel, cfg.exclude_paths) else rel.as_posix()


def local_projection(cfg: OverleafConfig) -> Projection:
    out = run_git(cfg.target, ["ls-files", "-z", "--", cfg.paper_root.as_posix()]).stdout
    files: dict[str, bytes] = {}
    paper_resolved = cfg.paper_root_path.resolve()
    for repo_rel in [item for item in out.split("\0") if item]:
        pub_rel = _repo_rel_to_publication_rel(cfg, repo_rel)
        if pub_rel is None:
            continue
        path = cfg.target / repo_rel
        resolved = path.resolve()
        if not resolved.is_relative_to(paper_resolved):
            raise OverleafError(f"publication path escapes paper_root through symlink: {repo_rel}")
        if not path.exists() or not path.is_file():
            continue
        files[pub_rel] = path.read_bytes()
    return Projection(files)


def remote_projection(cfg: OverleafConfig, mirror: Path) -> Projection:
    files: dict[str, bytes] = {}
    root = mirror.resolve()
    for path in sorted(mirror.rglob("*")):
        if ".git" in path.relative_to(mirror).parts:
            continue
        if not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise OverleafError(f"remote mirror path escapes project root: {path}")
        rel = path.relative_to(mirror).as_posix()
        if is_excluded(rel, cfg.exclude_paths):
            continue
        files[rel] = path.read_bytes()
    return Projection(files)


def current_commit_or_unknown(path: Path) -> str:
    result = run_git(path, ["rev-parse", "HEAD"], check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNBORN"


def classify_sync(local: str, remote: str, baseline: str | None) -> str:
    if not baseline:
        return "unknown"
    if local == baseline and remote == baseline:
        return "synced"
    if local != baseline and remote == baseline:
        return "local_ahead"
    if local == baseline and remote != baseline:
        return "remote_ahead"
    if local == remote and local != baseline:
        return "equivalent"
    return "diverged"


def _remove_mirror_worktree(mirror: Path) -> None:
    for path in sorted(mirror.iterdir(), key=lambda p: len(p.parts), reverse=True):
        if path.name == ".git":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def materialize_projection(mirror: Path, projection: Projection) -> None:
    _remove_mirror_worktree(mirror)
    for rel, data in projection.files.items():
        path = mirror / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def commit_mirror_if_needed(mirror: Path, message: str) -> bool:
    run_git(mirror, ["add", "-A"])
    diff = run_git(mirror, ["diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        return False
    if diff.returncode != 1:
        raise OverleafError("unable to inspect mirror staged diff")
    run_git(mirror, ["commit", "-m", message])
    return True


def push_mirror(cfg: OverleafConfig, mirror: Path) -> None:
    run_git(mirror, ["push", "origin", cfg.remote_branch])


def changed_publishable_paths(cfg: OverleafConfig) -> list[str]:
    out = run_git(cfg.target, ["status", "--porcelain=v1", "-z", "--", cfg.paper_root.as_posix()]).stdout
    items = [item for item in out.split("\0") if item]
    paths: set[str] = set()
    index = 0
    while index < len(items):
        entry = items[index]
        status = entry[:2]
        path_text = entry[3:] if len(entry) > 3 else ""
        candidates = [path_text]
        if "R" in status or "C" in status:
            index += 1
            if index < len(items):
                candidates.append(items[index])
        for repo_rel in candidates:
            pub_rel = _repo_rel_to_publication_rel(cfg, repo_rel)
            if pub_rel is not None:
                paths.add(pub_rel)
        index += 1
    return sorted(paths)


def validate_target_remotes(cfg: OverleafConfig) -> list[str]:
    errors: list[str] = []
    remotes = run_git(cfg.target, ["remote"], check=False).stdout.splitlines()
    for remote in remotes:
        url = run_git(cfg.target, ["remote", "get-url", remote], check=False).stdout.strip()
        if remote == "origin" and "git.overleaf.com" in url:
            errors.append("target repository origin points at Overleaf; keep origin as the whole-repo remote")
        if remote == "overleaf":
            errors.append("target repository must not depend on an overleaf remote; use the machine-local mirror")
    return errors


def validate_symlinks(cfg: OverleafConfig) -> list[str]:
    errors: list[str] = []
    paper = cfg.paper_root_path.resolve()
    for repo_rel in [item for item in run_git(cfg.target, ["ls-files", "-z", "--", cfg.paper_root.as_posix()]).stdout.split("\0") if item]:
        pub_rel = _repo_rel_to_publication_rel(cfg, repo_rel)
        if pub_rel is None:
            continue
        path = cfg.target / repo_rel
        if path.is_symlink() and not path.resolve().is_relative_to(paper):
            errors.append(f"publication symlink escapes paper_root: {repo_rel}")
    return errors


def latex_escape_warnings(cfg: OverleafConfig) -> list[str]:
    warnings: list[str] = []
    try:
        projection = local_projection(cfg)
    except OverleafError:
        return warnings
    for rel, data in projection.files.items():
        if rel.endswith(".tex"):
            text = data.decode("utf-8", errors="ignore")
            if "../" in text:
                warnings.append(
                    f"WARN {cfg.paper_root.as_posix()}/{rel} contains '../'; it may compile locally but fail after Overleaf projection"
                )
    return warnings


def validate_overleaf(target: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    errors: list[str] = []
    try:
        cfg = load_config(target)
        lines.append(f"OK installed: {config_path(cfg.target)}")
        lines.append(f"OK paper_root: {cfg.paper_root}")
        lines.append(f"OK main_document: {cfg.main_document}")
        lines.append("OK remote_branch: master")
        errors.extend(validate_target_remotes(cfg))
        errors.extend(validate_symlinks(cfg))
        try:
            local_projection(cfg)
            lines.append("OK publication paths remain inside paper_root")
        except OverleafError as exc:
            errors.append(str(exc))
        lines.extend(latex_escape_warnings(cfg))
    except OverleafError as exc:
        errors.append(str(exc))
    for error in errors:
        lines.append(f"ERROR {error}")
    if errors:
        lines.append(f"FAILED: {len(errors)} error(s)")
        return lines, 1
    lines.append("Overleaf Bridge validation passed.")
    return lines, 0


def connect_overleaf(target: Path, *, remote_url: str, bootstrap: bool = False) -> list[str]:
    cfg = load_config(target)
    safe_url = sanitize_remote_url(remote_url)
    mirror = ensure_mirror(cfg, safe_url)
    local = local_projection(cfg)
    remote = remote_projection(cfg, mirror)
    actions = [f"Mirror: {mirror}", f"Remote: {locator_for_url(safe_url)}"]
    if bootstrap:
        if remote.files:
            raise OverleafError("bootstrap refused: Overleaf remote is not empty")
        materialize_projection(mirror, local)
        committed = commit_mirror_if_needed(mirror, "Initialize Overleaf manuscript projection")
        if committed:
            push_mirror(cfg, mirror)
        baseline = local.digest
        save_connection(
            cfg,
            connection_payload(
                cfg,
                safe_url,
                baseline=baseline,
                remote_commit=current_commit_or_unknown(mirror),
                local_locator=current_commit_or_unknown(cfg.target),
                managed_paths=local.paths,
            ),
        )
        actions.append("Connected and bootstrapped baseline.")
        return actions
    if local.digest != remote.digest:
        raise OverleafError("connect refused: local publication and Overleaf remote differ; use --bootstrap only for an empty remote")
    save_connection(
        cfg,
        connection_payload(
            cfg,
            safe_url,
            baseline=local.digest,
            remote_commit=current_commit_or_unknown(mirror),
            local_locator=current_commit_or_unknown(cfg.target),
            managed_paths=local.paths,
        ),
    )
    actions.append("Connected with matching local and remote content.")
    return actions


def push_overleaf(target: Path) -> list[str]:
    cfg = load_config(target)
    conn = load_connection(cfg)
    changed = changed_publishable_paths(cfg)
    if changed:
        raise OverleafError("push refused: publishable manuscript changes are uncommitted: " + ", ".join(changed))
    mirror = ensure_mirror(cfg, conn["remote_url"])
    local = local_projection(cfg)
    remote = remote_projection(cfg, mirror)
    condition = classify_sync(local.digest, remote.digest, conn.get("last_synced_digest"))
    if condition == "remote_ahead":
        raise OverleafError("push refused: Overleaf remote is ahead; run ai-bridge overleaf pull first")
    if condition == "diverged":
        raise OverleafError("push refused: local and Overleaf remote have diverged")
    if condition in {"synced", "equivalent"}:
        if condition == "equivalent":
            save_connection(
                cfg,
                connection_payload(
                    cfg,
                    conn["remote_url"],
                    baseline=local.digest,
                    remote_commit=current_commit_or_unknown(mirror),
                    local_locator=current_commit_or_unknown(cfg.target),
                    managed_paths=local.paths,
                ),
            )
            return ["Equivalent local and remote content; refreshed baseline."]
        return ["Already synced; no Overleaf commit created."]
    if condition != "local_ahead":
        raise OverleafError("push refused: synchronization baseline is unknown; reconnect safely first")
    materialize_projection(mirror, local)
    committed = commit_mirror_if_needed(mirror, "Publish manuscript projection from Bridge Kit")
    if committed:
        push_mirror(cfg, mirror)
    save_connection(
        cfg,
        connection_payload(
            cfg,
            conn["remote_url"],
            baseline=local.digest,
            remote_commit=current_commit_or_unknown(mirror),
            local_locator=current_commit_or_unknown(cfg.target),
            managed_paths=local.paths,
        ),
    )
    return ["Published local manuscript projection to Overleaf.", f"Files: {len(local.files)}"]


def pull_overleaf(target: Path) -> list[str]:
    cfg = load_config(target)
    conn = load_connection(cfg)
    mirror = ensure_mirror(cfg, conn["remote_url"])
    local = local_projection(cfg)
    remote = remote_projection(cfg, mirror)
    condition = classify_sync(local.digest, remote.digest, conn.get("last_synced_digest"))
    if condition == "local_ahead":
        raise OverleafError("pull refused: local publication is ahead; commit/push or resolve local work first")
    if condition == "diverged":
        raise OverleafError("pull refused: local and Overleaf remote have diverged")
    if condition in {"synced", "equivalent"}:
        if condition == "equivalent":
            save_connection(
                cfg,
                connection_payload(
                    cfg,
                    conn["remote_url"],
                    baseline=local.digest,
                    remote_commit=current_commit_or_unknown(mirror),
                    local_locator=current_commit_or_unknown(cfg.target),
                    managed_paths=local.paths,
                ),
            )
            return ["Equivalent local and remote content; refreshed baseline."]
        return ["Already synced; no files changed."]
    if condition != "remote_ahead":
        raise OverleafError("pull refused: synchronization baseline is unknown; reconnect safely first")
    managed_paths = [str(item) for item in conn.get("managed_paths", []) if isinstance(item, str)]
    paper_root = cfg.paper_root_path
    for rel in managed_paths:
        if rel not in remote.files and not is_excluded(rel, cfg.exclude_paths):
            candidate = paper_root / rel
            if candidate.exists() and candidate.resolve().is_relative_to(paper_root.resolve()):
                candidate.unlink()
    for rel, data in remote.files.items():
        if is_excluded(rel, cfg.exclude_paths):
            continue
        path = paper_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    save_connection(
        cfg,
        connection_payload(
            cfg,
            conn["remote_url"],
            baseline=remote.digest,
            remote_commit=current_commit_or_unknown(mirror),
            local_locator=current_commit_or_unknown(cfg.target),
            managed_paths=remote.paths,
        ),
    )
    return ["Imported Overleaf changes into paper_root; review, compile, commit, then push origin/main."]


def status_overleaf(target: Path) -> list[str]:
    try:
        cfg = load_config(target)
    except OverleafError as exc:
        return ["installed: false", f"reason: {exc}", "next: ai-bridge overleaf install"]
    lines = [
        "installed: true",
        f"paper_root: {cfg.paper_root}",
        f"main_document: {cfg.main_document}",
    ]
    try:
        conn = load_connection(cfg)
    except OverleafError:
        lines.extend(["connected: false", "sync: unknown", "next: ai-bridge overleaf connect"])
        return lines
    lines.append("connected: true")
    lines.append(f"remote: {locator_for_url(conn['remote_url'])}")
    try:
        mirror = ensure_mirror(cfg, conn["remote_url"])
        local = local_projection(cfg)
        remote = remote_projection(cfg, mirror)
        condition = classify_sync(local.digest, remote.digest, conn.get("last_synced_digest"))
    except OverleafError as exc:
        condition = "unknown"
        lines.append(f"sync_error: {exc}")
    changed = changed_publishable_paths(cfg)
    lines.append(f"sync: {condition}")
    lines.append(f"publishable_uncommitted_changes: {str(bool(changed)).lower()}")
    if changed:
        lines.append("changed_paths: " + ", ".join(changed))
    next_action = {
        "synced": "no action needed",
        "local_ahead": "ai-bridge overleaf push",
        "remote_ahead": "ai-bridge overleaf pull",
        "equivalent": "ai-bridge overleaf push or pull to refresh baseline",
        "diverged": "resolve divergence manually",
        "unknown": "validate connection and baseline",
    }.get(condition, "validate connection and baseline")
    lines.append(f"next: {next_action}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge overleaf")
    sub = parser.add_subparsers(dest="command")
    install = sub.add_parser("install", help="Install tracked Overleaf Bridge config in a project.")
    install.add_argument("--target", type=Path, default=Path.cwd())
    install.add_argument("--paper-root", required=True)
    install.add_argument("--main-document", default="main.tex")
    connect = sub.add_parser("connect", help="Connect to an Overleaf Git project via a machine-local mirror.")
    connect.add_argument("--target", type=Path, default=Path.cwd())
    connect.add_argument("--remote-url", required=True)
    connect.add_argument("--bootstrap", action="store_true")
    for name in ["status", "push", "pull", "validate"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--target", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "install":
            for line in install_overleaf(args.target, paper_root=args.paper_root, main_document=args.main_document):
                print(line)
            return 0
        if args.command == "connect":
            for line in connect_overleaf(args.target, remote_url=args.remote_url, bootstrap=args.bootstrap):
                print(line)
            return 0
        if args.command == "status":
            for line in status_overleaf(args.target):
                print(line)
            return 0
        if args.command == "push":
            for line in push_overleaf(args.target):
                print(line)
            return 0
        if args.command == "pull":
            for line in pull_overleaf(args.target):
                print(line)
            return 0
        if args.command == "validate":
            lines, code = validate_overleaf(args.target)
            for line in lines:
                print(line)
            return code
    except OverleafError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
