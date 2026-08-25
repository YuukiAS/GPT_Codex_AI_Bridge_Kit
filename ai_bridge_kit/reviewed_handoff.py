from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import external_wait
from . import visual_review


SCHEMA_NAME = "AI_BRIDGE_REVIEWED_HANDOFF_SCHEMA_V1"
CURRENT_SCHEMA = "AI_BRIDGE_REVIEWED_CURRENT_V1"
REVIEW_SCHEMA = "AI_BRIDGE_REVIEWED_REVIEW_V1"
TASK_KEY_RE = re.compile(r"^\d+_[A-Za-z0-9]+(?:_[A-Za-z0-9]+){0,2}$")

TASK_STATES = {
    "PLAN_REQUESTED",
    "PLAN_FROZEN",
    "EXECUTING",
    "WAITING_FOR_CI",
    "NEEDS_GPT_PLANNER",
    "READY_FOR_GPT_REVIEW",
    "REVISE",
    "PASS",
    "AWAIT_HUMAN_DECISION",
    "BLOCKED",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PLAN_REQUESTED": {"PLAN_FROZEN", "BLOCKED"},
    "PLAN_FROZEN": {"EXECUTING", "BLOCKED"},
    "EXECUTING": {"WAITING_FOR_CI", "READY_FOR_GPT_REVIEW", "NEEDS_GPT_PLANNER", "BLOCKED"},
    "WAITING_FOR_CI": {"READY_FOR_GPT_REVIEW", "REVISE", "BLOCKED"},
    "NEEDS_GPT_PLANNER": {"PLAN_FROZEN", "AWAIT_HUMAN_DECISION", "BLOCKED"},
    "READY_FOR_GPT_REVIEW": {"REVISE", "PASS", "BLOCKED"},
    "REVISE": {"EXECUTING", "NEEDS_GPT_PLANNER", "AWAIT_HUMAN_DECISION", "BLOCKED"},
    "PASS": {"AWAIT_HUMAN_DECISION"},
    "AWAIT_HUMAN_DECISION": set(),
    "BLOCKED": set(),
}

REVIEW_DECISIONS = {"PASS", "REVISE", "BLOCKED"}
TERMINAL_STATES = {"AWAIT_HUMAN_DECISION", "BLOCKED"}
EXTERNAL_WAIT_STATE_OWNERS = {
    "NEEDS_GPT_PLANNER": "Planner",
    "READY_FOR_GPT_REVIEW": "Reviewer",
}
FINAL_REPORT_HEADINGS = [
    "## What this task solved",
    "## What changed",
    "## New capabilities / behavior",
    "## Example usage",
    "## Regression and remaining limitations",
    "## Technical appendix",
]

REQUIRED_CORE_FILES = [
    "README.md",
    "schema.json",
    "prompts/PLANNER.md",
    "prompts/REVIEWER_SCHEDULED_TASK.md",
    "prompts/CODEX_EXECUTOR.md",
    "templates/REQUEST.md",
    "templates/PLAN.md",
    "templates/RESULT.md",
    "templates/REVIEW.md",
    "templates/FINAL_REPORT.md",
]


@dataclass
class ReviewedStatus:
    target: Path
    installed: bool
    missing: list[str]
    task_count: int


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def reviewed_root(target: Path) -> Path:
    return target.resolve() / "automation" / "reviewed_handoff"


def task_root(target: Path, task_key: str) -> Path:
    return reviewed_root(target) / "tasks" / task_key


def result_root(target: Path, task_key: str) -> Path:
    return target.resolve() / "results" / task_key


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def git_output(target: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=target, text=True, stderr=subprocess.DEVNULL).strip()


def current_commit(target: Path) -> str:
    try:
        return git_output(target, ["rev-parse", "HEAD"])
    except Exception:
        return "UNKNOWN"


def current_branch(target: Path) -> str:
    try:
        return git_output(target, ["branch", "--show-current"]) or "DETACHED"
    except Exception:
        return "UNKNOWN"


def git_repo_available(target: Path) -> bool:
    try:
        return git_output(target, ["rev-parse", "--is-inside-work-tree"]) == "true"
    except Exception:
        return False


def git_commit_exists(target: Path, commit: str) -> bool:
    if not commit or commit == "UNKNOWN" or not git_repo_available(target):
        return False
    try:
        subprocess.check_call(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=target,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def git_is_ancestor(target: Path, base_commit: str, implementation_commit: str) -> bool:
    if not git_commit_exists(target, base_commit) or not git_commit_exists(target, implementation_commit):
        return False
    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", base_commit, implementation_commit],
            cwd=target,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str | None]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}, "missing opening YAML frontmatter marker"
    end = text.find("\n---", 4)
    if end == -1:
        return {}, "missing closing YAML frontmatter marker"
    data: dict[str, str] = {}
    for line_number, line in enumerate(text[4:end].splitlines(), start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace() or stripped.startswith("-"):
            continue
        if ":" not in stripped:
            return data, f"invalid frontmatter line {line_number}: {line}"
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, None


def _copy_template(src: Path, dst: Path, *, force: bool, actions: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        actions.append(f"SKIP existing file: {dst}")
        return
    existed = dst.exists()
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    actions.append(f"COPY {'overwrite' if existed else 'create'}: {dst}")


def install_reviewed_handoff(target: Path, *, force: bool = False) -> tuple[ReviewedStatus, list[str]]:
    target = target.resolve()
    source = kit_root() / "templates" / "reviewed_handoff"
    if not source.exists():
        raise ValueError("reviewed-handoff templates are missing from the Bridge Kit installation")
    root = reviewed_root(target)
    actions: list[str] = []
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_CORE_FILES:
        _copy_template(source / rel, root / rel, force=force, actions=actions)
    return inspect_reviewed_handoff(target), actions


def inspect_reviewed_handoff(target: Path) -> ReviewedStatus:
    target = target.resolve()
    root = reviewed_root(target)
    missing = [rel for rel in REQUIRED_CORE_FILES if not (root / rel).exists()]
    tasks_dir = root / "tasks"
    task_count = len([p for p in tasks_dir.iterdir() if p.is_dir()]) if tasks_dir.exists() else 0
    return ReviewedStatus(target=target, installed=root.exists() and not missing, missing=missing, task_count=task_count)


def format_status(status: ReviewedStatus) -> str:
    state = "configured" if status.installed else "missing"
    lines = [
        f"Reviewed Handoff: {state}",
        f"Target: {status.target}",
        f"Tasks: {status.task_count}",
    ]
    if status.missing:
        lines.append("Missing: " + ", ".join(status.missing))
    return "\n".join(lines)


def init_task(
    target: Path,
    task_key: str,
    *,
    objective: str = "",
    max_review_rounds: int = 2,
    ci_required: bool = False,
    visual_review_required: bool = False,
    visual_review_manifest_path: str = "",
) -> list[str]:
    target = target.resolve()
    if not TASK_KEY_RE.fullmatch(task_key):
        raise ValueError("task_key must look like <id>_<1-3-word_slug>, for example 001_skill_intake")
    if max_review_rounds not in {1, 2}:
        raise ValueError("Reviewed Handoff allows max_review_rounds of 1 or 2")
    status = inspect_reviewed_handoff(target)
    if not status.installed:
        raise ValueError("Reviewed Handoff is not installed; run reviewed-handoff install first")
    root = task_root(target, task_key)
    if root.exists():
        raise ValueError(f"Reviewed Handoff task already exists: {task_key}")
    root.mkdir(parents=True)
    result_root(target, task_key).mkdir(parents=True, exist_ok=True)
    request_template = read_text(reviewed_root(target) / "templates" / "REQUEST.md")
    request_text = request_template.replace("<TASK_KEY>", task_key).replace(
        "<OBJECTIVE>", objective.strip() or "TODO: GPT Planner should write the task objective."
    )
    write_text(root / "REQUEST.md", request_text)
    current = {
        "schema": CURRENT_SCHEMA,
        "task_key": task_key,
        "state": "PLAN_REQUESTED",
        "review_round": 0,
        "max_review_rounds": max_review_rounds,
        "plan_revision": 0,
        "max_plan_revisions": 1,
        "base_commit": current_commit(target),
        "base_branch": current_branch(target),
        "implementation_commit": None,
        "ci_required": ci_required,
        "ci_status": "PENDING" if ci_required else "NOT_REQUIRED",
        "last_review_decision": None,
        "next_action": "RUN_GPT_PLANNER",
    }
    if visual_review_required:
        current["visual_review_required"] = True
        current["visual_review_manifest_path"] = visual_review_manifest_path or f"results/{task_key}/visual_review/visual_inputs.json"
        current["visual_review_evidence_path"] = f"results/{task_key}/visual_review/VISUAL_REVIEW.json"
    write_json(root / "CURRENT.json", current)
    return [
        f"CREATE {root / 'REQUEST.md'}",
        f"CREATE {root / 'CURRENT.json'}",
        f"DIR {result_root(target, task_key)}",
    ]


def validate_plan_file(path: Path, task_key: str) -> list[str]:
    data, parse_error = parse_frontmatter(path)
    errors: list[str] = []
    if parse_error:
        return [f"PLAN.md: {parse_error}"]
    if data.get("schema") != "AI_BRIDGE_REVIEWED_PLAN_V1":
        errors.append("PLAN.md schema mismatch")
    if data.get("task_key") != task_key:
        errors.append("PLAN.md task_key mismatch")
    if data.get("decision") != "PLAN_FROZEN":
        errors.append("PLAN.md decision must be PLAN_FROZEN")
    text = read_text(path)
    for heading in [
        "## Frozen decisions",
        "## Implementation scope",
        "## Acceptance and regression gates",
        "## Out of scope",
    ]:
        if heading not in text:
            errors.append(f"PLAN.md missing required section: {heading}")
    return errors


def validate_result_file(path: Path, task_key: str, current: dict[str, Any]) -> list[str]:
    data, parse_error = parse_frontmatter(path)
    errors: list[str] = []
    if parse_error:
        return [f"RESULT.md: {parse_error}"]
    if data.get("schema") != "AI_BRIDGE_REVIEWED_RESULT_V1":
        errors.append("RESULT.md schema mismatch")
    if data.get("task_key") != task_key:
        errors.append("RESULT.md task_key mismatch")
    commit = str(current.get("implementation_commit") or "")
    if data.get("implementation_commit") != commit:
        errors.append("RESULT.md implementation_commit must match CURRENT")
    return errors


def visual_review_evidence_path(target: Path, task_key: str, current: dict[str, Any]) -> Path:
    rel = str(current.get("visual_review_evidence_path") or f"results/{task_key}/visual_review/VISUAL_REVIEW.json")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("visual_review_evidence_path must be repository-relative")
    return target.resolve() / rel


def visual_review_manifest_path(target: Path, task_key: str, current: dict[str, Any]) -> Path:
    rel = str(current.get("visual_review_manifest_path") or f"results/{task_key}/visual_review/visual_inputs.json")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("visual_review_manifest_path must be repository-relative")
    return target.resolve() / rel


def validate_visual_review_manifest(target: Path, task_key: str, current: dict[str, Any]) -> list[str]:
    path = visual_review_manifest_path(target, task_key, current)
    if not path.exists():
        return [f"visual review input manifest missing: {path.relative_to(target.resolve())}"]
    try:
        manifest = visual_review.normalize_manifest(target.resolve(), load_json(path))
    except Exception as exc:
        return [f"visual review input manifest invalid: {exc}"]
    errors: list[str] = []
    if manifest.get("task_key") != task_key:
        errors.append("visual review input manifest task_key mismatch")
    if manifest.get("workflow_type") != "reviewed_handoff":
        errors.append("visual review input manifest workflow_type must be reviewed_handoff")
    bindings = manifest.get("identity_bindings") if isinstance(manifest.get("identity_bindings"), dict) else {}
    if bindings.get("implementation_commit") != str(current.get("implementation_commit") or ""):
        errors.append("visual review input manifest implementation_commit must match CURRENT")
    return errors


def reviewed_visual_review_status(target: Path, task_key: str, current: dict[str, Any]) -> dict[str, Any]:
    if not current.get("visual_review_required"):
        return {"required": False, "status": "NOT_REQUIRED", "errors": []}
    path = visual_review_evidence_path(target, task_key, current)
    if not path.exists():
        manifest_errors = validate_visual_review_manifest(target, task_key, current)
        if manifest_errors:
            return {
                "required": True,
                "status": "INVALID",
                "path": str(path.relative_to(target.resolve())),
                "manifest_path": str(visual_review_manifest_path(target, task_key, current).relative_to(target.resolve())),
                "errors": manifest_errors,
            }
        return {
            "required": True,
            "status": "PENDING",
            "path": str(path.relative_to(target.resolve())),
            "manifest_path": str(visual_review_manifest_path(target, task_key, current).relative_to(target.resolve())),
            "errors": ["visual review evidence pending"],
        }
    try:
        payload = load_json(path)
    except Exception as exc:
        return {"required": True, "status": "INVALID", "path": str(path.relative_to(target.resolve())), "errors": [f"VISUAL_REVIEW.json unreadable: {exc}"]}
    expected = {
        "task_key": task_key,
        "workflow_type": "reviewed_handoff",
        "implementation_commit": str(current.get("implementation_commit") or ""),
    }
    errors = visual_review.validate_visual_review_payload(payload, expected=expected)
    decision = payload.get("overall_decision")
    if errors:
        return {"required": True, "status": "INVALID", "path": str(path.relative_to(target.resolve())), "errors": errors}
    if decision == "BLOCKED":
        return {"required": True, "status": "BLOCKED", "path": str(path.relative_to(target.resolve())), "errors": []}
    if decision == "REVISE":
        return {"required": True, "status": "REVISE", "path": str(path.relative_to(target.resolve())), "errors": []}
    return {"required": True, "status": "PASS", "path": str(path.relative_to(target.resolve())), "errors": []}


def validate_final_report(path: Path) -> list[str]:
    if not path.exists():
        return ["terminal state requires FINAL_REPORT.md"]
    text = read_text(path)
    errors: list[str] = []
    for heading in FINAL_REPORT_HEADINGS:
        if heading not in text:
            errors.append(f"FINAL_REPORT.md missing required section: {heading}")
    return errors


def review_files(target: Path, task_key: str) -> list[Path]:
    return sorted(result_root(target, task_key).glob("REVIEW_*.md"))


def validate_review_file(path: Path, task_key: str, expected_round: int | None = None) -> tuple[dict[str, str], list[str]]:
    data, parse_error = parse_frontmatter(path)
    errors: list[str] = []
    if parse_error:
        return data, [f"{path.name}: {parse_error}"]
    required = ["schema", "task_key", "review_round", "decision", "implementation_commit"]
    for key in required:
        if not data.get(key):
            errors.append(f"{path.name}: missing {key}")
    if data.get("schema") != REVIEW_SCHEMA:
        errors.append(f"{path.name}: schema mismatch")
    if data.get("task_key") != task_key:
        errors.append(f"{path.name}: task_key mismatch")
    try:
        round_number = int(data.get("review_round", ""))
    except ValueError:
        round_number = -1
        errors.append(f"{path.name}: invalid review_round")
    if expected_round is not None and round_number != expected_round:
        errors.append(f"{path.name}: expected review_round {expected_round}, found {round_number}")
    if data.get("decision") not in REVIEW_DECISIONS:
        errors.append(f"{path.name}: invalid decision {data.get('decision')}")
    return data, errors


def latest_review_metadata(target: Path, task_key: str) -> tuple[dict[str, str] | None, Path | None, list[str]]:
    reviews = review_files(target, task_key)
    if not reviews:
        return None, None, []
    latest = reviews[-1]
    data, errors = validate_review_file(latest, task_key, expected_round=len(reviews))
    return data, latest, errors


def reviewed_external_wait_status(target: Path, task_key: str, *, now: Any = None) -> dict[str, Any]:
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    state = str(current.get("state") or "")
    visual_status = reviewed_visual_review_status(target, task_key, current)
    if state == "READY_FOR_GPT_REVIEW" and visual_status.get("required") and visual_status.get("status") == "PENDING":
        return {
            "operational_status": "waiting_visual_review_evidence",
            "external_owner": "GitHub Actions",
            "wait_owner": "Visual Review",
            "current_identity": str(current.get("implementation_commit") or "").strip() or None,
            "fresh_decision": False,
            "stale_decision": False,
            "may_block": False,
            "visual_review": visual_status,
            "blocker_required_evidence": [
                "GitHub Actions visual-review workflow is disabled, expired, unauthenticated, or lacks required secret access",
                "visual input manifest or image artifact is inaccessible from the published branch",
                "VISUAL_REVIEW.json cannot be produced because of a concrete service failure",
            ],
        }
    owner_map = dict(EXTERNAL_WAIT_STATE_OWNERS)
    if state == "WAITING_FOR_CI" and current.get("ci_status") in {"PASS", "FAIL"}:
        owner_map["WAITING_FOR_CI"] = "Reviewer"
    latest, latest_path, review_errors = latest_review_metadata(target, task_key)
    status = external_wait.build_wait_status(
        current,
        current_identity=str(current.get("implementation_commit") or ""),
        latest_decision_identity=(latest or {}).get("implementation_commit"),
        latest_decision_path=str(latest_path.relative_to(target)) if latest_path else None,
        latest_decision=(latest or {}).get("decision"),
        state_owner_map=owner_map,
        external_failure_evidence=review_errors,
        now=now,
    )
    if status["operational_status"] == "not_external_gpt_wait" and state == "WAITING_FOR_CI":
        status["wait_owner"] = "CI"
    return status


def validate_task(target: Path, task_key: str) -> list[str]:
    target = target.resolve()
    root = task_root(target, task_key)
    errors: list[str] = []
    current_path = root / "CURRENT.json"
    request_path = root / "REQUEST.md"
    if not request_path.exists():
        errors.append("REQUEST.md missing")
    if not current_path.exists():
        return errors + ["CURRENT.json missing"]
    try:
        current = load_json(current_path)
    except Exception as exc:
        return errors + [f"CURRENT.json unreadable: {exc}"]
    if current.get("schema") != CURRENT_SCHEMA:
        errors.append("CURRENT.schema mismatch")
    if current.get("task_key") != task_key:
        errors.append("CURRENT.task_key mismatch")
    state = current.get("state")
    if state not in TASK_STATES:
        errors.append(f"CURRENT.state invalid: {state}")
    max_reviews = current.get("max_review_rounds")
    if max_reviews not in {1, 2}:
        errors.append("CURRENT.max_review_rounds must be 1 or 2")
    plan_revision = current.get("plan_revision")
    if not isinstance(plan_revision, int) or plan_revision < 0 or plan_revision > 1:
        errors.append("CURRENT.plan_revision must be 0 or 1")

    plan_path = root / "PLAN.md"
    if state != "PLAN_REQUESTED":
        if not plan_path.exists():
            errors.append(f"{state} requires PLAN.md")
        else:
            errors.extend(validate_plan_file(plan_path, task_key))

    result_path = result_root(target, task_key) / "RESULT.md"
    implementation_bound = state in {"WAITING_FOR_CI", "READY_FOR_GPT_REVIEW", "REVISE", "PASS"} or (
        state in TERMINAL_STATES and bool(current.get("implementation_commit"))
    )
    if implementation_bound:
        if not result_path.exists():
            errors.append(f"{state} requires results/{task_key}/RESULT.md")
        commit = str(current.get("implementation_commit") or "").strip()
        if not commit:
            errors.append(f"{state} requires implementation_commit locator")
        else:
            if result_path.exists():
                errors.extend(validate_result_file(result_path, task_key, current))
            if git_repo_available(target):
                if not git_commit_exists(target, commit):
                    errors.append(f"{state} implementation_commit is not a real Git commit locator")
                base_commit = str(current.get("base_commit") or "")
                if git_commit_exists(target, commit) and git_commit_exists(target, base_commit):
                    if not git_is_ancestor(target, base_commit, commit):
                        errors.append(f"{state} implementation_commit is not descended from base_commit")

        ci_required = bool(current.get("ci_required"))
        ci_status = current.get("ci_status")
        if state == "WAITING_FOR_CI":
            if not ci_required:
                errors.append("WAITING_FOR_CI requires ci_required=true")
            if ci_status not in {"PENDING", "PASS", "FAIL"}:
                errors.append("WAITING_FOR_CI ci_status must be PENDING, PASS, or FAIL")
        elif ci_required and state in {"READY_FOR_GPT_REVIEW", "PASS"}:
            if ci_status != "PASS":
                errors.append(f"{state} requires ci_status=PASS")
        elif ci_required and state == "AWAIT_HUMAN_DECISION" and current.get("human_gate_reason") == "PASS":
            if ci_status != "PASS":
                errors.append("PASS human gate requires ci_status=PASS")
        elif ci_required:
            if ci_status not in {"PENDING", "PASS", "FAIL"}:
                errors.append(f"{state} has invalid ci_status: {ci_status}")
        elif ci_status not in {"NOT_REQUIRED", "PASS"}:
            errors.append(f"{state} requires ci_status=NOT_REQUIRED or PASS when CI is not required")

        visual_status = reviewed_visual_review_status(target, task_key, current)
        if visual_status.get("required"):
            status = visual_status.get("status")
            if status == "INVALID":
                errors.extend(str(item) for item in visual_status.get("errors", []))
            elif status == "PENDING" and state != "READY_FOR_GPT_REVIEW":
                errors.append(f"{state} requires current VISUAL_REVIEW.json before leaving visual evidence pending")
            elif state == "PASS" and status != "PASS":
                errors.append("PASS requires visual review PASS evidence")
            elif state == "AWAIT_HUMAN_DECISION" and current.get("human_gate_reason") == "PASS" and status != "PASS":
                errors.append("PASS human gate requires visual review PASS evidence")

    reviews = review_files(target, task_key)
    if len(reviews) > 2:
        errors.append("Reviewed Handoff allows at most two GPT review artifacts")
    latest_data: dict[str, str] | None = None
    for index, path in enumerate(reviews, start=1):
        data, review_errors = validate_review_file(path, task_key, expected_round=index)
        errors.extend(review_errors)
        latest_data = data
    if current.get("review_round") != len(reviews):
        errors.append("CURRENT.review_round must equal the number of REVIEW_<n>.md artifacts")
    if current.get("last_review_decision") in REVIEW_DECISIONS and not latest_data:
        errors.append("CURRENT.last_review_decision requires a GPT review artifact")
    if latest_data:
        if current.get("last_review_decision") != latest_data.get("decision"):
            errors.append("CURRENT.last_review_decision must match the latest review artifact")
        latest_commit = latest_data.get("implementation_commit")
        if state in {"REVISE", "PASS", "AWAIT_HUMAN_DECISION", "BLOCKED"} and latest_commit != str(current.get("implementation_commit")):
            errors.append("latest review must be bound to CURRENT implementation_commit")
        decision = latest_data.get("decision")
        if state == "REVISE" and decision != "REVISE":
            errors.append("REVISE state requires latest review decision REVISE")
        if state == "PASS" and decision != "PASS":
            errors.append("PASS state requires latest review decision PASS")
    elif state in {"REVISE", "PASS"}:
        errors.append(f"{state} requires at least one REVIEW_<n>.md artifact")

    if state == "PASS" and current.get("review_round", 0) < 1:
        errors.append("PASS requires at least one GPT review")
    if state == "AWAIT_HUMAN_DECISION":
        gate_reason = current.get("human_gate_reason")
        if current.get("review_limit_reached"):
            if not latest_data or latest_data.get("decision") != "REVISE":
                errors.append("review-limit human gate requires latest GPT review decision REVISE")
            if current.get("review_round") != current.get("max_review_rounds"):
                errors.append("review-limit human gate requires review_round=max_review_rounds")
        if current.get("implementation_commit") and not latest_data and gate_reason != "PLANNER_DECISION":
            errors.append("implementation-backed human gate requires a GPT review artifact or explicit PLANNER_DECISION escalation")
    if state == "BLOCKED" and current.get("implementation_commit") and not latest_data and not current.get("runner_failure"):
        errors.append("implementation-backed BLOCKED state requires a GPT review artifact or runner_failure evidence")
    if state in TERMINAL_STATES:
        errors.extend(validate_final_report(result_root(target, task_key) / "FINAL_REPORT.md"))
    return errors


def validate_reviewed_handoff(target: Path) -> tuple[list[str], int]:
    target = target.resolve()
    status = inspect_reviewed_handoff(target)
    lines = [format_status(status)]
    errors: list[str] = []
    if status.missing:
        errors.extend(f"missing {item}" for item in status.missing)
    schema_path = reviewed_root(target) / "schema.json"
    if schema_path.exists():
        try:
            schema = load_json(schema_path)
            if schema.get("schema") != SCHEMA_NAME:
                errors.append("schema.json schema mismatch")
            if set(schema.get("task_states", [])) != TASK_STATES:
                errors.append("schema.json task_states drift")
            graph = {key: set(value) for key, value in schema.get("allowed_transitions", {}).items()}
            if graph != ALLOWED_TRANSITIONS:
                errors.append("schema.json allowed_transitions drift")
        except Exception as exc:
            errors.append(f"schema.json invalid: {exc}")
    tasks_dir = reviewed_root(target) / "tasks"
    if tasks_dir.exists():
        for path in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
            errors.extend(f"{path.name}: {item}" for item in validate_task(target, path.name))
    if errors:
        lines.extend(f"ERROR {item}" for item in errors)
        return lines, 1
    lines.append("Reviewed Handoff validation passed.")
    return lines, 0


def transition_allowed(source_state: str, next_state: str) -> bool:
    return next_state in ALLOWED_TRANSITIONS.get(source_state, set())


def plan_transition(target: Path, task_key: str) -> dict[str, Any]:
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    state = str(current.get("state"))
    errors = validate_task(target, task_key)
    if errors:
        return {"state": state, "valid": False, "errors": errors, "next_action": "REPAIR_WORKFLOW_ARTIFACTS"}
    root = task_root(target, task_key)
    result_dir = result_root(target, task_key)
    if state == "PLAN_REQUESTED":
        if (root / "PLAN.md").exists():
            return {"state": state, "valid": True, "next_state": "PLAN_FROZEN", "next_action": "FREEZE_GPT_PLAN"}
        return {"state": state, "valid": True, "next_action": "RUN_GPT_PLANNER"}
    if state == "PLAN_FROZEN":
        return {"state": state, "valid": True, "next_state": "EXECUTING", "next_action": "RUN_CODEX_EXECUTOR"}
    if state == "EXECUTING":
        if (result_dir / "RESULT.md").exists() and str(current.get("implementation_commit") or "").strip():
            if current.get("ci_required"):
                return {"state": state, "valid": True, "next_state": "WAITING_FOR_CI", "next_action": "PUBLISH_AND_WAIT_FOR_CI"}
            return {"state": state, "valid": True, "next_state": "READY_FOR_GPT_REVIEW", "next_action": "WAIT_SCHEDULED_GPT_REVIEW"}
        return {"state": state, "valid": True, "next_action": "CONTINUE_CODEX_EXECUTION"}
    if state == "WAITING_FOR_CI":
        ci_status = current.get("ci_status")
        if ci_status == "PASS":
            return {
                "state": state,
                "valid": True,
                "next_state": "READY_FOR_GPT_REVIEW",
                "next_action": "RUN_GPT_REVIEW",
                **reviewed_external_wait_status(target, task_key),
            }
        if ci_status == "FAIL":
            return {
                "state": state,
                "valid": True,
                "next_action": "RECORD_CI_FAILURE_REVIEW",
                **reviewed_external_wait_status(target, task_key),
            }
        return {"state": state, "valid": True, "next_action": "WAIT_FOR_CI"}
    if state == "NEEDS_GPT_PLANNER":
        if current.get("plan_revision", 0) >= current.get("max_plan_revisions", 1):
            return {"state": state, "valid": True, "next_state": "AWAIT_HUMAN_DECISION", "next_action": "HUMAN_PLAN_DECISION"}
        return {
            "state": state,
            "valid": True,
            "next_action": "WAIT_SCHEDULED_GPT_PLANNER",
            **reviewed_external_wait_status(target, task_key),
        }
    if state == "READY_FOR_GPT_REVIEW":
        visual_status = reviewed_visual_review_status(target, task_key, current)
        if visual_status.get("required") and visual_status.get("status") == "PENDING":
            return {
                "state": state,
                "valid": True,
                "next_action": "WAIT_FOR_VISUAL_REVIEW_EVIDENCE",
                "visual_review": visual_status,
            }
        return {
            "state": state,
            "valid": True,
            "next_action": "WAIT_SCHEDULED_GPT_REVIEW",
            **reviewed_external_wait_status(target, task_key),
        }
    if state == "REVISE":
        if current.get("review_round", 0) >= current.get("max_review_rounds", 2):
            return {"state": state, "valid": True, "next_state": "AWAIT_HUMAN_DECISION", "next_action": "HUMAN_REVIEW_DECISION"}
        return {"state": state, "valid": True, "next_state": "EXECUTING", "next_action": "RUN_CODEX_REPAIR"}
    if state == "PASS":
        if (result_dir / "FINAL_REPORT.md").exists():
            return {"state": state, "valid": True, "next_state": "AWAIT_HUMAN_DECISION", "next_action": "PRESENT_FINAL_REPORT"}
        return {"state": state, "valid": True, "next_action": "WRITE_FINAL_REPORT"}
    return {"state": state, "valid": True, "next_action": "NO_AUTOMATIC_TRANSITION"}


def apply_transition(
    target: Path,
    task_key: str,
    *,
    expected_state: str,
    next_state: str,
    next_action: str = "",
) -> dict[str, Any]:
    path = task_root(target, task_key) / "CURRENT.json"
    original = load_json(path)
    current = dict(original)
    if current.get("state") != expected_state:
        raise ValueError(f"transition expected {expected_state}, found {current.get('state')}")
    if not transition_allowed(expected_state, next_state):
        raise ValueError(f"illegal transition edge: {expected_state} -> {next_state}")
    errors = validate_task(target, task_key)
    if errors:
        raise ValueError("; ".join(errors))
    if next_state == "PLAN_FROZEN":
        plan_path = task_root(target, task_key) / "PLAN.md"
        if not plan_path.exists():
            raise ValueError("PLAN_FROZEN requires PLAN.md")
        plan_errors = validate_plan_file(plan_path, task_key)
        if plan_errors:
            raise ValueError("; ".join(plan_errors))
    if expected_state == "NEEDS_GPT_PLANNER" and next_state == "PLAN_FROZEN":
        if current.get("plan_revision", 0) >= current.get("max_plan_revisions", 1):
            raise ValueError("Reviewed Handoff allows only one scheduled GPT plan revision before human escalation")
        current["plan_revision"] = int(current.get("plan_revision", 0)) + 1
    if expected_state == "READY_FOR_GPT_REVIEW":
        raise ValueError("use reviewed-handoff review record for every READY_FOR_GPT_REVIEW exit so GPT review cannot be bypassed")
    if expected_state == "WAITING_FOR_CI" and next_state in {"REVISE", "BLOCKED"}:
        raise ValueError("use reviewed-handoff review record for CI failure decisions")
    if expected_state == "WAITING_FOR_CI" and next_state == "READY_FOR_GPT_REVIEW":
        current["ci_status"] = "PASS"
    if expected_state == "REVISE" and next_state == "EXECUTING":
        if current.get("review_round", 0) >= current.get("max_review_rounds", 2):
            raise ValueError("review round limit reached; route to AWAIT_HUMAN_DECISION")
    if expected_state == "EXECUTING" and next_state in {"WAITING_FOR_CI", "READY_FOR_GPT_REVIEW"}:
        result_path = result_root(target, task_key) / "RESULT.md"
        if not result_path.exists() or not str(current.get("implementation_commit") or "").strip():
            raise ValueError(f"{next_state} requires current RESULT.md and implementation_commit")
        result_errors = validate_result_file(result_path, task_key, current)
        if result_errors:
            raise ValueError("; ".join(result_errors))
        if git_repo_available(target):
            commit = str(current.get("implementation_commit") or "")
            if not git_commit_exists(target, commit):
                raise ValueError(f"{next_state} requires a real implementation_commit Git locator")
            base_commit = str(current.get("base_commit") or "")
            if git_commit_exists(target, base_commit) and not git_is_ancestor(target, base_commit, commit):
                raise ValueError(f"{next_state} implementation_commit must descend from base_commit")
        if current.get("ci_required"):
            if next_state != "WAITING_FOR_CI":
                raise ValueError("CI-required Executor work must enter WAITING_FOR_CI before GPT review")
            if current.get("ci_status") != "PENDING":
                raise ValueError("Executor must publish CI-required work with ci_status=PENDING")
        elif next_state != "READY_FOR_GPT_REVIEW":
            raise ValueError("CI-not-required Executor work should enter READY_FOR_GPT_REVIEW directly")
    if next_state in TERMINAL_STATES:
        report_errors = validate_final_report(result_root(target, task_key) / "FINAL_REPORT.md")
        if report_errors:
            raise ValueError("; ".join(report_errors))
    if next_state == "AWAIT_HUMAN_DECISION" and expected_state == "NEEDS_GPT_PLANNER":
        current["human_gate_reason"] = "PLANNER_DECISION"
    if next_state == "AWAIT_HUMAN_DECISION" and expected_state == "REVISE":
        if current.get("review_round", 0) < current.get("max_review_rounds", 2):
            raise ValueError("automatic review-limit human gate is only valid after max_review_rounds")
        current["review_limit_reached"] = True
        current["human_gate_reason"] = "REVIEW_LIMIT"
    if next_state == "AWAIT_HUMAN_DECISION" and expected_state == "PASS":
        current["human_gate_reason"] = "PASS"
    current["state"] = next_state
    if next_action:
        current["next_action"] = next_action
    write_json(path, current)
    post_errors = validate_task(target, task_key)
    if post_errors:
        write_json(path, original)
        raise ValueError("transition would create invalid Reviewed Handoff state: " + "; ".join(post_errors))
    return current


def record_review(
    target: Path,
    task_key: str,
    *,
    decision: str,
    body: str,
    implementation_commit: str | None = None,
) -> dict[str, Any]:
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"unsupported review decision: {decision}")
    root = task_root(target, task_key)
    current_path = root / "CURRENT.json"
    original = load_json(current_path)
    current = dict(original)
    source_state = current.get("state")
    if source_state not in {"READY_FOR_GPT_REVIEW", "WAITING_FOR_CI"}:
        raise ValueError("GPT review can only be recorded from READY_FOR_GPT_REVIEW or failed WAITING_FOR_CI")
    if source_state == "WAITING_FOR_CI":
        if decision == "PASS":
            raise ValueError("failed CI cannot be recorded as PASS")
        if decision == "REVISE":
            current["ci_status"] = "FAIL"
    errors = validate_task(target, task_key)
    if errors:
        raise ValueError("; ".join(errors))
    visual_status = reviewed_visual_review_status(target, task_key, current)
    if visual_status.get("required"):
        status = visual_status.get("status")
        if status == "PENDING":
            raise ValueError("visual review evidence pending; GPT review round must not be consumed")
        if status == "INVALID":
            raise ValueError("; ".join(str(item) for item in visual_status.get("errors", [])))
        if decision == "PASS" and status != "PASS":
            raise ValueError(f"GPT review PASS requires visual review PASS evidence, found {status}")
    next_round = int(current.get("review_round", 0)) + 1
    max_rounds = int(current.get("max_review_rounds", 2))
    if next_round > max_rounds:
        raise ValueError("review round limit reached")
    terminal_after_review = decision == "BLOCKED" or (decision == "REVISE" and next_round >= max_rounds)
    if terminal_after_review:
        report_errors = validate_final_report(result_root(target, task_key) / "FINAL_REPORT.md")
        if report_errors:
            raise ValueError("terminal review decision requires FINAL_REPORT.md before closing the automatic loop: " + "; ".join(report_errors))
    current_commit_locator = str(current.get("implementation_commit") or "")
    commit = implementation_commit or current_commit_locator
    if not commit:
        raise ValueError("review requires implementation_commit locator")
    if commit != current_commit_locator:
        raise ValueError("review implementation_commit must match CURRENT implementation_commit")
    review_path = result_root(target, task_key) / f"REVIEW_{next_round}.md"
    if review_path.exists():
        raise ValueError(f"review artifact already exists: {review_path.name}")
    header = (
        "---\n"
        f"schema: {REVIEW_SCHEMA}\n"
        f"task_key: {task_key}\n"
        f"review_round: {next_round}\n"
        f"decision: {decision}\n"
        f"implementation_commit: {commit}\n"
        "---\n\n"
    )
    write_text(review_path, header + body.rstrip() + "\n")
    current["review_round"] = next_round
    current["last_review_decision"] = decision
    if decision == "PASS":
        current["state"] = "PASS"
        current["next_action"] = "WRITE_FINAL_REPORT"
    elif decision == "BLOCKED":
        current["state"] = "BLOCKED"
        current["next_action"] = "PRESENT_FINAL_REPORT"
    elif next_round >= max_rounds:
        current["state"] = "AWAIT_HUMAN_DECISION"
        current["review_limit_reached"] = True
        current["human_gate_reason"] = "REVIEW_LIMIT"
        current["next_action"] = "PRESENT_FINAL_REPORT"
    else:
        current["state"] = "REVISE"
        current["next_action"] = "RUN_CODEX_REPAIR"
    write_json(current_path, current)
    post_errors = validate_task(target, task_key)
    if post_errors:
        write_json(current_path, original)
        review_path.unlink(missing_ok=True)
        raise ValueError("review would create invalid Reviewed Handoff state: " + "; ".join(post_errors))
    return current


def prompt_text(target: Path, name: str) -> str:
    mapping = {
        "planner": "PLANNER.md",
        "reviewer-scheduled-task": "REVIEWER_SCHEDULED_TASK.md",
        "codex": "CODEX_EXECUTOR.md",
    }
    return read_text(reviewed_root(target) / "prompts" / mapping[name])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge reviewed-handoff")
    sub = parser.add_subparsers(dest="command")
    for name in ["install", "status", "validate"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--target", type=Path, default=Path.cwd())
        if name == "install":
            cmd.add_argument("--force", action="store_true")
    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command")
    task_init = task_sub.add_parser("init")
    task_init.add_argument("--target", type=Path, default=Path.cwd())
    task_init.add_argument("--task-key", required=True)
    task_init.add_argument("--objective", default="")
    task_init.add_argument("--max-review-rounds", type=int, default=2)
    task_init.add_argument("--ci-required", action="store_true")
    task_init.add_argument("--visual-review-required", action="store_true")
    task_init.add_argument("--visual-review-manifest-path", default="")

    transition = sub.add_parser("transition")
    transition_sub = transition.add_subparsers(dest="transition_command")
    transition_plan = transition_sub.add_parser("plan")
    transition_plan.add_argument("--target", type=Path, default=Path.cwd())
    transition_plan.add_argument("--task-key", required=True)
    transition_apply = transition_sub.add_parser("apply")
    transition_apply.add_argument("--target", type=Path, default=Path.cwd())
    transition_apply.add_argument("--task-key", required=True)
    transition_apply.add_argument("--expected-state", required=True)
    transition_apply.add_argument("--next-state", required=True)
    transition_apply.add_argument("--next-action", default="")

    review = sub.add_parser("review")
    review_sub = review.add_subparsers(dest="review_command")
    review_record = review_sub.add_parser("record")
    review_record.add_argument("--target", type=Path, default=Path.cwd())
    review_record.add_argument("--task-key", required=True)
    review_record.add_argument("--decision", choices=sorted(REVIEW_DECISIONS), required=True)
    review_record.add_argument("--body", required=True)
    review_record.add_argument("--implementation-commit")

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--target", type=Path, default=Path.cwd())
    prompt.add_argument("name", choices=["planner", "reviewer-scheduled-task", "codex"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "install":
        status, actions = install_reviewed_handoff(args.target, force=args.force)
        for action in actions:
            print(action)
        print()
        print(format_status(status))
        return 0 if status.installed else 1
    if args.command == "status":
        print(format_status(inspect_reviewed_handoff(args.target)))
        return 0
    if args.command == "validate":
        lines, code = validate_reviewed_handoff(args.target)
        for line in lines:
            print(line)
        return code
    if args.command == "task" and args.task_command == "init":
        for action in init_task(
            args.target,
            args.task_key,
            objective=args.objective,
            max_review_rounds=args.max_review_rounds,
            ci_required=args.ci_required,
            visual_review_required=args.visual_review_required,
            visual_review_manifest_path=args.visual_review_manifest_path,
        ):
            print(action)
        return 0
    if args.command == "transition" and args.transition_command == "plan":
        print(json.dumps(plan_transition(args.target, args.task_key), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "transition" and args.transition_command == "apply":
        result = apply_transition(
            args.target,
            args.task_key,
            expected_state=args.expected_state,
            next_state=args.next_state,
            next_action=args.next_action,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "review" and args.review_command == "record":
        result = record_review(
            args.target,
            args.task_key,
            decision=args.decision,
            body=args.body,
            implementation_commit=args.implementation_commit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "prompt":
        print(prompt_text(args.target, args.name))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
