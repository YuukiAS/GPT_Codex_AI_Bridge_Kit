from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import smtplib
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable


VALID_TERMINAL_STATUSES = {"complete", "blocked", "awaiting_human"}
LEGACY_BRIEF_SCHEMA = "ai-bridge.notification_brief.v1"
STRUCTURED_BRIEF_SCHEMA = "ai-bridge.notification_brief.v2"
VALID_BRIEF_SCHEMAS = {LEGACY_BRIEF_SCHEMA, STRUCTURED_BRIEF_SCHEMA}
VALID_EVENT_TYPES = {"terminal", "awaiting_human", "operational_blocked", "operational_progress", "milestone"}
SEMANTIC_DECISION_AUTHORITIES = {"Planner", "Reviewer", "Critic", "Final Critic"}
OPERATIONAL_DECISION_AUTHORITIES = {"Controller", "Watcher"}
COMMON_BRIEF_FIELDS = {
    "schema",
    "project",
    "task_key",
    "key_conclusion",
    "next_step",
    "evidence_paths",
}
LEGACY_REQUIRED_BRIEF_FIELDS = COMMON_BRIEF_FIELDS | {"terminal_status"}
STRUCTURED_REQUIRED_BRIEF_FIELDS = COMMON_BRIEF_FIELDS | {"event_type", "status", "decision_authority"}
MACHINE_HOME = Path.home() / ".ai-bridge"
STATE_PATH = MACHINE_HOME / "state" / "notifier" / "legacy.json"
PRIVATE_ENV_PATH = MACHINE_HOME / "private" / "notifier.env"
NOTIFICATION_REQUEST_SCHEMA = "ai-bridge.notification_request.v1"
AUTO_CONSUMERS = {"lite", "review", "control", "persistent"}
AUTO_FIELDS = {
    "schema",
    "project",
    "task_key",
    "consumer",
    "fact_class",
    "status",
    "decision_authority",
    "summary",
    "next_action",
    "stage",
    "completed",
    "total",
    "fraction",
    "eta",
    "eta_low",
    "eta_high",
    "duration_seconds",
    "branch",
    "version",
    "run_id",
    "runtime_id",
    "source_event_id",
    "recipient_override",
}
AUTO_REQUIRED_FIELDS = {
    "schema",
    "project",
    "task_key",
    "consumer",
    "fact_class",
    "status",
    "decision_authority",
    "summary",
    "next_action",
    "source_event_id",
}
AUTO_DELIVER_DEADLINE_SECONDS = 120.0
STATUS_LABELS = {
    "complete": "完成",
    "blocked": "阻塞",
    "awaiting_human": "等待人工确认",
}
EVENT_TYPE_LABELS = {
    "terminal": "终态",
    "awaiting_human": "等待人工确认",
    "operational_blocked": "运行阻塞",
    "operational_progress": "运行进展",
    "milestone": "里程碑",
}
OPTIONAL_LABELS = {
    "commit_status": "commit",
    "push_status": "push",
    "duration": "运行时长",
    "branch": "branch",
    "version": "version",
}


@dataclass(frozen=True)
class NotifierResult:
    status: str
    event_key: str = ""
    message: str = ""


def machine_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.environ.get("AI_BRIDGE_STATE_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".ai-bridge").resolve()


def machine_config_path(config_root: Path | None = None) -> Path:
    return machine_home(config_root) / "private" / "notifier.env"


def notifier_state_root(state_root: Path | None = None) -> Path:
    return machine_home(state_root) / "state" / "notifier"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(payload)
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema": "ai-bridge.notifier.state.v1",
            "sent": {},
            "last_success": None,
            "last_failure": None,
            "baseline_initialized": False,
            "baseline_events": {},
        }
    try:
        state = load_json(path)
    except json.JSONDecodeError:
        state = {}
    state.setdefault("schema", "ai-bridge.notifier.state.v1")
    state.setdefault("sent", {})
    state.setdefault("last_success", None)
    state.setdefault("last_failure", None)
    state.setdefault("baseline_initialized", False)
    state.setdefault("baseline_events", {})
    return state


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def notifier_env(
    env: dict[str, str] | None = None,
    env_file: Path | None = None,
    *,
    config_root: Path | None = None,
) -> dict[str, str]:
    """Load the one machine config; explicit ``env`` is test dependency injection only."""
    path = env_file if env_file is not None else machine_config_path(config_root)
    merged = load_env_file(path)
    if env is not None:
        merged.update(env)
    return merged


def validate_brief(brief: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = str(brief.get("schema", "")).strip()
    if schema not in VALID_BRIEF_SCHEMAS:
        errors.append("schema must be one of: " + ", ".join(sorted(VALID_BRIEF_SCHEMAS)))
    required = LEGACY_REQUIRED_BRIEF_FIELDS if schema != STRUCTURED_BRIEF_SCHEMA else STRUCTURED_REQUIRED_BRIEF_FIELDS
    missing = sorted(required - set(brief))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if schema == STRUCTURED_BRIEF_SCHEMA:
        event_type = str(brief.get("event_type", "")).strip()
        if event_type not in VALID_EVENT_TYPES:
            errors.append("event_type must be one of: " + ", ".join(sorted(VALID_EVENT_TYPES)))
        status = str(brief.get("status", "")).strip()
        if not status:
            errors.append("status must be a non-empty string")
        authority = str(brief.get("decision_authority", "")).strip()
        if event_type in {"operational_blocked", "operational_progress"}:
            if authority not in OPERATIONAL_DECISION_AUTHORITIES:
                errors.append(f"{event_type} decision_authority must be Controller or Watcher")
            status_upper = str(brief.get("status", "")).strip().upper()
            if status_upper in {"PASS", "READY", "RELEASE_READY", "COMPLETE"}:
                errors.append(f"{event_type} status must not claim semantic PASS/READY/release completion")
        elif event_type in VALID_EVENT_TYPES and authority not in SEMANTIC_DECISION_AUTHORITIES:
            errors.append("semantic notification decision_authority must be Planner, Reviewer, Critic, or Final Critic")
    else:
        terminal_status = str(brief.get("terminal_status", "")).strip().lower()
        if terminal_status not in VALID_TERMINAL_STATUSES:
            errors.append("terminal_status must be one of: " + ", ".join(sorted(VALID_TERMINAL_STATUSES)))
    evidence_paths = brief.get("evidence_paths")
    if not isinstance(evidence_paths, list) or not evidence_paths:
        errors.append("evidence_paths must be a non-empty list")
    for item in evidence_paths if isinstance(evidence_paths, list) else []:
        if not isinstance(item, str) or not item.strip():
            errors.append("evidence_paths entries must be non-empty strings")
            break
    return errors


def brief_digest(brief: dict[str, Any]) -> str:
    canonical = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def brief_event_type(brief: dict[str, Any]) -> str:
    if brief.get("schema") == STRUCTURED_BRIEF_SCHEMA:
        return str(brief.get("event_type", "")).strip()
    terminal_status = str(brief.get("terminal_status", "")).strip().lower()
    return "awaiting_human" if terminal_status == "awaiting_human" else "terminal"


def brief_status_value(brief: dict[str, Any]) -> str:
    if brief.get("schema") == STRUCTURED_BRIEF_SCHEMA:
        return str(brief.get("status", "")).strip()
    return str(brief.get("terminal_status", "")).strip().lower()


def event_key(brief: dict[str, Any]) -> str:
    parts = [
        str(brief.get("project", "")),
        str(brief.get("task_key", "")),
        brief_event_type(brief),
        brief_status_value(brief).lower(),
        brief_digest(brief),
    ]
    return "|".join(parts)


def recipients(env: dict[str, str]) -> list[str]:
    raw = env.get("AI_BRIDGE_NOTIFY_TO", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def require_email_config(env: dict[str, str]) -> list[str]:
    missing = []
    for key in ["AI_BRIDGE_NOTIFY_SMTP_USER", "AI_BRIDGE_NOTIFY_SMTP_PASSWORD"]:
        if not env.get(key):
            missing.append(key)
    if not env.get("AI_BRIDGE_NOTIFY_FROM") and not env.get("AI_BRIDGE_NOTIFY_SMTP_USER"):
        missing.append("AI_BRIDGE_NOTIFY_FROM")
    if not recipients(env):
        missing.append("AI_BRIDGE_NOTIFY_TO")
    return missing


def validate_machine_config(
    *,
    config_root: Path | None = None,
    config: dict[str, str] | None = None,
) -> dict[str, Any]:
    path = machine_config_path(config_root)
    values = dict(config) if config is not None else load_env_file(path)
    errors = require_email_config(values)
    for key, value in values.items():
        if key.startswith("AI_BRIDGE_NOTIFY_") and ("\r" in value or "\n" in value):
            errors.append(f"{key} contains a forbidden newline")
    mode = None
    if config is None and path.exists():
        mode = path.stat().st_mode & 0o777
        if mode != 0o600:
            errors.append(f"machine config mode must be 0600, found {mode:04o}")
    return {
        "status": "VALID" if not errors else "INVALID",
        "config_path": path.as_posix(),
        "mode": mode,
        "missing_or_invalid": sorted(set(errors)),
        "config": values,
    }


def redacted_config_digest(values: dict[str, str]) -> str:
    transport = {
        key: values[key]
        for key in sorted(values)
        if key.startswith("AI_BRIDGE_NOTIFY_")
    }
    return hashlib.sha256(
        json.dumps(transport, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def readiness_path(state_root: Path | None = None) -> Path:
    return notifier_state_root(state_root) / "readiness.json"


def notifier_readiness(
    *,
    config_root: Path | None = None,
    state_root: Path | None = None,
    config: dict[str, str] | None = None,
) -> dict[str, Any]:
    validation = validate_machine_config(config_root=config_root, config=config)
    values = validation.pop("config")
    digest = redacted_config_digest(values) if not validation["missing_or_invalid"] else ""
    evidence = None
    path = readiness_path(state_root)
    if path.is_file():
        try:
            evidence = load_json(path)
        except (OSError, json.JSONDecodeError):
            evidence = None
    ready = bool(
        validation["status"] == "VALID"
        and evidence
        and evidence.get("config_digest") == digest
        and evidence.get("transport_test_accepted_at")
    )
    return {
        **validation,
        "config_digest": digest,
        "transport_ready": ready,
        "transport_test_accepted_at": evidence.get("transport_test_accepted_at") if evidence else None,
    }


def require_notifier_ready(
    *,
    config_root: Path | None = None,
    state_root: Path | None = None,
    config: dict[str, str] | None = None,
) -> dict[str, Any]:
    status = notifier_readiness(config_root=config_root, state_root=state_root, config=config)
    if not status["transport_ready"]:
        raise ValueError("NOTIFIER_NOT_READY: run ai-bridge notifier validate and ai-bridge notifier send-test")
    return status


def migrate_legacy(
    project: Path,
    *,
    config_root: Path | None = None,
) -> NotifierResult:
    project = project.expanduser().resolve()
    legacy = project / ".ai-bridge" / "private" / "notifier.env"
    if not legacy.is_file():
        return NotifierResult("LEGACY_CONFIG_MISSING", message=legacy.as_posix())
    values = load_env_file(legacy)
    validation = validate_machine_config(config=values)
    if validation["status"] != "VALID":
        return NotifierResult("LEGACY_CONFIG_INVALID", message="; ".join(validation["missing_or_invalid"]))
    destination = machine_config_path(config_root)
    if destination.exists():
        current_values = load_env_file(destination)
        if redacted_config_digest(current_values) == redacted_config_digest(values):
            return NotifierResult("NOOP_ALREADY_MIGRATED", message=destination.as_posix())
        return NotifierResult("MACHINE_CONFIG_CONFLICT", message="machine config exists with a different digest")
    atomic_write_bytes(destination, legacy.read_bytes(), mode=0o600)
    return NotifierResult("MIGRATED", message=destination.as_posix())


def _bounded_auto_string(name: str, value: Any, *, maximum: int = 1024, required: bool = False) -> str:
    text = str(value or "")
    if required and not text:
        raise ValueError(f"NotificationRequest {name} is required")
    if len(text.encode("utf-8")) > maximum:
        raise ValueError(f"NotificationRequest {name} exceeds {maximum} bytes")
    if "\r" in text or "\n" in text:
        raise ValueError(f"NotificationRequest {name} contains a forbidden newline")
    return text


def validate_notification_request(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    extra = sorted(set(request) - AUTO_FIELDS)
    missing = sorted(AUTO_REQUIRED_FIELDS - set(request))
    if extra:
        errors.append("unsupported automatic fields: " + ", ".join(extra))
    if missing:
        errors.append("missing automatic fields: " + ", ".join(missing))
    if request.get("schema") != NOTIFICATION_REQUEST_SCHEMA:
        errors.append(f"schema must be {NOTIFICATION_REQUEST_SCHEMA}")
    if request.get("consumer") not in AUTO_CONSUMERS:
        errors.append("consumer must be lite, review, control, or persistent")
    for name in AUTO_FIELDS & set(request):
        value = request.get(name)
        if isinstance(value, str):
            try:
                _bounded_auto_string(name, value, maximum=2048 if name in {"summary", "next_action"} else 512)
            except ValueError as exc:
                errors.append(str(exc))
    for name in ("completed", "total"):
        if name in request and request[name] is not None and (not isinstance(request[name], int) or request[name] < 0):
            errors.append(f"{name} must be a non-negative integer")
    if request.get("completed") is not None and request.get("total") is not None and request["completed"] > request["total"]:
        errors.append("completed must not exceed total")
    if request.get("fraction") is not None:
        fraction = request["fraction"]
        if not isinstance(fraction, (int, float)) or not 0 <= float(fraction) <= 1:
            errors.append("fraction must be between 0 and 1")
    consumer = request.get("consumer")
    authority = request.get("decision_authority")
    fact_class = str(request.get("fact_class") or "")
    if consumer in {"lite", "persistent"}:
        if authority != "Runtime" or not fact_class.startswith("runtime_"):
            errors.append(f"{consumer} may send runtime facts only with decision_authority=Runtime")
    if consumer == "review" and authority != "Reviewer":
        errors.append("review notification authority must be Reviewer")
    if consumer == "control" and authority not in SEMANTIC_DECISION_AUTHORITIES:
        errors.append("control notification authority must be an existing semantic role")
    status = str(request.get("status") or "")
    if consumer in {"lite", "persistent"} and re.search(r"(?i)(^|\W)(PASS|READY|RELEASE_READY|COMPLETE)(\W|$)", status):
        errors.append("runtime status must not claim semantic PASS/READY/release completion")
    return errors


def notification_request(**facts: Any) -> dict[str, Any]:
    request = {"schema": NOTIFICATION_REQUEST_SCHEMA, **facts}
    errors = validate_notification_request(request)
    if errors:
        raise ValueError("; ".join(errors))
    return request


def parse_notification_policy_text(text: str) -> dict[str, str]:
    match = re.search(r"(?ms)^## Notification\s*$\n(.*?)(?=^## |\Z)", text)
    if not match:
        raise ValueError("Notification section missing")
    fields: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip().removeprefix("-").strip()
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip().lower().replace(" ", "_")] = value.strip()
    notify = fields.get("notify", "").upper()
    recipient = fields.get("recipient_override", "")
    if notify not in {"OFF", "ON"}:
        raise ValueError("Notification Notify must be OFF or ON")
    if not recipient:
        raise ValueError("Notification Recipient override must be NONE or an explicit address")
    if recipient != "NONE" and ("@" not in recipient or "\r" in recipient or "\n" in recipient):
        raise ValueError("Notification Recipient override is invalid")
    return {"notify": notify, "recipient_override": "" if recipient == "NONE" else recipient}


def expression_facts(request: dict[str, Any]) -> dict[str, Any]:
    errors = validate_notification_request(request)
    if errors:
        raise ValueError("; ".join(errors))
    return {key: value for key, value in request.items() if key != "recipient_override"}


def resolve_recipient(request: dict[str, Any], config: dict[str, str]) -> str:
    override = str(request.get("recipient_override") or "").strip()
    resolved = override or ",".join(recipients(config))
    return _bounded_auto_string("resolved_recipient", resolved, maximum=512, required=True)


def auto_event_key(request: dict[str, Any], *, repo_identity: str, resolved_recipient: str) -> str:
    payload = {
        "repo_identity": repo_identity,
        "task_key": request["task_key"],
        "consumer": request["consumer"],
        "fact_class": request["fact_class"],
        "source_event_id": request["source_event_id"],
        "runtime_id": request.get("runtime_id", ""),
        "resolved_recipient": resolved_recipient,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def event_directory(event_key_value: str, *, state_root: Path | None = None) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", event_key_value):
        raise ValueError("event key must be 64 lowercase hex")
    return notifier_state_root(state_root) / "events" / event_key_value


def claim_event(
    request: dict[str, Any],
    *,
    repo_identity: str,
    config: dict[str, str],
    state_root: Path | None = None,
) -> tuple[str, Path, str]:
    errors = validate_notification_request(request)
    if errors:
        raise ValueError("; ".join(errors))
    recipient = resolve_recipient(request, config)
    key = auto_event_key(request, repo_identity=repo_identity, resolved_recipient=recipient)
    directory = event_directory(key, state_root=state_root)
    directory.mkdir(parents=True, exist_ok=True)
    claim = directory / "claim.json"
    payload = {
        "schema": "ai-bridge.notifier.claim.v1",
        "event_key": key,
        "claimed_at": utc_now(),
        "repo_identity": repo_identity,
        "resolved_recipient": recipient,
        "request": request,
    }
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return "DUPLICATE", directory, recipient
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return "CLAIMED", directory, recipient


def subject_for_brief(brief: dict[str, Any], env: dict[str, str], *, test: bool = False) -> str:
    prefix = env.get("AI_BRIDGE_NOTIFY_SUBJECT_PREFIX", "[AI Bridge]")
    if brief.get("schema") == STRUCTURED_BRIEF_SCHEMA:
        status_label_text = status_label(brief)
    else:
        status = str(brief.get("terminal_status", "")).strip().lower()
        status_label_text = STATUS_LABELS.get(status, status or "未知状态")
    task = str(brief.get("task_key", "unknown"))
    if test:
        return f"{prefix} 测试邮件：{task}"
    return f"{prefix} {status_label_text}：{task}"


def status_label(brief: dict[str, Any]) -> str:
    status = brief_status_value(brief)
    label = STATUS_LABELS.get(status.lower(), status or "未知状态")
    raw = status or "unknown"
    if brief.get("schema") == STRUCTURED_BRIEF_SCHEMA and label == raw:
        return label
    return f"{label}（{raw}）"


def render_plain(brief: dict[str, Any]) -> str:
    evidence = brief.get("evidence_paths") if isinstance(brief.get("evidence_paths"), list) else []
    event_type = brief_event_type(brief)
    event_label = EVENT_TYPE_LABELS.get(event_type, event_type or "通知")
    lines = [
        f"状态：{status_label(brief)}",
        f"结论：{str(brief.get('key_conclusion', '')).strip()}",
        f"你现在需要做什么：{brief.get('next_step', '')}",
        "",
        f"项目：{brief.get('project', 'unknown')}",
        f"任务：{brief.get('task_key', 'unknown')}",
        f"事件：{event_label}",
    ]
    if brief.get("decision_authority"):
        lines.append(f"语义/状态来源：{brief['decision_authority']}")
    for key, label in OPTIONAL_LABELS.items():
        if brief.get(key):
            lines.append(f"{label}：{brief[key]}")
    jobs = brief.get("jobs")
    if isinstance(jobs, list) and jobs:
        lines.extend(["", "作业概览"])
        for item in jobs[:8]:
            if isinstance(item, dict):
                summary = "；".join(f"{key}={value}" for key, value in item.items())
                lines.append(f"- {summary}")
            else:
                lines.append(f"- {item}")
    lines.extend(["", "可检查"])
    lines.extend(str(item) for item in evidence[:8])
    details = brief.get("details")
    if isinstance(details, str) and details.strip():
        lines.extend(["", "备注", details.strip()[:1000]])
    return "\n".join(lines).strip() + "\n"


def render_html(brief: dict[str, Any]) -> str:
    evidence = brief.get("evidence_paths") if isinstance(brief.get("evidence_paths"), list) else []
    evidence_items = "\n".join(f"<li>{html.escape(str(item))}</li>" for item in evidence[:8])
    event_type = brief_event_type(brief)
    event_label = EVENT_TYPE_LABELS.get(event_type, event_type or "通知")
    rows = []
    if brief.get("decision_authority"):
        rows.append(f"<p><strong>语义/状态来源：</strong>{html.escape(str(brief['decision_authority']))}</p>")
    for key, label in OPTIONAL_LABELS.items():
        if brief.get(key):
            rows.append(f"<p><strong>{html.escape(label)}：</strong>{html.escape(str(brief[key]))}</p>")
    jobs = brief.get("jobs")
    jobs_html = ""
    if isinstance(jobs, list) and jobs:
        job_items = []
        for item in jobs[:8]:
            if isinstance(item, dict):
                summary = "；".join(f"{key}={value}" for key, value in item.items())
                job_items.append(f"<li>{html.escape(summary)}</li>")
            else:
                job_items.append(f"<li>{html.escape(str(item))}</li>")
        jobs_html = "<h2>作业概览</h2><ul>" + "\n".join(job_items) + "</ul>"
    details = brief.get("details")
    detail_html = ""
    if isinstance(details, str) and details.strip():
        detail_html = f"<h2>备注</h2><p>{html.escape(details.strip()[:1000])}</p>"
    return (
        "<html><body>"
        f"<p><strong>状态：</strong>{html.escape(status_label(brief))}</p>"
        f"<p><strong>结论：</strong>{html.escape(str(brief.get('key_conclusion', '')))}</p>"
        f"<p><strong>你现在需要做什么：</strong>{html.escape(str(brief.get('next_step', '')))}</p>"
        f"<p><strong>项目：</strong>{html.escape(str(brief.get('project', 'unknown')))}</p>"
        f"<p><strong>任务：</strong>{html.escape(str(brief.get('task_key', 'unknown')))}</p>"
        f"<p><strong>事件：</strong>{html.escape(event_label)}</p>"
        + "".join(rows)
        + jobs_html
        + f"<h2>可检查</h2><ul>{evidence_items}</ul>"
        + detail_html
        + "</body></html>"
    )


def build_email_message(brief: dict[str, Any], env: dict[str, str], *, test: bool = False) -> EmailMessage:
    message = EmailMessage()
    sender = env.get("AI_BRIDGE_NOTIFY_FROM") or env.get("AI_BRIDGE_NOTIFY_SMTP_USER", "")
    message["From"] = sender
    message["To"] = ", ".join(recipients(env))
    message["Subject"] = subject_for_brief(brief, env, test=test)
    expressed = brief.get("_clear_writing_text")
    if isinstance(expressed, str) and expressed.strip():
        plain = expressed.strip() + "\n"
        rich = f"<html><body><p>{html.escape(expressed.strip()).replace(chr(10), '<br>')}</p></body></html>"
    else:
        plain = render_plain(brief)
        rich = render_html(brief)
    message.set_content(plain)
    message.add_alternative(rich, subtype="html")
    return message


def send_email(
    brief: dict[str, Any],
    env: dict[str, str],
    *,
    test: bool = False,
    timeout: float = 30,
) -> None:
    missing = require_email_config(env)
    if missing:
        raise ValueError("missing email config: " + ", ".join(missing))
    message = build_email_message(brief, env, test=test)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=max(0.1, timeout)) as smtp:
        smtp.starttls()
        smtp.login(env["AI_BRIDGE_NOTIFY_SMTP_USER"], env["AI_BRIDGE_NOTIFY_SMTP_PASSWORD"])
        smtp.send_message(message)


def render_auto_plain(request: dict[str, Any]) -> str:
    facts = expression_facts(request)
    labels = [
        ("状态", "status"),
        ("结论", "summary"),
        ("下一步", "next_action"),
        ("项目", "project"),
        ("任务", "task_key"),
        ("消费者", "consumer"),
        ("事实类型", "fact_class"),
        ("事实来源", "decision_authority"),
        ("阶段", "stage"),
        ("完成数", "completed"),
        ("总数", "total"),
        ("比例", "fraction"),
        ("ETA", "eta"),
        ("ETA 下界", "eta_low"),
        ("ETA 上界", "eta_high"),
        ("运行秒数", "duration_seconds"),
        ("branch", "branch"),
        ("version", "version"),
        ("run_id", "run_id"),
        ("runtime_id", "runtime_id"),
    ]
    return "\n".join(f"{label}：{facts[key]}" for label, key in labels if facts.get(key) not in {None, ""}) + "\n"


def build_auto_email(
    request: dict[str, Any],
    config: dict[str, str],
    *,
    resolved_recipient: str,
    expressed: str,
) -> EmailMessage:
    errors = validate_notification_request(request)
    if errors:
        raise ValueError("; ".join(errors))
    sender = config.get("AI_BRIDGE_NOTIFY_FROM") or config.get("AI_BRIDGE_NOTIFY_SMTP_USER", "")
    prefix = _bounded_auto_string(
        "subject_prefix",
        config.get("AI_BRIDGE_NOTIFY_SUBJECT_PREFIX", "[AI Bridge]"),
        maximum=128,
        required=True,
    )
    message = EmailMessage()
    message["From"] = _bounded_auto_string("from", sender, maximum=320, required=True)
    message["To"] = _bounded_auto_string("to", resolved_recipient, maximum=512, required=True)
    message["Subject"] = f"{prefix} {request['status']}：{request['task_key']}"
    body = expressed.strip() + "\n"
    message.set_content(body)
    message.add_alternative(f"<html><body><p>{html.escape(body.strip()).replace(chr(10), '<br>')}</p></body></html>", subtype="html")
    return message


def send_auto_email(
    request: dict[str, Any],
    config: dict[str, str],
    *,
    resolved_recipient: str,
    expressed: str,
    timeout: float,
) -> None:
    missing = require_email_config(config)
    if missing:
        raise ValueError("missing email config: " + ", ".join(missing))
    message = build_auto_email(request, config, resolved_recipient=resolved_recipient, expressed=expressed)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=max(0.1, timeout)) as smtp:
        smtp.starttls()
        smtp.login(config["AI_BRIDGE_NOTIFY_SMTP_USER"], config["AI_BRIDGE_NOTIFY_SMTP_PASSWORD"])
        smtp.send_message(message)


def _attempt_path(directory: Path, attempt_id: str) -> Path:
    return directory / "attempts" / f"{attempt_id}.json"


def _write_attempt(directory: Path, attempt: dict[str, Any]) -> None:
    write_json(_attempt_path(directory, str(attempt["attempt_id"])), attempt)
    write_json(directory / "latest.json", attempt)


def _read_latest_attempt(directory: Path) -> dict[str, Any] | None:
    path = directory / "latest.json"
    if not path.is_file():
        return None
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def deliver_event_inline(
    directory: Path,
    *,
    config_root: Path | None = None,
    config: dict[str, str] | None = None,
    deadline_seconds: float = AUTO_DELIVER_DEADLINE_SECONDS,
    expression_runner: Callable[..., Any] = subprocess.run,
    sender: Callable[..., None] | None = None,
    parent_attempt_id: str | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> NotifierResult:
    claim = load_json(directory / "claim.json")
    request = claim.get("request")
    if not isinstance(request, dict):
        return NotifierResult("FAILED", event_key=str(claim.get("event_key") or ""), message="frozen request missing")
    errors = validate_notification_request(request)
    if errors:
        return NotifierResult("FAILED", event_key=str(claim.get("event_key") or ""), message="; ".join(errors))
    active_config = dict(config) if config is not None else notifier_env(config_root=config_root)
    attempt_id = uuid.uuid4().hex
    attempt = {
        "schema": "ai-bridge.notifier.attempt.v1",
        "attempt_id": attempt_id,
        "parent_attempt_id": parent_attempt_id,
        "event_key": claim["event_key"],
        "stage": "CLAIMED",
        "started_at": utc_now(),
        "config_digest": redacted_config_digest(active_config),
    }
    _write_attempt(directory, attempt)
    started = monotonic()
    fallback = render_auto_plain(request)
    attempt["stage"] = "EXPRESSION"
    _write_attempt(directory, attempt)
    from .clear_writing import render_once

    remaining = max(0.0, deadline_seconds - (monotonic() - started))
    rendered = render_once(
        expression_facts(request),
        fallback_text=fallback,
        runner=expression_runner,
        timeout_seconds=min(90.0, remaining),
    )
    attempt["expression_mode"] = rendered["mode"]
    attempt["model_invocations"] = rendered["model_invocations"]
    remaining = max(0.0, deadline_seconds - (monotonic() - started))
    if remaining <= 0:
        attempt.update(stage="FAILED_TIMEOUT_BEFORE_TRANSPORT", failed_at=utc_now())
        _write_attempt(directory, attempt)
        return NotifierResult("FAILED", event_key=claim["event_key"], message="deadline before transport")
    attempt["stage"] = "TRANSPORT_STARTED"
    attempt["transport_started_at"] = utc_now()
    _write_attempt(directory, attempt)
    send_func = sender or send_auto_email
    try:
        send_func(
            request,
            active_config,
            resolved_recipient=claim["resolved_recipient"],
            expressed=rendered["text"],
            timeout=remaining,
        )
    except Exception as exc:
        attempt.update(stage="FAILED", failed_at=utc_now(), error=f"{type(exc).__name__}: {exc}")
        _write_attempt(directory, attempt)
        return NotifierResult("FAILED", event_key=claim["event_key"], message=attempt["error"])
    attempt.update(stage="SMTP_ACCEPTED", smtp_accepted_at=utc_now())
    _write_attempt(directory, attempt)
    write_json(
        directory / "receipt.json",
        {
            "schema": "ai-bridge.notifier.receipt.v1",
            "event_key": claim["event_key"],
            "status": "SMTP_ACCEPTED",
            "smtp_accepted_at": attempt["smtp_accepted_at"],
            "attempt_id": attempt_id,
        },
    )
    return NotifierResult("SMTP_ACCEPTED", event_key=claim["event_key"], message="SMTP accepted; inbox delivery not asserted")


def _terminate_helper(process: Any) -> None:
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _run_delivery_helper(
    directory: Path,
    *,
    config_root: Path,
    deadline_seconds: float,
    parent_attempt_id: str | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
) -> NotifierResult:
    claim = load_json(directory / "claim.json")
    command = [
        sys.executable,
        "-m",
        "ai_bridge_kit.notifier",
        "_deliver-helper",
        "--event-dir",
        directory.as_posix(),
        "--config-root",
        config_root.as_posix(),
        "--deadline-seconds",
        str(deadline_seconds),
    ]
    if parent_attempt_id:
        command.extend(["--parent-attempt-id", parent_attempt_id])
    process = popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        process.wait(timeout=deadline_seconds)
    except subprocess.TimeoutExpired:
        _terminate_helper(process)
        latest = _read_latest_attempt(directory) or {}
        if latest.get("stage") == "SMTP_ACCEPTED":
            return NotifierResult("SMTP_ACCEPTED", event_key=claim["event_key"], message="SMTP accepted before helper timeout")
        if latest.get("stage") == "TRANSPORT_STARTED":
            latest.update(stage="DELIVERY_UNKNOWN", failed_at=utc_now(), error="helper deadline after transport started")
            _write_attempt(directory, latest)
            return NotifierResult("DELIVERY_UNKNOWN", event_key=claim["event_key"], message=latest["error"])
        if latest:
            latest.update(stage="FAILED_TIMEOUT_BEFORE_TRANSPORT", failed_at=utc_now(), error="helper deadline before transport")
            _write_attempt(directory, latest)
        return NotifierResult("FAILED", event_key=claim["event_key"], message="helper deadline before transport")
    latest = _read_latest_attempt(directory) or {}
    stage = str(latest.get("stage") or "FAILED")
    if stage == "SMTP_ACCEPTED":
        return NotifierResult("SMTP_ACCEPTED", event_key=claim["event_key"], message="SMTP accepted; inbox delivery not asserted")
    return NotifierResult(stage if stage in {"FAILED", "DELIVERY_UNKNOWN"} else "FAILED", event_key=claim["event_key"], message=str(latest.get("error") or f"helper exited {process.returncode}"))


def deliver_notification(
    request: dict[str, Any],
    *,
    repo_identity: str,
    config_root: Path | None = None,
    state_root: Path | None = None,
    deadline_seconds: float = AUTO_DELIVER_DEADLINE_SECONDS,
    popen: Callable[..., Any] = subprocess.Popen,
    require_ready: bool = True,
    config: dict[str, str] | None = None,
) -> NotifierResult:
    started = time.monotonic()
    active_config = dict(config) if config is not None else notifier_env(config_root=config_root)
    if require_ready:
        require_notifier_ready(config_root=config_root, state_root=state_root, config=config)
    status, directory, _recipient = claim_event(
        request,
        repo_identity=repo_identity,
        config=active_config,
        state_root=state_root,
    )
    key = directory.name
    if status == "DUPLICATE":
        latest = _read_latest_attempt(directory)
        duplicate_status = "duplicate" if latest and latest.get("stage") == "SMTP_ACCEPTED" else "in_progress_or_requires_retry"
        return NotifierResult(duplicate_status, event_key=key, message="event already claimed")
    remaining = deadline_seconds - (time.monotonic() - started)
    if remaining <= 0:
        return NotifierResult("FAILED", event_key=key, message="deadline before helper launch")
    return _run_delivery_helper(
        directory,
        config_root=machine_home(config_root),
        deadline_seconds=remaining,
        popen=popen,
    )


def retry_event(
    event_key_value: str,
    *,
    confirm_possible_duplicate: bool = False,
    config_root: Path | None = None,
    state_root: Path | None = None,
    deadline_seconds: float = AUTO_DELIVER_DEADLINE_SECONDS,
    popen: Callable[..., Any] = subprocess.Popen,
) -> NotifierResult:
    started = time.monotonic()
    directory = event_directory(event_key_value, state_root=state_root)
    latest = _read_latest_attempt(directory)
    if latest is None:
        return NotifierResult("NOT_RETRYABLE", event_key=event_key_value, message="event or attempt missing")
    stage = str(latest.get("stage") or "")
    if stage == "DELIVERY_UNKNOWN" and not confirm_possible_duplicate:
        return NotifierResult("CONFIRM_POSSIBLE_DUPLICATE_REQUIRED", event_key=event_key_value)
    if stage not in {"FAILED", "FAILED_TIMEOUT_BEFORE_TRANSPORT", "DELIVERY_UNKNOWN"}:
        return NotifierResult("NOT_RETRYABLE", event_key=event_key_value, message=f"stage={stage}")
    remaining = deadline_seconds - (time.monotonic() - started)
    if remaining <= 0:
        return NotifierResult("FAILED", event_key=event_key_value, message="deadline before retry helper launch")
    return _run_delivery_helper(
        directory,
        config_root=machine_home(config_root),
        deadline_seconds=remaining,
        parent_attempt_id=str(latest.get("attempt_id") or ""),
        popen=popen,
    )


def send_brief(
    brief_path: Path,
    *,
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
    expression: bool = False,
    expression_runner: Callable[..., Any] = subprocess.run,
    expression_codex_bin: str = "codex",
    expression_state_root: Path | None = None,
) -> NotifierResult:
    try:
        brief = load_json(brief_path)
    except (OSError, json.JSONDecodeError) as exc:
        return NotifierResult("invalid", message=f"invalid brief: {type(exc).__name__}: {exc}")
    if not isinstance(brief, dict):
        return NotifierResult("invalid", message="invalid brief: expected JSON object")
    errors = validate_brief(brief)
    if errors:
        return NotifierResult("invalid", message="; ".join(errors))
    key = event_key(brief)
    state = load_state(state_path)
    if key in state["sent"]:
        return NotifierResult("duplicate", event_key=key, message="duplicate suppressed")
    if dry_run:
        return NotifierResult("dry_run", event_key=key, message="dry-run; no email sent")
    transport_brief = brief
    expression_mode = "NOT_REQUESTED"
    if expression:
        from .clear_writing import render_once

        rendered = render_once(
            brief,
            fallback_text=render_plain(brief),
            codex_bin=expression_codex_bin,
            state_root=expression_state_root,
            runner=expression_runner,
        )
        transport_brief = dict(brief)
        transport_brief["_clear_writing_text"] = rendered["text"]
        expression_mode = str(rendered["mode"])
    active_env = notifier_env(env)
    send_func = sender or (lambda payload, merged_env: send_email(payload, merged_env))
    try:
        send_func(transport_brief, active_env)
    except Exception as exc:
        state["last_failure"] = {
            "event_key": key,
            "brief_path": str(brief_path),
            "error": f"{type(exc).__name__}: {exc}",
            "failed_at": utc_now(),
        }
        write_json(state_path, state)
        return NotifierResult("failed", event_key=key, message=state["last_failure"]["error"])
    receipt = {"brief_path": str(brief_path), "sent_at": utc_now(), "project": brief["project"], "task_key": brief["task_key"]}
    state["sent"][key] = receipt
    state["last_success"] = receipt
    write_json(state_path, state)
    return NotifierResult("sent", event_key=key, message=f"sent; expression={expression_mode}")


def terminal_briefs(root: Path = Path.cwd()) -> list[Path]:
    return sorted(root.glob("results/*/notification_brief.json"))


def notification_briefs(root: Path = Path.cwd()) -> list[Path]:
    paths = [*root.glob("results/*/notification_brief.json"), *root.glob("results/*/notifications/*.json")]
    return sorted(dict.fromkeys(paths))


def notifier_once(
    *,
    root: Path = Path.cwd(),
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
) -> list[NotifierResult]:
    state = load_state(state_path)
    briefs = notification_briefs(root)
    if not state.get("baseline_initialized"):
        for path in briefs:
            try:
                brief = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(brief, dict) and not validate_brief(brief):
                state["baseline_events"][event_key(brief)] = {"brief_path": str(path), "baselined_at": utc_now()}
        state["baseline_initialized"] = True
        write_json(state_path, state)
        return []
    results: list[NotifierResult] = []
    for path in briefs:
        try:
            brief = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(brief, dict) and event_key(brief) in state.get("baseline_events", {}):
            continue
        results.append(
            send_brief(
                path,
                state_path=state_path,
                env=env,
                dry_run=dry_run,
                sender=sender,
                expression=True,
            )
        )
    return results


def send_test(
    *,
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    config_root: Path | None = None,
    state_root: Path | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
) -> NotifierResult:
    brief = {
        "schema": "ai-bridge.notification_brief.v1",
        "project": "AI Bridge Notifier",
        "task_key": "send_test",
        "terminal_status": "complete",
        "key_conclusion": "Generic Notifier 的 Gmail SMTP 测试邮件已经从当前机器发出。",
        "next_step": "SMTP accepted 会建立与当前配置 digest 绑定的 transport readiness；不据此声称收件箱已投递。",
        "evidence_paths": ["ai-bridge notifier send-test"],
    }
    if dry_run:
        return NotifierResult("dry_run", event_key=event_key(brief), message="dry-run; no email sent")
    active_env = notifier_env(env, config_root=config_root)
    send_func = sender or (lambda payload, merged_env: send_email(payload, merged_env, test=True))
    try:
        send_func(brief, active_env)
    except Exception as exc:
        state = load_state(state_path)
        state["last_failure"] = {
            "event_key": event_key(brief),
            "brief_path": "send-test",
            "error": f"{type(exc).__name__}: {exc}",
            "failed_at": utc_now(),
        }
        write_json(state_path, state)
        return NotifierResult("failed", event_key=event_key(brief), message=state["last_failure"]["error"])
    validation = validate_machine_config(config_root=config_root, config=active_env if env is not None else None)
    if validation["status"] == "VALID":
        write_json(
            readiness_path(state_root),
            {
                "schema": "ai-bridge.notifier.readiness.v1",
                "transport_test_accepted_at": utc_now(),
                "config_digest": redacted_config_digest(active_env),
                "transport_result": "SMTP_ACCEPTED",
            },
        )
    return NotifierResult("sent", event_key=event_key(brief), message="SMTP accepted; inbox delivery not asserted")


def status_text(state_path: Path = STATE_PATH) -> str:
    state = load_state(state_path)
    lines = [
        f"state_path: {state_path}",
        f"sent_count: {len(state.get('sent', {}))}",
        f"baseline_initialized: {str(bool(state.get('baseline_initialized'))).lower()}",
        f"last_success: {json.dumps(state.get('last_success'), ensure_ascii=False, sort_keys=True)}",
        f"last_failure: {json.dumps(state.get('last_failure'), ensure_ascii=False, sort_keys=True)}",
    ]
    return "\n".join(lines)


def machine_status(
    *,
    config_root: Path | None = None,
    state_root: Path | None = None,
) -> dict[str, Any]:
    readiness = notifier_readiness(config_root=config_root, state_root=state_root)
    events_root = notifier_state_root(state_root) / "events"
    recoverable: list[dict[str, str]] = []
    if events_root.is_dir():
        for directory in sorted(path for path in events_root.iterdir() if path.is_dir()):
            latest = _read_latest_attempt(directory)
            if not latest:
                continue
            stage = str(latest.get("stage") or "")
            if stage in {"FAILED", "FAILED_TIMEOUT_BEFORE_TRANSPORT", "DELIVERY_UNKNOWN"}:
                command = f"ai-bridge notifier retry --event-key {directory.name}"
                if stage == "DELIVERY_UNKNOWN":
                    command += " --confirm-possible-duplicate"
                recoverable.append({"event_key": directory.name, "stage": stage, "next_command": command})
    return {"schema": "ai-bridge.notifier.status.v1", **readiness, "recoverable_events": recoverable}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge notifier")
    subparsers = parser.add_subparsers(dest="notifier_command")

    send_parser = subparsers.add_parser("send", help="Send exactly one terminal notification brief.")
    send_parser.add_argument("brief_path", type=Path)
    send_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("send-test", help="Send a real SMTP test email.").add_argument("--dry-run", action="store_true")
    subparsers.add_parser("validate", help="Validate the machine notifier config without sending email.")
    migrate = subparsers.add_parser("migrate-legacy", help="Copy one legacy project config into the machine config if safe.")
    migrate.add_argument("--project", type=Path, required=True)
    retry = subparsers.add_parser("retry", help="Explicitly retry one failed or unknown logical event.")
    retry.add_argument("--event-key", required=True)
    retry.add_argument("--confirm-possible-duplicate", action="store_true")
    subparsers.add_parser("once", help="Scan notification briefs once.").add_argument("--dry-run", action="store_true")
    run_parser = subparsers.add_parser("run", help="Optional polling compatibility mode.")
    run_parser.add_argument("--poll-seconds", type=float, default=60.0)
    run_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser("status", help="Show local notifier state.")
    helper = subparsers.add_parser("_deliver-helper", help=argparse.SUPPRESS)
    helper.add_argument("--event-dir", type=Path, required=True)
    helper.add_argument("--config-root", type=Path, required=True)
    helper.add_argument("--deadline-seconds", type=float, required=True)
    helper.add_argument("--parent-attempt-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.notifier_command == "send":
        result = send_brief(args.brief_path, dry_run=args.dry_run)
        print(f"{result.status}: {result.message}")
        return 0 if result.status in {"sent", "duplicate", "dry_run"} else 1
    if args.notifier_command == "send-test":
        result = send_test(dry_run=args.dry_run)
        print(f"{result.status}: {result.message}")
        return 0 if result.status in {"sent", "dry_run"} else 1
    if args.notifier_command == "validate":
        result = validate_machine_config()
        result.pop("config", None)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "VALID" else 1
    if args.notifier_command == "migrate-legacy":
        result = migrate_legacy(args.project)
        print(f"{result.status}: {result.message}")
        return 0 if result.status in {"MIGRATED", "NOOP_ALREADY_MIGRATED"} else 1
    if args.notifier_command == "retry":
        result = retry_event(args.event_key, confirm_possible_duplicate=args.confirm_possible_duplicate)
        print(f"{result.status}: {result.message}")
        return 0 if result.status in {"SMTP_ACCEPTED", "duplicate"} else 1
    if args.notifier_command == "once":
        results = notifier_once(dry_run=args.dry_run)
        print(json.dumps([result.__dict__ for result in results], indent=2, sort_keys=True))
        return 0 if all(result.status in {"sent", "duplicate", "dry_run"} for result in results) else 1
    if args.notifier_command == "run":
        while True:
            results = notifier_once(dry_run=args.dry_run)
            failures = [result for result in results if result.status == "failed"]
            if failures:
                print(json.dumps([result.__dict__ for result in failures], indent=2, sort_keys=True))
            time.sleep(args.poll_seconds)
    if args.notifier_command == "status":
        print(json.dumps(machine_status(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.notifier_command == "_deliver-helper":
        result = deliver_event_inline(
            args.event_dir.resolve(),
            config_root=args.config_root,
            deadline_seconds=args.deadline_seconds,
            parent_attempt_id=args.parent_attempt_id,
        )
        return 0 if result.status == "SMTP_ACCEPTED" else 1
    parser.print_help()
    return 0
