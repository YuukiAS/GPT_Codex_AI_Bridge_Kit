from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import plugin_replay


RUN_SCHEMA = "AI_BRIDGE_CANDIDATE_PLUGIN_REPLAY_RUN_V1"
CANDIDATE_NAMESPACE = "ai-bridge-candidate"
CANDIDATE_COMMIT_INVALID = "CANDIDATE_COMMIT_INVALID"
CANDIDATE_MARKETPLACE_MANIFEST_INVALID = "CANDIDATE_MARKETPLACE_MANIFEST_INVALID"
CANDIDATE_PLUGIN_NOT_FOUND = "CANDIDATE_PLUGIN_NOT_FOUND"
CANDIDATE_PLUGIN_SOURCE_INVALID = "CANDIDATE_PLUGIN_SOURCE_INVALID"
CANDIDATE_PLUGIN_ADD_FAILED = "CANDIDATE_PLUGIN_ADD_FAILED"
CANDIDATE_INSTALL_IDENTITY_MISMATCH = "CANDIDATE_INSTALL_IDENTITY_MISMATCH"
CANDIDATE_EFFECTIVE_PLUGIN_NOT_PROVEN = "CANDIDATE_EFFECTIVE_PLUGIN_NOT_PROVEN"
CANDIDATE_CHILD_CONFIG_CHANGED = "CANDIDATE_CHILD_CONFIG_CHANGED"
CANDIDATE_REPLAY_FAILED = "CANDIDATE_REPLAY_FAILED"
CANDIDATE_REPLAY_LOCKED = "CANDIDATE_REPLAY_LOCKED"
CANDIDATE_REPLAY_CLEANUP_FAILED = "CANDIDATE_REPLAY_CLEANUP_FAILED"


class CandidateReplayError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class CandidateSource:
    commit: str
    manifest_path: str
    entry: dict[str, Any]
    source_path: str


@dataclass(frozen=True)
class CandidateState:
    codex_home: Path
    identity_id: str
    identity_root: Path
    active_path: Path
    lock_path: Path


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(_json_dumps(payload), encoding="utf-8")
    os.replace(tmp, path)


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _candidate_state(codex_home: Path, env: dict[str, str] | None = None) -> CandidateState:
    identity_id = hashlib.sha256(str(codex_home).encode("utf-8")).hexdigest()[:24]
    identity_root = plugin_replay.machine_state_home(env) / "candidate-replay" / identity_id
    return CandidateState(
        codex_home=codex_home,
        identity_id=identity_id,
        identity_root=identity_root,
        active_path=identity_root / "active.json",
        lock_path=identity_root / "candidate-replay.lock",
    )


@contextlib.contextmanager
def acquire_identity_lock(state: CandidateState):
    state.identity_root.mkdir(parents=True, exist_ok=True)
    handle = state.lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CandidateReplayError(
                CANDIDATE_REPLAY_LOCKED,
                f"another candidate replay is active for Codex identity {state.codex_home}",
            ) from exc
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _safe_plugin_name(value: str) -> str:
    return plugin_replay._safe_plugin_name(value)


def _is_within(path: Path, root: Path) -> bool:
    return plugin_replay._is_within(path, root)


def _normalize_manifest_path(path: str) -> str:
    if not path or path.startswith("/"):
        raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate local source path must be relative")
    normalized = Path(path).as_posix()
    parts = Path(normalized).parts
    if any(part == ".." for part in parts):
        raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate local source path escapes repository tree")
    return normalized.removeprefix("./")


def resolve_candidate_commit(target_repo: Path, candidate_commit: str) -> str:
    result = _run_git(target_repo, ["rev-parse", "--verify", f"{candidate_commit}^{{commit}}"])
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or result.stdout.strip() or candidate_commit
        raise CandidateReplayError(CANDIDATE_COMMIT_INVALID, detail)
    return result.stdout.strip().splitlines()[0]


def _git_show_text(target_repo: Path, commit: str, path: str) -> str:
    result = _run_git(target_repo, ["show", f"{commit}:{path}"])
    if result.returncode != 0:
        detail = result.stderr.strip() or f"{path} missing"
        raise CandidateReplayError(CANDIDATE_MARKETPLACE_MANIFEST_INVALID, detail)
    return result.stdout


def _source_path_from_entry(entry: dict[str, Any]) -> str:
    source = entry.get("source")
    if isinstance(source, dict):
        if source.get("source") != "local":
            raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate plugin source must be local")
        path = source.get("path")
    elif isinstance(source, str):
        path = source
    else:
        raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate plugin source must be a local source object")
    if not isinstance(path, str) or not path.strip():
        raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate local source path is missing")
    return _normalize_manifest_path(path.strip())


def resolve_candidate_source(target_repo: Path, plugin: str, candidate_commit: str) -> CandidateSource:
    commit = resolve_candidate_commit(target_repo, candidate_commit)
    manifest_path = ".agents/plugins/marketplace.json"
    try:
        manifest = json.loads(_git_show_text(target_repo, commit, manifest_path))
    except json.JSONDecodeError as exc:
        raise CandidateReplayError(CANDIDATE_MARKETPLACE_MANIFEST_INVALID, str(exc)) from exc
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        raise CandidateReplayError(CANDIDATE_MARKETPLACE_MANIFEST_INVALID, "marketplace manifest must contain a plugins list")
    matches = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == plugin]
    if not matches:
        raise CandidateReplayError(CANDIDATE_PLUGIN_NOT_FOUND, f"plugin {plugin!r} is not present in committed marketplace")
    if len(matches) > 1:
        raise CandidateReplayError(CANDIDATE_MARKETPLACE_MANIFEST_INVALID, f"plugin {plugin!r} appears multiple times")
    entry = matches[0]
    source_path = _source_path_from_entry(entry)
    check = _run_git(target_repo, ["cat-file", "-e", f"{commit}:{source_path}"])
    if check.returncode != 0:
        detail = check.stderr.strip() or f"candidate plugin directory is missing: {source_path}"
        raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, detail)
    return CandidateSource(commit=commit, manifest_path=manifest_path, entry=entry, source_path=source_path)


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_dir():
            continue
        rel = item.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(plugin_replay._sha256(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _extract_commit_subtree(target_repo: Path, commit: str, source_path: str, destination: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(target_repo), "archive", "--format=tar", commit, source_path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise CandidateReplayError(
            CANDIDATE_PLUGIN_SOURCE_INVALID,
            result.stderr.decode("utf-8", errors="replace").strip() or "git archive failed",
        )
    destination.mkdir(parents=True, exist_ok=True)
    prefix = source_path.rstrip("/") + "/"
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            if member.name == "pax_global_header":
                continue
            if source_path.rstrip("/").startswith(member.name.rstrip("/") + "/"):
                continue
            if member.name.rstrip("/") == source_path.rstrip("/"):
                continue
            if not member.name.startswith(prefix):
                raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "git archive emitted an unexpected path")
            rel = Path(member.name[len(prefix) :])
            if rel.is_absolute() or any(part == ".." for part in rel.parts):
                raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "git archive emitted an unsafe path")
            target = destination / rel
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if member.issym():
                raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "candidate plugin tree must not contain symlinks")
            if not member.isfile():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise CandidateReplayError(CANDIDATE_PLUGIN_SOURCE_INVALID, "git archive entry could not be read")
            with target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def stage_candidate_marketplace(
    *,
    target_repo: Path,
    candidate: CandidateSource,
    plugin: str,
    run_dir: Path,
    marketplace_name: str,
) -> tuple[Path, Path, str]:
    marketplace_root = run_dir / "marketplace"
    plugin_path = marketplace_root / "plugins" / plugin
    _extract_commit_subtree(target_repo, candidate.commit, candidate.source_path, plugin_path)
    manifest = {
        "name": marketplace_name,
        "plugins": [
            {
                "name": plugin,
                "source": {"source": "local", "path": f"./plugins/{plugin}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                "category": candidate.entry.get("category", "Developer Tools"),
            }
        ],
    }
    manifest_path = marketplace_root / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(_json_dumps(manifest), encoding="utf-8")
    return marketplace_root, plugin_path, tree_digest(plugin_path)


def _candidate_marketplace_config(marketplace_name: str, marketplace_root: Path) -> list[str]:
    return [
        "-c",
        f'marketplaces.{marketplace_name}.source_type="local"',
        "-c",
        f'marketplaces.{marketplace_name}.source="{marketplace_root}"',
    ]


def _candidate_plugin_enable_config(plugin_id: str) -> list[str]:
    return ["-c", f"plugins.{plugin_id}.enabled=true"]


def _run_codex_json(args: list[str], *, codex_home: Path) -> dict[str, Any]:
    result = plugin_replay._run_codex(args, codex_home=codex_home)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise CandidateReplayError(CANDIDATE_REPLAY_FAILED, detail or "codex command failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CandidateReplayError(CANDIDATE_REPLAY_FAILED, f"codex JSON output could not be parsed: {exc}") from exc


def _plugin_add(
    *,
    plugin: str,
    marketplace_name: str,
    marketplace_root: Path,
    codex_home: Path,
) -> dict[str, Any]:
    args = [
        "plugin",
        *_candidate_marketplace_config(marketplace_name, marketplace_root),
        "add",
        "--json",
        f"{plugin}@{marketplace_name}",
    ]
    result = plugin_replay._run_codex(args, codex_home=codex_home)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise CandidateReplayError(CANDIDATE_PLUGIN_ADD_FAILED, detail or "codex plugin add failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CandidateReplayError(CANDIDATE_PLUGIN_ADD_FAILED, f"plugin add JSON output could not be parsed: {exc}") from exc


def _plugin_remove(plugin_id: str, *, codex_home: Path) -> subprocess.CompletedProcess[str]:
    return plugin_replay._run_codex(["plugin", "remove", "--json", plugin_id], codex_home=codex_home)


def _plugin_list(*, codex_home: Path, config_args: list[str] | None = None) -> dict[str, Any]:
    return _run_codex_json(["plugin", *(config_args or []), "list", "--json"], codex_home=codex_home)


def _flatten_plugin_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ["installed", "available"]:
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items


def _installed_candidate(payload: dict[str, Any], plugin_id: str) -> dict[str, Any] | None:
    for item in _flatten_plugin_list(payload):
        if item.get("pluginId") == plugin_id and item.get("installed") is True:
            return item
    return None


def _same_name_identities(payload: dict[str, Any], plugin: str) -> list[dict[str, Any]]:
    return [item for item in _flatten_plugin_list(payload) if item.get("name") == plugin and item.get("installed") is True]


def _identity_snapshots(payload: dict[str, Any], plugin: str, *, exclude_plugin_id: str | None = None) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for item in _same_name_identities(payload, plugin):
        plugin_id = item.get("pluginId")
        if plugin_id == exclude_plugin_id:
            continue
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        source_path = source.get("path") if isinstance(source, dict) else None
        digest = None
        if isinstance(source_path, str):
            path = Path(source_path).expanduser()
            if path.exists() and path.is_dir():
                digest = tree_digest(path.resolve())
        snapshots.append(
            {
                "pluginId": plugin_id,
                "enabled": item.get("enabled"),
                "source_path": source_path,
                "source_tree_digest": digest,
            }
        )
    return sorted(snapshots, key=lambda item: str(item.get("pluginId")))


def _config_hash(codex_home: Path) -> str | None:
    path = codex_home / "config.toml"
    if not path.exists():
        return None
    return plugin_replay._sha256(path)


def _build_candidate_child_argv(
    *,
    workspace: Path,
    outputs_dir: Path,
    codex_executable: str,
    marketplace_name: str,
    marketplace_root: Path,
    plugin_id: str,
    last_message_name: str = "last-message.txt",
    json_events: bool = False,
) -> list[str]:
    argv = [codex_executable, "exec", "--ignore-user-config"]
    if json_events:
        argv.append("--json")
    argv.extend(_candidate_marketplace_config(marketplace_name, marketplace_root))
    argv.extend(_candidate_plugin_enable_config(plugin_id))
    argv.extend(
        [
            "-c",
            'approval_policy="never"',
            "-c",
            "sandbox_workspace_write.network_access=false",
            "-c",
            "sandbox_workspace_write.exclude_slash_tmp=true",
            "-c",
            "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "--disable",
            "memories",
            "-s",
            "workspace-write",
            "-C",
            str(workspace),
            "--add-dir",
            str(outputs_dir),
            "--skip-git-repo-check",
            "--ephemeral",
            "-o",
            str(outputs_dir / last_message_name),
            "-",
        ]
    )
    return argv


def _actual_consumption_proof(child_output: str, installed_path: Path) -> dict[str, Any]:
    path_text = str(installed_path)
    skill_text = str(installed_path / "skills")
    proven = path_text in child_output or skill_text in child_output
    return {
        "proven": proven,
        "evidence": "installed_candidate_path_in_child_event_stream" if proven else None,
        "installed_path": path_text,
    }


def _validate_journal(state: CandidateState, payload: dict[str, Any]) -> None:
    plugin_id = str(payload.get("candidate_plugin_id") or "")
    marketplace_name = str(payload.get("candidate_marketplace_name") or "")
    staging_path = Path(str(payload.get("staging_path") or "")).expanduser().resolve()
    if not marketplace_name.startswith(CANDIDATE_NAMESPACE + "-"):
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, "journal marketplace name is not Bridge-owned")
    if not plugin_id.endswith("@" + marketplace_name):
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, "journal plugin identity is not Bridge-owned")
    if not _is_within(staging_path, state.identity_root):
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, "journal staging path is outside Bridge candidate state")


def recover_stale_journal(state: CandidateState) -> dict[str, Any] | None:
    if not state.active_path.exists():
        return None
    try:
        payload = json.loads(state.active_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, f"active.json is invalid: {exc}") from exc
    _validate_journal(state, payload)
    plugin_id = str(payload["candidate_plugin_id"])
    staging_path = Path(str(payload["staging_path"])).expanduser().resolve()
    remove_result = _plugin_remove(plugin_id, codex_home=state.codex_home)
    if remove_result.returncode != 0:
        list_payload = _plugin_list(codex_home=state.codex_home)
        if _installed_candidate(list_payload, plugin_id) is not None:
            raise CandidateReplayError(
                CANDIDATE_REPLAY_CLEANUP_FAILED,
                remove_result.stderr.strip() or remove_result.stdout.strip() or f"failed to remove {plugin_id}",
            )
    shutil.rmtree(staging_path.parent, ignore_errors=True)
    if staging_path.exists():
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, f"staging path still exists: {staging_path}")
    state.active_path.unlink(missing_ok=True)
    return {"recovered_plugin_id": plugin_id, "removed_staging_path": str(staging_path)}


def _cleanup_owned_resources(
    *,
    state: CandidateState,
    active: dict[str, Any],
    retain_journal_on_failure: bool,
) -> None:
    plugin_id = str(active["candidate_plugin_id"])
    staging_path = Path(str(active["staging_path"])).expanduser().resolve()
    remove_result = _plugin_remove(plugin_id, codex_home=state.codex_home)
    if remove_result.returncode != 0:
        try:
            list_payload = _plugin_list(codex_home=state.codex_home)
        except CandidateReplayError:
            list_payload = {}
        if _installed_candidate(list_payload, plugin_id) is not None:
            if not retain_journal_on_failure:
                state.active_path.unlink(missing_ok=True)
            raise CandidateReplayError(
                CANDIDATE_REPLAY_CLEANUP_FAILED,
                remove_result.stderr.strip() or remove_result.stdout.strip() or f"failed to remove {plugin_id}",
            )
    shutil.rmtree(staging_path.parent, ignore_errors=True)
    if staging_path.exists():
        raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, f"staging path still exists: {staging_path}")
    state.active_path.unlink(missing_ok=True)


def _journal_payload(
    *,
    run_id: str,
    candidate_plugin_id: str,
    candidate_marketplace_name: str,
    staging_path: Path,
    phase: str,
    candidate_commit: str,
    identity_id: str,
) -> dict[str, Any]:
    return {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "candidate_plugin_id": candidate_plugin_id,
        "candidate_marketplace_name": candidate_marketplace_name,
        "staging_path": str(staging_path),
        "phase": phase,
        "candidate_commit": candidate_commit,
        "identity_id": identity_id,
    }


def run_candidate_plugin_replay(
    *,
    target: Path,
    plugin: str,
    candidate_commit: str,
    task_file: Path,
    input_files: list[Path],
    caller_cwd: Path | None = None,
    codex_home: Path | None = None,
) -> tuple[dict[str, Any], int]:
    plugin = _safe_plugin_name(plugin)
    target_repo = plugin_replay.resolve_target_repo(target)
    selected_codex_home = plugin_replay.enforce_current_codex_home(codex_home)
    state = _candidate_state(selected_codex_home)
    task = plugin_replay._require_file_in_roots(
        task_file,
        "task file",
        plugin_replay.authorized_task_roots(target_repo, caller_cwd=caller_cwd),
    )
    inputs = [
        plugin_replay._require_file_in_roots(path, "input", plugin_replay.authorized_input_roots(target_repo))
        for path in input_files
    ]
    if not inputs:
        raise ValueError("at least one --input file is required")

    with acquire_identity_lock(state):
        recovered = recover_stale_journal(state)
        candidate = resolve_candidate_source(target_repo, plugin, candidate_commit)
        run_id = plugin_replay.new_run_id()
        marketplace_name = f"{CANDIDATE_NAMESPACE}-{run_id}"
        candidate_plugin_id = f"{plugin}@{marketplace_name}"
        run_dir = state.identity_root / run_id
        workspace = run_dir / "workspace"
        outputs_dir = run_dir / "outputs"
        workspace.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        marketplace_root, staged_plugin_path, staged_digest = stage_candidate_marketplace(
            target_repo=target_repo,
            candidate=candidate,
            plugin=plugin,
            run_dir=run_dir,
            marketplace_name=marketplace_name,
        )
        marketplace_config = _candidate_marketplace_config(marketplace_name, marketplace_root)
        active = _journal_payload(
            run_id=run_id,
            candidate_plugin_id=candidate_plugin_id,
            candidate_marketplace_name=marketplace_name,
            staging_path=marketplace_root,
            phase="journal_written",
            candidate_commit=candidate.commit,
            identity_id=state.identity_id,
        )
        _atomic_write_json(state.active_path, active)

        codex_executable = plugin_replay.resolved_executable("codex")
        ai_bridge_executable = plugin_replay.resolved_executable("ai-bridge")
        payload: dict[str, Any] = {
            "schema": RUN_SCHEMA,
            "run_id": run_id,
            "status": "running",
            "mode": "B0",
            "target": str(target_repo),
            "codex_home": str(selected_codex_home),
            "identity_id": state.identity_id,
            "run_dir": str(run_dir),
            "workspace": str(workspace),
            "outputs_dir": str(outputs_dir),
            "codex_executable": codex_executable,
            "ai_bridge_executable": ai_bridge_executable,
            "candidate_commit": candidate.commit,
            "candidate_manifest_path": candidate.manifest_path,
            "candidate_source_path": candidate.source_path,
            "candidate_marketplace_name": marketplace_name,
            "candidate_plugin_id": candidate_plugin_id,
            "staged_plugin_path": str(staged_plugin_path),
            "staged_plugin_tree_digest": staged_digest,
            "installed_path": None,
            "installed_plugin_tree_digest": None,
            "same_name_identities_before": [],
            "same_name_identity_snapshots_before": [],
            "same_name_identity_snapshots_after": [],
            "effective_plugin_preflight": None,
            "child_selection_config": None,
            "child_config_hash_before": None,
            "child_config_hash_after": None,
            "actual_consumption": {"proven": False},
            "recovered_stale_journal": recovered,
            "error_code": None,
            "exit_code": None,
        }
        run_json = run_dir / "run.json"
        plugin_replay.write_run_json(run_dir, payload)
        try:
            before_list = _plugin_list(codex_home=selected_codex_home)
            payload["same_name_identities_before"] = _same_name_identities(before_list, plugin)
            payload["same_name_identity_snapshots_before"] = _identity_snapshots(before_list, plugin)
            install_result = _plugin_add(
                plugin=plugin,
                marketplace_name=marketplace_name,
                marketplace_root=marketplace_root,
                codex_home=selected_codex_home,
            )
            active["phase"] = "plugin_installed"
            _atomic_write_json(state.active_path, active)
            installed_plugin_id = install_result.get("pluginId")
            installed_path = install_result.get("installedPath")
            if installed_plugin_id != candidate_plugin_id or not isinstance(installed_path, str):
                raise CandidateReplayError(
                    CANDIDATE_INSTALL_IDENTITY_MISMATCH,
                    f"plugin add returned {installed_plugin_id!r} at {installed_path!r}",
                )
            installed_path_obj = Path(installed_path).expanduser().resolve()
            installed_digest = tree_digest(installed_path_obj)
            if installed_digest != staged_digest:
                raise CandidateReplayError(
                    CANDIDATE_INSTALL_IDENTITY_MISMATCH,
                    "installed plugin tree digest does not match staged candidate",
                )
            payload["installed_path"] = str(installed_path_obj)
            payload["installed_plugin_tree_digest"] = installed_digest
            preflight_config = [
                *marketplace_config,
                *_candidate_plugin_enable_config(candidate_plugin_id),
            ]
            preflight = _plugin_list(codex_home=selected_codex_home, config_args=preflight_config)
            installed_candidate = _installed_candidate(preflight, candidate_plugin_id)
            if installed_candidate is None or installed_candidate.get("enabled") is not True:
                raise CandidateReplayError(CANDIDATE_EFFECTIVE_PLUGIN_NOT_PROVEN, "candidate is not enabled in preflight")
            payload["effective_plugin_preflight"] = {
                "candidate": installed_candidate,
                "same_name_identities": _same_name_identities(preflight, plugin),
            }
            read_scope_argv = _build_candidate_child_argv(
                workspace=workspace,
                outputs_dir=outputs_dir,
                codex_executable=codex_executable,
                marketplace_name=marketplace_name,
                marketplace_root=marketplace_root,
                plugin_id=candidate_plugin_id,
                last_message_name="read-scope-last-message.txt",
            )
            filesystem_read_scope = plugin_replay.probe_child_filesystem_read_scope(
                child_argv=read_scope_argv,
                workspace=workspace,
                outputs_dir=outputs_dir,
                codex_home=selected_codex_home,
            )
            payload["filesystem_read_scope"] = filesystem_read_scope
            if filesystem_read_scope.get("contract_errors"):
                raise CandidateReplayError(plugin_replay.CHILD_CONTRACT_ERROR, "child sandbox contract drifted")
            write_isolation_argv = _build_candidate_child_argv(
                workspace=workspace,
                outputs_dir=outputs_dir,
                codex_executable=codex_executable,
                marketplace_name=marketplace_name,
                marketplace_root=marketplace_root,
                plugin_id=candidate_plugin_id,
                last_message_name="write-isolation-last-message.txt",
            )
            write_isolation = plugin_replay.verify_child_write_isolation(
                child_argv=write_isolation_argv,
                workspace=workspace,
                outputs_dir=outputs_dir,
                codex_home=selected_codex_home,
                run_id=run_id,
            )
            payload["write_isolation"] = write_isolation
            if write_isolation["status"] != "passed":
                error_code = plugin_replay.CHILD_CONTRACT_ERROR if write_isolation.get("contract_errors") else plugin_replay.WRITE_ISOLATION_ERROR
                raise CandidateReplayError(error_code, "child write isolation failed")
            staged = plugin_replay.stage_files(run_dir, task, inputs, dry_run=False)
            payload["inputs"] = plugin_replay._metadata_for(staged)
            child_argv = _build_candidate_child_argv(
                workspace=workspace,
                outputs_dir=outputs_dir,
                codex_executable=codex_executable,
                marketplace_name=marketplace_name,
                marketplace_root=marketplace_root,
                plugin_id=candidate_plugin_id,
                json_events=True,
            )
            payload["child_argv"] = child_argv
            payload["child_selection_config"] = {
                "ignore_user_config": True,
                "marketplace_name": marketplace_name,
                "marketplace_root": str(marketplace_root),
                "candidate_plugin_enabled": candidate_plugin_id,
                "quoted_key_form": False,
            }
            plugin_replay.write_run_json(run_dir, payload)
            prompt = plugin_replay.child_prompt(plugin, staged, outputs_dir)
            child_hash_before = _config_hash(selected_codex_home)
            payload["child_config_hash_before"] = child_hash_before
            result = plugin_replay.run_child_command(
                child_argv,
                workspace=workspace,
                prompt=prompt,
                codex_home=selected_codex_home,
            )
            child_output = result.stdout or ""
            output_path = outputs_dir / "child-output.jsonl"
            output_path.write_text(child_output, encoding="utf-8")
            child_hash_after = _config_hash(selected_codex_home)
            payload["child_config_hash_after"] = child_hash_after
            if child_hash_before != child_hash_after:
                raise CandidateReplayError(CANDIDATE_CHILD_CONFIG_CHANGED, "$CODEX_HOME/config.toml changed during child selection interval")
            payload["child_output_path"] = str(output_path)
            payload["last_message_path"] = str(outputs_dir / "last-message.txt")
            payload["exit_code"] = result.returncode
            proof = _actual_consumption_proof(child_output, installed_path_obj)
            payload["actual_consumption"] = proof
            if result.returncode != 0:
                raise CandidateReplayError(CANDIDATE_REPLAY_FAILED, f"child Codex exited with {result.returncode}")
            if not proof["proven"]:
                raise CandidateReplayError(
                    CANDIDATE_EFFECTIVE_PLUGIN_NOT_PROVEN,
                    "child event stream did not reference the installed candidate plugin path",
                )
            active["phase"] = "child_completed"
            _atomic_write_json(state.active_path, active)
            payload["status"] = "completed"
            plugin_replay.write_run_json(run_dir, payload)
        except Exception as exc:
            payload["status"] = "failed"
            payload["error_code"] = exc.code if isinstance(exc, CandidateReplayError) else CANDIDATE_REPLAY_FAILED
            payload["error"] = str(exc)
            plugin_replay.write_run_json(run_dir, payload)
            try:
                _cleanup_owned_resources(state=state, active=active, retain_journal_on_failure=True)
            except CandidateReplayError as cleanup_exc:
                payload["status"] = "failed"
                payload["error_code"] = cleanup_exc.code
                payload["cleanup_error"] = str(cleanup_exc)
                plugin_replay.write_run_json(run_dir, payload)
                raise
            raise
        _cleanup_owned_resources(state=state, active=active, retain_journal_on_failure=True)
        after_cleanup_list = _plugin_list(codex_home=selected_codex_home)
        if _installed_candidate(after_cleanup_list, candidate_plugin_id) is not None:
            payload["status"] = "failed"
            payload["error_code"] = CANDIDATE_REPLAY_CLEANUP_FAILED
            payload["cleanup_error"] = "candidate plugin identity is still installed after cleanup"
            plugin_replay.write_run_json(run_dir, payload)
            raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, payload["cleanup_error"])
        payload["same_name_identity_snapshots_after"] = _identity_snapshots(
            after_cleanup_list,
            plugin,
            exclude_plugin_id=candidate_plugin_id,
        )
        if payload["same_name_identity_snapshots_after"] != payload["same_name_identity_snapshots_before"]:
            payload["status"] = "failed"
            payload["error_code"] = CANDIDATE_REPLAY_CLEANUP_FAILED
            payload["cleanup_error"] = "pre-existing same-name plugin identity changed during candidate replay"
            plugin_replay.write_run_json(run_dir, payload)
            raise CandidateReplayError(CANDIDATE_REPLAY_CLEANUP_FAILED, payload["cleanup_error"])
        payload["cleanup"] = {
            "candidate_absent": True,
            "staging_absent": not marketplace_root.exists(),
            "active_journal_absent": not state.active_path.exists(),
        }
        plugin_replay.write_run_json(run_dir, payload)
        return candidate_replay_summary(payload), 0


def candidate_replay_summary(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "run_id",
        "status",
        "mode",
        "target",
        "codex_home",
        "identity_id",
        "run_dir",
        "workspace",
        "outputs_dir",
        "candidate_commit",
        "candidate_manifest_path",
        "candidate_source_path",
        "candidate_marketplace_name",
        "candidate_plugin_id",
        "staged_plugin_tree_digest",
        "installed_path",
        "installed_plugin_tree_digest",
        "actual_consumption",
        "child_config_hash_before",
        "child_config_hash_after",
        "child_output_path",
        "last_message_path",
        "error_code",
        "exit_code",
    ]
    summary = {key: payload.get(key) for key in keys if key in payload}
    summary["run_json"] = str(Path(payload["run_dir"]) / "run.json")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge candidate-plugin-replay")
    parser.add_argument("--target", type=Path, required=True, help="Target Git repository containing the candidate commit.")
    parser.add_argument("--plugin", required=True, help="Candidate plugin name to resolve from committed marketplace.json.")
    parser.add_argument("--candidate-commit", required=True, help="Git commit SHA containing the candidate plugin marketplace entry.")
    parser.add_argument("--task", type=Path, required=True, help="Explicit replay instruction/task file.")
    parser.add_argument("--input", dest="inputs", type=Path, action="append", required=True, help="Explicit input file to copy into the replay run. Repeat for multiple files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary, exit_code = run_candidate_plugin_replay(
            target=args.target,
            plugin=args.plugin,
            candidate_commit=args.candidate_commit,
            task_file=args.task,
            input_files=args.inputs,
        )
    except CandidateReplayError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
