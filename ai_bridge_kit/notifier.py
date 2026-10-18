from __future__ import annotations

import argparse
import getpass
import hashlib
import html
import json
import os
import re
import smtplib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable


VALID_TERMINAL_STATUSES = {"complete", "blocked", "awaiting_human"}
LEGACY_BRIEF_SCHEMA = "ai-bridge.notification_brief.v1"
STRUCTURED_BRIEF_SCHEMA = "ai-bridge.notification_brief.v2"
VALID_BRIEF_SCHEMAS = {LEGACY_BRIEF_SCHEMA, STRUCTURED_BRIEF_SCHEMA}
VALID_EVENT_TYPES = {"terminal", "awaiting_human", "operational_blocked", "operational_progress", "runtime_terminal", "milestone"}
CANONICAL_EVENT_SCHEMA = "ai-bridge.notification_event.v1"
CANONICAL_EVENT_CLASSES = {"progress", "runtime_terminal", "semantic_completion"}
NOTIFICATION_INTENT_DEFAULTS = {
    "progress_email": "DISABLED",
    "runtime_terminal_email": "DISABLED",
    "semantic_completion_email": "DISABLED",
}
NOTIFICATION_INTENT_VALUES = {
    "progress_email": {"ENABLED", "DISABLED"},
    "runtime_terminal_email": {"ENABLED", "DISABLED"},
    "semantic_completion_email": {"ENABLED", "DISABLED", "UNSUPPORTED"},
}
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
STATE_PATH = Path(".ai-bridge") / "state" / "notifier.json"
PRIVATE_ENV_PATH = Path(".ai-bridge") / "private" / "notifier.env"
MACHINE_ENV_RELATIVE_PATH = Path("notifier") / "notifier.env"
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
    "runtime_terminal": "运行终止",
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


def normalize_notification_intents(payload: dict[str, Any] | None) -> dict[str, str]:
    raw = payload if isinstance(payload, dict) else {}
    result = dict(NOTIFICATION_INTENT_DEFAULTS)
    for key, allowed in NOTIFICATION_INTENT_VALUES.items():
        value = str(raw.get(key, result[key])).strip().upper()
        if value not in allowed:
            raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
        result[key] = value
    return result


def canonical_event(
    *,
    event_class: str,
    project: str,
    task_key: str,
    status: str,
    key_conclusion: str,
    next_step: str,
    evidence_paths: list[str],
    emitter: str,
    runtime_id: str = "",
    lifecycle_owner: str = "",
    primary_runtime_owner: str = "",
    semantic_authority: str = "",
    subtype: str = "",
    terminal_status: str = "",
    exit_code: int | None = None,
    started_at: str = "",
    ended_at: str = "",
) -> dict[str, Any]:
    if event_class not in CANONICAL_EVENT_CLASSES:
        raise ValueError("event_class must be progress, runtime_terminal, or semantic_completion")
    values = [project, task_key, status, key_conclusion, next_step, emitter]
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("canonical notification event string fields must be non-empty")
    if not evidence_paths or not all(isinstance(item, str) and item.strip() for item in evidence_paths):
        raise ValueError("canonical notification event evidence_paths must be non-empty")
    if event_class == "runtime_terminal":
        if not runtime_id.strip() or not lifecycle_owner.strip():
            raise ValueError("runtime_terminal requires runtime_id and lifecycle_owner")
        semantic_words = re.compile(r"\b(PASS|READY|RELEASE_READY|GOAL[_ ]?COMPLETE)\b", re.IGNORECASE)
        if semantic_words.search(" ".join([status, key_conclusion, next_step])):
            raise ValueError("runtime_terminal must not claim Goal PASS/READY/RELEASE_READY")
        if not primary_runtime_owner.strip():
            primary_runtime_owner = lifecycle_owner
    if event_class == "semantic_completion" and semantic_authority not in SEMANTIC_DECISION_AUTHORITIES:
        raise ValueError("semantic_completion requires Planner, Reviewer, Critic, or Final Critic authority")
    return {
        "schema": CANONICAL_EVENT_SCHEMA,
        "event_class": event_class,
        "project": project.strip(),
        "task_key": task_key.strip(),
        "status": status.strip(),
        "key_conclusion": key_conclusion.strip(),
        "next_step": next_step.strip(),
        "evidence_paths": [item.strip() for item in evidence_paths],
        "emitter": emitter.strip(),
        "runtime_id": runtime_id.strip(),
        "lifecycle_owner": lifecycle_owner.strip(),
        "primary_runtime_owner": primary_runtime_owner.strip(),
        "semantic_authority": semantic_authority.strip(),
        "subtype": subtype.strip(),
        "terminal_status": terminal_status.strip(),
        "exit_code": exit_code,
        "started_at": started_at.strip(),
        "ended_at": ended_at.strip(),
    }


def event_intent_state(event: dict[str, Any], intents: dict[str, Any] | None) -> str:
    normalized = normalize_notification_intents(intents)
    key = {
        "progress": "progress_email",
        "runtime_terminal": "runtime_terminal_email",
        "semantic_completion": "semantic_completion_email",
    }.get(str(event.get("event_class")))
    if key is None:
        raise ValueError("unknown canonical event_class")
    return normalized[key]


def canonical_event_digest(event: dict[str, Any]) -> str:
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def runtime_terminal_dedupe_key(event: dict[str, Any]) -> str:
    if event.get("event_class") != "runtime_terminal":
        raise ValueError("runtime_terminal event required")
    return "|".join(
        [str(event.get("runtime_id")), str(event.get("status")).lower(), str(event.get("lifecycle_owner"))]
    )


def deterministic_fallback(event: dict[str, Any], *, language: str = "zh-CN") -> str:
    if language.lower().startswith("zh"):
        return "；".join(
            [
                f"任务 {event['task_key']}",
                f"事件 {event['event_class']}",
                f"状态 {event['status']}",
                str(event["key_conclusion"]),
                f"下一步：{event['next_step']}",
            ]
        ) + "。"
    return (
        f"Task {event['task_key']}; event {event['event_class']}; status {event['status']}; "
        f"{event['key_conclusion']} Next: {event['next_step']}"
    )


def rendered_event_brief(event: dict[str, Any], rendered_text: str) -> dict[str, Any]:
    event_class = str(event.get("event_class"))
    if event_class == "progress":
        event_type = "operational_progress"
        authority = "Watcher"
    elif event_class == "runtime_terminal":
        event_type = "runtime_terminal"
        authority = "Controller"
    elif event_class == "semantic_completion":
        event_type = "terminal"
        authority = str(event.get("semantic_authority"))
    else:
        raise ValueError("unknown canonical event_class")
    return {
        "schema": STRUCTURED_BRIEF_SCHEMA,
        "project": event["project"],
        "task_key": event["task_key"],
        "event_type": event_type,
        "status": event["status"],
        "decision_authority": authority,
        "key_conclusion": rendered_text.strip(),
        "next_step": event["next_step"],
        "evidence_paths": list(event["evidence_paths"]),
        "canonical_event_class": event_class,
        "canonical_event_sha256": canonical_event_digest(event),
        "runtime_id": event.get("runtime_id", ""),
        "lifecycle_owner": event.get("lifecycle_owner", ""),
    }


def gmail_effect_identity(event: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    from .readiness import bounded_effect_identity

    return bounded_effect_identity(
        "gmail_send",
        {
            "provider": "GMAIL_SMTP",
            "account_from": env.get("AI_BRIDGE_NOTIFY_FROM") or env.get("AI_BRIDGE_NOTIFY_SMTP_USER") or "UNCONFIGURED",
            "recipient": ",".join(recipients(env)) or "UNCONFIGURED",
            "task_event": ":".join(
                [
                    str(event["task_key"]),
                    str(event["event_class"]),
                    str(event.get("runtime_id") or event.get("semantic_authority") or "workflow"),
                ]
            ),
            "purpose": "bounded_notification",
            "data_class": "canonical_notification_text",
        },
    )


def deliver_canonical_event(
    event: dict[str, Any],
    *,
    intents: dict[str, Any] | None,
    output_dir: Path,
    expected_effect_sha256: str = "",
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
    app: Any | None = None,
    neutral_cwd: Path | None = None,
    language: str = "zh-CN",
    reader_turns_used: int = 0,
    reader_render_max_turns: int = 0,
    progress_thread_id: str | None = None,
    auto_reader: bool = True,
) -> dict[str, Any]:
    def finish(payload: dict[str, Any]) -> dict[str, Any]:
        state_path = output_dir / "delivery_state.json"
        state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    output_dir.mkdir(parents=True, exist_ok=True)
    event_path = output_dir / "canonical_event.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    intent = event_intent_state(event, intents)
    if event.get("event_class") == "runtime_terminal" and event.get("lifecycle_owner") != event.get("primary_runtime_owner"):
        return finish({"status": "suppressed_non_primary_runtime_owner", "event_path": event_path.as_posix()})
    active_env = notifier_env(env)
    effect = gmail_effect_identity(event, active_env) if intent == "ENABLED" else None
    authorization_missing = bool(not dry_run and effect is not None and effect["sha256"] != expected_effect_sha256)
    if authorization_missing and not progress_thread_id:
        return finish({
            "status": "authorization_required",
            "event_path": event_path.as_posix(),
            "effect": effect,
        })
    automatic_reader_failure = ""
    if app is None and intent == "ENABLED" and auto_reader and not dry_run:
        from .codex_progress_thread import JsonRpcProxy

        owned_neutral = neutral_cwd or (notifier_state_home(env) / "reader-neutral")
        owned_neutral.mkdir(parents=True, exist_ok=True)
        try:
            with JsonRpcProxy() as owned_app:
                return deliver_canonical_event(
                    event,
                    intents=intents,
                    output_dir=output_dir,
                    expected_effect_sha256=expected_effect_sha256,
                    dry_run=dry_run,
                    env=env,
                    sender=sender,
                    app=owned_app,
                    neutral_cwd=owned_neutral,
                    language=language,
                    reader_turns_used=reader_turns_used,
                    reader_render_max_turns=reader_render_max_turns,
                    progress_thread_id=progress_thread_id,
                    auto_reader=False,
                )
        except Exception as exc:
            automatic_reader_failure = f"reader app unavailable: {type(exc).__name__}: {exc}"
    render: dict[str, Any] | None = None
    if app is not None and neutral_cwd is not None and (progress_thread_id or intent == "ENABLED"):
        from .reader_layer import render_event

        render = render_event(
            app,
            event=event,
            neutral_cwd=neutral_cwd,
            language=language,
            reader_turns_used=reader_turns_used,
            reader_render_max_turns=reader_render_max_turns,
            progress_thread_id=progress_thread_id,
        )
    elif intent == "ENABLED":
        text = deterministic_fallback(event, language=language)
        if progress_thread_id:
            raise ValueError("progress_thread_id requires the shared app-server client")
        render = {
            "reader_layer": "DEGRADED_FALLBACK",
            "text": text,
            "model_turn_used": False,
            "reader_turns_used": reader_turns_used,
            "failure": automatic_reader_failure or "reader app unavailable",
        }
    if intent != "ENABLED":
        result = {"status": "disabled_by_frozen_intent", "event_path": event_path.as_posix(), "intent": intent}
        if render is not None:
            result["reader"] = render
        return finish(result)
    if authorization_missing:
        return finish({
            "status": "authorization_required",
            "event_path": event_path.as_posix(),
            "effect": effect,
            "reader": render,
        })
    assert render is not None and effect is not None
    brief = rendered_event_brief(event, str(render["text"]))
    brief_path = output_dir / "notification_brief.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = send_brief(
        brief_path,
        state_path=output_dir / "notifier_state.json",
        env=active_env,
        dry_run=dry_run,
        sender=sender,
    )
    return finish({
        "status": result.status,
        "event_path": event_path.as_posix(),
        "brief_path": brief_path.as_posix(),
        "effect": effect,
        "reader": render,
        "event_key": result.event_key,
        "message": result.message,
    })


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


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


def notifier_state_home(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    return Path(source.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser().resolve()


def machine_env_path(env: dict[str, str] | None = None) -> Path:
    return notifier_state_home(env) / MACHINE_ENV_RELATIVE_PATH


def notifier_env(
    env: dict[str, str] | None = None,
    env_file: Path = PRIVATE_ENV_PATH,
    *,
    machine_file: Path | None = None,
) -> dict[str, str]:
    merged = load_env_file(machine_file or machine_env_path(env))
    merged.update(load_env_file(env_file))
    source = os.environ if env is None else env
    for key in [
        "AI_BRIDGE_NOTIFY_SMTP_USER",
        "AI_BRIDGE_NOTIFY_SMTP_PASSWORD",
        "AI_BRIDGE_NOTIFY_FROM",
        "AI_BRIDGE_NOTIFY_TO",
        "AI_BRIDGE_NOTIFY_SUBJECT_PREFIX",
    ]:
        if source.get(key):
            merged[key] = source[key]
    return merged


def write_env_profile(path: Path, values: dict[str, str]) -> None:
    allowed = {
        "AI_BRIDGE_NOTIFY_SMTP_USER",
        "AI_BRIDGE_NOTIFY_SMTP_PASSWORD",
        "AI_BRIDGE_NOTIFY_FROM",
        "AI_BRIDGE_NOTIFY_TO",
        "AI_BRIDGE_NOTIFY_SUBJECT_PREFIX",
    }
    payload = "".join(f"{key}={values[key]}\n" for key in sorted(values) if key in allowed and values[key])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)


def configure_profile(
    *,
    scope: str,
    target: Path,
    values: dict[str, str],
    clear: bool = False,
    env: dict[str, str] | None = None,
) -> Path:
    if scope not in {"machine", "project"}:
        raise ValueError("scope must be machine or project")
    path = machine_env_path(env) if scope == "machine" else target.resolve() / PRIVATE_ENV_PATH
    if clear:
        path.unlink(missing_ok=True)
        return path
    current = load_env_file(path)
    current.update({key: value for key, value in values.items() if value})
    if scope == "project" and "AI_BRIDGE_NOTIFY_SMTP_PASSWORD" in values:
        raise ValueError("project scope must not store Gmail App Password")
    if not current:
        raise ValueError("configure requires at least one value")
    write_env_profile(path, current)
    return path


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
        if event_type in {"operational_blocked", "operational_progress", "runtime_terminal"}:
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
    message.set_content(render_plain(brief))
    message.add_alternative(render_html(brief), subtype="html")
    return message


def send_email(brief: dict[str, Any], env: dict[str, str], *, test: bool = False) -> None:
    missing = require_email_config(env)
    if missing:
        raise ValueError("missing email config: " + ", ".join(missing))
    message = build_email_message(brief, env, test=test)
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(env["AI_BRIDGE_NOTIFY_SMTP_USER"], env["AI_BRIDGE_NOTIFY_SMTP_PASSWORD"])
        smtp.send_message(message)


def send_brief(
    brief_path: Path,
    *,
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
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
    active_env = notifier_env(env)
    send_func = sender or (lambda payload, merged_env: send_email(payload, merged_env))
    try:
        send_func(brief, active_env)
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
    return NotifierResult("sent", event_key=key, message="sent")


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
        results.append(send_brief(path, state_path=state_path, env=env, dry_run=dry_run, sender=sender))
    return results


def send_test(
    *,
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
) -> NotifierResult:
    brief = {
        "schema": "ai-bridge.notification_brief.v1",
        "project": "AI Bridge Notifier",
        "task_key": "send_test",
        "terminal_status": "complete",
        "key_conclusion": "Generic Notifier 的 Gmail SMTP 测试邮件已经从当前机器发出。",
        "next_step": "只有确认真实邮件送达后，才标记 NOTIFIER_READY。",
        "evidence_paths": ["ai-bridge notifier send-test"],
    }
    if dry_run:
        return NotifierResult("dry_run", event_key=event_key(brief), message="dry-run; no email sent")
    active_env = notifier_env(env)
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
    return NotifierResult("sent", event_key=event_key(brief), message="sent")


def status_text(state_path: Path = STATE_PATH, *, target: Path = Path.cwd(), env: dict[str, str] | None = None) -> str:
    state = load_state(state_path)
    machine = load_env_file(machine_env_path(env))
    project = load_env_file(target.resolve() / PRIVATE_ENV_PATH)
    resolved = notifier_env(env, target.resolve() / PRIVATE_ENV_PATH)
    defaults_path = target.resolve() / "automation" / "notifier" / "DEFAULTS.json"
    defaults_payload = load_json(defaults_path) if defaults_path.is_file() else {}
    intents = normalize_notification_intents(defaults_payload)
    delivery_candidates = list((target.resolve() / "results").glob("**/delivery_state.json")) if (target.resolve() / "results").is_dir() else []
    latest_delivery: dict[str, Any] | None = None
    if delivery_candidates:
        newest = max(delivery_candidates, key=lambda item: item.stat().st_mtime_ns)
        try:
            latest_delivery = load_json(newest)
        except (OSError, json.JSONDecodeError):
            latest_delivery = {"status": "unreadable", "path": newest.as_posix()}
    latest_reader = latest_delivery.get("reader") if isinstance(latest_delivery, dict) and isinstance(latest_delivery.get("reader"), dict) else {}
    lines = [
        "provider: GMAIL_SMTP smtp.gmail.com:587 STARTTLS",
        f"machine_config: {'configured' if machine else 'absent'} ({machine_env_path(env)})",
        f"project_config: {'configured' if project else 'absent'} ({target.resolve() / PRIVATE_ENV_PATH})",
        f"sender: {resolved.get('AI_BRIDGE_NOTIFY_FROM') or resolved.get('AI_BRIDGE_NOTIFY_SMTP_USER') or 'UNCONFIGURED'}",
        f"recipient: {resolved.get('AI_BRIDGE_NOTIFY_TO') or 'UNCONFIGURED'}",
        f"credential_state: {'configured' if resolved.get('AI_BRIDGE_NOTIFY_SMTP_PASSWORD') else 'missing'}",
        f"notification_intents: {json.dumps(intents, sort_keys=True)}",
        f"state_path: {state_path}",
        f"sent_count: {len(state.get('sent', {}))}",
        f"baseline_initialized: {str(bool(state.get('baseline_initialized'))).lower()}",
        f"last_success: {json.dumps(state.get('last_success'), ensure_ascii=False, sort_keys=True)}",
        f"last_failure: {json.dumps(state.get('last_failure'), ensure_ascii=False, sort_keys=True)}",
        f"last_delivery: {json.dumps(latest_delivery, ensure_ascii=False, sort_keys=True)}",
        f"reader_layer: {latest_reader.get('reader_layer', 'UNKNOWN')}",
        f"reader_plugin: {latest_reader.get('plugin_id', 'UNKNOWN')}@{latest_reader.get('plugin_version', 'UNKNOWN')}",
        f"last_display_injection: {latest_reader.get('display_injection_state', 'UNKNOWN')}",
        "local_clear_note: clearing Bridge local config does not revoke the Google App Password",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge notifier")
    subparsers = parser.add_subparsers(dest="notifier_command")

    send_parser = subparsers.add_parser("send", help="Send exactly one terminal notification brief.")
    send_parser.add_argument("brief_path", type=Path)
    send_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("send-test", help="Send a real SMTP test email.").add_argument("--dry-run", action="store_true")
    subparsers.add_parser("once", help="Scan notification briefs once.").add_argument("--dry-run", action="store_true")
    run_parser = subparsers.add_parser("run", help="Optional polling compatibility mode.")
    run_parser.add_argument("--poll-seconds", type=float, default=60.0)
    run_parser.add_argument("--dry-run", action="store_true")
    status_parser = subparsers.add_parser("status", help="Show local notifier state and resolved Gmail config.")
    status_parser.add_argument("--target", type=Path, default=Path.cwd())
    configure = subparsers.add_parser("configure", help="Configure Gmail SMTP at machine or project scope.")
    configure.add_argument("--scope", choices=["machine", "project"], default="machine")
    configure.add_argument("--target", type=Path, default=Path.cwd())
    configure.add_argument("--smtp-user")
    configure.add_argument("--app-password")
    configure.add_argument("--from-address")
    configure.add_argument("--recipient")
    configure.add_argument("--subject-prefix")
    configure.add_argument("--clear", action="store_true")
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
        print(status_text(target=args.target))
        return 0
    if args.notifier_command == "configure":
        app_password = args.app_password
        if args.scope == "machine" and not args.clear and app_password is None and sys.stdin.isatty():
            app_password = getpass.getpass("Gmail App Password (leave blank to keep existing): ").strip()
        values = {
            "AI_BRIDGE_NOTIFY_SMTP_USER": args.smtp_user or "",
            "AI_BRIDGE_NOTIFY_SMTP_PASSWORD": app_password or "",
            "AI_BRIDGE_NOTIFY_FROM": args.from_address or "",
            "AI_BRIDGE_NOTIFY_TO": args.recipient or "",
            "AI_BRIDGE_NOTIFY_SUBJECT_PREFIX": args.subject_prefix or "",
        }
        try:
            path = configure_profile(
                scope=args.scope,
                target=args.target,
                values=values,
                clear=args.clear,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"{'CLEARED' if args.clear else 'CONFIGURED'}: {path}")
        if args.clear:
            print("Google App Password was not revoked; clear affects Bridge local config only.")
        return 0
    parser.print_help()
    return 0
