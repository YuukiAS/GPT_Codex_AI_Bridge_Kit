from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit.cli import init_workspace, main, validate_workspace


class RepoCliCompatibilityTests(unittest.TestCase):
    def test_init_and_validate_workspace_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"

            with contextlib.redirect_stdout(io.StringIO()):
                init_code = init_workspace(target)
            with contextlib.redirect_stdout(io.StringIO()):
                validate_code = validate_workspace(target)

            self.assertEqual(init_code, 0)
            self.assertEqual(validate_code, 0)
            self.assertTrue((target / "AGENTS.md").exists())
            self.assertTrue((target / "prompts" / "AGENT_RULES.md").exists())
            self.assertTrue(
                (target / ".agents" / "skills" / "agent-task-executor" / "SKILL.md").exists()
            )

    def test_existing_cli_commands_remain_available(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["where"]), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["prompt", "task-template"]), 0)


if __name__ == "__main__":
    unittest.main()
