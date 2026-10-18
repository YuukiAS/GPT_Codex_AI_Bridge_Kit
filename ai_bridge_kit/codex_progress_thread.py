from __future__ import annotations

import base64
import hashlib
import json
import os
import select
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class AppServerError(RuntimeError):
    pass


class JsonRpcProxy:
    """Small WebSocket client for an already-running official Codex app-server.

    ``codex app-server proxy`` is a byte relay to the app-server Unix socket.
    Unix-socket app-server listeners still speak RFC 6455 rather than JSONL, so
    the Bridge must perform the WebSocket handshake and frame JSON-RPC messages.
    """

    def __init__(self, *, codex: str = "codex", socket_path: Path | None = None) -> None:
        command = [codex, "app-server", "proxy"]
        if socket_path is not None:
            command.extend(["--sock", socket_path.expanduser().resolve().as_posix()])
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._next_id = 1
        self._lock = threading.Lock()
        self._read_deadline: float | None = time.monotonic() + 15
        self.notifications: list[dict[str, Any]] = []
        try:
            self._handshake()
            self.request(
                "initialize",
                {
                    "clientInfo": {"name": "ai-bridge-kit", "title": "AI Bridge Kit", "version": "0.11.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self._write_message({"method": "initialized"})
        except Exception:
            self.close()
            raise
        finally:
            self._read_deadline = None

    def close(self) -> None:
        if self._process.poll() is None:
            try:
                self._write_frame(b"", opcode=0x8)
            except (BrokenPipeError, OSError):
                pass
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def __enter__(self) -> "JsonRpcProxy":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _stderr_text(self) -> str:
        if self._process.poll() is None or self._process.stderr is None:
            return ""
        return self._process.stderr.read().decode("utf-8", errors="replace").strip()

    def _read_exact(self, size: int) -> bytes:
        assert self._process.stdout is not None
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            if self._read_deadline is not None and os.name != "nt":
                timeout = self._read_deadline - time.monotonic()
                if timeout <= 0 or not select.select([self._process.stdout], [], [], timeout)[0]:
                    raise AppServerError("app-server proxy timed out")
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                raise AppServerError(f"app-server proxy closed: {self._stderr_text()}")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _handshake(self) -> None:
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            "GET /rpc HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        assert self._process.stdin is not None
        self._process.stdin.write(request)
        self._process.stdin.flush()
        response = bytearray()
        while not response.endswith(b"\r\n\r\n"):
            response.extend(self._read_exact(1))
            if len(response) > 16384:
                raise AppServerError("app-server WebSocket handshake headers are too large")
        header_lines = response.decode("iso-8859-1").split("\r\n")
        if not header_lines or " 101 " not in f" {header_lines[0]} ":
            raise AppServerError(f"app-server WebSocket handshake failed: {header_lines[0] if header_lines else ''}")
        headers: dict[str, str] = {}
        for line in header_lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if headers.get("sec-websocket-accept") != expected:
            raise AppServerError("app-server WebSocket handshake accept mismatch")

    def _write_frame(self, payload: bytes, *, opcode: int = 0x1) -> None:
        assert self._process.stdin is not None
        mask = secrets.token_bytes(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self._process.stdin.write(bytes(header) + mask + masked)
        self._process.stdin.flush()

    def _read_frame(self) -> tuple[int, bool, bytes]:
        first, second = self._read_exact(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = int.from_bytes(self._read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._read_exact(8), "big")
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return opcode, fin, payload

    def _read_message(self) -> dict[str, Any]:
        fragments = bytearray()
        message_opcode: int | None = None
        while True:
            opcode, fin, payload = self._read_frame()
            if opcode == 0x8:
                raise AppServerError("app-server WebSocket closed")
            if opcode == 0x9:
                self._write_frame(payload, opcode=0xA)
                continue
            if opcode == 0xA:
                continue
            if opcode in {0x1, 0x2}:
                message_opcode = opcode
                fragments = bytearray(payload)
            elif opcode == 0x0 and message_opcode is not None:
                fragments.extend(payload)
            else:
                raise AppServerError(f"unsupported app-server WebSocket opcode: {opcode}")
            if not fin:
                continue
            if message_opcode != 0x1:
                raise AppServerError("app-server returned a non-text WebSocket message")
            raw = bytes(fragments).decode("utf-8")
            break
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AppServerError(f"invalid app-server JSON: {raw}") from exc
        if not isinstance(payload, dict):
            raise AppServerError("app-server message must be an object")
        return payload

    def _write_message(self, payload: dict[str, Any]) -> None:
        self._write_frame(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._write_message({"id": request_id, "method": method, "params": params})
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
        "multiAgentMode": {"custom": "Never delegate to sub-agents in this display-only thread."},
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
    instruction_sources = response.get("instructionSources", [])
    if instruction_sources not in (None, []):
        raise AppServerError(
            "progress thread loaded instruction sources: "
            + json.dumps(instruction_sources, ensure_ascii=False, separators=(",", ":"))
        )
    effective_multi_agent = response.get("multiAgentMode")
    if effective_multi_agent not in (None, {"custom": "Never delegate to sub-agents in this display-only thread."}):
        raise AppServerError("progress thread multi-agent mode is not disabled")
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
