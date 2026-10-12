from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import readiness
from ai_bridge_kit.cli import init_workspace, main as cli_main, validate_workspace


class ReadinessTests(unittest.TestCase):
    def init_git(self, path: Path) -> None:
        subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=path, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=path)
        subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=path)

    def write_task(self, target: Path, task_key: str) -> None:
        task = target / "prompts" / "tasks" / f"{task_key}.md"
        task.write_text(
            "\n".join(
                [
                    "---",
                    f"task_key: {task_key}",
                    "project: fixture",
                    "status: READY",
                    "executor: Codex",
                    "risk_level: low",
                    "allow_code_change: true",
                    "allow_shell_command: true",
                    "allow_network: false",
                    "allow_external_upload: false",
                    "requires_human_approval: false",
                    "---",
                    "",
                    "# Fixture task",
                ]
            ),
            encoding="utf-8",
        )

    def test_validate_strict_fails_confirmed_instruction_budget_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            self.init_git(target)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(init_workspace(target), 0)
            (target / ".codex").mkdir()
            (target / ".codex" / "config.toml").write_text("project_doc_max_bytes = 64\n", encoding="utf-8")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = validate_workspace(target, strict=True)

            self.assertEqual(code, 1)
            self.assertIn("instruction budget exceeded", output.getvalue())

    def test_lite_task_run_dry_run_binds_full_task_sources_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            self.init_git(target)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(init_workspace(target), 0)
            self.write_task(target, "repo--feature")
            subprocess.check_call(["git", "add", "."], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "lite task"], cwd=target, stdout=subprocess.DEVNULL)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli_main(["task", "run", "--target", str(target), "--task-key", "repo--feature", "--dry-run"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "dry_run")
            labels = {item["label"] for item in payload["preflight"]["source_bindings"]}
            self.assertEqual({"repo_agents", "agent_rules", "task"}, labels)

    def test_isolated_control_file_read_rejects_path_traversal_and_preserves_git_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.init_git(root)
            (root / "CONTROL.md").write_text("control\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "CONTROL.md"], cwd=root)
            subprocess.check_call(["git", "commit", "-m", "control"], cwd=root, stdout=subprocess.DEVNULL)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            subprocess.check_call(["git", "remote", "add", "origin", str(root)], cwd=root)

            result = readiness.read_control_file_isolated(
                root,
                expected_repo="local:" + root.resolve().as_posix(),
                commit=commit,
                path="CONTROL.md",
                require_github_https=False,
            )

            self.assertEqual(result["text"], "control\n")
            self.assertTrue(result["protected_git_state_unchanged"])
            with self.assertRaises(readiness.ReadinessError):
                readiness.read_control_file_isolated(
                    root,
                    expected_repo="local:" + root.resolve().as_posix(),
                    commit=commit,
                    path="../CONTROL.md",
                    require_github_https=False,
                )


if __name__ == "__main__":
    unittest.main()
