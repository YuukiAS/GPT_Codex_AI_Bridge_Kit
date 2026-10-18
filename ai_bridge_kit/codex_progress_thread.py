from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any


class AppServerError(RuntimeError):
    pass


class JsonRpcProxy:
    """Small JSONL client for an already-running official Codex app-server."""

    def __init__(self, *, codex: str = "codex", socket_path: Path | None = None) -> None:
        command = [codex, "app-server", "proxy"]
        if socket_path is not None:
            command.extend(["--sock", socket_path.expanduser().resolve().as_posix()])
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._next_id = 1
        self._lock = threading.Lock()
        self.notifications: list[dict[str, Any]] = []
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "ai-bridge-kit", "title": "AI Bridge Kit", "version": "0.11.0"},
                "capabilities": {"experimentalApi": True},
            },
        )

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def __enter__(self) -> "JsonRpcProxy":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _read_message(self) -> dict[str, Any]:
        assert self._process.stdout is not None
        raw = self._process.stdout.readline()
        if not raw:
            stderr = self._process.stderr.read().strip() if self._process.stderr is not None else ""
            raise AppServerError(f"app-server proxy closed: {stderr}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AppServerError(f"invalid app-server JSON: {raw.rstrip()}") from exc
        if not isinstance(payload, dict):
            raise AppServerError("app-server message must be an object")
        return payload

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            assert self._process.stdin is not None
            self._process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
            self._process.stdin.flush()
            while True:
                message = self._read_message()
                if message.get("id") != request_id:
                    self.notifications.append(message)
                    continue
                if "error" in message:
                    raise AppServerError(f"{method} failed: {message['error']}")
                result = message.get("result", {})
                if not isinstance(result, dict):
                    raise AppServerError(f"{method} returned a non-object result")
                return result

    def wait_notification(self, method: str, *, thread_id: str, turn_id: str) -> dict[str, Any]:
        while True:
            message = self._read_message()
            if message.get("method") != method:
                self.notifications.append(message)
                continue
            params = message.get("params", {})
            if params.get("threadId") == thread_id and params.get("turn", {}).get("id") == turn_id:
                return params
            self.notifications.append(message)


def _thread_id(response: dict[str, Any]) -> str:
    thread_id = str(response.get("thread", {}).get("id") or "")
    if not thread_id:
        raise AppServerError("thread response omitted thread.id")
    return thread_id


def start_progress_display_thread(app: Any, *, neutral_cwd: Path) -> str:
    request = {
        "cwd": neutral_cwd.expanduser().resolve().as_posix(),
        "ephemeral": False,
        "dynamicTools": [],
        "environments": [],
        "runtimeWorkspaceRoots": [],
        "selectedCapabilityRoots": [],
        "approvalPolicy": "never",
        "sandbox": "read-only",
        "baseInstructions": "This is a display-only Progress thread. Do not run model turns or tools.",
        "developerInstructions": "Accept only assistant items injected by the Bridge reporter.",
        "multiAgentMode": "none",
    }
    response = app.request(
        "thread/start",
        request,
    )
    # The official response exposes the effective values that can be verified
    # without starting a model turn. Anything less fails closed.
    if response.get("approvalPolicy") not in {None, "never"}:
        raise AppServerError("progress thread approval policy is not tool-free")
    if response.get("runtimeWorkspaceRoots", []) != []:
        raise AppServerError("progress thread runtime workspace roots are not empty")
    if response.get("instructionSources", []) not in (None, []):
        raise AppServerError("progress thread loaded instruction sources")
    if response.get("multiAgentMode") not in {None, "none"}:
        raise AppServerError("progress thread multi-agent mode is not none")
    return _thread_id(response)


def inject_progress_text(app: Any, *, thread_id: str, text: str) -> None:
    if not text.strip():
        raise AppServerError("progress injection text must be non-empty")
    app.request(
        "thread/inject_items",
        {
            "threadId": thread_id,
            "items": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text.strip()}],
                }
            ],
        },
    )


def read_progress_thread(app: Any, *, thread_id: str) -> dict[str, Any]:
    return app.request("thread/read", {"threadId": thread_id, "includeTurns": True})


def resume_progress_thread(app: Any, *, thread_id: str) -> dict[str, Any]:
    response = app.request("thread/resume", {"threadId": thread_id})
    if _thread_id(response) != thread_id:
        raise AppServerError("exact progress thread ID reconnect failed")
    return response


def injected_assistant_texts(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "agentMessage" and isinstance(value.get("text"), str):
                texts.append(value["text"])
            if value.get("role") == "assistant":
                for content in value.get("content", []):
                    if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                        text = content.get("text")
                        if isinstance(text, str):
                            texts.append(text)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
    return texts
