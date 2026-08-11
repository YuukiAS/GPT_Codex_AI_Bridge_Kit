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
REQUIRED_BRIEF_FIELDS = {
    "schema",
    "project",
    "task_key",
    "terminal_status",
    "key_conclusion",
    "next_step",
    "evidence_paths",
}
STATE_PATH = Path(".ai-bridge") / "state" / "notifier.json"
PRIVATE_ENV_PATH = Path(".ai-bridge") / "private" / "notifier.env"


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
    missing = sorted(REQUIRED_BRIEF_FIELDS - set(brief))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
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


def event_key(brief: dict[str, Any]) -> str:
    parts = [
        str(brief.get("project", "")),
        str(brief.get("task_key", "")),
        str(brief.get("terminal_status", "")).lower(),
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
    status = str(brief.get("terminal_status", "")).upper()
    task = str(brief.get("task_key", "unknown"))
    label = "SEND_TEST" if test else status
    return f"{prefix}[{label}] {task}"


def render_plain(brief: dict[str, Any]) -> str:
    evidence = brief.get("evidence_paths") if isinstance(brief.get("evidence_paths"), list) else []
    lines = [
        f"Project: {brief.get('project', 'unknown')}",
        f"Task: {brief.get('task_key', 'unknown')}",
        f"Status: {brief.get('terminal_status', 'unknown')}",
        "",
        f"Conclusion: {brief.get('key_conclusion', '')}",
        f"Next step: {brief.get('next_step', '')}",
        "",
        "Evidence:",
    ]
    lines.extend(f"- {item}" for item in evidence[:8])
    for key in ["commit_status", "push_status", "duration", "branch", "version"]:
        if brief.get(key):
            lines.append(f"{key}: {brief[key]}")
    details = brief.get("details")
    if isinstance(details, str) and details.strip():
        lines.extend(["", "Details:", details.strip()[:1000]])
    return "\n".join(lines).strip() + "\n"


def render_html(brief: dict[str, Any]) -> str:
    evidence = brief.get("evidence_paths") if isinstance(brief.get("evidence_paths"), list) else []
    evidence_items = "\n".join(f"<li>{html.escape(str(item))}</li>" for item in evidence[:8])
    rows = []
    for key in ["commit_status", "push_status", "duration", "branch", "version"]:
        if brief.get(key):
            rows.append(f"<p><strong>{html.escape(key)}:</strong> {html.escape(str(brief[key]))}</p>")
    details = brief.get("details")
    detail_html = ""
    if isinstance(details, str) and details.strip():
        detail_html = f"<h2>Details</h2><p>{html.escape(details.strip()[:1000])}</p>"
    return (
        "<html><body>"
        f"<p><strong>Project:</strong> {html.escape(str(brief.get('project', 'unknown')))}</p>"
        f"<p><strong>Task:</strong> {html.escape(str(brief.get('task_key', 'unknown')))}</p>"
        f"<p><strong>Status:</strong> {html.escape(str(brief.get('terminal_status', 'unknown')))}</p>"
        f"<p><strong>Conclusion:</strong> {html.escape(str(brief.get('key_conclusion', '')))}</p>"
        f"<p><strong>Next step:</strong> {html.escape(str(brief.get('next_step', '')))}</p>"
        f"<h2>Evidence</h2><ul>{evidence_items}</ul>"
        + "".join(rows)
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


def notifier_once(
    *,
    root: Path = Path.cwd(),
    state_path: Path = STATE_PATH,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    sender: Callable[[dict[str, Any], dict[str, str]], None] | None = None,
) -> list[NotifierResult]:
    state = load_state(state_path)
    briefs = terminal_briefs(root)
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
        "key_conclusion": "Generic notifier SMTP test completed.",
        "next_step": "Mark NOTIFIER_READY only if this real email was received.",
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
