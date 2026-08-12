from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import reviewed_handoff as rh


ELIGIBLE_EXECUTOR_STATES = {"PLAN_FROZEN", "REVISE"}


def state_path(target: Path) -> Path:
    return target.resolve() / ".ai-bridge" / "state" / "reviewed-handoff-watcher.json"


def log_root(target: Path) -> Path:
    return target.resolve() / ".ai-bridge" / "logs" / "reviewed-handoff"


def load_local_state(target: Path) -> dict[str, Any]:
    path = state_path(target)
    if not path.exists():
        return {"schema": "AI_BRIDGE_REVIEWED_WATCHER_STATE_V1", "events": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_local_state(target: Path, payload: dict[str, Any]) -> None:
    path = state_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_output(target: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=target, text=True, stderr=subprocess.STDOUT).strip()


def ensure_clean_repo(target: Path) -> None:
    try:
        git_output(target, ["rev-parse", "--show-toplevel"])
    except Exception as exc:
        raise ValueError(f"Reviewed Handoff watcher requires a Git repository: {exc}") from exc
    dirty = git_output(target, ["status", "--porcelain"])
    if dirty:
        raise ValueError("Reviewed Handoff watcher refuses to sync or launch Codex with a dirty working tree")


def resolve_branch(target: Path, branch: str | None) -> str:
    selected = branch or git_output(target, ["branch", "--show-current"])
    if not selected:
        raise ValueError("Reviewed Handoff watcher requires an existing checked-out branch, not detached HEAD")
    current = git_output(target, ["branch", "--show-current"])
    if current != selected:
        raise ValueError(f"Reviewed Handoff watcher is on branch {current!r}, expected {selected!r}; it will not switch branches")
    return selected


def sync_origin_ff_only(target: Path, branch: str) -> None:
    ensure_clean_repo(target)
    git_output(target, ["fetch", "origin", branch])
    git_output(target, ["merge", "--ff-only", f"origin/{branch}"])


def event_identity(task_key: str, current: dict[str, Any]) -> str:
    # Deliberately plain operational identity, not a cryptographic workflow identity.
    return "|".join(
        [
            task_key,
            str(current.get("state") or ""),
            str(current.get("review_round") or 0),
            str(current.get("plan_revision") or 0),
            str(current.get("implementation_commit") or ""),
        ]
    )


def eligible_events(target: Path) -> list[tuple[str, dict[str, Any]]]:
    tasks_dir = rh.reviewed_root(target) / "tasks"
    if not tasks_dir.exists():
        return []
    events: list[tuple[str, dict[str, Any]]] = []
    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        current_path = task_dir / "CURRENT.json"
        if not current_path.exists():
            continue
        current = rh.load_json(current_path)
        if current.get("state") in ELIGIBLE_EXECUTOR_STATES:
            events.append((task_dir.name, current))
    return events


def executor_prompt(target: Path, task_key: str, current: dict[str, Any], branch: str) -> str:
    state = current.get("state")
    return f"""You are the Codex Executor for Reviewed Handoff task `{task_key}` in this repository.

Read, in this order:
1. repository `AGENTS.md` if present;
2. `automation/reviewed_handoff/README.md`;
3. `automation/reviewed_handoff/prompts/CODEX_EXECUTOR.md`;
4. `automation/reviewed_handoff/tasks/{task_key}/REQUEST.md`;
5. `automation/reviewed_handoff/tasks/{task_key}/PLAN.md`;
6. `automation/reviewed_handoff/tasks/{task_key}/CURRENT.json`;
7. existing `results/{task_key}/REVIEW_*.md` when this is a repair.

The machine state that triggered this run is `{state}`. Work only on this task. Do not redesign the frozen Plan. If a material decision cannot be derived safely, publish `NEEDS_GPT_PLANNER` according to the protocol instead of asking the human interactively.

Use the already checked-out existing branch `{branch}`. Do not create a branch or PR. When implementation is complete, run the real acceptance/regression checks, create an implementation commit containing the task-owned implementation changes, then write/update `results/{task_key}/RESULT.md` and `CURRENT.json` with that implementation commit as a locator in a separate control-plane commit. Push ordinary commits to `origin/{branch}`. Do not add provenance hashes, receipt graphs, or Agent-Flow artifacts.
"""


def codex_command(target: Path, codex_bin: str) -> list[str]:
    return [codex_bin, "exec", "-C", str(target.resolve()), "-"]


def run_codex_event(
    target: Path,
    task_key: str,
    current: dict[str, Any],
    *,
    branch: str,
    codex_bin: str = "codex",
    dry_run: bool = False,
) -> dict[str, Any]:
    prompt = executor_prompt(target, task_key, current, branch)
    command = codex_command(target, codex_bin)
    if dry_run:
        return {"task_key": task_key, "event": event_identity(task_key, current), "command": command, "prompt": prompt, "launched": False}

    event = event_identity(task_key, current)
    safe_event = str(abs(hash(event)))
    log_dir = log_root(target) / task_key
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{safe_event}.log"
    started = time.time()
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            command,
            cwd=target,
            input=prompt,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            check=False,
        )
    return {
        "task_key": task_key,
        "event": event,
        "command": command,
        "launched": True,
        "exit_code": proc.returncode,
        "log_path": str(log_path),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def watcher_once(
    target: Path,
    *,
    branch: str | None = None,
    codex_bin: str = "codex",
    sync: bool = True,
    dry_run: bool = False,
    max_attempts_per_event: int = 2,
) -> dict[str, Any]:
    target = target.resolve()
    selected_branch = resolve_branch(target, branch)
    if sync:
        sync_origin_ff_only(target, selected_branch)
    else:
        ensure_clean_repo(target)

    validation_lines, validation_code = rh.validate_reviewed_handoff(target)
    if validation_code:
        return {"status": "invalid_workflow", "branch": selected_branch, "errors": validation_lines}

    local = load_local_state(target)
    events = local.setdefault("events", {})
    for task_key, current in eligible_events(target):
        event = event_identity(task_key, current)
        prior = events.get(event, {}) if isinstance(events.get(event), dict) else {}
        attempts = int(prior.get("attempts", 0))
        if prior.get("completed"):
            continue
        if attempts >= max_attempts_per_event:
            continue
        if dry_run:
            return {"status": "dry_run", **run_codex_event(target, task_key, current, branch=selected_branch, codex_bin=codex_bin, dry_run=True)}

        result = run_codex_event(target, task_key, current, branch=selected_branch, codex_bin=codex_bin)
        attempts += 1
        # Re-fetch on the next watcher cycle; Codex owns tracked state transitions.
        events[event] = {
            "attempts": attempts,
            "completed": result.get("exit_code") == 0,
            "last_exit_code": result.get("exit_code"),
            "last_log_path": result.get("log_path"),
        }
        write_local_state(target, local)
        result["status"] = "codex_completed" if result.get("exit_code") == 0 else "codex_failed"
        result["attempt"] = attempts
        return result
    return {"status": "idle", "branch": selected_branch}


def watcher_run(
    target: Path,
    *,
    branch: str | None = None,
    codex_bin: str = "codex",
    interval_seconds: int = 60,
    max_cycles: int | None = None,
) -> int:
    cycles = 0
    while True:
        try:
            result = watcher_once(target, branch=branch, codex_bin=codex_bin, sync=True, dry_run=False)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(json.dumps({"status": "watcher_error", "error": str(exc)}, ensure_ascii=False), flush=True)
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return 0
        time.sleep(max(5, interval_seconds))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge reviewed-handoff watcher")
    sub = parser.add_subparsers(dest="command")
    once = sub.add_parser("once")
    once.add_argument("--target", type=Path, default=Path.cwd())
    once.add_argument("--branch")
    once.add_argument("--codex-bin", default="codex")
    once.add_argument("--no-sync", action="store_true")
    once.add_argument("--dry-run", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--target", type=Path, default=Path.cwd())
    run.add_argument("--branch")
    run.add_argument("--codex-bin", default="codex")
    run.add_argument("--interval-seconds", type=int, default=60)
    run.add_argument("--max-cycles", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "once":
        result = watcher_once(
            args.target,
            branch=args.branch,
            codex_bin=args.codex_bin,
            sync=not args.no_sync,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("status") not in {"invalid_workflow", "codex_failed"} else 1
    if args.command == "run":
        return watcher_run(
            args.target,
            branch=args.branch,
            codex_bin=args.codex_bin,
            interval_seconds=args.interval_seconds,
            max_cycles=args.max_cycles,
        )
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
