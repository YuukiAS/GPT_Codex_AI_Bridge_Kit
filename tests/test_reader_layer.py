from __future__ import annotations

import base64
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import codex_progress_thread, notifier, reader_layer


class FakeApp:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.requests: list[tuple[str, dict]] = []
        self.thread_count = 0
        self.turn_count = 0
        self.injected: dict[str, list[str]] = {}

    def request(self, method: str, params: dict):
        self.requests.append((method, params))
        if method == "plugin/list":
            return {
                "marketplaces": [
                    {
                        "plugins": [
                            {
                                "id": reader_layer.WRITING_PLUGIN_ID,
                                "installed": True,
                                "enabled": True,
                                "localVersion": "0.4",
                                "source": {"type": "local", "path": str(self.root / "writing-style")},
                            }
                        ]
                    }
                ]
            }
        if method == "skills/list":
            return {
                "skills": [
                    {
                        "name": f"writing-style:{name}",
                        "path": str(self.root / "plugin-cache" / name / "SKILL.md"),
                        "pluginId": reader_layer.WRITING_PLUGIN_ID,
                    }
                    for name in reader_layer.REQUIRED_READER_SKILLS
                ]
            }
        if method == "thread/start":
            self.thread_count += 1
            thread_id = f"thread-{self.thread_count}"
            self.injected.setdefault(thread_id, [])
            return {
                "thread": {
                    "id": thread_id,
                    "ephemeral": params.get("ephemeral"),
                    "environments": params.get("environments", []),
                },
                "approvalPolicy": params.get("approvalPolicy"),
                "runtimeWorkspaceRoots": params.get("runtimeWorkspaceRoots", []),
                "instructionSources": [],
                "multiAgentMode": params.get("multiAgentMode"),
                "sandbox": {"type": "readOnly", "networkAccess": False},
            }
        if method == "turn/start":
            self.turn_count += 1
            return {"turn": {"id": f"turn-{self.turn_count}"}}
        if method == "thread/inject_items":
            text = params["items"][0]["content"][0]["text"]
            self.injected.setdefault(params["threadId"], []).append(text)
            return {}
        if method == "thread/read":
            return {
                "thread": {
                    "id": params["threadId"],
                    "turns": [
                        {
                            "items": [
                                {
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": text}],
                                }
                            ]
                        }
                        for text in self.injected.get(params["threadId"], [])
                    ],
                }
            }
        if method == "thread/resume":
            return {"thread": {"id": params["threadId"]}}
        raise AssertionError(method)

    def wait_notification(self, method: str, *, thread_id: str, turn_id: str):
        self.requests.append((method, {"threadId": thread_id, "turnId": turn_id}))
        return {
            "threadId": thread_id,
            "turn": {
                "id": turn_id,
                "items": [
                    {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": f"状态 stage-{self.turn_count}，已完成真实阶段 {self.turn_count}。"}],
                    }
                ],
            },
        }


def event(number: int = 1) -> dict:
    return notifier.canonical_event(
        event_class="progress",
        project="demo",
        task_key="repo--task",
        status=f"stage-{number}",
        key_conclusion=f"完成真实阶段 {number}。",
        next_step="继续观察。",
        evidence_paths=[f"results/progress-{number}.json"],
        emitter="persistent_supervisor",
        runtime_id="runtime-1",
        lifecycle_owner="persistent_supervisor",
    )


class ReaderLayerTests(unittest.TestCase):
    def test_display_thread_accepts_machine_instructions_without_model_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            original = app.request

            def with_instructions(method: str, params: dict):
                response = original(method, params)
                if method == "thread/start":
                    response["instructionSources"] = ["/selected-codex-home/AGENTS.md"]
                return response

            app.request = with_instructions  # type: ignore[method-assign]
            display = codex_progress_thread.start_progress_display_thread(app, neutral_cwd=root)
            self.assertEqual(display, "thread-1")
            self.assertEqual(app.turn_count, 0)

    def test_reader_instruction_source_fails_before_model_turn_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            original = app.request

            def with_instructions(method: str, params: dict):
                response = original(method, params)
                if method == "thread/start" and params.get("ephemeral"):
                    response["instructionSources"] = ["/selected-codex-home/AGENTS.md"]
                return response

            app.request = with_instructions  # type: ignore[method-assign]
            result = reader_layer.render_event(
                app,
                event=event(),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=0,
                reader_render_max_turns=2,
            )
            self.assertEqual(result["reader_layer"], "DEGRADED_FALLBACK")
            self.assertIn("READER_INSTRUCTION_SOURCES_NOT_EMPTY", result["failure"])
            self.assertFalse(result["model_turn_used"])
            self.assertEqual(app.turn_count, 0)

    def test_reader_multi_agent_surface_fails_before_model_turn_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            original = app.request

            def with_multi_agent_surface(method: str, params: dict):
                response = original(method, params)
                if method == "thread/start" and params.get("ephemeral"):
                    response["multiAgentMode"] = "explicitRequestOnly"
                return response

            app.request = with_multi_agent_surface  # type: ignore[method-assign]
            result = reader_layer.render_event(
                app,
                event=event(),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=0,
                reader_render_max_turns=2,
            )
            self.assertEqual(result["reader_layer"], "DEGRADED_FALLBACK")
            self.assertIn("READER_MULTI_AGENT_MODE_NOT_DISABLED", result["failure"])
            self.assertFalse(result["model_turn_used"])
            self.assertEqual(app.turn_count, 0)

    def test_reader_preflight_runs_before_display_without_model_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            preflight = reader_layer.preflight_reader_isolation(app, neutral_cwd=root)
            display = codex_progress_thread.start_progress_display_thread(app, neutral_cwd=root)
            starts = [(method, params) for method, params in app.requests if method == "thread/start"]
            self.assertTrue(preflight["thread"]["ephemeral"])
            self.assertEqual(display, "thread-2")
            self.assertTrue(starts[0][1]["ephemeral"])
            self.assertFalse(starts[1][1]["ephemeral"])
            self.assertEqual(app.turn_count, 0)

    def test_json_rpc_proxy_uses_websocket_handshake_and_masked_frames(self) -> None:
        websocket_key = bytes(range(16))
        encoded_key = base64.b64encode(websocket_key).decode("ascii")
        accept = base64.b64encode(
            hashlib.sha1(
                (encoded_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        initialize_result = json.dumps(
            {"id": 1, "result": {}}, separators=(",", ":")
        ).encode("utf-8")
        server_frame = bytes([0x81, len(initialize_result)]) + initialize_result

        class FakeProcess:
            def __init__(self) -> None:
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO(
                    (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                    ).encode("ascii")
                    + server_frame
                )
                self.stderr = io.BytesIO()
                self.running = True

            def poll(self):
                return None if self.running else 0

            def terminate(self) -> None:
                self.running = False

            def wait(self, timeout: int) -> int:
                return 0

            def kill(self) -> None:
                self.running = False

        process = FakeProcess()
        random_bytes = [websocket_key, b"mask", b"mask", b"mask"]
        with (
            mock.patch.object(codex_progress_thread.subprocess, "Popen", return_value=process),
            mock.patch.object(codex_progress_thread.select, "select", return_value=([process.stdout], [], [])),
            mock.patch.object(codex_progress_thread.secrets, "token_bytes", side_effect=random_bytes),
        ):
            proxy = codex_progress_thread.JsonRpcProxy(codex="codex")
            proxy.close()

        written = process.stdin.getvalue()
        self.assertIn(b"GET /rpc HTTP/1.1\r\n", written)
        self.assertIn(f"Sec-WebSocket-Key: {encoded_key}\r\n".encode("ascii"), written)
        frame_start = written.index(b"\r\n\r\n") + 4
        self.assertEqual(written[frame_start] & 0x0F, 0x1)
        self.assertTrue(written[frame_start + 1] & 0x80)
        self.assertFalse(process.running)

    def test_display_delivery_runs_when_progress_email_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            display = codex_progress_thread.start_progress_display_thread(app, neutral_cwd=root)
            result = notifier.deliver_canonical_event(
                event(),
                intents={"progress_email": "DISABLED"},
                output_dir=root / "results" / "repo--task" / "notifications" / "progress",
                app=app,
                neutral_cwd=root,
                reader_render_max_turns=1,
                progress_thread_id=display,
            )
            self.assertEqual(result["status"], "disabled_by_frozen_intent")
            self.assertEqual(result["reader"]["display_injection_state"], "INJECTED")
            self.assertEqual(len(app.injected[display]), 1)

    def test_fresh_stateless_reader_and_persistent_display_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            display = codex_progress_thread.start_progress_display_thread(app, neutral_cwd=root)
            first = reader_layer.render_event(
                app,
                event=event(1),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=0,
                reader_render_max_turns=2,
                progress_thread_id=display,
            )
            second = reader_layer.render_event(
                app,
                event=event(2),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=first["reader_turns_used"],
                reader_render_max_turns=2,
                progress_thread_id=display,
            )

            self.assertEqual(first["reader_layer"], "NORMAL_WRITING_STYLE")
            self.assertEqual(second["reader_layer"], "NORMAL_WRITING_STYLE")
            self.assertEqual(first["plugin_id"], reader_layer.WRITING_PLUGIN_ID)
            self.assertEqual(first["plugin_version"], "0.4")
            reader_starts = [params for method, params in app.requests if method == "thread/start" and params.get("ephemeral")]
            self.assertEqual(len(reader_starts), 2)
            display_starts = [params for method, params in app.requests if method == "thread/start" and params.get("ephemeral") is False]
            self.assertEqual(display_starts[0]["runtimeWorkspaceRoots"], [])
            self.assertEqual(display_starts[0]["selectedCapabilityRoots"], [])
            self.assertEqual(display_starts[0]["approvalPolicy"], "never")
            turn_inputs = [params["input"] for method, params in app.requests if method == "turn/start"]
            self.assertEqual(len(turn_inputs), 2)
            self.assertNotIn("progress-1.json", turn_inputs[1][0]["text"])
            self.assertEqual([item["type"] for item in turn_inputs[0]], ["text", "skill", "skill"])
            self.assertEqual(
                [item["name"] for item in turn_inputs[0][1:]],
                ["writing-style:chinese-prose", "writing-style:writing-fidelity"],
            )
            self.assertEqual(len(app.injected[display]), 2)
            read = codex_progress_thread.read_progress_thread(app, thread_id=display)
            self.assertEqual(codex_progress_thread.injected_assistant_texts(read), app.injected[display])
            resumed = codex_progress_thread.resume_progress_thread(app, thread_id=display)
            self.assertEqual(resumed["thread"]["id"], display)

    def test_budget_exhaustion_uses_zero_model_fallback_and_injects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            display = codex_progress_thread.start_progress_display_thread(app, neutral_cwd=root)
            before = app.turn_count
            result = reader_layer.render_event(
                app,
                event=event(),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=2,
                reader_render_max_turns=2,
                progress_thread_id=display,
            )

            self.assertEqual(result["reader_layer"], "DEGRADED_FALLBACK")
            self.assertFalse(result["model_turn_used"])
            self.assertEqual(app.turn_count, before)
            self.assertEqual(app.injected[display], [result["text"]])

    def test_wrong_plugin_identity_degrades_without_copying_skill_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FakeApp(root)
            original = app.request

            def wrong(method: str, params: dict):
                payload = original(method, params)
                if method == "plugin/list":
                    payload["marketplaces"][0]["plugins"][0]["id"] = "other@vendor"
                return payload

            app.request = wrong  # type: ignore[method-assign]
            result = reader_layer.render_event(
                app,
                event=event(),
                neutral_cwd=root,
                language="zh-CN",
                reader_turns_used=0,
                reader_render_max_turns=2,
            )
            self.assertEqual(result["reader_layer"], "DEGRADED_FALLBACK")
            self.assertEqual(app.turn_count, 0)


if __name__ == "__main__":
    unittest.main()
