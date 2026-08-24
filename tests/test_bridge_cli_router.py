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
            self.assertTrue((target / "AGENTS.md").exists())

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
