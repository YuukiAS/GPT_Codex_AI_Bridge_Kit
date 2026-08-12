from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import reviewed_handoff as rh
from ai_bridge_kit import reviewed_runner as runner


class ReviewedRunnerTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        state_home = base / "state-home"
        target = base / "project"
        target.mkdir()
        subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
        subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
        status, _ = rh.install_reviewed_handoff(target)
        self.assertTrue(status.installed)
        rh.init_task(target, "001_feature", objective="runner test")
        plan_template = rh.read_text(rh.reviewed_root(target) / "templates" / "PLAN.md")
        rh.write_text(rh.task_root(target, "001_feature") / "PLAN.md", plan_template.replace("<TASK_KEY>", "001_feature"))
        rh.apply_transition(target, "001_feature", expected_state="PLAN_REQUESTED", next_state="PLAN_FROZEN")
        subprocess.check_call(["git", "add", "."], cwd=target)
        subprocess.check_call(["git", "commit", "-m", "freeze plan"], cwd=target, stdout=subprocess.DEVNULL)
        return tmp, target, state_home

    def attach_origin(self, target: Path, base: Path) -> Path:
        remote = base / "origin.git"
        subprocess.check_call(["git", "init", "--bare", "--initial-branch", "main", remote], stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "remote", "add", "origin", str(remote)], cwd=target)
        subprocess.check_call(["git", "push", "-u", "origin", "main"], cwd=target, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote)
        return remote

    @staticmethod
    def codex_only_fake(real_run, callback=None):
        def fake_run(*args, **kwargs):
            command = args[0] if args else kwargs.get("args")
            if isinstance(command, (list, tuple)) and command and str(command[0]).endswith("codex"):
                if callback:
                    callback()
                return subprocess.CompletedProcess(args=command, returncode=0)
            return real_run(*args, **kwargs)
        return fake_run

    def test_machine_state_is_outside_repository(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            path = runner.state_path(target)
            self.assertTrue(str(path).startswith(str(state_home)))
            self.assertFalse(str(path).startswith(str(target / ".ai-bridge")))
            runner.write_local_state(target, {"schema": "AI_BRIDGE_REVIEWED_WATCHER_STATE_V1", "events": {}})
            self.assertEqual(subprocess.check_output(["git", "status", "--porcelain"], cwd=target, text=True).strip(), "")

    def test_watcher_dry_run_only_targets_executor_states(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            result = runner.watcher_once(target, branch="main", sync=False, dry_run=True)
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["task_key"], "001_feature")
            self.assertIn("codex", result["command"][0])
            self.assertIn("PLAN_FROZEN", result["prompt"])
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "NEEDS_GPT_PLANNER"
            rh.write_json(current_path, current)
            subprocess.check_call(["git", "add", str(current_path.relative_to(target))], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "wait planner"], cwd=target, stdout=subprocess.DEVNULL)
            result = runner.watcher_once(target, branch="main", sync=False, dry_run=True)
            self.assertEqual(result["status"], "idle")

    def test_exit_zero_without_state_progress_is_not_marked_complete(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            real_run = subprocess.run
            with mock.patch("subprocess.run", side_effect=self.codex_only_fake(real_run)):
                result = runner.watcher_once(target, branch="main", sync=False)
            self.assertEqual(result["status"], "codex_no_progress")
            local = runner.load_local_state(target)
            event = runner.event_identity("001_feature", rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json"))
            self.assertFalse(local["events"][event]["completed"])
            self.assertEqual(local["events"][event]["attempts"], 1)

    def test_state_progress_requires_committed_clean_state(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"

            def progress():
                current = rh.load_json(current_path)
                current["state"] = "NEEDS_GPT_PLANNER"
                rh.write_json(current_path, current)
                subprocess.check_call(["git", "add", str(current_path.relative_to(target))], cwd=target)
                subprocess.check_call(["git", "commit", "-m", "request planner"], cwd=target, stdout=subprocess.DEVNULL)

            real_run = subprocess.run
            with mock.patch("subprocess.run", side_effect=self.codex_only_fake(real_run, progress)):
                result = runner.watcher_once(target, branch="main", sync=False)
            self.assertEqual(result["status"], "codex_progressed")
            self.assertTrue(result["progressed"])
            self.assertFalse(runner.working_tree_dirty(target))

    def test_dirty_work_from_current_codex_event_blocks_without_retrying_over_it(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            def leave_dirty_work():
                (target / "partial.py").write_text("PARTIAL = True\n", encoding="utf-8")

            real_run = subprocess.run
            with mock.patch("subprocess.run", side_effect=self.codex_only_fake(real_run, leave_dirty_work)), mock.patch(
                "ai_bridge_kit.reviewed_runner.publish_operational_blocker",
                return_value={"published": True, "state": "BLOCKED"},
            ) as blocker:
                result = runner.watcher_once(target, branch="main", sync=False)
            self.assertEqual(result["status"], "codex_dirty_blocked")
            self.assertEqual(result["attempt"], 1)
            blocker.assert_called_once()
            self.assertTrue((target / "partial.py").exists())
            local = runner.load_local_state(target)
            event = runner.event_identity("001_feature", rh.load_json(rh.task_root(target, "001_feature") / "CURRENT.json"))
            self.assertTrue(local["events"][event]["completed"])

    def test_watcher_refuses_preexisting_dirty_tree_before_launch(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            (target / "dirty.txt").write_text("do not overwrite\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dirty working tree"):
                runner.watcher_once(target, branch="main", sync=False, dry_run=True)

    def test_watcher_event_identity_is_plain_operational_locator(self) -> None:
        current = {"state": "REVISE", "review_round": 1, "plan_revision": 0, "implementation_commit": "abc123"}
        event = runner.event_identity("001_feature", current)
        self.assertEqual(event, "001_feature|REVISE|1|0|abc123")
        self.assertNotIn("sha256", event.lower())

    def test_executor_direct_push_is_blocked_by_process_guard(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            self.attach_origin(target, Path(tmp.name))
            (target / "src.py").write_text("VALUE = 2\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "src.py"], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "executor local commit"], cwd=target, stdout=subprocess.DEVNULL)
            result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=target,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=runner.push_guard_environment(target),
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Executor must not push", result.stdout)

    def test_executor_authority_rejects_request_plan_review_and_protected_current(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            pre_head = runner.git_output(target, ["rev-parse", "HEAD"])
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            pre_current = rh.load_json(current_path)
            rh.write_text(rh.task_root(target, "001_feature") / "REQUEST.md", "# changed\n")
            rh.write_text(rh.result_root(target, "001_feature") / "REVIEW_1.md", "# changed\n")
            post_current = dict(pre_current)
            post_current["review_round"] = 1
            rh.write_json(current_path, post_current)
            subprocess.check_call(["git", "add", "."], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "executor authority violation"], cwd=target, stdout=subprocess.DEVNULL)
            post_head = runner.git_output(target, ["rev-parse", "HEAD"])
            errors = runner.executor_authority_errors(target, "001_feature", pre_current, post_current, pre_head, post_head)
            text = "\n".join(errors)
            self.assertIn("review_round", text)
            self.assertIn("REQUEST.md", text)
            self.assertIn("REVIEW_1.md", text)

    def test_publish_clean_progress_pushes_authorized_branch_without_creating_branch(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            self.attach_origin(target, Path(tmp.name))
            before_branches = subprocess.check_output(["git", "branch", "--format", "%(refname:short)"], cwd=target, text=True).splitlines()
            (target / "src.py").write_text("VALUE = 2\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "src.py"], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "executor validated progress"], cwd=target, stdout=subprocess.DEVNULL)
            published, error = runner.publish_clean_progress(target, "main")
            self.assertTrue(published, error)
            self.assertIsNone(error)
            self.assertEqual(runner.branch_heads(target, "main")[0], runner.branch_heads(target, "main")[1])
            after_branches = subprocess.check_output(["git", "branch", "--format", "%(refname:short)"], cwd=target, text=True).splitlines()
            self.assertEqual(before_branches, after_branches)

    def test_publish_clean_progress_rejects_diverged_branch(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            remote = self.attach_origin(target, Path(tmp.name))
            clone = Path(tmp.name) / "other"
            subprocess.check_call(["git", "clone", str(remote), str(clone)], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "other@example.org"], cwd=clone)
            subprocess.check_call(["git", "config", "user.name", "Other User"], cwd=clone)
            (clone / "remote.txt").write_text("remote\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "remote.txt"], cwd=clone)
            subprocess.check_call(["git", "commit", "-m", "remote advance"], cwd=clone, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "push", "origin", "main"], cwd=clone, stdout=subprocess.DEVNULL)

            (target / "local.txt").write_text("local\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "local.txt"], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "local advance"], cwd=target, stdout=subprocess.DEVNULL)
            published, error = runner.publish_clean_progress(target, "main")
            self.assertFalse(published)
            self.assertIn("diverged", str(error))


if __name__ == "__main__":
    unittest.main()
