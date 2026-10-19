from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ai_bridge_kit import clear_writing, notifier


class FakeCodex:
    def __init__(self, plugin_root: Path, *, stdout: str | None = None, plugin_available: bool = True) -> None:
        self.plugin_root = plugin_root
        self.stdout = stdout or ""
        self.plugin_available = plugin_available
        self.plugin_calls = 0
        self.model_calls = 0

    def __call__(self, command, **_kwargs):
        if command[1:4] == ["plugin", "list", "--json"]:
            self.plugin_calls += 1
            plugins = []
            if self.plugin_available:
                plugins.append(
                    {
                        "id": clear_writing.WRITING_PLUGIN_ID,
                        "installed": True,
                        "enabled": True,
                        "version": "0.4.0",
                        "installedPath": self.plugin_root.as_posix(),
                    }
                )
            return SimpleNamespace(returncode=0, stdout=json.dumps({"plugins": plugins}), stderr="")
        if command[1:3] == ["exec", "--ephemeral"]:
            self.model_calls += 1
            return SimpleNamespace(returncode=0, stdout=self.stdout, stderr="")
        raise AssertionError(command)


class ClearWritingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plugin = self.root / "writing-style"
        manifest = self.plugin / ".codex-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"id": clear_writing.WRITING_PLUGIN_ID, "version": "0.4.0"}),
            encoding="utf-8",
        )
        self.skills = {
            "writing-fidelity": self.plugin / "skills" / "fidelity" / "SKILL.md",
            "chinese-prose": self.plugin / "skills" / "zh" / "SKILL.md",
        }
        for name, path in self.skills.items():
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: {name}\ndescription: test\n---\n# Test\n", encoding="utf-8")
        self.brief = {
            "schema": notifier.STRUCTURED_BRIEF_SCHEMA,
            "project": "Bridge 项目",
            "task_key": "repo--task",
            "event_type": "operational_blocked",
            "status": "blocked",
            "decision_authority": "Watcher",
            "key_conclusion": "运行已阻塞。",
            "next_step": "检查证据。",
            "evidence_paths": ["results/repo--task/RESULT.md"],
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def jsonl(self, text: str, *, turns: int = 1) -> str:
        events = [{"type": "thread.started"}]
        for _ in range(turns):
            events.append({"type": "turn.started"})
        for path in self.skills.values():
            events.append(
                {
                    "type": "item.completed",
                    "item": {"type": "command_execution", "command": f"sed -n 1,80p {path.resolve()}"},
                }
            )
        events.append({"type": "item.completed", "item": {"type": "agent_message", "text": text}})
        events.append({"type": "turn.completed"})
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n"

    def good_text(self) -> str:
        return (
            "Bridge 项目中的 repo--task 当前状态为 blocked。"
            "运行已阻塞，请检查证据。"
            "results/repo--task/RESULT.md"
        )

    def test_normal_path_uses_one_model_turn_and_both_exact_skills(self) -> None:
        fake = FakeCodex(self.plugin, stdout=self.jsonl(self.good_text()))
        result = clear_writing.render_once(
            self.brief,
            fallback_text="fallback",
            codex_bin="/usr/bin/codex",
            state_root=self.root / "state",
            runner=fake,
        )
        self.assertEqual(result["mode"], "NORMAL_WRITING_STYLE")
        self.assertEqual(result["model_invocations"], 1)
        self.assertEqual(result["model_retry_count"], 0)
        self.assertEqual(fake.model_calls, 1)
        self.assertTrue(all(result["jsonl_evidence"]["skill_consumed"].values()))

    def test_plugin_failure_uses_zero_model_fallback(self) -> None:
        fake = FakeCodex(self.plugin, plugin_available=False)
        result = clear_writing.render_once(
            self.brief,
            fallback_text="deterministic",
            codex_bin="/usr/bin/codex",
            state_root=self.root / "state",
            runner=fake,
        )
        self.assertEqual(result["mode"], "DETERMINISTIC_FALLBACK")
        self.assertEqual(result["text"], "deterministic")
        self.assertEqual(result["model_invocations"], 0)
        self.assertEqual(fake.model_calls, 0)

    def test_jsonl_turn_or_fidelity_failure_never_retries(self) -> None:
        cases = [
            self.jsonl(self.good_text(), turns=2),
            self.jsonl("缺少 exact facts"),
            "{not-json}\n",
        ]
        for stdout in cases:
            with self.subTest(stdout=stdout[:24]):
                fake = FakeCodex(self.plugin, stdout=stdout)
                result = clear_writing.render_once(
                    self.brief,
                    fallback_text="fallback",
                    codex_bin="/usr/bin/codex",
                    state_root=self.root / "state",
                    runner=fake,
                )
                self.assertEqual(result["mode"], "DETERMINISTIC_FALLBACK")
                self.assertEqual(result["model_invocations"], 1)
                self.assertEqual(result["model_retry_count"], 0)
                self.assertEqual(fake.model_calls, 1)

    def test_automatic_send_uses_adapter_but_manual_send_stays_legacy(self) -> None:
        brief_path = self.root / "brief.json"
        brief_path.write_text(json.dumps(self.brief), encoding="utf-8")
        captured: list[dict[str, object]] = []
        fake = FakeCodex(self.plugin, stdout=self.jsonl(self.good_text()))
        result = notifier.send_brief(
            brief_path,
            state_path=self.root / "automatic-state.json",
            sender=lambda payload, _env: captured.append(payload),
            expression=True,
            expression_runner=fake,
            expression_codex_bin="/usr/bin/codex",
            expression_state_root=self.root / "state",
        )
        self.assertEqual(result.status, "sent")
        self.assertIn("expression=NORMAL_WRITING_STYLE", result.message)
        self.assertEqual(captured[0]["_clear_writing_text"], self.good_text())
        self.assertEqual(fake.model_calls, 1)

        class NeverCall:
            def __call__(self, *_args, **_kwargs):
                raise AssertionError("manual send must not invoke Clear Writing")

        manual: list[dict[str, object]] = []
        result = notifier.send_brief(
            brief_path,
            state_path=self.root / "manual-state.json",
            sender=lambda payload, _env: manual.append(payload),
            expression=False,
            expression_runner=NeverCall(),
        )
        self.assertEqual(result.status, "sent")
        self.assertNotIn("_clear_writing_text", manual[0])

    def test_transport_failure_does_not_trigger_second_model_call(self) -> None:
        brief_path = self.root / "brief.json"
        brief_path.write_text(json.dumps(self.brief), encoding="utf-8")
        fake = FakeCodex(self.plugin, stdout=self.jsonl(self.good_text()))

        def fail_transport(_payload, _env):
            raise RuntimeError("smtp failed")

        result = notifier.send_brief(
            brief_path,
            state_path=self.root / "state.json",
            sender=fail_transport,
            expression=True,
            expression_runner=fake,
            expression_codex_bin="/usr/bin/codex",
            expression_state_root=self.root / "neutral",
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(fake.model_calls, 1)


if __name__ == "__main__":
    unittest.main()

