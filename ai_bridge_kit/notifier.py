from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import smtplib
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
VALID_EVENT_TYPES = {"terminal", "awaiting_human", "operational_blocked", "milestone"}
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
STATUS_LABELS = {
    "complete": "完成",
    "blocked": "阻塞",
    "awaiting_human": "等待人工确认",
}
EVENT_TYPE_LABELS = {
    "terminal": "终态",
    "awaiting_human": "等待人工确认",
    "operational_blocked": "运行阻塞",
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


def notifier_env(env: dict[str, str] | None = None, env_file: Path = PRIVATE_ENV_PATH) -> dict[str, str]:
    merged = load_env_file(env_file)
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
        if event_type == "operational_blocked":
            if authority not in OPERATIONAL_DECISION_AUTHORITIES:
                errors.append("operational_blocked decision_authority must be Controller or Watcher")
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
    subparsers.add_parser("status", help="Show local notifier state.")
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
        print(status_text())
        return 0
    parser.print_help()
    return 0
