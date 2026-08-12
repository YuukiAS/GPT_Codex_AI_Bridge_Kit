from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AGENT_FLOW_REL = Path("automation") / "agent_flow"
RESULTS_REL = Path("results")
SCHEMA_VERSION = "ai-bridge.agent_flow.v1"

ROLES = {"Planner", "Critic", "Controller", "Verifier", "Executor"}
FINDING_CLASSES = {
    "IMPLEMENTATION_BUG",
    "VERIFIER_BUG",
    "VERIFIER_CONTRACT_DRIFT",
    "EVIDENCE_GAP",
    "PROVENANCE_BINDING_GAP",
    "OPERATIONAL_FAILURE",
    "RUNTIME_ENVIRONMENT_FAILURE",
    "CONTRACT_AMBIGUITY",
    "CONTRACT_CONTRADICTION",
    "DIAGNOSTIC_ANOMALY",
    "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
}
CHANGE_CLASSES = {
    "CONTRACT_CHANGED",
    "REQUIREMENT_LEDGER_CHANGED",
    "IMPLEMENTATION_SOURCE_CHANGED",
    "VERIFIER_SOURCE_CHANGED",
    "RUNTIME_ENVIRONMENT_CHANGED",
    "CI_WORKFLOW_CHANGED",
    "CONTROL_PLANE_ONLY_CHANGED",
    "RECEIPT_OR_MANIFEST_ONLY_CHANGED",
    "CURRENT_OR_ROUTING_ONLY_CHANGED",
    "DOC_ONLY_CHANGED",
    "NO_RELEVANT_CHANGE",
}
TASK_STATES = {
    "PLAN_REQUESTED",
    "PLAN_READY_FOR_CRITIC",
    "PLAN_FROZEN",
    "CONTROLLER_INITIALIZING",
    "VERIFIER_RUNNING",
    "VERIFIER_FROZEN",
    "EXECUTOR_RUNNING",
    "EVIDENCE_RUNNING",
    "CI_RUNNING",
    "READY_FOR_PLANNER_REVIEW",
    "WAITING_FOR_EXTERNAL_GPT",
    "PLANNER_REVISE_EXECUTOR",
    "PLANNER_REVISE_VERIFIER",
    "PLANNER_REVISE_BOTH",
    "PLANNER_PASS_CANDIDATE",
    "READY_FOR_CRITIC_FINAL_AUDIT",
    "CRITIC_FINAL_REVISE",
    "PLANNER_PASS",
    "AWAIT_HUMAN_DECISION",
    "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE",
    "BLOCKED_REQUIRED_SOURCE",
    "BLOCKED_ROLE_ISOLATION",
    "BLOCKED_CONTRACT_DRIFT",
    "BLOCKED_CI",
    "STOPPED_MAX_ROUNDS",
    "STOPPED_USER",
}
TERMINAL_NOTIFICATION_STATES = {
    "AWAIT_HUMAN_DECISION",
    "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE",
    "STOPPED_MAX_ROUNDS",
}


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload, pretty=True), encoding="utf-8")


def canonical_json(payload: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def git_output(target: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=target, text=True, stderr=subprocess.DEVNULL).strip()


def current_branch(target: Path) -> str:
    try:
        branch = git_output(target, ["rev-parse", "--abbrev-ref", "HEAD"])
        return branch if branch != "HEAD" else "DETACHED"
    except Exception:
        return "UNKNOWN"


def current_commit(target: Path) -> str:
    try:
        return git_output(target, ["rev-parse", "HEAD"])
    except Exception:
        return "UNKNOWN"


def changed_paths(target: Path, base: str, head: str) -> list[str]:
    output = git_output(target, ["diff", "--name-only", base, head])
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def state_home(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    return Path(source.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser() / "agent-flow"


def agent_root(target: Path) -> Path:
    return target / AGENT_FLOW_REL


def task_root(target: Path, task_key: str) -> Path:
    return agent_root(target) / "tasks" / task_key


def result_root(target: Path, task_key: str) -> Path:
    return target / RESULTS_REL / task_key


def default_profile(project_name: str) -> dict[str, Any]:
    return {
        "schema": "AI_BRIDGE_PROJECT_PROFILE_V1",
        "project": project_name,
        "risk_profile": "high-risk",
        "integration_branch": "",
        "requires_final_critic": True,
        "requires_ci": False,
        "semantic_paths": {
            "implementation": ["src/**", "app/**", "lib/**"],
            "verifier": ["tests/**", "test/**", "verifier/**"],
            "runtime_environment": ["requirements*.txt", "pyproject.toml", "package*.json", "Dockerfile"],
            "ci_workflow": [".github/workflows/**"],
            "control_plane": ["automation/agent_flow/**"],
            "receipts_or_manifests": ["results/**/receipts/**", "results/**/notification_brief.json"],
            "current_or_routing": ["automation/agent_flow/tasks/**/CURRENT.json"],
            "documentation": ["docs/**", "README.md", "CHANGELOG.md"],
        },
        "role_write_scopes": {
            "Planner": ["automation/agent_flow/tasks/**/PLANNER_DRAFT.md", "automation/agent_flow/tasks/**/planner_reviews/**"],
            "Critic": ["automation/agent_flow/tasks/**/critic_reviews/**", "automation/agent_flow/tasks/**/FROZEN_CONTRACT.md", "automation/agent_flow/tasks/**/REQUIREMENT_LEDGER.json"],
            "Controller": ["automation/agent_flow/tasks/**/CURRENT.json", "results/**/controller_report.md", "results/**/notification_brief.json"],
            "Verifier": ["tests/**", "verifier/**", "automation/agent_flow/tasks/**/VERIFIER_SOURCE_MANIFEST.json", "results/**/verification/**"],
            "Executor": ["src/**", "app/**", "lib/**", "results/**/implementation/**"],
        },
    }


def template_root() -> Path:
    return kit_root() / "templates" / "agent_flow"


def copy_template(src_rel: str, dst: Path, actions: list[str], *, force: bool = False) -> None:
    src = template_root() / src_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    if existed and not force:
        actions.append(f"SKIP existing file: {dst}")
        return
    shutil.copy2(src, dst)
    actions.append(f"COPY {'overwrite' if existed else 'create'}: {dst}")


def install_agent_flow(target: Path, *, force: bool = False) -> tuple[str, list[str]]:
    target = target.resolve()
    root = agent_root(target)
    actions: list[str] = []
    for directory in [
        root,
        root / "templates",
        root / "prompts",
        root / "tasks",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
        actions.append(f"DIR  {directory}")

    copy_template("README.md", root / "README.md", actions, force=force)
    copy_template("schema.json", root / "schema.json", actions, force=force)
    copy_template("ROLE_AUTHORITY_POLICY.md", root / "ROLE_AUTHORITY_POLICY.md", actions, force=force)
    for name in [
        "requirement_ledger.template.json",
        "implementation_source_manifest.template.json",
        "verifier_source_manifest.template.json",
        "source_snapshot.template.json",
        "review_bundle.template.json",
        "routing_policy.template.json",
    ]:
        copy_template(f"templates/{name}", root / "templates" / name, actions, force=force)
    for name in ["PLANNER.md", "CRITIC.md", "CONTROLLER.md", "VERIFIER.md", "EXECUTOR.md"]:
        copy_template(f"prompts/{name}", root / "prompts" / name, actions, force=force)

    profile_path = root / "PROJECT_PROFILE.json"
    existed = profile_path.exists()
    if existed and not force:
        actions.append(f"SKIP existing file: {profile_path}")
    else:
        write_json(profile_path, default_profile(target.name))
        actions.append(f"{'OVERWRITE' if existed else 'CREATE'} project profile: {profile_path}")

    return inspect_agent_flow(target).state, actions


@dataclass(frozen=True)
class AgentFlowStatus:
    target: Path
    state: str
    missing: list[str]
    task_count: int
    current_branch: str
    project_profile: str


def inspect_agent_flow(target: Path) -> AgentFlowStatus:
    target = target.resolve()
    root = agent_root(target)
    required = [
        root / "README.md",
        root / "schema.json",
        root / "ROLE_AUTHORITY_POLICY.md",
        root / "PROJECT_PROFILE.json",
        root / "templates" / "requirement_ledger.template.json",
        root / "prompts" / "PLANNER.md",
        root / "prompts" / "CRITIC.md",
        root / "prompts" / "CONTROLLER.md",
        root / "prompts" / "VERIFIER.md",
        root / "prompts" / "EXECUTOR.md",
    ]
    missing = [rel_path(path, target) for path in required if not path.exists()]
    profile = "missing"
    if (root / "PROJECT_PROFILE.json").exists():
        try:
            load_project_profile(target)
            profile = "valid"
        except Exception:
            profile = "invalid"
    task_count = len(list((root / "tasks").iterdir())) if (root / "tasks").is_dir() else 0
    state = "configured" if not missing and profile == "valid" else ("missing" if missing else "drifted")
    return AgentFlowStatus(target, state, missing, task_count, current_branch(target), profile)


def format_status(status: AgentFlowStatus) -> str:
    lines = [
        f"target: {status.target}",
        f"agent_flow: {status.state}",
        f"current_branch: {status.current_branch}",
        f"project_profile: {status.project_profile}",
        f"task_count: {status.task_count}",
    ]
    for item in status.missing:
        lines.append(f"missing: {item}")
    return "\n".join(lines)


def load_project_profile(target: Path) -> dict[str, Any]:
    profile = load_json(agent_root(target) / "PROJECT_PROFILE.json")
    if profile.get("schema") != "AI_BRIDGE_PROJECT_PROFILE_V1":
        raise ValueError("PROJECT_PROFILE.json schema must be AI_BRIDGE_PROJECT_PROFILE_V1")
    semantic_paths = profile.get("semantic_paths")
    if not isinstance(semantic_paths, dict):
        raise ValueError("PROJECT_PROFILE.json must contain semantic_paths")
    for key in ["implementation", "verifier", "control_plane"]:
        if not isinstance(semantic_paths.get(key), list):
            raise ValueError(f"semantic_paths.{key} must be a list")
    return profile


def init_task(
    target: Path,
    task_key: str,
    *,
    integration_branch: str | None = None,
    profile: str = "high-risk",
    max_repair_rounds: int = 5,
) -> list[str]:
    target = target.resolve()
    root = task_root(target, task_key)
    root.mkdir(parents=True, exist_ok=True)
    (result_root(target, task_key) / "receipts").mkdir(parents=True, exist_ok=True)
    branch = integration_branch or current_branch(target)
    nonce = str(uuid.uuid4())
    request_path = root / "REQUEST.json"
    current_path = root / "CURRENT.json"
    actions: list[str] = []
    if not request_path.exists():
        write_json(
            request_path,
            {
                "schema": "AI_BRIDGE_AGENT_FLOW_REQUEST_V1",
                "task_key": task_key,
                "request_nonce": nonce,
                "profile": profile,
                "integration_branch": branch,
                "max_repair_rounds": max_repair_rounds,
                "status": "PLAN_REQUESTED",
                "contract_frozen": False,
            },
        )
        actions.append(f"CREATE {request_path}")
    else:
        actions.append(f"SKIP existing file: {request_path}")
        nonce = str(load_json(request_path).get("request_nonce") or nonce)
    if not current_path.exists():
        write_json(
            current_path,
            {
                "schema": "AI_BRIDGE_AGENT_FLOW_CURRENT_V1",
                "task_key": task_key,
                "request_nonce": nonce,
                "state": "PLAN_REQUESTED",
                "integration_branch": branch,
                "current_review_target_id": None,
                "frozen_contract_sha256": None,
                "requirement_ledger_sha256": None,
                "implementation_semantic_digest_sha256": None,
                "verifier_semantic_digest_sha256": None,
                "critic_mode": "REQUIRED_INITIAL",
                "planner_decision": None,
                "final_critic_decision": None,
                "open_findings": [],
                "heavy_verifier_runs": [],
                "last_change_class": None,
                "next_action": "RUN_PLANNER_INITIAL",
            },
        )
        actions.append(f"CREATE {current_path}")
    else:
        actions.append(f"SKIP existing file: {current_path}")
    return actions


def all_repo_files(target: Path) -> list[Path]:
    ignored_parts = {".git", "__pycache__", ".ai-bridge"}
    files: list[Path] = []
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(target)
        if any(part in ignored_parts for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def semantic_candidate_files(target: Path) -> list[Path]:
    try:
        output = git_output(target, ["ls-files"])
    except Exception:
        return all_repo_files(target)
    files: list[Path] = []
    for line in output.splitlines():
        path = target / line.strip()
        if path.is_file():
            files.append(path)
    return sorted(files)


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def source_manifest(target: Path, task_key: str, profile: dict[str, Any], group: str) -> dict[str, Any]:
    patterns = profile["semantic_paths"].get(group, [])
    paths = []
    for path in semantic_candidate_files(target):
        rel = rel_path(path, target)
        if matches_any(rel, patterns):
            paths.append({"path": rel, "sha256": file_sha256(path)})
    paths = sorted(paths, key=lambda item: item["path"])
    digest_payload = {"group": group, "paths": paths}
    schema = (
        "AI_BRIDGE_IMPLEMENTATION_SOURCE_MANIFEST_V1"
        if group == "implementation"
        else "AI_BRIDGE_VERIFIER_SOURCE_MANIFEST_V1"
    )
    return {
        "schema": schema,
        "task_key": task_key,
        "paths": paths,
        "semantic_digest_sha256": sha256_text(canonical_json(digest_payload)),
    }


def compute_review_target_id(
    *,
    task_identity: dict[str, Any],
    frozen_contract_sha256: str,
    requirement_ledger_sha256: str,
    implementation_semantic_digest_sha256: str,
    verifier_semantic_digest_sha256: str,
) -> str:
    return sha256_text(
        canonical_json(
            {
                "task_identity": task_identity,
                "frozen_contract_sha256": frozen_contract_sha256,
                "requirement_ledger_sha256": requirement_ledger_sha256,
                "implementation_semantic_digest_sha256": implementation_semantic_digest_sha256,
                "verifier_semantic_digest_sha256": verifier_semantic_digest_sha256,
            }
        )
    )


def snapshot(target: Path, task_key: str) -> dict[str, Any]:
    target = target.resolve()
    profile = load_project_profile(target)
    root = task_root(target, task_key)
    request = load_json(root / "REQUEST.json")
    contract_path = root / "FROZEN_CONTRACT.md"
    ledger_path = root / "REQUIREMENT_LEDGER.json"
    if not contract_path.exists():
        raise ValueError("FROZEN_CONTRACT.md is required before snapshot")
    if not ledger_path.exists():
        raise ValueError("REQUIREMENT_LEDGER.json is required before snapshot")
    validate_requirement_ledger(load_json(ledger_path))
    contract_digest = file_sha256(contract_path)
    ledger_digest = file_sha256(ledger_path)
    implementation = source_manifest(target, task_key, profile, "implementation")
    verifier = source_manifest(target, task_key, profile, "verifier")
    write_json(root / "IMPLEMENTATION_SOURCE_MANIFEST.json", implementation)
    write_json(root / "VERIFIER_SOURCE_MANIFEST.json", verifier)
    task_identity = {
        "task_key": task_key,
        "request_nonce": request.get("request_nonce"),
        "profile": request.get("profile"),
    }
    review_target_id = compute_review_target_id(
        task_identity=task_identity,
        frozen_contract_sha256=contract_digest,
        requirement_ledger_sha256=ledger_digest,
        implementation_semantic_digest_sha256=implementation["semantic_digest_sha256"],
        verifier_semantic_digest_sha256=verifier["semantic_digest_sha256"],
    )
    source_snapshot = {
        "schema": "AI_BRIDGE_SOURCE_SNAPSHOT_V1",
        "task_key": task_key,
        "task_identity": task_identity,
        "frozen_contract_sha256": contract_digest,
        "requirement_ledger_sha256": ledger_digest,
        "implementation_semantic_digest_sha256": implementation["semantic_digest_sha256"],
        "verifier_semantic_digest_sha256": verifier["semantic_digest_sha256"],
        "review_target_id": review_target_id,
        "git_locator": {
            "commit": current_commit(target),
            "branch": current_branch(target),
        },
    }
    write_json(root / "SOURCE_SNAPSHOT.json", source_snapshot)
    return source_snapshot


def validate_requirement_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = ledger.get("requirements")
    if not isinstance(entries, list) or not entries:
        return ["REQUIREMENT_LEDGER.json must contain non-empty requirements list"]
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"requirements[{index}] must be an object")
            continue
        req_id = entry.get("requirement_id")
        if not req_id:
            errors.append(f"requirements[{index}] missing requirement_id")
        elif req_id in seen:
            errors.append(f"duplicate requirement_id: {req_id}")
        seen.add(str(req_id))
        for key in ["source", "type", "blocking", "owner_role", "verifier_authority", "change_requires_contract_review"]:
            if key not in entry:
                errors.append(f"{req_id or index} missing {key}")
        threshold = entry.get("threshold")
        provenance = entry.get("threshold_provenance")
        if threshold is not None and provenance not in {"frozen_contract", "requirement_ledger", "mechanically_derived_invariant"}:
            errors.append(f"{req_id or index} threshold has invalid provenance: {provenance}")
    if errors:
        raise ValueError("; ".join(errors))
    return []


def classify_paths(paths: list[str], profile: dict[str, Any]) -> str:
    if not paths:
        return "NO_RELEVANT_CHANGE"
    semantic = profile["semantic_paths"]
    classes: list[str] = []
    for path in paths:
        if path.endswith("FROZEN_CONTRACT.md"):
            classes.append("CONTRACT_CHANGED")
        elif path.endswith("REQUIREMENT_LEDGER.json"):
            classes.append("REQUIREMENT_LEDGER_CHANGED")
        elif matches_any(path, semantic.get("implementation", [])):
            classes.append("IMPLEMENTATION_SOURCE_CHANGED")
        elif matches_any(path, semantic.get("verifier", [])):
            classes.append("VERIFIER_SOURCE_CHANGED")
        elif matches_any(path, semantic.get("runtime_environment", [])):
            classes.append("RUNTIME_ENVIRONMENT_CHANGED")
        elif matches_any(path, semantic.get("ci_workflow", [])):
            classes.append("CI_WORKFLOW_CHANGED")
        elif matches_any(path, semantic.get("current_or_routing", [])):
            classes.append("CURRENT_OR_ROUTING_ONLY_CHANGED")
        elif matches_any(path, semantic.get("control_plane", [])):
            classes.append("CONTROL_PLANE_ONLY_CHANGED")
        elif matches_any(path, semantic.get("receipts_or_manifests", [])):
            classes.append("RECEIPT_OR_MANIFEST_ONLY_CHANGED")
        elif matches_any(path, semantic.get("documentation", [])):
            classes.append("DOC_ONLY_CHANGED")
    if not classes:
        return "NO_RELEVANT_CHANGE"
    priority = [
        "CONTRACT_CHANGED",
        "REQUIREMENT_LEDGER_CHANGED",
        "IMPLEMENTATION_SOURCE_CHANGED",
        "VERIFIER_SOURCE_CHANGED",
        "RUNTIME_ENVIRONMENT_CHANGED",
        "CI_WORKFLOW_CHANGED",
        "CONTROL_PLANE_ONLY_CHANGED",
        "RECEIPT_OR_MANIFEST_ONLY_CHANGED",
        "CURRENT_OR_ROUTING_ONLY_CHANGED",
        "DOC_ONLY_CHANGED",
    ]
    return next(item for item in priority if item in classes)


def invalidation_plan(change_class: str, *, review_target_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
    plan = {
        "change_class": change_class,
        "new_semantic_target_required": False,
        "heavy_verifier_required": False,
        "executor_restart": False,
        "verifier_restart": False,
        "runtime_probe_required": False,
        "ci_required": False,
        "lightweight_validation_only": False,
        "review_target_id": review_target_id,
        "semantic_invalidation_reason": reason,
    }
    if change_class == "CONTRACT_CHANGED":
        plan.update(new_semantic_target_required=True, heavy_verifier_required=True, verifier_restart=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "REQUIREMENT_LEDGER_CHANGED":
        plan.update(new_semantic_target_required=True, heavy_verifier_required=True, verifier_restart=True, runtime_probe_required=True)
    elif change_class == "IMPLEMENTATION_SOURCE_CHANGED":
        plan.update(heavy_verifier_required=True, executor_restart=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "VERIFIER_SOURCE_CHANGED":
        plan.update(heavy_verifier_required=True, verifier_restart=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "RUNTIME_ENVIRONMENT_CHANGED":
        plan.update(runtime_probe_required=True)
    elif change_class == "CI_WORKFLOW_CHANGED":
        plan.update(ci_required=True)
    elif change_class in {"CONTROL_PLANE_ONLY_CHANGED", "RECEIPT_OR_MANIFEST_ONLY_CHANGED", "CURRENT_OR_ROUTING_ONLY_CHANGED"}:
        plan.update(lightweight_validation_only=True)
    return plan


def assert_heavy_verifier_reason(current: dict[str, Any], review_target_id: str, reason: str | None) -> None:
    runs = current.get("heavy_verifier_runs")
    if not isinstance(runs, list):
        return
    if any(run.get("review_target_id") == review_target_id for run in runs if isinstance(run, dict)) and not reason:
        raise ValueError("second heavy verifier run for same review_target_id requires semantic invalidation reason")


def route_findings(findings: list[dict[str, Any]], *, controller_originated: bool = False) -> dict[str, Any]:
    blocking = [item for item in findings if item.get("blocking")]
    if not blocking:
        return {"route": "READY_FOR_PLANNER_REVIEW", "target_role": "Planner"}
    finding = blocking[0]
    classification = finding.get("classification")
    if classification not in FINDING_CLASSES:
        raise ValueError(f"unsupported finding classification: {classification}")
    if classification == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED" and (
        controller_originated or not finding.get("planner_classified")
    ):
        raise ValueError("Controller cannot route a user scientific/product choice without Planner classification")
    routes = {
        "IMPLEMENTATION_BUG": ("REPAIR_EXECUTOR", "Executor"),
        "VERIFIER_BUG": ("REPAIR_VERIFIER", "Verifier"),
        "VERIFIER_CONTRACT_DRIFT": ("PLANNER_ADJUDICATE_VERIFIER_DRIFT", "Planner"),
        "EVIDENCE_GAP": ("REPAIR_OWNING_ROLE", finding.get("target_role") or finding.get("owner_role") or "Controller"),
        "PROVENANCE_BINDING_GAP": ("CONTROLLER_REPAIR_PROVENANCE", "Controller"),
        "OPERATIONAL_FAILURE": ("CONTROLLER_SAME_SCOPE_RECOVERY", "Controller"),
        "RUNTIME_ENVIRONMENT_FAILURE": ("RUNTIME_ADAPTER_RECOVERY", "Controller"),
        "CONTRACT_AMBIGUITY": ("PLANNER_INTERPRET_CONTRACT", "Planner"),
        "CONTRACT_CONTRADICTION": ("PLANNER_TO_CRITIC_CONTRACT_REVIEW", "Planner"),
        "DIAGNOSTIC_ANOMALY": ("PLANNER_DIAGNOSTIC_REVIEW", "Planner"),
        "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED": ("ASK_USER", "User"),
    }
    route, role = routes[classification]
    return {"route": route, "target_role": role, "finding_id": finding.get("finding_id")}


def normalize_adapter_result(
    *,
    adapter_name: str,
    evidence: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_findings = findings or []
    for finding in normalized_findings:
        classification = finding.get("classification")
        if classification not in FINDING_CLASSES:
            raise ValueError(f"adapter produced unsupported finding classification: {classification}")
        if classification == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED" and not finding.get("planner_classified"):
            raise ValueError("project adapter cannot independently create a user scientific/product choice")
    return {
        "schema": "AI_BRIDGE_PROJECT_ADAPTER_RESULT_V1",
        "adapter_name": adapter_name,
        "evidence": evidence or [],
        "findings": normalized_findings,
    }


def validate_role_receipt(receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    role = receipt.get("role")
    if role not in ROLES:
        errors.append(f"invalid role: {role}")
    if receipt.get("resume_strategy") == "last" or receipt.get("used_resume_last"):
        errors.append("production role binding must use exact session/thread id, not resume --last")
    if role in {"Controller", "Verifier", "Executor"} and not (
        receipt.get("session_id") or receipt.get("thread_id")
    ):
        errors.append(f"{role} receipt requires exact session_id or thread_id")
    for key in ["runtime_adapter", "allowed_write_scope", "start_or_resume_status"]:
        if key not in receipt:
            errors.append(f"role receipt missing {key}")
    return errors


def validate_executor_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if result.get("test_aware_alternate_path") or result.get("synthetic_fake_effect"):
        errors.append("Executor result uses a forbidden test-aware or synthetic path")
    touched = result.get("touched_paths", [])
    forbidden_patterns = [
        "automation/agent_flow/tasks/*/FROZEN_CONTRACT.md",
        "automation/agent_flow/tasks/*/REQUIREMENT_LEDGER.json",
        "automation/agent_flow/tasks/*/VERIFIER_SOURCE_MANIFEST.json",
        "automation/agent_flow/tasks/*/FINAL_CRITIC_AUDIT.json",
        "tests/**",
        "verifier/**",
    ]
    for path in touched if isinstance(touched, list) else []:
        if matches_any(str(path), forbidden_patterns):
            errors.append(f"Executor touched forbidden authority path: {path}")
    return errors


def validate_finding(finding: dict[str, Any], ledger_ids: set[str]) -> list[str]:
    errors: list[str] = []
    classification = finding.get("classification")
    if classification not in FINDING_CLASSES:
        errors.append(f"invalid finding classification: {classification}")
    if finding.get("blocking"):
        req_ids = finding.get("requirement_ids")
        if classification != "DIAGNOSTIC_ANOMALY" and (not isinstance(req_ids, list) or not req_ids):
            errors.append("blocking finding must cite requirement_ids")
        for req_id in req_ids if isinstance(req_ids, list) else []:
            if req_id not in ledger_ids:
                errors.append(f"blocking finding cites unknown requirement_id: {req_id}")
        threshold = finding.get("threshold")
        if threshold is not None and finding.get("threshold_provenance") not in {
            "frozen_contract",
            "requirement_ledger",
            "mechanically_derived_invariant",
        }:
            errors.append("Verifier cannot create uncited blocking threshold")
    return errors


def validate_review_bundle(target: Path, task_key: str) -> tuple[dict[str, Any], list[str]]:
    bundle_path = result_root(target, task_key) / "REVIEW_BUNDLE.json"
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    bundle = load_json(bundle_path)
    snapshot_payload = load_json(snapshot_path)
    errors: list[str] = []
    for key in [
        "schema",
        "task_key",
        "review_target_id",
        "frozen_contract_sha256",
        "requirement_ledger_sha256",
        "implementation_semantic_digest_sha256",
        "verifier_semantic_digest_sha256",
        "required_evidence",
        "open_findings",
    ]:
        if key not in bundle:
            errors.append(f"REVIEW_BUNDLE.json missing {key}")
    for key in [
        "review_target_id",
        "frozen_contract_sha256",
        "requirement_ledger_sha256",
        "implementation_semantic_digest_sha256",
        "verifier_semantic_digest_sha256",
    ]:
        if bundle.get(key) != snapshot_payload.get(key):
            errors.append(f"REVIEW_BUNDLE.json {key} does not match SOURCE_SNAPSHOT.json")
    if "historical_runtime_manifest" in bundle or "all_historical_receipts" in bundle:
        errors.append("REVIEW_BUNDLE.json must not include giant historical runtime manifests")
    for evidence in bundle.get("required_evidence", []) if isinstance(bundle.get("required_evidence"), list) else []:
        if isinstance(evidence, dict) and evidence.get("target_sensitive") and evidence.get("review_target_id") != bundle.get("review_target_id"):
            errors.append("target-sensitive evidence is bound to a different review_target_id")
    if errors:
        raise ValueError("; ".join(errors))
    return bundle, []


def validate_task_state(target: Path, task_key: str) -> list[str]:
    root = task_root(target, task_key)
    current = load_json(root / "CURRENT.json")
    state = current.get("state")
    errors: list[str] = []
    if state not in TASK_STATES:
        errors.append(f"invalid state: {state}")
    if state == "PLAN_READY_FOR_CRITIC" and not (root / "PLANNER_DRAFT.md").exists():
        errors.append("PLAN_READY_FOR_CRITIC requires PLANNER_DRAFT.md")
    if state == "PLAN_FROZEN":
        if not (root / "FROZEN_CONTRACT.md").exists():
            errors.append("PLAN_FROZEN requires FROZEN_CONTRACT.md")
        if not (root / "REQUIREMENT_LEDGER.json").exists():
            errors.append("PLAN_FROZEN requires REQUIREMENT_LEDGER.json")
    if state == "VERIFIER_FROZEN":
        receipt = root / "VERIFIER_FREEZE.json"
        manifest = root / "VERIFIER_SOURCE_MANIFEST.json"
        if not receipt.exists() or not manifest.exists():
            errors.append("VERIFIER_FROZEN requires verifier manifest and verifier-owned freeze receipt")
        else:
            receipt_json = load_json(receipt)
            manifest_json = load_json(manifest)
            if receipt_json.get("verifier_semantic_digest_sha256") != manifest_json.get("semantic_digest_sha256"):
                errors.append("VERIFIER_FROZEN receipt digest does not match verifier source manifest")
            if not receipt_json.get("verifier_evidence_id"):
                errors.append("VERIFIER_FROZEN requires verifier_evidence_id")
    if state in {"PLANNER_PASS", "AWAIT_HUMAN_DECISION"}:
        final = root / "FINAL_CRITIC_AUDIT.json"
        if not final.exists():
            errors.append(f"{state} requires FINAL_CRITIC_AUDIT.json")
        else:
            final_json = load_json(final)
            if final_json.get("decision") != "CRITIC_FINAL_PASS":
                errors.append(f"{state} requires CRITIC_FINAL_PASS")
            if final_json.get("touched_paths"):
                errors.append("Final Critic has no implementation/verifier write authority")
    return errors


def validate_agent_flow(target: Path) -> tuple[list[str], int]:
    status = inspect_agent_flow(target)
    lines = [format_status(status)]
    errors: list[str] = []
    if status.missing:
        errors.extend(f"missing {item}" for item in status.missing)
    try:
        profile = load_project_profile(target)
    except Exception as exc:
        errors.append(str(exc))
        profile = {}
    profile_text = canonical_json(profile) if profile else ""
    forbidden = ["CARE", "MyoPS", "nnU-Net", "Slurm", "develop"]
    for token in forbidden:
        if token in profile_text and token != profile.get("integration_branch"):
            errors.append(f"generic Project Profile must not require CARE-specific token: {token}")
    tasks_dir = agent_root(target) / "tasks"
    if tasks_dir.exists():
        for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
            task_key = task_dir.name
            for required in ["REQUEST.json", "CURRENT.json"]:
                if not (task_dir / required).exists():
                    errors.append(f"{task_key} missing {required}")
            if (task_dir / "REQUIREMENT_LEDGER.json").exists():
                try:
                    ledger = load_json(task_dir / "REQUIREMENT_LEDGER.json")
                    validate_requirement_ledger(ledger)
                    ledger_ids = {str(item.get("requirement_id")) for item in ledger.get("requirements", []) if isinstance(item, dict)}
                    findings_path = result_root(target, task_key) / "open_findings.json"
                    if findings_path.exists():
                        for finding in load_json(findings_path).get("findings", []):
                            errors.extend(validate_finding(finding, ledger_ids))
                except Exception as exc:
                    errors.append(f"{task_key}: {exc}")
            if (task_dir / "CURRENT.json").exists():
                errors.extend(f"{task_key}: {item}" for item in validate_task_state(target, task_key))
            if (result_root(target, task_key) / "REVIEW_BUNDLE.json").exists():
                try:
                    validate_review_bundle(target, task_key)
                except Exception as exc:
                    errors.append(f"{task_key}: {exc}")
    if errors:
        lines.extend(f"ERROR {item}" for item in errors)
        return lines, 1
    lines.append("Agent-Flow validation passed.")
    return lines, 0


def role_prompt(target: Path, role: str) -> str:
    normalized = role.upper()
    if normalized.title() not in ROLES and normalized not in {item.upper() for item in ROLES}:
        raise ValueError(f"unknown role: {role}")
    path = agent_root(target) / "prompts" / f"{normalized}.md"
    return read_text(path)


def worktree_plan(target: Path, role: str, base_ref: str = "HEAD") -> dict[str, Any]:
    role = role.capitalize()
    if role not in {"Verifier", "Executor"}:
        raise ValueError("detached worktree plan is only for Verifier/Executor isolation")
    return {
        "role": role,
        "branch_created": False,
        "command": ["git", "worktree", "add", "--detach", f"<state-home>/{target.name}/{role.lower()}", base_ref],
        "policy": "detached worktree; explicit user authorization required before creating role branches",
    }


def terminal_notification_brief(target: Path, task_key: str) -> dict[str, Any] | None:
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    state = current.get("state")
    if state not in TERMINAL_NOTIFICATION_STATES:
        return None
    status = "awaiting_human" if state == "AWAIT_HUMAN_DECISION" else "blocked"
    return {
        "schema": "ai-bridge.notification_brief.v1",
        "project": target.name,
        "task_key": task_key,
        "terminal_status": status,
        "key_conclusion": f"Agent-Flow reached {state}.",
        "next_step": "Review the current Review Bundle and decide the next human action.",
        "evidence_paths": [str((result_root(target, task_key) / "REVIEW_BUNDLE.json").as_posix())],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge agent-flow")
    sub = parser.add_subparsers(dest="command")
    for name in ["install", "status", "validate"]:
        command = sub.add_parser(name)
        command.add_argument("--target", type=Path, default=Path.cwd())
        if name == "install":
            command.add_argument("--force", action="store_true")
    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command")
    task_init = task_sub.add_parser("init")
    task_init.add_argument("--target", type=Path, default=Path.cwd())
    task_init.add_argument("--task-key", required=True)
    task_init.add_argument("--integration-branch")
    task_init.add_argument("--max-repair-rounds", type=int, default=5)
    task_init.add_argument("--profile", default="high-risk")

    snapshot_parser = sub.add_parser("snapshot")
    snapshot_parser.add_argument("--target", type=Path, default=Path.cwd())
    snapshot_parser.add_argument("--task-key", required=True)

    bundle = sub.add_parser("bundle")
    bundle_sub = bundle.add_subparsers(dest="bundle_command")
    bundle_validate = bundle_sub.add_parser("validate")
    bundle_validate.add_argument("--target", type=Path, default=Path.cwd())
    bundle_validate.add_argument("--task-key", required=True)

    classify = sub.add_parser("classify-change")
    classify.add_argument("--target", type=Path, default=Path.cwd())
    classify.add_argument("--task-key")
    classify.add_argument("--base")
    classify.add_argument("--head")
    classify.add_argument("--path", action="append", default=[])

    route = sub.add_parser("route")
    route.add_argument("--target", type=Path, default=Path.cwd())
    route.add_argument("--task-key", required=True)

    prompt = sub.add_parser("prompt")
    prompt.add_argument("--target", type=Path, default=Path.cwd())
    prompt.add_argument("role", choices=sorted(role.lower() for role in ROLES))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "install":
        state, actions = install_agent_flow(args.target, force=args.force)
        for action in actions:
            print(action)
        print()
        print(format_status(inspect_agent_flow(args.target)))
        return 0 if state == "configured" else 1
    if args.command == "status":
        print(format_status(inspect_agent_flow(args.target)))
        return 0
    if args.command == "validate":
        lines, code = validate_agent_flow(args.target)
        for line in lines:
            print(line)
        return code
    if args.command == "task" and args.task_command == "init":
        for action in init_task(
            args.target,
            args.task_key,
            integration_branch=args.integration_branch,
            profile=args.profile,
            max_repair_rounds=args.max_repair_rounds,
        ):
            print(action)
        return 0
    if args.command == "snapshot":
        print(canonical_json(snapshot(args.target, args.task_key), pretty=True), end="")
        return 0
    if args.command == "bundle" and args.bundle_command == "validate":
        _, errors = validate_review_bundle(args.target, args.task_key)
        for error in errors:
            print(error)
        print("Review Bundle validation passed.")
        return 0
    if args.command == "classify-change":
        profile = load_project_profile(args.target)
        paths = list(args.path)
        if args.base and args.head:
            paths.extend(changed_paths(args.target, args.base, args.head))
        change_class = classify_paths(sorted(set(paths)), profile)
        print(canonical_json({"change_class": change_class, "invalidation": invalidation_plan(change_class)}, pretty=True), end="")
        return 0
    if args.command == "route":
        current = load_json(task_root(args.target, args.task_key) / "CURRENT.json")
        result = route_findings(current.get("open_findings", []))
        print(canonical_json(result, pretty=True), end="")
        return 0
    if args.command == "prompt":
        print(role_prompt(args.target, args.role))
        return 0
    parser.print_help()
    return 0
