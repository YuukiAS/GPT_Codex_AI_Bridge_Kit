from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli


class BridgeCliRouterTests(unittest.TestCase):
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

    def test_init_preserves_existing_project_root_under_normal_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            existing = "# Project Rules\n\nDo not rewrite this prose.\n"
            (target / "AGENTS.md").write_text(existing, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--target", str(target)]), 0)
            first = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(first.startswith(existing.rstrip()))
            self.assertNotIn("This file is the repository-level instruction surface", first)
            self.assertEqual(first.count("<!-- ai-bridge-kit:start -->"), 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli.main(["init", "--force", "--target", str(target)]), 0)
            forced = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(forced.startswith(existing.rstrip()))
            self.assertNotIn("This file is the repository-level instruction surface", forced)
            self.assertEqual(forced.count("<!-- ai-bridge-kit:start -->"), 1)

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
