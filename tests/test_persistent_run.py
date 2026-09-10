from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import persistent_run


def git_call(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class PersistentRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_codex_home = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(self.root / "codex-home")

    def tearDown(self) -> None:
        if self.previous_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = self.previous_codex_home
        self.tmp.cleanup()

    def make_repo(self) -> Path:
        target = self.root / f"project-{len(list(self.root.glob('project-*')))}"
        target.mkdir()
        git_call(target, "init")
        return target

    def write_goal(self, target: Path, rel: str = "prompts/tasks/001_goal.md") -> Path:
        goal = target / rel
        goal.parent.mkdir(parents=True, exist_ok=True)
        goal.write_text("# Goal\n\nPersistent execution: REQUIRED\n", encoding="utf-8")
        return goal

    def test_install_into_real_git_repo_without_lite(self) -> None:
        target = self.make_repo()

        actions = persistent_run.install_persistent_run(target)

        self.assertTrue(any("persistent_run/README.md" in item for item in actions))
        self.assertTrue((target / "automation" / "persistent_run" / "README.md").is_file())
        self.assertTrue((target / "automation" / "persistent_run" / "CONTRACT_TEMPLATE.md").is_file())
        self.assertTrue((target / "automation" / "persistent_run" / "KICKOFF_TEMPLATE.md").is_file())
        self.assertFalse((target / "prompts" / "AGENT_RULES.md").exists())
        self.assertFalse((target / ".agents" / "skills" / "agent-task-executor" / "SKILL.md").exists())

    def test_install_preserves_user_agents_content_and_updates_managed_block(self) -> None:
        target = self.make_repo()
        agents = target / "AGENTS.md"
        agents.write_text("# User Rules\n\nKeep this.\n", encoding="utf-8")

        persistent_run.install_persistent_run(target)
        first = agents.read_text(encoding="utf-8")

        self.assertIn("# User Rules", first)
        self.assertIn("Keep this.", first)
        self.assertIn(persistent_run.PERSISTENT_RUN_BEGIN_MARKER, first)
        self.assertEqual(first.count(persistent_run.PERSISTENT_RUN_BEGIN_MARKER), 1)

        agents.write_text(
            first.replace("0.8.0 唯一 persistence backend", "stale managed text"),
            encoding="utf-8",
        )
        persistent_run.install_persistent_run(target)
        updated = agents.read_text(encoding="utf-8")

        self.assertIn("# User Rules", updated)
        self.assertNotIn("stale managed text", updated)
        self.assertIn("0.8.0 唯一 persistence backend", updated)
        self.assertEqual(updated.count(persistent_run.PERSISTENT_RUN_BEGIN_MARKER), 1)

    def test_repeated_install_is_stable_and_does_not_write_codex_home_or_rules(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)
        first_files = {
            path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted((target / "automation" / "persistent_run").glob("*.md"))
        }
        first_agents = (target / "AGENTS.md").read_text(encoding="utf-8")

        persistent_run.install_persistent_run(target)

        second_files = {
            path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted((target / "automation" / "persistent_run").glob("*.md"))
        }
        self.assertEqual(first_files, second_files)
        self.assertEqual(first_agents, (target / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertFalse(Path(os.environ["CODEX_HOME"]).exists())
        self.assertFalse((target / ".codex" / "rules").exists())

    def test_validate_pass_and_failures(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)

        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 0)
        self.assertTrue(any("Persistent Run validation passed" in line for line in lines))

        (target / "automation" / "persistent_run" / "README.md").unlink()
        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 1)
        self.assertTrue(any("missing automation/persistent_run/README.md" in line for line in lines))

        persistent_run.install_persistent_run(target)
        agents = target / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(persistent_run.PERSISTENT_RUN_END_MARKER, ""),
            encoding="utf-8",
        )
        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 1)
        self.assertTrue(any("markers" in line for line in lines))

    def test_kickoff_requires_existing_repo_relative_goal_and_rejects_escape(self) -> None:
        target = self.make_repo()
        self.write_goal(target)
        outside = self.root / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")

        prompt = persistent_run.render_kickoff_prompt(target, "prompts/tasks/001_goal.md")

        self.assertIn("Goal: `prompts/tasks/001_goal.md`", prompt)
        self.assertIn("persistent tmux session", prompt)
        self.assertIn("Do not ask again", prompt)
        self.assertIn("does not permit scope expansion", prompt)

        with self.assertRaisesRegex(persistent_run.PersistentRunError, "repo-relative"):
            persistent_run.render_kickoff_prompt(target, "../outside.md")
        with self.assertRaisesRegex(persistent_run.PersistentRunError, "repo-relative"):
            persistent_run.render_kickoff_prompt(target, str(outside))
        with self.assertRaisesRegex(persistent_run.PersistentRunError, "does not exist"):
            persistent_run.render_kickoff_prompt(target, "prompts/tasks/missing.md")

    def test_validate_rejects_codex_rules_created_by_target(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)
        (target / ".codex" / "rules").mkdir(parents=True)

        lines, code = persistent_run.validate_persistent_run(target)

        self.assertEqual(code, 1)
        self.assertTrue(any(".codex/rules" in line for line in lines))

    def test_bridge_cli_dispatches_install_validate_and_kickoff(self) -> None:
        target = self.make_repo()
        self.write_goal(target)

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bridge_cli.main(["persistent-run", "install", "--target", str(target)]), 0)
        self.assertIn("persistent_run/README.md", out.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bridge_cli.main(["persistent-run", "validate", "--target", str(target)]), 0)
        self.assertIn("Persistent Run validation passed", out.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(
                bridge_cli.main(
                    [
                        "persistent-run",
                        "prompt",
                        "kickoff",
                        "--target",
                        str(target),
                        "--goal",
                        "prompts/tasks/001_goal.md",
                    ]
                ),
                0,
            )
        self.assertIn("Goal: `prompts/tasks/001_goal.md`", out.getvalue())


if __name__ == "__main__":
    unittest.main()
