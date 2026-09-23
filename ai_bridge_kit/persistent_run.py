from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
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


def install_agents_block(target: Path) -> str:
    agents = target / "AGENTS.md"
    block = _managed_block()
    if not agents.exists():
        write_text(agents, block)
        return f"CREATE {agents}"
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
    if updated != current:
        write_text(agents, updated)
    return f"{action} Persistent Run managed block in {agents}"


def install_persistent_run(target: Path) -> list[str]:
    target = ensure_git_repo(target.resolve())
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
    actions.append(install_agents_block(target))
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
    rel_goal, _goal_path = _validate_goal_path(target, goal)
    template = read_text(template_root() / "KICKOFF_TEMPLATE.md")
    return template.replace("__GOAL_PATH__", rel_goal).rstrip() + "\n"


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
    except PersistentRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
