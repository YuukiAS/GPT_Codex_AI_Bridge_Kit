from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _field_map(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        match = re.match(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z /_-]*?):\s*(.*?)\s*$", raw)
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def _json_argv(raw: str, *, field: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PersistentRunError(f"{field} must be a JSON argv array") from exc
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise PersistentRunError(f"{field} must be a non-empty JSON argv array of strings")
    if any("\x00" in item for item in value):
        raise PersistentRunError(f"{field} contains NUL")
    return value


def parse_persistent_contract(target: Path, goal: str) -> dict[str, Any]:
    target = ensure_git_repo(target.resolve())
    rel_goal, goal_path = _validate_goal_path(target, goal)
    raw = goal_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PersistentRunError("Goal must be UTF-8") from exc
    fields = _field_map(text)
    required = {
        "persistent execution": "REQUIRED",
        "backend": "tmux",
        "goal source": rel_goal,
        "run/session key": None,
        "working directory": None,
        "launch argv json": None,
        "resume argv json": None,
        "progress producer": None,
        "progress source locator": None,
        "reader render max turns": None,
        "progress email": None,
        "runtime terminal email": None,
        "semantic completion email": None,
    }
    missing = [name for name in required if not fields.get(name)]
    if missing:
        raise PersistentRunError("Persistent Run contract missing fields: " + ", ".join(missing))
    for name, expected in required.items():
        if expected is not None and fields[name] != expected:
            raise PersistentRunError(f"Persistent Run contract requires {name}: {expected}")
    run_key = fields["run/session key"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_key):
        raise PersistentRunError("Run/session key must be a stable safe key")
    working_raw = fields["working directory"].replace("\\", "/")
    working = PurePosixPath(working_raw)
    if working.is_absolute() or ".." in working.parts:
        raise PersistentRunError("Working directory must be repo-relative")
    working_path = (target / working.as_posix()).resolve()
    if not working_path.is_relative_to(target) or not working_path.is_dir():
        raise PersistentRunError("Working directory is missing or outside the repository")
    launch_argv = _json_argv(fields["launch argv json"], field="Launch argv JSON")
    resume_raw = fields["resume argv json"]
    resume_argv = launch_argv if resume_raw == "SAME_AS_LAUNCH" else _json_argv(resume_raw, field="Resume argv JSON")
    progress_producer = fields["progress producer"]
    if progress_producer not in {"project-native", "lifecycle-only"}:
        raise PersistentRunError("Progress producer must be project-native or lifecycle-only")
    progress_locator = fields["progress source locator"]
    progress_path: Path | None = None
    if progress_locator != "NONE":
        candidate = PurePosixPath(progress_locator.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            raise PersistentRunError("Progress source locator must be repo-relative or NONE")
        progress_path = (target / candidate.as_posix()).resolve()
        if not progress_path.is_relative_to(target):
            raise PersistentRunError("Progress source locator resolves outside repository")
    try:
        reader_max = int(fields["reader render max turns"])
    except ValueError as exc:
        raise PersistentRunError("Reader render max turns must be a bounded integer") from exc
    if not 0 <= reader_max <= 1000:
        raise PersistentRunError("Reader render max turns must be between 0 and 1000")
    from . import notifier

    intents = notifier.normalize_notification_intents(
        {
            "progress_email": fields["progress email"],
            "runtime_terminal_email": fields["runtime terminal email"],
            "semantic_completion_email": fields["semantic completion email"],
        }
    )
    if intents["semantic_completion_email"] == "ENABLED":
        # Persistent Run can copy this intent for the underlying workflow, but never owns it.
        pass
    goal_sha = _sha256_bytes(raw)
    session_digest = hashlib.sha256(f"{target.as_posix()}|{run_key}".encode("utf-8")).hexdigest()[:16]
    return {
        "repo": target.as_posix(),
        "goal": rel_goal,
        "goal_sha256": goal_sha,
        "run_key": run_key,
        "runtime_id": f"persistent:{run_key}:{goal_sha[:12]}",
        "session_name": f"ai-bridge-pr-{session_digest}",
        "working_directory": working_path.as_posix(),
        "launch_argv": launch_argv,
        "resume_argv": resume_argv,
        "progress_producer": progress_producer,
        "progress_source": progress_path.as_posix() if progress_path else "NONE",
        "reader_render_max_turns": reader_max,
        "notification_intents": intents,
        "report_interval_seconds": max(900, _parse_seconds(fields.get("report interval"), default=3600)),
        "resource_boundary_sha256": _sha256_bytes(text.encode("utf-8")),
    }


def persistent_launch_effect(contract: dict[str, Any]) -> dict[str, Any]:
    from .readiness import bounded_effect_identity

    return bounded_effect_identity(
        "persistent_launch",
        {
            "repo": contract["repo"],
            "run_key": contract["run_key"],
            "goal": contract["goal"],
            "goal_sha256": contract["goal_sha256"],
            "backend": "tmux",
            "launch_argv_sha256": _sha256_bytes(json.dumps(contract["launch_argv"], separators=(",", ":")).encode("utf-8")),
            "resume_argv_sha256": _sha256_bytes(json.dumps(contract["resume_argv"], separators=(",", ":")).encode("utf-8")),
            "resource_boundary_sha256": contract["resource_boundary_sha256"],
            "progress_backend": "official_shared_app_server",
            "purpose": "terminal_owned_survive_disconnect",
        },
    )


def _run_binding_path(contract: dict[str, Any], *, state_root: Path | None = None) -> Path:
    identity = hashlib.sha256(f"{contract['repo']}|{contract['run_key']}".encode("utf-8")).hexdigest()[:24]
    return state_home(state_root) / "persistent-run" / "runs" / identity / "binding.json"


def _tmux_has_session(session_name: str, *, runner: Any = subprocess.run) -> bool:
    result = runner(
        ["tmux", "has-session", "-t", f"={session_name}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


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


def _delivery_decision(previous: dict[str, Any] | None, current: dict[str, Any], *, interval_seconds: int) -> tuple[str, str]:
    if previous is None:
        return "deliver", "start_or_resume"
    if previous.get("stage") != current.get("stage"):
        return "deliver", "stage_transition"
    if current.get("status") in {"stalled", "blocked", "complete", "failed"} and previous.get("status") != current.get("status"):
        return "deliver", f"status_{current.get('status')}"
    if current.get("fraction") is not None and current.get("fraction") != previous.get("fraction"):
        return "deliver", "progress_changed"
    if _eta_changed(previous, current):
        return "deliver", "eta_changed"
    previous_time = _timestamp_seconds(previous.get("observed_at"))
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
    decision, reason = _delivery_decision(previous_report if isinstance(previous_report, dict) else None, normalized, interval_seconds=interval_seconds)
    notification = "not_requested"
    notification_result: dict[str, Any] | None = None
    from . import notifier

    intents = notifier.normalize_notification_intents(raw.get("notification_intents"))
    legacy_notify_authorized = os.environ.get("AI_BRIDGE_PERSISTENT_RUN_NOTIFY_AUTHORIZED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if "notification_intents" not in raw and legacy_notify_authorized:
        intents["progress_email"] = "ENABLED"
    progress_event = notifier.canonical_event(
        event_class="progress",
        project=str(raw.get("project") or "Persistent Run"),
        task_key=str(raw.get("task_key") or normalized.get("run_locator") or "persistent_run"),
        status=str(normalized.get("status")),
        key_conclusion=str(
            normalized.get("progress_summary")
            or f"Persistent Run stage {normalized.get('stage')} progress update."
        ),
        evidence_paths=[path.expanduser().resolve().as_posix(), (report_dir / "latest.json").as_posix()],
        next_step="Continue monitoring existing project-native progress evidence.",
        emitter="persistent_supervisor",
        runtime_id=str(normalized.get("run_locator")),
        lifecycle_owner="persistent_supervisor",
        primary_runtime_owner="persistent_supervisor",
    )
    if delivery_mode == "notifications":
        if decision != "deliver":
            notification = "suppressed"
        elif intents["progress_email"] == "ENABLED" and legacy_notify_authorized:
            brief_path = report_dir / "notification_brief.json"
            rendered = notifier.deterministic_fallback(progress_event)
            brief = notifier.rendered_event_brief(progress_event, rendered)
            brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            notification_result = notifier.send_brief(
                brief_path,
                state_path=report_dir / "notifier_state.json",
                dry_run=bool(raw.get("notification_dry_run")),
            )
            notification = str(getattr(notification_result, "status", "unknown"))
            notification_result = {
                "status": getattr(notification_result, "status", "unknown"),
                "event_key": getattr(notification_result, "event_key", ""),
                "message": getattr(notification_result, "message", ""),
            }
        elif intents["progress_email"] != "ENABLED":
            notification = "disabled_by_frozen_intent"
        else:
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
        "notification_intents": intents,
        "canonical_event": progress_event,
        "notification_result": notification_result,
        "normalized": normalized,
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


def _managed_block() -> str:
    snippet = read_text(template_root() / "AGENTS_SNIPPET.md").strip()
    return f"{PERSISTENT_RUN_BEGIN_MARKER}\n{snippet}\n{PERSISTENT_RUN_END_MARKER}\n"


def projected_agents_block(target: Path) -> tuple[str, str]:
    agents = target / "AGENTS.md"
    block = _managed_block()
    if not agents.exists():
        return block, f"CREATE {agents}"
    current = read_text(agents)
    if PERSISTENT_RUN_BEGIN_MARKER in current and PERSISTENT_RUN_END_MARKER in current:
        start = current.index(PERSISTENT_RUN_BEGIN_MARKER)
        end = current.index(PERSISTENT_RUN_END_MARKER) + len(PERSISTENT_RUN_END_MARKER)
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
    return updated, f"{action} Persistent Run managed block in {agents}"


def install_agents_block(target: Path, *, projected: str | None = None, projected_action: str = "") -> str:
    agents = target / "AGENTS.md"
    updated, action = projected_agents_block(target) if projected is None else (projected, projected_action)
    current = read_text(agents) if agents.exists() else None
    if updated != current:
        write_text(agents, updated)
    return action


def install_persistent_run(target: Path) -> list[str]:
    target = ensure_git_repo(target.resolve())
    from .readiness import ReadinessError, preflight_root_agents_mutation

    projected_agents, projected_action = projected_agents_block(target)
    try:
        preflight_root_agents_mutation(
            target,
            projected_agents.encode("utf-8"),
            block_name="persistent_run",
            block_bytes=len(_managed_block().encode("utf-8")),
        )
    except ReadinessError as exc:
        raise PersistentRunError(str(exc)) from exc
    actions: list[str] = []
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
    actions.append(install_agents_block(target, projected=projected_agents, projected_action=projected_action))
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
    contract = parse_persistent_contract(target, goal)
    effect = persistent_launch_effect(contract)
    from . import notifier

    notify_env = notifier.notifier_env(None, Path(contract["repo"]) / notifier.PRIVATE_ENV_PATH)
    notification_effects: dict[str, str] = {}
    for event_class in ("progress", "runtime_terminal"):
        prototype = notifier.canonical_event(
            event_class=event_class,
            project=Path(contract["repo"]).name,
            task_key=contract["run_key"],
            status="authorized_future_runtime_event",
            key_conclusion="Bounded future Persistent Run notification facts.",
            next_step="Use only the frozen event class and runtime identity.",
            evidence_paths=[contract["goal"]],
            emitter="persistent_supervisor",
            runtime_id=contract["runtime_id"],
            lifecycle_owner="persistent_supervisor",
            primary_runtime_owner="persistent_supervisor",
        )
        notification_effects[event_class] = notifier.gmail_effect_identity(prototype, notify_env)["sha256"]
    template = read_text(template_root() / "KICKOFF_TEMPLATE.md")
    replacements = {
        "__GOAL_PATH__": contract["goal"],
        "__GOAL_SHA256__": contract["goal_sha256"],
        "__RUN_KEY__": contract["run_key"],
        "__EFFECT_SHA256__": effect["sha256"],
        "__REPO__": contract["repo"],
        "__PROGRESS_NOTIFICATION_EFFECT_SHA256__": notification_effects["progress"],
        "__RUNTIME_NOTIFICATION_EFFECT_SHA256__": notification_effects["runtime_terminal"],
    }
    for marker, value in replacements.items():
        template = template.replace(marker, str(value))
    return template.rstrip() + "\n"


def start_persistent_run(
    target: Path,
    goal: str,
    *,
    expected_goal_sha256: str,
    authorization_effect_sha256: str,
    progress_notification_effect_sha256: str = "",
    runtime_notification_effect_sha256: str = "",
    state_root: Path | None = None,
    app_factory: Any = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    contract = parse_persistent_contract(target, goal)
    if contract["goal_sha256"] != expected_goal_sha256:
        raise PersistentRunError("PERSISTENT_GOAL_HASH_MISMATCH")
    effect = persistent_launch_effect(contract)
    if effect["sha256"] != authorization_effect_sha256:
        raise PersistentRunError("PERSISTENT_LAUNCH_AUTHORIZATION_SCOPE_MISMATCH")
    binding_path = _run_binding_path(contract, state_root=state_root)
    previous = _read_json_if_exists(binding_path)
    session_active = _tmux_has_session(contract["session_name"], runner=runner)
    if previous is not None:
        compatible = (
            previous.get("goal_sha256") == contract["goal_sha256"]
            and previous.get("effect_sha256") == effect["sha256"]
            and previous.get("session_name") == contract["session_name"]
        )
        if session_active and compatible:
            previous["last_resumed_at"] = _utc_now()
            _atomic_json(binding_path, previous)
            return {**previous, "status": "RESUMED_EXISTING_RUN", "binding_path": binding_path.as_posix()}
        if session_active:
            raise PersistentRunError("PERSISTENT_RUN_CONFLICTING_ACTIVE_BINDING")

    if app_factory is None:
        from .codex_progress_thread import JsonRpcProxy

        app_factory = JsonRpcProxy
    neutral_cwd = state_home(state_root) / "persistent-run" / "reader-neutral"
    neutral_cwd.mkdir(parents=True, exist_ok=True)
    try:
        from .codex_progress_thread import start_progress_display_thread

        with app_factory() as app:
            progress_thread_id = start_progress_display_thread(app, neutral_cwd=neutral_cwd)
    except Exception as exc:
        raise PersistentRunError(f"PROGRESS_THREAD_SHARED_APP_SERVER_UNAVAILABLE: {exc}") from exc

    binding = {
        "schema": "ai-bridge.persistent_run.binding.v1",
        **contract,
        "effect_sha256": effect["sha256"],
        "binding_path": binding_path.as_posix(),
        "state_root": state_home(state_root).as_posix(),
        "progress_thread_id": progress_thread_id,
        "progress_thread_isolation": "STRUCTURED_TOOL_FREE_CONFIG_REQUESTED",
        "lifecycle_owner": "persistent_supervisor",
        "status": "launching",
        "started_at": _utc_now(),
        "reader_turns_used": 0,
        "notification_effect_sha256": {
            "progress": progress_notification_effect_sha256,
            "runtime_terminal": runtime_notification_effect_sha256,
        },
    }
    _atomic_json(binding_path, binding)
    supervisor = [
        sys.executable,
        "-m",
        "ai_bridge_kit.persistent_run",
        "supervise",
        "--binding",
        binding_path.as_posix(),
    ]
    result = runner(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            contract["session_name"],
            "-c",
            contract["working_directory"],
            shlex.join(supervisor),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        binding["status"] = "launch_failed"
        binding["launch_error"] = (result.stderr or result.stdout or "tmux launch failed").strip()
        _atomic_json(binding_path, binding)
        raise PersistentRunError(f"PERSISTENT_TMUX_LAUNCH_FAILED: {binding['launch_error']}")
    binding["status"] = "active"
    binding["tmux_command"] = ["tmux", "new-session", "-d", "-s", contract["session_name"]]
    _atomic_json(binding_path, binding)
    return {**binding, "status": "STARTED_NEW_RUN", "binding_path": binding_path.as_posix()}


def _binding_for_goal(target: Path, goal: str, *, state_root: Path | None = None) -> tuple[dict[str, Any], Path]:
    contract = parse_persistent_contract(target, goal)
    path = _run_binding_path(contract, state_root=state_root)
    binding = _read_json_if_exists(path)
    if binding is None:
        raise PersistentRunError("PERSISTENT_RUN_BINDING_UNAVAILABLE")
    return binding, path


def status_persistent_run(
    target: Path,
    goal: str,
    *,
    state_root: Path | None = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    binding, path = _binding_for_goal(target, goal, state_root=state_root)
    active = _tmux_has_session(str(binding.get("session_name") or ""), runner=runner)
    progress: dict[str, Any] | str = "UNKNOWN"
    source = binding.get("progress_source")
    if isinstance(source, str) and source != "NONE" and Path(source).is_file():
        try:
            progress = normalize_progress_file(Path(source))
        except PersistentRunError:
            progress = "UNKNOWN"
    return {
        "schema": "ai-bridge.persistent_run.status.v1",
        "availability": "active" if active else ("terminal" if binding.get("status") == "terminal" else "unavailable"),
        "run_key": binding.get("run_key"),
        "session_name": binding.get("session_name"),
        "lifecycle_owner": binding.get("lifecycle_owner"),
        "goal": binding.get("goal"),
        "goal_sha256": binding.get("goal_sha256"),
        "progress": progress,
        "reporter_active": active and binding.get("status") == "active",
        "progress_thread_id": binding.get("progress_thread_id"),
        "progress_thread_isolation": binding.get("progress_thread_isolation"),
        "reader_layer": binding.get("reader_layer", "UNKNOWN"),
        "last_delivery_at": binding.get("last_delivery_at", "UNKNOWN"),
        "last_delivery_reason": binding.get("last_delivery_reason", "UNKNOWN"),
        "terminal_status": binding.get("terminal_status", "UNKNOWN"),
        "exit_code": binding.get("exit_code", "UNKNOWN"),
        "binding_path": path.as_posix(),
    }


def _supervisor_delivery(binding: dict[str, Any], event: dict[str, Any], binding_path: Path) -> None:
    from .codex_progress_thread import JsonRpcProxy
    from . import notifier

    neutral = Path(str(binding.get("state_root") or state_home())) / "persistent-run" / "reader-neutral"
    neutral.mkdir(parents=True, exist_ok=True)
    try:
        with JsonRpcProxy() as app:
            delivery = notifier.deliver_canonical_event(
                event,
                intents=binding.get("notification_intents"),
                output_dir=binding_path.parent / "notifications" / str(event.get("event_class")) / str(event.get("runtime_id") or "progress"),
                expected_effect_sha256=str(
                    (binding.get("notification_effect_sha256") or {}).get(str(event.get("event_class")), "")
                    if isinstance(binding.get("notification_effect_sha256"), dict)
                    else ""
                ),
                app=app,
                neutral_cwd=neutral,
                language="zh-CN",
                reader_turns_used=int(binding.get("reader_turns_used") or 0),
                reader_render_max_turns=int(binding.get("reader_render_max_turns") or 0),
                progress_thread_id=str(binding.get("progress_thread_id") or "") or None,
            )
        rendered = delivery.get("reader") if isinstance(delivery.get("reader"), dict) else {}
        binding["reader_turns_used"] = rendered.get("reader_turns_used", binding.get("reader_turns_used", 0))
        binding["reader_layer"] = rendered.get("reader_layer", "DEGRADED_FALLBACK")
        binding["reader_failure_reason"] = rendered.get("failure", "")
        binding["notification_delivery_status"] = delivery.get("status", "UNKNOWN")
        binding["last_delivery_at"] = _utc_now()
        binding["last_delivery_reason"] = event.get("subtype") or event.get("event_class")
    except Exception as exc:
        binding["reader_layer"] = "DEGRADED_FALLBACK"
        binding["reader_failure_reason"] = f"DISPLAY_INJECTION_FAILED: {exc}"
    _atomic_json(binding_path, binding)


def supervise_binding(binding_path: Path) -> int:
    binding = _read_json_if_exists(binding_path)
    if binding is None:
        raise PersistentRunError("supervisor binding is missing")
    argv = binding.get("launch_argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise PersistentRunError("supervisor binding launch argv is invalid")
    from . import notifier

    started = _utc_now()
    child = subprocess.Popen(argv, cwd=str(binding["working_directory"]))
    binding["primary_pid"] = child.pid
    binding["status"] = "active"
    _atomic_json(binding_path, binding)
    start_event = notifier.canonical_event(
        event_class="progress",
        subtype="start",
        project=Path(str(binding["repo"])).name,
        task_key=str(binding["run_key"]),
        status="running",
        key_conclusion="Persistent Run primary runtime started.",
        evidence_paths=[binding_path.as_posix()],
        next_step="Continue using project-native progress evidence.",
        emitter="persistent_supervisor",
        runtime_id=str(binding["runtime_id"]),
        lifecycle_owner="persistent_supervisor",
        primary_runtime_owner="persistent_supervisor",
    )
    _supervisor_delivery(binding, start_event, binding_path)
    interval = int(binding.get("report_interval_seconds") or 3600)
    while True:
        try:
            exit_code = child.wait(timeout=interval)
            break
        except subprocess.TimeoutExpired:
            source = binding.get("progress_source")
            if isinstance(source, str) and source != "NONE" and Path(source).is_file():
                report = report_progress_file(Path(source), state_root=Path(str(binding.get("state_root") or state_home())))
                if report["delivery_decision"] == "deliver":
                    _supervisor_delivery(binding, report["canonical_event"], binding_path)
    ended = _utc_now()
    binding["status"] = "terminal"
    binding["terminal_status"] = "success" if exit_code == 0 else "failed"
    binding["exit_code"] = exit_code
    binding["ended_at"] = ended
    _atomic_json(binding_path, binding)
    terminal_event = notifier.canonical_event(
        event_class="runtime_terminal",
        project=Path(str(binding["repo"])).name,
        task_key=str(binding["run_key"]),
        status=str(binding["terminal_status"]),
        key_conclusion=f"Persistent Run primary runtime exited with code {exit_code}.",
        evidence_paths=[binding_path.as_posix()],
        next_step="Evaluate the original Goal completion criteria separately.",
        emitter="persistent_supervisor",
        runtime_id=str(binding["runtime_id"]),
        lifecycle_owner="persistent_supervisor",
        primary_runtime_owner="persistent_supervisor",
        started_at=started,
        ended_at=ended,
        terminal_status=str(binding["terminal_status"]),
        exit_code=exit_code,
    )
    _supervisor_delivery(binding, terminal_event, binding_path)
    return exit_code


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
    start = sub.add_parser("start", help="Idempotently start or resume one frozen terminal-owned tmux run.")
    start.add_argument("--target", type=Path, default=Path.cwd())
    start.add_argument("--goal", required=True)
    start.add_argument("--expected-goal-sha256", required=True)
    start.add_argument("--authorization-effect-sha256", required=True)
    start.add_argument("--progress-notification-effect-sha256", default="")
    start.add_argument("--runtime-notification-effect-sha256", default="")
    start.add_argument("--state-home", type=Path)
    status = sub.add_parser("status", help="Show truthful machine-local status for one frozen Persistent Run.")
    status.add_argument("--target", type=Path, default=Path.cwd())
    status.add_argument("--goal", required=True)
    status.add_argument("--state-home", type=Path)
    progress = sub.add_parser("progress", help="Normalize project-native Persistent Run progress evidence.")
    progress.add_argument("--evidence", type=Path, required=True)
    progress.add_argument("--stalled-after-seconds", type=int)
    report = sub.add_parser("report", help="Record and compare a project-native Persistent Run progress event.")
    report.add_argument("--progress", type=Path, required=True)
    report.add_argument("--state-home", type=Path)
    report.add_argument("--history-limit", type=int, default=20)
    report.add_argument("--stalled-after-seconds", type=int)
    latest = sub.add_parser("latest", help="Read the latest recorded Persistent Run report for a progress source.")
    latest.add_argument("--progress", type=Path, required=True)
    latest.add_argument("--state-home", type=Path)
    supervise = sub.add_parser("supervise", help=argparse.SUPPRESS)
    supervise.add_argument("--binding", type=Path, required=True)
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
                        authorization_effect_sha256=args.authorization_effect_sha256,
                        progress_notification_effect_sha256=args.progress_notification_effect_sha256,
                        runtime_notification_effect_sha256=args.runtime_notification_effect_sha256,
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
                    status_persistent_run(args.target, args.goal, state_root=args.state_home),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "progress":
            print(json.dumps(normalize_progress_file(args.evidence, stalled_after_seconds=args.stalled_after_seconds), ensure_ascii=False, indent=2, sort_keys=True))
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
        if args.command == "supervise":
            return supervise_binding(args.binding.expanduser().resolve())
    except PersistentRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
