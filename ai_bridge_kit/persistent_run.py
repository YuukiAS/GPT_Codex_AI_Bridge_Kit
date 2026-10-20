from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


PERSISTENT_RUN_BEGIN_MARKER = "<!-- ai-bridge-kit:persistent-run:start -->"
PERSISTENT_RUN_END_MARKER = "<!-- ai-bridge-kit:persistent-run:end -->"
REQUIRED_TEMPLATE_FILES = (
    "README.md",
    "CONTRACT_TEMPLATE.md",
    "KICKOFF_TEMPLATE.md",
)


class PersistentRunError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write((json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _contract_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z /_-]*):\s*(.*?)\s*$", raw)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2)
    return fields


def _json_argv(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PersistentRunError("Launch argv must be a JSON array") from exc
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item and "\0" not in item for item in value):
        raise PersistentRunError("Launch argv must be a non-empty JSON string array")
    return value


def _parse_seconds(value: Any, *, default: int) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0:
        return int(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text.isdigit():
            return int(text)
        match = re.fullmatch(r"(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hour|hours)", text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("h"):
                return amount * 3600
            if unit.startswith("m"):
                return amount * 60
            return amount
    return default


def _timestamp_seconds(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip() or value == "UNKNOWN":
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def normalize_progress_evidence(payload: dict[str, Any], *, stalled_after_seconds: int | None = None) -> dict[str, Any]:
    run_locator = str(payload.get("run_locator") or payload.get("run_key") or payload.get("session") or "UNKNOWN").strip() or "UNKNOWN"
    stage = str(payload.get("stage") or payload.get("current_stage") or "UNKNOWN").strip() or "UNKNOWN"
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    last_event = events[-1] if events and isinstance(events[-1], dict) else None
    progress_text = str(
        payload.get("progress_since_previous")
        or payload.get("message")
        or (last_event or {}).get("message")
        or ""
    ).strip()
    completed = payload.get("completed")
    total = payload.get("total")
    unit = payload.get("unit")
    fraction: float | None = None
    if isinstance(completed, int) and isinstance(total, int) and total > 0 and 0 <= completed <= total:
        fraction = completed / total
    elif isinstance(payload.get("fraction"), (int, float)) and 0 <= float(payload["fraction"]) <= 1:
        fraction = float(payload["fraction"])
    eta = payload.get("eta") or payload.get("expected_finish")
    eta_basis = str(payload.get("eta_basis") or "").strip()
    uncertainty = payload.get("eta_uncertainty")
    if eta in {None, ""} or not eta_basis:
        eta_value: str | int | float = "UNKNOWN"
        uncertainty_value: str | int | float = "UNKNOWN"
    else:
        eta_value = eta
        uncertainty_value = uncertainty if uncertainty not in {None, ""} else "UNKNOWN"
    seconds_since_progress = payload.get("seconds_since_progress")
    status = str(payload.get("status") or "normal").strip().lower() or "normal"
    if stalled_after_seconds is not None and isinstance(seconds_since_progress, (int, float)):
        if seconds_since_progress >= stalled_after_seconds:
            status = "stalled"
    if status not in {"normal", "slow", "stalled", "blocked", "complete", "failed"}:
        status = "normal"
    observed_at = payload.get("observed_at") or payload.get("timestamp") or (last_event or {}).get("timestamp") or _utc_now()
    return {
        "schema": "ai-bridge.persistent_run.progress.v1",
        "run_locator": run_locator,
        "observed_at": observed_at,
        "stage": stage,
        "status": status,
        "last_progress_at": payload.get("last_progress_at") or (last_event or {}).get("timestamp") or "UNKNOWN",
        "progress_event_count": len(events),
        "progress_since_previous": progress_text or bool(last_event),
        "progress_summary": progress_text,
        "completed": completed if isinstance(completed, int) else None,
        "total": total if isinstance(total, int) else None,
        "unit": unit if isinstance(unit, str) and unit.strip() else None,
        "fraction": fraction,
        "eta": eta_value,
        "eta_basis": eta_basis or "UNKNOWN",
        "eta_uncertainty": uncertainty_value,
        "semantic_completion_claim": False,
    }


def normalize_progress_file(path: Path, *, stalled_after_seconds: int | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PersistentRunError(f"progress evidence unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise PersistentRunError("progress evidence must be a JSON object")
    return normalize_progress_evidence(payload, stalled_after_seconds=stalled_after_seconds)


def state_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    if os.environ.get("AI_BRIDGE_STATE_HOME"):
        return Path(os.environ["AI_BRIDGE_STATE_HOME"]).expanduser().resolve()
    return Path.home().joinpath(".ai-bridge").resolve()


def _report_identity(progress_path: Path, normalized: dict[str, Any]) -> str:
    raw = "|".join([progress_path.expanduser().resolve().as_posix(), str(normalized.get("run_locator") or "UNKNOWN")])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _report_dir(progress_path: Path, normalized: dict[str, Any], *, root: Path | None = None) -> Path:
    return state_home(root) / "persistent-run" / _report_identity(progress_path, normalized)


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PersistentRunError(f"state file is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise PersistentRunError(f"state file must contain a JSON object: {path}")
    return payload


def _eta_changed(previous: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if not previous:
        return True
    previous_eta = previous.get("eta")
    current_eta = current.get("eta")
    if (previous_eta == "UNKNOWN") != (current_eta == "UNKNOWN"):
        return True
    previous_seconds = _timestamp_seconds(previous_eta)
    current_seconds = _timestamp_seconds(current_eta)
    observed_seconds = _timestamp_seconds(current.get("observed_at"))
    if previous_seconds is None or current_seconds is None:
        return previous_eta != current_eta
    remaining = abs(previous_seconds - observed_seconds) if observed_seconds is not None else 3600
    threshold = max(900, remaining * 0.25)
    return abs(current_seconds - previous_seconds) >= threshold


def _delivery_decision(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    interval_seconds: int,
    last_delivered: dict[str, Any] | None,
    last_delivered_at: str | None = None,
) -> tuple[str, str]:
    if previous is None or last_delivered is None:
        return "deliver", "start_or_resume"
    if previous.get("stage") != current.get("stage"):
        return "deliver", "stage_transition"
    if current.get("status") in {"stalled", "blocked", "complete", "failed"} and previous.get("status") != current.get("status"):
        return "deliver", f"status_{current.get('status')}"
    if _eta_changed(last_delivered, current):
        return "deliver", "eta_changed"
    previous_time = _timestamp_seconds(last_delivered_at or last_delivered.get("observed_at"))
    current_time = _timestamp_seconds(current.get("observed_at"))
    if previous_time is not None and current_time is not None and current_time - previous_time >= interval_seconds:
        return "deliver", "cadence_interval"
    return "suppress", "duplicate_or_non_material"


def _bounded_history_append(history_path: Path, entry: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                history.append(payload)
    history.append(entry)
    history = history[-limit:]
    history_path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in history), encoding="utf-8")
    return history


def report_progress_file(
    path: Path,
    *,
    state_root: Path | None = None,
    history_limit: int = 20,
    stalled_after_seconds: int | None = None,
) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PersistentRunError(f"progress evidence unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise PersistentRunError("progress evidence must be a JSON object")
    stall_threshold = stalled_after_seconds if stalled_after_seconds is not None else raw.get("stall_threshold_seconds")
    normalized = normalize_progress_evidence(raw, stalled_after_seconds=stall_threshold if isinstance(stall_threshold, int) else None)
    interval_seconds = _parse_seconds(raw.get("report_interval_seconds") or raw.get("report_interval"), default=3600)
    delivery_mode = str(raw.get("delivery_mode") or "local").strip().lower() or "local"
    if interval_seconds < 900 and not raw.get("allow_short_test_interval"):
        interval_seconds = 900
    report_dir = _report_dir(path, normalized, root=state_root)
    report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = report_dir / "latest.json"
    history_path = report_dir / "history.jsonl"
    previous_latest = _read_json_if_exists(latest_path)
    previous_report = previous_latest.get("normalized") if previous_latest else None
    last_delivered = previous_latest.get("last_logical_delivery") if previous_latest else None
    last_delivered_at = previous_latest.get("last_logical_delivery_at") if previous_latest else None
    # Read old reports without mistaking a suppressed observation for delivery.
    if previous_latest and "last_logical_delivery" not in previous_latest and previous_latest.get("delivery_decision") == "deliver":
        last_delivered = previous_report
    decision, reason = _delivery_decision(
        previous_report if isinstance(previous_report, dict) else None,
        normalized,
        interval_seconds=interval_seconds,
        last_delivered=last_delivered if isinstance(last_delivered, dict) else None,
        last_delivered_at=last_delivered_at,
    )
    if decision == "deliver":
        last_delivered = normalized
        last_delivered_at = normalized["observed_at"]
    notification = "not_requested"
    if delivery_mode == "notifications":
        notification = "unavailable_existing_configuration_not_verified"
    elif delivery_mode not in {"local", "none"}:
        notification = "unsupported_delivery_mode"
    entry = {
        "schema": "ai-bridge.persistent_run.report.v1",
        "progress_source_locator": path.expanduser().resolve().as_posix(),
        "state_directory": report_dir.as_posix(),
        "report_interval_seconds": interval_seconds,
        "delivery_mode": delivery_mode,
        "delivery_decision": decision,
        "delivery_reason": reason,
        "notification_projection": notification,
        "notification_result": None,
        "normalized": normalized,
        "last_logical_delivery": last_delivered,
        "last_logical_delivery_at": last_delivered_at,
    }
    latest_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    history = _bounded_history_append(history_path, entry, limit=history_limit)
    entry["history_count"] = len(history)
    entry["latest_path"] = latest_path.as_posix()
    entry["history_path"] = history_path.as_posix()
    return entry


def latest_report_for_progress(path: Path, *, state_root: Path | None = None) -> dict[str, Any]:
    normalized = normalize_progress_file(path)
    latest_path = _report_dir(path, normalized, root=state_root) / "latest.json"
    latest = _read_json_if_exists(latest_path)
    if latest is None:
        raise PersistentRunError("no Persistent Run report is recorded for this progress source")
    return latest


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_output(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise PersistentRunError(message)
    return result.stdout.strip()


def ensure_git_repo(target: Path) -> Path:
    try:
        root = git_output(target, ["rev-parse", "--show-toplevel"])
    except Exception as exc:
        raise PersistentRunError(f"target is not inside a Git repository: {target}") from exc
    return Path(root).resolve()


def persistent_run_root(target: Path) -> Path:
    return target / "automation" / "persistent_run"


def template_root() -> Path:
    return kit_root() / "templates" / "persistent_run"


def _managed_block() -> bytes:
    snippet = (template_root() / "AGENTS_SNIPPET.md").read_bytes().strip()
    return (
        PERSISTENT_RUN_BEGIN_MARKER.encode("utf-8")
        + b"\n"
        + snippet
        + b"\n"
        + PERSISTENT_RUN_END_MARKER.encode("utf-8")
        + b"\n"
    )


def install_agents_block(target: Path) -> str:
    from .readiness import managed_agents_transaction

    result = managed_agents_transaction(
        target,
        _managed_block(),
        begin_marker=PERSISTENT_RUN_BEGIN_MARKER.encode("utf-8"),
        end_marker=PERSISTENT_RUN_END_MARKER.encode("utf-8"),
        block_name="persistent_run",
    )
    return f"{result['action']} Persistent Run managed block in {result['path']}"


def install_persistent_run(target: Path) -> list[str]:
    target = ensure_git_repo(target.resolve())
    from .readiness import ReadinessError

    try:
        agents_action = install_agents_block(target)
    except ReadinessError as exc:
        raise PersistentRunError(str(exc)) from exc
    actions: list[str] = [agents_action]
    source_root = template_root()
    destination_root = persistent_run_root(target)
    for name in REQUIRED_TEMPLATE_FILES:
        source = source_root / name
        destination = destination_root / name
        desired = read_text(source)
        existed = destination.exists()
        current = read_text(destination) if existed else None
        if current != desired:
            write_text(destination, desired)
            actions.append(f"{'UPDATE' if existed else 'CREATE'} {destination}")
        else:
            actions.append(f"SKIP unchanged {destination}")
    return actions


def _validate_goal_path(target: Path, raw_goal: str) -> tuple[str, Path]:
    value = str(raw_goal or "").replace("\\", "/").strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value == ".":
        raise PersistentRunError("goal must be a repo-relative path and must not contain '..'")
    candidate = target / path.as_posix()
    resolved_target = target.resolve()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(resolved_target):
        raise PersistentRunError("goal resolves outside target repository")
    if not candidate.exists() or not candidate.is_file():
        raise PersistentRunError(f"goal file does not exist: {path.as_posix()}")
    return path.as_posix(), candidate


def render_kickoff_prompt(target: Path, goal: str) -> str:
    target = ensure_git_repo(target.resolve())
    rel_goal, goal_path = _validate_goal_path(target, goal)
    digest = _sha256_bytes(goal_path.read_bytes())
    template = read_text(template_root() / "KICKOFF_TEMPLATE.md")
    return (
        template.replace("__GOAL_PATH__", rel_goal)
        .replace("__GOAL_SHA256__", digest)
        .rstrip()
        + "\n"
    )


def parse_persistent_contract(target: Path, goal: str, *, expected_goal_sha256: str) -> dict[str, Any]:
    target = ensure_git_repo(target.resolve())
    rel_goal, goal_path = _validate_goal_path(target, goal)
    goal_bytes = goal_path.read_bytes()
    goal_sha256 = _sha256_bytes(goal_bytes)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_goal_sha256 or ""):
        raise PersistentRunError("expected Goal SHA-256 must be 64 lowercase hex")
    if goal_sha256 != expected_goal_sha256:
        raise PersistentRunError(f"GOAL_SHA256_MISMATCH: actual={goal_sha256} expected={expected_goal_sha256}")
    try:
        text = goal_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PersistentRunError("Goal must be UTF-8") from exc
    fields = _contract_fields(text)
    if fields.get("Persistent execution") != "REQUIRED":
        raise PersistentRunError("Goal must freeze 'Persistent execution: REQUIRED'")
    if fields.get("Backend") != "tmux":
        raise PersistentRunError("Goal must freeze 'Backend: tmux'")
    if fields.get("Goal source") != rel_goal:
        raise PersistentRunError("Goal source must exactly match --goal")
    run_key = fields.get("Run/session key", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_key):
        raise PersistentRunError("Run/session key must be a stable safe key")
    working_raw = fields.get("Working directory", ".").replace("\\", "/")
    working_path = PurePosixPath(working_raw)
    if working_path.is_absolute() or ".." in working_path.parts:
        raise PersistentRunError("Working directory must be repo-relative")
    working_directory = (target / working_path.as_posix()).resolve()
    if not working_directory.is_relative_to(target) or not working_directory.is_dir():
        raise PersistentRunError("Working directory is missing or outside target")
    launch_argv = _json_argv(fields.get("Launch argv", ""))
    progress_mode = fields.get("Progress mode", "").strip().lower()
    if progress_mode not in {"count", "fraction", "stage", "none"}:
        raise PersistentRunError("Progress mode must be count, fraction, stage, or none")
    progress_owner = fields.get("Progress owner", "").strip().lower()
    if progress_owner not in {"bridge-child", "project-native", "none"}:
        raise PersistentRunError("Progress owner must be bridge-child, project-native, or none")
    if progress_mode in {"count", "fraction"} and progress_owner == "none":
        raise PersistentRunError("count/fraction progress requires a real producer")
    progress_raw = fields.get("Progress source locator", "").replace("\\", "/").strip()
    if not progress_raw:
        raise PersistentRunError("Progress source locator is required")
    progress_path: Path | None = None
    progress_rel = progress_raw
    if progress_owner == "bridge-child":
        if progress_raw != "bridge-state":
            raise PersistentRunError("bridge-child progress source must be bridge-state")
    elif progress_owner == "project-native":
        progress = PurePosixPath(progress_raw)
        if progress_raw in {"NONE", "bridge-state"} or progress.is_absolute() or ".." in progress.parts:
            raise PersistentRunError("Progress source locator must be repo-relative")
        progress_path = (target / progress.as_posix()).resolve()
        if not progress_path.is_relative_to(target):
            raise PersistentRunError("Progress source locator resolves outside target")
        progress_rel = progress.as_posix()
    elif progress_raw != "NONE":
        raise PersistentRunError("progress owner none requires Progress source locator: NONE")
    cadence_raw = fields.get("Expected progress update seconds", "").strip()
    if cadence_raw == "UNKNOWN":
        expected_update_seconds: int | str = "UNKNOWN"
    elif cadence_raw.isdigit() and int(cadence_raw) > 0:
        expected_update_seconds = int(cadence_raw)
    else:
        raise PersistentRunError("Expected progress update seconds must be a positive integer or UNKNOWN")
    notify = fields.get("Notify", "").strip().upper()
    if notify not in {"OFF", "ON"}:
        raise PersistentRunError("Notify must be OFF or ON")
    recipient_raw = fields.get("Recipient override", "").strip()
    if not recipient_raw:
        raise PersistentRunError("Recipient override must be NONE or an explicit address")
    if recipient_raw == "NONE":
        recipient_override = ""
    else:
        if "\r" in recipient_raw or "\n" in recipient_raw or "@" not in recipient_raw:
            raise PersistentRunError("Recipient override is invalid")
        recipient_override = recipient_raw
    notification_cadence_raw = fields.get("Notification cadence minutes", "60").strip()
    if not notification_cadence_raw.isdigit() or int(notification_cadence_raw) < 15:
        raise PersistentRunError("Notification cadence minutes must be an integer >= 15")
    notification_cadence_minutes = int(notification_cadence_raw)
    try:
        branch = git_output(target, ["branch", "--show-current"]) or "DETACHED"
    except PersistentRunError:
        branch = "UNKNOWN"
    try:
        expected_commit = git_output(target, ["rev-parse", "--verify", "HEAD"])
    except PersistentRunError:
        expected_commit = "UNBORN"
    try:
        repo_origin = git_output(target, ["remote", "get-url", "origin"])
    except PersistentRunError:
        repo_origin = "NO_ORIGIN"
    identity = {
        "repo_realpath": target.as_posix(),
        "repo_origin": repo_origin,
        "branch": branch,
        "expected_commit": expected_commit,
        "run_key": run_key,
        "goal_repo_relative_path": rel_goal,
        "goal_sha256": goal_sha256,
        "working_directory_repo_relative_path": working_path.as_posix(),
        "launch_argv": launch_argv,
        "backend": "tmux",
        "progress_mode": progress_mode,
        "progress_owner": progress_owner,
        "progress_source_locator": progress_rel,
        "expected_progress_update_seconds": expected_update_seconds,
        "notify": notify,
        "recipient_override": recipient_override,
        "notification_cadence_minutes": notification_cadence_minutes,
    }
    launch_id = _sha256_bytes(
        json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return {
        **identity,
        "launch_id": launch_id,
        "session_name": f"ai-bridge-pr-{launch_id}",
        "working_directory": working_directory.as_posix(),
        "progress_source_path": progress_path.as_posix() if progress_path else "",
    }


def _run_binding_path(contract: dict[str, Any], *, state_root: Path | None = None) -> Path:
    key = f"{contract['repo_realpath']}\0{contract['run_key']}".encode("utf-8")
    return state_home(state_root) / "persistent-run" / "runs" / f"{_sha256_bytes(key)}.json"


def _tmux_has_session(session_name: str, *, runner: Any = subprocess.run) -> bool:
    result = runner(
        ["tmux", "has-session", "-t", f"={session_name}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def _binding_matches(binding: dict[str, Any], contract: dict[str, Any]) -> bool:
    immutable = [
        "repo_realpath",
        "repo_origin",
        "branch",
        "expected_commit",
        "run_key",
        "goal_repo_relative_path",
        "goal_sha256",
        "working_directory_repo_relative_path",
        "launch_argv",
        "backend",
        "launch_id",
        "session_name",
        "progress_mode",
        "progress_owner",
        "progress_source_locator",
        "expected_progress_update_seconds",
        "notify",
        "recipient_override",
        "notification_cadence_minutes",
    ]
    return all(binding.get(key) == contract.get(key) for key in immutable)


def _boot_identity() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        return "UNKNOWN"
    return value if re.fullmatch(r"[0-9a-f-]{36}", value) else "UNKNOWN"


def _process_identity(pid: int) -> dict[str, Any] | None:
    if pid <= 0:
        return None
    proc = Path("/proc") / str(pid)
    try:
        stat_text = (proc / "stat").read_text(encoding="utf-8")
        _prefix, separator, suffix = stat_text.rpartition(")")
        if not separator:
            return None
        stat_fields = suffix.strip().split()
        start_ticks = stat_fields[19]
        cmdline = (proc / "cmdline").read_bytes()
    except (OSError, IndexError):
        return None
    return {
        "pid": pid,
        "boot_id": _boot_identity(),
        "start_ticks": start_ticks,
        "argv_digest": _sha256_bytes(cmdline),
    }


def _quantitative_value(progress: dict[str, Any], mode: str) -> tuple[float, float] | None:
    if mode == "count":
        completed, total = progress.get("completed"), progress.get("total")
        if isinstance(completed, int) and isinstance(total, int) and total > 0 and 0 <= completed <= total:
            return float(completed), float(total)
    if mode == "fraction":
        value = progress.get("fraction")
        if isinstance(value, (int, float)) and 0 <= float(value) <= 1:
            return float(value), 1.0
    return None


def _iso_from_seconds(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat()


def estimate_progress_eta(
    history: list[dict[str, Any]],
    *,
    mode: str,
    expected_update_seconds: int | str,
) -> dict[str, Any]:
    result = {"eta": "UNKNOWN", "eta_low": "UNKNOWN", "eta_high": "UNKNOWN", "eta_confidence": "INSUFFICIENT"}
    points: list[tuple[float, float, float, str]] = []
    for item in history[-12:]:
        observed = _timestamp_seconds(item.get("observed_at"))
        value_total = _quantitative_value(item, mode)
        if observed is None or value_total is None:
            continue
        value, total = value_total
        points.append((observed, value, total, str(item.get("stage") or "UNKNOWN")))
    if not points:
        return result
    newest = points[-1][0]
    points = [point for point in points if newest - point[0] <= 3600]
    segment = [points[-1]]
    max_gap = max(900, 3 * expected_update_seconds) if isinstance(expected_update_seconds, int) else 900
    for point in reversed(points[:-1]):
        newer = segment[-1]
        if point[3] != newer[3] or point[2] != newer[2] or point[1] > newer[1] or newer[0] - point[0] > max_gap:
            break
        segment.append(point)
    segment.reverse()
    if len(segment) < 3 or segment[-1][0] - segment[0][0] < 600:
        return result
    rates = [
        (right[1] - left[1]) / (right[0] - left[0])
        for left, right in zip(segment, segment[1:])
        if right[0] > left[0] and right[1] > left[1]
    ]
    if not rates:
        return result
    center_rate = statistics.median(rates)
    if center_rate <= 0:
        return result
    remaining = segment[-1][2] - segment[-1][1]
    if remaining < 0:
        return result
    eta_seconds = remaining / center_rate
    result["eta"] = _iso_from_seconds(segment[-1][0] + eta_seconds)
    if len(rates) >= 2:
        ordered = sorted(rates)
        low_rate = ordered[max(0, int((len(ordered) - 1) * 0.25))]
        high_rate = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.75 + 0.999999))]
        if low_rate > 0 and high_rate > 0:
            result["eta_low"] = _iso_from_seconds(segment[-1][0] + remaining / high_rate)
            result["eta_high"] = _iso_from_seconds(segment[-1][0] + remaining / low_rate)
            result["eta_confidence"] = "ESTIMATED_RANGE"
        else:
            result["eta_confidence"] = "LOW"
    else:
        result["eta_confidence"] = "LOW"
    return result


def update_run_progress(
    *,
    stage: str,
    status: str = "normal",
    message: str = "",
    completed: int | None = None,
    total: int | None = None,
    fraction: float | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    active = os.environ if env is None else env
    path_raw = active.get("AI_BRIDGE_PROGRESS_PATH", "")
    mode = active.get("AI_BRIDGE_PROGRESS_MODE", "")
    owner = active.get("AI_BRIDGE_PROGRESS_OWNER", "")
    run_key = active.get("AI_BRIDGE_RUN_KEY", "")
    runtime_id = active.get("AI_BRIDGE_RUNTIME_ID", "")
    if owner != "bridge-child" or mode not in {"count", "fraction", "stage", "none"}:
        raise PersistentRunError("progress update requires a bridge-child Persistent environment")
    if not path_raw or not run_key or not re.fullmatch(r"[0-9a-f]{64}", runtime_id):
        raise PersistentRunError("progress update environment is incomplete")
    if mode == "count" and not (
        isinstance(completed, int) and isinstance(total, int) and total > 0 and 0 <= completed <= total
    ):
        raise PersistentRunError("count progress requires 0 <= completed <= total")
    if mode == "fraction" and not (isinstance(fraction, (int, float)) and 0 <= float(fraction) <= 1):
        raise PersistentRunError("fraction progress requires 0 <= fraction <= 1")
    payload = {
        "schema": "ai-bridge.persistent_run.progress.v2",
        "run_key": run_key,
        "runtime_id": runtime_id,
        "observed_at": _utc_now(),
        "stage": stage or "UNKNOWN",
        "status": status,
        "message": message,
        "completed": completed,
        "total": total,
        "fraction": float(fraction) if fraction is not None else None,
    }
    _atomic_json(Path(path_raw).expanduser().resolve(), payload)
    return payload


def observe_binding_progress(binding: dict[str, Any]) -> dict[str, Any]:
    path_raw = str(binding.get("progress_source_path") or "")
    observed_at = _utc_now()
    if not path_raw or binding.get("progress_mode") == "none":
        binding["progress_observation"] = {"state": "UNAVAILABLE", "observed_at": observed_at, "reason": "progress source not configured"}
        return binding
    try:
        normalized = normalize_progress_file(Path(path_raw))
    except PersistentRunError as exc:
        binding["progress_observation"] = {"state": "UNAVAILABLE", "observed_at": observed_at, "reason": str(exc)}
        return binding
    history = binding.get("progress_history") if isinstance(binding.get("progress_history"), list) else []
    point = dict(normalized)
    if not history or history[-1] != point:
        history.append(point)
    history = history[-12:]
    eta = estimate_progress_eta(
        history,
        mode=str(binding.get("progress_mode") or "none"),
        expected_update_seconds=binding.get("expected_progress_update_seconds", "UNKNOWN"),
    )
    normalized.update(eta)
    binding["progress_history"] = history
    binding["last_good_progress"] = normalized
    binding["progress_observation"] = {"state": "AVAILABLE", "observed_at": observed_at}
    return binding


def _persistent_notification(
    binding: dict[str, Any],
    *,
    fact_class: str,
    status: str,
    summary: str,
    next_action: str,
    progress: dict[str, Any] | None = None,
) -> None:
    if binding.get("notify") != "ON":
        return
    try:
        from .notifier import deliver_notification, notification_request

        progress = progress or {}
        source_id = "|".join(
            [
                str(binding.get("launch_id") or ""),
                fact_class,
                str(progress.get("observed_at") or binding.get("child_exit_observed_at") or binding.get("child_started_at") or ""),
                status,
            ]
        )
        request = notification_request(
            project=Path(str(binding["repo_realpath"])).name,
            task_key=str(binding["run_key"]),
            consumer="persistent",
            fact_class=fact_class,
            status=status,
            decision_authority="Runtime",
            summary=summary,
            next_action=next_action,
            stage=str(progress.get("stage") or ""),
            completed=progress.get("completed"),
            total=progress.get("total"),
            fraction=progress.get("fraction"),
            eta=progress.get("eta", "UNKNOWN"),
            eta_low=progress.get("eta_low", "UNKNOWN"),
            eta_high=progress.get("eta_high", "UNKNOWN"),
            run_id=str(binding.get("run_key") or ""),
            runtime_id=str(binding.get("launch_id") or ""),
            source_event_id=source_id,
            recipient_override=str(binding.get("recipient_override") or ""),
        )
        delivery = deliver_notification(
            request,
            repo_identity=str(binding.get("repo_realpath") or ""),
        )
        binding["last_notification"] = {
            "status": delivery.status,
            "event_key": delivery.event_key,
            "recorded_at": _utc_now(),
            "fact_class": fact_class,
        }
    except Exception as exc:
        binding["last_notification"] = {
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "recorded_at": _utc_now(),
            "fact_class": fact_class,
        }


def _binding_terminal(binding: dict[str, Any]) -> bool:
    return bool(binding.get("child_exit_observed_at") or binding.get("create_failure_observed_at") or binding.get("resolved_at"))


def _progress_status(contract: dict[str, Any]) -> dict[str, Any]:
    raw = str(contract.get("progress_source_path") or "")
    if not raw:
        return {"state": "UNKNOWN", "reason": "progress source not configured"}
    path = Path(raw)
    if not path.is_file():
        return {"state": "UNKNOWN", "reason": "progress source missing", "path": path.as_posix()}
    try:
        return {"state": "AVAILABLE", "normalized": normalize_progress_file(path), "path": path.as_posix()}
    except PersistentRunError as exc:
        return {"state": "UNKNOWN", "reason": str(exc), "path": path.as_posix()}


def _run_status(
    contract: dict[str, Any],
    binding: dict[str, Any] | None,
    exact_active: bool,
) -> dict[str, Any]:
    progress = _progress_status(contract)
    if binding is None:
        return {
            "status": "CONFLICT" if exact_active else "NOT_STARTED",
            "reason": "exact session exists without binding" if exact_active else "no binding or exact session",
            "launch_id": contract["launch_id"],
            "session_name": contract["session_name"],
            "progress": progress,
        }
    if not _binding_matches(binding, contract):
        return {"status": "CONFLICT", "reason": "binding identity mismatch", "binding": binding}
    if _binding_terminal(binding):
        if exact_active:
            return {"status": "CONFLICT", "reason": "terminal binding has active session", "binding": binding}
        if binding.get("resolved_at"):
            return {
                "status": "STALE_CLOSED_WITHOUT_COMPLETION",
                "binding": binding,
                "progress": progress,
                "semantic_completion_claim": False,
            }
        return {
            "status": "TERMINAL" if binding.get("child_exit_observed_at") else "CREATE_FAILED",
            "exit_code": binding.get("exit_code"),
            "binding": binding,
            "progress": progress,
        }
    if exact_active:
        return {
            "status": "RUNNING" if binding.get("child_started_at") else "STARTING",
            "binding": binding,
            "progress": progress,
        }
    return {
        "status": "UNKNOWN/UNAVAILABLE",
        "reason": "nonterminal binding exists but exact session is missing; no relaunch and no terminal inference",
        "binding": binding,
        "progress": progress,
    }


def start_persistent_run(
    target: Path,
    goal: str,
    *,
    expected_goal_sha256: str,
    state_root: Path | None = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    contract = parse_persistent_contract(target, goal, expected_goal_sha256=expected_goal_sha256)
    binding_path = _run_binding_path(contract, state_root=state_root)
    if contract["progress_owner"] == "bridge-child":
        contract["progress_source_path"] = binding_path.with_suffix(".progress.json").as_posix()
    binding = _read_json_if_exists(binding_path)
    exact_active = _tmux_has_session(contract["session_name"], runner=runner)
    observed = _run_status(contract, binding, exact_active)
    if observed["status"] != "NOT_STARTED":
        mapping = {
            "TERMINAL": "ALREADY_TERMINAL",
            "CREATE_FAILED": "ALREADY_TERMINAL",
            "RUNNING": "RETURN_EXISTING",
            "STARTING": "RETURN_EXISTING",
            "UNKNOWN/UNAVAILABLE": "NO_RELAUNCH",
        }
        original = str(observed["status"])
        observed["status"] = mapping.get(original, original)
        if original in {"RUNNING", "STARTING", "UNKNOWN/UNAVAILABLE"}:
            observed["lifecycle_state"] = original
        return observed
    if contract["notify"] == "ON":
        from .notifier import require_notifier_ready

        try:
            require_notifier_ready(state_root=state_root)
        except ValueError as exc:
            return {
                "status": "NOTIFIER_NOT_READY",
                "reason": str(exc),
                "launch_id": contract["launch_id"],
                "session_name": contract["session_name"],
            }
    binding = {
        "schema": "ai-bridge.persistent-run.binding.v2",
        **contract,
        "binding_path": binding_path.as_posix(),
        "start_requested_at": _utc_now(),
        "lifecycle_state": "START_REQUESTED",
        "host_boot_id": _boot_identity(),
    }
    _atomic_json(binding_path, binding)
    supervisor = [
        sys.executable,
        "-m",
        "ai_bridge_kit.persistent_run",
        "_supervise",
        "--binding",
        binding_path.as_posix(),
        "--launch-id",
        contract["launch_id"],
    ]
    command = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        contract["session_name"],
        "-c",
        contract["working_directory"],
        *supervisor,
    ]
    result = runner(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        created = _tmux_has_session(contract["session_name"], runner=runner)
        if not created:
            binding["create_failure_observed_at"] = _utc_now()
            binding["create_returncode"] = result.returncode
            binding["lifecycle_state"] = "CREATE_FAILED"
            binding["create_error"] = (result.stderr or result.stdout or "tmux new-session failed").strip()
            _atomic_json(binding_path, binding)
            return {"status": "CREATE_FAILED", "binding": binding, "command": command}
        binding["lifecycle_state"] = "UNKNOWN/UNAVAILABLE"
        binding["create_error"] = "tmux returned nonzero but the exact session exists"
        _atomic_json(binding_path, binding)
        return {"status": "UNKNOWN/UNAVAILABLE", "binding": binding, "command": command}
    return {
        "status": "NEW_START",
        "launch_id": contract["launch_id"],
        "session_name": contract["session_name"],
        "binding_path": binding_path.as_posix(),
        "command": command,
        "progress": _progress_status(contract),
    }


def status_persistent_run(
    target: Path,
    goal: str,
    *,
    expected_goal_sha256: str,
    state_root: Path | None = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    contract = parse_persistent_contract(target, goal, expected_goal_sha256=expected_goal_sha256)
    binding_path = _run_binding_path(contract, state_root=state_root)
    if contract["progress_owner"] == "bridge-child":
        contract["progress_source_path"] = binding_path.with_suffix(".progress.json").as_posix()
    binding = _read_json_if_exists(binding_path)
    exact_active = _tmux_has_session(contract["session_name"], runner=runner)
    return _run_status(contract, binding, exact_active)


def recover_persistent_run(
    target: Path,
    goal: str,
    *,
    expected_goal_sha256: str,
    state_root: Path | None = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    contract = parse_persistent_contract(target, goal, expected_goal_sha256=expected_goal_sha256)
    binding_path = _run_binding_path(contract, state_root=state_root)
    if contract["progress_owner"] == "bridge-child":
        contract["progress_source_path"] = binding_path.with_suffix(".progress.json").as_posix()
    binding = _read_json_if_exists(binding_path)
    exact_active = _tmux_has_session(contract["session_name"], runner=runner)
    base = {"launch_id": contract["launch_id"], "session_name": contract["session_name"], "binding_path": binding_path.as_posix()}
    if binding is None:
        if exact_active:
            return {**base, "classification": "IDENTITY_CONFLICT", "next_action": "resolve the independently authorized conflicting exact session, then recover again"}
        return {**base, "classification": "NOT_STARTED", "next_action": "start only with current user kickoff authorization"}
    if not _binding_matches(binding, contract):
        return {**base, "classification": "IDENTITY_CONFLICT", "next_action": "do not takeover; resolve the conflicting binding/session independently"}
    if _binding_terminal(binding):
        return {**base, "classification": "TERMINAL", "next_action": "evaluate the original Goal completion criteria; do not infer completion from runtime state", "binding": binding}
    if exact_active:
        return {**base, "classification": "ACTIVE", "next_action": "continue with persistent-run status", "binding": binding}
    current_boot = _boot_identity()
    recorded_boot = str(binding.get("host_boot_id") or "UNKNOWN")
    if recorded_boot != "UNKNOWN" and current_boot != "UNKNOWN" and recorded_boot != current_boot:
        return {**base, "classification": "SAFE_TO_CLOSE_STALE", "next_action": f"persistent-run resolve --expected-launch-id {contract['launch_id']} --close-stale", "binding": binding}
    recorded_process = binding.get("child_process_identity")
    if isinstance(recorded_process, dict) and isinstance(recorded_process.get("pid"), int):
        current_process = _process_identity(recorded_process["pid"])
        if current_process is None:
            proc_root = Path("/proc")
            proc_pid = proc_root / str(recorded_process["pid"])
            if proc_root.is_dir() and not proc_pid.exists():
                return {**base, "classification": "SAFE_TO_CLOSE_STALE", "next_action": f"persistent-run resolve --expected-launch-id {contract['launch_id']} --close-stale", "binding": binding}
            return {
                **base,
                "classification": "DUPLICATE_RISK_UNRESOLVED",
                "next_action": "process identity is unavailable; obtain proof the old child ended before resolving stale state",
                "binding": binding,
            }
        comparable = ("boot_id", "start_ticks", "argv_digest")
        if all(recorded_process.get(key) == current_process.get(key) for key in comparable):
            return {**base, "classification": "ORPHAN_CHILD_ALIVE", "next_action": "wait and run persistent-run recover again; destructive termination requires separate authorization", "binding": binding}
        return {**base, "classification": "SAFE_TO_CLOSE_STALE", "next_action": f"persistent-run resolve --expected-launch-id {contract['launch_id']} --close-stale", "binding": binding}
    return {
        **base,
        "classification": "DUPLICATE_RISK_UNRESOLVED",
        "next_action": "obtain host evidence that the old child ended, or separately authorize termination, then recover again",
        "binding": binding,
    }


def resolve_persistent_run(
    target: Path,
    goal: str,
    *,
    expected_goal_sha256: str,
    expected_launch_id: str,
    close_stale: bool,
    state_root: Path | None = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    if not close_stale:
        raise PersistentRunError("resolve requires --close-stale")
    recovered = recover_persistent_run(
        target,
        goal,
        expected_goal_sha256=expected_goal_sha256,
        state_root=state_root,
        runner=runner,
    )
    if recovered["launch_id"] != expected_launch_id:
        raise PersistentRunError("expected launch identity mismatch")
    if recovered["classification"] != "SAFE_TO_CLOSE_STALE":
        raise PersistentRunError(f"close stale refused: {recovered['classification']}")
    if _tmux_has_session(recovered["session_name"], runner=runner):
        raise PersistentRunError("close stale refused: exact session is active")
    binding_path = Path(recovered["binding_path"])
    binding = _read_json_if_exists(binding_path)
    if binding is None or binding.get("launch_id") != expected_launch_id:
        raise PersistentRunError("close stale refused: binding identity changed")
    if binding != recovered.get("binding") or _binding_terminal(binding):
        raise PersistentRunError("close stale refused: binding state changed during recovery")
    binding["resolved_at"] = _utc_now()
    binding["lifecycle_state"] = "STALE_CLOSED_WITHOUT_COMPLETION"
    binding["semantic_completion_claim"] = False
    _atomic_json(binding_path, binding)
    return {
        "status": "STALE_CLOSED_WITHOUT_COMPLETION",
        "launch_id": expected_launch_id,
        "binding_path": binding_path.as_posix(),
        "semantic_completion_claim": False,
    }


def supervise_binding(
    binding_path: Path,
    launch_id: str,
    *,
    observation_seconds: float = 60.0,
) -> int:
    binding = _read_json_if_exists(binding_path)
    if binding is None:
        return 2
    expected_session = f"ai-bridge-pr-{launch_id}"
    if binding.get("launch_id") != launch_id or binding.get("session_name") != expected_session:
        binding["supervisor_identity_error_at"] = _utc_now()
        binding["lifecycle_state"] = "UNKNOWN/UNAVAILABLE"
        _atomic_json(binding_path, binding)
        return 2
    working_directory = Path(str(binding.get("working_directory") or ""))
    argv = binding.get("launch_argv")
    if not working_directory.is_dir() or not isinstance(argv, list) or not argv:
        binding["supervisor_start_error_at"] = _utc_now()
        binding["lifecycle_state"] = "UNKNOWN/UNAVAILABLE"
        _atomic_json(binding_path, binding)
        return 2
    child_env = os.environ.copy()
    child_env.update(
        {
            "AI_BRIDGE_RUN_KEY": str(binding["run_key"]),
            "AI_BRIDGE_PROGRESS_PATH": str(binding.get("progress_source_path") or ""),
            "AI_BRIDGE_PROGRESS_MODE": str(binding.get("progress_mode") or "none"),
            "AI_BRIDGE_PROGRESS_OWNER": str(binding.get("progress_owner") or "none"),
            "AI_BRIDGE_PROGRESS_EXPECTED_UPDATE_SECONDS": str(binding.get("expected_progress_update_seconds") or "UNKNOWN"),
            "AI_BRIDGE_RUNTIME_OWNER": "persistent",
            "AI_BRIDGE_RUNTIME_ID": launch_id,
        }
    )
    try:
        child = subprocess.Popen(argv, cwd=working_directory, env=child_env)
    except OSError as exc:
        binding["child_spawn_failure_observed_at"] = _utc_now()
        binding["child_spawn_error"] = str(exc)
        binding["lifecycle_state"] = "SPAWN_FAILED"
        _atomic_json(binding_path, binding)
        return 2
    binding["child_started_at"] = _utc_now()
    binding["child_pid"] = child.pid
    binding["child_process_identity"] = _process_identity(child.pid) or {"state": "UNAVAILABLE"}
    binding["lifecycle_state"] = "RUNNING"
    observe_binding_progress(binding)
    _persistent_notification(
        binding,
        fact_class="runtime_start",
        status="RUNNING",
        summary="Persistent primary child started; this is a runtime fact, not semantic completion.",
        next_action="Use persistent-run status to observe the same launch identity.",
    )
    binding["last_logical_delivery"] = binding.get("last_good_progress")
    binding["last_logical_delivery_at"] = binding["child_started_at"]
    _atomic_json(binding_path, binding)
    if not hasattr(child, "poll"):
        exit_code = child.wait()
    else:
        while True:
            try:
                exit_code = child.wait(timeout=observation_seconds)
                break
            except subprocess.TimeoutExpired:
                previous = binding.get("last_good_progress") if isinstance(binding.get("last_good_progress"), dict) else None
                observe_binding_progress(binding)
                current = binding.get("last_good_progress") if isinstance(binding.get("last_good_progress"), dict) else None
                if current is not None:
                    # Supervisor observation time, not producer publication time,
                    # drives cadence even when a healthy source is unchanged.
                    observed = {**current, "observed_at": _utc_now()}
                    decision, _reason = _delivery_decision(
                        previous,
                        observed,
                        interval_seconds=int(binding.get("notification_cadence_minutes", 60)) * 60,
                        last_delivered=binding.get("last_logical_delivery"),
                        last_delivered_at=binding.get("last_logical_delivery_at"),
                    )
                    if decision == "deliver":
                        runtime_status = str(current.get("status") or "RUNNING").upper()
                        if runtime_status == "COMPLETE":
                            runtime_status = "SOURCE_REPORTED_TERMINAL"
                        _persistent_notification(
                            binding,
                            fact_class="runtime_progress",
                            status=runtime_status,
                            summary="Persistent supervisor observed project-owned progress; this is not semantic completion.",
                            next_action="Continue observing the same runtime unless the original Goal requires action.",
                            progress=current,
                        )
                        # A logical delivery consumes cadence even if transport
                        # fails; observations must not become automatic retries.
                        binding["last_logical_delivery"] = current
                        binding["last_logical_delivery_at"] = observed["observed_at"]
                _atomic_json(binding_path, binding)
    binding["child_exit_observed_at"] = _utc_now()
    binding["exit_code"] = exit_code
    binding["lifecycle_state"] = "TERMINAL"
    _persistent_notification(
        binding,
        fact_class="runtime_terminal",
        status=f"EXITED_{exit_code}",
        summary=f"Persistent primary child exited with code {exit_code}; Goal completion is not inferred.",
        next_action="Evaluate the original Goal's positive completion evidence.",
        progress=binding.get("last_good_progress") if isinstance(binding.get("last_good_progress"), dict) else None,
    )
    _atomic_json(binding_path, binding)
    return 0


def validate_persistent_run(target: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    errors: list[str] = []
    try:
        target = ensure_git_repo(target.resolve())
    except PersistentRunError as exc:
        return [f"ERROR {exc}", "FAILED: 1 error(s)"], 1

    source_root = template_root()
    destination_root = persistent_run_root(target)
    for name in REQUIRED_TEMPLATE_FILES:
        source = source_root / name
        destination = destination_root / name
        rel = destination.relative_to(target).as_posix()
        if not destination.exists():
            errors.append(f"missing {rel}")
            continue
        if not destination.is_file():
            errors.append(f"not a file: {rel}")
            continue
        if read_text(destination) != read_text(source):
            errors.append(f"template mismatch: {rel}")
            continue
        lines.append(f"OK   {rel} installed")

    agents = target / "AGENTS.md"
    if not agents.exists():
        errors.append("missing AGENTS.md")
    else:
        text = read_text(agents)
        begin_count = text.count(PERSISTENT_RUN_BEGIN_MARKER)
        end_count = text.count(PERSISTENT_RUN_END_MARKER)
        if begin_count != 1 or end_count != 1:
            errors.append("Persistent Run AGENTS managed block markers are missing or duplicated")
        elif text.index(PERSISTENT_RUN_BEGIN_MARKER) > text.index(PERSISTENT_RUN_END_MARKER):
            errors.append("Persistent Run AGENTS managed block markers are malformed")
        else:
            snippet = read_text(source_root / "AGENTS_SNIPPET.md").strip()
            block = text[
                text.index(PERSISTENT_RUN_BEGIN_MARKER) + len(PERSISTENT_RUN_BEGIN_MARKER) : text.index(PERSISTENT_RUN_END_MARKER)
            ].strip()
            if block != snippet:
                errors.append("Persistent Run AGENTS managed block content mismatch")
            else:
                lines.append("OK   AGENTS.md Persistent Run managed block installed")

    forbidden_codex_rules = target / ".codex" / "rules"
    if forbidden_codex_rules.exists():
        errors.append("Persistent Run install must not create .codex/rules")
    else:
        lines.append("OK   .codex/rules absent")

    for error in errors:
        lines.append(f"ERROR {error}")
    if errors:
        lines.append(f"FAILED: {len(errors)} error(s)")
        return lines, 1
    lines.append("Persistent Run validation passed.")
    return lines, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge persistent-run")
    sub = parser.add_subparsers(dest="command")
    install = sub.add_parser("install", help="Install Persistent Run in a project.")
    install.add_argument("--target", type=Path, default=Path.cwd())
    validate = sub.add_parser("validate", help="Validate a Persistent Run installation.")
    validate.add_argument("--target", type=Path, default=Path.cwd())
    prompt = sub.add_parser("prompt", help="Print Persistent Run prompts.")
    prompt_sub = prompt.add_subparsers(dest="prompt_command")
    kickoff = prompt_sub.add_parser("kickoff", help="Print explicit kickoff authorization for a Goal.")
    kickoff.add_argument("--target", type=Path, default=Path.cwd())
    kickoff.add_argument("--goal", required=True)
    start = sub.add_parser("start", help="Start exactly one frozen local Persistent Run.")
    start.add_argument("--target", type=Path, default=Path.cwd())
    start.add_argument("--goal", required=True)
    start.add_argument("--expected-goal-sha256", required=True)
    start.add_argument("--state-home", type=Path)
    status = sub.add_parser("status", help="Read the exact local Persistent Run lifecycle.")
    status.add_argument("--target", type=Path, default=Path.cwd())
    status.add_argument("--goal", required=True)
    status.add_argument("--expected-goal-sha256", required=True)
    status.add_argument("--state-home", type=Path)
    progress = sub.add_parser("progress", help="Normalize evidence or update bridge-child progress.")
    progress.add_argument("--evidence", type=Path)
    progress.add_argument("--stalled-after-seconds", type=int)
    progress_sub = progress.add_subparsers(dest="progress_command")
    update = progress_sub.add_parser("update", help="Atomically update progress for the current bridge-child run.")
    update.add_argument("--stage", required=True)
    update.add_argument("--status", default="normal")
    update.add_argument("--message", default="")
    update.add_argument("--completed", type=int)
    update.add_argument("--total", type=int)
    update.add_argument("--fraction", type=float)
    recover = sub.add_parser("recover", help="Classify one abnormal Persistent Run without relaunching it.")
    recover.add_argument("--target", type=Path, default=Path.cwd())
    recover.add_argument("--goal", required=True)
    recover.add_argument("--expected-goal-sha256", required=True)
    recover.add_argument("--state-home", type=Path)
    resolve = sub.add_parser("resolve", help="Explicitly close a proven stale binding without claiming completion.")
    resolve.add_argument("--target", type=Path, default=Path.cwd())
    resolve.add_argument("--goal", required=True)
    resolve.add_argument("--expected-goal-sha256", required=True)
    resolve.add_argument("--expected-launch-id", required=True)
    resolve.add_argument("--close-stale", action="store_true")
    resolve.add_argument("--state-home", type=Path)
    report = sub.add_parser("report", help="Record and compare a project-native Persistent Run progress event.")
    report.add_argument("--progress", type=Path, required=True)
    report.add_argument("--state-home", type=Path)
    report.add_argument("--history-limit", type=int, default=20)
    report.add_argument("--stalled-after-seconds", type=int)
    latest = sub.add_parser("latest", help="Read the latest recorded Persistent Run report for a progress source.")
    latest.add_argument("--progress", type=Path, required=True)
    latest.add_argument("--state-home", type=Path)
    supervise = sub.add_parser("_supervise", help=argparse.SUPPRESS)
    supervise.add_argument("--binding", type=Path, required=True)
    supervise.add_argument("--launch-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "install":
            for line in install_persistent_run(args.target):
                print(line)
            return 0
        if args.command == "validate":
            lines, code = validate_persistent_run(args.target)
            for line in lines:
                print(line)
            return code
        if args.command == "prompt" and args.prompt_command == "kickoff":
            print(render_kickoff_prompt(args.target, args.goal), end="")
            return 0
        if args.command == "start":
            print(
                json.dumps(
                    start_persistent_run(
                        args.target,
                        args.goal,
                        expected_goal_sha256=args.expected_goal_sha256,
                        state_root=args.state_home,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "status":
            print(
                json.dumps(
                    status_persistent_run(
                        args.target,
                        args.goal,
                        expected_goal_sha256=args.expected_goal_sha256,
                        state_root=args.state_home,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "progress" and args.progress_command == "update":
            print(
                json.dumps(
                    update_run_progress(
                        stage=args.stage,
                        status=args.status,
                        message=args.message,
                        completed=args.completed,
                        total=args.total,
                        fraction=args.fraction,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "progress":
            if args.evidence is None:
                raise PersistentRunError("progress requires --evidence or the update subcommand")
            print(json.dumps(normalize_progress_file(args.evidence, stalled_after_seconds=args.stalled_after_seconds), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "recover":
            print(
                json.dumps(
                    recover_persistent_run(
                        args.target,
                        args.goal,
                        expected_goal_sha256=args.expected_goal_sha256,
                        state_root=args.state_home,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "resolve":
            print(
                json.dumps(
                    resolve_persistent_run(
                        args.target,
                        args.goal,
                        expected_goal_sha256=args.expected_goal_sha256,
                        expected_launch_id=args.expected_launch_id,
                        close_stale=args.close_stale,
                        state_root=args.state_home,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "report":
            print(
                json.dumps(
                    report_progress_file(
                        args.progress,
                        state_root=args.state_home,
                        history_limit=args.history_limit,
                        stalled_after_seconds=args.stalled_after_seconds,
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "latest":
            print(json.dumps(latest_report_for_progress(args.progress, state_root=args.state_home), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "_supervise":
            return supervise_binding(args.binding.resolve(), args.launch_id)
    except PersistentRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
