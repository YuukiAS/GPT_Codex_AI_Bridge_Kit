from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable


WRITING_PLUGIN_ID = "writing-style@yuukias-ai-skills"
REQUIRED_SKILLS = ("writing-fidelity", "chinese-prose")
MAX_OUTPUT_BYTES = 4096
MODEL_TIMEOUT_SECONDS = 90


class ClearWritingError(ValueError):
    pass


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_dicts(nested)


def _plugin_items(payload: Any) -> list[dict[str, Any]]:
    return [
        item
        for item in _walk_dicts(payload)
        if (item.get("id") or item.get("pluginId") or item.get("plugin_id")) == WRITING_PLUGIN_ID
    ]


def _plugin_root(item: dict[str, Any]) -> Path:
    for key in ("installedPath", "installed_path", "path", "source"):
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("path")
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser().resolve()
            if path.is_dir():
                return path
    raise ClearWritingError("WRITING_STYLE_PLUGIN_PATH_UNAVAILABLE")


def _manifest_identity(root: Path, item: dict[str, Any]) -> tuple[str, str]:
    path = root / ".codex-plugin" / "plugin.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_MANIFEST_INVALID") from exc
    plugin_id = payload.get("id") or payload.get("pluginId")
    plugin_name = payload.get("name")
    if plugin_id not in {None, WRITING_PLUGIN_ID} or plugin_name not in {None, "writing-style"}:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_MANIFEST_ID_MISMATCH")
    if plugin_id is None and plugin_name != "writing-style":
        raise ClearWritingError("WRITING_STYLE_PLUGIN_MANIFEST_ID_MISMATCH")
    inventory_version = item.get("localVersion") or item.get("version")
    manifest_version = payload.get("version")
    if not isinstance(inventory_version, str) or not inventory_version.strip():
        raise ClearWritingError("WRITING_STYLE_PLUGIN_VERSION_UNAVAILABLE")
    if manifest_version != inventory_version:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_VERSION_MISMATCH")
    return inventory_version, path.as_posix()


def _skill_name(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClearWritingError("WRITING_STYLE_SKILL_UNREADABLE") from exc
    match = re.search(r"(?m)^name:\s*([^\s]+)\s*$", text[:4096])
    if not match:
        raise ClearWritingError("WRITING_STYLE_SKILL_NAME_MISSING")
    return match.group(1).split(":")[-1]


def _resolve_skills(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob("SKILL.md"):
        name = _skill_name(path)
        if name in REQUIRED_SKILLS:
            if name in result:
                raise ClearWritingError(f"WRITING_STYLE_SKILL_AMBIGUOUS: {name}")
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ClearWritingError("WRITING_STYLE_SKILL_PATH_ESCAPE")
            result[name] = resolved.as_posix()
    missing = [name for name in REQUIRED_SKILLS if name not in result]
    if missing:
        raise ClearWritingError("WRITING_STYLE_SKILLS_UNAVAILABLE: " + ",".join(missing))
    return result


def resolve_installed_writing_style(
    *,
    codex_bin: str = "codex",
    runner: Callable[..., Any] = subprocess.run,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    executable = shutil.which(codex_bin) if not Path(codex_bin).is_absolute() else codex_bin
    if not executable:
        raise ClearWritingError("CODEX_EXECUTABLE_UNAVAILABLE")
    result = runner(
        [executable, "plugin", "list", "--json"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(0.1, min(30.0, timeout_seconds)),
    )
    if result.returncode != 0:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_INVENTORY_FAILED")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_INVENTORY_INVALID") from exc
    items = _plugin_items(payload)
    if len(items) != 1:
        raise ClearWritingError(f"WRITING_STYLE_PLUGIN_IDENTITY_AMBIGUOUS: count={len(items)}")
    item = items[0]
    if item.get("installed") is not True or item.get("enabled") is not True:
        raise ClearWritingError("WRITING_STYLE_PLUGIN_NOT_ENABLED")
    root = _plugin_root(item)
    version, manifest = _manifest_identity(root, item)
    return {
        "plugin_id": WRITING_PLUGIN_ID,
        "version": version,
        "root": root.as_posix(),
        "manifest": manifest,
        "skills": _resolve_skills(root),
        "codex_bin": str(Path(executable).resolve()),
    }


def _reader_facts(brief: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "project",
        "task_key",
        "consumer",
        "fact_class",
        "event_type",
        "terminal_status",
        "status",
        "decision_authority",
        "summary",
        "key_conclusion",
        "next_step",
        "stage",
        "completed",
        "total",
        "fraction",
        "eta",
        "eta_low",
        "eta_high",
        "duration_seconds",
        "branch",
        "version",
        "run_id",
        "runtime_id",
        "source_event_id",
    ]
    return {key: brief[key] for key in keys if key in brief}


def _prompt(brief: dict[str, Any]) -> str:
    facts = json.dumps(_reader_facts(brief), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return (
        "Use $writing-fidelity and $chinese-prose to render one concise natural Simplified Chinese notification. "
        "Preserve the exact status, project, task identity, every number/date/time/version, UNKNOWN, "
        "and the original conclusion strength. Add no facts or numbers. Runtime/operational facts must never become "
        "Goal PASS, READY, RELEASE_READY, or semantic completion. Return only the notification text.\n"
        f"Immutable facts: {facts}\n"
    )


def _parse_jsonl(stdout: str, skills: dict[str, str]) -> tuple[str, dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, raw in enumerate(stdout.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ClearWritingError(f"CODEX_JSONL_INVALID_LINE: {number}") from exc
        if not isinstance(event, dict):
            raise ClearWritingError(f"CODEX_JSONL_NON_OBJECT_LINE: {number}")
        events.append(event)
    counts = Counter(str(event.get("type") or "") for event in events)
    if counts["thread.started"] != 1 or counts["turn.started"] != 1 or counts["turn.completed"] != 1:
        raise ClearWritingError(
            "CODEX_TURN_BOUNDARY_INVALID: "
            f"thread.started={counts['thread.started']} turn.started={counts['turn.started']} "
            f"turn.completed={counts['turn.completed']}"
        )
    if counts["turn.failed"] or counts["error"]:
        raise ClearWritingError("CODEX_TURN_FAILED")
    messages: list[str] = []
    consumed = {name: False for name in REQUIRED_SKILLS}
    for event in events:
        for item in _walk_dicts(event):
            kind = str(item.get("type") or item.get("kind") or "")
            if kind in {"agent_message", "agentMessage"}:
                text = item.get("text") or item.get("message")
                if isinstance(text, str) and text.strip():
                    messages.append(text.strip())
            if "skill" in kind.lower():
                name = str(item.get("name") or item.get("skill") or "").split(":")[-1]
                path = str(item.get("path") or "")
                if name in consumed and path and Path(path).resolve().as_posix() == skills[name]:
                    consumed[name] = True
            if kind in {"command_execution", "commandExecution", "local_shell_call"}:
                command = str(item.get("command") or item.get("cmd") or "")
                if not re.search(r"(^|\s)(cat|sed|head|tail|rg|bat)(\s|$)", command):
                    continue
                for name, path in skills.items():
                    if re.search(
                        rf"(?:^|[;&|]\s*|\s)(?:cat|sed|head|tail|rg|bat)\b[^;&|\n]*{re.escape(path)}",
                        command,
                    ):
                        consumed[name] = True
    if not messages:
        raise ClearWritingError("CODEX_FINAL_AGENT_MESSAGE_MISSING")
    missing = [name for name, value in consumed.items() if not value]
    if missing:
        raise ClearWritingError("CODEX_SKILL_CONSUMPTION_UNPROVEN: " + ",".join(missing))
    return messages[-1], {"event_counts": dict(counts), "skill_consumed": consumed}


def _numbers(text: str) -> Counter[str]:
    return Counter(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text))


def fidelity_check(brief: dict[str, Any], rendered: str) -> None:
    if not rendered.strip() or len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ClearWritingError("CLEAR_WRITING_OUTPUT_EMPTY_OR_OVERSIZE")
    facts = _reader_facts(brief)
    required = [
        str(value)
        for value in [
            facts.get("project"),
            facts.get("task_key"),
            facts.get("status") or facts.get("terminal_status"),
            facts.get("branch"),
            facts.get("version"),
            facts.get("run_id"),
            facts.get("runtime_id"),
            *(brief.get("required_exact_literals") if isinstance(brief.get("required_exact_literals"), list) else []),
        ]
        if value not in {None, ""}
    ]
    for literal in required:
        if literal not in rendered:
            raise ClearWritingError(f"CLEAR_WRITING_REQUIRED_LITERAL_MISSING: {literal}")
    canonical = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    if _numbers(canonical) != _numbers(rendered):
        raise ClearWritingError("CLEAR_WRITING_PROTECTED_NUMBERS_CHANGED")
    if "UNKNOWN" in canonical and "UNKNOWN" not in rendered:
        raise ClearWritingError("CLEAR_WRITING_UNKNOWN_CHANGED")
    status = str(facts.get("status") or facts.get("terminal_status") or "").lower()
    if (facts.get("event_type") or "") in {"operational_blocked", "operational_progress"} or status in {
        "blocked",
        "failed",
        "pending",
        "running",
        "unknown",
        "awaiting_human",
    }:
        forbidden = ("Goal PASS", "READY", "RELEASE_READY", "目标已完成", "发布就绪")
        if any(re.search(rf"(?<![A-Za-z_]){re.escape(token)}(?![A-Za-z_])", rendered, re.IGNORECASE) for token in forbidden):
            raise ClearWritingError("CLEAR_WRITING_CONCLUSION_STRENGTHENED")


def render_once(
    brief: dict[str, Any],
    *,
    fallback_text: str,
    codex_bin: str = "codex",
    state_root: Path | None = None,
    runner: Callable[..., Any] = subprocess.run,
    timeout_seconds: float = MODEL_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        plugin = resolve_installed_writing_style(
            codex_bin=codex_bin,
            runner=runner,
            timeout_seconds=timeout_seconds,
        )
    except (ClearWritingError, OSError, subprocess.SubprocessError) as exc:
        return {
            "mode": "DETERMINISTIC_FALLBACK",
            "text": fallback_text,
            "failure": f"{type(exc).__name__}: {exc}",
            "model_invocations": 0,
            "model_retry_count": 0,
        }
    neutral = (
        state_root
        or Path(os.environ.get("AI_BRIDGE_STATE_HOME", "~/.ai-bridge")).expanduser()
    ).resolve() / "clear-writing"
    neutral.mkdir(parents=True, exist_ok=True)
    command = [
        plugin["codex_bin"],
        "exec",
        "--ephemeral",
        "--json",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "-C",
        neutral.as_posix(),
        "-",
    ]
    try:
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ClearWritingError("CLEAR_WRITING_DEADLINE_EXHAUSTED")
        result = runner(
            command,
            input=_prompt(brief),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(0.1, min(MODEL_TIMEOUT_SECONDS, remaining)),
        )
        if result.returncode != 0:
            raise ClearWritingError(f"CODEX_EXEC_NONZERO: {result.returncode}")
        rendered, evidence = _parse_jsonl(result.stdout, plugin["skills"])
        fidelity_check(brief, rendered)
    except (ClearWritingError, OSError, subprocess.SubprocessError) as exc:
        return {
            "mode": "DETERMINISTIC_FALLBACK",
            "text": fallback_text,
            "failure": f"{type(exc).__name__}: {exc}",
            "model_invocations": 1,
            "model_retry_count": 0,
            "plugin": plugin,
        }
    return {
        "mode": "NORMAL_WRITING_STYLE",
        "text": rendered,
        "failure": "",
        "model_invocations": 1,
        "model_retry_count": 0,
        "plugin": plugin,
        "jsonl_evidence": evidence,
    }
