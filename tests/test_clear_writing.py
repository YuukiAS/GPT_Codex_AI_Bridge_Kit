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
        self.prompts: list[str] = []

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
            self.prompts.append(_kwargs["input"])
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
        invocation = result["jsonl_evidence"]["skill_invocation"]
        self.assertEqual(invocation["method"], "explicit_prompt")
        self.assertEqual(invocation["names"], list(clear_writing.REQUIRED_SKILLS))
        self.assertFalse(invocation["jsonl_skill_load_events_required"])
        self.assertNotIn("skill_consumed", result["jsonl_evidence"])
        for name in clear_writing.REQUIRED_SKILLS:
            self.assertIn(f"${name}", fake.prompts[0])
            self.assertEqual(result["plugin"]["skills"][name], self.skills[name].as_posix())

    def test_saved_real_one_turn_trace_uses_normal_style_without_load_events(self) -> None:
        directory = Path(__file__).resolve().parents[1] / "results/bridge-core--product-scope-reset/c32b910"
        raw = json.loads((directory / "C6_MODEL_JSONL.json").read_text())
        record = json.loads((directory / "C6_LIVE_RAW_EVIDENCE.json").read_text())["evidence"]
        self.assertEqual(raw, record["model-jsonl.json"])
        self.assertEqual(raw["returncode"], 0)
        request = record["request.json"]
        text, counts = clear_writing._parse_jsonl(raw["stdout"])
        self.assertEqual(counts["event_counts"]["turn.completed"], 1)
        self.assertIn("不代表目标已完成", text)
        clear_writing.fidelity_check(notifier.expression_facts(request), text)
        fake = FakeCodex(self.plugin, stdout=raw["stdout"])
        result = clear_writing.render_once(
            notifier.expression_facts(request), fallback_text="fallback",
            codex_bin="/usr/bin/codex", state_root=self.root / "replay", runner=fake,
        )
        self.assertEqual(result["mode"], "NORMAL_WRITING_STYLE")
        self.assertEqual(result["text"], text)
        self.assertEqual(result["failure"], "")
        self.assertEqual(fake.model_calls, 1)  # Recorded response, no subprocess.

    def test_positive_completion_still_fails_but_explicit_negation_passes(self) -> None:
        for phrase in (
            "不代表目标已完成", "并不能说明目标已完成", "尚不能认定目标已完成",
            "不代表发布就绪", "尚不能认定发布就绪", "不是目标已完成",
            "不代表“目标已完成”", "不代表 READY", "并不能说明 Goal PASS",
        ):
            with self.subTest(negative=phrase):
                clear_writing.fidelity_check(self.brief, self.good_text() + "。" + phrase)
        for phrase in (
            "目标已完成", "发布就绪", "Goal PASS", "READY", "RELEASE_READY",
            "不代表目标已完成，但发布就绪", "并不能说明目标已完成。目标已完成",
            "不代表目标已完成且发布就绪", "并不是不代表目标已完成",
        ):
            with self.subTest(positive=phrase):
                with self.assertRaisesRegex(clear_writing.ClearWritingError, "CONCLUSION_STRENGTHENED"):
                    clear_writing.fidelity_check(self.brief, self.good_text() + "。" + phrase)

    def test_missing_required_skill_prevents_model_launch(self) -> None:
        self.skills["chinese-prose"].unlink()
        fake = FakeCodex(self.plugin, stdout=self.jsonl(self.good_text()))
        result = clear_writing.render_once(
            self.brief, fallback_text="fallback", codex_bin="/usr/bin/codex",
            state_root=self.root / "missing", runner=fake,
        )
        self.assertEqual(result["mode"], "DETERMINISTIC_FALLBACK")
        self.assertIn("WRITING_STYLE_SKILLS_UNAVAILABLE", result["failure"])
        self.assertEqual(fake.model_calls, 0)

    def test_plugin_identity_failures_keep_model_count_zero(self) -> None:
        fake = FakeCodex(self.plugin, stdout=self.jsonl(self.good_text()))
        for failure in ("disabled", "duplicate", "version_mismatch"):
            def bad_inventory(command, **kwargs):
                if command[1:4] != ["plugin", "list", "--json"]:
                    return fake(command, **kwargs)
                response = fake(command, **kwargs)
                payload = json.loads(response.stdout)
                if failure == "disabled":
                    payload["plugins"][0]["enabled"] = False
                elif failure == "duplicate":
                    payload["plugins"].append(dict(payload["plugins"][0]))
                else:
                    payload["plugins"][0]["version"] = "mismatched"
                response.stdout = json.dumps(payload)
                return response
            with self.subTest(failure=failure):
                result = clear_writing.render_once(
                    self.brief, fallback_text="fallback", codex_bin="/usr/bin/codex",
                    state_root=self.root / "identity", runner=bad_inventory,
                )
                self.assertEqual(result["mode"], "DETERMINISTIC_FALLBACK")
                self.assertEqual(fake.model_calls, 0)

    def test_jsonl_errors_and_invalid_boundary_order_are_not_accepted(self) -> None:
        valid = [json.loads(line) for line in self.jsonl(self.good_text()).splitlines()]
        for event in (
            {"type": "error", "message": "fatal"},
            {"type": "turn.failed"},
            {"type": "item.completed", "item": {"type": "error", "message": "fatal"}},
        ):
            with self.subTest(event=event):
                raw = "\n".join(json.dumps(item) for item in [*valid, event])
                with self.assertRaisesRegex(clear_writing.ClearWritingError, "CODEX_TURN_FAILED"):
                    clear_writing._parse_jsonl(raw)
        raw = "\n".join(json.dumps(item) for item in [valid[1], valid[0], *valid[2:]])
        with self.assertRaisesRegex(clear_writing.ClearWritingError, "BOUNDARY_ORDER_INVALID"):
            clear_writing._parse_jsonl(raw)

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

    def test_current_codex_inventory_nested_source_and_name_manifest_resolve(self) -> None:
        manifest = self.plugin / ".codex-plugin" / "plugin.json"
        manifest.write_text(
            json.dumps({"name": "writing-style", "version": "0.4.0"}),
            encoding="utf-8",
        )

        def current_inventory(command, **_kwargs):
            self.assertEqual(command[1:4], ["plugin", "list", "--json"])
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "installed": [
                            {
                                "pluginId": clear_writing.WRITING_PLUGIN_ID,
                                "marketplaceName": "yuukias-ai-skills",
                                "installed": True,
                                "enabled": True,
                                "version": "0.4.0",
                                "source": {"source": "local", "path": self.plugin.as_posix()},
                            }
                        ]
                    }
                ),
                stderr="",
            )

        resolved = clear_writing.resolve_installed_writing_style(
            codex_bin="/usr/bin/codex",
            runner=current_inventory,
        )
        self.assertEqual(resolved["plugin_id"], clear_writing.WRITING_PLUGIN_ID)
        self.assertEqual(set(resolved["skills"]), set(clear_writing.REQUIRED_SKILLS))

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
