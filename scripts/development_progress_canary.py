#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_bridge_kit import notifier, reader_layer
from ai_bridge_kit.codex_progress_thread import (
    JsonRpcProxy,
    injected_assistant_texts,
    read_progress_thread,
    resume_progress_thread,
    start_progress_display_thread,
)


TASK_KEY = "bridge-core--execution-context-readiness-convergence"
CANARY_SCHEMA = "ai-bridge.development_progress_canary.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest_texts(texts: list[str]) -> str:
    canonical = json.dumps(texts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecordingProxy(JsonRpcProxy):
    def __init__(self, **kwargs: Any) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        super().__init__(**kwargs)

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((method, params))
        return super().request(method, params)


def progress_event(number: int, evidence_path: str) -> dict[str, Any]:
    return notifier.canonical_event(
        event_class="progress",
        project="GPT_Codex_AI_Bridge_Kit",
        task_key=TASK_KEY,
        status=f"DEVELOPMENT_CANARY_STAGE_{number}",
        key_conclusion=f"Development reader canary stage {number} completed without a final acceptance claim.",
        next_step="Continue development evidence collection; final G01-G14 gates remain unstarted.",
        evidence_paths=[evidence_path],
        emitter="development_progress_canary",
        runtime_id="development-progress-canary-0.11.0",
        lifecycle_owner="development_progress_canary",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.expanduser().resolve()
    require(not output.exists(), f"refusing to overwrite existing canary evidence: {output}")
    neutral_cwd = args.neutral_cwd.expanduser().resolve()
    neutral_cwd.mkdir(parents=True, exist_ok=True)
    executor_thread_id = args.executor_thread_id.strip()
    require(bool(executor_thread_id), "executor thread id is required")
    evidence_rel = output.relative_to(args.repo_root.expanduser().resolve()).as_posix()
    started_at = utc_now()

    with RecordingProxy(codex=args.codex, socket_path=args.socket) as writer:
        executor_before = read_progress_thread(writer, thread_id=executor_thread_id)
        executor_before_texts = injected_assistant_texts(executor_before)
        reader_preflight = reader_layer.preflight_reader_isolation(writer, neutral_cwd=neutral_cwd)
        display_thread_id = start_progress_display_thread(writer, neutral_cwd=neutral_cwd)

        first = reader_layer.render_event(
            writer,
            event=progress_event(1, evidence_rel),
            neutral_cwd=neutral_cwd,
            language="zh-CN",
            reader_turns_used=0,
            reader_render_max_turns=2,
            progress_thread_id=display_thread_id,
        )
        require(first["reader_layer"] == "NORMAL_WRITING_STYLE", f"first reader failed: {first['failure']}")
        require(first["model_turn_used"] is True, "first reader did not use its single model turn")
        require(first["display_injection_state"] == "INJECTED", "first display injection failed")

        with RecordingProxy(codex=args.codex, socket_path=args.socket) as viewer:
            first_view = read_progress_thread(viewer, thread_id=display_thread_id)
            first_view_texts = injected_assistant_texts(first_view)
            require(first["text"] in first_view_texts, "viewer could not see the first injected message")

            second = reader_layer.render_event(
                writer,
                event=progress_event(2, evidence_rel),
                neutral_cwd=neutral_cwd,
                language="zh-CN",
                reader_turns_used=first["reader_turns_used"],
                reader_render_max_turns=2,
                progress_thread_id=display_thread_id,
            )
            require(second["reader_layer"] == "NORMAL_WRITING_STYLE", f"second reader failed: {second['failure']}")
            require(second["model_turn_used"] is True, "second reader did not use its single model turn")
            require(second["display_injection_state"] == "INJECTED", "second display injection failed")
            require(first["reader_thread_id"] != second["reader_thread_id"], "reader threads were reused")
            require(second["reader_turns_used"] == 2, "reader turn ceiling was not accounted exactly")

            open_view = read_progress_thread(viewer, thread_id=display_thread_id)
            open_view_texts = injected_assistant_texts(open_view)
            require(first["text"] in open_view_texts, "first message disappeared while viewer remained open")
            require(second["text"] in open_view_texts, "viewer could not see reporter's second injection")

        turn_inputs = [params["input"] for method, params in writer.requests if method == "turn/start"]
        require(len(turn_inputs) == 2, "development canary did not use exactly two reader turns")
        require(all([item.get("type") for item in value] == ["text", "skill", "skill"] for value in turn_inputs),
                "reader input did not contain exactly canonical text plus two structured skills")
        require(first["text"] not in turn_inputs[1][0]["text"], "second reader inherited first rendered history")

    with RecordingProxy(codex=args.codex, socket_path=args.socket) as cold:
        resumed = resume_progress_thread(cold, thread_id=display_thread_id)
        cold_view = read_progress_thread(cold, thread_id=display_thread_id)
        cold_texts = injected_assistant_texts(cold_view)
        require(first["text"] in cold_texts and second["text"] in cold_texts,
                "exact-ID cold resume did not preserve both normal messages")

        fallback = reader_layer.render_event(
            cold,
            event=progress_event(3, evidence_rel),
            neutral_cwd=neutral_cwd,
            language="zh-CN",
            reader_turns_used=2,
            reader_render_max_turns=2,
            progress_thread_id=display_thread_id,
        )
        require(fallback["reader_layer"] == "DEGRADED_FALLBACK", "budget exhaustion did not select fallback")
        require(fallback["model_turn_used"] is False, "fallback unexpectedly used a model turn")
        require("READER_TURN_BUDGET_EXHAUSTED" in fallback["failure"], "fallback reason is not budget exhaustion")
        require(fallback["display_injection_state"] == "INJECTED", "fallback display injection failed")
        final_view = read_progress_thread(cold, thread_id=display_thread_id)
        final_texts = injected_assistant_texts(final_view)
        require(all(text in final_texts for text in [first["text"], second["text"], fallback["text"]]),
                "normal/fallback messages are not all durable")

        executor_after = read_progress_thread(cold, thread_id=executor_thread_id)
        executor_after_texts = injected_assistant_texts(executor_after)
        require(not any(text in executor_after_texts for text in [first["text"], second["text"], fallback["text"]]),
                "development progress text leaked into the Executor thread")

    require(first["plugin_id"] == reader_layer.WRITING_PLUGIN_ID, "wrong writing plugin identity")
    require(second["plugin_id"] == reader_layer.WRITING_PLUGIN_ID, "wrong second writing plugin identity")
    expected_skills = set(reader_layer.REQUIRED_READER_SKILLS)
    require(set(first["skills"]) == expected_skills and set(second["skills"]) == expected_skills,
            "required writing skills were not resolved")

    return {
        "schema": CANARY_SCHEMA,
        "task_key": TASK_KEY,
        "status": "PASS",
        "started_at": started_at,
        "ended_at": utc_now(),
        "codex_executable": Path(args.codex).expanduser().resolve().as_posix(),
        "app_server_socket": args.socket.expanduser().resolve().as_posix(),
        "neutral_cwd": neutral_cwd.as_posix(),
        "executor_thread_id": executor_thread_id,
        "executor_thread_untouched": True,
        "executor_before_text_digest": digest_texts(executor_before_texts),
        "executor_after_text_digest": digest_texts(executor_after_texts),
        "progress_thread_id": display_thread_id,
        "progress_thread_non_ephemeral": True,
        "progress_thread_tool_free": True,
        "same_shared_app_server": True,
        "reader_preflight_thread_id": reader_preflight["thread"]["id"],
        "reader_preflight_model_turns": 0,
        "reader_preflight_before_display_allocation": True,
        "viewer_open_during_second_injection": True,
        "exact_id_cold_resume": resumed.get("thread", {}).get("id") == display_thread_id,
        "durable_messages": len({first["text"], second["text"], fallback["text"]}),
        "reader_render_max_turns": 2,
        "reader_turns_used": second["reader_turns_used"],
        "fresh_reader_thread_ids": [first["reader_thread_id"], second["reader_thread_id"]],
        "reader_threads_distinct": first["reader_thread_id"] != second["reader_thread_id"],
        "reader_input_contains_progress_history": False,
        "plugin_id": first["plugin_id"],
        "plugin_version": first["plugin_version"],
        "skills": first["skills"],
        "normal_deliveries": [
            {"reader_layer": first["reader_layer"], "text": first["text"], "injection": first["display_injection_state"]},
            {"reader_layer": second["reader_layer"], "text": second["text"], "injection": second["display_injection_state"]},
        ],
        "fallback_delivery": {
            "reader_layer": fallback["reader_layer"],
            "model_turn_used": fallback["model_turn_used"],
            "reason": fallback["failure"],
            "text": fallback["text"],
            "injection": fallback["display_injection_state"],
        },
        "final_g01_g14_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded 0.11.0 development Progress/Clear Writing canary.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--neutral-cwd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executor-thread-id", required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--codex", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        result = {
            "schema": CANARY_SCHEMA,
            "task_key": TASK_KEY,
            "status": "FAIL_CLOSED",
            "ended_at": utc_now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "final_g01_g14_started": False,
        }
        exit_code = 1
    else:
        exit_code = 0
    args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.expanduser().resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
