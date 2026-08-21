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

from . import external_wait
from . import visual_review


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
    "POTENTIAL_SCIENTIFIC_OR_PRODUCT_CHOICE",
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
    "CONTRACT_REVIEW_REQUIRED",
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
EXTERNAL_WAIT_STATE_OWNERS = {
    "PLAN_REQUESTED": "Planner",
    "PLAN_READY_FOR_CRITIC": "Critic",
    "READY_FOR_PLANNER_REVIEW": "Planner",
    "WAITING_FOR_EXTERNAL_GPT": "Planner",
    "CONTRACT_REVIEW_REQUIRED": "Critic",
    "READY_FOR_CRITIC_FINAL_AUDIT": "Final Critic",
    "CRITIC_FINAL_REVISE": "Planner",
}
CRITIC_MODES = {"REQUIRED_INITIAL", "STANDBY", "REQUIRED_CONTRACT_REVIEW", "REQUIRED_FINAL_AUDIT", "COMPLETE"}
ALLOWED_TRANSITIONS = {
    "PLAN_REQUESTED": {"PLAN_READY_FOR_CRITIC"},
    "PLAN_READY_FOR_CRITIC": {"PLAN_FROZEN", "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE", "BLOCKED_REQUIRED_SOURCE"},
    "PLAN_FROZEN": {"CONTROLLER_INITIALIZING"},
    "CONTROLLER_INITIALIZING": {"VERIFIER_RUNNING"},
    "VERIFIER_RUNNING": {"VERIFIER_FROZEN", "BLOCKED_ROLE_ISOLATION", "STOPPED_MAX_ROUNDS"},
    "VERIFIER_FROZEN": {"EXECUTOR_RUNNING"},
    "EXECUTOR_RUNNING": {"EVIDENCE_RUNNING", "PLANNER_REVISE_EXECUTOR", "BLOCKED_ROLE_ISOLATION", "STOPPED_MAX_ROUNDS"},
    "EVIDENCE_RUNNING": {"CI_RUNNING", "READY_FOR_PLANNER_REVIEW"},
    "CI_RUNNING": {"READY_FOR_PLANNER_REVIEW", "BLOCKED_CI"},
    "READY_FOR_PLANNER_REVIEW": {"WAITING_FOR_EXTERNAL_GPT"},
    "WAITING_FOR_EXTERNAL_GPT": {
        "PLANNER_REVISE_EXECUTOR",
        "PLANNER_REVISE_VERIFIER",
        "PLANNER_REVISE_BOTH",
        "CONTRACT_REVIEW_REQUIRED",
        "PLANNER_PASS_CANDIDATE",
        "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE",
    },
    "CONTRACT_REVIEW_REQUIRED": {"PLANNER_REVISE_BOTH", "BLOCKED_CONTRACT_DRIFT"},
    "PLANNER_REVISE_EXECUTOR": {"EXECUTOR_RUNNING"},
    "PLANNER_REVISE_VERIFIER": {"VERIFIER_RUNNING"},
    "PLANNER_REVISE_BOTH": {"VERIFIER_RUNNING", "EXECUTOR_RUNNING"},
    "PLANNER_PASS_CANDIDATE": {"READY_FOR_CRITIC_FINAL_AUDIT"},
    "READY_FOR_CRITIC_FINAL_AUDIT": {"PLANNER_PASS", "CRITIC_FINAL_REVISE"},
    "CRITIC_FINAL_REVISE": {"WAITING_FOR_EXTERNAL_GPT", "PLANNER_REVISE_EXECUTOR", "PLANNER_REVISE_VERIFIER", "PLANNER_REVISE_BOTH"},
    "PLANNER_PASS": {"AWAIT_HUMAN_DECISION"},
    "AWAIT_HUMAN_DECISION": set(),
    "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE": set(),
    "BLOCKED_REQUIRED_SOURCE": set(),
    "BLOCKED_ROLE_ISOLATION": set(),
    "BLOCKED_CONTRACT_DRIFT": set(),
    "BLOCKED_CI": set(),
    "STOPPED_MAX_ROUNDS": set(),
    "STOPPED_USER": set(),
}
REQUIRED_FINAL_CRITIC_CHECKS = {
    "contract_not_silently_weakened",
    "requirement_ledger_not_expanded_by_runtime_roles",
    "planner_blocking_requirements_closed",
    "verifier_no_uncited_blocking_requirement_or_threshold",
    "executor_no_test_aware_alternate_behavior",
    "review_bundle_bound_to_current_target",
    "required_evidence_passed",
    "ci_passed_when_required",
    "no_unresolved_contract_ambiguity_or_contradiction",
}
EVIDENCE_SUCCESS_STATUSES = {
    "unit_test": {"PASS", "passed", "success"},
    "runtime_probe": {"PASS", "passed", "success"},
    "ci": {"PASS", "passed", "success"},
    "review": {"PASS", "passed", "success"},
    "visual_review": {"PASS"},
    "artifact": {"PRESENT", "PASS", "success"},
}
CHANGE_CLASS_PRIORITY = [
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
]
HEAVY_VERIFIER_REASONS = {
    "CONTRACT_CHANGED",
    "REQUIREMENT_LEDGER_CHANGED",
    "IMPLEMENTATION_SOURCE_CHANGED",
    "VERIFIER_SOURCE_CHANGED",
}
PROFILE_REQUIRED_FIELDS = {
    "schema": str,
    "project": str,
    "project_objective": str,
    "repository_truth_sources": list,
    "artifact_language_policy": str,
    "contract_source_policy": dict,
    "implementation_semantic_paths": list,
    "verifier_semantic_paths": list,
    "runtime_adapter": dict,
    "ci": dict,
    "external_boundaries": dict,
    "expensive_operation_policy": dict,
    "human_decision_boundary": str,
    "notification_policy": dict,
    "integration_branch_policy": dict,
    "role_isolation_policy": dict,
    "semantic_paths": dict,
    "role_write_scopes": dict,
    "optional_visual_source_policy": dict,
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


def payload_digest(payload: dict[str, Any], *, omit: set[str] | None = None) -> str:
    omit = set() if omit is None else omit
    return sha256_text(canonical_json({key: value for key, value in payload.items() if key not in omit}))


def bundle_digest(bundle: dict[str, Any]) -> str:
    return payload_digest(bundle, omit={"bundle_sha256"})


def artifact_path(target: Path, task_key: str, rel: str) -> Path:
    return task_root(target, task_key) / rel


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
        "project_objective": "Repository-specific high-risk Agent-Flow objective. Customize before production use.",
        "repository_truth_sources": ["README.md", "AGENTS.md", "pyproject.toml"],
        "artifact_language_policy": "repository/task controlled",
        "contract_source_policy": {
            "frozen_contract_path": "automation/agent_flow/tasks/<task_key>/FROZEN_CONTRACT.md",
            "requirement_ledger_path": "automation/agent_flow/tasks/<task_key>/REQUIREMENT_LEDGER.json",
        },
        "optional_visual_source_policy": {
            "enabled": False,
            "manifest_path": "",
        },
        "risk_profile": "high-risk",
        "integration_branch": "",
        "integration_branch_policy": {
            "default": "current_checked_out_branch",
            "create_branch_without_user_authorization": False,
        },
        "requires_final_critic": True,
        "requires_ci": False,
        "ci": {
            "required": False,
            "workflow": "",
        },
        "runtime_adapter": {
            "name": "local",
            "requires_external_service": False,
        },
        "external_boundaries": {
            "requires_private_data": False,
            "requires_network": False,
            "requires_gpu": False,
        },
        "expensive_operation_policy": {
            "requires_explicit_user_authorization": True,
            "examples": [],
        },
        "human_decision_boundary": "AWAIT_HUMAN_DECISION",
        "notification_policy": {
            "terminal_states": sorted(TERMINAL_NOTIFICATION_STATES),
            "brief_path": "results/<task_key>/notification_brief.json",
        },
        "role_isolation_policy": {
            "controller": "authorized integration branch",
            "verifier": "detached worktree",
            "executor": "detached worktree",
            "create_role_branches_without_user_authorization": False,
        },
        "implementation_semantic_paths": ["src/**", "app/**", "lib/**"],
        "verifier_semantic_paths": ["tests/**", "test/**", "verifier/**"],
        "semantic_paths": {
            "implementation": ["src/**", "app/**", "lib/**"],
            "verifier": ["tests/**", "test/**", "verifier/**"],
            "runtime_environment": ["requirements*.txt", "pyproject.toml", "package*.json", "Dockerfile"],
            "ci_workflow": [".github/workflows/**"],
            "control_plane": ["automation/agent_flow/**"],
            "receipts_or_manifests": ["results/**/receipts/**", "results/**/notification_brief.json", "results/**/visual_review/**"],
            "current_or_routing": ["automation/agent_flow/tasks/**/CURRENT.json"],
            "documentation": ["docs/**", "README.md", "CHANGELOG.md"],
        },
        "role_write_scopes": {
            "Planner": [
                "automation/agent_flow/tasks/**/PLANNER_DRAFT.md",
                "automation/agent_flow/tasks/**/PLANNER_PASS_CANDIDATE.json",
                "results/**/planner_reviews/**",
            ],
            "Critic": [
                "automation/agent_flow/tasks/**/CRITIC_FREEZE.json",
                "automation/agent_flow/tasks/**/FINAL_CRITIC_AUDIT.json",
                "automation/agent_flow/tasks/**/FROZEN_CONTRACT.md",
                "automation/agent_flow/tasks/**/REQUIREMENT_LEDGER.json",
                "results/**/critic_reviews/**",
            ],
            "Controller": ["automation/agent_flow/tasks/**/CURRENT.json", "results/**/controller_report.md", "results/**/notification_brief.json"],
            "Verifier": [
                "tests/**",
                "verifier/**",
                "automation/agent_flow/tasks/**/VERIFIER_SOURCE_MANIFEST.json",
                "automation/agent_flow/tasks/**/VERIFIER_FREEZE.json",
                "results/**/verification/**",
                "results/**/findings/**",
            ],
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
    if existed:
        actions.append(f"SKIP existing file: {profile_path}")
    else:
        write_json(profile_path, default_profile(target.name))
        actions.append(f"CREATE project profile: {profile_path}")

    return inspect_agent_flow(target).state, actions


@dataclass(frozen=True)
class AgentFlowStatus:
    target: Path
    state: str
    missing: list[str]
    task_count: int
    current_branch: str
    project_profile: str


@dataclass(frozen=True)
class RoleLaunchRequest:
    role: str
    task_key: str
    request_nonce: str
    review_target_id: str | None
    base_ref: str
    allowed_write_scope: list[str]
    worktree_policy: str


@dataclass(frozen=True)
class RoleReceipt:
    role: str
    session_id: str
    runtime_adapter: str
    worktree_id: str
    base_task_nonce: str
    allowed_write_scope: list[str]
    start_or_resume_status: str
    produced_commit: str
    produced_evidence_id: str
    commit_kind: str = "no_commit"

    def to_json(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "session_id": self.session_id,
            "runtime_adapter": self.runtime_adapter,
            "worktree_id": self.worktree_id,
            "base_task_nonce": self.base_task_nonce,
            "allowed_write_scope": self.allowed_write_scope,
            "start_or_resume_status": self.start_or_resume_status,
            "produced_commit": self.produced_commit,
            "produced_evidence_id": self.produced_evidence_id,
            "commit_kind": self.commit_kind,
        }


class RuntimeAdapter:
    name = "abstract"

    def launch_role(self, request: RoleLaunchRequest) -> RoleReceipt:
        raise NotImplementedError


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
    for key, expected_type in PROFILE_REQUIRED_FIELDS.items():
        if key not in profile:
            raise ValueError(f"PROJECT_PROFILE.json missing {key}")
        if not isinstance(profile[key], expected_type):
            raise ValueError(f"PROJECT_PROFILE.json {key} must be {expected_type.__name__}")
    semantic_paths = profile.get("semantic_paths")
    if not isinstance(semantic_paths, dict):
        raise ValueError("PROJECT_PROFILE.json must contain semantic_paths")
    for key in [
        "implementation",
        "verifier",
        "runtime_environment",
        "ci_workflow",
        "control_plane",
        "receipts_or_manifests",
        "current_or_routing",
        "documentation",
    ]:
        if not isinstance(semantic_paths.get(key), list):
            raise ValueError(f"semantic_paths.{key} must be a list")
    if profile.get("implementation_semantic_paths") != semantic_paths.get("implementation"):
        raise ValueError("implementation_semantic_paths must match semantic_paths.implementation")
    if profile.get("verifier_semantic_paths") != semantic_paths.get("verifier"):
        raise ValueError("verifier_semantic_paths must match semantic_paths.verifier")
    visual_policy = profile.get("optional_visual_source_policy")
    if visual_policy.get("enabled") is not False and visual_policy.get("enabled") is not True:
        raise ValueError("optional_visual_source_policy.enabled must be boolean")
    if visual_policy.get("enabled"):
        manifest_path = str(visual_policy.get("manifest_path") or "")
        if not manifest_path or Path(manifest_path).is_absolute() or ".." in Path(manifest_path).parts:
            raise ValueError("optional_visual_source_policy.manifest_path must be repository-relative when enabled")
        privacy_policy = visual_policy.get("privacy_policy", visual_review.DEFAULT_PRIVACY_POLICY)
        if privacy_policy != visual_review.DEFAULT_PRIVACY_POLICY and not visual_policy.get("external_upload_authorization"):
            raise ValueError("optional_visual_source_policy requires explicit external_upload_authorization for non-public data")
        if profile.get("external_boundaries", {}).get("requires_private_data") and not visual_policy.get("external_upload_authorization"):
            raise ValueError("private-data Agent-Flow visual review requires explicit external_upload_authorization")
    if profile.get("integration_branch_policy", {}).get("create_branch_without_user_authorization"):
        raise ValueError("Project Profile cannot authorize branch creation without explicit user metadata")
    if profile.get("role_isolation_policy", {}).get("create_role_branches_without_user_authorization"):
        raise ValueError("Project Profile cannot create role branches without explicit user authorization")
    return profile


def load_repo_schema(target: Path) -> dict[str, Any]:
    schema = load_json(agent_root(target) / "schema.json")
    if schema.get("schema") != "AI_BRIDGE_AGENT_FLOW_SCHEMA_V1":
        raise ValueError("schema.json schema must be AI_BRIDGE_AGENT_FLOW_SCHEMA_V1")
    expected = {
        "roles": ROLES,
        "finding_classes": FINDING_CLASSES,
        "change_classes": CHANGE_CLASSES,
        "task_states": TASK_STATES,
        "critic_modes": CRITIC_MODES,
        "terminal_states": TERMINAL_NOTIFICATION_STATES,
    }
    for key, values in expected.items():
        actual = set(schema.get(key, []))
        if actual != values:
            missing = sorted(values - actual)
            extra = sorted(actual - values)
            raise ValueError(f"schema.json drift for {key}: missing={missing} extra={extra}")
    graph = schema.get("allowed_transitions")
    if not isinstance(graph, dict):
        raise ValueError("schema.json missing allowed_transitions")
    actual_graph = {str(state): set(targets) for state, targets in graph.items() if isinstance(targets, list)}
    if actual_graph != ALLOWED_TRANSITIONS:
        missing_states = sorted(set(ALLOWED_TRANSITIONS) - set(actual_graph))
        extra_states = sorted(set(actual_graph) - set(ALLOWED_TRANSITIONS))
        drift_edges = sorted(
            state for state in set(ALLOWED_TRANSITIONS).intersection(actual_graph) if actual_graph[state] != ALLOWED_TRANSITIONS[state]
        )
        raise ValueError(f"schema.json drift for allowed_transitions: missing_states={missing_states} extra_states={extra_states} drift_edges={drift_edges}")
    return schema


def validate_task_envelope(target: Path, task_key: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    root = task_root(target, task_key)
    errors: list[str] = []
    if root.name != task_key:
        errors.append("task directory name must match task_key")
    request_path = root / "REQUEST.json"
    current_path = root / "CURRENT.json"
    request = load_json(request_path) if request_path.exists() else None
    current = load_json(current_path) if current_path.exists() else None
    if request is None:
        errors.append("REQUEST.json missing")
    if current is None:
        errors.append("CURRENT.json missing")
    if request is None or current is None:
        return request, current, errors
    if request.get("schema") != "AI_BRIDGE_AGENT_FLOW_REQUEST_V1":
        errors.append("REQUEST.schema mismatch")
    if current.get("schema") != "AI_BRIDGE_AGENT_FLOW_CURRENT_V1":
        errors.append("CURRENT.schema mismatch")
    if request.get("task_key") != task_key:
        errors.append("REQUEST.task_key must match task directory")
    if current.get("task_key") != task_key:
        errors.append("CURRENT.task_key must match task directory")
    if not request.get("request_nonce"):
        errors.append("REQUEST.request_nonce missing")
    if not current.get("request_nonce"):
        errors.append("CURRENT.request_nonce missing")
    if request.get("request_nonce") != current.get("request_nonce"):
        errors.append("REQUEST/CURRENT request_nonce mismatch")
    if not isinstance(request.get("profile"), str) or not request.get("profile"):
        errors.append("REQUEST.profile missing")
    if request.get("integration_branch") != current.get("integration_branch"):
        errors.append("REQUEST/CURRENT integration_branch mismatch")
    if not isinstance(request.get("max_repair_rounds"), int) or request.get("max_repair_rounds") < 0:
        errors.append("REQUEST.max_repair_rounds must be a non-negative integer")
    if current.get("critic_mode") not in CRITIC_MODES:
        errors.append("CURRENT.critic_mode invalid")
    if current.get("state") not in TASK_STATES:
        errors.append("CURRENT.state invalid")
    return request, current, errors


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
                "findings_ref": None,
                "findings_sha256": None,
                "blocking_finding_ids": [],
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


def validate_current_semantic_snapshot(target: Path, task_key: str, profile: dict[str, Any]) -> list[str]:
    root = task_root(target, task_key)
    errors: list[str] = []
    required_paths = [
        root / "FROZEN_CONTRACT.md",
        root / "REQUIREMENT_LEDGER.json",
        root / "IMPLEMENTATION_SOURCE_MANIFEST.json",
        root / "VERIFIER_SOURCE_MANIFEST.json",
        root / "SOURCE_SNAPSHOT.json",
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(f"semantic snapshot artifact missing: {path.name}")
    if errors:
        return errors
    current_impl = source_manifest(target, task_key, profile, "implementation")
    current_verifier = source_manifest(target, task_key, profile, "verifier")
    stored_impl = load_json(root / "IMPLEMENTATION_SOURCE_MANIFEST.json")
    stored_verifier = load_json(root / "VERIFIER_SOURCE_MANIFEST.json")
    stored_snapshot = load_json(root / "SOURCE_SNAPSHOT.json")
    current_contract_sha256 = file_sha256(root / "FROZEN_CONTRACT.md")
    current_ledger_sha256 = file_sha256(root / "REQUIREMENT_LEDGER.json")
    try:
        ledger_errors = validate_requirement_ledger(load_json(root / "REQUIREMENT_LEDGER.json"))
    except Exception as exc:
        ledger_errors = [f"current REQUIREMENT_LEDGER.json unreadable or invalid: {exc}"]
    errors.extend(f"current REQUIREMENT_LEDGER.json invalid: {item}" for item in ledger_errors)
    if stored_snapshot.get("frozen_contract_sha256") != current_contract_sha256:
        errors.append("SOURCE_SNAPSHOT.json frozen_contract_sha256 is stale against current FROZEN_CONTRACT.md")
    if stored_snapshot.get("requirement_ledger_sha256") != current_ledger_sha256:
        errors.append("SOURCE_SNAPSHOT.json requirement_ledger_sha256 is stale against current REQUIREMENT_LEDGER.json")
    if stored_impl != current_impl:
        errors.append("IMPLEMENTATION_SOURCE_MANIFEST.json is stale against current tracked implementation semantic source")
    if stored_verifier != current_verifier:
        errors.append("VERIFIER_SOURCE_MANIFEST.json is stale against current tracked verifier semantic source")
    if stored_snapshot.get("implementation_semantic_digest_sha256") != current_impl.get("semantic_digest_sha256"):
        errors.append("SOURCE_SNAPSHOT.json implementation semantic digest is stale")
    if stored_snapshot.get("verifier_semantic_digest_sha256") != current_verifier.get("semantic_digest_sha256"):
        errors.append("SOURCE_SNAPSHOT.json verifier semantic digest is stale")
    recomputed_target = compute_review_target_id(
        task_identity=stored_snapshot.get("task_identity", {}),
        frozen_contract_sha256=current_contract_sha256,
        requirement_ledger_sha256=current_ledger_sha256,
        implementation_semantic_digest_sha256=current_impl["semantic_digest_sha256"],
        verifier_semantic_digest_sha256=current_verifier["semantic_digest_sha256"],
    )
    if stored_snapshot.get("review_target_id") != recomputed_target:
        errors.append("SOURCE_SNAPSHOT.json review_target_id is stale against current semantic source")
    return errors


def validate_requirement_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = ledger.get("requirements")
    if not isinstance(entries, list) or not entries:
        errors.append("REQUIREMENT_LEDGER.json must contain non-empty requirements list")
    seen: set[str] = set()
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
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
        if threshold is not None and provenance == "mechanically_derived_invariant":
            for key in [
                "parent_requirement_ids",
                "logical_derivation",
                "why_necessary",
                "changes_product_or_scientific_semantics",
            ]:
                if key not in entry:
                    errors.append(f"{req_id or index} derived threshold missing {key}")
            if entry.get("changes_product_or_scientific_semantics") is not False:
                errors.append(f"{req_id or index} derived threshold must not change product/scientific semantics")
        if threshold is not None and provenance == "requirement_ledger" and not entry.get("threshold_authority"):
            errors.append(f"{req_id or index} requirement_ledger threshold requires threshold_authority")
    if errors:
        raise ValueError("; ".join(errors))
    return []


def ledger_requirements_by_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("requirement_id")): item
        for item in ledger.get("requirements", [])
        if isinstance(item, dict) and item.get("requirement_id")
    }


def requirement_authorizes_threshold(requirement: dict[str, Any], finding: dict[str, Any]) -> bool:
    provenance = finding.get("threshold_provenance")
    if provenance == "frozen_contract":
        return requirement.get("source", {}).get("path", "").endswith("FROZEN_CONTRACT.md")
    if provenance == "requirement_ledger":
        return requirement.get("threshold") == finding.get("threshold") and bool(requirement.get("threshold_authority"))
    if provenance == "mechanically_derived_invariant":
        parent_ids = finding.get("parent_requirement_ids")
        return (
            isinstance(parent_ids, list)
            and bool(parent_ids)
            and bool(finding.get("logical_derivation"))
            and bool(finding.get("why_necessary"))
            and finding.get("changes_product_or_scientific_semantics") is False
        )
    return False


def classify_path(path: str, profile: dict[str, Any]) -> str | None:
    semantic = profile["semantic_paths"]
    if path.endswith("FROZEN_CONTRACT.md"):
        return "CONTRACT_CHANGED"
    if path.endswith("REQUIREMENT_LEDGER.json"):
        return "REQUIREMENT_LEDGER_CHANGED"
    if matches_any(path, semantic.get("implementation", [])):
        return "IMPLEMENTATION_SOURCE_CHANGED"
    if matches_any(path, semantic.get("verifier", [])):
        return "VERIFIER_SOURCE_CHANGED"
    if matches_any(path, semantic.get("runtime_environment", [])):
        return "RUNTIME_ENVIRONMENT_CHANGED"
    if matches_any(path, semantic.get("ci_workflow", [])):
        return "CI_WORKFLOW_CHANGED"
    if matches_any(path, semantic.get("current_or_routing", [])):
        return "CURRENT_OR_ROUTING_ONLY_CHANGED"
    if matches_any(path, semantic.get("control_plane", [])):
        return "CONTROL_PLANE_ONLY_CHANGED"
    if matches_any(path, semantic.get("receipts_or_manifests", [])):
        return "RECEIPT_OR_MANIFEST_ONLY_CHANGED"
    if matches_any(path, semantic.get("documentation", [])):
        return "DOC_ONLY_CHANGED"
    return None


def classify_changes(paths: list[str], profile: dict[str, Any]) -> dict[str, Any]:
    classes = sorted(
        {item for item in (classify_path(path, profile) for path in paths) if item},
        key=CHANGE_CLASS_PRIORITY.index,
    )
    if not classes:
        classes = ["NO_RELEVANT_CHANGE"]
    primary = classes[0]
    return {
        "change_classes": classes,
        "primary_change_class": primary,
        "invalidation_plan": invalidation_plan_for_classes(classes),
    }


def classify_paths(paths: list[str], profile: dict[str, Any]) -> str:
    return str(classify_changes(paths, profile)["primary_change_class"])


def invalidation_plan(change_class: str, *, review_target_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
    plan = {
        "change_class": change_class,
        "new_semantic_target_required": False,
        "heavy_verifier_required": False,
        "executor_restart": False,
        "verifier_restart": False,
        "critic_refreeze_required": False,
        "runtime_probe_required": False,
        "ci_required": False,
        "lightweight_validation_only": False,
        "requires_controller_state_validation": False,
        "review_target_id": review_target_id,
        "semantic_invalidation_reason": reason,
    }
    if change_class == "CONTRACT_CHANGED":
        plan.update(new_semantic_target_required=True, critic_refreeze_required=True, heavy_verifier_required=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "REQUIREMENT_LEDGER_CHANGED":
        plan.update(new_semantic_target_required=True, heavy_verifier_required=True, runtime_probe_required=True)
    elif change_class == "IMPLEMENTATION_SOURCE_CHANGED":
        plan.update(heavy_verifier_required=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "VERIFIER_SOURCE_CHANGED":
        plan.update(heavy_verifier_required=True, runtime_probe_required=True, ci_required=True)
    elif change_class == "RUNTIME_ENVIRONMENT_CHANGED":
        plan.update(runtime_probe_required=True)
    elif change_class == "CI_WORKFLOW_CHANGED":
        plan.update(ci_required=True)
    elif change_class in {"CONTROL_PLANE_ONLY_CHANGED", "RECEIPT_OR_MANIFEST_ONLY_CHANGED", "CURRENT_OR_ROUTING_ONLY_CHANGED"}:
        plan.update(lightweight_validation_only=True)
    if change_class == "CURRENT_OR_ROUTING_ONLY_CHANGED":
        plan.update(requires_controller_state_validation=True)
    return plan


def invalidation_plan_for_classes(change_classes: list[str], *, review_target_id: str | None = None) -> dict[str, Any]:
    union = {
        "change_classes": change_classes,
        "primary_change_class": change_classes[0] if change_classes else "NO_RELEVANT_CHANGE",
        "new_semantic_target_required": False,
        "heavy_verifier_required": False,
        "executor_restart": False,
        "verifier_restart": False,
        "critic_refreeze_required": False,
        "runtime_probe_required": False,
        "ci_required": False,
        "lightweight_validation_only": False,
        "requires_controller_state_validation": False,
        "review_target_id": review_target_id,
    }
    for change_class in change_classes:
        plan = invalidation_plan(change_class, review_target_id=review_target_id)
        for key, value in plan.items():
            if isinstance(value, bool):
                union[key] = bool(union.get(key)) or value
    return union


def assert_heavy_verifier_reason(current: dict[str, Any], review_target_id: str, reason: str | None) -> None:
    runs = current.get("heavy_verifier_runs")
    if not isinstance(runs, list):
        return
    repeated = any(run.get("review_target_id") == review_target_id for run in runs if isinstance(run, dict))
    if repeated and reason not in HEAVY_VERIFIER_REASONS:
        raise ValueError("second heavy verifier run for same review_target_id requires a semantic invalidation reason")


def planner_choice_is_bound(target: Path, task_key: str, finding: dict[str, Any]) -> bool:
    rel = finding.get("planner_classification_artifact")
    if not isinstance(rel, str) or not rel:
        return False
    path = target / rel if rel.startswith(("results/", "automation/")) else task_root(target, task_key) / rel
    if not path.exists():
        return False
    artifact = load_json(path)
    artifact_errors = validate_machine_review_artifact(
        target,
        task_key,
        artifact,
        role="Planner",
        decision="SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED",
        review_target_required=True,
    )
    return (
        not artifact_errors
        and artifact.get("decision") == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED"
        and artifact.get("finding_id") == finding.get("finding_id")
        and artifact.get("review_target_id") == finding.get("created_against_review_target_id")
    )


def route_findings(
    findings: list[dict[str, Any]],
    *,
    controller_originated: bool = False,
    target: Path | None = None,
    task_key: str | None = None,
) -> dict[str, Any]:
    blocking = [item for item in findings if item.get("blocking")]
    if not blocking:
        return {"route": "READY_FOR_PLANNER_REVIEW", "target_role": "Planner"}
    finding = blocking[0]
    classification = finding.get("classification")
    if classification not in FINDING_CLASSES:
        raise ValueError(f"unsupported finding classification: {classification}")
    if classification == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED":
        planner_bound = bool(target and task_key and planner_choice_is_bound(target, task_key, finding))
        if controller_originated or not planner_bound:
            raise ValueError("Controller cannot route a user scientific/product choice without bound Planner classification artifact")
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
        "POTENTIAL_SCIENTIFIC_OR_PRODUCT_CHOICE": ("PLANNER_REVIEW_POTENTIAL_USER_CHOICE", "Planner"),
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
        if classification == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED":
            raise ValueError("project adapter cannot independently create a user scientific/product choice")
    return {
        "schema": "AI_BRIDGE_PROJECT_ADAPTER_RESULT_V1",
        "adapter_name": adapter_name,
        "evidence": evidence or [],
        "findings": normalized_findings,
    }


def validate_role_receipt(
    receipt: dict[str, Any],
    *,
    request_nonce: str | None = None,
    review_target_id: str | None = None,
    allow_fake_test: bool = False,
) -> list[str]:
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
    for key in [
        "runtime_adapter",
        "allowed_write_scope",
        "start_or_resume_status",
        "worktree_id",
        "produced_evidence_id",
        "base_task_nonce",
        "commit_kind",
    ]:
        if key not in receipt:
            errors.append(f"role receipt missing {key}")
    commit_kind = receipt.get("commit_kind")
    if commit_kind not in {"git", "no_commit", "external", "fake-test"}:
        errors.append(f"role receipt commit_kind invalid: {commit_kind}")
    if commit_kind == "fake-test" and not allow_fake_test:
        errors.append("production role receipt cannot use commit_kind=fake-test")
    produced_commit = str(receipt.get("produced_commit") or "").strip()
    if commit_kind == "git" and not produced_commit:
        errors.append("role receipt produced_commit must be non-empty for commit_kind=git")
    if commit_kind in {"no_commit", "external"} and produced_commit:
        errors.append(f"role receipt commit_kind={commit_kind} cannot provide produced_commit for integration")
    if not str(receipt.get("produced_evidence_id") or "").strip():
        errors.append("role receipt produced_evidence_id must be non-empty")
    if request_nonce and receipt.get("base_task_nonce") != request_nonce:
        errors.append("role receipt base_task_nonce mismatch")
    if review_target_id and role in {"Verifier", "Executor"}:
        if not receipt.get("base_review_target_id"):
            errors.append("role receipt base_review_target_id missing for current semantic target")
        elif receipt.get("base_review_target_id") != review_target_id:
            errors.append("role receipt base_review_target_id mismatch")
    return errors


def git_commit_changed_paths(target: Path, commit: str) -> tuple[list[str] | None, str | None]:
    try:
        subprocess.check_call(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=target, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output = git_output(target, ["diff-tree", "--no-commit-id", "--name-only", "-r", commit])
        return sorted(line.strip() for line in output.splitlines() if line.strip()), None
    except Exception as exc:
        return None, str(exc)


def validate_role_commit_diff(target: Path, role: str, receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if receipt.get("commit_kind") != "git":
        return errors
    commit = str(receipt.get("produced_commit") or "")
    actual, err = git_commit_changed_paths(target, commit)
    if actual is None:
        return [f"{role} receipt produced_commit is not a valid Git commit: {commit}"]
    claimed = sorted(str(path) for path in receipt.get("touched_paths", []) if str(path))
    if claimed and claimed != actual:
        errors.append(f"{role} receipt touched_paths do not match produced_commit diff: claimed={claimed} actual={actual}")
    return errors


def validate_touched_paths(role: str, touched_paths: list[str], profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = profile.get("role_write_scopes", {}).get(role, [])
    for path in touched_paths:
        if allowed and not matches_any(str(path), allowed):
            errors.append(f"{role} touched path outside allowed_write_scope: {path}")
    if role == "Controller":
        forbidden_patterns = [
            *profile.get("semantic_paths", {}).get("implementation", []),
            *profile.get("semantic_paths", {}).get("verifier", []),
            "tests/**",
            "verifier/**",
        ]
        for path in touched_paths:
            if matches_any(str(path), forbidden_patterns):
                errors.append(f"Controller touched forbidden implementation/verifier path: {path}")
    return errors


def validate_executor_result(
    result: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    task_key: str | None = None,
    request_nonce: str | None = None,
    review_target_id: str | None = None,
) -> list[str]:
    errors: list[str] = []
    for key in ["schema", "task_key", "status", "touched_paths"]:
        if key not in result:
            errors.append(f"Executor result missing {key}")
    if result.get("schema") != "AI_BRIDGE_EXECUTOR_RESULT_V1":
        errors.append("Executor result schema mismatch")
    if task_key and result.get("task_key") != task_key:
        errors.append("Executor result task_key mismatch")
    if request_nonce and result.get("request_nonce") != request_nonce:
        errors.append("Executor result request_nonce mismatch")
    if review_target_id and result.get("review_target_id") != review_target_id:
        errors.append("Executor result review_target_id mismatch")
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
    if profile and isinstance(touched, list):
        errors.extend(validate_touched_paths("Executor", [str(path) for path in touched], profile))
    return errors


def validate_verifier_freeze(target: Path, task_key: str, profile: dict[str, Any]) -> list[str]:
    root = task_root(target, task_key)
    receipt = root / "VERIFIER_FREEZE.json"
    manifest = root / "VERIFIER_SOURCE_MANIFEST.json"
    errors: list[str] = []
    if not receipt.exists() or not manifest.exists():
        return ["VERIFIER_FROZEN requires verifier manifest and verifier-owned freeze receipt"]
    payload = load_json(receipt)
    manifest_json = load_json(manifest)
    request = load_json(root / "REQUEST.json")
    snapshot = load_json(root / "SOURCE_SNAPSHOT.json") if (root / "SOURCE_SNAPSHOT.json").exists() else {}
    for key in ["schema", "task_key", "request_nonce", "verifier_semantic_digest_sha256", "verifier_evidence_id"]:
        if key not in payload:
            errors.append(f"Verifier freeze missing {key}")
    if payload.get("schema") != "AI_BRIDGE_VERIFIER_FREEZE_V1":
        errors.append("Verifier freeze schema mismatch")
    if payload.get("task_key") != task_key:
        errors.append("Verifier freeze task_key mismatch")
    if payload.get("request_nonce") != request.get("request_nonce"):
        errors.append("Verifier freeze request_nonce mismatch")
    if snapshot.get("review_target_id") and payload.get("review_target_id") != snapshot.get("review_target_id"):
        errors.append("Verifier freeze review_target_id mismatch")
    if payload.get("verifier_semantic_digest_sha256") != manifest_json.get("semantic_digest_sha256"):
        errors.append("VERIFIER_FROZEN receipt digest does not match verifier source manifest")
    if not payload.get("verifier_evidence_id"):
        errors.append("VERIFIER_FROZEN requires verifier_evidence_id")
    return errors


def role_receipt_path(target: Path, task_key: str, role: str) -> Path:
    return result_root(target, task_key) / "receipts" / f"{role.lower()}_role_receipt.json"


def load_role_receipts(target: Path, task_key: str) -> dict[str, dict[str, Any]]:
    receipts = {}
    for role in ["Planner", "Critic", "Controller", "Verifier", "Executor"]:
        path = role_receipt_path(target, task_key, role)
        if path.exists():
            receipts[role] = load_json(path)
    return receipts


def validate_role_receipts(target: Path, task_key: str, profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    receipts = load_role_receipts(target, task_key)
    request = load_json(task_root(target, task_key) / "REQUEST.json")
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    review_target_id = load_json(snapshot_path).get("review_target_id") if snapshot_path.exists() else None
    session_ids: dict[str, str] = {}
    worktree_ids: dict[str, str] = {}
    for role in ["Planner", "Critic", "Controller", "Verifier", "Executor"]:
        receipt = receipts.get(role)
        if not receipt:
            continue
        errors.extend(
            f"{role} receipt: {item}"
            for item in validate_role_receipt(
                receipt,
                request_nonce=request.get("request_nonce"),
                review_target_id=review_target_id,
                allow_fake_test=False,
            )
        )
        session = str(receipt.get("session_id") or receipt.get("thread_id") or "")
        worktree = str(receipt.get("worktree_id") or "")
        if session:
            if session in session_ids:
                errors.append(f"{role} shares session/thread id with {session_ids[session]}")
            session_ids[session] = role
        if worktree:
            if worktree in worktree_ids:
                errors.append(f"{role} shares worktree identity with {worktree_ids[worktree]}")
            worktree_ids[worktree] = role
        touched = receipt.get("touched_paths", [])
        if isinstance(touched, list):
            errors.extend(validate_touched_paths(role, [str(path) for path in touched], profile))
        errors.extend(validate_role_commit_diff(target, role, receipt))
    return errors


def validate_machine_review_artifact(
    target: Path,
    task_key: str,
    artifact: dict[str, Any],
    *,
    role: str,
    decision: str,
    review_target_required: bool,
) -> list[str]:
    errors: list[str] = []
    request = load_json(task_root(target, task_key) / "REQUEST.json")
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    review_target_id = load_json(snapshot_path).get("review_target_id") if snapshot_path.exists() else None
    for key in ["role", "task_key", "request_nonce", "artifact_path", "artifact_sha256", "decision", "touched_paths"]:
        if key not in artifact:
            errors.append(f"{role} review artifact missing {key}")
    if errors:
        return errors
    if artifact.get("role") != role:
        errors.append(f"{role} review artifact role mismatch")
    if artifact.get("task_key") != task_key:
        errors.append(f"{role} review artifact task_key mismatch")
    if artifact.get("request_nonce") != request.get("request_nonce"):
        errors.append(f"{role} review artifact request_nonce mismatch")
    if artifact.get("decision") != decision:
        errors.append(f"{role} review artifact decision mismatch")
    if review_target_required and artifact.get("review_target_id") != review_target_id:
        errors.append(f"{role} review artifact review_target_id mismatch")
    rel = str(artifact.get("artifact_path"))
    path = target / rel
    if not path.exists():
        errors.append(f"{role} review artifact path missing: {rel}")
    elif artifact.get("artifact_sha256") != file_sha256(path):
        errors.append(f"{role} review artifact sha256 mismatch")
    profile = load_project_profile(target)
    touched = artifact.get("touched_paths")
    if isinstance(touched, list):
        errors.extend(validate_touched_paths(role, [str(item) for item in touched], profile))
    else:
        errors.append(f"{role} review artifact touched_paths must be a list")
    return errors


def validate_finding(finding: dict[str, Any], ledger_ids: set[str]) -> list[str]:
    return validate_finding_against_ledger(finding, {req_id: {"requirement_id": req_id} for req_id in ledger_ids}, None)


def validate_finding_against_ledger(
    finding: dict[str, Any],
    requirements: dict[str, dict[str, Any]],
    current_review_target_id: str | None,
) -> list[str]:
    errors: list[str] = []
    classification = finding.get("classification")
    if classification not in FINDING_CLASSES:
        errors.append(f"invalid finding classification: {classification}")
    if classification == "DIAGNOSTIC_ANOMALY" and finding.get("blocking"):
        errors.append("DIAGNOSTIC_ANOMALY cannot be blocking")
    if finding.get("blocking"):
        for key in [
            "finding_id",
            "classification",
            "blocking",
            "summary",
            "observed_evidence",
            "required_repair",
            "required_regression_evidence",
            "forbidden_workaround",
            "created_against_review_target_id",
        ]:
            if key not in finding:
                errors.append(f"blocking finding missing {key}")
        if not (finding.get("owner_role") or finding.get("target_role")):
            errors.append("blocking finding missing owner_role/target_role")
        if current_review_target_id and finding.get("created_against_review_target_id") != current_review_target_id:
            errors.append("target-sensitive finding is not bound to current review_target_id")
        req_ids = finding.get("requirement_ids")
        if classification != "DIAGNOSTIC_ANOMALY" and (not isinstance(req_ids, list) or not req_ids):
            errors.append("blocking finding must cite requirement_ids")
        for req_id in req_ids if isinstance(req_ids, list) else []:
            if req_id not in requirements:
                errors.append(f"blocking finding cites unknown requirement_id: {req_id}")
        threshold = finding.get("threshold")
        if threshold is not None:
            req_id = req_ids[0] if isinstance(req_ids, list) and req_ids else None
            requirement = requirements.get(str(req_id), {})
            if not requirement_authorizes_threshold(requirement, finding):
                errors.append("Verifier cannot create uncited blocking threshold")
    return errors


def current_findings_path(target: Path, task_key: str) -> Path:
    return result_root(target, task_key) / "findings" / "CURRENT_FINDINGS.json"


def load_current_findings(target: Path, task_key: str) -> dict[str, Any]:
    path = current_findings_path(target, task_key)
    if path.exists():
        return load_json(path)
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    legacy = current.get("open_findings", [])
    return {
        "schema": "AI_BRIDGE_CURRENT_FINDINGS_V1",
        "task_key": task_key,
        "request_nonce": current.get("request_nonce"),
        "review_target_id": current.get("current_review_target_id"),
        "findings": legacy if isinstance(legacy, list) else [],
    }


def materialize_current_findings(target: Path, task_key: str) -> dict[str, Any]:
    path = current_findings_path(target, task_key)
    if path.exists():
        return load_json(path)
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    legacy = current.get("open_findings", [])
    findings = legacy if isinstance(legacy, list) else []
    return write_current_findings(target, task_key, findings, current.get("current_review_target_id"))


def findings_digest(payload: dict[str, Any]) -> str:
    return payload_digest(payload, omit={"findings_sha256"})


def validate_current_findings(target: Path, task_key: str, requirements: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    payload = load_current_findings(target, task_key)
    request = load_json(task_root(target, task_key) / "REQUEST.json")
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    current_target = load_json(snapshot_path).get("review_target_id") if snapshot_path.exists() else current.get("current_review_target_id")
    if payload.get("schema") != "AI_BRIDGE_CURRENT_FINDINGS_V1":
        errors.append("CURRENT_FINDINGS schema mismatch")
    if payload.get("task_key") != task_key:
        errors.append("CURRENT_FINDINGS task_key mismatch")
    if payload.get("request_nonce") != request.get("request_nonce"):
        errors.append("CURRENT_FINDINGS request_nonce mismatch")
    if payload.get("review_target_id") not in {None, current_target}:
        errors.append("CURRENT_FINDINGS review_target_id mismatch")
    if "findings_sha256" in payload and payload.get("findings_sha256") != findings_digest(payload):
        errors.append("CURRENT_FINDINGS findings_sha256 stale")
    if current.get("findings_ref"):
        expected_ref = f"results/{task_key}/findings/CURRENT_FINDINGS.json"
        if current.get("findings_ref") != expected_ref:
            errors.append(f"CURRENT findings_ref must be {expected_ref}")
        if current.get("findings_sha256") != payload.get("findings_sha256"):
            errors.append("CURRENT findings_sha256 mismatch")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("CURRENT_FINDINGS findings must be a list")
        findings = []
    if requirements is not None:
        for finding in findings:
            if isinstance(finding, dict):
                errors.extend(validate_finding_against_ledger(finding, requirements, current_target))
                if finding.get("classification") == "SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED" and not planner_choice_is_bound(target, task_key, finding):
                    errors.append("SCIENTIFIC_OR_PRODUCT_CHOICE_REQUIRED requires bound Planner artifact")
            else:
                errors.append("finding entry must be an object")
    blocking_ids = [str(finding.get("finding_id")) for finding in findings if isinstance(finding, dict) and finding.get("blocking")]
    if current.get("blocking_finding_ids") is not None and current.get("blocking_finding_ids") != blocking_ids:
        errors.append("CURRENT blocking_finding_ids mismatch")
    return payload, errors


def write_current_findings(target: Path, task_key: str, findings: list[dict[str, Any]], review_target_id: str | None) -> dict[str, Any]:
    request = load_json(task_root(target, task_key) / "REQUEST.json")
    payload = {
        "schema": "AI_BRIDGE_CURRENT_FINDINGS_V1",
        "task_key": task_key,
        "request_nonce": request.get("request_nonce"),
        "review_target_id": review_target_id,
        "findings": findings,
    }
    payload["findings_sha256"] = findings_digest(payload)
    write_json(current_findings_path(target, task_key), payload)
    current_path = task_root(target, task_key) / "CURRENT.json"
    current = load_json(current_path)
    current.pop("open_findings", None)
    current["findings_ref"] = f"results/{task_key}/findings/CURRENT_FINDINGS.json"
    current["findings_sha256"] = payload["findings_sha256"]
    current["blocking_finding_ids"] = [str(finding.get("finding_id")) for finding in findings if finding.get("blocking")]
    write_json(current_path, current)
    return payload


def evidence_path_allowed(rel: str, task_key: str) -> bool:
    allowed = [
        f"results/{task_key}/verification/**",
        f"results/{task_key}/implementation/**",
        f"results/{task_key}/receipts/**",
        f"results/{task_key}/visual_review/**",
        f"results/{task_key}/planner_reviews/**",
        f"results/{task_key}/critic_reviews/**",
        f"automation/agent_flow/tasks/{task_key}/**",
    ]
    return matches_any(rel, allowed)


def visual_policy_enabled(profile: dict[str, Any]) -> bool:
    return profile.get("optional_visual_source_policy", {}).get("enabled") is True


def agent_flow_visual_review_path(target: Path, task_key: str, profile: dict[str, Any]) -> Path:
    policy = profile.get("optional_visual_source_policy", {})
    rel = str(policy.get("evidence_path") or f"results/{task_key}/visual_review/VISUAL_REVIEW.json")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("optional_visual_source_policy.evidence_path must be repository-relative")
    return target / rel


def agent_flow_visual_expected_bindings(target: Path, task_key: str) -> dict[str, Any]:
    root = task_root(target, task_key)
    request = load_json(root / "REQUEST.json")
    snapshot_payload = load_json(root / "SOURCE_SNAPSHOT.json")
    return {
        "task_key": task_key,
        "workflow_type": "agent_flow",
        "request_nonce": request.get("request_nonce"),
        "review_target_id": snapshot_payload.get("review_target_id"),
        "frozen_contract_sha256": snapshot_payload.get("frozen_contract_sha256"),
        "requirement_ledger_sha256": snapshot_payload.get("requirement_ledger_sha256"),
        "implementation_semantic_digest_sha256": snapshot_payload.get("implementation_semantic_digest_sha256"),
        "verifier_semantic_digest_sha256": snapshot_payload.get("verifier_semantic_digest_sha256"),
    }


def agent_flow_visual_review_status(target: Path, task_key: str, profile: dict[str, Any]) -> dict[str, Any]:
    if not visual_policy_enabled(profile):
        return {"required": False, "status": "NOT_REQUIRED", "errors": []}
    path = agent_flow_visual_review_path(target, task_key, profile)
    rel = rel_path(path, target)
    if not path.exists():
        return {"required": True, "status": "PENDING", "path": rel, "errors": ["visual review evidence pending"]}
    try:
        payload = load_json(path)
    except Exception as exc:
        return {"required": True, "status": "INVALID", "path": rel, "errors": [f"VISUAL_REVIEW.json unreadable: {exc}"]}
    errors = visual_review.validate_visual_review_payload(payload, expected=agent_flow_visual_expected_bindings(target, task_key))
    if errors:
        return {"required": True, "status": "INVALID", "path": rel, "errors": errors}
    return {"required": True, "status": payload.get("overall_decision"), "path": rel, "errors": []}


def validate_evidence_entry(target: Path, task_key: str, evidence: dict[str, Any], review_target_id: str) -> list[str]:
    errors: list[str] = []
    for key in ["evidence_id", "kind", "path", "sha256", "status", "required", "target_sensitive", "review_target_id"]:
        if key not in evidence:
            errors.append(f"required evidence missing {key}")
    if errors:
        return errors
    rel = str(evidence.get("path"))
    if not evidence_path_allowed(rel, task_key):
        errors.append(f"required evidence path outside allowed scope: {rel}")
    path = target / rel
    if not path.exists() or not path.is_file():
        errors.append(f"required evidence file missing: {rel}")
    else:
        if evidence.get("sha256") != file_sha256(path):
            errors.append(f"required evidence sha256 mismatch: {rel}")
        if path.suffix == ".json":
            try:
                artifact = load_json(path)
            except Exception as exc:
                errors.append(f"required evidence JSON artifact unreadable: {rel}: {exc}")
                artifact = {}
            if not artifact.get("schema"):
                errors.append(f"required evidence artifact missing schema: {rel}")
            if artifact.get("evidence_id") != evidence.get("evidence_id"):
                errors.append(f"required evidence artifact evidence_id mismatch: {rel}")
            if artifact.get("status") != evidence.get("status"):
                errors.append(f"required evidence artifact status mismatch: {rel}")
            if evidence.get("kind") == "visual_review":
                errors.extend(
                    f"required visual review evidence invalid: {item}"
                    for item in visual_review.validate_visual_review_payload(
                        artifact,
                        expected={
                            "task_key": task_key,
                            "workflow_type": "agent_flow",
                            "review_target_id": evidence.get("review_target_id"),
                        },
                    )
                )
            elif evidence.get("target_sensitive") and artifact.get("review_target_id") != evidence.get("review_target_id"):
                errors.append(f"required evidence artifact review_target_id mismatch: {rel}")
    allowed_statuses = EVIDENCE_SUCCESS_STATUSES.get(str(evidence.get("kind")), {"PASS", "success"})
    if evidence.get("status") not in allowed_statuses:
        errors.append(f"required evidence status is not successful: {evidence.get('status')}")
    if evidence.get("target_sensitive") and evidence.get("review_target_id") != review_target_id:
        errors.append("target-sensitive evidence is bound to a different review_target_id")
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
    ]:
        if key not in bundle:
            errors.append(f"REVIEW_BUNDLE.json missing {key}")
    if "bundle_sha256" not in bundle:
        errors.append("REVIEW_BUNDLE.json missing bundle_sha256")
    elif bundle.get("bundle_sha256") != bundle_digest(bundle):
        errors.append("REVIEW_BUNDLE.json bundle_sha256 is stale")
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
    required_evidence = bundle.get("required_evidence")
    if not isinstance(required_evidence, list):
        errors.append("REVIEW_BUNDLE.json required_evidence must be a list")
        required_evidence = []
    for evidence in required_evidence:
        if not isinstance(evidence, dict):
            errors.append("required evidence entry must be an object")
            continue
        if evidence.get("required"):
            errors.extend(validate_evidence_entry(target, task_key, evidence, str(bundle.get("review_target_id"))))
    if errors:
        raise ValueError("; ".join(errors))
    return bundle, []


def final_critic_artifact_path(target: Path, task_key: str) -> Path:
    return task_root(target, task_key) / "FINAL_CRITIC_AUDIT.json"


def planner_pass_candidate_path(target: Path, task_key: str) -> Path:
    return task_root(target, task_key) / "PLANNER_PASS_CANDIDATE.json"


def current_snapshot(target: Path, task_key: str) -> dict[str, Any]:
    return load_json(task_root(target, task_key) / "SOURCE_SNAPSHOT.json")


def validate_planner_pass_candidate(target: Path, task_key: str) -> list[str]:
    path = planner_pass_candidate_path(target, task_key)
    if not path.exists():
        return ["Planner pass candidate missing PLANNER_PASS_CANDIDATE.json"]
    errors: list[str] = []
    candidate = load_json(path)
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    request_path = task_root(target, task_key) / "REQUEST.json"
    if not snapshot_path.exists():
        return ["Planner pass candidate requires SOURCE_SNAPSHOT.json"]
    if not request_path.exists():
        return ["Planner pass candidate requires REQUEST.json"]
    snapshot_payload = load_json(snapshot_path)
    request = load_json(request_path)
    for key in ["schema", "task_key", "request_nonce", "review_target_id", "decision"]:
        if key not in candidate:
            errors.append(f"Planner pass candidate missing {key}")
    if candidate.get("decision") != "PLANNER_PASS_CANDIDATE":
        errors.append("Planner pass candidate decision must be PLANNER_PASS_CANDIDATE")
    if candidate.get("task_key") != task_key:
        errors.append("Planner pass candidate task_key mismatch")
    if candidate.get("request_nonce") != request.get("request_nonce"):
        errors.append("Planner pass candidate request_nonce mismatch")
    if candidate.get("review_target_id") != snapshot_payload.get("review_target_id"):
        errors.append("Planner pass candidate is not bound to current review_target_id")
    errors.extend(
        validate_machine_review_artifact(
            target,
            task_key,
            candidate,
            role="Planner",
            decision="PLANNER_PASS_CANDIDATE",
            review_target_required=True,
        )
    )
    return errors


def validate_critic_freeze(target: Path, task_key: str) -> list[str]:
    root = task_root(target, task_key)
    path = root / "CRITIC_FREEZE.json"
    if not path.exists():
        return ["PLAN_FROZEN requires Critic freeze artifact"]
    errors: list[str] = []
    freeze = load_json(path)
    request = load_json(root / "REQUEST.json")
    required = [
        "schema",
        "task_key",
        "request_nonce",
        "decision",
        "frozen_contract_sha256",
        "requirement_ledger_sha256",
        "critic_mode",
    ]
    for key in required:
        if key not in freeze:
            errors.append(f"Critic freeze artifact missing {key}")
    if errors:
        return errors
    if freeze.get("schema") != "AI_BRIDGE_CRITIC_FREEZE_V1":
        errors.append("Critic freeze artifact schema mismatch")
    if freeze.get("task_key") != task_key:
        errors.append("Critic freeze artifact task_key mismatch")
    if freeze.get("request_nonce") != request.get("request_nonce"):
        errors.append("Critic freeze artifact request_nonce mismatch")
    if freeze.get("decision") != "PLAN_FROZEN":
        errors.append("Critic freeze decision must be PLAN_FROZEN")
    if freeze.get("critic_mode") not in {"REQUIRED_INITIAL", "REQUIRED_CONTRACT_REVIEW"}:
        errors.append("Critic freeze critic_mode invalid")
    if (root / "FROZEN_CONTRACT.md").exists() and freeze.get("frozen_contract_sha256") != file_sha256(root / "FROZEN_CONTRACT.md"):
        errors.append("Critic freeze artifact frozen_contract_sha256 mismatch")
    if (root / "REQUIREMENT_LEDGER.json").exists() and freeze.get("requirement_ledger_sha256") != file_sha256(root / "REQUIREMENT_LEDGER.json"):
        errors.append("Critic freeze artifact requirement_ledger_sha256 mismatch")
    errors.extend(
        validate_machine_review_artifact(
            target,
            task_key,
            freeze,
            role="Critic",
            decision="PLAN_FROZEN",
            review_target_required=False,
        )
    )
    return errors


def validate_final_critic_artifact(target: Path, task_key: str) -> list[str]:
    path = final_critic_artifact_path(target, task_key)
    if not path.exists():
        return ["Final Critic artifact missing FINAL_CRITIC_AUDIT.json"]
    errors: list[str] = []
    artifact = load_json(path)
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    bundle_path = result_root(target, task_key) / "REVIEW_BUNDLE.json"
    request_path = task_root(target, task_key) / "REQUEST.json"
    if not snapshot_path.exists():
        errors.append("Final Critic artifact requires SOURCE_SNAPSHOT.json")
    if not bundle_path.exists():
        errors.append("Final Critic artifact requires REVIEW_BUNDLE.json")
    if not request_path.exists():
        errors.append("Final Critic artifact requires REQUEST.json")
    if errors:
        return errors
    snapshot_payload = load_json(snapshot_path)
    bundle = load_json(bundle_path)
    request = load_json(request_path)
    try:
        validate_review_bundle(target, task_key)
    except Exception as exc:
        errors.append(f"Final Critic artifact requires valid Review Bundle: {exc}")
    required = [
        "schema",
        "task_key",
        "request_nonce",
        "review_target_id",
        "frozen_contract_sha256",
        "requirement_ledger_sha256",
        "review_bundle_sha256",
        "planner_pass_candidate_artifact",
        "decision",
        "blocking_findings",
        "audit_checks",
        "touched_paths",
    ]
    for key in required:
        if key not in artifact:
            errors.append(f"Final Critic artifact missing {key}")
    if errors:
        return errors
    if artifact.get("schema") != "AI_BRIDGE_FINAL_CRITIC_AUDIT_V1":
        errors.append("Final Critic artifact schema must be AI_BRIDGE_FINAL_CRITIC_AUDIT_V1")
    if artifact.get("task_key") != task_key:
        errors.append("Final Critic artifact task_key mismatch")
    if artifact.get("request_nonce") != request.get("request_nonce"):
        errors.append("Final Critic artifact request_nonce mismatch")
    for key in ["review_target_id", "frozen_contract_sha256", "requirement_ledger_sha256"]:
        if artifact.get(key) != snapshot_payload.get(key):
            errors.append(f"Final Critic artifact {key} mismatch")
    if artifact.get("review_bundle_sha256") != bundle.get("bundle_sha256"):
        errors.append("Final Critic artifact review_bundle_sha256 mismatch")
    if bundle.get("bundle_sha256") != bundle_digest(bundle):
        errors.append("Final Critic artifact is bound to a stale Review Bundle digest")
    if artifact.get("planner_pass_candidate_artifact") != "PLANNER_PASS_CANDIDATE.json":
        errors.append("Final Critic artifact must bind PLANNER_PASS_CANDIDATE.json")
    if artifact.get("decision") not in {"CRITIC_FINAL_PASS", "CRITIC_FINAL_REVISE"}:
        errors.append("Final Critic decision is invalid")
    if artifact.get("decision") == "CRITIC_FINAL_PASS" and artifact.get("blocking_findings"):
        errors.append("CRITIC_FINAL_PASS cannot contain blocking_findings")
    checks = artifact.get("audit_checks")
    if not isinstance(checks, dict):
        errors.append("Final Critic audit_checks must be an object")
    else:
        missing_checks = sorted(REQUIRED_FINAL_CRITIC_CHECKS - set(checks))
        if missing_checks:
            errors.append(f"Final Critic missing required audit_checks: {missing_checks}")
        for key in REQUIRED_FINAL_CRITIC_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"Final Critic required audit_check must be true: {key}")
    touched = artifact.get("touched_paths")
    if not isinstance(touched, list):
        errors.append("Final Critic touched_paths must be an explicit list")
    elif touched:
        errors.append("Final Critic has no implementation/verifier write authority")
    errors.extend(
        validate_machine_review_artifact(
            target,
            task_key,
            artifact,
            role="Critic",
            decision=str(artifact.get("decision")),
            review_target_required=True,
        )
    )
    return errors


def has_blocking_findings(current: dict[str, Any], bundle: dict[str, Any] | None = None) -> bool:
    for source in [current.get("open_findings"), bundle.get("open_findings") if bundle else None]:
        for finding in source if isinstance(source, list) else []:
            if isinstance(finding, dict) and finding.get("blocking"):
                return True
    return False


def has_current_blocking_findings(target: Path, task_key: str) -> bool:
    findings, errors = validate_current_findings(target, task_key)
    if errors:
        return True
    return any(isinstance(finding, dict) and finding.get("blocking") for finding in findings.get("findings", []))


def validate_untracked_semantic_sources(target: Path, profile: dict[str, Any]) -> list[str]:
    try:
        output = git_output(target, ["ls-files", "--others", "--exclude-standard"])
    except Exception:
        return []
    errors: list[str] = []
    patterns = [*profile["semantic_paths"].get("implementation", []), *profile["semantic_paths"].get("verifier", [])]
    for path in [line.strip() for line in output.splitlines() if line.strip()]:
        if matches_any(path, patterns):
            errors.append(f"untracked semantic source requires commit or explicit exclusion: {path}")
    return errors


def validate_contract_review_resume(
    target: Path,
    task_key: str,
    current: dict[str, Any],
    profile: dict[str, Any],
) -> list[str]:
    root = task_root(target, task_key)
    errors = validate_critic_freeze(target, task_key)
    if not errors:
        freeze_payload = load_json(root / "CRITIC_FREEZE.json")
        if freeze_payload.get("critic_mode") != "REQUIRED_CONTRACT_REVIEW":
            errors.append("contract review requires current Critic refreeze with critic_mode=REQUIRED_CONTRACT_REVIEW")
    base_target = current.get("contract_review_base_target_id")
    if not base_target:
        errors.append("contract review resume requires contract_review_base_target_id")
    snapshot_path = root / "SOURCE_SNAPSHOT.json"
    if not snapshot_path.exists():
        errors.append("contract review resume requires regenerated SOURCE_SNAPSHOT.json")
        return errors
    errors.extend(validate_current_semantic_snapshot(target, task_key, profile))
    snapshot_payload = load_json(snapshot_path)
    new_target = snapshot_payload.get("review_target_id")
    if not new_target:
        errors.append("contract review resume requires current SOURCE_SNAPSHOT review_target_id")
    elif base_target and new_target == base_target:
        errors.append("contract review resume requires a new semantic review_target_id")
    return errors


def validate_transition_predicates(target: Path, task_key: str, state: str, current: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    root = task_root(target, task_key)
    errors: list[str] = []
    snapshot_path = root / "SOURCE_SNAPSHOT.json"
    bundle_path = result_root(target, task_key) / "REVIEW_BUNDLE.json"
    if state in {
        "VERIFIER_FROZEN",
        "READY_FOR_PLANNER_REVIEW",
        "WAITING_FOR_EXTERNAL_GPT",
        "PLANNER_PASS_CANDIDATE",
        "READY_FOR_CRITIC_FINAL_AUDIT",
        "PLANNER_PASS",
        "AWAIT_HUMAN_DECISION",
    }:
        errors.extend(validate_current_semantic_snapshot(target, task_key, profile))
    if state == "PLAN_READY_FOR_CRITIC" and not (root / "PLANNER_DRAFT.md").exists():
        errors.append("PLAN_READY_FOR_CRITIC requires current PLANNER_DRAFT artifact")
    if state in {"CONTROLLER_INITIALIZING", "VERIFIER_RUNNING"}:
        controller_receipt = role_receipt_path(target, task_key, "Controller")
        if not controller_receipt.exists():
            errors.append(f"{state} requires Controller role receipt")
        else:
            request = load_json(root / "REQUEST.json")
            errors.extend(
                f"Controller role receipt: {item}"
                for item in validate_role_receipt(load_json(controller_receipt), request_nonce=request.get("request_nonce"))
            )
    if state == "PLAN_FROZEN":
        freeze = root / "CRITIC_FREEZE.json"
        errors.extend(validate_critic_freeze(target, task_key))
        if not (root / "FROZEN_CONTRACT.md").exists():
            errors.append("PLAN_FROZEN requires FROZEN_CONTRACT.md")
        if not (root / "REQUIREMENT_LEDGER.json").exists():
            errors.append("PLAN_FROZEN requires REQUIREMENT_LEDGER.json")
        if (root / "REQUIREMENT_LEDGER.json").exists():
            try:
                validate_requirement_ledger(load_json(root / "REQUIREMENT_LEDGER.json"))
            except Exception as exc:
                errors.append(f"PLAN_FROZEN ledger invalid: {exc}")
    if state == "VERIFIER_FROZEN":
        role_receipt = role_receipt_path(target, task_key, "Verifier")
        errors.extend(validate_verifier_freeze(target, task_key, profile))
        if not role_receipt.exists():
            errors.append("VERIFIER_FROZEN requires Verifier role receipt")
        else:
            request = load_json(root / "REQUEST.json")
            snapshot = load_json(snapshot_path) if snapshot_path.exists() else {}
            errors.extend(
                f"Verifier role receipt: {item}"
                for item in validate_role_receipt(
                    load_json(role_receipt),
                    request_nonce=request.get("request_nonce"),
                    review_target_id=snapshot.get("review_target_id"),
                )
            )
    if state in {"EXECUTOR_RUNNING", "EVIDENCE_RUNNING"}:
        executor_receipt = role_receipt_path(target, task_key, "Executor")
        if not executor_receipt.exists():
            errors.append(f"{state} requires Executor role receipt")
        else:
            request = load_json(root / "REQUEST.json")
            snapshot = load_json(snapshot_path) if snapshot_path.exists() else {}
            errors.extend(
                f"Executor role receipt: {item}"
                for item in validate_role_receipt(
                    load_json(executor_receipt),
                    request_nonce=request.get("request_nonce"),
                    review_target_id=snapshot.get("review_target_id"),
                )
            )
    if state == "EVIDENCE_RUNNING":
        executor_result_path = result_root(target, task_key) / "implementation" / "executor_result.json"
        if not executor_result_path.exists():
            errors.append("EVIDENCE_RUNNING requires Executor result artifact")
        else:
            request = load_json(root / "REQUEST.json")
            snapshot = load_json(snapshot_path) if snapshot_path.exists() else {}
            errors.extend(
                validate_executor_result(
                    load_json(executor_result_path),
                    profile,
                    task_key=task_key,
                    request_nonce=request.get("request_nonce"),
                    review_target_id=snapshot.get("review_target_id"),
                )
            )
    if state == "READY_FOR_PLANNER_REVIEW":
        if not snapshot_path.exists():
            errors.append("READY_FOR_PLANNER_REVIEW requires SOURCE_SNAPSHOT.json")
        if not bundle_path.exists():
            errors.append("READY_FOR_PLANNER_REVIEW requires REVIEW_BUNDLE.json")
        if snapshot_path.exists():
            snapshot_payload = load_json(snapshot_path)
            if current.get("current_review_target_id") != snapshot_payload.get("review_target_id"):
                errors.append("CURRENT current_review_target_id must match SOURCE_SNAPSHOT")
        if bundle_path.exists():
            try:
                bundle, _ = validate_review_bundle(target, task_key)
                if profile.get("requires_ci") or profile.get("ci", {}).get("required"):
                    ci_evidence = [
                        evidence for evidence in bundle.get("required_evidence", [])
                        if isinstance(evidence, dict) and evidence.get("kind") == "ci" and evidence.get("required")
                    ]
                    if not ci_evidence:
                        errors.append("READY_FOR_PLANNER_REVIEW requires CI evidence artifact PASS")
                if visual_policy_enabled(profile):
                    visual_status = agent_flow_visual_review_status(target, task_key, profile)
                    if visual_status.get("status") == "PENDING":
                        errors.append("READY_FOR_PLANNER_REVIEW requires visual review evidence before Planner review")
                    elif visual_status.get("status") == "INVALID":
                        errors.extend(str(item) for item in visual_status.get("errors", []))
                    visual_evidence = [
                        evidence for evidence in bundle.get("required_evidence", [])
                        if isinstance(evidence, dict) and evidence.get("kind") == "visual_review" and evidence.get("required")
                    ]
                    if not visual_evidence:
                        errors.append("READY_FOR_PLANNER_REVIEW requires Visual Review evidence in Review Bundle")
            except Exception as exc:
                errors.append(f"READY_FOR_PLANNER_REVIEW bundle invalid: {exc}")
        errors.extend(validate_untracked_semantic_sources(target, profile))
    if state == "PLANNER_PASS_CANDIDATE":
        errors.extend(validate_planner_pass_candidate(target, task_key))
    if state == "READY_FOR_CRITIC_FINAL_AUDIT":
        errors.extend(validate_planner_pass_candidate(target, task_key))
    if state in {"PLANNER_PASS", "AWAIT_HUMAN_DECISION"}:
        errors.extend(validate_planner_pass_candidate(target, task_key))
        errors.extend(validate_final_critic_artifact(target, task_key))
        if bundle_path.exists():
            if has_current_blocking_findings(target, task_key):
                errors.append(f"{state} has unresolved blocking findings")
        if state == "AWAIT_HUMAN_DECISION" and current.get("terminal_policy") != "human_gate":
            errors.append("AWAIT_HUMAN_DECISION requires terminal_policy=human_gate")
    return errors


def validate_task_state(target: Path, task_key: str, profile: dict[str, Any] | None = None) -> list[str]:
    profile = load_project_profile(target) if profile is None else profile
    root = task_root(target, task_key)
    _, current, envelope_errors = validate_task_envelope(target, task_key)
    if current is None:
        return envelope_errors
    state = current.get("state")
    errors: list[str] = list(envelope_errors)
    if state not in TASK_STATES:
        errors.append(f"invalid state: {state}")
    errors.extend(validate_transition_predicates(target, task_key, str(state), current, profile))
    return errors


def validate_agent_flow(target: Path) -> tuple[list[str], int]:
    status = inspect_agent_flow(target)
    lines = [format_status(status)]
    errors: list[str] = []
    if status.missing:
        errors.extend(f"missing {item}" for item in status.missing)
    try:
        load_repo_schema(target)
    except Exception as exc:
        errors.append(f"schema drift: {exc}")
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
            request, current, envelope_errors = validate_task_envelope(target, task_key)
            errors.extend(f"{task_key}: {item}" for item in envelope_errors)
            if (task_dir / "REQUIREMENT_LEDGER.json").exists():
                try:
                    ledger = load_json(task_dir / "REQUIREMENT_LEDGER.json")
                    validate_requirement_ledger(ledger)
                    requirements = ledger_requirements_by_id(ledger)
                    _, finding_errors = validate_current_findings(target, task_key, requirements)
                    errors.extend(f"{task_key}: {item}" for item in finding_errors)
                except Exception as exc:
                    errors.append(f"{task_key}: {exc}")
            if profile:
                errors.extend(f"{task_key}: {item}" for item in validate_role_receipts(target, task_key, profile))
            for name, role in [
                ("controller_result.json", "Controller"),
                ("executor_result.json", "Executor"),
                ("verifier_result.json", "Verifier"),
            ]:
                path = result_root(target, task_key) / "implementation" / name
                if not path.exists():
                    path = result_root(target, task_key) / "verification" / name
                if path.exists() and profile:
                    payload = load_json(path)
                    touched = payload.get("touched_paths", [])
                    if isinstance(touched, list):
                        errors.extend(
                            f"{task_key}: {item}"
                            for item in validate_touched_paths(role, [str(item) for item in touched], profile)
                        )
                    if role == "Executor":
                        request = load_json(task_dir / "REQUEST.json") if (task_dir / "REQUEST.json").exists() else {}
                        snapshot_path = task_dir / "SOURCE_SNAPSHOT.json"
                        snapshot_payload = load_json(snapshot_path) if snapshot_path.exists() else {}
                        errors.extend(
                            f"{task_key}: {item}"
                            for item in validate_executor_result(
                                payload,
                                profile,
                                task_key=task_key,
                                request_nonce=request.get("request_nonce"),
                                review_target_id=snapshot_payload.get("review_target_id"),
                            )
                        )
            if (task_dir / "CURRENT.json").exists():
                errors.extend(f"{task_key}: {item}" for item in validate_task_state(target, task_key, profile or None))
                current = load_json(task_dir / "CURRENT.json")
                review_target_id = current.get("current_review_target_id")
                reason = current.get("semantic_invalidation_reason")
                if review_target_id:
                    try:
                        assert_heavy_verifier_reason(current, str(review_target_id), reason)
                    except Exception as exc:
                        errors.append(f"{task_key}: {exc}")
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


def integration_branch_ready(target: Path, current: dict[str, Any]) -> bool:
    branch = str(current.get("integration_branch") or current_branch(target))
    if branch in {"", "UNKNOWN", "DETACHED"}:
        return False
    try:
        branches = git_output(target, ["branch", "--format", "%(refname:short)"]).splitlines()
    except Exception:
        return False
    return branch in branches


def integration_plan(target: Path, task_key: str, role: str, role_receipt: dict[str, Any]) -> dict[str, Any]:
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    if not integration_branch_ready(target, current):
        raise ValueError("Controller integration requires a valid existing authorized integration branch")
    profile = load_project_profile(target)
    request = load_json(task_root(target, task_key) / "REQUEST.json")
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    review_target_id = load_json(snapshot_path).get("review_target_id") if snapshot_path.exists() else None
    errors = validate_role_receipt(
        role_receipt,
        request_nonce=request.get("request_nonce"),
        review_target_id=review_target_id,
        allow_fake_test=False,
    )
    if role_receipt.get("role") != role:
        errors.append("integration role receipt role mismatch")
    if role_receipt.get("commit_kind") != "git":
        errors.append("Controller integration requires role receipt commit_kind=git")
    errors.extend(validate_role_commit_diff(target, role, role_receipt))
    changed, err = git_commit_changed_paths(target, str(role_receipt.get("produced_commit") or ""))
    if err or changed is None:
        errors.append("Controller integration requires a valid produced Git commit")
        changed = []
    errors.extend(validate_touched_paths(role, changed, profile))
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "role": role,
        "role_commit": role_receipt.get("produced_commit"),
        "changed_paths": changed,
        "integration_branch": current.get("integration_branch") or current_branch(target),
        "branch_created": False,
        "policy": "Controller integrates exact role commit SHA into authorized existing branch only",
    }


def transition_allowed(source_state: str, next_state: str) -> bool:
    return next_state in ALLOWED_TRANSITIONS.get(source_state, set())


def route_current_findings(target: Path, task_key: str) -> dict[str, Any]:
    materialize_current_findings(target, task_key)
    ledger_path = task_root(target, task_key) / "REQUIREMENT_LEDGER.json"
    requirements = ledger_requirements_by_id(load_json(ledger_path)) if ledger_path.exists() else {}
    findings, errors = validate_current_findings(target, task_key, requirements)
    if errors:
        raise ValueError("; ".join(errors))
    return route_findings(findings.get("findings", []), target=target, task_key=task_key)


def _decision_from_json(path: Path, *, identity_key: str = "review_target_id") -> tuple[str | None, str | None, str | None]:
    if not path.exists():
        return None, None, None
    payload = load_json(path)
    identity = payload.get(identity_key)
    decision = payload.get("decision")
    return str(identity) if identity else None, str(decision) if decision else None, str(path)


def _planner_findings_decision(target: Path, task_key: str) -> tuple[str | None, str | None, str | None]:
    path = current_findings_path(target, task_key)
    payload = load_current_findings(target, task_key)
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        return (
            str(payload.get("review_target_id") or ""),
            "PLANNER_FINDINGS",
            str(path) if path.exists() else f"results/{task_key}/findings/CURRENT_FINDINGS.json",
        )
    return None, None, None


def latest_external_decision_metadata(target: Path, task_key: str, state: str) -> tuple[str | None, str | None, str | None]:
    root = task_root(target, task_key)
    if state == "WAITING_FOR_EXTERNAL_GPT":
        identity, decision, path = _decision_from_json(root / "PLANNER_PASS_CANDIDATE.json")
        if identity or decision:
            return identity, decision, path
        return _planner_findings_decision(target, task_key)
    if state == "READY_FOR_CRITIC_FINAL_AUDIT":
        return _decision_from_json(root / "FINAL_CRITIC_AUDIT.json")
    if state == "PLAN_READY_FOR_CRITIC":
        return _decision_from_json(root / "CRITIC_FREEZE.json", identity_key="request_nonce")
    if state == "CONTRACT_REVIEW_REQUIRED":
        return _decision_from_json(root / "CRITIC_FREEZE.json")
    return None, None, None


def _rel_locator(target: Path, path: str | None) -> str | None:
    if not path:
        return None
    raw = Path(path)
    try:
        return str(raw.relative_to(target))
    except ValueError:
        return path


def agent_flow_external_wait_status(target: Path, task_key: str, *, now: Any = None) -> dict[str, Any]:
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    state = str(current.get("state") or "")
    identity = str(current.get("current_review_target_id") or "")
    if state == "PLAN_READY_FOR_CRITIC":
        identity = str(current.get("request_nonce") or identity)
    decision_identity, decision, path = latest_external_decision_metadata(target, task_key, state)
    return external_wait.build_wait_status(
        current,
        current_identity=identity,
        latest_decision_identity=decision_identity,
        latest_decision=decision,
        latest_decision_path=_rel_locator(target, path),
        state_owner_map=EXTERNAL_WAIT_STATE_OWNERS,
        now=now,
    )


def _stale_external_decision_errors(errors: list[str]) -> bool:
    if not errors:
        return False
    stale_markers = [
        "review_target_id mismatch",
        "not bound to current_review_target_id",
        "current review_target_id",
    ]
    return all(any(marker in error for marker in stale_markers) for error in errors)


def plan_transition(target: Path, task_key: str) -> dict[str, Any]:
    profile = load_project_profile(target)
    current = load_json(task_root(target, task_key) / "CURRENT.json")
    state = current.get("state")
    errors = validate_task_state(target, task_key, profile)
    if errors:
        return {"state": state, "valid": False, "errors": errors, "next_action": "REPAIR_STATE_EVIDENCE"}
    if state == "PLAN_REQUESTED":
        return {
            "state": state,
            "valid": True,
            "next_state": "PLAN_READY_FOR_CRITIC",
            "next_action": "RUN_PLANNER_INITIAL",
            **agent_flow_external_wait_status(target, task_key),
        }
    if state == "PLAN_READY_FOR_CRITIC":
        return {
            "state": state,
            "valid": True,
            "next_state": "PLAN_FROZEN",
            "next_action": "RUN_CRITIC_INITIAL",
            **agent_flow_external_wait_status(target, task_key),
        }
    if state == "PLAN_FROZEN":
        return {"state": state, "valid": True, "next_state": "CONTROLLER_INITIALIZING", "next_action": "INITIALIZE_CONTROLLER"}
    if state == "CONTROLLER_INITIALIZING":
        return {"state": state, "valid": True, "next_state": "VERIFIER_RUNNING", "next_action": "LAUNCH_VERIFIER"}
    if state == "VERIFIER_RUNNING":
        return {"state": state, "valid": True, "next_state": "VERIFIER_FROZEN", "next_action": "WAIT_FOR_VERIFIER_FREEZE"}
    if state == "VERIFIER_FROZEN":
        return {"state": state, "valid": True, "next_state": "EXECUTOR_RUNNING", "next_action": "LAUNCH_EXECUTOR"}
    if state == "EXECUTOR_RUNNING":
        return {"state": state, "valid": True, "next_state": "EVIDENCE_RUNNING", "next_action": "COLLECT_RUNTIME_EVIDENCE"}
    if state == "EVIDENCE_RUNNING":
        visual_status = agent_flow_visual_review_status(target, task_key, profile)
        if visual_status.get("required") and visual_status.get("status") == "PENDING":
            return {
                "state": state,
                "valid": True,
                "next_action": "WAIT_FOR_VISUAL_REVIEW_EVIDENCE",
                "visual_review": visual_status,
            }
        if profile.get("requires_ci") or profile.get("ci", {}).get("required"):
            return {"state": state, "valid": True, "next_state": "CI_RUNNING", "next_action": "RUN_CI"}
        return {"state": state, "valid": True, "next_state": "READY_FOR_PLANNER_REVIEW", "next_action": "RUN_PLANNER_REVIEW"}
    if state == "CI_RUNNING":
        return {"state": state, "valid": True, "next_state": "READY_FOR_PLANNER_REVIEW", "next_action": "RUN_PLANNER_REVIEW"}
    if state == "READY_FOR_PLANNER_REVIEW":
        return {
            "state": state,
            "valid": True,
            "next_state": "WAITING_FOR_EXTERNAL_GPT",
            "next_action": "RUN_PLANNER_REVIEW",
            **agent_flow_external_wait_status(target, task_key),
        }
    if state == "WAITING_FOR_EXTERNAL_GPT":
        candidate_errors = validate_planner_pass_candidate(target, task_key)
        if not candidate_errors:
            return {"state": state, "valid": True, "next_state": "PLANNER_PASS_CANDIDATE", "next_action": "RUN_FINAL_CRITIC"}
        try:
            route = route_current_findings(target, task_key)
        except ValueError as exc:
            split_errors = [item.strip() for item in str(exc).split(";") if item.strip()]
            if _stale_external_decision_errors(split_errors):
                return {
                    "state": state,
                    "valid": True,
                    "next_action": "WAIT_FOR_PLANNER_REVIEW_ARTIFACT",
                    **agent_flow_external_wait_status(target, task_key),
                }
            return {"state": state, "valid": False, "errors": [str(exc)], "next_action": "REPAIR_FINDINGS_ARTIFACT"}
        route_to_state = {
            "REPAIR_EXECUTOR": "PLANNER_REVISE_EXECUTOR",
            "REPAIR_VERIFIER": "PLANNER_REVISE_VERIFIER",
            "PLANNER_INTERPRET_CONTRACT": "CONTRACT_REVIEW_REQUIRED",
            "PLANNER_TO_CRITIC_CONTRACT_REVIEW": "CONTRACT_REVIEW_REQUIRED",
            "ASK_USER": "NEEDS_USER_SCIENTIFIC_OR_PRODUCT_CHOICE",
        }
        next_state = route_to_state.get(route["route"])
        if next_state:
            return {"state": state, "valid": True, "next_state": next_state, "next_action": route["route"], "route": route}
        return {
            "state": state,
            "valid": True,
            "next_action": "WAIT_FOR_PLANNER_REVIEW_ARTIFACT",
            **agent_flow_external_wait_status(target, task_key),
        }
    if state == "PLANNER_REVISE_EXECUTOR":
        return {"state": state, "valid": True, "next_state": "EXECUTOR_RUNNING", "next_action": "LAUNCH_EXECUTOR_REPAIR"}
    if state == "PLANNER_REVISE_VERIFIER":
        return {"state": state, "valid": True, "next_state": "VERIFIER_RUNNING", "next_action": "LAUNCH_VERIFIER_REPAIR"}
    if state == "PLANNER_REVISE_BOTH":
        return {"state": state, "valid": True, "next_state": "VERIFIER_RUNNING", "next_action": "LAUNCH_VERIFIER_THEN_EXECUTOR_REPAIR"}
    if state == "CONTRACT_REVIEW_REQUIRED":
        resume_errors = validate_contract_review_resume(target, task_key, current, profile)
        if resume_errors:
            return {
                "state": state,
                "valid": True,
                "next_action": "RUN_OR_WAIT_CONTRACT_CRITIC_REVIEW",
                "waiting_on": resume_errors,
                **agent_flow_external_wait_status(target, task_key),
            }
        return {"state": state, "valid": True, "next_state": "PLANNER_REVISE_BOTH", "next_action": "RESUME_AFTER_CONTRACT_REFREEZE"}
    if state == "PLANNER_PASS_CANDIDATE":
        return {"state": state, "valid": True, "next_state": "READY_FOR_CRITIC_FINAL_AUDIT", "next_action": "RUN_FINAL_CRITIC"}
    if state == "READY_FOR_CRITIC_FINAL_AUDIT":
        final_errors = validate_final_critic_artifact(target, task_key)
        if final_errors:
            return {
                "state": state,
                "valid": True,
                "next_action": "RUN_OR_WAIT_FINAL_CRITIC",
                "waiting_on": final_errors,
                **agent_flow_external_wait_status(target, task_key),
            }
        artifact = load_json(final_critic_artifact_path(target, task_key))
        if artifact.get("decision") == "CRITIC_FINAL_PASS":
            return {"state": state, "valid": True, "next_state": "PLANNER_PASS", "next_action": "APPLY_FINAL_CRITIC_PASS"}
        return {"state": state, "valid": True, "next_state": "CRITIC_FINAL_REVISE", "next_action": "ROUTE_FINAL_CRITIC_REVISE"}
    if state == "CRITIC_FINAL_REVISE":
        return {
            "state": state,
            "valid": True,
            "next_state": "WAITING_FOR_EXTERNAL_GPT",
            "next_action": "RUN_PLANNER_REVIEW",
            **agent_flow_external_wait_status(target, task_key),
        }
    if state == "PLANNER_PASS":
        return {"state": state, "valid": True, "next_state": "AWAIT_HUMAN_DECISION", "next_action": "WRITE_TERMINAL_BRIEF"}
    return {"state": state, "valid": True, "next_action": "NO_AUTOMATIC_TRANSITION"}


def apply_transition(target: Path, task_key: str, *, expected_state: str, next_state: str, next_action: str = "") -> dict[str, Any]:
    path = task_root(target, task_key) / "CURRENT.json"
    current = load_json(path)
    if current.get("state") != expected_state:
        raise ValueError(f"transition expected {expected_state}, found {current.get('state')}")
    if not transition_allowed(expected_state, next_state):
        raise ValueError(f"illegal transition edge: {expected_state} -> {next_state}")
    errors = validate_task_state(target, task_key)
    if errors:
        raise ValueError("; ".join(errors))
    profile = load_project_profile(target)
    snapshot_path = task_root(target, task_key) / "SOURCE_SNAPSHOT.json"
    if snapshot_path.exists() and next_state in {
        "VERIFIER_FROZEN",
        "EVIDENCE_RUNNING",
        "CI_RUNNING",
        "READY_FOR_PLANNER_REVIEW",
        "WAITING_FOR_EXTERNAL_GPT",
        "CONTRACT_REVIEW_REQUIRED",
        "PLANNER_PASS_CANDIDATE",
        "READY_FOR_CRITIC_FINAL_AUDIT",
        "PLANNER_PASS",
        "AWAIT_HUMAN_DECISION",
    }:
        snapshot_payload = load_json(snapshot_path)
        current["current_review_target_id"] = snapshot_payload.get("review_target_id")
        current["frozen_contract_sha256"] = snapshot_payload.get("frozen_contract_sha256")
        current["requirement_ledger_sha256"] = snapshot_payload.get("requirement_ledger_sha256")
        current["implementation_semantic_digest_sha256"] = snapshot_payload.get("implementation_semantic_digest_sha256")
        current["verifier_semantic_digest_sha256"] = snapshot_payload.get("verifier_semantic_digest_sha256")
    if next_state == "PLAN_FROZEN":
        current["critic_mode"] = "STANDBY"
        if (task_root(target, task_key) / "FROZEN_CONTRACT.md").exists():
            current["frozen_contract_sha256"] = file_sha256(task_root(target, task_key) / "FROZEN_CONTRACT.md")
        if (task_root(target, task_key) / "REQUIREMENT_LEDGER.json").exists():
            current["requirement_ledger_sha256"] = file_sha256(task_root(target, task_key) / "REQUIREMENT_LEDGER.json")
    if next_state == "CONTRACT_REVIEW_REQUIRED":
        current["critic_mode"] = "REQUIRED_CONTRACT_REVIEW"
        current["contract_review_base_target_id"] = current.get("current_review_target_id")
    if expected_state == "CONTRACT_REVIEW_REQUIRED" and next_state == "PLANNER_REVISE_BOTH":
        resume_errors = validate_contract_review_resume(target, task_key, current, profile)
        if resume_errors:
            raise ValueError("; ".join(resume_errors))
        snapshot_payload = load_json(task_root(target, task_key) / "SOURCE_SNAPSHOT.json")
        current["current_review_target_id"] = snapshot_payload.get("review_target_id")
        current["frozen_contract_sha256"] = snapshot_payload.get("frozen_contract_sha256")
        current["requirement_ledger_sha256"] = snapshot_payload.get("requirement_ledger_sha256")
        current["implementation_semantic_digest_sha256"] = snapshot_payload.get("implementation_semantic_digest_sha256")
        current["verifier_semantic_digest_sha256"] = snapshot_payload.get("verifier_semantic_digest_sha256")
        current["critic_mode"] = "STANDBY"
        current.pop("contract_review_base_target_id", None)
    if next_state == "READY_FOR_CRITIC_FINAL_AUDIT":
        current["critic_mode"] = "REQUIRED_FINAL_AUDIT"
    if next_state == "AWAIT_HUMAN_DECISION":
        current["terminal_policy"] = "human_gate"
    next_errors = validate_transition_predicates(target, task_key, next_state, current, profile)
    if next_errors:
        raise ValueError("; ".join(next_errors))
    current["state"] = next_state
    if next_action:
        current["next_action"] = next_action
    write_json(path, current)
    return current


def write_terminal_brief(target: Path, task_key: str) -> dict[str, Any]:
    errors = validate_task_state(target, task_key)
    if errors:
        raise ValueError("; ".join(errors))
    brief = terminal_notification_brief(target, task_key)
    if brief is None:
        raise ValueError("task is not in a terminal/user-decision notifiable state")
    path = result_root(target, task_key) / "notification_brief.json"
    write_json(path, brief)
    return brief


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

    terminal = sub.add_parser("terminal-brief")
    terminal.add_argument("--target", type=Path, default=Path.cwd())
    terminal.add_argument("--task-key", required=True)

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
        print(canonical_json(classify_changes(sorted(set(paths)), profile), pretty=True), end="")
        return 0
    if args.command == "route":
        result = route_current_findings(args.target, args.task_key)
        print(canonical_json(result, pretty=True), end="")
        return 0
    if args.command == "transition" and args.transition_command == "plan":
        print(canonical_json(plan_transition(args.target, args.task_key), pretty=True), end="")
        return 0
    if args.command == "transition" and args.transition_command == "apply":
        print(
            canonical_json(
                apply_transition(
                    args.target,
                    args.task_key,
                    expected_state=args.expected_state,
                    next_state=args.next_state,
                    next_action=args.next_action,
                ),
                pretty=True,
            ),
            end="",
        )
        return 0
    if args.command == "terminal-brief":
        print(canonical_json(write_terminal_brief(args.target, args.task_key), pretty=True), end="")
        return 0
    if args.command == "prompt":
        print(role_prompt(args.target, args.role))
        return 0
    parser.print_help()
    return 0
