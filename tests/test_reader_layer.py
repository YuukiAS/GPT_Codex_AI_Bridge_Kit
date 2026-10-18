from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
                    {"name": name, "path": str(self.root / "writing-style" / name / "SKILL.md"), "pluginId": reader_layer.WRITING_PLUGIN_ID}
                    for name in reader_layer.REQUIRED_READER_SKILLS
                ]
            }
        if method == "thread/start":
            self.thread_count += 1
            thread_id = f"thread-{self.thread_count}"
            self.injected.setdefault(thread_id, [])
            return {"thread": {"id": thread_id}}
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
