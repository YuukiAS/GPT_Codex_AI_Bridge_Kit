from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit.cli import init_workspace, main, validate_workspace


class RepoCliCompatibilityTests(unittest.TestCase):
    def write_task(self, path: Path, task_key: str) -> None:
        path.write_text(
            "\n".join(
                [
                    "---",
                    f'task_key: "{task_key}"',
                    'project: "project-name"',
                    'status: "READY"',
                    'executor: "Codex executor session"',
                    'risk_level: "low"',
                    "allow_code_change: false",
                    "allow_shell_command: true",
                    "allow_network: false",
                    "allow_external_upload: false",
                    "requires_human_approval: false",
                    "---",
                    "",
                    "# Task",
                    "",
                ]
            ),
            encoding="utf-8",
        )

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

    def test_validate_workspace_accepts_semantic_and_existing_legacy_task_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(init_workspace(target), 0)

            tasks_dir = target / "prompts" / "tasks"
            self.write_task(tasks_dir / "repo--feature.md", "repo--feature")
            self.write_task(tasks_dir / "001_legacy.md", "001_legacy")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validate_workspace(target), 0)

    def test_validate_workspace_rejects_path_hostile_task_key_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(init_workspace(target), 0)

            tasks_dir = target / "prompts" / "tasks"
            self.write_task(tasks_dir / "repo---feature.md", "repo---feature")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(validate_workspace(target), 1)
            self.assertIn("task_key must be either legacy", output.getvalue())


if __name__ == "__main__":
    unittest.main()
