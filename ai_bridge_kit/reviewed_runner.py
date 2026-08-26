from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import reviewed_handoff as rh


ELIGIBLE_EXECUTOR_STATES = {"PLAN_FROZEN", "REVISE"}
PROTECTED_CURRENT_FIELDS = {
    "schema",
    "task_key",
    "review_round",
    "max_review_rounds",
    "plan_revision",
    "max_plan_revisions",
    "base_commit",
    "base_branch",
    "ci_required",
    "last_review_decision",
    "review_limit_reached",
    "human_gate_reason",
    "runner_failure",
}


def machine_state_home() -> Path:
    override = os.environ.get("AI_BRIDGE_STATE_HOME")
    return Path(override).expanduser().resolve() if override else (Path.home() / ".ai-bridge").resolve()


def repo_state_slug(target: Path) -> str:
    raw = target.resolve().as_posix().strip("/") or "repository"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)


def machine_task_root(target: Path) -> Path:
    return machine_state_home() / "reviewed-handoff" / repo_state_slug(target)


def state_path(target: Path) -> Path:
    return machine_task_root(target) / "watcher.json"


def log_root(target: Path) -> Path:
    return machine_task_root(target) / "logs"


def load_local_state(target: Path) -> dict[str, Any]:
    path = state_path(target)
    if not path.exists():
        return {"schema": "AI_BRIDGE_REVIEWED_WATCHER_STATE_V1", "events": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_local_state(target: Path, payload: dict[str, Any]) -> None:
    path = state_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_watcher_status(target: Path, status: str, *, branch: str, errors: list[str] | None = None) -> None:
    local = load_local_state(target)
    entry = {
        "status": status,
        "branch": branch,
        "errors": errors or [],
        "recorded_at": utc_now(),
    }
    local["last_status"] = entry
    if status == "invalid_workflow":
        local["last_invalid_workflow"] = entry
    write_local_state(target, local)


def git_output(target: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=target, text=True, stderr=subprocess.STDOUT).strip()


def ensure_git_repo(target: Path) -> None:
    try:
        git_output(target, ["rev-parse", "--show-toplevel"])
    except Exception as exc:
        raise ValueError(f"Reviewed Handoff watcher requires a Git repository: {exc}") from exc


def working_tree_dirty(target: Path) -> bool:
    ensure_git_repo(target)
    return bool(git_output(target, ["status", "--porcelain"]))


def ensure_clean_repo(target: Path) -> None:
    if working_tree_dirty(target):
        raise ValueError("Reviewed Handoff watcher refuses to sync or launch Codex with a dirty working tree")


def resolve_branch(target: Path, branch: str | None) -> str:
    ensure_git_repo(target)
    selected = branch or git_output(target, ["branch", "--show-current"])
    if not selected:
        raise ValueError("Reviewed Handoff watcher requires an existing checked-out branch, not detached HEAD")
    current = git_output(target, ["branch", "--show-current"])
    if current != selected:
        raise ValueError(f"Reviewed Handoff watcher is on branch {current!r}, expected {selected!r}; it will not switch branches")
    return selected


def branch_heads(target: Path, branch: str) -> tuple[str, str]:
    return git_output(target, ["rev-parse", "HEAD"]), git_output(target, ["rev-parse", f"origin/{branch}"])


def branch_relation(target: Path, branch: str) -> tuple[int, int]:
    counts = git_output(target, ["rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"]).split()
    if len(counts) != 2:
        raise ValueError("unable to determine local/remote branch relation")
    return int(counts[0]), int(counts[1])


def sync_origin_ff_only(target: Path, branch: str) -> None:
    ensure_clean_repo(target)
    git_output(target, ["fetch", "origin", branch])
    git_output(target, ["merge", "--ff-only", f"origin/{branch}"])
    local_head, remote_head = branch_heads(target, branch)
    if local_head != remote_head:
        raise ValueError(
            "Reviewed Handoff watcher requires the local branch to equal origin before launching Codex; "
            "push or reconcile pre-existing local commits first"
        )


def publish_clean_progress(target: Path, branch: str) -> tuple[bool, str | None]:
    """Ensure validated clean Codex progress is visible on origin."""
    if working_tree_dirty(target):
        return False, "working tree is dirty"
    git_output(target, ["fetch", "origin", branch])
    local_head, remote_head = branch_heads(target, branch)
    if local_head == remote_head:
        return True, None
    behind, ahead = branch_relation(target, branch)
    if behind == 0 and ahead > 0:
        git_output(target, ["push", "origin", branch])
        git_output(target, ["fetch", "origin", branch])
        local_head, remote_head = branch_heads(target, branch)
        if local_head == remote_head:
            return True, None
        return False, "origin did not reach the local Codex commit after push"
    return False, f"local/remote branch diverged during Codex execution (behind={behind}, ahead={ahead})"


def current_at_ref(target: Path, ref: str, task_key: str) -> dict[str, Any] | None:
    rel = f"automation/reviewed_handoff/tasks/{task_key}/CURRENT.json"
    try:
        return json.loads(git_output(target, ["show", f"{ref}:{rel}"]))
    except Exception:
        return None


def validate_unpublished_executor_progress(target: Path, branch: str) -> tuple[str | None, dict[str, Any]]:
    local_head, remote_head = branch_heads(target, branch)
    if local_head == remote_head:
        return None, {"status": "up_to_date"}
    try:
        behind, ahead = branch_relation(target, branch)
    except Exception as exc:
        return None, {"status": "unpublished_progress_recovery_failed", "reason": str(exc)}
    if ahead == 0:
        return None, {"status": "no_unpublished_executor_progress", "behind": behind, "ahead": ahead}
    if behind != 0:
        return None, {
            "status": "unpublished_progress_recovery_failed",
            "reason": f"local/remote branch diverged before recovery (behind={behind}, ahead={ahead})",
            "behind": behind,
            "ahead": ahead,
        }

    task_failures: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    tasks_dir = rh.reviewed_root(target) / "tasks"
    if tasks_dir.exists():
        for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
            task_key = task_dir.name
            post_current_path = task_dir / "CURRENT.json"
            if not post_current_path.exists():
                continue
            pre_current = current_at_ref(target, f"origin/{branch}", task_key)
            if not pre_current or pre_current.get("state") not in ELIGIBLE_EXECUTOR_STATES:
                continue
            post_current = rh.load_json(post_current_path)
            pre_event = event_identity(task_key, pre_current)
            post_event = event_identity(task_key, post_current)
            progressed = post_event != pre_event or post_current.get("state") not in ELIGIBLE_EXECUTOR_STATES
            if not progressed:
                task_failures.append({"task_key": task_key, "errors": ["local commits did not advance the Executor event"]})
                continue
            authority_errors = executor_authority_errors(target, task_key, pre_current, post_current, remote_head, local_head)
            workflow_errors = []
            if not authority_errors:
                validation_lines, validation_code = rh.validate_reviewed_handoff(target)
                workflow_errors = validation_lines if validation_code else []
            lineage_errors: list[str] = []
            if post_current.get("state") in {"WAITING_FOR_CI", "READY_FOR_GPT_REVIEW"}:
                implementation_commit = str(post_current.get("implementation_commit") or "")
                if not implementation_commit:
                    lineage_errors.append("Executor handoff requires implementation_commit")
                elif not rh.git_is_ancestor(target, remote_head, implementation_commit) or not rh.git_is_ancestor(target, implementation_commit, local_head):
                    lineage_errors.append("implementation_commit is not contained in the unpublished Executor commit range")
            errors = authority_errors + workflow_errors + lineage_errors
            if errors:
                task_failures.append({"task_key": task_key, "event": pre_event, "errors": errors})
                continue
            candidates.append({"task_key": task_key, "event": pre_event, "post_state": post_current.get("state")})

    if len(candidates) != 1:
        reason = "unpublished commits are not bound to exactly one valid current Executor event"
        return None, {
            "status": "unpublished_progress_recovery_failed",
            "reason": reason,
            "candidate_count": len(candidates),
            "task_failures": task_failures,
            "behind": behind,
            "ahead": ahead,
        }
    return str(candidates[0]["event"]), {
        "status": "validated_unpublished_executor_progress",
        "task_key": candidates[0]["task_key"],
        "event": candidates[0]["event"],
        "post_state": candidates[0]["post_state"],
        "behind": behind,
        "ahead": ahead,
    }


def recover_unpublished_executor_progress(target: Path, branch: str) -> dict[str, Any]:
    if working_tree_dirty(target):
        return {
            "status": "unpublished_progress_recovery_failed",
            "reason": "working tree is dirty",
        }
    git_output(target, ["fetch", "origin", branch])
    event, validation = validate_unpublished_executor_progress(target, branch)
    if validation.get("status") != "validated_unpublished_executor_progress":
        return validation
    published, publication_error = publish_clean_progress(target, branch)
    if not published:
        return {
            **validation,
            "status": "unpublished_progress_recovery_failed",
            "reason": publication_error,
        }
    local = load_local_state(target)
    events = local.setdefault("events", {})
    prior = events.get(str(event), {}) if isinstance(events.get(str(event)), dict) else {}
    events[str(event)] = {
        **prior,
        "attempts": int(prior.get("attempts", 0)),
        "completed": True,
        "completed_at": utc_now(),
        "running": False,
        "recovered_after_restart": True,
        "last_publication_error": None,
        "last_publication_status": "published",
        "last_result": "recovered_unpublished_progress",
    }
    local["last_status"] = {"status": "recovered_unpublished_progress", "branch": branch, "errors": [], "recorded_at": utc_now()}
    write_local_state(target, local)
    return {
        "branch": branch,
        **validation,
        "status": "recovered_unpublished_progress",
    }


def event_identity(task_key: str, current: dict[str, Any]) -> str:
    # Plain operational identity only. It is deliberately not hashed into workflow state.
    return "|".join(
        [
            task_key,
            str(current.get("state") or ""),
            str(current.get("review_round") or 0),
            str(current.get("plan_revision") or 0),
            str(current.get("implementation_commit") or ""),
        ]
    )


def log_name(task_key: str, current: dict[str, Any]) -> str:
    return "-".join(
        [
            task_key,
            str(current.get("state") or "state").lower(),
            f"r{current.get('review_round') or 0}",
            f"p{current.get('plan_revision') or 0}",
        ]
    ) + ".log"


def executor_phase(current: dict[str, Any]) -> str:
    if current.get("state") == "REVISE":
        return "repair"
    if current.get("state") == "PLAN_FROZEN":
        return "initial_implementation"
    return "not_executor_owned"


def waiting_owner(target: Path, task_key: str, current: dict[str, Any]) -> str:
    state = str(current.get("state") or "")
    if state in ELIGIBLE_EXECUTOR_STATES:
        return "Codex"
    try:
        status = rh.reviewed_external_wait_status(target, task_key)
    except Exception:
        status = {}
    if status.get("operational_status") in {"waiting_external_review", "waiting_visual_review_evidence"}:
        return str(status.get("wait_owner") or status.get("external_owner") or "External")
    if state == "WAITING_FOR_CI":
        return "CI"
    if state in {"PASS", "AWAIT_HUMAN_DECISION", "BLOCKED"}:
        return "None"
    return str(current.get("next_action") or "Unknown")


def record_event_start(
    target: Path,
    *,
    branch: str,
    task_key: str,
    current: dict[str, Any],
    event: str,
    attempts: int,
) -> str:
    started_at = utc_now()
    local = load_local_state(target)
    events = local.setdefault("events", {})
    prior = events.get(event, {}) if isinstance(events.get(event), dict) else {}
    local["last_status"] = {"status": "executor_running", "branch": branch, "errors": [], "recorded_at": started_at}
    events[event] = {
        **prior,
        "task_key": task_key,
        "state": current.get("state"),
        "phase": executor_phase(current),
        "review_round": current.get("review_round"),
        "plan_revision": current.get("plan_revision"),
        "branch": branch,
        "runtime_type": "codex_exec",
        "thread_id": None,
        "started_at": started_at,
        "completed_at": None,
        "running": True,
        "completed": False,
        "attempts": attempts,
        "last_result": "running",
        "last_publication_status": "not_started",
    }
    write_local_state(target, local)
    return started_at


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


def external_wait_events(target: Path) -> list[tuple[str, dict[str, Any]]]:
    tasks_dir = rh.reviewed_root(target) / "tasks"
    if not tasks_dir.exists():
        return []
    waiting: list[tuple[str, dict[str, Any]]] = []
    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        current_path = task_dir / "CURRENT.json"
        if not current_path.exists():
            continue
        status = rh.reviewed_external_wait_status(target, task_dir.name)
        if status.get("operational_status") in {"waiting_external_review", "waiting_visual_review_evidence"}:
            waiting.append((task_dir.name, status))
    return waiting


def changed_paths(target: Path, pre_head: str, post_head: str) -> list[str]:
    if pre_head == post_head:
        return []
    output = git_output(target, ["diff", "--name-only", pre_head, post_head])
    return sorted(line.strip().replace("\\", "/") for line in output.splitlines() if line.strip())


def executor_authority_errors(
    target: Path,
    task_key: str,
    pre_current: dict[str, Any],
    post_current: dict[str, Any],
    pre_head: str,
    post_head: str,
) -> list[str]:
    errors: list[str] = []
    for field in sorted(PROTECTED_CURRENT_FIELDS):
        if pre_current.get(field) != post_current.get(field):
            errors.append(f"Executor changed protected CURRENT field: {field}")

    ci_required = bool(pre_current.get("ci_required"))
    allowed_states = {"NEEDS_GPT_PLANNER", "WAITING_FOR_CI"} if ci_required else {
        "NEEDS_GPT_PLANNER",
        "READY_FOR_GPT_REVIEW",
    }
    post_state = post_current.get("state")
    if post_state not in allowed_states:
        errors.append(
            "Executor ended in a state outside its authority for this task: "
            f"{post_state}; allowed={sorted(allowed_states)}"
        )
    if ci_required and post_state == "WAITING_FOR_CI" and post_current.get("ci_status") != "PENDING":
        errors.append("CI-required Executor must publish WAITING_FOR_CI with ci_status=PENDING")
    if not ci_required and post_state == "READY_FOR_GPT_REVIEW" and post_current.get("ci_status") not in {"NOT_REQUIRED", "PASS"}:
        errors.append("CI-not-required Executor produced invalid ci_status before GPT review")

    own_current = f"automation/reviewed_handoff/tasks/{task_key}/CURRENT.json"
    own_result = f"results/{task_key}/RESULT.md"
    for path in changed_paths(target, pre_head, post_head):
        if path.startswith("automation/reviewed_handoff/") and path != own_current:
            errors.append(f"Executor changed Planner/Reviewer/control authority path: {path}")
            continue
        review_match = re.fullmatch(r"results/([^/]+)/REVIEW_\d+\.md", path)
        final_match = re.fullmatch(r"results/([^/]+)/FINAL_REPORT\.md", path)
        result_match = re.fullmatch(r"results/([^/]+)/RESULT\.md", path)
        if review_match or final_match:
            errors.append(f"Executor changed Reviewer/user-report authority path: {path}")
        elif result_match and path != own_result:
            errors.append(f"Executor changed another Reviewed Handoff task result: {path}")
    return errors


def push_guard_environment(target: Path) -> dict[str, str]:
    """Install a process-local pre-push guard for Codex; watcher remains the publisher."""
    hooks_dir = machine_task_root(target) / "git-hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        "echo 'Reviewed Handoff Executor must not push; the watcher owns validated publication.' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    try:
        hook.chmod(0o700)
    except OSError:
        pass
    env = os.environ.copy()
    try:
        count = int(env.get("GIT_CONFIG_COUNT", "0") or "0")
    except ValueError:
        count = 0
    env["GIT_CONFIG_COUNT"] = str(count + 1)
    env[f"GIT_CONFIG_KEY_{count}"] = "core.hooksPath"
    env[f"GIT_CONFIG_VALUE_{count}"] = str(hooks_dir)
    return env


def executor_prompt(target: Path, task_key: str, current: dict[str, Any], branch: str) -> str:
    state = current.get("state")
    ci_instruction = (
        "This task requires GitHub CI. After local tests and commits, keep `ci_status=PENDING` and finish in "
        "`WAITING_FOR_CI`; do not claim GitHub CI PASS locally."
        if current.get("ci_required")
        else "This task does not require GitHub CI; finish successful local execution in `READY_FOR_GPT_REVIEW`."
    )
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

Use the already checked-out existing branch `{branch}`. Do not create a branch or PR. Do not push. The watcher is the sole publisher for Executor events and will push only after validating your committed diff and workflow state. A pre-push guard is installed for this Codex process intentionally.

Never modify `REQUEST.md`, `PLAN.md`, previous `REVIEW_<n>.md`, `FINAL_REPORT.md`, Reviewed Handoff schema/prompts/templates, review counters/limits, Planner counters/limits, base Git locators, CI requirement, or Reviewer decisions. You may update only Executor-owned workflow outputs such as this task's `CURRENT.state`, `implementation_commit`, `ci_status`, `next_action`, and `results/{task_key}/RESULT.md`, in addition to the actual Plan-owned implementation files.

{ci_instruction}

When implementation is complete, run the real local acceptance/regression checks, create an implementation commit containing the Plan-owned implementation changes, then write/update `results/{task_key}/RESULT.md` and `CURRENT.json` with that implementation commit as a locator in a separate control-plane commit. Leave the working tree clean. Do not add provenance hashes, receipt graphs, or Agent-Flow artifacts.
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
        return {
            "task_key": task_key,
            "event": event_identity(task_key, current),
            "command": command,
            "prompt": prompt,
            "launched": False,
        }

    event = event_identity(task_key, current)
    pre_head = git_output(target, ["rev-parse", "HEAD"])
    log_dir = log_root(target) / task_key
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_name(task_key, current)
    started = time.time()
    started_at = utc_now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n=== watcher launch: {event} ===\n")
        proc = subprocess.run(
            command,
            cwd=target,
            input=prompt,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=push_guard_environment(target),
            check=False,
        )
    post_path = rh.task_root(target, task_key) / "CURRENT.json"
    post_current = rh.load_json(post_path) if post_path.exists() else {}
    post_head = git_output(target, ["rev-parse", "HEAD"])
    progressed = event_identity(task_key, post_current) != event or post_current.get("state") not in ELIGIBLE_EXECUTOR_STATES
    return {
        "task_key": task_key,
        "event": event,
        "command": command,
        "launched": True,
        "exit_code": proc.returncode,
        "progressed": progressed,
        "post_state": post_current.get("state"),
        "pre_head": pre_head,
        "post_head": post_head,
        "log_path": str(log_path),
        "runtime_type": "codex_exec",
        "thread_id": None,
        "started_at": started_at,
        "completed_at": utc_now(),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def publish_operational_blocker(
    target: Path,
    task_key: str,
    *,
    branch: str,
    event: str,
    attempts: int,
    log_path: str | None,
) -> dict[str, Any]:
    current_path = rh.task_root(target, task_key) / "CURRENT.json"
    current = rh.load_json(current_path)
    result_dir = rh.result_root(target, task_key)
    result_dir.mkdir(parents=True, exist_ok=True)
    final_path = result_dir / "FINAL_REPORT.md"
    final_path.write_text(
        "# Final Report\n\n"
        "## What this task solved\n\n"
        "Reviewed Handoff could not complete this task automatically because the local Codex watcher exhausted its bounded execution attempts. No successful final implementation is claimed.\n\n"
        "## What changed\n\n"
        "The workflow stopped at an operational boundary rather than silently retrying forever. Any uncommitted local changes must be inspected before resuming.\n\n"
        "## New capabilities / behavior\n\n"
        "No new capability is claimed until the execution blocker is resolved and the normal GPT review loop completes.\n\n"
        "## Deliberately not adopted / unchanged\n\n"
        "The watcher did not discard or reset potentially useful local work and did not create a new branch.\n\n"
        "## Example usage\n\n"
        "After resolving the local Codex/runtime problem, resume the same Reviewed Handoff task rather than creating a replacement task.\n\n"
        "## Regression and remaining limitations\n\n"
        f"Executor event `{event}` did not make validated workflow progress after {attempts} attempts. Inspect the local watcher log before recovery.\n\n"
        "## Technical appendix\n\n"
        f"- task: `{task_key}`\n- watcher log: `{log_path or 'unavailable'}`\n- state before blocker: `{current.get('state')}`\n",
        encoding="utf-8",
    )
    current["state"] = "BLOCKED"
    current["next_action"] = "HUMAN_OPERATIONAL_RECOVERY"
    current["runner_failure"] = {"event": event, "attempts": attempts, "log_path": log_path}
    rh.write_json(current_path, current)

    rel_current = str(current_path.relative_to(target))
    rel_final = str(final_path.relative_to(target))
    try:
        # --only commits exactly the control files, preserving unrelated dirty implementation work.
        git_output(target, ["add", rel_current, rel_final])
        git_output(target, ["commit", "--only", rel_current, rel_final, "-m", f"Block Reviewed Handoff task {task_key} after runner failure"])
        git_output(target, ["push", "origin", branch])
        return {"published": True, "state": "BLOCKED", "final_report": rel_final}
    except Exception as exc:
        return {"published": False, "error": str(exc), "state": "BLOCKED", "final_report": rel_final}


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
        recovery = recover_unpublished_executor_progress(target, selected_branch)
        if recovery.get("status") == "recovered_unpublished_progress":
            return recovery
        if recovery.get("status") == "unpublished_progress_recovery_failed":
            return {"branch": selected_branch, **recovery}
        sync_origin_ff_only(target, selected_branch)
    else:
        ensure_clean_repo(target)

    validation_lines, validation_code = rh.validate_reviewed_handoff(target)
    if validation_code:
        record_watcher_status(target, "invalid_workflow", branch=selected_branch, errors=validation_lines)
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
            blocker = publish_operational_blocker(
                target,
                task_key,
                branch=selected_branch,
                event=event,
                attempts=attempts,
                log_path=prior.get("last_log_path"),
            )
            return {"status": "event_exhausted", "task_key": task_key, "event": event, "attempts": attempts, "blocker": blocker}
        if dry_run:
            return {
                "status": "dry_run",
                **run_codex_event(target, task_key, current, branch=selected_branch, codex_bin=codex_bin, dry_run=True),
            }

        pre_current = dict(current)
        record_event_start(
            target,
            branch=selected_branch,
            task_key=task_key,
            current=current,
            event=event,
            attempts=attempts + 1,
        )
        result = run_codex_event(target, task_key, current, branch=selected_branch, codex_bin=codex_bin)
        attempts += 1
        post_current_path = rh.task_root(target, task_key) / "CURRENT.json"
        post_current = rh.load_json(post_current_path) if post_current_path.exists() else {}
        dirty_after = working_tree_dirty(target)
        authority_errors = executor_authority_errors(
            target,
            task_key,
            pre_current,
            post_current,
            str(result.get("pre_head") or ""),
            str(result.get("post_head") or ""),
        ) if result.get("progressed") and not dirty_after else []
        workflow_errors = (
            rh.validate_task(target, task_key)
            if result.get("progressed") and not dirty_after and not authority_errors
            else []
        )
        completed = bool(result.get("progressed")) and not dirty_after and not authority_errors and not workflow_errors
        publication_error: str | None = None
        if completed and sync:
            published, publication_error = publish_clean_progress(target, selected_branch)
            completed = published
        publication_status = "not_requested"
        if sync:
            publication_status = "published" if completed else ("publication_failed" if publication_error else "not_published")

        local = load_local_state(target)
        events = local.setdefault("events", {})
        local["last_status"] = {
            "status": "codex_progressed" if completed else "executor_not_completed",
            "branch": selected_branch,
            "errors": authority_errors + workflow_errors + ([publication_error] if publication_error else []),
            "recorded_at": utc_now(),
        }
        events[event] = {
            **(events.get(event, {}) if isinstance(events.get(event), dict) else {}),
            "attempts": attempts,
            "completed": completed,
            "completed_at": utc_now(),
            "running": False,
            "last_exit_code": result.get("exit_code"),
            "last_progressed": result.get("progressed"),
            "last_result": "completed" if completed else "not_completed",
            "last_log_path": result.get("log_path"),
            "last_authority_errors": authority_errors,
            "last_workflow_errors": workflow_errors,
            "last_publication_error": publication_error,
            "last_publication_status": publication_status,
        }
        write_local_state(target, local)

        if completed:
            result["status"] = "codex_progressed"
            result["attempt"] = attempts
            return result

        if authority_errors:
            events[event]["completed"] = True
            events[event]["manual_recovery_required"] = True
            write_local_state(target, local)
            result.update(
                status="codex_authority_violation",
                attempt=attempts,
                authority_errors=authority_errors,
                reason="Executor changed Planner/Reviewer authority; local commits were not published",
            )
            return result

        # If Codex committed something but never produced a valid state transition, do not publish or retry over it.
        if not result.get("progressed") and result.get("post_head") != result.get("pre_head"):
            events[event]["completed"] = True
            events[event]["manual_recovery_required"] = True
            write_local_state(target, local)
            result.update(
                status="local_manual_recovery_required",
                attempt=attempts,
                reason="Codex advanced local Git history without publishing a valid Reviewed Handoff state; commits were not auto-pushed",
            )
            return result

        # If this Codex invocation itself left uncommitted work, do not launch another Codex over it.
        if dirty_after:
            if result.get("post_head") == result.get("pre_head"):
                blocker = publish_operational_blocker(
                    target,
                    task_key,
                    branch=selected_branch,
                    event=event,
                    attempts=attempts,
                    log_path=result.get("log_path"),
                )
                events[event]["completed"] = True
                events[event]["terminated_dirty"] = True
                write_local_state(target, local)
                result.update(status="codex_dirty_blocked", attempt=attempts, blocker=blocker)
                return result
            events[event]["completed"] = True
            events[event]["manual_recovery_required"] = True
            write_local_state(target, local)
            result.update(
                status="local_manual_recovery_required",
                attempt=attempts,
                reason="Codex left a dirty tree after advancing local Git history; partial commits are not auto-pushed",
            )
            return result

        if workflow_errors:
            result["status"] = "codex_invalid_progress"
            result["workflow_errors"] = workflow_errors
        elif publication_error:
            result["status"] = "codex_unpublished_progress"
            result["publication_error"] = publication_error
        elif result.get("exit_code") == 0:
            result["status"] = "codex_no_progress"
        else:
            result["status"] = "codex_failed"
        result["attempt"] = attempts
        return result
    waiting = external_wait_events(target)
    if waiting:
        task_key, status = waiting[0]
        return {"status": status.get("operational_status"), "branch": selected_branch, "task_key": task_key, **status}
    return {"status": "idle", "branch": selected_branch}


def watcher_status(target: Path, *, branch: str | None = None) -> dict[str, Any]:
    target = target.resolve()
    selected_branch = resolve_branch(target, branch)
    local = load_local_state(target)
    events = local.get("events", {}) if isinstance(local.get("events"), dict) else {}
    tasks: list[dict[str, Any]] = []
    tasks_dir = rh.reviewed_root(target) / "tasks"
    if tasks_dir.exists():
        for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
            current_path = task_dir / "CURRENT.json"
            if not current_path.exists():
                continue
            current = rh.load_json(current_path)
            event = event_identity(task_dir.name, current)
            runtime = events.get(event, {}) if isinstance(events.get(event), dict) else {}
            tasks.append(
                {
                    "task": task_dir.name,
                    "state": current.get("state"),
                    "executor_event": event,
                    "phase": executor_phase(current),
                    "thread_id": runtime.get("thread_id"),
                    "runtime_type": runtime.get("runtime_type") or "codex_exec",
                    "started_at": runtime.get("started_at"),
                    "running": bool(runtime.get("running")),
                    "completed": bool(runtime.get("completed")),
                    "completed_at": runtime.get("completed_at"),
                    "last_exit_code": runtime.get("last_exit_code"),
                    "last_result": runtime.get("last_result"),
                    "waiting_owner": waiting_owner(target, task_dir.name, current),
                    "last_publication_status": runtime.get("last_publication_status"),
                    "last_publication_error": runtime.get("last_publication_error"),
                    "last_log_path": runtime.get("last_log_path"),
                }
            )
    return {
        "schema": "AI_BRIDGE_REVIEWED_WATCHER_STATUS_V1",
        "target": str(target),
        "branch": selected_branch,
        "state_path": str(state_path(target)),
        "last_status": local.get("last_status"),
        "last_invalid_workflow": local.get("last_invalid_workflow"),
        "tasks": tasks,
    }


def watcher_sleep_seconds(status: str | None, interval_seconds: int, *, invalid_workflow_streak: int = 0) -> int:
    if status == "invalid_workflow":
        multiplier = 2 ** min(max(invalid_workflow_streak - 1, 0), 3)
        return min(3600, max(600, interval_seconds * multiplier))
    if status in {"waiting_external_review", "waiting_visual_review_evidence"}:
        return max(600, interval_seconds)
    return max(5, interval_seconds)


def watcher_run(
    target: Path,
    *,
    branch: str | None = None,
    codex_bin: str = "codex",
    interval_seconds: int = 60,
    max_cycles: int | None = None,
) -> int:
    cycles = 0
    invalid_workflow_streak = 0
    stop_statuses = {
        "local_manual_recovery_required",
        "event_exhausted",
        "codex_dirty_blocked",
        "codex_authority_violation",
        "codex_invalid_progress",
        "codex_unpublished_progress",
        "unpublished_progress_recovery_failed",
    }
    while True:
        result: dict[str, Any] = {}
        try:
            result = watcher_once(target, branch=branch, codex_bin=codex_bin, sync=True, dry_run=False)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
            if result.get("status") == "invalid_workflow":
                invalid_workflow_streak += 1
            else:
                invalid_workflow_streak = 0
            if result.get("status") in stop_statuses:
                return 1
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(json.dumps({"status": "watcher_error", "error": str(exc)}, ensure_ascii=False), flush=True)
            return 1
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return 0
        sleep_seconds = watcher_sleep_seconds(
            str(result.get("status") or ""),
            interval_seconds,
            invalid_workflow_streak=invalid_workflow_streak,
        )
        time.sleep(sleep_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge reviewed-handoff watcher")
    sub = parser.add_subparsers(dest="command")
    once = sub.add_parser("once")
    once.add_argument("--target", type=Path, default=Path.cwd())
    once.add_argument("--branch")
    once.add_argument("--codex-bin", default="codex")
    once.add_argument("--no-sync", action="store_true")
    once.add_argument("--dry-run", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--target", type=Path, default=Path.cwd())
    status.add_argument("--branch")
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
        failure_statuses = {
            "invalid_workflow",
            "codex_failed",
            "codex_invalid_progress",
            "codex_unpublished_progress",
            "event_exhausted",
            "codex_dirty_blocked",
            "codex_authority_violation",
            "local_manual_recovery_required",
            "unpublished_progress_recovery_failed",
        }
        return 0 if result.get("status") not in failure_statuses else 1
    if args.command == "status":
        print(json.dumps(watcher_status(args.target, branch=args.branch), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
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
