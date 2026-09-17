from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli


class BridgeCliRouterTests(unittest.TestCase):
    def managed_span(self, content: bytes) -> tuple[int, int]:
        begin = b"<!-- ai-bridge-kit:start -->"
        end = b"<!-- ai-bridge-kit:end -->"
        start = content.index(begin)
        marker_end = content.index(end, start) + len(end)
        for newline in (b"\r\n", b"\n", b"\r"):
            if content.startswith(newline, marker_end):
                return start, marker_end + len(newline)
        return start, marker_end

    def test_legacy_where_and_prompt_delegate_unchanged(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bridge_cli.main(["where"]), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bridge_cli.main(["prompt", "task-template"]), 0)

    def test_legacy_init_and_validate_delegate_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--target", str(target)]), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["validate", "--target", str(target)]), 0)
            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("This file is the repository-level instruction surface", agents)
            self.assertEqual(agents.count("<!-- ai-bridge-kit:start -->"), 1)
            self.assertIn("prompts/AGENT_RULES.md", agents)
            self.assertNotIn("MAJOR.MINOR.PATCH", agents)
            rules = (target / "prompts" / "AGENT_RULES.md").read_text(encoding="utf-8")
            self.assertIn("## Versioning Default", rules)
            self.assertIn("MAJOR.MINOR.PATCH", rules)
            self.assertIn("Docs, TODO, tests, or helper-only changes", rules)
            self.assertIn("commits may remain unreleased", rules)

    def test_init_preserves_existing_project_root_under_normal_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            existing = b"# Project Rules\r\n\r\nDo not rewrite this prose.   \r\n\r\n"
            (target / "AGENTS.md").write_bytes(existing)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--target", str(target)]), 0)
            first = (target / "AGENTS.md").read_bytes()
            self.assertTrue(first.startswith(existing))
            self.assertNotIn(b"This file is the repository-level instruction surface", first)
            self.assertEqual(first.count(b"<!-- ai-bridge-kit:start -->"), 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--force", "--target", str(target)]), 0)
            forced = (target / "AGENTS.md").read_bytes()
            self.assertTrue(forced.startswith(existing))
            self.assertNotIn(b"This file is the repository-level instruction surface", forced)
            self.assertEqual(forced.count(b"<!-- ai-bridge-kit:start -->"), 1)

    def test_force_init_preserves_raw_bytes_around_existing_managed_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            original_prefix = b"# Project Rules\r\n\r\nkeep trailing spaces   \r\n"
            old_block = (
                b"<!-- ai-bridge-kit:start -->\r\n"
                b"old managed block\r\n"
                b"<!-- ai-bridge-kit:end -->\r\n"
            )
            original_suffix = b"\r\nAfter block prose\r\n\tindented\t\r\n"
            (target / "AGENTS.md").write_bytes(original_prefix + old_block + original_suffix)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--force", "--target", str(target)]), 0)
            updated = (target / "AGENTS.md").read_bytes()
            start, span_end = self.managed_span(updated)
            self.assertEqual(updated[:start], original_prefix)
            self.assertEqual(updated[span_end:], original_suffix)
            self.assertEqual(updated.count(b"<!-- ai-bridge-kit:start -->"), 1)

    def test_repeated_normal_init_preserves_mixed_newline_existing_root_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            existing = b"# Project Rules\r\nline two\nline three\rtrailing   "
            (target / "AGENTS.md").write_bytes(existing)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--target", str(target)]), 0)
            first = (target / "AGENTS.md").read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--target", str(target)]), 0)
            second = (target / "AGENTS.md").read_bytes()
            self.assertEqual(second, first)
            self.assertTrue(second.startswith(existing))
            self.assertEqual(second.count(b"<!-- ai-bridge-kit:start -->"), 1)

    def test_agent_flow_still_routes_to_legacy_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["agent-flow", "install", "--target", str(target)]), 0)
            self.assertTrue((target / "automation" / "agent_flow" / "schema.json").exists())

    def test_overleaf_routes_to_dedicated_cli_without_breaking_legacy(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                bridge_cli.main(["overleaf", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
