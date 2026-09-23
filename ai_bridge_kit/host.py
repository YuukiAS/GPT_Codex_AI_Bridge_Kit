from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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
EXTERNAL_WAIT_POLICY_MARKERS = [
    "## External Planner / Reviewer Waiting",
    "MIN_EXTERNAL_GPT_WAIT = 2 hours",
    "waiting_external_review",
    "Stale Planner/Reviewer/Critic artifacts are not new decisions",
    "must not consume `review_round`, `repair_round`",
]

REQUIRED_CONFIG = {
    ("", "approval_policy"): '"on-request"',
    ("", "sandbox_mode"): '"workspace-write"',
    ("", "approvals_reviewer"): '"auto_review"',
    ("sandbox_workspace_write", "network_access"): "true",
    ("features", "default_mode_request_user_input"): "false",
    ("features", "memories"): "true",
}


class HostPublishError(ValueError):
    pass


@dataclass(frozen=True)
class PublishResult:
    status: str
    repo: str
    branch: str
    pushed_oid: str
    destination: str
    output: str


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
    trusted_ai_bridge_executable: Path | None
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


def resolve_ai_bridge_executable() -> Path | None:
    resolved = shutil.which("ai-bridge")
    if resolved:
        return Path(resolved).resolve()
    argv0 = Path(sys.argv[0]).expanduser()
    if argv0.name == "ai-bridge" and argv0.exists():
        return argv0.resolve()
    return None


def _starlark_string(value: str) -> str:
    return json.dumps(value)


def desired_rules_text(ai_bridge_executable: Path | None = None) -> str:
    text = read_text(kit_root() / "templates" / "host" / "rules" / "ai-bridge-global.rules")
    executable = ai_bridge_executable or resolve_ai_bridge_executable()
    replacement = _starlark_string(str(executable)) if executable else '"AI_BRIDGE_EXECUTABLE_NOT_RESOLVED"'
    return text.replace('"@@AI_BRIDGE_EXECUTABLE@@"', replacement)


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
    trusted_executable = resolve_ai_bridge_executable()
    next_rules = desired_rules_text(trusted_executable)

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


def _rules_state(path: Path, ai_bridge_executable: Path | None = None) -> str:
    if not path.exists():
        return "missing"
    return "configured" if read_text(path) == desired_rules_text(ai_bridge_executable) else "drifted"


def detect_project_overrides(cwd: Path | None = None) -> list[Path]:
    cwd = Path.cwd() if cwd is None else cwd
    candidates = [cwd / ".codex" / "config.toml", cwd / ".codex" / "rules"]
    return [path for path in candidates if path.exists()]


def inspect_host_policy(codex_home: Path, cwd: Path | None = None) -> HostStatus:
    config_path = codex_home / "config.toml"
    trusted_executable = resolve_ai_bridge_executable()
    config_checks = _check_config(config_path)
    config_state = _state_from_checks(config_checks) if config_path.exists() else "missing"
    agents_state = _agents_state(codex_home / "AGENTS.md")
    narrative_language_state = _narrative_language_state(codex_home / "AGENTS.md")
    rules_state = _rules_state(codex_home / RULES_RELATIVE_PATH, trusted_executable)
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
        trusted_ai_bridge_executable=trusted_executable,
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


def _git(
    cwd: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise HostPublishError(message)
    return result


def _git_text(cwd: Path, args: list[str], *, env: dict[str, str] | None = None) -> str:
    return _git(cwd, args, env=env).stdout.strip()


def _git_lines(cwd: Path, args: list[str]) -> list[str]:
    text = _git_text(cwd, args)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _canonical_repo_identity(url: str) -> str:
    value = url.strip()
    if value.startswith("file://"):
        return "local:" + Path(value.removeprefix("file://")).expanduser().resolve().as_posix()
    local_candidate = Path(value).expanduser()
    if local_candidate.exists() or value.startswith(("/", "./", "../")):
        return "local:" + local_candidate.resolve().as_posix()
    patterns = [
        r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    raise HostPublishError("REMOTE_IDENTITY_UNSUPPORTED")


def _single_remote_url(cwd: Path, args: list[str], reason: str) -> str:
    urls = _git_lines(cwd, args)
    if len(urls) != 1:
        raise HostPublishError(reason)
    return urls[0]


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "on"}


def _config_value(cwd: Path, key: str) -> str:
    result = _git(cwd, ["config", "--get", key], check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _config_entries_with_scope(cwd: Path) -> list[tuple[str, str, str]]:
    result = _git(cwd, ["config", "--show-scope", "--show-origin", "--list"], check=False)
    if result.returncode != 0:
        raise HostPublishError("GIT_CONFIG_INSPECTION_FAILED")
    entries: list[tuple[str, str, str]] = []
    for raw in result.stdout.splitlines():
        parts = raw.split("\t", 2)
        if len(parts) != 3 or "=" not in parts[2]:
            continue
        scope, origin, assignment = parts
        key, value = assignment.split("=", 1)
        entries.append((scope.strip(), key.strip(), value.strip()))
    return entries


def _has_config_key(cwd: Path, key: str) -> bool:
    return _git(cwd, ["config", "--get-all", key], check=False).returncode == 0


def _reject_process_transport_env(env: dict[str, str]) -> None:
    for key in ["GIT_SSH", "GIT_SSH_COMMAND"]:
        if env.get(key):
            raise HostPublishError("CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL")
    for key in ["GIT_ASKPASS", "SSH_ASKPASS"]:
        if env.get(key):
            raise HostPublishError("ASKPASS_REQUIRES_APPROVAL")
    if any(
        key in env
        for key in [
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
            "GIT_CONFIG_NOSYSTEM",
        ]
    ) or any(key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) for key in env):
        raise HostPublishError("CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL")
    if any(key.startswith("GIT_PUSH_OPTION") for key in env):
        raise HostPublishError("PUSH_OPTIONS_REQUIRE_APPROVAL")


def _reject_repository_transport_config(cwd: Path) -> None:
    if _has_config_key(cwd, "core.sshCommand"):
        raise HostPublishError("CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL")
    if _has_config_key(cwd, "core.askPass"):
        raise HostPublishError("ASKPASS_REQUIRES_APPROVAL")
    for scope, key, _value in _config_entries_with_scope(cwd):
        if key == "credential.helper" or (key.startswith("credential.") and key.endswith(".helper")):
            if scope in {"local", "worktree", "command"}:
                raise HostPublishError("REPO_CREDENTIAL_HELPER_REQUIRES_APPROVAL")


def _pre_push_hook_path(cwd: Path) -> Path:
    hooks_path = _config_value(cwd, "core.hooksPath")
    git_dir = Path(_git_text(cwd, ["rev-parse", "--git-dir"]))
    if not git_dir.is_absolute():
        git_dir = cwd / git_dir
    if hooks_path:
        candidate = Path(hooks_path).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        return candidate / "pre-push"
    return git_dir / "hooks" / "pre-push"


def _reject_active_hook(cwd: Path) -> None:
    hook = _pre_push_hook_path(cwd)
    if hook.exists() and os.access(hook, os.X_OK):
        raise HostPublishError("PRE_PUSH_HOOK_REQUIRES_APPROVAL")


def _sanitized_push_env(source: dict[str, str]) -> dict[str, str]:
    env = dict(source)
    for key in list(env):
        if key in {
            "GIT_SSH",
            "GIT_SSH_COMMAND",
            "GIT_SSH_VARIANT",
            "GIT_ASKPASS",
            "SSH_ASKPASS",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_SYSTEM",
            "GIT_CONFIG_NOSYSTEM",
        } or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_PUSH_OPTION")):
            env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _assert_publisher_preconditions(
    cwd: Path,
    *,
    expected_repo: str,
    expected_branch: str,
    env: dict[str, str],
) -> tuple[str, str]:
    _reject_process_transport_env(env)
    if env.get("AI_BRIDGE_REVIEWED_RUNNER_PUSH_GUARD") or env.get("AI_BRIDGE_REVIEWED_EXECUTOR"):
        raise HostPublishError("REVIEW_EXECUTOR_GUARD_REQUIRES_REVIEWED_RUNNER")
    top = Path(_git_text(cwd, ["rev-parse", "--show-toplevel"])).resolve()
    branch = _git_text(top, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch != expected_branch:
        raise HostPublishError("BRANCH_ASSERTION_FAILED")
    fetch_url = _single_remote_url(top, ["remote", "get-url", "--all", "origin"], "REMOTE_URL_AMBIGUOUS")
    push_url = _single_remote_url(top, ["remote", "get-url", "--push", "--all", "origin"], "REMOTE_PUSH_URL_AMBIGUOUS")
    repo = _canonical_repo_identity(fetch_url)
    push_repo = _canonical_repo_identity(push_url)
    if repo != push_repo or repo != expected_repo:
        raise HostPublishError("REMOTE_IDENTITY_MISMATCH")
    if _config_value(top, f"branch.{branch}.remote") != "origin":
        raise HostPublishError("UPSTREAM_REMOTE_MISMATCH")
    if _config_value(top, f"branch.{branch}.merge") != f"refs/heads/{branch}":
        raise HostPublishError("UPSTREAM_MERGE_MISMATCH")
    if _is_true(_config_value(top, "remote.origin.mirror")):
        raise HostPublishError("MIRROR_PUSH_REQUIRES_APPROVAL")
    if _is_true(_config_value(top, "push.followTags")):
        raise HostPublishError("FOLLOW_TAGS_REQUIRES_APPROVAL")
    recurse = _config_value(top, "push.recurseSubmodules").lower()
    if recurse and recurse not in {"no", "false", "off"}:
        raise HostPublishError("RECURSIVE_SUBMODULE_PUSH_REQUIRES_APPROVAL")
    if _has_config_key(top, "push.pushOption"):
        raise HostPublishError("PUSH_OPTIONS_REQUIRE_APPROVAL")
    signing = _config_value(top, "push.gpgSign").lower()
    if signing and signing not in {"false", "no", "off"}:
        raise HostPublishError("SIGNED_PUSH_REQUIRES_APPROVAL")
    captured_head = _git_text(top, ["rev-parse", "HEAD"])
    _reject_repository_transport_config(top)
    _reject_active_hook(top)
    remote_env = _sanitized_push_env(env)
    remote_query = _git_text(top, ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"], env=remote_env)
    remote_parts = remote_query.split()
    if len(remote_parts) < 2:
        raise HostPublishError("REMOTE_SAME_NAME_BRANCH_REQUIRED")
    remote_oid = remote_parts[0]
    if _git(top, ["merge-base", "--is-ancestor", remote_oid, "HEAD"], check=False).returncode != 0:
        raise HostPublishError("REMOTE_AHEAD_REQUIRES_PULL")
    return top.as_posix(), captured_head


def publish_current_branch(
    cwd: Path,
    *,
    expected_repo: str,
    expected_branch: str,
    env: dict[str, str] | None = None,
) -> PublishResult:
    active_env = dict(os.environ if env is None else env)
    top_text, captured_head = _assert_publisher_preconditions(
        cwd,
        expected_repo=expected_repo,
        expected_branch=expected_branch,
        env=active_env,
    )
    top = Path(top_text)
    mutation_env = _sanitized_push_env(active_env)
    final_top, final_head = _assert_publisher_preconditions(
        top,
        expected_repo=expected_repo,
        expected_branch=expected_branch,
        env=mutation_env,
    )
    if Path(final_top) != top or final_head != captured_head:
        raise HostPublishError("FINAL_RECHECK_CHANGED")
    refspec = f"{captured_head}:refs/heads/{expected_branch}"
    result = _git(
        top,
        [
            "-c",
            "push.followTags=false",
            "-c",
            "push.recurseSubmodules=no",
            "-c",
            "push.gpgSign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "push",
            "--porcelain",
            "origin",
            refspec,
        ],
        env=mutation_env,
        check=False,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode != 0:
        raise HostPublishError(output or "git push failed")
    return PublishResult(
        status="published",
        repo=expected_repo,
        branch=expected_branch,
        pushed_oid=captured_head,
        destination=f"origin/refs/heads/{expected_branch}",
        output=output,
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
    if "default_mode_request_user_input" not in features:
        issues.append("missing capability: default_mode_request_user_input")
    if "memories" not in features:
        issues.append("missing capability: memories")
    elif not features["memories"]:
        issues.append("capability disabled: memories")
    return features, issues


def _execpolicy_decision(
    rules_path: Path,
    command: list[str],
    *,
    resolve_host_executables: bool = False,
) -> tuple[str | None, str]:
    try:
        args = ["execpolicy", "check", "--rules", str(rules_path)]
        if resolve_host_executables:
            args.append("--resolve-host-executables")
        result = _run_codex([*args, *command])
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
        if "prompt" in lower or "ask" in lower:
            return "prompt", output
        if "forbidden" in lower or "deny" in lower:
            return "forbidden", output
        if "no matching" in lower:
            return "no_match", output
        return None, output
    decision = str(payload.get("decision") or payload.get("outcome") or "").lower().replace("-", "_")
    if payload.get("matchedRules") == [] and not decision:
        return "no_match", output
    if decision == "allow":
        return "allow", output
    if decision in {"prompt", "ask"}:
        return "prompt", output
    if decision in {"forbidden", "deny"}:
        return "forbidden", output
    if decision in {"none", "no_match"}:
        return "no_match", output
    return decision or None, output


def _effective_execpolicy_decision(decision: str | None) -> str | None:
    if decision == "no_match":
        return "prompt"
    return decision


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
        status.trusted_ai_bridge_executable,
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

    features, feature_issues = _feature_availability()
    if feature_issues:
        exit_code = 1
        status = _with_incompatible(status)
        for issue in feature_issues:
            lines.append(f"Incompatible: {issue}")
    else:
        default_state = "enabled" if features.get("default_mode_request_user_input") else "disabled"
        lines.append(
            "Feature availability: default_mode_request_user_input supported/"
            f"{default_state}; memories available/enabled"
        )

    rules_path = codex_home / RULES_RELATIVE_PATH
    trusted_executable = resolve_ai_bridge_executable()
    if trusted_executable:
        lines.append(f"Trusted ai-bridge executable: {trusted_executable}")
    else:
        exit_code = 1
        status = _with_incompatible(status)
        lines.append("Incompatible: ai-bridge executable not found for host_executable pinning")
    replay_command = [
        "ai-bridge",
        "plugin-replay",
        "--target",
        str(cwd or Path.cwd()),
        "--plugin",
        "sites",
        "--task",
        "TASK.md",
        "--input",
        "INPUT.txt",
        "--dry-run",
    ]
    publisher_command = [
        "ai-bridge",
        "host",
        "publish-current-branch",
        "--expected-repo",
        "YuukiAS/GPT_Codex_AI_Bridge_Kit",
        "--expected-branch",
        "main",
    ]
    materializer_command = [
        "ai-bridge",
        "reviewed-handoff",
        "materialize-worktree",
        "--target",
        str(cwd or Path.cwd()),
        "--task-key",
        "repo--feature",
        "--expected-repo",
        "YuukiAS/GPT_Codex_AI_Bridge_Kit",
        "--expected-worktree",
        "/tmp/repo--feature",
        "--expected-base-ref",
        "origin/main",
        "--mode",
        "bootstrap",
    ]
    gh_safe_read_checks = [
        ["gh", "auth", "status", "--"],
        ["gh", "pr", "list", "--"],
        ["gh", "pr", "status", "--"],
        ["gh", "issue", "list", "--"],
        ["gh", "issue", "status", "--"],
        ["gh", "run", "list", "--"],
    ]
    gh_gated_checks = [
        ["gh", "auth", "status", "--show-token"],
        ["gh", "pr", "view", "1"],
        ["gh", "pr", "list", "--repo", "private/repo"],
        ["gh", "api", "/user"],
    ]
    slurm_read_only_checks = [
        ["squeue", "-j", "156911", "-o", "%.18i %.9P %.30j %.8u %.2t %.12M %.12l %.20R %.30b"],
        ["squeue", "-u", "testuser", "-h"],
        ["sinfo", "-h"],
        ["sacct", "-j", "156911"],
        ["sstat", "-j", "156911.batch"],
        ["sprio", "-j", "156911"],
        ["scontrol", "show", "job", "156911"],
        ["scontrol", "show", "partition"],
        ["scontrol", "ping"],
    ]
    slurm_gated_checks = [
        ["sbatch", "job.sh"],
        ["srun", "--pty", "bash"],
        ["salloc", "-t", "00:10:00"],
        ["scancel", "156911"],
        ["scontrol", "update", "JobId=156911", "TimeLimit=30"],
        ["scontrol", "hold", "156911"],
        ["scontrol", "release", "156911"],
        ["scontrol", "requeue", "156911"],
        ["scontrol", "suspend", "156911"],
        ["scontrol", "resume", "156911"],
        ["sacctmgr", "modify", "user", "name=test", "set", "Fairshare=2"],
        ["bash", "-lc", "squeue -h | xargs scancel"],
    ]
    process_read_only_checks = [
        ["ps", "-u", "testuser", "-o", "pid,ppid,stat,etime,cmd"],
        ["ps", "-ef"],
    ]
    process_gated_checks = [
        ["kill", "123"],
        ["pkill", "python"],
        ["renice", "10", "-p", "123"],
        ["setsid", "bash"],
        ["python", "script.py"],
        ["bash", "-lc", "ps -ef"],
        ["sh", "-c", "ps -ef"],
        ["zsh", "-c", "ps -ef"],
    ]
    tmux_read_only_checks = [
        ["tmux", "ls"],
        ["tmux", "list-sessions"],
        ["tmux", "has-session", "-t", "example"],
    ]
    tmux_gated_checks = [
        ["tmux", "new-session", "-d", "-s", "example"],
        ["tmux", "kill-session", "-t", "example"],
        ["tmux", "kill-server"],
        ["tmux", "send-keys", "-t", "example", "ls", "Enter"],
        ["tmux", "attach-session", "-t", "example"],
        ["tmux", "detach-client", "-s", "example"],
    ]
    checks: list[tuple[list[str], str, str, bool]] = [
        (replay_command, "allow", "direct", True),
        (publisher_command, "allow", "direct", True),
        (materializer_command, "allow", "direct", True),
        *[(command, "allow", "direct", False) for command in gh_safe_read_checks],
        *[(command, "prompt", "effective", False) for command in gh_gated_checks],
        *[(command, "allow", "direct", False) for command in slurm_read_only_checks],
        *[(command, "prompt", "effective", False) for command in slurm_gated_checks],
        *[(command, "allow", "direct", False) for command in process_read_only_checks],
        *[(command, "prompt", "effective", False) for command in process_gated_checks],
        *[(command, "allow", "direct", False) for command in tmux_read_only_checks],
        *[(command, "prompt", "effective", False) for command in tmux_gated_checks],
        (["codex", "exec", "-C", "/tmp", "-"], "prompt", "effective", False),
        (["git", "fetch", "origin", "main"], "allow", "direct", False),
        (["git", "fetch", "--all", "--prune"], "allow", "direct", False),
        (["git", "fetch", "https://example.invalid/repo.git", "main"], "prompt", "effective", False),
        (["git", "fetch", "origin", "feature:feature"], "prompt", "effective", False),
        (["git", "pull", "--ff-only", "origin", "main"], "allow", "direct", False),
        (["git", "pull", "--rebase", "origin", "main"], "prompt", "effective", False),
        (["git", "pull", "--ff-only", "--autostash", "origin", "main"], "prompt", "effective", False),
        (["git", "pull", "--ff-only", "origin", "main", "--autostash"], "prompt", "effective", False),
        (["git", "add", "README.md"], "allow", "direct", False),
        (["git", "commit", "-m", "test"], "allow", "direct", False),
        (["git", "commit", "--amend", "--no-edit"], "allow", "direct", False),
        (["git", "push", "origin", "main"], "prompt", "effective", False),
        (["git", "push", "origin", "test-branch"], "prompt", "effective", False),
        (["git", "push", "upstream", "main"], "no_match", "direct", False),
        (["git", "switch", "main"], "prompt", "effective", False),
        (["git", "switch", "-c", "test-branch"], "prompt", "effective", False),
        (["git", "checkout", "-b", "test-branch"], "prompt", "effective", False),
        (["git", "branch", "test-branch"], "prompt", "effective", False),
        (["git", "reset", "--hard"], "prompt", "effective", False),
        (["git", "clean", "-fd"], "prompt", "effective", False),
        (["git", "restore", "README.md"], "prompt", "effective", False),
        (["git", "remote", "add", "mirror", "https://example.invalid/repo.git"], "prompt", "effective", False),
        (["git", "remote", "remove", "origin"], "prompt", "effective", False),
        (["git", "remote", "set-url", "origin", "https://example.invalid/repo.git"], "prompt", "effective", False),
        (["git", "branch", "-d", "test-branch"], "prompt", "effective", False),
        (["git", "branch", "-D", "test-branch"], "prompt", "effective", False),
        (["git", "branch", "-m", "old-branch", "new-branch"], "prompt", "effective", False),
        (["git", "worktree", "add", "../wt", "-b", "test-branch"], "prompt", "effective", False),
        (["git", "push", "-u", "origin", "test-branch"], "prompt", "effective", False),
        (["git", "push", "--set-upstream", "origin", "test-branch"], "prompt", "effective", False),
        (["git", "push", "origin", "--delete", "test-branch"], "prompt", "effective", False),
        (["git", "push", "origin", "--force", "main"], "prompt", "effective", False),
        (["git", "push", "origin", "main", "--force"], "prompt", "effective", False),
        (["git", "push", "origin", "main", "--force-with-lease"], "prompt", "effective", False),
        (["git", "push", "origin", "main", "-f"], "prompt", "effective", False),
    ]
    for command, expected, comparison, resolve_host in checks:
        decision, raw = _execpolicy_decision(
            rules_path,
            command,
            resolve_host_executables=resolve_host,
        )
        observed = _effective_execpolicy_decision(decision) if comparison == "effective" else decision
        label = " ".join(command)
        if observed == expected:
            suffix = f" ({decision})" if comparison == "effective" and decision != observed else ""
            lines.append(f"Execpolicy: {label} => {observed}{suffix}")
        else:
            exit_code = 1
            lines.append(f"Execpolicy mismatch: {label} => {observed or 'unknown'} expected {expected}")
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
    if status.trusted_ai_bridge_executable:
        lines.append(f"trusted ai-bridge executable: {status.trusted_ai_bridge_executable}")
    else:
        lines.append("trusted ai-bridge executable: unresolved")
    if status.project_overrides:
        lines.append("project override awareness:")
        for path in status.project_overrides:
            lines.append(f"- {path}")
    else:
        lines.append("project override awareness: none found in current repository")
    lines.append(f"overall state: {status.overall_state}")
    return "\n".join(lines)
