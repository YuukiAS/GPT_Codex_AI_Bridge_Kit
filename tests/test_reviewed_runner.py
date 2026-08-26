from __future__ import annotations

import contextlib
import io
import json
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

    def commit_valid_executor_handoff(self, target: Path) -> str:
        (target / "src.py").write_text("VALUE = 2\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "src.py"], cwd=target)
        subprocess.check_call(["git", "commit", "-m", "executor implementation"], cwd=target, stdout=subprocess.DEVNULL)
        implementation_commit = runner.git_output(target, ["rev-parse", "HEAD"])
        result_path = rh.result_root(target, "001_feature") / "RESULT.md"
        result_template = rh.read_text(rh.reviewed_root(target) / "templates" / "RESULT.md")
        rh.write_text(
            result_path,
            result_template.replace("<TASK_KEY>", "001_feature").replace("<COMMIT>", implementation_commit),
        )
        current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
        current = rh.load_json(current_path)
        current["state"] = "READY_FOR_GPT_REVIEW"
        current["implementation_commit"] = implementation_commit
        current["ci_status"] = "NOT_REQUIRED"
        current["next_action"] = "WAIT_SCHEDULED_GPT_REVIEW"
        rh.write_json(current_path, current)
        subprocess.check_call(["git", "add", str(result_path.relative_to(target)), str(current_path.relative_to(target))], cwd=target)
        subprocess.check_call(["git", "commit", "-m", "handoff to reviewer"], cwd=target, stdout=subprocess.DEVNULL)
        return implementation_commit

    def remove_out_of_scope_from_plan(self, target: Path) -> None:
        plan_path = rh.task_root(target, "001_feature") / "PLAN.md"
        text = plan_path.read_text(encoding="utf-8")
        plan_path.write_text(
            text.replace("\n## Out of scope\n\nList tempting adjacent improvements that Reviewer must not turn into blocking scope.\n", "\n"),
            encoding="utf-8",
        )

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
            self.assertEqual(result["status"], "waiting_external_review")
            self.assertEqual(result["external_owner"], "Planner")

    def test_watcher_reports_external_wait_without_consuming_executor_attempts(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            (target / "src.py").write_text("VALUE = 2\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "src.py"], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "implementation"], cwd=target, stdout=subprocess.DEVNULL)
            implementation_commit = runner.git_output(target, ["rev-parse", "HEAD"])
            result_path = rh.result_root(target, "001_feature") / "RESULT.md"
            result_template = rh.read_text(rh.reviewed_root(target) / "templates" / "RESULT.md")
            rh.write_text(
                result_path,
                result_template.replace("<TASK_KEY>", "001_feature").replace("<COMMIT>", implementation_commit),
            )
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["state"] = "READY_FOR_GPT_REVIEW"
            current["implementation_commit"] = implementation_commit
            current["ci_status"] = "NOT_REQUIRED"
            current["next_action"] = "WAIT_SCHEDULED_GPT_REVIEW"
            rh.write_json(current_path, current)
            subprocess.check_call(["git", "add", str(result_path.relative_to(target)), str(current_path.relative_to(target))], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "handoff to reviewer"], cwd=target, stdout=subprocess.DEVNULL)

            result = runner.watcher_once(target, branch="main", sync=False)

            self.assertEqual(result["status"], "waiting_external_review")
            self.assertEqual(result["external_owner"], "Reviewer")
            self.assertFalse((runner.state_path(target)).exists())

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

    def test_watcher_status_reports_executor_runtime_and_wait_owner(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            real_run = subprocess.run
            with mock.patch("subprocess.run", side_effect=self.codex_only_fake(real_run)):
                runner.watcher_once(target, branch="main", sync=False)

            status = runner.watcher_status(target, branch="main")

            self.assertEqual(status["schema"], "AI_BRIDGE_REVIEWED_WATCHER_STATUS_V1")
            self.assertEqual(status["branch"], "main")
            task = status["tasks"][0]
            self.assertEqual(task["task"], "001_feature")
            self.assertEqual(task["state"], "PLAN_FROZEN")
            self.assertEqual(task["phase"], "initial_implementation")
            self.assertEqual(task["runtime_type"], "codex_exec")
            self.assertIsNone(task["thread_id"])
            self.assertFalse(task["running"])
            self.assertFalse(task["completed"])
            self.assertEqual(task["last_exit_code"], 0)
            self.assertEqual(task["last_result"], "not_completed")
            self.assertEqual(task["waiting_owner"], "Codex")
            self.assertEqual(task["last_publication_status"], "not_requested")
            self.assertTrue(task["started_at"])
            self.assertTrue(task["completed_at"])

    def test_watcher_status_cli_prints_json(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = runner.main(["status", "--target", str(target), "--branch", "main"])

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["schema"], "AI_BRIDGE_REVIEWED_WATCHER_STATUS_V1")
            self.assertEqual(payload["tasks"][0]["task"], "001_feature")

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

    def test_watcher_run_survives_invalid_workflow_until_remote_plan_fix(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            remote = self.attach_origin(target, Path(tmp.name))
            self.remove_out_of_scope_from_plan(target)
            subprocess.check_call(["git", "add", str((rh.task_root(target, "001_feature") / "PLAN.md").relative_to(target))], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "invalid planner freeze"], cwd=target, stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "push", "origin", "main"], cwd=target, stdout=subprocess.DEVNULL)
            planner = Path(tmp.name) / "planner"
            subprocess.check_call(["git", "clone", str(remote), str(planner)], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "planner@example.org"], cwd=planner)
            subprocess.check_call(["git", "config", "user.name", "Planner"], cwd=planner)

            def remote_fix_after_invalid_sleep(seconds: int) -> None:
                self.assertGreaterEqual(seconds, 600)
                plan_template = rh.read_text(rh.reviewed_root(planner) / "templates" / "PLAN.md")
                rh.write_text(rh.task_root(planner, "001_feature") / "PLAN.md", plan_template.replace("<TASK_KEY>", "001_feature"))
                subprocess.check_call(["git", "add", str((rh.task_root(planner, "001_feature") / "PLAN.md").relative_to(planner))], cwd=planner)
                subprocess.check_call(["git", "commit", "-m", "repair frozen plan"], cwd=planner, stdout=subprocess.DEVNULL)
                subprocess.check_call(["git", "push", "origin", "main"], cwd=planner, stdout=subprocess.DEVNULL)

            launches = []
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"

            def executor_progress(*args, **kwargs):
                launches.append(args)
                pre_head = runner.git_output(target, ["rev-parse", "HEAD"])
                current = rh.load_json(current_path)
                current["state"] = "NEEDS_GPT_PLANNER"
                current["next_action"] = "RUN_GPT_PLANNER"
                rh.write_json(current_path, current)
                subprocess.check_call(["git", "add", str(current_path.relative_to(target))], cwd=target)
                subprocess.check_call(["git", "commit", "-m", "executor requests planner"], cwd=target, stdout=subprocess.DEVNULL)
                post_head = runner.git_output(target, ["rev-parse", "HEAD"])
                return {
                    "task_key": "001_feature",
                    "event": runner.event_identity("001_feature", {"state": "PLAN_FROZEN", "review_round": 0, "plan_revision": 0, "implementation_commit": None}),
                    "launched": True,
                    "exit_code": 0,
                    "progressed": True,
                    "post_state": "NEEDS_GPT_PLANNER",
                    "pre_head": pre_head,
                    "post_head": post_head,
                    "log_path": str(Path(tmp.name) / "executor.log"),
                }

            sleep_calls = []

            def sleep_side_effect(seconds: int) -> None:
                sleep_calls.append(seconds)
                if len(sleep_calls) == 1:
                    remote_fix_after_invalid_sleep(seconds)

            with contextlib.redirect_stdout(io.StringIO()) as output, mock.patch(
                "time.sleep",
                side_effect=sleep_side_effect,
            ), mock.patch("ai_bridge_kit.reviewed_runner.run_codex_event", side_effect=executor_progress):
                code = runner.watcher_run(target, branch="main", interval_seconds=1, max_cycles=3)

            lines = [json.loads(line) for line in output.getvalue().splitlines() if line.strip()]
            self.assertEqual(code, 0)
            self.assertEqual(lines[0]["status"], "invalid_workflow")
            self.assertIn("## Out of scope", "\n".join(lines[0]["errors"]))
            self.assertEqual(lines[1]["status"], "codex_progressed")
            self.assertEqual(lines[2]["status"], "waiting_external_review")
            self.assertEqual(len(launches), 1)
            self.assertEqual(sleep_calls[0], 600)
            local = runner.load_local_state(target)
            self.assertEqual(local["last_status"]["status"], "codex_progressed")
            self.assertEqual(local["last_invalid_workflow"]["status"], "invalid_workflow")
            self.assertFalse(any(record.get("attempts", 0) > 1 for record in local["events"].values()))
            self.assertEqual(runner.branch_heads(target, "main")[0], runner.branch_heads(target, "main")[1])

    def test_watcher_run_returns_failure_for_process_level_error(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            with contextlib.redirect_stdout(io.StringIO()) as output, mock.patch(
                "ai_bridge_kit.reviewed_runner.watcher_once",
                side_effect=RuntimeError("unexpected process failure"),
            ):
                code = runner.watcher_run(target, branch="main", interval_seconds=1, max_cycles=3)

            line = json.loads(output.getvalue().strip())
            self.assertEqual(code, 1)
            self.assertEqual(line["status"], "watcher_error")
            self.assertIn("unexpected process failure", line["error"])

    def test_watcher_event_identity_is_plain_operational_locator(self) -> None:
        current = {"state": "REVISE", "review_round": 1, "plan_revision": 0, "implementation_commit": "abc123"}
        event = runner.event_identity("001_feature", current)
        self.assertEqual(event, "001_feature|REVISE|1|0|abc123")
        self.assertNotIn("sha256", event.lower())
        local_runtime = {"thread_id": "01a03788-3c07-7862-b643-88877d5b3088", "runtime_type": "codex_app"}
        self.assertEqual(runner.event_identity("001_feature", current), event)
        self.assertNotIn(str(local_runtime["thread_id"]), event)

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

    def test_watcher_restart_recovers_crash_after_executor_commit_before_push(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            self.attach_origin(target, Path(tmp.name))
            implementation_commit = self.commit_valid_executor_handoff(target)

            with mock.patch("ai_bridge_kit.reviewed_runner.run_codex_event") as launched:
                result = runner.watcher_once(target, branch="main", sync=True)

            launched.assert_not_called()
            self.assertEqual(result["status"], "recovered_unpublished_progress")
            self.assertEqual(result["task_key"], "001_feature")
            self.assertEqual(result["post_state"], "READY_FOR_GPT_REVIEW")
            self.assertEqual(runner.branch_heads(target, "main")[0], runner.branch_heads(target, "main")[1])
            remote_current = runner.current_at_ref(target, "origin/main", "001_feature")
            self.assertIsNotNone(remote_current)
            self.assertEqual(remote_current["implementation_commit"], implementation_commit)
            local = runner.load_local_state(target)
            self.assertTrue(local["events"][result["event"]]["completed"])
            self.assertTrue(local["events"][result["event"]]["recovered_after_restart"])

    def test_unpublished_recovery_rejects_dirty_tree(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            self.attach_origin(target, Path(tmp.name))
            self.commit_valid_executor_handoff(target)
            (target / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

            result = runner.watcher_once(target, branch="main", sync=True)

            self.assertEqual(result["status"], "unpublished_progress_recovery_failed")
            self.assertIn("dirty", result["reason"])
            local_head, remote_head = runner.branch_heads(target, "main")
            self.assertNotEqual(local_head, remote_head)

    def test_unpublished_recovery_rejects_diverged_branch(self) -> None:
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
            self.commit_valid_executor_handoff(target)

            result = runner.watcher_once(target, branch="main", sync=True)

            self.assertEqual(result["status"], "unpublished_progress_recovery_failed")
            self.assertIn("diverged", result["reason"])

    def test_unpublished_recovery_rejects_executor_authority_violation(self) -> None:
        tmp, target, state_home = self.make_project()
        with tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(state_home)}):
            self.attach_origin(target, Path(tmp.name))
            current_path = rh.task_root(target, "001_feature") / "CURRENT.json"
            current = rh.load_json(current_path)
            current["review_round"] = 1
            current["state"] = "READY_FOR_GPT_REVIEW"
            current["implementation_commit"] = runner.git_output(target, ["rev-parse", "HEAD"])
            current["ci_status"] = "NOT_REQUIRED"
            rh.write_json(current_path, current)
            rh.write_text(rh.result_root(target, "001_feature") / "REVIEW_1.md", "# unauthorized\n")
            subprocess.check_call(["git", "add", "."], cwd=target)
            subprocess.check_call(["git", "commit", "-m", "unauthorized executor handoff"], cwd=target, stdout=subprocess.DEVNULL)

            result = runner.watcher_once(target, branch="main", sync=True)

            self.assertEqual(result["status"], "unpublished_progress_recovery_failed")
            text = "\n".join("\n".join(item.get("errors", [])) for item in result["task_failures"])
            self.assertIn("review_round", text)
            self.assertIn("REVIEW_1.md", text)


if __name__ == "__main__":
    unittest.main()
