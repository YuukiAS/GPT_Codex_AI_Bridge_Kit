from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


HOST_BEGIN_MARKER = "<!-- ai-bridge-kit:host-policy:start -->"
HOST_END_MARKER = "<!-- ai-bridge-kit:host-policy:end -->"
RULES_RELATIVE_PATH = Path("rules") / "ai-bridge-global.rules"
NARRATIVE_POLICY_MARKERS = [
    "## User-Facing Narrative Language",
    "natural Simplified Chinese",
    "goal-objective.md",
    "Repository artifacts are a separate concern from interactive narrative",
    "repository/task-specific language policy",
]

REQUIRED_CONFIG = {
    ("", "approval_policy"): '"on-request"',
    ("", "sandbox_mode"): '"workspace-write"',
    ("", "approvals_reviewer"): '"auto_review"',
    ("sandbox_workspace_write", "network_access"): "true",
    ("features", "default_mode_request_user_input"): "true",
    ("features", "memories"): "true",
}


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class ConfigCheck:
    key: str
    actual: str | None
    expected: str
    state: str


@dataclass(frozen=True)
class HostStatus:
    codex_home: Path
    config_exists: bool
    config_checks: list[ConfigCheck]
    agents_state: str
    narrative_language_state: str
    narrative_language: str
    artifact_language_policy: str
    rules_state: str
    project_overrides: list[Path]
    overall_state: str


def resolve_codex_home(explicit: Path | None = None, env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if explicit is not None:
        return explicit.expanduser().resolve()
    if env.get("CODEX_HOME"):
        return Path(env["CODEX_HOME"]).expanduser().resolve()
    return Path.home().joinpath(".codex").resolve()


def desired_agents_block() -> str:
    snippet = read_text(kit_root() / "templates" / "host" / "GLOBAL_AGENTS_SNIPPET.md").strip()
    return f"{HOST_BEGIN_MARKER}\n{snippet}\n{HOST_END_MARKER}\n"


def desired_rules_text() -> str:
    return read_text(kit_root() / "templates" / "host" / "rules" / "ai-bridge-global.rules")


def _section_for_line(line: str, current: str) -> str:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
        return stripped.strip("[]").strip()
    return current


def _split_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
        return None
    return key, value.strip()


def config_values(text: str) -> dict[tuple[str, str], str]:
    values: dict[tuple[str, str], str] = {}
    section = ""
    for line in text.splitlines():
        section = _section_for_line(line, section)
        parsed = _split_assignment(line)
        if parsed:
            key, value = parsed
            values[(section, key)] = value
    return values


def _format_assignment(key: str, value: str, source_line: str | None = None) -> str:
    if source_line is None:
        return f"{key} = {value}"
    indent = source_line[: len(source_line) - len(source_line.lstrip())]
    return f"{indent}{key} = {value}"


def patch_config_text(text: str) -> str:
    lines = text.splitlines()
    found: set[tuple[str, str]] = set()
    sections: set[str] = set()
    current_section = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            current_section = stripped.strip("[]").strip()
            sections.add(current_section)
        parsed = _split_assignment(line)
        if parsed and (current_section, parsed[0]) in REQUIRED_CONFIG:
            found.add((current_section, parsed[0]))

    missing_by_section: dict[str, list[tuple[str, str]]] = {}
    for (section, key), value in REQUIRED_CONFIG.items():
        if (section, key) not in found:
            missing_by_section.setdefault(section, []).append((key, value))

    output: list[str] = []
    inserted_root = "" not in missing_by_section
    inserted_sections = {section for section in ["sandbox_workspace_write", "features"] if section not in missing_by_section}

    def append_missing(section: str, leading_blank: bool = True) -> None:
        missing = missing_by_section.get(section, [])
        if not missing:
            return
        if leading_blank and output and output[-1].strip():
            output.append("")
        for key, value in missing:
            output.append(_format_assignment(key, value))

    for line in lines:
        stripped = line.strip()
        is_table = stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[[")
        if is_table:
            if not inserted_root:
                append_missing("")
                inserted_root = True
            section_for_line = stripped.strip("[]").strip()
        else:
            section_for_line = _section_for_line(line, section_for_line) if "section_for_line" in locals() else ""

        parsed = _split_assignment(line)
        if parsed and (section_for_line, parsed[0]) in REQUIRED_CONFIG:
            key = parsed[0]
            output.append(_format_assignment(key, REQUIRED_CONFIG[(section_for_line, key)], line))
        else:
            output.append(line)

        if is_table and section_for_line in missing_by_section and section_for_line not in inserted_sections:
            append_missing(section_for_line, leading_blank=False)
            inserted_sections.add(section_for_line)

    if not inserted_root:
        append_missing("")
        inserted_root = True

    for section in ["sandbox_workspace_write", "features"]:
        if section in inserted_sections:
            continue
        if section in sections:
            continue
        else:
            if output and output[-1].strip():
                output.append("")
            output.append(f"[{section}]")
            append_missing(section, leading_blank=False)
        inserted_sections.add(section)

    return "\n".join(output).rstrip() + "\n"


def install_managed_block(current: str | None, block: str) -> str:
    if current is None or current == "":
        return block
    if HOST_BEGIN_MARKER in current and HOST_END_MARKER in current:
        start = current.index(HOST_BEGIN_MARKER)
        end = current.index(HOST_END_MARKER) + len(HOST_END_MARKER)
        prefix = current[:start].rstrip()
        suffix = current[end:].lstrip()
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(block.rstrip())
        if suffix:
            parts.append(suffix.rstrip())
        return "\n\n".join(parts) + "\n"
    return current.rstrip() + "\n\n" + block


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup(codex_home: Path, files_to_modify: list[Path]) -> Path:
    backup_root = codex_home / "ai-bridge-kit" / "backups" / _timestamp()
    backup_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "timestamp": backup_root.name,
        "kit_version": __version__,
        "codex_home": str(codex_home),
        "modified_files": [],
    }
    for path in files_to_modify:
        rel = path.relative_to(codex_home)
        entry = {
            "path": str(rel),
            "existed": path.exists(),
            "backup_path": None,
        }
        if path.exists():
            backup_path = backup_root / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
            entry["backup_path"] = str(backup_path)
        manifest["modified_files"].append(entry)
    (backup_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return backup_root


def install_host_policy(codex_home: Path) -> tuple[HostStatus, list[str]]:
    codex_home.mkdir(parents=True, exist_ok=True)
    config_path = codex_home / "config.toml"
    agents_path = codex_home / "AGENTS.md"
    rules_path = codex_home / RULES_RELATIVE_PATH

    current_config = read_text(config_path) if config_path.exists() else ""
    next_config = patch_config_text(current_config)
    current_agents = read_text(agents_path) if agents_path.exists() else None
    next_agents = install_managed_block(current_agents, desired_agents_block())
    current_rules = read_text(rules_path) if rules_path.exists() else None
    next_rules = desired_rules_text()

    changes: list[tuple[Path, str]] = []
    if next_config != current_config:
        changes.append((config_path, next_config))
    if next_agents != (current_agents or ""):
        changes.append((agents_path, next_agents))
    if next_rules != current_rules:
        changes.append((rules_path, next_rules))

    actions: list[str] = []
    if changes:
        backup_dir = create_backup(codex_home, [path for path, _ in changes])
        actions.append(f"Backup: {backup_dir}")
        for path, text in changes:
            write_text(path, text)
            actions.append(f"Updated: {path}")
    else:
        actions.append("No changes needed; host policy is already configured.")

    return inspect_host_policy(codex_home), actions


def _normalize_config_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[:1] in {"'", '"'} and value[-1:] == value[:1]:
        return value[1:-1]
    return value


def _check_config(config_path: Path) -> list[ConfigCheck]:
    values = config_values(read_text(config_path)) if config_path.exists() else {}
    checks: list[ConfigCheck] = []
    for (section, key), expected in REQUIRED_CONFIG.items():
        actual = values.get((section, key))
        dotted = f"{section}.{key}" if section else key
        state = "configured" if _normalize_config_value(actual) == _normalize_config_value(expected) else "missing"
        if actual is not None and state != "configured":
            state = "drifted"
        checks.append(ConfigCheck(dotted, actual, expected, state))
    return checks


def _state_from_checks(checks: list[ConfigCheck]) -> str:
    states = {check.state for check in checks}
    if "drifted" in states:
        return "drifted"
    if "missing" in states:
        return "missing"
    return "configured"


def _agents_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    current = read_text(path)
    block = desired_agents_block()
    if block in current:
        return "configured"
    if HOST_BEGIN_MARKER in current or HOST_END_MARKER in current:
        return "drifted"
    return "missing"


def _narrative_language_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    current = read_text(path)
    if HOST_BEGIN_MARKER not in current or HOST_END_MARKER not in current:
        return "missing"
    start = current.index(HOST_BEGIN_MARKER)
    end = current.index(HOST_END_MARKER) + len(HOST_END_MARKER)
    managed_block = current[start:end]
    return (
        "configured"
        if all(marker in managed_block for marker in NARRATIVE_POLICY_MARKERS)
        else "drifted"
    )


def _rules_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "configured" if read_text(path) == desired_rules_text() else "drifted"


def detect_project_overrides(cwd: Path | None = None) -> list[Path]:
    cwd = Path.cwd() if cwd is None else cwd
    candidates = [cwd / ".codex" / "config.toml", cwd / ".codex" / "rules"]
    return [path for path in candidates if path.exists()]


def inspect_host_policy(codex_home: Path, cwd: Path | None = None) -> HostStatus:
    config_path = codex_home / "config.toml"
    config_checks = _check_config(config_path)
    config_state = _state_from_checks(config_checks) if config_path.exists() else "missing"
    agents_state = _agents_state(codex_home / "AGENTS.md")
    narrative_language_state = _narrative_language_state(codex_home / "AGENTS.md")
    rules_state = _rules_state(codex_home / RULES_RELATIVE_PATH)
    states = {config_state, agents_state, narrative_language_state, rules_state}
    if "drifted" in states:
        overall = "drifted"
    elif "missing" in states:
        overall = "missing"
    else:
        overall = "configured"
    return HostStatus(
        codex_home=codex_home,
        config_exists=config_path.exists(),
        config_checks=config_checks,
        agents_state=agents_state,
        narrative_language_state=narrative_language_state,
        narrative_language="zh-CN",
        artifact_language_policy="repository/task controlled",
        rules_state=rules_state,
        project_overrides=detect_project_overrides(cwd),
        overall_state=overall,
    )


def _run_codex(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["codex", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _codex_version() -> tuple[str | None, str | None]:
    try:
        result = _run_codex(["--version"])
    except FileNotFoundError:
        return None, "codex executable not found"
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode != 0:
        return output or None, "codex --version failed"
    version_line = next((line for line in output.splitlines() if "codex" in line.lower()), output)
    return version_line, None


def _feature_availability() -> tuple[dict[str, bool], list[str]]:
    try:
        result = _run_codex(["features", "list"])
    except FileNotFoundError:
        return {}, ["codex executable not found"]
    issues: list[str] = []
    if result.returncode != 0:
        return {}, ["codex features list failed"]
    features: dict[str, bool] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] in {"default_mode_request_user_input", "memories"}:
            features[parts[0]] = parts[-1].lower() == "true"
    for feature in ["default_mode_request_user_input", "memories"]:
        if feature not in features:
            issues.append(f"missing capability: {feature}")
        elif not features[feature]:
            issues.append(f"capability disabled: {feature}")
    return features, issues


def _execpolicy_decision(rules_path: Path, command: list[str]) -> tuple[str | None, str]:
    try:
        result = _run_codex(["execpolicy", "check", "--rules", str(rules_path), *command])
    except FileNotFoundError:
        return None, "codex executable not found"
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode != 0:
        return None, output
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        lower = result.stdout.lower()
        if "allow" in lower:
            return "allow", output
        if "no matching" in lower or "ask" in lower:
            return "no_match", output
        return None, output
    decision = str(payload.get("decision") or payload.get("outcome") or "").lower()
    if payload.get("matchedRules") == [] and not decision:
        return "no_match", output
    if decision == "allow":
        return "allow", output
    if decision in {"ask", "deny", "none", "no_match", "no-match"}:
        return "no_match", output
    return decision or None, output


def _with_incompatible(status: HostStatus) -> HostStatus:
    if status.overall_state != "configured":
        return status
    return HostStatus(
        status.codex_home,
        status.config_exists,
        status.config_checks,
        status.agents_state,
        status.narrative_language_state,
        status.narrative_language,
        status.artifact_language_policy,
        status.rules_state,
        status.project_overrides,
        "incompatible",
    )


def validate_host_policy(codex_home: Path, cwd: Path | None = None) -> tuple[HostStatus, list[str], int]:
    status = inspect_host_policy(codex_home, cwd)
    lines: list[str] = []
    exit_code = 0

    if status.overall_state != "configured":
        exit_code = 1
        lines.append(f"Host policy files are {status.overall_state}. Run: ai-bridge host install")

    version, version_error = _codex_version()
    if version:
        lines.append(f"Codex version: {version}")
    if version_error:
        exit_code = 1
        status = _with_incompatible(status)
        lines.append(f"Incompatible: {version_error}")

    _, feature_issues = _feature_availability()
    if feature_issues:
        exit_code = 1
        status = _with_incompatible(status)
        for issue in feature_issues:
            lines.append(f"Incompatible: {issue}")
    else:
        lines.append("Feature availability: default_mode_request_user_input and memories available/enabled")

    rules_path = codex_home / RULES_RELATIVE_PATH
    checks = [
        (["git", "push", "origin", "main"], "allow"),
        (["git", "push", "upstream", "main"], "no_match"),
        (["git", "push", "--set-upstream", "origin", "main"], "allow"),
        (["git", "push", "-u", "origin", "main"], "allow"),
    ]
    for command, expected in checks:
        decision, raw = _execpolicy_decision(rules_path, command)
        label = " ".join(command)
        if decision == expected:
            lines.append(f"Execpolicy: {label} => {decision}")
        else:
            exit_code = 1
            lines.append(f"Execpolicy mismatch: {label} => {decision or 'unknown'} expected {expected}")
            if raw:
                lines.append(f"Execpolicy raw output: {raw}")

    return status, lines, exit_code


def format_status(status: HostStatus) -> str:
    lines = [
        f"Codex Home: {status.codex_home}",
        f"config.toml exists: {str(status.config_exists).lower()}",
    ]
    for check in status.config_checks:
        actual = check.actual if check.actual is not None else "missing"
        lines.append(f"{check.key}: {actual} ({check.state})")
    lines.extend(
        [
            f"global AGENTS managed block: {status.agents_state}",
            f"narrative_language: {status.narrative_language} ({status.narrative_language_state})",
            f"artifact_language_policy: {status.artifact_language_policy}",
            f"ai-bridge-global.rules: {status.rules_state}",
        ]
    )
    if status.project_overrides:
        lines.append("project override awareness:")
        for path in status.project_overrides:
            lines.append(f"- {path}")
    else:
        lines.append("project override awareness: none found in current repository")
    lines.append(f"overall state: {status.overall_state}")
    return "\n".join(lines)
