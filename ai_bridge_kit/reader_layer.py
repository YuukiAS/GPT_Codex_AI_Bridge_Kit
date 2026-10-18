from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import notifier
from .codex_progress_thread import AppServerError, inject_progress_text


WRITING_PLUGIN_ID = "writing-style@yuukias-ai-skills"
REQUIRED_READER_SKILLS = ("chinese-prose", "writing-fidelity")
READER_TEXT_MAX_BYTES = 4096
READER_MULTI_AGENT_MODE = {"custom": "Never delegate to sub-agents in this reader thread."}


class ReaderLayerError(RuntimeError):
    pass


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_dicts(nested)


def resolve_writing_skills(
    plugin_list: dict[str, Any],
    skills_list: dict[str, Any],
) -> dict[str, dict[str, str]]:
    plugin: dict[str, Any] | None = None
    for item in _walk_dicts(plugin_list):
        if item.get("id") == WRITING_PLUGIN_ID:
            plugin = item
            break
    if plugin is None or plugin.get("installed") is not True or plugin.get("enabled") is not True:
        raise ReaderLayerError("WRITING_STYLE_PLUGIN_UNAVAILABLE")
    result: dict[str, dict[str, str]] = {}
    for item in _walk_dicts(skills_list):
        actual_name = item.get("name")
        raw_path = item.get("path")
        if not isinstance(actual_name, str) or not isinstance(raw_path, str):
            continue
        logical_name = actual_name.removeprefix("writing-style:")
        if logical_name not in REQUIRED_READER_SKILLS:
            continue
        plugin_id = item.get("pluginId") or item.get("plugin_id")
        if plugin_id != WRITING_PLUGIN_ID:
            continue
        result[logical_name] = {
            "name": actual_name,
            "path": Path(raw_path).expanduser().resolve().as_posix(),
        }
    missing = [name for name in REQUIRED_READER_SKILLS if name not in result]
    if missing:
        raise ReaderLayerError("WRITING_STYLE_SKILLS_UNAVAILABLE: " + ",".join(missing))
    return result


def writing_plugin_version(plugin_list: dict[str, Any]) -> str:
    for item in _walk_dicts(plugin_list):
        if item.get("id") == WRITING_PLUGIN_ID:
            value = item.get("localVersion") or item.get("version")
            if isinstance(value, str) and value.strip():
                return value.strip()
            manifest = item.get("manifest")
            if isinstance(manifest, dict) and isinstance(manifest.get("version"), str):
                return manifest["version"].strip() or "UNKNOWN"
    return "UNKNOWN"


def reader_turn_input(
    event: dict[str, Any],
    *,
    language: str,
    skills: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    if event.get("schema") != notifier.CANONICAL_EVENT_SCHEMA:
        raise ReaderLayerError("CANONICAL_NOTIFICATION_EVENT_REQUIRED")
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prompt = (
        "Render the canonical notification event below for the user. Preserve every fact and claim boundary. "
        "Use 2-5 natural sentences, add no facts, and do not claim semantic completion for runtime-only events.\n"
        f"Language preference: {language}\n"
        f"Canonical event: {canonical}"
    )
    if len(prompt.encode("utf-8")) > READER_TEXT_MAX_BYTES:
        raise ReaderLayerError("READER_INPUT_BUDGET_EXCEEDED")
    return [
        {"type": "text", "text": prompt},
        *[
            {"type": "skill", "name": skills[name]["name"], "path": skills[name]["path"]}
            for name in REQUIRED_READER_SKILLS
        ],
    ]


def _assistant_text(value: Any) -> str:
    candidates: list[str] = []
    for item in _walk_dicts(value):
        if item.get("type") == "agentMessage" and isinstance(item.get("text"), str) and item["text"].strip():
            candidates.append(item["text"].strip())
        if item.get("role") != "assistant":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    candidates.append(text.strip())
    if not candidates:
        raise ReaderLayerError("READER_RESULT_MISSING")
    return candidates[-1]


def fidelity_check(event: dict[str, Any], rendered: str, turn_payload: dict[str, Any]) -> None:
    if not rendered.strip() or len(rendered.encode("utf-8")) > READER_TEXT_MAX_BYTES:
        raise ReaderLayerError("READER_RESULT_BUDGET_OR_EMPTY")
    for item in _walk_dicts(turn_payload):
        item_type = str(item.get("type") or "")
        if item_type in {"function_call", "local_shell_call", "web_search_call", "mcp_tool_call"}:
            raise ReaderLayerError("READER_USED_TOOL")
    if event.get("event_class") == "runtime_terminal":
        forbidden = ("RELEASE_READY", "Goal PASS", "目标已完成", "发布就绪")
        if any(token.lower() in rendered.lower() for token in forbidden):
            raise ReaderLayerError("READER_WEAKENED_RUNTIME_CLAIM_BOUNDARY")
    protected_text = " ".join(
        str(event.get(key) or "")
        for key in ["status", "key_conclusion", "terminal_status", "exit_code"]
    )
    status = str(event.get("status") or "").strip()
    if status and status.lower() not in rendered.lower():
        raise ReaderLayerError("READER_FIDELITY_STATUS_MISSING")
    for number in sorted(set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", protected_text))):
        if number not in rendered:
            raise ReaderLayerError(f"READER_FIDELITY_NUMBER_MISSING: {number}")
    if "UNKNOWN" in protected_text and "UNKNOWN" not in rendered:
        raise ReaderLayerError("READER_FIDELITY_UNKNOWN_MISSING")


def validate_reader_thread(response: dict[str, Any]) -> None:
    thread = response.get("thread", {})
    if thread.get("ephemeral") is not True:
        raise ReaderLayerError("READER_THREAD_NOT_EPHEMERAL")
    if thread.get("environments") != []:
        raise ReaderLayerError("READER_ENVIRONMENTS_NOT_EMPTY")
    if response.get("approvalPolicy") != "never":
        raise ReaderLayerError("READER_APPROVAL_POLICY_NOT_NEVER")
    if response.get("runtimeWorkspaceRoots") != []:
        raise ReaderLayerError("READER_RUNTIME_ROOTS_NOT_EMPTY")
    instruction_sources = response.get("instructionSources")
    if instruction_sources != []:
        raise ReaderLayerError(
            "READER_INSTRUCTION_SOURCES_NOT_EMPTY: "
            + json.dumps(instruction_sources, ensure_ascii=False, separators=(",", ":"))
        )
    if response.get("multiAgentMode") != READER_MULTI_AGENT_MODE:
        raise ReaderLayerError("READER_MULTI_AGENT_MODE_NOT_DISABLED")
    sandbox = response.get("sandbox")
    sandbox_ok = (
        isinstance(sandbox, dict)
        and sandbox.get("type") == "readOnly"
        and sandbox.get("networkAccess") is False
    )
    if not sandbox_ok:
        raise ReaderLayerError("READER_SANDBOX_NOT_READ_ONLY_NO_NETWORK")


def start_reader_thread(app: Any, *, neutral_cwd: Path) -> dict[str, Any]:
    response = app.request(
        "thread/start",
        {
            "cwd": neutral_cwd.expanduser().resolve().as_posix(),
            "ephemeral": True,
            "dynamicTools": [],
            "environments": [],
            "runtimeWorkspaceRoots": [],
            "selectedCapabilityRoots": [],
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "baseInstructions": "Render only the supplied event. Do not use tools or infer missing facts.",
            "developerInstructions": "Return only the user-facing notification text.",
            "multiAgentMode": READER_MULTI_AGENT_MODE,
        },
    )
    validate_reader_thread(response)
    if not str(response.get("thread", {}).get("id") or ""):
        raise ReaderLayerError("READER_THREAD_ID_MISSING")
    return response


def preflight_reader_isolation(app: Any, *, neutral_cwd: Path) -> dict[str, Any]:
    """Start and validate an ephemeral zero-turn reader before allocating display state."""
    return start_reader_thread(app, neutral_cwd=neutral_cwd)


def render_event(
    app: Any,
    *,
    event: dict[str, Any],
    neutral_cwd: Path,
    language: str,
    reader_turns_used: int,
    reader_render_max_turns: int,
    progress_thread_id: str | None = None,
) -> dict[str, Any]:
    if reader_render_max_turns < 0 or reader_turns_used < 0:
        raise ReaderLayerError("READER_TURN_BUDGET_INVALID")
    mode = "NORMAL_WRITING_STYLE"
    rendered: str
    reader_thread_id = ""
    used_model_turn = False
    plugin_version = "UNKNOWN"
    selected_skills: dict[str, dict[str, str]] = {}
    try:
        if reader_turns_used >= reader_render_max_turns:
            raise ReaderLayerError("READER_TURN_BUDGET_EXHAUSTED")
        plugins = app.request("plugin/list", {"cwds": [neutral_cwd.expanduser().resolve().as_posix()]})
        skills_payload = app.request(
            "skills/list",
            {"cwds": [neutral_cwd.expanduser().resolve().as_posix()], "forceReload": False},
        )
        skills = resolve_writing_skills(plugins, skills_payload)
        selected_skills = skills
        plugin_version = writing_plugin_version(plugins)
        thread = start_reader_thread(app, neutral_cwd=neutral_cwd)
        reader_thread_id = str(thread.get("thread", {}).get("id") or "")
        turn = app.request(
            "turn/start",
            {
                "threadId": reader_thread_id,
                "cwd": neutral_cwd.expanduser().resolve().as_posix(),
                "environments": [],
                "multiAgentMode": {"custom": "Never delegate to sub-agents in this reader turn."},
                "input": reader_turn_input(event, language=language, skills=skills),
            },
        )
        turn_id = str(turn.get("turn", {}).get("id") or "")
        if not turn_id:
            raise ReaderLayerError("READER_TURN_ID_MISSING")
        used_model_turn = True
        completed = app.wait_notification(
            "turn/completed",
            thread_id=reader_thread_id,
            turn_id=turn_id,
        )
        rendered = _assistant_text(completed)
        fidelity_check(event, rendered, completed)
    except (ReaderLayerError, AppServerError, OSError, ValueError) as exc:
        mode = "DEGRADED_FALLBACK"
        rendered = notifier.deterministic_fallback(event, language=language)
        failure = f"{type(exc).__name__}: {exc}"
    else:
        failure = ""
    display_injection_state = "NOT_REQUESTED"
    if progress_thread_id:
        try:
            inject_progress_text(app, thread_id=progress_thread_id, text=rendered)
            display_injection_state = "INJECTED"
        except (AppServerError, OSError, ValueError) as exc:
            display_injection_state = "FAILED"
            failure = "; ".join(item for item in [failure, f"DISPLAY_INJECTION_FAILED: {exc}"] if item)
    return {
        "reader_layer": mode,
        "text": rendered,
        "reader_thread_id": reader_thread_id,
        "model_turn_used": used_model_turn,
        "reader_turns_used": reader_turns_used + (1 if used_model_turn else 0),
        "failure": failure,
        "progress_thread_id": progress_thread_id or "",
        "plugin_id": WRITING_PLUGIN_ID,
        "plugin_version": plugin_version,
        "skills": selected_skills,
        "display_injection_state": display_injection_state,
    }
